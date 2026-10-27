"""Fake-only MD5 identity/prefix controller; no models, release or native path.

Injected fake scoring is trusted cooperative Python, not a security sandbox.
Only public identity evidence is loaded. Fake responses are caller-supplied
synthetic values and may be journaled only in fresh system-temporary folders.
There is deliberately no CLI, native-root/toolchain argument or model import.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

REPOSITORY = Path(__file__).resolve().parents[1]
PREREG = Path('results/2026-10-26-md5-candidate-heldout-prereg')
V1 = PREREG/'controller-preparation-v1'
ERRATUM = PREREG/'controller-preparation-v1-erratum-2026-10-26/erratum.json'
CERTS = PREREG/'offline-certificates-v1'
V1_SHA = '0a4997edbdb9db2d8fd612dd6ccee9520830467c5421043a6df3d13d8ade672e'
V1_MANIFEST_SHA = 'e6479e3b4f2120e93826e165ba8bbc8cfe07f5782614275389f023668d488d1b'
ERRATUM_SHA = 'f6a2f4b74a658a8916b15cdfbf4aee74e9e40a50a7bd5d08c171200ace7a68e7'
LIVE = ('fixed_joint_lookahead',0,3)


def require(condition,message):
    if not condition: raise ValueError(message)


def pack(value):
    return json.dumps(value,sort_keys=True,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(pack(value)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class PublicPool:
    """Immutable serialized identities; preparation namespace is NOT native context."""
    rows: tuple[bytes,...]
    logical_namespace: str
    archived_hardware_context: str
    policies: tuple[str,...]
    bindings: tuple[tuple[Path,str],...]

    def validate(self):
        require(len(self.rows)==12,'Exactly twelve public identities required')
        rows=[json.loads(row) for row in self.rows]
        for field in ('name','formula','archived_candidate_id','preparation_candidate_id'):
            require(len({r[field] for r in rows})==12,'Non-bijective public '+field)
        require(self.logical_namespace!=self.archived_hardware_context,'Logical namespace is not native context')
        for row in rows:
            require(row['archived_context_id']==self.archived_hardware_context and
                row['preparation_context_id']==self.logical_namespace and
                row['archived_candidate_id']==digest([self.archived_hardware_context,row['formula']]) and
                row['preparation_candidate_id']==digest([self.logical_namespace,row['formula']]),'Invalid identity remap')
            assembly=[value for path,value in self.bindings if path.as_posix().endswith(row['assembly_path'])]
            require(len(assembly)==1 and assembly[0]==row['assembly_sha256'],'Assembly identity binding differs')
        for path,expected in self.bindings:
            require(sha(path)==expected,'Public/source binding changed: '+str(path))
        return rows

    @property
    def ids(self):
        return tuple(r['preparation_candidate_id'] for r in self.validate())

    def entry(self,identity):
        rows=self.validate()
        require(identity in self.ids,'Unknown public identity')
        return next(r for r in rows if r['preparation_candidate_id']==identity)


def load_public_pool(repository=REPOSITORY):
    """Identity-only saved evidence read; never candidate outcomes or old wrappers."""
    repository=Path(repository).resolve();bound={}
    def read(relative,expected=None):
        path=repository/relative;actual=sha(path)
        require(expected is None or actual==expected,'Pinned public evidence changed')
        bound[path]=actual
        return json.loads(path.read_text())
    contract=read(V1/'controller-contract.json',V1_SHA)
    manifest=read(V1/'artifact-manifest.json',V1_MANIFEST_SHA)
    require(manifest['controller-contract.json']==V1_SHA,'V1 manifest mismatch')
    for name,expected in manifest.items():
        require(Path(name).name==name,'Manifest entry escapes preparation directory')
        path=repository/V1/name
        require(sha(path)==expected,'Declared preparation artifact changed');bound[path]=expected
    erratum=read(ERRATUM,ERRATUM_SHA)
    require(erratum['binds']['controller_contract_sha256']==V1_SHA and
        erratum['binds']['controller_manifest_sha256']==V1_MANIFEST_SHA and
        erratum['scope_adoption']['live_policy']==LIVE[0] and
        erratum['scope_adoption']['live_seed']==0 and erratum['scope_adoption']['live_budget']==3 and
        erratum['scope_adoption']['evaluation_area_delta_lut4']==64 and
        erratum['scope_adoption']['clock_floor_mhz']==12. and
        erratum['policy_update_semantics']['policy_code_changes'] is False,'Wrong reviewed erratum')
    for relative,expected in ((V1/'controller-contract.json',V1_SHA),
                             (V1/'artifact-manifest.json',V1_MANIFEST_SHA),(ERRATUM,ERRATUM_SHA)):
        path=repository/Path(str(relative)+'.sha256')
        require(path.read_text().strip()==expected,'Public SHA sidecar mismatch');bound[path]=sha(path)
    require(contract['dispatch'] is False and contract['candidate_dispatch_enabled'] is False and
        contract['model_artifacts_created'] is False and contract['measurement_authorization'] is False and
        contract['new_pool_labels']==0,'Preparation is not an authorizing release')
    roster=read(PREREG/'roster.json',contract['identity_basis']['roster_file_sha256'])
    certificates=read(CERTS/'certificates.json',contract['identity_basis']['certificates_file_sha256'])
    remap=read(V1/'id-remap.json',manifest['id-remap.json'])
    require(remap==contract['id_remap'] and len(roster)==len(remap)==len(certificates['certificates'])==12,
        'Ordered twelve-entry remap required')
    for row,mapping,certificate in zip(roster,remap,certificates['certificates']):
        require(all(row[k]==mapping[k]==certificate[k] for k in ('name','formula')) and
            mapping['archived_candidate_id']==certificate['candidate_id'] and
            mapping['assembly_path']==str(CERTS/certificate['assembly']) and
            mapping['assembly_sha256']==certificate['assembly_sha256'],'Formula/certificate mapping changed')
        path=repository/mapping['assembly_path']
        require(path.parent==repository/CERTS and path.name==row['name']+'.S' and
            sha(path)==mapping['assembly_sha256'],'Emitted assembly changed');bound[path]=sha(path)
    for name,expected in contract['identity_basis']['recipe_source_sha256'].items():
        require((name.startswith(('scripts/','isaforge/')) and name.endswith('.py')) or name=='pyproject.toml',
            'Only recipe source files may be authenticated')
        path=repository/name;require(sha(path)==expected,'Recipe source changed');bound[path]=expected
    bound[Path(__file__).resolve()]=sha(Path(__file__).resolve())
    pool=PublicPool(tuple(pack(r) for r in remap),contract['preparation_context_id'],
        contract['identity_basis']['archived_hardware_context_id'],
        tuple(r['policy'] for r in contract['policies']),tuple(sorted(bound.items())))
    pool.validate()
    return pool


@dataclass(frozen=True)
class Session:
    policy: str
    seed: int
    horizon: int
    endpoint_kind: str='planned'

    def validate(self,pool):
        require(self.policy in pool.policies and type(self.seed) is int and self.seed in range(5), 'Unknown policy/seed')
        require(type(self.horizon) is int and self.horizon in (1,2,3),'Unknown horizon')
        finite=self.policy.startswith('fixed_joint_')
        require(self.endpoint_kind==('planned' if finite else 'b3-prefix') and
            (finite or self.horizon==3),'Independent finite horizons differ from B3 prefixes')


class TemporaryJournal:
    """Exclusive append-only fake fixture records with fsync and hash rechecks."""
    def __init__(self,path):
        self.path=Path(path).resolve();self._hashes={}
        require(self.path.is_relative_to(Path(tempfile.gettempdir()).resolve()) and
            not self.path.is_relative_to(REPOSITORY) and not self.path.exists(),
            'Fake journals require a fresh system-temporary path outside the repository')
        self.path.mkdir(parents=True)

    def validate(self):
        require({p.name for p in self.path.iterdir()}==set(self._hashes),'Unexpected/missing journal entry')
        require(all(sha(self.path/name)==value for name,value in self._hashes.items()),'Journal seal changed')

    def seal(self,name,value):
        self.validate();path=self.path/name
        require(Path(name).name==name and name not in self._hashes,'Append-only journal entry required')
        with path.open('xb') as stream:
            stream.write(pack(value)+b'\n');stream.flush();os.fsync(stream.fileno())
        descriptor=os.open(self.path,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        self._hashes[name]=sha(path)
        self.validate()


class FakeScorer:
    """Scripted synthetic acquisition checker; never a fitted policy/model."""
    fake_only=True
    def __init__(self,ordered_ids): self.order=tuple(ordered_ids)
    def acquire(self,public_ids,paid,session):
        remaining=[i for i in self.order if i in public_ids and i not in paid]
        require(remaining,'No scripted fake acquisition remains')
        return dict(candidate_id=remaining[0],fake_score=digest([self.order,list(paid),session]))
    def check(self,acquisition,public_ids,paid,session):
        return acquisition==self.acquire(public_ids,paid,session)


@dataclass(frozen=True)
class FakeResponse:
    """Synthetic tokens only; deliberately no measured-cycle/hardware fields."""
    status: str='verified'
    synthetic_value: str='synthetic-only'
    known_failure_evidence: str=''
    cost_complete: bool=True

    def __post_init__(self):
        require(type(self.cost_complete) is bool and isinstance(self.synthetic_value,str) and
            self.synthetic_value.startswith('synthetic'),'Only explicitly synthetic response tokens allowed')


class FakeEvaluator:
    """Only an attached controller can request one reserved synthetic response.

    Private attributes are a cooperative Python boundary, not tamper-proof ACLs.
    No callable native evaluator may be injected or adapted through this class.
    """
    def __init__(self,responses):
        require(all(type(v) is FakeResponse for v in responses.values()),'Synthetic responses only')
        self.__responses=copy.deepcopy(responses);self.__guard=None;self.__permit=None;self.calls=[]
    def _attach(self,guard,permit):
        require(self.__guard is None,'Fake evaluator already belongs to another session')
        self.__guard,self.__permit=guard,permit
    def evaluate(self,identity,proof,*,permit=None):
        require(self.__guard is not None and permit is self.__permit,'Unreserved direct evaluator call forbidden')
        self.__guard(identity,proof)
        self.calls.append(identity)
        require(identity in self.__responses,'No synthetic response supplied')
        return copy.deepcopy(self.__responses[identity])


class FakeOnlyController:
    """One isolated paid-prefix provider; collection mode adds the exact3+9 gate.

    Separate instances are mandatory per policy/seed/horizon. Neither providers
    nor injected scorers receive the evaluator's response store. Collection's
    reference records never enter the live policy's prefix or fake numeric state.
    """
    fake_only=True
    candidate_dispatch_enabled=False
    measurement_authorization=False
    model_artifacts_created=False

    def __init__(self,pool,session,journal,scorer,evaluator,*,collection=False):
        pool.validate();session.validate(pool)
        require(type(evaluator) is FakeEvaluator and getattr(scorer,'fake_only',False) is True,
            'Only injected fake evaluator/scoring checker allowed')
        require(not collection or (session.policy,session.seed,session.horizon)==LIVE,'Frozen live pilot required')
        self.pool,self.session,self.journal,self.scorer=pool,session,journal,scorer
        self.collection=collection;self.evaluator=evaluator
        self._records=();self._charges=();self._stopped=False;self._pending=None;self._permit=object();self._live_hash=None
        self.events=[]
        self._session=dict(policy=session.policy,seed=session.seed,horizon=session.horizon,
            endpoint_kind=session.endpoint_kind,logical_namespace=pool.logical_namespace,
            archived_hardware_context=pool.archived_hardware_context,
            public_binding_sha256=digest([(str(path),value) for path,value in pool.bindings]),
            fake_only=True,collection=collection)
        self._session_id=digest(self._session)
        self._scope_frozen=pack(self._session)
        self.journal.seal('session.json',self._session)
        evaluator._attach(self._authorize,self._permit)

    @property
    def charged_ids(self): return self._charges
    @property
    def _completed_ids(self): return tuple(r['candidate_id'] for r in map(json.loads,self._records))
    @property
    def stopped(self): return self._stopped
    @property
    def paid_prefix(self):
        records=[json.loads(r) for r in self._records]
        return copy.deepcopy(records[:3] if self.collection else records)
    @property
    def successful_paid_prefix(self): return [r for r in self.paid_prefix if r['status']=='verified']
    @property
    def numeric_updates(self): return len(self.successful_paid_prefix)

    def _boundary(self):
        require(not self._stopped,'Stopped fixture; no retry or automatic recovery')
        try:
            require(pack(self._session)==self._scope_frozen and
                (self.session.policy,self.session.seed,self.session.horizon,self.session.endpoint_kind,
                 self.collection,self.pool.logical_namespace,self.pool.archived_hardware_context)==
                (self._session['policy'],self._session['seed'],self._session['horizon'],self._session['endpoint_kind'],
                 self._session['collection'],self._session['logical_namespace'],self._session['archived_hardware_context']),
                'Immutable session scope changed')
            self.pool.validate();self.journal.validate()
        except BaseException:
            self._stopped=True
            raise

    def next_proof(self):
        self._boundary();index=len(self._records)
        require(index<(12 if self.collection else self.session.horizon),'Charged budget exhausted')
        mode='oracle-reference' if self.collection and index>=3 else 'adaptive'
        if mode=='adaptive':
            acquisition=self.scorer.acquire(self.pool.ids,self._completed_ids,self._session)
            identity=acquisition['candidate_id']
        else:
            require(self._live_hash is not None,'Complete sealed live trace required')
            identity=next(i for i in self.pool.ids if i not in self._completed_ids);acquisition=None
        if identity not in self.pool.ids or identity in self._completed_ids:
            self._stopped=True
            raise ValueError('Controller requires a declared uncharged identity')
        row=self.pool.entry(identity)
        return dict(session_id=self._session_id,session=copy.deepcopy(self._session),mode=mode,
            index=index,candidate_id=identity,archived_candidate_id=row['archived_candidate_id'],
            formula=row['formula'],assembly_sha256=row['assembly_sha256'],
            attempted_ids_before=list(self._completed_ids),successful_paid_ids=[r['candidate_id'] for r in self.successful_paid_prefix],
            paid_prefix_sha256=digest(self.paid_prefix),numeric_updates=self.numeric_updates,
            remaining_queries=max(0,self.session.horizon-index),live_trace_sha256=self._live_hash,
            acquisition=acquisition,fake_only=True)

    def _check(self,identity,proof):
        # Mandatory bindings are independently compared before the injected checker.
        expected=self.next_proof()
        require(identity==expected['candidate_id'] and
            {k:v for k,v in proof.items() if k!='acquisition'}==
            {k:v for k,v in expected.items() if k!='acquisition'},'Mandatory identity/prefix/horizon/assembly proof differs')
        if expected['mode']=='adaptive':
            require(self.scorer.check(proof['acquisition'],self.pool.ids,self._completed_ids,self._session),
                'Injected fake acquisition proof rejected')
        else: require(proof['acquisition'] is None,'Reference cannot carry acquisition proof')
        self._boundary()

    def _authorize(self,identity,proof):
        require(self._pending is not None and self._pending==(identity,digest(proof)),'No exact pending reservation')
        self._check(identity,proof)
        self.events.append('fake-evaluation')
        self._pending=None  # One evaluation per permit/reservation.

    def request(self,identity,proof):
        """The only paid provider; never exposes unrequested/store-wide responses."""
        self._boundary()
        try:
            self._check(identity,proof)
            index=len(self._records);stem=f'{index:02d}'
            self.journal.seal(stem+'-proof.json',proof);self.events.append('proof')
            reservation=dict(candidate_id=identity,proof_sha256=digest(proof),session_id=self._session_id,
                charged_slot=index+1,assembly_sha256=proof['assembly_sha256'],fake_only=True)
            self.journal.seal(stem+'-reservation.json',reservation);self.events.append('reservation')
            self._charges+=(identity,)
            self._pending=(identity,digest(proof))
            response=self.evaluator.evaluate(identity,copy.deepcopy(proof),permit=self._permit)
            require(response.cost_complete and (response.status=='verified' or
                (response.status=='known_failure' and bool(response.known_failure_evidence))),
                'Infrastructure/interrupted/ambiguous outcome: preserve reservation and stop')
            record=dict(candidate_id=identity,status=response.status,synthetic_value=response.synthetic_value
                if response.status=='verified' else None,known_failure_evidence=response.known_failure_evidence,
                cost_scope='synthetic fixture only',fake_only=True)
            self.journal.seal(stem+'-terminal.json',record);self.events.append('terminal')
            self._records+= (pack(record),)
            if self.collection and len(self._records)==3:
                trace=dict(session_id=self._session_id,attempted_ids=list(self.charged_ids),
                    paid_prefix=self.paid_prefix,numeric_updates=self.numeric_updates,remaining_outcomes_exist=False,fake_only=True)
                self.journal.seal('live-trace.json',trace);self._live_hash=digest(trace)
            self._boundary()
            return copy.deepcopy(record)
        except BaseException:
            self._stopped=True;self._pending=None
            raise

    def prefix_endpoint(self,budget):
        require(type(budget) is int and 1<=budget<=len(self.paid_prefix),'Unavailable prefix endpoint')
        return dict(session_id=self._session_id,planned_horizon=self.session.horizon,
            endpoint_kind='b3-prefix' if self.session.horizon==3 and budget<3 else self.session.endpoint_kind,
            budget=budget,paid_prefix=copy.deepcopy(self.paid_prefix[:budget]),fake_only=True)
