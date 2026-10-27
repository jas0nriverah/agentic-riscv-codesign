"""Read-only authentication of an isolated MD5 candidate-heldout native prefix.

This module deliberately has no evaluator, model loader, dispatcher, or recovery
path.  It only accepts a separately bound *new* native context; the archived
MD5 outcome root is rejected before candidate measurement files are opened.
Authentication is cooperative local-process validation, not an OS sandbox or
release authority.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from . import codesign as c
from . import md5_offline_controller as identity

SOURCE = 'isaforge/md5_native_evidence.py'
SCHEMA = 'isaforge-md5-native-evidence-v1'
ANCHOR_SCHEMA = 'isaforge-md5-native-evidence-anchor-v1'
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return c.digest(value)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite JSON constant: ' + value)


def _finite(value, label='JSON'):
    if type(value) is float:
        require(math.isfinite(value), label + ' contains a non-finite number')
    elif type(value) is list:
        for item in value:
            _finite(item, label)
    elif type(value) is dict:
        for item in value.values():
            _finite(item, label)


def strict_json(raw: bytes, label='artifact', *, object_required=True):
    """Decode one bounded UTF-8 JSON object without duplicate/non-finite values."""
    require(type(raw) is bytes and len(raw) <= MAX_FILE_BYTES, label + ' is not bounded bytes')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid ' + label + ' JSON') from error
    _finite(value, label)
    if object_required:
        require(type(value) is dict, label + ' must be a JSON object')
    return value


def _components(relative):
    require(type(relative) is str and bool(relative), 'Evidence path must be a nonempty string')
    require('\\' not in relative and '\x00' not in relative, 'Evidence path has invalid separators')
    parts = relative.split('/')
    require(not relative.startswith('/') and all(part not in ('', '.', '..') for part in parts),
            'Evidence path must be contained and normalized')
    return tuple(parts)


def _absolute_no_symlink(value):
    """Return a normalized absolute path after rejecting symlinked components."""
    absolute = Path(os.path.abspath(os.fspath(value)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            require(current == absolute, 'Native root has a missing path component')
            break
        require(not stat.S_ISLNK(info.st_mode), 'Native root path cannot traverse a symlink')
    return absolute


def _read_file(root: Path, relative: str, *, maximum=MAX_FILE_BYTES):
    """Read one regular file beneath root with no symlink traversal or mutation."""
    parts = _components(relative)
    current = root
    for part in parts[:-1]:
        current = current / part
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                'Evidence path traverses a non-directory or symlink')
    path = current / parts[-1]
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            'Evidence member must be a regular non-symlink file')
    require(info.st_size <= maximum, 'Evidence member exceeds size limit')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        require(stat.S_ISREG(opened.st_mode) and opened.st_ino == info.st_ino and
                opened.st_dev == info.st_dev, 'Evidence member changed during open')
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            require(total <= maximum, 'Evidence member exceeds size limit')
        return b''.join(chunks)
    finally:
        os.close(descriptor)


@contextmanager
def _locked_root(value):
    root = _absolute_no_symlink(value)
    require(root.is_dir(), 'Native root must be an existing real directory')
    root = root.resolve(strict=True)
    lock_path = root / '.native.lock'
    require(not lock_path.is_symlink() and lock_path.is_file(),
            'A stable native snapshot requires the existing evaluator lock')
    descriptor = os.open(lock_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        lock_stat = os.fstat(descriptor)
        require(stat.S_ISREG(lock_stat.st_mode), 'Native lock must be a regular file')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Native evaluator is active; audit after it stops') from None
        yield root
    finally:
        os.close(descriptor)


def _sealed(root, relative):
    raw = _read_file(root, relative)
    sidecar = _read_file(root, relative + '.sha256', maximum=256).decode('ascii').strip()
    actual = hashlib.sha256(raw).hexdigest()
    require(len(sidecar) == 64 and all(ch in '0123456789abcdef' for ch in sidecar) and sidecar == actual,
            'Sealed artifact byte digest differs: ' + relative)
    return strict_json(raw, relative, object_required=relative != 'commands.json'), actual, raw


def _tree_inventory(root, relative):
    """Hash one charged measurement subtree, rejecting links and extra files."""
    base = root.joinpath(*_components(relative))
    require(not base.is_symlink() and base.is_dir(), 'Charged measurement directory is missing')
    inventory = {}
    pending = [base]
    total = 0
    while pending:
        directory = pending.pop()
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            info = child.lstat()
            require(not stat.S_ISLNK(info.st_mode), 'Symlink in charged measurement tree')
            if stat.S_ISDIR(info.st_mode):
                if child.name == 'obj_dir':
                    continue
                pending.append(child)
                continue
            require(stat.S_ISREG(info.st_mode), 'Non-regular member in charged measurement tree')
            rel = child.relative_to(base)
            if 'obj_dir' in rel.parts:
                continue
            require(info.st_size <= MAX_FILE_BYTES, 'Measurement artifact exceeds size limit')
            data = _read_file(root, (Path(relative) / rel).as_posix())
            total += len(data)
            require(total <= MAX_SNAPSHOT_BYTES, 'Charged attempt snapshot exceeds size limit')
            inventory[rel.as_posix()] = hashlib.sha256(data).hexdigest()
    return inventory


def _anchor(anchor):
    require(type(anchor) is dict and anchor.get('schema') == ANCHOR_SCHEMA,
            'Explicit prelabel native-evidence anchor required')
    required = {'schema', 'native_context_id', 'archived_context_id', 'preparation_context_id',
        'plan_sha256', 'protocol_sha256', 'discovery_sha256', 'baseline_record_sha256',
        'release_sha256', 'manifest_sha256', 'model_manifest_sha256', 'compiler_flags',
        'source_bindings', 'input_bindings', 'tool_bindings', 'candidates', 'public_rows', 'session',
        'live_budget'}
    require(set(anchor) == required, 'Native-evidence anchor fields differ')
    native = anchor['native_context_id']
    require(type(native) is str and len(native) == 64 and native not in
        (anchor['archived_context_id'], anchor['preparation_context_id']),
        'A distinct new native context is required')
    for key in ('plan_sha256', 'protocol_sha256', 'discovery_sha256', 'baseline_record_sha256',
                'release_sha256', 'manifest_sha256', 'model_manifest_sha256'):
        value = anchor[key]
        require(type(value) is str and len(value) == 64 and all(ch in '0123456789abcdef' for ch in value),
                'Malformed anchor digest: ' + key)
    require(anchor['live_budget'] == 3 and len(anchor['candidates']) == len(anchor['public_rows']) == 12,
            'The frozen twelve-candidate, three-live protocol is required')
    session = anchor['session']
    require(type(session) is dict and set(session) == {'policy', 'seed', 'horizon', 'session_id'} and
        session['policy'] == 'fixed_joint_lookahead' and session['seed'] == 0 and session['horizon'] == 3 and
        session['session_id'] == digest({k: session[k] for k in ('policy', 'seed', 'horizon')}),
        'Frozen live session identity differs')
    require(type(anchor['compiler_flags']) is list and '-mabi=ilp32' in anchor['compiler_flags'] and
        any(flag.startswith('-march=rv32i') and not flag.startswith('-march=rv32im')
            for flag in anchor['compiler_flags']), 'RV32I/ILP32 compiler contract required')
    require(type(anchor['source_bindings']) is dict and SOURCE in anchor['source_bindings'] and
        anchor['source_bindings'][SOURCE] == hashlib.sha256((identity.REPOSITORY / SOURCE).read_bytes()).hexdigest(),
        'The evidence reader must be bound into the prelabel source contract')
    # Pin the archived identity namespace and roster through the existing
    # identity-only loader. It authenticates only the frozen public roster,
    # certificates and source bindings; it never reads MD5 outcomes/history.
    trusted_pool = identity.load_public_pool()
    trusted_rows = trusted_pool.validate()
    require(anchor['archived_context_id'] == trusted_pool.archived_hardware_context and
        anchor['preparation_context_id'] == trusted_pool.logical_namespace,
        'Anchor archived/preparation identity differs from the pinned public roster')
    require(type(anchor['input_bindings']) is dict and type(anchor['tool_bindings']) is dict,
            'Explicit input/tool bindings required')
    candidates = anchor['candidates']; public = anchor['public_rows']
    trusted_by_formula = {row['formula']: row for row in trusted_rows}
    require(len(trusted_by_formula) == 12, 'Pinned public identity roster is not unique')
    names = [row.get('native_name') for row in candidates]
    native_ids = [row.get('native_candidate_id') for row in candidates]
    logical_ids = [row.get('preparation_candidate_id') for row in candidates]
    require(all(type(name) is str and name.startswith('candidate_') for name in names) and
        len(set(names)) == len(set(native_ids)) == len(set(logical_ids)) == 12,
        'Candidate remap must be bijective')
    for row, feature in zip(candidates, public):
        formula = row.get('formula')
        trusted = trusted_by_formula.get(formula)
        require(type(formula) is str and row.get('native_candidate_id') == digest([native, formula]) and
            row.get('preparation_candidate_id') == digest([anchor['preparation_context_id'], formula]) and
            trusted is not None and trusted['name'] == row.get('native_name') and
            trusted['preparation_candidate_id'] == row.get('preparation_candidate_id') and
            trusted['archived_candidate_id'] == digest([anchor['archived_context_id'], formula]) and
            trusted['assembly_sha256'] == row.get('assembly_sha256') and
            feature.get('candidate_id') == row['preparation_candidate_id'] and feature.get('formula') == formula and
            type(row.get('discovery')) is dict and row['discovery'].get('formula') == formula and
            row['discovery'].get('name') == row['native_name'] and
            row['discovery'].get('candidate_id') == row['native_candidate_id'] and
            row.get('assembly') == row['discovery'].get('assembly') and
            row.get('assembly_sha256') == row['discovery'].get('assembly_sha256'),
            'Candidate feature/assembly remap differs')
    return anchor


def _validate_plan_and_public(root, anchor):
    from . import campaign_evidence as ce
    plan, plan_sha, _ = _sealed(root, 'plan.json')
    require(plan_sha == anchor['plan_sha256'] and plan.get('context_id') == anchor['native_context_id'] and
        digest({key: value for key, value in plan.items() if key != 'context_id'}) == plan['context_id'],
        'Native plan/context digest differs from prelabel anchor')
    require(plan.get('memory_partition') == {'ram_bytes': 8192, 'program_limit': 6400,
        'stack_floor': 6528, 'stack_bytes': 1664, 'minimum_guard_bytes': 128},
        'Frozen 6400/6528/8 KiB memory partition required')
    require(plan.get('configuration', {}).get('ram_bytes') == 8192 and
        plan.get('compiler_flags') == anchor['compiler_flags'] and
        plan.get('source_bindings') == anchor['source_bindings'] and plan.get('inputs') == anchor['input_bindings'],
        'Plan compiler/source/input contract differs')
    for name, expected in plan['source_bindings'].items():
        data = _read_file(identity.REPOSITORY, name)
        require(hashlib.sha256(data).hexdigest() == expected, 'Bound source changed: ' + name)
    for name, expected in plan['inputs'].items():
        data = _read_file(root, 'inputs/' + name)
        require(hashlib.sha256(data).hexdigest() == expected, 'Bound input changed: ' + name)
    require(plan.get('tools') == anchor['tool_bindings'], 'Plan tool bindings differ')
    for item in plan['tools'].values():
        tool = Path(item['path'])
        require(tool.is_file() and not tool.is_dir() and hashlib.sha256(tool.read_bytes()).hexdigest() == item['sha256'],
                'Bound tool changed')
    protocol, protocol_sha, _ = _sealed(root, 'evaluation-protocol.json')
    require(protocol_sha == anchor['protocol_sha256'] and
        protocol.get('schema') == 'isaforge-guarded-measurement-protocol-v1' and
        protocol.get('context_id') == plan['context_id'] and protocol.get('source_bindings') == plan['source_bindings'] and
        protocol.get('clock_mhz') == 12.0 and protocol.get('route_seeds') == [1, 2, 3] and
        protocol.get('attempts_per_candidate') == 1 and protocol.get('maximum_candidate_attempts') == 12,
        'Native evaluation protocol differs')
    discovery, discovery_sha, _ = _sealed(root, 'discovery/discovery.json')
    require(discovery_sha == anchor['discovery_sha256'] and discovery.get('context_id') == plan['context_id'] and
        discovery.get('workload') == plan.get('workload') and
        discovery.get('pool') == [row['discovery'] for row in anchor['candidates']],
        'Native discovery differs from frozen candidate remap')
    names = [row['native_name'] for row in anchor['candidates']]
    require(protocol.get('pool_names') == names and plan.get('pool_size') == 12,
        'Native twelve-candidate pool differs')
    for row in anchor['candidates']:
        assembly = _read_file(root, row['assembly'])
        require(hashlib.sha256(assembly).hexdigest() == row['assembly_sha256'],
                'Exact lowered assembly changed: ' + row['native_name'])
    baseline, baseline_sha, _ = _sealed(root, 'measurements/baseline/measurement.json')
    require(baseline_sha == anchor['baseline_record_sha256'] and
        protocol.get('baseline_sha256') == baseline_sha and baseline.get('context_id') == plan['context_id'] and
        baseline.get('name') == 'baseline' and baseline.get('evaluation_id') ==
        digest([plan['context_id'], discovery_sha, 'baseline']),
        'Baseline anchor/identity differs')
    return plan, protocol, discovery, baseline


def _validate_receipt_bytes(root, commands):
    names = set()
    for row in commands:
        require(type(row) is dict and type(row.get('log')) is str and row['log'] not in names,
                'Duplicate/malformed native receipt')
        names.add(row['log'])
        raw = _read_file(root, row['log'])
        require(hashlib.sha256(raw).hexdigest() == row.get('log_sha256'),
                'Native command log changed: ' + row['log'])
        elapsed = row.get('elapsed_seconds')
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
                'Invalid native command duration')


def _exact_route_constraints(root, attempt, record):
    from . import core_routing
    routes = record.get('routes')
    require(type(routes) is list and [row.get('seed') for row in routes] == [1, 2, 3],
            'Exactly three ordered route seeds required')
    for seed in (1, 2, 3):
        report = strict_json(_read_file(root, (Path(attempt) / 'synthesis' / f'route-{seed}.json').as_posix()),
                             f'route-{seed}.json')
        fmax = report.get('fmax', {})
        require(bool(fmax) and all(type(metrics.get('constraint')) in (int, float) and
            metrics['constraint'] == 12.0 for metrics in fmax.values()),
            'Route must use the exact 12 MHz constraint; tolerance-near constraints are rejected')
        summary = core_routing.timing_summary(report, 12.0)
        require(summary == {key: value for key, value in routes[seed - 1].items() if key != 'seed'},
                'Route summary differs from raw report')


def _exact_baseline_route_constraints(root, baseline):
    simulations = [relative for relative in baseline.get('artifacts', {})
                   if relative.endswith('/simulation/simulation.json')]
    require(len(simulations) == 1, 'Baseline simulation artifact is ambiguous')
    attempt = (Path('measurements/baseline') / Path(simulations[0]).parent.parent).as_posix()
    _exact_route_constraints(root, attempt, baseline)


def _known_invalid(root, name, ledger):
    """Only a complete strict raw run can be called a known invalid design."""
    from . import md5_protocol_bridge as bridge
    raw_paths = [relative for relative in ledger.get('artifacts', {})
                 if relative.endswith('/simulation/simulation.json') and 'unobserved-control' not in relative]
    if len(raw_paths) != 1:
        return None
    try:
        raw = strict_json(_read_file(root, (Path('measurements') / name / raw_paths[0]).as_posix()),
                          'failure simulation')
        return bridge.classify_complete_invalid(raw)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def authenticate_prefix(native_root, anchor, attempt_count):
    """Authenticate a contiguous, already-paid prefix from one new native root.

    No target outcome is read until the new context, source, pool and baseline
    anchors match. The function returns verified records only after raw
    processor/netlist/route recount; known invalid failures and unknown charged
    attempts never produce numerical model rows. This grants no dispatch or
    measurement authority.
    """
    anchor = _anchor(anchor)
    require(type(attempt_count) is int and 0 <= attempt_count <= 12,
            'Attempt prefix length is outside the frozen budget')
    root_value = _absolute_no_symlink(native_root).resolve(strict=False)
    historical_roots = ((identity.REPOSITORY / 'results').resolve(),
                        (identity.REPOSITORY / 'generated').resolve())
    require(not any(root_value == path or root_value.is_relative_to(path) for path in historical_roots),
            'Historical result roots cannot be candidate-heldout native roots')
    with _locked_root(root_value) as root:
        # This first read rejects the archived MD5 context before any measurement
        # or attempt-ledger path is opened.
        plan, protocol, discovery, baseline = _validate_plan_and_public(root, anchor)
        from . import campaign_evidence as ce, guarded_evidence as ge
        adapter = ce._adapter(plan)
        control = root / 'selection-controller' / 'attempts'
        require(not control.is_symlink(), 'Controller attempt root cannot be a symlink')
        existing = []
        if control.exists():
            require(control.is_dir(), 'Controller attempt path is not a directory')
            for child in control.iterdir():
                require(not child.is_symlink() and child.is_dir(), 'Unexpected controller attempt member')
                existing.append(child.name)
        expected_dirs = [f'{i:02d}' for i in range(attempt_count)]
        require(sorted(existing) == expected_dirs, 'Controller attempts must be exactly the requested contiguous prefix')
        by_logical = {row['preparation_candidate_id']: row for row in anchor['candidates']}
        public_by_id = {row['candidate_id']: row for row in anchor['public_rows']}
        preloaded_decisions = []
        selected_names = []
        selected_logical = []
        for index in range(attempt_count):
            decision, decision_sha, _ = _sealed(root,
                f'selection-controller/attempts/{index:02d}/decision.json')
            logical = decision.get('candidate_id')
            require(logical in by_logical and logical not in selected_logical,
                    'Unknown/reused candidate in charged prefix')
            row = by_logical[logical]
            require(decision.get('index') == index and decision.get('native_name') == row['native_name'] and
                decision.get('native_candidate_id') == row['native_candidate_id'],
                'Decision identity differs from the prelabel remap')
            preloaded_decisions.append((decision, decision_sha))
            selected_names.append(row['native_name'])
            selected_logical.append(logical)
        ledger_directory = root / 'attempt-ledger'
        require(not ledger_directory.is_symlink() and ledger_directory.is_dir(),
                'Attempt ledger directory is missing or unsafe')
        ledger_files = []
        for path in ledger_directory.iterdir():
            require(not path.is_symlink() and path.is_file(), 'Unexpected attempt-ledger member')
            if path.suffix == '.json' and path.stem != 'baseline':
                ledger_files.append(path.stem)
        require(set(ledger_files) == set(selected_names),
                'Ledger files exist outside the requested paid prefix')
        measurements_dir = root / 'measurements'
        measurement_dirs = []
        for path in measurements_dir.iterdir():
            require(not path.is_symlink() and path.is_dir(), 'Unexpected measurement member')
            measurement_dirs.append(path.name)
        require(set(measurement_dirs) == {'baseline', *selected_names},
                'Measurement directories exist outside the requested paid prefix')
        commands, _, _ = _sealed(root, 'commands.json')
        require(type(commands) is list, 'Native command receipt file must be a list')
        _validate_receipt_bytes(root, commands)
        baseline_ledger, _, baseline_end = ge._ledger(root, 'baseline', protocol, commands)
        require(baseline_ledger.get('status') == 'success' and
                baseline_end == len(protocol['baseline_receipts']),
                'Baseline ledger must terminate the frozen baseline receipt prefix')
        baseline_checked, _ = ge._baseline(root, adapter, discovery, protocol, commands)
        require(baseline_checked == baseline, 'Recounted baseline differs from its external hash anchor')
        _exact_baseline_route_constraints(root, baseline_checked)

        all_ids = []
        successful_ids = []
        verified = []
        charged = []
        receipt_cursor = len(protocol['baseline_receipts'])
        live_sha = None
        first_three_complete = False

        # A name-only inventory is safe: it detects foreign/future attempts
        # without opening any outcome bytes outside the requested prefix.
        allowed_ledger_names = set()
        for index in range(attempt_count):
            folder = control / f'{index:02d}'
            decision, decision_sha = preloaded_decisions[index]
            logical = decision.get('candidate_id')
            require(logical in by_logical and logical not in all_ids,
                    'Unknown/reused candidate in charged prefix')
            row = by_logical[logical]
            name = row['native_name']; allowed_ledger_names.add(name)
            mode = 'adaptive' if index < anchor['live_budget'] else 'oracle-reference'
            require(decision.get('index') == index and decision.get('mode') == mode and
                decision.get('native_name') == name and decision.get('native_candidate_id') == row['native_candidate_id'] and
                decision.get('formula') == row['formula'] and decision.get('assembly_sha256') == row['assembly_sha256'] and
                decision.get('session_id') == anchor['session']['session_id'] and
                decision.get('manifest_sha256') == anchor['manifest_sha256'] and
                decision.get('release_sha256') == anchor['release_sha256'] and
                decision.get('model_manifest_sha256') == anchor['model_manifest_sha256'] and
                decision.get('paid_ids_before') == all_ids and
                decision.get('successful_paid_ids_before') == successful_ids and
                decision.get('chosen_before_dispatch') is True,
                'Decision differs from frozen identity/session/own-prefix binding')
            if index < anchor['live_budget']:
                require(decision.get('completed_live_trace_sha256') is None and
                    type(decision.get('acquisition_sha256')) is str,
                    'Live decision must bind an acquisition before dispatch')
                acquisition, acquisition_sha, _ = _sealed(root,
                    f'selection-controller/attempts/{index:02d}/acquisition.json')
                require(acquisition_sha == decision['acquisition_sha256'] and
                    acquisition.get('event', {}).get('candidate_id') == logical and
                    acquisition.get('session_id') == anchor['session']['session_id'],
                    'Live acquisition proof identity/hash differs')
            else:
                live, live_sha, _ = _sealed(root, 'selection-controller/live.json')
                require(decision.get('acquisition_sha256') is None and
                    decision.get('completed_live_trace_sha256') == live_sha and
                    live.get('attempted_ids') == all_ids[:anchor['live_budget']] and
                    live.get('remaining_outcomes_exist') is False,
                    'Reference attempt preceded the complete sealed live trace')
                reference_order = [candidate['preparation_candidate_id'] for candidate in anchor['candidates']
                                   if candidate['preparation_candidate_id'] not in all_ids]
                require(reference_order and logical == reference_order[0],
                        'Reference remainder differs from frozen candidate order')
                first_three_complete = True

            completed_path = f'selection-controller/attempts/{index:02d}/completed.json'
            completed_raw_path = folder / 'completed.json'
            ledger, ledger_sha, _ = _sealed(root, f'attempt-ledger/{name}.json')
            commands_for_ledger = commands
            start = ledger.get('receipt_start')
            end = ledger.get('receipt_end')
            require(type(start) is int and start == receipt_cursor and
                (type(end) is int or ledger.get('status') == 'started'),
                'Attempt receipt spans must be contiguous and ordered')
            ledger_checked, checked_start, checked_end = ge._ledger(root, name, protocol, commands_for_ledger)
            require(ledger_checked == ledger and checked_start == start,
                    'Native attempt ledger changed during authentication')
            receipt_cursor = checked_end
            all_ids.append(logical)

            status = ledger['status']
            if status in ('started', 'interrupted'):
                require(index == attempt_count - 1 and not completed_raw_path.exists(),
                        'Pending/interrupted attempt must be the final charged entry and cannot be completed')
                partial_inventory = _tree_inventory(root, f'measurements/{name}')
                if status == 'interrupted':
                    require(partial_inventory == ledger['artifacts'],
                            'Interrupted attempt artifact inventory differs')
                charged.append(dict(index=index, candidate_id=logical, native_name=name,
                    status='unknown', elapsed_seconds=ledger.get('elapsed_seconds'),
                    known_lower_bound_seconds=sum(item['elapsed_seconds'] for item in commands[start:checked_end]),
                    partial_artifacts=partial_inventory, model_row=None, continuation_allowed=False))
                continue

            completed, completed_sha, _ = _sealed(root, completed_path)
            outcome, outcome_sha, _ = _sealed(root, f'selection-controller/attempts/{index:02d}/outcome.json')
            require(completed.get('decision_sha256') == decision_sha and
                completed.get('outcome_sha256') == outcome_sha and
                completed.get('ledger_sha256') == ledger_sha and
                completed.get('candidate_id') == logical and
                completed.get('terminal_status') == status,
                'Completed controller record does not seal decision/outcome/ledger')
            require(ledger['elapsed_seconds'] is not None,
                    'Terminal native attempt has no charged wall-time measurement')

            if status == 'success':
                measurement, _, _ = _sealed(root, f'measurements/{name}/measurement.json')
                candidate = row['discovery']
                record = ce._audit_success(root, candidate, baseline_checked, commands, adapter)
                require(record == measurement, 'Raw hardware recount differs from saved measurement record')
                _exact_route_constraints(root, f'measurements/{name}/attempt-000', record)
                oracle_log = [receipt for receipt in commands[start:checked_end]
                    if receipt['log'].endswith('/integer-oracle/verification.log')]
                trap_log = [receipt for receipt in commands[start:checked_end]
                    if receipt['log'].endswith('/illegal-on-baseline/simulation.json')]
                require(len(oracle_log) == len(trap_log) == 1 and
                    oracle_log[0]['failure'] is None and oracle_log[0]['returncode'] == oracle_log[0]['expected_returncode'] == 0 and
                    trap_log[0]['returncode'] == trap_log[0]['expected_returncode'] == 6,
                    'Independent integer oracle or unextended-core trap receipt missing')
                public = public_by_id[logical]
                expected_outcome = ce._outcome(public, record, baseline_checked)
                expected_outcome['measurement_record_seconds'] = record['elapsed_seconds']
                expected_outcome['measurement_seconds'] = ledger['elapsed_seconds']
                require(outcome == expected_outcome and completed.get('failure_class') is None,
                        'Normalized outcome differs from raw verified performance/hardware evidence')
                successful_ids.append(logical)
                verified.append(expected_outcome)
                charged.append(dict(index=index, candidate_id=logical, native_name=name,
                    status='verified', elapsed_seconds=ledger['elapsed_seconds'],
                    measurement_record_seconds=record['elapsed_seconds'],
                    native_command_seconds=sum(item['elapsed_seconds'] for item in commands[start:checked_end]),
                    model_row=expected_outcome, continuation_allowed=True))
            else:
                require(status == 'failed' and 'speedup' not in outcome and 'area' not in outcome,
                        'Failed attempts cannot carry numerical model labels')
                reason = _known_invalid(root, name, ledger)
                if reason is None:
                    require(index == attempt_count - 1,
                            'Unknown charged failure blocks every later attempt')
                    charged.append(dict(index=index, candidate_id=logical, native_name=name,
                        status='unknown', elapsed_seconds=ledger['elapsed_seconds'],
                        known_lower_bound_seconds=sum(item['elapsed_seconds'] for item in commands[start:checked_end]),
                        model_row=None, continuation_allowed=False))
                else:
                    require(outcome.get('failure_class') == reason and outcome.get('candidate_id') == logical,
                            'Known-invalid classification differs from complete raw run evidence')
                    charged.append(dict(index=index, candidate_id=logical, native_name=name,
                        status='known_invalid', failure_class=reason,
                        elapsed_seconds=ledger['elapsed_seconds'], model_row=None,
                        continuation_allowed=True))
            require(completed_sha and _tree_inventory(root, f'measurements/{name}') == ledger['artifacts'],
                    'Terminal attempt artifact inventory differs')

        require(receipt_cursor == len(commands),
                'Uncharged native command receipts remain after the requested paid prefix')
        require(set(ledger_files) == allowed_ledger_names,
                'Ledger files exist outside the requested paid prefix')
        return dict(schema=SCHEMA, context_id=plan['context_id'],
            attempt_count=attempt_count, charged_attempts=charged, verified_outcomes=verified,
            successful_paid_ids=successful_ids, attempted_ids=all_ids,
            live_trace_authenticated=first_three_complete,
            acquisition_recomputed=False, raw_measurements_recounted=True,
            target_outcomes_read=attempt_count, model_fits=0, native_jobs=0,
            candidate_dispatch_enabled=False, measurement_authorization=False,
            release_authority=False,
            limitations=['Caller-supplied prelabel anchor authenticity is a separate trust boundary.',
                'Acquisition proofs are byte-linked but not recomputed by this read-only reader.',
                'No durable reservation recovery or native dispatch is implemented.',
                'This is consumed-workload candidate-heldout development, not workload generalization.'])
