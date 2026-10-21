"""Connect fresh guarded workloads to the unchanged ten-policy comparison.

Only historical evidence is replayed at freeze. Full-pool scoring remains a
cooperative paid-label replay, not an external-agent operating-system boundary.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import tempfile

from . import budgeted_selection as model, campaign_evidence as prior, codesign as c
from . import guarded_evidence as evidence, guarded_workload as native

SOURCE = 'isaforge/guarded_selection.py'
SOURCES = (SOURCE, native.SOURCE, evidence.SOURCE, 'isaforge/guarded_attempts.py',
           'isaforge/relocation_guard.py')
CORPUS = c.ROOT/'results/2026-10-21-expanded-corpus/corpus.json'
HISTORY_RAW = c.ROOT/'generated/reproduction/budget-campaign'


def authenticate_history(raw_root):
    """Authenticate the sealed 27 labels and three failures against native archives."""
    from scripts.reproduce_budget_campaign import SNAPSHOT, HISTORY, replay
    raw_root = Path(raw_root).resolve()
    replay(SNAPSHOT, raw_root)
    with tempfile.TemporaryDirectory(prefix='isaforge-history-') as folder:
        derived = prior.export_corpus(SNAPSHOT/'selection',
            [raw_root/'target-edn', raw_root/'target-ud'], Path(folder)/'corpus.json',
            history_roots=[raw_root/'history'/Path(name).name for name in HISTORY])
    saved = c.unseal(CORPUS)
    for key in ('rows', 'failed_attempts', 'successful_labels', 'independent_workload_groups'):
        c.require(derived[key] == saved[key], 'Archived expanded history differs: '+key)
    c.require(len(derived['rows']) == 27 and len(derived['failed_attempts']) == 3,
              'Expected the fixed 27-label, three-failure development corpus')
    verified = sum(r['measurement_seconds'] for r in derived['rows'])
    failed = sum(r['measurement_seconds'] for r in derived['failed_attempts'])
    costs = dict(successful_labels=27, failed_attempts=3, total_candidate_attempts=30,
        verified_candidate_wall_seconds=verified, failed_candidate_wall_seconds=failed,
        total_candidate_wall_seconds=verified+failed,
        prior_history_costs=derived['historical_costs'], prior_campaign_audits=derived['campaign_audits'],
        note='Frozen model historical_candidate_wall_seconds sums successful labels only; add failed_candidate_wall_seconds once for full historical attempt cost. Baseline/setup/command/inference scopes remain separate.')
    return derived, costs


def _check_native_protocol(root, before):
    protocol = c.unseal(Path(root)/'evaluation-protocol.json')
    c.require(protocol['schema'] == 'isaforge-guarded-measurement-protocol-v1' and
        protocol['context_id'] == before['context_id'] and protocol['attempts_per_candidate'] == 1,
        'Guarded evaluation protocol differs from accepted baseline')
    c.require(protocol['pool_names'] == before['pool_names'] and
        c.digest(protocol['baseline_receipts']) == c.digest(before['receipts']), 'Guarded baseline/pool receipt binding differs')
    c.require(protocol['area_caps'] == [32,64,128] and protocol['clock_mhz'] == 12.0,
              'Use the fixed hardware constraints')
    return protocol


def freeze(target_root, output, *, history_raw_root=HISTORY_RAW, scope='prospective'):
    target_root, output = Path(target_root).resolve(), Path(output).resolve()
    c.require(not output.exists(), 'Preserve prior guarded selection protocols')
    c.require(scope in ('prospective', 'engineering-validation'), 'Explicit selection scope required')
    c.require(not list((target_root/'attempt-ledger').glob('candidate_*.json')),
              'Candidate ledger preceded prediction freeze')
    public, context, before = native.baseline_public(target_root)
    native_protocol = _check_native_protocol(target_root, before)
    corpus, costs = authenticate_history(history_raw_root)
    workload = before['workload']
    if scope == 'prospective':
        c.require(workload not in corpus['independent_workload_groups'],
                  'Prospective target must be a new source workload, not an existing five-workload context')
        c.require(native_protocol['scope'] == 'dataset-expansion', 'Prospective selection needs a dataset-expansion measurement protocol')
    training = [r for r in corpus['rows'] if r['workload_group'] != workload]
    contexts = dict(corpus['contexts']); contexts[public[0]['benchmark']] = context
    output.mkdir(parents=True)
    calibration = prior._calibration(target_root)
    model.freeze(training, public, contexts, output/'model', target_workload=workload,
        calibration_cost_seconds=calibration['native_command_seconds'], cost_provenance=costs,
        scope='prospective' if scope == 'prospective' else 'consumed-data development')
    for name, value in (('historical-corpus.json',corpus),('baseline.json',before)):
        c.seal(output/name,value)
    protocol = dict(schema='isaforge-guarded-selection-v1', scope=scope, target_workload=workload,
        target_labels_read=0, historical_costs=costs, whole_target_excluded_ids=[r['candidate_id']
            for r in corpus['rows'] if r['workload_group'] == workload],
        evaluation_protocol_sha256=c.sha(target_root/'evaluation-protocol.json'),
        source_bindings={name:c.sha(c.ROOT/name) for name in SOURCES},
        corpus_sha256=c.sha(CORPUS), historical_raw_root=str(Path(history_raw_root).resolve()),
        artifacts={p.relative_to(output).as_posix():c.sha(p) for p in output.rglob('*') if p.is_file()},
        limitations=['Engineering validation of a consumed workload is not held-out source-family ML evidence.',
            'Historical failure time is charged separately from the successful-label training sum.',
            'Unknown outcomes remain censored; reference gaps cannot establish full-pool regret.',
            'Paid-label replay is cooperative, not an external-agent sandbox.'])
    # Close the race between baseline acceptance and completion of historical fitting.
    native.baseline_public(target_root)
    c.require(not list((target_root/'attempt-ledger').glob('candidate_*.json')), 'Candidate ledger appeared during freeze')
    c.require(c.sha(target_root/'evaluation-protocol.json') == protocol['evaluation_protocol_sha256'], 'Evaluation protocol changed during freeze')
    c.seal(output/'protocol.json',protocol)
    return protocol


def evaluate(root, target_root, *, history_raw_root=None, verify=False):
    root, target_root = Path(root), Path(target_root)
    protocol = c.unseal(root/'protocol.json')
    for name, digest in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == digest, 'Frozen guarded selection source changed: '+name)
    for name, digest in protocol['artifacts'].items():
        c.require(c.sha(root/name) == digest, 'Frozen guarded selection artifact changed: '+name)
    c.require(c.sha(CORPUS) == protocol['corpus_sha256'], 'Historical corpus snapshot changed')
    c.require(c.sha(target_root/'evaluation-protocol.json') == protocol['evaluation_protocol_sha256'], 'Frozen evaluation protocol changed')
    before = c.unseal(root/'baseline.json'); _check_native_protocol(target_root,before)
    for name, digest in before['artifacts'].items():
        c.require(c.sha(target_root/name) == digest, 'Frozen guarded baseline changed: '+name)
    corpus, costs = authenticate_history(history_raw_root or protocol['historical_raw_root'])
    frozen = c.unseal(root/'historical-corpus.json')
    c.require(corpus['rows'] == frozen['rows'] and corpus['failed_attempts'] == frozen['failed_attempts']
              and costs == protocol['historical_costs'], 'Authenticated historical labels/costs changed')
    training = [r for r in corpus['rows'] if r['workload_group'] != protocol['target_workload']]
    refit = prior.verify_predictions(root/'model',training)
    checked = evidence.audit(target_root)
    c.require(checked['context_id'] == before['context_id'] and checked['attempt_collection_complete']
              and not checked['unattempted'] and checked['candidate_wall_seconds_complete'],
              'All frozen candidates require terminal attempts and known elapsed costs before policy scoring')
    public, outcomes = checked['public'], checked['outcomes']
    c.require(public == c.unseal(root/'model/public.json') and len(outcomes) == len(public), 'Complete frozen outcome/public pool required')
    c.require(all(type(r['measurement_seconds']) in (int,float) and math.isfinite(r['measurement_seconds'])
                  and r['measurement_seconds'] > 0 for r in outcomes), 'Finite positive charged attempt durations required')
    result = model.evaluate(root/'model',outcomes,verify=verify)
    report = dict(schema='isaforge-guarded-selection-report-v1', scope=protocol['scope'],
        protocol_sha256=c.sha(root/'protocol.json'), historical_costs=costs, prediction_refit=refit,
        raw_audit=checked, selection=result, best_verified_references=checked['best_verified_references'],
        reference_censored_candidates=checked['reference_censored_candidates'],
        reference_interpretation='Best verified reference only; any unknown outcome makes the full-pool optimum unresolved.',
        broad_generalization_established=False, new_native_jobs=0)
    if verify: c.require(model.stable(report) == model.stable(c.unseal(root/'report.json')), 'Guarded selection replay differs')
    else:
        c.require(not (root/'report.json').exists(), 'Preserve prior guarded selection report')
        c.seal(root/'report.json',report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','evaluate','replay'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--target-root',type=Path,required=True)
    parser.add_argument('--history-raw-root',type=Path)
    parser.add_argument('--scope',choices=('prospective','engineering-validation'),default='prospective')
    args=parser.parse_args(argv)
    if args.command=='freeze':
        result=freeze(args.target_root,args.root,history_raw_root=args.history_raw_root or HISTORY_RAW,scope=args.scope)
        print(dict(scope=result['scope'],target_labels_read=0,historical_costs=result['historical_costs']))
    else:
        result=evaluate(args.root,args.target_root,history_raw_root=args.history_raw_root,verify=args.command=='replay')
        print(dict(scope=result['scope'],new_native_jobs=0,reference_censored_candidates=result['reference_censored_candidates']))


if __name__=='__main__': main()
