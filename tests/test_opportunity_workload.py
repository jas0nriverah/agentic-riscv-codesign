"""Public qualification rejects weak opportunities without candidate labels."""
import copy
from pathlib import Path
import shutil

import pytest

from isaforge import codesign as c, opportunity_workload as w
from scripts import qualify_opportunity_sources as q


def public_pool():
    return c.unseal(c.ROOT/'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes/controls11/model/public.json')


def set_counts(row,count):
    row['runs']=count
    features=row['latency_features']
    features['region_custom_instructions']=count
    features['dynamic_custom_cycles']=count*5
    features['replacement_execution_fraction']=count/features['baseline_instructions']


def test_gate_requires_both_conditions_on_the_same_formula_and_accepts_boundary():
    public=public_pool()
    for row in public:
        set_counts(row,1)
        row['latency_features']['estimated_cycle_reduction']=0.
    public[0]['latency_features']['estimated_cycle_reduction']=.005
    set_counts(public[1],10)
    assert w.opportunity_gate(public)['passed'] is False
    set_counts(public[0],10)
    gate=w.opportunity_gate(public)
    assert gate['passed'] and gate['qualifying_candidate_ids']==[public[0]['candidate_id']]
    assert gate['target_candidate_attempts']==0 and gate['measured_candidate_labels_used'] is False
    public[0]['speedup']=2.
    with pytest.raises(ValueError,match='non-public'):
        w.opportunity_gate(public)


def test_gate_rejects_wrong_pool_size_and_detects_a_changed_public_snapshot(tmp_path,monkeypatch):
    public=public_pool()
    assert w.opportunity_gate(public)['passed']
    with pytest.raises(ValueError,match='twelve'):
        w.opportunity_gate(public[:-1])
    monkeypatch.setattr(w,'discovery_public',lambda root:copy.deepcopy(public))
    gate=w.opportunity(tmp_path)
    assert w.check_opportunity(tmp_path)==gate
    with pytest.raises(ValueError,match='Preserve prior'):
        w.opportunity(tmp_path)
    public[0]['latency_features']['estimated_cycle_reduction']+=.001
    with pytest.raises(ValueError,match='unchanged public'):
        w.check_opportunity(tmp_path)


def test_failed_gate_is_preserved_before_exception(tmp_path,monkeypatch):
    public=public_pool()
    for row in public:
        row['latency_features']['estimated_cycle_reduction']=.00499
    monkeypatch.setattr(w,'discovery_public',lambda root:public)
    with pytest.raises(ValueError,match='rejected'):
        w.opportunity(tmp_path)
    assert c.unseal(tmp_path/'opportunity.json')['passed'] is False


def test_registry_source_pins_and_nested_global_restoration():
    assert list(w.WORKLOADS)==['cnt','bubblesort','prime','insertsort','tarai','recursion','janne_complex','cover']
    assert w.FAMILIES['insertsort']==w.FAMILIES['bubblesort']=='sorting'
    assert set(w.STATIC_REJECTIONS)=={'janne_complex'}
    assert set(w.b.SOURCES).issubset(w.GATE_SOURCES)
    assert set(w.GATE_SOURCES).issubset(q.SOURCES)
    for name,(_,digest) in w.WORKLOADS.items():
        assert c.sha(c.ROOT/w.program(name))==digest
    before=(w.bw.SOURCE,w.bw.POOL_SIZE,w.bw.WORKLOADS,w.bw.g.SOURCE,w.bw.g.POOL_SIZE)
    with pytest.raises(RuntimeError):
        with w.registration(),w.bw.registration('cnt'):
            assert w.bw.SOURCE==w.bw.g.SOURCE==w.SOURCE
            assert w.bw.POOL_SIZE==w.bw.g.POOL_SIZE==12
            with w.registration():
                raise RuntimeError('restore')
    assert (w.bw.SOURCE,w.bw.POOL_SIZE,w.bw.WORKLOADS,w.bw.g.SOURCE,w.bw.g.POOL_SIZE)==before


@pytest.fixture
def qualifier(tmp_path,monkeypatch):
    for name in q.SOURCES:
        target=tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(q.ROOT/name,target)
    monkeypatch.setattr(q,'ROOT',tmp_path)
    reference=tmp_path/q.REFERENCE
    c.seal(reference/'plan.json',{'context_id':'reference'})
    c.seal(tmp_path/q.HISTORY,{'independent_workload_groups':['consumed']})
    output,parent=tmp_path/q.OUTPUT,tmp_path/q.NATIVE_PARENT
    calls=[]
    control={'reject':set(),'interrupt':None}
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        name,phase=metadata['workload'],metadata['phase']
        protocol=c.unseal(output/'protocol.json')
        assert protocol['order']==list(w.WORKLOADS)
        assert protocol['stop_after_successful_families']==3
        assert protocol['minimum_calibrated_cycle_reduction']==.005
        assert argv==protocol['phase_commands'][name][phase]
        assert metadata['protocol_sha256']==c.sha(output/'protocol.json')
        calls.append((name,phase))
        native=parent/name
        c.seal(native/'plan.json',{'context_id':name,'workload':name})
        if phase=='freeze':
            c.seal(native/'evaluation-protocol.json',{'pool_names':[f'candidate_{i}' for i in range(12)],'maximum_candidate_attempts':12})
        if (name,phase)==control['interrupt']:
            raise KeyboardInterrupt('retained interrupt')
        rejected=(name,phase) in control['reject']
        record=dict(status='nonzero_exit' if rejected else 'success',returncode=int(rejected),
            durations=dict(monotonic_elapsed_seconds=1.,utc_elapsed_seconds=1.,clock_disagreement_detected=False))
        c.seal(folder/'record.json',record)
        return record
    monkeypatch.setattr(q.observed_command,'run',observe)
    monkeypatch.setattr(q.w,'validate_inputs',lambda root:c.unseal(Path(root)/'plan.json'))
    monkeypatch.setattr(q.w,'check_opportunity',lambda root:{'passed':True})
    return dict(output=output,parent=parent,reference=reference,calls=calls,control=control)


def qualify(f):
    return q.qualify(f['output'],f['parent'],f['reference'])


def test_qualification_stops_after_exactly_three_distinct_families(qualifier):
    f=qualifier
    result=qualify(f)
    assert result['status']=='accepted' and list(result['accepted'])==['cnt','bubblesort','prime']
    assert result['successful_families']==3 and result['target_candidate_attempts']==0
    assert f['calls']==[(name,phase) for name in ('cnt','bubblesort','prime') for phase in q.PHASES]
    with pytest.raises(ValueError,match='Fresh'):
        qualify(f)


def test_qualification_rejections_and_related_sorting_do_not_lower_gate(qualifier):
    f=qualifier
    f['control']['reject']={('cnt','discover'),('prime','opportunity'),('recursion','discover'),('cover','discover')}
    result=qualify(f)
    assert result['status']=='insufficient_qualified_families'
    assert list(result['accepted'])==['bubblesort','tarai']
    records={row['workload']:row for row in result['records']}
    assert records['insertsort']['status']=='related_family_skipped'
    assert records['janne_complex']['status']=='static_rejection'
    assert not any(name in ('insertsort','janne_complex') for name,_ in f['calls'])
    assert ('prime','baseline') not in f['calls']
    assert (f['output']/'prime/raw.tar.gz').is_file()


def test_interrupted_qualification_stops_and_retains_partial_archive(qualifier):
    f=qualifier
    f['control']['interrupt']=('cnt','discover')
    with pytest.raises(KeyboardInterrupt):
        qualify(f)
    assert f['calls']==[('cnt','prepare'),('cnt','discover')]
    result=c.unseal(f['output']/'qualification.json')
    assert result['status']=='interrupted' and result['target_candidate_attempts']==0
    assert (f['output']/'cnt/raw.tar.gz').is_file()
