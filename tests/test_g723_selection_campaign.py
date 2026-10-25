"""Synthetic controller contracts only; no estimator fits or native jobs."""
import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from isaforge import codesign as c
from scripts import g723_selection_campaign as t


class FakeModel:
    def fit(self,training):
        self.training = copy.deepcopy(training)
        return self
    def predict(self,public):
        return [dict(candidate_id=r['candidate_id'],fake=True) for r in public]
    def snapshot(self):
        return dict(training_ids=[r['candidate_id'] for r in self.training],training_rows_sha256=c.digest(self.training),
            model_state_sha256=c.digest(self.training))


class FakePosterior:
    def __init__(self,training,public,paid=()):
        self.training,self.public,self.paid = copy.deepcopy(training),copy.deepcopy(public),copy.deepcopy(list(paid))
    def clone(self):
        return type(self)(self.training,self.public,self.paid)
    def snapshot(self):
        result = dict(initial_training_ids=[r['candidate_id'] for r in self.training],
            paid_ids=[r['candidate_id'] for r in self.paid],paid_outcomes_sha256=c.digest(self.paid))
        result['posterior_state_sha256'] = c.digest(result)
        return result
    def predict(self):
        return [dict(candidate_id=r['candidate_id'],fake=True) for r in self.public]
    def joint(self):
        return dict(candidate_ids=[r['candidate_id'] for r in self.public],outputs={
            'fake':dict(mean=np.zeros(len(self.public)),covariance=np.eye(len(self.public)),
                observation_covariance=2*np.eye(len(self.public)))})
    def condition(self,outcome,*,queried_id):
        assert queried_id == outcome['candidate_id']
        return type(self)(self.training,self.public,[*self.paid,outcome])


@pytest.fixture
def case():
    root = c.ROOT/'results/2026-10-21-blind-campaign/targets/beebs-ndes'
    audited = c.unseal(root/'audit.json')
    public = copy.deepcopy(audited['public'])
    training = c.unseal(c.ROOT/'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes/controls11/model/history.json')
    return dict(public=public,history=training,posterior=FakePosterior(training,public),
        fantasies={seed:dict(metadata={'seed':seed,'fixed':True}) for seed in range(5)},
        labels={row['candidate_id']:row for row in audited['outcomes']})


@pytest.fixture
def fake_search(monkeypatch):
    control = dict(tamper=None,unsealed=False,budgets=[],mismatch=False)
    def search(public,training,provider,*,posterior,policy,area_cap,clock_mhz,seed,budget,on_acquire):
        control['budgets'].append(budget)
        state = posterior.clone()
        released,proofs,curve = [],[],[]
        # Deliberately change choice with planned horizon: truncation is detectable.
        ordered = public[budget:]+public[:budget]
        for candidate in ordered[:budget]:
            snapshot = state.snapshot()
            proof = dict(event=dict(policy=policy,candidate_id=candidate['candidate_id'],planned_budget=budget,
                remaining_queries=budget-len(released),charged_before_query=len(released),
                attempted_ids_before_query=list(released),paid_target_ids_before_query=[r['candidate_id'] for r in state.paid],
                posterior_state_sha256=snapshot['posterior_state_sha256']),posterior_snapshot=snapshot,
                successful_paid_ids=[r['candidate_id'] for r in state.paid],
                initial_training_ids=[r['candidate_id'] for r in training],snapshot_sha256=c.digest(snapshot),
                fantasy_table={'seed':seed,'fixed':True})
            if control['tamper']:
                control['tamper'](proof)
            if not control['unsealed']:
                on_acquire(copy.deepcopy(proof))
            proofs.append(proof)
            outcome = provider(copy.deepcopy(public[0] if control['mismatch'] else candidate))
            released.append(candidate['candidate_id'])
            if t.b.validate_outcome(outcome,candidate):
                state = state.condition(outcome,queried_id=candidate['candidate_id'])
            curve.append(dict(budget=len(released),attempted_ids=list(released),best_speedup=1.))
        return dict(policy=policy,planned_budget=budget,curve=curve,acquisition_proofs=proofs,
            final_posterior_snapshot=state.snapshot())
    monkeypatch.setattr(t.f,'search',search)
    return control


def test_finite_query_seals_exact_successful_paid_prefix(case,fake_search):
    paid,proofs = [],[]
    def acquire(proof):
        assert proof['event']['attempted_ids_before_query'] == paid
        assert proof['successful_paid_ids'] == paid
        proofs.append(proof)
    def provider(row):
        assert len(proofs) == len(paid)+1
        assert proofs[-1]['event']['candidate_id'] == row['candidate_id']
        paid.append(row['candidate_id'])
        return case['labels'][row['candidate_id']]
    result = t.run_search(case,provider,on_acquire=acquire)
    assert len(paid) == len(set(paid)) == 3
    assert result['final_posterior_snapshot']['paid_ids'] == paid


@pytest.mark.parametrize('change',[
    lambda p:p['initial_training_ids'].append('unpaid'),
    lambda p:p['successful_paid_ids'].append('unpaid'),
    lambda p:p['posterior_snapshot'].update(paid_outcomes_sha256='unpaid'),
    lambda p:p['fantasy_table'].update(seed=4),
    lambda p:p['event'].update(remaining_queries=1),
])
def test_tampered_model_or_horizon_fails_before_provider(case,fake_search,change):
    fake_search['tamper'] = change
    calls = []
    with pytest.raises(ValueError,match='Exact sealed initial'):
        t.run_search(case,lambda row:calls.append(row))
    assert calls == []


def test_provider_rejects_a_query_without_a_preceding_proof(case,fake_search):
    fake_search['unsealed'] = True
    calls = []
    with pytest.raises(ValueError,match='Seal unique'):
        t.run_search(case,lambda row:calls.append(row))
    assert calls == []


def test_independent_horizons_are_not_truncated_b3(case,fake_search):
    results = [t.finite_search(case,lambda row:case['labels'][row['candidate_id']],policy=t.f.LOOKAHEAD,
        seed=0,area_cap=64,budget=budget) for budget in (1,2,3)]
    assert fake_search['budgets'] == [1,2,3]
    assert len({r['curve'][0]['attempted_ids'][0] for r in results}) == 3
    assert [len(r['curve']) for r in results] == [1,2,3]


def test_failed_paid_attempt_is_charged_without_gaussian_label(case,fake_search):
    first = case['public'][3]
    original = case['labels'][first['candidate_id']]
    failed = {key:copy.deepcopy(original[key]) for key in t.b.PUBLIC_KEYS}
    failed.update(status='failed',failure_class='infrastructure_unknown',reference_censored=True,
        measurement_seconds=1.,error='Synthetic infrastructure failure')
    paid = []
    def provider(row):
        paid.append(row['candidate_id'])
        return failed if row['candidate_id'] == first['candidate_id'] else case['labels'][row['candidate_id']]
    result = t.run_search(case,provider)
    assert len(paid) == 3
    assert result['final_posterior_snapshot']['paid_ids'] == paid[1:]


def test_old_helper_registration_restores_after_nested_error():
    original = t.old.w
    with pytest.raises(RuntimeError):
        with t._old_workload():
            assert t.old.w is t.w
            with t._old_workload():
                raise RuntimeError('restore')
    assert t.old.w is original


@pytest.fixture
def release_gate(tmp_path,monkeypatch):
    monkeypatch.setattr(t,'ROOT',tmp_path)
    prereg,native = tmp_path/'prereg',tmp_path/'native'
    target = dict(context_id='context')
    c.seal(prereg/'cohort.json',dict(targets={t.w.GROUP:target}))
    c.seal(prereg/'manifest.json',{})
    c.seal(prereg/'targets'/t.w.GROUP/'baseline/evaluation-protocol.json',{})
    released = dict(schema=t.w.PROTOCOL['schema']+'-release',manifest_sha256=c.sha(prereg/'manifest.json'),
        cohort_sha256=c.sha(prereg/'cohort.json'),context_id='context',preregistration_root='prereg',
        evaluation_protocol_sha256=c.sha(prereg/'targets'/t.w.GROUP/'baseline/evaluation-protocol.json'),
        pushed_remote_head='0'*40,prelabel_commit='0'*40,pushed_branch='ai-guided-ml',remote='origin',
        zero_candidate_attempts=True,target_labels_observed=0)
    c.seal(native/'release.json',released)
    calls = []
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:dict(context_id='context'))
    def authenticate(root):
        calls.append('complete models')
        return {},t.w.GROUP,target,{}
    monkeypatch.setattr(t,'authenticate',authenticate)
    monkeypatch.setattr(t.prior,'check_git_checkpoint',lambda *args:calls.append('git blobs'))
    monkeypatch.setattr(t,'check_baseline',lambda *args:calls.append('baseline'))
    def remote(*args,**kwargs):
        calls.append('actual remote')
        return SimpleNamespace(stdout='0'*40+'\trefs/heads/ai-guided-ml\n')
    monkeypatch.setattr(t.subprocess,'run',remote)
    return dict(native=native,prereg=prereg,record=released,calls=calls)


def test_every_dispatch_rechecks_complete_models_git_and_actual_remote(release_gate):
    f = release_gate
    assert t.check_native_release(f['native']) == f['record']
    assert t.check_native_release(f['native']) == f['record']
    assert f['calls'] == ['complete models','git blobs','baseline','actual remote']*2


def test_metadata_only_release_cannot_bypass_missing_model_package(release_gate,monkeypatch):
    def missing(root): raise ValueError('Missing complete models')
    monkeypatch.setattr(t,'authenticate',missing)
    with pytest.raises(ValueError,match='Missing complete models'):
        t.check_native_release(release_gate['native'])
    assert release_gate['calls'] == []


def test_asserted_pushed_head_cannot_bypass_actual_remote(release_gate,monkeypatch):
    monkeypatch.setattr(t.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(stdout='1'*40+'\trefs/heads/ai-guided-ml\n'))
    with pytest.raises(ValueError,match='Actual origin'):
        t.check_native_release(release_gate['native'])
    assert release_gate['calls'] == ['complete models','git blobs','baseline']


def test_released_evaluator_cannot_reach_native_before_complete_release(tmp_path,monkeypatch):
    evaluator = object.__new__(t.ReleasedEvaluator)
    evaluator.root = tmp_path
    called = []
    monkeypatch.setattr(t.w,'check_opportunity',lambda root:called.append('opportunity'))
    def reject(root): raise ValueError('No complete release')
    monkeypatch.setattr(t,'check_native_release',reject)
    monkeypatch.setattr(t.g.Evaluator,'measure',lambda self,name:called.append('native'))
    with pytest.raises(ValueError,match='No complete release'):
        evaluator.measure('candidate_00')
    assert called == ['opportunity']
    evaluator.measure('baseline')
    assert called == ['opportunity','opportunity','native']


@pytest.fixture
def collector(tmp_path,monkeypatch,case,fake_search):
    native,prereg,output = tmp_path/'native',tmp_path/'prereg',tmp_path/'collection'
    native.mkdir(); prereg.mkdir()
    target = dict(original_root=str(native),native_order=[f'candidate_{i:02d}' for i in range(12)])
    cohort = dict(qualification={'path':'qualification'},python_executable='python')
    c.seal(prereg/'manifest.json',{})
    released = tmp_path/'release.json'; c.seal(released,{})
    monkeypatch.setattr(t,'authenticate',lambda root:(cohort,t.w.GROUP,target,case))
    monkeypatch.setattr(t.prior,'_zero',lambda root:None)
    monkeypatch.setattr(t,'check_baseline',lambda *args:None)
    monkeypatch.setattr(t,'checked_release',lambda *args,**kwargs:{})
    monkeypatch.setattr(t,'check_native_release',lambda root:None)
    seen,calls = [],[]
    control = dict(interrupt=None)
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        index = len(calls)
        calls.append(metadata['candidate_id'])
        assert argv[1:3] == [t.SOURCE,'measure']
        assert (output/'live.json').exists() == (index >= 3)
        if index < 3:
            proof = c.unseal(output/'acquisitions'/f'{index:02d}.json')
            assert proof['event']['candidate_id'] == metadata['candidate_id']
            assert proof['successful_paid_ids'] == seen
        if index == control['interrupt']:
            raise KeyboardInterrupt('No retry')
        seen.append(metadata['candidate_id'])
        c.seal(native/'outer-timing'/f'{index:03d}-measure.json',dict(command='measure'))
        c.seal(native/'attempt-ledger'/(metadata['native_name']+'.json'),dict(status='success'))
        return dict(status='success',returncode=0)
    monkeypatch.setattr(t.observed,'run',observe)
    monkeypatch.setattr(t,'audit',lambda root:dict(charged_candidate_attempts=len(seen),
        outcomes=[case['labels'][i] for i in seen],candidate_wall_seconds_complete=True))
    return dict(native=native,prereg=prereg,output=output,release=released,calls=calls,seen=seen,control=control,case=case)


def test_live_trace_is_sealed_before_any_reference_outcome(collector):
    f = collector
    result = t.collect(f['prereg'],f['native'],f['release'],f['output'])
    trace = c.unseal(f['output']/'live.json')
    assert result['status'] == 'complete'
    assert len(set(f['calls'])) == len(f['seen']) == 12
    assert trace['attempted_ids'] == f['calls'][:3]
    assert f['calls'][3:] == [r['candidate_id'] for r in f['case']['public'] if r['candidate_id'] not in f['calls'][:3]]


def test_interruption_preserves_attempt_and_never_silently_restarts(collector):
    f = collector
    f['control']['interrupt'] = 1
    with pytest.raises(KeyboardInterrupt):
        t.collect(f['prereg'],f['native'],f['release'],f['output'])
    record = c.unseal(f['output']/'collection.json')
    assert record['status'] == 'interrupted' and record['paid_ids'] == f['calls'][:1]
    assert len(f['calls']) == 2 and record['dispatched_ids'] == f['calls'] and not (f['output']/'live.json').exists()
    assert (f['output']/'manifest.json').exists()
    with pytest.raises(ValueError,match='Fresh output'):
        t.collect(f['prereg'],f['native'],f['release'],f['output'])


def test_stable_ignores_only_declared_host_timers():
    before = dict(acquisition_host_seconds=1.,conditioning_host_seconds=2.,measurement_seconds=3.,
        proof={'posterior_state_sha256':'exact'},speedup=1.1)
    after = dict(before,acquisition_host_seconds=10.,conditioning_host_seconds=20.)
    assert t.stable(before) == t.stable(after)
    after['measurement_seconds'] += .01
    assert t.stable(before) != t.stable(after)


def make_grid(case):
    labels = case['labels']
    outer = {identity:row['measurement_seconds']+1. for identity,row in labels.items()}
    runs = []
    for policy in t.POLICIES:
        for cap in (32,64,128):
            for seed in range(5):
                for planned in ((1,2,3) if policy in t.f.POLICIES else (3,)):
                    curve = []
                    for budget in range(1,planned+1):
                        paid = [r['candidate_id'] for r in case['public'][:budget]]
                        best = max([1.]+[labels[i]['speedup'] for i in paid if t.b._feasible(labels[i],cap,12.)])
                        curve.append(dict(budget=budget,planned_budget=planned,attempted_ids=paid,best_speedup=best,
                            target_measurement_seconds=sum(labels[i]['measurement_seconds'] for i in paid),inference_seconds=0.))
                    run = dict(policy=policy,cap=cap,seed=seed,curve=curve,planned_budget=planned)
                    t.old.annotate(run,labels,outer,cap)
                    runs.append(run)
    return runs,outer


def test_seventeen_policy_endpoint_grid_and_independent_horizons(case):
    runs,_ = make_grid(case)
    endpoints = t._endpoints(case['public'],list(case['labels'].values()),runs,False)
    assert len(runs) == 345 and sum(len(r['curve']) for r in runs) == 900
    assert len(endpoints) == 180
    assert len([r for r in endpoints if r['endpoint_kind'] == 'B3-prefix']) == 153
    assert len([r for r in endpoints if r['endpoint_kind'] == 'horizon-aware-terminal']) == 27
    assert all(r['planned_budget'] == r['budget'] for r in endpoints if r['endpoint_kind'] == 'horizon-aware-terminal')
    assert all(r['dependent_seed_count'] == 5 for r in endpoints)


@pytest.mark.parametrize('mutation',[
    lambda r:r.pop(),
    lambda r:r.append(copy.deepcopy(r[-1])),
    lambda r:r[0]['curve'][0].update(best_speedup=100.),
    lambda r:r[0]['curve'][0].update(target_measurement_seconds=0.),
    lambda r:r[0]['curve'][0].update(known_infeasible_attempts=100),
    lambda r:r[0]['curve'][0].update(inference_seconds=float('inf')),
])
def test_endpoint_validation_rejects_grid_arithmetic_cost_or_classification_tampering(case,mutation):
    runs,_ = make_grid(case)
    mutation(runs)
    with pytest.raises(ValueError):
        t._endpoints(case['public'],list(case['labels'].values()),runs,False)


@pytest.fixture
def frozen(tmp_path,monkeypatch,case):
    """Exercise complete freeze/authentication plumbing with fake model objects."""
    actual = c.unseal(c.ROOT/'results/2026-10-22-twelve-source-corpus/corpus.json')
    monkeypatch.setattr(t,'ROOT',tmp_path)
    monkeypatch.setattr(t,'HISTORY',tmp_path/'history/corpus.json')
    c.seal(t.HISTORY,actual)
    monkeypatch.setattr(t,'history',lambda path:copy.deepcopy(actual))
    native,output,qualified = tmp_path/'native',tmp_path/'prereg',tmp_path/'qualified'
    qualified.mkdir(); t.prior._seal_manifest(qualified)
    qual = dict(path='qualified',manifest_sha256=c.sha(qualified/'manifest.json'))
    monkeypatch.setattr(t,'qualification',lambda *args:qual)
    public = copy.deepcopy(case['public'])
    for row in public:
        row['benchmark'] = t.w.GROUP+':fake-context'
    context = dict(context_id='fake-context',workload_group=t.w.GROUP,baseline_provenance={'fake':True})
    before = dict(workload=t.w.GROUP,pool_names=[f'candidate_{i:02d}' for i in range(12)])
    plan = dict(context_id='fake-context',source_bindings={})
    for name in t.prior.BASELINES:
        value = {'fake':name}
        if name == 'public.json': value = public
        if name == 'context.json': value = context
        if name == 'before.json': value = before
        if name == 'plan.json': value = plan
        if name == 'measurements/baseline/measurement.json':
            value = dict(name='baseline',routes=[dict(seed=seed,internal_timing_pass=True,device_fits=True) for seed in (1,2,3)],
                performance={'cycles':100},resources={'lut4_count':1})
        if name == 'evaluation-protocol.json': value = dict(pool_names=before['pool_names'])
        c.seal(native/name,value)
    c.seal(native/'opportunity.json',t.w.opportunity_gate(public))
    c.seal(native/'outer-timing/000-prepare.json',{'fake':True})
    monkeypatch.setattr(t.w,'baseline_public',lambda root:(copy.deepcopy(public),copy.deepcopy(context),copy.deepcopy(before)))
    monkeypatch.setattr(t.w,'validate_inputs',lambda root:copy.deepcopy(plan))
    monkeypatch.setattr(t.w,'check_plan',lambda value:None)
    monkeypatch.setattr(t.prior.evidence,'_calibration',lambda root:{'native_command_seconds':0.})
    monkeypatch.setattr(t,'sources',lambda plan:{'fixture-controller':'bound'})
    monkeypatch.setattr(t.semantic,'SemanticHardwareSurrogate',FakeModel)
    monkeypatch.setattr(t.j.JointHardwarePosterior,'from_fitted',lambda model,training,public:FakePosterior(training,public))
    families = {t.family(r['formula']) for r in public}
    fitting = [r for r in actual['rows'] if t.family(r['formula']) not in families]
    assert len({r['workload_group'] for r in fitting}) >= 2
    def freeze(history,features,contexts,destination,**kwargs):
        assert history == actual['rows'] and kwargs['target_workload'] == t.w.GROUP
        assert kwargs['target_labels_observed'] == 0
        c.seal(destination/'controls11/model/history.json',fitting)
        c.seal(destination/'controls11/model/predictions.json',{'complete-old-control-fixture':True})
        protocol = dict(schema=t.experiment.SCHEMA,scope='prospective source holdout',target_labels_observed=0,target_labels_read=0,
            artifacts={p.relative_to(destination).as_posix():c.sha(p) for p in destination.rglob('*') if p.is_file()},
            historical_training_ids=[r['candidate_id'] for r in fitting],
            historical_postfilter_groups=sorted({r['workload_group'] for r in fitting}),
            contexts_digest=c.digest(contexts),source_history_digest=c.digest(history),
            cost_provenance=kwargs['cost_provenance'],input_bindings=kwargs['input_bindings'])
        c.seal(destination/'protocol.json',protocol)
        return protocol
    monkeypatch.setattr(t.experiment,'freeze',freeze)
    monkeypatch.setattr(t.experiment,'authenticate',lambda folder:dict(public=public,history=fitting))
    t.freeze(native,output,qualification_path=qualified)
    return dict(output=output,native=native,history=actual,public=public,training=fitting)


def test_freeze_seals_all17_controls_initial_states_and_five_fixed_tables(frozen):
    root = frozen['output']
    cohort,group,target,case = t.authenticate(root)
    assert group == t.w.GROUP
    assert cohort['policies'] == t.OLD_POLICIES+list(t.f.POLICIES)
    assert len(cohort['policies']) == len(set(cohort['policies'])) == 17
    assert cohort['historical_costs']['successful_labels'] == 99
    assert cohort['historical_costs']['failed_attempts'] == 3
    assert cohort['historical_costs']['total_candidate_attempts'] == 102
    costs = c.unseal(root/'targets'/t.w.GROUP/'cost-provenance.json')
    assert costs['qualification_baseline']['candidate_training_labels'] == 0
    assert costs['qualification_baseline']['baseline_attempts'] == 1
    assert costs['qualification_baseline']['completed_routes'] == 3
    assert cohort['target_labels_read'] == cohort['target_labels_observed'] == 0
    assert cohort['live'] == dict(policy=t.f.LOOKAHEAD,seed=0,area_cap=64,clock_mhz=12.,budget=3)
    assert target['historical_training_ids'] == [r['candidate_id'] for r in frozen['training']]
    assert case['posterior'].snapshot() == case['joint_initial']
    for seed in range(5):
        draws,metadata = t.f.normal_draws(seed)
        assert c.unseal(root/'fantasies'/f'seed{seed}.json') == dict(normals=draws.tolist(),metadata=metadata)
    assert c.unseal(root/'targets'/t.w.GROUP/'joint/cost.json')['initial_surrogate_fits'] == 0
    with pytest.raises(ValueError,match='Fresh output'):
        t.freeze(frozen['native'],root,qualification_path=root.parent/'qualified')


@pytest.mark.parametrize('artifact',[
    'joint/initial.json','joint/joint.json','joint/marginals.json','semantic/snapshot.json',
    'selection/controls11/model/predictions.json',
])
def test_missing_complete_model_inventory_cannot_be_resealed_as_release(frozen,artifact):
    root = frozen['output']
    path = root/'targets'/t.w.GROUP/artifact
    path.unlink()
    Path(str(path)+'.sha256').unlink()
    t.prior._seal_manifest(root)
    with pytest.raises((ValueError,FileNotFoundError)):
        t.authenticate(root)


def test_resealed_draw_table_tampering_fails_exact_numeric_authentication(frozen):
    root = frozen['output']
    path = root/'fantasies/seed0.json'
    table = c.unseal(path)
    table['normals'][0][0] += 1.
    c.seal(path,table)
    cohort = c.unseal(root/'cohort.json')
    cohort['fantasy_table_sha256s']['0'] = c.sha(path)
    c.seal(root/'cohort.json',cohort)
    t.prior._seal_manifest(root)
    with pytest.raises(ValueError,match='Exact sealed settings/normal draws'):
        t.authenticate(root)


def test_resealed_joint_numeric_state_tampering_fails_exact_reconstruction(frozen):
    root = frozen['output']
    path = root/'targets'/t.w.GROUP/'joint/joint.json'
    values = c.unseal(path)
    values['outputs']['fake']['mean'][0] = 1.
    c.seal(path,values)
    cohort = c.unseal(root/'cohort.json')
    cohort['targets'][t.w.GROUP]['joint_distribution_sha256'] = c.sha(path)
    c.seal(root/'cohort.json',cohort)
    t.prior._seal_manifest(root)
    with pytest.raises(ValueError,match='Exact shared-fit joint initial'):
        t.authenticate(root)


def test_finite_provider_must_match_the_last_sealed_candidate(case,fake_search):
    fake_search['mismatch'] = True
    called = []
    with pytest.raises(ValueError,match='Seal unique chosen'):
        t.run_search(case,lambda row:called.append(row))
    assert called == []


def test_old_count_proofs_normalize_only_json_equivalent_score(tmp_path,monkeypatch):
    proof = dict(event={'score':(1.,2.),'candidate_id':'chosen'},model_state_sha256='unchanged',training_ids=['h'])
    def old_search(case,provider,*,on_acquire,**kwargs):
        on_acquire(copy.deepcopy(proof))
        return dict(acquisition_proofs=[copy.deepcopy(proof)])
    monkeypatch.setattr(t.old,'count_search',old_search)
    observed = []
    result = t.count_search({},None,policy=t.count.POLICY,seed=0,area_cap=64,on_acquire=observed.append)
    assert observed == result['acquisition_proofs']
    assert observed[0]['event']['score'] == [1.,2.]
    assert c.digest(observed[0]) == c.digest(proof)
    c.seal(tmp_path/'proof.json',observed[0])
    assert c.unseal(tmp_path/'proof.json') == observed[0]
    assert proof['event']['score'] == (1.,2.)


@pytest.fixture
def campaign(tmp_path,monkeypatch,case):
    """Pure reporting/export fixture: remapped consumed rows are synthetic labels."""
    previous = c.unseal(c.ROOT/'results/2026-10-22-twelve-source-corpus/corpus.json')
    monkeypatch.setattr(t,'ROOT',tmp_path)
    monkeypatch.setattr(t,'HISTORY',tmp_path/'history/corpus.json')
    c.seal(t.HISTORY,previous); t.prior._seal_manifest(t.HISTORY.parent)
    public,labels = [],{}
    for index,source in enumerate(case['public']):
        feature = dict(source,candidate_id=f'synthetic-g723-{index}',benchmark=t.w.GROUP+':synthetic')
        row = dict(case['labels'][source['candidate_id']],candidate_id=feature['candidate_id'],benchmark=feature['benchmark'])
        public.append(feature); labels[row['candidate_id']] = row
    fake = dict(public=public,labels=labels)
    runs,outer = make_grid(fake)
    context = dict(context_id='synthetic',workload_group=t.w.GROUP)
    audited = dict(public=public,outcomes=list(labels.values()),context_id='synthetic',attempt_collection_complete=True,
        candidate_wall_seconds_complete=True,charged_candidate_attempts=12,unattempted=[],
        candidate_wall_seconds=sum(r['measurement_seconds'] for r in labels.values()),
        successful=[dict(name=f'candidate_{i:02d}',candidate_id=r['candidate_id']) for i,r in enumerate(public)],failed_or_interrupted=[])
    prereg,root = tmp_path/'prereg',tmp_path/'campaign'
    baseline_record = dict(name='baseline',routes=[dict(seed=s,internal_timing_pass=True,device_fits=True) for s in (1,2,3)],
        performance={'cycles':100},resources={'lut4_count':1})
    baseline = prereg/'targets'/t.w.GROUP/'baseline'
    for name,value in [('public.json',public),('context.json',context),('measurements/baseline/measurement.json',baseline_record)]:
        c.seal(baseline/name,value)
    bound = tmp_path/'bound-helper.py'; bound.write_text('exact bound helper')
    source_bindings = {'bound-helper.py':c.sha(bound)}
    historical = dict(source_corpus_sha256=c.sha(t.HISTORY),total_candidate_wall_seconds=previous['total_candidate_attempt_wall_seconds'],
        successful_labels=99,failed_attempts=3,total_candidate_attempts=102)
    qualified = {'fixture':True}
    cohort = dict(schema=t.SCHEMA,source_bindings=source_bindings,policies=t.POLICIES,
        historical_costs=historical,qualification=qualified)
    c.seal(prereg/'cohort.json',cohort); t.prior._seal_manifest(prereg)
    endpoints = t._endpoints(public,list(labels.values()),runs,False)
    report = dict(prereg_manifest_sha256=c.sha(prereg/'manifest.json'),native_audit_digest=c.digest(audited),
        outcomes_sha256=c.digest(audited['outcomes']),policies=t.POLICIES,runs=runs,endpoints=endpoints,reference_censored=False,
        calibration_diagnostics=t.calibration_diagnostics(public,audited['outcomes']))
    provenance = dict(schema=t.SCHEMA+'-campaign',preregistration='prereg',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        source_bindings=source_bindings,live=t.LIVE,qualification_baseline=t.baseline_accounting(baseline_record),
        historical_costs=historical,qualification=qualified,charged_candidate_attempts=12,successful_labels=12,
        collection_paired_durations={'fixture':True},calibration_diagnostics=t.calibration_diagnostics(public,audited['outcomes']))
    for name,value in [('provenance.json',provenance),('audit.json',audited),('outer-times.json',outer),
        ('report.json',report),('endpoints.json',endpoints),('baseline.json',baseline_record)]:
        c.seal(root/name,value)
    t.prior._seal_manifest(root)
    return dict(root=root,prereg=prereg,previous=previous,bound=bound)


def test_readonly_campaign_inputs_reconstruct_all_endpoints(campaign):
    values = t._campaign_inputs(campaign['root'])
    assert len(values[-1]) == 180


def test_readonly_report_export_rejects_current_bound_source_drift(campaign):
    campaign['bound'].write_text('changed source')
    with pytest.raises(ValueError):
        t._campaign_inputs(campaign['root'])


@pytest.mark.parametrize('field',['outcomes_sha256','native_audit_digest','prereg_manifest_sha256'])
def test_resealed_report_cannot_break_outcome_audit_or_prereg_bindings(campaign,field):
    path = campaign['root']/'report.json'
    value = c.unseal(path); value[field] = 'tampered'
    c.seal(path,value); t.prior._seal_manifest(campaign['root'])
    with pytest.raises(ValueError,match='Exact report source/outcome/audit'):
        t._campaign_inputs(campaign['root'])


def test_resealed_outer_mapping_cannot_change_paid_costs(campaign):
    path = campaign['root']/'outer-times.json'
    value = c.unseal(path); value[next(iter(value))] += 1.
    c.seal(path,value); t.prior._seal_manifest(campaign['root'])
    with pytest.raises(ValueError,match='Exact report source/outcome/audit'):
        t._campaign_inputs(campaign['root'])


def test_corpus_export_appends_once_and_preserves_old99plus3_bytes(campaign,monkeypatch):
    monkeypatch.setattr(t,'history',lambda path:copy.deepcopy(campaign['previous']))
    # Export provenance binds the current controller, represented by this fixture file.
    source = t.ROOT/t.SOURCE; source.parent.mkdir(exist_ok=True); source.write_text('synthetic controller')
    output = campaign['root'].parent/'export'
    result = t.export_corpus(campaign['root'],output)
    assert result['rows'][:99] == campaign['previous']['rows']
    assert result['failed_attempts'][:3] == campaign['previous']['failed_attempts']
    assert result['successful_labels'] == 111 and result['total_candidate_attempts'] == 114
    assert len(result['independent_workload_groups']) == 13 and len(result['contexts']) == 14
    assert (output/'historical-corpus.json').read_bytes() == t.HISTORY.read_bytes()
    assert result['new_qualification_baseline']['candidate_training_labels'] == 0
    assert result['new_qualification_baseline']['completed_routes'] == 3


def test_known_benefit_misses_are_counted_once_per_source_candidate(case):
    rows = copy.deepcopy(list(case['labels'].values()))
    row = rows[0]
    row['candidate_cycles'] += 1
    row['speedup'] = row['baseline_cycles']/row['candidate_cycles']
    result = t.calibration_diagnostics(case['public'],rows)
    assert result['successful_candidates_checked'] == 12
    assert result['unique_candidate_violation_count'] == 1
    assert result['violated_known_benefit_assumption'] is True
    assert result['violating_candidate_ids'] == [row['candidate_id']]
    assert result['candidates'][0]['measured_minus_calibrated_saved_cycles'] == -1
    assert row['candidate_cycles'] == case['labels'][row['candidate_id']]['candidate_cycles']+1


def test_resealed_calibration_diagnostic_cannot_hide_a_source_miss(campaign):
    path = campaign['root']/'report.json'
    value = c.unseal(path)
    value['calibration_diagnostics']['unique_candidate_violation_count'] = 99
    c.seal(path,value); t.prior._seal_manifest(campaign['root'])
    with pytest.raises(ValueError,match='Exact source-level measured-vs-calibrated'):
        t._campaign_inputs(campaign['root'])
