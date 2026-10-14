"""Independent evaluator checks: denominators, identity integrity, and freezes."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evaluate_v4.py'
spec = importlib.util.spec_from_file_location('evaluate_v4', SCRIPT)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_metrics_keep_zeros_and_define_cap_denominators():
    score = ev.metrics(np.array([0., 16., 17., 32.]), np.array([4., 16., 16., 33.]))
    assert score['mae_lut4'] == 1.5
    assert score['zero_target_mae_lut4'] == 4
    assert score['positive_count'] == 3
    assert score['positive_median_ape_percent'] == pytest.approx(100 / 32)
    cap = score['cap_feasibility']['16']
    assert cap['false_accept_count'] == 1
    assert cap['false_reject_count'] == 0
    assert cap['false_accept_rate_among_true_infeasible'] == .5
    assert cap['infeasible_fraction_among_predicted_feasible'] == pytest.approx(1 / 3)
    assert score['cap_feasibility']['256']['false_accept_rate_among_true_infeasible'] is None


def test_zero_only_metrics_are_defined_without_percentage_error():
    score = ev.metrics(np.array([0., 0.]), np.array([0., 2.]))
    assert score['positive_mape_percent'] is None
    assert score['positive_median_ape_percent'] is None
    assert score['zero_target_mae_lut4'] == 1


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'extra', 'wrong_formula', 'nan', 'negative', 'boolean'])
def test_prediction_integrity(mutation):
    declared = [{'benchmark': 'b', 'candidate_id': 'a', 'formula': 'in0', 'stratum': 's'},
                {'benchmark': 'b', 'candidate_id': 'b', 'formula': 'in1', 'stratum': 's'}]
    rows = [{**r, 'predicted_lut4': 1} for r in declared]
    if mutation == 'duplicate':
        rows.append(rows[0])
    elif mutation == 'missing':
        rows.pop()
    elif mutation == 'extra':
        rows.append({**rows[0], 'candidate_id': 'extra'})
    elif mutation == 'wrong_formula':
        rows[0]['formula'] = 'in1'
    else:
        rows[0]['predicted_lut4'] = {'nan': float('nan'), 'negative': -1, 'boolean': True}[mutation]
    with pytest.raises(ValueError):
        ev.aligned(declared, rows, 'predicted_lut4')


def frozen_fixture(tmp_path):
    def save(name, data):
        p = tmp_path / name
        p.write_text(json.dumps(data))
        return {'path': str(p), 'sha256': ev.sha(p)}

    candidates = [{'benchmark': f'b{i // 32}', 'candidate_id': f'id{i}',
                   'formula': f'formula{i}', 'stratum': f's{i // 32}'} for i in range(256)]
    predictions = [{**r, 'predicted_lut4': i % 33} for i, r in enumerate(candidates)]
    labels = [{**r, 'lut4_count': i % 33, 'correctness_verified': True,
               'measurement_source': 'rtl_synthesis'} for i, r in enumerate(candidates)]
    artifact = save('artifact.json', {'frozen': True})
    source = save('source.json', {'source': True})
    m = {'schema': 'isaforge-v4-freeze-v1', 'candidate_frozen_at_utc': '2026-10-13T00:00:00Z',
         'candidates': save('candidates.json', candidates),
         'development_data': save('development.json', [{'formula': f'dev{i}'} for i in range(1289)]),
         'protocol': {'path': str(ev.PROTOCOL), 'sha256': ev.sha(ev.PROTOCOL)},
         'evaluator': {'path': str(SCRIPT), 'sha256': ev.sha(SCRIPT)},
         'models': {name: {'frozen_at_utc': '2026-10-13T01:00:00Z',
             'predictions': save(f'{name}.json', predictions), 'artifact': artifact,
             'sources': [source]} for name in ev.MODELS}}
    manifest = tmp_path / 'freeze.json'
    manifest.write_text(json.dumps(m))
    release = tmp_path / 'release.json'
    release.write_text(json.dumps({'released_at_utc': '2026-10-13T02:00:00Z',
                                  'dataset': save('labels.json', labels)}))
    return m, manifest, release


def test_complete_holdout_and_pairing_are_order_independent(tmp_path):
    m, manifest, release = frozen_fixture(tmp_path)
    path = Path(m['models']['v4']['predictions']['path'])
    rows = ev.read(path)
    rows.reverse()
    path.write_text(json.dumps(rows))
    m['models']['v4']['predictions']['sha256'] = ev.sha(path)
    manifest.write_text(json.dumps(m))
    report = ev.evaluate(manifest, release)
    assert report['holdout_formula_count'] == 256
    assert report['models']['v4']['primary_macro_stratum_mae_lut4'] == 0
    assert len(report['models']['v4']['candidate_errors']) == 256
    assert report['paired_comparisons']['masterrtl_retrained']['tie_count'] == 256
    assert report['paired_comparisons']['masterrtl_retrained']['descriptive_paired_bootstrap_95_percentile_interval_lut4'] == [0., 0.]


def test_artifact_tampering_blocks_score_before_labels(tmp_path):
    m, manifest, release = frozen_fixture(tmp_path)
    Path(m['models']['v4']['artifact']['path']).write_text('{}')
    release.unlink()
    with pytest.raises(ValueError, match='hash mismatch'):
        ev.evaluate(manifest, release)


def test_release_before_freeze_is_rejected(tmp_path):
    _, manifest, release = frozen_fixture(tmp_path)
    data = ev.read(release)
    data['released_at_utc'] = '2026-10-13T01:00:00Z'
    release.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='precede label release'):
        ev.evaluate(manifest, release)


def test_paired_difference_sign_preserves_a_v4_loss(tmp_path):
    m, manifest, release = frozen_fixture(tmp_path)
    path = Path(m['models']['v4']['predictions']['path'])
    rows = ev.read(path)
    for row in rows:
        row['predicted_lut4'] += 7
    path.write_text(json.dumps(rows))
    m['models']['v4']['predictions']['sha256'] = ev.sha(path)
    manifest.write_text(json.dumps(m))
    report = ev.evaluate(manifest, release)
    paired = report['paired_comparisons']['masterrtl_retrained']
    assert paired['macro_stratum_mae_difference_lut4'] == 7
    assert paired['comparator_smaller_absolute_error_count'] == 256
    assert paired['descriptive_paired_bootstrap_95_percentile_interval_lut4'] == [7., 7.]


def test_holdout_development_overlap_rejected(tmp_path):
    m, manifest, _ = frozen_fixture(tmp_path)
    p = Path(m['development_data']['path'])
    rows = ev.read(p)
    rows[0]['formula'] = 'formula0'
    p.write_text(json.dumps(rows))
    m['development_data']['sha256'] = ev.sha(p)
    manifest.write_text(json.dumps(m))
    with pytest.raises(ValueError, match='occurs in development'):
        ev.validate_freeze(manifest)


def test_validation_reads_no_label_file(tmp_path):
    _, manifest, release = frozen_fixture(tmp_path)
    Path(ev.read(release)['dataset']['path']).unlink()
    release.unlink()
    ev.validate_freeze(manifest)
