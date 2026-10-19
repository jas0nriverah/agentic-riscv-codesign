#!/usr/bin/env python3
"""Materialize reviewed pre-label evidence into a portable, commit-ready seal.

Working directories remain immutable. Their exact JSON evidence is archived;
all release-critical flat references resolve inside the repository.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from train_v6 import read, sha, write, now, record, checked
from isaforge import area_model_v8 as v8


def dropped_input_coverage(verified, portable, indexes, exceptions):
    """Fail closed when materialization drops an input with no retained bytes."""
    available = {}
    for index in indexes:
        for member in read(index)['files']:
            available.setdefault((member['sha256'], member['bytes']), []).append(
                {'archive_index': str(index), 'member': member['path']})
    kept = set(map(lambda p: Path(p).resolve(), portable))
    rows = []
    for p in dict.fromkeys(map(lambda p: Path(p).resolve(), verified)):
        if p in kept:
            continue
        digest, size = sha(p), p.stat().st_size
        matches = available.get((digest, size), [])
        exception = exceptions.get(str(p))
        if matches:
            status = 'exact-bytes-in-published-archive'
        elif exception and exception['sha256'] == digest:
            status = 'explicit-nondistributed-dependency-or-failed-partial'
        else:
            raise ValueError('Uncovered dropped input: ' + str(p))
        rows.append({'original_path': str(p), 'sha256': digest, 'bytes': size,
                     'status': status, 'archive_matches': matches, 'exception': exception if not matches else None})
    return rows


def archive_index(manifest_path, archive_path, output):
    """Normalize published archive contracts without changing original evidence."""
    manifest = read(manifest_path)
    expected = manifest.get('archive', {}).get('sha256', manifest.get('archive_sha256'))
    if expected != sha(archive_path):
        raise ValueError('Published archive hash differs from original member manifest')
    members = manifest.get('files', manifest.get('members'))
    if isinstance(members, dict):
        members = [{'path': name, **entry} for name, entry in members.items()]
    if not isinstance(members, list) or not members:
        raise ValueError('Complete archive member manifest required')
    write(output, {'schema': 'isaforge-v8-release-archive-index-v1',
          'archive': record(archive_path, output.parent),
          'source_manifest': record(manifest_path, output.parent),
          'files': [{'path': e['path'], 'sha256': e['sha256'], 'bytes': e.get('bytes', e.get('size'))} for e in members]})
    from measure_v8_applications import verify_archive_manifest
    verify_archive_manifest(output)


def run(root, application, training, consumed, runtime_archive, runtime_manifest, runtime_audit, independent_review):
    paths = list(map(lambda p: Path(p).resolve(), (root, application, training, consumed, runtime_archive,
                                                 runtime_manifest, runtime_audit, independent_review)))
    root, application, training, consumed, runtime_archive, runtime_manifest, runtime_audit, independent_review = paths
    if not root.is_relative_to(ROOT) or root.exists():
        raise ValueError('New repository-owned result directory required')
    inputs = read(application / 'input-preparation.json')
    preparation = read(training / 'preparation.json')
    registry_start = read(consumed / 'start.json')
    if any(r['runtime_source_sha256'] != v8.source_hashes() for r in (inputs, preparation, registry_start)):
        raise ValueError('Preparation/runtime sources differ')
    verified = []
    for entry_set, base in [(inputs, application), (preparation, training), (registry_start, consumed)]:
        verified += [checked(entry, base) for entry in entry_set['files']]
    train_data = checked(preparation['training_data'], training)
    complete = read(consumed / 'completion.json')
    consumed_features = checked(complete['features'], consumed)
    checked(complete['start'], consumed)
    # Independent review must identify these exact evidence bytes, not a title.
    review = read(independent_review)
    if (review.get('status') != 'approved-for-input-seal'
            or review.get('input_preparation_sha256') != sha(application / 'input-preparation.json')
            or review.get('training_preparation_sha256') != sha(training / 'preparation.json')
            or review.get('consumed_completion_sha256') != sha(consumed / 'completion.json')
            or review.get('runtime_audit_sha256') != sha(runtime_audit)):
        raise ValueError('Exact independent input/preparation/runtime review required')
    for path in (runtime_archive, runtime_manifest, runtime_audit):
        if not path.is_relative_to(ROOT):
            raise ValueError('Published runtime archive, manifest and audit must be inside repository')
    guarded = [*verified, train_data, consumed_features, application / 'input-preparation.json',
               training / 'preparation.json', consumed / 'start.json', consumed / 'completion.json',
               independent_review, runtime_archive, runtime_manifest, runtime_audit]
    initial_digests = {str(p): sha(p) for p in guarded}
    root.mkdir(parents=True)
    for key, name in [('rows', 'rows.json'), ('programs', 'programs.json'), ('features', 'features.json'), ('novelty', 'novelty.json')]:
        source = checked(inputs[key], application)
        shutil.copyfile(source, root / name)
        if sha(root / name) != inputs[key]['sha256']:
            raise ValueError('First application input bytes changed during materialization')
    training_root = root / 'training'
    training_root.mkdir()
    shutil.copyfile(train_data, training_root / 'training-data.json')
    if sha(training_root / 'training-data.json') != preparation['training_data']['sha256']:
        raise ValueError('Training bytes changed during materialization')
    shutil.copyfile(independent_review, root / 'independent-input-review.json')
    # Exact preparation attempts and the complete consumed feature/proof registry.
    archive = root / 'prelabel-audit.zip'
    members = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for label, directory in [('application', application), ('training', training), ('consumed', consumed)]:
            for path in sorted(directory.rglob('*.json')):
                member = label + '/' + path.relative_to(directory).as_posix()
                out.write(path, member)
                members.append({'path': member, 'sha256': sha(path), 'bytes': path.stat().st_size})
    write(root / 'prelabel-audit-manifest.json', {'schema': 'isaforge-v8-prelabel-audit-archive-v1',
          'archive': record(archive, root), 'members': members,
          'scope': 'Exact working preparation JSON; paths inside original records describe original execution. '
                   'Release references below are repository relative; first native proof outcomes are retained.'})
    published_v7 = ROOT / 'results/2026-10-14-development-semantics-v7/evidence'
    # Historical unpacked V7 members are authenticated by its published archive;
    # generated runtime bytes are authenticated by the separately replayed archive.
    portable = [p for p in verified if p.is_relative_to(ROOT) and not p.is_relative_to(ROOT / 'generated')]
    portable += [published_v7 / 'evidence.tar.gz', published_v7 / 'evidence-manifest.json',
                 runtime_archive, runtime_manifest, runtime_audit,
                 root / 'prelabel-audit.zip', root / 'prelabel-audit-manifest.json',
                 root / 'independent-input-review.json', Path(__file__)]
    portable += [p for p in (ROOT / 'benchmarks/application-v8').rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts]
    portable += [ROOT / 'docs/v8-application-pilot-protocol.md']
    portable += [ROOT / 'scripts' / n for n in ('measure_v6.py', 'evaluate_v6.py')]
    portable += [ROOT / 'tests/test_semantic_features_v7_independent.py']
    portable += [p for folder in ('isaforge', 'scripts', 'tests') for p in (ROOT / folder).glob('*v8*.py')]
    portable = list(dict.fromkeys(portable))
    if any(not p.is_file() for p in portable):
        raise ValueError('Missing portable source/evidence')
    feature_root = ROOT / 'benchmarks/application-v8'
    archive_pairs = [('v7', published_v7 / 'evidence-manifest.json', published_v7 / 'evidence.tar.gz'),
                     ('runtime', runtime_manifest, runtime_archive),
                     ('prelabel', root / 'prelabel-audit-manifest.json', archive),
                     ('features', feature_root / 'feature-evidence-manifest.json', feature_root / 'feature-evidence.zip')]
    indexes = []
    for name, manifest_path, archive_path in archive_pairs:
        index_path = root / 'archive-indexes' / (name + '.json')
        archive_index(manifest_path, archive_path, index_path)
        indexes.append(index_path)
    portable += indexes
    preflight = read(ROOT / 'benchmarks/application-v8/cohort-preflight.json')
    exceptions = {str(Path(e['path']).resolve()): {'sha256': e['sha256'],
                  'scope': 'Pinned native tool dependency supplied separately; not benchmark data.'}
                  for e in preflight['tools'].values()}
    partial = preflight['programs']['mpeg2']['partial_trace']
    exceptions[str((ROOT / partial['path']).resolve())] = {'sha256': partial['sha256'],
        'scope': 'Failed incomplete MPEG2 trace retained locally; excluded program, never used for features or evaluation.'}
    coverage = dropped_input_coverage(verified, portable, indexes, exceptions)
    write(root / 'materialization-coverage.json', {'schema': 'isaforge-v8-materialization-coverage-v1',
          'records': coverage, 'uncovered_inputs': 0,
          'scope': 'Every dropped flat input has exact archived bytes or an explicit pinned-tool/failed-partial exception.'})
    portable.append(root / 'materialization-coverage.json')
    flat = [record(p, root) for p in portable]
    write(training_root / 'preparation.json', {**preparation,
          'files': [record(p, training_root) for p in portable],
          'training_data': record(training_root / 'training-data.json', training_root),
          'original_preparation_member': 'training/preparation.json',
          'original_preparation_sha256': sha(training / 'preparation.json'),
          'materialized_at_utc': now(), 'materialization_scope': 'Same bytes, rows and features; zero refits or re-extractions.'})
    data_paths = [root / name for name in ('rows.json', 'programs.json', 'features.json', 'novelty.json')]
    if any(sha(path) != digest for path, digest in initial_digests.items()):
        raise ValueError('Reviewed input changed during materialization')
    for entry in flat:
        checked(entry, root)
    write(root / 'input-seal.json', {**inputs, 'schema': 'isaforge-v8-application-input-seal-v1',
          'status': 'sealed-inputs-only', 'sealed_at_utc': now(),
          'files': [*flat, *(record(p, root) for p in data_paths)],
          **{key: record(root / name, root) for key, name in [('rows', 'rows.json'), ('features', 'features.json'),
               ('programs', 'programs.json'), ('novelty', 'novelty.json')]},
          'first_native_feature_extraction_retained': True, 'new_estimator_fits': 0,
          'archive_manifests': [record(p, root) for p in indexes],
          'external_work_paths_in_release_bindings': False})
    print('Sealed portable application inputs; no fits, predictions or labels.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'application', 'training', 'consumed', 'runtime-archive', 'runtime-manifest', 'runtime-audit', 'independent-review'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    run(a.root, a.application, a.training, a.consumed, a.runtime_archive, a.runtime_manifest, a.runtime_audit, a.independent_review)
