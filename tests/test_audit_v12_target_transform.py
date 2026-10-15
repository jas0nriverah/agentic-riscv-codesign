"""Independent synthetic V12 group/split audit tests; no fitting/native jobs."""
import ast
import copy
import importlib.util
from pathlib import Path
import struct
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_v12_target_transform',ROOT/'scripts/audit_v12_target_transform.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def inputs():
    rows=[];vectors=[];aliases=[];sources=[]
    for s,stratum in enumerate(m.STRATA):
        for j in range(5):
            i=len(rows);formula=f'addi(in0,{i+1})'
            rows.append({'formula':formula,'stratum':stratum,'lut4_count':i,'original_zero':False})
            vectors.append(m.float32_row([float(i+1)]*217));aliases.append({formula});sources.append(('old_component',str(i)))
    return rows,vectors,aliases,sources


def test_group_split_is_label_independent_and_deterministic():
    r,v,a,s=inputs();groups,diagnostic=m.reconstruct_groups(r,v,a,s);folds=m.reconstruct_folds(r,groups)
    poisoned=copy.deepcopy(r)
    for i,row in enumerate(poisoned):row.update(lut4_count=100000-i,target=-999,residual=float('nan'),predicted_lut4=0,benchmark='POISON',saved=999)
    pg,pd=m.reconstruct_groups(poisoned,v,a,s);pf=m.reconstruct_folds(poisoned,pg)
    assert pg==groups and pd==diagnostic and pf==folds
    assert [len(x) for x in folds['validation_indices']]==[9]*5
    assert all(set(x)==set(m.STRATA) for x in folds['training_stratum_counts'])


def test_transitive_source_alias_and_float32_edges_cannot_be_separated():
    r,v,a,s=inputs();s[1]=s[0];a[2].add(r[1]['formula']);v[3]=v[2]
    groups,_=m.reconstruct_groups(r,v,a,s)
    assert next(c for c in groups if 0 in c['indices'])['indices']==[0,1,2,3]
    folds=m.reconstruct_folds(r,groups);assert len({folds['fold_ids'][i] for i in range(4)})==1


def test_commutative_identity_is_sufficient_without_operand_renaming():
    assert m.commutative('add(in0,in1)')==m.commutative('add(in1,in0)')
    assert m.commutative('sub(in0,in1)')!=m.commutative('sub(in1,in0)')
    assert m.commutative('mulhsu(in0,in1)')!=m.commutative('mulhsu(in1,in0)')
    assert m.commutative('mulh(in0,in1)')==m.commutative('mulh(in1,in0)')


def test_float32_collisions_follow_learner_conversion_and_signed_zero():
    assert m.float32_row([1.0]*217)==m.float32_row([1.0+1e-10]*217)
    assert m.float32_row([0.0]*217)==m.float32_row([-0.0]*217)
    assert m.float32_row([1.0]*217)!=m.float32_row([1.001]*217)


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),-1])
def test_bad_matrix_values_fail_closed(value):
    with pytest.raises(ValueError):m.float32_row([value]*217)


def test_entire_coverage_context_is_a_group():
    r,v,a,s=inputs();s[0]=('coverage_context','direct_product');s[8]=s[0];s[19]=s[0]
    groups,_=m.reconstruct_groups(r,v,a,s);assert next(g for g in groups if 0 in g['indices'])['indices']==[0,8,19]


def test_missing_stratum_in_a_training_partition_is_not_silently_relaxed():
    r,v,a,s=inputs()
    for i,row in enumerate(r):
        if row['stratum']==m.STRATA[0]:s[i]=('old_component','all_of_one_stratum')
    groups,_=m.reconstruct_groups(r,v,a,s)
    with pytest.raises(ValueError,match='nine strata'):m.reconstruct_folds(r,groups)


def test_no_fitting_runner_or_native_imports():
    tree=ast.parse((ROOT/'scripts/audit_v12_target_transform.py').read_text());names=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):names.extend(v.name for v in node.names)
        elif isinstance(node,ast.ImportFrom):names.append(node.module or '')
    assert not any('develop_v12_target_transform' in n or 'ensemble' in n or n=='subprocess' for n in names)


def npy(body=b'',shape=(1713,217),descr='<f4',fortran=False):
    header=repr({'descr':descr,'fortran_order':fortran,'shape':shape}).encode()+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+body


def test_independent_npy_reader_requires_exact_dtype_shape_order_and_length():
    body=b'\0'*(1713*217*4);assert m.npy_bytes(npy(body))==body
    for value in [npy(body,descr='>f4'),npy(body,shape=(217,1713)),npy(body,fortran=True),npy(body[:-1]),b'POISON']:
        with pytest.raises(ValueError):m.npy_bytes(value)


def test_actual_input_reconstruction_never_reads_v6_v8_evaluation_targets_or_models(monkeypatch):
    original=Path.read_bytes;seen=[]
    def guard(path):
        resolved=path.resolve();name=str(resolved)
        assert '/2026-10-14-v6/corpus/test/' not in name
        assert '/2026-10-14-v6/corpus/calibration/' not in name
        assert '/2026-10-15-v8-application-transfer/measurements/' not in name
        assert path.suffix!='.joblib'
        seen.append(name);return original(path)
    monkeypatch.setattr(Path,'read_bytes',guard)
    rows,vectors,aliases,sources,diagnostic=m.reconstruct_inputs()
    groups,group_diag=m.reconstruct_groups(rows,vectors,aliases,sources);folds=m.reconstruct_folds(rows,groups)
    assert len(rows)==1713 and len(groups)==528 and len(vectors[0])==868
    assert [len(v) for v in folds['validation_indices']]==[366,373,339,317,318]
    assert len(group_diag['float32_collision_classes'])==140 and seen
