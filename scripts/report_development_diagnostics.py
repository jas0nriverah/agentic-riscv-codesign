#!/usr/bin/env python3
"""Plot repeated-seed development scores and exact inference runtime."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path('results/2026-10-14-development-diagnostics'))
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
scores = json.loads((args.root/'summary.json').read_text())['by_view']
timing = json.loads((args.root/'fast-graph-runtime.json').read_text())['timings']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42,
                     'svg.hashsalt': 'isaforge-development-diagnostics'})
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout='constrained')
names = ('original_graph', 'dual_graph', 'dual_semantics')
labels = ('Original\ngraph', 'Dual\ngraph', 'Dual graph\n+ semantics')
means = [scores[n]['macro_mae_mean'] for n in names]
sd = [scores[n]['macro_mae_std_across_seeds'] for n in names]
axes[0].errorbar(range(3), means, yerr=sd, fmt='o', color='#17699C', capsize=6)
for i, value in enumerate(means):
    axes[0].text(i+.08, value, f'{value:.3f}', va='center')
axes[0].set_xticks(range(3), labels)
axes[0].set_xlim(-.35, 2.5)
axes[0].set_ylabel('Macro-stratum MAE (LUT4)')
axes[0].set_title('Development OOF scores across five seeds', loc='left')
axes[0].grid(axis='y', alpha=.15)
axes[0].text(0, -.25, 'Same 1,665 fitting rows and five grouped folds.\nError bars: sample SD across seeds, not a confidence interval.',
             transform=axes[0].transAxes, fontsize=9, va='top')
x = np.arange(2)
for offset, name, label, color in ((-.18, 'standard', 'Standard V5 path', '#81909E'),
                                  (.18, 'original_only', 'Original-only path', '#17699C')):
    values = [timing[name]['cold_features_and_prediction_seconds'], timing[name]['warm_median_seconds']]
    axes[1].bar(x+offset, values, width=.34, label=label, color=color)
    for position, value in zip(x+offset, values):
        axes[1].text(position, value+.65, f'{value:.2f}', ha='center', fontsize=9)
axes[1].set_xticks(x, ['Cold cache', 'Warm cache'])
axes[1].set_ylabel('Feature extraction + prediction (seconds)')
axes[1].set_ylim(0, 43)
axes[1].set_title('Same original-graph model, exact outputs', loc='left')
axes[1].legend(frameon=False, loc='upper right', fontsize=9)
axes[1].grid(axis='y', alpha=.15); axes[1].set_axisbelow(True)
axes[1].text(0, -.25, '256 inputs, one worker; one cold pair, median of three warm runs.\nStandard ran first. Loading/startup excluded; no accuracy gain.',
             transform=axes[1].transAxes, fontsize=9, va='top')
for ext in ('png', 'svg', 'pdf'):
    metadata = {'Date': None} if ext == 'svg' else {'CreationDate': None, 'ModDate': None} if ext == 'pdf' else {}
    fig.savefig(args.output/f'stability-runtime.{ext}', dpi=250, bbox_inches='tight', metadata=metadata)
plt.close(fig)
print(args.output)
