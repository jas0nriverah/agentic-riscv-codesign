"""The separate verifier includes action contexts without weakening its receipt."""
from __future__ import annotations

import sqlite3

import pytest

from isaforge import codesign as c
from scripts import verify_nanocobs_selection as verifier

TABLES = ('episodes', 'decisions', 'model_calls', 'retrievals', 'context_windows',
    'action_contexts', 'decision_rationales', 'rationale_measurements',
    'rationale_selection_decisions', 'host_events')


def database():
    db = sqlite3.connect(':memory:')
    for table in TABLES:
        db.execute(f'CREATE TABLE {table} (total_tokens INTEGER)')
        db.execute(f'INSERT INTO {table} VALUES (NULL)')
    return db


def projection():
    return dict(release_id='release', **{name:1 for name in TABLES})


def test_action_context_count_is_required_and_matches_sealed_receipt():
    with database() as db:
        assert verifier.check_projection_counts(db, projection())['action_contexts'] == 1
        missing = projection()
        del missing['action_contexts']
        with pytest.raises(ValueError, match='row counts differ'):
            verifier.check_projection_counts(db, missing)


def test_tampered_action_context_receipt_or_database_is_rejected():
    with database() as db:
        wrong = dict(projection(), action_contexts=2)
        with pytest.raises(ValueError, match='row counts differ'):
            verifier.check_projection_counts(db, wrong)
        db.execute('INSERT INTO action_contexts VALUES (NULL)')
        with pytest.raises(ValueError, match='row counts differ'):
            verifier.check_projection_counts(db, projection())


def test_missing_action_context_table_is_rejected():
    with database() as db:
        db.execute('DROP TABLE action_contexts')
        with pytest.raises(ValueError, match='schema is missing or invalid'):
            verifier.check_projection_counts(db, projection())


def test_sqlite_checksum_still_required(tmp_path):
    path = tmp_path / 'observability.sqlite'
    path.write_bytes(b'changed database')
    with pytest.raises(ValueError, match='checksum differs'):
        verifier.verify_sqlite_projection(path,
            dict(database_sha256='incorrect', projection=projection()))
