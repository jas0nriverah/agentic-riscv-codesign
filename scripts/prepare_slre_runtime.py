"""Prepare SLRE with the bounded freestanding C runtime and unchanged memory limits."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import additional_workload, codesign as c


def prepare(reference, output):
    output = Path(output)
    plan = additional_workload.prepare(reference, output, 'slre', 6, '-Os')
    plan.pop('context_id')
    support = ROOT / 'hardware/embench_strings.c'
    memory = output / 'inputs/embench_memory.c'
    memory.write_text(memory.read_text() + '\n' + support.read_text())
    plan['inputs'][memory.name] = c.sha(memory)
    for relative in ('hardware/embench_strings.c', 'scripts/prepare_slre_runtime.py'):
        plan['source_bindings'][relative] = c.sha(ROOT / relative)
        snapshot = output / 'sources' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes((ROOT / relative).read_bytes())
    plan['runtime_support'] = 'C-locale newlib character table, strlen, strchr; no benchmark changes or relaxed memory/ISA limits.'
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.reference_root, args.root)
