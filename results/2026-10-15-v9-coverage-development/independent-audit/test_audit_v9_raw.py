"""Synthetic corruption tests; never open the actual V9 target measurements."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import audit_v9_raw as a


def fixture(root, wrong_output=False, wrong_count=False, wrong_rtl=False, wrong_input=False):
    directory = root / 'measurements'
    directory.mkdir()
    done = {'attempt': 'attempt-9999'}
    (directory / 'completion.json').write_text(json.dumps(done))
    candidates = [{'formula': f'mul(in0,addi(0,{i}))', 'candidate_id': 'synthetic-' + str(i)} for i in range(1, 49)]
    formulas = sorted(r['formula'] for r in candidates)
    tool = {'version': 'Yosys synthetic fixture', 'executable_sha256': 'a' * 64}
    metrics, label_index, members = [], {}, {}
    prefix = a.PREFIX + done['attempt'] + '/'
    def add(name, data):
        members[prefix + name] = data.encode() if isinstance(data, str) else data
    for index, formula in enumerate(formulas):
        folder = 'circuits/' + a.digest(formula.encode())[:20] + '/'
        rtl = a.original_rtl(formula)
        if wrong_rtl and index == 0:
            rtl = rtl.replace(b'in0 * n0', b'in0 + n0')
        netlist = {'modules': {'candidate': {'cells': {'a': {'type': 'SB_LUT4'}, 'b': {'type': 'SB_CARRY'}}}}}
        files = {'candidate.v': rtl,
            'ice40.ys': b'read_verilog "/synthetic/candidate.v"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "/synthetic/ice40-netlist.json"\nstat\n',
            'ice40.log': b'synthetic successful mapping log\n',
            'ice40-netlist.json': json.dumps(netlist).encode()}
        count = 2 if wrong_count and index == 0 else 1
        metric = {'formula': formula, 'tool': tool['version'], 'tool_sha256': tool['executable_sha256'],
            'measurement_source': 'rtl_synthesis', 'ice40_cell_types': {'SB_LUT4': 1, 'SB_CARRY': 1},
            'ice40_lut4_count': count, 'ice40_carry_count': 1}
        for name, key in (('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'),
                           ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')):
            add(folder + name, files[name])
            metric[key] = a.digest(files[name])
        add(folder + 'metrics.json', json.dumps(metric))
        metrics.append(metric)
        label_index[formula] = {'lut4_count': count, 'carry_count': 1, 'rtl_sha256': metric['rtl_sha256'],
            'measurement_source': 'rtl_synthesis', 'correctness_verified': True}
    labels = [{**r, **label_index[r['formula']]} for r in candidates]
    rtl = a.verification_rtl(formulas)
    lines = []
    for index, (x, y) in enumerate(a.input_pairs()):
        # Independent closed-form fixture output rather than calling the oracle.
        outputs = [(x * int(formula.rsplit(',', 1)[1][:-2])) & 0xffffffff for formula in formulas]
        if wrong_output and index == 0:
            outputs[0] ^= 1
        words = [x, y, *outputs]
        if wrong_input and index == 0:
            words[0] ^= 1
        lines.append(' '.join(f'{word:08x}' for word in words))
    vectors = ('\n'.join(lines) + '\n').encode()
    add('verification/batch-0000/verification.v', rtl)
    add('verification/batch-0000/vectors.txt', vectors)
    add('verification/batch-0000/verification.log', b'2148 vectors passed\n')
    proofs = [{'verified': True, 'formula_count': 48, 'vectors_per_formula': 2148,
        'total_comparisons': 48 * 2148, 'random_seed': a.SEED,
        'rtl_sha256': a.digest(rtl), 'vectors_sha256': a.digest(vectors)}]
    archive = directory / 'raw-evidence.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
        for name, data in members.items():
            stream.writestr(name, data)
    manifest = {'schema': 'isaforge-v9-coverage-raw-evidence-v1', 'archive': archive.name,
        'archive_sha256': a.sha(archive), 'completion_sha256': a.sha(directory / 'completion.json'),
        'attempt': done['attempt'], 'complete': True, 'compiler_objects_included': False,
        'files': [{'path': name, 'size': len(data), 'sha256': a.digest(data)} for name, data in members.items()]}
    (directory / 'raw-evidence.json').write_text(json.dumps(manifest))
    return candidates, labels, metrics, proofs, done, tool


class IndependentRawTests(unittest.TestCase):
    def test_original_rtl_known_constant_product(self):
        expected = "module candidate(input wire [31:0] in0, in1, output wire [31:0] result);\nwire [31:0] n0 = 32'h00000000 + 32'h0000000b;\nwire [31:0] n1 = in0 * n0;\nassign result = n1;\nendmodule\n"
        self.assertEqual(a.original_rtl('mul(in0,addi(0,11))'), expected.encode())

    def test_original_rtl_known_shift_stages(self):
        text = a.original_rtl('srai(in0,1)').decode()
        self.assertIn('wire [31:0] stage_n0_0 = shift_n0[0] ? {{1{value_n0[31]}}, value_n0[31:1]} : value_n0;', text)
        self.assertIn('wire [31:0] stage_n0_4 = shift_n0[4] ? {{16{stage_n0_3[31]}}, stage_n0_3[31:16]} : stage_n0_3;', text)

    def test_complete_synthetic_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = a.raw_checks(root, *fixture(root))
            self.assertEqual(result['independent_expected_outputs_recomputed'], 103104)
            self.assertEqual(result['netlists_recounted'], 48)
            self.assertTrue(result['passed'])

    def test_authenticated_wrong_expected_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Independent expected-output mismatch'):
                a.raw_checks(root, *fixture(root, wrong_output=True))

    def test_authenticated_wrong_resource_count_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'resource recount differs'):
                a.raw_checks(root, *fixture(root, wrong_count=True))

    def test_authenticated_wrong_original_rtl_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Mapped original RTL identity differs'):
                a.raw_checks(root, *fixture(root, wrong_rtl=True))

    def test_authenticated_wrong_vector_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Vector seed/boundaries differ'):
                a.raw_checks(root, *fixture(root, wrong_input=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
