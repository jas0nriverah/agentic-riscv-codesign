"""Recount the CRC32 experiment from retained raw evidence, without native jobs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import statistics

from . import codesign as c
from .core_routing import timing_summary
from .soc_experiment import validate_netlist


def stable(value):
    """Model replay excludes wall-clock bookkeeping, never numerical outcomes."""
    if isinstance(value, list): return [stable(v) for v in value]
    if isinstance(value, dict):
        return {k:stable(v) for k,v in value.items() if k != 'fit_and_predict_seconds'}
    return value


def audit(root, *, replay=False):
    root = Path(root).resolve()
    plan = c.read(root/'plan.json')
    header = copy.deepcopy(plan)
    context = header.pop('context_id'); candidates = header.pop('candidates')
    c.require(c.digest(header) == context and candidates == c.public_rows(context), 'Plan/feature identity changed')
    for name, expected in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name) == expected, 'Source binding differs: '+name)
    for name, expected in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name) == expected, 'Input changed: '+name)
    commands = c.unseal(root/'commands.json')
    phases = defaultdict(float)
    for command in commands:
        log = root/command['log']
        c.require(c.sha(log) == command['log_sha256'], 'Command log changed')
        c.require(command['returncode'] == command['expected_returncode'] and command['failure'] is None, 'Failed command in completed experiment')
        name = log.name
        phase = ('routing' if name.startswith('route-') else 'synthesis' if name == 'synthesis.log'
                 else 'native_build' if name == 'build.log' else 'processor_simulation' if name == 'simulation.json'
                 else 'formal_proof' if name == 'equivalence.log' else 'compilation_and_other_checks')
        phases[phase] += command['elapsed_seconds']
    records = {}
    for path in sorted((root/'measurements').glob('*/measurement.json')):
        record = c.unseal(path)
        for name, expected in record['artifacts'].items():
            c.require(c.sha(path.parent/name) == expected, 'Evidence changed: '+name)
        attempt = (root/record['firmware_image']).parent.parent
        rtl = (attempt/'candidate.v').read_text()
        c.require(c.digest([context, record['name'], rtl]) == record['evaluation_id'] == path.parent.name, 'Implementation identity changed')
        c.require(c.sha(attempt/'candidate.v') == record['implementation_sha256'], 'RTL identity changed')
        custom = record['name'] != 'baseline'
        formula = c.CANDIDATES[record['name']][0] if custom else 'add(in0,in1)'
        c.require((attempt/'reference.v').read_text() == c.generate_rtl(formula,'reference'), 'Reference changed')
        c.require('Equivalence successfully proven' in (attempt/'equivalence.log').read_text(), 'No successful proof')
        c.require('228 comparisons passed' in (attempt/'integer-oracle/verification.log').read_text(), 'Missing integer-oracle check')
        measured = c.validate_execution(c.read(attempt/'simulation/simulation.json'), custom)
        c.require(measured == record['performance'], 'Performance differs from raw execution')
        resources = validate_netlist(c.read(attempt/'synthesis/ice40-netlist.json'))
        c.require(resources == record['resources'], 'Resource recount differs')
        for route in record['routes']:
            c.require(route == {'seed':route['seed'], **timing_summary(c.read(attempt/f'synthesis/route-{route["seed"]}.json'),12.0)}, 'Timing recount differs')
        c.require([r['seed'] for r in record['routes']] == [1,2,3], 'Missing declared routing seed')
        if custom:
            types = Counter(cell['type'] for cell in c.read(attempt/'unit/unit.json')['modules']['candidate']['cells'].values())
            c.require(dict(sorted(types.items())) == record['unit_resources']['cell_types'], 'Unit resource recount differs')
            c.require('processor trap' in (attempt/'illegal-on-baseline/simulation.json').read_text(), 'Missing illegal-instruction control')
        records[record['evaluation_id']] = record
    original = {}
    for name in ('baseline', *c.CANDIDATES):
        formula = c.CANDIDATES[name][0] if name != 'baseline' else 'add(in0,in1)'
        identity = c.digest([context,name,c.generate_rtl(formula)])
        c.require(identity in records, 'Incomplete six-candidate pool')
        original[name] = records[identity]
    baseline = original['baseline']
    baseline_performance = baseline['performance']
    for record in records.values():
        attempt = (root/record['firmware_image']).parent.parent
        control = 'source-control-simulation' if record['name'] == 'baseline' else 'stock-on-extension'
        measured = c.validate_execution(c.read(attempt/control/'simulation.json'), False)
        c.require(all(measured[k] == baseline_performance[k] for k in ('cycles','instructions','full_checksum','benchmark_result')), 'Baseline control changed')
    observations = c.read(root/'observations.json')
    c.require(len(observations) == len(candidates), 'Incomplete observations')
    hardware = []
    for row in observations:
        record = original[row['name']]
        c.require(row['evaluation_id'] == record['evaluation_id'], 'Observation implementation changed')
        c.require(row['speedup'] == baseline_performance['cycles']/record['performance']['cycles'], 'Wrong speedup label')
        c.require(row['area'] == record['resources']['lut4_count'], 'Wrong area label')
        for key in c.FEATURE_COLUMNS:
            c.require(row[key] == next(p for p in candidates if p['candidate_id'] == row['candidate_id'])[key], 'Feature label leakage/change')
        hardware.append({'name':row['name'], 'cycles':record['performance']['cycles'], 'speedup':row['speedup'],
                         'cycle_reduction_percent':100*(1-1/row['speedup']), 'lut4':row['area'],
                         'added_lut4':row['area']-baseline['resources']['lut4_count'],
                         'flip_flops':record['resources']['flip_flop_count'], 'carry_cells':record['resources']['carry_count'],
                         'bram':record['resources']['memory_blocks'], 'unit_lut4':record['unit_resources']['lut4_count'],
                         'unit_carry':record['unit_resources']['carry_count'],
                         'fmax_mhz':[r['limiting_internal_fmax_mhz'] for r in record['routes']],
                         'conditional_fmax_speedups':[row['speedup']*r['limiting_internal_fmax_mhz']/b['limiting_internal_fmax_mhz']
                                                    for r,b in zip(record['routes'],baseline['routes'])],
                         'correct':record['performance']['self_check_passed'],
                         'handshakes':record['performance']['protocol_statistics']['pcpi_handshakes'],
                         'evaluation_seconds':record['elapsed_seconds']})
    report = c.read(root/'selection-report.json')
    if replay:
        repeated = c.comparison(candidates, observations, report['area_cap_integrated_lut4'])
        for key, value in repeated.items():
            c.require(stable(value) == stable(report[key]), 'Policy/model replay differs: '+key)
    groups = defaultdict(list)
    for row in report['results']: groups[row['policy'],row['budget']].append(row)
    policies = []
    for (policy,budget), values in sorted(groups.items()):
        c.require([r['seed'] for r in values] == [0,1,2,3,4], 'Missing search seed')
        policies.append({'policy':policy,'budget':budget,'seeds':len(values),
                         'mean_best_speedup':statistics.mean(r['best_speedup'] for r in values),
                         'mean_regret':statistics.mean(r['regret'] for r in values),
                         'oracle_hits':sum(abs(r['regret']) < 1e-12 for r in values),
                         'mean_charged_measurement_seconds':statistics.mean(r['measured_cost_seconds'] for r in values)})
    to_oracle = {}
    for policy in c.POLICIES:
        to_oracle[policy] = [min(r['budget'] for r in report['results'] if r['policy'] == policy and r['seed'] == seed and abs(r['regret']) < 1e-12)
                             for seed in range(5)]
    changed = {str(budget):sum(next(r for r in report['results'] if r['policy']=='active_learning' and r['seed']==seed and r['budget']==budget)['measured_candidate_ids'] !=
                                    next(r for r in report['results'] if r['policy']=='random' and r['seed']==seed and r['budget']==budget)['measured_candidate_ids']
                                    for seed in range(5)) for budget in range(1,7)}
    return {'context_id':context,'raw_records_recounted':len(records),'policy_replay_verified':replay,
            'baseline':{'cycles':baseline_performance['cycles'],'resources':baseline['resources'],
                        'fmax_mhz':[r['limiting_internal_fmax_mhz'] for r in baseline['routes']]},
            'hardware':hardware,'policies':policies,'queries_to_exact_oracle_by_seed':to_oracle,
            'learned_query_orders_different_from_random_out_of_five':changed,
            'native_commands':len(commands),'native_seconds':sum(r['elapsed_seconds'] for r in commands),
            'phase_seconds':dict(sorted(phases.items())),
            'live_selection':c.unseal(root/'live-selection.json'),
            'training_scope':'Paid within-CRC32 application-speedup observations only; zero historical speedup labels; no area predictor.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replay',action='store_true')
    args = p.parse_args(argv)
    result = audit(args.root,replay=args.replay)
    c.write(args.output,result)
    print(json.dumps({k:result[k] for k in ('raw_records_recounted','policy_replay_verified','native_commands','native_seconds')}))


if __name__ == '__main__': main()
