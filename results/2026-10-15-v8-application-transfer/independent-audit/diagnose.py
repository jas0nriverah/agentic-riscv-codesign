"""Post-release descriptive error concentration; no fitting or policy changes."""
from collections import defaultdict
import json
from pathlib import Path
import audit

ROOT = Path('../agentic-riscv-codesign/results/2026-10-15-v8-application-transfer').resolve()


def has_inputs(node):
    if isinstance(node, tuple):
        return any(has_inputs(child) for child in node[1:])
    return node in ('in0', 'in1')


def operations(node):
    if not isinstance(node, tuple):
        return []
    return [node] + [n for child in node[1:] for n in operations(child)]


def group(formula):
    nodes = operations(audit.parse(formula))
    if any(n[0] in ('mulh', 'mulhu', 'mulhsu') for n in nodes):
        return 'multiply_high'
    if any(n[0] == 'mul' and any(not has_inputs(c) for c in n[1:]) for n in nodes):
        return 'constant_operand_low_multiply'
    if any(n[0] == 'mul' for n in nodes):
        return 'variable_operand_low_multiply'
    return 'no_multiply'


def main():
    result = audit.read('result-audit.json')
    readiness = audit.read('prelabel-readiness.json')
    audit.need(audit.file_digest('audit.py') == readiness['audit_source_sha256'] == result['input_hashes']['audit_source_sha256'],
               'Prepared/first-run audit source identity differs')
    rows = audit.read(ROOT / 'rows.json')
    freeze = audit.read(ROOT / 'point-freeze.json')
    done = audit.read(ROOT / 'measurements/completion.json')
    labels = audit.read(ROOT / 'measurements' / done['attempt'] / 'labels.json')
    actual = {r['formula']: r['lut4_count'] for r in labels}
    novelty = {r['formula']: r for r in audit.read(ROOT / 'novelty.json')['records']}
    training = audit.read(ROOT / 'training/training-data.json')['rows']
    training_areas = [r['lut4_count'] for r in training]
    groups = {r['formula']: group(r['formula']) for r in rows}
    prediction_points = {}
    for model in audit.MODELS:
        records = audit.read(ROOT / freeze['models'][model]['predictions']['path'])
        prediction_points[model] = {(r['benchmark'], r['candidate_id']): r['predicted_lut4'] for r in records}
    by_model = {}
    for model in audit.MODELS:
        enriched = []
        for row in rows:
            point = prediction_points[model][row['benchmark'], row['candidate_id']]
            enriched.append({**{k: row[k] for k in ('benchmark', 'family', 'candidate_id', 'formula', 'overlapSafeSaved', 'primary_family')},
                'actual_lut4': actual[row['formula']], 'predicted_lut4': point,
                'residual_lut4': point - actual[row['formula']],
                'absolute_error_lut4': abs(point - actual[row['formula']]),
                'multiply_group': groups[row['formula']],
                'strict_no_declared_match': novelty[row['formula']]['strict_no_declared_match']})
        primary = [r for r in enriched if r['primary_family']]
        total_ae = sum(r['absolute_error_lut4'] for r in primary)
        grouped = {}
        for name in sorted(set(r['multiply_group'] for r in primary)):
            selected = [r for r in primary if r['multiply_group'] == name]
            ae = sum(r['absolute_error_lut4'] for r in selected)
            grouped[name] = {'primary_rows': len(selected), 'mae_lut4': ae / len(selected),
                'total_absolute_error_lut4': ae, 'share_primary_pooled_absolute_error': ae / total_ae}
        video_ae = sum(r['absolute_error_lut4'] for r in primary if r['family'] == 'video')
        family_mae_total = sum(v['equal_program_mae_lut4'] for v in result['scores'][model]['by_family'].values() if v['primary_family'])
        false_accept = [r for r in primary if r['predicted_lut4'] <= 64 < r['actual_lut4']]
        false_reject = [r for r in primary if r['actual_lut4'] <= 64 < r['predicted_lut4']]
        by_model[model] = {'primary_equal_family_mae_lut4': result['scores'][model]['primary_equal_family_mae_lut4'],
            'pooled_primary_mae_lut4': total_ae / len(primary),
            'video_share_primary_pooled_absolute_error': video_ae / total_ae,
            'video_share_primary_family_macro_mae': result['scores'][model]['by_family']['video']['equal_program_mae_lut4'] / family_mae_total,
            'multiply_groups': grouped,
            'worst_primary_rows': sorted(primary, key=lambda r: (-r['absolute_error_lut4'], r['formula']))[:10],
            'cap64_false_accepts': false_accept, 'cap64_false_rejects': false_reject,
            'primary_zero_target_error': result['scores'][model]['pooled_primary_application_rows']['zero_mae_lut4']}
    decisive = []
    indexed_rows = {r['candidate_id']: r for r in rows}
    for case in result['selection']['details']:
        if case['strategy'] != 'predicted_area_feasible_merit' or case['seed'] != audit.SEEDS[0]:
            continue
        if case['selected_overlapSafeSaved'] == case['oracle_overlapSafeSaved']:
            continue
        oracle = indexed_rows[case['oracle_candidate_id']]
        decisive.append({**case, 'oracle_formula': oracle['formula'],
            'oracle_actual_lut4': actual[oracle['formula']],
            'oracle_predicted_lut4': prediction_points[case['model']][oracle['benchmark'], oracle['candidate_id']]})
    summary = {'schema': 'independent-v8-post-release-error-concentration-v1',
        'scope': 'Descriptive post-release development evidence; no fitted model, changed policy, fresh generalization claim, or calibrated safety claim.',
        'first_run_source_matches_prelabel_source': True,
        'first_run_audit_sha256': audit.file_digest('result-audit.json'),
        'first_run_log_sha256': audit.file_digest('first-run.log'),
        'primary_rows': 150, 'unique_physical_targets': len(actual),
        'unique_actual_lut4_range': [min(actual.values()), max(actual.values())],
        'unique_zero_targets': sum(v == 0 for v in actual.values()),
        'primary_zero_target_rows': sum(r['primary_family'] and actual[r['formula']] == 0 for r in rows),
        'training_lut4_range': [min(training_areas), max(training_areas)],
        'fresh_unique_targets_above_training_max': sum(v > max(training_areas) for v in actual.values()),
        'by_model': by_model,
        'primary_acquisition_failures_one_representative_seed': decisive,
        'all_merit_cap64_budget1_cases_match_oracle': all(r['selected_overlapSafeSaved'] == r['oracle_overlapSafeSaved']
            for r in result['selection']['details'] if r['strategy'] == 'merit'),
        'primary': result['primary']}
    Path('error-concentration.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('by_model', 'primary_acquisition_failures_one_representative_seed')}, indent=2))
    for model, record in by_model.items():
        print(model, json.dumps({k: v for k, v in record.items() if k not in ('worst_primary_rows', 'cap64_false_accepts', 'cap64_false_rejects')}, sort_keys=True))
    print('DECISIVE', json.dumps(decisive, indent=2))


if __name__ == '__main__':
    main()
