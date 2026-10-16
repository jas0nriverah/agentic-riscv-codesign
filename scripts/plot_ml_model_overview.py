#!/usr/bin/env python3
"""Vector overview of the retained area model and its measured improvement loop."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V9 = ROOT / 'results/2026-10-15-v9-coverage-development'
V13 = ROOT / 'results/2026-10-15-v13b-coverage-recovery'


def need(condition, message):
    if not condition: raise ValueError(message)


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    path = Path(path).resolve()
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def write(path, value):
    with Path(path).open('x') as stream: json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def source_data(v13_summary=None):
    model_path = V9 / 'fit-attempt-0000/models/mapping-coverage.json'
    model = read(model_path)
    need(model['training_formula_count'] == 1713 and len(model['feature_columns']) == 336 and len(model['mapping_columns']) == 217
         and model['fitted_parameters']['n_estimators'] == 300, 'Retained V9 model recipe differs')
    groups_path = V13 / 'fitting/groups.json'; prep_path = V13 / 'fitting/preparation.json'; groups = read(groups_path); prep = read(prep_path)
    need(prep['rows'] == 1761 and prep['old_rows'] == 1713 and prep['new_rows'] == 48 and prep['maximum_fits'] == 30, 'Current comparison input counts differ')
    group_count = len(groups['components']); need(group_count == 538, 'Current joint closure differs')
    sources = [Path(__file__), model_path, groups_path, prep_path, ROOT / 'isaforge/area_model_v6.py', ROOT / 'isaforge/area_model_v5.py',
               ROOT / 'docs/v6-results.md', ROOT / 'docs/v9-coverage-results.md', ROOT / 'docs/v12-target-transform-results.md', ROOT / 'docs/v13-coverage-protocol.md']
    experiment = {'status': 'pending', 'rows': 1761, 'old_primary_rows': 1713, 'new_secondary_rows': 48, 'joint_groups': group_count,
                  'folds': 5, 'paired_seeds': 3, 'variants': 2, 'fits': 30, 'promoted': False,
                  'card_headline': 'Comparison in progress', 'card_detail': '1,761 joint rows; not promoted'}
    if v13_summary is not None:
        path = Path(v13_summary).resolve(); done_path = path.parent / 'completion.json'; done = read(done_path); summary = read(path)
        need(done['complete'] is True and done['fits_completed'] == done['fits_attempted'] == 30 and sha(path) == done['summary_sha256']
             and summary['schema'] == 'isaforge-v13-matched-coverage-comparison-v1', 'Completed actual V13 summary required')
        primary = summary['primary_augmented_minus_control_original1713_macro_mae_lut4']
        control = sum(s['original1713']['macro_stratum_mae_lut4'] for s in summary['scores']['control'].values()) / 3
        percent = 100 * primary['mean'] / control
        coverage_control = sum(s['coverage48']['pooled']['mae_lut4'] for s in summary['scores']['control'].values()) / 3
        coverage_augmented = sum(s['coverage48']['pooled']['mae_lut4'] for s in summary['scores']['augmented'].values()) / 3
        coverage_percent = 100 * (coverage_augmented - coverage_control) / coverage_control
        experiment.update(status='completed-development', primary_delta_lut4=primary['mean'], primary_delta_percent=percent,
                          new48_mae_control=coverage_control, new48_mae_augmented=coverage_augmented, new48_delta_percent=coverage_percent,
                          card_headline=f'Old MAE {percent:+.2f}%', card_detail=f'New 48 MAE {coverage_percent:+.2f}%\nNot promoted · V9 retained')
        sources.extend([path, done_path])
    return {'schema': 'isaforge-ml-model-overview-data-v1', 'retained_model': {'version': 'V9 coverage', 'labeled_originals': 1713, 'full_columns': 336,
            'selected_columns': 217, 'trees': 300, 'estimator': 'ExtraTreesRegressor', 'target': 'Original isolated combinational iCE40 LUT4',
            'feature_breakdown': {'SOG': 14, 'original_graph': 60, 'normalized_graph': 60, 'absolute_graph_differences': 60, 'mapping_descriptors': 23},
            'zero_override': 'Only original generic gate count zero forces point zero', 'uncertainty': 'Uncalibrated point estimate'},
            'experiment': experiment, 'history': [
                {'version': 'V6', 'cohort': 'Fresh structural-family holdout', 'metric': 'Equal-stratum MAE', 'change_percent': -6.32, 'sample_count': 192, 'status': 'Feature improvement within declared grammar'},
                {'version': 'V9', 'cohort': 'Consumed V8 applications', 'metric': 'Equal-family MAE', 'change_percent': -25.40, 'sample_count': 146, 'status': 'Coverage improvement on development applications'},
                {'version': 'V12', 'cohort': 'Consumed1713 grouped OOF', 'metric': 'Equal-nine-stratum MAE', 'change_percent': 4.77, 'status': 'Log target rejected; raw target retained'}],
            'history_scope': 'Different cohorts and comparisons. These percentages do not form a common accuracy trend.',
            'scope': 'Isolated LUT4 area prediction and targeted consumed-development model comparison; no hardware timing, power, CPU speedup, calibrated safety or independent-transfer claim.',
            'source_sha256': [record(p) for p in dict.fromkeys(sources)]}


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'isaforge-ml-overview'})
    fig, ax = plt.subplots(figsize=(20, 14.7)); ax.set_xlim(0, 20); ax.set_ylim(0, 14.7); ax.axis('off')
    fig.patch.set_facecolor('#F3F6FA'); ax.set_facecolor('#F3F6FA'); fig.subplots_adjust(0, 0, 1, 1)
    navy, muted, blue, teal, border = '#192D45', '#506179', '#246EA6', '#1B8B89', '#D9E2ED'
    def text(x, y, value, size=12, color=navy, weight='normal', **kwargs):
        kwargs.setdefault('va', 'top')
        return ax.text(x, y, value, fontsize=size, color=color, fontweight=weight, **kwargs)
    def panel(x, y, w, h, face='white', edge=border, rounding=.17):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0.015,rounding_size={rounding}', linewidth=1.2, edgecolor=edge, facecolor=face, zorder=1))
    def pill(x, y, w, h, label, face='#E6EFF8', color=blue, size=11):
        panel(x, y, w, h, face=face, edge=face, rounding=h / 2)
        text(x + w / 2, y + h / 2, label, size, color, 'bold', ha='center', va='center')
    def arrow(x1, y1, x2, y2, color=blue, style='solid', lw=1.9):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=16, linewidth=lw, color=color, linestyle=style, zorder=2))
    text(.48, 14.22, 'ISAForge  /  how our area model works', 28, weight='bold')
    text(.5, 13.64, 'A tree ensemble turns an instruction formula into an estimate of isolated FPGA logic cost.', 15, muted)
    pill(12.1, 13.0, 7.4, .42, 'RETAINED MODEL  ·  V9  ·  1,713 labeled originals', face='#E0F0EF', color='#126E6C', size=12)
    text(.5, 13.08, 'THE PREDICTION PATH', 11, muted, 'bold')
    xs = [.48, 4.1, 8.2, 12.5, 16.2]; widths = [3.08, 3.55, 3.75, 3.15, 3.32]
    for x, w in zip(xs, widths): panel(x, 8.73, w, 3.86)
    for x1, x2 in zip([3.56, 7.65, 11.95, 15.65], [4.1, 8.2, 12.5, 16.2]): arrow(x1 + .05, 10.55, x2 - .05, 10.55)
    for x, title in zip(xs, ['1  Formula', '2  Graph views', '3  Fixed features', '4  Tree ensemble', '5  Area estimate']): text(x + .22, 12.28, title, 15, weight='bold')
    text(.72, 11.72, 'RV32 computation\nwith shared inputs', 13, muted)
    panel(.72, 10.15, 2.6, 1.03, face='#F0F4F9', edge='#F0F4F9', rounding=.1)
    text(.9, 10.96, 'add(\n  mul(in0,addi(0,341)),\n  in1)', 10.8, '#304C6B', family='DejaVu Sans Mono')
    text(.73, 9.78, 'Only the formula enters\nfeature extraction.\nNo observed area or residual.', 11.5, muted, linespacing=1.65)
    text(4.33, 11.72, 'Yosys generic lowering\nbefore target ABC mapping', 12.5, muted)
    # A small graph icon conveys dataflow, not a learned graph network.
    nodes = [(4.68, 10.5), (5.42, 10.83), (5.42, 10.15), (6.22, 10.5), (6.94, 10.5)]
    for a, b in ((0, 1), (0, 2), (1, 3), (2, 3), (3, 4)): arrow(*nodes[a], *nodes[b], color='#7B9EB9', lw=1.1)
    for i, (x, y) in enumerate(nodes): ax.add_patch(Circle((x, y), .105, facecolor=teal if i in (0, 4) else blue, edgecolor='white', linewidth=1, zorder=3))
    text(4.33, 9.82, 'Original DAG\nNormalized DAG\nSOG structural descriptors', 12, muted, linespacing=1.55)
    text(8.45, 11.75, '217', 35, blue, 'bold'); text(9.77, 11.65, 'selected columns\nfrom 336 computed', 12, muted, linespacing=1.45)
    text(8.46, 10.7, '14   SOG\n60   Original graph\n60   Normalized graph\n60   Absolute graph differences\n23   Mapping descriptors', 11.5, muted, linespacing=1.7)
    text(12.75, 11.73, 'ExtraTreesRegressor', 12.5, muted, 'bold')
    # Three representative trees; the label gives the true ensemble size.
    for cx in (13.05, 13.9, 14.75):
        for start, end in (((cx, 10.85), (cx - .21, 10.48)), ((cx, 10.85), (cx + .21, 10.48)), ((cx - .21, 10.48), (cx - .33, 10.13)), ((cx - .21, 10.48), (cx - .08, 10.13))):
            ax.plot([start[0], end[0]], [start[1], end[1]], color='#6F92B1', lw=1.3)
        for x, y in ((cx, 10.85), (cx - .21, 10.48), (cx + .21, 10.48), (cx - .33, 10.13), (cx - .08, 10.13)):
            ax.add_patch(Circle((x, y), .055, facecolor=blue, zorder=3))
    text(12.77, 9.83, '300 randomized trees\nRaw LUT4 training target\nAverage tree predictions', 11.9, muted, linespacing=1.6)
    text(16.46, 11.74, 'Predicted LUT4', 21, blue, 'bold')
    text(16.46, 11.13, 'Isolated combinational\niCE40 datapath area', 12.5, muted, linespacing=1.5)
    text(16.46, 10.27, 'max(0, forest mean)', 11.5, navy, family='DejaVu Sans Mono')
    panel(16.44, 9.24, 2.84, .64, face='#E8F3F2', edge='#E8F3F2', rounding=.1)
    text(16.58, 9.76, 'Original generic gates =0\nforces the returned point to 0', 10.5, '#126E6C', linespacing=1.45)
    text(16.46, 9.04, 'Point estimate · uncalibrated', 10.5, muted)
    # Labels enter fitting, not the prediction feature path.
    panel(.48, 7.05, 19.04, 1.15, face='#E9EFF7', edge='#D7E2EE')
    pill(.72, 7.64, 2.18, .32, 'TRAINING LABELS', face='#D9E7F4', size=10)
    text(3.1, 7.93, 'Verified original RTL', 14, weight='bold'); arrow(7.1, 7.71, 7.6, 7.71)
    text(7.83, 7.93, 'Yosys iCE40 synthesis', 14, weight='bold'); arrow(12.05, 7.71, 12.55, 7.71)
    text(12.78, 7.93, 'Count original LUT4', 14, weight='bold')
    text(3.1, 7.42, 'V13 batch: 48 originals × 2,148 sample comparisons; all 48 original labels independently audited.', 11.7, muted)
    arrow(14.15, 8.22, 14.15, 8.68, color=teal, style='dashed'); text(14.45, 8.56, 'fit', 10.5, '#126E6C')
    text(.5, 6.7, 'HOW WE IMPROVE IT  /  MEASURE, COMPARE, THEN DECIDE', 11, muted, 'bold')
    improvement = [
        ('Diagnose a mechanism', 'Correlated high products\nAffine chains\nComparator/shift compositions'),
        ('Add 48 training originals', 'Fixed before measurements\nVerified original-RTL targets\nAll outcomes and failures retained'),
        ('Run a matched comparison', '538 jointly closed groups\n5 folds × 3 seeds × 2 variants\n30 fits; shared held-out groups'),
        ('Retain or adopt on evidence', 'Old 1,713-row macro MAE primary\nCap64 FA/FR + P99 + worst underprediction\nNew 48 are secondary challenges')]
    for i, (title, body) in enumerate(improvement):
        x = .48 + i * 4.84; panel(x, 4.25, 4.5, 2.06, face='white')
        pill(x + .18, 5.72, .34, .34, str(i + 1), face='#DDEEF0', color='#126E6C', size=11)
        text(x + .68, 6.02, title, 13, weight='bold'); text(x + .23, 5.37, body, 11.8, muted, linespacing=1.65)
        if i < 3: arrow(x + 4.54, 5.27, x + 4.79, 5.27, color=teal, lw=1.5)
    text(.5, 3.89, 'EVIDENCE CARDS  /  DIFFERENT COHORTS, NOT ONE ACCURACY TREND', 11, muted, 'bold')
    cards = [
        ('V6 · fresh holdout', 'MAE −6.32%', '192 newly measured circuits\nFeature change within its grammar', '#E6F1ED', '#287459'),
        ('V9 · consumed applications', 'MAE −25.40%', 'Examined application families\nDevelopment coverage improved', '#E5F0F7', '#246EA6'),
        ('V12 · log target rejected', 'MAE +4.77%', 'Grouped 1,713-row OOF comparison\nRaw target retained', '#F8EBE6', '#AC5841'),
        ('V13 · targeted coverage', data['experiment']['card_headline'], data['experiment']['card_detail'], '#EBEDF8', '#5B63A2')]
    for i, (title, headline, detail, face, accent) in enumerate(cards):
        x = .48 + i * 4.84; panel(x, 1.22, 4.5, 2.25, face=face, edge=face)
        text(x + .22, 3.2, title, 13, accent, 'bold'); text(x + .22, 2.7, headline, 22 if i < 3 else 17, accent, 'bold')
        text(x + .22, 2.07, detail, 11.4, muted, linespacing=1.6)
    text(.5, .84, 'Retained V9: 1,713 labeled originals · 217 selected features · 300 trees. V13 improved its new coverage cohort but regressed the old primary; V9 stays retained.', 11.5, navy)
    text(.5, .43, 'Area of isolated original RTL only. These results do not establish CPU speed, routed timing, power, calibrated safety or independent application transfer. Full data/provenance: figure-data.json.', 10.5, muted)
    files = []
    for extension in ('png', 'svg', 'pdf'):
        path = output / ('ml-model-overview.' + extension)
        fig.savefig(path, dpi=220, bbox_inches='tight', pad_inches=.15, metadata={'CreationDate': None, 'ModDate': None} if extension == 'pdf' else None); files.append(path)
    plt.close(fig); return files, matplotlib.__version__


def run(output, v13_summary=None):
    output = Path(output).resolve(); need(not output.exists(), 'Fresh overview output directory required')
    data = source_data(v13_summary); before = {ROOT / r['path']: r['sha256'] for r in data['source_sha256']}
    output.mkdir(parents=True); write(output / 'figure-data.json', data); files, version = render(data, output)
    need(all(sha(p) == h for p, h in before.items()), 'Diagram sources changed during rendering')
    result = {'schema': 'isaforge-ml-model-overview-manifest-v1', 'matplotlib_version': version, 'data': record(output / 'figure-data.json'),
              'files': [record(p) for p in files], 'native_jobs': 0, 'model_imports_or_fits': 0, 'scope': data['scope']}
    write(output / 'figure-manifest.json', result); return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True); p.add_argument('--v13-summary', type=Path)
    args = p.parse_args(); print(json.dumps(run(args.output, args.v13_summary), indent=2))
