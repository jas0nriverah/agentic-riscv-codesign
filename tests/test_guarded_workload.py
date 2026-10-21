"""Reachable pre-stratification protection and immutable native contracts."""
import copy
import fcntl
from pathlib import Path
import shutil

import pytest

from isaforge import guarded_workload as g, codesign as c


def plan_template():
    return dict(workload='ud',pool_size=6,memory_partition=g.q.partition_spec(),
        compiler_flags=list(g.q.bounded.compact.FLAGS),simulation_cycle_limit=800000000,
        native_limits=dict(g.NATIVE_LIMITS),build_variant=dict(required_entrypoint=g.SOURCE),
        relocation_guard=dict(g.GUARD_RULE),pool_rule=g.POOL_RULE,
        source_bindings={name:c.sha(c.ROOT/name) for name in
            (g.SOURCE,g.QUALIFIED_SOURCE,g.guard.SOURCE,g.attempts.SOURCE,g.EVIDENCE_SOURCE,*g.AUTHENTICATION_SOURCES)},
        tools={},inputs={})


def test_guard_is_reachable_before_rank_stratification(monkeypatch):
    candidates=[];sites={};program={}
    for i in range(9):
        pcs=[4*(2*i+j) for j in range(2)]
        candidates.append(dict(name=f'candidate_{i:02d}',formula=str(i),
            occurrences=[dict(sites=[2*i,2*i+1],pcs=[hex(pc) for pc in pcs])]))
        for j,pc in enumerate(pcs):
            sites[pc]=dict(site=2*i+j,assembly='add a0,a0,a1')
            program[pc]=dict(op='add')
    # The old top-merit choice is unsafe. Its position must be removed BEFORE
    # stratification; otherwise unsafe candidate00 survives or the pool shrinks.
    sites[0]['assembly']='lui s0,%hi(a)'
    raw=dict(executable_candidates=candidates,executable_formula_count=9,pool=candidates[:6])
    before=copy.deepcopy(raw)
    monkeypatch.setattr(g,'ORIGINAL_EXTRACT',lambda *args:raw)
    calibration=dict(rule_matches_all=True,semantic_checks_passed=True,stock_trap_control_passed=True,
        rows=[dict(op='add',immediate=None,cycles=4),dict(op='pcpi',immediate=None,cycles=5)])
    result=g.extract_pool(program,{},sites,6,calibration)
    assert [row['name'] for row in result['pool']]==[
        'candidate_01','candidate_02','candidate_04','candidate_05','candidate_07','candidate_08']
    assert result['relocation_guard']['input_executable_count']==9
    assert result['relocation_guard']['rejected_count']==1
    assert result['eligible_formula_count']==8
    assert raw==before


def test_nested_guard_context_restores_every_global_after_failure(monkeypatch):
    before=(g.q.WORKLOADS,g.q.SOURCE,g.partition.EXTRACT,g.partition.POOL_RULE)
    with pytest.raises(RuntimeError):
        with g.registration():
            with g.registration():
                assert g.partition.EXTRACT is g._guarded_extract
                assert g.q.SOURCE==g.SOURCE
            assert g.partition.EXTRACT is g._guarded_extract
            raise RuntimeError('restore')
    assert (g.q.WORKLOADS,g.q.SOURCE,g.partition.EXTRACT,g.partition.POOL_RULE)==before


def test_legacy_runner_rejects_guarded_budget_before_subprocess(tmp_path,monkeypatch):
    plan=plan_template();plan['context_id']=c.digest(plan);c.seal(tmp_path/'plan.json',plan)
    legacy=object.__new__(g.w.Runner);legacy.root=tmp_path;legacy.plan=plan;legacy.receipts=[]
    def forbidden(*args,**kwargs):
        pytest.fail('Legacy runner reached subprocess launch')
    monkeypatch.setattr(c.subprocess,'Popen',forbidden)
    with pytest.raises(ValueError,match='Unsupported budget'):
        legacy.run(['/fixture/native-tool'],tmp_path/'native.log')
    assert not (tmp_path/'native.log').exists()


def test_new_runner_releases_lock_when_plan_initialization_fails(tmp_path):
    plan=plan_template();plan['native_limits'].pop('candidate_attempts')
    plan['context_id']=c.digest(plan);c.seal(tmp_path/'plan.json',plan)
    with pytest.raises(ValueError,match='budget marker'):
        g.Runner(tmp_path)
    with (tmp_path/'.native.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(stream,fcntl.LOCK_UN)


@pytest.mark.parametrize('field,value',[
    ('native_limits',dict(commands=240,seconds=2400,command_seconds=180,workers=1,build_workers=2)),
    ('native_limits',dict(g.NATIVE_LIMITS,candidate_attempts=True)),
    ('build_variant',dict(required_entrypoint=g.QUALIFIED_SOURCE)),
    ('relocation_guard',dict(g.GUARD_RULE,required=False)),
    ('pool_rule','unguarded original rule'),('pool_size',True),('workload','crc32'),
])
def test_old_or_mutated_contract_cannot_enter_guarded_runner(field,value):
    plan=plan_template();plan[field]=value
    with pytest.raises(ValueError):
        g.check_plan(plan)


@pytest.mark.parametrize('workload',list(g.WORKLOADS))
def test_prepare_binds_all_immutable_runtime_sources_and_restores_registry(tmp_path,monkeypatch,workload):
    previous=g.q.WORKLOADS;original_source=g.q.SOURCE
    def base(reference,output,name,size,*,program_limit,stack_floor):
        assert g.q.WORKLOADS==g.WORKLOADS and g.q.SOURCE==original_source
        inputs=Path(output)/'inputs';inputs.mkdir(parents=True)
        spec=g.q.partition_spec(program_limit,stack_floor)
        (inputs/'stack_monitor.hpp').write_text(g.q.monitor_source(spec))
        for name in g.q.extended.DRIVERS:
            (inputs/name).write_text(g.q.extended.driver_source(name))
        result=plan_template();result.update(workload=workload,memory_partition=spec,context_id='old')
        result['inputs']={p.name:c.sha(p) for p in inputs.iterdir()}
        return result
    monkeypatch.setattr(g.q,'prepare',base)
    root=tmp_path/'fresh'
    plan=g.prepare('unused',root,workload)
    assert g.q.WORKLOADS is previous and g.q.SOURCE==original_source
    assert plan['native_limits']['candidate_attempts']==1
    assert plan['context_id']==c.digest({k:v for k,v in plan.items() if k!='context_id'})
    for name in (g.SOURCE,g.QUALIFIED_SOURCE,g.guard.SOURCE,g.attempts.SOURCE,g.EVIDENCE_SOURCE,*g.AUTHENTICATION_SOURCES):
        assert c.sha(root/'sources'/name)==plan['source_bindings'][name]
    (root/'inputs/soc_sim.cpp').write_text('changed simulator')
    with pytest.raises(ValueError,match='input changed'):
        g.authenticate_plan(root)


def recorded_guarded_discovery(tmp_path):
    """Create only new replay fixtures from authentic baseline-only local data."""
    prior=c.ROOT/'generated/qualified-ud-2026-10-20'
    if not (prior/'discovery/discovery.json').exists():
        pytest.skip('Preserved local processor inputs are not restored')
    root=tmp_path/'guarded';root.mkdir()
    old=c.unseal(prior/'discovery/discovery.json')
    old_image=prior/old['baseline_image'];old_folder=old_image.parent.parent
    folder=root/'discovery/attempt-000';folder.mkdir(parents=True)
    shutil.copytree(prior/'inputs',root/'inputs')
    for name in ('original','marked'):
        shutil.copytree(old_folder/name,folder/name)
    for name in ('program.s','marked.S'):
        shutil.copyfile(old_folder/name,folder/name)
    (folder/'profile').mkdir()
    shutil.copyfile(prior/old['profile'],folder/'profile/simulation.json')
    plan=plan_template();plan['inputs']={p.name:c.sha(p) for p in (root/'inputs').iterdir()}
    plan['context_id']=c.digest(plan);c.seal(root/'plan.json',plan)
    image=root/old['baseline_image']
    marked,sites=g.lowering.mark_assembly((folder/'program.s').read_text())
    mapping=g.lowering.map_sites(sites,(image.parent/'symbols.txt').read_text())
    program=g.lowering.read_program((image.parent/'disassembly.txt').read_text())
    result=g.extract_pool(program,c.read(root/old['profile']),mapping,6,
                          c.read(root/'inputs/latency-calibration.json'))
    for candidate in result['pool']:
        candidate['candidate_id']=c.digest([plan['context_id'],candidate['formula']])
        candidate['lowering_check']=g.lowering.verify_lowering(candidate,program,result['block_starts'])
        output=folder/(candidate['name']+'.S');output.write_text(g.lowering.lower(marked,candidate))
        candidate['assembly']=str(output.relative_to(root));candidate['assembly_sha256']=c.sha(output)
    result.update(context_id=plan['context_id'],workload='ud',baseline_performance=old['baseline_performance'],
        baseline_image=old['baseline_image'],baseline_binary_identical=True,mapped_statements=len(mapping),
        memory_check=old['memory_check'],profile=old['profile'],artifacts=g.w.artifact_hashes(root/'discovery'))
    c.seal(root/'discovery/discovery.json',result)
    return root,result


def test_cached_discovery_rederives_guarded_pool_and_blocks_unsafe_original_before_measure(tmp_path,monkeypatch):
    root,result=recorded_guarded_discovery(tmp_path)
    assert g.authenticate_discovery(root)==result
    unsafe=c.unseal(c.ROOT/'generated/qualified-ud-2026-10-20/discovery/discovery.json')['pool'][-1]
    changed=copy.deepcopy(result);changed['pool'][-1]=unsafe
    c.seal(root/'discovery/discovery.json',changed)
    evaluator=object.__new__(g.Evaluator);evaluator.root=root
    monkeypatch.setattr(g.q.Evaluator,'discover',lambda self:changed)
    def forbidden(*args,**kwargs):
        pytest.fail('Unsafe cached original reached the paid attempt lifecycle')
    monkeypatch.setattr(g.OneAttemptMixin,'measure',forbidden)
    with pytest.raises(ValueError,match='shortlist differs'):
        evaluator.measure(unsafe['name'])


def test_resealed_lowered_source_mutation_is_rejected_semantically(tmp_path):
    root,result=recorded_guarded_discovery(tmp_path)
    candidate=result['pool'][0];path=root/candidate['assembly']
    path.write_text(path.read_text()+'\n# mutation with resealed inventory\n')
    result['artifacts']={name:value for name,value in g.w.artifact_hashes(root/'discovery').items()
                         if name not in ('discovery.json','discovery.json.sha256')}
    candidate['assembly_sha256']=c.sha(path)
    c.seal(root/'discovery/discovery.json',result)
    with pytest.raises(ValueError,match='lowered assembly differs'):
        g.authenticate_discovery(root)
