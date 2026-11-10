#!/usr/bin/env python3
"""Replay both independent coverage audits without altering frozen receipts."""
from __future__ import annotations
import json
from pathlib import Path
import audit_targeted_coverage as first
import audit_budget_preserving_coverage as second

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = {ROOT/'results/targeted-coverage/audit.json',
            ROOT/'results/budget-preserving-coverage/audit.json'}


def verify_receipt(path, body):
    path = Path(path).resolve()
    if path not in RECEIPTS:
        raise ValueError('Unexpected audit write destination: ' + str(path))
    expected = json.loads(path.read_text())
    actual = dict(body)
    # Only the time of this read-only re-execution differs from the frozen run.
    expected.pop('audited_at_utc', None)
    actual.pop('audited_at_utc', None)
    if actual != expected:
        raise ValueError('Independent audit differs from frozen receipt: ' + str(path))


def main():
    first.write = verify_receipt
    second.write = verify_receipt
    results = {'targeted_coverage': first.final_audit(),
               'budget_preserving_coverage': second.final_audit()}
    print(json.dumps({'status':'pass','receipts_modified':False,'results':results},indent=2))


if __name__ == '__main__':
    main()
