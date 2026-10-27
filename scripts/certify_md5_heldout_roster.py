"""Offline certificates for the fixed public MD5 roster; no native entry point.

Only saved baseline text/metadata and the existing pure block verifier are used.
This script never enumerates candidates or authorizes candidate measurements.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
from isaforge import codesign as c, assembly_lowering as lowering, relocation_guard as guard

ROOT = SOURCE_ROOT
PREREG = Path('results/2026-10-26-md5-candidate-heldout-prereg')
BASE = Path('generated/blind-cohort-2026-10-21/nettle-md5')
ROSTER_SHA256 = 'c4ac398adbd28f3ef975d60a73b0863b20974a794259ed3141050bbc7e60cdd9'
AUDIT_SHA256 = 'c0c58c9f6e89bb12cc954cf54ffe84eb22b23b911f8dbc1ecb8842e6debc2f8b'
VECTORS = 64
SEED = 20261019  # Existing verify_lowering contract; not a new sampling choice.
SOURCES = ('scripts/certify_md5_heldout_roster.py', 'isaforge/codesign.py',
           'isaforge/assembly_lowering.py', 'isaforge/relocation_guard.py',
           'isaforge/features.py', 'isaforge/rtl.py', 'src/candidates.py',
           'src/tracing.py', 'src/verify_candidate_fusions.py')
PUBLIC_FILES = ('program.s', 'marked.S', 'marked/symbols.txt',
                'marked/disassembly.txt', 'marked/firmware.hex', 'original/firmware.hex')


def read_json(path):
    return json.loads(path.read_text())


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def public_inputs():
    """Authenticate only an explicit public-file allowlist; no outcome traversal."""
    prereg = ROOT/PREREG
    manifest = read_json(prereg/'artifact-manifest.json')
    for name in ('preregistration.json', 'roster.json'):
        c.require(c.sha(prereg/name) == manifest[name], 'Preregistration artifact changed: '+name)
    audit = prereg/'independent-cohort-audit.json'
    audit_sidecar = prereg/'independent-cohort-audit.json.sha256'
    c.require(audit_sidecar.read_text().strip() == c.sha(audit) == AUDIT_SHA256,
              'Independent cohort audit or SHA256 sidecar changed')
    protocol = read_json(prereg/'preregistration.json')
    roster_bytes = (prereg/'roster.json').read_bytes()
    roster = json.loads(roster_bytes)
    c.require(roster_bytes == compact(roster) and c.sha(prereg/'roster.json') == ROSTER_SHA256 ==
              protocol['roster']['sha256'], 'Exact compact roster serialization changed')
    c.require(len(roster) == 12 and len({r['name'] for r in roster}) == 12 and
              len({r['formula'] for r in roster}) == 12 and
              all(set(r) == {'name','formula'} for r in roster), 'Exact twelve distinct roster entries required')
    c.require(protocol['eligibility_pending'] is True and
              protocol['candidate_dispatch_enabled'] is False and protocol['new_pool_labels'] == 0 and
              protocol['historical_md5_labels_excluded'] is True, 'Zero-label qualification boundary changed')
    bindings = protocol['source_artifact_sha256']
    base = ROOT/BASE
    input_hashes = {}
    for suffix in ('plan.json','discovery/discovery.json'):
        path = base/suffix
        expected = bindings[(BASE/suffix).as_posix()]
        c.require(c.sha(path) == expected, 'Bound public metadata changed: '+suffix)
        input_hashes[(BASE/suffix).as_posix()] = expected
    plan, discovery = read_json(base/'plan.json'), read_json(base/'discovery/discovery.json')
    context = plan['context_id']
    c.require(c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == context and
              discovery['context_id'] == context == protocol['existing_context_id'], 'Public context identity changed')
    c.require(plan['workload'] == 'nettle-md5' and discovery['workload'] == 'nettle-md5', 'Different workload')
    pure_sources = {}
    for name in SOURCES[1:]:
        expected = plan.get('source_bindings', {}).get(name, bindings.get(name))
        c.require(expected is not None and c.sha(SOURCE_ROOT/name) == expected,
                  'Bound pure dependency changed or missing: '+name)
        pure_sources[name] = expected
    folder = base/'discovery/attempt-000'
    for suffix in PUBLIC_FILES:
        path = folder/suffix
        expected = discovery['artifacts']['attempt-000/'+suffix]
        c.require(c.sha(path) == expected, 'Archived public baseline input changed: '+suffix)
        input_hashes[(BASE/'discovery/attempt-000'/suffix).as_posix()] = expected
    marked, sites = lowering.mark_assembly((folder/'program.s').read_text())
    c.require(marked == (folder/'marked.S').read_text(), 'Saved statement markers differ')
    c.require(c.sha(folder/'marked/firmware.hex') == c.sha(folder/'original/firmware.hex'),
              'Original and marked baseline bytes differ')
    site_map = lowering.map_sites(sites, (folder/'marked/symbols.txt').read_text())
    program = lowering.read_program((folder/'marked/disassembly.txt').read_text())
    # Match the original extractor's source-symbol assignment, without enumeration.
    for pc, site in site_map.items():
        c.require(pc in program, 'Source site absent from saved baseline disassembly')
        program[pc]['symbol'] = site['function']
    candidates = discovery['executable_candidates']
    by_name = {r['name']:r for r in candidates}
    c.require(len(by_name) == len(candidates), 'Duplicate archived candidate names')
    selected = []
    for row in roster:
        c.require(row['name'] in by_name and by_name[row['name']]['formula'] == row['formula'],
                  'Roster differs from archived public inventory')
        selected.append(copy.deepcopy(by_name[row['name']]))
    return dict(roster=roster, candidates=selected, context=context, discovery=discovery,
                marked=marked, sites=sites, site_map=site_map, program=program,
                input_sha256=input_hashes, pure_source_sha256=pure_sources,
                prereg_sha256={name:c.sha(prereg/name) for name in
                    ('preregistration.json','roster.json','artifact-manifest.json',
                     'independent-cohort-audit.json','independent-cohort-audit.json.sha256')})


def certify_candidate(candidate, data):
    """Validate one stored occurrence list; no candidate search or native tools."""
    c.require(candidate.get('occurrences'), 'No stored executable occurrences')
    for occurrence in candidate['occurrences']:
        pcs = [int(pc,16) if isinstance(pc,str) else pc for pc in occurrence['pcs']]
        c.require(2 <= len(pcs) <= 4 and len(set(pcs)) == len(pcs), 'Invalid occurrence size')
        c.require(all(pc in data['site_map'] for pc in pcs), 'Occurrence lacks complete source mapping')
        c.require([data['site_map'][pc]['site'] for pc in pcs] == occurrence['sites'],
                  'Archived occurrence source-PC mapping differs')
    relocation = guard.require_relocation_free(candidate, data['sites'])
    checked = lowering.verify_lowering(candidate, data['program'],
                                      data['discovery']['block_starts'], vectors=VECTORS)
    c.require(checked['passed'] is True and checked['comparisons'] == VECTORS*checked['blocks'],
              'Incomplete sampled block comparisons')
    assembly = lowering.lower(data['marked'], candidate)
    certificate = dict(name=candidate['name'], formula=candidate['formula'],
        candidate_id=c.digest([data['context'], candidate['formula']]),
        candidate_identity_serialization='codesign.digest([context_id,formula]): sorted-key JSON with default spaces; distinct from compact roster file SHA256',
        context_id=data['context'], source_occurrences=copy.deepcopy(candidate['occurrences']),
        relocation_check=relocation, lowering_check=checked,
        assembly=candidate['name']+'.S', assembly_sha256=hashlib.sha256(assembly.encode()).hexdigest(),
        candidate_dispatch_enabled=False, new_pool_labels=0,
        certificate_scope='Existing 64-vector pure-Python full-register/memory/control block check; not universal equivalence, assembled firmware validation or whole-program execution.')
    return certificate, assembly


def build(output):
    output = Path(output).resolve(); parent = (ROOT/PREREG).resolve()
    c.require(output.parent == parent and not output.exists(),
              'Fresh direct certificate subdirectory under the MD5 preregistration required')
    data = public_inputs()
    sources = {SOURCES[0]:c.sha(SOURCE_ROOT/SOURCES[0]), **data['pure_source_sha256']}
    result = dict(schema='isaforge-md5-offline-lowering-certificates-v1',
        status='incomplete', eligibility_pending=True, candidate_dispatch_enabled=False,
        new_pool_labels=0, historical_md5_labels_excluded=True,
        global_unmeasured_status='unresolved pending cross-context attempted-identity audit',
        context_id=data['context'], roster_file_sha256=ROSTER_SHA256,
        roster_codesign_digest=c.digest(data['roster']),
        roster_serialization='Compact sorted-key UTF-8 JSON, no trailing newline',
        codesign_digest_serialization='json.dumps(value,sort_keys=True,allow_nan=False) with default spaces',
        input_sha256=data['input_sha256'], preregistration_sha256=data['prereg_sha256'],
        pure_verifier_source_sha256=sources,
        verifier_contract=dict(vectors_per_block=VECTORS, random_seed=SEED,
            full_register_memory_control=True, joint_occurrences_within_block=True,
            universal_proof=False, whole_program_execution=False),
        forbidden_operations_invoked=False, candidate_enumeration=False, native_jobs=0,
        certificates=[], limitations=[
            'Context-derived candidate IDs reference the preserved baseline context; a future new plan/protocol must explicitly bind or remap them.',
            'No compiler/assembler/linker validation of the emitted source; no candidate firmware or processor execution.',
            'No RTL proof, synthesis, routing, integrated area/timing or measured performance.',
            'No whole-workload holdout or global unmeasured assertion; MD5 remains consumed development.',
            'The existing pool-level opportunity gate is unchanged; these certificates grant no dispatch authorization.'])
    output.mkdir()
    active = None
    try:
        for candidate in data['candidates']:
            active = candidate['name']
            certificate, assembly = certify_candidate(candidate,data)
            (output/certificate['assembly']).write_text(assembly)
            result['certificates'].append(certificate)
        c.require(len(result['certificates']) == 12, 'All twelve certificates required')
        result['status'] = 'offline_certificates_complete_eligibility_pending'
    except BaseException as error:
        result.update(status='rejected', failed_candidate=active, failure=repr(error))
        raise
    finally:
        c.seal(output/'certificates.json',result)
        c.seal(output/'artifact-manifest.json',{
            p.name:c.sha(p) for p in sorted(output.iterdir())
            if p.is_file() and p.name not in ('artifact-manifest.json','artifact-manifest.json.sha256')})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/PREREG/'offline-certificates-v1')
    args = parser.parse_args(argv)
    result = build(args.output)
    print(json.dumps(dict(status=result['status'], certificates=len(result['certificates']),
                         native_jobs=result['native_jobs'],candidate_dispatch_enabled=False)))


if __name__ == '__main__':
    main()
