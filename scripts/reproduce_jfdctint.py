"""Git-bound exact replay of the fresh-source BEEBS integer DCT experiment.

Reconstruct labels and complete operation timers from archived native evidence,
refit all frozen models, and replay twelve policies without hardware jobs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, budgeted_selection as b, guarded_evidence
from isaforge import beebs_workload as workload, factorized_selection_experiment as experiment
from isaforge.feasible_benefit import FeasibleBenefitPredictor, AREA_CAPS
from isaforge.feasibility_selection import FeasibilitySelectionPredictor
from isaforge.model import _number
from isaforge.speedup_corpus import family
from scripts.reproduce_budget_campaign import check_prelabel_commit
from scripts.reproduce_guarded_sha256 import _path, _inventory, _hashes, _manifest

PREREG = ROOT/'results/2026-10-21-jfdctint-preregistration'
SELECTION = ROOT/'results/2026-10-21-jfdctint-selection'
CAMPAIGN = ROOT/'results/2026-10-21-jfdctint-campaign'
OUTPUT = ROOT/'generated/reproduction/jfdctint'
SOURCE = 'scripts/reproduce_jfdctint.py'
SOURCES = (SOURCE, 'scripts/reproduce_guarded_sha256.py', 'scripts/reproduce_budget_campaign.py',
           'scripts/reproduce_prospective.py', workload.SOURCE)
WORKLOAD = 'beebs-jfdctint'
BASELINES = ('plan.json', 'discovery/discovery.json', 'measurements/baseline/measurement.json',
             'commands.json', 'evaluation-protocol.json', 'attempt-ledger/baseline.json',
             'public.json', 'context.json', 'before.json')
FINAL_REPORTS = {name+suffix for name in ('report.json', 'controls11/report.json',
                 'controls11/model/report.json') for suffix in ('', '.sha256')}


def required_selection(selection):
    selection = Path(selection)
    protocol = c.unseal(selection/'protocol.json')
    c.require(protocol.get('schema') == experiment.SCHEMA and
              protocol.get('scope') == 'prospective source holdout' and
              protocol.get('target_workload') == WORKLOAD and
              type(protocol.get('target_labels_read')) is int and protocol['target_labels_read'] == 0 and
              type(protocol.get('target_labels_observed')) is int and protocol['target_labels_observed'] == 0 and
              protocol.get('policies') == [*b.POLICIES, experiment.controls.POLICY, experiment.POLICY],
              'Expected zero-label twelve-policy BEEBS source freeze')
    artifacts = protocol.get('artifacts')
    _hashes(selection, artifacts)
    c.require(not {'protocol.json', 'protocol.json.sha256'} & set(artifacts),
              'Frozen protocol cannot inventory itself')
    return set(artifacts)|{'protocol.json', 'protocol.json.sha256'}, protocol


def check_inputs(prereg, protocol, outer):
    prereg = Path(prereg)
    bindings = c.unseal(prereg/'inputs/bindings.json')
    c.require(bindings == protocol['input_bindings'], 'Frozen input bindings differ')
    _hashes(ROOT, bindings)
    _hashes(ROOT, outer['source_bindings'])
    history = c.unseal(prereg/'inputs/history.json')
    public = c.unseal(prereg/'inputs/public.json')
    contexts = c.unseal(prereg/'inputs/contexts.json')
    costs = c.unseal(prereg/'inputs/cost-provenance.json')
    corpus = c.unseal(_path(ROOT, outer['source_history']))
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 39 and
              len(corpus['contexts']) == 7 and len(corpus['independent_workload_groups']) == 6 and
              corpus['total_candidate_attempts'] == 42 and len(corpus['failed_attempts']) == 3,
              'Complete consumed 39-label historical corpus required')
    c.require(history == corpus['rows'] and
              c.unseal(prereg/'inputs/historical-failures.json') == corpus['failed_attempts'] and
              all(row['workload_group'] != WORKLOAD for row in history+corpus['failed_attempts']),
              'Entire target source must be absent from historical outcomes')
    c.require(c.digest(history) == protocol['source_history_digest'] and
              c.digest(public) == protocol['public_digest'] and
              c.digest(contexts) == protocol['contexts_digest'] and
              costs == protocol['cost_provenance'], 'Frozen source/input/cost digest differs')
    context = c.unseal(prereg/'baseline/context.json')
    expected = dict(corpus['contexts']); expected[public[0]['benchmark']] = context
    c.require(contexts == expected and public == c.unseal(prereg/'baseline/public.json'),
              'Historical/native context assembly differs')
    c.require(public[0]['benchmark'] == WORKLOAD+':'+context['context_id'] and
              context['workload_group'] == WORKLOAD, 'BEEBS source context differs')
    available = costs['historical_training_available']
    c.require(available == dict(successful_labels=39, failed_attempts=3,
        recorded_invalid_executions=sum(not row['reference_censored'] for row in corpus['failed_attempts']),
        censored_unknown_attempts=sum(row['reference_censored'] for row in corpus['failed_attempts']),
        total_candidate_attempts=42, total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(_path(ROOT, outer['source_history']))) and
        costs['target_baseline'] == context['baseline_provenance'], 'Historical/baseline charges differ')
    families = {family(row['formula']) for row in public}
    fitting = [row for row in history if family(row['formula']) not in families]
    c.require([row['candidate_id'] for row in fitting] == protocol['historical_training_ids'] and
              len({row['workload_group'] for row in fitting}) >= 2,
              'Fixed historical family-excluded cohort differs')


def check_prelabel(selection, prereg):
    selection, prereg = Path(selection), Path(prereg)
    entries = _manifest(prereg)
    required, inner = required_selection(selection)
    c.require({name for name in entries if name.startswith('selection/')} ==
              {'selection/'+name for name in required} and
              {name.removeprefix('selection/') for name in _inventory(prereg) if name.startswith('selection/')} == required,
              'Complete preregistered frozen selection inventory required')
    for name in required:
        c.require(c.sha(_path(selection, name)) == entries['selection/'+name],
                  'Changed prelabel model artifact: '+name)
    outer = c.unseal(prereg/'protocol.json')
    c.require(outer.get('schema') == 'isaforge-jfdctint-preregistration-v1' and
              outer.get('target_workload') == WORKLOAD and outer.get('scope') == 'prospective source holdout' and
              type(outer.get('target_candidate_attempts_before_and_after_fit')) is int and
              outer['target_candidate_attempts_before_and_after_fit'] == 0 and
              type(outer.get('target_candidate_labels_observed')) is int and
              outer['target_candidate_labels_observed'] == 0 and outer.get('selection_policy_count') == 12,
              'Zero-attempt fresh-source preregistration required')
    c.require(outer.get('baseline_files') == list(BASELINES), 'Complete baseline-copy list required')
    expected = {'baseline/'+name+suffix for name in BASELINES for suffix in ('', '.sha256')}
    c.require(expected <= entries.keys(), 'Preregistered baseline file omitted')
    for name in BASELINES: c.unseal(prereg/'baseline'/name)
    timers = outer.get('baseline_outer_files')
    c.require(isinstance(timers, dict) and timers, 'Baseline outer timer prefix required')
    _hashes(prereg/'baseline/outer-timing', timers, exact=True)
    c.require({'baseline/outer-timing/'+name for name in timers} <= entries.keys(), 'Unbound baseline outer timer')
    c.require(outer['selection_protocol_sha256'] == c.sha(selection/'protocol.json'), 'Frozen selection protocol differs')
    check_inputs(prereg, inner, outer)
    return c.sha(prereg/'manifest.json')


def check_baselines(prereg, raw, selection):
    prereg, raw, selection = map(Path, (prereg, raw, selection))
    outer = c.unseal(prereg/'protocol.json')
    plan = c.unseal(raw/'plan.json'); workload.check_plan(plan)
    c.require(plan['context_id'] == outer['context_id'], 'Native/preregistered source context differs')
    for name in BASELINES:
        if name != 'commands.json':
            c.require(c.sha(_path(raw, name)) == c.sha(_path(prereg, 'baseline/'+name)),
                      'Preregistered native baseline changed: '+name)
    before = c.unseal(prereg/'baseline/commands.json')
    evaluation, commands = c.unseal(raw/'evaluation-protocol.json'), c.unseal(raw/'commands.json')
    c.require(before == evaluation['baseline_receipts'] and commands[:len(before)] == before,
              'Exact baseline receipt prefix required')
    c.require(evaluation['pool_names'] == outer['native_order'] and evaluation['maximum_candidate_attempts'] == 6,
              'Frozen six-candidate order differs')
    _hashes(raw/'outer-timing', outer['baseline_outer_files'])
    c.require(c.unseal(raw/'public.json') == c.unseal(selection/'controls11/model/public.json'),
              'Native/frozen public rows differ')


def _utc(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('Valid UTC outer-operation timestamp required') from None
    c.require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), 'UTC timestamp required')
    return parsed


def candidate_outer_times(raw, native_audit, prereg):
    """Derive complete operation times; every attempted candidate appears once."""
    raw, prereg = Path(raw), Path(prereg)
    outer = c.unseal(prereg/'protocol.json')
    prefix = outer['baseline_outer_files']
    _hashes(raw/'outer-timing', prefix)
    extras = _inventory(raw/'outer-timing')-set(prefix)
    records = {name for name in extras if name.endswith('.json')}
    c.require(extras == records|{name+'.sha256' for name in records}, 'Unpaired outer timer artifacts')
    names, public = native_audit['pool_names'], native_audit['public']
    c.require(len(names) == len(public) == 6 and len(set(names)) == 6, 'Unique complete native pool required')
    mapping = dict(zip(names, (row['candidate_id'] for row in public)))
    ends = []
    for name in prefix:
        if name.endswith('.json'):
            record = c.unseal(_path(raw/'outer-timing', name))
            ends.append(_utc(record.get('started_at_utc')) + timedelta(seconds=
                        _number(record.get('elapsed_seconds'), 'baseline outer seconds', positive=True)))
    c.require(ends, 'Timed baseline prefix required')
    previous_end = max(ends)
    times = {}
    for name in sorted(records):
        record = c.unseal(_path(raw/'outer-timing', name))
        candidate = record.get('candidate')
        c.require(record.get('schema') == 'isaforge-wrapper-outer-time-v1' and
                  record.get('command') == 'measure' and candidate in mapping,
                  'Only candidate measure operations may follow baseline timer prefix')
        identity = mapping[candidate]
        c.require(identity not in times, 'Duplicate candidate outer timer')
        ledger = c.unseal(raw/'attempt-ledger'/(candidate+'.json'))
        duration = _number(record.get('elapsed_seconds'), 'outer operation seconds', positive=True)
        c.require(ledger['status'] in ('success', 'failed') and record.get('status') == ledger['status'],
                  'Outer operation/attempt terminal status differs')
        c.require(duration >= _number(ledger['elapsed_seconds'], 'ledger seconds', positive=True),
                  'Complete outer operation must enclose attempt ledger')
        scope = record.get('scope')
        c.require(isinstance(scope, str) and scope.startswith('Complete CLI operation through lock close'),
                  'Complete source-bound CLI timer scope required')
        start, attempt = _utc(record.get('started_at_utc')), _utc(ledger.get('started_at_utc'))
        c.require(start >= previous_end, 'Serial candidate operation timestamp order differs')
        c.require(start <= attempt and start+timedelta(seconds=duration) >=
                  attempt+timedelta(seconds=ledger['elapsed_seconds']),
                  'Outer timestamps do not enclose attempt')
        previous_end = start+timedelta(seconds=duration)
        times[identity] = duration
    c.require(set(times) == set(mapping.values()), 'Complete unique candidate outer timers required')
    return {mapping[name]: times[mapping[name]] for name in names}


def verify_refits(selection):
    selection = Path(selection)
    case = experiment.authenticate(selection)
    public, history = case['public'], case['history']
    original = c.unseal(selection/'controls11/model/predictions.json')
    utility = c.unseal(selection/'controls11/utility-predictions.json')
    classifier = case['predictions']
    c.require([row['seed'] for row in original] == list(experiment.SEEDS), 'Complete ordered control seeds required')
    with tempfile.TemporaryDirectory(prefix='isaforge-jfdctint-refit-') as temporary:
        for frozen in original:
            seed = frozen['seed']
            c.require(b.stable(b.zero_shot(history, public, seed)) == b.stable(frozen),
                      'Original control prediction refit differs')
            for model_class, values, directory in (
                (FeasibleBenefitPredictor, utility, 'controls11/utility-models'),
                (FeasibilitySelectionPredictor, classifier, 'feasibility-models')):
                model = model_class(seed).fit(history)
                by_cap = next(row for row in values if row['seed'] == seed)['by_cap']
                c.require(all(model.predict(public, area_cap=cap) == by_cap[str(cap)] for cap in AREA_CAPS),
                          'Frozen model prediction refit differs: '+directory)
                schema = model.save(Path(temporary)/directory/f'seed-{seed}')
                c.require(schema == c.unseal(selection/directory/f'seed-{seed}'/'schema.json'),
                          'Exported model JSON/schema refit differs: '+directory)
    return dict(original_control_prediction_refits=5, utility_prediction_and_model_refits=5,
                feasibility_prediction_and_model_refits=5)


def _release(path, commit, prereg, native, *, raw=None):
    record = c.unseal(path)
    c.require(record.get('schema') == 'isaforge-jfdctint-release-v1' and
              record.get('prelabel_commit') == commit and
              record.get('remote_commit') == commit and record.get('pushed_branch') == 'ai-guided-ml' and
              record.get('prereg_manifest_sha256') == c.sha(Path(prereg)/'manifest.json') and
              record.get('context_id') == native['context_id'] and
              record.get('evaluation_protocol_sha256') == native['protocol_sha256'] and
              record.get('zero_candidate_attempts') is True and
              type(record.get('target_labels_observed')) is int and record['target_labels_observed'] == 0 and
              record.get('native_order') == native['pool_names'],
              'Git-bound pushed zero-attempt release receipt required')
    released = _utc(record.get('released_at_utc'))
    if raw is not None:
        for path in sorted((Path(raw)/'outer-timing').glob('*.json')):
            timer = c.unseal(path)
            if timer.get('command') == 'measure':
                c.require(released < _utc(timer.get('started_at_utc')),
                          'Release must precede every candidate outer operation')
    return record


def pack_campaign(native, campaign, selection, prereg, prelabel_commit, release):
    """Package completed evidence; never launches/retries a hardware evaluation."""
    native, campaign, selection, prereg = map(Path, (native, campaign, selection, prereg))
    c.require(not campaign.exists(), 'Preserve existing campaign package')
    prereg_hash = check_prelabel(selection, prereg)
    check_prelabel_commit(prereg, prelabel_commit)
    check_baselines(prereg, native, selection)
    audited = workload.audit(native)
    experiment.checked_outcomes(audited['public'], audited['outcomes'], audited)
    times = candidate_outer_times(native, audited, prereg)
    _release(release, prelabel_commit, prereg, audited, raw=native)
    c.require((native/'release.json').is_file() and c.sha(native/'release.json') == c.sha(release),
              'Native archive must retain exact pre-attempt release receipt')
    required, _ = required_selection(selection)
    final = {name: c.sha(_path(selection, name)) for name in _inventory(selection)}
    c.require(set(final) == required|FINAL_REPORTS, 'Exactly three sealed final reports required')
    campaign.mkdir(parents=True)
    with workload.registration(): guarded_evidence.pack(native, campaign/'native', prelabel_commit=None)
    for name, value in (('audit.json', audited), ('outcomes.json', audited['outcomes']),
                        ('outer-times.json', times), ('selection-manifest.json', final)):
        c.seal(campaign/name, value)
    for suffix in ('', '.sha256'):
        shutil.copyfile(str(release)+suffix, str(campaign/'release-verification.json')+suffix)
    c.seal(campaign/'provenance.json', dict(schema='isaforge-jfdctint-campaign-v1',
        prelabel_commit=prelabel_commit, prereg_manifest_sha256=prereg_hash, selection_manifest=final,
        context_id=audited['context_id'], evaluation_protocol_sha256=audited['protocol_sha256'],
        outcomes_sha256=c.sha(campaign/'outcomes.json'), release_sha256=c.sha(campaign/'release-verification.json'),
        source_bindings={name: c.sha(ROOT/name) for name in SOURCES}))
    (campaign/'README.md').write_text(
        '# Fresh-source BEEBS DCT evidence\n\n'
        'Six serial, one-attempt candidate measurements follow the complete pushed prelabel '
        'checkpoint `' + prelabel_commit + '`. The original source/input and all64 coefficient checks '
        'are unchanged. The native archive rederives every outcome, integrated resource/timing result, '
        'guard/control check and charged duration.\n\n'
        'The inner archive asserts receipt/source integrity. The outer campaign authenticates the entire '
        'committed preregistration, exact native protocol copy, zero-attempt release receipt and later '
        'candidate timestamps. Original-path Git provenance is not claimed by the inner pack.\n\n'
        'Reproduce with `python scripts/reproduce_jfdctint.py` or `make reproduce-jfdctint`. '
        'Replay launches no native jobs and exactly refits the original controls, utility ensemble '
        'and new feasibility ensemble before checking180 trajectories /540 endpoints. '
        'All twelve policies share information and budgets. Predictions are uncalibrated; '
        'one additional source does not establish broad superiority.\n')
    c.seal(campaign/'manifest.json', {name: c.sha(_path(campaign, name)) for name in _inventory(campaign)})
    return audited


def replay(campaign=CAMPAIGN, output=OUTPUT, *, prereg=PREREG, selection=SELECTION):
    campaign, output, prereg, selection = map(Path, (campaign, output, prereg, selection))
    entries = _manifest(campaign)
    required_files = {'provenance.json', 'outcomes.json', 'audit.json', 'outer-times.json',
                      'release-verification.json', 'selection-manifest.json', 'native/manifest.json'}
    c.require({name+suffix for name in required_files for suffix in ('', '.sha256')} <= entries.keys(),
              'Complete campaign evidence/provenance required')
    provenance = c.unseal(campaign/'provenance.json')
    c.require(provenance.get('schema') == 'isaforge-jfdctint-campaign-v1', 'Unknown BEEBS campaign schema')
    c.require(check_prelabel(selection, prereg) == provenance['prereg_manifest_sha256'], 'Prelabel manifest differs')
    check_prelabel_commit(prereg, provenance['prelabel_commit'])
    sources = provenance.get('source_bindings')
    c.require(isinstance(sources, dict) and set(SOURCES) <= sources.keys(), 'Complete replay/helper source bindings required')
    _hashes(ROOT, sources)
    _hashes(selection, provenance.get('selection_manifest'), exact=True)
    frozen, _ = required_selection(selection)
    c.require(set(provenance['selection_manifest']) == frozen|FINAL_REPORTS, 'Exactly three sealed final reports required')
    c.require(c.unseal(campaign/'selection-manifest.json') == provenance['selection_manifest'], 'Final selection inventory differs')
    c.require(c.sha(campaign/'outcomes.json') == provenance['outcomes_sha256'] and
              c.sha(campaign/'release-verification.json') == provenance['release_sha256'], 'Campaign outcome/release binding differs')
    with workload.registration(): audited = guarded_evidence.replay(campaign/'native', output)
    c.require(c.unseal(campaign/'audit.json') == audited, 'Raw audit differs from rederived native evidence')
    check_baselines(prereg, output, selection)
    c.require(audited['context_id'] == provenance['context_id'] and
              audited['protocol_sha256'] == provenance['evaluation_protocol_sha256'], 'Campaign context/protocol differs')
    _release(campaign/'release-verification.json', provenance['prelabel_commit'], prereg, audited, raw=output)
    c.require((output/'release.json').is_file() and
              c.sha(output/'release.json') == c.sha(campaign/'release-verification.json'),
              'Replayed native release receipt differs')
    outcomes = c.unseal(campaign/'outcomes.json')
    experiment.checked_outcomes(audited['public'], outcomes, audited)
    times = candidate_outer_times(output, audited, prereg)
    c.require(c.unseal(campaign/'outer-times.json') == times, 'Archived outer operation timers differ')
    refits = verify_refits(selection)
    result = experiment.evaluate(selection, outcomes, native_audit=audited, outer_times=times, verify=True)
    c.require(audited.get('new_native_jobs') == result.get('new_native_jobs') == 0 and
              result['trajectories'] == 180 and result['endpoints'] == 540,
              'Complete twelve-policy hardware-free replay required')
    return dict(target_workload=WORKLOAD, context_id=audited['context_id'], charged_candidate_attempts=6,
                trajectories=180, endpoints=540, **refits, new_native_jobs=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=CAMPAIGN)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--selection', type=Path, default=SELECTION)
    args = parser.parse_args(argv)
    print(replay(args.campaign, args.output, prereg=args.preregistration, selection=args.selection))


if __name__ == '__main__': main()
