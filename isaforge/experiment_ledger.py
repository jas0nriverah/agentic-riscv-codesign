"""Rebuild a local SQLite projection of automatic-workload evidence.

Raw JSON and the existing read-only workload audit remain authoritative. This
analysis/demo database contains labels and MUST NOT be given to selection policies.
No native evaluation, model fitting, or external service is invoked.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sqlite3

from . import codesign as c
from . import workload_audit

SCHEMA = "isaforge-experiment-ledger-v1"
DDL = """
CREATE TABLE IF NOT EXISTS metadata (schema TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS contexts (
 context_id TEXT PRIMARY KEY, workload TEXT NOT NULL, status TEXT NOT NULL,
 manifest_sha256 TEXT NOT NULL, plan_json TEXT NOT NULL, audit_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_files (
 context_id TEXT NOT NULL REFERENCES contexts, path TEXT NOT NULL,
 sha256 TEXT NOT NULL, PRIMARY KEY(context_id,path));
CREATE TABLE IF NOT EXISTS candidates (
 context_id TEXT NOT NULL REFERENCES contexts, candidate_id TEXT NOT NULL,
 name TEXT NOT NULL, formula TEXT NOT NULL, features_json TEXT NOT NULL,
 PRIMARY KEY(context_id,candidate_id), UNIQUE(context_id,name));
CREATE TABLE IF NOT EXISTS measurements (
 context_id TEXT NOT NULL REFERENCES contexts, evaluation_id TEXT NOT NULL,
 candidate_id TEXT, name TEXT NOT NULL, cycles INTEGER NOT NULL CHECK(cycles>0),
 instructions INTEGER NOT NULL, speedup REAL NOT NULL CHECK(speedup>0),
 integrated_lut4 INTEGER NOT NULL, added_lut4 INTEGER NOT NULL,
 frequency_mhz REAL NOT NULL, timing_feasible INTEGER NOT NULL,
 correctness_verified INTEGER NOT NULL CHECK(correctness_verified=1),
 PRIMARY KEY(context_id,evaluation_id), UNIQUE(context_id,name),
 FOREIGN KEY(context_id,candidate_id) REFERENCES candidates(context_id,candidate_id));
CREATE TABLE IF NOT EXISTS routes (
 context_id TEXT NOT NULL, evaluation_id TEXT NOT NULL, seed INTEGER NOT NULL,
 fmax_mhz REAL NOT NULL, internal_timing_pass INTEGER NOT NULL, device_fits INTEGER NOT NULL,
 PRIMARY KEY(context_id,evaluation_id,seed),
 FOREIGN KEY(context_id,evaluation_id) REFERENCES measurements(context_id,evaluation_id));
CREATE TABLE IF NOT EXISTS failures (
 context_id TEXT NOT NULL REFERENCES contexts, source_path TEXT NOT NULL,
 kind TEXT NOT NULL, authentication TEXT NOT NULL, detail_json TEXT NOT NULL,
 PRIMARY KEY(context_id,source_path));
CREATE TABLE IF NOT EXISTS costs (
 context_id TEXT NOT NULL REFERENCES contexts, source_path TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('native_command','evaluation_wall','failed_attempt_wall')),
 phase TEXT NOT NULL, seconds REAL NOT NULL CHECK(seconds>=0),
 unit TEXT NOT NULL CHECK(unit='seconds'), timer_scope TEXT NOT NULL,
 detail_json TEXT NOT NULL, PRIMARY KEY(context_id,source_path,kind));
CREATE VIEW IF NOT EXISTS workload_summary AS
 SELECT c.context_id,c.workload,c.status,
 (SELECT count(*) FROM candidates x WHERE x.context_id=c.context_id) AS candidates,
 (SELECT count(*) FROM measurements x WHERE x.context_id=c.context_id AND x.candidate_id IS NOT NULL) AS verified_candidates,
 (SELECT max(speedup) FROM measurements x WHERE x.context_id=c.context_id AND timing_feasible=1) AS best_timing_feasible_speedup,
 (SELECT count(*) FROM failures x WHERE x.context_id=c.context_id) AS failure_records
 FROM contexts c;
CREATE VIEW IF NOT EXISTS cost_summary AS
 SELECT context_id,kind,phase,unit,timer_scope,count(*) AS records,sum(seconds) AS seconds
 FROM costs GROUP BY context_id,kind,phase,unit,timer_scope;
"""


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _seconds(value):
    c.require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
              "Invalid elapsed seconds")
    return value


def _path(root, relative):
    c.require(isinstance(relative, str) and not Path(relative).is_absolute(), "Expected relative evidence path")
    result = (root / relative).resolve()
    c.require(result.is_relative_to(root), "Evidence path escapes experiment root")
    return result


def _strict_read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            c.require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Non-finite JSON value: " + value)
    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def project(root, *, incomplete=False):
    """Authenticate evidence before opening the database; never infer absent labels.

    Incomplete mode authenticates the plan, inputs, sources and command receipts;
    it imports no performance labels. Unsealed failure files are explicitly marked
    observed, rather than authenticated by a historical checksum.
    """
    root = Path(root).resolve()
    sources = {}

    def include(relative, expected=None):
        path = _path(root, relative)
        actual = c.sha(path)
        c.require(expected is None or actual == expected, "Evidence checksum mismatch: " + relative)
        sources[relative] = actual
        return path

    def sealed(relative):
        path = include(relative)
        sidecar = include(relative + ".sha256")
        c.require(c.sha(path) == sidecar.read_text().strip(), "Sealed evidence changed: " + relative)
        return _strict_read(path)

    plan = sealed("plan.json")
    c.require(plan['schema'] == 'isaforge-automatic-workload-v1', "Unsupported automatic-workload schema")
    context = plan['context_id']
    c.require(c.digest({k: v for k, v in plan.items() if k != 'context_id'}) == context, "Invalid context identity")
    for name, expected in plan['inputs'].items():
        include('inputs/' + name, expected)
    for name, expected in plan['source_bindings'].items():
        snapshot = 'sources/' + name
        if _path(root, snapshot).is_file():
            include(snapshot, expected)
        else:
            c.require(c.sha(c.ROOT / name) == expected, "Source binding differs: " + name)
    commands = ([] if incomplete and not (root / 'commands.json').exists()
                else sealed('commands.json'))
    c.require(isinstance(commands, list), "Commands must be a list")
    costs, failures, candidates, measurements, routes = [], [], [], [], []
    logs = set()
    for command in commands:
        name = command['log']
        c.require(name not in logs, "Duplicate command log: " + name)
        logs.add(name)
        include(name, command['log_sha256'])
        phase = 'baseline' if name.startswith('measurements/baseline/') else (
            'candidate' if name.startswith('measurements/') else 'discovery_or_setup')
        costs.append((context, name, 'native_command', phase, _seconds(command['elapsed_seconds']), 'seconds',
                      'NativeRunner.run monotonic wall time for one subprocess including wait/cleanup; overlaps evaluation_wall', _json(command)))
        if command['failure'] is not None or command['returncode'] != command['expected_returncode']:
            failures.append((context, name, 'native_command', 'sealed_command_receipt', _json(command)))
    for path in sorted(root.rglob('failure.json')):
        if 'obj_dir' in path.parts:
            continue
        name = str(path.relative_to(root))
        record = _strict_read(include(name))
        c.require(isinstance(record.get('error'), str), "Failure record lacks error: " + name)
        failures.append((context, name, 'attempt', 'observed_unsealed_file', _json(record)))
        if 'elapsed_seconds' in record:
            costs.append((context, name, 'failed_attempt_wall', 'failed_attempt', _seconds(record['elapsed_seconds']), 'seconds',
                          'Evaluator failed-attempt monotonic wall time; overlaps native_command', _json(record)))
    checked = {'scope': 'Plan/input/source and available sealed command-log verification only; no performance labels imported.',
               'command_receipts_present': (root / 'commands.json').exists()}
    if not incomplete:
        if 'memory_partition' in plan:
            from .partitioned_workload import audit as partitioned_audit
            checked = partitioned_audit(root)
        else:
            checked = workload_audit.audit(root)
        discovery = sealed('discovery/discovery.json')
        for name, expected in discovery['artifacts'].items():
            include('discovery/' + name, expected)
        names, ids = set(), set()
        for candidate in discovery['pool']:
            name, identity = candidate['name'], candidate['candidate_id']
            c.require(name != 'baseline' and name not in names and identity not in ids, "Duplicate candidate identity/name")
            c.require(identity == c.digest([context, candidate['formula']]), "Candidate identity differs")
            names.add(name); ids.add(identity)
            candidates.append((context, identity, name, candidate['formula'], _json(candidate['features'])))
        expected_paths = {f'measurements/{name}/measurement.json' for name in names | {'baseline'}}
        actual_paths = {str(p.relative_to(root)) for p in (root / 'measurements').glob('*/measurement.json')}
        c.require(actual_paths == expected_paths, "Unexpected or missing measurement records")
        evaluation_ids = set()
        for name in ['baseline', *sorted(names)]:
            source = f'measurements/{name}/measurement.json'
            record = sealed(source)
            c.require(record['evaluation_id'] not in evaluation_ids, "Duplicate evaluation identity")
            evaluation_ids.add(record['evaluation_id'])
            c.require(record['workload'] == plan['workload'] and record['name'] == name, "Measurement workload/name differs")
            if name != 'baseline':
                c.require(record['candidate_id'] == next(x[1] for x in candidates if x[2] == name), "Measurement candidate identity differs")
            for artifact, expected in record['artifacts'].items():
                include(f'measurements/{name}/' + artifact, expected)
            performance = record['performance']
            c.require(type(performance['cycles']) is int and performance['cycles'] > 0, "Invalid cycle label")
            c.require(type(performance['instructions']) is int and performance['instructions'] > 0, "Invalid instruction count")
            c.require(type(record['resources']['lut4_count']) is int and record['resources']['lut4_count'] >= 0
                      and type(record['added_lut4']) is int, "Invalid integrated LUT4 label")
            c.require(type(record['speedup']) in (int, float) and math.isfinite(record['speedup'])
                      and record['speedup'] > 0, "Invalid speedup label")
            c.require(record['frequency_mhz'] == 12.0 and type(record['timing_feasible']) is bool,
                      "Unsupported clock or malformed timing feasibility")
            c.require(name != 'baseline' or record['candidate_id'] is None, "Baseline cannot identify a candidate")
            measurements.append((context, record['evaluation_id'], record['candidate_id'], name, performance['cycles'],
                                 performance['instructions'], record['speedup'], record['resources']['lut4_count'],
                                 record['added_lut4'], record['frequency_mhz'], int(record['timing_feasible']), 1))
            seeds = set()
            for route in record['routes']:
                c.require(route['seed'] not in seeds, "Duplicate routing seed")
                c.require(type(route['seed']) is int and type(route['internal_timing_pass']) is bool
                          and type(route['device_fits']) is bool, "Malformed routing record")
                seeds.add(route['seed'])
                routes.append((context, record['evaluation_id'], route['seed'], route['limiting_internal_fmax_mhz'],
                               int(route['internal_timing_pass']), int(route['device_fits'])))
            costs.append((context, source, 'evaluation_wall', 'baseline' if name == 'baseline' else 'candidate',
                          _seconds(record['elapsed_seconds']), 'seconds',
                          'Evaluator.measure successful-attempt monotonic wall time; excludes prerequisite baseline/discovery; overlaps native_command',
                          _json({'evaluation_id': record['evaluation_id']})))
    manifest = c.digest({'files': sources, 'status': 'incomplete' if incomplete else 'verified_complete'})
    return {'context': (context, plan['workload'], 'incomplete' if incomplete else 'verified_complete', manifest, _json(plan), _json(checked)),
            'source_files': [(context, name, sha) for name, sha in sorted(sources.items())], 'candidates': candidates,
            'measurements': measurements, 'routes': routes, 'failures': failures, 'costs': costs}


def connect(database):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.executescript(DDL)
    existing = connection.execute('SELECT schema FROM metadata').fetchall()
    c.require(not existing or [r[0] for r in existing] == [SCHEMA], "Unsupported ledger schema")
    connection.execute('INSERT OR IGNORE INTO metadata VALUES (?)', (SCHEMA,))
    connection.commit()
    return connection


def import_evidence(database, root, *, incomplete=False):
    projection = project(root, incomplete=incomplete)
    context = projection['context']
    connection = connect(database)
    try:
        with connection:
            previous = connection.execute('SELECT * FROM contexts WHERE context_id=?', (context[0],)).fetchone()
            if previous is not None:
                c.require(tuple(previous) == context, "Context already imported with different evidence; rebuild a fresh projection")
                return {'context_id': context[0], 'imported': False}
            connection.execute('INSERT INTO contexts VALUES (?,?,?,?,?,?)', context)
            for table in ('source_files', 'candidates', 'measurements', 'routes', 'failures', 'costs'):
                rows = projection[table]
                if rows:
                    connection.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in rows[0])})', rows)
        return {'context_id': context[0], 'imported': True}
    finally:
        connection.close()


def export(database):
    """Deterministic JSON containing typed records, retained hashes and SQL summaries."""
    c.require(Path(database).is_file(), "Ledger does not exist")
    connection = sqlite3.connect(f'file:{Path(database).resolve().as_posix()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        c.require([r[0] for r in connection.execute('SELECT schema FROM metadata')] == [SCHEMA], "Unsupported ledger schema")
        result = {'schema': SCHEMA, 'label_access': 'Analysis only; never a selection-policy label source.',
                  'cost_note': 'Cost kinds overlap. Sum only within a stated kind/timer scope; never add command and evaluation wall time.'}
        for table in ('contexts', 'source_files', 'candidates', 'measurements', 'routes', 'failures', 'costs', 'workload_summary', 'cost_summary'):
            rows = [dict(row) for row in connection.execute(f'SELECT * FROM {table}')]
            result[table] = sorted(rows, key=_json)
        return result
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('import', 'summary', 'export'))
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--incomplete', action='store_true', help='Import authenticated metadata/cost/failure records only, with no labels')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'import':
            c.require(args.root is not None, '--root is required for import')
            result = import_evidence(args.db, args.root, incomplete=args.incomplete)
        else:
            result = export(args.db)
            if args.command == 'summary':
                result = {key: result[key] for key in ('schema', 'cost_note', 'workload_summary', 'cost_summary')}
        if args.output:
            c.write(args.output, result)
        else:
            print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError, TypeError, ImportError, sqlite3.Error) as error:
        parser.exit(2, f'Ledger error: {error}\n')


if __name__ == '__main__':
    main()
