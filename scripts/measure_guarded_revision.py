#!/usr/bin/env python3
"""Joint-frozen synthetic 32/40 measurement; 300s shared native, zero fits."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json, os, signal, subprocess, sys, time, zipfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import validate_selected_features as prior
import measure_budget_preserving_coverage as previous
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
TRAIN = ROOT / 'results/guarded-revision-data'
TEST = ROOT / 'results/guarded-revision-validation'
POLICY = {'total_native_seconds': 300, 'training_native_seconds': 180, 'workers': 2,
          'fits': 0, 'retries': 0, 'replacement_candidates': 0, 'random_vectors': 2048,
          'vectors_per_formula': 2148, 'caps_lut4': [32, 64, 128]}
TRAIN_TEMPLATES = (
 ('signed_variable_xor_dual_add','xor(sub(in0,sra(xor(in0,in1),andi(in0,{k}))),add(in0,in1))',[1,7,15,31]),
 ('signed_variable_dual_sub','xor(sub(in0,sra(in1,andi(in0,{k}))),sub(in0,in1))',[1,7,15,31]),
 ('signed_variable_add_sub','xor(add(in0,sra(in1,andi(in0,{k}))),sub(in0,in1))',[1,7,15,31]),
 ('signed_variable_xor_add_sub','xor(add(in0,sra(xor(in0,in1),andi(in0,{k}))),sub(in0,in1))',[1,7,15,31]),
 ('static_signed_or_difference','sub(srai(or(in0,in1),{k}),srai(in1,31))',[2,7,19,29]),
 ('static_signed_offset_difference','sub(srai(xori(in0,37),{k}),srai(in1,31))',[2,7,19,29]),
 ('static_signed_sum_difference','sub(srai(add(in0,or(in0,in1)),{k}),srai(in1,31))',[2,7,19,29]),
 ('static_signed_sub_difference','sub(srai(sub(in0,and(in0,in1)),{k}),srai(in1,31))',[2,7,19,29]),
)
TEST_TEMPLATES = (
 ('heldout_signed_variable_or_dual','xor(sub(in0,sra(or(in0,in1),andi(in0,{k}))),add(in0,in1))',[1,5,15,31]),
 ('heldout_signed_variable_dual_offset','xor(sub(in0,sra(in1,andi(in0,{k}))),addi(in1,73))',[1,5,15,31]),
 ('heldout_signed_variable_add_boolean','xor(add(in0,sra(in1,andi(in0,{k}))),and(in0,in1))',[1,5,15,31]),
 ('heldout_signed_variable_reverse_dual','xor(sub(in1,sra(in0,andi(in1,{k}))),add(in0,in1))',[1,5,15,31]),
 ('heldout_static_signed_xor_sum','add(srai(xor(in0,in1),{k}),srai(in1,31))',[3,9,21,28]),
 ('heldout_static_signed_or_xor','xor(srai(or(in0,in1),{k}),srai(in1,31))',[3,9,21,28]),
 ('control_variable_left_boolean','or(sll(and(in0,in1),andi(in0,{k})),xor(in0,in1))',[1,7,15,31]),
 ('control_variable_right_arithmetic','sub(srl(add(in0,in1),andi(in0,{k})),xor(in0,in1))',[1,7,15,31]),
 ('control_mixed_static_arithmetic','xor(sub(slli(in1,{k}),in0),srli(add(in0,in1),5))',[2,6,17,27]),
 ('control_mixed_boolean_arithmetic','add(and(slli(in0,{k}),in1),sub(in0,in1))',[2,6,17,27]),
)
read, write, need, sha, now = prior.read, prior.write, prior.need, prior.sha, prior.now
skeleton = previous.skeleton

def candidates(kind):
    need(kind in ('train','test'), 'Unknown cohort')
    rows=[]
    for name, template, values in TRAIN_TEMPLATES if kind=='train' else TEST_TEMPLATES:
        for k in values:
            formula=parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id':'guarded-revision-'+kind+':'+prior.sha_bytes(formula.encode()),
                         'formula':formula,'template':name,'parameter':k})
    need(len(rows)==len({r['formula'] for r in rows})==(32 if kind=='train' else 40), 'Exact unique cohort required')
    return rows

def inventory():
    """Extend the frozen all-history inventory by every subsequent consumed cohort/alias."""
    paths=[previous.OUT/n for n in ('historical-formulas.json','candidates.json','novelty.json')]
    paths += [ROOT/'results/targeted-coverage-data'/n for n in ('candidates.json','novelty.json')]
    paths += [ROOT/'results/targeted-coverage-validation'/n for n in ('candidates.json','novelty.json')]
    paths += [ROOT/'results/selection-validation'/n for n in ('historical-formulas.json','historical-input-inventory.json','candidates.json')]
    history=set()
    for path in paths:
        history.update(prior.formula_strings(read(path)))
    return sorted(history), paths

def draft_novelty():
    history, paths=inventory()
    known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history}; train_skeletons={skeleton(r['formula']) for r in candidates('train')}
    from isaforge.semantic_features_v7 import analyze_modes, Budget
    seen=set(); reports={'train':[],'test':[]}
    for kind in ('train','test'):
        for row in candidates(kind):
            modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500))
            forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
            keys=set().union(*(prior.identity_keys(f) for f in forms))
            report={'candidate_id':row['candidate_id'],'forms':sorted(forms),
                    'historical_identity_overlap':sorted(keys&known),
                    'across_cohort_identity_overlap':sorted(keys&seen),
                    'historical_skeleton_overlap':skeleton(row['formula']) in old_skeletons,
                    'train_test_skeleton_overlap':kind=='test' and skeleton(row['formula']) in train_skeletons}
            reports[kind].append(report);seen.update(keys)
    return history, paths, reports

def prepare():
    need(not TRAIN.exists() and not TEST.exists(),'Fresh directories required')
    history, paths, reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['across_cohort_identity_overlap'] or
                 r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap']
                 for rs in reports.values() for r in rs),'Input-only collision; stop before freeze or native jobs')
    for kind,out in [('train',TRAIN),('test',TEST)]:
        write(out/'candidates.json',candidates(kind))
        write(out/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':72,
            'previous_additional_consumed_count':136,'comparisons':reports[kind],
            'scope':'Canonical, commutative V4, V4/V5 normalized identities and V7 aliases versus frozen all-prior inventory including last64+40+32; original constant-erased AST skeletons versus all prior and across train/test. Not exhaustive semantic equivalence or application independence.'})
    write(TRAIN/'historical-formulas.json',history)
    tools=read(previous.OUT/'tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(TRAIN/'tools.json',tools)
    sources=[Path(__file__),ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',
             ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_guarded_revision.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'guarded-revision-joint32train40test-v1','frozen_at_utc':now(),'policy':POLICY,
        'training_count':32,'test_count':40,'training_templates':TRAIN_TEMPLATES,'test_templates':TEST_TEMPLATES,
        'success_rule':'Freeze candidate policy and evaluation criteria before training labels; test MAE and positive-target MAPE strictly improve versus base, maximum underprediction and false_accept and false_reject separately no worse at each cap32/64/128. Retain incumbent comparison and all consumed regressions.',
        'chronology':'Joint input/measurement/policy freeze and audit; both cohorts label-free features; auditor pretrain receipt; original training RTL verification then labels; candidate/incumbent/base ordered test points freeze and independent receipt; original test RTL verification then labels.',
        'native_accounting':'Sum elapsed wall time of feature, train-label, test-label stages, including all subprocess startup/verification/features/synthesis and failures; idle audit/policy time excluded. Both-cohort feature stage charged to training180s. Two workers maximum, all stages shared300s.',
        'missing_rule':'Keep all72 predeclared rows and every failure; no retries, replacements or complete-cohort scoring with missing cases.',
        'scope':'Synthetic regression-targeted training32 and fresh compositions24 plus variable-shift/mixed controls16; no application-transfer, calibration, timing, power, full-core or CPU claim.',
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
        'inputs':{str(p.relative_to(ROOT)):sha(p) for out in [TRAIN,TEST] for p in sorted(out.iterdir()) if p.is_file()},
        'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},
        'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(TRAIN/'plan.json',plan);write(TEST/'plan.json',plan);return plan

def validate():
    plan=read(TRAIN/'plan.json');need(plan['policy']==POLICY,'Policy changed')
    need(read(TEST/'plan.json')==plan,'Joint cohort plan differs')
    for kind,out in [('train',TRAIN),('test',TEST)]:need(read(out/'candidates.json')==candidates(kind),'Cohort changed')
    for section in ('sources','inputs','prior_inventory_sources'):
        for path,digest in plan[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed: '+path)
    for tool in read(TRAIN/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
    return plan

def verify_point_freeze():
    freeze=read(TEST/'point-freeze.json');need(freeze['target_label_jobs']==0,'Test points must precede labels')
    need(bool(freeze['bindings']),'Point bindings required')
    for path,digest in freeze['bindings'].items():need(sha(ROOT/path)==digest,'Point/model binding changed: '+path)
    return freeze

def receipt(path):
    need(read(path)['status']=='pass','Independent passing auditor receipt required: '+str(path))

def worker(kind,stage,index):
    validate();out=TRAIN if kind=='train' else TEST;rows=read(out/'candidates.json')
    attempt=TRAIN/'feature-attempt.json' if stage=='feature' else out/'label-attempt.json'
    need(attempt.exists(),'Owned single attempt required')
    if kind=='test' and stage!='feature':verify_point_freeze()
    if stage=='feature':
        row=rows[index];folder=out/'raw/features'/str(index);tools=read(TRAIN/'tools.json')
        tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
        _, records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1)
        write(folder/'result.json',{**row,**records[0],'status':'complete'})
    elif stage=='verify':
        from isaforge.rtl import verify_rtl_batch
        proof=verify_rtl_batch([r['formula'] for r in rows],out/'raw/verification',random_vectors=2048,
                               seed=2026110905+(kind=='test'),timeout=180)
        need(proof['verified'] is True and proof['formula_count']==len(rows) and
             proof['total_comparisons']==2148*len(rows),'Complete original RTL verification required')
        write(out/'raw/verification/result.json',proof)
    else:
        proof=read(out/'raw/verification/result.json')
        need(proof['verified'] and proof['total_comparisons']==2148*len(rows),'Original RTL verification required')
        from isaforge.synthesis import run_synthesis
        from isaforge.rtl import generate_rtl
        row=rows[index];folder=out/'raw/labels'/str(index);metrics=run_synthesis(row['formula'],folder,timeout=120)
        counts=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values())
        need(counts['SB_LUT4']==metrics['ice40_lut4_count'],'LUT recount differs')
        need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'Original RTL differs')
        write(folder/'result.json',{**row,'status':'complete','lut4':counts['SB_LUT4'],'carry':counts['SB_CARRY'],
            'rtl_sha256':metrics['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),
            'netlist_sha256':sha(folder/'ice40-netlist.json'),
            'measurement_source':'Actual Yosys synth_ice40 defaults original RTL; SB_LUT4 only'})

def run(stage):
    validate();receipt(TRAIN/'preflight-audit.json')
    feature=stage=='features';training=stage!='test-labels';out=TRAIN if training else TEST
    attempt=TRAIN/'feature-attempt.json' if feature else out/'label-attempt.json'
    need(not attempt.exists(),'Single attempt only; no retries')
    used=0 if feature else read(TRAIN/('feature-completion.json' if training else 'completion.json'))['total_native_elapsed_seconds']
    if not feature:
        need(read(TRAIN/'feature-completion.json')['complete'],'Complete features required')
        receipt(TRAIN/'pretrain-audit.json' if training else TEST/'prelabel-audit.json')
        if not training:
            need(read(TRAIN/'completion.json')['complete'],'Complete training labels required');verify_point_freeze()
    budget=min(300-used,180-used) if training else 300-used
    need(budget>0,'Shared native budget exhausted')
    began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,
                   'stage':stage,'policy':POLICY,'fits':0})
    def owned(kind,phase,index=None):
        dest=TRAIN if kind=='train' else TEST
        folder=dest/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log'
        command=[sys.executable,str(Path(__file__).resolve()),'worker','--kind',kind,'--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Shared native deadline exhausted')
            with log.open('x') as stream:
                process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:raise TimeoutError('Shared native deadline')
                need(code==0,'Worker failed: '+str(log))
        except Exception as caught:error=repr(caught)
        finally:
            if process:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        result={'kind':kind,'stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),
                'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
        write(folder/'worker.json',result);jobs.append(result);return result
    def batch(kind,phase):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda i:owned(kind,phase,i),range(len(candidates(kind)))))
        failures.extend(r for r in results if r['error'])
        return results
    def retained(kind,phase):
        dest=TRAIN if kind=='train' else TEST;records=[]
        for index,row in enumerate(read(dest/'candidates.json')):
            path=dest/'raw'/(phase+'s')/str(index)/'result.json'
            records.append(read(path) if path.exists() else {**row,'status':'failed','error':'No complete native result; see retained worker evidence'})
        return records
    try:
        if feature:
            for kind,dest in [('train',TRAIN),('test',TEST)]:
                batch(kind,'feature');records=retained(kind,'feature')
                write(dest/'features.json',{'columns':list(v6.columns()),'records':records})
                need(len(v6.columns())==336 and all(r['status']=='complete' and len(r['values'])==336 for r in records),'Incomplete336 features; no replacements')
            train=read(TRAIN/'features.json')['records'];test=read(TEST/'features.json')['records'];keys={tuple(r['values']) for r in train}
            write(TEST/'feature-collisions.json',{'test_training_exact_full336_collisions':[r['candidate_id'] for r in test if tuple(r['values']) in keys],
                   'scope':'Full336 equality is separate from formula identity; no row replacements.'})
        else:
            kind='train' if training else 'test';proof=owned(kind,'verify')
            if proof['error']:failures.append(proof)
            need(not failures,'Original RTL verification failed; labels forbidden')
            batch(kind,'label');write(out/'labels.json',retained(kind,'label'))
        need(not failures,'Incomplete stage; every failure retained; no retries or replacements')
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
        if feature:
            for kind,dest in [('train',TRAIN),('test',TEST)]:
                if not (dest/'features.json').exists():write(dest/'features.json',{'columns':list(v6.columns()),'records':retained(kind,'feature')})
        else:write(out/'labels.json',retained('train' if training else 'test','label'))
    finally:
        elapsed=time.monotonic()-began
        result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':elapsed,
                'total_native_elapsed_seconds':used+elapsed,'native_budget_seconds':budget,'fits':0,
                'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,
                'label_count':sum(r['status']=='complete' for r in read(out/'labels.json')) if (out/'labels.json').exists() else 0}
        write(out/('feature-completion.json' if feature else 'completion.json'),result)
    return result

def pack(kind):
    out=TRAIN if kind=='train' else TEST;raw=out/'raw';need(raw.is_dir(),'Raw evidence required')
    target=out/'raw-evidence.zip';need(not target.exists(),'Single archive only')
    files=[p for p in sorted(raw.rglob('*')) if p.is_file()]
    manifest=[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:archive.write(path,str(path.relative_to(out)))
    with zipfile.ZipFile(target) as archive:
        for item in manifest:need(prior.sha_bytes(archive.read(item['path']))==item['sha256'],'Archive verification failed')
    write(out/'raw-evidence-manifest.json',{'archive':target.name,'archive_sha256':sha(target),'files':manifest})
    shutil.rmtree(raw);return {'archive':str(target),'files':len(files),'sha256':sha(target)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['draft','prepare','features','train-labels','test-labels','worker','pack'])
    parser.add_argument('--kind',choices=['train','test'],default='train');parser.add_argument('--stage',choices=['feature','verify','label']);parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.command=='draft':
        history,paths,reports=draft_novelty();result={'historical_count':len(history),'collisions':[r for rs in reports.values() for r in rs if r['historical_identity_overlap'] or r['across_cohort_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap']]}
    elif args.command=='prepare':result=prepare()
    elif args.command=='worker':worker(args.kind,args.stage,args.index);return
    elif args.command=='pack':result=pack(args.kind)
    else:result=run(args.command)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
