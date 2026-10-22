"""Present the bounded live GP measurement and all twelve fixed replay controls.

Read-only authentication and arithmetic only: no model fits/predictions, native
jobs, new policy choices, clock corrections or changes to sealed inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c, observed_command as observed
from isaforge import factorized_selection_experiment as e
from scripts import live_gp_campaign as live_runtime
from scripts.export_guarded_corpus import _csv
from scripts.report_budget_campaign import table
from scripts.report_guarded_selection import candidate_rows
from scripts.report_blind_campaign import endpoints_for_source, POLICY_LABELS, packed_measurements
from scripts.reproduce_guarded_sha256 import _manifest, _hashes, _inventory

CAMPAIGN = ROOT/'results/2026-10-22-live-gp-campaign'
PREREG = ROOT/'results/2026-10-22-live-gp-preregistration'
OUTPUT = ROOT/'results/2026-10-22-live-gp-report'
SOURCE = 'scripts/report_live_gp_campaign.py'
FINAL_REPORTS = {name+suffix for name in ('report.json','controls11/report.json','controls11/model/report.json')
                 for suffix in ('','.sha256')}


def paired_collection(case):
    """Validate recorded receipt identities, paid-prefix visibility and clock math."""
    campaign, cohort = case['campaign'], case['cohort']
    folder = campaign/'collection'
    _manifest(folder)
    whole, trace = c.unseal(folder/'collection.json'), c.unseal(folder/'live.json')
    labels = {row['candidate_id']: row for row in case['outcomes']}
    names = dict(zip((row['candidate_id'] for row in case['public']),case['audit']['pool_names']))
    config = live_runtime.LIVE
    c.require(whole['status'] == 'complete' and whole['live'] == trace['live'] == config == cohort['live'] and
              trace['remaining_outcomes_exist'] is False and
              whole['prereg_manifest_sha256'] == c.sha(case['prereg']/'manifest.json') and
              whole['release_sha256'] == c.sha(campaign/'release.json') and
              whole['live_trace_sha256'] == c.sha(folder/'live.json') and
              whole['durations'] == observed._durations(whole['start'],whole['end']) and
              whole['durations'] == case['provenance']['collection_paired_durations'],
              'Complete source-bound paired live collection required')
    paid, first = whole['paid_ids'], trace['attempted_ids']
    c.require(len(first) == config['budget'] == 3 and len(paid) == len(set(paid)) == len(labels) == 6 and
              paid[:3] == first and set(paid) == set(labels) and
              paid[3:] == [row['candidate_id'] for row in case['public'] if row['candidate_id'] not in first],
              'Three live queries must precede the separate three-candidate oracle remainder')
    c.require({path.name for path in (folder/'queries').iterdir()} == {f'{index:02d}' for index in range(6)},
              'Exactly six query receipt directories required')
    replay = next(run for run in case['report']['runs'] if run['cap'] == config['area_cap'] and
                  run['seed'] == config['seed'] and run['policy'] == config['policy'])
    c.require(b.stable(trace['search']['events']) == b.stable(replay['events']),
              'Recorded live GP acquisition events differ from fixed paid replay')
    c.require(len(trace['search']['curve']) == 3 and
              b.stable(case['provenance']['live_best']) == b.stable(trace['search']['curve'][-1]),
              'Recorded live result differs from campaign provenance')
    for point, repeated in zip(trace['search']['curve'],replay['curve']):
        c.require(b.stable(point) == b.stable({key:repeated[key] for key in point}),
                  'Recorded live curve differs from the same replay seed')
    previous = whole['start']['monotonic_after_ns']
    queries = []
    for index, identity in enumerate(paid):
        query = folder/'queries'/f'{index:02d}'
        decision, completed = c.unseal(query/'decision.json'),c.unseal(query/'completed.json')
        record, started = c.unseal(query/'command/record.json'),c.unseal(query/'command/started.json')
        live_runtime.observed_pair(record,started)
        expected = dict(index=index,mode='adaptive' if index < 3 else 'oracle-reference',candidate_id=identity,
            native_name=names[identity],paid_ids_before=paid[:index],
            prereg_manifest_sha256=c.sha(case['prereg']/'manifest.json'),release_sha256=c.sha(campaign/'release.json'),
            completed_live_trace_sha256=None if index < 3 else c.sha(folder/'live.json'),chosen_before_dispatch=True)
        argv = [cohort['python_executable'],'-m','isaforge.integer_workload','measure','--root',
                case['target']['original_root'],'--candidate',names[identity]]
        c.require(decision == expected == record['metadata'] == started['metadata'] and
                  record['argv_sha256'] == hashlib.sha256(observed._json(argv)).hexdigest() and
                  record['observer_pid'] == whole['observer_pid'] and
                  record['durations'] == observed._durations(record['start'],record['end']) and
                  record['durations']['monotonic_endpoints_ordered'] and
                  previous <= record['start']['monotonic_before_ns'] and
                  record['end']['monotonic_after_ns'] <= whole['end']['monotonic_after_ns'],
                  'Serial chosen-before-dispatch paired receipts differ')
        if index < 3:
            c.require(record['end']['monotonic_after_ns'] <= trace['finish']['monotonic_before_ns'],
                      'Live query finished after the sealed live trace')
        else:
            c.require(trace['finish']['monotonic_after_ns'] <= record['start']['monotonic_before_ns'],
                      'Oracle outcome existed before the completed live trace')
        row = labels[identity]
        partial = c.unseal(query/'partial-audit.json')
        partial_labels = {item['candidate_id']:item for item in partial['outcomes']}
        c.require(set(partial_labels) == set(paid[:index+1]) and
                  all(value == labels[key] for key,value in partial_labels.items()) and
                  partial['charged_candidate_attempts'] == index+1 and
                  partial['candidate_wall_seconds_complete'] and
                  completed['partial_audit_digest'] == c.digest(partial) and
                  completed['candidate_id'] == identity and completed['audited_paid_ids'] == sorted(paid[:index+1]) and
                  c.unseal(query/'outcome.json') == row and completed['outcome_sha256'] == c.sha(query/'outcome.json') and
                  (record['returncode'] == 0) == (row.get('status','success') == 'success') and
                  record['durations']['monotonic_elapsed_seconds'] >= case['outer_times'][identity] >= row['measurement_seconds'],
                  'Only charged terminal outcomes may be visible in a live query prefix')
        for stream in ('stdout','stderr'):
            c.require(c.sha(query/'command'/(stream+'.txt')) == record[stream+'_sha256'],
                      'Paired subprocess output checksum differs')
        queries.append(dict(query=index+1,mode=decision['mode'],candidate=names[identity],candidate_id=identity,
            status=row.get('status','success'),ledger_monotonic_seconds=row['measurement_seconds'],
            cli_monotonic_seconds=case['outer_times'][identity],paired_durations=record['durations']))
        previous = record['end']['monotonic_after_ns']
    return dict(schema='isaforge-live-gp-presented-clock-v1',paired_collection_durations=whole['durations'],
        live_prefix_paired_durations=observed._durations(whole['start'],trace['finish']),queries=queries,
        actual_calendar_wall_seconds=None,uninterrupted_calendar_wall_time_established=False,
        note='Paired UTC/monotonic values are retained separately. No tolerance, correction or uninterrupted wall-time saving is claimed.')


def load(campaign, prereg):
    campaign, prereg = Path(campaign).resolve(),Path(prereg).resolve()
    _manifest(campaign);_manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json');provenance = c.unseal(campaign/'provenance.json')
    c.require(cohort['schema'] == live_runtime.SCHEMA and len(cohort['targets']) == 1 and
              provenance['schema'] == live_runtime.SCHEMA+'-campaign' and
              provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
              provenance['source_bindings'] == cohort['source_bindings'] and provenance['live'] == cohort['live'] == live_runtime.LIVE,
              'Exact single-source frozen live campaign required')
    _hashes(ROOT,cohort['source_bindings'])
    group,target = next(iter(cohort['targets'].items()))
    c.require(provenance['workload_group'] == group and target['pool_size'] == 6,
              'Declared six-candidate source identity required')
    selection,original = campaign/'selection',prereg/'targets'/group/'selection'
    c.require(_inventory(selection) == _inventory(original)|FINAL_REPORTS,
              'Complete frozen model package and all final reports required')
    for name in _inventory(original):
        c.require(c.sha(selection/name) == c.sha(original/name), 'Prelabel model/prediction changed: '+name)
    protocol = c.unseal(selection/'protocol.json')
    audit,outer = c.unseal(campaign/'audit.json'),c.unseal(campaign/'outer-times.json')
    public,outcomes = b.public_rows(audit['public']),audit['outcomes']
    c.require(public == c.unseal(prereg/'targets'/group/'public.json') and
              target['native_order'] == audit['pool_names'] and len(public) == 6 and
              protocol['target_workload'] == group and protocol['policies'] == list(POLICY_LABELS) and
              protocol['historical_training_ids'] == target['historical_training_ids'],
              'Exact public pool, twelve policies and fitting cohort required')
    report = c.unseal(selection/'report.json')
    c.require(report['protocol_sha256'] == c.sha(selection/'protocol.json') and
              report['native_audit_digest'] == c.digest(audit) and report['outcomes_sha256'] == c.digest(outcomes) and
              report['reference_censored'] == e.checked_outcomes(public,outcomes,audit) and
              outer == report['candidate_outer_operation_seconds'] and
              provenance['historical_costs'] == cohort['historical_costs'] and
              provenance['qualification'] == cohort['qualification'] and
              provenance['charged_candidate_attempts'] == audit['charged_candidate_attempts'] == 6 and
              provenance['successful_labels'] == len(audit['successful']) and
              provenance['trajectories'] == report['trajectories'] == 180 and
              provenance['endpoints'] == report['endpoints'] == 540 and
              provenance['live_native_dispatch'] is True and provenance['other_policies_native_remeasured'] is False,
              'Final report/native bindings differ')
    context = c.unseal(prereg/'targets'/group/'baseline/context.json')
    c.require(context['workload_group'] == group and context['context_id'] == audit['context_id'] == target['context_id'] and
              set(outer) == {row['candidate_id'] for row in public} and
              all(math.isfinite(value) and value > 0 for value in outer.values()), 'Complete source context and timers required')
    case = dict(campaign=campaign,prereg=prereg,cohort=cohort,provenance=provenance,target=target,
        group=group,selection=selection,protocol=protocol,audit=audit,outer_times=outer,public=public,
        outcomes=outcomes,report=report,context=context)
    case['endpoints'] = endpoints_for_source(group,report,outcomes)
    c.require(case['endpoints'] == c.unseal(campaign/'endpoints.json'), 'Stored twelve-policy endpoints differ')
    case['clock'] = paired_collection(case)
    return case


def resources(record):
    routes,resource = record['routes'],record['resources']
    c.require(len(routes) == len({row['seed'] for row in routes}) == 3, 'Three unique routing seeds required')
    return dict(total_lut4=resource['lut4_count'],flip_flops=resource['flip_flop_count'],
        carry_cells=resource['carry_count'],bram_blocks=resource['memory_blocks'],
        program_data_memory_blocks=resource.get('program_data_memory_blocks'),
        route_seed_count=3,route_seeds=[row['seed'] for row in routes],
        route_fmax_mhz=[row['limiting_internal_fmax_mhz'] for row in routes],
        min_fmax_mhz=min(row['limiting_internal_fmax_mhz'] for row in routes))


def costs(case):
    old = case['cohort']['historical_costs']; audit = case['audit']; clock = case['clock']
    c.require(old['successful_labels'] == 81 and old['failed_attempts'] == 3 and old['total_candidate_attempts'] == 84,
              'Historical81-success/3-failure/84-attempt cost required')
    queries = clock['queries']
    return dict(shared_historical_costs=old,new_candidate_attempts=audit['charged_candidate_attempts'],
        new_candidate_recorded_monotonic_seconds=audit['candidate_wall_seconds'],
        total_unique_candidate_attempts=84+audit['charged_candidate_attempts'],
        history_plus_new_recorded_attempt_seconds=old['total_candidate_wall_seconds']+audit['candidate_wall_seconds'],
        live_candidate_attempts=3,oracle_remainder_attempts=len(queries)-3,
        live_ledger_monotonic_seconds=sum(row['ledger_monotonic_seconds'] for row in queries[:3]),
        oracle_remainder_ledger_monotonic_seconds=sum(row['ledger_monotonic_seconds'] for row in queries[3:]),
        candidate_cli_monotonic_seconds=sum(case['outer_times'].values()),
        candidate_subprocess_monotonic_seconds=sum(row['paired_durations']['monotonic_elapsed_seconds'] for row in queries),
        native_command_count=audit['native_command_count'],native_command_monotonic_seconds=audit['native_command_seconds'],
        baseline_ledger_recorded_seconds=audit['baseline_wall_seconds'],baseline_record_seconds=audit['baseline_record_seconds'],
        qualification=case['cohort']['qualification'],
        classifier_fit_prediction_costs=c.unseal(case['selection']/'feasibility-costs.json'),
        utility_fit_prediction_costs=c.unseal(case['selection']/'controls11/utility-inference-costs.json'),
        control_fit_prediction_costs=[dict(seed=row['seed'],fit_prediction_seconds=row['inference_seconds'])
            for row in c.unseal(case['selection']/'controls11/model/predictions.json')],
        paired_collection_durations=clock['paired_collection_durations'],live_prefix_paired_durations=clock['live_prefix_paired_durations'],
        actual_calendar_wall_seconds=None,timer_scopes_overlap=True,
        note='Historical mixed scopes remain qualified. Live observer, CLI, ledger, native-command and collection durations overlap; do not add them. Other-policy sums are paid replay costs, not measured live-search lifetimes.')


def build(campaign, prereg, output):
    campaign,prereg,output = map(lambda path:Path(path).resolve(),(campaign,prereg,output))
    c.require(not output.exists() and not any(output.is_relative_to(path) or path.is_relative_to(output)
              for path in (campaign,prereg)), 'Fresh report outside sealed inputs required')
    case = load(campaign,prereg); audit = case['audit']; endpoints = case['endpoints']
    displayed = candidate_rows(audit)
    records = packed_measurements(campaign/'native',['baseline']+[row['candidate'] for row in displayed if row['status'] == 'verified'])
    baseline = dict(baseline_cycles=records['baseline']['performance']['cycles'],**resources(records['baseline']))
    candidates,routes = [],[]
    for row in displayed:
        extras = dict(flip_flops=None,carry_cells=None,bram_blocks=None,program_data_memory_blocks=None,
                      route_seed_count=None,route_seeds=None,route_fmax_mhz=None)
        if row['status'] == 'verified':
            record = records[row['candidate']];extras = resources(record)
            c.require(record['performance']['cycles'] == row['cycles'] and extras['total_lut4'] == row['total_lut4'] and
                      extras['min_fmax_mhz'] == row['min_fmax_mhz'], 'Archived hardware/cycle values differ')
        candidates.append(dict(workload_group=case['group'],baseline_cycles=baseline['baseline_cycles'],
            **{**row,**extras},outer_operation_seconds=case['outer_times'][row['candidate_id']],
            timer_basis='recorded monotonic elapsed'))
    for name,record in records.items():
        routes += [dict(candidate=name,**row) for row in record['routes']]
    live_trace = c.unseal(campaign/'collection/live.json')
    labels = {row['candidate_id']:row for row in case['outcomes']}
    query_rows = []
    reference = next(row for row in endpoints if row['cap'] == 64)['reference_cycle_reduction']
    for point in live_trace['search']['curve']:
        attempted = [labels[identity] for identity in point['attempted_ids']]
        best = min([baseline['baseline_cycles']]+[row['candidate_cycles'] for row in attempted if b._feasible(row,64,12)])
        gain = (baseline['baseline_cycles']-best)/baseline['baseline_cycles']
        c.require(math.isclose(point['best_speedup'],baseline['baseline_cycles']/best,rel_tol=1e-12),
                  'Live verified performance differs from actual integer cycles')
        query_rows.append(dict(query=point['budget'],candidate_id=point['attempted_ids'][-1],best_verified_cycles=best,
            best_verified_speedup=point['best_speedup'],verified_cycle_reduction=gain,
            cycle_reduction_regret=reference-gain,oracle_cycle_reduction_fraction=gain/reference if reference > 0 else None,
            charged_ledger_monotonic_seconds=point['target_measurement_seconds'],
            actual_live_policy=live_runtime.LIVE['policy'],actual_live_seed=0))
    accounting = costs(case)
    ceiling = max(row['latency_features']['estimated_saved_cycles'] for row in case['public'])
    primary = [row for row in endpoints if row['cap'] == 64 and row['budget'] == 3]
    fmt = lambda value: '' if value is None or value == '' else f'{value:.9f}'
    text = ['# Fresh-source live GP campaign: '+case['group'],
        'One source, six declared candidates, twelve unchanged policies. The predeclared hybrid_gp_adapt seed0 makes three actual native queries '
        'at +64 LUT4 and12MHz; the other three candidates are measured only after the completed live trace is sealed, for a separate pool oracle. '
        'All other policy/seed comparisons are charged cooperative replay. Five seeds are dependent repetitions, not five independent workloads.',
        f"Baseline:{baseline['baseline_cycles']:,} cycles. The public calibrated ceiling in this restricted pool is only {ceiling} saved cycles "
        f"({100*ceiling/baseline['baseline_cycles']:.9f}% of baseline cycles). This tiny opportunity limits practical gains; it is not broadened after seeing outcomes. "
        'The original workload/input/verifier and frozen policies remain unchanged. A native simulated processor result is not a physical-board measurement.',
        f"Baseline integrated resources: {baseline['total_lut4']} LUT4, {baseline['flip_flops']} flip-flops, "
        f"{baseline['carry_cells']} carry cells and {baseline['bram_blocks']} BRAM blocks. "
        f"Routing seeds {baseline['route_seeds']} achieve {baseline['route_fmax_mhz']} MHz; minimum {baseline['min_fmax_mhz']:.9f} MHz.",
        '## Actual integrated processor outcomes',
        table([['Candidate','Formula','Cycles','Speedup','LUT4 / added','FF / carry / BRAM','Three route Fmax MHz','Minimum MHz','Correctness'],['---']*9]+
            [[row['candidate'],row['formula'],row['cycles'],fmt(row['speedup']),f"{row['total_lut4']} / {row['added_lut4']}",
              f"{row['flip_flops']} / {row['carry_cells']} / {row['bram_blocks']}",
              ', '.join(fmt(value) for value in (row['route_fmax_mhz'] or [])),fmt(row['min_fmax_mhz']),row['correctness']] for row in candidates]),
        'All resources cover the integrated processor/PCPI/RAM. Three route seeds and their minimum are retained; no faster-clock benefit is credited. '
        'Blank failed-attempt performance/hardware values remain unknown. Failures are charged and retain their classifications; unknown outcomes are never negative labels.',
        '## Actual three-query live trace',
        table([['Query','Best cycles','Speedup','Cycle reduction','Regret','Oracle gain fraction','Ledger monotonic s'],['---']*7]+
            [[row['query'],row['best_verified_cycles'],fmt(row['best_verified_speedup']),fmt(row['verified_cycle_reduction']),
              fmt(row['cycle_reduction_regret']),fmt(row['oracle_cycle_reduction_fraction']),fmt(row['charged_ledger_monotonic_seconds'])] for row in query_rows]),
        'The live trace is one seed of one fixed GP policy. Its actual query IDs, paired command receipts, paid-prefix partial audits and later oracle boundary are retained in the campaign. '
        'Three fixed-budget queries are still spent after an early optimum; this does not demonstrate automatic stopping. '
        'The local callback is cooperative isolation, not an OS sandbox. No LLM-agent, joint-set or broad model superiority is established.',
        '## All twelve fixed-policy primary endpoints',
        table([['Policy','Mean cycle reduction','Mean regret','Oracle gain fraction','Improved-reference hits /5','Mean ledger monotonic s'],['---']*6]+
            [[POLICY_LABELS[row['policy']],fmt(row['mean_verified_cycle_reduction']),fmt(row['mean_cycle_reduction_regret']),
              fmt(row['mean_oracle_cycle_reduction_fraction']),row['improving_reference_hits'],fmt(row['mean_target_measurement_seconds'])] for row in primary]),
        'All caps32/64/128 and budgets1/2/3 appear in endpoints.csv. Cycle reduction is1−1/speedup, computed before seed averaging. '
        'Regret subtracts achieved cycle reduction from the verified pool reference. Oracle fraction is undefined for baseline-only references; '
        'baseline retention never earns a90% improved-gain success. If any outcome is infrastructure-censored, reference gaps are lower bounds on regret to the unresolved optimum.',
        '## Costs and clock qualification',
        f"Historical data:81 successful labels plus3 failures =84 unique attempts / {accounting['shared_historical_costs']['total_candidate_wall_seconds']:.6f} recorded seconds, charged once. "
        f"New pool:{accounting['new_candidate_attempts']} attempts / {accounting['new_candidate_recorded_monotonic_seconds']:.6f} ledger monotonic seconds; "
        f"live prefix:{accounting['live_ledger_monotonic_seconds']:.6f}s, oracle remainder:{accounting['oracle_remainder_ledger_monotonic_seconds']:.6f}s. "
        f"Historical plus new candidate attempts:{accounting['total_unique_candidate_attempts']} / {accounting['history_plus_new_recorded_attempt_seconds']:.6f} recorded seconds. "
        'Baseline/setup, rejected qualification, fitting/inference, observer, CLI and native-command costs remain separate in costs.json. Overlapping scopes must not be added.',
        'The previous corpus clock-accounting amendment and strict MD5 failures are preserved separately from this campaign’s paired UTC/monotonic endpoints. '
        'Both paired deltas, capture brackets and disagreement flags are retained in clock-accounting.json. No timestamp correction, '
        'uninterrupted calendar wall time or adaptive-time saving is claimed. Other policies have replayed paid-duration sums, not measured live-search runtimes.',
        'This presenter runs zero model fits/predictions and zero native jobs. Raw provenance, live-choice recreation and exact model refits belong to live_gp_campaign replay. '
        'All new labels become consumed data after collection; no policy is promoted or retuned from these outcomes.']
    output.mkdir(parents=True)
    for name,rows in (('baseline.csv',[baseline]),('candidates.csv',candidates),('routes.csv',routes),('endpoints.csv',endpoints),
                      ('primary.csv',primary),('live-trace.csv',query_rows)):_csv(output/name,rows)
    c.seal(output/'hardware.json',records);c.seal(output/'costs.json',accounting)
    c.seal(output/'clock-accounting.json',dict(historical=case['cohort']['historical_costs']['clock_accounting'],current=case['clock']))
    c.seal(output/'summary.json',dict(workload_group=case['group'],baseline=baseline,public_max_saved_cycles=ceiling,
        primary=primary,live_trace=query_rows,reference_censored=case['report']['reference_censored'],
        superiority_established=False,new_model_fits=0,new_native_jobs=0))
    (output/'results.md').write_text('\n\n'.join(text)+'\n')
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(ROOT/SOURCE),campaign_manifest_sha256=c.sha(campaign/'manifest.json'),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),new_model_fits=0,new_model_predictions=0,new_native_jobs=0))
    c.seal(output/'manifest.json',{path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(candidates=len(candidates),policies=len(primary),endpoint_summaries=len(endpoints),live_queries=len(query_rows),new_model_fits=0,new_native_jobs=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--preregistration',type=Path,default=PREREG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();print(build(args.campaign,args.preregistration,args.output))


if __name__=='__main__':main()
