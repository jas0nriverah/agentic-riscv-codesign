import pytest
from isaforge.features import parse_formula
from isaforge.probe_corpus import STRATA,formula_shape
from isaforge.v6_corpus import Generator,identity_keys,component_map,inspect_seal,tree_operations,SEEDS,_instantiate

def record(formula,value):
    return {'formula':formula,'normalized_formula':formula,'values':[float(value)]+[0.]*335}

def test_reproducible_diverse_two_input_grammar():
    a=Generator([],families=2).generate();b=Generator([],families=2).generate();assert a==b
    assert {s:len(r) for s,r in a.items()}=={'calibration':32,'test':32}
    keys=set()
    for rows in a.values():
        for offset in range(0,len(rows),2):
            pair=rows[offset:offset+2]
            assert pair[0]['original_skeleton']==pair[1]['original_skeleton']
            assert len({r['formula'] for r in pair})==2
            union=set()
            for r in pair:
                assert formula_shape(r['formula'])[1]==2 and tree_operations(r['formula'])<=15
                assert parse_formula(r['formula']).canonical()==r['formula']
                union|=identity_keys(r['formula'])
            assert not union&keys;keys|=union

def test_shared_diamond_retains_repeated_operations():
    rows=Generator([],families=2).generate()['calibration']
    for r in rows:
        if r['stratum']=='shared_diamond':
            counts={}
            def visit(node):
                if node.children:
                    key=node.canonical();counts[key]=counts.get(key,0)+1
                    for child in node.children:visit(child)
            visit(parse_formula(r['formula']))
            assert any(n>=2 and 'in0' in f and 'in1' in f for f,n in counts.items())

def test_current_normalizer_wire_identity_is_excluded():
    assert identity_keys('add(in0,0)')&identity_keys('ori(in0,0)')

def test_commutative_identity_preserves_inputs():
    assert ('equivalence','add(in0,in1)') in identity_keys('add(in1,in0)')
    assert identity_keys('sub(in0,in1)')!=identity_keys('sub(in1,in0)')

def test_both_v5_and_augmented_exact_vectors_join():
    a,b='add(in0,in1)','xor(in0,in1)';ra,rb=record(a,1),record(b,1)
    rb['values'][-1]=17.
    groups=component_map([{'formula':a},{'formula':b}],[ra,rb]);assert groups[a]==groups[b]

def test_current_normalization_bridges_nonidentical_skeletons():
    a,b='add(in0,in1)','sub(in0,in1)';ra,rb=record(a,1),record(b,2);rb['normalized_formula']=a
    assert component_map([{'formula':a},{'formula':b}],[ra,rb])[a]==component_map([{'formula':a},{'formula':b}],[ra,rb])[b]

def test_missing_duplicate_malformed_features_fail_closed():
    a='add(in0,in1)';rows=[{'formula':a}]
    with pytest.raises(ValueError):component_map(rows,[])
    with pytest.raises(ValueError):component_map(rows,[record(a,1)]*2)
    r=record(a,1);r['values'][-1]=float('nan')
    with pytest.raises(ValueError):component_map(rows,[r])
    r=record(a,1);r['values'].pop()
    with pytest.raises(ValueError):component_map(rows,[r])

def test_feature_overlap_rejects_entire_pair_and_repair_is_input_only():
    generator=Generator([],families=1);cohorts=generator.generate();records={};n=0
    # Unique test vectors for otherwise disjoint generated pairs.
    for scope,rows in cohorts.items():
        records[scope]=[]
        for r in rows:n+=1;records[scope].append(record(r['formula'],n))
    consumed=[{'formula':'addi(in0,42)'}];old=[record(consumed[0]['formula'],1)]
    seal=inspect_seal(consumed,cohorts,old,records,families=1,minimum=1)
    bad=seal['rejections'];assert len(bad)==2 and {r['scope'] for r in bad}=={'calibration'}
    fresh=generator.replace(cohorts,bad)
    assert fresh['test']==cohorts['test']
    assert fresh['calibration'][2:]==cohorts['calibration'][2:]
    assert fresh['calibration'][:2]!=cohorts['calibration'][:2]

def test_complete_family_component_counts_and_crossscope_disjoint():
    cohorts=Generator([],families=2).generate();records={};n=0
    for scope,rows in cohorts.items():
        records[scope]=[]
        for r in rows:n+=1;records[scope].append(record(r['formula'],n))
    seal=inspect_seal([],cohorts,[],records,families=2,minimum=2)
    assert seal['status']=='sealed' and seal['cross_cohort_component_count']==0
    assert all(v==2 for counts in seal['stratum_component_counts'].values() for v in counts.values())
    ids=[{seal['component_by_formula'][r['formula']] for r in cohorts[s]} for s in SEEDS]
    assert not ids[0]&ids[1]

def test_pair_variant_contract_and_stratum_balance_required():
    cohorts=Generator([],families=1).generate();records={};n=0
    for scope,rows in cohorts.items():
        records[scope]=[]
        for r in rows:n+=1;records[scope].append(record(r['formula'],n))
    cohorts['test'][0]['variant_index']=1
    with pytest.raises(ValueError,match='two variants'):inspect_seal([],cohorts,[],records,families=1,minimum=1)

def test_invalid_acquisition_budget():
    for count in (0,13,True):
        with pytest.raises(ValueError):Generator([],families=count)


def test_unrelated_literals_independent_but_shared_tokens_reused():
    class Draws:
        def __init__(self):self.n=0
        def choice(self,values):self.n+=1;return self.n
    rng=Draws()
    assert _instantiate('add(addi(in0,C0),addi(in1,C1))',rng)=='add(addi(in0,1),addi(in1,2))'
    rng=Draws()
    assert _instantiate('xor(addi(add(in0,in1),C0),slli(addi(add(in0,in1),C0),S1))',rng)=='xor(addi(add(in0,in1),1),slli(addi(add(in0,in1),1),2))'


def test_strata_preserve_operator_intent_without_unsupported_instructions():
    cohorts=Generator([],families=2).generate()
    for rows in cohorts.values():
        for r in rows:
            ops=[]
            def visit(n):
                if n.children:
                    ops.append(n.value)
                    for c in n.children:visit(c)
            visit(parse_formula(r['formula']))
            muls=sum(op in ('mul','mulh','mulhu','mulhsu') for op in ops)
            assert muls==(1 if r['stratum']=='multiplication' else 0)
            if r['stratum']=='mask_logic':assert set(ops)<={'and','or','xor','andi','ori','xori'}
            if r['stratum']=='constant_shifts':assert any(op in ('slli','srli','srai') for op in ops)
            if r['stratum']=='variable_shifts':assert any(op in ('sll','srl','sra') for op in ops) and 'andi' in ops
            if r['stratum']=='comparators':assert any(op in ('slt','sltu','slti','sltiu') for op in ops)
