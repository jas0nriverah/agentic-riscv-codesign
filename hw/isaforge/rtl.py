"""Synthesizable, combinational RV32 candidate logic and an integer oracle.

Formulas use decoded immediates: notably ``lui`` already contains its shifted
32-bit value, as produced by ``src/tracing.py``. Every internal result wraps to
32 bits. The module is an isolated datapath, not a processor integration.
"""
from __future__ import annotations

import hashlib
import itertools
import random
import re
import shutil
import subprocess
from pathlib import Path

from .features import Expression, parse_formula

MASK = (1 << 32) - 1
BOUNDARIES = (0, 1, 2, 31, 32, 33, 0x7FFFFFFF, 0x80000000, 0x80000001, MASK)


def _signed(value: int) -> int:
    return value - (1 << 32) if value & (1 << 31) else value


def evaluate_formula(formula: str | Expression, in0: int, in1: int) -> int:
    """Evaluate exact RV32 arithmetic using Python integers (no RTL execution)."""
    expression = parse_formula(formula) if isinstance(formula, str) else formula

    def visit(node: Expression) -> int:
        if not node.children:
            return (node.value if isinstance(node.value, int) else
                    (in0 if node.value == 'in0' else in1)) & MASK
        operands = [visit(child) for child in node.children]
        op = str(node.value)
        a = operands[0]
        b = operands[1] if len(operands) > 1 else 0
        if op == 'lui': result = a
        elif op in ('add', 'addi'): result = a + b
        elif op == 'sub': result = a - b
        elif op in ('and', 'andi'): result = a & b
        elif op in ('or', 'ori'): result = a | b
        elif op in ('xor', 'xori'): result = a ^ b
        elif op in ('sll', 'slli'): result = a << (b & 31)
        elif op in ('srl', 'srli'): result = a >> (b & 31)
        elif op in ('sra', 'srai'): result = _signed(a) >> (b & 31)
        elif op in ('slt', 'slti'): result = int(_signed(a) < _signed(b))
        elif op in ('sltu', 'sltiu'): result = int(a < b)
        elif op == 'mul': result = a * b
        elif op == 'mulh': result = (_signed(a) * _signed(b)) >> 32
        elif op == 'mulhsu': result = (_signed(a) * b) >> 32
        elif op == 'mulhu': result = (a * b) >> 32
        else: raise ValueError(f'unsupported operation {op}')
        return result & MASK
    return visit(expression)


def generate_rtl(formula: str, module_name: str = 'candidate') -> str:
    """Generate explicit 32-bit intermediate nets and signed multiply operands."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', module_name):
        raise ValueError('invalid module name')
    root = parse_formula(formula)
    lines = [f'module {module_name}(input wire [31:0] in0, in1, output wire [31:0] result);']
    cache: dict[str, str] = {}

    def visit(node: Expression) -> str:
        if not node.children:
            return f"32'h{node.value & MASK:08x}" if isinstance(node.value, int) else str(node.value)
        key = node.canonical()
        if key in cache:
            return cache[key]
        args = [visit(child) for child in node.children]
        name = f'n{len(cache)}'
        # Reserve the name after visiting children; all intermediate nets are 32-bit.
        cache[key] = name
        op = str(node.value)
        a = args[0]
        b = args[1] if len(args) > 1 else ''
        binary = {'add': '+', 'addi': '+', 'sub': '-', 'and': '&', 'andi': '&',
                  'or': '|', 'ori': '|', 'xor': '^', 'xori': '^', 'mul': '*'}
        if op == 'lui': expr = a
        elif op in binary: expr = f'{a} {binary[op]} {b}'
        elif op in ('sll', 'slli', 'srl', 'srli', 'sra', 'srai'):
            # Explicit discard-and-mux stages preserve RV32 truncation. Verilator
            # 5.050 incorrectly folds some chained variable/immediate shifts by
            # adding shift amounts modulo32; concat stages avoid that rewrite.
            shift, prior = f'shift_{name}', f'value_{name}'
            lines.extend([f'wire [31:0] {shift} = {b};', f'wire [31:0] {prior} = {a};'])
            for bit in range(5):
                distance = 1 << bit
                stage = f'stage_{name}_{bit}'
                if op in ('sll', 'slli'):
                    shifted = f"{{{prior}[{31-distance}:0], {distance}'b0}}"
                elif op in ('sra', 'srai'):
                    shifted = f'{{{{{distance}{{{prior}[31]}}}}, {prior}[31:{distance}]}}'
                else:
                    shifted = f"{{{distance}'b0, {prior}[31:{distance}]}}"
                lines.append(f'wire [31:0] {stage} = {shift}[{bit}] ? {shifted} : {prior};')
                prior = stage
            expr = prior
        elif op in ('slt', 'slti', 'sltu', 'sltiu'):
            expr = f'{{31\'b0, ($signed({a}) < $signed({b}))}}' if op in ('slt', 'slti') else f'{{31\'b0, ({a} < {b})}}'
        elif op in ('mulh', 'mulhsu', 'mulhu'):
            # First name the operands so constants and expressions can be indexed.
            left, right, product = f'a_{name}', f'b_{name}', f'p_{name}'
            lines.extend([f'wire [31:0] {left} = {a};', f'wire [31:0] {right} = {b};'])
            sign_a = f'{{32{{{left}[31]}}}}' if op != 'mulhu' else "32'b0"
            sign_b = f'{{32{{{right}[31]}}}}' if op == 'mulh' else "32'b0"
            lines.append(f'wire signed [63:0] {product} = $signed({{{sign_a}, {left}}}) * $signed({{{sign_b}, {right}}});')
            expr = f'{product}[63:32]'
        else: raise ValueError(f'unsupported operation {op}')
        lines.append(f'wire [31:0] {name} = {expr};')
        return name

    result = visit(root)
    lines.extend([f'assign result = {result};', 'endmodule', ''])
    return '\n'.join(lines)


def verify_rtl_batch(formulas: list[str], output_dir: str | Path, *, random_vectors: int = 1024,
                     seed: int = 20261013, verilator: str = 'verilator', timeout: int = 180) -> dict:
    """Compile actual RTL, compare every output on boundary and seeded random inputs.

    One Verilator compilation verifies all supplied formulas. The retained vector
    file records each pair and independent Python-oracle outputs for replay.
    """
    if not formulas or random_vectors < 0:
        raise ValueError('supply formulas and a nonnegative random vector count')
    executable = shutil.which(verilator)
    if executable is None:
        raise RuntimeError('Verilator is required for actual RTL verification')
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    outputs = ', '.join(f'output wire [31:0] out_{i}' for i in range(len(formulas)))
    rtl = [f'module verification_top(input wire [31:0] in0, in1, {outputs});']
    rtl.extend(f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(formulas)))
    rtl.append('endmodule')
    rtl.extend(generate_rtl(formula, f'candidate_{i}') for i, formula in enumerate(formulas))
    rtl_path = directory / 'verification.v'
    rtl_path.write_text('\n'.join(rtl))
    pairs = list(itertools.product(BOUNDARIES, repeat=2))
    rng = random.Random(seed)
    pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(random_vectors))
    expressions = [parse_formula(formula) for formula in formulas]
    vector_path = directory / 'vectors.txt'
    with vector_path.open('w') as vectors:
        for a, b in pairs:
            vectors.write(' '.join(f'{x:08x}' for x in [a, b, *(evaluate_formula(expr, a, b) for expr in expressions)]) + '\n')
    harness = ['#include "Vverification_top.h"', '#include "verilated.h"', '#include <fstream>',
               '#include <iostream>', '#include <cstdint>',
               'int main(int argc, char **argv) { Verilated::commandArgs(argc, argv);',
               'Vverification_top top; std::ifstream vectors(argv[1]); uint32_t a,b,want; unsigned count=0;',
               'while(vectors >> std::hex >> a >> b) { top.in0=a; top.in1=b; top.eval();']
    for i in range(len(formulas)):
        harness.append(f'if (!(vectors >> std::hex >> want) || top.out_{i} != want) {{ std::cerr << "Mismatch formula {i} vector " << std::dec << count << " got " << std::hex << top.out_{i} << " expected " << want << "\\n"; return 1; }}')
    harness.extend(['++count; }', 'std::cout << count << " vectors passed\\n"; top.final(); return 0; }'])
    cpp_path = directory / 'verification.cpp'
    cpp_path.write_text('\n'.join(harness))
    version = subprocess.run([executable, '--version'], check=True, capture_output=True, text=True).stdout.strip()
    build = subprocess.run([executable, '--cc', '--exe', '--build', '-j', '2', '-Wno-fatal', '--top-module',
                            'verification_top', '--Mdir', str(directory / 'obj_dir'), str(rtl_path), str(cpp_path)],
                           capture_output=True, text=True, timeout=timeout)
    (directory / 'verilator-build.log').write_text(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError(f'Verilator build failed; see {directory / "verilator-build.log"}')
    run = subprocess.run([str(directory / 'obj_dir/Vverification_top'), str(vector_path)],
                         capture_output=True, text=True, timeout=timeout)
    (directory / 'verification.log').write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'RTL correctness failed: {run.stdout}{run.stderr}')
    return {'verified': True, 'formula_count': len(formulas), 'vectors_per_formula': len(pairs),
            'total_comparisons': len(formulas) * len(pairs), 'random_seed': seed,
            'oracle': 'Python integer RV32 semantics', 'tool': version,
            'rtl_sha256': hashlib.sha256(rtl_path.read_bytes()).hexdigest(),
            'vectors_sha256': hashlib.sha256(vector_path.read_bytes()).hexdigest()}


def verify_rtl(formula: str, output_dir: str | Path, **kwargs) -> dict:
    return verify_rtl_batch([formula], output_dir, **kwargs)
