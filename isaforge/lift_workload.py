"""Original-input TACLe lift qualification through the frozen guarded pipeline.

The only build change is a declared three-file ABI amalgamation. The original
1,001 zero-input controller iterations and checksum4,005,888 remain unchanged.
No candidate dispatcher or policy/model experiment is provided here.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from . import codesign as c, next_tacle_workload as base

SOURCE = 'isaforge/lift_workload.py'
HELPER_SOURCE = base.SOURCE
WORKLOAD = 'lift'
GROUP = 'tacle-lift'
BASE = 'benchmarks/tacle/lift/'
PROGRAM = BASE+'isaforge_adapter.c'
PROVENANCE = 'benchmarks/tacle/LIFT_SOURCES.json'
UPSTREAM_COMMIT = 'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
UPSTREAM = {
    'lift.c':'37cdaa52e7aafea8f9bd116a73366955d9215400c6ad402f62f35ab624d0a1ea',
    'liftlibcontrol.c':'370cd4369e41925c942b41eea4751ad2897d3db0985dfc8efcd6d13436f4bd19',
    'liftlibio.c':'050b104d594142bb0d0067e6a2f1c1fed095029e99c2d64d0d7b1a677cf44ae6',
    'liftlibcontrol.h':'327e6cc4b14fddb5e5f5f58ce4262f63af7f80e9e7399eb6290d410278c343ec',
    'liftlibio.h':'eebf92aa26e4689da2b6863de1ca3d7854b3bf40316a3116459441bc5e26014c',
    'README':'81c27f9f20b6202bd981ac98d5799319436305a0ed6475eafa806e63cfdaa976',
    'changeLog.txt':'01b1131cdf90cfdec2e1265d3b1cf3daa6b8ac64783bc50d0c321f352abc9dff',
}
g, evidence, prior = base.g, base.evidence, base.prior
POOL_SIZE = base.POOL_SIZE
PARTITION = dict(base.PARTITION)
NATIVE_LIMITS = dict(base.NATIVE_LIMITS)
ABI = dict(data_model='ILP32, eight-bit bytes',
    source_order=['lift.c','liftlibio.c','liftlibcontrol.c'],
    namespace='Only main renamed to isaforge_tacle_lift_original_main; original lift_* symbols and separate storage preserved.',
    layout_assertions='sizeof(int),sizeof(long),sizeof(void*)=4;sizeof(short)=2;__CHAR_BIT__=8; original five array sizes asserted.',
    compilation='Single translation unit with three unchanged C files and unchanged headers; not separate-object binary identity.')
RUNTIME_SUPPORT = 'Original lift_init/lift_main/lift_return,1001zero digital/ADC stimuli and checksum4005888; external ILP32 ABI/amalgamation only.'
CONTEXT_TRANSFER = 'Original-input TACLeBench lift; declared three-file amalgamation and unchanged guarded8KiB RV32I context.'
PROTOCOL = dict(schema='isaforge-tacle-lift-v1',workload_group=GROUP,pool_size=POOL_SIZE,
    minimum_calibrated_cycle_reduction=.005,minimum_timed_replacements=10,
    joint_gate='At least one selected formula satisfies both numeric minima.',
    unchanged_input=True,unchanged_upstream_source=True,unchanged_verifier=True,
    original_input=dict(controller_iterations=1001,digital_stimulus=0,adc1=0,adc2=0,adc3=0),
    build_context=ABI,
    correctness='Original lift_return requires checksum4005888 after original1001 zero-input controller iterations.',
    target_candidate_attempts=0,candidate_dispatch='Disabled in qualification-only adapter.',
    unchanged_context_rule='One original lift input/context only; preserve rejection without input, pool, memory, gate or helper changes.',
    rejection_rule='Preserve first rejection and partial archive; no retries or automatic source fallback.')
GATE_SOURCES = tuple(dict.fromkeys((SOURCE,HELPER_SOURCE,prior.SOURCE,g.SOURCE,
    'scripts/blind_campaign.py',*prior.semantic.SOURCES,'isaforge/latency_features.py',PROGRAM,PROVENANCE,
    *(BASE+name for name in UPSTREAM))))

# Capture originals before installing any scoped bindings. No frozen source or
# persistent global is edited; the same process supports nesting and exceptions.
_ORIGINAL = {name:getattr(base,name) for name in ('registration','prepare','check_plan','validate_inputs',
    'opportunity_gate','discovery_public','opportunity','check_opportunity','baseline_public','main','Evaluator')}


@contextmanager
def source_binding(*,deriving=False):
    replacements = dict(SOURCE=SOURCE,WORKLOAD=WORKLOAD,GROUP=GROUP,BASE=BASE,PROGRAM=PROGRAM,
        PROVENANCE=PROVENANCE,UPSTREAM_COMMIT=UPSTREAM_COMMIT,UPSTREAM=UPSTREAM,POOL_SIZE=POOL_SIZE,
        PARTITION=PARTITION,NATIVE_LIMITS=NATIVE_LIMITS,PROTOCOL=PROTOCOL,GATE_SOURCES=GATE_SOURCES,
        registration=registration,upstream_record=upstream_record,prepare=prepare,
        baseline_public=baseline_public,Evaluator=Evaluator,__doc__=__doc__,
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


@contextmanager
def registration():
    with source_binding(),_ORIGINAL['registration']():
        previous = g.WORKLOADS
        g.WORKLOADS = {WORKLOAD:'../../tacle/lift/isaforge_adapter.c'}
        try:
            yield
        finally:
            g.WORKLOADS = previous


def upstream_record():
    return dict(suite='TACLeBench',commit=UPSTREAM_COMMIT,directory='bench/app/lift',files=dict(UPSTREAM),
        provenance=PROVENANCE,provenance_sha256=c.sha(c.ROOT/PROVENANCE),
        adapter=PROGRAM,adapter_sha256=c.sha(c.ROOT/PROGRAM),abi=ABI)


def check_plan(plan):
    with source_binding():
        _ORIGINAL['check_plan'](plan)
    c.require(plan.get('runtime_support') == RUNTIME_SUPPORT,
        'Original-input lift ABI/amalgamation metadata required')


def validate_inputs(root):
    with source_binding():
        plan = _ORIGINAL['validate_inputs'](root)
    return plan


def prepare(reference,output):
    with source_binding(deriving=True):
        plan = _ORIGINAL['prepare'](reference,output)
    # Replace only the reused helper's source-specific descriptive string before
    # any native operation. Its original extraction/context machinery is intact.
    plan.pop('context_id')
    plan['runtime_support'] = RUNTIME_SUPPORT
    plan['context_id'] = c.digest(plan)
    c.seal(Path(output)/'plan.json',plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    with source_binding():
        return _ORIGINAL['opportunity_gate'](public)


def discovery_public(root):
    validate_inputs(root)
    with source_binding():
        return _ORIGINAL['discovery_public'](root)


def opportunity(root):
    validate_inputs(root)
    with source_binding():
        return _ORIGINAL['opportunity'](root)


def check_opportunity(root):
    validate_inputs(root)
    with source_binding():
        return _ORIGINAL['check_opportunity'](root)


class Evaluator(_ORIGINAL['Evaluator']):
    def __init__(self,root):
        validate_inputs(root)
        with source_binding():
            super().__init__(root)

    def discover(self):
        with source_binding():
            return super().discover()

    def measure(self,name):
        c.require(name == 'baseline','Candidate dispatch disabled during lift zero-label qualification')
        with source_binding():
            return super().measure(name)


def baseline_public(root):
    validate_inputs(root)
    with source_binding():
        rows,context,before = _ORIGINAL['baseline_public'](root)
    context['context_transfer'] = CONTEXT_TRANSFER
    return rows,context,before


def main(argv=None):
    with source_binding():
        return _ORIGINAL['main'](argv)


if __name__ == '__main__':
    main()
