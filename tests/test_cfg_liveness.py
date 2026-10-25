"""Synthetic static CFG/translation fixtures; never compile, fit or measure."""
import copy

import pytest

from isaforge import assembly_lowering as a, cfg_liveness as cfg, codesign as c
from isaforge import relocation_guard as guard


def ins(op, rd=None, rs1=None, rs2=None, imm=None):
    return dict(op=op, rd=rd, rs1=rs1, rs2=rs2, imm=imm, symbol='fixture')


def kill(reg):
    return ins('addi', reg, 0, imm=0)


def ret():
    return ins('jalr', 0, 1, imm=0)


def raw_instruction(word):
    return {**ins(*a.tracing.decode(word)), 'raw': word}


def auipc(upper=0, rd=1):
    return raw_instruction((upper & 0xfffff000) | rd << 7 | 0x17)


def jalr(offset=0, rd=1, rs1=1):
    return raw_instruction((offset & 0xfff) << 20 | rs1 << 15 | rd << 7 | 0x67)


def fixture(program, counts=None):
    counts = {pc: 10 for pc in program} if counts is None else counts
    sites = {}
    for index, (pc, row) in enumerate(sorted(program.items())):
        op = row['op']
        if op in cfg.REGISTER_OPS:
            operands = [f'x{row[k]}' for k in ('rd', 'rs1', 'rs2')]
        elif op in cfg.IMMEDIATE_OPS:
            operands = [f'x{row["rd"]}', f'x{row["rs1"]}', str(row['imm'])]
        elif op in ('lui', 'auipc'):
            operands = [f'x{row["rd"]}', str(row['imm'] >> 12)]
        else:
            operands = []  # Unsupported removed statements remain fail-closed.
        sites[pc] = dict(site=index, function='fixture', source_line=index,
                         assembly=op + ' ' + ','.join(operands))
    profile = dict(region_counts={str(pc): counts.get(pc, 0) for pc in program},
                   total_counts={str(pc): counts.get(pc, 0) for pc in program},
                   block_starts=sorted(program), words=[0, 0, 10000, sum(counts.values()) + 1])
    # Deliberately retain only real block starts; an instruction-level profile
    # would prohibit fusion by splitting every statement into its own block.
    profile['block_starts'] = [min(program)]
    return profile, sites


# Ordinary compiler-return assumption is explicit in every positive fixture.
# Default rejection and independent option checks are tested separately below.
def analyze(*args, **kwargs):
    return cfg.analyze(*args, compiler_abi_returns=True, **kwargs)


def extract(*args, **kwargs):
    return cfg.extract(*args, compiler_abi_returns=True, **kwargs)


def authenticate_certificate(*args, **kwargs):
    return cfg.authenticate_certificate(*args, compiler_abi_returns=True, **kwargs)


def authenticate_extraction(*args, **kwargs):
    return cfg.authenticate_extraction(*args, compiler_abi_returns=True, **kwargs)


def verify_lowering(*args, **kwargs):
    return cfg.verify_lowering(*args, compiler_abi_returns=True, **kwargs)


FORMULA = 'or(sltu(0,in0),in1)'


def diamond():
    return {0: ins('sltu', 13, 0, 13), 4: ins('or', 15, 13, 15),
            8: ins('bne', rs1=12, rs2=14, imm=12),
            12: kill(13), 16: ins('jal', 0, imm=8), 20: kill(13), 24: ret()}


def node(certificate, pc):
    return next(n for n in certificate['nodes'] if n['pc'] == pc)


def candidate(extraction, formula=FORMULA):
    return next(r for r in extraction['executable_candidates'] if r['formula'] == formula)


def test_both_successors_overwrite_before_read_and_legacy_verifier_stays_strict():
    program = diamond(); profile, sites = fixture(program)
    certificate = analyze(program)
    assert node(certificate, 8)['successors'] == [12, 20]
    assert 13 not in node(certificate, 8)['live_out']
    result = extract(program, profile, sites, 12, certificate=certificate)
    row = candidate(result)
    assert row['occurrences'][0]['inputs'] == [13, 15]
    assert row['occurrences'][0]['output'] == 15
    checked = verify_lowering(row, program, profile, sites, certificate)
    assert checked['schema'] == cfg.VERIFICATION_SCHEMA and checked['passed']
    assert checked['blocks'][0]['permitted_dead_register_differences'] == [13]
    assert checked['comparisons'] == 64
    assert FORMULA not in [r['formula'] for r in a.extract(program, profile, sites, 12)['executable_candidates']]
    with pytest.raises(ValueError, match='Illegal fusion'):
        a.verify_lowering(row, program, result['block_starts'])


@pytest.mark.parametrize('arm', [12, 20])
def test_use_on_either_edge_is_live_even_if_unobserved(arm):
    program = diamond(); program[arm] = ins('addi', 7, 13, imm=0)
    unobserved = {12, 16} if arm == 12 else {20}
    counts = {pc: (0 if pc in unobserved else 10) for pc in program}
    profile, sites = fixture(program, counts)
    certificate = analyze(program)
    assert 13 in node(certificate, 8)['live_out']
    assert FORMULA not in [r['formula'] for r in extract(program, profile, sites)['executable_candidates']]


def test_loop_fixed_point_retains_value_used_only_after_backedge():
    program = {0: ins('addi', 7, 3, imm=0), 4: kill(3),
               8: ins('bne', rs1=1, rs2=2, imm=-8), 12: kill(3), 16: ret()}
    certificate = analyze(program)
    assert node(certificate, 8)['successors'] == [0, 12]
    assert 3 in node(certificate, 0)['live_in']
    assert 3 in node(certificate, 8)['live_out']
    assert 3 not in node(certificate, 4)['live_in']
    assert 3 not in node(certificate, 12)['live_in']
    assert certificate['fixed_point_iterations'] >= 2


@pytest.mark.parametrize('barrier', [ins('unknown'), ins('ecall'), ret(),
                                     ins('jalr', 1, 5, imm=0), ins('jal', 1, imm=8)])
def test_calls_returns_indirect_and_opaque_effects_are_all_live(barrier):
    program = {0: ins('sltu', 13, 0, 13), 4: ins('or', 15, 13, 15),
               8: barrier, 12: kill(13), 16: ret()}
    certificate = analyze(program)
    assert node(certificate, 8)['live_in'] == list(range(1, 32))
    assert node(certificate, 8)['live_out'] == list(range(1, 32))
    profile, sites = fixture(program)
    if certificate['entry_model']['extraction_supported']:
        assert FORMULA not in [r['formula'] for r in extract(program, profile, sites)['executable_candidates']]
    else:
        with pytest.raises(ValueError, match='Unsupported static entry model'):
            extract(program, profile, sites)


@pytest.mark.parametrize('case', ['gap', 'target', 'fallthrough'])
def test_gaps_or_missing_branch_successors_do_not_prove_deadness(case):
    program = diamond()
    if case == 'gap':
        del program[8]
    elif case == 'target':
        program[8]['imm'] = 100
    else:
        del program[12]
    certificate = analyze(program)
    boundary = node(certificate, 4 if case == 'gap' else 8)
    assert 'missing_static_successor' in boundary['boundary']
    assert boundary['live_out'] == list(range(1, 32))
    profile, sites = fixture(program)
    with pytest.raises(ValueError, match='Unsupported static entry model'):
        extract(program, profile, sites)


def test_noncontiguous_fusion_preserves_intervening_work():
    program = {0: ins('sltu', 13, 0, 13), 4: ins('addi', 6, 6, imm=1),
               8: ins('or', 15, 13, 15), 12: ins('jal', 0, imm=4), 16: kill(13), 20: ret()}
    profile, sites = fixture(program); result = extract(program, profile, sites)
    row = candidate(result)
    assert row['occurrences'][0]['sites'] == [0, 2]
    checked = verify_lowering(row, program, profile, sites, result['certificate'])
    assert checked['passed'] and checked['blocks'][0]['permitted_dead_register_differences'] == [13]
    text = '\n'.join(f'__isaforge_begin_{s["site"]}:\n{s["assembly"]}\n__isaforge_end_{s["site"]}:'
                     for s in sites.values()) + '\n'
    rewritten = a.lower(text, row)
    assert 'addi x6,x6,1' in rewritten and '.insn r 0x0b, 0, 1, x15, x13, x15' in rewritten


@pytest.mark.parametrize('early', [ins('sw', rs1=2, rs2=13, imm=0),
                                    ins('sw', rs1=13, rs2=2, imm=0),
                                    ins('addi', 6, 13, imm=0)])
def test_intervening_read_of_internal_result_remains_external_output(early):
    program = {0: ins('sltu', 13, 0, 13), 4: early,
               8: ins('or', 15, 13, 15), 12: kill(13), 16: ret()}
    profile, sites = fixture(program)
    assert FORMULA not in [r['formula'] for r in extract(program, profile, sites)['executable_candidates']]


def test_replacement_input_clobber_is_still_rejected():
    program = {0: ins('addi', 5, 3, imm=1), 4: kill(3),
               8: ins('or', 15, 5, 15), 12: kill(5), 16: ret()}
    profile, sites = fixture(program)
    assert 'or(addi(in0,1),in1)' not in [r['formula'] for r in extract(program, profile, sites)['executable_candidates']]


def test_branch_use_of_temporary_prevents_fusion():
    program = diamond(); program[8]['rs1'] = 13
    profile, sites = fixture(program)
    assert FORMULA not in [r['formula'] for r in extract(program, profile, sites)['executable_candidates']]


def test_zero_is_not_live_not_an_input_and_cannot_be_a_result():
    program = {0: ins('addi', 5, 0, imm=1), 4: ins('addi', 5, 5, imm=2), 8: ret()}
    certificate = analyze(program)
    assert all(0 not in n[k] for n in certificate['nodes'] for k in ('uses', 'defs', 'live_in', 'live_out'))
    profile, sites = fixture(program); result = extract(program, profile, sites)
    row = candidate(result, 'addi(addi(0,1),2)')
    assert row['occurrences'][0]['inputs'] == []
    assert verify_lowering(row, program, profile, sites, certificate)['passed']
    program[4]['rd'] = 0
    assert not extract(program, profile, sites)['executable_candidates']


def test_no_globals_or_input_records_are_mutated_and_legacy_shape_is_compatible():
    program = diamond(); profile, sites = fixture(program)
    before = copy.deepcopy((program, profile, sites))
    functions = (a.extract, a.verify_lowering, a.discovery.findLastWrites, a.discovery.extractCandidates)
    result = extract(program, profile, sites, 12)
    assert result['requested_pool_size'] == 12 and result['pool'] == result['executable_candidates'][:12]
    assert result['relocation_filter_applied'] is False and 'relocation_guard' not in result
    assert authenticate_extraction(program, profile, sites, result) == result
    assert verify_lowering(candidate(result), program, profile, sites, result['certificate'])['passed']
    assert (program, profile, sites) == before
    assert functions == (a.extract, a.verify_lowering, a.discovery.findLastWrites, a.discovery.extractCandidates)


@pytest.mark.parametrize('part', ['live_out', 'successors', 'policy', 'source_binding', 'hash'])
def test_certificate_tamper_fails_even_with_recomputed_outer_hash(part):
    program = diamond(); certificate = analyze(program)
    if part in ('live_out', 'successors'):
        node(certificate, 8)[part] = []
    elif part == 'source_binding':
        certificate['source_bindings'][cfg.SOURCE] = '0' * 64
    else:
        certificate['policy'] = 'different policy'
    certificate['certificate_sha256'] = c.digest({k: v for k, v in certificate.items() if k != 'certificate_sha256'})
    if part == 'hash':
        certificate['certificate_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='certificate differs'):
        authenticate_certificate(program, certificate)


def test_whole_program_binding_includes_unexecuted_code_and_metadata():
    program = diamond(); program[100] = kill(9)
    certificate = analyze(program)
    for key, value in [('imm', 1), ('symbol', 'different_source')]:
        changed = copy.deepcopy(program); changed[100][key] = value
        with pytest.raises(ValueError, match='certificate differs'):
            authenticate_certificate(changed, certificate)


def test_source_drift_is_rejected_without_changing_any_file(monkeypatch):
    program = diamond(); certificate = analyze(program)
    changed = dict(certificate['source_bindings']); changed['src/candidates.py'] = '0' * 64
    monkeypatch.setattr(cfg, '_source_bindings', lambda: changed)
    with pytest.raises(ValueError, match='certificate differs'):
        authenticate_certificate(program, certificate)


@pytest.mark.parametrize('part', ['formula', 'inputs', 'output', 'sites', 'pcs', 'overlap', 'profile', 'source_map'])
def test_candidate_and_input_tamper_fails_rederivation(part):
    program = diamond(); profile, sites = fixture(program); result = extract(program, profile, sites)
    row = copy.deepcopy(candidate(result)); occurrence = row['occurrences'][0]
    if part == 'formula':
        row['formula'] = 'or(in0,in1)'
    elif part in ('inputs', 'sites', 'pcs'):
        occurrence[part] = list(reversed(occurrence[part]))
    elif part == 'output':
        occurrence['output'] = 14
    elif part == 'overlap':
        row['occurrences'].append(copy.deepcopy(occurrence))
    elif part == 'profile':
        profile['unused_but_bound_field'] = 'changed'
    else:
        sites[0]['assembly'] += ' # changed original source bytes'
    with pytest.raises(ValueError, match='Candidate differs'):
        verify_lowering(row, program, profile, sites, result['certificate'])


@pytest.mark.parametrize('fault', ['memory', 'control', 'live', 'zero', 'unmodified_dead'])
def test_projected_verifier_actually_checks_memory_control_and_registers(monkeypatch, fault):
    program = diamond(); profile, sites = fixture(program); result = extract(program, profile, sites)
    original = a.interpreter.execute
    def corrupted(block, instructions, state, replacements):
        regs, memory, target = original(block, instructions, state, replacements)
        if replacements:
            if fault == 'memory':
                memory[123] = 45
            elif fault == 'control':
                target = 123
            else:
                reg = {'live': 1, 'zero': 0, 'unmodified_dead': 7}[fault]
                regs[reg] ^= 1
        return regs, memory, target
    monkeypatch.setattr(a.interpreter, 'execute', corrupted)
    with pytest.raises(ValueError, match='Fusion changes'):
        verify_lowering(candidate(result), program, profile, sites, result['certificate'])


def test_retained_overwrite_of_same_dead_register_cannot_be_masked(monkeypatch):
    program = {0: ins('sltu', 13, 0, 13), 4: ins('or', 15, 13, 15), 8: kill(13),
               12: ins('bne', rs1=12, rs2=14, imm=12), 16: kill(13),
               20: ins('jal', 0, imm=8), 24: kill(13), 28: ret()}
    profile, sites = fixture(program); result = extract(program, profile, sites)
    row = candidate(result)
    assert 13 not in node(result['certificate'], 12)['live_out']
    checked = verify_lowering(row, program, profile, sites, result['certificate'])
    assert checked['blocks'][0]['permitted_dead_register_differences'] == []
    original = a.interpreter.execute
    def corrupted(block, instructions, state, replacements):
        regs, memory, target = original(block, instructions, state, replacements)
        if replacements:
            regs[13] ^= 1  # Corrupt the retained kill at0x8, not the removed0x0.
        return regs, memory, target
    monkeypatch.setattr(a.interpreter, 'execute', corrupted)
    with pytest.raises(ValueError, match='architectural register'):
        verify_lowering(row, program, profile, sites, result['certificate'])


def test_relocation_guard_runs_once_in_existing_chain_and_verifier_fails_closed():
    program = {0: ins('lui', 13, imm=4096), 4: ins('addi', 13, 13, imm=4), 8: ret()}
    profile, sites = fixture(program); sites[0]['assembly'] = 'lui a3,%hi(object)'
    sites[4]['assembly'] = 'addi a3,a3,%lo(object)'
    result = extract(program, profile, sites)
    assert result['executable_formula_count'] == 1
    guarded = guard.filter_executable_candidates(result, list(sites.values()))
    assert guarded['executable_formula_count'] == 0 and guarded['relocation_guard']['rejected_count'] == 1
    with pytest.raises(ValueError, match='relocatable'):
        verify_lowering(result['pool'][0], program, profile, sites, result['certificate'])


def test_full_extraction_rederivation_rejects_metadata_tamper():
    program = diamond(); profile, sites = fixture(program); result = extract(program, profile, sites)
    result['raw_formula_count'] += 1
    with pytest.raises(ValueError, match='extraction differs'):
        authenticate_extraction(program, profile, sites, result)


@pytest.mark.parametrize('bad', [True, -1, 32, 1.5])
def test_malformed_registers_fail_before_analysis(bad):
    program = diamond(); program[0]['rd'] = bad
    with pytest.raises(ValueError, match='register'):
        analyze(program)


def test_raw_word_decode_binding_and_unsupported_isa_fail_closed():
    program = {0: ins('addi', 5, 0, imm=1), 4: ret()}; program[0]['raw'] = 0x00100293
    assert analyze(program)
    program[0]['imm'] = 2
    with pytest.raises(ValueError, match='raw RV32 word'):
        analyze(program)
    program = {0: ins('mul', 5, 3, 4), 4: ins('addi', 5, 5, imm=1), 8: ret()}
    profile, sites = fixture(program)
    assert node(analyze(program), 0)['boundary'] == ['opaque_effect']
    with pytest.raises(ValueError, match='Unsupported static entry model'):
        extract(program, profile, sites)


def test_canonical_returns_require_explicit_independent_caller_option():
    program = diamond(); program[24]['raw'] = 0x00008067
    profile, sites = fixture(program)
    assert not cfg.analyze(program)['entry_model']['extraction_supported']
    with pytest.raises(ValueError, match='compiler_abi_return_assumption_required'):
        cfg.extract(program, profile, sites)
    result = extract(program, profile, sites)
    assert result['certificate']['entry_model']['compiler_abi_returns'] is True
    for call in (
        lambda: cfg.authenticate_certificate(program, result['certificate']),
        lambda: cfg.extract(program, profile, sites, certificate=result['certificate']),
        lambda: cfg.authenticate_extraction(program, profile, sites, result),
        lambda: cfg.verify_lowering(candidate(result), program, profile, sites, result['certificate']),
    ):
        with pytest.raises(ValueError, match='certificate differs'):
            call()
    forged = copy.deepcopy(result['certificate'])
    forged['entry_model']['compiler_abi_returns'] = False
    forged['certificate_sha256'] = c.digest({k: v for k, v in forged.items() if k != 'certificate_sha256'})
    with pytest.raises(ValueError, match='certificate differs'):
        cfg.authenticate_certificate(program, forged)


@pytest.mark.parametrize('transfer', [ins('jalr', 0, 5, imm=0), ins('jalr', 0, 1, imm=4),
                                       ins('jalr', 1, 5, imm=0)])
def test_unobserved_indirect_entry_into_fusion_interior_refuses_all_extraction(transfer):
    program = diamond(); program[100] = transfer; program[104] = ret()
    counts = {pc: 0 if pc >= 100 else 10 for pc in program}
    profile, sites = fixture(program, counts)
    # x5 could hold4: the observed trace is not a target-completeness proof.
    certificate = analyze(program)
    assert any(r['pc'] == 100 and r['reason'] == 'unresolved_indirect_control'
               for r in certificate['entry_model']['unsupported'])
    with pytest.raises(ValueError, match='Unsupported static entry model'):
        extract(program, profile, sites)


@pytest.mark.parametrize('transfer', [ins('beq', rs1=1, rs2=2, imm=-96), ins('jal', 1, imm=-96)])
def test_unobserved_direct_targets_and_call_continuations_are_protected_entries(transfer):
    program = diamond(); program[100] = transfer; program[104] = ret()
    counts = {pc: 0 if pc >= 100 else 10 for pc in program}
    profile, sites = fixture(program, counts); result = extract(program, profile, sites)
    assert {4, 104} <= set(result['certificate']['entry_model']['protected_entries'])
    assert {4, 104} <= set(result['block_starts'])
    assert FORMULA not in [r['formula'] for r in result['executable_candidates']]


@pytest.mark.parametrize('kind', ['opaque', 'auipc_jalr'])
def test_unobserved_opaque_instruction_or_unresolved_call_pair_is_not_special_cased(kind):
    program = diamond()
    if kind == 'opaque':
        program.update({100: ins('unknown'), 104: ret()})
    else:
        program.update({100: ins('auipc', 1, imm=0), 104: ins('jalr', 1, 1, imm=-100), 108: ret()})
    profile, sites = fixture(program, {pc: 0 if pc >= 100 else 10 for pc in program})
    with pytest.raises(ValueError, match='Unsupported static entry model'):
        extract(program, profile, sites)


def call_fixture():
    return {0: auipc(), 4: jalr(16), 8: ret(), 16: ret()}


def test_exact_raw_call_pair_is_resolved_with_callee_and_continuation_entries():
    program = call_fixture(); profile, sites = fixture(program)
    result = extract(program, profile, sites); certificate = result['certificate']
    proof = certificate['entry_model']['resolved_direct_calls']
    assert proof == [dict(auipc_pc=0, jalr_pc=4, target=16, continuation=8,
                          auipc_raw=program[0]['raw'], jalr_raw=program[4]['raw'])]
    assert {8, 16} <= set(certificate['entry_model']['protected_entries'])
    assert node(certificate, 4)['successors'] == [8, 16]
    assert node(certificate, 4)['boundary'] == ['resolved_direct_call']
    assert node(certificate, 4)['live_in'] == list(range(1, 32))
    assert node(certificate, 4)['live_out'] == list(range(1, 32))


@pytest.mark.parametrize('upper,offset,base,target', [
    (0, 17, 0, 16), (-4096, 16, 4096, 16),
    (0, -16, 4096, 4080), (4096, 16, 0xfffffff0, 4096)])
def test_call_target_uses_signed_wrapped_rv32_arithmetic_and_clears_bit_zero(upper, offset, base, target):
    program = {base: auipc(upper), base + 4: jalr(offset), base + 8: ret(), target: ret()}
    certificate = analyze(program)
    assert certificate['entry_model']['extraction_supported']
    assert certificate['entry_model']['resolved_direct_calls'][0]['target'] == target


@pytest.mark.parametrize('bad', ['missing_upper_raw', 'missing_lower_raw', 'wrong_link',
                                 'wrong_base_use', 'wrong_upper_def', 'misaligned', 'absent_target'])
def test_direct_call_recognition_requires_exact_raw_pair_and_valid_target(bad):
    program = call_fixture()
    if bad == 'missing_upper_raw':
        del program[0]['raw']
    elif bad == 'missing_lower_raw':
        del program[4]['raw']
    elif bad == 'wrong_link':
        program[4] = jalr(16, rd=5)
    elif bad == 'wrong_base_use':
        program[4] = jalr(16, rs1=5)
    elif bad == 'wrong_upper_def':
        program[0] = auipc(rd=5)
    else:
        program[4] = jalr(18 if bad == 'misaligned' else 20)
    profile, sites = fixture(program)
    assert not analyze(program)['entry_model']['resolved_direct_calls']
    with pytest.raises(ValueError, match='unresolved_indirect_control'):
        extract(program, profile, sites)


@pytest.mark.parametrize('entry', ['direct_branch', 'later_call_pair'])
def test_global_entries_from_all_pairs_are_collected_before_accepting_any_second_word(entry):
    program = call_fixture()
    if entry == 'direct_branch':
        program.update({100: ins('bne', rs1=1, rs2=2, imm=-96), 104: ret()})
    else:
        program.update({100: auipc(), 104: jalr(-96), 108: ret()})
    profile, sites = fixture(program, {pc: 0 if pc >= 100 else 10 for pc in program})
    certificate = analyze(program)
    assert 4 in certificate['entry_model']['protected_entries']
    assert dict(pc=4, reason='entry_into_call_second_word') in certificate['entry_model']['unsupported']
    with pytest.raises(ValueError, match='entry_into_call_second_word'):
        extract(program, profile, sites)


@pytest.mark.parametrize('csr', [0xc00, 0xc80, 0xc02, 0xc82])
@pytest.mark.parametrize('rd', [0, 10])
def test_only_exact_readonly_counter_encodings_are_opaque_noncontrol_barriers(csr, rd):
    word = csr << 20 | rd << 7 | 0x2073
    program = {0: ins('addi', 5, 3, imm=1), 4: raw_instruction(word),
               8: ins('addi', 5, 5, imm=2), 12: ret()}
    profile, sites = fixture(program); result = extract(program, profile, sites)
    certificate = result['certificate']
    assert certificate['entry_model']['readonly_counter_reads'] == [dict(pc=4, raw=word, csr=csr, rd=rd)]
    assert node(certificate, 4)['boundary'] == ['readonly_counter_barrier']
    assert node(certificate, 4)['successors'] == [8]
    assert node(certificate, 4)['live_out'] == list(range(1, 32))
    assert not result['executable_candidates']  # Cannot cross the counter read.


@pytest.mark.parametrize('word', [0xc0001073, 0xc0003073, 0xc0006073,
                                 0xc000a073, 0xc0102073, 0xc0302073, 0x30002073])
def test_counter_writes_reserved_csr_and_nonwhitelisted_reads_refuse_extraction(word):
    program = {0: raw_instruction(word), 4: ret()}
    profile, sites = fixture(program)
    certificate = analyze(program)
    assert certificate['entry_model']['readonly_counter_reads'] == []
    with pytest.raises(ValueError, match='opaque_instruction'):
        extract(program, profile, sites)


def test_exact_ebreak_requires_independent_explicit_firmware_termination_option():
    program = diamond(); program[100] = raw_instruction(0x00100073)
    profile, sites = fixture(program, {pc: 0 if pc == 100 else 10 for pc in program})
    with pytest.raises(ValueError, match='firmware_trap_exit_assumption_required'):
        extract(program, profile, sites)
    result = extract(program, profile, sites, firmware_trap_exit=True)
    certificate = result['certificate']
    assert certificate['entry_model']['firmware_trap_exit'] is True
    assert certificate['entry_model']['firmware_trap_exits'] == [dict(pc=100, raw=0x00100073)]
    assert node(certificate, 100)['successors'] == []
    assert node(certificate, 100)['boundary'] == ['firmware_trap_exit']
    assert node(certificate, 100)['live_in'] == list(range(1, 32))
    assert node(certificate, 100)['live_out'] == list(range(1, 32))
    row = candidate(result)
    assert verify_lowering(row, program, profile, sites, certificate, firmware_trap_exit=True)['passed']
    assert authenticate_extraction(program, profile, sites, result, firmware_trap_exit=True) == result
    for call in (
        lambda: authenticate_certificate(program, certificate),
        lambda: extract(program, profile, sites, certificate=certificate),
        lambda: authenticate_extraction(program, profile, sites, result),
        lambda: verify_lowering(row, program, profile, sites, certificate),
    ):
        with pytest.raises(ValueError, match='certificate differs'):
            call()
    forged = copy.deepcopy(certificate); forged['entry_model']['firmware_trap_exit'] = False
    forged['certificate_sha256'] = c.digest({k: v for k, v in forged.items() if k != 'certificate_sha256'})
    with pytest.raises(ValueError, match='certificate differs'):
        authenticate_certificate(program, forged)


@pytest.mark.parametrize('raw', [0x00000073, 0x001000f3, 0x10200073, 0x30200073])
def test_firmware_option_does_not_admit_other_traps_or_privileged_returns(raw):
    program = {0: raw_instruction(raw), 4: ret()}; profile, sites = fixture(program)
    with pytest.raises(ValueError, match='opaque_instruction'):
        extract(program, profile, sites, firmware_trap_exit=True)


@pytest.mark.parametrize('raw', [0x02009293, 0x0200d293, 0x4200d293, 0x000092e7])
def test_reserved_shift_or_jalr_encodings_are_not_promoted_from_legacy_decoder(raw):
    op, rd, rs1, rs2, imm = a.tracing.decode(raw)
    program = {0: {**ins(op, rd, rs1, rs2, imm), 'raw': raw}, 4: ret()}
    with pytest.raises(ValueError, match='Reserved RV32'):
        analyze(program)


def test_original_lift_loop_facts_recover_two_classes_without_native_inputs():
    # Exact decoded instructions/PCs from the original two output-packing loops,
    # expressed as synthetic facts. No saved experiment or outcome is opened.
    program = {
        0xf4: ins('lw', 13, 14, imm=12), 0xf8: ins('slli', 15, 15, imm=1),
        0xfc: ins('addi', 14, 14, imm=-4), 0x100: ins('sltu', 13, 0, 13),
        0x104: ins('or', 15, 13, 15), 0x108: ins('bne', rs1=12, rs2=14, imm=-20),
        0x10c: ins('lui', 14, imm=4096), 0x110: ins('sw', rs1=14, rs2=15, imm=-1532),
        0x114: ins('lui', 14, imm=4096), 0x118: ins('addi', 14, 14, imm=-1516),
        0x11c: ins('addi', 12, 14, imm=-56), 0x120: ins('lw', 13, 14, imm=52),
        0x124: ins('slli', 15, 15, imm=1), 0x128: ins('addi', 14, 14, imm=-4),
        0x12c: ins('sltu', 13, 0, 13), 0x130: ins('or', 15, 13, 15),
        0x134: ins('bne', rs1=12, rs2=14, imm=-20), 0x138: ins('lui', 14, imm=4096),
        0x13c: ins('lui', 13, imm=4096), 0x140: ins('sw', rs1=14, rs2=15, imm=-1536),
        0x144: ins('lw', 14, 13, imm=-1380), 0x148: ins('add', 15, 14, 15),
        0x14c: ins('sw', rs1=13, rs2=15, imm=-1380), 0x150: ret()}
    counts = {pc: 4004 if 0xf4 <= pc <= 0x108 else 14014 if 0x120 <= pc <= 0x134 else 1001
              for pc in program}
    profile, sites = fixture(program, counts)
    result = extract(program, profile, sites, 12)
    old = a.extract(program, profile, sites, 12)
    for formula in (FORMULA, 'or(sltu(0,in0),slli(in1,1))'):
        row = candidate(result, formula)
        assert row['region_custom_instructions'] == 18018 and len(row['occurrences']) == 2
        assert formula not in [r['formula'] for r in old['executable_candidates']]
        checked = verify_lowering(row, program, profile, sites, result['certificate'])
        assert checked['comparisons'] == 128
        assert all(b['permitted_dead_register_differences'] == [13] for b in checked['blocks'])
