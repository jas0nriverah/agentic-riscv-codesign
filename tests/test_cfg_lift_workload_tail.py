"""No-native CFG Lift adapter/qualifier fixtures; original rejection untouched."""
import copy
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest

from isaforge import codesign as c, cfg_lift_workload as prior_w, cfg_lift_workload_tail as w, lift_workload as old
from scripts import qualify_cfg_lift_tail as q
from scripts.blind_campaign import _seal_manifest


def state():
    g=w.g
    return (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,g.ORIGINAL_EXTRACT,g.POOL_RULE,
            g.partition.EXTRACT,g.partition.POOL_RULE,g.q.POOL_SIZE,g.q.bounded.POOL_SIZE,
            g.q.bounded.campaign.POOL_SIZE,w.lowering.verify_lowering,w.evidence._public,
            dict(vars(w.base)),dict(vars(q.runner)),w._ACTIVE_ROOT.get())


def test_exact_original_hardware_inputs_and_numeric_gates_and_new_identity():
    assert w.SOURCE != old.SOURCE and w.PROTOCOL['schema'] != old.PROTOCOL['schema']
    assert w.WORKLOAD==old.WORKLOAD=='lift' and w.GROUP==old.GROUP=='tacle-lift'
    assert w.PROGRAM==old.PROGRAM and w.UPSTREAM==old.UPSTREAM and w.ABI==old.ABI
    assert w.PARTITION==old.PARTITION==w.g.q.partition_spec(6400,6528)
    assert w.NATIVE_LIMITS==old.NATIVE_LIMITS and w.POOL_SIZE==12
    assert w.PROTOCOL['original_input']==old.PROTOCOL['original_input']
    assert w.PROTOCOL['minimum_calibrated_cycle_reduction']==.005
    assert w.PROTOCOL['minimum_timed_replacements']==10
    assert w.PROTOCOL['correctness']==old.PROTOCOL['correctness']
    assert w.COVERAGE['compiler_abi_returns'] is True
    assert w.COVERAGE['firmware_trap_exit'] is True
    assert w.COVERAGE['firmware_trap_source_bindings']==w.FIRMWARE_TRAP_SOURCES
    assert set(w.FIRMWARE_TRAP_SOURCES)<=set(w.GATE_SOURCES)
    w.validate_firmware_context()
    assert w.PROTOCOL['lowering_verification']==w.cfg.VERIFICATION_SCHEMA
    assert w.PROTOCOL['unchanged_verifier'] is False
    assert w.PROTOCOL['unchanged_upstream_correctness_verifier'] is True
    assert w.CONTRACT in w.GATE_SOURCES and q.SOURCE in w.GATE_SOURCES
    assert set(w.PRIOR_CFG_REJECTION_FILES) <= set(w.GATE_SOURCES)
    assert set(w.cfg.SOURCES)|set(old.GATE_SOURCES) <= set(w.GATE_SOURCES)
    assert set(w.GATE_SOURCES) <= set(q.SOURCES)
    assert q.NATIVE=='generated/tacle-lift-cfg-tail-2026-10-25'
    assert q.OUTPUT=='results/2026-10-25-lift-cfg-tail-qualification'
    assert q.PHASES==q.runner.PHASES and q.PHASES==('prepare','discover','opportunity','baseline','public','freeze')


@pytest.mark.parametrize('exception',[RuntimeError,KeyboardInterrupt,SystemExit])
def test_nested_root_and_legacy_scopes_restore_all_globals_after_errors(tmp_path,exception):
    before=state()
    with pytest.raises(exception):
        with q.registration(),w.registration(tmp_path/'outer'):
            assert q.runner.w is w and q.runner.phase_command is q.phase_command
            assert w.g.SOURCE==w.SOURCE and w.g.ORIGINAL_EXTRACT is w._extract
            assert w.g.WORKLOADS=={'lift':'../../tacle/lift/isaforge_adapter.c'}
            assert w._ACTIVE_ROOT.get()==(tmp_path/'outer').resolve()
            with w.registration(tmp_path/'inner'):
                assert w._ACTIVE_ROOT.get()==(tmp_path/'inner').resolve()
            assert w._ACTIVE_ROOT.get()==(tmp_path/'outer').resolve()
            with old.registration():
                assert w.g.SOURCE==old.SOURCE
            assert w.g.SOURCE==w.SOURCE
            raise exception('restore')
    assert state()==before


def test_registration_changes_only_extraction_hook_not_guard_or_calibration(tmp_path,monkeypatch):
    before=state();original_guard=w.g.guard.filter_executable_candidates
    original_pool=w.g.partition.extract_pool
    sentinel=dict(executable_candidates=[],block_starts=[],fixture=True)
    captured=[]
    def extract(program,profile,sites,size,**kwargs):
        captured.append((program,profile,sites,size,kwargs));return copy.deepcopy(sentinel)
    monkeypatch.setattr(w.cfg,'extract',extract)
    with w.registration(tmp_path):
        result=w.g._guarded_extract({'program':1},{'profile':1},{0:{'site':0,'assembly':'addi x1,x0,1'}},12)
        assert w.g.guard.filter_executable_candidates is original_guard
        assert w.g.partition.extract_pool is original_pool
        assert result['relocation_guard']['schema']==w.g.guard.SCHEMA
        assert captured[0][3:]==(12,{'compiler_abi_returns':True,'firmware_trap_exit':True})
    assert state()==before


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    def guarded(reference,output,workload,pool_size,*,program_limit,stack_floor):
        assert workload=='lift' and pool_size==12 and (program_limit,stack_floor)==(6400,6528)
        assert w.g.WORKLOADS=={'lift':'../../tacle/lift/isaforge_adapter.c'}
        inputs=output/'inputs';inputs.mkdir(parents=True)
        shutil.copyfile(c.ROOT/w.PROGRAM,inputs/'program.c')
        shutil.copyfile(c.ROOT/'hardware/embench_firmware.c',inputs/'embench_firmware.c')
        for name in w.FIRMWARE_TRAP_SOURCES:
            filename=Path(name).name
            if filename=='checked_sim.cpp':
                (inputs/filename).write_text(w.g.q.extended.driver_source(filename))
            else:shutil.copyfile(c.ROOT/name,inputs/filename)
        g=w.g
        return dict(context_id='temporary',workload=workload,pool_size=pool_size,memory_partition=w.PARTITION,
            compiler_flags=list(g.q.bounded.compact.FLAGS),simulation_cycle_limit=g.CYCLE_LIMIT,
            native_limits=dict(w.NATIVE_LIMITS),build_variant={'required_entrypoint':w.SOURCE},
            relocation_guard=g.GUARD_RULE,pool_rule=g.POOL_RULE,
            source_bindings={name:c.sha(c.ROOT/name) for name in (w.SOURCE,g.QUALIFIED_SOURCE,g.guard.SOURCE,
                g.attempts.SOURCE,g.EVIDENCE_SOURCE,*g.AUTHENTICATION_SOURCES)})
    monkeypatch.setattr(w.g,'prepare',guarded)
    root=tmp_path/'native';plan=w.prepare(tmp_path/'reference',root)
    return root,plan


def test_prepare_binds_new_context_and_old_entrypoints_reject_it(prepared):
    root,plan=prepared
    assert w.validate_inputs(root)==plan and plan['coverage_context']==w.COVERAGE
    assert plan['runtime_support']==w.RUNTIME_SUPPORT
    assert plan['opportunity_source_protocol']==w.PROTOCOL
    assert plan['upstream']==old.upstream_record()
    for name in w.GATE_SOURCES:
        assert c.sha(root/'sources'/name)==plan['source_bindings'][name]==c.sha(c.ROOT/name)
    assert c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id']
    for check in (old.check_plan,w.base.check_plan,w.g.check_plan):
        with pytest.raises(ValueError):check(plan)


@pytest.mark.parametrize('mutation',[
    lambda p:p['coverage_context'].update(compiler_abi_returns=False),
    lambda p:p['coverage_context'].update(firmware_trap_exit=False),
    lambda p:p['coverage_context']['firmware_trap_source_bindings'].update({'hardware/soc_top.v':'other'}),
    lambda p:p.pop('coverage_context'),
    lambda p:p['opportunity_source_protocol'].update(lowering_verification='old-verifier'),
    lambda p:p['opportunity_source_protocol']['original_input'].update(controller_iterations=1000),
    lambda p:p.update(memory_partition=w.g.q.partition_spec(7168,7296)),
    lambda p:p['source_bindings'].update({'isaforge/cfg_liveness.py':'wrong-source'}),
    *[lambda p,name=Path(name).name:p['inputs'].update({name:'resealed-changed-firmware'})
      for name in w.FIRMWARE_TRAP_SOURCES],
])
def test_coverage_flag_input_hardware_or_bound_source_tamper_rejected(prepared,mutation):
    _,plan=prepared;altered=copy.deepcopy(plan);mutation(altered)
    altered.pop('context_id');altered['context_id']=c.digest(altered)
    with pytest.raises(ValueError):w.check_plan(altered)


def test_candidate_dispatch_and_legacy_measure_collect_cli_remain_closed(tmp_path,monkeypatch):
    calls=[];before=state();obj=object.__new__(w.Evaluator);obj.root=tmp_path
    monkeypatch.setattr(w.g.Evaluator,'measure',lambda self,name:calls.append(name))
    with pytest.raises(ValueError,match='Candidate dispatch disabled'):obj.measure('candidate_00')
    assert calls==[]
    for command in ('measure','collect'):
        with pytest.raises(SystemExit):w.main([command,'--root',str(tmp_path)])
    assert state()==before


@pytest.mark.parametrize('source',list(w.FIRMWARE_TRAP_SOURCES))
def test_firmware_opt_in_requires_each_exact_bound_source(source,monkeypatch,tmp_path):
    original=c.sha
    monkeypatch.setattr(c,'sha',lambda path:'changed' if Path(path)==c.ROOT/source else original(path))
    with pytest.raises(ValueError,match='Exact startup/IRQ-disabled/trap-terminal'):
        w._extract({}, {}, {}, 12)
    with pytest.raises(ValueError,match='Exact startup/IRQ-disabled/trap-terminal'):
        w.prepare(tmp_path/'reference',tmp_path/'native')
    assert not (tmp_path/'native').exists()


def saved_fixture(root):
    """Actual synthetic assembly, raw RV32 words, marker map and saved profile."""
    folder=root/'discovery/attempt-000';(folder/'marked').mkdir(parents=True);(folder/'original').mkdir()
    assembly='.type fixture,@function\nfixture:\n sltu x13,x0,x13\n or x15,x13,x15\n bne x12,x14,.Larm\n addi x13,x0,0\n jal x0,.Lend\n.Larm:\n addi x13,x0,0\n.Lend:\n jalr x0,x1,0\n.size fixture,.-fixture\n'
    (folder/'program.s').write_text(assembly);marked,sites=w.lowering.mark_assembly(assembly);(folder/'marked.S').write_text(marked)
    words=[(13<<20)|(3<<12)|(13<<7)|0x33,(15<<20)|(13<<15)|(6<<12)|(15<<7)|0x33,
           (14<<20)|(12<<15)|(1<<12)|(6<<8)|0x63,(13<<7)|0x13,0x0080006f,(13<<7)|0x13,0x8067]
    (folder/'marked/disassembly.txt').write_text('00000000 <fixture>:\n'+''.join(f'{i*4:08x}: {word:08x} decoded\n' for i,word in enumerate(words)))
    (folder/'marked/symbols.txt').write_text(''.join(f'{i*4:08x} t __isaforge_begin_{i}\n{i*4+4:08x} t __isaforge_end_{i}\n' for i in range(7)))
    for name in ('marked/firmware.hex','original/firmware.hex'):(folder/name).write_text('same original baseline bytes\n')
    profile=dict(region_counts={str(i*4):10 for i in range(7)},total_counts={str(i*4):10 for i in range(7)},block_starts=[0],words=[0,0,10000,71])
    c.write(folder/'profile/simulation.json',profile)
    program,actual_profile,site_map=w.saved_discovery_inputs(root)
    extracted=w._extract(program,actual_profile,site_map,12)
    candidate=copy.deepcopy(next(r for r in extracted['executable_candidates'] if r['formula']=='or(sltu(0,in0),in1)'))
    return folder,program,actual_profile,site_map,extracted,candidate


@pytest.fixture
def verification(tmp_path,monkeypatch):
    root=tmp_path/'native';folder,program,profile,site_map,extraction,candidate=saved_fixture(root)
    plan=dict(pool_size=12,context_id='bound-context')
    monkeypatch.setattr(w,'validate_inputs',lambda p:copy.deepcopy(plan))
    candidate['candidate_id']=c.digest([plan['context_id'],candidate['formula']])
    return dict(root=root,folder=folder,program=program,profile=profile,site_map=site_map,
                extraction=extraction,candidate=candidate,plan=plan)


def test_verifier_rederives_root_inputs_and_distinct_certificate_after_native_envelopes(verification):
    f=verification;before=state()
    result=w.verify_from_root(f['root'],f['candidate'],f['program'],f['extraction']['block_starts'],vectors=4)
    assert result['schema']==w.cfg.VERIFICATION_SCHEMA and result['passed']
    assert result['blocks'][0]['permitted_dead_register_differences']==[13]
    native=copy.deepcopy(f['candidate']);native.update(lowering_check=result,assembly='ignored-envelope.S',assembly_sha256='native-enforces')
    assert w.verify_from_root(f['root'],native,f['program'],f['extraction']['block_starts'],vectors=4)==result
    with w.registration(f['root']):
        assert w.lowering.verify_lowering(native,f['program'],f['extraction']['block_starts'],4)==result
    assert state()==before


@pytest.mark.parametrize('kind',['source','firmware','profile','certificate','program','starts','identity','unknown-envelope'])
def test_verifier_rejects_saved_source_certificate_program_or_candidate_tampering(verification,kind):
    f=verification;row=copy.deepcopy(f['candidate']);program=copy.deepcopy(f['program']);starts=list(f['extraction']['block_starts'])
    if kind=='source':(f['folder']/'program.s').write_text((f['folder']/'program.s').read_text().replace('sltu','slt',1))
    elif kind=='firmware':(f['folder']/'marked/firmware.hex').write_text('changed')
    elif kind=='profile':
        profile=copy.deepcopy(f['profile']);profile['region_counts']={str(k):20 for k in program};profile['total_counts']=copy.deepcopy(profile['region_counts']);profile['words'][3]=141;c.write(f['folder']/'profile/simulation.json',profile)
    elif kind=='certificate':row['liveness_binding']['certificate_sha256']='forged'
    elif kind=='program':program[0]['rd']=14
    elif kind=='starts':starts.append(4)
    elif kind=='identity':row['candidate_id']='other-context'
    else:row['proof_from_candidate']={'passed':True}
    with pytest.raises(ValueError):w.verify_from_root(f['root'],row,program,starts,vectors=2)


def test_callback_without_scoped_root_fails_and_ambiguous_attempts_are_not_selected(verification):
    f=verification
    with w.registration():
        with pytest.raises(ValueError,match='Root-bound'):w.lowering.verify_lowering(f['candidate'],f['program'],f['extraction']['block_starts'])
    (f['root']/'discovery/attempt-001').mkdir()
    with pytest.raises(ValueError,match='One original'):w.saved_discovery_inputs(f['root'])


def write_history(root,successes=110):
    old_rows=[dict(candidate_id=f'old{i}') for i in range(99)];old_failed=[dict(candidate_id=f'old-failed{i}') for i in range(3)]
    old_value=dict(successful_labels=99,rows=old_rows,failed_attempts=old_failed)
    rows=old_rows+[dict(candidate_id=f'new{i}') for i in range(successes-99)]
    failed=old_failed+[dict(candidate_id=f'new-failed{i}') for i in range(111-successes)]
    value=dict(successful_labels=len(rows),rows=rows,failed_attempts=failed,total_candidate_attempts=114,
        independent_workload_groups=['tacle-g723-enc',*[f'g{i}' for i in range(12)]],contexts={f'c{i}':{} for i in range(14)},
        preserved_original_rows_digest=c.digest(old_rows),preserved_original_failed_attempts_digest=c.digest(old_failed))
    for name,obj in ((q.PRESERVED_HISTORY,old_value),(q.HISTORY,value)):
        c.seal(root/name,obj);_seal_manifest((root/name).parent)
    return value


def write_rejection(root):
    folder=root/q.ORIGINAL_REJECTION
    protocol=dict(copy.deepcopy(old.PROTOCOL),schema=old.PROTOCOL['schema']+'-qualification')
    c.seal(folder/'protocol.json',protocol)
    result=dict(protocol_sha256=c.sha(folder/'protocol.json'),status='rejected',accepted={},target_candidate_attempts=0,
        records=[dict(workload='lift',family='tacle-lift',status='rejected',failed_phase='discover',
            commands=[dict(phase=p,record={'returncode':code}) for p,code in (('prepare',0),('discover',1))])])
    c.seal(folder/'qualification.json',result);_seal_manifest(folder)
    return result


def write_prior_cfg_rejection(root):
    folder=root/q.PRIOR_CFG_REJECTION
    protocol=dict(copy.deepcopy(prior_w.PROTOCOL),schema=prior_w.PROTOCOL['schema']+'-qualification')
    c.seal(folder/'protocol.json',protocol)
    result=dict(schema=protocol['schema']+'-result',
        protocol_sha256=c.sha(folder/'protocol.json'),status='rejected',accepted={},target_candidate_attempts=0,
        records=[dict(workload='lift',family='tacle-lift',status='rejected',failed_phase='discover',
            commands=[dict(phase=p,record={'returncode':code}) for p,code in (('prepare',0),('discover',1))])])
    c.seal(folder/'qualification.json',result);_seal_manifest(folder)
    return result


@pytest.fixture
def qualifier(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'ROOT',tmp_path);write_history(tmp_path);write_rejection(tmp_path);write_prior_cfg_rejection(tmp_path)
    actual=c.ROOT
    for name in q.SOURCES:
        target=tmp_path/name
        if target.exists():continue
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(actual/name,target)
    reference=tmp_path/q.REFERENCE;c.seal(reference/'plan.json',{'reference':True})
    output,native=tmp_path/q.OUTPUT,tmp_path/q.NATIVE;calls=[];control=dict(reject=None,interrupt=None)
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        phase=metadata['phase'];calls.append(phase)
        assert q.runner.w is w and argv==q.phase_command(phase,native,reference) and timeout_seconds==3600
        protocol=c.unseal(output/'protocol.json')
        assert protocol['coverage_context']==w.COVERAGE and protocol['memory_partition']==old.PARTITION
        assert protocol['source_bindings'][q.REJECTION_FILES[1]]==c.sha(tmp_path/q.REJECTION_FILES[1])
        c.seal(native/'plan.json',{'context_id':'cfg-context'})
        if phase==control['interrupt']:raise KeyboardInterrupt('preserve')
        if phase=='freeze':c.seal(native/'evaluation-protocol.json',dict(pool_names=[f'candidate_{i:02d}' for i in range(12)],maximum_candidate_attempts=12))
        rejected=phase==control['reject'];record=dict(status='nonzero_exit' if rejected else 'success',returncode=int(rejected),durations=dict(monotonic_elapsed_seconds=1.,utc_elapsed_seconds=1.,clock_disagreement_detected=False))
        c.seal(folder/'record.json',record);return record
    monkeypatch.setattr(q.runner.observed_command,'run',observe)
    monkeypatch.setattr(w,'validate_inputs',lambda root:c.unseal(Path(root)/'plan.json'))
    monkeypatch.setattr(w,'check_opportunity',lambda root:{'passed':True})
    return dict(output=output,native=native,reference=reference,calls=calls,control=control)


def test_qualifier_preserves_history_rejection_and_zero_label_gate(qualifier):
    f=qualifier;before=state();original=c.sha(q.ROOT/q.ORIGINAL_REJECTION/'qualification.json')
    assert q.validate_history()['successful_labels']==110
    assert q.validate_original_rejection()['original_rejection_remains_final']
    assert q.validate_prior_cfg_rejection()['prior_cfg_rejection_remains_final']
    result=q.qualify(f['output'],f['native'],f['reference'])
    assert result['status']=='accepted' and result['target_candidate_attempts']==0
    assert f['calls']==list(q.PHASES) and (f['output']/'raw.tar.gz').is_file()
    assert c.sha(q.ROOT/q.ORIGINAL_REJECTION/'qualification.json')==original and state()==before
    with pytest.raises(ValueError,match='Fresh'):q.qualify(f['output'],f['native'],f['reference'])


@pytest.mark.parametrize('phase',['discover','opportunity'])
def test_new_rejection_preserved_without_baseline_or_retry(qualifier,phase):
    f=qualifier;f['control']['reject']=phase;result=q.qualify(f['output'],f['native'],f['reference'])
    assert result['status']=='rejected' and result['accepted']=={} and 'baseline' not in f['calls']
    assert f['calls']==list(q.PHASES)[:q.PHASES.index(phase)+1] and (f['output']/'raw.tar.gz').is_file()


def test_interrupt_restores_runner_and_keeps_archive(qualifier):
    f=qualifier;f['control']['interrupt']='discover';before=state()
    with pytest.raises(KeyboardInterrupt):q.qualify(f['output'],f['native'],f['reference'])
    assert state()==before and (f['output']/'raw.tar.gz').is_file()
    assert c.unseal(f['output']/'qualification.json')['status']=='interrupted'


@pytest.mark.parametrize('successes',[99,105,111])
def test_history_requires_exact_final110_labels_not_old_or_alternate_counts(tmp_path,monkeypatch,successes):
    monkeypatch.setattr(q,'ROOT',tmp_path);write_history(tmp_path,successes)
    with pytest.raises(ValueError,match='110-label'):q.validate_history()


def test_missing_or_relabelled_original_rejection_blocks_before_any_dispatch(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'ROOT',tmp_path);write_history(tmp_path)
    with pytest.raises(FileNotFoundError):q.qualify(tmp_path/'out',tmp_path/'native',tmp_path/'reference')
    result=write_rejection(tmp_path);result['status']='accepted'
    c.seal(tmp_path/q.ORIGINAL_REJECTION/'qualification.json',result);_seal_manifest(tmp_path/q.ORIGINAL_REJECTION)
    with pytest.raises(ValueError,match='Preserved original'):q.validate_original_rejection()
    assert not (tmp_path/'out').exists()


def test_missing_or_relabelled_prior_cfg_rejection_blocks_before_any_dispatch(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'ROOT',tmp_path);write_history(tmp_path);write_rejection(tmp_path)
    with pytest.raises(FileNotFoundError):q.qualify(tmp_path/'out',tmp_path/'native',tmp_path/'reference')
    write_prior_cfg_rejection(tmp_path)
    result=c.unseal(tmp_path/q.PRIOR_CFG_REJECTION/'qualification.json');result['status']='accepted'
    c.seal(tmp_path/q.PRIOR_CFG_REJECTION/'qualification.json',result);_seal_manifest(tmp_path/q.PRIOR_CFG_REJECTION)
    with pytest.raises(ValueError,match='Preserved prior CFG-context'):q.validate_prior_cfg_rejection()
    assert not (tmp_path/'out').exists()
