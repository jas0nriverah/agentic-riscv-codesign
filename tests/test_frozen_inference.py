import pytest
from isaforge.frozen_inference import infer


def test_inference_never_receives_labels_or_dynamic_features():
    class Model:
        def predict(self, rows):
            assert all(set(row) == {'benchmark', 'candidate_id', 'formula'} for row in rows)
            return [{**row, 'predicted_lut4': 3.0} for row in rows]
    rows = [dict(benchmark='x', candidate_id='id', formula='xor(in0,in1)', lut4_count=123, runs=999)]
    predictions, timing = infer(Model(), rows, repeats=2)
    assert predictions[0]['predicted_lut4'] == 3
    assert 'lut4_count' not in predictions[0]
    assert len(timing['warm_batch_seconds']) == 2


def test_nondeterministic_predictions_rejected():
    class Model:
        calls = 0
        def predict(self, rows):
            self.calls += 1
            return [{'predicted_lut4': self.calls}]
    with pytest.raises(ValueError, match='not deterministic'):
        infer(Model(), [dict(benchmark='x', candidate_id='id', formula='xor(in0,in1)')])
