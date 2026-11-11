"""Release-first learning must corroborate legacy and new budget proposals alike."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('corroboration',Path(__file__).parents[1]/'scripts/learn_boundary_corroboration.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
FORM='xor(add(sra(addi(xori(in0,11),73),andi(in1,3)),in1),in0)'


def test_release_first_has_no_legacy_median_bypass_and_no_raw_point_replacement():
 p,c=r.budget_support([60.,126.,20.,100.],[73.05,145.,150.,120.],[84.7633,128.,31.,50.],[True]*4)
 assert p==[73.05,128.,32.,120.] and c==[[],[128],[32,64,128],[]]
 assert r.budget_support([126.],[145.],[128.0001],[True])[0]==[145.]
 assert r.budget_support([126.],[145.],[1.],[False])[0]==[145.]


def test_all_root_chains_support_and_old_raw_diagnostics_remain_unchanged():
 class Model:
  def __init__(self,width):self.width=width
  def predict(self,x):assert x.shape[1]==self.width;return np.array([125.,84.7633])
 old={n:[128.,64.] for n in r.baseline.NAMES};old[r.CURRENT]=[126.,60.];old[r.BUDGET]=[145.,73.05]
 payload={'models':old,'routes':[], 'learned_raw_lut4':{'old':[129.,97.]}}
 support=r.derive_support([FORM]);assert support['cell_counts']=={'wide_unshared':1}
 values,_,detail=r.points([{'formula':FORM}]*2,np.zeros((2,336)),{'augmented':Model(233),'coverage':Model(217)},support,payload)
 assert values[r.PRIMARY]==[128.,73.05] and values[r.FALLBACK]==[128.,73.05]
 assert values[r.STRUCTURAL]==[128.,64.]
 assert detail['learned_raw_lut4']==payload['learned_raw_lut4']
 assert detail['corroboration_raw_lut4'][r.PRIMARY]==[125.,84.7633]
 assert detail['proposal_provenance'][r.PRIMARY][1]['64']['structural_proposal']
 assert not detail['proposal_provenance'][r.PRIMARY][1]['64']['candidate_accepts']


def test_any_unsupported_same_chain_falls_back_to_release():
 mixed='xor(add(sra(slli(andi(addi(xori(in0,7),11),255),24),andi(xori(in1,13),1)),sra(addi(xori(in1,13),7),in0)),or(in0,in1))'
 assert set(r.cells(mixed))=={'narrow_unshared','wide_shared'}
 support=r.derive_support([FORM]);assert 'wide_shared' not in support['supported_cells']
 class Model:
  def predict(self,x):return np.array([1.])
 old={n:[128.] for n in r.baseline.NAMES};old[r.CURRENT]=[126.];old[r.BUDGET]=[145.]
 values,_,detail=r.points([{'formula':mixed}],np.zeros((1,336)),{'augmented':Model(),'coverage':Model()},support,{'models':old,'routes':[]})
 assert values[r.PRIMARY]==[145.] and detail['pipeline_covered']==[False]


def test_accuracy_against_every_reference_and_cap_errors_cannot_offset():
 models={n:[128.,128.] for n in r.NAMES};models[r.CURRENT]=[125.,125.];models[r.BUDGET]=[140.,140.]
 m=r.panel_metrics({'models':models,'actual_lut4':[125.,159.]})
 assert set(m['checks'][r.PRIMARY]['accuracy_no_worse'])==set(r.REFERENCES)
 assert not m['checks'][r.PRIMARY]['caps']['128']['false_accept_no_worse_release']
 assert not r.passed(m['checks'][r.PRIMARY])
 # Raising an old correct point toward release cannot hide behind a release gain.
 models={n:[128.] for n in r.NAMES};models[r.CURRENT]=[126.];models[r.BUDGET]=[150.];models[r.PRIMARY]=[129.]
 m=r.panel_metrics({'models':models,'actual_lut4':[128.]})
 assert m['checks'][r.PRIMARY]['accuracy_no_worse'][r.BUDGET]['mae_lut4']
 assert not m['checks'][r.PRIMARY]['accuracy_no_worse'][r.PREVIOUS]['mae_lut4']
 assert not r.passed(m['checks'][r.PRIMARY])


def fixture():
 pool=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
 pool +=[{'cohort':cohort,'reserved_control':False,'template':cohort} for cohort in ('sharing','legacy') for _ in range(8)]
 pool +=[{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(80)]
 values={n:[128.]*128 for n in r.NAMES};values[r.BUDGET]=[150.]*128
 fresh={'representations':{k:{'pool_cluster_representatives':list(range(128)),'pool_historical_or_training_matches':[]} for k in ('coverage','augmented')}}
 return pool,values,fresh


def test_fixed48_and_all_three_prospective_activities_required():
 pool,values,fresh=fixture()
 for i in range(48,54):values[r.PREVIOUS][i]=145.
 selection=r.choose(pool,values,fresh,r.PRIMARY)
 assert selection['selected_pool_indices']==list(range(54))
 cov=r.coverage(pool,values,selection,fresh,r.PRIMARY)
 assert not cov['passed'] and cov['selected_active_count']==6
 values[r.PREVIOUS][40]=64.;values[r.LEARNED][32]=128.;values[r.PRIMARY][32]=140.
 cov=r.coverage(pool,values,selection,fresh,r.PRIMARY)
 assert cov['passed'] and cov['legacy64_veto_pool_indices']==[40] and cov['sharing128_veto_pool_indices']==[32]


def test_either_representation_collision_excludes_actions_but_never_fixed_rows():
 pool,values,fresh=fixture()
 for i in range(48,54):values[r.PREVIOUS][i]=145.
 fresh['representations']['augmented']['pool_historical_or_training_matches']=[48,0]
 fresh['representations']['coverage']['pool_cluster_representatives'][49]=0
 selected=r.choose(pool,values,fresh,r.PRIMARY)
 assert selected['historical_collision_active_pool_indices']==[48]
 assert selected['fixed_feature_collision_active_pool_indices']==[49]
 assert selected['selected_active_pool_indices']==[50,51,52,53]
 assert selected['selected_pool_indices'][:48]==list(range(48))
 assert not r.coverage(pool,values,selected,fresh,r.PRIMARY)['checks']['augmented_fixed_novel']


def test_training_matrices_share_the_same217_prefix_and_only16_new_columns():
 rows=[{'formula':FORM}];x=np.arange(217.,dtype=float).reshape(1,217)
 a=r.inputs(rows,x,'augmented');b=r.inputs(rows,x,'coverage')
 assert a.shape==(1,233) and b.shape==(1,217)
 assert np.array_equal(a[:,:217],b) and a[0,217:].tolist()==r.local.features(FORM)
