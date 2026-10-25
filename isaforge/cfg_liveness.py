"""Opt-in static RV32 liveness coverage; no native runner or legacy mutation.

All static successors participate, including unobserved branches and backedges.
Unknown effects, calls, returns, indirect jumps and absent successors have an
all-register-live boundary. No ABI or dynamic-path deadness is assumed. This
adds only a proof of dead temporary outputs to the existing dataflow rules.

Callers still authenticate the original assembly/linked-PC mapping, ISA,
firmware and profile. These certificates authenticate those supplied inputs,
not their acquisition. Randomized block equivalence is not a universal proof.
Extraction additionally requires closed static entries. Its optional canonical
return support assumes ordinary compiler-generated RV32 C ABI control flow;
it is NOT an arbitrary-binary control proof. That caller option defaults false
and is rechecked independently of certificate contents. Only exact adjacent
raw AUIPC x1/JALR x1,x1 direct calls may be resolved, after a global second-word
entry check. Four exact read-only counter CSRRS forms are opaque non-control
barriers. A separate default-false firmware_trap_exit option permits only exact
EBREAK as a terminal exit under caller-authenticated IRQ-disabled startup/SoC/
simulator termination semantics; it is not generic trap support. Other indirect
control, unknown instructions and absent successors refuse extraction globally.
Nothing here qualifies a workload, selects a pool or authorizes measurement.
"""
from __future__ import annotations

from collections import Counter
import copy
import random

from . import assembly_lowering as a, codesign as c, relocation_guard as guard

SOURCE = 'isaforge/cfg_liveness.py'
SOURCES = (SOURCE, 'isaforge/assembly_lowering.py', 'src/candidates.py',
           'src/tracing.py', 'src/verify_candidate_fusions.py', 'isaforge/rtl.py',
           'isaforge/features.py', 'isaforge/relocation_guard.py', 'isaforge/codesign.py')
SCHEMA = 'isaforge-rv32-static-cfg-liveness-v1'
EXTRACTION_SCHEMA = 'isaforge-rv32-liveness-extraction-v1'
VERIFICATION_SCHEMA = 'isaforge-rv32-liveness-projected-equivalence-v1'
REGISTERS = frozenset(range(1, 32))
REGISTER_OPS = frozenset('add sub and or xor sll srl sra slt sltu'.split())
IMMEDIATE_OPS = frozenset('addi andi ori xori slli srli srai slti sltiu'.split())
PURE = REGISTER_OPS | IMMEDIATE_OPS | {'lui'}
LOADS = frozenset('lb lh lw lbu lhu'.split())
STORES = frozenset('sb sh sw'.split())
BRANCHES = frozenset('beq bne blt bge bltu bgeu'.split())
KNOWN = PURE | LOADS | STORES | BRANCHES | {'auipc', 'jal', 'jalr'}
POLICY = ('Least fixed point: out=union(successor in), in=uses|(out-defs). '
          'All x1..x31 live at unknown effects, calls, indirect jumps/returns, '
          'missing targets/fallthrough; x0 is always zero. No ABI inference.')
ENTRY_SCOPE = ('Closed direct-control entries only. Explicit compiler_abi_returns '
               'permits canonical jalr x0,x1,0 as an ordinary compiler-generated '
               'RV32 C ABI return, not arbitrary-binary control. No unresolved '
               'indirect jumps/calls; only adjacent raw AUIPC x1/JALR x1,x1 pairs '
               'with globally protected second words resolve. Only exact CSRRS '
               'x0-source cycle/cycleh/instret/instreth reads may be opaque '
               'non-control barriers. Explicit firmware_trap_exit permits exact '
               'EBREAK only as an IRQ-disabled firmware/simulator terminal exit. '
               'No other opaque instruction or absent '
               'successor; no observed-path entry inference.')
MASK = 2**32 - 1
COUNTER_CSRS = frozenset((0xc00, 0xc80, 0xc02, 0xc82))


def _source_bindings():
    return {name: c.sha(c.ROOT / name) for name in SOURCES}


def _validate(program):
    c.require(isinstance(program, dict) and program, 'Nonempty static program required')
    for pc, row in program.items():
        c.require(type(pc) is int and 0 <= pc <= 0xfffffffc and pc % 4 == 0 and
                  isinstance(row, dict) and isinstance(row.get('op'), str), 'Invalid static instruction')
        c.require(all(k in row for k in ('rd', 'rs1', 'rs2', 'imm')), 'Incomplete decoded instruction')
        c.require(all(r is None or type(r) is int and 0 <= r < 32
                      for r in (row['rd'], row['rs1'], row['rs2'])), 'Invalid RV32 register')
        c.require(row['imm'] is None or type(row['imm']) is int, 'Invalid RV32 immediate')
        op, rd, rs1, rs2, imm = (row[k] for k in ('op', 'rd', 'rs1', 'rs2', 'imm'))
        if 'raw' in row:
            c.require(type(row['raw']) is int and 0 <= row['raw'] < 2**32 and
                      a.tracing.decode(row['raw']) == (op, rd, rs1, rs2, imm),
                      'Decoded instruction differs from raw RV32 word')
            # The frozen decoder intentionally has a small grammar. Do not
            # promote its permissive decoding of reserved encodings to proof.
            if op in ('slli', 'srli', 'srai'):
                c.require(row['raw'] >> 25 == (32 if op == 'srai' else 0),
                          'Reserved RV32 shift encoding')
            if op == 'jalr':
                c.require((row['raw'] >> 12) & 7 == 0, 'Reserved RV32 JALR encoding')
        if op not in KNOWN:
            continue  # Unsupported effects are opaque, never inferred from fields.
        if op in REGISTER_OPS:
            valid = all(type(r) is int for r in (rd, rs1, rs2)) and imm is None
        elif op in IMMEDIATE_OPS | LOADS | {'jalr'}:
            valid = type(rd) is int and type(rs1) is int and rs2 is None and type(imm) is int
            if valid:
                valid = 0 <= imm < 32 if op in ('slli', 'srli', 'srai') else -2048 <= imm < 2048
        elif op in {'lui', 'auipc'}:
            valid = type(rd) is int and rs1 is None and rs2 is None and type(imm) is int
            if valid:
                valid = -(2**31) <= imm < 2**31 and imm % 4096 == 0
        elif op == 'jal':
            valid = type(rd) is int and rs1 is None and rs2 is None and type(imm) is int
            if valid:
                valid = -(2**20) <= imm < 2**20 and imm % 2 == 0
        else:
            valid = rd is None and type(rs1) is int and type(rs2) is int and type(imm) is int
            if valid:
                valid = (-4096 <= imm < 4096 and imm % 2 == 0) if op in BRANCHES else -2048 <= imm < 2048
        c.require(valid, 'Malformed supported RV32 instruction')


def _counter_read(row):
    raw = row.get('raw')
    if (row['op'] == 'unknown' and type(raw) is int and
            raw & 0x000ff07f == 0x00002073 and raw >> 20 in COUNTER_CSRS):
        return dict(raw=raw, csr=raw >> 20, rd=(raw >> 7) & 31)
    return None


def _entries(program):
    """Recognize exact direct-call pairs, then check ALL static entry targets.

    Collect every proposed pair target before deciding any pair's acceptance:
    a later pair may jump into an earlier pair's second word. No register value
    propagation, arbitrary JALR resolution or trace-based target closure occurs.
    """
    protected = {min(program)}; proposed = {}
    for pc, row in sorted(program.items()):
        if row['op'] in BRANCHES | {'jal'}:
            protected.update(((pc + row['imm']) & MASK, (pc + 4) & MASK))
        elif row['op'] == 'jalr':
            protected.add((pc + 4) & MASK)
            prev_pc = (pc - 4) & MASK; prev = program.get(prev_pc)
            if (row['rd'] == row['rs1'] == 1 and prev is not None and
                    prev['op'] == 'auipc' and prev['rd'] == 1 and
                    type(prev.get('raw')) is int and type(row.get('raw')) is int):
                target = ((prev_pc + prev['imm'] + row['imm']) & MASK) & ~1
                if target % 4 == 0 and target in program:
                    proposed[pc] = dict(auipc_pc=prev_pc, jalr_pc=pc, target=target,
                                        continuation=(pc + 4) & MASK,
                                        auipc_raw=prev['raw'], jalr_raw=row['raw'])
                    protected.add(target)
    accepted = {pc: proof for pc, proof in proposed.items() if pc not in protected}
    bypassed = sorted(set(proposed) - set(accepted))
    return protected, accepted, bypassed


def analyze(program, *, compiler_abi_returns=False, firmware_trap_exit=False):
    """Certify a whole static decoded program, independently of trace counts."""
    _validate(program)
    c.require(type(compiler_abi_returns) is bool, 'Explicit Boolean compiler ABI return option required')
    c.require(type(firmware_trap_exit) is bool, 'Explicit Boolean firmware trap-exit option required')
    nodes = {}
    protected, calls, bypassed = _entries(program)
    unsupported = []; counters = []; trap_exits = []
    for pc, row in sorted(program.items()):
        op = row['op']; boundary = []
        uses = {r for r in (row['rs1'], row['rs2']) if r}
        defs = {row['rd']} if row['rd'] else set()
        if op not in KNOWN:
            counter = _counter_read(row)
            trap = row.get('raw') == 0x00100073 and op == 'unknown'
            boundary.append('firmware_trap_exit' if trap and firmware_trap_exit else
                            'readonly_counter_barrier' if counter else 'opaque_effect')
            targets = [] if trap and firmware_trap_exit else [(pc + 4) & MASK]
            if trap and firmware_trap_exit:
                trap_exits.append(dict(pc=pc, raw=row['raw']))
            elif counter:
                counters.append(dict(pc=pc, **counter))
            else:
                unsupported.append(dict(pc=pc, reason='firmware_trap_exit_assumption_required'
                                        if trap else 'opaque_instruction'))
            protected.update((pc, (pc + 4) & MASK))
        elif op == 'jalr':
            boundary.append('resolved_direct_call' if pc in calls else 'indirect_call_or_return')
            targets = [calls[pc]['target'], (pc + 4) & MASK] if pc in calls else \
                [(pc + 4) & MASK] if row['rd'] else []
            canonical = (row['rd'], row['rs1'], row['imm']) == (0, 1, 0)
            if pc not in calls and (not canonical or not compiler_abi_returns):
                reason = 'entry_into_call_second_word' if pc in bypassed else \
                    'unresolved_indirect_control' if not canonical else 'compiler_abi_return_assumption_required'
                unsupported.append(dict(pc=pc, reason=reason))
        elif op == 'jal':
            targets = [(pc + row['imm']) & MASK]
            if row['rd']:
                boundary.append('call'); targets.append((pc + 4) & MASK)
        elif op in BRANCHES:
            targets = [(pc + row['imm']) & MASK, (pc + 4) & MASK]
        else:
            targets = [(pc + 4) & MASK]
        absent = sorted({t for t in targets if t not in program})
        if absent:
            boundary.append('missing_static_successor')
            unsupported.append(dict(pc=pc, reason='missing_static_successor'))
        if boundary:
            uses, defs = set(REGISTERS), set()
        nodes[pc] = dict(pc=pc, successors=sorted({t for t in targets if t in program}),
                         absent_successors=absent, boundary=boundary,
                         uses=sorted(uses), defs=sorted(defs))
    live_in = {pc: set() for pc in nodes}; live_out = {pc: set() for pc in nodes}
    iterations = 0
    while True:
        iterations += 1; changed = False
        for pc in reversed(list(nodes)):
            node = nodes[pc]
            out = set(REGISTERS) if node['boundary'] else set()
            for target in node['successors']:
                out.update(live_in[target])
            incoming = set(node['uses']) | (out - set(node['defs']))
            if out != live_out[pc] or incoming != live_in[pc]:
                live_out[pc], live_in[pc] = out, incoming; changed = True
        if not changed:
            break
    for pc, node in nodes.items():
        node.update(live_in=sorted(live_in[pc]), live_out=sorted(live_out[pc]))
    payload = dict(schema=SCHEMA, policy=POLICY, source_bindings=_source_bindings(),
                   program_sha256=c.digest([[pc, program[pc]] for pc in sorted(program)]),
                   entry_model=dict(compiler_abi_returns=compiler_abi_returns, scope=ENTRY_SCOPE,
                                    firmware_trap_exit=firmware_trap_exit,
                                    protected_entries=sorted(protected & set(program)),
                                    resolved_direct_calls=[calls[pc] for pc in sorted(calls)],
                                    readonly_counter_reads=counters,
                                    firmware_trap_exits=trap_exits,
                                    extraction_supported=not unsupported, unsupported=unsupported),
                   nodes=list(nodes.values()), fixed_point_iterations=iterations)
    return {**payload, 'certificate_sha256': c.digest(payload)}


def authenticate_certificate(program, certificate, *, compiler_abi_returns=False, firmware_trap_exit=False):
    """Recompute CFG, least fixed point, complete program and source bindings."""
    derived = analyze(program, compiler_abi_returns=compiler_abi_returns, firmware_trap_exit=firmware_trap_exit)
    c.require(certificate == derived, 'Static CFG/liveness certificate differs from rederivation')
    return derived


def _inputs(program, profile, site_map):
    c.require(isinstance(site_map, dict) and site_map and set(site_map) <= set(program),
              'Original source/PC map required')
    sites = list(site_map.values())
    # Validate uniqueness and statement provenance, including unused map entries.
    guard._sites(sites)
    c.require(isinstance(profile, dict) and isinstance(profile.get('region_counts'), dict) and
              isinstance(profile.get('total_counts'), dict) and
              isinstance(profile.get('block_starts'), list), 'Complete baseline profile required')
    counts = []
    for key in ('region_counts', 'total_counts'):
        table = profile[key]
        c.require(all(isinstance(pc, str) and pc.isdecimal() and str(int(pc)) == pc and
                      type(n) is int and n >= 0 for pc, n in table.items()), 'Invalid profile counts')
        converted = Counter({int(pc): n for pc, n in table.items()})
        c.require(set(converted) <= set(program), 'Profile address absent from static program')
        counts.append(converted)
    runs, total = counts
    c.require(all(total[pc] >= n for pc, n in runs.items()), 'Timed count exceeds total count')
    c.require(all(type(pc) is int and pc % 4 == 0 and pc >= 0 for pc in profile['block_starts']),
              'Invalid profile block start')
    words = profile.get('words')
    c.require(isinstance(words, list) and len(words) >= 4 and type(words[3]) is int and
              sum(runs.values()) + 1 == words[3] and sum(runs.values()) > 0, 'Profile/counter mismatch')
    return runs, total


def extract(program, profile, site_map, pool_size=6, *, certificate=None, compiler_abi_returns=False,
            firmware_trap_exit=False):
    """Legacy-shaped extraction before the existing relocation/calibration chain.

    Existing graph enumeration, contribution/input/output rules, formula naming,
    feature extraction and deterministic overlap handling remain in use. Only
    the conservative last-write output set is refined by liveness. The returned
    provisional pool has the legacy top-savings rule; the caller still applies
    the unchanged relocation/calibration/stratification chain. This function
    does not apply relocation filtering. No shared globals or inputs mutate.
    """
    c.require(type(pool_size) is int and 1 <= pool_size <= 30, 'Invalid pool size')
    certificate = analyze(program, compiler_abi_returns=compiler_abi_returns,
                          firmware_trap_exit=firmware_trap_exit) if certificate is None else \
        authenticate_certificate(program, certificate, compiler_abi_returns=compiler_abi_returns,
                                 firmware_trap_exit=firmware_trap_exit)
    c.require(certificate['entry_model']['extraction_supported'],
              'Unsupported static entry model: ' + str(certificate['entry_model']['unsupported']))
    runs, total = _inputs(program, profile, site_map)
    nodes = {n['pc']: n for n in certificate['nodes']}
    starts = set(profile['block_starts']) | set(certificate['entry_model']['protected_entries'])
    for pc, row in program.items():
        if row['op'] in a.discovery.JUMPS or row['op'] not in KNOWN:
            starts.add(pc + 4)
        if row['op'] not in KNOWN:
            starts.add(pc)
    blocks = a.discovery.findBlocks(program, starts)
    c.require(all(len({runs[pc] for pc in block}) == 1 for block in blocks), 'Mixed block counts')
    patterns = {}; rejected = Counter(); legal_occurrences = 0
    binding = dict(certificate_sha256=certificate['certificate_sha256'],
                   profile_sha256=c.digest(profile),
                   source_map_sha256=c.digest([[pc, site_map[pc]] for pc in sorted(site_map)]))
    for block in blocks:
        if not runs[block[0]]:
            continue
        sources = a.discovery.findSources(block, program)
        last = {i for i in a.discovery.findLastWrites(block, program)
                if program[block[i]]['rd'] in nodes[block[-1]]['live_out']}
        potential = a.discovery.findPotentialCandidates(block, program, a.discovery.findArrows(block, program), 4)
        for members in sorted(potential, key=lambda m: tuple(sorted(m))):
            if any(program[block[i]]['op'] not in PURE for i in members):
                continue
            if not a.discovery.followsRules(members, block, program, sources, last):
                continue
            formula = a.discovery.describe(members, block, program, sources)
            patterns.setdefault(formula, [])
            legal_occurrences += 1
            pcs = [block[i] for i in sorted(members)]
            if not all(pc in site_map for pc in pcs):
                rejected['not_whole_source_statements'] += 1; continue
            if any(program[pc]['op'] not in KNOWN for pc in block):
                rejected['opaque_block'] += 1; continue
            patterns[formula].append(dict(blockStart=f'0x{block[0]:08x}',
                pcs=[f'0x{pc:08x}' for pc in pcs], blockRuns=runs[block[0]], size=len(pcs),
                symbols=sorted({site_map[pc].get('function') or program[pc].get('symbol')
                                for pc in pcs} - {None}),
                sites=[site_map[pc]['site'] for pc in pcs],
                inputs=a.inputs_for(members, block, program), output=program[pcs[-1]]['rd']))
    executable = []
    for formula, occurrences in patterns.items():
        used = set(); chosen = []
        for occurrence in sorted(occurrences, key=lambda o: (-o['size'], o['pcs'])):
            if used.isdisjoint(occurrence['pcs']):
                chosen.append(occurrence); used.update(occurrence['pcs'])
        if not chosen:
            continue
        size = min(o['size'] for o in chosen); count = sum(o['blockRuns'] for o in chosen)
        feature_row = dict(formula=formula, size=size, runs=count, places=len(chosen),
                           saved=(size - 1) * count, savedPercent=100 * (size - 1) * count / sum(runs.values()))
        executable.append(dict(formula=formula, occurrences=chosen, features=a.extract_features(feature_row),
            expected_instruction_reduction=sum((o['size'] - 1) * o['blockRuns'] for o in chosen),
            region_custom_instructions=count,
            total_custom_instructions=sum(total[int(o['pcs'][-1], 16)] for o in chosen),
            liveness_binding=copy.deepcopy(binding)))
    executable.sort(key=lambda r: (-r['expected_instruction_reduction'], r['formula']))
    for index, row in enumerate(executable):
        row['name'] = f'candidate_{index:02d}'
    return dict(schema=EXTRACTION_SCHEMA, certificate=certificate, **binding,
                requested_pool_size=pool_size, relocation_filter_applied=False,
                raw_formula_count=len(patterns), legal_occurrence_count=legal_occurrences,
                rejected_occurrences=dict(rejected), block_starts=sorted(starts),
                executable_formula_count=len(executable), source_mapped_formula_count=len(executable),
                pool_rule='Top overlap-safe dynamic instruction savings, then formula; max four operations; explicit static CFG liveness context.',
                pool=executable[:pool_size], executable_candidates=executable)


def authenticate_extraction(program, profile, site_map, extraction, *, compiler_abi_returns=False,
                            firmware_trap_exit=False):
    c.require(isinstance(extraction, dict), 'Liveness extraction required')
    derived = extract(program, profile, site_map, extraction.get('requested_pool_size'),
                      certificate=extraction.get('certificate'), compiler_abi_returns=compiler_abi_returns,
                      firmware_trap_exit=firmware_trap_exit)
    c.require(extraction == derived, 'Liveness extraction differs from rederivation')
    return derived


def verify_lowering(candidate, program, profile, site_map, certificate, *, vectors=64,
                    compiler_abi_returns=False, firmware_trap_exit=False):
    """Explicit projected equivalence after certificate AND candidate rederivation.

    Only eliminated temporary writes proved dead at block exit may differ.
    Every other register (including x0), written memory and branch destination
    must agree. The old full-register verifier is never changed or bypassed for
    an old context; callers must opt in to this distinct schema/context.
    """
    c.require(type(vectors) is int and vectors >= 1, 'Positive equivalence vector count required')
    authenticate_certificate(program, certificate, compiler_abi_returns=compiler_abi_returns,
                             firmware_trap_exit=firmware_trap_exit)
    derived = extract(program, profile, site_map, certificate=certificate, compiler_abi_returns=compiler_abi_returns,
                      firmware_trap_exit=firmware_trap_exit)
    c.require(candidate in derived['executable_candidates'], 'Candidate differs from complete rederivation')
    guard.require_relocation_free(candidate, list(site_map.values()))
    blocks = {b[0]: b for b in a.discovery.findBlocks(program, set(derived['block_starts']))}
    nodes = {n['pc']: n for n in certificate['nodes']}; groups = {}
    for occurrence in candidate['occurrences']:
        block = blocks[int(occurrence['blockStart'], 16)]
        groups.setdefault(block[0], []).append(dict(
            members={block.index(int(pc, 16)) for pc in occurrence['pcs']}, formula=candidate['formula']))
    rng = random.Random(20261025); comparisons = 0; proofs = []
    for start, replacements in sorted(groups.items()):
        block = blocks[start]; live = set(nodes[block[-1]]['live_out'])
        last_writes = a.discovery.findLastWrites(block, program)
        eliminated = {i for r in replacements for i in r['members'] - {max(r['members'])}}
        outputs = {program[block[max(r['members'])]]['rd'] for r in replacements}
        permitted = {program[block[i]]['rd'] for i in eliminated & last_writes}
        permitted -= live | outputs | {0, None}
        proofs.append(dict(block_start=start, exit_pc=block[-1], live_out=sorted(live),
                           permitted_dead_register_differences=sorted(permitted)))
        for _ in range(vectors):
            state = {reg: rng.getrandbits(32) if reg else 0 for reg in range(32)}
            original = a.interpreter.execute(block, program, state.copy(), [])
            fused = a.interpreter.execute(block, program, state.copy(), replacements)
            c.require(original[1:] == fused[1:], 'Fusion changes memory or control')
            c.require(all(original[0][reg] == fused[0][reg] for reg in range(32) if reg not in permitted),
                      'Fusion changes a live or unmodified architectural register')
            comparisons += 1
    return dict(schema=VERIFICATION_SCHEMA, passed=True, candidate_sha256=c.digest(candidate),
                **candidate['liveness_binding'], blocks=proofs, comparisons=comparisons,
                vectors_per_block=vectors,
                scope='Recomputed static liveness plus sampled block equivalence; exact memory/control and all registers except certified dead eliminated temporaries. Not a universal program proof or native qualification.')
