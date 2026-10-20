"""Plan-parameterized memory contracts without native processor execution."""
from pathlib import Path

import pytest

from isaforge import qualified_workload as q, codesign as c


@pytest.mark.parametrize('limit,floor',[(7168,7296),(6656,6784),(7424,7552),(7552,7680)])
def test_closed_partition_supports_valid_predeclared_bounds(limit,floor):
    spec=q.partition_spec(limit,floor)
    assert q.checked_partition(spec)==spec
    assert spec['stack_bytes']>=512
    assert spec['stack_floor']-spec['program_limit']>=128
    original=(c.ROOT/'hardware/stack_monitor.hpp').read_text()
    assert q.monitor_source(spec).replace(f'floor=={floor}','floor==4352').replace(f'program_end<={limit}','program_end<=4224')==original


@pytest.mark.parametrize('limit,floor',[(7168,7280),(7169,7296),(7168,7696),
                                     (0,7296),(8192,7296),(7168.0,7296),(True,7296)])
def test_invalid_partitions_fail_before_any_native_work(limit,floor):
    with pytest.raises(ValueError):
        q.partition_spec(limit,floor)


def plan_for(spec):
    return dict(workload='ud',pool_size=6,memory_partition=spec,
                compiler_flags=list(q.bounded.compact.FLAGS),
                build_variant=dict(required_entrypoint=q.SOURCE),simulation_cycle_limit=800000000)


def test_per_plan_adapter_uses_its_own_memory_bounds(tmp_path):
    original=q.bounded.PARTITION
    spec=q.partition_spec(7424,7552)
    adapter=q.adapter_for_plan(plan_for(spec))
    (tmp_path/'symbols.txt').write_text('00001c00 B _program_end\n00001b00 D _writable_start\n')
    assert adapter.memory_symbols(tmp_path/'firmware.hex')==(7168,6912)
    raw=dict(stack_initialized=True,stack_violations=0,min_sp=7600,max_stack_bytes=592,
             stack_checked_cycles=100,first_violation=dict(kind='none',pc=0,address=0),trapped=False)
    assert adapter.validate_memory(raw)['stack_headroom_bytes']==48
    assert q.validate_memory(raw)['stack_headroom_bytes']==304
    assert q.bounded.PARTITION is original
    raw.update(min_sp=7500,max_stack_bytes=692)
    with pytest.raises(ValueError):
        adapter.validate_memory(raw)


def test_registration_restores_even_after_error():
    before=(q.bounded.WORKLOADS,q.bounded.SOURCE,q.bounded.PARTITION,q.bounded.monitor_source)
    with pytest.raises(RuntimeError):
        with q.registration(entrypoint=True):
            assert q.bounded.PARTITION==q.PARTITION
            assert q.bounded.SOURCE==q.SOURCE
            raise RuntimeError('restore')
    assert (q.bounded.WORKLOADS,q.bounded.SOURCE,q.bounded.PARTITION,q.bounded.monitor_source)==before


def test_prepare_binds_declared_partition_and_both_drivers(tmp_path,monkeypatch):
    hashes={name:c.sha(c.ROOT/name) for name in (q.bounded.SOURCE,q.extended.SOURCE)}
    def base(reference,output,workload,size):
        inputs=Path(output)/'inputs';inputs.mkdir(parents=True)
        (inputs/'soc_link.ld').write_text('ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")')
        return dict(context_id='old',workload=workload,pool_size=size,configuration={},
                    source_bindings=dict(hashes),build_variant={},compiler_flags=list(q.bounded.compact.FLAGS))
    monkeypatch.setattr(q.bounded,'prepare',base)
    output=tmp_path/'new'
    plan=q.prepare('unused',output,program_limit=7424,stack_floor=7552)
    q.check_plan(plan);adapter=q.adapter_for_plan(plan);adapter.validate_runtime_inputs(output)
    assert plan['configuration']['stack_bytes']==640
    assert c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id']
    assert '_program_end <= 7424' in (output/'inputs/soc_link.ld').read_text()
    for name,expected in plan['inputs'].items():
        assert c.sha(output/'inputs'/name)==expected
    assert all(c.sha(c.ROOT/name)==expected for name,expected in hashes.items())
    (output/'inputs/stack_monitor.hpp').write_text(q.monitor_source())
    with pytest.raises(ValueError,match='Monitor derivation'):
        adapter.validate_runtime_inputs(output)


@pytest.mark.parametrize('method',['compile_program','simulate','discover'])
def test_inherited_paths_obey_plan_partition_and_restore(monkeypatch,method):
    previous=q.bounded.PARTITION
    spec=q.partition_spec(7424,7552)
    def checked(self,*args,**kwargs):
        assert q.bounded.PARTITION==spec
        assert q.bounded.SOURCE==q.SOURCE
        return True
    monkeypatch.setattr(q.bounded.Evaluator,method,checked)
    evaluator=object.__new__(q.Evaluator);evaluator.partition=spec
    assert getattr(evaluator,method)() is True
    assert q.bounded.PARTITION is previous


def test_check_plan_rejects_changed_ram_stack_and_workload():
    for key,value in [('ram_bytes',16384),('stack_bytes',512),('minimum_guard_bytes',0),('stack_bytes',896.0)]:
        spec=dict(q.PARTITION);spec[key]=value
        with pytest.raises(ValueError):
            q.check_plan(plan_for(spec))
    plan=plan_for(dict(q.PARTITION));plan['workload']='crc32'
    with pytest.raises(ValueError):
        q.check_plan(plan)
