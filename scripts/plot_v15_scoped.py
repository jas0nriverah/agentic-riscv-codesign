#!/usr/bin/env python3
"""Render completed V15 synthetic stress evidence; no training/native jobs."""
import argparse
import hashlib
import json
from pathlib import Path


def render(root, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    files = {name: root/'attempt'/name for name in ('completion.json', 'metrics.json', 'labels.json', 'predictions.json')}
    data = {name: json.loads(path.read_text()) for name, path in files.items()}
    assert data['completion.json']['complete'] is True
    assert data['completion.json']['completed_mapping_count'] == 32
    metrics = data['metrics.json']['models']
    assert metrics['V15'] == metrics['V9']
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 11, 'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, (ax, table_ax) = plt.subplots(1, 2, figsize=(15, 7.5), gridspec_kw={'width_ratios': [1.4, 1]})
    fig.subplots_adjust(left=.20, right=.98, top=.79, bottom=.29, wspace=.3)
    keys = ['xor_then_constmul', 'constmul_then_xor', 'xor_signed_shift', 'and_signed_shift']
    names = ['Equal-template mean', 'XOR then constant product', 'Constant product then XOR', 'XOR then signed shift', 'AND then signed shift']
    ys = np.arange(5)
    for name, offset, color, label in [('V6', -.15, '#687887', 'Frozen V6'), ('V15', .15, '#147D92', 'Frozen V9 = scoped V15')]:
        values = [metrics[name]['macro_template_mae']] + [metrics[name]['template_mae'][k] for k in keys]
        ax.barh(ys+offset, values, height=.27, color=color, label=label)
        for y, value in zip(ys+offset, values):
            ax.annotate(f'{value:.2f}', (value, y), xytext=(4, 0), textcoords='offset points', va='center', fontsize=9)
    ax.set_yticks(ys, names); ax.invert_yaxis(); ax.set_xlim(0, ax.get_xlim()[1]*1.16)
    ax.set_xlabel('Mean absolute error · LUT4 (lower is better)')
    ax.grid(axis='x', color='#E2E8F0'); ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='upper left', bbox_to_anchor=(0, 1.23), frameon=False, fontsize=10)
    table_ax.axis('off')
    cells = []
    for name, label in [('V6', 'V6'), ('V15', 'V9 / V15')]:
        for cap in ('32', '64', '128'):
            row = metrics[name]['caps'][cap]
            cells.append([label, cap, row['false_accept'], row['false_reject']])
    table = table_ax.table(cellText=cells, colLabels=['Model', 'Cap', 'FA', 'FR'], cellLoc='center', bbox=[.03, .22, .94, .68])
    table.auto_set_font_size(False); table.set_fontsize(11)
    table_ax.text(.03, 1, 'Hardware-budget mistakes · all 32', fontsize=12, transform=table_ax.transAxes)
    table_ax.text(.03, .05, 'Worst underprediction, LUT4\nV6: %.2f     V9 / V15: %.2f' % (metrics['V6']['worst_underprediction']['lut4'], metrics['V15']['worst_underprediction']['lut4']), transform=table_ax.transAxes)
    fig.suptitle('Prospective arithmetic stress: 32 verified circuits', x=.08, y=.96, ha='left', fontsize=19)
    fig.text(.08, .895, 'Four fixed templates × eight parameters; frozen predictions before fresh original-RTL iCE40 measurements.', fontsize=11)
    fig.text(.08, .17, 'All 32 select V9 by the input-only gate, so V15 = V9 by construction. Zero new fits.\nRelated synthetic coverage test; no new application-transfer or router-generalization claim.', fontsize=10)
    fig.text(.08, .08, 'FA: predicted ≤ cap, measured > cap. FR: measured ≤ cap, predicted > cap.\nAll templates, threshold errors and tails retained; descriptive results, no population confidence interval.', fontsize=10)
    for suffix in ('png', 'svg', 'pdf'):
        fig.savefig(output/('v15-stress.'+suffix), dpi=180)
    plt.close(fig)
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'source_sha256': sha(Path(__file__)), 'inputs': {str(p): sha(p) for p in files.values()},
                'figures': {p.name: sha(p) for p in output.iterdir() if p.suffix in ('.png', '.svg', '.pdf')}, 'metrics': metrics,
                'scope': data['metrics.json']['scope']}
    (output/'figure-data.json').write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    render(args.root, args.output)
