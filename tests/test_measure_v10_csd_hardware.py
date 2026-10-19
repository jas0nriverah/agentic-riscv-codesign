"""Synthetic V10 contracts: no Yosys, ABC, fitting or target measurement."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measure_v10_csd_hardware', ROOT/'scripts/measure_v10_csd_hardware.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('Native execution forbidden in synthetic tests'))


def identity_netlist():
    return {'modules': {'candidate': {'ports': {
        'in0': {'direction': 'input', 'bits': list(range(2, 34))},
        'in1': {'direction': 'input', 'bits': list(range(34, 66))},
        'result': {'direction': 'output', 'bits': list(range(2, 34))}}, 'cells': {}}}}


@pytest.mark.parametrize('context,x,y,want', [
    ('direct_product', 0xffffffff, 99, 0xfffffff5),
    ('add_after_product', 0xffffffff, 12, 1),
    ('sub_before_product', 0, 1, 0xfffffff5),
    ('masked_sub_before_product', 128+7, 9, 0xffffffea)])
def test_independent_unsigned_context_oracle(context, x, y, want):
    assert m.oracle({'context': context, 'constant_u32': 11}, x, y) == want


def test_fixed_vectors_and_unknown_oracle():
    assert len(m.vectors()) == 2148 and m.vectors() == m.vectors()
    assert m.vectors()[:100] == [(a, b) for a in m.BOUNDARIES for b in m.BOUNDARIES]
    with pytest.raises(ValueError): m.oracle({'context': 'new', 'constant_u32': 11}, 1, 2)


def test_mapped_lut_index_and_carry_truth_tables():
    graph = identity_netlist();module = graph['modules']['candidate']
    module['ports']['result']['bits'] = [66, 67]+['0']*30
    module['cells'] = {
        'lut': {'type': 'SB_LUT4', 'parameters': {'LUT_INIT': format(1 << 9, '016b')},
            'connections': {'I0': [2], 'I1': [3], 'I2': [4], 'I3': [5], 'O': [66]},
            'port_directions': {'I0': 'input', 'I1': 'input', 'I2': 'input', 'I3': 'input', 'O': 'output'}},
        'carry': {'type': 'SB_CARRY', 'connections': {'I0': [2], 'I1': [3], 'CI': [4], 'CO': [67]},
            'port_directions': {'I0': 'input', 'I1': 'input', 'CI': 'input', 'CO': 'output'}}}
    evaluate = m.mapped_evaluator(graph)
    for x in range(16):
        assert evaluate(x, 0) == int(x == 9)+2*int((x & 7).bit_count() >= 2)


@pytest.mark.parametrize('mutate', [
    lambda n: n['modules']['candidate']['ports']['result']['bits'].__setitem__(0, 'x'),
    lambda n: n['modules']['candidate']['ports']['result']['bits'].__setitem__(0, True),
    lambda n: n['modules']['candidate']['ports']['result']['bits'].__setitem__(0, -1),
    lambda n: n['modules']['candidate']['ports']['result']['bits'].__setitem__(0, 999),
    lambda n: n['modules']['candidate']['cells'].update({'bad': {'type': 'SB_DFF', 'connections': {}}}),
    lambda n: n['modules']['candidate']['ports']['in0']['bits'].__setitem__(0, 34)])
def test_mapped_unknowns_cells_and_aliases_fail_closed(mutate):
    graph = identity_netlist();mutate(graph)
    with pytest.raises(ValueError): m.mapped_evaluator(graph)


def test_eval_parser_retains_undefined_and_exact_order():
    values = m.rtl_observations("Eval result: \\result = 32'"+'0'*31+"1.\nEval result: \\result = 32'"+'x'*32+".\nEval result: \\result = 17.\n")
    assert values == [1, None, 17]


@pytest.fixture
def tools(tmp_path):
    for name in ('yosys', 'yosys-abc', 'yosys-config'):
        (tmp_path/name).write_bytes(name.encode())
    data = tmp_path/'share/yosys';(data/'ice40').mkdir(parents=True)
    (data/'ice40/cells_sim.v').write_text('synthetic library')
    return {'executables': {key: {'path': str(tmp_path/name), 'sha256': m.sha(tmp_path/name), 'version': 'fixture'}
        for key, name in (('yosys', 'yosys'), ('abc', 'yosys-abc'), ('yosys_config', 'yosys-config'))},
        'yosys_data': {'path': str(data), 'files': [{'path': 'ice40/cells_sim.v', 'sha256': m.sha(data/'ice40/cells_sim.v')}]}}


def test_sanitized_environment_ignores_shell_injection(tools, monkeypatch):
    monkeypatch.setenv('ABC', '/bad/abc');monkeypatch.setenv('YOSYS_DATDIR', '/bad/data')
    monkeypatch.setenv('DYLD_INSERT_LIBRARIES', '/bad/lib');monkeypatch.setenv('LD_PRELOAD', '/bad/lib')
    env = m.native_environment(tools)
    assert env['ABC'] == tools['executables']['abc']['path']
    assert set(env) == {'PATH', 'ABC', 'LANG', 'LC_ALL', 'TZ'}


def test_owned_process_receives_sanitized_environment(tools, monkeypatch, tmp_path):
    observed = {}
    def launch(command, **kwargs):
        observed.update(kwargs);return SimpleNamespace(pid=123)
    monkeypatch.setattr(m.subprocess, 'Popen', launch)
    worker = m.HardwareWorkers(tools)
    assert worker.launch(['synthetic-never-executed'], None).pid in worker.active
    assert observed['env'] == m.native_environment(tools) and observed['start_new_session'] is True
    worker.finished(123);assert not worker.active
    worker.cancel()
    with pytest.raises(RuntimeError): worker.launch([], None)


def test_abc_placeholder_grounded_in_retained_yosys_log(tools):
    # Exact spelling observed in archived V9 Yosys logs.
    log = 'Running ABC command: "<yosys-exe-dir>/yosys-abc" -s -f <abc-temp-dir>/abc.script 2>&1'
    assert m.abc_invocations(log, tools) == [dict(path=tools['executables']['abc']['path'], sha256=tools['executables']['abc']['sha256'])]
    for bad in ('<yosys-exe-dir>/../yosys-abc', '<unknown>/yosys-abc', '/tmp/wrong-abc'):
        with pytest.raises((ValueError, FileNotFoundError)): m.abc_invocations('Running ABC command: "'+bad+'"', tools)
    with pytest.raises(ValueError): m.abc_invocations('', tools)


def test_actual_datadir_must_be_logged_and_bound(tools, tmp_path):
    rtl = tmp_path/'candidate.v';rtl.write_text('module candidate; endmodule')
    data = Path(tools['yosys_data']['path'])/'ice40/cells_sim.v'
    log = f"Parsing Verilog input from `{rtl}' to AST representation.\nParsing Verilog input from `{data}' to AST representation.\n"
    assert set(m.data_invocations(log, tools, rtl)) == {'ice40/cells_sim.v'}
    with pytest.raises(ValueError): m.data_invocations('', tools, rtl)
    with pytest.raises(ValueError): m.data_invocations(log+"Parsing Verilog input from `/evil/cells_sim.v'", tools, rtl)
    data.write_text('changed')
    with pytest.raises(ValueError): m.data_invocations(log, tools, rtl)


def test_exact_flow_resets_verification_before_default_synthesis(tmp_path):
    commands = m.arm_commands(tmp_path/'candidate.v', tmp_path/'mapped.json')
    assert sum(c.startswith('eval ') for c in commands) == 2148
    reset = commands.index('design -reset')
    assert commands[reset+2:reset+4] == ['synth_ice40 -top candidate', 'check -assert']
    assert not any('-dsp' in c or '-nocarry' in c for c in commands)
    assert m.proof_commands(tmp_path/'miter.v')[1:] == ['prep -top pair_miter -flatten', 'check -assert', 'sat -timeout 60 -verify -prove trigger 0 -show-inputs -show-outputs']


@pytest.mark.parametrize('execution,text,status', [
    ({'returncode': 0, 'timed_out': False}, 'SAT proof finished - no model found: SUCCESS!', 'proved'),
    ({'returncode': 1, 'timed_out': False}, 'model found: FAIL', 'failed'),
    ({'returncode': 0, 'timed_out': False}, 'unknown', 'unknown'),
    ({'returncode': None, 'timed_out': True}, 'partial', 'timeout')])
def test_universal_actual_rtl_proof_verdicts_retained(tmp_path, tools, monkeypatch, execution, text, status):
    source = tmp_path/'miter.v';source.write_text('synthetic sealed miter')
    pair = {'pair_id': 'v10-csd:'+'a'*64, 'miter_rtl': {'path': 'miter.v', 'sha256': m.sha(source)}}
    def run(command, log, owner, timeout):
        assert timeout == 60;log.write_text(text);return execution
    monkeypatch.setattr(m, 'run_owned', run)
    result = m.prove_pair(tmp_path, pair, tmp_path/'proof', tools, None)
    assert result['status'] == status and result['proved'] == (status == 'proved')
    assert m.read(tmp_path/'proof/proof.json') == result
    assert (tmp_path/'proof/prove.log').read_text() == text


@pytest.mark.parametrize('name', ['../escape', m.PREFIX+'attempt-0000/../escape', m.PREFIX+'attempt-0001/member', '/abs/path'])
def test_owned_path_boundaries(tmp_path, name):
    with pytest.raises(ValueError): m.destination(name, tmp_path, 'attempt-0000')


def test_timeout_preserves_partial_log_and_kills_owned_group(tmp_path, monkeypatch):
    events = []
    class Process:
        pid = 12345
        calls = 0
        def wait(self, timeout=None):
            self.calls += 1
            if self.calls == 1: raise subprocess.TimeoutExpired('fixture', timeout)
            return -9
    class Owner:
        def launch(self, command, stream): stream.write(b'partial retained');return Process()
        def finished(self, pid): events.append(('finished', pid))
    monkeypatch.setattr(m.os, 'killpg', lambda pid, sig: events.append(('kill', pid)))
    path = tmp_path/'timeout.log'
    result = m.run_owned([], path, Owner(), 60)
    assert result['returncode'] is None and result['timed_out'] is True and result['elapsed_seconds'] >= 0
    assert path.read_bytes() == b'partial retained' and events == [('kill', 12345), ('finished', 12345)]


def test_collection_is_gated_and_never_automatically_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'validate_approval', lambda *_: (_ for _ in ()).throw(ValueError('parent approval required')))
    with pytest.raises(ValueError, match='parent approval'): m.collect(tmp_path, tmp_path/'measurement-approval.json')
    assert not (tmp_path/'label-release.json').exists()
    m.write(tmp_path/'label-release.json', {'prior': 'failed'})
    with pytest.raises(ValueError, match='single-attempt'): m.collect(tmp_path, tmp_path/'measurement-approval.json')


@pytest.mark.parametrize('proof_pass', [False, True])
def test_complete_cohort_and_failed_proof_retention(tmp_path, tools, monkeypatch, proof_pass):
    import prepare_v10_csd_hardware as prep
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    root = tmp_path/'results';root.mkdir();m.write(root/'preparation.json', {'fixture': True})
    approval = root/'measurement-approval.json';m.write(approval, {'fixture': True})
    proof = root/'source-proof.json';m.write(proof, {'source-proof': 'fixture'})
    pairs = [{'pair_id': 'v10-csd:'+format(i, '064x'), 'proof': {'path': proof.name, 'sha256': m.sha(proof)}} for i in range(32)]
    monkeypatch.setattr(m, 'validate_approval', lambda *_: ({}, {}, pairs, tools, {'freeze_commit': 'a'*40}, {}))
    monkeypatch.setattr(prep, 'validate_tools', lambda *_: None)
    seen = []
    def prove(root, pair, folder, tools, owner):
        seen.append(pair['pair_id']);folder.mkdir(parents=True);(folder/'prove.log').write_text('unknown retained')
        return {'pair_id': pair['pair_id'], 'proved': proof_pass, 'status': 'proved' if proof_pass else 'unknown'}
    monkeypatch.setattr(m, 'prove_pair', prove)
    arms = []
    def measure(root, pair, arm, folder, tools, owner):
        assert proof_pass
        arms.append((pair['pair_id'], arm));folder.mkdir(parents=True);(folder/'ice40.log').write_text('fresh fixture log')
        return {'pair_id': pair['pair_id'], 'arm': arm}
    monkeypatch.setattr(m, 'measure_arm', measure)
    if proof_pass: m.collect(root, approval)
    else:
        with pytest.raises(RuntimeError, match='Incomplete paired'): m.collect(root, approval)
    done = m.read(root/'measurements/completion.json')
    assert len(set(seen)) == 32 and done['complete'] is proof_pass and len(done['failures']) == (0 if proof_pass else 32)
    assert len(set(arms)) == done['fresh_synthesis_jobs_completed'] == (64 if proof_pass else 0)
    assert (root/'measurements/attempt-0000/raw-evidence.zip').is_file()
    monkeypatch.setattr(m, 'prepared_inputs', lambda *_: ({}, {}, pairs, tools, {}))
    recovered, content = m.archive_data(root, 'attempt-0000')
    assert recovered == done and json.loads(content['pairs.json']) == pairs
    corrupted = {**done, 'fresh_synthesis_jobs_completed': 999}
    (root/'measurements/completion.json').write_text(json.dumps(corrupted))
    with pytest.raises(ValueError, match='Completion differs'): m.archive_data(root, 'attempt-0000')
    with pytest.raises(ValueError, match='single-attempt'): m.collect(root, approval, attempt='attempt-0001')


@pytest.fixture
def arm_evidence(tmp_path, tools, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    root = tmp_path/'results';root.mkdir();source = root/'source.v';source.write_text('sealed synthetic RTL')
    pair = {'pair_id': 'v10-csd:'+'a'*64, 'source_candidate_id': 'source-a', 'constant_u32': 1,
        'context': 'direct_product', 'formula': 'mul(in0,addi(0,1))',
        'arms': {'original': {'formula': 'mul(in0,addi(0,1))', 'rtl': {'path': source.name, 'sha256': m.sha(source)}}}}
    folder = tmp_path/m.PREFIX/'attempt-0000/circuits'/('a'*64)/'original'
    def fake_run(command, log, owner, timeout):
        assert timeout == 360
        netlist = log.with_name('ice40-netlist.json');m.write(netlist, identity_netlist())
        lines = [f"Eval result: \\result = 32'{a:032b}." for a, b in m.vectors()]
        lines += ['Running ABC command: "<yosys-exe-dir>/yosys-abc" -s -f <abc-temp-dir>/abc.script 2>&1',
            f"Parsing Verilog input from `{folder/'candidate.v'}' to AST representation.",
            f"Parsing Verilog input from `{tools['yosys_data']['path']}/ice40/cells_sim.v' to AST representation."]
        log.write_text('\n'.join(lines)+'\n')
        return {'returncode': 0, 'timed_out': False}
    monkeypatch.setattr(m, 'run_owned', fake_run)
    metric = m.measure_arm(root, pair, 'original', folder, tools, None)
    return root, pair, folder, metric, tools


def test_sampled_rtl_and_mapped_checks_consume_actual_raw_netlist(arm_evidence):
    root, pair, folder, metric, _ = arm_evidence
    assert metric['actual_rtl_verified'] and metric['mapped_netlist_verified']
    assert metric['vectors_per_arm'] == 2148 and metric['lut4_count'] == 0
    assert len((folder/'observations.txt').read_text().splitlines()) == 2148
    assert metric['rtl_sha256'] == pair['arms']['original']['rtl']['sha256']


@pytest.mark.parametrize('poison', ['none', 'raw-eval', 'script', 'netlist', 'identity', 'count', 'extra-arm'])
def test_independent_audit_recomputes_and_rejects_reauthenticated_corruption(arm_evidence, monkeypatch, poison):
    root, pair, folder, metric, tools = arm_evidence
    prefix = 'circuits/'+('a'*64)+'/original/'
    content = {prefix+p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    content['pairs.json'] = json.dumps([pair]).encode();content['tools.json'] = json.dumps(tools).encode()
    done = {'complete': False, 'failures': ['other31pairs-missing'], 'fresh_synthesis_jobs_completed': 1,
        'universal_actual_rtl_pairs_proved': 0}
    if poison == 'raw-eval':
        content[prefix+'ice40.log'] = content[prefix+'ice40.log'].replace(b"Eval result: \\result = 32'00000000000000000000000000000000.", b"Eval result: \\result = 32'00000000000000000000000000000001.", 1)
        metric['log_sha256'] = m.digest(content[prefix+'ice40.log'])
    elif poison == 'script':
        content[prefix+'ice40.ys'] += b'synth_ice40 -dsp\n';metric['script_sha256'] = m.digest(content[prefix+'ice40.ys'])
    elif poison == 'netlist':
        graph = identity_netlist();graph['modules']['candidate']['ports']['result']['bits'] = ['0']*32
        content[prefix+'ice40-netlist.json'] = json.dumps(graph).encode()
        metric['netlist_sha256'] = m.digest(content[prefix+'ice40-netlist.json'])
    elif poison == 'identity': metric['formula'] = 'foreign formula'
    elif poison == 'count': done['fresh_synthesis_jobs_completed'] = 2
    records = [metric]
    if poison == 'extra-arm': records.append({**metric, 'arm': 'unknown'})
    m.write(root/'measurements/attempt-0000/arm-measurements.json', records)
    monkeypatch.setattr(m, 'archive_data', lambda *_: (done, content))
    monkeypatch.setattr(m, 'review_proofs', lambda *a, **k: {'pairs_proved': 0})
    if poison == 'none':
        report = m.audit(root, attempt='attempt-0000')
        assert report['sampled_source_and_mapped_comparisons'] == 4296
        assert report['pair_results'] is None and report['mean_csd_minus_original_lut4'] is None
    else:
        with pytest.raises(ValueError): m.audit(root, attempt='attempt-0000')
