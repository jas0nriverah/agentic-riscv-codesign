"""Real matched iCE40 place-and-route with an explicit external-memory boundary."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_pins(chipdb: str, package: str) -> tuple[dict[tuple[int, int, int], str], set[tuple[int, int, int]]]:
    """Read package and dedicated global-clock locations from IceStorm's database."""
    section = ''
    pins = {}
    globals_ = set()
    for raw in chipdb.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line: continue
        if line.startswith('.'):
            section = line
        elif section == f'.pins {package}':
            pin, x, y, z = line.split()
            pins[(int(x), int(y), int(z))] = pin
        elif section == '.gbufpin':
            x, y, z, _ = line.split()
            globals_.add((int(x), int(y), int(z)))
    if not pins: raise ValueError(f'package {package} missing from chip database')
    return pins, globals_ & pins.keys()


def port_signature(netlist: dict, top: str = 'core_top') -> dict[str, str]:
    signature = {}
    for name, port in netlist['modules'][top]['ports'].items():
        for bit in range(len(port['bits'])):
            scalar = name if len(port['bits']) == 1 else f'{name}[{bit+port.get("offset", 0)}]'
            signature[scalar] = port['direction']
    return signature


def validate_memory_boundary(signature: dict[str, str], boundary: str) -> None:
    if boundary == 'onchip_initialized_memory':
        inputs = {name for name, direction in signature.items() if direction == 'input'}
        if inputs != {'clk', 'resetn'} or any(name.startswith('mem_') for name in signature):
            raise ValueError('closed-memory SoC must expose only clk/resetn inputs and no external memory interface')


def placement_pins(placed: dict, pin_locations: dict, signature: dict[str, str]) -> dict[str, str]:
    """Match packed SB_IO PACKAGE_PIN nets to top ports and physical locations."""
    modules = placed['modules']
    if len(modules) != 1: raise ValueError('expected one packed placement module')
    module = next(iter(modules.values()))
    nets = {}
    for name, port in module['ports'].items():
        for i, bit in enumerate(port['bits']):
            scalar = name if len(port['bits']) == 1 else f'{name}[{i+port.get("offset", 0)}]'
            if bit in nets: raise ValueError('ambiguous top-level package net')
            nets[bit] = scalar
    mapping = {}
    for cell in module['cells'].values():
        if cell['type'] != 'SB_IO': continue
        package_net = cell['connections']['PACKAGE_PIN']
        if len(package_net) != 1 or package_net[0] not in nets:
            raise ValueError('unmatched SB_IO package pin')
        name = nets[package_net[0]]
        bel = cell['attributes'].get('NEXTPNR_BEL', '')
        location = re.fullmatch(r'X(\d+)/Y(\d+)/io(\d+)', bel)
        if not location: raise ValueError('missing physical I/O placement')
        pin = pin_locations.get(tuple(map(int, location.groups())))
        if pin is None: raise ValueError('I/O location absent from chosen package')
        if name in mapping or pin in mapping.values(): raise ValueError('duplicate physical I/O constraint')
        mapping[name] = pin
    if set(mapping) != set(signature): raise ValueError('I/O constraints do not cover all scalar ports')
    return mapping


def timing_summary(report: dict, frequency: float) -> dict:
    fmax = report.get('fmax', {})
    if not fmax: raise ValueError('routed report contains no synchronous clock timing')
    clocks = {}
    for clock, metrics in fmax.items():
        achieved = metrics.get('achieved')
        constraint = metrics.get('constraint')
        if not isinstance(achieved, (int, float)) or not math.isfinite(achieved) or achieved <= 0:
            raise ValueError('invalid routed clock frequency')
        if not isinstance(constraint, (int, float)) or not math.isclose(constraint, frequency):
            raise ValueError('routed timing constraint differs from protocol')
        clocks[clock] = {'achieved_mhz': achieved, 'constraint_mhz': constraint,
                         'internal_timing_pass': achieved >= constraint}
    utilization = report.get('utilization', {})
    if not utilization: raise ValueError('missing routed resource utilization')
    fits = all(0 <= item['used'] <= item['available'] for item in utilization.values())
    paths = []
    for path in report.get('critical_paths', []):
        paths.append({'from': path['from'], 'to': path['to'],
                      'delay_ns': sum(segment['delay'] for segment in path['path'])})
    return {'clocks': clocks, 'limiting_internal_fmax_mhz': min(v['achieved_mhz'] for v in clocks.values()),
            'internal_timing_pass': all(v['internal_timing_pass'] for v in clocks.values()),
            'device_fits': fits, 'utilization': utilization, 'critical_path_summaries': paths}


def _run(command: list[str], directory: Path, name: str, timeout: float) -> dict:
    console = directory / f'{name}-console.log'
    started = time.perf_counter()
    with console.open('w') as stream:
        run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    return {'command': command, 'returncode': run.returncode,
            'wall_seconds': time.perf_counter()-started, 'console_log': str(console.resolve()),
            'console_sha256': _sha(console)}


def run_routing(synthesis_dir: str | Path, output_dir: str | Path, chipdb: str | Path,
                seeds: tuple[int, ...] = (1, 2, 3), frequency: float = 12.,
                tool: str = 'nextpnr-ice40', timeout: float = 180., top: str = 'core_top',
                configurations: tuple[str, str] = ('baseline', 'both-combinational'),
                memory_boundary: str = 'external_native_memory') -> dict:
    if not seeds or len(set(seeds)) != len(seeds) or any(seed < 0 for seed in seeds):
        raise ValueError('specify distinct nonnegative routing seeds')
    if not math.isfinite(frequency) or frequency <= 0: raise ValueError('frequency must be positive')
    if len(configurations) != 2 or len(set(configurations)) != 2 or any(
            not re.fullmatch(r'[A-Za-z0-9_-]+', name) for name in configurations):
        raise ValueError('specify two distinct safe synthesis configuration names')
    if memory_boundary not in ('external_native_memory', 'onchip_initialized_memory'):
        raise ValueError('unknown memory timing boundary')
    executable = shutil.which(tool)
    if not executable: raise ValueError(f'missing place-and-route tool {tool}')
    root, output = Path(synthesis_dir).resolve(), Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    baseline_name, custom_name = configurations
    sources = {name: root / name / 'ice40-netlist.json' for name in configurations}
    signatures = {name: port_signature(json.loads(path.read_text()), top) for name, path in sources.items()}
    if signatures[baseline_name] != signatures[custom_name]:
        raise ValueError('baseline and custom core interfaces differ')
    if signatures[baseline_name].get('clk') != 'input': raise ValueError('DUT must expose scalar clock input clk')
    validate_memory_boundary(signatures[baseline_name], memory_boundary)
    source_hashes = {name: _sha(path) for name, path in sources.items()}
    database = Path(chipdb).resolve()
    locations, global_locations = package_pins(database.read_text(), 'ct256')
    if not global_locations: raise ValueError('package has no dedicated clock input')
    # A dedicated global-clock pin is fixed before baseline placement. Remaining
    # pin assignments come from one baseline-only seed-0 placement and are then
    # frozen for every measured design/seed; no custom timing guides selection.
    clock_location = min(global_locations)
    bootstrap = output / 'bootstrap'
    bootstrap.mkdir(exist_ok=True)
    clock_pcf = bootstrap / 'clock.pcf'
    clock_pcf.write_text(f'set_io clk {locations[clock_location]}\n')
    placed_path = bootstrap / 'placed.json'
    initial = [executable, '--hx8k', '--package', 'ct256', '--json', str(sources[baseline_name]),
               '--pcf', str(clock_pcf), '--pcf-allow-unconstrained', '--freq', str(frequency),
               '--seed', '0', '--threads', '1', '--no-route', '--write', str(placed_path),
               '--log', str(bootstrap/'placement.log')]
    initial_result = _run(initial, bootstrap, 'placement', timeout)
    if initial_result['returncode'] != 0: raise ValueError('baseline pin bootstrap placement failed; inspect retained logs')
    mapping = placement_pins(json.loads(placed_path.read_text()), locations, signatures[baseline_name])
    pcf = output / 'common.pcf'
    pcf.write_text(''.join(f'set_io {name} {pin}\n' for name, pin in sorted(mapping.items())))
    version = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True)
    protocol = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'device': 'iCE40HX8K',
                'top_module': top, 'configurations': list(configurations), 'memory_boundary': memory_boundary,
                'package': 'CT256', 'target_frequency_mhz': frequency, 'seeds': list(seeds),
                'pin_selection': 'dedicated clock pin plus baseline-only seed-0 placement; fixed for all measured runs',
                'clock_pin': mapping['clk'], 'scalar_io_count': len(mapping), 'pin_mapping': mapping,
                'pcf_sha256': _sha(pcf), 'chipdb_path': str(database), 'chipdb_sha256': _sha(database),
                'netlist_paths': {name: str(path) for name, path in sources.items()}, 'netlist_sha256': source_hashes,
                'nextpnr_version_output': (version.stdout+version.stderr).strip(),
                'nextpnr_binary_sha256': _sha(Path(executable)),
                'runner_source_sha256': _sha(Path(__file__)), 'bootstrap': initial_result,
                'timing_scope': ('all synchronous SoC paths including on-chip instruction/data RAM; reset/status I/O remain asynchronous'
                                 if memory_boundary == 'onchip_initialized_memory' else
                                 'internal synchronous core paths only; no external memory/device input/output delay constraints')}
    # Retain the exact runner source used even if the repository gains a new
    # version later, so its protocol hash remains independently checkable.
    (output/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    (output/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    runs = []
    for seed in seeds:
        for name, source in sources.items():
            if _sha(source) != source_hashes[name]: raise ValueError('synthesis netlist changed during matched routing')
            directory = output / f'{name}-seed{seed}'
            directory.mkdir(exist_ok=True)
            report_path, asc = directory/'report.json', directory/'routed.asc'
            command = [executable, '--hx8k', '--package', 'ct256', '--json', str(source), '--pcf', str(pcf),
                       '--freq', str(frequency), '--seed', str(seed), '--threads', '1',
                       '--report', str(report_path), '--detailed-timing-report', '--asc', str(asc),
                       '--log', str(directory/'routing.log')]
            result = {'configuration': name, 'seed': seed, **_run(command, directory, 'routing', timeout)}
            result['status'] = 'failed'
            if result['returncode'] == 0 and report_path.exists() and asc.exists():
                result.update(timing_summary(json.loads(report_path.read_text()), frequency))
                result.update(report_path=str(report_path), report_sha256=_sha(report_path),
                              routed_asc_path=str(asc), routed_asc_sha256=_sha(asc))
                unconstrained = 'is unconstrained in PCF' in (directory/'routing.log').read_text()
                result['all_io_constrained'] = not unconstrained
                if result['device_fits'] and result['internal_timing_pass'] and not unconstrained:
                    result['status'] = 'routed_and_internal_timing_passed'
            runs.append(result)
            (output/'runs.json').write_text(json.dumps(runs, indent=2)+'\n')
    summaries = {}
    for name in sources:
        selected = [r for r in runs if r['configuration'] == name]
        values = [r['limiting_internal_fmax_mhz'] for r in selected if r['status'] == 'routed_and_internal_timing_passed']
        summaries[name] = {'successful_seed_count': len(values), 'required_seed_count': len(seeds),
                           'min_internal_fmax_mhz': min(values) if values else None,
                           'median_internal_fmax_mhz': statistics.median(values) if values else None,
                           'max_internal_fmax_mhz': max(values) if values else None}
    limitations = ['No physical FPGA board, power, temperature, or silicon measurement.',
                   'Register-to-register timing is estimated by nextpnr after actual routing.',
                   'Reset/status input/output arrival, electrical load and required-time constraints are absent.',
                   'Three routing seeds describe placement sensitivity, not a statistical population estimate.']
    if memory_boundary == 'external_native_memory':
        limitations += ['External RAM/peripheral timing is not modeled or constrained.',
                        'Simulation uses zero-wait external RAM; multiplying cycles by Fmax does not establish complete-system time.']
    else:
        limitations += ['Cycle-derived elapsed time at routed Fmax is a timing-model estimate, not a measured board runtime.',
                        'Reset release must be synchronized and status observation designed appropriately in a physical implementation.']
    summary = {**protocol, 'runs': runs, 'summary_by_configuration': summaries,
               'all_runs_passed': all(r['status'] == 'routed_and_internal_timing_passed' for r in runs),
               'limitations': limitations}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthesis-dir', default='generated/core/synthesis')
    parser.add_argument('--output-dir', default='generated/core/routing')
    parser.add_argument('--chipdb', required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[1, 2, 3])
    parser.add_argument('--frequency', type=float, default=12.)
    parser.add_argument('--nextpnr', default='nextpnr-ice40')
    parser.add_argument('--top', default='core_top')
    parser.add_argument('--configurations', nargs=2, default=['baseline', 'both-combinational'])
    parser.add_argument('--memory-boundary', choices=['external_native_memory', 'onchip_initialized_memory'],
                        default='external_native_memory')
    args = parser.parse_args(argv)
    report = run_routing(args.synthesis_dir, args.output_dir, args.chipdb,
                         tuple(args.seeds), args.frequency, args.nextpnr, top=args.top,
                         configurations=tuple(args.configurations), memory_boundary=args.memory_boundary)
    print(json.dumps({'all_runs_passed': report['all_runs_passed'],
                      'summary_by_configuration': report['summary_by_configuration']}, indent=2))
    return 0 if report['all_runs_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
