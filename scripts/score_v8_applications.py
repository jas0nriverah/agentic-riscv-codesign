#!/usr/bin/env python3
"""Score completed, approved V8 evidence without fitting or predicting again.

Raw evidence is read directly from its authenticated archive; restoration and
native tools are unnecessary. Novelty and OOD summaries are secondary only.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import measure_v8_applications as collector
from evaluate_v8_applications import evaluate, error_metrics, MODELS, PRIMARY
from evaluate_v6 import verification_source
from isaforge.features import parse_formula
from isaforge.rtl import BOUNDARIES, generate_rtl

read,sha,utc=collector.read,collector.sha,collector.utc


def digest(data):return hashlib.sha256(data).hexdigest()


def integer(value,name):
    if type(value) is not int or value<0:raise ValueError('Nonnegative integer '+name+' required')
    return value


def validate_measurements(root):
    """All pre-label gates precede any reading of completed fresh target files."""
    root=Path(root).resolve()
    point,inputs,rows,review=collector.validate_approval(root,root/'label-approval.json')
    bindings={(root/e['path']).resolve():e['sha256'] for e in [*point['files'],*inputs['files']]}
    if bindings.get(Path(__file__).resolve())!=sha(__file__):raise ValueError('Scorer source must be bound in approved committed freeze')
    release=read(root/'label-release.json');directory=root/'measurements';done=read(directory/'completion.json')
    expected_release={'schema':'isaforge-v8-application-label-release-v1','point_freeze_sha256':sha(root/'point-freeze.json'),
        'input_seal_sha256':sha(root/'input-seal.json'),'approval_sha256':sha(root/'label-approval.json'),
        'freeze_commit':review['freeze_commit'],'collector_sha256':sha(collector.__file__),
        'verification_seed':collector.VERIFY_SEED,'vectors_per_formula':2148,'workers':2}
    if (any(release.get(k)!=v for k,v in expected_release.items())
        or not utc(review['reviewed_at_utc'])<=utc(release['released_at_utc'])):raise ValueError('Release identity or approval chronology differs')
    attempt=done.get('attempt','')
    if not isinstance(attempt,str) or not re.fullmatch('attempt-[0-9]{4}',attempt):raise ValueError('Owned measurement attempt required')
    expected_done={'schema':'isaforge-v8-application-measurements-v1','complete':True,'failures':[],
        'unique_original_formulas':collector.UNIQUE_COUNT,'application_rows':collector.ROW_COUNT,
        'verification_seed':collector.VERIFY_SEED,'vectors_per_formula':2148,'collector_sha256':sha(collector.__file__),
        'release_sha256':sha(root/'label-release.json'),'frozen_tool':inputs['frozen_tool'],
        'original_rtl_only':True,'legacy_measurements_reused':False,'scratch_directory':collector.PREFIX+attempt}
    if (any(done.get(k)!=v or (type(v) is bool and type(done.get(k)) is not bool) for k,v in expected_done.items())
        or not utc(release['released_at_utc'])<=utc(done['completed_at_utc'])):raise ValueError('Complete fresh original measurement identity required')
    stage=directory/attempt
    if read(stage/'completion.json')!=done:raise ValueError('Attempt and stage completion differ')
    for name,key in [('labels.json','labels_sha256'),('unique-measurements.json','unique_measurements_sha256'),('verification.json','verification_sha256')]:
        if sha(stage/name)!=done[key]:raise ValueError('Completed measurement file digest differs')
    labels=read(stage/'labels.json');metrics=read(stage/'unique-measurements.json');proofs=read(stage/'verification.json')
    formulas=sorted({r['formula'] for r in rows})
    def indexed(records):
        result={r['formula']:r for r in records}
        if len(records)!=collector.UNIQUE_COUNT or len(result)!=len(records) or set(result)!=set(formulas):raise ValueError('Exact complete unique original targets required')
        return result
    by_formula=indexed(metrics);label_index=indexed(labels)
    sizes=[len(formulas[i:i+128]) for i in range(0,len(formulas),128)]
    if done['verification_batch_sizes']!=sizes or len(proofs)!=len(sizes):raise ValueError('Verification batch coverage differs')
    manifest_path=directory/'raw-evidence.json';manifest=read(manifest_path)
    if (manifest.get('schema')!='isaforge-v8-original-raw-evidence-v1' or manifest.get('archive')!='raw-evidence.zip'
        or manifest.get('completion_sha256')!=sha(directory/'completion.json') or manifest.get('compiler_objects_included') is not False):raise ValueError('Raw archive completion identity differs')
    archive=collector.verify_archive_manifest(manifest_path)
    prefix=collector.PREFIX+attempt+'/'
    if any(not r['path'].startswith(prefix) for r in manifest['files']):raise ValueError('Raw archive crosses owned attempt')
    with zipfile.ZipFile(archive) as raw:
        def data(name):
            try:return raw.read(prefix+name)
            except KeyError as error:raise ValueError('Required raw evidence missing: '+name) from error
        def bound(name,expected):
            value=data(name)
            if digest(value)!=expected:raise ValueError('Raw proof or physical target digest differs: '+name)
            return value
        for index,(proof,size) in enumerate(zip(proofs,sizes)):
            if (proof.get('verified') is not True or proof.get('formula_count')!=size or proof.get('vectors_per_formula')!=2148
                or proof.get('total_comparisons')!=size*2148 or proof.get('random_seed')!=collector.VERIFY_SEED
                or proof.get('v4_validation_override_sha256')!=sha(ROOT/'isaforge/v4_validation.py')):raise ValueError('Incomplete original RTL proof')
            folder=f'verification/batch-{index*128:04d}/'
            rtl=bound(folder+'verification.v',proof['rtl_sha256'])
            if rtl.decode()!=verification_source(formulas[index*128:index*128+size]):raise ValueError('Verified batch original formulas differ')
            vectors=bound(folder+'vectors.txt',proof['vectors_sha256']).decode().splitlines()
            import itertools,random
            rng=random.Random(collector.VERIFY_SEED);pairs=list(itertools.product(BOUNDARIES,repeat=2))
            pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048))
            if len(vectors)!=2148:raise ValueError('Verification vector count differs')
            for line,pair in zip(vectors,pairs):
                fields=line.split()
                if (len(fields)!=size+2 or any(re.fullmatch('[0-9a-f]{8}',v) is None for v in fields)
                    or tuple(int(v,16) for v in fields[:2])!=pair):raise ValueError('Verification vector seed or shape differs')
            if proof.get('signed_overflow_workaround_applied'):
                bound(folder+'yosys-boundary-cross-check/eval.log',proof['independent_yosys_log_sha256'])
        for formula in formulas:
            metric=by_formula[formula];label=label_index[formula]
            folder='circuits/'+digest(formula.encode())[:20]+'/'
            if (json.loads(data(folder+'metrics.json'))!=metric or metric.get('tool')!=inputs['frozen_tool']['version']
                or metric.get('tool_sha256')!=inputs['frozen_tool']['executable_sha256'] or metric.get('measurement_source')!='rtl_synthesis'
                or not utc(release['released_at_utc'])<=utc(metric['measured_at_utc'])<=utc(done['completed_at_utc'])):raise ValueError('Original target provenance differs')
            if metric['rtl_sha256']!=digest(generate_rtl(formula).encode()):raise ValueError('Target is not frozen original RTL')
            for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]:
                bound(folder+name,metric[key])
            netlist=json.loads(data(folder+'ice40-netlist.json'))
            cells=Counter(cell['type'] for cell in netlist['modules']['candidate'].get('cells',{}).values())
            if dict(cells)!=metric['ice40_cell_types']:raise ValueError('Raw netlist cell recount differs')
            for label_key,metric_key,cell in [('lut4_count','ice40_lut4_count','SB_LUT4'),('carry_count','ice40_carry_count','SB_CARRY')]:
                if integer(label[label_key],label_key)!=integer(metric[metric_key],metric_key) or metric[metric_key]!=cells[cell]:raise ValueError('Label, metric and raw resource count differ')
            if (label.get('rtl_sha256')!=metric['rtl_sha256'] or label.get('measurement_source')!='rtl_synthesis'
                or label.get('correctness_verified') is not True):raise ValueError('Original physical label proof differs')
    predictions={model:read(collector.checked(point['models'][model]['predictions'],root)) for model in MODELS}
    for model,records in predictions.items():
        if any(p.get('model')!=model or p.get('calibration_status')!='point_only_application_pilot' for p in records):
            raise ValueError('Frozen prediction model or point-only projection status differs')
    return rows,labels,predictions,read(root/'programs.json'),read(root/'novelty.json'),{
        'point_freeze_sha256':sha(root/'point-freeze.json'),'input_seal_sha256':sha(root/'input-seal.json'),
        'approval_sha256':sha(root/'label-approval.json'),'release_sha256':sha(root/'label-release.json'),
        'completion_sha256':sha(directory/'completion.json'),'raw_manifest_sha256':sha(manifest_path),'raw_archive_sha256':sha(archive),
        'labels_sha256':done['labels_sha256'],'verification_sha256':done['verification_sha256'],
        'unique_measurements_sha256':done['unique_measurements_sha256'],'freeze_commit':review['freeze_commit'],
        'scorer_sha256':sha(__file__),'pure_evaluator_sha256':sha(ROOT/'scripts/evaluate_v8_applications.py'),
        'raw_netlists_recounted':len(formulas),'verified_formula_vectors':2148*len(formulas),
        'verification_scope':'Authenticated original RTL and seeded vector shape/proof records; independent full oracle replay is a separate audit.'}


def diagnostics(rows,labels,predictions,programs,novelty):
    """Use frozen input classifications and frozen point diagnostics only."""
    formulas={r['formula'] for r in rows};records=novelty['records'];index={r['formula']:r for r in records}
    if (novelty.get('schema')!='isaforge-v8-input-novelty-v1' or len(records)!=len(index) or set(index)!=formulas
        or novelty.get('fresh_unique_formulas')!=len(formulas) or novelty.get('primary_rows_removed')!=0):raise ValueError('Complete frozen novelty ledger required')
    channels={'canonical','original_or_normalized','commutative_normalized','ordered_skeleton',
        'mapping217_vector','legacy_original336_vector','legacy_rewritten336_vector'}
    for record in records:
        matches=record['matches'];identity=('canonical','original_or_normalized','commutative_normalized')
        if (set(matches)!=channels or any(not isinstance(v,list) or any(not isinstance(f,str) for f in v) for v in matches.values())
            or type(record.get('no_declared_identity_match')) is not bool or type(record.get('strict_no_declared_match')) is not bool
            or record['no_declared_identity_match']!=(not any(matches[c] for c in identity))
            or record['strict_no_declared_match']!=(not any(matches.values()))):raise ValueError('Inconsistent frozen novelty flags')
    label={r['formula']:r['lut4_count'] for r in labels};primary={p['family'] for p in programs if p['primary_family']}
    strata={'canonical_seen':lambda r:bool(r['matches']['canonical']),
        'no_declared_identity_match':lambda r:r['no_declared_identity_match'],
        'strict_no_declared_match':lambda r:r['strict_no_declared_match'],
        'familiar_under_any_declared_test':lambda r:not r['strict_no_declared_match']}
    result={}
    for name,predicate in strata.items():
        selected=[i for i,row in enumerate(rows) if predicate(index[row['formula']])]
        counts=Counter(rows[i]['benchmark'] for i in selected);families={rows[i]['family'] for i in selected if rows[i]['primary_family']}
        scores={}
        for model in MODELS:
            by_program={p['benchmark']:error_metrics([label[rows[i]['formula']] for i in selected if rows[i]['benchmark']==p['benchmark']],
                [predictions[model][i]['predicted_lut4'] for i in selected if rows[i]['benchmark']==p['benchmark']]) for p in programs if counts[p['benchmark']]}
            by_family={f:statistics.fmean(by_program[p['benchmark']]['mae_lut4'] for p in programs if p['family']==f and p['benchmark'] in by_program) for f in families}
            scores[model]={'by_program':by_program,'by_primary_family_mae_lut4':by_family,
                'complete_primary_family_macro_mae_lut4':statistics.fmean(by_family.values()) if families==primary else None}
        a,b=PRIMARY
        result[name]={'application_rows':len(selected),'unique_formulas':len({rows[i]['formula'] for i in selected}),
            'by_program_rows':dict(counts),'missing_programs':[p['benchmark'] for p in programs if not counts[p['benchmark']]],
            'missing_primary_families':sorted(primary-families),'family_complete':families==primary,'scores':scores,
            'complete_family_primary_difference_lut4':scores[a]['complete_primary_family_macro_mae_lut4']-scores[b]['complete_primary_family_macro_mae_lut4'] if families==primary else None}
    ood={}
    for model in MODELS:
        points=predictions[model];values=[];spreads=[];shared={}
        for row,point in zip(rows,points):
            outside=point.get('outside_training_feature_ranges');spread=point.get('tree_disagreement_lut4')
            if outside is not None:integer(outside,'Frozen OOD count')
            if spread is not None and (type(spread) not in (int,float) or not math.isfinite(spread) or spread<0):raise ValueError('Invalid frozen disagreement')
            current=(outside,spread)
            if row['formula'] in shared and shared[row['formula']]!=current:raise ValueError('Shared formula frozen diagnostics differ')
            shared[row['formula']]=current;values.append(outside);spreads.append(spread)
        def subset(mask):
            selected=[i for i,v in enumerate(values) if mask(v)]
            return {'application_rows':len(selected),'metrics':error_metrics([label[rows[i]['formula']] for i in selected],[points[i]['predicted_lut4'] for i in selected]) if selected else None}
        ood[model]={'diagnostic_rows':sum(v is not None for v in values),'missing_diagnostic_rows':sum(v is None for v in values),
            'maximum_outside_feature_count':max((v for v in values if v is not None),default=None),
            'outside_any_selected_feature_range':subset(lambda v:v is not None and v>0),'inside_selected_feature_ranges':subset(lambda v:v==0),
            'mean_frozen_tree_disagreement_lut4':statistics.fmean(v for v in spreads if v is not None) if any(v is not None for v in spreads) else None}
    return {'novelty':result,'ood':ood,'scope':'Secondary consumed-test diagnostics; no novelty theorem, calibrated coverage claim, acquisition change or primary-row exclusion.'}


def score(root,output=None):
    root=Path(root).resolve();output=Path(output) if output is not None else root/'evaluation.json'
    if output.exists():raise ValueError('Evaluation output is immutable')
    rows,labels,predictions,programs,novelty,provenance=validate_measurements(root)
    value=evaluate(rows,labels,predictions,expected_programs=programs)
    value.update({'schema':'isaforge-v8-committed-application-evaluation-v1','lineage_validated_by_wrapper':True,
        'evaluated_at_utc':collector.now(),'provenance':provenance,'secondary_diagnostics':diagnostics(rows,labels,predictions,programs,novelty)})
    encoded=json.dumps(value,indent=2,allow_nan=False)+'\n';output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(encoded)
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();score(args.root,args.output)
