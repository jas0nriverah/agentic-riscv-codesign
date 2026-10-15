#!/usr/bin/env python3
"""Authenticate and replay the published V8 application evaluation without fits.

Use Python 3.13 with requirements-research.txt and the proofs extra (also the
reports extra for figures). The frozen
scorer reads retained raw evidence directly; no synthesis, simulator, historical
local tool path, or raw-evidence restoration is needed. Output must be fresh.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import score_v8_applications as scorer

DEFAULT_ROOT = ROOT / 'results/2026-10-15-v8-application-transfer'
DEFAULT_OUTPUT = ROOT / 'generated/reproduction/v8'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def comparable(value):
    """Ignore only the top-level evaluation timestamp, preserving JSON types."""
    if not isinstance(value, dict) or 'evaluated_at_utc' not in value:
        raise ValueError('Timestamped evaluation object required')
    scorer.utc(value['evaluated_at_utc'])
    result = dict(value)
    del result['evaluated_at_utc']
    return json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)


def reproduce(root=DEFAULT_ROOT, output=DEFAULT_OUTPUT, *, skip_figures=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    reference_path = root / 'evaluation.json'
    if output.exists():
        raise ValueError('Reproduction output must be a fresh directory')
    if not reference_path.is_file():
        raise ValueError('Published V8 evaluation.json required')
    output.mkdir(parents=True)
    evaluation_path = output / 'evaluation.json'
    # The frozen scorer gates all fresh target reads on committed approval and
    # authenticates every frozen file, archive member, proof and raw cell count.
    scorer.score(root, evaluation_path)
    reproduced = json.loads(evaluation_path.read_text())
    reference = json.loads(reference_path.read_text())
    if comparable(reproduced) != comparable(reference):
        raise ValueError('Reproduced V8 evaluation differs from published reference; output retained for inspection')
    report = {
        'schema': 'isaforge-v8-application-reproduction-v1',
        'status': 'pass',
        'published_evaluation_sha256': sha(reference_path),
        'reproduced_evaluation_sha256': sha(evaluation_path),
        'point_freeze_sha256': reproduced['provenance']['point_freeze_sha256'],
        'scorer_sha256': sha(scorer.__file__),
        'reproduction_source_sha256': sha(__file__),
        'comparison': 'All JSON fields and types match except top-level evaluated_at_utc.',
        'new_estimator_fits': 0,
        'fresh_target_generation': False,
        'raw_evidence_restored': False,
        'figures_generated': not skip_figures,
    }
    if not skip_figures:
        from plot_v8_applications import run as plot
        plot(evaluation_path, output / 'figures', root=root)
    (output / 'reproduction.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--skip-figures', action='store_true')
    args = parser.parse_args()
    report = reproduce(args.root, args.output, skip_figures=args.skip_figures)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
