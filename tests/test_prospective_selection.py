"""Synthetic interface contracts; these fixtures are not research evidence."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isaforge import codesign as c
from isaforge import prospective_selection as p
from isaforge.features import extract_features


def public(identity, formula, benchmark='third:context'):
    features=extract_features(dict(formula=formula,size=2,runs=10,places=1,saved=10,savedPercent=1))
    return dict(candidate_id=identity,benchmark=benchmark,formula=formula,**features,
                latency_features={**{k:1.0 for k in p.EXECUTION_COLUMNS},'estimated_speedup':1.02})


def history():
    rows=[public('h1','xor(in0,slli(in1,1))','old1:context'),
          public('h2','and(in0,slli(in1,1))','old2:context'),
          public('h3','or(in0,slli(in1,1))','old2:context')]
    return [{**r,'workload_group':'old1' if i==0 else 'old2', 'speedup':1.01+i*.01,
             'measurement_source':'synthesis_estimate','measurement_seconds':2.0} for i,r in enumerate(rows)]


class ProspectiveContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'run'
        self.target=[public('t1','add(in0,slli(in1,1))'),public('t2','sub(in0,slli(in1,1))')]
        self.hist=history()
        self.contexts={r['benchmark']:{k:'bound' for k in p.CONTEXT_KEYS} for r in self.hist+self.target}

    def freeze(self):
        # Stub models to test acquisition isolation and provenance independently
        # of optional ML package availability or fitting performance.
        regression=[dict(candidate_id=r['candidate_id'],mean=1.0,lower=.9,upper=1.1,std=.1) for r in self.target]
        ranking=[dict(candidate_id=r['candidate_id'],rank_score=float(i)) for i,r in enumerate(self.target)]
        with patch.object(p.SpeedupPredictor,'fit',return_value=p.SpeedupPredictor()), \
             patch.object(p.SpeedupPredictor,'predict',return_value=regression), \
             patch.object(p.SpeedupRanker,'fit',return_value=p.SpeedupRanker()), \
             patch.object(p.SpeedupRanker,'predict',return_value=ranking), \
             patch.object(p,'execution_predictions',return_value=regression):
            return p.freeze(self.hist,self.hist,self.target,self.contexts,self.root,
                            target_workload='third',calibration_cost_seconds=5,area_cap=100,seeds=(0,),budgets=(1,2))

    def outcomes(self):
        return [{**r,'speedup':speed,'area':90,'area_cap':100,'timing_feasible':True,
                 'measurement_source':'synthesis_estimate','measurement_seconds':3} for r,speed in zip(self.target,[1.1,1.2])]

    def test_rejects_target_labels(self):
        for field in ('speedup','candidate_cycles','area','measurement_seconds'):
            rows=copy.deepcopy(self.target); rows[0][field]=1
            with self.assertRaises((ValueError,RuntimeError)): p.public_rows(rows)

    def test_freezes_counts_and_replays_equal_budget(self):
        protocol=self.freeze()
        self.assertEqual(protocol['target_labels_read'],0)
        self.assertEqual(protocol['historical_fit_rows'],3)
        report=p.evaluate(self.root,self.outcomes(),area_cap=100)
        self.assertEqual(len(report['runs']),len(p.POLICIES))
        for run in report['runs']:
            self.assertEqual([v['budget'] for v in run['curve']],[1,2])
            self.assertEqual(run['curve'][-1]['best_speedup'],1.2)
            self.assertEqual(run['curve'][-1]['target_candidate_wall_seconds'],6)
        self.assertEqual(report,p.evaluate(self.root,self.outcomes(),area_cap=100,verify=True))

    def test_frozen_constraints_and_public_artifact(self):
        self.freeze()
        with self.assertRaises((ValueError,RuntimeError)): p.evaluate(self.root,self.outcomes(),area_cap=99)
        rows=c.unseal(self.root/'public.json'); rows[0]['runs']+=1; c.seal(self.root/'public.json',rows)
        with self.assertRaises((ValueError,RuntimeError)): p.evaluate(self.root,self.outcomes(),area_cap=100)

    def test_outcome_identity_and_completeness(self):
        self.freeze()
        with self.assertRaises((ValueError,RuntimeError)): p.evaluate(self.root,self.outcomes()[:1],area_cap=100)
        rows=self.outcomes(); rows[0]['saved']+=1
        with self.assertRaises((ValueError,RuntimeError)): p.evaluate(self.root,rows,area_cap=100)

    def test_contexts_and_target_history_exclusion(self):
        del self.contexts[self.target[0]['benchmark']]
        with self.assertRaises((ValueError,RuntimeError)): self.freeze()
        self.assertFalse(self.root.exists())

    def test_source_family_exclusion_before_fit(self):
        self.hist[0]['formula']=self.target[0]['formula']
        protocol=self.freeze()
        self.assertEqual(protocol['historical_fit_rows'],2)
        self.assertEqual(protocol['excluded_related_ids'],['h1'])

    def test_actual_fixed_ensemble_is_deterministic(self):
        first=p.execution_predictions(self.hist,self.target,3)
        self.assertEqual(first,p.execution_predictions(self.hist,self.target,3))
        self.assertEqual([r['candidate_id'] for r in first],['t1','t2'])
        self.assertTrue(all(r['lower']<=r['mean']<=r['upper'] for r in first))
        constant=copy.deepcopy(self.hist)
        for row in constant: row['speedup']=1.01
        values=p.execution_predictions(constant,self.target,3)
        self.assertTrue(all(r['mean']==1.01 and r['std']==0 for r in values))

    def test_constant_extended_features_preserve_exact_baseline_reductions(self):
        # Extra columns have no split information: only the feature width changes.
        # A non-default interval also detects literal quantile-tail regressions.
        predictor=p.SpeedupPredictor(seed=7,interval=.8).fit(self.hist)
        self.assertEqual(predictor.predict(self.target),
                         p.execution_predictions(self.hist,self.target,7,predictor))
        self.assertEqual(p.execution_predictions(self.hist,[],7,predictor),[])

    def test_extended_matrix_is_fixed_and_label_free(self):
        old=p.feature_matrix(self.target); new=p.execution_matrix(self.target)
        self.assertEqual(new[0][:len(old[0])],old[0])
        self.assertEqual(len(new[0]),len(p.FEATURE_COLUMNS)+len(p.EXECUTION_COLUMNS))
        self.assertFalse(any('speedup' in k for k in p.EXECUTION_COLUMNS))


if __name__=='__main__': unittest.main()
