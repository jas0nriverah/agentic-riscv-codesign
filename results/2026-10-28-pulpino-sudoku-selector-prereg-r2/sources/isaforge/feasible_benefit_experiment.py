"""Freeze and replay the one fixed feasible-benefit model on an explicit pool.

The caller asserts target-label availability before any writes. Controls retain
the original ten-policy freeze; utility models use that exact filtered history.
This module never discovers workloads or starts native measurements.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import statistics
import time

from . import budgeted_selection as b, codesign as c
from .feasible_benefit import (AREA_CAPS, CLOCK_MHZ, MODEL_SETTINGS, BUDGET_FEATURE,
    FeasibleBenefitPredictor, decision_utility, search)
from .speedup_corpus import family

POLICY = 'feasible_benefit_xgb'
SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
SOURCES = ('isaforge/feasible_benefit_experiment.py','isaforge/feasible_benefit.py',*b.SOURCES)
SCOPES = ('consumed-source fresh-candidate-pool','consumed-data development','prospective source holdout')


def _relative(root, name):
    path = (root/name).resolve()
    c.require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()), 'Artifact escapes freeze root')
    return path


def freeze(history, public, contexts, output, *, target_workload,
           target_labels_observed, calibration_cost_seconds, cost_provenance=None,
           scope='consumed-source fresh-candidate-pool', input_bindings=None):
    """Write ten unchanged controls plus five exported utility ensembles.

    History must already exclude the entire target source workload. Related
    families are then removed by the existing control freeze, identically for
    every learned policy. This function requires a deliberate zero-label assertion.
    """
    output = Path(output)
    c.require(type(target_labels_observed) is int and target_labels_observed == 0,
              'Freeze requires explicit zero observed target candidate labels')
    c.require(scope in SCOPES, 'Explicit generalization scope required')
    c.require(not output.exists(), 'Fresh feasible benefit freeze directory required')
    public = b.public_rows(public)
    c.require(len(public) >= max(BUDGETS), 'At least three public candidates required')
    c.require(len({r['candidate_id'] for r in history}) == len(history), 'Unique historical candidates required')
    c.require(all(r['workload_group'] != target_workload for r in history), 'Target source workload in history')
    c.require(not {r['benchmark'] for r in history} & {r['benchmark'] for r in public}, 'Target context in history')
    target_families = {family(r['formula']) for r in public}
    expected_history = [r for r in history if family(r['formula']) not in target_families]
    fitting_groups = sorted({r['workload_group'] for r in expected_history})
    c.require(len(fitting_groups) >= 2, 'At least two post-family-filter historical groups required')
    for row in history: c.require(b.validate_outcome(row), 'Failed attempts are historical costs, not fitting labels')
    output.mkdir(parents=True)
    prefit = dict(schema='isaforge-feasible-benefit-freeze-v1', scope=scope,
        target_workload=target_workload, target_labels_observed=0, target_labels_read=0,
        source_bindings={name:c.sha(c.ROOT/name) for name in SOURCES},
        input_bindings=input_bindings or {}, public_digest=c.digest(public), history_digest=c.digest(history),
        contexts_digest=c.digest(contexts), historical_available_rows=len(history),
        expected_fitting_ids=[r['candidate_id'] for r in expected_history],postfilter_groups=fitting_groups,
        model_settings=MODEL_SETTINGS, budget_feature=BUDGET_FEATURE, area_caps=list(AREA_CAPS),
        clock_mhz=CLOCK_MHZ, seeds=list(SEEDS),budgets=list(BUDGETS),new_native_jobs=0,
        inference_and_measurement_costs='Historical attempts, baseline/setup, fitting/inference and target measurements are separate; timer scopes may overlap.',
        decision_target='signed feasible normalized saved cycles; infeasible zero utility; failed utility unknown')
    c.seal(output/'pre-fit-protocol.json',prefit)
    original = b.freeze(history, public, contexts, output/'model', target_workload=target_workload,
        calibration_cost_seconds=calibration_cost_seconds, cost_provenance=cost_provenance,
        area_caps=AREA_CAPS,clock_mhz=CLOCK_MHZ,seeds=SEEDS,budgets=BUDGETS,
        scope='consumed-data development' if scope == 'consumed-data development' else 'prospective')
    training = c.unseal(output/'model/history.json')
    checked_public = c.unseal(output/'model/public.json')
    c.require(training == expected_history, 'Utility/control fitting cohorts differ')
    c.require(checked_public == public, 'Utility/control public pools differ')
    predictions, costs = [], []
    for seed in SEEDS:
        began = time.monotonic()
        predictor = FeasibleBenefitPredictor(seed).fit(training)
        values = {str(cap):predictor.predict(public,area_cap=cap) for cap in AREA_CAPS}
        elapsed = time.monotonic()-began
        exported = output/'utility-models'/f'seed-{seed}'
        predictor.save(exported)
        loaded = FeasibleBenefitPredictor.load(exported)
        c.require(all(loaded.predict(public,area_cap=cap) == values[str(cap)] for cap in AREA_CAPS),
                  'Exported model predictions differ')
        predictions.append(dict(seed=seed,by_cap=values))
        costs.append(dict(seed=seed,fit_and_all_caps_prediction_seconds=elapsed,
            historical_lut4_per_tree_operation=predictor.area_per_op, fitting_candidates=len(training)))
    c.seal(output/'utility-predictions.json',predictions)
    c.seal(output/'utility-inference-costs.json',costs)
    artifacts = {str(path.relative_to(output)):c.sha(path) for path in sorted(output.rglob('*')) if path.is_file()}
    protocol = dict(**prefit, original_control_protocol_sha256=c.sha(output/'model/protocol.json'),
        original_control_policies=list(b.POLICIES), utility_policy=POLICY,
        historical_fitting_rows=len(training),historical_postfilter_groups=fitting_groups,
        historical_training_ids=[r['candidate_id'] for r in training],
        excluded_related_ids=original['excluded_related_ids'],
        historical_candidate_wall_seconds=original['historical_candidate_wall_seconds'],
        calibration_cost_seconds=calibration_cost_seconds,cost_provenance=cost_provenance or {},
        packages=original['packages'],artifacts=artifacts,
        limitations=['No target labels were available to this freeze caller by its explicit assertion.',
            'Consumed-source fresh-pool evidence is not unseen-workload generalization.',
            'Utility is not speedup or calibrated feasibility.',
            'Five dependent model/tie seeds do not create independent target workloads.',
            'This wrapper never starts native jobs; native one-attempt charging is enforced by the workload evaluator.',
            'Single instructions only; jointly selected sets remain unmeasured.'])
    c.seal(output/'protocol.json',protocol)
    return protocol


def authenticate(root):
    """Validate the complete prelabel package without reading target outcomes."""
    root = Path(root).resolve()
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol['schema'] == 'isaforge-feasible-benefit-freeze-v1' and
              protocol['target_labels_observed'] == 0 and protocol['target_labels_read'] == 0,
              'Expected zero-label feasible benefit freeze')
    c.require(set(protocol['source_bindings']) == set(SOURCES), 'Missing source bindings')
    for name,expected in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == expected, 'Frozen feasible benefit source changed: '+name)
    for name,expected in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == expected, 'Frozen dependency changed: '+name)
    c.require(protocol['model_settings'] == MODEL_SETTINGS and protocol['area_caps'] == list(AREA_CAPS)
              and protocol['clock_mhz'] == CLOCK_MHZ and protocol['seeds'] == list(SEEDS)
              and protocol['budgets'] == list(BUDGETS), 'Frozen model protocol differs')
    for name,expected in protocol['artifacts'].items():
        c.require(c.sha(_relative(root,name)) == expected, 'Frozen package artifact changed: '+name)
    original = c.unseal(root/'model/protocol.json')
    c.require(c.sha(root/'model/protocol.json') == protocol['original_control_protocol_sha256'],
              'Original control protocol binding differs')
    for name,expected in original['artifacts'].items():
        c.require(c.sha(_relative(root/'model',name)) == expected, 'Frozen control artifact changed')
    public = c.unseal(root/'model/public.json');history = c.unseal(root/'model/history.json')
    predictions = c.unseal(root/'utility-predictions.json')
    b.public_rows(public)
    c.require(c.digest(public) == protocol['public_digest'], 'Public digest differs')
    c.require([r['candidate_id'] for r in history] == protocol['historical_training_ids'] == original['historical_training_ids'],
              'Utility/control historical cohort differs')
    c.require(sorted({r['workload_group'] for r in history}) == protocol['historical_postfilter_groups']
              and len(protocol['historical_postfilter_groups']) >= 2, 'Postfilter historical groups differ')
    for seed in SEEDS:
        model = FeasibleBenefitPredictor.load(root/'utility-models'/f'seed-{seed}')
        c.require(model.training_ids == protocol['historical_training_ids'], 'Exported historical cohort differs')
        values = next(p for p in predictions if p['seed'] == seed)['by_cap']
        c.require(all(model.predict(public,area_cap=cap) == values[str(cap)] for cap in AREA_CAPS),
                  'Frozen utility model/predictions differ')
    return dict(protocol=protocol,control_protocol=original,public=public,history=history,predictions=predictions)


def evaluate(root, outcomes, *, reference_censored=False, verify=False):
    """Privileged equal-budget scorer over sealed, already-frozen predictions."""
    root = Path(root)
    c.require(type(reference_censored) is bool, 'Explicit reference censorship flag required')
    case = authenticate(root)
    c.require(verify or not (root/'report.json').exists(), 'Preserve prior feasible benefit report')
    public,protocol = case['public'],case['protocol']
    labels = {r['candidate_id']:r for r in outcomes}
    c.require(len(labels) == len(outcomes) and set(labels) == {r['candidate_id'] for r in public},
              'Complete unique attempted pool required')
    for row in public: b.validate_outcome(labels[row['candidate_id']],row)
    inferred_censorship = any(r.get('reference_censored') is True for r in outcomes)
    c.require(reference_censored or not inferred_censorship, 'Censored outcomes require censored reference')
    outcomes = [labels[r['candidate_id']] for r in public]
    controls = b.evaluate(root/'model',outcomes,verify=verify)
    runs = [dict(target=protocol['target_workload'],cap=run['area_delta_lut4_cap'],**copy.deepcopy(run)) for run in controls['runs']]
    diagnostics = []
    for cap in AREA_CAPS:
        for seed in SEEDS:
            prediction = next(p for p in case['predictions'] if p['seed'] == seed)['by_cap'][str(cap)]
            result = search(public,lambda row:copy.deepcopy(labels[row['candidate_id']]),
                area_cap=cap,seed=seed,budget=max(BUDGETS),predictions=prediction)
            runs.append(dict(target=protocol['target_workload'],cap=cap,seed=seed,policy=POLICY,**result))
            known = [r for r in outcomes if r.get('status','success') == 'success']
            estimates = {p['candidate_id']:p for p in prediction}
            diagnostics.append(dict(seed=seed,cap=cap,known_utility_rows=len(known),unknown_utility_rows=len(outcomes)-len(known),
                normalized_feasible_utility_mae=statistics.mean(abs(
                    estimates[r['candidate_id']]['mean_saved_cycles_per_occurrence']-decision_utility(r,cap)) for r in known) if known else None))
    for run in runs:
        cap = run['cap']
        reference = max([1.0]+[r['speedup'] for r in outcomes if b._feasible(r,cap,CLOCK_MHZ)])
        for point in run['curve']:
            attempted = [labels[identity] for identity in point['attempted_ids']]
            point.update(gap_to_best_verified=reference-point['best_speedup'],
                reference_kind='best verified; full pool censored' if reference_censored else 'measured fixed-pool oracle',
                known_infeasible_attempts=sum(r.get('status','success')=='success' and not b._feasible(r,cap,CLOCK_MHZ) for r in attempted),
                unknown_attempts=sum(r.get('status','success')!='success' for r in attempted))
    summary = []
    for cap in AREA_CAPS:
        for policy in (*b.POLICIES,POLICY):
            for budget in BUDGETS:
                points = [run['curve'][budget-1] for run in runs if run['cap']==cap and run['policy']==policy]
                summary.append(dict(cap=cap,policy=policy,budget=budget,dependent_seed_count=len(points),
                    mean_best_speedup=statistics.mean(p['best_speedup'] for p in points),
                    mean_gap_to_best_verified=statistics.mean(p['gap_to_best_verified'] for p in points),
                    mean_target_measurement_seconds=statistics.mean(p['target_measurement_seconds'] for p in points),
                    mean_known_infeasible_attempts=statistics.mean(p['known_infeasible_attempts'] for p in points),
                    mean_unknown_attempts=statistics.mean(p['unknown_attempts'] for p in points)))
    result = dict(schema=protocol['schema'],protocol_sha256=c.sha(root/'protocol.json'),outcomes_sha256=c.digest(outcomes),
        scope=protocol['scope'],reference_censored=reference_censored,runs=runs,summary=summary,
        utility_diagnostics=diagnostics,control_report_sha256=c.sha(root/'model/report.json'),
        trajectories=len(runs),endpoints=sum(len(r['curve']) for r in runs),new_native_jobs=0,
        superiority_established=False,limitations=protocol['limitations'])
    if verify:
        def stable(value):
            if isinstance(value,(list,tuple)):return [stable(v) for v in value]
            if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('inference_seconds','replay_search_host_seconds')}
            return value
        c.require(stable(result) == stable(c.unseal(root/'report.json')), 'Feasible benefit replay differs')
    else:c.seal(root/'report.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','predict','evaluate','verify'))
    parser.add_argument('--root',type=Path,required=True)
    for name in ('history','public','contexts','cost-provenance','outcomes','output','input-bindings'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--target-workload');parser.add_argument('--target-labels-observed',type=int)
    parser.add_argument('--calibration-cost-seconds',type=float)
    parser.add_argument('--scope',choices=SCOPES,default=SCOPES[0])
    parser.add_argument('--reference-censored',action='store_true')
    parser.add_argument('--seed',type=int,choices=SEEDS,default=0)
    parser.add_argument('--area-cap',type=int,choices=AREA_CAPS,default=64)
    args=parser.parse_args(argv)
    if args.command=='freeze':
        c.require(all((args.history,args.public,args.contexts,args.target_workload,
                       args.target_labels_observed is not None,args.calibration_cost_seconds is not None)), 'Missing freeze inputs')
        result=freeze(c.unseal(args.history),c.unseal(args.public),c.unseal(args.contexts),args.root,
            target_workload=args.target_workload,target_labels_observed=args.target_labels_observed,
            calibration_cost_seconds=args.calibration_cost_seconds,scope=args.scope,
            cost_provenance=c.unseal(args.cost_provenance) if args.cost_provenance else None,
            input_bindings=c.unseal(args.input_bindings) if args.input_bindings else None)
        print(dict(historical_fitting_rows=result['historical_fitting_rows'],postfilter_groups=result['historical_postfilter_groups'],target_labels_read=0))
    elif args.command=='predict':
        c.require(args.public is not None and args.output is not None, 'Predict requires sealed public input and fresh output')
        c.require(not args.output.exists(), 'Fresh prediction output required')
        case=authenticate(args.root)
        model=FeasibleBenefitPredictor.load(args.root/'utility-models'/f'seed-{args.seed}')
        values=model.predict(c.unseal(args.public),area_cap=args.area_cap)
        c.seal(args.output,values);print(dict(predictions=len(values),target_labels_read=0))
    else:
        c.require(args.outcomes is not None,'Sealed private outcomes required')
        result=evaluate(args.root,c.unseal(args.outcomes),reference_censored=args.reference_censored,verify=args.command=='verify')
        print({k:result[k] for k in ('trajectories','endpoints','new_native_jobs')})

if __name__=='__main__':main()
