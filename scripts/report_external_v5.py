#!/usr/bin/env python3
"""Render complete external-transfer scores without fitting or selecting models."""
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
LABELS = ('V4 frozen', 'Fixed MasterRTL recipe', 'Equally tuned SOG', 'SOG + original graph', 'SOG + dual graphs', 'Dual graphs + semantics')
COLORS = ('#81909E', '#B27A4B', '#49697F', '#6AA0AF', '#3E8D83', '#17699C')
FAMILIES = ('graph_shortest_paths', 'speech_codec', 'multiset_word_search')


def table(headers, rows):
    cell = lambda tag, value: f'<{tag}>'+html.escape(str(value))+f'</{tag}>'
    return '<div class="table"><table><tr>'+''.join(cell('th', h) for h in headers)+'</tr>'+''.join('<tr>'+''.join(cell('td', v) for v in row)+'</tr>' for row in rows)+'</table></div>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.evaluation.read_text())
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42,
                         'svg.hashsalt': 'isaforge-external-v5'})
    figures = []

    def save(fig, name, caption):
        for ext in ('png', 'svg', 'pdf'):
            metadata = {'Date': None} if ext == 'svg' else {'CreationDate': None, 'ModDate': None} if ext == 'pdf' else {}
            fig.savefig(out/f'{name}.{ext}', dpi=250, bbox_inches='tight', metadata=metadata)
        plt.close(fig)
        svg = (out/f'{name}.svg').read_text()
        figures.append('<figure>'+svg[svg.index('<svg'):]+'<figcaption>'+caption+f' <a href="{name}.pdf">PDF</a> · <a href="{name}.svg">SVG</a></figcaption></figure>')

    values = [data['models'][n]['all']['macro_family_mae_lut4'] for n in ORDER]
    fig, ax = plt.subplots(figsize=(10, 4.4), layout='constrained')
    ax.barh(range(6), values, color=COLORS)
    ax.set_yticks(range(6), LABELS); ax.invert_yaxis()
    ax.set_xlim(0, max(values)*1.2)
    for i, v in enumerate(values):
        ax.text(v+max(values)*.015, i, f'{v:.3f}', va='center')
    ax.set_xlabel('Equal-weight mean of three family MAEs (LUT4)')
    ax.set_title('External application-derived circuits: frozen model comparison', loc='left')
    ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
    save(fig, 'external-primary', 'All 80 program/formula occurrences remain: Dijkstra 5, ADPCM 47, anagram 28; 79 unique circuits measured. Each family contributes one third of the primary score. Familiar circuits are included and identified separately. These are three curated families, not population confidence intervals.')

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3), sharey=True, layout='constrained')
    for ax, family, title in zip(axes, FAMILIES, ('Dijkstra (5 circuits)', 'ADPCM decoding (47 circuits)', 'Anagram search (28 circuits)')):
        values = [data['models'][n]['all']['by_family'][family]['mae_lut4'] for n in ORDER]
        ax.barh(range(6), values, color=COLORS); ax.set_xlim(0, max(max(values)*1.25, .1))
        for i, v in enumerate(values):
            ax.text(v+max(max(values), .1)*.025, i, f'{v:.2f}', va='center', fontsize=9)
        ax.set_title(title, loc='left'); ax.set_xlabel('MAE (LUT4)')
        ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
    axes[0].set_yticks(range(6), LABELS); axes[0].invert_yaxis()
    save(fig, 'external-families', 'Horizontal scales differ by family. Dijkstra candidate discovery uses one path; its full 20-path correctness controls run outside the trace window. ADPCM is the exact pinned two-code instance. Anagram witnesses are checked for all three phrases. No CPU cycles or speedup are measured here.')

    full = data['models']['dual_semantics']['all']['macro_family_mae_lut4']
    sog = data['models']['sog_tuned']['all']['macro_family_mae_lut4']
    delta = data['paired_comparisons']['all']['macro_family_mae_difference_lut4']
    body = '<p class="eyebrow">ISAForge • Frozen external transfer</p><h1>From synthetic circuits to application-derived inputs</h1>'
    body += f'<p>The preregistered full-V5 model has <strong>{full:.3f} LUT4 family-macro MAE</strong>, versus {sog:.3f} for equally tuned SOG. The signed difference is <strong>{delta:+.3f} LUT4</strong>; negative favors full V5. All six artifacts were frozen earlier, with no retraining or recalibration for these applications.</p>'
    best = min(ORDER, key=lambda n: data['models'][n]['all']['macro_family_mae_lut4'])
    body += f'<p><strong>{LABELS[ORDER.index(best)]}</strong> has the lowest observed primary error, {data["models"][best]["all"]["macro_family_mae_lut4"]:.3f} LUT4. The primary comparator remains equally tuned SOG. Rankings across these curated families do not establish published-system superiority.</p>'
    body += ''.join(figures)
    fmt = lambda v: 'unavailable' if v is None else f'{v:.3f}'
    a = data['models']['dual_semantics']['all']
    body += f'<p>Positive MAPE uses all {a["positive_count"]} positive targets; all {a["zero_count"]} zero targets remain in MAE, RMSLE and feasibility metrics.</p>'
    body += '<h2>All frozen models and scopes</h2>'+table(['Predictor', 'All-family macro MAE', 'Pooled 80-row MAE', 'Pooled positive MAPE (%)', 'Formula-novel macro MAE', 'Strict-novel macro MAE'], [[label, fmt(data['models'][n]['all']['macro_family_mae_lut4']), fmt(data['models'][n]['all']['mae_lut4']), fmt(data['models'][n]['all']['positive_mape_percent']), fmt(data['models'][n]['formula_novel']['macro_family_mae_lut4']), fmt(data['models'][n]['strict_novel']['macro_family_mae_lut4'])] for n, label in zip(ORDER, LABELS)])
    body += '<h2>Input overlap is explicit</h2><p>Novelty is fixed against all 2,313 consumed formulas before external labels. Formula novelty excludes exact, normalized and full-feature matches. Strict novelty additionally excludes original and normalized skeleton matches. If any family is absent, its three-family subset macro is unavailable.</p>'+table(['Subset', 'Rows', 'Family counts', 'Status'], [[scope, data['models']['dual_semantics'][scope]['row_count'], data['models']['dual_semantics'][scope]['family_counts'], data['models']['dual_semantics'][scope]['status']] for scope in ('all', 'formula_novel', 'strict_novel')])
    bound_rows = []
    for name, label in zip(ORDER, LABELS):
        bounds = data['models'][name].get('frozen_bound_diagnostics')
        if bounds is None:
            continue
        b = bounds['all']
        bound_rows.append([label, f"{b['finite_bound_count']}/{b['row_count']}",
                           fmt(100*b['observed_candidate_coverage']) if b['observed_candidate_coverage'] is not None else 'unavailable',
                           fmt(b['mean_slack_lut4']), fmt(b['minimum_slack_lut4']),
                           b['outside_feature_range_rows'], f"{bounds['whole_family_coverage_count']}/3"])
    body += '<h2>Frozen upper bounds under application shift</h2><p>These are observed candidate diagnostics without recalibration. The three application families differ from the calibration groups, so neither candidate coverage nor whole-family counts establish a 90% guarantee. Feature-range checks can miss unfamiliar feature combinations.</p>'+table(['Predictor', 'Finite bounds', 'Candidate coverage (%)', 'Mean slack (LUT4)', 'Worst slack (LUT4)', 'Feature-range OOD rows', 'Families fully covered'], bound_rows)
    rows = sorted(data['models']['dual_semantics']['candidate_errors'], key=lambda r: r['absolute_error_lut4'], reverse=True)[:10]
    body += '<h2>Largest full-V5 errors</h2>'+table(['Family', 'Formula', 'Measured LUT4', 'Prediction', 'Absolute error'], [[r['family'], r['formula'], r['lut4_count'], fmt(r['predicted_lut4']), fmt(r['absolute_error_lut4'])] for r in rows])
    body += '<h2>Limits</h2><p>Three curated program families, small pinned inputs, repeated formulas and a partial Dijkstra trace limit generalization. All cases remain in the primary endpoint. A subset score does not replace the frozen primary comparison. This study measures isolated original-RTL FPGA resources; it establishes no modified-CPU correctness, acquisition savings, board timing or application speedup. Source attribution and correctness scope follow the pinned <a href="https://github.com/tacle/tacle-bench/tree/c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08">TACLeBench source</a> and the repository protocol.</p><p><a href="report-data.json">All metrics and candidate errors</a> · <a href="provenance.json">Provenance</a></p>'
    css = 'body{font:16px/1.6 system-ui;color:#20394b;background:#f5f7f9}main{max-width:1150px;margin:auto;padding:38px;background:white}h1{font-size:34px;line-height:1.2}h2{margin-top:34px;color:#185372}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:1px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px;border-bottom:1px solid #dce4ea;text-align:left;overflow-wrap:anywhere}th{background:#edf4f8}figure{margin:28px 0}figure svg{width:100%;height:auto}figcaption{font-size:13px;color:#536d7e}a{color:#096b9c}'
    (out/'report.html').write_text('<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge external transfer</title><style>'+css+'</style><main>'+body+'</main></html>')
    (out/'report-data.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({'evaluation_sha256': hashlib.sha256(args.evaluation.read_bytes()).hexdigest(), 'report_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'freeze_sha256': data['freeze_sha256'], 'all_rows_retained': True}, indent=2)+'\n')
    print(out/'report.html')


if __name__ == '__main__':
    main()
