"""Authenticate a prospective multi-workload selection campaign.

This wrapper starts no native jobs. Public target features come only from
accepted baselines; target labels are opened only by explicit evaluation.
The cohort manifest is intended to be committed before candidate collection.
It is a cooperative replay boundary, not an operating-system sandbox.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics

from . import assembly_lowering as lowering
from . import codesign as c
from . import partitioned_workload as partition
from . import prospective_inputs as prior_inputs
from . import workload_audit
from .latency_features import candidate_features
from .speedup_corpus import family, validate_isa
from .workload_experiment import validate_execution, verify_cache

SCHEMA = 'isaforge-prospective-cohort-v1'
SOURCE = 'isaforge/campaign_evidence.py'
DEFAULT_HISTORY = (*prior_inputs.DEFAULT_HISTORY,
                   c.ROOT / 'generated/partitioned-slre-2026-10-20-r2')
BASELINE_FILES = ('plan.json', 'discovery/discovery.json',
                  'measurements/baseline/measurement.json')


def _seconds(value):
    from .selection import _number
    value = _number(value, 'elapsed seconds')
    c.require(value >= 0, 'Negative elapsed seconds')
    return value


def _receipts(root, *, allow_failures=False):
    """Verify every receipt/log, retaining expected negative controls."""
    root = Path(root)
    rows = c.unseal(root / 'commands.json')
    c.require(isinstance(rows, list), 'Native receipts must be a list')
    names = set()
    for row in rows:
        name = row['log']; path = (root / name).resolve()
        c.require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()),
                  'Native receipt path escapes root')
        c.require(name not in names, 'Duplicate native receipt log')
        names.add(name)
        c.require(c.sha(path) == row['log_sha256'], 'Native command log changed: ' + name)
        _seconds(row['elapsed_seconds'])
        if not allow_failures:
            c.require(row['returncode'] == row['expected_returncode'] and row['failure'] is None,
                      'Failed native command in accepted baseline')
    return rows


def _calibration(root):
    from scripts.analyze_speedup_model import authenticated_calibration
    calibration, plan = authenticated_calibration(c.ROOT / 'results/2026-10-20-latency-calibration')
    root = Path(root)
    for name in ('picorv32.v', 'soc_top.v', 'pcpi_single.v'):
        c.require(c.sha(root / 'inputs' / name) == plan['inputs'][name],
                  'Historical/target hardware differs from latency calibration')
    return calibration


def _adapter(plan):
    if plan.get('build_variant',{}).get('required_entrypoint') == 'isaforge/qualified_workload.py':
        from . import qualified_workload
        return qualified_workload.adapter_for_plan(plan)
    if plan.get('build_variant',{}).get('required_entrypoint') == 'isaforge/extended_workload.py':
        from . import extended_workload
        extended_workload.check_plan(plan)
        return extended_workload
    if plan.get('memory_partition') == partition.PARTITION:
        return partition
    from . import bounded_workload
    c.require(plan.get('memory_partition') == bounded_workload.PARTITION and
              plan.get('build_variant',{}).get('required_entrypoint') == bounded_workload.SOURCE,
              'Unknown or unchecked memory partition')
    return bounded_workload


def _observations(root, adapter, receipts):
    """Reconcile every successful checked-observer invocation and RAM image."""
    for row in receipts:
        if (not row['log'].endswith('/simulation.json') or 'unobserved-control' in row['log'] or
                row['failure'] is not None or row['returncode'] != row['expected_returncode']):
            continue
        raw=c.read(root/row['log'])
        if row['expected_returncode']==10:
            c.require(raw['stack_initialized'] and raw['stack_violations']>0, 'Guard simulation lacks violation')
        else:
            adapter.validate_memory(raw,trapped=row['expected_returncode']==6)
        c.require(len(row['argv'])==5 and row['argv'][-1]==str(adapter.PARTITION['stack_floor']),
                  'Observer invocation differs from declared partition')
        binary=partition.portable_binary(root,row['argv'][1])
        end,start=adapter.memory_symbols(binary.with_suffix('.hex'))
        c.require(row['argv'][-3:-1]==[str(end),str(start)], 'Observer bounds differ from ELF symbols')
        c.require(binary.with_suffix('.hex').read_text()==adapter.memory_image(binary.read_bytes()),
                  'Observed RAM image differs from binary and zero-fill contract')


def authenticate_baseline(root, adapter):
    """Generalize the frozen baseline audit using a declared checked partition."""
    root=Path(root).resolve(); prior_inputs.reject_candidate_measurements(root)
    plan=c.unseal(root/'plan.json')
    c.require(c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'], 'Invalid target context')
    c.require(plan.get('memory_partition')==adapter.PARTITION, 'Unchecked memory partition')
    c.require(plan['compiler_flags']==list(partition.compact.FLAGS), 'Unexpected target compiler flags')
    if hasattr(adapter,'check_plan'):
        adapter.check_plan(plan)
        c.require((root/'inputs/stack_monitor.hpp').read_text()==adapter.monitor_source(), 'Bounded stack monitor derivation differs')
    if hasattr(adapter,'validate_runtime_inputs'):
        adapter.validate_runtime_inputs(root)
    for name,digest in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Target source changed: '+name)
    for name,digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name)==digest, 'Target input changed: '+name)
    commands=_receipts(root)
    for command in commands:
        c.require(not command['log'].startswith('measurements/') or command['log'].startswith('measurements/baseline/'),
                  'Candidate attempt exists before freeze')
        if command['argv'][0]==plan['tools']['gcc']['path']:
            flags=plan['compiler_flags']
            c.require(command['argv'][1:1+len(flags)]==flags, 'Compiler receipt flags differ')
    _observations(root,adapter,commands)
    guards=verify_cache(root/'guard-controls','controls.json')
    c.require([r['detected_kind'] for r in guards['controls']]==['stack-pointer','ram-write'], 'Guard negative controls missing')
    for row in guards['controls']:
        raw=row['raw']
        c.require(raw['stack_initialized'] and raw['stack_violations']>0 and
                  raw['first_violation']['kind']==row['detected_kind'], 'Guard failed to detect violation')
        expected_address=(4096 if adapter.PARTITION==partition.PARTITION else adapter.PARTITION['stack_floor']-4) \
            if row['detected_kind']=='stack-pointer' else adapter.PARTITION['program_limit']
        c.require(raw['first_violation']['address']==expected_address, 'Guard fixture violated unexpected address')
        folder=root/'guard-controls'/row['name']/'guard-simulation/simulation.json'
        c.require(c.read(folder)==raw, 'Guard raw evidence differs')
    discovery=verify_cache(root/'discovery','discovery.json')
    c.require(discovery['context_id']==plan['context_id'], 'Target discovery context differs')
    baseline=verify_cache(root/'measurements/baseline','measurement.json')
    c.require(baseline['context_id']==plan['context_id'] and baseline['name']=='baseline', 'Baseline context differs')
    c.require(baseline['evaluation_id']==c.digest([plan['context_id'],c.sha(root/'discovery/discovery.json'),'baseline']), 'Baseline evaluation identity differs')
    profile=c.read(root/discovery['profile']); memory=adapter.validate_memory(profile)
    performance=validate_execution(profile)
    c.require(profile['markers']==2 and sum(profile['region_counts'].values())+1==performance['instructions'], 'Profile counters differ')
    c.require(performance==baseline['performance']==discovery['baseline_performance'], 'Baseline performance differs')
    image=root/discovery['baseline_image']
    c.require(c.sha(image)==c.sha(image.parent.parent/'original/firmware.hex'), 'Marked baseline changed')
    c.require(c.sha(root/baseline['firmware_image'])==baseline['firmware_sha256'], 'Measured baseline firmware changed')
    adapter.memory_symbols(image)
    c.require(image.read_text()==adapter.memory_image(image.with_suffix('.bin').read_bytes()), 'Baseline RAM packing differs')
    c.require(validate_isa((image.parent/'disassembly.txt').read_text())['custom_static_sites']==0, 'Baseline contains custom instructions')
    folder=root/'measurements/baseline'
    sims=[folder/p for p in baseline['artifacts'] if p.endswith('/simulation/simulation.json')]
    controls=[folder/p for p in baseline['artifacts'] if p.endswith('/unobserved-control/simulation.json')]
    c.require(len(sims)==len(controls)==1, 'Missing baseline observer comparison')
    c.require(validate_execution(c.read(controls[0]))==performance, 'Unobserved baseline differs')
    adapter.validate_memory(c.read(sims[0]))
    c.require(validate_execution(c.read(sims[0]))==performance, 'Measured baseline simulation differs')
    attempt=sims[0].parent.parent
    c.require(c.validate_netlist(c.read(attempt/'synthesis/ice40-netlist.json'))==baseline['resources'], 'Baseline resource recount differs')
    routes=[dict(seed=seed,**c.timing_summary(c.read(attempt/f'synthesis/route-{seed}.json'),12.0)) for seed in (1,2,3)]
    c.require(routes==baseline['routes'] and all(r['internal_timing_pass'] and r['device_fits'] for r in routes), 'Baseline timing infeasible')
    c.require(baseline['speedup']==1.0, 'Baseline speedup differs')
    return plan,discovery,baseline,commands,memory


def _public(root, plan, discovery, baseline, calibration):
    """Recompute execution features from baseline disassembly and occurrences."""
    root = Path(root)
    program = lowering.read_program((root / discovery['baseline_image']).parent.joinpath('disassembly.txt').read_text())
    workload = 'embench-' + plan['workload']
    benchmark = workload + ':' + plan['context_id']
    result = []
    for row in discovery['pool']:
        c.require(row['candidate_id'] == c.digest([plan['context_id'], row['formula']]),
                  'Discovery candidate identity differs')
        c.require(lowering.verify_lowering(row, program, discovery['block_starts']) == row['lowering_check'],
                  'Candidate lowering check differs')
        execution = candidate_features(row, program, baseline['performance']['cycles'],
                                       baseline['performance']['instructions'], calibration)
        execution['region_custom_instructions'] = row['region_custom_instructions']
        c.require(execution['region_custom_instructions'] == sum(o['blockRuns'] for o in row['occurrences']),
                  'Baseline replacement count differs')
        result.append(dict(candidate_id=row['candidate_id'], benchmark=benchmark,
            formula=row['formula'], **row['features'], latency_features=execution))
    c.require(len(result) == plan['pool_size'], 'Incomplete target pool')
    return result


def _outcome(public, record, baseline):
    routes = record['routes']
    c.require([r['seed'] for r in routes] == [1, 2, 3], 'Three fixed routing seeds required')
    return dict(public, speedup=record['speedup'], area=record['resources']['lut4_count'],
        area_cap=baseline['resources']['lut4_count'] + 128,
        area_delta_lut4=record['added_lut4'],
        routed_fmax_min_mhz=min(r['limiting_internal_fmax_mhz'] for r in routes),
        device_fits=all(r['device_fits'] for r in routes), timing_feasible=record['timing_feasible'],
        correctness_verified=True, measurement_source='synthesis_estimate',
        measurement_seconds=_seconds(record['elapsed_seconds']),
        baseline_cycles=baseline['performance']['cycles'], candidate_cycles=record['performance']['cycles'],
        baseline_period_ns=1000/12, candidate_period_ns=1000/12)


def history_rows(history_roots=DEFAULT_HISTORY):
    """Authenticate old native evidence and rebuild all historical features.

    Old automatic imports retain their original sample identities. SLRE uses
    its frozen discovery identities. Compiler/partition contexts are explicit.
    No historical feature projection is trusted without re-derivation.
    """
    rows, contexts, costs = [], {}, []
    for value in history_roots:
        root = Path(value).resolve(); plan = c.unseal(root / 'plan.json')
        imported = None
        if 'memory_partition' in plan:
            checked = _adapter(plan).audit(root)
        else:
            imported = workload_audit.import_automatic(root)
            checked = imported['audit']
        discovery = c.unseal(root / 'discovery/discovery.json')
        baseline = c.unseal(root / 'measurements/baseline/measurement.json')
        public = _public(root, plan, discovery, baseline, _calibration(root))
        old = {r['formula']: r for r in imported['rows']} if imported else {}
        for candidate, features in zip(discovery['pool'], public):
            record = c.unseal(root / 'measurements' / candidate['name'] / 'measurement.json')
            measured = _outcome(features, record, baseline)
            if imported:
                measured = {**old[features['formula']], **measured,
                            'candidate_id': old[features['formula']]['candidate_id']}
            measured.update(workload_group='embench-' + plan['workload'],
                            candidate_family=family(features['formula']))
            rows.append(measured)
        receipts = _receipts(root)
        contexts[public[0]['benchmark']] = prior_inputs.context(root, plan, receipts)
        costs.append(dict(workload='embench-' + plan['workload'], context_id=plan['context_id'],
            candidate_labels=len(public),
            candidate_wall_seconds=sum(r['measurement_seconds'] for r in rows[-len(public):]),
            native_command_seconds=checked['native_seconds'], native_command_count=len(receipts),
            baseline_wall_seconds=baseline['elapsed_seconds'],
            setup_command_seconds=sum(r['elapsed_seconds'] for r in receipts if not r['log'].startswith('measurements/'))))
    c.require(len({r['candidate_id'] for r in rows}) == len(rows), 'Duplicate historical sample')
    return rows, contexts, dict(contexts=costs,
        candidate_labels=len(rows), candidate_wall_seconds=sum(r['measurement_seconds'] for r in rows),
        note='Native command and evaluation wall scopes overlap; do not add them. All available historical labels are charged, including excluded families.')


def baseline_public(target_root):
    root = Path(target_root).resolve()
    # This check is deliberately first; do not open labels during qualification.
    prior_inputs.reject_candidate_measurements(root)
    c.require(not list((root / 'measurements').glob('candidate_*/attempt-*')),
              'Candidate attempt exists before prospective freeze')
    adapter = _adapter(c.unseal(root/'plan.json'))
    plan, discovery, baseline, receipts, memory = authenticate_baseline(root,adapter)
    calibration = _calibration(root)
    c.require(c.read(root / 'inputs/latency-calibration.json') == calibration,
              'Target calibration projection differs')
    image = root / discovery['baseline_image']
    program = lowering.read_program((image.parent / 'disassembly.txt').read_text())
    marked, sites = lowering.mark_assembly((image.parent.parent / 'program.s').read_text())
    c.require(marked == (image.parent.parent / 'marked.S').read_text(), 'Marked assembly differs')
    site_map = lowering.map_sites(sites, (image.parent / 'symbols.txt').read_text())
    regenerated = adapter.extract_pool(program, c.read(root / discovery['profile']),
                                         site_map, plan['pool_size'], calibration)
    c.require(len(regenerated['pool']) == len(discovery['pool']), 'Pool size differs')
    for derived, candidate in zip(regenerated['pool'], discovery['pool']):
        c.require(all(candidate[k] == v for k, v in derived.items()), 'Re-extracted candidate differs')
        c.require(lowering.lower(marked, candidate) == (root / candidate['assembly']).read_text(),
                  'Lowered assembly differs')
    public = _public(root, plan, discovery, baseline, calibration)
    context = prior_inputs.context(root, plan, receipts)
    context['baseline_provenance']['memory_check'] = memory
    context['workload_group'] = 'embench-' + plan['workload']
    context['context_transfer'] = 'Explicit compiler/linker/memory context; source workload is the independent unit.'
    before = dict(workload='embench-' + plan['workload'], context_id=plan['context_id'],
        artifacts={name: c.sha(root / name) for name in BASELINE_FILES},
        commands_sha256=c.sha(root / 'commands.json'), receipts=receipts,
        pool_names=[r['name'] for r in discovery['pool']],
        public_sha256=c.digest(public), baseline_lut4=baseline['resources']['lut4_count'])
    return public, context, before


def freeze(target_roots, output, *, history_roots=DEFAULT_HISTORY):
    from . import budgeted_selection as model
    output = Path(output)
    c.require(not output.exists(), 'Use a fresh campaign output')
    roots = [Path(p).resolve() for p in target_roots]
    c.require(len(roots) >= 2 and len(set(roots)) == len(roots), 'At least two distinct target workloads required')
    # Accept every baseline before creating a model prediction or directory.
    targets = [baseline_public(root) for root in roots]
    groups = [before['workload'] for _, _, before in targets]
    c.require(len(set(groups)) == len(groups), 'Input/compiler variants are not independent workloads')
    history, contexts, costs = history_rows(history_roots)
    c.require(not set(groups) & {r['workload_group'] for r in history}, 'Target source workload in history')
    for public, context, _ in targets:
        contexts[public[0]['benchmark']] = context
    calibration = _calibration(roots[0])
    output.mkdir(parents=True)
    cohort = dict(schema=SCHEMA, target_labels_read=0, primary_added_lut4_cap=64, primary_budget=3,
        added_lut4_caps=[32,64,128], budgets=[1,2,3], seeds=[0,1,2,3,4], clock_mhz=12.0,
        route_seeds=[1,2,3], historical_costs=costs, targets={},
        source_bindings={SOURCE:c.sha(c.ROOT/SOURCE)},
        chronology='Commit and push this manifest before candidate collection; hashes alone do not establish wall-clock chronology.',
        independent_unit='Workload/source family; seeds and compiler/input contexts are dependent repetitions.',
        policy_isolation='Cooperative replay only; no external LLM operating-system isolation.')
    for root, (public, context, before) in zip(roots, targets):
        name = before['workload']; destination = output / name
        model.freeze(history, public, contexts, destination, target_workload=name,
            calibration_cost_seconds=calibration['native_command_seconds'], cost_provenance=costs)
        c.seal(output / (name + '-baseline.json'), before)
        cohort['targets'][name] = dict(context_id=before['context_id'],
            baseline_snapshot=name+'-baseline.json', baseline_snapshot_sha256=c.sha(output/(name+'-baseline.json')),
            selection_artifacts={p.name:c.sha(p) for p in destination.iterdir() if p.is_file()},
            original_root=str(root))
    # Recheck every cohort member after all predictions are written.
    for root in roots:
        prior_inputs.reject_candidate_measurements(root)
        c.require(not list((root/'measurements').glob('candidate_*/attempt-*')), 'Candidate attempt occurred during freeze')
    c.seal(output / 'cohort.json', cohort)
    return cohort


def _chronology(root, before):
    for name, digest in before['artifacts'].items():
        c.require(c.sha(root/name) == digest, 'Frozen target baseline changed: '+name)
    final = _receipts(root, allow_failures=True); initial = before['receipts']
    c.require(c.digest(initial) == c.digest(final[:len(initial)]), 'Prelabel native receipt prefix differs')
    c.require(all(not r['log'].startswith('measurements/') or r['log'].startswith('measurements/baseline/')
                  for r in initial), 'Candidate attempt preceded freeze')
    suffix = final[len(initial):]
    c.require(suffix and all(any(r['log'].startswith('measurements/'+name+'/') for name in before['pool_names'])
                            for r in suffix), 'Unexpected post-freeze native scope')
    return final


def _audit_success(root, candidate, baseline, commands, adapter):
    """Raw audit for a successful candidate in a possibly incomplete pool."""
    base = root/'measurements'/candidate['name']; record = verify_cache(base, 'measurement.json')
    plan = c.unseal(root/'plan.json')
    c.require(record['evaluation_id'] == c.digest([plan['context_id'],c.sha(root/'discovery/discovery.json'),candidate['name']])
              and record['context_id'] == plan['context_id'] and record['candidate_id'] == candidate['candidate_id'],
              'Measured candidate identity differs')
    c.require(record['features'] == candidate['features'] and record['formula'] == candidate['formula'], 'Measured feature join differs')
    simulations = [base/p for p in record['artifacts'] if p.endswith('/simulation/simulation.json')]
    c.require(len(simulations) == 1, 'Exactly one candidate attempt is required')
    raw = c.read(simulations[0]); attempt = simulations[0].parent.parent
    performance = validate_execution(raw, candidate); adapter.validate_memory(raw)
    c.require(performance == record['performance'], 'Cycle/correctness record differs')
    c.require(performance['benchmark_result_u32'] == baseline['performance']['benchmark_result_u32'], 'Program result differs')
    c.require(baseline['performance']['instructions']-performance['instructions'] == candidate['expected_instruction_reduction'],
              'Measured instruction savings differ')
    c.require(c.validate_netlist(c.read(attempt/'synthesis/ice40-netlist.json')) == record['resources'], 'Netlist recount differs')
    routes = [dict(seed=seed, **c.timing_summary(c.read(attempt/f'synthesis/route-{seed}.json'),12.0)) for seed in (1,2,3)]
    c.require(routes == record['routes'] and record['timing_feasible'] == all(r['internal_timing_pass'] and r['device_fits'] for r in routes),
              'Routed timing recount differs')
    c.require(record['added_lut4'] == record['resources']['lut4_count']-baseline['resources']['lut4_count'], 'Area delta differs')
    c.require(record['speedup'] == baseline['performance']['cycles']/performance['cycles'], 'Speedup arithmetic differs')
    firmware = root/record['firmware_image']
    c.require(c.sha(firmware) == record['firmware_sha256'], 'Candidate firmware changed')
    c.require(validate_isa((firmware.parent/'disassembly.txt').read_text())['custom_static_sites'] == len(candidate['occurrences']),
              'Static custom count differs')
    stock = c.read(attempt/'stock-on-extension/simulation.json')
    adapter.validate_memory(stock)
    c.require(validate_execution(stock) == baseline['performance'], 'Stock-on-extension control differs')
    trap = str((attempt/'illegal-on-baseline/simulation.json').relative_to(root))
    c.require(any(r['log']==trap and r['returncode']==r['expected_returncode']==6 for r in commands), 'Negative trap control missing')
    return record


def outcomes(target_root, before, public):
    root = Path(target_root).resolve(); commands = _chronology(root,before)
    plan=c.unseal(root/'plan.json'); discovery=c.unseal(root/'discovery/discovery.json')
    adapter=_adapter(plan)
    if hasattr(adapter,'check_plan'):
        adapter.check_plan(plan)
        c.require((root/'inputs/stack_monitor.hpp').read_text()==adapter.monitor_source(), 'Bounded stack monitor derivation differs')
    if hasattr(adapter,'validate_runtime_inputs'):
        adapter.validate_runtime_inputs(root)
    c.require(plan['context_id']==before['context_id'], 'Target context differs')
    for name,digest in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Target source changed: '+name)
    for name,digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name)==digest, 'Target input changed: '+name)
    _observations(root,adapter,commands)
    baseline=verify_cache(root/'measurements/baseline','measurement.json')
    c.require(c.digest(public)==before['public_sha256'], 'Frozen public pool changed')
    mapping={r['candidate_id']:r for r in public}; rows=[]; failures=[]
    expected={r['name'] for r in discovery['pool']} | {'baseline'}
    c.require({p.name for p in (root/'measurements').iterdir() if p.is_dir()}==expected, 'Unexpected/missing candidate measurement directory')
    for candidate in discovery['pool']:
        base=root/'measurements'/candidate['name']; attempts=list(base.glob('attempt-*'))
        c.require(len(attempts)==1, 'One native attempt per candidate required; retries need separately charged protocol')
        feature=mapping[candidate['candidate_id']]
        if (base/'measurement.json').exists():
            c.require(not list(base.rglob('failure.json')), 'Successful candidate also contains uncharged failure')
            record=_audit_success(root,candidate,baseline,commands,adapter)
            rows.append(_outcome(feature,record,baseline))
        else:
            paths=list(base.rglob('failure.json')); c.require(len(paths)==1, 'Missing native failure evidence')
            failed=c.read(paths[0]); c.require(isinstance(failed.get('error'),str), 'Malformed native failure')
            elapsed=_seconds(failed['elapsed_seconds'])
            receipt_rows=[r for r in commands if r['log'].startswith(str(attempts[0].relative_to(root))+'/')]
            c.require(receipt_rows, 'Failed attempt lacks native receipts')
            rows.append(dict(feature,status='failed',measurement_seconds=elapsed,error=failed['error']))
            failures.append(dict(candidate_id=feature['candidate_id'],source=str(paths[0].relative_to(root)),
                                 sha256=c.sha(paths[0]),elapsed_seconds=elapsed,error=failed['error']))
    full_audit = adapter.audit(root) if not failures else dict(scope='Frozen authenticated baseline and per-success raw audit; failed attempts cannot enter feasible selection.',failures=failures)
    residuals=[dict(candidate_id=r['candidate_id'],
        estimated_saved_cycles=r['latency_features']['estimated_saved_cycles'],
        measured_saved_cycles=r['baseline_cycles']-r['candidate_cycles'],
        saved_cycle_residual=r['baseline_cycles']-r['candidate_cycles']-r['latency_features']['estimated_saved_cycles'])
        for r in rows if r.get('status','success')=='success']
    return rows, dict(raw_audit=full_audit,failed_attempts=failures,analytic_cycle_residuals=residuals,
        analytic_cycles_match_all_successes=all(r['saved_cycle_residual']==0 for r in residuals) if residuals else None,
        native_command_count=len(commands),native_command_seconds=sum(r['elapsed_seconds'] for r in commands),
        target_candidate_wall_seconds=sum(r['measurement_seconds'] for r in rows),
        baseline_wall_seconds=baseline['elapsed_seconds'],cache_hits=0,new_native_jobs=0)


def paired_summary(reports):
    """Aggregate only matched workload/seed/cap/budget endpoints."""
    rows=[]
    for workload,report in reports.items():
        endpoints={(run['policy'],run['seed'],run['area_delta_lut4_cap'],point['budget']):point
                   for run in report['runs'] for point in run['curve']}
        policies=sorted({key[0] for key in endpoints})
        settings=sorted({key[1:] for key in endpoints})
        c.require(len(endpoints)==len(policies)*len(settings), 'Incomplete paired endpoints')
        for comparator in ('frequency','merit','calibrated_latency','latency_cost_heuristic'):
            c.require(comparator in policies, 'Missing declared heuristic comparator')
            for policy in policies:
                if policy==comparator: continue
                for cap,budget in sorted({(cap,budget) for _,cap,budget in settings}):
                    paired=[(endpoints[policy,seed,cap,budget],endpoints[comparator,seed,cap,budget])
                            for seed,setting_cap,setting_budget in settings if (setting_cap,setting_budget)==(cap,budget)]
                    deltas=[a['best_speedup']-b['best_speedup'] for a,b in paired]
                    rows.append(dict(workload=workload,policy=policy,comparator=comparator,
                        area_delta_lut4_cap=cap,budget=budget,paired_seeds=len(paired),
                        mean_speedup_difference=statistics.mean(deltas),
                        mean_regret_reduction=statistics.mean(b['regret']-a['regret'] for a,b in paired),
                        mean_target_seconds_difference=statistics.mean(a['target_measurement_seconds']-b['target_measurement_seconds'] for a,b in paired),
                        seed_wins=sum(d>0 for d in deltas),seed_ties=sum(d==0 for d in deltas),seed_losses=sum(d<0 for d in deltas)))
    aggregate=[]
    keys=sorted({(r['policy'],r['comparator'],r['area_delta_lut4_cap'],r['budget']) for r in rows})
    for policy,comparator,cap,budget in keys:
        matched=[r for r in rows if (r['policy'],r['comparator'],r['area_delta_lut4_cap'],r['budget'])==(policy,comparator,cap,budget)]
        c.require(len(matched)==len(reports), 'Workload missing from paired aggregate')
        deltas=[r['mean_speedup_difference'] for r in matched]
        aggregate.append(dict(policy=policy,comparator=comparator,area_delta_lut4_cap=cap,budget=budget,
            independent_workloads=len(matched),mean_workload_speedup_difference=statistics.mean(deltas),
            mean_workload_regret_reduction=statistics.mean(r['mean_regret_reduction'] for r in matched),
            mean_workload_target_seconds_difference=statistics.mean(r['mean_target_seconds_difference'] for r in matched),
            workload_mean_wins=sum(d>0 for d in deltas),workload_mean_ties=sum(d==0 for d in deltas),workload_mean_losses=sum(d<0 for d in deltas)))
    return dict(independent_test_workloads=len(reports), workload_reports=sorted(reports),
        per_workload=rows,aggregate=aggregate,
        independent_unit='workload/source family',seed_repetitions_are_independent=False,
        note='Per-workload reports preserve paired seeds, constraints, evaluation counts, time and oracle regret. No seed-based generalization confidence interval.')


def verify_predictions(root, history):
    """Refit from authenticated historical evidence without target outcomes."""
    from . import budgeted_selection as model
    root=Path(root); protocol=c.unseal(root/'protocol.json')
    public=c.unseal(root/'public.json')
    c.require(all(r['workload_group']!=protocol['target_workload'] and
                  r['benchmark']!=public[0]['benchmark'] for r in history), 'Target workload in refit history')
    families={family(r['formula']) for r in public}
    training=[r for r in history if family(r['formula']) not in families]
    c.require(training==c.unseal(root/'history.json'), 'Authenticated historical fitting rows differ')
    c.require([r['candidate_id'] for r in training]==protocol['historical_training_ids'], 'Historical training IDs differ')
    c.require([r['candidate_id'] for r in history if family(r['formula']) in families]==protocol['excluded_related_ids'],
              'Related-family exclusions differ')
    frozen=c.unseal(root/'predictions.json')
    c.require([r['seed'] for r in frozen]==protocol['seeds'], 'Frozen prediction seeds differ')
    for row in frozen:
        derived=model.zero_shot(training,public,row['seed'])
        c.require(model.stable(derived)==model.stable(row), 'Exact historical-only prediction refit differs')
    return dict(historical_available_rows=len(history),historical_fit_rows=len(training),
                seeds=protocol['seeds'],exact_prediction_refit=True,target_outcomes_used=0)


def evaluate(root, target_roots, *, history_roots=DEFAULT_HISTORY, verify=False):
    from . import budgeted_selection as model
    root=Path(root); cohort=c.unseal(root/'cohort.json')
    c.require(cohort['schema']==SCHEMA and cohort['target_labels_read']==0, 'Invalid cohort protocol')
    for name,digest in cohort['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Frozen campaign source changed: '+name)
    supplied={c.unseal(Path(p)/'plan.json')['context_id']:Path(p).resolve() for p in target_roots}
    c.require(set(supplied)=={r['context_id'] for r in cohort['targets'].values()}, 'All and only frozen target contexts required')
    history,_,history_costs=history_rows(history_roots)
    c.require(history_costs==cohort['historical_costs'], 'Authenticated historical collection costs differ')
    reports, audits, refits={},{},{}
    for name,entry in cohort['targets'].items():
        c.require(c.sha(root/entry['baseline_snapshot'])==entry['baseline_snapshot_sha256'], 'Frozen baseline snapshot changed')
        destination=root/name
        for artifact,digest in entry['selection_artifacts'].items():
            c.require(c.sha(destination/artifact)==digest, 'Frozen selection artifact changed')
        # Historical refit and prediction authentication do not open any labels.
        refits[name]=verify_predictions(destination,history)
        before=c.unseal(root/entry['baseline_snapshot']); public=c.unseal(destination/'public.json')
        rows,audits[name]=outcomes(supplied[entry['context_id']],before,public)
        reports[name]=model.evaluate(destination,rows,verify=verify)
    report=dict(cohort_sha256=c.sha(root/'cohort.json'),targets=reports,audits=audits,prediction_refits=refits,
        paired=paired_summary(reports),historical_costs=cohort['historical_costs'],
        new_native_jobs=0,oracle='Measured complete frozen candidate pool, including failed attempts as nonselectable; baseline always available.',
        broad_generalization_established=False)
    if verify:
        c.require(model.stable(report)==model.stable(c.unseal(root/'campaign-report.json')), 'Campaign replay differs')
    else:
        c.require(not (root/'campaign-report.json').exists(), 'Preserve prior campaign report')
        c.seal(root/'campaign-report.json',report)
    return report


def export_corpus(root, target_roots, output, *, history_roots=DEFAULT_HISTORY):
    """Export consumed measured data after successful campaign verification.

    This is an analysis/training artifact for a later experiment, never an
    input to the campaign that produced these target outcomes. Failed native
    attempts remain separate because they have no verified performance label.
    """
    from .prospective_selection import PUBLIC_KEYS
    root,output=Path(root),Path(output)
    c.require(not output.exists(), 'Preserve prior corpus export')
    c.require((root/'campaign-report.json').exists(), 'Evaluate campaign before exporting consumed labels')
    report=evaluate(root,target_roots,history_roots=history_roots,verify=True)
    cohort=c.unseal(root/'cohort.json'); history,contexts,costs=history_rows(history_roots)
    supplied={c.unseal(Path(p)/'plan.json')['context_id']:Path(p).resolve() for p in target_roots}
    rows=list(history); failures=[]
    for name,entry in cohort['targets'].items():
        public=c.unseal(root/name/'public.json'); before=c.unseal(root/entry['baseline_snapshot'])
        target,_=outcomes(supplied[entry['context_id']],before,public)
        contexts.update(c.unseal(root/name/'protocol.json')['contexts'])
        for row in target:
            enriched=dict(row,workload_group=name,candidate_family=family(row['formula']))
            (failures if row.get('status','success')=='failed' else rows).append(enriched)
    fields=(*PUBLIC_KEYS,'workload_group','candidate_family','speedup','area','area_cap',
        'area_delta_lut4','routed_fmax_min_mhz','device_fits','timing_feasible','correctness_verified',
        'measurement_source','measurement_seconds','baseline_cycles','candidate_cycles',
        'baseline_period_ns','candidate_period_ns')
    canonical=[{key:row[key] for key in fields} for row in rows]
    c.require(len({r['candidate_id'] for r in canonical+failures})==len(canonical)+len(failures),
              'Duplicate exported sample identity')
    result=dict(schema='isaforge-consumed-campaign-corpus-v1',scope='Consumed-data analysis; future protocols must declare new held-out workloads.',
        rows=canonical,failed_attempts=failures,contexts=contexts,
        successful_labels=len(canonical),independent_workload_groups=sorted({r['workload_group'] for r in canonical}),
        historical_costs=costs,campaign_audits=report['audits'],cohort_sha256=c.sha(root/'cohort.json'),
        campaign_report_sha256=c.sha(root/'campaign-report.json'),new_native_jobs=0)
    output.parent.mkdir(parents=True,exist_ok=True); c.seal(output,result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','evaluate','replay','export'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--target-root',type=Path,required=True,action='append')
    parser.add_argument('--history-root',type=Path,action='append')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.command=='freeze':
        result=freeze(args.target_root,args.root,history_roots=args.history_root or DEFAULT_HISTORY)
        print(dict(target_labels_read=result['target_labels_read'],target_workloads=list(result['targets'])))
    elif args.command=='export':
        c.require(args.output is not None, '--output required for consumed corpus export')
        result=export_corpus(args.root,args.target_root,args.output,history_roots=args.history_root or DEFAULT_HISTORY)
        print(dict(new_native_jobs=0,successful_labels=result['successful_labels'],failed_attempts=len(result['failed_attempts'])))
    else:
        result=evaluate(args.root,args.target_root,history_roots=args.history_root or DEFAULT_HISTORY,
                        verify=args.command=='replay')
        print(dict(new_native_jobs=0,target_workloads=list(result['targets'])))


if __name__=='__main__': main()
