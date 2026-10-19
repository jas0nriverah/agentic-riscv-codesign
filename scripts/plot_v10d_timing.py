#!/usr/bin/env python3
"""Publish every fixed timing pair only after portable evidence replay."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def render(rows, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
        'pdf.fonttype':42,'svg.hashsalt':'isaforge-v10d-timing','axes.spines.top':False,'axes.spines.right':False})
    identities=list(dict.fromkeys(row['pair_id'] for row in rows))
    index={(r['pair_id'],r['seed']):r for r in rows}
    if len(identities)!=32 or len(index)!=96 or len(rows)!=96:
        raise ValueError('Complete32 pairs by3 seeds required')
    if set(index)!={(p,s) for p in identities for s in (1,2,3)}:
        raise ValueError('Exact paired seed grid required')
    labels=[]
    contexts={'direct_product':'Kx','add_after_product':'Kx + y',
        'sub_before_product':'K(x − y)','masked_sub_before_product':'K((x & 63) − y)'}
    for p in identities:
        r=index[p,1];labels.append(f"{r['constant_u32']:4d} · {contexts[r['context']]}")
    original=np.array([[index[p,s]['original_fmax_mhz'] for s in (1,2,3)] for p in identities])
    csd=np.array([[index[p,s]['csd_fmax_mhz'] for s in (1,2,3)] for p in identities])
    delta=np.array([[index[p,s]['csd_minus_original_period_ns'] for s in (1,2,3)] for p in identities])
    fig,axes=plt.subplots(1,3,figsize=(15,15),gridspec_kw={'wspace':.25})
    fig.subplots_adjust(left=.20,right=.95,top=.88,bottom=.10)
    fig.suptitle('Verified constant-multiply implementations · matched routed timing',x=.035,ha='left',y=.98,fontsize=18)
    fig.text(.035,.945,'All 32 pairs × 3 matched seeds · iCE40HX8K / CT256 · common mapped 132-FF harness · 12 MHz constraint',fontsize=11)
    fig.text(.035,.920,'Full-harness modeled Fmax; wrapper-limited and unresolved paths remain included. No board or CPU speedup claim.',fontsize=10)
    vmax=max(original.max(),csd.max());limit=max(float(abs(delta).max()),1e-9)
    for i,(values,title) in enumerate([(original,'Original Fmax · MHz'),(csd,'CSD Fmax · MHz'),(delta,'CSD − original period · ns')]):
        ax=axes[i]
        options={'cmap':'RdBu_r','norm':TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit)} if i==2 else {'cmap':'viridis','vmin':0,'vmax':vmax}
        picture=ax.imshow(values,aspect='auto',**options)
        ax.set_title(title,loc='left',pad=14)
        ax.set_xticks([0,1,2],['Seed 1','Seed 2','Seed 3'])
        ax.set_yticks(range(32),labels if i==0 else ['']*32)
        ax.tick_params(axis='y',length=0)
        for y in range(4,32,4): ax.axhline(y-.5,color='white',lw=2)
        for (y,x),v in np.ndenumerate(values):
            rgba=picture.cmap(picture.norm(v));lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            ax.text(x,y,f'{v:+.2f}' if i==2 else f'{v:.1f}',ha='center',va='center',fontsize=9,color='black' if lum>.57 else 'white')
        fig.colorbar(picture,ax=ax,fraction=.045,pad=.03)
    means=delta.mean(axis=1)
    fig.text(.035,.075,f'Primary: 32 pair means across the same three seeds · mean Δ {means.mean():+.3f} ns · median {np.median(means):+.3f} ns · lower / equal / higher: {(means<0).sum()} / {(means==0).sum()} / {(means>0).sum()}',fontsize=10)
    fig.text(.035,.045,'Period = 1000 / Fmax. Negative period change favors CSD; positive change favors original. Every seed is shown.\nThese are matched development cases, not independent samples of new programs. Full precision and path classifications: figure-data.json.',fontsize=10)
    figures=[('v10d-matched-timing',fig)]
    fig,axes=plt.subplots(1,3,figsize=(19,8),gridspec_kw={'wspace':.3})
    fig.subplots_adjust(left=.08,right=.97,top=.83,bottom=.16)
    fig.suptitle('Resource savings versus routed period · every matched seed',x=.045,ha='left',y=.98,fontsize=19)
    from collections import Counter
    classes=Counter(r[arm+'_path_classification'] for r in rows for arm in ('original','csd'))
    fig.text(.045,.875,'192 path classifications: '+', '.join(f'{key}: {value}' for key,value in sorted(classes.items())),fontsize=10)
    fig.text(.045,.92,'Lower values favor CSD on both axes; LUT4/carry remain separate resources. No combined cost weight is assumed.',fontsize=11)
    colors=['#245f9a','#d48328','#389472']
    for ax,resource,description in [(axes[0],'lut4','Wrapped LUT4'),(axes[1],'carry','Wrapped carry cells'),(axes[2],'packed_lc','Packed logic cells')]:
        for seed,color in zip((1,2,3),colors):
            selected=[r for r in rows if r['seed']==seed]
            if resource=='packed_lc':
                x=[r['csd_utilization']['ICESTORM_LC']['used']-r['original_utilization']['ICESTORM_LC']['used'] for r in selected]
            else:
                primitive={'lut4':'SB_LUT4','carry':'SB_CARRY'}[resource]
                x=[r['csd_wrapped_primitive_counts'].get(primitive,0)-r['original_wrapped_primitive_counts'].get(primitive,0) for r in selected]
            y=[r['csd_minus_original_period_ns'] for r in selected]
            ax.scatter(x,y,s=38,color=color,alpha=.75,edgecolors='white',linewidths=.4,label=f'Seed {seed}')
        ax.axvline(0,color='#8997a4',lw=1);ax.axhline(0,color='#8997a4',lw=1)
        ax.grid(alpha=.18);ax.set_axisbelow(True)
        ax.set_xlabel(f'{description}: CSD − original');ax.set_ylabel('Routed period: CSD − original (ns)')
        ax.legend(frameon=False)
    fig.text(.045,.055,'96 points per panel; coincident points may overlap. Each mapped arm retains 132 FFs. All results, including wrapper-limited paths, remain visible.\nWrapped mapped counts differ from bare candidate counts and packed place-and-route utilization; all three inventories are retained in figure-data.json.',fontsize=10)
    figures.append(('v10d-resource-timing-tradeoffs',fig))
    files=[]
    for name,fig in figures:
        for ext in ('png','svg','pdf'):
            p=output/(name+'.'+ext);fig.savefig(p,dpi=220,bbox_inches='tight',pad_inches=.2);files.append(p)
        plt.close(fig)
    return files


def run(root, output):
    import audit_v10d_timing as verifier
    root,output=Path(root).resolve(),Path(output).resolve()
    if output.exists(): raise ValueError('Fresh output directory required')
    audit=verifier.run(root)
    if audit['status']!='pass' or audit['complete'] is not True or audit['failures']:
        raise ValueError('Complete audited timing study required')
    rows=audit['paired_results']
    if len(rows)!=96: raise ValueError('All96 matched pairs required')
    output.mkdir(parents=True)
    write(output/'independent-audit.json',audit)
    data={'schema':'isaforge-v10d-timing-figures-v1','synthetic':False,'rows':rows,
          'mapped_arms':audit['mapped_arms'],'summary':audit['summary'],
          'path_classification_counts':audit['path_classification_counts'],
          'limits':'Full registered harness timing model; no board/CPU/power/ASIC/independent-transfer claim.'}
    write(output/'figure-data.json',data)
    files=render(rows,output)
    (output/'captions.md').write_text('All 32 fixed pairs and all three matched seeds. Period is 1000/Fmax; negative CSD-minus-original period favors CSD. No seeds are filtered by resource savings or path class. Full-harness timing is not exact arithmetic delay when wrapper-limited or attribution is unavailable. Resource plots show wrapped mapped LUT4/carry and packed logic-cell counts separately; the mapped harness has 132 FFs. No population confidence interval, board operation, CPU speedup or power claim.\n')
    def hashed(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    sources=[Path(__file__).resolve(),Path(verifier.__file__).resolve(),root/'preparation.json',root/'measurement-approval.json',root/'measurements/completion.json']
    write(output/'figure-manifest.json',{'schema':'isaforge-v10d-timing-publication-v1','pair_count':32,'matched_seed_pairs':96,
         'sources':[hashed(p) for p in sources],'files':[hashed(p) for p in sorted(output.iterdir()) if p.is_file()], 'figure_count':len(files)})
    return data['summary']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.root,args.output),indent=2))
