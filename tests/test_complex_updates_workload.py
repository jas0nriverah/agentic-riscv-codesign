"""Original-input complex_updates qualification preserves guarded and zero-label boundaries."""
import copy
from pathlib import Path
import shutil
import pytest

from isaforge import codesign as c, complex_updates_workload as w
from scripts import qualify_complex_updates as q


def public_pool():
    # Synthetic public schema only: no historical corpus/model/measurement files.
    rows = []
    for index in range(12):
        row = {name: 0 for name in w.prior.b.PUBLIC_KEYS}
        row.update(candidate_id=f'candidate_{index:02d}', benchmark='synthetic-public',
                   formula='add(in0,slli(in1,2))', size=2, runs=10, places=1,
                   saved=10, saved_percent=1., depth=2, tree_op_count=2,
                   input_count=2, constant_count=1, unique_constant_count=1,
                   max_abs_constant=2, op_add=1, op_slli=1)
        row['latency_features'] = {name: 0 for name in w.prior.b.LATENCY_KEYS}
        row['latency_features'].update(baseline_cycles=10000, baseline_instructions=1000,
            baseline_cpi=10., replacement_execution_fraction=.01,
            occurrence_size_min=2, occurrence_size_max=2, dynamic_software_cycles=100,
            dynamic_custom_cycles=50, estimated_saved_cycles=50,
            estimated_cycle_reduction=.005, estimated_speedup=10000/9950,
            region_custom_instructions=10)
        rows.append(row)
    return rows


@pytest.fixture(autouse=True)
def prohibit_native_models_and_measured_reads(monkeypatch):
    import subprocess
    import builtins
    def forbidden(*args, **kwargs):
        raise AssertionError('Native dispatch or model operation forbidden in offline tests')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(w.prior.b.SpeedupPredictor, 'fit', forbidden)
    monkeypatch.setattr(w.prior.b.SpeedupPredictor, 'predict', forbidden)
    monkeypatch.setattr(w.prior.b.SpeedupRanker, 'fit', forbidden)
    monkeypatch.setattr(w.prior.b.HardwareSurrogate, 'fit', forbidden)
    monkeypatch.setattr(w.prior.semantic.SemanticHardwareSurrogate, 'fit', forbidden)
    original = builtins.open
    def guarded_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            path = Path(file)
            assert not path.is_relative_to(c.ROOT/'results'), 'Historical result/model files forbidden'
        return original(file, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded_open)
    original_path_open = Path.open
    def guarded_path_open(path, *args, **kwargs):
        assert not path.is_relative_to(c.ROOT/'results'), 'Historical result/model files forbidden'
        return original_path_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_path_open)


def test_upstream_files_and_architecture_are_pinned():
    assert w.POOL_SIZE == 12
    assert w.PARTITION == w.g.q.partition_spec(6400,6528)
    assert w.PROTOCOL['minimum_calibrated_cycle_reduction'] == .005
    assert w.PROTOCOL['minimum_timed_replacements'] == 10
    for name,digest in w.UPSTREAM.items():
        assert c.sha(c.ROOT/w.BASE/name) == digest
    assert set(w.prior.semantic.SOURCES).issubset(w.GATE_SOURCES)
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


def test_candidate_dispatch_disabled_before_gate_or_native_entry(tmp_path,monkeypatch):
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = tmp_path
    called = []
    monkeypatch.setattr(w,'check_opportunity',lambda root:called.append('gate'))
    monkeypatch.setattr(w.g.Evaluator,'measure',lambda self,name:called.append('native'))
    with pytest.raises(ValueError, match='dispatch disabled'):
        evaluator.measure('candidate_00')
    assert called == []
    evaluator.measure('baseline')
    assert called == ['gate','native']


def test_qualification_argv_and_zero_attempt_guard(tmp_path):
    argv = q.phase_command('prepare',tmp_path/'native',tmp_path/'reference')
    assert argv[1:4] == ['-m','isaforge.complex_updates_workload','prepare']
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
    c.seal(tmp_path/q.HISTORY,{'synthetic_provenance_only':True})
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
        c.seal(native/'plan.json',{'context_id':'complex-updates'})
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


def test_separate_provenance_and_original_source_are_pinned():
    import json
    import hashlib
    record = json.loads((c.ROOT/w.PROVENANCE).read_text())
    assert record['commit'] == w.UPSTREAM_COMMIT
    assert record['directory'] == 'bench/kernel/complex_updates'
    assert set(record['files']) == set(w.UPSTREAM)
    for name,digest in w.UPSTREAM.items():
        raw = (c.ROOT/w.BASE/name).read_bytes()
        assert record['files'][name]['sha256'] == digest
        assert record['files'][name]['bytes'] == len(raw)
        assert record['files'][name]['git_blob_sha1'] == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    source = (c.ROOT/w.BASE/'complex_updates.c').read_text()
    adapter = (c.ROOT/w.PROGRAM).read_text()
    assert '#define N 16' in source
    assert 'check_sum != 144.0f' in source
    assert 'i < N' in source and 'check_sum += complex_updates_D[ i ]' in source
    assert '#include "complex_updates.c"' in adapter
    assert '_Static_assert(sizeof(int) == 4' in adapter
    assert 'sizeof(float) == 4' in adapter
    assert 'return result == 0 && complex_updates_return() == 0;' in adapter
    assert 'first16' in w.PROTOCOL['verifier_limitation']
    assert w.PROTOCOL['compiler_flags'] == list(w.COMPILER_FLAGS)
    assert '-march=rv32i_zicsr' in w.COMPILER_FLAGS and '-mabi=ilp32' in w.COMPILER_FLAGS
    assert '-Os' in w.COMPILER_FLAGS and '-ffast-math' not in w.COMPILER_FLAGS
    assert w.PROTOCOL['software_arithmetic_library'] == '-lgcc'
    assert w.PROTOCOL['clock_mhz'] == 12 and w.PROTOCOL['route_seeds'] == [1,2,3]
    assert w.PROTOCOL['candidate_dispatch_enabled'] is False
    assert w.PROTOCOL['target_candidate_attempts'] == 0


def test_registration_composes_with_frozen_tacle_adapter():
    g = w.g
    original = (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,w.evidence._public)
    with w.prior.registration():
        previous = (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,w.evidence._public)
        with w.registration():
            assert g.WORKLOADS == {'complex_updates':'../../tacle/complex_updates/isaforge_adapter.c'}
            assert w.evidence._public is w.public_projection
        assert previous == (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,w.evidence._public)
    assert original == (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,w.evidence._public)


def test_cli_has_no_candidate_measure_or_collect_path(tmp_path):
    with pytest.raises(SystemExit):
        w.main(['measure','--root',str(tmp_path)])
    with pytest.raises(SystemExit):
        w.main(['collect','--root',str(tmp_path)])


def test_prepare_copies_original_files_and_binds_context(tmp_path,monkeypatch):
    def base_prepare(reference, output, workload, pool_size, *, program_limit, stack_floor):
        assert workload == w.WORKLOAD and pool_size == 12
        assert (program_limit,stack_floor) == (6400,6528)
        assert w.g.SOURCE == w.SOURCE
        inputs = output/'inputs'
        inputs.mkdir(parents=True)
        shutil.copyfile(c.ROOT/w.PROGRAM,inputs/'program.c')
        shutil.copyfile(c.ROOT/'hardware/embench_firmware.c',inputs/'embench_firmware.c')
        g = w.g
        plan = dict(context_id='pre-amendment',workload=workload,pool_size=pool_size,
            memory_partition=w.PARTITION, compiler_flags=list(g.q.bounded.compact.FLAGS),
            simulation_cycle_limit=g.CYCLE_LIMIT,native_limits=dict(w.NATIVE_LIMITS),
            build_variant={'required_entrypoint':w.SOURCE},relocation_guard=g.GUARD_RULE,
            pool_rule=g.POOL_RULE,source_bindings={name:c.sha(c.ROOT/name) for name in
                (w.SOURCE,g.QUALIFIED_SOURCE,g.guard.SOURCE,g.attempts.SOURCE,g.EVIDENCE_SOURCE,*g.AUTHENTICATION_SOURCES)})
        return plan
    monkeypatch.setattr(w.g,'prepare',base_prepare)
    native = tmp_path/'native'
    plan = w.prepare(tmp_path/'reference',native)
    assert plan == w.validate_inputs(native)
    assert plan['opportunity_source_protocol'] == w.PROTOCOL
    assert plan['upstream'] == w.upstream_record()
    assert plan['context_id'] == c.digest({k:v for k,v in plan.items() if k != 'context_id'})
    for name,digest in w.UPSTREAM.items():
        assert c.sha(native/'inputs'/name) == digest
    for name in w.GATE_SOURCES:
        assert c.sha(native/'sources'/name) == plan['source_bindings'][name] == c.sha(c.ROOT/name)
    mutated = copy.deepcopy(plan)
    mutated['memory_partition'] = w.g.q.partition_spec(7168,7296)
    with pytest.raises(ValueError,match='Fixed original-input'):
        w.check_plan(mutated)
    mutated = copy.deepcopy(plan)
    mutated['opportunity_source_protocol']['minimum_timed_replacements'] = 1
    with pytest.raises(ValueError,match='Fixed original-input'):
        w.check_plan(mutated)
    (native/'inputs/complex_updates.c').write_text('changed')
    with pytest.raises(ValueError,match='Bound input changed'):
        w.validate_inputs(native)


def test_zero_candidates_guard_rejects_measurement_without_ledger(tmp_path):
    (tmp_path/'measurements/candidate_00').mkdir(parents=True)
    with pytest.raises(ValueError, match='zero candidate'):
        w.require_zero_candidates(tmp_path)


def test_provenance_commit_tampering_fails_without_native(tmp_path, monkeypatch):
    import json
    for name in [w.PROVENANCE, *(w.BASE+name for name in w.UPSTREAM)]:
        destination = tmp_path/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT/name, destination)
    record = json.loads((tmp_path/w.PROVENANCE).read_text())
    record['commit'] = '0'*40
    (tmp_path/w.PROVENANCE).write_text(json.dumps(record))
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='provenance'):
        w.upstream_record()


def test_frozen_pool_is_not_candidate_dispatch_authorization(qualifier, monkeypatch):
    f = qualifier
    result = q.qualify(f['output'], f['native'], f['reference'])
    assert result['status'] == 'accepted'
    protocol = c.unseal(f['output']/'protocol.json')
    assert protocol['candidate_dispatch_enabled'] is False
    assert protocol['pool_freeze_is_candidate_authorization'] is False
    evaluator = object.__new__(w.Evaluator)
    evaluator.root = f['native']
    with pytest.raises(ValueError, match='dispatch disabled'):
        evaluator.measure('candidate_00')
    w.require_zero_candidates(f['native'])
