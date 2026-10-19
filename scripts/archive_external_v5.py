#!/usr/bin/env python3
"""Package or restore hash-checked external synthesis evidence for score replay."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'generated/external-v5/target-measurements/'
DEFAULT = ROOT / 'results/2026-10-14-v5-external'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def destination(name, root):
    path = PurePosixPath(name)
    if not name.startswith(PREFIX) or path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError(f'Unexpected archive path: {name}')
    allowed = (root / PREFIX).resolve()
    target = root.joinpath(*path.parts)
    if not allowed.is_relative_to(root.resolve()) or not target.resolve().is_relative_to(allowed):
        raise ValueError(f'Archive path leaves evidence directory: {name}')
    return target


def pack(bundle, root=ROOT):
    completion = json.loads((bundle/'measurements/completion.json').read_text())
    if not completion['complete'] or completion['failures']:
        raise ValueError('Only complete measurement evidence can be packaged')
    scratch = (bundle/completion['scratch_directory']).resolve()
    files = sorted(p for p in scratch.rglob('*') if p.is_file() and not {'obj_dir', 'obj_dir_wrapv'}.intersection(p.parts))
    archive = bundle/'raw-evidence.zip'
    if archive.exists() or (bundle/'raw-evidence.json').exists():
        raise ValueError('Existing evidence archive is immutable')
    records = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in files:
            name = path.relative_to(root).as_posix()
            destination(name, root)
            data = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compresslevel=9)
            records.append({'path': name, 'size': len(data), 'sha256': digest(data)})
    manifest = {'schema': 'isaforge-external-evidence-v1', 'archive': archive.name,
                'archive_sha256': digest(archive.read_bytes()), 'files': records,
                'scope': 'Original circuit sources, mapping logs/netlists, verification source/results; generated compiler objects omitted.'}
    (bundle/'raw-evidence.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def restore(bundle, root=ROOT):
    manifest = json.loads((bundle/'raw-evidence.json').read_text())
    archive = bundle/'raw-evidence.zip'
    if manifest['schema'] != 'isaforge-external-evidence-v1' or manifest['archive'] != archive.name:
        raise ValueError('Unknown evidence archive schema')
    if digest(archive.read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Evidence archive SHA differs')
    records = {r['path']: r for r in manifest['files']}
    if len(records) != len(manifest['files']):
        raise ValueError('Duplicate manifest path')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(records):
            raise ValueError('Evidence archive inventory differs')
        # Validate every member and every existing file before writing anything.
        for name in names:
            target = destination(name, root)
            data = z.read(name)
            if len(data) != records[name]['size'] or digest(data) != records[name]['sha256']:
                raise ValueError(f'Changed archive evidence: {name}')
            if target.exists() and digest(target.read_bytes()) != records[name]['sha256']:
                raise ValueError(f'Existing evidence differs; refusing overwrite: {name}')
        for name in names:
            target = destination(name, root)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as out:
                    out.write(z.read(name))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pack', 'restore'))
    parser.add_argument('--bundle', type=Path, default=DEFAULT)
    args = parser.parse_args()
    result = (pack if args.action == 'pack' else restore)(args.bundle.resolve())
    print(json.dumps({'files': len(result['files']), 'archive_sha256': result['archive_sha256']}))


if __name__ == '__main__':
    main()
