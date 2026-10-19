"""Synthetic Yosys-shaped JSON only. Never parse/run the32study circuits."""
import importlib.util
import itertools
import json
from pathlib import Path
import random
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('rtl_algebra', ROOT / 'scripts/prove_v10_rtl_algebra.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class Fixture:
    def __init__(self, width=4):
        self.width = width
        self.a = list(range(2, 2 + width))
        self.b = list(range(2 + width, 2 + 2 * width))
        self.next_bit = 2 + 2 * width
        self.cells = {}
        self.result = self.a

    def constant(self, value, width=None):
        return [str((value >> i) & 1) for i in range(width or self.width)]

    def cell(self, kind, a, b, *, select=None):
        y = list(range(self.next_bit, self.next_bit + self.width))
        self.next_bit += self.width
        connections = {'A': list(a), 'B': list(b), 'Y': y}
        if kind == '$mux':
            params = {'WIDTH': self.width}
            connections['S'] = list(select)
        else:
            params = {'A_SIGNED': 0, 'B_SIGNED': 0, 'A_WIDTH': len(a), 'B_WIDTH': len(b), 'Y_WIDTH': self.width}
        self.cells['cell_' + str(len(self.cells))] = {'type': kind, 'parameters': params,
            'connections': connections, 'port_directions': {port: 'output' if port == 'Y' else 'input' for port in connections}}
        return y

    def left_wiring(self, bits, distance):
        return ['0'] * self.width if distance >= self.width else ['0'] * distance + bits[:self.width - distance]

    def data(self):
        data = {'creator': 'synthetic fixture, not native output', 'modules': {'candidate': {
            'attributes': {}, 'ports': {'in0': {'direction': 'input', 'bits': self.a},
                'in1': {'direction': 'input', 'bits': self.b}, 'result': {'direction': 'output', 'bits': self.result}},
            'cells': self.cells, 'netnames': {}}}}
        # Real JSON has no Python alias between result bits and a cell's Y list.
        return json.loads(json.dumps(data))


def concrete(data, width, a, b):
    """Independent concrete evaluator: actual wires/cells, no polynomial helpers."""
    module = data['modules']['candidate']
    values = {'0': 0, '1': 1}
    for name, value in [('in0', a), ('in1', b)]:
        values.update({bit: (value >> i) & 1 for i, bit in enumerate(module['ports'][name]['bits'])})
    pending = list(module['cells'].values())
    def word(bits): return sum(values[bit] * 2**i for i, bit in enumerate(bits))
    while pending:
        ready = [cell for cell in pending if all(bit in values for port, bits in cell['connections'].items()
                                                if port != 'Y' for bit in bits)]
        if not ready: raise ValueError('Concrete cycle/undriven')
        for cell in ready:
            c, op = cell['connections'], cell['type']
            x, y = word(c['A']), word(c['B'])
            if op == '$add': result = x + y
            elif op == '$sub': result = x - y
            elif op == '$mul': result = x * y
            elif op == '$and': result = x & y
            elif op == '$shl': result = x << y
            elif op == '$mux': result = y if word(c['S']) else x
            else: raise ValueError('Unsupported concrete operation')
            values.update({bit: (result >> i) & 1 for i, bit in enumerate(c['Y'])})
        pending = [cell for cell in pending if cell not in ready]
    return word(module['ports']['result']['bits'])


def pair(context, *, width=4, constant=3, mask=3):
    left, right = Fixture(width), Fixture(width)
    for f, rewritten in [(left, False), (right, True)]:
        operand = f.a
        if context == 'masked': operand = f.cell('$and', operand, f.constant(mask))
        if context in ('sub', 'masked'): operand = f.cell('$sub', operand, f.b)
        if rewritten:
            assert constant == 3
            # Staged RTL mux and concat rather than an abstract arithmetic shift.
            stage = f.cell('$mux', operand, f.left_wiring(operand, 1), select=['0'])
            shifted = f.cell('$mux', stage, f.left_wiring(stage, 2), select=['1'])
            product = f.cell('$sub', shifted, operand)
        else: product = f.cell('$mul', operand, f.constant(constant))
        f.result = f.cell('$add', product, f.b) if context == 'add' else product
    return left.data(), right.data()


class AlgebraTests(unittest.TestCase):
    def assert_concrete_matches(self, data, width):
        circuit = p.Circuit(data, width=width)
        for a, b in itertools.product(range(1 << width), repeat=2):
            self.assertEqual(circuit.evaluate_polynomial(circuit.result, a, b), concrete(data, width, a, b),
                             (a, b, circuit.result))

    def test_all_four_contexts_exhaustive_reduced_width_and_actual_mux_wiring(self):
        for width in (3, 4):
            for context in ('direct', 'add', 'sub', 'masked'):
                with self.subTest(width=width, context=context):
                    a, b = pair(context, width=width)
                    self.assertTrue(p.prove_pair(a, b, width=width)['proved'])
                    self.assert_concrete_matches(a, width)
                    self.assert_concrete_matches(b, width)

    def test_input_renumbering_cell_names_and_fanout_do_not_change_function(self):
        f = Fixture(4)
        shared = f.cell('$sub', f.a, f.b)
        f.result = f.cell('$add', shared, shared)
        g = Fixture(4)
        doubled_a = g.cell('$mul', g.a, g.constant(2))
        doubled_b = g.cell('$mul', g.b, g.constant(2))
        g.result = g.cell('$sub', doubled_a, doubled_b)
        data = g.data()
        mod = data['modules']['candidate']
        for port in mod['ports'].values(): port['bits'] = [bit + 1000 for bit in port['bits']]
        for cell in mod['cells'].values():
            for port, bits in cell['connections'].items():
                cell['connections'][port] = [bit + 1000 if type(bit) is int else bit for bit in bits]
        mod['cells'] = {'renamed_' + name: cell for name, cell in reversed(list(mod['cells'].items()))}
        self.assertTrue(p.prove_pair(f.data(), data, width=4)['proved'])
        self.assert_concrete_matches(f.data(), 4)
        self.assert_concrete_matches(data, 4)

    def test_masked_arithmetic_is_opaque_exact_function_not_linearized_bits(self):
        f, g = Fixture(4), Fixture(4)
        a = f.cell('$add', f.a, f.b); f.result = f.cell('$and', a, f.constant(3))
        b = g.cell('$add', g.b, g.a); g.result = g.cell('$and', b, g.constant(3))
        self.assertTrue(p.prove_pair(f.data(), g.data(), width=4)['proved'])
        self.assert_concrete_matches(f.data(), 4)
        # AND is not distributed over addition: carry into masked bits matters.
        h = Fixture(4)
        x = h.cell('$and', h.a, h.constant(3)); y = h.cell('$and', h.b, h.constant(3))
        h.result = h.cell('$add', x, y)
        self.assertFalse(p.prove_pair(f.data(), h.data(), width=4)['proved'])
        self.assertNotEqual(concrete(f.data(), 4, 3, 1), concrete(h.data(), 4, 3, 1))

    def test_shift_distance_is_verilog_not_rv32_and_wraps_at_word_width(self):
        for distance in (0, 1, 3, 4, 5, 16):
            f, g = Fixture(4), Fixture(4)
            f.result = f.cell('$shl', f.a, f.constant(distance, 5))
            g.result = g.left_wiring(g.a, distance)
            self.assertTrue(p.prove_pair(f.data(), g.data(), width=4)['proved'])
            self.assert_concrete_matches(f.data(), 4)
        f = Fixture(4);f.result = f.cell('$shl', f.a, f.constant(16, 5))
        identity = Fixture(4)
        self.assertFalse(p.prove_pair(f.data(), identity.data(), width=4)['proved'])

    def test_arbitrary_slices_permutations_constants_preserve_bit_provenance(self):
        rng = random.Random(2026101524)
        for seed in range(10):
            f = Fixture(4)
            x = f.cell('$sub', f.a, f.b)
            if seed % 2: x = f.cell('$and', x, f.constant(rng.randrange(16)))
            refs = [*x, *f.a, *f.b, '0', '1']
            f.result = [rng.choice(refs) for _ in range(4)]
            self.assert_concrete_matches(f.data(), 4)
        a, b = Fixture(4), Fixture(4);b.result = list(reversed(b.a))
        self.assertFalse(p.prove_pair(a.data(), b.data(), width=4)['proved'])

    def test_mixed_dags_exhaustively_match_concrete(self):
        rng = random.Random(2026101525)
        for _ in range(12):
            f = Fixture(4)
            words = [f.a, f.b]
            for _ in range(8):
                op = rng.choice(('$add', '$sub', '$mul', '$and', '$shl', '$mux'))
                a = rng.choice(words)
                b = rng.choice(words) if op in ('$add', '$sub', '$mux') else f.constant(rng.randrange(16))
                words.append(f.cell(op, a, b, select=[str(rng.randrange(2))] if op == '$mux' else None))
            f.result = words[-1]
            self.assert_concrete_matches(f.data(), 4)

    def test_adversarial_wrong_coefficient_shift_mask_operand_wire_not_proved(self):
        for poison in ('coefficient', 'shift', 'mask', 'operand', 'wire'):
            a, b = pair('masked', width=4)
            mod = b['modules']['candidate'];cells = mod['cells']
            if poison == 'mask': cells['cell_0']['connections']['B'] = Fixture(4).constant(7)
            elif poison == 'operand': cells['cell_1']['connections']['B'] = list(mod['ports']['in0']['bits'])
            elif poison == 'shift': cells['cell_3']['connections']['B'] = ['0', *cells['cell_2']['connections']['Y'][:3]]
            elif poison == 'coefficient': cells['cell_4']['type'] = '$add'
            else: mod['ports']['result']['bits'][0] = mod['ports']['in1']['bits'][0]
            with self.subTest(poison=poison):
                self.assertFalse(p.prove_pair(a, b, width=4)['proved'])
                self.assertTrue(any(concrete(a, 4, x, y) != concrete(b, 4, x, y)
                                    for x, y in itertools.product(range(16), repeat=2)))

    def test_constants_zero_allones_and_cancelled_variable_product(self):
        for mask in range(16):
            f = Fixture(4); f.result = f.cell('$and', f.a, f.constant(mask))
            self.assert_concrete_matches(f.data(), 4)
        f = Fixture(4); zero = f.cell('$sub', f.a, f.a); f.result = f.cell('$mul', zero, f.b)
        g = Fixture(4);g.result = g.constant(0)
        self.assertTrue(p.prove_pair(f.data(), g.data(), width=4)['proved'])

    def test_multiterm_add_sub_with_noncontiguous_mask_exhaustive(self):
        f, g = Fixture(5), Fixture(5)
        for circuit, rewritten in ((f, False), (g, True)):
            masked = circuit.cell('$and', circuit.a, circuit.constant(21))
            operand = circuit.cell('$sub', masked, circuit.b)
            if not rewritten:
                circuit.result = circuit.cell('$mul', operand, circuit.constant(13))
            else:
                high = circuit.cell('$shl', operand, circuit.constant(4))
                middle = circuit.left_wiring(operand, 2)
                difference = circuit.cell('$sub', high, middle)
                circuit.result = circuit.cell('$add', difference, operand)
        self.assertTrue(p.prove_pair(f.data(), g.data(), width=5)['proved'])
        self.assert_concrete_matches(f.data(), 5)
        self.assert_concrete_matches(g.data(), 5)


class RejectionTests(unittest.TestCase):
    def test_signed_extension_and_truncation_are_rejected(self):
        for field, value in [('A_SIGNED', 1), ('B_SIGNED', 1), ('A_WIDTH', 3), ('B_WIDTH', 3), ('Y_WIDTH', 5)]:
            f = Fixture(4);f.result = f.cell('$add', f.a, f.b)
            f.cells['cell_0']['parameters'][field] = value
            if field in ('A_WIDTH', 'B_WIDTH'): f.cells['cell_0']['connections'][field[0]].pop()
            with self.subTest(field=field), self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)

    def test_variable_multiply_and_mask_shift_mux_and_unsupported_dead_cell(self):
        for kind in ('$mul', '$and', '$shl', '$mux', '$xor'):
            f = Fixture(4);f.result = f.cell(kind, f.a, f.b, select=[f.a[0]] if kind == '$mux' else None)
            with self.subTest(kind=kind), self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)
        f = Fixture(4);f.cell('$xor', f.a, f.b)
        with self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)

    def test_invalid_wires_drivers_constants_cycles_and_directions(self):
        for poison in ('undef', 'undriven', 'driver', 'input-driver', 'cycle', 'direction', 'selector-x', 'parameter-x'):
            f = Fixture(4);f.result = f.cell('$add', f.a, f.b)
            c = f.cells['cell_0']
            if poison == 'undef': c['connections']['A'][0] = 'x'
            elif poison == 'undriven': c['connections']['A'][0] = 999
            elif poison == 'driver': c['connections']['Y'][1] = c['connections']['Y'][0]
            elif poison == 'input-driver': c['connections']['Y'][0] = f.a[0]
            elif poison == 'cycle': c['connections']['A'][0] = c['connections']['Y'][0]
            elif poison == 'direction': c['port_directions']['A'] = 'output'
            elif poison == 'selector-x': f.result = f.cell('$mux', f.a, f.b, select=['x'])
            else: c['parameters']['A_WIDTH'] = 'xx'
            with self.subTest(poison=poison), self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)

    def test_cycle_even_in_unselected_mux_branch_is_rejected(self):
        f = Fixture(4);f.result = f.cell('$mux', f.a, f.b, select=['0'])
        f.cells['cell_0']['connections']['B'][0] = f.result[0]
        with self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)

    def test_undriven_or_unsupported_unselected_mux_branch_is_rejected(self):
        f = Fixture(4);f.result = f.cell('$mux', f.a, [999, *f.b[1:]], select=['0'])
        with self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)
        f = Fixture(4);bad = f.cell('$xor', f.a, f.b);f.result = f.cell('$mux', f.a, bad, select=['0'])
        with self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=4)

    def test_names_attributes_or_netnames_cannot_override_actual_wires(self):
        a, b = Fixture(4), Fixture(4)
        b.result = b.b
        data = b.data()
        data['modules']['candidate']['netnames'] = {'result': {'bits': b.a, 'attributes': {'source_formula': 'in0'}}}
        data['modules']['candidate']['attributes']['proved_equal'] = '1'
        self.assertFalse(p.prove_pair(a.data(), data, width=4)['proved'])

    def test_port_aliases_signed_offsets_boxes_hierarchy_and_initial_state(self):
        for poison in ('alias', 'signed', 'offset', 'blackbox', 'hierarchy', 'init', 'memory', 'process'):
            f = Fixture(4);data = f.data();m = data['modules']['candidate']
            if poison == 'alias': m['ports']['in1']['bits'][0] = f.a[0]
            elif poison == 'signed': m['ports']['in0']['signed'] = 1
            elif poison == 'offset': m['ports']['in0']['offset'] = 2
            elif poison == 'blackbox': m['attributes']['blackbox'] = '1'
            elif poison == 'hierarchy': data['modules']['another'] = {}
            elif poison == 'init': m['netnames']['state'] = {'attributes': {'init': '0000'}}
            elif poison == 'memory': m['memories'] = {'ram': {}}
            else: m['processes'] = {'process': {}}
            with self.subTest(poison=poison), self.assertRaises(p.RejectedNetlist): p.Circuit(data, width=4)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json';path.write_text('{"modules":{},"modules":{}}')
            with self.assertRaises(p.RejectedNetlist): p.load(path)

    def test_binary_yosys_parameter_strings_and_explicit_word_width(self):
        f = Fixture(4);f.result = f.cell('$add', f.a, f.b)
        for cell in f.cells.values(): cell['parameters'] = {k: format(v, '032b') for k, v in cell['parameters'].items()}
        self.assertEqual(p.Circuit(f.data(), width=4).width, 4)
        with self.assertRaises(p.RejectedNetlist): p.Circuit(f.data(), width=32)


if __name__ == '__main__': unittest.main()
