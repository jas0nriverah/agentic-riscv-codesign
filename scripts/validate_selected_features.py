#!/usr/bin/env python3
"""One prospective synthetic transfer check; immutable inputs, zero fits, real LUT labels.

prepare projects historical evidence to formula strings only. run starts one
600-second, two-worker native attempt after full-data model artifacts are sealed.
All predictions precede verification and actual iCE40 labels. Failed rows remain.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import numpy as np
from isaforge import area_model_v6 as v6, area_model_v5 as v5
from isaforge.features import parse_formula
from isaforge.structural_features_v4 import normalize_formula as normalize_v4
from isaforge.structural_features_v5 import normalize_formula as normalize_v5
from isaforge.v5_corpus import equivalence_key

ARCHIVE = 'b64716a'
SEED = 2026110901
POLICY = {'native_attempt_seconds': 600, 'workers': 2, 'fits': 0,
          'retries': 0, 'replacement_candidates': 0, 'random_vectors': 2048,
          'vectors_per_formula': 2148, 'caps_lut4': [32, 64, 128]}
TEMPLATES = (
    ('boolean_add_shift', 'xor(add(in0,in1),srli(in0,{k}))', [3,5,7,11,13,17,23,29]),
    ('boolean_sub_shift', 'sub(and(in0,in1),slli(xor(in0,in1),{k}))', [1,3,5,9,13,17,21,27]),
    ('signed_compare_mix', 'add(slt(in0,in1),srli(xor(in0,in1),{k}))', [2,4,6,10,14,18,22,28]),
    ('masked_variable_shift', 'xor(srl(in0,andi(in1,{k})),addi(in1,37))', [1,3,7,15,17,21,27,31]),
    ('constant_product_mix', 'add(mul(in0,addi(0,{k})),xor(in1,srli(in0,7)))', [53,61,73,89,101,113,137,173]),
)
RECOVER = ['scripts/evaluate_v15_scoped.py', 'scripts/measure_v11e_transfer.py',
           'scripts/measure_v13b_coverage.py', 'scripts/measure_v6.py',
           'scripts/evaluate_v6.py', 'scripts/capture_v11_spooled.py']
EXCLUDED_NAMES = {'graph.json', 'word.json', 'sog.json', 'generic-netlist.json',
                  'ice40-netlist.json', 'package-lock.json', 'netlist.json'}


def now(): return datetime.now(timezone.utc).isoformat()
def sha_bytes(value): return hashlib.sha256(value).hexdigest()
def sha(path): return sha_bytes(Path(path).read_bytes())
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def need(value, message):
    if not value: raise ValueError(message)


def candidates():
    rows = []
    for name, template, parameters in TEMPLATES:
        for k in parameters:
            formula = parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id': 'selection-transfer:' + sha_bytes(formula.encode()),
                         'formula': formula, 'template': name, 'parameter': k})
    need(len(rows) == len({r['formula'] for r in rows}) == 40, 'Exact40 unique inputs required')
    return rows


def formula_strings(value):
    """Input projection only: numerical labels/predictions never enter novelty."""
    if isinstance(value, str):
        if re.fullmatch(r'[a-z][a-z0-9_]*\([a-z0-9_,()\- ]+\)', value):
            try: yield parse_formula(value).canonical()
            except ValueError: pass
    elif isinstance(value, dict):
        for key, child in value.items():
            # Some historical inventories map a formula to a group/id.
            if isinstance(key, str): yield from formula_strings(key)
            yield from formula_strings(child)
    elif isinstance(value, list):
        for child in value: yield from formula_strings(child)


@lru_cache(maxsize=None)
def identity_keys(formula):
    forms = {parse_formula(formula).canonical()}
    for normalizer in (normalize_v4, normalize_v5):
        for value in tuple(forms):
            try: forms.add(parse_formula(normalizer(value)).canonical())
            except ValueError: pass  # Bare wire/constant normal forms retained below.
    keys = {('canonical_or_normalized', value) for value in forms}
    keys.update(('commutative_v4_equivalence', equivalence_key(value)) for value in forms)
    for normalizer in (normalize_v4, normalize_v5):
        for value in forms:
            keys.add(('canonical_or_normalized', normalizer(value)))
    return frozenset(keys)


def historical_inputs(output):
    """Scan all recoverable historical JSON evidence, keeping formula projection.

    Netlists and graph payloads contain no formula inventory and are excluded by
    known filename. JSON in local ZIPs and the Git tar stream is scanned. No model loaded.
    """
    formulas = set(); records = []; malformed = []; skipped = Counter()
    def ingest(name, body, source):
        if b'formula' not in body and b'in0' not in body and b'in1' not in body: return
        try: data = json.loads(body)
        except (ValueError, UnicodeDecodeError) as error:
            malformed.append({'path': name, 'error': str(error)[:160]}); return
        found = set(formula_strings(data))
        if found:
            formulas.update(found)
            records.append({'source': source, 'path': name, 'sha256': sha_bytes(body),
                            'formula_count': len(found)})
    # Read every tracked historical JSON without restoring the historical tree.
    proc = subprocess.Popen(['git', 'archive', ARCHIVE], cwd=ROOT, stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
        for entry in archive:
            if not entry.isfile() or not entry.name.endswith(('.json', '.jsonl')): continue
            if Path(entry.name).name in EXCLUDED_NAMES: skipped['archive_netlist_graph'] += 1; continue
            ingest(entry.name, archive.extractfile(entry).read(), 'git:' + ARCHIVE)
    need(proc.wait() == 0, 'Historical git archive failed')
    scan_roots = [ROOT / 'results', ROOT / 'benchmarks', ROOT / 'generated', ROOT / 'models']
    # Parent's outputs are reachable historical exports outside the repository.
    outside = ROOT.parents[1] / 'outputs'
    if outside.is_dir(): scan_roots.append(outside)
    paths = []
    for base in scan_roots:
        paths.extend(base.rglob('*.json')); paths.extend(base.rglob('*.jsonl'))
    for path in sorted(set(paths)):
        if path.is_symlink() or path.is_relative_to(output) or 'selection-stability' in path.parts: continue
        if path.name in EXCLUDED_NAMES: skipped['local_netlist_graph'] += 1; continue
        ingest(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), path.read_bytes(), 'local')
    archives = sorted(set((ROOT / 'generated').rglob('*.zip')) | set((ROOT / 'results').rglob('*.zip')))
    archive_count = 0
    for path in archives:
        if path.is_relative_to(output): continue
        with zipfile.ZipFile(path) as archive:
            archive_count += 1
            for entry in archive.infolist():
                if not entry.filename.endswith(('.json', '.jsonl')) or Path(entry.filename).name in EXCLUDED_NAMES: continue
                ingest(str(path.relative_to(ROOT)) + '::' + entry.filename, archive.read(entry), 'local_zip')
    return formulas, {'formula_inventory_files': records, 'unique_formula_count': len(formulas),
        'scanned_local_json_count': len(paths), 'scanned_zip_count': archive_count,
        'excluded_no_formula_inventory_payloads': dict(skipped), 'malformed_json': malformed,
        'external_scan_roots': [str(p) for p in scan_roots if not p.is_relative_to(ROOT)]}


def sources():
    return [Path(__file__), ROOT/'scripts/predict.py', ROOT/'scripts/test_selection_stability.py',
            ROOT/'scripts/replay_selection_stability.py', ROOT/'tests/test_validate_selected_features.py',
            *sorted((ROOT / 'isaforge').glob('*.py'))]


def prepare(output):
    output = Path(output).resolve(); need(not output.exists(), 'Fresh output required')
    rows = candidates()
    formulas, inventory = historical_inputs(output)
    known = set().union(*(identity_keys(f) for f in sorted(formulas)))
    # Candidate semantic forms use only formula input and proof, no hardware job.
    from isaforge.semantic_features_v7 import analyze_modes, Budget
    reports = []; seen = set()
    for row in rows:
        modes = analyze_modes(row['formula'], budget=Budget(proof_timeout_ms=500))
        forms = {row['formula'], *(m['normalized_formula'] for m in modes.values())}
        keys = set().union(*(identity_keys(f) for f in forms))
        overlaps = sorted(keys & known)
        within = sorted(keys & seen)
        reports.append({'candidate_id': row['candidate_id'], 'forms': sorted(forms),
                        'historical_identity_overlap': overlaps, 'within_cohort_identity_overlap': within})
        seen.update(keys)
    need(not any(r['historical_identity_overlap'] or r['within_cohort_identity_overlap'] for r in reports),
         'Known identity collision: stop before freeze; no outcome-dependent replacements')
    output.mkdir(parents=True)
    write(output / 'candidates.json', rows)
    write(output / 'historical-formulas.json', sorted(formulas))
    write(output / 'historical-input-inventory.json', inventory)
    write(output / 'novelty.json', {'status': 'pass', 'comparisons': reports,
        'known_identity_key_count': len(known), 'unique_historical_formula_count': len(formulas),
        'scope': 'Exact/canonical, commutativity, V4 and V5 normalized identities plus all saved historical semantic aliases and prospective V7 modes. Sufficient identities only; no exhaustive semantic equivalence or application independence claim.',
        'limitations': 'Recoverable historical JSON inventories in git archive b64716a, local results/benchmarks/generated/models, local ZIPs and named outside outputs only. No guarantee for deleted/unreachable evidence, non-JSON sources, inaccessible external caches, or identities outside these normalizers.'})
    for name in RECOVER:
        body = subprocess.check_output(['git', 'show', ARCHIVE + ':' + name], cwd=ROOT)
        target = output / 'recovered-pipeline' / Path(name).name
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(body)
    tools = {}
    import shutil
    for name, argument in [('yosys', '-V'), ('verilator', '--version')]:
        executable = Path(shutil.which(name)).resolve()
        tools[name] = {'path': str(executable), 'sha256': sha(executable),
                       'version': subprocess.check_output([str(executable), argument], text=True).strip()}
    write(output / 'tools.json', tools)
    plan = {'schema': 'selection-fresh-synthetic-transfer-v1', 'frozen_at_utc': now(),
        'policy': POLICY, 'candidate_count': 40, 'templates': [name for name, _, _ in TEMPLATES],
        'primary_comparison': 'selected128 minus mapping217 mean absolute LUT4 error; paired plain point predictions.',
        'controls': ['original336'], 'caps': 'Plain p<=cap decisions at32/64/128. Report false_accept (predicted feasible, measured infeasible), false_reject, MAE, MAPE and maximum underprediction. No gate/guard adjustment.',
        'success_rule': 'Selected128 improves MAE and positive-target MAPE versus217 and does not increase false_accept OR false_reject at ANY cap32/64/128; otherwise no promotion.',
        'missing_rule': 'Retain every predeclared row and all failures. If any case or verification fails, complete-cohort primary unavailable. Never replace/retry.',
        'scope': 'Fresh synthetic transfer across five manually specified templates; no independent application-transfer, calibration, timing or full-core claim.',
        'chronology': 'Input/protocol freeze, completed stability plus full-data artifact freeze, label-free features, full ordered prediction freeze, original RTL verification, then actual fresh iCE40 target labels.',
        'sources': {str(p.relative_to(ROOT)): sha(p) for p in sources()},
        'inputs': {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
        'pipeline_recovery': {p.name: sha(p) for p in sorted((output/'recovered-pipeline').iterdir())},
        'fits': 0, 'target_label_jobs': 0, 'native_feature_jobs': 0}
    write(output / 'plan.json', plan)
    return plan


def validate(output):
    plan = read(output / 'plan.json')
    need(plan['policy'] == POLICY and read(output/'candidates.json') == candidates(), 'Protocol/cohort changed')
    bindings=dict(plan['sources'])
    amendment_path=output/'pre-native-amendment.json'
    if amendment_path.exists():
        amendment=read(amendment_path)
        need(amendment['original_plan_sha256']==sha(output/'plan.json') and amendment['target_label_jobs']==0 and amendment['native_feature_jobs']==0,'Invalid pre-native amendment')
        bindings.update(amendment['corrected_sources'])
    for relative, digest in bindings.items(): need(sha(ROOT/relative) == digest, 'Bound source changed: '+relative)
    for name, digest in plan['inputs'].items(): need(sha(output/name) == digest, 'Frozen input changed: '+name)
    for name, digest in plan['pipeline_recovery'].items(): need(sha(output/'recovered-pipeline'/name) == digest, 'Recovery changed')
    for tool in read(output/'tools.json').values(): need(sha(tool['path']) == tool['sha256'], 'Native binary changed')
    return plan


def metrics(rows, predictions, labels):
    need(len(labels)==len(rows) and all(r.get('status')=='complete' for r in labels), 'Full successful cohort required')
    y = np.array([r['lut4'] for r in labels], dtype=float); result = {}
    for name, values in predictions.items():
        p=np.asarray(values,dtype=float); need(p.shape == y.shape and np.isfinite(p).all() and (p>=0).all(), 'Invalid points')
        absolute=np.abs(p-y); positive=y>0; under=y-p
        result[name]={'count':len(y), 'mae_lut4':float(absolute.mean()),
            'positive_mape_percent':float((absolute[positive]/y[positive]).mean()*100) if positive.any() else None,
            'positive_count':int(positive.sum()), 'zero_count':int((~positive).sum()),
            'maximum_underprediction_lut4':float(max(0,under.max())),
            'worst_underprediction_candidate_id':rows[int(under.argmax())]['candidate_id'],
            'template_mae_lut4':{n:float(absolute[[r['template']==n for r in rows]].mean()) for n,_,_ in TEMPLATES},
            'caps':{str(cap):{'false_accept':int(((p<=cap)&(y>cap)).sum()),
                'false_reject':int(((p>cap)&(y<=cap)).sum()), 'predicted_accept':int((p<=cap).sum()),
                'actual_accept':int((y<=cap).sum()), 'total':len(y)} for cap in POLICY['caps_lut4']}}
    baseline,candidate=result['mapping217'],result['selected128']
    no_worse=all(candidate['caps'][str(cap)][kind]<=baseline['caps'][str(cap)][kind]
                 for cap in POLICY['caps_lut4'] for kind in ['false_accept','false_reject'])
    improved=candidate['mae_lut4']<baseline['mae_lut4'] and candidate['positive_mape_percent']<baseline['positive_mape_percent']
    return {'models':result, 'selected_minus217_mae_lut4':candidate['mae_lut4']-baseline['mae_lut4'],
            'selected_minus217_mape_percentage_points':candidate['positive_mape_percent']-baseline['positive_mape_percent'],
            'accuracy_improved':improved, 'all_cap_error_counts_no_worse':no_worse,
            'predeclared_success':improved and no_worse,
            'scope':'Fresh synthetic template transfer only; point decision errors are empirical counts, not calibrated safety guarantees.'}


def worker(output, stage, index=None):
    validate(output); rows=read(output/'candidates.json')
    need((output/'attempt.json').is_file(),'Owned attempt required before native worker')
    if stage in ('verify','label'):
        freeze=read(output/'point-freeze.json')
        for key,name in [('plan_sha256','plan.json'),('model_freeze_sha256','model-freeze.json'),('features_sha256','features.json'),('predictions_sha256','predictions.json')]:
            need(freeze[key]==sha(output/name),'Prediction seal changed')
        need(freeze['target_label_jobs']==0 and freeze['fits']==0,'Zero-target prediction freeze required')
        for relative,digest in read(output/'model-freeze.json')['models'].items():
            need(sha(ROOT/relative)==digest,'Frozen model bytes changed')
    if stage=='label':
        proof=read(output/'raw/verification/result.json')
        need(proof['verified'] is True and proof['formula_count']==40 and proof['total_comparisons']==85920,'Complete original RTL verification required before labels')
    if stage=='feature':
        row=rows[index]; folder=output/'raw/features'/str(index)
        tools=read(output/'tools.json'); tool={'version':tools['yosys']['version'], 'executable_sha256':tools['yosys']['sha256']}
        x, records=v6.FeatureExtractor(folder/'cache', frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1)
        write(folder/'result.json',{**row,**records[0]})
    elif stage=='verify':
        from isaforge.rtl import verify_rtl_batch
        proof=verify_rtl_batch([r['formula'] for r in rows],output/'raw/verification',random_vectors=2048,seed=SEED,timeout=180)
        write(output/'raw/verification/result.json',proof)
    elif stage=='label':
        from isaforge.synthesis import run_synthesis
        row=rows[index]; folder=output/'raw/labels'/str(index)
        m=run_synthesis(row['formula'],folder,timeout=120)
        netlist=read(folder/'ice40-netlist.json')
        count=Counter(c['type'] for c in netlist['modules']['candidate']['cells'].values())
        need(m['ice40_lut4_count']==count['SB_LUT4'],'Raw mapped LUT recount differs')
        from isaforge.rtl import generate_rtl
        need((folder/'candidate.v').read_text()==generate_rtl(row['formula']), 'Original RTL differs')
        write(folder/'result.json',{**row,'status':'complete','lut4':count['SB_LUT4'],
             'carry':count['SB_CARRY'],'rtl_sha256':m['rtl_sha256'],
             'measurement_source':'Actual Yosys synth_ice40 defaults on original RTL; SB_LUT4 cells only',
             'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json')})


def run(output, model_root):
    validate(output); need(not (output/'attempt.json').exists(), 'Only one attempt allowed')
    import test_selection_stability as stability
    need((model_root/'summary.json').is_file(), 'Completed stability required')
    summary=read(model_root/'summary.json')
    need(summary['fits_completed']==33 and summary['full_data_fits_completed']==3,'Completed frozen stability models required')
    models={name:stability.load_predictor(model_root,name) for name in ['mapping217','original336','selected128']}
    model_bindings={str(p.relative_to(ROOT)):sha(p) for p in sorted((model_root/'models').iterdir()) if p.is_file()}
    write(output/'model-freeze.json',{'frozen_at_utc':now(),'stability_summary_sha256':sha(model_root/'summary.json'),'models':model_bindings,'fits':0})
    rows=read(output/'candidates.json'); began=time.monotonic(); deadline=began+600
    write(output/'attempt.json',{'started_at_utc':now(),'policy':POLICY,'native_jobs':0,'fits':0})
    failures=[]; jobs=[]
    def owned(stage,index=None):
        folder=output/'raw'/('verification' if stage=='verify' else stage+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True); log=folder/'worker.log'
        command=[sys.executable,str(Path(__file__).resolve()),'worker','--output',str(output),'--stage',stage]
        if index is not None: command += ['--index',str(index)]
        started=now(); process=None; error=None; code=None
        try:
            remaining=deadline-time.monotonic(); need(remaining>0,'Native total600s exhausted')
            with log.open('x') as stream:
                process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,cwd=ROOT)
                try: code=process.wait(timeout=min(180,remaining))
                except subprocess.TimeoutExpired: raise TimeoutError('Worker or whole native attempt deadline')
                need(code==0,'Worker failed; see '+str(log))
        except Exception as caught: error=repr(caught)
        finally:
            if process is not None:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
        record={'stage':stage,'index':index,'started_at_utc':started,'finished_at_utc':now(),
                'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
        write(folder/'worker.json',record); jobs.append(record)
        return record
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            feature_jobs=list(pool.map(lambda i:owned('feature',i),range(len(rows))))
        failures.extend(r for r in feature_jobs if r['error'])
        if failures: raise ValueError('Incomplete features; no label jobs permitted')
        records=[read(output/'raw/features'/str(i)/'result.json') for i in range(len(rows))]
        x=np.asarray([r['values'] for r in records]); zero=v5.original_zero(x)
        write(output/'features.json',{'columns':list(v6.columns()),'records':records})
        order=[*v6.mapping_indices(),*range(194,313)]
        ordered=x[:,order]; columns=[v6.columns()[i] for i in order]
        need(np.array_equal(ordered[:,:217],x[:,v6.mapping_indices()]),'217 prefix alignment differs')
        predictions={name:np.asarray(model.predict_features(ordered,columns,zero)).tolist() for name,model in models.items()}
        # The full-data217 control must reproduce the existing frozen base point.
        import predict as existing
        base,_=existing.predict(rows,x,'base')
        base_values=np.asarray([r['predicted_lut4'] for r in base])
        need(np.array_equal(base_values,np.asarray(predictions['mapping217'])),'Fullfit217 differs from existing base')
        write(output/'predictions.json',{'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows], 'models':predictions,'existing_base_exact_match':True})
        write(output/'point-freeze.json',{'frozen_at_utc':now(),'plan_sha256':sha(output/'plan.json'),
            'model_freeze_sha256':sha(output/'model-freeze.json'),'features_sha256':sha(output/'features.json'),
            'predictions_sha256':sha(output/'predictions.json'),'target_label_jobs':0,'fits':0,
            'pre_native_amendment_sha256':sha(output/'pre-native-amendment.json') if (output/'pre-native-amendment.json').exists() else None})
        verify=owned('verify'); failures.extend([verify] if verify['error'] else [])
        need(not failures,'Original RTL verification failed; no labels permitted')
        with ThreadPoolExecutor(max_workers=2) as pool:
            label_jobs=list(pool.map(lambda i:owned('label',i),range(len(rows))))
        failures.extend(r for r in label_jobs if r['error'])
        labels=[]
        for i,row in enumerate(rows):
            result=output/'raw/labels'/str(i)/'result.json'
            labels.append(read(result) if result.is_file() else {**row,'status':'failed','error':label_jobs[i]['error']})
        write(output/'labels.json',labels)
        if not failures: write(output/'metrics.json',metrics(rows,predictions,labels))
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
    finally:
        write(output/'completion.json',{'completed_at_utc':now(),'complete':not failures,
            'native_attempt_elapsed_seconds':time.monotonic()-began,'fits':0,'failures':failures,
            'native_worker_jobs':jobs,'policy':POLICY,
            'label_count':sum(r.get('status')=='complete' for r in read(output/'labels.json')) if (output/'labels.json').exists() else 0})
    return read(output/'completion.json')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['prepare','run','worker'])
    parser.add_argument('--output',type=Path,default=ROOT/'results/selection-validation')
    parser.add_argument('--models',type=Path,default=ROOT/'results/selection-stability')
    parser.add_argument('--stage',choices=['feature','verify','label']); parser.add_argument('--index',type=int)
    args=parser.parse_args(); output=args.output.resolve()
    if args.command=='prepare': result=prepare(output)
    elif args.command=='run': result=run(output,args.models.resolve())
    else: worker(output,args.stage,args.index); return
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
