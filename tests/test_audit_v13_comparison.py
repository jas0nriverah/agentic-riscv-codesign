"""Independent joint-fold and saved-point synthetic checks; no fit/native calls."""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import struct
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_v13_comparison',ROOT/'scripts/audit_v13_comparison.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('No native or Git subprocess'))


def toy(old=45,new=8):
    rows=[{'formula':f'addi(in0,{i+1})','source':'original1665','inherited_component':str(i),'cohort':'original1713','stratum':m.STRATA[i%9],'lut4_count':i%5} for i in range(old)]
    rows.extend({'formula':f'addi(in1,{i+1})','source':'coverage_v13','context':'new-'+str(i//4),'family':'synthetic','cohort':'coverage48','stratum':m.STRATA[i%9],'lut4_count':100+i} for i in range(new))
    vectors=[m.geometry.float32_row([float(i+1)]+[0.]*216) for i in range(len(rows))]
    return rows,vectors,[[r['formula']] for r in rows]


def test_joint_group_transitivity_and_old_only_control_exclusion():
    rows,x,a=toy();rows[1]['inherited_component']=rows[0]['inherited_component'];a[45].append(rows[1]['formula']);x[49]=x[45]
    g,s=m.reconstruct_groups(rows,x,a);linked=(0,1,*range(45,53))
    assert len({g['row_components'][i] for i in linked})==1
    fold=s['fold_ids'][0];d=s['folds'][fold]
    assert all(i in d['validation_indices'] and i not in d['training_indices'] and i not in d['control_training_indices'] for i in linked)
    assert all(rows[i]['cohort']=='original1713' for d in s['folds'] for i in d['control_training_indices'])
    assert all(d['training_has_all9strata'] and d['control_training_has_all9strata'] for d in s['folds'])


def test_poisoned_targets_and_metadata_cannot_change_groups_or_folds():
    rows,x,a=toy();expected=m.reconstruct_groups(rows,x,a)
    for r in rows:r.update(lut4_count=-100000,predicted_lut4=float('nan'),residual=99,benchmark='POISON')
    assert m.reconstruct_groups(rows,x,a)==expected


def test_context_names_and_same_learner_vector_are_distinct_rules():
    rows,x,a=toy();rows[0].update(source='coverage48',context='same');rows[45]['context']='same'
    g,s=m.reconstruct_groups(rows,x,a);assert g['row_components'][0]!=g['row_components'][45]
    x[45]=x[0];g,s=m.reconstruct_groups(rows,x,a);assert g['row_components'][0]==g['row_components'][45]


def test_control_missing_stratum_fails_even_if_augmented_has_it():
    rows,x,a=toy(old=45,new=9)
    for r in rows[:45]:
        if r['stratum']==m.STRATA[0]:r['inherited_component']='whole-old-stratum'
    with pytest.raises(ValueError,match='CONTROL'):m.reconstruct_groups(rows,x,a)


def npy(shape=(1761,217),descr='<f4',order=False,body=None):
    header=repr({'descr':descr,'fortran_order':order,'shape':shape}).encode()+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+(b'\0'*(1761*217*4) if body is None else body)


def test_standard_library_matrix_parser_requires_shape_dtype_order_length_and_finite():
    assert len(m.matrix_bytes(npy(),1761))==1761*868
    for body in [npy(shape=(217,1761)),npy(descr='>f4'),npy(order=True),npy(body=b'\0'),npy(body=struct.pack('<f',float('nan'))+b'\0'*(1761*868-4))]:
        with pytest.raises(ValueError):m.matrix_bytes(body,1761)


def test_primary_and_secondary_denominators_and_budget_choices():
    rows,_,_=toy(old=1713,new=48);p=[float(r['lut4_count']) for r in rows];p[1713:]=[1000.+v for v in p[1713:]]
    s=m.cohort_scores(rows,p)
    assert s['original1713']['pooled']['count']==1713 and s['original1713']['macro_stratum_mae_lut4']==0
    assert s['coverage48']['pooled']['count']==48 and s['coverage48']['pooled']['mae_lut4']==1000
    assert m.paired(rows,[float(r['lut4_count']) for r in rows],p)['original1713']['64']['control_correct_augmented_wrong_count']==0


def test_all1761_point_rows_exact_raw_decode_and_original_zero():
    rows,_,_=toy(old=1713,new=48);zero=[False]*1761;zero[0]=True;ids=[i%5 for i in range(1761)]
    points=[{**r,'fold':ids[i],'original_zero':zero[i],'encoded_prediction':1.,'decoded_before_zero':1.,'predicted_lut4':0. if zero[i] else 1.} for i,r in enumerate(rows)]
    assert len(m.verify_points(points,rows,zero,ids))==1761
    for key,value in [('fold',True),('original_zero',1),('predicted_lut4',1.),('encoded_prediction',float('nan')),('decoded_before_zero',1.+math.ulp(1.)),('formula','POISON')]:
        bad=copy.deepcopy(points);bad[0][key]=value
        with pytest.raises(ValueError):m.verify_points(bad,rows,zero,ids)
    with pytest.raises(ValueError):m.verify_points(points[:-1],rows,zero,ids)
    with pytest.raises(ValueError):m.verify_points([points[1],points[0],*points[2:]],rows,zero,ids)


def test_fixed_paired_schedule_and_source_independence():
    s=m.schedule();assert len(s)==30 and len({(j['seed'],j['view'],j['fold']) for j in s})==30
    assert {j['view'] for j in s}=={'control','augmented'}
    tree=ast.parse((ROOT/'scripts/audit_v13_comparison.py').read_text());names=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):names.extend(a.name for a in n.names)
        elif isinstance(n,ast.ImportFrom):names.append(n.module or '')
    assert not any('develop_' in n or n in ('numpy','joblib','sklearn','subprocess') for n in names)
