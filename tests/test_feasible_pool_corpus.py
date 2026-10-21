"""Dataset contract tests; remapped fixtures are not new measurement evidence."""
import copy
from pathlib import Path
import shutil

import pytest
from isaforge import codesign as c
from scripts import export_feasible_pool_corpus as x

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def case(tmp_path,monkeypatch):
    previous=tmp_path/'previous'
    shutil.copytree(ROOT/'results/2026-10-21-six-workload-corpus',previous)
    old=c.unseal(previous/'corpus.json')
    public=c.unseal(ROOT/'results/2026-10-21-feasible-benefit-preregistration/inputs/public.json')
    old_sha=[row for row in old['rows'] if row['workload_group']=='embench-nettle-sha256']
    # Deliberately synthetic pairing tests schema/identity handling only.
    outcomes=[dict(copy.deepcopy(row),**candidate) for row,candidate in zip(old_sha,public)]
    audit=dict(outcomes=outcomes,public=public,attempt_collection_complete=True,
        candidate_wall_seconds_complete=True,unattempted=[],charged_candidate_attempts=6,
        candidate_wall_seconds=sum(row['measurement_seconds'] for row in outcomes),
        context_id=public[0]['benchmark'].split(':',1)[1])
    campaign=tmp_path/'campaign';campaign.mkdir()
    c.seal(campaign/'outcomes.json',outcomes);c.seal(campaign/'audit.json',audit)
    c.seal(campaign/'provenance.json',dict(scope='unit fixture only'))
    fixture_root=tmp_path/'fixture-root'
    context_path=Path('results/2026-10-21-feasible-benefit-preregistration/baseline/context.json')
    c.seal(fixture_root/context_path,c.unseal(ROOT/context_path))
    monkeypatch.setattr(x,'ROOT',fixture_root)
    return previous,campaign,old,audit


def test_new_candidate_pool_does_not_become_seventh_workload(case,tmp_path):
    previous,campaign,old,audit=case
    result=x.export(previous,campaign,tmp_path/'corpus')
    assert result['rows'][:33]==old['rows']
    assert result['successful_labels']==39
    assert len(result['contexts'])==7
    assert len(result['independent_workload_groups'])==6
    assert sum(row['workload_group']=='embench-nettle-sha256' for row in result['rows'])==12
    assert result['total_candidate_attempts']==42
    assert result['failed_attempts']==old['failed_attempts']
    assert result['total_candidate_attempt_wall_seconds']==old['total_candidate_attempt_wall_seconds']+audit['candidate_wall_seconds']


def test_unknown_failed_attempt_is_charged_without_performance_label(case,tmp_path):
    previous,campaign,old,audit=case
    failed=dict(audit['public'][0],status='failed',error='infrastructure interrupted fixture',
        measurement_seconds=2.0,failure_class='infrastructure_unknown',reference_censored=True)
    audit['outcomes'][0]=failed
    audit['candidate_wall_seconds']=sum(row['measurement_seconds'] for row in audit['outcomes'])
    c.seal(campaign/'outcomes.json',audit['outcomes']);c.seal(campaign/'audit.json',audit)
    result=x.export(previous,campaign,tmp_path/'corpus')
    assert result['successful_labels']==38 and len(result['failed_attempts'])==4
    assert result['total_candidate_attempts']==42
    item=result['failed_attempts'][-1]
    assert item['correctness_verified'] is None
    assert not {'speedup','candidate_cycles','area_delta_lut4'} & set(item)
    assert failed['candidate_id'] in result['reference_censored_candidates']
    assert len(result['reference_censored_candidates'])==2  # Includes original UD unknown.


def test_outcome_audit_mismatch_cannot_enter_corpus(case,tmp_path):
    previous,campaign,_,audit=case
    altered=copy.deepcopy(audit['outcomes']);altered[0]['measurement_seconds']+=1
    c.seal(campaign/'outcomes.json',altered)
    with pytest.raises(ValueError,match='Audited pool outcomes differ'):
        x.export(previous,campaign,tmp_path/'corpus')
    assert not (tmp_path/'corpus').exists()


def test_historical_corpus_tampering_is_rejected(case,tmp_path):
    previous,campaign,old,_=case
    old['rows'][0]['speedup']+=.1
    c.seal(previous/'corpus.json',old)
    with pytest.raises(ValueError,match='Historical corpus changed'):
        x.export(previous,campaign,tmp_path/'corpus')
