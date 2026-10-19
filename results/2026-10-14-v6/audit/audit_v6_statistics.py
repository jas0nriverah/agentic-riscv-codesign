#!/usr/bin/env python3
"""Independent completed-only V6 raw, calibration and test statistics replay.

No evaluator imports, fitting, measurement, hardware invocation or source mutation.
A stage must be explicitly released and complete before its label files open.
The caller must also have the parent's separate human release authorization.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import hashlib,itertools,json,math,random,re,subprocess,sys,zipfile
from pathlib import Path
import numpy as np

MODELS=('mapping_v6','router_v6','sog_tuned','original_graph','dual_graph','dual_semantics','masterrtl_fixed','v4_frozen')
NEW=MODELS[:2]
CAPS=(16,32,64,128,256)
BOUNDARIES=(0,1,2,31,32,33,2147483647,2147483648,2147483649,4294967295)
MASK=4294967295
SEEDS={'calibration':2026101520,'test':2026101521}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc(s):
    t=datetime.fromisoformat(s.replace('Z','+00:00'));assert t.tzinfo and t.utcoffset().total_seconds()==0;return t

def checked(entry,root):
    p=(root/entry['path']).resolve();assert sha(p)==entry['sha256'],('frozen bytes',p);return p

def close(a,b,path='root'):
    if isinstance(a,dict):
        assert a.keys()==b.keys(),(path,'keys',a.keys()-b.keys(),b.keys()-a.keys())
        for k in a:close(a[k],b[k],path+'.'+str(k))
    elif isinstance(a,list):
        assert len(a)==len(b),(path,'length')
        for i,(v,w) in enumerate(zip(a,b)):close(v,w,path+'.'+str(i))
    elif isinstance(a,(float,int)) and not isinstance(a,bool):
        assert isinstance(b,(float,int)) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-10*max(1,abs(a)),(path,a,b)
    else:assert a==b,(path,a,b)

def oracle(expression,in0,in1):
    """Separate exact-integer implementation; every internal result wraps RV32."""
    def signed(x):return x if x<2147483648 else x-4294967296
    def visit(n):
        if not n.children:return (n.value if isinstance(n.value,int) else in0 if n.value=='in0' else in1)&MASK
        args=tuple(visit(c) for c in n.children);a=args[0];b=args[-1];op=n.value
        if op=='lui':v=a  # Formula literals already encode the decoded LUI value.
        elif op in ('add','addi'):v=a+b
        elif op=='sub':v=a-b
        elif op in ('and','andi'):v=a&b
        elif op in ('or','ori'):v=a|b
        elif op in ('xor','xori'):v=a^b
        elif op in ('sll','slli'):v=a*2**(b%32)
        elif op in ('srl','srli'):v=a//2**(b%32)
        elif op in ('sra','srai'):v=signed(a)//2**(b%32)
        elif op in ('slt','slti'):v=int(signed(a)<signed(b))
        elif op in ('sltu','sltiu'):v=int(a<b)
        elif op=='mul':v=a*b
        elif op in ('mulh','mulhsu','mulhu'):
            left=signed(a) if op!='mulhu' else a;right=signed(b) if op=='mulh' else b
            v=(left*right)//4294967296
        else:raise AssertionError(('unsupported oracle operator',op))
        return v%4294967296
    return visit(expression)

def oracle_selfcheck(parse):
    cases=[('lui(-2147483648)',0,0,2147483648),('add(in0,in1)',MASK,2,1),('sub(in0,in1)',0,1,MASK),
      ('sll(in0,in1)',1,32,1),('srl(in0,in1)',MASK,31,1),('sra(in0,in1)',2147483648,31,MASK),
      ('slt(in0,in1)',MASK,0,1),('sltu(in0,in1)',MASK,0,0),('mul(in0,in1)',MASK,MASK,1),
      ('mulh(in0,in1)',2147483648,2,MASK),('mulhu(in0,in1)',MASK,MASK,MASK-1),
      ('mulhsu(in0,in1)',MASK,MASK,MASK),('srli(slli(in0,1),1)',MASK,0,2147483647)]
    for f,a,b,y in cases:assert oracle(parse(f),a,b)==y,('oracle selfcheck',f)
    return len(cases)

def aligned(rows,values,key):
    ids=lambda r:(r['benchmark'],r['candidate_id'],r['formula'])
    assert [ids(r) for r in rows]==[ids(r) for r in values]
    a=np.asarray([r[key] for r in values],dtype=float);assert a.shape==(len(rows),) and np.isfinite(a).all() and (a>=0).all();return a

def raw_stage(repo,root,scope,parse,render):
    folder=root/'corpus'/scope
    # Guard BEFORE opening dataset, unique counts, vectors or target archives.
    release=read(folder/'label-release.json');done=read(folder/'completion.json');review=read(folder/'label-approval.json')
    assert release['scope']==scope and release['authorized_after_parent_review'] is True
    assert done['complete'] is True and not done['failures'] and done['scope']==scope
    assert done['release']==release and done['legacy_measurements_reused'] is False
    assert done['unique_formula_count']==done['weighted_row_count']==192
    assert review==release['parent_review'] and review['approved_for_label_release'] is True
    assert sha(folder/'label-approval.json')==release['review_sha256']
    stagefile=root/('point-freeze.json' if scope=='calibration' else 'calibration-freeze.json')
    assert sha(stagefile)==release['freeze_sha256']==review['freeze_sha256']
    assert utc(read(stagefile)['frozen_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(release['released_at_utc'])<=utc(done['completed_at_utc'])
    assert done['collector_sha256']==sha(repo/'scripts/measure_v6.py') and done['original_rtl_only'] is True
    point=read(root/'point-freeze.json');assert release['point_freeze_sha256']==sha(root/'point-freeze.json')
    assert done['tool']==point['frozen_tool']['version'] and done['tool_sha256']==point['frozen_tool']['executable_sha256']
    assert re.fullmatch(r'attempt-\d{4}',done['attempt']);attempt=folder/done['attempt']
    assert read(attempt/'completion.json')==done
    for name,key in [('dataset.json','dataset_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:assert sha(attempt/name)==done[key]
    candidates=read(folder/'candidates.json');assert len(candidates)==192 and sha(folder/'candidates.json')==release['candidate_sha256']
    labels=read(attempt/'dataset.json');y=aligned(candidates,labels,'lut4_count');assert (y==y.astype(int)).all()
    unique=read(attempt/'unique-measurements.json');assert len(unique)==192;by_formula={r['formula']:r for r in unique};assert set(by_formula)=={r['formula'] for r in candidates}
    evidence=read(folder/'raw-evidence.json');archive=folder/evidence['archive'];assert sha(archive)==evidence['archive_sha256']
    assert evidence['completion_sha256']==sha(folder/'completion.json');assert evidence['scope']==scope
    entries={r['path']:r for r in evidence['files']};assert len(entries)==len(evidence['files'])
    scratch=(root/done['scratch_directory']).resolve();prefix=scratch.relative_to(repo).as_posix()
    assert prefix.startswith('generated/v6-measurements/'+scope+'/') and scratch.name==done['attempt']
    proofs=read(attempt/'verification.json');assert len(proofs)==2 and [p['formula_count'] for p in proofs]==[128,64]
    functions=sorted(by_formula);pairs=list(itertools.product(BOUNDARIES,repeat=2));rng=random.Random(SEEDS[scope]);pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048))
    comparisons=0;counts=[];wrap_incidents=0
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(entries)
        for name,entry in entries.items():
            assert name.startswith(prefix+'/') and '..' not in Path(name).parts and not Path(name).is_absolute()
            data=z.read(name);assert len(data)==entry['size'] and hashlib.sha256(data).hexdigest()==entry['sha256']
        for batch,proof in enumerate(proofs):
            assert proof['verified'] is True and proof['vectors_per_formula']==2148 and proof['total_comparisons']==proof['formula_count']*2148 and proof['random_seed']==SEEDS[scope]
            sub=f'{prefix}/verification/batch-{batch*128:04d}/';vf=sub+'vectors.txt';rtl=sub+'verification.v'
            assert hashlib.sha256(z.read(vf)).hexdigest()==proof['vectors_sha256'] and hashlib.sha256(z.read(rtl)).hexdigest()==proof['rtl_sha256']
            assert proof['v4_validation_override_sha256']==sha(repo/'isaforge/v4_validation.py')
            formulas=functions[batch*128:batch*128+proof['formula_count']];expr=[parse(f) for f in formulas]
            wrapper=[f"module verification_top(input wire [31:0] in0, in1, {', '.join(f'output wire [31:0] out_{i}' for i in range(len(formulas)))});"]
            wrapper.extend(f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(formulas)))
            wrapper.append('endmodule');wrapper.extend(render(f,f'candidate_{i}') for i,f in enumerate(formulas))
            assert z.read(rtl).decode()=='\n'.join(wrapper)
            vectorrows=z.read(vf).decode().splitlines();assert len(vectorrows)==2148
            for number,(line,(a,b)) in enumerate(zip(vectorrows,pairs)):
                fields=line.split();assert len(fields)==len(expr)+2 and all(re.fullmatch('[0-9a-f]{8}',v) for v in fields)
                values=[int(v,16) for v in fields];assert values[:2]==[a,b]
                expected=[oracle(e,a,b) for e in expr];assert values[2:]==expected,('oracle mismatch',scope,batch,number)
                comparisons+=len(expr)
            wrap=proof.get('signed_overflow_workaround_applied',False);wrap_incidents+=int(wrap)
            logfile=sub+('verification-wrapv.log' if wrap else 'verification.log')
            assert z.read(logfile).decode().strip()=='2148 vectors passed'
            if wrap:
                cross=sub+'yosys-boundary-cross-check/';assert hashlib.sha256(z.read(cross+'eval.log')).hexdigest()==proof['independent_yosys_log_sha256']
                observations=json.loads(z.read(cross+'observations.json'));expr=parse(proof['incident']['formula'])
                assert len(observations)==100 and all(r['result']==oracle(expr,r['in0'],r['in1']) for r in observations)
        for row in labels:
            f=row['formula'];metric=by_formula[f];sub=f'{prefix}/circuits/{hashlib.sha256(f.encode()).hexdigest()[:20]}/'
            declared=next(r for r in candidates if r['formula']==f)
            assert row['stratum']==declared['stratum'] and row['correctness_verified'] is True and row['measurement_source']=='rtl_synthesis'
            assert row['synthesis_tool']==metric['tool']==done['tool'] and metric['tool_sha256']==done['tool_sha256']
            assert row['rtl_sha256']==metric['rtl_sha256'] and z.read(sub+'candidate.v').decode()==render(f)
            assert row['lut4_count']==metric['ice40_lut4_count'] and row['carry_count']==metric['ice40_carry_count']
            assert json.loads(z.read(sub+'metrics.json'))==metric
            assert utc(release['released_at_utc'])<=utc(metric['measured_at_utc'])<=utc(done['completed_at_utc'])
            for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]:assert hashlib.sha256(z.read(sub+name)).hexdigest()==metric[key]
            netlist=json.loads(z.read(sub+'ice40-netlist.json'));cells=Counter(c['type'] for c in netlist['modules']['candidate'].get('cells',{}).values())
            assert dict(cells)==metric['ice40_cell_types'] and cells['SB_LUT4']==row['lut4_count'] and cells['SB_CARRY']==row['carry_count']
            counts.append({'formula':f,'lut4_count':cells['SB_LUT4'],'carry_count':cells['SB_CARRY']})
    assert comparisons==412416
    return candidates,y,{'status':'passed','scope':scope,'release_utc':release['released_at_utc'],'completed_utc':done['completed_at_utc'],
      'reviewed_commit':review['freeze_commit'],'raw_archive_sha256':sha(archive),'archive_members':len(entries),
      'independent_oracle_comparisons':comparisons,'verification_batches':[128,64],'verification_seed':SEEDS[scope],
      'wrap_incident_batches':wrap_incidents,'independently_recounted_netlists':192,'lut4_sum':int(y.sum()),'carry_sum':sum(c['carry_count'] for c in counts),'counts':counts}

def group_calibration(y,p,components):
    unique=sorted(set(components));scores={g:float(np.max((y-p)[components==g])) for g in unique};ordered=sorted(scores.values());rank=math.ceil((len(unique)+1)*.9)
    margin=None if rank>len(unique) else max(0.,ordered[rank-1])
    return {'group_count':len(unique),'rank':rank,'upper_margin_lut4':margin,'component_maximum_residuals':scores,
      'ranked_residual':None if rank>len(unique) else ordered[rank-1],'zero_clamp_applied':rank<=len(unique) and ordered[rank-1]<0,
      'ties_at_ranked_residual':None if rank>len(unique) else sum(v==ordered[rank-1] for v in ordered)}

def metric(y,p):
    ae=np.abs(p-y);positive=y>0;zero=y==0;ape=100*ae[positive]/y[positive]
    def ratio(x,n):return x/n if n else None
    caps={}
    for cap in CAPS:
        yes=y<=cap;pred=p<=cap;fa=int((pred&~yes).sum());fr=int((~pred&yes).sum())
        caps[str(cap)]={'true_accept_count':int((pred&yes).sum()),'true_reject_count':int((~pred&~yes).sum()),
          'false_accept_count':fa,'false_reject_count':fr,'true_feasible_count':int(yes.sum()),'true_infeasible_count':int((~yes).sum()),
          'predicted_feasible_count':int(pred.sum()),'false_accept_rate_among_true_infeasible':ratio(fa,int((~yes).sum())),
          'false_reject_rate_among_true_feasible':ratio(fr,int(yes.sum())),'infeasible_fraction_among_predicted_feasible':ratio(fa,int(pred.sum()))}
    return {'sample_count':len(y),'mae_lut4':float(ae.mean()),'rmsle':float(np.sqrt(np.mean((np.log1p(p)-np.log1p(y))**2))),
      'positive_mape_percent':float(ape.mean()) if len(ape) else None,'positive_median_ape_percent':float(np.median(ape)) if len(ape) else None,
      'positive_count':int(positive.sum()),'zero_count':int(zero.sum()),'zero_target_mae_lut4':float(ae[zero].mean()) if zero.any() else None,
      'cap_feasibility':caps,'signed_bias_lut4':float((p-y).mean()),'absolute_error_quantiles':{str(q):float(np.quantile(ae,q)) for q in (.5,.9,.95,.99)},
      'maximum_underprediction_lut4':float(max(0.,max(y-p)))}

def model_metrics(rows,y,predictions,group_map):
    p=aligned(rows,predictions,'predicted_lut4');s=np.array([r['stratum'] for r in rows]);g=np.array([group_map[r['formula']] for r in rows]);names=sorted(set(s))
    cells={name:metric(y[s==name],p[s==name]) for name in names};result={**metric(y,p),'by_stratum':cells,
      'by_component':{group:metric(y[g==group],p[g==group]) for group in sorted(set(g))},'macro_stratum_mae_lut4':float(np.mean([v['mae_lut4'] for v in cells.values()]))}
    if all('upper_lut4' in r for r in predictions):
        upper=np.array([np.inf if r['upper_lut4'] is None else r['upper_lut4'] for r in predictions]);finite=np.isfinite(upper);covered=y<=upper
        def bound(mask):
            slack=(upper-y)[mask];valid=finite[mask];groups=set(g[mask]);caps={}
            for cap in CAPS:caps[str(cap)]={'false_accept_count':int((mask&(upper<=cap)&(y>cap)).sum()),'false_reject_count':int((mask&(upper>cap)&(y<=cap)).sum()),
              'true_infeasible_count':int((mask&(y>cap)).sum()),'true_feasible_count':int((mask&(y<=cap)).sum()),'predicted_feasible_count':int((mask&(upper<=cap)).sum())}
            return {'candidate_coverage':float(covered[mask].mean()),'whole_component_coverage':float(np.mean([covered[g==q].all() for q in groups])),
              'component_count':len(groups),'finite_bound_fraction':float(valid.mean()),'mean_slack_lut4':float(slack.mean()) if valid.all() else None,
              'minimum_slack_lut4':float(slack.min()) if valid.all() else None,'finite_bounds_mean_slack_lut4':float(slack[valid].mean()) if valid.any() else None,'cap_decisions':caps}
        result['upper_bound']={**bound(np.ones(len(rows),bool)),'by_stratum':{n:bound(s==n) for n in names},
          'scope':'Observed complete synthetic components; exchangeability outside this grammar is unestablished.'}
    if all('outside_training_feature_ranges' in r and 'tree_disagreement_lut4' in r for r in predictions):
        out=np.array([r['outside_training_feature_ranges'] for r in predictions]);sd=[r['tree_disagreement_lut4'] for r in predictions]
        def domain(mask):
            values=np.array([v for v,keep in zip(sd,mask) if keep and v is not None]);return {'row_count':int(mask.sum()),
              'outside_training_range_row_count':int((out[mask]>0).sum()),'outside_training_range_dimension_sum':int(out[mask].sum()),
              'outside_training_range_dimensions_max':int(out[mask].max()),'tree_spread_available_count':len(values),
              'mean_tree_spread_lut4':float(values.mean()) if len(values) else None,'p95_tree_spread_lut4':float(np.quantile(values,.95)) if len(values) else None,
              'maximum_tree_spread_lut4':float(values.max()) if len(values) else None}
        result['tree_spread_and_domain']={'all':domain(np.ones(len(rows),bool)),'by_stratum':{n:domain(s==n) for n in names},
          'scope':'Tree spread and feature-range counts are descriptive; neither is a coverage guarantee.'}
    result['candidate_errors']=[{**r,'lut4_count':float(a),'predicted_lut4':float(b),'absolute_error_lut4':float(abs(b-a))} for r,a,b in zip(rows,y,p)]
    return result

def bootstrap(d,strata,groups):
    names=sorted(set(strata));rng=np.random.default_rng(2026101443);samples=np.zeros(10000);counts={};sizes={}
    assert len(names)==8
    for name in names:
        unique=sorted(set(groups[strata==name]));assert len(unique)>=8;assert all(set(strata[groups==g])=={name} for g in unique)
        sums=np.array([d[groups==g].sum() for g in unique]);n=np.array([(groups==g).sum() for g in unique]);counts[name]=len(unique);sizes[name]={str(g):int(k) for g,k in zip(unique,n)}
        draws=rng.integers(len(unique),size=(10000,len(unique)));samples+=np.sum(sums[draws],axis=1)/np.sum(n[draws],axis=1)/8
    return {'macro_stratum_mae_difference_lut4':float(np.mean([d[strata==n].mean() for n in names])),
      'descriptive_stratified_component_bootstrap_95_interval':np.quantile(samples,[.025,.975]).tolist(),'replicates':10000,'seed':2026101443,
      'component_counts_by_stratum':counts,'component_sizes_by_stratum':sizes,'empty_draw_rejection':False,
      'scope':'Descriptive paired whole-component resampling within eight fixed strata; conditional on synthetic grammar, not a population guarantee.'}

def estimator_digest(estimator):
    """Canonical independent tree state digest, excluding structured padding."""
    h=hashlib.sha256();h.update(json.dumps(estimator.get_params(),sort_keys=True,allow_nan=False).encode())
    assert hasattr(estimator,'estimators_'),'Expected fixed ExtraTrees ensemble'
    h.update(str(len(estimator.estimators_)).encode())
    for name in ('n_features_in_','n_outputs_'):
        h.update(name.encode());h.update(str(int(getattr(estimator,name))).encode())
    for tree in estimator.estimators_:
        h.update(json.dumps(tree.get_params(),sort_keys=True,allow_nan=False).encode())
        h.update(str((tree.n_features_in_,tree.n_outputs_,tree.tree_.n_features,tree.tree_.n_outputs)).encode())
        state=tree.tree_.__getstate__();h.update(str((state['max_depth'],state['node_count'])).encode())
        nodes=state['nodes']
        for name in nodes.dtype.names:
            values=np.ascontiguousarray(nodes[name]);h.update(name.encode());h.update(values.dtype.str.encode());h.update(str(values.shape).encode());h.update(values.tobytes())
        values=np.ascontiguousarray(state['values']);h.update(values.dtype.str.encode());h.update(str(values.shape).encode());h.update(values.tobytes())
    return h.hexdigest()

def audit(root,repo,scope,calibrated=False):
    sys.path.insert(0,str(repo));from isaforge.features import parse_formula
    from isaforge.rtl import generate_rtl
    tests=oracle_selfcheck(parse_formula)
    rows,y,raw=raw_stage(repo,root,scope,parse_formula,generate_rtl)
    point=read(root/'point-freeze.json');assert set(point['models'])==set(MODELS) and point['training_formula_count']==1665
    for e in point['files']:checked(e,root)
    if scope=='calibration':
        assert not (root/'corpus/test/label-release.json').exists(),'Test released before calibration audit complete'
    # Recheck reviewed git membership of point evidence without running evaluator.
    review=read(root/'corpus'/scope/'label-approval.json');entries=[{'path':'point-freeze.json','sha256':sha(root/'point-freeze.json')},*point['files']]
    for entry in point['models'].values():entries.extend(entry[k] for k in ('artifact','schema','calibration_predictions','test_predictions'))
    for e in entries:
        p=checked(e,root);data=subprocess.run(['git','show',review['freeze_commit']+':'+p.relative_to(repo).as_posix()],cwd=repo,capture_output=True)
        assert data.returncode==0 and hashlib.sha256(data.stdout).hexdigest()==e['sha256'],('reviewed commit bytes',p)
    predictions={name:{s:read(checked(entry[s+'_predictions'],root)) for s in ('calibration','test')} for name,entry in point['models'].items()}
    for name in MODELS:aligned(rows,predictions[name][scope],'predicted_lut4')
    groups=read(root/'corpus'/scope/'components.json')['component_by_formula'];component_ids=np.array([groups[r['formula']] for r in rows])
    result={'status':'passed','stage':scope,'source_sha256':sha(Path(__file__)),'oracle_selfchecks':tests,'raw_measurement_audit':raw,
      'point_freeze_sha256':sha(root/'point-freeze.json'),'point_reviewed_files':len(entries),'fresh_labels_used_for_fitting':0,
      'calibration':{},'limits':['Finite sampled verification does not prove all-input equivalence.',
      'Synthetic structural groups are not application families or a proof of exchangeability.',
      'Old control bounds retain earlier V5 calibration; new models alone receive fresh V6 calibration.']}
    if scope=='calibration':
        for name in NEW:
            p=aligned(rows,predictions[name][scope],'predicted_lut4');result['calibration'][name]=group_calibration(y,p,component_ids)
    if calibrated or scope=='test':
        import joblib
        freeze=read(root/'calibration-freeze.json');assert freeze['point_freeze']['sha256']==sha(root/'point-freeze.json') and freeze['new_fits']==0 and freeze['test_labels_read'] is False
        assert freeze['schema']=='isaforge-v6-calibration-freeze-v1' and set(freeze['models'])==set(NEW) and freeze['alpha']==.1
        assert checked(freeze['point_freeze'],root)==root/'point-freeze.json'
        calfolder=root/'corpus/calibration';caldone=read(calfolder/'completion.json');calattempt=calfolder/caldone['attempt']
        assert freeze['calibration_dataset_sha256']==caldone['dataset_sha256']
        assert utc(read(calfolder/'label-release.json')['released_at_utc'])<=utc(freeze['started_at_utc'])<=utc(freeze['frozen_at_utc'])
        frozen_paths={checked(entry,root) for entry in freeze['files']}
        required={root/'point-freeze.json',*(calfolder/n for n in ('label-release.json','label-approval.json','completion.json','raw-evidence.json','raw-evidence.zip')),
                  *(calattempt/n for n in ('completion.json','dataset.json','unique-measurements.json','verification.json')),repo/'scripts/evaluate_v6.py',repo/'scripts/measure_v6.py'}
        assert required<=frozen_paths
        result['calibration_frozen_evidence_records_checked']=len(freeze['files'])
        if scope=='test':
            calrows,caly,calraw=raw_stage(repo,root,'calibration',parse_formula,generate_rtl)
            calgroups=read(root/'corpus/calibration/components.json')['component_by_formula'];ids=np.array([calgroups[r['formula']] for r in calrows])
        else:calrows,caly,ids=rows,y,component_ids
        for name in NEW:
            entry=freeze['models'][name];schema=read(checked(entry['schema'],root));oldschema=read(checked(point['models'][name]['schema'],root))
            assert schema['artifact_sha256']==entry['artifact']['sha256'] and schema['calibration']==entry['calibration']
            for key in set(oldschema)-{'artifact_sha256','calibration'}:assert schema[key]==oldschema[key],('calibration changed schema',name,key)
            assert utc(freeze['started_at_utc'])<=utc(entry['frozen_at_utc'])<=utc(freeze['frozen_at_utc'])
            original=joblib.load(checked(point['models'][name]['artifact'],root));updated=joblib.load(checked(entry['artifact'],root))
            assert type(original) is type(updated)
            assert estimator_digest(original.estimator)==estimator_digest(updated.estimator)
            if original.semantic_expert is None:assert updated.semantic_expert is None
            else:
                assert type(original.semantic_expert) is type(updated.semantic_expert)
                for key,value in vars(original.semantic_expert).items():
                    other=getattr(updated.semantic_expert,key)
                    if key=='estimator':assert estimator_digest(value)==estimator_digest(other)
                    else:assert value==other
            for field in ('feature_columns','feature_minimum','feature_maximum','training_formula_count','training_provenance','kind','semantic_source','frozen_tool','runtime_source_sha256'):assert getattr(original,field)==getattr(updated,field)
            expected=group_calibration(caly,aligned(calrows,predictions[name]['calibration'],'predicted_lut4'),ids);result['calibration'][name]=expected
            assert updated.calibration==schema['calibration'] and updated.calibration['status']=='calibrated' and updated.calibration['alpha']==.1
            for key in ('group_count','rank','upper_margin_lut4'):assert updated.calibration[key]==freeze['models'][name]['calibration'][key]==expected[key]
            for s in ('calibration','test'):
                current=read(checked(freeze['models'][name][s+'_predictions'],root));old=predictions[name][s];assert len(current)==len(old)
                for a,b in zip(current,old):
                    for k in ('benchmark','candidate_id','formula','predicted_lut4','tree_disagreement_lut4','outside_training_feature_ranges','routed_expert'):assert a[k]==b[k]
                    margin=expected['upper_margin_lut4'];assert a['upper_lut4']==(None if margin is None else a['predicted_lut4']+margin)
                predictions[name][s]=current
            result['calibration'][name]['estimator_and_semantic_expert_weights_unchanged']=True
            result['calibration'][name]['all_384_points_spread_domain_routes_unchanged']=True
        result['calibration_freeze_sha256']=sha(root/'calibration-freeze.json')
    if scope=='test':
        evaluation=read(root/'evaluation.json');assert evaluation['test_dataset_sha256']==read(root/'corpus/test/completion.json')['dataset_sha256']
        assert evaluation['point_freeze_sha256']==sha(root/'point-freeze.json') and evaluation['calibration_freeze_sha256']==sha(root/'calibration-freeze.json')
        models={name:model_metrics(rows,y,predictions[name]['test'],groups) for name in MODELS};close(models,evaluation['models'])
        p=aligned(rows,predictions['mapping_v6']['test'],'predicted_lut4');base=aligned(rows,predictions['dual_graph']['test'],'predicted_lut4')
        strata=np.array([r['stratum'] for r in rows]);d=np.abs(p-y)-np.abs(base-y);paired=bootstrap(d,strata,component_ids);close(paired,evaluation['primary_paired_comparison'])
        result.update(models=models,primary_paired_comparison=paired,
          primary_improvement_percent=100*(models['dual_graph']['macro_stratum_mae_lut4']-models['mapping_v6']['macro_stratum_mae_lut4'])/models['dual_graph']['macro_stratum_mae_lut4'],
          mapping_smaller_error_count=int((d<0).sum()),ties=int((d==0).sum()),mapping_larger_error_count=int((d>0).sum()),
          primary_macro_contributions_by_stratum={s:float(d[strata==s].mean()/8) for s in sorted(set(strata))})
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--scope',choices=('calibration','test'),required=True);p.add_argument('--calibrated',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.root.resolve(),a.repo.resolve(),a.scope,a.calibrated);a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('models','raw_measurement_audit')},indent=2))
