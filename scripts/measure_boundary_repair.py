#!/usr/bin/env python3
"""Input-frozen fresh40 boundary challenge; no training, 300s shared native."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import validate_selected_features as prior
from isaforge.features import parse_formula
from isaforge import area_model_v6 as v6
RUNNER=ROOT/'scripts/measure_guarded_revision.py'
SPEC=importlib.util.spec_from_file_location('_boundary_repair_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
OUT=ROOT/'results/boundary-repair-validation'
POLICY={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
PROOF_SEED=2026111003
TEMPLATES=(
 ('boundary_full_compound_addxor_or','xor(add(sra(addi(xori(in0,43),89),andi(or(in0,in1),{k})),or(in0,in1)),in1)',[1,3,7,31]),
 ('boundary_full_compound_xorand_add','add(xor(sra(xori(addi(in1,89),43),andi(add(in0,in1),{k})),and(in0,in1)),in0)',[1,3,7,31]),
 ('boundary_full_compound_subxor','sub(sra(addi(xori(in0,43),89),andi(sub(in0,in1),{k})),xor(in0,in1))',[1,3,7,31]),
 ('boundary_full_compound_xor_oradd','xor(sra(xori(addi(in0,89),43),andi(in1,{k})),or(add(in0,in1),in1))',[1,3,7,31]),
 ('boundary_low8_compound_xorand','xor(sra(andi(addi(xori(in0,43),89),255),andi(in1,{k})),and(in0,in1))',[1,3,7,31]),
 ('boundary_low16_compound_addxor','add(sra(andi(xori(addi(in1,89),43),65535),andi(in0,{k})),xor(in0,in1))',[1,3,7,31]),
 ('boundary_signed8_compound_or','or(sra(slli(andi(addi(xori(in0,43),89),255),24),andi(xor(in0,in1),{k})),in1)',[1,3,7,31]),
 ('boundary_signed16_compound_xor','xor(sra(slli(andi(xori(addi(in1,89),43),65535),16),andi(or(in0,in1),{k})),in0)',[1,3,7,31]),
 ('control_unsigned_offset_xorshift','srl(addi(in0,89),andi(xor(in0,in1),{k}))',[1,3,7,31]),
 ('control_static_signed_mixed_or','xor(add(srai(in0,{k}),srli(in1,5)),or(in0,in1))',[1,3,7,15]),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def candidates():
    rows=[]
    for name,template,values in TEMPLATES:
        for k in values:
            f=parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id':'boundary-repair-test:'+prior.sha_bytes(f.encode()),
                         'formula':f,'template':name,'parameter':k})
    need(len(rows)==len({r['formula'] for r in rows})==40,'Exact unique fresh40 required')
    return rows

def inventory():
    paths=[ROOT/'results/budget-release-data'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    paths += [ROOT/'results/budget-release-validation'/n for n in ('candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

def draft_novelty():
    history,paths=inventory();known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history};seen=set();reports=[]
    from isaforge.semantic_features_v7 import analyze_modes,Budget
    for row in candidates():
        modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500))
        forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
        keys=set().union(*(prior.identity_keys(f) for f in forms))
        reports.append({'candidate_id':row['candidate_id'],'forms':sorted(forms),
                        'historical_identity_overlap':sorted(keys&known),'within_identity_overlap':sorted(keys&seen),
                        'historical_skeleton_overlap':skeleton(row['formula']) in old_skeletons})
        seen.update(keys)
    return history,paths,reports

def prepare():
    need(not OUT.exists(),'Fresh directory required')
    history,paths,reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] for r in reports),
         'Input-only collision; stop before freeze or native jobs')
    write(OUT/'candidates.json',candidates());write(OUT/'historical-formulas.json',history)
    write(OUT/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':40,
          'previous_latest_consumed_count':72,'comparisons':reports,
          'scope':'Canonical,commutative V4,V4/V5normalized identities,V7aliases and original constant-erased AST skeletons against all-prior including budget-release72. Finite screens,not exhaustive semantic equivalence or application independence.'})
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(OUT/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_boundary_repair.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'boundary-repair-fresh40-v1','frozen_at_utc':now(),'policy':POLICY,
          'training_count':0,'test_count':40,'templates':TEMPLATES,'proof_random_seed':PROOF_SEED,
          'design_assumptions':'Input-only design,not synthesis filtering: masks1/3 intend low variable-shift cost near64/128; masks7/31 stress wider shifts. Four fullwidth compound families16rows; two zero-extended8/16bit families8rows; two signed narrow8/16bit families8rows;8outside-route controls. Width truncation and masks plausibly span cap boundaries but do not guarantee native target counts or any success. No row replacement after features or labels.',
          'success_rule':'Policy,finite development hierarchy,and exact fresh gates frozen separately before labels; complete40 and named boundary subgroups evaluated against signed incumbent and budget-release candidate without postlabel selection.',
          'chronology':'Fresh cohort/protocol freeze and independent preflight;40label-free features;selected existing weights and all ordered predictions freeze;independent prelabel receipt;original RTL verification then all40original RTL synthesis labels.',
          'native_accounting':'Sum elapsed wall time features+labels including subprocess startup,verification,extraction,synthesis andfailures;shared300s,max2workers,no overlapping stages. Idle audit/model time excluded.',
          'missing_rule':'Keep all40rows andfailures;no retries,replacements,or complete-cohort primary with missingcases.',
          'scope':'Targeted synthetic32compound signed distribution plus8controls only;no application-transfer,calibrated bound,timing,power,full-core orCPU claim.',
          'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
          'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(OUT/'plan.json',plan);return plan

def validate():
    p=read(OUT/'plan.json');need(p['policy']==POLICY and read(OUT/'candidates.json')==candidates(),'Frozen protocol/cohort changed')
    for section in ('sources','inputs','prior_inventory_sources'):
        for path,digest in p[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed:'+path)
    for tool in read(OUT/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
    return p

def point_freeze():
    p=read(OUT/'point-freeze.json');need(p['target_label_jobs']==0 and bool(p['bindings']),'Prelabel point/model freeze required')
    for path,digest in p['bindings'].items():need(sha(ROOT/path)==digest,'Frozen point/model changed:'+path)
    return p

ORIGINAL_WORKER=native.worker

def worker(stage,index):
    if stage!='verify':return ORIGINAL_WORKER('test',stage,index)
    validate();need((OUT/'label-attempt.json').exists(),'Owned single attempt required');point_freeze()
    from isaforge.rtl import verify_rtl_batch
    p=verify_rtl_batch([r['formula'] for r in candidates()],OUT/'raw/verification',random_vectors=2048,seed=PROOF_SEED,timeout=180)
    need(p['verified'] is True and p['formula_count']==40 and p['total_comparisons']==85920,'Complete original RTL verification required')
    write(OUT/'raw/verification/result.json',p)

def configure_runner():
    native.TRAIN=OUT;native.TEST=OUT;native.validate=validate;native.verify_point_freeze=point_freeze
    native.__file__=str(Path(__file__).resolve());return native

def run(stage):
    validate();native.receipt(OUT/'preflight-audit.json');feature=stage=='features'
    attempt=OUT/('feature-attempt.json' if feature else 'label-attempt.json')
    need(not attempt.exists(),'Single attempt only;no retries')
    used=0 if feature else read(OUT/'feature-completion.json')['total_native_elapsed_seconds']
    if not feature:
        need(read(OUT/'feature-completion.json')['complete'],'Complete features required')
        native.receipt(OUT/'prelabel-audit.json');point_freeze()
    budget=POLICY['total_native_seconds']-used;need(budget>0,'Native budget exhausted')
    began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'stage':stage,'policy':POLICY,'fits':0})
    def owned(phase,index=None):
        folder=OUT/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log'
        command=[sys.executable,str(Path(__file__).resolve()),'worker','--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Shared native deadline exhausted')
            with log.open('x') as stream:
                process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:raise TimeoutError('Shared native deadline')
                need(code==0,'Worker failed:'+str(log))
        except Exception as caught:error=repr(caught)
        finally:
            if process:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        result={'kind':'test','stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
        write(folder/'worker.json',result);jobs.append(result);return result
    def retained(phase):
        records=[]
        for i,row in enumerate(candidates()):
            p=OUT/'raw'/(phase+'s')/str(i)/'result.json'
            records.append(read(p) if p.exists() else {**row,'status':'failed','error':'No complete native result;see retained worker evidence'})
        return records
    phase='feature' if feature else 'label'
    try:
        if not feature:
            proof=owned('verify')
            if proof['error']:failures.append(proof)
            need(not failures,'Original RTL verification failed;labels forbidden')
        with ThreadPoolExecutor(max_workers=POLICY['workers']) as pool:results=list(pool.map(lambda i:owned(phase,i),range(40)))
        failures.extend(r for r in results if r['error']);records=retained(phase)
        if feature:
            write(OUT/'features.json',{'columns':list(v6.columns()),'records':records})
            need(len(v6.columns())==336 and all(r['status']=='complete' and len(r['values'])==336 for r in records),'Incomplete336features;no replacements')
        else:write(OUT/'labels.json',records)
        need(not failures,'Incomplete stage;every failure retained;no retries or replacements')
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
        write(OUT/('features.json' if feature else 'labels.json'),{'columns':list(v6.columns()),'records':retained(phase)} if feature else retained(phase))
    finally:
        elapsed=time.monotonic()-began
        result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':elapsed,'total_native_elapsed_seconds':used+elapsed,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,'label_count':sum(r['status']=='complete' for r in read(OUT/'labels.json')) if (OUT/'labels.json').exists() else 0}
        write(OUT/('feature-completion.json' if feature else 'completion.json'),result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['draft','prepare','features','labels','worker','pack']);p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args();configure_runner()
    if a.command=='draft':
        history,paths,reports=draft_novelty();r={'historical_count':len(history),'collisions':[r for r in reports if r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap']]}
    elif a.command=='prepare':r=prepare()
    elif a.command=='worker':worker(a.stage,a.index);return
    elif a.command=='pack':r=native.pack('test')
    else:r=run(a.command)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
