#!/usr/bin/env python3
"""Render the saved, matched feature comparison without fitting any model.

The source is a development cross-validation report, not an independent test.
All plotted values come directly from its summary. SVG text remains editable;
PDF fonts are embedded and the PNG is rendered at publication resolution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / 'results/feature-comparison/summary.json'
DEFAULT_OUTPUT = ROOT / 'docs/figures/research'
INK = '#14283F'
MUTED = '#596C7B'
GRID = '#DCE5EB'
COLORS = ('#416C9B', '#879BAE', '#087F83')
MODEL_ORDER = ('mapping217', 'original336', 'selected128')
MODEL_LABELS = ('Mapping 217', 'Original 336', 'Selected 128')
METRICS = (
    ('group_macro_mae_lut4', 'Group-macro MAE', 'LUT4 · primary endpoint', '.2f'),
    ('positive_mape_percent', 'Positive-target MAPE', '% · pooled positive labels', '.2f'),
    ('maximum_underprediction_lut4', 'Worst underprediction', 'LUT4 · pooled predictions', '.2f'),
)


def load_summary(path: Path) -> tuple[dict, list[dict]]:
    """Reject missing/nonfinite observations rather than draw placeholder data."""
    summary = json.loads(path.read_text())
    if summary.get('schema') != 'isaforge-matched-feature-comparison-v1' or summary.get('fits_completed') != 15:
        raise ValueError('A complete fifteen-fit matched feature comparison is required')
    protocol_path = path.with_name('protocol.json')
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != summary['protocol_sha256']:
        raise ValueError('Source protocol hash does not match the completed summary')
    models = summary['metrics']
    if set(models) != set(MODEL_ORDER):
        raise ValueError(f'Expected exactly these matched models: {MODEL_ORDER}')
    rows = [models[name] for name in MODEL_ORDER]
    for row in rows:
        for key, *_ in METRICS:
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Finite nonnegative metric required: {key}')
    if len({row['count'] for row in rows}) != 1 or len({row['positive_count'] for row in rows}) != 1:
        raise ValueError('All comparators must cover the same matched observations')
    if len({row['group_count'] for row in rows}) != 1:
        raise ValueError('All comparators must cover the same groups')
    if any(len(row['by_fold']) != 5 for row in rows):
        raise ValueError('The completed five-fold comparison is required')
    return summary, rows


def render(summary_path: Path, output: Path) -> list[Path]:
    summary, rows = load_summary(summary_path)
    n = rows[0]['count']
    positive_n = rows[0]['positive_count']
    groups = rows[0]['group_count']
    digest = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 11,
        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'axes.unicode_minus': False,
    })
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.4), facecolor='white')
    fig.subplots_adjust(left=.135, right=.962, top=.69, bottom=.27, wspace=.38)
    fig.text(.045, .936, 'Matched comparison of feature representations',
             fontsize=23, fontweight='bold', color=INK)
    fig.text(.045, .875, 'DEVELOPMENT CROSS-VALIDATION', fontsize=10.5,
             fontweight='bold', color=COLORS[2])
    fig.text(.045, .828,
             f'5 matched folds · {n:,} circuit predictions · {groups:,} groups · lower error is better',
             fontsize=12, color=MUTED)

    y = [2, 1, 0]
    for index, (ax, (key, title, unit, fmt)) in enumerate(zip(axes, METRICS)):
        values = [row[key] for row in rows]
        maximum = max(values)
        bound = maximum * 1.27 if maximum else 1.0
        ax.set_xlim(0, bound)
        ax.set_ylim(-.65, 2.65)
        ax.barh(y, values, height=.46, color=COLORS, zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(MODEL_LABELS if index == 0 else ['', '', ''], color=INK, fontsize=12)
        ax.tick_params(axis='y', length=0, pad=11)
        ax.tick_params(axis='x', length=0, pad=8, labelsize=10, colors=MUTED)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4, min_n_ticks=3))
        ax.xaxis.grid(True, color=GRID, linewidth=.8, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.spines['bottom'].set_color(GRID)
        ax.set_title(title, loc='left', pad=29, fontsize=13, fontweight='bold', color=INK)
        ax.text(0, 1.035, unit, transform=ax.transAxes, fontsize=9.5, color=MUTED)
        for yy, value, color in zip(y, values, COLORS):
            ax.text(value + bound * .025, yy, format(value, fmt), va='center',
                    ha='left', fontsize=11.5, fontweight='bold', color=color)

    fig.lines.append(plt.Line2D([.045, .962], [.192, .192], transform=fig.transFigure,
                                color=GRID, linewidth=1))
    fig.text(.045, .151, 'Consumed development cohort; these are not independent test results.',
             fontsize=11, fontweight='bold', color=INK)
    false_safe = [row['caps']['128']['false_safe_count'] for row in rows]
    fig.text(.045, .108,
             'False-safe at cap 128 LUT4: ' + ' · '.join(f'{label}: {count}' for label, count in zip(MODEL_LABELS, false_safe)) +
             '  (prediction ≤128, actual >128)', fontsize=9.8, color='#855A1D')
    fig.text(.045, .065,
             f'MAPE uses {positive_n:,} strictly positive labels. Worst underprediction = max(0, measured − predicted).',
             fontsize=9.4, color=MUTED)
    fig.text(.045, .025,
             '128 features selected within each training fold. Source: results/feature-comparison/summary.json',
             fontsize=8.8, color=MUTED)

    output.mkdir(parents=True, exist_ok=True)
    paths = []
    provenance = f'Source summary SHA-256: {digest}. Development cross-validation; not an independent test.'
    for extension in ('svg', 'png', 'pdf'):
        path = output / f'feature-comparison.{extension}'
        metadata = {'Title': 'Matched feature comparison — development cross-validation',
                    'Creator': 'scripts/render_feature_comparison.py; Matplotlib'}
        metadata['Subject' if extension == 'pdf' else 'Description'] = provenance
        fig.savefig(path, dpi=300, facecolor='white', metadata=metadata)
        paths.append(path)
    plt.close(fig)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in render(args.summary, args.output):
        print(path.resolve())


if __name__ == '__main__':
    main()
