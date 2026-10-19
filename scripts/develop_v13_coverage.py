#!/usr/bin/env python3
"""Separately released V13 feature extraction, joint input freeze and30 matchedfits.

No deployment fit, target transform, residual adapter or evaluation-label reads.
The feature action uses the frozen V9/V6 extractor; all other actions are saved-
input arithmetic except the explicitly released30-fit action. No action retries.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
import develop_v12_target_transform as v12
import prepare_v13_coverage as inputs
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
from isaforge.structural_features_v4 import normalize_formula as v4_normalize
from isaforge.graph_features_v5 import _normalized_root

need,now,utc,sha,read,write,record,check_hashes=(getattr(v12,k) for k in ('need','now','utc','sha','read','write','record','check_hashes'))
SEEDS=v12.SEEDS
VIEWS=('control','augmented')
STRATA=v12.STRATA
PARAMETERS=dict(v12.PARAMETERS)
OLD_COUNT=1713
NEW_COUNT=48
COUNT=OLD_COUNT+NEW_COUNT
FEATURE_POLICY={'candidate_extractions':48,'workers':2,'owned_worker_timeout_seconds':360,'retries':0,
    'minimum_free_bytes':4*1024**3,'maximum_workspace_bytes':2*1024**3,'solver_queries':0,'estimator_fits':0,
    'pipeline':'Frozen V6 original336 extraction (SOG+original/normalized preABC generic graphs+pure V5+original mapping), select217 unchanged',
    'native_upper_bound':'At most3 cold preABC graph/SOG channels per candidate; no synth_ice40/ABC/labels in extraction'}


def equal(a,b):return inputs.identical(a,b)
def schedule():return [{'fit_index':i+1,'seed':s,'view':v,'fold':f} for i,(s,v,f) in enumerate((s,v,f) for s in SEEDS for v in VIEWS for f in range(5))]
def source_paths():
    names=('develop_v13_coverage.py','develop_v12_target_transform.py','prepare_v13_coverage.py','measure_v13_coverage.py','measure_v10_csd_hardware.py','audit_v13_measurements.py','measure_v13b_coverage.py')
    return [*(ROOT/'scripts'/n for n in names),ROOT/'tests/test_develop_v13_coverage.py',ROOT/'tests/test_measure_v13_coverage.py',
        ROOT/'tests/test_prepare_v13_coverage.py',ROOT/'tests/test_audit_v13_measurements.py',ROOT/'tests/test_measure_v13b_coverage.py',ROOT/'docs/v13-coverage-protocol.md',*sorted((ROOT/'isaforge').glob('*.py'))]
def git_freeze(bindings,commit):
    need(type(commit) is str and re.fullmatch('[0-9a-f]{40}',commit),'Exact Git freeze required')
    for p,h in bindings.items():
        body=subprocess.check_output(['git','show',commit+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)
        need(hashlib.sha256(body).hexdigest()==h,'Git freeze differs from prepared bytes')
def bound_files(root,manifest):
    result={}
    for e in manifest['files']:
        p=(root/e['path']).resolve();need(not Path(e['path']).is_absolute() and p.is_relative_to(ROOT) and p not in result,'Unique repository binding required')
        result[p]=e['sha256']
    check_hashes(result);return result


def old_inputs():
    """Read ONLY the already frozen V12 fitting whitelist/matrix/closure."""
    root=ROOT/inputs.V12;prep=read(root/'preparation.json')
    need(sha(root/'preparation.json')==inputs.V12_SHA,'Exact consumed V12 inputs required')
    bindings={(root/e['path']).resolve():e['sha256'] for e in prep['files']};paths=[root/'preparation.json']
    for n in ('fitting.json','matrix.npy','groups.json','split.json'):
        p=root/n;need(bindings.get(p)==sha(p),'V12 fitting byte identity differs');paths.append(p)
    need(bindings.get(ROOT/'scripts/develop_v12_target_transform.py')==sha(ROOT/'scripts/develop_v12_target_transform.py'),'Frozen V12 helper source changed')
    old_recipe=ROOT/inputs.V9/'recipe.json';need(bindings.get(old_recipe)==sha(old_recipe),'Frozen old feature-tool recipe differs');paths.append(old_recipe)
    data=read(root/'fitting.json');data['frozen_tool']=read(old_recipe)['frozen_tool'];matrix=np.load(root/'matrix.npy',allow_pickle=False)
    need(matrix.shape==(OLD_COUNT,217) and matrix.dtype==np.dtype('<f4') and np.isfinite(matrix).all() and np.all(matrix>=0),'Frozen1713x217 input matrix required')
    need(len(data['rows'])==len(data['original_zero'])==len(data['aliases'])==OLD_COUNT and all(type(z) is bool for z in data['original_zero']),'Complete old whitelist required')
    need(len({r['formula'] for r in data['rows']})==OLD_COUNT and all(type(r['lut4_count']) is int and r['lut4_count']>=0 for r in data['rows']),'Unique nonnegative original targets required')
    return data,matrix,paths



def measurement_collector(root):
    """Explicit plan schema selects a reviewed source, never an outcome fallback."""
    schema=read(Path(root)/'measurement-plan.json')['schema']
    if schema=='isaforge-v13-coverage-measurement-plan-v1':
        import measure_v13_coverage as collector
        return collector,'v13'
    if schema=='isaforge-v13b-coverage-measurement-plan-v1':
        import measure_v13b_coverage as collector
        return collector,'v13b'
    raise ValueError('Unrecognized original/recovery measurement plan')

def measurement_inputs(root):
    """Authenticate the exact successful48 original-label contract and raw ZIP."""
    root=Path(root).resolve();collector,revision=measurement_collector(root)
    candidates,plan,tools,review,bindings=collector.validate_approval(root,root/'measurement-approval.json')
    stage=root/'measurements/attempt-0000';done=read(root/'measurements/completion.json')
    need(equal(done,read(stage/'completion.json')),'Root/stage measurement completion differs')
    expected={'schema':f'isaforge-{revision}-coverage-measurements-v1','attempt':'attempt-0000','complete':True,'failures':[],
        'candidate_count':48,'new_physical_measurements':48,'verified_comparisons':103104,'verification_seed':2026101529,
        'vectors_per_formula':2148,'workers':2,'verification_batch_sizes':[48],'original_rtl_only':True,'legacy_measurements_reused':False,'new_estimator_fits':0}
    need(all(k in done and equal(done[k],v) for k,v in expected.items()),'Complete exact48 original measurements required')
    for key,name in [('preparation','preparation'),('recipe','recipe'),('candidates','candidates'),('measurement_plan','measurement-plan'),('tools','measurement-tools'),('approval','measurement-approval'),('release','label-release')]:
        p=root/(name+'.json');need(done[key+'_sha256']==sha(p),'Measurement lineage differs: '+name);bindings[p]=sha(p)
    need(done['collector_sha256']==sha(Path(collector.__file__)),'Frozen measurement collector identity differs')
    release=read(root/'label-release.json')
    need(release['schema']==f'isaforge-{revision}-coverage-label-release-v1' and release['freeze_commit']==done['freeze_commit']==review['freeze_commit']
        and release['policy']==collector.POLICY and utc(release['released_at_utc'])>=utc(review['reviewed_at_utc']),'Original/recovery release chronology or policy differs')
    for n,k in [('labels.json','labels_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:
        need(done[k]==sha(stage/n),'Completed target/proof identity differs');bindings[stage/n]=sha(stage/n)
    collector.verify_archive(root)
    for p in (root/'measurements/completion.json',stage/'completion.json',stage/'raw-evidence.json',stage/'raw-evidence.zip'):bindings[p]=sha(p)
    labels=read(stage/'labels.json');target={r['formula']:r for r in labels};need(len(labels)==len(target)==48 and set(target)=={r['formula'] for r in candidates},'Exact48 unique target join required')
    for c in candidates:
        r=target[c['formula']];need(all(equal(r[k],v) for k,v in c.items()) and type(r['lut4_count']) is int and r['lut4_count']>=0
            and r['correctness_verified'] is True and r['measurement_source']=='rtl_synthesis','Original-label identity/type differs')
    check_hashes(bindings)
    return candidates,{f:r['lut4_count'] for f,r in target.items()},tools,bindings


def prepare_features(root):
    root=Path(root).resolve();need(not (root/'feature-plan.json').exists() and not (root/'features').exists(),'Fresh single feature plan required')
    candidates,_,tools,bindings=measurement_inputs(root);base,_,old_paths=old_inputs()
    need(base['frozen_tool']=={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']},'New features must use original frozen training Yosys')
    bindings.update({p:sha(p) for p in [*source_paths(),*old_paths]});environment=v12.runtime()
    write(root/'feature-runtime.json',environment)
    plan={'schema':'isaforge-v13-feature-plan-v1','status':'prepared-no-feature-jobs','created_at_utc':now(),'policy':FEATURE_POLICY,
        'preparation_sha256':sha(root/'preparation.json'),'measurement_completion_sha256':sha(root/'measurements/completion.json'),
        'tools_sha256':sha(root/'measurement-tools.json'),'feature_runtime':record(root/'feature-runtime.json',root),
        'frozen_tool':{'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']},
        'columns':list(v6.columns()),'selected_columns':list(v6.mapping_columns()),'selected_indices':v6.mapping_indices().tolist(),
        'feature_source_sha256':v6.source_hashes(),'files':[record(p,root) for p in sorted(bindings)],
        'source_paths':[os.path.relpath(p,root) for p in source_paths()],'original_training_input_paths':[os.path.relpath(p,root) for p in old_paths],
        'aliases':'Old1713 saved accepted forms retained; new48 original plus frozen pure V4 normal form only, no V7/SMT proof claim.'}
    check_hashes(bindings);write(root/'feature-plan.json',plan);return plan


def validate_feature_plan(root):
    root=Path(root).resolve();plan=read(root/'feature-plan.json');need(plan['schema']=='isaforge-v13-feature-plan-v1' and plan['status']=='prepared-no-feature-jobs'
        and equal(plan['policy'],FEATURE_POLICY),'Exact bounded feature plan required')
    candidates,targets,tools,measurement_bindings=measurement_inputs(root);base,_,old_paths=old_inputs()
    need(base['frozen_tool']==plan['frozen_tool'],'Original/new feature tool mismatch')
    bindings=bound_files(root,plan);expected=set(measurement_bindings)|set(source_paths())|set(old_paths)
    need(set(bindings)==expected and plan['source_paths']==[os.path.relpath(p,root) for p in source_paths()]
        and plan['original_training_input_paths']==[os.path.relpath(p,root) for p in old_paths],'Complete exact feature input/source closure required')
    need(plan['feature_runtime']==record(root/'feature-runtime.json',root) and equal(read(root/'feature-runtime.json'),v12.runtime()),'Feature runtime changed')
    need(plan['preparation_sha256']==sha(root/'preparation.json') and plan['measurement_completion_sha256']==sha(root/'measurements/completion.json')
        and plan['tools_sha256']==sha(root/'measurement-tools.json') and plan['columns']==list(v6.columns())
        and plan['selected_columns']==list(v6.mapping_columns()) and plan['selected_indices']==v6.mapping_indices().tolist()
        and plan['feature_source_sha256']==v6.source_hashes(),'Feature schema/source/input differs')
    need(plan['frozen_tool']=={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']},'Feature Yosys identity differs')
    bindings.update({root/'feature-plan.json':sha(root/'feature-plan.json'),root/'feature-runtime.json':sha(root/'feature-runtime.json')})
    return plan,candidates,targets,tools,bindings


def review_binding(root,review,key,completion_sha):
    e=review[key];p=(root/e['path']).resolve();need(p.is_relative_to(root) and sha(p)==e['sha256'],'Exact independent review binding required')
    value=read(p);need(value['schema']=='isaforge-v13-independent-measurement-audit-v1' and value['status']=='pass' and value['complete'] is True and value['completion_sha256']==completion_sha,'Independent completed-stage review required')
    need(value['labels_sha256']==sha(root/'measurements/attempt-0000/labels.json') and value['raw_archive_sha256']==sha(root/'measurements/attempt-0000/raw-evidence.zip'),'Independent review target/raw binding differs')
    return p


def feature_worker(payload):
    """Invoked only inside the owned child; frozen V9/V6 feature function."""
    root=Path(payload['root']).resolve();plan=read(root/'feature-plan.json');claim=read(root/'feature-claim.json')
    need(claim['runner_sha256']==sha(__file__) and sha(root/'feature-claim.json')==payload['claim_sha256'] and claim['feature_plan_sha256']==sha(root/'feature-plan.json'),'Owned worker claim/source differs')
    candidates=read(root/'candidates.json');candidate=next((c for c in candidates if c['formula']==payload['formula']),None);need(candidate is not None,'Worker original outside fixed grid')
    key=candidate['candidate_id'].split(':')[1];stage=root/'features/attempt-0000'
    need(Path(payload['cache']).resolve()==stage/'cache'/key and Path(payload['result']).resolve()==stage/'workers'/key/'result.json' and payload['frozen_tool']==plan['frozen_tool'],'Worker path/tool differs')
    need(not Path(payload['cache']).exists() and not Path(payload['result']).exists(),'Fresh per-original feature cache/result required; no retry')
    x,records=v6.FeatureExtractor(payload['cache'],frozen_tool=payload['frozen_tool']).matrix([{'formula':payload['formula']}],workers=1)
    need(x.shape==(1,336) and len(records)==1 and records[0]['formula']==payload['formula'],'Complete single original extraction required')
    write(payload['result'],records[0])


def run_feature_worker(payload,log,owner):
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('xb') as stream:
        process=owner.launch([sys.executable,str(Path(__file__).resolve()),'feature-worker','--payload',json.dumps(payload)],stream)
        try:need(process.wait(timeout=360)==0,'Feature worker failed; raw log retained')
        finally:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();owner.finished(process.pid)
    return read(payload['result'])


def archive_features(stage):
    rows=[];path=stage/'raw-evidence.zip'
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(stage.rglob('*')):
            need(not p.is_symlink(),'No feature evidence symlinks')
            if p.is_file() and p!=path and p.name!='raw-evidence.json':
                n=p.relative_to(stage).as_posix();body=p.read_bytes();z.writestr(n,body);rows.append({'path':n,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
    write(stage/'raw-evidence.json',{'schema':'isaforge-v13-feature-archive-v1','archive':path.name,'archive_sha256':sha(path),'files':rows})


def feature_guard(stage):
    need(shutil.disk_usage(ROOT).free>=FEATURE_POLICY['minimum_free_bytes'],'Feature stage needs4GiB free')
    need(sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())<=FEATURE_POLICY['maximum_workspace_bytes'],'Feature evidence exceeds2GiB; retain and stop')


def extract_features(root,approval):
    from measure_v10_csd_hardware import HardwareWorkers
    root=Path(root).resolve();collector,revision=measurement_collector(root)
    approval=Path(approval).resolve();plan,candidates,_,tools,bindings=validate_feature_plan(root)
    need(approval==root/'feature-approval.json' and not (root/'feature-claim.json').exists() and not (root/'features').exists(),'Fresh single approved feature stage required')
    review=read(approval);expected={'status':'approved-v13-forty-eight-feature-extractions','feature_plan_sha256':sha(root/'feature-plan.json'),
        'measurement_completion_sha256':sha(root/'measurements/completion.json'),'runner_sha256':sha(__file__),'maximum_extractions':48}
    need(all(k in review and equal(review[k],v) for k,v in expected.items()) and utc(review['reviewed_at_utc'])>=utc(plan['created_at_utc']),'Feature release must follow/bind exact plan')
    git_freeze(bindings,review['freeze_commit']);audit=review_binding(root,review,'independent_measurement_audit',sha(root/'measurements/completion.json'))
    bindings.update({approval:sha(approval),audit:sha(audit)})
    bindings.update({Path(e['path']):e['sha256'] for e in read(root/'feature-runtime.json')['files']})
    collector.validate_tools(tools);check_hashes(bindings)
    stage=root/'features/attempt-0000';stage.mkdir(parents=True);write(root/'feature-claim.json',{'claimed_at_utc':now(),'maximum_extractions':48,'approval_sha256':sha(approval),'feature_plan_sha256':sha(root/'feature-plan.json'),'runner_sha256':sha(__file__)})
    bindings[root/'feature-claim.json']=sha(root/'feature-claim.json');owner=HardwareWorkers(tools);owner.environment=dict(tools['environment']);records={};failures=[];interruption=None
    try:
        def one(c):
            check_hashes(bindings);feature_guard(stage);key=c['candidate_id'].split(':')[1]
            payload={'root':str(root),'claim_sha256':sha(root/'feature-claim.json'),'formula':c['formula'],'cache':str(stage/'cache'/key),'frozen_tool':plan['frozen_tool'],'result':str(stage/'workers'/key/'result.json')}
            return c['formula'],run_feature_worker(payload,stage/'workers'/key/'worker.log',owner)
        pool=ThreadPoolExecutor(max_workers=2)
        try:
            futures={pool.submit(one,c):c for c in candidates}
            for future in as_completed(futures):
                try:f,r=future.result();records[f]=r
                except BaseException as e:
                    failures.append({'formula':futures[future]['formula'],'error':repr(e)})
                    if not isinstance(e,Exception):raise
        except BaseException:
            try:owner.cancel()
            except BaseException as cleanup:failures.append({'stage':'cleanup','error':repr(cleanup)})
            raise
        finally:pool.shutdown(wait=True,cancel_futures=True)
        collector.validate_tools(tools);check_hashes(bindings);feature_guard(stage)
    except BaseException as e:
        try:owner.cancel()
        except BaseException as cleanup:failures.append({'stage':'cleanup','error':repr(cleanup)})
        failures.append({'stage':'provenance-or-resource','error':repr(e)})
        if not isinstance(e,Exception):interruption=e
    rows=[{'candidate_id':c['candidate_id'],'cache_subdir':c['candidate_id'].split(':')[1],**records[c['formula']]} for c in candidates if c['formula'] in records]
    write(stage/'features.json',{'columns':list(v6.columns()),'records':rows})
    done={'schema':'isaforge-v13-feature-completion-v1','complete':not failures and len(rows)==48,'failures':failures,'candidate_count':48,
        'completed_extractions':len(rows),'feature_plan_sha256':sha(root/'feature-plan.json'),'approval_sha256':sha(approval),'claim_sha256':sha(root/'feature-claim.json'),
        'measurement_completion_sha256':sha(root/'measurements/completion.json'),'features_sha256':sha(stage/'features.json'),'runner_sha256':sha(__file__),
        'native_graph_invocations':len(list((stage/'cache').rglob('*.ys'))) if not failures and len(rows)==48 else None,
        'native_graph_scripts_retained':len(list((stage/'cache').rglob('*.ys'))),
        'native_graph_invocations_scope':'Complete graph/SOG pipeline count only; excludes Yosys identity/version probes. Partial retained scripts do not prove completed invocations.','collection_root':str(root),'completed_at_utc':now(),'fits_completed':0,'new_solver_queries':0,'new_physical_labels':0}
    write(stage/'completion.json',done)
    try:
        archive_features(stage);feature_guard(stage);check_hashes(bindings);collector.validate_tools(tools)
    except BaseException as e:
        done={**done,'complete':False,'failures':[*failures,{'stage':'archive-final-provenance','error':repr(e)}]}
        if not isinstance(e,Exception):interruption=e
    write(root/'features/completion.json',done)
    if interruption is not None:raise interruption
    need(done['complete'],'Incomplete feature attempt retained; no fit preparation')
    return done



def replay_feature_record(z,record,tool,collection_root):
    """Recompute336 from retained generic/SOG graphs, never invoke extractor."""
    from isaforge import graph_features_v5 as graph
    from isaforge import masterrtl_baseline as sog
    from isaforge import structural_features_v5 as semantic
    from isaforge.mapping_features_v6 import feature_vector
    from isaforge.rtl import generate_rtl
    from isaforge.synthesis import _yosys_quote
    root='cache/'+record['cache_subdir'];channels=[];graphs=[];native=set()
    normalized=_normalized_root(semantic.normalize_formula(record['formula']))
    need(record['normalized_formula']==normalized,'Frozen pure V5 normalized graph identity differs')
    def payload(prefix,folder,expected_formula):
        directory=root+'/'+folder+'/'+record[prefix+'_cache_key'];m= json.loads(z.read(directory+'/features.json'))
        need(m['cache_key']==record[prefix+'_cache_key'] and m['formula']==expected_formula,'Feature graph manifest identity differs')
        for name,digest in m['files_sha256'].items():need(hashlib.sha256(z.read(directory+'/'+name)).hexdigest()==digest,'Feature graph raw bytes differ')
        need(z.read(directory+'/candidate.v').decode()==generate_rtl(expected_formula),'Feature RTL differs from exact original/normalized formula')
        return directory,m
    for prefix,formula in [('original',record['formula']),('normalized',normalized)]:
        directory,m=payload(prefix,'generic',formula);context=m['context']
        expected_context={'schema':graph.SCHEMA,'pipeline':graph.PIPELINE,'tool':tool,'runtime_source_sha256':graph.source_hashes(),
            'feature_columns':list(graph.CHANNEL_COLUMNS),'scope':'generic combinational synthesis; no ABC, target mapping or measured labels'}
        expected_key=hashlib.sha256(json.dumps({'formula':formula,'context':expected_context},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        need(equal(context,expected_context) and record[prefix+'_cache_key']==expected_key and m['feature_columns']==list(graph.CHANNEL_COLUMNS),'Frozen generic feature context/key differs')
        need(set(m['files_sha256'])=={'candidate.v','extract.ys','word.json','graph.json','extract.log'} and z.read(directory+'/extract.ys').decode()==graph.PIPELINE,'Generic preABC script differs')
        net=json.loads(z.read(directory+'/graph.json'));word=json.loads(z.read(directory+'/word.json'));values=graph.channel_features(net,word)
        need(equal(values.tolist(),m['feature_values']),'Generic feature arithmetic differs');channels.append(values);graphs.append(net);native.add(directory+'/extract.ys')
    directory,m=payload('sog','sog',record['formula']);context=m['context'];expected_context={
        'pipeline':sog.PIPELINE,'tool':{**tool,'executable':'yosys'},'runtime_source_sha256':sog._source_hashes(),'feature_columns':list(sog.FEATURE_COLUMNS),'weights':sog.WEIGHTS}
    expected_key=hashlib.sha256(json.dumps({'formula':record['formula'],**expected_context},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    need(equal(context,expected_context) and record['sog_cache_key']==expected_key and set(m['files_sha256'])=={'candidate.v','sog.ys','sog.json','sog.v','sog.log'},'Frozen SOG preABC context differs')
    absolute=Path(collection_root)/'features/attempt-0000'/directory
    expected_script=f'read_verilog {_yosys_quote(absolute/"candidate.v")}\n{sog.PIPELINE}\ncheck -assert\nwrite_json {_yosys_quote(absolute/"sog.json")}\nwrite_verilog {_yosys_quote(absolute/"sog.v")}\nstat\n'
    need(z.read(directory+'/sog.ys').decode()==expected_script,'SOG preABC script differs');native.add(directory+'/sog.ys')
    sog_values,counts=sog.netlist_features(json.loads(z.read(directory+'/sog.json')));need(equal(sog_values,m['feature_values']) and equal(counts,m['primitive_cell_counts']),'SOG feature arithmetic differs')
    sem=semantic.feature_dict(record['formula']);mapping=feature_vector(graphs[0])
    need(record['original_graph_sha256']==hashlib.sha256(z.read(root+'/generic/'+record['original_cache_key']+'/graph.json')).hexdigest()
        and record['mapping_source_sha256']==v6.source_hashes()['mapping_features_v6.py'],'Original mapping graph/source differs')
    result=np.concatenate((sog_values,channels[0],channels[1],abs(channels[0]-channels[1]),[sem[n] for n in semantic.FEATURE_NAMES],mapping))
    need(result.shape==(336,) and np.array_equal(result,np.asarray(record['values'],dtype=float)),'Full336 features do not replay retained graph arithmetic')
    return result,native

def feature_inputs(root):
    root=Path(root).resolve();plan,candidates,targets,tools,bindings=validate_feature_plan(root);stage=root/'features/attempt-0000'
    done=read(root/'features/completion.json');need(equal(done,read(stage/'completion.json')) and done['schema']=='isaforge-v13-feature-completion-v1'
        and done['complete'] is True and done['failures']==[] and type(done['completed_extractions']) is int and done['completed_extractions']==48,'Complete48 feature extraction required')
    need(all(type(done[k]) is int and done[k]==v for k,v in [('candidate_count',48),('fits_completed',0),('new_solver_queries',0),('new_physical_labels',0)]),'Feature stage count/type contract differs')
    for key,path in [('feature_plan_sha256',root/'feature-plan.json'),('approval_sha256',root/'feature-approval.json'),('claim_sha256',root/'feature-claim.json'),
        ('measurement_completion_sha256',root/'measurements/completion.json'),('features_sha256',stage/'features.json'),('runner_sha256',Path(__file__))]:need(done[key]==sha(path),'Feature completion binding differs')
    archive=read(stage/'raw-evidence.json');need(archive['schema']=='isaforge-v13-feature-archive-v1' and archive['archive_sha256']==sha(stage/'raw-evidence.zip'),'Feature archive differs')
    members={e['path']:e for e in archive['files']};need(len(members)==len(archive['files']),'Duplicate feature archive member')
    with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
        need(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(members),'Feature archive coverage differs')
        for n,e in members.items():
            p=PurePosixPath(n);need(not p.is_absolute() and '..' not in p.parts and '\\' not in n and str(p)==n,'Unsafe archive member')
            body=z.read(n);need(type(e['bytes']) is int and len(body)==e['bytes'] and hashlib.sha256(body).hexdigest()==e['sha256'],'Feature archive member differs')
        for name in ('features.json','completion.json'):need(z.read(name)==(stage/name).read_bytes(),'Feature archive/stage differs')
    data=read(stage/'features.json');need(data['columns']==list(v6.columns()) and len(data['records'])==48,'Full336 named feature records required')
    records={r['formula']:r for r in data['records']};need(len(records)==48 and set(records)=={c['formula'] for c in candidates},'Exact48 feature formula coverage required')
    values=[];native=set()
    for c in candidates:
        r=records[c['formula']];need(r['candidate_id']==c['candidate_id'] and r['cache_subdir']==c['candidate_id'].split(':')[1],'Feature input identity differs')
        with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
            replayed,channels=replay_feature_record(z,r,plan['frozen_tool'],done['collection_root']);values.append(replayed);native.update(channels)
        for prefix,folder in [('original','generic'),('normalized','generic'),('sog','sog')]:
            n='cache/'+r['cache_subdir']+'/'+folder+'/'+r[prefix+'_cache_key']+'/features.json'
            need(n in members and members[n]['sha256']==r[prefix+'_manifest_sha256'],'Native graph record binding differs')
    need(96<=len(native)<=144,'Fresh48 candidate preABC channel invocation count outside96..144')
    need(done['native_graph_invocations']==len(native),'Feature native channel count differs')
    full=v12.numeric(values,(48,336));selected=v12.selected_float32(full,v6.mapping_indices());zero=full[:,list(v6.columns()).index('original_gate_count')]==0
    paths=[root/'features/completion.json',stage/'completion.json',stage/'features.json',stage/'raw-evidence.json',stage/'raw-evidence.zip',root/'feature-approval.json',root/'feature-claim.json']
    bindings.update({p:sha(p) for p in paths});check_hashes(bindings)
    return candidates,targets,full,selected,zero,bindings


def recipe():
    return {'schema':'isaforge-v13-matched-coverage-recipe-v1','old_rows':1713,'new_rows':48,'rows':1761,'views':list(VIEWS),'parameters':PARAMETERS,
        'seeds':list(SEEDS),'folds':5,'maximum_fits':30,'target_transform':'none','decode':'max(0,forest mean), then saved original generic-zero override',
        'feature_columns':list(v6.mapping_columns()),'selected_indices':v6.mapping_indices().tolist(),'scope':'Consumed-development coverage augmentation; no independent transfer, calibration or CPU claim.',
        'grouping':'Shared V12 transitive recipe, retained original V5/V9 groups, all new V13 contexts, original/pureV4 aliases and exact217float32 collisions; no new V7/SMT.',
        'primary':'Mean3seeds augmented-minus-control nine-stratum macro OOF MAE on original1713 only',
        'secondary':'Same heldout48 coverage rows, per-family/stratum plus old1713 cap64FA/FR and tails; caps32/128 sensitivity',
        'final_refit':False,'sample_weights':False,'hyperparameter_search':False,'evaluation_target_reads':0,'new_solver_queries':0}


def load_inputs(root):
    base,matrix,old_paths=old_inputs();candidates,targets,full,new_matrix,new_zero,bindings=feature_inputs(root)
    rows=[{**r,'cohort':'original1713'} for r in base['rows']];aliases=[list(a) for a in base['aliases']]
    for c in candidates:
        rows.append({'formula':c['formula'],'source':'coverage_v13','cohort':'coverage48','candidate_id':c['candidate_id'],
            'family':c['family'],'context':c['context'],'stratum':c['stratum'],'lut4_count':targets[c['formula']]})
        aliases.append(sorted({c['formula'],parse_formula(_normalized_root(v4_normalize(c['formula']))).canonical()}))
    need(len(rows)==len({r['formula'] for r in rows})==COUNT,'Unique1761 originals required; overlaps stop, never duplicate training observations')
    for p in old_paths:bindings[p]=sha(p)
    return rows,np.vstack((matrix,new_matrix)),np.concatenate((base['original_zero'],new_zero)),aliases,bindings


def build_groups(rows,matrix,aliases):
    public=[]
    for r in rows:
        clean={k:r[k] for k in ('formula','source','stratum')}
        if r['source']=='original1665':clean['inherited_component']=r['inherited_component']
        else:clean['context']=('v13:' if r['source']=='coverage_v13' else 'v9:')+r['context']
        public.append(clean)
    result=v12.build_groups(public,matrix,aliases);result['schema']='isaforge-v13-joint-leakage-groups-v1';return result


def assign_folds(rows,groups):
    result=v12.assign_folds(rows,groups);result['schema']='isaforge-v13-joint-folds-v1'
    for d in result['folds']:
        d['control_training_indices']=[i for i in d['training_indices'] if rows[i]['cohort']=='original1713']
        d['control_training_strata']=dict(Counter(rows[i]['stratum'] for i in d['control_training_indices']))
        d['control_training_has_all9strata']=set(d['control_training_strata'])==set(STRATA)
    result['feasible']=result['feasible'] and all(d['control_training_has_all9strata'] for d in result['folds'])
    result['failure_reason']=None if result['feasible'] else 'Need5nonemptyassessmentfolds and all9strata in each control AND augmented training partition; preserve closure and stop.'
    return result


def prepare(root):
    root=Path(root).resolve();out=root/'fitting';need(root.is_relative_to(ROOT) and not out.exists(),'Fresh repository-owned fitting preparation required')
    sources=source_paths();rows,matrix,zero,aliases,bindings=load_inputs(root);bindings.update({p:sha(p) for p in sources})
    groups=build_groups(rows,matrix,aliases);split=assign_folds(rows,groups);out.mkdir()
    try:
        write(out/'recipe.json',recipe());write(out/'runtime.json',v12.runtime());write(out/'fitting.json',{'rows':rows,'original_zero':zero.tolist(),'aliases':aliases})
        with (out/'matrix.npy').open('xb') as stream:np.save(stream,matrix,allow_pickle=False)
        write(out/'groups.json',groups);write(out/'split.json',split);check_hashes(bindings)
        paths=[*bindings,*sorted(p for p in out.iterdir() if p.is_file())]
        manifest={'schema':'isaforge-v13-matched-coverage-preparation-v1','status':'prepared-inputs-only' if split['feasible'] else 'infeasible-grouping',
            'created_at_utc':now(),'rows':1761,'old_rows':1713,'new_rows':48,'selected_columns':217,'fits_completed':0,'maximum_fits':30,
            'grouping_feasible':split['feasible'],'files':[record(p,out) for p in paths],
            'source_paths':[os.path.relpath(p,out) for p in sources],'input_paths':[os.path.relpath(p,out) for p in bindings if p not in sources],
            'fit_schedule':schedule(),'evaluation_target_reads':0,'new_solver_queries':0,'new_feature_extractions':0}
        write(out/'preparation.json',manifest);need(split['feasible'],'Infeasible joint grouping retained; no fit release');validate(root);return manifest
    except BaseException as e:write(out/'preparation-failure.json',{'error':repr(e),'fits_completed':0,'at_utc':now()});raise


def validate(root):
    root=Path(root).resolve();out=root/'fitting';m=read(out/'preparation.json')
    need(root.is_relative_to(ROOT) and not (out/'preparation-failure.json').exists() and m['schema']=='isaforge-v13-matched-coverage-preparation-v1'
        and m['status']=='prepared-inputs-only' and m['grouping_feasible'] is True and type(m['fits_completed']) is int and m['fits_completed']==0
        and type(m['maximum_fits']) is int and m['maximum_fits']==30,'Complete feasible joint input freeze required')
    bindings=bound_files(out,m);data=read(out/'fitting.json');matrix=np.load(out/'matrix.npy',allow_pickle=False)
    need(equal(read(out/'recipe.json'),recipe()) and equal(read(out/'runtime.json'),v12.runtime()),'Fitting recipe/runtime changed')
    need(matrix.shape==(COUNT,217) and matrix.dtype==np.dtype('<f4') and np.isfinite(matrix).all() and np.all(matrix>=0),'Complete1761x217 frozen matrix required')
    rows,expected,zero,aliases,inputs_binding=load_inputs(root)
    sources=source_paths();produced={out/n for n in ('recipe.json','runtime.json','fitting.json','matrix.npy','groups.json','split.json')}
    need(set(bindings)==set(inputs_binding)|set(sources)|produced and m['source_paths']==[os.path.relpath(p,out) for p in sources]
        and set(m['input_paths'])=={os.path.relpath(p,out) for p in inputs_binding if p not in sources},'Exact joint fitting input/source closure required')
    need(equal(data,{'rows':rows,'original_zero':zero.tolist(),'aliases':aliases}) and np.array_equal(matrix,expected),'Frozen whitelist/matrix differs from completed features')
    groups=build_groups(rows,matrix,aliases);split=assign_folds(rows,groups)
    need(equal(read(out/'groups.json'),groups) and equal(read(out/'split.json'),split) and split['feasible'] and equal(m['fit_schedule'],schedule()),'Shared closure/fold/schedule replay differs')
    bindings[out/'preparation.json']=sha(out/'preparation.json');return m,data,matrix,groups,split,bindings


def cohort_scores(rows,y,points):
    result={}
    for name in ('original1713','coverage48'):
        mask=np.asarray([r['cohort']==name for r in rows]);need(mask.any(),'Both scoring cohorts required')
        result[name]=v12.metrics(y[mask],points[mask],np.asarray([r['stratum'] for r in rows])[mask])
    families=sorted({r['family'] for r in rows if r['cohort']=='coverage48'})
    result['coverage_by_family']={f:v12.metrics(y[[r.get('family')==f for r in rows]],points[[r.get('family')==f for r in rows]],
        np.asarray([r['stratum'] for r in rows])[[r.get('family')==f for r in rows]]) for f in families}
    return result


def paired_decisions(y,control,augmented):
    raw=v12.paired_decisions(y,control,augmented)
    return {cap:{k.replace('raw','control').replace('log','augmented'):v for k,v in counts.items()} for cap,counts in raw.items()}


def fit(root,approval):
    root=Path(root).resolve();out=root/'fitting';approval=Path(approval).resolve();manifest,data,matrix,groups,split,bindings=validate(root)
    need(approval==out/'fit-approval.json' and not (out/'fit-claim.json').exists() and not (out/'fit-attempt-0000').exists(),'Exact approval and fresh single fit attempt required')
    review=read(approval);expected={'status':'approved-v13-thirty-matched-coverage-fits','preparation_sha256':sha(out/'preparation.json'),'runner_sha256':sha(__file__),'maximum_fits':30}
    need(all(k in review and equal(review[k],v) for k,v in expected.items()) and utc(review['reviewed_at_utc'])>=utc(manifest['created_at_utc']),'Exact reviewed30-fit release required')
    git_freeze(bindings,review['freeze_commit']);entry=review['independent_input_audit'];audit=(out/entry['path']).resolve()
    need(audit.is_relative_to(root) and sha(audit)==entry['sha256'],'Bound independent joint input review required');a=read(audit)
    need(a['status']=='pass' and a['preparation_sha256']==sha(out/'preparation.json'),'Independent input review must cover exact joint freeze')
    bindings.update({approval:sha(approval),audit:sha(audit)});bindings.update({Path(e['path']):e['sha256'] for e in read(out/'runtime.json')['files']});check_hashes(bindings)
    stage=out/'fit-attempt-0000';stage.mkdir();write(out/'fit-claim.json',{'claimed_at_utc':now(),'maximum_fits':30,'preparation_sha256':sha(out/'preparation.json'),'approval_sha256':sha(approval)})
    bindings[out/'fit-claim.json']=sha(out/'fit-claim.json');rows=data['rows'];y=np.asarray([r['lut4_count'] for r in rows],dtype=float)
    ids=np.asarray(split['fold_ids']);old=np.asarray([r['cohort']=='original1713' for r in rows]);zero=np.asarray(data['original_zero'],dtype=bool)
    predictions={};scores={};receipts=[];attempts=0;error=None
    try:
        with threadpool_limits(limits=1):
            for seed in SEEDS:
                for view in VIEWS:
                    encoded=np.full(len(rows),np.nan);counts=np.zeros(len(rows),dtype=int)
                    for fold in range(5):
                        check_hashes(bindings);attempts+=1;training=(ids!=fold)&(old if view=='control' else np.ones(len(rows),dtype=bool));validation=ids==fold
                        start={'fit_index':attempts,'seed':seed,'view':view,'fold':fold,'parameters':{**PARAMETERS,'random_state':seed},
                            'training_indices':np.flatnonzero(training).tolist(),'validation_indices':np.flatnonzero(validation).tolist(),'started_at_utc':now()}
                        need(utc(start['started_at_utc'])>=utc(review['reviewed_at_utc']),'Fit starts before review');write(stage/'receipts'/f'{attempts:02d}-start.json',start);began=time.monotonic()
                        estimator=ExtraTreesRegressor(**PARAMETERS,random_state=seed);estimator.fit(matrix[training],y[training]);direct=estimator.predict(matrix[validation]);fingerprint=v6.estimator_fingerprint(estimator)
                        artifact=stage/'models'/f'{attempts:02d}-{view}-seed-{seed}-fold-{fold}.joblib';artifact.parent.mkdir(parents=True,exist_ok=True);need(not artifact.exists(),'Fresh model artifact required');joblib.dump(estimator,artifact,compress=3);restored=joblib.load(artifact)
                        need(restored.get_params(deep=True)==estimator.get_params(deep=True) and v6.estimator_fingerprint(restored)==fingerprint and np.array_equal(restored.predict(matrix[validation]),direct),'Exact save/load model and heldout-point roundtrip required')
                        encoded[validation]=direct;counts[validation]+=1
                        receipt={**start,'completed_at_utc':now(),'elapsed_seconds':time.monotonic()-began,'estimator_fingerprint':fingerprint,'artifact':record(artifact,stage),'artifact_bytes':artifact.stat().st_size,'save_load_points_exact':True}
                        write(stage/'receipts'/f'{attempts:02d}-completed.json',receipt);receipts.append(receipt)
                    need(np.all(counts==1),'Every1761 row needs exactly one shared-heldout prediction');before,points=v12.decode(encoded,'raw',zero)
                    records=[{**r,'fold':int(ids[i]),'original_zero':bool(zero[i]),'encoded_prediction':float(encoded[i]),'decoded_before_zero':float(before[i]),'predicted_lut4':float(points[i])} for i,r in enumerate(rows)]
                    p=stage/'predictions'/f'{view}-seed-{seed}.json';write(p,records);need(equal(read(p),records),'Exact saved-point roundtrip required before scoring')
                    predictions[view,seed]=points;scores[view,seed]=cohort_scores(rows,y,points);write(stage/'metrics'/f'{view}-seed-{seed}.json',scores[view,seed])
                    print('completed',view,seed,'fits',attempts,'/30',flush=True)
        need(attempts==len(receipts)==30,'Exactly30 completed fits required');check_hashes(bindings)
        differences=[scores['augmented',s]['original1713']['macro_stratum_mae_lut4']-scores['control',s]['original1713']['macro_stratum_mae_lut4'] for s in SEEDS]
        summary={'schema':'isaforge-v13-matched-coverage-comparison-v1','scope':recipe()['scope'],'fits_completed':30,
            'primary_augmented_minus_control_original1713_macro_mae_lut4':{'per_seed':dict(zip(map(str,SEEDS),differences)),'mean':float(np.mean(differences)),'sample_sd_algorithm_seeds':float(np.std(differences,ddof=1))},
            'scores':{v:{str(s):scores[v,s] for s in SEEDS} for v in VIEWS},
            'paired_cap_decisions':{str(s):{name:paired_decisions(y[mask],predictions['control',s][mask],predictions['augmented',s][mask]) for name,mask in [('original1713',old),('coverage48',~old)]} for s in SEEDS},
            'promotion':'No automatic promotion/final refit; original1713 cap64FA/FR and tails remain separate endpoints; new48 secondary only.'}
        write(stage/'summary.json',summary)
    except BaseException as e:error=e
    done={'schema':'isaforge-v13-matched-fit-completion-v1','complete':error is None,'fits_attempted':attempts,'fits_completed':len(receipts),'maximum_fits':30,
        'preparation_sha256':sha(out/'preparation.json'),'approval_sha256':sha(approval),'runner_sha256':sha(__file__),'error':repr(error) if error else None,
        'summary_sha256':sha(stage/'summary.json') if (stage/'summary.json').exists() else None,'completed_at_utc':now(),'evaluation_target_reads':0,'new_solver_queries':0,'new_feature_extractions':0,'new_physical_labels':0}
    write(stage/'completion.json',done)
    if error is not None:raise error
    return done


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare-features','extract-features','feature-worker','prepare','validate','fit'));p.add_argument('--root',type=Path);p.add_argument('--approval',type=Path);p.add_argument('--payload')
    a=p.parse_args()
    if a.action=='feature-worker':
        if a.payload is None:p.error('feature-worker requires payload')
        feature_worker(json.loads(a.payload));sys.exit(0)
    if a.root is None:p.error('action requires --root')
    if a.action in ('fit','extract-features') and a.approval is None:p.error('released action requires --approval')
    if a.action=='prepare-features':result=prepare_features(a.root)
    elif a.action=='extract-features':result=extract_features(a.root,a.approval)
    elif a.action=='prepare':result=prepare(a.root)
    elif a.action=='validate':
        m,d,x,g,s,b=validate(a.root);result={'status':'valid','rows':len(d['rows']),'components':len(g['components']),'maximum_fits':30,'fits_completed':0}
    else:result=fit(a.root,a.approval)
    print(json.dumps(result,indent=2,allow_nan=False))
