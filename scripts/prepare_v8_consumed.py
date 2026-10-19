#!/usr/bin/env python3
"""Build the complete consumed-input novelty registry without reading labels."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from train_v6 import read, sha, write, now, record
from isaforge import area_model_v6 as v6
from isaforge import area_model_v8 as v8
from isaforge.features import parse_formula
from isaforge.v8_application_corpus import append_rewritten


def run(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a new registry path; retain all prior attempts')
    old = ROOT / 'results/2026-10-14-v6'
    freeze_path = old / 'point-freeze.json'
    freeze = read(freeze_path)
    bindings = {(old / r['path']).resolve(): r['sha256'] for r in freeze['files']}
    helper = ROOT / 'scripts/train_v6.py'
    if bindings.get(helper) != sha(helper):
        raise ValueError('Imported frozen V6 utility source changed')
    seal_path = old / 'corpus/input-seal.json'
    if bindings.get(seal_path) != sha(seal_path):
        raise ValueError('V6 input seal not bound to prediction freeze')
    seal = read(seal_path)
    paths = [old / 'corpus/consumed-features.json']
    paths.extend(old / 'corpus' / name for name in seal['attempt_files_sha256'] if name.endswith('-features.json'))
    if len(paths) != 3:
        raise ValueError('One consumed and two final V6 cohort input manifests required')
    registry = {}
    counts = {}
    for path in paths:
        expected = (seal['consumed_features_sha256'] if path.name == 'consumed-features.json'
                    else seal['attempt_files_sha256'][str(path.relative_to(old / 'corpus'))])
        if sha(path) != expected or bindings.get(path) != expected:
            raise ValueError('Consumed feature source differs from original V6 freeze')
        data = read(path)
        if tuple(data['columns']) != v6.columns():
            raise ValueError('Exact full336 input schema required')
        counts[str(path.relative_to(ROOT))] = len(data['records'])
        for row in data['records']:
            formula = parse_formula(row['formula']).canonical()
            if formula in registry and (registry[formula]['values'] != row['values']
                    or registry[formula]['normalized_formula'] != row['normalized_formula']):
                raise ValueError('Conflicting consumed input features')
            registry[formula] = {**row, 'formula': formula}
    if len(registry) != 2764:
        raise ValueError('Recomputed complete consumed unique count differs from planned2764')
    sources = v8.source_hashes()
    corpus_helper = ROOT / 'isaforge/v8_application_corpus.py'
    bindings_out = [record(path, output) for path in [freeze_path, seal_path, *paths, Path(__file__), helper, corpus_helper,
                    *(ROOT / 'isaforge' / n for n in sources)]]
    write(output / 'start.json', {'started_at_utc': now(), 'schema': 'isaforge-v8-consumed-start-v1',
          'source_counts': counts, 'unique_formulas': len(registry), 'files': bindings_out,
          'environment': v8.environment(), 'runtime_source_sha256': sources,
          'labels_read': False, 'model_predictions_read': False})
    records = []
    for i, formula in enumerate(sorted(registry)):
        records.append(append_rewritten(registry[formula]))
        if (i + 1) % 100 == 0:
            print(f'Consumed input identities {i+1}/{len(registry)}', flush=True)
    if v8.source_hashes() != sources or any(sha(output / r['path']) != r['sha256'] for r in bindings_out):
        raise ValueError('Source/input changed during registry preparation')
    write(output / 'features.json', {'columns': list(v8.columns()), 'records': records})
    write(output / 'completion.json', {'schema': 'isaforge-v8-consumed-completion-v1', 'completed_at_utc': now(),
          'start': record(output / 'start.json', output), 'features': record(output / 'features.json', output),
          'formulas': len(records), 'labels_read': False, 'model_predictions_read': False})
    print('Complete consumed registry:', len(records), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
