#!/usr/bin/env python3
"""Reproducible retrieval/trace engineering check on consumed SHA256 evidence.

Deterministic controls ignore retrieved context; identical outcomes validate
noninterference, not a retrieval or LLM performance benefit.
"""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_bounded_selector import run
from scripts.export_agent_observability import export
from isaforge import codesign as c
from isaforge.agent_memory import MODES


def evaluate(output):
    output = Path(output)
    if output.exists():
        raise ValueError('fresh output required')
    output.mkdir(parents=True)
    rows = []
    for mode in MODES:
        report = run(output/mode, targets=['sha256'], seeds=[0], caps=[64], memory_mode=mode)
        trace = export(output/mode, output/(mode+'.sqlite'))
        rows.append(dict(mode=mode, all_controls_match=report['all_controls_match'],
            trajectories=report['trajectories'], endpoints=report['endpoints'],
            llm_calls=report['llm_calls'], new_native_jobs=report['new_native_jobs'], **trace))
    result = dict(scope='Consumed-data software validation; no LLM or retrieval-quality comparison',
        results=rows, sources={p:c.sha(ROOT/p) for p in (
            'isaforge/agent_memory.py', 'isaforge/bounded_selector.py',
            'scripts/run_bounded_selector.py', 'scripts/export_agent_observability.py',
            'scripts/evaluate_agent_memory.py')})
    c.seal(output/'summary.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(evaluate(args.output))
