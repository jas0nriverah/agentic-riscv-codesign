#!/usr/bin/env python3
"""Render separate general and conditional panels from frozen audited evidence."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/boundary-refinement'
KEYS=('incumbent_signed','budget_release_compound_only','boundary_structural')
LABELS=('Signed','Release','Refined')
COLORS=('#70899C','#BA8C45','#087F83')
INK='#14283F';MUTED='#596C7B'

def main():
    inputs=[OUT/'fresh-metrics.json',OUT/'audit.json']
    data,audit=[json.loads(p.read_text()) for p in inputs]
    if audit['status']!='pass':raise ValueError('Independent evidence audit required')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','pdf.fonttype':42})
    fig=plt.figure(figsize=(15,10),facecolor='white')
    fig.text(.045,.95,'Structural boundary repair: two fresh evaluations',fontsize=24,fontweight='bold',color=INK)
    fig.text(.045,.91,f"Fixed 128-input pool · {data['unique_label_count']} unique measured circuits · zero fits · policy and selection frozen before labels",color=MUTED)
    ok=data['scoped_experimental_eligibility']
    fig.text(.045,.868,'Predeclared evidence gates: '+('PASS — scoped experimental validation' if ok else 'NOT PASSED — no promotion'),fontweight='bold',color=COLORS[2] if ok else '#A44635')
    panels=[(data['models'],f"General cohort · {data['general_count']} fixed circuits"),(data['conditional_models'],f"Conditional challenge · {data['active_count']} active + 8 shared controls")]
    for left,(models,title) in zip((.045,.54),panels):
        fig.text(left,.818,title,fontsize=14,fontweight='bold',color=INK)
        for bottom,metric,label,suffix in ((.64,'mae_lut4','Mean absolute error · LUT4 ↓',''),(.405,'positive_mape_percent','Positive-target MAPE · % ↓','%')):
            fig.text(left,bottom+.155,label,fontsize=11,color=MUTED)
            ax=fig.add_axes([left+.075,bottom,.33,.125])
            vals=[models[k][metric] for k in KEYS]
            ax.barh([2,1,0],vals,color=COLORS,height=.55,zorder=3)
            ax.set_yticks([2,1,0],LABELS);ax.set_xlim(0,max(vals)*1.3);ax.set_ylim(-.6,2.6)
            ax.spines[['top','right','left']].set_visible(False);ax.tick_params(length=0)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4));ax.grid(axis='x',color='#DFE7EC',zorder=0)
            for y,value in zip([2,1,0],vals):ax.text(value+max(vals)*.025,y,f'{value:.2f}{suffix}',va='center',fontweight='bold',fontsize=10)
        fig.text(left,.345,'False accepts / false rejects · separate gates',fontsize=11,fontweight='bold',color=INK)
        rows=[]
        for cap in ('32','64','128'):
            rows.append([cap]+[f"{models[k]['caps'][cap]['false_accept']} / {models[k]['caps'][cap]['false_reject']}" for k in KEYS])
        ax=fig.add_axes([left,.215,.43,.105]);ax.axis('off')
        table=ax.table(cellText=rows,colLabels=['Cap · LUT4',*LABELS],loc='center',cellLoc='center',bbox=[0,0,1,1])
        table.auto_set_font_size(False);table.set_fontsize(10)
        for (r,c),cell in table.get_celld().items():
            cell.set_edgecolor('#DFE7EC')
            if r==0:cell.set_facecolor('#EFF4F7');cell.set_text_props(weight='bold',color=INK)
        m=models[KEYS[0]];n=m['count']
        fig.text(left,.185,'Feasible / infeasible: '+ ' · '.join(f"{c}: {m['caps'][c]['actual_accept']}/{n-m['caps'][c]['actual_accept']}" for c in ('32','64','128')),fontsize=9.5,color=MUTED)
    fig.text(.045,.13,'Eight controls are shared between panels; no pooled metric or independent-cohort claim. Active-only gates are also audited.',fontsize=10,color=MUTED)
    fig.text(.045,.095,'The conditional sample is selected by frozen prediction disagreement, never labels. All pool features and predictions remain available.',fontsize=10,color=MUTED)
    fig.text(.045,.06,'Isolated iCE40 LUT4 estimation only; finite synthetic validation is not calibrated safety or a CPU speed, timing, power or application-transfer result.',fontsize=10,color=MUTED)
    outputs={}
    for ext in ('svg','png','pdf'):
        path=ROOT/f'docs/figures/research/boundary-refinement.{ext}'
        fig.savefig(path,dpi=180,facecolor='white',metadata={'Creator':'scripts/render_boundary_refinement.py'})
        outputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest();print(path)
    plt.close(fig)
    (OUT/'figure-provenance.json').write_text(json.dumps({'inputs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'outputs_sha256':outputs,'fits':0,'native_jobs':0},indent=2)+'\n')
if __name__=='__main__':main()
