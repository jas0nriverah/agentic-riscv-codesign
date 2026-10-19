"""Input-only V13 synthetic/retained-input checks; no native tools, fits or features."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_v13_coverage',ROOT/'scripts/prepare_v13_coverage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_fixed_grid_cpu_immediates_and_hashes():
    rows=m.fixed_candidates()
    assert len(rows)==len({r['candidate_id'] for r in rows})==len({r['formula'] for r in rows})==48
    assert m.Counter(r['family'] for r in rows)=={f:16 for f in ('correlated_high_products','affine_masked_chains','comparator_shift_compositions')}
    assert m.Counter(r['stratum'] for r in rows)=={'multiplication':16,'arithmetic_chain':16,'comparators':8,'constant_shifts':4,'variable_shifts':4}
    assert all(2<=m.syntax(r['formula'])['operation_count']<=4 for r in rows)
    assert all(set(m.syntax(r['formula'])['input_occurrences'])=={'in0','in1'} for r in rows)
    high=[r for r in rows if r['family']=='correlated_high_products']
    assert {(r['context'],r['parameters']['mask'],r['parameters']['shift']) for r in high}=={(c,k,s) for c in ('or_sub','sub_and_complement') for k in m.MASKS for s in (8,16)}


@pytest.mark.parametrize('formula',['mulhsu(sub(in0,andi(in0,-2049)),slli(in1,16))','add(slli(in0,32),in1)','add(in0,in1)','add(in0,addi(in0,1))','add(in0,7)','add(in0,addi(in1,2048))'])
def test_invalid_cpu_candidate_fails(formula):
    with pytest.raises(ValueError):m.syntax(formula)


def test_existing_oracle_correlation_and_intended_unary_cancellation():
    # Pure existing unsigned interpreter, not native RTL generation/verification.
    from isaforge.rtl import evaluate_formula
    mask=(1<<32)-1
    for x,y in [(0,0),(0xffffffff,0xffffffff),(0x80000000,0x7fffffff),(0x12345678,0x87654321)]:
        for k in m.MASKS:
            assert evaluate_formula(f'sub(ori(in0,{k}),in0)',x,y)==((~x)&k)
            assert evaluate_formula(f'sub(in0,andi(in0,{-k-1}))',x,y)==(x&k)
            for other in (0,123,mask):
                f=f'sub(add(sub(in0,in1),andi(in1,{k})),in0)'
                assert evaluate_formula(f,x,y)==evaluate_formula(f,other,y)==((y&k)-y)&mask
                f=f'add(sub(add(in0,in1),in0),xori(in1,{k}))'
                assert evaluate_formula(f,x,y)==evaluate_formula(f,other,y)==(y+(y^k))&mask


def test_saved_aliases_exclude_fallback_and_rejected_poison():
    r={'formula':'add(in0,in1)','normalized_formula':'add(in0,in1)','v7_modes':{c:{'metadata':{'status':'accepted'},'normalized_formula':'add(in1,in0)'} for c in ('bit','affine','combined')}}
    r['v7_modes']['bit']={'metadata':{'status':'fallback'},'normalized_formula':'sub(in0,in1)'}
    r['v7_modes']['affine']={'metadata':{'status':'rejected'},'normalized_formula':'xor(in0,in1)'}
    assert m.accepted_forms(r)=={'add(in0,in1)','add(in1,in0)'}
    r['v7_modes']['bit']['metadata']['status']='POISON'
    with pytest.raises(ValueError):m.accepted_forms(r)


def test_overlap_records_without_replacement_and_skeleton_not_alias():
    proposal=[{'candidate_id':'A','formula':'add(in0,in1)'},{'candidate_id':'B','formula':'sub(in0,in1)'}]
    ledger=[{'formula':'add(in1,in0)','accepted_forms':['add(in1,in0)'],'sources':['synthetic']},
        {'formula':'sub(in1,in0)','accepted_forms':['sub(in1,in0)'],'sources':['synthetic']}]
    before=copy.deepcopy(proposal);d=m.diagnostics(ledger,proposal)
    assert proposal==before and d['records'][0]['declared_alias_seen'] is True
    assert d['records'][1]['declared_alias_seen'] is False and d['records'][1]['matches']['ordered_skeleton']


def test_actual_whitelisted_ledger_and_target_poison_do_not_change_outputs(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('No process/native calls in input preparation')
    monkeypatch.setattr(subprocess,'Popen',forbidden);seen=[];original=m.read
    def guard(path):
        name=str(path);assert not any(t in name for t in ('labels.json','point-predictions.json','dataset.json','coverage-features.json','.joblib'))
        seen.append(Path(path));return original(path)
    monkeypatch.setattr(m,'read',guard)
    ledger,paths=m.load_ledger();assert len(paths)==8 and set(seen)==set(paths)
    assert len(ledger)>=2929 and sum(any(s.startswith('v11_input_only:') for s in r['sources']) for r in ledger)==196
    old=m.read(ROOT/m.V9/'consumed-input-ledger.json')['records'];new=m.read(ROOT/m.V9/'candidates.json');identities=m.read(ROOT/m.V9/'identity-analysis.json');fit=m.read(ROOT/m.V12/'fitting.json')
    expected=m.merge_ledger(old,new,identities,fit)
    for r in fit['rows']:r.update(lut4_count=-999999,actual=float('nan'),predicted=1,residual=2,benchmark='POISON')
    for r in old+new+identities:r.update(target=-777,actual=100000,point=10000)
    assert m.merge_ledger(old,new,identities,fit)==expected
    assert 'lut4_count' not in json.dumps(ledger)


def test_prepare_validate_and_reauthenticated_poison(tmp_path,monkeypatch):
    # Real retained identity bytes only; output is a synthetic temporary directory.
    root=tmp_path/'SYNTHETIC-input-only';manifest=m.prepare(root)
    assert manifest['candidate_count']==48 and all(manifest[k]==0 for k in m.recipe()['preparation_calls'])
    assert m.validate_preparation(root)[2]==m.fixed_candidates()
    with pytest.raises(ValueError,match='Fresh'):m.prepare(root)
    path=root/'coverage-diagnostics.json';body=m.read(path);body['mask_support'][0]['possible_one_bits']=999;path.write_text(json.dumps(body))
    prep=root/'preparation.json';manifest=m.read(prep)
    for e in manifest['files']:
        if (root/e['path']).resolve()==path:e['sha256']=m.sha(path)
    prep.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='coverage replay'):m.validate_preparation(root)


def test_failed_preparation_retains_failure_marker(tmp_path,monkeypatch):
    root=tmp_path/'SYNTHETIC-failed'
    def fail(*args):raise ValueError('SYNTHETIC broken provenance')
    monkeypatch.setattr(m,'load_ledger',fail)
    with pytest.raises(ValueError):m.prepare(root)
    assert m.read(root/'preparation-failure.json')['native_jobs']==0 and not (root/'preparation.json').exists()


def test_fixed_unsigned_oracle_witnesses_distinguish_all48_functions():
    from isaforge.rtl import evaluate_formula
    witnesses=((0,0),(0,1),(0,2),(0,255),(0,341),(0,1365),(0,65535),(0,65536),(0,8388608),
        (1,0),(1,4294967295),(2,0),(2,1),(2,65535),(2,8388608),(255,1365),(255,4294967295),
        (341,0),(341,1),(341,255),(341,65535),(1365,0),(1365,255),(1365,65535),(65536,1))
    # Each differing output witnesses nonidentity. Never infer equivalence from equality.
    outputs=[tuple(evaluate_formula(r['formula'],x,y) for x,y in witnesses) for r in m.fixed_candidates()]
    assert len(set(outputs))==48
