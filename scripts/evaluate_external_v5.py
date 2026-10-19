#!/usr/bin/env python3
"""Freeze or score external transfer using six existing models, without fitting."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_v4 import aligned,utc
from evaluate_v5 import extended_metrics,validate_freeze as validate_v5

MODELS=('sog_tuned','original_graph','dual_graph','dual_semantics','masterrtl_fixed','v4_frozen')
FAMILIES=('graph_shortest_paths','speech_codec','multiset_word_search')
PROGRAM_FAMILIES=dict(zip(('external_v5_dijkstra','external_v5_adpcm_dec','external_v5_anagram'),FAMILIES))
EXPECTED_PROGRAM_COUNTS={'external_v5_dijkstra':5,'external_v5_adpcm_dec':47,'external_v5_anagram':28}


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
    if sha(path)!=entry['sha256']:raise ValueError(f'Frozen file changed: {path}')
    return path


def validate_collection(cohort):
    cohort=Path(cohort)
    completion,report,plan=read(cohort/'completion.json'),read(cohort/'report.json'),read(cohort/'input-plan.json')
    if (completion['report_sha256']!=sha(cohort/'report.json')
            or completion['input_plan_sha256']!=sha(cohort/'input-plan.json')
            or completion['candidate_sha256']!=sha(cohort/'candidates.json')
            or report['input_plan_sha256']!=sha(cohort/'input-plan.json')
            or completion.get('resource_labels_released') is not False or completion.get('models_loaded') is not False
            or plan.get('target_labels_allowed') is not False or plan.get('model_predictions_allowed') is not False
            or report.get('all_self_checks_passed') is not True
            or report.get('all_families_present') is not True
            or report.get('target_labels_collected') is not False or report.get('models_loaded') is not False):
        raise ValueError('External collection did not completely pass label-free checks')
    by_program={r['program']:r for r in report['programs']}
    if set(by_program)!={'dijkstra','adpcm_dec','anagram'} or len(report['programs'])!=3:
        raise ValueError('All fixed external programs must remain represented')
    for row in report['programs']:
        if (row['status']!='passed' or row['self_check'].get('strong_check_passed') is not True
                or row['compiler_control'].get('matches_primary_output') is not True
                or row['trace'].get('validated') is not True or row['trace']['unknown_instructions']!=0
                or row['trace']['instret_delta']!=row['trace']['trace_instructions']+1
                or sha(cohort/'programs'/f"{row['program']}.elf")!=row['build']['elf_sha256']):
            raise ValueError('Program correctness/trace/ELF provenance failed')
    if len(by_program['anagram'].get('phrase_probes',[]))!=3 or not all(r.get('witness_check_passed') is True for r in by_program['anagram']['phrase_probes']):
        raise ValueError('All three anagram witnesses must pass')
    equivalence=read(cohort/'extraction-equivalence.json')
    if equivalence.get('passed') is not True or {r['benchmark'] for r in equivalence['benchmarks']}!={'dijkstra','adpcm_dec','anagram'}:
        raise ValueError('Fusion coverage incomplete')
    for row in equivalence['benchmarks']:
        if (row['skipped_opaque_block_occurrences']!=0 or row['checked_occurrences']<=0
                or row['individual_comparisons']!=16*row['checked_occurrences']):
            raise ValueError('Every declared fusion occurrence requires verification')
    for name,digest in plan['source_sha256'].items():
        if sha(cohort/'frozen-sources'/name)!=digest:
            raise ValueError('Missing original collection control-source snapshot')
    for program,spec in plan['upstream']['programs'].items():
        if PROGRAM_FAMILIES['external_v5_'+program]!=spec['family']:
            raise ValueError('Upstream family mapping changed')
        for name,digest in spec['files_sha256'].items():
            if sha(cohort/'sources'/name)!=digest:raise ValueError('Upstream source bytes changed')
    for row in report['programs']:
        builds=[(cohort/'programs'/row['program'],row['build']),
                (cohort/'controls'/row['program'],row['compiler_control']['build'])]
        builds += [(cohort/'controls'/f'anagram-phrase{i}',probe['build'])
                   for i,probe in enumerate(row.get('phrase_probes',[]))]
        for folder,build in builds:
            if (sha(folder/'snapshot.c')!=build['adapter_sha256']
                    or sha(folder/f"{row['program']}.elf")!=build['elf_sha256']):
                raise ValueError('Build adapter/ELF evidence changed')
    rows=read(cohort/'candidates.json')
    validate_candidates(rows)
    return rows,report,plan


def validate_candidates(rows):
    from collections import Counter
    from isaforge.features import candidate_id,parse_formula
    if (not isinstance(rows,list) or len(rows)!=80
            or Counter(r['benchmark'] for r in rows)!=Counter(EXPECTED_PROGRAM_COUNTS)
            or len({r['formula'] for r in rows})!=79
            or set(r['family'] for r in rows)!=set(FAMILIES)):
        raise ValueError('Expected all80 program/formula rows and79 unique formulas')
    if len({(r['benchmark'],r['candidate_id']) for r in rows})!=80:
        raise ValueError('Duplicate program/formula identities')
    for row in rows:
        if (row['family']!=PROGRAM_FAMILIES[row['benchmark']]
                or row.get('stratum',row['family'])!=row['family']
                or parse_formula(row['formula']).canonical()!=row['formula']
                or candidate_id(row['benchmark'],row['formula'])!=row['candidate_id']
                or any(k in row for k in ('lut4_count','carry_count','predicted_lut4'))):
            raise ValueError('External inputs must preserve canonical unlabelled identities')


def overlap_report(rows,external_features,development,consumed,development_features,consumed_features):
    from isaforge.structural_features_v5 import normalize_formula
    from isaforge.v5_corpus import skeleton
    sources={'development':(development,development_features),'consumed_v5_test':(consumed,consumed_features)}
    if (len(development)!=2057 or len(consumed)!=256
            or len({r['formula'] for r in development+consumed})!=2313):
        raise ValueError('Expected all2313 consumed reference formulas')
    external={r['formula']:r for r in external_features}
    if set(external)!={r['formula'] for r in rows}:raise ValueError('External feature coverage incomplete')
    indices={}
    for name,(inputs,features) in sources.items():
        indexed={r['formula']:r for r in features}
        if len(indexed)!=len(inputs) or set(indexed)!={r['formula'] for r in inputs}:
            raise ValueError('Reference feature coverage incomplete')
        indices[name]={
            'exact':set(indexed),
            'normalized':{normalize_formula(f) for f in indexed},
            'full_feature':{tuple(r['values']) for r in features},
            'original_skeleton':{skeleton(f) for f in indexed},
            'normalized_skeleton':{skeleton(normalize_formula(f)) for f in indexed},
        }
    records=[]
    for row in rows:
        formula=row['formula'];normalized=normalize_formula(formula)
        keys={'exact':formula,'normalized':normalized,'full_feature':tuple(external[formula]['values']),
              'original_skeleton':skeleton(formula),'normalized_skeleton':skeleton(normalized)}
        hits={name:{kind:key in index[kind] for kind,key in keys.items()} for name,index in indices.items()}
        strict=not any(any(values.values()) for values in hits.values())
        formula_novel=not any(any(values[kind] for kind in ('exact','normalized','full_feature')) for values in hits.values())
        records.append({**{key:row[key] for key in ('benchmark','candidate_id','formula','family')},
                        'normalized_formula':normalized,'overlap':hits,'strict_novel':strict,'formula_novel':formula_novel})
    return {'definition':'strict_novel excludes ANY exact, current-normalized, full-feature, original-skeleton or normalized-skeleton match in all2313 consumed formulas',
            'reference_formula_counts':{'development':2057,'consumed_v5_test':256},'records':records,
            'counts':{name:{kind:sum(r['overlap'][name][kind] for r in records) for kind in indices[name]} for name in indices},
            'strict_novel_rows':sum(r['strict_novel'] for r in records),
            'formula_novel_rows':sum(r['formula_novel'] for r in records)}


def collection_files(cohort):
    cohort=Path(cohort)
    files=[cohort/name for name in ('completion.json','report.json','input-plan.json','extraction-equivalence.json','candidates.json','full-candidates.json')]
    files += [p for folder in ('frozen-sources','sources') for p in (cohort/folder).rglob('*') if p.is_file()]
    files += [p for folder in ('programs','controls') for p in (cohort/folder).rglob('*')
              if p.is_file() and (p.suffix=='.elf' or p.name=='snapshot.c' or p.suffix=='.log')]
    files += [p for p in (cohort/'logs').glob('*.log') if 'trace' not in p.name]
    return list(dict.fromkeys(files))


def copy_evidence(cohort,destination):
    # Raw traces/caches stay in generated archives; source/input/binary evidence
    # needed to review the freeze is small enough to commit with the bundle.
    copied=[]
    files=collection_files(cohort)
    for source in files:
        if not source.is_file():continue
        target=destination/source.relative_to(cohort)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied.append(target)
    return copied


def freeze(root,cohort,v5_root,cache_root,workers=2):
    root,cohort,v5_root=map(lambda p:Path(p).resolve(),(root,cohort,v5_root))
    if (root/'freeze.json').exists() or (root/'label-release.json').exists():
        raise ValueError('Existing external freeze/release is immutable')
    raw_rows,collection,plan=validate_collection(cohort)
    old_manifest,_,_,_=validate_v5(v5_root)
    from isaforge.area_model_v5 import FeatureExtractor,load_model,columns,source_hashes
    from isaforge import masterrtl_baseline as master
    from isaforge.area_model_v4 import load_model as load_v4
    from isaforge.masterrtl_baseline import tool_identity
    rows=[{**row,'stratum':row['family']} for row in raw_rows]
    root.mkdir(parents=True,exist_ok=True)
    copied=copy_evidence(cohort,root/'collection')
    write(root/'candidates.json',rows)
    sources=source_hashes()
    start={'started_at_utc':now(),'fitting_performed':False,'model_source_freeze_sha256':sha(v5_root/'freeze.json'),
           'runtime_sources':sources,'external_target_labels_read':False}
    write(root/'freeze-start.json',start)
    models={name:load_model(checked(old_manifest['models'][name]['artifact'],v5_root),cache_root) for name in MODELS[:4]}
    extractor=FeatureExtractor(cache_root,frozen_tool=models['dual_semantics'].frozen_tool)
    unique=[{'formula':formula} for formula in sorted({r['formula'] for r in rows})]
    matrix,records=extractor.matrix(unique,workers=workers)
    write(root/'features.json',{'columns':columns(),'records':records,'unique_formula_count':len(unique)})
    by_formula={row['formula']:value for row,value in zip(unique,matrix)}
    x=np.asarray([by_formula[row['formula']] for row in rows])
    dev=read(v5_root/'development-data.json');consumed=read(v5_root/'corpus/test/candidates.json')
    dev_features=read(v5_root/'development-features.json');test_features=read(v5_root/'test-features.json')
    if tuple(dev_features['columns'])!=columns() or tuple(test_features['columns'])!=columns():
        raise ValueError('Reference feature schemas differ')
    overlap=overlap_report(rows,records,dev,consumed,dev_features['records'],test_features['records'])
    write(root/'overlap.json',overlap)
    entries={}
    for name in MODELS:
        old=old_manifest['models'][name]
        artifact,schema=checked(old['artifact'],v5_root),checked(old['schema'],v5_root)
        if name in models:
            predictions=models[name].predict_features(rows,x)
        elif name=='masterrtl_fixed':
            predictions=master.load_model(artifact,Path(cache_root)/'masterrtl-fixed').predict(rows)
        else:
            predictions=load_v4(artifact,Path(cache_root)/'v4').predict(rows)
        aligned(rows,predictions,'predicted_lut4')
        path=root/'predictions'/f'{name}.json';write(path,predictions)
        entries[name]={'artifact':record(artifact,root),'schema':record(schema,root),
                       'predictions':record(path,root),'frozen_at_utc':now()}
    files=[*copied,root/'candidates.json',root/'features.json',root/'overlap.json',root/'freeze-start.json',
           ROOT/'scripts/evaluate_external_v5.py',ROOT/'scripts/measure_external_v5.py',ROOT/'docs/external-v5-evaluation.md',ROOT/'docs/external-v5-protocol.md',
           ROOT/'tests/test_evaluate_external_v5.py',ROOT/'tests/test_external_v5.py',
           ROOT/'scripts/evaluate_v4.py',ROOT/'scripts/evaluate_v5.py',v5_root/'freeze.json',
           v5_root/'development-data.json',v5_root/'development-features.json',v5_root/'corpus/test/candidates.json',v5_root/'test-features.json',
           *(ROOT/'isaforge'/name for name in sources)]
    if source_hashes()!=sources:raise ValueError('Runtime changed during external inference')
    manifest={'schema':'isaforge-external-v5-freeze-v1','frozen_at_utc':now(),'models':entries,
              'files':[record(path,root) for path in dict.fromkeys(files)],'model_source_freeze':record(v5_root/'freeze.json',root),
              'candidate_sha256':sha(root/'candidates.json'),'family_names':list(FAMILIES),
              'program_counts':EXPECTED_PROGRAM_COUNTS,'formula_count':79,'program_formula_count':80,
              'primary':'Equal-weight three-family MAE on all80 program/formula rows',
              'primary_comparison':'dual_semantics minus sog_tuned','fitting_performed':False,
              'external_target_labels_read':False,'measurement_tool':tool_identity(),
              'measurement_scope':'Original RTL isolated iCE40 LUT4; Dijkstra is a partial-workload trace',
              'strict_novel_definition':overlap['definition']}
    write(root/'freeze.json',manifest)
    validate_freeze(root)
    return manifest


def validate_freeze(root):
    root=Path(root).resolve();manifest=read(root/'freeze.json')
    if (manifest.get('schema')!='isaforge-external-v5-freeze-v1' or set(manifest['models'])!=set(MODELS)
            or manifest.get('fitting_performed') is not False or manifest.get('external_target_labels_read') is not False
            or manifest.get('primary_comparison')!='dual_semantics minus sog_tuned'
            or manifest.get('family_names')!=list(FAMILIES)
            or manifest.get('program_counts')!=EXPECTED_PROGRAM_COUNTS
            or manifest.get('formula_count')!=79 or manifest.get('program_formula_count')!=80):
        raise ValueError('Invalid external model/prediction freeze')
    frozen=utc(manifest['frozen_at_utc']);paths={checked(entry,root) for entry in manifest['files']}
    required={root/name for name in ('candidates.json','features.json','overlap.json','freeze-start.json')}
    required|={ROOT/'scripts/evaluate_external_v5.py',ROOT/'scripts/measure_external_v5.py',ROOT/'docs/external-v5-evaluation.md',ROOT/'docs/external-v5-protocol.md',
           ROOT/'tests/test_evaluate_external_v5.py',ROOT/'tests/test_external_v5.py',
               ROOT/'scripts/evaluate_v4.py',ROOT/'scripts/evaluate_v5.py'}
    if not required<=paths:raise ValueError('Freeze omits required implementation/input evidence')
    rows=read(root/'candidates.json');validate_candidates(rows)
    if sha(root/'candidates.json')!=manifest['candidate_sha256']:raise ValueError('Changed candidate pool')
    raw_rows,_,_=validate_collection(root/'collection')
    if rows!=[{**r,'stratum':r['family']} for r in raw_rows]:
        raise ValueError('External rows differ from archived collection candidates')
    if not set(collection_files(root/'collection'))<=paths:
        raise ValueError('Freeze omits collection provenance evidence')
    old_freeze=checked(manifest['model_source_freeze'],root)
    if old_freeze not in paths:raise ValueError('Original V5 freeze not hash-bound')
    old_root=old_freeze.parent
    old_manifest,_,_,_=validate_v5(old_root)
    references=[old_root/name for name in ('development-data.json','development-features.json','corpus/test/candidates.json','test-features.json')]
    if not set(references)<=paths:raise ValueError('Consumed references not hash-bound')
    start=read(root/'freeze-start.json');started=utc(start['started_at_utc'])
    if (not utc(old_manifest['frozen_at_utc'])<=started<=frozen or start['model_source_freeze_sha256']!=sha(old_freeze)
            or start.get('fitting_performed') is not False or start.get('external_target_labels_read') is not False):
        raise ValueError('Invalid external freeze start')
    from isaforge.area_model_v5 import source_hashes
    if start['runtime_sources']!=source_hashes() or not {ROOT/'isaforge'/n for n in start['runtime_sources']}<=paths:
        raise ValueError('External runtime sources not completely frozen')
    features=read(root/'features.json')
    from isaforge.area_model_v5 import columns
    if (tuple(features['columns'])!=columns() or len(features['records'])!=79
            or {r['formula'] for r in features['records']}!={r['formula'] for r in rows}):
        raise ValueError('External feature schema/coverage incomplete')
    for entry in features['records']:
        values=np.asarray(entry['values'],dtype=float)
        if values.shape!=(len(columns()),) or not np.isfinite(values).all() or np.any(values<0):
            raise ValueError('Invalid frozen feature vector')
    overlap=read(root/'overlap.json')
    expected_overlap=overlap_report(rows,features['records'],read(references[0]),read(references[2]),
                                    read(references[1])['records'],read(references[3])['records'])
    if overlap!=expected_overlap:raise ValueError('Overlap inventory differs from hash-bound consumed references')
    predictions={}
    for name,entry in manifest['models'].items():
        for key in ('artifact','schema'):
            actual=checked(entry[key],root);original=checked(old_manifest['models'][name][key],old_root)
            if actual!=original or entry[key]['sha256']!=old_manifest['models'][name][key]['sha256']:
                raise ValueError('External artifact/schema differs from original V5 model freeze')
        predictions[name]=read(checked(entry['predictions'],root));aligned(rows,predictions[name],'predicted_lut4')
        if [(r['benchmark'],r['candidate_id'],r['formula']) for r in predictions[name]]!=[(r['benchmark'],r['candidate_id'],r['formula']) for r in rows]:
            raise ValueError('Frozen predictions must preserve declared input order')
        if not started<=utc(entry['frozen_at_utc'])<=frozen:
            raise ValueError('Prediction timestamp outside external freeze interval')
        validate_prediction_metadata(name,predictions[name],read(checked(entry['schema'],root)))
    return manifest,rows,predictions,overlap


def validate_prediction_metadata(name,predictions,schema):
    by_formula={}
    for row in predictions:
        value=row['predicted_lut4']
        if row['formula'] in by_formula and value!=by_formula[row['formula']]:
            raise ValueError('Repeated formula has inconsistent point predictions')
        by_formula[row['formula']]=value
        if name in MODELS[:4]:
            margin=schema['calibration']['upper_margin_lut4']
            upper=row.get('upper_lut4')
            if ((margin is None and upper is not None) or
                    (margin is not None and (upper is None or not np.isfinite(upper) or upper!=value+margin))):
                raise ValueError('Frozen upper bound differs from original calibration margin')
            if not isinstance(row.get('outside_training_feature_ranges'),int) or row['outside_training_feature_ranges']<0:
                raise ValueError('Missing frozen feature-range diagnostic')


def validate_committed_review(root,review_path):
    root=Path(root).resolve();manifest,rows,predictions,overlap=validate_freeze(root)
    review=review_path if isinstance(review_path,dict) else read(review_path)
    if (review.get('schema')!='isaforge-external-review-v1' or review.get('approved_for_label_release') is not True
            or review.get('freeze_sha256')!=sha(root/'freeze.json')
            or utc(review['reviewed_at_utc'])<utc(manifest['frozen_at_utc'])):
        raise ValueError('Explicit parent review of this exact freeze is required')
    commit=review['freeze_commit']
    if not isinstance(commit,str) or not __import__('re').fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Review must name an exact committed freeze SHA')
    records=[record(root/'freeze.json',root),*manifest['files']]
    for entry in manifest['models'].values():
        records.extend(entry[key] for key in ('artifact','schema','predictions'))
    for entry in records:
        path=checked(entry,root)
        if not path.is_relative_to(ROOT):raise ValueError('Committed freeze evidence must be in the repository')
        relative=path.relative_to(ROOT)
        run=subprocess.run(['git','show',f'{commit}:{relative.as_posix()}'],cwd=ROOT,capture_output=True)
        if run.returncode or hashlib.sha256(run.stdout).hexdigest()!=entry['sha256']:
            raise ValueError(f'Freeze evidence not committed at approved SHA: {relative}')
    return manifest,rows,predictions,overlap,review


def scoped_metrics(rows,y,p,mask):
    mask=np.asarray(mask,dtype=bool)
    represented={family:int(np.sum(mask & np.asarray([r['family']==family for r in rows]))) for family in FAMILIES}
    if not mask.any():return {'row_count':0,'family_counts':represented,'macro_family_mae_lut4':None,'status':'empty subset'}
    by_family={family:extended_metrics(y[ix],p[ix]) for family in FAMILIES if (ix:=mask & np.asarray([r['family']==family for r in rows])).any()}
    complete=all(represented.values())
    return {**extended_metrics(y[mask],p[mask]),'row_count':int(mask.sum()),'family_counts':represented,
            'by_family':by_family,'macro_family_mae_lut4':float(np.mean([by_family[f]['mae_lut4'] for f in FAMILIES])) if complete else None,
            'status':'all three families represented' if complete else 'incomplete family coverage; three-family macro unavailable'}


def validate_measurements(root,manifest,rows):
    root=Path(root);release=read(root/'label-release.json');completion=read(root/'measurements/completion.json')
    _,_,_,_,review=validate_committed_review(root,release['parent_review'])
    approval=root/'label-approval.json'
    if (not approval.is_file() or sha(approval)!=release['review_sha256'] or read(approval)!=review
            or release.get('authorized_after_parent_review') is not True or release['freeze_commit']!=review['freeze_commit']
            or release['freeze_sha256']!=sha(root/'freeze.json') or release['candidate_sha256']!=manifest['candidate_sha256']
            or not utc(manifest['frozen_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(release['released_at_utc'])
            or completion.get('complete') is not True or completion.get('failures')
            or completion.get('unique_formula_count')!=79 or completion.get('program_formula_count')!=80
            or completion.get('release')!=release or completion.get('original_rtl_only') is not True
            or completion.get('collector_sha256')!=sha(ROOT/'scripts/measure_external_v5.py')
            or completion.get('tool')!=manifest['measurement_tool']['version']
            or completion.get('tool_sha256')!=manifest['measurement_tool']['executable_sha256']):
        raise ValueError('External labels lack a complete reviewed post-freeze release')
    directory=root/'measurements'/completion['attempt']
    if not directory.resolve().is_relative_to((root/'measurements').resolve()):raise ValueError('Invalid measurement attempt path')
    for filename,key in [('dataset.json','dataset_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:
        if sha(directory/filename)!=completion[key]:raise ValueError('Changed external measurement evidence')
    proofs=read(directory/'verification.json')
    if (len(proofs)!=1 or proofs[0].get('verified') is not True or proofs[0].get('formula_count')!=79
            or proofs[0].get('vectors_per_formula')!=2148 or proofs[0].get('total_comparisons')!=79*2148):
        raise ValueError('Original RTL verification coverage incomplete')
    unique=read(directory/'unique-measurements.json');by_formula={r['formula']:r for r in unique}
    if len(unique)!=79 or set(by_formula)!={r['formula'] for r in rows}:
        raise ValueError('Unique original measurement coverage incomplete')
    from isaforge.rtl import generate_rtl
    scratch=(root/completion['scratch_directory']).resolve()
    if not scratch.is_relative_to(ROOT/'generated/external-v5/target-measurements'):
        raise ValueError('Measurement scratch evidence outside owned archive')
    for formula,row in by_formula.items():
        if (row['rtl_sha256']!=hashlib.sha256(generate_rtl(formula).encode()).hexdigest()
                or row.get('tool')!=completion['tool'] or row.get('tool_sha256')!=completion['tool_sha256']
                or row.get('measurement_source')!='rtl_synthesis'
                or utc(row['measured_at_utc'])<utc(release['released_at_utc'])):
            raise ValueError('Unique original circuit provenance differs')
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        if read(folder/'metrics.json')!=row or any(sha(folder/n)!=row[k] for n,k in
                [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]):
            raise ValueError('Original circuit synthesis evidence changed')
    labels=read(directory/'dataset.json');y=aligned(rows,labels,'lut4_count',measured=True)
    for row in labels:
        metric=by_formula[row['formula']]
        if (row['lut4_count']!=metric['ice40_lut4_count'] or row['carry_count']!=metric['ice40_carry_count']
                or row['rtl_sha256']!=metric['rtl_sha256'] or row['synthesis_tool']!=completion['tool']):
            raise ValueError('Expanded program label differs from unique original measurement')
    return labels,y


def bound_diagnostics(rows,y,predictions):
    def subset(indices):
        finite=[i for i in indices if predictions[i].get('upper_lut4') is not None and np.isfinite(predictions[i]['upper_lut4'])]
        slack=np.asarray([predictions[i]['upper_lut4']-y[i] for i in finite])
        return {'row_count':len(indices),'finite_bound_count':len(finite),
                'finite_bound_fraction':len(finite)/len(indices) if indices else None,
                'observed_candidate_coverage':float(np.mean(slack>=0)) if finite else None,
                'mean_slack_lut4':float(slack.mean()) if finite else None,
                'minimum_slack_lut4':float(slack.min()) if finite else None,
                'outside_feature_range_rows':sum(predictions[i]['outside_training_feature_ranges']>0 for i in indices),
                'outside_feature_range_dimensions_sum':sum(predictions[i]['outside_training_feature_ranges'] for i in indices)}
    groups={f:[i for i,r in enumerate(rows) if r['family']==f] for f in FAMILIES}
    return {'all':subset(list(range(len(rows)))),'by_family':{f:subset(ix) for f,ix in groups.items()},
            'whole_family_coverage_count':sum(all(predictions[i].get('upper_lut4') is not None and predictions[i]['upper_lut4']>=y[i] for i in ix) for ix in groups.values()),
            'scope':'Observed candidate and three curated family diagnostics; families differ from calibration groups; no 90% guarantee under application shift.'}


def evaluate(root):
    root=Path(root).resolve();manifest,rows,predictions,overlap=validate_freeze(root)
    labels,y=validate_measurements(root,manifest,rows)
    estimates={name:aligned(rows,values,'predicted_lut4') for name,values in predictions.items()}
    masks={'all':np.ones(len(rows),dtype=bool),'strict_novel':np.asarray([r['strict_novel'] for r in overlap['records']]),
           'formula_novel':np.asarray([r['formula_novel'] for r in overlap['records']])}
    first_by_formula={}
    for index,row in enumerate(rows):first_by_formula.setdefault(row['formula'],index)
    unique_indices=np.asarray(list(first_by_formula.values()))
    for formula in first_by_formula:
        indices=[i for i,r in enumerate(rows) if r['formula']==formula]
        if len(set(y[indices]))!=1:raise ValueError('Repeated original formula has inconsistent measured labels')
    result={'schema':'isaforge-external-v5-evaluation-v1','evaluated_at_utc':now(),'freeze_sha256':sha(root/'freeze.json'),
            'primary':manifest['primary'],'primary_comparison':manifest['primary_comparison'],
            'models':{},'paired_comparisons':{},'overlap':overlap['counts'],
            'limitations':'Three curated families; partial Dijkstra trace; shared exact formulas/structures explicitly retained; no CPU speedup or population-wide transfer guarantee.'}
    for name,p in estimates.items():
        result['models'][name]={scope:scoped_metrics(rows,y,p,mask) for scope,mask in masks.items()}
        result['models'][name]['unique_formula_pooled_secondary']=extended_metrics(y[unique_indices],p[unique_indices])
        if name in MODELS[:4]:result['models'][name]['frozen_bound_diagnostics']=bound_diagnostics(rows,y,predictions[name])
        result['models'][name]['candidate_errors']=[{**row,'lut4_count':float(target),'predicted_lut4':float(estimate),
            'absolute_error_lut4':float(abs(estimate-target))} for row,target,estimate in zip(rows,y,p)]
    for scope in masks:
        full=result['models']['dual_semantics'][scope]['macro_family_mae_lut4']
        sog=result['models']['sog_tuned'][scope]['macro_family_mae_lut4']
        result['paired_comparisons'][scope]={'macro_family_mae_difference_lut4':None if full is None or sog is None else full-sog,
                                          'definition':'Full V5 minus equally tuned SOG; negative favors V5; same rows and family weights'}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    create=sub.add_parser('freeze');create.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5-external')
    create.add_argument('--cohort',type=Path,default=ROOT/'generated/external-v5/cohort-02')
    create.add_argument('--v5-root',type=Path,default=ROOT/'results/2026-10-14-v5')
    create.add_argument('--cache-root',type=Path,default=ROOT/'generated/external-v5/features');create.add_argument('--workers',type=int,default=2)
    score=sub.add_parser('score');score.add_argument('--root',type=Path,default=ROOT/'results/2026-10-14-v5-external');score.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='freeze':
        result=freeze(args.root,args.cohort,args.v5_root,args.cache_root,args.workers)
        print(json.dumps({'frozen_at_utc':result['frozen_at_utc'],'labels_released':False}))
    else:
        result=evaluate(args.root);write(args.output,result)
        print(json.dumps(result['paired_comparisons'],indent=2))


if __name__=='__main__':main()
