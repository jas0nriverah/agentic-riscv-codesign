"""Actual Yosys synthesis of isolated candidate datapaths.

Generic gate counts/levels and iCE40 mapped LUT counts are resource proxies;
neither is a physical area, clock period, or full-processor performance label.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .features import parse_formula
from .rtl import generate_rtl


def netlist_metrics(netlist: dict, module_name: str = 'candidate') -> dict:
    """Count mapped cells and longest combinational path in generic gate levels."""
    module = netlist['modules'][module_name]
    cells = module.get('cells', {})
    cell_types = dict(sorted(Counter(cell['type'] for cell in cells.values()).items()))
    drivers: dict[int, tuple[str, list[int | str]]] = {}
    inputs: set[int] = set()
    for port in module.get('ports', {}).values():
        if port['direction'] == 'input':
            inputs.update(bit for bit in port['bits'] if isinstance(bit, int))
    for name, cell in cells.items():
        input_bits = [bit for port, bits in cell['connections'].items()
                      if cell['port_directions'][port] == 'input' for bit in bits]
        for port, bits in cell['connections'].items():
            if cell['port_directions'][port] == 'output':
                for bit in bits:
                    if isinstance(bit, int):
                        if bit in drivers:
                            raise ValueError('multiple netlist drivers')
                        drivers[bit] = (name, input_bits)
    depth_cache: dict[int, int] = {}
    active: set[int] = set()

    def depth(bit: int | str) -> int:
        if not isinstance(bit, int) or bit in inputs:
            return 0
        if bit in depth_cache:
            return depth_cache[bit]
        if bit in active:
            raise ValueError('combinational cycle in synthesized netlist')
        if bit not in drivers:
            raise ValueError('undriven bit in synthesized netlist')
        active.add(bit)
        _, fanin = drivers[bit]
        value = 1 + max((depth(source) for source in fanin), default=0)
        active.remove(bit)
        depth_cache[bit] = value
        return value

    outputs = [bit for port in module['ports'].values() if port['direction'] == 'output' for bit in port['bits']]
    return {'cell_count': len(cells), 'logic_depth': max((depth(bit) for bit in outputs), default=0),
            'cell_types': cell_types}


def _yosys_quote(path: Path) -> str:
    # Yosys string quoting, passed through a script file without a shell.
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'


def run_synthesis(formula: str, output_dir: str | Path, *, yosys: str = 'yosys',
                  ice40: bool = True, timeout: int = 180) -> dict:
    """Run generic synthesis and optionally real iCE40 technology mapping.

    Persist source, complete logs, and JSON netlists in ``output_dir``. The
    iCE40 run uses Yosys' default combinational LUT4/carry mapping (no DSP option,
    no place-and-route, no device timing). Throws on tool failures.
    """
    executable = shutil.which(yosys)
    if executable is None:
        raise RuntimeError('Yosys is required for actual synthesis')
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    canonical = parse_formula(formula).canonical()
    rtl_path = directory / 'candidate.v'
    rtl_path.write_text(generate_rtl(canonical))
    version = subprocess.run([executable, '-V'], check=True, capture_output=True, text=True).stdout.strip()

    def synthesize(flow: str, script_command: str) -> dict:
        netlist_path = directory / f'{flow}-netlist.json'
        script_path = directory / f'{flow}.ys'
        script_path.write_text(f'read_verilog {_yosys_quote(rtl_path)}\n{script_command}\ncheck -assert\nwrite_json {_yosys_quote(netlist_path)}\nstat\n')
        run = subprocess.run([executable, '-s', str(script_path)], capture_output=True, text=True, timeout=timeout)
        (directory / f'{flow}.log').write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError(f'Yosys {flow} failed; see {directory / (flow + ".log")}')
        return netlist_metrics(json.loads(netlist_path.read_text()))

    generic = synthesize('generic', 'synth -top candidate')
    result = {'formula': canonical, 'measurement_source': 'rtl_synthesis',
              'scope': 'isolated combinational RV32 candidate datapath',
              'generic_cell_count': generic['cell_count'], 'generic_logic_depth': generic['logic_depth'],
              'generic_cell_types': generic['cell_types'],
              'area_unit': 'generic mapped gates; iCE40 LUT4/carry resources reported separately',
              'depth_unit': 'generic mapped gate levels', 'tool': version,
              'rtl_sha256': hashlib.sha256(rtl_path.read_bytes()).hexdigest(),
              'measured_at_utc': datetime.now(timezone.utc).isoformat()}
    if ice40:
        mapped = synthesize('ice40', 'synth_ice40 -top candidate')
        result.update(ice40_lut4_count=mapped['cell_types'].get('SB_LUT4', 0),
                      ice40_carry_count=mapped['cell_types'].get('SB_CARRY', 0),
                      ice40_cell_types=mapped['cell_types'],
                      ice40_mapping='Yosys synth_ice40 defaults; no DSP; no place-and-route')
    (directory / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
