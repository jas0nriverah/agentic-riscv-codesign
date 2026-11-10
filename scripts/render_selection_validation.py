#!/usr/bin/env python3
"""Plot completed stability and fresh synthetic validation; zero fits/native jobs.

The two cohorts remain separate. Seed repeats are descriptive, and the fresh
cohort is a bounded synthetic template check rather than an application test.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT=Path(__file__).resolve().parents[1]
VIEWS=('mapping217','original336','selected128')
LABELS=('Mapping 217','Original 336','Selected 128')
COLORS=('#416C9B','#879BAE','#087F83')
INK='#14283F';MUTED='#596C7B';GRID='#DCE5EB';ALERT='#A44635';GOOD='#087F83'


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mean(values):return sum(values)/len(values)


def load_sources(stability_path,fresh_path):
    stability,fresh=read(stability_path),read(fresh_path)
    if stability.get('schema')!='isaforge-selection-stability-v1' or stability.get('fits_completed')!=33:
        raise ValueError('Completed33-fit stability summary required')
    if stability['protocol_sha256']!=sha(stability_path.with_name('protocol.json')):
        raise ValueError('Stability protocol hash differs')
    completion=read(fresh_path.with_name('completion.json'))
    if completion.get('complete') is not True or completion.get('label_count')!=40 or completion.get('fits')!=0:
        raise ValueError('Complete40-row fresh check with zero fits required')
    candidates=read(fresh_path.with_name('candidates.json'))
    template_counts=Counter(row['template'] for row in candidates)
    if len(candidates)!=40 or len(template_counts)!=5 or set(template_counts.values())!={8}:
        raise ValueError('Expected five equally weighted synthetic templates')
    if set(fresh['models'])!=set(VIEWS):raise ValueError('Fresh comparators differ')
    for models in [*stability['per_seed'].values(),fresh['models']]:
        if set(models)!=set(VIEWS):raise ValueError('Matched comparators required')
        for view,row in models.items():
            for key in ('positive_mape_percent','maximum_underprediction_lut4'):
                if not isinstance(row[key],(int,float)) or not math.isfinite(row[key]) or row[key]<0:
                    raise ValueError('Nonfinite metric: '+view+'/'+key)
    for row in fresh['models'].values():
        if row['count']!=40 or not math.isclose(row['mae_lut4'],mean(list(row['template_mae_lut4'].values())),abs_tol=1e-12):
            raise ValueError('Fresh MAE/template weighting differs')
    return stability,fresh


def draw_mae(ax,values,seed_values=None):
    ys=[2,1,0];bound=max(values)*1.22
    ax.barh(ys,values,height=.48,color=COLORS,zorder=3)
    if seed_values is not None:
        for yy,observations in zip(ys,seed_values):
            ax.scatter(observations,[yy-.11,yy,yy+.11],s=18,facecolor='white',edgecolor=INK,linewidth=.8,zorder=4)
    ax.set_xlim(0,bound);ax.set_ylim(-.55,2.55)
    ax.set_yticks(ys,LABELS,color=INK,fontsize=11.5)
    ax.tick_params(axis='y',length=0,pad=12)
    ax.tick_params(axis='x',length=0,pad=7,labelsize=10,colors=MUTED)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4,min_n_ticks=3))
    ax.xaxis.grid(True,color=GRID,linewidth=.8,zorder=0)
    ax.set_axisbelow(True);ax.spines[['top','right','left']].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    for yy,value,color in zip(ys,values,COLORS):
        ax.text(value+bound*.025,yy,f'{value:.2f}',va='center',fontsize=12,fontweight='bold',color=color)


def budget_table(fig,left,width,title,baseline,candidate,fields):
    columns=[left,left+width*.30,left+width*.66]
    fig.text(left,.375,title,fontsize=11,fontweight='bold',color=INK)
    for x,label in zip(columns,('Cap (LUT4)','False-safe: 217 → 128','False rejection: 217 → 128')):
        fig.text(x,.338,label,fontsize=9.6,color=MUTED)
    for i,cap in enumerate((32,64,128)):
        y=.296-i*.038
        fig.text(columns[0],y,str(cap),fontsize=11,color=INK)
        for x,field in zip(columns[1:],fields):
            a,b=baseline['caps'][str(cap)][field],candidate['caps'][str(cap)][field]
            fig.text(x,y,f'{a} → {b}',fontsize=11.5,fontweight='bold',color=ALERT if b>a else GOOD)
    a,b=baseline['maximum_underprediction_lut4'],candidate['maximum_underprediction_lut4']
    fig.text(left,.170,f'Worst underprediction: {a:.2f} → {b:.2f} LUT4',fontsize=10.5,color=ALERT if b>a else GOOD)


def render(stability_path,fresh_path,output):
    stability,fresh=load_sources(stability_path,fresh_path)
    seeds=sorted(stability['per_seed'])
    dev=[mean([stability['per_seed'][s][v]['group_macro_mae_lut4'] for s in seeds]) for v in VIEWS]
    prospective=[fresh['models'][v]['mae_lut4'] for v in VIEWS]
    repeats=[[stability['per_seed'][s][v]['group_macro_mae_lut4'] for s in seeds] for v in VIEWS]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none',
                         'pdf.fonttype':42,'ps.fonttype':42,'axes.unicode_minus':False})
    fig=plt.figure(figsize=(15.2,9.2),facecolor='white')
    fig.text(.055,.950,'Development gains did not transfer to the fresh check',fontsize=23,fontweight='bold',color=INK)
    fig.text(.055,.902,'Matched feature views · lower MAE is better · cohorts evaluated separately',fontsize=12,color=MUTED)
    fig.text(.055,.842,'A  Development selection stability',fontsize=14,fontweight='bold',color=INK)
    fig.text(.555,.842,'B  Prospective synthetic template check',fontsize=14,fontweight='bold',color=INK)
    fig.text(.055,.805,'Mean group-macro MAE across three seeds · LUT4',fontsize=10.5,color=MUTED)
    fig.text(.555,.805,'Mean absolute error on 40 newly measured circuits · LUT4',fontsize=10.5,color=MUTED)
    draw_mae(fig.add_axes([.163,.580,.308,.200]),dev,repeats)
    draw_mae(fig.add_axes([.663,.580,.290,.200]),prospective)
    dev_change=(dev[2]/dev[0]-1)*100
    fresh_change=(prospective[2]/prospective[0]-1)*100
    fig.text(.055,.527,f'128 vs 217: {dev_change:+.2f}% MAE; lower on all three seeds.',fontsize=11,fontweight='bold',color=GOOD)
    fig.text(.555,.527,f'128 vs 217: {fresh_change:+.2f}% MAE; fresh success rule failed.',fontsize=11,fontweight='bold',color=ALERT)
    jaccard=stability['selection_stability']['across_seeds_same_fold']['mean_jaccard']
    fig.text(.055,.493,f'1,665 rows · 522 groups · seed dots · same-fold Jaccard {jaccard:.3f}',fontsize=10,color=MUTED)
    mape=[fresh['models'][v]['positive_mape_percent'] for v in VIEWS]
    fig.text(.555,.493,f'Five equal-size templates · MAPE: {mape[0]:.2f}% → {mape[2]:.2f}% (217 → 128)',fontsize=10,color=MUTED)
    fig.lines.append(plt.Line2D([.055,.955],[.460,.460],transform=fig.transFigure,color=GRID,linewidth=1))
    fig.text(.055,.420,'C  Hardware budget decisions: baseline 217 → selected 128',fontsize=14,fontweight='bold',color=INK)
    aggregate=stability['eligibility']['descriptive_aggregates_not_independent_samples']
    budget_table(fig,.055,.43,'Development: sums over three descriptive seed repeats',
                 aggregate['mapping217'],aggregate['selected128'],('false_safe_count','false_rejection_count'))
    budget_table(fig,.555,.40,'Fresh: 40 frozen predictions matched to new labels',
                 fresh['models']['mapping217'],fresh['models']['selected128'],('false_accept','false_reject'))
    dev_status='PASS' if stability['eligibility']['strictly_eligible'] else 'FAIL'
    fresh_status='PASS' if fresh['predeclared_success'] else 'FAIL'
    fig.text(.055,.126,f'Development strict eligibility: {dev_status}',fontsize=11,fontweight='bold',color=ALERT if dev_status=='FAIL' else GOOD)
    fig.text(.555,.126,f'Fresh predeclared success: {fresh_status}',fontsize=11,fontweight='bold',color=ALERT if fresh_status=='FAIL' else GOOD)
    fig.lines.append(plt.Line2D([.055,.955],[.105,.105],transform=fig.transFigure,color=GRID,linewidth=1))
    fig.text(.055,.076,'Selected 128 remains experimental; keep 217 as the deployed default. No calibrated budget guarantee.',fontsize=10.5,fontweight='bold',color=INK)
    fig.text(.055,.047,'False-safe: prediction ≤ cap, measured area > cap. Seed repeats reuse the same consumed cohort; they are not independent samples.',fontsize=9.2,color=MUTED)
    fig.text(.055,.021,'Fresh scope: five synthetic circuit templates; no independent application-transfer or full-core claim. Sources: results/selection-stability and results/selection-validation.',fontsize=8.7,color=MUTED)
    output.mkdir(parents=True,exist_ok=True)
    paths=[]
    provenance=f'Stability summary SHA256 {sha(stability_path)}; fresh metrics SHA256 {sha(fresh_path)}. Separate cohorts; zero fits during rendering.'
    for extension in ('svg','png','pdf'):
        path=output/f'selection-validation.{extension}'
        metadata={'Title':'Feature selection: development stability and fresh synthetic validation',
                  'Creator':'scripts/render_selection_validation.py; Matplotlib',
                  'Subject' if extension=='pdf' else 'Description':provenance}
        fig.savefig(path,dpi=250,facecolor='white',metadata=metadata);paths.append(path)
    plt.close(fig)
    return paths


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stability',type=Path,default=ROOT/'results/selection-stability/summary.json')
    parser.add_argument('--fresh',type=Path,default=ROOT/'results/selection-validation/metrics.json')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/figures/research')
    args=parser.parse_args()
    for path in render(args.stability,args.fresh,args.output):print(path.resolve())
