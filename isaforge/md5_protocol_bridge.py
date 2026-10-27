"""Disabled bridge from frozen MD5 models to a declared evaluation protocol.

No native evaluator, native-root argument, tool invocation or target-outcome
loader exists here. Zero-paid authentication may load trusted saved models.
Paid reconstruction and evidence projection are synthetic-only test paths.
"""
from __future__ import annotations

from contextlib import ExitStack,contextmanager
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import time
from unittest.mock import patch

from . import md5_offline_controller as identity

ROOT=identity.REPOSITORY
PREREG=identity.PREREG
MODELS=PREREG/'model-preparation-v1'
MODEL_MANIFEST_SHA='84804c83a0cc9b0a2bce93c56bd4c72df2792035b1c52e15ebd2ceec0a63b000'
ENGINEERING_GAPS=('Native reservation/terminal evidence authentication and durable ledger recovery are not implemented.',
    'Native three-live-before-reference chronology and evaluator lock integration are not authenticated.',
    'Paid model/proof callbacks are synthetic-only; no real evaluator/model release authority exists.')
SOURCES=('isaforge/md5_protocol_bridge.py','scripts/prepare_md5_evaluation_protocol.py',
         'tests/test_md5_protocol_bridge.py')
DYNAMIC_FACTORIES={
    'hybrid_gp_adapt':'isaforge.budgeted_selection.HardwareSurrogate',
    'hybrid_gp_adapt_count':'isaforge.budgeted_selection.HardwareSurrogate',
    'hybrid_gp_adapt_count_semantic':'isaforge.semantic_selection.SemanticHardwareSurrogate'}
FIXED_CONDITIONER='isaforge.joint_hardware.JointHardwarePosterior.condition'
POLICIES=('frequency','merit','calibrated_latency','latency_cost_heuristic','random',
    'raw_regression','ranking','normalized_xgb','hybrid_gp_zero_shot','hybrid_gp_adapt',
    'feasible_benefit_xgb','factorized_feasibility_xgb','hybrid_gp_adapt_count',
    'hybrid_gp_adapt_count_semantic','fixed_joint_myopic','fixed_joint_lookahead','fixed_joint_heuristic_fallback')

require=identity.require
digest=identity.digest
sha=identity.sha


class DispatchDisabled(RuntimeError):pass
class ProtocolIncomplete(DispatchDisabled):pass


class DisabledBridge:
    """No bypass flag, evaluator injection, native parameters or enabled branch."""
    candidate_dispatch_enabled=False
    measurement_authorization=False
    def __init__(self,context=None,mapping=None,recomputed_proof=None):
        self._binding=identity.pack(dict(context=context,mapping=mapping,proof=recomputed_proof))
    def validate_for_review(self,session,attempted,verified,request,reservation,proof,**kwargs):
        bound=json.loads(self._binding)
        require(bound['context'] is not None,'No declared review binding')
        return validate_transaction(bound['context'],bound['mapping'],session,attempted,verified,
            proof,bound['proof'],request,reservation,**kwargs)
    def evaluate(self,*args,**kwargs):
        raise DispatchDisabled('Protocol declaration only; native dispatch is hard-disabled')


def declared_context(contract,archived_plan,model_manifest_sha,source_bindings,*,archived_plan_file_sha256):
    require(archived_plan['context_id']==contract['identity_basis']['archived_hardware_context_id'],
        'Archived hardware context mismatch')
    partition=archived_plan['memory_partition']
    require(partition['program_limit']==6400 and partition['stack_floor']==6528 and
        archived_plan['configuration']['ram_bytes']==8192,'Frozen6400/6528/8KiB context required')
    basis=dict(schema='isaforge-md5-declared-native-context-v1',authenticated_native_plan=False,
        archived_hardware_context_id=archived_plan['context_id'],
        preparation_context_id=contract['preparation_context_id'],model_manifest_sha256=model_manifest_sha,
        archived_plan_codesign_digest=digest(archived_plan),archived_plan_file_sha256=archived_plan_file_sha256,
        compiler_flags=archived_plan['compiler_flags'],
        memory_partition=partition,configuration=archived_plan['configuration'],
        hardware_and_source_inputs=archived_plan['inputs'],archived_source_bindings=archived_plan['source_bindings'],
        protocol_source_bindings=source_bindings,clock_mhz=12.,route_seeds=[1,2,3],
        status='Declared identity only; no fresh prepared/evaluator-authenticated native plan exists.')
    return dict(**basis,declared_native_context_id=digest(basis))


def native_remap(preparation_remap,context):
    rows=[];namespace=context['declared_native_context_id']
    require(len(preparation_remap)==12,'Exactly twelve identities required')
    require(namespace==digest({k:v for k,v in context.items() if k!='declared_native_context_id'}),
        'Declared context self-digest mismatch')
    for row in preparation_remap:
        require(row['preparation_context_id']==context['preparation_context_id'] and
            row['archived_context_id']==context['archived_hardware_context_id'], 'Remap context mismatch')
        require(row['preparation_candidate_id']==digest([row['preparation_context_id'],row['formula']]) and
            row['archived_candidate_id']==digest([row['archived_context_id'],row['formula']]),'Formula identity digest mismatch')
        rows.append(dict(**row,declared_native_context_id=namespace,
            declared_native_candidate_id=digest([namespace,row['formula']])))
    for key in ('name','formula','archived_candidate_id','preparation_candidate_id','declared_native_candidate_id'):
        require(len({r[key] for r in rows})==12,'Non-bijective '+key)
    require(namespace not in (context['preparation_context_id'],context['archived_hardware_context_id']),
        'Declared native namespace must be explicit and distinct')
    return rows


def make_session(policy,seed,horizon):
    value=dict(policy=policy,seed=seed,horizon=horizon)
    return dict(**value,session_id=digest(value))


def validate_prefix(session,mapping,attempted_ids,verified_records,*,collection=False):
    require(session==make_session(session['policy'],session['seed'],session['horizon']) and
        session['policy'] in POLICIES and type(session['seed']) is int and session['seed'] in range(5) and
        type(session['horizon']) is int and session['horizon'] in (1,2,3) and
        (session['policy'].startswith('fixed_joint_') or session['horizon']==3),'Unknown/unbound policy session')
    by_id={r['preparation_candidate_id']:r for r in mapping}
    require(len(by_id)==len(mapping)==12 and len(attempted_ids)==len(set(attempted_ids)) and
        set(attempted_ids)<=set(by_id) and len(attempted_ids)<=(12 if collection else session['horizon']),
        'Unknown/duplicate/over-budget attempted prefix')
    successful=[]
    for wrapped in verified_records:
        require(wrapped['session']==session and wrapped['candidate_id'] in attempted_ids and
            wrapped['candidate_id'] not in successful and wrapped['status']=='verified', 'Foreign/unpaid/unverified observation')
        row=by_id[wrapped['candidate_id']];outcome=wrapped['outcome']
        require(outcome['candidate_id']==row['preparation_candidate_id'] and
            wrapped['preparation_context_id']==row['preparation_context_id'] and outcome['formula']==row['formula'] and
            wrapped['assembly_sha256']==row['assembly_sha256'] and outcome['status']=='success' and
            outcome.get('failure_class') is None, 'Wrapped outcome identity/status mismatch')
        from . import budgeted_selection as selection
        require(selection.validate_outcome(outcome),'Verified wrapper requires successful validated model row')
        successful.append(wrapped['candidate_id'])
    require(successful==[i for i in attempted_ids if i in successful],'Verified prefix order changed')
    return by_id,successful


def synthetic_bytes(store,byte_sha256):
    """Authenticate opaque supplied bytes, including truncated unknown evidence."""
    raw=store[byte_sha256]
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==byte_sha256,'Synthetic artifact byte SHA mismatch')
    return raw


def synthetic_artifact(store,byte_sha256):
    """Decode synthetic JSON only after byte authentication; no filesystem reads."""
    raw=synthetic_bytes(store,byte_sha256)
    def pairs(items):
        require(len(dict(items))==len(items),'Duplicate synthetic JSON key')
        return dict(items)
    def invalid(value):raise ValueError('Nonfinite synthetic JSON constant: '+value)
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    require(type(value) is dict and value.get('synthetic_fixture') is True,'Explicit synthetic artifact required')
    digest(value)  # Separately named canonical object digest, not the raw-byte SHA.
    return value


def validate_attempt_cost(cost,*,complete_required):
    names=('native_command_seconds','attempt_seconds','cli_seconds','observer_seconds')
    require(set(cost)=={'synthetic_fixture','reservation_byte_sha256','values','known_lower_bounds'} and
        set(cost['values'])==set(cost['known_lower_bounds'])==set(names),'Exact named cost scopes required')
    from .model import _number
    values=cost['values'];bounds=cost['known_lower_bounds']
    for name in names:
        require(_number(bounds[name],'known cost lower bound')>=0,'Negative cost lower bound')
        if values[name] is not None:
            require(_number(values[name],'known cost')>=bounds[name],'Known cost is below its authenticated lower bound')
    for index,name in enumerate(names):
        if values[name] is not None:
            require(values[name]>=max(bounds[n] for n in names[:index+1]),
                'Known enclosing cost is below a contained-scope lower bound')
    known=[(i,values[name]) for i,name in enumerate(names) if values[name] is not None]
    require(all(a[1]<=b[1] for a,b in zip(known,known[1:])),'Overlapping cost scopes are inconsistent')
    complete=all(values[name] is not None for name in names)
    if complete_required:require(complete and values['attempt_seconds']>0,'Complete terminal costs required')
    return dict(values=copy.deepcopy(values),known_lower_bounds=copy.deepcopy(bounds),complete=complete,
        scopes_overlap=True,setup_historical_model_and_inference_excluded=True)


def classify_complete_invalid(raw):
    """Strict normalized SYNTHETIC raw-evidence predicate, not a native audit."""
    require(type(raw.get('words')) is list and len(raw['words'])==5 and
        all(type(v) is int and 0<=v<2**32 for v in raw['words']) and raw['words'][0]==0x49534146 and
        type(raw.get('markers')) is int and raw['markers']==2 and
        type(raw.get('partial_report_bits')) is int and raw['partial_report_bits']==0,
        'Complete explicit raw failure report required')
    require(type(raw.get('fault')) is int and raw['fault']>=0 and type(raw.get('trapped')) is bool and
        type(raw.get('stack_violations')) is int and raw['stack_violations']>=0,
        'Malformed explicit failure evidence')
    if raw['stack_violations']:
        violation=raw.get('first_violation',{})
        require(raw.get('stack_initialized') is True and violation.get('kind') in ('stack-pointer','ram-write') and
            type(violation.get('address')) is int and
            ((violation['kind']=='stack-pointer' and not 6528<=violation['address']<=8192) or
             (violation['kind']=='ram-write' and 6400<=violation['address']<6528)),
            'Explicit bounded-memory violation required')
        return 'memory_contract_failure'
    if raw['words'][4]==0:return 'recorded_self_check_failure'
    if raw['fault'] or raw['trapped']:return 'recorded_execution_failure'
    raise ValueError('Generic failure/exit code/error string is not known invalidity')


def envelope_case(context,mapping,session,public):
    require(mapping==native_remap([{k:v for k,v in row.items() if not k.startswith('declared_native_')}
        for row in mapping],context),'Declared mapping differs')
    validate_prefix(session,mapping,[],[],collection=True)
    require((session['policy'],session['seed'],session['horizon'])==('fixed_joint_lookahead',0,3),'Wrong live session')
    from . import budgeted_selection as selection
    public=selection.public_rows(public)
    require([r['candidate_id'] for r in public]==[r['preparation_candidate_id'] for r in mapping] and
        all(p['formula']==m['formula'] for p,m in zip(public,mapping)),'Exact declared public roster required')
    return dict(session=copy.deepcopy(session),model_manifest_sha256=context['model_manifest_sha256'],
        native_context_id=context['declared_native_context_id'],mapping_codesign_digest=digest(mapping),
        public_codesign_digest=digest(public))


def _live_trace(review,initial_state_digest,final_state_digest):
    require(len(review['charged_ids'])==3 and review['continuable'] and
        len(review['envelope_byte_sha256'])==3,'Exactly three continuable live envelopes required')
    return dict(synthetic_fixture=True,schema='md5-synthetic-live-trace-v1',case=review['case'],
        envelope_byte_sha256=review['envelope_byte_sha256'],proof_codesign_digests=review['proof_codesign_digests'],
        attempted_ids=review['charged_ids'],successful_paid_ids=[r['candidate_id'] for r in review['live_model_rows']],
        live_model_rows_codesign_digest=digest(review['live_model_rows']),initial_state_digest=initial_state_digest,
        final_state_digest=final_state_digest,remaining_outcomes_exist=False,
        chronology='Synthetic logical order only; native collection chronology is not authenticated.',
        raw_native_evidence_authenticated=False)


def review_attempt_envelopes(context,mapping,session,public,store,envelope_hashes,*,initial_state_digest,
                            fake_proof,fake_state,live_trace_hash=None):
    """Replay a synthetic byte store. Callbacks are cooperative, never real models.

    Reservation charges survive a pending/unknown terminal. All prior terminals
    must authenticate before another reservation. Reference payloads are private
    to collection and never enter the first-three live model-row view.
    """
    require(getattr(fake_proof,'fake_only',False) is True and getattr(fake_state,'fake_only',False) is True,
        'Marked fake proof/state callbacks required')
    require(type(initial_state_digest) is str and bool(initial_state_digest),'Initial state digest required')
    require(initial_state_digest==fake_state([]),'Initial state differs from empty paid prefix')
    case=envelope_case(context,mapping,session,public);by_id={r['preparation_candidate_id']:r for r in mapping}
    public_by_id={r['candidate_id']:r for r in public}
    review=dict(case=case,charged_ids=[],live_model_rows=[],envelope_byte_sha256=[],proof_codesign_digests=[],
        terminal_codesign_digests=[],costs=[],continuable=True,stopped=False,raw_native_evidence_authenticated=False,
        synthetic_contract_only=True)
    require(type(envelope_hashes) in (list,tuple) and len(envelope_hashes)<=12,'At most twelve charged slots')
    touched=[]
    for index,envelope_hash in enumerate(envelope_hashes):
        require(review['continuable'],'Pending/unknown attempt is charged; stop with no retry/replacement')
        envelope=synthetic_artifact(store,envelope_hash);touched.append(envelope_hash)
        require(set(envelope)=={'synthetic_fixture','reservation_byte_sha256','terminal_byte_sha256'},'Exact attempt envelope required')
        reservation_hash=envelope['reservation_byte_sha256'];reservation=synthetic_artifact(store,reservation_hash)
        touched.append(reservation_hash)
        identity_id=reservation['logical_candidate_id'];require(identity_id in by_id and identity_id not in review['charged_ids'],
            'Unknown/duplicate charged identity; no retries')
        row=by_id[identity_id];reference=index>=3
        expected=dict(synthetic_fixture=True,case=case,slot=index+1,logical_candidate_id=identity_id,
            native_candidate_id=row['declared_native_candidate_id'],formula=row['formula'],assembly_sha256=row['assembly_sha256'],
            prior_envelope_byte_sha256=list(review['envelope_byte_sha256']),
            live_model_rows_codesign_digest=digest(review['live_model_rows']),mode='reference' if reference else 'live',
            acquisition_proof_byte_sha256=reservation['acquisition_proof_byte_sha256'],
            acquisition_proof_codesign_digest=reservation['acquisition_proof_codesign_digest'],
            live_trace_byte_sha256=live_trace_hash if reference else None)
        require(reservation==expected,'Reservation case/slot/identity/assembly/prefix binding differs')
        if reference:
            require(live_trace_hash is not None,'Authenticated complete live trace required before reference')
            trace=synthetic_artifact(store,live_trace_hash);touched.append(live_trace_hash)
            live_review={**review,'charged_ids':review['charged_ids'][:3],
                'envelope_byte_sha256':review['envelope_byte_sha256'][:3],
                'proof_codesign_digests':review['proof_codesign_digests'][:3]}
            require(trace==_live_trace(live_review,initial_state_digest,fake_state(copy.deepcopy(review['live_model_rows']))),
                'Live trace differs from same case/envelopes/proofs/recomputed state')
            require(identity_id==next(r['preparation_candidate_id'] for r in mapping
                if r['preparation_candidate_id'] not in review['charged_ids']) and
                reservation['acquisition_proof_byte_sha256'] is None and
                reservation['acquisition_proof_codesign_digest'] is None,'Reference order/proof differs')
        else:
            proof_hash=reservation['acquisition_proof_byte_sha256'];proof=synthetic_artifact(store,proof_hash);touched.append(proof_hash)
            state_digest=fake_state(copy.deepcopy(review['live_model_rows']))
            require((index>0 or state_digest==initial_state_digest) and
                proof==fake_proof(copy.deepcopy(review['charged_ids']),copy.deepcopy(review['live_model_rows'])) and
                reservation['acquisition_proof_codesign_digest']==digest(proof),'Recomputed synthetic acquisition proof differs')
            event=proof['event']
            require(event['candidate_id']==identity_id and event['policy']==session['policy'] and
                event['planned_budget']==3 and event['remaining_queries']==3-index and event['charged_before_query']==index and
                event['attempted_ids_before_query']==review['charged_ids'] and
                event['paid_target_ids_before_query']==[r['candidate_id'] for r in review['live_model_rows']] and
                proof['successful_paid_ids']==event['paid_target_ids_before_query'] and
                proof['posterior_snapshot']['posterior_state_sha256']==state_digest,'Acquisition own-prefix/state differs')
        review['charged_ids'].append(identity_id);review['envelope_byte_sha256'].append(envelope_hash)
        review['proof_codesign_digests'].append(reservation['acquisition_proof_codesign_digest'])
        terminal_hash=envelope['terminal_byte_sha256']
        if terminal_hash is None:
            review.update(continuable=False,stopped=True);review['terminal_codesign_digests'].append(None)
            review['costs'].append(None);continue
        terminal=synthetic_artifact(store,terminal_hash);touched.append(terminal_hash)
        require(set(terminal)=={'synthetic_fixture','reservation_byte_sha256','kind','native_status','artifacts'} and
            terminal['reservation_byte_sha256']==reservation_hash and terminal['kind'] in ('verified','known_invalid','unknown') and
            set(terminal['artifacts'])=={'raw_byte_sha256','cost_byte_sha256'},'Exact terminal/reservation/artifact join required')
        verified=terminal['kind']=='verified';known=terminal['kind']=='known_invalid'
        raw_hash=terminal['artifacts']['raw_byte_sha256'];cost_hash=terminal['artifacts']['cost_byte_sha256']
        require(raw_hash is not None or not (verified or known),'Verified/known-invalid raw artifact required')
        raw=synthetic_artifact(store,raw_hash) if raw_hash is not None and (verified or known) else None
        if raw_hash is not None and not (verified or known):synthetic_bytes(store,raw_hash)
        if raw_hash is not None:touched.append(raw_hash)
        cost=synthetic_artifact(store,cost_hash);touched.append(cost_hash)
        require(cost['reservation_byte_sha256']==reservation_hash,'Cost belongs to a different reservation')
        if raw is not None:
            require(raw['reservation_byte_sha256']==reservation_hash and raw['candidate_id']==row['declared_native_candidate_id'] and
                raw['context_id']==context['declared_native_context_id'] and raw['formula']==row['formula'] and
                raw['assembly_sha256']==row['assembly_sha256'],'Terminal raw reservation/identity/assembly differs')
        cost_receipt=validate_attempt_cost(cost,complete_required=verified or known)
        if verified:
            require(terminal['native_status']=='success','Verified terminal requires native success')
            hardware=validate_sealed_synthetic_hardware(raw)
            require(raw['durations']==cost['values'],'Hardware/raw charged cost differs')
            model_row=dict(copy.deepcopy(public_by_id[identity_id]),status='success',baseline_cycles=raw['baseline']['cycles'],
                candidate_cycles=raw['candidate']['cycles'],speedup=raw['speedup'],area_delta_lut4=raw['added_lut4'],
                routed_fmax_min_mhz=raw['min_fmax_mhz'],device_fits=hardware['device_fits'],correctness_verified=True,
                measurement_seconds=cost['values']['attempt_seconds'])
            from . import budgeted_selection as selection
            require(selection.validate_outcome(model_row,public_by_id[identity_id]),'Derived verified model row invalid')
            if not reference:review['live_model_rows'].append(model_row)
        elif known:
            require(terminal['native_status']=='failed','Known invalid requires failed native terminal')
            classify_complete_invalid(raw)  # No model labels or Beta update.
        else:
            require(terminal['native_status'] in ('started','failed','interrupted','unknown','success'),'Unknown native status')
            review.update(continuable=False,stopped=True)
        review['terminal_codesign_digests'].append(digest(terminal));review['costs'].append(cost_receipt)
    review['live_state_digest']=fake_state(copy.deepcopy(review['live_model_rows']))
    review['charged_attempts']=len(review['charged_ids'])
    review['attempt_seconds']=sum(c['values']['attempt_seconds'] for c in review['costs']) if all(
        c is not None and c['values']['attempt_seconds'] is not None for c in review['costs']) else None
    review['known_attempt_seconds_lower_bound']=sum(c['values']['attempt_seconds'] if c['values']['attempt_seconds'] is not None
        else c['known_lower_bounds']['attempt_seconds'] for c in review['costs'] if c is not None)
    review['live_verified_records']=[dict(session=copy.deepcopy(session),candidate_id=r['candidate_id'],status='verified',
        synthetic_fixture=True,preparation_context_id=by_id[r['candidate_id']]['preparation_context_id'],
        assembly_sha256=by_id[r['candidate_id']]['assembly_sha256'],outcome=copy.deepcopy(r)) for r in review['live_model_rows']]
    # Recheck AFTER the final callback; callbacks remain cooperative fixtures.
    review['authenticated_artifact_byte_sha256']=sorted(set(touched))
    for artifact_hash in review['authenticated_artifact_byte_sha256']:synthetic_bytes(store,artifact_hash)
    return review


def live_trace_bytes(review,*,initial_state_digest):
    """Pure serialization only; a later review authenticates it from its inputs."""
    return identity.pack(_live_trace(review,initial_state_digest,review['live_state_digest']))


def validate_transaction(context,mapping,session,attempted,verified,proof,recomputed_proof,request,reservation,*,
                         live_trace=None,envelope_inputs=None):
    """Pure evaluator-bound proof/reservation binding; grants no dispatch authority."""
    require(mapping==native_remap([{k:v for k,v in row.items() if not k.startswith('declared_native_')} for row in mapping],context),
        'Declared mapping differs')
    by_id,successful=validate_prefix(session,mapping,attempted,verified,collection=True)
    require((session['policy'],session['seed'],session['horizon'])==('fixed_joint_lookahead',0,3), 'Wrong live session')
    identity_id=request['logical_candidate_id'];require(identity_id in by_id and identity_id not in attempted,'Unknown/already charged query')
    row=by_id[identity_id];index=len(attempted)
    require(index<12,'Collection budget exhausted')
    if envelope_inputs is not None:
        authenticated=review_attempt_envelopes(context,mapping,session,**envelope_inputs)
        require(authenticated['continuable'] and authenticated['charged_ids']==attempted and
            authenticated['live_verified_records']==verified,'Caller prefix differs from authenticated terminal envelopes')
    else:authenticated=None
    if index>=3 and authenticated is None:raise DispatchDisabled('Reference-phase trace authentication incomplete; bridge NO-GO')
    if (attempted or verified) and authenticated is None:
        raise DispatchDisabled('Zero-paid transaction review only; terminal accounting authentication incomplete')
    if index<3:
        require(live_trace is None and proof==recomputed_proof,'Exact recomputed live proof required')
        if authenticated is not None:
            require(proof==envelope_inputs['fake_proof'](copy.deepcopy(authenticated['charged_ids']),
                copy.deepcopy(authenticated['live_model_rows'])) and
                proof['posterior_snapshot']['posterior_state_sha256']==authenticated['live_state_digest'],
                'Current acquisition proof differs from authenticated own-prefix state')
        event=proof['event']
        require(event['candidate_id']==identity_id and event['policy']==session['policy'] and
            event['planned_budget']==3 and event['remaining_queries']==3-index and
            event['charged_before_query']==index and event['attempted_ids_before_query']==attempted and
            event['paid_target_ids_before_query']==successful and proof['successful_paid_ids']==successful,
            'Acquisition own-prefix/horizon mismatch')
        mode='adaptive'
    else:
        trace_hash=envelope_inputs['live_trace_hash']
        trace=synthetic_artifact(envelope_inputs['store'],trace_hash)
        first_three=review_attempt_envelopes(context,mapping,session,**{**envelope_inputs,
            'envelope_hashes':envelope_inputs['envelope_hashes'][:3],'live_trace_hash':None})
        require(proof is None and recomputed_proof is None and live_trace==trace==_live_trace(first_three,
            envelope_inputs['initial_state_digest'],first_three['live_state_digest']),
            'Complete authenticated live trace required before reference')
        require(identity_id==next(r['preparation_candidate_id'] for r in mapping if r['preparation_candidate_id'] not in attempted),
            'Wrong reference remainder order')
        mode='oracle-reference'
    expected=dict(logical_candidate_id=identity_id,native_candidate_id=row['declared_native_candidate_id'],
        native_context_id=context['declared_native_context_id'],formula=row['formula'],assembly_sha256=row['assembly_sha256'],
        model_manifest_sha256=context['model_manifest_sha256'],session_id=session['session_id'],mode=mode,
        attempted_ids_before=list(attempted),successful_paid_ids=successful,proof_sha256=digest(proof),
        live_trace_sha256=digest(live_trace) if live_trace is not None else None)
    require(request==expected and reservation==dict(**expected,charged_slot=index+1,chosen_before_reservation=True),
        'Evaluator request/reservation binding mismatch')
    if authenticated is not None:
        for artifact_hash in authenticated['authenticated_artifact_byte_sha256']:
            synthetic_bytes(envelope_inputs['store'],artifact_hash)
        if index>=3:synthetic_bytes(envelope_inputs['store'],envelope_inputs['live_trace_hash'])
    return dict(**expected,reservation_sha256=digest(reservation),validated_contract_only=True)


def validate_sealed_synthetic_hardware(record):
    """Sealed-record consistency under normalized exact-12-MHz constraints.

    Not raw evidence authentication/correctness proof. The frozen route parser
    uses math.isclose for constraints; a future native adapter must bind exact
    actual constraints or reject/normalize near-12 tolerance differences.
    """
    require(record.get('synthetic_fixture') is True and record['status']=='verified' and
        record.get('failure_class') is None,'Unknown/failed outcome cannot be verified')
    baseline=record['baseline'];candidate=record['candidate'];memory=record['memory'];controls=record['controls']
    values=[baseline['cycles'],candidate['cycles'],baseline['lut4'],candidate['lut4'],record['speedup'],record['added_lut4'],
        record['min_fmax_mhz'],*record['durations'].values(),*(r['fmax_mhz'] for r in record['routes']),
        *(r['fmax_mhz'] for r in baseline['routes'])]
    from .model import _number
    for value in values:_number(value,'sealed numeric')
    require(all(type(v) is int for v in (baseline['cycles'],candidate['cycles'],baseline['lut4'],candidate['lut4'],
        memory['program_end'],memory['stack_min'],*(r['seed'] for r in record['routes']),
        *(r['seed'] for r in baseline['routes']))),'Integral cycle/resource/memory/seed fields required')
    require(baseline['cycles']>0 and candidate['cycles']>0 and baseline['integrated_soc'] is True and
        candidate['integrated_soc'] is True and baseline['lut4']>=0 and candidate['lut4']>=0,'Invalid integrated baseline/candidate')
    require(record['speedup']==baseline['cycles']/candidate['cycles'] and
        record['added_lut4']==candidate['lut4']-baseline['lut4'],'Inconsistent cycles/area labels')
    require(memory==dict(ram_bytes=8192,program_limit=6400,stack_floor=6528,program_end=memory['program_end'],
        stack_min=memory['stack_min'],guard_violations=0,stack_violations=0) and
        0<=memory['program_end']<=6400 and 6528<=memory['stack_min']<=8192,'Memory/guard contract failed')
    require(all(baseline.get(k) is True for k in ('preserved','stack_negative_control','guard_negative_control')) and
        all(controls.get(k) is True for k in ('recorded_input_self_check','integer_oracle','pcpi_handshake',
            'stock_on_extension','custom_on_unextended_traps','custom_execution_count_matches')),'Incomplete baseline/PCPI/correctness controls')
    routes=record['routes']
    require(all([r['seed'] for r in table]==[1,2,3] and all(type(r['device_fits']) is bool and
        type(r['internal_timing_pass']) is bool and r['fmax_mhz']>0 for r in table)
        for table in (routes,baseline['routes'])),'Malformed route/device/timing record')
    require(all(r['internal_timing_pass']==(r['fmax_mhz']>=12) for table in (routes,baseline['routes']) for r in table),
        'Normalized exact12 route timing flag/Fmax mismatch')
    require(all(r['device_fits'] and r['internal_timing_pass'] and r['fmax_mhz']>=12
        for r in baseline['routes']),'Baseline route/device/timing contract failed')
    require(record['min_fmax_mhz']==min(r['fmax_mhz'] for r in routes),'Incorrect minimum Fmax')
    cost=record['durations']
    require(0<=cost['native_command_seconds']<=cost['attempt_seconds']<=cost['cli_seconds']<=cost['observer_seconds'] and
        cost['attempt_seconds']>0,'Incomplete/inconsistent charged durations')
    device_fits=all(r['device_fits'] for r in routes)
    timing_feasible=all(r['internal_timing_pass'] and r['fmax_mhz']>=12 for r in routes)
    return dict(sealed_record_contract_valid=True,device_fits=device_fits,timing_feasible=timing_feasible,
        feasible_at_cap64=record['added_lut4']<=64 and device_fits and timing_feasible,
        raw_native_evidence_authenticated=False)


def validate_pristine_joint(initial,history,public,mapping):
    """Authenticate the public initial-state contract before any clone/update."""
    require(public is not None,'Explicit initial public rows required for fixed-joint authentication')
    ids=[r['preparation_candidate_id'] for r in mapping]
    # The fitted public projection omits context/assembly fields. Identity binds
    # its formula/context; assembly remains bound by the evaluator/remap boundary.
    require([r['candidate_id'] for r in public]==ids and all(
        row['formula']==bound['formula'] and bound['preparation_candidate_id']==
        digest([bound['preparation_context_id'],bound['formula']]) for row,bound in zip(public,mapping)),
        'Fixed-joint declared public pool differs')
    snapshot=initial.snapshot()
    require(tuple(initial.candidate_ids)==tuple(ids) and snapshot['candidate_ids']==ids and
        snapshot['public_pool_sha256']==digest(public),'Fixed-joint initial pool differs')
    require(not initial.observed_ids and not initial.conditioned_ids and not snapshot['paid_ids'] and
        not snapshot['fantasy_ids'] and snapshot['hypothetical'] is False,
        'Fixed-joint initial state must be pristine; no paid/fantasy/conditioned identities')
    training_ids=[r['candidate_id'] for r in history]
    require(snapshot['initial_training_ids']==training_ids and
        snapshot['initial_snapshot']['training_ids']==training_ids and
        snapshot['initial_snapshot']['training_rows_sha256']==digest(history),
        'Fixed-joint initial history differs')


def reconstruct_policy_state(session,initial,history,attempted_ids,verified_records,*,mapping,
                             initial_public=None,fake_factories=None,fake_conditioner=None):
    """Concrete own-prefix update path, currently paid SYNTHETIC execution only.

    Original dynamic factories are named above; fixed-joint uses clone().condition.
    This milestone never enables those real paid calls. Injected marked fakes
    exercise exactly which own verified records each factory/conditioner receives.
    """
    validate_prefix(session,mapping,attempted_ids,verified_records)
    if session['policy'].startswith('fixed_joint_'):
        validate_pristine_joint(initial,history,initial_public,mapping)
    ids=[];outcomes=[]
    for wrapped in verified_records:
        require(wrapped['session']==session and wrapped['candidate_id'] in attempted_ids and
            wrapped['candidate_id'] not in ids and wrapped['status']=='verified', 'Foreign/unpaid/unverified observation')
        require(wrapped['synthetic_fixture'] is True,'Real paid reconstruction not enabled')
        ids.append(wrapped['candidate_id']);outcomes.append(copy.deepcopy(wrapped['outcome']))
    require(ids==[i for i in attempted_ids if i in ids],'Verified observations must retain charged prefix order')
    receipt=dict(session=copy.deepcopy(session),attempted_ids=list(attempted_ids),successful_paid_ids=ids,
        real_model_fits=0,synthetic_only=bool(outcomes))
    policy=session['policy']
    if not outcomes:
        receipt['update']='frozen initial state; zero paid observations'
        return copy.deepcopy(initial),receipt
    if policy in DYNAMIC_FACTORIES:
        name=DYNAMIC_FACTORIES[policy];factory=(fake_factories or {}).get(name)
        require(factory is not None and getattr(factory,'fake_only',False),'Marked fake factory required')
        model=factory();require(getattr(model,'fake_only',False),'Fake model required')
        state=model.fit(copy.deepcopy(history)+outcomes)
        receipt.update(update='dynamic refit',factory=name)
    elif policy.startswith('fixed_joint_'):
        require(fake_conditioner is not None and getattr(fake_conditioner,'fake_only',False),'Marked fake conditioner required')
        state=initial.clone()
        for candidate_id,outcome in zip(ids,outcomes):
            state=fake_conditioner(state,copy.deepcopy(outcome),queried_id=candidate_id)
        receipt.update(update='fixed initial preprocessing/kernel; own-paid conditioning',conditioner=FIXED_CONDITIONER)
    else:
        state=copy.deepcopy(initial)
        receipt.update(update='frozen fitted parameters; rescore against own paid incumbent',incumbent_inputs=outcomes)
    return state,receipt


def project_preserved_synthetic_evidence(original_path,original_sha256,mapping,*,ledger_path,ledger_sha256,validated_transaction):
    """Test only: raw native record+ledger bytes must preexist unchanged.

    No real-outcome loader is provided. The caller supplies temporary synthetic
    fixtures; original IDs, contexts, durations and raw bytes remain untouched.
    """
    paths=[Path(original_path).resolve(),Path(ledger_path).resolve()]
    require(all(p.is_relative_to(Path(tempfile.gettempdir()).resolve()) and not p.is_relative_to(ROOT) for p in paths),
        'Projection accepts temporary synthetic evidence only')
    require(sha(paths[0])==original_sha256 and sha(paths[1])==ledger_sha256,'Original evidence/ledger changed')
    raw=json.loads(paths[0].read_text());ledger=json.loads(paths[1].read_text())
    require(raw.get('synthetic_fixture') is True and ledger.get('synthetic_fixture') is True,
        'Real native evidence projection is not enabled')
    validate_sealed_synthetic_hardware(raw)
    require(ledger['original_record_sha256']==original_sha256 and ledger['status']=='success' and
        ledger['durations']==raw['durations'] and validated_transaction['validated_contract_only'] is True,
        'Incomplete original ledger/record join')
    for key in ('logical_candidate_id','native_candidate_id','native_context_id','formula','assembly_sha256','model_manifest_sha256',
                'session_id','proof_sha256','reservation_sha256','attempted_ids_before','successful_paid_ids'):
        require(all(key in transaction for transaction in (raw['transaction'],ledger['transaction'],validated_transaction)) and
            raw['transaction'][key]==ledger['transaction'][key]==validated_transaction[key],
            'Original proof/reservation/model/prefix join differs')
    for record in (raw,ledger):
        require(record['candidate_id']==mapping['declared_native_candidate_id'] and
            record['context_id']==mapping['declared_native_context_id'] and
            record['formula']==mapping['formula'] and record['assembly_sha256']==mapping['assembly_sha256'],
            'Original native identity/formula/assembly mismatch')
    require(all(validated_transaction[key]==mapping[bound] for key,bound in (
        ('native_candidate_id','declared_native_candidate_id'),('native_context_id','declared_native_context_id'),
        ('formula','formula'),('assembly_sha256','assembly_sha256'))) and
        validated_transaction['logical_candidate_id']==mapping['preparation_candidate_id'],
        'Transaction differs from same original native record/mapping')
    logical=copy.deepcopy(raw)
    logical.update(candidate_id=mapping['preparation_candidate_id'],context_id=mapping['preparation_context_id'],
        native_evidence=dict(original_path=str(paths[0]),original_sha256=original_sha256,
            ledger_path=str(paths[1]),ledger_sha256=ledger_sha256,
            original_native_candidate_id=raw['candidate_id'],original_native_context_id=raw['context_id'],
            original_durations=copy.deepcopy(raw['durations'])))
    require(sha(paths[0])==original_sha256 and sha(paths[1])==ledger_sha256,'Projection modified original evidence')
    return logical


@contextmanager
def forbid_fits_and_commands():
    """Runtime tripwire while authenticating trusted frozen states, not a sandbox."""
    from . import budgeted_selection as b,semantic_selection as s
    from .model import SpeedupPredictor
    from .ranking import SpeedupRanker
    from .feasible_benefit import FeasibleBenefitPredictor
    from .feasibility_selection import FeasibilitySelectionPredictor
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBRegressor,XGBClassifier,XGBRanker
    def denied(*a,**k):raise AssertionError('No fitting or external command permitted in protocol bridge')
    with ExitStack() as stack:
        for cls in (SpeedupPredictor,SpeedupRanker,b.NormalizedSpeedupPredictor,b.HardwareSurrogate,
                    s.SemanticHardwareSurrogate,FeasibleBenefitPredictor,FeasibilitySelectionPredictor,
                    GaussianProcessRegressor,StandardScaler,XGBRegressor,XGBClassifier,XGBRanker):
            stack.enter_context(patch.object(cls,'fit',denied))
        for name in ('subprocess.run','subprocess.Popen','os.system'):
            stack.enter_context(patch(name,denied))
        yield


def authenticate_model_metadata():
    pool=identity.load_public_pool(ROOT)
    folder=ROOT/MODELS;manifest_path=folder/'artifact-manifest.json'
    require(sha(manifest_path)==MODEL_MANIFEST_SHA and
        manifest_path.with_name(manifest_path.name+'.sha256').read_text().strip()==MODEL_MANIFEST_SHA,
        'Frozen model manifest changed')
    manifest=json.loads(manifest_path.read_text())
    for name,expected in manifest.items():
        path=(folder/name).resolve()
        require(path.is_relative_to(folder) and sha(path)==expected,'Frozen model artifact changed: '+name)
    record=json.loads((folder/'model-preparation.json').read_text())
    require(record['status']=='zero_label_models_complete_not_released' and record['model_fit_calls']==31 and
        record['target_outcomes_read']==record['new_pool_labels']==record['native_jobs']==0 and
        record['candidate_dispatch_enabled'] is False and record['measurement_authorization'] is False,
        'Model preparation is not a release')
    current=dict(python=platform.python_version(),packages={name:importlib.metadata.version(name) for name in record['dependencies']['packages']})
    require(current==record['dependencies'],'Frozen model dependencies changed')
    for name,expected in record['source_bindings'].items():require(sha(ROOT/name)==expected,'Frozen input/source changed: '+name)
    public=json.loads((folder/'inputs/public12.json').read_text())
    history=json.loads((folder/'inputs/history28.json').read_text())
    require(len(public)==12 and [r['candidate_id'] for r in public]==list(pool.ids) and len(history)==28 and
        digest(public)==record['public_rows_digest'] and digest(history)==record['training_rows_digest'], 'Bound public/history drift')
    return pool,record,public,history


def authenticate_zero_paid_models(public,history):
    """Recompute115 initial records; saved31 models only, no fit or provider."""
    start=time.monotonic_ns()
    import joblib
    from . import joint_hardware as j,finite_selection as f
    from scripts import freeze_md5_historical28_models as fixed
    folder=ROOT/MODELS
    read=lambda relative:json.loads((folder/relative).read_text())
    with forbid_fits_and_commands():
        semantic=joblib.load(folder/'semantic/model.joblib')
        semantic_predictions=semantic.predict(public)
        require(digest(semantic_predictions)==digest(read('semantic/predictions.json')) and
            digest(semantic.snapshot())==digest(read('semantic/snapshot.json')),'Saved semantic state differs')
        posterior=j.JointHardwarePosterior.from_fitted(semantic,history,public)
        require(digest(posterior.snapshot())==digest(read('joint/initial.json')),'Saved joint state differs')
        orders=[]
        for seed in range(5):
            predictions={}
            for name in ('raw','ranking','normalized','hardware','utility','feasibility'):
                model=joblib.load(folder/'models'/f'seed{seed}'/name/'model.joblib')
                values=model.predict(public,area_cap=64) if name in ('utility','feasibility') else model.predict(public)
                require(digest(values)==digest(read(f'models/seed{seed}/{name}/predictions.json')),'Saved model prediction differs')
                predictions[name]=values
            policies=read('model-preparation.json')['policies']
            orders.extend(fixed.initial_controls(public,history,predictions,semantic_predictions,seed,policies))
            draws,metadata=f.normal_draws(seed)
            require(digest(dict(normals=draws.tolist(),metadata=metadata))==digest(read(f'fantasies/seed{seed}.json')),
                'Frozen fantasy table differs')
            for policy in f.POLICIES:
                for budget in (1,2,3):
                    orders.append(fixed.finite_initial(public,history,posterior,policy=policy,seed=seed,budget=budget))
        require(len(orders)==115 and digest(orders)==digest(read('initial-orders.json')),
            'Frozen initial policy records differ')
        require(not posterior.observed_ids and not posterior.conditioned_ids,'Paid target state must stay empty')
    end=time.monotonic_ns()
    return dict(status='115_zero_paid_initial_records_exact',saved_models_loaded=31,model_fits=0,
        authentication_host_scope='Saved-model load, prediction, joint/fantasy and115 initial proof authentication; excludes earlier fitting and all native work.',
        authentication_monotonic_start_ns=start,authentication_monotonic_end_ns=end,
        authentication_host_seconds=(end-start)/1e9,
        initial_records=115,target_outcomes_read=0,paid_target_queries=0,native_jobs=0,
        initial_records_digest=digest(orders),realized_trajectories=False,
        limitation='Initial-state authentication only; no real paid dynamic refit or conditional branch executed.')


def protocol(context,remap,model_record,authentication):
    return dict(schema='isaforge-md5-disabled-native-evaluation-protocol-v1',status='incomplete_disabled_bridge_no_go',
        engineering_gaps=list(ENGINEERING_GAPS),
        candidate_dispatch_enabled=False,measurement_authorization=False,hardware_runtime_release=False,
        authenticated_native_plan=False,model_fits=0,target_outcomes_read=0,native_jobs=0,
        declared_context=context,id_remap=remap,model_manifest_sha256=MODEL_MANIFEST_SHA,
        model_preparation_path=str(MODELS),model_logical_namespace=model_record['logical_public_namespace'],
        initial_model_authentication=authentication,
        evaluator_boundary=dict(hard_gate='DisabledBridge.evaluate always raises DispatchDisabled before any evaluator work.',
            required_future_sequence=['authenticate separate pushed/root-approved release and actual native plan/remap',
                'hold one exclusive evaluator lock through prefix validation, proof sealing, durable reservation and terminal audit',
                'reconstruct exact own attempted prefix and successful verified prefix from immutable original evidence',
                'recompute policy choice/state with frozen models and appropriate update semantics',
                'seal identity/formula/exact assembly/source/model/seed/horizon/prefix/acquisition proof',
                'reserve and charge the unique candidate before any compiler or evaluator call',
                'preserve complete original native result, ledger, IDs, context, artifacts and timers before derived logical projection'],
            old_pool_wrappers='Never use old authenticate_discovery/baseline_public/freeze_pool to authorize this roster.'),
        paid_update_contract=dict(dynamic_factories=DYNAMIC_FACTORIES,fixed_conditioner=FIXED_CONDITIONER,
            dynamic='Only this policy/seed/horizon verified paid observations append to exact28 history; unchanged factory refits.',
            fixed='Clone the shared frozen initial posterior and condition sequentially on that session verified paid prefix; never refit preprocessing/kernel.',
            other='Frozen fitted parameters; incumbent-dependent scores recomputed from own paid incumbent.',
            current_support='Zero-paid real reconstruction authenticated. Nonempty paid paths run only with explicitly marked injected synthetic factories/conditioners.'),
        hardware_protocol=dict(isa='Unchanged archived RV32I/ILP32 compiler, linked helper ABI, sources and tool identities; verify actual plan before release.',
            ram_bytes=8192,program_limit=6400,stack_floor=6528,
            baseline=['reuse only byte/hash authenticated original baseline and three-seed integrated hardware evidence',
                'guard negative controls; fixed-input self-check, no observed stack/guard violation, baseline program fits partition'],
            candidate=['exact emitted assembly hash; assembler/ISA/relocation/lowering acceptance remains to be established',
                'integer/PCPI datapath oracle and recorded-input whole-program self-check',
                'stock firmware unchanged on extension; custom firmware rejects on unextended processor',
                'exact dynamic custom execution counts and memory/stack/guard observations',
                'complete integrated SoC area and device-fit, not isolated datapath area',
                'Complete recorded metrics for route seeds1,2,3; candidate feasibility separately requires added LUT4<=64, minimum Fmax>=12MHz, internal timing and device passes; verified infeasible measurements remain observations'],
            acceptance=dict(primary_added_lut4_cap=64,clock_floor_mhz=12.,route_seeds=[1,2,3]),
            pending=True),
        chronology=dict(live=dict(policy='fixed_joint_lookahead',seed=0,planned_budget=3),
            rule='At most12 unique attempts: three charged live queries, seal completeB3 trace, then nine remaining candidates in frozen roster order.',
            known_failures='Consume their slots; continue only after independently classified terminal failure and complete durable duration/evidence seals; no numerical updates.',
            unknowns='Infrastructure/timeout/interruption/ambiguous seals stop. Preserve reservation/partial artifacts and charge; explicit root recovery review, no automatic resume.',
            retries=0,replacements=0),
        comparison=dict(policies=17,seeds=[0,1,2,3,4],seeds_dependent=True,area_caps=[64],budgets=[1,2,3],
            finite='Independently plannedB1/B2/B3 terminal runs distinct fromB3 prefix curves.',
            accounting='Each cooperative replay sees only own requested charged prefix; failures charged. Not85 independent native campaigns or equal elapsed-time experiments.',
            cost_scopes=['all historical label attempts including exclusions/failures','baseline/qualification/calibration',
                'initial fits','initial predictions/proof authentication','paid refits/conditioning/acquisition',
                'native commands and attempt ledger','CLI/query/whole-collection observers','offline replay'],
            cost_rule='Retain original native durations before projection; overlapping scopes never summed. Model/history cost not free.',
            oracle='Restricted12 pool only; unresolved outcomes censor full-pool reference, making regret a lower bound.'),
        remaining_gates=['independent review of this disabled bridge and complete protocol/source bindings',
            'actual native plan, evaluator and tool/input/baseline authentication matching declared context/remap',
            'real paid-prefix reconstruction and locked evaluator/ledger integration, tested before enabling',
            'separate root-approved/pushed release and explicit native measurement authorization'],
        limitations=['Declaration is not hardware/runtime acceptance or collection readiness.',
            'Consumed-workload candidate/family-heldout development, not unseen-workload confirmation or a model win.',
            'Python callbacks/protocol checks are cooperative, not an OS sandbox.'])
