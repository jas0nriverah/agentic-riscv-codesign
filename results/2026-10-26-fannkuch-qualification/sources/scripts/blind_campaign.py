"""Freeze and authenticate a blind cohort using the twelve preserved selectors.

Only freeze/refit operations train the existing fixed models. This script never
starts native measurements; private outcomes are opened only by pack/replay.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, budgeted_selection as b, campaign_evidence as evidence
from isaforge import factorized_selection_experiment as experiment
from isaforge.model import _number
from isaforge.speedup_corpus import family
from scripts.reproduce_guarded_sha256 import _path, _inventory, _hashes, _manifest
from scripts.reproduce_jfdctint import verify_refits, BASELINES, FINAL_REPORTS

SOURCE = 'scripts/blind_campaign.py'
HISTORY = ROOT/'results/2026-10-21-seven-source-corpus/corpus.json'
QUALIFICATION = ROOT/'results/2026-10-21-blind-qualification'
SCHEMA = 'isaforge-blind-cohort-v1'
SOURCES = (SOURCE, 'scripts/collect_blind_campaign.py', 'isaforge/blind_workload.py', 'scripts/reproduce_jfdctint.py',
           'scripts/reproduce_guarded_sha256.py', 'scripts/reproduce_budget_campaign.py',
           'scripts/reproduce_prospective.py', *experiment.SOURCES)


def workload():
    # Late import keeps standalone provenance/timer tests independent of native setup.
    from isaforge import blind_workload
    return blind_workload


def _targets(targets):
    c.require(isinstance(targets, dict) and len(targets) >= 2, 'At least two declared sources required')
    result = {}
    for group, root in targets.items():
        c.require(isinstance(group, str) and group and '/' not in group and '\\' not in group and
                  group not in ('.', '..'), 'Safe unique source group required')
        resolved = Path(root).resolve()
        if (resolved/'plan.json').exists():
            plan = c.unseal(resolved/'plan.json')
            canonical = plan.get('workload_group', group)
            c.require(group in (canonical, plan.get('workload')), 'Declared workload/source group differs')
            c.require(canonical not in result, 'Duplicate source group declaration')
            group = canonical
        result[group] = resolved
    c.require(len(set(result.values())) == len(result), 'Distinct native roots required')
    return result


def _zero(root):
    evidence.prior_inputs.reject_candidate_measurements(root)
    c.require(not list((Path(root)/'attempt-ledger').glob('candidate_*.json')) and
              not list((Path(root)/'measurements').glob('candidate_*')), 'Candidate attempt before cohort release')


def historical_corpus(path):
    path = Path(path).resolve()
    _manifest(path.parent)
    corpus = c.unseal(path)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 45 and
              len(corpus['independent_workload_groups']) == 7 and len(corpus['contexts']) == 8 and
              corpus['total_candidate_attempts'] == 48 and len(corpus['failed_attempts']) == 3,
              'Complete consumed 45-label seven-source history required')
    c.require(len({row['candidate_id'] for row in corpus['rows']+corpus['failed_attempts']}) == 48,
              'Unique historical attempt identities required')
    for row in corpus['rows']:
        c.require(b.validate_outcome(row), 'Only verified historical labels may fit models')
        context = corpus['contexts'][row['benchmark']]
        c.require(context.get('workload_group',row['benchmark'].split(':',1)[0]) == row['workload_group'] and
                  row['benchmark'] == row['workload_group']+':'+context['context_id'], 'Historical source grouping differs')
    return corpus


def historical_costs(corpus, path):
    return dict(successful_labels=45, failed_attempts=3, total_candidate_attempts=48,
        recorded_invalid_executions=sum(not row['reference_censored'] for row in corpus['failed_attempts']),
        censored_unknown_attempts=sum(row['reference_censored'] for row in corpus['failed_attempts']),
        total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(path))


def _seal_manifest(root):
    root = Path(root)
    c.seal(root/'manifest.json', {name: c.sha(_path(root, name)) for name in _inventory(root)
        if name not in ('manifest.json', 'manifest.json.sha256')})


def qualification_evidence(path):
    path = Path(path).resolve()
    c.require(path.is_relative_to(ROOT), 'In-repository qualification evidence required')
    _manifest(path)
    protocol, record = c.unseal(path/'protocol.json'), c.unseal(path/'qualification.json')
    c.require(protocol['schema'] == 'isaforge-blind-qualification-v1' and
              record['protocol_sha256'] == c.sha(path/'protocol.json') and
              type(record['target_candidate_attempts']) is int and record['target_candidate_attempts'] == 0 and
              record['successful_sources'] == len(record['accepted']) == protocol['stop_after_successful_sources'],
              'Complete zero-candidate declared qualification required')
    _hashes(ROOT, protocol['source_bindings'])
    records = record['records']
    c.require([row['workload'] for row in records] == protocol['order'][:len(records)],
              'Declared qualification order differs')
    accepted, roots = {}, {}
    for row in records:
        commands = row['commands']
        c.require(commands and [cmd['phase'] for cmd in commands] == protocol['phases'][:len(commands)] and
                  all(cmd['returncode'] == 0 for cmd in commands[:-1]), 'Qualification command prefix differs')
        if row['status'] == 'accepted':
            c.require(len(commands) == len(protocol['phases']) and commands[-1]['returncode'] == 0 and
                      record['accepted'].get(row['workload']) == row['root'], 'Accepted source qualification incomplete')
            accepted['beebs-'+row['workload']] = row['context_id']
            roots['beebs-'+row['workload']] = row['root']
        else:
            c.require(row['status'] == 'rejected' and commands[-1]['returncode'] != 0 and
                      row['failed_phase'] == commands[-1]['phase'], 'Rejected qualification must retain its terminal failure')
    seconds = sum(_number(cmd['elapsed_seconds'],'qualification subprocess seconds',positive=True)
                  for row in records for cmd in row['commands'])
    c.require(seconds == record['complete_subprocess_seconds'] and len(accepted) == record['successful_sources'],
              'Qualification accepted-source count or subprocess cost differs')
    return dict(path=path.relative_to(ROOT).as_posix(),manifest_sha256=c.sha(path/'manifest.json'),
        protocol_sha256=c.sha(path/'protocol.json'),qualification_sha256=c.sha(path/'qualification.json'),
        setup_subprocess_seconds=seconds,accepted=accepted,original_roots=roots)


def freeze(targets, output, *, history=HISTORY, qualification=QUALIFICATION):
    started = time.monotonic()
    targets = _targets(targets)
    output, history = Path(output).resolve(), Path(history).resolve()
    c.require(output.is_relative_to(ROOT) and not output.exists(), 'Fresh in-repository preregistration required')
    qualified = qualification_evidence(qualification)
    c.require(set(qualified['accepted']) == set(targets) and all(
        root == ROOT/qualified['original_roots'][group] for group,root in targets.items()),
        'Targets must be exactly the declared qualified cohort')
    corpus = historical_corpus(history)
    historical_groups = {row['workload_group'] for row in corpus['rows']+corpus['failed_attempts']}
    c.require(not set(targets) & historical_groups, 'Entire target sources must be absent from history')
    # All targets pass the same pre-fit gate before any model or output is created.
    initial = {}
    for group, root in targets.items():
        _zero(root)
        public, context, before = workload().baseline_public(root)
        c.require(context['workload_group'] == group and before['workload'] == group and
                  public[0]['benchmark'] == group+':'+context['context_id'], 'Declared/native source identity differs')
        plan = c.unseal(root/'plan.json')
        c.require(len(public) == plan['pool_size'] and 6 <= len(public) <= 18,
                  'Declared complete 6..18 candidate pool required')
        c.require(c.unseal(root/'public.json') == public and c.unseal(root/'context.json') == context and
                  c.unseal(root/'before.json') == before, 'Saved public baseline differs')
        initial[group] = (public, context, before)
    contexts = dict(corpus['contexts'])
    for public, context, _ in initial.values():
        contexts[public[0]['benchmark']] = context
    c.require({group:context['context_id'] for group,(_,context,_) in initial.items()} == qualified['accepted'],
              'Qualified and frozen target contexts differ')
    shared = historical_costs(corpus, history)
    c.seal(output/'inputs/history.json', corpus['rows'])
    c.seal(output/'inputs/historical-failures.json', corpus['failed_attempts'])
    c.seal(output/'inputs/contexts.json', contexts)
    cohort = dict(schema=SCHEMA, target_labels_observed=0, target_labels_read=0,
        source_history=history.relative_to(ROOT).as_posix(), historical_costs=shared, qualification=qualified,
        independent_unit='source workload; contexts and seeds are dependent', targets={},
        policies=[*b.POLICIES, experiment.controls.POLICY, experiment.POLICY],
        seeds=list(experiment.SEEDS), budgets=list(experiment.BUDGETS), area_caps=[32,64,128], clock_mhz=12,
        source_bindings={name:c.sha(ROOT/name) for name in dict.fromkeys(SOURCES)},
        primary_endpoint=dict(area_delta_lut4=64, budget=3, clock_mhz=12),
        limitations=['All three-query policies spend three attempts; no automatic stopping claim.',
            'Full-pool serial collection and paid cooperative replay are not live adaptive native search.',
            'Frozen logistic scores and bootstrap spreads are not calibrated confidence.',
            'Unknown infrastructure failures censor the full-pool reference.',
            'Ledger, CLI, subprocess and native-command times overlap; report each scope separately.'])
    for group, root in targets.items():
        public, context, before = initial[group]
        folder = output/'targets'/group
        for name in BASELINES:
            for suffix in ('', '.sha256'):
                target = folder/'baseline'/(name+suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root/(name+suffix), target)
        timers = {}
        for path in sorted((root/'outer-timing').glob('*')):
            c.require(path.is_file(), 'Only regular baseline outer timer artifacts allowed')
            target = folder/'baseline/outer-timing'/path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            timers[path.name] = c.sha(path)
        c.require(timers, 'Complete baseline outer timers required')
        costs = dict(historical_training_available=shared, target_baseline=context['baseline_provenance'],
            note='All48 historical attempts charged once to the cohort, including three failures. Per-target reports repeat shared history for standalone accounting; cohort totals never multiply it. All timers retain their separate overlapping scopes.')
        c.seal(folder/'public.json', public)
        c.seal(folder/'cost-provenance.json', costs)
        bindings = {path.relative_to(ROOT).as_posix():c.sha(path)
                    for path in sorted(output.rglob('*')) if path.is_file() and
                    ('selection' not in path.relative_to(output).parts)}
        bindings[history.relative_to(ROOT).as_posix()] = c.sha(history)
        calibration = evidence._calibration(root)
        protocol = experiment.freeze(corpus['rows'], public, contexts, folder/'selection',
            target_workload=group, target_labels_observed=0, calibration_cost_seconds=calibration['native_command_seconds'],
            cost_provenance=costs, input_bindings=bindings, scope='prospective source holdout')
        cohort['targets'][group] = dict(context_id=context['context_id'], native_order=before['pool_names'],
            pool_size=len(public), original_root=str(root), baseline_files=list(BASELINES),
            baseline_outer_files=timers, selection_protocol_sha256=c.sha(folder/'selection/protocol.json'),
            historical_training_ids=protocol['historical_training_ids'],
            historical_postfilter_groups=protocol['historical_postfilter_groups'])
    # Simultaneous freeze: a candidate attempt in ANY source invalidates ALL freezes.
    for group, root in targets.items():
        _zero(root)
        c.require(workload().baseline_public(root) == initial[group], 'Cohort baseline changed during fitting')
        for name in BASELINES:
            c.require(c.sha(root/name) == c.sha(output/'targets'/group/'baseline'/name),
                      'Baseline changed during complete cohort freeze: '+name)
    cohort['freeze_outer_operation_seconds'] = time.monotonic()-started
    c.seal(output/'cohort.json', cohort)
    _seal_manifest(output)
    return cohort


def required_selection(root):
    root = Path(root)
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol['schema'] == experiment.SCHEMA and protocol['scope'] == 'prospective source holdout' and
              type(protocol['target_labels_observed']) is int and protocol['target_labels_observed'] == 0 and
              type(protocol['target_labels_read']) is int and protocol['target_labels_read'] == 0,
              'Zero-label source holdout selection required')
    _hashes(root, protocol['artifacts'])
    return set(protocol['artifacts'])|{'protocol.json','protocol.json.sha256'}, protocol


def check_preregistration(prereg):
    prereg = Path(prereg).resolve()
    entries = _manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(cohort['schema'] == SCHEMA and type(cohort['target_labels_observed']) is int and
              cohort['target_labels_observed'] == 0 and type(cohort['target_labels_read']) is int and
              cohort['target_labels_read'] == 0 and len(cohort['targets']) >= 2, 'Zero-label multi-source cohort required')
    c.require(cohort['policies'] == [*b.POLICIES, experiment.controls.POLICY, experiment.POLICY] and
              cohort['seeds'] == list(experiment.SEEDS) and cohort['budgets'] == list(experiment.BUDGETS) and
              cohort['area_caps'] == [32,64,128] and cohort['clock_mhz'] == 12,
              'Fixed twelve-policy comparison differs')
    c.require(cohort['source_bindings'] == {name:c.sha(ROOT/name) for name in dict.fromkeys(SOURCES)},
              'Complete frozen campaign sources required')
    qualified = qualification_evidence(_path(ROOT,cohort['qualification']['path']))
    c.require(qualified == cohort['qualification'] and qualified['accepted'] == {
        group:target['context_id'] for group,target in cohort['targets'].items()}, 'Bound qualification cohort differs')
    history_path = _path(ROOT, cohort['source_history'])
    corpus = historical_corpus(history_path)
    history, contexts = c.unseal(prereg/'inputs/history.json'), c.unseal(prereg/'inputs/contexts.json')
    c.require(history == corpus['rows'] and c.unseal(prereg/'inputs/historical-failures.json') == corpus['failed_attempts'] and
              cohort['historical_costs'] == historical_costs(corpus, history_path), 'Complete historical labels/failures/costs differ')
    groups = set(cohort['targets'])
    c.require(not groups & {row['workload_group'] for row in history+corpus['failed_attempts']}, 'Target source in historical outcomes')
    expected_contexts = dict(corpus['contexts'])
    for group, target in cohort['targets'].items():
        folder = prereg/'targets'/group
        frozen, inner = required_selection(folder/'selection')
        experiment.authenticate(folder/'selection')
        prefix = 'targets/'+group+'/selection/'
        c.require({name for name in entries if name.startswith(prefix)} == {prefix+name for name in frozen},
                  'Complete frozen selection inventory required')
        public = c.unseal(folder/'public.json')
        context = c.unseal(folder/'baseline/context.json')
        expected_contexts[public[0]['benchmark']] = context
        c.require(public == c.unseal(folder/'baseline/public.json') and context['workload_group'] == group and
                  context['context_id'] == target['context_id'] and len(public) == target['pool_size'] and
                  public[0]['benchmark'] == group+':'+target['context_id'], 'Frozen public/source context differs')
        c.require(target['baseline_files'] == list(BASELINES), 'Complete native baseline inventory required')
        for name in BASELINES:
            c.unseal(folder/'baseline'/name)
            c.require('targets/'+group+'/baseline/'+name in entries, 'Baseline omitted from manifest')
        _hashes(folder/'baseline/outer-timing', target['baseline_outer_files'], exact=True)
        families = {family(row['formula']) for row in public}
        training = [row for row in history if family(row['formula']) not in families]
        c.require([row['candidate_id'] for row in training] == target['historical_training_ids'] == inner['historical_training_ids'] and
                  sorted({row['workload_group'] for row in training}) == target['historical_postfilter_groups'] and
                  len(target['historical_postfilter_groups']) >= 2, 'Identical post-family-filter fitting cohort required')
        costs = c.unseal(folder/'cost-provenance.json')
        c.require(costs['historical_training_available'] == cohort['historical_costs'] and
                  costs['target_baseline'] == context['baseline_provenance'] and costs == inner['cost_provenance'],
                  'Historical/baseline charge provenance differs')
        c.require(c.sha(folder/'selection/protocol.json') == target['selection_protocol_sha256'] and
                  c.digest(public) == inner['public_digest'] and c.digest(history) == inner['source_history_digest'] and
                  c.digest(contexts) == inner['contexts_digest'] and inner['target_workload'] == group,
                  'Frozen selection input digests differ')
        _hashes(ROOT, inner['input_bindings'])
    c.require(contexts == expected_contexts, 'All historical and cohort source contexts required')
    return cohort


def check_git_checkpoint(prereg, commit):
    """Authenticate every committed artifact, using one read-only git batch."""
    prereg = Path(prereg).resolve()
    c.require(prereg.is_relative_to(ROOT) and isinstance(commit, str) and len(commit) == 40 and
              all(ch in '0123456789abcdef' for ch in commit), 'Exact in-repository prelabel commit required')
    entries = dict(_manifest(prereg))
    entries.update({name:c.sha(prereg/name) for name in ('manifest.json','manifest.json.sha256')})
    expected = {str((prereg/name).relative_to(ROOT)):digest for name,digest in entries.items()}
    cohort = c.unseal(prereg/'cohort.json')
    expected.update(cohort['source_bindings'])
    for group in cohort.get('targets',{}):
        plan = c.unseal(prereg/'targets'/group/'baseline/plan.json')
        for name,digest in plan['source_bindings'].items():
            c.require(name not in expected or expected[name] == digest,'Conflicting committed runtime binding: '+name)
            expected[name] = digest
    if 'qualification' in cohort:
        qualified = _path(ROOT,cohort['qualification']['path'])
        qualification_protocol = c.unseal(qualified/'protocol.json')
        expected.update(qualification_protocol['source_bindings'])
        for name in ('protocol.json','protocol.json.sha256','qualification.json','qualification.json.sha256','manifest.json','manifest.json.sha256'):
            expected[(qualified/name).relative_to(ROOT).as_posix()] = c.sha(qualified/name)
    expected[cohort['source_history']] = cohort['historical_costs']['source_corpus_sha256']
    query = ''.join(commit+':'+name+'\n' for name in expected).encode()
    result = subprocess.run(['git','cat-file','--batch'], input=query, cwd=ROOT, capture_output=True, check=False)
    c.require(result.returncode == 0, 'Git checkpoint object read failed')
    stream = io.BytesIO(result.stdout)
    for name, digest in expected.items():
        header = stream.readline().decode().strip().split()
        c.require(len(header) == 3 and header[1] == 'blob' and header[2].isdigit(), 'Committed preregistration artifact missing: '+name)
        data = stream.read(int(header[2]))
        c.require(stream.read(1) == b'\n' and hashlib.sha256(data).hexdigest() == digest,
                  'Committed prelabel artifact differs: '+name)
    c.require(not stream.read(), 'Unexpected Git checkpoint objects')


def _utc(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('Valid UTC timestamp required') from None
    c.require(result.tzinfo is not None and result.utcoffset() == timedelta(0), 'UTC timestamp required')
    return result


def release(prereg, targets, commit, output, *, branch='ai-guided-ml', remote='origin'):
    prereg, output = Path(prereg).resolve(), Path(output).resolve()
    targets = _targets(targets)
    cohort = check_preregistration(prereg)
    c.require(set(targets) == set(cohort['targets']) and not output.exists() and not output.is_relative_to(prereg) and
              branch == 'ai-guided-ml' and remote == 'origin',
              'Fresh external release and exact complete target cohort on origin/ai-guided-ml required')
    check_git_checkpoint(prereg, commit)
    result = subprocess.run(['git','ls-remote',remote,'refs/heads/'+branch], cwd=ROOT,
                            capture_output=True, text=True, check=False)
    c.require(result.returncode == 0 and result.stdout.strip().split() == [commit,'refs/heads/'+branch],
              'Exact prelabel commit must be pushed before release')
    for group, root in targets.items():
        _zero(root)
        c.require(not (root/'release.json').exists(), 'Preserve previous native release')
        check_baseline(prereg, group, root)
    record = dict(schema=SCHEMA+'-release', prelabel_commit=commit, remote_commit=commit,
        pushed_branch=branch, remote=remote, prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        zero_candidate_attempts=True, target_labels_observed=0, targets={
            group:dict(context_id=value['context_id'], native_order=value['native_order'],
                evaluation_protocol_sha256=c.sha(prereg/'targets'/group/'baseline/evaluation-protocol.json'))
            for group,value in cohort['targets'].items()}, released_at_utc=datetime.now(timezone.utc).isoformat())
    c.seal(output, record)
    for root in targets.values():
        for suffix in ('','.sha256'):
            shutil.copyfile(str(output)+suffix, str(root/'release.json')+suffix)
    return record


def check_baseline(prereg, group, raw):
    prereg, raw = Path(prereg), Path(raw)
    cohort = c.unseal(prereg/'cohort.json'); target = cohort['targets'][group]
    baseline = prereg/'targets'/group/'baseline'
    plan = c.unseal(raw/'plan.json'); workload().check_plan(plan)
    c.require(plan['context_id'] == target['context_id'], 'Native/preregistered context differs')
    for name in BASELINES:
        if name != 'commands.json':
            c.require(c.sha(raw/name) == c.sha(baseline/name), 'Exact preregistered baseline required: '+name)
    prefix = c.unseal(baseline/'commands.json')
    protocol, commands = c.unseal(raw/'evaluation-protocol.json'), c.unseal(raw/'commands.json')
    c.require(protocol['baseline_receipts'] == prefix == commands[:len(prefix)] and
              protocol['pool_names'] == target['native_order'] and protocol['maximum_candidate_attempts'] == target['pool_size'],
              'Exact baseline receipt prefix and declared candidate pool required')
    _hashes(raw/'outer-timing', target['baseline_outer_files'])


def candidate_outer_times(raw, audit, prefix):
    raw = Path(raw)
    _hashes(raw/'outer-timing', prefix)
    extras = _inventory(raw/'outer-timing')-set(prefix)
    records = {name for name in extras if name.endswith('.json')}
    c.require(extras == records|{name+'.sha256' for name in records}, 'Unpaired outer timer artifacts')
    names, public = audit['pool_names'], audit['public']
    c.require(len(names) == len(public) and len(set(names)) == len(names), 'Unique complete native pool required')
    mapping = dict(zip(names, (row['candidate_id'] for row in public)))
    ends = []
    for name in prefix:
        if name.endswith('.json'):
            row = c.unseal(raw/'outer-timing'/name)
            ends.append(_utc(row['started_at_utc'])+timedelta(seconds=_number(row['elapsed_seconds'],'baseline outer seconds',positive=True)))
    c.require(ends, 'Timed baseline prefix required')
    previous = max(ends); times = {}
    for name in sorted(records):
        row = c.unseal(raw/'outer-timing'/name); candidate = row.get('candidate')
        c.require(row.get('schema') == 'isaforge-wrapper-outer-time-v1' and row.get('command') == 'measure' and
                  candidate in mapping, 'Only declared candidate measure timers allowed')
        identity = mapping[candidate]
        c.require(identity not in times, 'Duplicate candidate outer timer')
        ledger = c.unseal(raw/'attempt-ledger'/(candidate+'.json'))
        duration = _number(row.get('elapsed_seconds'),'outer operation seconds',positive=True)
        elapsed = _number(ledger.get('elapsed_seconds'),'ledger seconds',positive=True)
        start, attempt = _utc(row.get('started_at_utc')), _utc(ledger.get('started_at_utc'))
        c.require(ledger['status'] in ('success','failed') and row.get('status') == ledger['status'], 'Outer/ledger terminal status differs')
        c.require(duration >= elapsed and start <= attempt and start+timedelta(seconds=duration) >= attempt+timedelta(seconds=elapsed),
                  'Outer timestamps must enclose attempt ledger')
        c.require(start >= previous, 'Serial candidate timer order differs')
        c.require(isinstance(row.get('scope'),str) and row['scope'].startswith('Complete CLI operation through lock close'),
                  'Complete source-bound CLI timer scope required')
        previous = start+timedelta(seconds=duration); times[identity] = duration
    c.require(set(times) == set(mapping.values()), 'Complete unique candidate outer timers required')
    return {mapping[name]:times[mapping[name]] for name in names}


def check_release(path, prereg, commit, *, raws=None):
    prereg = Path(prereg); cohort = c.unseal(prereg/'cohort.json'); record = c.unseal(path)
    expected = {group:dict(context_id=value['context_id'],native_order=value['native_order'],
        evaluation_protocol_sha256=c.sha(prereg/'targets'/group/'baseline/evaluation-protocol.json'))
        for group,value in cohort['targets'].items()}
    c.require(record.get('schema') == SCHEMA+'-release' and record.get('prelabel_commit') == commit and
              record.get('remote_commit') == commit and record.get('remote') == 'origin' and
              record.get('pushed_branch') == 'ai-guided-ml' and
              record.get('prereg_manifest_sha256') == c.sha(prereg/'manifest.json') and
              record.get('zero_candidate_attempts') is True and type(record.get('target_labels_observed')) is int and
              record['target_labels_observed'] == 0 and record.get('targets') == expected,
              'Complete pushed zero-attempt cohort release required')
    released = _utc(record.get('released_at_utc'))
    if raws is not None:
        c.require(set(raws) == set(expected), 'Complete native cohort required for release chronology')
        for root in raws.values():
            c.require(c.sha(Path(root)/'release.json') == c.sha(path), 'Native release copy differs')
            for ledger in (Path(root)/'attempt-ledger').glob('candidate_*.json'):
                c.require(released < _utc(c.unseal(ledger)['started_at_utc']), 'Release must precede every candidate ledger')
            for timer in (Path(root)/'outer-timing').glob('*.json'):
                row = c.unseal(timer)
                if row.get('command') == 'measure':
                    c.require(released < _utc(row['started_at_utc']), 'Release must precede every candidate outer operation')
    return record


def pack(prereg, targets, output, *, commit, release_path):
    prereg, output = Path(prereg).resolve(), Path(output).resolve(); targets = _targets(targets)
    cohort = check_preregistration(prereg)
    c.require(set(targets) == set(cohort['targets']) and not output.exists() and not output.is_relative_to(prereg),
              'Fresh campaign and complete target cohort required')
    check_git_checkpoint(prereg, commit)
    check_release(release_path, prereg, commit, raws=targets)
    audits, times = {}, {}
    for group, raw in targets.items():
        check_baseline(prereg, group, raw)
        audits[group] = workload().audit(raw)
        experiment.checked_outcomes(audits[group]['public'],audits[group]['outcomes'],audits[group])
        c.require(audits[group]['public'] == c.unseal(prereg/'targets'/group/'public.json'), 'Native/frozen public pool differs')
        times[group] = candidate_outer_times(raw,audits[group],cohort['targets'][group]['baseline_outer_files'])
    output.mkdir(parents=True)
    for suffix in ('','.sha256'):
        shutil.copyfile(str(release_path)+suffix,str(output/'release.json')+suffix)
    reports = {}
    for group, raw in targets.items():
        folder = output/'targets'/group
        shutil.copytree(prereg/'targets'/group/'selection',folder/'selection')
        verify_refits(folder/'selection')
        report = experiment.evaluate(folder/'selection',audits[group]['outcomes'],native_audit=audits[group],outer_times=times[group])
        c.require(report['trajectories'] == 180 and report['endpoints'] == 540, 'Complete twelve-policy report required')
        workload().pack(raw,folder/'native',prelabel_commit=None)
        c.seal(folder/'audit.json',audits[group]); c.seal(folder/'outer-times.json',times[group])
        reports[group] = dict(charged_candidate_attempts=audits[group]['charged_candidate_attempts'],
            candidate_wall_seconds=audits[group]['candidate_wall_seconds'], trajectories=180,endpoints=540)
    c.seal(output/'provenance.json',dict(schema=SCHEMA+'-campaign',prelabel_commit=commit,
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(output/'release.json'),
        source_bindings=cohort['source_bindings'],targets=reports,new_native_jobs=0))
    _seal_manifest(output)
    return reports


def replay(campaign, output, *, prereg):
    campaign, output, prereg = map(lambda p:Path(p).resolve(),(campaign,output,prereg))
    _manifest(campaign); cohort = check_preregistration(prereg)
    provenance = c.unseal(campaign/'provenance.json')
    c.require(provenance['schema'] == SCHEMA+'-campaign' and not output.exists() and
              provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
              provenance['release_sha256'] == c.sha(campaign/'release.json') and
              provenance['source_bindings'] == cohort['source_bindings'] and set(provenance['targets']) == set(cohort['targets']),
              'Complete source-bound campaign and fresh replay output required')
    check_git_checkpoint(prereg,provenance['prelabel_commit'])
    results, raws = {}, {}
    for group in cohort['targets']:
        folder = campaign/'targets'/group; selection = folder/'selection'
        frozen, _ = required_selection(prereg/'targets'/group/'selection')
        c.require(_inventory(selection) == frozen|FINAL_REPORTS, 'Exactly three sealed final reports required')
        for name in frozen:
            c.require(c.sha(selection/name) == c.sha(prereg/'targets'/group/'selection'/name), 'Prelabel model changed: '+name)
        raw = output/group; raws[group] = raw
        audited = workload().replay(folder/'native',raw)
        c.require(audited == c.unseal(folder/'audit.json'), 'Archived/native audit differs')
        check_baseline(prereg,group,raw)
        times = candidate_outer_times(raw,audited,cohort['targets'][group]['baseline_outer_files'])
        c.require(times == c.unseal(folder/'outer-times.json'), 'Archived outer times differ')
        refits = verify_refits(selection)
        report = experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=times,verify=True)
        c.require(report['trajectories'] == 180 and report['endpoints'] == 540 and report['new_native_jobs'] == 0,
                  'Complete hardware-free policy replay required')
        results[group] = dict(charged_candidate_attempts=audited['charged_candidate_attempts'],
            candidate_wall_seconds=audited['candidate_wall_seconds'],trajectories=180,endpoints=540)
        c.require(results[group] == provenance['targets'][group], 'Campaign count/time totals differ')
        results[group].update(refits)
    check_release(campaign/'release.json',prereg,provenance['prelabel_commit'],raws=raws)
    return dict(targets=results,new_native_jobs=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','release','pack','replay'))
    parser.add_argument('--target',action='append',default=[],help='Declared source-group=absolute-native-root; repeat for every source')
    parser.add_argument('--preregistration',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--history',type=Path,default=HISTORY)
    parser.add_argument('--qualification',type=Path,default=QUALIFICATION)
    parser.add_argument('--commit'); parser.add_argument('--release',type=Path); parser.add_argument('--campaign',type=Path)
    args = parser.parse_args(argv)
    targets = {}
    for value in args.target:
        group, sep, root = value.partition('=')
        c.require(sep and group not in targets,'Unique source-group=root declarations required')
        targets[group] = root
    if args.command == 'freeze':
        c.require(args.output.resolve() == args.preregistration.resolve(),'Freeze output must equal preregistration')
        result = freeze(targets,args.output,history=args.history,qualification=args.qualification)
    elif args.command == 'release': result = release(args.preregistration,targets,args.commit,args.output)
    elif args.command == 'pack':
        c.require(args.release is not None,'Release receipt required')
        result = pack(args.preregistration,targets,args.output,commit=args.commit,release_path=args.release)
    else:
        c.require(args.campaign is not None,'Campaign required')
        result = replay(args.campaign,args.output,prereg=args.preregistration)
    print(result)


if __name__ == '__main__':
    main()
