#!/usr/bin/env python3
"""Render audited coverage and completion status, never partial accuracy metrics."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/control-sharing-coverage'


def main():
    names = ['incomplete-outcome.json', 'audit.json', 'prior-coverage-diagnosis.json',
             'measurement-input-profile-audit.json', 'evaluation-targets.json', 'timings.json']
    paths = [OUT / n for n in names]
    outcome, audit, before, added, targets, timings = [json.loads(p.read_text()) for p in paths]
    assert audit['status'] == 'pass' and not audit['scoped_experimental_eligibility']
    assert outcome['status'] == 'incomplete_primary_cohort'
    assert not outcome['complete_population_scoring_performed']
    assert all(p['complete_population_metrics'] is None for p in outcome['populations'].values())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig = plt.figure(figsize=(14, 9), facecolor='white')
    ink, muted, red = '#14283F', '#596C7B', '#A44635'
    fig.text(.05, .94, 'Targeted training coverage: fresh validation incomplete',
             fontsize=23, fontweight='bold', color=ink)
    fig.text(.05, .895, 'One new classifier · 1,889 → 1,921 training circuits · unchanged 233 features and fixed 0.5 rule', color=muted)
    fig.text(.05, .85, 'Not promoted: development regressions; 39 of 55 fresh synthesis labels missing', color=red, fontweight='bold')

    fig.text(.05, .775, 'Input-profile coverage in training', fontsize=14, fontweight='bold', color=ink)
    ax = fig.add_axes([.22, .53, .23, .20])
    keys = ['both_input_and_control', 'repeated_and_data_post_outer']
    old = [before['group_counts'][k]['training_rows'] for k in keys]
    new = [v + added['group_counts'][k] for k, v in zip(keys, old)]
    for y, a, b in zip([1, 0], old, new):
        ax.barh(y + .16, a, height=.27, color='#8797A5', label='Before' if y else None)
        ax.barh(y - .16, b, height=.27, color='#087F68', label='After' if y else None)
        ax.text(a + .5, y + .16, str(a), va='center')
        ax.text(b + .5, y - .16, str(b), va='center')
    ax.set_yticks([1, 0], ['Two-input AND control', 'Repeated AND sharing'])
    ax.set_xlim(0, max(new) + 5)
    ax.set_xlabel('Training circuits matching the stated input-only profiles')
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.16), ncol=2, frameon=False)
    fig.text(.05, .46, 'Profile matches do not establish cost or class transfer.', color=muted, fontsize=10)

    fig.text(.56, .775, 'Retained required decisions', fontsize=14, fontweight='bold', color=ink)
    accept = targets['required_acceptances_count']
    reject = targets['required_rejections_count']
    failed_reject = len(audit['failed_required_rejections'])
    fig.text(.56, .69, f'{accept}/{accept} required acceptances pass', fontsize=18, color='#087F68', fontweight='bold')
    fig.text(.56, .62, f'{reject - failed_reject}/{reject} protected rejections pass', fontsize=18, color=red, fontweight='bold')
    fig.text(.56, .52, 'The sharing125 rejection is repaired.\nFour protected unsafe cases are accepted.\nFull panels: seven unsafe acceptances; four newly introduced.', color=ink, linespacing=1.6)

    cov = outcome['label_coverage']
    fig.text(.05, .36, 'Fresh labels: complete population required', fontsize=14, fontweight='bold', color=ink)
    ax = fig.add_axes([.05, .245, .40, .065]); left = 0
    for key, label, color in [('complete', 'Complete', '#087F68'), ('timeout', 'Timeout', '#D38A3C'), ('unattempted', 'Not attempted', '#AAB5BF')]:
        n = cov[key]
        ax.barh(0, n, left=left, color=color, height=.7, label=f'{label}: {n}')
        left += n
    ax.set_xlim(0, cov['requested']); ax.axis('off')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.1), ncol=3, frameon=False, fontsize=9)
    fig.text(.05, .155, 'Fresh MAE / MAPE: NOT EVALUABLE', fontsize=14, color=red, fontweight='bold')
    fig.text(.05, .115, 'All 55 fresh circuits passed RTL checks; only 16 have area labels.', color=muted, fontsize=10)

    native = outcome['native_accounting']
    fig.text(.56, .36, 'Bounded execution', fontsize=14, fontweight='bold', color=ink)
    fig.text(.56, .29, f"{native['total_summed_worker_seconds']:.2f} / {native['process_limit_seconds']} worker-seconds", fontsize=18, color=ink, fontweight='bold')
    fig.text(.56, .235, f"{native['total_stage_wall_seconds']:.2f}s stage wall time · peak {native['peak_workers']} workers", color=muted)
    fig.text(.56, .185, '32 training labels complete · one fit · no retries', color=ink)
    fig.text(.56, .135, '87 circuits RTL-verified · 186,876 comparisons passed', color=ink, fontsize=10)
    fig.text(.05, .045, 'Measured target: isolated iCE40 LUT4 count. Missing outcomes are retained; no partial-population accuracy or safety claim.', color=muted, fontsize=10)

    outputs = {}
    for ext in ['svg', 'png', 'pdf']:
        p = ROOT / f'docs/figures/research/control-sharing-coverage.{ext}'
        fig.savefig(p, dpi=180, facecolor='white', metadata={'Creator': 'scripts/render_control_sharing_coverage.py'})
        outputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    plt.close(fig)
    (OUT / 'figure-provenance.json').write_text(json.dumps({
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'outputs_sha256': outputs, 'fresh_accuracy_metrics_plotted': False, 'fits': 0, 'native_jobs': 0,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
