"""User-facing launcher failure handling; no package installs or native jobs."""
import importlib.util
from pathlib import Path
import subprocess
import os
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('startup', ROOT / 'scripts/startup.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


def test_missing_environment_check_is_read_only_and_works_outside_repo(tmp_path):
    env = dict(os.environ, ISAFORGE_VENV=str(tmp_path / 'missing env'))
    result = subprocess.run([str(ROOT / 'start.sh'), '--check'], cwd=tmp_path,
                            env=env, text=True, capture_output=True)
    assert result.returncode == 1
    assert 'Missing environment' in result.stderr
    assert not (tmp_path / 'missing env').exists()


def test_unknown_option_fails_before_bootstrap(tmp_path):
    env = dict(os.environ, ISAFORGE_VENV=str(tmp_path / 'missing'))
    result = subprocess.run([str(ROOT / 'start.sh'), '--unknown'], env=env,
                            text=True, capture_output=True)
    assert result.returncode == 2
    assert not (tmp_path / 'missing').exists()


def test_incomplete_environment_is_not_overwritten(tmp_path):
    path = tmp_path / 'broken env'
    path.mkdir()
    marker = path / 'keep'; marker.write_text('user data')
    result = subprocess.run([str(ROOT / 'start.sh')],
                            env=dict(os.environ, ISAFORGE_VENV=str(path)),
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert 'Incomplete environment' in result.stderr
    assert marker.read_text() == 'user data'


def test_dependency_mismatch_is_actionable(monkeypatch):
    monkeypatch.setattr(startup, 'version', lambda name: '0.0.0')
    with pytest.raises(ValueError, match='numpy: need .*found 0.0.0'):
        startup.dependencies()
