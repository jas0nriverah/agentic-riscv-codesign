"""Small synthetic fixture only: no retrospective 39-row fits or native jobs."""
import copy
from pathlib import Path

import pytest
from isaforge import codesign as c
from isaforge.features import candidate_id,extract_features
from isaforge.prospective_selection import PUBLIC_KEYS
from scripts import diagnose_factorized_selection as d

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def corpus(tmp_path):
    template=c.unseal(ROOT/'results/2026-10-21-sha256-selection/model/history.json')[0]
    rows=[];failed=[]
    definitions=[('embench-nettle-sha256','add(in0,slli(in1,{k}))',2),
                 ('source-b','xor(in0,srli(in1,{k}))',1),
                 ('source-c','and(in0,slli(in1,{k}))',1),
                 ('source-d','or(in0,srli(in1,{k}))',1)]
    for group,formula,contexts in definitions:
        for context in range(contexts):
            for index in range(3):
                row=copy.deepcopy(template)
                row['benchmark']=group+':context-'+str(context)
                row['formula']=formula.format(k=index+1)
                features=extract_features(dict(formula=row['formula'],size=2,runs=row['runs'],places=1,
                    saved=row['runs'],savedPercent=1.0))
                row.update(features,candidate_id=candidate_id(row['benchmark'],row['formula']),workload_group=group,
                           area_delta_lut4=(20,70,140)[index],measurement_seconds=float(index+1))
                rows.append(row)
    for index,(group,formula,_) in enumerate(definitions[:3]):
        row={key:copy.deepcopy(value) for key,value in rows[next(i for i,r in enumerate(rows) if r['workload_group']==group)].items()
             if key in PUBLIC_KEYS}
        row['formula']=formula.format(k=30)
        row['candidate_id']=candidate_id(row['benchmark'],row['formula'])
        row['max_abs_constant']=30
        row.update(status='failed',measurement_seconds=float(index+4),error='synthetic failed attempt',
            workload_group=group,reference_censored=index==2,
            failure_class='infrastructure_unknown' if index==2 else 'self_check_failure')
        failed.append(row)
    result=dict(rows=rows,failed_attempts=failed,successful_labels=len(rows),
        independent_workload_groups=sorted({r['workload_group'] for r in rows}),
        total_candidate_attempts=len(rows)+len(failed),
        total_candidate_attempt_wall_seconds=sum(r['measurement_seconds'] for r in rows+failed),timer_note='synthetic fixture')
    path=tmp_path/'corpus.json';c.seal(path,result)
    return result,path


def test_entire_sha_source_and_both_contexts_are_held_out_together(corpus):
    data,_=corpus
    folds=d.folds(data);sha=next(f for f in folds if f['source']=='embench-nettle-sha256')
    assert len(sha['target_contexts'])==2
    assert all(row['workload_group']!='embench-nettle-sha256' for row in sha['fitting'])
    assert len(sha['target'])==7
    assert all(row.get('status','success')=='success' for fold in folds for row in fold['fitting'])
    assert all(len(fold['fitting_groups'])>=2 for fold in folds)


def test_family_exclusion_uses_failed_rows_in_the_entire_held_source_pool(corpus):
    data,_=corpus;modified=copy.deepcopy(data)
    # A failed held-source formula is related to every source-b success. It must
    # exclude those fitting labels despite never providing a feasibility target.
    failure=modified['failed_attempts'][0]
    source_b=next(row for row in modified['rows'] if row['workload_group']=='source-b')
    failure['formula']=source_b['formula'];failure['candidate_id']='failed-shared-family'
    sha=next(f for f in d.folds(modified) if f['source']=='embench-nettle-sha256')
    assert 'source-b' not in sha['fitting_groups'] and len(sha['fitting_groups'])==2
    assert {r['candidate_id'] for r in modified['rows'] if r['workload_group']=='source-b'}<=set(sha['excluded_related_ids'])


def test_two_group_gate_prevents_a_silent_weak_fold(corpus):
    data,_=corpus;modified=copy.deepcopy(data)
    modified['rows']=[r for r in modified['rows'] if r['workload_group']!='source-d']
    modified['successful_labels']=len(modified['rows'])
    modified['total_candidate_attempts']=len(modified['rows'])+len(modified['failed_attempts'])
    modified['independent_workload_groups'].remove('source-d')
    modified['failed_attempts'][0]['formula']=next(r['formula'] for r in modified['rows'] if r['workload_group']=='source-b')
    with pytest.raises(ValueError,match='two post-family-filter'):d.folds(modified)


def test_monotonicity_counts_and_independent_gp_factor_exact():
    by_cap={str(cap):[dict(candidate_id='a',score=a),dict(candidate_id='b',score=b)]
            for cap,a,b in [(32,.8,.1),(64,.4,.2),(128,.6,.15)]}
    violations=d.cap_violations(by_cap,'score')
    assert [(r['candidate_id'],r['lower_cap'],r['upper_cap']) for r in violations]==[('a',32,64),('b',64,128)]
    assert violations[0]['decrease']==pytest.approx(.4)
    estimate=dict(area_delta_lut4_mean=64,area_delta_lut4_std=0,routed_fmax_min_mhz_mean=12,
                  routed_fmax_min_mhz_std=0,device_fit_probability=.8)
    assert d.gp_feasibility(estimate,32)==0
    assert d.gp_feasibility(estimate,64)==.8
    assert d.gp_feasibility(estimate,128)==.8


def test_fixed_fixture_diagnosis_fits_only_classifier_and_gp_and_replays(corpus,tmp_path,monkeypatch):
    data,path=corpus;fits=[]
    original=d.FeasibilitySelectionPredictor.fit
    def tracked(self,rows):
        fits.append([r['candidate_id'] for r in rows])
        assert all(r.get('status','success')=='success' for r in rows)
        return original(self,rows)
    monkeypatch.setattr(d.FeasibilitySelectionPredictor,'fit',tracked)
    def unrelated_models_forbidden(*args,**kwargs):raise AssertionError('Do not fit all retrospective artifact models')
    monkeypatch.setattr(d.b,'zero_shot',unrelated_models_forbidden)
    output=tmp_path/'first'
    result=d.run(output,corpus_path=path)
    expected=d.folds(data)
    assert len(fits)==len(expected)*5
    assert fits==[fold['fitting_ids'] for fold in expected for _ in range(5)]
    assert result['costs']['unique_attempts']==18
    assert result['costs']['recorded_verification_failures']==2
    assert result['costs']['unknown_infrastructure_attempts']==1
    assert result['costs']['failed_attempt_seconds']==15
    assert result['costs']['unique_recorded_attempt_seconds']==data['total_candidate_attempt_wall_seconds']
    assert len(result['selection_runs'])==5*5*3*2  # Five contexts; four source folds.
    assert {r['policy'] for r in result['selection_runs']}=={'factorized_feasibility_xgb','latency_cost_heuristic'}
    for metric in result['per_seed_brier']:
        source=metric['source']
        assert metric['known_rows']==sum(r['workload_group']==source for r in data['rows'])
        assert metric['excluded_unknown_rows']==sum(r['workload_group']==source for r in data['failed_attempts'])
    for macro in result['source_macro_brier']:
        source_values=[r['mean_brier'] for r in result['per_source_brier']
                       if r['cap']==macro['cap'] and r['method']==macro['method']]
        assert len(source_values)==macro['sources']==4
        assert macro['source_macro_brier']==pytest.approx(sum(source_values)/4)
    for run in result['selection_runs']:
        assert len(run['curve'])==3 and run['curve'][-1]['budget']==3
        assert run['curve'][-1]['target_measurement_seconds']>0
    predictions=c.unseal(output/'predictions.json')
    assert {p['source'] for p in predictions}==set(data['independent_workload_groups'])
    d.replay(output,tmp_path/'second',corpus_path=path)
    assert c.unseal(output/'predictions.json')==c.unseal(tmp_path/'second/predictions.json')
    with pytest.raises(ValueError,match='Fresh diagnosis'):d.run(output,corpus_path=path)


def test_cost_mismatch_fails_before_fits(corpus,tmp_path,monkeypatch):
    data,path=corpus;data['total_candidate_attempt_wall_seconds']+=1;c.seal(path,data)
    def forbidden(*args):raise AssertionError('No fit after invalid cost accounting')
    monkeypatch.setattr(d.FeasibilitySelectionPredictor,'fit',forbidden)
    with pytest.raises(ValueError,match='unique attempt cost'):d.run(tmp_path/'bad',corpus_path=path)


def test_replay_rejects_resealed_artifact_tampering_before_fit(corpus,tmp_path,monkeypatch):
    _,path=corpus;archive=tmp_path/'archive'
    c.seal(archive/'protocol.json',{})
    c.seal(archive/'predictions.json',[])
    c.seal(archive/'report.json',{})
    c.seal(archive/'manifest.json',{str(p.relative_to(archive)):c.sha(p)
        for p in archive.rglob('*') if p.is_file()})
    c.seal(archive/'predictions.json',[dict(changed=True)])
    def forbidden(*args,**kwargs):raise AssertionError('Do not refit altered artifacts')
    monkeypatch.setattr(d,'run',forbidden)
    with pytest.raises(ValueError,match='artifact changed'):d.replay(archive,tmp_path/'new',corpus_path=path)


def test_replay_requires_complete_source_and_package_bindings(corpus,tmp_path,monkeypatch):
    _,path=corpus;archive=tmp_path/'archive'
    c.seal(archive/'protocol.json',dict(schema='isaforge-factorized-source-diagnosis-v1',scope='consumed-data development',
        corpus_sha256=c.sha(path),source_bindings={},packages={}))
    c.seal(archive/'manifest.json',{str(p.relative_to(archive)):c.sha(p)
        for p in archive.rglob('*') if p.is_file()})
    def forbidden(*args,**kwargs):raise AssertionError('Do not refit missing bindings')
    monkeypatch.setattr(d,'run',forbidden)
    with pytest.raises(ValueError,match='source bindings'):d.replay(archive,tmp_path/'new',corpus_path=path)
