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


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(m.json.dumps(value,allow_nan=False)+'\n');return m.sha(path.read_bytes())


@pytest.fixture
def synthetic_results(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'SYNTHETIC';out=root/'fitting';stage=out/'fit-attempt-0000'
    rows,vectors,aliases=toy(old=1713,new=48)
    for i,r in enumerate(rows[1713:]):r['family']=('correlated_high_products','affine_masked_chains','comparator_shift_compositions')[i//16]
    groups,split=m.reconstruct_groups(rows,vectors,aliases);zero=[False]*1761;zero[0]=True;prep='a'*64
    source=tmp_path/'scripts/develop_v13_coverage.py';source.parent.mkdir();source.write_text('# SYNTHETIC NO MODEL\n');source_sha=m.sha(source.read_bytes())
    input_report={'schema':'isaforge-v13-independent-input-audit-v1','status':'pass','preparation_sha256':prep,'audit_source_sha256':'b'*64}
    recipe={'scope':'SYNTHETIC ONLY'};manifest={'created_at_utc':'2026-01-01T00:00:00Z'}
    monkeypatch.setattr(m,'input_audit',lambda r:(copy.deepcopy(input_report),copy.deepcopy(rows),zero.copy(),copy.deepcopy(split),recipe.copy(),manifest.copy(),{source:source_sha}))
    review=out/'independent-input-audit.json';review_sha=write(review,input_report)
    approval_sha=write(out/'fit-approval.json',{'status':'approved-v13-thirty-matched-coverage-fits','preparation_sha256':prep,'runner_sha256':source_sha,'maximum_fits':30,
        'freeze_commit':'f'*40,'reviewed_at_utc':'2026-01-01T00:00:01Z','independent_input_audit':{'path':review.name,'sha256':review_sha}})
    write(out/'fit-claim.json',{'maximum_fits':30,'approval_sha256':approval_sha,'preparation_sha256':prep,'claimed_at_utc':'2026-01-01T00:00:02Z'})
    for job in m.schedule():
        i=job['fit_index'];d=split['folds'][job['fold']]
        start={**job,'parameters':{**m.PARAMETERS,'random_state':job['seed']},'training_indices':d['control_training_indices'] if job['view']=='control' else d['training_indices'],
            'validation_indices':d['validation_indices'],'started_at_utc':f'2026-01-01T00:{i:02d}:00Z'}
        write(stage/'receipts'/f'{i:02d}-start.json',start)
        name=f"models/{i:02d}-{job['view']}-seed-{job['seed']}-fold-{job['fold']}.joblib";p=stage/name;p.parent.mkdir(exist_ok=True);p.write_bytes(b'SYNTHETIC NOT A MODEL')
        write(stage/'receipts'/f'{i:02d}-completed.json',{**start,'completed_at_utc':f'2026-01-01T00:{i:02d}:01Z','elapsed_seconds':1.,'estimator_fingerprint':'c'*64,
            'artifact':{'path':name,'sha256':m.sha(p.read_bytes())},'artifact_bytes':p.stat().st_size,'save_load_points_exact':True})
    points={};scores={}
    for seed in m.SEEDS:
        for view in m.VIEWS:
            record=[]
            for i,r in enumerate(rows):
                before=float(r['lut4_count']+(2 if view=='control' else 1));point=0. if zero[i] else before
                record.append({**r,'fold':split['fold_ids'][i],'original_zero':zero[i],'encoded_prediction':before,'decoded_before_zero':before,'predicted_lut4':point})
            name=f'{view}-seed-{seed}.json';write(stage/'predictions'/name,record);points[view,seed]=[r['predicted_lut4'] for r in record]
            scores[view,seed]=m.cohort_scores(rows,points[view,seed]);write(stage/'metrics'/name,scores[view,seed])
    differences=[scores['augmented',s]['original1713']['macro_stratum_mae_lut4']-scores['control',s]['original1713']['macro_stratum_mae_lut4'] for s in m.SEEDS]
    summary={'schema':'isaforge-v13-matched-coverage-comparison-v1','scope':recipe['scope'],'fits_completed':30,
        'primary_augmented_minus_control_original1713_macro_mae_lut4':{'per_seed':dict(zip(map(str,m.SEEDS),differences)),'mean':m.statistics.fmean(differences),'sample_sd_algorithm_seeds':m.statistics.stdev(differences)},
        'scores':{v:{str(s):scores[v,s] for s in m.SEEDS} for v in m.VIEWS},'paired_cap_decisions':{str(s):m.paired(rows,points['control',s],points['augmented',s]) for s in m.SEEDS},
        'promotion':'No automatic promotion/final refit; original1713 cap64FA/FR and tails remain separate endpoints; new48 secondary only.'}
    summary_sha=write(stage/'summary.json',summary)
    write(stage/'completion.json',{'schema':'isaforge-v13-matched-fit-completion-v1','complete':True,'error':None,'fits_attempted':30,'fits_completed':30,'maximum_fits':30,
        'preparation_sha256':prep,'approval_sha256':approval_sha,'runner_sha256':source_sha,'summary_sha256':summary_sha,'completed_at_utc':'2026-01-01T01:00:00Z',
        'evaluation_target_reads':0,'new_solver_queries':0,'new_feature_extractions':0,'new_physical_labels':0})
    return root


def test_full_synthetic10566_saved_points_and30_receipts_no_model_load(synthetic_results):
    report=m.results_audit(synthetic_results,require_models=True)
    assert report['saved_point_rows_verified']==10566 and report['fit_receipts_verified']==30 and report['available_model_hashes_verified']==30
    assert report['primary_recomputed']['mean']<0
    for v in m.VIEWS:
        for s in m.SEEDS:
            assert report['scores_recomputed'][v][str(s)]['original1713']['pooled']['count']==1713
            assert report['scores_recomputed'][v][str(s)]['coverage48']['pooled']['count']==48


@pytest.mark.parametrize('poison',['new_training_in_control','heldout_training','chronology','point_fold','point_order','tail_metric','cap_count_bool','reauthenticated_summary','missing_receipt','extra_points','model','completion_bool','incomplete'])
def test_results_corruption_rejected(synthetic_results,poison):
    stage=synthetic_results/'fitting/fit-attempt-0000'
    if poison in ('new_training_in_control','heldout_training','chronology'):
        name='01' if poison!='heldout_training' else '06';a=stage/'receipts'/f'{name}-start.json';b=stage/'receipts'/f'{name}-completed.json';start=m.read(a);end=m.read(b)
        if poison=='new_training_in_control':start['training_indices'].append(1713)
        elif poison=='heldout_training':start['training_indices'].append(start['validation_indices'][0])
        else:start['started_at_utc']='2025-01-01T00:00:00Z'
        end.update({k:v for k,v in start.items()});write(a,start);write(b,end)
    elif poison in ('point_fold','point_order'):
        p=stage/f'predictions/control-seed-{m.SEEDS[0]}.json';body=m.read(p)
        if poison=='point_fold':body[0]['fold']=(body[0]['fold']+1)%5
        else:body[0],body[1]=body[1],body[0]
        write(p,body)
    elif poison in ('tail_metric','cap_count_bool'):
        p=stage/f'metrics/control-seed-{m.SEEDS[0]}.json';body=m.read(p)
        if poison=='tail_metric':body['original1713']['pooled']['p99_absolute_error_lut4']+=1
        else:body['original1713']['pooled']['caps']['64']['false_accept_count']=False
        write(p,body)
    elif poison=='reauthenticated_summary':
        p=stage/'summary.json';body=m.read(p);body['paired_cap_decisions'][str(m.SEEDS[0])]['original1713']['64']['control_correct_augmented_wrong_count']+=1;digest=write(p,body)
        p=stage/'completion.json';body=m.read(p);body['summary_sha256']=digest;write(p,body)
    elif poison=='missing_receipt':(stage/'receipts/01-start.json').unlink()
    elif poison=='extra_points':write(stage/'predictions/extra.json',[])
    elif poison=='model':next((stage/'models').iterdir()).write_bytes(b'POISON')
    else:
        p=stage/'completion.json';body=m.read(p)
        if poison=='completion_bool':body['fits_completed']=True
        else:body['complete']=False
        write(p,body)
    with pytest.raises(ValueError):m.results_audit(synthetic_results)


def test_missing_model_bytes_are_disclosed_and_optional_in_saved_point_audit(synthetic_results):
    stage=synthetic_results/'fitting/fit-attempt-0000';next((stage/'models').iterdir()).unlink()
    assert m.results_audit(synthetic_results)['available_model_hashes_verified']==29
    with pytest.raises(ValueError,match='Required model'):m.results_audit(synthetic_results,require_models=True)
