#!/usr/bin/env python3
"""Independent V9 raw archive audit: stdlib only, no production imports/runs.

The copied independent V8 unsigned32 oracle checks every archived expected
output. A restricted, separate RTL renderer authenticates the fixed V9 grammar.
--prepare reads only approved inputs; --released is required for target I/O.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import random
import re
import unsigned_oracle as oracle

COUNT = 48
SEED = 2026101519
VECTORS = 2148
PREFIX = 'generated/v9-coverage-measurements/'
HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def utc(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, 'Timezone-aware timestamp required')
    return result


def integer(value):
    require(type(value) is int and value >= 0, 'Nonnegative integer count required')
    return value


def original_rtl(formula, module='candidate'):
    """Exact byte identity renderer for the fixed coverage grammar only.

    This does not execute the production generator. All arithmetic verification
    uses the separate unsigned oracle, rather than evaluating this RTL text.
    """
    tree = oracle.parse(formula)
    lines = [f'module {module}(input wire [31:0] in0, in1, output wire [31:0] result);']
    names = {}
    def emit(node):
        if type(node) is int:
            return f"32'h{node & 0xffffffff:08x}"
        if isinstance(node, str):
            return node
        if node in names:
            return names[node]
        op = node[0]
        require(op in ('add', 'addi', 'sub', 'and', 'andi', 'mul', 'srai', 'slli'), 'Operation outside fixed coverage RTL renderer')
        args = [emit(child) for child in node[1:]]
        name = f'n{len(names)}'
        names[node] = name
        a, b = args
        binary = {'add': '+', 'addi': '+', 'sub': '-', 'and': '&', 'andi': '&', 'mul': '*'}
        if op in binary:
            expression = a + ' ' + binary[op] + ' ' + b
        else:
            lines.extend([f'wire [31:0] shift_{name} = {b};', f'wire [31:0] value_{name} = {a};'])
            prior = f'value_{name}'
            for bit in range(5):
                distance = 2 ** bit
                if op == 'slli':
                    shifted = '{' + f"{prior}[{31-distance}:0], {distance}'b0" + '}'
                else:
                    shifted = '{{' + f'{distance}' + '{' + f'{prior}[31]' + '}}, ' + f'{prior}[31:{distance}]' + '}'
                stage = f'stage_{name}_{bit}'
                lines.append(f'wire [31:0] {stage} = shift_{name}[{bit}] ? {shifted} : {prior};')
                prior = stage
            expression = prior
        lines.append(f'wire [31:0] {name} = {expression};')
        return name
    result = emit(tree)
    lines.extend([f'assign result = {result};', 'endmodule', ''])
    return '\n'.join(lines).encode()


def verification_rtl(formulas):
    ports = ', '.join(f'output wire [31:0] out_{i}' for i in range(len(formulas)))
    lines = [f'module verification_top(input wire [31:0] in0, in1, {ports});']
    lines.extend(f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(formulas)))
    lines.append('endmodule')
    lines.extend(original_rtl(formula, f'candidate_{i}').decode() for i, formula in enumerate(formulas))
    return '\n'.join(lines).encode()


def input_pairs():
    rng = random.Random(SEED)
    yield from itertools.product(oracle.BOUNDARIES, repeat=2)
    for _ in range(2048):
        yield rng.getrandbits(32), rng.getrandbits(32)


def input_snapshot(root):
    root = Path(root).resolve()
    preparation = read(root / 'preparation.json')
    candidates = read(root / 'candidates.json')
    require(len(candidates) == len({r['formula'] for r in candidates}) == COUNT, 'Exactly48 originals required')
    require(sha(root / 'candidates.json') == preparation['candidates']['sha256'], 'Candidate input digest differs')
    require(sha(root / 'recipe.json') == preparation['recipe']['sha256'], 'Recipe input digest differs')
    return {'schema': 'independent-v9-raw-audit-readiness-v1', 'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
        'new_target_files_read': False, 'native_tools_run': False, 'model_imports_or_fits': False,
        'audit_source_sha256': sha(__file__), 'oracle_source_sha256': sha(HERE / 'unsigned_oracle.py'),
        'preparation_sha256': sha(root / 'preparation.json'), 'candidates_sha256': sha(root / 'candidates.json'),
        'recipe_sha256': sha(root / 'recipe.json'), 'count': COUNT, 'verification_seed': SEED,
        'vectors_per_formula': VECTORS,
        'expected_original_rtl': [{'formula': r['formula'], 'sha256': digest(original_rtl(r['formula']))} for r in candidates]}


def raw_checks(root, candidates, labels, metrics, proofs, done, tool):
    directory = root / 'measurements'
    manifest = read(directory / 'raw-evidence.json')
    require(manifest.get('schema') == 'isaforge-v9-coverage-raw-evidence-v1' and manifest.get('archive') == 'raw-evidence.zip'
        and manifest.get('complete') is True and manifest.get('attempt') == done['attempt']
        and manifest.get('compiler_objects_included') is False, 'Raw archive identity differs')
    archive = directory / 'raw-evidence.zip'
    require(sha(archive) == manifest['archive_sha256'] and sha(directory / 'completion.json') == manifest['completion_sha256'], 'Archive/completion digest differs')
    formulas = sorted(r['formula'] for r in candidates)
    label_index = {r['formula']: r for r in labels}
    metric_index = {r['formula']: r for r in metrics}
    require(len(labels) == len(metrics) == len(label_index) == len(metric_index) == COUNT
        and set(label_index) == set(metric_index) == set(formulas), 'Complete exact original targets required')
    require([r['formula'] for r in labels] == [r['formula'] for r in candidates], 'Original candidate/label order differs')
    for candidate, label in zip(candidates, labels):
        require(all(label[k] == v for k, v in candidate.items()), 'Candidate identity/metadata changed')
    records = {r['path']: r for r in manifest['files']}
    require(len(records) == len(manifest['files']) > 0, 'Duplicate/empty raw inventory')
    prefix = PREFIX + done['attempt'] + '/'
    comparisons = 0
    recounts = []
    import zipfile
    with zipfile.ZipFile(archive) as raw:
        require(len(raw.namelist()) == len(set(raw.namelist())) and set(raw.namelist()) == set(records), 'ZIP member inventory differs')
        for info in raw.infolist():
            name = info.filename
            path = PurePosixPath(name)
            require(name.startswith(prefix) and not path.is_absolute() and '..' not in path.parts and '\\' not in name
                and str(path) == name and not info.is_dir() and ((info.external_attr >> 16) & 0o170000) in (0, 0o100000), 'Unsafe/nonregular raw member')
            data = raw.read(info)
            record = records[name]
            require(type(record['size']) is int and len(data) == record['size'] and digest(data) == record['sha256'], 'Raw member bytes differ')
        def data(name):
            return raw.read(prefix + name)
        require(len(proofs) == 1, 'Exactly one48-formula vector batch required')
        proof = proofs[0]
        require(proof.get('verified') is True and proof.get('formula_count') == COUNT and proof.get('vectors_per_formula') == VECTORS
            and proof.get('total_comparisons') == COUNT * VECTORS and proof.get('random_seed') == SEED, 'Incomplete original vector proof')
        folder = 'verification/batch-0000/'
        rtl, vectors = data(folder + 'verification.v'), data(folder + 'vectors.txt')
        require(digest(rtl) == proof['rtl_sha256'] and digest(vectors) == proof['vectors_sha256'], 'Proof file digest differs')
        require(rtl == verification_rtl(formulas), 'Verified original RTL identity differs')
        trees = [oracle.parse(f) for f in formulas]
        lines = vectors.decode().splitlines()
        require(len(lines) == VECTORS, 'Vector count differs')
        for vector_index, ((a, b), line) in enumerate(zip(input_pairs(), lines)):
            fields = line.split()
            require(len(fields) == COUNT + 2 and all(re.fullmatch('[0-9a-f]{8}', f) for f in fields), 'Vector shape differs')
            words = [int(f, 16) for f in fields]
            require(words[:2] == [a, b], 'Vector seed/boundaries differ')
            for formula_index, tree in enumerate(trees):
                expected = oracle.evaluate(tree, a, b)
                require(words[formula_index + 2] == expected, f'Independent expected-output mismatch vector{vector_index} formula{formula_index}')
                comparisons += 1
        log = 'verification-wrapv.log' if proof.get('signed_overflow_workaround_applied') else 'verification.log'
        require(data(folder + log).decode().strip() == '2148 vectors passed', 'Successful archived RTL execution log missing')
        if proof.get('signed_overflow_workaround_applied'):
            require(digest(data(folder + 'yosys-boundary-cross-check/eval.log')) == proof['independent_yosys_log_sha256'], 'Boundary cross-check digest differs')
        for formula in formulas:
            label, metric = label_index[formula], metric_index[formula]
            folder = 'circuits/' + digest(formula.encode())[:20] + '/'
            require(json.loads(data(folder + 'metrics.json')) == metric, 'Archived metric identity differs')
            require(metric.get('tool') == tool['version'] and metric.get('tool_sha256') == tool['executable_sha256'], 'Mapped tool identity differs')
            require(metric.get('measurement_source') == label.get('measurement_source') == 'rtl_synthesis'
                and label.get('correctness_verified') is True, 'Target provenance differs')
            require(data(folder + 'candidate.v') == original_rtl(formula), 'Mapped original RTL identity differs')
            for name, key in (('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'),
                              ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')):
                require(digest(data(folder + name)) == metric[key], 'Mapped raw file hash differs: ' + name)
            require(label['rtl_sha256'] == metric['rtl_sha256'], 'Label RTL identity differs')
            script = data(folder + 'ice40.ys').decode().splitlines()
            require(len(script) == 5 and script[0].startswith('read_verilog "') and script[0].endswith('/candidate.v"')
                and script[1:3] == ['synth_ice40 -top candidate', 'check -assert']
                and script[3].startswith('write_json "') and script[3].endswith('/ice40-netlist.json"')
                and script[4] == 'stat', 'Unexpected original iCE40 target pass pipeline')
            netlist = json.loads(data(folder + 'ice40-netlist.json'))
            cells = Counter(cell['type'] for cell in netlist['modules']['candidate'].get('cells', {}).values())
            require(dict(cells) == metric['ice40_cell_types'], 'Mapped netlist cell recount differs')
            for label_key, metric_key, cell in (('lut4_count', 'ice40_lut4_count', 'SB_LUT4'), ('carry_count', 'ice40_carry_count', 'SB_CARRY')):
                require(integer(label[label_key]) == integer(metric[metric_key]) == cells[cell], 'LUT4/carry resource recount differs')
            if 'released_at_utc' in done:
                require(utc(done['released_at_utc']) <= utc(metric['measured_at_utc']) <= utc(done['completed_at_utc']), 'Target measurement chronology differs')
            recounts.append({'formula': formula, 'lut4_count': cells['SB_LUT4'], 'carry_count': cells['SB_CARRY']})
    return {'passed': True, 'archive_sha256': sha(archive), 'archive_members_authenticated': len(records),
        'independent_expected_outputs_recomputed': comparisons, 'original_rtl_identities_checked': len(recounts),
        'netlists_recounted': len(recounts), 'netlist_recounts': recounts}


def run(root, readiness):
    root = Path(root).resolve()
    ready = read(readiness)
    require(ready['audit_source_sha256'] == sha(__file__) and ready['oracle_source_sha256'] == sha(HERE / 'unsigned_oracle.py'), 'Prepared independent source changed')
    for name, key in (('preparation.json', 'preparation_sha256'), ('recipe.json', 'recipe_sha256'), ('candidates.json', 'candidates_sha256')):
        require(sha(root / name) == ready[key], 'Prepared input identity differs')
    preparation, recipe, candidates = read(root / 'preparation.json'), read(root / 'recipe.json'), read(root / 'candidates.json')
    require(ready['expected_original_rtl'] == [{'formula': r['formula'], 'sha256': digest(original_rtl(r['formula']))} for r in candidates], 'Prepared original RTL hashes differ')
    bindings = {}
    for entry in preparation['files']:
        path = (root / entry['path']).resolve()
        require(sha(path) == entry['sha256'], 'Frozen source/input binding changed')
        bindings[path] = entry['sha256']
    collector = next(p for p in bindings if p.name == 'measure_v9_coverage.py')
    approval = read(root / 'measurement-approval.json')
    expected = {'preparation_sha256': ready['preparation_sha256'], 'recipe_sha256': ready['recipe_sha256'],
        'candidates_sha256': ready['candidates_sha256'], 'collector_sha256': bindings[collector]}
    require(approval.get('status') == 'approved-v9-coverage-measurements' and all(approval.get(k) == v for k, v in expected.items()), 'Parent measurement approval differs')
    release = read(root / 'label-release.json')
    expected.update({'approval_sha256': sha(root / 'measurement-approval.json'), 'freeze_commit': approval['freeze_commit'],
        'verification_seed': SEED, 'vectors_per_formula': VECTORS, 'workers': 2, 'candidate_count': COUNT, 'frozen_tool': recipe['frozen_tool']})
    require(all(release.get(k) == v for k, v in expected.items()) and release.get('schema') == 'isaforge-v9-coverage-label-release-v1', 'Target release identity differs')
    require(utc(preparation['prepared_at_utc']) <= utc(approval['reviewed_at_utc']) <= utc(release['released_at_utc']), 'Preparation/approval/release chronology differs')
    directory = root / 'measurements'
    done = read(directory / 'completion.json')
    require(done.get('schema') == 'isaforge-v9-coverage-measurements-v1' and done.get('complete') is True and done.get('failures') == [], 'Complete successful coverage batch required')
    require(all(done.get(k) == v for k, v in expected.items() if k != 'candidate_count'), 'Completion/release identity differs')
    require(done.get('candidate_count') == done.get('unique_original_formulas') == done.get('new_physical_measurements') == COUNT
        and done.get('verification_batch_sizes') == [COUNT] and done.get('original_rtl_only') is True
        and done.get('legacy_measurements_reused') is False and done.get('new_estimator_fits') == 0, 'Fixed complete48 original-only batch required')
    require(re.fullmatch('attempt-[0-9]{4}', done['attempt']) is not None and done['scratch_directory'] == PREFIX + done['attempt'], 'Owned target attempt identity differs')
    require(done['release_sha256'] == sha(root / 'label-release.json') and utc(release['released_at_utc']) <= utc(done['completed_at_utc']), 'Completion release/chronology differs')
    stage = directory / done['attempt']
    require(read(stage / 'completion.json') == done, 'Stage/root completion differs')
    values = {}
    for filename, key in (('labels.json', 'labels_sha256'), ('unique-measurements.json', 'unique_measurements_sha256'), ('verification.json', 'verification_sha256')):
        require(sha(stage / filename) == done[key], 'Completed output digest differs')
        values[filename] = read(stage / filename)
    validation_source = next(p for p in bindings if p.name == 'v4_validation.py')
    require(len(values['verification.json']) == 1
        and values['verification.json'][0].get('v4_validation_override_sha256') == bindings[validation_source],
        'Wrapping-verifier frozen source identity differs')
    result = raw_checks(root, candidates, values['labels.json'], values['unique-measurements.json'], values['verification.json'],
        {**done, 'released_at_utc': release['released_at_utc']}, recipe['frozen_tool'])
    result.update({'schema': 'independent-v9-coverage-raw-audit-v1', 'audited_at_utc': datetime.now(timezone.utc).isoformat(),
        'readiness_sha256': sha(readiness), 'audit_source_sha256': sha(__file__), 'oracle_source_sha256': sha(HERE / 'unsigned_oracle.py'),
        'preparation_sha256': ready['preparation_sha256'], 'completion_sha256': sha(directory / 'completion.json'),
        'scope': 'Independent sampled expected-output replay, exact original-RTL bytes, archive authentication and resource recount. Archived successful logs link vectors to the collected RTL runs; no new RTL/native execution, model import or fitting. Not a universal equivalence proof.'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--released', action='store_true')
    parser.add_argument('--readiness', type=Path, default=HERE / 'audit-readiness.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.prepare:
        require(not args.released, 'Choose input preparation or released audit')
        value = input_snapshot(args.root)
    else:
        if not args.released:
            parser.error('Explicit parent release and --released required before target I/O')
        value = run(args.root, args.readiness)
    write(args.output, value)
    print(json.dumps({k: v for k, v in value.items() if k not in ('netlist_recounts', 'expected_original_rtl')}, indent=2))
