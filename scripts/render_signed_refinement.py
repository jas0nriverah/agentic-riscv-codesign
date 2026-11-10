#!/usr/bin/env python3
"""Render separate consumed repairs and sealed fresh40 refinement results."""
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
SELECTED='signed_refinement';CURRENT='incumbent_current'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bars(ax,models,names,labels,metric,suffix=''):
    values=[models[n][metric] for n in names];ys=(2,1,0);colors=(BLUE,LIGHT,TEAL)
    ax.barh(ys,values,height=.52,color=colors,zorder=3)
    ax.set_yticks(ys,labels,fontsize=10,color=INK);ax.tick_params(axis='y',length=0,pad=7)
    ax.tick_params(axis='x',length=0,pad=5,labelsize=9,colors=MUTED)
    ax.set_xlim(0,max(values)*1.3);ax.set_ylim(-.6,2.6)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4));ax.xaxis.grid(True,color=GRID,lw=.8,zorder=0)
    ax.spines[['top','right','left']].set_visible(False);ax.spines['bottom'].set_color(GRID)
    for yy,v,c in zip(ys,values,colors):ax.text(v+max(values)*.035,yy,f'{v:.2f}{suffix}',va='center',fontsize=11,fontweight='bold',color=c)

def render(development,fresh,audit_path,output):
    dev,held,audit=read(development),read(fresh),read(audit_path)
    if held['schema']!='isaforge-signed-refinement-v1' or audit['status']!='pass':raise ValueError('Sealed study and independent audit required')
    if held['selected_candidate']!=SELECTED or dev['selected_candidate']!=SELECTED:raise ValueError('Expected frozen primary selection')
    names=('base',CURRENT,SELECTED)
    if any(held['models'][n]['count']!=40 for n in names):raise ValueError('Matched complete fresh40 required')
    if any(held['models'][n]['caps']!=held['models']['base']['caps'] for n in names):raise ValueError('Expected exact unchanged cap counts')
    groups=[(dev['named_regressions']['research192'],('earlier_guard',CURRENT,SELECTED),('Earlier guard','Current','Refined')),
        (dev['named_regressions']['signed_add_boolean4'],names,('Base','Current','Refined')),
        (held['models'],names,('Base','Current','Refined'))]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
    fig=plt.figure(figsize=(16,10),facecolor='white')
    fig.text(.045,.953,'Narrow signed coverage repairs two retained tradeoffs',fontsize=24,fontweight='bold',color=INK)
    fig.text(.045,.913,'32 new training circuits · one fixed 300-tree fit · signed data/Boolean AST routes · four stored forests in the composite policy',fontsize=11.5,color=MUTED)
    titles=('A  Consumed research panel · 192','B  Consumed signed add/Boolean · 4','C  Independent fresh check · 40')
    for left,title,(models,keys,labels) in zip((.045,.365,.685),titles,groups):
        fig.text(left,.853,title,fontsize=13,fontweight='bold',color=INK)
        fig.text(left,.817,'MAE · LUT4 · lower is better',fontsize=10.5,color=MUTED)
        bars(fig.add_axes([left+.078,.648,.216,.145]),models,keys,labels,'mae_lut4')
        fig.text(left,.600,'Positive-target MAPE · lower is better',fontsize=10.5,color=MUTED)
        bars(fig.add_axes([left+.078,.432,.216,.145]),models,keys,labels,'positive_mape_percent','%')
    fig.text(.045,.390,'All seven retained panels: MAE, MAPE and worst underprediction no worse than current; prior fixes retained.',fontsize=10,color=TEAL,fontweight='bold')
    eligible=held['scoped_experimental_eligibility']
    fig.text(.735,.390,'Frozen gates '+('passed.' if eligible else 'failed.'),fontsize=10.5,fontweight='bold',color=TEAL if eligible else RED)
    fig.lines.append(plt.Line2D([.045,.965],[.369,.369],transform=fig.transFigure,color=GRID,lw=1))
    fig.text(.045,.338,'Fresh budget mistakes are unchanged: base = current = refined',fontsize=12,fontweight='bold',color=INK)
    for x,label in zip((.045,.175,.330,.500),('Cap · LUT4','False accept','False reject','Predicted / actual feasible')):fig.text(x,.309,label,fontsize=10,color=MUTED)
    for i,cap in enumerate((32,64,128)):
        row=held['models']['base']['caps'][str(cap)];y=.281-i*.027
        for x,value in zip((.045,.175,.330,.500),(str(cap),str(row['false_accept']),str(row['false_reject']),f"{row['predicted_accept']} / {row['actual_accept']}")):
            fig.text(x,y,value,fontsize=11,fontweight='bold',color=RED if row['false_accept'] and x==.175 else INK)
    fig.text(.685,.338,'Worst underprediction · LUT4',fontsize=12,fontweight='bold',color=INK)
    fig.text(.685,.301,' → '.join(f"{held['models'][n]['maximum_underprediction_lut4']:.2f}" for n in names),fontsize=16,fontweight='bold',color=INK)
    fig.text(.685,.274,'Base → current → refined',fontsize=10,color=MUTED)
    fig.text(.685,.243,'Points stay ≥ base; decisions at 32 / 64 / 128',fontsize=10,color=MUTED)
    fa=held['models']['base']['caps']
    fig.text(.685,.219,f"retain {fa['64']['false_accept']} false accept at 64 and {fa['128']['false_accept']} at 128.",fontsize=10,fontweight='bold',color=RED)
    fig.lines.append(plt.Line2D([.045,.965],[.197,.197],transform=fig.transFigure,color=GRID,lw=1))
    templates=audit['fresh_template_metrics_descriptive'];trade=templates['heldout_compound_signed_add_xor']
    fig.text(.045,.167,f"New subgroup regression: compound signed add/XOR (4 cases), current → refined MAE {trade[CURRENT]['mae_lut4']:.3f} → {trade[SELECTED]['mae_lut4']:.3f}; MAPE {trade[CURRENT]['positive_mape_percent']:.3f}% → {trade[SELECTED]['positive_mape_percent']:.3f}%.",fontsize=10,color=RED)
    offset=templates['control_signed_variable_offset_sub'];static=templates['control_static_signed_mixed']
    fig.text(.045,.139,f"Inherited controls, earlier guard → current = refined: offset/sub MAE {offset['earlier_guard']['mae_lut4']:.2f} → {offset[SELECTED]['mae_lut4']:.2f}, MAPE {offset['earlier_guard']['positive_mape_percent']:.2f}% → {offset[SELECTED]['positive_mape_percent']:.2f}%; static-signed mixed MAE {static['earlier_guard']['mae_lut4']:.2f} → {static[SELECTED]['mae_lut4']:.2f}, MAPE {static['earlier_guard']['positive_mape_percent']:.2f}% → {static[SELECTED]['positive_mape_percent']:.2f}%.",fontsize=9.7,color=RED)
    fig.text(.045,.105,'Primary selected on consumed development data before fresh labels; fallback reported separately. Four stored forests and structural routing form the policy.',fontsize=9.8,color=MUTED)
    fig.text(.045,.077,'Earlier 192 / 327 / 32 / 40 / 40 / 32 / 40 panels are consumed. Fresh40 is separate; no learning curve or universal subgroup improvement is implied.',fontsize=9.8,color=MUTED)
    fig.text(.045,.049,'Experimental isolated iCE40 LUT4 points only. No calibrated safety, CPU, timing, power or application-transfer guarantee. Base stays the default.',fontsize=10,color=MUTED)
    output.mkdir(parents=True,exist_ok=True);paths=[]
    provenance='; '.join(f'{p.name} SHA256 {sha(p)}' for p in (development,fresh,audit_path))+'. Separate cohorts; zero fits or native jobs in rendering.'
    for ext in ('svg','png','pdf'):
        path=output/f'signed-refinement.{ext}';meta={'Title':'Narrow signed coverage: two consumed tradeoff repairs and independent fresh40','Creator':'scripts/render_signed_refinement.py; Matplotlib','Subject' if ext=='pdf' else 'Description':provenance}
        fig.savefig(path,dpi=200,facecolor='white',metadata=meta);paths.append(path)
    plt.close(fig);return paths

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--development',type=Path,default=ROOT/'results/signed-refinement/development-metrics.json')
    p.add_argument('--fresh',type=Path,default=ROOT/'results/signed-refinement/fresh-metrics.json')
    p.add_argument('--audit',type=Path,default=ROOT/'results/signed-refinement/audit.json')
    p.add_argument('--output',type=Path,default=ROOT/'docs/figures/research')
    a=p.parse_args()
    for path in render(a.development,a.fresh,a.audit,a.output):print(path.resolve())
