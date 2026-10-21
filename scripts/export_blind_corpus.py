"""Append every blind-campaign success, retaining failed charges and source groups."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.speedup_corpus import family
from scripts.export_guarded_corpus import FIELDS, _csv
from scripts.reproduce_guarded_sha256 import _manifest
from scripts.report_blind_campaign import CAMPAIGN, PREREG, COLLECTION, load_targets, collection_costs

PREVIOUS = ROOT/'results/2026-10-21-seven-source-corpus'


def export(previous, campaign, prereg, output, *, collection=COLLECTION):
    previous, campaign, prereg, output = map(lambda path: Path(path).resolve(), (previous, campaign, prereg, output))
    c.require(not output.exists() and not any(output.is_relative_to(path) for path in (previous, campaign, prereg)),
              'Fresh corpus outside frozen inputs required')
    _manifest(previous)
    old = c.unseal(previous/'corpus.json')
    c.require(old['successful_labels'] == len(old['rows']) == 45 and len(old['failed_attempts']) == 3 and
              old['total_candidate_attempts'] == 48 and len(old['independent_workload_groups']) == 7 and
              len(old['contexts']) == 8, 'Complete 45-success/3-failure/48-attempt seven-source history required')
    targets = load_targets(campaign, prereg)
    collection = Path(collection).resolve()
    c.require(not output.is_relative_to(collection), 'Fresh corpus outside collection evidence required')
    collected = collection_costs(collection, campaign, prereg, targets)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(cohort['historical_costs']['source_corpus_sha256'] == c.sha(previous/'corpus.json'),
              'Export history differs from frozen training source')
    rows, failures = list(old['rows']), list(old['failed_attempts'])
    contexts = dict(old['contexts'])
    old_groups = {row['workload_group'] for row in rows+failures}
    collection = []
    for target in targets:
        group, audit, public = (target[key] for key in ('workload', 'audit', 'public'))
        c.require(group not in old_groups, 'Entire new source must be absent from historical contexts')
        labels = {row['candidate_id']: row for row in target['outcomes']}
        for candidate in public:
            row = labels[candidate['candidate_id']]
            enriched = dict(row, workload_group=group, candidate_family=family(row['formula']),
                measurement_timer_scope='guarded attempt ledger wall including validation overhead',
                outer_operation_seconds=target['outer_times'][row['candidate_id']])
            if b.validate_outcome(row, candidate):
                rows.append({**{key: enriched[key] for key in FIELDS},
                    **{key: enriched.get(key) for key in ('measurement_record_seconds', 'measurement_timer_scope', 'outer_operation_seconds')}})
            else:
                c.require('failure_class' in row and type(row.get('reference_censored')) is bool, 'Classified failure required')
                enriched['correctness_verified'] = None if row['reference_censored'] else False
                failures.append(enriched)
        benchmark = public[0]['benchmark']
        c.require(benchmark not in contexts and target['context']['workload_group'] == group,
                  'Distinct context with whole-source group required')
        contexts[benchmark] = target['context']
        collection.append(dict(workload_group=group,
            **{key: audit[key] for key in ('charged_candidate_attempts', 'candidate_wall_seconds',
                'native_command_seconds', 'native_command_count', 'baseline_wall_seconds', 'baseline_record_seconds')},
            candidate_outer_operation_seconds=sum(target['outer_times'].values())))
    c.require(len({row['candidate_id'] for row in rows+failures}) == len(rows)+len(failures), 'Duplicate corpus identity')
    new_attempts = sum(row['charged_candidate_attempts'] for row in collection)
    new_wall = sum(row['candidate_wall_seconds'] for row in collection)
    c.require(len(rows)+len(failures) == old['total_candidate_attempts']+new_attempts,
              'Every paid attempt must be a success or preserved failure')
    groups = sorted({row['workload_group'] for row in rows+failures})
    corpus = dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Consumed historical and blind-source measured pools; all target outcomes are now development data.',
        rows=rows, failed_attempts=failures, contexts=contexts, successful_labels=len(rows),
        independent_workload_groups=groups,
        historical_costs=dict(successful_labels=45, failed_attempts=3, total_candidate_attempts=48,
            total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'], source_corpus_sha256=c.sha(previous/'corpus.json')),
        new_candidate_attempts=new_attempts, total_candidate_attempts=old['total_candidate_attempts']+new_attempts,
        new_candidate_wall_seconds=new_wall,
        total_candidate_attempt_wall_seconds=old['total_candidate_attempt_wall_seconds']+new_wall,
        new_collection_costs=collection,
        qualification_costs=cohort['qualification'],
        collection_costs=collected,
        new_candidate_outer_operation_seconds=sum(row['candidate_outer_operation_seconds'] for row in collection),
        reference_censored_candidates=sorted(row['candidate_id'] for row in failures if row.get('reference_censored')),
        timer_note='Historical measurement-record and guarded-ledger durations retain their scopes. All candidate attempts, including failures, are counted once. New outer-operation timers enclose the ledger and overlap native-command time; complete subprocess wall remains in raw collection evidence. Baseline/setup, calibration and model costs are separate.',
        split_unit='Entire source workload; keep every compiler/hardware context of that source together.',
        new_model_fits=0, new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'corpus.json', corpus)
    _csv(output/'verified-labels.csv', rows)
    _csv(output/'failed-attempts.csv', failures)
    c.seal(output/'provenance.json', dict(source_sha256=c.sha(Path(__file__)),
        previous_manifest_sha256=c.sha(previous/'manifest.json'), campaign_manifest_sha256=c.sha(campaign/'manifest.json'),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'), collection_manifest_sha256=collected['manifest_sha256'],
        new_model_fits=0, new_native_jobs=0))
    (output/'README.md').write_text(
        '# Expanded consumed measured corpus\n\n'
        f"{len(rows)} successful whole-program cycle/hardware labels, {len(failures)} separate failed attempts, "
        f"{len(groups)} source workloads, {len(contexts)} contexts and {corpus['total_candidate_attempts']} charged attempts.\n\n"
        'The original45 successes and three failures are preserved exactly. Infrastructure-censored failures retain unknown correctness, '
        'performance and hardware outcomes. They never become zero-speedup or infeasible training examples. '
        'Historical and new failed attempts contribute their actual recorded elapsed time.\n\n'
        'All contexts from the same source belong in one held-out group; related formula-family exclusions remain necessary. '
        'The complete preregistered source pools were measured before this export; they are now consumed development data. '
        'Native results cover the original recorded inputs and three route seeds, not arbitrary-input correctness or a physical board.\n\n'
        'This exporter reads authenticated packed evidence and runs zero model fits or native jobs. '
        'Run `scripts/blind_campaign.py replay` separately for full chronology and exact frozen-model/policy reproduction.\n')
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, default=PREVIOUS)
    parser.add_argument('--campaign', type=Path, default=CAMPAIGN)
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--collection', type=Path, default=COLLECTION)
    args = parser.parse_args()
    corpus = export(args.previous, args.campaign, args.preregistration, args.output, collection=args.collection)
    print(dict(successful_labels=corpus['successful_labels'], failed_attempts=len(corpus['failed_attempts']),
        source_workloads=len(corpus['independent_workload_groups']), contexts=len(corpus['contexts']),
        new_model_fits=0, new_native_jobs=0))


if __name__ == '__main__':
    main()
