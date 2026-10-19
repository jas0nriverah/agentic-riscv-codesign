#!/usr/bin/env python3
"""Fail-closed universal equality checker for two actual Yosys word JSON files.

No formula/emitter/model imports, solver, Yosys invocation or area measurement.
The proposed caller must bind exact RTL, frontend executable/data/commands and
JSON bytes. Intended frontend: read_verilog; hierarchy -check -top candidate;
proc; opt_clean; write_json. This module only consumes the resulting JSON.

Sound but incomplete: unsigned equal-width arithmetic only; constant multiply,
AND, left shift and mux select. Signed/extended/truncated cell widths, variable
nonlinear operations, undef, hierarchy, state, multiple drivers and cycles fail
closed. Slices/concats preserve actual bit provenance. Full-width identity and
zero-filled left-shift wiring reduce algebraically; other bit permutations use
exact opaque bit functions, never an assumed whole-word identity.

Each polynomial equals the actual word in Z/(2**width), by induction over the
parsed DAG. Opaque mask/bit atoms name exact functions of canonical polynomials.
Treating them as unconstrained is conservative: equal normal forms prove
equality for every input; unequal forms are only NOT PROVED, not a counterexample.
References: Yosys word-cell semantics, and pinned +/simlib.v ($add/$sub/$mul/
$and/$shl/$mux). No claim of portable frontend provenance is made by JSON alone.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'isaforge-v10-actual-rtl-algebra-v1'
SUPPORTED = frozenset(('$add', '$sub', '$mul', '$and', '$shl', '$mux'))
MAX_CELLS = 4096
MAX_TERMS = 4096
MAX_DEPTH = 128


class RejectedNetlist(ValueError):
    pass


def need(value, message):
    if not value:
        raise RejectedNetlist(message)


def parameter(value):
    if type(value) is int:
        need(0 <= value < 2**64, 'Invalid integer parameter')
        return value
    need(isinstance(value, str) and re.fullmatch('[01]{1,64}', value), 'Defined binary parameter required')
    return int(value, 2)


def valid_bit(bit):
    return (type(bit) is int and bit >= 2) or (type(bit) is str and bit in ('0', '1'))


class Circuit:
    """A single flat, two-input combinational word module; all cells checked."""

    def __init__(self, data, *, module='candidate', width=32):
        need(type(width) is int and 1 <= width <= 32, 'Word width must be1..32')
        self.width, self.mask = width, (1 << width) - 1
        need(set(data.get('modules', {})) == {module}, 'Exactly one flat module required')
        self.module = data['modules'][module]
        need(not self.module.get('memories') and not self.module.get('processes')
            and not self.module.get('parameter_default_values'), 'No memories/processes/module parameters')
        for attr in ('blackbox', 'whitebox', 'lib_whitebox'):
            need(parameter(self.module.get('attributes', {}).get(attr, 0)) == 0, 'Black/white boxes unsupported')
        ports = self.module.get('ports', {})
        need(set(ports) == {'in0', 'in1', 'result'}, 'Exact in0/in1/result ports required')
        for name, port in ports.items():
            need(port.get('direction') == ('output' if name == 'result' else 'input'), 'Port direction differs')
            need(isinstance(port.get('bits'), list) and len(port['bits']) == width, 'Exact word-width port required')
            need(port.get('signed', 0) == 0 and port.get('offset', 0) == 0 and port.get('upto', 0) == 0,
                'Only unsigned descending zero-offset ports supported')
            need(all(valid_bit(bit) for bit in port['bits']), 'Undefined/invalid port bit')
        self.inputs = {}
        for name in ('in0', 'in1'):
            polynomial = self.poly(0, {('input', name): 1})
            for index, bit in enumerate(ports[name]['bits']):
                need(type(bit) is int and bit not in self.inputs, 'Distinct, unconstrained input wires required')
                self.inputs[bit] = (polynomial, index)
        self.cells = self.module.get('cells', {})
        need(isinstance(self.cells, dict) and len(self.cells) <= MAX_CELLS, 'Cell bound exceeded')
        self.drivers, self.memo = {}, {}
        for name, cell in self.cells.items():
            need(cell.get('type') in SUPPORTED, 'Unsupported cell: ' + str(cell.get('type')))
            need(cell.get('hide_name', 0) in (0, 1), 'Invalid cell metadata')
            ports_expected = {'A', 'B', 'Y', 'S'} if cell['type'] == '$mux' else {'A', 'B', 'Y'}
            connections, params = cell.get('connections', {}), cell.get('parameters', {})
            need(set(connections) == set(cell.get('port_directions', {})) == ports_expected, 'Cell ports differ')
            for port, bits in connections.items():
                need(isinstance(bits, list) and all(valid_bit(bit) for bit in bits), 'Undefined/invalid cell bit')
                need(cell['port_directions'][port] == ('output' if port == 'Y' else 'input'), 'Cell direction differs')
            if cell['type'] == '$mux':
                need(set(params) == {'WIDTH'} and parameter(params['WIDTH']) == width, 'Mux parameter width differs')
                need(all(len(connections[p]) == width for p in ('A', 'B', 'Y')) and len(connections['S']) == 1,
                    'Mux widths differ')
            else:
                need(set(params) == {'A_SIGNED', 'B_SIGNED', 'A_WIDTH', 'B_WIDTH', 'Y_WIDTH'}, 'Arithmetic parameters differ')
                need(parameter(params['A_SIGNED']) == parameter(params['B_SIGNED']) == 0, 'Signed cells unsupported')
                need(parameter(params['A_WIDTH']) == parameter(params['Y_WIDTH']) == width
                    and len(connections['A']) == len(connections['Y']) == width, 'Extended/truncated A/Y cell width unsupported')
                bw = parameter(params['B_WIDTH'])
                need(len(connections['B']) == bw and (1 <= bw <= 32 if cell['type'] == '$shl' else bw == width),
                    'Extended/truncated B cell width unsupported')
            for index, bit in enumerate(connections['Y']):
                need(type(bit) is int and bit not in self.drivers and bit not in self.inputs, 'Multiple/constant/input output driver')
                self.drivers[bit] = (name, index)
        for name, net in self.module.get('netnames', {}).items():
            need('init' not in net.get('attributes', {}), 'Initial-state assumptions unsupported')
        # Check the entire graph, even dead cells and unselected mux branches.
        active, done = set(), set()
        def visit(name, depth):
            need(depth <= MAX_DEPTH and name not in active, 'Cycle/depth bound in actual connections')
            if name in done:
                return
            active.add(name)
            for port, bits in self.cells[name]['connections'].items():
                if port == 'Y':
                    continue
                for bit in bits:
                    if type(bit) is int and bit not in self.inputs:
                        need(bit in self.drivers, 'Undriven actual wire')
                        visit(self.drivers[bit][0], depth + 1)
            active.remove(name)
            done.add(name)
        for name in self.cells:
            visit(name, 0)
        for name in self.cells:
            self.cell(name)
        self.result = self.vector(ports['result']['bits'])

    def poly(self, constant=0, terms=None):
        terms = tuple(sorted((atom, coefficient & self.mask) for atom, coefficient in (terms or {}).items()
                             if coefficient & self.mask))
        need(len(terms) <= MAX_TERMS, 'Polynomial term bound exceeded')
        return (constant & self.mask, terms)

    def add(self, a, b, sign=1):
        terms = dict(a[1])
        for atom, coefficient in b[1]:
            terms[atom] = terms.get(atom, 0) + sign * coefficient
        return self.poly(a[0] + sign * b[0], terms)

    def scale(self, a, coefficient):
        return self.poly(a[0] * coefficient, {atom: value * coefficient for atom, value in a[1]})

    def bit(self, bit):
        if type(bit) is str:
            return int(bit)
        if bit in self.inputs:
            return self.inputs[bit]
        need(bit in self.drivers, 'Undriven result wire')
        name, index = self.drivers[bit]
        polynomial = self.cell(name)
        return (polynomial[0] >> index) & 1 if not polynomial[1] else (polynomial, index)

    def vector(self, bits):
        need(len(bits) == self.width, 'Word assembly width differs')
        refs = [self.bit(bit) for bit in bits]
        # Exact lsb-first identity or zero-filled left shift, including discarded
        # high bits. Other slices NEVER inherit a whole-word polynomial.
        for shift in range(self.width):
            if not all(ref == 0 for ref in refs[:shift]):
                continue
            candidate = refs[shift]
            if isinstance(candidate, tuple):
                polynomial, index = candidate
                if index == 0 and all(ref == (polynomial, i) for i, ref in enumerate(refs[shift:])):
                    return self.scale(polynomial, 1 << shift)
        result = self.poly()
        for index, ref in enumerate(refs):
            if type(ref) is int:
                result = self.add(result, self.poly(ref << index))
            else:
                polynomial, source_index = ref
                atom = ('bit', polynomial, source_index)
                result = self.add(result, self.poly(0, {atom: 1 << index}))
        return result

    def constant_vector(self, bits):
        refs = [self.bit(bit) for bit in bits]
        need(all(type(ref) is int for ref in refs), 'Literal/constant-folded control required')
        return sum(ref << i for i, ref in enumerate(refs))

    def cell(self, name):
        if name in self.memo:
            return self.memo[name]
        cell = self.cells[name]
        kind, c = cell['type'], cell['connections']
        if kind == '$mux':
            selector = self.constant_vector(c['S'])
            need(selector in (0, 1), 'Defined1-bit constant mux control required')
            result = self.vector(c['B'] if selector else c['A'])
        else:
            a = self.vector(c['A'])
            if kind == '$shl':
                distance = self.constant_vector(c['B'])
                # Verilog left shift does NOT mask its shift distance like RV32.
                result = self.poly() if distance >= self.width else self.scale(a, 1 << distance)
            else:
                b = self.vector(c['B'])
                if kind in ('$add', '$sub'):
                    result = self.add(a, b, 1 if kind == '$add' else -1)
                elif kind == '$mul':
                    need(not a[1] or not b[1], 'Variable multiplication unsupported')
                    result = self.scale(a, b[0]) if not b[1] else self.scale(b, a[0])
                else:
                    need(kind == '$and' and (not a[1] or not b[1]), 'Variable bitwise AND unsupported')
                    operand, mask = (a, b[0]) if not b[1] else (b, a[0])
                    if not operand[1]: result = self.poly(operand[0] & mask)
                    elif mask == 0: result = self.poly()
                    elif mask == self.mask: result = operand
                    else: result = self.poly(0, {('and', operand, mask): 1})
        self.memo[name] = result
        return result

    def evaluate_polynomial(self, polynomial, in0, in1):
        """Diagnostic interpretation of the exact atom definitions, not a proof."""
        value = polynomial[0]
        for atom, coefficient in polynomial[1]:
            if atom[0] == 'input': term = in0 if atom[1] == 'in0' else in1
            elif atom[0] == 'and': term = self.evaluate_polynomial(atom[1], in0, in1) & atom[2]
            else:
                need(atom[0] == 'bit', 'Unknown atom')
                term = (self.evaluate_polynomial(atom[1], in0, in1) >> atom[2]) & 1
            value += coefficient * term
        return value & self.mask


def prove_pair(original, csd, *, module='candidate', width=32):
    left, right = Circuit(original, module=module, width=width), Circuit(csd, module=module, width=width)
    proved = left.result == right.result
    return {'schema': SCHEMA, 'status': 'proved' if proved else 'not-proved', 'proved': proved,
        'word_width': width, 'input_assumptions': [], 'method': 'actual parsed RTL DAG; exact modular affine polynomial identity',
        'original_polynomial': left.result, 'csd_polynomial': right.result,
        'original_cell_types': dict(Counter(c['type'] for c in left.cells.values())),
        'csd_cell_types': dict(Counter(c['type'] for c in right.cells.values())),
        'scope': 'Universal equality of supplied actual word-level JSONs. Caller must authenticate RTL/frontend/JSON lineage. No mapped-netlist, timing, power or area claim.',
        'incomplete_case_policy': 'Unequal normal forms do not establish inequivalence; unsupported semantics reject.'}


def load(path):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-json', type=Path, required=True)
    parser.add_argument('--csd-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--module', default='candidate')
    parser.add_argument('--width', type=int, default=32)
    args = parser.parse_args()
    try:
        result = prove_pair(load(args.original_json), load(args.csd_json), module=args.module, width=args.width)
    except (RejectedNetlist, KeyError, TypeError, RecursionError) as error:
        result = {'schema': SCHEMA, 'status': 'rejected', 'proved': False, 'error': str(error)}
    result['original_json_sha256'] = hashlib.sha256(args.original_json.read_bytes()).hexdigest()
    result['csd_json_sha256'] = hashlib.sha256(args.csd_json.read_bytes()).hexdigest()
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'proved': result['proved']}))
    raise SystemExit(0 if result['proved'] else 1)
