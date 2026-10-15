#!/usr/bin/env python3
"""Reviewed, committed V8 original-RTL target collection; NEVER run before approval.

Reuses frozen OwnedWorkers/run_owned isolation and wrapping verification. All
formulas are original canonical RTL; no old label cache or normalized target.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from measure_v6 import OwnedWorkers,run_owned
from isaforge import area_model_v8 as v8
from isaforge.features import parse_formula
from isaforge.rtl import generate_rtl
from evaluate_v8_applications import MODELS

PREFIX='generated/v8-measurements/'
VERIFY_SEED=2026101517
UNIQUE_COUNT=146
ROW_COUNT=152


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def utc(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None:raise ValueError('Timezone-aware stage timestamp required')
    return result

def checked(record,base):
    path=(Path(base)/record['path']).resolve()
    if not path.is_file() or sha(path)!=record['sha256']:raise ValueError('Changed freeze evidence: '+record['path'])
    return path

def member_name(name):
    path=PurePosixPath(name)
    if path.is_absolute() or not path.parts or '..' in path.parts or '\\' in name or str(path)!=name:raise ValueError('Unsafe evidence archive member')
    return name


def verify_archive_manifest(path):
    """Common flat manifest contract: archive{path,sha256}, files{path,sha256,bytes|size}."""
    path=Path(path).resolve();manifest=read(path);entry=manifest['archive']
    if isinstance(entry,str):entry={'path':entry,'sha256':manifest['archive_sha256']}
    archive=(path.parent/entry['path']).resolve()
    if not archive.is_relative_to(ROOT) or sha(archive)!=entry['sha256']:raise ValueError('Archive identity differs')
    records={r['path']:r for r in manifest['files']}
    if not records or len(records)!=len(manifest['files']):raise ValueError('Nonempty unique archived members required')
    for name in records:member_name(name)
    observed=set()
    def verify(name,data,size):
        member_name(name)
        if name in observed or name not in records:raise ValueError('Archive membership differs')
        observed.add(name);record=records[name];expected=record.get('bytes',record.get('size'))
        if type(expected) is not int or expected!=size or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Archived member bytes differ')
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as stream:
            for info in stream.infolist():
                if info.is_dir() or ((info.external_attr>>16)&0o170000)==0o120000:raise ValueError('Archive directories/links are forbidden')
                verify(info.filename,stream.read(info),info.file_size)
    else:
        with tarfile.open(archive,'r:*') as stream:
            for info in stream:
                if not info.isfile():raise ValueError('Archive special member forbidden')
                data=stream.extractfile(info).read();verify(info.name,data,info.size)
    if observed!=set(records):raise ValueError('Archive coverage differs')
    return archive


def freeze_records(root):
    root=Path(root).resolve();point_path=root/'point-freeze.json';input_path=root/'input-seal.json'
    point,inputs=read(point_path),read(input_path)
    if (point.get('schema')!='isaforge-v8-application-points-v1' or point.get('new_estimator_fits')!=2
        or point.get('application_rows')!=ROW_COUNT or point.get('unique_original_formulas')!=UNIQUE_COUNT
        or point.get('fresh_application_labels_read') is not False or point.get('point_only') is not True
        or point.get('primary_comparison')!='legacy_rewritten336 minus mapping_v6' or set(point['models'])!=set(MODELS)
        or inputs.get('status')!='sealed-inputs-only' or inputs.get('runtime_source_sha256')!=v8.source_hashes()):
        raise ValueError('Exact complete source-bound input/point freeze required')
    records=[{'path':'point-freeze.json','sha256':sha(point_path)},{'path':'input-seal.json','sha256':sha(input_path)},*point['files'],*inputs['files']]
    for entry in point['models'].values():records.extend(entry[k] for k in ('artifact','schema','predictions'))
    unique={}
    for entry in records:
        path=checked(entry,root)
        if path in unique and unique[path]!=entry['sha256']:raise ValueError('Conflicting freeze file digests')
        unique[path]=entry['sha256']
    required=[root/'rows.json',root/'features.json',root/'programs.json',root/'novelty.json',root/'training-start.json',Path(__file__).resolve(),
        ROOT/'scripts/evaluate_v8_applications.py',ROOT/'scripts/measure_v6.py',ROOT/'scripts/evaluate_v6.py',
        ROOT/'isaforge/v4_corpus.py',ROOT/'isaforge/v4_validation.py',ROOT/'isaforge/rtl.py',ROOT/'docs/v8-application-pilot-protocol.md',
        *(ROOT/'isaforge'/name for name in v8.source_hashes())]
    if any(path.resolve() not in unique for path in required):raise ValueError('Required sources/input evidence missing from freeze')
    rows=read(root/'rows.json');features=read(root/'features.json')
    formulas=[parse_formula(r['formula']).canonical() for r in rows]
    if len(rows)!=ROW_COUNT or len(set(formulas))!=UNIQUE_COUNT or any(r['formula']!=f for r,f in zip(rows,formulas)):
        raise ValueError('Exact152 application rows/146 canonical originals required')
    if len({(r['benchmark'],r['candidate_id']) for r in rows})!=ROW_COUNT:raise ValueError('Duplicate application identity')
    if tuple(features['columns'])!=v8.columns() or len(features['records'])!=UNIQUE_COUNT or {r['formula'] for r in features['records']}!=set(formulas):
        raise ValueError('Complete full455 input features required')
    for row in features['records']:
        values=row['values']
        if len(values)!=455 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values):raise ValueError('Invalid frozen full455 values')
    programs=read(root/'programs.json');declared={p['benchmark']:p for p in programs}
    if len(declared)!=5 or len(programs)!=5 or set(declared)!={r['benchmark'] for r in rows}:raise ValueError('Complete declared five-program pools required')
    if sum(type(r.get('primary_family')) is bool and r['primary_family'] for r in rows)!=150:raise ValueError('Exact150 primary rows required')
    for row in rows:
        program=declared[row['benchmark']]
        if (type(row.get('primary_family')) is not bool or type(row.get('traceTotalInstructions')) is not int or row['traceTotalInstructions']<=0
            or any(row[k]!=program[k] for k in ('family','primary_family','traceTotalInstructions'))
            or any(type(row.get(k)) is not int or not 0<=row[k]<=row['traceTotalInstructions'] for k in ('runs','overlapSafeSaved'))):
            raise ValueError('Frozen application roles/counts/trace denominators differ')
    start=read(root/'training-start.json')
    if (start.get('runtime_source_sha256')!=v8.source_hashes() or start.get('fresh_application_labels_read') is not False
        or start.get('mapping_control_refitted') is not False or start.get('maximum_fits')!=2
        or start.get('configuration')!=v8.FIXED_PARAMETERS or utc(start['started_at_utc'])>utc(point['frozen_at_utc'])):
        raise ValueError('Fixed fitting/source/point chronology differs')
    old_root=ROOT/'results/2026-10-14-v5';prior_root=ROOT/'results/2026-10-14-v6'
    for origin in (old_root/'freeze.json',prior_root/'point-freeze.json',old_root/'split.json',old_root/'development-data.json',old_root/'development-features.json'):
        if origin not in unique:raise ValueError('Original control/training provenance source missing from flat freeze')
    old=read(old_root/'freeze.json');prior=read(prior_root/'point-freeze.json');split=read(old_root/'split.json')
    expected_provenance={'fit_indices':split['fit_indices'],
        'fit_indices_sha256':hashlib.sha256(json.dumps(split['fit_indices'],separators=(',',':')).encode()).hexdigest(),
        'training_dataset_sha256':sha(old_root/'development-data.json'),'development_dataset_sha256':sha(old_root/'development-data.json'),
        'development_features_sha256':sha(old_root/'development-features.json'),'split_sha256':sha(old_root/'split.json')}
    for name,entry in point['models'].items():
        schema=read(checked(entry['schema'],root))
        if schema.get('artifact_sha256')!=entry['artifact']['sha256'] or schema.get('training_formula_count')!=1665:raise ValueError('Artifact/schema training identity differs')
        if name in v8.TRAINED_VIEWS:
            if (set(schema)!=v8.SCHEMA_FIELDS or schema['view']!=name or schema['schema']!=v8.SCHEMA or schema['feature_schema']!=v8.FEATURE_SCHEMA
                or schema['feature_columns']!=list(v8.columns()) or schema['selected_columns']!=list(v8.view_columns(name))
                or schema['selected_indices']!=v8.view_indices(name).tolist() or schema['runtime_source_sha256']!=v8.source_hashes()
                or schema['configuration']!=v8.FIXED_PARAMETERS or schema['fitted_parameters']!=v8.ExtraTreesRegressor(**v8.FIXED_PARAMETERS).get_params()
                or schema['training_provenance']!=expected_provenance or schema['frozen_tool']!=inputs['frozen_tool']
                or schema['point_only'] is not True or schema['upper_margin_lut4'] is not None):raise ValueError('New legacy point schema/recipe/provenance differs')
        else:
            origin_root,origin=(prior_root,prior['models']['mapping_v6']) if name=='mapping_v6' else (old_root,old['models'][name])
            if any(checked(entry[k],root)!=checked(origin[k],origin_root) or entry[k]['sha256']!=origin[k]['sha256'] for k in ('artifact','schema')):
                raise ValueError('Existing fixed control artifact/schema changed')
        predictions=read(checked(entry['predictions'],root));seen={}
        if len(predictions)!=len(rows):raise ValueError('Incomplete point coverage')
        for row,p in zip(rows,predictions):
            value=p.get('predicted_lut4')
            if (any(row[k]!=p.get(k) for k in ('benchmark','candidate_id','formula')) or type(value) not in (int,float)
                or not math.isfinite(value) or value<0 or p.get('upper_lut4') is not None):raise ValueError('Invalid aligned point-only predictions')
            if row['formula'] in seen and seen[row['formula']]!=value:raise ValueError('Shared original formula point differs')
            seen[row['formula']]=value
    archives=[*inputs.get('archive_manifests',[]),*point.get('archive_manifests',[])]
    if not archives:raise ValueError('Committed archive member manifests required before label release')
    for entry in archives:
        manifest_path=checked(entry,root)
        if manifest_path not in unique:raise ValueError('Archive manifest not bound in freeze files')
        archive=verify_archive_manifest(manifest_path)
        if archive not in unique:raise ValueError('Archive file not bound in freeze files')
    return point,inputs,rows,unique


def validate_approval(root,path):
    root,path=Path(root).resolve(),Path(path).resolve()
    if path!=root/'label-approval.json':raise ValueError('Keep exact parent approval at root/label-approval.json')
    point,inputs,rows,files=freeze_records(root);review=read(path)
    if (review.get('schema')!='isaforge-v8-application-label-approval-v1' or review.get('approved_for_label_release') is not True
        or review.get('point_freeze_sha256')!=sha(root/'point-freeze.json') or review.get('input_seal_sha256')!=sha(root/'input-seal.json')
        or not isinstance(review.get('freeze_commit'),str) or not re.fullmatch('[0-9a-f]{40}',review['freeze_commit'])
        or utc(review['reviewed_at_utc'])<utc(point['frozen_at_utc'])):raise ValueError('Exact committed parent label approval required')
    for file,digest in files.items():
        if not file.is_relative_to(ROOT):raise ValueError('All approved flat evidence must be in the repository')
        result=subprocess.run(['git','show',review['freeze_commit']+':'+file.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest()!=digest:raise ValueError('Approved freeze evidence differs from committed bytes')
    return point,inputs,rows,review


def collect(root,approval,*,workers=2,attempt='attempt-0000'):
    root=Path(root).resolve()
    if type(workers) is not int or workers!=2 or not re.fullmatch('attempt-[0-9]{4}',attempt):raise ValueError('Fixed two workers and explicit owned attempt required')
    if (root/'measurements/completion.json').exists() and read(root/'measurements/completion.json').get('complete') is True:raise ValueError('Completed measurements are immutable')
    point,inputs,rows,review=validate_approval(root,approval)
    output=root/'measurements'/attempt;scratch=ROOT/PREFIX/attempt
    if output.exists() or scratch.exists():raise ValueError('Fresh measurement attempt required; never reuse prior labels')
    tool=inputs['frozen_tool'];executable=shutil.which('yosys')
    if executable is None:raise RuntimeError('Frozen Yosys target tool required')
    version=subprocess.check_output([executable,'-V'],text=True).strip()
    if version!=tool['version'] or sha(executable)!=tool['executable_sha256']:raise ValueError('Native target tool version/binary differs')
    release={'schema':'isaforge-v8-application-label-release-v1','point_freeze_sha256':sha(root/'point-freeze.json'),
        'input_seal_sha256':sha(root/'input-seal.json'),'approval_sha256':sha(approval),'freeze_commit':review['freeze_commit'],
        'collector_sha256':sha(__file__),'verification_seed':VERIFY_SEED,'vectors_per_formula':2148,'workers':workers}
    release_path=root/'label-release.json'
    if release_path.exists():
        old=read(release_path)
        if any(old.get(k)!=v for k,v in release.items()):raise ValueError('Existing label release differs')
    else:write(release_path,{**release,'released_at_utc':now()})
    output.mkdir(parents=True);scratch.mkdir(parents=True)
    formulas=sorted({r['formula'] for r in rows});owner=OwnedWorkers();failures=[];proofs=[];measured={};interruption=None
    for offset in range(0,len(formulas),128):
        batch=formulas[offset:offset+128]
        try:
            proof=run_owned({'kind':'verify','formulas':batch,'folder':str(scratch/'verification'/f'batch-{offset:04d}'),'seed':VERIFY_SEED},scratch/f'verification-{offset:04d}-worker.log',owner)
            if (proof.get('verified') is not True or proof.get('formula_count')!=len(batch) or proof.get('vectors_per_formula')!=2148
                or proof.get('total_comparisons')!=2148*len(batch)):raise ValueError('Incomplete original RTL verification')
            proofs.append(proof)
        except BaseException as error:
            failures.append({'stage':'verification','batch_start':offset,'error':repr(error)})
            if not isinstance(error,Exception):owner.cancel();interruption=error
            break
    write(output/'verification.json',proofs)
    def measure(formula):
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        if folder.exists():raise ValueError('Fresh target circuit directory required')
        metric=run_owned({'kind':'map','formula':formula,'folder':str(folder),'executable':executable,'version':version},folder/'worker.log',owner)
        metric['tool_sha256']=tool['executable_sha256']
        if metric.get('formula')!=formula or metric['rtl_sha256']!=hashlib.sha256(generate_rtl(formula).encode()).hexdigest():raise ValueError('Mapped original RTL identity differs')
        for key in ('ice40_lut4_count','ice40_carry_count'):
            if type(metric[key]) is not int or metric[key]<0:raise ValueError('Nonnegative integer mapped resources required')
        write(folder/'metrics.json',metric);return metric
    if not failures:
        pool=ThreadPoolExecutor(max_workers=workers)
        try:
            futures={pool.submit(measure,f):f for f in formulas}
            for future in as_completed(futures):
                formula=futures[future]
                try:measured[formula]=future.result()
                except Exception as error:failures.append({'stage':'synthesis','formula':formula,'error':repr(error)})
                write(output/'progress.json',{'unique_completed':len(measured),'unique_total':UNIQUE_COUNT,'failures':failures})
        except BaseException as error:
            owner.cancel();interruption=error;failures.append({'stage':'cancellation','error':repr(error)})
        finally:pool.shutdown(wait=True,cancel_futures=True)
    unique=[measured[f] for f in formulas if f in measured]
    labels=[{'formula':f,'lut4_count':measured[f]['ice40_lut4_count'],'carry_count':measured[f]['ice40_carry_count'],
        'rtl_sha256':measured[f]['rtl_sha256'],'measurement_source':'rtl_synthesis','correctness_verified':True} for f in formulas if f in measured]
    write(output/'unique-measurements.json',unique);write(output/'labels.json',labels)
    done={'schema':'isaforge-v8-application-measurements-v1','complete':not failures and len(labels)==UNIQUE_COUNT,'failures':failures,
        'attempt':attempt,'unique_original_formulas':len(labels),'application_rows':ROW_COUNT,'verification_seed':VERIFY_SEED,
        'vectors_per_formula':2148,'verification_batch_sizes':[len(formulas[i:i+128]) for i in range(0,len(formulas),128)],
        'labels_sha256':sha(output/'labels.json'),'unique_measurements_sha256':sha(output/'unique-measurements.json'),
        'verification_sha256':sha(output/'verification.json'),'collector_sha256':sha(__file__),'release_sha256':sha(release_path),
        'frozen_tool':tool,'original_rtl_only':True,'legacy_measurements_reused':False,'scratch_directory':scratch.relative_to(ROOT).as_posix(),
        'completed_at_utc':now()}
    write(output/'completion.json',done);write(root/'measurements/completion.json',done)
    if interruption is not None:raise interruption
    if not done['complete']:raise RuntimeError('Incomplete V8 measurements retained; complete scoring blocked')
    pack(root);return done


def destination(name,repository):
    member_name(name);repository=Path(repository).resolve();allowed=repository/PREFIX
    target=repository/name
    if not name.startswith(PREFIX) or not allowed.resolve().is_relative_to(repository) or not target.resolve().is_relative_to(allowed.resolve()):raise ValueError('Archive escapes owned V8 evidence directory')
    return target


def pack(root):
    root=Path(root).resolve();directory=root/'measurements';done=read(directory/'completion.json')
    if done.get('complete') is not True or done['failures']:raise ValueError('Only completed original measurements can be archived')
    scratch=(ROOT/done['scratch_directory']).resolve()
    if not scratch.is_relative_to(ROOT/PREFIX):raise ValueError('Unexpected scratch directory')
    archive=directory/'raw-evidence.zip';manifest=directory/'raw-evidence.json'
    if archive.exists() or manifest.exists():raise ValueError('Raw evidence archives are immutable')
    records=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as stream:
        for path in sorted(scratch.rglob('*')):
            if path.is_symlink():raise ValueError('Symlink native evidence forbidden')
            if not path.is_file() or {'obj_dir','obj_dir_wrapv'}.intersection(path.parts):continue
            name=path.relative_to(ROOT).as_posix();destination(name,ROOT);data=path.read_bytes()
            info=zipfile.ZipInfo(name,date_time=(2026,10,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            stream.writestr(info,data,compresslevel=9);records.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    result={'schema':'isaforge-v8-original-raw-evidence-v1','archive':archive.name,'archive_sha256':sha(archive),'files':records,
        'completion_sha256':sha(directory/'completion.json'),'compiler_objects_included':False}
    write(manifest,result);return result


def restore(root,repository=ROOT):
    root,repository=Path(root).resolve(),Path(repository).resolve();directory=root/'measurements';manifest=read(directory/'raw-evidence.json');archive=directory/manifest['archive']
    if manifest.get('schema')!='isaforge-v8-original-raw-evidence-v1' or sha(archive)!=manifest['archive_sha256'] or sha(directory/'completion.json')!=manifest['completion_sha256']:raise ValueError('Raw evidence archive identity differs')
    records={r['path']:r for r in manifest['files']}
    if len(records)!=len(manifest['files']):raise ValueError('Duplicate raw manifest member')
    with zipfile.ZipFile(archive) as stream:
        names=stream.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(records):raise ValueError('Raw archive inventory differs')
        for name in names:
            target=destination(name,repository);data=stream.read(name);info=stream.getinfo(name)
            if info.is_dir() or ((info.external_attr>>16)&0o170000)==0o120000 or len(data)!=records[name]['size'] or hashlib.sha256(data).hexdigest()!=records[name]['sha256']:raise ValueError('Raw evidence member differs')
            if target.exists() and sha(target)!=records[name]['sha256']:raise ValueError('Existing native evidence differs; refusing overwrite')
        for name in names:
            target=destination(name,repository)
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as output:output.write(stream.read(name))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('collect','pack','restore'));p.add_argument('--root',type=Path,required=True)
    p.add_argument('--approval',type=Path);p.add_argument('--attempt',default='attempt-0000');p.add_argument('--workers',type=int,default=2);p.add_argument('--repository',type=Path,default=ROOT)
    a=p.parse_args()
    if a.action=='collect':
        if a.approval is None:p.error('collect requires exact --approval root/label-approval.json')
        result=collect(a.root,a.approval,workers=a.workers,attempt=a.attempt)
    else:result=pack(a.root) if a.action=='pack' else restore(a.root,a.repository)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
