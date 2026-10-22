"""Protocol integrity and orchestration checks; no real model fits/native jobs."""
import copy
from pathlib import Path

import pytest

from isaforge import codesign as c
from isaforge.speedup_corpus import family
from scripts import evaluate_expanded_history as experiment


def forbidden(*_, **__):
    raise AssertionError('No actual model fits or target scoring in protocol tests')


def test_prepare_predeclares_fixed_four_targets_and_never_fits(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment.e, 'freeze', forbidden)
    monkeypatch.setattr(experiment.e, 'evaluate', forbidden)
    root = tmp_path/'prepared'
    protocol = experiment.prepare(root)
    assert protocol['targets'] == list(experiment.TARGETS)
    assert len(protocol['policies']) == 12
    assert protocol['seeds'] == [0,1,2,3,4] and protocol['area_caps'] == [32,64,128] and protocol['budgets'] == [1,2,3]
    assert protocol['scope'] == 'consumed-data development' and protocol['change'] == 'expanded historical data only'
    assert protocol['tuning'] is False
    assert protocol['primary']['sources'] == list(experiment.TARGETS[:3])
    assert not (root/'experiments').exists() and not (root/'report.json').exists()
    assert c.unseal(root/'prepared.json')['new_model_fits'] == 0
    assert protocol['costs']['unique_successful_labels'] == 81
    assert protocol['costs']['unique_failed_attempts'] == 3 and protocol['costs']['unique_charged_attempts'] == 84
    assert len(protocol['costs']['unknown_censored_candidate_ids']) == 1
    assert protocol['costs']['actual_calendar_wall_seconds'] is None
    assert [len(protocol['cohorts'][group]['old_fitting_ids']) for group in experiment.TARGETS] == [44,33,29,38]
    assert [protocol['cohorts'][group]['old_available_successes'] for group in experiment.TARGETS] == [45,45,45,39]
    assert experiment.authenticate(root) == protocol
    with pytest.raises(ValueError, match='Fresh prepared'):
        experiment.prepare(root)


def test_expanded_cohorts_exclude_entire_source_all_contexts_families_and_failures():
    corpus, cases, _ = experiment.load_inputs(experiment.CORPUS)
    failed_ids = {row['candidate_id'] for row in corpus['failed_attempts']}
    for group, case in cases.items():
        fold = case['fold']
        target_contexts = {row['benchmark'] for row in corpus['rows']+corpus['failed_attempts'] if row['workload_group'] == group}
        target_families = {family(row['formula']) for row in fold['target']}
        assert set(fold['target_contexts']) == target_contexts
        assert all(row['workload_group'] != group and row['benchmark'] not in target_contexts for row in case['available'])
        assert all(family(row['formula']) not in target_families for row in fold['fitting'])
        assert not set(fold['fitting_ids']) & failed_ids
        assert len(fold['fitting_groups']) >= 2
        expected = {row['candidate_id'] for row in case['available'] if family(row['formula']) not in target_families}
        assert set(fold['fitting_ids']) == expected


def test_modified_protocol_fails_before_fitting(tmp_path, monkeypatch):
    root = tmp_path/'prepared'; experiment.prepare(root)
    protocol = c.unseal(root/'protocol.json'); protocol['seeds'] = [0]
    c.seal(root/'protocol.json', protocol)
    c.seal(root/'prepared.json', dict(protocol_sha256=c.sha(root/'protocol.json')))
    monkeypatch.setattr(experiment.e, 'freeze', forbidden)
    with pytest.raises(ValueError, match='Prepared inputs, sources, packages or fixed cohorts changed'):
        experiment.run(root)


def test_all_expanded_predictions_are_sealed_before_scoring_and_old_baseline_is_reused(tmp_path, monkeypatch):
    root = tmp_path/'prepared'; protocol = experiment.prepare(root)
    events = []
    def freeze(history, public, contexts, output, **kwargs):
        group = kwargs['target_workload']; events.append(('freeze', group))
        assert history and all(row['workload_group'] != group for row in history)
        assert kwargs['scope'] == 'consumed-data development'
        assert not (root/'prediction-release.json').exists()
        output = Path(output)
        c.seal(output/'feasibility-predictions.json', [dict(fixture_only=True)])
        c.seal(output/'feasibility-costs.json', [])
        c.seal(output/'controls11/utility-inference-costs.json', [])
        c.seal(output/'controls11/model/predictions.json', [])
        return dict(historical_training_ids=protocol['cohorts'][group]['expanded_fitting_ids'])
    def evaluate(output, outcomes, *, native_audit, outer_times):
        output = Path(output); group = output.name
        assert len([event for event in events if event[0] == 'freeze']) == 4
        release = c.unseal(root/'prediction-release.json')
        assert release['target_scoring_started'] is False
        assert release['targets'] == list(experiment.TARGETS)
        for name, digest in release['frozen_prediction_packages'].items():
            # Scoring writes reports; prediction package bytes stay unchanged.
            assert c.sha(root/name) == digest
        events.append(('score', group))
        original = experiment._case_paths(group)['original_report']
        result = copy.deepcopy(c.unseal(original))
        # b.search returns acquire scores as tuples; sealed JSON stores lists.
        # Exercise the actual in-memory/serialized boundary without model fits.
        for run in result['runs']:
            for event in run['events']:
                if isinstance(event.get('score'), list): event['score'] = tuple(event['score'])
        return result
    monkeypatch.setattr(experiment.e, 'freeze', freeze)
    monkeypatch.setattr(experiment.e, 'evaluate', evaluate)
    result = experiment.run(root)
    assert len(events) == 12 and all(event[0] == 'freeze' for event in events[:4])
    assert len(result['endpoints']) == 2*4*12*3*3
    assert len(result['source_macro']) == 2*12*3*3
    assert all(row['source_count'] == 3 for row in result['primary'])
    assert all(row['source_count'] == 4 for row in result['source_macro'])
    assert result['trajectories'] == 2*4*180 and result['seed_endpoints'] == 2*4*540
    assert all(row['cycle_reduction_change'] == 0 for row in result['comparisons'])
    assert result['costs']['unique_charged_attempts'] == 84 and result['new_native_jobs'] == 0
    assert result['superiority_established'] is False
    assert result['calibration_established'] is False
    assert len(result['dct_tight_cap']) == 2*12*3
    with pytest.raises(ValueError, match='Fresh prepared experiment'):
        experiment.run(root)


def test_stability_ignores_only_host_inference_timing():
    first = dict(mean_inference_seconds=1, inference_seconds={'a':2}, paid_target_seconds=3,
                 prediction=[dict(value=.2)], replay_search_host_seconds=4)
    second = dict(mean_inference_seconds=10, inference_seconds={'a':20}, paid_target_seconds=3,
                  prediction=[dict(value=.2)], replay_search_host_seconds=40)
    assert experiment.stable(first) == experiment.stable(second)
    second['paid_target_seconds'] = 0
    assert experiment.stable(first) != experiment.stable(second)


def test_stability_canonicalizes_nested_acquisition_score_tuples_without_dropping_scores():
    memory = dict(runs=[dict(events=[dict(action='acquire', score=(1, .125)),
                                    dict(action='measure-complete', charged=1)])])
    serialized = dict(runs=[dict(events=[dict(action='acquire', score=[1, .125]),
                                        dict(action='measure-complete', charged=1)])])
    assert experiment.stable(memory) == experiment.stable(serialized)
    serialized['runs'][0]['events'][0]['score'][1] = .25
    assert experiment.stable(memory) != experiment.stable(serialized)


def test_replay_rejects_changed_prediction_release_before_fit(tmp_path, monkeypatch):
    root = tmp_path/'prepared'; experiment.prepare(root)
    c.seal(root/'prediction-release.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
        target_scoring_started=False, targets=list(experiment.TARGETS), frozen_prediction_packages={}))
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'), prediction_release_sha256='changed'))
    experiment._seal_manifest(root)
    monkeypatch.setattr(experiment.e, 'freeze', forbidden)
    with pytest.raises(ValueError, match='pre-scoring prediction release bindings'):
        experiment.replay(root, tmp_path/'replay')


def prediction_package_fixture(root):
    """Small integrity fixture; bytes are placeholders, not learned models."""
    for cohort in ('old', 'expanded'):
        for group in experiment.TARGETS:
            package = root/'experiments'/cohort/group
            for directory in experiment.PORTABLE_MODELS:
                model = package/directory/'seed-0'
                model.mkdir(parents=True)
                (model/'member-00.json').write_text('{"fixture_weight":1}\n')
                c.seal(model/'schema.json', dict(fixture_only=True,
                    model_artifacts={'member-00.json': c.sha(model/'member-00.json')}))
            c.seal(package/'predictions.json', [dict(candidate_id='fixture-public', mean=.5)])
            c.seal(package/'protocol.json', dict(artifacts=experiment._inventory(package)))
    return dict(frozen_prediction_packages={str(path.relative_to(root)): c.sha(path)
        for path in sorted((root/'experiments').rglob('*')) if path.is_file()})


def test_release_cannot_omit_existing_model_member_even_after_outer_hashes_are_resealed(tmp_path, monkeypatch):
    root = tmp_path/'reference'
    experiment.prepare(root)
    release = prediction_package_fixture(root)
    member = next(name for name in release['frozen_prediction_packages'] if name.endswith('member-00.json'))
    del release['frozen_prediction_packages'][member]
    release.update(protocol_sha256=c.sha(root/'protocol.json'), target_scoring_started=False,
                   targets=list(experiment.TARGETS))
    c.seal(root/'prediction-release.json', release)
    c.seal(root/'report.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json')))
    experiment._seal_manifest(root)
    monkeypatch.setattr(experiment.e, 'authenticate', forbidden)
    monkeypatch.setattr(experiment.e, 'freeze', forbidden)
    with pytest.raises(ValueError, match='exact complete frozen package inventory'):
        experiment.replay(root, tmp_path/'recreated')
    assert not (tmp_path/'recreated').exists()


def test_inner_model_authentication_is_required_after_outer_release_checks(tmp_path, monkeypatch):
    root = tmp_path/'reference'; release = prediction_package_fixture(root)
    member = root/next(name for name in release['frozen_prediction_packages'] if name.endswith('member-00.json'))
    member.write_text('{"fixture_weight":2}\n')
    release['frozen_prediction_packages'][str(member.relative_to(root))] = c.sha(member)
    calls = []
    def authenticate(package):
        calls.append(package)
        experiment._hashes(package, c.unseal(package/'protocol.json')['artifacts'])
    monkeypatch.setattr(experiment.e, 'authenticate', authenticate)
    with pytest.raises(ValueError, match='checksum differs'):
        experiment.authenticate_prediction_packages(root, release)
    assert calls and member.is_relative_to(calls[-1])


def test_deeply_resealed_off_pool_model_change_fails_portable_refit_comparison(tmp_path, monkeypatch):
    reference, recreated = tmp_path/'reference', tmp_path/'recreated'
    prediction_package_fixture(reference)
    prediction_package_fixture(recreated)
    experiment.compare_portable_exports(reference, recreated)
    package = reference/'experiments/expanded'/experiment.TARGETS[0]
    prediction_digest = c.sha(package/'predictions.json')
    model = package/'feasibility-models/seed-0'
    (model/'member-00.json').write_text('{"fixture_weight":2}\n')
    c.seal(model/'schema.json', dict(fixture_only=True,
        model_artifacts={'member-00.json': c.sha(model/'member-00.json')}))
    # Simulate an internally consistent, resealed model change while public
    # prediction values remain unchanged. A prediction-only replay misses this.
    artifacts = {name: digest for name, digest in experiment._inventory(package).items()
                 if name not in ('protocol.json', 'protocol.json.sha256')}
    c.seal(package/'protocol.json', dict(artifacts=artifacts))
    release = dict(frozen_prediction_packages={str(path.relative_to(reference)): c.sha(path)
        for path in sorted((reference/'experiments').rglob('*')) if path.is_file()})
    monkeypatch.setattr(experiment.e, 'authenticate', lambda package:
        experiment._hashes(package, c.unseal(package/'protocol.json')['artifacts']))
    experiment.authenticate_prediction_packages(reference, release)
    assert c.sha(package/'predictions.json') == prediction_digest
    with pytest.raises(ValueError, match='Portable model/schema deterministic refit differs'):
        experiment.compare_portable_exports(reference, recreated)
