#!/usr/bin/env python3
"""Figures for the fixed fitting-only V7 semantic ablation; no holdout claim."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

VIEWS=('base','bit','affine','both','legacy_original','legacy_rewritten')
LABELS=('Mapping baseline (217)','+ bit descriptors (225)','+ affine descriptors (225)',
        '+ both blocks (233)','+ old semantics on original (336)','+ old semantics on rewrite (336)')
COLORS=('#718b9c','#599bab','#659a79','#145f95','#b98759','#9a6c99')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.prepared;out=args.output;out.mkdir(parents=True,exist_ok=True)
    summary=json.loads((root/'fit/summary.json').read_text())
    diagnostic=json.loads((root/'input-diagnostics.json').read_text())
    plan=json.loads((root/'plan.json').read_text());seeds=plan['seeds']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'isaforge-v7-development'})
    figures=[]
    def save(fig,name,caption):
        for extension in ('png','svg','pdf'):
            metadata={'Date':None} if extension=='svg' else {'CreationDate':None,'ModDate':None} if extension=='pdf' else {}
            fig.savefig(out/f'{name}.{extension}',dpi=300,bbox_inches='tight',metadata=metadata)
        plt.close(fig);svg=(out/f'{name}.svg').read_text()
        figures.append('<figure>'+svg[svg.index('<svg'):]+'<figcaption>'+caption+
            f' <a href="{name}.pdf">PDF</a> · <a href="{name}.svg">SVG</a></figcaption></figure>')
    fig,(ax,delta_ax)=plt.subplots(2,1,figsize=(10,6.4),layout='constrained',gridspec_kw={'height_ratios':[3,1]})
    means=[summary['by_view'][v]['macro_mae_mean'] for v in VIEWS]
    deviations=[summary['by_view'][v]['macro_mae_sample_sd'] for v in VIEWS]
    ax.barh(range(6),means,color=COLORS,xerr=deviations,capsize=3,error_kw={'elinewidth':1})
    ax.set_yticks(range(6),LABELS);ax.invert_yaxis();ax.set_xlim(0,max(means)*1.2)
    for i,value in enumerate(means):ax.text(value+deviations[i]+max(means)*.015,i,f'{value:.4f}',va='center')
    ax.set_xlabel('Nine-stratum macro OOF MAE (LUT4), mean ± seed SD')
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    delta=summary['paired_comparisons']['both_minus_base']['values_lut4']
    delta_ax.scatter(delta,range(3),color=COLORS[3]);delta_ax.axvline(0,color='#555',ls='--',lw=1)
    delta_ax.set_yticks(range(3),[str(s) for s in seeds]);delta_ax.set_xlabel('Declared primary: both blocks − baseline (LUT4); negative favors new blocks')
    fig.suptitle('V7 development only · 1,665 fitting circuits · five fixed group folds\nThree algorithm seeds share the same data; error bars are not population intervals',fontsize=11)
    save(fig,'v7-development-primary','All six fixed views and three paired seeds. Original fitting folds remain unchanged. These are consumed-data development scores, not an independent test. Seed SD describes estimator sensitivity only.')
    strata=sorted(summary['by_view']['base']['by_stratum_mean_mae'])
    fig,axes=plt.subplots(3,3,figsize=(12,9),layout='constrained')
    for ax,stratum in zip(axes.flat,strata):
        values=[summary['by_view'][v]['by_stratum_mean_mae'][stratum] for v in VIEWS]
        ax.bar(range(6),values,color=COLORS)
        ax.set_xticks(range(6),['Base','Bit','Affine','Both','Old','Rewrite'],fontsize=8,rotation=30)
        ax.set_ylim(0,max(max(values)*1.2,.1));ax.set_title(stratum.replace('_',' ').capitalize(),loc='left',fontsize=10)
        ax.set_ylabel('MAE (LUT4)');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('All nine fitting strata · three-seed mean MAE\nPanel scales differ; Old / Rewrite append the same 119 legacy semantic descriptors',fontsize=11)
    save(fig,'v7-development-strata','All nine original fitting strata, including workload formulas, with six fixed views. Panel scales differ. Every circuit, zero target and failure remains in the underlying scores.')
    body='<p>ISAForge · consumed-data development</p><h1>Do proved semantic descriptors improve the fixed mapping model?</h1>'
    body+=f'<p>The declared primary mean difference is <strong>{np.mean(delta):+.4f} LUT4</strong> (both blocks − baseline). Negative favors the new descriptors. All {summary["fits_completed"]} completed fits are recorded; identical full matrices may reuse predictions. No new target labels, model tuning or independent evaluation is performed.</p>'
    body+=''.join(figures)
    body+='<h2>Error tradeoffs across every view</h2><p>Each entry below is the mean of the three seed-specific metrics, not a pooled ensemble prediction. MAPE uses 1,413 positive targets; all 252 zero targets remain in MAE.</p><table><tr><th>View</th><th>Positive MAPE (%)</th><th>Zero MAE (LUT4)</th><th>95th-percentile absolute error (LUT4)</th></tr>'
    for view,label in zip(VIEWS,LABELS):
        records=[summary['scores'][view][str(seed)]['all_rows'] for seed in seeds]
        means=[np.mean([record[key] for record in records]) for key in ('positive_mape_percent','zero_mae_lut4','p95_absolute_error_lut4')]
        body+='<tr><td>'+html.escape(label)+'</td>'+''.join(f'<td>{value:.4f}</td>' for value in means)+'</tr>'
    body+='</table><p>The declared primary improves four of nine strata. Multiplication supplies more than the net gain, offsetting regressions elsewhere. Neither lower mean error nor a lower observed development score establishes better instruction selection.</p>'
    body+='<h2>Input evidence and limits</h2><p>Neither new bit-correlation identity occurs in the original fitting corpus. Any improvement cannot demonstrate learning those missing rewrite patterns. Affine rewriting, known-bit summaries and legacy normalization must be distinguished. Revised models need untouched application-family evaluation.</p>'
    body+='<pre>'+html.escape(json.dumps({k:{n:v for n,v in r.items() if n in ('changed_rows','statuses','crossfold_component_count','crossfold_rows','new_crossfold_component_count','new_crossfold_rows')}
        for k,r in diagnostic['by_rewrite_mode'].items()},indent=2))+'</pre>'
    body+='<h2>Complete evidence</h2><p><a href="summary.json">All scores, tails, caps and paired differences</a> · <a href="input-diagnostics.json">All feature prevalence and cross-fold identities</a> · <a href="provenance.json">Figure source hashes</a></p>'
    css='body{font:16px/1.6 system-ui;color:#20394b;background:#f4f7f9}main{max-width:1150px;margin:auto;padding:36px;background:white}h1{line-height:1.2}figure{margin:24px 0}figure svg{width:100%;height:auto}figcaption{font-size:13px;color:#536d7e}pre{font-size:12px;overflow:auto;background:#edf3f7;padding:16px}a{color:#096b9c}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:8px;text-align:right;border-bottom:1px solid #d6e1e8}th:first-child,td:first-child{text-align:left}'
    (out/'report.html').write_text('<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V7 fitting-only development</title><style>'+css+'</style><main>'+body+'</main></html>')
    for name,value in [('summary.json',summary),('input-diagnostics.json',diagnostic)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'summary_sha256':hashlib.sha256((root/'fit/summary.json').read_bytes()).hexdigest(),
        'pre_score_freeze_sha256':hashlib.sha256((root/'pre-score-freeze.json').read_bytes()).hexdigest()},indent=2)+'\n')
    print(out/'report.html')


if __name__=='__main__':main()
