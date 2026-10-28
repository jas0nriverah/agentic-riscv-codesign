"""Relocation-safe discovery and checked one-attempt processor evaluation.

Fresh plans use the existing extraction, calibrated stratification, lowering and
8 KiB evaluator. Symbolic source operands are excluded before stratification;
every cached/paid discovery is independently rederived before measurement.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from . import assembly_lowering as lowering, codesign as c
from . import partitioned_workload as partition, qualified_workload as q
from . import relocation_guard as guard, workload_experiment as w
from . import guarded_attempts as attempts
from .guarded_attempts import OneAttemptMixin

SOURCE='isaforge/guarded_workload.py'
QUALIFIED_SOURCE='isaforge/qualified_workload.py'
EVIDENCE_SOURCE='isaforge/guarded_evidence.py'
AUTHENTICATION_SOURCES=('isaforge/campaign_evidence.py','isaforge/prospective_inputs.py')
WORKLOADS={'edn':'edn/libedn.c','ud':'ud/libud.c',
           'nettle-sha256':'nettle-sha256/nettle-sha256.c'}
POOL_SIZE=6
CYCLE_LIMIT=q.CYCLE_LIMIT
NATIVE_LIMITS=dict(commands=240,seconds=2400,command_seconds=180,workers=1,
                   build_workers=2,candidate_attempts=1)
ORIGINAL_EXTRACT=partition.EXTRACT
POOL_RULE='Reject symbolic/unsupported removed source operands before calibration filtering; '+partition.POOL_RULE
GUARD_RULE=dict(schema=guard.SCHEMA,stage='before_calibration_and_stratification',required=True)


def _guarded_extract(program,profile,site_map,size):
    original=ORIGINAL_EXTRACT(program,profile,site_map,size)
    return guard.filter_executable_candidates(original,list(site_map.values()))


@contextmanager
def registration(*,entrypoint=True,extraction=True):
    previous=(q.WORKLOADS,q.SOURCE,partition.EXTRACT,partition.POOL_RULE)
    q.WORKLOADS=WORKLOADS
    if entrypoint:
        q.SOURCE=SOURCE
    if extraction:
        partition.EXTRACT=_guarded_extract
        partition.POOL_RULE=POOL_RULE
    try:
        yield
    finally:
        q.WORKLOADS,q.SOURCE,partition.EXTRACT,partition.POOL_RULE=previous


def extract_pool(program,profile,site_map,size,calibration):
    with registration():
        return partition.extract_pool(program,profile,site_map,size,calibration)


def check_plan(plan):
    c.require(isinstance(plan,dict) and plan.get('workload') in WORKLOADS and
              type(plan.get('pool_size')) is int and plan['pool_size']==POOL_SIZE,
              'Guarded entrypoint requires registered workload and six-candidate pool')
    q.checked_partition(plan.get('memory_partition'))
    c.require(plan.get('compiler_flags')==list(q.bounded.compact.FLAGS) and
              plan.get('simulation_cycle_limit')==CYCLE_LIMIT,'Different compiler/simulator protocol')
    limits=plan.get('native_limits')
    c.require(isinstance(limits,dict) and limits==NATIVE_LIMITS and
              all(type(value) is int for value in limits.values()),
              'Guarded one-attempt budget marker required')
    c.require(plan.get('build_variant',{}).get('required_entrypoint')==SOURCE and
              plan.get('relocation_guard')==GUARD_RULE and plan.get('pool_rule')==POOL_RULE,
              'Not a guarded extraction context')
    bindings=plan.get('source_bindings',{})
    c.require(isinstance(bindings,dict) and all(name in bindings for name in
              (SOURCE,QUALIFIED_SOURCE,guard.SOURCE,attempts.SOURCE,EVIDENCE_SOURCE,*AUTHENTICATION_SOURCES)),
              'Guarded runtime source bindings missing')


def validate_runtime_inputs(root,spec=None):
    root=Path(root)
    if spec is None:
        spec=c.unseal(root/'plan.json')['memory_partition']
    q.validate_runtime_inputs(root,q.checked_partition(spec))


def authenticate_plan(root):
    """Portable source/input validation; native executable identities are separate."""
    root=Path(root).resolve();plan=c.unseal(root/'plan.json');check_plan(plan)
    c.require(c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'],
              'Invalid guarded context identity')
    for name,expected in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==expected,'Guarded source changed: '+name)
    for name,expected in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name)==expected,'Guarded input changed: '+name)
    validate_runtime_inputs(root,plan['memory_partition'])
    return plan


class Runner(w.Runner):
    """Only this runner accepts the explicit one-attempt marker."""
    def __init__(self,root):
        try:
            super().__init__(root)
        except BaseException:
            if hasattr(self,'lock'):
                self.lock.close()
            raise

    def check(self):
        plan=authenticate_plan(self.root)
        c.require(plan==self.plan,'Plan on disk changed')
        for tool in plan['tools'].values():
            c.require(c.sha(tool['path'])==tool['sha256'],'Native tool changed')


def prepare(reference,output,workload='ud',pool_size=POOL_SIZE,*,program_limit=7168,stack_floor=7296):
    c.require(workload in WORKLOADS and type(pool_size) is int and pool_size==POOL_SIZE,
              'Guarded entrypoint requires registered workload and six-candidate pool')
    q.partition_spec(program_limit,stack_floor)
    with registration(entrypoint=False,extraction=False):
        plan=q.prepare(reference,output,workload,pool_size,
                       program_limit=program_limit,stack_floor=stack_floor)
    plan.pop('context_id');output=Path(output)
    plan['native_limits']=dict(NATIVE_LIMITS)
    plan['pool_rule']=POOL_RULE
    plan['relocation_guard']=dict(GUARD_RULE)
    plan['build_variant']['required_entrypoint']=SOURCE
    plan['partition_amendment']='Fresh relocation-guarded context; declared checked partition and complete original benchmark input. No earlier frozen pool is modified or retried.'
    for name in (SOURCE,QUALIFIED_SOURCE,guard.SOURCE,attempts.SOURCE,EVIDENCE_SOURCE,*AUTHENTICATION_SOURCES):
        plan['source_bindings'][name]=c.sha(c.ROOT/name)
        target=output/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(c.ROOT/name,target)
    plan['context_id']=c.digest(plan)
    c.seal(output/'plan.json',plan)
    authenticate_plan(output)
    return plan


def authenticate_discovery(root):
    """Reconstruct the full guarded pool; never open candidate measurements."""
    root=Path(root).resolve();plan=authenticate_plan(root)
    found=w.verify_cache(root/'discovery','discovery.json')
    c.require(found.get('context_id')==plan['context_id'] and found.get('workload')==plan['workload'],
              'Guarded discovery context differs')
    image=(root/found['baseline_image']).resolve()
    c.require(image.is_relative_to(root/'discovery') and image.parent.name=='marked',
              'Baseline image outside guarded discovery')
    folder=image.parent.parent
    marked,sites=lowering.mark_assembly((folder/'program.s').read_text())
    c.require(marked==(folder/'marked.S').read_text(),'Original marked assembly changed')
    c.require(c.sha(image)==c.sha(folder/'original/firmware.hex'),'Marked baseline changed')
    site_map=lowering.map_sites(sites,(image.parent/'symbols.txt').read_text())
    program=lowering.read_program((image.parent/'disassembly.txt').read_text())
    profile_path=(root/found['profile']).resolve()
    c.require(profile_path==folder/'profile/simulation.json','Profile outside guarded discovery')
    profile=c.read(profile_path)
    spec=plan['memory_partition']
    c.require(found.get('memory_check')==q.validate_memory(profile,spec=spec),
              'Discovery memory observations differ')
    c.require(found.get('baseline_performance')==w.validate_execution(profile),
              'Discovery baseline performance differs')
    derived=extract_pool(program,profile,site_map,plan['pool_size'],
                         c.read(root/'inputs/latency-calibration.json'))
    for key,value in derived.items():
        if key not in ('pool','executable_candidates'):
            c.require(found.get(key)==value,'Guarded discovery metadata differs: '+key)
    c.require(len(found['pool'])==len(derived['pool'])==POOL_SIZE and
              len(found['executable_candidates'])==len(derived['executable_candidates']),
              'Guarded candidate count differs')
    for expected,recorded in zip(derived['executable_candidates'],found['executable_candidates']):
        c.require(all(recorded.get(k)==v for k,v in expected.items()),'Guarded full candidate list differs')
    for expected,candidate in zip(derived['pool'],found['pool']):
        c.require(all(candidate.get(k)==v for k,v in expected.items()),'Guarded shortlist differs')
        c.require(candidate['candidate_id']==c.digest([plan['context_id'],candidate['formula']]),
                  'Guarded candidate identity differs')
        guard.require_relocation_free(candidate,sites)
        c.require(lowering.verify_lowering(candidate,program,found['block_starts'])==candidate['lowering_check'],
                  'Guarded lowering check differs')
        for occurrence in candidate['occurrences']:
            c.require([site_map[int(pc,16)]['site'] for pc in occurrence['pcs']]==occurrence['sites'],
                      'Guarded source-PC map differs')
        lowered=(root/candidate['assembly']).resolve()
        c.require(lowered.is_relative_to(folder) and lowered.read_text()==lowering.lower(marked,candidate) and
                  c.sha(lowered)==candidate['assembly_sha256'],'Guarded lowered assembly differs')
    return found


def adapter_for_plan(plan):
    check_plan(plan);spec=q.checked_partition(plan['memory_partition'])
    return SimpleNamespace(SOURCE=SOURCE,PARTITION=spec,check_plan=check_plan,
        monitor_source=lambda:q.monitor_source(spec),
        validate_runtime_inputs=lambda root:validate_runtime_inputs(root,spec),
        memory_symbols=lambda image:q.memory_symbols(image,spec),
        memory_image=lambda binary:q.memory_image(binary,spec),
        validate_memory=lambda raw,*,trapped=False:q.validate_memory(raw,trapped=trapped,spec=spec),
        extract_pool=extract_pool,audit=audit)


def baseline_public(root):
    from . import campaign_evidence as evidence
    root=Path(root).resolve()
    evidence.prior_inputs.reject_candidate_measurements(root)
    c.require(not list((root/'measurements').glob('candidate_*/attempt-*')),
              'Candidate attempt exists before prospective freeze')
    adapter=adapter_for_plan(c.unseal(root/'plan.json'))
    plan,discovery,baseline,receipts,memory=evidence.authenticate_baseline(root,adapter)
    c.require(authenticate_discovery(root)==discovery,'Guarded discovery changed during authentication')
    calibration=evidence._calibration(root)
    c.require(c.read(root/'inputs/latency-calibration.json')==calibration,'Calibration projection differs')
    public=evidence._public(root,plan,discovery,baseline,calibration)
    context=evidence.prior_inputs.context(root,plan,receipts)
    context['baseline_provenance']['memory_check']=memory
    context['workload_group']='embench-'+plan['workload']
    context['context_transfer']='Relocation-guarded source pool with explicit checked compiler/memory context.'
    before=dict(workload='embench-'+plan['workload'],context_id=plan['context_id'],
        artifacts={name:c.sha(root/name) for name in evidence.BASELINE_FILES},
        commands_sha256=c.sha(root/'commands.json'),receipts=receipts,
        pool_names=[row['name'] for row in discovery['pool']],public_sha256=c.digest(public),
        baseline_lut4=baseline['resources']['lut4_count'])
    return public,context,before


def audit(root):
    authenticate_discovery(root)
    with registration():
        return q.audit(root)


class Evaluator(OneAttemptMixin,q.Evaluator):
    def __init__(self,root):
        self.runner=Runner(root)
        try:
            self.root,self.plan=self.runner.root,self.runner.plan
            self.inputs=self.root/'inputs'
            self.tools={k:v['path'] for k,v in self.plan['tools'].items()}
            self.partition=q.checked_partition(self.plan['memory_partition'])
            self.cache_hits=0
        except BaseException:
            self.runner.lock.close()
            raise

    def discover(self):
        with registration():
            result=super().discover()
        c.require(authenticate_discovery(self.root)==result,'Guarded discovery changed after execution/cache access')
        return result

    def measure(self,name):
        # The lifecycle mixin remains authoritative for attempts and freeze.
        self.discover()
        return super().measure(name)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','discover','baseline','freeze','measure','collect','audit'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--reference-root',type=Path)
    parser.add_argument('--workload',choices=WORKLOADS,default='ud')
    parser.add_argument('--pool-size',type=int,default=POOL_SIZE)
    parser.add_argument('--program-limit',type=int,default=7168)
    parser.add_argument('--stack-floor',type=int,default=7296)
    parser.add_argument('--candidate')
    parser.add_argument('--scope',choices=('engineering-validation','dataset-expansion'),default='engineering-validation')
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
            if args.command=='freeze':
                result=attempts.freeze_pool(evaluator,scope=args.scope)
            elif args.command=='baseline':
                result=evaluator.measure('baseline')
            elif args.command=='measure':
                c.require(args.candidate is not None,'--candidate required')
                result=evaluator.measure(args.candidate)
            else:
                result=getattr(evaluator,args.command)()
            print(json.dumps(result,indent=2))
        finally:
            evaluator.runner.lock.close()


if __name__=='__main__':
    main()
