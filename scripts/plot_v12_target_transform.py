#!/usr/bin/env python3
"""Render completed V12 target-scale evidence; never fit or load estimators.

Every paired seed is shown. Full-precision plotted values, complete score tables
and SHA256 references to saved OOF points accompany the figures. No best-seed
selection, population interval, additional targets or model inference.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SEEDS=(2026101421,2026101422,2026101423)
VIEWS=('raw','log1p')
STRATA=('arithmetic_chain','comparators','constant_shifts','mask_logic','multiplication','parallel_branches','shared_diamond','variable_shifts','workload')
COLORS={'raw':'#65717D','log1p':'#126B9B'}
LABELS={'raw':'Raw target','log1p':'log1p target'}


def need(value,message):
    if not value:raise ValueError(message)
def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):
    path=Path(path).resolve()
    return {'path':path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),'sha256':sha(path)}
def write(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def close(a,b):return type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=0,abs_tol=1e-11)


def actual_data(root):
    import numpy as np
    root=Path(root).resolve();fit=root/'fit-attempt-0000'
    done_path=fit/'completion.json';need(done_path.is_file(),'Wait for completed fitting; partial outcomes are not plotted')
    done=read(done_path)
    need(done.get('schema')=='isaforge-v12-fit-completion-v1' and done.get('complete') is True and done.get('error') is None
        and all(type(done.get(k)) is int and done[k]==30 for k in ('fits_attempted','fits_completed','maximum_fits')),'Complete successful30-fit result required')
    for key in ('evaluation_target_reads','new_physical_labels','new_feature_extractions','new_solver_queries'):need(done.get(key)==0,'Fitting-only protocol differs')
    summary_path=fit/'summary.json';prep_path=root/'preparation.json';approval_path=root/'fit-approval.json'
    need(sha(summary_path)==done['summary_sha256'] and sha(prep_path)==done['preparation_sha256'] and sha(approval_path)==done['approval_sha256'],'Completed summary/preparation/approval identity differs')
    summary,prep=read(summary_path),read(prep_path)
    need(summary.get('schema')=='isaforge-v12-target-transform-comparison-v1' and summary['fits_completed']==30
        and set(summary['scores'])==set(VIEWS),'Exact two-view summary required')
    bindings={(root/e['path']).resolve():e['sha256'] for e in prep['files']}
    required=[root/n for n in ('fitting.json','split.json','recipe.json','runtime.json')]+[ROOT/'scripts/develop_v12_target_transform.py']
    need(all(bindings.get(p)==sha(p) for p in required),'Frozen fitting/recipe/source changed')
    need(done['runner_sha256']==sha(required[-1]),'Completed fitting source differs')
    fitting=read(root/'fitting.json');rows=fitting['rows'];split=read(root/'split.json');recipe=read(root/'recipe.json')
    need(len(rows)==len({r['formula'] for r in rows})==1713 and set(r['stratum'] for r in rows)==set(STRATA)
        and recipe['seeds']==list(SEEDS) and recipe['target_views']==list(VIEWS) and recipe['maximum_fits']==30,'Complete fixed1713row/three-seed recipe required')
    paths=[done_path,summary_path,prep_path,approval_path,root/'fit-claim.json',*required]
    for i in range(1,31):
        path=fit/'receipts'/f'{i:02d}-completed.json';receipt=read(path)
        need(receipt['fit_index']==i and receipt['save_load_points_exact'] is True,'Every fit needs completed model-roundtrip receipt');paths.append(path)
    truth=np.asarray([r['lut4_count'] for r in rows],dtype=float);strata=np.asarray([r['stratum'] for r in rows]);zero=np.asarray(fitting['original_zero'],dtype=bool)
    need(np.isfinite(truth).all() and np.all(truth>=0) and np.all(truth==np.floor(truth)),'Finite original LUT4 targets required')
    for view in VIEWS:
        need(set(summary['scores'][view])==set(map(str,SEEDS)),'All three fixed seeds required')
        for seed in SEEDS:
            point_path=fit/'predictions'/f'{view}-seed-{seed}.json';metric_path=fit/'metrics'/f'{view}-seed-{seed}.json'
            points=read(point_path);score=summary['scores'][view][str(seed)]
            need(len(points)==1713 and read(metric_path)==score,'Complete saved points and matching metric table required')
            for i,(expected,point) in enumerate(zip(rows,points)):
                need(all(point[k]==v for k,v in expected.items()) and point['fold']==split['fold_ids'][i]
                    and point['original_zero'] is bool(zero[i]),'OOF row/fold/zero identity changed')
            p=np.asarray([r['predicted_lut4'] for r in points]);encoded=np.asarray([r['encoded_prediction'] for r in points]);before=np.asarray([r['decoded_before_zero'] for r in points])
            need(np.isfinite(p).all() and np.all(p>=0) and np.isfinite(encoded).all(),'Finite complete OOF forecasts required')
            decoded=np.maximum(np.expm1(encoded) if view=='log1p' else encoded,0)
            need(np.array_equal(decoded,before),'Saved inverse of forest mean differs')
            decoded[zero]=0;need(np.array_equal(decoded,p),'Only original graph zero override permitted')
            errors=np.abs(p-truth);pooled=score['pooled']
            for key,value in [('mae_lut4',errors.mean()),('p99_absolute_error_lut4',np.quantile(errors,.99,method='linear')),
                ('maximum_underprediction_lut4',np.maximum(truth-p,0).max())]:need(close(pooled[key],float(value)),'Saved-point metric replay differs: '+key)
            need(pooled['count']==1713 and pooled['zero_target_count']==int((truth==0).sum()) and pooled['positive_target_count']==int((truth>0).sum()),'Complete metric denominators required')
            need(set(score['by_stratum'])==set(STRATA),'All9strata required')
            for name in STRATA:
                chosen=strata==name;cell=score['by_stratum'][name]
                need(cell['count']==int(chosen.sum()) and close(cell['mae_lut4'],float(errors[chosen].mean())),'All-stratum OOF replay differs')
            macro=float(np.mean([score['by_stratum'][name]['mae_lut4'] for name in STRATA]))
            need(close(score['macro_stratum_mae_lut4'],macro),'Equal-nine-stratum primary differs')
            for cap in (32,64,128):
                cell=pooled['caps'][str(cap)]
                expected={'false_accept_count':int(((p<=cap)&(truth>cap)).sum()),'false_reject_count':int(((p>cap)&(truth<=cap)).sum()),
                    'actually_feasible_count':int((truth<=cap).sum()),'actually_infeasible_count':int((truth>cap).sum()),'predicted_feasible_count':int((p<=cap).sum()),'count':1713}
                need(cell==expected,'Full-cohort cap decisions differ')
            paths.extend([point_path,metric_path])
    diffs=[summary['scores']['log1p'][str(s)]['macro_stratum_mae_lut4']-summary['scores']['raw'][str(s)]['macro_stratum_mae_lut4'] for s in SEEDS]
    primary=summary['primary_log_minus_raw_macro_mae_lut4']
    need(all(close(primary['per_seed'][str(s)],v) for s,v in zip(SEEDS,diffs)) and close(primary['mean'],float(np.mean(diffs))),'Paired three-seed primary differs')
    values={}
    for view in VIEWS:
        scores=summary['scores'][view]
        values[view]={'primary_macro_mae_by_seed':[scores[str(s)]['macro_stratum_mae_lut4'] for s in SEEDS],
            'stratum_mae_by_seed':{name:[scores[str(s)]['by_stratum'][name]['mae_lut4'] for s in SEEDS] for name in STRATA},
            'stratum_mae_three_seed_mean':{name:float(np.mean([scores[str(s)]['by_stratum'][name]['mae_lut4'] for s in SEEDS])) for name in STRATA},
            'cap64_false_accept_by_seed':[scores[str(s)]['pooled']['caps']['64']['false_accept_count'] for s in SEEDS],
            'cap64_false_reject_by_seed':[scores[str(s)]['pooled']['caps']['64']['false_reject_count'] for s in SEEDS],
            'p99_absolute_error_by_seed':[scores[str(s)]['pooled']['p99_absolute_error_lut4'] for s in SEEDS],
            'maximum_underprediction_by_seed':[scores[str(s)]['pooled']['maximum_underprediction_lut4'] for s in SEEDS]}
    data={'schema':'isaforge-v12-target-transform-figure-data-v1','synthetic':False,'training_rows':1713,'groups':prep['components'],
        'folds':5,'fits':30,'features':217,'seeds':list(SEEDS),'stratum_order':list(STRATA),'stratum_counts':fitting['stratum_counts'],
        'plotted_full_precision_values':values,'summary':summary,'source_and_input_sha256':[ref(p) for p in dict.fromkeys([Path(__file__),*paths])],
        'point_evidence':'All six complete saved1713-row OOF point files are hashed above; no duplicated or recomputed forecasts.',
        'scope':'Fitting-only consumed development on identical leakage-closed folds; no best-seed selection, population confidence interval, calibrated uncertainty, CPU or transfer claim.'}
    return data,list(dict.fromkeys(paths))


def render(data,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,
        'xtick.labelsize':10,'ytick.labelsize':10,'axes.spines.top':False,'axes.spines.right':False,
        'axes.axisbelow':True,'figure.facecolor':'white','svg.fonttype':'none','pdf.fonttype':42,'svg.hashsalt':'isaforge-v12-target-transform'})
    values=data['plotted_full_precision_values'];figures=[]
    seed_labels=[str(s)[-2:] for s in SEEDS]
    def bars(ax,key,ylabel,title,integer=False):
        positions=np.arange(3);all_values=[]
        for view,offset in [('raw',-.17),('log1p',.17)]:
            y=values[view][key];all_values.extend(y);ax.bar(positions+offset,y,width=.30,color=COLORS[view],label=LABELS[view])
            for x,v in zip(positions+offset,y):ax.annotate(f'{v:d}' if integer else f'{v:.3f}',(x,v),xytext=(0,5),textcoords='offset points',ha='center',va='bottom',fontsize=9)
        ax.set_xticks(positions,seed_labels);ax.set_xlabel('Paired algorithm seed · suffix');ax.set_ylabel(ylabel)
        ax.set_ylim(0,max(all_values)*1.22 or 1);ax.grid(axis='y',color='#E2E6EA',lw=.7);ax.set_title(title,loc='left',pad=14)
        if integer:ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    def title(fig,heading,subtitle):
        fig.suptitle(heading,x=.035,ha='left',y=.985,fontsize=19,color='#1D2832')
        fig.text(.035,.935,subtitle,fontsize=11,color='#48515C')
        handles=[plt.Rectangle((0,0),1,1,color=COLORS[v]) for v in VIEWS]
        fig.legend(handles,[LABELS[v] for v in VIEWS],loc='upper right',bbox_to_anchor=(.98,.93),ncol=2,frameon=False,fontsize=10)
    fig,axes=plt.subplots(1,3,figsize=(19,8.3),gridspec_kw={'width_ratios':[.8,1.28,.95],'wspace':.50})
    fig.subplots_adjust(left=.06,right=.975,top=.80,bottom=.25)
    title(fig,'V12 · changing target scale does not improve the declared point primary',
        'Same 1,713 original-target circuits · mapping217 · ExtraTrees300 · five leakage-closed folds · all three paired seeds (2026101421/22/23)')
    bars(axes[0],'primary_macro_mae_by_seed','Equal-nine-stratum OOF MAE (LUT4) ↓','A  Primary · every paired seed')
    ax=axes[1];positions=np.arange(9)
    names=[f"{name.replace('_',' ')} (N={data['stratum_counts'][name]})" for name in STRATA]
    for view,offset in [('raw',-.18),('log1p',.18)]:
        mean=[values[view]['stratum_mae_three_seed_mean'][s] for s in STRATA]
        ax.barh(positions+offset,mean,height=.31,color=COLORS[view],alpha=.86)
        for j,name in enumerate(STRATA):
            samples=values[view]['stratum_mae_by_seed'][name]
            ax.scatter(samples,[j+offset+d for d in (-.045,0,.045)],s=12,color='#17212A',alpha=.65,zorder=3)
    ax.set_yticks(positions,names);ax.invert_yaxis();ax.set_xlim(left=0);ax.grid(axis='x',color='#E2E6EA',lw=.7)
    ax.set_xlabel('OOF MAE (LUT4) ↓ · bars: mean of three seeds');ax.set_title('B  All nine strata · no selected subset',loc='left',pad=14)
    ax=axes[2];deltas=[];seed_deltas=[]
    for j,name in enumerate(STRATA):
        change=[l-r for l,r in zip(values['log1p']['stratum_mae_by_seed'][name],values['raw']['stratum_mae_by_seed'][name])]
        mean=float(np.mean(change));deltas.append(mean);seed_deltas.append(change)
        ax.barh(j,mean,height=.52,color='#BA5F55' if mean>0 else '#5A91AC',alpha=.85)
        ax.scatter(change,[j+d for d in (-.09,0,.09)],color='#263442',s=20,zorder=3)
    all_deltas=[value for row in seed_deltas for value in row];span=max(all_deltas)-min(all_deltas) or 1
    for j,mean in enumerate(deltas):
        label=(max(seed_deltas[j]+[mean])+.045*span) if mean>=0 else (min(seed_deltas[j]+[mean])-.045*span)
        ax.text(label,j,f'{mean:+.3f}',ha='left' if mean>=0 else 'right',va='center',fontsize=9)
    ax.set_yticks(positions,['']*9);ax.invert_yaxis();ax.set_xlim(min(0,min(all_deltas))-.25*span,max(0,max(all_deltas))+.28*span)
    ax.axvline(0,color='#36434F',lw=1);ax.grid(axis='x',color='#E2E6EA',lw=.7)
    ax.set_title('C  Paired stratum differences',loc='left',pad=14);ax.set_xlabel('log1p − raw MAE (LUT4) · negative favors log1p')
    primary=data['summary']['primary_log_minus_raw_macro_mae_lut4']
    fig.text(.035,.105,f"Primary mean across the three paired seeds: log1p − raw = {primary['mean']:+.6f} LUT4. All three seed contrasts are positive.\nDots in B–C show every seed; bars and labels are descriptive three-seed means. No best seed, error-bar inference or population confidence interval.",fontsize=11,color='#263442')
    fig.text(.035,.035,'OOF predictions use held-out leakage groups. Both targets retain the original-graph zero override; the log predictor decodes expm1 of the forest mean log prediction.\nFitting-only consumed development; no new evaluation labels, final refit, calibration, acquisition policy, CPU or independent-transfer claim. Full precision and source hashes: figure-data.json.',fontsize=10,color='#48515C')
    figures.append(('v12-primary-and-strata',fig))
    fig,axes=plt.subplots(2,2,figsize=(14.8,11.4),gridspec_kw={'wspace':.30,'hspace':.55})
    fig.subplots_adjust(left=.085,right=.965,top=.82,bottom=.18)
    title(fig,'V12 · threshold and tail tradeoffs remain separate endpoints',
        'All 1,713 OOF rows per view and seed · same five folds and zero override · raw/log contrasts are not an uncertainty or transfer claim')
    denominator=data['summary']['scores']['raw'][str(SEEDS[0])]['pooled']['caps']['64']
    bars(axes[0,0],'cap64_false_accept_by_seed','False accept count ↓',f"A  Cap64 FA · actually infeasible N={denominator['actually_infeasible_count']}",True)
    bars(axes[0,1],'cap64_false_reject_by_seed','False reject count ↓',f"B  Cap64 FR · actually feasible N={denominator['actually_feasible_count']}",True)
    bars(axes[1,0],'p99_absolute_error_by_seed','P99 absolute error (LUT4) ↓','C  P99 absolute error · all rows')
    bars(axes[1,1],'maximum_underprediction_by_seed','Maximum underprediction (LUT4) ↓','D  Worst underprediction · all rows')
    fig.text(.035,.095,'FA: prediction ≤64 when target >64. FR: prediction >64 when target ≤64. Equal-to-cap decisions count as feasible.\nThe log target increases cap64 false accepts and P99 error in every seed, while reducing false rejects and maximum underprediction.',fontsize=11,color='#263442')
    fig.text(.035,.035,'Every paired seed is shown; no mean-error or one-sided-risk improvement substitutes for the other endpoints. Cap32/128 sensitivities and full score tables are retained in figure-data.json.\nValues are static original-RTL LUT4 prediction errors on consumed fitting data, not hardware timing, packed area, board/CPU performance or population evidence.',fontsize=10,color='#48515C')
    figures.append(('v12-cap64-and-tails',fig))
    files=[]
    for name,fig in figures:
        for extension in ('png','pdf','svg'):
            path=output/(name+'.'+extension)
            fig.savefig(path,dpi=220,bbox_inches='tight',pad_inches=.20,metadata={'CreationDate':None,'ModDate':None} if extension=='pdf' else None);files.append(path)
        plt.close(fig)
    return files,matplotlib.__version__


def run(root,output):
    output=Path(output).resolve();need(not output.exists(),'Fresh figure directory required; preserve earlier figures')
    data,paths=actual_data(root);before={p:sha(p) for p in [Path(__file__),*paths]}
    output.mkdir(parents=True);files,version=render(data,output)
    write(output/'figure-data.json',data)
    need(all(sha(p)==value for p,value in before.items()),'Completed plot input/source changed while rendering')
    write(output/'figure-manifest.json',{'schema':'isaforge-v12-target-transform-publication-v1','complete':True,
        'source_and_input_sha256':data['source_and_input_sha256'],'output_sha256':{p.name:sha(p) for p in [*files,output/'figure-data.json']},
        'matplotlib':version,'figures':2,'raster_and_vector_outputs':len(files),'new_fits':0,'new_forecasts':0,'evaluation_target_reads':0,'new_physical_labels':0,
        'saved_fitting_points_metric_replay':True,'best_seed_selected':False,'population_interval':False})
    return {'output':str(output),'figures':2,'files':len(files),'primary':data['summary']['primary_log_minus_raw_macro_mae_lut4']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.root,args.output),indent=2))
