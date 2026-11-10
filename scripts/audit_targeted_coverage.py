#!/usr/bin/env python3
"""Independent retained-evidence auditor: never fit or start native jobs.

Metrics, gates, original-AST routing, RV32 arithmetic and resource recounts are
implemented here rather than imported from the experiment runners.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import itertools
from pathlib import Path
import random
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT = ROOT / 'results/targeted-coverage'
TRAIN = ROOT / 'results/targeted-coverage-data'
TEST = ROOT / 'results/targeted-coverage-validation'
CAPS = (32, 64, 128)
MASK = 2**32 - 1


def read(path): return json.loads(Path(path).read_text())
def digest(body): return hashlib.sha256(body).hexdigest()
def sha(path): return digest(Path(path).read_bytes())
def now(): return datetime.now(timezone.utc).isoformat()
def write(path, body):
    Path(path).write_text(json.dumps(body, indent=2, allow_nan=False) + '\n')


def parse(formula):
    tokens = re.findall(r'[a-z][a-z0-9_]*|-?\d+|[(),]', formula)
    index = 0
    def walk():
        nonlocal index
        token = tokens[index]; index += 1
        if index < len(tokens) and tokens[index] == '(':
            index += 1; args = [walk()]
            while tokens[index] == ',': index += 1; args.append(walk())
            assert tokens[index] == ')'; index += 1
            return token, tuple(args)
        return int(token) if re.fullmatch(r'-?\d+', token) else token
    result = walk(); assert index == len(tokens)
    return result


def nodes(node):
    yield node
    if isinstance(node, tuple):
        for child in node[1]: yield from nodes(child)


def route(formula):
    tree = parse(formula); parts = list(nodes(tree))
    ops = {n[0] for n in parts if isinstance(n, tuple)}
    variable = any(isinstance(n, tuple) and n[0] in ('sll', 'srl', 'sra')
                   and any(x in ('in0', 'in1') for x in nodes(n[1][1]))
                   for n in parts)
    arithmetic_xor = bool(ops & {'add', 'addi', 'sub'}) and bool(ops & {'xor', 'xori'})
    return variable or (arithmetic_xor and not ops & {'mul', 'mulh', 'mulhu', 'mulhsu'})


def skeleton(formula):
    def convert(node):
        if isinstance(node, int): return '#'
        if isinstance(node, str): return node
        return node[0], tuple(convert(child) for child in node[1])
    return repr(convert(parse(formula)))


def evaluate(node, a, b):
    if isinstance(node, int): return node & MASK
    if isinstance(node, str):
        assert node in ('in0', 'in1'); return a if node == 'in0' else b
    op, args = node; aa = evaluate(args[0], a, b)
    bb = evaluate(args[1], a, b) if len(args) > 1 else 0
    signed = lambda n: n - 2**32 if n >= 2**31 else n
    if op == 'lui': out = aa
    elif op in ('add', 'addi'): out = aa + bb
    elif op == 'sub': out = aa - bb
    elif op in ('and', 'andi'): out = aa & bb
    elif op in ('or', 'ori'): out = aa | bb
    elif op in ('xor', 'xori'): out = aa ^ bb
    elif op in ('sll', 'slli'): out = aa << (bb & 31)
    elif op in ('srl', 'srli'): out = aa >> (bb & 31)
    elif op in ('sra', 'srai'): out = signed(aa) >> (bb & 31)
    elif op in ('slt', 'slti'): out = int(signed(aa) < signed(bb))
    elif op in ('sltu', 'sltiu'): out = int(aa < bb)
    elif op == 'mul': out = aa * bb
    elif op == 'mulh': out = (signed(aa) * signed(bb)) >> 32
    elif op == 'mulhu': out = (aa * bb) >> 32
    elif op == 'mulhsu': out = (signed(aa) * bb) >> 32
    else: raise AssertionError(op)
    return out & MASK


def metrics(actual, predicted):
    assert len(actual) == len(predicted) and len(actual)
    assert all(math.isfinite(x) and x >= 0 for x in (*actual, *predicted))
    errors = [abs(y-p) for y, p in zip(actual, predicted)]
    positive = [e/y for e, y in zip(errors, actual) if y > 0]
    return {'count': len(actual), 'mae_lut4': sum(errors)/len(errors),
            'positive_mape_percent': 100*sum(positive)/len(positive) if positive else None,
            'positive_count': len(positive), 'zero_count': len(actual)-len(positive),
            'maximum_underprediction_lut4': max(0, max(y-p for y,p in zip(actual,predicted))),
            'caps': {str(c): {'false_accept': sum(p <= c < y for y,p in zip(actual,predicted)),
                            'false_reject': sum(y <= c < p for y,p in zip(actual,predicted))}
                     for c in CAPS}}


def gate(base, candidate, accuracy=True):
    improved = (candidate['mae_lut4'] < base['mae_lut4'] and
                candidate['positive_mape_percent'] < base['positive_mape_percent'])
    tails = candidate['maximum_underprediction_lut4'] <= base['maximum_underprediction_lut4']
    caps = all(candidate['caps'][str(c)][kind] <= base['caps'][str(c)][kind]
               for c in CAPS for kind in ('false_accept', 'false_reject'))
    return {'accuracy_improved': improved, 'maximum_underprediction_no_worse': tails,
            'all_cap_error_counts_no_worse': caps,
            'pass': (improved or not accuracy) and tails and caps}


def compare_metric(saved, computed):
    """Check all independent metric fields; runner may retain extra descriptions."""
    comparisons = 0
    for key, value in computed.items():
        assert key in saved, key
        if isinstance(value, dict): comparisons += compare_metric(saved[key], value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert math.isclose(saved[key], value, rel_tol=1e-12, abs_tol=1e-12), (key,saved[key],value)
            comparisons += 1
        else: assert saved[key] == value, (key, saved[key], value)
    return comparisons


def check_prior():
    baseline = read(OUT/'auditor-prior-artifacts.json')
    changed = [name for name, value in baseline['files'].items() if sha(ROOT/name) != value]
    assert not changed, changed
    return len(baseline['files'])


def archive_audit(folder):
    rows = read(folder/'candidates.json'); labels = read(folder/'labels.json')
    assert len(rows) == len(labels)
    assert [r['candidate_id'] for r in rows] == [l['candidate_id'] for l in labels]
    assert all(l['status'] == 'complete' and l['formula'] == r['formula'] for l,r in zip(labels,rows))
    manifest = read(folder/'raw-evidence-manifest.json'); archive = folder/manifest['archive']
    assert sha(archive) == manifest['archive_sha256']
    members = {r['path']:r for r in manifest['files']}; vector_checks = 0
    with zipfile.ZipFile(archive) as stream:
        get = lambda name: stream.read('raw/'+name)
        assert len(stream.namelist()) == len(set(stream.namelist()))
        assert set(stream.namelist()) == set(members)
        for name, record in members.items():
            body = stream.read(name)
            assert digest(body) == record['sha256'] and len(body) == record['bytes'], name
        proof = json.loads(get('verification/result.json'))
        vectors = get('verification/vectors.txt'); rtl = get('verification/verification.v').decode()
        assert proof['verified'] and proof['formula_count'] == len(rows)
        assert digest(vectors) == proof['vectors_sha256'] and digest(rtl.encode()) == proof['rtl_sha256']
        trees = [parse(r['formula']) for r in rows]
        parsed = [[int(t,16) for t in line.split()] for line in vectors.decode().splitlines()]
        assert len(parsed) == proof['vectors_per_formula'] == 2148
        assert proof['total_comparisons'] == len(parsed)*len(rows)
        seed = 2026110902 if folder == TRAIN else 2026110903
        assert proof['random_seed'] == seed
        boundary = [0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,MASK]
        rng = random.Random(seed)
        pairs = list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        assert [(v[0],v[1]) for v in parsed] == pairs
        assert get('verification/verification.log').decode().strip() == '2148 vectors passed'
        for values in parsed:
            assert len(values) == len(rows)+2
            a,b,*expected = values
            for node,want in zip(trees,expected):
                assert evaluate(node,a,b) == want
                vector_checks += 1
        for i,label in enumerate(labels):
            body = get(f'labels/{i}/ice40-netlist.json')
            assert digest(body) == label['netlist_sha256']
            net = json.loads(body); counts = Counter(c['type'] for c in net['modules']['candidate']['cells'].values())
            assert counts['SB_LUT4'] == label['lut4'] and counts['SB_CARRY'] == label['carry']
            measured = get(f'labels/{i}/candidate.v').decode()
            assert digest(measured.encode()) == label['rtl_sha256']
            assert measured.replace('module candidate(',f'module candidate_{i}(') in rtl
            body = get(f'labels/{i}/metrics.json'); target = json.loads(body)
            assert digest(body) == label['metrics_sha256']
            assert target['ice40_lut4_count'] == label['lut4'] and target['ice40_carry_count'] == label['carry']
            assert target['measurement_source'] == 'rtl_synthesis'
            assert 'synth_ice40 -top candidate' in get(f'labels/{i}/ice40.ys').decode()
        features = read(folder/'features.json')
        for i,record in enumerate(features['records']):
            assert json.loads(get(f'features/{i}/result.json')) == record
    return {'mapped_netlists_recounted':len(labels), 'RV32_vector_comparisons':vector_checks,
            'raw_archive_sha256':sha(archive),'archive_members_hashed':len(members)}


def authenticate_training_protocol():
    protocol = read(OUT/'protocol.json')
    assert protocol['primary_candidate'] == 'augmented217'
    assert protocol['secondary_candidate'] == 'scoped_augmented217'
    assert protocol['planned_fits'] == 1 and protocol['maximum_fits'] <= 3
    assert protocol['maximum_wall_seconds'] <= 120
    assert protocol['workers'] == protocol['native_threads'] == 1
    assert protocol['original_training_count'] == 1665 and protocol['new_training_count'] == 64
    assert protocol['fresh_test_count'] == 40 and protocol['consumed40_training_rows'] == 0
    assert protocol['configuration'] == {'n_estimators':300,'min_samples_leaf':1,
                                       'max_features':1.0,'n_jobs':1,'random_state':2026101401}
    assert len(protocol['feature_columns']) == len(set(protocol['feature_columns'])) == 336
    assert len(protocol['selected_columns']) == len(set(protocol['selected_columns'])) == 217
    for key in ('sources_sha256','inputs_sha256'):
        for name,value in protocol[key].items(): assert sha(ROOT/name) == value, name
    return protocol


def preflight():
    protocol = authenticate_training_protocol(); plan = read(TRAIN/'plan.json')
    assert not any((f/'labels.json').exists() for f in (TRAIN,TEST))
    assert not (TRAIN/'training-attempt.json').exists() and not (OUT/'run-start.json').exists()
    assert plan['policy'] == {'total_native_seconds':1200,'training_native_seconds':600,
        'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
    amendment = read(TRAIN/'pre-native-amendment.json')
    assert amendment['original_plan_sha256'] == sha(TRAIN/'plan.json')
    assert amendment['target_label_jobs'] == amendment['native_feature_jobs'] == 0
    for section in ('sources','inputs','prior_inventory_sources'):
        for name,value in plan[section].items(): assert sha(ROOT/name) == value, name
    freshplan = read(TEST/'plan.json')
    assert freshplan['shared_training_plan_sha256'] == sha(TRAIN/'plan.json')
    assert freshplan['pre_native_amendment_sha256'] == sha(TRAIN/'pre-native-amendment.json')
    rows = {kind:read(folder/'candidates.json') for kind,folder in (('train',TRAIN),('test',TEST))}
    assert len(rows['train']) == 64 and len(rows['test']) == 40
    joint = rows['train']+rows['test']
    assert len({r['formula'] for r in joint}) == len({r['candidate_id'] for r in joint}) == 104
    history = read(TRAIN/'historical-formulas.json')
    priorhistory = read(ROOT/'results/selection-validation/historical-formulas.json')
    prior40 = read(ROOT/'results/selection-validation/candidates.json')
    assert set(history) == set(priorhistory)|{r['formula'] for r in prior40}
    assert not set(history)&{r['formula'] for r in joint}
    train_skeletons = {skeleton(r['formula']) for r in rows['train']}
    assert not train_skeletons & {skeleton(r['formula']) for r in rows['test']}
    assert all(n==8 for n in Counter(r['template'] for r in rows['train']).values())
    assert len({r['template'] for r in rows['train']}) == 8
    assert len({r['template'] for r in rows['test']}) == 10
    assert all(n==4 for n in Counter(r['template'] for r in rows['test']).values())
    assert sum(r['template'].startswith('heldout_') for r in rows['test']) == 24
    for kind,folder in (('train',TRAIN),('test',TEST)):
        report = read(folder/'novelty.json')
        assert report['status'] == 'pass' and report['historical_count'] == len(history)
        assert [r['candidate_id'] for r in report['comparisons']] == [r['candidate_id'] for r in rows[kind]]
        assert all(not r['historical_identity_overlap'] and not r['across_cohort_identity_overlap']
                   for r in report['comparisons'])
    if not (OUT/'auditor-prior-artifacts.json').exists():
        write(OUT/'auditor-prior-artifacts.json', read('/tmp/isaforge-coverage-prior-artifacts.json'))
    oldcount = check_prior()
    receipt = {'schema':'independent-targeted-preflight-v1','status':'pass','audited_at_utc':now(),
        'bindings':{str(p.relative_to(ROOT)):sha(p) for p in (TRAIN/'plan.json',TRAIN/'pre-native-amendment.json',
            TEST/'plan.json',TRAIN/'candidates.json',TEST/'candidates.json',TRAIN/'novelty.json',TEST/'novelty.json',OUT/'protocol.json')},
        'old_artifacts_preserved':oldcount,'joint_rows':104,'training_rows':64,'test_rows':40,
        'test_training_constant_erased_AST_skeleton_overlap':0,'heldout_composition_rows':24,'control_rows':16,
        'historical_inventory_count':len(history),'prior_consumed_transfer_rows':40,
        'formula_and_saved_normalizer_identity_screen_authenticated':True,
        'no_new_labels_or_attempts_present':True,'audit_fits':0,'audit_native_jobs':0,
        'scope':'Original AST compositions differ from training; finite inherited formula/normalizer screen, not exhaustive semantic or application independence.'}
    assert not (TRAIN/'preflight-audit.json').exists()
    write(TRAIN/'preflight-audit.json',receipt)
    return receipt


def replay_points(payload, rows, features, protocol, base, candidate):
    import numpy as np
    assert payload['candidate_ids'] == [r['candidate_id'] for r in rows]
    assert payload['formulas'] == [r['formula'] for r in rows]
    assert [r['formula'] for r in features['records']] == payload['formulas']
    names = features['columns']; values = np.asarray([r['values'] for r in features['records']])
    assert values.shape == (len(rows),len(names)) and np.isfinite(values).all() and (values>=0).all()
    selected = values[:,[names.index(n) for n in protocol['selected_columns']]]
    zero = values[:,names.index('original_gate_count')] == 0
    bp = np.maximum(base.estimator.predict(selected),0); bp[zero] = 0
    cp = np.maximum(candidate.estimator.predict(selected),0); cp[zero] = 0
    mask = [route(r['formula']) for r in rows]
    sp = np.where(mask,cp,bp)
    for name,want in (('base',bp),('augmented217',cp),('scoped_augmented217',sp)):
        assert np.array_equal(want,np.asarray(payload['models'][name])), name
    assert [r['source_model']=='augmented217' for r in payload['routes']] == mask
    return len(rows)*3


def metric_audit():
    panels = read(OUT/'development-predictions.json')
    saved = read(OUT/'development-metrics.json'); computed = {}; gates = {}; comparisons = 0
    counts = {'research-baselines':192,'application-transfer':327,'arithmetic-stress':32,'selection-validation':40}
    for panel,payload in panels.items():
        assert len(payload['actual_lut4']) == counts[panel]
        if panel == 'selection-validation':
            truth = read(ROOT/'results'/panel/'labels.json')
            actual = [r['lut4'] for r in truth]
            assert payload['candidate_ids'] == [r['candidate_id'] for r in truth]
        else:
            truth = read(ROOT/'results'/panel/'observations.json')['rows']
            actual = [r['measured_lut4'] for r in truth]
            assert payload['candidate_ids'] == [r['id'] for r in truth]
        assert actual == payload['actual_lut4']
        assert payload['formulas'] == [r['formula'] for r in truth]
        computed[panel] = {name:metrics(actual,pred) for name,pred in payload['models'].items()}
        for name,m in computed[panel].items(): comparisons += compare_metric(saved['panels'][panel][name],m)
    for name in ('augmented217','scoped_augmented217'):
        checks = {panel:gate(m['base'],m[name],accuracy=panel=='selection-validation') for panel,m in computed.items()}
        passed = all(c['pass'] for c in checks.values())
        assert saved['gates'][name]['development_gate_passed'] == passed
        gates[name] = {'development_gate_passed':passed,'panels':checks}
    fresh = read(OUT/'fresh-predictions.json'); labels = read(TEST/'labels.json')
    assert fresh['candidate_ids'] == [l['candidate_id'] for l in labels]
    actual = [l['lut4'] for l in labels]; saved_fresh = read(OUT/'fresh-metrics.json')
    fresh_metrics = {name:metrics(actual,pred) for name,pred in fresh['models'].items()}
    for name,m in fresh_metrics.items(): comparisons += compare_metric(saved_fresh['models'][name],m)
    for name in gates:
        freshgate = gate(fresh_metrics['base'],fresh_metrics[name])
        eligible = freshgate['pass'] and gates[name]['development_gate_passed']
        assert saved_fresh['gates'][name]['fresh_gate_passed'] == freshgate['pass']
        assert saved_fresh['gates'][name]['scoped_experimental_eligibility'] == eligible
        gates[name].update({'fresh_gate':freshgate,'scoped_experimental_eligibility':eligible})
    return {'gates':gates,'development':computed,'fresh':fresh_metrics,'numeric_fields_compared':comparisons}


def job_audit(completion):
    assert completion['complete'] and not completion['failures'] and completion['fits'] == 0
    jobs = completion['native_worker_jobs']; events = []
    assert all(j['returncode'] == 0 and j['error'] is None for j in jobs)
    for job in jobs:
        assert job['started_at_utc'] <= job['finished_at_utc']
        events += [(job['started_at_utc'],1),(job['finished_at_utc'],-1)]
    active = peak = 0
    for _,change in sorted(events,key=lambda item:(item[0],item[1])):
        active += change; peak = max(active,peak)
    assert active == 0 and peak <= 2
    return {'jobs':len(jobs),'peak_recorded_workers':peak}


def identity_and_collision_audit(protocol):
    import numpy as np
    from isaforge.structural_features_v4 import normalize_formula as v4
    from isaforge.structural_features_v5 import normalize_formula as v5
    from isaforge.v5_corpus import equivalence_key
    from isaforge.features import parse_formula
    def keys(formula):
        forms = {parse_formula(formula).canonical()}
        for normalizer in (v4,v5):
            for value in tuple(forms):
                try: forms.add(parse_formula(normalizer(value)).canonical())
                except ValueError: pass
        result = {('formula',f) for f in forms}|{('commutative',equivalence_key(f)) for f in forms}
        result.update(('formula',normalizer(f)) for f in forms for normalizer in (v4,v5))
        return result
    history = set(read(TRAIN/'historical-formulas.json'))
    oldaliases = {f for r in read(ROOT/'results/selection-validation/novelty.json')['comparisons'] for f in r['forms']}
    known = set().union(*(keys(f) for f in history|oldaliases)); seen = set()
    for folder in (TRAIN,TEST):
        for row in read(folder/'novelty.json')['comparisons']:
            current = set().union(*(keys(f) for f in row['forms']))
            assert not current & known and not current & seen,row['candidate_id']
            seen.update(current)
    features = {name:read(folder/'features.json') for name,folder in (('train',TRAIN),('test',TEST))}
    selected = {}
    for name,payload in features.items():
        matrix = np.asarray([r['values'] for r in payload['records']])
        selected[name] = matrix[:,[payload['columns'].index(n) for n in protocol['selected_columns']]]
    trainkeys = {tuple(v) for v in selected['train']}
    testkeys = {tuple(v) for v in selected['test']}
    oldcols = read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as old:
        oldkeys = {tuple(v) for v in old['x'][:,[oldcols.index(n) for n in protocol['selected_columns']]]}
    return {'historical_original_formulas':len(history),'previous40_saved_semantic_aliases_checked':len(oldaliases),
        'known_sufficient_identity_keys':len(known),'joint_known_identity_overlaps':0,
        'joint_within_or_across_cohort_identity_overlaps':0,
        'test_rows_with_exact217_training_collision':sum(tuple(v) in trainkeys for v in selected['test']),
        'new_train_rows_with_exact217_original1665_collision':sum(tuple(v) in oldkeys for v in selected['train']),
        'test_rows_with_exact217_original1665_collision':sum(tuple(v) in oldkeys for v in selected['test']),
        'test_unique217_vectors':len(testkeys),'scope':'Known sufficient formula/normalizer identities use frozen library normalizers. Feature vector equality is separately reported and is not a semantic identity.'}


def authenticate_model():
    import joblib
    import numpy as np
    protocol = authenticate_training_protocol(); freeze = read(OUT/'model-freeze.json')
    assert freeze['protocol_sha256'] == sha(OUT/'protocol.json')
    assert freeze['fits_completed'] == 1 and freeze['wall_seconds'] <= 120
    for name,value in freeze['files_sha256'].items(): assert sha(OUT/name) == value, name
    candidate = joblib.load(OUT/'model.joblib'); base = joblib.load(ROOT/'models/base/model.joblib')
    metadata = read(OUT/'model.json')
    assert metadata['artifact_sha256'] == sha(OUT/'model.joblib')
    assert candidate.kind == 'mapping_v6' and candidate.training_formula_count == 1729
    assert candidate.calibration['status'] == 'uncalibrated' and candidate.calibration['upper_margin_lut4'] is None
    assert candidate.training_provenance['protocol_sha256'] == sha(OUT/'protocol.json')
    assert candidate.training_provenance['original_count'] == 1665
    assert candidate.training_provenance['targeted_count'] == 64
    assert candidate.training_provenance['consumed40_training_count'] == 0
    assert candidate.training_provenance['training_features_sha256'] == sha(TRAIN/'features.json')
    assert candidate.training_provenance['training_labels_sha256'] == sha(TRAIN/'labels.json')
    assert candidate.estimator.n_features_in_ == 217 and len(candidate.estimator.estimators_) == 300
    assert candidate.estimator.get_params(deep=False) == base.estimator.get_params(deep=False)
    assert all(int(t.tree_.n_node_samples[0]) == 1729 for t in candidate.estimator.estimators_)
    oldcols = read(ROOT/'results/feature-comparison/columns.json')
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as old:
        xold = old['x'][:,[oldcols.index(n) for n in protocol['feature_columns']]]
        assert xold.shape == (1665,336)
    features = read(TRAIN/'features.json')
    xnew = np.asarray([r['values'] for r in features['records']])
    xnew = xnew[:,[features['columns'].index(n) for n in protocol['feature_columns']]]
    assert xnew.shape == (64,336)
    combined = np.vstack((xold,xnew))
    assert np.array_equal(combined.min(axis=0),candidate.feature_minimum)
    assert np.array_equal(combined.max(axis=0),candidate.feature_maximum)
    for filename,value in candidate.runtime_source_sha256.items():
        assert sha(ROOT/'isaforge'/filename) == value,filename
    return protocol,base,candidate


def authenticate_fresh_points():
    protocol,base,candidate = authenticate_model()
    seal = read(OUT/'fresh-point-freeze.json')
    assert not seal['fresh_labels_present']
    for key,path in (('protocol_sha256',OUT/'protocol.json'),('model_freeze_sha256',OUT/'model-freeze.json'),
                     ('predictions_sha256',OUT/'fresh-predictions.json'),('features_sha256',TEST/'features.json'),
                     ('candidates_sha256',TEST/'candidates.json')):
        assert seal[key] == sha(path),key
    points = read(OUT/'fresh-predictions.json'); rows = read(TEST/'candidates.json')
    count = replay_points(points,rows,read(TEST/'features.json'),protocol,base,candidate)
    return count


def pretest():
    assert not (TEST/'labels.json').exists() and not (TRAIN/'test-attempt.json').exists()
    count = authenticate_fresh_points(); oldcount = check_prior()
    completion = read(TRAIN/'completion.json'); jobs = job_audit(completion)
    assert completion['label_count'] == 64 and completion['native_elapsed_seconds'] <= 600
    assert jobs['jobs'] == 169
    assert Counter(j['stage'] for j in completion['native_worker_jobs']) == {'feature':104,'verify':1,'label':64}
    start = read(OUT/'run-start.json'); freeze = read(OUT/'model-freeze.json')
    assert start['training_features_sha256'] == sha(TRAIN/'features.json')
    assert start['training_labels_sha256'] == sha(TRAIN/'labels.json')
    assert read(TRAIN/'preflight-audit.json')['audited_at_utc'] < read(TRAIN/'training-attempt.json')['started_at_utc']
    assert max(j['finished_at_utc'] for j in completion['native_worker_jobs']) < start['started_at_utc']
    assert start['started_at_utc'] < freeze['frozen_at_utc'] <= read(OUT/'fresh-predictions.json')['created_at_utc']
    bridge = read(TEST/'point-freeze.json')
    assert bridge['target_label_jobs'] == 0
    for name,value in bridge['bindings'].items(): assert sha(ROOT/name) == value,name
    assert bridge['frozen_at_utc'] >= read(OUT/'fresh-point-freeze.json')['frozen_at_utc']
    receipt = {'schema':'independent-targeted-fresh-prelabel-v1','status':'pass','audited_at_utc':now(),
        'bindings':{str(p.relative_to(ROOT)):sha(p) for p in (OUT/'model-freeze.json',OUT/'fresh-point-freeze.json',
            OUT/'fresh-predictions.json',TEST/'point-freeze.json',TEST/'features.json',TEST/'candidates.json')},
        'fresh_labels_absent':True,'fresh_attempt_absent':True,'loaded_weight_points_replayed':count,
        'training_labels':64,'fit_count':1,'training_native_seconds':completion['native_elapsed_seconds'],
        'old_artifacts_preserved':oldcount,'audit_native_jobs':0,'audit_fits':0}
    assert not (TEST/'prelabel-audit.json').exists()
    write(TEST/'prelabel-audit.json',receipt)
    return receipt


def final_audit():
    oldcount = check_prior(); protocol,base,candidate = authenticate_model()
    points_replayed = authenticate_fresh_points()
    for panel,payload in read(OUT/'development-predictions.json').items():
        rows = [{'candidate_id':i,'formula':f} for i,f in zip(payload['candidate_ids'],payload['formulas'])]
        points_replayed += replay_points(payload,rows,read(ROOT/'results'/panel/'features.json'),protocol,base,candidate)
    for receipt in (TRAIN/'preflight-audit.json',TEST/'prelabel-audit.json'):
        for name,value in read(receipt)['bindings'].items(): assert sha(ROOT/name) == value,name
    train = read(TRAIN/'completion.json'); test = read(TEST/'completion.json')
    trainjobs = job_audit(train); testjobs = job_audit(test)
    assert trainjobs['jobs'] == 169 and testjobs['jobs'] == 41
    assert train['label_count'] == 64 and test['label_count'] == 40
    assert train['native_elapsed_seconds'] <= 600
    assert train['native_elapsed_seconds']+test['native_elapsed_seconds'] <= 1200
    assert math.isclose(test['total_native_elapsed_seconds'],train['native_elapsed_seconds']+test['native_elapsed_seconds'],abs_tol=1e-9)
    nativeplan = read(TRAIN/'plan.json'); preflight = read(TRAIN/'preflight-audit.json')
    assert nativeplan['frozen_at_utc'] < read(TRAIN/'pre-native-amendment.json')['created_at_utc'] <= protocol['created_at_utc'] < preflight['audited_at_utc']
    assert preflight['audited_at_utc'] < read(TRAIN/'training-attempt.json')['started_at_utc']
    assert read(TEST/'prelabel-audit.json')['audited_at_utc'] < read(TRAIN/'test-attempt.json')['started_at_utc']
    trainworker = train['native_worker_jobs']; testworker = test['native_worker_jobs']
    assert max(j['finished_at_utc'] for j in trainworker) < read(OUT/'run-start.json')['started_at_utc']
    assert max(j['finished_at_utc'] for j in trainworker if j['stage']=='feature') < min(j['started_at_utc'] for j in trainworker if j['stage']=='verify')
    assert max(j['finished_at_utc'] for j in trainworker if j['stage']=='verify') < min(j['started_at_utc'] for j in trainworker if j['stage']=='label')
    assert read(OUT/'fresh-point-freeze.json')['frozen_at_utc'] < min(j['started_at_utc'] for j in testworker)
    assert max(j['finished_at_utc'] for j in testworker if j['stage']=='verify') < min(j['started_at_utc'] for j in testworker if j['stage']=='label')
    assert Counter(j['stage'] for j in testworker) == {'verify':1,'label':40}
    archives = {'training':archive_audit(TRAIN),'fresh':archive_audit(TEST)}
    identities = identity_and_collision_audit(protocol)
    replayed = metric_audit()
    result = {'schema':'independent-targeted-coverage-audit-v1','status':'pass','audited_at_utc':now(),
        'protocol_sha256':sha(OUT/'protocol.json'),'model_artifact_sha256':sha(OUT/'model.joblib'),
        'auditor_sha256':sha(Path(__file__)),'old_artifacts_preserved':oldcount,
        'frozen_cohorts_before_training_labels':True,'frozen_model_and_ordered_points_before_fresh_labels':True,
        'loaded_weight_predictions_replayed':points_replayed,'feature_order':'Selected217 mapped independently by column name; generic graph zero override identical.',
        'fit_count':1,'fit_stage_seconds':read(OUT/'model-freeze.json')['wall_seconds'],
        'native_jobs':trainjobs['jobs']+testjobs['jobs'],'maximum_recorded_worker_overlap':max(trainjobs['peak_recorded_workers'],testjobs['peak_recorded_workers']),
        'native_total_seconds':test['total_native_elapsed_seconds'],'raw_evidence':archives,
        'identity_and_feature_collision_audit':identities,
        'independent_metric_replay':replayed,'audit_native_jobs':0,'audit_fits':0,
        'limitations':['Synthetic isolated combinational circuits and ten declared test templates; no representative workload, full CPU, calibrated safety, timing, routing or power guarantee.',
        'Historical finite formula and saved-normalizer identity screen authenticated and source-reviewed, not an exhaustive semantic-equivalence proof.',
        'Saved feature extraction results authenticated and schema aligned; generic features not reextracted by this auditor.',
        'RV32 vector outputs independently recomputed and measured RTL authenticated to saved successful Verilator execution; no native rerun, universal proof, or mapped-netlist functional proof.',
        'Recorded process starts/ends and source-reviewed process-group cleanup support budget and worker receipts; historical OS process peaks or absence of unrecorded work cannot be proved from saved evidence.']}
    write(OUT/'audit.json',result)
    return {'status':'pass','loaded_points_replayed':points_replayed,'mapped_netlists_recounted':104,
        'RV32_vector_comparisons':sum(a['RV32_vector_comparisons'] for a in archives.values()),
        'eligibility':{n:g['scoped_experimental_eligibility'] for n,g in replayed['gates'].items()},
        'audit_native_jobs':0,'audit_fits':0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight','pretest','final'))
    args = parser.parse_args()
    result = {'preflight':preflight,'pretest':pretest,'final':final_audit}[args.command]()
    print(json.dumps(result,indent=2))
