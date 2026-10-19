#!/usr/bin/env python3
"""Prepare and seal V6 calibration/test INPUTS ONLY. No labels/models/RTL checks."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge.features import parse_formula
from isaforge.v6_corpus import Generator,SEEDS,STRATA,FAMILIES_PER_STRATUM,VARIANTS,MAX_TREE_OPERATIONS,MAX_FAMILY_DRAWS,MAX_FEATURE_REPAIRS,inspect_seal

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def consumed_inputs(repo):
    """Use only frozen input-feature manifests; never read a target-label file."""
    paths=[repo/'results/2026-10-14-v5/development-features.json',repo/'results/2026-10-14-v5/test-features.json',
           repo/'results/2026-10-14-v5-external/features.json']
    records={};sources=[]
    for path in paths:
        manifest=read(path);source_formulas=set()
        if len(manifest['columns'])!=313:raise ValueError('Consumed V5 input schema differs')
        for record in manifest['records']:
            formula=parse_formula(record['formula']).canonical();source_formulas.add(formula)
            if formula in records and records[formula]['values']!=record['values']:raise ValueError('Consumed exact formula features conflict')
            records[formula]={'formula':formula,'normalized_formula':record['normalized_formula'],'values':record['values']}
        sources.append({'path':str(path.relative_to(repo)),'sha256':sha(path),'rows':len(manifest['records']),'unique_formulas':len(source_formulas)})
    return [{'formula':f} for f in sorted(records)],records,{'schema':'isaforge-v6-consumed-inputs-v1','sources':sources,
      'listed_unique_per_source_sum':sum(s['unique_formulas'] for s in sources),'raw_record_count':sum(s['rows'] for s in sources),
      'canonical_unique_count':len(records),'formulas':sorted(records),'scope':'All consumed V5 development/test and external inputs; labels are not read.'}

def run(output,cache_root,workers=2):
    from isaforge.area_model_v5 import columns as v5_columns,source_hashes as v5_sources
    from isaforge.area_model_v6 import FeatureExtractor,columns,source_hashes
    output=Path(output).resolve();cache_root=Path(cache_root).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Existing acquisition cannot be overwritten; use a new lineage')
    if type(workers) is not int or not 1<=workers<=4:raise ValueError('Workers must be1..4')
    sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'isaforge/v6_corpus.py',ROOT/'docs/v6-protocol.md',
             ROOT/'tests/test_v6_corpus.py']}
    sources.update({'isaforge/'+name:value for name,value in source_hashes().items()})
    consumed,oldfeatures,manifest=consumed_inputs(ROOT)
    write(output/'consumed-manifest.json',manifest)
    # Pure input-extraction metadata supplies the tool identity: no fitted
    # artifact/schema, label file or prediction file is opened by acquisition.
    tool_path=ROOT/'results/2026-10-14-v5/feature-extraction.json'
    tool_schema=read(tool_path)
    if tool_schema['source_sha256']!=v5_sources():raise ValueError('Frozen V5 runtime source differs')
    if tuple(columns()[:313])!=v5_columns() or len(columns())!=336:raise ValueError('Expected complete frozen V5 plus mapping23 schema')
    write(output/'acquisition-plan.json',{'schema':'isaforge-v6-input-acquisition-v1','started_at_utc':now(),
      'seeds':SEEDS,'strata':STRATA,'families_per_stratum':FAMILIES_PER_STRATUM,'constant_variants_per_family':VARIANTS,
      'max_original_tree_operations':MAX_TREE_OPERATIONS,'max_draws_per_family_call':MAX_FAMILY_DRAWS,
      'max_feature_repairs':MAX_FEATURE_REPAIRS,'minimum_strong_components_per_stratum':8,
      'source_sha256':sources,'frozen_tool':tool_schema['frozen_tool'],'tool_input_metadata_sha256':sha(tool_path),'consumed_manifest_sha256':sha(output/'consumed-manifest.json'),
      'no_labels_or_models':True,'selection':'Deterministic grammar draw order; reject whole families only for input identity, skeleton, feature collision, shape budget or extraction failure. Stop if bounds exhausted.'})
    generator=Generator([r['formula'] for r in consumed]);cohorts=generator.generate()
    write(output/'attempts/0000/candidates.json',cohorts)
    print('Provisional candidates',sum(map(len,cohorts.values())),'consumed canonical unique',len(consumed),flush=True)
    extractor=FeatureExtractor(cache_root,frozen_tool=tool_schema['frozen_tool']);began=time.perf_counter()
    # Mapping descriptors are derived without target mapping or labels. The V5
    # prefix is independently compared with every frozen input-feature record.
    def extract(rows,stage):
        try:return extractor.matrix(rows,workers=workers)
        except Exception as error:
            write(output/'extraction-failure.json',{'stage':stage,'failed_at_utc':now(),
              'formulas':[r['formula'] for r in rows],'error':repr(error),'action':'stopped; no outcome-based replacement'})
            raise
    _,consumed_records=extract(consumed,'consumed-reference')
    for record in consumed_records:
        if record['values'][:313]!=oldfeatures[record['formula']]['values']:raise ValueError('Consumed V5 feature replay differs')
    write(output/'consumed-features.json',{'columns':columns(),'records':consumed_records})
    features={};history=[]
    for revision in range(MAX_FEATURE_REPAIRS+1):
        folder=output/'attempts'/f'{revision:04d}';write(folder/'candidates.json',cohorts)
        current={}
        for scope,rows in cohorts.items():
            missing=[r for r in rows if r['formula'] not in features]
            if missing:
                _,new=extract(missing,f'{scope}-revision-{revision}')
                features.update({r['formula']:r for r in new})
            current[scope]=[features[r['formula']] for r in rows]
            write(folder/f'{scope}-features.json',{'columns':columns(),'records':current[scope]})
        seal=inspect_seal(consumed,cohorts,consumed_records,current)
        write(folder/'seal.json',seal);write(output/'generation-rejections.json',generator.rejections)
        history.append({'revision':revision,'candidate_sha256':sha(folder/'candidates.json'),'seal_sha256':sha(folder/'seal.json'),
                        'status':seal['status'],'rejected_family_count':len({(r['scope'],r['family_id']) for r in seal['rejections']})})
        write(output/'acquisition-history.json',history)
        if seal['status']=='sealed':break
        if revision==MAX_FEATURE_REPAIRS:raise ValueError('Input-only feature repair budget exhausted; no model or label release permitted')
        print('Input-only rejected families',history[-1]['rejected_family_count'],'revision',revision,flush=True)
        cohorts=generator.replace(cohorts,seal['rejections'])
    else:raise ValueError('No sealed acquisition')
    for name,digest in sources.items():
        if sha(ROOT/name)!=digest:raise ValueError('Acquisition source changed; retain attempt and rerun a new lineage')
    seal.update({'status':'sealed-inputs-only','frozen_at_utc':now(),'source_sha256':sources,'frozen_tool':tool_schema['frozen_tool'],
      'consumed_manifest_sha256':sha(output/'consumed-manifest.json'),'consumed_features_sha256':sha(output/'consumed-features.json'),
      'acquisition_plan_sha256':sha(output/'acquisition-plan.json'),'generation_rejections_sha256':sha(output/'generation-rejections.json'),
      'acquisition_history_sha256':sha(output/'acquisition-history.json'),
      'attempt_files_sha256':{str(p.relative_to(output)):sha(p) for p in sorted((output/'attempts').rglob('*.json'))},
      'calibration_labels_accessed':False,'test_labels_accessed':False,'model_predictions_accessed':False,
      'feature_extraction_seconds':time.perf_counter()-began})
    write(output/'input-seal.json',seal)
    for scope,rows in cohorts.items():
        target=output/scope
        for record in current[scope]:record['v5_values']=record['values'][:313]
        write(target/'candidates.json',rows);write(target/'features.json',{'columns':columns(),'records':current[scope]})
        write(target/'components.json',{'schema':'isaforge-v6-input-components-v1',
          'component_by_formula':{r['formula']:seal['component_by_formula'][r['formula']] for r in rows},
          'stratum_component_counts':seal['stratum_component_counts'][scope]})
        write(target/'freeze.json',{'schema':'isaforge-v6-input-freeze-v1','status':'sealed-inputs-only','scope':scope,
          'frozen_at_utc':now(),'candidate_sha256':sha(target/'candidates.json'),'features_sha256':sha(target/'features.json'),
          'components_sha256':sha(target/'components.json'),'feature_columns':columns(),'source_sha256':sources,
          'frozen_tool':tool_schema['frozen_tool'],'consumed_manifest_sha256':sha(output/'consumed-manifest.json'),
          'seal_sha256':sha(output/'input-seal.json'),'candidate_count':len(rows),
          'stratum_component_counts':seal['stratum_component_counts'][scope],'labels_released':False})
    print(json.dumps({'output':str(output),'status':'sealed-inputs-only','scope_counts':seal['scope_counts'],
      'stratum_component_counts':seal['stratum_component_counts'],'consumed_unique':len(consumed)},indent=2),flush=True)
    return seal
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'results/2026-10-14-v6/corpus')
    parser.add_argument('--cache-root',type=Path,default=ROOT/'generated/v5-features');parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();run(args.output,args.cache_root,args.workers)
