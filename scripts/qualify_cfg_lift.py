"""One distinct Lift CFG-coverage qualification; original rejection stays final."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, cfg_lift_workload as w
from scripts import qualify_tacle_bitcount as runner
from scripts.blind_campaign import _manifest

SOURCE = 'scripts/qualify_cfg_lift.py'
REFERENCE = runner.REFERENCE
NATIVE = 'generated/tacle-lift-cfg-2026-10-25'
OUTPUT = 'results/2026-10-25-lift-cfg-qualification'
HISTORY = 'results/2026-10-25-thirteen-source-corpus/corpus.json'
PRESERVED_HISTORY = 'results/2026-10-22-twelve-source-corpus/corpus.json'
ORIGINAL_REJECTION = w.ORIGINAL_REJECTION
REJECTION_FILES = tuple(ORIGINAL_REJECTION+'/'+name for name in ('protocol.json', 'qualification.json', 'manifest.json'))
PHASES = runner.PHASES
SOURCES = tuple(dict.fromkeys((SOURCE, runner.SOURCE, 'scripts/qualify_tacle_lift.py',
    'scripts/blind_campaign.py', 'scripts/reproduce_guarded_sha256.py', PRESERVED_HISTORY,
    *REJECTION_FILES, 'scripts/qualify_opportunity_sources.py', 'scripts/reproduce_codesign.py',
    'isaforge/observed_command.py', *w.GATE_SOURCES)))


def phase_command(phase, native, reference):
    c.require(phase in PHASES, 'Declared qualification phase required')
    argv = [sys.executable, '-m', 'isaforge.cfg_lift_workload', phase, '--root', str(native)]
    if phase == 'prepare':
        argv += ['--reference-root', str(reference)]
    return argv


@contextmanager
def registration():
    replacements = dict(ROOT=ROOT, SOURCE=SOURCE, REFERENCE=REFERENCE, NATIVE=NATIVE, OUTPUT=OUTPUT,
        HISTORY=HISTORY, PHASES=PHASES, SOURCES=SOURCES, w=w, phase_command=phase_command)
    previous = {name:getattr(runner,name) for name in replacements}
    try:
        for name,value in replacements.items():
            setattr(runner,name,value)
        yield
    finally:
        for name,value in previous.items():
            setattr(runner,name,value)


def validate_history():
    _manifest(ROOT/Path(HISTORY).parent)
    _manifest(ROOT/Path(PRESERVED_HISTORY).parent)
    corpus, old = c.unseal(ROOT/HISTORY), c.unseal(ROOT/PRESERVED_HISTORY)
    attempts = corpus['rows']+corpus['failed_attempts']
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 110 and
        len(corpus['failed_attempts']) == 4 and corpus['total_candidate_attempts'] == len(attempts) ==
        len({row['candidate_id'] for row in attempts}) == 114 and
        len(corpus['independent_workload_groups']) == 13 and len(corpus['contexts']) == 14 and
        'tacle-g723-enc' in corpus['independent_workload_groups'] and
        w.GROUP not in corpus['independent_workload_groups'],
        'Exact completed thirteen-source110-label/four-failure/114-attempt corpus required')
    c.require(old['successful_labels'] == len(old['rows']) == 99 and len(old['failed_attempts']) == 3 and
        corpus['rows'][:99] == old['rows'] and corpus['failed_attempts'][:3] == old['failed_attempts'] and
        corpus['preserved_original_rows_digest'] == c.digest(old['rows']) and
        corpus['preserved_original_failed_attempts_digest'] == c.digest(old['failed_attempts']),
        'Preserve the original99 successful and3 failed rows exactly')
    return corpus


def validate_original_rejection():
    root = ROOT/ORIGINAL_REJECTION
    _manifest(root)
    protocol, result = c.unseal(root/'protocol.json'), c.unseal(root/'qualification.json')
    records = result['records']
    c.require(protocol['schema'] == w.lift.PROTOCOL['schema']+'-qualification' and
        all(protocol[key] == value for key,value in w.lift.PROTOCOL.items() if key != 'schema') and
        result['protocol_sha256'] == c.sha(root/'protocol.json') and
        result['status'] == 'rejected' and result['accepted'] == {} and
        type(result['target_candidate_attempts']) is int and result['target_candidate_attempts'] == 0 and
        len(records) == 1 and records[0]['workload'] == w.WORKLOAD and records[0]['family'] == w.GROUP and
        records[0]['status'] == 'rejected' and records[0]['failed_phase'] == 'discover' and
        [row['phase'] for row in records[0]['commands']] == ['prepare', 'discover'] and
        [row['record']['returncode'] for row in records[0]['commands']] == [0, 1],
        'Preserved original zero-label Lift discovery rejection required; never retry or relabel it')
    return dict(path=ORIGINAL_REJECTION, status='rejected', target_candidate_attempts=0,
        manifest_sha256=c.sha(root/'manifest.json'), protocol_sha256=c.sha(root/'protocol.json'),
        qualification_sha256=c.sha(root/'qualification.json'), original_rejection_remains_final=True)


def qualify(output, native, reference):
    validate_history()
    validate_original_rejection()
    with registration():
        return runner.qualify(output, native, reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/OUTPUT)
    parser.add_argument('--native-root', type=Path, default=ROOT/NATIVE)
    parser.add_argument('--reference-root', type=Path, default=ROOT/REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output, args.native_root, args.reference_root)
    print({key:result[key] for key in ('status', 'accepted', 'target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())
