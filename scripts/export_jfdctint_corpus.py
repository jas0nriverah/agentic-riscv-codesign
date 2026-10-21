"""Append authenticated BEEBS whole-program labels, keeping failed costs separate."""
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

PREVIOUS = ROOT/'results/2026-10-21-model-training-corpus'
CAMPAIGN = ROOT/'results/2026-10-21-jfdctint-campaign'
PREREG = ROOT/'results/2026-10-21-jfdctint-preregistration'


def export(previous, campaign, prereg, output):
    previous, campaign, prereg, output = map(lambda path: Path(path).resolve(), (previous, campaign, prereg, output))
    c.require(not output.exists() and not any(output.is_relative_to(path) for path in (previous, campaign, prereg)),
              'Fresh corpus outside frozen inputs required')
    _manifest(previous)
    _manifest(campaign)
    old = c.unseal(previous/'corpus.json')
    audit = c.unseal(campaign/'audit.json')
    c.require(audit['outcomes'] == c.unseal(campaign/'outcomes.json') and audit['attempt_collection_complete'] and
              audit['candidate_wall_seconds_complete'] and not audit['unattempted'], 'Complete native collection required')
    public = b.public_rows(audit['public'])
    group = 'beebs-jfdctint'
    c.require(all(row['benchmark'].split(':', 1)[0] == group for row in public) and
              all(row['workload_group'] != group for row in old['rows']+old['failed_attempts']),
              'Expected one fresh BEEBS source')
    rows, failures = [dict(row) for row in old['rows']], [dict(row) for row in old['failed_attempts']]
    labels = {row['candidate_id']: row for row in audit['outcomes']}
    c.require(len(labels) == len(public) == len(audit['outcomes']) and
              set(labels) == {row['candidate_id'] for row in public}, 'Complete unique candidate identities required')
    for candidate in public:
        row = labels[candidate['candidate_id']]
        enriched = dict(row, workload_group=group, candidate_family=family(row['formula']),
            measurement_timer_scope='guarded attempt ledger wall including validation overhead',
            outer_operation_seconds=c.unseal(campaign/'outer-times.json')[row['candidate_id']])
        if b.validate_outcome(row, candidate):
            rows.append({**{key: enriched[key] for key in FIELDS},
                **{key: enriched.get(key) for key in ('measurement_record_seconds', 'measurement_timer_scope', 'outer_operation_seconds')}})
        else:
            c.require('failure_class' in row and type(row.get('reference_censored')) is bool, 'Classified failure required')
            enriched['correctness_verified'] = None if row['reference_censored'] else False
            failures.append(enriched)
    c.require(len({row['candidate_id'] for row in rows+failures}) == len(rows)+len(failures), 'Duplicate corpus identity')
    context = c.unseal(prereg/'baseline/context.json')
    c.require(context['context_id'] == audit['context_id'] and context['workload_group'] == group,
              'Native/corpus source context differs')
    contexts = {**old['contexts'], public[0]['benchmark']: context}
    groups = sorted({row['workload_group'] for row in rows})
    corpus = dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Consumed six Embench sources and one BEEBS integer DCT source; all target labels are now development data.',
        rows=rows, failed_attempts=failures, contexts=contexts, successful_labels=len(rows),
        independent_workload_groups=groups,
        historical_costs=dict(successful_labels=old['successful_labels'], failed_attempts=len(old['failed_attempts']),
            total_candidate_attempts=old['total_candidate_attempts'],
            total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'], source_corpus_sha256=c.sha(previous/'corpus.json')),
        new_candidate_attempts=audit['charged_candidate_attempts'],
        total_candidate_attempts=old['total_candidate_attempts']+audit['charged_candidate_attempts'],
        new_candidate_wall_seconds=audit['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=old['total_candidate_attempt_wall_seconds']+audit['candidate_wall_seconds'],
        new_collection_costs={key: audit[key] for key in ('native_command_seconds', 'native_command_count',
            'baseline_wall_seconds', 'baseline_record_seconds')},
        new_candidate_outer_operation_seconds=sum(c.unseal(campaign/'outer-times.json').values()),
        reference_censored_candidates=sorted(row['candidate_id'] for row in failures if row.get('reference_censored')),
        timer_note='Historical narrow-record and newer guarded-ledger durations retain distinct scopes. New CLI-operation durations include validation and lock close, excluding interpreter startup; subprocess wall is retained separately in raw evidence. All overlap native command timers. Baseline/setup, calibration and model costs are separate.',
        new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'corpus.json', corpus)
    _csv(output/'verified-labels.csv', rows)
    _csv(output/'failed-attempts.csv', failures)
    c.seal(output/'provenance.json', dict(source_sha256=c.sha(Path(__file__)), previous_manifest_sha256=c.sha(previous/'manifest.json'),
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'), prereg_manifest_sha256=c.sha(prereg/'manifest.json'), new_native_jobs=0))
    (output/'README.md').write_text(
        '# Seven-source measured corpus\n\n'
        f"{len(rows)} successful whole-program speedup/hardware labels, {len(failures)} separate failures, "
        f"{len(groups)} source workloads, {len(contexts)} explicit contexts and {corpus['total_candidate_attempts']} charged attempts. "
        'The new source is pinned BEEBS integer JPEG DCT, not an Embench workload. Its original full input and verifier are unchanged.\n\n'
        'The prospective comparison excluded this entire source and related formula families from all fitting. '
        'The exported outcomes are now consumed development data. Future source splits must hold both SHA contexts together. '
        'Preserved failures include two recorded invalid executions and one infrastructure-censored unknown; none trains a zero-speedup/hardware label.\n\n'
        'Regenerate with `python scripts/export_jfdctint_corpus.py --output generated/seven-source-corpus`. '
        'The CLI first replays the complete raw evidence, prelabel checkpoint, exact model refits and twelve equal-budget policies.\n')
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, default=PREVIOUS)
    parser.add_argument('--campaign', type=Path, default=CAMPAIGN)
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from scripts.reproduce_jfdctint import replay
    replay(campaign=args.campaign, prereg=args.preregistration)
    corpus = export(args.previous, args.campaign, args.preregistration, args.output)
    print(dict(successful_labels=corpus['successful_labels'], failed_attempts=len(corpus['failed_attempts']),
        source_workloads=len(corpus['independent_workload_groups']), contexts=len(corpus['contexts']), new_native_jobs=0))


if __name__ == '__main__':
    main()
