#!/usr/bin/env python3
"""Present the fixed coverage fit, or render a marked synthetic layout only.

No model loading, inference, fitting, feature extraction, or metric recomputation.
Real figures require completed coverage scoring and its frozen point evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
COLORS = {'frozen': '#65717D', 'augmented': '#126B9B'}
CONSTANT_LABELS = {
    'add(mul(in0,addi(0,54)),in1)': '54x + y',
    'mul(in0,addi(0,2025))': '2025x',
    'mul(in0,addi(0,54))': '54x',
    'mul(in0,addi(lui(4096),-640))': '3456x',
    'mul(sub(andi(in0,63),in1),addi(0,54))': '54((x & 63) − y)',
    'mul(sub(in0,in1),addi(0,54))': '54(x − y)',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def actual_data(root, fit):
    root, fit = Path(root).resolve(), Path(fit).resolve()
    evaluation_path, freeze_path = fit/'evaluation.json', fit/'point-freeze.json'
    evaluation, freeze = read(evaluation_path), read(freeze_path)
    preparation_path = root/'preparation.json'
    preparation = read(preparation_path)
    recipe_path = (root/preparation['recipe']['path']).resolve()
    recipe = read(recipe_path)
    start_path, attempt_path = fit/'training-start.json', fit/'fit-attempt.json'
    start, attempt = read(start_path), read(attempt_path)
    if (evaluation.get('schema') != 'isaforge-v9-coverage-development-evaluation-v1'
            or evaluation.get('scope') != 'consumed-development-only'
            or freeze.get('new_fits') != 1 or freeze.get('training_rows') != 1713
            or freeze.get('all_application_fields_roundtrip_exact') is not True
            or freeze.get('evaluation_target_files_opened') is not False
            or start.get('original_training_formulas') != 1665 or start.get('new_training_formulas') != 48
            or start.get('maximum_fits') != 1 or attempt.get('rows') != 1713
            or len(attempt.get('selected_columns', [])) != 217
            or start.get('configuration') != recipe['fixed_parameters']
            or start['configuration'].get('n_estimators') != 300):
        raise ValueError('Complete fixed one-fit 1665+48/mapping217/ET300 evidence required')
    if (evaluation['point_freeze_sha256'] != sha(freeze_path)
            or freeze['preparation_sha256'] != sha(preparation_path)
            or preparation['recipe']['sha256'] != sha(recipe_path)):
        raise ValueError('Evaluation/freeze/preparation/recipe identity differs')
    if datetime.fromisoformat(evaluation['evaluated_at_utc']) < datetime.fromisoformat(freeze['frozen_at_utc']):
        raise ValueError('Scoring must follow the saved point freeze')
    predictions_path = fit/'point-predictions.json'
    artifact, schema = fit/'models/mapping-coverage.joblib', fit/'models/mapping-coverage.json'
    for path, key in ((predictions_path, 'predictions_sha256'), (artifact, 'artifact_sha256'), (schema, 'schema_sha256')):
        if sha(path) != freeze[key]:
            raise ValueError('Frozen fit output differs: '+str(path))
    label_entry = recipe['evaluation']['v8']['labels']
    labels_path = ROOT/label_entry['path']
    if sha(labels_path) != label_entry['sha256']:
        raise ValueError('Consumed V8 target digest differs')
    labels = {r['formula']: r['lut4_count'] for r in read(labels_path)}
    point_sets = read(predictions_path)['applications']
    if set(point_sets) != {'frozen', 'augmented'}:
        raise ValueError('Two complete application point sets required')
    application_root = ROOT/recipe['evaluation']['v8']['root']
    rows_path, programs_path = application_root/'rows.json', application_root/'programs.json'
    rows, programs = read(rows_path), read(programs_path)
    if len(rows) != 152 or any(len(points) != 152 for points in point_sets.values()):
        raise ValueError('Complete152 application rows required')
    primary = evaluation['primary']
    families = sorted(p['family'] for p in programs if p['primary_family'])
    families = sorted(set(families))
    if len(families) != 4 or set(primary['primary_family_mae_lut4']) != set(families):
        raise ValueError('Complete four-family macro required')
    family_rows = [{'family': family, **primary['primary_family_mae_lut4'][family],
                    'difference': primary['paired_family_differences_lut4'][family],
                    'rows': sum(r['family'] == family and r['primary_family'] for r in rows)} for family in families]
    constants = primary['diagnosed_subsets']['constant_multiply_six']['formulas']
    if len(constants) != len(set(constants)) or len(constants) != 6:
        raise ValueError('All six fixed diagnosed constant-multiply formulas required')
    constant_rows = []
    for formula in sorted(constants):
        row = {'formula': formula, 'case_id': hashlib.sha256(formula.encode()).hexdigest()[:6],
               'display_formula': CONSTANT_LABELS[formula],
               'actual_lut4': labels[formula]}
        for model, points in point_sets.items():
            candidates = [p['predicted_lut4'] for p in points if p['formula'] == formula]
            if not candidates or len(set(candidates)) != 1:
                raise ValueError('Complete consistent constant-multiply points required')
            row[model] = candidates[0]
            row[model+'_absolute_error'] = abs(candidates[0]-labels[formula])
        constant_rows.append(row)
    regression = evaluation['v6_test_regression']
    if set(regression) != {'frozen', 'augmented'} or any(m['count'] != 192 for m in regression.values()):
        raise ValueError('Complete192 V6 regression cases required')
    for metric in regression.values():
        if any(metric['caps'][str(cap)]['count'] != 192 for cap in (32, 64, 128)):
            raise ValueError('All regression cap denominators required')
    paths = [evaluation_path, freeze_path, preparation_path, recipe_path, start_path, attempt_path,
             predictions_path, artifact, schema, labels_path, rows_path, programs_path, Path(__file__).resolve()]
    # Public input files must still be authenticated by the sealed preparation.
    bound = {(root/e['path']).resolve(): e['sha256'] for e in preparation['files']}
    for path in (rows_path, programs_path):
        if bound.get(path.resolve()) != sha(path):
            raise ValueError('Prepared public cohort digest differs')
    return {'synthetic': False, 'family_rows': family_rows,
            'macro': primary['primary_family_macro_mae_lut4'],
            'macro_difference': primary['augmented_minus_frozen_mae_lut4'],
            'constant_rows': constant_rows, 'constant_metrics': primary['diagnosed_subsets']['constant_multiply_six']['scores'],
            'regression': regression, 'primary_rows': sum(r['primary_family'] for r in rows),
            'training_rows': 1713, 'new_paid_training_labels': 48, 'mapping_features': 217, 'trees': 300}, paths


def synthetic_data():
    """Values are deliberately invented and visibly marked; layout only."""
    families = [{'family': f'family {i+1}', 'frozen': old, 'augmented': new,
                 'difference': new-old, 'rows': 20+i} for i, (old, new) in enumerate(((4, 3), (2, 2.5), (1, .8), (8, 4)))]
    constants = [{'formula': f'synthetic_formula_{i}', 'case_id': f'CASE{i+1}', 'display_formula': f'Layout case {i+1}', 'actual_lut4': 50+10*i,
                  'frozen': 60+12*i, 'augmented': 51+11*i,
                  'frozen_absolute_error': 10+2*i, 'augmented_absolute_error': 1+i} for i in range(6)]
    metrics = {}
    for name, mae in (('frozen', 3.), ('augmented', 3.3)):
        metrics[name] = {'count': 192, 'mae_lut4': mae, 'signed_bias_lut4': .2,
            'rmsle': .08, 'positive_mape_percent': 7., 'positive_target_count': 150,
            'zero_target_count': 42, 'zero_mae_lut4': 0., 'p95_absolute_error_lut4': 9.,
            'p99_absolute_error_lut4': 20., 'worst_absolute_error_lut4': 50.,
            'maximum_underprediction_lut4': 30., 'underprediction_count': 90,
            'overprediction_count': 85, 'exact_prediction_count': 17,
            'caps': {str(c): {'false_accept_count': 2, 'false_reject_count': 3, 'count': 192} for c in (32, 64, 128)}}
    return {'synthetic': True, 'family_rows': families, 'macro': {'frozen': 3.75, 'augmented': 2.575},
            'macro_difference': -1.175, 'constant_rows': constants, 'regression': metrics,
            'primary_rows': 86, 'training_rows': 1713, 'new_paid_training_labels': 48, 'mapping_features': 217, 'trees': 300}, [Path(__file__).resolve()]


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 13,
        'axes.labelsize': 11, 'xtick.labelsize': 10, 'ytick.labelsize': 10.5,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.axisbelow': True,
        'figure.facecolor': 'white', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'svg.hashsalt': 'isaforge-v9-coverage'})
    fig = plt.figure(figsize=(16, 12.8))
    grid = fig.add_gridspec(2, 2, height_ratios=[.85, 1.25], wspace=.37, hspace=.43)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]
    fig.subplots_adjust(left=.12, right=.97, top=.82, bottom=.14)
    title = 'SYNTHETIC LAYOUT — NO EXPERIMENTAL RESULTS' if data['synthetic'] else 'V9: fixed training-coverage augmentation on consumed data'
    fig.suptitle(title, x=.035, ha='left', y=.98, fontsize=20,
                 color='#A13E31' if data['synthetic'] else '#1D2832')
    fig.text(.035, .935, '48 paid training labels + original 1,665 circuits → one fit on 1,713 rows · unchanged mapping217 features · ExtraTrees300', fontsize=12)
    fig.text(.035, .898, 'Consumed V8 application pools and V6 test regression · complete four-family comparison · no independent transfer claim', fontsize=11, color='#48515C')
    families = data['family_rows']
    labels = [f"{r['family']} (N={r['rows']})" for r in families]+['Equal-family mean']
    positions = np.arange(len(labels))
    ax = axes[0]
    for model, offset in (('frozen', -.18), ('augmented', .18)):
        values = [r[model] for r in families]+[data['macro'][model]]
        ax.barh(positions+offset, values, height=.32, color=COLORS[model], label='Frozen V6 mapping' if model == 'frozen' else 'Coverage augmented')
        for y, value in zip(positions+offset, values):
            ax.text(value, y, f' {value:.3f}', va='center', fontsize=9)
    ax.set_yticks(positions, labels);ax.invert_yaxis();ax.set_xlim(left=0)
    ax.set_xlim(right=max(max(r[m] for r in families) for m in COLORS)*1.22)
    ax.grid(axis='x', color='#E2E6EA', linewidth=.7)
    ax.set_title('A  Primary · complete V8 family MAE', loc='left', pad=14)
    ax.set_xlabel('Mean absolute error (LUT4) ↓')
    ax.legend(frameon=False, fontsize=9, loc='upper left', bbox_to_anchor=(0, -.19), ncol=2)
    ax = axes[1]
    differences = [r['difference'] for r in families]+[data['macro_difference']]
    ax.barh(positions, differences, height=.62,
            color=['#BA5F55' if d > 0 else '#73A6BD' for d in differences[:-1]]+[COLORS['augmented']])
    ax.set_yticks(positions, [r['family'] for r in families]+['Equal-family mean']);ax.invert_yaxis()
    lo, hi = min(0, min(differences)), max(0, max(differences));span = max(hi-lo, .01)
    ax.set_xlim(lo-.25*span, hi+.22*span);ax.axvline(0, color='#293640', linewidth=1)
    ax.grid(axis='x', color='#E2E6EA', linewidth=.7)
    for y, value in zip(positions, differences):
        ax.text(value+(.018*span if value >= 0 else -.018*span), y, f'{value:+.4f}',
                 va='center', ha='left' if value >= 0 else 'right', fontsize=10)
    ax.set_title('B  Primary · paired family differences', loc='left', pad=14)
    ax.set_xlabel('Augmented − frozen MAE (LUT4); negative favors augmentation')
    ax = axes[2]
    constants = data['constant_rows']
    for model, offset in (('frozen', -.18), ('augmented', .18)):
        values = [r[model+'_absolute_error'] for r in constants]
        ax.barh(np.arange(6)+offset, values, height=.32, color=COLORS[model], label='Frozen' if model == 'frozen' else 'Augmented')
        for y, value in zip(np.arange(6)+offset, values):
            ax.text(value, y, f' {value:.2f}', va='center', fontsize=9)
    ax.set_yticks(np.arange(6), [f"{r['display_formula']} · true {r['actual_lut4']}" for r in constants]);ax.invert_yaxis()
    ax.set_xlim(0, max(max(r[m+'_absolute_error'] for r in constants) for m in COLORS)*1.25 or 1)
    ax.grid(axis='x', color='#E2E6EA', linewidth=.7)
    ax.set_title('C  Secondary · all six diagnosed constant multiplications', loc='left', pad=14)
    ax.set_xlabel('Absolute error (LUT4) ↓')
    ax.text(0, -.11, 'Colors match panel A. x=in0, y=in1; wrapping u32 arithmetic.\nFull original formulas, hashes and points are in figure-data.json; all six cases shown.',
             transform=ax.transAxes, fontsize=9, color='#48515C', va='top')
    regression = data['regression']
    rows = []
    descriptors = [('MAE · LUT4', 'mae_lut4'), ('Signed bias · LUT4', 'signed_bias_lut4'),
        ('RMSLE', 'rmsle'), ('Positive MAPE · %', 'positive_mape_percent'),
        ('P95 absolute error · LUT4', 'p95_absolute_error_lut4'), ('P99 absolute error · LUT4', 'p99_absolute_error_lut4'),
        ('Worst absolute error · LUT4', 'worst_absolute_error_lut4'),
        ('Maximum underprediction · LUT4', 'maximum_underprediction_lut4'), ('Zero-target MAE · LUT4', 'zero_mae_lut4')]
    for label, key in descriptors:
        values = [regression[m][key] for m in COLORS]
        rows.append([label, *[f'{v:.4f}' if v is not None else 'undefined' for v in values]])
    for cap in (32, 64, 128):
        rows.append([f'Cap {cap} · false accept / reject', *[
            f"{regression[m]['caps'][str(cap)]['false_accept_count']} / {regression[m]['caps'][str(cap)]['false_reject_count']}" for m in COLORS]])
    for label, key in (('Count · positive / zero', None), ('Under / over / exact', 'counts')):
        rows.append([label, *[(f"{regression[m]['positive_target_count']} / {regression[m]['zero_target_count']}" if key is None else
            f"{regression[m]['underprediction_count']} / {regression[m]['overprediction_count']} / {regression[m]['exact_prediction_count']}") for m in COLORS]])
    ax = axes[3];ax.axis('off')
    table = ax.table(cellText=rows, colLabels=['Metric · all 192 cases', 'Frozen', 'Augmented'],
                     colWidths=[.58, .21, .21], cellLoc='center', bbox=[-.035, .01, 1.035, .98])
    table.auto_set_font_size(False);table.set_fontsize(9.8)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor('#D9E0E5')
        if row == 0:
            cell.set_facecolor('#E7EEF3');cell.set_text_props(weight='bold')
        elif row % 2 == 0:
            cell.set_facecolor('#F6F8FA')
        if row > 0 and column == 0:
            cell.set_text_props(ha='left')
    ax.set_title('D  Secondary · complete consumed V6 test regression', loc='left', pad=14)
    fig.text(.035, .045, 'One fixed seed and one fit; all 48 coverage targets retained. Four-family descriptive development, no population confidence interval.\n'
             'LUT4 prediction error is not ASIC physical area, instruction-selection quality, CPU speedup, timing or energy.', fontsize=10, color='#48515C', va='bottom')
    paths = []
    for extension in ('png', 'svg', 'pdf'):
        path = output/('v9-fixed-training-coverage.'+extension)
        fig.savefig(path, dpi=220, bbox_inches='tight', pad_inches=.18,
                    metadata={'CreationDate': None, 'ModDate': None} if extension == 'pdf' else None)
        paths.append(path)
    plt.close(fig)
    return paths, matplotlib.__version__


def run(root, fit, output, *, synthetic=False):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Figure output is immutable; use a fresh path')
    data, paths = synthetic_data() if synthetic else actual_data(root, fit)
    before = {str(path): sha(path) for path in paths}
    output.mkdir(parents=True)
    artifacts, matplotlib_version = render(data, output)
    data_path = output/'figure-data.json';write(data_path, data)
    caption_path = output/'caption.md'
    caption = ('**Fixed coverage augmentation on consumed development cohorts.** '
        'Panels A–B show all four primary V8 source families and the equal-family MAE contrast for frozen versus augmented mapping predictors. '
        'Panel C retains all six predeclared constant-multiply cases, including worsened errors. '
        'Its short expressions use x=in0 and y=in1 with wrapping unsigned 32-bit (u32) arithmetic; '
        'full original formulas, SHA-256 prefixes, measured targets and both point predictions remain in figure-data.json. '
        'Panel D reports every consumed V6 test case and preserves the tail and cap-threshold tradeoffs. '
        'The augmentation costs 48 paid original-circuit labels and one fit on 1,713 rows, with unchanged mapping217 features and 300-tree ExtraTrees recipe. '
        'These are descriptive results after consuming V8 and V6 test outcomes, not independent transfer confirmation, calibrated uncertainty, or CPU-performance evidence.\n')
    with caption_path.open('x') as stream:
        stream.write(('SYNTHETIC LAYOUT ONLY — NO EXPERIMENTAL RESULTS.\n\n' if synthetic else '') + caption)
    if {str(path): sha(path) for path in paths} != before:
        raise ValueError('Presentation source/input changed during render')
    write(output/'figure-manifest.json', {'schema': 'isaforge-v9-coverage-presentation-v1',
        'synthetic_layout_only': synthetic, 'source_and_input_sha256': before,
        'output_sha256': {path.name: sha(path) for path in [*artifacts, data_path, caption_path]},
        'matplotlib': matplotlib_version, 'python': sys.executable,
        'new_fits': 0, 'new_measurements': 0, 'forecasts_recomputed': False,
        'scope': 'Consumed V8+V6-test development only;48 paid training labels, one1713-row fit, unchanged mapping217/ET300.'})
    print(f'Wrote {"SYNTHETIC LAYOUT ONLY" if synthetic else "completed coverage result"} figures at {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Sealed coverage preparation root')
    parser.add_argument('--fit', type=Path, help='Completed fit/scoring output')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--synthetic-layout', action='store_true')
    args = parser.parse_args()
    if not args.synthetic_layout and (args.root is None or args.fit is None):
        parser.error('Real figures require --root and --fit; synthetic layout uses --synthetic-layout')
    run(args.root, args.fit, args.output, synthetic=args.synthetic_layout)
