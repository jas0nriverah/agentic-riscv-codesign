#!/usr/bin/env python3
"""Render audited V4 evaluation data, without model imports or score selection.

Usage: python scripts/report_v4.py --evaluation RESULTS/evaluation.json --out OUTPUT
The HTML embeds every figure and all report data, requiring no network or assets.
Separate PDF/SVG/PNG files are suitable for export. Zeros/outliers are retained.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import FuncNorm
import numpy as np

ORDER = ('v2_frozen', 'v3_frozen', 'masterrtl_frozen', 'masterrtl_retrained', 'v4')
LABELS = {'v2_frozen': 'V2 frozen (713 train)', 'v3_frozen': 'V3 frozen (713 train)',
          'masterrtl_frozen': 'MasterRTL frozen (713 train)',
          'masterrtl_retrained': 'MasterRTL retrained (1,289 train)',
          'v4': 'V4 (1,289 train)'}
SHORT = {'v2_frozen': 'V2 frozen', 'v3_frozen': 'V3 frozen',
         'masterrtl_frozen': 'MasterRTL frozen', 'masterrtl_retrained': 'MasterRTL retrained', 'v4': 'V4'}
COLORS = {'v2_frozen': '#9AA5B1', 'v3_frozen': '#687889', 'masterrtl_frozen': '#6F8798',
          'masterrtl_retrained': '#B56E34', 'v4': '#1768AC'}
STRATA = ('arithmetic_chain', 'comparators', 'constant_shifts', 'mask_logic',
          'multiplication', 'parallel_branches', 'shared_diamond', 'variable_shifts')
CAPTIONS = {
    'comparator-errors': 'All five frozen prediction files are scored on the same 256 new formulas, 32 in each of eight strata. Equal stratum sizes make macro MAE equal pooled MAE. MAPE uses the 235 positive labels; all 21 zero labels remain in MAE. MAPE is error, not an accuracy percentage. Frozen V2/V3/MasterRTL trained on 713 formulas; V4 and retrained MasterRTL trained on the same 1,289 development formulas. Differences against older fits include a training-data confound.',
    'paired-mae': 'Paired difference is V4 absolute error minus comparator absolute error; negative values favor V4. Dots show macro-stratum means and bars show the frozen evaluator\'s descriptive 95% percentile intervals from 10,000 paired resamples within fixed strata. These are not population confidence intervals or adjusted significance tests. The same-data retrained MasterRTL comparison is highlighted; its interval includes zero.',
    'stratum-errors': 'Every stratum contains all 32 preregistered formulas. Cell labels are MAE in LUT4; color uses log1p only to keep small and large errors visible. No formula, zero label, or outlier is removed. The multiplication stratum remains V4\'s largest error and is worse than retrained MasterRTL.',
    'v4-scatter': 'All 256 measured/predicted pairs are plotted on log1p coordinates with ticks showing original LUT4 counts. Both axes include zero and share the same limits; the dashed diagonal is exact prediction. Duplicate points may overlap. Three largest absolute-error observations are labeled, including zero-label outliers. The 64-LUT guides are descriptive and do not remove points.',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fmt(value, digits=2):
    return 'n/a' if value is None else f'{value:,.{digits}f}'


def configure():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.labelsize': 10, 'axes.titlesize': 12, 'axes.spines.top': False,
        'axes.spines.right': False, 'axes.edgecolor': '#BAC4CE',
        'axes.labelcolor': '#273747', 'text.color': '#1F3040',
        'xtick.color': '#415568', 'ytick.color': '#415568',
        'grid.color': '#E6EBF0', 'grid.linewidth': .7,
        'svg.fonttype': 'none', 'svg.hashsalt': 'isaforge-v4-report-v1',
        'pdf.fonttype': 42, 'savefig.facecolor': 'white'})


def export(fig, out, name):
    fig.savefig(out/f'{name}.svg', bbox_inches='tight', metadata={'Date': None})
    fig.savefig(out/f'{name}.pdf', bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
    fig.savefig(out/f'{name}.png', bbox_inches='tight', dpi=200)
    plt.close(fig)


def comparators(evaluation, out):
    models = evaluation['models']
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.9), sharey=True, layout='constrained')
    positions = np.arange(len(ORDER))
    for ax, field, title in zip(axes, ['mae_lut4', 'positive_mape_percent'],
                               ['Macro-stratum MAE (LUT4)', 'Positive-label MAPE (%)']):
        values = [models[n]['pooled'][field] for n in ORDER]
        ax.barh(positions, values, height=.62, color=[COLORS[n] for n in ORDER])
        ax.set_xlim(0, max(values)*1.18)
        ax.set_title(title, loc='left', pad=13)
        ax.set_axisbelow(True); ax.grid(axis='x')
        for i, value in enumerate(values):
            ax.text(value+max(values)*.018, i, fmt(value), va='center', fontsize=9,
                    fontweight='bold' if ORDER[i]=='v4' else 'normal')
    axes[0].set_yticks(positions, [LABELS[n] for n in ORDER])
    axes[0].invert_yaxis()
    fig.suptitle('Frozen 256-formula test: all predictions and labels retained', fontsize=13)
    export(fig, out, 'comparator-errors')


def paired(evaluation, out):
    names = ['masterrtl_retrained', 'masterrtl_frozen', 'v2_frozen', 'v3_frozen']
    comps = evaluation['paired_comparisons']
    fig, ax = plt.subplots(figsize=(9.8, 3.3), layout='constrained')
    ax.axvline(0, color='#43576A', ls='--', lw=1)
    for i, name in enumerate(names):
        item = comps[name]
        point = item['macro_stratum_mae_difference_lut4']
        low, high = item['descriptive_paired_bootstrap_95_percentile_interval_lut4']
        color = COLORS[name]
        ax.plot([low, high], [i, i], color=color, lw=3)
        ax.scatter([point], [i], color=color, s=52, zorder=3)
        ax.text(high+1, i, f'{point:+.2f} [{low:+.2f}, {high:+.2f}]', va='center', fontsize=9)
    bounds = [v for name in names for v in comps[name]['descriptive_paired_bootstrap_95_percentile_interval_lut4']]
    span = max(bounds)-min(bounds)
    ax.set_xlim(min(bounds)-span*.05, max(bounds)+span*.44)
    ax.set_yticks(range(len(names)), [LABELS[n] for n in names]); ax.invert_yaxis()
    ax.set_xlabel('V4 MAE minus comparator MAE (LUT4)   |   negative favors V4')
    ax.set_title('Paired MAE difference with descriptive 95% intervals', loc='left', pad=12)
    ax.grid(axis='x'); ax.set_axisbelow(True)
    export(fig, out, 'paired-mae')


def strata(evaluation, out):
    matrix = np.asarray([[evaluation['models'][n]['by_stratum'][s]['mae_lut4'] for n in ORDER]
                         for s in STRATA])
    fig, ax = plt.subplots(figsize=(10.4, 5.7), layout='constrained')
    norm = FuncNorm((np.log1p, np.expm1), vmin=0, vmax=float(matrix.max()))
    image = ax.imshow(matrix, cmap='Blues', norm=norm, aspect='auto')
    ax.set_xticks(range(len(ORDER)), [SHORT[n].replace(' ', '\n') for n in ORDER])
    ax.set_yticks(range(len(STRATA)), [s.replace('_', ' ').capitalize()+' (n=32)' for s in STRATA])
    for row in range(len(STRATA)):
        for column in range(len(ORDER)):
            value = matrix[row, column]
            ax.text(column, row, fmt(value), va='center', ha='center',
                    color='white' if norm(value)>.63 else '#153954', fontsize=10,
                    fontweight='bold' if column==4 else 'normal')
    ax.set_title('MAE by formula stratum (LUT4)', loc='left', pad=14)
    for spine in ax.spines.values(): spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax, fraction=.035, pad=.025)
    ticks = [v for v in (0, 1, 5, 20, 100, 500, 2000) if v <= matrix.max()]
    colorbar.set_ticks(ticks); colorbar.set_label('MAE; log1p color scale')
    export(fig, out, 'stratum-errors')


def scatter(evaluation, out):
    rows = evaluation['models']['v4']['candidate_errors']
    y = np.asarray([r['lut4_count'] for r in rows])
    p = np.asarray([r['predicted_lut4'] for r in rows])
    fig, ax = plt.subplots(figsize=(8, 6.2), layout='constrained')
    colors = plt.get_cmap('tab10').colors
    markers = ('o', 's', '^', 'D', 'v', 'P', 'X', '*')
    for i, s in enumerate(STRATA):
        selected = [j for j, r in enumerate(rows) if r['stratum']==s]
        ax.scatter(np.log1p(y[selected]), np.log1p(p[selected]), s=34,
                   label=s.replace('_', ' '), color=colors[i], marker=markers[i], alpha=.8,
                   edgecolors='white', linewidths=.35)
    limit = max(np.log1p(y).max(), np.log1p(p).max())+.22
    ax.plot([0, limit], [0, limit], '--', lw=1.1, color='#526A7D')
    for axis in (ax.axvline, ax.axhline):
        axis(np.log1p(64), lw=.7, color='#A7B8C5', ls=':')
    ticks = [v for v in (0, 1, 4, 16, 64, 256, 1024, 4096) if np.log1p(v)<=limit]
    ax.set_xticks(np.log1p(ticks), [str(v) for v in ticks])
    ax.set_yticks(np.log1p(ticks), [str(v) for v in ticks])
    ax.set_xlim(-.12, limit); ax.set_ylim(-.12, limit); ax.set_aspect('equal')
    ax.set_xlabel('Measured LUT4 count (log1p coordinates)')
    ax.set_ylabel('V4 predicted LUT4 count (log1p coordinates)')
    ax.set_title('Measured vs V4 prediction: all 256 formulas', loc='left', pad=12)
    worst = np.argsort(np.abs(p-y))[-3:][::-1]
    for rank, i in enumerate(worst, 1):
        ax.annotate(f'#{rank}', (np.log1p(y[i]), np.log1p(p[i])),
                    xytext=(7, 6 if rank!=2 else -12), textcoords='offset points', fontsize=9,
                    fontweight='bold', color='#17354D')
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=False, fontsize=9)
    ax.grid(alpha=.45); ax.set_axisbelow(True)
    export(fig, out, 'v4-scatter')


def table(headers, rows):
    head = ''.join(f'<th>{html.escape(str(h))}</th>' for h in headers)
    body = ''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in row)+'</tr>' for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def image_block(out, name, number):
    svg = (out/f'{name}.svg').read_text()
    svg = svg[svg.index('<svg'):]
    return f'<figure>{svg}<figcaption><b>Figure {number}.</b> {html.escape(CAPTIONS[name])}</figcaption><div class="exports"><a href="{name}.pdf">PDF</a> / <a href="{name}.svg">SVG</a> / <a href="{name}.png">PNG</a></div></figure>'


def runtime_section(runtime, timing):
    text = '<h2>Runtime cost</h2>'
    if runtime is not None:
        text += '<p>Cold preprocessing and cached inference are separate costs. These are elapsed times for this local machine and this fixed batch, not processor acceleration results.</p>'
        rows = []
        for name, d in runtime.get('models', {}).items():
            rows.append([LABELS.get(name, name), fmt(d.get('load_seconds'), 3),
                         fmt(d.get('cold_feature_and_prediction_seconds'), 3),
                         fmt(d.get('warm_median_seconds'), 3),
                         len(d.get('warm_feature_and_prediction_seconds', [])),
                         str(d.get('identical_to_frozen_predictions', 'unreported'))])
        text += table(['Model', 'Load seconds', 'Cold features + prediction seconds',
                       'Warm median seconds', 'Warm repeats', 'Matches frozen predictions'], rows)
        text += '<p class="small">'+html.escape(runtime.get('scope',''))+'</p>'
        text += '<details><summary>Full recorded cold/cached timing measurements</summary><pre>'+html.escape(json.dumps(runtime, indent=2))+'</pre></details>'
    else:
        text += '<p>Cold extraction timing has not been attached to this report. The table below uses pre-extracted features and excludes process startup, model loading, and JSON serialization; it cannot establish a cold-path speedup.</p>'
    text += table(['Model', 'Formulas', 'Recorded seconds', 'Scope'],
        [[SHORT[n], d.get('formula_count', 'n/a'), fmt(d.get('seconds'), 3), d.get('scope', '')]
         for n, d in timing.items()])
    return text


def report_html(evaluation, development, historical, runtime, timing, sources, out):
    models = evaluation['models']; v = models['v4']['pooled']; m = models['masterrtl_retrained']['pooled']
    comparison = evaluation['paired_comparisons']['masterrtl_retrained']
    difference = comparison['macro_stratum_mae_difference_lut4']
    lo, hi = comparison['descriptive_paired_bootstrap_95_percentile_interval_lut4']
    if hi < 0:
        conclusion = 'V4 has lower MAE than retrained MasterRTL in this fixed test.'
    elif lo > 0:
        conclusion = 'V4 has higher MAE than retrained MasterRTL in this fixed test.'
    else:
        conclusion = 'Overall MAE is close; this test does not establish a V4 advantage over retrained MasterRTL.'
    error_rows = []
    for name in ORDER:
        p = models[name]['pooled']; cap=p['cap_feasibility']['64']
        error_rows.append([LABELS[name], fmt(p['mae_lut4']), fmt(p['rmsle'], 3),
            fmt(p['positive_mape_percent']), fmt(p['positive_median_ape_percent']),
            fmt(p['zero_target_mae_lut4']), cap['false_accept_count'], cap['false_reject_count']])
    tradeoffs = (f"V4 MAE is {fmt(v['mae_lut4'])} LUT4 versus {fmt(m['mae_lut4'])}; paired difference "
        f"{difference:+.2f} LUT4, descriptive 95% interval [{lo:+.2f}, {hi:+.2f}]. "
        f"V4 has smaller absolute error on {comparison['v4_smaller_absolute_error_count']}/256 formulas. "
        f"Its positive-label median APE is {fmt(v['positive_median_ape_percent'])}% versus {fmt(m['positive_median_ape_percent'])}%, "
        f"while RMSLE is worse ({fmt(v['rmsle'],3)} versus {fmt(m['rmsle'],3)}) and zero-label MAE is much larger "
        f"({fmt(v['zero_target_mae_lut4'])} versus {fmt(m['zero_target_mae_lut4'],3)} LUT4 across 21 zeros). "
        "Multiplication MAE is also worse. These competing error summaries are all retained.")
    capv=v['cap_feasibility']['64']; capm=m['cap_feasibility']['64']
    captext = (f"At the 64-LUT cap, V4 has {capv['false_accept_count']} false accept and {capv['false_reject_count']} false rejects "
        f"({capv['false_accept_count']+capv['false_reject_count']} total), versus "
        f"{capm['false_accept_count']} and {capm['false_reject_count']} ({capm['false_accept_count']+capm['false_reject_count']} total) "
        "for retrained MasterRTL. A false accept predicts <=64 for a measured count >64; a false reject does the reverse. "
        "There are 192 truly feasible and 64 truly infeasible formulas. This threshold is prespecified, not chosen after scoring.")
    reductions = ', '.join(f"{100*(1-v['mae_lut4']/models[n]['pooled']['mae_lut4']):.2f}% versus {SHORT[n]}" for n in ('v2_frozen','v3_frozen'))
    selected = development.get('selected', 'unknown') if development else 'unknown'
    ablation_rows = [] if not development else [[name, fmt(d['mae_lut4']), fmt(d['macro_stratum_mae_lut4']),
          fmt(d['rmsle'],3), fmt(d['positive_mape_percent'])] for name,d in development['feature_ablations'].items()]
    worst = sorted(models['v4']['candidate_errors'], key=lambda r:r['absolute_error_lut4'], reverse=True)[:10]
    worst_rows = [[f'#{i+1}', r['stratum'].replace('_',' '), fmt(r['lut4_count'],0), fmt(r['predicted_lut4']),
                   fmt(r['absolute_error_lut4']), r['formula']] for i,r in enumerate(worst)]
    limitations = evaluation['limitations'] + [
        'The 192-formula V3 probe is a different cohort and is now part of development; its scores are not directly comparable to the new 256-formula test.',
        'V4 uses normalized pre-ABC graphs, graph features, structural features, and a selected ExtraTrees fit. Retrained MasterRTL uses original pre-ABC counts; both receive the same 1,289 training labels.',
        'Equivalent normalized RTL can map differently from original RTL. The prediction target remains the recorded original-RTL LUT4 count.',
        'Development ablations use a common XGBoost depth-3 fit, not the selected ExtraTrees estimator, and are not new holdout results.',
        'Older CPU/processor integration measurements are historical evidence only; this test contains no new cycle, speedup, ASIC area, or end-to-end workload measurement.',
    ]
    historical_text = '<p>The earlier 192-formula probe is now development evidence. Its MAE values must not be compared numerically to this new 256-formula cohort as a measure of model improvement.</p>'
    if historical:
        historical_text += table(['Historical comparator', 'Old probe MAE (n=192)', 'Old positive MAPE (%)'],
            [[n,fmt(d['pooled']['mae_lut4']),fmt(d['pooled']['positive_mape_percent'])]
             for n,d in historical['models'].items()])
    provenance_rows = [[name, record['path'], record['sha256']] for name,record in sources.items()]
    data = {'evaluation':evaluation, 'development':development, 'historical_192_probe':historical,
            'runtime_cost':runtime, 'timing':timing, 'source_files':sources, 'captions':CAPTIONS}
    embedded = json.dumps(data, separators=(',', ':'), allow_nan=False).replace('<','\\u003c')
    style = '''body{margin:0;background:#edf2f6;color:#203344;font:15px/1.6 system-ui,sans-serif}main{max-width:1140px;margin:32px auto;padding:40px;background:white;border-radius:12px;box-shadow:0 5px 24px #1b344b10}h1{font-size:34px;line-height:1.2;margin:12px 0}h2{font-size:22px;margin:40px 0 12px;border-top:1px solid #e3eaf0;padding-top:24px}.eyebrow{letter-spacing:.14em;font-size:11px;color:#1768ac;font-weight:750;text-transform:uppercase}.lede{font-size:19px;line-height:1.45;max-width:950px}.callout{padding:20px 24px;background:#f1f6fa;border-left:4px solid #1768ac;margin:22px 0}.badge{display:inline-block;background:#e8f1f8;color:#20567e;border-radius:16px;padding:4px 12px;font-size:12px;margin-right:6px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;background:#f3f6f9;color:#34516a;white-space:nowrap}th,td{padding:10px 12px;border-bottom:1px solid #e4eaf0;vertical-align:top}tbody tr:last-child{font-weight:650}td:last-child{overflow-wrap:anywhere}figure{margin:30px 0 36px;padding:18px;border:1px solid #e0e8ef;border-radius:8px}figure svg{display:block;width:100%;height:auto}figcaption{font-size:13px;color:#506374;margin:12px 0}.exports{font-size:12px}a{color:#1768ac}pre{overflow:auto;background:#f5f7fa;padding:16px;font-size:11px;line-height:1.5}details{margin:16px 0}summary{cursor:pointer;font-weight:600}.small{font-size:13px;color:#566d80}li{margin:7px 0}@media(max-width:700px){main{margin:0;padding:22px;border-radius:0}h1{font-size:27px}figure{padding:8px}}@media print{body{background:white}main{box-shadow:none;margin:0;padding:0}.exports{display:none}figure{break-inside:avoid}}'''
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge V4: frozen test results</title><style>{style}</style><main>
    <div class="eyebrow">ISAForge / reproducible evaluation</div><h1>V4 frozen test results</h1>
    <span class="badge">256 new formulas</span><span class="badge">8 strata x 32</span><span class="badge">All zeros and outliers retained</span>
    <p class="lede">{html.escape(conclusion)}</p><div class="callout">{html.escape(tradeoffs)}</div>
    <p>All models were frozen before release of these labels. V4 and retrained MasterRTL use the same 1,289 development formulas; the older frozen comparators use 713. V4's observed MAE reductions are {html.escape(reductions)}. Those reductions combine representation/model changes and extra training data.</p>
    <h2>Complete error summaries</h2>{table(['Model / training cohort','MAE LUT4','RMSLE','Positive MAPE %','Median APE %','Zero MAE LUT4','Cap64 false accepts','Cap64 false rejects'],error_rows)}
    <p class="small">MAE includes all 256 labels. Positive-label percentage errors include all 235 positive labels. Zero MAE uses all 21 zeros. Lower is better for every error metric. No metric is an accuracy percentage.</p>
    <p>{html.escape(captext)}</p>{image_block(out,'comparator-errors',1)}{image_block(out,'paired-mae',2)}
    <h2>Errors across formula families</h2>{image_block(out,'stratum-errors',3)}{image_block(out,'v4-scatter',4)}
    <h2>Largest V4 errors, including zero-label failures</h2>{table(['Rank','Stratum','Measured LUT4','V4 prediction','Absolute error','Formula'],worst_rows)}
    <h2>Development-only feature ablations</h2><p>The selected configuration is <b>{html.escape(selected)}</b>: ExtraTrees with 300 trees and minimum leaf size 1, fitted on raw LUT4 labels. Selection uses grouped development folds; these scores are development evidence, not an unbiased new test.</p>
    {table(['Feature set, fixed depth-3 XGBoost','Pooled MAE','Macro-stratum MAE','RMSLE','Positive MAPE %'],ablation_rows)}
    <p class="small">These ablations hold the XGBoost estimator fixed. They do not isolate the contribution of features to the final ExtraTrees fit. The development macro average includes the workload group and differs from the test's eight equally sized strata.</p>
    <h2>Historical evidence, separate cohort</h2>{historical_text}<p class="small">Earlier CPU results are not repeated as new results here: the present experiment measures isolated original-RTL LUT4 prediction only.</p>
    {runtime_section(runtime,timing)}
    <h2>Scope and limitations</h2><ul>{''.join('<li>'+html.escape(x)+'</li>' for x in limitations)}</ul>
    <h2>Provenance and export</h2><p class="small">Figure data, captions, source hashes, and every candidate-level prediction are embedded in this HTML and available in report-data.json. PDF, SVG, and PNG exports accompany each figure. SVG identifiers and metadata are deterministic.</p>
    {table(['Source','Recorded path','SHA-256'],provenance_rows)}
    <details><summary>Frozen evaluation provenance</summary><pre>{html.escape(json.dumps(evaluation['provenance'],indent=2))}</pre></details>
    <script type="application/json" id="report-data">{embedded}</script></main></html>'''
    (out/'report.html').write_text(content)
    (out/'report-data.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', required=True, type=Path)
    parser.add_argument('--out', '--output-dir', '--output', required=True, type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--historical', type=Path)
    parser.add_argument('--runtime-cost', type=Path)
    parser.add_argument('--wait-seconds', type=float, default=0)
    args = parser.parse_args()
    deadline = time.monotonic()+args.wait_seconds
    while not args.evaluation.exists() and time.monotonic()<deadline:
        time.sleep(min(2,max(0,deadline-time.monotonic())))
    evaluation = read(args.evaluation)
    if evaluation.get('schema')!='isaforge-v4-evaluation-v1' or evaluation.get('evaluation_status')!='complete frozen holdout':
        raise ValueError('A complete independently scored V4 frozen evaluation is required')
    if set(evaluation['models']) != set(ORDER) or evaluation['holdout_formula_count']!=256:
        raise ValueError('Report requires all five preregistered models and all 256 formulas')
    for model in evaluation['models'].values():
        if len(model['candidate_errors'])!=256 or model['pooled']['sample_count']!=256:
            raise ValueError('Partial cohorts cannot be rendered as a complete test')
    base = args.evaluation.resolve().parent
    paths = {'evaluation':args.evaluation.resolve(),
             'development': args.development or base/'development-evaluation.json',
             'historical_192_probe':args.historical or base.parent/'2026-10-13-v3'/'probe-evaluation.json',
             'runtime_cost':args.runtime_cost or base/'runtime-cost.json'}
    optional = {name:read(p) if p.exists() else None for name,p in paths.items() if name!='evaluation'}
    timing = {}
    for name in ORDER:
        p=base/'predictions'/f'{name}.timing.json'
        if p.exists(): timing[name]=read(p); paths[f'timing_{name}']=p
    paths['report_script']=Path(__file__).resolve()
    sources = {n:{'path':str(p.resolve()),'sha256':sha(p)} for n,p in paths.items() if p.exists()}
    args.out.mkdir(parents=True, exist_ok=True)
    configure()
    comparators(evaluation,args.out); paired(evaluation,args.out)
    strata(evaluation,args.out); scatter(evaluation,args.out)
    report_html(evaluation, optional['development'], optional['historical_192_probe'],
                optional['runtime_cost'],timing,sources,args.out)
    exports = {p.name:sha(p) for p in sorted(args.out.iterdir()) if p.is_file() and p.name!='manifest.json'}
    manifest = {'schema':'isaforge-v4-report-v1','sources':sources,'exports_sha256':exports,
                'figure_captions':CAPTIONS,'matplotlib_version':matplotlib.__version__,
                'figure_data':'report-data.json','cohort':'all256frozennewtestformulas'}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'out':str(args.out.resolve()),'figures':4,'test_formulas':256,'runtime_cost_attached':optional['runtime_cost'] is not None}))


if __name__=='__main__':
    main()
