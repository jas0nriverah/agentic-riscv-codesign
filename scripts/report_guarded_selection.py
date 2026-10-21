"""Render completed guarded selection evidence without fitting or native jobs.

This presenter reads the sealed post-collection report, including the preserved
guarded_evidence.audit result. It never opens a native target directory.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from scripts.report_budget_campaign import LABELS, primary_comparison, table, write_csv


def candidate_rows(audit):
    public=audit['public']; names=audit['pool_names']
    c.require(len(public)==len(names) and len(set(names))==len(names), 'Unique aligned public pool required')
    observed={r['candidate_id']:r for r in audit['outcomes']}
    c.require(len(observed)==len(audit['outcomes']) and set(observed)<={r['candidate_id'] for r in public},
              'Outcome identities differ from public pool')
    failed={r['name']:r for r in audit['failed_or_interrupted']}
    rows=[]
    for name,features in zip(names,public):
        outcome=observed.get(features['candidate_id']); failure=failed.get(name,{})
        row=dict(candidate=name,candidate_id=features['candidate_id'],formula=features['formula'],
            status='unattempted',cycles='',speedup='',total_lut4='',added_lut4='',min_fmax_mhz='',
            estimated_saved_cycles='',measured_saved_cycles='',saved_cycle_residual='',
            correctness_verified=None,correctness='Unverified',failure_class='',failure_reason='',
            charged_wall_seconds=None,measurement_record_seconds=None,reference_censored=True)
        if outcome and outcome.get('status','success')=='success':
            row.update(status='verified',cycles=outcome['candidate_cycles'],speedup=outcome['speedup'],
                total_lut4=outcome['area'],added_lut4=outcome['area_delta_lut4'],
                min_fmax_mhz=outcome['routed_fmax_min_mhz'],correctness_verified=True,
                correctness='Verified for recorded input',charged_wall_seconds=outcome['measurement_seconds'],
                measurement_record_seconds=outcome.get('measurement_record_seconds'),reference_censored=False)
            estimated=features.get('latency_features',{}).get('estimated_saved_cycles')
            baseline=outcome.get('baseline_cycles',features.get('latency_features',{}).get('baseline_cycles'))
            if estimated is not None and baseline is not None:
                measured=baseline-outcome['candidate_cycles']
                row.update(estimated_saved_cycles=estimated,measured_saved_cycles=measured,
                           saved_cycle_residual=measured-estimated)
        elif outcome or failure:
            row.update(status=failure.get('status','failed'),
                correctness_verified=failure.get('correctness_verified'),
                correctness='Failed on recorded run' if failure.get('correctness_verified') is False else 'Unverified',
                failure_class=failure.get('classification',(outcome or {}).get('failure_class','unknown')),
                failure_reason=failure.get('error',(outcome or {}).get('error','')),
                charged_wall_seconds=(outcome or {}).get('measurement_seconds',failure.get('elapsed_seconds')),
                reference_censored=failure.get('reference_censored',True))
        rows.append(row)
    return rows


def baseline_summary(audit,before):
    cycles={r.get('latency_features',{}).get('baseline_cycles') for r in audit['public']}
    cycles.update(r.get('baseline_cycles') for r in audit['outcomes'] if r.get('status','success')=='success')
    cycles.discard(None)
    luts={r['area']-r['area_delta_lut4'] for r in audit['outcomes'] if r.get('status','success')=='success'}
    if before.get('baseline_lut4') is not None: luts.add(before['baseline_lut4'])
    c.require(len(cycles)<=1 and len(luts)<=1,'Retained baseline values disagree')
    return dict(cycles=next(iter(cycles),None),lut4=next(iter(luts),None),
        min_fmax_mhz=before.get('baseline_routed_fmax_min_mhz',audit.get('baseline_routed_fmax_min_mhz')))


def regression_diagnostics(selection):
    groups={}
    for row in selection.get('diagnostics',[]):
        if row.get('model') in ('raw','normalized') and row.get('mae') is not None:
            groups.setdefault(row['model'],[]).append(row)
    return [dict(model=name,dependent_seed_repetitions=len({r['seed'] for r in rows}),
        mean_speedup_mae=statistics.mean(r['mae'] for r in rows),
        mean_interval_coverage=statistics.mean(r['interval_coverage'] for r in rows),
        calibrated_confidence=False) for name,rows in sorted(groups.items())]


def endpoint_rows(selection,references,costs):
    refs={r['area_delta_lut4_cap']:r for r in references}; result=[]
    for summary in selection['summary']:
        policy,cap,budget=(summary[k] for k in ('policy','area_delta_lut4_cap','budget'))
        matched=[(run['seed'],point) for run in selection['runs']
            if run['policy']==policy and run['area_delta_lut4_cap']==cap
            for point in run['curve'] if point['budget']==budget]
        c.require(len(matched)==5 and {seed for seed,_ in matched}==set(range(5)),
                  'Each endpoint requires five distinct dependent seed repetitions')
        points=[point for _,point in matched]; ref=refs[cap]
        c.require(statistics.mean(p['best_speedup'] for p in points)==summary['mean_best_speedup'],
                  'Frozen summary differs from per-seed endpoints')
        seconds=statistics.mean(p['target_measurement_seconds'] for p in points)
        c.require(seconds==summary['mean_target_measurement_seconds'], 'Frozen summary time differs')
        result.append(dict(policy=policy,area_delta_lut4_cap=cap,budget=budget,dependent_seed_count=5,
            mean_best_verified_speedup=summary['mean_best_speedup'],
            mean_gap_to_verified_reference=summary['mean_regret'],verified_reference_hits=summary['oracle_hits'],
            reference_speedup=ref['best_verified_speedup'],reference_complete=ref['complete_pool_reference'],
            positive_design_reference_hits=summary['oracle_hits'] if ref['best_verified_speedup']>1 else 0,
            mean_target_attempt_seconds=seconds,mean_failed_attempts=summary['mean_failed_attempts'],
            mean_inference_seconds=statistics.mean(p.get('inference_seconds',0) for p in points),
            historical_total_attempt_seconds=costs['total_candidate_wall_seconds'],
            history_plus_target_attempt_seconds=costs['total_candidate_wall_seconds']+seconds))
    c.require(result and {r['policy'] for r in result}==set(LABELS), 'All ten frozen policy summaries required')
    expected={(p,cap,b) for p in LABELS for cap in (32,64,128) for b in (1,2,3)}
    c.require(len(result)==len(expected) and {(r['policy'],r['area_delta_lut4_cap'],r['budget']) for r in result}==expected,
              'Complete policy/cap/budget endpoint grid required')
    return result


def number(value,places=3):
    return '' if value is None or value=='' else f'{value:.{places}f}'


def build(selection_root,output):
    selection_root,output=Path(selection_root).resolve(),Path(output).resolve()
    c.require(not output.is_relative_to(selection_root), 'Derived reports must be outside the frozen selection directory')
    path=selection_root/'report.json'
    c.require(path.exists(), 'Completed guarded selection report required; target files are not read by this presenter')
    report=c.unseal(path)
    c.require(report['schema']=='isaforge-guarded-selection-report-v1','Unknown guarded selection report schema')
    audit,selection,costs=report['raw_audit'],report['selection'],report['historical_costs']
    rows=candidate_rows(audit); references=report['best_verified_references']
    before=c.unseal(selection_root/'baseline.json') if (selection_root/'baseline.json').exists() else {}
    baseline=baseline_summary(audit,before); diagnostics=regression_diagnostics(selection)
    endpoints=endpoint_rows(selection,references,costs)
    workload=audit['public'][0]['benchmark'].split(':',1)[0]
    primary=[r for r in selection['summary'] if r['area_delta_lut4_cap']==64 and r['budget']==3]
    sections=['# Guarded instruction selection: '+workload,
        f"Scope: **{report['scope']}**. Primary endpoint: three charged candidate attempts, +64 LUT4, 12 MHz. "
        'One source workload is the independent unit; five seeds are dependent bootstrap/tie repetitions. '
        'These results do not establish broad generalization. Values come from checked RTL simulation and integrated FPGA synthesis/routing.',
        primary_comparison(primary)]
    if report['scope']!='prospective':
        sections.append('This consumed-workload run is engineering validation, not a held-out source-family ML test.')
    sections.append(f"Retained baseline: {baseline['cycles'] if baseline['cycles'] is not None else 'unavailable'} cycles; "
        f"{baseline['lut4'] if baseline['lut4'] is not None else 'unavailable'} integrated LUT4; minimum routed Fmax: "
        +(number(baseline['min_fmax_mhz'])+' MHz' if baseline['min_fmax_mhz'] is not None else 'not retained in the selection report.'))
    unknown=report['reference_censored_candidates']; missing=audit['unattempted']
    sections+=['## Verified references',table([['Added LUT4 cap','Best verified speedup','Selected candidate','Complete recorded pool'],['---']*4]+
        [[r['area_delta_lut4_cap'],number(r['best_verified_speedup'],9),r['selected_name'] or 'Baseline',
          r['complete_pool_reference']] for r in references])]
    if unknown or missing or any(not r['complete_pool_reference'] for r in references):
        sections.append('The reference is a **lower bound on the unresolved full-pool optimum**. '
            f"Censored outcomes: {', '.join(unknown) or 'none listed'}. Unattempted: {', '.join(missing) or 'none'}. "
            'Reported gaps are gaps to verified evidence, not complete-pool regret. Unknown correctness, hardware cost and elapsed time are never replaced with false or zero.')
    else:
        sections.append('References cover the declared recorded-input pool, including baseline and known invalid attempts. They do not cover all legal instructions or other inputs.')
    sections.append('A reference equal to 1.0 is baseline retention; reference hits in that case are not discoveries of improved designs.')
    sections+=['## Candidate outcomes',table([['Candidate','Verified cycles','Speedup','LUT4 / added','Min Fmax MHz','Correctness','Charged wall seconds'],['---']*7]+
        [[r['candidate'],r['cycles'],number(r['speedup'],9),
          f"{r['total_lut4']} / {r['added_lut4']}" if r['total_lut4']!='' else '',number(r['min_fmax_mhz']),
          r['correctness'],number(r['charged_wall_seconds'])] for r in rows])]
    failures=[r for r in rows if r['status']!='verified']
    if failures:
        sections.append(table([['Attempt','Status','Classification','Charged seconds','Reason'],['---']*5]+
            [[r['candidate'],r['status'],r['failure_class'],number(r['charged_wall_seconds']),r['failure_reason']] for r in failures]))
    sections.append('Correctness failures apply to the recorded run, not every possible input. Blank performance/hardware values are unverified. '
        'The charged ledger wall time includes the complete attempt; original measurement-record duration is retained separately in candidates.csv. Failed attempts still consume their query and known wall time.')
    residuals=[row for row in rows if row['saved_cycle_residual']!='']
    if residuals:
        sections+=['## Analytic cycle check',table([['Verified candidate','Estimated saved cycles','Measured saved cycles','Residual: measured minus estimated'],['---']*4]+
            [[row['candidate'],row['estimated_saved_cycles'],row['measured_saved_cycles'],row['saved_cycle_residual']] for row in residuals])]
    if diagnostics:
        sections+=['## Frozen regression diagnostics',table([['Model','Dependent seed repetitions','Mean speedup MAE','Nominal interval coverage (%)'],['---']*4]+
            [[row['model'],row['dependent_seed_repetitions'],number(row['mean_speedup_mae'],9),
              number(100*row['mean_interval_coverage'],1)] for row in diagnostics]),
            'These diagnostics cover verified success labels only. Failed and censored attempts have no regression label. '
            'Means across dependent model seeds are descriptive; nominal ensemble coverage is not calibrated confidence. '
            'Lower prediction error does not by itself establish a selection win.']
    sections.append('## Equal-budget policy results')
    for cap in (32,64,128):
        sections.append(f'### At most {cap} added LUT4')
        sections.append(table([['Policy','Queries','Mean best speedup','Gap to verified reference','Reference hits / 5','Mean attempt seconds','Mean failed queries'],['---']*7]+
            [[LABELS[r['policy']],r['budget'],number(r['mean_best_verified_speedup'],9),
              number(r['mean_gap_to_verified_reference'],9),r['verified_reference_hits'],
              number(r['mean_target_attempt_seconds']),number(r['mean_failed_attempts'],1)]
             for r in endpoints if r['area_delta_lut4_cap']==cap]))
    sections+=['## Costs and limits',
        f"Historical data: {costs['successful_labels']} verified labels and {costs['failed_attempts']} failed attempts "
        f"({costs['total_candidate_attempts']} attempts), costing {costs['verified_candidate_wall_seconds']:.6f} verified-label wall-seconds "
        f"plus {costs['failed_candidate_wall_seconds']:.6f} failed-attempt wall-seconds = **{costs['total_candidate_wall_seconds']:.6f} seconds**. "
        'The frozen model’s historical cost field counts successful labels only; the full attempt total above includes failures once.',
        f"Current candidate attempts: {audit['charged_candidate_attempts']}; known charged wall time {audit['candidate_wall_seconds']:.6f} seconds; "
        f"wall-time accounting complete: {audit['candidate_wall_seconds_complete']}. Baseline ledger wall time: {audit['baseline_wall_seconds']:.6f} seconds. "
        f"Native command time: {audit['native_command_seconds']:.6f} seconds in {audit['native_command_count']} commands. "
        'Baseline, setup, historical qualification, calibration and inference have separate scopes. Native command times overlap evaluation wall times and must not be added. '
        'policy-endpoints.csv reports target-only and shared-history-plus-target attempt time, with inference separate.',
        'A tie in best verified feasible performance is not a learned selection win. Faster failed attempts alone do not demonstrate better acquisition. '
        'Bootstrap/GP uncertainty is not calibrated confidence. Single-instruction outcomes do not establish the behavior of a jointly installed instruction set.',
        'This presenter reads the sealed completed report only. It performs zero model fits and zero native measurements; raw evidence authentication and exact historical refits belong to guarded_selection replay.']
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'candidates.csv',rows);write_csv(output/'policy-endpoints.csv',endpoints)
    if diagnostics: write_csv(output/'regression-diagnostics.csv',diagnostics)
    c.write(output/'baseline.json',baseline)
    c.write(output/'reference-status.json',dict(references=references,censored=unknown,unattempted=missing))
    (output/'results.md').write_text('\n\n'.join(sections)+'\n')
    provenance=dict(selection_report_sha256=c.sha(path),report_source_sha256=c.sha(__file__),
        source_scope=report['scope'],new_model_fits=0,new_native_jobs=0)
    c.write(output/'provenance.json',provenance)
    return dict(output=str(output),candidate_rows=len(rows),policy_endpoints=len(endpoints),**provenance)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-root',type=Path,default=ROOT/'results/2026-10-21-sha256-selection')
    parser.add_argument('--output',type=Path,default=ROOT/'generated/reproduction/guarded-sha256-report')
    args=parser.parse_args(argv);print(build(args.selection_root,args.output))


if __name__=='__main__':main()
