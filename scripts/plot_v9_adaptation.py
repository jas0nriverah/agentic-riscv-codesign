#!/usr/bin/env python3
"""Plot the fixed consumed-V8 correction result without recomputing predictions."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ADAPTERS = ('frozen', 'global_residual', 'local_residual')
COLORS = {'frozen': '#5E6B78', 'global_residual': '#B85B5B', 'local_residual': '#126B9B'}
LABELS = {'frozen': 'Frozen V6 mapping', 'global_residual': 'Global residual · secondary',
          'local_residual': 'Local residual · primary'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Presentation directory is immutable; use a fresh path')
    evaluation_path = root / 'evaluation-attempt-0000/evaluation.json'
    completion_path = root / 'evaluation-attempt-0000/completion.json'
    prepared_path = root / 'prepared-attempt-0000/public-prepared.json'
    preparation_path = root / 'prepared-attempt-0000/preparation.json'
    evidence = read(evaluation_path)
    completion = read(completion_path)
    prepared = read(prepared_path)
    if (evidence.get('schema') != 'isaforge-v9-consumed-development-evaluation-v1'
            or completion.get('complete') is not True or evidence['protocol']['primary_budget'] != 3
            or evidence['protocol']['dynamic_acquisition'] is not False):
        raise ValueError('Completed fixed V9 development evaluation required')
    if sha(evaluation_path) != completion['evaluation_sha256']:
        raise ValueError('Completed evaluation digest differs')
    for path, key in ((prepared_path, 'public_payload_sha256'), (preparation_path, 'preparation_sha256')):
        if sha(path) != evidence['provenance'][key]:
            raise ValueError('Prepared input digest differs')
    inputs = [evaluation_path, completion_path, prepared_path, preparation_path, Path(__file__).resolve()]
    before = {str(path): sha(path) for path in inputs}
    primary = evidence['primary']
    if primary['complete_primary_family_count'] != primary['primary_family_count'] or primary['primary_family_count'] != 4:
        raise ValueError('Complete four-family endpoint required for this presentation')
    families = list(primary['paired_family_differences_lut4'])
    results = {(row['family'], row['budget']): row for row in evidence['family_results']}
    denominators = {}
    for episode in prepared['episodes']:
        family = episode['family']
        denominators[family] = {}
        for budget in (1, 3, 5):
            row = results[family, budget]
            metrics = [m['frozen'] for m in row['by_program_metrics'].values() if m['frozen'] is not None]
            denominators[family][str(budget)] = {
                'unqueried_rows': sum(m['count'] for m in metrics),
                'positive_targets': sum(m['positive_target_count'] for m in metrics),
                'zero_targets': sum(m['zero_target_count'] for m in metrics),
                'queries_charged': row['exclusion']['charged_unique_original_queries'],
                'missing_programs': row['exclusion']['missing_programs']}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.titlesize': 13, 'axes.labelsize': 11,
                         'xtick.labelsize': 10, 'ytick.labelsize': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.axisbelow': True, 'figure.facecolor': 'white',
                         'svg.fonttype': 'none', 'svg.hashsalt': 'isaforge-v9-adaptation', 'pdf.fonttype': 42})
    output.mkdir(parents=True)
    fig = plt.figure(figsize=(16.2, 10.2))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.25, .72], width_ratios=[1, 1.15], hspace=.50, wspace=.38)
    left, right, table_ax = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, :])
    fig.subplots_adjust(left=.14, right=.97, top=.80, bottom=.15)
    fig.suptitle('V9: paid residual correction on consumed application data', x=.035, y=.98, ha='left', fontsize=20)
    means = primary['family_macro_mae_lut4']
    delta = primary['local_minus_frozen_mae_lut4']
    fig.text(.035, .925, f'Primary · 3 queries/family: frozen {means["frozen"]:.6f} → local {means["local_residual"]:.6f} LUT4 MAE '
             f'({delta:+.6f}; {abs(delta)/means["frozen"]*100:.2f}% lower).', fontsize=12)
    fig.text(.035, .885, 'All three adapters use identical unqueried cases within each budget. Surviving cases change across budgets.',
             fontsize=11, color='#48515C')
    differences = [primary['paired_family_differences_lut4'][f] for f in families] + [delta]
    names = [f'{f}  (N={denominators[f]["3"]["unqueried_rows"]})' for f in families] + ['Equal-family mean']
    left.barh(range(5), differences, color=['#78A6BE']*4+[COLORS['local_residual']], height=.62)
    left.set_yticks(range(5), names)
    left.invert_yaxis()
    left.axvline(0, color='#27343F', linewidth=1)
    span = max(abs(min(differences)), abs(max(differences)), .01)
    left.set_xlim(min(0, min(differences))-.24*span, max(0, max(differences))+.22*span)
    left.grid(axis='x', color='#E2E6EA', linewidth=.7)
    for i, value in enumerate(differences):
        left.text(value-.018*span if value < 0 else .018*span, i, f'{value:+.4f}',
                   ha='right' if value < 0 else 'left', va='center', fontsize=11)
    left.set_title('A  Primary paired family differences · budget 3', loc='left', pad=16)
    left.set_xlabel('Local − frozen MAE (LUT4); negative favors local')
    positions = np.arange(3)
    for offset, adapter in zip((-.24, 0, .24), ADAPTERS):
        values = [evidence['by_budget'][str(b)]['family_macro_mae_lut4'][adapter] for b in (1, 3, 5)]
        right.bar(positions+offset, values, width=.22, color=COLORS[adapter], label=LABELS[adapter])
        for x, value in zip(positions+offset, values):
            right.text(x, value+.055, f'{value:.3f}', ha='center', va='bottom', fontsize=10)
    right.set_xticks(positions, ['1 query\nsecondary', '3 queries\nprimary', '5 queries\nsecondary'])
    right.set_ylim(0, max(evidence['by_budget'][str(b)]['family_macro_mae_lut4'][a] for b in (1, 3, 5) for a in ADAPTERS)*1.42)
    right.set_ylabel('Equal-family unqueried MAE (LUT4) ↓')
    right.set_title('B  All adapters and budgets · changing cases', loc='left', pad=16)
    right.grid(axis='y', color='#E2E6EA', linewidth=.7)
    right.legend(frameon=False, fontsize=9, loc='upper right')
    table_ax.axis('off')
    table_rows = []
    for episode in prepared['episodes']:
        family = episode['family']
        name = family if episode['primary_family'] else 'isqrt · secondary'
        row = [name]
        for budget in (1, 3, 5):
            counts = denominators[family][str(budget)]
            row.append(f'{counts["unqueried_rows"]}   ({counts["positive_targets"]} / {counts["zero_targets"]})'
                       if not counts['missing_programs'] else 'exhausted · score undefined')
        table_rows.append(row)
    table = table_ax.table(cellText=table_rows,
        colLabels=['Family', 'Budget 1 · N (positive / zero)', 'Budget 3 · N (positive / zero)', 'Budget 5 · N (positive / zero)'],
        colWidths=[.19, .27, .27, .27], cellLoc='center', bbox=[-.09, .02, 1.09, .88])
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor('#D8E0E6')
        if row == 0:
            cell.set_facecolor('#E7EEF3');cell.set_text_props(weight='bold')
        elif table_rows[row-1][0] == 'fft':
            cell.set_facecolor('#FFF3DA')
        elif table_rows[row-1][0] == 'isqrt · secondary':
            cell.set_facecolor('#F4F4F4')
    table_ax.set_title('C  Exact unqueried denominators · identity groups control exclusion, not weighting', loc='left', pad=13)
    fig.text(.035, .057, 'Consumed-V8 development only · four source families · no population confidence intervals. '
             'FFT has only 3 zero targets at budget 3 and 1 at budget 5.\n'
             'The query policy is frozen: this study tests correction of remaining points, not improved instruction selection or CPU performance.',
             fontsize=10, color='#48515C', va='bottom')
    artifacts = []
    for extension in ('png', 'svg', 'pdf'):
        path = output / ('v9-budgeted-residual-correction.'+extension)
        metadata = {'CreationDate': None, 'ModDate': None} if extension == 'pdf' else None
        fig.savefig(path, dpi=220, bbox_inches='tight', pad_inches=.2, metadata=metadata)
        artifacts.append(path)
    plt.close(fig)
    data_path = output / 'figure-data.json'
    write(data_path, {'primary': primary, 'by_budget': evidence['by_budget'], 'denominators': denominators})
    caption_path = output / 'caption.md'
    caption = ('**Paid target-label correction on consumed V8 data.** Panel A shows the fixed primary contrast '
        'after three measured original formulas per primary family: local residual correction minus frozen-V6 MAE on identical unqueried cases. '
        f'The equal-family change is {delta:+.6f} LUT4 ({abs(delta)/means["frozen"]*100:.2f}% lower MAE); '
        'every family and the zero FFT difference remain visible. Panel B includes the fixed global-offset ablation '
        'and all budgets, with a zero-origin resource-error axis. Budget comparisons change the surviving cases '
        'and cannot establish a learning curve on one common test set. Panel C gives retained original-formula rows '
        'and positive/zero-target counts; FFT has no positive remaining targets at budgets 3 or 5, and isqrt is exhausted '
        'after two queries. Original formula rows are averaged within program, programs within family, then the four primary families equally. '
        'This descriptive consumed-cohort development result is neither independent transfer confirmation nor a demonstration '
        'of improved instruction selection, processor speedup, or calibrated prediction bounds.\n')
    with caption_path.open('x') as stream:
        stream.write(caption)
    if {str(path): sha(path) for path in inputs} != before:
        raise ValueError('Presentation input/source changed during rendering')
    write(output / 'figure-manifest.json', {'schema': 'isaforge-v9-presentation-manifest-v1',
        'source_and_input_sha256': before,
        'output_sha256': {p.name: sha(p) for p in [*artifacts, data_path, caption_path]},
        'matplotlib': matplotlib.__version__, 'python': sys.executable, 'new_fits': 0,
        'new_measurements': 0, 'forecasts_recomputed': False, 'axes': 'zero included; no broken axes',
        'scope': 'Consumed-V8 descriptive development; changing unqueried sets across budgets.'})
    print(f'Wrote V9 PNG/SVG/PDF and hash-bound figure data at {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)
