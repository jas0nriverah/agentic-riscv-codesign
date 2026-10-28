import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

import pytest

from scripts import reproduce_countnegative_diagnosis as replay


def archive(tmp_path, names, link=False):
    raw = tmp_path / 'raw.tar.gz'
    data = b'evidence'
    with tarfile.open(raw, 'w:gz') as stream:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = '/tmp/outside'
                member.size = 0
            stream.addfile(member, None if link else io.BytesIO(data))
    manifest = dict(sha256=replay.c.sha(raw), bytes=raw.stat().st_size,
        files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
               for name in sorted(set(names))])
    return raw, manifest


@pytest.mark.parametrize('names,link', [(['../escape'], False), (['/absolute'], False),
    (['same', 'same'], False), (['symlink'], True), (['.'], False)])
def test_rejects_unsafe_members_before_writing(tmp_path, names, link):
    raw, manifest = archive(tmp_path, names, link)
    target = tmp_path / 'restored'
    with pytest.raises(ValueError):
        replay.restore(raw, manifest, target)
    assert not target.exists()


def test_rejects_tampered_member_before_writing(tmp_path):
    raw, manifest = archive(tmp_path, ['valid'])
    manifest['files'][0]['sha256'] = '0' * 64
    target = tmp_path / 'restored'
    with pytest.raises(ValueError, match='member hash'):
        replay.restore(raw, manifest, target)
    assert not target.exists()


def test_rejects_output_inside_sealed_results():
    with pytest.raises(ValueError, match='generated/'):
        replay.reproduce(replay.EVIDENCE / 'new-output')


def test_full_archive_replay_without_processes_or_original_native_root(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Replay attempted subprocess execution')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    original = replay.ROOT / 'generated/tacle-countnegative-2026-10-27'
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert not path.resolve().is_relative_to(original), 'Read original native root'
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', guarded_open)
    with tempfile.TemporaryDirectory(dir=replay.ROOT / 'generated') as temporary:
        output = Path(temporary) / 'replay'
        result = replay.reproduce(output)
        assert result['status'] == 'exact_replay'
        assert replay.inventory(output) == replay.inventory(replay.EVIDENCE)
