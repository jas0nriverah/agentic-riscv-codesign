#!/usr/bin/env python3
"""Pack only the exact input-bound generic/SOG receipts, never rerun tools.

Members use paths relative to a portable feature-cache root. The first V7
proof/fallback ledger stays in the separately sealed input-feature JSON.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_file(root, relative):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or not relative.parts or any(p in ('..', '.') for p in relative.parts):
        raise ValueError('Unsafe cache member')
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Cache member is missing or escapes its root')
    return path


def pack(features, cache, archive, manifest):
    features, cache, archive, manifest = map(Path, (features, cache, archive, manifest))
    if archive.exists() or manifest.exists():
        raise ValueError('Archive and manifest paths must be new; preserve attempts')
    source_sha = sha(features)
    data = json.loads(features.read_text())
    if len(data['columns']) != 455 or len(data['records']) != 146:
        raise ValueError('Exact146 full455 sealed-input preparation required')
    members, receipts = {}, []
    seen = set()
    for row in data['records']:
        if row['formula'] in seen:
            raise ValueError('Unique original formulas required')
        seen.add(row['formula'])
        for channel, key_field, digest_field in (
            ('generic', 'original_cache_key', 'original_manifest_sha256'),
            ('generic', 'normalized_cache_key', 'normalized_manifest_sha256'),
            ('sog', 'sog_cache_key', 'sog_manifest_sha256'),
        ):
            key = row[key_field]
            if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                raise ValueError('Invalid cache-key digest')
            prefix = f'{channel}/{key}'
            receipt = safe_file(cache, prefix + '/features.json')
            if sha(receipt) != row[digest_field]:
                raise ValueError('Input-bound cache receipt changed')
            payload = json.loads(receipt.read_text())
            if payload['cache_key'] != key:
                raise ValueError('Receipt cache key differs')
            expected = {'features.json': row[digest_field], **payload['files_sha256']}
            # Explicit paths rather than directory walking prevent unrelated
            # scratch files or accidental target labels entering the package.
            required = ({'candidate.v', 'features.json', 'word.json', 'graph.json', 'extract.ys', 'extract.log'}
                        if channel == 'generic' else
                        {'candidate.v', 'features.json', 'sog.json', 'sog.v', 'sog.ys', 'sog.log'})
            if set(expected) != required:
                raise ValueError('Unexpected or incomplete receipt file schema')
            for name, digest in expected.items():
                if PurePosixPath(name).name != name:
                    raise ValueError('Receipt files must be direct cache children')
                member = prefix + '/' + name
                path = safe_file(cache, member)
                if sha(path) != digest:
                    raise ValueError('Receipt-bound cache file changed: ' + member)
                entry = {'path': member, 'sha256': digest, 'bytes': path.stat().st_size}
                if member in members and members[member] != entry:
                    raise ValueError('Conflicting duplicate cache evidence')
                members[member] = entry
            receipts.append({'formula': row['formula'], 'role': key_field,
                             'path': prefix + '/features.json', 'sha256': row[digest_field]})
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for name in sorted(members):
            target.write(safe_file(cache, name), name)
    with zipfile.ZipFile(archive) as target:
        if sorted(target.namelist()) != sorted(members):
            raise ValueError('Archive member inventory differs')
        for name, entry in members.items():
            value = target.read(name)
            if len(value) != entry['bytes'] or hashlib.sha256(value).hexdigest() != entry['sha256']:
                raise ValueError('Packed archive member mismatch')
    if sha(features) != source_sha or any(sha(safe_file(cache, n)) != e['sha256'] for n, e in members.items()):
        raise ValueError('Feature inputs/cache changed during packing')
    result = {'schema': 'isaforge-v8-feature-evidence-v1',
              'archive': {'path': archive.name, 'sha256': sha(archive), 'bytes': archive.stat().st_size},
              'input_features_sha256': source_sha, 'feature_columns': data['columns'],
              'unique_original_formulas': len(seen), 'receipt_references': receipts,
              'cache_directories': len({str(PurePosixPath(n).parent) for n in members}),
              'files': [members[n] for n in sorted(members)],
              'packer_source_sha256': sha(__file__),
              'scope': 'Input-only original/normalized generic and SOG graphs/RTL/scripts/logs/receipts. '
                       'No target mapping or timed semantic normalization was run; preserve original V7 ledger separately.'}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('features', 'cache', 'archive', 'manifest'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = pack(args.features, args.cache, args.archive, args.manifest)
    print(json.dumps({key: result[key] for key in ('archive', 'unique_original_formulas', 'cache_directories')}))
