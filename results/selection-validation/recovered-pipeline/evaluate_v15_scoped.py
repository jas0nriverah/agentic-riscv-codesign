#!/usr/bin/env python3
"""Predeclared32 related synthetic stress originals; no application-transfer claim.

prepare checks input novelty without native jobs/models/new target reads. run is
one Git-bound900s attempt: full336 features, frozen V6/V9/V15 points, verification,
then original RTL targets. No fits, retries, replacements or label-guided gates.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
import measure_v11e_transfer as hardware
import predict_v11d_transfer as frozen

SEED=2026101915
INPUT_AMENDMENT='archive/2026-10-19-v15-preflight'
POLICY={'attempt_seconds':900,'worker_seconds':360,'workers':2,'vectors_per_original':2148,
    'minimum_free_bytes':8*1024**3,'maximum_attempt_bytes':8*1024**3,'initial_free_bytes':16*1024**3,
    'retries':0,'replacement_candidates':0,'fits':0,'calibration_jobs':0}
TEMPLATES=(
    ('xor_then_constmul','mul(xor(in0,in1),addi(0,{p}))',(31,47,79,95,111,127,143,159)),
    ('constmul_then_xor','xor(mul(in0,addi(0,{p})),in1)',(31,47,79,95,111,127,143,159)),
    ('xor_signed_shift','sub(srai(xor(in0,in1),{p}),srai(in1,31))',(2,4,6,8,10,12,14,16)),
    ('and_signed_shift','sub(srai(and(in0,in1),{p}),srai(in1,31))',(2,4,6,8,10,12,14,16)))
NOVELTY_REQUIRED={
    'training1761':'results/2026-10-15-v13b-coverage-recovery/fitting/fitting.json',
    'v11':'results/2026-10-16-v11-model-inputs/candidates.json',
    'pre_reservation2929':'results/2026-10-16-v11-model-inputs/pre-reservation-reference.json',
    'v8_training':'results/2026-10-15-v8-application-transfer/training/training-data.json'}
need,read,sha,write=frozen.need,frozen.read,frozen.sha,frozen.write
now=lambda:datetime.now(timezone.utc).isoformat()


def candidates():
    result=[]
    for name,template,parameters in TEMPLATES:
        for p in parameters:
            formula=parse_formula(template.format(p=p)).canonical()
            result.append({'candidate_id':'v15-stress:'+hashlib.sha256(formula.encode()).hexdigest(),
                'formula':formula,'template':name,'parameter':p})
    need(len(result)==len({r['formula'] for r in result})==32,'Exactly32 fixed unique originals required')
    return result


def formula_inputs(data):
    """Project formulas/declared aliases only; no numerical outcome is used."""
    if isinstance(data,dict):
        if isinstance(data.get('formula'),str):
            yield data['formula']
            yield from (f for f in data.get('accepted_forms',[]) if isinstance(f,str))
        for k,v in data.items():
            if k not in ('formula','accepted_forms'): yield from formula_inputs(v)
    elif isinstance(data,list):
        for row in data: yield from formula_inputs(row)


def novelty(rows, references):
    wanted={r['formula'] for r in rows}; reports=[]; bindings={}
    for name,path in references.items():
        path=Path(path).resolve(); need(path.is_file() and not path.is_symlink(),'Missing novelty input: '+str(path))
        data=read(path); formulas={parse_formula(f).canonical() for f in formula_inputs(data)}
        if name=='training1761': need(len(formulas)==1761,'Exactly1761 fitting originals required')
        if name=='v11': need(len(formulas)==327,'Exactly327 V11 originals required')
        if name=='pre_reservation2929':
            need(isinstance(data,list) and len(data)==2929,'Exactly2929 pre-reservation original rows required')
        overlaps=sorted(wanted&formulas)
        reports.append({'name':name,'path':str(path.relative_to(ROOT)),'sha256':sha(path),
            'formula_or_declared_alias_count':len(formulas),'overlap':overlaps})
        bindings[path]=sha(path)
    need(not any(r['overlap'] for r in reports),'Existing original/declared alias: stop without replacements')
    return {'status':'pass','comparisons':reports,'all32_absent':True,
        'scope':'Canonical originals and saved accepted aliases only; no new equivalence solver or semantic novelty proof. Historical mixed fitting files are projected to input strings only; no historical target value is used.'},bindings


def input_amendment():
    return {'id':'V15-I1','archive':INPUT_AMENDMENT,'manifest_sha256':sha(ROOT/INPUT_AMENDMENT/'manifest.json'),
        'scope':'Input-only pre-freeze rejection of complete fourth template; new and_signed_shift template retains all8 fixed k and the other24 exact. No scientific job or new target preceded this amendment.'}


def source_paths():
    return sorted({Path(__file__).resolve(),ROOT/'tests/test_evaluate_v15_scoped.py',
        ROOT/'scripts/model_v15_scoped.py',ROOT/'tests/test_model_v15_scoped.py',
        ROOT/'scripts/measure_v11e_transfer.py',ROOT/'scripts/predict_v11d_transfer.py',
        *hardware.native.required_sources(),ROOT/'scripts/capture_v11_spooled.py',
        ROOT/'scripts/measure_v6.py',ROOT/'scripts/evaluate_v6.py',ROOT/'scripts/evaluate_v5.py',ROOT/'scripts/evaluate_v4.py',
        ROOT/'scripts/prepare_v11_model_comparison.py',ROOT/'scripts/develop_v13_coverage.py',
        *sorted((ROOT/'isaforge').glob('*.py')),*sorted((ROOT/INPUT_AMENDMENT).glob('*'))})


def default_references():
    refs={name:ROOT/path for name,path in NOVELTY_REQUIRED.items()}
    for path in sorted((ROOT/'results').glob('*/consumed-input-ledger.json')):
        refs['prior_consumed:'+path.parent.name]=path
    # Original V8 application input pools, when retained, precede V15 labels.
    for path in sorted((ROOT/'results/2026-10-15-v8-application-transfer').rglob('candidates.json')):
        refs['v8_input:'+path.relative_to(ROOT).as_posix()]=path
    return refs


def prepare(root):
    root=Path(root).resolve(); need(root.is_relative_to(ROOT/'results') and not root.exists(),'Fresh result directory required')
    rows=candidates(); report,bindings=novelty(rows,default_references())
    tools=read(ROOT/frozen.TOOLS); hardware.native.validate_tools(tools)
    models={}
    for name,(relative,h,count) in frozen.inputs.MODELS.items():
        artifact=ROOT/relative; need(sha(artifact)==h,'Frozen artifact changed')
        metadata=artifact.with_suffix('.json'); info=read(metadata)
        need(info['artifact_sha256']==h and info['training_formula_count']==count and info['calibration']['status']=='uncalibrated','Frozen metadata changed')
        need(info['feature_columns']==list(v6.columns()) and info['mapping_columns']==list(v6.mapping_columns()),'Frozen336/217 schema required')
        models[name]={'path':relative,'sha256':h,'metadata_sha256':sha(metadata),'training_rows':count}
        bindings.update({artifact:h,metadata:sha(metadata)})
    bindings.update({p:sha(p) for p in source_paths()}); bindings[ROOT/frozen.TOOLS]=sha(ROOT/frozen.TOOLS)
    runtime=frozen.runtime()
    tool={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']}
    need(all(read((ROOT/e['path']).with_suffix('.json'))['frozen_tool']==tool for e in models.values()),'Same frozen feature tool required')
    root.mkdir(parents=True); write(root/'candidates.json',rows); write(root/'novelty.json',report)
    write(root/'tools.json',tools); write(root/'runtime.json',runtime)
    plan={'schema':'isaforge-v15-synthetic-stress-plan-v1','created_at_utc':now(),'policy':dict(POLICY),
        'candidate_count':32,'input_amendment':input_amendment(),'templates':[{'name':n,'formula':f,'parameters':list(p)} for n,f,p in TEMPLATES],
        'candidates_sha256':sha(root/'candidates.json'),'novelty_sha256':sha(root/'novelty.json'),
        'tools_sha256':sha(root/'tools.json'),'runtime_sha256':sha(root/'runtime.json'),'models':models,
        'columns':list(v6.columns()),'frozen_tool':tool,
        'bindings':[{'path':str(p.relative_to(ROOT)),'sha256':h} for p,h in sorted(bindings.items())],
        'source_paths':[p.relative_to(ROOT).as_posix() for p in source_paths()],
        'primary':'Equal four-template mean of within-template MAE,8 originals/template; V15 minus V6 and V9.',
        'scope':'Prospective covered-domain synthetic composition stress, not fresh application transfer. All32 are inside the fixed gate; V15 equals V9 by construction. Gate fixed before labels; all32 retained or primary unavailable. No fits.',
        'calls':{'native_jobs':0,'model_artifacts_loaded':0,'new_labels':0,'fits':0}}
    write(root/'plan.json',plan); return plan


def validate(root):
    root=Path(root).resolve(); plan=read(root/'plan.json')
    need(plan['schema']=='isaforge-v15-synthetic-stress-plan-v1' and plan['policy']==POLICY and plan['candidate_count']==32,'Exact fixed32 policy required')
    need(plan['input_amendment']==input_amendment(),'Named pre-freeze input amendment changed')
    need(read(root/'candidates.json')==candidates() and sha(root/'candidates.json')==plan['candidates_sha256'],'Fixed original pool changed')
    for name,key in [('novelty.json','novelty_sha256'),('tools.json','tools_sha256'),('runtime.json','runtime_sha256')]: need(sha(root/name)==plan[key],'Prepared input changed')
    need(read(root/'novelty.json')['status']=='pass' and read(root/'novelty.json')['all32_absent'] is True,'Novelty check must precede labels')
    need(plan['source_paths']==[p.relative_to(ROOT).as_posix() for p in source_paths()],'Source closure changed')
    for e in plan['bindings']:
        path=(ROOT/e['path']).resolve(); need(path.is_relative_to(ROOT) and path.is_file() and not path.is_symlink() and sha(path)==e['sha256'],'Bound source/model/input changed')
    need(read(root/'runtime.json')==frozen.runtime(),'Frozen numerical runtime changed')
    return plan,read(root/'candidates.json'),read(root/'tools.json')


def git_freeze(root,commit,plan):
    need(re.fullmatch('[0-9a-f]{40}',commit or ''),'Exact reviewed Git commit required')
    paths=[ROOT/p for p in plan['source_paths']]+[root/n for n in ('plan.json','candidates.json','novelty.json','tools.json','runtime.json')]
    for path in paths:
        body=subprocess.check_output(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(body).hexdigest()==sha(path),'Git source/input freeze differs')


class Guard(hardware.AttemptGuard):
    # Raw files remain loose; no ZIP reservation or repeated closed-tree scan.
    def enforce_totals(self,current,maximum,archive_size=0):
        self.limits(); need(current<=POLICY['maximum_attempt_bytes'],'Whole8GiB stress attempt cap')


def owned(command,folder,owner,guard):
    folder.mkdir(parents=True,exist_ok=True); log=folder/'worker.log'; result=folder/'result.json'
    need(not log.exists() and not result.exists(),'Single fresh worker required')
    process=None; error=None; errors=[]; remaining=[]; began=time.monotonic(); start=now()
    try:
        with log.open('x') as stream:
            process=owner.launch(command,stream)
            while process.poll() is None:
                guard(); need(time.monotonic()-began<=360,'Worker360s deadline'); time.sleep(.25)
            guard(); need(time.monotonic()-began<=360 and process.returncode==0,'Worker failed/deadline')
    except BaseException as caught:error=caught
    finally:
        if process is not None:
            try:errors,remaining=frozen.clean([('v15-owned-worker',process)])
            except BaseException as caught:
                errors=[{'operation':'cleanup','error':repr(caught)}]; remaining=[{'pid':process.pid,'scope':'cleanup-unconfirmed'}]
            if not errors and not remaining:owner.remove(process)
        write(folder/'worker.json',{'command':command,'started_at_utc':start,'completed_at_utc':now(),
            'elapsed_seconds':time.monotonic()-began,'timeout_seconds':360,'returncode':process.returncode if process else None,
            'primary_error':repr(error) if error else None,'cleanup_errors':errors,'remaining_owned_children':remaining,
            'log_sha256':sha(log) if log.exists() else None,'complete':error is None and not errors and not remaining})
    if error is not None:raise error
    need(not errors and not remaining,'Owned cleanup failed'); return read(result)


def feature_worker(root,formula):
    plan,rows,tools=validate(root); row=next((r for r in rows if r['formula']==formula),None); need(row is not None,'Original outside fixed32')
    folder=root/'raw/features'/row['candidate_id'].split(':')[1]
    cache=folder/'cache'; need(not cache.exists(),'No feature retry/cache reuse')
    x,records=v6.FeatureExtractor(cache,frozen_tool=plan['frozen_tool']).matrix([{'formula':formula}],workers=1)
    need(x.shape==(1,336) and len(records)==1,'Complete original336 required')
    write(folder/'result.json',{**records[0],**row})


def prediction_worker(root):
    import model_v15_scoped as router
    _,rows,_=validate(root); data=read(root/'attempt/features.json')
    need(data['columns']==list(v6.columns()) and [r['formula'] for r in data['records']]==[r['formula'] for r in rows],'Full ordered336 matrix required')
    x=np.asarray([r['values'] for r in data['records']],dtype=float)
    need(x.shape==(32,336) and np.isfinite(x).all() and np.all(x>=0),'Finite32x336 required')
    models,routes=router.predict_models(rows,x)
    write(root/'raw/inference/result.json',{'models':models,'routes':routes})


def validate_points(points,rows):
    need(set(points['models'])=={'V6','V9','V15'},'Exact frozen comparison required')
    for values in points['models'].values():
        need(len(values)==32,'Full32 point set required')
        for r,p in zip(rows,values):
            need(r['candidate_id']==p['candidate_id'] and r['formula']==p['formula'],'Full ordered points required')
            need(type(p['predicted_lut4']) in (int,float) and math.isfinite(p['predicted_lut4']) and p['predicted_lut4']>=0 and p['upper_lut4'] is None and p['calibration_status']=='uncalibrated','Finite uncalibrated points required')
    need(len(points['routes'])==32,'Every original route required')
    for i,r in enumerate(points['routes']):
        need(r['source_model'] in ('V6','V9') and points['models']['V15'][i]==points['models'][r['source_model']][i],'Exact selected model point must be retained')


def validate_proof(proof,folder,rows):
    formulas=[r['formula'] for r in rows]
    wanted={'verified':True,'formula_count':32,'vectors_per_formula':2148,'total_comparisons':68736,'random_seed':SEED}
    need(all(type(proof.get(k)) is type(v) and proof[k]==v for k,v in wanted.items()),'Full32 original verification required')
    need(proof['v4_validation_override_sha256']==sha(ROOT/'isaforge/v4_validation.py'),'Frozen verifier changed')
    need((folder/'verification.v').read_text()==hardware.verification_source(formulas) and sha(folder/'verification.v')==proof['rtl_sha256'],'Exact original verification RTL required')
    pairs=list(hardware.itertools.product(hardware.BOUNDARIES,repeat=2)); rng=hardware.random.Random(SEED)
    pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048))
    with (folder/'vectors.txt').open() as stream:
        for a,b in pairs:
            expected=' '.join(f'{v:08x}' for v in (a,b,*[hardware.evaluate_formula(f,a,b) for f in formulas]))+'\n'
            need(stream.readline()==expected,'Full original vector/oracle bytes differ')
        need(stream.read(1)=='','Extra verification vector')
    need(sha(folder/'vectors.txt')==proof['vectors_sha256'] and type(proof['signed_overflow_workaround_applied']) is bool,'Verification vector evidence differs')


def metrics(rows,points,labels):
    need(len(rows)==len(labels)==32 and [r['candidate_id'] for r in rows]==[r['candidate_id'] for r in labels],'Full original labels/order required')
    result={}; y=np.asarray([r['lut4'] for r in labels],dtype=float)
    for name,records in points['models'].items():
        p=np.asarray([r['predicted_lut4'] for r in records]); error=p-y; absolute=np.abs(error)
        by={n:float(np.mean(absolute[[r['template']==n for r in rows]])) for n,_,_ in TEMPLATES}
        result[name]={'macro_template_mae':sum(by.values())/4,'template_mae':by,'pooled_mae':float(np.mean(absolute)),
            'bias':float(np.mean(error)),'rmsle':float(np.sqrt(np.mean((np.log1p(p)-np.log1p(y))**2))),
            'absolute_error_quantiles':{str(q):float(np.quantile(absolute,q/100)) for q in (90,95,99)},
            'worst_underprediction':{'lut4':float(max(0,np.max(y-p))),'candidate_id':rows[int(np.argmax(y-p))]['candidate_id']},
            'caps':{str(cap):{'false_accept':int(np.sum((p<=cap)&(y>cap))),'false_reject':int(np.sum((p>cap)&(y<=cap))),
                'predicted_accept':int(np.sum(p<=cap)),'actual_accept':int(np.sum(y<=cap)),'total':32} for cap in (32,64,128)}}
    return {'schema':'isaforge-v15-synthetic-stress-metrics-v1','models':result,
        'delta_v15_minus_v6':result['V15']['macro_template_mae']-result['V6']['macro_template_mae'],
        'delta_v15_minus_v9':result['V15']['macro_template_mae']-result['V9']['macro_template_mae'],
        'scope':'Prospective covered-domain synthetic32 stress, four templates. All32inside gate,V15=V9 by construction; no application-transfer/router-generalization claim.'}


def run(root,commit):
    root=Path(root).resolve(); plan,rows,tools=validate(root); git_freeze(root,commit,plan)
    need(not(root/'attempt').exists() and not(root/'raw').exists() and not(root/'claim.json').exists(),'One fresh32 attempt; no retries')
    need(shutil.disk_usage(ROOT).free>=POLICY['initial_free_bytes'],'Native stress start needs16GiB free')
    write(root/'claim.json',{'started_at_utc':now(),'freeze_commit':commit,'plan_sha256':sha(root/'plan.json'),'fits':0,'new_labels':0})
    output=root/'attempt'; scratch=root/'raw'; output.mkdir(); scratch.mkdir(); began=time.monotonic()
    guard=Guard(scratch,output,began=began,maximum_seconds=900); owner=hardware.HardwareWorkers(tools); failures=[]; measured={}; proofs=[]; points=None
    hot={ROOT/p:sha(ROOT/p) for p in plan.get('source_paths',[])}
    hot.update({root/n:sha(root/n) for n in ('plan.json','candidates.json','novelty.json','tools.json','runtime.json','claim.json') if (root/n).is_file()})
    def checked_owned(command,folder):
        hardware.provenance(hot,guard); result=owned(command,folder,owner,guard); hardware.provenance(hot,guard); return result
    def feature(row):
        folder=scratch/'features'/row['candidate_id'].split(':')[1]; guard.begin(folder)
        try:return checked_owned([sys.executable,str(Path(__file__).resolve()),'feature-worker','--root',str(root),'--formula',row['formula']],folder)
        finally:guard.end(folder)
    def parallel(function,items,collected=None):
        pool=ThreadPoolExecutor(max_workers=2); iterator=iter(items); pending={}
        collected={} if collected is None else collected
        try:
            while True:
                guard()
                while len(pending)<2:
                    item=next(iterator,None)
                    if item is None:break
                    pending[pool.submit(function,item)]=item
                if not pending:break
                done,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
                for future in done:
                    item=pending.pop(future); collected[item['candidate_id']]=future.result()
            return collected
        except BaseException: hardware.cancel(owner,failures); raise
        finally:pool.shutdown(wait=True,cancel_futures=True)
    try:
        extracted=parallel(feature,rows); data={'columns':list(v6.columns()),'records':[extracted[r['candidate_id']] for r in rows]}
        write(output/'features.json',data); guard.inventory()
        folder=scratch/'inference'; guard.begin(folder)
        try:points=checked_owned([sys.executable,str(Path(__file__).resolve()),'prediction-worker','--root',str(root)],folder)
        finally:guard.end(folder)
        validate_points(points,rows); write(output/'predictions.json',points)
        write(root/'point-freeze.json',{'frozen_at_utc':now(),'plan_sha256':sha(root/'plan.json'),'features_sha256':sha(output/'features.json'),
            'predictions_sha256':sha(output/'predictions.json'),'candidate_count':32,'prediction_count':96,'fits':0,'labels_read':0,'freeze_commit':commit})
        hot.update({path:sha(path) for path in (root/'point-freeze.json',output/'features.json',output/'predictions.json')})
        guard.inventory(); folder=scratch/'verification'; guard.begin(folder)
        try:
            proof=hardware.run_worker({'kind':'verify','formulas':[r['formula'] for r in rows],'folder':str(folder),'seed':SEED},folder,owner,hot,guard)
            validate_proof(proof,folder,rows)
            proofs.append(proof)
        finally:guard.end(folder)
        write(output/'verification.json',proofs); guard.inventory()
        def measure(row):
            folder=scratch/'circuits'/row['candidate_id'].split(':')[1]; guard.begin(folder)
            try:
                metric=hardware.run_worker({'kind':'map','formula':row['formula'],'folder':str(folder),'executable':tools['executables']['yosys']['path'],'version':tools['executables']['yosys']['version']},folder,owner,hot,guard)
                return hardware.validate_metric(metric,folder,row['formula'],tools)
            finally:guard.end(folder)
        measured=parallel(measure,rows,measured)
        labels=[{'candidate_id':r['candidate_id'],'formula':r['formula'],'template':r['template'],'lut4':measured[r['candidate_id']]['ice40_lut4_count']} for r in rows]
        write(output/'labels.json',labels); write(output/'measurements.json',[measured[r['candidate_id']] for r in rows])
        write(output/'metrics.json',metrics(rows,points,labels)); validate(root); hardware.native.validate_tools(tools); guard.inventory()
        records=[]
        for path in sorted(scratch.rglob('*')):
            if path.is_file(): records.append({'path':path.relative_to(root).as_posix(),'sha256':hardware.sha(path,guard),'bytes':path.stat().st_size})
        need(not owner.processes,'Remaining owned children prevent completion')
        write(output/'raw-evidence.json',{'files':records,'raw_files_retained':True,'compiler_objects_retained':True,'point_freeze_sha256':sha(root/'point-freeze.json')}); guard.inventory(); guard()
    except BaseException as error:
        failures.append({'error':repr(error)}); hardware.cancel(owner,failures)
        if not isinstance(error,Exception):
            write(output/'completion.json',{'complete':False,'failures':failures,'completed_at_utc':now(),'fits':0}); raise
    done={'schema':'isaforge-v15-synthetic-stress-completion-v1','complete':not failures,'failures':failures,'candidate_count':32,
        'completed_mapping_count':len(measured),'fits':0,'completed_at_utc':now(),'elapsed_seconds':time.monotonic()-began,
        'point_freeze_sha256':sha(root/'point-freeze.json') if (root/'point-freeze.json').exists() else None,
        'scope':plan['scope']}
    write(output/'completion.json',done); need(done['complete'],'Incomplete stress32 retained; full-panel primary unavailable'); return done


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','validate','run','feature-worker','prediction-worker'))
    parser.add_argument('--root',type=Path,required=True); parser.add_argument('--freeze-commit'); parser.add_argument('--formula'); a=parser.parse_args()
    if a.action=='prepare':result=prepare(a.root)
    elif a.action=='validate':result={'status':'valid','candidate_count':len(validate(a.root)[1]),'native_jobs':0}
    elif a.action=='run':result=run(a.root,a.freeze_commit)
    elif a.action=='feature-worker':result=feature_worker(a.root,a.formula)
    else:result=prediction_worker(a.root)
    print(json.dumps(result,indent=2,allow_nan=False))
