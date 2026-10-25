"""The offline Lift coverage preflight must consume the archived rejection inputs."""
from pathlib import Path

import pytest

from isaforge import codesign as c
from scripts import preflight_cfg_lift_tail as preflight


def archived_native_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    monkeypatch.setattr(preflight, 'REJECTION', 'results/rejection')
    package = tmp_path / preflight.REJECTION
    package.mkdir(parents=True)
    native = tmp_path / 'generated/native'
    entries = []
    for index, suffix in enumerate(preflight.ARTIFACT_SUFFIXES):
        path = native / suffix
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f'archived-input-{index}'.encode()
        path.write_bytes(content)
        entries.append(dict(path=suffix, bytes=len(content), sha256=c.sha(path)))
    archive = package / 'raw.tar.gz'
    archive.write_bytes(b'archive-identity')
    record = dict(archive='raw.tar.gz', sha256=c.sha(archive), bytes=archive.stat().st_size,
                  files=entries)
    c.seal(package / 'archive-manifest.json', record)
    rejection = dict(raw_archive_sha256=record['sha256'],
                     archive_manifest_sha256=c.sha(package / 'archive-manifest.json'))
    return native, rejection


def test_preflight_authenticates_each_consumed_input_against_frozen_archive(tmp_path, monkeypatch):
    native, rejection = archived_native_fixture(tmp_path, monkeypatch)
    observed = preflight.authenticate_saved_native(native, rejection)
    assert len(observed) == len(preflight.ARTIFACT_SUFFIXES)
    path = native / preflight.ARTIFACT_SUFFIXES[0]
    path.write_text('changed saved disassembly')
    with pytest.raises(ValueError, match='differs from rejected native archive'):
        preflight.authenticate_saved_native(native, rejection)


def test_preflight_rejects_missing_archived_input(tmp_path, monkeypatch):
    native, rejection = archived_native_fixture(tmp_path, monkeypatch)
    (native / preflight.ARTIFACT_SUFFIXES[-1]).unlink()
    with pytest.raises(ValueError, match='Missing or escaped saved Lift input'):
        preflight.authenticate_saved_native(native, rejection)
