"""Release-gated 17-policy measured development campaign for Lift CFG-tail."""
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
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c, observed_command as observed
from isaforge import count_selection as count, semantic_selection as semantic
from isaforge import cfg_lift_workload_tail as w, guarded_workload as g, guarded_evidence
from isaforge import factorized_selection_experiment as experiment
from isaforge import finite_selection as f, joint_hardware as j
from isaforge.speedup_corpus import family
from scripts import blind_campaign as prior, live_gp_campaign as live_helpers
from scripts import tacle_selection_campaign as old
from scripts import g723_selection_campaign as shared
from scripts import qualify_cfg_lift_tail as qualifier
from scripts.reproduce_guarded_sha256 import authenticate_files
from scripts.export_guarded_corpus import _csv

SOURCE = 'scripts/lift_selection_campaign.py'
CONTRACT = 'docs/lift-selection-campaign.md'
SCHEMA = 'isaforge-lift-cfg-tail-selection-v1'
HISTORY = ROOT/'results/2026-10-25-thirteen-source-corpus/corpus.json'
OLD_POLICIES = list(old.POLICIES)
POLICIES = [*OLD_POLICIES,*f.POLICIES]
LIVE = dict(policy=f.MYOPIC, seed=0, area_cap=64, clock_mhz=12., budget=3)
HOST_TIMERS = old.HOST_TIMERS | {'acquisition_host_seconds','conditioning_host_seconds',
    'host_monotonic_start_ns','host_monotonic_end_ns','host_monotonic_seconds',
    'initial_joint_construction_host_seconds','mean_initial_model_host_seconds',
    'observer_validation_conditioning_host_seconds','model_validation_refit_host_seconds'}
LIMITATIONS = [
    'Consumed Lift coverage development; not an untouched confirmatory source or superiority evidence.',
    'All seventeen existing controls and equal post-family-exclusion fitting rows are retained; no policy is promoted.',
    'Only fixed_joint_myopic seed0/+64/B3 is live; other controls are sealed post-collection replays, not native adaptive dispatchers.',
    'Original1001 zero-input iterations/checksum4005888 and changed projected-equivalence verifier remain limitations.',
    'Independent GPs, assumed Gaussian noise, calibrated benefit and common Beta device-fit are uncalibrated assumptions.',
    'Correctness/infrastructure failures remain charged without fabricated Gaussian labels; interruptions forbid automatic recovery.',
    'Historical114 attempts, baseline/qualification, target ledgers and host timers are separate overlapping scopes.',
    'No automatic stopping, end-to-end time saving, complete oracle or jointly measured instruction-set claim follows.',
    'A cooperative callback is not an OS sandbox; source/family confirmation and six independent families remain open.']


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
    names = (SOURCE,CONTRACT,shared.SOURCE,old.SOURCE,'scripts/qualify_cfg_lift_tail.py',
        'scripts/live_gp_campaign.py','isaforge/observed_command.py',
        'scripts/report_guarded_selection.py','scripts/export_guarded_corpus.py','scripts/report_budget_campaign.py',
        *prior.SOURCES,*count.SOURCES,*semantic.SOURCES,*f.SOURCES,*plan['source_bindings'])
    return {name:c.sha(ROOT/name) for name in dict.fromkeys(names)}


def qualification_manifest(path):
    """Authenticate the two exact historical manifest copies omitted by v2.

    Existing packs omitted nested manifest.json metadata from their inventories.
    Accept only these exact bytewise copies, transitively authenticated through
    the immutable original/v1 rejection validators; every other omission fails.
    """
    path = Path(path).resolve()
    entries = c.unseal(path/'manifest.json')
    prior._hashes(path,entries)
    c.require(authenticate_files(path,'manifest.json') == entries, 'Qualification manifest changed')
    actual = prior._inventory(path)-{'manifest.json','manifest.json.sha256'}
    missing = actual-set(entries)
    c.require(not set(entries)-actual, 'Qualification inventory references missing artifacts')
    if not missing:
        return {}
    expected = {'sources/'+name+'/manifest.json' for name in
        (w.ORIGINAL_REJECTION,w.PRIOR_CFG_REJECTION)}
    c.require(path == (ROOT/'results/2026-10-25-lift-cfg-tail-qualification').resolve() and missing == expected,
        'Only two exact authenticated historical manifest copies may be omitted')
    qualifier.validate_original_rejection()
    qualifier.validate_prior_cfg_rejection()
    bindings = {}
    for name in sorted(expected):
        canonical = ROOT/name.removeprefix('sources/')
        c.require((path/name).read_bytes() == canonical.read_bytes(),
            'Copied historical manifest differs from authenticated rejection')
        bindings[name] = c.sha(canonical)
    return bindings


def qualification(path, native):
    path = Path(path).resolve()
    c.require(path.is_relative_to(ROOT), 'Repository-local qualification required')
    transitive = qualification_manifest(path)
    protocol, result = c.unseal(path/'protocol.json'), c.unseal(path/'qualification.json')
    prior._hashes(ROOT,protocol['source_bindings'])
    c.require(protocol['schema'] == w.PROTOCOL['schema']+'-qualification' and
        all(protocol[key] == value for key,value in w.PROTOCOL.items() if key != 'schema') and
        result['protocol_sha256'] == c.sha(path/'protocol.json') and
        type(result['target_candidate_attempts']) is int and result['target_candidate_attempts'] == 0 and
        result['status'] == 'accepted' and result['accepted'] == {w.WORKLOAD:str(Path(native).resolve().relative_to(ROOT))},
        'Complete unchanged original-input zero-candidate qualification required')
    rows = result['records']
    c.require(len(rows) == 1 and rows[0]['status'] == 'accepted' and rows[0]['workload'] == w.WORKLOAD and
        rows[0]['context_id'] == c.unseal(Path(native)/'plan.json')['context_id'] and
        [cmd['phase'] for cmd in rows[0]['commands']] == protocol['phases'], 'Complete accepted qualification phases required')
    for cmd in rows[0]['commands']:
        folder = prior._path(path,cmd['observation'])
        record, started = c.unseal(folder/'record.json'), c.unseal(folder/'started.json')
        live_helpers.observed_pair(record,started)
        c.require(record == cmd['record'] and record['status'] == 'success' and record['returncode'] == 0 and
            record['durations'] == observed._durations(record['start'],record['end']) and
            record['metadata'] == dict(workload=w.WORKLOAD,phase=cmd['phase'],protocol_sha256=c.sha(path/'protocol.json')),
            'Qualification observer receipt differs')
        for stream in ('stdout','stderr'):
            c.require(c.sha(folder/(stream+'.txt')) == record[stream+'_sha256'], 'Qualification stream changed')
    seconds = sum(cmd['record']['durations']['monotonic_elapsed_seconds'] for cmd in rows[0]['commands'])
    c.require(seconds == result['recorded_subprocess_monotonic_seconds'], 'Qualification cost differs')
    return dict(path=path.relative_to(ROOT).as_posix(),manifest_sha256=c.sha(path/'manifest.json'),
        protocol_sha256=c.sha(path/'protocol.json'),qualification_sha256=c.sha(path/'qualification.json'),
        setup_subprocess_seconds=seconds,transitive_manifest_bindings=transitive)


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


def audit(native,*,native_lock_held=False):
    w.validate_inputs(native)
    w.check_opportunity(native)
    with w.registration(native):
        # The released evaluator keeps the exclusive native lock open through
        # controller decisions and one-attempt verification. Its in-lock audit
        # must use the guarded core directly instead of trying to take a second
        # shared flock on the same tree.
        return guarded_evidence._audit(native) if native_lock_held else guarded_evidence.audit(native)


def _measure_argv(python_executable,native_root,collection_root,native_name,mode,index):
    argv = [python_executable,SOURCE,'measure','--root',native_root,
        '--candidate',native_name,'--mode',mode]
    if mode == 'adaptive':
        argv += ['--acquisition-proof',str(Path(collection_root)/'acquisitions'/f'{index:02d}.json')]
    return argv


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
        scope='Qualification/setup baseline already measured; counted once separately from110historical training labels and candidate attempts.')


def history(path):
    path = Path(path).resolve()
    c.require(path == HISTORY.resolve(), 'Exact complete110-label historical corpus required')
    prior._manifest(path.parent)
    corpus = c.unseal(path)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 110 and
        len(corpus['failed_attempts']) == 4 and corpus['total_candidate_attempts'] == 114 and
        len(corpus['independent_workload_groups']) == 13 and len(corpus['contexts']) == 14,
        'Complete110-success/4-failure/114-attempt historical corpus required')
    attempts = corpus['rows']+corpus['failed_attempts']
    c.require(len({row['candidate_id'] for row in attempts}) == 114 and
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
    shared = dict(successful_labels=110,failed_attempts=4,total_candidate_attempts=114,
        total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(HISTORY),actual_calendar_wall_seconds=None,clock_accounting=corpus['clock_accounting'])
    costs = dict(historical_training_available=shared,target_baseline=context['baseline_provenance'],qualification=qualified,
        qualification_baseline=baseline_accounting(c.unseal(native/'measurements/baseline/measurement.json')),
        note='All114 historical attempts charged once; ledger, native, CLI, paired-observer and model scopes remain separate.')
    c.seal(folder/'public.json',public); c.seal(folder/'cost-provenance.json',costs)
    bindings = {p.relative_to(ROOT).as_posix():c.sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    bindings[HISTORY.relative_to(ROOT).as_posix()] = c.sha(HISTORY)
    protocol = experiment.freeze(corpus['rows'],public,contexts,folder/'selection',target_workload=w.GROUP,
        target_labels_observed=0,calibration_cost_seconds=prior.evidence._calibration(native)['native_command_seconds'],
        cost_provenance=costs,input_bindings=bindings,scope='consumed-data development')
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
    cohort = dict(schema=SCHEMA,scope="consumed-data development",target_labels_observed=0,target_labels_read=0,
        source_history=HISTORY.relative_to(ROOT).as_posix(),historical_costs=shared,qualification=qualified,
        source_bindings=sources(plan),python_executable=sys.executable,live=LIVE,
        policies=POLICIES,seeds=[0,1,2,3,4],area_caps=[32,64,128],budgets=[1,2,3],clock_mhz=12.,
        gp_settings=copy.deepcopy(b.GP_SETTINGS),semantic_columns=list(semantic.COLUMNS),
        finite_settings=copy.deepcopy(f.SETTINGS),finite_policies=list(f.POLICIES),
        finite_planned_budgets=[1,2,3],finite_terminal_rule='Each B1/B2/B3 independently executed; B3 prefixes separate.',
        fantasy_table_sha256s={str(seed):c.sha(output/'fantasies'/f'seed{seed}.json') for seed in range(5)},
        native_collection_rule='Seal three live fixed_joint_myopic decisions/outcomes before any remaining oracle-reference outcome exists; then collect remainder in frozen public order, one attempt each.',
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

def required_selection(root):
    """Authenticate the unchanged twelve-model package under development scope."""
    root = Path(root)
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol['schema'] == experiment.SCHEMA and
        protocol['scope'] == 'consumed-data development' and protocol['target_workload'] == w.GROUP and
        all(type(protocol[key]) is int and protocol[key] == 0
            for key in ('target_labels_read','target_labels_observed')) and
        protocol['policies'] == [*b.POLICIES,experiment.controls.POLICY,experiment.POLICY],
        'Complete zero-label Lift development selection required')
    prior._hashes(root,protocol['artifacts'])
    return set(protocol['artifacts'])|{'protocol.json','protocol.json.sha256'},protocol


def authenticate(prereg):
    """Complete model/source/cohort validation without opening target outcomes."""
    prereg = Path(prereg).resolve(); entries = prior._manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(cohort['schema'] == SCHEMA and cohort['scope'] == 'consumed-data development' and cohort['live'] == LIVE and cohort['policies'] == POLICIES and
        cohort['seeds'] == [0,1,2,3,4] and cohort['area_caps'] == [32,64,128] and cohort['budgets'] == [1,2,3] and
        cohort['clock_mhz'] == 12. and set(cohort['targets']) == {w.GROUP} and
        all(type(cohort[key]) is int and cohort[key] == 0 for key in ('target_labels_observed','target_labels_read')) and
        cohort['gp_settings'] == b.GP_SETTINGS and cohort['semantic_columns'] == list(semantic.COLUMNS) and
        cohort['finite_settings'] == f.SETTINGS and cohort['finite_policies'] == list(f.POLICIES) and
        cohort['finite_planned_budgets'] == [1,2,3] and
        cohort['finite_terminal_rule'] == 'Each B1/B2/B3 independently executed; B3 prefixes separate.' and
        cohort['primary'] == dict(area_delta_lut4=64,budget=3,clock_mhz=12.) and
        cohort['native_collection_rule'] == 'Seal three live fixed_joint_myopic decisions/outcomes before any remaining oracle-reference outcome exists; then collect remainder in frozen public order, one attempt each.' and
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
    qualified = ROOT/cohort['qualification']['path']
    c.require(qualification_manifest(qualified) == cohort['qualification']['transitive_manifest_bindings'],
        'Exact transitive qualification manifest proof required')
    c.require(c.sha(qualified/'manifest.json') == cohort['qualification']['manifest_sha256'], 'Qualification evidence changed')
    frozen,protocol = required_selection(folder/'selection')
    c.require(protocol['scope'] == 'consumed-data development', 'Consumed Lift development scope required')
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
    c.require(cohort['historical_costs']['successful_labels'] == 110 and cohort['historical_costs']['failed_attempts'] == 4 and
        cohort['historical_costs']['total_candidate_attempts'] == 114 and
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


def check_native_release(native):
    """Authenticate the complete package and the actual remote head per attempt."""
    native = Path(native).resolve()
    plan = w.validate_inputs(native)
    record = c.unseal(native/'release.json')
    prereg = prior._path(ROOT,record['preregistration_root'])
    c.require(not prereg.is_relative_to(native), 'Separate preregistration required')
    released = checked_release(native/'release.json',prereg,native=native)
    _,_,target,_ = authenticate(prereg)
    live_helpers.original_native(native,target)
    c.require(released['context_id'] == plan['context_id'], 'Released native context differs')
    check_baseline(prereg,native)
    remote = subprocess.run(['git','ls-remote','origin','refs/heads/ai-guided-ml'],cwd=ROOT,
        capture_output=True,text=True,check=True,timeout=30)
    c.require(remote.stdout.strip().split() == [released['prelabel_commit'],'refs/heads/ai-guided-ml'],
        'Actual origin/ai-guided-ml head must equal complete prelabel checkpoint')
    return prereg,released


class _NextQuery(Exception):
    pass


def next_live(case, outcomes):
    """Reconstruct only the charged prefix; stop before the next outcome read.

    A sentinel terminates the unchanged finite search at its next provider call.
    The complete proof must already have been validated by the existing paid
    prefix wrapper. No unqueried target observation is supplied to the policy.
    """
    outcomes = copy.deepcopy(list(outcomes))
    c.require(len(outcomes) <= LIVE['budget'] and
        len({r['candidate_id'] for r in outcomes}) == len(outcomes), 'Unique bounded live paid prefix required')
    proofs,used = [],[]
    def provider(row):
        if len(used) == len(outcomes):
            raise _NextQuery()
        value = outcomes[len(used)]
        c.require(value['candidate_id'] == row['candidate_id'], 'Paid prefix differs from frozen live myopic choices')
        b.validate_outcome(value,row)
        used.append(row['candidate_id'])
        return copy.deepcopy(value)
    try:
        trace = shared.finite_search(case,provider,policy=LIVE['policy'],seed=LIVE['seed'],
            area_cap=LIVE['area_cap'],budget=LIVE['budget'],on_acquire=proofs.append)
    except _NextQuery:
        c.require(len(used) == len(outcomes) and len(proofs) == len(outcomes)+1,
            'Exact proof before next provider required')
        return proofs[-1],None
    c.require(len(used) == LIVE['budget'] == len(outcomes), 'Complete live paid prefix required')
    return None,trace


def paid_prefix(native, case, target,*,native_lock_held=False):
    """Every native attempt needs an immutable controller decision and terminal audit."""
    native = Path(native)
    directories = sorted((native/'selection-controller/attempts').glob('*'))
    c.require(all(p.is_dir() and p.name == f'{i:02d}' for i,p in enumerate(directories)),
        'Contiguous controller attempts required; preserve unknown entries')
    audited = audit(native,native_lock_held=native_lock_held)
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    c.require(audited['charged_candidate_attempts'] == len(labels) == len(directories) and
        audited['candidate_wall_seconds_complete'], 'No unobserved or interrupted native attempt permitted')
    names = dict(zip([r['candidate_id'] for r in case['public']],target['native_order']))
    released = c.unseal(native/'release.json')
    paid = []
    for index,folder in enumerate(directories):
        decision,completed = c.unseal(folder/'decision.json'),c.unseal(folder/'completed.json')
        identity = decision['candidate_id']
        c.require(identity in names and identity not in [row['candidate_id'] for row in paid] and
            decision['index'] == index and decision['native_name'] == names[identity] and
            decision['paid_ids_before'] == [row['candidate_id'] for row in paid] and
            completed['decision_sha256'] == c.sha(folder/'decision.json') and
            completed['outcome_sha256'] == c.sha(folder/'outcome.json') and
            completed['ledger_sha256'] == c.sha(native/'attempt-ledger'/(names[identity]+'.json')) and
            c.unseal(folder/'outcome.json') == labels[identity], 'Exact charged controller outcome prefix required')
        c.require(decision['chosen_before_dispatch'] is True and
            decision['manifest_sha256'] == released['manifest_sha256'] and
            decision['release_sha256'] == c.sha(native/'release.json'), 'Decision release binding differs')
        live_trace = c.unseal(native/'selection-controller/live.json') if index >= LIVE['budget'] else None
        proof,_ = choose_dispatch(case,paid,candidate_id=identity,mode=decision['mode'],live_trace=live_trace)
        if proof is not None:
            c.require(c.unseal(folder/'acquisition.json') == proof and
                decision['acquisition_sha256'] == c.sha(folder/'acquisition.json') and
                decision['completed_live_trace_sha256'] is None, 'Exact sealed prior acquisition proof required')
        else:
            c.require(decision['acquisition_sha256'] is None and
                decision['completed_live_trace_sha256'] == c.sha(native/'selection-controller/live.json'),
                'Exact live trace seal required before reference attempt')
        paid.append(copy.deepcopy(labels[identity]))
    c.require(set(labels) == {r['candidate_id'] for r in paid}, 'Native outcomes outside controller prefix')
    return paid


def choose_dispatch(case, paid, *, candidate_id, mode, live_trace=None):
    """Pure scheduling gate; reference order starts after the complete live seal."""
    c.require(mode in ('adaptive','oracle-reference'), 'Explicit dispatch mode required')
    ids = [r['candidate_id'] for r in paid]
    public = case['public']
    c.require(len(ids) == len(set(ids)) and set(ids) <= {r['candidate_id'] for r in public},
        'Unique declared paid candidates required')
    c.require(candidate_id not in ids, 'Candidate already charged; never retry or return a cache hit')
    proof,trace = next_live(case,paid[:LIVE['budget']])
    if len(paid) < LIVE['budget']:
        c.require(mode == 'adaptive' and live_trace is None and
            proof['event']['candidate_id'] == candidate_id, 'Only exact next live acquisition may dispatch')
        return proof,None
    c.require(mode == 'oracle-reference' and live_trace is not None,
        'Seal complete live prefix before reference-only dispatch')
    if 'search' in live_trace:
        c.require(live_trace['schema'] == SCHEMA+'-live-trace' and live_trace['live'] == LIVE and
            live_trace['remaining_outcomes_exist'] is False and
            live_trace['attempted_ids'] == [row['candidate_id'] for row in paid[:LIVE['budget']]] and
            stable(live_trace['search']) == stable(trace),
            'Sealed live trace differs from the exact paid prefix')
    else:
        c.require(stable(live_trace) == stable(trace), 'Sealed live trace differs from the exact paid prefix')
    remaining = [r['candidate_id'] for r in public if r['candidate_id'] not in ids]
    c.require(remaining and candidate_id == remaining[0], 'Reference remainder must follow frozen public order')
    return None,trace


class ReleasedEvaluator(g.Evaluator):
    """A separate candidate-enabled path retaining the qualification-only block.

    The guarded runner's exclusive lock encloses scheduling, proof sealing,
    native dispatch, and terminal audit. A reservation left by a crash prevents
    all further dispatch until an explicit recovery protocol exists.
    """
    def __init__(self,root):
        self._inside_dispatch = False
        check_native_release(root)  # Gate before evaluator construction.
        with w.registration(root):
            super().__init__(root)

    def discover(self):
        with w.registration(self.root):
            return super().discover()

    def measure(self,name,*,mode='adaptive',acquisition_proof=None):
        if name == 'baseline':
            c.require(self._inside_dispatch, 'Standalone baseline dispatch is not part of this campaign')
            with w.registration(self.root):
                return super().measure(name)
        prereg,released = check_native_release(self.root)
        _,_,target,case = authenticate(prereg)
        paid = paid_prefix(self.root,case,target,native_lock_held=True)
        names = dict(zip(target['native_order'],[r['candidate_id'] for r in case['public']]))
        c.require(name in names, 'Candidate outside released twelve-formula pool')
        c.require(not (self.root/'attempt-ledger'/(name+'.json')).exists() and
            not (self.root/'measurements'/name).exists(), 'Candidate already charged; never retry')
        control = self.root/'selection-controller'
        live_path = control/'live.json'
        if len(paid) >= LIVE['budget'] and not live_path.exists():
            _,search = next_live(case,paid[:LIVE['budget']])
            trace = dict(schema=SCHEMA+'-live-trace',search=search,
                attempted_ids=[row['candidate_id'] for row in paid[:LIVE['budget']]],
                finish=observed._endpoint(),remaining_outcomes_exist=False,live=LIVE)
            c.seal(live_path,trace)
        live_trace = c.unseal(live_path) if live_path.exists() else None
        proof,_ = choose_dispatch(case,paid,candidate_id=names[name],mode=mode,live_trace=live_trace)
        if proof is not None and acquisition_proof is not None:
            c.require(stable(acquisition_proof) == stable(proof),
                'Externally sealed acquisition does not match the released paid prefix')
            # Preserve the exact pre-dispatch proof, including its original host
            # timers, so the external observer and native controller share one hash.
            proof = copy.deepcopy(acquisition_proof)
        if acquisition_proof is not None:
            c.require(proof is not None, 'An oracle-reference query cannot carry an acquisition proof')
        folder = control/'attempts'/f'{len(paid):02d}'
        folder.mkdir(parents=True,exist_ok=False)  # Reservation is never overwritten/retried.
        if proof is not None:
            c.seal(folder/'acquisition.json',proof)
        decision = dict(index=len(paid),mode=mode,candidate_id=names[name],native_name=name,
            paid_ids_before=[r['candidate_id'] for r in paid],chosen_before_dispatch=True,
            manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(self.root/'release.json'),
            acquisition_sha256=c.sha(folder/'acquisition.json') if proof is not None else None,
            completed_live_trace_sha256=c.sha(live_path) if live_trace is not None else None,
            started_at_utc=datetime.now(timezone.utc).isoformat())
        c.seal(folder/'decision.json',decision)
        error = None
        self._inside_dispatch = True
        try:
            with w.registration(self.root):
                super().measure(name)
        except Exception as caught:
            error = caught  # Terminal charged failures may continue; interruptions propagate.
        finally:
            self._inside_dispatch = False
        audited = audit(self.root,native_lock_held=True)
        values = {row['candidate_id']:row for row in audited['outcomes']}
        expected = {row['candidate_id'] for row in paid} | {names[name]}
        c.require(audited['charged_candidate_attempts'] == len(paid)+1 and set(values) == expected and
            audited['candidate_wall_seconds_complete'], 'One terminal charged outcome required; preserve reservation on failure')
        outcome = values[names[name]]
        public = next(row for row in case['public'] if row['candidate_id'] == names[name])
        success = b.validate_outcome(outcome,public)
        c.require((error is None) == success, 'Native exception and charged outcome disagree')
        c.seal(folder/'outcome.json',outcome)
        c.seal(folder/'completed.json',dict(decision_sha256=c.sha(folder/'decision.json'),
            outcome_sha256=c.sha(folder/'outcome.json'),
            ledger_sha256=c.sha(self.root/'attempt-ledger'/(name+'.json')),
            terminal_status='success' if success else 'failed',
            native_error=repr(error) if error is not None else None))
        return outcome


def measure(native,candidate,*,mode='adaptive',acquisition_proof=None):
    """Run one released candidate and preserve the complete CLI operation timer."""
    native = Path(native).resolve()
    c.require(candidate is not None and mode in ('adaptive','oracle-reference'),
        'Candidate and explicit dispatch mode required')
    started = time.monotonic()
    stamp = datetime.now(timezone.utc).isoformat()
    status = 'interrupted'
    try:
        evaluator = ReleasedEvaluator(native)
        try:
            supplied = c.unseal(acquisition_proof) if acquisition_proof is not None else None
            result = evaluator.measure(candidate,mode=mode,acquisition_proof=supplied)
        finally:
            evaluator.runner.lock.close()
        status = 'failed' if result.get('status') == 'failed' else 'success'
        return result
    except Exception:
        status = 'failed'
        raise
    finally:
        if native.exists():
            folder = native/'outer-timing'; folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob('*.json')))
            c.seal(folder/f'{sequence:03d}-measure.json',dict(schema='isaforge-wrapper-outer-time-v1',
                command='measure',candidate=candidate,mode=mode,started_at_utc=stamp,
                status=status,elapsed_seconds=time.monotonic()-started,
                scope='Complete CLI operation through lock close; excludes Python startup/final timer write; overlaps inner scopes.'))


def collect(prereg,native,release_path,output):
    """Measure the three sealed live choices, then the frozen public-order remainder."""
    prereg,native,release_path,output = (Path(p).resolve() for p in (prereg,native,release_path,output))
    cohort,_,target,case = authenticate(prereg)
    live_helpers.original_native(native,target)
    fresh(output,prereg,native,release_path,ROOT/cohort['qualification']['path'])
    prior._zero(native); check_baseline(prereg,native)
    checked_release(release_path,prereg,native=native); check_native_release(native)
    output.mkdir(parents=True)
    paid,trace_hash = [],None
    rows = {row['candidate_id']:row for row in case['public']}
    names = dict(zip(rows,target['native_order']))
    whole = dict(schema=SCHEMA+'-collection',status='started',start=observed._endpoint(),
        observer_pid=os.getpid(),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        release_sha256=c.sha(release_path),live=LIVE,dispatched_ids=[],
        native_root=str(native),collection_root=str(output))
    c.seal(output/'collection.json',whole)

    def dispatch(identity,index):
        nonlocal trace_hash
        mode = 'adaptive' if index < LIVE['budget'] else 'oracle-reference'
        proof = None
        if mode == 'adaptive':
            proof,_ = next_live(case,[c.unseal(output/'queries'/f'{i:02d}'/'outcome.json') for i in range(index)])
            c.require(proof['event']['candidate_id'] == identity and
                proof['event']['policy'] == LIVE['policy'] and
                proof['event']['charged_before_query'] == index,
                'Seal exact live model choice before native dispatch')
            c.seal(output/'acquisitions'/f'{index:02d}.json',proof)
        else:
            live_path = output/'live.json'
            if not live_path.exists():
                _,search = next_live(case,[c.unseal(output/'queries'/f'{i:02d}'/'outcome.json')
                    for i in range(LIVE['budget'])])
                c.require(search is not None, 'Complete live B3 trace required before reference outcomes')
                trace = dict(schema=SCHEMA+'-live-trace',search=search,
                    attempted_ids=list(paid[:LIVE['budget']]),finish=observed._endpoint(),
                    remaining_outcomes_exist=False,live=LIVE)
                c.seal(live_path,trace)
                native_live = native/'selection-controller/live.json'
                if not native_live.exists():
                    c.seal(native_live,trace)
                trace_hash = c.sha(live_path)
            c.require(identity == next(row['candidate_id'] for row in case['public'] if row['candidate_id'] not in paid),
                'Reference remainder must follow frozen public order')
        folder = output/'queries'/f'{index:02d}'
        folder.mkdir(parents=True,exist_ok=False)
        decision = dict(index=index,mode=mode,candidate_id=identity,native_name=names[identity],
            paid_ids_before=list(paid),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
            release_sha256=c.sha(release_path),completed_live_trace_sha256=trace_hash if mode == 'oracle-reference' else None,
            acquisition_sha256=c.sha(output/'acquisitions'/f'{index:02d}.json') if proof is not None else None,
            chosen_before_dispatch=True)
        c.seal(folder/'decision.json',decision)
        whole['dispatched_ids'].append(identity)
        before = set((native/'outer-timing').glob('*.json'))
        argv = [cohort['python_executable'],SOURCE,'measure','--root',str(native),
            '--candidate',names[identity],'--mode',mode]
        if proof is not None:
            argv += ['--acquisition-proof',str(output/'acquisitions'/f'{index:02d}.json')]
        command = observed.run(argv,folder/'command',cwd=ROOT,metadata=decision,timeout_seconds=3600)
        c.require(command['status'] in ('success','nonzero_exit'),
            'Interrupted/timeout native operation is charged and collection stops; never retry')
        audited = audit(native)
        labels = {value['candidate_id']:value for value in audited['outcomes']}
        expected = set(paid+[identity])
        c.require(audited['charged_candidate_attempts'] == index+1 and set(labels) == expected and
            audited['candidate_wall_seconds_complete'], 'Only exact paid terminal outcomes may reach the controller')
        value = labels[identity]
        b.validate_outcome(value,rows[identity])
        added = set((native/'outer-timing').glob('*.json'))-before
        c.require(len(added) == 1, 'Exactly one complete CLI operation timer per candidate required')
        cli = next(iter(added)); ledger = native/'attempt-ledger'/(names[identity]+'.json')
        c.require((command['returncode'] == 0) == (c.unseal(ledger)['status'] == 'success'),
            'CLI exit and guarded attempt-ledger status differ')
        controller = native/'selection-controller/attempts'/f'{index:02d}'
        native_decision = c.unseal(controller/'decision.json')
        c.require(native_decision['candidate_id'] == identity and native_decision['mode'] == mode and
            native_decision['chosen_before_dispatch'] is True and
            native_decision['paid_ids_before'] == paid and
            native_decision['acquisition_sha256'] == decision['acquisition_sha256'] and
            native_decision['completed_live_trace_sha256'] == decision['completed_live_trace_sha256'],
            'Native controller decision differs from paired external receipt')
        if proof is not None:
            c.require(c.unseal(controller/'acquisition.json') == proof, 'Native acquisition differs from sealed parent proof')
        elif mode == 'oracle-reference':
            c.require(stable(c.unseal(native/'selection-controller/live.json')) ==
                stable(c.unseal(output/'live.json')), 'Native and external complete live trace differ')
        c.seal(folder/'outcome.json',value); c.seal(folder/'partial-audit.json',audited)
        c.seal(folder/'completed.json',dict(candidate_id=identity,audited_paid_ids=sorted(expected),
            ledger_sha256=c.sha(ledger),cli_timer=cli.relative_to(native).as_posix(),
            cli_timer_sha256=c.sha(cli),outcome_sha256=c.sha(folder/'outcome.json'),
            partial_audit_digest=c.digest(audited)))
        paid.append(identity)
        print(json.dumps(dict(query=len(paid),mode=mode,name=names[identity],
            speedup=value.get('speedup'),area_delta_lut4=value.get('area_delta_lut4'),
            status=value.get('status','success'))),flush=True)

    try:
        while len(paid) < len(case['public']):
            index = len(paid)
            if index < LIVE['budget']:
                proof,_ = next_live(case,[c.unseal(output/'queries'/f'{i:02d}'/'outcome.json')
                    for i in range(index)])
                identity = proof['event']['candidate_id']
            else:
                identity = next(candidate['candidate_id'] for candidate in case['public'] if candidate['candidate_id'] not in paid)
            dispatch(identity,index)
        trace = c.unseal(output/'live.json')
        whole.update(status='complete',paid_ids=paid,live_trace_sha256=c.sha(output/'live.json'))
    except BaseException as error:
        whole.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
            error_type=type(error).__name__,error=repr(error),paid_ids=paid)
        raise
    finally:
        whole['end'] = observed._endpoint()
        whole['durations'] = observed._durations(whole['start'],whole['end'])
        c.seal(output/'collection.json',whole); prior._seal_manifest(output)
    return whole


def check_collection(prereg,native,collection,release_path):
    prereg,native,collection,release_path = (Path(p).resolve() for p in (prereg,native,collection,release_path))
    prior._manifest(collection)
    cohort,_,target,case = authenticate(prereg)
    released = checked_release(release_path,prereg,native=native)
    audited = audit(native)
    experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole = c.unseal(collection/'collection.json')
    c.require(whole['status'] == 'complete' and whole['live'] == LIVE and
        whole['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        whole['release_sha256'] == c.sha(release_path) and
        whole['durations'] == observed._durations(whole['start'],whole['end']),
        'Complete paired Lift collection required')
    paid = whole['paid_ids']
    logical_native_root,logical_collection_root = whole.get('native_root'),whole.get('collection_root')
    c.require(isinstance(logical_native_root,str) and Path(logical_native_root).is_absolute() and
        Path(logical_native_root).resolve() == Path(target['original_root']).resolve() and
        isinstance(logical_collection_root,str) and Path(logical_collection_root).is_absolute(),
        'Frozen absolute native and collection command roots required')
    c.require(whole['dispatched_ids'] == paid and len(paid) == len(set(paid)) == len(case['public']) and
        set(paid) == set(names), 'Every candidate attempted exactly once')
    trace = c.unseal(collection/'live.json')
    c.require(whole['live_trace_sha256'] == c.sha(collection/'live.json') and
        trace['remaining_outcomes_exist'] is False and trace['attempted_ids'] == paid[:LIVE['budget']] and
        len(trace['attempted_ids']) == LIVE['budget'], 'Sealed live prefix before reference outcomes required')
    outer,times = {},{}
    previous_end = whole['start']['monotonic_after_ns']; timer_names = set()
    native_receipts = c.unseal(native/'commands.json')
    for index,identity in enumerate(paid):
        folder = collection/'queries'/f'{index:02d}'
        decision,completed = c.unseal(folder/'decision.json'),c.unseal(folder/'completed.json')
        command,started = c.unseal(folder/'command/record.json'),c.unseal(folder/'command/started.json')
        live_helpers.observed_pair(command,started)
        mode = 'adaptive' if index < LIVE['budget'] else 'oracle-reference'
        acquisition_path = collection/'acquisitions'/f'{index:02d}.json'
        expected = dict(index=index,mode=mode,candidate_id=identity,native_name=names[identity],
            paid_ids_before=paid[:index],prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
            release_sha256=c.sha(release_path),
            completed_live_trace_sha256=c.sha(collection/'live.json') if index >= LIVE['budget'] else None,
            acquisition_sha256=c.sha(acquisition_path) if index < LIVE['budget'] else None,
            chosen_before_dispatch=True)
        argv = _measure_argv(cohort['python_executable'],logical_native_root,logical_collection_root,
            names[identity],mode,index)
        argv_hash = hashlib.sha256(json.dumps(argv,sort_keys=True,allow_nan=False,
            separators=(',',':')).encode()).hexdigest()
        c.require(decision == expected == command['metadata'] == started['metadata'] and
            command['argv_sha256'] == argv_hash and command['observer_pid'] == whole['observer_pid'] and
            command['status'] in ('success','nonzero_exit') and
            previous_end <= command['start']['monotonic_before_ns'] and
            command['end']['monotonic_after_ns'] <= whole['end']['monotonic_after_ns'] and
            command['durations'] == observed._durations(command['start'],command['end']) and
            command['durations']['monotonic_endpoints_ordered'],
            'Source-bound serial paid receipt differs')
        c.require(prior._utc(command['start']['utc_iso']) >= prior._utc(released['released_at_utc']),
            'Candidate command predates frozen release')
        for stream in ('stdout','stderr'):
            c.require(c.sha(folder/'command'/(stream+'.txt')) == command[stream+'_sha256'],
                'Observed output stream changed')
        ledger_path = native/'attempt-ledger'/(names[identity]+'.json'); ledger = c.unseal(ledger_path)
        partial = c.unseal(folder/'partial-audit.json')
        prefix = {row['candidate_id']:row for row in partial['outcomes']}
        c.require((command['returncode'] == 0) == (ledger['status'] == 'success') and
            ledger['status'] in ('success','failed') and partial['context_id'] == audited['context_id'] and
            partial['charged_candidate_attempts'] == index+1 and partial['candidate_wall_seconds_complete'] and
            set(prefix) == set(paid[:index+1]) and all(value == labels[key] for key,value in prefix.items()) and
            partial['native_command_count'] == ledger['receipt_end'] and
            partial['native_command_seconds'] == sum(row['elapsed_seconds'] for row in native_receipts[:ledger['receipt_end']]) and
            c.unseal(folder/'outcome.json') == labels[identity] and
            completed['outcome_sha256'] == c.sha(folder/'outcome.json') and
            completed['partial_audit_digest'] == c.digest(partial) and
            completed['ledger_sha256'] == c.sha(ledger_path) and completed['candidate_id'] == identity and
            completed['audited_paid_ids'] == sorted(paid[:index+1]),
            'Exact charged paid prefix, native receipt span or outcome differs')
        cli = prior._path(native,completed['cli_timer']); cli_record = c.unseal(cli)
        c.require(completed['cli_timer'] not in timer_names and c.sha(cli) == completed['cli_timer_sha256'] and
            cli_record['command'] == 'measure' and cli_record['candidate'] == names[identity] and
            cli_record['mode'] == mode and command['durations']['monotonic_elapsed_seconds'] >=
            cli_record['elapsed_seconds'] >= labels[identity]['measurement_seconds'],
            'Nested observed attempt timer scopes differ')
        timer_names.add(completed['cli_timer']); times[identity] = cli_record['elapsed_seconds']
        outer[identity] = command['durations']['monotonic_elapsed_seconds']
        controller = native/'selection-controller/attempts'/f'{index:02d}'
        native_decision = c.unseal(controller/'decision.json')
        c.require(native_decision['candidate_id'] == identity and native_decision['mode'] == mode and
            native_decision['paid_ids_before'] == paid[:index] and
            native_decision['manifest_sha256'] == released['manifest_sha256'] and
            native_decision['release_sha256'] == c.sha(native/'release.json') and
            native_decision['acquisition_sha256'] == expected['acquisition_sha256'] and
            native_decision['completed_live_trace_sha256'] == expected['completed_live_trace_sha256'],
            'Native controller decision differs from release/external receipt')
        if index < LIVE['budget']:
            c.require(c.unseal(controller/'acquisition.json') == c.unseal(acquisition_path),
                'Native live acquisition differs from pre-dispatch proof')
        else:
            c.require(stable(c.unseal(native/'selection-controller/live.json')) == stable(trace),
                'Native complete live trace differs from reference gate')
        if index < LIVE['budget']:
            c.require(command['end']['monotonic_after_ns'] <= trace['finish']['monotonic_before_ns'],
                'Live query occurred after its trace seal')
        else:
            c.require(trace['finish']['monotonic_after_ns'] <= command['start']['monotonic_before_ns'],
                'Reference outcome preceded live trace seal')
        previous_end = command['end']['monotonic_after_ns']
    actual_timers = {p.relative_to(native).as_posix() for p in (native/'outer-timing').glob('*.json')
        if c.unseal(p).get('command') == 'measure'}
    c.require(actual_timers == timer_names, 'Unobserved candidate CLI operation or missing timer')
    used,replay_proofs = [],[]
    def replay_provider(row):
        c.require(len(used) < LIVE['budget'] and row['candidate_id'] == paid[len(used)],
            'Frozen live prefix differs on replay')
        used.append(row['candidate_id'])
        return labels[row['candidate_id']]
    run = shared.finite_search(case,replay_provider,policy=LIVE['policy'],seed=LIVE['seed'],
        area_cap=LIVE['area_cap'],budget=LIVE['budget'],on_acquire=replay_proofs.append)
    c.require(len(used) == LIVE['budget'] and stable(run) == stable(trace['search']) and
        len(replay_proofs) == LIVE['budget'] and all(stable(proof) ==
        stable(c.unseal(collection/'acquisitions'/f'{i:02d}.json')) for i,proof in enumerate(replay_proofs)),
        'Exact live model state, acquisition proofs and paid-prefix replay required')
    return audited,outer,trace,whole


def _endpoints(public,outcomes,runs,censored):
    """Validate verified-incumbent, oracle-regret, failure and paid-cost curves."""
    features = {row['candidate_id']:row for row in public}
    labels = {row['candidate_id']:row for row in outcomes}
    c.require(set(labels) == set(features) and len(features) == len(public) == len(outcomes),
        'Complete unique outcome/public pool required')
    actual_censored = False
    for identity,row in labels.items():
        if not b.validate_outcome(row,features[identity]):
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class') and
                not {'area','device_fits','timing_feasible'} & set(row),
                'Classified failure without fabricated hardware labels required')
            actual_censored |= row['reference_censored']
    c.require(type(censored) is bool and actual_censored == censored, 'Exact full-pool reference censorship required')
    expected = {(policy,cap,seed,budget) for policy in POLICIES for cap in (32,64,128)
        for seed in range(5) for budget in ((1,2,3) if policy in f.POLICIES else (3,))}
    keys = [(run['policy'],run['cap'],run['seed'],run.get('planned_budget',3)) for run in runs]
    c.require(len(keys) == len(expected) and set(keys) == expected,
        'Complete seventeen-policy finite-horizon run grid required')
    outer = runs[0]['candidate_outer_operation_seconds']
    c.require(set(outer) == set(labels) and all(type(value) in (int,float) and math.isfinite(value) and
        value >= labels[key]['measurement_seconds'] for key,value in outer.items()),
        'Complete measured CLI-operation costs required')
    points = []
    for run in runs:
        budget = run.get('planned_budget',3)
        c.require(len(run['curve']) == budget and [point['budget'] for point in run['curve']] ==
            list(range(1,budget+1)) and run['candidate_outer_operation_seconds'] == outer,
            'Exact planned trajectory and common cost map required')
        terminal = run['curve'][-1]['attempted_ids']
        for point in run['curve']:
            paid = point['attempted_ids']
            c.require(len(paid) == len(set(paid)) == point['budget'] and set(paid) <= set(labels) and
                paid == terminal[:point['budget']], 'Exact unique charged query prefix required')
            attempted = [labels[identity] for identity in paid]
            best = max([1.]+[row['speedup'] for row in attempted if b._feasible(row,run['cap'],LIVE['clock_mhz'])])
            c.require(point['best_speedup'] == best and
                point['target_measurement_seconds'] == sum(row['measurement_seconds'] for row in attempted) and
                point['target_outer_operation_seconds'] == sum(outer[identity] for identity in paid),
                'Measured incumbent and exact paid costs differ')
            known = sum((row.get('status','success') == 'success' and not b._feasible(row,run['cap'],LIVE['clock_mhz'])) or
                (row.get('status') == 'failed' and not row['reference_censored']) for row in attempted)
            unknown = sum(row.get('status') == 'failed' and row['reference_censored'] for row in attempted)
            c.require(point['known_infeasible_attempts'] == known and point['unknown_attempts'] == unknown and
                type(point.get('inference_seconds',0.)) in (int,float) and
                math.isfinite(point.get('inference_seconds',0.)) and point.get('inference_seconds',0.) >= 0,
                'Known-invalid/unknown failures or host inference cost differ')
            reference = max([1.]+[row['speedup'] for row in outcomes
                if b._feasible(row,run['cap'],LIVE['clock_mhz'])])
            common = dict(point,policy=run['policy'],cap=run['cap'],seed=run['seed'],planned_budget=budget,
                verified_cycle_reduction=1-1/best,reference_speedup=reference,
                reference_cycle_reduction=1-1/reference,cycle_reduction_regret=1/best-1/reference,
                reference_complete=not censored,regret_is_lower_bound=censored)
            if budget == 3:
                points.append(dict(common,endpoint_kind='B3-prefix'))
            if run['policy'] in f.POLICIES and point['budget'] == budget:
                points.append(dict(common,endpoint_kind='horizon-aware-terminal'))
    groups = {}
    for point in points:
        key = tuple(point[name] for name in ('policy','cap','budget','planned_budget','endpoint_kind'))
        groups.setdefault(key,[]).append(point)
    summary = []
    for key,values in groups.items():
        c.require(sorted(row['seed'] for row in values) == list(range(5)), 'Five fixed dependent seeds per endpoint required')
        item = dict(zip(('policy','cap','budget','planned_budget','endpoint_kind'),key))
        item.update(dependent_seed_count=5,reference_speedup=values[0]['reference_speedup'],
            reference_cycle_reduction=values[0]['reference_cycle_reduction'],
            reference_complete=not censored,regret_is_lower_bound=censored)
        for field in ('best_speedup','verified_cycle_reduction','cycle_reduction_regret','target_measurement_seconds',
                      'target_outer_operation_seconds','known_infeasible_attempts','unknown_attempts','inference_seconds'):
            item['mean_'+field] = statistics.mean(point.get(field,0.) for point in values)
        item['verified_reference_hits'] = sum(point['best_speedup'] == point['reference_speedup'] for point in values)
        summary.append(item)
    return summary


def evaluate(prereg,selection,audited,outer,output,*,verify=False):
    """Replay all seventeen fixed policies after labels; never refit on Lift labels."""
    prereg,selection,output = map(Path,(prereg,selection,output))
    cohort,_,_,case = authenticate(prereg)
    censored = experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    c.require(set(outer) == {row['candidate_id'] for row in case['public']} and
        all(outer[row['candidate_id']] >= row['measurement_seconds'] for row in audited['outcomes']),
        'Complete charged native/outer durations required')
    c.require(verify or not output.exists(), 'Preserve existing complete selection report')
    base = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=outer,verify=verify)
    runs = copy.deepcopy(base['runs'])
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    for policy in (*OLD_POLICIES[-2:],*f.POLICIES):
        for seed in cohort['seeds']:
            for cap in cohort['area_caps']:
                budgets = cohort['budgets'] if policy in f.POLICIES else (3,)
                for budget in budgets:
                    released = []
                    trajectory = output.parent/'replay-acquisitions'/policy/f'B{budget}-cap{cap}-seed{seed}'
                    def acquire(proof):
                        event = proof['event']
                        c.require(event['charged_before_query'] == len(released) and
                            event['attempted_ids_before_query'] == released,
                            'Only the charged replay prefix may reach acquisition')
                        path = trajectory/f'{len(released):02d}.json'
                        if verify:
                            c.require(c.unseal(path) == proof, 'Frozen acquisition proof changed during replay')
                        else:
                            c.seal(path,proof)
                    def provider(row):
                        proof = c.unseal(trajectory/f'{len(released):02d}.json')
                        c.require(proof['event']['candidate_id'] == row['candidate_id'] and
                            row['candidate_id'] not in released,
                            'Seal policy choice before releasing its measured outcome')
                        released.append(row['candidate_id'])
                        return copy.deepcopy(labels[row['candidate_id']])
                    if policy in f.POLICIES:
                        searched = shared.finite_search(case,provider,policy=policy,seed=seed,
                            area_cap=cap,budget=budget,on_acquire=acquire)
                    else:
                        with _old_workload():
                            searched = count_search(case,provider,policy=policy,seed=seed,
                                area_cap=cap,on_acquire=acquire)
                    c.require(len(released) == len(set(released)) == budget,
                        'Exact planned query count required')
                    runs.append(dict(target=w.GROUP,cap=cap,seed=seed,**searched))
    with _old_workload():
        for run in runs:
            old.annotate(run,labels,outer,run['cap'])
    endpoints = _endpoints(case['public'],audited['outcomes'],runs,censored)
    result = dict(schema=SCHEMA+'-report',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        outcomes_sha256=c.digest(audited['outcomes']),native_audit_digest=c.digest(audited),
        policies=POLICIES,runs=runs,endpoints=endpoints,reference_censored=censored,
        calibration_diagnostics=shared.calibration_diagnostics(case['public'],audited['outcomes']),
        trajectories=len(runs),endpoint_points=sum(len(run['curve']) for run in runs),
        endpoint_summaries=len(endpoints),new_native_jobs=0,superiority_established=False,
        limitations=LIMITATIONS)
    if verify:
        c.require(stable(result) == stable(c.unseal(output)), 'Fixed-policy replay differs from sealed report')
    else:
        c.seal(output,result)
    return result


def pack(prereg,native,collection,release_path,output):
    prereg,native,collection,release_path,output = (Path(p).resolve()
        for p in (prereg,native,collection,release_path,output))
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
    report = evaluate(prereg,selection,audited,outer,output/'report.json')
    refits = verify_frozen_selection(prereg,selection,reports_required=True)
    with w.registration(native):
        guarded_evidence.pack(native,output/'native',prelabel_commit=None)
    c.seal(output/'audit.json',audited); c.seal(output/'outer-times.json',outer)
    c.seal(output/'endpoints.json',report['endpoints'])
    baseline = c.unseal(native/'measurements/baseline/measurement.json')
    records = {row['name']:c.unseal(native/'measurements'/row['name']/'measurement.json')
        for row in audited['successful']}
    c.seal(output/'baseline.json',baseline); c.seal(output/'native-measurements.json',records)
    provenance = dict(schema=SCHEMA+'-campaign',prelabel_commit=released['prelabel_commit'],
        preregistration=prereg.relative_to(ROOT).as_posix(),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        source_bindings=cohort['source_bindings'],workload_group=w.GROUP,live=LIVE,
        live_best=trace['search']['curve'][-1],live_native_attempts=LIVE['budget'],
        charged_candidate_attempts=audited['charged_candidate_attempts'],successful_labels=len(audited['successful']),
        historical_costs=cohort['historical_costs'],qualification=cohort['qualification'],
        qualification_baseline=baseline_accounting(baseline),calibration_diagnostics=report['calibration_diagnostics'],
        collection_paired_durations=whole['durations'],refits=refits,trajectories=report['trajectories'],
        endpoint_points=report['endpoint_points'],endpoint_summaries=report['endpoint_summaries'],
        live_native_dispatch=True,other_policies_native_remeasured=False,actual_calendar_wall_seconds=None,
        new_native_jobs=0,limitations=LIMITATIONS)
    c.seal(output/'provenance.json',provenance); prior._seal_manifest(output)
    return provenance


def verify_frozen_selection(prereg,selection,*,reports_required=False):
    """Bind copied post-label selection artifacts to their preregistered bytes."""
    source = Path(prereg)/'targets'/w.GROUP/'selection'
    selection = Path(selection)
    frozen,_ = required_selection(source)
    inventory = prior._inventory(selection)
    derived_reports = inventory-frozen
    valid_reports = derived_reports == prior.FINAL_REPORTS if reports_required else derived_reports in (set(),prior.FINAL_REPORTS)
    c.require(not (frozen-inventory) and valid_reports,
        'Complete frozen model package and exact optional/final report inventory required')
    for name in frozen:
        c.require(c.sha(selection/name) == c.sha(source/name),
            'Frozen model changed after labels: '+name)
    began = time.monotonic()
    result = prior.verify_refits(selection)
    return dict(result,model_validation_refit_host_seconds=time.monotonic()-began)


def restore_native_snapshot(snapshot,destination):
    """Restore and independently audit archived raw evidence with root-bound checks."""
    snapshot,destination = Path(snapshot).resolve(),Path(destination).resolve()
    with w.registration(destination):
        restored = guarded_evidence.replay(snapshot,destination)
    w.validate_inputs(destination)
    with w.registration(destination):
        audited = audit(destination)
    c.require(restored == audited, 'Restored archive receipt differs from raw native audit')
    return audited


def _campaign_inputs(campaign):
    campaign = Path(campaign).resolve(); prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json')
    prereg = prior._path(ROOT,provenance['preregistration'])
    cohort,_,target,_ = authenticate(prereg)
    c.require(provenance['schema'] == SCHEMA+'-campaign' and
        provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        provenance['source_bindings'] == cohort['source_bindings'] and provenance['live'] == LIVE,
        'Complete released Lift campaign/prelabel binding required')
    prior._hashes(ROOT,cohort['source_bindings'])
    checked_release(campaign/'release.json',prereg)
    audited = c.unseal(campaign/'audit.json'); outer = c.unseal(campaign/'outer-times.json')
    public,context = c.unseal(prereg/'targets'/w.GROUP/'baseline/public.json'),c.unseal(prereg/'targets'/w.GROUP/'baseline/context.json')
    c.require(audited['public'] == public and audited['context_id'] == context['context_id'] and
        audited['attempt_collection_complete'] and audited['candidate_wall_seconds_complete'] and
        audited['charged_candidate_attempts'] == len(public) and not audited['unattempted'] and
        provenance['charged_candidate_attempts'] == len(public) and
        provenance['successful_labels'] == len(audited['successful']) and
        c.unseal(campaign/'baseline.json') == c.unseal(prereg/'targets'/w.GROUP/'baseline/measurements/baseline/measurement.json'),
        'Complete original-input candidate collection required')
    selection_refits = verify_frozen_selection(prereg,campaign/'selection',reports_required=True)
    c.require(stable(provenance['refits']) == stable(selection_refits),
        'Frozen model refits differ from campaign provenance')
    with tempfile.TemporaryDirectory(prefix='isaforge-lift-campaign-audit-') as temporary:
        native_root = Path(temporary)/'native'
        raw_audit = restore_native_snapshot(campaign/'native',native_root)
        check_baseline(prereg,native_root)
        checked,_,_,_ = check_collection(prereg,native_root,campaign/'collection',campaign/'release.json')
        c.require(raw_audit == checked == audited,
            'Restored raw native snapshot and paid collection audits differ')
    report = c.unseal(campaign/'report.json')
    c.require(report['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        report['outcomes_sha256'] == c.digest(audited['outcomes']) and
        report['native_audit_digest'] == c.digest(audited) and report['policies'] == POLICIES and
        report['runs'] and report['runs'][0]['candidate_outer_operation_seconds'] == outer,
        'Sealed policy report/outcomes/costs differ')
    endpoints = _endpoints(public,audited['outcomes'],report['runs'],report['reference_censored'])
    c.require(stable(endpoints) == stable(c.unseal(campaign/'endpoints.json')) == stable(report['endpoints']),
        'All seventeen-policy measured endpoints differ')
    return campaign,prereg,cohort,provenance,audited,outer,public,context,endpoints,selection_refits


def report(campaign,output):
    campaign,prereg,cohort,provenance,audited,outer,public,context,endpoints,selection_refits = _campaign_inputs(campaign)
    output = Path(output).resolve(); fresh(output,campaign,prereg); output.mkdir(parents=True)
    from scripts.report_guarded_selection import candidate_rows
    candidates = candidate_rows(audited)
    primary = [row for row in endpoints if row['cap'] == 64 and row['endpoint_kind'] == 'B3-prefix']
    lines = ['# Lift seventeen-policy measured selection comparison','',
        'Consumed engineering-transfer evidence; Lift informed this development and is not an untouched test workload. '
        'Five seeds are dependent repetitions, not five independent programs. No superiority claim follows.', '',
        '| Policy | Queries | Verified cycle reduction (%) | Regret to measured pool (%) | Reference hits / 5 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in primary:
        lines.append(f"| {row['policy']} | {row['budget']} | {100*row['mean_verified_cycle_reduction']:.9f} | "
            f"{100*row['mean_cycle_reduction_regret']:.9f} | {row['verified_reference_hits']} |")
    lines += ['', 'Primary constraint: +64 LUT4, 12 MHz, B3 prefix. Finite B1/B2/B3 runs are also independently '
        'executed and retained as terminal-horizon endpoints. Each replay exposes a label only after the policy '
        'seals its next choice; retrospective policy outcomes are not additional native measurements.', '',
        f"Pool: {audited['charged_candidate_attempts']} charged attempts, {len(audited['successful'])} verified labels, "
        f"{len(audited['failed_or_interrupted'])} charged failures; native attempt time "
        f"{audited['candidate_wall_seconds']:.6f}s and paired observed CLI operations "
        f"{sum(outer.values()):.6f}s. Historical corpus: 110 verified labels, four failures /114 attempts.", '',
        'The accepted qualification baseline is counted separately from candidate labels. Ledger, CLI, observer, '
        'synthesis, setup, model-fit and inference timers overlap or represent distinct scopes; they are never '
        'summed into a single claimed project-time saving. Frozen-model reproducibility checks run deterministic '
        'historical refits after collection; their count and host time are recorded separately and are not new '
        'training or selection-model promotion. Full-pool regret is labeled a lower bound whenever an '
        f"infrastructure/correctness outcome censors the oracle. This report invocation's deterministic model-validation "
        f"refits took {selection_refits['model_validation_refit_host_seconds']:.6f} host seconds.", '',
        *['- '+line for line in LIMITATIONS], '']
    (output/'results.md').write_text('\n'.join(lines))
    _csv(output/'endpoints.csv',endpoints); _csv(output/'candidates.csv',candidates); _csv(output/'primary.csv',primary)
    c.seal(output/'costs.json',dict(historical_costs=provenance['historical_costs'],
        qualification=provenance['qualification'],qualification_baseline=provenance['qualification_baseline'],
        collection_paired_durations=provenance['collection_paired_durations'],
        model_validation_refits=selection_refits,
        campaign_pack_model_validation_refits=provenance['refits'],
        candidate_attempt_seconds=audited['candidate_wall_seconds'],candidate_observed_cli_seconds=outer,
        timer_scopes_overlap=True,actual_calendar_wall_seconds=None))
    summary = dict(candidates=len(candidates),endpoint_summaries=len(endpoints),policies=POLICIES,
        primary=primary,calibration_diagnostics=provenance['calibration_diagnostics'],
        model_validation_refits=selection_refits,new_model_fits=0,new_model_predictions=0,
        new_native_jobs=0,superiority_established=False)
    c.seal(output/'summary.json',summary); prior._seal_manifest(output)
    return summary


def export_corpus(campaign,output):
    campaign,prereg,cohort,provenance,audited,outer,public,context,_,selection_refits = _campaign_inputs(campaign)
    output = Path(output).resolve(); fresh(output,campaign,prereg)
    previous = history(HISTORY)
    c.require(provenance['historical_costs']['source_corpus_sha256'] == c.sha(HISTORY) and
        w.GROUP not in previous['independent_workload_groups'] and
        public[0]['benchmark'] not in previous['contexts'], 'Exact prior corpus and new target context required')
    previous_ids = {row['candidate_id'] for row in previous['rows']+previous['failed_attempts']}
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    c.require(not previous_ids.intersection(labels) and set(labels) == {row['candidate_id'] for row in public} == set(outer) and
        sum(row['measurement_seconds'] for row in labels.values()) == audited['candidate_wall_seconds'],
        'Distinct complete new paid labels and exact attempt-cost sum required')
    rows,failures = copy.deepcopy(previous['rows']),copy.deepcopy(previous['failed_attempts'])
    for feature in public:
        row = labels[feature['candidate_id']]
        enriched = dict(row,workload_group=w.GROUP,candidate_family=family(row['formula']),
            outer_operation_seconds=outer[row['candidate_id']],
            measurement_timer_scope='paired observed CLI monotonic duration; native attempt ledger is separately retained')
        if b.validate_outcome(row,feature):
            rows.append(enriched)
        else:
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class') and
                not {'area','device_fits','timing_feasible'} & set(row),
                'Classified failure without fabricated speedup/hardware labels required')
            enriched['correctness_verified'] = None if row['reference_censored'] else False
            failures.append(enriched)
    all_attempts = rows+failures
    c.require(len({row['candidate_id'] for row in all_attempts}) == len(all_attempts) ==
        previous['total_candidate_attempts']+len(public) and
        rows[:len(previous['rows'])] == previous['rows'] and
        failures[:len(previous['failed_attempts'])] == previous['failed_attempts'] and
        len(rows)-len(previous['rows']) == len(audited['successful']) and
        len(failures)-len(previous['failed_attempts']) == len(audited['failed_or_interrupted']),
        'Preserve prior labels exactly and append every candidate attempt once')
    contexts = copy.deepcopy(previous['contexts']); contexts[public[0]['benchmark']] = context
    groups = sorted({row['workload_group'] for row in all_attempts})
    c.require(len(groups) == len(previous['independent_workload_groups'])+1 and
        len(contexts) == len(previous['contexts'])+1, 'One additional source/context required')
    paired = provenance['collection_paired_durations']
    clock = dict(historical=previous['clock_accounting'],current_paired_collection=paired)
    value = dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Historical corpus plus all charged consumed Lift transfer attempts.',rows=rows,
        failed_attempts=failures,contexts=contexts,successful_labels=len(rows),independent_workload_groups=groups,
        historical_costs=provenance['historical_costs'],preserved_original_rows_digest=c.digest(previous['rows']),
        preserved_original_failed_attempts_digest=c.digest(previous['failed_attempts']),
        new_candidate_attempts=len(public),total_candidate_attempts=len(all_attempts),
        new_candidate_wall_seconds=audited['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=previous['total_candidate_attempt_wall_seconds']+audited['candidate_wall_seconds'],
        new_candidate_outer_operation_seconds=sum(outer.values()),qualification_costs=provenance['qualification'],
        new_qualification_baseline=provenance['qualification_baseline'],
        new_calibration_diagnostics=provenance['calibration_diagnostics'],
        new_collection_costs={key:audited.get(key) for key in
            ('native_command_count','native_command_seconds','baseline_wall_seconds','baseline_record_seconds')},
        historical_qualification_costs=previous.get('qualification_costs'),clock_accounting=clock,
        historical_clock_accounting=previous['clock_accounting'],current_paired_clock_accounting=paired,
        actual_calendar_wall_seconds=None,live_native_attempts=LIVE['budget'],
        oracle_reference_attempts=len(public)-LIVE['budget'],
        split_unit='Entire source workload and all its contexts, with related formula-family exclusions.',
        timer_note='Ledger, CLI, observer, synthesis and host model timers have distinct/overlapping scopes; no total-time saving claimed.',
        reference_censored_candidates=sorted(row['candidate_id'] for row in failures if row.get('reference_censored')),
        consumed_development_source=True,model_validation_refits=selection_refits,
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0)
    output.mkdir(parents=True)
    shutil.copyfile(HISTORY,output/'historical-corpus.json')
    c.require(c.sha(output/'historical-corpus.json') == c.sha(HISTORY), 'Bytewise historical corpus preservation required')
    c.seal(output/'corpus.json',value); c.seal(output/'clock-accounting.json',clock)
    _csv(output/'verified-labels.csv',rows); _csv(output/'failed-attempts.csv',failures)
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(ROOT/SOURCE),
        previous_manifest_sha256=c.sha(HISTORY.parent/'manifest.json'),previous_corpus_sha256=c.sha(HISTORY),
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        model_validation_refits=selection_refits,campaign_pack_model_validation_refits=provenance['refits'],
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0))
    (output/'README.md').write_text(f"# Consumed corpus including Lift\n\n{len(rows)} verified labels, {len(failures)} failures, "
        f"{len(all_attempts)} attempts and {len(groups)} source groups. The exact historical corpus, its original rows "
        "and failures are preserved. Lift is consumed engineering-transfer data, not an untouched confirmation set. "
        "Unknown outcomes retain their failure class without fabricated labels.\n")
    prior._seal_manifest(output)
    return value


def replay(campaign,output):
    campaign,output = Path(campaign).resolve(),Path(output).resolve()
    prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json'); prereg = prior._path(ROOT,provenance['preregistration'])
    cohort,_,target,_ = authenticate(prereg)
    fresh(output,campaign,prereg,target['original_root'],ROOT/cohort['qualification']['path'])
    c.require(provenance['schema'] == SCHEMA+'-campaign' and
        provenance['source_bindings'] == cohort['source_bindings'] and
        provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json'),
        'Exact campaign and source-bound preregistration required')
    prior._hashes(ROOT,cohort['source_bindings'])
    prior.check_git_checkpoint(prereg,provenance['prelabel_commit'])
    regenerated = restore_native_snapshot(campaign/'native',output/'native')
    check_baseline(prereg,output/'native')
    baseline = c.unseal(prereg/'targets'/w.GROUP/'baseline/measurements/baseline/measurement.json')
    checked,outer,trace,whole = check_collection(prereg,output/'native',
        campaign/'collection',campaign/'release.json')
    c.require(regenerated == checked == c.unseal(campaign/'audit.json') and
        outer == c.unseal(campaign/'outer-times.json') and
        baseline == c.unseal(campaign/'baseline.json'),
        'Raw attempt audit, command timers and qualification baseline replay differ')
    refits = verify_frozen_selection(prereg,campaign/'selection',reports_required=True)
    c.require(stable(provenance['refits']) == stable(refits),
        'Copied model refits differ from campaign provenance')
    result = evaluate(prereg,campaign/'selection',checked,outer,campaign/'report.json',verify=True)
    c.require(stable(result['endpoints']) == stable(c.unseal(campaign/'endpoints.json')) and
        result['trajectories'] == len(c.unseal(campaign/'report.json')['runs']) and
        stable(trace['search']['curve'][-1]) == stable(provenance['live_best']) and
        whole['durations'] == provenance['collection_paired_durations'],
        'Complete fixed-policy endpoints, live trace or collection clocks differ')
    receipt = dict(charged_candidate_attempts=checked['charged_candidate_attempts'],
        trajectories=result['trajectories'],endpoint_points=result['endpoint_points'],
        endpoint_summaries=result['endpoint_summaries'],new_native_jobs=0,
        live_trace_exact=True,scientific_and_paid_cost_fields_exact=True,
        excluded_host_timer_fields=sorted(HOST_TIMERS),refits=refits)
    c.seal(output/'reproduction.json',receipt); prior._seal_manifest(output)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','authenticate','release','measure','collect','pack','replay','report','export'))
    parser.add_argument('--native-root',type=Path)
    parser.add_argument('--root',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--preregistration',type=Path)
    parser.add_argument('--qualification',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--collection',type=Path)
    parser.add_argument('--release',type=Path)
    parser.add_argument('--campaign',type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--candidate')
    parser.add_argument('--acquisition-proof',type=Path)
    parser.add_argument('--mode',choices=('adaptive','oracle-reference'),default='adaptive')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        cohort = freeze(args.native_root,args.output,qualification_path=args.qualification)
        target = cohort['targets'][w.GROUP]
        result = dict(schema=cohort['schema'],scope=cohort['scope'],policies=len(cohort['policies']),
            pool_size=target['pool_size'],historical_fitting_rows=len(target['historical_training_ids']),
            historical_postfilter_groups=target['historical_postfilter_groups'],target_labels_read=0,new_native_jobs=0)
    elif args.command == 'authenticate':
        cohort,_,_,_ = authenticate(args.preregistration)
        result = dict(schema=cohort['schema'],target_labels_read=0,new_native_jobs=0)
    elif args.command == 'release':
        result = release(args.preregistration,args.native_root,args.commit,args.output)
    elif args.command == 'collect':
        result = collect(args.preregistration,args.native_root,args.release,args.output)
    elif args.command == 'pack':
        result = pack(args.preregistration,args.native_root,args.collection,args.release,args.output)
    elif args.command == 'replay':
        result = replay(args.campaign,args.output)
    elif args.command == 'report':
        result = report(args.campaign,args.output)
    elif args.command == 'export':
        corpus = export_corpus(args.campaign,args.output)
        result = {key:corpus[key] for key in ('successful_labels','total_candidate_attempts','independent_workload_groups')}
    else:
        root = args.root or args.native_root
        result = measure(root,args.candidate,mode=args.mode,acquisition_proof=args.acquisition_proof)
    print(json.dumps(result,indent=2))
    if args.command == 'measure' and result.get('status') == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
