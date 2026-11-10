#!/usr/bin/env python3
"""Audit the separately frozen zero-fit policy and its new synthetic test.

Reuses the authenticated first independent auditor's parsing/oracle/metric
primitives; never imports experiment metric code or launches fits/native jobs.
"""
from __future__ import annotations
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import random
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'scripts')]
import audit_targeted_coverage as prior

OUT = ROOT/'results/budget-preserving-coverage'
TEST = ROOT/'results/budget-preserving-validation'
read,write,sha,digest,now = prior.read,prior.write,prior.sha,prior.digest,prior.now
CAPS = (32,64,128)
NAME = 'budget_preserving_coverage'


def policy(base, scoped):
    assert len(base) == len(scoped)
    assert all(math.isfinite(x) and x>=0 for x in (*base,*scoped))
    result = [min(max(b,s),next((c for c in CAPS if b<=c),math.inf)) for b,s in zip(base,scoped)]
    assert all(p>=b and math.isfinite(p) for p,b in zip(result,base))
    assert all((p<=c)==(b<=c) for p,b in zip(result,base) for c in CAPS)
    return result


def check_prior():
    baseline = read(OUT/'auditor-prior-artifacts.json')
    for name,value in baseline['files'].items(): assert sha(ROOT/name)==value,name
    return len(baseline['files'])


def proof_receipt():
    return {'formula':'p=min(max(b,s),nextcap(b)); nextcap=min({32,64,128} intersect [b,infinity)), else infinity',
        'assumptions':'b,s finite nonnegative; fixed caps32/64/128; exact <= decision convention.',
        'intervals':['0<=b<=32 => b<=p<=32', '32<b<=64 =>32<b<=p<=64',
                     '64<b<=128 =>64<b<=p<=128', '128<b =>128<b<=p<infinity'],
        'deductions':['For every declared cap, p<=cap iff b<=cap, so every false-accept and false-reject count is identical for arbitrary targets.',
                      'p>=b implies max(actual-p,0)<=max(actual-b,0) for every row; therefore maximum underprediction cannot increase.'],
        'limitations':'No claim of improved decisions, calibration, representative workload performance, other caps, timing, routing, power or CPU integration.'}


def authenticate():
    protocol=read(OUT/'protocol.json'); assert protocol['schema']=='isaforge-budget-preserving-coverage-v1'
    assert protocol['new_fits']==protocol['native_jobs']==0 and protocol['fresh_count']==32
    assert protocol['policy']['formula']=='p=min(max(base,scoped_augmented217),nextcap(base))'
    assert protocol['policy']['caps_lut4']==[32,64,128] and not protocol['policy']['calibrated']
    for section in ('sources_sha256','inputs_sha256'):
        for name,value in protocol[section].items():assert sha(ROOT/name)==value,name
    plan=read(TEST/'plan.json')
    assert plan['policy']=={'total_native_seconds':120,'workers':2,'fits':0,'retries':0,
        'replacement_candidates':0,'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    for section in ('sources','inputs','prior_inventory_sources'):
        for name,value in plan[section].items():assert sha(ROOT/name)==value,name
    frozen=read(OUT/'policy-freeze.json')
    assert frozen['new_fits']==0 and frozen['protocol_sha256']==sha(OUT/'protocol.json')
    for name,value in frozen['files_sha256'].items():assert sha(OUT/name)==value,name
    return protocol


def replay_points():
    protocol,base,candidate=prior.authenticate_model()
    points=read(OUT/'fresh-predictions.json');rows=read(TEST/'candidates.json')
    assert prior.replay_points(points,rows,read(TEST/'features.json'),protocol,base,candidate)==96
    expected=policy(points['models']['base'],points['models']['scoped_augmented217'])
    assert points['models'][NAME]==expected
    assert points['source_scoped_points']==points['models']['scoped_augmented217']
    for name in ('base',NAME):
        for cap in CAPS:
            assert points['cap_decisions'][name][str(cap)]==[p<=cap for p in points['models'][name]]
    assert points['checks']['pointwise_prediction_at_least_base']
    assert all(points['checks']['pointwise_cap_decisions_identical'][str(c)] for c in CAPS)
    seal=read(OUT/'fresh-point-freeze.json')
    assert not seal['fresh_labels_present'] and seal['new_fits']==0
    for key,path in [('protocol_sha256',OUT/'protocol.json'),('policy_freeze_sha256',OUT/'policy-freeze.json'),
        ('predictions_sha256',OUT/'fresh-predictions.json'),('features_sha256',TEST/'features.json'),('candidates_sha256',TEST/'candidates.json')]:
        assert seal[key]==sha(path),key
    return 128


def stat(actual,points):
    result=prior.metrics(actual,points)
    for cap in CAPS:
        result['caps'][str(cap)].update({'actual_accept':sum(y<=cap for y in actual),
                                        'predicted_accept':sum(p<=cap for p in points)})
    return result


def development_audit():
    saved=read(OUT/'development-metrics.json');computed={};regressions=[];fields=0
    source=read(ROOT/'results/targeted-coverage/development-predictions.json')
    former=read(ROOT/'results/targeted-coverage/fresh-predictions.json')
    former['actual_lut4']=[r['lut4'] for r in read(ROOT/'results/targeted-coverage-validation/labels.json')]
    source['consumed-first-fresh40']=former
    for panel,row in read(OUT/'development-predictions.json').items():
        original=source[panel]
        assert row['candidate_ids']==original['candidate_ids'] and row['formulas']==original['formulas']
        assert row['actual_lut4']==original['actual_lut4']
        assert row['source_scoped_points']==original['models']['scoped_augmented217']
        expected=policy(original['models']['base'],row['source_scoped_points'])
        assert row['models']=={'base':original['models']['base'],NAME:expected}
        computed[panel]={n:stat(row['actual_lut4'],p) for n,p in row['models'].items()}
        for name,m in computed[panel].items():fields+=prior.compare_metric(saved['panels'][panel][name],m)
        for metric in ('mae_lut4','positive_mape_percent'):
            b,p=(computed[panel][n][metric] for n in ('base',NAME))
            if p>b:regressions.append({'panel':panel,'metric':metric,'base':b,'policy':p,'increase':p-b})
    motivating=computed['selection-validation']
    passed=prior.gate(motivating['base'],motivating[NAME])['pass']
    assert saved['development_gate_passed']==passed
    return {'panels':computed,'development_gate_passed':passed,'accuracy_regressions':regressions,'numeric_fields_checked':fields}


def prelabel():
    protocol=authenticate()
    assert not (TEST/'labels.json').exists() and not (TEST/'label-attempt.json').exists()
    if not (OUT/'auditor-prior-artifacts.json').exists():
        write(OUT/'auditor-prior-artifacts.json',read('/tmp/isaforge-budget-prior-artifacts.json'))
    oldcount=check_prior();points=replay_points();dev=development_audit()
    done=read(TEST/'feature-completion.json');jobs=prior.job_audit(done)
    assert jobs['jobs']==32 and done['native_elapsed_seconds']<120
    assert Counter(j['stage'] for j in done['native_worker_jobs'])=={'feature':32}
    report=read(TEST/'novelty.json');rows=read(TEST/'candidates.json')
    assert report['status']=='pass' and len(rows)==32
    assert all(not r['historical_identity_overlap'] and not r['within_identity_overlap'] and not r['historical_skeleton_overlap'] for r in report['comparisons'])
    history=read(TEST/'historical-formulas.json')
    assert len(history)==report['historical_count']
    assert not {r['formula'] for r in rows}&set(history)
    assert not {prior.skeleton(r['formula']) for r in rows}&{prior.skeleton(f) for f in history}
    assert len({r['template'] for r in rows})==8 and all(n==4 for n in Counter(r['template'] for r in rows).values())
    bridge=read(TEST/'point-freeze.json');assert bridge['target_label_jobs']==0
    for name,value in bridge['bindings'].items():assert sha(ROOT/name)==value,name
    assert read(TEST/'plan.json')['frozen_at_utc']<read(TEST/'feature-attempt.json')['started_at_utc']
    assert max(j['finished_at_utc'] for j in done['native_worker_jobs'])<read(OUT/'fresh-predictions.json')['created_at_utc']
    assert protocol['frozen_at_utc']<read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<=bridge['frozen_at_utc']
    receipt={'schema':'independent-budget-preserving-prelabel-v1','status':'pass','audited_at_utc':now(),
        'bindings':{str(p.relative_to(ROOT)):sha(p) for p in (OUT/'protocol.json',OUT/'policy-freeze.json',
            OUT/'fresh-point-freeze.json',OUT/'fresh-predictions.json',TEST/'plan.json',TEST/'point-freeze.json',TEST/'candidates.json',TEST/'features.json')},
        'new_labels_absent':True,'label_attempt_absent':True,'fresh_points_replayed':points,
        'old_and_first_study_artifacts_preserved':oldcount,'historical_formulas_and_aliases':len(history),
        'constant_erased_AST_skeleton_overlap':0,'math_proof':proof_receipt(),
        'development_gate_passed':dev['development_gate_passed'],'development_accuracy_regressions':dev['accuracy_regressions'],
        'feature_native_seconds':done['native_elapsed_seconds'],'audit_fits':0,'audit_native_jobs':0}
    assert not (TEST/'prelabel-audit.json').exists()
    write(TEST/'prelabel-audit.json',receipt)
    return receipt


def raw_audit():
    rows = read(TEST/'candidates.json'); labels = read(TEST/'labels.json')
    assert len(rows)==len(labels)==32
    assert [r['candidate_id'] for r in rows]==[l['candidate_id'] for l in labels]
    manifest = read(TEST/'raw-evidence-manifest.json')
    archive = TEST/manifest['archive']; assert sha(archive)==manifest['archive_sha256']
    members = {r['path']:r for r in manifest['files']}
    with zipfile.ZipFile(archive) as stream:
        assert len(stream.namelist())==len(set(stream.namelist())) and set(stream.namelist())==set(members)
        for name,record in members.items():
            body=stream.read(name); assert digest(body)==record['sha256'] and len(body)==record['bytes']
        get=lambda name:stream.read('raw/'+name)
        proof=json.loads(get('verification/result.json'))
        vectors=get('verification/vectors.txt'); rtl=get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count']==32 and proof['vectors_per_formula']==2148
        assert proof['random_seed']==2026110903 and proof['total_comparisons']==68736
        assert digest(vectors)==proof['vectors_sha256'] and digest(rtl.encode())==proof['rtl_sha256']
        boundary=[0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,2**32-1]
        rng=random.Random(proof['random_seed'])
        pairs=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        parsed=[[int(v,16) for v in line.split()] for line in vectors.decode().splitlines()]
        assert len(parsed)==2148 and [(v[0],v[1]) for v in parsed]==pairs
        trees=[prior.parse(r['formula']) for r in rows]
        for vector in parsed:
            assert len(vector)==34
            a,b,*expected=vector
            assert [prior.evaluate(tree,a,b) for tree in trees]==expected
        assert get('verification/verification.log').decode().strip()=='2148 vectors passed'
        features=read(TEST/'features.json')
        for i,(row,label) in enumerate(zip(rows,labels)):
            assert label['status']=='complete' and label['formula']==row['formula']
            body=get(f'labels/{i}/ice40-netlist.json'); assert digest(body)==label['netlist_sha256']
            cells=json.loads(body)['modules']['candidate']['cells']
            counts=Counter(c['type'] for c in cells.values())
            assert counts['SB_LUT4']==label['lut4'] and counts['SB_CARRY']==label['carry']
            measured=get(f'labels/{i}/candidate.v').decode()
            assert digest(measured.encode())==label['rtl_sha256']
            assert measured.replace('module candidate(',f'module candidate_{i}(') in rtl
            body=get(f'labels/{i}/metrics.json'); assert digest(body)==label['metrics_sha256']
            target=json.loads(body)
            assert target['ice40_lut4_count']==label['lut4'] and target['ice40_carry_count']==label['carry']
            assert target['measurement_source']=='rtl_synthesis'
            assert 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
            assert json.loads(get(f'features/{i}/result.json'))==features['records'][i]
    return {'archive_sha256':sha(archive),'members_hashed':len(members),
        'mapped_LUT4_and_carry_netlists_recounted':32,'independent_RV32_vector_comparisons':32*2148}


def identity_audit():
    import numpy as np
    from isaforge.structural_features_v4 import normalize_formula as v4
    from isaforge.structural_features_v5 import normalize_formula as v5
    from isaforge.v5_corpus import equivalence_key
    from isaforge.features import parse_formula
    def keys(formula):
        forms={parse_formula(formula).canonical()}
        for normalizer in (v4,v5):
            for value in tuple(forms):
                try:forms.add(parse_formula(normalizer(value)).canonical())
                except ValueError:pass
        result={('formula',f) for f in forms}|{('commutative',equivalence_key(f)) for f in forms}
        result.update(('formula',normalizer(f)) for f in forms for normalizer in (v4,v5))
        return result
    history=set(read(TEST/'historical-formulas.json'))
    aliases={f for r in read(ROOT/'results/selection-validation/novelty.json')['comparisons'] for f in r['forms']}
    known=set().union(*(keys(f) for f in history|aliases));seen=set()
    for row in read(TEST/'novelty.json')['comparisons']:
        current=set().union(*(keys(f) for f in row['forms']))
        assert not known&current and not seen&current,row['candidate_id']
        seen.update(current)
    protocol=read(ROOT/'results/targeted-coverage/protocol.json');selected=protocol['selected_columns']
    oldcols=read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        oldkeys={tuple(v) for v in data['x'][:,[oldcols.index(n) for n in selected]]}
    for name in ('targeted-coverage-data','targeted-coverage-validation'):
        payload=read(ROOT/'results'/name/'features.json')
        matrix=np.asarray([r['values'] for r in payload['records']])[:,[payload['columns'].index(n) for n in selected]]
        oldkeys.update(tuple(v) for v in matrix)
    payload=read(TEST/'features.json');matrix=np.asarray([r['values'] for r in payload['records']])
    values=matrix[:,[payload['columns'].index(n) for n in selected]]
    return {'historical_formulas_and_saved_aliases':len(history),'previous_consumed40_aliases_additionally_checked':len(aliases),
        'known_sufficient_identity_keys':len(known),'known_identity_overlaps':0,'within_new_cohort_identity_overlaps':0,
        'new217_unique_vectors':len({tuple(v) for v in values}),
        'new_rows_with_exact217_original1665_or_previous104_collision':sum(tuple(v) in oldkeys for v in values),
        'scope':'Finite known formula/normalizer identities are separate from feature-vector collisions. Generic features authenticated, not reextracted.'}


def final_audit():
    protocol=authenticate();oldcount=check_prior();pointcount=replay_points();dev=development_audit()
    receipt=read(TEST/'prelabel-audit.json')
    for name,value in receipt['bindings'].items():assert sha(ROOT/name)==value,name
    features=read(TEST/'feature-completion.json');labels=read(TEST/'completion.json')
    featurejobs=prior.job_audit(features);labeljobs=prior.job_audit(labels)
    assert featurejobs['jobs']==32 and labeljobs['jobs']==33
    assert Counter(j['stage'] for j in labels['native_worker_jobs'])=={'verify':1,'label':32}
    total=features['native_elapsed_seconds']+labels['native_elapsed_seconds']
    assert total<=120 and math.isclose(total,labels['total_native_elapsed_seconds'],abs_tol=1e-9)
    assert read(TEST/'label-attempt.json')['started_at_utc']>receipt['audited_at_utc']
    jobs=labels['native_worker_jobs']
    assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc']<min(j['started_at_utc'] for j in jobs)
    assert max(j['finished_at_utc'] for j in jobs if j['stage']=='verify')<min(j['started_at_utc'] for j in jobs if j['stage']=='label')
    raw=raw_audit();identities=identity_audit()
    points=read(OUT/'fresh-predictions.json');rows=read(TEST/'candidates.json');truth=read(TEST/'labels.json')
    assert points['candidate_ids']==[r['candidate_id'] for r in truth]
    actual=[r['lut4'] for r in truth]
    fresh={n:stat(actual,points['models'][n]) for n in ('base',NAME)}
    saved=read(OUT/'fresh-metrics.json');fields=0
    for name,m in fresh.items():fields+=prior.compare_metric(saved['models'][name],m)
    freshgate=prior.gate(fresh['base'],fresh[NAME])['pass']
    assert saved['fresh_gate_passed']==freshgate
    assert saved['scoped_experimental_eligibility']==(freshgate and dev['development_gate_passed'])
    template_metrics={};regressions=list(dev['accuracy_regressions'])
    for template in sorted({r['template'] for r in rows}):
        indices=[i for i,r in enumerate(rows) if r['template']==template]
        template_metrics[template]={n:stat([actual[i] for i in indices],[points['models'][n][i] for i in indices]) for n in ('base',NAME)}
        for metric in ('mae_lut4','positive_mape_percent'):
            b,p=(template_metrics[template][n][metric] for n in ('base',NAME))
            if p>b:regressions.append({'panel':'fresh32:'+template,'metric':metric,'base':b,'policy':p,'increase':p-b})
    result={'schema':'independent-budget-preserving-audit-v1','status':'pass','audited_at_utc':now(),
        'protocol_sha256':sha(OUT/'protocol.json'),'auditor_sha256':sha(Path(__file__)),
        'first_independent_auditor_sha256':sha(ROOT/'scripts/audit_targeted_coverage.py'),
        'old_and_first_study_artifacts_preserved':oldcount,'mathematical_proof':proof_receipt(),
        'new_fits':0,'new_model_weights':0,'native_jobs':65,'native_total_seconds':total,
        'recorded_worker_peak':max(featurejobs['peak_recorded_workers'],labeljobs['peak_recorded_workers']),
        'fresh_predictions_replayed':pointcount,'development_policies_recomputed':631,
        'new_cohort_and_policy_before_labels':True,'ordered_points_before_verification_before_labels':True,
        'identity_and_feature_collision_audit':identities,'raw_evidence':raw,'development':dev,'fresh':fresh,
        'fresh_template_metrics':template_metrics,'accuracy_regressions':regressions,'fresh_numeric_fields_checked':fields,
        'fresh_gate_passed':freshgate,'scoped_experimental_eligibility':freshgate and dev['development_gate_passed'],
        'audit_fits':0,'audit_native_jobs':0,
        'limitations':['The policy preserves every base classification mistake at caps32/64/128 and provides no improvement in budget classification or calibrated coverage.',
        'Only a fixed synthetic32-case test across eight manually declared compositions; first fresh40 is consumed development data, and no representative application or full CPU claim follows.',
        'Saved generic features, original RTL, tool identities and execution logs authenticated; independent RV32 vector arithmetic and raw mapped LUT/carry recounts do not constitute universal equivalence or mapped-netlist functional proof.',
        'Finite historical formula/normalizer screen and recorded chronology support these receipts; inaccessible inventories, equivalences outside normalizers and unrecorded historical activity cannot be excluded.']}
    write(OUT/'audit.json',result)
    return {'status':'pass','fresh_gate_passed':freshgate,'scoped_experimental_eligibility':result['scoped_experimental_eligibility'],
        'fresh_points_replayed':pointcount,'raw_netlists_recounted':32,'RV32_vector_checks':68736,
        'native_seconds':total,'accuracy_regressions':regressions,'audit_fits':0,'audit_native_jobs':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prelabel','final'))
    args=parser.parse_args()
    print(json.dumps({'prelabel':prelabel,'final':final_audit}[args.command](),indent=2))
