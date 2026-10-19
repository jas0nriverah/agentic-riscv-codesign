#!/usr/bin/env python3
"""Present completed V8 results without changing evaluation or frozen evidence.

Produces PNG/SVG/PDF figures plus hash-bound source and figure-data manifests.
Run only after the measurement-completion and evaluation notifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

MODELS = ('mapping_v6', 'legacy_original336', 'legacy_rewritten336',
          'dual_graph', 'sog_tuned', 'masterrtl_fixed')
NAMES = {'mapping_v6': 'Mapping V6 · baseline',
         'legacy_original336': 'Legacy original',
         'legacy_rewritten336': 'Legacy rewritten · primary',
         'dual_graph': 'Dual graph', 'sog_tuned': 'SOG tuned',
         'masterrtl_fixed': 'MasterRTL fixed'}
COLORS = {'mapping_v6': '#D17822', 'legacy_original336': '#7A5195',
          'legacy_rewritten336': '#126B9B', 'dual_graph': '#008477',
          'sog_tuned': '#BA536D', 'masterrtl_fixed': '#656D78',
          'merit': '#28333E', 'frequency': '#9A7E35', 'random': '#8694A3'}
CHALLENGER, BASELINE = 'legacy_rewritten336', 'mapping_v6'
FOOTNOTE = ('Four primary source families; descriptive fixed-cohort results, no population confidence intervals. '
            'Benefit and regret use an overlap-safe retired-instruction-count proxy; no CPU speedup claim.')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def configure():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.titlesize': 12, 'axes.labelsize': 11,
                         'xtick.labelsize': 10, 'ytick.labelsize': 10,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white',
                         'savefig.facecolor': 'white', 'axes.axisbelow': True})
    return plt


def footer(fig, extra=''):
    fig.text(.035, .026, FOOTNOTE + ('\n' + extra if extra else ''),
             fontsize=9, color='#48515C', va='bottom')


def save(fig, stem, output):
    paths = []
    for extension in ('png', 'svg', 'pdf'):
        path = output / (stem + '.' + extension)
        fig.savefig(path, dpi=220, bbox_inches='tight', pad_inches=.18)
        paths.append(path)
    return paths


def horizontal(ax, labels, values, colors, *, signed=False, formatter=None):
    ax.barh(range(len(values)), values, color=colors, height=.66)
    ax.set_yticks(range(len(values)), labels)
    ax.invert_yaxis()
    ax.grid(axis='x', color='#E2E6EA', linewidth=.7)
    if signed:
        low, high = min(0, min(values)), max(0, max(values))
        span = max(high - low, 1)
        ax.set_xlim(low - .17 * span, high + .2 * span)
        ax.axvline(0, color='#28333E', linewidth=1)
    else:
        ax.set_xlim(0, max(max(values) * 1.3, .1))
    distance = (ax.get_xlim()[1] - ax.get_xlim()[0]) * .018
    for i, value in enumerate(values):
        label = formatter(value) if formatter else f'{value:.2f}'
        ax.text(value + (distance if value >= 0 else -distance), i, label,
                ha='left' if value >= 0 else 'right', va='center', fontsize=10)


def errors_figure(evaluation, plt, output):
    scores, primary = evaluation['scores'], evaluation['primary']
    families = list(primary['paired_family_differences_lut4'])
    assert len(families) == 4
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 6.2),
                             gridspec_kw={'width_ratios': [1.16, 1, 1]})
    fig.subplots_adjust(left=.13, right=.97, top=.79, bottom=.24, wspace=.53)
    fig.suptitle('V8 application transfer: frozen point-prediction error', fontsize=19, x=.035, ha='left', y=.98)
    fig.text(.035, .89, 'Primary contrast: legacy rewritten − mapping V6. Negative MAE differences favor rewritten.', fontsize=11)
    macro = [scores[m]['primary_equal_family_mae_lut4'] for m in MODELS]
    horizontal(axes[0], [NAMES[m] for m in MODELS], macro, [COLORS[m] for m in MODELS])
    axes[0].set_title('A  All six models · family-macro MAE', loc='left', pad=18)
    axes[0].set_xlabel('Mean absolute error (LUT4) ↓')
    delta = primary['paired_family_differences_lut4']
    labels = families + ['Equal-family mean']
    values = [delta[f] for f in families] + [primary['difference_lut4']]
    horizontal(axes[1], labels, values, ['#90B7C9'] * 4 + [COLORS[CHALLENGER]], signed=True)
    axes[1].set_title('B  Four paired family differences', loc='left', pad=18)
    axes[1].set_xlabel('Rewritten − baseline MAE (LUT4)')
    leave = primary['leave_one_family_out_difference_lut4']
    horizontal(axes[2], ['Omit ' + f for f in families], [leave[f] for f in families],
               ['#708D9D'] * 4, signed=True)
    axes[2].axvline(primary['difference_lut4'], color=COLORS[CHALLENGER], linestyle=':', linewidth=1.6,
                    label='All-four-family mean')
    axes[2].legend(loc='lower right', fontsize=9, frameon=False)
    axes[2].set_title('C  Leave-one-family-out sensitivity', loc='left', pad=18)
    axes[2].set_xlabel('Mean difference in remaining 3 families')
    footer(fig, 'All six comparisons are shown. Panels B–C are the declared primary contrast; other model comparisons are secondary.')
    return save(fig, 'v8-error-and-family-sensitivity', output)


def selection_figure(evaluation, plt, output):
    selection = evaluation['selection']
    assert selection['primary_cap_lut4'] == 64 and selection['primary_attempt_budget'] == 1
    aggregates = selection['aggregates']
    policies = [(m, 'predicted_area_feasible_merit', NAMES[m]) for m in MODELS]
    policies += [(BASELINE, s, label) for s, label in (('merit', 'Merit only'),
                 ('frequency', 'Frequency only'), ('random', 'Random · mean of 5 seeds'))]

    def entry(model, strategy, budget):
        return aggregates[f'{model}/{strategy}/cap64/budget{budget}']

    # The three public baselines must be independent of predictor identity.
    for strategy in ('merit', 'frequency', 'random'):
        for budget in (1, 3, 5):
            expected = entry(BASELINE, strategy, budget)['primary_equal_family_normalized_regret_percent']
            assert all(entry(m, strategy, budget)['primary_equal_family_normalized_regret_percent'] == expected for m in MODELS)
    values = [entry(m, s, 1)['primary_equal_family_normalized_regret_percent'] for m, s, _ in policies]
    colors = [COLORS[m if s == 'predicted_area_feasible_merit' else s] for m, s, _ in policies]
    fig, axes = plt.subplots(1, 2, figsize=(15.8, 8), gridspec_kw={'width_ratios': [1.15, 1]})
    fig.subplots_adjust(left=.20, right=.97, top=.79, bottom=.20, wspace=.3)
    fig.suptitle('V8 measurement-budget selection: instruction-count regret', fontsize=18, x=.035, ha='left', y=.98)
    fig.text(.035, .89, 'Cap 64 LUT4 · measured feasibility required · lower regret is better · baseline saved instructions = 0', fontsize=11)
    horizontal(axes[0], [label for _, _, label in policies], values, colors,
               formatter=lambda value: f'{value:.3f}%')
    axes[0].axhline(5.5, color='#B8C1C9', linewidth=.8)
    axes[0].set_xlabel('Family-macro regret (% of trace instructions) ↓')
    axes[0].set_title('A  Primary endpoint · one attempted candidate', loc='left', pad=18)
    # A full-value table exposes overlaps and losers without hidden curves or
    # truncated axes. Each cell is the fixed equal-family summary at its budget.
    axes[1].axis('off')
    table_values = [[f"{entry(m, s, b)['primary_equal_family_normalized_regret_percent']:.3f}%"
                     for b in (1, 3, 5)] for m, s, _ in policies]
    table = axes[1].table(cellText=table_values, colLabels=['1 attempt', '3 attempts', '5 attempts'],
                           cellLoc='center', colLoc='center', bbox=[.02, .06, .94, .86])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor('#D9E0E5')
        if row == 0:
            cell.set_facecolor('#E8EEF3')
            cell.set_text_props(weight='bold')
        else:
            cell.set_facecolor('#F2F7FA' if row <= 6 else '#F6F6F3')
            if column == 0:
                cell.set_text_props(color=colors[row - 1], weight='bold')
    axes[1].set_title('B  Secondary budget sensitivity · same row order', loc='left', pad=18)
    axes[1].text(.02, -.015, 'All values are regret as % of trace instructions.\nRandom averages all five fixed seeds; seeds are not population replicates.',
                 transform=axes[1].transAxes, fontsize=9, color='#48515C', va='top')
    footer(fig, 'Six model policies prioritize predicted-feasible candidates by merit. Merit/frequency/random use the same candidate pools and attempt budgets.')
    return save(fig, 'v8-selection-regret-and-budgets', output)


def contextual_records(rows, labels, predictions, novelty):
    actual = {r['formula']: r['lut4_count'] for r in labels}
    novel = {r['formula']: r for r in novelty['records']}
    points = {model: {(r['benchmark'], r['candidate_id']): r for r in records}
              for model, records in predictions.items()}
    result = []
    for row in rows:
        key = row['benchmark'], row['candidate_id']
        value = {'benchmark': row['benchmark'], 'candidate_id': row['candidate_id'],
                 'formula': row['formula'], 'family': row['family'], 'primary_family': row['primary_family'],
                 'actual_lut4': actual[row['formula']],
                 'strict_no_declared_match': novel[row['formula']]['strict_no_declared_match'],
                 'no_declared_identity_match': novel[row['formula']]['no_declared_identity_match'],
                 'canonical_seen': bool(novel[row['formula']]['matches']['canonical'])}
        for model in (BASELINE, CHALLENGER):
            p = points[model][key]
            assert p['formula'] == row['formula']
            value[model] = {'predicted_lut4': p['predicted_lut4'],
                            'absolute_error_lut4': abs(p['predicted_lut4'] - value['actual_lut4']),
                            'outside_training_feature_ranges': p['outside_training_feature_ranges']}
        result.append(value)
    return result


def context_figure(evaluation, records, plt, output):
    primary = [r for r in records if r['primary_family']]
    families = sorted({r['family'] for r in primary})
    colors = dict(zip(families, ('#126B9B', '#D17822', '#008477', '#A64D79')))
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 12.2), gridspec_kw={'height_ratios': [1.18, 1]})
    fig.subplots_adjust(left=.10, right=.97, top=.87, bottom=.16, wspace=.27, hspace=.43)
    fig.suptitle('V8 point predictions and secondary error context', fontsize=19, x=.035, ha='left', y=.98)
    fig.text(.035, .93, 'Primary-family memberships shown; shared formulas retain their program memberships. Equal x/y scales start at zero.', fontsize=11)
    maximum = max([r['actual_lut4'] for r in primary] +
                  [r[m]['predicted_lut4'] for r in primary for m in (BASELINE, CHALLENGER)]) * 1.06
    maximum = max(maximum, 1)
    for ax, model, panel in zip(axes[0], (BASELINE, CHALLENGER), ('A', 'B')):
        ax.plot([0, maximum], [0, maximum], color='#737D87', linestyle='--', linewidth=1, zorder=0)
        for family in families:
            subset = [r for r in primary if r['family'] == family]
            ax.scatter([r['actual_lut4'] for r in subset], [r[model]['predicted_lut4'] for r in subset],
                        s=27, alpha=.72, color=colors[family], label=family, edgecolor='white', linewidth=.4)
        ax.set(xlim=(0, maximum), ylim=(0, maximum), xlabel='Measured original-RTL LUT4', ylabel='Frozen predicted LUT4')
        ax.set_aspect('equal', adjustable='box')
        ax.grid(color='#E2E6EA', linewidth=.7)
        ax.set_title(f'{panel}  {NAMES[model]}', loc='left', pad=12)
        if model == BASELINE:
            ax.legend(frameon=False, fontsize=9, loc='upper left')
    worst = sorted(primary, key=lambda r: (-r[CHALLENGER]['absolute_error_lut4'], r['benchmark'], r['candidate_id']))[:8]
    ax = axes[1, 0]
    for shift, model in ((-.18, BASELINE), (.18, CHALLENGER)):
        ax.barh([i + shift for i in range(len(worst))], [r[model]['absolute_error_lut4'] for r in worst],
                 height=.32, color=COLORS[model], label=NAMES[model])
    ax.set_yticks(range(len(worst)), [f"{r['benchmark']} · {hashlib.sha256(r['formula'].encode()).hexdigest()[:6]}" for r in worst])
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.grid(axis='x', color='#E2E6EA', linewidth=.7)
    ax.set_xlabel('Absolute error (LUT4) ↓')
    ax.set_title('C  Secondary · 8 largest rewritten errors', loc='left', pad=14)
    ax.legend(frameon=False, fontsize=9, loc='lower right')
    ax = axes[1, 1]
    ax.axis('off')
    conditions = [('All retained', lambda r: True),
                  ('Canonical seen', lambda r: r['canonical_seen']),
                  ('No declared identity match', lambda r: r['no_declared_identity_match']),
                  ('Strict no declared match', lambda r: r['strict_no_declared_match']),
                  ('Familiar under any test', lambda r: not r['strict_no_declared_match'])]
    table_data = []
    for name, predicate in conditions:
        all_rows = [r for r in records if predicate(r)]
        primary_rows = [r for r in primary if predicate(r)]
        table_data.append([name, str(len(all_rows)), str(len({r['formula'] for r in all_rows})),
                           str(len(primary_rows)), str(len({r['family'] for r in primary_rows})) + '/4'])
    table = ax.table(cellText=table_data, colLabels=['Input-only class', 'All\nrows', 'Unique\nformulas', 'Primary\nrows', 'Primary\nfamilies'],
                      cellLoc='center', colWidths=[.43, .12, .15, .15, .15], bbox=[-.02, .20, 1.04, .74])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor('#D9E0E5')
        if row == 0:
            cell.set_facecolor('#E8EEF3')
            cell.set_text_props(weight='bold')
        if row > 0 and column == 0:
            cell.set_text_props(ha='left')
    ax.set_title('D  Secondary novelty · explicit denominators', loc='left', pad=14)
    ax.text(0, .11, 'Classes overlap; none removes primary rows. “Strict” means no match\nunder any declared test; it is not a claim of semantic novelty.\nFull formulas, errors and range diagnostics are in figure-data.json.',
             transform=ax.transAxes, fontsize=9, color='#48515C', va='top')
    footer(fig, 'Scatter panels show both models in the primary contrast. Worst-error and novelty panels are consumed-test diagnostics; no retuning or new success endpoint.')
    return save(fig, 'v8-prediction-errors-and-novelty', output), worst, table_data


def captions(evaluation):
    scores, primary = evaluation['scores'], evaluation['primary']
    aggregates = evaluation['selection']['aggregates']
    def regret(model, strategy='predicted_area_feasible_merit', budget=1):
        return aggregates[f'{model}/{strategy}/cap64/budget{budget}']['primary_equal_family_normalized_regret_percent']
    return ('# V8 application-transfer figure captions\n\n'
        '**Figure 1 — Frozen point-prediction error and family sensitivity.** '
        'Panel A reports all six models using equal program weights within a family and equal weights across the four primary source families. '
        f'The declared primary contrast is legacy rewritten versus mapping V6: MAE '
        f"{scores[CHALLENGER]['primary_equal_family_mae_lut4']:.6f} versus {scores[BASELINE]['primary_equal_family_mae_lut4']:.6f} LUT4, "
        f"a rewritten-minus-baseline difference of {primary['difference_lut4']:+.6f} LUT4. "
        'Panel B retains every paired family difference; negative differences favor rewritten. '
        'Panel C recomputes that descriptive contrast after omitting each family, exposing dependence on the family mix. '
        'No population confidence interval is estimated from these four families. Other-model comparisons and omission sensitivity are secondary.\n\n'
        '**Figure 2 — Selection regret under a fixed measurement budget.** '
        'Panel A uses the declared cap of 64 LUT4 and one candidate attempt per program and policy. '
        'The six model policies prioritize predicted-feasible candidates by overlap-safe saved instructions; actual measured feasibility determines the final selection. '
        f'Rewritten regret is {regret(CHALLENGER):.6f}% of trace instructions versus {regret(BASELINE):.6f}% for mapping V6. '
        f'Merit-only regret is {regret(BASELINE, "merit"):.6f}%; this tie or difference must be retained when assessing model value. '
        'Panel B reports the same policies at budgets of one, three and five attempts; all five fixed random seeds are averaged without treating seeds as population replicates. '
        'Regret is the full-pool oracle overlap-safe saved-instruction count minus the selected count, divided by the trace instruction count and multiplied by 100. '
        'It is an instruction-count proxy, not processor speedup, latency, clock frequency, or additive multi-instruction benefit.\n\n'
        '**Figure 3 — Actual/predicted resource counts and consumed-test context.** '
        'Panels A–B show mapping V6 and legacy rewritten on primary-family memberships with identical, zero-origin, equal-aspect axes; the dashed line is exact prediction. '
        'Panel C shows the eight primary memberships with the largest rewritten absolute errors and the baseline errors on those same cases. '
        'Case labels give the program and first six hexadecimal characters of the formula SHA-256; full formulas and range diagnostics accompany the figures in figure-data.json. '
        'Panel D distinguishes all 152 program memberships, 146 unique formulas and 150 primary memberships. '
        'Input-only novelty classes overlap and do not exclude any primary row; the strict-no-declared-match subset covers only three of four primary families and cannot support a complete four-family novelty claim. '
        'Worst-error and novelty panels are secondary diagnostics after test consumption.\n\n'
        'All figures preserve the declared primary comparison, show every comparison model, and use zero-inclusive axes. '
        'Source/input and output hashes are recorded in figure-manifest.json.\n')


def run(evaluation_path, output_dir, root=None):
    """Render a validated score, using its parent as evidence root by default."""
    evaluation_path, output = Path(evaluation_path), Path(output_dir)
    root = Path(root) if root is not None else evaluation_path.parent
    root, evaluation_path, output = map(lambda p: Path(p).resolve(), (root, evaluation_path, output))
    if output.exists():
        raise ValueError('Figure output directory already exists; use a fresh path')
    evaluation = read(evaluation_path)
    if (evaluation.get('schema') != 'isaforge-v8-committed-application-evaluation-v1'
            or evaluation.get('lineage_validated_by_wrapper') is not True
            or evaluation.get('point_only') is not True):
        raise ValueError('Completed, lineage-validated committed evaluation required')
    if evaluation['primary']['family_count'] != 4 or set(evaluation['scores']) != set(MODELS):
        raise ValueError('All six fixed models and four primary families required')
    completion_path = root / 'measurements/completion.json'
    completion = read(completion_path)
    if completion.get('complete') is not True or completion.get('failures') != []:
        raise ValueError('Complete measurements with no failures required')
    labels_path = root / 'measurements' / completion['attempt'] / 'labels.json'
    paths = [evaluation_path, root / 'point-freeze.json', root / 'input-seal.json', completion_path,
             root / 'rows.json', root / 'novelty.json', labels_path, Path(__file__).resolve()]
    freeze = read(root / 'point-freeze.json')
    prediction_paths = {m: (root / freeze['models'][m]['predictions']['path']).resolve() for m in MODELS}
    paths.extend(prediction_paths.values())
    before = {str(p): sha(p) for p in paths}
    provenance = evaluation['provenance']
    for name, path in (('point_freeze_sha256', root / 'point-freeze.json'),
                       ('input_seal_sha256', root / 'input-seal.json'),
                       ('completion_sha256', completion_path), ('labels_sha256', labels_path)):
        if sha(path) != provenance[name]:
            raise ValueError('Evaluation-bound input digest differs: ' + name)
    if sha(labels_path) != completion['labels_sha256']:
        raise ValueError('Label completion digest differs')
    seal = read(root / 'input-seal.json')
    for key in ('rows', 'novelty'):
        if (root / seal[key]['path']).resolve() != root / (key + '.json') or sha(root / (key + '.json')) != seal[key]['sha256']:
            raise ValueError('Sealed presentation context digest differs: ' + key)
    for model, path in prediction_paths.items():
        if sha(path) != freeze['models'][model]['predictions']['sha256']:
            raise ValueError('Frozen prediction digest differs')
    rows, novelty, labels = read(root / 'rows.json'), read(root / 'novelty.json'), read(labels_path)
    predictions = {m: read(p) for m, p in prediction_paths.items()}
    records = contextual_records(rows, labels, predictions, novelty)
    if len(records) != evaluation['counts']['application_formula_rows']:
        raise ValueError('Application row count differs')
    output.mkdir(parents=True)
    plt = configure()
    figures = errors_figure(evaluation, plt, output)
    figures += selection_figure(evaluation, plt, output)
    more, worst, novelty_table = context_figure(evaluation, records, plt, output)
    figures += more
    plt.close('all')
    data_path = output / 'figure-data.json'
    write_new(data_path, {'schema': 'isaforge-v8-presentation-data-v1', 'scope': FOOTNOTE,
                          'primary': evaluation['primary'], 'counts': evaluation['counts'],
                          'records': records, 'worst_rewritten_primary_errors': worst,
                          'novelty_denominators': novelty_table})
    captions_path = output / 'captions.md'
    with captions_path.open('x') as stream:
        stream.write(captions(evaluation))
    if {str(p): sha(p) for p in paths} != before:
        raise ValueError('Presentation inputs or source changed during rendering')
    write_new(output / 'figure-manifest.json', {'schema': 'isaforge-v8-presentation-manifest-v1',
        'python': sys.executable, 'matplotlib': __import__('matplotlib').__version__,
        'source_and_input_sha256': before,
        'output_sha256': {str(p.relative_to(output)): sha(p) for p in [*figures, data_path, captions_path]},
        'scope': FOOTNOTE, 'models_refit': False, 'points_recomputed': False,
        'evaluation_recomputed': False, 'axes': 'Zero included; scatter axes share equal scales; no broken axes.',
        'primary': 'Rewritten minus mapping V6; four-family MAE; cap64/budget1 selection.',
        'secondary': 'Other models, leave-family-out, budget sensitivity, worst errors and novelty context.'})
    print(f'Wrote {len(figures)} figures plus data and hash manifest to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Evidence root; defaults to evaluation parent')
    parser.add_argument('--evaluation', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.evaluation is None and args.root is None:
        parser.error('--evaluation or --root is required')
    run(args.evaluation or args.root / 'evaluation.json', args.output, args.root)
