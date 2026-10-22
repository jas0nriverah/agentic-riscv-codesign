"""Read-only presenters: receipt boundaries, resources and unchanged old history."""
import copy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from isaforge import codesign as c
from scripts import report_live_gp_campaign as report
from scripts import export_live_gp_corpus as corpus


def seal_manifest(folder):
    c.seal(folder/'manifest.json', {path.relative_to(folder).as_posix():c.sha(path)
        for path in sorted(folder.rglob('*')) if path.is_file() and
        path.relative_to(folder).as_posix() not in ('manifest.json','manifest.json.sha256')})


def fake_case(tmp_path, *, failed=False):
    """Historical schema only: fabricated IDs/receipts are explicitly test fixtures."""
    old = c.unseal(corpus.PREVIOUS/'corpus.json')
    group, context = 'beebs-presenter-fixture', 'fixture-context'
    public, outcomes = [], []
    for index in range(6):
        row = copy.deepcopy(old['rows'][0])
        row.update(candidate_id='presenter-fixture-'+str(index), benchmark=group+':'+context,
                   workload_group=group, measurement_seconds=1.0, status='success')
        item = {key:copy.deepcopy(row[key]) for key in report.b.PUBLIC_KEYS}
        public.append(item)
        if failed and index == 5:
            row = dict(item, status='failed', measurement_seconds=1.0,
                failure_class='infrastructure_unknown', reference_censored=True,
                error='synthetic receipt fixture infrastructure failure')
        outcomes.append(row)
    campaign, prereg = tmp_path/'campaign', tmp_path/'prereg'
    campaign.mkdir();prereg.mkdir()
    c.seal(campaign/'release.json', dict(fixture=True))
    seal_manifest(campaign);seal_manifest(prereg)
    return dict(campaign=campaign, prereg=prereg,group=group,public=public,outcomes=outcomes,
        target=dict(original_root='/fixture/native'),
        audit=dict(context_id=context,pool_names=['candidate_'+str(i) for i in range(6)],
            charged_candidate_attempts=6,candidate_wall_seconds=6.0,native_command_count=6,
            native_command_seconds=3.0,baseline_wall_seconds=2.0,baseline_record_seconds=1.0),
        outer_times={row['candidate_id']:2.0 for row in outcomes},
        context=dict(context_id=context,workload_group=group,full_context_fixture=dict(partition=[6400,6528])),
        cohort=dict(live=report.live_runtime.LIVE,python_executable='/fixture/python',
            qualification=dict(setup_seconds=7.0),historical_costs=dict(successful_labels=81,
                failed_attempts=3,total_candidate_attempts=84,
                source_corpus_sha256=c.sha(corpus.PREVIOUS/'corpus.json'),
                total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'],
                clock_accounting=old['clock_accounting'])))


def endpoint(seconds):
    mono=int(seconds*1e9);utc=1792627200000000000+mono
    return dict(utc_ns=utc,utc_iso=datetime.fromtimestamp(utc/1e9,timezone.utc).isoformat(),
                monotonic_before_ns=mono,monotonic_after_ns=mono+10)


@pytest.fixture
def receipts(tmp_path):
    case=fake_case(tmp_path);folder=case['campaign']/'collection';folder.mkdir()
    paid=[row['candidate_id'] for row in case['public']]
    search=dict(events=[dict(fixture_query=index) for index in range(3)],
        curve=[dict(budget=index+1,attempted_ids=paid[:index+1],best_speedup=1.,
                    target_measurement_seconds=float(index+1)) for index in range(3)])
    trace=dict(live=report.live_runtime.LIVE,remaining_outcomes_exist=False,attempted_ids=paid[:3],
               search=search,finish=endpoint(28))
    c.seal(folder/'live.json',trace)
    whole=dict(status='complete',live=report.live_runtime.LIVE,paid_ids=paid,observer_pid=123,
        prereg_manifest_sha256=c.sha(case['prereg']/'manifest.json'),
        release_sha256=c.sha(case['campaign']/'release.json'),live_trace_sha256=c.sha(folder/'live.json'),
        start=endpoint(0),end=endpoint(70))
    whole['durations']=report.observed._durations(whole['start'],whole['end'])
    c.seal(folder/'collection.json',whole)
    for index,identity in enumerate(paid):
        query=folder/'queries'/f'{index:02d}';command=query/'command';command.mkdir(parents=True)
        decision=dict(index=index,mode='adaptive' if index<3 else 'oracle-reference',candidate_id=identity,
            native_name=case['audit']['pool_names'][index],paid_ids_before=paid[:index],
            prereg_manifest_sha256=c.sha(case['prereg']/'manifest.json'),release_sha256=c.sha(case['campaign']/'release.json'),
            completed_live_trace_sha256=None if index<3 else c.sha(folder/'live.json'),chosen_before_dispatch=True)
        c.seal(query/'decision.json',decision)
        argv=['/fixture/python','-m','isaforge.integer_workload','measure','--root','/fixture/native',
              '--candidate',decision['native_name']]
        immutable=dict(schema=report.observed.SCHEMA,argv_sha256=hashlib.sha256(report.observed._json(argv)).hexdigest(),
            metadata=decision,metadata_sha256=hashlib.sha256(report.observed._json(decision)).hexdigest(),
            observer_pid=123,stdout_file='stdout.txt',stderr_file='stderr.txt',start=endpoint(10*index+1))
        c.seal(command/'started.json',dict(immutable,status='started',end=None,returncode=None,child_pid=None))
        end=endpoint(10*index+6)
        for stream in ('stdout','stderr'):(command/(stream+'.txt')).write_text('fixture only\n')
        record=dict(immutable,status='success',returncode=0,end=end,
            durations=report.observed._durations(immutable['start'],end),
            stdout_sha256=c.sha(command/'stdout.txt'),stderr_sha256=c.sha(command/'stderr.txt'))
        c.seal(command/'record.json',record)
        c.seal(query/'outcome.json',case['outcomes'][index])
        partial=dict(outcomes=case['outcomes'][:index+1],charged_candidate_attempts=index+1,
                     candidate_wall_seconds_complete=True)
        c.seal(query/'partial-audit.json',partial)
        c.seal(query/'completed.json',dict(partial_audit_digest=c.digest(partial),candidate_id=identity,
            audited_paid_ids=sorted(paid[:index+1]),outcome_sha256=c.sha(query/'outcome.json')))
    seal_manifest(folder)
    case['report']=dict(runs=[dict(policy='hybrid_gp_adapt',cap=64,seed=0,**copy.deepcopy(search))])
    case['provenance']=dict(live_best=copy.deepcopy(search['curve'][-1]),collection_paired_durations=whole['durations'])
    return case


def test_paired_receipts_keep_live_and_oracle_separate_without_clock_claim(receipts):
    clock=report.paired_collection(receipts)
    assert len(clock['queries'])==6
    assert [row['mode'] for row in clock['queries']]==['adaptive']*3+['oracle-reference']*3
    assert clock['live_prefix_paired_durations']['monotonic_elapsed_seconds']==28
    assert clock['paired_collection_durations']['monotonic_elapsed_seconds']==70
    assert clock['actual_calendar_wall_seconds'] is None
    assert clock['uninterrupted_calendar_wall_time_established'] is False


def test_future_outcome_cannot_leak_into_paid_prefix_even_when_resealed(receipts):
    query=receipts['campaign']/'collection/queries/00'
    partial=c.unseal(query/'partial-audit.json');partial['outcomes'].append(receipts['outcomes'][5])
    c.seal(query/'partial-audit.json',partial)
    completed=c.unseal(query/'completed.json');completed['partial_audit_digest']=c.digest(partial)
    c.seal(query/'completed.json',completed);seal_manifest(receipts['campaign']/'collection')
    with pytest.raises(ValueError,match='Only charged terminal outcomes'):
        report.paired_collection(receipts)


def test_oracle_dispatch_before_live_completion_is_rejected(receipts):
    folder=receipts['campaign']/'collection';trace=c.unseal(folder/'live.json')
    trace['finish']=endpoint(35);c.seal(folder/'live.json',trace)
    whole=c.unseal(folder/'collection.json');whole['live_trace_sha256']=c.sha(folder/'live.json')
    c.seal(folder/'collection.json',whole)
    # Reseal all identity/hash links so the tested defect is the observed boundary.
    for index in range(3,6):
        query=folder/'queries'/f'{index:02d}';decision=c.unseal(query/'decision.json')
        decision['completed_live_trace_sha256']=c.sha(folder/'live.json');c.seal(query/'decision.json',decision)
        for name in ('started','record'):
            path=query/'command'/(name+'.json');record=c.unseal(path);record['metadata']=decision
            record['metadata_sha256']=hashlib.sha256(report.observed._json(decision)).hexdigest();c.seal(path,record)
    seal_manifest(folder)
    with pytest.raises(ValueError,match='Oracle outcome existed before'):
        report.paired_collection(receipts)


def test_receipt_output_tampering_is_rejected_by_complete_manifest(receipts):
    (receipts['campaign']/'collection/queries/00/command/stdout.txt').write_text('changed')
    with pytest.raises(ValueError,match='checksum'):
        report.paired_collection(receipts)


def test_packed_hardware_keeps_all_routes_bram_and_minimum():
    native=report.ROOT/'results/2026-10-21-jfdctint-campaign/native'
    if not native.exists():pytest.skip('consumed DCT packed fixture unavailable')
    record=report.packed_measurements(native,['baseline'])['baseline']
    values=report.resources(record)
    assert values['total_lut4']==1653 and values['flip_flops']==655 and values['carry_cells']==295
    assert values['bram_blocks']==20 and values['program_data_memory_blocks']==16
    assert values['route_seeds']==[1,2,3] and values['route_seed_count']==3
    assert values['min_fmax_mhz']==min(values['route_fmax_mhz'])
    duplicate=copy.deepcopy(record);duplicate['routes'][0]['seed']=2
    with pytest.raises(ValueError,match='Three unique'):report.resources(duplicate)


def test_history_cost_is_shared_once_and_clock_scopes_are_not_added(receipts,tmp_path):
    receipts['clock']=report.paired_collection(receipts)
    selection=tmp_path/'selection';receipts['selection']=selection
    c.seal(selection/'feasibility-costs.json',dict(fixture_seconds=8))
    c.seal(selection/'controls11/utility-inference-costs.json',dict(fixture_seconds=9))
    c.seal(selection/'controls11/model/predictions.json',[dict(seed=0,inference_seconds=10)])
    value=report.costs(receipts)
    assert value['total_unique_candidate_attempts']==90
    assert value['history_plus_new_recorded_attempt_seconds']==4853.804292626148+6
    assert value['live_ledger_monotonic_seconds']==value['oracle_remainder_ledger_monotonic_seconds']==3
    assert value['candidate_cli_monotonic_seconds']==12
    assert value['candidate_subprocess_monotonic_seconds']==30
    assert value['paired_collection_durations']['monotonic_elapsed_seconds']==70
    assert value['timer_scopes_overlap'] is True and value['actual_calendar_wall_seconds'] is None


def test_export_keeps_all_old_rows_unknown_failure_and_full_context(tmp_path,monkeypatch):
    case=fake_case(tmp_path,failed=True);case['clock']=dict(fixture='paired-only',actual_calendar_wall_seconds=None)
    monkeypatch.setattr(corpus,'load',lambda *_:case)
    old=c.unseal(corpus.PREVIOUS/'corpus.json')
    value=corpus.export(corpus.PREVIOUS,case['campaign'],case['prereg'],tmp_path/'export')
    assert value['successful_labels']==86 and len(value['failed_attempts'])==4
    assert value['total_candidate_attempts']==90
    assert len(value['independent_workload_groups'])==11 and len(value['contexts'])==12
    assert json.dumps(value['rows'][:81])==json.dumps(old['rows'])
    assert json.dumps(value['failed_attempts'][:3])==json.dumps(old['failed_attempts'])
    assert value['historical_clock_accounting']==old['clock_accounting']
    assert value['current_paired_clock_accounting']==case['clock']
    assert value['total_candidate_attempt_wall_seconds']==old['total_candidate_attempt_wall_seconds']+6
    assert value['contexts'][case['public'][0]['benchmark']]==case['context']
    failed=value['failed_attempts'][-1]
    assert failed['correctness_verified'] is None and failed['reference_censored'] is True
    assert not {'speedup','candidate_cycles','area_delta_lut4'}&set(failed)
    assert all('candidate_family' in row for row in value['rows'][-5:])
    with pytest.raises(ValueError,match='Fresh corpus'):
        corpus.export(corpus.PREVIOUS,case['campaign'],case['prereg'],tmp_path/'export')


def test_completed_live_campaign_presents_all_fixed_controls_and_exports_exact_history(tmp_path):
    if not (report.CAMPAIGN/'manifest.json').exists():pytest.skip('live campaign not yet completed')
    result=report.build(report.CAMPAIGN,report.PREREG,tmp_path/'report')
    assert result==dict(candidates=6,policies=12,endpoint_summaries=108,live_queries=3,new_model_fits=0,new_native_jobs=0)
    summary=c.unseal(tmp_path/'report/summary.json')
    assert summary['public_max_saved_cycles']==11 and summary['superiority_established'] is False
    assert {row['policy'] for row in summary['primary']}==set(report.POLICY_LABELS)
    old=c.unseal(corpus.PREVIOUS/'corpus.json')
    value=corpus.export(corpus.PREVIOUS,report.CAMPAIGN,report.PREREG,tmp_path/'corpus')
    assert value['successful_labels']==87 and len(value['failed_attempts'])==3
    assert value['total_candidate_attempts']==90
    assert value['rows'][:81]==old['rows'] and value['failed_attempts']==old['failed_attempts']
    assert value['historical_clock_accounting']==old['clock_accounting']
