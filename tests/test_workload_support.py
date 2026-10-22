"""Archived original profiles, not fresh native artifacts, establish these checks."""
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

from scripts import diagnose_workload_support as d
from isaforge import codesign as c

REPO = d.ROOT
SNAPSHOT = REPO/d.QUALIFICATION


@pytest.fixture
def archive_only_repo(tmp_path, monkeypatch):
    """A repository mirror with no original generated roots, tools or native jobs.

    Explicitly forbid reads at the real generated roots, including accidental
    absolute paths retained inside the historical commands and plans.
    """
    mirror = tmp_path/'repo'
    snapshot = mirror/d.QUALIFICATION
    shutil.copytree(SNAPSHOT, snapshot)
    sources = dict(c.read(snapshot/'protocol.json')['source_bindings'])
    sources[d.SOURCE] = c.sha(REPO/d.SOURCE)
    for archive in snapshot.glob('*/raw.tar.gz'):
        with tarfile.open(archive) as stream:
            sources.update(json.load(stream.extractfile('plan.json'))['source_bindings'])
    for name in sources:
        destination = mirror/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO/name, destination)
    assert not (mirror/'generated').exists()
    original_open = Path.open

    def archived_only(path, *args, **kwargs):
        if path.is_absolute() and path.is_relative_to(REPO/'generated'):
            raise AssertionError('Original generated roots must be unavailable')
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError('No native/compiler/model process or candidate lowering allowed')

    monkeypatch.setattr(Path, 'open', archived_only)
    monkeypatch.setattr(c, 'ROOT', mirror)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(d.al, 'lower', forbidden)
    return mirror, snapshot


def test_archives_alone_reproduce_all_failures_and_coverage(archive_only_repo):
    mirror, snapshot = archive_only_repo
    report = d.diagnose(snapshot, mirror/'derived/first')
    assert report['target_candidate_attempts'] == report['native_jobs_run'] == report['candidate_lowerings_run'] == 0
    rows = {row['workload']:row for row in report['workloads']}
    assert [r.get('calibrated_eligible_count') for r in rows.values()] == [0, 0, 1, 1, 0, 0, None, 0]
    assert sum(r['status'] == 'discovery_rejected' for r in rows.values()) == 7
    assert rows['janne_complex']['status'] == 'static_rejection'
    assert all(not r['twelve_formula_gate_passed'] and not r['both_numeric_minima_formulas']
               for r in rows.values() if 'calibrated_eligible_count' in r)
    assert rows['cnt']['relocation_guard']['rejections'][0]['unsafe_sites'][0]['reason'] == 'relocation_modifier'
    prime = rows['prime']
    assert prime['baseline_performance']['cycles'] == 386055
    assert prime['eligible'][0]['formula'] == 'andi(xori(in0,1),255)'
    assert prime['eligible'][0]['timed_replacements'] == 1
    assert prime['eligible'][0]['latency_features']['estimated_saved_cycles'] == 3
    coverage = prime['timed_source_coverage']
    assert (coverage['mapped_source_instructions'], coverage['profile_instructions']) == (3071, 75682)
    assert coverage['outside_symbols']['__hidden___udivsi3'] == 48006
    assert sum(coverage['outside_symbols'].values()) + 3071 == 75682
    insertion = rows['insertsort']['eligible'][0]
    assert insertion['timed_replacements'] == 9
    assert insertion['latency_features']['estimated_saved_cycles'] == 45
    assert insertion['latency_features']['estimated_cycle_reduction'] == 45/2221
    for row in rows.values():
        if 'timed_source_coverage' in row:
            value = row['timed_source_coverage']
            assert value['profile_instructions']+1 == value['counter_instructions']
    assert not any(str(REPO) in key for key in report['source_bindings'])
    assert not list((mirror/'generated').iterdir())  # restored evidence is temporary
    assert c.unseal(mirror/'derived/first/support.json') == report
    assert d.diagnose(snapshot, mirror/'derived/replay') == report
    with pytest.raises(ValueError, match='Fresh diagnostic output'):
        d.diagnose(snapshot, mirror/'derived/first')


def test_changed_runtime_source_rejected(archive_only_repo):
    mirror, snapshot = archive_only_repo
    source = mirror/'isaforge/latency_features.py'
    source.write_bytes(source.read_bytes()+b'\n# altered\n')
    with pytest.raises(ValueError, match='Bound source changed'):
        d.diagnose(snapshot, mirror/'derived/tampered')
    assert not (mirror/'derived/tampered').exists()


def test_changed_archive_byte_rejected(archive_only_repo):
    mirror, snapshot = archive_only_repo
    source = snapshot/'prime/raw.tar.gz'
    value = bytearray(source.read_bytes())
    value[-20] ^= 1
    source.write_bytes(value)
    with pytest.raises(ValueError, match='Qualification evidence changed'):
        d.diagnose(snapshot, mirror/'derived/tampered')


@pytest.mark.parametrize('artifact', ['inputs/program.c', 'plan.json'])
def test_restored_input_and_context_are_independently_authenticated(archive_only_repo, artifact):
    mirror, snapshot = archive_only_repo
    restored = mirror/'restored'
    archive = c.unseal(snapshot/'prime/archive-manifest.json')
    d.restore_archive(snapshot/'prime', archive, restored)
    if artifact == 'plan.json':
        plan = c.unseal(restored/artifact)
        plan['context_id'] = '0'*64
        c.seal(restored/artifact, plan)
    else:
        source = restored/artifact
        source.write_bytes(source.read_bytes()+b'\n')
    with pytest.raises(ValueError):
        d.profile_support(restored, archive)


def test_safe_restorer_rejects_resealed_archive_with_old_inventory(archive_only_repo):
    mirror, snapshot = archive_only_repo
    folder = snapshot/'prime'
    archive = c.unseal(folder/'archive-manifest.json')
    archive['files'][0]['sha256'] = '0'*64
    with pytest.raises(ValueError, match='Member checksum mismatch'):
        d.restore_archive(folder, archive, mirror/'restored')


def test_output_inside_qualification_rejected_before_restore_or_writes(archive_only_repo, monkeypatch):
    mirror, snapshot = archive_only_repo
    before = {p.relative_to(snapshot):c.sha(p) for p in snapshot.rglob('*') if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Rejected output must not restore any archive')

    monkeypatch.setattr(d, 'restore_archive', forbidden)
    output = snapshot/'new-child'
    with pytest.raises(ValueError, match='separate from the qualification snapshot'):
        d.diagnose(snapshot, output)
    assert not output.exists()
    assert not (mirror/'generated').exists()
    assert {p.relative_to(snapshot):c.sha(p) for p in snapshot.rglob('*') if p.is_file()} == before
    assert c.unseal(snapshot/'manifest.json')


def test_output_under_other_sealed_result_rejected(archive_only_repo):
    mirror, snapshot = archive_only_repo
    sealed = mirror/'results/other-sealed-result'
    sealed.mkdir()
    c.seal(sealed/'manifest.json', {'preserved':True})
    output = sealed/'new-child/nested'
    with pytest.raises(ValueError, match='already sealed result root'):
        d.diagnose(snapshot, output)
    assert not (sealed/'new-child').exists()
    assert c.unseal(sealed/'manifest.json') == {'preserved':True}
