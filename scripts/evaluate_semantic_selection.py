"""One fixed six-field/count-acquisition development experiment; no native jobs.

prepare seals all nine initial fits/predictions before run opens target outcomes.
run seals every adaptive acquisition/model-state digest before its paid release.
replay refits/repeats exactly, excluding only explicit host timing metadata.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from pathlib import Path
import shutil
import statistics
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c, count_selection as count
from isaforge import semantic_selection as semantic
from scripts import evaluate_count_acquisition as previous

SCHEMA = 'isaforge-six-semantic-selection-development-v1'
POLICY = 'hybrid_gp_adapt_count_semantic'
OUTPUT = ROOT/'results/2026-10-22-semantic-selection-development'
COUNT = ROOT/'results/2026-10-22-count-acquisition-development'
CORPUS = previous.CORPUS
NEGATIVE = ROOT/'results/2026-10-21-structure-feasibility-development/README.md'
POLICIES = {**previous.POLICIES, POLICY: 'Count GP with six semantic fields'}
SOURCES = tuple(dict.fromkeys(('scripts/evaluate_semantic_selection.py',
                             *semantic.SOURCES, *previous.SOURCES)))
HOST_TIMERS = previous.HOST_TIMERS | {
    'host_monotonic_start_ns', 'host_monotonic_end_ns', 'host_monotonic_seconds',
    'new_search_host_monotonic_seconds', 'initial_model_host_seconds',
    'run_envelope_host_monotonic_seconds', 'combined_model_and_run_host_seconds',
    'cached_initial_inference_seconds',
}
LIMITATIONS = [
    'All target sources are consumed development data; no fresh-source superiority or calibration claim.',
    'Exactly six existing formula-only fields are appended. StandardScaler, GP settings, targets, count score and paid updates are unchanged.',
    'The exact nine cached cohorts remain fixed. Expanded history already contains consumed other-source labels; newly released observations never cross cases.',
    'All thirteen earlier controls are reused, not refitted or measured again. Old/expanded source macros remain separate; DCT and Expint are separate.',
    'Five seeds and cap/budget replicas are dependent. Pool oracles do not cover every legal formula.',
    'The earlier 45-descriptor negative result and DCT constant-descriptor collision are retained, not retuned away.',
    'GP spreads/probabilities are uncalibrated. A newly separated formula is not demonstrated accurate area prediction.',
    'Ninety prior native attempts remain charged once; replay costs overlap and no uninterrupted calendar-wall or total-cost advantage is established.',
    'Cooperative local provider isolation is not an operating-system sandbox. No new native jobs or tuning.',
]


def stable(value):
    if isinstance(value, (list, tuple)):
        return [stable(item) for item in value]
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in HOST_TIMERS}
    return value


def planned_protocol():
    previous._manifest(COUNT)
    previous.authenticate(COUNT)
    base = previous.planned_protocol()
    expected = [row['case_id'] for row in previous.specs()]
    c.require(len(expected) == 9 and [row['case_id'] for row in base['cases']] == expected,
              'Exact nine cached cohorts and order required')
    bindings = dict(base['input_bindings'])
    for name in ('manifest.json', 'protocol.json', 'prediction-release.json', 'report.json', 'runtime-costs.json'):
        path = COUNT/name
        bindings[path.relative_to(ROOT).as_posix()] = c.sha(path)
    bindings[NEGATIVE.relative_to(ROOT).as_posix()] = c.sha(NEGATIVE)
    for case in base['cases']:
        path = COUNT/'new-policy'/case['case_id']/'report.json'
        bindings[path.relative_to(ROOT).as_posix()] = c.sha(path)
    return dict(schema=SCHEMA, scope='consumed-data development', new_policy=POLICY,
        cases=copy.deepcopy(base['cases']), policies=list(POLICIES),
        change='Append only the fixed six formula-only fields to the duration-free adaptive GP.',
        feature_columns=list(semantic.COLUMNS), added_columns=list(semantic.EXTRA_COLUMNS),
        gp_settings=copy.deepcopy(b.GP_SETTINGS), surrogate_factory='isaforge.semantic_selection.SemanticHardwareSurrogate',
        acquisition_policy=count.POLICY, benefit=base['benefit'], area_caps=list(previous.CAPS),
        seeds=list(previous.SEEDS), budgets=list(previous.BUDGETS), clock_mhz=12.,
        primary=base['primary'], secondary=base['secondary'],
        initial_policy='Fit exactly once per cached case; seal all nine predictions and compact snapshots before opening target outcomes.',
        update_policy='Same feature block and historical cohort plus only the same case successful paid prefix; no cross-case updates.',
        area_probability_diagnostic_threshold=.95, input_bindings=bindings,
        source_bindings={name: c.sha(ROOT/name) for name in SOURCES}, packages=base['packages'],
        count_control_root=COUNT.relative_to(ROOT).as_posix(),
        timing_exclusions=sorted(HOST_TIMERS), tuning=False, new_native_jobs=0, limitations=LIMITATIONS)


def _failure(root, phase, error):
    c.seal(Path(root)/(phase+'-failure.json'), dict(phase=phase, error=repr(error),
        traceback=traceback.format_exc(), preserve_partial_directory=True, new_native_jobs=0))


def _guard_output(output):
    protected = (CORPUS.parent, previous.EXPANDED, previous.BLIND, previous.DCT,
                 previous.LIVE, COUNT, NEGATIVE.parent)
    c.require(not output.exists() and not any(output.is_relative_to(path.resolve())
        or path.resolve().is_relative_to(output) for path in protected),
        'Fresh output outside all authenticated input roots required')


def prepare(output):
    output = Path(output).resolve()
    _guard_output(output)
    protocol = planned_protocol()
    output.mkdir(parents=True)
    c.seal(output/'protocol.json', protocol)
    c.seal(output/'prepare-started.json', dict(protocol_sha256=c.sha(output/'protocol.json'), new_native_jobs=0))
    timings = []
    try:
        for case in protocol['cases']:
            folder = output/'inputs'/case['case_id']
            folder.mkdir(parents=True)
            for name in previous.FILES:
                for suffix in ('', '.sha256'):
                    shutil.copyfile(COUNT/'inputs'/case['case_id']/(name+suffix), folder/(name+suffix))
            history = c.unseal(folder/'history.json')
            public = c.unseal(folder/'public.json')
            began = time.monotonic_ns()
            model = semantic.SemanticHardwareSurrogate().fit(history)
            predictions = model.predict(public)
            snapshot = model.snapshot()
            ended = time.monotonic_ns()
            initial = output/'initial'/case['case_id']
            c.seal(initial/'predictions.json', predictions)
            c.seal(initial/'snapshot.json', snapshot)
            timings.append(dict(case_id=case['case_id'], initial_surrogate_fits=1, initial_scalar_gp_fits=3,
                host_monotonic_start_ns=began, host_monotonic_end_ns=ended,
                host_monotonic_seconds=(ended-began)/1e9))
        c.seal(output/'prediction-release.json', dict(protocol_sha256=c.sha(output/'protocol.json'),
            case_ids=[case['case_id'] for case in protocol['cases']],
            input_files=previous.inventory(output/'inputs'), initial_files=previous.inventory(output/'initial'),
            initial_surrogate_fits=9, initial_scalar_gp_fits=27, target_scoring_started=False))
        c.seal(output/'prepare-runtime.json', dict(records=timings,
            initial_model_host_seconds=sum(row['host_monotonic_seconds'] for row in timings)))
        c.seal(output/'prepared.json', dict(protocol_sha256=c.sha(output/'protocol.json'),
            prediction_release_sha256=c.sha(output/'prediction-release.json'),
            prepare_runtime_sha256=c.sha(output/'prepare-runtime.json'), new_native_jobs=0))
    except BaseException as error:
        _failure(output, 'prepare', error)
        raise
    return protocol


def authenticate(root):
    root = Path(root).resolve()
    protocol = c.unseal(root/'protocol.json')
    c.require(protocol == planned_protocol(), 'Source, input, fixed feature block or exact cohort changed')
    c.require(not (root/'prepare-failure.json').exists(), 'Preserved failed preparation cannot be resumed')
    release = c.unseal(root/'prediction-release.json')
    c.require(c.unseal(root/'prepared.json') == dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'),
        prepare_runtime_sha256=c.sha(root/'prepare-runtime.json'), new_native_jobs=0), 'Prepared bindings differ')
    c.require(release == dict(protocol_sha256=c.sha(root/'protocol.json'),
        case_ids=[case['case_id'] for case in protocol['cases']],
        input_files=previous.inventory(root/'inputs'), initial_files=previous.inventory(root/'initial'),
        initial_surrogate_fits=9, initial_scalar_gp_fits=27, target_scoring_started=False),
        'Complete all-case prediction release required before scoring')
    expected_inputs = {case['case_id']+'/'+name+suffix for case in protocol['cases']
                       for name in previous.FILES for suffix in ('', '.sha256')}
    expected_initial = {case['case_id']+'/'+name+suffix for case in protocol['cases']
                       for name in ('predictions.json', 'snapshot.json') for suffix in ('', '.sha256')}
    c.require(previous._inventory(root/'inputs') == expected_inputs and
              previous._inventory(root/'initial') == expected_initial, 'Exact model/input inventory required')
    timing = c.unseal(root/'prepare-runtime.json')
    c.require([row['case_id'] for row in timing['records']] == release['case_ids'], 'All initial host timing records required')
    for case, record in zip(protocol['cases'], timing['records']):
        folder = root/'inputs'/case['case_id']
        for name, digest in case['cached_files'].items():
            c.require(c.sha(folder/name) == digest, 'Exact original cached cohort/input bytes required')
            c.unseal(folder/name)
        history = c.unseal(folder/'history.json')
        snapshot = c.unseal(root/'initial'/case['case_id']/'snapshot.json')
        predictions = c.unseal(root/'initial'/case['case_id']/'predictions.json')
        public = c.unseal(folder/'public.json')
        projected = [{key: row[key] for key in b.PUBLIC_KEYS} for row in history]
        c.require(snapshot['columns'] == list(semantic.COLUMNS) and snapshot['extra_columns'] == list(semantic.EXTRA_COLUMNS)
            and snapshot['training_ids'] == case['fitting_ids'] and snapshot['training_rows_sha256'] == c.digest(history)
            and snapshot['public_training_rows_sha256'] == c.digest(projected)
            and snapshot['feature_matrix_sha256'] == c.digest(semantic.semantic_matrix(projected))
            and snapshot['gp_settings'] == protocol['gp_settings'] and snapshot['source_bindings'] == semantic.source_bindings()
            and snapshot['packages'] == {key: protocol['packages'][key] for key in ('numpy', 'scipy', 'scikit-learn')},
            'Initial model exact feature/cohort/source proof differs')
        c.require([row['candidate_id'] for row in predictions] == case['public_ids']
            and [row['candidate_id'] for row in public] == case['public_ids'], 'Complete ordered target predictions required')
        fields = {'candidate_id', 'device_fit_probability'} | {key+suffix
            for key in protocol['gp_settings']['output_scale_floors'] for suffix in ('_mean', '_std')}
        for value in predictions:
            c.require(set(value) == fields and 0 <= b._number(value['device_fit_probability'], 'fit probability') <= 1,
                      'Exact finite initial prediction schema required')
            for key in protocol['gp_settings']['output_scale_floors']:
                b._number(value[key+'_mean'], key+' mean')
                c.require(b._number(value[key+'_std'], key+' std') >= 0, 'Nonnegative initial uncertainty required')
        c.require(record['initial_surrogate_fits'] == 1 and record['initial_scalar_gp_fits'] == 3
            and record['host_monotonic_end_ns'] >= record['host_monotonic_start_ns']
            and record['host_monotonic_seconds'] == (record['host_monotonic_end_ns']-record['host_monotonic_start_ns'])/1e9,
            'Exact same-clock initial host duration required')
    c.require(timing['initial_model_host_seconds'] == sum(row['host_monotonic_seconds'] for row in timing['records']),
              'Initial fit host cost must be counted once')
    return protocol


def _macro(endpoints):
    result = []
    for cohort in ('old', 'expanded'):
        for policy in POLICIES:
            for cap in previous.CAPS:
                for budget in previous.BUDGETS:
                    rows = [row for row in endpoints if row['cohort'] == cohort
                        and row['workload_group'] in previous.TARGETS[:3]
                        and (row['policy'], row['cap'], row['budget']) == (policy, cap, budget)]
                    c.require(len(rows) == 3 and {row['workload_group'] for row in rows} == set(previous.TARGETS[:3]),
                              'Three distinct primary sources required; cohorts must remain separate')
                    result.append(dict(cohort=cohort, policy=policy, cap=cap, budget=budget, source_count=3,
                        **{key: statistics.mean(row[key] for row in rows) for key in (
                            'mean_verified_cycle_reduction', 'mean_cycle_reduction_regret',
                            'mean_target_measurement_seconds', 'mean_target_outer_operation_seconds')}))
    return result


def _area_diagnostics(case, labels, predictions, cap, phase, **metadata):
    result = []
    for value in predictions:
        actual = labels[value['candidate_id']]
        if actual.get('status', 'success') != 'success':
            continue  # Unknown failures never supply area targets.
        mean, std = value['area_delta_lut4_mean'], value['area_delta_lut4_std']
        probability = b._probability_below(mean, std, cap)
        feasible = actual['area_delta_lut4'] <= cap
        result.append(dict(case_id=case['case_id'], cohort=case['cohort'], source=case['source'], cap=cap,
            phase=phase, candidate_id=value['candidate_id'], formula=actual['formula'],
            predicted_area_mean=mean, predicted_area_std=std, actual_area=actual['area_delta_lut4'],
            predicted_area_feasibility=probability, actual_area_feasible=feasible,
            brier=(probability-int(feasible))**2, absolute_area_error=abs(mean-actual['area_delta_lut4']),
            error_in_model_std=abs(mean-actual['area_delta_lut4'])/std if std > 0 else None,
            false_feasible_mean=mean <= cap and not feasible,
            false_feasible_probability95=probability >= .95 and not feasible, **metadata))
    return result


def run(root):
    root = Path(root).resolve()
    protocol = authenticate(root)
    c.require(not any((root/name).exists() for name in ('started.json', 'report.json', 'run-failure.json')),
              'Fresh complete preparation required; never resume a failed scientific run')
    c.seal(root/'started.json', dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'), new_native_jobs=0))
    try:
        return _run(root, protocol)
    except BaseException as error:
        _failure(root, 'run', error)
        raise


def _run(root, protocol):
    began = time.monotonic_ns()
    prior = c.unseal(COUNT/'report.json')
    c.require(prior['policies'] == list(previous.POLICIES) and prior['cases'] == 9,
              'All thirteen completed controls required')
    endpoints, comparisons, diagnostics, timings = [], [], [], []
    prepare_timing = c.unseal(root/'prepare-runtime.json')
    for case, initial_time in zip(protocol['cases'], prepare_timing['records']):
        identity = case['case_id']
        folder = root/'inputs'/identity
        public, history = c.unseal(folder/'public.json'), c.unseal(folder/'history.json')
        initial = c.unseal(root/'initial'/identity/'predictions.json')
        initial_snapshot = c.unseal(root/'initial'/identity/'snapshot.json')
        audit, outer = c.unseal(ROOT/case['audit']), c.unseal(ROOT/case['outer'])
        censored = previous.e.checked_outcomes(public, audit['outcomes'], audit)
        labels = {row['candidate_id']: row for row in audit['outcomes']}
        c.require(set(outer) == set(labels) and all(outer[key] >= row['measurement_seconds'] for key, row in labels.items()),
                  'Exact complete qualified candidate durations required')
        control = c.unseal(ROOT/case['package']/'report.json')
        paid_control = c.unseal(COUNT/'new-policy'/identity/'report.json')
        c.require(control['protocol_sha256'] == case['cached_files']['model-protocol.json']
            and control['native_audit_digest'] == c.digest(audit) and control['outcomes_sha256'] == c.digest(audit['outcomes'])
            and paid_control['outcomes_sha256'] == c.digest(audit['outcomes']), 'Control/native outcome binding differs')
        controls = [row for row in prior['endpoints'] if row['case_id'] == identity]
        c.require(len(controls) == 13*9 and {row['policy'] for row in controls} == set(previous.POLICIES),
                  'Complete thirteen-control endpoint grid required')
        old_twelve = previous.endpoints_for_source(case['source'], control, audit['outcomes'])
        for row in old_twelve:
            archived = next(value for value in controls if (value['policy'], value['cap'], value['budget']) ==
                            (row['policy'], row['cap'], row['budget']))
            c.require(all(archived[key] == value for key, value in row.items()), 'Original twelve control endpoints changed')
        endpoints.extend(copy.deepcopy(controls))
        cached = c.unseal(folder/'predictions.json')
        for cap in previous.CAPS:
            diagnostics.extend(_area_diagnostics(case, labels, initial, cap, 'initial_semantic'))
            diagnostics.extend(_area_diagnostics(case, labels, cached[0]['hardware'], cap, 'initial_original'))
        runs = []
        started = time.monotonic_ns()
        for seed in previous.SEEDS:
            for cap in previous.CAPS:
                released = []
                state = copy.deepcopy(initial_snapshot)
                trajectory = root/'acquisitions'/identity/f'cap{cap}-seed{seed}'

                class Tracked(semantic.SemanticHardwareSurrogate):
                    def fit(self, rows):
                        nonlocal state
                        result = super().fit(rows)
                        state = result.snapshot()
                        return result

                def acquire(event):
                    expected_ids = case['fitting_ids']+event['paid_target_ids_before_query']
                    c.require(event['attempted_ids_before_query'] == released and event['charged_before_query'] == len(released)
                        and state['training_ids'] == expected_ids and state['columns'] == list(semantic.COLUMNS),
                        'Only exact history plus this case successful paid prefix may fit')
                    c.seal(trajectory/f'{len(released):02d}.json', dict(event=event,
                        semantic_policy=POLICY, training_ids=state['training_ids'],
                        model_state_sha256=state['model_state_sha256'], snapshot_sha256=c.digest(state)))

                def provider(candidate):
                    proof = c.unseal(trajectory/f'{len(released):02d}.json')
                    c.require(proof['event']['candidate_id'] == candidate['candidate_id']
                        and candidate['candidate_id'] not in released, 'Seal each choice before one charged outcome release')
                    released.append(candidate['candidate_id'])
                    return copy.deepcopy(labels[candidate['candidate_id']])

                prediction = dict(hardware=initial, inference_seconds={'hybrid_gp_adapt': initial_time['host_monotonic_seconds']})
                searched = count.search(public, history, provider, area_cap=cap, clock_mhz=12., seed=seed, budget=3,
                    predictions=prediction, surrogate_factory=Tracked, on_acquire=acquire)
                c.require(len(released) == len(set(released)) == 3, 'All three unique attempts must be charged')
                previous.annotate(searched, labels, outer, cap, censored)
                searched.update(policy=POLICY, acquisition_policy=count.POLICY)
                runs.append(dict(cap=cap, seed=seed, **searched))
                for event in searched['events']:
                    if event['action'] == 'acquire' and event['charged_before_query']:
                        diagnostics.extend(_area_diagnostics(case, labels, event['hardware_predictions'], cap,
                            'paid_update_semantic', seed=seed, charged_before_query=event['charged_before_query']))
        report = dict(case_id=identity, source=case['source'], cohort=case['cohort'], runs=runs,
            outcomes_sha256=c.digest(audit['outcomes']), protocol_sha256=c.sha(root/'protocol.json'),
            prediction_release_sha256=c.sha(root/'prediction-release.json'), reference_censored=censored, new_native_jobs=0)
        c.seal(root/'new-policy'/identity/'report.json', report)
        added = previous.summarize_new(case['source'], runs, audit['outcomes'], censored)
        for row in added:
            row.update(policy=POLICY, case_id=identity, cohort=case['cohort'])
        endpoints.extend(added)
        for row in added:
            for comparator in (count.POLICY, 'hybrid_gp_adapt', 'hybrid_gp_zero_shot', 'merit'):
                original = next(value for value in controls if
                    (value['policy'], value['cap'], value['budget']) == (comparator, row['cap'], row['budget']))
                delta = row['mean_verified_cycle_reduction']-original['mean_verified_cycle_reduction']
                comparisons.append(dict(case_id=identity, cohort=case['cohort'], source=case['source'],
                    cap=row['cap'], budget=row['budget'], comparator=comparator,
                    semantic_cycle_reduction=row['mean_verified_cycle_reduction'],
                    control_cycle_reduction=original['mean_verified_cycle_reduction'], cycle_reduction_change=delta,
                    result=previous.verdict(delta), significance_established=False))
        ended = time.monotonic_ns()
        timings.append(dict(case_id=identity, host_monotonic_start_ns=started, host_monotonic_end_ns=ended,
            new_search_host_monotonic_seconds=(ended-started)/1e9,
            paid_gp_update_fit_calls=sum(run['paid_update_calls'] for run in runs),
            paid_update_host_seconds=sum(run['paid_update_host_seconds'] for run in runs)))
    macro = _macro(endpoints)
    initial_diagnostics = [row for row in diagnostics if row['phase'].startswith('initial_')]
    diagnostic_summary = []
    for case in protocol['cases']:
        for phase in ('initial_original', 'initial_semantic'):
            for cap in previous.CAPS:
                values = [row for row in initial_diagnostics if (row['case_id'], row['phase'], row['cap']) == (case['case_id'], phase, cap)]
                diagnostic_summary.append(dict(case_id=case['case_id'], phase=phase, cap=cap, candidates=len(values),
                    area_mae=statistics.mean(row['absolute_area_error'] for row in values),
                    area_brier=statistics.mean(row['brier'] for row in values),
                    false_feasible_mean=sum(row['false_feasible_mean'] for row in values),
                    false_feasible_probability95=sum(row['false_feasible_probability95'] for row in values)))
    result = dict(schema=SCHEMA, scope=protocol['scope'], protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'), policies=list(POLICIES), cases=9,
        distinct_target_sources=5, initial_surrogate_fits=9, initial_scalar_gp_fits=27,
        new_policy_trajectories=135, new_policy_seed_endpoints=405,
        reused_control_trajectories=1755, reused_control_seed_endpoints=5265,
        endpoints=endpoints, primary_source_macro=macro,
        primary=[row for row in macro if row['cap'] == 64 and row['budget'] == 3], comparisons=comparisons,
        q3_comparison_counts={policy: dict(Counter(row['result'] for row in comparisons if
            row['budget'] == 3 and row['comparator'] == policy)) for policy in
            (count.POLICY, 'hybrid_gp_adapt', 'hybrid_gp_zero_shot', 'merit')},
        early_comparison_counts={str(budget): dict(Counter(row['result'] for row in comparisons if
            row['budget'] == budget and row['comparator'] == count.POLICY)) for budget in (1, 2)},
        regressed_endpoints=[row for row in comparisons if row['result'] == 'loss'],
        initial_area_diagnostics=diagnostic_summary, costs=copy.deepcopy(prior['costs']),
        preserved_negative_descriptor_sha256=c.sha(NEGATIVE), calibration_established=False,
        superiority_established=False, tuning=False, new_native_jobs=0, limitations=LIMITATIONS)
    c.seal(root/'report.json', result)
    c.seal(root/'area-diagnostics.json', diagnostics)
    ended = time.monotonic_ns()
    c.seal(root/'runtime-costs.json', dict(records=timings, initial_model_host_seconds=prepare_timing['initial_model_host_seconds'],
        host_monotonic_start_ns=began, host_monotonic_end_ns=ended, run_envelope_host_monotonic_seconds=(ended-began)/1e9,
        combined_model_and_run_host_seconds=prepare_timing['initial_model_host_seconds']+(ended-began)/1e9,
        initial_surrogate_fits=9, paid_update_surrogate_fits=sum(row['paid_gp_update_fit_calls'] for row in timings),
        scope='Initial fit/predict/snapshot durations plus run envelope, without process/import startup or the gap between phases. Paid-update timers overlap run envelope; do not add them again. Historical native durations reused, never rerun.'))
    for name, values in (('endpoints.csv', endpoints), ('source-macro.csv', macro), ('comparisons.csv', comparisons),
                         ('area-diagnostics.csv', diagnostic_summary), ('regressed-endpoints.csv', result['regressed_endpoints'])):
        previous._csv(root/name, values)
    _readme(root, result)
    previous.seal_manifest(root)
    return result


def _readme(root, result):
    primary = [row for row in result['comparisons'] if row['cap'] == 64 and row['budget'] == 3]
    lines = ['# One six-field semantic GP development hypothesis',
        'All nine initial models/predictions were sealed before any target scoring. The sole representation change appends the fixed six fields '
        'to the duration-free adaptive GP. All13 earlier controls remain unchanged. Nine cached cohort/source cases, five dependent seeds, '
        'caps32/64/128, budgets1/2/3. Expanded history already contains consumed other-source labels; no newly scored outcomes cross cases.',
        previous.table([['Case', 'Comparator', 'Semantic gain%', 'Control gain%', 'Difference pp', 'Result'], ['---']*6]+[
            [row['case_id'], row['comparator'], f"{100*row['semantic_cycle_reduction']:.9f}",
             f"{100*row['control_cycle_reduction']:.9f}", f"{100*row['cycle_reduction_change']:.9f}", row['result']]
            for row in primary]),
        f"Query-three comparisons over27 cohort/source/cap means: {result['q3_comparison_counts']}. "
        f"Early mean comparisons versus count-only: {result['early_comparison_counts']}. "
        'All caps, budgets, source macros and regressions are retained in CSV/JSON. Old/expanded AHA/NDES/MD5 macros remain separate; DCT and Expint remain separate.',
        'NDES operation orientation is now distinguishable, but this does not guarantee correct synthesis costs or calibrated GP probabilities. '
        'Both constant DCT expressions still have the identical six-field block despite different integrated costs; their original constant feature remains. '
        'The earlier45-descriptor negative result remains bound and unmodified. Area Brier/error/false-feasible diagnostics are secondary, not confidence guarantees.',
        'All90 prior native attempts, including3 failures, remain charged once globally in costs. No new native measurements occur. '
        'Nine initial surrogate fits (27 scalar GPs) and paid-success update fits are new host work. Their raw monotonic timers are retained separately; '
        'counterfactual policy native costs overlap, and historical clock qualifications remain. No automatic stopping, uninterrupted wall-time or total-cost advantage is established.',
        'This is one fixed consumed-data representation experiment, not a feature sweep or an untouched-source result. No learner is promoted. '
        'Replay with `python scripts/evaluate_semantic_selection.py replay --root results/2026-10-22-semantic-selection-development '
        '--output generated/reproduction/semantic-selection` using a fresh output. Only explicitly named host timing fields may differ.']
    (root/'README.md').write_text('\n\n'.join(lines)+'\n')


def replay(reference, output):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    c.require(not output.is_relative_to(reference) and not reference.is_relative_to(output),
              'Replay output must not overlap its frozen reference')
    previous._manifest(reference)
    authenticate(reference)
    original = c.unseal(reference/'report.json')
    prepare(output)
    try:
        c.require(c.sha(reference/'prediction-release.json') == c.sha(output/'prediction-release.json'),
                  'Exact initial predictions/snapshots/release differ')
        result = run(output)
        c.require(stable(original) == stable(result), 'Semantic numerical/decision/control replay differs')
        c.require(c.unseal(reference/'area-diagnostics.json') == c.unseal(output/'area-diagnostics.json'),
                  'Constraint prediction/error diagnostics differ')
        c.require(previous.inventory(reference/'acquisitions') == previous.inventory(output/'acquisitions'),
                  'Pre-release predictions, paid prefix or model-state digest differs')
        for case in original['endpoints']:
            c.require(case['policy'] in POLICIES, 'Unexpected replay policy')
        for case in planned_protocol()['cases']:
            name = Path('new-policy')/case['case_id']/'report.json'
            c.require(stable(c.unseal(reference/name)) == stable(c.unseal(output/name)), 'Exact paid trajectory differs')
        for name in ('prepare-runtime.json', 'runtime-costs.json'):
            c.require(stable(c.unseal(reference/name)) == stable(c.unseal(output/name)), 'Non-timing cost fields differ')
        c.seal(output/'replay-verification.json', dict(reference_manifest_sha256=c.sha(reference/'manifest.json'),
            compared_initial_surrogates=9, compared_new_trajectories=135, compared_new_seed_endpoints=405,
            all_thirteen_controls_unchanged=True, excluded_host_timer_keys=sorted(HOST_TIMERS), new_native_jobs=0))
        previous.seal_manifest(output)
    except BaseException as error:
        _failure(output, 'replay', error)
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'replay'))
    parser.add_argument('--root', type=Path, default=OUTPUT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output or args.root)
        print(dict(cases=len(result['cases']), initial_surrogate_fits=9, new_native_jobs=0))
    elif args.command == 'run':
        result = run(args.root)
        print({key: result[key] for key in ('new_policy_trajectories', 'q3_comparison_counts', 'early_comparison_counts', 'new_native_jobs')})
    else:
        c.require(args.output is not None, 'Fresh replay --output required')
        result = replay(args.root, args.output)
        print(dict(verified_new_trajectories=result['new_policy_trajectories'], new_native_jobs=0))


if __name__ == '__main__':
    main()
