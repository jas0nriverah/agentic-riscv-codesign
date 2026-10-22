"""Renew only the failed Levenshtein qualification with explicit strlen support.

The original rejection is immutable. Reuse the original qualifier's blocking
five-phase procedure with a scoped module/command/protocol amendment; never
change the original source, twelve-candidate gate, partition or prior evidence.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, string_workload as workload
from scripts import qualify_levenshtein as original

SOURCE = 'scripts/qualify_string_workload.py'
PRIOR = 'results/2026-10-22-levenshtein-qualification'
NATIVE = 'generated/live-gp-levenshtein-strlen-2026-10-22'
OUTPUT = 'results/2026-10-22-levenshtein-strlen-qualification'


def prior_rejection():
    folder = ROOT / PRIOR
    manifest = c.unseal(folder / 'manifest.json')
    for name, digest in manifest.items():
        path = (folder / name).resolve()
        c.require(path.is_relative_to(folder.resolve()) and c.sha(path) == digest,
                  'Preserved original qualification evidence differs')
    result = c.unseal(folder / 'qualification.json')
    c.require(result['status'] == 'rejected' and result['failed_phase'] == 'discover' and
              result['accepted'] is False and result['target_candidate_attempts'] == 0,
              'Original zero-candidate discovery rejection required')
    archive = c.unseal(folder / 'archive-manifest.json')
    c.require(c.sha(folder / archive['archive']) == archive['sha256'], 'Original failure archive differs')
    log_name = 'discovery/attempt-000/original/compile.log'
    entries = [entry for entry in archive['files'] if entry['path'] == log_name]
    c.require(len(entries) == 1, 'Original linker failure log required')
    with tarfile.open(folder / archive['archive'], 'r:gz') as stream:
        member = stream.getmember(log_name)
        c.require(member.isfile() and member.size <= 1024 * 1024, 'Bounded original linker log required')
        diagnostic = stream.extractfile(member).read()
    c.require(hashlib.sha256(diagnostic).hexdigest() == entries[0]['sha256'] and
              b'undefined reference' in diagnostic and b'strlen' in diagnostic,
              'Original undefined-strlen diagnosis required')
    return dict(path=PRIOR, manifest_sha256=c.sha(folder / 'manifest.json'),
                qualification_sha256=c.sha(folder / 'qualification.json'),
                original_linker_log_sha256=entries[0]['sha256'],
                reason='Original linker reported undefined strlen; append only standard freestanding strlen to the external firmware harness. No source/input/pool/partition change.',
                abi_extension=workload.abi_extension())


def phase_command(phase, native, reference):
    c.require(phase in original.PHASES, 'Only the five declared qualification phases are allowed')
    argv = [sys.executable, '-m', 'isaforge.string_workload', phase, '--root', str(native)]
    if phase == 'prepare':
        argv += ['--workload', 'levenshtein', '--reference-root', str(reference)]
    return argv


class _ProtocolAmendment:
    """Delegate ordinary record I/O; add renewal provenance before first seal."""
    def __init__(self, output, renewal):
        self.output, self.renewal = Path(output).resolve(), renewal

    def __getattr__(self, name):
        return getattr(c, name)

    def seal(self, path, value):
        if Path(path).resolve() == self.output / 'protocol.json':
            value = dict(value, schema='isaforge-levenshtein-strlen-qualification-v1',
                         qualification_amendment=self.renewal)
        return c.seal(path, value)


@contextmanager
def registration(output, renewal):
    previous = (original.ROOT, original.SOURCE, original.SOURCES, original.workload,
                original.phase_command, original.c)
    original.ROOT, original.SOURCE = ROOT, SOURCE
    original.SOURCES = tuple(dict.fromkeys((SOURCE, workload.SOURCE, workload.ORIGINAL_BLIND_SOURCE,
                                           'scripts/qualify_levenshtein.py', *original.SOURCES)))
    original.workload, original.phase_command = workload, phase_command
    original.c = _ProtocolAmendment(output, renewal)
    try:
        yield
    finally:
        (original.ROOT, original.SOURCE, original.SOURCES, original.workload,
         original.phase_command, original.c) = previous


def qualify(output, native, reference):
    renewal = prior_rejection()
    with registration(output, renewal):
        return original.qualify(output, native, reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT / NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT / original.REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_root, args.reference_root)
    print(result)
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
