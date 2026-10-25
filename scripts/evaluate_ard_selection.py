"""One consumed-data, train-only ARD area surrogate test; no native jobs.

The acquisition is the unchanged finite myopic method. All seventeen completed
controls, exact ten cached cohorts and independent planned horizons are retained.
Only initialize is new; paid/fantasy Gaussian conditioning remains unchanged.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import ard_hardware as a, budgeted_selection as b, codesign as c, finite_selection as f
from scripts import evaluate_finite_selection as e

SCHEMA = 'isaforge-ard-area-selection-development-v1'
POLICY = 'ard_area__fixed_joint_myopic'
BASE = ROOT/'results/2026-10-25-finite-selection-development'
OUTPUT = ROOT/'results/2026-10-25-ard-selection-development'
CONTRACT = ROOT/'docs/ard-area-experiment.md'
CAPS, SEEDS, BUDGETS = e.CAPS, e.SEEDS, e.BUDGETS
SOURCES = tuple(dict.fromkeys(('scripts/evaluate_ard_selection.py', *a.SOURCES, *e.SOURCES)))
HOST_TIMERS = e.HOST_TIMERS | {'semantic_fit_host_seconds', 'joint_construction_host_seconds',
    'ard_start_fit_host_seconds', 'ard_fit_host_seconds', 'initialize_host_seconds'}
LIMITATIONS = [
    'One area-surrogate specification changes covariance family, ARD and historical likelihood fitting together; this does not isolate their individual effects.',
    'All scored sources are consumed development data. Ten cohort/source cases span six sources; seeds, caps, budgets and repeated cohorts are dependent.',
    'The historical 99-label/102-attempt ledger is the frozen original-cohort scope, not all project costs after subsequent source collections.',
    'Only the existing myopic acquisition is evaluated with the new initializer. There is no model, kernel, prior or policy sweep.',
    'Every model fit uses only its original cached historical cohort. New paid observations never cross cases; all update parameters and preprocessing stay fixed after initialization.',
    'Gaussian observation noise, known analytic benefit and the common Beta device model are assumptions; probabilities are not calibrated confidence.',
    'Three deterministic optimizer starts are selected solely by finite historical marginal likelihood; nonconvergence and bound hits remain visible.',
    'Strongest archived control is a retrospective reporting envelope selected within each case/cap/horizon, not a deployable target-label-aware selector.',
    'All seventeen controls are copied exactly. Earlier fourteen-policy B1/B2 controls are prefixes of their horizon-independent three-query searches.',
    'Native ledger costs are reused and overlap across policies/cohorts. Host timers, initialization, original setup and recorded native costs are distinct scopes.',
    'No G723 artifact or outcome is read. Its frozen live policy is outside this experiment.',
    'No new native jobs, fresh-source result, promotion, calibrated-confidence or field-superiority claim.',
]


def source_bindings():
    return {relative: c.sha(ROOT/relative) for relative in SOURCES}


def input_roots():
    return (BASE, *e.input_roots())


def fresh(output, extra=()):
    output = Path(output).resolve()
    protected = [Path(p).resolve() for p in (*input_roots(), *extra)]
    c.require(not output.exists() and not any(output.is_relative_to(p) or p.is_relative_to(output)
        for p in protected), 'Fresh ARD output outside all sealed evidence/input roots required')
    c.require(not any((p/'manifest.json').exists() and (p/'manifest.json.sha256').exists()
                     for p in output.parents), 'Cannot write inside sealed evidence')
    return output


def stable(value):
    if isinstance(value, (list, tuple)):
        return [stable(item) for item in value]
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in HOST_TIMERS}
    return value


def _method_root(root):
    return Path(root)/'models'/POLICY


def _controls():
    original = c.unseal(BASE/'archived-controls.json')
    finite = c.unseal(BASE/'report.json')['endpoints']
    c.require({r['policy'] for r in finite} == set(f.POLICIES), 'All three original finite-model controls required')
    return dict(original_fourteen=original, fixed_joint_three=finite)


def planned_protocol():
    e.manifest(BASE)
    base = e.authenticate(BASE)
    c.require(base['area_caps'] == list(CAPS) and base['seeds'] == list(SEEDS) and
        base['planned_budgets'] == list(BUDGETS), 'Identical frozen caps/seeds/planned horizons required')
    cases = copy.deepcopy(base['cases'])
    for case in cases:
        for filename in e.INPUT_FILES:
            # Reuse the completed finite package's authenticated exact input bytes.
            c.unseal(BASE/'inputs'/case['case_id']/filename)
    bindings = copy.deepcopy(base['input_bindings'])
    bindings[e.name(CONTRACT)] = c.sha(CONTRACT)
    for path in (BASE/'manifest.json', BASE/'protocol.json', BASE/'report.json',
                 BASE/'prediction-release.json', BASE/'archived-controls.json'):
        bindings[e.name(path)] = c.sha(path)
        bindings[e.name(Path(str(path)+'.sha256'))] = c.sha(Path(str(path)+'.sha256'))
    history = copy.deepcopy(base['historical_accounting'])
    history['scope'] = 'Frozen original ten-case historical cohort ledger only; not all project costs after additional source collections.'
    return dict(schema=SCHEMA, scope='consumed-data development', model_identity=POLICY,
        acquisition_policy=f.MYOPIC, new_model_count=1, new_policy_count=1,
        cases=cases, area_caps=list(CAPS), seeds=list(SEEDS), planned_budgets=list(BUDGETS), clock_mhz=12.,
        source_bindings=source_bindings(), input_bindings=bindings,
        packages={key: importlib.metadata.version(key) for key in ('numpy', 'scipy', 'scikit-learn', 'xgboost')},
        initializer_settings=copy.deepcopy(a.SETTINGS), finite_settings=copy.deepcopy(f.SETTINGS),
        semantic_columns=copy.deepcopy(base['semantic_columns']), historical_accounting=history,
        original_finite_manifest_sha256=c.sha(BASE/'manifest.json'),
        original_finite_protocol_sha256=c.sha(BASE/'protocol.json'),
        pre_fit_contract=e.name(CONTRACT), pre_fit_contract_sha256=c.sha(CONTRACT),
        # Count the declared grid without parsing any completed endpoint values.
        archived_control_rows=len(cases)*len(CAPS)*len(BUDGETS)*(len(e.OLD_POLICIES)+2*len(f.POLICIES)),
        archived_control_policies=[*e.OLD_POLICIES, *f.POLICIES],
        expected_new_trajectories=len(cases)*len(CAPS)*len(SEEDS)*len(BUDGETS),
        expected_new_curve_points=len(cases)*len(CAPS)*len(SEEDS)*sum(BUDGETS),
        expected_new_endpoint_summaries=2*len(cases)*len(CAPS)*len(BUDGETS),
        endpoint_kinds=['B3-prefix', 'horizon-aware-terminal'],
        primary=dict(cap=64, planned_budget=3, endpoint='Best verified feasible whole-program cycle reduction and measured-pool regret',
            comparisons=['latency_cost_heuristic', f.MYOPIC, 'strongest_archived_control'],
            source_units='Old/expanded AHA/NDES/MD5 macros separately; DCT, Expint and bitcount separate.'),
        preparation='Seal every ARD joint/marginal/snapshot package and deterministic normal table before parsing native outcomes.',
        real_update='Original immutable JointHardwarePosterior conditioning; no estimator or hyperparameter refit inside search.',
        optimizer_selection='Historical marginal likelihood only, never target labels or selection utility.',
        replay_excluded_host_timer_keys=sorted(HOST_TIMERS), limitations=LIMITATIONS,
        tuning=False, new_native_jobs=0, model_promoted=False, calibration_established=False, superiority_established=False)


def _validate_controls(cases, archived):
    """Parse/check numeric controls only after all initial states are rebuilt."""
    identities = [r['case_id'] for r in cases]
    c.require([r['case_id'] for r in archived['original_fourteen']] == identities,
              'Exact ordered original fourteen-policy case inventory required')
    c.require(len(archived['fixed_joint_three']) == len(cases)*len(f.POLICIES)*len(CAPS)*len(BUDGETS)*2,
              'Complete three-policy/two-endpoint-kind control inventory required')
    for case, controls in zip(cases, archived['original_fourteen']):
        fourteen = controls['endpoints']
        expected = {(p, cap, budget) for p in e.OLD_POLICIES for cap in CAPS for budget in BUDGETS}
        c.require(len(fourteen) == len(expected) and
            {(r['policy'], r['cap'], r['budget']) for r in fourteen} == expected and
            fourteen == e._read_controls(case), 'Every original fourteen-policy numeric endpoint must remain EXACT')
        rows = [r for r in archived['fixed_joint_three'] if r['case_id'] == case['case_id']]
        expected_finite = {(p, cap, budget, planned, kind) for p in f.POLICIES for cap in CAPS
            for budget in BUDGETS for planned, kind in ((max(BUDGETS), 'B3-prefix'), (budget, 'horizon-aware-terminal'))}
        c.require(len(rows) == len(expected_finite) and
            {(r['policy'], r['cap'], r['budget'], r['planned_budget'], r['endpoint_kind']) for r in rows} == expected_finite,
            'All three finite controls and both independent endpoint kinds required')
        for row in rows:
            c.require(row['source'] == case['source'] and row['cohort'] == case['cohort'] and
                row['dependent_seed_count'] == len(SEEDS), 'Exact finite-control source/cohort/dependent-seed units required')
            c.require(0 <= b._number(row['mean_verified_cycle_reduction'], 'archived verified cycle reduction') < 1 and
                b._number(row['mean_cycle_reduction_regret'], 'archived cycle reduction regret') >= 0,
                'Finite nonnegative archived utility/regret required')


def _failure(root, phase, error):
    path = Path(root)/(phase+'-failure.json')
    if Path(root).exists() and not path.exists():
        value = dict(phase=phase, error=repr(error), traceback=traceback.format_exc(),
            preserve_partial_directory=True, retry_or_resume_allowed=False, new_native_jobs=0)
        if isinstance(error, a.ARDInitializationError):
            value.update(initialization_record=error.record, optimizer_attempts=error.attempts,
                         initialization_costs=error.costs)
        e.seal(path, value)


def _initialize(folder, case):
    history = c.unseal(folder/'history.json')
    public = c.unseal(folder/'public.json')
    result = a.initialize(history, public)
    posterior = result.posterior
    initial = posterior.snapshot()['initial_snapshot']
    c.require(initial['schema'] == a.SCHEMA and initial['settings'] == a.SETTINGS and
        initial['original_semantic_snapshot'] == c.unseal(folder/'cached-snapshot.json') and
        initial['training_ids'] == case['fitting_ids'] and initial['training_rows_sha256'] == c.digest(history) and
        list(posterior.candidate_ids) == case['public_ids'] and not posterior.observed_ids,
        'Exact historical cohort, unchanged semantic initialization and unpaid ARD state required')
    attempts = initial['optimizer_attempts']
    c.require(len(attempts) == 3 and result.costs['semantic_surrogate_fits'] == 1 and
        result.costs['semantic_scalar_gp_fits'] == 3 and result.costs['ard_scalar_gp_fit_attempts'] == 3 and
        result.costs['total_scalar_gp_fit_attempts'] == 6, 'One original semantic fit and all three ARD starts must be charged')
    costs = dict(case_id=case['case_id'], **copy.deepcopy(result.costs),
        optimizer_attempts=3, optimizer_objective_calls=sum(r['objective_calls'] for r in attempts),
        optimizer_gradient_calls=sum(r['gradient_calls'] for r in attempts),
        selected_start_index=initial['selected_start_index'],
        nonconverged_start_indices=copy.deepcopy(initial['nonconverged_start_indices']))
    return posterior, costs


def _release(root, cases):
    return dict(protocol_sha256=c.sha(root/'protocol.json'), case_ids=[r['case_id'] for r in cases],
        input_files=e.inventory(root/'inputs'), initial_files=e.inventory(root/'initial'),
        fantasy_files=e.inventory(_method_root(root)/'fantasies'), native_outcomes_parsed=False,
        semantic_surrogate_fits=len(cases), semantic_scalar_gp_fits=3*len(cases),
        ard_scalar_gp_fit_attempts=3*len(cases), total_scalar_gp_fit_attempts=6*len(cases))


def prepare(output):
    output = fresh(output)
    output.mkdir(parents=True)
    try:
        protocol = planned_protocol()
        e.seal(output/'protocol.json', protocol)
        costs = []
        for case in protocol['cases']:
            folder = output/'inputs'/case['case_id']
            for filename in e.INPUT_FILES:
                e._copy(BASE/'inputs'/case['case_id']/filename, folder/filename)
            posterior, record = _initialize(folder, case)
            initial = output/'initial'/case['case_id']
            for filename, value in [('joint.json', e._joint_json(posterior)),
                                    ('marginals.json', posterior.predict()), ('snapshot.json', posterior.snapshot())]:
                e.seal(initial/filename, value)
            e.seal(output/'prepare-cost-records'/(case['case_id']+'.json'), record)
            costs.append(record)
        for seed in SEEDS:
            draws, metadata = f.normal_draws(seed)
            e.seal(_method_root(output)/'fantasies'/f'seed{seed}.json', dict(normals=draws.tolist(), metadata=metadata))
        e.seal(output/'prediction-release.json', _release(output, protocol['cases']))
        e.seal(output/'prepare-runtime.json', dict(records=costs))
        e.seal(output/'prepared.json', dict(protocol_sha256=c.sha(output/'protocol.json'),
            prediction_release_sha256=c.sha(output/'prediction-release.json'),
            prepare_runtime_sha256=c.sha(output/'prepare-runtime.json'), new_native_jobs=0))
        e.seal_manifest(output)
        return protocol
    except BaseException as error:
        _failure(output, 'prepare', error)
        raise


def authenticate(root):
    root = Path(root).resolve()
    c.require(not (root/'prepare-failure.json').exists(), 'Failed ARD preparation cannot be resumed')
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol == planned_protocol(), 'Frozen ARD source/settings/cohort/control bindings changed')
    c.require(c.unseal(root/'prediction-release.json') == _release(root, protocol['cases']),
              'Complete all-case ARD prediction release required')
    c.require(c.unseal(root/'prepared.json') == dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'),
        prepare_runtime_sha256=c.sha(root/'prepare-runtime.json'), new_native_jobs=0), 'ARD preparation cost receipt changed')
    records = c.unseal(root/'prepare-runtime.json')['records']
    c.require([r['case_id'] for r in records] == [r['case_id'] for r in protocol['cases']], 'Every initial fit cost record required')
    for case, record in zip(protocol['cases'], records):
        for filename in e.INPUT_FILES:
            c.require(c.sha(root/'inputs'/case['case_id']/filename) == c.sha(BASE/'inputs'/case['case_id']/filename),
                      'Exact original cached inputs required')
        c.require(record == c.unseal(root/'prepare-cost-records'/(case['case_id']+'.json')),
                  'Raw per-case initialization costs changed')
        c.require(record['total_scalar_gp_fit_attempts'] == 6 and record['ard_scalar_gp_fit_attempts'] == 3,
                  'All initial scalar fit attempts must remain charged')
    for seed in SEEDS:
        draws, metadata = f.normal_draws(seed)
        c.require(c.unseal(_method_root(root)/'fantasies'/f'seed{seed}.json') == dict(normals=draws.tolist(), metadata=metadata),
                  'Exact fixed normal table required')
    return protocol


def _phase_totals(records):
    fields = ('semantic_surrogate_fits', 'semantic_scalar_gp_fits', 'unused_original_semantic_area_scalar_fits',
              'ard_scalar_gp_fit_attempts', 'ard_scalar_gp_fits_completed', 'total_scalar_gp_fit_attempts',
              'optimizer_attempts', 'optimizer_objective_calls', 'optimizer_gradient_calls',
              'semantic_fit_host_seconds', 'joint_construction_host_seconds', 'ard_fit_host_seconds', 'initialize_host_seconds')
    return {field: sum(record[field] for record in records) for field in fields}


def _comparisons(rows, controls):
    fourteen = {record['case_id']: record['endpoints'] for record in controls['original_fourteen']}
    result = []
    order = [*e.OLD_POLICIES, *f.POLICIES]
    for row in rows:
        historical = [r for r in fourteen[row['case_id']] if (r['cap'], r['budget']) == (row['cap'], row['budget'])]
        finite = [r for r in controls['fixed_joint_three'] if all(r[field] == row[field]
            for field in ('case_id', 'cap', 'budget', 'planned_budget', 'endpoint_kind'))]
        c.require(len(historical) == 14 and len(finite) == 3, 'Same-information seventeen-control endpoint set required')
        strongest = max([*historical, *finite], key=lambda r: (r['mean_verified_cycle_reduction'], -order.index(r['policy'])))
        choices = [('latency_cost_heuristic', next(r for r in historical if r['policy'] == 'latency_cost_heuristic')),
                   (f.MYOPIC, next(r for r in finite if r['policy'] == f.MYOPIC)),
                   ('strongest_archived_control', strongest)]
        for comparator, original in choices:
            delta = row['mean_verified_cycle_reduction']-original['mean_verified_cycle_reduction']
            result.append({key: row[key] for key in ('case_id', 'source', 'cohort', 'policy', 'cap', 'budget', 'planned_budget', 'endpoint_kind')} |
                dict(comparator=comparator, comparator_policy=original['policy'],
                    comparator_planned_budget=original.get('planned_budget', 3),
                    policy_cycle_reduction=row['mean_verified_cycle_reduction'],
                    comparator_cycle_reduction=original['mean_verified_cycle_reduction'],
                    difference_cycle_reduction=delta, result='tie' if abs(delta) <= 1e-14 else ('win' if delta > 0 else 'loss'),
                    retrospective_control_envelope=comparator == 'strongest_archived_control', significance_established=False))
    return result


def _readme(root, report):
    lines = ['# One train-only ARD area surrogate development experiment', '',
        'Known-benefit myopic acquisition and paid Gaussian conditioning are unchanged. The single new model identity is `'+POLICY+'`. '
        'All seventeen original controls are retained exactly. No fresh-source, calibrated-confidence or superiority claim.', '',
        '| Case | ARD cycle reduction % | Original myopic % | Difference pp |', '| --- | ---: | ---: | ---: |']
    for row in report['comparisons']:
        if row['cap'] == 64 and row['budget'] == 3 and row['endpoint_kind'] == 'B3-prefix' and row['comparator'] == f.MYOPIC:
            lines.append(f"| {row['case_id']} | {100*row['policy_cycle_reduction']:.9f} | "
                         f"{100*row['comparator_cycle_reduction']:.9f} | {100*row['difference_cycle_reduction']:.9f} |")
    lines.extend(['', 'B3 prefixes and separately executed B1/B2/B3 terminals have separate endpoint kinds. '
        'Old/expanded three-source macros are separate; DCT cohort cases, Expint and bitcount remain separate.', '',
        f"{report['new_trajectories']} trajectories / {report['new_curve_points']} curve points / "
        f"{len(report['endpoints'])} new summaries; {report['archived_control_summary_rows']} unchanged control summaries.", '',
        'All three optimizer starts, statuses, convergence warnings, bound hits and training likelihoods are preserved in initial snapshots. '
        'Unused original semantic-area fits remain charged. Preparation fits and run reconstruction fits are separate; acquisition, '
        'conditioning, validation and initialization timers overlap their stated envelopes and are not summed twice.', '',
        *['- '+line for line in LIMITATIONS], '',
        'Replay: `python scripts/evaluate_ard_selection.py replay --root '+e.name(root)+' --output generated/ard-selection-replay`.', ''])
    (root/'README.md').write_text('\n'.join(lines))


def run(root):
    root = Path(root).resolve()
    c.require(not any((root/p).exists() for p in ('started.json', 'report.json', 'run-failure.json')),
              'Fresh prepared ARD run required; no overwrite/retry/resume')
    try:
        protocol = authenticate(root)
        e.manifest(root)
        e.seal(root/'started.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
            prediction_release_sha256=c.sha(root/'prediction-release.json'), new_native_jobs=0))
        began_run = time.monotonic()
        models, rebuilt = {}, []
        for case in protocol['cases']:
            posterior, costs = _initialize(root/'inputs'/case['case_id'], case)
            initial = root/'initial'/case['case_id']
            c.require(e._joint_json(posterior) == c.unseal(initial/'joint.json') and
                posterior.predict() == c.unseal(initial/'marginals.json') and posterior.snapshot() == c.unseal(initial/'snapshot.json'),
                'Exact ARD joint state, optimizer choice and marginal reconstruction required')
            models[case['case_id']] = posterior
            e.seal(root/'run-initialization-cost-records'/(case['case_id']+'.json'), costs)
            rebuilt.append(costs)
        # No native outcome is parsed until EVERY prepared ARD state is rebuilt.
        controls = _controls()
        _validate_controls(protocol['cases'], controls)
        case_data = {}
        for case, archive in zip(protocol['cases'], controls['original_fourteen']):
            identity = case['case_id']
            public = c.unseal(root/'inputs'/identity/'public.json')
            history = c.unseal(root/'inputs'/identity/'history.json')
            labels, outer, censored, audit_digest = e._read_outcomes(case, public)
            outcomes_digest = c.digest(list(labels.values()))
            e._control_outcome_bindings(case, audit_digest, outcomes_digest)
            c.require(archive['native_audit_digest'] == audit_digest and archive['outcomes_sha256'] == outcomes_digest,
                      'Original control archive must bind identical native outcomes')
            for row in controls['fixed_joint_three']:
                if row['case_id'] == identity:
                    reference = max([1.]+[r['speedup'] for r in labels.values() if b._feasible(r, row['cap'], 12.)])
                    c.require(row['reference_speedup'] == reference and row['reference_cycle_reduction'] == 1-1/reference and
                        row['reference_complete'] == (not censored) and row['regret_is_lower_bound'] == censored,
                        'Finite controls must retain identical measured-pool reference and censorship')
            case_data[identity] = public, history, labels, outer, censored
        points, indices, unique_labels = [], [], {}
        totals = dict(new_trajectories=0, new_curve_points=0, conditional_updates=0,
            observer_validation_conditional_updates=0, calibrated_benefit_assumption_violations=0)
        host = dict(acquisition_host_seconds=0., conditioning_host_seconds=0., observer_validation_conditioning_host_seconds=0.)
        counterfactual = dict(charged_replayed_attempts=0, target_measurement_seconds=0., target_outer_operation_seconds=0.)
        for case in protocol['cases']:
            identity = case['case_id']
            public, history, labels, outer, censored = case_data[identity]
            for candidate_id, outcome in labels.items():
                c.require(candidate_id not in unique_labels or unique_labels[candidate_id] == outcome,
                          'Repeated contexts must retain identical native outcomes/costs')
                unique_labels[candidate_id] = outcome
            for budget in BUDGETS:
                for cap in CAPS:
                    for seed in SEEDS:
                        searched, relative = e._run_one(_method_root(root), case, models[identity], public, history,
                            labels, outer, censored, policy=f.MYOPIC, cap=cap, seed=seed, budget=budget)
                        path = (_method_root(root)/relative).relative_to(root).as_posix()
                        indices.append(dict(case_id=identity, policy=POLICY, acquisition_policy=f.MYOPIC,
                            cap=cap, seed=seed, planned_budget=budget, path=path, scientific_run_sha256=c.digest(stable(searched))))
                        totals['new_trajectories'] += 1
                        totals['new_curve_points'] += len(searched['curve'])
                        for key in ('conditional_updates', 'observer_validation_conditional_updates', 'calibrated_benefit_assumption_violations'):
                            totals[key] += searched[key]
                        for key in host:
                            host[key] += searched[key]
                        counterfactual['charged_replayed_attempts'] += budget
                        for key in ('target_measurement_seconds', 'target_outer_operation_seconds'):
                            counterfactual[key] += searched['curve'][-1][key]
                        for point in searched['curve']:
                            metadata = dict(case_id=identity, source=case['source'], cohort=case['cohort'], policy=POLICY, cap=cap, seed=seed)
                            if budget == max(BUDGETS):
                                points.append(dict(**metadata, **copy.deepcopy(point), endpoint_kind='B3-prefix'))
                            if point['budget'] == budget:
                                points.append(dict(**metadata, **copy.deepcopy(point), endpoint_kind='horizon-aware-terminal'))
        expected = len(protocol['cases'])*len(CAPS)*len(SEEDS)*len(BUDGETS)
        c.require(totals['new_trajectories'] == expected and totals['new_curve_points'] == expected//len(BUDGETS)*sum(BUDGETS),
                  'Complete single-model independent horizon grid required')
        summaries = e._summaries(points)
        c.require(len(summaries) == protocol['expected_new_endpoint_summaries'],
                  'Both complete primary-prefix and independently planned terminal summary grids required')
        prepared = c.unseal(root/'prepare-runtime.json')['records']
        costs = dict(prepare_records=prepared, run_initialization_records=rebuilt,
            prepare_totals=_phase_totals(prepared), run_initialization_totals=_phase_totals(rebuilt),
            estimator_fits_inside_search=0, **host, counterfactual_target_search=counterfactual,
            reused_target_pool=dict(unique_attempts=len(unique_labels),
                recorded_candidate_ledger_seconds=sum(r['measurement_seconds'] for r in unique_labels.values()),
                scope='Already collected target pools; overlaps frozen historical corpus and counterfactual trajectories.'),
            run_envelope_host_seconds=time.monotonic()-began_run,
            scope='Prepare and run initialization scopes separate. Acquisition/conditioning/validation are inside run envelope; do not sum them again. Envelope starts after authentication and ends before report writing. Initialization includes the otherwise unused original semantic-area fit.')
        report = dict(schema=SCHEMA+'-report', scope='consumed-data development', model_identity=POLICY,
            acquisition_policy=f.MYOPIC, protocol_sha256=c.sha(root/'protocol.json'),
            prediction_release_sha256=c.sha(root/'prediction-release.json'), original_finite_manifest_sha256=protocol['original_finite_manifest_sha256'],
            case_count=len(protocol['cases']), distinct_consumed_target_sources=len({r['source'] for r in protocol['cases']}),
            **totals, archived_control_summary_rows=protocol['archived_control_rows'], runs=indices,
            endpoints=summaries, comparisons=_comparisons(summaries, controls), primary_source_macros=e._macros(summaries),
            costs=costs, historical_accounting=protocol['historical_accounting'],
            original_setup_cost_provenance=[dict(case_id=r['case_id'], provenance=r['original_cost_provenance']) for r in protocol['cases']],
            new_native_jobs=0, tuning=False, model_promoted=False, calibration_established=False, superiority_established=False, limitations=LIMITATIONS)
        e.seal(root/'archived-controls.json', controls)
        e.seal(root/'seed-endpoints.json', points)
        e.seal(root/'runtime-costs.json', costs)
        e.seal(root/'report.json', report)
        for filename, rows in [('endpoints.csv', summaries), ('comparisons.csv', report['comparisons']),
                               ('source-macros.csv', report['primary_source_macros'])]:
            e._csv(root/filename, rows)
        _readme(root, report)
        e.seal_manifest(root)
        return report
    except BaseException as error:
        _failure(root, 'run', error)
        raise


def replay(reference, output):
    reference = Path(reference).resolve()
    output = fresh(output, (reference,))
    e.manifest(reference)
    authenticate(reference)
    original = c.unseal(reference/'report.json')
    prepare(output)
    try:
        c.require(c.unseal(reference/'prediction-release.json') == c.unseal(output/'prediction-release.json'),
                  'Exact ARD state/optimizer/fantasy/input release differs')
        result = run(output)
        c.require(c.unseal(reference/'archived-controls.json') == c.unseal(output/'archived-controls.json'), 'All seventeen numeric controls must remain exact')
        c.require(stable(original) == stable(result), 'ARD scientific states/decisions/fit accounting/paid costs differ')
        c.require(e.inventory(_method_root(reference)/'acquisitions') == e.inventory(_method_root(output)/'acquisitions'),
                  'Exact pre-provider ARD model/paid-prefix proofs differ')
        c.require(stable(c.unseal(reference/'seed-endpoints.json')) == stable(c.unseal(output/'seed-endpoints.json')),
                  'Independent planned terminal and primary prefix endpoints differ')
        for entry in original['runs']:
            c.require(stable(c.unseal(reference/entry['path'])) == stable(c.unseal(output/entry['path'])), 'Exact raw myopic method trajectory must reproduce')
        e.seal(output/'replay-verification.json', dict(reference_manifest_sha256=c.sha(reference/'manifest.json'),
            compared_trajectories=result['new_trajectories'], compared_curve_points=result['new_curve_points'],
            all_seventeen_controls_exact=True, excluded_host_timer_keys=sorted(HOST_TIMERS),
            raw_reference_runtime=c.unseal(reference/'runtime-costs.json'), raw_replayed_runtime=c.unseal(output/'runtime-costs.json'), new_native_jobs=0))
        e.seal_manifest(output)
        return result
    except BaseException as error:
        _failure(output, 'replay', error)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'replay'))
    parser.add_argument('--root', type=Path, default=OUTPUT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        value = prepare(args.output or args.root)
        print(dict(cases=len(value['cases']), model_identity=POLICY, new_native_jobs=0))
    elif args.command == 'run':
        value = run(args.root)
        print({key: value[key] for key in ('new_trajectories', 'new_curve_points', 'archived_control_summary_rows', 'new_native_jobs')})
    else:
        c.require(args.output is not None, 'Fresh --output required for ARD replay')
        value = replay(args.root, args.output)
        print(dict(verified_trajectories=value['new_trajectories'], new_native_jobs=0))


if __name__ == '__main__':
    main()
