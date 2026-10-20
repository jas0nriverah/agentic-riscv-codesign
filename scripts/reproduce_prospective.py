#!/usr/bin/env python3
"""Archive/replay the preregistered SLRE transfer experiment and build its demo.

Replay authenticates raw evidence and recomputes the fixed predictions; it starts
no hardware jobs. SQLite and HTML are disposable analysis projections, never
selector inputs. Historical experiments and the prelabel commit stay unchanged.
"""
from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge import experiment_ledger as ledger
from isaforge import partitioned_workload as partition
from isaforge import prospective_inputs
from scripts.reproduce_codesign import pack_archive, restore_archive

SNAPSHOT = ROOT / 'results/2026-10-20-slre-transfer'
PREREG = ROOT / 'results/2026-10-20-slre-preregistration'
HISTORY = (ROOT / 'results/2026-10-19-automatic-aha-mont64',
           ROOT / 'results/2026-10-20-automatic-crc32')
PRELABEL_COMMIT = '1c812e1c6c09070ae45931241c37163d53ee05ee'
# Manifest bytes present in the pushed prelabel commit, before collection began.
PREREG_MANIFEST_SHA256 = '78ea0326e42a7b266d5be88b92a5c6c199c2664c89a876e9ce2be7ff62ab9e63'
SELECTION_FILES = ('protocol.json', 'public.json', 'predictions.json', 'report.json')


def authenticate_files(root, manifest_name):
    root = Path(root).resolve()
    entries = c.unseal(root / manifest_name)
    for name, expected in entries.items():
        path = (root / name).resolve()
        c.require(path.is_relative_to(root) and path.is_file(), 'Unsafe/missing manifest entry: ' + name)
        c.require(c.sha(path) == expected, 'Manifest checksum differs: ' + name)
    return entries


def source_path(name):
    path = (ROOT / name).resolve()
    c.require(not Path(name).is_absolute() and path.is_relative_to(ROOT), 'Source path escapes checkout')
    return path


def check_preregistration(prereg, target, selection):
    """Bind frozen baseline receipts to the exact prefix of final native work."""
    prereg, target, selection = map(Path, (prereg, target, selection))
    c.require(c.sha(prereg / 'manifest.json') == PREREG_MANIFEST_SHA256, 'Pushed preregistration manifest differs')
    authenticate_files(prereg, 'manifest.json')
    for name in ('protocol.json', 'public.json', 'predictions.json'):
        c.unseal(selection / name)
        c.require(c.sha(prereg / name) == c.sha(selection / name), 'Prelabel artifact changed: ' + name)
    for before, after in (('target-plan.json', 'plan.json'),
                          ('target-discovery.json', 'discovery/discovery.json'),
                          ('target-baseline.json', 'measurements/baseline/measurement.json')):
        c.require(c.sha(prereg / before) == c.sha(target / after), 'Prelabel target evidence changed: ' + after)
    initial = c.read(prereg / 'baseline-command-receipts.json')
    final = c.unseal(target / 'commands.json')
    c.require(initial and final[:len(initial)] == initial, 'Prelabel command prefix differs')
    c.require(all(not r['log'].startswith('measurements/') or
                  r['log'].startswith('measurements/baseline/') for r in initial),
              'Candidate attempt preceded preregistration')
    c.require(len(final) > len(initial), 'No post-freeze candidate commands')
    c.require(all(r['log'].startswith('measurements/candidate_') for r in final[len(initial):]),
              'Unexpected post-freeze command scope')
    protocol = c.unseal(selection / 'protocol.json')
    c.require(protocol['target_labels_read'] == 0, 'Target labels were used before freeze')
    benchmark = c.unseal(selection / 'public.json')[0]['benchmark']
    expected = protocol['contexts'][benchmark]['baseline_provenance']['artifacts']['commands.json']
    c.require(c.sha(prereg / 'baseline-command-receipts.json') == expected, 'Baseline receipt binding differs')
    for receipt in initial:
        c.require(c.sha(target / receipt['log']) == receipt['log_sha256'], 'Baseline raw receipt changed')
    return dict(prelabel_commit=PRELABEL_COMMIT, target_labels_at_freeze=protocol['target_labels_read'],
                baseline_receipt_count=len(initial), final_receipt_count=len(final),
                baseline_receipts_sha256=expected, predictions_sha256=c.sha(selection / 'predictions.json'))


def measurement_costs(target, failed):
    c.require(not list((Path(failed) / 'measurements').rglob('measurement.json')),
              'Initial preparation failure unexpectedly contains measurement files')
    failed_projection = ledger.project(failed, incomplete=True)
    c.require(failed_projection['failures'], 'Missing preserved initial failure')
    c.require(not failed_projection['measurements'], 'Failed preparation contains verified labels')
    commands = c.unseal(Path(target) / 'commands.json')
    buckets = {name: [] for name in ('setup_and_guard_controls', 'baseline', 'candidates')}
    for row in commands:
        phase = ('baseline' if row['log'].startswith('measurements/baseline/') else
                 'candidates' if row['log'].startswith('measurements/') else 'setup_and_guard_controls')
        buckets[phase].append(row)
    failed_commands = c.unseal(Path(failed) / 'commands.json')
    buckets['failed_initial_partition_attempt'] = failed_commands
    records = [c.unseal(p) for p in sorted((Path(target) / 'measurements').glob('*/measurement.json'))]
    return dict(native_commands={k: dict(count=len(v), seconds=sum(r['elapsed_seconds'] for r in v))
                                 for k, v in buckets.items()},
                actual_native_command_count=len(commands) + len(failed_commands),
                actual_native_command_seconds=sum(r['elapsed_seconds'] for r in commands + failed_commands),
                baseline_evaluation_wall_seconds=next(r['elapsed_seconds'] for r in records if r['name'] == 'baseline'),
                candidate_evaluation_wall_seconds=sum(r['elapsed_seconds'] for r in records if r['name'] != 'baseline'),
                note='Command durations form disjoint buckets here. Evaluation wall durations overlap those buckets; never add the two timer scopes. Historical training and calibration costs remain separate in the selection report.')


def restore_history(output):
    output = Path(output)
    roots = []
    for snapshot in HISTORY:
        target = output / snapshot.name
        restore_archive(snapshot, c.unseal(snapshot / 'archive-manifest.json'), target)
        roots.append(target)
    return roots


def pack(target, failed, selection, output):
    from scripts.verify_prospective_predictions import verify
    target, failed, selection, output = map(Path, (target, failed, selection, output))
    c.require(not output.exists(), 'Never overwrite a frozen snapshot')
    prereg = check_preregistration(PREREG, target, selection)
    checked = partition.audit(target)
    report = prospective_inputs.evaluate_workload(selection, target, verify=True)
    prediction_check = verify(selection, history_roots=prospective_inputs.DEFAULT_HISTORY)
    costs = measurement_costs(target, failed)
    output.mkdir(parents=True)
    archives = {'experiment': pack_archive(target, output / 'raw.tar.gz'),
                'failed_initial_partition': pack_archive(failed, output / 'failed-partition.tar.gz')}
    c.seal(output / 'archive-manifest.json', archives)
    for name in SELECTION_FILES:
        for suffix in ('', '.sha256'):
            shutil.copyfile(selection / (name + suffix), output / (name + suffix))
    for name, value in (('audit.json', checked), ('preregistration-check.json', prereg),
                        ('prediction-replay.json', prediction_check), ('measurement-costs.json', costs)):
        c.seal(output / name, value)
    source_names = set(c.unseal(target / 'plan.json')['source_bindings'])
    source_names.update(c.unseal(selection / 'protocol.json')['source_bindings'])
    source_names.update(('scripts/reproduce_prospective.py', 'scripts/reproduce_codesign.py',
                         'scripts/verify_prospective_predictions.py', 'scripts/build_research_demo.py',
                         'isaforge/experiment_ledger.py', 'isaforge/prospective_inputs.py'))
    sources = {name: c.sha(source_path(name)) for name in sorted(source_names)}
    for name in sources:
        copy = output / 'sources' / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path(name), copy)
    c.seal(output / 'source-manifest.json', sources)
    c.write(output / 'environment.json', dict(python=platform.python_version(), platform=platform.platform(),
            packages={name: importlib.metadata.version(name) for name in
                      ('numpy', 'scipy', 'scikit-learn', 'xgboost', 'joblib', 'pytest', 'matplotlib', 'z3-solver')}))
    c.seal(output / 'manifest.json', {p.relative_to(output).as_posix(): c.sha(p)
           for p in sorted(output.rglob('*')) if p.is_file()})
    return dict(snapshot=str(output), oracle_speedup=report['oracle_speedup'],
                archive_bytes={k: v['bytes'] for k, v in archives.items()})


def replay(snapshot, output):
    from scripts.verify_prospective_predictions import verify
    snapshot, output = Path(snapshot), Path(output)
    authenticate_files(snapshot, 'manifest.json')
    sources = c.unseal(snapshot / 'source-manifest.json')
    for name, expected in sources.items():
        c.require(c.sha(source_path(name)) == expected, 'Bound replay source changed: ' + name)
    for name, record in c.unseal(snapshot / 'archive-manifest.json').items():
        restore_archive(snapshot, record, output / name)
    target, failed = output / 'experiment', output / 'failed_initial_partition'
    checked = partition.audit(target)
    c.require(checked == c.unseal(snapshot / 'audit.json'), 'Raw processor replay differs')
    prereg = check_preregistration(PREREG, target, snapshot)
    c.require(prereg == c.unseal(snapshot / 'preregistration-check.json'), 'Prelabel chronology replay differs')
    costs = measurement_costs(target, failed)
    c.require(costs == c.unseal(snapshot / 'measurement-costs.json'), 'Cost replay differs')
    history = restore_history(output / 'history')
    prediction_check = verify(snapshot, history_roots=history)
    c.require(prediction_check == c.unseal(snapshot / 'prediction-replay.json'), 'Prediction refit replay differs')
    report = prospective_inputs.evaluate_workload(snapshot, target, verify=True)
    c.write(output / 'audit.json', checked)
    return dict(new_native_jobs=0, measurements=len(checked['observations']),
                policy_seed_runs=len(report['runs']), policy_budget_outcomes=len(report['runs']) * len(report['budgets'])
                if 'budgets' in report else sum(len(r['curve']) for r in report['runs']),
                prediction_replay=prediction_check)


def demo(snapshot, output):
    from scripts.build_research_demo import build
    snapshot, output = Path(snapshot), Path(output)
    replay(snapshot, output)
    database = output / 'experiments.sqlite'
    # Idempotent exact-manifest imports. No measurements or labels are synthesized.
    for root in restore_history(output / 'history') + [output / 'experiment']:
        ledger.import_evidence(database, root)
    ledger.import_evidence(database, output / 'failed_initial_partition', incomplete=True)
    c.write(output / 'ledger.json', ledger.export(database))
    return build(database, snapshot, output / 'index.html')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack', 'replay', 'demo'))
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--output', type=Path, default=ROOT / 'generated/reproduction/prospective-slre')
    parser.add_argument('--target-root', type=Path)
    parser.add_argument('--failed-root', type=Path)
    parser.add_argument('--selection-root', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'pack':
        c.require(all((args.target_root, args.failed_root, args.selection_root)), 'Pack needs three evidence roots')
        result = pack(args.target_root, args.failed_root, args.selection_root, args.snapshot)
    elif args.command == 'replay':
        result = replay(args.snapshot, args.output)
    else:
        result = demo(args.snapshot, args.output)
    print(result)


if __name__ == '__main__':
    main()
