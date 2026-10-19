#!/usr/bin/env python3
"""Seal the entire audited V11c original pool; no extraction/inference/labels/fits.

The caller supplies the reviewed independent-audit digest. This stage rechecks
its complete byte closure, not its expensive raw parser/ELF/fusion computation.
The audit's disclosed shared-helper scope remains unchanged. Budgets below are
proposals only, never native authorization.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from isaforge.features import parse_formula
from isaforge.v5_corpus import equivalence_key, skeleton

V9=Path('results/2026-10-15-v9-coverage-development')
V9_PREP_SHA='468d264af46134f6717e317c9fcdc10c47f0f45e5938ec5da2999793d2977dca'
V9_POINT_SHA='ba377ae7ee17d7f656a1e05e5139fa98ec04f1b63d29d73e9322662eabe333bc'
MODELS={'V6':('results/2026-10-14-v6/models/mapping_v6.joblib','1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56',1665),
        'V9':(str(V9/'fit-attempt-0000/models/mapping-coverage.joblib'),'dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d',1713)}
FAMILIES={'ammunition':'arbitrary-precision-bit-strings','audiobeam':'audio-beamforming','pm':'numeric-template-matching',
          'fmref':'fm-reception','fac':'integer-recurrences','recursion':'integer-recurrences'}

def need(condition,message):
    if not condition:raise ValueError(message)
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def read(path):
    def unique(items):
        d={}
        for k,v in items:need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def equal(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def record(path,base):return {'path':os.path.relpath(Path(path).resolve(),base),'sha256':sha(path),'bytes':Path(path).stat().st_size}
def canonical(f):
    need(type(f) is str and parse_formula(f).canonical()==f,'Canonical original/form required');return f
def integer(n):need(type(n) is int and n>=0,'Nonnegative integer count required');return n
def identifier(formula):return 'v11-original:'+hashlib.sha256(formula.encode()).hexdigest()
def checked(entry,base):
    need(type(entry['path']) is str and not Path(entry['path']).is_absolute(),'Relative repository record required')
    p=(base/entry['path']).resolve();need(p.is_relative_to(ROOT) and p.is_file() and not (base/entry['path']).is_symlink(),'Missing/unsafe bound file')
    need(sha(p)==entry['sha256'] and ('bytes' not in entry or p.stat().st_size==integer(entry['bytes'])),'Bound input bytes differ');return p
def check_hashes(bindings):
    need(all(p.is_file() and not p.is_symlink() and sha(p)==h for p,h in bindings.items()),'Input/source changed during staging')
def sources():
    return sorted({ROOT/'scripts/prepare_v11_model_comparison.py',ROOT/'tests/test_prepare_v11_model_comparison.py',
        ROOT/'scripts/score_v11_transfer.py',ROOT/'scripts/audit_v11c_recovery.py',ROOT/'scripts/audit_v11_recovery.py',
        ROOT/'scripts/audit_v11b_failure.py',ROOT/'scripts/recover_v11c_transfer.py',ROOT/'scripts/capture_v11_spooled.py',
        ROOT/'docs/v11b-transfer-protocol.md',ROOT/'docs/v11c-environment-amendment.md',*sorted((ROOT/'isaforge').glob('*.py'))})

def authenticate_recovery(root,audit_path,audit_sha256):
    """Trust only the caller-reviewed audit identity plus its unchanged inputs."""
    import audit_v11c_recovery as audit
    root=Path(root).resolve();audit_path=Path(audit_path).resolve()
    need(type(audit_sha256) is str and re.fullmatch('[0-9a-f]{64}',audit_sha256) and audit_path.is_relative_to(ROOT) and sha(audit_path)==audit_sha256,'Explicit reviewed independent-audit digest required')
    report=read(audit_path);stage=root/'run/attempt-0000';done=read(root/'completion.json')
    need(report['schema']=='isaforge-v11c-independent-recovery-audit-v1' and report['status']=='pass' and report['complete'] is True and report['source_sha256']==sha(audit.__file__),'Complete current-source independent result audit required')
    need(done['schema']=='isaforge-v11c-recovery-completion-v1' and done['complete'] is True and done['failures']==[] and equal(done,read(stage/'completion.json')),'Complete V11c attempt required')
    for k,p in [('preparation_sha256',root/'preparation.json'),('completion_sha256',root/'completion.json'),('evidence_manifest_sha256',stage/'evidence-manifest.json')]:
        need(report[k]==sha(p),'Audit no longer authenticates current recovery')
    need(all(type(report[k]) is int and report[k]==n for k,n in [('program_count',6),('reused_program_count',4),('recovered_program_count',2),('labels_predictions_features_fits',0)]),'Audit cohort/scope differs')
    need(datetime.fromisoformat(report['audited_at_utc'])>=datetime.fromisoformat(done['completed_at_utc']),'Audit precedes recovery completion')
    data=audit.inputs(root);manifest,files=audit.verify_package(root,done)
    records=read(stage/'programs.json');audit.verify_outcomes(records,data['plan'])
    need(set(report['programs'])==set(FAMILIES),'Independent audit omits/extends outcomes')
    for name,row in records.items():
        review=report['programs'][name]
        need(review['status']==row['status'] and integer(review['candidate_count'])==integer(row['candidate_count']),'Audited outcome differs')
    bindings={**data['bindings'],**{p:r['sha256'] for p,r in files.items()}}
    for p in (audit_path,root/'preparation.json',root/'completion.json',stage/'evidence-manifest.json',stage/'metadata.zip'):bindings[p]=sha(p)
    return records,report,bindings

def pool(root,records):
    need(type(records) is dict and set(records)==set(FAMILIES),'Exactly six reserved outcomes required')
    memberships=[];by_formula=defaultdict(list);copies={};completed=[]
    for name,family in FAMILIES.items():
        r=records[name];need(r['family']==family and r['status'] in ('complete','empty'),'Wrong family or incomplete program')
        path=checked(r['candidate_file'],root);rows=read(path)
        need(type(rows) is list and len(rows)==integer(r['candidate_count']),'Full candidate count differs')
        formulas=[canonical(row['formula']) for row in rows]
        need(len(set(formulas))==len(formulas),'Duplicate canonical original within program')
        need((r['status']=='empty')==(len(rows)==0),'Empty must remain distinct from incomplete/nonempty')
        need(name!='recursion' or not rows,'Reserved recursion must remain empty')
        ids=[]
        for formula,row in zip(formulas,rows):
            by_formula[formula].append(name);ids.append(identifier(formula));completed.append({**row,'benchmark':name,'family':family})
        memberships.append({'program':name,'family':family,'status':r['status'],'canonical_count':len(rows),'canonical_ids':sorted(ids)})
        copies[name]=path
    need(all(any(m['canonical_count'] for m in memberships if m['family']==f) for f in set(FAMILIES.values())),'Every declared family needs a nonempty eligible program')
    need(equal(completed,read(root/'run/attempt-0000/completed-rows.json')),'Full source program/formula memberships differ')
    candidates=[{'candidate_id':identifier(f),'formula':f,'programs':by_formula[f],'families':sorted({FAMILIES[n] for n in by_formula[f]})} for f in sorted(by_formula)]
    return memberships,candidates,copies

def accepted_forms(row):
    forms={canonical(row['formula']),canonical(row['normalized_formula'])}
    need(set(row['v7_modes'])=={'bit','affine','combined'},'All three saved V9 identity modes required')
    for mode in row['v7_modes'].values():
        status=mode['metadata']['status'];need(status in ('accepted','fallback','rejected'),'Unknown normalization status')
        if status=='accepted':forms.add(canonical(mode['normalized_formula']))
    return forms

def historical_inputs():
    root=ROOT/V9;prep=root/'preparation.json';need(sha(prep)==V9_PREP_SHA,'Frozen V9 input preparation differs')
    m=read(prep);bound={(root/e['path']).resolve():e['sha256'] for e in m['files']};bindings={prep:sha(prep)}
    def sealed(name):
        p=root/name;need(bound.get(p)==sha(p),'Historical input not bound to V9 freeze');bindings[p]=sha(p);return read(p)
    prior=sealed('consumed-input-ledger.json')['records'];new=sealed('candidates.json');identities=sealed('identity-analysis.json');recipe=sealed('recipe.json')
    need(len(prior)==2881 and len({r['formula'] for r in prior})==2881 and len(new)==48 and len(identities)==48,'Exact pre-reservation input panel required')
    aliases={canonical(r['formula']):{canonical(f) for f in r['accepted_forms']}|{r['formula']} for r in prior}
    imap={canonical(r['formula']):r for r in identities};need(len(imap)==48 and set(imap)=={r['formula'] for r in new},'V9 original/identity coverage differs')
    for row in new:aliases.setdefault(canonical(row['formula']),set()).update(accepted_forms(imap[row['formula']]))
    need(len(aliases)==2929,'Exact 2929-original pre-reservation reference required')
    models={};schemas={}
    point=root/'fit-attempt-0000/point-freeze.json';need(sha(point)==V9_POINT_SHA,'Frozen V9 point identity differs');bindings[point]=sha(point);freeze=read(point)
    for name,(relative,expected,count) in MODELS.items():
        artifact=ROOT/relative;schema=artifact.with_suffix('.json')
        need(artifact.is_file() and sha(artifact)==expected,'Exact local frozen model artifact required: '+name)
        expected_schema=recipe['baseline_model']['schema']['sha256'] if name=='V6' else freeze['schema_sha256']
        need(sha(schema)==expected_schema,'Frozen model metadata identity differs');d=read(schema);schemas[name]=d
        need(d['artifact_sha256']==expected and d['schema']=='isaforge-v6-model-v1' and d['kind']=='mapping_v6' and d['training_formula_count']==count and d['calibration']['status']=='uncalibrated','Adopted raw mapping predictor differs')
        need(d['feature_columns']==recipe['feature_columns'] and d['mapping_columns']==recipe['selected_columns'] and len(d['feature_columns'])==336 and len(d['mapping_columns'])==217 and d['configuration']==recipe['fixed_parameters'] and d['frozen_tool']==recipe['frozen_tool'],'Original 336/217 predictor/tool configuration differs')
        for filename,h in d['runtime_source_sha256'].items():
            p=ROOT/'isaforge'/filename;need(sha(p)==h,'Frozen inference source differs');bindings[p]=h
        bindings[artifact]=sha(artifact);bindings[schema]=sha(schema)
        models[name]={'artifact':record(artifact,ROOT),'metadata':record(schema,ROOT),'training_formula_count':count,'calibration_status':'uncalibrated','point_only':True}
    v6=schemas['V6'];p=ROOT/'results/2026-10-14-v5/development-features.json'
    need(sha(p)==v6['training_provenance']['development_features_sha256'],'Original training feature-input identity differs');bindings[p]=sha(p)
    records=read(p)['records'];indices=v6['training_provenance']['fit_indices']
    need(len(indices)==len(set(indices))==1665 and all(type(i) is int and 0<=i<len(records) for i in indices),'Exact original1665 training indices required')
    training6={canonical(records[i]['formula']) for i in indices};training9=training6|set(imap)
    need(len(training6)==1665 and len(training9)==1713 and training9<=set(aliases),'Exact predictor training original memberships required')
    # No training-data/target/point-prediction file is opened in this function.
    return aliases,{'V6':training6,'V9':training9},models,bindings

def overlap(candidates,aliases,training):
    indices={channel:defaultdict(set) for channel in ('saved_accepted_form','frozen_commutative_v4_normalization','ordered_skeleton')}
    parent={original:original for original in aliases}
    def find(original):
        while parent[original]!=original:
            parent[original]=parent[parent[original]];original=parent[original]
        return original
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    for original,forms in aliases.items():
        for form in {*forms,original}:
            indices['saved_accepted_form'][form].add(original);indices['frozen_commutative_v4_normalization'][equivalence_key(form)].add(original);indices['ordered_skeleton'][skeleton(form)].add(original)
    # Only declared identity channels create edges. Skeletons never do.
    for channel in ('saved_accepted_form','frozen_commutative_v4_normalization'):
        for originals in indices[channel].values():
            ordered=sorted(originals)
            for original in ordered[1:]:union(ordered[0],original)
    components=defaultdict(set)
    for original in aliases:components[find(original)].add(original)
    rows=[]
    for c in candidates:
        f=c['formula'];matches={'saved_accepted_form':sorted(indices['saved_accepted_form'].get(f,())),
            'frozen_commutative_v4_normalization':sorted(indices['frozen_commutative_v4_normalization'].get(equivalence_key(f),())),
            'ordered_skeleton':sorted(indices['ordered_skeleton'].get(skeleton(f),()))}
        functional=set(matches['saved_accepted_form'])|set(matches['frozen_commutative_v4_normalization'])
        closed=set().union(*(components[find(original)] for original in functional)) if functional else set()
        matches['accepted_identity_component_originals']=sorted(closed)
        rows.append({'candidate_id':c['candidate_id'],'formula':f,'pre_reservation_canonical_seen':f in aliases,'pre_reservation_matches':matches,
            'training_overlap':{name:{'canonical_seen':f in originals,'declared_alias_originals':sorted(functional&originals),
                'accepted_identity_component_originals':sorted(closed&originals)} for name,originals in training.items()}})
    return {'schema':'isaforge-v11-input-overlap-v1','reference_original_count':len(aliases),'records':rows,
        'accepted_identity_components':{'count':len(components),'largest_original_count':max(map(len,components.values()),default=0),
            'edges':'Shared accepted literal forms or frozen commutativity/V4 equivalence keys; transitive closure across reference originals only. No skeleton edges.'},
        'scope':'Pre-reservation2929 only. Literal/direct saved accepted forms and frozen commutativity/V4 matches are retained separately from component-derived transitive identity matches; skeletons are structural diagnostics only. No new SMT, vectors or exhaustive non-equivalence claim. All originals retained; later V13/V11 ledgers are not the reference.'}

def budget(n,m):
    integer(n);integer(m);b=(n+127)//128
    return {'status':'proposal-only-not-approved','unique_original_mappings':n,'program_formula_memberships':m,'rtl_output_comparisons':2148*n,
        'vectors_per_original':2148,'verification_batch_maximum':128,'verification_batches':b,'mapping_workers':2,'owned_worker_timeout_seconds':360,
        'timeout_envelope_seconds_excluding_packaging':360*(b+(n+1)//2),'maximum_cold_feature_channels':3*n,
        'feature_jobs_released':0,'prediction_jobs_released':0,'target_jobs_released':0,'fits_released':0,
        'requires_separate_release':'Full-pool byte/free-space caps, fixed vector seed, exact feature/native tools including SDK/compiler, owned failure retention, saved prediction freeze, source/Git approval and independent raw audit must be sealed before their respective jobs.'}

def prepare(source_root,audit_path,audit_sha256,output):
    source_root=Path(source_root).resolve();output=Path(output).resolve()
    need(source_root.is_relative_to(ROOT/'results') and output.is_relative_to(ROOT/'results') and not output.is_relative_to(source_root) and not output.exists(),'Fresh separate repository result root required')
    records,audit,bindings=authenticate_recovery(source_root,audit_path,audit_sha256)
    memberships,candidates,copies=pool(source_root,records);aliases,training,models,historical=historical_inputs();bindings.update(historical)
    need(len(candidates)==integer(audit['unique_canonical_formulas']) and sum(m['canonical_count'] for m in memberships)==integer(audit['program_formula_rows']),'Independent audit/pool denominators differ')
    source_files=sources();bindings.update({p:sha(p) for p in source_files});check_hashes(bindings)
    output.mkdir();produced=[]
    try:
        for name,p in copies.items():
            target=output/'original-candidate-files'/(name+'.json');target.parent.mkdir(exist_ok=True);target.write_bytes(p.read_bytes());need(sha(target)==sha(p),'Original candidate copy differs');produced.append(target)
        for name,value in [('memberships.json',memberships),('candidates.json',candidates),('overlap.json',overlap(candidates,aliases,training)),
            ('pre-reservation-reference.json',[{'formula':f,'accepted_forms':sorted(forms)} for f,forms in sorted(aliases.items())]),
            ('predictors.json',models),('proposed-budget.json',budget(len(candidates),sum(m['canonical_count'] for m in memberships)))]:
            p=output/name;write(p,value);produced.append(p)
        check_hashes(bindings)
        manifest={'schema':'isaforge-v11-model-comparison-inputs-v1','status':'prepared-inputs-only','prepared_at_utc':now(),
            'source_root':os.path.relpath(source_root,output),'reviewed_audit':record(audit_path,output),'audit_independence':audit['independence'],
            'program_count':6,'family_count':5,'empty_programs':[m['program'] for m in memberships if m['status']=='empty'],
            'unique_canonical_originals':len(candidates),'program_formula_memberships':sum(m['canonical_count'] for m in memberships),
            'original_endpoint':'undefined: empty recursion MAE; never zero','amended_endpoint':'V11b-E1: five-family/equal-eligible-program MAE only after complete frozen predictions and full original-target labels',
            'selection':'All audited originals retained regardless of familiarity, predicted/actual area, shared helpers or cross-program membership. No outcome-dependent filtering.',
            'files':[record(p,output) for p in sorted({*bindings,*produced})],
            'source_paths':[os.path.relpath(p,output) for p in source_files],
            'calls':{'native_jobs':0,'feature_extractions':0,'model_artifacts_loaded':0,'predictions':0,'target_label_files_opened':0,'fits':0,'new_solver_queries':0},
            'authentication_scope':'Caller-reviewed independent report digest plus reauthenticated byte/package closure. No second raw parser/ELF/fusion replay; shared helper limitations are preserved verbatim.'}
        write(output/'preparation.json',manifest);return manifest
    except BaseException as e:write(output/'preparation-failure.json',{'error':repr(e),'at_utc':now(),'native_jobs':0,'new_labels':0});raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--audit-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=prepare(a.source_root,a.audit,a.audit_sha256,a.output)
    print(json.dumps({k:result[k] for k in ('status','program_count','family_count','unique_canonical_originals','program_formula_memberships','calls')},indent=2))
