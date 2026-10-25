"""One original-input lift qualification; shared runner, zero candidate labels."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c,lift_workload as w
from scripts import qualify_tacle_bitcount as runner
from scripts.blind_campaign import _manifest

SOURCE = 'scripts/qualify_tacle_lift.py'
REFERENCE = runner.REFERENCE
NATIVE = 'generated/tacle-lift-2026-10-25'
OUTPUT = 'results/2026-10-25-lift-qualification'
HISTORY = 'results/2026-10-25-thirteen-source-corpus/corpus.json'
PRESERVED_HISTORY = 'results/2026-10-22-twelve-source-corpus/corpus.json'
PHASES = runner.PHASES
SOURCES = tuple(dict.fromkeys((SOURCE,runner.SOURCE,'scripts/blind_campaign.py',
    'scripts/reproduce_guarded_sha256.py',PRESERVED_HISTORY,
    'scripts/qualify_opportunity_sources.py','scripts/reproduce_codesign.py','isaforge/observed_command.py',*w.GATE_SOURCES)))


def phase_command(phase,native,reference):
    c.require(phase in PHASES,'Declared qualification phase required')
    argv = [sys.executable,'-m','isaforge.lift_workload',phase,'--root',str(native)]
    if phase == 'prepare':
        argv += ['--reference-root',str(reference)]
    return argv


@contextmanager
def registration():
    replacements = dict(ROOT=ROOT,SOURCE=SOURCE,REFERENCE=REFERENCE,NATIVE=NATIVE,OUTPUT=OUTPUT,
        HISTORY=HISTORY,PHASES=PHASES,SOURCES=SOURCES,w=w,phase_command=phase_command)
    previous = {name:getattr(runner,name) for name in replacements}
    try:
        for name,value in replacements.items():
            setattr(runner,name,value)
        yield
    finally:
        for name,value in previous.items():
            setattr(runner,name,value)


def validate_history():
    # This path is deliberately unavailable until the serialized g723 campaign
    # has twelve terminal outcomes and its exact complete corpus is exported.
    # Never substitute the older99-label corpus to let qualification start early.
    _manifest(ROOT/Path(HISTORY).parent)
    _manifest(ROOT/Path(PRESERVED_HISTORY).parent)
    corpus,old = c.unseal(ROOT/HISTORY),c.unseal(ROOT/PRESERVED_HISTORY)
    attempts = corpus['rows']+corpus['failed_attempts']
    c.require(corpus['successful_labels'] == len(corpus['rows']) and
        corpus['total_candidate_attempts'] == len(attempts) == len({r['candidate_id'] for r in attempts}) == 114 and
        len(corpus['independent_workload_groups']) == 13 and len(corpus['contexts']) == 14 and
        'tacle-g723-enc' in corpus['independent_workload_groups'] and w.GROUP not in corpus['independent_workload_groups'],
        'Exact completed thirteen-source114-attempt corpus required before lift qualification')
    c.require(old['successful_labels'] == len(old['rows']) == 99 and len(old['failed_attempts']) == 3 and
        corpus['rows'][:99] == old['rows'] and corpus['failed_attempts'][:3] == old['failed_attempts'] and
        corpus['preserved_original_rows_digest'] == c.digest(old['rows']) and
        corpus['preserved_original_failed_attempts_digest'] == c.digest(old['failed_attempts']),
        'Preserve the original99 successful and3 failed rows exactly')
    return corpus


def qualify(output,native,reference):
    validate_history()
    with registration():
        return runner.qualify(output,native,reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/OUTPUT)
    parser.add_argument('--native-root',type=Path,default=ROOT/NATIVE)
    parser.add_argument('--reference-root',type=Path,default=ROOT/REFERENCE)
    args = parser.parse_args(argv)
    result = qualify(args.output,args.native_root,args.reference_root)
    print({key:result[key] for key in ('status','accepted','target_candidate_attempts')})
    return 0 if result['status'] == 'accepted' else 1


if __name__ == '__main__':
    raise SystemExit(main())
