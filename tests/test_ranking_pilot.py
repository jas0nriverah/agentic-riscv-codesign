"""Synthetic fixtures check contracts, not research performance."""
import copy

import pytest

from isaforge import codesign as c
from isaforge import selection_pilot as pilot
from isaforge import speedup_corpus as corpus
from isaforge.features import extract_features
from isaforge.ranking import SpeedupRanker, grouped_labels


def sample(group, number, cycles=80, *, area=12, feasible=True):
    formula = f'addi(in0,{number})'
    identity = {'workload': group, 'processor_id': 'fixture', 'formula': formula}
    features = extract_features({'formula': formula, 'size': 2, 'runs': 10+number,
                                 'places': 1, 'saved': 10+number, 'savedPercent': number})
    return {**features, 'candidate_id': c.digest(identity), 'benchmark': group+':input',
            'sample_identity': identity, 'workload': group, 'workload_group': group,
            'processor_id': 'fixture', 'formula': formula, 'candidate_family': corpus.family(formula),
            'label_kind': corpus.LABEL_KIND, 'measurement_source': 'synthesis_estimate',
            'baseline_cycles': 100, 'candidate_cycles': cycles, 'baseline_period_ns': 10,
            'candidate_period_ns': 10, 'speedup': 100/cycles, 'area': area, 'area_cap': 20,
            'timing_feasible': feasible, 'correctness_verified': True, 'custom_execution_count': 10,
            'measurement_seconds': float(number)}


def test_ranking_pairs_are_within_query_and_preserve_measured_ties():
    rows = [sample('b', 4, 40), sample('a', 1, 100), sample('a', 2, 50),
            sample('b', 3, 80), sample('a', 5, 50)]
    ordered, labels, qids, groups = grouped_labels(rows)
    for row, label, qid in zip(ordered, labels, qids):
        assert groups[qid]['benchmark'] == row['benchmark']
        assert label == int(row['candidate_cycles'] in (50, 40))
    assert [g['rows'] for g in groups] == [3, 2]


def test_between_workload_offset_is_not_a_ranking_pair():
    rows = [sample('a', 1, 50), sample('a', 2, 50), sample('b', 3, 80), sample('b', 4, 80)]
    with pytest.raises(ValueError, match='unequal pair'):
        SpeedupRanker().fit(rows)


def test_ranker_outputs_scores_only_and_ignores_target_outcomes():
    train = [sample('train', n, 100-n*10) for n in range(1, 7)]
    model = SpeedupRanker().fit(train)
    target = [sample('test', n) for n in range(1, 4)]
    before = model.predict(pilot.public_rows(target))
    poisoned = copy.deepcopy(target)
    for row in poisoned:
        row.update(speedup=999, area=0, timing_feasible=False, measurement_seconds=999)
    assert model.predict(poisoned) == before
    assert all(set(row) == {'candidate_id', 'rank_score'} for row in before)
    assert before == SpeedupRanker().fit(list(reversed(train))).predict(pilot.public_rows(target))


def test_ranker_rejects_missing_group_duplicate_and_unmeasured_labels():
    rows = [sample('train', 1), sample('train', 2, 50)]
    with pytest.raises(ValueError, match='Duplicate'):
        SpeedupRanker().fit(rows+rows[:1])
    for key in ('benchmark', 'speedup', 'measurement_source'):
        bad = copy.deepcopy(rows)
        bad[0].pop(key)
        with pytest.raises(ValueError):
            SpeedupRanker().fit(bad)


def predictions(rows):
    return {'ranking': [dict(candidate_id=r['candidate_id'], rank_score=10-i) for i,r in enumerate(rows)],
            'regression': [dict(candidate_id=r['candidate_id'], mean=2-i*.1, lower=1, upper=3-i*.1, std=.1)
                           for i,r in enumerate(rows)], 'ranking_seconds': .1, 'regression_seconds': .2}


@pytest.mark.parametrize('policy', pilot.POLICIES)
def test_policies_query_public_rows_and_obey_budget_and_joint_feasibility(policy):
    rows = [sample('target', 1, 10, area=99), sample('target', 2, 20, feasible=False), sample('target', 3, 50)]
    labels = {r['candidate_id']: r for r in rows}
    calls = []
    def measure(row):
        assert set(row) == set(pilot.PUBLIC_KEYS)
        calls.append(row['candidate_id'])
        return labels[row['candidate_id']]
    training = [sample('train', 4, 70), sample('train', 5, 80)]
    result = pilot.search(pilot.public_rows(rows), training, measure, 20, policy, 0, 3, predictions(rows))
    assert len(calls) == len(set(calls)) == 3
    assert result['curve'][-1]['selected_id'] == rows[2]['candidate_id']
    assert result['curve'][-1]['best_speedup'] == 2
    assert result['curve'][-1]['target_measurement_seconds'] == 6
    for point in result['curve']:
        assert len(point['measured_ids']) == point['budget']
        assert point['selected_id'] is None or point['selected_id'] in point['measured_ids']


def test_adaptation_never_trains_on_unpaid_target_labels(monkeypatch):
    training = [sample('train', 4), sample('train', 5, 50)]
    target = [sample('target', 1), sample('target', 2, 50), sample('target', 3, 25)]
    paid, fits = [], []
    class Spy:
        def __init__(self, seed):
            pass
        def fit(self, rows):
            assert {r['candidate_id'] for r in rows} == {r['candidate_id'] for r in training} | set(paid)
            fits.append(len(rows))
            return self
        def predict(self, rows):
            assert all(set(r) == set(pilot.PUBLIC_KEYS) for r in rows)
            return predictions(rows)['regression']
    monkeypatch.setattr(pilot, 'SpeedupPredictor', Spy)
    labels = {r['candidate_id']: r for r in target}
    def measure(row):
        paid.append(row['candidate_id'])
        return labels[row['candidate_id']]
    pilot.search(pilot.public_rows(target), training, measure, 20, 'ucb_adapt', 0, 3, predictions(target))
    assert fits == [3, 4]


def test_zero_budget_and_slowdowns_return_baseline():
    row = sample('target', 1, 120)
    args = (pilot.public_rows([row]), [], lambda _: row, 20, 'random', 0)
    assert pilot.search(*args, 0, predictions([row]))['curve'] == []
    assert pilot.search(*args, 1, predictions([row]))['curve'][0]['best_speedup'] == 1


def test_pair_accuracy_counts_prediction_ties_and_ignores_outcome_ties():
    assert pilot.pair_accuracy([1, 2], [0, 0]) == .5
    assert pilot.pair_accuracy([1, 2, 2], [0, 1, 2]) == 1
    assert pilot.pair_accuracy([1, 1], [0, 1]) is None


def test_original_primary_generalization_gate_is_not_bypassed(tmp_path):
    rows = [sample('a', 1), sample('a', 2), sample('b', 3), sample('b', 4)]
    with pytest.raises(ValueError, match='at least three'):
        corpus.evaluate(rows, tmp_path/'primary')
    with pytest.raises(ValueError, match='acknowledge-consumed-data'):
        pilot.main(['freeze', '--root', str(tmp_path/'pilot')])
