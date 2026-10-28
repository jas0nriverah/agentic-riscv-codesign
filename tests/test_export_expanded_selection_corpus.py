import json

import pytest

from scripts import export_expanded_selection_corpus as exporter


def test_export_combines_only_sealed_complete_development_data(tmp_path):
    output = tmp_path / 'corpus'
    written = exporter.export(output)
    corpus, manifest = exporter.authenticate(output)
    assert len(manifest) == 4  # corpus/provenance payloads and their SHA sidecars
    assert written == corpus
    assert corpus['successful_labels'] == len(corpus['rows']) == 156
    assert corpus['failed_attempt_count'] == len(corpus['failed_attempts']) == 4
    assert corpus['total_candidate_attempts'] == 160
    assert corpus['new_candidate_attempts'] == 34
    assert corpus['all_rows_consumed_for_development'] is True
    assert corpus['scope'].startswith('consumed development')
    assert len({r['candidate_id'] for r in corpus['rows']}) == 156
    assert all(r['source_id'] == r['benchmark'] and r['candidate_family'] for r in corpus['rows'])
    assert all(r['data_use'] == 'consumed-development' for r in corpus['rows'])
    assert all(r['data_use'] == 'consumed-development' for r in corpus['failed_attempts'])
    assert {s['successful_rows'] for s in json.loads((output / 'provenance.json').read_text())['studies']} == {10, 12}


def test_manifest_authentication_detects_output_tampering(tmp_path):
    output = tmp_path / 'corpus'
    exporter.export(output)
    with (output / 'corpus.json').open('a') as stream:
        stream.write(' ')
    with pytest.raises(ValueError, match='Manifest mismatch'):
        exporter.authenticate(output)


@pytest.mark.parametrize('field,value', [('area_delta_lut4', 999999), ('workload_group', 'forged-group')])
def test_resigned_corpus_tampering_is_detected_against_sources(tmp_path, field, value):
    output = tmp_path / 'corpus'
    exporter.export(output)
    corpus = exporter.c.unseal(output / 'corpus.json')
    corpus['rows'][0][field] = value
    exporter.c.seal(output / 'corpus.json', corpus)
    manifest = exporter.c.unseal(output / 'manifest.json')
    manifest['corpus.json'] = exporter.sha(output / 'corpus.json')
    manifest['corpus.json.sha256'] = exporter.sha(output / 'corpus.json.sha256')
    exporter.c.seal(output / 'manifest.json', manifest)
    with pytest.raises(ValueError):
        exporter.authenticate(output)


def test_manifest_rejects_paths_outside_evidence_root(tmp_path):
    output = tmp_path / 'unsafe'
    output.mkdir()
    exporter.c.seal(output / 'manifest.json', {'../outside.json': '0' * 64})
    with pytest.raises(ValueError, match='escapes evidence root'):
        exporter.verify_manifest(output)


def test_normalizer_rejects_inconsistent_family_or_group():
    row = {'candidate_id': 'x', 'benchmark': 'nanocobs:abc', 'formula': 'add(in0,in1)',
           'candidate_family': 'sub(input,input)', 'workload_group': 'nanocobs',
           'correctness_verified': True, 'speedup': 1.0}
    with pytest.raises(ValueError, match='candidate_family'):
        exporter._normalise(row)
    row['candidate_family'] = exporter.family(row['formula'])
    row['workload_group'] = 'wrong'
    with pytest.raises(ValueError, match='workload_group'):
        exporter._normalise(row)
