"""Current-screen model adapter tests; no target labels or hardware are used."""
import copy

import pytest

from isaforge.current_grouped_predictions import fit_current_grouped_predictions
from isaforge.speedup_corpus import family
from test_budgeted_selection import history, measured, public


def target_pool():
    return [public('t1', 'add(in0,slli(in1,1))'),
            public('t2', 'sub(in0,slli(in1,1))'),
            public('t3', 'add(in0,srli(in1,1))')]


def run_fit(training=None):
    target = target_pool()
    if training is None:
        training = history()
        training[2] = measured(public('h3', 'or(in0,slli(in1,1))', 'old2:ctx'),
                               area=48, savings=20)
    return fit_current_grouped_predictions(training, target,
        target_workload_group='target',
        target_formula_families=[family(row['formula']) for row in target], seed=0)


def test_current_grouped_predictions_are_label_free_and_provenance_bound():
    bundle, metadata = run_fit()
    assert bundle['schema'] == metadata['schema']
    assert len(bundle['rows']) == 3
    assert len({row['pairwise_rank_position'] for row in bundle['rows']}) == 3
    assert sorted(row['pairwise_rank_position'] for row in bundle['rows']) == [1, 2, 3]
    assert all(0 <= row['factorized_feasibility_probability'] <= 1
               for row in bundle['rows'])
    assert all(row['factorized_feasibility_disagreement'] >= 0
               for row in bundle['rows'])
    assert all(set(row) == {
        'candidate_id', 'pairwise_rank_score', 'pairwise_rank_position',
        'factorized_feasibility_probability', 'factorized_feasibility_disagreement',
        'factorized_decision_score'} for row in bundle['rows'])
    assert 'candidate_cycles' not in str(bundle)
    assert 'area_delta_lut4' not in str(bundle)
    assert metadata['uncertainty_calibrated'] is False
    assert metadata['target_workload_group'] == 'target'
    assert metadata['training_rows'] == 3
    assert metadata['model_source_fingerprint']
    assert metadata['model_fit_and_prediction_seconds']['ranker_fit'] >= 0


def test_current_grouped_fit_rejects_related_target_formula_in_training():
    target = target_pool()
    training = history()
    training[2] = measured(public('h3', 'or(in0,slli(in1,1))', 'old2:ctx'),
                           area=48, savings=20)
    related = copy.deepcopy(training[0])
    related['candidate_id'] = 'related-target-family'
    related['formula'] = target[0]['formula']
    training.append(related)
    with pytest.raises(ValueError, match='related family'):
        fit_current_grouped_predictions(training, target,
            target_workload_group='target',
            target_formula_families=[family(row['formula']) for row in target])


def test_current_grouped_fit_rejects_wrong_target_workload():
    target = target_pool()
    training = history()
    training[2] = measured(public('h3', 'or(in0,slli(in1,1))', 'old2:ctx'),
                           area=48, savings=20)
    with pytest.raises(ValueError, match='held-out group'):
        fit_current_grouped_predictions(training, target,
            target_workload_group='another-target',
            target_formula_families=[family(row['formula']) for row in target])
