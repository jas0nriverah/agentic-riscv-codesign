"""Read-only arithmetic, presentation and export for the fixed TACLe campaign.

No model fitting, policy prediction or native process is invoked here. Inputs
must already have passed the campaign's provenance and native evidence checks.
"""
from __future__ import annotations

import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from scripts.export_guarded_corpus import _csv
from scripts.report_budget_campaign import table
from scripts.report_guarded_selection import candidate_rows

CAPS, SEEDS, BUDGETS = (32, 64, 128), tuple(range(5)), (1, 2, 3)


def _seconds(value, label):
    c.require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
              'Finite nonnegative '+label+' required')
    return value


def endpoints(public, outcomes, runs, *, policies, reference_censored=False):
    """Validate all 210 paid trajectories and aggregate their 630 endpoints.

    ``runs`` use cap/seed/policy/curve and carry the identical authoritative
    candidate_outer_operation_seconds mapping. Host inference durations are
    retained separately, never used to authenticate native measurement cost.
    """
    policies = list(policies)
    c.require(len(policies) == len(set(policies)) == 14, 'All fourteen unique policies required')
    features = {row['candidate_id']: row for row in public}
    labels = {row['candidate_id']: row for row in outcomes}
    c.require(len(features) == len(public) and len(labels) == len(outcomes) and
              set(features) == set(labels) and len(features) >= 3,
              'Complete unique public/outcome pool required')
    baselines = {row['latency_features']['baseline_cycles'] for row in public}
    c.require(len(baselines) == 1 and next(iter(baselines)) > 0, 'Common positive baseline required')
    censored = False
    for identity, row in labels.items():
        if not b.validate_outcome(row, features[identity]):
            c.require(not {'area','device_fits','timing_feasible'} & set(row), 'Failed attempt has unverified hardware labels')
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class'),
                      'Failed attempts require classification and explicit censorship')
            censored |= row['reference_censored']
    c.require(type(reference_censored) is bool and reference_censored == censored,
              'Reference censorship differs from unknown outcomes')
    expected = {(policy, cap, seed) for policy in policies for cap in CAPS for seed in SEEDS}
    actual = [(run['policy'], run['cap'], run['seed']) for run in runs]
    c.require(len(actual) == len(expected) and set(actual) == expected,
              'Complete unique fourteen-policy/cap/dependent-seed grid required')
    outer = runs[0]['candidate_outer_operation_seconds']
    c.require(set(outer) == set(labels), 'Complete candidate outer-operation timer mapping required')
    for identity, seconds in outer.items():
        _seconds(seconds, 'outer-operation seconds')
        c.require(seconds >= labels[identity]['measurement_seconds'], 'Outer operation shorter than charged ledger')
    checked = {}
    for run in runs:
        c.require(run['candidate_outer_operation_seconds'] == outer, 'Authoritative outer-operation mappings differ')
        curve, cap = run['curve'], run['cap']
        c.require(len(curve) == 3 and [point['budget'] for point in curve] == list(BUDGETS),
                  'Every policy must spend all three charged attempts')
        final = curve[-1]['attempted_ids']
        for budget, point in zip(BUDGETS, curve):
            paid = point['attempted_ids']
            c.require(len(paid) == len(set(paid)) == budget and set(paid) <= set(labels),
                      'One paid unique candidate per query required')
            c.require(paid == final[:budget], 'Exact paid trajectory prefix required')
            attempted = [labels[identity] for identity in paid]
            best = max([1.0]+[row['speedup'] for row in attempted if b._feasible(row, cap, 12)])
            c.require(point['best_speedup'] == best, 'Best speedup differs from paid feasible measured outcomes')
            c.require(point['target_measurement_seconds'] == sum(row['measurement_seconds'] for row in attempted),
                      'Paid ledger cost differs from attempted prefix')
            c.require(point['target_outer_operation_seconds'] == sum(outer[identity] for identity in paid),
                      'Paid outer-operation cost differs from attempted prefix')
            known = sum((row.get('status', 'success') == 'success' and not b._feasible(row, cap, 12)) or
                        (row.get('status') == 'failed' and not row['reference_censored']) for row in attempted)
            unknown = sum(row.get('status') == 'failed' and row['reference_censored'] for row in attempted)
            c.require(point['known_infeasible_attempts'] == known and point['unknown_attempts'] == unknown,
                      'Known-infeasible/unknown attempted counts differ')
            _seconds(point.get('inference_seconds', 0), 'host inference seconds')
        checked[run['policy'], cap, run['seed']] = curve
    result = []
    for policy in policies:
        for cap in CAPS:
            reference = max([1.0]+[row['speedup'] for row in outcomes if b._feasible(row, cap, 12)])
            reference_gain = 1-1/reference
            for budget in BUDGETS:
                points = [checked[policy, cap, seed][budget-1] for seed in SEEDS]
                gains = [1-1/point['best_speedup'] for point in points]
                fractions = [gain/reference_gain for gain in gains] if reference_gain > 0 else []
                result.append(dict(policy=policy, cap=cap, budget=budget, dependent_seed_count=5,
                    mean_best_verified_speedup=statistics.mean(point['best_speedup'] for point in points),
                    mean_verified_cycle_reduction=statistics.mean(gains),
                    reference_speedup=reference, reference_cycle_reduction=reference_gain,
                    mean_cycle_reduction_regret=statistics.mean(reference_gain-gain for gain in gains),
                    mean_oracle_cycle_reduction_fraction=statistics.mean(fractions) if fractions else None,
                    oracle_gain_fraction_defined=reference_gain > 0,
                    at_least_90_percent_oracle_gain_runs=sum(value >= .9-1e-12 for value in fractions),
                    verified_reference_hits=sum(point['best_speedup'] == reference for point in points),
                    improving_reference_hits=sum(reference > 1 and point['best_speedup'] == reference for point in points),
                    reference_is_baseline=reference == 1, reference_complete=not censored, regret_is_lower_bound=censored,
                    mean_charged_attempts=budget,
                    mean_target_measurement_seconds=statistics.mean(point['target_measurement_seconds'] for point in points),
                    mean_target_outer_operation_seconds=statistics.mean(point['target_outer_operation_seconds'] for point in points),
                    mean_known_infeasible_attempts=statistics.mean(point['known_infeasible_attempts'] for point in points),
                    mean_unknown_attempts=statistics.mean(point['unknown_attempts'] for point in points),
                    mean_inference_seconds=statistics.mean(point.get('inference_seconds', 0) for point in points),
                    inference_timer_basis='host-dependent recorded inference duration; separate from paid native cost'))
    return result


def _resources(record):
    if record is None:
        return dict(flip_flops=None, carry_cells=None, bram_blocks=None, program_data_memory_blocks=None,
                    route_seeds=None, route_fmax_mhz=None)
    resources, routes = record['resources'], record['routes']
    c.require(len(routes) == 3 and {row['seed'] for row in routes} == {1, 2, 3}, 'Three unique routing seeds required')
    return dict(total_lut4=resources['lut4_count'], flip_flops=resources['flip_flop_count'],
        carry_cells=resources['carry_count'], bram_blocks=resources['memory_blocks'],
        program_data_memory_blocks=resources.get('program_data_memory_blocks'),
        route_seeds=[row['seed'] for row in routes],
        route_fmax_mhz=[row['limiting_internal_fmax_mhz'] for row in routes],
        min_fmax_mhz=min(row['limiting_internal_fmax_mhz'] for row in routes))


def _fresh_output(output, inputs=()):
    output = Path(output)
    c.require(output.is_absolute(), 'Absolute output path required')
    output = output.resolve()
    c.require(not output.exists() and not any(output.is_relative_to(path) or path.is_relative_to(output)
              for path in inputs), 'Fresh output outside sealed inputs required')
    c.require(not any((ancestor/'manifest.json').exists() and (ancestor/'manifest.json.sha256').exists()
              for ancestor in output.parents), 'Cannot write inside sealed evidence root')
    return output


def write_report(output, *, audit, baseline, endpoints, live, historical_costs, qualification):
    """Write a fresh report directory; native_measurements is a report-only map.

    ``baseline`` is the authenticated native baseline measurement dictionary.
    ``audit['native_measurements']`` maps candidate native names to their exact
    measurements; missing/failed native rows retain unknown hardware values.
    """
    output = _fresh_output(output)
    c.require(len(audit['public']) == 12, 'Declared twelve-candidate TACLe pool required')
    policies = {row['policy'] for row in endpoints}
    expected = {(policy,cap,budget) for policy in policies for cap in CAPS for budget in BUDGETS}
    c.require(len(policies) == 14 and len(endpoints) == 126 and
              {(row['policy'],row['cap'],row['budget']) for row in endpoints} == expected and
              all(row['dependent_seed_count'] == 5 for row in endpoints),
              'Complete fourteen-policy endpoint summary required')
    base = dict(baseline_cycles=baseline['performance']['cycles'], **_resources(baseline))
    c.require(base['baseline_cycles'] == 51689, 'Qualified TACLe bitcount baseline differs')
    measurements = audit.get('native_measurements', {})
    candidates = []
    labels = {row['candidate_id']:row for row in audit['outcomes']}
    for row in candidate_rows(audit):
        record = measurements.get(row['candidate'])
        if row['status'] == 'verified':
            c.require(record is not None, 'Successful candidate native measurement required')
            resource = _resources(record)
            c.require(record['performance']['cycles'] == row['cycles'] and resource['total_lut4'] == row['total_lut4'] and
                      resource['min_fmax_mhz'] == row['min_fmax_mhz'], 'Native performance/resources differ from audited outcome')
        else:
            c.require(record is None, 'Failed/unattempted candidate cannot have a successful measurement')
            resource = _resources(None)
        observed = labels.get(row['candidate_id'], {})
        candidates.append(dict(baseline_cycles=base['baseline_cycles'], device_fits=observed.get('device_fits'),
            timing_feasible=observed.get('timing_feasible'), **{**row, **resource}))
    primary = [row for row in endpoints if row['cap'] == 64]
    fmt = lambda value: 'unknown' if value is None or value == '' else f'{value:.9f}'
    text = ['# TACLeBench bitcount: fixed fourteen-policy selection',
        'One untouched source, twelve automatically lowered formulas, RV32I with 8 KiB RAM and a common 12 MHz target. '
        'Five seeds are dependent repetitions; the twelve candidates share one workload and are not twelve independent source tests. '
        'The independent test unit is one source. Native simulated processor results '
        'and integrated synthesis/routing cover the recorded input and verifier.',
        f"Baseline: {base['baseline_cycles']:,} cycles, {base['total_lut4']} LUT4, {base['flip_flops']} flip-flops, "
        f"{base['carry_cells']} carry cells, {base['bram_blocks']} BRAM blocks; minimum routed Fmax {fmt(base['min_fmax_mhz'])} MHz.",
        '## All twelve native candidate outcomes',
        table([['Candidate / formula','Baseline cycles','Optimized cycles','Speedup','LUT4 / added','FF / carry / BRAM','Minimum MHz','Check status'], ['---']*8]+
            [[row['candidate']+' / '+row['formula'], row['baseline_cycles'], row['cycles'] or 'unknown', fmt(row['speedup']),
              f"{row['total_lut4']} / {row['added_lut4']}",
              f"{row['flip_flops']} / {row['carry_cells']} / {row['bram_blocks']}", fmt(row['min_fmax_mhz']),
              row['correctness']+'; '+row['status']+'; device='+str(row['device_fits'])+'; timing='+str(row['timing_feasible'])+((': '+row['failure_class']+'; '+row['failure_reason']) if row['failure_class'] else '')]
              for row in candidates]),
        'Resources cover the integrated processor/PCPI/RAM. All three routing seeds are retained in candidates.csv. '
        'Blank or unknown failure values remain unverified; infrastructure failures carry no negative performance or correctness label.',
        '## Primary +64 LUT4 comparison at every charged budget',
        table([['Policy','Queries','Mean cycle cut (%)','Mean cycle-cut regret (%)','Verified reference hits /5','Mean paid ledger s','Mean outer-operation s'], ['---']*7]+
            [[row['policy'],row['budget'],fmt(100*row['mean_verified_cycle_reduction']),fmt(100*row['mean_cycle_reduction_regret']),
              row['verified_reference_hits'],fmt(row['mean_target_measurement_seconds']),fmt(row['mean_target_outer_operation_seconds'])]
              for row in primary]),
        'The primary endpoint is budget three at +64 LUT4. All fourteen policies, caps32/64/128 and budgets1/2/3 are retained in endpoints.csv. '
        'Cycle cut is 1−1/speedup before seed averaging. Baseline retention is not an improved-design discovery. '
        'Censored references give only lower bounds on regret to the unresolved complete-pool optimum. '
        'Combined reporting counts classified noncensored recorded correctness/memory failures as known invalid; '
        'only censored failures are unknown. This diagnostic qualification changes no policy acquisition, prediction or choice; '
        'the raw legacy twelve-policy reports remain preserved.',
        '## Measurement accounting and limitations',
        f"Current pool: {audit['charged_candidate_attempts']} charged native attempts, {len(audit['successful'])} verified labels, "
        f"{len(audit['failed_or_interrupted'])} failed/interrupted rows; {fmt(audit['candidate_wall_seconds'])} recorded ledger seconds "
        f"(complete: {audit['candidate_wall_seconds_complete']}). Baseline ledger: {fmt(audit.get('baseline_wall_seconds'))} s; "
        f"native commands: {audit.get('native_command_count', 'unknown')} / {fmt(audit.get('native_command_seconds'))} s.",
        f"Shared history: {historical_costs.get('successful_labels', 'unknown')} verified labels and "
        f"{historical_costs.get('failed_attempts', 'unknown')} failures, {historical_costs.get('total_candidate_attempts', 'unknown')} "
        f"attempts / {fmt(historical_costs.get('total_candidate_wall_seconds'))} recorded seconds, charged once. "
        'Baseline/setup, qualification, fitting and host-dependent inference are separate scopes in costs.json. '
        'Ledger, outer-operation, subprocess and native-command scopes overlap and must not be added. '
        'Other-policy paid-duration sums are replay accounting, not measured live-search lifetimes.',
        'The actual live trace is retained in live.json; policy replay does not create extra native measurements. '
        'Fixed three-query runs spend every attempt even after reaching a reference. No automatic stopping, source generalization, '
        'statistical significance, model superiority, calibrated uncertainty, uninterrupted wall-time savings, joint-set behavior or LLM advantage '
        'is established by this single fresh source. After collection these labels are consumed development data. '
        'This presenter performs zero model fits, predictions and native jobs.']
    output.mkdir(parents=True)
    (output/'results.md').write_text('\n\n'.join(text)+'\n')
    _csv(output/'candidates.csv', candidates)
    _csv(output/'endpoints.csv', endpoints)
    _csv(output/'primary.csv', primary)
    c.seal(output/'baseline.json', base)
    c.seal(output/'live.json', live)
    c.seal(output/'costs.json', dict(historical_costs=historical_costs, qualification=qualification,
        current={key:audit.get(key) for key in ('charged_candidate_attempts','candidate_wall_seconds',
            'candidate_wall_seconds_complete','baseline_wall_seconds','baseline_record_seconds',
            'native_command_seconds','native_command_count')}, timer_scopes_overlap=True,
        mean_inference_seconds_basis='host-dependent; see endpoints.csv', actual_calendar_wall_seconds=None))
    c.seal(output/'summary.json', dict(candidates=len(candidates), endpoint_summaries=len(endpoints), primary=primary,
        independent_source_count=1, dependent_seed_count=5, superiority_established=False,
        new_model_fits=0, new_model_predictions=0, new_native_jobs=0))
    c.seal(output/'manifest.json', {path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(candidates=len(candidates), policies=14, endpoint_summaries=len(endpoints), new_model_fits=0, new_native_jobs=0)


def export_corpus(previous_path, campaign_path, output):
    """Append twelve paid attempts while preserving the 87-row history exactly.

    This is a read-only export of already authenticated campaign evidence. Full
    raw native and model replay remains the campaign reproducer's responsibility.
    """
    from isaforge.speedup_corpus import family
    from scripts.reproduce_guarded_sha256 import _manifest

    previous, campaign = Path(previous_path), Path(campaign_path)
    c.require(previous.is_absolute() and campaign.is_absolute(), 'Absolute input paths required')
    previous, campaign = previous.resolve(), campaign.resolve()
    output = _fresh_output(output, (previous, campaign))
    _manifest(previous)
    _manifest(campaign)
    old, provenance = c.unseal(previous/'corpus.json'), c.unseal(campaign/'provenance.json')
    c.require(old['successful_labels'] == len(old['rows']) == 87 and len(old['failed_attempts']) == 3 and
              old['total_candidate_attempts'] == 90 and len(old['independent_workload_groups']) == 11 and len(old['contexts']) == 12,
              'Complete 87-success/3-failure/90-attempt historical corpus required')
    relative = Path(provenance['preregistration'])
    c.require(not relative.is_absolute() and '..' not in relative.parts, 'Repository-relative preregistration required')
    prereg = (ROOT/relative).resolve()
    c.require(prereg.is_relative_to(ROOT.resolve()), 'Preregistration path escapes repository')
    _fresh_output(output, (prereg,))
    _manifest(prereg)
    historical = provenance['historical_costs']
    c.require(historical['source_corpus_sha256'] == c.sha(previous/'corpus.json') and
              historical['total_candidate_wall_seconds'] == old['total_candidate_attempt_wall_seconds'] and
              historical['successful_labels'] == 87 and historical['failed_attempts'] == 3 and historical['total_candidate_attempts'] == 90,
              'Export history differs from frozen prelabel history and costs')
    audit, outer = c.unseal(campaign/'audit.json'), c.unseal(campaign/'outer-times.json')
    folder = prereg/'targets/tacle-bitcount/baseline'
    public, context = c.unseal(folder/'public.json'), c.unseal(folder/'context.json')
    c.require(audit['public'] == public and len(public) == len(audit['outcomes']) == audit['charged_candidate_attempts'] == 12 and
              audit['attempt_collection_complete'] and audit['candidate_wall_seconds_complete'] and not audit['unattempted'],
              'Complete twelve-attempt native audit required')
    labels = {row['candidate_id']:row for row in audit['outcomes']}
    c.require(len(labels) == len(public) and set(labels) == {row['candidate_id'] for row in public} == set(outer),
              'Complete unique native outcomes and outer timers required')
    c.require(sum(row['measurement_seconds'] for row in labels.values()) == audit['candidate_wall_seconds'],
              'Candidate ledger charges differ from raw audit')
    benchmark = public[0]['benchmark']
    c.require(all(row['benchmark'] == benchmark for row in public) and
              context['workload_group'] == 'tacle-bitcount' and context['context_id'] == audit['context_id'] and
              benchmark.split(':',1) == ['tacle-bitcount', context['context_id']], 'Complete source/context identity required')
    c.require('tacle-bitcount' not in old['independent_workload_groups'] and benchmark not in old['contexts'],
              'Fresh source and distinct context must be absent from old corpus')
    rows, failures = list(old['rows']), list(old['failed_attempts'])
    successful_ids, failed_ids = set(), set()
    for feature in public:
        row = labels[feature['candidate_id']]
        _seconds(outer[row['candidate_id']], 'outer-operation seconds')
        c.require(outer[row['candidate_id']] >= row['measurement_seconds'], 'Outer operation shorter than charged ledger')
        enriched = dict(row,workload_group='tacle-bitcount',candidate_family=family(row['formula']),
            measurement_timer_scope='recorded monotonic guarded-attempt elapsed; paired UTC/monotonic observations remain separate',
            outer_operation_seconds=outer[row['candidate_id']])
        if b.validate_outcome(row,feature):
            rows.append(enriched)
            successful_ids.add(row['candidate_id'])
        else:
            c.require(not {'area','device_fits','timing_feasible'} & set(row), 'Failed attempt has unverified hardware labels')
            c.require(type(row.get('reference_censored')) is bool and row.get('failure_class'),
                      'Failed attempts require classification and explicit censorship')
            enriched['correctness_verified'] = None if row['reference_censored'] else False
            failures.append(enriched)
            failed_ids.add(row['candidate_id'])
    c.require(successful_ids == {row['candidate_id'] for row in audit['successful']} and
              len(failed_ids) == len(audit['failed_or_interrupted']), 'Native success/failure counts differ')
    all_rows = rows+failures
    c.require(len({row['candidate_id'] for row in all_rows}) == len(all_rows) == 102,
              'Every charged attempt needs one unique corpus row')
    c.require(rows[:87] == old['rows'] and failures[:3] == old['failed_attempts'], 'Historical rows must remain exactly unchanged')
    contexts = dict(old['contexts'])
    contexts[benchmark] = context
    groups = sorted({row['workload_group'] for row in all_rows})
    c.require(len(groups) == 12 and len(contexts) == 13, 'Twelve-source/thirteen-context corpus required')
    live = c.unseal(campaign/'collection/live.json')
    paid = live['attempted_ids']
    c.require(provenance['live_native_attempts'] == len(paid) == len(set(paid)) == 3 and
              set(paid) <= set(labels) and live['live'] == provenance['live'], 'Exact three-attempt live prefix required')
    paired = provenance['collection_paired_durations']
    clock = dict(historical=old['clock_accounting'], current_paired_collection=paired)
    corpus = dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Consumed eleven-source history plus twelve paid TACLeBench bitcount attempts; all target labels are now development data.',
        rows=rows,failed_attempts=failures,contexts=contexts,successful_labels=len(rows),independent_workload_groups=groups,
        historical_costs=historical,preserved_original_rows_digest=c.digest(old['rows']),
        preserved_original_failed_attempts_digest=c.digest(old['failed_attempts']),
        new_candidate_attempts=12,total_candidate_attempts=102,new_candidate_wall_seconds=audit['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=old['total_candidate_attempt_wall_seconds']+audit['candidate_wall_seconds'],
        new_collection_costs={key:audit.get(key) for key in ('native_command_count','native_command_seconds','baseline_wall_seconds','baseline_record_seconds')},
        new_candidate_outer_operation_seconds=sum(outer.values()),qualification_costs=provenance['qualification'],
        historical_qualification_costs=old.get('qualification_costs'),historical_clock_accounting=old['clock_accounting'],
        current_paired_clock_accounting=paired,clock_accounting=clock,actual_calendar_wall_seconds=None,
        reference_censored_candidates=sorted(row['candidate_id'] for row in failures if row.get('reference_censored')),
        split_unit='Entire source workload; every context of a source stays together in held-out splits, with related-family exclusions.',
        timer_note='Historical costs and their clock qualification are preserved. Ledger, CLI, subprocess and native-command durations overlap; do not add them. Qualification and host inference are separate. No uninterrupted calendar wall-time saving is established.',
        new_live_native_attempts=3,new_oracle_reference_attempts=9,
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'corpus.json',corpus)
    c.seal(output/'clock-accounting.json',clock)
    _csv(output/'verified-labels.csv',rows)
    _csv(output/'failed-attempts.csv',failures)
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(Path(__file__)),previous_manifest_sha256=c.sha(previous/'manifest.json'),
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        new_model_fits=0,new_model_predictions=0,new_native_jobs=0))
    (output/'README.md').write_text('# Consumed corpus including TACLeBench bitcount\n\n'
        f"{len(rows)} verified labels, {len(failures)} preserved failures, 102 charged attempts, twelve sources and thirteen contexts. "
        'The original 87 verified rows and three failures are exactly preserved. Unknown failures carry no fabricated performance, hardware or correctness labels.\n\n'
        'One fresh source and five dependent seeds do not establish generalization, significance, model superiority or calibrated uncertainty. '
        'Keep all source contexts together in held-out splits. Candidate attempts, historical cost, baseline/setup, qualification and inference remain distinct; overlapping timer scopes are not additive. '
        'This exporter performs zero model fits, predictions or native jobs.\n')
    c.seal(output/'manifest.json',{path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return corpus
