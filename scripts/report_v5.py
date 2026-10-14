#!/usr/bin/env python3
"""Scientific V5 figures from frozen scores, with all scopes and failures."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ORDER = ('v4_frozen', 'masterrtl_fixed', 'sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics')
LABELS = {'v4_frozen': 'V4 frozen', 'masterrtl_fixed': 'Fixed MasterRTL recipe',
          'sog_tuned': 'Equally tuned SOG', 'original_graph': 'SOG + original graph',
          'dual_graph': 'SOG + dual graphs', 'dual_semantics': 'Dual graphs + semantics'}
SCOPES = ('known_families', 'unseen_compositions')


def table(headers, rows):
    return '<div class="table"><table><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in headers)+'</tr>'+''.join(
        '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table></div>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.evaluation.read_text())
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                        'axes.spines.top': False, 'axes.spines.right': False,
                        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'isaforge-v5'})
    figures = []

    def save(fig, name, caption):
        for ext in ('svg', 'pdf', 'png'):
            metadata = {'Date': None} if ext == 'svg' else {'CreationDate': None, 'ModDate': None} if ext == 'pdf' else {}
            fig.savefig(out/f'{name}.{ext}', bbox_inches='tight', dpi=200, metadata=metadata)
        plt.close(fig)
        svg = (out/f'{name}.svg').read_text()
        figures.append('<figure>'+svg[svg.index('<svg'):]+'<figcaption>'+caption+
                       f' <a href="{name}.pdf">PDF</a> · <a href="{name}.svg">SVG</a></figcaption></figure>')

    colors = ['#81909E', '#B27A4B', '#49697F', '#6AA0AF', '#3E8D83', '#17699C']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True, layout='constrained')
    for ax, scope in zip(axes, SCOPES):
        values = [data['models'][n]['by_scope'][scope]['mae_lut4'] for n in ORDER]
        ax.barh(range(len(ORDER)), values, color=colors)
        ax.set_title('Known families (secondary)' if scope == 'known_families' else 'Unseen compositions (primary)', loc='left')
        ax.set_xlabel('MAE (LUT4)'); ax.set_xlim(0, max(values)*1.2)
        for i, value in enumerate(values):
            ax.text(value+max(values)*.015, i, f'{value:.2f}', va='center', fontsize=9)
        ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(ORDER)), [LABELS[n] for n in ORDER]); axes[0].invert_yaxis()
    save(fig, 'scope-comparison', 'Each scope has 128 original-RTL circuits, 16 per stratum. All predictions, zeros and outliers remain. V5 views use identical fitting rows, folds and tuning budgets. V4 is an older frozen fit.')

    fig, ax = plt.subplots(figsize=(10, 4.3), layout='constrained')
    names = [n for n in ORDER if n != 'dual_semantics']
    ax.axvline(0, ls='--', color='#607580')
    for i, name in enumerate(names):
        c = data['paired_comparisons']['unseen_compositions'][name]
        low, high = c['descriptive_cluster_bootstrap_95_interval']
        point = c['macro_stratum_mae_difference_lut4']
        ax.plot([low, high], [i, i], lw=3, color='#17699C'); ax.scatter(point, i, color='#17699C')
        ax.annotate(f'{point:+.2f} [{low:+.2f}, {high:+.2f}]', (high, i), xytext=(6, 6), textcoords='offset points', fontsize=9)
    ax.set_yticks(range(len(names)), [LABELS[n] for n in names]); ax.invert_yaxis()
    ax.set_xlabel('Dual+semantics MAE minus comparator MAE (LUT4); negative favors dual+semantics')
    ax.set_title('Unseen compositions: paired descriptive 95% cluster intervals', loc='left')
    ax.margins(x=.35); ax.grid(axis='x', alpha=.15)
    save(fig, 'paired-primary', 'Whole structural/equivalence clusters are sampled together globally, preserving macro-stratum weighting. 10,000 valid draws; empty-stratum draws are rejected. Only 19 unseen-composition clusters are available; five strata each contain a single cluster. These conditional intervals cannot estimate between-family uncertainty in those strata and are not population or multiple-comparison guarantees.')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout='constrained')
    rows = data['models']['dual_semantics']['candidate_errors']
    for ax, scope in zip(axes, SCOPES):
        selected = [r for r in rows if r['evaluation_scope'] == scope]
        y = np.asarray([r['lut4_count'] for r in selected]); p = np.asarray([r['predicted_lut4'] for r in selected])
        ax.scatter(np.log1p(y), np.log1p(p), alpha=.7, s=24, color='#17699C')
        limit = max(np.log1p(y).max(), np.log1p(p).max())+.2
        ax.plot([0, limit], [0, limit], '--', color='#718391')
        ticks = [v for v in (0, 1, 4, 16, 64, 256, 1024, 4096) if np.log1p(v) <= limit]
        ax.set_xticks(np.log1p(ticks), ticks); ax.set_yticks(np.log1p(ticks), ticks)
        ax.set_xlim(-.1, limit); ax.set_ylim(-.1, limit); ax.set_aspect('equal')
        ax.set_title(scope.replace('_', ' ').capitalize(), loc='left')
        ax.set_xlabel('Measured LUT4 (log1p coordinates)'); ax.set_ylabel('Predicted LUT4 (log1p coordinates)')
        for i in np.argsort(abs(p-y))[-2:]:
            ax.annotate(f'{y[i]:.0f}→{p[i]:.1f}', (np.log1p(y[i]), np.log1p(p[i])), xytext=(5, 7), textcoords='offset points', fontsize=8)
    save(fig, 'all-predictions', 'All 256 dual+semantics predictions; no difficult case is removed. The two largest errors per scope are annotated. Coordinates use log1p to retain true zero targets.')

    fig, ax = plt.subplots(figsize=(10, 4.3), layout='constrained')
    bounded = ('sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics')
    positions = np.arange(len(bounded))
    for offset, scope, color in ((-.18, 'known_families', '#3E8D83'), (.18, 'unseen_compositions', '#17699C')):
        values = [100*data['models'][n]['by_scope'][scope]['upper_bound']['whole_component_coverage'] for n in bounded]
        ax.bar(positions+offset, values, width=.34, color=color, label=scope.replace('_', ' ').capitalize())
        for x, value in zip(positions+offset, values):
            ax.text(x, value+1, f'{value:.1f}%', ha='center', fontsize=9)
    ax.axhline(90, ls='--', color='#A64A38', label='Nominal 90% under exchangeability')
    ax.set_xticks(positions, [LABELS[n].replace(' + ', '\n+ ') for n in bounded])
    ax.set_ylim(0, 112); ax.set_ylabel('Whole-component upper-bound coverage (%)')
    ax.set_title('Calibrated bounds lose coverage on unseen structures', loc='left')
    ax.legend(loc='lower left', fontsize=9); ax.grid(axis='y', alpha=.15); ax.set_axisbelow(True)
    save(fig, 'bound-coverage', 'A component is covered only if every circuit in it is below its upper estimate. Denominators are 94 known-family components and 19 unseen-composition components. Nominal coverage requires exchangeability; the shifted-cohort results do not support that assumption.')

    tables = []
    for scope in SCOPES:
        scores = []
        for n in ORDER:
            m = data['models'][n]['by_scope'][scope]
            fmt = lambda v: 'n/a' if v is None else f'{v:.2f}'
            scores.append([LABELS[n], fmt(m['mae_lut4']), fmt(m['positive_mape_percent']), fmt(m['positive_median_ape_percent']), f"{m['rmsle']:.3f}", fmt(m['zero_target_mae_lut4'])])
        tables += ['<h2>'+scope.replace('_', ' ').capitalize()+'</h2>', table(['Predictor', 'MAE LUT4', 'MAPE %', 'Median APE %', 'RMSLE', 'Zero MAE'], scores)]
    strata = data['models']['dual_semantics']['by_scope']['unseen_compositions']['by_stratum']
    tables += ['<h2>Unseen compositions by stratum</h2><p>The full model’s aggregate gain comes from multiplication. Across the other seven strata together, its MAE is 10.87 versus 10.72 LUT4 for tuned SOG. These are post-test diagnostics; all eight strata remain in the primary endpoint.</p>', table(['Stratum', 'Tuned SOG', 'Original graph', 'Dual graphs', 'Dual + semantics'], [[s]+[f"{data['models'][n]['by_scope']['unseen_compositions']['by_stratum'][s]['mae_lut4']:.2f}" for n in ('sog_tuned', 'original_graph', 'dual_graph', 'dual_semantics')] for s in strata])]
    worst = sorted(rows, key=lambda r: r['absolute_error_lut4'], reverse=True)[:12]
    coverage = []
    for name in ORDER:
        if name in ('masterrtl_fixed', 'v4_frozen'):
            continue
        for scope in SCOPES:
            c = data['models'][name]['by_scope'][scope]['upper_bound']
            coverage.append([LABELS[name], scope, f"{100*c['candidate_coverage']:.1f}%", f"{100*c['whole_component_coverage']:.1f}%", str(c['mean_upper_minus_target_lut4'])])
    body = '<p class="eyebrow">ISAForge • V5 frozen research experiment</p><h1>Original and normalized circuit representations</h1><p>Matched small-model comparison on original iCE40 LUT4 cost. The primary endpoint is unseen-composition macro-stratum MAE; the primary comparison is dual graphs plus semantics versus equally tuned original SOG. All V4 evidence remains separate and frozen.</p>'
    full = data['models']['dual_semantics']['by_scope']['unseen_compositions']['mae_lut4']
    reference = data['models']['sog_tuned']['by_scope']['unseen_compositions']['mae_lut4']
    original = data['models']['original_graph']['by_scope']['unseen_compositions']['mae_lut4']
    body += f'<p><strong>Primary result: {full:.2f} versus {reference:.2f} LUT4 MAE, a {100*(1-full/reference):.2f}% reduction.</strong> The simpler original-graph view has lower observed MAE ({original:.2f}); extra semantic features do not improve this test. Bounds under-cover unseen structural groups. These findings guide a new evaluation rather than changing this frozen endpoint.</p>'
    body += ''.join(tables)+''.join(figures)
    body += '<h2>Remaining largest failures</h2>'+table(['Scope', 'Formula', 'Measured', 'Predicted', 'Absolute error'], [[r['evaluation_scope'], r['formula'], r['lut4_count'], round(r['predicted_lut4'], 3), round(r['absolute_error_lut4'], 3)] for r in worst])
    body += '<h2>Upper-bound calibration</h2><p>Bounds use maxima of residuals within held-out calibration components. 90% nominal coverage requires exchangeable whole groups, which is not established for novel compositions. Observed coverage and slack are diagnostics; tree disagreement is not calibrated confidence.</p>'+table(['Model', 'Scope', 'Candidate coverage', 'Whole-component coverage', 'Mean upper − actual LUT4'], coverage)
    body += '<h2>Research context and next validation</h2><p><a href="https://arxiv.org/html/2311.08441v1">MasterRTL</a> motivates bit-level representations and low-cost tree models; its ASIC designs and published area percentage are not this FPGA benchmark. <a href="https://doi.org/10.1145/2560014">Lam et al.</a> motivate carry/width-aware custom-instruction estimates, while excluding several complex operations from their evaluated class. <a href="https://arxiv.org/abs/1403.5607">Constrained Bayesian optimization</a> motivates calibrated feasibility and explicit measurement cost. These ideas require matched evaluation here.</p><p>This experiment does not establish CPU speedup or useful acquisition savings. The next application study needs untouched source families, correct compilation/execution, equally budgeted merit/random/model comparisons and whole-processor resource/timing measurements. A changed model requires another untouched test.</p>'
    body += '<p><a href="report-data.json">Complete scores and all error rows</a> · <a href="provenance.json">Source provenance</a></p>'
    css = 'body{font:16px/1.6 system-ui;color:#20394b;background:#f5f7f9}main{max-width:1100px;margin:auto;padding:38px;background:white}h1{font-size:36px;line-height:1.2}h2{margin-top:38px;color:#185372}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:1px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #dce4ea;text-align:left;overflow-wrap:anywhere}th{background:#edf4f8}figure{margin:28px 0}figure svg{width:100%;height:auto}figcaption{font-size:13px;color:#536d7e}a{color:#096b9c}'
    (out/'report.html').write_text('<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge V5</title><style>'+css+'</style><main>'+body+'</main></html>')
    (out/'report-data.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({'evaluation_sha256': hashlib.sha256(args.evaluation.read_bytes()).hexdigest(), 'report_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'model_freeze_sha256': data['freeze_sha256'], 'all_rows_retained': True}, indent=2)+'\n')
    print(out/'report.html')


if __name__ == '__main__':
    main()
