"""Synthetic demo evidence contracts, never claims of new processor results."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from isaforge import codesign as c

SPEC = importlib.util.spec_from_file_location('research_demo', Path(__file__).resolve().parents[1] / 'scripts/build_research_demo.py')
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


@pytest.fixture
def evidence(tmp_path):
    context = {'context_id': 'exact-context', 'workload': 'fixture<script>', 'status': 'verified_complete',
               'manifest_sha256': 'manifest', 'plan_json': json.dumps({'schema':'isaforge-automatic-workload-v1'})}
    baseline = {'context_id':'exact-context','evaluation_id':'eb','candidate_id':None,'name':'baseline','cycles':100,
                'speedup':1.0,'integrated_lut4':100,'timing_feasible':1,'correctness_verified':1,'frequency_mhz':12}
    a = {**baseline,'evaluation_id':'ea','candidate_id':'ledger-a','name':'a','cycles':80,'speedup':1.25,'integrated_lut4':150}
    b = {**baseline,'evaluation_id':'ex','candidate_id':'ledger-b','name':'b','cycles':50,'speedup':2.0,'integrated_lut4':229}
    candidates = [{'context_id':'exact-context','candidate_id':'ledger-'+name,'formula':formula,'features_json':'{"runs": 2}'}
                  for name,formula in [('a','add(in0,in1)'),('b','sub(in0,in1)')]]
    data = dict(contexts=[context],candidates=candidates,measurements=[baseline,a,b],routes=[],cost_summary=[],failures=[])
    public = [{'candidate_id':'public-'+name,'benchmark':'embench-fixture<script>:exact-context','formula':r['formula'],'runs':2}
              for name,r in zip(('a','b'),candidates)]
    directory = tmp_path / 'selection'
    directory.mkdir()
    c.seal(directory/'public.json', public)
    c.seal(directory/'predictions.json', [])
    protocol = dict(schema='isaforge-prospective-selection-v1',target_workload='embench-fixture<script>',target_candidates=2,
                    target_labels_read=0,area_cap=228,contexts={'context':'bound'},policies=['fixed','random'],seeds=[0,1],budgets=[1,2],
                    historical_fit_rows=5,historical_candidate_wall_seconds=8,calibration_command_seconds=4,
                    artifacts={name:c.sha(directory/name) for name in ('public.json','predictions.json')})
    c.seal(directory/'protocol.json',protocol)
    runs=[]
    for policy in protocol['policies']:
        for seed in protocol['seeds']:
            curve=[]
            for budget in protocol['budgets']:
                ids=['public-a','public-b'] if policy=='fixed' else ['public-b','public-a']
                best=1.25 if policy=='fixed' or budget==2 else 1
                curve.append(dict(budget=budget,measured_ids=ids[:budget],best_speedup=best,regret=1.25-best,
                                  target_candidate_wall_seconds=budget*3))
            runs.append(dict(policy=policy,seed=seed,curve=curve,fit_and_predict_seconds=.1))
    summary=[]
    for policy in protocol['policies']:
        for budget in protocol['budgets']:
            point=next(r for r in runs if r['policy']==policy)['curve'][budget-1]
            summary.append(dict(policy=policy,budget=budget,mean_best_speedup=point['best_speedup'],mean_regret=point['regret'],
                                oracle_hits=2 if point['regret']==0 else 0,mean_target_candidate_wall_seconds=budget*3))
    report=dict(protocol_sha256=c.sha(directory/'protocol.json'),contexts=protocol['contexts'],oracle_speedup=1.25,
                oracle_label_count=2,runs=runs,summary=summary,diagnostics=[],limitations=['<script>bad</script>'])
    c.seal(directory/'report.json',report)
    return data,directory,tmp_path/'output.html'


def test_area_timing_correctness_and_baseline_fallback(evidence):
    data,_,_=evidence
    assert demo.workload_rows(data)[0]['best']['name']=='a'
    for field,value in [('timing_feasible',0),('correctness_verified',0),('frequency_mhz',13)]:
        changed=copy.deepcopy(data)
        changed['measurements'][1][field]=value
        assert demo.workload_rows(changed)[0]['best']['name']=='baseline'
    changed=copy.deepcopy(data)
    changed['measurements'][1].update(cycles=200,speedup=.5)
    assert demo.workload_rows(changed)[0]['best']['name']=='baseline'


def test_exact_context_and_public_candidate_join(evidence):
    data,directory,_=evidence
    result=demo.load_selection(directory,data,demo.workload_rows(data))
    assert result['target_context_id']=='exact-context'
    assert len(result['summary'])==4
    data['candidates'][0]['features_json']='{"runs": 99}'
    with pytest.raises(ValueError,match='features differ'):
        demo.load_selection(directory,data,demo.workload_rows(data))


def test_incomplete_context_not_counted_as_verified(evidence):
    data,_,_=evidence
    data['contexts'].append({**data['contexts'][0],'context_id':'failed','status':'incomplete'})
    assert len(demo.workload_rows(data))==1


def test_escaping_and_offline_html(evidence,monkeypatch):
    data,directory,output=evidence
    monkeypatch.setattr(demo.ledger,'export',lambda _:data)
    monkeypatch.setattr(demo,'_chart',lambda _: '<svg aria-label="fixture plot"></svg>')
    demo.build('fixture.sqlite',directory,output)
    html=output.read_text()
    assert 'fixture&lt;script&gt;' in html and '&lt;script&gt;bad&lt;/script&gt;' in html
    assert '<script>' not in html and '<script src=' not in html and 'cdn.' not in html
    assert 'dependent seed repetitions' in html and 'Consumed development evidence' not in html
    assert 'original CRC32 source-adapter' in html
    assert 'baseline +128 LUT4 (228 total)' in html
    assert 'not calibrated confidence' in html


def test_sealed_report_tampering_rejected(evidence):
    data,directory,_=evidence
    (directory/'report.json').write_text('{}')
    with pytest.raises(ValueError,match='Cached record changed'):
        demo.load_selection(directory,data,demo.workload_rows(data))


@pytest.mark.parametrize('mutation,message',[
    ('endpoint','endpoint differs'),('summary','arithmetic differs'),('missing_seed','Missing policy/seed'),
    ('duplicate_query','charged measurement'),('area_cap','area cap'),('context','target must join')])
def test_report_evidence_mismatches_fail(evidence,mutation,message):
    data,directory,_=evidence
    protocol=c.unseal(directory/'protocol.json'); report=c.unseal(directory/'report.json')
    if mutation=='endpoint': report['runs'][0]['curve'][0]['best_speedup']=2
    elif mutation=='summary': report['summary'][0]['mean_best_speedup']=2
    elif mutation=='missing_seed': report['runs'].pop()
    elif mutation=='duplicate_query': report['runs'][0]['curve'][1]['measured_ids']=['public-a','public-a']
    elif mutation=='area_cap': protocol['area_cap']=999
    elif mutation=='context':
        for rows in (data['contexts'],data['candidates'],data['measurements']):
            for row in rows: row['context_id']='other-context'
    c.seal(directory/'protocol.json',protocol)
    report['protocol_sha256']=c.sha(directory/'protocol.json')
    c.seal(directory/'report.json',report)
    with pytest.raises(ValueError,match=message):
        demo.load_selection(directory,data,demo.workload_rows(data))


def test_ambiguous_baseline_fails(evidence):
    data,_,_=evidence
    data['measurements'].append(dict(data['measurements'][0]))
    with pytest.raises(ValueError,match='Exactly one baseline'):
        demo.workload_rows(data)


def test_matplotlib_chart_is_embedded_svg(evidence):
    data,directory,_=evidence
    selection=demo.load_selection(directory,data,demo.workload_rows(data))
    svg=demo._chart(selection)
    assert svg.startswith('<svg')
    assert 'Charged candidate evaluations' in svg and 'measured pool oracle' in svg
    assert 'http://www.w3.org' in svg  # Namespace only, not a network request.
