"""Pinned nanocobs original differential probe workload on the guarded PicoRV32 pipeline.

Qualification is baseline-only. It reuses the existing extraction, RV32I
lowering, stack checks, cycle simulator, and integrated area/routing evaluator;
candidate dispatch stays disabled until a separate frozen release is reviewed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil

from . import budgeted_selection as budget
from . import blind_workload as bw
from . import campaign_evidence as evidence
from . import codesign as c
from . import guarded_workload as g
from .speedup_corpus import family
from . import latency_features

lowering, guard, w, q = g.lowering, g.guard, g.w, g.q
VARIABLE_POOL_RULE = 'All calibrated relocation-safe formulas up to the computational cap; deterministic rank-stratified cap, no minimum benefit or occurrence admission.'

SOURCE = 'isaforge/nanocobs_v2_workload.py'
QUALIFIER = 'scripts/qualify_nanocobs_v2.py'
TEST = 'tests/test_nanocobs_v2_workload.py'
CONTRACT = 'docs/nanocobs-v2-adapter-contract-2026-10-28.md'
PIN = 'benchmarks/nanocobs/SOURCE_PIN.json'
ADAPTER = 'benchmarks/nanocobs/adapter.c'
UPSTREAM_C = 'benchmarks/nanocobs/upstream/cobs.c'
LICENSE = 'benchmarks/nanocobs/upstream/LICENSE'
WORKLOAD = GROUP = 'nanocobs'
REPOSITORY = 'https://github.com/charlesnicholson/nanocobs'
UPSTREAM_COMMIT = '8d47d35ebe81c7caecc2b8954b1355d223ecabcb'
HISTORY = 'results/2026-10-26-lift-selection-corpus/corpus.json'
POOL_SIZE = 30  # Computational cap, never an admission minimum.
PARTITION = dict(g.q.partition_spec(6400, 6528))
NATIVE_LIMITS = dict(bw.NATIVE_LIMITS)
# Only the production TU is compiled into program.s, marked, extracted or lowered.
WORKLOADS = {WORKLOAD: str(c.ROOT / UPSTREAM_C)}
PINNED = {'schema': 'isaforge-workload-source-pin-v1',
 'repository': 'https://github.com/charlesnicholson/nanocobs',
 'commit': '8d47d35ebe81c7caecc2b8954b1355d223ecabcb',
 'files': {'benchmarks/nanocobs/upstream/LICENSE': {'sha256': 'be1ed16b605545037e3922495f3387a1630d0dc5e360905cb01fd9be16ff8f34',
                                                    'git_blob_sha1': '7badcf20c31cb1ba1ed7e9ef5bc0206d976e7238',
                                                    'bytes': 2557},
           'benchmarks/nanocobs/upstream/cobs.c': {'sha256': '7cc86cb168a76e153c202b330824787f6daa1cb7734e9030fc10da8ee1d88aa9',
                                                   'git_blob_sha1': '6de92b6b9c3a787f1a265daf18c21dc9e6ab126b',
                                                   'bytes': 19788},
           'benchmarks/nanocobs/upstream/cobs.h': {'sha256': '9923b13fb8d3f3d7d3000290670fdc099d1cb0af9ff9fe65cac82514842f8745',
                                                   'git_blob_sha1': '3e82d8e6a9ba5e233d7a46713338040f2e5e4aca',
                                                   'bytes': 8823},
           'benchmarks/nanocobs/upstream/tests/cobs_ref.c': {'sha256': '133e8a6844c1c10e2a0ccbd079970dafc0f8adb413f404e105b058fd530984c9',
                                                             'git_blob_sha1': 'e78c9ed022a964e7336f79b12502570af2bea7ce',
                                                             'bytes': 908},
           'benchmarks/nanocobs/upstream/tests/cobs_ref.h': {'sha256': 'e3eab4c6bfd8177e428be14f99823b2486f2873d0bb07dc854664cc037aeb7c9',
                                                             'git_blob_sha1': '0ca75b7f21f3e8269c3be7c1721d89ef43ddd81f',
                                                             'bytes': 2855},
           'benchmarks/nanocobs/upstream/tests/qemu/probe.c': {'sha256': '8a85a901a409049ba3b73e0488c5ce32c3aef04d23ee103dfb0fefcad32b93c4',
                                                               'git_blob_sha1': '41a8763a13d8f9d6a40b7b0f8dd118534187775c',
                                                               'bytes': 4001}},
 'adapter_sha256': '288871f8107c222ae5c2746caa0b1c49233cb204ae8f10834d1a4e80e76b819d',
 'fixed_cases': 8215,
 'common_mode_limitation': 'Scalar reference includes the same pinned cobs.c with renamed symbols '
                           'and SWAR disabled; differential agreement cannot exclude shared source '
                           'bugs.'}
FILE_BINDINGS = {name: (v['sha256'], v['git_blob_sha1'], v['bytes'])
                 for name, v in PINNED['files'].items()}
ADAPTER_SHA256 = '288871f8107c222ae5c2746caa0b1c49233cb204ae8f10834d1a4e80e76b819d'
COMPILER_FLAGS = [*g.q.bounded.compact.FLAGS, '-DCOBS_SWAR_WORD_BITS=32']
PROTOCOL = dict(schema='isaforge-nanocobs-v2', workload_group=GROUP,
    upstream_suite='nanocobs original QEMU differential probe',
    upstream_repository=REPOSITORY, upstream_commit=UPSTREAM_COMMIT,
    pool_cap=POOL_SIZE, minimum_legal_candidates=1, fixed_cases=8215,
    admission_rule='Any nonempty calibrated relocation-safe pool under the existing four-operation extractor qualifies; benefit and occurrence counts are descriptive only.',
    technical_calibration_limit='Existing public latency feature API requires calibrated source instruction latencies. Unsupported latency formulas remain excluded; this is a disclosed runtime limitation, not a benefit threshold.',
    unchanged_upstream_algorithm_and_fixed_input=True,
    eligible_translation_unit=UPSTREAM_C,
    fixed_translation_units=['adapter.c', 'upstream/tests/cobs_ref.c'],
    correctness='Original full probe returns zero with failed == 0 and passed == 8215.',
    correctness_limitation=PINNED['common_mode_limitation'],
    library_runtime='Existing byte memcpy in hardware/embench_memory.c retained unchanged.',
    timing_limitation='Complete original probe including scalar reference and checker is timed; only production cobs.c can be rewritten.',
    compiler_flags=COMPILER_FLAGS, isa='rv32i_zicsr', abi='ilp32', optimization='-Os',
    clock_mhz=12, route_seeds=[1,2,3], memory_partition=PARTITION,
    candidate_dispatch_enabled=False, target_candidate_attempts=0,
    family_status='Formula-family overlap must be audited before independence claims.')

PUBLIC = evidence._public
GUARDED_SOURCE = g.SOURCE
AUTHENTICATION_SOURCES = tuple(g.AUTHENTICATION_SOURCES)
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, TEST, CONTRACT, PIN, ADAPTER, *FILE_BINDINGS,
    LICENSE, HISTORY, GUARDED_SOURCE, *AUTHENTICATION_SOURCES,
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
    'hardware/checked_sim.cpp', 'scripts/reproduce_codesign.py',
    'scripts/qualify_opportunity_sources.py',
)))


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def source_record():
    pin = json.loads((c.ROOT / PIN).read_text())
    c.require(pin == PINNED and pin['commit'] == UPSTREAM_COMMIT and
              pin['adapter_sha256'] == ADAPTER_SHA256,
              'Pinned nanocobs source manifest differs')
    for name, (sha, blob, size) in FILE_BINDINGS.items():
        raw = (c.ROOT / name).read_bytes()
        c.require(c.sha(c.ROOT / name) == sha and _git_blob_sha1(raw) == blob and
                  len(raw) == size, 'Pinned nanocobs upstream bytes differ: ' + name)
    c.require(c.sha(c.ROOT / ADAPTER) == ADAPTER_SHA256,
              'Pinned nanocobs adapter differs')
    return pin


@contextmanager
def registration():
    q = g.q
    bounded = q.bounded
    campaign = bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
                q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE,
                campaign.POOL_SIZE, evidence._public, bounded.compact.FLAGS,
                g.partition.extract_pool, g.authenticate_discovery, g.POOL_RULE, g.audit)
    g.SOURCE = SOURCE
    g.WORKLOADS = dict(WORKLOADS)
    g.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    q.WORKLOADS = dict(WORKLOADS)
    q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    bounded.compact.FLAGS = list(COMPILER_FLAGS)
    g.partition.extract_pool = variable_extract_pool
    g.authenticate_discovery = authenticate_discovery
    g.POOL_RULE = VARIABLE_POOL_RULE
    g.audit = audit
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.WORKLOADS, q.POOL_SIZE, bounded.POOL_SIZE,
         campaign.POOL_SIZE, evidence._public, bounded.compact.FLAGS,
                g.partition.extract_pool, g.authenticate_discovery, g.POOL_RULE, g.audit) = previous


def check_plan(plan):
    c.require(plan.get('workload') == WORKLOAD and
              plan.get('pool_size') == POOL_SIZE and
              plan.get('memory_partition') == PARTITION and
              plan.get('compiler_flags') == list(PROTOCOL['compiler_flags']),
              'Different nanocobs workload/compiler/memory/pool contract')
    c.require(plan.get('upstream') == source_record() and
              plan.get('nanocobs_protocol') == PROTOCOL,
              'Pinned nanocobs source/protocol differs')
    c.require(plan.get('inputs', {}).get('program.c') == FILE_BINDINGS[UPSTREAM_C][0] and
              plan.get('inputs', {}).get('adapter.c') == ADAPTER_SHA256,
              'nanocobs adapter/algorithm input differs')
    for name in GATE_SOURCES:
        c.require(plan.get('source_bindings', {}).get(name) == c.sha(c.ROOT / name),
                  'nanocobs source/protocol binding differs: ' + name)
    c.require(c.digest({key: value for key, value in plan.items()
                        if key != 'context_id'}) == plan.get('context_id'),
              'Invalid nanocobs context identity')


def validate_inputs(root):
    root = Path(root)
    plan = c.unseal(root / 'plan.json')
    check_plan(plan)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root / 'inputs' / name) == digest,
                  'Bound nanocobs input differs: ' + name)
    c.require((root / 'inputs/embench_firmware.c').read_bytes() ==
              (c.ROOT / 'hardware/embench_firmware.c').read_bytes(),
              'Generic freestanding harness changed')
    for name, (sha, _, _) in FILE_BINDINGS.items():
        relative = Path(name).relative_to('benchmarks/nanocobs')
        c.require(plan['inputs'].get(relative.as_posix()) == sha,
                  'Pinned nanocobs linked input differs: ' + name)
    c.require(plan['inputs'].get('cobs.h') == FILE_BINDINGS[
        'benchmarks/nanocobs/upstream/cobs.h'][0], 'Production header differs')
    return plan


def prepare(reference, output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh nanocobs qualification root required')
    upstream = source_record()
    history = c.unseal(c.ROOT / HISTORY)
    prior_groups = {row.get('workload_group') for row in history.get('rows', [])}
    c.require(GROUP not in prior_groups,
              'nanocobs workload group already exists in historical corpus')
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION['program_limit'],
            stack_floor=PARTITION['stack_floor'])
    plan.pop('context_id')
    inputs = output / 'inputs'
    shutil.copytree(c.ROOT / 'benchmarks/nanocobs/upstream', inputs / 'upstream')
    shutil.copyfile(c.ROOT / ADAPTER, inputs / 'adapter.c')
    shutil.copyfile(c.ROOT / 'benchmarks/nanocobs/upstream/cobs.h', inputs / 'cobs.h')
    plan['inputs'] = {path.relative_to(inputs).as_posix(): c.sha(path)
                      for path in sorted(inputs.rglob('*')) if path.is_file()}
    plan.update(upstream=upstream, workload_group=GROUP, computational_pool_cap=POOL_SIZE,
        pool_size_semantics='Legacy plan pool_size is the immutable computational cap; discovery actual_pool_size is independently authenticated.',
        qualification_order=[WORKLOAD],
        qualification_rule='One pinned original 8215-case differential probe on guarded RV32I/Zicsr PicoRV32; require at least one legal executable formula, capped only for compute; no benefit or occurrence minima. No candidate labels, retries, or gate changes.',
        runtime_support=PROTOCOL['library_runtime'],
        source_family_review=PROTOCOL['family_status'],
        qualification_context='Original shared 8-KiB RAM split: 6400-byte program/data limit, 6528-byte stack floor, RV32I/ILP32 -Os, same PicoRV32/PCPI and 12-MHz three-route evaluator.',
        nanocobs_protocol=PROTOCOL,
        historical_corpus_sha256=c.sha(c.ROOT / HISTORY))
    for name in GATE_SOURCES:
        plan['source_bindings'][name] = c.sha(c.ROOT / name)
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan['context_id'] = c.digest(plan)
    c.seal(output / 'plan.json', plan)
    validate_inputs(output)
    return plan


def effective_policy_budget(requested_budget, actual_pool_size):
    """Same requested B across pools; fewer than B choices means min(B, N)."""
    c.require(type(requested_budget) is int and requested_budget >= 1 and
              type(actual_pool_size) is int and actual_pool_size >= 0,
              'Positive requested budget and nonnegative actual pool size required')
    return min(requested_budget, actual_pool_size)


class NoLegalCandidates(ValueError):
    def __init__(self, extraction):
        super().__init__('No legal calibrated executable candidates')
        self.extraction = extraction


def variable_extract_pool(program, profile, site_map, pool_cap, calibration):
    c.require(type(pool_cap) is int and 1 <= pool_cap <= 30, 'Invalid computational pool cap')
    # The original extractor returns its complete executable list regardless of
    # requested shortlist size. Consume that complete list, then guard/calibrate.
    result = g._guarded_extract(program, profile, site_map, 1)
    table = latency_features.latency_table(calibration)
    eligible, excluded = [], []
    for candidate in result['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    latency_features.instruction_latency(program[int(pc, 16)], table)
        except ValueError:
            excluded.append(candidate['formula'])
        else:
            eligible.append(candidate)
    if not eligible:
        raise NoLegalCandidates(dict(result, pool=[], actual_pool_size=0,
            eligible_formula_count=0, excluded_uncalibrated_formulas=excluded,
            computational_pool_cap=pool_cap))
    count = min(pool_cap, len(eligible))
    indices = (list(range(count)) if len(eligible) <= pool_cap else
               [round(i * (len(eligible)-1)/(count-1)) for i in range(count)]
               if count > 1 else [0])
    result.update(pool=[eligible[i] for i in indices], pool_rule=VARIABLE_POOL_RULE,
        eligible_formula_count=len(eligible), excluded_uncalibrated_formulas=excluded,
        selected_rank_indices=indices, actual_pool_size=count,
        computational_pool_cap=pool_cap)
    return result


def authenticate_discovery(root):
    """Reconstruct the full guarded pool; never open candidate measurements."""
    root=Path(root).resolve();plan=g.authenticate_plan(root)
    found=w.verify_cache(root/'discovery','discovery.json')
    c.require(found.get('context_id')==plan['context_id'] and found.get('workload')==plan['workload'],
              'Guarded discovery context differs')
    image=(root/found['baseline_image']).resolve()
    c.require(image.is_relative_to(root/'discovery') and image.parent.name=='marked',
              'Baseline image outside guarded discovery')
    folder=image.parent.parent
    marked,sites=lowering.mark_assembly((folder/'program.s').read_text())
    c.require(marked==(folder/'marked.S').read_text(),'Original marked assembly changed')
    c.require(c.sha(image)==c.sha(folder/'original/firmware.hex'),'Marked baseline changed')
    site_map=lowering.map_sites(sites,(image.parent/'symbols.txt').read_text())
    program=lowering.read_program((image.parent/'disassembly.txt').read_text())
    profile_path=(root/found['profile']).resolve()
    c.require(profile_path==folder/'profile/simulation.json','Profile outside guarded discovery')
    profile=c.read(profile_path)
    spec=plan['memory_partition']
    c.require(found.get('memory_check')==q.validate_memory(profile,spec=spec),
              'Discovery memory observations differ')
    c.require(found.get('baseline_performance')==w.validate_execution(profile),
              'Discovery baseline performance differs')
    derived=variable_extract_pool(program,profile,site_map,plan['pool_size'],
                         c.read(root/'inputs/latency-calibration.json'))
    for key,value in derived.items():
        if key not in ('pool','executable_candidates'):
            c.require(found.get(key)==value,'Guarded discovery metadata differs: '+key)
    c.require(1 <= len(found['pool']) == len(derived['pool']) <= plan['pool_size'] and
              len(found['executable_candidates'])==len(derived['executable_candidates']),
              'Guarded candidate count differs')
    for expected,recorded in zip(derived['executable_candidates'],found['executable_candidates']):
        c.require(all(recorded.get(k)==v for k,v in expected.items()),'Guarded full candidate list differs')
    for expected,candidate in zip(derived['pool'],found['pool']):
        c.require(all(candidate.get(k)==v for k,v in expected.items()),'Guarded shortlist differs')
        c.require(candidate['candidate_id']==c.digest([plan['context_id'],candidate['formula']]),
                  'Guarded candidate identity differs')
        guard.require_relocation_free(candidate,sites)
        c.require(lowering.verify_lowering(candidate,program,found['block_starts'])==candidate['lowering_check'],
                  'Guarded lowering check differs')
        for occurrence in candidate['occurrences']:
            c.require([site_map[int(pc,16)]['site'] for pc in occurrence['pcs']]==occurrence['sites'],
                      'Guarded source-PC map differs')
        lowered=(root/candidate['assembly']).resolve()
        c.require(lowered.is_relative_to(folder) and lowered.read_text()==lowering.lower(marked,candidate) and
                  c.sha(lowered)==candidate['assembly_sha256'],'Guarded lowered assembly differs')
    return found


def require_zero_candidates(root):
    root = Path(root)
    c.require(not list((root / 'attempt-ledger').glob('candidate_*')) and
              not list((root / 'measurements').glob('candidate_*')),
              'Qualification requires zero candidate attempts')


def public_projection(root, plan, discovery, baseline, calibration):
    count = len(discovery['pool'])
    c.require(1 <= count <= plan['pool_size'], 'Nonempty pool within computational cap required')
    rows = PUBLIC(root, dict(plan, pool_size=count), discovery, baseline, calibration)
    for row in rows:
        c.require(row['benchmark'] == 'embench-' + WORKLOAD + ':' + plan['context_id'],
                  'Unexpected nanocobs public projection identity')
        row['benchmark'] = GROUP + ':' + plan['context_id']
    return rows


def discovery_public(root):
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {'performance': discovery['baseline_performance']}, calibration)
    return budget.public_rows(rows)


def source_family_audit(public):
    history = c.unseal(c.ROOT / HISTORY)
    c.require(len(history.get('rows', [])) == 122 and
              len({row.get('workload_group') for row in history['rows']}) == 14,
              'Expected authenticated 122-label/14-group family history')
    historic = {}
    for row in history['rows']:
        key = row.get('candidate_family') or family(row['formula'])
        historic.setdefault(key, []).append(row['formula'])
    target = {}
    for row in public:
        key = family(row['formula'])
        target.setdefault(key, []).append(row['candidate_id'])
    overlap = sorted(set(target) & set(historic))
    novel = sorted(set(target) - set(historic))
    return dict(schema=PROTOCOL['schema'] + '-source-family-audit',
        historical_corpus_sha256=c.sha(c.ROOT / HISTORY),
        historical_workload_groups=14, historical_verified_labels=122,
        target_candidate_count=len(public),
        target_operation_family_count=len(target),
        historical_operation_family_count=len(historic),
        overlapping_operation_families=overlap,
        novel_operation_families=novel,
        overlap_candidate_ids=sorted(identity for key in overlap
            for identity in target[key]),
        novel_candidate_ids=sorted(identity for key in novel
            for identity in target[key]),
        interpretation='Descriptive overlap against the named historical 122-label/14-group corpus only. Recent tiny-regex, Sudoku and Ascon public pools are outside this audit and must also be checked before an independence claim; family-held-out evaluation must exclude every overlapping target operation family.')


def opportunity_gate(public):
    # No projected-benefit or occurrence-count admission thresholds.
    passing = [row['candidate_id'] for row in public]
    return dict(schema=PROTOCOL['schema'] + '-gate', protocol=PROTOCOL,
        passed=bool(public), qualifying_candidate_ids=passing,
        actual_pool_size=len(public), computational_pool_cap=POOL_SIZE,
        source_family_audit=source_family_audit(public), public_digest=c.digest(public),
        maximum_public_cycle_reduction=max((
            row['latency_features']['estimated_cycle_reduction'] for row in public), default=None),
        maximum_timed_replacements=max((budget.occurrence_count(row) for row in public), default=None),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def opportunity(root):
    root = Path(root)
    c.require(not (root / 'opportunity.json').exists(),
              'Preserve prior nanocobs opportunity record')
    result = opportunity_gate(discovery_public(root))
    c.seal(root / 'opportunity.json', result)
    c.require(result['passed'], 'Unchanged nanocobs opportunity gate rejected workload')
    return result


def check_opportunity(root):
    recorded = c.unseal(Path(root) / 'opportunity.json')
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived['passed'],
              'Accepted unchanged nanocobs opportunity gate required')
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def compile_program(self, folder, source, expected_sites=0, *, fixture=False):
        folder.mkdir(parents=True)
        elf, binary = folder / 'firmware.elf', folder / 'firmware.bin'
        files = [source] if fixture else [self.inputs / 'soc_start.S', self.inputs / 'embench_firmware.c',
                self.inputs / 'embench_memory.c', source, self.inputs / 'beebsc.c', self.inputs / 'adapter.c',
                self.inputs / 'upstream/tests/cobs_ref.c']
        self.runner.run([self.tools['gcc'], *self.plan['compiler_flags'], '-I', self.inputs,
                         '-Wl,--no-relax', '-Wl,--gc-sections', '-Wl,-T,' + str(self.inputs / 'soc_link.ld'),
                         *files, '-lgcc', '-o', elf], folder / 'compile.log')
        self.runner.run([self.tools['objcopy'], '-O', 'binary', elf, binary], folder / 'objcopy.log')
        disassembly = self.runner.run([self.tools['objdump'], '-d', elf], folder / 'disassembly.txt')
        isa = g.q.bounded.validate_isa(disassembly)
        c.require(isa['custom_static_sites'] == expected_sites, 'Unexpected custom instruction sites')
        self.runner.run([self.tools['nm'], '-n', elf], folder / 'symbols.txt')
        image = folder / 'firmware.hex'
        end, start = g.q.memory_symbols(image, self.partition)
        image.write_text(g.q.memory_image(binary.read_bytes(), self.partition))
        c.write(folder / 'validation.json', dict(isa=isa, program_and_bss_end=end,
                writable_start=start, stack_floor=self.partition['stack_floor'],
                guard_bytes=self.partition['stack_floor'] - end))
        return image

    def discover(self):
        require_zero_candidates(self.root)
        try:
            with registration():
                result = super().discover()
        except NoLegalCandidates as error:
            c.seal(self.root / 'discovery-rejection.json', dict(
                schema=PROTOCOL['schema'] + '-discovery-rejection',
                context_id=self.plan['context_id'], passed=False,
                source_level_rejection=True, target_candidate_attempts=0,
                reason=str(error), extraction=error.extraction,
                plan_sha256=c.sha(self.root / 'plan.json')))
            raise
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == 'baseline',
                  'Candidate dispatch disabled during nanocobs qualification')
        require_zero_candidates(self.root)
        check_opportunity(self.root)
        with registration():
            result = super().measure(name)
        require_zero_candidates(self.root)
        return result


def baseline_public(root):
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = g.baseline_public(root)
    context['workload_group'] = before['workload'] = GROUP
    context['context_transfer'] = 'Pinned full nanocobs differential probe on guarded PicoRV32.'
    c.require(opportunity_gate(rows) == c.unseal(Path(root) / 'opportunity.json'),
              'Discovery and routed-baseline public projections differ')
    return rows, context, before


def audit(root):
    """Authenticate the variable pool and full baseline through existing guards.

    The legacy workload_audit demands cap == actual size. Its baseline checks
    are supplied here by authenticate_baseline and independent pool rederivation,
    without mutating the sealed plan or weakening either check.
    """
    rows, context, before = baseline_public(root)
    attempt = g.attempts.read_attempt(root, 'baseline')
    c.require(attempt['status'] == 'success', 'Successful baseline ledger required')
    return dict(schema=PROTOCOL['schema'] + '-baseline-audit',
        context_id=context['context_id'], actual_pool_size=len(rows),
        computational_pool_cap=POOL_SIZE, baseline=before,
        target_candidate_attempts=0, baseline_ledger_status=attempt['status'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'discover', 'opportunity',
        'baseline', 'public', 'freeze', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        c.require(args.reference_root is not None, '--reference-root required')
        result = prepare(args.reference_root, args.root)
    elif args.command == 'opportunity':
        result = opportunity(args.root)
    elif args.command == 'public':
        rows, context, before = baseline_public(args.root)
        for name, value in [('public.json', rows), ('context.json', context),
                            ('before.json', before)]:
            c.seal(args.root / name, value)
        result = dict(context_id=context['context_id'], candidates=len(rows))
    elif args.command == 'audit':
        result = audit(args.root)
    else:
        evaluator = Evaluator(args.root)
        try:
            if args.command == 'freeze':
                check_opportunity(args.root)
                with registration():
                    result = g.attempts.freeze_pool(evaluator, scope='dataset-expansion')
            elif args.command == 'baseline':
                result = evaluator.measure('baseline')
            else:
                result = evaluator.discover()
        finally:
            evaluator.runner.lock.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
