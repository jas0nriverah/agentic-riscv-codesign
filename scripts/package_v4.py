#!/usr/bin/env python3
"""Package V4 raw evidence, frozen inference dependencies and selected SOG cache.

Only the separate evidence ZIP and its manifest sidecar are written in outputs.
Raw scripts/logs keep their original provenance paths; archive member paths are
portable repository-relative paths. Compiled verification builds are excluded.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT.parents[1] / 'outputs'
V4 = ROOT / 'results/2026-10-13-v4'
COMMIT = '2383818'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cache_keys(value):
    if isinstance(value, dict):
        for name, item in value.items():
            if name.endswith('cache_key') and isinstance(item, str):
                if not re.fullmatch('[0-9a-f]{64}', item):
                    raise ValueError('invalid referenced SOG cache key')
                yield item
            yield from cache_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from cache_keys(item)


def files_to_package():
    paths = set()
    def add(path):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or path.is_symlink():
            raise ValueError(f'expected regular repository file: {path}')
        paths.add(path)
    def tree(directory, suffixes=None):
        for path in sorted(Path(directory).rglob('*')):
            if path.is_file() and not any(p.startswith('obj_dir') or p == '__pycache__' for p in path.parts):
                if suffixes is None or path.suffix in suffixes:
                    add(path)
    for name in ('README.md', 'pyproject.toml', 'Makefile', 'CITATION.cff', '.github/workflows/tests.yml'):
        add(ROOT / name)
    tree(ROOT / 'isaforge', {'.py', '.md'})
    tree(ROOT / 'docs', {'.md', '.png', '.svg', '.json', '.pdf'})
    tree(ROOT / 'tests', {'.py'})
    for path in sorted((ROOT / 'scripts').glob('*v4*.py')):
        add(path)
    tree(V4)
    for name in ('results/2026-10-13/dataset.json',
                 'results/2026-10-13-prospective/transfer/dataset.json',
                 'results/2026-10-13-prospective/final/dataset.json',
                 'results/2026-10-13-v3/probe/dataset.json',
                 'results/2026-10-13-v3/models/preregistration.json',
                 'results/2026-10-13-v3/masterrtl/preregistration.json'):
        add(ROOT / name)
    frozen = json.loads((V4 / 'freeze.json').read_text())
    for model in frozen['models'].values():
        for record in [model['artifact'], model['predictions'], *model['sources']]:
            path = (V4 / record['path']).resolve()
            if sha(path.read_bytes()) != record['sha256']:
                raise ValueError(f'frozen evidence hash mismatch: {path}')
            add(path)
    # Only relevant raw evidence: all V4 circuits, all harness/vector/log sources,
    # and the retained initial simulator incident, excluding compiler outputs.
    tree(ROOT / 'generated/v4-corpus', {'.v', '.cpp', '.ys', '.json', '.txt', '.log'})
    manifest_names = ('development-features.json', 'test-features.json', 'raw-feature-extraction.json')
    keys = set()
    for name in manifest_names:
        keys.update(cache_keys(json.loads((V4 / name).read_text())))
    cache = ROOT / 'generated/masterrtl-baseline/sog-cache'
    for key in sorted(keys):
        directory = cache / key
        if not directory.is_dir() or not (directory / 'features.json').is_file() or not (directory / 'sog.json').is_file():
            raise ValueError(f'referenced SOG cache evidence missing: {key}')
        tree(directory, {'.v', '.ys', '.json', '.txt', '.log'})
    for cohort, expected in (('development', 384), ('test', 256)):
        circuits = ROOT / f'generated/v4-corpus/{cohort}/circuits'
        if len(list(circuits.glob('*/metrics.json'))) != expected:
            raise ValueError(f'{cohort}: expected all {expected} measured raw circuits')
        completion = json.loads((V4 / f'corpus/{cohort}/completion.json').read_text())
        if not completion['complete'] or completion['failures'] or completion['measured_count'] != expected:
            raise ValueError(f'{cohort}: incomplete measurement')
    return sorted(paths), sorted(keys)


def package(output):
    output = Path(output).resolve()
    if output.parent != OUTPUTS.resolve() or output.name != 'ISAForge-v4-evidence.zip':
        raise ValueError('output must be the separate outputs/ISAForge-v4-evidence.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    selected, keys = files_to_package()
    full_commit = subprocess.run(['git', 'rev-parse', COMMIT], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    commit_text = subprocess.run(['git', 'show', '--no-patch', '--format=fuller', full_commit], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    commit_tree = subprocess.run(['git', 'rev-parse', full_commit + '^{tree}'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    marker = f'Frozen model/prediction commit: {full_commit}\nTree: {commit_tree}\n\n{commit_text}'.encode()
    readme = '''ISAForge V4 reproducibility evidence

Extract this archive at a repository root. Paths retain the original repository
structure. All 384 development and 256 held-out circuits, actual iCE40 netlists,
complete synthesis logs/scripts, formula RTL, verification harnesses/vectors,
and the original development simulator incident are retained. Compiler object
directories and executables are omitted.

The restored SOG cache is generated/masterrtl-baseline/sog-cache, relative to
the extracted root. Only keys referenced by development-features.json,
test-features.json and raw-feature-extraction.json are included. The last file
records all 1,545 raw formulas; normalized V4 feature records add their keys.

Install dependencies from pyproject.toml in a Python virtual environment.
This archive contains trusted local pickle/joblib artifacts from this run.
Load models with an explicit cache path pointing at the restored SOG cache.
Complete cached-feature inference validates provenance without invoking Yosys.
Previously unseen formulas require the recorded Yosys build/tool identity for
new label-free pre-ABC graph extraction, independently of target iCE40 synthesis.
Recorded tool paths and raw .ys files may contain original absolute paths.
To rerun synthesis, use the source collector, which generates local scripts.

Replay score/provenance validation (no fitting or new synthesis):
  python scripts/evaluate_v4.py --manifest results/2026-10-13-v4/freeze.json \\
    --release results/2026-10-13-v4/label-release.json \\
    --output work/v4-replayed-evaluation.json
Replay frozen V4 inference using restored feature evidence:
  python -m isaforge.area_model_v4 --model results/2026-10-13-v4/models/v4.joblib \\
    --candidates results/2026-10-13-v4/corpus/test/candidates.json \\
    --cache-dir generated/masterrtl-baseline/sog-cache \\
    --output work/v4-replayed-predictions.json
See scripts/evaluate_v4.py --help for supported options and docs/v4-protocol.md.
The saved independent-validation.json records a second score/netlist recount.
For independent git-commit proof replay, extract over the original Git checkout
with commit 2383818 in its history and run scripts/audit_v4.py --help. Git history
is not included in this archive; FROZEN-MODEL-COMMIT.txt records its commit/tree.

SHA256-MANIFEST.json enumerates every evidence file's path, size and SHA-256.
The manifest itself is excluded from its own checksum listing. The archive
sidecar records the archive SHA-256 and manifest checksum. This package is a
snapshot: rerunning package_v4.py refreshes it after final report/document edits.

Synthetic held-out formulas measure isolated iCE40 LUT4 resources. They do not
establish independent-workload performance, CPU speedup, ASIC area or timing.
'''.encode()
    partial = output.with_suffix('.zip.partial')
    manifest = {'schema': 'isaforge-v4-evidence-v1', 'packaged_at_utc': datetime.now(timezone.utc).isoformat(),
                'frozen_model_commit': full_commit, 'frozen_model_tree': commit_tree,
                'raw_candidate_circuit_count': 640, 'referenced_sog_cache_key_count': len(keys),
                'referenced_sog_cache_keys': keys, 'files': []}
    source_hashes = {}
    try:
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for path in selected:
                data = path.read_bytes(); relative = path.relative_to(ROOT).as_posix()
                digest = sha(data); source_hashes[path] = digest
                archive.writestr(relative, data)
                manifest['files'].append({'path': relative, 'bytes': len(data), 'sha256': digest})
            for name, data in [('EVIDENCE-README.txt', readme), ('FROZEN-MODEL-COMMIT.txt', marker)]:
                archive.writestr(name, data)
                manifest['files'].append({'path': name, 'bytes': len(data), 'sha256': sha(data)})
            manifest['file_count'] = len(manifest['files'])
            manifest['uncompressed_bytes'] = sum(item['bytes'] for item in manifest['files'])
            manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
            archive.writestr('SHA256-MANIFEST.json', manifest_bytes)
        if any(sha(path.read_bytes()) != digest for path, digest in source_hashes.items()):
            raise ValueError('source evidence changed during packaging; retry after edits finish')
        with zipfile.ZipFile(partial) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f'archive CRC integrity failed: {bad}')
            if len(archive.namelist()) != manifest['file_count'] + 1 or len(set(archive.namelist())) != len(archive.namelist()):
                raise ValueError('archive member duplication or omission')
        os.replace(partial, output)
        summary = {'archive': str(output), 'archive_bytes': output.stat().st_size,
                   'archive_sha256': sha(output.read_bytes()), 'manifest_sha256': sha(manifest_bytes),
                   **{k: v for k, v in manifest.items() if k not in ('files', 'referenced_sog_cache_keys')}}
        sidecar = output.with_suffix('.manifest.json')
        sidecar.write_text(json.dumps({'archive_summary': summary, 'evidence_manifest': manifest}, indent=2) + '\n')
        print(json.dumps(summary, indent=2))
        return summary
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUTS / 'ISAForge-v4-evidence.zip')
    args = parser.parse_args()
    package(args.output)


if __name__ == '__main__':
    main()
