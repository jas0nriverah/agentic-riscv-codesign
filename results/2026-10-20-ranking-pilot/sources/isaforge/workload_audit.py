"""Recount automatic-workload evidence and export measured corpus rows.

Read-only audit: no native subprocesses, model fitting, or new labels.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import assembly_lowering as lowering
from . import codesign as c
from . import speedup_corpus as corpus
from .workload_experiment import validate_execution, verify_cache


def audit(root):
    root = Path(root).resolve()
    plan = c.unseal(root / 'plan.json')
    c.require(c.digest({k: v for k, v in plan.items() if k != 'context_id'}) == plan['context_id'], 'Invalid context')
    for name, expected in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT / name) == expected, 'Source binding differs: ' + name)
    for name, expected in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == expected, 'Input checksum mismatch')
    commands = c.unseal(root / 'commands.json')
    for command in commands:
        c.require(c.sha(root / command['log']) == command['log_sha256'], 'Native log changed')
        c.require(command['returncode'] == command['expected_returncode'] and command['failure'] is None,
                  'Failed command in completed experiment')
    discovery = verify_cache(root / 'discovery', 'discovery.json')
    c.require(discovery['context_id'] == plan['context_id'], 'Discovery context mismatch')
    profile = c.read(root / discovery['profile'])
    c.require(profile['markers'] == 2 and sum(profile['region_counts'].values()) + 1 == profile['words'][3], 'Trace/counter mismatch')
    base_image = root / discovery['baseline_image']
    source_folder = base_image.parent.parent
    c.require(c.sha(source_folder / 'original/firmware.hex') == c.sha(base_image), 'Baseline assembly changed')
    marked, sites = lowering.mark_assembly((source_folder / 'program.s').read_text())
    c.require(marked == (source_folder / 'marked.S').read_text(), 'Assembly markers differ')
    site_map = lowering.map_sites(sites, (base_image.parent / 'symbols.txt').read_text())
    program = lowering.read_program((base_image.parent / 'disassembly.txt').read_text())
    regenerated = lowering.extract(program, profile, site_map, plan['pool_size'])
    c.require(len(discovery['pool']) == plan['pool_size'], 'Incomplete frozen pool')
    baseline = verify_cache(root / 'measurements/baseline', 'measurement.json')
    records = [baseline]
    for derived, candidate in zip(regenerated['pool'], discovery['pool']):
        c.require(all(candidate[k] == v for k, v in derived.items()), 'Re-extracted candidate differs')
        c.require(lowering.verify_lowering(candidate, program, discovery['block_starts']) == candidate['lowering_check'], 'Block check differs')
        c.require(lowering.lower(marked, candidate) == (root / candidate['assembly']).read_text(), 'Lowered assembly differs')
        records.append(verify_cache(root / 'measurements' / candidate['name'], 'measurement.json'))
    observations = []
    for record in records:
        name = record['name']; custom = name != 'baseline'
        candidate = next((p for p in discovery['pool'] if p['name'] == name), None)
        expected_id = c.digest([plan['context_id'], c.sha(root / 'discovery/discovery.json'), name])
        c.require(record['evaluation_id'] == expected_id and record['context_id'] == plan['context_id'], 'Evaluation context mismatch')
        folder = root / 'measurements' / name
        sims = [folder / p for p in record['artifacts'] if p.endswith('/simulation/simulation.json')]
        c.require(sims, 'Missing raw processor output')
        attempt = sims[-1].parent.parent
        performance = validate_execution(c.read(sims[-1]), candidate)
        c.require(performance == record['performance'], 'Cycle/correctness record differs')
        resources = c.validate_netlist(c.read(attempt / 'synthesis/ice40-netlist.json'))
        c.require(resources == record['resources'], 'Resource recount differs')
        routes = [{'seed': seed, **c.timing_summary(c.read(attempt / f'synthesis/route-{seed}.json'), 12.0)}
                  for seed in (1, 2, 3)]
        c.require(routes == record['routes'], 'Timing recount differs')
        speedup = baseline['performance']['cycles'] / performance['cycles']
        c.require(speedup == record['speedup'], 'Speedup arithmetic differs')
        c.require(record['added_lut4'] == resources['lut4_count'] - baseline['resources']['lut4_count'], 'Area delta differs')
        c.require(record['timing_feasible'] == all(r['internal_timing_pass'] and r['device_fits'] for r in routes), 'Feasibility differs')
        c.require(record['firmware_sha256'] == c.sha(root / record['firmware_image']), 'Firmware changed')
        if custom:
            isa = corpus.validate_isa((root / record['firmware_image']).parent.joinpath('disassembly.txt').read_text())
            c.require(isa['custom_static_sites'] == len(candidate['occurrences']), 'Static custom count differs')
            c.require(baseline['performance']['instructions'] - performance['instructions'] == candidate['expected_instruction_reduction'], 'Instruction savings differ')
            stock = validate_execution(c.read(attempt / 'stock-on-extension/simulation.json'))
            c.require(stock == baseline['performance'], 'Stock program control differs')
            trap = str((attempt / 'illegal-on-baseline/simulation.json').relative_to(root))
            c.require(any(r['log'] == trap and r['returncode'] == 6 and r['expected_returncode'] == 6 for r in commands), 'Negative trap control missing')
            c.require(record['features'] == candidate['features'] and record['formula'] == candidate['formula'], 'Feature/label join differs')
        else:
            c.require(performance == validate_execution(profile), 'Profile/stock execution differs')
        fmax = [r['limiting_internal_fmax_mhz'] for r in routes]
        baseline_fmax = [r['limiting_internal_fmax_mhz'] for r in baseline['routes']]
        observations.append({'name': name, 'formula': record['formula'], 'cycles': performance['cycles'],
                             'instructions': performance['instructions'], 'speedup': speedup,
                             'cycle_reduction_percent': 100 * (1 - 1 / speedup),
                             'lut4': resources['lut4_count'], 'added_lut4': record['added_lut4'],
                             'flip_flops': resources['flip_flop_count'], 'carry': resources['carry_count'],
                             'ram4k': resources['memory_blocks'], 'routed_fmax_mhz': fmax,
                             'conditional_fmax_speedup': [speedup * f / b for f, b in zip(fmax, baseline_fmax)],
                             'timing_feasible': record['timing_feasible'], 'correctness_passed': True})
    return {'context_id': plan['context_id'], 'workload': plan['workload'], 'observations': observations,
            'raw_formulas': discovery['raw_formula_count'], 'executable_formulas': discovery['executable_formula_count'],
            'native_commands': len(commands), 'failed_native_commands': sum(r['failure'] is not None for r in commands),
            'native_seconds': sum(r['elapsed_seconds'] for r in commands),
            'audit_scope': 'Hash verification; re-extracted and re-lowered candidates; sampled block checks; raw processor counters/controls; recounted netlists and all routes. Reuses the original extractor, integer interpreter and resource/timing parsers.'}


def import_automatic(root):
    root = Path(root).resolve()
    checked = audit(root)
    plan = c.unseal(root / 'plan.json')
    processor = {'core': plan['core_commit'], 'isa': plan['configuration']['isa'],
                 'ram_bytes': plan['configuration']['ram_bytes'], 'clock_mhz': 12.0, 'pcpi_wait_cycles': 1,
                 'compiler_sha256': plan['tools']['gcc']['sha256'],
                 'hardware': {p: h for p, h in plan['source_bindings'].items() if p in
                              ('hardware/soc_top.v', 'hardware/pcpi_single.v', 'hardware/soc_start.S', 'hardware/soc_link.ld')}}
    processor_id = c.digest(processor)
    inputs = {'source_sha256': plan['inputs']['program.c'], 'harness_sha256': plan['inputs']['embench_firmware.c'],
              'cpu_mhz_repetition_scale': 1, 'warmup_repetitions': 1, 'inputs': 'Unmodified upstream initialisation and self-check'}
    baseline = c.unseal(root / 'measurements/baseline/measurement.json')
    rows = []
    for candidate in c.unseal(root / 'discovery/discovery.json')['pool']:
        record = c.unseal(root / 'measurements' / candidate['name'] / 'measurement.json')
        workload = 'embench-' + plan['workload']
        identity = {'workload': workload, 'source_revision': plan['embench_commit'], 'input_id': c.digest(inputs),
                    'processor_id': processor_id, 'formula': record['formula'],
                    'firmware_sha256': record['firmware_sha256'], 'measurement_context_id': plan['context_id'],
                    'implementation_sha256': c.digest(c.generate_rtl(record['formula']))}
        rows.append({**candidate['features'], 'name': candidate['name'], 'candidate_id': c.digest(identity),
                     'benchmark': workload + ':' + plan['context_id'], 'formula': record['formula'],
                     'workload': workload, 'workload_group': workload, 'processor_id': processor_id,
                     'sample_identity': identity, 'input_configuration': inputs, 'label_kind': corpus.LABEL_KIND,
                     'candidate_family': corpus.family(record['formula']), 'measurement_source': 'synthesis_estimate',
                     'measurement_detail': 'Measured whole-benchmark RTL cycles and integrated FPGA synthesis/routing at common 12 MHz.',
                     'baseline_cycles': baseline['performance']['cycles'], 'candidate_cycles': record['performance']['cycles'],
                     'baseline_period_ns': 1000 / 12, 'candidate_period_ns': 1000 / 12,
                     'speedup': record['speedup'], 'area': record['resources']['lut4_count'],
                     'area_cap': baseline['resources']['lut4_count'] + 128, 'timing_feasible': record['timing_feasible'],
                     'correctness_verified': True, 'custom_execution_count': record['performance']['custom_instructions'],
                     'measurement_seconds': record['elapsed_seconds'], 'evaluation_id': record['evaluation_id'],
                     'feature_provenance': 'Actual RV32I PicoRV32 execution profile and legally lowered disjoint occurrences; no measured cost or speedup in features.'})
    return {'schema': 'isaforge-measured-speedup-corpus-v1', 'processor_contexts': {processor_id: processor},
            'source_contexts': [plan['context_id']], 'rows': rows, 'readiness': corpus.readiness(rows),
            'audit': checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--crc32-root', type=Path)
    args = parser.parse_args(argv)
    result = import_automatic(args.root)
    if args.crc32_root:
        crc = corpus.import_crc32(args.crc32_root)
        c.require(result['processor_contexts'] == crc['processor_contexts'], 'Processor context differs')
        result['rows'] += crc['rows']
        result['source_contexts'] += crc['source_contexts']
        result['readiness'] = corpus.readiness(result['rows'])
        result['limitations'] = ['Historical CRC32 features use RV32IM discovery; aha-mont64 features use the actual RV32I program. Reprofile CRC32 before uniform target-ISA model evaluation.',
                                 'Two workload groups are insufficient for the predeclared cross-workload evaluation gate.']
    c.seal(args.output, result)
    print(result['readiness'])


if __name__ == '__main__': main()
