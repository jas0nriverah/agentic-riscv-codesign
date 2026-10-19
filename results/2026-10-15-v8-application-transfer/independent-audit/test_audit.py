"""Synthetic audit tests. No experiment code or target-label reads."""
import itertools
import json
from pathlib import Path
import random
import tempfile
import unittest
import zipfile

import audit


def fixture():
    programs = [{'benchmark': name, 'family': name, 'primary_family': name != 'secondary',
                 'traceTotalInstructions': 1000} for name in ('a', 'b', 'c', 'd', 'secondary')]
    formulas = ('add(in0,in1)', 'sub(in0,in1)', 'xor(in0,in1)')
    rows = [{**p, 'candidate_id': p['benchmark'] + ':' + str(i), 'formula': formula,
             'overlapSafeSaved': (100, 80, 40)[i], 'runs': (1, 10, 20)[i]}
            for p in programs for i, formula in enumerate(formulas)]
    labels = [{'formula': f, 'lut4_count': y} for f, y in zip(formulas, (100, 64, 0))]
    predictions = {}
    for model in audit.MODELS:
        values = (1, 64, 0) if model == 'mapping_v6' else (101, 65, 66) if model == 'legacy_rewritten336' else (100, 64, 0)
        predictions[model] = [{'benchmark': r['benchmark'], 'candidate_id': r['candidate_id'],
                              'formula': r['formula'], 'predicted_lut4': values[i % 3], 'upper_lut4': None}
                             for i, r in enumerate(rows)]
    return rows, programs, labels, predictions


class OracleTests(unittest.TestCase):
    def test_fixed_cases(self):
        examples = [
            ('add(in0,in1)', audit.MASK, 1, 0),
            ('addi(in0,-1)', 0, 0, audit.MASK),
            ('sub(in0,in1)', 0, 1, audit.MASK),
            ('slli(slli(in0,31),1)', 1, 0, 0),
            ('srl(in0,in1)', audit.MASK, 32, audit.MASK),
            ('sra(in0,in1)', audit.SIGN, 31, audit.MASK),
            ('srai(in0,-1)', 0x80000001, 0, audit.MASK),
            ('sra(in0,in1)', 0x80000001, 0, 0x80000001),
            ('slt(in0,in1)', audit.MASK, 0, 1),
            ('sltu(in0,in1)', audit.MASK, 0, 0),
            ('sltiu(in0,-1)', audit.SIGN, 0, 1),
            ('mul(in0,in1)', audit.MASK, audit.MASK, 1),
            ('mulh(in0,in1)', audit.MASK, audit.MASK, 0),
            ('mulh(in0,in1)', audit.SIGN, 2, audit.MASK),
            ('mulhsu(in0,in1)', audit.MASK, audit.MASK, audit.MASK),
            ('mulhsu(in0,in1)', audit.SIGN, audit.MASK, 0x80000000),
            ('mulhu(in0,in1)', audit.MASK, audit.MASK, 0xfffffffe),
            ('lui(-2147483648)', 0, 0, audit.SIGN),
            ('xor(and(in0,in1),or(in0,in1))', 0x5500, 0x50aa, 0x05aa)]
        for formula, a, b, expected in examples:
            with self.subTest(formula=formula, a=a, b=b):
                self.assertEqual(audit.evaluate(audit.parse(formula), a, b), expected)

    def test_unsigned_implementations_against_integer_definitions(self):
        rng = random.Random(73)
        pairs = [(a, b) for a in audit.BOUNDARIES for b in audit.BOUNDARIES]
        pairs += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(3000)]
        def signed(x):
            return x if x < 2**31 else x - 2**32
        definitions = {
            'add': lambda x, y: x + y,
            'sub': lambda x, y: x - y,
            'and': lambda x, y: x & y,
            'or': lambda x, y: x | y,
            'xor': lambda x, y: x ^ y,
            'sll': lambda x, y: x << (y & 31),
            'srl': lambda x, y: x >> (y & 31),
            'sra': lambda x, y: signed(x) >> (y & 31),
            'slt': lambda x, y: int(signed(x) < signed(y)),
            'sltu': lambda x, y: int(x < y),
            'mul': lambda x, y: x * y,
            'mulh': lambda x, y: (signed(x) * signed(y)) >> 32,
            'mulhsu': lambda x, y: (signed(x) * y) >> 32,
            'mulhu': lambda x, y: (x * y) >> 32}
        for op, reference in definitions.items():
            tree = audit.parse(op + '(in0,in1)')
            for a, b in pairs:
                self.assertEqual(audit.evaluate(tree, a, b), reference(a, b) & audit.MASK)

    def test_bad_grammar(self):
        for formula in ('add(in0)', 'add(in0,in1)junk', 'add(in0,in2)', 'addi(in0,in1)',
                        'lui(in0)', 'slli(in0,in1)', 'in0', 'add(in0,4294967296)',
                        'add(in0,in1);', '__import__(in0,in1)', 'add(in0,,in1)'):
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                audit.parse(formula)


class MetricTests(unittest.TestCase):
    def test_errors_and_zero_handling(self):
        value = audit.errors([0, 32, 64, 129], [4, 32, 65, 64])
        self.assertEqual(value['mae_lut4'], 17.5)
        self.assertEqual(value['signed_bias_lut4'], -15)
        self.assertEqual(value['zero_target_count'], 1)
        self.assertEqual(value['zero_mae_lut4'], 4)
        self.assertEqual(value['maximum_underprediction_lut4'], 65)
        self.assertAlmostEqual(value['p95_absolute_error_lut4'], 55.85)
        self.assertAlmostEqual(value['p99_absolute_error_lut4'], 63.17)
        self.assertEqual(value['caps']['64']['false_accept_count'], 1)
        self.assertEqual(value['caps']['64']['false_reject_count'], 1)
        self.assertIsNone(audit.errors([0], [0])['positive_mape_percent'])
        self.assertEqual(audit.errors([0], [0])['rmsle'], 0)

    def test_primary_and_acquisition(self):
        value = audit.metrics_and_acquisition(*fixture())
        self.assertAlmostEqual(value['primary']['difference_lut4'], (68 - 99) / 3)
        self.assertEqual(value['scores']['mapping_v6']['primary_equal_family_mae_lut4'], 33)
        self.assertEqual(len(value['selection']['details']), 600)
        self.assertEqual(len(value['selection']['aggregates']), 24)
        details = value['selection']['details']
        mapping = next(r for r in details if r['benchmark'] == 'a' and r['model'] == 'mapping_v6'
                       and r['strategy'] == 'predicted_area_feasible_merit')
        self.assertEqual(mapping['attempts'][0]['candidate_id'], 'a:0')
        self.assertEqual(mapping['selected_overlapSafeSaved'], 0)
        self.assertEqual(mapping['oracle_overlapSafeSaved'], 80)
        self.assertEqual(mapping['normalized_regret_percent_trace_instructions'], 8)
        # All points infeasible: smallest excess comes first, not highest merit.
        challenger = next(r for r in details if r['benchmark'] == 'a' and r['model'] == 'legacy_rewritten336'
                          and r['strategy'] == 'predicted_area_feasible_merit')
        self.assertEqual(challenger['attempts'][0]['candidate_id'], 'a:1')
        self.assertEqual(challenger['retained_oracle_savings_fraction'], 1)
        frequency = next(r for r in details if r['benchmark'] == 'a' and r['strategy'] == 'frequency')
        self.assertEqual(frequency['selected_overlapSafeSaved'], 40)

    def test_zero_oracle(self):
        rows, programs, labels, predictions = fixture()
        for row in rows:
            row['overlapSafeSaved'] = 0
        value = audit.metrics_and_acquisition(rows, programs, labels, predictions)
        self.assertTrue(all(r['normalized_regret_percent_trace_instructions'] == 0 for r in value['selection']['details']))
        self.assertTrue(all(r['retained_oracle_savings_fraction'] is None for r in value['selection']['details']))
        aggregate = next(iter(value['selection']['aggregates'].values()))
        self.assertEqual(aggregate['eligible_primary_family_count'], 0)
        self.assertIsNone(aggregate['primary_equal_eligible_family_conditional_retention'])

    def test_frozen_ties_ignore_actual_area(self):
        rows, programs, labels, predictions = fixture()
        for row in rows:
            row['overlapSafeSaved'] = 100
        labels[0]['lut4_count'] = 64
        labels[1]['lut4_count'] = 1
        value = audit.metrics_and_acquisition(rows, programs, labels, predictions)
        # Lexical add wins even though sub has smaller actual area.
        self.assertTrue(all(r['oracle_candidate_id'].endswith(':0') for r in value['selection']['details']))

    def test_shared_prediction_poison_rejected(self):
        rows, programs, labels, predictions = fixture()
        predictions['mapping_v6'][3]['predicted_lut4'] += 1
        with self.assertRaisesRegex(ValueError, 'Shared formula point differs'):
            audit.metrics_and_acquisition(rows, programs, labels, predictions)

    def test_missing_pool_rejected(self):
        rows, programs, labels, predictions = fixture()
        with self.assertRaisesRegex(ValueError, 'Incomplete declared pools'):
            audit.metrics_and_acquisition([r for r in rows if r['benchmark'] != 'a'], programs, labels, predictions)

    def test_compare_tolerance_and_types(self):
        self.assertFalse(audit.compare({'x': 1.0}, {'x': 1 + 1e-12, 'extra': 3}))
        self.assertTrue(audit.compare({'x': 1.0}, {'x': 1.1}))
        self.assertTrue(audit.compare({'x': True}, {'x': 1}))


def synthetic_raw_fixture(root, bad_output=False, bad_count=False):
    """Portable fixture with no experiment source/data dependence."""
    directory = root / 'measurements'
    directory.mkdir()
    done = {'attempt': 'attempt-9999', 'verification_batch_sizes': [128, 18]}
    (directory / 'completion.json').write_text(json.dumps(done))
    formulas = sorted(f'addi(in0,{i})' for i in range(146))
    rows = [{'formula': f} for f in formulas]
    labels, metrics, proofs = [], [], []
    members = {}
    prefix = 'generated/v8-measurements/attempt-9999/'
    def add(name, data):
        members[prefix + name] = data.encode() if isinstance(data, str) else data
    for i, formula in enumerate(formulas):
        folder = 'circuits/' + audit.digest(formula.encode())[:20] + '/'
        source = 'module candidate(input wire [31:0] in0, in1, output wire [31:0] result);\nassign result = in0 + 32\'d' + str(int(formula[9:-1])) + ';\nendmodule\n'
        netlist = {'modules': {'candidate': {'cells': {'a': {'type': 'SB_LUT4'}, 'b': {'type': 'SB_CARRY'}}}}}
        files = {'candidate.v': source, 'ice40.ys': '# synthetic', 'ice40.log': 'synthetic',
                 'ice40-netlist.json': json.dumps(netlist)}
        metric = {'formula': formula, 'ice40_cell_types': {'SB_LUT4': 1, 'SB_CARRY': 1},
                  'ice40_lut4_count': 2 if bad_count and i == 0 else 1, 'ice40_carry_count': 1,
                  'measurement_source': 'rtl_synthesis'}
        for filename, key in (('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'),
                              ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')):
            add(folder + filename, files[filename])
            metric[key] = audit.digest(files[filename].encode())
        add(folder + 'metrics.json', json.dumps(metric))
        metrics.append(metric)
        labels.append({'formula': formula, 'lut4_count': metric['ice40_lut4_count'], 'carry_count': 1,
                       'rtl_sha256': metric['rtl_sha256'], 'correctness_verified': True,
                       'measurement_source': 'rtl_synthesis'})
    for index in range(2):
        batch = formulas[index * 128:(index + 1) * 128]
        folder = f'verification/batch-{index * 128:04d}/'
        rtl = []
        for j, formula in enumerate(batch):
            rtl.append(f'candidate_{j} c{j}(.in0(in0), .in1(in1), .result(out_{j}));')
            candidate = members[prefix + 'circuits/' + audit.digest(formula.encode())[:20] + '/candidate.v'].decode()
            rtl.append(candidate.replace('module candidate(', f'module candidate_{j}(', 1))
        rtl = '\n'.join(rtl)
        rng = random.Random(2026101517)
        pairs = list(itertools.product(audit.BOUNDARIES, repeat=2))
        pairs += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048)]
        lines = []
        for i, (a, b) in enumerate(pairs):
            outputs = [(a + int(f[9:-1])) & audit.MASK for f in batch]
            if bad_output and index == i == 0:
                outputs[0] ^= 1
            lines.append(' '.join(f'{v:08x}' for v in [a, b, *outputs]))
        vectors = '\n'.join(lines) + '\n'
        add(folder + 'verification.v', rtl)
        add(folder + 'vectors.txt', vectors)
        add(folder + 'verification.log', '2148 vectors passed\n')
        proofs.append({'verified': True, 'formula_count': len(batch), 'vectors_per_formula': 2148,
                       'total_comparisons': len(batch) * 2148, 'random_seed': 2026101517,
                       'rtl_sha256': audit.digest(rtl.encode()), 'vectors_sha256': audit.digest(vectors.encode())})
    archive = directory / 'raw-evidence.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
        for name, data in members.items():
            stream.writestr(name, data)
    manifest = {'archive': archive.name, 'archive_sha256': audit.file_digest(archive),
                'completion_sha256': audit.file_digest(directory / 'completion.json'),
                'files': [{'path': name, 'size': len(data), 'sha256': audit.digest(data)} for name, data in members.items()]}
    (directory / 'raw-evidence.json').write_text(json.dumps(manifest))
    return rows, labels, metrics, proofs, done


class RawEvidenceTests(unittest.TestCase):
    def test_all_outputs_and_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = synthetic_raw_fixture(root)
            result = audit.raw_audit(root, *fixture)
            self.assertEqual(result['independent_expected_outputs_recomputed'], 313608)
            self.assertEqual(result['netlists_recounted'], 146)

    def test_authenticated_wrong_expected_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = synthetic_raw_fixture(root, bad_output=True)
            with self.assertRaisesRegex(ValueError, 'Independent oracle mismatch'):
                audit.raw_audit(root, *fixture)

    def test_authenticated_wrong_resource_count_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = synthetic_raw_fixture(root, bad_count=True)
            with self.assertRaisesRegex(ValueError, 'Resource recount differs'):
                audit.raw_audit(root, *fixture)


if __name__ == '__main__':
    unittest.main(verbosity=2)
