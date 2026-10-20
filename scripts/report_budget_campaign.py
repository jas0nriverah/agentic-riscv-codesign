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
    return '\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)


def write_csv(path, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def build(snapshot, raw, output):
    snapshot, raw, output = map(Path, (snapshot, raw, output))
    verification = replay(snapshot, raw)
    report = c.unseal(snapshot/'selection/campaign-report.json')
    output.mkdir(parents=True, exist_ok=True)
    measurements, endpoints = [], []
    sections = ['# ISAForge: prospective equal-budget results',
        'Primary comparison: three paid candidate evaluations, at most 64 added LUT4, '
        '12 MHz, five dependent seeds. Two source workloads are the independent test units. '
        'The measured oracle covers each frozen six-candidate pool. Figures are RTL simulation '
        'and integrated FPGA synthesis/routing, not physical-board measurements.']
    for workload, value in report['targets'].items():
        root = raw/('target-'+workload.removeprefix('embench-'))
        baseline = c.unseal(root/'measurements/baseline/measurement.json')
        discovery = c.unseal(root/'discovery/discovery.json')
        rows = []
        for candidate in discovery['pool']:
            path = root/'measurements'/candidate['name']/'measurement.json'
            if not path.exists():
                rows.append(dict(workload=workload, candidate=candidate['name'], cycles='',
                    speedup='', added_lut4='', flip_flops='', carry_cells='', min_fmax_mhz='',
                    feasible_at_64=False, correctness='failed', formula=candidate['formula']))
                continue
            record = c.unseal(path)
            fmax = min(r['limiting_internal_fmax_mhz'] for r in record['routes'])
            rows.append(dict(workload=workload, candidate=candidate['name'],
                cycles=record['performance']['cycles'], speedup=record['speedup'],
                added_lut4=record['added_lut4'],
                flip_flops=record['resources']['flip_flop_count'],
                carry_cells=record['resources'].get('carry_count',''), min_fmax_mhz=fmax,
                feasible_at_64=record['added_lut4']<=64 and record['timing_feasible'],
                correctness='verified', formula=candidate['formula']))
        measurements += rows
        sections += ['## '+workload, f"Baseline: {baseline['performance']['cycles']:,} cycles; "
            f"{baseline['resources']['lut4_count']:,} LUT4. All routing seeds are retained in the raw evidence."]
        sections.append(table([['Candidate','Cycles','Speedup','Added LUT4','Min Fmax MHz','Feasible at +64','Correctness'],
            ['---']*7]+[[r['candidate'],r['cycles'],f"{r['speedup']:.9f}" if r['speedup'] else '',
            r['added_lut4'],r['min_fmax_mhz'],r['feasible_at_64'],r['correctness']] for r in rows]))
        primary = [r for r in value['summary'] if r['area_delta_lut4_cap']==64 and r['budget']==3]
        sections.append(table([['Policy','Mean best speedup','Oracle hits / 5','Mean candidate seconds'],['---']*4]+
            [[LABELS[r['policy']],f"{r['mean_best_speedup']:.9f}",r['oracle_hits'],
              f"{r['mean_target_measurement_seconds']:.3f}"] for r in primary]))
        endpoints += [dict(workload=workload, **r) for r in value['summary']]
    sections += ['## Interpretation and limits',
        'Read the paired workload comparisons in campaign-report.json before claiming an advantage. '
        'A tie in best feasible speedup is not an ML win. Lower prediction error alone is not a selection win. '
        'These workloads become development data after this report; changes need fresh held-out workloads or inputs.',
        'The fixed historical training corpus has 18 candidate labels and 793.926327 candidate wall-seconds. '
        'Baseline/setup work, calibration, failed qualification attempts, static diagnostics and inference are separate '
        'reported scopes. This is not a complete lifetime project-cost total. Never add native command durations '
        'to overlapping evaluation wall durations. Individual candidate benefits do not establish a combined instruction set.',
        'The LLM selection agent, additional independent inputs, calibrated uncertainty and jointly evaluated instruction sets remain missing.',
        'Reproduce: `python scripts/report_budget_campaign.py`. Replay authenticates all raw measurements, '
        'refits frozen predictions exactly and starts zero native hardware jobs.']
    write_csv(output/'candidates.csv', measurements)
    write_csv(output/'policy-endpoints.csv', endpoints)
    (output/'results.md').write_text('\n\n'.join(sections)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shown = ('merit','calibrated_latency','random','raw_regression','normalized_xgb','hybrid_gp_adapt')
    fig, axes = plt.subplots(1,len(report['targets']),figsize=(12,4.8),squeeze=False)
    for ax,(workload,value) in zip(axes[0],report['targets'].items()):
        oracle = next(r['speedup'] for r in value['oracles'] if r['area_delta_lut4_cap']==64)
        ax.axhline(100*(oracle-1),color='#333333',linestyle=':',label='Measured pool oracle')
        for index,policy in enumerate(shown):
            points = sorted((r for r in value['summary'] if r['policy']==policy and r['area_delta_lut4_cap']==64),key=lambda r:r['budget'])
            ax.plot([r['budget'] for r in points],[100*(r['mean_best_speedup']-1) for r in points],
                    marker=('o','s','^','v','D','X')[index],markersize=5,
                    linestyle=('-', '--','-.',':','--','-')[index],label=LABELS[policy],alpha=.85)
        ax.set_title(workload.removeprefix('embench-'));ax.set_xticks([1,2,3]);ax.set_xlabel('Paid candidate evaluations')
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
