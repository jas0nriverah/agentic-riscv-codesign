#!/usr/bin/env python3
"""Render the sealed repair study with separate development and fresh cohorts."""
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
NAMES=('base','incumbent_guard','guard_revised_static_abstain')
LABELS=('Base','Incumbent','Revised')
COLORS=(BLUE,LIGHT,TEAL)


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bars(ax,models,metric,suffix=''):
    values=[models[n][metric] for n in NAMES];ys=(2,1,0)
    ax.barh(ys,values,height=.52,color=COLORS,zorder=3)
    ax.set_yticks(ys,LABELS,fontsize=10,color=INK);ax.tick_params(axis='y',length=0,pad=7)
    ax.tick_params(axis='x',length=0,pad=5,labelsize=9,colors=MUTED)
    ax.set_xlim(0,max(values)*1.3);ax.set_ylim(-.6,2.6)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4));ax.xaxis.grid(True,color=GRID,lw=.8,zorder=0)
    ax.spines[['top','right','left']].set_visible(False);ax.spines['bottom'].set_color(GRID)
    for yy,v,c in zip(ys,values,COLORS):ax.text(v+max(values)*.035,yy,f'{v:.2f}{suffix}',va='center',fontsize=11,fontweight='bold',color=c)

def render(development,fresh,audit_path,output):
    dev,held,audit=read(development),read(fresh),read(audit_path)
    if held['schema']!='isaforge-guarded-revision-v1' or audit['status']!='pass':raise ValueError('Sealed study and completed independent audit required')
    selected=held['selected_candidate']
    if selected!=NAMES[-1] or dev['selected_candidate']!=selected:raise ValueError('Figure expects the frozen selected fallback')
    if any(held['models'][n]['count']!=40 for n in NAMES):raise ValueError('Complete matched independent40 required')
    if any(held['models'][n]['caps']!=held['models']['base']['caps'] for n in NAMES):raise ValueError('Expected exact unchanged cap errors')
    groups=[dev['named_regressions']['arithmetic-stress32'],dev['named_regressions']['signed_dual_arithmetic4'],held['models']]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False})
    fig=plt.figure(figsize=(16,10),facecolor='white')
    fig.text(.045,.953,'Signed arithmetic coverage repairs the remaining panel regressions',fontsize=23,fontweight='bold',color=INK)
    fig.text(.045,.913,'32 new training circuits · one fixed 300-tree fit · input-only signed repair route · base cap decisions preserved',fontsize=12,color=MUTED)
    titles=('A  Consumed arithmetic stress · 32','B  Consumed signed dual arithmetic · 4','C  Independent fresh check · 40')
    starts=(.045,.365,.685)
    for left,title,models in zip(starts,titles,groups):
        fig.text(left,.853,title,fontsize=13,fontweight='bold',color=INK)
        fig.text(left,.817,'MAE · LUT4 · lower is better',fontsize=10.5,color=MUTED)
        bars(fig.add_axes([left+.068,.648,.226,.145]),models,'mae_lut4')
        fig.text(left,.600,'Positive-target MAPE · lower is better',fontsize=10.5,color=MUTED)
        bars(fig.add_axes([left+.068,.432,.226,.145]),models,'positive_mape_percent','%')
    passed=held['scoped_experimental_eligibility']
    fig.text(.045,.390,'Both named regressions fixed; all six retained panels have MAE and MAPE no worse than base.',fontsize=10.5,color=TEAL,fontweight='bold')
    fig.text(.685,.390,'Fresh and development gates '+('passed.' if passed else 'failed.'),fontsize=10.5,fontweight='bold',color=TEAL if passed else RED)
    fig.lines.append(plt.Line2D([.045,.965],[.369,.369],transform=fig.transFigure,color=GRID,lw=1))
    fig.text(.045,.338,'Fresh budget mistakes are unchanged for all three predictors',fontsize=12,fontweight='bold',color=INK)
    for x,label in zip((.045,.175,.330,.500),('Cap · LUT4','False accept','False reject','Predicted / actual feasible')):fig.text(x,.309,label,fontsize=10,color=MUTED)
    for i,cap in enumerate((32,64,128)):
        row=held['models']['base']['caps'][str(cap)];y=.281-i*.027
        for x,value in zip((.045,.175,.330,.500),(str(cap),str(row['false_accept']),str(row['false_reject']),f"{row['predicted_accept']} / {row['actual_accept']}")):
            fig.text(x,y,value,fontsize=11,fontweight='bold',color=RED if cap==128 and x==.175 else INK)
    fig.text(.685,.338,'Worst underprediction · LUT4',fontsize=12,fontweight='bold',color=INK)
    worst=' → '.join(f"{held['models'][n]['maximum_underprediction_lut4']:.2f}" for n in NAMES)
    fig.text(.685,.301,worst,fontsize=16,fontweight='bold',color=INK)
    fig.text(.685,.274,'Base → incumbent → revised',fontsize=10,color=MUTED)
    fig.text(.685,.243,'Exact decisions at caps 32 / 64 / 128;',fontsize=10,color=MUTED)
    fig.text(.685,.219,'the two false accepts at 128 remain.',fontsize=10,fontweight='bold',color=RED)
    fig.lines.append(plt.Line2D([.045,.965],[.197,.197],transform=fig.transFigure,color=GRID,lw=1))
    template=audit['fresh_template_metrics_descriptive']['heldout_signed_variable_add_boolean']
    research=dev['panels']['research-baselines']
    fig.text(.045,.167,f"Visible tradeoffs: fresh signed-variable-add/boolean subgroup (4 cases) MAE {template['base']['mae_lut4']:.2f} → {template[selected]['mae_lut4']:.2f} vs base; MAPE {template['base']['positive_mape_percent']:.2f}% → {template[selected]['positive_mape_percent']:.2f}%.",fontsize=10,color=RED)
    fig.text(.045,.139,f"Retained research MAE {research['incumbent_guard']['mae_lut4']:.2f} → {research[selected]['mae_lut4']:.2f} vs incumbent (base {research['base']['mae_lut4']:.2f}). No new subgroup is an independent population guarantee.",fontsize=10,color=RED)
    fig.text(.045,.105,'The predeclared static-signed fallback was selected on consumed development data; the primary missed its retained research MAPE gate.',fontsize=10,color=MUTED)
    fig.text(.045,.077,'All earlier 192 / 327 / 32 / 40 / 40 / 32 panels are consumed. The fresh 40-case cohort was frozen separately; no learning curve is implied.',fontsize=10,color=MUTED)
    fig.text(.045,.049,'Experimental isolated iCE40 LUT4 point estimates only. No calibrated safety, full-CPU, timing, power or application-transfer guarantee. Base stays the default.',fontsize=10,color=MUTED)
    output.mkdir(parents=True,exist_ok=True);paths=[]
    provenance='; '.join(f'{p.name} SHA256 {sha(p)}' for p in (development,fresh,audit_path))+'. Separate cohorts; zero fits or native jobs in rendering.'
    for ext in ('svg','png','pdf'):
        path=output/f'guarded-revision.{ext}';meta={'Title':'Guarded signed arithmetic repair: consumed panels and independent fresh40','Creator':'scripts/render_guarded_revision.py; Matplotlib','Subject' if ext=='pdf' else 'Description':provenance}
        fig.savefig(path,dpi=200,facecolor='white',metadata=meta);paths.append(path)
    plt.close(fig);return paths

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--development',type=Path,default=ROOT/'results/guarded-revision/development-metrics.json')
    p.add_argument('--fresh',type=Path,default=ROOT/'results/guarded-revision/fresh-metrics.json')
    p.add_argument('--audit',type=Path,default=ROOT/'results/guarded-revision/audit.json')
    p.add_argument('--output',type=Path,default=ROOT/'docs/figures/research')
    a=p.parse_args()
    for path in render(a.development,a.fresh,a.audit,a.output):print(path.resolve())
