"""Synthetic fake sessions; actual evidence test reads identity metadata only."""
import builtins
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from isaforge import md5_offline_controller as w


@pytest.fixture(autouse=True)
def forbid_native_models_and_outcome_files(monkeypatch):
    def forbidden(*a,**k): raise AssertionError('Native/model/extraction entry point forbidden')
    monkeypatch.setattr(subprocess,'run',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
    original_import=builtins.__import__
    def guarded_import(name,*a,**k):
        assert not (name.startswith(('sklearn','xgboost','numpy')) or name in
            ('isaforge.codesign','isaforge.guarded_workload','isaforge.assembly_lowering'))
        return original_import(name,*a,**k)
    monkeypatch.setattr(builtins,'__import__',guarded_import)
    original_open=Path.open
    def guarded_open(path,*a,**k):
        assert not any(part in ('measurements','attempt-ledger','model','models') for part in path.parts)
        if path.resolve().is_relative_to(w.REPOSITORY/'results'):
            assert path.resolve().is_relative_to(w.REPOSITORY/w.PREREG)
            mode=a[0] if a else k.get('mode','r')
            assert all(flag not in mode for flag in ('w','a','x','+')), 'No target evidence writes'
        return original_open(path,*a,**k)
    monkeypatch.setattr(Path,'open',guarded_open)


@pytest.fixture
def pool(tmp_path):
    context='synthetic-archived';logical='synthetic-logical'
    rows=[];bindings=[]
    for i in range(12):
        path=tmp_path/f'source-{i}.S';path.write_text(f'# synthetic source {i}\n');hashed=w.sha(path)
        formula=f'add(in0,slli(in1,{i+1}))'
        rows.append(w.pack(dict(name=f'candidate_{i:02d}',formula=formula,archived_context_id=context,
            archived_candidate_id=w.digest([context,formula]),preparation_context_id=logical,
            preparation_candidate_id=w.digest([logical,formula]),assembly_path=str(path),assembly_sha256=hashed)))
        bindings.append((path,hashed))
    # Include a distinct synthetic source binding to test transaction-time rechecks.
    implementation=tmp_path/'fake-source.py';implementation.write_text('# synthetic frozen source\n')
    bindings.append((implementation,w.sha(implementation)))
    return w.PublicPool(tuple(rows),logical,context,('fixed_joint_lookahead','fixed_joint_myopic','merit'),tuple(bindings))


def make(pool,tmp_path,*,key=None,collection=False,responses=None,order=None,name='journal'):
    key=key or w.Session('fixed_joint_lookahead',0,3)
    responses=responses or {identity:w.FakeResponse() for identity in pool.ids}
    evaluator=w.FakeEvaluator(responses)
    controller=w.FakeOnlyController(pool,key,w.TemporaryJournal(tmp_path/name),
        w.FakeScorer(order or tuple(reversed(pool.ids))),evaluator,collection=collection)
    return controller,evaluator


def query(controller):
    proof=controller.next_proof()
    return controller.request(proof['candidate_id'],proof)


def test_actual_roster_identity_only_no_fake_evaluation_or_journal():
    pool=w.load_public_pool()
    assert len(pool.ids)==12 and pool.logical_namespace!=pool.archived_hardware_context
    assert pool.entry(pool.ids[0])['name']=='candidate_03'
    assert all(w.sha(path)==expected for path,expected in pool.bindings)


def test_bijective_remap_rejects_duplicates_unknown_and_changed_formula(pool):
    row=json.loads(pool.rows[0]);bad=list(pool.rows);bad[1]=bad[0]
    with pytest.raises(ValueError,match='Non-bijective'):replace(pool,rows=tuple(bad)).validate()
    row['formula']='add(in0,in1)';bad=list(pool.rows);bad[0]=w.pack(row)
    with pytest.raises(ValueError,match='Invalid identity'):replace(pool,rows=tuple(bad)).validate()
    row=json.loads(pool.rows[0]);row['assembly_sha256']='0'*64;bad[0]=w.pack(row)
    with pytest.raises(ValueError,match='Assembly identity'):replace(pool,rows=tuple(bad)).validate()
    with pytest.raises(ValueError,match='Unknown public'):pool.entry('unknown')


def test_direct_evaluator_bypass_and_wrong_evaluator_rejected(pool,tmp_path):
    controller,evaluator=make(pool,tmp_path)
    with pytest.raises(ValueError,match='Unreserved direct'):evaluator.evaluate(pool.ids[0],{})
    with pytest.raises(ValueError,match='No exact pending'):evaluator.evaluate(pool.ids[0],{},permit=controller._permit)
    with pytest.raises(ValueError,match='Only injected fake'):
        w.FakeOnlyController(pool,controller.session,w.TemporaryJournal(tmp_path/'other'),controller.scorer,lambda *a:None)
    assert evaluator.calls==[]


def test_exact_three_live_plus_nine_reference_order_and_no_reference_updates(pool,tmp_path):
    c,e=make(pool,tmp_path,collection=True)
    for _ in range(3):query(c)
    live=list(reversed(pool.ids))[:3]
    assert c.charged_ids==tuple(live) and (c.journal.path/'live-trace.json').exists()
    assert c.numeric_updates==3
    for _ in range(9):query(c)
    assert e.calls==live+[identity for identity in pool.ids if identity not in live]
    assert len(set(c.charged_ids))==12 and len(c.paid_prefix)==3 and c.numeric_updates==3
    assert c.events==['proof','reservation','fake-evaluation','terminal']*12
    with pytest.raises(ValueError,match='budget exhausted'):c.next_proof()


@pytest.mark.parametrize('field,value',[
    ('session_id','other'),('candidate_id','unknown'),('assembly_sha256','0'*64),
    ('attempted_ids_before',['unpaid']),('successful_paid_ids',['unpaid']),
    ('remaining_queries',99),('mode','oracle-reference'),('live_trace_sha256','forged')])
def test_mandatory_fields_cannot_be_bypassed_by_injected_checker(pool,tmp_path,monkeypatch,field,value):
    c,e=make(pool,tmp_path);proof=c.next_proof();proof[field]=value
    monkeypatch.setattr(c.scorer,'check',lambda *a:True)
    with pytest.raises(ValueError,match='Mandatory'):c.request(pool.ids[-1],proof)
    assert e.calls==[] and not list(c.journal.path.glob('*reservation*')) and c.stopped


def test_wrong_fake_acquisition_rejected_before_reservation(pool,tmp_path):
    c,e=make(pool,tmp_path);proof=c.next_proof();proof['acquisition']['fake_score']='tampered'
    with pytest.raises(ValueError,match='acquisition proof rejected'):c.request(proof['candidate_id'],proof)
    assert e.calls==[] and c.charged_ids==()


def test_permissive_fake_scorer_cannot_repeat_charged_identity(pool,tmp_path,monkeypatch):
    c,e=make(pool,tmp_path);query(c)
    monkeypatch.setattr(c.scorer,'acquire',lambda *a:dict(candidate_id=pool.ids[-1],fake_score='permissive'))
    monkeypatch.setattr(c.scorer,'check',lambda *a:True)
    with pytest.raises(ValueError,match='declared uncharged'):c.next_proof()
    assert len(e.calls)==1 and c.charged_ids==(pool.ids[-1],) and c.stopped


def test_sentinel_store_and_policy_seed_horizon_prefix_isolation(pool,tmp_path):
    c,e=make(pool,tmp_path,responses={pool.ids[-1]:w.FakeResponse()},name='a')
    query(c)  # Missing every other response: no store-wide enumeration/read occurs.
    assert e.calls==[pool.ids[-1]] and len(c.paid_prefix)==1
    sessions=[w.Session('fixed_joint_myopic',0,3),w.Session('fixed_joint_lookahead',1,3),
              w.Session('fixed_joint_lookahead',0,1),w.Session('fixed_joint_lookahead',0,2)]
    for i,key in enumerate(sessions):
        other,ev=make(pool,tmp_path,key=key,name=f'isolated-{i}')
        assert other.paid_prefix==[] and other.numeric_updates==0
        leaked=c.next_proof()
        with pytest.raises(ValueError,match='Mandatory'):other.request(leaked['candidate_id'],leaked)
        assert ev.calls==[]


def test_known_failure_consumes_slot_without_numeric_update(pool,tmp_path):
    replies={i:w.FakeResponse() for i in pool.ids}
    replies[pool.ids[-1]]=w.FakeResponse('known_failure',known_failure_evidence='synthetic-classified-invalid')
    c,e=make(pool,tmp_path,responses=replies);query(c)
    assert len(c.charged_ids)==1 and c.numeric_updates==0 and len(c.paid_prefix)==1
    proof=c.next_proof();assert proof['index']==1 and proof['remaining_queries']==2
    assert proof['successful_paid_ids']==[]
    query(c);assert c.numeric_updates==1 and e.calls==list(reversed(pool.ids))[:2]
    with pytest.raises(ValueError):c.request(pool.ids[-1],proof)
    assert len(e.calls)==2


@pytest.mark.parametrize('status,cost,evidence',[
    ('infrastructure_unknown',True,''),('interrupted',True,''),('ambiguous',True,''),
    ('failed',True,''),('known_failure',True,''),('known_failure',False,'synthetic-invalid')])
def test_unknown_or_incomplete_failure_stops_preserves_charge_and_cannot_retry(pool,tmp_path,status,cost,evidence):
    replies={pool.ids[-1]:w.FakeResponse(status,known_failure_evidence=evidence,cost_complete=cost)}
    c,e=make(pool,tmp_path,responses=replies)
    with pytest.raises(ValueError,match='preserve reservation'):query(c)
    assert c.stopped and c.charged_ids==(pool.ids[-1],) and c.numeric_updates==0
    assert (c.journal.path/'00-reservation.json').exists() and not (c.journal.path/'00-terminal.json').exists()
    with pytest.raises(ValueError,match='Stopped'):c.next_proof()
    with pytest.raises(ValueError,match='fresh system-temporary'):w.TemporaryJournal(c.journal.path)
    assert len(e.calls)==1


def test_interruption_during_terminal_seal_leaves_reserved_attempt_stopped(pool,tmp_path,monkeypatch):
    c,e=make(pool,tmp_path);real=c.journal.seal
    def interrupted(name,value):
        if name.endswith('-terminal.json'):raise KeyboardInterrupt('synthetic interruption')
        return real(name,value)
    monkeypatch.setattr(c.journal,'seal',interrupted)
    with pytest.raises(KeyboardInterrupt):query(c)
    assert c.stopped and len(c.charged_ids)==1 and c.paid_prefix==[]
    with pytest.raises(ValueError,match='Stopped'):c.next_proof()
    assert len(e.calls)==1


@pytest.mark.parametrize('target',('journal','source','assembly'))
def test_revalidates_seals_and_sources_at_every_transaction(pool,tmp_path,target):
    c,e=make(pool,tmp_path);query(c)
    if target=='journal':path=c.journal.path/'00-terminal.json'
    elif target=='source':path=pool.bindings[-1][0]
    else:path=pool.bindings[0][0]
    original=path.read_bytes();path.write_text('tampered')
    with pytest.raises(ValueError,match='changed'):c.next_proof()
    assert c.stopped and len(e.calls)==1
    path.write_bytes(original)
    with pytest.raises(ValueError,match='Stopped'):c.next_proof()


def test_finite_planned_b1_b2_remain_distinct_from_b3_prefix(pool,tmp_path):
    b1,_=make(pool,tmp_path,key=w.Session('fixed_joint_lookahead',0,1),name='b1')
    b2,_=make(pool,tmp_path,key=w.Session('fixed_joint_lookahead',0,2),name='b2')
    b3,_=make(pool,tmp_path,name='b3')
    query(b1);query(b2);query(b2);query(b3)
    assert b1.prefix_endpoint(1)['endpoint_kind']=='planned'
    assert b2.prefix_endpoint(2)['planned_horizon']==2
    assert b3.prefix_endpoint(1)['endpoint_kind']=='b3-prefix'
    assert len({b1._session_id,b2._session_id,b3._session_id})==3
    with pytest.raises(ValueError,match='finite horizons'):
        w.Session('merit',0,1,'b3-prefix').validate(pool)


def test_session_scope_cannot_be_changed_after_binding(pool,tmp_path):
    c,e=make(pool,tmp_path);c.session=w.Session('fixed_joint_lookahead',0,1)
    with pytest.raises(ValueError,match='Immutable session scope'):c.next_proof()
    assert c.stopped and e.calls==[]


def test_fake_journal_cannot_write_repository_or_target_evidence():
    with pytest.raises(ValueError,match='system-temporary'):
        w.TemporaryJournal(w.REPOSITORY/w.PREREG/'forbidden-fake-journal')
