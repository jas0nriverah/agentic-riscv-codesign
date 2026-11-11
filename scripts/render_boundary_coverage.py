#!/usr/bin/env python3
"""Render the matched coverage trial from independently audited saved evidence."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'results/boundary-coverage'
KEYS = ('incumbent_signed', 'budget_release_compound_only',
        'boundary_structural', 'boundary_coverage_only', 'boundary_augmented')
LABELS = ('Signed', 'Release', 'Prior repair', 'Coverage · 217', 'Local features · 233')
COLORS = ('#8797A5', '#B88D48', '#5F748B', '#369CB0', '#087F68')
INK, MUTED = '#14283F', '#596C7B'


def main():
    paths = [RESULT / name for name in ('fresh-metrics.json', 'audit.json')]
    data, audit = [json.loads(path.read_text()) for path in paths]
    if audit['status'] != 'pass':
        raise ValueError('Independent evidence audit required before rendering')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig = plt.figure(figsize=(16, 12), facecolor='white')
    fig.text(.04, .955, 'Training coverage and local features: matched comparison',
             fontsize=23, fontweight='bold', color=INK)
    fig.text(.04, .922, 'Two fixed 300-tree fits · identical 1,857 training circuits · 32 new training labels · 217 vs 233 features', color=MUTED)
    selected = data['selected_candidate']
    selected_label = LABELS[KEYS.index(selected)] if selected else 'none (development gates failed)'
    fig.text(.04, .892, 'Development-selected policy: ' + selected_label + ' · ' +
             ('All declared gates pass' if data['scoped_experimental_eligibility'] else 'Not eligible for promotion'),
             color='#087F68' if data['scoped_experimental_eligibility'] else '#A44635', fontweight='bold')
    for left, models, title in (
        (.04, data['models'], f"General cohort · {data['general_count']} fixed circuits"),
        (.535, data['conditional_models'], f"Conditional cohort · {data['active_count']} active + 8 shared controls"),
    ):
        fig.text(left, .845, title, fontsize=14, color=INK, fontweight='bold')
        for bottom, metric, title in ((.635, 'mae_lut4', 'Policy MAE · LUT4 ↓'),
                                      (.405, 'positive_mape_percent', 'Policy positive-target MAPE · % ↓')):
            fig.text(left, bottom + .165, title, color=MUTED)
            ax = fig.add_axes([left + .13, bottom, .29, .145])
            values = [models[key][metric] for key in KEYS]
            ax.barh(range(4, -1, -1), values, color=COLORS, height=.65, zorder=3)
            ax.set_yticks(range(4, -1, -1), LABELS)
            ax.set_xlim(0, max(max(values), .01) * 1.32)
            ax.spines[['top', 'right', 'left']].set_visible(False)
            ax.tick_params(length=0)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
            ax.grid(axis='x', color='#E1E8ED', zorder=0)
            for y, value in zip(range(4, -1, -1), values):
                ax.text(value + max(max(values), .01) * .025, y, f'{value:.2f}', va='center', fontsize=9)
        fig.text(left, .355, 'False accepts / false rejects · each budget assessed separately', color=INK, fontsize=10, fontweight='bold')
        ax = fig.add_axes([left, .235, .44, .10]); ax.axis('off')
        cells = [[cap] + [f"{models[key]['caps'][cap]['false_accept']} / {models[key]['caps'][cap]['false_reject']}" for key in KEYS] for cap in ('32', '64', '128')]
        table = ax.table(cellText=cells, colLabels=['Cap', 'Signed', 'Release', 'Prior', '217', '233'], cellLoc='center', bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False); table.set_fontsize(9)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#DFE7EC')
            if row == 0:
                cell.set_facecolor('#EFF4F7'); cell.set_text_props(weight='bold', color=INK)
        ref = models[KEYS[0]]
        fig.text(left, .208, 'Feasible / infeasible: ' + ' · '.join(f"{cap}: {ref['caps'][cap]['actual_accept']}/{ref['count'] - ref['caps'][cap]['actual_accept']}" for cap in ('32', '64', '128')), fontsize=9, color=MUTED)
    fig.text(.04, .155, 'The new forests support a fixed cap-correction policy; bars show final policy predictions, not standalone raw-regressor accuracy.', color=MUTED)
    fig.text(.04, .125, 'Raw-regressor diagnostics and active-only gates are retained in the report. Candidate selection precedes fresh labels; no post-test model switch.', color=MUTED)
    fig.text(.04, .095, 'Eight controls are shared between cohorts. Conditional cases are selected by prediction disagreement; the cohorts are not pooled.', color=MUTED)
    fig.text(.04, .065, 'Measured target: isolated iCE40 LUT4 count. This is not a CPU speedup, application-transfer or universal hardware-safety result.', color=MUTED)
    outputs = {}
    for extension in ('svg', 'png', 'pdf'):
        path = ROOT / f'docs/figures/research/boundary-coverage.{extension}'
        fig.savefig(path, dpi=180, facecolor='white', metadata={'Creator': 'scripts/render_boundary_coverage.py'})
        outputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    (RESULT / 'figure-provenance.json').write_text(json.dumps({
        'inputs_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'outputs_sha256': outputs, 'fits': 0, 'native_jobs': 0,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
