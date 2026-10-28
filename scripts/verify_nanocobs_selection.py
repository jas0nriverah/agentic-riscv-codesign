"""Verify the sealed nanocobs release, including action-context row counts.

The original executor's verification failure remains preserved. This separate
verifier retains its manifest/ledger/cost/SQLite/archive/full-native-audit and
policy-replay checks and fixes only the omitted action_contexts count.
It launches no native hardware evaluations or LLM calls. Policy replay may refit
its original paid-update GP models in temporary directories.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from scripts import execute_nanocobs_v2_selector as study

RESULTS, PREREG = study.RESULTS, study.PREREG
require = study.require


def projection_counts(db, release_id):
    """Explicit allowlist, including every table in the sealed export receipt."""
    try:
        return dict(release_id=release_id,
            episodes=db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0],
            decisions=db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],
            model_calls=db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0],
            retrievals=db.execute('SELECT COUNT(*) FROM retrievals').fetchone()[0],
            context_windows=db.execute('SELECT COUNT(*) FROM context_windows').fetchone()[0],
            action_contexts=db.execute('SELECT COUNT(*) FROM action_contexts').fetchone()[0],
            decision_rationales=db.execute('SELECT COUNT(*) FROM decision_rationales').fetchone()[0],
            rationale_measurements=db.execute('SELECT COUNT(*) FROM rationale_measurements').fetchone()[0],
            rationale_selection_decisions=db.execute(
                'SELECT COUNT(*) FROM rationale_selection_decisions').fetchone()[0],
            host_events=db.execute('SELECT COUNT(*) FROM host_events').fetchone()[0],
            missing_token_rows=db.execute(
                'SELECT COUNT(*) FROM model_calls WHERE total_tokens IS NULL').fetchone()[0])
    except sqlite3.DatabaseError as error:
        raise ValueError('SQLite observability table/schema is missing or invalid') from error


def check_projection_counts(db, projection):
    counts = projection_counts(db, projection['release_id'])
    expected = dict(projection, missing_token_rows=counts['missing_token_rows'])
    require(counts == expected,
            'SQLite observability row counts differ from the sealed export receipt')
    require(counts['missing_token_rows'] == counts['model_calls'],
            'Current Codex relay token limitation must remain explicit')
    return counts


def verify_sqlite_projection(database, observability):
    database = Path(database).resolve()
    require(c.sha(database) == observability['database_sha256'],
            'SQLite observability projection checksum differs')
    with sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True) as db:
        require(db.execute('PRAGMA quick_check').fetchone()[0] == 'ok',
                'SQLite observability projection fails integrity check')
        return check_projection_counts(db, observability['projection'])


def verify():
    result = c.unseal(RESULTS / "study-report.json")
    expected = c.unseal(RESULTS / "manifest.json")
    require(study._inventory(RESULTS) == expected, "Scored study manifest differs")
    agent = c.unseal(RESULTS / "agent-report.json")
    ledger = c.unseal(RESULTS / "agent/ledger.json")
    require(agent["ledger_sha256"] == c.sha(RESULTS / "agent/ledger.json") and
            ledger.get("decision_rationale") == agent.get("decision_rationale") and
            ledger.get("status") == agent.get("status") and
            ledger.get("selected_id") == agent.get("selected_id"),
            "Agent report differs from the host-authoritative decision ledger")
    costs = ledger.get("native_attempt_cost_accounting")
    require(isinstance(costs, dict) and
            agent.get("agent_attempt_costs") == costs.get("attempts") and
            agent.get("actual_agent_measurement_seconds") == costs.get("measurement_seconds") and
            agent.get("known_agent_measurement_seconds") == costs.get("known_measurement_seconds") and
            agent.get("agent_measurement_time_complete") == costs.get("measurement_time_complete") and
            agent.get("agent_outer_operation_seconds") == costs.get("outer_operation_seconds") and
            agent.get("known_agent_outer_operation_seconds") == costs.get("known_outer_operation_seconds"),
            "Agent cost report differs from durable host-ledger accounting")
    archive_record = c.unseal(RESULTS / "archive-manifest.json")
    require(study._inventory(RESULTS / "agent") ==
            c.unseal(RESULTS / "agent/manifest.json"),
            "Agent evidence package manifest differs")
    observability = c.unseal(RESULTS / 'agent/observability-export.json')
    counts = verify_sqlite_projection(RESULTS / 'agent/observability.sqlite', observability)
    with tempfile.TemporaryDirectory(prefix="isaforge-nanocobs-v2-verify-") as temp:
        restored = Path(temp) / "native"
        study.restore_archive(RESULTS, archive_record, restored)
        require(study._archive_inventory(restored) == {row["path"]: row["sha256"]
                for row in archive_record["files"]},
                "Archived raw native evidence differs from its manifest")
        prereg, release_record, _ = study._verify_release(dispatch=False,
            native_root=restored, receipt_path=RESULTS / "release.json")
        require(result["prelabel_commit"] == release_record["prelabel_commit"] and
                result["target_context_id"] == prereg["target_context_id"],
                "Scored result and frozen target disagree")
        archived_audit = c.unseal(RESULTS / "native-audit.json")
        require(study._audit_target(restored) == archived_audit,
                "Regenerated native audit differs from the preserved audit")
        outcomes = c.unseal(RESULTS / "outcomes.json")
        outer_times = c.unseal(RESULTS / "outer-times.json")
        require(archived_audit["outcomes"] == outcomes,
                "Scored outcomes differ from the restored raw-evidence audit")
        scoring_temp = Path(temp) / "scoring"
        scoring_temp.mkdir()
        scoring_root = scoring_temp / "selection"
        shutil.copytree(PREREG / "selection", scoring_root)
        replay = study.factorized.evaluate(scoring_root, outcomes,
            native_audit=archived_audit, outer_times=outer_times)
        replay = study._sanitize_scoring_reports(scoring_root, replay, outcomes, archived_audit)
        scored_replay = c.unseal(RESULTS / "factorized-policy-report.json")
        require(study._stable_policy_report(replay) == study._stable_policy_report(scored_replay),
                "Prespecified policy trajectories do not reproduce deterministically")
        for generated, saved in (
            (scoring_root / "report.json", RESULTS / "scoring/factorized-report.json"),
            (scoring_root / "controls11/report.json", RESULTS / "scoring/matched-controls-report.json"),
            (scoring_root / "controls11/model/report.json", RESULTS / "scoring/primary-model-report.json"),
        ):
            require(study._stable_policy_report(c.unseal(generated)) ==
                    study._stable_policy_report(c.unseal(saved)),
                    "Derived policy scorer report differs: " + saved.name)
    return dict(status='verified', action_contexts=counts['action_contexts'],
        candidate_outcomes=len(outcomes), full_archive_audit=True,
        deterministic_policy_replay=True, new_native_jobs=0,
        target_labels_acquired=0, original_executor_modified=False)


if __name__ == '__main__':
    print(verify())
