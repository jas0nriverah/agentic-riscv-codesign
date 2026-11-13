"""The compatibility wrapper restores prose only; it never repairs evidence."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_coverage', ROOT/'scripts/check_coverage.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def fixture(root):
    path = root/'tests/fixtures/coverage-results-readme.md'
    path.parent.mkdir(parents=True)
    path.write_bytes((ROOT/'tests/fixtures/coverage-results-readme.md').read_bytes())
    for experiment in ('targeted-coverage','budget-preserving-coverage'):
        p=root/'results'/experiment/'auditor-prior-artifacts.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'files':{'results/README.md':checker.HISTORICAL_README_SHA}}))


def test_only_prose_is_restored_and_checkout_is_untouched(tmp_path, monkeypatch):
    root=tmp_path/'source';root.mkdir();fixture(root)
    (root/'results/README.md').write_text('current presentation')
    (root/'results/evidence.json').write_text('even changed evidence must be passed to the real audit')
    names=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()]
    monkeypatch.setattr(checker.subprocess,'check_output',lambda *a,**k:('\0'.join(names)+'\0').encode())
    target=tmp_path/'snapshot'
    checker.prepare_snapshot(root,target)
    assert (target/'results/README.md').read_bytes()==checker.historical_readme(root)
    assert (root/'results/README.md').read_text()=='current presentation'
    assert (target/'results/evidence.json').read_bytes()==(root/'results/evidence.json').read_bytes()
    assert (target/'results/evidence.json').stat().st_ino!=(root/'results/evidence.json').stat().st_ino


def test_modified_historical_prose_is_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path/'tests/fixtures/coverage-results-readme.md').write_text('changed')
    with pytest.raises(ValueError,match='fixture changed'): checker.historical_readme(tmp_path)


def test_inventory_mismatch_is_rejected(tmp_path):
    fixture(tmp_path)
    p=tmp_path/'results/targeted-coverage/auditor-prior-artifacts.json'
    p.write_text(json.dumps({'files':{'results/README.md':'incorrect'}}))
    with pytest.raises(ValueError,match='inventory'): checker.historical_readme(tmp_path)
