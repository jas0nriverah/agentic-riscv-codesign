"""Regression checks for the prospective countnegative selector boundary."""
from __future__ import annotations

from io import StringIO

import pytest

from isaforge import codesign as c
from isaforge import guarded_attempts as attempts
from isaforge import countnegative_v2_workload as workload
from scripts import execute_countnegative_v2_selector as study
from test_bounded_selector import grouped_metadata, grouped_prediction_bundle
from test_budgeted_selection import history, public


def _public_pool():
    return [
        public("countnegative-1", saved_cycles=60),
        public("countnegative-2", "sub(in0,slli(in1,1))", saved_cycles=20),
        public("countnegative-3", "add(in0,srli(in1,1))", saved_cycles=30),
    ]


def test_live_agent_request_names_held_out_countnegative_scope_and_no_inherited_failure(tmp_path):
    target = _public_pool()
    training = history()
    session = study.ProspectiveLiveSelectionSession(
        target,
        training,
        None,
        lambda row: row,
        area_cap=study.AREA_CAP,
        budget=study.BUDGET,
        ledger_path=tmp_path / "ledger.json",
        historical_available_rows=106,
        grouped_predictions=grouped_prediction_bundle(target),
        grouped_model_metadata=grouped_metadata(),
    )

    request = session.request()
    text = str(request)
    assert "original deterministic 20x20 countnegative matrix and fixed checksum" in text
    assert "exact operator-tree families are excluded" in text
    assert "regex" not in text.lower()
    assert "unseen-workload experiment" not in text
    assert "startup failure" not in text.lower()
    assert session.ledger["scope"] == (
        "prospective live measurement on a source- and exact-family-held-out workload"
    )
    assert session.ledger["returned_observation_measurement_seconds"] == 0
    assert "target_attempt_wall_seconds" not in session.ledger
    assert not hasattr(study, "STARTUP_FAILURE")


def test_agent_measurement_and_resource_budget_remain_frozen():
    assert study.BUDGET == 3
    assert study.AREA_CAP == 64
    assert study.CLOCK_MHZ == 12.0
    assert study.MAX_MODEL_CALLS == 12
    assert study.MAX_TOOL_CALLS == 20
    assert study.RESULTS.name == "2026-10-28-countnegative-v2-selection-r1"
    assert study.PREREG.name == "2026-10-28-countnegative-v2-selector-prereg-r2"


def test_agent_refuses_a_noninteractive_stdin_before_creating_an_episode():
    with pytest.raises(ValueError, match="interactive PTY"):
        study._require_interactive_relay(StringIO())


def test_agent_attempt_costs_include_charged_attempt_even_when_projection_is_missing(tmp_path):
    native = tmp_path / "native"
    study_root = tmp_path / "study"
    names = {"target-a": "candidate_1", "target-b": "candidate_2"}
    first = attempts.ledger_path(native, names["target-a"])
    second = attempts.ledger_path(native, names["target-b"])
    c.seal(first, dict(schema=attempts.SCHEMA, name=names["target-a"],
        status="failed", elapsed_seconds=2.5, artifacts={}))
    c.seal(second, dict(schema=attempts.SCHEMA, name=names["target-b"],
        status="started", elapsed_seconds=None, artifacts={}))
    timer = study_root / "outer-times" / "target-a.json"
    c.seal(timer, dict(candidate_id="target-a", status="failed", elapsed_seconds=3.0))

    costs = study._agent_attempt_costs(native, study_root, set(names), names, {"target-a"})

    assert costs["measurement_seconds"] is None
    assert costs["known_measurement_seconds"] == 2.5
    assert costs["measurement_time_unknown_ids"] == ["target-b"]
    assert costs["outer_operation_seconds"] is None
    assert costs["known_outer_operation_seconds"] == 3.0
    assert costs["outer_operation_time_unknown_ids"] == ["target-b"]
    assert costs["attempts"][0]["outcome_returned_to_selector"] is True
    assert costs["attempts"][1]["outcome_returned_to_selector"] is False


def test_agent_startup_refuses_any_preexisting_candidate_attempt(tmp_path):
    workload.require_zero_candidates(tmp_path)
    ledger = attempts.ledger_path(tmp_path, "candidate_1")
    c.seal(ledger, dict(schema=attempts.SCHEMA, name="candidate_1",
        status="failed", elapsed_seconds=0.1, artifacts={}))
    try:
        workload.require_zero_candidates(tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("preexisting target attempt was not rejected")


def test_selection_evaluator_reuses_exact_frozen_multitu_compiler():
    assert study.ReleaseBoundEvaluator.compile_program is workload.Evaluator.compile_program
    assert study.ReleaseBoundEvaluator.__bases__ == (study.guarded.Evaluator,)


def test_unknown_candidate_is_rejected_before_native_or_ledger_dispatch(monkeypatch):
    evaluator = study.ReleaseBoundEvaluator.__new__(study.ReleaseBoundEvaluator)
    monkeypatch.setattr(study, '_verify_release', lambda:
        ({}, {}, dict(pool=[dict(name='candidate_00')])))
    monkeypatch.setattr(study.guarded.Evaluator, 'measure',
        lambda *args: pytest.fail('Unknown candidate reached native dispatch'))
    with pytest.raises(ValueError, match='outside signed actual pool'):
        evaluator.measure('candidate_99')


def test_release_roster_authenticates_names_ids_formulas_context_and_actual_size():
    import copy
    rows = [dict(name=f'candidate_{i:02d}', candidate_id=f'id-{i}', formula=f'formula-{i}')
            for i in range(4)]
    prereg = dict(target_candidate_ids=[r['candidate_id'] for r in rows])
    record = dict(pool_roster=copy.deepcopy(rows), target_context_id='context')
    discovery = dict(pool=rows, context_id='context')
    study._require_release_roster(prereg, record, discovery)
    for key in ('name', 'candidate_id', 'formula'):
        altered = copy.deepcopy(record)
        altered['pool_roster'][0][key] = 'changed'
        with pytest.raises(ValueError, match='IDs, formulas or context differ'):
            study._require_release_roster(prereg, altered, discovery)
    altered = dict(record, target_context_id='changed')
    with pytest.raises(ValueError, match='IDs, formulas or context differ'):
        study._require_release_roster(prereg, altered, discovery)


def test_recent_overlap_only_reads_public_rosters_and_derives_families(tmp_path, monkeypatch):
    from scripts import prepare_countnegative_v2_selector as prep
    roster = [public('prior', 'add(in0,in1)')]
    c.seal(tmp_path / 'prior/public.json', roster)
    monkeypatch.setattr(prep, 'ROOT', tmp_path)
    monkeypatch.setattr(prep, 'RECENT_PUBLIC_ROSTERS', ('prior/public.json',))
    result = prep.recent_public_overlap([public('target', 'add(in0,in1)')])
    assert result[0]['candidate_count'] == 1
    assert result[0]['target_overlap_candidate_ids'] == ['target']
    assert result[0]['overlapping_families']
    assert result[0]['sha256'] == c.sha(tmp_path / 'prior/public.json')


def test_no_inherited_prior_relay_failure_provenance_or_human_action_approval():
    from pathlib import Path
    from scripts import prepare_countnegative_v2_selector as prep
    source = Path(study.__file__).read_text()
    assert 'PREVIOUS_RELAY_FAILURE' not in source
    assert 'prior-relay-startup-failure' not in source
    preparation = Path(prep.__file__).read_text()
    assert 'A human relay supplies' not in preparation
    assert 'no human review of each action' in preparation


def test_expanded_r2_history_is_authenticated_and_current_target_absent():
    from scripts import prepare_countnegative_v2_selector as prep
    corpus = prep._history()
    assert prep.HISTORY.parent.name == '2026-10-28-expanded-selection-corpus-r2'
    assert len(corpus['rows']) == 156
    assert len(corpus['failed_attempts']) == 4
    assert corpus['total_candidate_attempts'] == 160
    assert all(r['workload_group'] != workload.GROUP for r in corpus['rows'])


def test_whole_target_source_and_every_target_family_excluded_before_fitting():
    from scripts import prepare_countnegative_v2_selector as prep
    target = [public('target', 'add(in0,in1)')]
    rows = [dict(public('same-source', 'sub(in0,in1)'), workload_group=workload.GROUP),
            dict(public('same-family', 'add(in0,in1)'), workload_group='other'),
            dict(public('retained', 'sub(in0,in1)'), workload_group='other')]
    training, excluded = prep.split_training(rows, target)
    assert [r['candidate_id'] for r in training] == ['retained']
    assert {r['candidate_id'] for r in excluded} == {'same-source','same-family'}


def test_fresh_executor_verification_counts_action_contexts_and_retains_full_replay():
    from pathlib import Path
    source = Path(study.__file__).read_text()
    assert 'action_contexts=db.execute("SELECT COUNT(*) FROM action_contexts")' in source
    assert 'restore_archive(RESULTS, archive_record, restored)' in source
    assert '_audit_target(restored) == archived_audit' in source
    assert 'factorized.evaluate(scoring_root, outcomes,' in source
    assert 'Prespecified policy trajectories do not reproduce deterministically' in source


def test_countnegative_correctness_limit_does_not_copy_nanocobs_fields():
    from pathlib import Path
    from scripts import prepare_countnegative_v2_selector as prep
    assert '20x20' in prep.CORRECTNESS_LIMITATION and 'checksum0x1778de' in prep.CORRECTNESS_LIMITATION
    assert 'collisions' in prep.CORRECTNESS_LIMITATION
    source = Path(prep.__file__).read_text()
    assert 'scalar reference' not in source
    assert '8,215' not in source
    assert 'factorized.freeze(training, public' in source
    assert prep.workload.variable.effective_policy_budget(3,4) == 3


def test_sqlite_action_context_count_mismatch_is_rejected_behaviorally():
    import sqlite3
    tables = ('episodes','decisions','model_calls','retrievals','context_windows','action_contexts',
        'decision_rationales','rationale_measurements','rationale_selection_decisions','host_events')
    with sqlite3.connect(':memory:') as db:
        for table in tables:
            db.execute(f'CREATE TABLE {table} (total_tokens INTEGER)')
            db.execute(f'INSERT INTO {table} VALUES (NULL)')
        projection = dict(release_id='release', **{t:1 for t in tables})
        assert study._verify_observability_counts(db, projection)['action_contexts'] == 1
        with pytest.raises(ValueError, match='row counts differ'):
            study._verify_observability_counts(db, dict(projection, action_contexts=0))
        db.execute('DELETE FROM action_contexts')
        with pytest.raises(ValueError, match='row counts differ'):
            study._verify_observability_counts(db, projection)


def test_history_rederives_expanded_export_provenance_and_binds_exporter(monkeypatch):
    from scripts import prepare_countnegative_v2_selector as prep
    calls = []
    authenticate = prep.expanded_corpus.authenticate
    def spy(path):
        calls.append(path)
        return authenticate(path)
    monkeypatch.setattr(prep.expanded_corpus, 'authenticate', spy)
    assert len(prep._history()['rows']) == 156
    assert calls == [prep.HISTORY.parent]
    assert 'scripts/export_expanded_selection_corpus.py' in prep.SOURCES


def test_real_expanded_history_contexts_cover_every_benchmark_and_bind_actual_sources():
    from scripts import prepare_countnegative_v2_selector as prep
    corpus = prep._history()
    contexts, bindings = prep.history_contexts(corpus)
    assert {row['benchmark'] for row in corpus['rows']} <= set(contexts)
    assert len(contexts) == len(corpus['contexts']) + 3
    for source in corpus['new_source_contexts']:
        context = contexts[source['source_id']]
        assert context['context_id'] == source['context_id']
        assert context['workload_group'] + ':' + context['context_id'] == source['source_id']
        assert any(name.endswith('/inputs/context.json') and c.sha(prep.ROOT/name) == digest
                   for name,digest in bindings.items())
    assert sum(name.endswith('/inputs/context.json') for name in bindings) == 3
    assert sum(name.endswith('/inputs/context.json.sha256') for name in bindings) == 3


def test_historical_context_cannot_be_fabricated_or_reidentified(monkeypatch):
    import copy
    from scripts import prepare_countnegative_v2_selector as prep
    corpus = prep._history()
    changed = copy.deepcopy(corpus)
    changed['new_source_contexts'][0]['context_id'] = 'fabricated-context'
    with pytest.raises(ValueError, match='source-context identity differs'):
        prep.history_contexts(changed)
