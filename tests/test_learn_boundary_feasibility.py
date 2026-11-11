"""Direct feasibility probabilities and execution barriers, without any fitted model."""
import importlib.util,json
from pathlib import Path
import numpy as np
import pytest
SPEC=importlib.util.spec_from_file_location('feasibility',Path(__file__).parents[1]/'scripts/learn_boundary_feasibility.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
FORM='xor(add(sra(addi(xori(in0,11),73),andi(in1,3)),in1),in0)'


class Probabilities:
 n_outputs_=3
 def __init__(self,classes,values):self.classes_=[np.asarray(c) for c in classes];self.values=values
 def predict_proba(self,x):return [np.tile(v,(len(x),1)) for v in self.values]


def test_positive_class_mapping_reversed_order_and_singleton_outputs():
 model=Probabilities([[1,0]]*3,[[.2,.8],[.6,.4],[.9,.1]])
 assert r.positive_probabilities(model,np.zeros((2,217))).tolist()==[[.2,.6,.9]]*2
 model=Probabilities([[0],[1],[0,1]],[[1.],[1.],[0.,1.]])
 assert r.positive_probabilities(model,np.zeros((1,233))).tolist()==[[0.,1.,1.]]


def test_unsorted_or_invalid_probabilities_fail_without_sorting_or_repair():
 for model in (Probabilities([[0,1]]*3,[[.3,.7],[.5,.5],[.1,.9]]),Probabilities([[0],[2],[1]],[[1.],[1.],[1.]]),Probabilities([[0,1]]*3,[[.5,.6],[.4,.6],[.1,.9]])):
  with pytest.raises((ValueError,AssertionError)):r.positive_probabilities(model,np.zeros((1,217)))


def test_exact_half_tie_accepts_smallest_crossed_cap_and_never_replaces_release_points():
 p,c=r.budget_support([20.,60.,126.,100.],[150.,73.05,145.,120.],[[.5,.5,.8],[0.,.499999,.9],[0.,0.,.5],[1.,1.,1.]],[True]*4)
 assert p==[32.,73.05,128.,120.] and c==[[32,64,128],[],[128],[]]
 assert r.budget_support([126.],[145.],[[1.,1.,1.]],[False])[0]==[145.]


def test_cached_old_means_remain_distinct_from_new_probabilities_and_no_legacy_bypass():
 old={n:[128.,64.] for n in r.baseline.NAMES};old[r.CURRENT]=[126.,60.];old[r.BUDGET]=[145.,73.05]
 cached={'models':old,'routes':[],'corroboration_raw_lut4':{'old':[129.,84.]}}
 model=Probabilities([[0,1]]*3,[[1.,0.],[1.,0.],[0.,1.]])
 v,_,d=r.points([{'formula':FORM}]*2,np.zeros((2,217)),{'augmented':model,'coverage':model},r.derive_support([FORM]),cached)
 assert v[r.PRIMARY]==[128.,73.05] and v[r.STRUCTURAL]==[128.,64.]
 assert d['corroboration_raw_lut4']==cached['corroboration_raw_lut4']
 assert d['feasibility_probabilities'][r.PRIMARY]==[[0.,0.,1.]]*2


def test_all_six_accuracy_references_and_no_offset_cap_case_gates():
 values={n:[128.,128.] for n in r.NAMES};values[r.CURRENT]=[125.,125.];values[r.BUDGET]=[140.,140.]
 m=r.panel_metrics({'models':values,'actual_lut4':[125.,159.]})
 assert len(m['checks'][r.PRIMARY]['accuracy_no_worse'])==6
 assert not m['checks'][r.PRIMARY]['caps']['128']['no_new_false_accept_cases']
 assert not r.passed(m['checks'][r.PRIMARY])


def test_reused1889_matrices_labels_and_weights_configuration_need_no_fit():
 rows,x,y,labels=r.training_data()
 assert len(rows)==1889 and x['coverage'].shape==(1889,217) and x['augmented'].shape==(1889,233)
 assert np.array_equal(x['coverage'],x['augmented'][:,:217])
 assert labels.sum(axis=0).tolist()==[975,1307,1603]
 assert np.all(np.diff(labels.astype(int),axis=1)>=0)
 assert r.PARAMETERS['n_estimators']==300 and r.PARAMETERS['n_jobs']==1 and r.PARAMETERS['max_features']==1.
 assert r.PARAMETERS['class_weight'] is None and r.PARAMETERS['bootstrap'] is False


def test_parent_and_independent_approvals_must_bind_this_exact_protocol(tmp_path,monkeypatch):
 output=tmp_path/'model';fresh=tmp_path/'data';output.mkdir();fresh.mkdir()
 (output/'protocol.json').write_text('{}\n');digest=r.sha(output/'protocol.json')
 monkeypatch.setattr(r.prior,'relative',lambda p:p.name)
 def save(parent,audit):
  (output/'execution-authorization.json').write_text(json.dumps(parent));(fresh/'preflight-audit.json').write_text(json.dumps(audit))
 parent={'protocol_sha256':digest,'allow_two_classifier_fits':True,'authorizer':'parent'}
 audit={'status':'pass','bindings':{'protocol.json':digest}}
 for p,a in [({**parent,'allow_two_classifier_fits':False},audit),({**parent,'protocol_sha256':'wrong'},audit),(parent,{**audit,'status':'fail'}),(parent,{'status':'pass','bindings':{'protocol.json':'wrong'}})]:
  save(p,a)
  with pytest.raises((ValueError,AssertionError)):r.validate_execution_approval(output,fresh)
 save(parent,audit);assert r.validate_execution_approval(output,fresh)==(parent,audit)


def fixture():
 pool=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
 pool +=[{'cohort':g,'reserved_control':False,'template':g} for g in ('sharing','legacy') for _ in range(8)]
 pool +=[{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(80)]
 values={n:[128.]*128 for n in r.NAMES};values[r.BUDGET]=[150.]*128
 fresh={'representations':{k:{'pool_cluster_representatives':list(range(128)),'pool_historical_or_training_matches':[]} for k in ('coverage','augmented')}}
 return pool,values,fresh


def test_new_actions_compare_classifier_to_latest_augmented_mean_policy():
 pool,v,f=fixture()
 for i in range(48,54):v[r.ABSTENTION][i]=145.
 assert r.choose(pool,v,f,r.PRIMARY)['raw_active_pool_indices']==[]
 for i in range(48,54):v[r.PREVIOUS][i]=145.
 v[r.ABSTENTION][40]=64.;v[r.LEARNED][32]=128.;v[r.PRIMARY][32]=140.
 chosen=r.choose(pool,v,f,r.PRIMARY)
 assert chosen['selected_pool_indices']==list(range(54)) and r.coverage(pool,v,chosen,f,r.PRIMARY)['passed']
 f['representations']['augmented']['pool_historical_or_training_matches']=[48]
 assert r.choose(pool,v,f,r.PRIMARY)['selected_active_pool_indices']==[50,49,52,51,53]


def test_expanded_retained_metrics_recompute_every_named_group_without_fits():
 panels=r.read(r.baseline.OUT/'development-predictions.json');fresh=r.read(r.baseline.OUT/'fresh-predictions.json');rows=r.read(r.baseline.FRESH/'candidates.json');y=r.prior.labels_for(rows,r.read(r.baseline.FRESH/'labels.json'))
 for name,key in [('consumed-eleventh-general32','general_selected_indices'),('consumed-eleventh-sharing8','sharing_selected_indices'),('consumed-eleventh-legacy8','legacy_selected_indices'),('consumed-eleventh-conditional9','conditional_selected_indices')]:
  ix=fresh[key];panels[name]={**r.baseline.point_subset(fresh,ix),'actual_lut4':[y[i] for i in ix]}
 for row in panels.values():
  for n in r.CANDIDATES:row['models'][n]=list(row['models'][r.PREVIOUS])
 m=r.development_metrics(panels)
 assert len(m['panels'])==22 and len(m['named_regressions'])==25 and len(m['evaluation_cases'])==73
 assert m['selected_candidate'] is None and m['retained_metric_rows']==1049


def test_feature_freeze_missing_wrong_protocol_and_tampering_block_before_fit(tmp_path,monkeypatch):
 output=tmp_path/'model';output.mkdir();(output/'protocol.json').write_text('{}\n')
 monkeypatch.setattr(r,'ROOT',tmp_path)
 with pytest.raises(FileNotFoundError):r.validate_feature_freeze(output)
 features=tmp_path/'pool-features.json';features.write_text('{"records":[]}\n')
 seal={'protocol_sha256':r.sha(output/'protocol.json'),'bindings':{'pool-features.json':r.sha(features)}}
 (output/'feature-freeze.json').write_text(json.dumps({**seal,'protocol_sha256':'wrong'}))
 with pytest.raises(ValueError):r.validate_feature_freeze(output)
 (output/'feature-freeze.json').write_text(json.dumps(seal));assert r.validate_feature_freeze(output)==seal
 features.write_text('{"records":["tampered"]}\n')
 with pytest.raises(ValueError):r.validate_feature_freeze(output)
