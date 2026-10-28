"""Replay the frozen discovery diagnosis using only committed archive evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c

EVIDENCE = ROOT / 'results/2026-10-27-countnegative-discovery-diagnosis'
QUALIFICATION = ROOT / 'results/2026-10-27-countnegative-qualification'
DEFAULT_OUTPUT = ROOT / 'generated/reproduction/countnegative-diagnosis'


def inventory(folder):
    return {p.relative_to(folder).as_posix(): c.sha(p)
            for p in sorted(folder.rglob('*')) if p.is_file()
            and p.name not in ('manifest.json', 'manifest.json.sha256')}


def restore(raw, manifest, destination):
    """Validate the complete archive before writing regular files to fresh storage."""
    c.require(c.sha(raw) == manifest['sha256'] and
              raw.stat().st_size == manifest['bytes'], 'Archive hash/size differs')
    entries = {row['path']: row for row in manifest['files']}
    c.require(len(entries) == len(manifest['files']), 'Duplicate manifest path')
    payloads = []
    with tarfile.open(raw, 'r:gz') as stream:
        members = stream.getmembers()
        names = [member.name for member in members]
        c.require(len(names) == len(set(names)) and set(names) == set(entries),
                  'Archive member inventory differs')
        for member in members:
            name = PurePosixPath(member.name)
            c.require(member.isfile() and bool(name.parts) and not name.is_absolute() and
                      '..' not in name.parts and name.as_posix() == member.name,
                      'Unsafe archive member: ' + member.name)
            data = stream.extractfile(member).read()
            expected = entries[member.name]
            c.require(len(data) == expected['bytes'] and
                      hashlib.sha256(data).hexdigest() == expected['sha256'],
                      'Archive member hash/size differs: ' + member.name)
            payloads.append((name, data))
    c.require(not destination.exists(), 'Restore destination must be fresh')
    destination.mkdir(parents=True)
    for name, data in payloads:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def reproduce(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    c.require(output.is_relative_to(ROOT / 'generated') and not output.exists(),
              'Use a fresh output directory under generated/')
    for folder in (EVIDENCE, QUALIFICATION):
        c.require(c.unseal(folder / 'manifest.json') == inventory(folder),
                  'Evidence inventory differs: ' + str(folder))
    expected = c.unseal(EVIDENCE / 'report.json')
    for name, digest in expected['source_bindings'].items():
        c.require(c.sha(ROOT / name) == digest, 'Frozen diagnostic source differs: ' + name)
    spec = importlib.util.spec_from_file_location(
        '_frozen_countnegative_diagnosis', ROOT / 'scripts/diagnose_tacle_countnegative_discovery.py')
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)
    archive = c.unseal(QUALIFICATION / 'archive-manifest.json')
    c.require(c.sha(diagnostic.HISTORY) == expected['historical_corpus_sha256'],
              'Historical corpus differs')
    with tempfile.TemporaryDirectory(prefix='isaforge-countnegative-replay-') as temporary:
        native = Path(temporary) / 'native'
        restore(QUALIFICATION / archive['archive'], archive, native)
        diagnostic.NATIVE = native
        result = diagnostic.diagnose(output)
    c.require(result == expected, 'Reconstructed diagnostic report differs')
    c.require(inventory(output) == inventory(EVIDENCE),
              'Reconstructed diagnostic files differ')
    return dict(status='exact_replay', candidate_labels=0, native_jobs=0,
                output=str(output), report_sha256=c.sha(output / 'report.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(reproduce(args.output))


if __name__ == '__main__':
    main()
