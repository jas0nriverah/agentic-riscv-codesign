"""Learned physical-cap support, matched representations and prospective activity."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('learning',Path(__file__).parents[1]/'scripts/learn_boundary_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
IN='xor(add(sra(addi(xori(in0,11),73),andi(in1,3)),in1),or(in0,in1))'
OUT='xor(add(sra(addi(xori(in0,11),73),andi(in1,3)),in1),in0)'


def test_raw_means_support_only_crossed_physical_caps_and_never_replace_good_points():
 p,c=r.budget_support([126.,20.,64.,126.],[145.,150.,100.,145.],[125.,31.,1.,128.01],[True,True,True,True])
 assert p==[128.,32.,64.,145.] and c==[[128],[32,64,128],[64],[]]
 p,_=r.budget_support([100.],[120.],[50.],[True])
 assert p==[120.] # Raw50 cannot lower an already accepted128 estimate.


def test_outside_learning_scope_and_all_previous_repairs_are_exactly_preserved(monkeypatch):
 class Model:
  def __init__(self,width):self.width=width
  def predict(self,x):assert x.shape[1]==self.width;return np.full(len(x),125.)
 old={n:[145.,145.,128.] for n in r.incumbent.NAMES};old[r.CURRENT]=[126.,126.,126.]
 monkeypatch.setattr(r.incumbent,'points',lambda *args:(old,[],{}))
 rows=[{'formula':f} for f in (IN,OUT,IN)]
 values,_,details=r.points(rows,np.zeros((3,336)),{'augmented':Model(233),'coverage':Model(217)},object())
 assert values[r.PRIMARY]==[128.,145.,128.]
 assert values[r.FALLBACK]==[128.,145.,128.] and details['learning_scope']==[True,False,True]


def test_previous_accuracy_cannot_be_offset_by_release_improvement():
 models={n:[129.] for n in r.NAMES};models[r.CURRENT]=[126.];models[r.BUDGET]=[150.];models[r.PREVIOUS]=[128.];models[r.PRIMARY]=[126.]
 m=r.panel_metrics({'models':models,'actual_lut4':[128.]})
 assert m['checks'][r.PRIMARY]['accuracy_no_worse_release']['mae_lut4']
 assert not m['checks'][r.PRIMARY]['accuracy_no_worse_previous']['mae_lut4']
 assert not r.passed(m['checks'][r.PRIMARY])


def test_false_accept_increase_blocks_even_if_false_rejection_is_repaired():
 models={n:[128.,128.] for n in r.NAMES};models[r.CURRENT]=[125.,125.];models[r.BUDGET]=[140.,140.];models[r.PREVIOUS]=[140.,140.]
 m=r.panel_metrics({'models':models,'actual_lut4':[125.,159.]})
 assert m['checks'][r.PRIMARY]['caps']['128']=={'false_accept_no_worse_release':False,'false_reject_no_worse_signed':True}
 assert not r.passed(m['checks'][r.PRIMARY])


def fixture():
 pool=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
 pool +=[{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(96)]
 values={n:[128.]*128 for n in r.NAMES};values[r.BUDGET]=[150.]*128
 fresh={'representations':{k:{'pool_cluster_representatives':list(range(128)),'pool_historical_or_training_matches':[]} for k in ('coverage','augmented')}}
 return pool,values,fresh


def test_activity_requires_new_learned_change_not_inherited_median_correction():
 pool,values,fresh=fixture()
 assert r.choose(pool,values,fresh,r.PRIMARY)['raw_active_pool_indices']==[]
 for i in range(32,38):values[r.PREVIOUS][i]=145.
 selected=r.choose(pool,values,fresh,r.PRIMARY)
 assert selected['selected_active_pool_indices']==list(range(32,38))
 assert r.coverage(pool,values,selected,fresh,r.PRIMARY)['passed']


def test_either_feature_representation_collision_excludes_without_replacements():
 pool,values,fresh=fixture()
 for i in range(32,38):values[r.PREVIOUS][i]=145.
 fresh['representations']['augmented']['pool_historical_or_training_matches']=[32]
 fresh['representations']['coverage']['pool_cluster_representatives'][33]=0
 selected=r.choose(pool,values,fresh,r.PRIMARY)
 assert selected['historical_collision_active_pool_indices']==[32]
 assert selected['general_feature_collision_active_pool_indices']==[33]
 assert selected['selected_active_pool_indices']==[34,35,36,37]
 assert selected['selected_pool_indices'][:32]==list(range(32))
