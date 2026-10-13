"""Refit the chosen structural model on all measurements after evaluation.

This artifact is for future inference. Its fitting scores must never replace
the frozen-model prospective test results.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .area_model_v2 import train_resource_model, save_model, load_area_model_v2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    rows = [row for path in args.rows for row in json.loads(path.read_text())]
    model = train_resource_model(rows)
    metadata = {'target': 'isolated iCE40 mapped SB_LUT4 count',
                'measurement_source': 'rtl_synthesis', 'training_row_count': len(rows),
                'benchmark_names': sorted({r['benchmark'] for r in rows}),
                'input_dataset_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.rows},
                'selection_status': 'Deployment choice made after comparing frozen models on final test.',
                'evaluation_status': 'Refit on all available data. No independent test of this refitted artifact yet.',
                'reference_evaluation': 'Prospective scores refer to the separate frozen 301-formula model.'}
    paths = save_model(model, args.output, 'resource-deployment', metadata)
    inputs = [{k: r[k] for k in ('benchmark', 'candidate_id', 'formula')} for r in rows]
    assert load_area_model_v2(paths['model_path']).predict(inputs) == model.predict(inputs)
    print(json.dumps({'training_rows': len(rows), 'training_formulas': model.training_formula_count, **paths}, indent=2))


if __name__ == '__main__':
    main()
