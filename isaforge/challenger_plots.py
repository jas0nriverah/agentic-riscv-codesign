"""Reproduce research figures from released development/probe evaluations.

Read only explicitly supplied evaluation, measurement and prediction files.
This plotting module performs no training, selection or synthesis. The caller
must enforce the probe-label release protocol before invoking its probe inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np

MODEL_ORDER = ('resource_v2', 'v1_xgboost_log', 'v2_residual_xgb',
               'v3_original', 'v3_structural', 'masterrtl_sog')
MODEL_LABELS = {
    'resource_v2': 'Resource v2', 'v1_xgboost_log': 'XGBoost v1',
    'v2_residual_xgb': 'Residual XGBoost v2', 'v3_original': 'v3 original pipeline',
    'v3_structural': 'v3 structural pipeline', 'masterrtl_sog': 'MasterRTL SOG adaptation',
}
COLORS = dict(zip(MODEL_ORDER, ('#333333', '#E69F00', '#0072B2',
                              '#CC79A7', '#009E73', '#D55E00')))
STYLE = {
    'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
    'axes.labelsize': 10, 'figure.titlesize': 14, 'xtick.labelsize': 9,
    'ytick.labelsize': 10, 'legend.fontsize': 9, 'axes.spines.top': False,
    'axes.spines.right': False, 'axes.grid': False, 'pdf.fonttype': 42,
    'ps.fonttype': 42, 'svg.fonttype': 'none', 'savefig.facecolor': 'white',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _interval(values, draws, index):
    values = np.asarray(values, dtype=float)
    if values.shape != (index.shape[1],):
        raise ValueError('bootstrap input must contain one value per program')
    means = values[index].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {'mean': float(values.mean()), 'lower': float(lo), 'upper': float(hi),
            'program_count': len(values), 'bootstrap_draws': draws}


def _dev_models(development, reference=None):
    """Merge the separately frozen reference into the matched comparison."""
    result = {name: {'macro': metrics, 'programs': {}}
              for name, metrics in development['macro_program_metrics'].items()}
    for fold in development['folds']:
        for name, metrics in fold['metrics'].items():
            result[name]['programs'][fold['held_out_benchmark']] = metrics
    if reference:
        if (reference.get('training_dataset_sha256') != development.get('training_dataset_sha256')
                and reference.get('training_dataset_sha256') is not None):
            raise ValueError('matched reference training dataset differs from development')
        original_folds = {fold['held_out_benchmark']: fold for fold in development['folds']}
        macros = reference.get('macro_program_metrics')
        if macros is None:
            raise ValueError('reference development report requires macro_program_metrics')
        for name, metrics in macros.items():
            if name in result: raise ValueError(f'duplicate reference model {name}')
            result[name] = {'macro': metrics, 'programs': {}}
        for fold in reference['folds']:
            original = original_folds.get(fold['held_out_benchmark'])
            if original is None: raise ValueError('reference contains an unmatched program')
            for field in ('train_formula_count', 'test_size', 'excluded_matching_formula_rows'):
                if field in fold and fold[field] != original[field]:
                    raise ValueError('matched reference program split differs from development')
            for name, metrics in fold['metrics'].items():
                result[name]['programs'][fold['held_out_benchmark']] = metrics
    return result


def _save(fig, output, name):
    for extension in ('svg', 'pdf', 'png'):
        fig.savefig(output / f'{name}.{extension}', dpi=300, bbox_inches='tight', pad_inches=0.13)
    plt.close(fig)


def _grid(ax, axis='x'):
    ax.grid(axis=axis, color='#e4e7ea', linewidth=0.6)
    ax.set_axisbelow(True)


def _paired(ax, programs, base, new, xlabel, baseline='resource_v2', challenger='v3_structural'):
    order = np.argsort(base)
    y = np.arange(len(programs))
    for row, i in zip(y, order):
        ax.plot([base[i], new[i]], [row, row], color='#bdc5cc', linewidth=1.4, zorder=1)
    ax.scatter(base[order], y, color=COLORS[baseline], marker='o', s=35, zorder=3,
               label=MODEL_LABELS[baseline])
    ax.scatter(new[order], y, color=COLORS[challenger], marker='D', s=37, zorder=4,
               label=MODEL_LABELS[challenger])
    ax.set_yticks(y, np.asarray(programs)[order])
    ax.set_xlabel(xlabel); ax.set_xlim(left=0); _grid(ax)
    ax.legend(frameon=False, loc='lower right')


def _horizontal_metrics(ax, names, values, intervals=None, short_labels=False, format_spec='.2f'):
    y = np.arange(len(names))
    ax.barh(y, values, height=0.61, color=[COLORS[n] for n in names], alpha=0.9)
    labels = ({'v3_original': 'Original pipeline', 'v3_structural': 'Structural pipeline'}
              if short_labels else MODEL_LABELS)
    ax.set_yticks(y, [labels[n] for n in names]); ax.invert_yaxis()
    ax.set_xlim(left=0); _grid(ax)
    if intervals:
        lo = [max(0, v - intervals[n]['lower']) for n, v in zip(names, values)]
        hi = [max(0, intervals[n]['upper'] - v) for n, v in zip(names, values)]
        ax.errorbar(values, y, xerr=np.asarray([lo, hi]), color='#222222', fmt='none',
                    capsize=3, elinewidth=0.9, zorder=4)
    xmax = max(ax.get_xlim()[1], max(values, default=1))
    ax.set_xlim(0, xmax * 1.16)
    for row, value in zip(y, values):
        ax.text(value + xmax * 0.018, row - 0.15, f'{value:{format_spec}}', va='center', fontsize=9)


def _scatter_points(dataset, prediction_paths):
    def index(rows):
        result = {}
        for row in rows:
            key = (row['benchmark'], row['candidate_id'])
            if key in result: raise ValueError('duplicate probe identity')
            result[key] = row
        return result
    truth = index(dataset)
    result = {}
    for name, path in prediction_paths.items():
        predictions = index(read(path))
        if set(truth) != set(predictions): raise ValueError('scatter prediction coverage mismatch')
        records = []
        for key, row in truth.items():
            pred = predictions[key]
            if row['formula'] != pred['formula']: raise ValueError('scatter formula mismatch')
            values = [row['lut4_count'], pred['predicted_lut4']]
            if not np.isfinite(values).all() or min(values) < 0:
                raise ValueError('scatter values must be finite and nonnegative')
            records.append({'benchmark': row['benchmark'], 'candidate_id': row['candidate_id'],
                            'stratum': row['stratum'], 'measured_lut4': float(row['lut4_count']),
                            'predicted_lut4': float(pred['predicted_lut4'])})
        result[name] = records
    return result


def render(development_path, output, probe_path=None, probe_dataset=None,
           prediction_paths=None, reference_development=None, seed=20261013,
           bootstrap_draws=10000, timing_paths=None, cold_timing=None, independent_audit=None):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    development = read(development_path)
    reference = read(reference_development) if reference_development else None
    dev = _dev_models(development, reference)
    names = [name for name in MODEL_ORDER if name in dev]
    if set(dev) - set(MODEL_ORDER): raise ValueError('unknown model names')
    programs = sorted(dev['resource_v2']['programs'])
    if any(sorted(dev[name]['programs']) != programs for name in names):
        raise ValueError('development programs differ across comparators')
    if len(programs) != 17: raise ValueError('research comparison requires all 17 programs')
    rng = np.random.default_rng(seed)
    index = rng.integers(0, len(programs), size=(bootstrap_draws, len(programs)))
    interval = {}
    for metric in ('mae_lut4', 'rmsle'):
        interval[metric] = {name: _interval([dev[name]['programs'][p][metric] for p in programs],
                                          bootstrap_draws, index) for name in names}
        if any(not np.isclose(interval[metric][name]['mean'],
                              dev[name]['macro']['macro_program_' + metric]) for name in names):
            raise ValueError('development macro metrics differ from program means')
    base = np.asarray([dev['resource_v2']['programs'][p]['mae_lut4'] for p in programs])
    new = np.asarray([dev['v3_structural']['programs'][p]['mae_lut4'] for p in programs])
    difference = _interval(base - new, bootstrap_draws, index)
    probe = read(probe_path) if probe_path else None
    if probe and set(probe['models']) != set(names):
        raise ValueError('probe/development model comparison coverage differs')
    provenance_paths = {'development_evaluation': development_path}
    if reference_development: provenance_paths['reference_development_evaluation'] = reference_development
    if probe_path: provenance_paths['probe_evaluation'] = probe_path
    if probe_dataset: provenance_paths['probe_dataset'] = probe_dataset
    for name, path in (prediction_paths or {}).items(): provenance_paths['prediction_' + name] = path
    for name, path in (timing_paths or {}).items(): provenance_paths['timing_' + name] = path
    if cold_timing: provenance_paths['masterrtl_cold_timing'] = cold_timing
    if independent_audit: provenance_paths['independent_probe_audit'] = independent_audit
    data = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'model_labels': MODEL_LABELS, 'model_order': names,
            'development_scope': {key: development.get(key) for key in
                                  ('evaluation_status', 'target', 'method', 'training_row_count',
                                   'unique_formula_count', 'training_dataset_sha256', 'limitations')},
            'development': {name: {'macro_metrics': dev[name]['macro'],
                                   'program_metrics': dev[name]['programs']} for name in names},
            'paired_program_bootstrap': {'seed': seed, 'draws': bootstrap_draws,
                                        'interval_type': 'percentile 95%; paired program resampling',
                                        'metrics': interval,
                                        'resource_minus_structural_mae': difference},
            'probe': probe, 'input_files': {name: {'path': str(Path(p).resolve()), 'sha256': sha(p)}
                                           for name, p in provenance_paths.items()},
            'plotting_source_sha256': sha(__file__)}
    data['runtime_versions'] = {'python': platform.python_version(),
                                'matplotlib': matplotlib.__version__, 'numpy': np.__version__}
    if reference:
        data['matched_reference_adaptation'] = {key: reference.get(key) for key in
                                                ('reference_provenance', 'model_config', 'feature_columns',
                                                 'method', 'training_dataset_sha256', 'limitations')}
    captions = {}
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(9.0, 7.5), constrained_layout=True)
        _paired(ax, programs, base, new, 'Program mean absolute error (LUT4)')
        ax.set_title('Paired development errors across all 17 held-out programs', loc='left', pad=14)
        mean_delta = difference['mean']
        fig.suptitle('Resource baseline and structural challenger', x=0.01, ha='left', weight='bold')
        _save(fig, output, '01_program_mae')
        captions['01_program_mae'] = (
            'Each connected pair is one program in nested leave-one-program-out development evaluation; '
            'identical formulas are excluded from training. Programs are ordered by resource-baseline MAE. '
            f'Equal-program mean resource-minus-structural MAE is {mean_delta:.3f} LUT4, '
            f'with a paired program-bootstrap percentile interval [{difference["lower"]:.3f}, '
            f'{difference["upper"]:.3f}]. Positive differences favor the structural pipeline. '
            'All benchmark labels have previously informed development; this is not an untouched test.')
        if 'masterrtl_sog' in dev:
            reference_mae = np.asarray([dev['masterrtl_sog']['programs'][p]['mae_lut4'] for p in programs])
            reference_difference = _interval(reference_mae - new, bootstrap_draws, index)
            data['paired_program_bootstrap']['masterrtl_minus_structural_mae'] = reference_difference
            fig, ax = plt.subplots(figsize=(9.0, 7.5), constrained_layout=True)
            _paired(ax, programs, reference_mae, new, 'Program mean absolute error (LUT4)',
                    baseline='masterrtl_sog')
            ax.set_title('Paired development errors across all 17 held-out programs', loc='left', pad=14)
            fig.suptitle('Matched MasterRTL adaptation and structural challenger',
                         x=0.01, ha='left', weight='bold')
            _save(fig, output, '06_masterrtl_program_mae')
            captions['06_masterrtl_program_mae'] = (
                'Each pair compares the MasterRTL SOG adaptation and structural pipeline on the same '
                'held-out program and mapped LUT4 labels. Both fit the shared development corpus; '
                'the adaptation uses published MasterRTL features/model family, rather than its '
                'published ASIC labels or a published headline error rate. '
                f'Mean adaptation-minus-structural MAE is {reference_difference["mean"]:.3f} LUT4, '
                f'with paired program-bootstrap percentile interval [{reference_difference["lower"]:.3f}, '
                f'{reference_difference["upper"]:.3f}]. Positive differences favor the structural '
                'pipeline. Development labels were previously inspected, and these folds do not '
                'establish superiority on an untouched real-program population.')
        panels = 2 if probe else 1
        fig, axes = plt.subplots(1, panels, figsize=(13.8 if probe else 7.2, 5.5), constrained_layout=True)
        axes = np.atleast_1d(axes)
        vals = [dev[n]['macro']['macro_program_mae_lut4'] for n in names]
        _horizontal_metrics(axes[0], names, vals, interval['mae_lut4'])
        axes[0].set_title('Development: macro program MAE', loc='left', pad=15)
        axes[0].set_xlabel('MAE (LUT4); programs weighted equally')
        if probe:
            vals = [probe['models'][n]['pooled']['mae_lut4'] for n in names]
            _horizontal_metrics(axes[1], names, vals)
            axes[1].set_title('Frozen synthetic probe: circuit MAE', loc='left', pad=15)
            axes[1].set_xlabel('MAE (LUT4); each probe circuit weighted equally')
        fig.suptitle('Matched models, separate evaluation populations', weight='bold')
        _save(fig, output, '02_model_comparison')
        captions['02_model_comparison'] = (
            'Development bars average 17 held-out program errors equally; error bars are 95% percentile '
            f'intervals from paired resampling of those programs ({bootstrap_draws:,} draws, seed {seed}). '
            'These describe sensitivity to the observed program mix, not calibrated predictive uncertainty. '
            'Probe bars average released synthetic circuits and carry no inferential error bars. '
            'The populations and horizontal scales are separate. All models use the same LUT4 target. '
            'The MasterRTL comparator, if present, adapts its published SOG features/model family to this '
            'training corpus and LUT4 target; it is not a reproduction of its published ASIC accuracy.')
        fig, axes = plt.subplots(1, 3 if probe else 2, figsize=(12.5 if probe else 8.5, 4.7), constrained_layout=True)
        ablation_names = ['v3_original', 'v3_structural']
        for ax, metric, title in zip(axes[:2], ('mae_lut4', 'rmsle'),
                                    ('Development macro MAE', 'Development macro RMSLE')):
            vals = [dev[n]['macro']['macro_program_' + metric] for n in ablation_names]
            _horizontal_metrics(ax, ablation_names, vals, interval[metric], short_labels=True)
            ax.set_title(title, loc='left', pad=15)
            ax.set_xlabel('LUT4' if metric == 'mae_lut4' else 'Root mean squared log(1 + LUT4) error')
        if probe:
            _horizontal_metrics(axes[2], ablation_names,
                                [probe['models'][n]['pooled']['mae_lut4'] for n in ablation_names],
                                short_labels=True)
            axes[2].set_title('Frozen probe MAE', loc='left', pad=15); axes[2].set_xlabel('LUT4')
        fig.suptitle('Original and structural pipelines: absolute and log error', weight='bold')
        _save(fig, output, '05_feature_ablation')
        captions['05_feature_ablation'] = (
            'Compare the nested-selected original-feature pipeline with the structural-feature pipeline. '
            'The structural pipeline also uses its improved physical resource baseline, and nested '
            'selection can choose a different learner; this is a pipeline ablation, not an isolated '
            'causal estimate of feature effects. Development intervals use the same paired program '
            'bootstrap as Figure 2; probe bars have no error bars. Absolute and logarithmic errors '
            'can favor different pipelines, so both development outcomes are shown.')
        if probe:
            strata = sorted(probe['models']['resource_v2']['by_stratum'])
            if len(strata) != 8: raise ValueError('research probe requires all eight strata')
            b = np.asarray([probe['models']['resource_v2']['by_stratum'][s]['mae_lut4'] for s in strata])
            n = np.asarray([probe['models']['v3_structural']['by_stratum'][s]['mae_lut4'] for s in strata])
            labels = [s.replace('_', ' ') + f' (n={probe["models"]["resource_v2"]["by_stratum"][s]["sample_count"]})'
                      for s in strata]
            fig, ax = plt.subplots(figsize=(10.0, 5.8), constrained_layout=True)
            _paired(ax, labels, b, n, 'Within-stratum mean absolute error (LUT4)')
            ax.set_title('Every released synthetic probe stratum', loc='left', pad=14)
            fig.suptitle('Resource baseline and structural challenger', x=0.01, ha='left', weight='bold')
            _save(fig, output, '04_probe_strata')
            captions['04_probe_strata'] = (
                'All eight declared probe strata are shown, ordered by baseline MAE, with the number '
                'of circuits stated. No stratum is removed because it favors either model. These '
                'are engineered stress circuits, not independent real programs. No uncertainty '
                'interval is attached to within-stratum averages.')
            if 'masterrtl_sog' in names:
                matched = ('masterrtl_sog', 'v2_residual_xgb', 'v3_structural')
                ordered = sorted(strata, key=lambda s: probe['models']['masterrtl_sog']['by_stratum'][s]['mae_lut4'])
                y = np.arange(len(ordered))
                labels = [s.replace('_', ' ') + f' (n={probe["models"]["masterrtl_sog"]["by_stratum"][s]["sample_count"]})'
                          for s in ordered]
                arrays = {n: np.asarray([probe['models'][n]['by_stratum'][s]['mae_lut4'] for s in ordered])
                          for n in matched}
                limit = max(max(a) for a in arrays.values()) * 1.12
                fig, axes = plt.subplots(1, 2, figsize=(14.2, 6.1), constrained_layout=True)
                for ax in axes:
                    for name, marker, offset in (('v2_residual_xgb', 'o', .08), ('v3_structural', 'D', -.08)):
                        for row, x, ref in zip(y, arrays[name], arrays['masterrtl_sog']):
                            ax.plot([ref, x], [row, row+offset], color='#bdc5cc', linewidth=1, zorder=1)
                        ax.scatter(arrays[name], y+offset, color=COLORS[name], marker=marker,
                                   s=34, label=MODEL_LABELS[name], zorder=3)
                    ax.scatter(arrays['masterrtl_sog'], y, color=COLORS['masterrtl_sog'],
                               marker='^', s=43, label=MODEL_LABELS['masterrtl_sog'], zorder=4)
                    ax.set_yticks(y, labels); ax.set_xlim(0, limit); _grid(ax)
                axes[0].set_title('Full linear range · all eight strata', loc='left', pad=15)
                axes[0].set_xlabel('Within-stratum mean absolute error (LUT4)')
                axes[1].set_xscale('function', functions=(np.log1p, np.expm1))
                axes[1].set_xticks([t for t in (0, 1, 5, 10, 25, 100, 400) if t <= limit])
                axes[1].set_title('Logarithmic view · all eight strata', loc='left', pad=15)
                axes[1].set_xlabel('MAE in LUT4; positions use log(1 + MAE)')
                handles, legend_labels = axes[0].get_legend_handles_labels()
                fig.legend(handles, legend_labels, loc='outside lower center', ncol=3, frameon=False)
                fig.suptitle('Matched probe comparison by declared circuit stratum', weight='bold')
                _save(fig, output, '08_matched_probe_strata')
                captions['08_matched_probe_strata'] = (
                    'All eight fixed synthetic strata (24 circuits each) are shown for MasterRTL SOG '
                    'adaptation, residual XGBoost v2 and the structural v3 pipeline. Each gray segment '
                    'links a comparator mean with the matched MasterRTL mean. Strata are ordered by '
                    'MasterRTL MAE. The left panel retains the full linear range; the right includes '
                    'every same point using log(1 + MAE) spacing with ticks labeled in LUT4 units. '
                    'Multiplication is retained in both views, rather than excluded to enlarge the '
                    'smaller errors. No interval is inferred from these eight within-stratum averages.')
            if probe_dataset and prediction_paths:
                provenance = probe.get('provenance', {})
                if provenance.get('dataset_sha256') != sha(probe_dataset):
                    raise ValueError('scatter dataset hash differs from scored probe')
                for name, path in prediction_paths.items():
                    if provenance.get('prediction_sha256', {}).get(name) != sha(path):
                        raise ValueError('scatter prediction hash differs from scored probe')
                points = _scatter_points(read(probe_dataset), prediction_paths)
                if set(points) != set(names): raise ValueError('scatter must include every compared model')
                for name, records in points.items():
                    if len(records) != probe['candidate_count']:
                        raise ValueError('scatter point count differs from scored probe')
                    mae = np.mean([abs(r['measured_lut4'] - r['predicted_lut4']) for r in records])
                    if not np.isclose(mae, probe['models'][name]['pooled']['mae_lut4']):
                        raise ValueError('scatter errors differ from scored probe')
                data['probe_scatter_points'] = points
                ymax = max(max(r['measured_lut4'], r['predicted_lut4']) for rs in points.values() for r in rs)
                limit = max(10, (ymax + 1) * 1.20)
                fig, axes = plt.subplots(2, 3, figsize=(12.7, 8.5), constrained_layout=True)
                for ax, name in zip(axes.flat, names):
                    records = points[name]; truth = np.asarray([r['measured_lut4'] for r in records])
                    pred = np.asarray([r['predicted_lut4'] for r in records]); zero = truth == 0
                    ax.scatter(truth[~zero] + 1, pred[~zero] + 1, s=23, alpha=0.65,
                               color=COLORS[name], linewidths=0, rasterized=False)
                    ax.scatter(truth[zero] + 1, pred[zero] + 1, s=30, facecolors='none',
                               edgecolors='#222222', linewidths=1, marker='s', zorder=4)
                    ax.plot([1, limit], [1, limit], linestyle='--', color='#8e979f', linewidth=1)
                    ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(0.86, limit); ax.set_ylim(0.86, limit)
                    ax.set_aspect('equal', adjustable='box'); ax.set_title(MODEL_LABELS[name], loc='left')
                    ticks = [1, 2, 11, 101, 1001, 10001]
                    ticks = [t for t in ticks if t <= limit]
                    ax.set_xticks(ticks); ax.set_yticks(ticks)
                    formatter = FuncFormatter(lambda value, position: f'{max(0, value - 1):g}')
                    ax.xaxis.set_major_formatter(formatter); ax.yaxis.set_major_formatter(formatter)
                    ax.minorticks_off(); _grid(ax, 'both')
                    ax.set_xlabel('Measured LUT4'); ax.set_ylabel('Predicted LUT4')
                    zmae = float(pred[zero].mean()) if zero.any() else 0.
                    ax.text(0.04, 0.96, f'n={len(truth)}; true zeros={int(zero.sum())}\n'
                            f'MAE={probe["models"][name]["pooled"]["mae_lut4"]:.2f}; zero MAE={zmae:.2f}',
                            transform=ax.transAxes, va='top', fontsize=8,
                            bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .85, 'pad': 2})
                for ax in list(axes.flat)[len(names):]: ax.set_visible(False)
                fig.suptitle('Frozen synthetic probe predictions · axes use log(1 + LUT4)', weight='bold')
                fig.legend(handles=[Line2D([], [], marker='s', markersize=6, linestyle='none',
                                           markerfacecolor='none', markeredgecolor='#222222', label='True-zero circuits'),
                                    Line2D([], [], linestyle='--', color='#8e979f', label='Perfect prediction')],
                           loc='outside lower center', ncol=2, frameon=False)
                _save(fig, output, '03_probe_scatter')
                captions['03_probe_scatter'] = (
                    'Each panel shows all probe circuits for one frozen model with the same scales. '
                    'Axis coordinates use log(1 + LUT4), but ticks are labeled in LUT4 units; '
                    'true-zero circuits are retained at the left boundary and marked with hollow '
                    'squares. Panel annotations give circuit count, true-zero count, overall MAE, '
                    'and MAE on zero targets. The diagonal denotes perfect predictions. '
                    'Duplicate points can overlap; the archived figure data retains every circuit. '
                    'No point is removed for high error or zero measured area.')
        if timing_paths:
            if not probe or set(timing_paths) != set(names):
                raise ValueError('timing figure requires the released probe and every compared model')
            timings = {name: read(path) for name, path in timing_paths.items()}
            if any(timings[n]['row_count'] != probe['candidate_count'] for n in names):
                raise ValueError('timing batch size differs from evaluated probe')
            hashes = {value.get('candidate_sha256', value.get('candidates_sha256'))
                      for value in timings.values()}
            if None in hashes or len(hashes) != 1:
                raise ValueError('timing model inputs differ')
            cold = read(cold_timing) if cold_timing else None
            if cold and (cold['formula_count'] != probe['candidate_count'] or
                         cold['artifact_sha256'] != timings['masterrtl_sog']['model_sha256']):
                raise ValueError('cold timing uses a different model or input batch size')
            data['inference_timing'] = {'warm_batch_reports': timings, 'masterrtl_cold_report': cold}
            fig, axes = plt.subplots(1, 2 if cold else 1,
                                     figsize=(14.4 if cold else 7.2, 5.7), constrained_layout=True)
            axes = np.atleast_1d(axes)
            values = [timings[n]['median_warm_batch_seconds'] for n in names]
            _horizontal_metrics(axes[0], names, values, format_spec='.3g')
            axes[0].set_title('Warm inference: median of repeated batches', loc='left', pad=15)
            axes[0].set_xlabel('Wall time per full probe batch (seconds)')
            if cold:
                labels = ['MasterRTL: cold graph + ML', 'MasterRTL: immediate warm repeat',
                          'v3 structural: first in-memory batch', 'v3 structural: warm batch median']
                values = [cold['cold_feature_plus_ml_seconds'], cold['warm_cached_feature_plus_ml_seconds'],
                          timings['v3_structural']['first_batch_seconds'],
                          timings['v3_structural']['median_warm_batch_seconds']]
                ax = axes[1]; y = np.arange(len(labels))
                ax.barh(y, values, height=.61, color=[COLORS['masterrtl_sog']]*2 + [COLORS['v3_structural']]*2)
                ax.set_yticks(y, labels); ax.invert_yaxis(); ax.set_xscale('log')
                ax.set_xlim(min(values)*.7, max(values)*1.7)
                ax.set_xlabel('Seconds per batch (logarithmic scale)'); _grid(ax)
                ax.set_title('Different preprocessing requirements', loc='left', pad=15)
                for row, value in zip(y, values): ax.text(value*1.06, row, f'{value:.3g}', va='center', fontsize=9)
            fig.suptitle(f'Measured CPU inference time · all {probe["candidate_count"]} probe formulas', weight='bold')
            _save(fig, output, '07_inference_cost')
            captions['07_inference_cost'] = (
                'Warm bars are recorded medians of repeated fixed-input inference batches, not uncertainty '
                'estimates. All models process the same full formula batch. Model loading, process startup '
                'and input/output JSON serialization are excluded. MasterRTL warm inference includes '
                'cached graph-file IO, integrity checks and traversal; formula models use in-memory '
                'features. The right panel separates a fresh-cache MasterRTL graph extraction plus ML '
                '(one extraction worker), its immediate warm repeat, and the structural model first '
                'in-memory/warm batches. These preprocessing scopes are explicitly different. '
                'Cold and warm MasterRTL predictions are identical according to the retained timing '
                'record. Hardware and cache state affect these CPU wall times; no runtime interval '
                'or end-to-end processor-speedup claim is inferred.')
        if independent_audit:
            if not probe: raise ValueError('independent audit figure requires a released probe evaluation')
            audit = read(independent_audit)
            if audit['input_sha256']['probe_evaluation'] != sha(probe_path):
                raise ValueError('audit evaluated a different probe report')
            if probe_dataset and audit['input_sha256']['measured_dataset'] != sha(probe_dataset):
                raise ValueError('audit used different probe labels')
            for name, path in (prediction_paths or {}).items():
                if audit['input_sha256']['prediction:' + name] != sha(path):
                    raise ValueError('audit used different predictions')
            data['independent_probe_audit'] = {key: audit[key] for key in
                                              ('method', 'created_at_utc', 'prediction_freeze_commit',
                                               'bootstrap', 'input_sha256', 'paired_masterrtl_comparisons',
                                               'positive_target_count', 'zero_target_count', 'limitations')}
            compared = ('v3_structural', 'v2_residual_xgb')
            pairs = audit['paired_masterrtl_comparisons']
            means = np.asarray([pairs[n]['primary_macro_stratum_mae_difference_lut4'] for n in compared])
            intervals = np.asarray([pairs[n]['stratified_paired_bootstrap_95_percentile_interval_lut4']
                                    for n in compared])
            fig, ax = plt.subplots(figsize=(9.2, 4.0), constrained_layout=True)
            y = np.arange(len(compared))
            ax.axvline(0, color='#89929b', linestyle='--', linewidth=1)
            ax.errorbar(means, y, xerr=np.vstack((means-intervals[:, 0], intervals[:, 1]-means)),
                        fmt='D', color=COLORS['masterrtl_sog'], ecolor='#333333', markersize=7,
                        capsize=5, elinewidth=1.4)
            ax.set_yticks(y, [MODEL_LABELS[n] for n in compared]); ax.invert_yaxis()
            span = intervals.max() - intervals.min(); ax.set_xlim(intervals.min()-span*.12,
                                                                intervals.max()+span*.08)
            ax.set_ylim(1.4, -.5); _grid(ax)
            for row, mean, bounds in zip(y, means, intervals):
                ax.text(.98, row-.18, f'{mean:+.2f} [{bounds[0]:+.2f}, {bounds[1]:+.2f}]',
                        transform=ax.get_yaxis_transform(), ha='right', va='bottom', fontsize=10)
            ax.set_xlabel('Comparator MAE − MasterRTL MAE (LUT4); positive favors MasterRTL')
            ax.set_title('Fixed eight strata; paired formula resampling within each stratum', loc='left', pad=14)
            fig.suptitle('Frozen probe: paired mean absolute-error differences', weight='bold')
            fig.legend(handles=[Line2D([], [], marker='D', linestyle='none', color=COLORS['masterrtl_sog'],
                                       label='Paired mean difference'),
                                Line2D([], [], marker='|', linestyle='-', color='#333333',
                                       label='Percentile 95% interval')],
                       loc='outside lower center', ncol=2, frameon=False)
            _save(fig, output, '09_paired_probe_differences')
            captions['09_paired_probe_differences'] = (
                'Points are comparator-minus-MasterRTL absolute-error differences, averaged equally '
                'over the eight fixed declared strata. Positive differences favor MasterRTL. '
                'Intervals come directly from the retained independent audit: 10,000 paired bootstrap '
                'replicates resample 24 candidate pairs with replacement within each fixed stratum, '
                'using the same draws for both models and comparisons (seed 2026101304); bounds are '
                'percentiles 2.5 and 97.5. Programs and strata themselves are not resampled. '
                'These are descriptive conditional formula-level intervals for this curated '
                'synthetic probe. Related graph patterns and pool selection limit inference to '
                'real workloads. The residual-XGBoost comparison interval crosses zero, so the '
                'point estimate alone does not establish clear superiority over that comparator.')
    data['figure_captions'] = dict(sorted(captions.items()))
    (output / 'figure-data.json').write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    lines = ['Research figures: matched isolated iCE40 LUT4 prediction', '',
             'Each figure is supplied as editable SVG, vector PDF, and 300 dpi PNG.',
             'Target: isolated mapped SB_LUT4 count, not ASIC area, timing, power, or CPU speedup.',
             'Development labels were previously inspected; nested folds are development evidence.',
             'Probe inputs must be supplied only after every compared model is frozen.',
             'The synthetic probe tests transfer to declared circuit families, not real workload superiority.',
             'Development intervals: paired resampling of 17 programs; descriptive program-mix sensitivity.',
             'Probe paired-difference intervals: candidate-pair resampling within eight FIXED strata.',
             'Probe intervals are conditional on this curated formula pool; programs/strata are not resampled.',
             'No row, random seed, or engineered probe circuit is treated as an independent program.', '',
             'Reproduction:', '  See invocation.json for the exact CLI and input paths.',
             '  Input SHA-256, complete figure data, bootstrap details, and captions: figure-data.json', '']
    for name, caption in sorted(captions.items()): lines.extend([name, caption, ''])
    (output / 'README.txt').write_text('\n'.join(lines) + '\n')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--reference-development', type=Path)
    parser.add_argument('--probe', type=Path)
    parser.add_argument('--probe-dataset', type=Path)
    parser.add_argument('--prediction', action='append', default=[], help='model_name=JSON file')
    parser.add_argument('--timing', action='append', default=[], help='model_name=timing JSON file')
    parser.add_argument('--masterrtl-cold-timing', type=Path)
    parser.add_argument('--independent-audit', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--bootstrap-draws', type=int, default=10000)
    args = parser.parse_args(argv)
    if args.bootstrap_draws < 1000: parser.error('use at least 1000 bootstrap draws')
    predictions = {}
    for declaration in args.prediction:
        name, path = declaration.split('=', 1)
        if name in predictions: parser.error('duplicate prediction model')
        predictions[name] = Path(path)
    if bool(args.probe_dataset) != bool(predictions):
        parser.error('scatter requires both --probe-dataset and prediction files')
    if (args.probe_dataset or predictions) and not args.probe:
        parser.error('scatter requires --probe evaluation')
    timings = {}
    for declaration in args.timing:
        name, path = declaration.split('=', 1)
        if name in timings: parser.error('duplicate timing model')
        timings[name] = Path(path)
    if args.masterrtl_cold_timing and not timings:
        parser.error('cold timing requires --timing files')
    render(args.development, args.output, args.probe, args.probe_dataset, predictions,
           args.reference_development, args.seed, args.bootstrap_draws, timings,
           args.masterrtl_cold_timing, args.independent_audit)
    import sys
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'invocation.json').write_text(json.dumps({'cwd': str(Path.cwd()),
        'command': [sys.executable, '-m', 'isaforge.challenger_plots', *(argv if argv is not None else sys.argv[1:])]},
        indent=2) + '\n')
    print(f'Research figures saved to {args.output.resolve()}')


if __name__ == '__main__': main()
