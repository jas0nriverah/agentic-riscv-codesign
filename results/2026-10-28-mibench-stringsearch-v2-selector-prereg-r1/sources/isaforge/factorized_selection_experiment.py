"""One fixed feasibility/benefit separation, alongside eleven frozen controls.

This wrapper does not run hardware. Complete outcomes are privileged scoring
inputs; prediction accepts only the public projection. No diagnostic tunes the
classifier, confidence threshold, stopping rule or model settings.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import statistics
import time

from . import budgeted_selection as b, codesign as c
from . import feasible_benefit_experiment as controls
from .feasibility_selection import (AREA_CAPS, CLOCK_MHZ, MODEL_SETTINGS,
    BUDGET_FEATURE, FeasibilitySelectionPredictor)
from .model import _number
from .speedup_corpus import family

POLICY = 'factorized_feasibility_xgb'
SEEDS, BUDGETS = controls.SEEDS, controls.BUDGETS
SOURCES = ('isaforge/factorized_selection_experiment.py',
    'isaforge/feasibility_selection.py', *controls.SOURCES)
SCHEMA = 'isaforge-factorized-selection-v1'
INVALID_FAILURES = {'memory_contract_failure', 'recorded_self_check_failure',
                    'recorded_execution_failure'}
UNKNOWN_FAILURES = {'unknown', 'infrastructure_unknown'}


def source_identity(public, contexts, target_workload):
    public = b.public_rows(public)
    benchmarks = {row['benchmark'] for row in public}
    c.require(len(benchmarks) == 1, 'One target context required')
    benchmark = public[0]['benchmark']
    c.require(benchmark.split(':', 1)[0] == target_workload,
              'Public benchmark and held-out source disagree')
    c.require(benchmark in contexts, 'Target provenance context required')
    context = contexts[benchmark]
    c.require(context.get('workload_group') == target_workload and
              benchmark == target_workload + ':' + context['context_id'],
              'Target source/context identity disagrees')
    return public


def support_diagnostics(history, public):
    """Training-range extrapolation flags only; never gates or reranks queries."""
    ranges = {key: [min(row[key] for row in history), max(row[key] for row in history)]
              for key in b.STRUCTURAL_COLUMNS}
    return dict(training_ranges=ranges, candidates=[dict(candidate_id=row['candidate_id'],
        outside_training_range=[key for key, (low, high) in ranges.items()
                                if not low <= row[key] <= high]) for row in public],
        use='Diagnostic only; no abstention threshold or policy modification.')


def freeze(history, public, contexts, output, *, target_workload,
           target_labels_observed, calibration_cost_seconds, cost_provenance=None,
           input_bindings=None, scope='prospective source holdout'):
    output = Path(output)
    c.require(type(target_labels_observed) is int and target_labels_observed == 0,
              'Freeze requires explicit zero observed target candidate labels')
    c.require(scope in ('prospective source holdout', 'consumed-data development'),
              'Explicit source-holdout scope required')
    c.require(not output.exists(), 'Fresh factorized experiment directory required')
    public = source_identity(public, contexts, target_workload)
    c.require(all(row['workload_group'] != target_workload for row in history),
              'Entire target source must be excluded')
    # Delegate identical cohort selection and every old model to the frozen code.
    original = controls.freeze(history, public, contexts, output/'controls11',
        target_workload=target_workload, target_labels_observed=target_labels_observed,
        calibration_cost_seconds=calibration_cost_seconds, cost_provenance=cost_provenance,
        input_bindings=input_bindings, scope=scope)
    training = c.unseal(output/'controls11/model/history.json')
    c.require(len({row['workload_group'] for row in training}) >= 2,
              'At least two post-family-filter sources required')
    predictions, costs = [], []
    for seed in SEEDS:
        started = time.monotonic()
        model = FeasibilitySelectionPredictor(seed).fit(training)
        fit_seconds = time.monotonic() - started
        started = time.monotonic()
        values = {str(cap): model.predict(public, area_cap=cap) for cap in AREA_CAPS}
        prediction_seconds = time.monotonic() - started
        exported = output/'feasibility-models'/f'seed-{seed}'
        model.save(exported)
        loaded = FeasibilitySelectionPredictor.load(exported)
        c.require(all(loaded.predict(public, area_cap=cap) == values[str(cap)] for cap in AREA_CAPS),
                  'Portable classifier predictions differ')
        predictions.append(dict(seed=seed, by_cap=values))
        costs.append(dict(seed=seed, fitting_seconds=fit_seconds,
                          all_cap_prediction_seconds=prediction_seconds,
                          fitting_candidates=len(training), area_per_op=model.area_per_op))
    c.seal(output/'feasibility-predictions.json', predictions)
    c.seal(output/'feasibility-costs.json', costs)
    c.seal(output/'support-diagnostics.json', support_diagnostics(training, public))
    artifacts = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob('*')) if path.is_file()}
    protocol = dict(schema=SCHEMA, scope=scope, target_workload=target_workload,
        target_labels_read=0, target_labels_observed=0, source_bindings={name: c.sha(c.ROOT/name) for name in SOURCES},
        input_bindings=input_bindings or {}, source_history_digest=c.digest(history),
        contexts_digest=c.digest(contexts), public_digest=c.digest(public),
        historical_available_rows=len(history), historical_fitting_rows=len(training),
        historical_training_ids=[row['candidate_id'] for row in training],
        historical_postfilter_groups=sorted({row['workload_group'] for row in training}),
        excluded_related_ids=original['excluded_related_ids'], packages=original['packages'],
        control_protocol_sha256=c.sha(output/'controls11/protocol.json'),
        policies=[*b.POLICIES, controls.POLICY, POLICY], seeds=list(SEEDS), budgets=list(BUDGETS),
        area_caps=list(AREA_CAPS), clock_mhz=CLOCK_MHZ, model_settings=MODEL_SETTINGS,
        budget_feature=BUDGET_FEATURE, cost_provenance=cost_provenance or {},
        primary_endpoint=dict(area_delta_lut4=64, budget=3, clock_mhz=12),
        target='successful-execution conditional hardware feasibility, multiplied by nonnegative analytic fractional cycle savings',
        predeclared_diagnostics=['source/cap Brier score', 'known-infeasible paid queries',
            'missed feasible optima', 'cross-cap score monotonicity violations', 'training support'],
        artifacts=artifacts, limitations=[
            'One new held-out source is not broad generalization evidence.',
            'Historical measurements, failed attempts and consumed development costs are not free.',
            'Logistic scores and candidate-bootstrap disagreement are not calibrated confidence.',
            'Hardware feasibility is conditional on successful verified execution; unknown failures are not negative labels.',
            'Analytic cycle benefit is a public calibrated estimate, not a new measured speedup label.',
            'This is static zero-shot selection; the unchanged GP control performs paid adaptation.',
            'Five bootstrap/tie seeds are dependent repetitions.',
            'Full-pool serial collection permits cooperative paid replay, not live adaptive native search.',
            'Single instructions only; combinations require joint execution and hardware measurement.'])
    c.seal(output/'protocol.json', protocol)
    return protocol


def authenticate(root):
    root = Path(root)
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol['schema'] == SCHEMA and type(protocol['target_labels_read']) is int and
              protocol['target_labels_read'] == 0 and type(protocol['target_labels_observed']) is int and
              protocol['target_labels_observed'] == 0, 'Expected zero-label factorized freeze')
    c.require(set(protocol['source_bindings']) == set(SOURCES), 'Complete experiment sources required')
    for name, expected in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == expected, 'Frozen factorized source changed: ' + name)
    for name, expected in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == expected, 'Frozen dependency changed: ' + name)
    c.require(protocol['policies'] == [*b.POLICIES, controls.POLICY, POLICY] and
              protocol['seeds'] == list(SEEDS) and protocol['budgets'] == list(BUDGETS) and
              protocol['area_caps'] == list(AREA_CAPS) and protocol['clock_mhz'] == CLOCK_MHZ and
              protocol['model_settings'] == MODEL_SETTINGS, 'Fixed comparison settings differ')
    for name, expected in protocol['artifacts'].items():
        c.require(c.sha(controls._relative(root, name)) == expected, 'Frozen factorized artifact changed: ' + name)
    case = controls.authenticate(root/'controls11')
    c.require(c.sha(root/'controls11/protocol.json') == protocol['control_protocol_sha256'],
              'Frozen eleven-control protocol differs')
    training, public = case['history'], case['public']
    child = case['protocol']
    for outer, inner in (('public_digest', 'public_digest'), ('contexts_digest', 'contexts_digest'),
                         ('source_history_digest', 'history_digest'), ('target_workload', 'target_workload'),
                         ('input_bindings', 'input_bindings'), ('cost_provenance', 'cost_provenance'),
                         ('historical_available_rows', 'historical_available_rows')):
        c.require(protocol[outer] == child[inner], 'Classifier/control metadata differs: ' + outer)
    c.require(protocol['historical_training_ids'] == case['protocol']['historical_training_ids'] ==
              [row['candidate_id'] for row in training], 'Classifier/control training cohort differs')
    c.require(protocol['historical_postfilter_groups'] == sorted({row['workload_group'] for row in training}) and
              len(protocol['historical_postfilter_groups']) >= 2, 'Postfilter source groups differ')
    source_identity(public, case['control_protocol']['contexts'], protocol['target_workload'])
    predictions = c.unseal(root/'feasibility-predictions.json')
    c.require(len(predictions) == len(SEEDS) and {row['seed'] for row in predictions} == set(SEEDS),
              'Complete unique prediction seeds required')
    for row in predictions:
        c.require(set(row['by_cap']) == {str(cap) for cap in AREA_CAPS}, 'Complete cap prediction grid required')
        model = FeasibilitySelectionPredictor.load(root/'feasibility-models'/f"seed-{row['seed']}")
        c.require(model.training_ids == protocol['historical_training_ids'], 'Classifier historical cohort differs')
        c.require(all(model.predict(public, area_cap=cap) == row['by_cap'][str(cap)] for cap in AREA_CAPS),
                  'Classifier/predictions differ')
    c.require(c.unseal(root/'support-diagnostics.json') == support_diagnostics(training, public),
              'Training support diagnostics differ')
    return dict(protocol=protocol, history=training, public=public, predictions=predictions, controls=case)


def checked_outcomes(public, outcomes, native_audit):
    """Fail closed on missing classification and on a falsely complete oracle."""
    c.require(isinstance(native_audit, dict) and native_audit.get('attempt_collection_complete') is True and
              native_audit.get('candidate_wall_seconds_complete') is True and not native_audit.get('unattempted'),
              'Complete native attempt audit required')
    c.require(native_audit.get('public') == public and native_audit.get('outcomes') == outcomes,
              'Outcomes/public pool differ from native audit')
    c.require(native_audit.get('context_id') == public[0]['benchmark'].split(':', 1)[1],
              'Native/selection context identity differs')
    labels = {row['candidate_id']: row for row in outcomes}
    c.require(len(labels) == len(outcomes) == len(public) and set(labels) == {row['candidate_id'] for row in public},
              'One unique attempted outcome per candidate required')
    c.require(native_audit.get('charged_candidate_attempts') == len(public), 'Charged native attempt count differs')
    pool_names = native_audit.get('pool_names', [])
    c.require(len(pool_names) == len(public) and len(set(pool_names)) == len(pool_names),
              'Complete native pool name/identity order required')
    failed_rows = native_audit.get('failed_or_interrupted', [])
    native_failures = {row['name']: row for row in failed_rows}
    c.require(len(native_failures) == len(failed_rows), 'Unique native failures required')
    censored = set()
    failed = set()
    for name, candidate in zip(pool_names, public):
        row = labels[candidate['candidate_id']]
        if b.validate_outcome(row, candidate):
            c.require(name not in native_failures, 'Success also has native failure evidence')
            continue
        failed.add(name)
        failure_class = row.get('failure_class')
        c.require(failure_class in INVALID_FAILURES | UNKNOWN_FAILURES and type(row.get('reference_censored')) is bool,
                  'Classified failure and boolean censorship required')
        c.require(row['reference_censored'] == (failure_class in UNKNOWN_FAILURES),
                  'Failure classification/censorship disagree')
        failure = native_failures.get(name, {})
        c.require(failure.get('classification') == failure_class and failure.get('error') == row['error'] and
                  failure.get('elapsed_seconds') == row['measurement_seconds'] and
                  failure.get('reference_censored') == row['reference_censored'],
                  'Failure differs from native classification')
        if row['reference_censored']:
            censored.add(name)
    c.require(failed == set(native_failures), 'Native/scorer failed candidate identities disagree')
    c.require(censored == set(native_audit.get('reference_censored_candidates', [])),
              'Native/scorer censored candidate identities disagree')
    return bool(censored)


def prediction_diagnostics(predictions, outcomes):
    known = [row for row in outcomes if row.get('status', 'success') == 'success']
    rows = []
    for prediction in predictions:
        by_cap = {cap: {row['candidate_id']: row for row in prediction['by_cap'][str(cap)]} for cap in AREA_CAPS}
        for cap in AREA_CAPS:
            values = by_cap[cap]
            rows.append(dict(seed=prediction['seed'], cap=cap, known_candidates=len(known),
                failed_unknown_hardware_candidates=len(outcomes)-len(known),
                feasibility_brier=statistics.mean((values[row['candidate_id']]['feasibility_score_mean'] -
                    float(b._feasible(row, cap, CLOCK_MHZ)))**2 for row in known) if known else None,
                calibrated=False))
        violations = [identity for identity in by_cap[AREA_CAPS[0]] if any(
            by_cap[lower][identity]['feasibility_score_mean'] > by_cap[upper][identity]['feasibility_score_mean']
            for lower, upper in zip(AREA_CAPS[:-1], AREA_CAPS[1:]))]
        rows.append(dict(seed=prediction['seed'], cap='all', cross_cap_monotonicity_violations=violations,
                         compared_candidates=len(outcomes), calibrated=False))
    return rows


def evaluate(root, outcomes, *, native_audit, outer_times, verify=False):
    root = Path(root)
    case = authenticate(root)
    public, protocol = case['public'], case['protocol']
    censored = checked_outcomes(public, outcomes, native_audit)
    c.require(set(outer_times) == {row['candidate_id'] for row in public}, 'Complete candidate outer timers required')
    for row in outcomes:
        c.require(_number(outer_times[row['candidate_id']], 'outer operation seconds', positive=True) >=
                  row['measurement_seconds'], 'Outer operation must enclose attempt ledger time')
    c.require(verify or not (root/'report.json').exists(), 'Preserve prior factorized report')
    old = controls.evaluate(root/'controls11', outcomes, reference_censored=censored, verify=verify)
    runs = copy.deepcopy(old['runs'])
    labels = {row['candidate_id']: row for row in outcomes}
    for prediction in case['predictions']:
        for cap in AREA_CAPS:
            # The frozen static selector only requires a decision-score key.
            # This alias means predicted feasible fractional savings, not speedup.
            adapted = [dict(row, mean_fractional_cycle_savings=row['decision_score'])
                       for row in prediction['by_cap'][str(cap)]]
            result = controls.search(public, lambda row: copy.deepcopy(labels[row['candidate_id']]),
                area_cap=cap, seed=prediction['seed'], budget=max(BUDGETS), predictions=adapted)
            runs.append(dict(target=protocol['target_workload'], cap=cap, seed=prediction['seed'], policy=POLICY, **result))
    for run in runs:
        cap = run['cap']
        reference = max([1.0] + [row['speedup'] for row in outcomes if b._feasible(row, cap, CLOCK_MHZ)])
        for point in run['curve']:
            attempted = [labels[identity] for identity in point['attempted_ids']]
            point.update(gap_to_best_verified=reference-point['best_speedup'],
                reference_kind='best verified; full pool censored' if censored else 'measured fixed-pool oracle',
                known_infeasible_attempts=sum(row.get('status', 'success') == 'success' and
                                             not b._feasible(row, cap, CLOCK_MHZ) for row in attempted),
                unknown_attempts=sum(row.get('status', 'success') != 'success' for row in attempted))
            point['target_outer_operation_seconds'] = sum(outer_times[identity] for identity in point['attempted_ids'])
    summary = []
    for cap in AREA_CAPS:
        for policy in protocol['policies']:
            for budget in BUDGETS:
                points = [run['curve'][budget-1] for run in runs if run['cap'] == cap and run['policy'] == policy]
                summary.append(dict(cap=cap, policy=policy, budget=budget, dependent_seed_count=len(points),
                    mean_best_speedup=statistics.mean(point['best_speedup'] for point in points),
                    mean_gap_to_best_verified=statistics.mean(point['gap_to_best_verified'] for point in points),
                    mean_target_measurement_seconds=statistics.mean(point['target_measurement_seconds'] for point in points),
                    mean_target_outer_operation_seconds=statistics.mean(point['target_outer_operation_seconds'] for point in points),
                    mean_known_infeasible_attempts=statistics.mean(point['known_infeasible_attempts'] for point in points),
                    mean_unknown_attempts=statistics.mean(point['unknown_attempts'] for point in points)))
    result = dict(schema=SCHEMA, protocol_sha256=c.sha(root/'protocol.json'), outcomes_sha256=c.digest(outcomes),
        native_audit_digest=c.digest(native_audit), scope=protocol['scope'], reference_censored=censored,
        candidate_outer_operation_seconds=outer_times,
        runs=runs, summary=summary, feasibility_diagnostics=prediction_diagnostics(case['predictions'], outcomes),
        control_report_sha256=c.sha(root/'controls11/report.json'), trajectories=len(runs),
        endpoints=sum(len(run['curve']) for run in runs), new_native_jobs=0,
        superiority_established=False, limitations=protocol['limitations'])
    if verify:
        def stable(value):
            if isinstance(value, (list, tuple)): return [stable(item) for item in value]
            if isinstance(value, dict): return {key: stable(item) for key, item in value.items()
                if key not in ('inference_seconds', 'replay_search_host_seconds')}
            return value
        c.require(stable(result) == stable(c.unseal(root/'report.json')), 'Factorized policy replay differs')
    else:
        c.seal(root/'report.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'predict', 'evaluate', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    for name in ('history', 'public', 'contexts', 'cost-provenance', 'input-bindings', 'outcomes', 'native-audit', 'outer-times', 'output'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--target-workload')
    parser.add_argument('--target-labels-observed', type=int)
    parser.add_argument('--calibration-cost-seconds', type=float)
    parser.add_argument('--scope', choices=('prospective source holdout', 'consumed-data development'), default='prospective source holdout')
    parser.add_argument('--seed', type=int, choices=SEEDS, default=0)
    parser.add_argument('--area-cap', type=int, choices=AREA_CAPS, default=64)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        c.require(all((args.history, args.public, args.contexts, args.target_workload,
                       args.target_labels_observed is not None, args.calibration_cost_seconds is not None)), 'Missing freeze inputs')
        result = freeze(c.unseal(args.history), c.unseal(args.public), c.unseal(args.contexts), args.root,
            target_workload=args.target_workload, target_labels_observed=args.target_labels_observed,
            calibration_cost_seconds=args.calibration_cost_seconds, scope=args.scope,
            cost_provenance=c.unseal(args.cost_provenance) if args.cost_provenance else None,
            input_bindings=c.unseal(args.input_bindings) if args.input_bindings else None)
        print(dict(historical_fitting_rows=result['historical_fitting_rows'], target_labels_read=0))
    elif args.command == 'predict':
        c.require(args.public is not None and args.output is not None and not args.output.exists(), 'Public input and fresh prediction output required')
        authenticate(args.root)
        model = FeasibilitySelectionPredictor.load(args.root/'feasibility-models'/f'seed-{args.seed}')
        values = model.predict(c.unseal(args.public), area_cap=args.area_cap)
        c.seal(args.output, values)
        print(dict(predictions=len(values), target_labels_read=0))
    else:
        c.require(args.outcomes is not None and args.native_audit is not None and args.outer_times is not None,
                  'Sealed private outcomes, native audit and outer timers required')
        result = evaluate(args.root, c.unseal(args.outcomes), native_audit=c.unseal(args.native_audit),
                          outer_times=c.unseal(args.outer_times), verify=args.command == 'verify')
        print({key: result[key] for key in ('trajectories', 'endpoints', 'new_native_jobs')})


if __name__ == '__main__':
    main()
