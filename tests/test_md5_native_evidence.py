"""Read-only boundary tests using fabricated temporary evidence only."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from isaforge import md5_native_evidence as evidence
from isaforge import md5_protocol_bridge as bridge
from scripts import prepare_md5_evaluation_protocol as protocol_entry


@pytest.fixture(autouse=True)
def no_real_evidence_or_external_commands(monkeypatch):
    """Guard both pathlib reads and the reader's low-level file descriptor IO."""
    repository = evidence.identity.REPOSITORY.resolve()
    original_path_open, original_os_open = Path.open, os.open

    def check(path):
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = Path(os.fsdecode(path)).resolve()
            assert not any(resolved.is_relative_to(repository / name)
                           for name in ('results', 'generated')), 'Real MD5 artifacts are forbidden'

    def path_open(path, *args, **kwargs):
        check(path)
        return original_path_open(path, *args, **kwargs)

    def descriptor_open(path, *args, **kwargs):
        check(path)
        return original_os_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail('External commands, model loading and model execution are forbidden')

    monkeypatch.setattr(Path, 'open', path_open)
    monkeypatch.setattr(os, 'open', descriptor_open)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(bridge, 'authenticate_model_metadata', forbidden)
    monkeypatch.setattr(bridge, 'authenticate_zero_paid_models', forbidden)


@pytest.fixture
def anchor(monkeypatch):
    native = evidence.digest({'fabricated': 'new-native-context'})
    preparation = 'fabricated-preparation-context'
    archived = 'fabricated-archived-context'
    candidates, public = [], []
    trusted_rows = []
    for index in range(12):
        formula = f'add(in0,slli(in1,{index + 1}))'
        name = f'candidate_{index:02d}'
        assembly = f'discovery/{name}.s'
        assembly_sha = hashlib.sha256(f'fixture assembly {index}'.encode()).hexdigest()
        native_id = evidence.digest([native, formula])
        logical_id = evidence.digest([preparation, formula])
        feature = {'candidate_id': logical_id, 'formula': formula}
        discovery = dict(name=name, candidate_id=native_id, formula=formula,
                         assembly=assembly, assembly_sha256=assembly_sha)
        trusted_rows.append(dict(name=name, formula=formula,
            archived_context_id=archived, preparation_context_id=preparation,
            archived_candidate_id=evidence.digest([archived, formula]),
            preparation_candidate_id=logical_id, assembly_path=f'public/{name}.S',
            assembly_sha256=assembly_sha))
        candidates.append(dict(native_name=name, native_candidate_id=native_id,
            preparation_candidate_id=logical_id, formula=formula, assembly=assembly,
            assembly_sha256=assembly_sha, discovery=discovery, public=copy.deepcopy(feature)))
        public.append(feature)
    trusted_pool = SimpleNamespace(archived_hardware_context=archived,
        logical_namespace=preparation, validate=lambda: trusted_rows)
    monkeypatch.setattr(evidence.identity, 'load_public_pool', lambda: trusted_pool)
    return dict(schema=evidence.ANCHOR_SCHEMA, native_context_id=native,
        archived_context_id=archived, preparation_context_id=preparation,
        plan_sha256='1' * 64, protocol_sha256='2' * 64, discovery_sha256='3' * 64,
        baseline_record_sha256='4' * 64, release_sha256='5' * 64,
        manifest_sha256='6' * 64, model_manifest_sha256='7' * 64,
        compiler_flags=['-march=rv32i_zicsr', '-mabi=ilp32', '-Os'],
        source_bindings={evidence.SOURCE: hashlib.sha256(
            (evidence.identity.REPOSITORY / evidence.SOURCE).read_bytes()).hexdigest()},
        input_bindings={}, tool_bindings={}, candidates=candidates, public_rows=public,
        session=bridge.make_session('fixed_joint_lookahead', 0, 3), live_budget=3)


@pytest.fixture
def native_root(tmp_path):
    root = tmp_path / 'fabricated-native'
    root.mkdir()
    (root / '.native.lock').write_bytes(b'')
    return root


def seal(root, name, value):
    raw = json.dumps(value, allow_nan=False).encode()
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    Path(str(path) + '.sha256').write_text(hashlib.sha256(raw).hexdigest() + '\n')
    return hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}'])
def test_strict_json_rejects_duplicate_keys(raw):
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        evidence.strict_json(raw)


@pytest.mark.parametrize('raw', [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
    b'{"x":1e999}', b'{"x":[{"y":-1e999}]}'])
def test_strict_json_rejects_nonfinite_values_recursively(raw):
    with pytest.raises(ValueError, match='[Nn]on-finite'):
        evidence.strict_json(raw)


@pytest.mark.parametrize('raw', [b'[]', b'null', b'1', b'"text"', b'{', b'{"x":"\xff"}'])
def test_strict_json_rejects_nonobjects_or_invalid_utf8_json(raw):
    with pytest.raises(ValueError):
        evidence.strict_json(raw)


def test_strict_json_accepts_bounded_finite_object_and_rejects_nonbytes(monkeypatch):
    raw = b'{"x":[1,2.5,null,true]}'
    assert evidence.strict_json(raw) == {'x': [1, 2.5, None, True]}
    with pytest.raises(ValueError, match='bounded bytes'):
        evidence.strict_json(raw.decode())
    monkeypatch.setattr(evidence, 'MAX_FILE_BYTES', len(raw) - 1)
    with pytest.raises(ValueError, match='bounded bytes'):
        evidence.strict_json(raw)


@pytest.mark.parametrize('relative', ['', '/outside', '../outside', 'safe/../../outside',
    'safe/../outside', './payload', 'safe//payload', 'safe/payload/',
    'safe\\outside', 'safe\x00outside'])
def test_read_file_rejects_escaping_or_invalid_paths_before_open(native_root, relative):
    with pytest.raises(ValueError):
        evidence._read_file(native_root, relative)


@pytest.mark.parametrize('kind', ['leaf', 'parent'])
def test_read_file_rejects_symlink_members(native_root, tmp_path, kind):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'payload').write_bytes(b'private fixture')
    if kind == 'leaf':
        (native_root / 'payload').symlink_to(outside / 'payload')
        relative = 'payload'
    else:
        (native_root / 'linked').symlink_to(outside, target_is_directory=True)
        relative = 'linked/payload'
    with pytest.raises(ValueError, match='symlink'):
        evidence._read_file(native_root, relative)


def test_read_file_is_read_only_and_checks_size(native_root):
    path = native_root / 'payload'
    path.write_bytes(b'opaque fixture')
    before = path.read_bytes()
    assert evidence._read_file(native_root, 'payload') == before
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='size limit'):
        evidence._read_file(native_root, 'payload', maximum=3)


def test_tree_inventory_rejects_symlinks_in_included_tree(native_root, tmp_path):
    base = native_root / 'measurements/candidate_00/attempt-000'
    base.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.write_bytes(b'fixture')
    (base / 'linked').symlink_to(outside)
    with pytest.raises(ValueError, match='Symlink'):
        evidence._tree_inventory(native_root, 'measurements/candidate_00')


def test_tree_inventory_never_reads_ignored_build_tree(native_root, monkeypatch):
    base = native_root / 'measurements/candidate_00/obj_dir'
    base.mkdir(parents=True)
    (base / 'unparsed.json').write_bytes(b'not evidence JSON')
    original = evidence._read_file

    def included_only(root, relative, **kwargs):
        assert 'obj_dir' not in Path(relative).parts
        return original(root, relative, **kwargs)

    monkeypatch.setattr(evidence, '_read_file', included_only)
    assert evidence._tree_inventory(native_root, 'measurements/candidate_00') == {}


def test_sealed_command_receipt_array_uses_strict_json_without_object_requirement(native_root):
    commands = [dict(log='fabricated.log', elapsed_seconds=0.25)]
    expected = seal(native_root, 'commands.json', commands)
    value, actual, raw = evidence._sealed(native_root, 'commands.json')
    assert value == commands and actual == expected
    assert hashlib.sha256(raw).hexdigest() == expected
    seal(native_root, 'plan.json', commands)
    with pytest.raises(ValueError, match='JSON object'):
        evidence._sealed(native_root, 'plan.json')


def test_sealed_bytes_reject_tampering_before_decoding(native_root):
    seal(native_root, 'plan.json', {'fabricated': True})
    (native_root / 'plan.json').write_bytes(b'{"fabricated":false}')
    with pytest.raises(ValueError, match='byte digest differs'):
        evidence._sealed(native_root, 'plan.json')


@pytest.mark.parametrize('defect', ['missing', 'symlink', 'root_symlink'])
def test_existing_real_lock_and_root_are_required(native_root, tmp_path, defect):
    root = native_root
    if defect == 'missing':
        (root / '.native.lock').unlink()
    elif defect == 'symlink':
        (root / '.native.lock').unlink()
        target = tmp_path / 'other-lock'
        target.write_bytes(b'')
        (root / '.native.lock').symlink_to(target)
    else:
        root = tmp_path / 'linked-root'
        root.symlink_to(native_root, target_is_directory=True)
    with pytest.raises(ValueError, match='lock|real directory|symlink'):
        with evidence._locked_root(root):
            pytest.fail('Unsafe root acquired a read lock')


def test_active_exclusive_lock_blocks_reader_without_mutation(native_root):
    lock = native_root / '.native.lock'
    with lock.open('r') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='evaluator is active'):
            with evidence._locked_root(native_root):
                pytest.fail('Exclusive evaluator lock was bypassed')
    with evidence._locked_root(native_root) as acquired:
        assert acquired == native_root.resolve()
    assert lock.read_bytes() == b''


def test_anchor_accepts_only_explicit_bijective_new_native_ids(anchor):
    original = copy.deepcopy(anchor)
    assert evidence._anchor(anchor) == original
    assert anchor == original
    for row in anchor['candidates']:
        assert row['native_candidate_id'] != row['preparation_candidate_id']


@pytest.mark.parametrize('defect', ['archived', 'preparation', 'native_id', 'logical_id',
    'duplicate_name', 'duplicate_native', 'duplicate_logical', 'public_formula',
    'discovery_id', 'assembly_hash', 'session', 'source', 'extra', 'digest'])
def test_anchor_context_remap_and_source_rejection_precedes_any_native_read(anchor, monkeypatch, defect):
    if defect in ('archived', 'preparation'):
        anchor['native_context_id'] = anchor[defect + '_context_id']
    elif defect == 'native_id':
        anchor['candidates'][0]['native_candidate_id'] = anchor['candidates'][0]['preparation_candidate_id']
    elif defect == 'logical_id':
        anchor['candidates'][0]['preparation_candidate_id'] = 'foreign'
    elif defect.startswith('duplicate_'):
        key = {'duplicate_name': 'native_name', 'duplicate_native': 'native_candidate_id',
               'duplicate_logical': 'preparation_candidate_id'}[defect]
        anchor['candidates'][1][key] = anchor['candidates'][0][key]
    elif defect == 'public_formula':
        anchor['public_rows'][0]['formula'] = 'foreign'
    elif defect == 'discovery_id':
        anchor['candidates'][0]['discovery']['candidate_id'] = 'foreign'
    elif defect == 'assembly_hash':
        anchor['candidates'][0]['assembly_sha256'] = 'foreign'
    elif defect == 'session':
        anchor['session']['seed'] = 1
    elif defect == 'source':
        anchor['source_bindings'][evidence.SOURCE] = '0' * 64
    elif defect == 'extra':
        anchor['release_authority'] = True
    else:
        anchor['plan_sha256'] = 'g' * 64
    monkeypatch.setattr(evidence, '_read_file', lambda *args, **kwargs:
                        pytest.fail('Rejected anchor must precede native artifact reads'))
    with pytest.raises(ValueError):
        evidence.authenticate_prefix('/nonexistent/fabricated-native', anchor, 0)


@pytest.mark.parametrize('attempt_count', [-1, 13, True, 1.0, None])
def test_prefix_budget_rejected_before_root_or_measurements(anchor, attempt_count, monkeypatch):
    monkeypatch.setattr(evidence, '_locked_root', lambda *args, **kwargs:
                        pytest.fail('Invalid prefix must precede native lock acquisition'))
    with pytest.raises(ValueError, match='prefix length'):
        evidence.authenticate_prefix('/nonexistent/fabricated-native', anchor, attempt_count)


@pytest.mark.parametrize('defect', ['hash', 'context', 'self_digest'])
def test_plan_anchor_rejection_precedes_measurement_or_ledger_reads(native_root, anchor, monkeypatch, defect):
    plan = {'context_id': anchor['native_context_id'], 'fabricated': 'unaccepted plan'}
    if defect == 'context':
        plan['context_id'] = anchor['archived_context_id']
    elif defect == 'self_digest':
        plan['context_id'] = anchor['native_context_id']
    actual_sha = seal(native_root, 'plan.json', plan)
    if defect != 'hash':
        anchor['plan_sha256'] = actual_sha
    original = evidence._read_file
    opened = []

    def public_only(root, relative, **kwargs):
        opened.append(relative)
        assert relative in ('plan.json', 'plan.json.sha256'), 'Context rejection read target artifacts'
        return original(root, relative, **kwargs)

    monkeypatch.setattr(evidence, '_read_file', public_only)
    with pytest.raises(ValueError, match='plan/context'):
        evidence.authenticate_prefix(native_root, anchor, 0)
    assert opened == ['plan.json', 'plan.json.sha256']


def test_historical_result_root_rejected_before_lock_or_artifact_reads(anchor, monkeypatch):
    monkeypatch.setattr(evidence, '_locked_root', lambda *args, **kwargs:
                        pytest.fail('Historical root must be rejected before locking'))
    with pytest.raises(ValueError, match='Historical result roots'):
        evidence.authenticate_prefix(evidence.identity.REPOSITORY / 'results/fabricated-only', anchor, 0)


def test_historical_generated_root_rejected_before_lock_or_artifact_reads(anchor, monkeypatch):
    monkeypatch.setattr(evidence, '_locked_root', lambda *args, **kwargs:
                        pytest.fail('Historical root must be rejected before locking'))
    with pytest.raises(ValueError, match='Historical result roots'):
        evidence.authenticate_prefix(evidence.identity.REPOSITORY / 'generated/fabricated-only', anchor, 0)


def test_anchor_archived_namespace_is_bound_to_pinned_identity_roster(anchor, monkeypatch):
    anchor['archived_context_id'] = 'caller-substituted-archived-context'
    monkeypatch.setattr(evidence, '_read_file', lambda *args, **kwargs:
                        pytest.fail('Identity substitution must fail before native-root reads'))
    with pytest.raises(ValueError, match='pinned public roster'):
        evidence.authenticate_prefix('/nonexistent/fabricated-native', anchor, 0)


def test_prefix_api_rejects_root_symlink_before_any_native_read(native_root, tmp_path, anchor, monkeypatch):
    linked = tmp_path / 'linked-native-root'
    linked.symlink_to(native_root, target_is_directory=True)
    monkeypatch.setattr(evidence, '_read_file', lambda *args, **kwargs:
                        pytest.fail('Root symlink rejection must precede artifact reads'))
    with pytest.raises(ValueError, match='symlink'):
        evidence.authenticate_prefix(linked, anchor, 0)


def test_authentication_cannot_enable_dispatch_or_protocol_build(tmp_path, monkeypatch):
    gate = bridge.DisabledBridge()
    assert gate.candidate_dispatch_enabled is gate.measurement_authorization is False
    with pytest.raises(bridge.DispatchDisabled, match='hard-disabled'):
        gate.evaluate(enable=True, release_authority=True, evidence={'authenticated': True})
    monkeypatch.setattr(bridge, 'ENGINEERING_GAPS', ())
    monkeypatch.setattr(protocol_entry, 'ROOT', tmp_path)
    monkeypatch.setattr(bridge, 'PREREG', Path('fabricated-preregistration'))
    output = tmp_path / bridge.PREREG / 'disabled-protocol'
    with pytest.raises(bridge.ProtocolIncomplete, match='unconditionally disabled'):
        protocol_entry.build(output)
    assert not output.exists()
