"""Synthetic ARD experiment integration; no real cohorts, policies or native jobs."""
import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from isaforge import ard_hardware as a, codesign as c, finite_selection as f
from scripts import evaluate_ard_selection as w, evaluate_finite_selection as e
from test_finite_selection_experiment import fixture as finite_fixture


@pytest.fixture
def fixture(finite_fixture, monkeypatch):
    # This is a completed *synthetic* finite-control package. The real results
    # directory is never used by this test fixture or by its model initializers.
    e.prepare(finite_fixture['root'])
    e.run(finite_fixture['root'])
    monkeypatch.setattr(w, 'BASE', finite_fixture['root'])
    monkeypatch.setattr(w, 'CAPS', e.CAPS)
    monkeypatch.setattr(w, 'SEEDS', e.SEEDS)
    monkeypatch.setattr(w, 'BUDGETS', e.BUDGETS)
    contract = finite_fixture['tmp']/'pre-fit-contract.md'
    contract.write_text('Synthetic contract: fixed train-only three-start area initializer.\n')
    monkeypatch.setattr(w, 'CONTRACT', contract)
    return dict(**finite_fixture, base=finite_fixture['root'], root_ard=finite_fixture['tmp']/'ard-run')


def test_prepare_seals_all_models_and_tables_before_outcomes_without_g723_reads(fixture):
    original_unseal, original_initialize = c.unseal, a.initialize
    calls = []
    def unseal(path):
        path = Path(path)
        assert 'g723' not in str(path).lower(), 'Experiment read a G723 artifact'
        assert path.name not in ('audit.json', 'outer.json'), 'Preparation parsed native target outcomes'
        assert path.resolve() not in {(w.BASE/'report.json').resolve(), (w.BASE/'archived-controls.json').resolve()}, \
            'Preparation/authentication parsed completed target endpoint values'
        return original_unseal(path)
    def initialize(rows, public):
        assert rows == fixture['rows']
        assert not {r['candidate_id'] for r in rows} & {r['candidate_id'] for r in public}
        calls.append([r['candidate_id'] for r in public])
        return original_initialize(rows, public)
    with patch.object(c, 'unseal', side_effect=unseal), patch.object(a, 'initialize', side_effect=initialize), \
         patch.object(f, 'search', side_effect=AssertionError('No search during preparation')):
        protocol = w.prepare(fixture['root_ard'])
        w.authenticate(fixture['root_ard'])
    root = fixture['root_ard']
    assert len(calls) == 10
    assert protocol['model_identity'] == w.POLICY
    assert protocol['acquisition_policy'] == f.MYOPIC
    assert protocol['new_model_count'] == protocol['new_policy_count'] == 1
    assert protocol['archived_control_rows'] == 600
    assert protocol['expected_new_trajectories'] == 30
    assert protocol['expected_new_curve_points'] == protocol['expected_new_endpoint_summaries'] == 60
    assert len(protocol['archived_control_policies']) == 17
    assert protocol['pre_fit_contract_sha256'] == c.sha(w.CONTRACT)
    assert protocol['source_bindings'] == w.source_bindings()
    assert protocol['historical_accounting']['charged_attempts'] == 3  # synthetic fixture ledger
    assert 'not all project costs' in protocol['historical_accounting']['scope']
    release = c.unseal(root/'prediction-release.json')
    assert not release['native_outcomes_parsed']
    assert release['semantic_surrogate_fits'] == 10
    assert release['semantic_scalar_gp_fits'] == release['ard_scalar_gp_fit_attempts'] == 30
    assert release['total_scalar_gp_fit_attempts'] == 60
    assert len(release['initial_files']) == 60
    assert len(release['input_files']) == 80
    for case in fixture['cases']:
        snapshot = c.unseal(root/'initial'/case['case_id']/'snapshot.json')
        initial = snapshot['initial_snapshot']
        assert initial['schema'] == a.SCHEMA
        assert len(initial['optimizer_attempts']) == 3
        assert initial['original_semantic_snapshot'] == c.unseal(case['cached_snapshot'])
        assert not snapshot['paid_ids']
    w.authenticate(root)
    e.manifest(root)


def test_run_retains_exact17_controls_separate_horizons_model_identity_and_fit_costs(fixture):
    root = fixture['root_ard']
    w.prepare(root)
    initial_controls = w._controls()
    before_source = w.source_bindings()
    original_initialize, original_outcomes, original_controls = a.initialize, e._read_outcomes, w._controls
    calls = []
    def initialize(rows, public):
        assert rows == fixture['rows']
        calls.append([r['candidate_id'] for r in public])
        return original_initialize(rows, public)
    def outcomes(case, public):
        assert len(calls) == 10, 'Native audit parsed before all initial rebuilds'
        assert c.unseal(root/'prediction-release.json')['case_ids'] == [r['case_id'] for r in fixture['cases']]
        return original_outcomes(case, public)
    def controls():
        assert len(calls) == 10, 'Completed control endpoints parsed before all initial rebuilds'
        return original_controls()
    with patch.object(a, 'initialize', side_effect=initialize), patch.object(e, '_read_outcomes', side_effect=outcomes), \
         patch.object(w, '_controls', side_effect=controls):
        report = w.run(root)
    assert len(calls) == 10
    assert w.source_bindings() == before_source
    assert report['model_identity'] == w.POLICY and report['acquisition_policy'] == f.MYOPIC
    assert report['case_count'] == 10 and report['distinct_consumed_target_sources'] == 6
    assert report['new_trajectories'] == 30 and report['new_curve_points'] == 60
    assert len(report['endpoints']) == 60
    assert report['archived_control_summary_rows'] == 600
    assert c.unseal(root/'archived-controls.json') == initial_controls
    assert report['conditional_updates'] == report['observer_validation_conditional_updates'] == 60
    assert report['calibrated_benefit_assumption_violations'] == 0
    assert report['costs']['estimator_fits_inside_search'] == 0
    for phase in ('prepare_totals', 'run_initialization_totals'):
        values = report['costs'][phase]
        assert values['semantic_surrogate_fits'] == values['unused_original_semantic_area_scalar_fits'] == 10
        assert values['semantic_scalar_gp_fits'] == values['ard_scalar_gp_fit_attempts'] == values['optimizer_attempts'] == 30
        assert values['total_scalar_gp_fit_attempts'] == 60
        assert values['ard_scalar_gp_fits_completed'] == 30
        assert values['optimizer_objective_calls'] >= values['optimizer_gradient_calls'] > 0
    assert report['costs']['counterfactual_target_search']['charged_replayed_attempts'] == 60
    for entry in report['runs']:
        assert entry['policy'] == w.POLICY
        assert entry['acquisition_policy'] == f.MYOPIC
        assert w.POLICY in entry['path']
        raw = c.unseal(root/entry['path'])
        assert raw['policy'] == f.MYOPIC
        assert len(raw['curve']) == entry['planned_budget']
        assert raw['initial_model_fits_in_search'] == 0
        for proof in raw['acquisition_proofs']:
            assert proof['event']['policy'] == f.MYOPIC
            assert proof['posterior_snapshot']['initial_snapshot']['schema'] == a.SCHEMA
            assert all(v['expected_adaptive_second_gain'] == 0 for v in proof['event']['action_values'])
    terminal_native = sum(c.unseal(root/r['path'])['curve'][-1]['target_measurement_seconds'] for r in report['runs'])
    assert report['costs']['counterfactual_target_search']['target_measurement_seconds'] == terminal_native
    assert {r['comparator'] for r in report['comparisons']} == {
        'latency_cost_heuristic', f.MYOPIC, 'strongest_archived_control'}
    assert all(r['retrospective_control_envelope'] == (r['comparator'] == 'strongest_archived_control')
               for r in report['comparisons'])
    assert all(r['source_count'] == 3 for r in report['primary_source_macros'])
    assert {r['cohort'] for r in report['primary_source_macros']} == {'old', 'expanded'}
    for row in report['endpoints']:
        assert row['policy'] == w.POLICY
        assert row['planned_budget'] == (3 if row['endpoint_kind'] == 'B3-prefix' else row['budget'])
    assert not report['superiority_established'] and not report['model_promoted']
    assert not report['calibration_established'] and report['new_native_jobs'] == 0
    assert (root/'README.md').exists() and (root/'comparisons.csv').exists()
    e.manifest(root)
    with pytest.raises(ValueError, match='Fresh prepared ARD run'):
        w.run(root)


def test_replay_exact_optimizer_proofs_scientific_costs_and_raw_timer_arrays(fixture):
    root = fixture['root_ard']
    w.prepare(root)
    original = w.run(root)
    output = fixture['tmp']/'ard-replay'
    replayed = w.replay(root, output)
    assert w.stable(original) == w.stable(replayed)
    assert c.unseal(root/'archived-controls.json') == c.unseal(output/'archived-controls.json')
    assert e.inventory(w._method_root(root)/'acquisitions') == e.inventory(w._method_root(output)/'acquisitions')
    receipt = c.unseal(output/'replay-verification.json')
    assert receipt['all_seventeen_controls_exact']
    assert receipt['compared_trajectories'] == 30 and receipt['compared_curve_points'] == 60
    assert receipt['raw_reference_runtime'] == c.unseal(root/'runtime-costs.json')
    assert receipt['raw_replayed_runtime'] == c.unseal(output/'runtime-costs.json')
    assert receipt['raw_reference_runtime']['prepare_records'][0]['initialize_host_seconds'] != \
        receipt['raw_replayed_runtime']['prepare_records'][0]['initialize_host_seconds']
    e.manifest(output)


def test_pre_fit_contract_and_single_initializer_settings_are_bound(fixture, monkeypatch):
    root = fixture['root_ard']
    w.prepare(root)
    w.CONTRACT.write_text('Changed pre-fit contract.\n')
    with pytest.raises(ValueError, match='Frozen ARD source/settings/cohort/control'):
        w.authenticate(root)
    w.CONTRACT.write_text('Synthetic contract: fixed train-only three-start area initializer.\n')
    monkeypatch.setitem(a.SETTINGS, 'selection', 'select using unpaid target benefit')
    with pytest.raises(ValueError, match='Frozen ARD source/settings/cohort/control'):
        w.authenticate(root)


def test_completed_control_values_are_validated_only_in_run_after_initialization(fixture):
    path = fixture['base']/'archived-controls.json'
    controls = c.unseal(path)
    controls[0]['endpoints'][0]['mean_verified_cycle_reduction'] += .5
    c.seal(path, controls)
    e.seal_manifest(fixture['base'])
    root = fixture['root_ard']
    # Preparation authenticates bytes, but deliberately does not parse outcomes.
    w.prepare(root)
    with patch.object(e, '_run_one', side_effect=AssertionError('Search began before archived control validation')), \
         pytest.raises(ValueError, match='numeric endpoint must remain EXACT'):
        w.run(root)
    assert len(list((root/'run-initialization-cost-records').glob('*.json'))) == 10
    assert (root/'run-failure.json').exists() and not (root/'report.json').exists()


def test_all_start_failures_preserve_initialization_records_and_cannot_resume(fixture):
    costs = dict(semantic_surrogate_fits=1, semantic_scalar_gp_fits=3,
        unused_original_semantic_area_scalar_fits=1, ard_scalar_gp_fit_attempts=3,
        ard_scalar_gp_fits_completed=0, total_scalar_gp_fit_attempts=6,
        initialize_host_seconds=.1, ard_start_fit_host_seconds=[.01, .02, .03])
    attempts = [dict(start_index=i, eligible=False, fit_exception='synthetic failure') for i in range(3)]
    error = a.ARDInitializationError(dict(optimizer_attempts=attempts), costs)
    root = fixture['root_ard']
    with patch.object(a, 'initialize', side_effect=error), pytest.raises(a.ARDInitializationError):
        w.prepare(root)
    failure = c.unseal(root/'prepare-failure.json')
    assert failure['optimizer_attempts'] == attempts
    assert failure['initialization_costs'] == costs
    assert failure['preserve_partial_directory'] and not failure['retry_or_resume_allowed']
    assert not (root/'prediction-release.json').exists()
    with pytest.raises(ValueError):
        w.prepare(root)
    with pytest.raises(ValueError):
        w.run(root)


def test_joint_state_or_optimizer_record_tampering_rejected_before_outcomes(fixture):
    root = fixture['root_ard']
    w.prepare(root)
    first = fixture['cases'][0]['case_id']
    path = root/'initial'/first/'snapshot.json'
    snapshot = c.unseal(path)
    snapshot['initial_snapshot']['selected_start_index'] = 999
    c.seal(path, snapshot)
    with patch.object(e, '_read_outcomes', side_effect=AssertionError('Native outcome parsed after tampering')), \
         pytest.raises(ValueError, match='all-case ARD prediction release'):
        w.run(root)
    assert c.unseal(root/'run-failure.json')['preserve_partial_directory']


def test_forged_prefix_rejected_before_release_and_failure_retained(fixture):
    root = fixture['root_ard']
    w.prepare(root)
    original_search = f.search
    def search(public, training, provider, **kwargs):
        observer = kwargs['on_acquire']
        def forged(proof):
            proof['successful_paid_ids'] = ['unpaid-cross-case-target']
            observer(proof)
        kwargs['on_acquire'] = forged
        return original_search(public, training, lambda _: pytest.fail('Paid label released after forged proof'), **kwargs)
    with patch.object(f, 'search', side_effect=search), pytest.raises(ValueError, match='actual successful paid prefix'):
        w.run(root)
    assert (root/'started.json').exists() and (root/'run-failure.json').exists()
    assert not (root/'report.json').exists()


def test_strongest_control_is_same_case_cap_horizon_retrospective_envelope():
    common = dict(case_id='c', source='s', cohort='old', policy=w.POLICY,
                  cap=64, budget=1, planned_budget=1, endpoint_kind='horizon-aware-terminal',
                  mean_verified_cycle_reduction=.2)
    fourteen = [dict(policy=p, cap=64, budget=1, mean_verified_cycle_reduction=.1)
                for p in e.OLD_POLICIES]
    finite = [dict(common, policy=p, mean_verified_cycle_reduction=.15) for p in f.POLICIES]
    finite[1]['mean_verified_cycle_reduction'] = .3
    misleading_other_horizon = dict(common, policy=f.MYOPIC, planned_budget=3,
                                    endpoint_kind='B3-prefix', mean_verified_cycle_reduction=.99)
    comparisons = w._comparisons([common], dict(original_fourteen=[dict(case_id='c', endpoints=fourteen)],
        fixed_joint_three=finite+[misleading_other_horizon]))
    strongest = next(r for r in comparisons if r['comparator'] == 'strongest_archived_control')
    assert strongest['comparator_cycle_reduction'] == .3
    assert strongest['comparator_policy'] == f.LOOKAHEAD
    assert strongest['result'] == 'loss' and strongest['retrospective_control_envelope']


def test_guards_reject_writes_inside_any_original_or_completed_sealed_root(fixture):
    for path in (fixture['source']/'new', fixture['base']/'new', fixture['tmp']):
        with pytest.raises(ValueError):
            w.prepare(path)
    w.prepare(fixture['root_ard'])
    with pytest.raises(ValueError):
        w.replay(fixture['root_ard'], fixture['root_ard']/'nested')


def test_host_exclusions_never_remove_optimizer_status_fits_or_native_costs():
    before = dict(ard_start_fit_host_seconds=[1., 2., 3.], initialize_host_seconds=7.,
        ard_scalar_gp_fit_attempts=3, optimizer_objective_calls=15, selected_start_index=1,
        optimizer_success=False, negative_log_marginal_likelihood=2., target_measurement_seconds=9.,
        recorded_candidate_ledger_seconds=10., posterior_state_sha256='a')
    after = dict(before, ard_start_fit_host_seconds=[2., 3., 4.], initialize_host_seconds=9.)
    assert w.stable(before) == w.stable(after)
    for key in ('ard_scalar_gp_fit_attempts', 'optimizer_objective_calls', 'selected_start_index',
                'optimizer_success', 'negative_log_marginal_likelihood', 'target_measurement_seconds',
                'recorded_candidate_ledger_seconds', 'posterior_state_sha256'):
        changed = copy.deepcopy(before)
        changed[key] = 'different'
        assert w.stable(before) != w.stable(changed)
