"""Show all prespecified budgets from the fixed expanded-corpus diagnostic.

No fitting, new policies or target outcomes. This is retrospective development.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from scripts.evaluate_feasibility_model_families import _paired_group_bootstrap
SOURCE=ROOT/'reports/2026-10-28-grouped-feasibility-calibration-r1'
OUTPUT=ROOT/'reports/2026-10-28-budget-tradeoffs-r1'

def build():
    c.require(not OUTPUT.exists(),'Fresh output required')
    for name,digest in c.unseal(SOURCE/'manifest.json').items():
        c.require(c.sha(SOURCE/name)==digest,'Changed source artifact')
    summary=c.unseal(SOURCE/'result.json')['summary']
    grouped=c.unseal(SOURCE/'grouped.json')
    index={(r['group'],r['policy'],r['budget']):r for r in grouped}
    groups=sorted({r['group'] for r in grouped})
    paired=[]
    for policy in ('raw_factorized','pairwise'):
        for budget in (1,2,3):
            delta={g:index[g,policy,budget]['reduction']-index[g,'merit',budget]['reduction'] for g in groups}
            result=_paired_group_bootstrap(delta)
            result['interpretation']='Positive means higher verified cycle reduction than merit on these consumed workload groups.'
            paired.append(dict(policy=policy,budget=budget,**result))
    OUTPUT.mkdir()
    report=dict(scope='Retrospective consumed development; no confirmation or promotion',
        source_manifest_sha256=c.sha(SOURCE/'manifest.json'),script_sha256=c.sha(__file__),
        workload_groups=len(groups),summary=summary,paired=paired,
        limitation='Budget-specific descriptive comparisons; no posthoc primary-endpoint switch. B3 remains the primary endpoint of the frozen experiment.')
    c.seal(OUTPUT/'report.json',report)
    labels={'raw_factorized':'Feasibility utility','pairwise':'Pairwise XGBoost','merit':'Merit','calibrated_latency':'Latency','frequency':'Frequency','random':'Random'}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,(ax,cost)=plt.subplots(1,2,figsize=(12,5.2))
    for p,color in [('raw_factorized','#c0843d'),('pairwise','#2679a8'),('merit','#327c4d'),('random','#858d97')]:
        values=sorted((r for r in summary if r['policy']==p),key=lambda r:r['budget'])
        y=[100*r['mean_cycle_reduction'] for r in values]
        ax.plot([r['budget'] for r in values],y,'o-',label=labels[p],color=color,lw=2)
        cost.plot([r['mean_measurement_seconds'] for r in values],y,'o-',label=labels[p],color=color,lw=2)
    ax.set_xticks([1,2,3]);ax.set_xlabel('Permitted candidate evaluations');ax.set_ylabel('Mean verified cycle reduction (%)')
    cost.set_xlabel('Mean charged evaluation time (seconds)');cost.set_ylabel('Mean verified cycle reduction (%)')
    for a in (ax,cost):a.set_ylim(0,2);a.grid(alpha=.18)
    ax.legend(fontsize=10);ax.set_title('Ranking depends on evaluation budget',loc='left');cost.set_title('Historical charged measurement time',loc='left')
    fig.text(.02,.025,'17 workload groups • +64 LUT4 / 12 MHz • retrospective replay • B3 remains the primary endpoint',fontsize=10)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(OUTPUT/'budget-curves.png',dpi=180);fig.savefig(OUTPUT/'budget-curves.svg');plt.close(fig)
    p=OUTPUT/'budget-curves.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n')
    lines=['# Budget-dependent selection results','',
        'The same frozen experiment has different descriptive leaders at different budgets. Feasibility utility leads at B1, pairwise XGBoost at B2, and merit/latency at B3. Reporting only B3 hides the low-budget result; selecting B1 afterward as the new primary endpoint would also be misleading. B3 remains the prespecified primary endpoint. No new model is trained here.','',
        '| Policy | B1 reduction | B2 reduction | B3 reduction |','|---|---:|---:|---:|']
    for p,label in labels.items():
        values=sorted((r for r in summary if r['policy']==p),key=lambda r:r['budget'])
        lines.append('| '+label+' | '+' | '.join(f"{100*r['mean_cycle_reduction']:.4f}%" for r in values)+' |')
    lines+=['','## Paired workload uncertainty versus merit','','Intervals resample whole workload groups. Candidate rows and five dependent random seeds do not count as independent replications. These intervals describe consumed development evidence and are not confirmatory significance tests.','','| Challenger | Budget | Difference (percentage points) | 95% interval | Wins / ties / losses |','|---|---:|---:|---:|---:|']
    for r in paired:lines.append(f"| {labels[r['policy']]} | {r['budget']} | {100*r['mean']:+.4f} | [{100*r['lower_95']:+.4f}, {100*r['upper_95']:+.4f}] | {r['wins']} / {r['ties']} / {r['losses']} |")
    lines+=['','Measurement time comes from archived paid attempts, including failed attempts, not new time saved in this replay. Source-corpus collection cost (all160 attempts) is8,657.112seconds; fitting and inference costs are separate. Methods share the public information and attempt limits. No extra historical hardware observations are available for free to ML in a real deployment.','',
        'The next forward experiment should retain all three budgets and explicitly report actual pool size. With four candidates, B3 evaluates75% of the pool; with two candidates, B2 exhausts it. These are useful engineering tests but weak evidence for large-search-space efficiency.','',
        '![Budget and cost curves](budget-curves.png)','','```sh','.venv/bin/python scripts/report_budget_tradeoffs.py','```','']
    (OUTPUT/'README.md').write_text('\n'.join(lines))
    c.seal(OUTPUT/'manifest.json',{p.name:c.sha(p) for p in OUTPUT.iterdir() if p.is_file()})

if __name__=='__main__':build()
