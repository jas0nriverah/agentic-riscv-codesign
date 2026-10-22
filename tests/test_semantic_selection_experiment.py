"""Three-stage experiment checks using synthetic cohorts, never native jobs."""
import copy
from pathlib import Path

import pytest

from isaforge import budgeted_selection as b, codesign as c
from scripts import evaluate_semantic_selection as experiment
from test_budgeted_selection import history, measured, predictions, public


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    previous = experiment.previous
    cases = []
    endpoints = []
    count_root = tmp_path/'count'
    monkeypatch.setattr(experiment, 'ROOT', tmp_path)
    monkeypatch.setattr(experiment, 'COUNT', count_root)
    monkeypatch.setattr(experiment, 'CORPUS', tmp_path/'corpus'/'corpus.json')
    monkeypatch.setattr(experiment, 'NEGATIVE', tmp_path/'negative'/'README.md')
    experiment.NEGATIVE.parent.mkdir()
    experiment.NEGATIVE.write_text('Preserved earlier negative descriptor result.\n')
    runtime = tmp_path/'runtime.py'
    runtime.write_text('# Synthetic experiment binding\n')
    monkeypatch.setattr(experiment, 'SOURCES', ('runtime.py',))
    actual_specs = previous.specs()
    for index, spec in enumerate(actual_specs):
        identity, source = spec['case_id'], spec['source']
        folder = count_root/'inputs'/identity
        target = [public('target-'+str(index)+'-'+str(i), formula, source+':ctx') for i, formula in enumerate((
            'add(in0,slli(in1,3))', 'slli(add(in0,in1),2)', 'sub(in0,in1)'))]
        training = history()
        cached = [predictions(training, target, seed) for seed in previous.SEEDS]
        native = tmp_path/'native'/identity
        outcomes = [measured(row, area=area) for row, area in zip(target, (30, 71, 40))]
        audit = dict(outcomes=outcomes)
        outer = {row['candidate_id']: 3. for row in outcomes}
        c.seal(native/'audit.json', audit)
        c.seal(native/'outer.json', outer)
        for name, value in (('public.json', target), ('history.json', training),
                            ('predictions.json', cached), ('model-protocol.json', {'synthetic': identity})):
            c.seal(folder/name, value)
        curves = []
        for cap in previous.CAPS:
            curve = []
            for budget in previous.BUDGETS:
                paid = outcomes[:budget]
                best = max([1.]+[row['speedup'] for row in paid if b._feasible(row, cap, 12.)])
                curve.append(dict(budget=budget, best_speedup=best,
                    attempted_ids=[row['candidate_id'] for row in paid],
                    target_measurement_seconds=2.*budget, target_outer_operation_seconds=3.*budget,
                    known_infeasible_attempts=sum(not b._feasible(row, cap, 12.) for row in paid),
                    unknown_attempts=0, inference_seconds=0.))
            for seed in previous.SEEDS:
                curves.append(dict(cap=cap, seed=seed, curve=copy.deepcopy(curve)))
        control = dict(runs=[dict(policy=policy, **run) for policy in previous.POLICY_LABELS for run in curves],
            protocol_sha256=c.sha(folder/'model-protocol.json'), native_audit_digest=c.digest(audit),
            outcomes_sha256=c.digest(outcomes), reference_censored=False)
        package = tmp_path/'packages'/identity
        c.seal(package/'report.json', control)
        c.seal(count_root/'new-policy'/identity/'report.json', dict(outcomes_sha256=c.digest(outcomes)))
        rows = previous.endpoints_for_source(source, control, outcomes)
        rows += previous.summarize_new(source, curves, outcomes, False)
        endpoints.extend(dict(case_id=identity, cohort=spec['cohort'], **row) for row in rows)
        cases.append(dict(case_id=identity, cohort=spec['cohort'], source=source,
            public_ids=[row['candidate_id'] for row in target],
            fitting_ids=[row['candidate_id'] for row in training], fitting_rows=len(training),
            package=package.relative_to(tmp_path).as_posix(), audit=(native/'audit.json').relative_to(tmp_path).as_posix(),
            outer=(native/'outer.json').relative_to(tmp_path).as_posix(),
            cached_files={name: c.sha(folder/name) for name in previous.FILES}))
    c.seal(count_root/'protocol.json', {'synthetic': True})
    c.seal(count_root/'prediction-release.json', {'synthetic': True})
    c.seal(count_root/'runtime-costs.json', {'synthetic': True})
    c.seal(count_root/'report.json', dict(policies=list(previous.POLICIES), cases=9,
        endpoints=endpoints, costs=dict(unique_charged_attempts=90, unique_recorded_attempt_seconds=100.,
            clock_accounting={'synthetic': True}, preserved_failed_attempts=3)))
    previous.seal_manifest(count_root)
    base = dict(cases=cases, input_bindings={}, benefit='unchanged speedup gain', primary={'cap': 64, 'budget': 3},
        secondary=['DCT separately', 'Expint separately'], packages={name: previous.importlib.metadata.version(name)
                                                                  for name in previous.PACKAGES})
    monkeypatch.setattr(previous, 'authenticate', lambda root: base)
    monkeypatch.setattr(previous, 'planned_protocol', lambda: copy.deepcopy(base))
    monkeypatch.setattr(previous, 'specs', lambda: [{'case_id': case['case_id']} for case in cases])
    # Native-evidence checking is tested elsewhere. This fixture supplies no native evidence.
    monkeypatch.setattr(previous.e, 'checked_outcomes', lambda *args: False)
    return dict(root=tmp_path, prepared=tmp_path/'prepared', cases=cases, base=base, runtime=runtime)


def reseal_release(root):
    release = c.unseal(root/'prediction-release.json')
    release['input_files'] = experiment.previous.inventory(root/'inputs')
    release['initial_files'] = experiment.previous.inventory(root/'initial')
    c.seal(root/'prediction-release.json', release)
    prepared = c.unseal(root/'prepared.json')
    prepared['prediction_release_sha256'] = c.sha(root/'prediction-release.json')
    c.seal(root/'prepared.json', prepared)


def test_prepare_fits_all_nine_before_any_target_read(fixture, monkeypatch):
    original = c.unseal
    targets = {fixture['root']/case['audit'] for case in fixture['cases']}
    fit_ids = []
    real_fit = experiment.semantic.SemanticHardwareSurrogate.fit

    def read(path):
        assert Path(path) not in targets, 'Preparation must not open target outcomes'
        return original(path)

    def fit(model, rows):
        fit_ids.append([row['candidate_id'] for row in rows])
        assert all(not value.startswith('target-') for value in fit_ids[-1])
        return real_fit(model, rows)

    monkeypatch.setattr(c, 'unseal', read)
    monkeypatch.setattr(experiment.semantic.SemanticHardwareSurrogate, 'fit', fit)
    protocol = experiment.prepare(fixture['prepared'])
    assert len(fit_ids) == 9
    assert protocol['feature_columns'] == list(experiment.semantic.COLUMNS)
    assert len(protocol['policies']) == 14
    assert c.unseal(fixture['prepared']/'prediction-release.json')['target_scoring_started'] is False
    experiment.authenticate(fixture['prepared'])


def test_run_requires_complete_preparation_and_never_overwrites(fixture):
    with pytest.raises(FileNotFoundError):
        experiment.run(fixture['prepared'])
    experiment.prepare(fixture['prepared'])
    with pytest.raises(ValueError, match='Fresh'):
        experiment.prepare(fixture['prepared'])
    with pytest.raises(ValueError, match='outside'):
        experiment.prepare(experiment.COUNT/'nested')


def test_exact_case_count_order_and_source_bindings_are_gated(fixture):
    experiment.prepare(fixture['prepared'])
    fixture['runtime'].write_text('# Altered runtime\n')
    with pytest.raises(ValueError, match='Source'):
        experiment.authenticate(fixture['prepared'])
    fixture['runtime'].write_text('# Synthetic experiment binding\n')
    fixture['base']['cases'].reverse()
    with pytest.raises(ValueError):
        experiment.authenticate(fixture['prepared'])


def test_missing_initial_member_fails_even_after_outer_reseal(fixture):
    experiment.prepare(fixture['prepared'])
    path = fixture['prepared']/'initial'/fixture['cases'][-1]['case_id']/'predictions.json'
    path.unlink()
    Path(str(path)+'.sha256').unlink()
    reseal_release(fixture['prepared'])
    with pytest.raises(ValueError, match='inventory'):
        experiment.authenticate(fixture['prepared'])


@pytest.mark.parametrize('change', ('columns', 'cohort', 'source', 'packages', 'uncertainty'))
def test_exact_snapshot_and_prediction_gate_survives_outer_reseal(fixture, change):
    experiment.prepare(fixture['prepared'])
    initial = fixture['prepared']/'initial'/fixture['cases'][0]['case_id']
    if change == 'uncertainty':
        path = initial/'predictions.json'
        value = c.unseal(path)
        value[0]['area_delta_lut4_std'] = -1.
    else:
        path = initial/'snapshot.json'
        value = c.unseal(path)
        if change == 'columns': value['columns'].reverse()
        elif change == 'cohort': value['training_ids'] = value['training_ids'][:-1]
        elif change == 'source': value['source_bindings']['isaforge/semantic_selection.py'] = '0'*64
        elif change == 'packages': value['packages']['scikit-learn'] = 'altered'
    c.seal(path, value)
    reseal_release(fixture['prepared'])
    with pytest.raises(ValueError):
        experiment.authenticate(fixture['prepared'])


def test_prepare_failure_preserves_partial_models_and_cannot_resume(fixture, monkeypatch):
    real = experiment.semantic.SemanticHardwareSurrogate.fit
    calls = []

    def fit(model, rows):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('Synthetic fit interruption')
        return real(model, rows)

    monkeypatch.setattr(experiment.semantic.SemanticHardwareSurrogate, 'fit', fit)
    with pytest.raises(RuntimeError, match='interruption'):
        experiment.prepare(fixture['prepared'])
    assert (fixture['prepared']/'prepare-failure.json').exists()
    assert len(experiment.previous._inventory(fixture['prepared']/'initial')) == 4
    assert not (fixture['prepared']/'prediction-release.json').exists()
    with pytest.raises(ValueError, match='Fresh'):
        experiment.prepare(fixture['prepared'])


def test_complete_run_and_exact_replay_preserve_controls_costs_and_paid_model_proofs(fixture):
    root = fixture['prepared']
    experiment.prepare(root)
    result = experiment.run(root)
    assert result['new_policy_trajectories'] == 135
    assert result['new_policy_seed_endpoints'] == 405
    assert len(result['endpoints']) == 9*14*9
    assert result['costs']['unique_charged_attempts'] == 90
    assert result['new_native_jobs'] == 0 and result['tuning'] is False
    assert set(row['source'] for row in result['comparisons']) == {case['source'] for case in fixture['cases']}
    runtime = c.unseal(root/'runtime-costs.json')
    assert runtime['initial_surrogate_fits'] == 9 and runtime['paid_update_surrogate_fits'] == 270
    assert len(experiment.previous._inventory(root/'acquisitions')) == 405*2
    proof = c.unseal(next((root/'acquisitions').rglob('01.json')))
    assert len(proof['training_ids']) == 4
    assert len(proof['model_state_sha256']) == 64
    assert proof['event']['paid_target_ids_before_query'] == proof['training_ids'][-1:]
    replay = experiment.replay(root, fixture['root']/'replay')
    assert experiment.stable(replay) == experiment.stable(result)
    with pytest.raises(ValueError, match='Fresh'):
        experiment.run(root)
    with pytest.raises(ValueError, match='overlap'):
        experiment.replay(root, root/'nested')


def test_strict_projection_excludes_only_host_timers():
    original = dict(inference_seconds=1., paid_update_host_seconds=2.,
        measurement_seconds=4., area=30., attempted_ids=['a'], model_state_sha256='same')
    changed = {**original, 'inference_seconds': 99.}
    assert experiment.stable(original) == experiment.stable(changed)
    for key, value in (('measurement_seconds', 4.1), ('area', 31.), ('attempted_ids', ['b']), ('model_state_sha256', 'altered')):
        assert experiment.stable(original) != experiment.stable({**original, key: value})


def test_replay_rejects_deeply_resealed_prediction_before_target_scoring(fixture, monkeypatch):
    root = fixture['prepared']
    experiment.prepare(root)
    path = root/'initial'/fixture['cases'][0]['case_id']/'predictions.json'
    predictions = c.unseal(path)
    predictions[0]['area_delta_lut4_mean'] += .01
    c.seal(path, predictions)
    reseal_release(root)
    c.seal(root/'report.json', {'synthetic_completed_reference': True})
    experiment.previous.seal_manifest(root)

    def forbidden(*args):
        raise AssertionError('Target scoring must not run after changed initial predictions')

    monkeypatch.setattr(experiment, 'run', forbidden)
    with pytest.raises(ValueError, match='initial predictions'):
        experiment.replay(root, fixture['root']/'tamper-replay')
    assert (fixture['root']/'tamper-replay'/'replay-failure.json').exists()


def test_run_failure_is_preserved_and_not_retried(fixture, monkeypatch):
    root = fixture['prepared']
    experiment.prepare(root)
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise RuntimeError('Synthetic search interruption')

    monkeypatch.setattr(experiment.count, 'search', failed)
    with pytest.raises(RuntimeError, match='interruption'):
        experiment.run(root)
    assert (root/'run-failure.json').exists()
    assert len(calls) == 1
    with pytest.raises(ValueError, match='never resume'):
        experiment.run(root)
    assert len(calls) == 1


@pytest.mark.skipif(not (experiment.OUTPUT/'report.json').exists(), reason='Completed development artifact unavailable')
def test_completed_development_manifest_and_every_paid_prefix_without_refitting(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Completed artifact audit must not refit scientific models')

    monkeypatch.setattr(experiment.semantic.SemanticHardwareSurrogate, 'fit', forbidden)
    root = experiment.OUTPUT
    experiment.previous._manifest(root)
    protocol = experiment.authenticate(root)
    result = c.unseal(root/'report.json')
    previous = c.unseal(experiment.COUNT/'report.json')
    assert len(protocol['cases']) == 9 and len(result['policies']) == 14
    assert result['costs'] == previous['costs']
    assert result['costs']['unique_charged_attempts'] == 90
    assert [row for row in result['endpoints'] if row['policy'] != experiment.POLICY] == previous['endpoints']
    assert result['new_native_jobs'] == 0
    observed = 0
    for case in protocol['cases']:
        report = c.unseal(root/'new-policy'/case['case_id']/'report.json')
        for run in report['runs']:
            acquired = [event for event in run['events'] if event['action'] == 'acquire']
            assert len(acquired) == 3
            for index, event in enumerate(acquired):
                proof = c.unseal(root/'acquisitions'/case['case_id']/f"cap{run['cap']}-seed{run['seed']}"/f'{index:02d}.json')
                assert proof['event'] == event
                assert proof['training_ids'] == case['fitting_ids']+event['paid_target_ids_before_query']
                assert event['charged_before_query'] == index
                assert event['attempted_ids_before_query'] == run['curve'][-1]['attempted_ids'][:index]
                assert len(proof['model_state_sha256']) == 64
                observed += 1
    assert observed == 405
