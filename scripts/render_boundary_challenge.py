#!/usr/bin/env python3
"""Render the frozen fresh boundary-challenge comparison; no fits or synthesis."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/boundary-challenge'

def main():
    paths = [OUT / name for name in ('fresh-metrics.json', 'development-metrics.json', 'audit.json')]
    fresh, dev, audit = [json.loads(p.read_text()) for p in paths]
    if audit['status'] != 'pass':
        raise ValueError('Independent evidence audit must pass before rendering')
    current = 'incumbent_signed'
    evaluated = fresh['evaluated_candidate']
    names = [current, 'budget_release_compound_only', evaluated]
    labels = ['Signed incumbent', 'Budget release', 'Median repair']
    models = fresh['models']
    counts = {models[n]['count'] for n in names}
    if len(counts) != 1:
        raise ValueError('Matched cohort required')
    n = counts.pop()
    colors = ['#70899C', '#BA8C45', '#087F83']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42, 'font.size': 11})
    fig, axs = plt.subplots(2, 2, figsize=(13, 9))
    fig.subplots_adjust(left=.16, right=.97, bottom=.25, top=.82, hspace=.65, wspace=.65)
    fig.suptitle('Testing the median repair where predictions disagree', x=.06, y=.97, ha='left', fontsize=23, fontweight='bold', color='#14283F')
    fig.text(.06, .916, f'{n} selected fresh circuits from a fixed 200-input pool · selection and predictions frozen before labels', color='#596C7B')
    eligible = fresh.get('scoped_experimental_eligibility', False)
    fig.text(.06, .88, 'Predeclared selection and fresh gates: ' + ('PASS' if eligible else 'NOT PASSED — candidate remains diagnostic'), color='#087F83' if eligible else '#A44635', fontweight='bold')
    for ax, metric, title in zip(axs[0], ['mae_lut4', 'positive_mape_percent'], ['Mean absolute error · LUT4 ↓', 'Positive-target MAPE · % ↓']):
        values = [models[k][metric] for k in names]
        ax.barh([2, 1, 0], values, color=colors, height=.55, zorder=3)
        ax.set_yticks([2, 1, 0], labels)
        ax.set_xlim(0, max(values)*1.25)
        for y, value in zip([2, 1, 0], values):
            ax.text(value+max(values)*.025, y, f'{value:.2f}', va='center', fontweight='bold')
        ax.set_title(title, loc='left', fontsize=13, pad=15)
    caps = ['32', '64', '128']
    for ax, field, title in zip(axs[1], ['false_accept', 'false_reject'], ['False acceptances · lower is better', 'False rejections · lower is better']):
        for j, name in enumerate(names):
            vals = [models[name]['caps'][cap][field] for cap in caps]
            xx = np.arange(3)+(j-1)*.24
            ax.bar(xx, vals, width=.22, color=colors[j], label=labels[j], zorder=3)
            for x, value in zip(xx, vals):
                ax.text(x, value+.12, str(value), ha='center', fontsize=10)
        maximum = max(models[name]['caps'][cap][field] for name in names for cap in caps)
        ax.set_ylim(0, max(2, maximum+2))
        ax.set_xticks(range(3), [f'{c} LUT4' for c in caps])
        ax.set_title(title, loc='left', fontsize=13, pad=15)
        ax.yaxis.get_major_locator().set_params(integer=True)
    for ax in axs.flat:
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='x' if ax in axs[0] else 'y', color='#E2E8ED', zorder=0)
        ax.set_axisbelow(True)
    axs[1, 0].legend(loc='upper left', fontsize=8, frameon=False)
    den = models[current]['caps']
    denominators = ' · '.join(f"{c} LUT4: {den[c]['actual_accept']} feasible / {n-den[c]['actual_accept']} infeasible" for c in caps)
    fig.text(.06, .15, denominators, fontsize=10, color='#596C7B')
    worst = ' → '.join(f"{models[k]['maximum_underprediction_lut4']:.2f}" for k in names)
    fig.text(.06, .117, f'Worst underprediction (signed → release → repair): {worst} LUT4.', fontsize=10, color='#596C7B')
    coverage = fresh['selection_coverage']
    fig.text(.06, .18, f"Conditional challenge: {coverage['selected_active_count']} changed predictions across {len(coverage['selected_active_templates'])} templates + {coverage['selected_control_count']} fixed controls.", fontsize=10, color='#596C7B')
    fig.text(.06, .083, 'Prediction-conditioned challenge, not a population estimate. All 200 pool records retained; no pooling with the separate broad 40-case test.', fontsize=9.5, color='#596C7B')
    fig.text(.06, .05, 'Targeted isolated iCE40 area study; no calibrated safety, application-transfer, timing, power or CPU-speed claim.', fontsize=9.5, color='#596C7B')
    folder = ROOT / 'docs/figures/research'
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    outputs = {}
    for ext in ('svg', 'png', 'pdf'):
        path = folder / f'boundary-challenge.{ext}'
        fig.savefig(path, dpi=180, facecolor='white', metadata={'Creator': 'scripts/render_boundary_challenge.py'})
        outputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(path)
    plt.close(fig)
    (OUT / 'figure-provenance.json').write_text(json.dumps({'inputs_sha256': hashes, 'outputs_sha256': outputs, 'fits': 0, 'native_jobs': 0}, indent=2)+'\n')

if __name__ == '__main__':
    main()
