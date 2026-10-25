"""Exact raw compiler tail-transfer closure; no compiler or native jobs."""
import pytest

from isaforge import assembly_lowering as a, cfg_liveness_tail as cfg


def decoded(word):
    return {**dict(zip(('op', 'rd', 'rs1', 'rs2', 'imm'), a.tracing.decode(word))), 'raw': word}


def auipc(rd, upper=0):
    return decoded((upper & 0xfffff000) | (rd << 7) | 0x17)


def jalr(rd, rs1, offset):
    return decoded(((offset & 0xfff) << 20) | (rs1 << 15) | (rd << 7) | 0x67)


def ret():
    return jalr(0, 1, 0)


def test_exact_nonlinking_auipc_jalr_pair_resolves_tail_target_as_barrier():
    program = {0: auipc(6), 4: jalr(0, 6, 17), 8: ret(), 16: ret()}
    cert = cfg.analyze(program, compiler_abi_returns=True)
    entry = cert['entry_model']
    assert entry['extraction_supported']
    assert entry['resolved_direct_tail_transfers'] == [dict(
        auipc_pc=0, jalr_pc=4, target=16, auipc_raw=program[0]['raw'], jalr_raw=program[4]['raw'])]
    assert 16 in entry['protected_entries'] and 8 in entry['protected_entries']
    node = next(row for row in cert['nodes'] if row['pc'] == 4)
    assert node['successors'] == [16]
    assert node['boundary'] == ['resolved_direct_tail_transfer']
    assert node['live_in'] == list(range(1, 32))
    assert node['live_out'] == list(range(1, 32))


def test_exact_auipc_jalr_linking_call_remains_supported_alongside_tail_extension():
    program = {0: auipc(1), 4: jalr(1, 1, 12), 8: ret(), 12: ret()}
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert cert['entry_model']['extraction_supported']
    assert cert['entry_model']['resolved_direct_calls'] == [dict(
        auipc_pc=0, jalr_pc=4, target=12, auipc_raw=program[0]['raw'],
        jalr_raw=program[4]['raw'], continuation=8)]
    node = next(row for row in cert['nodes'] if row['pc'] == 4)
    assert node['successors'] == [8, 12]
    assert node['boundary'] == ['resolved_direct_call']


@pytest.mark.parametrize('upper,offset,base,target', [
    (0, 17, 0, 16), (-4096, 16, 4096, 16),
    (0, -16, 4096, 4080), (4096, 16, 0xfffffff0, 4096)])
def test_tail_target_uses_signed_wrapped_rv32_arithmetic(upper, offset, base, target):
    program = {base: auipc(6, upper), base + 4: jalr(0, 6, offset),
               base + 8: ret(), target: ret()}
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert cert['entry_model']['extraction_supported']
    assert cert['entry_model']['resolved_direct_tail_transfers'][0]['target'] == target


@pytest.mark.parametrize('fault', ['wrong_base', 'linking_destination', 'zero_base',
                                   'missing_auipc_raw', 'missing_jalr_raw', 'misaligned', 'absent'])
def test_tail_pair_requires_exact_registers_raw_words_and_resolved_target(fault):
    program = {0: auipc(6), 4: jalr(0, 6, 16), 8: ret(), 16: ret()}
    if fault == 'wrong_base':
        program[4] = jalr(0, 7, 16)
    elif fault == 'linking_destination':
        program[4] = jalr(1, 6, 16)
    elif fault == 'zero_base':
        program[0] = auipc(0)
        program[4] = jalr(0, 0, 16)
    elif fault == 'missing_auipc_raw':
        del program[0]['raw']
    elif fault == 'missing_jalr_raw':
        del program[4]['raw']
    elif fault == 'misaligned':
        program[4] = jalr(0, 6, 18)
    elif fault == 'absent':
        program[4] = jalr(0, 6, 20)
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert not cert['entry_model']['resolved_direct_tail_transfers']
    assert not cert['entry_model']['extraction_supported']
    expected_reason = ('missing_raw_direct_tail_proof' if fault in
                       ('missing_auipc_raw', 'missing_jalr_raw') else
                       'invalid_direct_tail_target' if fault in ('misaligned', 'absent') else
                       'unresolved_indirect_control')
    assert any(row['reason'] == expected_reason for row in cert['entry_model']['unsupported'])


@pytest.mark.parametrize('base,offset', [(6, 16), (1, 0)])
def test_static_branch_entry_into_second_word_rejects_tail_pair_even_for_canonical_ret(base, offset):
    program = {0: auipc(base), 4: jalr(0, base, offset), 8: ret(), 16: ret(),
               20: dict(op='beq', rd=None, rs1=1, rs2=2, imm=-16)}
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert not cert['entry_model']['extraction_supported']
    assert dict(pc=4, reason='entry_into_resolved_transfer_second_word') in cert['entry_model']['unsupported']


def test_invalid_auipc_ra_tail_target_cannot_fall_back_to_abi_return():
    program = {0: auipc(1, 4096), 4: jalr(0, 1, 0), 8: ret()}
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert not cert['entry_model']['extraction_supported']
    assert dict(pc=4, reason='invalid_direct_tail_target', target=4096) in cert['entry_model']['unsupported']


@pytest.mark.parametrize('fault', ['missing_auipc_raw', 'missing_jalr_raw', 'absent_target'])
def test_canonical_abi_return_fallback_cannot_rescue_unproven_x1_tail(fault):
    target = 4096 if fault == 'absent_target' else 0
    program = {0: auipc(1, 4096 if fault == 'absent_target' else 0), 4: jalr(0, 1, 0),
               8: ret(), 16: ret()}
    if fault == 'missing_auipc_raw':
        del program[0]['raw']
    elif fault == 'missing_jalr_raw':
        del program[4]['raw']
    else:
        del program[16]
    cert = cfg.analyze(program, compiler_abi_returns=True)
    assert not cert['entry_model']['extraction_supported']
    expected_reason = ('invalid_direct_tail_target' if fault == 'absent_target' else
                       'missing_raw_direct_tail_proof')
    assert dict(pc=4, reason=expected_reason, target=target) in cert['entry_model']['unsupported']
