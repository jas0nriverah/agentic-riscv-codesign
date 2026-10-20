"""Driver-only cycle-budget extension, without running native tools."""
from pathlib import Path

import pytest

from isaforge import extended_workload as extended, codesign as c


@pytest.mark.parametrize('name',extended.DRIVERS)
def test_driver_change_is_exactly_cycle_ceiling(name):
    original=(c.ROOT/'hardware'/name).read_text()
    derived=extended.driver_source(name)
    assert derived.replace('cycle<800000000','cycle<200000000')==original
    assert 'cycle<800000000' in derived


def test_registration_restores_entrypoint_and_workloads_after_error():
    previous,source=extended.bounded.WORKLOADS,extended.bounded.SOURCE
    partition,monitor=extended.bounded.PARTITION,extended.bounded.monitor_source
    with pytest.raises(RuntimeError):
        with extended.registration(entrypoint=True):
            assert extended.bounded.WORKLOADS==extended.WORKLOADS
            assert extended.bounded.SOURCE==extended.SOURCE
            assert extended.bounded.PARTITION==extended.PARTITION
            raise RuntimeError('restore')
    assert extended.bounded.WORKLOADS is previous
    assert extended.bounded.SOURCE==source
    assert extended.bounded.PARTITION is partition
    assert extended.bounded.monitor_source is monitor


def test_prepare_binds_both_drivers_and_original_sources(tmp_path,monkeypatch):
    source=extended.bounded.SOURCE
    hashes={name:c.sha(c.ROOT/name) for name in (source,extended.bounded.campaign.SOURCE)}
    def base(reference,output,workload,size):
        inputs=Path(output)/'inputs';inputs.mkdir(parents=True)
        (inputs/'stack_monitor.hpp').write_text(extended.monitor_source())
        (inputs/'soc_link.ld').write_text('ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")')
        return dict(context_id='old',workload=workload,pool_size=size,
                    source_bindings=dict(hashes),memory_partition=dict(extended.PARTITION),
                    configuration={},
                    compiler_flags=list(extended.bounded.compact.FLAGS),build_variant={})
    monkeypatch.setattr(extended.bounded,'prepare',base)
    output=tmp_path/'new'
    plan=extended.prepare('unused',output,'statemate')
    extended.check_plan(plan)
    extended.validate_runtime_inputs(output)
    assert c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id']
    assert plan['source_bindings'][source]==hashes[source]
    assert plan['simulation_cycle_limit']==800000000
    assert plan['configuration']['stack_bytes']==1408
    assert '_program_end <= 6656' in (output/'inputs/soc_link.ld').read_text()
    for name,expected in plan['inputs'].items():
        assert c.sha(output/'inputs'/name)==expected
    assert all(c.sha(c.ROOT/name)==expected for name,expected in hashes.items())
    (output/'inputs/soc_sim.cpp').write_text((c.ROOT/'hardware/soc_sim.cpp').read_text())
    with pytest.raises(ValueError,match='driver differs'):
        extended.validate_runtime_inputs(output)


def test_check_plan_rejects_other_ceiling_and_workload():
    plan=dict(workload='edn',pool_size=6,memory_partition=dict(extended.PARTITION),
              compiler_flags=list(extended.bounded.compact.FLAGS),
              build_variant=dict(required_entrypoint=extended.SOURCE),simulation_cycle_limit=800000000)
    extended.check_plan(plan)
    plan['simulation_cycle_limit']=200000000
    with pytest.raises(ValueError,match='cycle limit'):
        extended.check_plan(plan)
    plan['simulation_cycle_limit']=800000000;plan['workload']='ud'
    with pytest.raises(ValueError,match='bounded campaign'):
        extended.check_plan(plan)


def test_memory_uses_extended_partition_and_restores_bounded_context(tmp_path):
    original=extended.bounded.PARTITION
    (tmp_path/'symbols.txt').write_text('00001914 B _program_end\n00001900 D _writable_start\n')
    assert extended.memory_symbols(tmp_path/'firmware.hex')==(6420,6400)
    raw=dict(stack_initialized=True,stack_violations=0,min_sp=7000,max_stack_bytes=1192,
             stack_checked_cycles=100,first_violation=dict(kind='none',pc=0,address=0),trapped=False)
    assert extended.validate_memory(raw)['stack_headroom_bytes']==216
    raw.update(min_sp=6783,max_stack_bytes=1409)
    with pytest.raises(ValueError):
        extended.validate_memory(raw)
    assert extended.bounded.PARTITION is original
    original_header=(c.ROOT/'hardware/stack_monitor.hpp').read_text()
    assert extended.monitor_source().replace('floor==6784','floor==4352').replace('program_end<=6656','program_end<=4224')==original_header


@pytest.mark.parametrize('method',['compile_program','simulate','discover'])
def test_inherited_native_path_sees_extended_partition_without_mutation(monkeypatch,method):
    previous=extended.bounded.PARTITION
    def checked(self,*args,**kwargs):
        assert extended.bounded.PARTITION==extended.PARTITION
        assert extended.bounded.SOURCE==extended.SOURCE
        assert extended.bounded.monitor_source()==extended.monitor_source()
        return 'checked'
    monkeypatch.setattr(extended.bounded.Evaluator,method,checked)
    evaluator=object.__new__(extended.Evaluator)
    assert getattr(evaluator,method)()=='checked'
    assert extended.bounded.PARTITION is previous
