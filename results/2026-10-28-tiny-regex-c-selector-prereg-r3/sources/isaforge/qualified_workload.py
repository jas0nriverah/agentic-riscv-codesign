"""Plan-parameterized checked partitions for UD on the unchanged 8 KiB SoC.

Qualification is label-free. The closed runtime keeps at least 128 guard bytes
and 512 stack bytes, checks every SP update/RAM write, and uses both 800-million
cycle drivers. Native command deadlines and two build workers stay unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from . import bounded_workload as bounded, codesign as c
from . import extended_workload as extended, workload_experiment as w

SOURCE = 'isaforge/qualified_workload.py'
WORKLOADS = {'ud': 'ud/libud.c'}
POOL_SIZE = 6
CYCLE_LIMIT = 800000000
PARTITION = dict(ram_bytes=8192,program_limit=7168,stack_floor=7296,
                 stack_bytes=896,minimum_guard_bytes=128)
extract_pool = bounded.extract_pool
pool_for_audit = bounded.pool_for_audit
observer_sources = bounded.observer_sources


def partition_spec(program_limit=7168, stack_floor=7296):
    c.require(type(program_limit) is int and type(stack_floor) is int and
              0 < program_limit < stack_floor <= 7680 and
              program_limit % 16 == stack_floor % 16 == 0 and
              stack_floor-program_limit >= 128,
              'Partition requires 16-byte alignment, at least 128 guard bytes and 512 stack bytes in 8 KiB RAM')
    return dict(ram_bytes=8192,program_limit=program_limit,stack_floor=stack_floor,
                stack_bytes=8192-stack_floor,minimum_guard_bytes=128)


def checked_partition(spec):
    c.require(isinstance(spec,dict) and all(type(value) is int for value in spec.values()) and
              spec==partition_spec(spec.get('program_limit'),spec.get('stack_floor')),
              'Invalid checked partition specification')
    return dict(spec)


def monitor_source(spec=None):
    spec = checked_partition(PARTITION if spec is None else spec)
    original=(c.ROOT/'hardware/stack_monitor.hpp').read_text()
    old='return floor==4352 && writable_start<=program_end && program_end<=4224;'
    c.require(original.count(old)==1,'Pinned stack monitor configuration changed')
    return original.replace(old,f"return floor=={spec['stack_floor']} && writable_start<=program_end && program_end<={spec['program_limit']};")


@contextmanager
def registration(spec=None, *, entrypoint=False):
    previous=(bounded.WORKLOADS,bounded.SOURCE,bounded.PARTITION,bounded.monitor_source)
    bounded.WORKLOADS=WORKLOADS
    if entrypoint:
        spec=checked_partition(PARTITION if spec is None else spec)
        bounded.SOURCE=SOURCE
        bounded.PARTITION=spec
        bounded.monitor_source=lambda:monitor_source(spec)
    try:
        yield
    finally:
        bounded.WORKLOADS,bounded.SOURCE,bounded.PARTITION,bounded.monitor_source=previous


def memory_symbols(image, spec=None):
    with registration(spec,entrypoint=True):
        return bounded.memory_symbols(image)


def memory_image(binary, spec=None):
    with registration(spec,entrypoint=True):
        return bounded.memory_image(binary)


def validate_memory(raw, *, trapped=False, spec=None):
    with registration(spec,entrypoint=True):
        return bounded.validate_memory(raw,trapped=trapped)


def check_plan(plan):
    spec=checked_partition(plan.get('memory_partition'))
    with registration(spec,entrypoint=True):
        bounded.check_plan(plan)
    c.require(plan.get('simulation_cycle_limit')==CYCLE_LIMIT,'Different simulation cycle limit')


def validate_runtime_inputs(root, spec=None):
    inputs=Path(root)/'inputs'
    c.require((inputs/'stack_monitor.hpp').read_text()==monitor_source(spec),'Monitor derivation differs')
    for name in extended.DRIVERS:
        c.require((inputs/name).read_text()==extended.driver_source(name),'Qualified simulation driver differs: '+name)


def adapter_for_plan(plan):
    """Expose an immutable per-plan partition to the independent evidence audit."""
    check_plan(plan)
    spec=checked_partition(plan['memory_partition'])
    return SimpleNamespace(SOURCE=SOURCE,PARTITION=spec,check_plan=check_plan,
        monitor_source=lambda:monitor_source(spec),
        validate_runtime_inputs=lambda root:validate_runtime_inputs(root,spec),
        memory_symbols=lambda image:memory_symbols(image,spec),
        memory_image=lambda binary:memory_image(binary,spec),
        validate_memory=lambda raw,*,trapped=False:validate_memory(raw,trapped=trapped,spec=spec),
        extract_pool=extract_pool,pool_for_audit=pool_for_audit,audit=audit)


def prepare(reference,output,workload='ud',pool_size=POOL_SIZE,*,program_limit=7168,stack_floor=7296):
    c.require(workload in WORKLOADS and type(pool_size) is int and pool_size==POOL_SIZE,
              'Qualified campaign requires UD and six-candidate pool')
    spec=partition_spec(program_limit,stack_floor)
    with registration():
        plan=bounded.prepare(reference,output,workload,pool_size)
    plan.pop('context_id')
    output=Path(output);inputs=output/'inputs'
    link=inputs/'soc_link.ld'
    old='ASSERT(_program_end <= 6400, "firmware must leave the declared guard and 1664-byte stack")'
    text=link.read_text();c.require(text.count(old)==1,'Unexpected bounded linker contract')
    link.write_text(text.replace(old,f'ASSERT(_program_end <= {program_limit}, "firmware must leave the declared guard and {spec["stack_bytes"]}-byte stack")'))
    (inputs/'stack_monitor.hpp').write_text(monitor_source(spec))
    for name in extended.DRIVERS:
        (inputs/name).write_text(extended.driver_source(name))
    plan['memory_partition']=spec
    plan['configuration']['stack_bytes']=spec['stack_bytes']
    plan['simulation_cycle_limit']=CYCLE_LIMIT
    plan['partition_amendment']='Prelabel UD qualification after linker-map program/data/BSS end 7072; software double helpers are retained. Partition and simulator ceiling are explicit; full-input observed stack correctness is required before candidate labels.'
    plan['driver_derivation']='Exact cycle<200000000 to cycle<800000000 replacement only in both frozen simulation drivers.'
    plan['build_variant']['required_entrypoint']=SOURCE
    for name in (SOURCE,extended.SOURCE):
        plan['source_bindings'][name]=c.sha(c.ROOT/name)
        target=output/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(c.ROOT/name,target)
    plan['inputs']={p.name:c.sha(p) for p in inputs.iterdir()}
    plan['context_id']=c.digest(plan)
    c.seal(output/'plan.json',plan)
    validate_runtime_inputs(output,spec)
    return plan


class Evaluator(bounded.Evaluator):
    def __init__(self,root):
        w.Evaluator.__init__(self,root)
        check_plan(self.plan)
        self.partition=checked_partition(self.plan['memory_partition'])
        validate_runtime_inputs(self.root,self.partition)

    def compile_program(self,*args,**kwargs):
        with registration(self.partition,entrypoint=True):
            return super().compile_program(*args,**kwargs)

    def simulate(self,*args,**kwargs):
        with registration(self.partition,entrypoint=True):
            return super().simulate(*args,**kwargs)

    def discover(self):
        with registration(self.partition,entrypoint=True):
            return super().discover()

    def guard_controls(self):
        self.runner.check();base=self.root/'guard-controls'
        if (base/'controls.json').exists():
            return w.verify_cache(base,'controls.json')
        base.mkdir(exist_ok=True);results=[]
        underflow=self.partition['stack_floor']-4
        guard=self.partition['program_limit']
        for name,code,kind,address in [('stack-underflow',f'li sp,{underflow}','stack-pointer',underflow),
                ('guard-write',f'li t0,{guard}\nsw zero,0(t0)','ram-write',guard)]:
            folder=base/name;folder.mkdir();source=folder/'fixture.S'
            source.write_text('.section .text.start\n.global _start\n_start:\nli sp,8192\n'+code+'\nebreak\n')
            image=self.compile_program(folder/'firmware',source,fixture=True)
            datapath=folder/'candidate.v';datapath.write_text(c.generate_rtl('add(in0,in1)'))
            raw,_=self.simulate(folder/'guard-simulation',image,datapath,False,expected=10)
            c.require(raw['stack_initialized'] and raw['stack_violations']>0 and
                      raw['first_violation']['kind']==kind and raw['first_violation']['address']==address,
                      'Guard control did not detect expected violation')
            results.append(dict(name=name,detected_kind=kind,raw=raw))
        record=dict(controls=results,artifacts=w.artifact_hashes(base));c.seal(base/'controls.json',record)
        return record

    def collect(self):
        with registration(self.partition,entrypoint=True):
            result=super().collect()
        result['simulation_cycle_limit']=CYCLE_LIMIT
        result['limitations']=[item.replace('6400-byte program limit and 1664-byte observed stack',
            f"{self.partition['program_limit']}-byte program limit and {self.partition['stack_bytes']}-byte observed stack")
            for item in result['limitations']]
        c.seal(self.root/'report.json',result)
        return result


def audit(root):
    plan=c.unseal(Path(root)/'plan.json');check_plan(plan)
    spec=checked_partition(plan['memory_partition']);validate_runtime_inputs(root,spec)
    with registration(spec,entrypoint=True):
        result=bounded.audit(root)
    result['simulation_cycle_limit']=CYCLE_LIMIT
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','discover','baseline','collect','audit'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--reference-root',type=Path)
    parser.add_argument('--workload',choices=WORKLOADS,default='ud')
    parser.add_argument('--pool-size',type=int,default=POOL_SIZE)
    parser.add_argument('--program-limit',type=int,default=7168)
    parser.add_argument('--stack-floor',type=int,default=7296)
    args=parser.parse_args(argv)
    if args.command=='prepare':
        c.require(args.reference_root is not None,'--reference-root required')
        print(prepare(args.reference_root,args.root,args.workload,args.pool_size,
              program_limit=args.program_limit,stack_floor=args.stack_floor)['context_id'])
    elif args.command=='audit':
        print(json.dumps(audit(args.root),indent=2))
    else:
        evaluator=Evaluator(args.root)
        try:
            result=evaluator.measure('baseline') if args.command=='baseline' else getattr(evaluator,args.command)()
            print(json.dumps(dict(workload=evaluator.plan['workload'],command=args.command,context_id=result['context_id'])))
        finally:
            evaluator.runner.lock.close()


if __name__=='__main__':
    main()
