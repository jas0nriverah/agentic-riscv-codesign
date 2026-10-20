"""Replay October 20 selection research, automatic CRC32 and failed fit probes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge.selection_pilot import run
from reproduce_codesign import restore_archive
from reproduce_workload import main as replay_workload


def main():
    replay_workload(['replay', '--snapshot', str(ROOT/'results/2026-10-20-automatic-crc32'),
                     '--output', str(ROOT/'generated/reproduction/automatic-crc32-2026-10-20')])
    report = run(ROOT/'results/2026-10-20-ranking-pilot', verify=True)
    snapshot = ROOT/'results/2026-10-20-workload-feasibility'
    archives = [(snapshot, row['archive'], row['name']) for row in c.unseal(snapshot/'manifest.json')]
    for name in ('slre-runtime', 'slre-small'):
        folder = ROOT/f'results/2026-10-20-{name}-probe'
        archives.append((folder, c.unseal(folder/'archive-manifest.json'), name))
    total, seconds = 0, 0.0
    for folder, record, name in archives:
        output = ROOT/'generated/reproduction/research-fit-probes'/name
        restore_archive(folder, record, output)
        plan = c.unseal(output/'plan.json')
        c.require(c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == plan['context_id'], 'Plan changed')
        for source, expected in plan['source_bindings'].items():
            c.require(c.sha(ROOT/source) == expected, 'Probe source changed: '+source)
        for source, expected in plan['inputs'].items():
            c.require(c.sha(output/'inputs'/source) == expected, 'Probe input changed')
        commands = c.unseal(output/'commands.json')
        c.require(commands and commands[0]['failure'] is not None and commands[0]['returncode'] != 0,
                  'Expected preserved failed baseline compile')
        for command in commands:
            c.require(c.sha(output/command['log']) == command['log_sha256'], 'Probe log changed')
        total += len(commands)
        seconds += sum(row['elapsed_seconds'] for row in commands)
    print({'policy_seed_budget_outcomes': sum(len(r['curve']) for r in report['runs']),
           'failed_workload_build_contexts': len(archives), 'probe_native_commands': total,
           'probe_native_seconds': seconds, 'new_native_jobs': 0})


if __name__ == '__main__':
    main()
