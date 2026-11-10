#!/usr/bin/env python3
"""Standard-library-only replay of the fixed selection stability experiment."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from replay_feature_comparison import metrics, equal

VIEWS = ('mapping217', 'original336', 'selected128')
SEEDS = (2026101401, 2026110901, 2026110902)
CAPS = (32, 64, 128)


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mean(values): return sum(values) / len(values)


def selection_stability(selections):
    pairs = []
    for a, b in itertools.combinations(selections, 2):
        x, y = set(a['selected_indices']), set(b['selected_indices'])
        pairs.append({'seed_a': a['seed'], 'fold_a': a['fold'],
                      'seed_b': b['seed'], 'fold_b': b['fold'],
                      'intersection_count': len(x & y), 'union_count': len(x | y),
                      'jaccard': len(x & y) / len(x | y)})
    def report(items):
        values = [r['jaccard'] for r in items]
        return {'pair_count': len(values), 'mean_jaccard': mean(values),
                'minimum_jaccard': min(values), 'maximum_jaccard': max(values)}
    counts = Counter(i for s in selections for i in s['selected_indices'])
    return {'all_pairs': report(pairs),
            'within_seed_across_folds': {str(seed): report([r for r in pairs if r['seed_a'] == r['seed_b'] == seed]) for seed in SEEDS},
            'across_seeds_same_fold': report([r for r in pairs if r['seed_a'] != r['seed_b'] and r['fold_a'] == r['fold_b']]),
            'across_seeds_all_folds': report([r for r in pairs if r['seed_a'] != r['seed_b']]),
            'always_selected_count': sum(n == len(selections) for n in counts.values()),
            'distinct_selected_count': len(counts),
            'column_selection_counts': [{'source_index': i, 'selected_count': counts[i]} for i in range(336)],
            'pairs': pairs}


def eligibility(per_seed):
    """Predeclared descriptive gate; seeds are algorithmic repeats, not new data."""
    lower_each = all(per_seed[str(s)]['selected128']['group_macro_mae_lut4'] <
                     per_seed[str(s)]['mapping217']['group_macro_mae_lut4'] for s in SEEDS)
    aggregates = {}
    for view in VIEWS:
        aggregates[view] = {
            'mean_seed_group_macro_mae_lut4': mean([per_seed[str(s)][view]['group_macro_mae_lut4'] for s in SEEDS]),
            'maximum_underprediction_lut4': max(per_seed[str(s)][view]['maximum_underprediction_lut4'] for s in SEEDS),
            'caps': {str(cap): {field: sum(per_seed[str(s)][view]['caps'][str(cap)][field] for s in SEEDS)
                               for field in ('false_safe_count', 'false_rejection_count')} for cap in CAPS}}
    candidate, base = aggregates['selected128'], aggregates['mapping217']
    caps_ok = {str(cap): {field: candidate['caps'][str(cap)][field] <= base['caps'][str(cap)][field]
                         for field in ('false_safe_count', 'false_rejection_count')} for cap in CAPS}
    under_ok = candidate['maximum_underprediction_lut4'] <= base['maximum_underprediction_lut4']
    return {'mean_error_promising': lower_each,
            'primary_mae_strictly_lower_each_seed': lower_each,
            'aggregate_budget_errors_not_worse': caps_ok,
            'maximum_underprediction_not_worse': under_ok,
            'strictly_eligible': lower_each and under_ok and all(all(v.values()) for v in caps_ok.values()),
            'descriptive_aggregates_not_independent_samples': aggregates}


def summaries(rows):
    per_seed = {}
    for seed in SEEDS:
        selected = [r for r in rows if r['seed'] == seed]
        per_seed[str(seed)] = {}
        for view in VIEWS:
            result = metrics(selected, view)
            result['by_fold'] = [metrics([r for r in selected if r['validation_fold'] == fold], view) for fold in range(5)]
            per_seed[str(seed)][view] = result
    return per_seed


def replay(output):
    output = Path(output)
    manifest, protocol = read(output/'manifest.json'), read(output/'protocol.json')
    for name, digest in manifest['files_sha256'].items(): assert sha(output/name) == digest, name
    for name, digest in protocol['input_sha256'].items(): assert sha(output/name) == digest, name
    for name, digest in protocol['runner_source_sha256'].items(): assert sha(ROOT/name) == digest, name
    assert protocol['maximum_new_fits'] == 33 and protocol['new_seeds'] == list(SEEDS[1:])
    assert protocol['original_seed'] == SEEDS[0] and protocol['new_synthesis'] == 0
    summary, rows = read(output/'summary.json'), read(output/'predictions.json')
    assert summary['fits_completed'] == 33 and summary['cv_fits_completed'] == 30
    assert summary['total_wall_seconds'] <= 600
    assert summary['protocol_sha256'] == sha(output/'protocol.json')
    assert read(output/'run-start.json')['protocol_sha256'] == sha(output/'protocol.json')
    folds = read(output/'folds.json'); original = read(output/'original-seed/predictions.json')
    assert len(rows) == 1665*3 and len(folds) == len(original) == 1665
    for seed in SEEDS:
        replicate = [r for r in rows if r['seed'] == seed]
        assert len(replicate) == 1665
        for i, (row, fold) in enumerate(zip(replicate, folds)):
            assert row['row_index'] == fold['row_index'] == i
            assert row['group'] == fold['group'] and row['validation_fold'] == fold['validation_fold']
            assert row['actual_lut4'] == original[i]['actual_lut4']
            assert row['original_zero_override'] == original[i]['original_zero_override']
            if row['original_zero_override']: assert all(row['predicted_lut4'][v] == 0 for v in VIEWS)
            if seed == SEEDS[0]: assert {k:v for k,v in row.items() if k!='seed'} == original[i]
    assert len({r['group'] for r in folds}) == 522
    for group in {r['group'] for r in folds}: assert len({r['validation_fold'] for r in folds if r['group']==group}) == 1
    selections, columns = read(output/'selected-columns.json'), read(output/'columns.json')
    assert len(selections) == 15
    assert {(r['seed'], r['fold']) for r in selections} == set(itertools.product(SEEDS, range(5)))
    for entry in selections:
        importance = entry['full336_training_importances']
        chosen = sorted(sorted(range(336), key=lambda i:(-importance[i], i))[:128])
        assert entry['selected_indices'] == chosen
        assert entry['selected_columns'] == [columns[i] for i in chosen]
        assert entry['training_rows'] == [i for i, r in enumerate(folds) if r['validation_fold'] != entry['fold']]
    equal(selection_stability(selections), summary['selection_stability'])
    per_seed = summaries(rows)
    equal(per_seed, summary['per_seed'])
    equal(eligibility(per_seed), summary['eligibility'])
    timings = read(output/'timings.json')
    assert len(timings) == 33 and [r['fit_index'] for r in timings] == list(range(1,34))
    assert {(r['seed'],r['fold'],r['view']) for r in timings if r['stage']=='cross_validation'} == set(itertools.product(SEEDS[1:], range(5), VIEWS))
    assert {(r['seed'],r['view']) for r in timings if r['stage']=='full_data'} == {(SEEDS[0],v) for v in VIEWS}
    selection = read(output/'models/full-data-selection.json')
    chosen = sorted(sorted(range(336),key=lambda i:(-selection['full336_training_importances'][i],i))[:128])
    assert selection['selected_indices'] == chosen
    for view in VIEWS:
        metadata = read(output/'models'/f'{view}.json')
        assert metadata['experimental_only'] is True and metadata['point_only'] is True
        assert metadata['artifact_sha256'] == sha(output/'models'/f'{view}.joblib')
        assert metadata['source_columns'] == columns and metadata['training_row_count'] == 1665
        assert metadata['protocol_sha256'] == sha(output/'protocol.json')
        indices = list(range(217)) if view=='mapping217' else list(range(336)) if view=='original336' else chosen
        assert metadata['selected_indices'] == indices
        assert metadata['selected_columns'] == [columns[i] for i in indices]
    print(json.dumps({'status':'pass','rows_per_seed':1665,'groups':522,'descriptive_seed_replicates':3,
                      'verified_new_fits':33,'new_fits':0,'strictly_eligible':summary['eligibility']['strictly_eligible']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/selection-stability')
    replay(parser.parse_args().output)
