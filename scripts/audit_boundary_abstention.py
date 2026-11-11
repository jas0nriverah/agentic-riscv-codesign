#!/usr/bin/env python3
"""Independent zero-fit same-chain abstention audit. No fitting/native jobs.

Reuses sealed forest provenance; independently replays input-only support,
points, selection, metrics, chronology, vectors and mapped-cell evidence.
"""
from __future__ import annotations
import argparse
from collections import Counter
import itertools,json,math,random,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_targeted_coverage as old
import audit_boundary_coverage as feature
import audit_boundary_refinement as frozen
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/boundary-abstention';TEST=ROOT/'results/boundary-abstention-validation'
OLD=ROOT/'results/boundary-coverage'
CAPS=(32,64,128);TOL=1e-10
NAME='boundary_abstention';LEARNED='boundary_coverage_only';STRUCTURAL='boundary_structural';CURRENT='incumbent_signed';RELEASE='budget_release_compound_only'
CANDIDATES=('boundary_augmented','boundary_coverage_only')
COUNTS={**feature.COUNTS,'consumed-ninth-general32':32,'consumed-ninth-conditional9':9}


def check_bindings(mapping,root=ROOT):
 for p,h in mapping.items():assert sha(root/p)==h,p


def preserved():
 s=read(OUT/'auditor-prior-artifacts.json');check_bindings(s['files']);g=read(ROOT/s['goal_ledger']['path']);g.pop('status',None);assert g==s['goal_ledger']['protected_content']
 assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==s['submodules'];return len(s['files'])


def receipt(path,body,write=False):
 body={'schema':'independent-boundary-abstention-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
 if write:
  with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
 else:
  saved=read(path);actual=dict(body)
  for d in (saved,actual):d.pop('audited_at_utc',None)
  assert saved==actual,'Receipt replay differs:'+str(path)
 return body


def cells(formula):
 result=[]
 for data,control,post,outer in feature.ast_chains(formula):
  span=feature.ast_unknown_shape(data)[0];op=outer[0] if isinstance(outer,tuple) else outer
  if op not in ('and','or','xor') and span>16:continue
  shared=len(feature.ast_nonleaf_subtrees(data)&feature.ast_nonleaf_subtrees(post))
  result.append({'unknown_span':span,'shared_nonleaf_count':shared,'outer_operator':op,'cell':('narrow' if span<=16 else 'wide')+('_shared' if shared else '_unshared')})
 return result


def support():
 formulas=[r['formula'] for r in read(OLD/'training-manifest.json')['rows']];counts=Counter();eligible=chains=0
 for formula in formulas:
  c=cells(formula);eligible+=bool(c);chains+=len(c);counts.update(r['cell'] for r in c)
 result={'training_formula_count':len(formulas),'eligible_formula_count':eligible,'eligible_chain_count':chains,'cell_counts':dict(sorted(counts.items())),'supported_cells':sorted(counts),'input_only':True}
 assert result==read(OUT/'support-cells.json') and result['cell_counts']=={'narrow_shared':4,'narrow_unshared':8,'wide_unshared':20}
 mixed='xor(add(sra(slli(andi(addi(xori(in0,7),11),255),24),andi(xori(in1,13),1)),sra(addi(xori(in1,13),7),in0)),or(in0,in1))'
 assert [r['cell'] for r in cells(mixed)]==['narrow_unshared','wide_shared']
 assert not all(r['cell'] in counts for r in cells(mixed))
 return result


_MODELS=None

def models():
 global _MODELS
 if _MODELS is None:
  import joblib
  a=read(OLD/'audit.json');p=read(OLD/'protocol.json');seal=read(OLD/'model-freeze.json');assert a['status']=='pass' and a['zero_consumed_evaluation_labels_fitted'] and a['protocol_sha256']==sha(OLD/'protocol.json');check_bindings(seal['files_sha256'],OLD)
  _MODELS={k:joblib.load(OLD/(k+'.joblib')) for k in ('coverage','augmented')}
  for k,m in _MODELS.items():assert m.n_features_in_==(217 if k=='coverage' else 233) and len(m.estimators_)==300 and all(m.get_params()[n]==v for n,v in p['policy']['configuration'].items())
 return _MODELS


def matrix(features):
 import numpy as np
 columns=read(OLD/'protocol.json')['base_columns'];x=np.asarray([r['values'] for r in features['records']],dtype=float)[:,[features['columns'].index(n) for n in columns]];assert np.isfinite(x).all();return x


def points(row,features):
 import numpy as np
 values,routes,details=frozen.points(row,features);x=matrix(features);raw={};caps={};scope=[feature.ast_learning_scope(f) for f in row['formulas']]
 for n,k in zip(CANDIDATES,('augmented','coverage')):
  xx=np.hstack([x,np.asarray([feature.ast_features(f) for f in row['formulas']])]) if k=='augmented' else x
  raw[n]=models()[k].predict(xx).tolist();out=[];limits=[]
  for s,p,r,active in zip(values[CURRENT],values[STRUCTURAL],raw[n],scope):
   c=[cap for cap in CAPS if active and s<=cap<p and r<=cap];out.append(min(c) if c else p);limits.append(c)
  values[n]=out;caps[n]=limits
 known=set(support()['supported_cells']);guard=[];result=[]
 for f,learned,previous in zip(row['formulas'],values[LEARNED],values[STRUCTURAL]):
  chain=cells(f);allowed=bool(chain) and all(r['cell'] in known for r in chain);p=learned if allowed else previous;result.append(p)
  guard.append({'chains':chain,'all_cells_supported':allowed,'unsupported_cells':sorted({r['cell'] for r in chain if r['cell'] not in known}),'blocked_caps':[c for c in CAPS if learned<=c<p],'supported_new_caps':[c for c in CAPS if p<=c<previous]})
 values[NAME]=result
 return values,routes,{**details,'learning_scope':scope,'learned_raw_lut4':raw,'learned_supported_caps_lut4':caps,'coverage_guard':guard}


def metrics(y,values):
 m={n:feature.prior.metrics(y,v) for n,v in values.items()};p=m[NAME]
 m['checks']={'accuracy_no_worse':{r:feature.accuracy(m[r],p) for r in (RELEASE,STRUCTURAL,LEARNED)},
  'caps':{str(c):{'false_accept_no_worse_release':p['caps'][str(c)]['false_accept']<=m[RELEASE]['caps'][str(c)]['false_accept'],'false_reject_no_worse_signed':p['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject']} for c in CAPS},
  'maximum_underprediction_no_worse':all(p['maximum_underprediction_lut4']<=m[r]['maximum_underprediction_lut4']+TOL for r in (RELEASE,STRUCTURAL,LEARNED,CURRENT)),
  'pointwise_bounds':all(s<=l<=g<=p<=r for s,l,g,p,r in zip(values[CURRENT],values[LEARNED],values[NAME],values[STRUCTURAL],values[RELEASE])),
  'events':{r:feature.prior.cap_events(values[r],values[NAME],y) for r in (CURRENT,RELEASE,STRUCTURAL,LEARNED)}}
 return m


def passed(c):return all(all(v.values()) for v in c['accuracy_no_worse'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']


def panel_sources():
 result=feature.panel_sources();folder=ROOT/'results/boundary-coverage-validation';r=read(folder/'candidates.json');l=read(folder/'labels.json');f=read(folder/'features.json');p=read(OLD/'fresh-predictions.json')
 for name,key in (('consumed-ninth-general32','general_selected_indices'),('consumed-ninth-conditional9','conditional_selected_indices')):
  ix=p[key];result[name]=({'candidate_ids':[r[i]['candidate_id'] for i in ix],'formulas':[r[i]['formula'] for i in ix],'actual_lut4':[l[i]['lut4'] for i in ix]},{'columns':f['columns'],'records':[f['records'][i] for i in ix]})
 return result


def identity_audit():
 h=set(read(TEST/'historical-formulas.json'));required=set(read(ROOT/'results/boundary-coverage-data/historical-formulas.json'));aliases=set()
 for folder,filename in (('boundary-coverage-data','candidates.json'),('boundary-coverage-validation','pool-candidates.json')):
  d=ROOT/'results'/folder;required.update(r['formula'] for r in read(d/filename))
  for r in read(d/'novelty.json')['comparisons']:aliases.update(r['forms'])
 assert required<=h;known=set().union(*(feature.prior.identity_keys(f) for f in h|aliases));skeleton={old.skeleton(f) for f in h};seen=set();rows=read(TEST/'pool-candidates.json');novel=read(TEST/'novelty.json');assert len(rows)==128 and novel['status']=='pass'
 for row,e in zip(rows,novel['comparisons']):
  assert e['candidate_id']==row['candidate_id'];keys=set().union(*(feature.prior.identity_keys(f) for f in {row['formula'],*e['forms']}));assert not keys&known and not keys&seen and old.skeleton(row['formula']) not in skeleton;seen.update(keys)
 return {'historical_formulas':len(h),'fresh_pool_rows':128,'known_or_within_identity_or_historical_skeleton_collisions':0,'all_last32_training_and128_pool_included':True}


def authenticate():
 p=read(OUT/'protocol.json');plan=read(TEST/'plan.json');pool=read(TEST/'pool-candidates.json')
 assert p['schema']=='isaforge-boundary-abstention-v1' and p['finite_candidates']==[NAME] and p['planned_fits']==p['maximum_fits']==p['native_jobs']==0 and p['retained_panels']==COUNTS and sum(COUNTS.values())==938 and p['gates']['tolerance']==TOL
 assert p['selection']['pool_count']==128 and p['selection']['general_count']==32 and p['selection']['unsupported_count']==8 and p['selection']['challenge_count']==88 and p['selection']['maximum_active']==16 and p['selection']['shared_controls']==8
 assert len(pool)==128 and [i for i,r in enumerate(pool) if r['cohort']=='general']==list(range(32)) and [i for i,r in enumerate(pool) if r['cohort']=='unsupported']==list(range(32,40)) and [i for i,r in enumerate(pool) if r['reserved_control']]==list(range(24,32))
 for section in ('sources_sha256','inputs_sha256'):check_bindings(p[section])
 assert plan['schema']=='boundary-abstention-pool128-v1' and plan['pool_count']==128 and plan['training_count']==0 and plan['maximum_selected_count']==56
 assert plan['policy']=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
 for section in ('sources','inputs','prior_inventory_sources'):check_bindings(plan[section])
 for r in read(TEST/'tools.json').values():assert sha(r['path'])==r['sha256']
 support();seal=read(OUT/'policy-freeze.json');assert seal['protocol_sha256']==sha(OUT/'protocol.json') and seal['new_fits']==0;check_bindings(seal['files_sha256'],OUT)
 assert not (OUT/'run-start.json').exists() and not list(OUT.glob('*.joblib'))
 return p


def bindings():
 files=[OUT/n for n in ('protocol.json','support-cells.json','policy-freeze.json','development-predictions.json','development-metrics.json','auditor-prior-artifacts.json','goal-at-freeze.json','goal-update-at-freeze.json')]+[TEST/n for n in ('plan.json','pool-candidates.json','novelty.json','historical-formulas.json','tools.json')]
 return {str(p.relative_to(ROOT)):sha(p) for p in files}


def preflight(write=False):
 p=authenticate();count=preserved();novel=identity_audit()
 if write:assert not any((TEST/n).exists() for n in ('pool-features.json','features.json','feature-attempt.json','label-attempt.json','labels.json','selection.json'))
 return receipt(TEST/'preflight-audit.json',{'bindings':bindings(),'scientific_artifacts_preserved':count,'identity_audit':novel,'reviewed_policy':p['policy'],'reviewed_selection':p['selection'],'reviewed_gates':p['gates'],'formula_only_training_support':support(),'no_new_features_labels_attempts_at_receipt':True,'new_fits':0,'reused_forest_provenance_audit_sha256':sha(OLD/'audit.json'),'mixed_chain_adversary_replayed':True},write)


def raw_audit(folder):
    rows=read(folder/'candidates.json');labels=read(folder/'labels.json');features=read(folder/'features.json')
    assert len(rows)==len(labels) and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels]
    manifest=read(folder/'raw-evidence-manifest.json');archive=folder/manifest['archive']
    assert sha(archive)==manifest['archive_sha256'];members={r['path']:r for r in manifest['files']}
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members)
        for name,row in members.items():
            body=z.read(name);assert digest(body)==row['sha256'] and len(body)==row['bytes']
        get=lambda n:z.read('raw/'+n)
        kind='test'
        feature_jobs=[j for j in read(TEST/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind]
        label_jobs=read(folder/'completion.json')['native_worker_jobs']
        for job in feature_jobs+label_jobs:
            phase=job['stage'];directory='verification' if phase=='verify' else phase+'s/'+str(job['index'])
            assert json.loads(get(directory+'/worker.json'))==job
            assert digest(get(directory+'/worker.log'))==job['log_sha256']
        proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148
        assert proof['random_seed']==read(TEST/'plan.json')['proof_random_seed']
        assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256']
        assert proof['total_comparisons']==2148*len(rows)
        boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1];rng=random.Random(proof['random_seed'])
        expected=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        parsed=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()]
        assert len(parsed)==2148 and [(r[0],r[1]) for r in parsed]==expected
        trees=[old.parse(r['formula']) for r in rows]
        for a,b,*targets in parsed:assert [old.evaluate(t,a,b) for t in trees]==targets
        assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
        for i,(row,label) in enumerate(zip(rows,labels)):
            assert label['status']=='complete' and label['formula']==row['formula']
            assert json.loads(get(f'labels/{i}/result.json'))==label
            net=get(f'labels/{i}/ice40-netlist.json');assert digest(net)==label['netlist_sha256']
            counts=Counter(c['type'] for c in json.loads(net)['modules']['candidate']['cells'].values())
            assert counts['SB_LUT4']==label['lut4'] and counts['SB_CARRY']==label['carry']
            source=get(f'labels/{i}/candidate.v').decode();assert digest(source.encode())==label['rtl_sha256']
            assert source.replace('module candidate(',f'module candidate_{i}(') in rtl
            body=get(f'labels/{i}/metrics.json');assert digest(body)==label['metrics_sha256']
            m=json.loads(body);assert m['ice40_lut4_count']==label['lut4'] and m['ice40_carry_count']==label['carry'] and m['measurement_source']=='rtl_synthesis'
            assert 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
            assert features['records'][i]==read(folder/'pool-features.json')['records'][read(folder/'selection.json')['selected_pool_indices'][i]]
        pool=read(folder/'pool-features.json');assert len(pool['records'])==128
        for i,record in enumerate(pool['records']):assert json.loads(get(f'features/{i}/result.json'))==record
    return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'all_pool_feature_results_authenticated':128,'independent_RV32_vector_comparisons':2148*len(rows),'native_job_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}



def chronology(final=False):
    features=read(TEST/'feature-completion.json');reports=[features]
    assert old.job_audit(features)['jobs']==128 and Counter(j['stage'] for j in features['native_worker_jobs'])=={'feature':128}
    assert read(TEST/'preflight-audit.json')['audited_at_utc']<read(TEST/'feature-attempt.json')['started_at_utc']
    if final:
        labels=read(TEST/'completion.json');reports.append(labels)
        selected_count=len(read(TEST/'candidates.json'))
        assert old.job_audit(labels)['jobs']==selected_count+1 and Counter(j['stage'] for j in labels['native_worker_jobs'])=={'verify':1,'label':selected_count}
        assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
        assert max(j['finished_at_utc'] for j in features['native_worker_jobs'])<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
        assert max(j['finished_at_utc'] for j in labels['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in labels['native_worker_jobs'] if j['stage']=='label')
        assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
    events=[event for report in reports for j in report['native_worker_jobs'] for event in ((j['started_at_utc'],1),(j['finished_at_utc'],-1))];active=peak=0
    for _,delta in sorted(events,key=lambda x:(x[0],x[1])):active+=delta;peak=max(peak,active)
    assert active==0 and peak<=2
    total=sum(r['native_elapsed_seconds'] for r in reports);assert total<=300 and math.isclose(reports[-1]['total_native_elapsed_seconds'],total,abs_tol=1e-9)
    return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'total_native_seconds':total,'recorded_worker_peak':peak,'new_fits':0}




def development():
 saved=read(OUT/'development-predictions.json');stored=read(OUT/'development-metrics.json');computed={}
 assert set(saved)==set(COUNTS)
 for name,(row,f) in panel_sources().items():
  assert len(row['actual_lut4'])==COUNTS[name]
  for k,v in row.items():assert saved[name][k]==v,(name,k)
  values,routes,details=points(row,f);assert values==saved[name]['models'] and routes==saved[name]['routes'],name
  for k,v in details.items():assert saved[name][k]==v,(name,k)
  computed[name]=metrics(row['actual_lut4'],values);old.compare_metric(stored['panels'][name],computed[name])
 def sub(name,ix):
  r=saved[name];assert ix;return metrics([r['actual_lut4'][i] for i in ix],{n:[v[i] for i in ix] for n,v in r['models'].items()})
 def group(name,folder,template):
  ix=[i for i,r in enumerate(read(ROOT/'results'/folder/'candidates.json')) if r['template']==template];assert len(ix)==4;return sub(name,ix)
 named={'arithmetic_stress32':computed['arithmetic-stress'],'signed_dual_arithmetic4':group('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),'signed_add_boolean4':group('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),'compound_signed_add_xor4':group('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_add_xor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_xordata_addxor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_xordata_addxor')}
 r=saved['consumed-sixth-broad40'];named['broad_compound32']=sub('consumed-sixth-broad40',[i for i,f in enumerate(r['formulas']) if feature.prior.predicates(f)[0]])
 r=saved['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][RELEASE][i]];fa=[i for i,y in enumerate(r['actual_lut4']) if any(r['models']['boundary_median'][i]<=c<r['models'][RELEASE][i] and y>c for c in CAPS)];assert len(fr)==8 and len(fa)==2
 named['eight_corrected_fr']=sub('consumed-seventh-conditional18',fr);named['two_previous_new_fa']=sub('consumed-seventh-conditional18',fa)
 r=saved['consumed-eighth-general32'];four=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][STRUCTURAL][i]];assert len(four)==4;named['four_confident_fr']=sub('consumed-eighth-general32',four);named['prior_active16']=sub('consumed-eighth-conditional24',list(range(16)))
 safe=saved['consumed-ninth-general32'];si=[i for i,y in enumerate(safe['actual_lut4']) if y<=128<safe['models'][STRUCTURAL][i] and safe['models'][LEARNED][i]<=128];assert len(si)==1 and safe['actual_lut4'][si[0]]==122;named['safe122']=sub('consumed-ninth-general32',si)
 bad=saved['consumed-ninth-conditional9'];bi=[i for i,y in enumerate(bad['actual_lut4']) if y>128 and bad['models'][LEARNED][i]<=128<bad['models'][STRUCTURAL][i]];assert len(bi)==1 and bad['actual_lut4'][bi[0]]==159;named['unsafe159']=sub('consumed-ninth-conditional9',bi)
 for k,v in named.items():old.compare_metric(stored['named_regressions'][k],v)
 req=read(OLD/'development-metrics.json')['required_rejection_cases'];lookup={cid:r['models'][NAME][i] for r in saved.values() for i,cid in enumerate(r['candidate_ids'])};assert len(req)==30
 gates={'all_fifteen_retained_panels_pass':all(passed(m['checks']) for m in computed.values()),'all_named_subsets_preserved':all(passed(m['checks']) for m in named.values()),'all_thirty_required_repairs_preserved':all(lookup[r['candidate_id']]<=r['cap'] for r in req),'safe122_preserved':all(safe['models'][NAME][i]<=128 for i in si),'unsafe159_rejected':all(bad['models'][NAME][i]>128 for i in bi)};gates['development_gate_passed']=all(gates.values())
 assert stored['gates']=={NAME:gates} and stored['selected_candidate']==(NAME if gates['development_gate_passed'] else None) and stored['evaluated_candidate']==NAME and stored['retained_metric_rows']==938 and stored['retained_circuit_records']==922 and stored['shared_controls']==16 and stored['no_pooled_metric']
 return {'gates':gates,'selected_candidate':stored['selected_candidate'],'evaluated_candidate':NAME,'retained_metric_rows':938,'retained_circuit_records':922,'named_subsets':list(named),'required_repairs_preserved':sum(lookup[r['candidate_id']]<=r['cap'] for r in req),'safe122':{'actual_lut4':122,'prediction':safe['models'][NAME][si[0]]},'unsafe159':{'actual_lut4':159,'prediction':bad['models'][NAME][bi[0]]},'development_predictions_replayed':938*8,'no_pooled_metric':True}


def feature_freshness():
 import numpy as np
 formulas,h=feature.historical_records();blocks=[h]
 for path in (ROOT/'results/boundary-coverage-data/features.json',ROOT/'results/boundary-coverage-validation/features.json',ROOT/'results/boundary-coverage-validation/pool-features.json'):
  f=read(path);blocks.append(matrix(f));formulas.extend(r['formula'] for r in f['records'])
 h=np.vstack(blocks);assert h.shape==(3235,217) and len(formulas)==3235
 pool=read(TEST/'pool-candidates.json');x=matrix(read(TEST/'pool-features.json'));assert x.shape==(128,217);reports={}
 for kind in ('coverage','augmented'):
  hist=np.hstack([h,np.asarray([feature.ast_features(f) for f in formulas])]) if kind=='augmented' else h
  values=np.hstack([x,np.asarray([feature.ast_features(r['formula']) for r in pool])]) if kind=='augmented' else x
  known={tuple(float(v) for v in row) for row in hist};groups={};rep=[];keys=[tuple(float(v) for v in row) for row in values]
  for i,key in enumerate(keys):groups.setdefault(key,[]).append(i);rep.append(groups[key][0])
  reports[kind]={'historical_unique_count':len(known),'historical_matches':[i for i,k in enumerate(keys) if k in known],'cluster_representatives':rep,'duplicate_clusters':[v for v in groups.values() if len(v)>1]}
 return {'historical_rows':3235,'fitted_rows':1857,'evaluated_circuit_records':922,'prior_pool_rows':[200,128,128],'representations':reports,'equality':'Exact float64 numeric217/233 tuples; labels unused.'}


def select(pool,values,details,fresh):
 general=list(range(32));unsupported=list(range(32,40));controls=list(range(24,32));fixed=general+unsupported;reps={k:r['cluster_representatives'] for k,r in fresh['representations'].items()};history=set().union(*(r['historical_matches'] for r in fresh['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()}
 raw=[i for i,r in enumerate(pool) if r['cohort']=='challenge' and any(values[NAME][i]<=c<values[STRUCTURAL][i] for c in CAPS)];collision=[i for i in raw if any(reps[k][i] in seen[k] for k in reps)];eligible=[i for i in raw if i not in history and i not in collision];groups={}
 for i in eligible:groups.setdefault(pool[i]['template'],[]).append(i)
 active=[];skipped=[]
 while len(active)<16 and any(groups.values()):
  for t in sorted(groups):
   if len(active)>=16:break
   while groups[t] and any(reps[k][groups[t][0]] in seen[k] for k in reps):skipped.append(groups[t].pop(0))
   if groups[t]:
    i=groups[t].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 selected=fixed+active;s={'general_pool_indices':general,'unsupported_pool_indices':unsupported,'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in history],'fixed_collision_active_pool_indices':collision,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':selected};checks={}
 for k,r in fresh['representations'].items():
  keys=r['cluster_representatives'];checks[k+'_fixed_fresh']=not bool(set(r['historical_matches'])&set(fixed));checks[k+'_fixed_unique']=len({keys[i] for i in fixed})==40;checks[k+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[NAME][i]<=c<values[STRUCTURAL][i] for i in active) for c in CAPS};blocked=[i for i in unsupported if details['coverage_guard'][i]['blocked_caps']]
 checks.update({'at_least_four_supported_actions':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128_action':caps['128']>=1,'at_least_one_fixed_blocked_override':len(blocked)>=1})
 cov={'pool_count':128,'general_count':32,'unsupported_count':8,'shared_control_count':8,'raw_active_count':len(raw),'eligible_active_count':len(eligible),'selected_active_count':len(active),'selected_templates':templates,'supported_action_caps':caps,'blocked_override_count':len(blocked),'blocked_unsupported_pool_indices':blocked,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}
 return s,cov


def fresh_points():
 authenticate();dev=development();pool=read(TEST/'pool-candidates.json');f=read(TEST/'pool-features.json');stored=read(OUT/'pool-predictions.json');row={'formulas':[r['formula'] for r in pool]};values,routes,details=points(row,f)
 assert stored['models']==values and stored['routes']==routes and stored['candidate_ids']==[r['candidate_id'] for r in pool] and stored['formulas']==row['formulas'] and stored['templates']==[r['template'] for r in pool]
 for k,v in details.items():assert stored[k]==v,k
 freshness=feature_freshness();assert freshness==read(OUT/'feature-freshness.json');selection,coverage=select(pool,values,details,freshness);s=read(TEST/'selection.json')
 for k,v in selection.items():assert s[k]==v,k
 assert s['coverage']==coverage and s['labels_present'] is False and s['pool_predictions_sha256']==sha(OUT/'pool-predictions.json')
 ix=selection['selected_pool_indices'];saved=read(OUT/'fresh-predictions.json');assert read(TEST/'candidates.json')==[pool[i] for i in ix] and read(TEST/'features.json')=={'columns':f['columns'],'records':[f['records'][i] for i in ix]}
 for k in ('candidate_ids','formulas','templates','routes',*details):
  if isinstance(stored[k],dict):assert saved[k]=={n:[v[i] for i in ix] for n,v in stored[k].items()},k
  else:assert saved[k]==[stored[k][i] for i in ix],k
 assert saved['models']=={n:[v[i] for i in ix] for n,v in values.items()}
 assert saved['general_selected_indices']==list(range(32)) and saved['unsupported_selected_indices']==list(range(32,40)) and saved['active_selected_indices']==list(range(40,len(ix))) and saved['shared_control_selected_indices']==list(range(24,32)) and saved['conditional_selected_indices']==list(range(40,len(ix)))+list(range(24,32))
 assert saved['selection_coverage']==coverage and saved['selected_candidate']==stored['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==stored['evaluated_candidate']==NAME
 seal=read(OUT/'fresh-point-freeze.json');bridge=read(TEST/'point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0 and bridge['target_label_jobs']==0;check_bindings(seal['bindings']);check_bindings(bridge['bindings'])
 assert read(OUT/'policy-freeze.json')['frozen_at_utc']<stored['created_at_utc']<s['frozen_at_utc']<seal['frozen_at_utc']
 return saved,dev,freshness


def cached_inference(saved):
 c=read(OUT/'cached-inference-check.json');assert c['model']==NAME and c['selected_candidate']==saved['selected_candidate'] and c['fits']==c['native_jobs']==0 and c['calibration_status']=='uncalibrated' and c['upper_lut4'] is None
 for k in ('candidate_ids','formulas','models','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap','learning_scope','learned_raw_lut4','learned_supported_caps_lut4','coverage_guard'):assert c[k]==saved[k],k
 assert c['predicted_lut4']==saved['models'][NAME] and c['protocol_sha256']==sha(OUT/'protocol.json') and c['features_sha256']==sha(TEST/'features.json') and c['candidates_sha256']==sha(TEST/'candidates.json')
 return {'artifact_sha256':sha(OUT/'cached-inference-check.json'),'eight_model_predictions_replayed':8*len(saved['candidate_ids']),'uncalibrated':True,'fits':0,'native_jobs':0}


def prelabel(write=False):
 authenticate();count=preserved();preflight(False);jobs=chronology();saved,dev,fresh=fresh_points()
 if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 files=[OUT/n for n in ('feature-freshness.json','pool-predictions.json','fresh-point-freeze.json','fresh-predictions.json','cached-inference-check.json')]+[TEST/n for n in ('selection.json','candidates.json','features.json','point-freeze.json','pool-features.json','feature-completion.json')]
 return receipt(TEST/'prelabel-audit.json',{'bindings':{**bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in files}},'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,'fresh_predictions_replayed':8*len(saved['candidate_ids']),'all_pool_predictions_replayed':1024,'feature_freshness':fresh,'selection_coverage':saved['selection_coverage'],'development':dev,'cached_inference':cached_inference(saved),'native_accounting_to_date':jobs,'unchanged_forest_provenance_audit_sha256':sha(OLD/'audit.json'),'weights_all_pool_points_exact_selected_subset_before_labels':True,'general32_and_unsupported8_fixed_before_predictions':True,'shared_controls_not_independent':True,'no_pooled_metric':True},write)


def final_audit(write=False):
 authenticate();count=preserved();prelabel(False);jobs=chronology(True);saved,dev,fresh=fresh_points();rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels];y=[r['lut4'] for r in labels];scored=read(OUT/'fresh-metrics.json')
 def sub(ix):return metrics([y[i] for i in ix],{n:[v[i] for i in ix] for n,v in saved['models'].items()})
 general=sub(saved['general_selected_indices']);unsupported=sub(saved['unsupported_selected_indices']);conditional=sub(saved['conditional_selected_indices']);active=sub(saved['active_selected_indices']) if saved['active_selected_indices'] else None
 fields=old.compare_metric(scored['models'],general)+old.compare_metric(scored['unsupported_models'],unsupported)+old.compare_metric(scored['conditional_models'],conditional)
 if active:fields+=old.compare_metric(scored['active_subgroup'],active)
 else:assert scored['active_subgroup'] is None
 checks={'coverage':saved['selection_coverage'],'general_no_loss':passed(general['checks']),'general_strict_signed':feature.accuracy(general[CURRENT],general[NAME],True),'general_strict_fa_gain_signed':sum(general[NAME]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),'unsupported_passes':passed(unsupported['checks']),'conditional_full_passes':passed(conditional['checks']),'active_subset_passes':bool(active and passed(active['checks'])),'unsupported_exact_previous':all(saved['models'][NAME][i]==saved['models'][STRUCTURAL][i] for i in saved['unsupported_selected_indices'])}
 ok=checks['coverage']['passed'] and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['unsupported_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes'] and checks['unsupported_exact_previous'];eligible=ok and dev['selected_candidate']==NAME
 gates={NAME:{'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates']['development_gate_passed'],'eligible':eligible}}
 assert scored['gates']==gates and scored['scoped_experimental_eligibility']==eligible and scored['selected_candidate']==dev['selected_candidate'] and scored['evaluated_candidate']==NAME
 assert scored['selection_coverage']==saved['selection_coverage'] and scored['general_count']==32 and scored['unsupported_count']==8 and scored['active_count']==len(saved['active_selected_indices']) and scored['conditional_count']==len(saved['conditional_selected_indices']) and scored['shared_controls']==8 and scored['unique_label_count']==len(y) and scored['fits']==scored['native_jobs']==0 and scored['no_pooled_metric'] and scored['fresh_labels_sha256']==sha(TEST/'labels.json')
 def decisions(ix):
  out={}
  for ref in (CURRENT,RELEASE,STRUCTURAL,LEARNED):
   caps={}
   for cap in CAPS:
    events=[]
    for i in ix:
     before=saved['models'][ref][i];after=saved['models'][NAME][i]
     if (before<=cap)==(after<=cap):continue
     event=('corrected_false_reject' if y[i]<=cap else 'new_false_accept') if after<=cap else ('new_false_reject' if y[i]<=cap else 'corrected_false_accept')
     events.append({'selected_index':i,'pool_index':read(TEST/'selection.json')['selected_pool_indices'][i],'candidate_id':rows[i]['candidate_id'],'template':rows[i]['template'],'formula':rows[i]['formula'],'actual_lut4':y[i],'reference_lut4':before,'prediction_lut4':after,'event':event,'coverage_guard':saved['coverage_guard'][i]})
    feasible=sum(y[i]<=cap for i in ix);caps[str(cap)]={'actual_feasible':feasible,'actual_infeasible':len(ix)-feasible,'changed_decisions':events}
   out[ref]=caps
  return out
 scientific={'all_fifteen_retained_panels938_metric_rows922_records_preserved':dev['gates']['all_fifteen_retained_panels_pass'],'all_named_accuracy_FA_FR_tail_subgroups_preserved':dev['gates']['all_named_subsets_preserved'],'all_thirty_known_repairs_preserved':dev['gates']['all_thirty_required_repairs_preserved'],'safe122_repair_preserved':dev['gates']['safe122_preserved'],'unsafe159_rejected':dev['gates']['unsafe159_rejected'],'fresh_general_strict_signed_accuracy_and_FA_gains':all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'],'fresh_general_no_loss_all_three_comparators_and_FR_signed':checks['general_no_loss'],'four_supported_actions_two_templates_including128':all(checks['coverage']['checks'][k] for k in ('at_least_four_supported_actions','at_least_two_templates','at_least_one_cap128_action')),'fixed_unsupported8_including_prediction_defined_blocked_override':checks['coverage']['checks']['at_least_one_fixed_blocked_override'],'fresh_supported_and_fixed_feature_novelty':all(v for k,v in checks['coverage']['checks'].items() if k.startswith(('coverage_','augmented_'))),'unsupported8_no_loss_and_FR_gates':checks['unsupported_passes'],'unsupported8_exact_previous':checks['unsupported_exact_previous'],'conditional_full_no_loss_and_FR_gates':checks['conditional_full_passes'],'active_only_no_loss_and_FR_gates':checks['active_subset_passes'],'no_new_fits_or_consumed_labels_fitted_existing_weights_authenticated':True,'policy_cohort_selection_features_and_gates_frozen_before_features_and_labels':True,'all128_predictions_and_selection_before_labels':True,'bounded300native_seconds_peak_two':jobs['total_native_seconds']<=300 and jobs['recorded_worker_peak']<=2,'prior_scientific_artifacts_preserved_goal_status_only_exception':count==len(read(OUT/'auditor-prior-artifacts.json')['files']),'independent_vector_netlist_chronology_cached_inference_audits_pass':True,'separate_populations_and_shared_controls_disclosed_no_pooling':True}
 assert all(scientific.values())==eligible
 raw=raw_audit(TEST)
 templates={t:sub([i for i,r in enumerate(rows) if r['template']==t]) for t in sorted({r['template'] for r in rows})}
 body={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'goal_ledger_status_only_mutable':True,'new_fits':0,'new_training_rows':0,'training_support':support(),'unchanged_forest_provenance_audit_sha256':sha(OLD/'audit.json'),'native_accounting':jobs,'identity_audit':identity_audit(),'feature_freshness':fresh,'fresh_raw_evidence':raw,'cached_inference':cached_inference(saved),'development':dev,'fresh_general32':general,'fresh_unsupported8':unsupported,'fresh_conditional_full':conditional,'fresh_active_only':active,'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':dev['selected_candidate'],'evaluated_candidate':NAME,'scoped_experimental_eligibility':eligible,'selection_coverage':saved['selection_coverage'],'pool_count':128,'selected_unique_label_count':len(y),'all_unselected_pool_inputs_features_predictions_retained':True,'shared_control_count':8,'shared_control_selected_indices':saved['shared_control_selected_indices'],'shared_controls_not_independent':True,'general_cap_decision_cases':decisions(saved['general_selected_indices']),'unsupported_cap_decision_cases':decisions(saved['unsupported_selected_indices']),'conditional_full_cap_decision_cases':decisions(saved['conditional_selected_indices']),'active_only_cap_decision_cases':decisions(saved['active_selected_indices']),'selected_numeric_fields_compared':fields,'development_predictions_replayed':938*8,'all_pool_predictions_replayed':1024,'selected_predictions_replayed':len(y)*8,'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':all(scientific.values()),'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,'false_acceptance_sum_unit':'circuit-budget events, not unique circuits; each population has per-cap actual feasible/infeasible denominators and changed-case identities.','mape_definition':'100*mean(abs(actual-predicted)/actual) over actual>0; zero-target rows remain in MAE, tail and cap denominators and are excluded only from MAPE.','mathematical_bounds':'signed<=learned217<=abstention<=previous_structural<=release. Abstention can restore prior false rejections; mandatory FR gates compare signed separately at each cap.','limitations':['Input-only cell support is finite structural coverage, not calibrated risk or proof that new learned overrides are safe.','ANY unsupported eligible same-chain cell blocks the whole formula; no aggregate minimum-width/maximum-sharing shortcut.','Same sealed1857-row forest and previous independent training reconstruction reused by hash; no new fitting or consumed-label training.','General32, unsupported8 and prediction-conditional actions are separate finite synthetic populations. Conditional-full shares8 general controls; no pooled or independent-cohort claim.','OriginalRTL verification uses finite2148 vectors per case; mapped-cell recounts are not universal equivalence, mappednetlist proof, timing, power or CPU-speedup evidence.']}
 diagnostics=OUT/'failure-diagnostics.json'
 if diagnostics.exists():body['descriptive_failure_diagnostics_sha256']=sha(diagnostics)
 return receipt(OUT/'audit.json',body,write)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=('preflight','prelabel','final'),nargs='?',default='final');parser.add_argument('--write-receipt',action='store_true');a=parser.parse_args();r=globals()[{'final':'final_audit'}.get(a.command,a.command)](a.write_receipt);print(json.dumps({'status':r['status'],'receipt_created':a.write_receipt,'audit_fits':0,'audit_native_jobs':0,**{k:r[k] for k in ('selected_candidate','scoped_experimental_eligibility','native_accounting') if k in r}},indent=2))
