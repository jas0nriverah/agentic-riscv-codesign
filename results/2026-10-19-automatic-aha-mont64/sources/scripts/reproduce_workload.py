"""Archive or replay the automatically extracted processor experiment."""
from pathlib import Path
import argparse
import importlib.metadata
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge.workload_audit import audit
from isaforge.workload_selection import compare, stable_report
from reproduce_codesign import pack_archive, restore_archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack', 'replay'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'results/2026-10-19-automatic-aha-mont64')
    parser.add_argument('--output', type=Path, default=ROOT / 'generated/reproduction/automatic-aha-mont64')
    args = parser.parse_args(argv)
    if args.command == 'pack':
        c.require(args.root is not None and not args.snapshot.exists(), 'New snapshot and existing root required')
        checked = audit(args.root)
        selected = c.unseal(args.root / 'selection-report.json')
        c.require(stable_report(compare(args.root)) == stable_report(selected), 'Selection replay differs')
        args.snapshot.mkdir(parents=True)
        archive = pack_archive(args.root, args.snapshot / 'raw.tar.gz')
        c.seal(args.snapshot / 'archive-manifest.json', archive)
        c.seal(args.snapshot / 'audit.json', checked)
        for name in ('plan.json', 'report.json', 'selection-report.json', 'combined-corpus.json'):
            c.seal(args.snapshot / name, c.unseal(args.root / name))
        plan = c.unseal(args.root / 'plan.json')
        sources = {**plan['source_bindings'], **{name: c.sha(ROOT / name) for name in
                   ('isaforge/workload_audit.py', 'isaforge/workload_selection.py',
                    'scripts/reproduce_workload.py', 'scripts/reproduce_codesign.py')}}
        for name, expected in sources.items():
            target = args.snapshot / 'sources' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            c.require(c.sha(target) == expected, 'Source snapshot mismatch')
        c.seal(args.snapshot / 'source-manifest.json', sources)
        c.write(args.snapshot / 'environment.json', {'python': platform.python_version(), 'platform': platform.platform(),
                'packages': {name: importlib.metadata.version(name) for name in
                             ('numpy', 'scipy', 'scikit-learn', 'xgboost', 'joblib', 'pytest')}})
        print({'archived_bytes': archive['bytes'], 'measurements': len(checked['observations'])})
    else:
        restore_archive(args.snapshot, c.unseal(args.snapshot / 'archive-manifest.json'), args.output)
        checked = audit(args.output)
        c.require(checked == c.unseal(args.snapshot / 'audit.json'), 'Replay differs from frozen audit')
        c.require(stable_report(compare(args.output)) == stable_report(c.unseal(args.output / 'selection-report.json')),
                  'Selection replay differs')
        print('Verified automatic extraction/lowering, seven processor measurements, all routing seeds, raw evidence and 120 policy/seed/budget outcomes. No native jobs.')


if __name__ == '__main__': main()
