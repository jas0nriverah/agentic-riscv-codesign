#!/usr/bin/env python3
"""Independent stdlib-only V13 raw measurement replay; no production imports.

Checks saved evidence only. The pinned V9 unsigned oracle is shared explicitly;
the restricted RTL renderer and provenance/resource audit are implemented here.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path, PurePosixPath
import posixpath
import random
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / 'results/2026-10-15-v9-coverage-development/independent-audit/unsigned_oracle.py'
ORACLE_SHA = '6d97a070e15e7ccad75051cf641ea7526be9ed25239b3622c405755985d983c3'
COUNT, SEED, VECTORS = 48, 2026101529, 2148
ATTEMPT = 'attempt-0000'
PREFIX = 'generated/v13-coverage-measurements/' + ATTEMPT
BASE_TOOLS = 'results/2026-10-15-v10d-csd-hardware/tools.json'
BASE_TOOLS_SHA = 'ee267f729fb235c4a60b0688b9130cea987bcbf7076a347b0316d8f7089f547a'
FAILED_ROOT = 'results/2026-10-15-v13-coverage-development'
FAILED_COMPLETION_SHA = '1867ba13580064ee26efe876598fc6d7385ffd91d0a93a58375b8697058f5332'
FAILED_ARCHIVE_SHA = 'f426981b14560439572249003b240aa8815d8e4874326bd215b46a34dc330283'
INPUT_FILES = ('preparation.json', 'recipe.json', 'candidates.json', 'consumed-input-ledger.json', 'duplicate-analysis.json', 'coverage-diagnostics.json')


def need(condition, message):
    if not condition: raise ValueError(message)


def digest(data): return hashlib.sha256(data).hexdigest()
def sha(path): return digest(Path(path).read_bytes())


def loads(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def read(path): return loads(Path(path).read_bytes())


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def integer(value):
    need(type(value) is int and value >= 0, 'Nonnegative integer required')
    return value


def utc(value):
    result = datetime.fromisoformat(value)
    need(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, 'UTC timestamp required')
    return result


def oracle_module():
    need(sha(ORACLE) == ORACLE_SHA, 'Pinned unsigned oracle changed')
    spec = importlib.util.spec_from_file_location('v13_independent_unsigned_oracle', ORACLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oracle = oracle_module()


def original_rtl(formula, module='candidate'):
    """Independent exact-byte renderer restricted to the fixed V13 grammar."""
    tree = oracle.parse(formula)
    lines = [f'module {module}(input wire [31:0] in0, in1, output wire [31:0] result);']
    names = {}
    def emit(node):
        if type(node) is int: return f"32'h{node & 0xffffffff:08x}"
        if isinstance(node, str): return node
        if node in names: return names[node]
        op = node[0]
        need(op in ('add', 'addi', 'sub', 'andi', 'ori', 'xori', 'slli', 'srli', 'srai', 'sra', 'slt', 'sltu', 'mulhsu'), 'Unsupported V13 renderer operation')
        a, b = [emit(child) for child in node[1:]]
        name = f'n{len(names)}'; names[node] = name
        symbols = {'add': '+', 'addi': '+', 'sub': '-', 'andi': '&', 'ori': '|', 'xori': '^'}
        if op in symbols: expression = a + ' ' + symbols[op] + ' ' + b
        elif op in ('slli', 'srli', 'srai', 'sra'):
            lines.extend([f'wire [31:0] shift_{name} = {b};', f'wire [31:0] value_{name} = {a};'])
            prior = f'value_{name}'
            for bit in range(5):
                distance = 2 ** bit
                if op == 'slli': shifted = '{' + f"{prior}[{31-distance}:0], {distance}'b0" + '}'
                elif op == 'srli': shifted = '{' + f"{distance}'b0, {prior}[31:{distance}]" + '}'
                else: shifted = '{{' + str(distance) + '{' + f'{prior}[31]' + '}}, ' + f'{prior}[31:{distance}]' + '}'
                stage = f'stage_{name}_{bit}'
                lines.append(f'wire [31:0] {stage} = shift_{name}[{bit}] ? {shifted} : {prior};')
                prior = stage
            expression = prior
        elif op in ('slt', 'sltu'):
            compare = f'$signed({a}) < $signed({b})' if op == 'slt' else f'{a} < {b}'
            expression = "{31'b0, (" + compare + ')}'
        else:
            left, right, product = f'a_{name}', f'b_{name}', f'p_{name}'
            lines.extend([f'wire [31:0] {left} = {a};', f'wire [31:0] {right} = {b};'])
            sign = '{32{' + f'{left}[31]' + '}}'
            lines.append(f"wire signed [63:0] {product} = $signed({{{sign}, {left}}}) * $signed({{32'b0, {right}}});")
            expression = product + '[63:32]'
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
    lines.extend(original_rtl(f, f'candidate_{i}').decode() for i, f in enumerate(formulas))
    return '\n'.join(lines).encode()


def input_pairs():
    rng = random.Random(SEED)
    yield from itertools.product(oracle.BOUNDARIES, repeat=2)
    for _ in range(2048): yield rng.getrandbits(32), rng.getrandbits(32)


def verify_vectors(data, formulas):
    lines = data.decode().splitlines(); need(len(lines) == VECTORS, 'Exactly2148 vectors required')
    trees = [oracle.parse(f) for f in formulas]
    total = 0
    for index, ((a, b), line) in enumerate(zip(input_pairs(), lines)):
        fields = line.split()
        need(len(fields) == COUNT + 2 and all(re.fullmatch('[0-9a-f]{8}', f) for f in fields), 'Invalid vector shape')
        words = [int(f, 16) for f in fields]
        need(words[:2] == [a, b], 'Boundary/random input sequence differs')
        for j, tree in enumerate(trees):
            need(words[j + 2] == oracle.evaluate(tree, a, b), f'Independent output differs at vector{index}/formula{j}')
            total += 1
    return total


def bound_files(manifest, root):
    result = {}
    for entry in manifest['files']:
        need(set(entry) == {'path', 'sha256'} and not Path(entry['path']).is_absolute(), 'Relative binding required')
        path = (root / entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in result and path.is_file() and sha(path) == entry['sha256'], 'Changed/duplicate frozen file: ' + entry['path'])
        result[path] = entry['sha256']
    return result


def check_native_log(text, metric, tools, original_path):
    """Resolve recorded ABC/library identities without accessing native tools."""
    executable = tools['executables']['abc']; observed = []
    commands = re.findall(r'Running ABC command:\s*(?:"([^"]+)"|(\S+))', text)
    need(bool(commands), 'Actual ABC invocation missing')
    for quoted, plain in commands:
        name = quoted or plain
        if name == '<yosys-exe-dir>/yosys-abc': name = str(PurePosixPath(tools['executables']['yosys']['path']).parent / 'yosys-abc')
        need(name == executable['path'], 'Actual ABC executable differs')
        observed.append({'path': executable['path'], 'sha256': executable['sha256']})
    need(same(observed, metric['abc_invocations']), 'ABC evidence differs')
    base = PurePosixPath(tools['yosys_data']['path']); inventory = {r['path']: r['sha256'] for r in tools['yosys_data']['files']}
    observed = {}
    for name in re.findall(r"Parsing Verilog input from [`']([^']+)'", text):
        if name == original_path: continue
        # Yosys emits its sealed bin/../share path. Resolve lexical dot segments
        # without consulting the replay host's filesystem or installed tools.
        path = PurePosixPath(posixpath.normpath(name))
        need(path.is_absolute() and path.is_relative_to(base), 'Unsealed synthesis library')
        relative = path.relative_to(base).as_posix(); need(relative in inventory, 'Unknown synthesis data member')
        item = observed.setdefault(relative, {'sha256': inventory[relative], 'resolved_path': str(path), 'logged_paths': []})
        if name not in item['logged_paths']: item['logged_paths'].append(name)
    need('ice40/cells_sim.v' in observed and same(observed, metric['data_invocations']), 'Actual data-library evidence differs')


def validate_recovery(root, plan, tools, bindings):
    """Explicit V13b prelabel recovery, with the original zero-label failure kept."""
    previous = ROOT / FAILED_ROOT; stage = previous / 'measurements' / ATTEMPT
    need(sha(previous / 'measurements/completion.json') == FAILED_COMPLETION_SHA
         and sha(stage / 'raw-evidence.zip') == FAILED_ARCHIVE_SHA, 'Exact original failed attempt required')
    old = read(previous / 'measurements/completion.json')
    need(old['complete'] is False and old['failures'] and same(old, read(stage / 'completion.json')), 'Original failure must remain incomplete')
    for key in ('new_physical_measurements', 'verified_comparisons', 'new_estimator_fits'):
        need(type(old[key]) is int and old[key] == 0, 'Recovery requires original zero labels/comparisons/fits')
    for name in ('labels', 'unique-measurements', 'verification'):
        need(read(stage / (name + '.json')) == [], 'Original failed attempt contains targets/proof')
    old_manifest = read(stage / 'raw-evidence.json')
    need(old_manifest['archive_sha256'] == FAILED_ARCHIVE_SHA and old_manifest['completion_sha256'] == FAILED_COMPLETION_SHA
         and old_manifest['complete'] is False, 'Original failed archive closure differs')
    required = [previous / n for n in INPUT_FILES]
    required.extend(previous / n for n in ('measurement-plan.json', 'measurement-tools.json', 'measurement-approval.json', 'label-release.json', 'measurements/completion.json'))
    required.extend(stage / n for n in ('completion.json', 'raw-evidence.json', 'raw-evidence.zip', 'labels.json', 'unique-measurements.json', 'verification.json'))
    for name in INPUT_FILES: need((root / name).read_bytes() == (previous / name).read_bytes(), 'Recovery changed prepared scientific inputs')
    amendment_path = root / 'recovery-amendment.json'; amendment = read(amendment_path)
    expected = {'schema': 'isaforge-v13b-prelabel-recovery-v1', 'source_root': FAILED_ROOT,
                'source_freeze_commit': '6d7721e89104fac0f9fe255b81b2f0f6c3b021a5',
                'failed_completion_sha256': FAILED_COMPLETION_SHA, 'failed_raw_archive_sha256': FAILED_ARCHIVE_SHA}
    need(all(amendment.get(k) == v for k, v in expected.items()) and plan['recovery_amendment_sha256'] == sha(amendment_path), 'Explicit prelabel recovery amendment differs')
    required.append(amendment_path)
    diagnosis = ROOT / 'generated/v13-sdk-preflight'; probe = ROOT / 'generated/v13b-sdk-preflight/attempt-0000'
    required.extend(diagnosis / n for n in ('report.json', 'probe.cpp', 'frozen_env.log', 'explicit_sdk.log', 'shim_first.log'))
    required.extend(probe / n for n in ('report.json', 'probe.cpp', 'collector-source.py', 'tools.json', 'build.log', 'run.log'))
    need(all(bindings.get(p) == sha(p) for p in required), 'Plan omits recovery evidence closure')
    diagnostic = read(diagnosis / 'report.json'); runs = {r['name']: r for r in diagnostic['runs']}
    need(runs['frozen_env']['returncode'] != 0 and runs['explicit_sdk']['returncode'] == runs['explicit_sdk']['executable_returncode'] == 0
         and diagnostic['source_sha256'] == sha(diagnosis / 'probe.cpp'), 'Original SDK diagnosis differs')
    for row in runs.values(): need(sha(diagnosis / (row['name'] + '.log')) == row['log_sha256'], 'SDK diagnosis log differs')
    proof = read(probe / 'report.json'); probe_tools = read(probe / 'tools.json')
    need(proof['schema'] == 'isaforge-v13b-sdk-header-preflight-v1' and proof['complete'] is True and proof['error'] is None
         and len(proof['runs']) == 2, 'Actual recovery-owner header preflight required')
    for key in ('rtl_comparisons', 'physical_labels', 'estimator_fits'):
        need(type(proof[key]) is int and proof[key] == 0, 'Header preflight must be noncohort')
    need(proof['environment'] == probe_tools['environment'] == tools['environment']
         and proof['environment']['SDKROOT'] == probe_tools['sdk']['path'] == tools['sdk']['path']
         and probe_tools['sdk'] == tools['sdk'] and proof['tools_sha256'] == sha(probe / 'tools.json')
         and proof['collector_source_sha256'] == sha(probe / 'collector-source.py')
         and (probe / 'collector-source.py').read_bytes() == (ROOT / 'scripts/measure_v13b_coverage.py').read_bytes()
         and proof['source_sha256'] == sha(probe / 'probe.cpp'), 'Recovery SDK/source/owner environment differs')
    need({r['name'] for r in proof['runs']} == {'build', 'run'}, 'Header preflight execution grid differs')
    for row in proof['runs']: need(type(row['returncode']) is int and row['returncode'] == 0 and sha(probe / (row['name'] + '.log')) == row['log_sha256'], 'Header preflight runtime differs')
    need(utc(proof['completed_at_utc']) <= utc(plan['created_at_utc']), 'Recovery plan predates passing preflight')
    return {'preserved_failed_completion_sha256': FAILED_COMPLETION_SHA, 'preserved_failed_archive_sha256': FAILED_ARCHIVE_SHA,
            'recovery_amendment_sha256': sha(amendment_path), 'header_preflight_sha256': sha(probe / 'report.json'),
            'same_prepared_input_files': len(INPUT_FILES), 'prior_labels_comparisons_fits': 0,
            'bound_evidence': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in required]}


def run(root):
    root = Path(root).resolve()
    prep, plan = read(root / 'preparation.json'), read(root / 'measurement-plan.json')
    profiles = {'isaforge-v13-coverage-measurement-plan-v1': 'v13', 'isaforge-v13b-coverage-measurement-plan-v1': 'v13b'}
    need(plan.get('schema') in profiles, 'Explicit V13/V13b measurement profile required')
    profile = profiles[plan['schema']]
    prefix = 'generated/' + profile + '-coverage-measurements/' + ATTEMPT
    need(prep['schema'] == 'isaforge-v13-coverage-preparation-v1' and prep['status'] == 'prepared-inputs-only', 'V13 input preparation required')
    need(plan['status'] == 'prepared-no-native-jobs', 'V13 native plan required')
    bindings = bound_files(prep, root); planned = bound_files(plan, root)
    need(all(planned.get(p) == h for p, h in bindings.items()) and planned.get(root / 'preparation.json') == sha(root / 'preparation.json'), 'Plan omits input preparation closure')
    for name in ('preparation', 'recipe', 'candidates'): need(plan[name + '_sha256'] == sha(root / (name + '.json')), 'Plan input identity differs')
    need(plan['tools'] == {'path': 'measurement-tools.json', 'sha256': sha(root / 'measurement-tools.json')}, 'Tool plan digest differs')
    tools = read(root / 'measurement-tools.json')
    need(tools['schema'] == 'isaforge-' + profile + '-coverage-tools-v1' and tools['inherited_inventory'] == {'path': BASE_TOOLS, 'sha256': BASE_TOOLS_SHA}
         and sha(ROOT / BASE_TOOLS) == BASE_TOOLS_SHA, 'Historical synthesis inventory differs')
    historical = read(ROOT / BASE_TOOLS)
    need(tools['yosys_data'] == historical['yosys_data'] and all(tools['executables'][k] == v for k, v in historical['executables'].items()), 'Synthesis tool/data identity differs')
    recovery = validate_recovery(root, plan, tools, planned) if profile == 'v13b' else None
    policy = plan['policy']
    for key, value in {'seed': SEED, 'random_vectors': 2048, 'boundary_vectors': 100, 'total_vectors': VECTORS, 'workers': 2,
                       'worker_timeout_seconds': 360, 'candidate_count': COUNT, 'retries': 0, 'replacement_candidates': 0, 'new_estimator_fits': 0}.items():
        need(type(policy.get(key)) is int and policy[key] == value, 'Fixed native policy differs')
    need(policy['original_rtl_only'] is True, 'Original-only policy required')
    candidates = read(root / 'candidates.json'); formulas = sorted(r['formula'] for r in candidates)
    need(len(candidates) == len(set(formulas)) == len({r['candidate_id'] for r in candidates}) == COUNT, 'Exactly48 original identities required')
    approval, release = read(root / 'measurement-approval.json'), read(root / 'label-release.json')
    expected = {name + '_sha256': sha(root / (name.replace('_', '-') + '.json')) for name in ('preparation', 'recipe', 'candidates', 'measurement_plan')}
    expected.update(tools_sha256=sha(root / 'measurement-tools.json'), collector_sha256=sha(ROOT / ('scripts/measure_' + profile + '_coverage.py')),
                    collector_tests_sha256=sha(ROOT / ('tests/test_measure_' + profile + '_coverage.py')))
    if recovery is not None: expected['recovery_amendment_sha256'] = recovery['recovery_amendment_sha256']
    need(approval['status'] == 'approved-' + profile + '-coverage-measurements' and all(approval.get(k) == v for k, v in expected.items())
         and re.fullmatch('[0-9a-f]{40}', approval['freeze_commit']), 'Exact approved release required')
    need(release['schema'] == 'isaforge-' + profile + '-coverage-label-release-v1' and release['freeze_commit'] == approval['freeze_commit']
         and same(release['policy'], policy) and all(release.get(k) == v for k, v in expected.items() if k != 'collector_tests_sha256')
         and release['approval_sha256'] == sha(root / 'measurement-approval.json'), 'Label release differs')
    need(utc(prep['created_at_utc']) <= utc(plan['created_at_utc']) <= utc(approval['reviewed_at_utc']) <= utc(release['released_at_utc']), 'Release chronology differs')
    directory = root / 'measurements'; stage = directory / ATTEMPT; done = read(directory / 'completion.json')
    need(done['schema'] == 'isaforge-' + profile + '-coverage-measurements-v1' and done['complete'] is True and done['failures'] == [] and same(done, read(stage / 'completion.json')), 'Complete matching stage/root completion required')
    for key, value in {'candidate_count': COUNT, 'new_physical_measurements': COUNT, 'verified_comparisons': COUNT * VECTORS,
                       'verification_seed': SEED, 'vectors_per_formula': VECTORS, 'workers': 2, 'new_estimator_fits': 0}.items():
        need(type(done.get(key)) is int and done[key] == value, 'Completed count differs')
    need(done['attempt'] == ATTEMPT and done['scratch_directory'] == prefix and done['verification_batch_sizes'] == [COUNT]
         and done['original_rtl_only'] is True and done['legacy_measurements_reused'] is False, 'Single original-only attempt required')
    need(all(done.get(k) == v for k, v in release.items() if k.endswith('_sha256')) and done['release_sha256'] == sha(root / 'label-release.json')
         and done['freeze_commit'] == approval['freeze_commit'], 'Completion release identity differs')
    need(utc(release['released_at_utc']) <= utc(done['completed_at_utc']), 'Completion predates release')
    values = {}
    for name, key in [('labels', 'labels_sha256'), ('unique-measurements', 'unique_measurements_sha256'), ('verification', 'verification_sha256')]:
        need(sha(stage / (name + '.json')) == done[key], 'Completed stage digest differs')
        values[name] = read(stage / (name + '.json'))
    labels, metrics, proofs = values['labels'], values['unique-measurements'], values['verification']
    need(len(labels) == len(metrics) == COUNT and [r['formula'] for r in labels] == [r['formula'] for r in candidates]
         and [r['formula'] for r in metrics] == formulas, 'Exact candidate/label/metric order required')
    for candidate, label in zip(candidates, labels): need(all(same(label[k], v) for k, v in candidate.items()), 'Candidate metadata differs')
    need(len(proofs) == 1, 'Single full verification batch required'); proof = proofs[0]
    for key, value in {'verified': True, 'formula_count': COUNT, 'vectors_per_formula': VECTORS, 'total_comparisons': COUNT * VECTORS, 'random_seed': SEED}.items():
        need(type(proof.get(key)) is type(value) and proof[key] == value, 'Complete verification counts required')
    need(proof['v4_validation_override_sha256'] == planned[ROOT / 'isaforge/v4_validation.py']
         and type(proof['signed_overflow_workaround_applied']) is bool, 'Verification implementation differs')
    manifest = read(stage / 'raw-evidence.json'); archive = stage / 'raw-evidence.zip'
    need(manifest['schema'] == 'isaforge-' + profile + '-coverage-raw-evidence-v1' and manifest['archive'] == archive.name and manifest['attempt'] == ATTEMPT
         and manifest['complete'] is True and manifest['compiler_objects_included'] is False
         and manifest['completion_sha256'] == sha(stage / 'completion.json') and manifest['archive_sha256'] == sha(archive), 'Raw archive identity differs')
    records = {r['path']: r for r in manifest['files']}; need(len(records) == len(manifest['files']) > 0, 'Duplicate/empty archive manifest')
    recounts = []; index = {r['formula']: r for r in labels}
    with zipfile.ZipFile(archive) as raw:
        need(len(raw.namelist()) == len(set(raw.namelist())) and set(raw.namelist()) == set(records), 'Exact archive inventory required')
        for info in raw.infolist():
            name = info.filename; path = PurePosixPath(name); entry = records[name]
            need(not path.is_absolute() and '..' not in path.parts and '\\' not in name and str(path) == name and not info.is_dir()
                 and ((info.external_attr >> 16) & 0o170000) in (0, 0o100000), 'Unsafe archive member')
            data = raw.read(info); need(type(entry['size']) is int and len(data) == entry['size'] and digest(data) == entry['sha256'], 'Raw member digest differs')
        def data(name): return raw.read(name)
        for name in ('preparation', 'recipe', 'candidates', 'measurement-plan', 'measurement-tools', 'measurement-approval', 'label-release'):
            need(data(name + '.json') == (root / (name + '.json')).read_bytes(), 'Archived release input differs')
        for name in ('verification', 'unique-measurements', 'labels', 'completion'):
            need(data('stage/' + name + '.json') == (stage / (name + '.json')).read_bytes(), 'Archived stage differs')
        for path, h in planned.items():
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith(('scripts/', 'isaforge/', 'tests/')) or relative == 'docs/v13-coverage-protocol.md':
                need(digest(data('sources/' + relative)) == h, 'Archived source differs')
        if recovery is not None:
            for entry in recovery['bound_evidence']:
                need(digest(data('recovery-evidence/' + entry['path'])) == entry['sha256'], 'Archived recovery evidence differs')
        folder = 'verification/batch-0000/'
        rtl, vector_data = data(folder + 'verification.v'), data(folder + 'vectors.txt')
        need(digest(rtl) == proof['rtl_sha256'] and rtl == verification_rtl(formulas) and digest(vector_data) == proof['vectors_sha256'], 'Original verified RTL/vector identity differs')
        comparisons = verify_vectors(vector_data, formulas)
        runtime = 'verification-wrapv.log' if proof['signed_overflow_workaround_applied'] else 'verification.log'
        need(data(folder + runtime).decode().strip() == '2148 vectors passed', 'Successful archived runtime log required')
        need(same(loads(data('verification-0000-worker.result.json')), proof), 'Verification worker result differs')
        if proof['signed_overflow_workaround_applied']:
            need('Mismatch formula' in data(folder + 'initial-failure.log').decode() and same(loads(data(folder + 'initial-failure.json')), proof['incident']), 'Initial simulator failure missing')
            cross = folder + 'yosys-boundary-cross-check/'
            need(digest(data(cross + 'eval.log')) == proof['independent_yosys_log_sha256'] and integer(proof['independent_yosys_boundary_comparisons']) == 100, 'Boundary cross-check differs')
            tree = oracle.parse(proof['incident']['formula']); observations = loads(data(cross + 'observations.json'))
            need(type(proof['incident']['formula_index']) is int and 0 <= proof['incident']['formula_index'] < COUNT
                 and formulas[proof['incident']['formula_index']] == proof['incident']['formula'], 'Workaround incident formula differs')
            expected = [{'in0': a, 'in1': b, 'result': oracle.evaluate(tree, a, b)} for a, b in itertools.product(oracle.BOUNDARIES, repeat=2)]
            need(same(observations, expected), 'Independent workaround boundary outputs differ')
            reported = re.findall(r"Eval result: \\result = (32'[01]+|[0-9]+)\.", data(cross + 'eval.log').decode())
            decoded = [int(v.split("'")[1], 2) if "'" in v else int(v) for v in reported]
            need(decoded == [r['result'] for r in expected], 'Archived boundary execution differs')
        gate = loads(data('verification-gate.json'))
        need(integer(gate['comparison_count']) == COUNT * VECTORS and gate['verification_sha256'] == digest(json.dumps(proof, sort_keys=True).encode()), 'Verification gate differs')
        need(utc(release['released_at_utc']) <= utc(gate['verified_at_utc']) <= utc(done['completed_at_utc']), 'Verification gate chronology differs')
        circuit_ids = {n.split('/')[1] for n in records if n.startswith('circuits/')}
        need(circuit_ids == {digest(f.encode())[:20] for f in formulas}, 'Exactly48 circuit folders required')
        for metric in metrics:
            formula = metric['formula']; label = index[formula]; folder = 'circuits/' + digest(formula.encode())[:20] + '/'
            need(same(loads(data(folder + 'measurement.json')), metric), 'Archived measurement differs')
            worker = {k: v for k, v in metric.items() if k not in ('tool_sha256', 'abc_invocations', 'data_invocations')}
            need(same(loads(data(folder + 'metrics.json')), worker) and same(loads(data(folder + 'worker.result.json')), worker), 'Original worker receipt differs')
            need(metric['tool'] == tools['executables']['yosys']['version'] and metric['tool_sha256'] == tools['executables']['yosys']['sha256'], 'Measured tool differs')
            need(metric['measurement_source'] == label['measurement_source'] == 'rtl_synthesis' and label['correctness_verified'] is True, 'Original target provenance differs')
            need(data(folder + 'candidate.v') == original_rtl(formula) and label['rtl_sha256'] == metric['rtl_sha256'], 'Measured original RTL differs')
            for name, key in [('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'), ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')]:
                need(digest(data(folder + name)) == metric[key], 'Mapped raw file identity differs')
            script = data(folder + 'ice40.ys').decode().splitlines()
            match = re.fullmatch(r'read_verilog "([^"\n]+)"', script[0]) if script else None
            need(match is not None and len(script) == 5, 'Exact synthesis script required')
            original = match[1]; path = PurePosixPath(original)
            need(path.is_absolute() and '..' not in path.parts and original.endswith('/' + prefix + '/' + folder + 'candidate.v'), 'Owned synthesis path differs')
            need(script[1:3] == ['synth_ice40 -top candidate', 'check -assert'] and script[3:] == ['write_json "' + str(path.with_name('ice40-netlist.json')) + '"', 'stat'], 'Fixed original synthesis recipe differs')
            need(metric['command'] == [tools['executables']['yosys']['path'], '-s', str(path.with_name('ice40.ys'))], 'Actual synthesis command differs')
            check_native_log(data(folder + 'ice40.log').decode(), metric, tools, original)
            cells = Counter(c['type'] for c in loads(data(folder + 'ice40-netlist.json'))['modules']['candidate'].get('cells', {}).values())
            need(set(cells) <= {'SB_LUT4', 'SB_CARRY'} and same(dict(cells), metric['ice40_cell_types']), 'Mapped primitive recount differs')
            for label_key, metric_key, cell in [('lut4_count', 'ice40_lut4_count', 'SB_LUT4'), ('carry_count', 'ice40_carry_count', 'SB_CARRY')]:
                need(integer(label[label_key]) == integer(metric[metric_key]) == cells[cell], 'Label/resource count differs')
            start = loads(data(folder + 'measurement-start.json'))
            need(start['formula'] == formula and start['verification_gate_sha256'] == digest(data('verification-gate.json')), 'Per-arm verification gate differs')
            need(utc(gate['verified_at_utc']) <= utc(start['started_at_utc']) <= utc(metric['measured_at_utc']) <= utc(done['completed_at_utc']), 'Target chronology differs')
            recounts.append({'formula': formula, 'lut4_count': cells['SB_LUT4'], 'carry_count': cells['SB_CARRY']})
    return {'schema': 'isaforge-v13-independent-measurement-audit-v1', 'status': 'pass', 'complete': True,
            'measurement_profile': profile,
            'prelabel_recovery': recovery,
            'audited_at_utc': datetime.now(timezone.utc).isoformat(), 'audit_source_sha256': sha(__file__), 'oracle_source_sha256': ORACLE_SHA,
            'preparation_sha256': sha(root / 'preparation.json'), 'measurement_plan_sha256': sha(root / 'measurement-plan.json'),
            'tools_sha256': sha(root / 'measurement-tools.json'), 'approval_sha256': sha(root / 'measurement-approval.json'),
            'completion_sha256': sha(directory / 'completion.json'), 'labels_sha256': done['labels_sha256'], 'raw_archive_sha256': sha(archive),
            'archive_members_authenticated': len(records), 'independent_expected_outputs_recomputed': comparisons,
            'original_rtl_identities_checked': COUNT, 'netlists_recounted': COUNT, 'netlist_recounts': recounts,
            'new_native_jobs': 0, 'new_estimator_fits': 0,
            'scope': 'Independent unsigned expected-output replay, separate restricted original-RTL renderer, source/release/archive chronology and mapped LUT4/carry recount. Shared pinned V9 oracle disclosed. Successful archived simulator logs connect saved vectors to execution; no universal equivalence, fresh native execution, fitting or hermetic OS/SDK claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = run(args.root)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'netlist_recounts'}, indent=2))
