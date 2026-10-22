"""Connect the preserved paid-adaptive GP to bounded native measurements.

The first three queries are chosen online, before any remaining pool outcomes
exist. Only then is the rest collected for a separate measured-pool reference.
Every model, pool, runtime and decision rule is frozen before candidate work.
This changes dispatch, not the existing models or acquisition function.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c, observed_command as observed
from isaforge import factorized_selection_experiment as experiment
from isaforge.speedup_corpus import family
from scripts import blind_campaign as prior
from scripts.report_blind_campaign import endpoints_for_source, POLICY_LABELS

SOURCE = 'scripts/live_gp_campaign.py'
HISTORY = ROOT/'results/2026-10-21-ten-source-corpus/corpus.json'
SCHEMA = 'isaforge-live-gp-v1'
LIVE = dict(policy='hybrid_gp_adapt', seed=0, area_cap=64, clock_mhz=12, budget=3)
LIMITATIONS = [
    'One fresh source and one live seed do not establish broad generalization or field superiority.',
    'All twelve policies retain their fixed settings; only the declared GP trajectory dispatches live hardware.',
    'Other policies use charged cooperative replay of the same pool, not newly measured live runtimes.',
    'Only successful paid target observations update the GP; failed attempts remain charged.',
    'GP probabilities and bootstrap disagreement are not calibrated confidence.',
    'Historical data and qualification costs are not free; all timer scopes remain distinct and overlapping.',
    'Paired UTC and monotonic observations are retained separately; uninterrupted calendar wall time is not established.',
    'The callback boundary is local cooperative isolation, not an operating-system sandbox.',
    'Single instructions only; selected combinations require joint execution and hardware measurement.']


def workload():
    from isaforge import integer_workload
    return integer_workload


def fresh_output(output, *, prereg=None, native=None, cohort=None, extra=()):
    output = Path(output).resolve()
    protected = [Path(path).resolve() for path in extra]
    if prereg is not None: protected.append(Path(prereg).resolve())
    if native is not None: protected.append(Path(native).resolve())
    if cohort is not None:
        protected += [(ROOT/cohort['source_history']).resolve().parent,
                      (ROOT/cohort['qualification']['path']).resolve()]
    c.require(not output.exists() and all(not output.is_relative_to(path) and
              not path.is_relative_to(output) for path in protected),
              'Fresh output must be separate from preregistration, native state and frozen inputs')
    return output


def original_native(native, target):
    c.require(Path(native).resolve() == Path(target['original_root']).resolve(),
              'Original frozen native root required for active collection')


def observed_pair(record, started):
    immutable = ('schema','argv_sha256','argv_count','cwd','metadata','metadata_sha256','observer_pid',
        'observer_session_id','observer_os_session_id','clock_info','timeout_seconds','stdout_file',
        'stderr_file','start','scope','cross_process_monotonic_origin_verified')
    c.require(record.get('schema') == observed.SCHEMA and started.get('status') == 'started' and
              started.get('end') is None and started.get('returncode') is None and started.get('child_pid') is None and
              all(record.get(key) == started.get(key) for key in immutable) and
              record.get('metadata_sha256') == hashlib.sha256(observed._json(record['metadata'])).hexdigest() and
              record.get('stdout_file') == 'stdout.txt' and record.get('stderr_file') == 'stderr.txt',
              'Immutable paired observer receipt fields differ')
    c.require(type(record.get('returncode')) is int and record.get('status') ==
              ('success' if record['returncode'] == 0 else 'nonzero_exit'),
              'Observer exit status and return code differ')


def history(path):
    path = Path(path).resolve(); prior._manifest(path.parent)
    corpus = c.unseal(path)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 81 and
              len(corpus['failed_attempts']) == 3 and corpus['total_candidate_attempts'] == 84 and
              len(corpus['independent_workload_groups']) == 10 and len(corpus['contexts']) == 11,
              'Complete consumed81-label/84-attempt history required')
    rows = corpus['rows']+corpus['failed_attempts']
    c.require(len({row['candidate_id'] for row in rows}) == 84 and
              sum(row['measurement_seconds'] for row in rows) == corpus['total_candidate_attempt_wall_seconds'],
              'Unique recorded historical charges required')
    for row in corpus['rows']:
        c.require(b.validate_outcome(row), 'Verified historical labels required')
    return corpus


def sources(plan):
    names = (SOURCE, 'isaforge/observed_command.py', 'scripts/qualify_integer_workload.py',
             'scripts/report_blind_campaign.py', *prior.SOURCES, *plan['source_bindings'])
    return {name:c.sha(ROOT/name) for name in dict.fromkeys(names)}


def qualification(path, group, native):
    path = Path(path).resolve(); prior._manifest(path)
    protocol, result = c.unseal(path/'protocol.json'), c.unseal(path/'qualification.json')
    prior._hashes(ROOT, protocol['source_bindings'])
    name = group.removeprefix('beebs-')
    c.require(path.is_relative_to(ROOT) and result['protocol_sha256'] == c.sha(path/'protocol.json') and
              result['target_candidate_attempts'] == 0 and result['accepted'] == {name:str(Path(native).resolve().relative_to(ROOT))},
              'Exactly one accepted zero-candidate qualification required')
    records = result['records']
    c.require([row['workload'] for row in records] == protocol['order'][:len(records)] and
              records[-1]['status'] == 'accepted' and records[-1]['context_id'] == c.unseal(Path(native)/'plan.json')['context_id'],
              'Declared qualification prefix/context differs')
    return dict(path=path.relative_to(ROOT).as_posix(), manifest_sha256=c.sha(path/'manifest.json'),
        protocol_sha256=c.sha(path/'protocol.json'), qualification_sha256=c.sha(path/'qualification.json'),
        setup_subprocess_seconds=result['recorded_subprocess_monotonic_seconds'])


def freeze(native, output, *, qualification_path, history_path=HISTORY):
    native, output, history_path = map(lambda p:Path(p).resolve(), (native, output, history_path))
    c.require(output.is_relative_to(ROOT), 'In-repository preregistration required')
    fresh_output(output,native=native,extra=(history_path.parent,qualification_path))
    prior._zero(native)
    public, context, before = workload().baseline_public(native)
    group = context['workload_group']; plan = c.unseal(native/'plan.json')
    c.require(len(public) == plan['pool_size'] == 6 and before['workload'] == group and
              c.unseal(native/'public.json') == public and c.unseal(native/'context.json') == context and
              c.unseal(native/'before.json') == before, 'Exact declared six-candidate baseline required')
    qualified = qualification(qualification_path, group, native)
    corpus = history(history_path)
    c.require(group not in {row['workload_group'] for row in corpus['rows']+corpus['failed_attempts']},
              'Entire fresh target source must be absent from history')
    contexts = dict(corpus['contexts']); contexts[public[0]['benchmark']] = context
    for name, value in (('history',corpus['rows']), ('historical-failures',corpus['failed_attempts']), ('contexts',contexts)):
        c.seal(output/'inputs'/(name+'.json'), value)
    folder = output/'targets'/group
    for name in prior.BASELINES:
        for suffix in ('','.sha256'):
            destination = folder/'baseline'/(name+suffix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(native/(name+suffix), destination)
    shutil.copytree(native/'outer-timing', folder/'baseline/outer-timing')
    timers = {name:c.sha(folder/'baseline/outer-timing'/name) for name in prior._inventory(folder/'baseline/outer-timing')}
    shared = dict(successful_labels=81, failed_attempts=3, total_candidate_attempts=84,
        total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(history_path), actual_calendar_wall_seconds=None,
        clock_accounting=corpus['clock_accounting'])
    costs = dict(historical_training_available=shared, target_baseline=context['baseline_provenance'],
                 qualification=qualified, note='Historical84 attempts charged once; native, CLI, observer, qualification and model durations overlap.')
    c.seal(folder/'public.json', public); c.seal(folder/'cost-provenance.json', costs)
    bindings = {path.relative_to(ROOT).as_posix():c.sha(path) for path in sorted(output.rglob('*')) if path.is_file()}
    bindings[history_path.relative_to(ROOT).as_posix()] = c.sha(history_path)
    protocol = experiment.freeze(corpus['rows'], public, contexts, folder/'selection',
        target_workload=group, target_labels_observed=0,
        calibration_cost_seconds=prior.evidence._calibration(native)['native_command_seconds'],
        cost_provenance=costs, input_bindings=bindings, scope='prospective source holdout')
    prior._zero(native)
    c.require(workload().baseline_public(native) == (public,context,before), 'Baseline changed during fitting')
    cohort = dict(schema=SCHEMA, target_labels_observed=0, target_labels_read=0,
        source_history=history_path.relative_to(ROOT).as_posix(), historical_costs=shared,
        qualification=qualified, source_bindings=sources(plan), python_executable=sys.executable,
        live=LIVE, policies=list(POLICY_LABELS), seeds=list(experiment.SEEDS), area_caps=[32,64,128], budgets=[1,2,3],
        native_collection_rule='Three live adaptive queries; seal their completed trace before collecting the remaining pool in declared membership order. No retries.',
        targets={group:dict(context_id=context['context_id'], native_order=before['pool_names'], pool_size=len(public),
            original_root=str(native), baseline_files=list(prior.BASELINES), baseline_outer_files=timers,
            selection_protocol_sha256=c.sha(folder/'selection/protocol.json'),
            historical_training_ids=protocol['historical_training_ids'],
            historical_postfilter_groups=protocol['historical_postfilter_groups'])}, limitations=LIMITATIONS)
    c.seal(output/'cohort.json', cohort); prior._seal_manifest(output)
    authenticate(output)
    return cohort


def authenticate(prereg):
    prereg = Path(prereg).resolve(); entries = prior._manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(cohort['schema'] == SCHEMA and cohort['live'] == LIVE and cohort['target_labels_observed'] == 0 and
              cohort['target_labels_read'] == 0 and len(cohort['targets']) == 1 and
              cohort['policies'] == list(POLICY_LABELS) and cohort['seeds'] == list(experiment.SEEDS) and
              cohort['area_caps'] == [32,64,128] and cohort['budgets'] == [1,2,3], 'Fixed fresh-source live protocol required')
    group, target = next(iter(cohort['targets'].items())); folder = prereg/'targets'/group
    plan = c.unseal(folder/'baseline/plan.json'); workload().check_plan(plan)
    c.require(cohort['source_bindings'] == sources(plan), 'Frozen live runtime changed')
    corpus = history(ROOT/cohort['source_history'])
    c.require(cohort['historical_costs']['source_corpus_sha256'] == c.sha(ROOT/cohort['source_history']) and
              c.unseal(prereg/'inputs/history.json') == corpus['rows'] and
              c.unseal(prereg/'inputs/historical-failures.json') == corpus['failed_attempts'], 'Complete historical data binding differs')
    c.require(group not in {row['workload_group'] for row in corpus['rows']+corpus['failed_attempts']}, 'Target source in history')
    qualified = ROOT/cohort['qualification']['path']; prior._manifest(qualified)
    c.require(c.sha(qualified/'manifest.json') == cohort['qualification']['manifest_sha256'], 'Qualification evidence changed')
    frozen, protocol = prior.required_selection(folder/'selection')
    prefix = 'targets/'+group+'/selection/'
    c.require({name for name in entries if name.startswith(prefix)} == {prefix+name for name in frozen},
              'Complete frozen model inventory required')
    case = experiment.authenticate(folder/'selection')
    public, context = c.unseal(folder/'baseline/public.json'), c.unseal(folder/'baseline/context.json')
    contexts = dict(corpus['contexts']); contexts[public[0]['benchmark']] = context
    families = {family(row['formula']) for row in public}
    fitting = [row for row in corpus['rows'] if family(row['formula']) not in families]
    c.require(case['public'] == public == c.unseal(folder/'public.json') and case['history'] == fitting and
              protocol['historical_training_ids'] == target['historical_training_ids'] and
              c.unseal(prereg/'inputs/contexts.json') == contexts and c.digest(contexts) == protocol['contexts_digest'] and
              c.digest(corpus['rows']) == protocol['source_history_digest'] and
              target['context_id'] == context['context_id'] == plan['context_id'] and
              target['pool_size'] == len(public) == 6 and
              target['native_order'] == c.unseal(folder/'baseline/evaluation-protocol.json')['pool_names'] and
              c.sha(folder/'selection/protocol.json') == target['selection_protocol_sha256'],
              'Frozen baseline, cohort or model inputs differ')
    prior._hashes(ROOT, protocol['input_bindings'])
    return cohort, group, target, case


def check_baseline(prereg, group, native):
    workload().validate_inputs(native)
    with workload().registration():
        prior.check_baseline(prereg, group, native)


def release(prereg, native, commit, output):
    prereg, native, output = map(lambda p:Path(p).resolve(), (prereg,native,output))
    cohort, group, target, _ = authenticate(prereg)
    original_native(native,target)
    fresh_output(output,prereg=prereg,native=native,cohort=cohort)
    c.require(not (native/'release.json').exists(), 'Fresh native release required')
    prior.check_git_checkpoint(prereg, commit)
    remote = subprocess.run(['git','ls-remote','origin','refs/heads/ai-guided-ml'], cwd=ROOT, capture_output=True, text=True, check=True)
    c.require(remote.stdout.strip().split() == [commit,'refs/heads/ai-guided-ml'], 'Push exact prelabel commit before release')
    prior._zero(native); check_baseline(prereg,group,native)
    record = dict(schema=prior.SCHEMA+'-release', prelabel_commit=commit, remote_commit=commit,
        pushed_branch='ai-guided-ml',remote='origin',prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        zero_candidate_attempts=True,target_labels_observed=0,targets={group:dict(context_id=target['context_id'],
            native_order=target['native_order'],evaluation_protocol_sha256=c.sha(native/'evaluation-protocol.json'))},
        released_at_utc=datetime.now(timezone.utc).isoformat())
    c.seal(output,record)
    for suffix in ('','.sha256'): shutil.copyfile(str(output)+suffix,str(native/'release.json')+suffix)
    return record


def run_search(case, provider):
    predictions = c.unseal(case['selection_root']/'controls11/model/predictions.json')
    prediction = next(row for row in predictions if row['seed'] == LIVE['seed'])
    return b.search(case['public'],case['history'],provider,predictions=prediction,**LIVE)


def collect(prereg, native, release_path, output):
    prereg, native, output = map(lambda p:Path(p).resolve(), (prereg,native,output))
    cohort, group, target, case = authenticate(prereg)
    original_native(native,target)
    fresh_output(output,prereg=prereg,native=native,cohort=cohort,extra=(release_path,))
    prior._zero(native); check_baseline(prereg,group,native)
    released = c.unseal(release_path)
    prior.check_git_checkpoint(prereg,released['prelabel_commit'])
    prior.check_release(release_path,prereg,released['prelabel_commit'],raws={group:native})
    c.require(not output.exists() and str(native) == target['original_root'], 'Fresh live collection on original frozen root required')
    output.mkdir(parents=True); paid = []; trace_hash = None
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    case['selection_root'] = prereg/'targets'/group/'selection'
    overall = dict(schema=SCHEMA+'-collection',status='started',start=observed._endpoint(),observer_pid=os.getpid(),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),live=LIVE)
    c.seal(output/'collection.json',overall)
    def provider(row):
        nonlocal trace_hash
        identity = row['candidate_id']; index = len(paid)
        c.require(identity in names and identity not in paid and index < len(names), 'Unique declared paid query required')
        mode = 'adaptive' if index < LIVE['budget'] else 'oracle-reference'
        c.require((mode == 'adaptive') == (trace_hash is None), 'Seal completed adaptive trace before oracle collection')
        folder = output/'queries'/f'{index:02d}'; folder.mkdir(parents=True)
        decision = dict(index=index,mode=mode,candidate_id=identity,native_name=names[identity],paid_ids_before=list(paid),
            prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
            completed_live_trace_sha256=trace_hash,chosen_before_dispatch=True)
        c.seal(folder/'decision.json',decision)
        before = set((native/'outer-timing').glob('*.json'))
        argv = [cohort['python_executable'],'-m','isaforge.integer_workload','measure','--root',str(native),'--candidate',names[identity]]
        record = observed.run(argv,folder/'command',cwd=ROOT,metadata=decision,timeout_seconds=3600)
        c.require(record['status'] in ('success','nonzero_exit'), 'Interrupted/failed dispatch stops collection without retry')
        audited = workload().audit(native)
        expected = set(paid+[identity]); labels = {value['candidate_id']:value for value in audited['outcomes']}
        c.require(audited['charged_candidate_attempts'] == index+1 and set(labels) == expected and
                  audited['candidate_wall_seconds_complete'], 'Only paid terminal outcomes may reach the learner')
        value = labels[identity]; b.validate_outcome(value,row)
        added = set((native/'outer-timing').glob('*.json'))-before
        c.require(len(added) == 1, 'One complete CLI receipt per native query required')
        cli = next(iter(added)); ledger = native/'attempt-ledger'/(names[identity]+'.json')
        c.require((record['returncode'] == 0) == (c.unseal(ledger)['status'] == 'success'), 'CLI/ledger terminal status differs')
        c.seal(folder/'outcome.json',value)
        c.seal(folder/'partial-audit.json',audited)
        c.seal(folder/'completed.json',dict(candidate_id=identity,audited_paid_ids=sorted(expected),
            ledger_sha256=c.sha(ledger),cli_timer=cli.relative_to(native).as_posix(),cli_timer_sha256=c.sha(cli),
            outcome_sha256=c.sha(folder/'outcome.json'),partial_audit_digest=c.digest(audited)))
        paid.append(identity)
        print(json.dumps(dict(query=len(paid),mode=mode,name=names[identity],speedup=value.get('speedup'),
                              area_delta_lut4=value.get('area_delta_lut4'),status=value.get('status','success'))),flush=True)
        return value
    try:
        search = run_search(case,provider)
        live = dict(schema=SCHEMA+'-live-trace',search=search,attempted_ids=list(paid),
                    finish=observed._endpoint(),remaining_outcomes_exist=False,live=LIVE)
        c.seal(output/'live.json',live); trace_hash = c.sha(output/'live.json')
        for row in case['public']:
            if row['candidate_id'] not in paid: provider(row)
        overall.update(status='complete',paid_ids=paid,live_trace_sha256=trace_hash)
    except BaseException as error:
        overall.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
                       error_type=type(error).__name__,paid_ids=paid)
        raise
    finally:
        overall['end'] = observed._endpoint(); overall['durations'] = observed._durations(overall['start'],overall['end'])
        c.seal(output/'collection.json',overall); prior._seal_manifest(output)
    return overall


def check_collection(prereg, native, collection, release_path):
    prereg, native, collection = map(Path,(prereg,native,collection))
    prior._manifest(collection)
    cohort, group, target, case = authenticate(prereg)
    audited = workload().audit(native); experiment.checked_outcomes(case['public'],audited['outcomes'],audited)
    labels = {row['candidate_id']:row for row in audited['outcomes']}
    names = dict(zip((row['candidate_id'] for row in case['public']),target['native_order']))
    whole, live = c.unseal(collection/'collection.json'), c.unseal(collection/'live.json')
    c.require(whole['status'] == 'complete' and whole['live'] == live['live'] == LIVE and
              whole['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and whole['release_sha256'] == c.sha(release_path) and
              whole['live_trace_sha256'] == c.sha(collection/'live.json') and live['remaining_outcomes_exist'] is False and
              whole['durations'] == observed._durations(whole['start'],whole['end']), 'Complete paired live collection required')
    paid = whole['paid_ids']; first = live['attempted_ids']
    c.require(len(first) == LIVE['budget'] and paid[:len(first)] == first and len(paid) == len(set(paid)) == len(names) and
              set(paid) == set(names) and paid[len(first):] == [row['candidate_id'] for row in case['public'] if row['candidate_id'] not in first],
              'Live prefix and declared oracle remainder order required')
    times = {}; previous_end = whole['start']['monotonic_after_ns']; cli_names = set()
    for index,identity in enumerate(paid):
        folder = collection/'queries'/f'{index:02d}'
        decision, completed = c.unseal(folder/'decision.json'),c.unseal(folder/'completed.json')
        record, started = c.unseal(folder/'command/record.json'),c.unseal(folder/'command/started.json')
        observed_pair(record,started)
        expected = dict(index=index,mode='adaptive' if index < LIVE['budget'] else 'oracle-reference',
            candidate_id=identity,native_name=names[identity],paid_ids_before=paid[:index],
            prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(release_path),
            completed_live_trace_sha256=None if index < LIVE['budget'] else c.sha(collection/'live.json'),chosen_before_dispatch=True)
        argv = [cohort['python_executable'],'-m','isaforge.integer_workload','measure','--root',target['original_root'],'--candidate',names[identity]]
        argv_hash = hashlib.sha256(json.dumps(argv,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
        c.require(decision == expected == record['metadata'] == started['metadata'] and
                  record['argv_sha256'] == started['argv_sha256'] == argv_hash and started['status'] == 'started' and
                  started['start'] == record['start'] and record['observer_pid'] == whole['observer_pid'] and
                  record['status'] in ('success','nonzero_exit') and record['end']['monotonic_after_ns'] <= whole['end']['monotonic_after_ns'] and
                  previous_end <= record['start']['monotonic_before_ns'], 'Serial source-bound paid dispatch receipts differ')
        c.require(record['durations'] == observed._durations(record['start'],record['end']) and
                  record['durations']['monotonic_endpoints_ordered'], 'Raw paired endpoints/durations differ')
        for stream in ('stdout','stderr'):
            c.require(c.sha(folder/'command'/(stream+'.txt')) == record[stream+'_sha256'], 'Subprocess output hash differs')
        ledger = c.unseal(native/'attempt-ledger'/(names[identity]+'.json'))
        partial = c.unseal(folder/'partial-audit.json')
        partial_labels = {row['candidate_id']:row for row in partial['outcomes']}
        receipt_end = ledger['receipt_end']
        native_receipts = c.unseal(native/'commands.json')
        c.require((record['returncode'] == 0) == (ledger['status'] == 'success') and
                  ledger['status'] in ('success','failed') and partial['context_id'] == audited['context_id'] and
                  partial['charged_candidate_attempts'] == index+1 and partial['candidate_wall_seconds_complete'] and
                  set(partial_labels) == set(paid[:index+1]) and
                  all(value == labels[key] for key,value in partial_labels.items()) and
                  partial['native_command_count'] == receipt_end and
                  partial['native_command_seconds'] == sum(row['elapsed_seconds'] for row in native_receipts[:receipt_end]) and
                  completed['partial_audit_digest'] == c.digest(partial),
                  'Paid partial audit, native receipt prefix or terminal observer status differs')
        c.require(c.unseal(folder/'outcome.json') == labels[identity] and completed['outcome_sha256'] == c.sha(folder/'outcome.json') and
                  completed['candidate_id'] == identity and completed['audited_paid_ids'] == sorted(paid[:index+1]) and
                  completed['ledger_sha256'] == c.sha(native/'attempt-ledger'/(names[identity]+'.json')), 'Paid outcome/ledger evidence differs')
        cli_path = prior._path(native,completed['cli_timer']); cli = c.unseal(cli_path)
        c.require(completed['cli_timer'] not in cli_names and c.sha(cli_path) == completed['cli_timer_sha256'] and
                  cli['command'] == 'measure' and cli['candidate'] == names[identity] and
                  record['durations']['monotonic_elapsed_seconds'] >= cli['elapsed_seconds'] >= labels[identity]['measurement_seconds'],
                  'Nested monotonic duration scopes differ')
        cli_names.add(completed['cli_timer']); times[identity] = cli['elapsed_seconds']
        if index < LIVE['budget']:
            c.require(record['end']['monotonic_after_ns'] <= live['finish']['monotonic_before_ns'], 'Adaptive query after live trace finished')
        else:
            c.require(live['finish']['monotonic_after_ns'] <= record['start']['monotonic_before_ns'], 'Oracle outcome collected before completed live trace')
        previous_end = record['end']['monotonic_after_ns']
    c.require({path.relative_to(native).as_posix() for path in (native/'outer-timing').glob('*.json')
               if c.unseal(path).get('command') == 'measure'} == cli_names, 'Unobserved candidate CLI operation')
    case['selection_root'] = prereg/'targets'/group/'selection'
    used = []
    def paid_provider(row):
        c.require(row['candidate_id'] == first[len(used)], 'Live adaptive choice differs from deterministic paid replay')
        used.append(row['candidate_id']); return labels[row['candidate_id']]
    recreated = run_search(case,paid_provider)
    c.require(b.stable(recreated) == b.stable(live['search']), 'Live GP predictions, decisions or paid curve differ')
    return audited,times,live,whole


def pack(prereg,native,collection,release_path,output):
    prereg,native,collection,output = map(lambda p:Path(p).resolve(),(prereg,native,collection,output))
    cohort,group,target,_ = authenticate(prereg)
    original_native(native,target)
    fresh_output(output,prereg=prereg,native=native,cohort=cohort,extra=(collection,release_path))
    released = c.unseal(release_path)
    prior.check_git_checkpoint(prereg,released['prelabel_commit']); check_baseline(prereg,group,native)
    prior.check_release(release_path,prereg,released['prelabel_commit'],raws={group:native})
    audited,times,live,whole = check_collection(prereg,native,collection,release_path)
    output.mkdir(parents=True); shutil.copytree(collection,output/'collection')
    for suffix in ('','.sha256'): shutil.copyfile(str(release_path)+suffix,str(output/'release.json')+suffix)
    selection = output/'selection'; shutil.copytree(prereg/'targets'/group/'selection',selection)
    refits = prior.verify_refits(selection)
    report = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=times)
    workload().pack(native,output/'native',prelabel_commit=None)
    c.seal(output/'audit.json',audited); c.seal(output/'outer-times.json',times)
    c.seal(output/'endpoints.json',endpoints_for_source(group,report,audited['outcomes']))
    result = dict(schema=SCHEMA+'-campaign',prelabel_commit=released['prelabel_commit'],
        preregistration=prereg.relative_to(ROOT).as_posix(),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        source_bindings=cohort['source_bindings'],workload_group=group,live=LIVE,live_best=live['search']['curve'][-1],
        charged_candidate_attempts=audited['charged_candidate_attempts'],successful_labels=len(audited['successful']),
        historical_costs=cohort['historical_costs'],qualification=cohort['qualification'],
        collection_paired_durations=whole['durations'],refits=refits,trajectories=report['trajectories'],endpoints=report['endpoints'],
        live_native_dispatch=True,other_policies_native_remeasured=False,new_native_jobs=0,limitations=LIMITATIONS)
    c.seal(output/'provenance.json',result); prior._seal_manifest(output)
    return result


def replay(campaign,output):
    campaign,output = map(lambda p:Path(p).resolve(),(campaign,output))
    prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json'); prereg = ROOT/provenance['preregistration']
    cohort,group,target,_ = authenticate(prereg)
    fresh_output(output,prereg=prereg,native=target['original_root'],cohort=cohort,extra=(campaign,))
    c.require(provenance['schema'] == SCHEMA+'-campaign' and provenance['source_bindings'] == cohort['source_bindings'] and
              provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json'), 'Campaign/prelabel binding differs')
    prior.check_git_checkpoint(prereg,provenance['prelabel_commit'])
    raw = output/'native'; audited = workload().replay(campaign/'native',raw); check_baseline(prereg,group,raw)
    prior.check_release(campaign/'release.json',prereg,provenance['prelabel_commit'],raws={group:raw})
    checked,times,live,whole = check_collection(prereg,raw,campaign/'collection',campaign/'release.json')
    c.require(checked == audited == c.unseal(campaign/'audit.json') and times == c.unseal(campaign/'outer-times.json'), 'Replayed native outcomes/timers differ')
    selection = campaign/'selection'; frozen,_ = prior.required_selection(prereg/'targets'/group/'selection')
    c.require(prior._inventory(selection) == frozen|prior.FINAL_REPORTS, 'Complete final selection package required')
    for name in frozen:
        c.require(c.sha(selection/name) == c.sha(prereg/'targets'/group/'selection'/name), 'Prelabel model changed')
    refits = prior.verify_refits(selection)
    report = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=times,verify=True)
    c.require(c.unseal(campaign/'endpoints.json') == endpoints_for_source(group,report,audited['outcomes']) and
              b.stable(provenance['live_best']) == b.stable(live['search']['curve'][-1]) and
              provenance['collection_paired_durations'] == whole['durations'], 'Final campaign decisions or costs differ')
    return dict(charged_candidate_attempts=audited['charged_candidate_attempts'],trajectories=report['trajectories'],
                endpoints=report['endpoints'],**refits,new_native_jobs=0,live_trace_exact=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','release','collect','pack','replay'))
    for name in ('preregistration','native-root','qualification','history','output','release','collection','campaign'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--commit')
    args = parser.parse_args(argv)
    if args.command == 'freeze': result = freeze(args.native_root,args.output,qualification_path=args.qualification,history_path=args.history or HISTORY)
    elif args.command == 'release': result = release(args.preregistration,args.native_root,args.commit,args.output)
    elif args.command == 'collect': result = collect(args.preregistration,args.native_root,args.release,args.output)
    elif args.command == 'pack': result = pack(args.preregistration,args.native_root,args.collection,args.release,args.output)
    else: result = replay(args.campaign,args.output)
    print(result)


if __name__ == '__main__': main()
