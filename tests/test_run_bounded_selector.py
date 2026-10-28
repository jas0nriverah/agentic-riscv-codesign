"""Actual frozen-data replay and tampering checks; no live measurements/models."""
import copy
from pathlib import Path
import shutil

import pytest

from isaforge import codesign as c
from scripts.run_bounded_selector import TARGETS, complete_frontier, load_case, run


def test_ten_matched_controls_reproduce_frozen_sha256(tmp_path):
    report = run(tmp_path/'run', targets=['sha256'], seeds=[0], caps=[64])
    assert report['trajectories'] == 10 and report['endpoints'] == 30
    assert report['all_controls_match'] is True
    assert report['llm_calls'] == report['new_native_jobs'] == 0
    values = {r['policy']: r for r in report['runs']}
    assert values['latency_cost_heuristic']['historical_attempt_seconds'] == pytest.approx(1698.1529543341312)
    heuristic = [p for p in report['endpoints_detail'] if p['policy'] == 'latency_cost_heuristic'][0]
    assert heuristic['best_speedup'] == pytest.approx(1.0213846654906067)
    assert heuristic['replayed_target_measurement_seconds'] == pytest.approx(67.4707846249803)
    for path, expected in c.unseal(tmp_path/'run'/'manifest.json').items():
        assert c.sha(tmp_path/'run'/path) == expected


def test_no_key_does_not_create_result_or_call_remote(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='no model call'):
        run(tmp_path/'missing', provider='responses', model='explicit-test-model')
    assert not (tmp_path/'missing').exists()


def test_zero_query_episode_is_in_every_budget_without_inventing_measurements():
    result = dict(curve=[], charged_attempts=0, status='finalized', selected_id=None, best_speedup=1.)
    values = complete_frontier(result, 3)
    assert [r['budget'] for r in values] == [1, 2, 3]
    assert all(r['best_speedup'] == 1 and r['actual_charged_attempts'] == 0 and
               r['replayed_target_measurement_seconds'] == 0 and r['carried_forward'] for r in values)


def test_early_stop_carries_incumbent_and_cost_without_survivor_bias():
    point = dict(budget=1, selected_id='paid', best_speedup=1.04,
                 attempted_ids=['paid'], measured_ids=['paid'], replayed_target_measurement_seconds=7.)
    result = dict(curve=[point], charged_attempts=1, status='model_error', selected_id='paid', best_speedup=1.04)
    values = complete_frontier(result, 3)
    assert all(r['best_speedup'] == 1.04 and r['actual_charged_attempts'] == 1 and
               r['replayed_target_measurement_seconds'] == 7 for r in values)
    assert [r['carried_forward'] for r in values] == [False, True, True]
    assert point['budget'] == 1


def test_finalized_choice_and_best_performance_found_remain_distinct():
    result = dict(curve=[dict(budget=1, selected_id='paid', best_speedup=1.04)],
                  charged_attempts=1, status='finalized', selected_id=None, best_speedup=1.)
    point = complete_frontier(result, 1)[0]
    assert point['best_speedup'] == 1.04 and point['selected_id'] == 'paid'
    assert point['finalized_speedup'] == 1. and point['finalized_selected_id'] is None


def test_frozen_artifact_tampering_rejected(tmp_path):
    folder = c.ROOT/TARGETS['sha256']
    shutil.copytree(folder, tmp_path/'case')
    value = c.unseal(tmp_path/'case'/'public.json')
    value[0]['runs'] += 1
    c.seal(tmp_path/'case'/'public.json', value)
    with pytest.raises(ValueError, match='artifact changed'):
        load_case(tmp_path/'case')


def test_private_outcome_change_rejected_even_when_resealed(tmp_path):
    shutil.copytree(c.ROOT/TARGETS['sha256'], tmp_path/'case')
    value = c.unseal(tmp_path/'case'/'report.json')
    for candidate in value['runs']:
        for event in candidate['events']:
            if 'observation' in event:
                event['observation']['area_delta_lut4'] += 1
    c.seal(tmp_path/'case'/'report.json', value)
    with pytest.raises(ValueError, match='outcome binding'):
        load_case(tmp_path/'case')


@pytest.mark.parametrize('kwargs', [dict(targets=['unknown']), dict(seeds=[0, 0]),
                                    dict(caps=[-1]), dict(budget=0)])
def test_invalid_experiment_grid_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError): run(tmp_path/'bad', **kwargs)
    assert not (tmp_path/'bad').exists()


def test_memory_modes_preserve_controls_and_sql_trace(tmp_path):
    import sqlite3
    from scripts.export_agent_observability import export
    report = run(tmp_path/'hybrid', targets=['sha256'], seeds=[0], caps=[64], memory_mode='hybrid')
    assert report['all_controls_match'] and report['llm_calls'] == 0
    summary = export(tmp_path/'hybrid', tmp_path/'trace.sqlite')
    assert summary['episodes'] == 10 and summary['retrievals'] > 0
    with sqlite3.connect(tmp_path/'trace.sqlite') as db:
        assert db.execute('SELECT COUNT(*) FROM tools WHERE tool="measure"').fetchone()[0] == 30
        assert db.execute('SELECT COUNT(*) FROM decisions WHERE tool_sequence IS NULL').fetchone()[0] == 0
    with pytest.raises(ValueError, match='fresh output'):
        export(tmp_path/'hybrid', tmp_path/'trace.sqlite')
    ledger = tmp_path/'hybrid'/report['runs'][0]['ledger']
    ledger.write_text('{}')
    with pytest.raises(ValueError):
        export(tmp_path/'hybrid', tmp_path/'tampered.sqlite')
