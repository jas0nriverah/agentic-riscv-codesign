#!/usr/bin/env python3
"""One released V13 original-RTL batch; no fitting, replacement or retry.

prepare records a separate measurement source/tool seal without native study jobs.
collect requires the parent's committed approval. verify checks archived bytes only.
The frozen V4 signed-overflow simulator validation workaround is retained verbatim.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from measure_v6 import run_owned
from measure_v10_csd_hardware import HardwareWorkers, native_environment, abc_invocations, data_invocations
from evaluate_v6 import verification_source
from isaforge.features import parse_formula
from isaforge.rtl import BOUNDARIES, evaluate_formula, generate_rtl

PREFIX='generated/v13-coverage-measurements/'
COUNT=48
SEED=2026101529
ATTEMPT='attempt-0000'
BASE_TOOLS='results/2026-10-15-v10d-csd-hardware/tools.json'
BASE_TOOLS_SHA='ee267f729fb235c4a60b0688b9130cea987bcbf7076a347b0316d8f7089f547a'
POLICY={'seed':SEED,'random_vectors':2048,'boundary_vectors':100,'total_vectors':2148,
        'workers':2,'worker_timeout_seconds':360,'minimum_free_bytes':4*1024**3,
        'maximum_workspace_bytes':2*1024**3,'original_rtl_only':True,'candidate_count':48,
        'retries':0,'replacement_candidates':0,'new_estimator_fits':0}


def need(condition,message):
    if not condition:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def read(path):
    def unique(items):
        out={}
        for key,value in items:need(key not in out,'Duplicate JSON key');out[key]=value
        return out
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def utc(value):
    value=datetime.fromisoformat(value);need(value.tzinfo is not None,'Timezone required');return value

def record(path,root):return {'path':os.path.relpath(Path(path).resolve(),Path(root).resolve()),'sha256':sha(path)}
def integer(value):need(type(value) is int and value>=0,'Nonnegative integer count required');return value

def required_sources():
    names=('measure_v13_coverage.py','prepare_v13_coverage.py','measure_v6.py','evaluate_v4.py',
           'evaluate_v5.py','evaluate_v6.py','measure_v10_csd_hardware.py')
    return [*(ROOT/'scripts'/n for n in names),ROOT/'tests/test_measure_v13_coverage.py',
            ROOT/'tests/test_prepare_v13_coverage.py',ROOT/'docs/v13-coverage-protocol.md',
            *sorted((ROOT/'isaforge').glob('*.py'))]

def check_hashes(bindings):
    need(all(p.is_file() and not p.is_symlink() and sha(p)==h for p,h in bindings.items()),'Bound source/input changed')

def prepared_inputs(root):
    from prepare_v13_coverage import validate_preparation
    root=Path(root).resolve();manifest,recipe,candidates=validate_preparation(root)
    need(manifest['schema']=='isaforge-v13-coverage-preparation-v1','V13 input seal required')
    formulas=[r['formula'] for r in candidates]
    need(len(formulas)==len(set(formulas))==COUNT and len({r['candidate_id'] for r in candidates})==COUNT
         and all(parse_formula(f).canonical()==f for f in formulas),'Exactly48 distinct canonical originals required')
    policy=recipe['future_collection_policy']
    for k,v in [('seed',SEED),('random_vectors',2048),('boundary_vectors',100),('total_vectors',2148),('workers',2),('timeout_seconds',360)]:
        need(type(policy[k]) is int and policy[k]==v,'Changed input collection policy')
    bindings={root/'preparation.json':sha(root/'preparation.json')}
    for e in manifest['files']:
        p=(root/e['path']).resolve();need(p.is_relative_to(ROOT),'Repository-local sealed input required')
        need(p not in bindings or bindings[p]==e['sha256'],'Conflicting binding');bindings[p]=e['sha256']
    check_hashes(bindings)
    return manifest,recipe,candidates,bindings

def inventory_tree(directory):
    directory=Path(directory).resolve();rows=[]
    for p in sorted(directory.rglob('*')):
        if p.is_file():rows.append({'path':p.relative_to(directory).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    return rows

def tools_inventory():
    need(sha(ROOT/BASE_TOOLS)==BASE_TOOLS_SHA,'Historical synthesis inventory differs')
    baseline=read(ROOT/BASE_TOOLS)
    tools={'schema':'isaforge-v13-coverage-tools-v1','inherited_inventory':{'path':BASE_TOOLS,'sha256':sha(ROOT/BASE_TOOLS)},
           'executables':{k:dict(v) for k,v in baseline['executables'].items()},'yosys_data':baseline['yosys_data'],
           'python_version':sys.version,'platform':sys.platform,
           'scope':'Same-host binary and data provenance; OS, SDK, dynamic loader and system libraries are not hermetic.'}
    for name,command in [('python',sys.executable),('verilator','verilator'),('cxx','c++'),('make','make'),('perl','perl')]:
        found=shutil.which(command);need(found is not None,'Required runtime unavailable: '+name)
        p=Path(found).resolve();tools['executables'][name]={'path':str(p),'sha256':sha(p)}
    verilator=Path(tools['executables']['verilator']['path'])
    binary=verilator.with_name('verilator_bin');need(binary.is_file(),'Verilator native binary required')
    tools['executables']['verilator_bin']={'path':str(binary),'sha256':sha(binary)}
    include=verilator.parent.parent/'share/verilator/include'
    need(include.is_dir(),'Verilator include tree required')
    tools['verilator_include']={'path':str(include),'files':inventory_tree(include)}
    # Apple compiler shim resolves the SDK compiler at execution; pin that file too.
    if sys.platform=='darwin':
        compiler=Path(subprocess.check_output(['/usr/bin/xcrun','--find','clang++'],text=True).strip()).resolve()
        tools['executables']['compiler']={'path':str(compiler),'sha256':sha(compiler)}
    tools['environment']=native_environment(tools)
    tools['resolved_commands']={n:{'path':str(Path(shutil.which(n,path=tools['environment']['PATH'])).resolve()),'sha256':sha(shutil.which(n,path=tools['environment']['PATH']))} for n in ('verilator','c++','make','perl')}
    validate_tools(tools);return tools

def validate_tools(tools):
    need(tools['schema']=='isaforge-v13-coverage-tools-v1' and tools['python_version']==sys.version
         and tools['platform']==sys.platform,'Executing runtime differs')
    base=tools['inherited_inventory'];need(base['path']==BASE_TOOLS and sha(ROOT/base['path'])==base['sha256']==BASE_TOOLS_SHA,'Inherited tool inventory changed')
    historical=read(ROOT/BASE_TOOLS)
    need(tools['yosys_data']==historical['yosys_data'] and all(tools['executables'][k]==v for k,v in historical['executables'].items()),'Pinned synthesis tool differs')
    need({'yosys','abc','yosys_config','python','verilator','verilator_bin','cxx','make','perl'}<=set(tools['executables']),'Incomplete native runtime inventory')
    for e in tools['executables'].values():need(Path(e['path']).is_absolute() and sha(e['path'])==e['sha256'],'Native executable changed')
    need(tools['executables']['python']['path']==str(Path(sys.executable).resolve()),'Python executable differs')
    for key in ('yosys_data','verilator_include'):
        need(inventory_tree(tools[key]['path'])==tools[key]['files'],'Native data tree changed')
    need(tools['environment']==native_environment(tools),'Changed native environment')
    need(tools['resolved_commands']=={n:{'path':str(Path(shutil.which(n,path=tools['environment']['PATH'])).resolve()),'sha256':sha(shutil.which(n,path=tools['environment']['PATH']))} for n in ('verilator','c++','make','perl')},'Native command resolution changed')

def prepare_measurement(root):
    root=Path(root).resolve();manifest,recipe,candidates,bindings=prepared_inputs(root)
    need(not (root/'measurement-plan.json').exists() and not (root/'measurement-tools.json').exists(),'Fresh measurement seal required')
    bindings.update({p.resolve():sha(p) for p in required_sources()});bindings[ROOT/BASE_TOOLS]=sha(ROOT/BASE_TOOLS)
    tools=tools_inventory();write(root/'measurement-tools.json',tools);check_hashes(bindings)
    plan={'schema':'isaforge-v13-coverage-measurement-plan-v1','status':'prepared-no-native-jobs','created_at_utc':now(),
          'preparation_sha256':sha(root/'preparation.json'),'recipe_sha256':sha(root/'recipe.json'),
          'candidates_sha256':sha(root/'candidates.json'),'tools':record(root/'measurement-tools.json',root),
          'policy':POLICY,'files':[record(p,root) for p in sorted(bindings)],
          'verification':'Frozen verify_wrapping on all48 before any mapping; retained identical-RTL signed-overflow workaround allowed.',
          'archive_replay':'Member SHA256, exact vector regeneration, original RTL identity and mapped LUT4/carry recount; V8/V9 stdlib oracle can independently adapt to V13 seed/formulas.',
          'native_jobs':0,'estimator_fits':0}
    write(root/'measurement-plan.json',plan);return plan

def validate_plan(root):
    root=Path(root).resolve();manifest,recipe,candidates,bindings=prepared_inputs(root);plan=read(root/'measurement-plan.json')
    need(plan['schema']=='isaforge-v13-coverage-measurement-plan-v1' and plan['status']=='prepared-no-native-jobs' and plan['policy']==POLICY,'Fixed measurement plan required')
    for n in ('preparation','recipe','candidates'):need(plan[n+'_sha256']==sha(root/(n+'.json')),'Plan input seal differs')
    seen={}
    for e in plan['files']:
        p=(root/e['path']).resolve();need(p.is_relative_to(ROOT) and p not in seen,'Duplicate/nonlocal plan binding');seen[p]=e['sha256']
    need(set(bindings)|{p.resolve() for p in required_sources()}|{ROOT/BASE_TOOLS}==set(seen),'Exact native/source/input closure required')
    check_hashes(seen);need(plan['tools']==record(root/'measurement-tools.json',root),'Tool seal differs')
    tools=read(root/'measurement-tools.json');validate_tools(tools)
    seen[root/'measurement-plan.json']=sha(root/'measurement-plan.json');seen[root/'measurement-tools.json']=sha(root/'measurement-tools.json')
    return manifest,recipe,candidates,plan,tools,seen

def validate_approval(root,approval):
    root=Path(root).resolve();approval=Path(approval).resolve();need(approval==root/'measurement-approval.json','Exact root approval required')
    manifest,recipe,candidates,plan,tools,bindings=validate_plan(root);review=read(approval)
    expected={'status':'approved-v13-coverage-measurements','preparation_sha256':sha(root/'preparation.json'),
              'recipe_sha256':sha(root/'recipe.json'),'candidates_sha256':sha(root/'candidates.json'),
              'measurement_plan_sha256':sha(root/'measurement-plan.json'),'tools_sha256':sha(root/'measurement-tools.json'),
              'collector_sha256':sha(__file__),'collector_tests_sha256':sha(ROOT/'tests/test_measure_v13_coverage.py')}
    need(all(review.get(k)==v for k,v in expected.items()) and isinstance(review.get('freeze_commit'),str)
         and re.fullmatch('[0-9a-f]{40}',review['freeze_commit']),'Exact committed measurement release required')
    need(utc(review['reviewed_at_utc'])>=max(utc(plan['created_at_utc']),utc(manifest['created_at_utc'])),'Approval precedes preparation')
    for p,h in bindings.items():
        r=subprocess.run(['git','show',review['freeze_commit']+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True)
        need(r.returncode==0 and digest(r.stdout)==h,'Approved source/input/tool seal differs from Git')
    bindings[approval]=sha(approval);return candidates,plan,tools,review,bindings

def vectors():
    pairs=list(itertools.product(BOUNDARIES,repeat=2));rng=random.Random(SEED)
    pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048));need(len(pairs)==2148,'Fixed vector count');return pairs

def validate_verification(proof,folder,formulas):
    required={'verified':True,'formula_count':COUNT,'vectors_per_formula':2148,'total_comparisons':COUNT*2148,'random_seed':SEED}
    need(all(type(proof.get(k)) is type(v) and proof[k]==v for k,v in required.items()),'Incomplete original RTL verification')
    need(proof['v4_validation_override_sha256']==sha(ROOT/'isaforge/v4_validation.py'),'Verification worker differs')
    need((folder/'verification.v').read_text()==verification_source(formulas) and sha(folder/'verification.v')==proof['rtl_sha256'],'Original batch RTL differs')
    lines=[' '.join(f'{v:08x}' for v in [a,b,*[evaluate_formula(f,a,b) for f in formulas]]) for a,b in vectors()]
    need((folder/'vectors.txt').read_text()=='\n'.join(lines)+'\n' and sha(folder/'vectors.txt')==proof['vectors_sha256'],'Expected vectors differ')
    need(type(proof.get('signed_overflow_workaround_applied')) is bool,'Explicit workaround status required')

def validate_metric(metric,folder,formula,tools):
    version=tools['executables']['yosys']['version'];original=generate_rtl(formula).encode()
    need(metric.get('formula')==formula and metric.get('tool')==version and metric.get('measurement_source')=='rtl_synthesis'
         and metric['rtl_sha256']==digest(original) and (folder/'candidate.v').read_bytes()==original,'Mapped target is not sealed original RTL')
    for n,k in [('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]:need(sha(folder/n)==metric[k],'Raw mapped evidence hash differs')
    expected=f'read_verilog "{folder/"candidate.v"}"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{folder/"ice40-netlist.json"}"\nstat\n'
    need((folder/'ice40.ys').read_text()==expected,'Fixed synthesis recipe differs')
    cells=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate'].get('cells',{}).values())
    need(dict(cells)==metric['ice40_cell_types'] and set(cells)<={'SB_LUT4','SB_CARRY'},'Mapped cell inventory differs')
    for k,c in [('ice40_lut4_count','SB_LUT4'),('ice40_carry_count','SB_CARRY')]:need(integer(metric[k])==cells[c],'Mapped resource recount differs')
    need(metric.get('command')==[tools['executables']['yosys']['path'],'-s',str(folder/'ice40.ys')],'Actual synthesis command differs')
    log=(folder/'ice40.log').read_text();metric={**metric,'tool_sha256':tools['executables']['yosys']['sha256'],
        'abc_invocations':abc_invocations(log,tools),'data_invocations':data_invocations(log,tools,folder/'candidate.v')}
    return metric

def guard(scratch,output):
    need(shutil.disk_usage(ROOT).free>=POLICY['minimum_free_bytes'],'Less than4GiB free; retained attempt stops')
    size=0
    for directory in (scratch,output):
        for p in directory.rglob('*'):
            need(not p.is_symlink(),'Symlink in owned evidence')
            if p.is_file():size+=p.stat().st_size
    need(size<=POLICY['maximum_workspace_bytes'],'Owned workspace exceeds2GiB; retained attempt stops')

def safe_cancel(owner,failures):
    try:owner.cancel()
    except BaseException as e:failures.append({'stage':'cleanup','error':repr(e)})

def archive(scratch,output,done):
    files={}
    for p in sorted(scratch.rglob('*')):
        need(not p.is_symlink(),'Symlink evidence forbidden')
        if p.is_file() and not {'obj_dir','obj_dir_wrapv'}.intersection(p.parts):files[p.relative_to(scratch).as_posix()]=p
    for n in ('verification.json','unique-measurements.json','labels.json','completion.json'):files['stage/'+n]=output/n
    records=[];path=output/'raw-evidence.zip'
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,p in sorted(files.items()):
            data=p.read_bytes();z.writestr(name,data);records.append({'path':name,'sha256':digest(data),'size':len(data)})
    result={'schema':'isaforge-v13-coverage-raw-evidence-v1','archive':'raw-evidence.zip','archive_sha256':sha(path),
            'complete':done['complete'],'attempt':ATTEMPT,'files':records,'compiler_objects_included':False,'completion_sha256':sha(output/'completion.json')}
    write(output/'raw-evidence.json',result);return result

def verify_archive(root):
    stage=Path(root)/'measurements'/ATTEMPT;m=read(stage/'raw-evidence.json');done=read(stage/'completion.json')
    need(m['schema']=='isaforge-v13-coverage-raw-evidence-v1' and m['attempt']==ATTEMPT and m['complete'] is done['complete'],'Archive identity differs')
    need(sha(stage/'raw-evidence.zip')==m['archive_sha256'] and sha(stage/'completion.json')==m['completion_sha256'],'Archive/completion digest differs')
    rows={r['path']:r for r in m['files']};need(len(rows)==len(m['files']),'Duplicate manifest member')
    with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
        need(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(rows),'Archive inventory differs')
        for n,r in rows.items():
            p=PurePosixPath(n);need(not p.is_absolute() and '..' not in p.parts and '\\' not in n and str(p)==n,'Unsafe archive path')
            data=z.read(n);need(type(r['size']) is int and len(data)==r['size'] and digest(data)==r['sha256'],'Archived member differs')
        need(z.read('stage/completion.json')==(stage/'completion.json').read_bytes(),'Archived completion differs')
        for n,k in [('verification.json','verification_sha256'),('labels.json','labels_sha256'),('unique-measurements.json','unique_measurements_sha256')]:
            need(sha(stage/n)==done[k] and z.read('stage/'+n)==(stage/n).read_bytes(),'Stage bytes differ')
    return m

def collect(root,approval):
    root=Path(root).resolve();candidates,plan,tools,review,bindings=validate_approval(root,approval)
    output=root/'measurements'/ATTEMPT;scratch=ROOT/PREFIX/ATTEMPT
    need(not (root/'measurements').exists() and not scratch.exists() and not (root/'label-release.json').exists(),'Single fresh measurement attempt required; no retries')
    guard(scratch,output);output.mkdir(parents=True);scratch.mkdir(parents=True)
    release={'schema':'isaforge-v13-coverage-label-release-v1','released_at_utc':now(),'freeze_commit':review['freeze_commit'],
             **{k:sha(root/(n+'.json')) for k,n in [('preparation_sha256','preparation'),('recipe_sha256','recipe'),('candidates_sha256','candidates'),('measurement_plan_sha256','measurement-plan'),('tools_sha256','measurement-tools'),('approval_sha256','measurement-approval')]},
             'collector_sha256':sha(__file__),'policy':POLICY}
    write(root/'label-release.json',release);bindings[root/'label-release.json']=sha(root/'label-release.json')
    for n in ('preparation','recipe','candidates','measurement-plan','measurement-tools','measurement-approval','label-release'):shutil.copyfile(root/(n+'.json'),scratch/(n+'.json'))
    for p,h in bindings.items():
        if p in required_sources():
            dest=scratch/'sources'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    formulas=sorted(r['formula'] for r in candidates);owner=HardwareWorkers(tools);failures=[];proofs=[];measured={};interruption=None
    try:
        check_hashes(bindings);validate_tools(tools)
        folder=scratch/'verification/batch-0000'
        proof=run_owned({'kind':'verify','formulas':formulas,'folder':str(folder),'seed':SEED},scratch/'verification-0000-worker.log',owner,timeout=360)
        validate_verification(proof,folder,formulas);proofs.append(proof);guard(scratch,output)
        write(scratch/'verification-gate.json',{'verified_at_utc':now(),'comparison_count':COUNT*2148,'verification_sha256':digest(json.dumps(proof,sort_keys=True).encode())})
        def measure(formula):
            folder=scratch/'circuits'/digest(formula.encode())[:20];need(not folder.exists(),'Fresh circuit required')
            folder.mkdir(parents=True);write(folder/'measurement-start.json',{'formula':formula,'started_at_utc':now(),'verification_gate_sha256':sha(scratch/'verification-gate.json')})
            metric=run_owned({'kind':'map','formula':formula,'folder':str(folder),'executable':tools['executables']['yosys']['path'],
                              'version':tools['executables']['yosys']['version']},folder/'worker.log',owner,timeout=360)
            metric=validate_metric(metric,folder,formula,tools);write(folder/'measurement.json',metric);return metric
        pool=ThreadPoolExecutor(max_workers=2)
        try:
            pending={};iterator=iter(formulas)
            while True:
                check_hashes(bindings);guard(scratch,output)
                while len(pending)<2:
                    formula=next(iterator,None)
                    if formula is None:break
                    pending[pool.submit(measure,formula)]=formula
                if not pending:break
                ready,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
                for future in ready:
                    formula=pending.pop(future)
                    try:measured[formula]=future.result()
                    except Exception as e:failures.append({'stage':'synthesis','formula':formula,'error':repr(e)})
        except BaseException:
            safe_cancel(owner,failures);raise
        finally:pool.shutdown(wait=True,cancel_futures=True)
    except BaseException as e:
        failures.append({'stage':'verification-or-guard' if not proofs else 'guard-or-interruption','error':repr(e)});safe_cancel(owner,failures)
        if not isinstance(e,Exception):interruption=e
    try:check_hashes(bindings);validate_tools(tools);guard(scratch,output)
    except BaseException as e:failures.append({'stage':'final-provenance-resource','error':repr(e)})
    unique=[measured[f] for f in formulas if f in measured]
    labels=[{**r,'lut4_count':measured[r['formula']]['ice40_lut4_count'],'carry_count':measured[r['formula']]['ice40_carry_count'],
             'rtl_sha256':measured[r['formula']]['rtl_sha256'],'measurement_source':'rtl_synthesis','correctness_verified':True} for r in candidates if r['formula'] in measured]
    for n,v in [('verification',proofs),('unique-measurements',unique),('labels',labels)]:write(output/(n+'.json'),v)
    done={'schema':'isaforge-v13-coverage-measurements-v1','attempt':ATTEMPT,'complete':not failures and len(labels)==48,
          'failures':failures,'candidate_count':48,'new_physical_measurements':len(unique),'verified_comparisons':COUNT*2148 if proofs else 0,
          'verification_seed':SEED,'vectors_per_formula':2148,'workers':2,'verification_batch_sizes':[48],
          'original_rtl_only':True,'legacy_measurements_reused':False,'new_estimator_fits':0,'freeze_commit':review['freeze_commit'],
          **{k:v for k,v in release.items() if k.endswith('_sha256')},'release_sha256':sha(root/'label-release.json'),
          **{k:sha(output/n) for n,k in [('verification.json','verification_sha256'),('labels.json','labels_sha256'),('unique-measurements.json','unique_measurements_sha256')]},
          'scratch_directory':scratch.relative_to(ROOT).as_posix(),'completed_at_utc':now()}
    write(output/'completion.json',done)
    try:archive(scratch,output,done);verify_archive(root);guard(scratch,output)
    except BaseException as e:
        # A failed archive cannot release a completed primary. Preserve the original
        # stage completion and partial archive; publish an explicit failed root status.
        done={**done,'complete':False,'failures':[*failures,{'stage':'archive','error':repr(e)}]}
    write(root/'measurements/completion.json',done)
    if interruption is not None:raise interruption
    if not done['complete']:raise RuntimeError('Incomplete V13 attempt retained; no fitting release')
    return done

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','collect','verify'));p.add_argument('--root',type=Path,required=True);p.add_argument('--approval',type=Path)
    a=p.parse_args()
    if a.action=='collect':
        if a.approval is None:p.error('collect requires --approval root/measurement-approval.json')
        result=collect(a.root,a.approval)
    elif a.action=='prepare':result=prepare_measurement(a.root)
    else:result=verify_archive(a.root)
    print(json.dumps(result,indent=2,allow_nan=False))
