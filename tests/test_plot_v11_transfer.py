"""Synthetic-only publication contract checks; no actual V11 points or labels."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/plot_v11_transfer.py'
spec = importlib.util.spec_from_file_location('plot_v11_transfer_test', SCRIPT)
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def fixture(): return p.synthetic_fixture()


def test_reviewed_digest_required_for_library_and_exact_file_bytes(tmp_path):
    payload, _ = fixture()
    with pytest.raises(ValueError, match='caller-reviewed'): p.prepare_data(payload)
    digest = p.digest(p.canonical(payload))
    assert p.prepare_data(payload, reviewed_payload_sha256=digest)['synthetic_preview'] is False
    path = tmp_path/'payload.json'; path.write_text(json.dumps(payload, indent=2))
    with pytest.raises(ValueError, match='caller-reviewed'): p.prepare_data(path, reviewed_payload_sha256=digest)
    assert p.prepare_data(path, reviewed_payload_sha256=p.sha(path))['payload_sha256'] == p.sha(path)


def test_overlap_requires_own_review_digest():
    payload, overlap = fixture(); digest = p.digest(p.canonical(payload))
    with pytest.raises(ValueError, match='overlap SHA256'):
        p.prepare_data(payload, reviewed_payload_sha256=digest, overlap=overlap)
    data = p.prepare_data(payload, reviewed_payload_sha256=digest, overlap=overlap,
                          reviewed_overlap_sha256=p.digest(p.canonical(overlap)))
    assert 'does not independently authenticate' in data['admission']


def test_unchanged_score_zero_outliers_and_all_omissions():
    payload, overlap = fixture(); data = p.prepare_data(payload, synthetic_preview=True, overlap=overlap)
    assert data['score'] == p.scoring.score(**payload)
    assert data['score']['per_program']['recursion']['metrics']['V6'] is None
    assert data['score']['original_equal_all_program_endpoint']['available'] is False
    assert len(data['global_unique_points']) == 11
    assert max(r['actual'] for r in data['global_unique_points']) == 3000
    assert min(r['actual'] for r in data['global_unique_points']) == 0
    assert len(data['leave_one_family_out']) == 5
    for row in data['leave_one_family_out']:
        values = [f['equal_eligible_program_mae']['delta_v9_minus_v6'] for name, f in data['score']['per_family'].items() if name != row['omitted_family']]
        assert row['delta_v9_minus_v6'] == pytest.approx(sum(values)/4)


def test_optional_metadata_preserved_without_affecting_arithmetic():
    payload, _ = fixture(); expected = p.scoring.score(**payload)
    payload['metadata'] = {'scope':'SYNTHETIC provenance placeholder'}
    data = p.prepare_data(payload, synthetic_preview=True)
    assert data['scoring_inputs']['metadata'] == payload['metadata']
    assert data['score'] == expected


def test_overlap_expands_memberships_and_never_uses_skeleton_as_identity():
    payload, overlap = fixture()
    row = overlap['records'][2]
    row['pre_reservation_matches']['accepted_identity_component_originals'] = []
    for m in p.scoring.MODELS: row['training_overlap'][m]['accepted_identity_component_originals'] = []
    data = p.prepare_data(payload, synthetic_preview=True, overlap=overlap)
    n = data['score']['coverage']['program_formula_rows']
    for ref, channels in data['familiarity'].items():
        for cells in channels.values():
            assert sum(cells[s]['membership_count'] for s in ('familiar','unfamiliar')) == n
    c = data['familiarity']['pre_reservation']['canonical']['familiar']
    assert c['membership_count'] > c['unique_original_count']
    assert data['familiarity']['pre_reservation']['component']['unfamiliar']['membership_count'] > 0
    assert 'ordered_skeleton' not in data['familiarity']['pre_reservation']


@pytest.mark.parametrize('poison', ['duplicate','missing','extra','bool','component'])
def test_overlap_join_and_types_fail_closed(poison):
    payload, overlap = fixture(); overlap = copy.deepcopy(overlap)
    if poison == 'duplicate': overlap['records'][-1] = overlap['records'][0]
    if poison == 'missing': overlap['records'].pop()
    if poison == 'extra': overlap['records'][0]['candidate_id'] = 'unknown'
    if poison == 'bool': overlap['records'][0]['training_overlap']['V6']['canonical_seen'] = 1
    if poison == 'component': overlap['records'][0]['pre_reservation_matches']['accepted_identity_component_originals'] = []
    with pytest.raises(ValueError): p.prepare_data(payload, synthetic_preview=True, overlap=overlap)


def test_partial_inputs_never_plot():
    payload, _ = fixture(); payload['predictions']['V9'].pop()
    with pytest.raises(ValueError): p.prepare_data(payload, synthetic_preview=True)


def test_render_all_formats_marks_synthetic_and_binds_every_file(tmp_path):
    payload, overlap = fixture(); out = tmp_path/'preview'
    manifest = p.run(payload, out, synthetic_preview=True, overlap=overlap)
    assert len(manifest['files']) == 13
    for record in manifest['files']: assert p.sha(out/record['path']) == record['sha256']
    for svg in out.glob('*.svg'): assert 'SYNTHETIC' in svg.read_text()
    data = json.loads((out/'figure-data.json').read_text())
    assert data['global_unique_points'][-1]['id'] == sorted(r['id'] for r in payload['labels'])[-1]
    with pytest.raises(ValueError, match='Fresh'): p.run(payload, out, synthetic_preview=True)
