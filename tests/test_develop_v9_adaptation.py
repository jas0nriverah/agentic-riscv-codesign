"""Synthetic preparation/replay I/O boundaries; never real V8 labels."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from isaforge import area_model_v6 as v6, area_model_v8 as v8

PATH = Path(__file__).resolve().parents[1] / 'scripts/develop_v9_adaptation.py'
spec = importlib.util.spec_from_file_location('develop_v9_adaptation', PATH)
d = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = d
spec.loader.exec_module(d)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def synthetic_root(tmp_path, monkeypatch):
    root = tmp_path / 'v8'
    root.mkdir()
    program = {'benchmark': 'synthetic', 'family': 'F', 'primary_family': True, 'traceTotalInstructions': 1000}
    rows, records, predictions = [], [], []
    for i in range(8):
        formula = f'addi(in0,{i+1})'
        rows.append({**program, 'candidate_id': str(i), 'formula': formula,
                     'overlapSafeSaved': 100-i, 'runs': i+1, 'unused_target': 'poison'})
        values = [0.] * 455
        values[v8.columns().index('original_gate_count')] = 1.
        records.append({'formula': formula, 'values': values, 'v7_modes': {}, 'unused_target': 'poison'})
        predictions.append({'benchmark': 'synthetic', 'candidate_id': str(i), 'formula': formula,
                            'predicted_lut4': 10., 'upper_lut4': None})
    for name, value in [('rows.json', rows), ('programs.json', [program]),
                         ('features.json', {'columns': list(v8.columns()), 'records': records}),
                         ('points.json', predictions), ('mapping.json', {})]:
        put(root / name, value)
    (root / 'mapping.joblib').write_bytes(b'synthetic-model-not-a-real-fit')
    seal = {'runtime_source_sha256': v8.source_hashes(),
            'rows': d.record(root / 'rows.json', root),
            'features': d.record(root / 'features.json', root),
            'files': [d.record(root / 'programs.json', root)]}
    put(root / 'input-seal.json', seal)
    freeze = {'point_only': True, 'new_estimator_fits': 2, 'models': {'mapping_v6': {
        'artifact': d.record(root / 'mapping.joblib', root),
        'schema': d.record(root / 'mapping.json', root),
        'predictions': d.record(root / 'points.json', root)}}}
    put(root / 'point-freeze.json', freeze)

    class FakeEstimator:
        def apply(self, selected):
            assert selected.shape == (8, 217)
            return np.zeros((8, 300), dtype=int)

    class FakeModel:
        kind = 'mapping_v6'
        calibration = {'status': 'uncalibrated'}
        estimator = FakeEstimator()
        def predict_features(self, inputs, x):
            assert x.shape == (8, 336)
            return [{'predicted_lut4': 10.} for _ in inputs]

    monkeypatch.setattr(v6, 'load_model', lambda _: FakeModel())
    return root


def test_actual_read_guard_blocks_label_and_evaluation_file_opens(tmp_path):
    for name in ('evaluation.json', 'measurements/attempt-0000/labels.json', 'training/training-data.json'):
        put(tmp_path / name, {'secret': 100})
    put(tmp_path / 'features.json', {'public': True})
    with d.public_input_guard(tmp_path):
        assert d.read(tmp_path / 'features.json') == {'public': True}
        for name in ('evaluation.json', 'measurements/attempt-0000/labels.json', 'training/training-data.json'):
            with pytest.raises(RuntimeError, match='forbids target/evaluation'):
                d.read(tmp_path / name)
    assert d.read(tmp_path / 'evaluation.json') == {'secret': 100}


def test_preparation_is_label_blind_manifest_first_and_immutable(tmp_path, monkeypatch):
    root = synthetic_root(tmp_path, monkeypatch)
    put(root / 'evaluation.json', {'poison': True})
    put(root / 'measurements/attempt-0000/labels.json', {'poison': True})
    output = tmp_path / 'prepared'
    writes, original_write = [], d.write
    def recording_write(path, value):
        writes.append(Path(path).name)
        original_write(path, value)
    monkeypatch.setattr(d, 'write', recording_write)
    manifest = d.prepare(root, output)
    assert writes == ['preparation.json', 'public-prepared.json']
    assert manifest['application_labels_read'] is manifest['application_evaluation_read'] is False
    _, value = d.load_prepared(output)
    assert len(value['selected_mapping_columns']) == 217
    assert len(value['leaf_ids'][0]) == 300
    assert all('unused_target' not in r for r in value['rows'])
    with pytest.raises(ValueError, match='immutable'):
        d.prepare(root, output)
    # A bound file mutation cannot be silently accepted at evaluation time.
    (root / 'rows.json').write_text('[]\n')
    with pytest.raises(ValueError, match='Bound input changed'):
        d.load_prepared(output)


def test_evaluation_review_gate_sequential_forecasts_then_scoring(tmp_path, monkeypatch):
    root = synthetic_root(tmp_path, monkeypatch)
    prepared_dir = tmp_path / 'prepared'
    d.prepare(root, prepared_dir)
    output = tmp_path / 'evaluated'
    review = tmp_path / 'review.json'
    put(review, {'status': 'unapproved'})
    with pytest.raises(ValueError, match='parent release'):
        d.evaluate(prepared_dir, output, review)
    assert not output.exists()
    labels_path = root / 'measurements/attempt-0000/labels.json'
    put(labels_path, [{'formula': f'addi(in0,{i+1})', 'lut4_count': 12, 'unused_metadata': -999} for i in range(8)])
    put(root / 'measurements/completion.json', {'complete': True, 'failures': [], 'attempt': 'attempt-0000',
                                               'labels_sha256': d.sha(labels_path)})
    put(review, {'status': 'approved-consumed-development-replay',
                 'preparation_sha256': d.sha(prepared_dir / 'preparation.json'),
                 'public_payload_sha256': d.sha(prepared_dir / 'public-prepared.json')})
    writes, original_write = [], d.write
    def recording_write(path, value):
        writes.append(Path(path).name)
        original_write(path, value)
    monkeypatch.setattr(d, 'write', recording_write)
    result = d.evaluate(prepared_dir, output, review)
    assert writes == ['evaluation-start.json', 'unqueried-forecasts.json', 'evaluation.json', 'completion.json']
    assert result['costs']['simulated_family_query_reveals'] == 5
    assert result['costs']['new_physical_measurements'] == result['costs']['new_estimator_fits'] == 0
    forecasts = d.read(output / 'unqueried-forecasts.json')
    assert len(forecasts['query_log']) == 5
    assert result['primary']['local_minus_frozen_mae_lut4'] == pytest.approx(-1.5)
    assert d.read(output / 'completion.json')['complete'] is True
    with pytest.raises(ValueError, match='immutable'):
        d.evaluate(prepared_dir, output, review)
