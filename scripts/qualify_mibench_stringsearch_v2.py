"""Run fresh baseline-only mibench_stringsearch v2 qualification; no candidate dispatch."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import mibench_stringsearch_v2_workload as w
from scripts import qualify_nanocobs_v2 as driver

SOURCE = 'scripts/qualify_mibench_stringsearch_v2.py'
NATIVE = 'generated/mibench-stringsearch-v2-qualification-2026-10-28-r1'
OUTPUT = 'results/2026-10-28-mibench-stringsearch-v2-qualification-r1'
REFERENCE, PHASES = driver.REFERENCE, driver.PHASES
SOURCES = tuple(dict.fromkeys((SOURCE, driver.SOURCE, 'scripts/qualify_opportunity_sources.py',
    'scripts/reproduce_codesign.py', 'isaforge/observed_command.py', *w.GATE_SOURCES)))


def phase_command(phase, native, reference):
    w.c.require(phase in PHASES, 'Declared qualification phase required')
    argv = [sys.executable, '-m', 'isaforge.mibench_stringsearch_v2_workload', phase, '--root', str(native)]
    return argv + (['--reference-root', str(reference)] if phase == 'prepare' else [])


@contextmanager
def registration():
    previous = driver.w, driver.SOURCE, driver.SOURCES, driver.phase_command
    driver.w, driver.SOURCE, driver.SOURCES, driver.phase_command = w, SOURCE, SOURCES, phase_command
    try:
        yield
    finally:
        driver.w, driver.SOURCE, driver.SOURCES, driver.phase_command = previous


def qualify(output, native, reference):
    with registration():
        return driver.qualify(output, native, reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT / NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT / REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_root, args.reference_root)
    print(dict(status=result['status'], accepted=result['accepted'], target_candidate_attempts=0))
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())
