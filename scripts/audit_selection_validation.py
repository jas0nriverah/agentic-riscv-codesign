#!/usr/bin/env python3
"""Independent bounded audit of retained selection validation; no fits or native jobs."""
from pathlib import Path
import json,zipfile,hashlib,math,re,random,itertools
from collections import Counter
from datetime import datetime,timezone
import os
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
p=Path('results/selection-validation');s=Path('results/selection-stability')
read=lambda path:json.loads(Path(path).read_text())
digest=lambda body:hashlib.sha256(body).hexdigest()
sha=lambda path:digest(Path(path).read_bytes())
plan=read(p/'plan.json');am=read(p/'pre-native-amendment.json');seal=read(p/'point-freeze.json');mf=read(p/'model-freeze.json');done=read(p/'completion.json');rr=read(p/'candidates.json');points=read(p/'predictions.json');labels=read(p/'labels.json');saved=read(p/'metrics.json')
assert sha(p/'plan.json')==am['original_plan_sha256']=='5301fe81ca5cd0fb1f42be1cd1f1d667d7a3648987f0801162b13536e64fe00b'
assert sha(p/'candidates.json')==am['unchanged_candidates_sha256']=='7ee14cd29acbf18731ca097716cc4d601f45d3ac93d7f7e70346a51d03a6f4dc'
assert sha(p/'pre-native-amendment.json')=='96b6263c83f564abe304c02a54ae50b1a5368573487b34aa4b5ee7678698c9da'
for n,h in plan['inputs'].items():assert sha(p/n)==h,n
for n,h in {**plan['sources'],**am['corrected_sources']}.items():assert sha(n)==h,n
for n,h in plan['pipeline_recovery'].items():assert sha(p/'recovered-pipeline'/n)==h
for n,h in mf['models'].items():assert sha(n)==h
assert mf['stability_summary_sha256']==sha(s/'summary.json')
for k,n in [('plan_sha256','plan.json'),('model_freeze_sha256','model-freeze.json'),('features_sha256','features.json'),('predictions_sha256','predictions.json'),('pre_native_amendment_sha256','pre-native-amendment.json')]:assert seal[k]==sha(p/n)
assert seal['fits']==seal['target_label_jobs']==done['fits']==0
assert done['complete'] and not done['failures'] and done['label_count']==40 and done['native_attempt_elapsed_seconds']<=600
assert len(rr)==len(labels)==40 and len({r['template'] for r in rr})==5
assert all(n==8 for n in Counter(r['template'] for r in rr).values())
assert points['candidate_ids']==[r['candidate_id'] for r in rr]==[r['candidate_id'] for r in labels]
assert points['existing_base_exact_match'] and all(l['status']=='complete' and l['formula']==r['formula'] for l,r in zip(labels,rr))
jobs=done['native_worker_jobs'];assert len(jobs)==81 and Counter(j['stage'] for j in jobs)=={'feature':40,'verify':1,'label':40}
assert all(j['returncode']==0 and j['error'] is None for j in jobs)
assert plan['frozen_at_utc']<am['amended_at_utc']<mf['frozen_at_utc']<=read(p/'attempt.json')['started_at_utc']
assert max(j['finished_at_utc'] for j in jobs if j['stage']=='feature')<points['created_at_utc']<=seal['frozen_at_utc']<min(j['started_at_utc'] for j in jobs if j['stage'] in ['verify','label'])
assert max(j['finished_at_utc'] for j in jobs if j['stage']=='verify')<min(j['started_at_utc'] for j in jobs if j['stage']=='label')
events=[]
for j in jobs:events += [(j['started_at_utc'],1),(j['finished_at_utc'],-1)]
active=peak=0
for t,d in sorted(events,key=lambda x:(x[0],x[1])):active+=d;peak=max(peak,active)
assert peak==2 and active==0
numeric=0;maxdiff=0
mean=lambda a:sum(a)/len(a)
def eq(a,b):
 global numeric,maxdiff
 if isinstance(b,dict):
  assert set(a)==set(b)
  for k in b:eq(a[k],b[k])
 elif isinstance(b,(int,float)) and not isinstance(b,bool):
  assert math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12),(a,b)
  numeric+=1;maxdiff=max(maxdiff,abs(a-b))
 else:assert a==b,(a,b)
models={}
for v,pp in points['models'].items():
 assert len(pp)==40 and all(math.isfinite(x) and x>=0 for x in pp)
 errors=[abs(a-l['lut4']) for a,l in zip(pp,labels)];positive=[e/l['lut4'] for e,l in zip(errors,labels) if l['lut4']>0];under=[l['lut4']-a for l,a in zip(labels,pp)]
 models[v]={'count':40,'mae_lut4':mean(errors),'positive_mape_percent':100*mean(positive) if positive else None,'positive_count':len(positive),'zero_count':40-len(positive),'maximum_underprediction_lut4':max(0,max(under)),'worst_underprediction_candidate_id':rr[max(range(40),key=lambda i:under[i])]['candidate_id'],'template_mae_lut4':{t:mean([errors[i] for i,r in enumerate(rr) if r['template']==t]) for t in sorted({r['template'] for r in rr})},'caps':{str(c):{'false_accept':sum(a<=c<l['lut4'] for a,l in zip(pp,labels)),'false_reject':sum(l['lut4']<=c<a for a,l in zip(pp,labels)),'predicted_accept':sum(a<=c for a in pp),'actual_accept':sum(l['lut4']<=c for l in labels),'total':40} for c in [32,64,128]}}
b,c=models['mapping217'],models['selected128'];better=c['mae_lut4']<b['mae_lut4'] and c['positive_mape_percent']<b['positive_mape_percent'];capsok=all(c['caps'][str(cap)][k]<=b['caps'][str(cap)][k] for cap in [32,64,128] for k in ['false_accept','false_reject'])
calculated={'models':models,'selected_minus217_mae_lut4':c['mae_lut4']-b['mae_lut4'],'selected_minus217_mape_percentage_points':c['positive_mape_percent']-b['positive_mape_percent'],'accuracy_improved':better,'all_cap_error_counts_no_worse':capsok,'predeclared_success':better and capsok,'scope':saved['scope']};eq(calculated,saved)
MASK=2**32-1
def parse(text):
 tokens=re.findall(r'[a-z][a-z0-9_]*|-?\d+|[(),]',text);index=0
 def walk():
  nonlocal index
  token=tokens[index];index+=1
  if index<len(tokens) and tokens[index]=='(':
   index+=1;args=[walk()]
   while tokens[index]==',':index+=1;args.append(walk())
   assert tokens[index]==')';index+=1;return (token,tuple(args))
  return int(token) if re.fullmatch(r'-?\d+',token) else token
 node=walk();assert index==len(tokens);return node
signed=lambda n:n-2**32 if n>=2**31 else n
def evaluate(node,a,b):
 if isinstance(node,int):return node&MASK
 if isinstance(node,str):assert node in ['in0','in1'];return a if node=='in0' else b
 op,args=node;aa=evaluate(args[0],a,b);bb=evaluate(args[1],a,b) if len(args)>1 else 0
 if op=='lui':out=aa
 elif op in ['add','addi']:out=aa+bb
 elif op=='sub':out=aa-bb
 elif op in ['and','andi']:out=aa&bb
 elif op in ['or','ori']:out=aa|bb
 elif op in ['xor','xori']:out=aa^bb
 elif op in ['sll','slli']:out=aa<<(bb&31)
 elif op in ['srl','srli']:out=aa>>(bb&31)
 elif op in ['sra','srai']:out=signed(aa)>>(bb&31)
 elif op in ['slt','slti']:out=int(signed(aa)<signed(bb))
 elif op in ['sltu','sltiu']:out=int(aa<bb)
 elif op=='mul':out=aa*bb
 elif op=='mulh':out=(signed(aa)*signed(bb))>>32
 elif op=='mulhu':out=(aa*bb)>>32
 elif op=='mulhsu':out=(signed(aa)*bb)>>32
 else:raise AssertionError(op)
 return out&MASK
asts=[parse(r['formula']) for r in rr]
manifest=read(p/'raw-evidence-manifest.json');archive=p/manifest['archive'];assert sha(archive)==manifest['archive_sha256'];rawbytes=0
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(manifest['members'])
 for name,entry in manifest['members'].items():
  body=z.read(name);assert len(body)==entry['bytes'] and digest(body)==entry['sha256'],name;rawbytes+=len(body)
 proof=json.loads(z.read('verification/result.json'));vectors=z.read('verification/vectors.txt');verrtl=z.read('verification/verification.v').decode();assert digest(vectors)==proof['vectors_sha256'] and digest(verrtl.encode())==proof['rtl_sha256']
 assert proof['verified'] and proof['total_comparisons']==85920 and proof['vectors_per_formula']==2148
 assert z.read('verification/verification.log').decode().strip()=='2148 vectors passed'
 parsedvectors=[[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()];assert len(parsedvectors)==2148 and all(len(v)==42 for v in parsedvectors)
 rng=random.Random(2026110901);boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,MASK]
 expectedpairs=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
 assert [(v[0],v[1]) for v in parsedvectors]==expectedpairs
 for i,(r,l) in enumerate(zip(rr,labels)):
  rtl=z.read(f'labels/{i}/candidate.v').decode();assert digest(rtl.encode())==l['rtl_sha256'];assert rtl.replace('module candidate(','module candidate_'+str(i)+'(') in verrtl
  body=z.read(f'labels/{i}/ice40-netlist.json');assert digest(body)==l['netlist_sha256'];net=json.loads(body);counts=Counter(c['type'] for c in net['modules']['candidate']['cells'].values());assert counts['SB_LUT4']==l['lut4'] and counts['SB_CARRY']==l['carry']
  m=json.loads(z.read(f'labels/{i}/metrics.json'));assert digest(z.read(f'labels/{i}/metrics.json'))==l['metrics_sha256'] and m['ice40_lut4_count']==l['lut4'] and m['ice40_carry_count']==l['carry'];assert m['measurement_source']=='rtl_synthesis';assert 'synth_ice40 -top candidate' in z.read(f'labels/{i}/ice40.ys').decode()
 vectorchecks=0
 for vi,v in enumerate(parsedvectors):
  a,b,*expected=v
  for i,node in enumerate(asts):assert evaluate(node,a,b)==expected[i],(vi,i);vectorchecks+=1
novel=read(p/'novelty.json');history=read(p/'historical-formulas.json');assert novel['status']=='pass' and len(history)==novel['unique_historical_formula_count']==8706
assert not any(r['historical_identity_overlap'] or r['within_cohort_identity_overlap'] for r in novel['comparisons'])
assert not set(history)&{r['formula'] for r in rr}
strict=read(s/'summary.json')['eligibility']['strictly_eligible']
# Direct inference from retained artifacts, with schema mapping by column name.
import joblib
import numpy as np
features=read(p/'features.json');source_columns=read(s/'columns.json')
storage_columns=features['columns'];matrix=np.asarray([r['values'] for r in features['records']])
ordered=matrix[:,[storage_columns.index(n) for n in source_columns]]
zero=ordered[:,source_columns.index('original_gate_count')]==0
for view in ['mapping217','original336','selected128']:
 metadata=read(s/'models'/f'{view}.json');model=joblib.load(s/'models'/f'{view}.joblib')
 values=np.maximum(model.predict(ordered[:,metadata['selected_indices']]),0);values[zero]=0
 assert np.array_equal(values,np.asarray(points['models'][view])),view
audit={'schema':'isaforge-independent-selection-validation-audit-v1','status':'pass','audited_at_utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':sha(p/'plan.json'),'pre_native_amendment_sha256':sha(p/'pre-native-amendment.json'),'metrics_sha256':sha(p/'metrics.json'),'raw_archive_sha256':sha(archive),'original_plan_and_candidates_preserved':True,'plan_and_code_amendment_observed_before_attempt':True,'frozen_source_model_input_hashes_verified':True,'input_before_predictions_before_verification_before_target_labels':True,'complete_rows':40,'template_count':5,'retained_historical_formulas':len(history),'novelty_exact_formula_overlap_count':0,'novelty_saved_normalizer_identity_screen_authenticated':True,'raw_archive_members_hashed':len(manifest['members']),'raw_archive_bytes_hashed':rawbytes,'mapped_netlists_recounted':40,'mapped_target_semantics':'ice40 SB_LUT4 cell count; SB_CARRY counted separately; not generic gates or total cell count','independent_RV32_vector_oracle_checks':vectorchecks,'measured_original_RTL_matches_verified_modules':40,'direct_saved_model_inference_replayed':True,'prediction_count_replayed':120,'feature_schema_reordered_independently_by_column_name':True,'all_metrics_replayed':True,'metric_numeric_comparisons':numeric,'maximum_numeric_replay_difference':maxdiff,'native_worker_jobs':81,'maximum_recorded_overlapping_workers':peak,'native_attempt_seconds':done['native_attempt_elapsed_seconds'],'new_audit_native_jobs':0,'new_audit_fits':0,'predeclared_fresh_success':better and capsok,'stability_strictly_eligible':strict,'promotion_eligible':strict and better and capsok,'metrics':calculated,'limitations':['Prospective synthetic circuits from five manually specified templates; does not establish independent application transfer or representative population generalization.','Historical JSON/formula identity screen is broad but finite; deleted/unreachable, non-JSON, inaccessible external evidence and equivalences outside normalizers may be missed. Saved normalizer screen authenticated and source-reviewed, not independently reimplemented.','Independent RV32 oracle recomputed85920 expected vector outputs; successful saved Verilator execution and measured original RTL identities authenticated. No native audit rerun, universal equivalence proof or mapped-netlist functional proof.','Loaded frozen forests reproduce all points; generic graph feature values authenticated from retained extraction outputs, not independently recomputed.','Recorded native counters/chronology and source-reviewed process isolation; historical OS process peaks and absence of unrecorded activity cannot be independently proved.','LUT4 caps ignore carry usage, routing, timing, physical area and processor integration. Point predictions provide no calibrated feasibility guarantee.']}
audit['audit_script']={'path':str(Path(__file__).relative_to(ROOT)),'sha256':sha(Path(__file__))}
(p/'audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':'pass','vector_oracle_checks':vectorchecks,'raw_members':len(manifest['members']),'metric_maximum_difference':maxdiff,'fresh_success':better and capsok,'promotion_eligible':audit['promotion_eligible']}))
