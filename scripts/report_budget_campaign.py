"""Reproduce and export measured campaign tables and a primary-endpoint figure."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from scripts.reproduce_budget_campaign import SNAPSHOT, replay

LABELS = dict(frequency='Frequency', merit='Merit', calibrated_latency='Calibrated latency',
    latency_cost_heuristic='Latency + cost heuristic', random='Random',
    raw_regression='Original XGBoost', ranking='Pairwise XGBoost',
    normalized_xgb='Normalized XGBoost', hybrid_gp_zero_shot='Hybrid GP: zero shot',
    hybrid_gp_adapt='Hybrid GP: paid adaptation')


def table(rows):
    def cell(value):
        return ('' if value is None else str(value)).replace('|','\\|').replace('\n',' ')
    return '\n'.join('| '+' | '.join(cell(value) for value in row)+' |' for row in rows)


def write_csv(path, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def failed_candidate(base):
    """Describe observed failures without inferring unknown correctness/benefit.

    Exit 7 alone is ambiguous: self-check, timeout and incomplete reports share
    it. Only the raw checked simulation can establish a recorded-run failure.
    """
    base = Path(base)
    failures = list(base.glob('attempt-*/failure.json'))
    c.require(len(failures) == 1, 'Exactly one authenticated failed attempt required')
    failure = c.read(failures[0]); attempt = failures[0].parent
    path = attempt/'simulation/simulation.json'
    raw = c.read(path) if path.exists() else {}
    words = raw.get('words', [])
    complete = (len(words) == 5 and words[0] == 1230192966 and raw.get('markers') == 2
                and raw.get('partial_report_bits') == 0)
    result = dict(outcome='failed_attempt', failure_class='outcome_unknown',
        correctness='Unverified', correctness_verified=None,
        observed_unverified_cycles=words[2] if complete else '',
        failure_reason=failure['error'], measurement_seconds=failure['elapsed_seconds'],
        reference_censored=True)
    if raw.get('stack_violations', 0) > 0:
        result.update(failure_class='memory_contract_failure', correctness='Memory-contract failure on recorded run',
                      correctness_verified=False, reference_censored=False)
    elif complete and words[4] == 0:
        result.update(failure_class='self_check_failure', correctness='Self-check failed on recorded run',
                      correctness_verified=False, reference_censored=False)
    elif raw.get('fault', 0) or raw.get('trapped', False):
        result.update(failure_class='execution_failure', correctness='Execution failed on recorded run',
                      correctness_verified=False, reference_censored=False)
    elif any(reason in failure['error'] for reason in ('Less than 2 GiB free', 'No space left on device')):
        result.update(failure_class='infrastructure_unknown', correctness='Unverified: infrastructure interrupted attempt')
    return result


def candidate_rows(root, workload):
    root = Path(root)
    discovery = c.unseal(root/'discovery/discovery.json')
    rows = []
    for candidate in discovery['pool']:
        base = root/'measurements'/candidate['name']; path = base/'measurement.json'
        common = dict(workload=workload, candidate=candidate['name'], cycles='', speedup='',
            lut4='', added_lut4='', flip_flops='', carry_cells='', min_fmax_mhz='',
            feasible_at_64=None, formula=candidate['formula'])
        if not path.exists():
            result = failed_candidate(base)
            # A known recorded-run correctness failure cannot be selected. An
            # interrupted attempt has unknown feasibility, rather than false.
            common.update(feasible_at_64=None if result['reference_censored'] else False, **result)
        else:
            record = c.unseal(path)
            fmax = min(r['limiting_internal_fmax_mhz'] for r in record['routes'])
            common.update(cycles=record['performance']['cycles'], speedup=record['speedup'],
                lut4=record['resources']['lut4_count'], added_lut4=record['added_lut4'],
                flip_flops=record['resources']['flip_flop_count'],
                carry_cells=record['resources'].get('carry_count',''), min_fmax_mhz=fmax,
                feasible_at_64=record['added_lut4']<=64 and record['timing_feasible'],
                outcome='verified', failure_class='', correctness='Verified for recorded input',
                correctness_verified=True, observed_unverified_cycles='', failure_reason='',
                measurement_seconds=record['elapsed_seconds'], reference_censored=False)
        rows.append(common)
    return rows


def reference_status(rows):
    unknown = [r['candidate'] for r in rows if r['reference_censored']]
    return dict(label='Best verified pool reference', complete_for_recorded_pool=not unknown,
        censored_candidates=unknown,
        interpretation=('Lower bound on the frozen-pool optimum: interrupted attempts have unknown performance, hardware feasibility and/or correctness.'
                        if unknown else 'Reference over verified candidates, baseline, and observed invalid recorded runs in the declared pool.'))


def primary_comparison(primary):
    latency = next(r['mean_best_speedup'] for r in primary if r['policy']=='calibrated_latency')
    learned = [r for r in primary if r['policy'] in ('raw_regression','ranking','normalized_xgb',
                                                    'hybrid_gp_zero_shot','hybrid_gp_adapt')]
    if learned and all(r['mean_best_speedup'] == latency for r in learned):
        return 'All five learned policies tie calibrated latency at the primary endpoint; this comparison shows no learned selection win.'
    if learned and all(r['mean_best_speedup'] <= latency for r in learned):
        return 'No learned policy exceeds calibrated latency at the primary endpoint; some perform worse.'
    return 'Some learned policies exceed calibrated latency at this workload endpoint; assess the paired workload results before claiming transfer.'


def build(snapshot, raw, output):
    snapshot, raw, output = map(Path, (snapshot, raw, output))
    verification = replay(snapshot, raw)
    report = c.unseal(snapshot/'selection/campaign-report.json')
    output.mkdir(parents=True, exist_ok=True)
    measurements, endpoints, references = [], [], {}
    sections = ['# ISAForge: prospective equal-budget results',
        'Primary comparison: three paid candidate evaluations, at most 64 added LUT4, '
        '12 MHz, five dependent seeds. Two source workloads are the independent test units. '
        'The reference is the best verified feasible design found in each frozen six-candidate pool. '
        'Any infrastructure-censored attempt makes that reference a lower bound on the pool optimum. Figures are RTL simulation '
        'and integrated FPGA synthesis/routing, not physical-board measurements.']
    for workload, value in report['targets'].items():
        root = raw/('target-'+workload.removeprefix('embench-'))
        baseline = c.unseal(root/'measurements/baseline/measurement.json')
        rows = candidate_rows(root, workload)
        reference = references[workload] = reference_status(rows)
        measurements += rows
        sections += ['## '+workload, f"Baseline: {baseline['performance']['cycles']:,} cycles; "
            f"{baseline['resources']['lut4_count']:,} LUT4. All routing seeds are retained in the raw evidence."]
        sections.append(reference['label']+'. '+reference['interpretation'])
        sections.append(table([['Candidate','Verified cycles','Speedup','LUT4 / added','FF','Carry','Min Fmax MHz','Feasible at +64','Correctness','Charged seconds'],
            ['---']*10]+[[r['candidate'],r['cycles'],f"{r['speedup']:.9f}" if r['speedup'] else '',
            str(r['lut4'])+' / '+str(r['added_lut4']) if r['lut4']!='' else '',r['flip_flops'],r['carry_cells'],
            r['min_fmax_mhz'],r['feasible_at_64'],r['correctness'],f"{r['measurement_seconds']:.3f}"] for r in rows]))
        failures = [r for r in rows if r['outcome']=='failed_attempt']
        if failures:
            sections.append(table([['Failed attempt','Classification','Charged seconds','Reason'],['---']*4]+
                [[r['candidate'],r['failure_class'],f"{r['measurement_seconds']:.3f}",r['failure_reason']] for r in failures]))
            sections.append('Recorded-run self-check or memory-contract failures are not proofs about all inputs. '
                            'Blank hardware/performance values were not verified. Unverified observed cycles, where available, '
                            'are diagnostic only and are retained separately in candidates.csv. Every failed attempt consumes its query and recorded wall time.')
        primary = [r for r in value['summary'] if r['area_delta_lut4_cap']==64 and r['budget']==3]
        sections.append(primary_comparison(primary))
        sections.append(table([['Policy','Mean best speedup','Verified-reference hits / 5','Mean candidate seconds'],['---']*4]+
            [[LABELS[r['policy']],f"{r['mean_best_speedup']:.9f}",r['oracle_hits'],
              f"{r['mean_target_measurement_seconds']:.3f}"] for r in primary]))
        for point in value['summary']:
            exported = dict(point)
            exported['verified_reference_hits'] = exported.pop('oracle_hits')
            if 'mean_regret' in exported:
                exported['mean_gap_to_verified_reference'] = exported.pop('mean_regret')
            endpoints.append(dict(workload=workload,reference_complete=reference['complete_for_recorded_pool'],**exported))
    sections += ['## Interpretation and limits',
        'Read the paired workload comparisons in campaign-report.json before claiming an advantage. '
        'A tie in best feasible speedup is not an ML win. Lower prediction error alone is not a selection win. '
        'These workloads become development data after this report; changes need fresh held-out workloads or inputs.',
        f"The fixed historical training corpus has {report['historical_costs']['candidate_labels']} candidate labels and "
        f"{report['historical_costs']['candidate_wall_seconds']:.6f} candidate wall-seconds. "
        'Baseline/setup work, calibration, failed qualification attempts, static diagnostics and inference are separate '
        'reported scopes. This is not a complete lifetime project-cost total. Never add native command durations '
        'to overlapping evaluation wall durations. Individual candidate benefits do not establish a combined instruction set.',
        'The LLM selection agent, additional independent inputs, calibrated uncertainty and jointly evaluated instruction sets remain missing.',
        'Reproduce: `python scripts/report_budget_campaign.py`. Replay authenticates all raw measurements, '
        'refits frozen predictions exactly and starts zero native hardware jobs.']
    write_csv(output/'candidates.csv', measurements)
    write_csv(output/'policy-endpoints.csv', endpoints)
    c.write(output/'reference-status.json',references)
    (output/'results.md').write_text('\n\n'.join(sections)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shown = ('merit','calibrated_latency','random','raw_regression','normalized_xgb','hybrid_gp_adapt')
    fig, axes = plt.subplots(1,len(report['targets']),figsize=(12,4.8),squeeze=False)
    for ax,(workload,value) in zip(axes[0],report['targets'].items()):
        reference = next(r['speedup'] for r in value['oracles'] if r['area_delta_lut4_cap']==64)
        ax.axhline(100*(reference-1),color='#333333',linestyle=':',label='Best verified pool reference')
        for index,policy in enumerate(shown):
            points = sorted((r for r in value['summary'] if r['policy']==policy and r['area_delta_lut4_cap']==64),key=lambda r:r['budget'])
            ax.plot([r['budget'] for r in points],[100*(r['mean_best_speedup']-1) for r in points],
                    marker=('o','s','^','v','D','X')[index],markersize=5,
                    linestyle=('-', '--','-.',':','--','-')[index],label=LABELS[policy],alpha=.85)
        suffix = '\nPool optimum remains unknown' if references[workload]['censored_candidates'] else ''
        ax.set_title(workload.removeprefix('embench-')+suffix);ax.set_xticks([1,2,3]);ax.set_xlabel('Paid candidate evaluations')
        ax.set_ylabel('Best feasible speedup gain (%)');ax.grid(alpha=.2)
    handles,labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4,frameon=False,fontsize=8)
    fig.suptitle('Held-out workloads · +64 LUT4 · 12 MHz\nMean of five dependent seeds; overlapping curves indicate ties',fontsize=12)
    fig.tight_layout(rect=(0,.14,1,.91))
    fig.savefig(output/'selection.png',dpi=180);fig.savefig(output/'selection.svg');plt.close(fig)
    c.write(output/'verification.json',verification)
    print(dict(output=str(output),**verification))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,default=SNAPSHOT)
    parser.add_argument('--raw-root',type=Path,default=ROOT/'generated/reproduction/budget-campaign')
    parser.add_argument('--output',type=Path,default=ROOT/'generated/reproduction/budget-campaign-report')
    args=parser.parse_args();build(args.snapshot,args.raw_root,args.output)


if __name__=='__main__': main()
