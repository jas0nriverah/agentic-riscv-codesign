"""Contracts for the live measured-program path, not synthetic speedup claims."""
import copy
import shutil
import subprocess
from unittest.mock import patch

import pytest

from isaforge import codesign as c
from isaforge.core_experiment import crc32_oracle
from isaforge.features import FEATURE_COLUMNS
from isaforge.selection import run_policy


def rows():
    return c.public_rows('test-context')


def label(row, speedup=1.1, area=110, timing=True):
    return {**row, 'speedup': speedup, 'area': area, 'timing_feasible': timing,
            'measurement_source': 'synthetic', 'measurement_seconds': 1}


def test_fixed_pool_has_only_retained_kernel_candidates_and_context_identity():
    public = rows()
    assert len(public) == 6
    assert {r['formula'] for r in public} == {v[0] for v in c.CANDIDATES.values()}
    assert all(r['runs'] == 174080 and r['input_count'] <= 2 for r in public)
    assert not {r['candidate_id'] for r in public} & {r['candidate_id'] for r in c.public_rows('different-input-context')}


def test_firmware_lowering_has_fixed_opcode_and_no_changes_outside_macro():
    original = (c.ROOT/'benchmarks/embench/src/crc32/crc_32.c').read_text()
    before, after = original.split(c.MACRO)
    for name in c.CANDIDATES:
        lowered = c.lower_crc(original, name)
        assert lowered.startswith(before) and lowered.endswith(after)
        assert lowered.count('.insn r 0x0b, 0, 1') == 1
    with pytest.raises(ValueError, match='Pinned'):
        c.lower_crc(original.replace(c.MACRO, ''), 'index_byte')


def test_live_measurement_hides_outcomes_and_only_bought_rows_reach_model():
    candidates = [label(r, 99) for r in rows()]
    called = []
    tools = c.LiveSelectionTools(candidates, lambda r: called.append(r['candidate_id']) or label(r), 3, 200)

    class InspectingModel:
        warnings = ['uncalibrated']
        def __init__(self, seed): pass
        def fit(self, data):
            assert {r['candidate_id'] for r in data} == set(called)
            assert all(r['speedup'] == 1.1 for r in data)
            return self
        def predict(self, data):
            assert all(set(r) == {'candidate_id', 'benchmark', 'formula', *FEATURE_COLUMNS} for r in data)
            return [dict(candidate_id=r['candidate_id'], upper=2+i) for i,r in enumerate(data)]
    with patch.object(c, 'SpeedupPredictor', InspectingModel):
        result = run_policy(tools, 'active_learning', bootstrap=2)
    assert result['measurements_used'] == 3
    assert len(called) == 3
    event = next(e for e in tools.events if e['action'] == 'predict')
    assert len(event['training_ids']) == 2
    tools.measure(called[0])
    assert len(called) == 3
    assert 'name' not in tools.list_candidates()[0]


def test_failed_measurements_are_charged_and_cannot_be_retried_for_free():
    def fail(row): raise RuntimeError('native failure')
    tools = c.LiveSelectionTools(rows(), fail, 1, 200)
    with pytest.raises(RuntimeError, match='native failure'):
        tools.measure(rows()[0]['candidate_id'])
    assert tools.measurements_used == 1 and tools.training_size == 0
    with pytest.raises(ValueError, match='budget'):
        tools.measure(rows()[1]['candidate_id'])


@pytest.mark.parametrize('change', [dict(formula='xor(in0,in1)'), dict(size=999), dict(candidate_id='other'), dict(timing_feasible=None)])
def test_provider_cannot_change_identity_features_or_omit_timing(change):
    tools = c.LiveSelectionTools(rows(), lambda r: {**label(r), **change}, 1, 200)
    with pytest.raises(ValueError): tools.measure(rows()[0]['candidate_id'])
    assert tools.measurements_used == 1 and tools.training_size == 0


@pytest.mark.parametrize('speedup,area,timing', [(1,110,True), (2,201,True), (2,110,False)])
def test_final_design_must_improve_and_satisfy_area_and_timing(speedup, area, timing):
    tools = c.LiveSelectionTools(rows(), lambda r: label(r,speedup,area,timing), 1, 200)
    tools.measure(rows()[0]['candidate_id'])
    assert tools.choose_final() is None


def test_execution_contract_rejects_wrong_outputs_counts_and_wait_cycles():
    raw = {'status': 0x600d600d, 'words': [crc32_oracle(),11433,100,50,1],
           'fault': 0, 'partial_report_bits': 0, 'pcpi_handshakes': 176128,
           'pcpi_valid_cycles': 352256, 'pcpi_wait_cycles': 176128}
    assert c.validate_execution(raw, True)['cycles'] == 100
    for key in ('fault','partial_report_bits','pcpi_handshakes','pcpi_valid_cycles','pcpi_wait_cycles'):
        bad = copy.deepcopy(raw); bad[key] += 1
        with pytest.raises(ValueError): c.validate_execution(bad, True)
    bad = copy.deepcopy(raw); bad['words'][0] ^= 1
    with pytest.raises(ValueError): c.validate_execution(bad, True)


def test_sealed_record_detects_changed_measurements(tmp_path):
    path = tmp_path/'measurement.json'
    c.seal(path, {'cycles': 100})
    assert c.unseal(path) == {'cycles': 100}
    c.write(path, {'cycles': 50})
    with pytest.raises(ValueError, match='record changed'): c.unseal(path)


@pytest.mark.skipif(not shutil.which('yosys'), reason='Yosys unavailable')
def test_universal_proof_rejects_incorrect_datapath(tmp_path):
    reference = tmp_path/'reference.v'
    reference.write_text(c.generate_rtl(c.CANDIDATES['index_byte'][0], 'reference'))
    for good in (True, False):
        proposal = tmp_path/'candidate.v'
        proposal.write_text('module candidate(input [31:0] in0,in1,output [31:0] result);\n'
                            + ('assign result = {24\'b0, in0[7:0] ^ in1[7:0]};' if good else 'assign result = in0 ^ in1;') + '\nendmodule\n')
        run = subprocess.run(['yosys', '-Q', '-p', f'read_verilog {reference} {proposal}; proc; opt; '
                              'equiv_make reference candidate equiv; hierarchy -top equiv; equiv_simple; equiv_status -assert'],
                             capture_output=True, timeout=15)
        assert (run.returncode == 0) == good
