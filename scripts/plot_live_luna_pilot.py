#!/usr/bin/env python3
"""Render preserved live-agent trajectories. Never queries a model or hardware."""
import argparse
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c


def plot(source, output):
    output = Path(output)
    if output.exists():
        raise ValueError('use a fresh output directory')
    data = c.unseal(source)
    output.mkdir(parents=True)
    fig, ax = plt.subplots(figsize=(10.5, 5.5), layout='constrained')
    for row, color, label in zip(data['rows'], ['#607286', '#2878A8'],
                                ['Live Luna: no retrieval', 'Live Luna: hybrid memory']):
        ax.plot([0, 1, 2, 3], [0]+[100*(1-1/p['best_speedup']) for p in row['curve']],
                marker='o', lw=2.5, label=label, color=color)
    row = next(x for x in data['controls'] if x['policy'] == 'latency_cost_heuristic')
    ax.plot([0, 1, 2, 3], [0]+[100*(1-1/p['best_speedup']) for p in row['curve']],
            marker='s', lw=2.5, color='#18856B', label='Latency/cost heuristic (archived)')
    ax.set(xlabel='Measurement allowance (charged archive queries)',
           ylabel='Best feasible whole-program cycle reduction (%)',
           xticks=[0, 1, 2, 3], ylim=(-.08, 2.4))
    ax.set_title('Live LLM pilot on archived SHA256 measurements', loc='left', fontsize=16, pad=16)
    ax.grid(axis='y', alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='lower right', frameon=False)
    fig.supxlabel('One episode per LLM arm. Hybrid stops at two queries; its result carries forward.\n'
                  'No new hardware jobs. No causal retrieval or generalization claim.', fontsize=10)
    for extension in ('png', 'svg'):
        fig.savefig(output/('pilot-performance.'+extension), dpi=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'results/2026-10-28-live-luna-memory/comparison.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plot(args.source, args.output)
