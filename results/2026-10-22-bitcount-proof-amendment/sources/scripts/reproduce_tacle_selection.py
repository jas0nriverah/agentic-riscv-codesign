"""Pre-label JSON representation amendment for frozen acquisition proofs.

The frozen controller compares in-memory tuples to JSON arrays. Normalize only
the proof's two-number score at that boundary; every serialized byte/value,
model, acquisition, paid outcome and native timer remains exact. This adapter
is itself committed before candidate measurements, with a label-free witness.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from scripts import tacle_selection_campaign as frozen

SOURCE = 'scripts/reproduce_tacle_selection.py'
CONTRACT = 'isaforge-tacle-proof-json-amendment-v1'
AMENDMENT = ROOT/'results/2026-10-22-bitcount-proof-amendment'


def canonical_proof(proof):
    """Change tuple->JSON list for exactly event.score, preserving its content."""
    c.require(isinstance(proof,dict) and isinstance(proof.get('event'),dict), 'Acquisition proof required')
    normalized = copy.deepcopy(proof)
    score = normalized['event'].get('score')
    c.require(isinstance(score,(tuple,list)) and len(score) == 2 and
        all(type(value) in (int,float) for value in score), 'Exactly two numeric acquisition-score fields required')
    normalized['event']['score'] = list(score)
    c.require(c.digest(normalized) == c.digest(proof), 'Every serialized proof field/value must remain exact')
    return normalized


@contextmanager
def normalized_proofs():
    """Scoped post-prediction representation fix; no frozen file is edited."""
    original = frozen.count_search
    def adapted(case,provider,*,policy,seed,area_cap,on_acquire=None):
        def acquire(proof):
            if on_acquire is not None:
                on_acquire(canonical_proof(proof))
        result = original(case,provider,policy=policy,seed=seed,area_cap=area_cap,on_acquire=acquire)
        result['acquisition_proofs'] = [canonical_proof(proof) for proof in result['acquisition_proofs']]
        return result
    frozen.count_search = adapted
    try:
        yield
    finally:
        frozen.count_search = original


def prepare(prereg,output):
    prereg,output = Path(prereg).resolve(),Path(output).resolve()
    frozen.fresh(output,prereg)
    c.require(output.is_relative_to(ROOT), 'Repository-local amendment required')
    cohort,group,target,case = frozen.authenticate(prereg)
    native = Path(target['original_root'])
    frozen.prior._zero(native)
    captured = []
    class BeforeAnyOutcome(Exception):
        pass
    def acquire(proof):
        captured.append(copy.deepcopy(proof))
        raise BeforeAnyOutcome
    def forbidden(row):
        raise AssertionError('No target label or native provider may be queried')
    try:
        frozen.run_search(case,forbidden,on_acquire=acquire)
    except BeforeAnyOutcome:
        pass
    c.require(len(captured) == 1, 'Exactly one label-free acquisition witness required')
    proof = captured[0]
    c.require(isinstance(proof['event']['score'],tuple), 'Witness must expose the frozen tuple/JSON mismatch')
    output.mkdir(parents=True)
    c.seal(output/'witness.json',proof)
    decoded = c.unseal(output/'witness.json')
    c.require(decoded != proof and canonical_proof(proof) == decoded and c.digest(proof) == c.digest(decoded),
        'Exact tuple/list-only failure and numeric-preserving repair must be demonstrated before labels')
    c.seal(output/'cohort.json',dict(schema=CONTRACT,phase='pre-label serialization amendment',
        source_history=cohort['source_history'],historical_costs=cohort['historical_costs'],targets={},
        preregistration=prereg.relative_to(ROOT).as_posix(),prereg_manifest_sha256=c.sha(prereg/'manifest.json'),
        source_bindings={SOURCE:c.sha(ROOT/SOURCE),frozen.SOURCE:c.sha(ROOT/frozen.SOURCE)},
        target_labels_observed=0,target_labels_read=0,target_candidate_attempts=0,
        witness_sha256=c.sha(output/'witness.json'),frozen_python_equality=False,
        repaired_python_equality=True,canonical_json_digest_identical=True,
        change='Only acquisition_proof.event.score tuple becomes a JSON list. No serialized value, score, model, policy, target label or native cost changes.',
        numeric_tolerance_used=False,frozen_sources_edited=False))
    for name in (SOURCE,frozen.SOURCE):
        destination = output/'sources'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,destination)
    frozen.prior._zero(native)
    frozen.prior._seal_manifest(output)
    authenticate(output,prereg)
    return c.unseal(output/'cohort.json')


def authenticate(amendment,prereg,commit=None):
    amendment,prereg = Path(amendment).resolve(),Path(prereg).resolve()
    frozen.prior._manifest(amendment)
    record = c.unseal(amendment/'cohort.json')
    c.require(record['schema'] == CONTRACT and record['phase'] == 'pre-label serialization amendment' and
        record['preregistration'] == prereg.relative_to(ROOT).as_posix() and
        record['prereg_manifest_sha256'] == c.sha(prereg/'manifest.json') and
        record['source_bindings'] == {SOURCE:c.sha(ROOT/SOURCE),frozen.SOURCE:c.sha(ROOT/frozen.SOURCE)} and
        all(type(record[key]) is int and record[key] == 0 for key in
            ('target_labels_observed','target_labels_read','target_candidate_attempts')) and
        record['frozen_python_equality'] is False and record['repaired_python_equality'] is True and
        record['canonical_json_digest_identical'] is True and record['numeric_tolerance_used'] is False and
        record['frozen_sources_edited'] is False and record['witness_sha256'] == c.sha(amendment/'witness.json'),
        'Exact source-bound zero-label JSON proof amendment required')
    witness = c.unseal(amendment/'witness.json')
    c.require(canonical_proof(witness) == witness, 'Recorded witness must be exact canonical JSON')
    for name,digest in record['source_bindings'].items():
        c.require(c.sha(amendment/'sources'/name) == digest, 'Amendment source snapshot changed')
    if commit is not None:
        frozen.prior.check_git_checkpoint(amendment,commit)
    return dict(contract=CONTRACT,phase=record['phase'],path=amendment.relative_to(ROOT).as_posix(),
        manifest_sha256=c.sha(amendment/'manifest.json'),source_bindings=record['source_bindings'],
        witness_sha256=record['witness_sha256'],frozen_sources_edited=False,
        serialized_proof_values_exact=True,numeric_tolerance_used=False)


def pack(prereg,native,collection,release_path,output,*,amendment=AMENDMENT):
    prereg,output = Path(prereg).resolve(),Path(output).resolve()
    released = c.unseal(release_path)
    binding = authenticate(amendment,prereg,released['prelabel_commit'])
    with normalized_proofs():
        result = frozen.pack(prereg,native,collection,release_path,output)
    c.seal(output/'proof-amendment.json',binding)
    frozen.prior._seal_manifest(output)
    return dict(result,proof_amendment=binding)


def replay(campaign,output,*,amendment=AMENDMENT):
    campaign,output = Path(campaign).resolve(),Path(output).resolve()
    frozen.prior._manifest(campaign)
    provenance = c.unseal(campaign/'provenance.json'); prereg = ROOT/provenance['preregistration']
    binding = authenticate(amendment,prereg,provenance['prelabel_commit'])
    c.require(c.unseal(campaign/'proof-amendment.json') == binding, 'Pre-label proof amendment differs')
    with normalized_proofs():
        result = frozen.replay(campaign,output)
    c.seal(output/'proof-amendment.json',binding)
    frozen.prior._seal_manifest(output)
    return dict(result,proof_amendment=binding)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','pack','replay'))
    for name in ('preregistration','native-root','collection','release','output','campaign'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--amendment',type=Path,default=AMENDMENT)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.preregistration,args.output)
    elif args.command == 'pack':
        result = pack(args.preregistration,args.native_root,args.collection,args.release,args.output,amendment=args.amendment)
    else:
        result = replay(args.campaign,args.output,amendment=args.amendment)
    print(result)


if __name__ == '__main__':
    main()
