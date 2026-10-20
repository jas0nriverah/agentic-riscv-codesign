"""Qualification source/partition contracts without running native tools."""
from pathlib import Path
import shutil

import pytest

from isaforge import codesign as c, workload_campaign as campaign


def test_registration_restores_existing_entries_after_failure():
    previous = dict(campaign.w.WORKLOADS)
    with pytest.raises(RuntimeError):
        with campaign.registration():
            assert campaign.w.WORKLOADS['ud'] == 'ud/libud.c'
            assert campaign.w.WORKLOADS['nettle-sha256'] == previous['nettle-sha256']
            raise RuntimeError('qualification fixture')
    assert campaign.w.WORKLOADS == previous


@pytest.mark.parametrize('workload', list(campaign.WORKLOADS))
def test_prepare_binds_unmodified_workload_and_checked_runtime(tmp_path, monkeypatch, workload):
    calibration_root = c.ROOT / 'results/2026-10-20-latency-calibration'

    def fake_base(reference, output, name, size):
        inputs = Path(output) / 'inputs'
        inputs.mkdir(parents=True)
        for filename in ('picorv32.v', 'soc_top.v', 'pcpi_single.v'):
            shutil.copyfile(calibration_root / 'inputs' / filename, inputs / filename)
        for filename in ('soc_link.ld', 'embench_memory.c', 'embench_firmware.c'):
            shutil.copyfile(c.ROOT / 'hardware' / filename, inputs / filename)
        shutil.copyfile(c.ROOT / 'benchmarks/embench/src' / campaign.w.WORKLOADS[name], inputs / 'program.c')
        return dict(context_id='unused', workload=name, pool_size=size, source_bindings={},
                    configuration={}, build_variant={}, compiler_flags=list(campaign.compact.FLAGS))

    monkeypatch.setattr(campaign.compact, 'prepare', fake_base)
    output = tmp_path / 'experiment'
    plan = campaign.prepare('unused', output, workload)
    inputs = output / 'inputs'
    assert c.unseal(output / 'plan.json') == plan
    assert c.digest({key: value for key, value in plan.items() if key != 'context_id'}) == plan['context_id']
    assert plan['memory_partition'] == campaign.partition.PARTITION
    assert plan['configuration']['stack_bytes'] == 3840
    assert plan['build_variant']['required_entrypoint'] == campaign.SOURCE
    assert plan['qualification_order'] == ['ud', 'nettle-sha256', 'statemate']
    assert plan['pool_size'] == 6
    assert plan['pool_rule'] == campaign.partition.POOL_RULE
    assert (inputs / 'program.c').read_bytes() == (c.ROOT / 'benchmarks/embench/src' / campaign.WORKLOADS[workload]).read_bytes()
    assert '_program_end <= 4224' in (inputs / 'soc_link.ld').read_text()
    assert '_writable_start' in (inputs / 'soc_link.ld').read_text()
    assert '0xdead0005' in (inputs / 'embench_memory.c').read_text()
    harness = (inputs / 'embench_firmware.c').read_text()
    if workload == 'nettle-sha256':
        assert 'byte<sizeof(expected_sha256)' in harness
        assert harness.index('int correct=verify_benchmark(result)') < harness.index('expected_sha256')
        assert harness.index('c1=cycles()') < harness.index('expected_sha256')
        # Match all 32 digest bytes against the unchanged upstream test vector.
        source = (inputs / 'program.c').read_text()
        import re
        expected = re.findall(r'0x[0-9a-f]{2}', campaign.SHA256_CHECK)
        upstream = re.findall(r'0x[0-9a-f]{2}', source[source.index('unsigned char hash[32]'):source.index('uint8_t buffer')])
        assert expected == upstream and len(expected) == 32
    else:
        assert 'expected_sha256' not in harness
    for name, expected in plan['inputs'].items():
        assert c.sha(inputs / name) == expected
    for name, expected in plan['source_bindings'].items():
        assert c.sha(output / 'sources' / name) == expected


@pytest.mark.parametrize('workload,size', [('crc32',6), ('ud',3), ('ud',True)])
def test_reject_unregistered_workload_or_changed_pool_before_prepare(tmp_path, workload, size):
    with pytest.raises(ValueError, match='registered workload and six-candidate'):
        campaign.prepare('unused', tmp_path / 'experiment', workload, size)
    assert not (tmp_path / 'experiment').exists()
