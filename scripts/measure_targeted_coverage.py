#!/usr/bin/env python3
"""Frozen coverage expansion; shared1200s native budget, no retries or fits."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json,os,signal,subprocess,sys,time,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import validate_selected_features as prior
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
TRAIN=ROOT/'results/targeted-coverage-data';TEST=ROOT/'results/targeted-coverage-validation'
POLICY={'total_native_seconds':1200,'training_native_seconds':600,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
TRAIN_TEMPLATES=(
 ('shift_left_offset','sll(addi(in0,{k}),andi(in1,31))',[2,6,10,18,34,66,130,258]),
 ('shift_right_xor','srl(xor(in0,addi(in1,{k})),andi(in1,15))',[3,9,19,35,67,131,259,515]),
 ('shift_signed_sum','sra(add(in0,in1),andi(xori(in1,{k}),31))',[1,3,7,11,15,19,23,31]),
 ('shift_mask_add','add(sll(in0,andi(in1,{k})),in1)',[1,3,5,7,11,15,23,31]),
 ('shift_sub_xor','xor(srl(addi(in0,{k}),in1),sub(in0,in1))',[5,13,29,61,125,253,509,1021]),
 ('mixed_offset_sub','sub(add(in0,addi(in1,{k})),slli(in1,7))',[7,21,43,85,171,341,683,1365]),
 ('mixed_shift_xor','add(sub(slli(in0,{k}),in1),xor(in0,in1))',[1,2,4,6,9,14,21,29]),
 ('mixed_dual_arith','xor(add(in0,srli(in1,{k})),sub(in1,in0))',[1,3,5,8,12,17,24,30]),)
TEST_TEMPLATES=(
 ('heldout_shift_sum_xor','xor(sll(add(in0,in1),andi(in1,{k})),in0)',[3,7,15,31]),
 ('heldout_shift_xor_sub','sub(srl(xor(in0,in1),andi(in1,{k})),in0)',[1,7,23,31]),
 ('heldout_signed_sub_add','add(sra(sub(in0,in1),andi(in1,{k})),in1)',[3,11,15,31]),
 ('heldout_shift_arithmetic','xor(add(in0,sll(in1,andi(in0,{k}))),sub(in0,in1))',[1,5,15,31]),
 ('heldout_mixed_shift_sub','sub(add(slli(in0,{k}),in1),srli(in0,7))',[2,5,13,25]),
 ('heldout_mixed_shift_add','add(xor(srli(in0,{k}),in1),sub(in1,in0))',[2,6,16,27]),
 ('control_boolean','or(and(in0,srli(in1,{k})),xor(in0,in1))',[3,8,19,26]),
 ('control_compare','xor(slt(in0,addi(in1,{k})),srli(in1,9))',[11,47,191,767]),
 ('control_product','xor(mul(in0,addi(0,{k})),and(in0,in1))',[23,47,95,191]),
 ('control_constant_shift','and(xor(in0,slli(in1,{k})),srli(in0,3))',[2,7,18,28]),)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now

def candidates(kind):
 rows=[]
 for name,template,values in TRAIN_TEMPLATES if kind=='train' else TEST_TEMPLATES:
  for k in values:
   f=parse_formula(template.format(k=k)).canonical();rows.append({'candidate_id':'targeted-'+kind+':'+prior.sha_bytes(f.encode()),'formula':f,'template':name,'parameter':k})
 need(len(rows)==len({r['formula'] for r in rows})==(64 if kind=='train' else 40),'Exact unique cohort required');return rows

def prepare():
 need(not TRAIN.exists() and not TEST.exists(),'Fresh directories required')
 h=read(ROOT/'results/selection-validation/historical-formulas.json');p=read(ROOT/'results/selection-validation/candidates.json')
 need(len(h)==8706 and len(p)==40,'Prior inventory differs');history=sorted(set(h)|{r['formula'] for r in p})
 known=set().union(*(prior.identity_keys(f) for f in history))
 from isaforge.semantic_features_v7 import analyze_modes,Budget
 seen=set();reports={'train':[],'test':[]}
 for kind in ('train','test'):
  for row in candidates(kind):
   modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500));forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
   keys=set().union(*(prior.identity_keys(f) for f in forms))
   reports[kind].append({'candidate_id':row['candidate_id'],'forms':sorted(forms),'historical_identity_overlap':sorted(keys&known),'across_cohort_identity_overlap':sorted(keys&seen)})
   seen.update(keys)
 need(not any(r['historical_identity_overlap'] or r['across_cohort_identity_overlap'] for rs in reports.values() for r in rs),'Identity collision before labels')
 TRAIN.mkdir(parents=True);TEST.mkdir(parents=True)
 for kind,out in [('train',TRAIN),('test',TEST)]:
  write(out/'candidates.json',candidates(kind));write(out/'novelty.json',{'status':'pass','comparisons':reports[kind],'historical_count':len(history),'prior_inventory_count':8706,'previous_transfer_count':40,'scope':'Joint104screen: canonical, commutative V4 equivalence, V4/V5 normalization and prospective V7 aliases. Sufficient identities, not exhaustive semantic equivalence. Feature collisions distinct. Inherited historical-input-inventory scope; no application independence claim.'})
 write(TRAIN/'historical-formulas.json',history);tools=read(ROOT/'results/selection-validation/tools.json')
 for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
 write(TRAIN/'tools.json',tools)
 sources=[Path(__file__),ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_targeted_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 plan={'schema':'targeted-training-prospective-validation-v1','frozen_at_utc':now(),'policy':POLICY,'training_count':64,'test_count':40,'training_templates':TRAIN_TEMPLATES,'test_templates':TEST_TEMPLATES,
 'primary_model':'augmented217','baseline':'mapping217','secondary_model':'scoped_augmented217',
 'secondary_scope_gate':'Original AST has sll/srl/sra with in0/in1 in control subtree OR has add/addi/sub AND xor/xori; excludes any mul/mulh/mulhu/mulhsu. Literal AST, base fallback otherwise.',
 'success_rule':'Primary test MAE and positive-target MAPE strictly improve versus frozen mapping217; false_accept AND false_reject no worse at EACH cap32/64/128; maximum underprediction no worse. No posthoc criteria.',
 'fit_contract':'Zero measurement fits. One augmented217 fit originaltraining plus64; fixed scoped route secondary. Prior40 not training.',
 'chronology':'Joint cohort/protocol freeze and audit; train+test label-free features; train original RTL verification then labels; candidate artifact freeze and ALLordered test predictions freeze and audit; test RTL verification then labels.',
 'missing_rule':'Retain all rows/failures; no retries or replacements; missing cases make primary unavailable.',
 'scope':'Fresh synthetic heldout compositions24 plus controls16; no application-transfer, calibration, timing or full-core claim.',
 'sources':{str(x.relative_to(ROOT)):sha(x) for x in sources},'inputs':{str(x.relative_to(ROOT)):sha(x) for out in [TRAIN,TEST] for x in sorted(out.iterdir()) if x.is_file()},
 'prior_inventory_sources':{str(x.relative_to(ROOT)):sha(x) for x in [ROOT/'results/selection-validation/historical-formulas.json',ROOT/'results/selection-validation/historical-input-inventory.json',ROOT/'results/selection-validation/candidates.json']},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
 write(TRAIN/'plan.json',plan);return plan

def validate():
 plan=read(TRAIN/'plan.json');need(plan['policy']==POLICY,'Policy changed')
 for kind,out in [('train',TRAIN),('test',TEST)]:need(read(out/'candidates.json')==candidates(kind),'Cohort changed')
 for section in ('sources','inputs','prior_inventory_sources'):
  for path,digest in plan[section].items():need(sha(ROOT/path)==digest,'Binding changed: '+path)
 for tool in read(TRAIN/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
 return plan

def verify_point_freeze():
 f=read(TEST/'point-freeze.json');need(f['target_label_jobs']==0,'Test points frozen after labels')
 for path,digest in f['bindings'].items():need(sha(ROOT/path)==digest,'Test point binding changed: '+path)
 return f

def worker(kind,stage,index):
 validate();out=TRAIN if kind=='train' else TEST;rows=read(out/'candidates.json')
 need((TRAIN/('training-attempt.json' if kind=='train' or stage=='feature' else 'test-attempt.json')).exists(),'Owned attempt required')
 if kind=='test' and stage!='feature':verify_point_freeze()
 if stage=='feature':
  row=rows[index];folder=out/'raw/features'/str(index);tools=read(TRAIN/'tools.json');tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
  x,records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1);write(folder/'result.json',{**row,**records[0]})
 elif stage=='verify':
  from isaforge.rtl import verify_rtl_batch
  proof=verify_rtl_batch([r['formula'] for r in rows],out/'raw/verification',random_vectors=2048,seed=2026110902+(kind=='test'),timeout=180)
  need(proof['verified'] is True and proof['formula_count']==len(rows) and proof['total_comparisons']==2148*len(rows),'Incomplete verification');write(out/'raw/verification/result.json',proof)
 elif stage=='label':
  proof=read(out/'raw/verification/result.json');need(proof['verified'] and proof['total_comparisons']==2148*len(rows),'Complete verification required')
  from isaforge.synthesis import run_synthesis
  from isaforge.rtl import generate_rtl
  row=rows[index];folder=out/'raw/labels'/str(index);m=run_synthesis(row['formula'],folder,timeout=120)
  count=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values())
  need(count['SB_LUT4']==m['ice40_lut4_count'],'LUT recount differs');need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'Original RTL differs')
  write(folder/'result.json',{**row,'status':'complete','lut4':count['SB_LUT4'],'carry':count['SB_CARRY'],'rtl_sha256':m['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json'),'measurement_source':'Actual Yosys synth_ice40 defaults original RTL; SB_LUT4 only'})

def run(stage):
 validate();need((TRAIN/'preflight-audit.json').exists(),'Auditor receipt required');training=stage=='train';out=TRAIN if training else TEST
 filename='training-attempt.json' if training else 'test-attempt.json';need(not (TRAIN/filename).exists(),'Single attempt; no retries')
 used=0 if training else read(TRAIN/'completion.json')['native_elapsed_seconds']
 if not training:
  need(read(TRAIN/'completion.json')['complete'],'Training incomplete');verify_point_freeze();need((TEST/'prelabel-audit.json').exists(),'Test audit receipt required')
 budget=600 if training else 1200-used;began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
 write(TRAIN/filename,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'policy':POLICY,'fits':0})
 def owned(kind,phase,index=None):
  dest=TRAIN if kind=='train' else TEST;folder=dest/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index));folder.mkdir(parents=True,exist_ok=True)
  log=folder/'worker.log';cmd=[sys.executable,str(Path(__file__).resolve()),'worker','--kind',kind,'--stage',phase]
  if index is not None:cmd+=['--index',str(index)]
  started=now();process=None;error=None;code=None
  try:
   remaining=deadline-time.monotonic();need(remaining>0,'Shared native budget exhausted')
   with log.open('x') as stream:
    process=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
    try:code=process.wait(timeout=min(180,remaining))
    except subprocess.TimeoutExpired:raise TimeoutError('Worker or native deadline')
    need(code==0,'Worker failed: '+str(log))
  except Exception as caught:error=repr(caught)
  finally:
   if process is not None:
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()
  r={'kind':kind,'stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None};write(folder/'worker.json',r);jobs.append(r);return r
 def batch(kind,phase):
  with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(lambda i:owned(kind,phase,i),range(64 if kind=='train' else 40)))
  failures.extend(x for x in r if x['error']);need(not failures,'Incomplete native stage; no replacement/retry')
 try:
  if training:
   for kind,dest in [('train',TRAIN),('test',TEST)]:
    batch(kind,'feature');records=[read(dest/'raw/features'/str(i)/'result.json') for i in range(64 if kind=='train' else 40)]
    need(len(v6.columns())==336 and all(len(r['values'])==336 for r in records),'Exact336schema required');write(dest/'features.json',{'columns':list(v6.columns()),'records':records})
   a=read(TRAIN/'features.json')['records'];b=read(TEST/'features.json')['records'];keys={tuple(r['values']) for r in a}
   write(TEST/'feature-collisions.json',{'test_training_exact_full336_collisions':[r['candidate_id'] for r in b if tuple(r['values']) in keys],'scope':'Full336vector equality is distinct from formula identity; no row replacements.'})
  kind='train' if training else 'test';proof=owned(kind,'verify')
  if proof['error']:failures.append(proof)
  need(not failures,'Verification failed; labels forbidden');batch(kind,'label')
  write(out/'labels.json',[read(out/'raw/labels'/str(i)/'result.json') for i in range(64 if training else 40)])
 except Exception as error:failures.append({'stage':'attempt','error':repr(error)})
 finally:
  elapsed=time.monotonic()-began;write(out/'completion.json',{'completed_at_utc':now(),'complete':not failures,'native_elapsed_seconds':elapsed,'total_native_elapsed_seconds':used+elapsed,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'label_count':len(read(out/'labels.json')) if (out/'labels.json').exists() else 0,'policy':POLICY})
 return read(out/'completion.json')

def pack(kind):
 out=TRAIN if kind=='train' else TEST;raw=out/'raw';need(raw.is_dir(),'Raw evidence required');target=out/'raw-evidence.zip';need(not target.exists(),'Single archive')
 files=[p for p in sorted(raw.rglob('*')) if p.is_file()];manifest=[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,str(p.relative_to(out)))
 with zipfile.ZipFile(target) as z:
  for r in manifest:need(prior.sha_bytes(z.read(r['path']))==r['sha256'],'Archive verification failed')
 write(out/'raw-evidence-manifest.json',{'archive':target.name,'archive_sha256':sha(target),'files':manifest});shutil.rmtree(raw);return {'archive':str(target),'files':len(files),'sha256':sha(target)}

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run-train','run-test','worker','pack']);p.add_argument('--kind',choices=['train','test'],default='train');p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args()
 if a.command=='prepare':result=prepare()
 elif a.command=='worker':worker(a.kind,a.stage,a.index);return
 elif a.command=='pack':result=pack(a.kind)
 else:result=run('train' if a.command=='run-train' else 'test')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
