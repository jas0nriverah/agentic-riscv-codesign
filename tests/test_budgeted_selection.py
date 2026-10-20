"""Synthetic interface tests; these are not new measured research outcomes."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isaforge import budgeted_selection as b
from isaforge import codesign as c
from isaforge.features import extract_features


def public(identity, formula='add(in0,slli(in1,1))', benchmark='target:ctx', *, runs=10,
           baseline=1000, saved_cycles=40):
    features = extract_features(dict(formula=formula,size=2,runs=runs,places=1,
                                    saved=runs,savedPercent=1.0))
    values = dict(baseline_cycles=baseline,baseline_instructions=baseline//4,
        baseline_cpi=4.0,replacement_execution_fraction=runs/(baseline//4),
        occurrence_size_min=2,occurrence_size_max=2,dynamic_software_cycles=5*runs+saved_cycles,
        dynamic_custom_cycles=5*runs,dynamic_shift_extra_cycles=0,
        estimated_saved_cycles=saved_cycles,estimated_cycle_reduction=saved_cycles/baseline,
        estimated_speedup=baseline/(baseline-saved_cycles),region_custom_instructions=runs)
    return dict(candidate_id=identity,benchmark=benchmark,formula=formula,
                **features,latency_features=values)


def measured(row, *, area=40, fmax=15.0, savings=40, seconds=2.0):
    baseline = row['latency_features']['baseline_cycles']
    return dict(**copy.deepcopy(row),baseline_cycles=baseline,candidate_cycles=baseline-savings,
        speedup=baseline/(baseline-savings),area_delta_lut4=area,routed_fmax_min_mhz=fmax,
        device_fits=True,correctness_verified=True,measurement_seconds=seconds,
        measurement_source='synthesis_estimate',workload_group=row['benchmark'].split(':')[0])


def history():
    return [measured(public('h1','xor(in0,slli(in1,1))','old1:ctx'),area=32),
            measured(public('h2','and(in0,slli(in1,1))','old2:ctx'),area=40),
            measured(public('h3','or(in0,slli(in1,1))','old2:ctx'),area=48)]


def predictions(training, target, seed):
    simple = [dict(candidate_id=r['candidate_id'],mean=1.01,lower=1.0,upper=1.1,std=.01)
              for r in target]
    hardware = [dict(candidate_id=r['candidate_id'],area_delta_lut4_mean=40.,area_delta_lut4_std=8.,
        routed_fmax_min_mhz_mean=15.,routed_fmax_min_mhz_std=1.,
        log_measurement_seconds_mean=0.,log_measurement_seconds_std=.25,
        device_fit_probability=.8) for r in target]
    return dict(seed=seed,raw=simple,normalized=simple,hardware=hardware,
        ranking=[dict(candidate_id=r['candidate_id'],rank_score=float(i)) for i,r in enumerate(target)],
        inference_seconds={})


class BudgetedContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'run'
        self.history = history()
        self.target = [public('t1',saved_cycles=60),
                       public('t2','sub(in0,slli(in1,1))',saved_cycles=20),
                       public('t3','add(in0,srli(in1,1))',saved_cycles=30)]
        self.contexts = {r['benchmark']:{'source':'test-only'} for r in self.history+self.target}

    def freeze(self):
        with patch.object(b,'zero_shot',side_effect=predictions):
            return b.freeze(self.history,self.target,self.contexts,self.root,
                target_workload='target',calibration_cost_seconds=5,seeds=(0,),budgets=(1,2,3))

    def test_public_boundary_rejects_nested_and_outer_labels(self):
        for key in ('speedup','area_delta_lut4','measurement_seconds'):
            rows=copy.deepcopy(self.target); rows[0][key]=1
            with self.assertRaises((ValueError,RuntimeError)): b.public_rows(rows)
            rows=copy.deepcopy(self.target); rows[0]['latency_features'][key]=1
            with self.assertRaises((ValueError,RuntimeError)): b.public_rows(rows)

    def test_exact_occurrences_are_region_counts(self):
        row=self.target[0]
        self.assertEqual(b.occurrence_count(row),10)
        # Measured whole-program execution includes startup; it is not a feature.
        row['custom_execution_count']=1000
        self.assertEqual(b.occurrence_count(row),10)
        del row['latency_features']['region_custom_instructions']
        self.assertEqual(b.occurrence_count(row),10)
        row['latency_features']['dynamic_custom_cycles']+=1
        with self.assertRaises((ValueError,RuntimeError)): b.occurrence_count(row)

    def test_freeze_and_verified_feasible_oracle(self):
        protocol=self.freeze()
        self.assertEqual(protocol['target_labels_read'],0)
        self.assertEqual(len(protocol['policies']),10)
        outcomes=[measured(self.target[0],area=77,savings=60),
                  measured(self.target[1],area=30,savings=20),
                  measured(self.target[2],area=60,fmax=11,savings=30)]
        report=b.evaluate(self.root,outcomes)
        self.assertEqual(len(report['summary']),90)
        self.assertEqual(report['policy_seed_cap_budget_outcomes'],90)
        self.assertEqual(report['oracles'][1]['speedup'],1000/980)
        self.assertEqual(report['oracles'][2]['speedup'],1000/940)
        self.assertEqual(b.stable(report),b.stable(b.evaluate(self.root,outcomes,verify=True)))

    def test_failures_charge_budget_and_cost_and_keep_baseline(self):
        values=predictions(self.history,self.target,0)
        calls=[]
        def provider(row):
            calls.append(row['candidate_id'])
            if row['candidate_id']=='t1':
                return dict(**row,status='failed',measurement_seconds=7,error='retained synthesis failure')
            return measured(row,area=1000,savings=30)
        result=b.search(self.target,self.history,provider,area_cap=64,clock_mhz=12,
            policy='calibrated_latency',seed=0,budget=3,predictions=values)
        self.assertEqual(calls[0],'t1')
        self.assertEqual(result['curve'][0]['budget'],1)
        self.assertEqual(result['curve'][0]['failed_attempts'],1)
        self.assertEqual(result['curve'][0]['target_measurement_seconds'],7)
        self.assertEqual(result['curve'][-1]['target_measurement_seconds'],11)
        self.assertEqual(result['curve'][-1]['best_speedup'],1.0)
        self.assertEqual(len(set(calls)),3)

    def test_future_outcomes_cannot_change_first_acquisition(self):
        values=predictions(self.history,self.target,0)
        for policy in b.POLICIES:
            calls=[]
            def provider(row):
                calls.append(row['candidate_id'])
                return measured(row,savings=1)
            first=b.search(self.target,self.history,provider,area_cap=64,clock_mhz=12,
                policy=policy,seed=0,budget=1,predictions=values)['events'][0]
            calls.clear()
            def changed(row):
                calls.append(row['candidate_id'])
                return measured(row,savings=500)
            second=b.search(self.target,self.history,changed,area_cap=64,clock_mhz=12,
                policy=policy,seed=0,budget=1,predictions=values)['events'][0]
            self.assertEqual(first,second)
            self.assertEqual(len(calls),1)
            self.assertEqual(first['paid_target_ids_before_query'],[])

    def test_hybrid_uses_constraints_and_duration(self):
        row=self.target[0]; estimate=predictions(self.history,[row],0)['hardware'][0]
        base=b.hybrid_score(row,estimate,1.0,64,12)
        self.assertGreater(base,0)
        self.assertLess(b.hybrid_score(row,estimate,1.0,16,12),base)
        self.assertLess(b.hybrid_score(row,estimate,1.0,64,20),base)
        slower={**estimate,'log_measurement_seconds_mean':2.0}
        self.assertLess(b.hybrid_score(row,slower,1.0,64,12),base)
        self.assertEqual(b.hybrid_score(row,estimate,2.0,64,12),0)

    def test_only_paid_successes_update_hardware_surrogate(self):
        values=predictions(self.history,self.target,0); seen=[]
        real=b.HardwareSurrogate.fit
        def fit(model,rows):
            seen.append([r['candidate_id'] for r in rows]); return real(model,rows)
        with patch.object(b.HardwareSurrogate,'fit',new=fit):
            result=b.search(self.target,self.history,lambda r:measured(r),area_cap=64,clock_mhz=12,
                policy='hybrid_gp_adapt',seed=0,budget=3,predictions=values)
        self.assertEqual(len(seen),2)
        self.assertEqual(seen[0],['h1','h2','h3',result['curve'][0]['attempted_ids'][0]])
        self.assertEqual(seen[1],['h1','h2','h3']+result['curve'][1]['attempted_ids'])

    def test_family_exclusion_and_frozen_artifacts(self):
        self.history[0]=measured(public('h1',self.target[0]['formula'],'old1:ctx'))
        protocol=self.freeze()
        self.assertEqual(protocol['excluded_related_ids'],['h1'])
        self.assertEqual(protocol['historical_fit_rows'],2)
        values=c.unseal(self.root/'public.json'); values[0]['runs']+=1
        c.seal(self.root/'public.json',values)
        with self.assertRaises((ValueError,RuntimeError)):
            b.evaluate(self.root,[measured(r) for r in self.target])

    def test_measurement_identity_and_correctness_are_checked(self):
        row=measured(self.target[0]); row['latency_features']['estimated_speedup']+=.1
        with self.assertRaises((ValueError,RuntimeError)): b.validate_outcome(row,self.target[0])
        row=measured(self.target[0]); row['correctness_verified']=False
        with self.assertRaises((ValueError,RuntimeError)): b.validate_outcome(row,self.target[0])


class NormalizedModelContracts(unittest.TestCase):
    def test_constant_per_occurrence_transfers_scale_and_retains_slowdowns(self):
        rows=history()
        # Four saved cycles per occurrence is constant despite different scale.
        rows[1]=measured(public('h2','and(in0,slli(in1,1))','old2:ctx',runs=20,baseline=10000),savings=80)
        model=b.NormalizedSpeedupPredictor(3).fit(rows)
        target=[public('new',runs=100,baseline=100000)]
        result=model.predict(target)[0]
        self.assertEqual(result['saved_cycles_per_occurrence_mean'],4.0)
        self.assertAlmostEqual(result['mean'],100000/(100000-400),places=14)
        slow=[measured(r,savings=-40) for r in [public('a','xor(in0,slli(in1,1))','one:ctx'),
                                               public('b','and(in0,slli(in1,1))','two:ctx')]]
        self.assertLess(b.NormalizedSpeedupPredictor().fit(slow).predict(target)[0]['mean'],1.0)

    def test_reconstruction_floor_is_explicit_and_no_events_are_features(self):
        rows=[measured(public('a','xor(in0,slli(in1,1))','one:ctx'),savings=900),
              measured(public('b','and(in0,slli(in1,1))','two:ctx'),savings=900)]
        result=b.NormalizedSpeedupPredictor().fit(rows).predict([public('new',runs=100)])[0]
        self.assertEqual(result['one_cycle_floor_members'],20)
        self.assertEqual(result['mean'],1000)
        self.assertFalse(set(('runs','saved','places','saved_percent'))&set(b.STRUCTURAL_COLUMNS))

    def test_nonconstant_fit_is_deterministic(self):
        rows=history(); rows[0]=measured(public('h1','xor(in0,slli(in1,1))','old1:ctx'),savings=20)
        target=[public('new')]
        self.assertEqual(b.NormalizedSpeedupPredictor(2).fit(rows).predict(target),
                         b.NormalizedSpeedupPredictor(2).fit(rows).predict(target))


if __name__=='__main__': unittest.main()
