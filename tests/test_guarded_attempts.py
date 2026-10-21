"""Attempt/query accounting survives failures, cache use and interruptions."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from isaforge import codesign as c, guarded_attempts as a, workload_experiment as w


class FakeNative:
    def __init__(self, root):
        self.root = root
        self.plan = dict(context_id='test-context', source_bindings={}, memory_partition={})
        self.runner = SimpleNamespace(receipts=[], check=lambda: None)
        self.calls = []
        self.fail = {}
        self.cache_hits = 0
        root.mkdir()
        (root / 'discovery').mkdir()
        c.seal(root / 'discovery/discovery.json', dict(pool=[dict(name='candidate_00'), dict(name='candidate_01')], artifacts={}))
        self.plan['workload'] = 'fixture'

    def discover(self):
        return w.verify_cache(self.root / 'discovery', 'discovery.json')

    def measure(self, name):
        base = self.root / 'measurements' / name
        if (base / 'measurement.json').exists():
            self.cache_hits += 1
            return w.verify_cache(base, 'measurement.json')
        self.calls.append(name)
        attempt = base / 'attempt-000'
        attempt.mkdir(parents=True)
        if name in self.fail:
            error = self.fail[name]
            c.write(attempt / 'failure.json', dict(error=repr(error), elapsed_seconds=0.1))
            raise error
        record = dict(name=name, elapsed_seconds=0.1, artifacts=w.artifact_hashes(base))
        c.seal(base / 'measurement.json', record)
        return record


class Evaluator(a.OneAttemptMixin, FakeNative):
    pass


def prepared(tmp_path):
    e = Evaluator(tmp_path / 'native')
    e.measure('baseline')
    c.seal(e.root / 'evaluation-protocol.json', dict(schema=a.PROTOCOL_SCHEMA,
        context_id=e.plan['context_id'], discovery_sha256=c.sha(e.root / 'discovery/discovery.json'),
        baseline_sha256=c.sha(e.root / 'measurements/baseline/measurement.json'),
        pool_names=['candidate_00', 'candidate_01'], maximum_candidate_attempts=2,
        attempts_per_candidate=1, baseline_receipts=[], source_bindings={}))
    return e


def test_candidate_requires_freeze_before_creating_native_attempt(tmp_path):
    e = Evaluator(tmp_path / 'native')
    with pytest.raises((ValueError, FileNotFoundError)):
        e.measure('candidate_00')
    assert e.calls == []
    assert not (e.root / 'attempt-ledger').exists()


def test_failure_is_charged_and_remaining_candidate_executes_without_retry(tmp_path):
    e = prepared(tmp_path)
    e.fail['candidate_00'] = ValueError('Less than 2 GiB free')
    report = e.collect()
    assert report['collection_complete']
    assert report['charged_candidate_attempts'] == 2 and report['failed_attempts'] == 1
    assert [r['name'] for r in report['measurements']] == ['candidate_01']
    assert e.calls == ['baseline', 'candidate_00', 'candidate_01']
    assert report['known_candidate_wall_seconds'] > 0 and report['elapsed_cost_complete']
    assert e.collect() == report
    assert e.calls == ['baseline', 'candidate_00', 'candidate_01']
    with pytest.raises(a.AttemptAlreadyCharged):
        e.measure('candidate_00')
    assert not list(e.root.rglob('attempt-001'))


def test_success_cache_authenticates_record_and_does_not_add_charge(tmp_path):
    e = prepared(tmp_path)
    record = e.measure('candidate_00')
    state = a.ledger_path(e.root, 'candidate_00').read_bytes()
    assert e.measure('candidate_00') == record
    assert a.ledger_path(e.root, 'candidate_00').read_bytes() == state
    assert e.calls == ['baseline', 'candidate_00']
    path = e.root / 'measurements/candidate_00/measurement.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='artifact changed|differs from ledger'):
        e.measure('candidate_00')


def test_caught_interruption_is_retained_and_collect_stops(tmp_path):
    e = prepared(tmp_path)
    e.fail['candidate_00'] = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        e.measure('candidate_00')
    state = a.read_attempt(e.root, 'candidate_00')
    assert state['status'] == 'interrupted' and state['elapsed_seconds'] >= 0
    report = e.collect()
    assert not report['collection_complete'] and report['unknown_attempts'] == 1
    assert report['unattempted_candidates'] == ['candidate_01']
    assert e.calls == ['baseline', 'candidate_00']


def test_hard_interruption_has_unknown_time_and_is_never_retried(tmp_path):
    e = prepared(tmp_path)
    e.fail['candidate_00'] = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        e.measure('candidate_00')
    path = a.ledger_path(e.root, 'candidate_00')
    row = c.unseal(path)
    row.update(status='started', elapsed_seconds=None, artifacts={})
    row.pop('receipt_end'); row.pop('error')
    c.seal(path, row)
    report = e.collect()
    assert report['charged_candidate_attempts'] == 1 and not report['elapsed_cost_complete']
    assert report['known_candidate_wall_seconds'] == 0  # known subtotal, not actual free cost
    assert report['attempts'][0]['elapsed_seconds'] is None
    with pytest.raises(a.AttemptAlreadyCharged):
        e.measure('candidate_00')
    assert not list(e.root.rglob('attempt-001'))


def test_orphaned_artifacts_are_not_silently_retried(tmp_path):
    e = prepared(tmp_path)
    (e.root / 'measurements/candidate_00/attempt-000').mkdir(parents=True)
    with pytest.raises(ValueError, match='Unledgered'):
        e.measure('candidate_00')
    assert e.calls == ['baseline']


@pytest.mark.parametrize('field,value', [('discovery_sha256','changed'), ('baseline_sha256','changed'),
    ('pool_names',['candidate_00']), ('maximum_candidate_attempts',3), ('attempts_per_candidate',2),
    ('source_bindings',{'changed':'source'}), ('baseline_receipts',[{'fake':'command'}])])
def test_changed_frozen_contract_stops_before_native_work(tmp_path, field, value):
    e = prepared(tmp_path)
    path = e.root / 'evaluation-protocol.json'
    protocol = c.unseal(path); protocol[field] = value; c.seal(path, protocol)
    with pytest.raises(ValueError):
        e.measure('candidate_00')
    assert e.calls == ['baseline']


def test_source_validation_error_is_not_swallowed_as_a_charged_attempt(tmp_path):
    e = prepared(tmp_path)
    def broken():
        raise ValueError('Source changed')
    e.runner.check = broken
    with pytest.raises(ValueError, match='Source changed'):
        e.collect()
    assert not a.ledger_path(e.root, 'candidate_00').exists()


def test_attempt_artifact_escape_is_rejected(tmp_path):
    e = prepared(tmp_path)
    e.measure('candidate_00')
    path = a.ledger_path(e.root, 'candidate_00')
    state = c.unseal(path); state['artifacts'] = {'../../../outside':'invalid'}
    c.seal(path, state)
    with pytest.raises(ValueError, match='escapes'):
        a.read_attempt(e.root, 'candidate_00')
