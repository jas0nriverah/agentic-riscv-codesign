"""Present sealed blind-source results without fitting models or running hardware."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge import factorized_selection_experiment as e
from scripts.report_budget_campaign import LABELS, table
from scripts.export_guarded_corpus import _csv
from scripts.report_guarded_selection import candidate_rows, baseline_summary
from scripts.reproduce_guarded_sha256 import _manifest, _hashes

CAMPAIGN = ROOT/'results/2026-10-21-blind-campaign'
PREREG = ROOT/'results/2026-10-21-blind-preregistration'
COLLECTION = ROOT/'results/2026-10-21-blind-collection'
POLICY_LABELS = {**LABELS, e.controls.POLICY: 'Feasible-benefit XGBoost',
                 e.POLICY: 'Factorized feasibility XGBoost'}


def cycle_reduction(speedup):
    """Fraction of original processor cycles saved, with baseline exactly zero."""
    c.require(isinstance(speedup, (int, float)) and speedup >= 1,
              'Best verified speedup must include baseline')
    return 1 - 1 / speedup


def endpoints_for_source(workload, report, outcomes, policies=POLICY_LABELS):
    """Recompute gains from each paid trajectory before averaging dependent seeds."""
    c.require(set(policies) == set(POLICY_LABELS), 'All twelve frozen policies required')
    expected = {(policy, cap, seed) for policy in policies for cap in e.AREA_CAPS for seed in e.SEEDS}
    actual = [(run['policy'], run['cap'], run['seed']) for run in report['runs']]
    c.require(len(actual) == len(expected) and set(actual) == expected,
              'Complete unique policy/cap/dependent-seed grid required')
    labels = {row['candidate_id']: row for row in outcomes}
    c.require(len(labels) == len(outcomes), 'Unique measured candidate identities required')
    references = {cap: max([1.0] + [row['speedup'] for row in outcomes
                  if b._feasible(row, cap, 12)]) for cap in e.AREA_CAPS}
    result = []
    for policy in policies:
        for cap in e.AREA_CAPS:
            reference = references[cap]
            reference_gain = cycle_reduction(reference)
            runs = [run for run in report['runs'] if run['policy'] == policy and run['cap'] == cap]
            for budget in e.BUDGETS:
                points = []
                for run in runs:
                    curve = run['curve']
                    c.require(len(curve) == max(e.BUDGETS) and
                              [point['budget'] for point in curve] == list(e.BUDGETS),
                              'Every policy spends all three charged attempts')
                    point = curve[budget-1]
                    c.require(len(point['attempted_ids']) == budget and
                              len(set(point['attempted_ids'])) == budget and set(point['attempted_ids']) <= set(labels),
                              'One paid unique candidate per query required')
                    attempted = [labels[identity] for identity in point['attempted_ids']]
                    c.require(point['attempted_ids'] == curve[-1]['attempted_ids'][:budget],
                              'Paid trajectory must preserve its query prefix')
                    best = max([1.0] + [row['speedup'] for row in attempted if b._feasible(row, cap, 12)])
                    c.require(point['best_speedup'] == best, 'Trajectory differs from paid verified outcomes')
                    c.require(point['target_measurement_seconds'] == sum(row['measurement_seconds'] for row in attempted),
                              'Trajectory paid ledger cost differs')
                    points.append(point)
                gains = [cycle_reduction(point['best_speedup']) for point in points]
                fractions = [gain/reference_gain for gain in gains] if reference_gain > 0 else []
                result.append(dict(workload_group=workload, policy=policy, cap=cap, budget=budget,
                    dependent_seed_count=len(points), mean_best_verified_speedup=statistics.mean(
                        point['best_speedup'] for point in points),
                    mean_verified_cycle_reduction=statistics.mean(gains),
                    reference_speedup=reference, reference_cycle_reduction=reference_gain,
                    mean_cycle_reduction_regret=statistics.mean(reference_gain-gain for gain in gains),
                    mean_oracle_cycle_reduction_fraction=statistics.mean(fractions) if fractions else None,
                    at_least_90_percent_oracle_gain_runs=sum(value >= .9-1e-12 for value in fractions),
                    oracle_gain_fraction_defined=reference_gain > 0,
                    improving_reference_hits=sum(reference > 1 and point['best_speedup'] == reference for point in points),
                    reference_is_baseline=reference == 1,
                    reference_complete=not report['reference_censored'],
                    regret_is_lower_bound=report['reference_censored'],
                    mean_charged_attempts=budget,
                    mean_target_measurement_seconds=statistics.mean(point['target_measurement_seconds'] for point in points),
                    mean_target_outer_operation_seconds=statistics.mean(point['target_outer_operation_seconds'] for point in points),
                    mean_known_infeasible_attempts=statistics.mean(point['known_infeasible_attempts'] for point in points),
                    mean_unknown_attempts=statistics.mean(point['unknown_attempts'] for point in points),
                    mean_inference_seconds=statistics.mean(point.get('inference_seconds', 0) for point in points)))
    return result


def source_macro(endpoints):
    """Each source has equal weight; candidate counts and seeds are not sources."""
    groups = sorted({row['workload_group'] for row in endpoints})
    c.require(groups, 'At least one source required')
    metrics = ('mean_best_verified_speedup', 'mean_verified_cycle_reduction',
               'reference_cycle_reduction', 'mean_cycle_reduction_regret',
               'mean_target_measurement_seconds', 'mean_target_outer_operation_seconds',
               'mean_known_infeasible_attempts', 'mean_unknown_attempts', 'mean_inference_seconds')
    result = []
    for policy in POLICY_LABELS:
        for cap in e.AREA_CAPS:
            for budget in e.BUDGETS:
                rows = [row for row in endpoints if (row['policy'], row['cap'], row['budget']) == (policy, cap, budget)]
                c.require(len(rows) == len(groups) and {row['workload_group'] for row in rows} == set(groups),
                          'One endpoint per independent source required')
                fractions = [row['mean_oracle_cycle_reduction_fraction'] for row in rows
                             if row['oracle_gain_fraction_defined']]
                result.append(dict(policy=policy, cap=cap, budget=budget, source_count=len(groups),
                    **{key: statistics.mean(row[key] for row in rows) for key in metrics},
                    mean_oracle_cycle_reduction_fraction=statistics.mean(fractions) if fractions else None,
                    oracle_gain_fraction_source_count=len(fractions),
                    baseline_only_sources=sum(row['reference_is_baseline'] for row in rows),
                    censored_sources=sum(not row['reference_complete'] for row in rows),
                    independent_units='source workloads; five dependent seeds within each source'))
    return result


def primary_comparisons(endpoints):
    """Descriptive fixed factorized-model comparisons; sources remain the units."""
    selected = {(row['workload_group'], row['policy']): row for row in endpoints
                if row['cap'] == 64 and row['budget'] == 3}
    result = []
    for group in sorted({row['workload_group'] for row in endpoints}):
        model = selected[group, e.POLICY]
        for comparator in ('frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic'):
            control = selected[group, comparator]
            difference = model['mean_verified_cycle_reduction']-control['mean_verified_cycle_reduction']
            result.append(dict(workload_group=group, policy=e.POLICY, comparator=comparator,
                model_cycle_reduction=model['mean_verified_cycle_reduction'],
                comparator_cycle_reduction=control['mean_verified_cycle_reduction'],
                difference_cycle_reduction=difference,
                result='tie' if abs(difference) <= 1e-12 else ('win' if difference > 0 else 'loss'),
                independent_unit='source workload', significance_established=False))
    counts = [dict(comparator=comparator,
        **{outcome: sum(row['comparator'] == comparator and row['result'] == outcome for row in result)
           for outcome in ('win', 'tie', 'loss')}, significance_established=False)
        for comparator in ('frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic')]
    return result, counts


def collection_costs(collection, campaign, prereg, targets):
    """Bind complete subprocess wall to every charged campaign identity and ledger."""
    collection, campaign, prereg = map(Path, (collection, campaign, prereg))
    _manifest(collection)
    protocol = c.unseal(collection/'protocol.json')
    commands = c.unseal(collection/'commands.json')
    summary = c.unseal(collection/'summary.json')
    cohort = c.unseal(prereg/'cohort.json')
    provenance = c.unseal(campaign/'provenance.json')
    c.require(protocol['schema'] == 'isaforge-blind-collection-v1' and
              protocol['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
              protocol['release_sha256'] == c.sha(campaign/'release.json') and
              protocol['prelabel_commit'] == provenance['prelabel_commit'] and
              protocol['source_sha256'] == c.sha(ROOT/'scripts/collect_blind_campaign.py') and
              protocol['workers'] == protocol['attempts_per_candidate'] == 1,
              'Complete serial released collection protocol required')
    expected_order = {group: target['native_order'] for group, target in cohort['targets'].items()}
    c.require(protocol['order'] == expected_order and
              [(row['workload_group'], row['candidate']) for row in commands] ==
              [(group, name) for group, names in expected_order.items() for name in names],
              'Complete unique declared collection order required')
    observed = {}
    for target in targets:
        labels = {row['candidate_id']: row for row in target['outcomes']}
        for name, candidate in zip(target['audit']['pool_names'], target['public']):
            observed[target['workload'], name] = (labels[candidate['candidate_id']], target['outer_times'][candidate['candidate_id']])
    c.require(set(observed) == {(row['workload_group'], row['candidate']) for row in commands},
              'Collection and charged campaign identities differ')
    costs = []
    for row in commands:
        label, outer = observed[row['workload_group'], row['candidate']]
        elapsed = row['elapsed_seconds']
        c.require(isinstance(elapsed, (float, int)) and math.isfinite(elapsed) and
                  elapsed >= outer >= row['ledger_seconds'] == label['measurement_seconds'] and
                  row['attempt_status'] == label.get('status', 'success') and
                  (row['returncode'] == 0) == (row['attempt_status'] == 'success'),
                  'Collection status/timer must match and enclose the charged attempt')
        costs.append(dict(workload_group=row['workload_group'], candidate=row['candidate'],
            candidate_id=label['candidate_id'], status=row['attempt_status'],
            complete_subprocess_seconds=elapsed, outer_operation_seconds=outer, ledger_seconds=row['ledger_seconds']))
    expected_summary = dict(attempted_candidates=len(costs),
        successful=sum(row['status'] == 'success' for row in costs),
        failed=sum(row['status'] == 'failed' for row in costs),
        complete_subprocess_seconds=sum(row['complete_subprocess_seconds'] for row in costs),
        ledger_seconds=sum(row['ledger_seconds'] for row in costs), historical_costs=cohort['historical_costs'])
    c.require(all(summary[key] == value for key, value in expected_summary.items()),
              'Collection summary differs from actual candidate charges')
    return dict(**expected_summary, candidates=costs, manifest_sha256=c.sha(collection/'manifest.json'),
                scope='Complete subprocess wall includes startup and overlaps CLI-operation and ledger timers.')


def _record_resources(record):
    routes = record['routes']
    c.require(len(routes) == len({row['seed'] for row in routes}) == 3, 'Exactly three unique routed seeds required')
    return dict(total_lut4=record['resources']['lut4_count'],
                flip_flops=record['resources']['flip_flop_count'],
                carry_cells=record['resources'].get('carry_count'),
                min_fmax_mhz=min(row['limiting_internal_fmax_mhz'] for row in routes),
                route_seed_count=len(routes))


def packed_measurements(native, names):
    """Read only named, bounded regular JSON members; never extract archive paths."""
    native = Path(native)
    manifest = c.unseal(native/'archive-manifest.json')
    c.require(manifest['archive'] == 'raw.tar.gz' and c.sha(native/'raw.tar.gz') == manifest['sha256'],
              'Native measurement archive checksum differs')
    entries = {row['path']: row for row in manifest['files']}
    c.require(len(entries) == len(manifest['files']), 'Unique archived measurement inventory required')
    wanted = {f'measurements/{name}/measurement.json' for name in names}
    c.require(wanted <= set(entries), 'Every successful measurement must be archived')
    records = {}
    with tarfile.open(native/'raw.tar.gz', 'r:gz') as archive:
        members = archive.getmembers()
        c.require(len(members) == len(entries) and {member.name for member in members} == set(entries) and
                  all(member.isfile() for member in members), 'Only complete unique regular archived files allowed')
        for name in wanted:
            member = archive.getmember(name)
            entry = entries[name]
            c.require(member.size == entry['bytes'] and 0 < member.size <= 1024*1024,
                      'Bounded measurement JSON member required')
            with archive.extractfile(member) as stream:
                payload = stream.read(1024*1024+1)
            c.require(len(payload) == member.size and hashlib.sha256(payload).hexdigest() == entry['sha256'],
                      'Archived measurement checksum differs')
            records[Path(name).parent.name] = json.loads(payload)
    return records


def load_targets(campaign, prereg):
    """Authenticate the packed inventory and all report/native evidence bindings."""
    campaign, prereg = Path(campaign).resolve(), Path(prereg).resolve()
    _manifest(campaign)
    _manifest(prereg)
    cohort = c.unseal(prereg/'cohort.json')
    provenance = c.unseal(campaign/'provenance.json')
    c.require(provenance['schema'] == 'isaforge-blind-cohort-v1-campaign' and
              provenance['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
              provenance['release_sha256'] == c.sha(campaign/'release.json') and
              provenance['source_bindings'] == cohort['source_bindings'] and
              set(provenance['targets']) == set(cohort['targets']), 'Campaign/preregistration bindings differ')
    _hashes(ROOT, cohort['source_bindings'])
    targets = []
    for native in sorted((campaign/'targets').glob('*/native')):
        workload = native.parent.name
        selection = native.parent/'selection'
        audit = c.unseal(native.parent/'audit.json')
        outcomes = audit['outcomes']
        report = c.unseal(selection/'report.json')
        protocol = c.unseal(selection/'protocol.json')
        public = b.public_rows(audit['public'])
        c.require(protocol['target_workload'] == workload and
                  all(row['benchmark'].split(':', 1)[0] == workload for row in public),
                  'Whole-source identity required')
        c.require(c.sha(selection/'protocol.json') == c.sha(prereg/'targets'/workload/'selection/protocol.json') and
                  public == c.unseal(prereg/'targets'/workload/'public.json'),
                  'Exact frozen source pool and selection protocol required')
        c.require(report['protocol_sha256'] == c.sha(selection/'protocol.json') and
                  report['outcomes_sha256'] == c.digest(outcomes) and
                  report['native_audit_digest'] == c.digest(audit), 'Report/evidence bindings differ')
        c.require(report['reference_censored'] == e.checked_outcomes(public, outcomes, audit),
                  'Reference censorship differs')
        c.require(set(protocol['policies']) == set(POLICY_LABELS), 'All twelve frozen policies required')
        context = c.unseal(prereg/'targets'/workload/'baseline/context.json')
        c.require(context['context_id'] == audit['context_id'] and context['workload_group'] == workload,
                  'Native/corpus source context differs')
        declared = cohort['targets'][workload]
        c.require(context['context_id'] == declared['context_id'] and len(public) == declared['pool_size'] and
                  audit['pool_names'] == declared['native_order'], 'Declared complete source pool differs')
        outer = c.unseal(native.parent/'outer-times.json')
        c.require(outer == report['candidate_outer_operation_seconds'] and
                  set(outer) == {row['candidate_id'] for row in public} and
                  all(outer[row['candidate_id']] >= row['measurement_seconds'] for row in outcomes),
                  'Complete enclosing outer-operation times required')
        targets.append(dict(workload=workload, native=native, selection=selection,
            audit=audit, outcomes=outcomes, report=report, protocol=protocol,
            public=public, context=context, outer_times=outer))
    c.require(targets, 'Completed packed source targets required')
    c.require({target['workload'] for target in targets} == set(cohort['targets']), 'Complete declared target cohort required')
    return targets


def build(campaign, prereg, output, *, collection=COLLECTION):
    campaign, prereg, output = map(lambda path: Path(path).resolve(), (campaign, prereg, output))
    c.require(not output.exists() and not any(output.is_relative_to(path) for path in (campaign, prereg)),
              'Fresh report outside frozen evidence required')
    targets = load_targets(campaign, prereg)
    collection = Path(collection).resolve()
    c.require(not output.is_relative_to(collection), 'Fresh report outside collection evidence required')
    collected = collection_costs(collection, campaign, prereg, targets)
    endpoints, candidates, baselines, reliability, costs, predictions = [], [], [], [], [], []
    for target in targets:
        workload, audit, outcomes, report = (target[key] for key in ('workload', 'audit', 'outcomes', 'report'))
        endpoints += endpoints_for_source(workload, report, outcomes, target['protocol']['policies'])
        baseline = baseline_summary(audit, {})
        displayed = candidate_rows(audit)
        records = packed_measurements(target['native'], ['baseline']+[row['candidate'] for row in displayed if row['status'] == 'verified'])
        resources = _record_resources(records['baseline'])
        c.require(records['baseline']['performance']['cycles'] == baseline['cycles'], 'Archived baseline cycles differ')
        baselines.append(dict(workload_group=workload, baseline_cycles=baseline['cycles'], **resources))
        for row in displayed:
            resource = dict(flip_flops=None, carry_cells=None, route_seed_count=None)
            if row['status'] == 'verified':
                resource = _record_resources(records[row['candidate']])
                c.require(resource['total_lut4'] == row['total_lut4'] and resource['min_fmax_mhz'] == row['min_fmax_mhz'],
                          'Raw and derived hardware resources differ')
                c.require(records[row['candidate']]['performance']['cycles'] == row['cycles'], 'Archived candidate cycles differ')
            candidates.append(dict(workload_group=workload, baseline_cycles=baseline['cycles'],
                **{**row, **resource}, outer_operation_seconds=target['outer_times'][row['candidate_id']]))
        predictions += [dict(workload_group=workload, seed=seed['seed'], cap=cap, **row)
                        for seed in c.unseal(target['selection']/'feasibility-predictions.json')
                        for cap in e.AREA_CAPS for row in seed['by_cap'][str(cap)]]
        for cap in e.AREA_CAPS:
            values = [row['feasibility_brier'] for row in report['feasibility_diagnostics'] if row['cap'] == cap]
            reliability.append(dict(workload_group=workload, cap=cap,
                feasibility_brier=statistics.mean(values) if values and all(value is not None for value in values) else None,
                verified_candidate_count=sum(row.get('status', 'success') == 'success' for row in outcomes),
                unknown_hardware_count=sum(row.get('status', 'success') != 'success' for row in outcomes),
                calibrated=False))
        costs.append(dict(workload_group=workload,
            **{key: audit[key] for key in ('charged_candidate_attempts', 'candidate_wall_seconds',
                'native_command_count', 'native_command_seconds', 'baseline_wall_seconds', 'baseline_record_seconds')},
            candidate_outer_operation_seconds=sum(target['outer_times'].values()),
            classifier_fit_prediction_costs=c.unseal(target['selection']/'feasibility-costs.json'),
            utility_fit_prediction_costs=c.unseal(target['selection']/'controls11/utility-inference-costs.json'),
            control_fit_prediction_costs=[dict(seed=row['seed'], fit_and_prediction_seconds=row['inference_seconds'])
                for row in c.unseal(target['selection']/'controls11/model/predictions.json')],
            shared_historical_costs=target['protocol']['cost_provenance'],
            calibration_cost_seconds=target['protocol'].get('calibration_cost_seconds')))
    macro = source_macro(endpoints)
    primary = [row for row in macro if row['cap'] == 64 and row['budget'] == 3]
    comparisons, comparison_counts = primary_comparisons(endpoints)
    historical = costs[0]['shared_historical_costs']['historical_training_available']
    c.require(all(row['shared_historical_costs']['historical_training_available'] == historical for row in costs),
              'All sources must share the same historical cost cohort')
    c.require(historical['successful_labels'] == 45 and historical['failed_attempts'] == 3 and
              historical['total_candidate_attempts'] == 48, 'Shared historical attempt counts differ')
    cohort = c.unseal(prereg/'cohort.json')
    accounting = dict(shared_historical_costs=historical,
        new_candidate_attempts=sum(row['charged_candidate_attempts'] for row in costs),
        new_candidate_wall_seconds=sum(row['candidate_wall_seconds'] for row in costs),
        total_candidate_attempts=48+sum(row['charged_candidate_attempts'] for row in costs),
        total_candidate_attempt_wall_seconds=historical['total_candidate_wall_seconds']+sum(row['candidate_wall_seconds'] for row in costs),
        qualification=cohort['qualification'], freeze_outer_operation_seconds=cohort['freeze_outer_operation_seconds'],
        collection=collected,
        per_source=costs, timer_scopes_overlap=True, new_model_fits=0, new_native_jobs=0)
    fmt = lambda value: '' if value is None else f'{value:.9f}'
    text = ['# Blind independent-source campaign',
        f"{len(targets)} independent source workloads; {len(candidates)} declared candidate attempts. "
        'Primary endpoint: three charged attempts, at most64 added LUT4, minimum routed Fmax12MHz. '
        'Original inputs and recorded-input verifiers are retained. All hardware costs cover the integrated processor/PCPI/RAM; '
        'Fmax is the minimum of three routing seeds. No frequency increase is credited.',
        '## Whole-source primary comparison',
        table([['Policy', 'Cycle reduction', 'Cycle-reduction regret', 'Oracle gain fraction', 'Sources with positive reference', 'Mean ledger s'], ['---']*6]+
            [[POLICY_LABELS[row['policy']], fmt(row['mean_verified_cycle_reduction']), fmt(row['mean_cycle_reduction_regret']),
              fmt(row['mean_oracle_cycle_reduction_fraction']), row['oracle_gain_fraction_source_count'],
              fmt(row['mean_target_measurement_seconds'])] for row in primary]),
        'Cycle reduction is1−1/speedup, computed within every seed before averaging. '
        'Oracle gain fraction divides achieved cycle reduction by the best verified feasible cycle reduction. '
        'A baseline-only reference has zero gain and an undefined fraction, excluded from the fraction macro with its denominator disclosed. '
        'It never earns a90% gain success or an improving-design discovery. Regret is the difference in these cycle reductions. '
        'For censored pools this is regret to the best verified reference, a lower bound on regret to the unresolved optimum.',
        'Each source receives equal macro weight after its five dependent seed repetitions are averaged. '
        'Seeds are bootstrap/tie repetitions, not independent workloads. Every policy uses the same frozen historical cohort '
        'and pays for each query before observing its outcome. All twelve policies, caps32/64/128 and budgets1/2/3 '
        'are in endpoints.csv and source-macro.csv. These are cooperative paid replays, not measured live adaptive-search lifetimes.',
        table([['Factorized model versus', 'Source wins', 'Ties', 'Losses'], ['---']*4]+
              [[POLICY_LABELS[row['comparator']], row['win'], row['tie'], row['loss']] for row in comparison_counts]),
        'These counts compare mean verified cycle reduction at the fixed primary endpoint in each source. '
        'They are descriptive comparisons of the frozen policies; no statistical significance or general model superiority is established. '
        'Source-specific gains and differences are in primary-comparisons.csv.',
        '## Actual processor evidence',
        table([['Source', 'Baseline cycles', 'LUT4', 'Minimum Fmax MHz'], ['---']*4]+
              [[row['workload_group'], row['baseline_cycles'], row['total_lut4'], fmt(row['min_fmax_mhz'])] for row in baselines]),
        table([['Source', 'Candidate', 'Cycles', 'Speedup', 'LUT4 / added', 'Minimum Fmax MHz', 'Correctness', 'Charged s'], ['---']*8]+
            [[row['workload_group'], row['candidate'], row['cycles'], fmt(row['speedup']) if row['speedup'] != '' else '',
              f"{row['total_lut4']} / {row['added_lut4']}", fmt(row['min_fmax_mhz']) if row['min_fmax_mhz'] != '' else '',
              row['correctness'], fmt(row['charged_wall_seconds'])] for row in candidates]),
        'Complete candidate resources, analytic-cycle residuals, failures and enclosing operation times are in candidates.csv. '
        'Unknown correctness/performance/hardware outcomes remain blank and charged; infrastructure failures do not become negative labels. '
        'References cover the declared recorded-input pools, not all legal formulas or arbitrary inputs.',
        '## Costs and reliability',
        f"New collection: {sum(row['charged_candidate_attempts'] for row in costs)} charged attempts / "
        f"{sum(row['candidate_wall_seconds'] for row in costs):.3f}ledger seconds, including failures. "
        f"Enclosing candidate operations: {sum(row['candidate_outer_operation_seconds'] for row in costs):.3f}s. "
        f"Complete candidate subprocess wall, including startup: {collected['complete_subprocess_seconds']:.3f}s "
        f"across {collected['successful']} successful and {collected['failed']} failed commands. "
        f"Baseline ledger: {sum(row['baseline_wall_seconds'] for row in costs):.3f}s. "
        f"Native commands: {sum(row['native_command_count'] for row in costs)} / "
        f"{sum(row['native_command_seconds'] for row in costs):.3f}s. These scopes overlap and must not be added. "
        f"Historical cost:45 successful labels plus3 failed attempts =48 attempts / {historical['total_candidate_wall_seconds']:.3f}s. "
        f"History plus new candidate attempts: {accounting['total_candidate_attempts']} / {accounting['total_candidate_attempt_wall_seconds']:.3f}s. "
        f"Qualification/setup subprocess wall: {accounting['qualification']['setup_subprocess_seconds']:.3f}s, including rejected sources. "
        'This overlaps accepted-source baseline/CLI/native timers and is not added to them. '
        'Shared historical training costs, setup/calibration and per-seed fitting/prediction timers are retained in costs.json. '
        'The shared history is counted once. '
        'Full collection subprocess wall is retained in the packed driver evidence. Policy paid wall sums are not an observed end-to-end acquisition runtime.',
        'Feasibility Brier error uses successfully verified candidates only; unknown hardware outcomes are excluded and charged. '
        'Bootstrap score spread is uncalibrated estimator disagreement. Broad model superiority, calibrated confidence and joint-set performance are not established. '
        'Preserve heuristic wins, ties and regressions. Target labels are now consumed data.',
        'This presenter performs zero model fits and zero native measurements. Full chronology, raw-evidence and exact policy verification belong to blind_campaign replay.']
    output.mkdir(parents=True)
    for name, rows in (('baselines.csv', baselines), ('candidates.csv', candidates), ('endpoints.csv', endpoints),
                       ('source-macro.csv', macro), ('primary.csv', primary), ('primary-comparisons.csv', comparisons),
                       ('feasibility.csv', reliability), ('predictions.csv', predictions)):
        _csv(output/name, rows)
    c.seal(output/'costs.json', accounting)
    c.seal(output/'summary.json', dict(primary=primary, macro=macro, independent_source_count=len(targets),
        candidate_attempts=len(candidates), feasibility=reliability, superiority_established=False,
        primary_comparisons=comparisons, primary_comparison_counts=comparison_counts,
        new_model_fits=0, new_native_jobs=0))
    (output/'results.md').write_text('\n\n'.join(text)+'\n')
    c.seal(output/'provenance.json', dict(source_sha256=c.sha(Path(__file__)),
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'), prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        collection_manifest_sha256=collected['manifest_sha256'],
        new_model_fits=0, new_native_jobs=0))
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(sources=len(targets), candidates=len(candidates), policies=len(primary),
        endpoint_summaries=len(endpoints), macro_endpoints=len(macro), new_model_fits=0, new_native_jobs=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, default=CAMPAIGN)
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--collection', type=Path, default=COLLECTION)
    args = parser.parse_args()
    print(build(args.campaign, args.preregistration, args.output, collection=args.collection))


if __name__ == '__main__':
    main()
