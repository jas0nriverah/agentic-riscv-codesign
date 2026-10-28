#!/usr/bin/env python3
"""Generate the reviewed freestanding adapter from the pinned PULPino Sudoku."""
from __future__ import annotations
import argparse
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'benchmarks/pulpino-sudoku'
SOURCE = BASE / 'upstream/sudokusolver.c'
HEADER = BASE / 'upstream/sudokusolver.h'
OUTPUT = BASE / 'adapter.c'
PIN = BASE / 'SOURCE_PIN.json'

PREFIX = '''#include "upstream/sudokusolver.h"

int grid_init[SUDOKUSIZE * SUDOKUSIZE];
int grid_solved[SUDOKUSIZE * SUDOKUSIZE];
int solved[1];

int safe(int*, int, int, int);
void solve(int*, int, int, int*);
void sudokusolver(int*, int*);

'''

SUFFIX = '''

/* ISAForge ABI adapter: the measured region preserves the source's two solves. */
void initialise_benchmark(void) { }
void warm_caches(int iterations) { (void)iterations; }

int benchmark(void)
{
    for (int k = 0; k < 2; k++) {
        for (int i = 0; i < SUDOKUSIZE; i++)
            for (int j = 0; j < SUDOKUSIZE; j++)
                grid_solved[i * SUDOKUSIZE + j] = grid_init[i * SUDOKUSIZE + j];
        solved[0] = 0;
        sudokusolver(grid_solved, solved);
    }
    return solved[0];
}

int verify_benchmark(int result)
{
    if (result != 1 || solved[0] != 1) return 0;
    for (int i = 0; i < SUDOKUSIZE * SUDOKUSIZE; i++)
        if (grid_solved[i] != SUDOKUSOLVED[i]) return 0;
    return 1;
}
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def adapt(source: str) -> str:
    marker = '// start solver. (this function is used for profiling)\n'
    if source.count(marker) != 1:
        raise ValueError('Pinned source solver marker must occur exactly once')
    # Preserve the solver entry, constraint-checking and recursive search exactly.
    solver = source.split(marker, 1)[1]
    if not solver.startswith('void sudokusolver(') or solver.count('void solve(') != 1:
        raise ValueError('Pinned source solver tail does not match reviewed structure')
    # Preserve the puzzle as initialized by the upstream check() routine.
    start = '  // store sudoku to solve in grid_init\n'
    end = '  // loop two times. (cold/hot IC)\n'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('Pinned puzzle initialization markers changed')
    setup = source.split(start, 1)[1].split(end, 1)[0]
    if 'grid_init[8 * SUDOKUSIZE + 7] = 5;' not in setup or setup.count('grid_init[') != 39:
        # One indexed zeroing loop plus the fixed givens, bound to the source hash.
        raise ValueError('Upstream fixed puzzle initialization changed')
    # Put input setup inside benchmark(), so cycle timing includes the original
    # input construction, both result resets, and both solver invocations.
    body = textwrap.indent(setup, '  ')
    wrapper = '''
void initialise_benchmark(void) { }
void warm_caches(int iterations) { (void)iterations; }

int benchmark(void)
{
'''+body+'''    for (int k = 0; k < 2; k++) {
        for (int i = 0; i < SUDOKUSIZE; i++)
            for (int j = 0; j < SUDOKUSIZE; j++)
                grid_solved[i * SUDOKUSIZE + j] = grid_init[i * SUDOKUSIZE + j];
        solved[0] = 0;
        sudokusolver(grid_solved, solved);
    }
    return solved[0];
}

int verify_benchmark(int result)
{
    if (result != 1 || solved[0] != 1) return 0;
    for (int i = 0; i < SUDOKUSIZE * SUDOKUSIZE; i++)
        if (grid_solved[i] != SUDOKUSOLVED[i]) return 0;
    return 1;
}
'''
    return PREFIX + solver + wrapper


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = json.loads(PIN.read_text())
    files = record.get('files', {})
    if sha(SOURCE.read_bytes()) != files.get(str(SOURCE.relative_to(ROOT)), {}).get('sha256') or \
       sha(HEADER.read_bytes()) != files.get(str(HEADER.relative_to(ROOT)), {}).get('sha256'):
        raise SystemExit('Pinned PULPino source/header bytes differ')
    output = adapt(SOURCE.read_text()).encode()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != output or sha(output) != record.get('adapter_sha256'):
            raise SystemExit('Generated PULPino adapter differs from its pin')
        print(f'verified {OUTPUT.relative_to(ROOT)} sha256={sha(output)}')
    else:
        OUTPUT.write_bytes(output)
        record['adapter_sha256'] = sha(output)
        PIN.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        print(f'wrote {OUTPUT.relative_to(ROOT)} sha256={sha(output)}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
