"""Synthetic bridge contracts only; no target evidence/model execution."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from isaforge import md5_protocol_bridge as b
from scripts import prepare_md5_evaluation_protocol as entry
from test_budgeted_selection import public as synthetic_public


@pytest.fixture(autouse=True)
def no_native_no_outcomes_no_model_artifacts(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('External command forbidden')
    monkeypatch.setattr(subprocess,'run',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
    original=Path.open
    def guarded(path,*a,**k):
        assert not path.resolve().is_relative_to(b.ROOT/'results'),'No real target/history/model artifact access in synthetic tests'
        assert not path.resolve().is_relative_to(b.ROOT/'generated'),'No native artifact access in synthetic tests'
        return original(path,*a,**k)
    monkeypatch.setattr(Path,'open',guarded)


@pytest.fixture
def declaration():
    contract={'preparation_context_id':'prep-synthetic','identity_basis':{'archived_hardware_context_id':'archived-synthetic'}}
    plan=dict(context_id='archived-synthetic',memory_partition={'program_limit':6400,'stack_floor':6528},
        configuration={'ram_bytes':8192},compiler_flags=['-march=rv32i_zicsr','-mabi=ilp32','-Os'],
        inputs={'soc_top.v':'synthetic-hardware-hash'},source_bindings={'synthetic-source.py':'synthetic-source-hash'})
    context=b.declared_context(contract,plan,'synthetic-model-manifest',{'synthetic-bridge.py':'code-sha'},
        archived_plan_file_sha256='synthetic-plan-file-sha')
    rows=[dict(name=f'candidate_{i:02d}',formula=f'add(in0,slli(in1,{i+1}))',
        archived_context_id='archived-synthetic',preparation_context_id='prep-synthetic',
        archived_candidate_id=b.digest(['archived-synthetic',f'add(in0,slli(in1,{i+1}))']),
        preparation_candidate_id=b.digest(['prep-synthetic',f'add(in0,slli(in1,{i+1}))']),
        assembly_sha256=f'synthetic-assembly-{i}') for i in range(12)]
    return context,rows,plan,contract


def test_declared_namespace_is_bijective_and_never_runtime_authority(declaration):
    context,rows,_,_=declaration;mapping=b.native_remap(rows,context)
    assert len(mapping)==12 and context['authenticated_native_plan'] is False
    assert context['declared_native_context_id'] not in ('prep-synthetic','archived-synthetic')
    assert context['archived_plan_file_sha256']=='synthetic-plan-file-sha'
    assert all(r['declared_native_candidate_id']==b.digest([context['declared_native_context_id'],r['formula']]) for r in mapping)
    with pytest.raises(b.DispatchDisabled):b.DisabledBridge().evaluate(mapping[0],enable=True,release='anything')


@pytest.mark.parametrize('key',('name','formula','preparation_candidate_id','archived_candidate_id'))
def test_duplicate_mapping_rejected(declaration,key):
    context,rows,_,_=declaration;rows[1][key]=rows[0][key]
    with pytest.raises(ValueError,match='Non-bijective|identity digest'):b.native_remap(rows,context)


def test_archived_partition_and_context_cannot_be_rescued(declaration):
    _,_,plan,contract=declaration
    for change in ({'stack_floor':6500},{'program_limit':6500}):
        altered=copy.deepcopy(plan);altered['memory_partition'].update(change)
        with pytest.raises(ValueError,match='6400/6528'):
            b.declared_context(contract,altered,'models',{},archived_plan_file_sha256='file-sha')
    plan['context_id']='different'
    with pytest.raises(ValueError,match='Archived hardware'):
        b.declared_context(contract,plan,'models',{},archived_plan_file_sha256='file-sha')


def session(policy='hybrid_gp_adapt',seed=0,horizon=3):
    return b.make_session(policy,seed,horizon)


@pytest.fixture
def mapping(declaration):
    context,rows,_,_=declaration
    return b.native_remap(rows,context)


def paid(key,row):
    public=synthetic_public(row['preparation_candidate_id'],row['formula'],'synthetic:ctx')
    return dict(session=key,candidate_id=row['preparation_candidate_id'],status='verified',synthetic_fixture=True,
        preparation_context_id=row['preparation_context_id'],assembly_sha256=row['assembly_sha256'],
        outcome=dict(public,status='success',baseline_cycles=1000,candidate_cycles=960,speedup=1000/960,
            area_delta_lut4=20,routed_fmax_min_mhz=60.,device_fits=True,correctness_verified=True,measurement_seconds=2.))


class FakeModel:
    fake_only=True
    def __init__(self):self.received=None
    def fit(self,rows):self.received=rows;return self


class FakeFactory:
    fake_only=True
    def __call__(self):return FakeModel()


class FakeJoint:
    def __init__(self,public,history):
        self.paid=[];self.fantasies=[];self.public=copy.deepcopy(public);self.history=copy.deepcopy(history)
        self.device_alpha=1;self.device_beta=1
    @property
    def candidate_ids(self):return tuple(r['candidate_id'] for r in self.public)
    @property
    def observed_ids(self):return tuple(self.paid)
    @property
    def conditioned_ids(self):return tuple(self.paid+self.fantasies)
    def snapshot(self):
        ids=[r['candidate_id'] for r in self.history]
        return dict(candidate_ids=list(self.candidate_ids),public_pool_sha256=b.digest(self.public),
            paid_ids=list(self.paid),fantasy_ids=list(self.fantasies),hypothetical=bool(self.fantasies),
            initial_training_ids=ids,initial_snapshot=dict(training_ids=ids,training_rows_sha256=b.digest(self.history)))
    def clone(self):return copy.deepcopy(self)


class FakeConditioner:
    fake_only=True
    def __call__(self,state,outcome,queried_id):
        assert queried_id==outcome['candidate_id'];state.paid.append(queried_id)
        if 'device_fits' in outcome:
            if outcome['device_fits']:state.device_alpha+=1
            else:state.device_beta+=1
        return state


def joint_public(mapping):
    # Actual model-public projection has no context_id or assembly_sha256.
    return [synthetic_public(r['preparation_candidate_id'],r['formula'],'synthetic:ctx') for r in mapping]


@pytest.mark.parametrize('policy',tuple(b.DYNAMIC_FACTORIES))
def test_dynamic_factory_receives_exact_history_plus_own_verified_prefix(policy,mapping):
    key=session(policy);record=paid(key,mapping[1]);ids=[r['preparation_candidate_id'] for r in mapping]
    factories={name:FakeFactory() for name in b.DYNAMIC_FACTORIES.values()}
    state,receipt=b.reconstruct_policy_state(key,None,[{'historical':'synthetic'}],ids[:2],[record],mapping=mapping,fake_factories=factories)
    assert state.received==[{'historical':'synthetic'},record['outcome']]
    assert receipt['successful_paid_ids']==ids[1:2] and receipt['attempted_ids']==ids[:2]
    assert receipt['factory']==b.DYNAMIC_FACTORIES[policy] and receipt['real_model_fits']==0


def test_fixed_joint_conditions_a_clone_without_dynamic_refit(mapping):
    key=session('fixed_joint_lookahead');public=joint_public(mapping);initial=FakeJoint(public,[])
    record=paid(key,mapping[0]);candidate_id=record['candidate_id']
    state,receipt=b.reconstruct_policy_state(key,initial,[],[candidate_id],[record],mapping=mapping,
        initial_public=public,fake_conditioner=FakeConditioner())
    assert all('context_id' not in r and 'assembly_sha256' not in r for r in public)
    assert initial.paid==[] and state.paid==[candidate_id] and receipt['conditioner']==b.FIXED_CONDITIONER


@pytest.mark.parametrize('defect',('paid','fantasy','foreign','pool','history','missing_public'))
def test_fixed_joint_rejects_nonpristine_or_mismatched_initial_state(mapping,defect):
    public=joint_public(mapping);history=[dict(candidate_id='historical-synthetic')]
    initial=FakeJoint(public,history)
    if defect=='paid':initial.paid=[public[0]['candidate_id']]
    elif defect=='fantasy':initial.fantasies=[public[0]['candidate_id']]
    elif defect=='foreign':initial.paid=['FOREIGN_OR_FANTASY_ID']
    elif defect=='pool':initial.public[0]['latency_features']['estimated_speedup']=2.
    elif defect=='history':initial.history=[dict(candidate_id='different-history')]
    with pytest.raises(ValueError,match='pristine|pool differs|history differs|Explicit initial public'):
        b.reconstruct_policy_state(session('fixed_joint_lookahead'),initial,history,[],[],mapping=mapping,
            initial_public=None if defect=='missing_public' else public)
    assert initial.paid==(['FOREIGN_OR_FANTASY_ID'] if defect=='foreign' else
        [public[0]['candidate_id']] if defect=='paid' else [])


@pytest.mark.parametrize('other', [session(seed=1),session(horizon=1),session('hybrid_gp_adapt_count')])
def test_policies_seeds_and_horizons_cannot_inherit_another_prefix(other,mapping):
    with pytest.raises(ValueError,match='Foreign/unpaid|Unknown/unbound'):
        b.reconstruct_policy_state(other,None,[],[mapping[0]['preparation_candidate_id']],[paid(session(),mapping[0])],mapping=mapping)


def test_no_actual_paid_updates_and_zero_paid_does_not_fit(mapping):
    key=session();record=paid(key,mapping[0]);record['synthetic_fixture']=False
    with pytest.raises(ValueError,match='Real paid reconstruction'):
        b.reconstruct_policy_state(key,None,[],[record['candidate_id']],[record],mapping=mapping,fake_factories={})
    state,receipt=b.reconstruct_policy_state(key,{'initial':'immutable'},[],[],[],mapping=mapping)
    assert state=={'initial':'immutable'} and receipt['real_model_fits']==0
    assert receipt['successful_paid_ids']==[]



def test_model_manifest_mismatch_stops_before_unpickling(monkeypatch):
    monkeypatch.setattr(b.identity,'load_public_pool',lambda *a:None)
    monkeypatch.setattr(b,'sha',lambda *a:'changed')
    with pytest.raises(ValueError,match='model manifest changed'):b.authenticate_model_metadata()


def test_fit_and_external_command_tripwires():
    from isaforge.model import SpeedupPredictor
    with b.forbid_fits_and_commands():
        with pytest.raises(AssertionError,match='No fitting'):SpeedupPredictor().fit([])
        with pytest.raises(AssertionError,match='No fitting'):subprocess.run(['never-executed'])


def test_output_gate_precedes_model_execution(tmp_path,monkeypatch):
    monkeypatch.setattr(entry,'authenticate_zero_paid_models',lambda *a:pytest.fail('not called'),raising=False)
    with pytest.raises(ValueError,match='Fresh direct'):entry.build(tmp_path/'outside')


@pytest.fixture
def transaction(declaration,mapping):
    context=declaration[0];key=session('fixed_joint_lookahead');row=mapping[0]
    proof=dict(event=dict(candidate_id=row['preparation_candidate_id'],policy=key['policy'],planned_budget=3,
        remaining_queries=3,charged_before_query=0,attempted_ids_before_query=[],paid_target_ids_before_query=[]),
        successful_paid_ids=[],synthetic_fixture=True)
    request=dict(logical_candidate_id=row['preparation_candidate_id'],native_candidate_id=row['declared_native_candidate_id'],
        native_context_id=context['declared_native_context_id'],formula=row['formula'],assembly_sha256=row['assembly_sha256'],
        model_manifest_sha256=context['model_manifest_sha256'],session_id=key['session_id'],mode='adaptive',
        attempted_ids_before=[],successful_paid_ids=[],proof_sha256=b.digest(proof),live_trace_sha256=None)
    reservation=dict(**request,charged_slot=1,chosen_before_reservation=True)
    return context,key,proof,request,reservation


def test_evaluator_bound_proof_native_mapping_and_reservation(transaction,mapping,tmp_path):
    context,key,proof,request,reservation=transaction
    gate=b.DisabledBridge(context,mapping,proof)
    receipt=gate.validate_for_review(key,[],[],request,reservation,proof)
    assert receipt['native_candidate_id']==mapping[0]['declared_native_candidate_id']
    assert receipt['validated_contract_only'] is True
    # Reuse the existing synthetic append-only mechanism; no evaluator is called.
    journal=b.identity.TemporaryJournal(tmp_path/'reservation-order')
    journal.seal('proof.json',proof);journal.seal('reservation.json',reservation)
    assert list(journal._hashes)==['proof.json','reservation.json']
    with pytest.raises(b.DispatchDisabled):gate.evaluate(request,proof,reservation)
    assert len(list(journal.path.iterdir()))==2


@pytest.mark.parametrize('field',('formula','native_candidate_id','assembly_sha256','model_manifest_sha256','session_id'))
def test_transaction_tampering_fails_before_any_evaluator(transaction,mapping,field):
    context,key,proof,request,reservation=transaction;request[field]='tampered'
    with pytest.raises(ValueError,match='request/reservation'):
        b.DisabledBridge(context,mapping,proof).validate_for_review(key,[],[],request,reservation,proof)


def test_reference_phase_fails_closed_even_with_minimal_forged_trace(transaction,mapping):
    context,key,proof,request,reservation=transaction
    attempted=[r['preparation_candidate_id'] for r in mapping[:3]]
    request['logical_candidate_id']=mapping[3]['preparation_candidate_id']
    with pytest.raises(b.DispatchDisabled,match='Reference-phase'):
        b.DisabledBridge(context,mapping,proof).validate_for_review(key,attempted,[],request,reservation,None,
            live_trace={'complete':True,'attempted_ids':attempted,'remaining_outcomes_exist':False})


@pytest.mark.parametrize('include_verified',(False,True))
def test_nonzero_paid_transaction_cannot_authorize_next_slot(transaction,mapping,include_verified):
    context,key,proof,request,reservation=transaction;first=mapping[0]['preparation_candidate_id']
    verified=[paid(key,mapping[0])] if include_verified else []
    request['logical_candidate_id']=mapping[1]['preparation_candidate_id']
    with pytest.raises(b.DispatchDisabled,match='Zero-paid.*terminal accounting'):
        b.DisabledBridge(context,mapping,proof).validate_for_review(key,[first],verified,request,reservation,proof)


@pytest.mark.parametrize('change',('unknown_policy','bad_session','foreign_payload','duplicate','over_budget'))
def test_reconstruction_rejects_invalid_sessions_and_smuggled_observations(mapping,change):
    key=session();wrapped=paid(key,mapping[0]);ids=[wrapped['candidate_id']]
    if change=='unknown_policy':key=b.make_session('unknown',0,3)
    elif change=='bad_session':key['session_id']='forged'
    elif change=='foreign_payload':wrapped['outcome']['candidate_id']=mapping[1]['preparation_candidate_id']
    elif change=='duplicate':ids*=2
    else:ids=[r['preparation_candidate_id'] for r in mapping[:4]]
    with pytest.raises(ValueError):
        b.reconstruct_policy_state(key,None,[],ids,[wrapped],mapping=mapping)


def hardware():
    routes=[dict(seed=i,fmax_mhz=60.,device_fits=True,internal_timing_pass=True) for i in (1,2,3)]
    return dict(synthetic_fixture=True,status='verified',failure_class=None,
        baseline=dict(cycles=200,lut4=100,integrated_soc=True,preserved=True,stack_negative_control=True,
            guard_negative_control=True,routes=copy.deepcopy(routes)),
        candidate=dict(cycles=100,lut4=120,integrated_soc=True),speedup=2.,added_lut4=20,
        memory=dict(ram_bytes=8192,program_limit=6400,stack_floor=6528,program_end=6000,stack_min=7000,
            guard_violations=0,stack_violations=0),
        controls={name:True for name in ('recorded_input_self_check','integer_oracle','pcpi_handshake',
            'stock_on_extension','custom_on_unextended_traps','custom_execution_count_matches')},
        routes=routes,min_fmax_mhz=60.,durations=dict(native_command_seconds=1.,attempt_seconds=2.,cli_seconds=3.,observer_seconds=4.))


def test_synthetic_sealed_contract_is_not_raw_native_authentication():
    receipt=b.validate_sealed_synthetic_hardware(hardware())
    assert receipt['sealed_record_contract_valid'] and receipt['raw_native_evidence_authenticated'] is False


@pytest.mark.parametrize('defect',('missing_pcpi','wrong_seed','device_flag','timing_flag','baseline_device',
                                  'baseline_timing','zero_clock','min_clock','area','speedup','duration',
                                  'infinite_clock','infinite_duration','bool_cycles','negative_end','failed'))
def test_sealed_contract_rejects_incomplete_inconsistent_or_unknown_values(defect):
    raw=hardware()
    if defect=='missing_pcpi':raw['controls']['pcpi_handshake']=False
    elif defect=='wrong_seed':raw['routes'][0]['seed']=2
    elif defect=='device_flag':raw['routes'][0]['device_fits']=0
    elif defect=='timing_flag':raw['routes'][0]['internal_timing_pass']=1
    elif defect=='baseline_device':raw['baseline']['routes'][0]['device_fits']=False
    elif defect=='baseline_timing':raw['baseline']['routes'][0].update(fmax_mhz=9.,internal_timing_pass=False)
    elif defect=='zero_clock':raw['routes'][0]['fmax_mhz']=0.
    elif defect=='min_clock':raw['min_fmax_mhz']=61.
    elif defect=='area':raw['added_lut4']=21
    elif defect=='speedup':raw['speedup']=3.
    elif defect=='duration':raw['durations']['attempt_seconds']=10.
    elif defect=='infinite_clock':raw['routes'][0]['fmax_mhz']=float('inf')
    elif defect=='infinite_duration':raw['durations']={k:float('inf') for k in raw['durations']}
    elif defect=='bool_cycles':raw['candidate']['cycles']=True
    elif defect=='negative_end':raw['memory']['program_end']=-1
    else:raw['status']='known_failure'
    with pytest.raises(ValueError):b.validate_sealed_synthetic_hardware(raw)


@pytest.mark.parametrize('infeasibility',('area','timing','internal_timing','device'))
def test_complete_verified_infeasible_measurements_reach_paid_conditioner(mapping,infeasibility):
    raw=hardware()
    if infeasibility=='area':raw['candidate']['lut4']=165;raw['added_lut4']=65
    elif infeasibility=='timing':
        raw['routes'][0].update(fmax_mhz=9.,internal_timing_pass=False);raw['min_fmax_mhz']=9.
    elif infeasibility=='internal_timing':
        for route in raw['routes']:route.update(fmax_mhz=9.,internal_timing_pass=False)
        raw['min_fmax_mhz']=9.
    else:raw['routes'][0]['device_fits']=False
    before=copy.deepcopy(raw);receipt=b.validate_sealed_synthetic_hardware(raw)
    assert receipt['sealed_record_contract_valid'] and receipt['feasible_at_cap64'] is False and raw==before
    key=session('fixed_joint_lookahead');record=paid(key,mapping[0]);public=joint_public(mapping)
    record['outcome'].update(routed_fmax_min_mhz=raw['min_fmax_mhz'],device_fits=receipt['device_fits'],
        area_delta_lut4=raw['added_lut4'])
    initial=FakeJoint(public,[])
    state,update=b.reconstruct_policy_state(key,initial,[],[record['candidate_id']],[record],mapping=mapping,
        initial_public=public,fake_conditioner=FakeConditioner())
    assert state.paid==[record['candidate_id']] and update['successful_paid_ids']==state.paid
    assert state.device_beta==(2 if infeasibility=='device' else 1)
    assert state.device_alpha==(1 if infeasibility=='device' else 2)
    assert initial.paid==[] and initial.device_beta==1


@pytest.mark.parametrize('table',('candidate','baseline'))
@pytest.mark.parametrize('fmax,flag',((60.,False),(9.,True)))
def test_exact12_contract_rejects_contradictory_route_timing_flags(table,fmax,flag):
    raw=hardware();routes=raw['routes'] if table=='candidate' else raw['baseline']['routes']
    routes[0].update(fmax_mhz=fmax,internal_timing_pass=flag)
    if table=='candidate':raw['min_fmax_mhz']=min(r['fmax_mhz'] for r in routes)
    with pytest.raises(ValueError,match='exact12 route timing flag/Fmax mismatch'):
        b.validate_sealed_synthetic_hardware(raw)


def test_exact12_equality_is_feasible_for_candidate_and_baseline():
    raw=hardware()
    for table in (raw['routes'],raw['baseline']['routes']):
        for route in table:route.update(fmax_mhz=12.,internal_timing_pass=True)
    raw['min_fmax_mhz']=12.
    receipt=b.validate_sealed_synthetic_hardware(raw)
    assert receipt['sealed_record_contract_valid'] and receipt['timing_feasible'] and receipt['feasible_at_cap64']


def test_preserved_success_projection_keeps_raw_ids_bytes_and_costs(tmp_path,transaction,mapping):
    context,key,proof,request,reservation=transaction;row=mapping[0]
    receipt=b.DisabledBridge(context,mapping,proof).validate_for_review(key,[],[],request,reservation,proof)
    raw=hardware();raw.update(candidate_id=row['declared_native_candidate_id'],context_id=row['declared_native_context_id'],
        formula=row['formula'],assembly_sha256=row['assembly_sha256'],transaction=receipt)
    record=tmp_path/'original-record.json';ledger=tmp_path/'original-ledger.json'
    record.write_text(json.dumps(raw,indent=2));record_bytes=record.read_bytes();record_sha=b.sha(record)
    native_ledger=dict(synthetic_fixture=True,status='success',candidate_id=raw['candidate_id'],context_id=raw['context_id'],
        formula=raw['formula'],assembly_sha256=raw['assembly_sha256'],transaction=receipt,
        durations=raw['durations'],original_record_sha256=record_sha)
    ledger.write_text(json.dumps(native_ledger));ledger_bytes=ledger.read_bytes();ledger_sha=b.sha(ledger)
    logical=b.project_preserved_synthetic_evidence(record,record_sha,row,ledger_path=ledger,ledger_sha256=ledger_sha,
        validated_transaction=receipt)
    assert record.read_bytes()==record_bytes and ledger.read_bytes()==ledger_bytes
    assert logical['candidate_id']==row['preparation_candidate_id']
    assert logical['native_evidence']['original_native_candidate_id']==raw['candidate_id']
    assert logical['native_evidence']['original_durations']==raw['durations']


@pytest.mark.parametrize('defect',('other_candidate','wrong_logical','raw_logical_only','missing_logical'))
def test_projection_rejects_other_transaction_with_same_preserved_record_and_mapping(
        tmp_path,transaction,mapping,defect):
    context,key,proof,request,reservation=transaction
    receipt=b.DisabledBridge(context,mapping,proof).validate_for_review(key,[],[],request,reservation,proof)
    row=mapping[1] if defect=='other_candidate' else mapping[0]
    if defect=='wrong_logical':receipt['logical_candidate_id']=mapping[1]['preparation_candidate_id']
    if defect=='missing_logical':receipt.pop('logical_candidate_id')
    preserved_transaction=copy.deepcopy(receipt)
    if defect=='raw_logical_only':preserved_transaction['logical_candidate_id']=mapping[1]['preparation_candidate_id']
    raw=hardware();raw.update(candidate_id=row['declared_native_candidate_id'],context_id=row['declared_native_context_id'],
        formula=row['formula'],assembly_sha256=row['assembly_sha256'],transaction=preserved_transaction)
    record=tmp_path/'record-b.json';ledger=tmp_path/'ledger-b.json'
    record.write_text(json.dumps(raw));record_bytes=record.read_bytes();record_sha=b.sha(record)
    native_ledger=dict(synthetic_fixture=True,status='success',candidate_id=raw['candidate_id'],context_id=raw['context_id'],
        formula=raw['formula'],assembly_sha256=raw['assembly_sha256'],transaction=preserved_transaction,
        durations=raw['durations'],original_record_sha256=record_sha)
    ledger.write_text(json.dumps(native_ledger));ledger_bytes=ledger.read_bytes();ledger_sha=b.sha(ledger)
    with pytest.raises(ValueError,match='Transaction differs from same original|Original proof/reservation'):
        b.project_preserved_synthetic_evidence(record,record_sha,row,ledger_path=ledger,ledger_sha256=ledger_sha,
            validated_transaction=receipt)
    assert record.read_bytes()==record_bytes and ledger.read_bytes()==ledger_bytes


def test_incomplete_bridge_cannot_seal_any_protocol_artifact(monkeypatch):
    monkeypatch.setattr(b,'ENGINEERING_GAPS',())  # Closing pure contracts cannot enable the builder.
    monkeypatch.setattr(b,'authenticate_model_metadata',lambda:pytest.fail('No model execution before NO-GO gate'))
    with pytest.raises(b.ProtocolIncomplete,match='Incomplete bridge'):
        entry.build(b.ROOT/b.PREREG/'evaluation-protocol-v1')


class SyntheticEnvelopes:
    """Temporary in-memory byte fixtures; no real models, files or outcomes."""
    def __init__(self,context,mapping):
        self.context=context;self.mapping=mapping;self.key=session('fixed_joint_lookahead')
        self.public=[synthetic_public(r['preparation_candidate_id'],r['formula'],'synthetic:ctx',baseline=200) for r in mapping]
        self.store={};self.envelopes=[];self.trace=None
        def state(rows):return b.digest(dict(initial='synthetic-state',paid=rows))
        state.fake_only=True;self.state=state;self.initial=state([])
        def proof(attempted,rows):
            chosen=next(r for r in mapping if r['preparation_candidate_id'] not in attempted)
            return dict(synthetic_fixture=True,event=dict(candidate_id=chosen['preparation_candidate_id'],
                policy=self.key['policy'],planned_budget=3,remaining_queries=3-len(attempted),
                charged_before_query=len(attempted),attempted_ids_before_query=list(attempted),
                paid_target_ids_before_query=[r['candidate_id'] for r in rows]),
                successful_paid_ids=[r['candidate_id'] for r in rows],
                posterior_snapshot=dict(posterior_state_sha256=state(rows)))
        proof.fake_only=True;self.proof=proof
    def put(self,value):
        raw=value if type(value) is bytes else json.dumps(value,sort_keys=True).encode()
        key=hashlib.sha256(raw).hexdigest();self.store[key]=raw;return key
    def inputs(self):
        return dict(public=self.public,store=self.store,envelope_hashes=self.envelopes,
            initial_state_digest=self.initial,fake_proof=self.proof,fake_state=self.state,live_trace_hash=self.trace)
    def review(self):return b.review_attempt_envelopes(self.context,self.mapping,self.key,**self.inputs())
    def append(self,kind='verified',*,change_raw=None,cost_values=None,bounds=None,opaque_raw=None):
        before=self.review();index=len(self.envelopes)
        row=next(r for r in self.mapping if r['preparation_candidate_id'] not in before['charged_ids'])
        proof=self.proof(before['charged_ids'],before['live_model_rows']) if index<3 else None
        reservation=dict(synthetic_fixture=True,case=before['case'],slot=index+1,
            logical_candidate_id=row['preparation_candidate_id'],native_candidate_id=row['declared_native_candidate_id'],
            formula=row['formula'],assembly_sha256=row['assembly_sha256'],
            prior_envelope_byte_sha256=list(self.envelopes),live_model_rows_codesign_digest=b.digest(before['live_model_rows']),
            mode='live' if index<3 else 'reference',acquisition_proof_byte_sha256=self.put(proof) if proof else None,
            acquisition_proof_codesign_digest=b.digest(proof) if proof else None,
            live_trace_byte_sha256=self.trace if index>=3 else None)
        reservation_hash=self.put(reservation)
        terminal_hash=None
        if kind!='pending':
            values=hardware()['durations'] if cost_values is None else cost_values
            cost=dict(synthetic_fixture=True,reservation_byte_sha256=reservation_hash,values=values,
                known_lower_bounds=copy.deepcopy(values) if bounds is None else bounds)
            if kind=='verified':raw=hardware()
            else:raw=dict(synthetic_fixture=True,words=[0x49534146,0,0,0,0],markers=2,
                partial_report_bits=0,fault=0,trapped=False,stack_violations=0)
            raw.update(candidate_id=row['declared_native_candidate_id'],context_id=row['declared_native_context_id'],
                formula=row['formula'],assembly_sha256=row['assembly_sha256'],reservation_byte_sha256=reservation_hash)
            if change_raw:change_raw(raw)
            raw_hash=(self.put(raw) if kind!='unknown' else
                self.put(opaque_raw) if opaque_raw is not None else None)
            terminal=dict(synthetic_fixture=True,reservation_byte_sha256=reservation_hash,kind=kind,
                native_status='success' if kind=='verified' else 'failed' if kind=='known_invalid' else 'interrupted',
                artifacts=dict(raw_byte_sha256=raw_hash,cost_byte_sha256=self.put(cost)))
            terminal_hash=self.put(terminal)
        envelope=dict(synthetic_fixture=True,reservation_byte_sha256=reservation_hash,terminal_byte_sha256=terminal_hash)
        self.envelopes.append(self.put(envelope));return self.envelopes[-1]
    def seal_trace(self):
        self.trace=self.put(b.live_trace_bytes(self.review(),initial_state_digest=self.initial));return self.trace
    def replace(self,index,field,value):
        envelope=b.synthetic_artifact(self.store,self.envelopes[index]);envelope[field]=value
        self.envelopes[index]=self.put(envelope)


@pytest.fixture
def envelopes(declaration,mapping):return SyntheticEnvelopes(declaration[0],mapping)


def test_empty_envelope_prefix_authenticates_initial_state(envelopes):
    inputs=envelopes.inputs();inputs['initial_state_digest']='FOREIGN_INITIAL'
    with pytest.raises(ValueError,match='empty paid prefix'):
        b.review_attempt_envelopes(envelopes.context,envelopes.mapping,envelopes.key,**inputs)


def test_authenticated_envelopes_derive_success_model_status_and_keep_infeasible_data(envelopes):
    def infeasible(raw):
        raw['routes'][0].update(fmax_mhz=9.,device_fits=False,internal_timing_pass=False);raw['min_fmax_mhz']=9.
    envelopes.append(change_raw=infeasible);review=envelopes.review();row=review['live_model_rows'][0]
    assert review['charged_attempts']==1 and review['continuable']
    assert row['status']=='success' and row['routed_fmax_min_mhz']==9. and row['device_fits'] is False
    assert row['measurement_seconds']==2. and review['raw_native_evidence_authenticated'] is False
    assert review['live_verified_records'][0]['status']=='verified'
    public=joint_public(envelopes.mapping)
    # Reconstruct against the same schema and public digest as the actual observation.
    initial=FakeJoint(envelopes.public,[])
    state,_=b.reconstruct_policy_state(envelopes.key,initial,[],review['charged_ids'],review['live_verified_records'],
        mapping=envelopes.mapping,initial_public=envelopes.public,fake_conditioner=FakeConditioner())
    assert state.device_beta==2 and state.paid==review['charged_ids'] and initial.paid==[]


@pytest.mark.parametrize('kind',('pending','unknown'))
def test_pending_unknown_reservations_remain_charged_and_stop_without_retry(envelopes,kind):
    envelopes.append(kind);review=envelopes.review()
    assert review['charged_attempts']==1 and review['stopped'] and not review['continuable']
    assert not review['live_model_rows']
    with pytest.raises(ValueError,match='three continuable'):envelopes.seal_trace()
    # An extra supplied envelope cannot bypass a prior incomplete/unknown terminal.
    envelopes.envelopes.append(envelopes.envelopes[0])
    with pytest.raises(ValueError,match='stop with no retry'):envelopes.review()


@pytest.mark.parametrize('opaque',(None,b'{truncated simulator JSON',b'not JSON at all'))
def test_unknown_preserves_nullable_cost_bounds_and_missing_or_opaque_raw(envelopes,opaque):
    values=dict(native_command_seconds=None,attempt_seconds=None,cli_seconds=None,observer_seconds=4.)
    bounds=dict(native_command_seconds=.25,attempt_seconds=.5,cli_seconds=.75,observer_seconds=1.)
    envelopes.append('unknown',cost_values=values,bounds=bounds,opaque_raw=opaque)
    review=envelopes.review()
    assert review['stopped'] and review['charged_attempts']==1 and review['attempt_seconds'] is None
    assert review['known_attempt_seconds_lower_bound']==.5 and not review['live_model_rows']


@pytest.mark.parametrize('reason',('selfcheck','fault','memory'))
def test_explicit_known_invalid_charges_without_labels_and_allows_next_query(envelopes,reason):
    def raw_failure(raw):
        if reason!='selfcheck':raw['words'][4]=1
        if reason=='fault':raw['fault']=2
        elif reason=='memory':raw.update(stack_initialized=True,stack_violations=1,
            first_violation=dict(kind='stack-pointer',address=6524))
    envelopes.append('known_invalid',change_raw=raw_failure);first=envelopes.review()
    assert first['continuable'] and first['charged_attempts']==1 and not first['live_model_rows']
    envelopes.append();review=envelopes.review()
    assert review['charged_attempts']==2 and len(review['live_model_rows'])==1
    assert review['live_model_rows'][0]['candidate_id']==review['charged_ids'][1]


@pytest.mark.parametrize('defect',('generic','partial','selfasserted','incomplete_cost','learner_labels'))
def test_failure_cannot_become_known_invalid_from_error_flags_or_incomplete_evidence(envelopes,defect):
    def bad(raw):
        if defect in ('generic','selfasserted'):raw['words'][4]=1;raw.update(error='failed',exit_code=1,known_invalid=True)
        elif defect=='partial':raw['markers']=1
    envelopes.append('known_invalid',change_raw=bad)
    envelope=b.synthetic_artifact(envelopes.store,envelopes.envelopes[0])
    terminal=b.synthetic_artifact(envelopes.store,envelope['terminal_byte_sha256'])
    if defect=='incomplete_cost':
        cost=b.synthetic_artifact(envelopes.store,terminal['artifacts']['cost_byte_sha256'])
        cost['values']['attempt_seconds']=None;terminal['artifacts']['cost_byte_sha256']=envelopes.put(cost)
    elif defect=='learner_labels':terminal['speedup']=2.
    envelopes.replace(0,'terminal_byte_sha256',envelopes.put(terminal))
    with pytest.raises(ValueError):envelopes.review()


@pytest.mark.parametrize('artifact',('reservation','raw','cost','terminal','proof','envelope'))
def test_artifact_byte_tamper_fails_before_any_transition(envelopes,artifact):
    key=envelopes.append();envelope=b.synthetic_artifact(envelopes.store,key)
    reservation=b.synthetic_artifact(envelopes.store,envelope['reservation_byte_sha256'])
    terminal=b.synthetic_artifact(envelopes.store,envelope['terminal_byte_sha256'])
    hashes=dict(envelope=key,reservation=envelope['reservation_byte_sha256'],terminal=envelope['terminal_byte_sha256'],
        raw=terminal['artifacts']['raw_byte_sha256'],cost=terminal['artifacts']['cost_byte_sha256'],
        proof=reservation['acquisition_proof_byte_sha256'])
    envelopes.store[hashes[artifact]]+=b' '
    with pytest.raises(ValueError,match='byte SHA'):envelopes.review()


def test_late_state_callback_cannot_mutate_previously_authenticated_bytes(envelopes):
    envelopes.append();original=envelopes.state;calls=[]
    def malicious(rows):
        calls.append(1)
        if len(calls)==3:envelopes.store[envelopes.envelopes[0]]+=b' '
        return original(rows)
    malicious.fake_only=True;envelopes.state=malicious
    with pytest.raises(ValueError,match='byte SHA'):envelopes.review()
    assert len(calls)==3


@pytest.mark.parametrize('artifact',('raw','cost'))
def test_same_identity_artifacts_from_another_reservation_cannot_be_reused(envelopes,artifact):
    envelopes.append();envelope=b.synthetic_artifact(envelopes.store,envelopes.envelopes[0])
    terminal=b.synthetic_artifact(envelopes.store,envelope['terminal_byte_sha256'])
    key=artifact+'_byte_sha256';value=b.synthetic_artifact(envelopes.store,terminal['artifacts'][key])
    value['reservation_byte_sha256']='other-proof-model-reservation'
    terminal['artifacts'][key]=envelopes.put(value)
    envelopes.replace(0,'terminal_byte_sha256',envelopes.put(terminal))
    with pytest.raises(ValueError,match='reservation'):envelopes.review()


@pytest.mark.parametrize('defect',('slot','prefix','case','duplicate'))
def test_reservations_require_contiguous_unique_exact_case_and_prior_prefix(envelopes,defect):
    envelopes.append();envelopes.append()
    envelope=b.synthetic_artifact(envelopes.store,envelopes.envelopes[1])
    reservation=b.synthetic_artifact(envelopes.store,envelope['reservation_byte_sha256'])
    if defect=='slot':reservation['slot']=4
    elif defect=='prefix':reservation['prior_envelope_byte_sha256']=[]
    elif defect=='case':reservation['case']['model_manifest_sha256']='another-model'
    else:reservation['logical_candidate_id']=envelopes.mapping[0]['preparation_candidate_id']
    envelopes.replace(1,'reservation_byte_sha256',envelopes.put(reservation))
    with pytest.raises(ValueError):envelopes.review()


def test_cost_scopes_reject_impossible_outer_cost_and_sum_exact_known_attempts(envelopes):
    cost=dict(synthetic_fixture=True,reservation_byte_sha256='synthetic',
        values=dict(native_command_seconds=None,attempt_seconds=None,cli_seconds=None,observer_seconds=2.),
        known_lower_bounds=dict(native_command_seconds=3.,attempt_seconds=0.,cli_seconds=0.,observer_seconds=0.))
    with pytest.raises(ValueError,match='enclosing cost'):b.validate_attempt_cost(cost,complete_required=False)
    envelopes.append()
    values=dict(native_command_seconds=None,attempt_seconds=None,cli_seconds=None,observer_seconds=5.)
    bounds=dict(native_command_seconds=0.,attempt_seconds=3.,cli_seconds=0.,observer_seconds=0.)
    envelopes.append('unknown',cost_values=values,bounds=bounds)
    assert envelopes.review()['known_attempt_seconds_lower_bound']==5.


def test_three_live_trace_authenticates_references_without_exposing_reference_rows(envelopes):
    envelopes.append();envelopes.append('known_invalid');envelopes.append()
    before=envelopes.review();trace=envelopes.seal_trace()
    for _ in range(9):envelopes.append()
    after=envelopes.review();payload=b.synthetic_artifact(envelopes.store,trace)
    assert after['charged_attempts']==12 and after['live_model_rows']==before['live_model_rows']
    assert after['live_state_digest']==before['live_state_digest'] and len(after['live_verified_records'])==2
    assert payload['remaining_outcomes_exist'] is False and payload['raw_native_evidence_authenticated'] is False
    assert 'logical order' in payload['chronology']
    assert after['charged_ids']==[r['preparation_candidate_id'] for r in envelopes.mapping]
    with pytest.raises(b.DispatchDisabled):b.DisabledBridge().evaluate(after)


@pytest.mark.parametrize('kind',('pending','unknown'))
def test_reference_interruption_is_charged_and_blocks_later_references(envelopes,kind):
    for _ in range(3):envelopes.append()
    envelopes.seal_trace();live=envelopes.review()['live_model_rows'];envelopes.append(kind)
    review=envelopes.review()
    assert review['charged_attempts']==4 and review['stopped'] and review['live_model_rows']==live
    envelopes.envelopes.append(envelopes.envelopes[-1])
    with pytest.raises(ValueError,match='stop with no retry'):envelopes.review()


def test_unknown_terminal_cannot_smuggle_learner_labels(envelopes):
    envelopes.append('unknown');envelope=b.synthetic_artifact(envelopes.store,envelopes.envelopes[0])
    terminal=b.synthetic_artifact(envelopes.store,envelope['terminal_byte_sha256']);terminal['model_row']={'speedup':2.}
    envelopes.replace(0,'terminal_byte_sha256',envelopes.put(terminal))
    with pytest.raises(ValueError,match='Exact terminal'):envelopes.review()


def test_reference_boundary_requires_same_full_authenticated_live_trace(envelopes):
    for _ in range(3):envelopes.append()
    envelopes.seal_trace();review=envelopes.review();row=envelopes.mapping[3];key=envelopes.key
    trace=b.synthetic_artifact(envelopes.store,envelopes.trace)
    request=dict(logical_candidate_id=row['preparation_candidate_id'],native_candidate_id=row['declared_native_candidate_id'],
        native_context_id=envelopes.context['declared_native_context_id'],formula=row['formula'],assembly_sha256=row['assembly_sha256'],
        model_manifest_sha256=envelopes.context['model_manifest_sha256'],session_id=key['session_id'],mode='oracle-reference',
        attempted_ids_before=review['charged_ids'],successful_paid_ids=[r['candidate_id'] for r in review['live_model_rows']],
        proof_sha256=b.digest(None),live_trace_sha256=b.digest(trace))
    reservation=dict(**request,charged_slot=4,chosen_before_reservation=True)
    gate=b.DisabledBridge(envelopes.context,envelopes.mapping,None)
    receipt=gate.validate_for_review(key,review['charged_ids'],review['live_verified_records'],request,reservation,None,
        live_trace=trace,envelope_inputs=envelopes.inputs())
    assert receipt['mode']=='oracle-reference' and receipt['validated_contract_only']
    trace['final_state_digest']='foreign-state'
    with pytest.raises(ValueError,match='authenticated live trace'):
        gate.validate_for_review(key,review['charged_ids'],review['live_verified_records'],request,reservation,None,
            live_trace=trace,envelope_inputs=envelopes.inputs())


@pytest.mark.parametrize('defect',('missing','minimal','state','case','proof','envelope','order'))
def test_reference_rejects_missing_forged_or_crosscase_trace(envelopes,defect):
    for _ in range(3):envelopes.append()
    envelopes.seal_trace();trace=b.synthetic_artifact(envelopes.store,envelopes.trace)
    if defect=='missing':envelopes.trace=None
    elif defect=='minimal':trace=dict(synthetic_fixture=True,complete=True,attempted_ids=trace['attempted_ids'])
    elif defect=='state':trace['final_state_digest']='foreign-state'
    elif defect=='case':trace['case']['session']['seed']=1
    elif defect=='proof':trace['proof_codesign_digests'][0]='other-proof'
    elif defect=='envelope':trace['envelope_byte_sha256'][0]='other-envelope'
    elif defect=='order':trace['attempted_ids'].reverse()
    if defect!='missing':envelopes.trace=envelopes.put(trace)
    envelopes.append()
    with pytest.raises(ValueError,match='trace'):envelopes.review()


def test_boundary_rejects_caller_omitting_or_adding_authenticated_verified_rows(envelopes,transaction):
    envelopes.append();review=envelopes.review();context,key,proof,request,reservation=transaction
    # Use this envelope's actual case, public/prefix and recomputed second proof.
    key=envelopes.key;proof=envelopes.proof(review['charged_ids'],review['live_model_rows']);row=envelopes.mapping[1]
    request=dict(logical_candidate_id=row['preparation_candidate_id'],native_candidate_id=row['declared_native_candidate_id'],
        native_context_id=envelopes.context['declared_native_context_id'],formula=row['formula'],assembly_sha256=row['assembly_sha256'],
        model_manifest_sha256=envelopes.context['model_manifest_sha256'],session_id=key['session_id'],mode='adaptive',
        attempted_ids_before=review['charged_ids'],successful_paid_ids=[review['charged_ids'][0]],
        proof_sha256=b.digest(proof),live_trace_sha256=None)
    reservation=dict(**request,charged_slot=2,chosen_before_reservation=True)
    gate=b.DisabledBridge(envelopes.context,envelopes.mapping,proof)
    assert gate.validate_for_review(key,review['charged_ids'],review['live_verified_records'],request,reservation,proof,
        envelope_inputs=envelopes.inputs())['validated_contract_only']
    for forged in ([],review['live_verified_records']*2):
        with pytest.raises(ValueError):gate.validate_for_review(key,review['charged_ids'],forged,request,reservation,proof,
            envelope_inputs=envelopes.inputs())
    # A self-bound bridge proof is insufficient: rederive the CURRENT proof from
    # authenticated prior terminals, independently of the bound supplied proof.
    for defect in ('foreign_state','wrong_current_choice','stale_prefix'):
        forged_proof=copy.deepcopy(proof)
        if defect=='foreign_state':forged_proof['posterior_snapshot']['posterior_state_sha256']='FOREIGN_POSTERIOR'
        elif defect=='wrong_current_choice':forged_proof['event']['candidate_id']=envelopes.mapping[2]['preparation_candidate_id']
        else:forged_proof['event']['attempted_ids_before_query']=[]
        forged_request=dict(request,proof_sha256=b.digest(forged_proof))
        forged_reservation=dict(**forged_request,charged_slot=2,chosen_before_reservation=True)
        with pytest.raises(ValueError,match='Current acquisition proof'):
            b.DisabledBridge(envelopes.context,envelopes.mapping,forged_proof).validate_for_review(key,
                review['charged_ids'],review['live_verified_records'],forged_request,forged_reservation,forged_proof,
                envelope_inputs=envelopes.inputs())
    original_proof=envelopes.proof
    def malicious_current(attempted,rows):
        if len(attempted)==1:envelopes.store[envelopes.envelopes[0]]+=b' '
        return original_proof(attempted,rows)
    malicious_current.fake_only=True;envelopes.proof=malicious_current
    with pytest.raises(ValueError,match='byte SHA'):
        gate.validate_for_review(key,review['charged_ids'],review['live_verified_records'],request,reservation,proof,
            envelope_inputs=envelopes.inputs())
