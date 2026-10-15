#!/usr/bin/env python3
"""Extract complete admitted application inputs before prediction/target release.

This creates prepared inputs, not an experimental freeze. Independent runtime
replay, final protocol/source binding and parent review precede the input seal.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from train_v6 import read, sha, write, now, record, checked
from isaforge import area_model_v8 as v8
from isaforge.v8_application_corpus import application_rows, novelty_ledger


def referenced_files(value):
    """Enumerate explicit file records in the preflight, including failed attempts."""
    result = []
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            path = (ROOT / value['path']).resolve()
            if sha(path) != value['sha256']:
                raise ValueError('Preflight evidence changed: ' + str(path))
            if 'bytes' in value and path.stat().st_size != value['bytes']:
                raise ValueError('Preflight evidence size changed')
            result.append(path)
        for child in value.values():
            result.extend(referenced_files(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(referenced_files(child))
    return result


def run(root, consumed_root, cache_root, workers):
    root, consumed_root, cache_root = map(lambda p: Path(p).resolve(), (root, consumed_root, cache_root))
    if root.exists():
        raise ValueError('Use a new application preparation directory; preserve all attempts')
    preflight_path = ROOT / 'benchmarks/application-v8/cohort-preflight.json'
    preflight = read(preflight_path)
    paths = [preflight_path, *referenced_files(preflight)]
    for group in ('runtime_dependencies', 'evidence_files'):
        for name, digest in preflight[group].items():
            path = ROOT / name
            if sha(path) != digest:
                raise ValueError('Preflight source/evidence changed: ' + name)
            paths.append(path)
    expected = {'bitcount': 47, 'fft': 6, 'ndes': 47, 'h264_dec': 50, 'isqrt': 2}
    programs, pools = [], []
    for name in sorted(expected):
        p = preflight['programs'][name]
        if p['upstream_algorithm_or_input_changes'] or not p['O0_O2_output_identical']:
            raise ValueError('Admitted source/output contract differs')
        candidates = read(ROOT / p['all_roi_candidates']['path'])
        if len(candidates) != expected[name] or p['all_roi_count'] != len(candidates):
            raise ValueError('Complete admitted candidate pool differs')
        fusion = read(ROOT / p['fusion_all_roi']['path'])
        if fusion.get('passed') is not True or any(b['skipped_opaque_block_occurrences'] for b in fusion['benchmarks']):
            raise ValueError('Complete no-skip fusion verification required')
        spec = {'benchmark': name, 'family': p['family'], 'primary_family': p['role'] == 'primary',
                'traceTotalInstructions': p['trace_instruction_count']}
        programs.append(spec)
        pools.append((spec, candidates))
    rows = application_rows(pools)
    unique = [{'formula': f} for f in sorted({r['formula'] for r in rows})]
    if len(rows) != 152 or len(unique) != 146 or sum(r['primary_family'] for r in rows) != 150:
        raise ValueError('Declared full-pool application/physical coverage differs')
    complete_path = consumed_root / 'completion.json'
    complete = read(complete_path)
    start_path = checked(complete['start'], consumed_root)
    consumed_path = checked(complete['features'], consumed_root)
    consumed_start = read(start_path)
    for entry in consumed_start['files']:
        paths.append(checked(entry, consumed_root))
    consumed = read(consumed_path)
    if tuple(consumed['columns']) != v8.columns() or len(consumed['records']) != 2764:
        raise ValueError('Complete consumed full455 registry required')
    tool_path = ROOT / 'results/2026-10-14-v5/feature-extraction.json'
    tool_meta = read(tool_path)
    sources = v8.source_hashes()
    paths += [complete_path, start_path, consumed_path, tool_path, Path(__file__), ROOT / 'scripts/train_v6.py',
              ROOT / 'isaforge/v8_application_corpus.py', *(ROOT / 'isaforge' / n for n in sources)]
    bindings = [record(p, root) for p in dict.fromkeys(paths)]
    write(root / 'input-start.json', {'schema': 'isaforge-v8-application-preparation-v1', 'started_at_utc': now(),
          'files': bindings, 'environment': v8.environment(), 'runtime_source_sha256': sources,
          'programs': programs, 'application_rows': len(rows), 'unique_original_formulas': len(unique),
          'fresh_labels_read': False, 'model_predictions_read': False, 'status': 'preparing-not-sealed'})
    write(root / 'rows.json', rows)
    write(root / 'programs.json', programs)
    # The metadata comes from input-only extraction, not fitted models or labels.
    tool = tool_meta['frozen_tool'] if 'frozen_tool' in tool_meta else tool_meta['tool']
    _, records = v8.FeatureExtractor(cache_root, frozen_tool=tool).matrix(unique, workers=workers)
    write(root / 'features.json', {'columns': list(v8.columns()), 'records': records})
    write(root / 'novelty.json', novelty_ledger(consumed['records'], records))
    if v8.source_hashes() != sources:
        raise ValueError('Feature source changed during preparation')
    for entry in bindings:
        checked(entry, root)
    write(root / 'input-preparation.json', {'schema': 'isaforge-v8-application-prepared-v1',
          'prepared_at_utc': now(), 'status': 'prepared-inputs-only-not-sealed',
          'files': [*bindings, *(record(root / n, root) for n in
              ('input-start.json', 'rows.json', 'programs.json', 'features.json', 'novelty.json'))],
          'runtime_source_sha256': sources, 'frozen_tool': tool,
          'rows': record(root / 'rows.json', root), 'features': record(root / 'features.json', root),
          'programs': record(root / 'programs.json', root), 'novelty': record(root / 'novelty.json', root),
          'application_rows': len(rows), 'unique_original_formulas': len(unique),
          'fresh_labels_read': False, 'model_predictions_read': False})
    print('Prepared146 unique inputs and152 application memberships; no fits/predictions/labels.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'consumed-root', 'cache-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    args = parser.parse_args()
    run(args.root, args.consumed_root, args.cache_root, args.workers)
