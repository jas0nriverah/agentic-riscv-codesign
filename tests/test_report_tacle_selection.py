"""Synthetic report fixtures exercise paid accounting without native jobs or fits."""
import copy
import json

import pytest

from isaforge import codesign as c
from scripts import report_tacle_selection as report

POLICIES = tuple('fixture_policy_'+str(index) for index in range(14))


def fixture(*, failure=None):
    public, outcomes = [], []
    for index in range(12):
        item = {key:0 for key in report.b.PUBLIC_KEYS}
        item.update(candidate_id='fixture-'+str(index), benchmark='tacle-bitcount:fixture-context',
            formula='add(in0,in1)', latency_features=dict(baseline_cycles=51689))
        public.append(item)
        if index == 2 and failure:
            outcomes.append(dict(item, status='failed', measurement_seconds=3.,
                error='synthetic failure retained', failure_class='infrastructure_unknown' if failure == 'unknown' else 'recorded_self_check_failure',
                reference_censored=failure == 'unknown'))
        else:
            cycles = 51689-100*(index+1)
            outcomes.append(dict(item, status='success', measurement_seconds=float(index+1),
                baseline_cycles=51689, candidate_cycles=cycles, speedup=51689/cycles,
                area=1000+10*(index+1), area_delta_lut4=10*(index+1), routed_fmax_min_mhz=60.,
                device_fits=True, correctness_verified=True))
    outer = {row['candidate_id']:row['measurement_seconds']+1 for row in outcomes}
    runs = []
    for policy in POLICIES:
        for cap in report.CAPS:
            for seed in report.SEEDS:
                curve = []
                for budget in report.BUDGETS:
                    attempted = outcomes[:budget]
                    known = sum((row.get('status') == 'success' and not report.b._feasible(row,cap,12)) or
                        (row.get('status') == 'failed' and not row['reference_censored']) for row in attempted)
                    curve.append(dict(budget=budget,attempted_ids=[row['candidate_id'] for row in attempted],
                        best_speedup=max([1.]+[row['speedup'] for row in attempted if report.b._feasible(row,cap,12)]),
                        target_measurement_seconds=sum(row['measurement_seconds'] for row in attempted),
                        target_outer_operation_seconds=sum(outer[row['candidate_id']] for row in attempted),
                        known_infeasible_attempts=known,
                        unknown_attempts=sum(row.get('status') == 'failed' and row['reference_censored'] for row in attempted),
                        inference_seconds=.01*budget))
                runs.append(dict(policy=policy,cap=cap,seed=seed,curve=curve,candidate_outer_operation_seconds=copy.deepcopy(outer)))
    return public, outcomes, runs


def aggregate(case, **kwargs):
    return report.endpoints(*case, policies=POLICIES, **kwargs)


def test_complete_grid_aggregates_real_cycle_gain_and_separate_timers():
    rows = aggregate(fixture())
    assert len(rows) == 126
    point = next(row for row in rows if row['cap'] == 64 and row['budget'] == 3)
    assert point['dependent_seed_count'] == 5
    assert point['mean_verified_cycle_reduction'] == pytest.approx(300/51689)
    assert point['reference_cycle_reduction'] == pytest.approx(600/51689)
    assert point['mean_cycle_reduction_regret'] == pytest.approx(300/51689)
    assert point['mean_target_measurement_seconds'] == 6
    assert point['mean_target_outer_operation_seconds'] == 9
    assert point['mean_inference_seconds'] == .03
    assert 'host-dependent' in point['inference_timer_basis']


@pytest.mark.parametrize('mutation', ['omit_run','duplicate_run','omit_point','outcome_identity','outcome_speedup',
    'unpaid_best','prefix','ledger','outer','outer_mapping','counts'])
def test_tampering_fails_closed(mutation):
    public, outcomes, runs = fixture()
    point = runs[0]['curve'][0]
    if mutation == 'omit_run': runs.pop()
    elif mutation == 'duplicate_run': runs[-1] = copy.deepcopy(runs[0])
    elif mutation == 'omit_point': runs[0]['curve'].pop()
    elif mutation == 'outcome_identity': outcomes[0]['formula'] = 'xor(in0,in1)'
    elif mutation == 'outcome_speedup': outcomes[0]['speedup'] = 2
    elif mutation == 'unpaid_best': point['best_speedup'] = outcomes[2]['speedup']
    elif mutation == 'prefix': point['attempted_ids'] = [outcomes[3]['candidate_id']]
    elif mutation == 'ledger': point['target_measurement_seconds'] = 0
    elif mutation == 'outer': point['target_outer_operation_seconds'] = 0
    elif mutation == 'outer_mapping': runs[-1]['candidate_outer_operation_seconds']['fixture-0'] += 1
    elif mutation == 'counts': point['unknown_attempts'] = 1
    with pytest.raises(ValueError): aggregate((public,outcomes,runs))


def test_unknown_failure_is_charged_censors_reference_and_never_becomes_label():
    case = fixture(failure='unknown')
    with pytest.raises(ValueError,match='censorship'): aggregate(case)
    rows = aggregate(case, reference_censored=True)
    point = next(row for row in rows if row['cap'] == 64 and row['budget'] == 3)
    assert point['mean_unknown_attempts'] == 1 and point['mean_known_infeasible_attempts'] == 0
    assert point['mean_target_measurement_seconds'] == 6
    assert point['mean_best_verified_speedup'] == case[1][1]['speedup']
    assert point['reference_complete'] is False and point['regret_is_lower_bound'] is True
    case[1][2]['speedup'] = 1
    with pytest.raises(ValueError,match='Failed attempt'): aggregate(case,reference_censored=True)


def test_recorded_correctness_failure_is_known_invalid_but_has_no_regression_label():
    case = fixture(failure='known')
    point = next(row for row in aggregate(case) if row['cap'] == 64 and row['budget'] == 3)
    assert point['mean_known_infeasible_attempts'] == 1 and point['mean_unknown_attempts'] == 0
    assert point['reference_complete'] is True
    assert not {'speedup','candidate_cycles','area_delta_lut4'} & set(case[1][2])


def native_record(cycles, area=1000):
    return dict(performance=dict(cycles=cycles),resources=dict(lut4_count=area,flip_flop_count=600,
        carry_count=200,memory_blocks=20,program_data_memory_blocks=16),routes=[
        dict(seed=seed,limiting_internal_fmax_mhz=60.+seed-1) for seed in (1,2,3)])


def audit_fixture(case):
    public, outcomes, _ = case
    names = ['candidate_'+str(index) for index in range(12)]
    success, failed, measurements = [], [], {}
    for name, outcome in zip(names,outcomes):
        if outcome.get('status') == 'success':
            success.append(dict(name=name,candidate_id=outcome['candidate_id']))
            measurements[name] = native_record(outcome['candidate_cycles'],outcome['area'])
        else:
            failed.append(dict(name=name,status='failed',classification=outcome['failure_class'],
                reference_censored=outcome['reference_censored'],error=outcome['error'],
                elapsed_seconds=outcome['measurement_seconds'],correctness_verified=None))
    return dict(public=public,outcomes=outcomes,pool_names=names,successful=success,
        failed_or_interrupted=failed,unattempted=[],native_measurements=measurements,
        charged_candidate_attempts=12,candidate_wall_seconds=78.,candidate_wall_seconds_complete=True,
        baseline_wall_seconds=2.,native_command_count=20,native_command_seconds=40.)


def test_report_retains_twelve_candidates_unknowns_all_policy_budgets_and_scopes(tmp_path):
    case = fixture(failure='unknown')
    output = tmp_path/'report'
    audit = audit_fixture(case)
    result = report.write_report(output,audit=audit,baseline=native_record(51689),
        endpoints=aggregate(case,reference_censored=True),live=dict(fixture=True),
        historical_costs=dict(successful_labels=87,failed_attempts=3,total_candidate_attempts=90,total_candidate_wall_seconds=5000.),
        qualification=dict(recorded_seconds=7))
    assert result['candidates'] == 12 and result['endpoint_summaries'] == 126
    text = (output/'results.md').read_text()
    assert '51,689 cycles' in text and 'infrastructure_unknown' in text
    assert 'host-dependent inference' in text and 'Five seeds are dependent' in text
    assert len((output/'candidates.csv').read_text().splitlines()) == 13
    assert len((output/'endpoints.csv').read_text().splitlines()) == 127
    assert len((output/'primary.csv').read_text().splitlines()) == 43
    assert c.unseal(output/'costs.json')['timer_scopes_overlap'] is True
    assert c.unseal(output/'summary.json')['superiority_established'] is False
    with pytest.raises(ValueError,match='Fresh output'):
        report.write_report(output,audit=audit,baseline=native_record(51689),endpoints=aggregate(case,reference_censored=True),
            live={},historical_costs={},qualification={})
    assert json.dumps(audit['outcomes']) == json.dumps(case[1])


def test_report_rejects_hardware_cheat_and_sealed_destination(tmp_path):
    case = fixture(); audit = audit_fixture(case)
    audit['native_measurements']['candidate_0']['resources']['lut4_count'] += 1
    with pytest.raises(ValueError,match='Native performance/resources'):
        report.write_report(tmp_path/'report',audit=audit,baseline=native_record(51689),endpoints=aggregate(case),
            live={},historical_costs={},qualification={})
    sealed = tmp_path/'sealed';c.seal(sealed/'manifest.json',{})
    with pytest.raises(ValueError,match='sealed evidence'):
        report.write_report(sealed/'new-report',audit=audit,baseline=native_record(51689),endpoints=aggregate(case),
            live={},historical_costs={},qualification={})


def seal_manifest(folder):
    c.seal(folder/'manifest.json',{path.relative_to(folder).as_posix():c.sha(path)
        for path in sorted(folder.rglob('*')) if path.is_file() and
        path.relative_to(folder).as_posix() not in ('manifest.json','manifest.json.sha256')})


def corpus_fixture(tmp_path,monkeypatch,*,failure='unknown'):
    monkeypatch.setattr(report,'ROOT',tmp_path)
    previous, campaign, prereg = tmp_path/'previous', tmp_path/'campaign', tmp_path/'prereg'
    old_rows = [dict(candidate_id='old-'+str(i),workload_group='old-source-'+str(i%11),
        exact_preserved_payload=dict(index=i,unchanged=True)) for i in range(87)]
    old_failed = [dict(candidate_id='old-failed-'+str(i),workload_group='old-source-'+str(i),
        correctness_verified=None,reference_censored=True,measurement_seconds=2.) for i in range(3)]
    old = dict(successful_labels=87,total_candidate_attempts=90,rows=old_rows,failed_attempts=old_failed,
        independent_workload_groups=['old-source-'+str(i) for i in range(11)],
        contexts={'old-context-'+str(i):dict(unchanged=True) for i in range(12)},
        total_candidate_attempt_wall_seconds=100.5,clock_accounting=dict(historical_clock_failure='preserved exactly'),
        qualification_costs=dict(old_qualification='preserved'))
    c.seal(previous/'corpus.json',old);seal_manifest(previous)
    case = fixture(failure=failure);audit = audit_fixture(case)
    audit.update(attempt_collection_complete=True,context_id='fixture-context')
    c.seal(campaign/'audit.json',audit)
    outer = case[2][0]['candidate_outer_operation_seconds']
    c.seal(campaign/'outer-times.json',outer)
    live = dict(policy='fixture_semantic_count',cap=64,seed=0,budget=3)
    c.seal(campaign/'collection/live.json',dict(live=live,attempted_ids=[row['candidate_id'] for row in case[0][:3]]))
    c.seal(campaign/'provenance.json',dict(preregistration='prereg',historical_costs=dict(
        successful_labels=87,failed_attempts=3,total_candidate_attempts=90,total_candidate_wall_seconds=100.5,
        source_corpus_sha256=c.sha(previous/'corpus.json')),qualification=dict(seconds=9),
        collection_paired_durations=dict(monotonic_elapsed_seconds=100.,utc_elapsed_seconds=100.1),
        live_native_attempts=3,live=live))
    seal_manifest(campaign)
    c.seal(prereg/'targets/tacle-bitcount/baseline/public.json',case[0])
    c.seal(prereg/'targets/tacle-bitcount/baseline/context.json',dict(workload_group='tacle-bitcount',
        context_id='fixture-context',full_recorded_context=dict(memory=8192,clock_mhz=12)))
    seal_manifest(prereg)
    return previous,campaign,prereg,old


def test_export_preserves_every_old_row_failure_full_context_and_separate_cost(tmp_path,monkeypatch):
    previous,campaign,prereg,old = corpus_fixture(tmp_path,monkeypatch)
    value = report.export_corpus(previous,campaign,tmp_path/'new-corpus')
    assert value['rows'][:87] == old['rows'] and value['failed_attempts'][:3] == old['failed_attempts']
    assert json.dumps(value['rows'][:87]) == json.dumps(old['rows'])
    assert value['successful_labels'] == 98 and len(value['failed_attempts']) == 4
    assert value['total_candidate_attempts'] == 102
    assert len(value['independent_workload_groups']) == 12 and len(value['contexts']) == 13
    assert value['total_candidate_attempt_wall_seconds'] == 178.5
    assert value['new_candidate_outer_operation_seconds'] == 90
    assert value['new_live_native_attempts'] == 3 and value['new_oracle_reference_attempts'] == 9
    assert value['historical_clock_accounting'] == old['clock_accounting']
    assert value['contexts']['tacle-bitcount:fixture-context']['full_recorded_context'] == dict(memory=8192,clock_mhz=12)
    failed = value['failed_attempts'][-1]
    assert failed['correctness_verified'] is None and failed['reference_censored'] is True
    assert not {'speedup','candidate_cycles','area_delta_lut4','routed_fmax_min_mhz'} & set(failed)
    assert value['new_model_fits'] == value['new_native_jobs'] == 0


@pytest.mark.parametrize('mutation',['history_cost','ledger_cost','missing_outcome','invented_failed_label','live_future_id'])
def test_resealed_export_tampering_is_rejected(tmp_path,monkeypatch,mutation):
    previous,campaign,prereg,old = corpus_fixture(tmp_path,monkeypatch)
    if mutation == 'history_cost':
        value=c.unseal(campaign/'provenance.json');value['historical_costs']['total_candidate_wall_seconds']+=1
        c.seal(campaign/'provenance.json',value)
    elif mutation == 'live_future_id':
        value=c.unseal(campaign/'collection/live.json');value['attempted_ids'][-1]='outside-pool'
        c.seal(campaign/'collection/live.json',value)
    else:
        value=c.unseal(campaign/'audit.json')
        if mutation == 'ledger_cost':value['candidate_wall_seconds']+=1
        elif mutation == 'missing_outcome':value['outcomes'].pop()
        elif mutation == 'invented_failed_label':value['outcomes'][2]['speedup']=2.
        c.seal(campaign/'audit.json',value)
    seal_manifest(campaign)
    with pytest.raises(ValueError):report.export_corpus(previous,campaign,tmp_path/'export')
