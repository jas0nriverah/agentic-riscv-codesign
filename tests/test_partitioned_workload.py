"""Partition adapter contracts without processor builds or measurements."""
from pathlib import Path

import pytest

from isaforge import partitioned_workload as p

ROOT = Path(__file__).resolve().parents[1]


def good_raw():
    return dict(stack_initialized=True, stack_violations=0, min_sp=5000,
                max_stack_bytes=3192, stack_checked_cycles=100,
                first_violation=dict(kind='none', pc=0, address=0), trapped=False)


@pytest.mark.parametrize('field,value', [
    ('stack_initialized', False), ('stack_violations', 1), ('min_sp', 4351),
    ('min_sp', 8193), ('min_sp', True), ('max_stack_bytes', 1),
    ('stack_checked_cycles', 0), ('stack_checked_cycles', True),
    ('first_violation', dict(kind='ram-write', pc=4, address=4224)),
    ('trapped', True),
])
def test_memory_evidence_rejects_invalid_fields(field, value):
    raw = good_raw(); raw[field] = value
    with pytest.raises(ValueError):
        p.validate_memory(raw)


def test_memory_evidence_and_explicit_trap():
    result = p.validate_memory(good_raw())
    assert result['stack_headroom_bytes'] == 648
    raw = good_raw(); raw['trapped'] = True
    assert p.validate_memory(raw, trapped=True) == result


@pytest.mark.parametrize('end,start,passes', [(4224,4000,True),(4225,4000,False),
                                             (4164,4165,False),(4164,4000,True)])
def test_symbols_enforce_compile_guard(tmp_path,end,start,passes):
    (tmp_path/'symbols.txt').write_text(f'{end:08x} B _program_end\n{start:08x} D _writable_start\n')
    if passes:
        assert p.memory_symbols(tmp_path/'firmware.hex') == (end,start)
        assert p.PARTITION['stack_floor'] - end >= p.PARTITION['minimum_guard_bytes']
    else:
        with pytest.raises(ValueError): p.memory_symbols(tmp_path/'firmware.hex')


def test_observer_changes_visibility_only_and_synthesis_core_is_original(tmp_path):
    inputs=tmp_path/'inputs'; outputs=tmp_path/'sim'; inputs.mkdir(); outputs.mkdir()
    # Fixed declarations are covered without creating or running Verilator.
    core=('reg [63:0] count_cycle, count_instr;\n'
          'reg [31:0] reg_pc, reg_next_pc, reg_op1, reg_op2, reg_out;\n'
          'reg [31:0] cpuregs [0:regfile_size-1];\n')
    top=(ROOT/'hardware/soc_top.v').read_text()
    (inputs/'picorv32.v').write_text(core); (inputs/'soc_top.v').write_text(top)
    observed_core,observed_top,synthesis_top=p.observer_sources(inputs,outputs,Path('/tmp/firmware.hex'))
    strip=lambda text:text.replace(' /* verilator public_flat_rd */','')
    # Splitting combined declarations preserves behavior but is not byte identity.
    assert strip(observed_core.read_text()).replace('reg [63:0] count_cycle; reg [63:0] count_instr;',
                                                  'reg [63:0] count_cycle, count_instr;').replace('reg [31:0] reg_pc; reg [31:0] reg_next_pc,',
                                                  'reg [31:0] reg_pc, reg_next_pc,') == core
    assert strip(observed_top.read_text()) == strip(synthesis_top.read_text())
    expected=top.replace('.LATENCY(0)','.LATENCY(1)').replace('"firmware.hex"','"/tmp/firmware.hex"')
    assert synthesis_top.read_text() == expected
    assert (inputs/'picorv32.v').read_text()==core
    assert (inputs/'soc_top.v').read_text()==top


def test_pool_uses_all_executable_candidates_and_filters_operations(monkeypatch):
    candidates=[dict(formula=str(i),name=f'auto-{i}',occurrences=[dict(pcs=[hex(i*4)])])
                for i in range(9)]
    monkeypatch.setattr(p,'EXTRACT',lambda *args:dict(pool=candidates[:3],executable_candidates=candidates))
    calibration=dict(rule_matches_all=True,semantic_checks_passed=True,stock_trap_control_passed=True,
                     rows=[dict(op='add',immediate=None,cycles=4),dict(op='pcpi',immediate=None,cycles=5)])
    program={i*4:dict(op='add' if i!=4 else 'srl') for i in range(9)}
    result=p.extract_pool(program,{},[],3,calibration)
    assert result['eligible_formula_count']==8
    assert result['excluded_uncalibrated_formulas']==['4']
    assert result['selected_rank_indices']==[0,4,7]
    assert [r['formula'] for r in result['pool']]==['0','5','8']


def test_pool_patch_restores_after_exception():
    original=p.lowering.extract
    with pytest.raises(RuntimeError):
        with p.pool_for_audit({}):
            assert p.lowering.extract is not original
            raise RuntimeError('test')
    assert p.lowering.extract is original
def test_partition_image_preserves_bytes_and_zero_fills():
    from isaforge.partitioned_workload import memory_image
    binary = bytes(range(256)) * 16 + b'abc' * 22
    words = memory_image(binary).splitlines()
    assert len(words) == 2048
    restored = b''.join(int(word, 16).to_bytes(4, 'little') for word in words)
    assert restored[:len(binary)] == binary
    assert restored[len(binary):] == bytes(8192 - len(binary))
    with pytest.raises(ValueError):
        memory_image(bytes(4225))
    with pytest.raises(ValueError):
        memory_image(b'')
