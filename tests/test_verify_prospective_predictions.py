"""Independent prediction replay contracts; synthetic fixtures only."""
import copy
import unittest
from unittest.mock import patch

from isaforge import codesign as c, prospective_selection as selection
from isaforge.model import SpeedupPredictor
from isaforge.ranking import SpeedupRanker
from scripts import verify_prospective_predictions as replay
from tests.test_prospective_selection import history, public


class PredictionReplayContracts(unittest.TestCase):
    def setUp(self):
        self.history=history(); self.public=[public('t','add(in0,slli(in1,1))')]
        self.features=copy.deepcopy(self.history)
        self.protocol=dict(input_digests=dict(history=c.digest(self.history),history_features=c.digest(self.features)),
            target_workload='third',excluded_related_ids=[],historical_available_rows=3,historical_fit_rows=3,
            fit_workload_groups=['old1','old2'],historical_candidate_wall_seconds=6)

    def record(self, seed=0):
        model=SpeedupPredictor(seed=seed).fit(self.history)
        return dict(seed=seed,regression=model.predict(self.public),
            ranking=SpeedupRanker(seed=seed).fit(self.history).predict(self.public),
            execution=selection.execution_predictions(self.history,self.public,seed,model),
            inference_seconds={k:1 for k in ('regression_zero_shot','ranking_zero_shot','execution_regression_zero_shot')})

    def test_reconstructs_exact_training(self):
        rows=replay.training_rows(self.history,self.features,self.public,self.protocol)
        self.assertEqual(rows,self.history)

    def test_rejects_historical_labels_or_counts_changed(self):
        changed=copy.deepcopy(self.history); changed[0]['speedup']+=.001
        with self.assertRaisesRegex(ValueError,'Historical corpus changed'):
            replay.training_rows(changed,self.features,self.public,self.protocol)
        self.protocol['historical_fit_rows']=2
        with self.assertRaisesRegex(ValueError,'fitting counts'):
            replay.training_rows(self.history,self.features,self.public,self.protocol)

    def test_rejects_target_history_overlap(self):
        self.protocol['target_workload']='old1'
        with self.assertRaisesRegex(ValueError,'Target workload'):
            replay.training_rows(self.history,self.features,self.public,self.protocol)

    def test_rejects_exclusion_drift(self):
        self.protocol['excluded_related_ids']=['unexpected']
        with self.assertRaisesRegex(ValueError,'Family exclusions'):
            replay.training_rows(self.history,self.features,self.public,self.protocol)

    def test_exact_replay_ignores_only_timer_values(self):
        record=self.record()
        record['inference_seconds']={k:999 for k in record['inference_seconds']}
        self.assertEqual(replay.verify_predictions(self.history,self.public,[record],[0]),
                         {'regression':1,'ranking':1,'execution':1})
        record['execution'][0]['mean']+=1e-10
        with self.assertRaisesRegex(ValueError,'Exact fixed prediction'):
            replay.verify_predictions(self.history,self.public,[record],[0])

    def test_rejects_seed_or_unknown_field_changes(self):
        record=self.record()
        with self.assertRaisesRegex(ValueError,'seeds changed'):
            replay.verify_predictions(self.history,self.public,[record],[1])
        record['ignored_extra']='must reject'
        with self.assertRaisesRegex(ValueError,'Unknown frozen prediction fields'):
            replay.verify_predictions(self.history,self.public,[record],[0])


if __name__=='__main__': unittest.main()
