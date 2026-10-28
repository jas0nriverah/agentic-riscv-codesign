#!/usr/bin/env python3
"""Audit frozen r5 model predictions against the held-out tiny-regex outcomes.

Post-label diagnostic only: reads archived predictions and outcomes, never
refits a model, feeds labels back into selection, or changes the sealed study.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import kendalltau, spearmanr
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c

STUDY = 'results/2026-10-28-tiny-regex-c-selection-r2'
PREREG = 'results/2026-10-28-tiny-regex-c-selector-prereg-r5'
STUDY_MANIFEST_SHA256 = '61418b0f56626bd831223a9249159744d364996e3cfadf4a28510a041c368e37'
PREREG_MANIFEST_SHA256 = '5d65ad1a28490f3d30f8b8d5f7b07e0a0a2805f9b7e252cae9a545981247d6a0'
DEFAULT_OUTPUT = 'reports/2026-10-28-tiny-regex-model-diagnostics-r1'
AREA_CAP = 64
MIN_FMAX_MHZ = 12.0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def read(path):
    return json.loads(Path(path).read_text())


def authenticate(root, expected):
    root = Path(root).resolve()
    require(sha(root / 'manifest.json') == expected, 'Pinned manifest changed')
    require((root / 'manifest.json.sha256').read_text().strip() == expected,
            'Manifest sidecar differs')
    inventory = read(root / 'manifest.json')
    require(isinstance(inventory, dict) and inventory, 'Nonempty inventory required')
    for name, expected_hash in inventory.items():
        member = (root / name).resolve()
        require(member.is_relative_to(root) and member.is_file(),
                'Invalid manifest member: ' + name)
        require(sha(member) == expected_hash, 'Member hash mismatch: ' + name)
    return inventory


def feasible(row):
    return (row.get('status', 'success') == 'success' and
            row.get('correctness_verified') is True and
            row.get('device_fits') is True and
            row['area_delta_lut4'] <= AREA_CAP and
            row['routed_fmax_min_mhz'] >= MIN_FMAX_MHZ)


def analyze(root=ROOT):
    root = Path(root).resolve()
    study_root, prereg_root = root / STUDY, root / PREREG
    study_inventory = authenticate(study_root, STUDY_MANIFEST_SHA256)
    prereg_inventory = authenticate(prereg_root, PREREG_MANIFEST_SHA256)
    require({'study-report.json', 'outcomes.json'} <= study_inventory.keys(),
            'Missing sealed study data')
    required_prereg = {'preregistration.json', 'agent-predictions.json',
        'agent-model-metadata.json', 'selection/feasibility-predictions.json',
        'inputs/public.json'}
    require(required_prereg <= prereg_inventory.keys(), 'Missing frozen prediction data')
    prereg = read(prereg_root / 'preregistration.json')
    report = read(study_root / 'study-report.json')
    require(prereg['target_labels_read'] == prereg['target_labels_observed'] == 0 and
            prereg['candidate_attempts_before_fit'] == 0,
            'Predictions must come from a zero-label preregistration')
    require(report['preregistration_manifest_sha256'] == PREREG_MANIFEST_SHA256 and
            report['complete_measured_reference_pool'] is True and
            not report['reference_censored_candidates'],
            'Complete study bound to exact zero-label preregistration required')

    public = read(prereg_root / 'inputs/public.json')
    outcomes = read(study_root / 'outcomes.json')
    require(len(public) == len(outcomes) == 12, 'Expected twelve candidates')
    by_public = {row['candidate_id']: row for row in public}
    by_outcome = {row['candidate_id']: row for row in outcomes}
    require(set(by_public) == set(by_outcome), 'Target candidate identities differ')

    predictions = read(prereg_root / 'agent-predictions.json')
    seed0 = next((row for row in predictions if row['seed'] == 0), None)
    require(seed0 is not None and len(seed0['rows']) == 12, 'Seed-0 ranker roster required')
    rank = {row['candidate_id']: row for row in seed0['rows']}
    feasibility_predictions = read(prereg_root / 'selection/feasibility-predictions.json')
    probability_seed0 = next((row for row in feasibility_predictions
                              if row['seed'] == 0), None)
    require(probability_seed0 is not None, 'Seed-0 feasibility roster required')
    probability_rows = probability_seed0['by_cap'][str(AREA_CAP)]
    probabilities = {row['candidate_id']: row for row in probability_rows}
    require(set(rank) == set(probabilities) == set(by_public),
            'Prediction candidate identities differ')

    rows = []
    for candidate_id, candidate in by_public.items():
        outcome = by_outcome[candidate_id]
        rank_prediction = rank[candidate_id]
        feasibility_prediction = probabilities[candidate_id]
        rows.append(dict(candidate_id=candidate_id, formula=outcome['formula'],
            pairwise_rank_position=rank_prediction['pairwise_rank_position'],
            pairwise_rank_score=rank_prediction['pairwise_rank_score'],
            feasibility_score=feasibility_prediction['feasibility_score_mean'],
            feasibility_disagreement=feasibility_prediction['feasibility_score_std'],
            probability_calibrated=feasibility_prediction.get('calibrated', False),
            observed_feasible=feasible(outcome),
            area_delta_lut4=outcome['area_delta_lut4'],
            routed_fmax_min_mhz=outcome['routed_fmax_min_mhz'],
            correctness_verified=outcome['correctness_verified'],
            baseline_cycles=outcome['baseline_cycles'],
            candidate_cycles=outcome['candidate_cycles'],
            measured_saved_cycles=outcome['baseline_cycles'] - outcome['candidate_cycles'],
            measured_cycle_reduction=1 - outcome['candidate_cycles'] / outcome['baseline_cycles'],
            measured_speedup=outcome['speedup'],
            analytic_estimated_saved_cycles=candidate['latency_features']['estimated_saved_cycles'],
            analytic_minus_measured_saved_cycles=(
                candidate['latency_features']['estimated_saved_cycles'] -
                (outcome['baseline_cycles'] - outcome['candidate_cycles']))))
    rows.sort(key=lambda row: (row['pairwise_rank_position'], row['candidate_id']))

    labels = np.asarray([int(row['observed_feasible']) for row in rows], dtype=int)
    probs = np.asarray([row['feasibility_score'] for row in rows], dtype=float)
    require(np.all(np.isfinite(probs)) and np.all((probs >= 0) & (probs <= 1)),
            'Feasibility scores must be finite in [0,1]')
    require(len(set(labels)) == 2, 'Both feasibility outcomes are needed for these metrics')
    measured_speedups = np.asarray([row['measured_speedup'] for row in rows])
    rank_positions = np.asarray([row['pairwise_rank_position'] for row in rows])
    prevalence = float(labels.mean())
    brier = float(brier_score_loss(labels, probs))
    prevalence_brier = prevalence * (1 - prevalence)
    threshold = 0.5
    predicted_feasible = probs >= threshold
    tp = int(np.sum(predicted_feasible & (labels == 1)))
    fp = int(np.sum(predicted_feasible & (labels == 0)))
    tn = int(np.sum(~predicted_feasible & (labels == 0)))
    fn = int(np.sum(~predicted_feasible & (labels == 1)))
    rank_order = sorted(rows, key=lambda row: row['pairwise_rank_position'])
    oracle = max((row for row in rows if row['observed_feasible']),
                 key=lambda row: (row['measured_speedup'], -row['area_delta_lut4'],
                                  row['candidate_id']))
    fastest = max(rows, key=lambda row: row['measured_speedup'])
    top_k = []
    for k in (1, 2, 3):
        prefix = rank_order[:k]
        feasible_prefix = [row for row in prefix if row['observed_feasible']]
        best = max(feasible_prefix, key=lambda row: row['measured_speedup']) if feasible_prefix else None
        top_k.append(dict(k=k,
            first_feasible_candidate_id=next(
                (row['candidate_id'] for row in prefix if row['observed_feasible']), None),
            best_feasible_speedup=best['measured_speedup'] if best else 1.0,
            oracle_candidate_seen=any(row['candidate_id'] == oracle['candidate_id']
                                      for row in prefix),
            cycle_reduction_regret=oracle['measured_cycle_reduction'] -
                (best['measured_cycle_reduction'] if best else 0.0)))
    residuals = [row['analytic_minus_measured_saved_cycles'] for row in rows]
    metadata = read(prereg_root / 'agent-model-metadata.json')
    metadata = metadata if isinstance(metadata, list) else [metadata]
    meta0 = next((row for row in metadata
                  if row.get('pairwise_ranker', {}).get('seed') == 0), None)
    require(meta0 is not None, 'Seed-0 model metadata required')
    model_timing = meta0.get('model_fit_and_prediction_seconds', {})
    return dict(schema='isaforge-tiny-regex-frozen-model-diagnostic-v1',
        scope='post-label audit of a complete held-out target pool; no refit or label feedback',
        inputs=dict(study=STUDY, study_manifest_sha256=STUDY_MANIFEST_SHA256,
            preregistration=PREREG, preregistration_manifest_sha256=PREREG_MANIFEST_SHA256,
            study_members_authenticated=len(study_inventory),
            preregistration_members_authenticated=len(prereg_inventory),
            prelabel_commit=report['prelabel_commit']),
        model=dict(training_rows=meta0['training_rows'],
            training_workload_groups=len(meta0['training_workload_groups']),
            target_workload_group=meta0['target_workload_group'],
            target_formula_families=len(meta0['target_formula_families']),
            ranker=meta0['pairwise_ranker'],
            feasibility_model=meta0['factorized_feasibility'],
            uncertainty_calibrated=meta0['uncertainty_calibrated'],
            fit_and_prediction_seconds=model_timing),
        target=dict(candidate_count=len(rows),
            correctness_passed=sum(row['correctness_verified'] is True for row in rows),
            feasible_count=int(labels.sum()), area_cap_lut4=AREA_CAP,
            minimum_fmax_mhz=MIN_FMAX_MHZ,
            measured_oracle_candidate_id=oracle['candidate_id'],
            measured_oracle_speedup=oracle['measured_speedup'],
            measured_oracle_cycle_reduction=oracle['measured_cycle_reduction'],
            fastest_unconstrained_candidate=dict(candidate_id=fastest['candidate_id'],
                speedup=fastest['measured_speedup'], area_delta_lut4=fastest['area_delta_lut4'],
                feasible=fastest['observed_feasible']),
            pairwise_rank_position_of_oracle=oracle['pairwise_rank_position'],
            pairwise_rank_position_of_fastest=fastest['pairwise_rank_position']),
        ranking=dict(spearman_rank_vs_speedup=float(spearmanr(
                -rank_positions, measured_speedups).statistic),
            kendall_tau_vs_speedup=float(kendalltau(
                -rank_positions, measured_speedups).statistic),
            top_k_feasible_performance=top_k,
            interpretation='One workload and twelve correlated candidates; descriptive only. Rank scores are ordinal, not speedup magnitudes.'),
        feasibility=dict(brier_score=brier, prevalence_baseline_brier=prevalence_brier,
            brier_skill_vs_prevalence=(1-brier/prevalence_brier) if prevalence_brier else None,
            log_loss=float(log_loss(labels, probs, labels=[0, 1])),
            roc_auc=float(roc_auc_score(labels, probs)),
            average_precision=float(average_precision_score(labels, probs)),
            threshold=threshold, confusion=dict(true_positive=tp, false_positive=fp,
                true_negative=tn, false_negative=fn),
            min_score=float(probs.min()), max_score=float(probs.max()),
            interpretation='The model was explicitly uncalibrated before labels. One small workload sample; do not tune a threshold from it.'),
        analytic_latency=dict(max_abs_saved_cycle_residual=max(map(abs, residuals)),
            exact_residual_count=sum(value == 0 for value in residuals), rows=len(residuals),
            interpretation='Analytic estimated cycle savings exactly matched the measured deltas on this pool. This is a deterministic feature/baseline result, not evidence that XGBoost predicts speedup magnitude.'),
        actual_agent=dict(attempted_ids=report['agent']['attempted_ids'],
            charged_attempts=report['agent']['charged_attempts'],
            selected_id=report['agent']['selected_id'],
            selected_speedup=report['agent']['selected_measured_speedup'],
            measurement_seconds=report['agent']['target_measurement_seconds'],
            provider_calls=report['agent'].get('provider_calls'),
            model_latency_tokens='Unavailable for cooperative Codex relay; measurement time is not model latency.'),
        rows=rows, superiority_established=False, training_rows_added=0,
        model_refits=0, native_jobs=0)


def render_csv(summary):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(summary['rows'][0]))
    writer.writeheader()
    writer.writerows(summary['rows'])
    return stream.getvalue().encode()


def render_plot(summary):
    rows = summary['rows']
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.8), constrained_layout=True)
    ax = axes[0]
    for feasible_value, color, label, marker in (
            (True, '#197c66', 'Measured feasible', 'o'),
            (False, '#c35c57', 'Measured infeasible', 'X')):
        subset = [row for row in rows if row['observed_feasible'] is feasible_value]
        center = 1 if feasible_value else 0
        offsets = np.linspace(-.18, .18, len(subset)) if len(subset) > 1 else [0]
        ax.scatter([row['feasibility_score'] for row in subset],
            [center + offset for offset in offsets], s=72, c=color, marker=marker,
            edgecolors='white', linewidths=.7, label=label, zorder=3)
        for row, offset in zip(subset, offsets):
            ax.annotate(row['candidate_id'][:4],
                (row['feasibility_score'], center + offset),
                xytext=(4, 4), textcoords='offset points', fontsize=7, color='#25364a')
    ax.axvline(.5, color='#44566c', linestyle='--', linewidth=1.1,
               label='0.5 classification threshold')
    ax.set_xlim(0, 1)
    ax.set_ylim(-.32, 1.32)
    ax.set_yticks([0, 1], ['Infeasible', 'Feasible'])
    ax.set_xlabel('Frozen model feasibility score (uncalibrated)')
    ax.set_title(f"Area/timing feasibility | Brier {summary['feasibility']['brier_score']:.3f}")
    ax.grid(axis='x', color='#d9e0e8', linewidth=.7)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc='upper center')

    ax = axes[1]
    for feasible_value, color, label, marker in (
            (True, '#197c66', 'Measured feasible', 'o'),
            (False, '#c35c57', 'Measured infeasible', 'X')):
        subset = [row for row in rows if row['observed_feasible'] is feasible_value]
        ax.scatter([row['pairwise_rank_position'] for row in subset],
            [100*row['measured_cycle_reduction'] for row in subset], s=72,
            c=color, marker=marker, edgecolors='white', linewidths=.7, label=label, zorder=3)
        for row in subset:
            ax.annotate(row['candidate_id'][:4],
                (row['pairwise_rank_position'], 100*row['measured_cycle_reduction']),
                xytext=(4, 4), textcoords='offset points', fontsize=7, color='#25364a')
    ax.axvline(summary['target']['pairwise_rank_position_of_fastest'],
               color='#c35c57', linestyle=':', linewidth=1.2)
    ax.axvline(summary['target']['pairwise_rank_position_of_oracle'],
               color='#197c66', linestyle='--', linewidth=1.2)
    ax.set_xticks(range(1, len(rows)+1))
    ax.set_xlabel('XGBoost predicted rank (1 = first)')
    ax.set_ylabel('Measured whole-program cycle reduction (%)')
    ax.set_title('Ordinal speedup ranking | feasibility matters')
    ax.text(.98, .97, 'Dashed: feasible oracle rank  •  Dotted: raw-fastest rank',
            transform=ax.transAxes, va='top', ha='right', fontsize=7.5, color='#506176')
    ax.grid(axis='both', color='#d9e0e8', linewidth=.7)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc='lower left')
    output = io.BytesIO()
    fig.savefig(output, format='png', dpi=220, facecolor='white')
    plt.close(fig)
    return output.getvalue()


def render_readme(summary):
    f, r, a, target = (summary['feasibility'], summary['ranking'],
                       summary['analytic_latency'], summary['target'])
    fp = f['confusion']['false_positive']
    predicted_feasible = fp + f['confusion']['true_positive']
    rank_fast = target['pairwise_rank_position_of_fastest']
    rank_oracle = target['pairwise_rank_position_of_oracle']
    def ordinal(n):
        return f"{n}{'th' if 10 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"
    lines = ['# Frozen tiny-regex-c model diagnostic', '',
        'This is a post-label audit of the zero-label r5 predictions against the complete r2 target pool. '
        'No model was refit and no target outcome entered training.', '',
        '## What the model predicted', '',
        f"- XGBoost pairwise ranker: {summary['model']['training_rows']} historical rows across "
        f"{summary['model']['training_workload_groups']} groups; target workload and "
        f"{summary['model']['target_formula_families']} exact expression families were excluded. "
        'It predicts ordering, not speedup magnitude.',
        f"- The analytic latency feature supplied the cycle-benefit estimate; it matches all "
        f"{a['exact_residual_count']} observed cycle deltas here. This is a deterministic feature check on one pool, "
        'not learned magnitude prediction.',
        f"- Feasibility output was explicitly uncalibrated. Seed-0 Brier is {f['brier_score']:.3f} versus "
        f"{f['prevalence_baseline_brier']:.3f} for a prevalence-only baseline; ROC AUC is {f['roc_auc']:.3f}. "
        f"At the illustrative 0.5 cutoff, it predicts {predicted_feasible}/12 feasible and has {fp} false positives. "
        'Do not tune a threshold to these twelve labels.',
        '',
        '## Held-out result', '',
        f"- Pairwise rank versus measured speedup: Spearman {r['spearman_rank_vs_speedup']:.3f}, "
        f"Kendall tau {r['kendall_tau_vs_speedup']:.3f} on twelve candidates from one related-domain workload.",
        f"- The raw-fastest design ranked {ordinal(rank_fast)} but exceeded the +64 LUT4 cap. "
        f"The feasible oracle ranked {ordinal(rank_oracle)} and was found after two measurements.",
        f"- Feasible oracle: {target['measured_oracle_speedup']:.6f}× speedup, "
        f"{100*target['measured_oracle_cycle_reduction']:.4f}% cycle reduction.",
        '- These target metrics are descriptive; candidate rows from one source are correlated and do not estimate independent-workload generalization.',
        '',
        '## Next model work', '',
        'The evidence points to better feasibility calibration and new measured outcomes across workloads, not another speedup-regression family. '
        'Keep XGBoost frozen until fresh eligible labels support a preregistered grouped evaluation. Host verification remains authoritative for area and timing.',
        '',
        'The agent reached the oracle at two measurements and tied merit, calibrated latency, pairwise XGBoost, and factorized XGBoost. '
        'This diagnostic does not establish model or agent superiority.', '',
        '![Frozen model diagnostics](heldout-model-diagnostics.png)', '',
        'Reproduce into a fresh directory or verify exact outputs with scripts/report_tiny_regex_model_diagnostics.py.', '']
    return '\n'.join(lines).encode()


def artifacts(summary):
    content = {'model-diagnostics.json': encoded(summary),
        'candidate-diagnostics.csv': render_csv(summary),
        'README.md': render_readme(summary),
        'heldout-model-diagnostics.png': render_plot(summary)}
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in content.items()}
    content['manifest.json'] = encoded(manifest)
    content['manifest.json.sha256'] = (hashlib.sha256(content['manifest.json']).hexdigest() + '\n').encode()
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path)
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    summary = analyze()
    content = artifacts(summary)
    destination = (args.verify or args.output or ROOT / DEFAULT_OUTPUT).resolve()
    require(not destination.is_relative_to((ROOT / 'results').resolve()),
            'Output cannot overwrite source evidence')
    if args.verify:
        require(destination.is_dir() and {path.name for path in destination.iterdir()} == set(content),
                'Output inventory differs')
        for name, value in content.items():
            require((destination / name).read_bytes() == value, 'Exact reproduction mismatch: ' + name)
        print('Verified pinned model predictions/outcomes and exact diagnostic outputs.')
    else:
        require(not destination.exists(), 'Use a fresh output directory')
        destination.mkdir(parents=True)
        for name, value in content.items():
            (destination / name).write_bytes(value)
        print(f'Wrote frozen-model diagnostics to {destination}')


if __name__ == '__main__':
    main()
