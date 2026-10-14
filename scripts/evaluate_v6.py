#!/usr/bin/env python3
"""Staged, committed V6 calibration and test evaluation; never fit an estimator."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
import itertools
import random
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluate_v4 import aligned,utc
from evaluate_v5 import extended_metrics,validate_freeze as validate_v5

NEW_MODELS=('mapping_v6','router_v6')
OLD_MODELS=('sog_tuned','original_graph','dual_graph','dual_semantics','masterrtl_fixed','v4_frozen')
MODELS=NEW_MODELS+OLD_MODELS
SCOPES=('calibration','test')
ALPHA=.1
REPLICATES=10000
BOOTSTRAP_SEED=2026101443
VERIFICATION_SEEDS={'calibration':2026101520,'test':2026101521}

def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def record(path,base):
    import os
    path=Path(path).resolve()
    return {'path':os.path.relpath(path,base),'sha256':sha(path)}
def checked(entry,base):
    path=(Path(base)/entry['path']).resolve()
    if sha(path)!=entry['sha256']:raise ValueError(f'Frozen file differs: {path}')
    return path
def source_path(name):return ROOT/name if '/' in name else ROOT/'isaforge'/name
def checked_files(manifest,base):
    paths={}
    for entry in manifest['files']:
        path=checked(entry,base)
        if path in paths and paths[path]!=entry['sha256']:raise ValueError('Conflicting frozen file records')
        paths[path]=entry['sha256']
    return paths
def require_files(paths,required):
    if not {Path(p).resolve() for p in required}<=set(paths):raise ValueError('Manifest omits required frozen evidence')

def validate_inputs(root):
    root=Path(root).resolve();corpus=root/'corpus'
    from isaforge.v6_corpus import validate_inputs as replay_input_seal
    replay_input_seal(corpus,ROOT)
    seal=read(corpus/'input-seal.json')
    if (seal.get('schema')!='isaforge-v6-input-seal-v1' or seal.get('status')!='sealed-inputs-only'
            or seal.get('scope_counts')!={'calibration':192,'test':192}
            or seal.get('cross_cohort_component_count')!=0
            or seal.get('feature_columns_count')!=336 or seal.get('v5_identity_columns_count')!=313):
        raise ValueError('Complete sealed V6 input independence required')
    rows={};features={};groups={};all_formulas=set();all_components=set();strata=None
    global_map=seal['component_by_formula']
    for scope in SCOPES:
        directory=corpus/scope;freeze=read(directory/'freeze.json')
        if freeze.get('schema')!='isaforge-v6-input-freeze-v1' or freeze.get('status')!='sealed-inputs-only':
            raise ValueError('Unsealed input cohort')
        for name,key in [('candidates.json','candidate_sha256'),('features.json','features_sha256'),('components.json','components_sha256')]:
            if sha(directory/name)!=freeze[key]:raise ValueError('Changed V6 sealed input')
        if freeze['seal_sha256']!=sha(corpus/'input-seal.json'):raise ValueError('Input seal hash differs')
        for name,digest in freeze['source_sha256'].items():
            if sha(source_path(name))!=digest:raise ValueError('Input generation source differs')
        r=read(directory/'candidates.json');f=read(directory/'features.json');g=read(directory/'components.json')['component_by_formula']
        if len(r)!=192 or len({v['formula'] for v in r})!=192 or len({(v['benchmark'],v['candidate_id']) for v in r})!=192:
            raise ValueError('Expected192 unique formulas and identities per cohort')
        names=sorted({v['stratum'] for v in r})
        if len(names)!=8 or any(sum(v['stratum']==s for v in r)!=24 for s in names) or (strata is not None and names!=strata):
            raise ValueError('Expected identical eight strata with24 rows each')
        strata=names
        formulas={v['formula'] for v in r}
        if formulas&all_formulas or set(g)!=formulas or any(global_map.get(k)!=v for k,v in g.items()) or set(g.values())&all_components:
            raise ValueError('Cross-cohort formula/component leakage')
        component_strata={}
        for row in r:component_strata.setdefault(g[row['formula']],set()).add(row['stratum'])
        if any(len(v)!=1 for v in component_strata.values()):raise ValueError('Components may not cross strata')
        counts={s:len({g[v['formula']] for v in r if v['stratum']==s}) for s in strata}
        if any(n<8 for n in counts.values()) or seal['stratum_component_counts'][scope]!=counts:
            raise ValueError('At least eight complete components per scope/stratum required')
        if (len(f['columns'])!=336 or len(f['records'])!=192
                or [v['formula'] for v in f['records']]!=[v['formula'] for v in r]
                or f['columns']!=freeze['feature_columns']):raise ValueError('V6 feature schema/alignment differs')
        for entry in f['records']:
            values=np.asarray(entry['values'],dtype=float)
            if values.shape!=(336,) or not np.isfinite(values).all() or np.any(values<0) or list(values[:313])!=entry['v5_values']:
                raise ValueError('Invalid label-free feature channels')
        rows[scope],features[scope],groups[scope]=r,f,g
        all_formulas|=formulas;all_components|=set(g.values())
    if set(global_map)!=all_formulas:raise ValueError('Global component coverage differs')
    return rows,features,groups,seal

def validate_predictions(rows,predictions,*,margin='original'):
    aligned(rows,predictions,'predicted_lut4')
    keys=lambda values:[(r['benchmark'],r['candidate_id'],r['formula']) for r in values]
    if keys(rows)!=keys(predictions):raise ValueError('Prediction order differs')
    if margin!='original':
        for row in predictions:
            upper=row.get('upper_lut4')
            if margin is None:
                if upper is not None:raise ValueError('Unbounded/uncalibrated prediction must have null upper')
            elif (isinstance(upper,bool) or not isinstance(upper,(float,int)) or not math.isfinite(upper)
                    or upper!=row['predicted_lut4']+margin):raise ValueError('Upper bound disagrees with fixed margin')

def validate_uncertainty_metadata(predictions):
    for row in predictions:
        spread=row.get('tree_disagreement_lut4');outside=row.get('outside_training_feature_ranges')
        if (type(outside) is not int or not 0<=outside<=336
                or spread is not None and (isinstance(spread,bool) or not isinstance(spread,(float,int)) or not math.isfinite(spread) or spread<0)
                or not isinstance(row.get('uncertainty_scope'),str) or not row['uncertainty_scope']):
            raise ValueError('Invalid aligned tree-spread/domain metadata')

def validate_point_freeze(root):
    root=Path(root).resolve();manifest=read(root/'point-freeze.json')
    if (manifest.get('schema')!='isaforge-v6-point-freeze-v1' or set(manifest['models'])!=set(MODELS)
            or manifest.get('training_formula_count')!=1665 or manifest.get('new_estimator_fits')!=1
            or manifest.get('fresh_calibration_labels_read') is not False or manifest.get('fresh_test_labels_read') is not False
            or manifest.get('primary_comparison')!='mapping_v6 minus dual_graph'):raise ValueError('Incomplete V6 point freeze')
    files=checked_files(manifest,root);rows,features,groups,seal=validate_inputs(root)
    required=[root/'training-start.json',root/'corpus/input-seal.json',ROOT/'scripts/evaluate_v6.py',ROOT/'scripts/measure_v6.py',ROOT/'docs/v6-protocol.md']
    required += [root/'corpus'/s/n for s in SCOPES for n in ('candidates.json','features.json','components.json','freeze.json')]
    required += [root/'corpus'/n for n in ('acquisition-plan.json','consumed-manifest.json','consumed-features.json','acquisition-history.json','generation-rejections.json')]
    required += [root/'corpus'/n for n in seal['attempt_files_sha256']]
    required += [source_path(n) for n in seal['source_sha256']]
    required += [ROOT/r[key] for r in read(root/'corpus/consumed-manifest.json')['sources'] for key in ('path','freeze_path')]
    required += [ROOT/'results/2026-10-14-v5/feature-extraction.json',ROOT/'tests/test_evaluate_v6.py']
    require_files(files,required)
    old_freeze=checked(manifest['source_v5_freeze'],root);require_files(files,[old_freeze])
    old,_,_,_=validate_v5(old_freeze.parent)
    start=read(root/'training-start.json');split=read(old_freeze.parent/'split.json')
    if start['fit_indices']!=split['fit_indices'] or len(set(start['fit_indices']))!=1665:
        raise ValueError('New models must use exact original1665 fitting rows')
    if not utc(old['frozen_at_utc'])<=utc(start['started_at_utc'])<=utc(manifest['frozen_at_utc']):
        raise ValueError('Invalid V6 fitting chronology')
    for s in SCOPES:
        f=read(root/'corpus'/s/'freeze.json')
        if utc(f['frozen_at_utc'])>utc(manifest['frozen_at_utc']) or f['frozen_tool']!=manifest['frozen_tool']:
            raise ValueError('Input/tool chronology differs')
    from isaforge.area_model_v6 import source_hashes,columns,mapping_columns
    from isaforge.area_model import _versions
    if start['runtime_source_sha256']!=source_hashes() or start['versions']!=_versions():raise ValueError('V6 fitting runtime/environment changed')
    require_files(files,[source_path(n) for n in start['runtime_source_sha256']])
    if any(tuple(f['columns'])!=tuple(columns()) for f in features.values()):raise ValueError('Runtime feature schema differs')
    baseline_schema=read(checked(old['models']['dual_graph']['schema'],old_freeze.parent))
    expected_training={'fit_indices_sha256':hashlib.sha256(json.dumps(split['fit_indices'],separators=(',',':')).encode()).hexdigest(),
        'training_dataset_sha256':sha(old_freeze.parent/'development-data.json'),
        'development_features_sha256':sha(old_freeze.parent/'development-features.json'),'split_sha256':sha(old_freeze.parent/'split.json')}
    if (start.get('fit_indices_sha256')!=expected_training['fit_indices_sha256']
            or start.get('fresh_calibration_labels_read') is not False or start.get('fresh_test_labels_read') is not False
            or start.get('calibration_used_for_selection') is not False
            or start['full_estimator_parameters']!=baseline_schema['fitted_parameters']
            or start['primary_estimator_parameters']!=baseline_schema['fitted_parameters']):raise ValueError('Training selection/fit-index/parameter contract differs')
    predictions={}
    for name,entry in manifest['models'].items():
        artifact=checked(entry['artifact'],root);schema=read(checked(entry['schema'],root))
        if not utc(start['started_at_utc'])<=utc(entry['frozen_at_utc'])<=utc(manifest['frozen_at_utc']):
            raise ValueError('Point prediction timestamp outside freeze')
        if name in NEW_MODELS:
            if (schema['artifact_sha256']!=entry['artifact']['sha256'] or schema['training_formula_count']!=1665
                    or schema['runtime_source_sha256']!=start['runtime_source_sha256']
                    or schema['calibration'].get('status')!='uncalibrated' or schema['calibration']['upper_margin_lut4'] is not None
                    or schema['calibration'].get('alpha')!=ALPHA or schema['versions']!=start['versions']
                    or any(schema['training_provenance'].get(k)!=v for k,v in expected_training.items())
                    or schema['training_provenance'].get('fit_indices')!=split['fit_indices']
                    or schema['fitted_parameters']!=baseline_schema['fitted_parameters']
                    or tuple(schema['mapping_columns'])!=tuple(mapping_columns()) or len(schema['mapping_columns'])!=217
                    or schema['kind']!=name or schema['frozen_tool']!=manifest['frozen_tool']):
                raise ValueError('New point artifact/schema is not exact uncalibrated fit')
            semantic_source=None if name=='mapping_v6' else {k+'_sha256':old['models']['dual_semantics'][k]['sha256'] for k in ('artifact','schema')}
            if schema['semantic_source']!=semantic_source:raise ValueError('Router semantic source differs from unchanged V5 expert')
        else:
            for key in ('artifact','schema'):
                if checked(entry[key],root)!=checked(old['models'][name][key],old_freeze.parent) or entry[key]['sha256']!=old['models'][name][key]['sha256']:
                    raise ValueError('Old V5 controls changed')
        predictions[name]={}
        for scope in SCOPES:
            values=read(checked(entry[scope+'_predictions'],root))
            validate_predictions(rows[scope],values,margin=None if name in NEW_MODELS else 'original')
            if name in ('sog_tuned','original_graph','dual_graph','dual_semantics'):
                validate_predictions(rows[scope],values,margin=schema['calibration']['upper_margin_lut4'])
            if name in (*NEW_MODELS,'sog_tuned','original_graph','dual_graph','dual_semantics'):validate_uncertainty_metadata(values)
            predictions[name][scope]=values
    for scope in SCOPES:
        from isaforge.area_model_v6 import has_multiply
        for row,mapping,router,semantic in zip(rows[scope],predictions['mapping_v6'][scope],predictions['router_v6'][scope],predictions['dual_semantics'][scope]):
            routed=has_multiply(row['formula']);expected=semantic if routed else mapping
            if router['predicted_lut4']!=expected['predicted_lut4'] or router['routed_expert']!=('dual_semantics' if routed else 'mapping_v6'):
                raise ValueError('Router point differs from fixed syntax-selected expert')
    return manifest,rows,features,groups,predictions

def freeze_records(root,stage):
    root=Path(root).resolve();point=read(root/'point-freeze.json')
    records=[record(root/'point-freeze.json',root),*point['files']]
    for entry in point['models'].values():records.extend(entry[k] for k in ('artifact','schema','calibration_predictions','test_predictions'))
    if stage=='test':
        calibrated=read(root/'calibration-freeze.json');records.extend([record(root/'calibration-freeze.json',root),*calibrated['files']])
        for entry in calibrated['models'].values():records.extend(entry[k] for k in ('artifact','schema','calibration_predictions','test_predictions'))
    return records

def validate_review(root,scope,review):
    root=Path(root).resolve()
    if scope not in SCOPES:raise ValueError('Unknown label stage')
    validate_point_freeze(root)
    if scope=='test':validate_calibration_freeze(root)
    review=review if isinstance(review,dict) else read(review)
    path=root/('point-freeze.json' if scope=='calibration' else 'calibration-freeze.json')
    frozen=read(path)
    if (review.get('schema')!='isaforge-v6-label-review-v1' or review.get('scope')!=scope
            or review.get('approved_for_label_release') is not True or review.get('freeze_sha256')!=sha(path)
            or utc(review['reviewed_at_utc'])<utc(frozen['frozen_at_utc'])
            or not isinstance(review.get('freeze_commit'),str) or not re.fullmatch('[0-9a-f]{40}',review['freeze_commit'])):
        raise ValueError('Exact stage-specific parent approval required')
    for entry in freeze_records(root,scope):
        file=checked(entry,root)
        if not file.is_relative_to(ROOT):raise ValueError('Review evidence must be in repository')
        result=subprocess.run(['git','show',f"{review['freeze_commit']}:{file.relative_to(ROOT).as_posix()}"],cwd=ROOT,capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest()!=entry['sha256']:raise ValueError('Stage evidence not at approved commit')
    return review

def verification_source(formulas):
    """Exact original-source wrapper emitted by the unchanged audited helper."""
    from isaforge.rtl import generate_rtl
    outputs=', '.join(f'output wire [31:0] out_{i}' for i in range(len(formulas)))
    lines=[f'module verification_top(input wire [31:0] in0, in1, {outputs});']
    lines.extend(f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(formulas)))
    lines.append('endmodule');lines.extend(generate_rtl(f,f'candidate_{i}') for i,f in enumerate(formulas))
    return '\n'.join(lines)

def validate_verification_vectors(path,formula_count,seed):
    from isaforge.rtl import BOUNDARIES
    rng=random.Random(seed);expected=list(itertools.product(BOUNDARIES,repeat=2))
    expected.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048))
    lines=Path(path).read_text().splitlines()
    if len(lines)!=2148:raise ValueError('Verification vector count differs')
    for line,pair in zip(lines,expected):
        fields=line.split()
        if len(fields)!=formula_count+2 or any(re.fullmatch('[0-9a-f]{8}',v) is None for v in fields) or tuple(int(v,16) for v in fields[:2])!=pair:
            raise ValueError('Verification vector seed/shape differs')

def validate_archive(root,scope):
    directory=Path(root)/'corpus'/scope;manifest=read(directory/'raw-evidence.json');archive=directory/'raw-evidence.zip'
    if (manifest.get('schema')!='isaforge-v6-evidence-v1' or manifest.get('scope')!=scope
            or manifest.get('archive')!=archive.name or sha(archive)!=manifest['archive_sha256']
            or manifest['completion_sha256']!=sha(directory/'completion.json')):raise ValueError('Portable raw archive provenance differs')
    records={r['path']:r for r in manifest['files']}
    if len(records)!=len(manifest['files']):raise ValueError('Duplicate portable archive member')
    completion=read(directory/'completion.json');scratch=(Path(root)/completion['scratch_directory']).resolve()
    expected={p.relative_to(ROOT).as_posix() for p in scratch.rglob('*') if p.is_file() and not {'obj_dir','obj_dir_wrapv'}.intersection(p.parts)}
    if set(records)!=expected:raise ValueError('Portable archive omits retained raw evidence')
    prefix=f'generated/v6-measurements/{scope}/'
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(records):raise ValueError('Portable archive inventory differs')
        for name in names:
            p=Path(name);target=(ROOT/p).resolve()
            if p.is_absolute() or '..' in p.parts or '\\' in name or not name.startswith(prefix) or not target.is_relative_to((ROOT/prefix).resolve()) or not target.is_relative_to(ROOT):raise ValueError('Portable archive member escapes stage')
            data=z.read(name)
            if len(data)!=records[name]['size'] or hashlib.sha256(data).hexdigest()!=records[name]['sha256'] or sha(target)!=records[name]['sha256']:raise ValueError('Changed portable raw evidence')
    return manifest

def validate_measurements(root,scope):
    root=Path(root).resolve();directory=root/'corpus'/scope
    point,rows,_,groups,_=validate_point_freeze(root);release=read(directory/'label-release.json');done=read(directory/'completion.json')
    review=validate_review(root,scope,release['parent_review']);approval=directory/'label-approval.json'
    if (read(approval)!=review or sha(approval)!=release['review_sha256'] or release['scope']!=scope
            or release['freeze_sha256']!=review['freeze_sha256'] or release['freeze_commit']!=review['freeze_commit']
            or release['candidate_sha256']!=sha(directory/'candidates.json')
            or utc(release['released_at_utc'])<utc(review['reviewed_at_utc'])
            or release.get('authorized_after_parent_review') is not True or release.get('point_freeze_sha256')!=sha(root/'point-freeze.json')
            or done.get('complete') is not True or done.get('failures') or done.get('unique_formula_count')!=192
            or done.get('weighted_row_count')!=192 or done.get('release')!=release
            or done.get('scope')!=scope or done.get('legacy_measurements_reused') is not False
            or done.get('collector_sha256')!=sha(ROOT/'scripts/measure_v6.py')
            or done.get('original_rtl_only') is not True or done['tool']!=point['frozen_tool']['version']
            or done['tool_sha256']!=point['frozen_tool']['executable_sha256']):raise ValueError('Invalid completed post-approval measurement')
    if not re.fullmatch('attempt-[0-9]{4}',done['attempt']):raise ValueError('Invalid measurement attempt identity')
    attempt=directory/done['attempt'];scratch=(root/done['scratch_directory']).resolve()
    if not attempt.resolve().is_relative_to(directory) or not scratch.is_relative_to(ROOT/'generated/v6-measurements'/scope):raise ValueError('Invalid owned measurement path')
    if scratch.name!=done['attempt'] or read(attempt/'completion.json')!=done:raise ValueError('Attempt completion differs from stage completion')
    for name,key in [('dataset.json','dataset_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:
        if sha(attempt/name)!=done[key]:raise ValueError('Changed retained measurement')
    if not utc(release['released_at_utc'])<=utc(done['completed_at_utc']):raise ValueError('Completion precedes stage release')
    proofs=read(attempt/'verification.json');count=0;formulas=sorted(r['formula'] for r in rows[scope])
    if len(proofs)!=2 or [p['formula_count'] for p in proofs]!=[128,64]:raise ValueError('Exact128/64 verification batches required')
    for index,proof in enumerate(proofs):
        if (proof.get('verified') is not True or proof['vectors_per_formula']!=2148
                or proof['total_comparisons']!=proof['formula_count']*2148 or proof['random_seed']!=VERIFICATION_SEEDS[scope]):raise ValueError('Incomplete original RTL verification')
        folder=scratch/'verification'/f'batch-{index*128:04d}'
        if sha(folder/'verification.v')!=proof['rtl_sha256'] or sha(folder/'vectors.txt')!=proof['vectors_sha256']:raise ValueError('Changed verification bytes')
        if (folder/'verification.v').read_text()!=verification_source(formulas[index*128:index*128+proof['formula_count']]):raise ValueError('Verification batch formulas differ from frozen originals')
        validate_verification_vectors(folder/'vectors.txt',proof['formula_count'],VERIFICATION_SEEDS[scope])
        if proof['v4_validation_override_sha256']!=sha(ROOT/'isaforge/v4_validation.py'):raise ValueError('Verification source differs')
        if proof.get('signed_overflow_workaround_applied') and sha(folder/'yosys-boundary-cross-check/eval.log')!=proof['independent_yosys_log_sha256']:raise ValueError('Changed wrap incident evidence')
        count+=proof['formula_count']
    if count!=192:raise ValueError('Incomplete192 formula verification')
    unique=read(attempt/'unique-measurements.json');by_formula={r['formula']:r for r in unique}
    if len(unique)!=192 or set(by_formula)!={r['formula'] for r in rows[scope]}:raise ValueError('Incomplete unique original targets')
    from isaforge.rtl import generate_rtl
    for formula,metric in by_formula.items():
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        if (read(folder/'metrics.json')!=metric or metric['rtl_sha256']!=hashlib.sha256(generate_rtl(formula).encode()).hexdigest()
                or metric['tool']!=done['tool'] or metric['tool_sha256']!=done['tool_sha256'] or metric.get('measurement_source')!='rtl_synthesis'
                or not utc(release['released_at_utc'])<=utc(metric['measured_at_utc'])<=utc(done['completed_at_utc'])):raise ValueError('Changed original-circuit target provenance')
        for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]:
            if sha(folder/name)!=metric[key]:raise ValueError('Changed physical synthesis evidence')
    labels=read(attempt/'dataset.json');y=aligned(rows[scope],labels,'lut4_count',measured=True)
    for label in labels:
        metric=by_formula[label['formula']]
        if label['lut4_count']!=metric['ice40_lut4_count'] or label['carry_count']!=metric['ice40_carry_count'] or label['rtl_sha256']!=metric['rtl_sha256'] or label['synthesis_tool']!=done['tool']:raise ValueError('Expanded label differs from original target')
    validate_archive(root,scope)
    return labels,y,done

def group_upper_margin(y,p,groups):
    y,p=np.asarray(y,dtype=float),np.asarray(p,dtype=float);groups=list(groups)
    if y.ndim!=1 or y.shape!=p.shape or len(y)!=len(groups) or not len(y) or not np.isfinite(y).all() or not np.isfinite(p).all():raise ValueError('Aligned finite complete calibration groups required')
    unique=sorted(set(groups));scores=[max(float(y[i]-p[i]) for i,g in enumerate(groups) if g==group) for group in unique]
    rank=math.ceil((len(unique)+1)*(1-ALPHA));margin=None if rank>len(unique) else max(0.,sorted(scores)[rank-1])
    return {'status':'calibrated','alpha':ALPHA,'group_count':len(unique),'rank':rank,'upper_margin_lut4':margin,
            'method':'one-sided maximum residual per complete calibration component; fixed zero lower clamp',
            'assumption':'exchangeable complete calibration/test components; no guarantee under application or grammar shift'}

def calibrate(root):
    root=Path(root).resolve()
    if (root/'calibration-freeze.json').exists() or (root/'corpus/test/label-release.json').exists() or (root/'corpus/test/completion.json').exists():raise ValueError('Calibration freeze is immutable and must precede test release')
    point,rows,features,groups,predictions=validate_point_freeze(root);_,y,done=validate_measurements(root,'calibration')
    from isaforge.area_model_v6 import load_model,save_model
    entries={};started=now()
    for name in NEW_MODELS:
        p=aligned(rows['calibration'],predictions[name]['calibration'],'predicted_lut4')
        calibration=group_upper_margin(y,p,[groups['calibration'][r['formula']] for r in rows['calibration']])
        model=copy.deepcopy(load_model(checked(point['models'][name]['artifact'],root)))
        model.calibration=calibration
        saved=save_model(model,root/'calibrated-models'/f'{name}.joblib')
        entry={k:record(saved[k],root) for k in ('artifact','schema')}
        for scope in SCOPES:
            values=model.predict_features(rows[scope],np.asarray([r['values'] for r in features[scope]['records']]))
            actual=aligned(rows[scope],values,'predicted_lut4');original=aligned(rows[scope],predictions[name][scope],'predicted_lut4')
            if not np.array_equal(actual,original):raise ValueError('Calibration changed a frozen point prediction')
            validate_predictions(rows[scope],values,margin=calibration['upper_margin_lut4'])
            path=root/'calibrated-predictions'/f'{name}-{scope}.json';write(path,values);entry[scope+'_predictions']=record(path,root)
        entry.update(calibration=calibration,frozen_at_utc=now());entries[name]=entry
    directory=root/'corpus/calibration';attempt=directory/done['attempt']
    files=[root/'point-freeze.json',directory/'label-release.json',directory/'label-approval.json',directory/'completion.json',
           *(attempt/n for n in ('completion.json','dataset.json','unique-measurements.json','verification.json')),
           directory/'raw-evidence.json',directory/'raw-evidence.zip',ROOT/'scripts/evaluate_v6.py',ROOT/'scripts/measure_v6.py']
    manifest={'schema':'isaforge-v6-calibration-freeze-v1','started_at_utc':started,'frozen_at_utc':now(),
              'point_freeze':record(root/'point-freeze.json',root),'models':entries,'files':[record(p,root) for p in files],
              'calibration_dataset_sha256':done['dataset_sha256'],'test_labels_read':False,'new_fits':0,
              'alpha':ALPHA,'zero_margin_policy':'max(0,ranked complete-component maximum residual)'}
    write(root/'calibration-freeze.json',manifest);validate_calibration_freeze(root);return manifest

def validate_calibration_freeze(root):
    root=Path(root).resolve();point,rows,_,groups,predictions=validate_point_freeze(root);manifest=read(root/'calibration-freeze.json')
    if (manifest.get('schema')!='isaforge-v6-calibration-freeze-v1' or set(manifest['models'])!=set(NEW_MODELS)
            or manifest.get('new_fits')!=0 or manifest.get('test_labels_read') is not False or manifest.get('alpha')!=ALPHA
            or checked(manifest['point_freeze'],root)!=root/'point-freeze.json'):raise ValueError('Invalid independent calibration freeze')
    files=checked_files(manifest,root)
    require_files(files,[root/'point-freeze.json',root/'corpus/calibration/completion.json',root/'corpus/calibration/label-release.json',root/'corpus/calibration/label-approval.json',root/'corpus/calibration/raw-evidence.json',root/'corpus/calibration/raw-evidence.zip',ROOT/'scripts/evaluate_v6.py',ROOT/'scripts/measure_v6.py'])
    _,y,done=validate_measurements(root,'calibration')
    require_files(files,[root/'corpus/calibration'/done['attempt']/name for name in ('completion.json','dataset.json','unique-measurements.json','verification.json')])
    if manifest.get('zero_margin_policy')!='max(0,ranked complete-component maximum residual)':raise ValueError('Fixed zero-margin policy differs')
    if manifest['calibration_dataset_sha256']!=done['dataset_sha256'] or not utc(read(root/'corpus/calibration/label-release.json')['released_at_utc'])<=utc(manifest['started_at_utc'])<=utc(manifest['frozen_at_utc']):raise ValueError('Calibration lineage/chronology differs')
    upper_predictions={}
    for name,entry in manifest['models'].items():
        expected=group_upper_margin(y,aligned(rows['calibration'],predictions[name]['calibration'],'predicted_lut4'),[groups['calibration'][r['formula']] for r in rows['calibration']])
        schema=read(checked(entry['schema'],root));checked(entry['artifact'],root)
        if entry['calibration']!=expected or schema['calibration']!=expected or schema['artifact_sha256']!=entry['artifact']['sha256']:raise ValueError('Calibration artifact/margin disagreement')
        if not utc(manifest['started_at_utc'])<=utc(entry['frozen_at_utc'])<=utc(manifest['frozen_at_utc']):raise ValueError('Calibrated prediction outside stage freeze')
        original_schema=read(checked(point['models'][name]['schema'],root))
        for key in set(original_schema)-{'artifact_sha256','calibration'}:
            if schema.get(key)!=original_schema[key]:raise ValueError('Calibration changed fitted model schema')
        upper_predictions[name]={}
        for scope in SCOPES:
            values=read(checked(entry[scope+'_predictions'],root));validate_predictions(rows[scope],values,margin=expected['upper_margin_lut4'])
            validate_uncertainty_metadata(values)
            if not np.array_equal(aligned(rows[scope],values,'predicted_lut4'),aligned(rows[scope],predictions[name][scope],'predicted_lut4')):raise ValueError('Calibrated point changed')
            for value,original in zip(values,predictions[name][scope]):
                for key in ('tree_disagreement_lut4','outside_training_feature_ranges','routed_expert'):
                    if value[key]!=original[key]:raise ValueError('Calibration changed frozen point diagnostics or routing')
            upper_predictions[name][scope]=values
    return manifest,upper_predictions

def paired_stratified_components(difference,strata,components,replicates=REPLICATES):
    d=np.asarray(difference,dtype=float);s=np.asarray(strata);g=np.asarray(components)
    if d.ndim!=1 or d.shape!=s.shape or d.shape!=g.shape or not np.isfinite(d).all() or isinstance(replicates,bool) or not isinstance(replicates,int) or replicates<1:raise ValueError('Aligned finite paired component arrays required')
    names=sorted(set(s));component_strata={group:set(s[g==group]) for group in set(g)}
    if len(names)!=8 or any(len(v)!=1 for v in component_strata.values()):raise ValueError('Eight strata with noncrossing components required')
    rng=np.random.default_rng(BOOTSTRAP_SEED);samples=np.zeros(replicates);counts={};sizes={}
    for name in names:
        unique=sorted(set(g[s==name]));counts[name]=len(unique)
        if len(unique)<8:raise ValueError('At least eight components per stratum required')
        sums=np.asarray([d[g==group].sum() for group in unique]);n=np.asarray([np.sum(g==group) for group in unique]);sizes[name]={str(group):int(size) for group,size in zip(unique,n)}
        draws=rng.integers(0,len(unique),size=(replicates,len(unique)))
        samples+=(sums[draws].sum(axis=1)/n[draws].sum(axis=1))/len(names)
    return {'macro_stratum_mae_difference_lut4':float(np.mean([d[s==name].mean() for name in names])),
            'descriptive_stratified_component_bootstrap_95_interval':np.quantile(samples,[.025,.975]).tolist(),
            'replicates':replicates,'seed':BOOTSTRAP_SEED,'component_counts_by_stratum':counts,'component_sizes_by_stratum':sizes,
            'empty_draw_rejection':False,'scope':'Descriptive paired whole-component resampling within eight fixed strata; conditional on synthetic grammar, not a population guarantee.'}

def model_metrics(rows,y,predictions,components):
    p=aligned(rows,predictions,'predicted_lut4');strata=np.asarray([r['stratum'] for r in rows]);names=sorted(set(strata))
    groups=np.asarray([components[r['formula']] for r in rows])
    result={**extended_metrics(y,p),'by_stratum':{name:extended_metrics(y[strata==name],p[strata==name]) for name in names}}
    result['by_component']={str(group):extended_metrics(y[groups==group],p[groups==group]) for group in sorted(set(groups))}
    result['macro_stratum_mae_lut4']=float(np.mean([v['mae_lut4'] for v in result['by_stratum'].values()]))
    if all('upper_lut4' in row for row in predictions):
        upper=np.asarray([np.inf if row['upper_lut4'] is None else row['upper_lut4'] for row in predictions],dtype=float);finite=np.isfinite(upper);covered=y<=upper
        def bound_cell(mask):
            selected=set(groups[mask]);slack=(upper-y)[mask];valid=finite[mask]
            return {'candidate_coverage':float(covered[mask].mean()),'whole_component_coverage':float(np.mean([covered[groups==g].all() for g in selected])),
                'component_count':len(selected),'finite_bound_fraction':float(valid.mean()),'mean_slack_lut4':float(slack.mean()) if valid.all() else None,
                'minimum_slack_lut4':float(slack.min()) if valid.all() else None,
                'finite_bounds_mean_slack_lut4':float(slack[valid].mean()) if valid.any() else None,
                'cap_decisions':{str(cap):{'false_accept_count':int(np.sum(mask & (upper<=cap) & (y>cap))),
                    'false_reject_count':int(np.sum(mask & (upper>cap) & (y<=cap))),
                    'true_infeasible_count':int(np.sum(mask & (y>cap))),'true_feasible_count':int(np.sum(mask & (y<=cap))),
                    'predicted_feasible_count':int(np.sum(mask & (upper<=cap)))} for cap in (16,32,64,128,256)}}
        result['upper_bound']={**bound_cell(np.ones(len(rows),dtype=bool)),
            'by_stratum':{name:bound_cell(strata==name) for name in names},'scope':'Observed complete synthetic components; exchangeability outside this grammar is unestablished.'}
    if all('outside_training_feature_ranges' in r and 'tree_disagreement_lut4' in r for r in predictions):
        outside=np.asarray([r['outside_training_feature_ranges'] for r in predictions]);spread=[r['tree_disagreement_lut4'] for r in predictions]
        def domain_cell(mask):
            sd=np.asarray([v for v,keep in zip(spread,mask) if keep and v is not None],dtype=float)
            return {'row_count':int(mask.sum()),'outside_training_range_row_count':int(np.sum(outside[mask]>0)),
                'outside_training_range_dimension_sum':int(outside[mask].sum()),'outside_training_range_dimensions_max':int(outside[mask].max()),
                'tree_spread_available_count':len(sd),'mean_tree_spread_lut4':float(sd.mean()) if len(sd) else None,
                'p95_tree_spread_lut4':float(np.quantile(sd,.95)) if len(sd) else None,'maximum_tree_spread_lut4':float(sd.max()) if len(sd) else None}
        result['tree_spread_and_domain']={'all':domain_cell(np.ones(len(rows),dtype=bool)),'by_stratum':{name:domain_cell(strata==name) for name in names},
            'scope':'Tree spread and feature-range counts are descriptive; neither is a coverage guarantee.'}
    result['candidate_errors']=[{**row,'lut4_count':float(target),'predicted_lut4':float(estimate),'absolute_error_lut4':float(abs(estimate-target))} for row,target,estimate in zip(rows,y,p)]
    return result

def evaluate(root):
    root=Path(root).resolve();point,rows,_,groups,predictions=validate_point_freeze(root);calibration,upper=validate_calibration_freeze(root)
    _,y,done=validate_measurements(root,'test')
    for name in NEW_MODELS:predictions[name]=upper[name]
    models={name:model_metrics(rows['test'],y,values['test'],groups['test']) for name,values in predictions.items()}
    p=aligned(rows['test'],predictions['mapping_v6']['test'],'predicted_lut4');baseline=aligned(rows['test'],predictions['dual_graph']['test'],'predicted_lut4')
    paired=paired_stratified_components(abs(p-y)-abs(baseline-y),[r['stratum'] for r in rows['test']],[groups['test'][r['formula']] for r in rows['test']])
    return {'schema':'isaforge-v6-evaluation-v1','evaluated_at_utc':now(),'point_freeze_sha256':sha(root/'point-freeze.json'),
            'calibration_freeze_sha256':sha(root/'calibration-freeze.json'),'test_dataset_sha256':done['dataset_sha256'],
            'primary':'Eight-stratum macro MAE, mapping_v6 minus unchanged dual_graph','models':models,'primary_paired_comparison':paired,
            'limits':['Fresh synthetic shape validation after development; conditional on frozen grammar and strata, no CPU/application population claim.',
                      'Old control bounds retain their original V5 calibration; only mapping_v6/router_v6 use fresh calibration components.',
                      'Router margin calibrates its final composite points. No model fitting, tuning or data replacement after fresh labels.']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('validate','calibrate','score'));parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v6');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='validate':result={'point_freeze':validate_point_freeze(args.root)[0]['frozen_at_utc']}
    elif args.action=='calibrate':result=calibrate(args.root)
    else:
        if args.output is None:parser.error('score requires --output')
        result=evaluate(args.root);write(args.output,result)
    print(json.dumps(result if args.action!='score' else result['primary_paired_comparison'],indent=2))
if __name__=='__main__':main()
