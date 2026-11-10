#!/usr/bin/env python3
"""Render two separate prospective coverage checks from saved actual metrics."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT=Path(__file__).resolve().parents[1]
INK='#14283F';MUTED='#596C7B';GRID='#DCE5EB';BLUE='#416C9B';TEAL='#087F83';LIGHT='#879BAE';RED='#A44635'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(first,second,development):
    a,b,d=read(first),read(second),read(development)
    if a['schema']!='isaforge-targeted-coverage-v1' or b['schema']!='isaforge-budget-preserving-coverage-v1':raise ValueError('Frozen study schemas required')
    if any(m['count']!=40 for m in a['models'].values()) or any(m['count']!=32 for m in b['models'].values()):raise ValueError('Separate complete40/32 cohorts required')
    for result in (a,b):
        baseline=result['models']['base']
        if any(model['caps']!=baseline['caps'] for model in result['models'].values()):raise ValueError('Expected unchanged cap counts in these saved checks')
    return a,b,d
def draw(ax,models,names,labels,colors):
    values=[models[n]['mae_lut4'] for n in names];ys=list(range(len(names)))[::-1]
    ax.barh(ys,values,height=.48,color=colors,zorder=3)
    ax.set_yticks(ys,labels,fontsize=11,color=INK);ax.tick_params(axis='y',length=0,pad=10)
    ax.tick_params(axis='x',length=0,pad=7,labelsize=10,colors=MUTED)
    ax.set_xlim(0,max(values)*1.25);ax.set_ylim(-.55,len(names)-.45)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4));ax.xaxis.grid(True,color=GRID,lw=.8,zorder=0)
    ax.spines[['top','right','left']].set_visible(False);ax.spines['bottom'].set_color(GRID)
    for yy,value,color in zip(ys,values,colors):ax.text(value+max(values)*.035,yy,f'{value:.2f}',va='center',fontsize=12,fontweight='bold',color=color)
def budgets(fig,left,title,models,candidate):
    b,c=models['base'],models[candidate]
    fig.text(left,.430,title,fontsize=10.5,fontweight='bold',color=INK)
    columns=(left,left+.105,left+.255)
    for x,label in zip(columns,('Cap LUT4','False accept','False reject')):fig.text(x,.391,label,fontsize=9.5,color=MUTED)
    for i,cap in enumerate((32,64,128)):
        y=.352-i*.035
        fig.text(columns[0],y,str(cap),fontsize=10.5,color=INK)
        for x,key in zip(columns[1:],('false_accept','false_reject')):
            fig.text(x,y,f"{b['caps'][str(cap)][key]} → {c['caps'][str(cap)][key]}",fontsize=11,color=INK,fontweight='bold')
    fig.text(left,.222,f"Worst underprediction: {b['maximum_underprediction_lut4']:.2f} → {c['maximum_underprediction_lut4']:.2f} LUT4",fontsize=10,color=MUTED)


def render(first,second,development,audit_path,output):
    a,b,d=load(first,second,development)
    audit=read(audit_path)
    if audit['status']!='pass':raise ValueError('Completed independent audit required')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
    fig=plt.figure(figsize=(14.6,8.2),facecolor='white')
    fig.text(.055,.950,'Targeted examples improve point estimates',fontsize=23,fontweight='bold',color=INK)
    fig.text(.055,.905,'Fixed 217 features · 64 new training circuits · two separately frozen synthetic cohorts · lower MAE is better',fontsize=11.5,color=MUTED)
    fig.text(.055,.847,'A  First prospective check · 40 circuits',fontsize=14,fontweight='bold',color=INK)
    fig.text(.555,.847,'B  New policy check · 32 other circuits',fontsize=14,fontweight='bold',color=INK)
    fig.text(.055,.808,'Mean absolute LUT4 error · three frozen point predictors',fontsize=10.5,color=MUTED)
    fig.text(.555,.808,'Mean absolute LUT4 error · zero additional fits',fontsize=10.5,color=MUTED)
    draw(fig.add_axes([.168,.582,.285,.190]),a['models'],['base','augmented217','scoped_augmented217'],['Base','Augmented','Scoped'],[BLUE,LIGHT,TEAL])
    draw(fig.add_axes([.685,.582,.270,.190]),b['models'],['base','budget_preserving_coverage'],['Base','Guarded policy'],[BLUE,TEAL])
    am=a['models'];bm=b['models'];key='budget_preserving_coverage'
    fig.text(.055,.533,f"MAPE: {am['base']['positive_mape_percent']:.2f}% → {am['augmented217']['positive_mape_percent']:.2f}% / {am['scoped_augmented217']['positive_mape_percent']:.2f}% (augmented / scoped)",fontsize=10,color=MUTED)
    fig.text(.555,.533,f"MAPE: {bm['base']['positive_mape_percent']:.2f}% → {bm[key]['positive_mape_percent']:.2f}% · MAE {(bm[key]['mae_lut4']/bm['base']['mae_lut4']-1)*100:.2f}%",fontsize=10,color=MUTED)
    fig.text(.055,.496,'Fresh gate passed; retained development budget gate failed.',fontsize=10.5,fontweight='bold',color=RED)
    status='passed' if b['scoped_experimental_eligibility'] else 'failed'
    fig.text(.555,.496,f'Development and new fresh gates {status}; explicit experiment only.',fontsize=10.5,fontweight='bold',color=TEAL if status=='passed' else RED)
    fig.lines.append(plt.Line2D([.055,.955],[.466,.466],transform=fig.transFigure,color=GRID,lw=1))
    budgets(fig,.055,'Unchanged fresh counts · base → scoped (augmented also identical)',am,'scoped_augmented217')
    budgets(fig,.555,'Unchanged fresh counts · base → guarded policy',bm,key)
    fig.lines.append(plt.Line2D([.055,.955],[.192,.192],transform=fig.transFigure,color=GRID,lw=1))
    fig.text(.055,.157,'Guarded policy: p = min(max(b, s), nextcap(b))',fontsize=12,fontweight='bold',color=INK)
    fig.text(.555,.157,'b = base; s = scoped; nextcap = smallest 32/64/128 ≥ b, else ∞.',fontsize=10,color=MUTED)
    fig.text(.055,.119,'The policy exactly preserves base decisions at these caps, including existing mistakes, and never lowers a base point estimate.',fontsize=10,color=MUTED)
    stress=d['panels']['arithmetic-stress']
    template=audit['fresh_template_metrics']['signed_dual_arithmetic']
    fig.text(.055,.086,f"Regressions: retained 32-case stress MAE {stress['base']['mae_lut4']:.2f} → {stress[key]['mae_lut4']:.2f} / MAPE {stress['base']['positive_mape_percent']:.2f}% → {stress[key]['positive_mape_percent']:.2f}%; new four-case signed dual arithmetic MAE {template['base']['mae_lut4']:.2f} → {template[key]['mae_lut4']:.2f}.",fontsize=9.3,color=RED)
    fig.text(.055,.055,'First 40-case test is consumed development for the later policy. Separate cohorts; no learning curve. Base remains the default.',fontsize=9.1,color=MUTED)
    fig.text(.055,.025,'Synthetic circuit evidence only; no calibrated safety, application-transfer, timing, power or full-CPU guarantee.',fontsize=9.1,color=MUTED)
    output.mkdir(parents=True,exist_ok=True);paths=[]
    provenance=f'First metrics SHA256 {sha(first)}; second metrics SHA256 {sha(second)}; development SHA256 {sha(development)}; independent audit SHA256 {sha(audit_path)}. Separate cohorts. Zero fits or native jobs during rendering.'
    for ext in ('svg','png','pdf'):
        path=output/f'targeted-coverage.{ext}'
        metadata={'Title':'Targeted coverage: two separate prospective synthetic checks','Creator':'scripts/render_targeted_coverage.py; Matplotlib',
                  'Subject' if ext=='pdf' else 'Description':provenance}
        fig.savefig(path,dpi=220,facecolor='white',metadata=metadata);paths.append(path)
    plt.close(fig);return paths


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first',type=Path,default=ROOT/'results/targeted-coverage/fresh-metrics.json')
    parser.add_argument('--second',type=Path,default=ROOT/'results/budget-preserving-coverage/fresh-metrics.json')
    parser.add_argument('--development',type=Path,default=ROOT/'results/budget-preserving-coverage/development-metrics.json')
    parser.add_argument('--audit',type=Path,default=ROOT/'results/budget-preserving-coverage/audit.json')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/figures/research')
    args=parser.parse_args()
    for path in render(args.first,args.second,args.development,args.audit,args.output):print(path.resolve())
