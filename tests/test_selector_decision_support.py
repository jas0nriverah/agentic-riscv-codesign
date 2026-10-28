"""Selection-board tests: public predictions plus outcomes already paid for."""
from copy import deepcopy

import pytest

from isaforge.selector_decision_support import build_grouped_decision_board
from test_budgeted_selection import measured, public


@pytest.fixture
def board_inputs():
    candidates = [public('t1', saved_cycles=60),
        public('t2', 'sub(in0,slli(in1,1))', saved_cycles=20),
        public('t3', 'add(in0,srli(in1,1))', saved_cycles=30)]
    predictions = {
        't1': dict(pairwise_rank_score=3., pairwise_rank_position=1,
            factorized_feasibility_probability=.7,
            factorized_feasibility_disagreement=.1, factorized_decision_score=.03),
        't2': dict(pairwise_rank_score=2., pairwise_rank_position=2,
            factorized_feasibility_probability=.5,
            factorized_feasibility_disagreement=.2, factorized_decision_score=.02),
        't3': dict(pairwise_rank_score=1., pairwise_rank_position=3,
            factorized_feasibility_probability=.3,
            factorized_feasibility_disagreement=.3, factorized_decision_score=.01),
    }
    return candidates, predictions


def test_board_distinguishes_predictions_from_paid_verification(board_inputs):
    candidates, predictions = board_inputs
    paid = measured(candidates[0], area=70, savings=60)
    board = build_grouped_decision_board(candidates, predictions, ['t1'], [paid],
        area_cap=64, clock_mhz=12)

    assert board['schema'] == 'isaforge-grouped-decision-board-v1'
    assert board['uncertainty_calibrated'] is False
    assert board['advisory_default_candidate_id'] == 't2'
    assert [row['pairwise_rank_position'] for row in board['rows']] == [1, 2, 3]
    assert board['rows'][0]['paid_verification']['status'] == 'area_infeasible'
    assert board['rows'][0]['paid_verification']['verified_feasible'] is False
    assert board['rows'][1]['paid_verification'] is None
    assert 'speedup' not in board['rows'][1]
    assert board['rows'][1]['factorized_feasibility_score'] == .5


def test_board_changes_only_when_public_paid_observation_is_added(board_inputs):
    candidates, predictions = board_inputs
    before = build_grouped_decision_board(candidates, predictions, [], [],
        area_cap=64, clock_mhz=12)
    hidden = measured(candidates[0], area=70, savings=60)
    # The unmeasured evaluator result is deliberately not an input to the board.
    still_hidden = build_grouped_decision_board(candidates, predictions, [], [],
        area_cap=64, clock_mhz=12)
    assert still_hidden == before
    after = build_grouped_decision_board(candidates, predictions, ['t1'], [hidden],
        area_cap=64, clock_mhz=12)
    assert after['rows'][0]['paid_verification']['status'] == 'area_infeasible'
    assert after['advisory_default_candidate_id'] == 't2'


def test_board_keeps_failures_unlabeled_and_charges_candidate(board_inputs):
    candidates, predictions = board_inputs
    failure = dict(**deepcopy(candidates[0]), status='failed',
        error='public fixture failure', measurement_seconds=3.)
    board = build_grouped_decision_board(candidates, predictions, ['t1'], [failure],
        area_cap=64, clock_mhz=12)
    result = board['rows'][0]['paid_verification']
    assert result == dict(status='failed_no_performance_or_hardware_label',
                          measurement_seconds=3.)


def test_board_rejects_incomplete_or_labeled_prediction_fields(board_inputs):
    candidates, predictions = board_inputs
    incomplete = deepcopy(predictions)
    incomplete.pop('t3')
    with pytest.raises(ValueError):
        build_grouped_decision_board(candidates, incomplete, [], [], area_cap=64, clock_mhz=12)
    labeled = deepcopy(predictions)
    labeled['t1']['speedup'] = 1.2
    with pytest.raises(ValueError):
        build_grouped_decision_board(candidates, labeled, [], [], area_cap=64, clock_mhz=12)


def test_board_rejects_paid_outcome_for_unattempted_candidate(board_inputs):
    candidates, predictions = board_inputs
    paid = measured(candidates[0])
    with pytest.raises(ValueError):
        build_grouped_decision_board(candidates, predictions, [], [paid],
            area_cap=64, clock_mhz=12)
