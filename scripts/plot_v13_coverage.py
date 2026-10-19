#!/usr/bin/env python3
"""Plot completed matched V13 coverage OOF evidence; no fits or model loading.

All three paired seeds and both cohorts are retained. Source hashes and plotted
full precision values accompany PNG/SVG/PDF figures. No selected seed or CI.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (2026101421, 2026101422, 2026101423)
VIEWS = ('control', 'augmented')
STRATA = ('arithmetic_chain', 'comparators', 'constant_shifts', 'mask_logic', 'multiplication', 'parallel_branches', 'shared_diamond', 'variable_shifts', 'workload')
FAMILIES = ('correlated_high_products', 'affine_masked_chains', 'comparator_shift_compositions')
COLORS = {'control': '#6A7480', 'augmented': '#187AA1'}
LABELS = {'control': 'Control · old rows only', 'augmented': 'Augmented · eligible coverage rows added'}


def need(value, message):
    if not value: raise ValueError(message)


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {'path': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path), 'sha256': sha(path)}


def close(a, b): return type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, rel_tol=0, abs_tol=1e-11)


def write(path, value):
    with Path(path).open('x') as stream: json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def actual_data(root):
    """Read complete results only and replay every plotted metric from OOF rows."""
    import numpy as np
    root = Path(root).resolve(); fitting = root / 'fitting'; stage = fitting / 'fit-attempt-0000'
    completion = stage / 'completion.json'
    need(completion.is_file(), 'Wait for actual completed fitting; partial results are not plotted')
    done = read(completion)
    need(done.get('schema') == 'isaforge-v13-matched-fit-completion-v1' and done.get('complete') is True and done.get('error') is None
         and all(type(done.get(k)) is int and done[k] == 30 for k in ('fits_attempted', 'fits_completed', 'maximum_fits')), 'Complete successful30-fit result required')
    for key in ('evaluation_target_reads', 'new_solver_queries', 'new_feature_extractions', 'new_physical_labels'):
        need(type(done.get(key)) is int and done[key] == 0, 'Fitting-only completion contract differs')
    summary_path = stage / 'summary.json'; preparation = fitting / 'preparation.json'; approval = fitting / 'fit-approval.json'
    need(sha(summary_path) == done['summary_sha256'] and sha(preparation) == done['preparation_sha256'] and sha(approval) == done['approval_sha256'], 'Completed result identity differs')
    summary = read(summary_path); prep = read(preparation)
    need(summary['schema'] == 'isaforge-v13-matched-coverage-comparison-v1' and summary['fits_completed'] == 30 and set(summary['scores']) == set(VIEWS), 'Matched two-view summary required')
    bindings = {(fitting / e['path']).resolve(): e['sha256'] for e in prep['files']}
    required = [fitting / n for n in ('fitting.json', 'split.json', 'groups.json', 'recipe.json', 'runtime.json')]
    runner = ROOT / 'scripts/develop_v13_coverage.py'
    need(all(bindings.get(p) == sha(p) for p in [*required, runner]) and done['runner_sha256'] == sha(runner), 'Fitting input/recipe/source changed')
    payload = read(fitting / 'fitting.json'); rows = payload['rows']; split = read(fitting / 'split.json'); recipe = read(fitting / 'recipe.json')
    need(len(rows) == len({r['formula'] for r in rows}) == 1761 and Counter(r['cohort'] for r in rows) == {'original1713': 1713, 'coverage48': 48}, 'Complete old1713/new48 identity required')
    need(recipe['seeds'] == list(SEEDS) and recipe['maximum_fits'] == 30, 'Fixed paired-seed recipe required')
    need(len(split['fold_ids']) == len(rows) and set(split['fold_ids']) == set(range(5)), 'Shared fivefold map required')
    truth = np.asarray([r['lut4_count'] for r in rows], dtype=float); zero = np.asarray(payload['original_zero'], dtype=bool)
    need(np.isfinite(truth).all() and np.all(truth >= 0) and np.all(truth == np.floor(truth)), 'Finite original integer LUT4 targets required')
    cohorts = np.asarray([r['cohort'] for r in rows]); strata = np.asarray([r['stratum'] for r in rows])
    families = np.asarray([r.get('family', '') if r['cohort'] == 'coverage48' else '' for r in rows])
    old = cohorts == 'original1713'; new = ~old
    need(set(strata[old]) == set(STRATA) and Counter(families[new]) == {f: 16 for f in FAMILIES}, 'All primary strata and secondary families required')
    paths = [completion, summary_path, preparation, approval, fitting / 'fit-claim.json', *required, runner]
    plotted = {}
    for view in VIEWS:
        need(set(summary['scores'][view]) == set(map(str, SEEDS)), 'Every paired seed required')
        cells = {key: [] for key in ('primary_macro_mae_by_seed', 'cap64_false_accept_by_seed', 'cap64_false_reject_by_seed', 'p99_absolute_error_by_seed', 'maximum_underprediction_by_seed')}
        cells['old_stratum_mae_by_seed'] = {s: [] for s in STRATA}
        cells['new_stratum_mae_by_seed'] = {s: [] for s in sorted(set(strata[new]))}
        cells['new_family_mae_by_seed'] = {f: [] for f in FAMILIES}
        for seed in SEEDS:
            point_path = stage / 'predictions' / f'{view}-seed-{seed}.json'; metric_path = stage / 'metrics' / f'{view}-seed-{seed}.json'
            records = read(point_path); score = summary['scores'][view][str(seed)]
            need(len(records) == len(rows) and read(metric_path) == score, 'Complete saved point/metric table required')
            for i, (row, point) in enumerate(zip(rows, records)):
                need(all(point[k] == v for k, v in row.items()) and point['fold'] == split['fold_ids'][i] and point['original_zero'] is bool(zero[i]), 'OOF identity/fold/zero mismatch')
            encoded = np.asarray([p['encoded_prediction'] for p in records]); before = np.asarray([p['decoded_before_zero'] for p in records]); points = np.asarray([p['predicted_lut4'] for p in records])
            need(np.isfinite(encoded).all() and np.isfinite(points).all() and np.all(points >= 0) and np.array_equal(np.maximum(encoded, 0), before), 'Raw-target decoding differs')
            expected = before.copy(); expected[zero] = 0; need(np.array_equal(expected, points), 'Original graph zero override differs')
            errors = np.abs(points - truth)
            for cohort, mask in (('original1713', old), ('coverage48', new)):
                target = score[cohort]; pooled = target['pooled']; count = int(mask.sum())
                need(pooled['count'] == count and close(pooled['mae_lut4'], float(errors[mask].mean()))
                     and close(pooled['p99_absolute_error_lut4'], float(np.quantile(errors[mask], .99, method='linear')))
                     and close(pooled['maximum_underprediction_lut4'], float(np.maximum(truth[mask] - points[mask], 0).max())), 'OOF cohort MAE/tail replay differs')
                for name in sorted(set(strata[mask])):
                    selection = mask & (strata == name); actual = float(errors[selection].mean())
                    need(target['by_stratum'][name]['count'] == int(selection.sum()) and close(target['by_stratum'][name]['mae_lut4'], actual), 'OOF stratum replay differs')
                    cells['old_stratum_mae_by_seed' if cohort == 'original1713' else 'new_stratum_mae_by_seed'][name].append(actual)
                for cap in (32, 64, 128):
                    y, p = truth[mask], points[mask]
                    counts = {'false_accept_count': int(((p <= cap) & (y > cap)).sum()), 'false_reject_count': int(((p > cap) & (y <= cap)).sum()),
                              'actually_feasible_count': int((y <= cap).sum()), 'actually_infeasible_count': int((y > cap).sum()), 'predicted_feasible_count': int((p <= cap).sum()), 'count': count}
                    need(pooled['caps'][str(cap)] == counts, 'All-row cap replay differs')
            primary = float(np.mean([score['original1713']['by_stratum'][s]['mae_lut4'] for s in STRATA]))
            need(close(score['original1713']['macro_stratum_mae_lut4'], primary), 'Equal-nine-stratum primary differs')
            for family in FAMILIES:
                mask = new & (families == family); actual = float(errors[mask].mean()); cell = score['coverage_by_family'][family]['pooled']
                need(cell['count'] == 16 and close(cell['mae_lut4'], actual), 'Secondary family replay differs'); cells['new_family_mae_by_seed'][family].append(actual)
            pooled = score['original1713']['pooled']; cells['primary_macro_mae_by_seed'].append(primary)
            for key, value in [('cap64_false_accept_by_seed', pooled['caps']['64']['false_accept_count']), ('cap64_false_reject_by_seed', pooled['caps']['64']['false_reject_count']),
                               ('p99_absolute_error_by_seed', pooled['p99_absolute_error_lut4']), ('maximum_underprediction_by_seed', pooled['maximum_underprediction_lut4'])]: cells[key].append(value)
            paths.extend((point_path, metric_path))
        plotted[view] = cells
    delta = [a - c for a, c in zip(plotted['augmented']['primary_macro_mae_by_seed'], plotted['control']['primary_macro_mae_by_seed'])]
    primary = summary['primary_augmented_minus_control_original1713_macro_mae_lut4']
    need(all(close(primary['per_seed'][str(s)], d) for s, d in zip(SEEDS, delta)) and close(primary['mean'], float(np.mean(delta))), 'Paired primary summary differs')
    for i in range(1, 31):
        path = stage / 'receipts' / f'{i:02d}-completed.json'; receipt = read(path)
        need(receipt['fit_index'] == i and receipt['save_load_points_exact'] is True, 'Every completed fit receipt required'); paths.append(path)
    data = {'schema': 'isaforge-v13-coverage-figure-data-v1', 'synthetic': False, 'original_primary_rows': 1713, 'coverage_secondary_rows': 48,
            'joint_rows': 1761, 'groups': len(read(fitting / 'groups.json')['components']), 'features': 217, 'trees': 300, 'folds': 5, 'fits': 30, 'seeds': list(SEEDS),
            'old_stratum_order': list(STRATA), 'new_stratum_order': sorted(set(strata[new])), 'family_order': list(FAMILIES),
            'cohort_stratum_counts': {name: dict(Counter(strata[cohorts == name])) for name in ('original1713', 'coverage48')},
            'plotted_full_precision_values': plotted, 'summary': summary,
            'source_and_input_sha256': [ref(p) for p in dict.fromkeys([Path(__file__), *paths])],
            'scope': 'Targeted consumed-development augmentation; identical joint closed held-out groups. Old1713 primary, new48 secondary. All three seeds; no selected seed, statistical confidence interval, final refit, independent transfer, calibration, hardware timing, power or CPU claim.'}
    return data, list(dict.fromkeys(paths))


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 13, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.axisbelow': True, 'figure.facecolor': 'white', 'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'isaforge-v13-coverage'})
    values = data['plotted_full_precision_values']; figures = []
    def heading(fig, title, subtitle):
        fig.suptitle(title, x=.035, y=.985, ha='left', fontsize=20, color='#1E2B36')
        fig.text(.035, .94, subtitle, fontsize=11, color='#455461')
        handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[v]) for v in VIEWS]
        fig.legend(handles, [LABELS[v] for v in VIEWS], loc='upper center', bbox_to_anchor=(.53, .918), ncol=2, frameon=False, fontsize=10)
    def seed_bars(ax, key, title, ylabel, counts=False):
        x = np.arange(3); maximum = 0
        for view, offset in (('control', -.18), ('augmented', .18)):
            y = values[view][key]; maximum = max(maximum, *y); ax.bar(x + offset, y, width=.31, color=COLORS[view])
            for position, value in zip(x + offset, y): ax.annotate(str(value) if counts else f'{value:.3f}', (position, value), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=10)
        ax.set_xticks(x, ['21', '22', '23']); ax.set_xlabel('Paired algorithm seed suffix · 20261014xx'); ax.set_ylabel(ylabel)
        ax.set_ylim(0, maximum * 1.22 if maximum else 1); ax.set_title(title, loc='left', pad=14); ax.grid(axis='y', color='#E2E8ED', lw=.7)
        if counts: ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    def differences(ax, names, key, labels, title):
        all_values = []; means = []; changes = []
        for i, name in enumerate(names):
            change = [a - c for a, c in zip(values['augmented'][key][name], values['control'][key][name])]; average = float(np.mean(change)); means.append(average); all_values.extend(change); changes.append(change)
            ax.barh(i, average, height=.5, color='#BA675A' if average > 0 else '#4C96B1', alpha=.85)
            ax.scatter(change, [i + offset for offset in (-.08, 0, .08)], color='#263743', s=23, zorder=3)
        span = max(all_values) - min(all_values) or 1
        for i, mean in enumerate(means):
            if abs(mean) > .25 * span:
                ax.text(mean / 2, i, f'{mean:+.3f}', va='center', ha='center', fontsize=10, color='white', weight='bold')
            else:
                position = max(changes[i] + [mean]) + .04 * span if mean >= 0 else min(changes[i] + [mean]) - .04 * span
                ax.text(position, i, f'{mean:+.3f}', va='center', ha='left' if mean >= 0 else 'right', fontsize=10)
        ax.set_xlim(min(0, min(all_values)) - .22 * span, max(0, max(all_values)) + .30 * span); ax.axvline(0, color='#314553', lw=1)
        ax.set_yticks(range(len(names)), labels); ax.invert_yaxis(); ax.grid(axis='x', color='#E2E8ED', lw=.7)
        ax.set_title(title, loc='left', pad=14); ax.set_xlabel('Augmented − control MAE (LUT4) · negative favors augmentation')
    fig, axes = plt.subplots(2, 2, figsize=(18.5, 13), gridspec_kw={'wspace': .52, 'hspace': .55})
    fig.subplots_adjust(left=.16, right=.96, top=.82, bottom=.17)
    heading(fig, 'V13 · targeted coverage on identical held-out groups', 'Old 1,713-row primary and new 48-row secondary · raw target · 217 features · 300 trees · five joint closed folds · all three paired seeds')
    seed_bars(axes[0, 0], 'primary_macro_mae_by_seed', 'A  Primary · old 1,713 equal-nine-stratum MAE', 'OOF macro MAE (LUT4) ↓')
    differences(axes[0, 1], STRATA, 'old_stratum_mae_by_seed', [s.replace('_', ' ') for s in STRATA], 'B  Primary cohort · every stratum')
    ax = axes[1, 0]
    names = ['Correlated high products', 'Affine/masked chains', 'Comparator/shift compositions']; samples_all = []
    for view, offset in (('control', -.17), ('augmented', .17)):
        samples = [values[view]['new_family_mae_by_seed'][f] for f in FAMILIES]; means = [float(np.mean(y)) for y in samples]; samples_all.extend(v for row in samples for v in row)
        ax.scatter(means, np.arange(3) + offset, s=95, marker='D', color=COLORS[view], zorder=3)
        for i, y in enumerate(samples): ax.scatter(y, [i + offset + d for d in (-.04, 0, .04)], color='#263743', s=23, zorder=3)
    ax.set_yticks(range(3), [n + ' (N=16)' for n in names]); ax.invert_yaxis(); ax.grid(axis='x', color='#E2E8ED', lw=.7)
    if min(samples_all) > 0:
        from matplotlib.ticker import FuncFormatter
        ax.set_xscale('log'); ax.set_xlim(min(samples_all) / 1.5, max(samples_all) * 1.4); ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
        scale = 'log scale'
    else:
        ax.set_xlim(left=0); scale = 'linear scale'
    ax.set_title('C  Secondary new 48 · all three fixed families', loc='left', pad=14); ax.set_xlabel(f'OOF MAE (LUT4) ↓ · {scale} · diamonds: mean; dots: all seeds')
    new_names = data['new_stratum_order']; counts = data['cohort_stratum_counts']['coverage48']
    differences(axes[1, 1], new_names, 'new_stratum_mae_by_seed', [s.replace('_', ' ') + f' (N={counts[s]})' for s in new_names], 'D  Secondary new 48 · every represented stratum')
    primary = data['summary']['primary_augmented_minus_control_original1713_macro_mae_lut4']
    fig.text(.035, .095, f"Declared primary, augmented − control: {primary['mean']:+.6f} LUT4 across the three paired seeds. Negative favors augmentation.\nB/D bars show descriptive seed means and dots show all three contrasts. C uses pooled MAE within each family, not a reweighted primary.", fontsize=11, color='#263743')
    fig.text(.035, .035, 'Targeted consumed-development experiment: both views use the same joint closed validation groups; no linked new validation row enters augmentation training.\nOld 1,713 rows remain the primary denominator. New 48 results are secondary; no selected seed, confidence interval, fresh-transfer, calibration or CPU claim. Full precision and hashes: figure-data.json.', fontsize=10, color='#455461')
    figures.append(('v13-primary-and-coverage', fig))
    fig, axes = plt.subplots(2, 2, figsize=(14.8, 11.6), gridspec_kw={'wspace': .32, 'hspace': .55})
    fig.subplots_adjust(left=.09, right=.96, top=.81, bottom=.18)
    heading(fig, 'V13 · budget errors and tails remain separate endpoints', 'All old 1,713 primary OOF rows in each view and seed · identical joint folds · cap64 boundary is inclusive')
    denominator = data['summary']['scores']['control'][str(SEEDS[0])]['original1713']['pooled']['caps']['64']
    seed_bars(axes[0, 0], 'cap64_false_accept_by_seed', f"A  Cap64 false accepts · infeasible N={denominator['actually_infeasible_count']}", 'False accepts ↓', True)
    seed_bars(axes[0, 1], 'cap64_false_reject_by_seed', f"B  Cap64 false rejects · feasible N={denominator['actually_feasible_count']}", 'False rejects ↓', True)
    seed_bars(axes[1, 0], 'p99_absolute_error_by_seed', 'C  P99 absolute error · all primary rows', 'P99 absolute error (LUT4) ↓')
    seed_bars(axes[1, 1], 'maximum_underprediction_by_seed', 'D  Maximum underprediction · all primary rows', 'Maximum underprediction (LUT4) ↓')
    fig.text(.035, .095, 'False accept: point ≤64 with target >64. False reject: point >64 with target ≤64. Lower is better for each endpoint separately.\nThree paired algorithm seeds are displayed in full; an improved mean does not erase a worse cap decision or tail. Cap32/128 sensitivities remain in figure-data.json.', fontsize=11, color='#263743')
    fig.text(.035, .035, 'Static original-RTL LUT4 prediction errors on consumed development data. No statistical confidence intervals, calibrated safety bound, hardware timing, power or CPU-performance inference.\nBoth views retain the same original-generic-graph zero override; canonical/accepted aliases, exact selected-vector collisions and complete contexts close the shared fold map.', fontsize=10, color='#455461')
    figures.append(('v13-cap64-and-tails', fig))
    files = []
    for name, figure in figures:
        for extension in ('png', 'svg', 'pdf'):
            path = output / (name + '.' + extension)
            figure.savefig(path, dpi=220, bbox_inches='tight', pad_inches=.2, metadata={'CreationDate': None, 'ModDate': None} if extension == 'pdf' else None); files.append(path)
        plt.close(figure)
    return files, matplotlib.__version__


def run(root, output):
    output = Path(output).resolve(); need(not output.exists(), 'Fresh figure directory required')
    data, paths = actual_data(root); before = {p: sha(p) for p in [Path(__file__), *paths]}
    output.mkdir(parents=True); write(output / 'figure-data.json', data); files, version = render(data, output)
    need(all(sha(p) == h for p, h in before.items()), 'Source/evidence changed during rendering')
    manifest = {'schema': 'isaforge-v13-coverage-figure-manifest-v1', 'matplotlib_version': version, 'figure_data': ref(output / 'figure-data.json'),
                'files': [ref(p) for p in files], 'native_jobs': 0, 'model_imports_or_fits': 0, 'scope': data['scope']}
    write(output / 'figure-manifest.json', manifest); return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(run(args.root, args.output), indent=2))
