"""A fresh source test of the fourteen fixed selectors, including live semantic GP.

Reuse the frozen twelve-policy experiment and guarded processor evaluator. The
two already-tested count policies add no tuning or model settings. Three live
queries precede the separate measured-pool reference; all outcomes stay hidden
until each policy's charged query. Replay launches no native tools.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
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
from isaforge import tacle_workload as w, guarded_evidence
from isaforge import factorized_selection_experiment as experiment
from isaforge.speedup_corpus import family
from scripts import blind_campaign as prior, live_gp_campaign as live_helpers
from scripts import report_tacle_selection as presenter

SOURCE = 'scripts/tacle_selection_campaign.py'
SCHEMA = w.SELECTION_SCHEMA
HISTORY = ROOT/'results/2026-10-22-eleven-source-corpus/corpus.json'
LIVE = dict(policy='hybrid_gp_adapt_count_semantic', seed=0, area_cap=64, clock_mhz=12., budget=3)
POLICIES = list(w.POLICIES)
HOST_TIMERS = {'inference_seconds','paid_update_host_seconds','cached_initial_inference_seconds',
    'replay_search_host_seconds','mean_inference_seconds'}
LIMITATIONS = [
    'One new source and five dependent seeds do not establish broad generalization, significance or field superiority.',
    'All fourteen existing models/policies/settings are fixed; no model/feature sweep or promotion.',
    'Only semantic count-GP seed0/+64/three queries dispatches live native evaluations; other policies use charged cooperative replay.',
    'A cooperative local callback is not an OS sandbox. Oracle outcomes are withheld until each policy asks for a paid measurement.',
    'GP probabilities/disagreement remain uncalibrated. Actual whole-program cycles remain distinct from analytic predictions.',
    'Full original TACLeBench input and aggregate1095 verifier are retained; declared ILP32 amalgamation differs from the upstream separate-object build.',
    'The benchmark verifier and sampled instruction/lowering checks are fixed-input evidence, not universal correctness proofs.',
    'All historical90 attempts, new failed attempts, baseline/setup, model fitting and qualification costs remain charged with distinct timer scopes.',
    'The initial semantic-fit receipt counts only that fit. Repeated authentication refits are validation work inside CLI/outer scopes, not additional initial fits or free total-model work.',
    'UTC and monotonic endpoints are retained separately; overlapping scopes cannot establish uninterrupted calendar-wall-time savings.',
    'The baseline is always available; a pool reference is complete only if no candidate remains infrastructure-censored.',
    'Combined-report diagnostics classify known invalid failures as infeasible and only infrastructure-censored outcomes as unknown; legacy reports retain their original diagnostic fields.',
    'Single instructions only; one-to-three-instruction sets still require joint execution/synthesis.']


def stable(value):
    if isinstance(value,(list,tuple)):
        return [stable(item) for item in value]
    if isinstance(value,dict):
        return {key:stable(item) for key,item in value.items() if key not in HOST_TIMERS}
    return value


def sources(plan):
    names = (SOURCE, 'scripts/report_tacle_selection.py', 'scripts/qualify_tacle_bitcount.py',
        'scripts/live_gp_campaign.py', 'isaforge/observed_command.py',
        'scripts/report_guarded_selection.py', 'scripts/export_guarded_corpus.py', 'scripts/report_budget_campaign.py',
        *prior.SOURCES, *count.SOURCES, *semantic.SOURCES, *plan['source_bindings'])
    return {name:c.sha(ROOT/name) for name in dict.fromkeys(names)}


def history(path):
    path = Path(path).resolve()
    c.require(path == HISTORY.resolve(), 'Exact complete87-label historical corpus required')
    prior._manifest(path.parent)
    corpus = c.unseal(path)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 87 and
        len(corpus['failed_attempts']) == 3 and corpus['total_candidate_attempts'] == 90 and
        len(corpus['independent_workload_groups']) == 11 and len(corpus['contexts']) == 12,
        'Complete87-success/3-failure/90-attempt historical corpus required')
    attempts = corpus['rows']+corpus['failed_attempts']
    c.require(len({row['candidate_id'] for row in attempts}) == 90 and
        sum(row['measurement_seconds'] for row in attempts) == corpus['total_candidate_attempt_wall_seconds'],
        'Unique fully charged historical attempts required')
    c.require(all(b.validate_outcome(row) for row in corpus['rows']), 'Only verified history may fit models')
    c.require(w.GROUP not in {row['workload_group'] for row in attempts}, 'Entire fresh target source must be absent')
    return corpus


def qualification(path, native):
    path = Path(path).resolve()
    c.require(path.is_relative_to(ROOT), 'Repository-local qualification required')
    prior._manifest(path)
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
        setup_subprocess_seconds=seconds)


def fresh(output, *inputs):
    return live_helpers.fresh_output(output,extra=(*inputs,HISTORY.parent))


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
    shared = dict(successful_labels=87,failed_attempts=3,total_candidate_attempts=90,
        total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(HISTORY),actual_calendar_wall_seconds=None,clock_accounting=corpus['clock_accounting'])
    costs = dict(historical_training_available=shared,target_baseline=context['baseline_provenance'],qualification=qualified,
        note='All90 historical attempts charged once; ledger, native, CLI, paired-observer and model scopes remain separate.')
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
    prior._zero(native)
    c.require(w.baseline_public(native) == (public,context,before), 'Baseline changed during complete model freeze')
    cohort = dict(schema=SCHEMA,target_labels_observed=0,target_labels_read=0,
        source_history=HISTORY.relative_to(ROOT).as_posix(),historical_costs=shared,qualification=qualified,
        source_bindings=sources(plan),python_executable=sys.executable,live=LIVE,
        policies=POLICIES,seeds=[0,1,2,3,4],area_caps=[32,64,128],budgets=[1,2,3],clock_mhz=12.,
        gp_settings=copy.deepcopy(b.GP_SETTINGS),semantic_columns=list(semantic.COLUMNS),
        native_collection_rule='Seal three live semantic-count-GP decisions/outcomes before any remaining oracle-reference outcome exists; then collect remainder in frozen public order, one attempt each.',
        targets={w.GROUP:dict(context_id=context['context_id'],native_order=before['pool_names'],pool_size=len(public),
            original_root=str(native),baseline_files=list(prior.BASELINES),baseline_outer_files=timers,
            selection_protocol_sha256=c.sha(folder/'selection/protocol.json'),
            historical_training_ids=protocol['historical_training_ids'],historical_postfilter_groups=protocol['historical_postfilter_groups'],
            semantic_predictions_sha256=c.sha(folder/'semantic/predictions.json'),semantic_snapshot_sha256=c.sha(folder/'semantic/snapshot.json'))},
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
        cohort['gp_settings'] == b.GP_SETTINGS and cohort['semantic_columns'] == list(semantic.COLUMNS),
        'Complete fixed fourteen-policy zero-label source-holdout protocol required')
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
        c.unseal(prereg/'inputs/contexts.json') == contexts and c.digest(contexts) == protocol['contexts_digest'] and
        c.digest(corpus['rows']) == protocol['source_history_digest'] and
        target['context_id'] == context['context_id'] == plan['context_id'] and target['pool_size'] == len(public) == 12 and
        target['native_order'] == c.unseal(folder/'baseline/evaluation-protocol.json')['pool_names'] and
        c.sha(folder/'selection/protocol.json') == target['selection_protocol_sha256'] and
        w.opportunity_gate(public) == c.unseal(folder/'baseline/opportunity.json'), 'Source/family exclusions or baseline/pool changed')
    prior._hashes(ROOT,protocol['input_bindings'])
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
    case.update(selection_root=folder/'selection',semantic_predictions=initial,semantic_snapshot=snapshot,
        semantic_cost=cost,cohort=cohort)
    return cohort,w.GROUP,target,case


def check_baseline(prereg, native):
    prereg,native = Path(prereg),Path(native)
    plan = w.validate_inputs(native)
    target = c.unseal(prereg/'cohort.json')['targets'][w.GROUP]
    baseline = prereg/'targets'/w.GROUP/'baseline'
    c.require(plan['context_id'] == target['context_id'], 'Native/preregistered context differs')
    for name in (*prior.BASELINES,'opportunity.json'):
        if name != 'commands.json':
            c.require(c.sha(native/name) == c.sha(baseline/name), 'Exact preregistered baseline required: '+name)
    prefix = c.unseal(baseline/'commands.json')
    protocol,commands = c.unseal(native/'evaluation-protocol.json'),c.unseal(native/'commands.json')
    c.require(protocol['baseline_receipts'] == prefix == commands[:len(prefix)] and
        protocol['pool_names'] == target['native_order'] and protocol['maximum_candidate_attempts'] == target['pool_size'],
        'Exact baseline receipt prefix and declared candidate pool required')
    prior._hashes(native/'outer-timing',target['baseline_outer_files'])


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
    w.check_release(native)
    return record


def count_search(case,provider,*,policy,seed,area_cap,on_acquire=None):
    c.require(policy in (count.POLICY,LIVE['policy']), 'Fixed count-acquisition policy required')
    semantic_policy = policy == LIVE['policy']
    predictions = c.unseal(case['selection_root']/'controls11/model/predictions.json')
    prediction = next(row for row in predictions if row['seed'] == seed)
    state = copy.deepcopy(case['semantic_snapshot']) if semantic_policy else None
    if semantic_policy:
        prediction = dict(hardware=case['semantic_predictions'],inference_seconds={
            'hybrid_gp_adapt':case['semantic_cost']['host_monotonic_seconds']})
    proofs = []
    class Tracked(semantic.SemanticHardwareSurrogate):
        def fit(self,rows):
            nonlocal state
            result = super().fit(rows)
            state = result.snapshot()
            return result
    def acquire(event):
        expected_ids = [row['candidate_id'] for row in case['history']]+event['paid_target_ids_before_query']
        proof = dict(event=copy.deepcopy(event),policy=policy,training_ids=expected_ids)
        if semantic_policy:
            c.require(state['training_ids'] == expected_ids, 'Only historical rows plus successful paid prefix may fit')
            proof.update(model_state_sha256=state['model_state_sha256'],snapshot_sha256=c.digest(state))
        proofs.append(proof)
        if on_acquire is not None:
            on_acquire(copy.deepcopy(proof))
    searched = count.search(case['public'],case['history'],provider,area_cap=area_cap,clock_mhz=12.,seed=seed,
        budget=3,predictions=prediction,surrogate_factory=Tracked if semantic_policy else b.HardwareSurrogate,
        on_acquire=acquire)
    searched.update(policy=policy,acquisition_policy=count.POLICY,acquisition_proofs=proofs)
    return searched


def run_search(case,provider,*,on_acquire=None):
    return count_search(case,provider,policy=LIVE['policy'],seed=LIVE['seed'],area_cap=LIVE['area_cap'],on_acquire=on_acquire)


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


def collect(prereg,native,release_path,output):
    prereg,native,output = (Path(p).resolve() for p in (prereg,native,output))
    cohort,_,target,case = authenticate(prereg)
    live_helpers.original_native(native,target)
    fresh(output,prereg,native,release_path,ROOT/cohort['qualification']['path'])
    prior._zero(native); check_baseline(prereg,native)
    checked_release(release_path,prereg,native=native)
    w.check_release(native)
    output.mkdir(parents=True)
    paid,trace_hash = [],None
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole = dict(schema=SCHEMA+'-collection',status='started',start=observed._endpoint(),observer_pid=os.getpid(),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),live=LIVE)
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
            c.require(proof['event']['candidate_id'] == identity and proof['policy'] == LIVE['policy'],
                'Seal model-state/acquisition proof before native dispatch')
            acquisition = c.sha(proof_path)
        folder = output/'queries'/f'{index:02d}'
        folder.mkdir(parents=True)
        decision = dict(index=index,mode=mode,candidate_id=identity,native_name=names[identity],paid_ids_before=list(paid),
            prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
            completed_live_trace_sha256=trace_hash,acquisition_sha256=acquisition,chosen_before_dispatch=True)
        c.seal(folder/'decision.json',decision)
        before = set((native/'outer-timing').glob('*.json'))
        argv = [cohort['python_executable'],'-m','isaforge.tacle_workload','measure','--root',str(native),'--candidate',names[identity]]
        record = observed.run(argv,folder/'command',cwd=ROOT,metadata=decision,timeout_seconds=3600)
        c.require(record['status'] in ('success','nonzero_exit'), 'Interruption stops collection; never retry')
        audited = w.audit(native)
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
    audited = w.audit(native)
    experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole,trace = c.unseal(collection/'collection.json'),c.unseal(collection/'live.json')
    c.require(whole['status'] == 'complete' and whole['live'] == trace['live'] == LIVE and
        whole['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and whole['release_sha256'] == c.sha(release_path) and
        whole['live_trace_sha256'] == c.sha(collection/'live.json') and trace['remaining_outcomes_exist'] is False and
        whole['durations'] == observed._durations(whole['start'],whole['end']), 'Complete paired live collection required')
    paid,first = whole['paid_ids'],trace['attempted_ids']
    c.require(len(first) == LIVE['budget'] and paid[:len(first)] == first and len(paid) == len(set(paid)) == len(names) and
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
        argv = [cohort['python_executable'],'-m','isaforge.tacle_workload','measure','--root',target['original_root'],'--candidate',names[identity]]
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


def annotate(run,labels,outer,cap):
    """Diagnostics only: never alter a prediction, acquisition or chosen prefix."""
    for point in run['curve']:
        attempted = [labels[identity] for identity in point['attempted_ids']]
        unknown = [row for row in attempted if row.get('status','success') != 'success' and row.get('reference_censored') is True]
        invalid = [row for row in attempted if row.get('status','success') != 'success' and row.get('reference_censored') is False]
        point['known_infeasible_attempts'] = len(invalid)+sum(row.get('status','success') == 'success' and
            not b._feasible(row,cap,12.) for row in attempted)
        point['unknown_attempts'] = len(unknown)
        point['target_outer_operation_seconds'] = sum(outer[identity] for identity in point['attempted_ids'])
    run['candidate_outer_operation_seconds'] = dict(outer)


def evaluate(prereg,selection,audited,outer,output,*,verify=False):
    """Same budgets/data for all14 policies; outcomes stay in the paid provider."""
    prereg,selection,output = map(Path,(prereg,selection,output))
    cohort,_,_,case = authenticate(prereg)
    censored = experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    c.require(set(outer) == {row['candidate_id'] for row in case['public']} and
        all(outer[row['candidate_id']] >= row['measurement_seconds'] for row in audited['outcomes']),
        'Complete charged native/outer durations required')
    c.require(verify or not output.exists(), 'Preserve existing complete selection report')
    old = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=outer,verify=verify)
    runs = copy.deepcopy(old['runs'])
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    for policy in (count.POLICY,LIVE['policy']):
        for seed in cohort['seeds']:
            for cap in cohort['area_caps']:
                released = []
                trajectory = output.parent/'replay-acquisitions'/policy/f'cap{cap}-seed{seed}'
                def acquire(proof):
                    c.require(proof['event']['charged_before_query'] == len(released) and
                        proof['event']['attempted_ids_before_query'] == released, 'Only paid replay prefix may reach acquisition')
                    path = trajectory/f'{len(released):02d}.json'
                    if verify:
                        c.require(c.unseal(path) == proof, 'Exact replay acquisition/model-state seal differs')
                    else:
                        c.seal(path,proof)
                def provider(row):
                    proof = c.unseal(trajectory/f'{len(released):02d}.json')
                    c.require(proof['event']['candidate_id'] == row['candidate_id'] and row['candidate_id'] not in released,
                        'Seal choice before one charged replay outcome release')
                    released.append(row['candidate_id'])
                    return copy.deepcopy(labels[row['candidate_id']])
                searched = count_search(case,provider,policy=policy,seed=seed,area_cap=cap,on_acquire=acquire)
                c.require(len(released) == len(set(released)) == 3, 'Every fixed-budget trajectory spends exactly three attempts')
                runs.append(dict(target=w.GROUP,cap=cap,seed=seed,**searched))
    for run in runs:
        annotate(run,labels,outer,run['cap'])
    endpoints = presenter.endpoints(case['public'],audited['outcomes'],runs,policies=POLICIES,reference_censored=censored)
    result = dict(schema=SCHEMA+'-report',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        outcomes_sha256=c.digest(audited['outcomes']),native_audit_digest=c.digest(audited),
        policies=POLICIES,runs=runs,endpoints=endpoints,reference_censored=censored,
        trajectories=len(runs),endpoint_points=sum(len(run['curve']) for run in runs),endpoint_summaries=len(endpoints),
        new_native_jobs=0,superiority_established=False,limitations=LIMITATIONS)
    if verify:
        archived = c.unseal(output)
        c.require(stable(result) == stable(archived), 'Scientific predictions, paid selections or costs differ on replay')
    else:
        c.seal(output,result)
    return result


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
        collection_paired_durations=whole['durations'],refits=refits,trajectories=report['trajectories'],endpoints=report['endpoint_points'],
        endpoint_summaries=report['endpoint_summaries'],live_native_dispatch=True,other_policies_native_remeasured=False,
        actual_calendar_wall_seconds=None,new_native_jobs=0,limitations=LIMITATIONS)
    c.seal(output/'provenance.json',result); prior._seal_manifest(output)
    return result


def report(campaign,output):
    campaign,output = Path(campaign).resolve(),Path(output).resolve()
    prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json')
    audited = c.unseal(campaign/'audit.json')
    audited['native_measurements'] = c.unseal(campaign/'native-measurements.json')
    return presenter.write_report(output,audit=audited,baseline=c.unseal(campaign/'baseline.json'),
        endpoints=c.unseal(campaign/'endpoints.json'),live=c.unseal(campaign/'collection/live.json'),
        historical_costs=provenance['historical_costs'],qualification=provenance['qualification'])


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
        result['trajectories'] == 210 and result['endpoint_points'] == 630 and result['endpoint_summaries'] == 126,
        'Complete fixed-policy endpoints/live trace/native cost replay required')
    # Nondeterministic host timers are explicitly excluded from exact scientific
    # equality; preserve their old and fresh values without rewriting either.
    c.seal(output/'archived-endpoints.json',c.unseal(campaign/'endpoints.json'))
    c.seal(output/'replayed-endpoints.json',result['endpoints'])
    receipt = dict(charged_candidate_attempts=audited['charged_candidate_attempts'],
        trajectories=210,endpoints=630,endpoint_summaries=126,**refits,new_native_jobs=0,live_trace_exact=True,
        scientific_and_paid_cost_fields_exact=True,excluded_host_timer_fields=sorted(HOST_TIMERS),
        initial_semantic_model_refit_exact=True,paired_collection_clocks_exact=True)
    c.seal(output/'reproduction.json',receipt); prior._seal_manifest(output)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','release','collect','pack','replay','report','export'))
    for name in ('preregistration','native-root','qualification','output','release','collection','campaign'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--commit')
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        result = freeze(args.native_root,args.output,qualification_path=args.qualification)
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
    else:
        corpus = presenter.export_corpus(HISTORY.parent.resolve(),args.campaign.resolve(),args.output.resolve())
        result = {key:corpus[key] for key in ('successful_labels','total_candidate_attempts','independent_workload_groups')}
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
