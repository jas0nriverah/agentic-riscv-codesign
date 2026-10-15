#!/usr/bin/env python3
"""Verify retained diagnostic bytes and original inputs without ML dependencies."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for record in manifest['files']:
        name = record['path']
        require(Path(name).name == name, 'Package member must be a flat filename')
        data = (HERE / name).read_bytes()
        require(len(data) == record['bytes'] and sha(data) == record['sha256'], 'Package member differs: ' + name)
    restored = gzip.decompress((HERE / 'diagnosis.json.gz').read_bytes())
    record = manifest['restored_full_diagnosis']
    require(len(restored) == record['bytes'] and sha(restored) == record['sha256'], 'Restored JSON differs')
    full = json.loads(restored)
    require(full['model_fit_calls'] == full['new_labels'] == 0, 'Read-only contract differs')
    require(full['script_sha256'] == sha((HERE / 'diagnose_support.py').read_bytes()), 'Diagnostic source differs')
    require(full['oracle_source_sha256'] == sha((HERE / 'audit.py').read_bytes()), 'Oracle source differs')
    cases = [r for q in full['queries'].values() for r in q['by_model'].values()]
    require(len(cases) == 35 and sum(len(r['all_300_tree_leaf_records']) for r in cases) == 10500, 'Leaf coverage differs')
    ledger = json.loads((HERE / 'source-input-hashes.json').read_text())
    records = ledger['repository_inputs'] + ledger['runtime_sources']
    for item in records:
        path = REPO / item['path']
        require(path.resolve().is_relative_to(REPO.resolve()), 'Input path escapes repository')
        require(sha(path.read_bytes()) == item['sha256'], 'Original input differs: ' + item['path'])
    proposal = json.loads((HERE / 'proposed-experiment-inputs.json').read_text())
    require(proposal['fitted_model_or_labels_created'] is False and len(proposal['inputs']) == 48, 'Proposal contract differs')
    print(json.dumps({'verified': True, 'package_files': len(manifest['files']),
        'input_and_source_digests': len(records), 'restored_full_json_sha256': sha(restored),
        'tree_leaf_records': 10500, 'model_fits': 0, 'new_labels': 0}, indent=2))


if __name__ == '__main__':
    main()
