"""Persistent one-attempt accounting for fresh guarded workload contexts.

The ledger lives outside measurement artifacts so terminal status updates never
invalidate a successful measurement's original hash inventory. Interrupted
attempts remain unknown; resuming collection never silently retries them.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import time

from . import codesign as c, workload_experiment as w

SOURCE = 'isaforge/guarded_attempts.py'
SCHEMA = 'isaforge-guarded-attempt-v1'
PROTOCOL_SCHEMA = 'isaforge-guarded-measurement-protocol-v1'


class AttemptAlreadyCharged(ValueError):
    """A failed or interrupted attempt cannot be retried in the same context."""


def ledger_path(root, name):
    c.require(name == 'baseline' or (name.startswith('candidate_') and name[10:].isdigit()),
              'Invalid attempt name')
    return Path(root) / 'attempt-ledger' / (name + '.json')


def read_attempt(root, name):
    """Authenticate one ledger and its terminal artifacts without native tools."""
    root = Path(root).resolve()
    row = c.unseal(ledger_path(root, name))
    c.require(row.get('schema') == SCHEMA and row.get('name') == name,
              'Invalid attempt ledger identity')
    c.require(row.get('status') in ('started', 'success', 'failed', 'interrupted'),
              'Unknown attempt status')
    elapsed = row.get('elapsed_seconds')
    c.require((row['status'] == 'started' and elapsed is None) or
              (type(elapsed) in (float, int) and math.isfinite(elapsed) and elapsed >= 0),
              'Invalid attempt elapsed time')
    base = root / 'measurements' / name
    for relative, expected in row.get('artifacts', {}).items():
        path = (base / relative).resolve()
        c.require(not Path(relative).is_absolute() and path.is_relative_to(base.resolve()),
                  'Attempt artifact escapes measurement root')
        c.require(c.sha(path) == expected, 'Attempt artifact changed: ' + relative)
    if row['status'] == 'success':
        c.require(c.sha(base / 'measurement.json') == row['record_sha256'],
                  'Successful measurement differs from ledger')
    return row


def check_protocol(evaluator):
    """Require the frozen public pool and baseline to precede candidate queries."""
    root, plan = evaluator.root, evaluator.plan
    protocol = c.unseal(root / 'evaluation-protocol.json')
    c.require(protocol.get('schema') == PROTOCOL_SCHEMA and
              protocol.get('context_id') == plan['context_id'], 'Invalid evaluation protocol')
    discovery = w.verify_cache(root / 'discovery', 'discovery.json')
    c.require(protocol['discovery_sha256'] == c.sha(root / 'discovery/discovery.json') and
              protocol['baseline_sha256'] == c.sha(root / 'measurements/baseline/measurement.json'),
              'Frozen pool or baseline changed')
    names = [row['name'] for row in discovery['pool']]
    c.require(protocol['pool_names'] == names and len(set(names)) == len(names) and
              protocol['maximum_candidate_attempts'] == len(names) and protocol['attempts_per_candidate'] == 1,
              'Candidate query contract changed')
    before = protocol['baseline_receipts']
    c.require(c.digest(evaluator.runner.receipts[:len(before)]) == c.digest(before),
              'Native baseline receipt prefix changed')
    c.require(protocol['source_bindings'] == plan['source_bindings'], 'Protocol source bindings changed')
    return protocol


def freeze_pool(evaluator, *, scope='engineering-validation'):
    """Freeze after checked baseline qualification and before any candidate attempt."""
    c.require(scope in ('engineering-validation', 'dataset-expansion'), 'Unknown measurement scope')
    root = evaluator.root
    c.require(not (root / 'evaluation-protocol.json').exists(), 'Preserve existing evaluation protocol')
    c.require(not list((root / 'attempt-ledger').glob('candidate_*.json')) and
              not list((root / 'measurements').glob('candidate_*')), 'Candidate work preceded freeze')
    discovery = evaluator.discover()
    evaluator.measure('baseline')
    # This read-only validator re-extracts the guarded pool and recounts raw
    # baseline controls, resources and timing before its observations are frozen.
    from .guarded_workload import baseline_public
    baseline_public(root)
    names = [row['name'] for row in discovery['pool']]
    result = dict(schema=PROTOCOL_SCHEMA, context_id=evaluator.plan['context_id'], scope=scope,
        discovery_sha256=c.sha(root / 'discovery/discovery.json'),
        baseline_sha256=c.sha(root / 'measurements/baseline/measurement.json'),
        pool_names=names, maximum_candidate_attempts=len(names), attempts_per_candidate=1,
        clock_mhz=12.0, area_caps=[32, 64, 128], route_seeds=[1, 2, 3],
        baseline_receipts=list(evaluator.runner.receipts),
        source_bindings=dict(evaluator.plan['source_bindings']),
        chronology='Commit and push this protocol and its source bindings before candidate measurements.',
        interpretation='Measured dataset/engineering validation only; no held-out learned-selection claim without a separately frozen prediction protocol.')
    c.seal(root / 'evaluation-protocol.json', result)
    return result


class OneAttemptMixin:
    """Wrap the existing processor evaluator without modifying frozen sources."""

    def measure(self, name):
        discovery = self.discover()
        names = [row['name'] for row in discovery['pool']]
        c.require(name == 'baseline' or name in names, 'Candidate outside guarded pool')
        if name != 'baseline':
            check_protocol(self)
        base = self.root / 'measurements' / name
        state = ledger_path(self.root, name)
        identity = c.digest([self.plan['context_id'], c.sha(self.root / 'discovery/discovery.json'), name])
        if state.exists():
            prior = read_attempt(self.root, name)
            c.require(prior['context_id'] == self.plan['context_id'] and prior['evaluation_id'] == identity,
                      'Attempt context changed')
            if prior['status'] != 'success':
                raise AttemptAlreadyCharged(f'{name}: {prior["status"]} attempt already charged; use a new declared context, never an implicit retry')
            return super().measure(name)
        c.require(not base.exists(), 'Unledgered measurement artifacts exist; preserve and investigate')
        if name != 'baseline':
            # Baseline cost is setup, never included in this candidate's charge.
            self.measure('baseline')
            charged = list((self.root / 'attempt-ledger').glob('candidate_*.json'))
            c.require(len(charged) < len(names), 'Candidate query budget exhausted')
        self.runner.check()
        row = dict(schema=SCHEMA, context_id=self.plan['context_id'], name=name,
            evaluation_id=identity, started_at_utc=datetime.now(timezone.utc).isoformat(),
            receipt_start=len(self.runner.receipts), receipt_prefix_sha256=c.digest(self.runner.receipts),
            status='started', elapsed_seconds=None, artifacts={})
        state.parent.mkdir(parents=True, exist_ok=True)
        c.seal(state, row)
        began = time.monotonic()
        try:
            result = super().measure(name)
        except BaseException as error:
            row.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed',
                       error=repr(error), elapsed_seconds=time.monotonic() - began,
                       receipt_end=len(self.runner.receipts), artifacts=w.artifact_hashes(base))
            c.seal(state, row)
            raise
        row.update(status='success', elapsed_seconds=time.monotonic() - began,
                   receipt_end=len(self.runner.receipts), artifacts=w.artifact_hashes(base),
                   record_sha256=c.sha(base / 'measurement.json'))
        c.seal(state, row)
        return result

    def collect(self):
        discovery = self.discover()
        check_protocol(self)
        baseline = self.measure('baseline')
        records, attempts = [], []
        stopped = False
        for candidate in discovery['pool']:
            name = candidate['name']
            state = ledger_path(self.root, name)
            if state.exists():
                prior = read_attempt(self.root, name)
                if prior['status'] in ('started', 'interrupted'):
                    attempts.append(prior)
                    stopped = True
                    break
                if prior['status'] == 'failed':
                    attempts.append(prior)
                    continue
            try:
                records.append(self.measure(name))
            except Exception:
                # Only a terminal, durably charged failure may be skipped.
                # Missing evidence/source failures must not silently disappear.
                if not state.exists():
                    raise
                failure = read_attempt(self.root, name)
                if failure['status'] != 'failed':
                    raise
            attempts.append(read_attempt(self.root, name))
        report = dict(schema='isaforge-guarded-collection-v1', context_id=self.plan['context_id'],
            workload=self.plan['workload'], baseline=baseline, measurements=records,
            candidate_pool=discovery['pool'], attempts=attempts,
            collection_complete=not stopped and len(attempts) == len(discovery['pool']),
            failed_attempts=sum(row['status'] == 'failed' for row in attempts),
            unknown_attempts=sum(row['status'] in ('started', 'interrupted') for row in attempts),
            unattempted_candidates=[p['name'] for p in discovery['pool'] if p['name'] not in {r['name'] for r in attempts}],
            charged_candidate_attempts=len(attempts),
            known_candidate_wall_seconds=sum(row['elapsed_seconds'] for row in attempts if row['elapsed_seconds'] is not None),
            elapsed_cost_complete=all(row['elapsed_seconds'] is not None for row in attempts),
            native_commands=len(self.runner.receipts),
            native_seconds=sum(row['elapsed_seconds'] for row in self.runner.receipts),
            memory_partition=self.plan['memory_partition'],
            limitations=['Single-instruction measurements on recorded inputs, not combined-set performance.',
                'RTL simulation and synthesis/routing, not physical-board measurements.',
                'Failures remain charged and unknown outcomes are not infeasible labels.',
                'Ledger wall-time includes validation overhead; native command time overlaps it.',
                'Engineering/dataset collection alone establishes no ML generalization or selection advantage.'])
        path = self.root / 'collection-report.json'
        if path.exists():
            c.require(c.unseal(path) == report, 'Preserve prior collection report; interrupted contexts need a new declared run')
        else:
            c.seal(path, report)
        return report
