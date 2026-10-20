"""Strict 6400/6528 partition contracts without native hardware jobs."""
import json
from pathlib import Path

import pytest

from isaforge import bounded_workload as bounded, codesign as c


def good_raw():
    return dict(stack_initialized=True, stack_violations=0, min_sp=7000,
                max_stack_bytes=1192, stack_checked_cycles=100,
                first_violation=dict(kind='none', pc=0, address=0), trapped=False)


@pytest.mark.parametrize('field,value', [('min_sp',6527), ('min_sp',8193),
        ('min_sp',True), ('stack_initialized',False), ('stack_violations',1),
        ('max_stack_bytes',1193), ('stack_checked_cycles',0), ('trapped',True)])
def test_memory_rejects_partition_and_observation_violations(field, value):
    raw = good_raw()
    raw[field] = value
    with pytest.raises(ValueError):
        bounded.validate_memory(raw)


def test_memory_boundary_and_context_restore():
    original = bounded.partition.PARTITION
    raw = good_raw()
    raw.update(min_sp=6528, max_stack_bytes=1664)
    assert bounded.validate_memory(raw)['stack_headroom_bytes'] == 0
    assert bounded.partition.PARTITION is original
    with pytest.raises(RuntimeError):
        with bounded.partition_context():
            assert bounded.partition.PARTITION == bounded.PARTITION
            raise RuntimeError('restore')
    assert bounded.partition.PARTITION is original


@pytest.mark.parametrize('end,start,passes', [(6400,6000,True),(6401,6000,False),
                                             (6300,6301,False),(6300,0,True)])
def test_symbols_enforce_program_guard(tmp_path, end, start, passes):
    (tmp_path / 'symbols.txt').write_text(f'{end:08x} B _program_end\n{start:08x} D _writable_start\n')
    if passes:
        assert bounded.memory_symbols(tmp_path / 'firmware.hex') == (end,start)
    else:
        with pytest.raises(ValueError):
            bounded.memory_symbols(tmp_path / 'firmware.hex')


def test_binary_limit_and_zero_fill():
    binary = bytes(range(256)) * 25
    image = bounded.memory_image(binary)
    assert len(image.splitlines()) == 2048
    restored = b''.join(int(row,16).to_bytes(4,'little') for row in image.splitlines())
    assert restored == binary + bytes(1792)
    with pytest.raises(ValueError):
        bounded.memory_image(binary + b'x')


def test_monitor_changes_only_declared_configuration():
    original = (c.ROOT / 'hardware/stack_monitor.hpp').read_text()
    derived = bounded.monitor_source()
    assert derived.replace('floor==6528','floor==4352').replace('program_end<=6400','program_end<=4224') == original
    assert 'if (sp<floor || sp>8192)' in derived
    assert '(floor<=byte && byte<8192)' in derived


def test_prepare_seals_new_partition_without_changing_source_module(tmp_path, monkeypatch):
    previous = bounded.campaign.WORKLOADS
    frozen_hash = c.sha(bounded.campaign.__file__)

    def fake_prepare(reference, output, workload, size):
        assert bounded.campaign.WORKLOADS == bounded.WORKLOADS
        inputs = Path(output) / 'inputs'
        inputs.mkdir(parents=True)
        (inputs / 'soc_link.ld').write_text('ASSERT(_program_end <= 4224, "firmware must leave the declared guard and 3840-byte stack")')
        (inputs / 'stack_monitor.hpp').write_text('old monitor')
        return dict(context_id='old', workload=workload, pool_size=size,
                    configuration={}, source_bindings={}, build_variant={},
                    compiler_flags=list(bounded.compact.FLAGS))

    monkeypatch.setattr(bounded.campaign, 'prepare', fake_prepare)
    output = tmp_path / 'experiment'
    plan = bounded.prepare('unused', output, 'edn')
    bounded.check_plan(plan)
    assert bounded.campaign.WORKLOADS is previous
    assert c.sha(bounded.campaign.__file__) == frozen_hash
    assert c.digest({k:v for k,v in plan.items() if k!='context_id'}) == plan['context_id']
    assert plan['configuration']['stack_bytes'] == 1664
    assert (output / 'inputs/stack_monitor.hpp').read_text() == bounded.monitor_source()
    assert '_program_end <= 6400' in (output / 'inputs/soc_link.ld').read_text()
    for name, expected in plan['inputs'].items():
        assert c.sha(output / 'inputs' / name) == expected
    assert c.sha(output / 'sources' / bounded.SOURCE) == plan['source_bindings'][bounded.SOURCE]


def test_simulation_receipt_uses_checked_floor_and_two_workers(tmp_path, monkeypatch):
    evaluator = object.__new__(bounded.Evaluator)
    evaluator.inputs = tmp_path / 'inputs'
    evaluator.tools = dict(verilator='fixture-verilator')
    calls = []
    class Runner:
        def run(self, argv, log, **kwargs):
            calls.append((list(map(str,argv)),kwargs))
            return json.dumps(good_raw())
    evaluator.runner = Runner()
    monkeypatch.setattr(bounded,'observer_sources',lambda *args: (Path('core.v'),Path('observed.v'),Path('top.v')))
    firmware = tmp_path / 'firmware'
    firmware.mkdir()
    (firmware / 'symbols.txt').write_text('00001800 B _program_end\n00001700 D _writable_start\n')
    raw, _ = evaluator.simulate(tmp_path / 'profile', firmware / 'firmware.hex', Path('candidate.v'), False)
    assert raw == good_raw()
    assert calls[0][0][calls[0][0].index('-j')+1] == '2'
    assert calls[1][0][-3:] == ['6144','5888','6528']
