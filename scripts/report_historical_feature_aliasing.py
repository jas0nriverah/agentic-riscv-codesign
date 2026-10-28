#!/usr/bin/env python3
"""Audit historical feature aliasing without fitting or changing a selector.

Only the pinned, consumed 122-row historical corpus is read. Ordered AST paths
are a proposed representation diagnostic, not a trained or promoted model.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge.budgeted_selection import STRUCTURAL_COLUMNS
from isaforge.features import FEATURE_COLUMNS, parse_formula

CORPUS = 'results/2026-10-26-lift-selection-corpus'
CORPUS_MANIFEST_SHA256 = '219806a8a9c569f783ecbbe82561f2c3199dcb1faa83054710141fdfef0930c8'
CORPUS_SHA256 = '901413111da94933a1c14f0e758c1cf96f959bde44325e79ded6e47c4b8743ef'
OUTPUT = 'reports/2026-10-28-historical-feature-aliasing-r1'
AREA_CAP = 64
CLOCK_MHZ = 12.0
SOURCES = ('scripts/report_historical_feature_aliasing.py',
           'isaforge/features.py', 'isaforge/budgeted_selection.py')


def require(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def authenticate(root, expected_manifest):
    root = Path(root).resolve()
    require(sha(root / 'manifest.json') == expected_manifest,
            'Pinned historical manifest changed')
    require((root / 'manifest.json.sha256').read_text().strip() == expected_manifest,
            'Historical manifest sidecar differs')
    inventory = json.loads((root / 'manifest.json').read_text())
    require(isinstance(inventory, dict) and inventory, 'Nonempty inventory required')
    for name, expected in inventory.items():
        member = (root / name).resolve()
        require(member.is_relative_to(root) and member.is_file(),
                'Invalid historical manifest member: ' + name)
        require(sha(member) == expected, 'Historical member hash mismatch: ' + name)
    return inventory


def numeric_vector(row, columns):
    """Outcome-free public numeric allowlist; no label participates in keys."""
    values = []
    for column in columns:
        value = row[column]
        require(not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value), 'Invalid numeric feature: ' + column)
        values.append(float(value))
    return values


def ordered_ast_paths(formula):
    """Preserve root, full child path, operand position, input role and literal.

    This exact-tree diagnostic can expose omitted information. It is not a
    learned embedding or a recommended high-dimensional categorical feature.
    Operator tokens, paths and literals are obtained solely from public syntax.
    """
    result = []

    def visit(node, path, parent, operand):
        kind = 'operator' if node.children else (
            'constant' if isinstance(node.value, int) else 'input')
        result.append(dict(path=list(path), parent_operator=parent,
            operand_position=operand, kind=kind, value=node.value))
        for position, child in enumerate(node.children):
            visit(child, (*path, position), str(node.value), position)

    visit(parse_formula(formula), (), None, None)
    return result


def feasible(row):
    require(row.get('status', 'success') == 'success' and
            row.get('correctness_verified') is True and
            isinstance(row.get('device_fits'), bool),
            'Only known, verified historical outcomes may be scored')
    require(all(not isinstance(row[key], bool) and
                isinstance(row[key], (int, float)) and math.isfinite(row[key])
                for key in ('area_delta_lut4', 'routed_fmax_min_mhz')),
            'Known finite hardware outcomes required')
    return (row['device_fits'] and row['area_delta_lut4'] <= AREA_CAP and
            row['routed_fmax_min_mhz'] >= CLOCK_MHZ)


def compare(rows):
    """Group before reading outcomes, then score only within each fixed key."""
    key_functions = {
        'ranker_numeric': lambda row: numeric_vector(row, FEATURE_COLUMNS),
        'feasibility_structural_numeric': lambda row: numeric_vector(row, STRUCTURAL_COLUMNS),
        'proposed_structural_plus_ordered_ast': lambda row: dict(
            numeric=numeric_vector(row, STRUCTURAL_COLUMNS),
            paths=ordered_ast_paths(row['formula'])),
    }
    descriptors = {}
    ordered = sorted(rows, key=lambda row: row['candidate_id'])
    require(len({row['candidate_id'] for row in ordered}) == len(ordered),
            'Unique historical candidate IDs required')
    for name, key_function in key_functions.items():
        groups = defaultdict(list)
        keys = {}
        for row in ordered:
            key = key_function(row)
            key_sha = digest(key)
            require(key_sha not in keys or keys[key_sha] == key, 'Descriptor hash collision')
            keys[key_sha] = key
            groups[key_sha].append(row)
        mixed, errors, pairs = [], 0, 0
        for key_sha, members in sorted(groups.items()):
            labels = [bool(feasible(row)) for row in members]
            if len(set(labels)) < 2:
                continue
            yes, no = sum(labels), len(labels) - sum(labels)
            errors += min(yes, no)
            pairs += yes * no
            mixed.append(dict(descriptor_sha256=key_sha,
                descriptor=keys[key_sha], feasible_rows=yes, infeasible_rows=no,
                rows=[dict(candidate_id=row['candidate_id'],
                    workload_group=row['workload_group'], formula=row['formula'],
                    area_delta_lut4=row['area_delta_lut4'],
                    routed_fmax_min_mhz=row['routed_fmax_min_mhz'],
                    feasible=label, record_sha256=digest(row))
                    for row, label in zip(members, labels)]))
        descriptors[name] = dict(unique_vectors=len(groups),
            repeated_vector_groups=sum(len(members) > 1 for members in groups.values()),
            mixed_feasibility_groups=len(mixed),
            mixed_feasibility_rows=sum(len(group['rows']) for group in mixed),
            opposite_label_pairs=pairs,
            minimum_in_sample_classification_errors_from_aliasing=errors,
            mixed_groups=mixed)
    return descriptors


def analyze(root=ROOT):
    root = Path(root).resolve()
    corpus_root = root / CORPUS
    inventory = authenticate(corpus_root, CORPUS_MANIFEST_SHA256)
    require(inventory.get('corpus.json') == CORPUS_SHA256 and
            sha(corpus_root / 'corpus.json') == CORPUS_SHA256,
            'Pinned historical corpus changed')
    corpus = json.loads((corpus_root / 'corpus.json').read_text())
    rows = corpus.get('rows', [])
    require(corpus.get('schema') == 'isaforge-consumed-guarded-corpus-v1' and
            len(rows) == corpus.get('successful_labels') == 122 and
            corpus.get('total_candidate_attempts') == 126 and
            len(corpus.get('failed_attempts', [])) == 4 and
            len({row['workload_group'] for row in rows}) == 14,
            'Expected 122 historical successes, four failures and 14 groups')
    return dict(schema='isaforge-historical-feature-aliasing-diagnostic-v1',
        scope='Retrospective consumed historical data; no fitting, tuning, selector change or target outcomes',
        source=dict(corpus=CORPUS + '/corpus.json',
            corpus_sha256=CORPUS_SHA256, manifest_sha256=CORPUS_MANIFEST_SHA256,
            authenticated_members=len(inventory)),
        sources_sha256={name: sha(root / name) for name in SOURCES},
        successful_historical_rows=len(rows), historical_workload_groups=14,
        charged_failures_excluded_from_labels=4,
        area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
        numeric_columns=dict(ranker=list(FEATURE_COLUMNS),
                             feasibility=list(STRUCTURAL_COLUMNS)),
        descriptor_contract=dict(
            inputs='Only numeric public feature allowlists and parsed public formula syntax',
            proposal='Current structural numeric vector plus ordered AST paths with root, parent, operand position, input role and exact immediate',
            budget_feature='The fixed cap-relative proxy is constant for identical tree-op counts within a fit; appending it cannot separate identical structural vectors.',
            status='Proposed challenger only; exact-tree identity does not establish generalization or a suitable trainable feature set'),
        descriptors=compare(rows),
        interpretation=[
            'Opposite historical labels under the same feature vector demonstrate information omitted by that representation.',
            'The in-sample error bound concerns deterministic classifiers on these exact rows; it is not irreducible test error or an uncertainty interval.',
            'Ordered paths can separate syntax but do not prove better predictions, calibration, selection, timing learning or transfer.',
            'Candidate rows are correlated within 14 consumed workloads; no statistical superiority or independent generalization is claimed.',
            'Next: preregister a compact outcome-independent structural feature challenger and evaluate whole-workload/family holdouts before any prospective promotion.'])


def readme(summary):
    descriptions = {
        'ranker_numeric': 'Current ranker numeric features (including profile counts)',
        'feasibility_structural_numeric': 'Current hardware-feasibility structural features',
        'proposed_structural_plus_ordered_ast': 'Proposed structural features + ordered AST paths',
    }
    lines = ['# Historical feature-aliasing diagnostic', '',
        'This report authenticates the consumed **122-success / 14-workload** historical corpus. '
        'Four charged failures are excluded from this numeric hardware-label diagnostic. '
        'It fits no model, tunes no threshold and reads no tiny-regex target outcomes.', '',
        'The diagnostic asks whether different measured +64-LUT4 / 12-MHz feasibility outcomes '
        'share exactly the same input representation. All representation keys are computed '
        'from public features and syntax before their labels are scored.', '',
        '| Representation | Unique vectors | Mixed-label groups | Rows in mixed groups | Opposite-label pairs |',
        '|---|---:|---:|---:|---:|']
    for name in descriptions:
        value = summary['descriptors'][name]
        lines.append(f"| {descriptions[name]} | {value['unique_vectors']} | {value['mixed_feasibility_groups']} | {value['mixed_feasibility_rows']} | {value['opposite_label_pairs']} |")
    lines += ['', '## Demonstrated limitation', '']
    for group in summary['descriptors']['feasibility_structural_numeric']['mixed_groups']:
        lines.append('These historical rows share one structural numeric vector:')
        lines.append('')
        for row in group['rows']:
            label = 'feasible' if row['feasible'] else 'infeasible'
            lines.append(f"- `{row['formula']}` — {row['workload_group']}, +{row['area_delta_lut4']} LUT4, {label}.")
        lines.append('')
    lines += ['The feature vector records operation counts, depth and aggregate constants, '
        'but omits parent/child ordering and operand placement. At a fixed area cap, the '
        'existing cap-relative proxy also cannot distinguish identical vectors. The proposed '
        'descriptor preserves full ordered AST paths, input roles and exact constants using '
        'public syntax alone. It is a representation diagnostic, not a trained embedding or '
        'a recommendation to memorize full formulas.', '', '## Decision and limits', '',
        'This supports testing compact operator-order and operand-position features. '
        'It does **not** justify promoting a new selector or changing the frozen model. '
        'Separating syntax does not establish prediction or selection improvements. '
        'Any feature challenger needs a separately frozen, grouped workload/family evaluation; '
        'results on this already-consumed corpus remain development evidence.', '',
        'The collision-based in-sample classification-error lower bound applies only to '
        'deterministic classification of these exact feature vectors. It is not an '
        'irreducible generalization error estimate. The ranker includes dynamic profile '
        'counts; absence of full-vector collisions there does not make those profile '
        'counts a hardware-cost representation or demonstrate a selection win.', '',
        '```sh', '../work/audit-venv/bin/python scripts/report_historical_feature_aliasing.py',
        '../work/audit-venv/bin/python scripts/report_historical_feature_aliasing.py --verify reports/2026-10-28-historical-feature-aliasing-r1',
        '```', '', 'Every input and output is hash-bound in `diagnostic.json` and `manifest.json`. '
        'No native jobs, LLM calls, training fits or candidate measurements are performed.', '']
    return '\n'.join(lines).encode()


def artifacts(summary):
    content = {'diagnostic.json': encoded(summary), 'README.md': readme(summary)}
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in content.items()}
    content['manifest.json'] = encoded(manifest)
    content['manifest.json.sha256'] = (hashlib.sha256(content['manifest.json']).hexdigest() + '\n').encode()
    return content


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    summary = analyze()
    content = artifacts(summary)
    destination = (args.verify or args.output or ROOT / OUTPUT).resolve()
    require(not destination.is_relative_to((ROOT / 'results').resolve()),
            'Output cannot overwrite sealed source evidence')
    if args.verify:
        require(destination.is_dir() and {p.name for p in destination.iterdir()} == set(content),
                'Output inventory differs')
        for name, value in content.items():
            require((destination / name).read_bytes() == value,
                    'Exact diagnostic reproduction mismatch: ' + name)
        print('Verified pinned historical corpus and exact feature-aliasing outputs.')
    else:
        require(not destination.exists(), 'Use a fresh output directory')
        destination.mkdir(parents=True)
        for name, value in content.items():
            (destination / name).write_bytes(value)
        print('Wrote historical feature-aliasing diagnostic to ' + str(destination))


if __name__ == '__main__':
    main()
