#!/usr/bin/env python3
"""Independent carry-representation/full-pipeline audit; no fitting or native jobs."""
from __future__ import annotations
import argparse
from collections import Counter
from functools import lru_cache
import itertools,json,math,random,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_boundary_abstention as prior
import audit_boundary_coverage as feature
import audit_targeted_coverage as old
read,sha,digest,now=old.read,old.sha,old.digest,old.now
OUT=ROOT/'results/boundary-corroboration';TRAIN=ROOT/'results/boundary-corroboration-data';TEST=ROOT/'results/boundary-corroboration-validation'
CAPS=(32,64,128);TOL=1e-10;MASK=(1<<32)-1
CURRENT='incumbent_signed';RELEASE='budget_release_compound_only';STRUCTURAL='boundary_structural';LEARNED='boundary_coverage_only';ABSTENTION='boundary_abstention'
CANDIDATES=('corroborated_augmented','corroborated_coverage_only');KINDS=dict(zip(CANDIDATES,('augmented','coverage')))
COUNTS={**prior.COUNTS,'consumed-tenth-general32':32,'consumed-tenth-unsupported8':8,'consumed-tenth-conditional14':14}


def check_bindings(mapping,root=ROOT):
 for name,h in mapping.items():assert sha(root/name)==h,name


def preserved():
 s=read(OUT/'auditor-prior-artifacts.json');check_bindings(s['files']);g=read(ROOT/s['goal_ledger']['path']);g.pop('status',None);assert g==s['goal_ledger']['protected_content']
 assert subprocess.check_output(['git','submodule','status'],cwd=ROOT).decode().splitlines()==s['submodules'];return len(s['files'])


def receipt(path,body,write=False):
 body={'schema':'independent-boundary-corroboration-'+path.stem+'-v1','status':'pass','audited_at_utc':now(),**body,'audit_fits':0,'audit_native_jobs':0}
 if write:
  with path.open('x') as f:json.dump(body,f,indent=2,allow_nan=False);f.write('\n')
 else:
  saved=read(path);actual=dict(body)
  for d in (saved,actual):d.pop('audited_at_utc',None)
  assert saved==actual,'Receipt replay differs:'+str(path)
 return body


def add_masks(a,b):
 """Independent bitwise abstract addition: possible bit/carry sets, modulo32."""
 for z,o in (a,b):assert not z&o and 0<=z<=MASK and 0<=o<=MASK
 zero=one=0;carry={0}
 for i in range(32):
  possible=[]
  for z,o in (a,b):possible.append({0} if z&(1<<i) else ({1} if o&(1<<i) else {0,1}))
  sums={x+y+c for x in possible[0] for y in possible[1] for c in carry};bits={x&1 for x in sums};carry={x>>1 for x in sums}
  if bits=={0}:zero|=1<<i
  elif bits=={1}:one|=1<<i
 return zero,one


@lru_cache(maxsize=32768)
def known_bits(node):
 if not isinstance(node,tuple):return ((~node)&MASK,node&MASK) if isinstance(node,int) else (0,0)
 op,args=node;bits=[known_bits(n) for n in args]
 if op=='lui':return bits[0]
 if all((z|o)==MASK for z,o in bits):
  v=old.evaluate((op,tuple(o for z,o in bits)),0,0);return (~v)&MASK,v&MASK
 a=bits[0];b=bits[1] if len(bits)>1 else (0,0);z0,o0=a;z1,o1=b
 if op in ('add','addi'):return add_masks(a,b)
 if op in ('and','andi'):return z0|z1,o0&o1
 if op in ('or','ori'):return z0&z1,o0|o1
 if op in ('xor','xori'):return (z0&z1)|(o0&o1),(z0&o1)|(o0&z1)
 if op in ('slt','slti','sltu','sltiu'):return MASK^1,0
 if op in ('sll','slli','srl','srli','sra','srai') and ((z1|o1)&31)==31:
  n=o1&31
  if not n:return a
  if op in ('sll','slli'):return ((z0<<n)|((1<<n)-1))&MASK,(o0<<n)&MASK
  high=MASK^((1<<(32-n))-1)
  if op in ('srl','srli'):return (z0>>n)|high,o0>>n
  return (z0>>n)|(high if z0&(1<<31) else 0),(o0>>n)|(high if o0&(1<<31) else 0)
 return 0,0


def unknown_shape(node):
 z,o=known_bits(node);assert not z&o and 0<=z<=MASK and 0<=o<=MASK;u=MASK^(z|o)
 if not u:return 0,32,0
 lo=(u&-u).bit_length()-1;return u.bit_length()-lo,lo,u.bit_count()


def ast_features(formula):
 v=feature.ast_features(formula).copy();chains=feature.ast_chains(formula)
 if chains:
  v[10]=min(unknown_shape(data)[0] for data,_,_,_ in chains);v[11]=max(unknown_shape(data)[1] for data,_,_,_ in chains)
  v[12]=max(((MASK^(known_bits(control)[0]|known_bits(control)[1]))&31).bit_count() for _,control,_,_ in chains)
 return v


def cells(formula):
 result=[]
 for data,control,post,outer in feature.ast_chains(formula):
  span=unknown_shape(data)[0];op=outer[0] if isinstance(outer,tuple) else outer;shared=len(feature.ast_nonleaf_subtrees(data)&feature.ast_nonleaf_subtrees(post))
  result.append({'unknown_span':span,'shared_nonleaf_count':shared,'outer_operator':op,'cell':('narrow' if span<=16 else 'wide')+('_shared' if shared else '_unshared')})
 return result


def carry_soundness():
 """Exhaustive low4 abstract domains plus exact RV32 expression checks."""
 abstract=[]
 for pattern in itertools.product((0,1,2),repeat=4):
  z=MASK^15;o=0
  for i,v in enumerate(pattern):
   if v==0:z|=1<<i
   elif v==1:o|=1<<i
  concrete=[x for x in range(16) if x&o==o and x&z==0];abstract.append(((z,o),concrete))
 total=0
 for (a,aa),(b,bb) in itertools.product(abstract,repeat=2):
  z,o=add_masks(a,b)
  for x,y in itertools.product(aa,bb):v=(x+y)&MASK;assert v&z==0 and v&o==o;total+=1
 formulas=['addi(slli(andi(in0,255),24),101)','addi(slli(andi(in0,255),24),-1)','add(andi(in0,65535),andi(in0,65535))','addi(ori(in0,4294901760),65535)','addi(andi(in0,255),4294967295)','add(ori(in0,4294967040),andi(in1,255))','sra(addi(slli(andi(in0,255),24),101),ori(andi(in1,4294967264),3))']
 boundary=[0,1,2,31,32,33,255,256,65535,65536,0x7fffffff,0x80000000,0xffffffff];rng=random.Random(2026111106);vectors=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(512)];comparisons=0
 for formula in formulas:
  node=old.parse(formula);z,o=known_bits(node)
  for a,b in vectors:v=old.evaluate(node,a,b);assert not v&z and v&o==o;comparisons+=1
 assert unknown_shape(old.parse(formulas[0]))==(8,24,8) and unknown_shape(old.parse(formulas[1]))==(8,24,8)
 return {'exhaustive_low4_abstract_operand_pairs':81**2,'concrete_addition_comparisons':total,'RV32_expression_vector_comparisons':comparisons,'sound_masks_disjoint_and_modular32':True,'negative_literal_wrap_and_shared_input_cases':True}


def panel_sources():
 result=prior.panel_sources();folder=ROOT/'results/boundary-abstention-validation';rows=read(folder/'candidates.json');labels=read(folder/'labels.json');f=read(folder/'features.json');saved=read(ROOT/'results/boundary-abstention/fresh-predictions.json')
 for name,key in (('consumed-tenth-general32','general_selected_indices'),('consumed-tenth-unsupported8','unsupported_selected_indices'),('consumed-tenth-conditional14','conditional_selected_indices')):
  ix=saved[key];result[name]=({'candidate_ids':[rows[i]['candidate_id'] for i in ix],'formulas':[rows[i]['formula'] for i in ix],'actual_lut4':[labels[i]['lut4'] for i in ix]},{'columns':f['columns'],'records':[f['records'][i] for i in ix]})
 assert len(result)==18 and sum(COUNTS.values())==992
 return result


def historical_records():
 import numpy as np
 formulas,h=feature.historical_records();blocks=[h]
 for folder,filename in (('boundary-coverage-data','features.json'),('boundary-coverage-validation','features.json'),('boundary-coverage-validation','pool-features.json'),('boundary-abstention-validation','features.json'),('boundary-abstention-validation','pool-features.json')):
  f=read(ROOT/'results'/folder/filename);blocks.append(prior.matrix(f));formulas.extend(r['formula'] for r in f['records'])
 h=np.vstack(blocks);assert h.shape==(3409,217) and len(formulas)==3409
 return formulas,h


def identity_audit():
 history=set(read(TRAIN/'historical-formulas.json'));assert history==set(read(TEST/'historical-formulas.json'));required=set(read(prior.TEST/'historical-formulas.json'));aliases=set()
 for r in read(prior.TEST/'pool-candidates.json'):required.add(r['formula'])
 for row in read(prior.TEST/'novelty.json')['comparisons']:aliases.update(row['forms'])
 assert required|aliases<=history
 known=set().union(*(feature.prior.identity_keys(f) for f in history));old_skeletons={old.skeleton(f) for f in history};seen=set();train_skeletons=set();reports={}
 for kind,folder,filename,count in (('train',TRAIN,'candidates.json',32),('test',TEST,'pool-candidates.json',128)):
  rows=read(folder/filename);novel=read(folder/'novelty.json');assert len(rows)==count and novel['status']=='pass' and len(novel['comparisons'])==count
  for r,e in zip(rows,novel['comparisons']):
   assert r['candidate_id']==e['candidate_id'];keys=set().union(*(feature.prior.identity_keys(f) for f in {r['formula'],*e['forms']}));skeleton=old.skeleton(r['formula']);assert not keys&known and not keys&seen and skeleton not in old_skeletons;seen.update(keys)
   if kind=='train':train_skeletons.add(skeleton)
   else:assert skeleton not in train_skeletons
  reports[kind]={'rows':count,'historical_identity_or_skeleton_collisions':0,'joint_or_cross_cohort_identity_or_skeleton_collisions':0}
 return {'historical_formulas':len(history),'reports':reports,'all_previous128_pool_rows_including82_unlabelled_consumed':True}


def feature_freshness():
 import numpy as np
 formulas,h=historical_records();training=read(TRAIN/'candidates.json');pool=read(TEST/'pool-candidates.json');tx=prior.matrix(read(TRAIN/'features.json'));px=prior.matrix(read(TEST/'pool-features.json'));assert tx.shape==(32,217) and px.shape==(128,217)
 reports={}
 for kind in ('coverage','augmented'):
  history=np.hstack([h,np.asarray([ast_features(f) for f in formulas])]) if kind=='augmented' else h
  t=np.hstack([tx,np.asarray([ast_features(r['formula']) for r in training])]) if kind=='augmented' else tx
  p=np.hstack([px,np.asarray([ast_features(r['formula']) for r in pool])]) if kind=='augmented' else px
  known={tuple(float(v) for v in row) for row in history};train_keys=[tuple(float(v) for v in row) for row in t];both=known|set(train_keys);keys=[tuple(float(v) for v in row) for row in p];groups={};rep=[]
  for i,key in enumerate(keys):groups.setdefault(key,[]).append(i);rep.append(groups[key][0])
  reports[kind]={'historical_unique_count':len(known),'training_historical_matches':[i for i,k in enumerate(train_keys) if k in known],'training_unique_count':len(set(train_keys)),'pool_historical_or_training_matches':[i for i,k in enumerate(keys) if k in both],'pool_cluster_representatives':rep,'pool_duplicate_clusters':[v for v in groups.values() if len(v)>1]}
 return {'historical_rows':3409,'fitted_rows':1857,'unique_consumed_labels':968,'prior_pool_rows':[200,128,128,128],'representations':reports,'training_fresh':all(not r['training_historical_matches'] and r['training_unique_count']==32 for r in reports.values()),'equality':'Exact float64 numeric tuples; no rounding, no labels.'}


def profile_audit():
 report=read(OUT/'measurement-input-profile-audit.json');check_bindings(report['sources']);targets=read(OUT/'evaluation-targets.json');check_bindings(targets['bindings'])
 oldrows=read(ROOT/'results/boundary-coverage/training-manifest.json')['rows'];newrows=read(TRAIN/'candidates.json');vectors={'old1857':[ast_features(r['formula']) for r in oldrows],'new32':[ast_features(r['formula']) for r in newrows]};vectors['combined1889']=vectors['old1857']+vectors['new32'];summary={};expected=[(group,r) for group in ('established_repairs','remaining_fr_targets','required_rejections') for r in targets[group]]
 assert len(expected)==len(report['matrix'])==49 and len(targets['established_repairs'])==39 and len(targets['remaining_fr_targets'])==4 and len(targets['required_rejections'])==6
 for row,(group,target) in zip(report['matrix'],expected):
  assert row['target_group']==group and row['candidate_id']==target['candidate_id'] and row['formula']==target['formula'];v=ast_features(row['formula']);assert row['features16']==v and row['first10']==v[:10]
  for name,xx in vectors.items():
   matches={'first10':sum(x[:10]==v[:10] for x in xx),'full16':sum(x==v for x in xx)};assert row['matches'][name]==matches
   d=summary.setdefault(group,{}).setdefault(name,{'first10':0,'full16':0})
   for k,n in matches.items():d[k]+=bool(n)
 assert summary==report['coverage_summary'] and summary['remaining_fr_targets']['new32']['full16']==4
 return {'source_sha256':sha(OUT/'measurement-input-profile-audit.json'),'all49_formula_feature_vectors_and_old1857_new32_counts_replayed':True,'coverage_summary':summary,'evaluation_targets_not_used_for_training_or_inference':True,'profile_match_not_cost_or_safety_transfer':True}


def helper_review():
 import boundary_carry_features as helper
 from isaforge.features import parse_formula
 assert tuple(helper.COLUMNS)==tuple(__import__('boundary_coverage_features').COLUMNS)
 formulas,_=historical_records()
 for f in formulas:
  assert helper.features(f)==ast_features(f),f
  assert helper.known_bits(parse_formula(f))==known_bits(old.parse(f)),f
  assert helper.learning_scope(f)==bool(feature.ast_chains(f))
 return {'helper_sha256':sha(ROOT/'scripts/boundary_carry_features.py'),'historical_formula_masks16_columns_and_scope_independently_compared':len(formulas),'soundness':carry_soundness(),'old_helper_immutable':True}


def authenticate():
 p=read(OUT/'protocol.json');plan=read(TRAIN/'plan.json');assert plan==read(TEST/'plan.json')
 assert p['schema']=='isaforge-boundary-corroboration-v1' and p['planned_fits']==p['maximum_fits']==2 and p['fit_threads']==1 and p['maximum_fit_seconds']==120 and p['total_training_rows']==1889 and p['consumed_labels_fitted']==0 and p['retained_panels']==COUNTS
 assert p['policy']['fit_order']==['augmented233','coverage217'] and p['policy']['configuration']==read(ROOT/'results/boundary-coverage/protocol.json')['policy']['configuration']
 assert p['base_columns']==read(ROOT/'results/boundary-coverage/protocol.json')['base_columns'] and p['augmented_columns']==p['base_columns']+list(feature.AST_COLUMNS)
 assert p['gates']['tolerance']==TOL
 for k in ('sources_sha256','inputs_sha256'):check_bindings(p[k])
 assert plan['schema']=='boundary-corroboration-train32-pool128-v1' and plan['training_count']==32 and plan['pool_count']==128 and plan['general_count']==32 and plan['sharing_count']==8 and plan['legacy_count']==8 and plan['challenge_count']==80 and plan['maximum_selected_count']==64
 assert plan['policy']=={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
 for k in ('sources','inputs','prior_inventory_sources','design_audit_inputs'):check_bindings(plan[k])
 rows=read(TEST/'pool-candidates.json');assert len(read(TRAIN/'candidates.json'))==32 and len(rows)==128
 assert [i for i,r in enumerate(rows) if r['cohort']=='general']==list(range(32)) and [i for i,r in enumerate(rows) if r['cohort']=='sharing']==list(range(32,40)) and [i for i,r in enumerate(rows) if r['cohort']=='legacy']==list(range(40,48)) and [i for i,r in enumerate(rows) if r['cohort']=='challenge']==list(range(48,128)) and [i for i,r in enumerate(rows) if r['reserved_control']]==list(range(24,32))
 for tool in read(TRAIN/'tools.json').values():assert sha(tool['path'])==tool['sha256']
 return p


def bindings():
 files=[OUT/n for n in ('protocol.json','auditor-prior-artifacts.json','evaluation-targets.json','measurement-input-profile-audit.json','method-rationale.json','goal-at-freeze.json','goal-update-at-freeze.json')]+[TRAIN/n for n in ('plan.json','candidates.json','novelty.json','historical-formulas.json','tools.json')]+[TEST/n for n in ('plan.json','pool-candidates.json','novelty.json','historical-formulas.json','tools.json')]
 if str((OUT/'support-cells.json').relative_to(ROOT)) in read(OUT/'protocol.json')['inputs_sha256']:files.append(OUT/'support-cells.json')
 return {str(p.relative_to(ROOT)):sha(p) for p in files}


def preflight(write=False):
 p=authenticate();count=preserved()
 if write:
  assert not any((folder/n).exists() for folder in (TRAIN,TEST) for n in ('features.json','pool-features.json','feature-attempt.json','label-attempt.json','labels.json','selection.json'))
  assert not list(OUT.glob('fit-*-attempt.json')) and not (OUT/'run-start.json').exists() and not list(OUT.glob('*.joblib'))
 return receipt(TRAIN/'preflight-audit.json',{'bindings':bindings(),'scientific_artifacts_preserved':count,'identity_audit':identity_audit(),'input_coverage_audit':profile_audit(),'carry_helper_review':helper_review(),'formula_only_support':training_support(),'reviewed_policy':p['policy'],'reviewed_selection':p['selection'],'reviewed_gates':p['gates'],'no_new_features_labels_fit_attempts_at_receipt':True,'planned_fits':2,'fixed48_mandatory_general_sharing_legacy_before_predictions':True,'all_old_forest_provenance_reused_by_frozen_hash':True},write)


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
        kind='train' if folder==TRAIN else 'test'
        feature_jobs=[j for j in read(TRAIN/'feature-completion.json')['native_worker_jobs'] if j['kind']==kind]
        label_jobs=read(folder/'completion.json')['native_worker_jobs']
        for job in feature_jobs+label_jobs:
            phase=job['stage'];directory='verification' if phase=='verify' else phase+'s/'+str(job['index'])
            assert json.loads(get(directory+'/worker.json'))==job
            assert digest(get(directory+'/worker.log'))==job['log_sha256']
        proof=json.loads(get('verification/result.json'));vectors=get('verification/vectors.txt');rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==len(rows) and proof['vectors_per_formula']==2148
        assert proof['random_seed']==read(TRAIN/'plan.json')['proof_random_seeds'][kind]
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
            if folder==TRAIN:assert json.loads(get(f'features/{i}/result.json'))==features['records'][i]
            else:assert features['records'][i]==read(folder/'pool-features.json')['records'][read(folder/'selection.json')['selected_pool_indices'][i]]
        if folder!=TRAIN:
            pool=read(folder/'pool-features.json');assert len(pool['records'])==128
            for i,record in enumerate(pool['records']):assert json.loads(get(f'features/{i}/result.json'))==record
    return {'archive_sha256':sha(archive),'members_hashed':len(members),'mapped_netlists_recounted':len(rows),'all_feature_results_authenticated':32 if folder==TRAIN else 128,'independent_RV32_vector_comparisons':2148*len(rows),'native_job_records_and_logs_authenticated':len(feature_jobs)+len(label_jobs)}


def chronology(final=False):
    features=read(TRAIN/'feature-completion.json');training=read(TRAIN/'completion.json');reports=[features,training]
    assert old.job_audit(features)['jobs']==160 and Counter((j['kind'],j['stage']) for j in features['native_worker_jobs'])=={('train','feature'):32,('test','feature'):128}
    assert old.job_audit(training)['jobs']==33 and Counter(j['stage'] for j in training['native_worker_jobs'])=={'verify':1,'label':32}
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
    assert read(TRAIN/'pretrain-audit.json')['audited_at_utc']<read(TRAIN/'label-attempt.json')['started_at_utc']
    assert max(j['finished_at_utc'] for j in features['native_worker_jobs'])<min(j['started_at_utc'] for j in training['native_worker_jobs'])
    if final:
        labels=read(TEST/'completion.json');reports.append(labels);selected_count=len(read(TEST/'candidates.json'))
        assert old.job_audit(labels)['jobs']==selected_count+1 and Counter(j['stage'] for j in labels['native_worker_jobs'])=={'verify':1,'label':selected_count}
        assert read(TEST/'prelabel-audit.json')['audited_at_utc']<read(TEST/'label-attempt.json')['started_at_utc']
        assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
        assert max(j['finished_at_utc'] for j in training['native_worker_jobs'])<min(j['started_at_utc'] for j in labels['native_worker_jobs'])
    for report in reports[1:]:assert max(j['finished_at_utc'] for j in report['native_worker_jobs'] if j['stage']=='verify')<min(j['started_at_utc'] for j in report['native_worker_jobs'] if j['stage']=='label')
    events=[event for report in reports for j in report['native_worker_jobs'] for event in ((j['started_at_utc'],1),(j['finished_at_utc'],-1))];active=peak=0
    for _,delta in sorted(events,key=lambda x:(x[0],x[1])):active+=delta;peak=max(peak,active)
    assert active==0 and peak<=2
    total=0
    for report in reports:
        total+=report['native_elapsed_seconds'];assert math.isclose(report['total_native_elapsed_seconds'],total,abs_tol=1e-9)
    assert total<=300
    return {'native_jobs':sum(len(r['native_worker_jobs']) for r in reports),'total_native_seconds':total,'recorded_worker_peak':peak,'new_fits':2}


def native_body(folder,relative):
    path=folder/'raw'/relative
    if path.exists():return path.read_bytes()
    manifest=read(folder/'raw-evidence-manifest.json')
    with zipfile.ZipFile(folder/manifest['archive']) as archive:return archive.read('raw/'+relative)


def pretrain(write=False):
    authenticate();count=preserved();preflight(False);features=read(TRAIN/'feature-completion.json');jobs=old.job_audit(features)
    assert jobs['jobs']==160 and Counter((j['kind'],j['stage']) for j in features['native_worker_jobs'])=={('train','feature'):32,('test','feature'):128}
    assert features['native_elapsed_seconds']==features['total_native_elapsed_seconds']<=300
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc']<read(TRAIN/'feature-attempt.json')['started_at_utc']
    for kind,folder,filename,expected in (('train',TRAIN,'features.json',32),('test',TEST,'pool-features.json',128)):
        records=read(folder/filename)['records'];assert len(records)==expected
        for j in features['native_worker_jobs']:
            if j['kind']!=kind:continue
            index=j['index'];prefix='features/'+str(index)+'/'
            assert json.loads(native_body(folder,prefix+'worker.json'))==j and digest(native_body(folder,prefix+'worker.log'))==j['log_sha256'] and json.loads(native_body(folder,prefix+'result.json'))==records[index]
    fresh=feature_freshness();assert fresh==read(OUT/'feature-freshness.json')
    seal=read(OUT/'feature-freeze.json');assert seal['training_fresh']==fresh['training_fresh'] and seal['protocol_sha256']==sha(OUT/'protocol.json');check_bindings(seal['bindings'])
    assert features['completed_at_utc']<seal['frozen_at_utc']
    if write:assert not any((folder/n).exists() for folder in (TRAIN,TEST) for n in ('labels.json','label-attempt.json')) and not (OUT/'run-start.json').exists()
    paths=[TRAIN/'feature-completion.json',TRAIN/'features.json',TEST/'pool-features.json',OUT/'feature-freshness.json',OUT/'feature-freeze.json']
    return receipt(TRAIN/'pretrain-audit.json',{'bindings':{**bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in paths}},'scientific_artifacts_preserved':count,
        'feature_jobs':160,'feature_native_seconds':features['native_elapsed_seconds'],'recorded_worker_peak':jobs['peak_recorded_workers'],'feature_freshness':fresh,
        'training_feature_eligibility':fresh['training_fresh'],'new_training_and_fresh_labels_attempts_absent_at_receipt':True,'feature_records_and_worker_logs_authenticated':160,
        'independent_AST_feature_values_replayed':3409+32+128,'audit_fits':0,'audit_native_jobs':0},write)


def training_support():
 formulas=[r['formula'] for r in read(ROOT/'results/boundary-coverage/training-manifest.json')['rows']]+[r['formula'] for r in read(TRAIN/'candidates.json')];counts=Counter();matched=0
 for f in formulas:
  c=cells(f);matched+=bool(c);counts.update(r['cell'] for r in c)
 result={'training_formula_count':len(formulas),'structural_formula_count':matched,'chain_count':sum(counts.values()),'cell_counts':dict(sorted(counts.items())),'supported_cells':sorted(counts),'input_only':True}
 assert result==read(OUT/'support-cells.json') and len(formulas)==1889
 return result


_MODELS=None

def models():
 global _MODELS
 if _MODELS is not None:return _MODELS
 import joblib,numpy as np
 p=authenticate();seal=read(OUT/'model-freeze.json');assert seal['protocol_sha256']==sha(OUT/'protocol.json') and seal['fits_completed']==2 and seal['wall_seconds']<=120 and seal['feature_freeze_sha256']==sha(OUT/'feature-freeze.json');check_bindings(seal['files_sha256'],OUT)
 oldrows=read(ROOT/'results/boundary-coverage/training-manifest.json')['rows'];newrows=read(TRAIN/'candidates.json');labels=read(TRAIN/'labels.json');assert [r['candidate_id'] for r in newrows]==[r['candidate_id'] for r in labels]
 with np.load(ROOT/'results/boundary-coverage/training-inputs.npz',allow_pickle=False) as z:oldx=z['coverage'];oldy=z['y']
 x=np.vstack([oldx,prior.matrix(read(TRAIN/'features.json'))]);y=np.concatenate([oldy,np.asarray([r['lut4'] for r in labels])]);rows=oldrows+newrows;aug=np.hstack([x,np.asarray([ast_features(r['formula']) for r in rows])]);assert x.shape==(1889,217) and aug.shape==(1889,233)
 expected=[{'training_index':i,'candidate_id':r['candidate_id'],'formula':r['formula'],'actual_lut4':float(y[i]),'source':'frozen1857' if i<1857 else 'new_training32'} for i,r in enumerate(rows)];manifest=read(OUT/'training-manifest.json');assert manifest['rows']==expected and manifest['consumed_evaluation_labels_fitted']==0
 with np.load(OUT/'training-inputs.npz',allow_pickle=False) as z:assert np.array_equal(z['coverage'],x) and np.array_equal(z['augmented'],aug) and np.array_equal(z['y'],y)
 evaluation=read(OUT/'evaluation-targets.json');assert not {r['formula'] for r in newrows}&{r['formula'] for group in ('established_repairs','remaining_fr_targets','required_rejections') for r in evaluation[group]}
 attempts=[read(OUT/f'fit-attempt-{i}.json') for i in (1,2)];timing=read(OUT/'timings.json');assert len(timing)==2 and [r['kind'] for r in timing]==['augmented','coverage'];start=read(OUT/'run-start.json');assert start['maximum_fits']==start['planned_fits']==2 and start['training_labels_sha256']==sha(TRAIN/'labels.json') and read(TRAIN/'completion.json')['completed_at_utc']<start['started_at_utc']<=attempts[0]['started_at_utc']<attempts[1]['started_at_utc']<seal['frozen_at_utc']
 estimators={};forensics={}
 for index,kind,xx in ((1,'augmented',aug),(2,'coverage',x)):
  m=joblib.load(OUT/(kind+'.joblib'));meta=read(OUT/(kind+'.json'));attempt=attempts[index-1];assert m.n_features_in_==xx.shape[1] and len(m.estimators_)==300 and all(m.get_params()[k]==v for k,v in p['policy']['configuration'].items())
  assert attempt['fit_index']==index and attempt['kind']==kind and attempt['training_count']==1889 and attempt['feature_count']==xx.shape[1] and attempt['training_inputs_sha256']==sha(OUT/'training-inputs.npz') and attempt['configuration']==p['policy']['configuration']
  assert meta['training_count']==1889 and meta['old_training_count']==1857 and meta['new_training_count']==32 and meta['consumed_labels_fitted']==0 and meta['artifact_sha256']==sha(OUT/(kind+'.joblib')) and meta['protocol_sha256']==sha(OUT/'protocol.json') and meta['columns']==(p['augmented_columns'] if kind=='augmented' else p['base_columns'])
  assert timing[index-1]['index']==index and 0<=timing[index-1]['fit_seconds']<=120
  estimators[kind]=m;forensics[kind]=feature.verify_tree_training(m,xx,y)
 _MODELS=estimators,{'old1857_ordered_inputs_and_targets_reused_by_frozen_hash':True,'new32_inputs_targets_verified_against_native_records':True,'both1889row_matrices_and_all16_carry_columns_reconstructed':True,'fits':forensics,'total_new_training_leaf_assignments_checked':1889*300*2,'consumed_evaluation_labels_fitted':0,'fixed_fit_order':['augmented','coverage'],'fit_records':timing}
 return _MODELS


def points(row,f):
 import numpy as np
 values,routes,details=prior.points(row,f);x=prior.matrix(f);known=set(training_support()['supported_cells']);cell_rows=[[r['cell'] for r in cells(formula)] for formula in row['formulas']];scope=[bool(c) and all(k in known for k in c) for c in cell_rows];raw={};limits={};provenance={};estimators,_=models()
 for name in CANDIDATES:
  kind=KINDS[name];xx=np.hstack([x,np.asarray([ast_features(formula) for formula in row['formulas']])]) if kind=='augmented' else x;raw[name]=estimators[kind].predict(xx).tolist();out=[];caps=[]
  for s,r,p,active in zip(values[CURRENT],values[RELEASE],raw[name],scope):
   allowed=[c for c in CAPS if active and s<=c<r and p<=c];out.append(min(allowed) if allowed else r);caps.append(allowed)
  values[name]=out;limits[name]=caps;provenance[name]=[{str(c):{'signed_accepts':values[CURRENT][i]<=c,'release_accepts':values[RELEASE][i]<=c,'structural_proposal':values[STRUCTURAL][i]<=c<values[RELEASE][i],'oldlearned_proposal':values[LEARNED][i]<=c<values[RELEASE][i],'oldabstention_proposal':values[ABSTENTION][i]<=c<values[RELEASE][i],'new_raw_accepts':raw[name][i]<=c,'covered':scope[i],'candidate_accepts':values[name][i]<=c} for c in CAPS} for i in range(len(row['formulas']))]
 return values,routes,{**details,'pipeline_cells':cell_rows,'pipeline_covered':scope,'corroboration_raw_lut4':raw,'corroborated_caps_lut4':limits,'proposal_provenance':provenance}


def metrics(y,values,raw=None):
 m={n:old.metrics(y,v) for n,v in values.items()};refs=(RELEASE,STRUCTURAL,LEARNED,ABSTENTION);checks={}
 for n in CANDIDATES:
  checks[n]={'accuracy_no_worse':{r:feature.accuracy(m[r],m[n]) for r in refs},'caps':{str(c):{'false_accept_no_worse_release':m[n]['caps'][str(c)]['false_accept']<=m[RELEASE]['caps'][str(c)]['false_accept'],'false_reject_no_worse_signed':m[n]['caps'][str(c)]['false_reject']<=m[CURRENT]['caps'][str(c)]['false_reject']} for c in CAPS},'maximum_underprediction_no_worse':all(m[n]['maximum_underprediction_lut4']<=m[r]['maximum_underprediction_lut4']+TOL for r in (*refs,CURRENT)),'pointwise_bounds':all(s<=p<=r for s,p,r in zip(values[CURRENT],values[n],values[RELEASE])),'events':{r:feature.prior.cap_events(values[r],values[n],y) for r in (*refs,CURRENT)}}
 m['checks']=checks
 if raw is not None:m['raw_model_metrics']={n:old.metrics(y,raw[n]) for n in CANDIDATES}
 return m


def passed(c):return all(all(v.values()) for v in c['accuracy_no_worse'].values()) and all(all(v.values()) for v in c['caps'].values()) and c['maximum_underprediction_no_worse'] and c['pointwise_bounds']


def development():
 saved=read(OUT/'development-predictions.json');stored=read(OUT/'development-metrics.json');computed={};assert set(saved)==set(COUNTS)
 for name,(r,f) in panel_sources().items():
  assert len(r['actual_lut4'])==COUNTS[name]
  for k,v in r.items():assert saved[name][k]==v,(name,k)
  values,routes,details=points(r,f);assert saved[name]['models']==values and saved[name]['routes']==routes,name
  for k,v in details.items():assert saved[name][k]==v,(name,k)
  computed[name]=metrics(r['actual_lut4'],values,details['corroboration_raw_lut4']);old.compare_metric(stored['panels'][name],computed[name])
 def sub(name,ix):
  r=saved[name];return metrics([r['actual_lut4'][i] for i in ix],{n:[v[i] for i in ix] for n,v in r['models'].items()},{n:[v[i] for i in ix] for n,v in r['corroboration_raw_lut4'].items()})
 def group(name,folder,template):
  ix=[i for i,r in enumerate(read(ROOT/'results'/folder/'candidates.json')) if r['template']==template];assert len(ix)==4;return sub(name,ix)
 named={'arithmetic_stress32':computed['arithmetic-stress'],'signed_dual_arithmetic4':group('consumed-second-fresh32','budget-preserving-validation','signed_dual_arithmetic'),'signed_add_boolean4':group('consumed-third-fresh40','guarded-revision-validation','heldout_signed_variable_add_boolean'),'compound_signed_add_xor4':group('consumed-fourth-fresh40','signed-refinement-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_add_xor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_add_xor'),'fifth_compound_signed_xordata_addxor4':group('consumed-fifth-fresh40','budget-release-validation','heldout_compound_signed_xordata_addxor')}
 r=saved['consumed-sixth-broad40'];named['broad_compound32']=sub('consumed-sixth-broad40',[i for i,f in enumerate(r['formulas']) if feature.prior.predicates(f)[0]])
 r=saved['consumed-seventh-conditional18'];fr=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][RELEASE][i]];fa=[i for i,y in enumerate(r['actual_lut4']) if any(r['models']['boundary_median'][i]<=c<r['models'][RELEASE][i] and y>c for c in CAPS)];assert len(fr)==8 and len(fa)==2;named['eight_corrected_fr']=sub('consumed-seventh-conditional18',fr);named['two_previous_new_fa']=sub('consumed-seventh-conditional18',fa)
 r=saved['consumed-eighth-general32'];four=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][STRUCTURAL][i]];assert len(four)==4;named['four_confident_fr']=sub('consumed-eighth-general32',four);named['prior_active16']=sub('consumed-eighth-conditional24',list(range(16)))
 r=saved['consumed-ninth-general32'];ix=[i for i,y in enumerate(r['actual_lut4']) if y<=128<r['models'][STRUCTURAL][i] and r['models'][LEARNED][i]<=128];assert len(ix)==1 and r['actual_lut4'][ix[0]]==122;named['safe122']=sub('consumed-ninth-general32',ix)
 r=saved['consumed-ninth-conditional9'];ix=[i for i,y in enumerate(r['actual_lut4']) if y>128 and r['models'][LEARNED][i]<=128<r['models'][STRUCTURAL][i]];assert len(ix)==1 and r['actual_lut4'][ix[0]]==159;named['unsafe159']=sub('consumed-ninth-conditional9',ix);named['latest_active6']=sub('consumed-tenth-conditional14',list(range(6)))
 lookup={cid:(r,i) for r in saved.values() for i,cid in enumerate(r['candidate_ids'])};targets=read(OUT/'evaluation-targets.json')
 for label,groupname in (('established39','established_repairs'),('remaining_fr4','remaining_fr_targets'),('protected_rejections6','required_rejections')):
  rr=targets[groupname];named[label]=metrics([r['actual_lut4'] for r in rr],{n:[lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]] for r in rr] for n in next(iter(saved.values()))['models']})
 assert len(named)==17
 for k,v in named.items():old.compare_metric(stored['named_regressions'][k],v)
 accept=targets['established_repairs']+targets['remaining_fr_targets'];reject=targets['required_rejections'];cases=[]
 for target in accept+reject:
  r,i=lookup[target['candidate_id']];assert r['actual_lut4'][i]==target['actual_lut4'] and r['formulas'][i]==target['formula'];cases.append({**{k:target[k] for k in ('candidate_id','formula','actual_lut4','cap')},'expected':'accept' if target in accept else 'reject','predictions':{n:r['models'][n][i] for n in CANDIDATES}})
 assert cases==stored['evaluation_cases'] and len(accept)==43 and len(reject)==6
 gates={}
 for n in CANDIDATES:
  g={'all_eighteen_panels_pass':all(passed(m['checks'][n]) for m in computed.values()),'all_named_subgroups_preserved':all(passed(m['checks'][n]) for m in named.values()),'all_forty_three_acceptances_pass':all(r['predictions'][n]<=r['cap'] for r in cases if r['expected']=='accept'),'all_six_rejections_pass':all(r['predictions'][n]>r['cap'] for r in cases if r['expected']=='reject')};g['development_gate_passed']=all(g.values());gates[n]=g
 selected=next((n for n in CANDIDATES if gates[n]['development_gate_passed']),None);assert stored['gates']==gates and stored['selected_candidate']==selected and stored['evaluated_candidate']==(selected or CANDIDATES[0]) and stored['retained_metric_rows']==992 and stored['retained_circuit_records']==968 and stored['shared_controls']==24 and stored['no_pooled_metric']
 return {'gates':gates,'selected_candidate':selected,'evaluated_candidate':selected or CANDIDATES[0],'named_subsets':list(named),'evaluation_cases':cases,'retained_metric_rows':992,'retained_circuit_records':968,'shared_controls':24,'no_pooled_metric':True,'development_predictions_replayed':992*10}


def select(pool,values,fresh,evaluated):
 groups={c:[i for i,r in enumerate(pool) if r['cohort']==c] for c in ('general','sharing','legacy')};fixed=groups['general']+groups['sharing']+groups['legacy'];controls=[i for i,r in enumerate(pool) if r['reserved_control']];reps={k:r['pool_cluster_representatives'] for k,r in fresh['representations'].items()};history=set().union(*(r['pool_historical_or_training_matches'] for r in fresh['representations'].values()));seen={k:{v[i] for i in fixed} for k,v in reps.items()}
 raw=[i for i,r in enumerate(pool) if r['cohort']=='challenge' and any(values[evaluated][i]<=c<values[ABSTENTION][i] for c in CAPS)];collision=[i for i in raw if any(reps[k][i] in seen[k] for k in reps)];eligible=[i for i in raw if i not in history and i not in collision];queues={}
 for i in eligible:queues.setdefault(pool[i]['template'],[]).append(i)
 active=[];skipped=[]
 while len(active)<16 and any(queues.values()):
  for template in sorted(queues):
   if len(active)>=16:break
   while queues[template] and any(reps[k][queues[template][0]] in seen[k] for k in reps):skipped.append(queues[template].pop(0))
   if queues[template]:
    i=queues[template].pop(0);active.append(i)
    for k in reps:seen[k].add(reps[k][i])
 selected=fixed+active;selection={**{c+'_pool_indices':v for c,v in groups.items()},'reserved_control_pool_indices':controls,'raw_active_pool_indices':raw,'eligible_active_pool_indices':eligible,'historical_collision_active_pool_indices':[i for i in raw if i in history],'fixed_feature_collision_active_pool_indices':collision,'skipped_duplicate_active_pool_indices':skipped,'selected_active_pool_indices':active,'selected_pool_indices':selected};checks={}
 for k,r in fresh['representations'].items():
  keys=r['pool_cluster_representatives'];checks[k+'_fixed_novel']=not bool(set(r['pool_historical_or_training_matches'])&set(fixed));checks[k+'_fixed_unique']=len({keys[i] for i in fixed})==48;checks[k+'_selected_unique']=len({keys[i] for i in selected})==len(selected)
 templates=sorted({pool[i]['template'] for i in active});caps={str(c):sum(values[evaluated][i]<=c<values[ABSTENTION][i] for i in active) for c in CAPS};legacy=[i for i in groups['legacy'] if values[ABSTENTION][i]<=64<values[evaluated][i]];sharing=[i for i in groups['sharing'] if values[LEARNED][i]<=128<values[evaluated][i]]
 checks.update({'at_least_four_new_acceptances':len(active)>=4,'at_least_two_templates':len(templates)>=2,'at_least_one_cap128':caps['128']>=1,'at_least_one_legacy64_veto':len(legacy)>=1,'at_least_one_sharing128_veto':len(sharing)>=1})
 coverage={'pool_count':128,'general_count':32,'sharing_count':8,'legacy_count':8,'shared_control_count':8,'raw_active_count':len(raw),'eligible_active_count':len(eligible),'selected_active_count':len(active),'selected_templates':templates,'acceptance_caps':caps,'legacy64_veto_count':len(legacy),'legacy64_veto_pool_indices':legacy,'sharing128_veto_count':len(sharing),'sharing128_veto_pool_indices':sharing,'unique_label_count':len(selected),'conditional_count':len(active)+8,'checks':checks,'passed':all(checks.values())}
 return selection,coverage


def fresh_points():
 authenticate();dev=development();pool=read(TEST/'pool-candidates.json');f=read(TEST/'pool-features.json');stored=read(OUT/'pool-predictions.json');row={'formulas':[r['formula'] for r in pool]};values,routes,details=points(row,f)
 assert stored['models']==values and stored['routes']==routes and stored['candidate_ids']==[r['candidate_id'] for r in pool] and stored['formulas']==row['formulas'] and stored['templates']==[r['template'] for r in pool]
 for k,v in details.items():assert stored[k]==v,k
 fresh=feature_freshness();assert fresh==read(OUT/'feature-freshness.json');selection,coverage=select(pool,values,fresh,dev['evaluated_candidate']);s=read(TEST/'selection.json')
 for k,v in selection.items():assert s[k]==v,k
 assert s['coverage']==coverage and s['labels_present'] is False and s['pool_predictions_sha256']==sha(OUT/'pool-predictions.json') and s['evaluated_candidate']==dev['evaluated_candidate']
 ix=selection['selected_pool_indices'];saved=read(OUT/'fresh-predictions.json');assert read(TEST/'candidates.json')==[pool[i] for i in ix] and read(TEST/'features.json')=={'columns':f['columns'],'records':[f['records'][i] for i in ix]}
 for k in ('candidate_ids','formulas','templates','routes',*details):
  if isinstance(stored[k],dict):assert saved[k]=={n:[v[i] for i in ix] for n,v in stored[k].items()},k
  else:assert saved[k]==[stored[k][i] for i in ix],k
 assert saved['models']=={n:[v[i] for i in ix] for n,v in values.items()} and saved['general_selected_indices']==list(range(32)) and saved['sharing_selected_indices']==list(range(32,40)) and saved['legacy_selected_indices']==list(range(40,48)) and saved['active_selected_indices']==list(range(48,len(ix))) and saved['shared_control_selected_indices']==list(range(24,32)) and saved['conditional_selected_indices']==list(range(48,len(ix)))+list(range(24,32))
 assert saved['selection_coverage']==coverage and saved['selected_candidate']==stored['selected_candidate']==dev['selected_candidate'] and saved['evaluated_candidate']==stored['evaluated_candidate']==dev['evaluated_candidate']
 seal=read(OUT/'fresh-point-freeze.json');bridge=read(TEST/'point-freeze.json');assert seal['fresh_labels_present'] is False and seal['new_fits']==0 and bridge['target_label_jobs']==0;check_bindings(seal['bindings']);check_bindings(bridge['bindings'])
 assert read(OUT/'model-freeze.json')['frozen_at_utc']<stored['created_at_utc']<s['frozen_at_utc']<seal['frozen_at_utc']
 return saved,dev,fresh


def cached_inference(saved):
 c=read(OUT/'cached-inference-check.json');assert c['model']==saved['evaluated_candidate'] and c['selected_candidate']==saved['selected_candidate'] and c['fits']==c['native_jobs']==0 and c['calibration_status']=='uncalibrated' and c['upper_lut4'] is None
 for k in ('candidate_ids','formulas','models','routes','structural_scope','applied_qualifying_caps_lut4','forest_medians_lut4','qualifying_caps_lut4','tree_predictions_above_cap','learning_scope','learned_raw_lut4','learned_supported_caps_lut4','coverage_guard','pipeline_cells','pipeline_covered','corroboration_raw_lut4','corroborated_caps_lut4','proposal_provenance'):assert c[k]==saved[k],k
 assert c['predicted_lut4']==saved['models'][saved['evaluated_candidate']] and c['protocol_sha256']==sha(OUT/'protocol.json') and c['features_sha256']==sha(TEST/'features.json') and c['candidates_sha256']==sha(TEST/'candidates.json')
 return {'artifact_sha256':sha(OUT/'cached-inference-check.json'),'ten_model_predictions_replayed':10*len(saved['candidate_ids']),'uncalibrated':True,'fits':0,'native_jobs':0}


def prelabel(write=False):
 authenticate();count=preserved();pretrain(False);jobs=chronology();saved,dev,fresh=fresh_points();_,forensics=models()
 if write:assert not any((TEST/n).exists() for n in ('labels.json','label-attempt.json'))
 files=[OUT/n for n in ('feature-freeze.json','feature-freshness.json','model-freeze.json','pool-predictions.json','fresh-point-freeze.json','fresh-predictions.json','cached-inference-check.json')]+[TRAIN/n for n in ('completion.json','labels.json','raw-evidence-manifest.json')]+[TEST/n for n in ('selection.json','candidates.json','features.json','point-freeze.json','pool-features.json')]
 return receipt(TEST/'prelabel-audit.json',{'bindings':{**bindings(),**{str(p.relative_to(ROOT)):sha(p) for p in files}},'scientific_artifacts_preserved':count,'fresh_labels_and_attempts_absent_at_receipt':True,'fresh_predictions_replayed':10*len(saved['candidate_ids']),'all_pool_predictions_replayed':1280,'feature_freshness':fresh,'selection_coverage':saved['selection_coverage'],'development':dev,'matched_training_forensics':forensics,'training_raw_evidence':raw_audit(TRAIN),'cached_inference':cached_inference(saved),'native_accounting_to_date':jobs,'two_fixed_fits_all128_points_and_selection_before_labels':True,'fixed48_general_sharing_legacy_before_predictions':True,'shared_controls_not_independent':True,'no_pooled_metric':True,'training_support':training_support(),'all_four_cells_covered_guard_has_no_effect_on_structural_chains':len(training_support()['supported_cells'])==4},write)


def final_audit(write=False):
 authenticate();count=preserved();prelabel(False);jobs=chronology(True);saved,dev,fresh=fresh_points();_,forensics=models();rows=read(TEST/'candidates.json');labels=read(TEST/'labels.json');assert saved['candidate_ids']==[r['candidate_id'] for r in labels];y=[r['lut4'] for r in labels];scored=read(OUT/'fresh-metrics.json')
 def sub(ix):return metrics([y[i] for i in ix],{n:[v[i] for i in ix] for n,v in saved['models'].items()},{n:[v[i] for i in ix] for n,v in saved['corroboration_raw_lut4'].items()})
 general=sub(saved['general_selected_indices']);sharing=sub(saved['sharing_selected_indices']);legacy=sub(saved['legacy_selected_indices']);conditional=sub(saved['conditional_selected_indices']);active=sub(saved['active_selected_indices']) if saved['active_selected_indices'] else None
 fields=sum(old.compare_metric(scored[k],m) for k,m in (('models',general),('sharing_models',sharing),('legacy_models',legacy),('conditional_models',conditional)))
 if active:fields+=old.compare_metric(scored['active_subgroup'],active)
 else:assert scored['active_subgroup'] is None
 gates={}
 for n in CANDIDATES:
  ix=[i for i in saved['active_selected_indices'] if any(saved['models'][n][i]<=c<saved['models'][ABSTENTION][i] for c in CAPS)];activity={'acceptances':len(ix),'templates':len({saved['templates'][i] for i in ix}),'cap128':sum(saved['models'][n][i]<=128<saved['models'][ABSTENTION][i] for i in ix),'legacy64_veto':sum(saved['models'][ABSTENTION][i]<=64<saved['models'][n][i] for i in saved['legacy_selected_indices']),'sharing128_veto':sum(saved['models'][LEARNED][i]<=128<saved['models'][n][i] for i in saved['sharing_selected_indices'])}
  activity_ok=activity['acceptances']>=4 and activity['templates']>=2 and activity['cap128']>=1 and activity['legacy64_veto']>=1 and activity['sharing128_veto']>=1
  checks={'coverage':saved['selection_coverage'],'model_specific_activity':activity,'model_specific_activity_passes':activity_ok,'general_no_loss':passed(general['checks'][n]),'general_strict_signed':feature.accuracy(general[CURRENT],general[n],True),'general_strict_fa_gain_signed':sum(general[n]['caps'][str(c)]['false_accept'] for c in CAPS)<sum(general[CURRENT]['caps'][str(c)]['false_accept'] for c in CAPS),'sharing_passes':passed(sharing['checks'][n]),'legacy_passes':passed(legacy['checks'][n]),'conditional_full_passes':passed(conditional['checks'][n]),'active_subset_passes':bool(active and passed(active['checks'][n]))}
  ok=checks['coverage']['passed'] and activity_ok and checks['general_no_loss'] and all(checks['general_strict_signed'].values()) and checks['general_strict_fa_gain_signed'] and checks['sharing_passes'] and checks['legacy_passes'] and checks['conditional_full_passes'] and checks['active_subset_passes'];gates[n]={'checks':checks,'fresh_gate_passed':ok,'development_gate_passed':dev['gates'][n]['development_gate_passed'],'eligible':ok and dev['selected_candidate']==n}
 chosen=dev['selected_candidate'];evaluated=dev['evaluated_candidate'];eligible=bool(chosen and gates[chosen]['eligible']);assert scored['gates']==gates and scored['scoped_experimental_eligibility']==eligible and scored['selected_candidate']==chosen and scored['evaluated_candidate']==evaluated
 assert scored['selection_coverage']==saved['selection_coverage'] and scored['general_count']==32 and scored['sharing_count']==scored['legacy_count']==8 and scored['active_count']==len(saved['active_selected_indices']) and scored['conditional_count']==len(saved['conditional_selected_indices']) and scored['shared_controls']==8 and scored['unique_label_count']==len(y) and scored['fits']==2 and scored['native_jobs']==0 and scored['no_pooled_metric'] and scored['fresh_labels_sha256']==sha(TEST/'labels.json')
 def decisions(ix):
  result={}
  for ref in (CURRENT,RELEASE,STRUCTURAL,LEARNED,ABSTENTION):
   caps={}
   for c in CAPS:
    events=[]
    for i in ix:
     before=saved['models'][ref][i];after=saved['models'][evaluated][i]
     if (before<=c)==(after<=c):continue
     event=('corrected_false_reject' if y[i]<=c else 'new_false_accept') if after<=c else ('new_false_reject' if y[i]<=c else 'corrected_false_accept')
     events.append({'selected_index':i,'pool_index':read(TEST/'selection.json')['selected_pool_indices'][i],'candidate_id':rows[i]['candidate_id'],'template':rows[i]['template'],'formula':rows[i]['formula'],'actual_lut4':y[i],'reference_lut4':before,'prediction_lut4':after,'raw_mean_lut4':saved['corroboration_raw_lut4'][evaluated][i],'event':event,'proposal_provenance':saved['proposal_provenance'][evaluated][i][str(c)]})
    feasible=sum(y[i]<=c for i in ix);caps[str(c)]={'actual_feasible':feasible,'actual_infeasible':len(ix)-feasible,'changed_decisions':events}
   result[ref]=caps
  return result
 check=gates[evaluated]['checks'];dg=dev['gates'][evaluated];scientific={'development_selected_candidate_exists':chosen is not None,'all_eighteen_retained992_metric_rows968_records_preserved':dg['all_eighteen_panels_pass'],'all_seventeen_named_subgroups_preserved':dg['all_named_subgroups_preserved'],'all39_established_repairs_and_four_remaining_FR_targets':dg['all_forty_three_acceptances_pass'],'all_six_protected_rejections_including107_113_and_two159_cases':dg['all_six_rejections_pass'],'fresh_general_strict_signed_accuracy_and_FA_gains':all(check['general_strict_signed'].values()) and check['general_strict_fa_gain_signed'],'fresh_general_no_loss_four_comparators_and_FA_FR_gates':check['general_no_loss'],'new_acceptance_coverage_and_freshness_all_prospective_requirements':check['coverage']['passed'] and check['model_specific_activity_passes'],'fixed_sharing8_no_loss_and_FA_FR_gates':check['sharing_passes'],'fixed_legacy8_no_loss_and_FA_FR_gates':check['legacy_passes'],'conditional_full_no_loss_and_FA_FR_gates':check['conditional_full_passes'],'active_only_no_loss_and_FA_FR_gates':check['active_subset_passes'],'no_consumed_evaluation_labels_fitted_and_both1889_matrices_leaves_reconstructed':forensics['consumed_evaluation_labels_fitted']==0,'sound_carry_masks_and_every_chain_binding_independently_checked':True,'cohorts_features_policy_finite_fit_hierarchy_gates_before_new_labels':True,'both_fixed_models_and_all128_points_selection_before_fresh_labels':True,'bounded_two_fits_single_thread_300native_seconds_peak_two':jobs['new_fits']==2 and jobs['total_native_seconds']<=300 and jobs['recorded_worker_peak']<=2,'prior857_scientific_artifacts_preserved_only_goal_status_mutable':count==857,'independent_source_vectors_netlists_chronology_cached_inference_audits_pass':True,'separate_populations_and_shared_controls_disclosed_no_pooling':True}
 assert all(scientific.values())==eligible
 raw={kind:raw_audit(folder) for kind,folder in (('train',TRAIN),('test',TEST))};templates={t:sub([i for i,r in enumerate(rows) if r['template']==t]) for t in sorted({r['template'] for r in rows})}
 body={'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),'scientific_artifacts_preserved':count,'goal_ledger_status_only_mutable':True,'fits':2,'new_training_rows':32,'total_training_rows':1889,'training_support':training_support(),'all_four_cells_covered_guard_has_no_effect_on_structural_chains':len(training_support()['supported_cells'])==4,'matched_training_forensics':forensics,'old_forest_forensics_reused_by_hash_no_optional_repetition':True,'native_accounting':jobs,'identity_audit':identity_audit(),'feature_freshness':fresh,'input_coverage_audit':profile_audit(),'carry_helper_review':helper_review(),'training_and_fresh_raw_evidence':raw,'cached_inference':cached_inference(saved),'descriptive_diagnostics':diagnostic_review(saved,y),'development':dev,'fresh_general32':general,'fresh_sharing8':sharing,'fresh_legacy8':legacy,'fresh_conditional_full':conditional,'fresh_active_only':active,'fresh_template_metrics_descriptive':templates,'fresh_gates':gates,'selected_candidate':chosen,'evaluated_candidate':evaluated,'scoped_experimental_eligibility':eligible,'selection_coverage':saved['selection_coverage'],'pool_count':128,'selected_unique_label_count':len(y),'all_unselected_pool_rows_features_predictions_retained':True,'shared_control_count':8,'shared_control_selected_indices':saved['shared_control_selected_indices'],'shared_controls_not_independent':True,'general_cap_decision_cases':decisions(saved['general_selected_indices']),'sharing_cap_decision_cases':decisions(saved['sharing_selected_indices']),'legacy_cap_decision_cases':decisions(saved['legacy_selected_indices']),'conditional_full_cap_decision_cases':decisions(saved['conditional_selected_indices']),'active_only_cap_decision_cases':decisions(saved['active_selected_indices']),'selected_numeric_fields_compared':fields,'development_predictions_replayed':992*10,'all_pool_predictions_replayed':1280,'selected_predictions_replayed':len(y)*10,'scientific_goal_requirement_checks':scientific,'scientific_goal_requirements_passed':all(scientific.values()),'goal_completion_verified':False,'publication_and_full_validation_verification_pending':True,'no_pooled_metric':True,'conditional_population_not_representative':True,'general_population_fixed_targeted_synthetic_not_representative':True,'false_acceptance_sum_unit':'circuit-budget events, not unique circuits; each population has per-cap actual feasible/infeasible denominators and changed-case identities.','mape_definition':'100*mean(abs(actual-predicted)/actual) over actual>0; zero-target rows remain in MAE, tail and cap denominators and are excluded only from MAPE.','mathematical_bounds':'signed<=candidate<=release. This prevents correcting existing signed false rejections or release false acceptances; separate no-worse counts therefore imply no new per-case errors against those comparators at each cap.','limitations':['Carry known-bit propagation is established abstract interpretation; this new independently tested implementation improves descriptor precision without proving area accuracy or safety.','Matched217/233 fits isolate the additional16-column block on identical1889 inputs/targets; simultaneous policy and training-coverage changes are not individually causal effects.','Allfour structural cells represented means the coverage guard is inactive among matchingchains; improvements cannot be attributed to abstention.','General32, sharing8, legacy8 and prediction-conditioned active populations are separate finite synthetic populations. Conditional-full shares8 general controls; no pooled or independent-cohort claim.','OriginalRTL proof uses finite2148 vectors per case; mapped-cell recounts are not universal equivalence, mappednetlist functional proof, timing, power or CPU-speedup evidence.','Both fixed fits, failed or unpromoted candidates, every finite pool row and all missing/failure evidence remain retained; no postfresh switch or relaxed gate.']}
 return receipt(OUT/'audit.json',body,write)


def diagnostic_review(saved,y):
 d=read(OUT/'failure-diagnostics.json');assert d['status']=='postlabel_descriptive_only' and d['policy_changed'] is False and d['additional_fits']==d['additional_native_jobs']==0;check_bindings(d['bindings'])
 panels=read(OUT/'development-predictions.json');lookup={cid:(r,i) for r in panels.values() for i,cid in enumerate(r['candidate_ids'])};lookup.update({cid:({**saved,'actual_lut4':y},i) for i,cid in enumerate(saved['candidate_ids'])});checked=0
 def walk(v):
  nonlocal checked
  if isinstance(v,dict):
   if 'candidate_id' in v:
    r,i=lookup[v['candidate_id']];assert v['formula']==r['formulas'][i] and v['actual_lut4']==r['actual_lut4'][i] and v['cells']==r['pipeline_cells'][i]
    assert all(p==r['models'][n][i] for n,p in v['predictions_lut4'].items()) and all(p==r['corroboration_raw_lut4'][n][i] for n,p in v['new_raw_lut4'].items());checked+=1
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(d);targets=read(OUT/'evaluation-targets.json')
 for n in CANDIDATES:
  expected={r['candidate_id'] for r in targets['established_repairs'] if lookup[r['candidate_id']][0]['models'][n][lookup[r['candidate_id']][1]]>r['cap']};assert {r['candidate_id'] for r in d['lost_established_repairs'][n]}==expected
  expected={saved['candidate_ids'][i] for i in saved['general_selected_indices'] if y[i]<=128 and saved['models'][CURRENT][i]<=128<saved['models'][n][i]};assert {r['candidate_id'] for r in d['fresh_general_new_false_rejections_vs_signed'][n]}==expected
 assert len(d['remaining_four_fr'])==4 and len(d['protected_six_rejections'])==6
 return {'sha256':sha(OUT/'failure-diagnostics.json'),'descriptive_case_instances_numerically_replayed':checked,'lost_established_repairs':{n:len(d['lost_established_repairs'][n]) for n in CANDIDATES},'fresh_general_FR128':{n:len(d['fresh_general_new_false_rejections_vs_signed'][n]) for n in CANDIDATES},'no_policy_or_gate_change':True}


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=('soundness','preflight','pretrain','prelabel','final'),default='final',nargs='?');parser.add_argument('--write-receipt',action='store_true');a=parser.parse_args();r=carry_soundness() if a.command=='soundness' else globals()[{'final':'final_audit'}.get(a.command,a.command)](a.write_receipt);print(json.dumps({k:r[k] for k in ('status','selected_candidate','scoped_experimental_eligibility','native_accounting','audit_fits','audit_native_jobs') if k in r},indent=2) if a.command!='soundness' else json.dumps(r,indent=2))
