#!/usr/bin/env python3
"""Export a same-charged-attempt comparison for the Codex chat pilot.

The sealed interactive run reports controls at its configured allowance. This
supplement additionally aligns archived controls to the chat agent's actual
charged attempts when it stops early. It never launches measurements.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from scripts.run_bounded_selector import TARGETS, load_case

RUN = ROOT/'results/2026-10-27-codex-chat-agent-edn-b64-s0'
OUT = ROOT/'results/2026-10-27-codex-chat-agent-edn-b64-s0-control-comparison'
POLICIES = ('frequency', 'merit', 'random', 'raw_regression', 'ranking',
            'latency_cost_heuristic', 'hybrid_gp_adapt')
FIELDS = ('policy', 'target', 'area_cap_lut4', 'seed', 'charged_attempts',
          'valid_measurements', 'selected_id', 'best_speedup',
          'regret_to_measured_pool_oracle', 'reference_kind')


def main():
    c.require(RUN.is_dir(), 'Frozen Codex chat run is missing')
    c.require(not OUT.exists(), 'Preserve prior comparison export')
    report = c.unseal(RUN/'report.json')
    c.require(report['status'] == 'finalized' and report['new_native_jobs'] == 0,
              'Expected completed replay with no new jobs')
    case = load_case(ROOT/TARGETS[report['target']])
    budget = report['charged_attempts']
    oracle = report['measured_pool_oracle']['speedup']
    rows = [dict(policy='current_codex_chat_llm', target=report['target'],
        area_cap_lut4=report['area_cap_lut4'], seed=report['seed'],
        charged_attempts=budget,
        valid_measurements=sum(1 for event in report['decisions']
                               if event['tool'] == 'measure' and event['status'] == 'ok'),
        selected_id=report['selected_id'], best_speedup=report['selected_speedup'],
        regret_to_measured_pool_oracle=oracle-report['selected_speedup'],
        reference_kind='consumed measured-pool oracle; post-selection reference')]
    for policy in POLICIES:
        match = next(row for row in case['report']['runs']
            if row['policy'] == policy and row['seed'] == report['seed'] and
            row['area_delta_lut4_cap'] == report['area_cap_lut4'])
        points = [point for point in match['curve'] if point['budget'] <= budget]
        point = points[-1] if points else dict(budget=0, selected_id=None, best_speedup=1.0)
        c.require(point['budget'] == budget, 'Control trajectory lacks the chat charged-attempt endpoint')
        rows.append(dict(policy=policy, target=report['target'],
            area_cap_lut4=report['area_cap_lut4'], seed=report['seed'],
            charged_attempts=point['budget'],
            valid_measurements=len(point.get('measured_ids', [])),
            selected_id=point['selected_id'], best_speedup=point['best_speedup'],
            regret_to_measured_pool_oracle=oracle-point['best_speedup'],
            reference_kind='consumed measured-pool oracle; post-selection reference'))
    OUT.mkdir(parents=True)
    with (OUT/'comparisons.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    inputs={name:hashlib.sha256((RUN/name).read_bytes()).hexdigest()
            for name in ('protocol.json','ledger.json','report.json')}
    inputs['frozen_control_protocol']=hashlib.sha256((ROOT/TARGETS[report['target']]/'protocol.json').read_bytes()).hexdigest()
    payload=dict(schema='isaforge-codex-chat-equal-charge-comparison-v1',
        scope='Retrospective consumed-data comparison at the chat episode actual charged-attempt count; no hardware runs.',
        target=report['target'], area_cap_lut4=report['area_cap_lut4'], seed=report['seed'],
        configured_allowance=report['budget'], actual_charged_attempts=budget,
        oracle_speedup=oracle, rows=len(rows), inputs=inputs,
        csv_sha256=hashlib.sha256((OUT/'comparisons.csv').read_bytes()).hexdigest(),
        new_native_jobs=0, uncertainty_calibrated=False)
    (OUT/'manifest.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print(json.dumps(payload,indent=2))


if __name__ == '__main__':
    main()
