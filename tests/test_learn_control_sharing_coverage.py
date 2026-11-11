"""Coverage-only intervention invariants, without fitting classifiers or native jobs."""
import importlib.util,json
from pathlib import Path
import numpy as np
import pytest
SPEC=importlib.util.spec_from_file_location('control_coverage',Path(__file__).parents[1]/'scripts/learn_control_sharing_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
FORM='xor(add(sra(addi(xori(in0,11),73),andi(in1,3)),in1),in0)'


def test_one_fixed233_intervention_preserves_algorithm_features_and_half_rule():
 assert r.CANDIDATES==(r.NAME,) and r.PARAMETERS==r.baseline.PARAMETERS
 assert r.columns()==r.baseline.columns('augmented') and len(r.columns())==233
 p,c=r.budget_support([126.,60.],[145.,73.],[ [0.,0.,.5],[0.,.49,.9] ],[True,True])
 assert p==[128.,73.] and c==[[128],[]]


def test_failed_active_classifier_is_not_a_global_accuracy_comparator():
 values={n:[150.] for n in r.NAMES};values[r.CURRENT]=[128.];values[r.FROZEN_BASELINE]=[128.]
 # Rejecting the unsafe129 atrelease fixesclassification but worsens MAE against the unsafe128 point.
 row={'models':values,'actual_lut4':[129.]}
 m=r.panel_metrics(row)
 assert len(m['checks'][r.NAME]['accuracy_no_worse'])==6 and r.passed(m['checks'][r.NAME])
 extra=r.panel_metrics(row,True)
 assert len(extra['checks'][r.NAME]['accuracy_no_worse'])==7
 assert not extra['checks'][r.NAME]['accuracy_no_worse'][r.FROZEN_BASELINE]['mae_lut4']
 assert not r.passed(extra['checks'][r.NAME])


def test_only_validated_general_and_legacy_panels_receive_extra_baseline_gate():
 assert r.VALIDATED_PANELS==('consumed-twelfth-general32','consumed-twelfth-legacy8')
 values={n:[145.] for n in r.NAMES};values[r.CURRENT]=[126.];values[r.FROZEN_BASELINE]=[128.]
 row={'models':values,'actual_lut4':[125.]}
 m=r.subset(row,[0],True)
 assert not m['checks'][r.NAME]['accuracy_no_worse'][r.FROZEN_BASELINE]['mae_lut4']
 assert r.FROZEN_BASELINE not in r.subset(row,[0])['checks'][r.NAME]['accuracy_no_worse']


def test_append32_uses_exact_frozen1889_prefix_and_never_consumed_targets(tmp_path,monkeypatch):
 new=[{'candidate_id':'new:'+str(i),'formula':FORM} for i in range(32)]
 (tmp_path/'candidates.json').write_text(json.dumps(new));(tmp_path/'features.json').write_text('{}');(tmp_path/'labels.json').write_text('[]')
 monkeypatch.setattr(r.prior,'feature_matrix',lambda rows,features:np.zeros((len(rows),336)))
 monkeypatch.setattr(r.prior,'labels_for',lambda rows,labels:[50.]*len(rows))
 rows,x,y,labels=r.training_data(tmp_path)
 with np.load(r.baseline.OUT/'training-inputs.npz') as d:
  assert np.array_equal(x['augmented'][:1889],d['augmented']) and np.array_equal(y[:1889],d['y'])
 assert x['augmented'].shape==(1921,233) and len(rows)==1921 and np.array_equal(x['coverage'],x['augmented'][:,:217])
 assert y[1889:].tolist()==[50.]*32 and rows[1889]['fit_source']=='new_training32'
 assert labels.shape==(1921,3) and np.all(np.diff(labels.astype(int),axis=1)>=0)


def test_single_fit_parent_and_independent_pretrain_approval_are_protocol_bound(tmp_path,monkeypatch):
 output=tmp_path/'model';training=tmp_path/'data';output.mkdir();training.mkdir();(output/'protocol.json').write_text('{}\n')
 monkeypatch.setattr(r,'ROOT',tmp_path);monkeypatch.setattr(r.prior,'relative',lambda p:str(p.relative_to(tmp_path)))
 for name in ('labels.json','features.json','completion.json'):(training/name).write_text('{}\n')
 digest=r.sha(output/'protocol.json');approval={'protocol_sha256':digest,'allow_one_classifier_fit':True,'authorizer':'parent','bindings':{r.prior.relative(training/n):r.sha(training/n) for n in ('labels.json','features.json','completion.json')}}
 audit={'status':'pass','bindings':{r.prior.relative(output/'protocol.json'):digest}}
 (output/'execution-authorization.json').write_text(json.dumps(approval));(training/'preflight-audit.json').write_text(json.dumps(audit))
 with pytest.raises(FileNotFoundError):r.validate_execution_approval(output,training)
 (training/'pretrain-audit.json').write_text(json.dumps({**audit,'status':'fail'}))
 with pytest.raises(ValueError):r.validate_execution_approval(output,training)
 (training/'pretrain-audit.json').write_text(json.dumps(audit));assert r.validate_execution_approval(output,training)==(approval,audit)
 (output/'execution-authorization.json').write_text(json.dumps({**approval,'protocol_sha256':'wrong'}))
 with pytest.raises(ValueError):r.validate_execution_approval(output,training)


def test_receipt_and_new_training_label_tampering_block_before_fit(tmp_path,monkeypatch):
 output=tmp_path/'model';training=tmp_path/'data';output.mkdir();training.mkdir();(output/'protocol.json').write_text('{}\n')
 monkeypatch.setattr(r,'ROOT',tmp_path);monkeypatch.setattr(r.prior,'relative',lambda p:str(p.relative_to(tmp_path)))
 for n in ('labels.json','features.json','completion.json','receipt-note.json'):(training/n).write_text('{}\n')
 digest=r.sha(output/'protocol.json');parent={'protocol_sha256':digest,'allow_one_classifier_fit':True,'authorizer':'parent','bindings':{r.prior.relative(training/n):r.sha(training/n) for n in ('labels.json','features.json','completion.json')}}
 audit={'status':'pass','bindings':{r.prior.relative(output/'protocol.json'):digest,r.prior.relative(training/'receipt-note.json'):r.sha(training/'receipt-note.json')}}
 (output/'execution-authorization.json').write_text(json.dumps(parent))
 for n in ('preflight-audit.json','pretrain-audit.json'):(training/n).write_text(json.dumps(audit))
 r.validate_execution_approval(output,training)
 (training/'receipt-note.json').write_text('{"tampered":true}\n')
 with pytest.raises(ValueError):r.validate_execution_approval(output,training)
 (training/'receipt-note.json').write_text('{}\n');(training/'labels.json').write_text('{"tampered":true}\n')
 with pytest.raises(ValueError):r.validate_execution_approval(output,training)


def fixture():
 pool=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
 pool +=[{'cohort':g,'reserved_control':False,'template':g} for g in ('sharing','legacy') for _ in range(8)]
 pool +=[{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(48)]
 values={n:[128.]*96 for n in r.NAMES};values[r.BUDGET]=[150.]*96
 fresh={'representations':{k:{'pool_cluster_representatives':list(range(96)),'pool_historical_or_training_matches':[]} for k in ('coverage','augmented')}}
 return pool,values,fresh


def test_activity_is_new_vs_frozen_classifier_and_mandatory48_cannot_be_dropped():
 pool,v,f=fixture()
 for i in range(48,54):v[r.baseline.PREVIOUS][i]=145.
 assert not r.choose(pool,v,f,r.NAME)['raw_active_pool_indices']
 for i in range(48,54):v[r.FROZEN_BASELINE][i]=145.
 v[r.ABSTENTION][40]=64.;v[r.LEARNED][32]=128.;v[r.NAME][32]=140.
 selection=r.choose(pool,v,f,r.NAME);assert selection['selected_pool_indices']==list(range(54))
 assert r.coverage(pool,v,selection,f,r.NAME)['passed']
 f['representations']['augmented']['pool_historical_or_training_matches']=[48,0]
 selected=r.choose(pool,v,f,r.NAME)
 assert selected['selected_pool_indices'][:48]==list(range(48)) and 48 not in selected['selected_active_pool_indices']
 assert not r.coverage(pool,v,selected,f,r.NAME)['checks']['augmented_fixed_novel']


def test_no_cap_error_offsets_and_raw_probabilities_stay_separate_from_old_baseline():
 values={n:[128.,128.] for n in r.NAMES};values[r.CURRENT]=[125.,125.];values[r.BUDGET]=[140.,140.]
 m=r.panel_metrics({'models':values,'actual_lut4':[125.,130.]})
 assert not m['checks'][r.NAME]['caps']['128']['no_new_false_accept_cases'] and not r.passed(m['checks'][r.NAME])
 class Model:
  n_outputs_=3;classes_=[np.array([0,1])]*3
  def predict_proba(self,x):return [np.tile(p,(len(x),1)) for p in ([1.,0.],[1.,0.],[0.,1.])]
 old={n:[145.] for n in r.baseline.NAMES};old[r.CURRENT]=[126.]
 v,_,d=r.points([{'formula':FORM}],np.zeros((1,217)),{'augmented':Model()},r.derive_support([FORM]),{'models':old,'routes':[],'feasibility_probabilities':{'old':[[0.,0.,.4]]}})
 assert v[r.NAME]==[128.] and d['coverage_feasibility_probabilities'][r.NAME]==[[0.,0.,1.]]
 assert d['feasibility_probabilities']=={'old':[[0.,0.,.4]]}


def test_all_inherited_and_new_gates_are_retained_and_analytically_feasible():
 panels=r.read(r.baseline.OUT/'development-predictions.json');saved=r.read(r.baseline.OUT/'fresh-predictions.json');rows=r.read(r.baseline.FRESH/'candidates.json');y=r.prior.labels_for(rows,r.read(r.baseline.FRESH/'labels.json'))
 for name,key in [('consumed-twelfth-general32','general_selected_indices'),('consumed-twelfth-sharing8','sharing_selected_indices'),('consumed-twelfth-legacy8','legacy_selected_indices'),('consumed-twelfth-conditional16','conditional_selected_indices')]:
  ix=saved[key];panels[name]={**r.baseline.point_subset(saved,ix),'actual_lut4':[y[i] for i in ix]}
 for row in panels.values():
  # Evaluation-only truth oracle proves compatibility; it is never an estimator or fit input.
  truth=(np.asarray(row['actual_lut4'])[:,None]<=np.asarray(r.CAPS)[None,:]).astype(float)
  row['models'][r.NAME]=r.budget_support(row['models'][r.CURRENT],row['models'][r.BUDGET],truth,[bool(r.local.learning_scope(f)) for f in row['formulas']])[0]
 m=r.development_metrics(panels)
 assert len(m['panels'])==26 and len(m['named_regressions'])==33 and len(m['evaluation_cases'])==100
 assert m['selected_candidate']==r.NAME and m['gates'][r.NAME]['development_gate_passed']
 assert len(m['panels']['consumed-twelfth-general32']['checks'][r.NAME]['accuracy_no_worse'])==7
 assert len(m['panels']['consumed-twelfth-conditional16']['checks'][r.NAME]['accuracy_no_worse'])==6
