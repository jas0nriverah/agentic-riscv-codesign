"""Independent parser/arithmetic audit of V7; no target labels or production oracle."""
import itertools
import copy
import math
import random
import re

import pytest

WORD=(1<<32)-1
BOUNDARY=(0,1,2,3,31,32,63,127,128,255,65535,0x7fffffff,0x80000000,0x80000001,0xaaaaaaaa,0x55555555,WORD)


def independent_parse(text):
    """Parse the public formula grammar without the production AST/parser."""
    tokens=re.findall(r'in[01]|[a-z][a-z0-9]*|-?[0-9]+|[(),]',text)
    if ''.join(tokens)!=re.sub(r'\s+','',text):raise ValueError('bad formula character')
    at=0
    def visit():
        nonlocal at
        if at>=len(tokens):raise ValueError('truncated formula')
        value=tokens[at];at+=1
        if re.fullmatch(r'-?[0-9]+',value):return int(value)
        if value in ('in0','in1'):return value
        if at>=len(tokens) or tokens[at]!='(':raise ValueError('missing parenthesis')
        at+=1;children=[visit()]
        while at<len(tokens) and tokens[at]==',':at+=1;children.append(visit())
        if at>=len(tokens) or tokens[at]!=')':raise ValueError('missing close')
        at+=1
        if len(children)!=(1 if value=='lui' else 2):raise ValueError('operation arity')
        return (value,*children)
    tree=visit()
    if at!=len(tokens):raise ValueError('trailing tokens')
    return tree


def recursive_word(tree,x,y):
    """Exact mathematical RV32 operations, separate from rtl.evaluate_formula."""
    if isinstance(tree,int):return tree&WORD
    if isinstance(tree,str):return (x if tree=='in0' else y)&WORD
    op=tree[0];a=recursive_word(tree[1],x,y);b=recursive_word(tree[2],x,y) if len(tree)==3 else 0
    signed=lambda n:n-(1<<32) if n>=1<<31 else n
    if op=='lui':v=a
    elif op in ('add','addi'):v=sum((a,b))
    elif op=='sub':v=a-b
    elif op in ('and','andi'):v=a&b
    elif op in ('or','ori'):v=a|b
    elif op in ('xor','xori'):v=a^b
    elif op in ('sll','slli'):v=a*pow(2,b%32)
    elif op in ('srl','srli'):v=a//pow(2,b%32)
    elif op in ('sra','srai'):v=signed(a)//pow(2,b%32)
    elif op in ('slt','slti'):v=int(signed(a)<signed(b))
    elif op in ('sltu','sltiu'):v=int(a<b)
    elif op=='mul':v=a*b
    elif op=='mulh':v=(signed(a)*signed(b))//(1<<32)
    elif op=='mulhsu':v=(signed(a)*b)//(1<<32)
    elif op=='mulhu':v=(a*b)//(1<<32)
    else:raise ValueError('unknown operation '+op)
    return v&WORD


def independent_qfbv(tree,z3,inputs,opaque=None):
    """Separate fixed-width SMT translation, including asymmetric high products."""
    if opaque is not None and tree in opaque:return opaque[tree]
    if isinstance(tree,int):return z3.BitVecVal(tree&WORD,32)
    if isinstance(tree,str):return inputs[tree]
    op=tree[0];a=independent_qfbv(tree[1],z3,inputs,opaque)
    b=independent_qfbv(tree[2],z3,inputs,opaque) if len(tree)==3 else None
    if op=='lui':return a
    if op in ('add','addi'):return a+b
    if op=='sub':return a-b
    if op in ('and','andi'):return a&b
    if op in ('or','ori'):return a|b
    if op in ('xor','xori'):return a^b
    if op in ('sll','slli'):return a<<(b&31)
    if op in ('srl','srli'):return z3.LShR(a,b&31)
    if op in ('sra','srai'):return a>>(b&31)
    if op in ('slt','slti'):return z3.If(a<b,z3.BitVecVal(1,32),z3.BitVecVal(0,32))
    if op in ('sltu','sltiu'):return z3.If(z3.ULT(a,b),z3.BitVecVal(1,32),z3.BitVecVal(0,32))
    if op=='mul':return a*b
    if op in ('mulh','mulhu','mulhsu'):
        left=z3.ZeroExt(32,a) if op=='mulhu' else z3.SignExt(32,a)
        right=z3.SignExt(32,b) if op=='mulh' else z3.ZeroExt(32,b)
        return z3.Extract(63,32,left*right)
    raise ValueError('unknown SMT operation '+op)


def replay_certificate(record,z3,query_callback=None):
    """Check every local miter independently, and its exact congruent position."""
    certificate=record['metadata']['certificate']
    assert certificate['initial']==record['original_formula']
    assert certificate['final']==record['normalized_formula']
    current=independent_parse(certificate['initial'])
    inputs={'in0':z3.BitVec('in0',32),'in1':z3.BitVec('in1',32)}
    def at(node,path):
        for index in path:
            assert isinstance(node,tuple) and type(index) is int and 0<=index<len(node)-1
            node=node[index+1]
        return node
    def replace(node,path,replacement):
        if not path:return replacement
        parts=list(node);parts[path[0]+1]=replace(parts[path[0]+1],path[1:],replacement)
        return tuple(parts)
    for number,step in enumerate(certificate['steps']):
        before=independent_parse(step['before']);after=independent_parse(step['after'])
        assert at(current,step['path'])==before
        assert step['proof']['result']=='unsat'
        atoms=step['proof'].get('opaque_atoms',[])
        assert len(atoms)==len(set(atoms))
        bindings={independent_parse(text):z3.BitVec(f'independent_opaque_{i}',32) for i,text in enumerate(atoms)}
        source=independent_qfbv(before,z3,inputs,bindings);target=independent_qfbv(after,z3,inputs,bindings)
        solver=z3.Then(z3.With('simplify',som=True),'qfbv').solver();solver.set(timeout=500);solver.add(source!=target)
        result=solver.check()
        if query_callback is not None:query_callback(number,step,solver,str(result))
        assert result==z3.unsat,(step['kind'],before,after,str(result))
        current=replace(current,step['path'],after)
    assert current==independent_parse(certificate['final'])
    return len(certificate['steps'])


def generated_formulas(count=64):
    """Fixed input-only grammar with all high products and nonlinear barriers."""
    rng=random.Random(2026101444)
    ops=('add','sub','and','or','xor','sll','srl','sra','slt','sltu','mul','mulh','mulhu','mulhsu')
    def make(depth):
        if not depth or rng.random()<.20:return rng.choice(('in0','in1',str(rng.choice(BOUNDARY)),'-1','4294967295'))
        op=rng.choice(ops);return f'{op}({make(depth-1)},{make(depth-1)})'
    result=[]
    for _ in range(count):
        term=make(3);mask=rng.choice(BOUNDARY);k=rng.choice((0,1,7,16,31,32,63,-1))
        choices=(f'sub(ori({term},{mask}),{term})',f'sub({term},andi({term},{mask}))',
          f'sub(slli(add({term},in1),{k}),slli({term},{k}))',
          f'addi(sub(add({term},in1),{term}),-2147483648)')
        result.append(choices[rng.randrange(len(choices))])
    return sorted(set(result))


def assert_interpreted_equal(original,replacement,random_count=12):
    left,right=independent_parse(original),independent_parse(replacement)
    rng=random.Random(2026101445)
    # Full Cartesian boundary set catches correlations and asymmetric signs.
    for x,y in itertools.chain(itertools.product(BOUNDARY,repeat=2),
              ((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(random_count))):
        assert recursive_word(left,x,y)==recursive_word(right,x,y),(original,replacement,x,y)


@pytest.mark.parametrize('mode',('bit','affine','combined'))
def test_independent_recursive_generated_rewrite_interactions(mode):
    from isaforge.semantic_features_v7 import normalize_formula
    for formula in generated_formulas():
        replacement=normalize_formula(formula,mode=mode)
        assert_interpreted_equal(formula,replacement)
        assert normalize_formula(replacement,mode=mode)==replacement
        assert normalize_formula(formula,mode=mode)==replacement


@pytest.mark.parametrize('mask',(0,1,-1,-2147483648,0x80000000,0x7fffffff,0x55555555,0xaaaaaaaa))
def test_generic_masks_and_signed_word_edges(mask):
    from isaforge.semantic_features_v7 import normalize_formula
    for term in ('in0','xori(in1,-1)','add(in0,in1)','mulhsu(in0,in1)'):
        for formula in (f'sub(ori({term},{mask}),{term})',f'sub({term},andi({term},{mask}))'):
            assert_interpreted_equal(formula,normalize_formula(formula,mode='bit'))


@pytest.mark.parametrize('distance',(0,1,16,31,32,63,-1,-2147483648,WORD))
def test_affine_fixed_left_shift_masks_and_modular_overflow(distance):
    from isaforge.semantic_features_v7 import normalize_formula
    for op in ('sll','slli'):
        formula=f'sub({op}(add(in0,in1),{distance}),add({op}(in0,{distance}),{op}(in1,{distance})))'
        assert_interpreted_equal(formula,normalize_formula(formula,mode='affine'))


@pytest.mark.parametrize('formula',(
    'sub(in0,ori(in0,255))', # subtraction order reverses the identity
    'sub(ori(in0,255),in1)', # repeated operand differs
    'sub(in0,andi(in1,255))',
    'sub(srli(add(in0,in1),1),add(srli(in0,1),srli(in1,1)))',
    'sub(srai(add(in0,in1),31),add(srai(in0,31),srai(in1,31)))',
    'sub(sll(add(in0,in1),in1),slli(add(in0,in1),1))',
    'mulh(add(in0,in1),in0)', 'mulhsu(add(in0,in1),in0)',
    'mulhu(sub(in0,in1),in0)', 'slt(add(in0,in1),in0)',
    'sub(add(mulhsu(in0,in1),mulhu(in0,in1)),mulhsu(in1,in0))',
))
def test_nonmatching_patterns_and_nonlinear_barriers(formula):
    from isaforge.semantic_features_v7 import normalize_formula
    for mode in ('bit','affine','combined'):
        assert_interpreted_equal(formula,normalize_formula(formula,mode=mode))


def test_independent_oracle_exposes_unsound_high_half_distribution():
    x,y=WORD,1
    for op in ('mulh','mulhu','mulhsu'):
        lhs=independent_parse(f'{op}(add(in0,in1),in0)')
        rhs=independent_parse(f'add({op}(in0,in0),{op}(in1,in0))')
        assert recursive_word(lhs,x,y)!=recursive_word(rhs,x,y)


def test_independent_parser_rejects_malformed_input():
    for text in ('add(in0,in1)garbage','add(in0)','add(in0,in1','add(in0,in1);','lui(1,2)'):
        with pytest.raises(ValueError):independent_parse(text)


def test_universal_qf_bv32_identities_and_coefficient_reconstruction():
    z3=pytest.importorskip('z3',reason='Install optional proofs dependency for formal tests')
    x,y,z,c,a,b=z3.BitVecs('x y z c a b',32)
    pairs=[((x|c)-x,(~x)&c),(x-(x&c),x&(~c)),
           ((x+y)+z,x+(y+z)),(x+y,y+x),(x-y,x+(-y)),
           (a*x+b*x,(a+b)*x),(a*x-b*x,(a-b)*x),
           (a*(x+y),a*x+a*y),(a*(b*x),(a*b)*x),
           (x<<(c&31),x<<z3.ZeroExt(27,z3.Extract(4,0,c)))]
    for k in range(32):
        pairs.extend(((x<<k,x*z3.BitVecVal(1<<k,32)),
                      ((x+y)<<k,(x<<k)+(y<<k)),
                      ((x-y)<<k,(x<<k)-(y<<k))))
    for source,target in pairs:
        solver=z3.Then(z3.With('simplify',som=True),'qfbv').solver();solver.set(timeout=500)
        solver.add(source!=target)
        assert solver.check()==z3.unsat


def test_independent_smt_and_integer_semantics_agree_at_signed_boundaries():
    z3=pytest.importorskip('z3',reason='Install optional proofs dependency for formal tests')
    ops=('add','addi','sub','and','andi','or','ori','xor','xori','sll','slli',
         'srl','srli','sra','srai','slt','slti','sltu','sltiu','mul','mulh','mulhu','mulhsu')
    for op in ops:
        tree=independent_parse(f'{op}(in0,in1)')
        for x,y in ((0,WORD),(WORD,1),(WORD,WORD),(0x80000000,WORD),
                    (0x80000000,0x80000001),(0x7fffffff,0x80000000),(31,32),(WORD,63)):
            term=independent_qfbv(tree,z3,{'in0':z3.BitVecVal(x,32),'in1':z3.BitVecVal(y,32)})
            assert z3.simplify(term).as_long()==recursive_word(tree,x,y)


@pytest.mark.parametrize('formula',(
    'slli(slli(in0,31),1)','slli(slli(in0,63),33)',
    'sub(slli(add(in0,in1),31),add(slli(in0,31),slli(in1,31)))',
    'sub(add(in0,in1),add(in1,in0))',
    'addi(addi(in0,4294967295),1)',
))
def test_affine_chained_shifts_do_not_remask_combined_distance(formula):
    from isaforge.semantic_features_v7 import normalize_formula
    result=normalize_formula(formula,mode='affine')
    assert_interpreted_equal(formula,result)
    assert normalize_formula(result,mode='affine')==result


@pytest.mark.parametrize('literal',(1<<32,(1<<32)+255,-(1<<31)-1))
def test_public_rv32_literal_domain_is_enforced(literal):
    from isaforge.semantic_features_v7 import normalize_formula
    with pytest.raises(ValueError):normalize_formula(f'ori(in0,{literal})')


@pytest.mark.parametrize('mode',('bit','affine','combined'))
def test_independent_certificate_replays_every_context_and_rejects_tampering(mode):
    z3=pytest.importorskip('z3')
    from isaforge.semantic_features_v7 import analyze_formula
    formula='mulhsu(add(sub(ori(in0,255),in0),slli(in1,33)),sub(in1,andi(in1,-1)))'
    record=analyze_formula(formula,mode=mode)
    assert replay_certificate(record,z3)>0
    altered=copy.deepcopy(record);altered['metadata']['certificate']['steps'][0]['after']='lui(17)'
    with pytest.raises(AssertionError):replay_certificate(altered,z3)
    altered=copy.deepcopy(record);altered['metadata']['certificate']['steps']=[]
    with pytest.raises(AssertionError):replay_certificate(altered,z3)


def test_feature_views_are_nested_formula_only_finite_and_original_cost_is_retained():
    from isaforge.semantic_features_v7 import analyze_formula,feature_dict,feature_matrix,FEATURE_NAMES_BY_MODE
    formula='mulhsu(sub(ori(in0,255),in0),sub(in1,andi(in1,-1)))'
    separate={m:feature_dict(formula,mode=m) for m in ('bit','affine')}
    combined=feature_dict(formula,mode='combined')
    assert combined=={**separate['bit'],**separate['affine']}
    for mode in ('bit','affine','combined'):
        data=analyze_formula(formula,mode=mode)
        assert tuple(data['features'])==FEATURE_NAMES_BY_MODE[mode]
        assert len(data['features'])<= (16 if mode=='combined' else 8)
        assert all(math.isfinite(v) and v>=0 for v in data['features'].values())
        assert data['metadata']['original_zero_override'] is False
        clean,_=feature_matrix([{'formula':formula}],mode=mode)
        poisoned,_=feature_matrix([{'formula':formula,'lut4_count':float('nan'),'stratum':'bad',
            'component':'bad','residual':float('inf'),'upper_margin_lut4':-1,'predicted_lut4':1e100}],mode=mode)
        assert clean==poisoned


def test_affine_operand_order_has_one_canonical_normal_form():
    from isaforge.semantic_features_v7 import normalize_formula
    formulas=('add(in0,add(in1,slli(in0,1)))','add(slli(in0,1),add(in0,in1))',
              'add(add(in1,in0),slli(in0,1))')
    assert len({normalize_formula(f,mode='affine') for f in formulas})==1


@pytest.mark.parametrize('failure',('unknown','unavailable'))
def test_any_unproved_local_step_rolls_back_every_mode(monkeypatch,failure):
    import isaforge.semantic_features_v7 as semantics
    formula='add(sub(ori(in0,255),in0),sub(in1,andi(in1,31)))'
    original_prove=semantics._prove;calls=0
    def injected(before,after,atoms,timeout_ms):
        nonlocal calls
        calls+=1
        if calls==2:return {'result':failure,'solver':{'available':failure!='unavailable'},'elapsed_ms':0,'cpu_ms':0}
        return original_prove(before,after,atoms,timeout_ms)
    monkeypatch.setattr(semantics,'_prove',injected)
    results=semantics.analyze_modes(formula)
    assert calls>=2
    assert any(a['proof']['result']=='unsat' for r in results.values() for a in r['metadata']['attempts'])
    for record in results.values():
        assert record['normalized_formula']==record['original_formula']==formula
        assert record['metadata']['certificate']['steps']==[]
        assert record['metadata']['status']=='fallback_original'
        assert record['metadata']['proof_engine']['fallback_reason']=='proof_'+failure


@pytest.mark.parametrize('limits,formula',(
    ({'max_atoms':1},'add(in0,in1)'),
    ({'max_island_ops':1},'add(add(in0,in1),andi(in0,255))'),
    ({'max_output_ops':1},'sub(ori(in0,255),in0)'),
    ({'max_passes':1},'sub(ori(in0,255),in0)'),
))
def test_any_structural_budget_failure_is_atomic_across_modes(limits,formula):
    import isaforge.semantic_features_v7 as semantics
    results=semantics.analyze_modes(formula,budget=semantics.Budget(**limits))
    for record in results.values():
        assert record['normalized_formula']==formula
        assert record['metadata']['status']=='fallback_original'
        assert record['metadata']['certificate']['steps']==[]
        assert record['metadata']['proof_engine']['fallback_reason']


def test_sat_proof_is_a_correctness_failure_and_never_fallback(monkeypatch):
    import isaforge.semantic_features_v7 as semantics
    monkeypatch.setattr(semantics,'_prove',lambda *a,**k:{'result':'sat'})
    with pytest.raises(semantics.ProofError):semantics.analyze_modes('sub(ori(in0,255),in0)')


def test_shared_formula_proof_time_cap_rolls_back_all_modes(monkeypatch):
    import isaforge.semantic_features_v7 as semantics
    real=semantics._prove
    def slow(*args,**kwargs):
        proof=real(*args,**kwargs)
        return {**proof,'elapsed_ms':501,'cpu_ms':501}
    monkeypatch.setattr(semantics,'_prove',slow)
    results=semantics.analyze_modes('sub(ori(in0,255),in0)')
    assert semantics.Budget().proof_timeout_ms==500
    for record in results.values():
        assert record['normalized_formula']==record['original_formula']
        assert record['metadata']['proof_engine']['fallback_reason']=='proof_budget'
