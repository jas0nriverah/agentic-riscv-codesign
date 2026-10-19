#!/usr/bin/env python3
"""Independent read-only inherited-OOF router replay; never imports experiment code."""
import argparse, ast, hashlib, json, re
from pathlib import Path
import numpy as np

SEEDS=list(range(2026101421,2026101426))
VIEWS=['original_graph','dual_graph','dual_semantics']
ROUTERS={'original_graph_mul_semantics':'original_graph','dual_graph_mul_semantics':'dual_graph'}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b,path='root'):
    if isinstance(a,dict):
        assert a.keys()==b.keys(),(path,'keys')
        for k in a:close(a[k],b[k],path+'.'+str(k))
    elif isinstance(a,list):
        assert len(a)==len(b),(path,'length')
        for i,(x,y) in enumerate(zip(a,b)):close(x,y,path+'.'+str(i))
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        assert np.isfinite(a) and np.isfinite(b) and abs(a-b)<=1e-10*max(1,abs(a)),(path,a,b)
    else:assert a==b,(path,a,b)
def metric(y,p,s):
    e=p-y; cells={}
    for k in sorted(set(s)):
        v=e[s==k]; ae=np.abs(v)
        cells[k]={'count':len(v),'mae_lut4':float(ae.mean()),'signed_bias_lut4':float(v.mean()),
          'median_absolute_error_lut4':float(np.median(ae)),'p95_absolute_error_lut4':float(np.quantile(ae,.95)),
          'maximum_underprediction_lut4':float(max(0,-v.min())),'underprediction_count':int((v<0).sum()),
          'overprediction_count':int((v>0).sum()),'exact_prediction_count':int((v==0).sum())}
    return {'mae_lut4':float(np.abs(e).mean()),'macro_stratum_mae_lut4':float(np.mean([c['mae_lut4'] for c in cells.values()])),
      'rmsle':float(np.sqrt(np.mean(np.square(np.log1p(p)-np.log1p(y))))),'by_stratum':cells}

def audit(repo,router):
    root=repo/'results/2026-10-14-v5'; plan=read(router/'plan.json');summary=read(router/'summary.json')
    assert plan['seeds']==SEEDS and plan['routers']==ROUTERS and plan['controls']==VIEWS
    for k in ('calibration_rows_used','test_rows_used','external_rows_used','new_fits','new_hardware_measurements'):assert plan[k]==0
    snapshot=router/'sources/develop_v6_targeted.py'; source=snapshot.read_text(); tree=ast.parse(source)
    # No fit, measurement or test-data function call occurs in the executed router source.
    calls=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '' for n in ast.walk(tree) if isinstance(n,ast.Call)]
    assert not set(calls)&{'fit','fit_predict','fit_transform','measure','collect','predict','predict_many','evaluate'}
    assert 'test-data.json' not in source and 'evaluation.json' not in source and 'joblib' not in source
    assert 'calibration_indices' in source and 'all_rows=read(inputs[0]);rows=[all_rows[i] for i in fit];del all_rows' in source
    hashes={}; relocated=[]
    for name,digest in plan['input_sha256'].items():
        p=Path(name)
        if p.name=='develop_v6_targeted.py':p=snapshot
        elif not p.exists():
            parts=p.parts; pos=parts.index('agentic-riscv-codesign');p=repo.joinpath(*parts[pos+1:]);relocated.append(name)
        assert sha(p)==digest,('input hash',name)
        hashes[str(p)]=digest
    split=read(root/'split.json');start_path=next(Path(n) for n in plan['input_sha256'] if n.endswith('/run-start.json'))
    if not start_path.exists():start_path=repo/'results/2026-10-14-development-diagnostics/run-start.json'
    diagnostics=start_path.parent;start=read(start_path)
    indices=split['fit_indices'];assert len(indices)==1665==len(set(indices));assert not set(indices)&set(split['calibration_indices'])
    assert plan['fitting_formula_indices']==indices==start['fitting_formula_indices']
    folds=split['fold_validation_indices'];assert len(folds)==5;assert plan['fold_validation_indices']==folds==start['fold_validation_indices']
    flat=[i for fold in folds for i in fold];assert len(flat)==len(set(flat))==1665 and set(flat)==set(indices)
    data=read(root/'development-data.json');rows=[data[i] for i in indices];del data
    groups={i:split['component_by_formula'][r['formula']] for i,r in zip(indices,rows)}
    for fold in folds:
        assert not {groups[i] for i in fold}&{groups[i] for i in indices if i not in set(fold)}
    y=np.array([r['lut4_count'] for r in rows]);strata=np.array([r.get('stratum','workload') for r in rows])
    # Independent operator-token scan: exact operator followed by '('; never stratum/label routing.
    gate=np.array([bool(re.search(r'(?<![A-Za-z0-9_])(?:mul|mulh|mulhu|mulhsu)\s*\(',r['formula'])) for r in rows])
    counts={'semantic':int(gate.sum()),'base':int((~gate).sum())};close(counts,plan['routing_counts']);close(counts,summary['routing_counts'])
    bystratum={s:{'semantic':int((gate&(strata==s)).sum()),'base':int((~gate&(strata==s)).sum())} for s in sorted(set(strata))}
    close(bystratum,summary['routing_counts_by_stratum'])
    def aligned(records):
        assert len(records)==1665
        for i,r,t in zip(indices,rows,records):
            assert t['development_index']==i and t['formula']==r['formula'] and t['lut4_count']==r['lut4_count'] and t['stratum']==r.get('stratum','workload')
        p=np.array([r['predicted_lut4'] for r in records]);assert np.isfinite(p).all() and (p>=0).all();return p
    scores={v:{} for v in [*VIEWS,*ROUTERS]};exact_route_values=0
    for seed in SEEDS:
        inherited={v:aligned(read(diagnostics/'predictions'/f'{v}-seed-{seed}.json')) for v in VIEWS}
        predictions=dict(inherited)
        for router_name,base in ROUTERS.items():
            records=read(router/'predictions'/f'{router_name}-seed-{seed}.json');p=aligned(records)
            expected=np.where(gate,inherited['dual_semantics'],inherited[base]);assert np.array_equal(p,expected)
            assert all(r['routed_view']==('dual_semantics' if g else base) for r,g in zip(records,gate))
            exact_route_values+=len(p);predictions[router_name]=p
        for view,p in predictions.items():scores[view][str(seed)]=metric(y,p,strata)
    close(scores,summary['all_seeds'])
    by_variant={}
    for view in scores:
        values=np.array([scores[view][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS])
        by_variant[view]={'macro_mae_mean':float(values.mean()),'macro_mae_sample_sd':float(values.std(ddof=1)),
          'macro_mae_min':float(values.min()),'macro_mae_max':float(values.max()),
          'by_stratum_mean_mae':{s:float(np.mean([scores[view][str(seed)]['by_stratum'][s]['mae_lut4'] for seed in SEEDS])) for s in sorted(set(strata))},
          'maximum_underprediction_across_seeds':max(c['maximum_underprediction_lut4'] for m in scores[view].values() for c in m['by_stratum'].values())}
    close(by_variant,summary['by_variant'])
    paired={}
    for r,base in ROUTERS.items():
        for control in (base,'dual_semantics'):
            diffs=[scores[r][str(seed)]['macro_stratum_mae_lut4']-scores[control][str(seed)]['macro_stratum_mae_lut4'] for seed in SEEDS]
            paired[r+'_minus_'+control]={'differences_lut4':diffs,'mean':float(np.mean(diffs)),
              'improved_seeds':int((np.array(diffs)<0).sum()),'per_stratum_mean_difference':{s:by_variant[r]['by_stratum_mean_mae'][s]-by_variant[control]['by_stratum_mean_mae'][s] for s in sorted(set(strata))}}
    close(paired,summary['paired_comparisons'])
    return {'status':'passed','audit_source_sha256':sha(Path(__file__)),'router_output':str(router),'executed_router_sha256':sha(snapshot),
      'current_router_sha256':sha(repo/'scripts/develop_v6_targeted.py'),'executed_snapshot_preserved':True,
      'seeds':SEEDS,'fitting_rows':1665,'calibration_rows_scored':0,'test_rows_read':0,'external_rows_read':0,
      'inherited_prediction_files':15,'routed_prediction_files':10,'exact_routed_prediction_values':exact_route_values,
      'fold_count':5,'fitting_components':len(set(groups.values())),'routing_counts':counts,'routing_counts_by_stratum':bystratum,
      'by_variant':by_variant,'paired_comparisons':paired,'verified_input_sha256':hashes,'relocated_inputs':relocated,
      'limits':['All numerical operations use fitting-only rows. The complete development JSON is parsed before selecting rows; calibration labels are not scored or used in routing.',
      'Source inspection finds no new fit/model inference/hardware/test-data call in the router; the imported develop_v6 module supplies passive helpers only.',
      'The gate and both variants are post-V5 development hypotheses. Five shared seeds are not five independent tests; no population confidence interval or new bound is established.',
      'The archived executed source, rather than the later portability fix, is bound to the original plan hash.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--router',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=audit(args.repo.resolve(),args.router.resolve());args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ('status','exact_routed_prediction_values','routing_counts','by_variant')},indent=2))
