"""One sealed, consumed-data finite-pool acquisition experiment; no native jobs.

prepare binds ten exact cached cohorts and seals every initial joint state before
run parses native outcomes. run separately executes planned budgets 1/2/3; replay
checks scientific states/decisions/costs exactly, retaining raw host timers.
"""
from __future__ import annotations

import argparse
import copy
import csv
import importlib.metadata
from pathlib import Path
import shutil
import statistics
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge import finite_selection as f, joint_hardware as j, semantic_selection as s
from isaforge.speedup_corpus import family

SCHEMA = 'isaforge-fixed-joint-finite-selection-development-v1'
SEMANTIC = ROOT/'results/2026-10-22-semantic-selection-development'
COUNT = ROOT/'results/2026-10-22-count-acquisition-development'
BITCOUNT = ROOT/'results/2026-10-22-bitcount-campaign'
BITPREREG = ROOT/'results/2026-10-22-bitcount-preregistration'
CORPUS = ROOT/'results/2026-10-22-twelve-source-corpus/corpus.json'
OUTPUT = ROOT/'results/2026-10-25-finite-selection-development'
CAPS, SEEDS, BUDGETS = (32, 64, 128), tuple(range(5)), (1, 2, 3)
OLD_POLICIES = (*b.POLICIES, 'feasible_benefit_xgb', 'factorized_feasibility_xgb',
                'hybrid_gp_adapt_count', 'hybrid_gp_adapt_count_semantic')
PRIMARY_SOURCES = ('beebs-aha-compress', 'beebs-ndes', 'beebs-nettle-md5')
SOURCES = tuple(dict.fromkeys(('scripts/evaluate_finite_selection.py', *f.SOURCES)))
HOST_TIMERS = {
    'host_monotonic_start_ns', 'host_monotonic_end_ns', 'host_monotonic_seconds',
    'prepare_model_host_seconds', 'run_initial_rebuild_host_seconds',
    'run_envelope_host_seconds', 'acquisition_host_seconds', 'conditioning_host_seconds',
    'observer_validation_conditioning_host_seconds', 'inference_seconds', 'mean_inference_seconds',
}
LIMITATIONS = [
    'All existing sources and every scored case are consumed development data; no superiority, calibration or promotion claim.',
    'Ten cohort/source cases are six sources; old/expanded replicas, caps, budgets and five seeds are dependent.',
    'Cached history already contains other consumed target sources. Only new paid observations are isolated across cases.',
    'Known calibrated benefit, independent area/timing outputs, assumed Gaussian observation noise and a common Beta device-fit model are assumptions.',
    'Fixed initial preprocessing/noisy conditioning and cycle-reduction utility are declared changes from the frozen semantic policy.',
    'Correctness and infrastructure failure probabilities are unmodeled; actual failures are charged without fabricated hardware labels.',
    'Three-query two-step receding horizon is an approximation; all final choices must be measured and feasible.',
    'Gardner known-benefit constrained EI and finite-pool 2-OPT-C are adaptations, not faithful full-paper reproductions or new algorithms.',
    'Cooperative local providers are not an operating-system sandbox. No native tools are launched.',
    'Counterfactual trajectories reuse overlapping historical measurements. Earlier oracle hits do not establish stopping or total-time savings.',
]


def resolve(name):
    path = Path(name)
    return path if path.is_absolute() else ROOT/path


def name(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def source_bindings():
    return {relative: c.sha(ROOT/relative) for relative in SOURCES}


def input_roots():
    return (SEMANTIC, COUNT, BITCOUNT, BITPREREG, CORPUS.parent)


def inventory(root):
    root = Path(root)
    return {path.relative_to(root).as_posix(): c.sha(path)
            for path in sorted(root.rglob('*')) if path.is_file()}


def manifest(root):
    root = Path(root)
    expected = c.unseal(root/'manifest.json')
    actual = {key: value for key, value in inventory(root).items()
              if key not in ('manifest.json', 'manifest.json.sha256')}
    c.require(expected == actual, 'Exact sealed input/output manifest required: '+str(root))


def seal(path, value):
    path = Path(path)
    c.require(not path.exists() and not Path(str(path)+'.sha256').exists(),
              'Never overwrite a sealed experiment artifact: '+str(path))
    c.seal(path, value)


def seal_manifest(root):
    root = Path(root)
    values = {key: value for key, value in inventory(root).items()
              if key not in ('manifest.json', 'manifest.json.sha256')}
    # Completion and replay add receipts. Only this derived inventory is refreshed.
    c.seal(root/'manifest.json', values)


def stable(value):
    if isinstance(value, (list, tuple)):
        return [stable(item) for item in value]
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in HOST_TIMERS}
    return value


def fresh(output, extra=()):
    output = Path(output).resolve()
    protected = [Path(p).resolve() for p in (*input_roots(), *extra)]
    c.require(not output.exists() and not any(output.is_relative_to(p) or p.is_relative_to(output)
              for p in protected), 'Fresh output outside sealed evidence/input roots required')
    c.require(not any((p/'manifest.json').exists() and (p/'manifest.json.sha256').exists()
                     for p in output.parents), 'Cannot write inside sealed evidence')
    return output


def specs():
    """Read cached metadata/public/history; target audit bytes are only hashed."""
    previous = c.unseal(SEMANTIC/'protocol.json')
    c.require(len(previous['cases']) == 9, 'Exact nine semantic development cases required')
    result = []
    expected = (44, 33, 29, 38, 68, 55, 50, 71, 67)
    for case, rows in zip(previous['cases'], expected):
        identity = case['case_id']
        result.append(dict(case_id=identity, source=case['source'], cohort=case['cohort'],
            expected_rows=rows, public=name(SEMANTIC/'inputs'/identity/'public.json'),
            history=name(SEMANTIC/'inputs'/identity/'history.json'),
            cached_predictions=name(SEMANTIC/'initial'/identity/'predictions.json'),
            cached_snapshot=name(SEMANTIC/'initial'/identity/'snapshot.json'),
            model_protocol=name(SEMANTIC/'inputs'/identity/'model-protocol.json'),
            control_report=name(SEMANTIC/'report.json'), control_kind='semantic',
            audit=case['audit'], outer=case['outer'],
            additional_bindings=[name(resolve(case['package'])/'report.json'),
                name(COUNT/'new-policy'/identity/'report.json'),
                name(SEMANTIC/'new-policy'/identity/'report.json')],
            original_cost_provenance=case['original_cost_provenance']))
    target = BITPREREG/'targets/tacle-bitcount'
    original = c.unseal(target/'selection/protocol.json')
    result.append(dict(case_id='cached__tacle-bitcount', source='tacle-bitcount', cohort='cached',
        expected_rows=67, public=name(target/'selection/controls11/model/public.json'),
        history=name(target/'selection/controls11/model/history.json'),
        cached_predictions=name(target/'semantic/predictions.json'),
        cached_snapshot=name(target/'semantic/snapshot.json'), model_protocol=name(target/'selection/protocol.json'),
        control_report=name(BITCOUNT/'report.json'), control_kind='bitcount',
        audit=name(BITCOUNT/'audit.json'), outer=name(BITCOUNT/'outer-times.json'),
        additional_bindings=[name(BITCOUNT/'endpoints.json'), name(BITPREREG/'cohort.json')],
        original_cost_provenance=original['cost_provenance']))
    c.require(len(result) == 10 and len({r['source'] for r in result}) == 6,
              'Ten cached cases and six consumed sources required')
    return result


def historical_accounting():
    # Bind the corpus without reading its target outcomes during preparation.
    return dict(successful_labels=99, failed_attempts=3, charged_attempts=102,
        recorded_candidate_ledger_seconds=6019.913663583149, source_corpus=name(CORPUS),
        source_corpus_sha256=c.sha(CORPUS), actual_calendar_wall_seconds=None,
        scope='All collected attempts counted once globally, including excluded fitting rows; overlapping policy/case costs are not added.')


def planned_protocol():
    for root in input_roots():
        manifest(root)
    cases, bindings = [], {}
    for spec in specs():
        public = b.public_rows(c.unseal(resolve(spec['public'])))
        history = c.unseal(resolve(spec['history']))
        original = c.unseal(resolve(spec['model_protocol']))
        snapshot = c.unseal(resolve(spec['cached_snapshot']))
        ids = [row['candidate_id'] for row in history]
        families = {family(row['formula']) for row in public}
        c.require(len(history) == spec['expected_rows'] and len(set(ids)) == len(ids) and
            ids == original['historical_training_ids'] == snapshot['training_ids'] and
            snapshot['training_rows_sha256'] == c.digest(history), 'Exact cached fitting cohort required')
        c.require(all(b.validate_outcome(row) and row['workload_group'] != spec['source'] and
            family(row['formula']) not in families for row in history) and
            len({row['workload_group'] for row in history}) >= 2 and
            not set(ids) & {row['candidate_id'] for row in public}, 'Whole-source/family exclusions and two historical groups required')
        paths = [spec[key] for key in ('public', 'history', 'cached_predictions', 'cached_snapshot',
                                      'model_protocol', 'control_report', 'audit', 'outer')]
        for path in [*paths, *spec['additional_bindings']]:
            bindings[path] = c.sha(resolve(path))
            sidecar = Path(str(resolve(path))+'.sha256')
            c.require(sidecar.read_text().strip() == bindings[path], 'Input checksum differs')
            bindings[name(sidecar)] = c.sha(sidecar)
        cases.append(dict(**copy.deepcopy(spec), public_ids=[r['candidate_id'] for r in public],
            public_rows_sha256=c.digest(public), fitting_ids=ids, fitting_rows=len(history),
            fitting_groups=sorted({r['workload_group'] for r in history}),
            fitting_recorded_seconds=sum(r['measurement_seconds'] for r in history),
            excluded_related_ids=original.get('excluded_related_ids', []),
            exclusion='Entire target workload/source plus every target formula family; exact original cached rows retained.'))
    history = historical_accounting()
    bindings[history['source_corpus']] = history['source_corpus_sha256']
    for root in input_roots():
        bindings[name(root/'manifest.json')] = c.sha(root/'manifest.json')
    return dict(schema=SCHEMA, scope='consumed-data development', cases=cases,
        old_policies=list(OLD_POLICIES), new_policies=list(f.POLICIES),
        area_caps=list(CAPS), seeds=list(SEEDS), planned_budgets=list(BUDGETS), clock_mhz=12.,
        settings=copy.deepcopy(f.SETTINGS), gp_settings=copy.deepcopy(b.GP_SETTINGS),
        semantic_columns=list(s.COLUMNS), joint_update=j.UPDATE_RULE, noise_assumption=j.NOISE_ASSUMPTION,
        source_bindings=source_bindings(), input_bindings=bindings,
        packages={key: importlib.metadata.version(key) for key in ('numpy', 'scipy', 'scikit-learn', 'xgboost')},
        historical_accounting=history,
        primary=dict(planned_budget=3, cap=64, endpoint='Best verified feasible cycle reduction and measured-pool regret',
            source_macros='Old/expanded AHA/NDES/MD5 separately; DCT/Expint/bitcount remain separate',
            prespecified_heuristic='latency_cost_heuristic', planning_comparator=f.MYOPIC),
        endpoint_kinds=['B3-prefix', 'horizon-aware-terminal'],
        preparation='Seal every cached-input/initial-joint/marginal/snapshot package and all-case release before parsing any native outcome; input authentication hashes raw audit bytes without deserializing labels.',
        real_updates='Same case successful paid prefix only; no new target releases cross cases; no estimator fit inside search.',
        replay_excluded_host_timer_keys=sorted(HOST_TIMERS), limitations=LIMITATIONS,
        tuning=False, native_jobs=0, calibration_established=False, superiority_established=False)


def _failure(root, phase, error):
    path = Path(root)/(phase+'-failure.json')
    if Path(root).exists() and not path.exists():
        seal(path, dict(phase=phase, error=repr(error), traceback=traceback.format_exc(),
                       preserve_partial_directory=True, retry_or_resume_allowed=False, new_native_jobs=0))


def _copy(source, destination):
    source, destination = Path(source), Path(destination)
    c.unseal(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    c.require(not destination.exists(), 'Fresh copied-input destination required')
    for suffix in ('', '.sha256'):
        shutil.copyfile(str(source)+suffix, str(destination)+suffix)


INPUT_FILES = ('public.json', 'history.json', 'cached-predictions.json', 'cached-snapshot.json')


def _joint_json(posterior):
    joint = posterior.joint()
    return dict(candidate_ids=joint['candidate_ids'], device_fit_probability=joint['device_fit_probability'],
        device_fit_alpha=joint['device_fit_alpha'], device_fit_beta=joint['device_fit_beta'],
        outputs={key: {field: value.tolist() if isinstance(value, np.ndarray) else value
                      for field, value in output.items()} for key, output in joint['outputs'].items()})


def _build_case(folder):
    history = c.unseal(folder/'history.json')
    public = b.public_rows(c.unseal(folder/'public.json'))
    model = s.SemanticHardwareSurrogate().fit(history)
    c.require(model.snapshot() == c.unseal(folder/'cached-snapshot.json'),
              'Initial semantic model must reproduce archived snapshot EXACTLY')
    c.require(model.predict(public) == c.unseal(folder/'cached-predictions.json'),
              'Initial semantic model predictions must reproduce archive EXACTLY')
    posterior = j.JointHardwarePosterior.from_fitted(model, history, public)
    for actual, expected in zip(posterior.predict(), c.unseal(folder/'cached-predictions.json')):
        c.require(actual['candidate_id'] == expected['candidate_id'] and set(actual) == set(expected),
                  'Complete ordered marginal fields required')
        for key in actual:
            if key != 'candidate_id':
                c.require(abs(actual[key]-expected[key]) <= 1e-10,
                          'New joint reconstruction differs from archived marginal')
    return posterior


def prepare(output):
    output = fresh(output)
    output.mkdir(parents=True)
    try:
        protocol = planned_protocol()
        seal(output/'protocol.json', protocol)
        records = []
        for case in protocol['cases']:
            folder = output/'inputs'/case['case_id']
            for key, filename in zip(('public', 'history', 'cached_predictions', 'cached_snapshot'), INPUT_FILES):
                _copy(resolve(case[key]), folder/filename)
            began = time.monotonic_ns()
            posterior = _build_case(folder)
            ended = time.monotonic_ns()
            initial = output/'initial'/case['case_id']
            for filename, value in [('joint.json', _joint_json(posterior)),
                                    ('marginals.json', posterior.predict()), ('snapshot.json', posterior.snapshot())]:
                seal(initial/filename, value)
            records.append(dict(case_id=case['case_id'], surrogate_fits=1, scalar_gp_fits=3,
                host_monotonic_start_ns=began, host_monotonic_end_ns=ended, host_monotonic_seconds=(ended-began)/1e9))
        for seed in SEEDS:
            draws, metadata = f.normal_draws(seed)
            seal(output/'fantasies'/f'seed{seed}.json', dict(normals=draws.tolist(), metadata=metadata))
        release = dict(protocol_sha256=c.sha(output/'protocol.json'), case_ids=[r['case_id'] for r in protocol['cases']],
            input_files=inventory(output/'inputs'), initial_files=inventory(output/'initial'),
            fantasy_files=inventory(output/'fantasies'), native_outcomes_parsed=False,
            initial_surrogate_fits=len(records), initial_scalar_gp_fits=3*len(records))
        seal(output/'prediction-release.json', release)
        seal(output/'prepare-runtime.json', dict(records=records,
            prepare_model_host_seconds=sum(r['host_monotonic_seconds'] for r in records)))
        seal(output/'prepared.json', dict(protocol_sha256=c.sha(output/'protocol.json'),
            prediction_release_sha256=c.sha(output/'prediction-release.json'),
            prepare_runtime_sha256=c.sha(output/'prepare-runtime.json'), new_native_jobs=0))
        seal_manifest(output)
        return protocol
    except BaseException as error:
        _failure(output, 'prepare', error)
        raise


def authenticate(root):
    root = Path(root).resolve()
    c.require(not (root/'prepare-failure.json').exists(), 'Failed preparation cannot be resumed')
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol == planned_protocol(), 'Frozen sources, settings, inputs or cached cohorts changed')
    release = c.unseal(root/'prediction-release.json')
    c.require(release == dict(protocol_sha256=c.sha(root/'protocol.json'),
        case_ids=[r['case_id'] for r in protocol['cases']], input_files=inventory(root/'inputs'),
        initial_files=inventory(root/'initial'), fantasy_files=inventory(root/'fantasies'),
        native_outcomes_parsed=False, initial_surrogate_fits=len(protocol['cases']),
        initial_scalar_gp_fits=3*len(protocol['cases'])), 'Complete all-case prediction release required')
    c.require(c.unseal(root/'prepared.json') == dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'),
        prepare_runtime_sha256=c.sha(root/'prepare-runtime.json'), new_native_jobs=0), 'Preparation receipt changed')
    timing = c.unseal(root/'prepare-runtime.json')
    c.require([r['case_id'] for r in timing['records']] == release['case_ids'], 'Every initial fit timing required')
    for case, record in zip(protocol['cases'], timing['records']):
        for key, filename in zip(('public', 'history', 'cached_predictions', 'cached_snapshot'), INPUT_FILES):
            c.require(c.sha(root/'inputs'/case['case_id']/filename) == protocol['input_bindings'][case[key]],
                      'Exact cached input bytes required')
        c.require(record['surrogate_fits'] == 1 and record['scalar_gp_fits'] == 3 and
            record['host_monotonic_end_ns'] >= record['host_monotonic_start_ns'] and
            record['host_monotonic_seconds'] == (record['host_monotonic_end_ns']-record['host_monotonic_start_ns'])/1e9,
            'Exact same-clock initial fit duration required')
    c.require(timing['prepare_model_host_seconds'] == sum(r['host_monotonic_seconds'] for r in timing['records']),
              'Initial model work must be counted exactly once')
    for seed in SEEDS:
        draws, metadata = f.normal_draws(seed)
        c.require(c.unseal(root/'fantasies'/f'seed{seed}.json') == dict(normals=draws.tolist(), metadata=metadata),
                  'Fixed deterministic fantasy table changed')
    return protocol


def _read_controls(case):
    original = c.unseal(resolve(case['control_report']))
    c.require(original['policies'] == list(OLD_POLICIES), 'All fourteen unchanged archived controls required')
    controls = ([row for row in original['endpoints'] if row['case_id'] == case['case_id']]
                if case['control_kind'] == 'semantic' else original['endpoints'])
    expected = {(policy, cap, budget) for policy in OLD_POLICIES for cap in CAPS for budget in BUDGETS}
    c.require(len(controls) == len(expected) and
        {(r['policy'], r['cap'], r['budget']) for r in controls} == expected,
        'Complete exact fourteen-policy control endpoint grid required')
    return copy.deepcopy(controls)


def _control_outcome_bindings(case, audit_digest, outcomes_digest):
    if case['control_kind'] == 'bitcount':
        original = c.unseal(resolve(case['control_report']))
        c.require(original['native_audit_digest'] == audit_digest and original['outcomes_sha256'] == outcomes_digest,
                  'Archived fourteen-control report/native audit binding differs')
        return
    c.require(len(case['additional_bindings']) == 3, 'Original twelve/count/semantic raw report bindings required')
    original, count, semantic = [c.unseal(resolve(path)) for path in case['additional_bindings']]
    c.require(original['native_audit_digest'] == audit_digest and
        original['protocol_sha256'] == c.sha(resolve(case['model_protocol'])) and
        all(report['outcomes_sha256'] == outcomes_digest for report in (original, count, semantic)),
        'Archived twelve/count/semantic controls must bind identical native target outcomes')


def _read_outcomes(case, public):
    audit, outer = c.unseal(resolve(case['audit'])), c.unseal(resolve(case['outer']))
    labels = {row['candidate_id']: row for row in audit['outcomes']}
    c.require(len(labels) == len(audit['outcomes']) == len(public) and
        set(labels) == {row['candidate_id'] for row in public} == set(outer), 'Complete unique attempted public pool required')
    censored = False
    for row in public:
        outcome = labels[row['candidate_id']]
        success = b.validate_outcome(outcome, row)
        duration = b._number(outer[row['candidate_id']], 'outer-operation seconds', positive=True)
        c.require(duration >= outcome['measurement_seconds'], 'Outer duration shorter than charged ledger')
        if not success:
            c.require(type(outcome.get('reference_censored')) is bool and outcome.get('failure_class'),
                      'Failed attempt requires explicit known/unknown classification')
            censored |= outcome['reference_censored']
    return labels, outer, censored, c.digest(audit)


def _annotate(run, labels, outer, cap, censored):
    reference = max([1.]+[r['speedup'] for r in labels.values() if b._feasible(r, cap, 12.)])
    reference_gain = 1-1/reference
    for point in run['curve']:
        rows = [labels[identity] for identity in point['attempted_ids']]
        best = max([1.]+[row['speedup'] for row in rows if b._feasible(row, cap, 12.)])
        c.require(point['best_speedup'] == best and len(rows) == len(set(point['attempted_ids'])) == point['budget'] and
            point['target_measurement_seconds'] == sum(r['measurement_seconds'] for r in rows), 'Exact uniquely charged endpoint required')
        point.update(verified_cycle_reduction=1-1/best, reference_speedup=reference,
            reference_cycle_reduction=reference_gain, cycle_reduction_regret=reference_gain-(1-1/best),
            target_outer_operation_seconds=sum(outer[identity] for identity in point['attempted_ids']),
            known_infeasible_attempts=sum((r.get('status', 'success') == 'success' and not b._feasible(r, cap, 12.)) or
                (r.get('status') == 'failed' and not r['reference_censored']) for r in rows),
            unknown_attempts=sum(r.get('status') == 'failed' and r['reference_censored'] for r in rows),
            reference_complete=not censored, regret_is_lower_bound=censored)


def _run_one(root, case, posterior, public, history, labels, outer, censored, *, policy, cap, seed, budget):
    relative = Path(f'B{budget}')/policy/case['case_id']/f'cap{cap}-seed{seed}'
    destination = root/'acquisitions'/relative
    released, successful = [], []
    expected_state = posterior.clone()
    validation_seconds = 0.
    validation_updates = 0
    def acquire(proof):
        event, snapshot = proof['event'], proof['posterior_snapshot']
        c.require(event['planned_budget'] == budget and event['remaining_queries'] == budget-len(released) and
            event['charged_before_query'] == len(released) and event['attempted_ids_before_query'] == released and
            event['paid_target_ids_before_query'] == [r['candidate_id'] for r in successful] and
            proof['successful_paid_ids'] == [r['candidate_id'] for r in successful] and
            snapshot['paid_outcomes_sha256'] == c.digest(successful) and
            proof['initial_training_ids'] == case['fitting_ids'], 'Only this case actual successful paid prefix may reach acquisition')
        c.require(snapshot == expected_state.snapshot() and proof['snapshot_sha256'] == c.digest(snapshot) and
            event['posterior_state_sha256'] == snapshot['posterior_state_sha256'], 'Exact actual-prefix posterior state proof required')
        c.require(proof['fantasy_table'] == c.unseal(root/'fantasies'/f'seed{seed}.json')['metadata'],
                  'Acquisition must use sealed fantasy table')
        seal(destination/f'{len(released):02d}.json', dict(case_id=case['case_id'], cap=cap, seed=seed,
             planned_budget=budget, proof=proof))
    def provider(candidate):
        nonlocal expected_state, validation_seconds, validation_updates
        proof = c.unseal(destination/f'{len(released):02d}.json')['proof']
        identity = candidate['candidate_id']
        c.require(proof['event']['candidate_id'] == identity and identity not in released and
            candidate == next(row for row in public if row['candidate_id'] == identity), 'Seal chosen unique public query before charged release')
        released.append(identity)
        outcome = copy.deepcopy(labels[identity])  # The sole current-query label release.
        if b.validate_outcome(outcome, candidate):
            successful.append(copy.deepcopy(outcome))
            began = time.monotonic()
            expected_state = expected_state.condition(outcome, queried_id=identity)
            validation_seconds += time.monotonic()-began
            validation_updates += 1
        return outcome
    run = f.search(public, history, provider, posterior=posterior, policy=policy, area_cap=cap,
        clock_mhz=12., seed=seed, budget=budget, on_acquire=acquire)
    c.require(len(released) == len(set(released)) == budget and
        run['final_posterior_snapshot'] == expected_state.snapshot(), 'All planned unique queries and exact final posterior required')
    _annotate(run, labels, outer, cap, censored)
    run.update(case_id=case['case_id'], source=case['source'], cohort=case['cohort'], cap=cap, seed=seed,
        observer_validation_conditioning_host_seconds=validation_seconds,
        observer_validation_conditional_updates=validation_updates)
    path = root/'runs'/relative/'report.json'
    seal(path, run)
    return run, path.relative_to(root).as_posix()


def _summaries(points):
    groups = {}
    for point in points:
        key = tuple(point[k] for k in ('case_id', 'source', 'cohort', 'policy', 'cap', 'budget', 'planned_budget', 'endpoint_kind'))
        groups.setdefault(key, []).append(point)
    result = []
    for key, values in groups.items():
        c.require(sorted(r['seed'] for r in values) == list(SEEDS), 'Every dependent seed required once per endpoint')
        identity = dict(zip(('case_id', 'source', 'cohort', 'policy', 'cap', 'budget', 'planned_budget', 'endpoint_kind'), key))
        row = dict(**identity, dependent_seed_count=len(values))
        for field in ('verified_cycle_reduction', 'cycle_reduction_regret', 'target_measurement_seconds',
                      'target_outer_operation_seconds', 'known_infeasible_attempts', 'unknown_attempts', 'inference_seconds'):
            row['mean_'+field] = statistics.mean(r[field] for r in values)
        row.update(reference_speedup=values[0]['reference_speedup'], reference_cycle_reduction=values[0]['reference_cycle_reduction'],
            reference_complete=values[0]['reference_complete'], regret_is_lower_bound=values[0]['regret_is_lower_bound'])
        result.append(row)
    return result


def _comparisons(summaries, controls):
    result = []
    for row in summaries:
        choices = [('latency_cost_heuristic', next(value for value in controls[row['case_id']]
            if (value['policy'], value['cap'], value['budget']) == ('latency_cost_heuristic', row['cap'], row['budget'])))]
        if row['policy'] != f.MYOPIC:
            choices.append((f.MYOPIC, next(value for value in summaries if all(value[key] == row[key]
                for key in ('case_id', 'cap', 'budget', 'planned_budget', 'endpoint_kind')) and value['policy'] == f.MYOPIC)))
        for comparator, original in choices:
            difference = row['mean_verified_cycle_reduction']-original['mean_verified_cycle_reduction']
            result.append({key: row[key] for key in ('case_id', 'source', 'cohort', 'policy', 'cap', 'budget', 'planned_budget', 'endpoint_kind')} |
                dict(comparator=comparator, policy_cycle_reduction=row['mean_verified_cycle_reduction'],
                    comparator_cycle_reduction=original['mean_verified_cycle_reduction'], difference_cycle_reduction=difference,
                    result='tie' if abs(difference) <= 1e-14 else ('win' if difference > 0 else 'loss'),
                    comparator_planned_budget=row['planned_budget'] if comparator == f.MYOPIC else 3,
                    significance_established=False))
    return result


def _macros(rows):
    result = []
    keys = {(r['cohort'], r['policy'], r['cap'], r['budget'], r['planned_budget'], r['endpoint_kind'])
            for r in rows if r['cohort'] in ('old', 'expanded') and r['source'] in PRIMARY_SOURCES}
    for key in sorted(keys):
        selected = [r for r in rows if (r['cohort'], r['policy'], r['cap'], r['budget'], r['planned_budget'], r['endpoint_kind']) == key
                    and r['source'] in PRIMARY_SOURCES]
        c.require(len(selected) == 3 and {r['source'] for r in selected} == set(PRIMARY_SOURCES),
                  'Exactly three primary source units per separately reported cohort required')
        record = dict(zip(('cohort', 'policy', 'cap', 'budget', 'planned_budget', 'endpoint_kind'), key))
        result.append(record | dict(source_count=3,
            mean_verified_cycle_reduction=statistics.mean(r['mean_verified_cycle_reduction'] for r in selected),
            mean_cycle_reduction_regret=statistics.mean(r['mean_cycle_reduction_regret'] for r in selected),
            independent_units='Three consumed sources; cohort replicas and seeds are dependent; no fresh-source inference.'))
    return result


def _csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _readme(root, report):
    lines = ['# Fixed joint-posterior finite-pool development experiment', '',
        'Consumed development data. All cached cohorts and fourteen historical controls are preserved. '
        'The new known-benefit constrained-EI and finite-pool 2-OPT-C adaptations share fixed preprocessing, '
        'noisy Gaussian conditioning, Beta device updates and cycle-reduction utility. No calibration or superiority is established.', '',
        'Primary +64 LUT4 / planned B=3 terminal results; earlier B3 prefixes and separately executed B1/B2 horizons remain in JSON/CSV.', '',
        '| Case | Policy | Cycle reduction % | Cost heuristic % | Difference pp |',
        '| --- | --- | ---: | ---: | ---: |']
    for row in report['comparisons']:
        if row['endpoint_kind'] == 'B3-prefix' and row['cap'] == 64 and row['budget'] == 3 and row['comparator'] == 'latency_cost_heuristic':
            lines.append(f"| {row['case_id']} | {row['policy']} | {100*row['policy_cycle_reduction']:.9f} | "
                         f"{100*row['comparator_cycle_reduction']:.9f} | {100*row['difference_cycle_reduction']:.9f} |")
    lines.extend(['', f"{report['case_count']} cohort/source cases span {report['distinct_consumed_target_sources']} sources; "
        'old/expanded AHA/NDES/MD5 macros are separate. DCT cohort results, Expint and bitcount remain case-level results.', '',
        f"{report['new_trajectories']} new replay trajectories / {report['new_curve_points']} charged curve points; "
        f"{report['archived_control_endpoint_rows']} exact archived control rows. No native jobs.", '',
        'Preparation fits, run authentication rebuilds, policy conditioning, validation conditioning and acquisition computation '
        'have separate raw host timers. Acquisition includes fantasy integration; these timers overlap the run envelope. '
        'Historical attempts, baseline/qualification provenance and counterfactual native ledger costs are distinct and overlapping scopes.', '',
        *['- '+line for line in LIMITATIONS], '',
        'Replay: `python scripts/evaluate_finite_selection.py replay --root '+name(root)+' --output generated/finite-replay`.', ''])
    (root/'README.md').write_text('\n'.join(lines))


def run(root):
    root = Path(root).resolve()
    c.require(not any((root/name).exists() for name in ('started.json', 'report.json', 'run-failure.json')),
              'Fresh prepared run required; preserve every partial/failed run')
    try:
        protocol = authenticate(root)
        manifest(root)
        seal(root/'started.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
            prediction_release_sha256=c.sha(root/'prediction-release.json'), new_native_jobs=0))
        began_run = time.monotonic()
        models, rebuilds = {}, []
        # Rebuild/authenticate ALL initial states before parsing ANY native outcome.
        for case in protocol['cases']:
            began = time.monotonic_ns()
            state = _build_case(root/'inputs'/case['case_id'])
            ended = time.monotonic_ns()
            initial = root/'initial'/case['case_id']
            c.require(_joint_json(state) == c.unseal(initial/'joint.json') and state.predict() == c.unseal(initial/'marginals.json') and
                state.snapshot() == c.unseal(initial/'snapshot.json'), 'Exact initial joint state reconstruction required')
            models[case['case_id']] = state
            rebuilds.append(dict(case_id=case['case_id'], surrogate_fits=1, scalar_gp_fits=3,
                host_monotonic_start_ns=began, host_monotonic_end_ns=ended, host_monotonic_seconds=(ended-began)/1e9))
        controls, archives, points, indices, unique_target_rows = {}, [], [], [], {}
        totals = dict(new_trajectories=0, new_curve_points=0, conditional_updates=0,
            observer_validation_conditional_updates=0, calibrated_benefit_assumption_violations=0)
        host_totals = dict(acquisition_host_seconds=0., conditioning_host_seconds=0.,
                           observer_validation_conditioning_host_seconds=0.)
        counterfactual_costs = dict(charged_replayed_attempts=0,
            target_measurement_seconds=0., target_outer_operation_seconds=0.)
        for case in protocol['cases']:
            identity = case['case_id']
            public = c.unseal(root/'inputs'/identity/'public.json')
            history = c.unseal(root/'inputs'/identity/'history.json')
            labels, outer, censored, audit_digest = _read_outcomes(case, public)
            _control_outcome_bindings(case, audit_digest, c.digest(list(labels.values())))
            for candidate_id, outcome in labels.items():
                c.require(candidate_id not in unique_target_rows or unique_target_rows[candidate_id] == outcome,
                          'Repeated cached contexts must reuse identical candidate outcomes and paid costs')
                unique_target_rows[candidate_id] = outcome
            controls[identity] = _read_controls(case)
            archives.append(dict(case_id=identity, control_report_sha256=protocol['input_bindings'][case['control_report']],
                native_audit_digest=audit_digest, outcomes_sha256=c.digest(list(labels.values())), endpoints=controls[identity]))
            for budget in BUDGETS:
                for policy in f.POLICIES:
                    for cap in CAPS:
                        for seed in SEEDS:
                            searched, path = _run_one(root, case, models[identity], public, history, labels, outer, censored,
                                policy=policy, cap=cap, seed=seed, budget=budget)
                            indices.append(dict(case_id=identity, policy=policy, cap=cap, seed=seed, planned_budget=budget,
                                path=path, scientific_run_sha256=c.digest(stable(searched))))
                            for field in totals:
                                if field == 'new_trajectories':
                                    totals[field] += 1
                                elif field == 'new_curve_points':
                                    totals[field] += len(searched['curve'])
                                else:
                                    totals[field] += searched[field]
                            for field in host_totals:
                                host_totals[field] += searched[field]
                            counterfactual_costs['charged_replayed_attempts'] += budget
                            for field in ('target_measurement_seconds', 'target_outer_operation_seconds'):
                                counterfactual_costs[field] += searched['curve'][-1][field]
                            for point in searched['curve']:
                                metadata = dict(case_id=identity, source=case['source'], cohort=case['cohort'], policy=policy, cap=cap, seed=seed)
                                if budget == max(BUDGETS):
                                    points.append(dict(**metadata, **copy.deepcopy(point), endpoint_kind='B3-prefix'))
                                if point['budget'] == budget:
                                    points.append(dict(**metadata, **copy.deepcopy(point), endpoint_kind='horizon-aware-terminal'))
        expected = len(protocol['cases'])*len(f.POLICIES)*len(CAPS)*len(SEEDS)*len(BUDGETS)
        c.require(totals['new_trajectories'] == expected and
            totals['new_curve_points'] == expected//len(BUDGETS)*sum(BUDGETS), 'Complete independent planned-budget trajectory grid required')
        summaries = _summaries(points)
        comparisons = _comparisons(summaries, controls)
        prepare_runtime = c.unseal(root/'prepare-runtime.json')
        runtime = dict(prepare=prepare_runtime, run_initial_rebuild_records=rebuilds,
            prepare_surrogate_fits=len(protocol['cases']), prepare_scalar_gp_fits=3*len(protocol['cases']),
            run_initial_rebuild_surrogate_fits=len(rebuilds), run_initial_rebuild_scalar_gp_fits=3*len(rebuilds),
            estimator_fits_inside_search=0, run_initial_rebuild_host_seconds=sum(r['host_monotonic_seconds'] for r in rebuilds),
            run_envelope_host_seconds=time.monotonic()-began_run, **totals, **host_totals,
            counterfactual_target_search=counterfactual_costs,
            reused_target_pool=dict(unique_attempts=len(unique_target_rows),
                successful_labels=sum(r.get('status', 'success') == 'success' for r in unique_target_rows.values()),
                recorded_candidate_ledger_seconds=sum(r['measurement_seconds'] for r in unique_target_rows.values()),
                scope='Already collected target pools; overlaps the global corpus ledger and counterfactual searches. No new native attempts.'),
            scope='Prepare/rebuild model host scopes separate. Acquisition includes fantasy integration. Policy/validation conditioning and acquisition overlap run envelope; never sum envelope twice. Run envelope starts after preparation authentication and ends before final report writes; normal-table generation, proof sealing and validation are inside this envelope. Policy inference_seconds includes acquisition/conditioning only, excluding initialization and provider validation.')
        report = dict(schema=SCHEMA+'-report', scope='consumed-data development',
            protocol_sha256=c.sha(root/'protocol.json'), prediction_release_sha256=c.sha(root/'prediction-release.json'),
            case_count=len(protocol['cases']), distinct_consumed_target_sources=len({r['source'] for r in protocol['cases']}),
            old_policies=list(OLD_POLICIES), new_policies=list(f.POLICIES), **totals,
            archived_control_endpoint_rows=sum(len(rows) for rows in controls.values()), runs=indices,
            endpoints=summaries, comparisons=comparisons, primary_source_macros=_macros(summaries),
            historical_accounting=protocol['historical_accounting'],
            setup_and_original_cost_provenance=[dict(case_id=r['case_id'], provenance=r['original_cost_provenance']) for r in protocol['cases']],
            costs=runtime, new_native_jobs=0, tuning=False, calibration_established=False,
            superiority_established=False, model_promoted=False, limitations=LIMITATIONS)
        seal(root/'archived-controls.json', archives)
        seal(root/'seed-endpoints.json', points)
        seal(root/'runtime-costs.json', runtime)
        seal(root/'report.json', report)
        for filename, values in [('endpoints.csv', summaries), ('comparisons.csv', comparisons),
                                 ('source-macros.csv', report['primary_source_macros']),
                                 ('archived-controls.csv', [dict(archive_case_id=record['case_id'], **row)
                                    for record in archives for row in record['endpoints']])]:
            _csv(root/filename, values)
        _readme(root, report)
        seal_manifest(root)
        return report
    except BaseException as error:
        _failure(root, 'run', error)
        raise


def replay(reference, output):
    reference, output = Path(reference).resolve(), fresh(output, (Path(reference).resolve(),))
    manifest(reference)
    authenticate(reference)
    original = c.unseal(reference/'report.json')
    prepare(output)
    try:
        c.require(c.unseal(reference/'prediction-release.json') == c.unseal(output/'prediction-release.json'),
                  'Exact initial inputs/joint states/marginals/snapshots/fantasy release differs')
        result = run(output)
        c.require(c.unseal(reference/'archived-controls.json') == c.unseal(output/'archived-controls.json'),
                  'Exact archived numeric controls changed')
        c.require(stable(original) == stable(result), 'Scientific decisions, states or paid costs differ on replay')
        c.require(inventory(reference/'acquisitions') == inventory(output/'acquisitions'), 'Exact pre-provider acquisition proof inventory differs')
        c.require(stable(c.unseal(reference/'seed-endpoints.json')) == stable(c.unseal(output/'seed-endpoints.json')),
                  'All primary prefixes and independently planned terminal endpoints must reproduce')
        for entry in original['runs']:
            c.require(stable(c.unseal(reference/entry['path'])) == stable(c.unseal(output/entry['path'])),
                      'Exact policy trajectory except named host timers required')
        seal(output/'replay-verification.json', dict(reference_manifest_sha256=c.sha(reference/'manifest.json'),
            compared_trajectories=result['new_trajectories'], compared_curve_points=result['new_curve_points'],
            all_fourteen_controls_exact=True, excluded_host_timer_keys=sorted(HOST_TIMERS), new_native_jobs=0,
            raw_reference_runtime=c.unseal(reference/'runtime-costs.json'), raw_replayed_runtime=c.unseal(output/'runtime-costs.json')))
        seal_manifest(output)
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
        result = prepare(args.output or args.root)
        print(dict(cases=len(result['cases']), new_native_jobs=0))
    elif args.command == 'run':
        result = run(args.root)
        print({key: result[key] for key in ('new_trajectories', 'new_curve_points', 'archived_control_endpoint_rows', 'new_native_jobs')})
    else:
        c.require(args.output is not None, 'Fresh --output required for replay')
        result = replay(args.root, args.output)
        print(dict(verified_trajectories=result['new_trajectories'], new_native_jobs=0))


if __name__ == '__main__':
    main()
