"""Render only the 2026-10-28 r1 frozen calibration experiment without fitting or measuring anything."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=ROOT/'reports/2026-10-28-grouped-feasibility-calibration-r1'
    for name,digest in c.unseal(source/'manifest.json').items():
        c.require(c.sha(source/name)==digest, 'Changed experiment artifact')
    result=c.unseal(source/'result.json')
    out=ROOT/'reports/2026-10-28-model-agent-checkpoint';out.mkdir(exist_ok=True)
    rows=[r for r in result['summary'] if r['budget']==3]
    labels={'raw_factorized':'Raw feasibility utility','calibrated_factorized':'Calibrated feasibility utility',
        'pairwise':'Pairwise XGBoost','merit':'Merit heuristic','calibrated_latency':'Latency heuristic',
        'frequency':'Frequency heuristic','random':'Random (5 seeds)'}
    plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(10,5.8))
    bars=ax.barh([labels[r['policy']] for r in rows],[100*r['mean_cycle_reduction'] for r in rows],color=['#547590','#c28f4e','#237fad','#427e57','#427e57','#82928a','#a8adb5'])
    ax.invert_yaxis();ax.set_xlim(0,2.1);ax.set_xlabel('Mean verified whole-program cycle reduction (%)')
    ax.bar_label(bars,fmt='%.3f%%',padding=5,fontsize=11)
    ax.set_title('Merit remains ahead at a three-evaluation budget',loc='left',pad=17)
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    fig.text(.02,.025,'17 held-out workload groups • +64 LUT4 / 12 MHz • consumed-data retrospective replay',fontsize=10)
    fig.tight_layout(rect=(0,.06,1,1))
    fig.savefig(out/'selection-budget3.png',dpi=180);fig.savefig(out/'selection-budget3.svg');plt.close(fig)
    p=out/'selection-budget3.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n')
    lines=['# Model and agent development checkpoint','',
        'The fixed nested calibration challenger was **not promoted**. It tied raw feasibility utility at budget three and worsened probability metrics. No new model outperformance claim is supported.','',
        '## Measured-data replay','',
        '156 successful candidate measurements and four charged failures across 17 workload groups. Each outer fold excludes its workload and all target canonical operator-tree families. Calibration uses only inner held-out predictions with the same exclusions. These are consumed development data, not a new prospective test.','',
        '| Policy | B3 mean cycle reduction | Mean charged seconds | Complete-pool regret |',
        '|---|---:|---:|---:|']
    for r in rows:lines.append(f"| {labels[r['policy']]} | {100*r['mean_cycle_reduction']:.4f}% | {r['mean_measurement_seconds']:.2f} | {100*r['mean_cycle_reduction_regret']:.4f} percentage points |")
    lines += ['', 'Regret covers 15 complete workload pools; two censored pools are excluded. Selection performance covers all 17. Random seeds are averaged within workload, not treated as independent evidence. Measurement times are historical charged evaluation times, not new hardware work. Total source-corpus collection cost is 8,657.112 seconds across all 160 attempts; fold fits use subsets of that corpus. The nested diagnostic took 24.743 seconds on this host.', '',
        'Brier score worsened from 0.21685 to 0.22390; log loss worsened from 0.62418 to 0.64048 (lower is better). Probability metrics cover successful known outcomes only. All 17 folds fitted the logistic calibrator; no identity fallbacks occurred. Calibrated utility ties raw utility on all 17 B3 workloads and loses to merit on two, tying 15. The paired workload-bootstrap interval for its reduction difference versus merit is [-0.4873, 0.0000] percentage points. This does not establish an advantage.', '',
        'The existing pairwise model remains a challenger, not the winning policy. The next useful experiment is a frozen forward comparison on countnegative; additional parameter sweeps on this development set would not establish generalization.', '',
        '## Newly qualified workload','',
        'Countnegative v2 passed prepare, discovery, opportunity, baseline, public-feature export and freeze. Four legal candidates were retained without the old twelve-candidate minimum. The unchanged upstream self-check passed; baseline is 12,477 cycles / 2,510 instructions, 1,653 LUT4, 295 carry cells, 20 RAM blocks, 655 flip-flops. Three routed Fmax values are 77.160 / 68.493 / 70.388 MHz. Candidate measurements remain **zero**; this is pipeline qualification, not four new speedup labels. The source was previously screened, so it is not an untouched-source claim.', '',
        '## Commands','', '```sh', '.venv/bin/python scripts/evaluate_grouped_feasibility_calibration.py --output reports/<fresh-directory>', '.venv/bin/python scripts/report_grouped_feasibility_calibration.py', '.venv/bin/python scripts/qualify_countnegative_v2.py --output results/<fresh-directory> --native-root generated/<fresh-directory>', '```', '',
        'Calibration replay creates a fresh sealed directory. Qualification invokes the real toolchain; preserve original results and use fresh paths for reruns. No production scores or frozen live-agent controllers were modified.', '',
        '## Agent diagnostics and validation', '', 'The new deterministic episode audit reconstructs the advice board from public predictions before each probe and checks temporal/hash links to paid outcomes. Nanocobs followed pairwise and utility advice on its one successful probe. Sudoku followed pairwise advice on the first two probes, departed on the third, and all three were area-infeasible. Missing historical utility advice stays explicitly unavailable. These audits improve observability; they do not establish an improved live policy.', '', 'Full repository validation: 4,592 tests and 181 subtests passed in 234.12 seconds; one intentional duplicate-ZIP warning. Ten new episode-audit tests passed separately. Countnegative qualification manifest authenticated all 82 artifacts. Frozen production controllers were unchanged.', '', '[Nanocobs decision audit](../2026-10-28-nanocobs-decision-audit-r1/README.md) · [Sudoku decision audit](../2026-10-28-sudoku-decision-audit-r1/README.md)', '', '![Budget-three results](selection-budget3.png)', '']
    (out/'README.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
