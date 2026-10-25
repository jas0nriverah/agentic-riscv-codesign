"""Distinct tail-transfer CFG-coverage context; candidates stay disabled.

The original Lift and first CFG-context rejections remain final. This context
adds only exact statically resolved non-linking tail transfers to CFG coverage.
Original input, compiler, processor, partition, relocation/calibration,
stratification and opportunity gate remain fixed. Canonical returns use a
declared ordinary compiled-C ABI assumption; this is not an arbitrary-binary or
universal program-equivalence proof.
"""
from __future__ import annotations

import copy
import argparse
import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from . import codesign as c, lift_workload as lift, cfg_liveness_tail as cfg
from . import assembly_lowering as lowering

SOURCE = 'isaforge/cfg_lift_workload_tail.py'
QUALIFIER = 'scripts/qualify_cfg_lift_tail.py'
CONTRACT = 'docs/cfg-liveness-tail-transfer.md'
ORIGINAL_REJECTION = 'results/2026-10-25-lift-qualification'
PRIOR_CFG_REJECTION = 'results/2026-10-25-lift-cfg-qualification'
PRIOR_CFG_REJECTION_FILES = tuple(PRIOR_CFG_REJECTION+'/'+name for name in
                                  ('protocol.json', 'qualification.json', 'manifest.json'))
base, g, evidence, prior = lift.base, lift.g, lift.evidence, lift.prior
WORKLOAD, GROUP, BASE, PROGRAM = lift.WORKLOAD, lift.GROUP, lift.BASE, lift.PROGRAM
PROVENANCE, UPSTREAM_COMMIT, UPSTREAM = lift.PROVENANCE, lift.UPSTREAM_COMMIT, dict(lift.UPSTREAM)
POOL_SIZE, PARTITION, NATIVE_LIMITS, ABI = lift.POOL_SIZE, dict(lift.PARTITION), dict(lift.NATIVE_LIMITS), copy.deepcopy(lift.ABI)
# Exact existing firmware, not a generic exception-handler assumption. These
# independently pinned bytes establish startup EBREAK, IRQ disablement and both
# simulators' terminal trap handling before either core option can be enabled.
FIRMWARE_TRAP_SOURCES = {
    'hardware/soc_start.S':'5f80f0e780ab4f8eb2bd18846dbeb5ab4406ca1efaa3221fb4c1e305bb4b0447',
    'hardware/soc_top.v':'912829da3e0754ff2522754b57368b11a9d38b8fb2494ca73ff8abaf38f2cb98',
    'hardware/profile_sim.cpp':'76770bcff03f67a82bfdb410c7687f24f733326b2a221d615f11c8116da43b45',
    'hardware/checked_sim.cpp':'477635f316551bf85bd7ac1addc11bb9fa2c252969202621e75692ea5cfd9f07'}
COVERAGE = dict(schema='isaforge-lift-static-cfg-tail-transfer-context-v2',
    certificate_schema=cfg.SCHEMA, extraction_schema=cfg.EXTRACTION_SCHEMA,
    verification_schema=cfg.VERIFICATION_SCHEMA, compiler_abi_returns=True,
    firmware_trap_exit=True, firmware_trap_source_bindings=dict(FIRMWARE_TRAP_SOURCES),
    trap_assumption='Exact raw EBREAK is an all-live terminal exit only in the pinned startup, IRQ-disabled SoC and profile/checked simulators that terminate on trap; no generic exception handler.',
    return_assumption='Only canonical raw jalr x0,x1,0 is an ordinary compiled-C ABI return; not arbitrary binary control flow.',
    resolved_direct_calls='Only exact adjacent raw AUIPC/JALR pairs with a shared nonzero base resolve: x1/x1 link calls or x0/base non-linking direct tail transfers. Targets must be aligned and in-program; every second word is protected against all static entries; transfers remain all-live barriers.',
    readonly_counters='Only exact CSRRS rd,{cycle,cycleh,instret,instreth},x0 encodings; opaque all-live isolated barriers, never fusion members.',
    unsupported_entries='Every other unknown effect or unsupported indirect entry makes extraction fail closed; both static branch edges, resolved call targets and continuations remain protected.',
    extraction='Scoped guarded ORIGINAL_EXTRACT; existing relocation guard, calibration filter and rank stratification unchanged.',
    verification='Reconstruct saved original assembly, linked static program, complete baseline profile and source-PC map for every callback; never trust candidate-supplied proof.',
    contract=CONTRACT)
PROTOCOL = dict(copy.deepcopy(lift.PROTOCOL), schema='isaforge-tacle-lift-cfg-tail-v2',
    coverage_context=copy.deepcopy(COVERAGE),
    lowering_verification=cfg.VERIFICATION_SCHEMA,
    unchanged_verifier=False, unchanged_upstream_correctness_verifier=True,
    unchanged_full_register_lowering_verifier=False,
    preserved_original_rejection=dict(path=ORIGINAL_REJECTION, final=True, target_candidate_attempts=0),
    preserved_prior_cfg_rejection=dict(path=PRIOR_CFG_REJECTION, final=True, target_candidate_attempts=0),
    unchanged_context_rule='Distinct v2 static-CFG tail-transfer coverage context; both earlier Lift rejections remain final. Original input, hardware, flags, partition, pool and numeric gate remain unchanged.',
    rejection_rule='Preserve both earlier rejections and this context first rejection; no retry, relabeling, gate changes or automatic source fallback.')
RUNTIME_SUPPORT = lift.RUNTIME_SUPPORT+' Static CFG liveness with explicit ordinary compiled-C canonical-return assumption and exact direct AUIPC/JALR tail-transfer resolution; original source verifier unchanged.'
CONTEXT_TRANSFER = 'Consumed Lift engineering-coverage context with static CFG liveness and exact compiler tail-transfer recognition; original1001-input/checksum4005888, hardware and partition retained.'
GATE_SOURCES = tuple(dict.fromkeys((SOURCE, QUALIFIER, CONTRACT, 'scripts/qualify_tacle_lift.py',
                                  'scripts/preflight_cfg_lift_tail.py', 'scripts/analyze_speedup_model.py',
                                  *FIRMWARE_TRAP_SOURCES, *PRIOR_CFG_REJECTION_FILES,
                                  *cfg.SOURCES, *lift.GATE_SOURCES)))
POOL_RULE = 'Static CFG-liveness coverage with explicit compiled-C return assumption; '+g.POOL_RULE
_ORIGINAL = dict(lift._ORIGINAL)
# This carries only a scoped root path, never cached program/profile/certificates.
_ACTIVE_ROOT = ContextVar('isaforge_cfg_lift_tail_root', default=None)
_ENVELOPE_FIELDS = frozenset(('candidate_id', 'lowering_check', 'assembly', 'assembly_sha256'))


@contextmanager
def source_binding(*, deriving=False):
    replacements = dict(SOURCE=SOURCE, WORKLOAD=WORKLOAD, GROUP=GROUP, BASE=BASE, PROGRAM=PROGRAM,
        PROVENANCE=PROVENANCE, UPSTREAM_COMMIT=UPSTREAM_COMMIT, UPSTREAM=UPSTREAM,
        POOL_SIZE=POOL_SIZE, PARTITION=PARTITION, NATIVE_LIMITS=NATIVE_LIMITS,
        PROTOCOL=PROTOCOL, GATE_SOURCES=GATE_SOURCES, registration=registration,
        upstream_record=upstream_record, prepare=prepare, baseline_public=baseline_public,
        opportunity_gate=opportunity_gate, discovery_public=discovery_public,
        opportunity=opportunity, check_opportunity=check_opportunity,
        Evaluator=Evaluator, __doc__=__doc__,
        check_plan=_ORIGINAL['check_plan'] if deriving else check_plan,
        validate_inputs=_ORIGINAL['validate_inputs'] if deriving else validate_inputs)
    previous = {name:getattr(base,name) for name in replacements}
    try:
        for name,value in replacements.items():
            setattr(base,name,value)
        yield
    finally:
        for name,value in previous.items():
            setattr(base,name,value)


def _extract(program, profile, site_map, size):
    validate_firmware_context()
    return cfg.extract(program, profile, site_map, size, compiler_abi_returns=True,
                       firmware_trap_exit=True)


def validate_firmware_context():
    for name, expected in FIRMWARE_TRAP_SOURCES.items():
        c.require(c.sha(c.ROOT/name) == expected,
                  'Exact startup/IRQ-disabled/trap-terminal firmware context required: '+name)


@contextmanager
def registration(root=None):
    """Opt in per context; restore every binding after nesting or interruption."""
    effective = Path(root).resolve() if root is not None else _ACTIVE_ROOT.get()
    token = _ACTIVE_ROOT.set(effective)
    try:
        with source_binding(), _ORIGINAL['registration']():
            previous = (g.WORKLOADS, g.ORIGINAL_EXTRACT, g.POOL_RULE, lowering.verify_lowering)
            g.WORKLOADS = {WORKLOAD:'../../tacle/lift/isaforge_adapter.c'}
            g.ORIGINAL_EXTRACT, g.POOL_RULE = _extract, POOL_RULE
            def verify(candidate, program, starts, vectors=64):
                c.require(effective is not None, 'Root-bound CFG verification callback required')
                return verify_from_root(effective, candidate, program, starts, vectors=vectors)
            lowering.verify_lowering = verify
            try:
                yield
            finally:
                g.WORKLOADS, g.ORIGINAL_EXTRACT, g.POOL_RULE, lowering.verify_lowering = previous
    finally:
        _ACTIVE_ROOT.reset(token)


def upstream_record():
    return lift.upstream_record()


def check_plan(plan):
    validate_firmware_context()
    with source_binding():
        _ORIGINAL['check_plan'](plan)
    c.require(plan.get('coverage_context') == COVERAGE and
              plan.get('runtime_support') == RUNTIME_SUPPORT,
              'Distinct explicitly declared Lift CFG coverage context required')
    for name, expected in FIRMWARE_TRAP_SOURCES.items():
        filename = Path(name).name
        if filename == 'checked_sim.cpp':
            # The existing qualified driver changes only the frozen cycle
            # ceiling; retain its independently checked terminal trap behavior.
            expected = hashlib.sha256(g.q.extended.driver_source(filename).encode()).hexdigest()
        c.require(plan['inputs'].get(filename) == expected,
                  'Exact bound firmware trap input required: '+filename)


def validate_inputs(root):
    with source_binding():
        return _ORIGINAL['validate_inputs'](root)


def prepare(reference, output):
    validate_firmware_context()
    with source_binding(deriving=True):
        plan = _ORIGINAL['prepare'](reference, output)
    plan.pop('context_id')
    plan.update(coverage_context=copy.deepcopy(COVERAGE), runtime_support=RUNTIME_SUPPORT,
        selection_evidence_scope='Consumed Lift coverage engineering only; no native candidate outcomes, model fitting or prospective superiority claim.',
        context_amendment='Distinct static-CFG coverage and projected-register verification context; the original rejected Lift context is preserved. Compiler/input/hardware/pool/gates remain exact.')
    plan['context_id'] = c.digest(plan)
    c.seal(Path(output)/'plan.json', plan)
    validate_inputs(output)
    return plan


def saved_discovery_inputs(root):
    """Read actual original artifacts anew; reject ambiguous or relocated inputs."""
    root = Path(root).resolve()
    folders = sorted((root/'discovery').glob('attempt-*'))
    c.require(len(folders) == 1 and folders[0].is_dir(), 'One original discovery attempt required')
    folder = folders[0].resolve()
    c.require(folder.is_relative_to(root/'discovery'), 'Discovery attempt outside native root')
    required = ('program.s', 'marked.S', 'marked/symbols.txt', 'marked/disassembly.txt',
                'profile/simulation.json', 'marked/firmware.hex', 'original/firmware.hex')
    for name in required:
        path = (folder/name).resolve()
        c.require(path.is_relative_to(folder) and path.is_file(), 'Missing or escaped saved original artifact: '+name)
    if (root/'discovery/discovery.json').exists():
        found = g.w.verify_cache(root/'discovery', 'discovery.json')
        c.require((root/found['baseline_image']).resolve() == folder/'marked/firmware.hex' and
                  (root/found['profile']).resolve() == folder/'profile/simulation.json',
                  'Authenticated original discovery paths differ')
    marked, sites = lowering.mark_assembly((folder/'program.s').read_text())
    c.require(marked == (folder/'marked.S').read_text(), 'Original marked source differs')
    c.require(c.sha(folder/'original/firmware.hex') == c.sha(folder/'marked/firmware.hex'),
              'Original and marked firmware differ')
    site_map = lowering.map_sites(sites, (folder/'marked/symbols.txt').read_text())
    program = lowering.read_program((folder/'marked/disassembly.txt').read_text())
    profile = c.read(folder/'profile/simulation.json')
    return program, profile, site_map


def verify_from_root(root, candidate, program, starts, *, vectors=64):
    """Authenticate root-derived inputs and reprove core legality, never metadata."""
    plan = validate_inputs(root)
    actual_program, profile, site_map = saved_discovery_inputs(root)
    c.require(program == actual_program, 'Verifier program differs from saved original program')
    extraction = _extract(actual_program, profile, site_map, plan['pool_size'])
    c.require(list(starts) == extraction['block_starts'], 'Verifier block starts differ from saved original profile/CFG')
    c.require(candidate.get('candidate_id') == c.digest([plan['context_id'], candidate['formula']]),
              'Native candidate identity differs from current coverage context')
    core = {key:copy.deepcopy(value) for key,value in candidate.items() if key not in _ENVELOPE_FIELDS}
    return cfg.verify_lowering(core, actual_program, profile, site_map, extraction['certificate'],
                               vectors=vectors, compiler_abi_returns=True,
                               firmware_trap_exit=True)


def authenticate_discovery(root):
    validate_inputs(root)
    with registration(root):
        return g.authenticate_discovery(root)


def opportunity_gate(public):
    with source_binding():
        return _ORIGINAL['opportunity_gate'](public)


def discovery_public(root):
    validate_inputs(root)
    with source_binding(), registration(root):
        return _ORIGINAL['discovery_public'](root)


def opportunity(root):
    validate_inputs(root)
    with source_binding(), registration(root):
        return _ORIGINAL['opportunity'](root)


def check_opportunity(root):
    validate_inputs(root)
    with source_binding(), registration(root):
        return _ORIGINAL['check_opportunity'](root)


class Evaluator(_ORIGINAL['Evaluator']):
    def __init__(self, root):
        validate_inputs(root)
        with source_binding(), registration(root):
            super().__init__(root)

    def discover(self):
        with source_binding(), registration(self.root):
            return super().discover()

    def measure(self, name):
        c.require(name == 'baseline', 'Candidate dispatch disabled during Lift CFG coverage qualification')
        with source_binding(), registration(self.root):
            return super().measure(name)


def baseline_public(root):
    validate_inputs(root)
    with source_binding(), registration(root):
        rows,context,before = _ORIGINAL['baseline_public'](root)
    context['context_transfer'] = CONTEXT_TRANSFER
    context['coverage_context'] = copy.deepcopy(COVERAGE)
    return rows,context,before


def main(argv=None):
    # Keep the saved-root callback bound across freeze_pool's direct guarded
    # baseline authentication as well as nested evaluator methods. The frozen
    # CLI remains responsible for full command/argument validation.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--root', type=Path)
    known, _ = parser.parse_known_args(argv)
    with source_binding(), registration(known.root):
        return _ORIGINAL['main'](argv)


if __name__ == '__main__':
    main()
