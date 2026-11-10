#!/usr/bin/env python3
"""Second untouched32 synthetic composition test;120s native, zero fits/retries."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import measure_targeted_coverage as first
import validate_selected_features as prior
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
OUT=ROOT/'results/budget-preserving-validation'
POLICY={'total_native_seconds':120,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
TEMPLATES=(
 ('signed_offset_boolean','xor(sra(addi(in0,{k}),in1),and(in0,in1))',[5,37,149,601]),
 ('right_sub_boolean','add(srl(sub(in0,in1),andi(in0,{k})),xor(in0,in1))',[1,7,15,31]),
 ('left_boolean_dualshift','sub(sll(xor(in0,in1),andi(in0,{k})),srli(in1,5))',[3,7,23,31]),
 ('signed_dual_arithmetic','xor(sub(in0,sra(in1,andi(in0,{k}))),add(in0,in1))',[1,5,15,31]),
 ('mixed_shift_difference','add(xor(slli(in1,{k}),in0),srli(sub(in0,in1),3))',[2,7,15,27]),
 ('control_boolean_dualshift','and(or(in0,slli(in1,{k})),xor(in1,srli(in0,5)))',[3,9,18,26]),
 ('control_unsigned_compare','add(sltu(in0,addi(in1,{k})),and(in0,in1))',[13,53,211,853]),
 ('control_product_sub','sub(mul(in1,addi(0,{k})),or(in0,in1))',[23,59,107,211]),)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now

def skeleton(formula):
 def convert(node):return (node.value,tuple(convert(c) for c in node.children)) if node.children else ('#' if isinstance(node.value,int) else node.value)
 return repr(convert(parse_formula(formula)))
def candidates():
 rows=[]
 for name,template,values in TEMPLATES:
  for k in values:
   f=parse_formula(template.format(k=k)).canonical();rows.append({'candidate_id':'budget-preserving-test:'+prior.sha_bytes(f.encode()),'formula':f,'template':name,'parameter':k})
 need(len(rows)==len({r['formula'] for r in rows})==32,'Exact32 unique cohort required');return rows

def prepare():
 need(not OUT.exists(),'Fresh directory required')
 paths=[first.TRAIN/n for n in ('historical-formulas.json','candidates.json','novelty.json')]+[first.TEST/n for n in ('candidates.json','novelty.json')]
 history=set(read(paths[0]));history.update(r['formula'] for p in [first.TRAIN/'candidates.json',first.TEST/'candidates.json'] for r in read(p))
 for p in [first.TRAIN/'novelty.json',first.TEST/'novelty.json']:
  history.update(f for r in read(p)['comparisons'] for f in r['forms'])
 known=set().union(*(prior.identity_keys(f) for f in history));skeletons={skeleton(f) for f in history};seen=set();reports=[]
 from isaforge.semantic_features_v7 import analyze_modes,Budget
 for row in candidates():
  modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500));forms={row['formula'],*(m['normalized_formula'] for m in modes.values())};keys=set().union(*(prior.identity_keys(f) for f in forms))
  reports.append({'candidate_id':row['candidate_id'],'forms':sorted(forms),'historical_identity_overlap':sorted(keys&known),'within_identity_overlap':sorted(keys&seen),'historical_skeleton_overlap':skeleton(row['formula']) in skeletons});seen.update(keys)
 need(not any(r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] for r in reports),'Input-only draft collision; stop before freeze/features/labels')
 OUT.mkdir(parents=True);write(OUT/'candidates.json',candidates());write(OUT/'historical-formulas.json',sorted(history));write(OUT/'novelty.json',{'status':'pass','comparisons':reports,'historical_count':len(history),'joint_new_count':32,'prior_original_inventory_count':8706,'consumed_previous40_count':40,'previous_train64_count':64,'first_fresh40_count':40,'scope':'Canonical/commutative/V4/V5normalized identities and V7aliases; constant-erased original AST composition skeletons versus all prior formulas. Not exhaustive semantic equivalence or application independence.'})
 write(OUT/'tools.json',read(first.TRAIN/'tools.json'))
 sources=[Path(__file__),ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_budget_preserving_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
 plan={'schema':'budget-preserving-second-fresh32-v1','frozen_at_utc':now(),'policy':POLICY,'candidate_count':32,'templates':TEMPLATES,'primary_model':'budget_preserving_scoped_augmented217','baseline':'base','success_rule':'MAE and positive-target MAPE strictly improve; maximum underprediction and false_accept AND false_reject no worse separately at cap32/64/128. No posthoc criteria.',
 'point_policy':'min(max(base,scoped_augmented217),next_cap(base)), next_cap is smallest of32/64/128 >=base or positive infinity if base>128. Fixed forest/route; no fit.',
 'chronology':'Input protocol/cohort freeze; bounded label-free native features; policy/model/all32ordered points freeze and audit; RTLverification then actualiCE40labels. Separate stageelapsed summed; idle/audit time excluded.',
 'scope':'Second fresh synthetic compositions20targeted+12controls only; no application-transfer, calibration, timing or fullcore claim.',
 'missing_rule':'Retain all32rows/failures; no replacement/retry; missingcase blocks complete-cohort primary.',
 'prior_native_seconds':read(first.TEST/'completion.json')['total_native_elapsed_seconds'],'current_round_total_native_cap_seconds':1200,
 'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},'inputs':{str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file()},'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
 write(OUT/'plan.json',plan);return plan

def validate():
 p=read(OUT/'plan.json');need(p['policy']==POLICY and read(OUT/'candidates.json')==candidates(),'Protocol/cohort changed')
 for section in ('sources','inputs','prior_inventory_sources'):
  for path,digest in p[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed: '+path)
 for tool in read(OUT/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
 return p

def points():
 f=read(OUT/'point-freeze.json');need(f['target_label_jobs']==0,'Points must precede labels')
 for path,digest in f['bindings'].items():need(sha(ROOT/path)==digest,'Point/modelbinding changed: '+path)
 return f

def worker(stage,index):
 validate();rows=read(OUT/'candidates.json');need((OUT/('feature-attempt.json' if stage=='feature' else 'label-attempt.json')).exists(),'Owned attempt required')
 if stage!='feature':points()
 if stage=='feature':
  folder=OUT/'raw/features'/str(index);row=rows[index];tools=read(OUT/'tools.json');tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
  _,records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1);write(folder/'result.json',{**row,**records[0]})
 elif stage=='verify':
  from isaforge.rtl import verify_rtl_batch
  p=verify_rtl_batch([r['formula'] for r in rows],OUT/'raw/verification',random_vectors=2048,seed=2026110903,timeout=100)
  need(p['verified'] and p['formula_count']==32 and p['total_comparisons']==68736,'Complete RTLproof required');write(OUT/'raw/verification/result.json',p)
 else:
  p=read(OUT/'raw/verification/result.json');need(p['verified'] and p['total_comparisons']==68736,'OriginalRTLproof required')
  from isaforge.synthesis import run_synthesis
  from isaforge.rtl import generate_rtl
  row=rows[index];folder=OUT/'raw/labels'/str(index);m=run_synthesis(row['formula'],folder,timeout=100)
  c=Counter(x['type'] for x in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values());need(c['SB_LUT4']==m['ice40_lut4_count'],'LUTrecount differs');need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'OriginalRTLdiffers')
  write(folder/'result.json',{**row,'status':'complete','lut4':c['SB_LUT4'],'carry':c['SB_CARRY'],'rtl_sha256':m['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json'),'measurement_source':'Actual Yosys synth_ice40 defaults originalRTL; SB_LUT4only'})

def run(stage):
 validate();feature=stage=='feature';name='feature-attempt.json' if feature else 'label-attempt.json';need(not (OUT/name).exists(),'Singleattempt; no retries')
 used=0 if feature else read(OUT/'feature-completion.json')['native_elapsed_seconds']
 if not feature:need(read(OUT/'feature-completion.json')['complete'],'Incompletefeatures');points();need(read(OUT/'prelabel-audit.json')['status']=='pass','Auditorreceipt required')
 budget=min(120-used,1200-read(OUT/'plan.json')['prior_native_seconds']-used);began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
 write(OUT/name,{'started_at_utc':now(),'budget_seconds':budget,'prior_stage_native_seconds':used,'fits':0,'policy':POLICY})
 def owned(phase,index=None):
  folder=OUT/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index));folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log';cmd=[sys.executable,str(Path(__file__).resolve()),'worker','--stage',phase]
  if index is not None:cmd+=['--index',str(index)]
  started=now();process=None;error=None;code=None
  try:
   remain=deadline-time.monotonic();need(remain>0,'Totalnative120s exhausted')
   with log.open('x') as stream:
    process=subprocess.Popen(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=process.wait(timeout=remain)
    except subprocess.TimeoutExpired:raise TimeoutError('Native120second shareddeadline')
    need(code==0,'Workerfailed: '+str(log))
  except Exception as e:error=repr(e)
  finally:
   if process:
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()
  r={'stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None};write(folder/'worker.json',r);jobs.append(r);return r
 try:
  if not feature:
   r=owned('verify')
   if r['error']:failures.append(r)
   need(not failures,'Verificationfailed; labelsforbidden')
  phase='feature' if feature else 'label'
  with ThreadPoolExecutor(max_workers=2) as pool:rs=list(pool.map(lambda i:owned(phase,i),range(32)))
  failures.extend(r for r in rs if r['error']);need(not failures,'Incompletestage; no retry/replacement')
  records=[read(OUT/'raw'/('features' if feature else 'labels')/str(i)/'result.json') for i in range(32)]
  if feature:
   need(len(v6.columns())==336 and all(len(r['values'])==336 for r in records),'Exact336schema required');write(OUT/'features.json',{'columns':list(v6.columns()),'records':records})
  else:write(OUT/'labels.json',records)
 except Exception as e:failures.append({'stage':'attempt','error':repr(e)})
 finally:
  elapsed=time.monotonic()-began;result={'completed_at_utc':now(),'complete':not failures,'native_elapsed_seconds':elapsed,'total_native_elapsed_seconds':used+elapsed,'current_round_total_native_seconds':read(OUT/'plan.json')['prior_native_seconds']+used+elapsed,'native_worker_jobs':jobs,'failures':failures,'fits':0,'policy':POLICY};write(OUT/('feature-completion.json' if feature else 'completion.json'),result)
 return result

def pack():
 previous=first.TRAIN
 try:first.TRAIN=OUT;return first.pack('train')
 finally:first.TRAIN=previous

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','features','labels','worker','pack']);p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args()
 if a.command=='prepare':r=prepare()
 elif a.command=='worker':worker(a.stage,a.index);return
 elif a.command=='pack':r=pack()
 else:r=run('feature' if a.command=='features' else 'label')
 print(json.dumps(r,indent=2))
if __name__=='__main__':main()
