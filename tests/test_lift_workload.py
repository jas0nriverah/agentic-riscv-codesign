"""Original-input lift adapter contracts; no compiler, simulator or model fits."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from isaforge import codesign as c,lift_workload as w
from scripts import qualify_tacle_lift as q


@pytest.fixture
def public():
    return c.unseal(c.ROOT/'results/2026-10-22-expanded-history-verified/experiments/expanded/beebs-ndes/controls11/model/public.json')


def test_upstream_bytes_provenance_and_abi_are_pinned():
    provenance = json.loads((c.ROOT/w.PROVENANCE).read_text())
    assert provenance['archive_sha256'] == 'de14a15d3623fb800ad0d056282d83ac8a69d2af7964b88bdf318215c4117626'
    assert provenance['commit'] == w.UPSTREAM_COMMIT
    assert provenance['directory'] == 'bench/app/lift'
    assert provenance['workload_group'] == w.GROUP
    assert set(provenance['files']) == set(w.UPSTREAM)
    for name,digest in w.UPSTREAM.items():
        raw = (c.ROOT/w.BASE/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest == provenance['files'][name]['sha256']
        assert provenance['files'][name]['bytes'] == len(raw)
        assert provenance['files'][name]['git_blob_sha1'] == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    source = (c.ROOT/w.BASE/'lift.c').read_text()
    adapter = (c.ROOT/w.PROGRAM).read_text()
    assert 'if ( i++ >= 1000 )' in source
    assert 'lift_checksum - 4005888' in source
    for variable in ('lift_simio_in','lift_simio_adc1','lift_simio_adc2','lift_simio_adc3'):
        assert variable+' = 0;' in source
        assert variable not in adapter  # No new stimulus in the external adapter.
    assert '#define main isaforge_tacle_lift_original_main' in adapter
    assert adapter.count('#define ') == 1
    assert [line for line in adapter.splitlines() if line.startswith('#include ')] == [
        '#include "lift.c"','#include "liftlibio.c"','#include "liftlibcontrol.c"']
    assert 'sizeof(int) == 4 && sizeof(long) == 4 && sizeof(void *) == 4' in adapter
    assert 'sizeof(short) == 2 && __CHAR_BIT__ == 8' in adapter
    assert 'return result == 0 && lift_return() == 0;' in adapter


def test_architecture_pool_and_original_input_gate_are_unchanged():
    assert w.POOL_SIZE == 12
    assert w.PARTITION == w.g.q.partition_spec(6400,6528)
    assert w.PROTOCOL['minimum_calibrated_cycle_reduction'] == .005
    assert w.PROTOCOL['minimum_timed_replacements'] == 10
    assert w.PROTOCOL['original_input'] == dict(controller_iterations=1001,digital_stimulus=0,adc1=0,adc2=0,adc3=0)
    assert w.PROTOCOL['build_context'] == w.ABI
    assert set(w.GATE_SOURCES) <= set(q.SOURCES)
    assert w.HELPER_SOURCE in w.GATE_SOURCES
    assert 'benchmarks/tacle/G723_SOURCES.json' not in w.GATE_SOURCES
    assert q.HISTORY == 'results/2026-10-25-thirteen-source-corpus/corpus.json'


def global_state():
    g = w.g
    return (g.SOURCE,g.WORKLOADS,g.POOL_SIZE,g.NATIVE_LIMITS,g.q.POOL_SIZE,
        g.q.bounded.POOL_SIZE,g.q.bounded.campaign.POOL_SIZE,w.evidence._public,
        dict(vars(w.base)),dict(vars(q.runner)))


def test_all_scoped_helper_and_nested_guarded_globals_restore_after_exception():
    before = global_state()
    with pytest.raises(RuntimeError):
        with q.registration(),w.registration():
            assert q.runner.w is w and q.runner.phase_command is q.phase_command
            assert w.base.WORKLOAD == 'lift' and w.g.SOURCE == w.SOURCE
            assert w.g.WORKLOADS == {'lift':'../../tacle/lift/isaforge_adapter.c'}
            with q.registration(),w.registration():
                assert w.base.upstream_record() == w.upstream_record()
                raise RuntimeError('restore')
    assert global_state() == before


def test_lift_registration_composes_with_original_g723_context():
    before = global_state()
    with w._ORIGINAL['registration']():
        previous = global_state()
        with w.registration():
            assert w.g.WORKLOADS == {'lift':'../../tacle/lift/isaforge_adapter.c'}
        assert global_state() == previous
    assert global_state() == before


def test_gate_requires_one_candidate_to_meet_both_minima(public):
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
    result = w.opportunity_gate(public)
    assert not result['passed'] and result['target_candidate_attempts'] == 0
    assert result['protocol'] == w.PROTOCOL
    public[0]['speedup'] = 2.
    with pytest.raises(ValueError,match='non-public'):
        w.opportunity_gate(public)


def test_cli_and_evaluator_have_no_candidate_dispatch(tmp_path,monkeypatch):
    called = []
    evaluator = object.__new__(w.Evaluator); evaluator.root = tmp_path
    monkeypatch.setattr(w.g.Evaluator,'measure',lambda self,name:called.append(name))
    with pytest.raises(ValueError,match='Candidate dispatch disabled'):
        evaluator.measure('candidate_00')
    assert called == []
    with pytest.raises(SystemExit):
        w.main(['measure','--root',str(tmp_path)])
    with pytest.raises(SystemExit):
        w.main(['collect','--root',str(tmp_path)])


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    def guarded(reference,output,workload,pool_size,*,program_limit,stack_floor):
        assert workload == 'lift' and pool_size == 12
        assert (program_limit,stack_floor) == (6400,6528)
        assert w.g.WORKLOADS == {'lift':'../../tacle/lift/isaforge_adapter.c'}
        inputs = output/'inputs'; inputs.mkdir(parents=True)
        shutil.copyfile(c.ROOT/w.PROGRAM,inputs/'program.c')
        shutil.copyfile(c.ROOT/'hardware/embench_firmware.c',inputs/'embench_firmware.c')
        g = w.g
        return dict(context_id='unamended',workload=workload,pool_size=pool_size,
            memory_partition=w.PARTITION,compiler_flags=list(g.q.bounded.compact.FLAGS),simulation_cycle_limit=g.CYCLE_LIMIT,
            native_limits=dict(w.NATIVE_LIMITS),build_variant={'required_entrypoint':w.SOURCE},
            relocation_guard=g.GUARD_RULE,pool_rule=g.POOL_RULE,
            source_bindings={name:c.sha(c.ROOT/name) for name in (w.SOURCE,g.QUALIFIED_SOURCE,g.guard.SOURCE,
                g.attempts.SOURCE,g.EVIDENCE_SOURCE,*g.AUTHENTICATION_SOURCES)})
    monkeypatch.setattr(w.g,'prepare',guarded)
    root = tmp_path/'native'
    plan = w.prepare(tmp_path/'reference',root)
    return root,plan


def test_prepare_reuses_guarded_pipeline_with_accurate_lift_metadata(prepared):
    root,plan = prepared
    assert w.validate_inputs(root) == plan
    assert plan['upstream'] == w.upstream_record()
    assert plan['upstream']['abi'] == w.ABI
    assert plan['opportunity_source_protocol'] == w.PROTOCOL
    assert plan['runtime_support'] == w.RUNTIME_SUPPORT
    assert 'g723' not in plan['runtime_support'].lower()
    for name,digest in w.UPSTREAM.items():
        assert plan['inputs'][name] == c.sha(root/'inputs'/name) == digest
    for name in w.GATE_SOURCES:
        assert c.sha(root/'sources'/name) == plan['source_bindings'][name] == c.sha(c.ROOT/name)
    assert c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == plan['context_id']


@pytest.mark.parametrize('mutation',[
    lambda p:p['opportunity_source_protocol']['original_input'].update(digital_stimulus=1),
    lambda p:p['opportunity_source_protocol'].update(minimum_timed_replacements=1),
    lambda p:p.update(memory_partition=w.g.q.partition_spec(7168,7296)),
    lambda p:p.update(runtime_support='g723_enc'),
])
def test_context_input_gate_or_abi_metadata_changes_are_rejected(prepared,mutation):
    _,plan = prepared
    altered = copy.deepcopy(plan);mutation(altered)
    altered.pop('context_id');altered['context_id'] = c.digest(altered)
    with pytest.raises(ValueError):
        w.check_plan(altered)


def test_changed_vendored_input_is_rejected(prepared):
    root,_ = prepared
    (root/'inputs/lift.c').write_text('changed')
    with pytest.raises(ValueError,match='Bound input changed'):
        w.validate_inputs(root)


def test_public_context_metadata_contains_lift_only(prepared,monkeypatch):
    root,_ = prepared
    # Replace just the frozen helper's original function reference in this test;
    # no native baseline, source parsing or policy fitting is performed.
    def original(path):
        return [],dict(workload_group=w.GROUP,context_transfer='g723_enc'),dict(workload=w.GROUP)
    monkeypatch.setitem(w._ORIGINAL,'baseline_public',original)
    _,context,before = w.baseline_public(root)
    assert context['context_transfer'] == w.CONTEXT_TRANSFER
    assert before['workload'] == context['workload_group'] == w.GROUP


def fake_corpus(successes=111):
    old_rows = [dict(candidate_id=f'old{i}') for i in range(99)]
    old_failed = [dict(candidate_id=f'old-failed{i}') for i in range(3)]
    old = dict(successful_labels=99,rows=old_rows,failed_attempts=old_failed)
    rows = old_rows+[dict(candidate_id=f'new{i}') for i in range(successes-99)]
    failures = old_failed+[dict(candidate_id=f'new-failed{i}') for i in range(111-successes)]
    value = dict(successful_labels=len(rows),rows=rows,failed_attempts=failures,total_candidate_attempts=114,
        independent_workload_groups=['tacle-g723-enc',*[f'group{i}' for i in range(12)]],
        contexts={f'context{i}':{} for i in range(14)},preserved_original_rows_digest=c.digest(old_rows),
        preserved_original_failed_attempts_digest=c.digest(old_failed))
    return old,value


@pytest.fixture
def history_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'ROOT',tmp_path)
    # Manifests authenticate fixture bytes, not actual g723 outcomes.
    from scripts.blind_campaign import _seal_manifest
    def write(successes=111):
        old,value = fake_corpus(successes)
        c.seal(tmp_path/q.PRESERVED_HISTORY,old);_seal_manifest((tmp_path/q.PRESERVED_HISTORY).parent)
        c.seal(tmp_path/q.HISTORY,value);_seal_manifest((tmp_path/q.HISTORY).parent)
        return value
    return dict(root=tmp_path,write=write)


@pytest.mark.parametrize('successes',[99,105,110,111])
def test_exact_future_history_allows_terminal_failures_without_hardcoded_success_count(history_fixture,successes):
    expected = history_fixture['write'](successes)
    assert q.validate_history() == expected


def test_missing_future_export_never_falls_back_to_old_corpus(history_fixture):
    root = history_fixture['root']
    old,_ = fake_corpus()
    c.seal(root/q.PRESERVED_HISTORY,old)
    with pytest.raises(FileNotFoundError):
        q.validate_history()
    assert not (root/q.OUTPUT).exists()


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(total_candidate_attempts=113),
    lambda p:p['rows'][0].update(candidate_id='changed historical row'),
    lambda p:p['independent_workload_groups'].append(w.GROUP),
    lambda p:p['contexts'].pop('context0'),
])
def test_resealed_incomplete_or_changed_history_is_rejected(history_fixture,mutation):
    root = history_fixture['root']; value = history_fixture['write']()
    mutation(value);c.seal(root/q.HISTORY,value)
    from scripts.blind_campaign import _seal_manifest
    _seal_manifest((root/q.HISTORY).parent)
    with pytest.raises(ValueError):
        q.validate_history()


@pytest.fixture
def qualifier(history_fixture,monkeypatch):
    root = history_fixture['root'];history_fixture['write'](110)
    actual_root = Path(__file__).resolve().parents[1]
    # The mocked run needs hash-bound source fixtures. Preserve corpus fixtures
    # above rather than copying real target outcomes into the synthetic run.
    for name in q.SOURCES:
        destination = root/name
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(actual_root/name,destination)
    reference = root/q.REFERENCE;c.seal(reference/'plan.json',{'context_id':'reference'})
    output,native = root/q.OUTPUT,root/q.NATIVE
    controls = dict(reject=None,interrupt=None)
    calls = []
    def observe(argv,folder,*,cwd,metadata,timeout_seconds):
        phase = metadata['phase']; calls.append(phase)
        assert q.runner.w is w
        assert argv == q.phase_command(phase,native,reference)
        protocol = c.unseal(output/'protocol.json')
        assert protocol['historical_corpus_sha256'] == c.sha(root/q.HISTORY)
        assert protocol['original_input'] == w.PROTOCOL['original_input']
        assert all(protocol[key] == value for key,value in w.PROTOCOL.items() if key != 'schema')
        assert protocol['pool_size'] == 12
        assert protocol['minimum_calibrated_cycle_reduction'] == .005
        assert protocol['minimum_timed_replacements'] == 10
        c.seal(native/'plan.json',{'context_id':'lift'})
        if phase == controls['interrupt']:
            raise KeyboardInterrupt('Preserve interruption')
        if phase == 'freeze':
            c.seal(native/'evaluation-protocol.json',dict(pool_names=[f'candidate_{i:02d}' for i in range(12)],maximum_candidate_attempts=12))
        rejected = phase == controls['reject']
        record = dict(status='nonzero_exit' if rejected else 'success',returncode=int(rejected),
            durations=dict(monotonic_elapsed_seconds=1.,utc_elapsed_seconds=1.,clock_disagreement_detected=False))
        c.seal(folder/'record.json',record)
        return record
    monkeypatch.setattr(q.runner.observed_command,'run',observe)
    monkeypatch.setattr(w,'validate_inputs',lambda path:c.unseal(Path(path)/'plan.json'))
    monkeypatch.setattr(w,'check_opportunity',lambda root:{'passed':True})
    return dict(output=output,native=native,reference=reference,calls=calls,controls=controls)


def test_qualification_uses_shared_runner_and_archives_exact_pool(qualifier):
    f = qualifier;before = global_state()
    result = q.qualify(f['output'],f['native'],f['reference'])
    assert result['status'] == 'accepted' and result['target_candidate_attempts'] == 0
    assert f['calls'] == list(q.PHASES)
    assert (f['output']/'raw.tar.gz').is_file()
    assert global_state() == before
    with pytest.raises(ValueError,match='Fresh'):
        q.qualify(f['output'],f['native'],f['reference'])


@pytest.mark.parametrize('phase',['discover','opportunity'])
def test_rejection_stops_before_routing_without_retuning(qualifier,phase):
    f = qualifier;f['controls']['reject'] = phase
    result = q.qualify(f['output'],f['native'],f['reference'])
    assert result['status'] == 'rejected' and result['accepted'] == {}
    assert f['calls'] == list(q.PHASES)[:q.PHASES.index(phase)+1]
    assert 'baseline' not in f['calls']
    assert (f['output']/'raw.tar.gz').is_file()


def test_interruption_restores_shared_runner_and_preserves_archive(qualifier):
    f = qualifier;f['controls']['interrupt'] = 'discover';before = global_state()
    with pytest.raises(KeyboardInterrupt):
        q.qualify(f['output'],f['native'],f['reference'])
    assert c.unseal(f['output']/'qualification.json')['status'] == 'interrupted'
    assert (f['output']/'raw.tar.gz').is_file()
    assert global_state() == before


def test_phase_commands_and_zero_attempt_guard(tmp_path):
    argv = q.phase_command('prepare',tmp_path/'native',tmp_path/'reference')
    assert argv[1:4] == ['-m','isaforge.lift_workload','prepare']
    with pytest.raises(ValueError,match='phase'):
        q.phase_command('measure',tmp_path/'native',tmp_path/'reference')
    c.seal(tmp_path/'attempt-ledger/candidate_00.json',{})
    with pytest.raises(ValueError,match='zero candidate'):
        q.runner.zero(tmp_path)
