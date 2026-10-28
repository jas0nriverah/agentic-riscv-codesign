#!/usr/bin/env python3
"""Reproduce source/host/link checks only; never simulate or measure a candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent
FLAGS = ['-march=rv32i_zicsr', '-mabi=ilp32', '-Os', '-std=gnu17',
         '-nostdlib', '-nostartfiles', '-ffreestanding', '-fno-builtin',
         '-ffunction-sections', '-fdata-sections', '-msmall-data-limit=0',
         '-mno-relax', '-DCPU_MHZ=1']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--riscv-gcc', type=Path, required=True)
    parser.add_argument('--clang', default='clang')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Use a fresh output directory outside this evidence package')
    pin = json.loads((ROOT/'source-pin.json').read_text())
    for relative, expected in pin['inputs'].items():
        path = (ROOT/relative).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Input hash mismatch: '+relative)
    gcc = args.riscv_gcc.resolve()
    nm = gcc.with_name(gcc.name.removesuffix('gcc')+'nm')
    clang = shutil.which(args.clang)
    if not clang or not gcc.is_file() or not nm.is_file():
        raise ValueError('Host clang and RISC-V gcc/nm required')
    output.mkdir(parents=True)
    records = []

    def run(name, argv, expected=0):
        argv = [str(x) for x in argv]
        start = time.monotonic()
        result = subprocess.run(argv, cwd=output, text=True, capture_output=True, timeout=60)
        records.append(dict(name=name, argv=argv, returncode=result.returncode,
            elapsed_seconds=time.monotonic()-start))
        (output/(name+'.stdout')).write_text(result.stdout)
        (output/(name+'.stderr')).write_text(result.stderr)
        (output/'commands.json').write_text(json.dumps(records, indent=2)+'\n')
        if result.returncode != expected:
            raise RuntimeError(name+': unexpected exit '+str(result.returncode))
        return result.stdout

    inputs = ROOT/'inputs'
    upstream = inputs/'upstream'
    for mode, fault in [('host32', False), ('host32_fault', True)]:
        run(mode+'_build', [clang, '-std=c99', '-Os', '-DCOBS_SWAR_WORD_BITS=32',
            *(['-DCOBS_PROBE_FAULT'] if fault else []), upstream/'cobs.c',
            upstream/'tests/cobs_ref.c', upstream/'tests/qemu/probe.c',
            inputs/'host_shim.c', '-o', output/mode])
        text = run(mode+'_execute', [output/mode], expected=1 if fault else 0)
        marker = 'RESULT FAIL 8214/8215' if fault else 'RESULT PASS 8215/8215'
        if marker not in text:
            raise RuntimeError('Upstream oracle count mismatch')
    run('rv32_link', [gcc, *FLAGS, '-fstack-usage', '-Wl,--gc-sections',
        '-Wl,--no-relax', '-Wl,-Map,'+str(output/'firmware.map'),
        '-Wl,-T,'+str(inputs/'soc_link.ld'), inputs/'soc_start.S',
        inputs/'embench_firmware.c', inputs/'embench_memory.c', inputs/'adapter.c',
        upstream/'cobs.c', upstream/'tests/cobs_ref.c', '-o', output/'firmware.elf'])
    symbols = run('rv32_symbols', [nm, '-n', output/'firmware.elf'])
    unresolved = run('rv32_unresolved', [nm, '-u', output/'firmware.elf'])
    ends = [int(line.split()[0], 16) for line in symbols.splitlines()
            if line.split()[-1:] == ['_program_end']]
    if len(ends) != 1 or ends[0] > 6400 or unresolved.strip():
        raise RuntimeError('Target link or runtime resolution failed')
    report = dict(status='source_host_and_rv32_link_preflight_passed',
        upstream_commit=pin['commit'], host_cases_passed=8215,
        seeded_fault_detected=True, host_swar_bits=32,
        host_pointer_width='Native host, not proof of RV32 execution',
        program_end_bytes=ends[0], program_limit_bytes=6400,
        gcc_sha256=hashlib.sha256(gcc.read_bytes()).hexdigest(),
        target_execution_performed=False, actual_stack_high_water=None,
        legal_candidate_pool=None, candidate_measurements=0, training_labels_added=0,
        limitations=['Differential reference uses the same code with SWAR disabled.',
            'Timed adapter includes upstream input generation and reference checks.',
            'No target execution, extraction, opportunity, area, or timing result.'])
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
