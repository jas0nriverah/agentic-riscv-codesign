#!/usr/bin/env python3
"""Fixed input-only200pool; prediction-only selected labels,300s shared native."""
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
SPEC=importlib.util.spec_from_file_location('_boundary_challenge_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
OUT=ROOT/'results/boundary-challenge-validation'
POLICY={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
PROOF_SEED=2026111101
PARAMETERS=((7,13,1),(23,61,1),(43,89,1),(173,257,1),(7,13,3),(23,61,3),(43,89,3),(173,257,3))
DATA_TEMPLATES=(
 ('addi_xori_xordata','addi(xori(xor(in0,in1),{c}),{d})'),
 ('xori_addi_xordata','xori(addi(xor(in0,in1),{d}),{c})'),
 ('xor_addi_xori_data','xor(addi(xori(in0,{c}),{d}),in1)'),
 ('xor_xori_addi_reverse','xor(xori(addi(in1,{d}),{c}),in0)'),
 ('addi_xori_ordata','addi(xori(or(in0,in1),{c}),{d})'),
 ('xori_addi_anddata','xori(addi(and(in0,in1),{d}),{c})'),
 ('addi_xori_low16_xordata','addi(xori(andi(xor(in0,in1),65535),{c}),{d})'),
 ('xori_addi_low31_xordata','xori(addi(andi(xor(in0,in1),2147483647),{d}),{c})'),
)
ROOT_TEMPLATES=(
 ('xor_add_reverse','xor(add({shift},in0),in1)'),
 ('add_dual_xor','add({shift},xor(in0,in1))'),
 ('xor_dual_add','xor({shift},add(in0,in1))'),
)
CONTROL_TEMPLATES=(
 ('control_static_mixed_and','and(add(srai(in1,{k}),srli(in0,3)),xor(in0,in1))',[1,3,7,15]),
 ('control_unsigned_add_or','or(srl(add(in0,in1),andi(xor(in0,in1),{k})),in0)',[1,3,7,31]),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def pool_candidates():
    rows=[]
    def append(formula,template,parameter,control):
        f=parse_formula(formula).canonical()
        rows.append({'candidate_id':'boundary-challenge-pool:'+prior.sha_bytes(f.encode()),
                     'formula':f,'template':template,'parameter':parameter,
                     'pool_index':len(rows),'reserved_control':control})
    for data_name,data_template in DATA_TEMPLATES:
        for root_name,root_template in ROOT_TEMPLATES:
            name='target_'+data_name+'__'+root_name
            for c,d,k in PARAMETERS:
                data=data_template.format(c=c,d=d)
                shift='sra('+data+',andi(or(in0,in1),'+str(k)+'))'
                append(root_template.format(shift=shift),name,[c,d,k],False)
    for name,template,values in CONTROL_TEMPLATES:
        for k in values:append(template.format(k=k),name,k,True)
    need(len(rows)==len({r['formula'] for r in rows})==200,'Exact unique fixed200pool required')
    return rows

def selected():
    seal=read(OUT/'selection.json');indices=seal['selected_pool_indices'];pool=read(OUT/'pool-candidates.json')
    need(8<=len(indices)<=24 and len(indices)==len(set(indices)),'At most16active+8controls required')
    need(all(type(i) is int and 0<=i<len(pool) for i in indices),'Valid selected pool indices required')
    rows=[pool[i] for i in indices]
    need(read(OUT/'candidates.json')==rows,'Selected candidates differ from exact pool subset')
    need(sum(r['reserved_control'] for r in rows)==8,'All8 fixed controls required')
    need({r['pool_index'] for r in rows if r['reserved_control']}=={r['pool_index'] for r in pool if r['reserved_control']},'Reserved controls changed')
    full=read(OUT/'pool-features.json');subset=read(OUT/'features.json')
    need(subset=={'columns':full['columns'],'records':[full['records'][i] for i in indices]},'Selected features differ from exact pool subset')
    return rows

def inventory():
    paths=[ROOT/'results/boundary-repair-validation'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

def draft_novelty():
    history,paths=inventory();known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history};seen=set();reports=[]
    from isaforge.semantic_features_v7 import analyze_modes,Budget
    for row in pool_candidates():
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
    write(OUT/'pool-candidates.json',pool_candidates());write(OUT/'historical-formulas.json',history)
    write(OUT/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':200,
          'previous_latest_consumed_count':40,'comparisons':reports,
          'scope':'Canonical,commutative V4,V4/V5normalized identities,V7aliases and original constant-erased AST skeletons against all-prior including boundary-repair40. Finite screens,not exhaustive semantic equivalence or application independence.'})
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(OUT/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_boundary_challenge.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'boundary-challenge-pool200-v1','frozen_at_utc':now(),'policy':POLICY,
          'training_count':0,'pool_count':200,'target_pool_count':192,'control_count':8,'maximum_selected_count':24,
          'all_pool_rows_consumed_for_future_novelty':True,
          'data_templates':DATA_TEMPLATES,'root_templates':ROOT_TEMPLATES,'parameter_sequence':PARAMETERS,
          'control_templates':CONTROL_TEMPLATES,'proof_random_seed':PROOF_SEED,
          'design_assumptions':'Fixed input-only192targetpool(8data ASTfamilies x3add/xorrootcompositions x8orderedconstant/maskparameters)+8fixedoutsidecontrols. Signed compound xor/and/or/narrowdata and lowmasks1/3 intended to challenge cap64/128 near consumed125pattern; no native cost guarantee. All200features and frozen predictions retained,including nonselected. No labels used for poolselection; no poolreplacement,extension,or retries.',
          'selection_rule':'Same frozen median policy only; up to16active exactmedian-versus-release prediction differences, excluding historical217-column feature collisions against all1825training+823consumed rows, deterministic round-robin sorted template names with fixed pool parameter order within each and at most one selected active per within-pool217feature key(first occurrence); append all8reservedcontrols unchanged in pool order. Any historical217collision or selected217duplicate involving reservedcontrols blocks eligibility without replacement. Log all collision data and retain every poolrow. Minimum4active across>=2templates and>=1cap128decisionchange required. Exact algorithm and acceptance gates frozen separately before features and labels.',
          'success_rule':'Freeze protocol and deterministic selection before features; freeze all200ordered predictions and selected subset before labels. Selected-full AND selected-active accuracy/false-acceptance/tail gates versus budget release and false-rejection gates versus signed incumbent; no postlabel selection.',
          'chronology':'Fixed200pool/protocol freeze and independent preflight;all200label-free native features;allpredictionpoints,deterministic selected indices and exact selected feature subset freeze;independent prelabel receipt;original selectedRTL verification then selected originalRTL labels.',
          'native_accounting':'Sum elapsed wall time all200poolfeatures+selectedverification/labels including subprocess startup,extraction,synthesis,and failures;shared300s,max2workers,no overlapping stages. Audit/modelidle excluded.',
          'missing_rule':'Keep all200poolrows/features/points and allselectedlabels/failures; no retries,replacements,poolextensions,or complete-cohort primary with missingcases.',
          'scope':'Prediction-disagreement conditional targeted synthetic challenge only; no unbiased generalization,application-transfer,calibrated bound,timing,power,full-core orCPU claim.',
          'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
          'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(OUT/'plan.json',plan);return plan

def validate():
    p=read(OUT/'plan.json');need(p['policy']==POLICY and read(OUT/'pool-candidates.json')==pool_candidates(),'Frozen protocol/cohort changed')
    for section in ('sources','inputs','prior_inventory_sources'):
        for path,digest in p[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed:'+path)
    for tool in read(OUT/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
    return p

def point_freeze():
    p=read(OUT/'point-freeze.json');need(p['target_label_jobs']==0 and bool(p['bindings']),'Prelabel point/model freeze required')
    for path,digest in p['bindings'].items():need(sha(ROOT/path)==digest,'Frozen point/model changed:'+path)
    selected()
    return p


def worker(stage,index):
    from collections import Counter
    validate();need((OUT/('feature-attempt.json' if stage=='feature' else 'label-attempt.json')).exists(),'Owned single attempt required')
    if stage=='feature':
        row=read(OUT/'pool-candidates.json')[index];folder=OUT/'raw/features'/str(index);tools=read(OUT/'tools.json')
        tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
        _,records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1)
        write(folder/'result.json',{**row,**records[0],'status':'complete'})
        return
    point_freeze();rows=selected()
    if stage=='verify':
        from isaforge.rtl import verify_rtl_batch
        p=verify_rtl_batch([r['formula'] for r in rows],OUT/'raw/verification',random_vectors=2048,seed=PROOF_SEED,timeout=180)
        need(p['verified'] is True and p['formula_count']==len(rows) and p['total_comparisons']==2148*len(rows),'Complete selected originalRTL verification required')
        write(OUT/'raw/verification/result.json',p)
    else:
        proof=read(OUT/'raw/verification/result.json')
        need(proof['verified'] and proof['total_comparisons']==2148*len(rows),'Selected originalRTL verification required')
        from isaforge.synthesis import run_synthesis
        from isaforge.rtl import generate_rtl
        row=rows[index];folder=OUT/'raw/labels'/str(index);metrics=run_synthesis(row['formula'],folder,timeout=120)
        counts=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values())
        need(counts['SB_LUT4']==metrics['ice40_lut4_count'],'LUT recount differs')
        need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'Selected originalRTL differs')
        write(folder/'result.json',{**row,'status':'complete','lut4':counts['SB_LUT4'],'carry':counts['SB_CARRY'],
              'rtl_sha256':metrics['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json'),
              'measurement_source':'Actual Yosys synth_ice40 defaults selected originalRTL;SB_LUT4only'})

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
    rows=pool_candidates() if feature else selected()
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
        for i,row in enumerate(rows):
            p=OUT/'raw'/(phase+'s')/str(i)/'result.json'
            records.append(read(p) if p.exists() else {**row,'status':'failed','error':'No complete native result;see retained worker evidence'})
        return records
    phase='feature' if feature else 'label'
    try:
        if not feature:
            proof=owned('verify')
            if proof['error']:failures.append(proof)
            need(not failures,'Original RTL verification failed;labels forbidden')
        with ThreadPoolExecutor(max_workers=POLICY['workers']) as pool:results=list(pool.map(lambda i:owned(phase,i),range(len(rows))))
        failures.extend(r for r in results if r['error']);records=retained(phase)
        if feature:
            write(OUT/'pool-features.json',{'columns':list(v6.columns()),'records':records})
            need(len(v6.columns())==336 and all(r['status']=='complete' and len(r['values'])==336 for r in records),'Incomplete336features;no replacements')
        else:write(OUT/'labels.json',records)
        need(not failures,'Incomplete stage;every failure retained;no retries or replacements')
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
        write(OUT/('pool-features.json' if feature else 'labels.json'),{'columns':list(v6.columns()),'records':retained(phase)} if feature else retained(phase))
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
