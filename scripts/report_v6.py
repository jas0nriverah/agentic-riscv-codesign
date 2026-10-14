#!/usr/bin/env python3
"""Render the complete frozen V6 synthetic test without selecting a winner."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ORDER=('v4_frozen','masterrtl_fixed','sog_tuned','original_graph','dual_graph','dual_semantics','mapping_v6','router_v6')
LABELS=('V4 frozen','Fixed MasterRTL recipe','Equally tuned SOG','SOG + original graph','SOG + dual graphs','Dual graphs + semantics','V6: dual graphs + mapping','V6: fixed multiply router')
COLORS=('#99a4ae','#b78354','#778b9b','#68a6b3','#398e87','#6d80ab','#145f95','#a76696')


def table(headers,rows):
    def cell(tag,value):return '<'+tag+'>'+html.escape(str(value))+'</'+tag+'>'
    return '<div class="table"><table><tr>'+''.join(cell('th',h) for h in headers)+'</tr>'+''.join('<tr>'+''.join(cell('td',v) for v in row)+'</tr>' for row in rows)+'</table></div>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();data=json.loads(args.evaluation.read_text());out=args.output;out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'pdf.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'isaforge-v6-frozen-test'})
    figures=[]
    def save(fig,name,caption):
        for ext in ('png','svg','pdf'):
            metadata={'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else {}
            fig.savefig(out/f'{name}.{ext}',dpi=300,bbox_inches='tight',metadata=metadata)
        plt.close(fig);svg=(out/f'{name}.svg').read_text()
        figures.append('<figure>'+svg[svg.index('<svg'):]+'<figcaption>'+caption+f' <a href="{name}.pdf">PDF</a> · <a href="{name}.svg">SVG</a></figcaption></figure>')
    models=data['models'];pair=data['primary_paired_comparison']
    values=[models[n]['macro_stratum_mae_lut4'] for n in ORDER]
    fig,(ax,contrast)=plt.subplots(2,1,figsize=(10,7.3),layout='constrained',gridspec_kw={'height_ratios':[4,1]})
    ax.barh(range(len(ORDER)),values,color=COLORS);ax.set_yticks(range(len(ORDER)),LABELS);ax.invert_yaxis()
    ax.set_xlim(0,max(max(values)*1.2,.1));ax.set_xlabel('Equal-weight mean of eight stratum MAEs (LUT4)')
    ax.set_title('Fresh V6 synthetic test: all frozen predictors',loc='left')
    for i,v in enumerate(values):ax.text(v+max(max(values),.1)*.015,i,f'{v:.3f}',va='center')
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    delta=pair['macro_stratum_mae_difference_lut4'];interval=pair['descriptive_stratified_component_bootstrap_95_interval']
    contrast.hlines(0,*interval,color=COLORS[-2],lw=3)
    contrast.scatter([delta],[0],color=COLORS[-2],s=42,zorder=3)
    contrast.axvline(0,color='#56616c',ls='--',lw=1)
    span=max(interval[1]-interval[0],abs(delta)*.2,.1)
    contrast.set_xlim(min(interval[0],0)-span*.15,max(interval[1],0)+span*.15)
    contrast.set_ylim(-.6,.6);contrast.set_yticks([])
    contrast.set_xlabel('Primary MAE difference (LUT4): mapping − dual graph; negative favors mapping')
    contrast.set_title(f'Fixed primary contrast: {delta:+.3f}  |  descriptive 95% interval [{interval[0]:+.3f}, {interval[1]:+.3f}]',loc='left',fontsize=10)
    fig.suptitle('192 test circuits · 96 structural components · 8 fixed synthetic strata',fontsize=12)
    save(fig,'v6-primary','All 192 original circuits, eight strata and 96 two-variant components. The interval uses 10,000 paired whole-component draws within fixed strata and conditions on this synthetic grammar. The fixed primary comparison is V6 mapping minus unchanged dual graph. The router and other controls are secondary; no observed winner replaces the primary endpoint.')
    strata=sorted(models['mapping_v6']['by_stratum']);views=('dual_graph','dual_semantics','mapping_v6','router_v6')
    fig,axes=plt.subplots(2,4,figsize=(14,7),layout='constrained')
    fig.suptitle('V6 test by stratum: 24 circuits / 12 components per panel\nPanel scales differ; all eight strata retained',fontsize=12)
    for ax,s in zip(axes.flat,strata):
        vals=[models[n]['by_stratum'][s]['mae_lut4'] for n in views]
        ax.bar(range(4),vals,color=[COLORS[ORDER.index(n)] for n in views]);ax.set_ylim(0,max(max(vals)*1.25,.1))
        ax.set_xticks(range(4),['Dual\ngraph','Full\nsemantics','V6\nmapping','V6\nrouter'],fontsize=8)
        for i,v in enumerate(vals):ax.text(i,v+max(max(vals),.1)*.025,f'{v:.2f}',ha='center',fontsize=8)
        ax.set_title(s.replace('_',' ').capitalize(),loc='left',fontsize=11);ax.set_ylabel('MAE (LUT4)')
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    save(fig,'v6-strata','Every declared stratum is retained. Vertical scales differ between panels. Each stratum contains 24 formulas in 12 separate structural components. These synthetic grammar families are not independently sourced applications.')
    fig,axes=plt.subplots(1,2,figsize=(11,5.8),layout='constrained',sharex=True,sharey=True)
    palette=plt.get_cmap('tab10')
    for ax,name,title in zip(axes,('dual_graph','mapping_v6'),('Unchanged dual-graph control','V6 mapping')):
        errors=models[name]['candidate_errors']
        for i,stratum in enumerate(strata):
            selected=[r for r in errors if r['stratum']==stratum]
            ax.scatter([r['lut4_count'] for r in selected],[r['predicted_lut4'] for r in selected],
                       s=22,alpha=.72,color=palette(i),label=stratum.replace('_',' '),edgecolors='none')
        ax.plot([0,3500],[0,3500],ls='--',color='#555',lw=1,zorder=0)
        ax.set_xscale('symlog',linthresh=1);ax.set_yscale('symlog',linthresh=1)
        ax.set_xlim(-.1,3500);ax.set_ylim(-.1,3500);ax.set_aspect('equal')
        ticks=[0,1,10,100,1000];ax.set_xticks(ticks,[str(v) for v in ticks]);ax.set_yticks(ticks,[str(v) for v in ticks])
        ax.set_xlabel('Measured isolated LUT4');ax.set_title(title,loc='left');ax.grid(alpha=.13)
    axes[0].set_ylabel('Predicted isolated LUT4')
    worst=max(models['mapping_v6']['candidate_errors'],key=lambda r:r['absolute_error_lut4'])
    axes[1].annotate(f"{worst['lut4_count']:,.0f} measured\n{worst['predicted_lut4']:,.0f} predicted",xy=(worst['lut4_count'],worst['predicted_lut4']),xytext=(12,1700),
                     fontsize=8,arrowprops={'arrowstyle':'-','color':'#555'},bbox={'facecolor':'white','edgecolor':'none','alpha':.9})
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=4,fontsize=8,frameon=False)
    fig.suptitle('All 192 V6 test circuits · equal axes · dashed line: exact prediction\nLinear scale from 0 to 1, logarithmic above 1; all six zero targets retained',fontsize=11)
    save(fig,'v6-predictions','Measured versus predicted original-circuit LUT4 on identical axes, retaining every zero and outlier. The annotated mapping overprediction remains in all metrics. Colors identify the eight fixed strata; this is a descriptive error view, not a new endpoint.')
    bound_names=[n for n in ORDER if 'upper_bound' in models[n]]
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained',sharey=True)
    fig.suptitle('V6 test: 192 circuits / 96 components · dashed line: nominal 90%\nV6 uses fresh calibration; controls retain their earlier margins',fontsize=11)
    for ax,key,title in zip(axes,('candidate_coverage','whole_component_coverage'),('Candidate coverage','Complete-component coverage')):
        vals=[100*models[n]['upper_bound'][key] for n in bound_names]
        ax.barh(range(len(bound_names)),vals,color=[COLORS[ORDER.index(n)] for n in bound_names])
        ax.set_xlim(0,108);ax.axvline(90,ls='--',color='#555',lw=1)
        ax.set_xlabel('Observed coverage (%)');ax.set_title(title,loc='left')
        for i,v in enumerate(vals):ax.text(v+1,i,f'{v:.1f}',va='center',fontsize=9,bbox={'facecolor':'white','edgecolor':'none','pad':1})
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(bound_names)),[LABELS[ORDER.index(n)] for n in bound_names]);axes[0].invert_yaxis()
    save(fig,'v6-coverage','Dashed line: nominal 90%. Only the two V6 predictors use the fresh calibration components; old controls retain their original V5 margins. Observed coverage does not guarantee exchangeability or application coverage. Null bounds are unbounded; finite fractions are reported below.')
    fmt=lambda x:'unavailable' if x is None else f'{x:.3f}'
    delta=pair['macro_stratum_mae_difference_lut4'];interval=pair['descriptive_stratified_component_bootstrap_95_interval']
    body='<p class="eyebrow">ISAForge • Frozen V6 validation</p><h1>Testing mapping-aware features on new structural families</h1>'
    body+=f'<p>The fixed primary difference is <strong>{delta:+.3f} LUT4</strong> (mapping − dual graph). Its descriptive paired component interval is <strong>[{interval[0]:+.3f}, {interval[1]:+.3f}]</strong>. Negative favors mapping. The interval conditions on the eight strata and synthetic grammar; it is not evidence of general application or CPU superiority.</p>'
    body+=''.join(figures)
    body+='<h2>All point metrics</h2>'+table(['Predictor','Macro MAE','Pooled MAE','RMSLE','Positive MAPE (%)','Positive / zero targets','Worst underprediction'],[[label,fmt(models[n]['macro_stratum_mae_lut4']),fmt(models[n]['mae_lut4']),fmt(models[n]['rmsle']),fmt(models[n]['positive_mape_percent']),f"{models[n]['positive_count']} / {models[n]['zero_count']}",fmt(models[n]['maximum_underprediction_lut4'])] for n,label in zip(ORDER,LABELS)])
    body+='<h2>Bounds and their limits</h2>'+table(['Predictor','Finite bounds (%)','Candidate coverage (%)','Component coverage (%)','Mean slack','Worst slack'],[[LABELS[ORDER.index(n)],fmt(100*models[n]['upper_bound']['finite_bound_fraction']),fmt(100*models[n]['upper_bound']['candidate_coverage']),fmt(100*models[n]['upper_bound']['whole_component_coverage']),fmt(models[n]['upper_bound']['mean_slack_lut4']),fmt(models[n]['upper_bound']['minimum_slack_lut4'])] for n in bound_names])
    largest=sorted(models['mapping_v6']['candidate_errors'],key=lambda r:r['absolute_error_lut4'],reverse=True)[:10]
    body+='<h2>Largest primary-model errors</h2>'+table(['Stratum','Formula','Measured LUT4','Prediction','Absolute error'],[[r['stratum'],r['formula'],r['lut4_count'],fmt(r['predicted_lut4']),fmt(r['absolute_error_lut4'])] for r in largest])
    body+='<h2>Evidence boundaries</h2><p>Point models and all calibration/test predictions precede calibration release. The calibrated artifacts and test bounds are separately committed before test release. No model, gate, margin rule, input or comparator is selected after test outcomes. All original-RTL measurements and failures remain. Structural grouping is sufficient but does not prove complete functional nonequivalence. Novelty filtering and the synthetic grammar limit exchangeability and transfer claims.</p><p><a href="report-data.json">Complete metrics, caps and errors</a> · <a href="provenance.json">Report provenance</a></p>'
    css='body{font:16px/1.6 system-ui;background:#f4f7f9;color:#20394b}main{max-width:1200px;margin:auto;padding:38px;background:white}h1{font-size:34px;line-height:1.2}h2{color:#185372;margin-top:34px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:1px}figure{margin:28px 0}figure svg{width:100%;height:auto}figcaption{font-size:13px;color:#536d7e}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px;border-bottom:1px solid #dce4ea;text-align:left;overflow-wrap:anywhere}th{background:#edf4f8}a{color:#096b9c}'
    (out/'report.html').write_text('<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge V6 frozen test</title><style>'+css+'</style><main>'+body+'</main></html>')
    (out/'report-data.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({'evaluation_sha256':hashlib.sha256(args.evaluation.read_bytes()).hexdigest(),'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'point_freeze_sha256':data['point_freeze_sha256'],'calibration_freeze_sha256':data['calibration_freeze_sha256']},indent=2)+'\n')
    print(out/'report.html')

if __name__=='__main__':main()
