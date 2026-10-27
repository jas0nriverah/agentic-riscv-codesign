"""Freeze label-free third-workload predictions, then replay a fixed comparison.

This is cooperative offline replay, not an external-agent security boundary.
Execution-aware feature choice was motivated by consumed development pools.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import random
import statistics
import time

from . import codesign as c
from .features import FEATURE_COLUMNS
from .model import SpeedupPredictor, feature_matrix, validate_training_rows
from .ranking import SpeedupRanker
from .speedup_corpus import family

EXECUTION_COLUMNS = ('baseline_cpi', 'replacement_execution_fraction',
                     'occurrence_size_min', 'occurrence_size_max',
                     'dynamic_software_cycles', 'dynamic_custom_cycles',
                     'dynamic_shift_extra_cycles', 'estimated_cycle_reduction')
POLICIES = ('frequency', 'merit', 'calibrated_latency', 'random',
            'regression_zero_shot', 'ranking_zero_shot', 'execution_regression_zero_shot')
SOURCES = ('isaforge/prospective_selection.py', 'isaforge/model.py',
           'isaforge/ranking.py', 'isaforge/features.py', 'isaforge/latency_features.py',
           'isaforge/codesign.py', 'isaforge/selection.py', 'isaforge/speedup_corpus.py',
           'isaforge/prospective_inputs.py', 'isaforge/partitioned_workload.py',
           'isaforge/compact_workload.py', 'isaforge/workload_audit.py',
           'isaforge/workload_experiment.py', 'isaforge/assembly_lowering.py',
           'scripts/analyze_speedup_model.py', 'scripts/calibrate_picorv32_latency.py',
           'hardware/latency_sim.cpp', 'src/tracing.py', 'src/candidates.py',
           'src/verify_candidate_fusions.py')
PUBLIC_KEYS = ('candidate_id', 'benchmark', 'formula', *FEATURE_COLUMNS, 'latency_features')
CONTEXT_KEYS = ('compiler_flags', 'ram_bytes', 'stack_bytes', 'hardware_context_id',
                'baseline_provenance')


def public_rows(rows):
    """Reject outcomes at freeze, rather than silently accepting a labeled file."""
    allowed = set(PUBLIC_KEYS)
    c.require(rows and len({r['candidate_id'] for r in rows}) == len(rows), 'Unique public pool required')
    c.require(all(set(r) <= allowed for r in rows), 'Public input contains non-public fields')
    result = [{k: copy.deepcopy(r[k]) for k in PUBLIC_KEYS} for r in rows]
    feature_matrix(result)
    for row in result:
        c.require(isinstance(row['benchmark'], str) and row['benchmark'], 'Explicit context required')
        family(row['formula'])
        values = row['latency_features']
        for key in (*EXECUTION_COLUMNS, 'estimated_speedup'):
            from .model import _number
            _number(values[key], key)
    return result


def execution_matrix(rows):
    return [old + [float(row['latency_features'][k]) for k in EXECUTION_COLUMNS]
            for row, old in zip(rows, feature_matrix(rows))]


def execution_predictions(training, public, seed, predictor=None):
    """Fixed baseline ensemble settings; only the feature columns differ.

    Reuses fitted estimator configurations and reproduces bootstrap draws from
    SpeedupPredictor. This explicit ablation adds no target adaptation or search.
    """
    import numpy as np
    predictor = predictor or SpeedupPredictor(seed=seed).fit(training)
    if not public:
        return []
    if predictor._constant is not None:
        return predictor.predict(public)
    from sklearn.base import clone
    rng = np.random.default_rng(seed)
    x, y = np.asarray(execution_matrix(training), dtype=float), np.asarray([r['speedup'] for r in training], dtype=float)
    models = []
    for template in predictor._models:
        indices = rng.integers(0, len(training), size=len(training))
        rng.integers(0, 2**31 - 1)
        model = clone(template)
        model.fit(x[indices], y[indices]); models.append(model)
    # Existing predictor computes ensemble reductions; its fixed feature reader
    # cannot consume extended vectors, so reduce the same samples explicitly.
    samples = np.stack([m.predict(execution_matrix(public)) for m in models])
    if not np.isfinite(samples).all():
        raise ValueError('Regressor produced non-finite predictions')
    scales = np.maximum(np.abs(samples).max(axis=0), 1.0)
    normalized = samples / scales
    means = normalized.mean(axis=0) * scales
    stds = normalized.std(axis=0) * scales
    tail = (1 - predictor.interval) / 2
    lower, upper = np.quantile(normalized, [tail, 1 - tail], axis=0) * scales
    return [dict(candidate_id=r['candidate_id'], mean=float(means[i]),
                 std=float(stds[i]), lower=float(lower[i]), upper=float(upper[i]))
            for i, r in enumerate(public)]


def support(training, public, execution=False):
    columns = list(FEATURE_COLUMNS) + (list(EXECUTION_COLUMNS) if execution else [])
    matrix = execution_matrix if execution else feature_matrix
    train, target = matrix(training), matrix(public)
    ranges = [(min(v[i] for v in train), max(v[i] for v in train)) for i in range(len(columns))]
    return [dict(candidate_id=r['candidate_id'], outside_training_ranges=[k for k, v, (lo, hi)
                in zip(columns, vector, ranges) if not lo <= v <= hi]) for r, vector in zip(public, target)]


def freeze(history, history_features, target, contexts, output, *, target_workload,
           calibration_cost_seconds, area_cap, seeds=(0, 1, 2, 3, 4), budgets=(1, 2, 3)):
    """Accept in-memory inputs; caller authenticates baseline feature extraction.

    Persist every supplied context and evidence digest. Contexts are indexed by
    exact benchmark/build identities; differing contexts are explicit transfer.
    """
    output = Path(output)
    c.require(not output.exists(), 'Use a fresh prospective directory')
    public = public_rows(target)
    c.require(len({r['benchmark'] for r in public}) == 1, 'Exactly one target context required')
    validate_training_rows(history)
    c.require(len({r['workload_group'] for r in history}) >= 2, 'Two historical workload groups required')
    c.require(all(r['workload_group'] != target_workload for r in history), 'Target workload present in history')
    c.require(all(type(v) is int and v >= 0 for v in seeds) and seeds, 'Invalid seeds')
    c.require(all(type(v) is int and 0 < v <= len(public) for v in budgets) and budgets, 'Invalid budgets')
    from .model import _number
    _number(calibration_cost_seconds, 'calibration cost')
    c.require(_number(area_cap, 'area cap') >= 0, 'Invalid area cap')
    c.require(calibration_cost_seconds >= 0, 'Negative calibration cost')
    needed = {r['benchmark'] for r in history + public}
    c.require(needed <= set(contexts), 'Missing explicit compilation/memory context')
    for name in needed:
        c.require(all(k in contexts[name] for k in CONTEXT_KEYS), 'Incomplete context: ' + name)
    enriched = {r['candidate_id']: r for r in history_features}
    families = {family(r['formula']) for r in public}
    training, excluded = [], []
    for row in history:
        c.require(row['benchmark'] not in {r['benchmark'] for r in public}, 'Target context in history')
        if family(row['formula']) in families:
            excluded.append(row['candidate_id']); continue
        features = enriched[row['candidate_id']]
        c.require(all(features[k] == row[k] for k in ('formula', 'benchmark', *FEATURE_COLUMNS)), 'Historical features changed')
        training.append({**row, 'latency_features': copy.deepcopy(features['latency_features'])})
    c.require(len(training) >= 2, 'Insufficient unrelated history')
    predictions = []
    for seed in seeds:
        began = time.monotonic()
        regressor = SpeedupPredictor(seed=seed).fit(training)
        regression = regressor.predict(public)
        regression_seconds = time.monotonic() - began
        began = time.monotonic()
        ranking = SpeedupRanker(seed=seed).fit(training).predict(public)
        ranking_seconds = time.monotonic() - began
        began = time.monotonic()
        execution = execution_predictions(training, public, seed, regressor)
        predictions.append(dict(seed=seed, regression=regression, ranking=ranking, execution=execution,
                                inference_seconds=dict(regression_zero_shot=regression_seconds,
                                  ranking_zero_shot=ranking_seconds,
                                  execution_regression_zero_shot=time.monotonic()-began)))
    protocol = dict(schema='isaforge-prospective-selection-v1', target_workload=target_workload,
        area_cap=area_cap, target_labels_read=0, target_candidates=len(public), historical_available_rows=len(history),
        historical_fit_rows=len(training), fit_workload_groups=sorted({r['workload_group'] for r in training}),
        excluded_related_ids=excluded, seeds=list(seeds), budgets=list(budgets), policies=list(POLICIES),
        execution_columns=list(EXECUTION_COLUMNS), contexts=contexts,
        uniform_contexts=len({c.digest(contexts[k]) for k in needed}) == 1,
        fixed_regressor=dict(ensemble_size=20,n_estimators=80,max_depth=2,learning_rate=.05,
                             objective='reg:squarederror',bootstrap='rows, size n, replacement'),
        selection_scope='Zero-shot single instructions; no target adaptation or constraint prediction',
        pool_bias='Pool is caller-declared; a top-merit pool does not assess candidates excluded by merit.',
        historical_candidate_wall_seconds=sum(r['measurement_seconds'] for r in history),
        calibration_command_seconds=calibration_cost_seconds,
        support=support(training, public), execution_support=support(training, public, True),
        source_bindings={p:c.sha(c.ROOT/p) for p in SOURCES},
        packages={p:importlib.metadata.version(p) for p in ('numpy','xgboost','scikit-learn')},
        input_digests=dict(history=c.digest(history), history_features=c.digest(history_features)),
        limitations=['One prospective workload does not establish broad generalization.',
          'Bootstrap spread is not calibrated uncertainty; support ranges are descriptive only.',
          'Execution-feature choice was motivated by consumed development data; settings are fixed.',
          'Historical candidate wall time excludes setup; calibration command time is a separate overlapping timer category.',
          'Offline replay uses recorded costs; no fresh end-to-end policy timing or set composition.',
          'Caller must authenticate baseline extraction and hardware calibration compatibility.'])
    output.mkdir(parents=True)
    for name, value in (('public.json', public), ('predictions.json', predictions)):
        c.seal(output/name, value)
    protocol['artifacts'] = {name:c.sha(output/name) for name in ('public.json','predictions.json')}
    c.seal(output/'protocol.json', protocol)
    return protocol


def evaluate(root, outcomes, *, area_cap, verify=False):
    """Only call after the permitted collection; all acquisition orders are frozen."""
    root = Path(root); protocol = c.unseal(root/'protocol.json')
    c.require(area_cap == protocol['area_cap'], 'Frozen area constraint changed')
    for name, digest in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == digest, 'Frozen source changed: '+name)
    for name, version in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == version, 'Frozen package changed')
    for name, digest in protocol['artifacts'].items():
        c.require(c.sha(root/name) == digest, 'Frozen artifact changed: '+name)
    c.require(verify or not (root/'report.json').exists(), 'Preserve prior report')
    public, predictions = c.unseal(root/'public.json'), c.unseal(root/'predictions.json')
    labels = {r['candidate_id']:r for r in outcomes}
    c.require(len(labels)==len(outcomes) and set(labels)=={r['candidate_id'] for r in public}, 'Complete measured oracle required')
    for row in public:
        measured=labels[row['candidate_id']]
        c.require(all(measured[k]==row[k] for k in ('benchmark','formula',*FEATURE_COLUMNS)), 'Measured public identity changed')
        c.require(measured['area_cap']==area_cap, 'Area constraint mismatch')
        c._measurement(measured)
        c.require(type(measured.get('timing_feasible')) is bool, 'Measured timing required')
        from .model import _number
        c.require(_number(measured['measurement_seconds'], 'measurement time')>=0, 'Negative time')
    oracle=max([1.0]+[r['speedup'] for r in outcomes if r['area']<=area_cap and r['timing_feasible']])
    runs=[]; diagnostics=[]
    for prediction in predictions:
        seed=prediction['seed']
        for model_name in ('regression','execution'):
            values=prediction[model_name]
            diagnostics.append(dict(seed=seed,model=model_name,
                mae=statistics.mean(abs(labels[v['candidate_id']]['speedup']-v['mean']) for v in values),
                ensemble_interval_coverage=statistics.mean(
                    v['lower']<=labels[v['candidate_id']]['speedup']<=v['upper'] for v in values),
                mean_interval_width=statistics.mean(v['upper']-v['lower'] for v in values),
                independent_test_workloads=1,calibrated_confidence=False))
        scores={'regression_zero_shot':{r['candidate_id']:r['mean'] for r in prediction['regression']},
                'ranking_zero_shot':{r['candidate_id']:r['rank_score'] for r in prediction['ranking']},
                'execution_regression_zero_shot':{r['candidate_id']:r['mean'] for r in prediction['execution']}}
        for policy in protocol['policies']:
            ordered=copy.deepcopy(public); random.Random(seed).shuffle(ordered)
            if policy in scores: ordered.sort(key=lambda r:-scores[policy][r['candidate_id']])
            elif policy!='random':
                ordered.sort(key=lambda r:-(r['latency_features']['estimated_speedup'] if policy=='calibrated_latency'
                                             else r['runs' if policy=='frequency' else 'saved']))
            tools=c.LiveSelectionTools(public, lambda r:copy.deepcopy(labels[r['candidate_id']]), max(protocol['budgets']), area_cap, seed)
            curve=[]
            for row in ordered[:max(protocol['budgets'])]:
                tools.measure(row['candidate_id']); best=tools.choose_final(); speed=best['speedup'] if best else 1.0
                if tools.measurements_used in protocol['budgets']:
                    curve.append(dict(budget=tools.measurements_used, best_speedup=speed, regret=oracle-speed,
                        measured_ids=tools.measured_candidate_ids, selected_id=best['candidate_id'] if best else None,
                        target_candidate_wall_seconds=sum(r['measurement_seconds'] for r in tools.observations.values())))
            runs.append(dict(policy=policy, seed=seed, curve=curve,
                             fit_and_predict_seconds=prediction['inference_seconds'].get(policy, 0),
                             required_historical_labels=protocol['historical_available_rows'] if policy in scores else 0,
                             historical_candidate_wall_seconds=protocol['historical_candidate_wall_seconds'] if policy in scores else 0,
                             calibration_command_seconds=protocol['calibration_command_seconds'] if policy in
                                ('calibrated_latency','execution_regression_zero_shot') else 0))
    summary=[]
    for policy in protocol['policies']:
        for budget in protocol['budgets']:
            points=[point for run in runs if run['policy']==policy
                    for point in run['curve'] if point['budget']==budget]
            summary.append(dict(policy=policy,budget=budget,
                mean_best_speedup=statistics.mean(v['best_speedup'] for v in points),
                mean_regret=statistics.mean(v['regret'] for v in points),
                oracle_hits=sum(v['regret']==0 for v in points),
                mean_target_candidate_wall_seconds=statistics.mean(v['target_candidate_wall_seconds'] for v in points)))
    report=dict(protocol_sha256=c.sha(root/'protocol.json'), outcomes_sha256=c.digest(outcomes),
                oracle_speedup=oracle, oracle_label_count=len(outcomes),
                oracle_candidate_wall_seconds=sum(r['measurement_seconds'] for r in outcomes),
                new_native_jobs=0, runs=runs, summary=summary, diagnostics=diagnostics,
                contexts=protocol['contexts'],
                cost_note='Candidate wall, calibration command, setup provenance and inference times are separate; no complete project total is inferred.',
                broad_generalization_established=False, limitations=protocol['limitations'])
    if verify: c.require(report==c.unseal(root/'report.json'), 'Prospective replay differs')
    else: c.seal(root/'report.json',report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze','evaluate','verify'))
    parser.add_argument('--root',type=Path,required=True)
    for name in ('history','history-features','target-public','contexts','outcomes'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--target-workload'); parser.add_argument('--calibration-cost-seconds',type=float)
    parser.add_argument('--area-cap',type=float)
    args=parser.parse_args(argv)
    if args.command=='freeze':
        c.require(all((args.history,args.history_features,args.target_public,args.contexts,args.target_workload,
                       args.calibration_cost_seconds is not None, args.area_cap is not None)), 'Missing freeze inputs')
        history=c.unseal(args.history); history=history['rows'] if isinstance(history,dict) else history
        result=freeze(history,c.unseal(args.history_features),c.unseal(args.target_public),c.unseal(args.contexts),
                      args.root,target_workload=args.target_workload,calibration_cost_seconds=args.calibration_cost_seconds,area_cap=args.area_cap)
        print({'target_labels_read':0,'historical_fit_rows':result['historical_fit_rows']})
    else:
        c.require(args.outcomes and args.area_cap is not None,'Measured outcomes and area cap required')
        values=c.unseal(args.outcomes); values=values['rows'] if isinstance(values,dict) else values
        print({'runs':len(evaluate(args.root,values,area_cap=args.area_cap,verify=args.command=='verify')['runs'])})


if __name__=='__main__': main()
