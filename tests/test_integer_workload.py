"""Fixed-six source identity, isolation and mocked bounded qualification."""
import copy
from pathlib import Path
import shutil

import pytest

from isaforge import integer_workload as w, codesign as c
from scripts import qualify_integer_workload as q


def plan_for(name='expint'):
    g = w.bw.g
    bindings = (w.SOURCE, w.ORIGINAL_BLIND_SOURCE, w.GUARDED_SOURCE, g.QUALIFIED_SOURCE,
                g.guard.SOURCE, g.attempts.SOURCE, g.EVIDENCE_SOURCE, *g.AUTHENTICATION_SOURCES,
                w.program(name), w.LICENSE)
    plan = dict(workload=name, pool_size=6, memory_partition=dict(w.PARTITION),
        compiler_flags=list(g.q.bounded.compact.FLAGS), simulation_cycle_limit=g.CYCLE_LIMIT,
        native_limits=dict(w.bw.NATIVE_LIMITS), build_variant={'required_entrypoint':w.SOURCE},
        relocation_guard=dict(g.GUARD_RULE), pool_rule=g.POOL_RULE,
        source_bindings={key:c.sha(c.ROOT/key) for key in bindings}, workload_group='beebs-'+name,
        upstream=dict(suite='BEEBS',commit=w.UPSTREAM_COMMIT,source=w.program(name),source_sha256=w.WORKLOADS[name][1]),
        inputs={'program.c':w.WORKLOADS[name][1]},
        integer_source_protocol=dict(schema='isaforge-integer-six-v1',order=['expint','bubblesort'],
                                     pool_size=6,unchanged_input=True,unchanged_partition=True))
    plan['context_id']=c.digest(plan)
    return plan


@pytest.mark.parametrize('name',w.WORKLOADS)
def test_original_sources_verifiers_and_new_pool_are_bound(name):
    assert c.sha(c.ROOT/w.program(name))==w.WORKLOADS[name][1]
    text=(c.ROOT/w.program(name)).read_text()
    if name=='expint':
        assert 'n = 50;' in text and 'x = 1;' in text and 'expected = 3883;' in text
    else:
        assert '#define NUMELEMS 100' in text and '#define MAXDIM   (NUMELEMS+1)' in text
        assert 'if (Array[i] != expected[i])' in text
    plan=plan_for(name);w.check_plan(plan)
    with pytest.raises(ValueError):w.bw.check_plan(plan)
    assert plan['memory_partition']['program_limit']==6400 and plan['memory_partition']['stack_floor']==6528


def test_nested_registration_restores_both_adapter_and_downstream_pool_globals():
    g=w.bw.g
    before=(w.bw.SOURCE,w.bw.POOL_SIZE,w.bw.WORKLOADS,g.POOL_SIZE,g.q.POOL_SIZE,g.q.bounded.POOL_SIZE,g.q.bounded.campaign.POOL_SIZE)
    with pytest.raises(RuntimeError):
        with w.registration():
            assert w.bw.POOL_SIZE==6 and list(w.bw.WORKLOADS)==['expint','bubblesort']
            with w.bw.registration({'workload':'expint'}):
                assert g.POOL_SIZE==g.q.POOL_SIZE==g.q.bounded.POOL_SIZE==g.q.bounded.campaign.POOL_SIZE==6
                with w.registration():assert w.bw.SOURCE==w.SOURCE
            raise RuntimeError('restore')
    assert (w.bw.SOURCE,w.bw.POOL_SIZE,w.bw.WORKLOADS,g.POOL_SIZE,g.q.POOL_SIZE,g.q.bounded.POOL_SIZE,g.q.bounded.campaign.POOL_SIZE)==before


@pytest.mark.parametrize('field',['pool','order','partition','old_binding','source','context'])
def test_fixed_six_protocol_rejects_self_consistent_changes(field):
    plan=plan_for()
    if field=='pool':plan['pool_size']=12
    elif field=='order':plan['integer_source_protocol']['order'].reverse()
    elif field=='partition':plan['memory_partition']=w.bw.g.q.partition_spec(6272,6400)
    elif field=='old_binding':plan['source_bindings'].pop(w.ORIGINAL_BLIND_SOURCE)
    elif field=='source':plan['inputs']['program.c']='0'*64
    if field!='context':plan['context_id']=c.digest({k:v for k,v in plan.items() if k!='context_id'})
    else:plan['context_id']='0'*64
    with pytest.raises(ValueError):w.check_plan(plan)


def test_prepare_binds_original_adapter_and_new_identity(tmp_path,monkeypatch):
    initial=plan_for();initial.pop('integer_source_protocol');initial['source_bindings'].pop(w.ORIGINAL_BLIND_SOURCE)
    initial['context_id']=c.digest({k:v for k,v in initial.items() if k!='context_id'})
    def prepare(reference,output,name):
        assert w.bw.POOL_SIZE==6 and name=='expint'
        inputs=output/'inputs';inputs.mkdir()
        shutil.copyfile(c.ROOT/w.program(name),inputs/'program.c')
        (inputs/'embench_firmware.c').write_text(w.bw.harness_source(name))
        return copy.deepcopy(initial)
    monkeypatch.setattr(w.bw,'prepare',prepare)
    plan=w.prepare('reference',tmp_path,'expint')
    assert plan['context_id']!=initial['context_id'] and w.validate_inputs(tmp_path)==plan
    assert (tmp_path/'sources'/w.ORIGINAL_BLIND_SOURCE).is_file()


@pytest.fixture
def qualifier(tmp_path,monkeypatch):
    actual=q.ROOT
    for name in q.SOURCES:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(actual/name,target)
    monkeypatch.setattr(q,'ROOT',tmp_path)
    ref=tmp_path/q.REFERENCE;c.seal(ref/'plan.json',{'context_id':'reference'})
    for name in q.REJECTIONS:c.seal(tmp_path/name/'manifest.json',{})
    output,parent=tmp_path/q.OUTPUT,tmp_path/q.NATIVE_PARENT
    calls=[];control={'reject':set(),'interrupt':None}
    def run(argv,folder,*,cwd,metadata,timeout_seconds):
        name,phase=metadata['workload'],metadata['phase'];protocol=c.unseal(output/'protocol.json')
        assert protocol['order']==['expint','bubblesort'] and protocol['pool_size']==6
        assert protocol['stop_after_successful_sources']==1 and argv==protocol['phase_commands'][name][phase]
        assert set(protocol['source_bindings'])==set(q.SOURCES)
        assert metadata['protocol_sha256']==c.sha(output/'protocol.json')
        calls.append((name,phase));folder.mkdir(parents=True)
        (folder/'stdout.txt').write_text('stdout');(folder/'stderr.txt').write_text('stderr')
        rejected=(name,phase) in control['reject'];interrupted=(name,phase)==control['interrupt']
        record=dict(status='interrupted' if interrupted else 'nonzero_exit' if rejected else 'success',
            returncode=None if interrupted else 1 if rejected else 0,
            durations=dict(monotonic_elapsed_seconds=2.,utc_elapsed_seconds=2.,clock_disagreement_detected=False))
        c.seal(folder/'record.json',record)
        native=parent/name;native.mkdir(parents=True,exist_ok=True)
        c.seal(native/'plan.json',{'workload':name,'context_id':'context-'+name})
        if phase=='freeze':c.seal(native/'evaluation-protocol.json',{'pool_names':['candidate_'+str(i) for i in range(6)],'maximum_candidate_attempts':6})
        if interrupted:raise KeyboardInterrupt('stop')
        return record
    monkeypatch.setattr(q.observed_command,'run',run)
    monkeypatch.setattr(q.workload,'validate_inputs',lambda root:c.unseal(Path(root)/'plan.json'))
    return dict(output=output,parent=parent,reference=ref,calls=calls,control=control)


def qualify(f):return q.qualify(f['output'],f['parent'],f['reference'])


def test_first_success_stops_and_uses_compatible_accepted_mapping(qualifier):
    f=qualifier;r=qualify(f)
    assert r['accepted']=={'expint':str((f['parent']/'expint').relative_to(q.ROOT))}
    assert f['calls']==[('expint',p) for p in q.PHASES]
    assert r['records'][0]['status']=='accepted' and r['records'][0]['context_id']=='context-expint'
    assert r['target_candidate_attempts']==0 and r['successful_sources']==1
    assert r['recorded_subprocess_monotonic_seconds']==10.
    assert (f['output']/'expint/archive-manifest.json').exists()
    assert not (f['output']/'bubblesort').exists()


def test_declared_fallback_runs_only_after_failed_first_source(qualifier):
    f=qualifier;f['control']['reject'].add(('expint','discover'));r=qualify(f)
    assert list(r['accepted'])==['bubblesort']
    assert f['calls']==[('expint','prepare'),('expint','discover')]+[('bubblesort',p) for p in q.PHASES]
    assert r['records'][0]['status']=='rejected' and r['records'][0]['failed_phase']=='discover'
    assert (f['output']/'expint/raw.tar.gz').exists()


def test_both_rejections_stop_without_weakening_or_retry(qualifier):
    f=qualifier;f['control']['reject']={('expint','discover'),('bubblesort','discover')};r=qualify(f)
    assert r['accepted']=={} and r['status']=='no_source_qualified'
    assert len(f['calls'])==4 and c.unseal(f['output']/'protocol.json')['pool_size']==6
    assert (f['output']/'manifest.json.sha256').exists()


def test_interrupt_does_not_advance_to_next_source(qualifier):
    f=qualifier;f['control']['interrupt']=('expint','discover')
    with pytest.raises(KeyboardInterrupt):qualify(f)
    r=c.unseal(f['output']/'qualification.json')
    assert r['status']=='interrupted' and len(r['records'])==1
    assert r['records'][0]['commands'][-1]['record']['status']=='interrupted'
    assert (f['output']/'expint/raw.tar.gz').exists()


def test_existing_run_or_changed_source_blocks_all_dispatch(qualifier):
    f=qualifier;source=q.ROOT/w.program('expint');source.write_text(source.read_text()+'\n')
    with pytest.raises(ValueError,match='Pinned original'):qualify(f)
    assert not f['output'].exists() and f['calls']==[]
    f['output'].mkdir(parents=True)
    with pytest.raises(ValueError,match='Fresh'):qualify(f)
