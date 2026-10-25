"""Synthetic sealed-run integration; never scores real development/native pools."""
import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from isaforge import codesign as c, finite_selection as f, semantic_selection as s
from scripts import evaluate_finite_selection as e
from test_budgeted_selection import history, measured, public


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    """Ten small cached cases with six sources, deliberately reduced cap/seed grid."""
    source = tmp_path/'sealed-inputs'
    source.mkdir()
    monkeypatch.setattr(e, 'CAPS', (64,))
    monkeypatch.setattr(e, 'SEEDS', (0,))
    monkeypatch.setattr(e, 'BUDGETS', (1, 2, 3))
    monkeypatch.setattr(e, 'input_roots', lambda: (source,))
    rows = history()
    model = s.SemanticHardwareSurrogate().fit(rows)
    coordinates = [(cohort, group) for cohort in ('old', 'expanded')
                   for group in (*e.PRIMARY_SOURCES, 'beebs-jfdctint')]
    coordinates += [('fresh', 'beebs-expint'), ('cached', 'tacle-bitcount')]
    cases, targets, controls = [], {}, {}
    semantic_controls = []
    for index, (cohort, group) in enumerate(coordinates):
        identity = cohort+'__'+group
        directory = source/identity
        directory.mkdir()
        pool = [public(f'{index}:t1', 'add(in0,slli(in1,1))', group+':ctx', saved_cycles=60),
                public(f'{index}:t2', 'sub(in0,in1)', group+':ctx', saved_cycles=30),
                public(f'{index}:t3', 'add(in0,srli(in1,1))', group+':ctx', saved_cycles=20)]
        outcomes = [measured(row, area=area, savings=row['latency_features']['estimated_saved_cycles'], seconds=2.+i)
                    for i, (row, area) in enumerate(zip(pool, (80, 40, 25)))]
        audit = dict(outcomes=outcomes, new_native_jobs=0, fixture_only=True)
        native_outer = {row['candidate_id']: row['measurement_seconds']+1 for row in outcomes}
        protocol = dict(historical_training_ids=[row['candidate_id'] for row in rows], excluded_related_ids=['excluded'],
                        cost_provenance=dict(qualification_seconds=5, baseline_seconds=3, fixture_only=True))
        for filename, value in [('public.json', pool), ('history.json', rows),
            ('predictions.json', model.predict(pool)), ('snapshot.json', model.snapshot()),
            ('model-protocol.json', protocol), ('audit.json', audit), ('outer.json', native_outer)]:
            c.seal(directory/filename, value)
        points = []
        for policy in e.OLD_POLICIES:
            for budget in e.BUDGETS:
                point = dict(policy=policy, cap=64, budget=budget, dependent_seed_count=1,
                    mean_verified_cycle_reduction=0., mean_cycle_reduction_regret=.03,
                    mean_target_measurement_seconds=2.*budget, mean_target_outer_operation_seconds=3.*budget,
                    mean_inference_seconds=.123, fixture_only=True)
                if index < 9:
                    point.update(case_id=identity, cohort=cohort, workload_group=group)
                points.append(point)
        controls[identity] = points
        if index < 9:
            semantic_controls.extend(points)
        target_report = directory/'controls.json' if index == 9 else source/'semantic-controls.json'
        additional = []
        if index < 9:
            for filename in ('twelve-report.json', 'count-report.json', 'semantic-report.json'):
                path = directory/filename
                c.seal(path, dict(outcomes_sha256=c.digest(outcomes), native_audit_digest=c.digest(audit),
                                 protocol_sha256=c.sha(directory/'model-protocol.json')))
                additional.append(str(path))
        else:
            c.seal(target_report, dict(policies=list(e.OLD_POLICIES), endpoints=points,
                outcomes_sha256=c.digest(outcomes), native_audit_digest=c.digest(audit)))
        cases.append(dict(case_id=identity, source=group, cohort=cohort, expected_rows=len(rows),
            public=str(directory/'public.json'), history=str(directory/'history.json'),
            cached_predictions=str(directory/'predictions.json'), cached_snapshot=str(directory/'snapshot.json'),
            model_protocol=str(directory/'model-protocol.json'), control_report=str(target_report),
            control_kind='bitcount' if index == 9 else 'semantic', audit=str(directory/'audit.json'),
            outer=str(directory/'outer.json'), additional_bindings=additional,
            original_cost_provenance=protocol['cost_provenance']))
        targets[identity] = pool
    c.seal(source/'semantic-controls.json', dict(policies=list(e.OLD_POLICIES), endpoints=semantic_controls))
    corpus = source/'corpus.json'
    c.seal(corpus, dict(fixture_only=True, successful_labels=3, total_candidate_attempts=3,
                       total_candidate_attempt_wall_seconds=6.))
    monkeypatch.setattr(e, 'specs', lambda: copy.deepcopy(cases))
    monkeypatch.setattr(e, 'historical_accounting', lambda: dict(successful_labels=3, failed_attempts=0,
        charged_attempts=3, recorded_candidate_ledger_seconds=6., source_corpus=str(corpus),
        source_corpus_sha256=c.sha(corpus), actual_calendar_wall_seconds=None, fixture_only=True))
    e.seal_manifest(source)
    return dict(source=source, root=tmp_path/'run', rows=rows, cases=cases,
                targets=targets, controls=controls, tmp=tmp_path)


def test_prepare_seals_every_initial_before_any_native_audit_and_no_search(fixture):
    opened = []
    real_unseal = c.unseal
    def checked(path):
        path = Path(path)
        assert path.name not in ('audit.json', 'outer.json'), 'Preparation opened target native outcomes'
        opened.append(path)
        return real_unseal(path)
    with patch.object(c, 'unseal', side_effect=checked), \
         patch.object(f, 'search', side_effect=AssertionError('No policy scoring during prepare')):
        protocol = e.prepare(fixture['root'])
    root = fixture['root']
    e.manifest(root)
    release = c.unseal(root/'prediction-release.json')
    assert release['case_ids'] == [row['case_id'] for row in fixture['cases']]
    assert len(protocol['cases']) == 10
    assert not release['native_outcomes_parsed']
    assert release['initial_surrogate_fits'] == 10 and release['initial_scalar_gp_fits'] == 30
    assert len(release['input_files']) == 10*4*2
    assert len(release['initial_files']) == 10*3*2
    assert set(protocol['old_policies']) == set(e.OLD_POLICIES)
    assert protocol['settings']['fantasy_draws'] == 128
    assert protocol['source_bindings'] == e.source_bindings()
    for case in fixture['cases']:
        identity = case['case_id']
        snapshot = c.unseal(root/'initial'/identity/'snapshot.json')
        assert snapshot['initial_snapshot'] == c.unseal(case['cached_snapshot'])
        assert snapshot['paid_ids'] == [] and not snapshot['hypothetical']
    with pytest.raises(ValueError, match='Fresh output'):
        e.prepare(root)


def test_run_complete_horizon_grid_old_controls_exact_and_all_rebuilds_before_audits(fixture):
    root = fixture['root']
    e.prepare(root)
    original_fit, original_outcomes = s.SemanticHardwareSurrogate.fit, e._read_outcomes
    fits, audit_cases = [], []
    def fit(self, rows):
        fits.append([r['candidate_id'] for r in rows])
        return original_fit(self, rows)
    def outcomes(case, public):
        assert len(fits) == 10, 'Audit opened before all initial model rebuilds completed'
        audit_cases.append(case['case_id'])
        assert c.unseal(root/'prediction-release.json')['case_ids'] == [r['case_id'] for r in fixture['cases']]
        return original_outcomes(case, public)
    with patch.object(s.SemanticHardwareSurrogate, 'fit', fit), patch.object(e, '_read_outcomes', side_effect=outcomes):
        report = e.run(root)
    assert len(fits) == len(audit_cases) == 10
    assert report['case_count'] == 10 and report['distinct_consumed_target_sources'] == 6
    assert report['new_trajectories'] == 90 and report['new_curve_points'] == 180
    assert report['conditional_updates'] == 180
    assert report['observer_validation_conditional_updates'] == 180
    assert report['calibrated_benefit_assumption_violations'] == 0
    assert report['archived_control_endpoint_rows'] == 420
    assert report['costs']['prepare_surrogate_fits'] == 10
    assert report['costs']['run_initial_rebuild_surrogate_fits'] == 10
    assert report['costs']['estimator_fits_inside_search'] == 0
    assert report['costs']['counterfactual_target_search']['charged_replayed_attempts'] == 180
    terminal_cost = sum(c.unseal(root/entry['path'])['curve'][-1]['target_measurement_seconds']
                        for entry in report['runs'])
    assert report['costs']['counterfactual_target_search']['target_measurement_seconds'] == terminal_cost
    assert report['costs']['reused_target_pool']['unique_attempts'] == 30
    assert report['historical_accounting']['charged_attempts'] == 3
    assert report['new_native_jobs'] == 0 and not report['model_promoted']
    assert not report['superiority_established'] and not report['calibration_established']
    archives = c.unseal(root/'archived-controls.json')
    for archive in archives:
        assert archive['endpoints'] == fixture['controls'][archive['case_id']]
    points = c.unseal(root/'seed-endpoints.json')
    assert sum(p['endpoint_kind'] == 'B3-prefix' for p in points) == 90
    assert sum(p['endpoint_kind'] == 'horizon-aware-terminal' for p in points) == 90
    for entry in report['runs']:
        run = c.unseal(root/entry['path'])
        planned = entry['planned_budget']
        assert f'/B{planned}/' in entry['path']
        assert len(run['curve']) == planned
        assert run['curve'][-1]['budget'] == planned
        assert run['curve'][-1]['target_measurement_seconds'] >= 2*planned
        assert all(proof['event']['planned_budget'] == planned for proof in run['acquisition_proofs'])
        assert [p['event']['remaining_queries'] for p in run['acquisition_proofs']] == list(range(planned, 0, -1))
        assert entry['scientific_run_sha256'] == c.digest(e.stable(run))
    for row in report['endpoints']:
        if row['endpoint_kind'] == 'horizon-aware-terminal':
            assert row['planned_budget'] == row['budget']
        else:
            assert row['planned_budget'] == 3
    assert {r['cohort'] for r in report['primary_source_macros']} == {'old', 'expanded'}
    assert all(r['source_count'] == 3 for r in report['primary_source_macros'])
    assert not any(r.get('source_count') == 10 for r in report['primary_source_macros'])
    assert {r['comparator'] for r in report['comparisons']} == {'latency_cost_heuristic', f.MYOPIC}
    assert (root/'README.md').read_text().startswith('# Fixed joint-posterior')
    assert (root/'endpoints.csv').exists()
    assert (root/'archived-controls.csv').exists()
    e.manifest(root)
    with pytest.raises(ValueError, match='Fresh prepared run'):
        e.run(root)


def test_replay_exact_states_proofs_paid_costs_and_retains_both_raw_host_arrays(fixture):
    root = fixture['root']
    e.prepare(root)
    original = e.run(root)
    output = fixture['tmp']/'replay'
    replay = e.replay(root, output)
    assert e.stable(original) == e.stable(replay)
    assert e.inventory(root/'acquisitions') == e.inventory(output/'acquisitions')
    assert c.unseal(root/'archived-controls.json') == c.unseal(output/'archived-controls.json')
    receipt = c.unseal(output/'replay-verification.json')
    assert receipt['all_fourteen_controls_exact']
    assert receipt['compared_trajectories'] == 90
    assert receipt['raw_reference_runtime'] == c.unseal(root/'runtime-costs.json')
    assert receipt['raw_replayed_runtime'] == c.unseal(output/'runtime-costs.json')
    assert receipt['raw_reference_runtime']['run_initial_rebuild_records'][0]['host_monotonic_start_ns'] != \
        receipt['raw_replayed_runtime']['run_initial_rebuild_records'][0]['host_monotonic_start_ns']
    e.manifest(output)


def test_proofs_are_sealed_before_unique_current_query_provider_release(fixture):
    root = fixture['root']
    e.prepare(root)
    original = f.search
    released = []
    def search(public, training, provider, **kwargs):
        seen = []
        original_observer = kwargs['on_acquire']
        def observer(proof):
            assert proof['event']['attempted_ids_before_query'] == seen
            original_observer(proof)
        def dispatch(candidate):
            context = Path(f"B{kwargs['budget']}")/kwargs['policy']
            case = next(r for r in fixture['cases'] if candidate['candidate_id'] in
                        [p['candidate_id'] for p in fixture['targets'][r['case_id']]])
            path = root/'acquisitions'/context/case['case_id']/f"cap64-seed{kwargs['seed']}"/f'{len(seen):02d}.json'
            assert c.unseal(path)['proof']['event']['candidate_id'] == candidate['candidate_id']
            assert candidate['candidate_id'] not in seen
            seen.append(candidate['candidate_id'])
            released.append(candidate['candidate_id'])
            return provider(candidate)
        kwargs['on_acquire'] = observer
        return original(public, training, dispatch, **kwargs)
    with patch.object(f, 'search', side_effect=search):
        e.run(root)
    assert len(released) == 180


def test_failed_unknown_charged_and_benefit_misses_retained(fixture):
    # Adjust only this synthetic fixture's native records and their explicit bindings.
    for case in fixture['cases']:
        audit = c.unseal(case['audit'])
        for row in audit['outcomes']:
            row['candidate_cycles'] -= 1
            row['speedup'] = row['baseline_cycles']/row['candidate_cycles']
        failed = copy.deepcopy(fixture['targets'][case['case_id']][0])
        failed.update(status='failed', measurement_seconds=7., error='fixture infrastructure interruption',
                      failure_class='infrastructure', reference_censored=True)
        audit['outcomes'][0] = failed
        c.seal(case['audit'], audit)
        outer = c.unseal(case['outer'])
        outer[failed['candidate_id']] = 8.
        c.seal(case['outer'], outer)
        if case['control_kind'] == 'bitcount':
            control = c.unseal(case['control_report'])
            control.update(native_audit_digest=c.digest(audit), outcomes_sha256=c.digest(audit['outcomes']))
            c.seal(case['control_report'], control)
        else:
            for path in case['additional_bindings']:
                report = c.unseal(path)
                report.update(native_audit_digest=c.digest(audit), outcomes_sha256=c.digest(audit['outcomes']))
                c.seal(path, report)
    e.seal_manifest(fixture['source'])
    root = fixture['root']
    e.prepare(root)
    report = e.run(root)
    assert 0 < report['conditional_updates'] < report['new_curve_points']
    assert report['calibrated_benefit_assumption_violations'] == report['conditional_updates']
    assert report['observer_validation_conditional_updates'] == report['conditional_updates']
    assert any(r['mean_unknown_attempts'] > 0 for r in report['endpoints'])
    assert all(not r['reference_complete'] and r['regret_is_lower_bound'] for r in report['endpoints'])
    for entry in report['runs']:
        run = c.unseal(root/entry['path'])
        assert run['curve'][-1]['failed_attempts'] == entry['planned_budget']-run['conditional_updates']
        if run['curve'][-1]['failed_attempts']:
            assert run['curve'][-1]['target_measurement_seconds'] >= 7


def test_forged_acquisition_prefix_fails_before_release_preserving_run_failure(fixture):
    root = fixture['root']
    e.prepare(root)
    original = f.search
    called = []
    def forged(public, training, provider, **kwargs):
        observer = kwargs['on_acquire']
        def bad_observer(proof):
            proof['posterior_snapshot']['paid_outcomes_sha256'] = c.digest(['unpaid-label'])
            observer(proof)
        def forbidden(_):
            called.append(True)
            pytest.fail('Provider was called after forged prefix')
        kwargs['on_acquire'] = bad_observer
        return original(public, training, forbidden, **kwargs)
    with patch.object(f, 'search', side_effect=forged), pytest.raises(ValueError, match='actual successful paid prefix'):
        e.run(root)
    assert not called
    failure = c.unseal(root/'run-failure.json')
    assert failure['preserve_partial_directory'] and not failure['retry_or_resume_allowed']
    assert (root/'started.json').exists() and not (root/'report.json').exists()
    with pytest.raises(ValueError, match='Fresh prepared run'):
        e.run(root)


def test_cached_initial_snapshot_mismatch_preserves_preparation_failure(fixture):
    case = fixture['cases'][0]
    snapshot = c.unseal(case['cached_snapshot'])
    snapshot['model_state_sha256'] = 'invalid-model-state'
    c.seal(case['cached_snapshot'], snapshot)
    e.seal_manifest(fixture['source'])
    with pytest.raises(ValueError, match='snapshot EXACTLY'):
        e.prepare(fixture['root'])
    assert c.unseal(fixture['root']/'prepare-failure.json')['phase'] == 'prepare'
    assert not (fixture['root']/'prediction-release.json').exists()
    with pytest.raises(ValueError):
        e.run(fixture['root'])


def test_input_or_release_tampering_rejected_without_native_audit(fixture):
    root = fixture['root']
    e.prepare(root)
    identity = fixture['cases'][0]['case_id']
    joint = c.unseal(root/'initial'/identity/'joint.json')
    joint['outputs']['area_delta_lut4']['mean'][0] += 1
    c.seal(root/'initial'/identity/'joint.json', joint)
    with patch.object(e, '_read_outcomes', side_effect=AssertionError('Audit opened on invalid release')), \
         pytest.raises(ValueError, match='all-case prediction release'):
        e.run(root)
    assert (root/'run-failure.json').exists()


def test_source_or_settings_change_invalidates_prepared_protocol(fixture, monkeypatch):
    root = fixture['root']
    e.prepare(root)
    monkeypatch.setitem(f.SETTINGS, 'fantasy_draws', 64)
    with pytest.raises(ValueError, match='Frozen sources, settings'):
        e.authenticate(root)


def test_related_family_or_whole_source_leakage_rejected_before_fit(fixture):
    case = fixture['cases'][0]
    target = c.unseal(case['public'])
    target[0] = public(target[0]['candidate_id'], fixture['rows'][0]['formula'], case['source']+':ctx')
    c.seal(case['public'], target)
    e.seal_manifest(fixture['source'])
    with patch.object(s.SemanticHardwareSurrogate, 'fit', side_effect=AssertionError('Fit on invalid split')), \
         pytest.raises(ValueError, match='Whole-source/family exclusions'):
        e.prepare(fixture['root'])


def test_write_guards_block_sealed_ancestors_inputs_existing_and_replay_overlap(fixture):
    for output in (fixture['source']/'new-run', fixture['source'], fixture['tmp']):
        with pytest.raises(ValueError):
            e.prepare(output)
    e.prepare(fixture['root'])
    with pytest.raises(ValueError):
        e.replay(fixture['root'], fixture['root']/'nested')
    assert not (fixture['source']/'new-run').exists()


def test_host_timer_exclusions_do_not_hide_native_costs_states_or_draw_settings():
    before = dict(inference_seconds=1., acquisition_host_seconds=2.,
        target_measurement_seconds=7., target_outer_operation_seconds=8.,
        recorded_candidate_ledger_seconds=9., posterior_state_sha256='a', fantasy_draws=128)
    host = dict(before, inference_seconds=3., acquisition_host_seconds=4.)
    assert e.stable(before) == e.stable(host)
    for field, changed in [('target_measurement_seconds', 8.), ('target_outer_operation_seconds', 9.),
                           ('recorded_candidate_ledger_seconds', 10.), ('posterior_state_sha256', 'b'),
                           ('fantasy_draws', 64)]:
        assert e.stable(before) != e.stable(dict(before, **{field: changed}))
