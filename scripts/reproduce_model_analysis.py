"""Authenticate and recompute frozen diagnostics without native measurements.

The frozen analyzer compares a Python tuple with its JSON list on --verify.
Preserve that source and use canonical JSON comparison here; do not weaken or
drop scientific fields. Only the explicitly measured analysis wall time varies.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c
from scripts import analyze_speedup_model as analysis


def canonical_results(value):
    return c.digest(analysis.stable(value))


def manifest(root):
    for name,expected in c.unseal(root/'manifest.json').items():
        c.require(c.sha(root/name)==expected,'Snapshot artifact changed: '+str(root/name))


def replay(root,calibration,pilot):
    root,calibration,pilot=map(Path,(root,calibration,pilot))
    manifest(root); manifest(calibration)
    measured,_=analysis.authenticated_calibration(calibration)
    c.require(measured==c.unseal(root/'calibration.json'),'Analysis calibration differs from raw evidence')
    scratch=c.ROOT/'generated/reproduction'; scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='model-analysis-',dir=scratch) as name:
        destination=Path(name)
        for path in root.rglob('*'):
            rel=path.relative_to(root)
            if not path.is_file() or rel.parts[0]=='sources' or path.name in (
                'report.json','report.json.sha256','manifest.json','manifest.json.sha256','README.md'):
                continue
            target=destination/rel; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
        recomputed=analysis.analyze(destination,pilot)
        c.require(canonical_results(recomputed)==canonical_results(c.unseal(root/'report.json')),
                  'Scientific results differ on replay')
    return dict(calibration_cases=measured['cases'],calibration_native_commands_recorded=measured['native_commands'],
                calibration_command_seconds_recorded=measured['native_command_seconds'],
                existing_policy_outcomes=recomputed['original_pilot_outcomes'],
                added_latency_policy_outcomes=recomputed['new_latency_policy_outcomes'],
                new_native_commands=0,scientific_results_match=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=c.ROOT/'results/2026-10-20-model-analysis')
    p.add_argument('--calibration',type=Path,default=c.ROOT/'results/2026-10-20-latency-calibration')
    p.add_argument('--pilot',type=Path,default=c.ROOT/'results/2026-10-20-ranking-pilot')
    args=p.parse_args(); print(replay(args.root,args.calibration,args.pilot))


if __name__=='__main__': main()
