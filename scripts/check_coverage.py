#!/usr/bin/env python3
"""Replay frozen audits with their historical prose and current scientific files.

The audits hash the old results index as well as scientific evidence. Restore
only that documented presentation file in a disposable copy, never in the
checkout. No scientific file or audit expectation is replaced or exempted.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_README_SHA = 'af608836afba669c237f82fb232ab9162ce3cb14e29ae5d139bbe576ea757c91'


def historical_readme(root):
    content = (root / 'tests/fixtures/coverage-results-readme.md').read_bytes()
    if hashlib.sha256(content).hexdigest() != HISTORICAL_README_SHA:
        raise ValueError('Historical results README fixture changed')
    for experiment in ('targeted-coverage', 'budget-preserving-coverage'):
        inventory = json.loads((root / 'results' / experiment / 'auditor-prior-artifacts.json').read_text())
        if inventory['files']['results/README.md'] != HISTORICAL_README_SHA:
            raise ValueError('Historical README does not match the frozen audit inventory')
    return content


def prepare_snapshot(root, destination):
    prose = historical_readme(root)
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    for name in filter(None, names):
        source = root / name
        # Git submodules are directory entries; neither audit needs their checkout.
        if source.is_dir():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (destination / 'results/README.md').write_bytes(prose)


def main():
    with tempfile.TemporaryDirectory(prefix='isaforge-coverage-') as temporary:
        snapshot = Path(temporary)
        prepare_snapshot(ROOT, snapshot)
        print('Replaying unchanged audits with the hash-verified historical results index; all scientific files come from this checkout.', flush=True)
        subprocess.run([sys.executable, str(snapshot / 'scripts/replay_coverage_audits.py')], cwd=snapshot, check=True)


if __name__ == '__main__':
    main()
