"""Seventeen frozen controls on original-input g723; source-bound paid dispatch.

Only fixed_joint_lookahead seed0/+64/B3 dispatches live; seal its complete paid
trace before the nine separately collected reference candidates. Old controls
reuse their frozen implementations. Finite B1/B2/B3 are independent horizons.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c, observed_command as observed
from isaforge import count_selection as count, semantic_selection as semantic
from isaforge import next_tacle_workload as w, guarded_workload as g, guarded_evidence
from isaforge import factorized_selection_experiment as experiment
from isaforge import finite_selection as f, joint_hardware as j
from isaforge.speedup_corpus import family
from scripts import blind_campaign as prior, live_gp_campaign as live_helpers
from scripts import tacle_selection_campaign as old
from scripts.export_guarded_corpus import _csv

SOURCE = 'scripts/g723_selection_campaign.py'
SCHEMA = 'isaforge-g723-selection-v1'
HISTORY = ROOT/'results/2026-10-22-twelve-source-corpus/corpus.json'
OLD_POLICIES = list(old.POLICIES)
POLICIES = [*OLD_POLICIES,*f.POLICIES]
LIVE = dict(policy=f.LOOKAHEAD, seed=0, area_cap=64, clock_mhz=12., budget=3)
HOST_TIMERS = old.HOST_TIMERS | {'acquisition_host_seconds','conditioning_host_seconds',
    'host_monotonic_start_ns','host_monotonic_end_ns','host_monotonic_seconds',
    'initial_joint_construction_host_seconds','mean_initial_model_host_seconds',
    'observer_validation_conditioning_host_seconds'}
LIMITATIONS = [
    'One fresh source and five dependent seeds do not establish broad generalization, significance, calibration or model superiority.',
    'All fourteen previous controls remain fixed and share identical source/family-excluded fitting rows with the three finite controls.',
    'Only fixed_joint_lookahead seed0/+64/planned B3 dispatches live native jobs; all other policies use charged cooperative replay.',
    'Finite B1/B2/B3 are independently executed horizons; B3 prefixes are labeled separately.',
    'Known calibrated benefit, independent hardware GPs, assumed Gaussian observation noise and a common Beta device-fit model are assumptions.',
    'Fixed initial preprocessing and noisy conditioning differ from the old dynamic semantic refit; two-step receding horizon is an approximation.',
    'Correctness/infrastructure failure probabilities are unmodeled; failed attempts are charged and never Gaussian labels.',
    'Original256 A-law samples and checksum24284 are retained; fixed-input checks do not prove arbitrary-input correctness.',
    'All102 historical attempts and every new attempt remain charged; ledger/native/CLI/observer/model timer scopes overlap and cannot be added.',
    'Initial fitting and repeated authentication refits have distinct host scopes; neither is free total-model cost.',
    'A cooperative callback is not an OS sandbox; outcome access is restricted to the current paid query.',
    'UTC/monotonic observations remain distinct; no uninterrupted calendar-wall-time saving is established.',
    'The paired collection timer begins after initial authentication/release checks; Python startup and initial checks are excluded. Candidate CLI timers include their dispatch checks.',
    'A pool reference is complete only without infrastructure-censored outcomes; baseline is always available.',
    'Single instructions only; joint instruction sets require joint execution and synthesis.']


@contextmanager
def _old_workload():
    """Reuse read-only old helpers with one scoped workload binding."""
    previous = old.w
    old.w = w
    try:
        yield
    finally:
        old.w = previous


def stable(value):
    if isinstance(value,(list,tuple)):
        return [stable(item) for item in value]
    if isinstance(value,dict):
        return {key:stable(item) for key,item in value.items() if key not in HOST_TIMERS}
    return value


def sources(plan):
    names = (SOURCE,old.SOURCE,'scripts/qualify_next_tacle.py',
        'scripts/live_gp_campaign.py','isaforge/observed_command.py',
        'scripts/report_guarded_selection.py','scripts/export_guarded_corpus.py','scripts/report_budget_campaign.py',
        *prior.SOURCES,*count.SOURCES,*semantic.SOURCES,*f.SOURCES,*plan['source_bindings'])
    return {name:c.sha(ROOT/name) for name in dict.fromkeys(names)}


def qualification(path,native):
    with _old_workload():
        return old.qualification(path,native)


def fresh(output,*inputs):
    return live_helpers.fresh_output(output,extra=(*inputs,HISTORY.parent))


def _joint_json(state):
    result = state.joint()
    for output in result['outputs'].values():
        for key in ('mean','covariance','observation_covariance'):
            output[key] = output[key].tolist()
    return result


def check_baseline(prereg,native):
    with _old_workload():
        return old.check_baseline(prereg,native)


def audit(native):
    w.validate_inputs(native)
    w.check_opportunity(native)
    with w.registration():
        return guarded_evidence.audit(native)


def count_search(case,provider,*,policy,seed,area_cap,on_acquire=None):
    # This old helper uses its unchanged semantic-policy identity and model rules.
    def canonical(proof):
        result = copy.deepcopy(proof)
        result['event']['score'] = list(result['event']['score'])
        c.require(c.digest(result) == c.digest(proof), 'Only canonical-JSON-equivalent score normalization allowed')
        return result
    def acquire(proof):
        if on_acquire is not None:
            on_acquire(canonical(proof))
    result = old.count_search(case,provider,policy=policy,seed=seed,area_cap=area_cap,on_acquire=acquire)
    result['acquisition_proofs'] = [canonical(proof) for proof in result['acquisition_proofs']]
    return result


def baseline_accounting(record):
    routes = record['routes']
    c.require(record['name'] == 'baseline' and [r['seed'] for r in routes] == [1,2,3] and
        all(r['internal_timing_pass'] and r['device_fits'] for r in routes),
        'Separate qualified baseline and all three routes required')
    return dict(candidate_training_labels=0,candidate_attempts=0,baseline_attempts=1,
        completed_integrated_designs=1,completed_routes=3,route_seeds=[1,2,3],
        performance=record['performance'],resources=record['resources'],
        scope='Qualification/setup baseline already measured; counted once separately from99historical training labels and candidate attempts.')


def history(path):
    path = Path(path).resolve()
    c.require(path == HISTORY.resolve(), 'Exact complete99-label historical corpus required')
    prior._manifest(path.parent)
    corpus = c.unseal(path)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 99 and
        len(corpus['failed_attempts']) == 3 and corpus['total_candidate_attempts'] == 102 and
        len(corpus['independent_workload_groups']) == 12 and len(corpus['contexts']) == 13,
        'Complete99-success/3-failure/102-attempt historical corpus required')
    attempts = corpus['rows']+corpus['failed_attempts']
    c.require(len({row['candidate_id'] for row in attempts}) == 102 and
        sum(row['measurement_seconds'] for row in attempts) == corpus['total_candidate_attempt_wall_seconds'],
        'Unique fully charged historical attempts required')
    c.require(all(b.validate_outcome(row) for row in corpus['rows']), 'Only verified history may fit models')
    c.require(w.GROUP not in {row['workload_group'] for row in attempts}, 'Entire fresh target source must be absent')
    return corpus

def freeze(native, output, *, qualification_path):
    native,output = Path(native).resolve(),Path(output).resolve()
    c.require(output.is_relative_to(ROOT), 'Repository-local preregistration required')
    fresh(output,native,qualification_path)
    prior._zero(native)
    public,context,before = w.baseline_public(native)
    plan = w.validate_inputs(native)
    c.require(context['workload_group'] == before['workload'] == w.GROUP and len(public) == w.POOL_SIZE and
        c.unseal(native/'public.json') == public and c.unseal(native/'context.json') == context and
        c.unseal(native/'before.json') == before, 'Exact complete twelve-candidate baseline required')
    qualified = qualification(qualification_path,native)
    corpus = history(HISTORY)
    contexts = dict(corpus['contexts']); contexts[public[0]['benchmark']] = context
    for name,value in [('history',corpus['rows']),('historical-failures',corpus['failed_attempts']),('contexts',contexts)]:
        c.seal(output/'inputs'/(name+'.json'),value)
    folder = output/'targets'/w.GROUP
    for name in prior.BASELINES:
        for suffix in ('','.sha256'):
            destination = folder/'baseline'/(name+suffix)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(native/(name+suffix),destination)
    for name in ('opportunity.json','opportunity.json.sha256'):
        shutil.copyfile(native/name,folder/'baseline'/name)
    shutil.copytree(native/'outer-timing',folder/'baseline/outer-timing')
    timers = {name:c.sha(folder/'baseline/outer-timing'/name) for name in prior._inventory(folder/'baseline/outer-timing')}
    shared = dict(successful_labels=99,failed_attempts=3,total_candidate_attempts=102,
        total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(HISTORY),actual_calendar_wall_seconds=None,clock_accounting=corpus['clock_accounting'])
    costs = dict(historical_training_available=shared,target_baseline=context['baseline_provenance'],qualification=qualified,
        qualification_baseline=baseline_accounting(c.unseal(native/'measurements/baseline/measurement.json')),
        note='All102 historical attempts charged once; ledger, native, CLI, paired-observer and model scopes remain separate.')
    c.seal(folder/'public.json',public); c.seal(folder/'cost-provenance.json',costs)
    bindings = {p.relative_to(ROOT).as_posix():c.sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    bindings[HISTORY.relative_to(ROOT).as_posix()] = c.sha(HISTORY)
    protocol = experiment.freeze(corpus['rows'],public,contexts,folder/'selection',target_workload=w.GROUP,
        target_labels_observed=0,calibration_cost_seconds=prior.evidence._calibration(native)['native_command_seconds'],
        cost_provenance=costs,input_bindings=bindings,scope='prospective source holdout')
    training = c.unseal(folder/'selection/controls11/model/history.json')
    began = time.monotonic_ns()
    model = semantic.SemanticHardwareSurrogate().fit(training)
    predictions,snapshot = model.predict(public),model.snapshot()
    ended = time.monotonic_ns()
    c.seal(folder/'semantic/predictions.json',predictions); c.seal(folder/'semantic/snapshot.json',snapshot)
    c.seal(folder/'semantic/cost.json',dict(initial_surrogate_fits=1,initial_scalar_gp_fits=3,
        host_monotonic_start_ns=began,host_monotonic_end_ns=ended,host_monotonic_seconds=(ended-began)/1e9))
    began_joint = time.monotonic_ns()
    posterior = j.JointHardwarePosterior.from_fitted(model,training,public)
    ended_joint = time.monotonic_ns()
    for name,value in [('initial',posterior.snapshot()),('joint',_joint_json(posterior)),('marginals',posterior.predict())]:
        c.seal(folder/'joint'/(name+'.json'),value)
    c.seal(folder/'joint/cost.json',dict(initial_surrogate_fits=0,initial_scalar_gp_fits=0,
        shared_semantic_initial_fit=True,initial_joint_construction_host_seconds=(ended_joint-began_joint)/1e9))
    for seed in range(5):
        draws,metadata = f.normal_draws(seed)
        c.seal(output/'fantasies'/f'seed{seed}.json',dict(normals=draws.tolist(),metadata=metadata))
    prior._zero(native)
    c.require(w.baseline_public(native) == (public,context,before), 'Baseline changed during complete model freeze')
    cohort = dict(schema=SCHEMA,target_labels_observed=0,target_labels_read=0,
        source_history=HISTORY.relative_to(ROOT).as_posix(),historical_costs=shared,qualification=qualified,
        source_bindings=sources(plan),python_executable=sys.executable,live=LIVE,
        policies=POLICIES,seeds=[0,1,2,3,4],area_caps=[32,64,128],budgets=[1,2,3],clock_mhz=12.,
        gp_settings=copy.deepcopy(b.GP_SETTINGS),semantic_columns=list(semantic.COLUMNS),
        finite_settings=copy.deepcopy(f.SETTINGS),finite_policies=list(f.POLICIES),
        finite_planned_budgets=[1,2,3],finite_terminal_rule='Each B1/B2/B3 independently executed; B3 prefixes separate.',
        fantasy_table_sha256s={str(seed):c.sha(output/'fantasies'/f'seed{seed}.json') for seed in range(5)},
        native_collection_rule='Seal three live fixed_joint_lookahead decisions/outcomes before any remaining oracle-reference outcome exists; then collect remainder in frozen public order, one attempt each.',
        targets={w.GROUP:dict(context_id=context['context_id'],native_order=before['pool_names'],pool_size=len(public),
            original_root=str(native),baseline_files=list(prior.BASELINES),baseline_outer_files=timers,
            selection_protocol_sha256=c.sha(folder/'selection/protocol.json'),
            historical_training_ids=protocol['historical_training_ids'],historical_postfilter_groups=protocol['historical_postfilter_groups'],
            semantic_predictions_sha256=c.sha(folder/'semantic/predictions.json'),semantic_snapshot_sha256=c.sha(folder/'semantic/snapshot.json'),
            joint_initial_sha256=c.sha(folder/'joint/initial.json'),joint_marginals_sha256=c.sha(folder/'joint/marginals.json'),
            joint_distribution_sha256=c.sha(folder/'joint/joint.json'))},
        primary=dict(area_delta_lut4=64,budget=3,clock_mhz=12.),limitations=LIMITATIONS)
    c.seal(output/'cohort.json',cohort); prior._seal_manifest(output)
    authenticate(output)
    return cohort

def authenticate(prereg):
    """Complete model/source/cohort validation without opening target outcomes."""
    prereg = Path(prereg).resolve(); entries = prior._manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(cohort['schema'] == SCHEMA and cohort['live'] == LIVE and cohort['policies'] == POLICIES and
        cohort['seeds'] == [0,1,2,3,4] and cohort['area_caps'] == [32,64,128] and cohort['budgets'] == [1,2,3] and
        cohort['clock_mhz'] == 12. and set(cohort['targets']) == {w.GROUP} and
        all(type(cohort[key]) is int and cohort[key] == 0 for key in ('target_labels_observed','target_labels_read')) and
        cohort['gp_settings'] == b.GP_SETTINGS and cohort['semantic_columns'] == list(semantic.COLUMNS) and
        cohort['finite_settings'] == f.SETTINGS and cohort['finite_policies'] == list(f.POLICIES) and
        cohort['finite_planned_budgets'] == [1,2,3] and
        cohort['finite_terminal_rule'] == 'Each B1/B2/B3 independently executed; B3 prefixes separate.' and
        cohort['primary'] == dict(area_delta_lut4=64,budget=3,clock_mhz=12.) and
        cohort['native_collection_rule'] == 'Seal three live fixed_joint_lookahead decisions/outcomes before any remaining oracle-reference outcome exists; then collect remainder in frozen public order, one attempt each.' and
        cohort['limitations'] == LIMITATIONS,
        'Complete fixed seventeen-policy zero-label source-holdout protocol required')
    target = cohort['targets'][w.GROUP]; folder = prereg/'targets'/w.GROUP
    plan = c.unseal(folder/'baseline/plan.json'); w.check_plan(plan)
    c.require(cohort['source_bindings'] == sources(plan), 'Frozen full controller/model/runtime sources changed')
    corpus = history(ROOT/cohort['source_history'])
    c.require(cohort['historical_costs']['source_corpus_sha256'] == c.sha(HISTORY) and
        cohort['historical_costs']['total_candidate_wall_seconds'] == corpus['total_candidate_attempt_wall_seconds'] and
        c.unseal(prereg/'inputs/history.json') == corpus['rows'] and
        c.unseal(prereg/'inputs/historical-failures.json') == corpus['failed_attempts'], 'Complete historical inputs/costs differ')
    qualified = ROOT/cohort['qualification']['path']; prior._manifest(qualified)
    c.require(c.sha(qualified/'manifest.json') == cohort['qualification']['manifest_sha256'], 'Qualification evidence changed')
    frozen,protocol = prior.required_selection(folder/'selection')
    prefix = 'targets/'+w.GROUP+'/selection/'
    c.require({name for name in entries if name.startswith(prefix)} == {prefix+name for name in frozen},
        'Complete frozen twelve-control model/prediction inventory required')
    case = experiment.authenticate(folder/'selection')
    public,context = c.unseal(folder/'baseline/public.json'),c.unseal(folder/'baseline/context.json')
    contexts = dict(corpus['contexts']); contexts[public[0]['benchmark']] = context
    families = {family(row['formula']) for row in public}
    fitting = [row for row in corpus['rows'] if family(row['formula']) not in families]
    c.require(case['public'] == public == c.unseal(folder/'public.json') and case['history'] == fitting and
        len({row['workload_group'] for row in fitting}) >= 2 and
        protocol['historical_training_ids'] == target['historical_training_ids'] == [row['candidate_id'] for row in fitting] and
        protocol['historical_postfilter_groups'] == target['historical_postfilter_groups'] == sorted({r['workload_group'] for r in fitting}) and
        c.unseal(prereg/'inputs/contexts.json') == contexts and c.digest(contexts) == protocol['contexts_digest'] and
        c.digest(corpus['rows']) == protocol['source_history_digest'] and
        target['context_id'] == context['context_id'] == plan['context_id'] and target['pool_size'] == len(public) == 12 and
        target['native_order'] == c.unseal(folder/'baseline/evaluation-protocol.json')['pool_names'] and
        c.sha(folder/'selection/protocol.json') == target['selection_protocol_sha256'] and
        w.opportunity_gate(public) == c.unseal(folder/'baseline/opportunity.json'), 'Source/family exclusions or baseline/pool changed')
    prior._hashes(ROOT,protocol['input_bindings'])
    c.require(cohort['historical_costs']['successful_labels'] == 99 and cohort['historical_costs']['failed_attempts'] == 3 and
        cohort['historical_costs']['total_candidate_attempts'] == 102 and
        protocol['cost_provenance'] == c.unseal(folder/'cost-provenance.json') and
        protocol['cost_provenance']['historical_training_available'] == cohort['historical_costs'] and
        protocol['cost_provenance']['target_baseline'] == context['baseline_provenance'] and
        protocol['cost_provenance']['qualification_baseline'] == baseline_accounting(c.unseal(folder/'baseline/measurements/baseline/measurement.json')),
        'Exact shared historical/baseline charge provenance required')
    semantic_files = {name for name in entries if name.startswith('targets/'+w.GROUP+'/semantic/')}
    c.require(semantic_files == {'targets/'+w.GROUP+'/semantic/'+name+suffix
        for name in ('predictions.json','snapshot.json','cost.json') for suffix in ('','.sha256')},
        'Complete exact semantic-model inventory required')
    initial,snapshot,cost = (c.unseal(folder/'semantic'/name) for name in ('predictions.json','snapshot.json','cost.json'))
    # Deterministic refit checks numerical predictions and model state, not only
    # asserted training metadata. No target outcome is read here.
    model = semantic.SemanticHardwareSurrogate().fit(fitting)
    c.require(model.predict(public) == initial and model.snapshot() == snapshot and
        c.sha(folder/'semantic/predictions.json') == target['semantic_predictions_sha256'] and
        c.sha(folder/'semantic/snapshot.json') == target['semantic_snapshot_sha256'] and
        cost['initial_surrogate_fits'] == 1 and cost['initial_scalar_gp_fits'] == 3 and
        cost['host_monotonic_end_ns'] >= cost['host_monotonic_start_ns'] and
        cost['host_monotonic_seconds'] == (cost['host_monotonic_end_ns']-cost['host_monotonic_start_ns'])/1e9,
        'Exact semantic initial model/predictions/cost changed')
    joint_files = {name for name in entries if name.startswith('targets/'+w.GROUP+'/joint/')}
    c.require(joint_files == {'targets/'+w.GROUP+'/joint/'+name+suffix
        for name in ('initial.json','joint.json','marginals.json','cost.json') for suffix in ('','.sha256')},
        'Complete exact joint initial model inventory required')
    posterior = j.JointHardwarePosterior.from_fitted(model,fitting,public)
    joint_initial,joint_distribution,joint_marginals,joint_cost = (c.unseal(folder/'joint'/name)
        for name in ('initial.json','joint.json','marginals.json','cost.json'))
    c.require(posterior.snapshot() == joint_initial and _joint_json(posterior) == joint_distribution and
        posterior.predict() == joint_marginals and
        target['joint_initial_sha256'] == c.sha(folder/'joint/initial.json') and
        target['joint_distribution_sha256'] == c.sha(folder/'joint/joint.json') and
        target['joint_marginals_sha256'] == c.sha(folder/'joint/marginals.json') and
        joint_cost['initial_surrogate_fits'] == joint_cost['initial_scalar_gp_fits'] == 0 and
        joint_cost['shared_semantic_initial_fit'] is True and joint_cost['initial_joint_construction_host_seconds'] >= 0,
        'Exact shared-fit joint initial state/marginals/distribution required')
    fantasy_files = {name for name in entries if name.startswith('fantasies/')}
    c.require(fantasy_files == {'fantasies/seed'+str(seed)+'.json'+suffix for seed in range(5)
        for suffix in ('','.sha256')}, 'All five exact fantasy-table artifacts required')
    fantasies = {}
    for seed in range(5):
        draws,metadata = f.normal_draws(seed)
        value = c.unseal(prereg/'fantasies'/f'seed{seed}.json')
        c.require(value == dict(normals=draws.tolist(),metadata=metadata) and
            cohort['fantasy_table_sha256s'].get(str(seed)) == c.sha(prereg/'fantasies'/f'seed{seed}.json'),
            'Exact sealed settings/normal draws/library-version required')
        fantasies[seed] = value
    case.update(posterior=posterior,joint_initial=joint_initial,fantasies=fantasies)
    case.update(selection_root=folder/'selection',semantic_predictions=initial,semantic_snapshot=snapshot,
        semantic_cost=cost,cohort=cohort)
    return cohort,w.GROUP,target,case

def checked_release(path,prereg,*,native=None):
    prereg = Path(prereg)
    cohort,_,target,_ = authenticate(prereg)
    released = c.unseal(path)
    c.require(released['schema'] == w.PROTOCOL['schema']+'-release' and
        released['manifest_sha256'] == c.sha(prereg/'manifest.json') and
        released['cohort_sha256'] == c.sha(prereg/'cohort.json') and
        released['context_id'] == target['context_id'] and
        released['preregistration_root'] == prereg.relative_to(ROOT).as_posix() and
        released['evaluation_protocol_sha256'] == c.sha(prereg/'targets'/w.GROUP/'baseline/evaluation-protocol.json') and
        released['pushed_remote_head'] == released['prelabel_commit'] and released['pushed_branch'] == 'ai-guided-ml' and
        released['remote'] == 'origin' and released['zero_candidate_attempts'] is True and
        type(released['target_labels_observed']) is int and released['target_labels_observed'] == 0,
        'Exact complete pushed zero-label release required')
    prior.check_git_checkpoint(prereg,released['prelabel_commit'])
    if native is not None:
        c.require(c.unseal(Path(native)/'release.json') == released, 'Native and external release differ')
    return released

def release(prereg,native,commit,output):
    prereg,native,output = (Path(p).resolve() for p in (prereg,native,output))
    cohort,_,target,_ = authenticate(prereg)
    live_helpers.original_native(native,target)
    fresh(output,prereg,native,ROOT/cohort['qualification']['path'])
    c.require(not (native/'release.json').exists(), 'Fresh native release required')
    prior.check_git_checkpoint(prereg,commit)
    remote = subprocess.run(['git','ls-remote','origin','refs/heads/ai-guided-ml'],cwd=ROOT,
        capture_output=True,text=True,check=True,timeout=30)
    c.require(remote.stdout.strip().split() == [commit,'refs/heads/ai-guided-ml'], 'Push exact complete prelabel checkpoint before release')
    prior._zero(native); check_baseline(prereg,native)
    record = dict(schema=w.PROTOCOL['schema']+'-release',prelabel_commit=commit,pushed_remote_head=commit,
        pushed_branch='ai-guided-ml',remote='origin',preregistration_root=prereg.relative_to(ROOT).as_posix(),
        manifest_sha256=c.sha(prereg/'manifest.json'),cohort_sha256=c.sha(prereg/'cohort.json'),
        evaluation_protocol_sha256=c.sha(native/'evaluation-protocol.json'),context_id=target['context_id'],
        zero_candidate_attempts=True,target_labels_observed=0,released_at_utc=datetime.now(timezone.utc).isoformat())
    c.seal(output,record)
    for suffix in ('','.sha256'):
        shutil.copyfile(str(output)+suffix,str(native/'release.json')+suffix)
    check_native_release(native)
    return record

def collect(prereg,native,release_path,output):
    prereg,native,output = (Path(p).resolve() for p in (prereg,native,output))
    cohort,_,target,case = authenticate(prereg)
    live_helpers.original_native(native,target)
    fresh(output,prereg,native,release_path,ROOT/cohort['qualification']['path'])
    prior._zero(native); check_baseline(prereg,native)
    checked_release(release_path,prereg,native=native)
    check_native_release(native)
    output.mkdir(parents=True)
    paid,trace_hash = [],None
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole = dict(schema=SCHEMA+'-collection',status='started',start=observed._endpoint(),observer_pid=os.getpid(),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),live=LIVE,dispatched_ids=[])
    c.seal(output/'collection.json',whole)
    def acquire(proof):
        index = len(paid)
        c.require(index < LIVE['budget'] and proof['event']['charged_before_query'] == index and
            proof['event']['attempted_ids_before_query'] == paid, 'Exact live paid prefix required before acquisition')
        c.seal(output/'acquisitions'/f'{index:02d}.json',proof)
    def provider(row):
        nonlocal trace_hash
        identity,index = row['candidate_id'],len(paid)
        c.require(identity in names and identity not in paid and index < len(names), 'Unique declared paid query required')
        mode = 'adaptive' if index < LIVE['budget'] else 'oracle-reference'
        c.require((mode == 'adaptive') == (trace_hash is None), 'Seal live trace before oracle collection')
        acquisition = None
        if mode == 'adaptive':
            proof_path = output/'acquisitions'/f'{index:02d}.json'
            proof = c.unseal(proof_path)
            c.require(proof['event']['candidate_id'] == identity and proof['event']['policy'] == LIVE['policy'],
                'Seal model-state/acquisition proof before native dispatch')
            acquisition = c.sha(proof_path)
        folder = output/'queries'/f'{index:02d}'
        folder.mkdir(parents=True)
        decision = dict(index=index,mode=mode,candidate_id=identity,native_name=names[identity],paid_ids_before=list(paid),
            prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
            completed_live_trace_sha256=trace_hash,acquisition_sha256=acquisition,chosen_before_dispatch=True)
        c.seal(folder/'decision.json',decision)
        whole['dispatched_ids'].append(identity)
        before = set((native/'outer-timing').glob('*.json'))
        argv = [cohort['python_executable'],SOURCE,'measure','--root',str(native),'--candidate',names[identity]]
        record = observed.run(argv,folder/'command',cwd=ROOT,metadata=decision,timeout_seconds=3600)
        c.require(record['status'] in ('success','nonzero_exit'), 'Interruption stops collection; never retry')
        audited = audit(native)
        labels = {value['candidate_id']:value for value in audited['outcomes']}
        expected = set(paid+[identity])
        c.require(audited['charged_candidate_attempts'] == index+1 and set(labels) == expected and
            audited['candidate_wall_seconds_complete'], 'Only exact paid terminal outcomes may reach the learner')
        value = labels[identity]; b.validate_outcome(value,row)
        added = set((native/'outer-timing').glob('*.json'))-before
        c.require(len(added) == 1, 'One CLI receipt per native query required')
        cli = next(iter(added)); ledger = native/'attempt-ledger'/(names[identity]+'.json')
        c.require((record['returncode'] == 0) == (c.unseal(ledger)['status'] == 'success'), 'CLI/ledger status differs')
        c.seal(folder/'outcome.json',value); c.seal(folder/'partial-audit.json',audited)
        c.seal(folder/'completed.json',dict(candidate_id=identity,audited_paid_ids=sorted(expected),
            ledger_sha256=c.sha(ledger),cli_timer=cli.relative_to(native).as_posix(),cli_timer_sha256=c.sha(cli),
            outcome_sha256=c.sha(folder/'outcome.json'),partial_audit_digest=c.digest(audited)))
        paid.append(identity)
        print(json.dumps(dict(query=len(paid),mode=mode,name=names[identity],speedup=value.get('speedup'),
            area_delta_lut4=value.get('area_delta_lut4'),status=value.get('status','success'))),flush=True)
        return value
    try:
        searched = run_search(case,provider,on_acquire=acquire)
        trace = dict(schema=SCHEMA+'-live-trace',search=searched,attempted_ids=list(paid),
            finish=observed._endpoint(),remaining_outcomes_exist=False,live=LIVE)
        c.seal(output/'live.json',trace); trace_hash = c.sha(output/'live.json')
        for row in case['public']:
            if row['candidate_id'] not in paid:
                provider(row)
        whole.update(status='complete',paid_ids=paid,live_trace_sha256=trace_hash)
    except BaseException as error:
        whole.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
            error_type=type(error).__name__,error=repr(error),paid_ids=paid)
        raise
    finally:
        whole['end'] = observed._endpoint(); whole['durations'] = observed._durations(whole['start'],whole['end'])
        c.seal(output/'collection.json',whole); prior._seal_manifest(output)
    return whole

def check_collection(prereg,native,collection,release_path):
    prereg,native,collection = (Path(p).resolve() for p in (prereg,native,collection))
    prior._manifest(collection)
    cohort,_,target,case = authenticate(prereg)
    released = checked_release(release_path,prereg,native=native)
    audited = audit(native)
    experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole,trace = c.unseal(collection/'collection.json'),c.unseal(collection/'live.json')
    c.require(whole['status'] == 'complete' and whole['live'] == trace['live'] == LIVE and
        whole['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and whole['release_sha256'] == c.sha(release_path) and
        whole['live_trace_sha256'] == c.sha(collection/'live.json') and trace['remaining_outcomes_exist'] is False and
        whole['durations'] == observed._durations(whole['start'],whole['end']), 'Complete paired live collection required')
    paid,first = whole['paid_ids'],trace['attempted_ids']
    c.require(whole['dispatched_ids'] == paid and len(first) == LIVE['budget'] and paid[:len(first)] == first and len(paid) == len(set(paid)) == len(names) and
        set(paid) == set(names) and paid[len(first):] == [row['candidate_id'] for row in case['public'] if row['candidate_id'] not in first],
        'Live prefix and declared oracle-remainder order required')
    times = {}; previous_end = whole['start']['monotonic_after_ns']; cli_names = set()
    native_receipts = c.unseal(native/'commands.json')
    for index,identity in enumerate(paid):
        folder = collection/'queries'/f'{index:02d}'
        decision,completed = c.unseal(folder/'decision.json'),c.unseal(folder/'completed.json')
        record,started = c.unseal(folder/'command/record.json'),c.unseal(folder/'command/started.json')
        live_helpers.observed_pair(record,started)
        proof_path = collection/'acquisitions'/f'{index:02d}.json'
        expected = dict(index=index,mode='adaptive' if index < LIVE['budget'] else 'oracle-reference',
            candidate_id=identity,native_name=names[identity],paid_ids_before=paid[:index],
            prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
            completed_live_trace_sha256=None if index < LIVE['budget'] else c.sha(collection/'live.json'),
            acquisition_sha256=c.sha(proof_path) if index < LIVE['budget'] else None,chosen_before_dispatch=True)
        argv = [cohort['python_executable'],SOURCE,'measure','--root',target['original_root'],'--candidate',names[identity]]
        argv_hash = hashlib.sha256(json.dumps(argv,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
        c.require(decision == expected == record['metadata'] == started['metadata'] and record['argv_sha256'] == argv_hash and
            record['observer_pid'] == whole['observer_pid'] and record['status'] in ('success','nonzero_exit') and
            previous_end <= record['start']['monotonic_before_ns'] and record['end']['monotonic_after_ns'] <= whole['end']['monotonic_after_ns'] and
            record['durations'] == observed._durations(record['start'],record['end']) and record['durations']['monotonic_endpoints_ordered'],
            'Source-bound serial paid receipt or paired durations differ')
        c.require(prior._utc(record['start']['utc_iso']) >= prior._utc(released['released_at_utc']), 'Native query predates model release')
        for stream in ('stdout','stderr'):
            c.require(c.sha(folder/'command'/(stream+'.txt')) == record[stream+'_sha256'], 'Native observer stream changed')
        ledger_path = native/'attempt-ledger'/(names[identity]+'.json'); ledger = c.unseal(ledger_path)
        partial = c.unseal(folder/'partial-audit.json'); prefix = {row['candidate_id']:row for row in partial['outcomes']}
        c.require((record['returncode'] == 0) == (ledger['status'] == 'success') and ledger['status'] in ('success','failed') and
            partial['context_id'] == audited['context_id'] and partial['charged_candidate_attempts'] == index+1 and
            partial['candidate_wall_seconds_complete'] and set(prefix) == set(paid[:index+1]) and
            all(value == labels[key] for key,value in prefix.items()) and partial['native_command_count'] == ledger['receipt_end'] and
            partial['native_command_seconds'] == sum(row['elapsed_seconds'] for row in native_receipts[:ledger['receipt_end']]) and
            c.unseal(folder/'outcome.json') == labels[identity] and completed['outcome_sha256'] == c.sha(folder/'outcome.json') and
            completed['partial_audit_digest'] == c.digest(partial) and completed['ledger_sha256'] == c.sha(ledger_path) and
            completed['candidate_id'] == identity and completed['audited_paid_ids'] == sorted(paid[:index+1]),
            'Exact successful-paid prefix, ledger or native receipt span differs')
        cli_path = prior._path(native,completed['cli_timer']); cli = c.unseal(cli_path)
        c.require(completed['cli_timer'] not in cli_names and c.sha(cli_path) == completed['cli_timer_sha256'] and
            cli['command'] == 'measure' and cli['candidate'] == names[identity] and
            record['durations']['monotonic_elapsed_seconds'] >= cli['elapsed_seconds'] >= labels[identity]['measurement_seconds'],
            'Nested monotonic duration scopes differ')
        cli_names.add(completed['cli_timer']); times[identity] = cli['elapsed_seconds']
        if index < LIVE['budget']:
            c.require(record['end']['monotonic_after_ns'] <= trace['finish']['monotonic_before_ns'], 'Live query after trace completion')
        else:
            c.require(trace['finish']['monotonic_after_ns'] <= record['start']['monotonic_before_ns'], 'Oracle outcome before live trace seal')
        previous_end = record['end']['monotonic_after_ns']
    c.require({p.relative_to(native).as_posix() for p in (native/'outer-timing').glob('*.json')
        if c.unseal(p).get('command') == 'measure'} == cli_names, 'Unobserved native candidate CLI call')
    used = []; proofs = []
    def provider(row):
        c.require(row['candidate_id'] == first[len(used)], 'Deterministic paid choice differs from live search')
        used.append(row['candidate_id'])
        return labels[row['candidate_id']]
    recreated = run_search(case,provider,on_acquire=proofs.append)
    c.require(stable(recreated) == stable(trace['search']) and len(proofs) == 3 and
        all(proof == c.unseal(collection/'acquisitions'/f'{i:02d}.json') for i,proof in enumerate(proofs)),
        'Live model state, predictions, acquisition proofs or paid curves differ')
    return audited,times,trace,whole

def pack(prereg,native,collection,release_path,output):
    prereg,native,collection,output = (Path(p).resolve() for p in (prereg,native,collection,output))
    cohort,_,target,_ = authenticate(prereg)
    live_helpers.original_native(native,target)
    fresh(output,prereg,native,collection,release_path,ROOT/cohort['qualification']['path'])
    released = checked_release(release_path,prereg,native=native)
    check_baseline(prereg,native)
    audited,outer,trace,whole = check_collection(prereg,native,collection,release_path)
    output.mkdir(parents=True)
    shutil.copytree(collection,output/'collection')
    for suffix in ('','.sha256'):
        shutil.copyfile(str(release_path)+suffix,str(output/'release.json')+suffix)
    selection = output/'selection'
    shutil.copytree(prereg/'targets'/w.GROUP/'selection',selection)
    refits = prior.verify_refits(selection)
    report = evaluate(prereg,selection,audited,outer,output/'report.json')
    with w.registration():
        guarded_evidence.pack(native,output/'native',prelabel_commit=None)
    # Complete prelabel chronology is authenticated by the cohort's Git blobs
    # and exact copied baseline; the ignored original generated path need not be
    # a Git-tracked native protocol path.
    c.seal(output/'audit.json',audited); c.seal(output/'outer-times.json',outer)
    c.seal(output/'endpoints.json',report['endpoints'])
    baseline = c.unseal(native/'measurements/baseline/measurement.json')
    records = {row['name']:c.unseal(native/'measurements'/row['name']/'measurement.json') for row in audited['successful']}
    c.seal(output/'baseline.json',baseline); c.seal(output/'native-measurements.json',records)
    result = dict(schema=SCHEMA+'-campaign',prelabel_commit=released['prelabel_commit'],
        preregistration=prereg.relative_to(ROOT).as_posix(),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        source_bindings=cohort['source_bindings'],workload_group=w.GROUP,live=LIVE,live_best=trace['search']['curve'][-1],
        live_native_attempts=LIVE['budget'],charged_candidate_attempts=audited['charged_candidate_attempts'],
        successful_labels=len(audited['successful']),historical_costs=cohort['historical_costs'],qualification=cohort['qualification'],
        qualification_baseline=baseline_accounting(baseline),calibration_diagnostics=report['calibration_diagnostics'],
        collection_paired_durations=whole['durations'],refits=refits,trajectories=report['trajectories'],endpoints=report['endpoint_points'],
        endpoint_summaries=report['endpoint_summaries'],live_native_dispatch=True,other_policies_native_remeasured=False,
        actual_calendar_wall_seconds=None,new_native_jobs=0,limitations=LIMITATIONS)
    c.seal(output/'provenance.json',result); prior._seal_manifest(output)
    return result

def replay(campaign,output):
    campaign,output = Path(campaign).resolve(),Path(output).resolve()
    prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json'); prereg = ROOT/provenance['preregistration']
    cohort,_,target,_ = authenticate(prereg)
    fresh(output,campaign,prereg,target['original_root'],ROOT/cohort['qualification']['path'])
    c.require(provenance['schema'] == SCHEMA+'-campaign' and provenance['source_bindings'] == cohort['source_bindings'] and
        provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json'), 'Complete campaign/prelabel binding required')
    prior.check_git_checkpoint(prereg,provenance['prelabel_commit'])
    raw = output/'native'
    with w.registration():
        audited = guarded_evidence.replay(campaign/'native',raw)
    w.validate_inputs(raw); check_baseline(prereg,raw)
    checked,outer,trace,whole = check_collection(prereg,raw,campaign/'collection',campaign/'release.json')
    c.require(checked == audited == c.unseal(campaign/'audit.json') and outer == c.unseal(campaign/'outer-times.json'),
        'Raw native outcomes, controls or paid timers differ')
    selection = campaign/'selection'
    frozen,_ = prior.required_selection(prereg/'targets'/w.GROUP/'selection')
    c.require(prior._inventory(selection) == frozen|prior.FINAL_REPORTS, 'Complete final twelve-control model package required')
    for name in frozen:
        c.require(c.sha(selection/name) == c.sha(prereg/'targets'/w.GROUP/'selection'/name), 'Frozen model changed after labels')
    refits = prior.verify_refits(selection)
    result = evaluate(prereg,selection,audited,outer,campaign/'report.json',verify=True)
    c.require(stable(c.unseal(campaign/'endpoints.json')) == stable(result['endpoints']) and
        stable(provenance['live_best']) == stable(trace['search']['curve'][-1]) and
        provenance['collection_paired_durations'] == whole['durations'] and
        result['trajectories'] == 345 and result['endpoint_points'] == 900 and result['endpoint_summaries'] == 180,
        'Complete fixed-policy endpoints/live trace/native cost replay required')
    # Nondeterministic host timers are explicitly excluded from exact scientific
    # equality; preserve their old and fresh values without rewriting either.
    c.seal(output/'archived-endpoints.json',c.unseal(campaign/'endpoints.json'))
    c.seal(output/'replayed-endpoints.json',result['endpoints'])
    receipt = dict(charged_candidate_attempts=audited['charged_candidate_attempts'],
        trajectories=345,endpoints=900,endpoint_summaries=180,**refits,new_native_jobs=0,live_trace_exact=True,
        scientific_and_paid_cost_fields_exact=True,excluded_host_timer_fields=sorted(HOST_TIMERS),
        initial_semantic_model_refit_exact=True,paired_collection_clocks_exact=True)
    c.seal(output/'reproduction.json',receipt); prior._seal_manifest(output)
    return receipt


def check_native_release(native):
    """Complete package and actual pushed head, rechecked for every paid query."""
    native = Path(native).resolve()
    plan = w.validate_inputs(native)
    release_record = c.unseal(native/'release.json')
    prereg = prior._path(ROOT,release_record['preregistration_root'])
    c.require(not prereg.is_relative_to(native), 'Separate preregistration required')
    released = checked_release(native/'release.json',prereg,native=native)
    c.require(released['context_id'] == plan['context_id'], 'Released native context differs')
    check_baseline(prereg,native)
    remote = subprocess.run(['git','ls-remote','origin','refs/heads/ai-guided-ml'],cwd=ROOT,
        capture_output=True,text=True,check=True,timeout=30)
    c.require(remote.stdout.strip().split() == [released['prelabel_commit'],'refs/heads/ai-guided-ml'],
        'Actual origin/ai-guided-ml head must equal complete prelabel checkpoint')
    return released


class ReleasedEvaluator(g.Evaluator):
    """The qualification adapter remains closed; only this gate dispatches labels."""
    def __init__(self,root):
        w.validate_inputs(root)
        with w.registration():
            super().__init__(root)

    def discover(self):
        with w.registration():
            return super().discover()

    def measure(self,name):
        w.check_opportunity(self.root)
        if name != 'baseline':
            check_native_release(self.root)
        with w.registration():
            return super().measure(name)


def finite_search(case,provider,*,policy,seed,area_cap,budget,on_acquire=None):
    """Prove the actual successful paid prefix before each provider invocation."""
    expected = case['posterior'].clone()
    released,successful = [],[]
    proof_count = 0
    last_proven_id = None
    validation_seconds = 0.
    def acquire(proof):
        nonlocal proof_count,last_proven_id
        event,snapshot = proof['event'],proof['posterior_snapshot']
        c.require(proof_count == len(released) and event['policy'] == policy and
            event['planned_budget'] == budget and event['remaining_queries'] == budget-len(released) and
            event['charged_before_query'] == len(released) and event['attempted_ids_before_query'] == released and
            event['paid_target_ids_before_query'] == [r['candidate_id'] for r in successful] and
            proof['successful_paid_ids'] == [r['candidate_id'] for r in successful] and
            proof['initial_training_ids'] == [r['candidate_id'] for r in case['history']] and
            snapshot['paid_outcomes_sha256'] == c.digest(successful) and
            snapshot == expected.snapshot() and proof['snapshot_sha256'] == c.digest(snapshot) and
            event['posterior_state_sha256'] == snapshot['posterior_state_sha256'] and
            proof['fantasy_table'] == case['fantasies'][seed]['metadata'],
            'Exact sealed initial state, fantasy table and successful paid prefix required')
        proof_count += 1
        last_proven_id = event['candidate_id']
        if on_acquire is not None:
            on_acquire(copy.deepcopy(proof))
    def paid(candidate):
        nonlocal expected,validation_seconds
        c.require(proof_count == len(released)+1 and candidate['candidate_id'] == last_proven_id and
            candidate['candidate_id'] not in released and
            candidate == next(row for row in case['public'] if row['candidate_id'] == candidate['candidate_id']),
            'Seal unique chosen public query before provider')
        released.append(candidate['candidate_id'])
        outcome = copy.deepcopy(provider(copy.deepcopy(candidate)))
        if b.validate_outcome(outcome,candidate):
            successful.append(copy.deepcopy(outcome))
            began_validation = time.monotonic()
            expected = expected.condition(outcome,queried_id=candidate['candidate_id'])
            validation_seconds += time.monotonic()-began_validation
        return outcome
    result = f.search(case['public'],case['history'],paid,posterior=case['posterior'],policy=policy,
        area_cap=area_cap,clock_mhz=12.,seed=seed,budget=budget,on_acquire=acquire)
    c.require(len(released) == len(set(released)) == proof_count == budget and
        result['final_posterior_snapshot'] == expected.snapshot(), 'Exact planned budget and terminal posterior required')
    result['observer_validation_conditioning_host_seconds'] = validation_seconds
    result['observer_validation_conditional_updates'] = len(successful)
    return result


def run_search(case,provider,*,on_acquire=None):
    return finite_search(case,provider,policy=LIVE['policy'],seed=LIVE['seed'],
        area_cap=LIVE['area_cap'],budget=LIVE['budget'],on_acquire=on_acquire)


def calibration_diagnostics(public,outcomes):
    features = {row['candidate_id']:row for row in public}
    rows = []
    for outcome in outcomes:
        feature = features[outcome['candidate_id']]
        if b.validate_outcome(outcome,feature):
            estimated = feature['latency_features']['estimated_saved_cycles']
            measured = outcome['baseline_cycles']-outcome['candidate_cycles']
            residual = measured-estimated
            rows.append(dict(candidate_id=outcome['candidate_id'],estimated_saved_cycles=estimated,
                measured_saved_cycles=measured,measured_minus_calibrated_saved_cycles=residual,
                calibrated_benefit_assumption_violated=residual != 0))
    misses = [row['candidate_id'] for row in rows if row['calibrated_benefit_assumption_violated']]
    return dict(successful_candidates_checked=len(rows),unique_candidate_violation_count=len(misses),
        violated_known_benefit_assumption=bool(misses),violating_candidate_ids=misses,candidates=rows,
        interpretation='Each successful candidate counted once; actual measured labels retained unchanged. A miss violates the known calibrated-benefit assumption, not a rejected or rewritten label.')


def _endpoints(public,outcomes,runs,censored):
    """Validate arithmetic, costs, failures and all independent planned horizons."""
    features = {r['candidate_id']:r for r in public}
    labels = {r['candidate_id']:r for r in outcomes}
    c.require(set(labels) == set(features) and len(features) == len(public) == len(outcomes),
        'Complete unique outcome/public pool required')
    actual_censored = False
    for identity,row in labels.items():
        if not b.validate_outcome(row,features[identity]):
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class') and
                not {'area','device_fits','timing_feasible'} & set(row), 'Classified failure without invented labels required')
            actual_censored |= row['reference_censored']
    c.require(type(censored) is bool and actual_censored == censored, 'Exact reference censorship required')
    expected = {(policy,cap,seed,budget) for policy in POLICIES for cap in (32,64,128) for seed in range(5)
        for budget in ((1,2,3) if policy in f.POLICIES else (3,))}
    keys = [(r['policy'],r['cap'],r['seed'],r.get('planned_budget',3)) for r in runs]
    c.require(len(keys) == len(expected) and set(keys) == expected, 'Complete17-policy independent finite horizon grid required')
    outer = runs[0]['candidate_outer_operation_seconds']
    c.require(set(outer) == set(labels) and all(type(v) in (int,float) and math.isfinite(v) and v >= labels[k]['measurement_seconds']
        for k,v in outer.items()), 'Complete authoritative outer-operation costs required')
    points = []
    for run in runs:
        budget = run.get('planned_budget',3)
        c.require(len(run['curve']) == budget and [p['budget'] for p in run['curve']] == list(range(1,budget+1)) and
            run['candidate_outer_operation_seconds'] == outer, 'Exact planned trajectory/cost map required')
        terminal = run['curve'][-1]['attempted_ids']
        for point in run['curve']:
            paid = point['attempted_ids']
            c.require(len(paid) == len(set(paid)) == point['budget'] and set(paid) <= set(labels) and
                paid == terminal[:point['budget']], 'Exact unique charged prefix required')
            attempted = [labels[i] for i in paid]
            best = max([1.]+[r['speedup'] for r in attempted if b._feasible(r,run['cap'],12.)])
            c.require(point['best_speedup'] == best and
                point['target_measurement_seconds'] == sum(r['measurement_seconds'] for r in attempted) and
                point['target_outer_operation_seconds'] == sum(outer[i] for i in paid),
                'Verified measured incumbent and exact paid costs required')
            known = sum((r.get('status','success') == 'success' and not b._feasible(r,run['cap'],12.)) or
                (r.get('status') == 'failed' and not r['reference_censored']) for r in attempted)
            unknown = sum(r.get('status') == 'failed' and r['reference_censored'] for r in attempted)
            c.require(point['known_infeasible_attempts'] == known and point['unknown_attempts'] == unknown,
                'Known invalid failures and infrastructure-unknown outcomes differ')
            c.require(type(point.get('inference_seconds',0.)) in (int,float) and
                math.isfinite(point.get('inference_seconds',0.)) and point.get('inference_seconds',0.) >= 0,
                'Finite nonnegative host inference seconds required')
            reference = max([1.]+[r['speedup'] for r in outcomes if b._feasible(r,run['cap'],12.)])
            common = dict(point,policy=run['policy'],cap=run['cap'],seed=run['seed'],planned_budget=budget,
                verified_cycle_reduction=1-1/best,reference_speedup=reference,
                reference_cycle_reduction=1-1/reference,cycle_reduction_regret=1/best-1/reference,
                reference_complete=not censored,regret_is_lower_bound=censored)
            # Preserve primary matched-budget B3 prefixes for every old/new policy.
            if budget == 3:
                points.append(dict(common,endpoint_kind='B3-prefix'))
            if run['policy'] in f.POLICIES and point['budget'] == budget:
                points.append(dict(common,endpoint_kind='horizon-aware-terminal'))
    groups = {}
    for point in points:
        key = tuple(point[k] for k in ('policy','cap','budget','planned_budget','endpoint_kind'))
        groups.setdefault(key,[]).append(point)
    result = []
    for key,values in groups.items():
        c.require(sorted(r['seed'] for r in values) == list(range(5)), 'Five dependent seeds per endpoint required')
        row = dict(zip(('policy','cap','budget','planned_budget','endpoint_kind'),key))
        row.update(dependent_seed_count=5,reference_speedup=values[0]['reference_speedup'],
            reference_cycle_reduction=values[0]['reference_cycle_reduction'],reference_complete=not censored,regret_is_lower_bound=censored)
        for field in ('best_speedup','verified_cycle_reduction','cycle_reduction_regret','target_measurement_seconds',
                      'target_outer_operation_seconds','known_infeasible_attempts','unknown_attempts','inference_seconds'):
            row['mean_'+field] = statistics.mean(p.get(field,0.) for p in values)
        row['verified_reference_hits'] = sum(p['best_speedup'] == p['reference_speedup'] for p in values)
        result.append(row)
    return result


def evaluate(prereg,selection,audited,outer,output,*,verify=False):
    prereg,selection,output = map(Path,(prereg,selection,output))
    cohort,_,_,case = authenticate(prereg)
    censored = experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    c.require(set(outer) == {row['candidate_id'] for row in case['public']} and
        all(outer[row['candidate_id']] >= row['measurement_seconds'] for row in audited['outcomes']),
        'Complete charged native/outer durations required')
    c.require(verify or not output.exists(), 'Preserve complete selection report')
    old_result = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=outer,verify=verify)
    runs = copy.deepcopy(old_result['runs'])
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    for policy in (*OLD_POLICIES[-2:],*f.POLICIES):
        for seed in cohort['seeds']:
            for cap in cohort['area_caps']:
                for budget in (cohort['budgets'] if policy in f.POLICIES else (3,)):
                    released = []
                    trajectory = output.parent/'replay-acquisitions'/policy/f'B{budget}-cap{cap}-seed{seed}'
                    def acquire(proof):
                        event = proof['event']
                        c.require(event['charged_before_query'] == len(released) and
                            event['attempted_ids_before_query'] == released, 'Only paid replay prefix may reach acquisition')
                        path = trajectory/f'{len(released):02d}.json'
                        if verify:
                            c.require(c.unseal(path) == proof, 'Exact replay state/acquisition proof changed')
                        else:
                            c.seal(path,proof)
                    def provider(row):
                        proof = c.unseal(trajectory/f'{len(released):02d}.json')
                        c.require(proof['event']['candidate_id'] == row['candidate_id'] and row['candidate_id'] not in released,
                            'Seal choice before one charged replay outcome release')
                        released.append(row['candidate_id'])
                        return copy.deepcopy(labels[row['candidate_id']])
                    searched = finite_search(case,provider,policy=policy,seed=seed,area_cap=cap,budget=budget,
                        on_acquire=acquire) if policy in f.POLICIES else count_search(case,provider,policy=policy,
                        seed=seed,area_cap=cap,on_acquire=acquire)
                    c.require(len(released) == len(set(released)) == budget, 'Exact planned unique query budget required')
                    runs.append(dict(target=w.GROUP,cap=cap,seed=seed,**searched))
    for run in runs:
        old.annotate(run,labels,outer,run['cap'])
    endpoints = _endpoints(case['public'],audited['outcomes'],runs,censored)
    result = dict(schema=SCHEMA+'-report',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        outcomes_sha256=c.digest(audited['outcomes']),native_audit_digest=c.digest(audited),
        policies=POLICIES,runs=runs,endpoints=endpoints,reference_censored=censored,
        calibration_diagnostics=calibration_diagnostics(case['public'],audited['outcomes']),
        trajectories=len(runs),endpoint_points=sum(len(run['curve']) for run in runs),endpoint_summaries=len(endpoints),
        new_native_jobs=0,superiority_established=False,limitations=LIMITATIONS)
    if verify:
        archived = c.unseal(output)
        c.require(stable(result) == stable(archived), 'Scientific predictions, paid selections or costs differ on replay')
    else:
        c.seal(output,result)
    return result


def _campaign_inputs(campaign):
    campaign = Path(campaign).resolve()
    prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json')
    prereg = prior._path(ROOT,provenance['preregistration'])
    prior._manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(provenance['schema'] == SCHEMA+'-campaign' and cohort['schema'] == SCHEMA and
        provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        provenance['source_bindings'] == cohort['source_bindings'] and provenance['live'] == LIVE and
        cohort['policies'] == POLICIES, 'Complete17-policy campaign/preregistration binding required')
    prior._hashes(ROOT,cohort['source_bindings'])
    audited = c.unseal(campaign/'audit.json')
    baseline = prereg/'targets'/w.GROUP/'baseline'
    public,context = c.unseal(baseline/'public.json'),c.unseal(baseline/'context.json')
    outer = c.unseal(campaign/'outer-times.json')
    c.require(audited['public'] == public and audited['context_id'] == context['context_id'] and
        context['workload_group'] == w.GROUP and audited['attempt_collection_complete'] and
        audited['candidate_wall_seconds_complete'] and audited['charged_candidate_attempts'] == 12 and
        not audited['unattempted'], 'Complete original-input twelve-attempt audit required')
    baseline_record = c.unseal(campaign/'baseline.json')
    c.require(baseline_record == c.unseal(baseline/'measurements/baseline/measurement.json') and
        provenance['qualification_baseline'] == baseline_accounting(baseline_record) and
        provenance['historical_costs'] == cohort['historical_costs'] and provenance['qualification'] == cohort['qualification'] and
        provenance['charged_candidate_attempts'] == audited['charged_candidate_attempts'] and
        provenance['successful_labels'] == len(audited['successful']),
        'Exact qualification baseline, historical charges and candidate counts required')
    report_value = c.unseal(campaign/'report.json')
    c.require(report_value['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        report_value['native_audit_digest'] == c.digest(audited) and
        report_value['outcomes_sha256'] == c.digest(audited['outcomes']) and report_value['policies'] == POLICIES and
        report_value['runs'] and report_value['runs'][0]['candidate_outer_operation_seconds'] == outer,
        'Exact report source/outcome/audit and authoritative outer-cost bindings required')
    calibration = calibration_diagnostics(public,audited['outcomes'])
    c.require(report_value['calibration_diagnostics'] == provenance['calibration_diagnostics'] == calibration,
        'Exact source-level measured-vs-calibrated saved-cycle diagnostics required')
    derived = _endpoints(public,audited['outcomes'],report_value['runs'],report_value['reference_censored'])
    c.require(stable(derived) == stable(c.unseal(campaign/'endpoints.json')) == stable(report_value['endpoints']),
        'All17-policy measured arithmetic and exact cost endpoints required')
    return campaign,prereg,cohort,provenance,audited,outer,public,context,derived


def report(campaign,output):
    campaign,prereg,cohort,provenance,audited,outer,public,context,endpoints = _campaign_inputs(campaign)
    output = Path(output).resolve()
    fresh(output,campaign,prereg)
    output.mkdir(parents=True)
    from scripts.report_guarded_selection import candidate_rows
    candidates = candidate_rows(audited)
    primary = [r for r in endpoints if r['cap'] == 64 and r['endpoint_kind'] == 'B3-prefix']
    calibration = provenance['calibration_diagnostics']
    lines = ['# Original-input g723 seventeen-policy comparison','',
        f"Known calibrated-benefit assumption: {calibration['unique_candidate_violation_count']} unique successful candidate violations; "
        f"violated={calibration['violated_known_benefit_assumption']}. Every actual label and residual is retained in summary.json.",'',
        'One fresh source; five dependent seeds. No significance, calibration or superiority claim.','',
        '| Policy | Queries | Cycle reduction % | Regret % | Verified reference hits /5 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in primary:
        lines.append(f"| {row['policy']} | {row['budget']} | {100*row['mean_verified_cycle_reduction']:.9f} | "
            f"{100*row['mean_cycle_reduction_regret']:.9f} | {row['verified_reference_hits']} |")
    lines += ['', 'Primary endpoint: +64 LUT4, planned B3 terminal. B3 prefixes remain separate from independently '
        'executed finite B1/B2/B3 terminal horizons in endpoints.csv. All old fourteen controls are preserved.', '',
        f"Native pool: {audited['charged_candidate_attempts']} charged attempts, {len(audited['successful'])} successes; "
        f"{audited['candidate_wall_seconds']:.6f} ledger seconds. History: 99 successes +3 failures /102 charged attempts.", '',
        'Qualification contributes one baseline integrated design and three routes, separately from the99label training corpus and candidate attempts. '
        'Other-policy cost curves are charged replay accounting. Ledger, native command, CLI, observer, fitting and '
        'inference timers have overlapping scopes. UTC and monotonic observations remain separate.', '',
        *['- '+line for line in LIMITATIONS], '']
    (output/'results.md').write_text('\n'.join(lines))
    _csv(output/'endpoints.csv',endpoints)
    _csv(output/'candidates.csv',candidates)
    _csv(output/'primary.csv',primary)
    c.seal(output/'live.json',c.unseal(campaign/'collection/live.json'))
    c.seal(output/'costs.json',dict(historical_costs=provenance['historical_costs'],qualification=provenance['qualification'],
        collection_paired_durations=provenance['collection_paired_durations'],
        qualification_baseline=provenance['qualification_baseline'],
        current={key:audited.get(key) for key in ('candidate_wall_seconds','baseline_wall_seconds','baseline_record_seconds',
            'native_command_count','native_command_seconds')},candidate_outer_operation_seconds=outer,
        timer_scopes_overlap=True,actual_calendar_wall_seconds=None))
    result = dict(candidates=len(candidates),endpoint_summaries=len(endpoints),policies=POLICIES,
        primary=primary,calibration_diagnostics=calibration,new_model_fits=0,new_model_predictions=0,new_native_jobs=0,superiority_established=False)
    c.seal(output/'summary.json',result)
    prior._seal_manifest(output)
    return result


def export_corpus(campaign,output):
    campaign,prereg,cohort,provenance,audited,outer,public,context,_ = _campaign_inputs(campaign)
    output = Path(output).resolve()
    fresh(output,campaign,prereg)
    old_corpus = history(HISTORY)
    c.require(provenance['historical_costs']['source_corpus_sha256'] == c.sha(HISTORY) and
        provenance['historical_costs']['total_candidate_wall_seconds'] == old_corpus['total_candidate_attempt_wall_seconds'] and
        w.GROUP not in old_corpus['independent_workload_groups'] and public[0]['benchmark'] not in old_corpus['contexts'],
        'Exact complete prior corpus and a new independent source required')
    rows,failures = copy.deepcopy(old_corpus['rows']),copy.deepcopy(old_corpus['failed_attempts'])
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    c.require(set(labels) == {r['candidate_id'] for r in public} == set(outer) and
        sum(r['measurement_seconds'] for r in labels.values()) == audited['candidate_wall_seconds'],
        'Complete distinct paid rows and exact ledger sum required')
    for feature in public:
        row = labels[feature['candidate_id']]
        enriched = dict(row,workload_group=w.GROUP,candidate_family=family(row['formula']),
            outer_operation_seconds=outer[row['candidate_id']],
            measurement_timer_scope='recorded monotonic guarded-attempt elapsed; paired UTC/monotonic remain separate')
        if b.validate_outcome(row,feature):
            rows.append(enriched)
        else:
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class') and
                not {'area','device_fits','timing_feasible'} & set(row), 'Classified failure without fabricated hardware labels required')
            enriched['correctness_verified'] = None if row['reference_censored'] else False
            failures.append(enriched)
    all_rows = rows+failures
    c.require(rows[:99] == old_corpus['rows'] and failures[:3] == old_corpus['failed_attempts'] and
        len({r['candidate_id'] for r in all_rows}) == len(all_rows) == 114 and
        len(rows)-99 == len(audited['successful']) and len(failures)-3 == len(audited['failed_or_interrupted']),
        'Preserve old99+3 exactly and append every charged attempt once')
    contexts = copy.deepcopy(old_corpus['contexts']); contexts[public[0]['benchmark']] = context
    groups = sorted({r['workload_group'] for r in all_rows})
    c.require(len(groups) == 13 and len(contexts) == 14, 'Thirteen-source fourteen-context corpus required')
    paired = provenance['collection_paired_durations']
    clock = dict(historical=old_corpus['clock_accounting'],current_paired_collection=paired)
    value = dict(schema='isaforge-consumed-guarded-corpus-v1',scope='Consumed twelve-source history plus twelve paid g723 attempts.',
        rows=rows,failed_attempts=failures,contexts=contexts,successful_labels=len(rows),independent_workload_groups=groups,
        historical_costs=provenance['historical_costs'],preserved_original_rows_digest=c.digest(old_corpus['rows']),
        preserved_original_failed_attempts_digest=c.digest(old_corpus['failed_attempts']),
        new_candidate_attempts=12,total_candidate_attempts=114,new_candidate_wall_seconds=audited['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=old_corpus['total_candidate_attempt_wall_seconds']+audited['candidate_wall_seconds'],
        new_candidate_outer_operation_seconds=sum(outer.values()),qualification_costs=provenance['qualification'],
        new_qualification_baseline=provenance['qualification_baseline'],
        new_calibration_diagnostics=provenance['calibration_diagnostics'],
        new_collection_costs={key:audited.get(key) for key in ('native_command_count','native_command_seconds','baseline_wall_seconds','baseline_record_seconds')},
        historical_qualification_costs=old_corpus.get('qualification_costs'),clock_accounting=clock,
        historical_clock_accounting=old_corpus['clock_accounting'],current_paired_clock_accounting=paired,
        actual_calendar_wall_seconds=None,new_live_native_attempts=3,new_oracle_reference_attempts=9,
        split_unit='Entire source workload and all its contexts, with related-family exclusions.',
        timer_note='Ledger/CLI/observer/native scopes overlap; fitting/inference separate. No uninterrupted wall-time saving established.',
        reference_censored_candidates=sorted(r['candidate_id'] for r in failures if r.get('reference_censored')),
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0)
    output.mkdir(parents=True)
    # Retain the exact previous corpus bytes as well as its unchanged row values.
    shutil.copyfile(HISTORY,output/'historical-corpus.json')
    c.require(c.sha(output/'historical-corpus.json') == c.sha(HISTORY), 'Bytewise historical corpus preservation required')
    c.seal(output/'corpus.json',value)
    c.seal(output/'clock-accounting.json',clock)
    _csv(output/'verified-labels.csv',rows); _csv(output/'failed-attempts.csv',failures)
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(ROOT/SOURCE),previous_manifest_sha256=c.sha(HISTORY.parent/'manifest.json'),
        previous_corpus_sha256=c.sha(HISTORY),campaign_manifest_sha256=c.sha(campaign/'manifest.json'),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),new_model_fits=0,new_model_predictions=0,new_native_jobs=0))
    (output/'README.md').write_text(f'# Consumed corpus including g723\n\n{len(rows)} verified labels, {len(failures)} failures, '
        '114 attempts, thirteen sources and fourteen contexts. Original99+3 rows and exact prior corpus bytes are preserved. '
        'Unknown outcomes retain qualified failure classes without invented labels. All target sources are consumed development data.\n')
    prior._seal_manifest(output)
    return value


def measure(native,candidate):
    native = Path(native).resolve()
    c.require(candidate is not None, 'Candidate required')
    began,status = time.monotonic(),'interrupted'
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        # The gate precedes evaluator construction and is repeated in measure.
        check_native_release(native)
        evaluator = ReleasedEvaluator(native)
        try:
            result = evaluator.measure(candidate)
        finally:
            evaluator.runner.lock.close()
        status = 'success'
        return result
    except Exception:
        status = 'failed'
        raise
    finally:
        if native.exists():
            folder = native/'outer-timing'; folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder/f'{sequence:03d}-measure.json',dict(schema='isaforge-wrapper-outer-time-v1',command='measure',
                candidate=candidate,started_at_utc=stamp,status=status,elapsed_seconds=time.monotonic()-began,
                scope='Complete CLI operation through lock close; excludes Python startup/final timer write; overlaps inner scopes.'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','release','measure','collect','pack','replay','report','export'))
    for name in ('preregistration','native-root','qualification','output','release','collection','campaign'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--candidate')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        result = freeze(args.native_root,args.output,qualification_path=args.qualification)
    elif args.command == 'release':
        result = release(args.preregistration,args.native_root,args.commit,args.output)
    elif args.command == 'measure':
        result = measure(args.root,args.candidate)
    elif args.command == 'collect':
        result = collect(args.preregistration,args.native_root,args.release,args.output)
    elif args.command == 'pack':
        result = pack(args.preregistration,args.native_root,args.collection,args.release,args.output)
    elif args.command == 'replay':
        result = replay(args.campaign,args.output)
    elif args.command == 'report':
        result = report(args.campaign,args.output)
    else:
        corpus = export_corpus(args.campaign,args.output)
        result = {key:corpus[key] for key in ('successful_labels','total_candidate_attempts','independent_workload_groups')}
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
