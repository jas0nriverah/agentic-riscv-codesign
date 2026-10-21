"""Generic prelabel freeze, exported prediction, and replay integration."""
import copy
from pathlib import Path
import pytest
from isaforge import codesign as c
from isaforge import feasible_benefit_experiment as e
from isaforge.feasible_benefit import FeasibleBenefitPredictor

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def case():
    path=ROOT/'results/2026-10-21-sha256-selection/model'
    protocol=c.unseal(path/'protocol.json')
    return dict(history=c.unseal(path/'history.json'),public=c.unseal(path/'public.json'),
                contexts=protocol['contexts'],target_workload=protocol['target_workload'])


@pytest.mark.parametrize('observed',[1,6,True,None,-1])
def test_zero_label_assertion_before_writes(case,tmp_path,observed):
    output=tmp_path/'freeze'
    with pytest.raises(ValueError,match='zero observed'):
        e.freeze(**case,output=output,target_labels_observed=observed,calibration_cost_seconds=0)
    assert not output.exists()


def test_target_source_excluded_before_writes(case,tmp_path):
    case['history'][0]['workload_group']=case['target_workload']
    with pytest.raises(ValueError,match='Target source'):
        e.freeze(**case,output=tmp_path/'freeze',target_labels_observed=0,calibration_cost_seconds=0)
    assert not (tmp_path/'freeze').exists()


def test_postfilter_groups_checked_before_model_fitting(case,tmp_path):
    for row in case['history']:row['workload_group']='single-history'
    with pytest.raises(ValueError,match='two post-family-filter'):
        e.freeze(**case,output=tmp_path/'freeze',target_labels_observed=0,calibration_cost_seconds=0)
    assert not (tmp_path/'freeze').exists()


def test_generic_model_freeze_export_and_11_policy_replay(case,tmp_path):
    path=ROOT/'results/2026-10-21-sha256-selection/model'
    archived=c.unseal(path/'report.json')
    labels={ev['candidate_id']:ev['observation'] for run in archived['runs'] for ev in run['events'] if 'observation' in ev}
    output=tmp_path/'freeze'
    protocol=e.freeze(**case,output=output,target_labels_observed=0,calibration_cost_seconds=0,
                      scope='consumed-data development')
    assert protocol['target_labels_read']==0
    assert protocol['historical_fitting_rows']==21
    assert len(protocol['historical_postfilter_groups'])>=2
    assert not (output/'report.json').exists() and not (output/'model/report.json').exists()
    checked=e.authenticate(output)
    predicted=checked['predictions'][0]['by_cap']['64']
    model=FeasibleBenefitPredictor.load(output/'utility-models/seed-0')
    assert model.predict(case['public'],area_cap=64)==predicted
    report=e.evaluate(output,list(labels.values()))
    assert report['trajectories']==165 and report['endpoints']==495
    assert {r['policy'] for r in report['runs']}=={*e.b.POLICIES,e.POLICY}
    new=next(r for r in report['runs'] if r['policy']==e.POLICY and r['cap']==64 and r['seed']==0)
    assert new['curve'][0]['best_speedup']==1
    assert new['curve'][1]['best_speedup']==pytest.approx(1.0213846648661133)
    e.evaluate(output,list(labels.values()),verify=True)
    with pytest.raises(ValueError,match='Preserve prior'):e.evaluate(output,list(labels.values()))
    # Changing the public bytes while resealing the child is still rejected by the parent binding.
    public=c.unseal(output/'model/public.json');public[0]['saved']+=1
    c.seal(output/'model/public.json',public)
    with pytest.raises(ValueError,match='artifact changed'):e.authenticate(output)


def test_cli_freeze_requires_explicit_zero_labels(case,tmp_path):
    for name in ('history','public','contexts'):c.seal(tmp_path/(name+'.json'),case[name])
    arguments=['freeze','--root',str(tmp_path/'freeze'),'--history',str(tmp_path/'history.json'),
        '--public',str(tmp_path/'public.json'),'--contexts',str(tmp_path/'contexts.json'),
        '--target-workload',case['target_workload'],'--calibration-cost-seconds','0']
    with pytest.raises(ValueError,match='Missing freeze'):e.main(arguments)
    assert not (tmp_path/'freeze').exists()
