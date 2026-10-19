#!/usr/bin/env python3
"""Independent, stdlib-only V8 raw-output and metric audit.

No imports from the experiment, no fitting, RTL execution, or synthesis. Target
I/O is opt-in via --released and must wait for parent label-release approval.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import random
import re
import zipfile

MASK = 0xffffffff
SIGN = 0x80000000
MODELS = ('mapping_v6', 'legacy_original336', 'legacy_rewritten336',
          'dual_graph', 'sog_tuned', 'masterrtl_fixed')
SEEDS = tuple(range(2026101501, 2026101506))
BOUNDARIES = (0, 1, 2, 31, 32, 33, 0x7fffffff, 0x80000000, 0x80000001, MASK)
STRATEGIES = ('predicted_area_feasible_merit', 'merit', 'frequency', 'random')
OPS = set('add addi sub and andi or ori xor xori sll slli srl srli sra srai slt slti sltu sltiu mul mulh mulhsu mulhu lui'.split())


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def file_digest(path):
    return digest(Path(path).read_bytes())


def avg(values):
    values = list(values)
    need(bool(values), 'Empty aggregation is not an endpoint')
    return math.fsum(values) / len(values)


def integer(value, name):
    need(type(value) is int and value >= 0, 'Nonnegative integer required: ' + name)
    return value


def point(value):
    need(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Invalid point')
    return float(value)


def parse(text):
    """Separate expression parser: scan a complete token stream, then build tuples."""
    need(isinstance(text, str) and 0 < len(text) <= 16384, 'Invalid formula text')
    # Reject unrecognized gaps, rather than silently skipping them.
    scanner = re.compile(r'-?[0-9]+|[a-z][a-z0-9]*|[(),]|\s+')
    tokens = []
    end = 0
    for match in scanner.finditer(text):
        need(match.start() == end, 'Unrecognized formula character')
        end = match.end()
        if not match.group().isspace():
            tokens.append(match.group())
    need(end == len(text), 'Trailing unrecognized formula character')
    cursor = 0

    def eat(expected=None):
        nonlocal cursor
        need(cursor < len(tokens), 'Unexpected end of formula')
        token = tokens[cursor]
        need(expected is None or token == expected, 'Expected ' + str(expected))
        cursor += 1
        return token

    def node(depth):
        need(depth <= 128, 'Excessive formula nesting')
        token = eat()
        if re.fullmatch('-?[0-9]+', token):
            need(len(token.lstrip('-')) <= 10, 'Oversized constant')
            value = int(token)
            need(-(1 << 31) <= value <= MASK, 'Constant outside RV32')
            return value
        if token in ('in0', 'in1'):
            return token
        need(token in OPS, 'Unknown operation ' + token)
        eat('(')
        left = node(depth + 1)
        if token == 'lui':
            need(type(left) is int, 'LUI requires decoded integer')
            eat(')')
            return (token, left)
        eat(',')
        right = node(depth + 1)
        eat(')')
        if token.endswith('i') or token in ('slli', 'srli', 'srai', 'sltiu'):
            need(type(right) is int, 'Immediate operation requires integer')
        return (token, left, right)

    result = node(0)
    need(cursor == len(tokens) and isinstance(result, tuple), 'Formula root/trailing tokens invalid')
    return result


def evaluate(tree, a, b):
    """Unsigned datapath oracle; signed comparisons use a sign-bit order transform.

    Arithmetic right shift explicitly inserts high ones; signed multiply high is
    unsigned multiply high minus the unsigned other operand for each sign bit.
    This avoids the production oracle's signed-integer conversion implementation.
    """
    if type(tree) is int:
        return tree & MASK
    if tree == 'in0':
        return a & MASK
    if tree == 'in1':
        return b & MASK
    op = tree[0]
    x = evaluate(tree[1], a, b)
    if op == 'lui':
        return x
    y = evaluate(tree[2], a, b)
    shift = y % 32
    if op in ('add', 'addi'):
        out = x + y
    elif op == 'sub':
        out = x + ((~y) & MASK) + 1
    elif op in ('and', 'andi'):
        out = x & y
    elif op in ('or', 'ori'):
        out = x | y
    elif op in ('xor', 'xori'):
        out = x ^ y
    elif op in ('sll', 'slli'):
        out = x * (1 << shift)
    elif op in ('srl', 'srli'):
        out = x // (1 << shift)
    elif op in ('sra', 'srai'):
        out = x >> shift
        if x & SIGN and shift:
            out |= MASK ^ ((1 << (32 - shift)) - 1)
    elif op in ('slt', 'slti'):
        out = int((x ^ SIGN) < (y ^ SIGN))
    elif op in ('sltu', 'sltiu'):
        out = int(x < y)
    elif op == 'mul':
        out = x * y
    elif op in ('mulh', 'mulhu', 'mulhsu'):
        out = (x * y) // (1 << 32)
        if op in ('mulh', 'mulhsu') and x & SIGN:
            out -= y
        if op == 'mulh' and y & SIGN:
            out -= x
    else:
        raise ValueError('Unhandled operation ' + op)
    return out & MASK


def quantile(values, fraction):
    ordered = sorted(values)
    at = (len(ordered) - 1) * fraction
    low = math.floor(at)
    high = math.ceil(at)
    return ordered[low] + (ordered[high] - ordered[low]) * (at - low)


def errors(actual, predicted):
    need(len(actual) == len(predicted) and bool(actual), 'Incomplete errors vector')
    pairs = [(integer(y, 'area'), point(p)) for y, p in zip(actual, predicted)]
    signed = [p - y for y, p in pairs]
    absolute = [abs(v) for v in signed]
    positives = [abs(p - y) / y for y, p in pairs if y]
    zeros = [p for y, p in pairs if y == 0]
    return {
        'count': len(pairs), 'mae_lut4': avg(absolute),
        'signed_bias_lut4': avg(signed),
        'rmsle': math.sqrt(avg((math.log1p(p) - math.log1p(y)) ** 2 for y, p in pairs)),
        'positive_target_count': len(positives),
        'positive_mape_percent': 100 * avg(positives) if positives else None,
        'zero_target_count': len(zeros), 'zero_mae_lut4': avg(zeros) if zeros else None,
        'p95_absolute_error_lut4': quantile(absolute, .95),
        'p99_absolute_error_lut4': quantile(absolute, .99),
        'worst_absolute_error_lut4': max(absolute),
        'maximum_underprediction_lut4': max([0] + [y - p for y, p in pairs]),
        'underprediction_count': sum(p < y for y, p in pairs),
        'overprediction_count': sum(p > y for y, p in pairs),
        'exact_prediction_count': sum(p == y for y, p in pairs),
        'caps': {str(c): {
            'false_accept_count': sum(p <= c and y > c for y, p in pairs),
            'false_reject_count': sum(p > c and y <= c for y, p in pairs),
            'predicted_feasible_count': sum(p <= c for y, p in pairs),
            'actually_feasible_count': sum(y <= c for y, p in pairs),
            'count': len(pairs)} for c in (32, 64, 128)}}


def inputs(rows, programs, labels, predictions):
    """Validate identities independently before any arithmetic."""
    declared = {p['benchmark']: p for p in programs}
    need(len(declared) == len(programs) == 5, 'Expected five unique declared programs')
    pools = defaultdict(list)
    seen = set()
    for row in rows:
        name = row['benchmark']
        need(name in declared, 'Undeclared program')
        for key in ('family', 'primary_family', 'traceTotalInstructions'):
            need(row[key] == declared[name][key], 'Program metadata differs')
        need(type(row['primary_family']) is bool, 'Invalid family role')
        need(type(row['traceTotalInstructions']) is int and row['traceTotalInstructions'] > 0, 'Invalid trace count')
        integer(row['overlapSafeSaved'], 'saved')
        integer(row['runs'], 'runs')
        need(max(row['overlapSafeSaved'], row['runs']) <= row['traceTotalInstructions'], 'Count exceeds trace')
        parse(row['formula'])
        key = (name, row['candidate_id'])
        need(key not in seen and row['formula'] not in {r['formula'] for r in pools[name]}, 'Duplicate program row')
        seen.add(key)
        pools[name].append(row)
    need(set(pools) == set(declared), 'Incomplete declared pools')
    actual = {r['formula']: integer(r['lut4_count'], 'actual') for r in labels}
    need(len(actual) == len(labels), 'Duplicate original target')
    need(set(actual) == {r['formula'] for r in rows}, 'Incomplete target union')
    need(set(predictions) == set(MODELS), 'Exactly six fixed models required')
    points = {}
    for model, records in predictions.items():
        indexed = {}
        shared = {}
        for record in records:
            key = (record['benchmark'], record['candidate_id'])
            need(key in seen and key not in indexed, 'Unexpected/duplicate prediction')
            row = next(r for r in pools[key[0]] if r['candidate_id'] == key[1])
            need(record['formula'] == row['formula'], 'Prediction formula differs')
            need(record.get('upper_lut4') is None and record.get('upper_margin_lut4') is None, 'Point-only required')
            value = point(record['predicted_lut4'])
            need(record['formula'] not in shared or value == shared[record['formula']], 'Shared formula point differs')
            shared[record['formula']] = value
            indexed[key] = value
        need(set(indexed) == seen, 'Prediction coverage differs')
        points[model] = indexed
    return declared, pools, actual, points


def metrics_and_acquisition(rows, programs, labels, predictions):
    declared, pools, actual, points = inputs(rows, programs, labels, predictions)
    families = defaultdict(list)
    for name, program in declared.items():
        families[program['family']].append(name)
    primary = sorted(f for f, names in families.items() if declared[names[0]]['primary_family'])
    need(len(primary) == 4, 'Exactly four primary families required')
    scores = {}
    for model in MODELS:
        program_scores = {}
        for name, pool in pools.items():
            program_scores[name] = errors([actual[r['formula']] for r in pool],
                [points[model][(name, r['candidate_id'])] for r in pool])
        family_scores = {f: {'program_count': len(names), 'programs': sorted(names),
            'primary_family': declared[names[0]]['primary_family'],
            'equal_program_mae_lut4': avg(program_scores[n]['mae_lut4'] for n in names),
            'application_formula_rows': sum(len(pools[n]) for n in names)} for f, names in families.items()}
        def pooled(selected):
            return errors([actual[r['formula']] for r in selected],
                [points[model][(r['benchmark'], r['candidate_id'])] for r in selected])
        scores[model] = {'by_program': program_scores, 'by_family': family_scores,
            'primary_equal_family_mae_lut4': avg(family_scores[f]['equal_program_mae_lut4'] for f in primary),
            'pooled_all_application_rows': pooled(rows),
            'pooled_primary_application_rows': pooled([r for r in rows if r['primary_family']])}
    deltas = {f: scores['legacy_rewritten336']['by_family'][f]['equal_program_mae_lut4'] -
              scores['mapping_v6']['by_family'][f]['equal_program_mae_lut4'] for f in primary}
    primary_result = {'challenger': 'legacy_rewritten336', 'baseline': 'mapping_v6',
        'difference_lut4': avg(deltas.values()), 'paired_family_differences_lut4': deltas,
        'leave_one_family_out_difference_lut4': {f: avg(d for g, d in deltas.items() if g != f) for f in primary},
        'family_count': len(primary)}
    decisions = []
    aggregates = {}
    # Finish each public acquisition ordering before accessing area for that case.
    for model in MODELS:
        for strategy in STRATEGIES:
            cases = []
            for name in sorted(declared):
                metadata = declared[name]
                lexical = sorted(pools[name], key=lambda r: (r['formula'], r['candidate_id']))
                for seed in SEEDS:
                    public = [(r, points[model][(name, r['candidate_id'])]) for r in lexical]
                    if strategy == 'random':
                        random.Random(seed).shuffle(public)
                    elif strategy == 'frequency':
                        public.sort(key=lambda v: (-v[0]['runs'], v[0]['formula'], v[0]['candidate_id']))
                    elif strategy == 'merit':
                        public.sort(key=lambda v: (-v[0]['overlapSafeSaved'], v[0]['formula'], v[0]['candidate_id']))
                    else:
                        # Explicitly partition by predicted feasibility before ranking.
                        feasible = [v for v in public if v[1] <= 64]
                        other = [v for v in public if v[1] > 64]
                        feasible.sort(key=lambda v: (-v[0]['overlapSafeSaved'], v[0]['formula'], v[0]['candidate_id']))
                        other.sort(key=lambda v: (v[1] - 64, -v[0]['overlapSafeSaved'], v[0]['formula'], v[0]['candidate_id']))
                        public = feasible + other
                    attempted = public[0][0]
                    area = actual[attempted['formula']]
                    selected = attempted if area <= 64 and attempted['overlapSafeSaved'] > 0 else None
                    best = sorted((r for r in lexical if actual[r['formula']] <= 64 and r['overlapSafeSaved'] > 0),
                        key=lambda r: (-r['overlapSafeSaved'], r['formula'], r['candidate_id']))
                    oracle = best[0] if best else None
                    saved = selected['overlapSafeSaved'] if selected else 0
                    oracle_saved = oracle['overlapSafeSaved'] if oracle else 0
                    case = {**{k: metadata[k] for k in ('benchmark', 'family', 'primary_family', 'traceTotalInstructions')},
                        'model': model, 'strategy': strategy, 'cap_lut4': 64, 'budget': 1, 'seed': seed,
                        'candidate_measurements': 1,
                        'attempts': [{'candidate_id': attempted['candidate_id'], 'formula': attempted['formula'],
                            'measured_lut4': area, 'actual_area_violation': area > 64,
                            'overlapSafeSaved': attempted['overlapSafeSaved']}],
                        'attempted_actual_area_violations': int(area > 64),
                        'selected_candidate_id': selected['candidate_id'] if selected else None,
                        'selected_actual_lut4': area if selected else None,
                        'selected_overlapSafeSaved': saved, 'baseline_overlapSafeSaved': 0,
                        'oracle_candidate_id': oracle['candidate_id'] if oracle else None,
                        'oracle_overlapSafeSaved': oracle_saved, 'oracle_full_pool_label_count': len(lexical),
                        'retained_oracle_savings_fraction': saved / oracle_saved if oracle_saved else None,
                        'normalized_regret_percent_trace_instructions': 100 * (oracle_saved - saved) / metadata['traceTotalInstructions']}
                    cases.append(case)
            program_regret = {n: avg(r['normalized_regret_percent_trace_instructions'] for r in cases if r['benchmark'] == n) for n in declared}
            family_regret = {f: avg(program_regret[n] for n in names) for f, names in families.items()}
            program_retention = {}
            for name in declared:
                retained = [r['retained_oracle_savings_fraction'] for r in cases
                            if r['benchmark'] == name and r['retained_oracle_savings_fraction'] is not None]
                program_retention[name] = avg(retained) if retained else None
            family_retention = {}
            for f, names in families.items():
                eligible = [program_retention[n] for n in names if program_retention[n] is not None]
                family_retention[f] = {'eligible_program_count': len(eligible), 'program_count': len(names),
                    'conditional_equal_eligible_program_retention': avg(eligible) if eligible else None}
            eligible_primary = [family_retention[f]['conditional_equal_eligible_program_retention'] for f in primary
                                if family_retention[f]['conditional_equal_eligible_program_retention'] is not None]
            conditional = [r['retained_oracle_savings_fraction'] for r in cases
                           if r['primary_family'] and r['retained_oracle_savings_fraction'] is not None]
            per_seed = {}
            for seed in SEEDS:
                p = {r['benchmark']: r['normalized_regret_percent_trace_instructions'] for r in cases if r['seed'] == seed}
                per_seed[str(seed)] = avg(avg(p[n] for n in families[f]) for f in primary)
            aggregates[f'{model}/{strategy}/cap64/budget1'] = {'model': model, 'strategy': strategy,
                'cap_lut4': 64, 'budget': 1,
                'primary_equal_family_normalized_regret_percent': avg(family_regret[f] for f in primary),
                'by_family_normalized_regret_percent': family_regret, 'by_program_normalized_regret_percent': program_regret,
                'primary_positive_oracle_program_seed_count': len(conditional),
                'primary_conditional_pooled_program_seed_retention': avg(conditional) if conditional else None,
                'per_seed_primary_equal_family_normalized_regret_percent': per_seed,
                'by_family_conditional_retention': family_retention,
                'eligible_primary_family_count': len(eligible_primary), 'primary_family_count': len(primary),
                'primary_equal_eligible_family_conditional_retention': avg(eligible_primary) if eligible_primary else None}
            decisions.extend(cases)
    return {'scores': scores, 'primary': primary_result,
            'selection': {'details': decisions, 'aggregates': aggregates}}


def compare(expected, observed, path='$', mismatches=None):
    """Expected may be a documented subset of the production evaluation."""
    if mismatches is None:
        mismatches = []
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            mismatches.append(path + ': object required')
        else:
            for key, value in expected.items():
                if key not in observed:
                    mismatches.append(path + '.' + str(key) + ': missing')
                else:
                    compare(value, observed[key], path + '.' + str(key), mismatches)
    elif isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            mismatches.append(path + ': list shape differs')
        else:
            for i, (a, b) in enumerate(zip(expected, observed)):
                compare(a, b, f'{path}[{i}]', mismatches)
    elif type(expected) in (float, int) and type(observed) in (float, int):
        if not math.isclose(expected, observed, rel_tol=1e-11, abs_tol=1e-10):
            mismatches.append(f'{path}: {expected!r} != {observed!r}')
    elif expected != observed or type(expected) is not type(observed):
        mismatches.append(f'{path}: {expected!r} != {observed!r}')
    return mismatches


def raw_audit(root, rows, labels, metrics, proofs, done):
    directory = root / 'measurements'
    manifest = read(directory / 'raw-evidence.json')
    archive = directory / manifest['archive']
    need(manifest['archive'] == 'raw-evidence.zip', 'Unexpected raw archive path')
    need(file_digest(archive) == manifest['archive_sha256'], 'Raw archive digest differs')
    need(file_digest(directory / 'completion.json') == manifest['completion_sha256'], 'Completion manifest differs')
    formulas = sorted({r['formula'] for r in rows})
    label_by_formula = {r['formula']: r for r in labels}
    metric_by_formula = {r['formula']: r for r in metrics}
    need(len(labels) == len(metrics) == len(formulas) == 146, 'Exact unique target count required')
    need(set(label_by_formula) == set(metric_by_formula) == set(formulas), 'Target identities differ')
    records = {r['path']: r for r in manifest['files']}
    need(len(records) == len(manifest['files']) > 0, 'Duplicate/empty manifest')
    prefix = 'generated/v8-measurements/' + done['attempt'] + '/'
    output_count = 0
    netlists = []
    with zipfile.ZipFile(archive) as raw:
        need(len(raw.namelist()) == len(set(raw.namelist())) and set(raw.namelist()) == set(records), 'Raw archive membership differs')
        for entry in raw.infolist():
            name = entry.filename
            path = PurePosixPath(name)
            need(name.startswith(prefix) and not path.is_absolute() and '..' not in path.parts and '\\' not in name,
                 'Unsafe/unowned archive name')
            need(str(path) == name and not entry.is_dir() and ((entry.external_attr >> 16) & 0o170000) != 0o120000,
                 'Nonregular archive member')
            data = raw.read(name)
            record = records[name]
            need(len(data) == record.get('size', record.get('bytes')) and digest(data) == record['sha256'], 'Raw member bytes differ: ' + name)

        def data(suffix):
            return raw.read(prefix + suffix)

        need(len(proofs) == 2 and done['verification_batch_sizes'] == [128, 18], 'Expected two batches 128+18')
        for index, proof in enumerate(proofs):
            batch = formulas[index * 128:(index + 1) * 128]
            trees = [parse(f) for f in batch]
            folder = f'verification/batch-{index * 128:04d}/'
            vectors = data(folder + 'vectors.txt')
            rtl = data(folder + 'verification.v')
            need(digest(vectors) == proof['vectors_sha256'] and digest(rtl) == proof['rtl_sha256'], 'Proof file binding differs')
            need(proof['verified'] is True and proof['formula_count'] == len(batch) and proof['vectors_per_formula'] == 2148
                 and proof['total_comparisons'] == 2148 * len(batch) and proof['random_seed'] == 2026101517,
                 'Incomplete vector proof')
            # Ensure expected vector-column j corresponds to the archived physical
            # candidate RTL, rather than trusting only the proof metadata.
            rtl_text = rtl.decode()
            for j, formula in enumerate(batch):
                candidate = data('circuits/' + digest(formula.encode())[:20] + '/candidate.v').decode()
                renamed = candidate.replace('module candidate(', f'module candidate_{j}(', 1)
                need(renamed in rtl_text, 'Verification/physical RTL mismatch for column ' + str(j))
                connection = f'candidate_{j} c{j}(.in0(in0), .in1(in1), .result(out_{j}));'
                need(rtl_text.count(connection) == 1, 'Verification output connection mismatch')
            rng = random.Random(2026101517)
            pairs = list(itertools.product(BOUNDARIES, repeat=2))
            pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(2048))
            lines = vectors.decode().splitlines()
            need(len(lines) == len(pairs) == 2148, 'Vector count differs')
            for i, ((a, b), line) in enumerate(zip(pairs, lines)):
                fields = line.split()
                need(len(fields) == len(batch) + 2 and all(re.fullmatch('[0-9a-f]{8}', f) for f in fields), 'Vector shape differs')
                words = [int(f, 16) for f in fields]
                need(words[:2] == [a, b], 'Vector inputs differ from seed/boundaries')
                for j, tree in enumerate(trees):
                    expected = evaluate(tree, a, b)
                    need(words[j + 2] == expected, f'Independent oracle mismatch batch{index} vector{i} formula{j}')
                    output_count += 1
            log_name = 'verification-wrapv.log' if proof.get('signed_overflow_workaround_applied') else 'verification.log'
            need(data(folder + log_name).decode().strip() == '2148 vectors passed', 'Successful RTL runtime log missing')

        for formula in formulas:
            metric = metric_by_formula[formula]
            label = label_by_formula[formula]
            folder = 'circuits/' + digest(formula.encode())[:20] + '/'
            need(json.loads(data(folder + 'metrics.json')) == metric, 'Archived metric differs')
            for filename, key in (('candidate.v', 'rtl_sha256'), ('ice40.ys', 'script_sha256'),
                                  ('ice40.log', 'log_sha256'), ('ice40-netlist.json', 'netlist_sha256')):
                need(digest(data(folder + filename)) == metric[key], 'Physical evidence hash differs: ' + filename)
            netlist = json.loads(data(folder + 'ice40-netlist.json'))
            cells = Counter(v['type'] for v in netlist['modules']['candidate'].get('cells', {}).values())
            need(dict(cells) == metric['ice40_cell_types'], 'Full cell recount differs')
            for cell, metric_key, label_key in (('SB_LUT4', 'ice40_lut4_count', 'lut4_count'),
                                                ('SB_CARRY', 'ice40_carry_count', 'carry_count')):
                need(integer(label[label_key], label_key) == integer(metric[metric_key], metric_key) == cells[cell], 'Resource recount differs')
            need(label['rtl_sha256'] == metric['rtl_sha256'] and label['correctness_verified'] is True
                 and label['measurement_source'] == metric['measurement_source'] == 'rtl_synthesis', 'Label provenance differs')
            netlists.append({'formula': formula, 'lut4_count': cells['SB_LUT4'], 'carry_count': cells['SB_CARRY']})
    return {'raw_archive_sha256': file_digest(archive), 'raw_member_count': len(records),
            'independent_expected_outputs_recomputed': output_count,
            'vectors_per_formula': 2148, 'batch_sizes': [128, 18],
            'netlists_recounted': len(netlists), 'netlist_recounts': netlists}


def run(root, evaluation=None):
    root = Path(root).resolve()
    rows = read(root / 'rows.json')
    programs = read(root / 'programs.json')
    need(len(rows) == 152 and sum(r['primary_family'] for r in rows) == 150, 'Exact row counts required')
    freeze = read(root / 'point-freeze.json')
    predictions = {}
    for model in MODELS:
        record = freeze['models'][model]['predictions']
        path = (root / record['path']).resolve()
        need(file_digest(path) == record['sha256'], 'Prediction digest differs')
        predictions[model] = read(path)
    done = read(root / 'measurements/completion.json')
    need(done['complete'] is True and done['failures'] == [], 'Complete successful measurements required')
    need(re.fullmatch('attempt-[0-9]{4}', done['attempt']) is not None, 'Invalid attempt identity')
    stage = root / 'measurements' / done['attempt']
    need(read(stage / 'completion.json') == done, 'Stage completion differs')
    loaded = {}
    for name, key in (('labels', 'labels_sha256'), ('unique-measurements', 'unique_measurements_sha256'),
                      ('verification', 'verification_sha256')):
        path = stage / (name + '.json')
        need(file_digest(path) == done[key], 'Target file digest differs')
        loaded[name] = read(path)
    raw = raw_audit(root, rows, loaded['labels'], loaded['unique-measurements'], loaded['verification'], done)
    result = metrics_and_acquisition(rows, programs, loaded['labels'], predictions)
    result.update({'schema': 'independent-v8-result-audit-v1', 'raw': raw,
        'independence': 'No experiment imports, model fit/prediction, synthesis, or RTL execution. Independent unsigned32 oracle checks all archived expected outputs; archived successful runtime logs bind sampled RTL checks.',
        'scope': 'All six fixed model error summaries, paired four-family primary, and every model/strategy/seed/program cap64 budget1 decision and aggregate.',
        'input_hashes': {'rows_sha256': file_digest(root / 'rows.json'),
            'programs_sha256': file_digest(root / 'programs.json'),
            'point_freeze_sha256': file_digest(root / 'point-freeze.json'),
            'completion_sha256': file_digest(root / 'measurements/completion.json'),
            'audit_source_sha256': file_digest(__file__)}})
    if evaluation:
        official = read(evaluation)
        mismatches = compare(result['scores'], official['scores'], '$.scores')
        compare(result['primary'], official['primary'], '$.primary', mismatches)
        compare(result['selection']['aggregates'], official['selection']['aggregates'], '$.selection.aggregates', mismatches)
        def case_key(r):
            return tuple(r[k] for k in ('model', 'benchmark', 'strategy', 'cap_lut4', 'budget', 'seed'))
        observed_cases = {case_key(r): r for r in official['selection']['details'] if r['cap_lut4'] == 64 and r['budget'] == 1}
        expected_cases = {case_key(r): r for r in result['selection']['details']}
        need(set(observed_cases) == set(expected_cases) and len(observed_cases) == 600, 'Primary decision coverage differs')
        for key, value in expected_cases.items():
            compare(value, observed_cases[key], '$.selection.case.' + str(key), mismatches)
        result['production_comparison'] = {'evaluation_sha256': file_digest(evaluation),
            'mismatches': mismatches, 'passed': not mismatches,
            'primary_decisions_compared': len(expected_cases), 'primary_aggregates_compared': len(result['selection']['aggregates'])}
        need(not mismatches, 'Production score mismatches: ' + json.dumps(mismatches[:10]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--released', action='store_true', help='Parent has explicitly authorized target-label audit')
    parser.add_argument('--evaluation', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.released:
        parser.error('Do not read target data before parent notification; explicit --released required')
    value = run(args.root, args.evaluation)
    with args.output.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write('\n')
    print(json.dumps({'output': str(args.output), 'raw': {k: v for k, v in value['raw'].items() if k != 'netlist_recounts'},
        'primary': value['primary'], 'comparison': value.get('production_comparison')}, indent=2))


if __name__ == '__main__':
    main()
