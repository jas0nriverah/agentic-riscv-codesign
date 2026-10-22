"""New multi-file source must keep the existing native/information boundaries."""
import copy
from pathlib import Path
import shutil
import pytest

from isaforge import codesign as c, tacle_workload as w
from scripts import qualify_tacle_bitcount as q


def public_pool():
    return c.unseal(c.ROOT/'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes/controls11/model/public.json')


def test_upstream_files_and_architecture_are_pinned():
    assert w.POOL_SIZE == 12
    assert w.PARTITION == w.g.q.partition_spec(6400,6528)
    assert w.PROTOCOL['minimum_calibrated_cycle_reduction'] == .005
    assert w.PROTOCOL['minimum_timed_replacements'] == 10
    for name,digest in w.UPSTREAM.items():
        assert c.sha(c.ROOT/w.BASE/name) == digest
    assert set(w.semantic.SOURCES).issubset(w.GATE_SOURCES)
    assert set(w.GATE_SOURCES).issubset(q.SOURCES)


def test_registration_restores_all_nested_globals_after_error():
    g = w.g
    before = (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,g.q.POOL_SIZE,
              g.q.bounded.POOL_SIZE,g.q.bounded.campaign.POOL_SIZE,w.evidence._public)
    with pytest.raises(RuntimeError):
        with w.registration():
            assert g.SOURCE == w.SOURCE and g.POOL_SIZE == 12
            assert g.NATIVE_LIMITS == w.NATIVE_LIMITS
            with w.registration():
                raise RuntimeError('restore')
    assert before == (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,g.q.POOL_SIZE,
                     g.q.bounded.POOL_SIZE,g.q.bounded.campaign.POOL_SIZE,w.evidence._public)


def test_gate_requires_joint_opportunity_and_rejects_labels():
    public = public_pool()
    for row in public:
        row['latency_features']['estimated_cycle_reduction'] = 0.
    public[0]['latency_features']['estimated_cycle_reduction'] = .005
    assert w.opportunity_gate(public)['passed']
    for row in public:
        row['runs'] = row['latency_features']['region_custom_instructions'] = 1
        row['latency_features']['dynamic_custom_cycles'] = 5
        row['latency_features']['replacement_execution_fraction'] = 1/row['latency_features']['baseline_instructions']
    public[1]['runs'] = public[1]['latency_features']['region_custom_instructions'] = 10
    public[1]['latency_features']['dynamic_custom_cycles'] = 50
    public[1]['latency_features']['replacement_execution_fraction'] = 10/public[1]['latency_features']['baseline_instructions']
    assert not w.opportunity_gate(public)['passed']
    public[0]['speedup'] = 2.
    with pytest.raises(ValueError, match='non-public'):
        w.opportunity_gate(public)
    with pytest.raises(ValueError, match='twelve'):
        w.opportunity_gate(public_pool()[:-1])


def test_failed_gate_is_preserved_and_never_overwritten(tmp_path,monkeypatch):
    public = public_pool()
    for row in public:
        row['latency_features']['estimated_cycle_reduction'] = .00499
    monkeypatch.setattr(w,'discovery_public',lambda root:copy.deepcopy(public))
    with pytest.raises(ValueError, match='rejected'):
        w.opportunity(tmp_path)
    assert c.unseal(tmp_path/'opportunity.json')['passed'] is False
    with pytest.raises(ValueError, match='Preserve'):
        w.opportunity(tmp_path)
    with pytest.raises(ValueError, match='unchanged opportunity'):
        w.check_opportunity(tmp_path)


def test_candidate_release_is_required_before_native_entry(tmp_path,monkeypatch):
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = tmp_path
    called = []
    monkeypatch.setattr(w,'check_opportunity',lambda root:called.append('gate'))
    monkeypatch.setattr(w,'check_release',lambda root:(_ for _ in ()).throw(ValueError('release absent')))
    monkeypatch.setattr(w.g.Evaluator,'measure',lambda self,name:called.append('native'))
    with pytest.raises(ValueError, match='release absent'):
        evaluator.measure('candidate_00')
    assert called == ['gate']
    evaluator.measure('baseline')
    assert called == ['gate','gate','native']


def test_qualification_argv_and_zero_attempt_guard(tmp_path):
    argv = q.phase_command('prepare',tmp_path/'native',tmp_path/'reference')
    assert argv[1:4] == ['-m','isaforge.tacle_workload','prepare']
    assert argv[-2:] == ['--reference-root',str(tmp_path/'reference')]
    assert '--reference-root' not in q.phase_command('discover',tmp_path/'native',tmp_path/'reference')
    with pytest.raises(ValueError,match='phase'):
        q.phase_command('measure',tmp_path/'native',tmp_path/'reference')
    c.seal(tmp_path/'attempt-ledger/candidate_00.json',{})
    with pytest.raises(ValueError,match='zero candidate'):
        q.zero(tmp_path)


@pytest.fixture
def qualifier(tmp_path,monkeypatch):
    for name in q.SOURCES:
        target = tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(q.ROOT/name,target)
    monkeypatch.setattr(q,'ROOT',tmp_path)
    reference = tmp_path/q.REFERENCE
    c.seal(reference/'plan.json',{'context_id':'reference'})
    c.seal(tmp_path/q.HISTORY,{'independent_workload_groups':['consumed']})
    output,native = tmp_path/q.OUTPUT,tmp_path/q.NATIVE
    control = dict(reject=None,interrupt=None)
    calls = []
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        phase = metadata['phase']
        protocol = c.unseal(output/'protocol.json')
        assert argv == protocol['phase_commands'][phase]
        assert protocol['minimum_calibrated_cycle_reduction'] == .005
        assert protocol['minimum_timed_replacements'] == 10
        assert protocol['pool_size'] == 12
        assert metadata['protocol_sha256'] == c.sha(output/'protocol.json')
        calls.append(phase)
        c.seal(native/'plan.json',{'context_id':'bitcount'})
        if phase == control['interrupt']:
            raise KeyboardInterrupt('preserved')
        if phase == 'freeze':
            c.seal(native/'evaluation-protocol.json',{'pool_names':[f'candidate_{i:02d}' for i in range(12)],'maximum_candidate_attempts':12})
        rejected = phase == control['reject']
        record = dict(status='nonzero_exit' if rejected else 'success',returncode=int(rejected),
            durations=dict(monotonic_elapsed_seconds=1.,utc_elapsed_seconds=1.,clock_disagreement_detected=False))
        c.seal(folder/'record.json',record)
        return record
    monkeypatch.setattr(q.observed_command,'run',observe)
    monkeypatch.setattr(q.w,'validate_inputs',lambda root:c.unseal(Path(root)/'plan.json'))
    monkeypatch.setattr(q.w,'check_opportunity',lambda root:{'passed':True})
    return dict(output=output,native=native,reference=reference,calls=calls,control=control)


def test_accepted_qualification_freezes_exact_pool_and_archives(qualifier):
    f = qualifier
    result = q.qualify(f['output'],f['native'],f['reference'])
    assert result['status'] == 'accepted' and result['target_candidate_attempts'] == 0
    assert f['calls'] == list(q.PHASES)
    assert (f['output']/'raw.tar.gz').is_file()
    assert c.unseal(f['output']/'manifest.json')['raw.tar.gz'] == c.sha(f['output']/'raw.tar.gz')
    with pytest.raises(ValueError, match='Fresh'):
        q.qualify(f['output'],f['native'],f['reference'])


@pytest.mark.parametrize('phase',['discover','opportunity'])
def test_rejected_qualification_never_routes_baseline_or_weakens_gate(qualifier,phase):
    f = qualifier
    f['control']['reject'] = phase
    result = q.qualify(f['output'],f['native'],f['reference'])
    assert result['status'] == 'rejected' and result['accepted'] == {}
    assert f['calls'] == list(q.PHASES)[:q.PHASES.index(phase)+1]
    assert 'baseline' not in f['calls']
    assert (f['output']/'raw.tar.gz').is_file()


def test_interrupted_qualification_preserves_partial_archive(qualifier):
    f = qualifier
    f['control']['interrupt'] = 'discover'
    with pytest.raises(KeyboardInterrupt):
        q.qualify(f['output'],f['native'],f['reference'])
    assert f['calls'] == ['prepare','discover']
    assert c.unseal(f['output']/'qualification.json')['status'] == 'interrupted'
    assert (f['output']/'raw.tar.gz').is_file()
