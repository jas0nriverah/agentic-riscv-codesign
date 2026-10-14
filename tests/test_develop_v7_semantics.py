"""Safety/identity contracts for the source-only V7 study; no model fits."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/develop_v7_semantics.py'
spec=importlib.util.spec_from_file_location('develop_v7_semantics',SCRIPT)
dev=importlib.util.module_from_spec(spec);spec.loader.exec_module(dev)


def test_new_normal_form_unions_original_other_row_and_preserves_old_groups():
    formulas=['sub(ori(in0,255),in0)','andi(xori(in0,4294967295),255)','xor(in0,in1)']
    old=dev.equivalence_diagnostic(formulas,formulas,['a','b','c'],[0,1,2])
    new=dev.equivalence_diagnostic(formulas,[formulas[1],formulas[1],formulas[2]],['a','b','c'],[0,1,2])
    assert old['crossfold_component_count']==0
    assert new['crossfold_components']==[[0,1]]
    assert new['component_count']==2


def test_original_component_not_split_by_new_identity():
    d=dev.equivalence_diagnostic(['add(in0,1)','sub(in0,1)'],['add(in0,1)','sub(in0,1)'],['same','same'],[0,0])
    assert d['component_sizes']==[2] and d['crossfold_component_count']==0


def test_vector_duplicates_keep_dimension_and_row_multiplicity():
    d=dev.duplicate_diagnostic([(0,1),(0,1),(0,1,0),(2,3)],[0,1,2,0])
    assert d['unique_count']==3 and d['crossfold_classes']==[[0,1]]
    assert not np.array_equal(np.array([[0,1]]),np.array([[0,1,0]]))


def test_cap_decisions_positive_mape_and_zero_denominator_are_exact():
    y=np.array([0.,16.,17.,40.]);p=np.array([1.,17.,16.,20.]);s=np.array(['a','a','b','b'])
    result=dev.detailed_metrics(y,p,s);cell=result['all_rows']
    assert result['macro_stratum_mae_lut4']==5.75
    assert cell['zero_target_count']==1 and cell['zero_mae_lut4']==1
    assert cell['positive_mape_percent']==pytest.approx((1/16+1/17+20/40)/3*100)
    assert cell['caps']['16']=={'false_accept_count':1,'false_reject_count':1,'predicted_feasible_count':2,'actually_feasible_count':2,'count':4}
    assert cell['maximum_underprediction_lut4']==20
    assert result['by_stratum']['b']['signed_bias_lut4']==-10.5


def test_prevalence_uses_training_sides_of_each_frozen_fold():
    x=np.array([[0.,1.],[2.,1.],[3.,1.]])
    d=dev.prevalence(x,['variable','constant'],[(np.array([0,1]),np.array([2])),(np.array([1,2]),np.array([0]))])
    assert d['constant']['training_variance_by_fold']==[0,0]
    assert d['variable']['training_variance_by_fold']==[1.,.25]


@pytest.mark.parametrize('bad',[[[float('nan')]],[[float('inf')]], [[-1.]], [[True,1.]]])
def test_matrix_invalid_values_or_shape_rejected(bad):
    with pytest.raises(ValueError):dev.numeric_matrix(bad,(1,1))


def test_historical_hash_resolution_rejects_ambiguous_suffix():
    with pytest.raises(ValueError,match='ambiguous'):
        dev.archive_digest({'/old/a/results/x/file':'1','/old/b/results/x/file':'2'},'results/x/file')
    assert dev.archive_digest({'/old/a/results/x/file':'1'},'results/x/file')=='1'


def test_preparation_refuses_repository_output_before_loading_data():
    with pytest.raises(ValueError,match='outside repository'):
        dev.prepare(None,None,None,None,dev.ROOT/'generated/v7')


def test_fixed_estimator_budget_and_descriptive_seed_scope():
    assert len(dev.VIEWS)*len(dev.SEEDS)*5==90
    assert dev.CONFIGURATION=={'n_estimators':300,'min_samples_leaf':1,'max_features':1.,'n_jobs':1}
    assert dev.SEEDS==(2026101421,2026101422,2026101423)


@pytest.fixture
def prepared_review(tmp_path):
    root=tmp_path/'prepared';root.mkdir();proof_root=tmp_path/'proof';proof_root.mkdir()
    formula='add(in0,in1)'
    mode={'normalized_formula':formula,'features':{'value':1.}}
    ledger=[{'formula':formula,'development_index':i,'modes':{m:mode for m in ('bit','affine','combined')}} for i in range(1665)]
    independent=[{'formula':formula,'original_index':i,'modes':{m:mode for m in ('bit','affine','combined')}} for i in range(1665)]
    dev.write(root/'proof-ledger.json',ledger);dev.write(proof_root/'fitting-input-records.json',independent)
    h=dev.sha(dev.ROOT/'isaforge/semantic_features_v7.py')
    plan={'input_sha256':{},'versions':dev._versions(),'seeds':list(dev.SEEDS),'configuration':dev.CONFIGURATION,
          'columns':dict.fromkeys(dev.VIEWS,[]),'formula_sha256':dev.digest([formula]*1665),
          'v5_freeze_sha256':'freeze','input_features_sha256':'inputs','split_sha256':'split','fit_indices_sha256':'fit',
          'solver':dev.semantic.solver_identity()}
    audit={'status':'pass','rows':1665,'fit_formula_sha256':plan['formula_sha256'],
           **{k:plan[k] for k in ('v5_freeze_sha256','input_features_sha256','split_sha256','fit_indices_sha256')},
           'source_sha256':{'isaforge/semantic_features_v7.py':h,'isaforge/features.py':dev.sha(dev.ROOT/'isaforge/features.py')},
           'solver_version':plan['solver']['version'],'records_sha256':dev.sha(proof_root/'fitting-input-records.json')}
    proof=proof_root/'fitting-input-audit.json';dev.write(proof,audit);dev.write(root/'plan.json',plan)
    seal={'schema':dev.SCHEMA,'stage':'pre-score-freeze','created_at_utc':'2026-10-14T23:00:00+00:00',
          'fits_completed':0,'maximum_fits':90,'files_sha256':{'plan.json':dev.sha(root/'plan.json'),'proof-ledger.json':dev.sha(root/'proof-ledger.json')},
          'plan_sha256':dev.sha(root/'plan.json'),'new_equivalence_crossfold_components':{'bit':1},'crossfold_vector_class_counts':{'base':1}}
    dev.write(root/'pre-score-freeze.json',seal)
    review={'schema':'isaforge-v7-parent-fit-review-v1','approved':True,'pre_score_freeze_sha256':dev.sha(root/'pre-score-freeze.json'),
            'preserve_original_folds_descriptive':True,'reviewed_at_utc':'2026-10-14T23:01:00+00:00',
            'crossfold_equivalence_assessment':'Use existing folds descriptively only.','crossfold_vector_assessment':'Retain original prefix duplicates descriptively.',
            'independent_proof_audit':{'path':str(proof),'sha256':dev.sha(proof)},'proof_ledger_sha256':dev.sha(root/'proof-ledger.json'),'semantic_source_sha256':h}
    path=tmp_path/'parent-review.json';dev.write(path,review)
    return root,path,review,audit,proof


def test_review_requires_separate_coherent_source_bound_audit(prepared_review):
    root,path,_,_,_=prepared_review
    assert dev.validate_prepared(root,path)[0]==root


@pytest.mark.parametrize('field,value', [('approved',False),('pre_score_freeze_sha256','wrong'),
    ('proof_ledger_sha256','wrong'),('semantic_source_sha256','wrong'),('crossfold_equivalence_assessment','  '),
    ('crossfold_vector_assessment',''),('preserve_original_folds_descriptive',False)])
def test_fit_gate_rejects_incomplete_or_unbound_review(prepared_review,field,value):
    root,path,review,_,_=prepared_review;review[field]=value;dev.write(path,review)
    with pytest.raises(ValueError):dev.validate_prepared(root,path)


@pytest.mark.parametrize('field,value',[('rows',1664),('solver_version','unknown'),('input_features_sha256','wrong'),
    ('fit_indices_sha256','wrong'),('fit_formula_sha256','wrong')])
def test_pass_status_alone_does_not_authorize_fit(prepared_review,field,value):
    root,path,review,audit,proof=prepared_review;audit[field]=value;dev.write(proof,audit)
    review['independent_proof_audit']['sha256']=dev.sha(proof);dev.write(path,review)
    with pytest.raises(ValueError,match='audit source/solver/fitting cohort'):dev.validate_prepared(root,path)


def test_review_rejects_record_change_even_with_pass_status(prepared_review):
    root,path,_,_,proof=prepared_review
    (proof.parent/'fitting-input-records.json').write_text('[]')
    with pytest.raises(ValueError,match='records changed'):dev.validate_prepared(root,path)


def test_prepared_source_mutation_rejected_before_fit(prepared_review):
    root,path,_,_,_=prepared_review
    (root/'proof-ledger.json').write_text('[]')
    with pytest.raises(ValueError,match='Prepared file changed'):dev.validate_prepared(root,path)
