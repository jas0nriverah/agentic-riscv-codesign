"""Keep incomplete paid evidence usable for training and unusable as an oracle."""
from __future__ import annotations

import copy
import subprocess

import pytest

from isaforge import ascon_training_supplement as supplement, codesign as c


@pytest.fixture(scope='module')
def audited():
    # Real archived RTL/netlist/route recount and all three audit-prefix hashes.
    # It invokes neither a native tool nor a model fit.
    def forbidden(*args, **kwargs):
        raise AssertionError('Training importer must not dispatch tools or fit models')
    from isaforge.model import SpeedupPredictor
    from isaforge.ranking import SpeedupRanker
    from isaforge.budgeted_selection import HardwareSurrogate
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, 'run', forbidden)
        patch.setattr(subprocess, 'Popen', forbidden)
        for model in (SpeedupPredictor, SpeedupRanker, HardwareSurrogate):
            patch.setattr(model, 'fit', forbidden)
        return supplement.build()


def test_real_archive_preserves_paid_outcomes_without_a_complete_oracle(audited):
    rows = supplement.validate(audited)
    assert [(row['candidate_cycles'], row['area_delta_lut4']) for row in rows] == [
        (242448246, 73), (243085014, 41), (241493094, 42)]
    assert all(row['correctness_verified'] and row['baseline_cycles'] == 247224006 for row in rows)
    assert audited['audit_prefix_sha256'] == list(supplement.AUDIT_PINS)
    assert len(audited['full_target_roster']) == 12
    assert len(audited['unmeasured_candidate_ids']) == 9
    assert audited['oracle'] is None and audited['evaluation_eligible'] is False
    assert all(audited['row_evidence'][row['candidate_id']]['historical_family_matches'] for row in rows)
    assert 'rows' not in audited and 'failed_attempts' not in audited


@pytest.mark.parametrize('purpose', ['test', 'evaluation', 'oracle', None])
def test_nontraining_use_fails_before_loading_or_scoring(audited, tmp_path, purpose):
    with pytest.raises(ValueError, match='training-only'):
        supplement.validate(audited, purpose=purpose)
    with pytest.raises(ValueError, match='training-only'):
        supplement.load(tmp_path/'does-not-exist', purpose=purpose)


@pytest.mark.parametrize('field,value', [
    ('training_only', False), ('evaluation_eligible', True), ('complete_pool', True),
    ('independent_confirmatory_families', 1), ('oracle', {'speedup': 1.023731}),
])
def test_incomplete_pool_cannot_be_relabelled_for_confirmation(audited, field, value):
    changed = copy.deepcopy(audited)
    changed[field] = value
    with pytest.raises(ValueError, match='contract'):
        supplement.validate(changed)


def test_attempted_roster_cannot_hide_unmeasured_candidates(audited):
    changed = copy.deepcopy(audited)
    changed['full_target_roster'] = [row for row in changed['full_target_roster']
                                   if row['candidate_id'] not in changed['unmeasured_candidate_ids']]
    changed['unmeasured_candidate_ids'] = []
    with pytest.raises(ValueError, match='twelve'):
        supplement.validate(changed)


def test_changed_measurement_fails_provenance_even_with_valid_arithmetic(audited):
    changed = copy.deepcopy(audited)
    row = changed['training_rows'][0]
    row['area'] -= 1
    row['area_delta_lut4'] -= 1
    with pytest.raises(ValueError, match='provenance'):
        supplement.validate(changed)


def test_validated_rows_are_independent_copies(audited):
    rows = supplement.validate(audited)
    rows[0]['latency_features']['estimated_saved_cycles'] = -1
    assert audited['training_rows'][0]['latency_features']['estimated_saved_cycles'] == 4775760


def test_tampered_archived_report_rejected_before_raw_audit(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    # Authentication reads the report first, so a changed report cannot reach
    # archive restoration or borrow the neighboring valid archive's labels.
    (source/'report.json').write_text('{}')
    with pytest.raises(ValueError, match='Pinned Ascon source changed: report.json'):
        supplement.build(source=source)


def test_sealed_export_round_trip_and_tamper_rejection(audited, tmp_path, monkeypatch):
    # Reuse the real audited build; the writer/loader must preserve every row.
    monkeypatch.setattr(supplement, 'build', lambda **kwargs: copy.deepcopy(audited))
    output = tmp_path/'supplement'
    supplement.export(output)
    assert supplement.load(output) == audited['training_rows']
    with pytest.raises(ValueError, match='Fresh output'):
        supplement.export(output)
    value = c.unseal(output/'supplement.json')
    value['training_rows'][0]['candidate_cycles'] -= 1
    c.seal(output/'supplement.json', value)
    with pytest.raises(ValueError, match='manifest member changed'):
        supplement.load(output)
