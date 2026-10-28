"""Export authenticated historical and completed selection outcomes for development."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge import budgeted_selection as b
from isaforge.speedup_corpus import family

HISTORY = ROOT / 'results/2026-10-26-lift-selection-corpus'
STUDIES = (
    ('results/2026-10-28-tiny-regex-c-selection-r2', 12),
    ('results/2026-10-28-pulpino-sudoku-selection-r4', 12),
    ('results/2026-10-28-nanocobs-v2-selection-r1', 10),
)
DEFAULT_OUTPUT = ROOT / 'results/2026-10-28-expanded-selection-corpus-r2'
SCHEMA = 'isaforge-expanded-selection-development-corpus-v1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_manifest(folder: Path):
    folder = Path(folder).resolve()
    manifest = c.unseal(folder / 'manifest.json')
    require(isinstance(manifest, dict) and manifest, f'Missing manifest: {folder}')
    for rel, digest in manifest.items():
        path = (folder / rel).resolve()
        require(path.is_relative_to(folder), f'Manifest path escapes evidence root: {rel}')
        require(path.is_file() and sha(path) == digest, f'Manifest mismatch: {path}')
    return manifest


def _normalise(row, *, group=None, consumed=True):
    out = dict(row)
    benchmark = out.get('benchmark')
    require(isinstance(benchmark, str) and ':' in benchmark, 'Missing benchmark source identity')
    derived_group = benchmark.split(':', 1)[0]
    if group is not None:
        require(derived_group == group, f'Unexpected workload group for {benchmark}')
    if 'workload_group' in out:
        require(out['workload_group'] == derived_group, 'workload_group disagrees with benchmark source')
    out['workload_group'] = derived_group
    out['source_id'] = benchmark
    expected_family = family(out['formula'])
    if 'candidate_family' in out:
        require(out['candidate_family'] == expected_family, 'candidate_family disagrees with formula')
    out['candidate_family'] = expected_family
    out['data_use'] = 'consumed-development'
    require(isinstance(out.get('candidate_id'), str) and out['candidate_id'], 'Missing candidate_id')
    if consumed:
        require(b.validate_outcome(out), 'Invalid successful outcome')
    else:
        require(out.get('status') == 'failed' and not b.validate_outcome(out),
                'Historical failed attempt has an invalid status or successful label')
    return out


def _read_study(rel: str, count: int):
    folder = ROOT / rel
    manifest = verify_manifest(folder)
    for name in ('outcomes.json', 'native-audit.json'):
        require(name in manifest, f'{name} is not sealed in {folder}')
    outcomes = c.unseal(folder / 'outcomes.json')
    audit = c.unseal(folder / 'native-audit.json')
    require(len(outcomes) == count, f'Unexpected outcome count in {folder}')
    require(audit.get('schema') == 'isaforge-guarded-evidence-v1' and
            audit.get('attempt_collection_complete') is True and
            audit.get('candidate_wall_seconds_complete') is True and
            audit.get('charged_candidate_attempts') == count and
            len(audit.get('successful', [])) == count and
            not audit.get('failed_or_interrupted') and not audit.get('unattempted'),
            f'Incomplete or failed native audit in {folder}')
    indexed = {r['candidate_id']: r for r in outcomes}
    require(len(indexed) == count and len(audit['outcomes']) == count, 'Duplicate or missing audit identities')
    audit_rows = {r['candidate_id']: r for r in audit['outcomes']}
    require(set(indexed) == set(audit_rows), 'Audit and outcomes candidate identities differ')
    rows = []
    for row in outcomes:
        audited = audit_rows[row['candidate_id']]
        require(audited == row and b.validate_outcome(row),
                'Native audit disagrees with sealed outcome')
        rows.append(_normalise(row))
    require(sum(r['measurement_seconds'] for r in audit['outcomes']) <= audit['candidate_wall_seconds'] + 1e-6,
            'Attempt costs do not cover the audited outcome records')
    return rows, audit, manifest


def _collect():
    history_manifest = verify_manifest(HISTORY)
    historical = c.unseal(HISTORY / 'corpus.json')
    require(historical.get('schema') == 'isaforge-consumed-guarded-corpus-v1' and
            historical.get('successful_labels') == len(historical.get('rows', [])) == 122 and
            len(historical.get('failed_attempts', [])) == 4 and
            historical.get('total_candidate_attempts') == 126,
            'Expected authenticated 122-success / 4-failure historical corpus')
    rows = [_normalise(r) for r in historical['rows']]
    failures = [_normalise(r, consumed=False) for r in historical['failed_attempts']]
    provenance = {'historical': {'root': HISTORY.relative_to(ROOT).as_posix(),
        'manifest_sha256': sha(HISTORY / 'manifest.json'), 'corpus_sha256': history_manifest['corpus.json'],
        'successful_rows': 122, 'failed_attempts': 4}, 'studies': []}
    new_cost = 0.0
    for rel, count in STUDIES:
        added, audit, manifest = _read_study(rel, count)
        rows.extend(added)
        new_cost += audit['candidate_wall_seconds']
        provenance['studies'].append({'root': rel, 'manifest_sha256': sha(ROOT / rel / 'manifest.json'),
            'outcomes_sha256': manifest['outcomes.json'], 'native_audit_sha256': manifest['native-audit.json'],
            'context_id': audit['context_id'], 'successful_rows': count,
            'charged_attempts': audit['charged_candidate_attempts'],
            'candidate_wall_seconds': audit['candidate_wall_seconds']})
    ids = [r['candidate_id'] for r in rows + failures]
    require(len(ids) == len(set(ids)), 'Duplicate candidate_id across success/failure corpus')
    require(len(rows) == 156 and len(failures) == 4, 'Unexpected expanded corpus totals')
    source_contexts = [{'source_id': next(r['source_id'] for r in rows if r['benchmark'].startswith(
        {'results/2026-10-28-tiny-regex-c-selection-r2':'tiny-regex-fixed-suite:',
         'results/2026-10-28-pulpino-sudoku-selection-r4':'pulpino-sudoku:',
         'results/2026-10-28-nanocobs-v2-selection-r1':'nanocobs:'}[study['root']])),
        'context_id': study['context_id'], 'study_root': study['root']} for study in provenance['studies']]
    historical_cost = historical['total_candidate_attempt_wall_seconds']
    corpus = {'schema': SCHEMA, 'scope': 'consumed development data; no prospective or holdout claim',
        'rows': rows, 'failed_attempts': failures, 'contexts': historical['contexts'],
        'new_source_contexts': source_contexts,
        'successful_labels': len(rows), 'failed_attempt_count': len(failures),
        'total_candidate_attempts': len(rows) + len(failures),
        'independent_workload_groups': sorted({r['workload_group'] for r in rows}),
        'historical_costs': historical['historical_costs'], 'historical_total_candidate_attempt_wall_seconds': historical_cost,
        'new_candidate_attempts': 34, 'new_candidate_wall_seconds': new_cost,
        'total_candidate_attempt_wall_seconds': historical_cost + new_cost,
        'timer_note': 'Historical cost scope follows the authenticated source corpus; new costs are audited attempt-ledger wall seconds.',
        'new_native_jobs': 0, 'all_rows_consumed_for_development': True}
    provenance['exporter_sha256'] = sha(Path(__file__))
    return corpus, provenance


def export(output: Path = DEFAULT_OUTPUT):
    output = Path(output).resolve()
    require(not output.exists(), 'Use a fresh output directory')
    corpus, provenance = _collect()
    output.mkdir(parents=True)
    c.seal(output / 'corpus.json', corpus)
    c.seal(output / 'provenance.json', provenance)
    c.seal(output / 'manifest.json', {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    return corpus


def authenticate(path: Path):
    """Load the export only after checking its sealed output manifest."""
    folder = Path(path).resolve()
    manifest = verify_manifest(folder)
    corpus = c.unseal(folder / 'corpus.json')
    provenance = c.unseal(folder / 'provenance.json')
    require(corpus.get('schema') == SCHEMA and corpus.get('successful_labels') == len(corpus['rows']) == 156 and
            corpus.get('failed_attempt_count') == len(corpus['failed_attempts']) == 4 and
            corpus.get('all_rows_consumed_for_development') is True, 'Expanded corpus schema/count/scope mismatch')
    seen = set()
    for row in corpus['rows']:
        normal = _normalise(row)
        require(normal == row, 'Expanded corpus row identity/family is not canonical')
        require(row['candidate_id'] not in seen, 'Duplicate candidate_id')
        seen.add(row['candidate_id'])
    for row in corpus['failed_attempts']:
        require(row.get('candidate_id') not in seen, 'Failure overlaps a success candidate_id')
        seen.add(row.get('candidate_id'))
    require(provenance.get('exporter_sha256') == sha(Path(__file__)), 'Exporter source binding changed')
    expected_corpus, expected_provenance = _collect()
    require(corpus == expected_corpus and provenance == expected_provenance,
            'Expanded corpus or provenance differs from authenticated sources')
    return corpus, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = export(args.output)
    print(json.dumps({'successful_labels': result['successful_labels'],
        'failed_attempts': result['failed_attempt_count'], 'workload_groups': len(result['independent_workload_groups']),
        'total_candidate_attempt_wall_seconds': result['total_candidate_attempt_wall_seconds']}))


if __name__ == '__main__':
    main()
