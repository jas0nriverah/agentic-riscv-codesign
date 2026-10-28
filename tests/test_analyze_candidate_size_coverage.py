import hashlib
import tarfile

import pytest

from isaforge import assembly_lowering
from scripts import analyze_candidate_size_coverage as analysis


def test_size_override_changes_only_extractor_maxsize_and_restores():
    original = assembly_lowering.discovery.extractCandidates
    seen = []

    def fake(program, runs, starts, maxSize=5, limit=None):
        seen.append((maxSize, limit))
        return {'maxSize': maxSize}

    assembly_lowering.discovery.extractCandidates = fake
    try:
        with analysis.extraction_size(6):
            assert assembly_lowering.discovery.extractCandidates({}, {}, set(), maxSize=4) == {'maxSize': 6}
        assert assembly_lowering.discovery.extractCandidates is fake
    finally:
        assembly_lowering.discovery.extractCandidates = original
    assert seen == [(6, None)]
    assert assembly_lowering.discovery.extractCandidates is original


@pytest.mark.parametrize('cap', [4, 5, 6])
def test_only_declared_caps_are_accepted(cap):
    original = assembly_lowering.discovery.extractCandidates
    with analysis.extraction_size(cap):
        assert assembly_lowering.discovery.extractCandidates is not original
    assert assembly_lowering.discovery.extractCandidates is original


def test_unbounded_or_unsupported_caps_are_rejected():
    for cap in (3, 7, 30):
        with pytest.raises(ValueError, match='declared'):
            with analysis.extraction_size(cap):
                pass


@pytest.mark.parametrize('study,count', [
    ('countnegative-v2', 4), ('stringsearch-v2', 2), ('nanocobs-v2', 10),
])
def test_authenticated_baseline_only_caps_reproduce_without_expanding_pool(study, count):
    report = analysis.analyze_study(study)
    assert report['caps']['4']['matches_authenticated_cap4_discovery'] is True
    assert report['caps']['4']['signed_candidate_count'] == count
    assert [report['caps'][str(cap)]['calibrated_relocation_safe_formula_count']
            for cap in analysis.CAPS] == [count, count, count]
    assert [report['caps'][str(cap)]['executable_formula_count']
            for cap in analysis.CAPS].count(report['caps']['4']['executable_formula_count']) == 3
    assert all(not report['caps'][str(cap)]['benefit_or_occurrence_filters_applied']
               for cap in analysis.CAPS)
    assert report['scope'].startswith('Exploratory baseline-only')


def test_resealed_native_input_cannot_differ_from_archived_baseline(tmp_path):
    native = tmp_path / 'native'
    native.mkdir()
    value = native / 'discovery' / 'profile.json'
    analysis.c.seal(value, {'cycles': 10})
    archive_path = tmp_path / 'raw.tar.gz'
    with tarfile.open(archive_path, 'w:gz') as stream:
        stream.add(value, arcname='discovery/profile.json')
    raw = value.read_bytes()
    archive = {'archive': 'raw.tar.gz', 'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        'bytes': archive_path.stat().st_size, 'files': [{'path': 'discovery/profile.json',
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]}
    analysis.verify_native_archive_members(archive_path, archive, native)

    analysis.c.seal(value, {'cycles': 999})  # Valid local sidecar, substituted evidence payload.
    with pytest.raises(ValueError, match='Native baseline file differs'):
        analysis.verify_native_archive_members(archive_path, archive, native)


def test_profile_and_timed_region_replacement_counts_are_separate():
    report = analysis.analyze_study('countnegative-v2')
    row = report['caps']['4']['formulas'][0]
    assert row['total_profile_replacements'] == 2
    assert row['timed_region_replacements'] == 1
    assert row['projected_cycle_reduction'] > 0


def test_analysis_restores_sealed_archive_without_old_generated_root(tmp_path):
    study = 'stringsearch-v2'
    module, evidence_root, _old_root = analysis.STUDIES[study]
    nonexistent = tmp_path / 'generated-root-must-not-be-read'
    analysis.STUDIES[study] = (module, evidence_root, nonexistent)
    try:
        report = analysis.analyze_study(study)
    finally:
        analysis.STUDIES[study] = (module, evidence_root, _old_root)
    assert not nonexistent.exists()
    assert report['caps']['4']['matches_authenticated_cap4_discovery'] is True
    assert report['caps']['4']['signed_candidate_count'] == 2
