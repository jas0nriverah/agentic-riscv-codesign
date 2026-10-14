import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('archive_external_v5', Path(__file__).parents[1]/'scripts/archive_external_v5.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def fixture_bundle(root):
    bundle = root/'results/external'
    (bundle/'measurements').mkdir(parents=True)
    scratch = root/archive.PREFIX/'attempt-0000'
    scratch.mkdir(parents=True)
    (scratch/'netlist.json').write_text('{"cells": {}}')
    for name in ('obj_dir', 'obj_dir_wrapv'):
        (scratch/name).mkdir()
        (scratch/name/'compiler.o').write_bytes(b'generated-object')
    (bundle/'measurements/completion.json').write_text(json.dumps({
        'complete': True, 'failures': [],
        'scratch_directory': '../../'+archive.PREFIX+'attempt-0000'}))
    archive.pack(bundle, root)
    return bundle, scratch


def test_restore_portable_and_idempotent(tmp_path):
    bundle, scratch = fixture_bundle(tmp_path/'original')
    moved = tmp_path/'new'
    archive.restore(bundle, moved)
    archive.restore(bundle, moved)
    assert (moved/archive.PREFIX/'attempt-0000/netlist.json').read_text() == (scratch/'netlist.json').read_text()
    assert not (moved/archive.PREFIX/'attempt-0000/obj_dir').exists()
    assert not (moved/archive.PREFIX/'attempt-0000/obj_dir_wrapv').exists()


def test_restore_refuses_changed_existing_file(tmp_path):
    bundle, scratch = fixture_bundle(tmp_path)
    (scratch/'netlist.json').write_text('changed')
    with pytest.raises(ValueError, match='refusing overwrite'):
        archive.restore(bundle, tmp_path)
    assert (scratch/'netlist.json').read_text() == 'changed'


def test_archive_corruption_rejected(tmp_path):
    bundle, _ = fixture_bundle(tmp_path)
    with (bundle/'raw-evidence.zip').open('ab') as out:
        out.write(b'changed')
    with pytest.raises(ValueError, match='SHA differs'):
        archive.restore(bundle, tmp_path)


@pytest.mark.parametrize('path', ['/tmp/escape', archive.PREFIX+'../escape', 'generated/other/file', archive.PREFIX+'a\\b'])
def test_unexpected_path_rejected(tmp_path, path):
    with pytest.raises(ValueError, match='Unexpected archive path'):
        archive.destination(path, tmp_path)


def test_symlinked_evidence_root_cannot_escape(tmp_path):
    root = tmp_path/'restore'
    allowed = root/archive.PREFIX
    allowed.parent.mkdir(parents=True)
    outside = tmp_path/'outside'
    outside.mkdir()
    allowed.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='leaves evidence directory'):
        archive.destination(archive.PREFIX+'file', root)
