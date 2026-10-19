#!/usr/bin/env python3
"""Fixed audited-V10d timing adapter: input preparation, then64 maps and192 routes.

No native study runs without a committed, exact parent approval. All mapped
transactions must pass before routing; every unsuccessful slot remains visible.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from collections import Counter
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
import prepare_v10_timing as harness
import measure_v10d_csd_hardware as area
import measure_v10_csd_hardware as frozen
import v10d_timing_paths as paths

need, sha, digest, now, utc = area.need, area.sha, area.digest, area.now, area.utc
write, copy, record, checked, committed = area.write, area.copy, area.record, area.checked, area.committed
# Strict JSON decoding also covers native files, not just manifests.
def read(path):
    def unique(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON key');value[key] = item
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)

SCHEMA = 'isaforge-v10d-timing-preparation-v1'
PREFIX = 'generated/v10d-timing/'
AREA_ROOT = 'results/2026-10-15-v10d-csd-hardware'
AREA_PREPARATION_SHA = '7c3b89e1405f8c999ac7cc95ceeb7f71971e5cd7a94225a9b1b600651c057560'
AREA_COMPLETION_SHA = '83676a2f949bad0276160e7d8a82aa2ded2beaf2352c9fe9d47706de7dbf3f3c'
ARMS, SEEDS = ('original', 'csd'), (1, 2, 3)
MIN_FREE_BYTES, MAX_ATTEMPT_BYTES = 8 * 1024**3, 4 * 1024**3
run_owned = frozen.run_owned


def required_sources():
    return list(dict.fromkeys([Path(__file__).resolve(), ROOT/'tests/test_measure_v10d_timing.py',
        ROOT/'docs/v10d-timing-protocol.md', ROOT/'scripts/audit_v10d_timing.py',
        ROOT/'tests/test_audit_v10d_timing.py', ROOT/'scripts/prepare_v10_timing.py',
        ROOT/'tests/test_prepare_v10_timing.py', ROOT/'docs/v10-timing-direction.md',
        ROOT/'scripts/v10d_timing_paths.py', ROOT/'tests/test_v10d_timing_paths.py', *area.required_sources()]))


def recipe():
    # Keep the reviewed timing policy byte-for-byte as a nested value.
    return {'schema': 'isaforge-v10d-timing-recipe-v1', 'timing': harness.recipe(),
        'mapping_script': ['read_verilog candidate.v', 'read_verilog wrapper.v',
            'synth_ice40 -top timing_top', 'check -assert', 'write_json ice40-netlist.json'],
        'route_detailed_timing_report': True, 'all64_sequential_checks_before_any_route': True,
        'automatic_retries': False, 'bootstrap': False, 'clock_relaxation': False,
        'min_free_bytes': MIN_FREE_BYTES, 'workspace_guard_bytes': MAX_ATTEMPT_BYTES,
        'primary': '32 equal-weight formula means of three paired seed csd-minus-original reciprocal-Fmax periods in ns',
        'incomplete_primary': None, 'retained_route_slots': 192,
        'limits': 'Common132FF four-pin harness timing; no arithmetic-only delay, CPU performance, power, board validation or population inference.'}


def dynamic_dependencies(binary):
    """Inventory transitive non-system Mach-O dependencies without executing them.

    Fail closed on unresolved install names. System libraries/OS loader remain
    an explicitly declared host boundary, rather than a hermetic-image claim.
    """
    binary = Path(binary).resolve();todo = [binary];seen = set();entries = [];edges = []
    def output(*args): return subprocess.check_output(['/usr/bin/otool', *args], text=True)
    while todo:
        current = todo.pop()
        if current in seen: continue
        seen.add(current)
        lines = output('-L', str(current)).splitlines()[1:]
        loads = [line.strip().split(' (compatibility version ', 1)[0] for line in lines if line.strip()]
        rpaths = re.findall(r'cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset', output('-l', str(current)), re.S)
        def expand(name):
            return name.replace('@loader_path', str(current.parent)).replace('@executable_path', str(binary.parent))
        for name in loads:
            if name.startswith(('/usr/lib/', '/System/Library/')): continue
            candidates = [Path(expand(name))] if not name.startswith('@rpath/') else [Path(expand(p))/name[len('@rpath/'):] for p in rpaths]
            valid = [p for p in candidates if p.is_absolute() and p.is_file()]
            need(len({p.resolve() for p in valid}) == 1, 'Unresolved or ambiguous non-system dynamic library: '+name)
            alias = valid[0];resolved = alias.resolve()
            edges.append({'loader': str(current), 'install_name': name, 'path': str(alias), 'resolved_path': str(resolved), 'sha256': sha(resolved)})
            if resolved != current: todo.append(resolved)
    for path in sorted(seen): entries.append({'path': str(path), 'sha256': sha(path)})
    return {'method': 'otool -L/-l transitive non-system Mach-O dependency closure',
        'files': entries, 'edges': sorted(edges, key=lambda x: (x['loader'], x['install_name'])),
        'boundary': 'System /usr/lib and /System/Library, macOS loader and kernel are not frozen.'}


def timing_tools(area_root, preparation):
    tools, sources = harness.timing_tools(area_root, preparation)
    tools['nextpnr_dynamic_dependencies'] = dynamic_dependencies(tools['nextpnr']['path'])
    validate_tools(tools)
    return tools, sources


def validate_tools(tools):
    harness.validate_timing_tools(tools)
    deps = tools.get('nextpnr_dynamic_dependencies')
    need(isinstance(deps, dict) and deps.get('files') and deps.get('edges') is not None, 'Native dependency inventory required')
    entries = deps['files'];need(len({e['path'] for e in entries}) == len(entries), 'Duplicate dependency file')
    for entry in entries:
        need(Path(entry['path']).is_absolute() and sha(entry['path']) == entry['sha256'], 'Dynamic dependency changed')
    need(any(e['path'] == tools['nextpnr']['path'] and e['sha256'] == tools['nextpnr']['sha256'] for e in entries), 'Router missing from dynamic closure')
    for edge in deps['edges']:
        need(str(Path(edge['path']).resolve()) == edge['resolved_path'] and sha(edge['path']) == edge['sha256']
            and any(e['path'] == edge['resolved_path'] and e['sha256'] == edge['sha256'] for e in entries), 'Dynamic alias or dependency changed')


def area_inputs(area_root, audit_path):
    """Explicit adapter for completed algebra-gated V10d; never reinterpret V10c."""
    area_root, audit_path = Path(area_root).resolve(), Path(audit_path).resolve()
    need(area_root == ROOT/AREA_ROOT and audit_path == area_root/'independent-audit.json', 'Exact audited V10d area root required')
    prep, _, pairs, _, bindings = area.validate_preparation(area_root)
    done_path = area_root/'measurements/completion.json';done = read(done_path);audit = read(audit_path)
    need(sha(area_root/'preparation.json') == AREA_PREPARATION_SHA and sha(done_path) == AREA_COMPLETION_SHA,
        'Exact completed V10d area identity required')
    need(done.get('complete') is True and done.get('failures') == [] and done.get('pair_count') == 32
        and done.get('frontend_jobs_completed') == done.get('successful_frontend_jobs') == 64
        and done.get('universal_actual_rtl_pairs_proved') == done.get('proof_records') == 32
        and done.get('fresh_synthesis_jobs_completed') == 64, 'Complete64/32/64 V10d area gate required')
    need(audit.get('schema') == 'isaforge-v10d-independent-portable-audit-v1' and audit.get('status') == 'pass'
        and audit.get('complete') is True and audit.get('failures') == []
        and audit.get('frontend_records_verified') == audit.get('arms_recounted') == 64
        and audit.get('rtl_pairs_proved_shared_checker') == 32
        and audit.get('audit_source_sha256') == sha(ROOT/'scripts/audit_v10d_hardware.py')
        and audit.get('completion_sha256') == sha(done_path) and audit.get('preparation_sha256') == AREA_PREPARATION_SHA,
        'Complete independently audited V10d raw evidence required')
    stage = area_root/'measurements'/done['attempt'];need(done['attempt'] == 'attempt-0000', 'Exact original area attempt required')
    files = {**bindings, done_path: sha(done_path), audit_path: sha(audit_path)}
    for name, field in [('completion.json', 'completion_sha256'), ('frontends.json', 'frontends_sha256'),
        ('algebra-proofs.json', 'algebra_proofs_sha256'), ('arm-measurements.json', 'arm_measurements_sha256'),
        ('summary.json', 'summary_sha256'), ('measurement-gate.json', 'measurement_gate_sha256')]:
        path = stage/name;expected = sha(done_path) if name == 'completion.json' else done[field]
        need(sha(path) == expected and (field not in audit or audit[field] == expected), 'Audited area stage changed: '+name);files[path] = expected
    raw = read(stage/'raw-evidence.json');archive = stage/'raw-evidence.zip'
    need(raw['completion_sha256'] == sha(done_path) and raw['archive_sha256'] == sha(archive) == audit['archive_sha256'], 'Audited area archive changed')
    for path in [stage/'raw-evidence.json', archive, area_root/'measurement-approval.json', area_root/'label-release.json']:
        files[path] = sha(path)
    need(files[area_root/'measurement-approval.json'] == done['approval_sha256']
        and files[area_root/'label-release.json'] == done['release_sha256'], 'Original area release changed')
    rows = read(stage/'arm-measurements.json');index = {(r['pair_id'], r['arm']): r for r in rows}
    need(len(index) == len(rows) == 64 and set(index) == {(p['pair_id'],a) for p in pairs for a in ARMS}, 'Exact64 area arm grid required')
    return prep, pairs, index, files


def preflight_inputs():
    root = ROOT/'results/2026-10-15-v10d-timing-preflight'
    final_path = root/'final-test-review.json';final = read(final_path)
    need(final.get('synthetic') is True and final.get('native_route_jobs_total') == 2
        and final.get('native_synthesis_jobs') == final.get('study_candidate_jobs') == 0
        and final.get('no_native_retries') is True and final['helper_source']['sha256'] == sha(paths.__file__)
        and final['helper_tests']['sha256'] == sha(ROOT/'tests/test_v10d_timing_paths.py'), 'Exact final two-toy preflight review required')
    expected = {root,root/'constant-zero'};files = [final_path]
    need(len(final['packages']) == 2 and {(ROOT/p['path']).resolve() for p in final['packages']} == expected,'Exactly two preserved preflight packages required')
    for package in final['packages']:
        folder = (ROOT/package['path']).resolve()
        need(set(package['files']) == {'README.md','raw-evidence.zip','raw-evidence.json','path-classification-review.json'},'Complete preflight package required')
        for name,value in package['files'].items():
            path = folder/name;need(sha(path) == value,'Preflight file changed');files.append(path)
        raw,review = read(folder/'raw-evidence.json'),read(folder/'path-classification-review.json')
        need(sha(folder/'raw-evidence.zip') == raw['archive_sha256'] and review.get('synthetic') is True
            and review.get('study_candidate_jobs') == review.get('native_synthesis_jobs') == 0
            and review.get('native_route_jobs') == 1 and review['shared_helper_sha256'] == sha(paths.__file__), 'Exact synthetic preflight lineage required')
        # Old per-route reviews deliberately retain their then-current test
        # hash; only final-test-review binds the final two-archive tests.
        with zipfile.ZipFile(folder/'raw-evidence.zip') as archive:
            need(len(archive.namelist()) == len(set(archive.namelist())) == len(raw['files']),'Complete preflight archive required')
            for entry in raw['files']:
                data = archive.read(entry['path'])
                need(len(data) == entry['bytes'] and digest(data) == entry['sha256'],'Synthetic preflight member changed')
    return files


def prepare(root, area_root=None, audit_path=None):
    root = Path(root).resolve();area_root = Path(area_root or ROOT/AREA_ROOT).resolve();audit_path = Path(audit_path or area_root/'independent-audit.json')
    need(root.is_relative_to(ROOT) and not root.exists(), 'Fresh repository-owned timing root required')
    sources = required_sources();need(all(p.is_file() for p in sources), 'Finish collector/auditor/tests/protocol before preparation')
    before = {p: sha(p) for p in sources}
    old, pairs, metrics, inherited = area_inputs(area_root, audit_path);tools, tool_sources = timing_tools(area_root, old)
    preflight = preflight_inputs();inherited.update({p:sha(p) for p in preflight})
    root.mkdir(parents=True)
    try:
        (root/'wrapper.v').write_text(harness.wrapper_rtl());(root/'common.pcf').write_text(harness.PCF)
        write(root/'recipe.json', recipe());write(root/'tools.json', tools)
        prepared = []
        for pair in pairs:
            row = {k: pair[k] for k in ('pair_id','source_candidate_id','constant_u32','context','formula','rewritten_formula')};row['arms'] = {}
            for arm in ARMS:
                source = checked(pair['arms'][arm]['rtl'], area_root)
                target = root/'rtl'/pair['pair_id'].split(':')[1]/arm/'candidate.v';copy(source,target)
                metric = metrics[pair['pair_id'],arm]
                row['arms'][arm] = {'formula': pair['arms'][arm]['formula'], 'candidate_rtl': record(target,root),
                    'wrapper_rtl': record(root/'wrapper.v',root), 'bare_lut4': metric['lut4_count'], 'bare_carry': metric['carry_count']}
            prepared.append(row)
        write(root/'pairs.json',prepared)
        need(all(sha(p) == value for p,value in {**before,**inherited}.items()), 'Inputs changed during timing preparation')
        files = sorted({*sources,*inherited,*tool_sources,*(p for p in root.rglob('*') if p.is_file())})
        manifest = {'schema': SCHEMA,'status': 'prepared-inputs-only','created_at_utc': now(), 'new_native_jobs':0,'model_fits':0,
            'area_root': os.path.relpath(area_root,root), 'area_preparation':record(area_root/'preparation.json',root),
            'area_completion':record(area_root/'measurements/completion.json',root), 'area_audit':record(audit_path,root),
            **{k:record(root/name,root) for k,name in [('recipe','recipe.json'),('tools','tools.json'),('pairs','pairs.json'),('wrapper','wrapper.v'),('pcf','common.pcf')]},
            'required_source_paths':[os.path.relpath(p,root) for p in sources], 'files':[record(p,root) for p in files]}
        write(root/'preparation.json',manifest);validate_preparation(root,check_runtime=True)
        return manifest
    except BaseException as error:
        write(root/'preparation-failure.json',{'error':repr(error),'created_at_utc':now(),'new_native_jobs':0});raise


def validate_preparation(root, *, check_runtime=False):
    root = Path(root).resolve();manifest = read(root/'preparation.json')
    need(root.is_relative_to(ROOT) and not (root/'preparation-failure.json').exists() and manifest.get('schema') == SCHEMA
        and manifest.get('status') == 'prepared-inputs-only' and type(manifest.get('new_native_jobs')) is int
        and manifest['new_native_jobs'] == manifest.get('model_fits') == 0, 'Valid input-only timing preparation required')
    bindings = {}
    for entry in manifest['files']:
        path = checked(entry,root);need(path not in bindings,'Duplicate preparation binding');bindings[path] = entry['sha256']
    def bound(entry):
        path = checked(entry,root);need(bindings.get(path) == entry['sha256'],'Reference absent from flat bindings');return path
    need(read(bound(manifest['recipe'])) == recipe() and bound(manifest['wrapper']).read_text() == harness.wrapper_rtl()
        and bound(manifest['pcf']).read_text() == harness.PCF, 'Fixed recipe/wrapper/PCF differs')
    area_root = (root/manifest['area_root']).resolve()
    for key,name in [('area_preparation','preparation.json'),('area_completion','measurements/completion.json'),('area_audit','independent-audit.json')]:
        need(bound(manifest[key]) == area_root/name, 'Area reference path differs')
    _, originals, metrics, inherited = area_inputs(area_root,bound(manifest['area_audit']))
    inherited.update({p:sha(p) for p in preflight_inputs()})
    need(all(bindings.get(p) == expected for p,expected in inherited.items()), 'Every audited area/preflight input/output binding must remain')
    pairs = read(bound(manifest['pairs']))
    need(len(pairs) == len({p['pair_id'] for p in pairs}) == 32
        and [(p['constant_u32'],p['context']) for p in pairs] == list(itertools.product(harness.CONSTANTS,harness.CONTEXTS)), 'Exact ordered32-pair cohort required')
    for pair,prior in zip(pairs,originals):
        need(set(pair['arms']) == set(ARMS) and all(pair[k] == prior[k] for k in ('pair_id','source_candidate_id','constant_u32','context','formula','rewritten_formula')), 'Original pair/formula identity changed')
        for arm in ARMS:
            row = pair['arms'][arm];metric = metrics[pair['pair_id'],arm]
            need(bound(row['candidate_rtl']).is_relative_to(root) and row['candidate_rtl']['sha256'] == prior['arms'][arm]['rtl']['sha256']
                and row['formula'] == prior['arms'][arm]['formula'] and row['wrapper_rtl'] == manifest['wrapper']
                and row['bare_lut4'] == metric['lut4_count'] and row['bare_carry'] == metric['carry_count'], 'Exact copied RTL/area/context differs')
    need(set(manifest['required_source_paths']) == {os.path.relpath(p,root) for p in required_sources()},'Required closure declaration differs')
    for path in required_sources(): need(bindings.get(path.resolve()) == sha(path),'Required source absent or changed')
    tools = read(bound(manifest['tools']))
    need(tools['area_tools'] == read(area_root/'tools.json'), 'Inherited area tool bytes differ')
    if check_runtime: validate_tools(tools)
    bindings[root/'preparation.json'] = sha(root/'preparation.json')
    return manifest,recipe(),pairs,tools,bindings


def validate_approval(root, approval):
    root,approval = Path(root).resolve(),Path(approval).resolve()
    need(approval == root/'measurement-approval.json','Exact root approval required')
    manifest,r,pairs,tools,bindings = validate_preparation(root,check_runtime=True);review = read(approval)
    expected = {'status':'approved-v10d-timing-measurements','preparation_sha256':sha(root/'preparation.json'),
        'recipe_sha256':manifest['recipe']['sha256'],'pairs_sha256':manifest['pairs']['sha256'],
        'collector_sha256':sha(__file__),'sequential_checker_sha256':sha(harness.__file__)}
    need(all(review.get(k) == v for k,v in expected.items()) and re.fullmatch('[0-9a-f]{40}',review.get('freeze_commit','')), 'Exact timing parent approval required')
    need(utc(review['reviewed_at_utc']) >= utc(manifest['created_at_utc']),'Review predates preparation')
    for path in bindings: committed(path,review['freeze_commit'])
    bindings[approval] = sha(approval)
    return manifest,r,pairs,tools,review,bindings


def mapping_script(folder):
    q = frozen._yosys_quote
    return '\n'.join([f'read_verilog {q(folder/"candidate.v")}',f'read_verilog {q(folder/"wrapper.v")}',
        'synth_ice40 -top timing_top','check -assert',f'write_json {q(folder/"ice40-netlist.json")}'])+'\n'


def mapped_arm(root,pair,arm,folder,tools,owner):
    folder.mkdir(parents=True);started = now();execution = None;error = None;counts = None;abc = None;libraries = None
    try:
        source = checked(pair['arms'][arm]['candidate_rtl'],root);wrapper = checked(pair['arms'][arm]['wrapper_rtl'],root)
        copy(source,folder/'candidate.v');copy(wrapper,folder/'wrapper.v');(folder/'ice40.ys').write_text(mapping_script(folder))
        execution = run_owned([tools['area_tools']['executables']['yosys']['path'],'-s',str(folder/'ice40.ys')],folder/'ice40.log',owner,360)
        need(execution['returncode'] == 0 and execution['timed_out'] is False,'Wrapped mapping failed/timeout')
        need((folder/'ice40-netlist.json').is_file(),'Successful mapping produced no netlist')
        text = (folder/'ice40.log').read_text(errors='replace')
        observed = re.findall(r"Parsing Verilog input from [`']([^']+)'",text)
        need(str(folder/'candidate.v') in observed and str(folder/'wrapper.v') in observed,'Candidate and common wrapper reads must be logged')
        # frozen library authenticator accepts one user RTL; remove only exact
        # wrapper read after separately authenticating those bytes above.
        sanitized = re.sub(r"Parsing Verilog input from [`']"+re.escape(str(folder/'wrapper.v'))+"'",'',text)
        libraries = frozen.data_invocations(sanitized,tools['area_tools'],folder/'candidate.v')
        abc = frozen.abc_invocations(text,tools['area_tools'])
        counts = dict(Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['timing_top']['cells'].values() if c['type'] != '$scopeinfo'))
        need(counts.get('SB_DFF') == 132 and set(counts) <= {'SB_DFF','SB_LUT4','SB_CARRY'},'Expected132FF/zeroBRAM primitive inventory')
    except Exception as exc: error = repr(exc)
    result = {'schema':'isaforge-v10d-timing-mapping-v1','pair_id':pair['pair_id'],'arm':arm,'success':error is None,
        'status':'complete' if error is None else 'timeout' if execution and execution['timed_out'] else 'failed',
        'error':error,'execution':execution,'started_at_utc':started,'completed_at_utc':now(),
        'command':[tools['area_tools']['executables']['yosys']['path'],'-s',str(folder/'ice40.ys')],
        'primitive_counts':counts,'bare_lut4':pair['arms'][arm]['bare_lut4'],'bare_carry':pair['arms'][arm]['bare_carry'],
        'abc_invocations':abc,'yosys_data_invocations':libraries,'yosys':tools['area_tools']['executables']['yosys']}
    for key,name in [('candidate_rtl_sha256','candidate.v'),('wrapper_rtl_sha256','wrapper.v'),('script_sha256','ice40.ys'),('log_sha256','ice40.log'),('netlist_sha256','ice40-netlist.json')]:
        result[key] = sha(folder/name) if (folder/name).is_file() else None
    write(folder/'mapping.json',result);return result


def sequential_check(pair,arm,mapping,scratch):
    started = now();result = None;error = None;folder = scratch/'mapping'/pair['pair_id'].split(':')[1]/arm
    try:
        need(mapping and mapping['success'] is True,'Successful wrapped mapping required')
        need(sha(folder/'ice40-netlist.json') == mapping['netlist_sha256'],'Mapped bytes changed before sequential check')
        samples = harness.vectors();result = harness.check_transactions(read(folder/'ice40-netlist.json'),samples,harness.oracle(pair['constant_u32'],pair['context'],samples))
        need(result['verified'] is True and result['transactions'] == 2148 and result['edges_per_parallel_frame'] == 99
            and result['boundary']['ff_count'] == 132,'Exact2148x99/132FF check required')
    except Exception as exc: error = repr(exc)
    row = {'schema':'isaforge-v10d-timing-sequential-record-v1','pair_id':pair['pair_id'],'arm':arm,'verified':error is None,
        'error':error,'started_at_utc':started,'completed_at_utc':now(),'netlist_sha256':mapping['netlist_sha256'] if mapping else None,
        'sequential_checker_sha256':sha(harness.__file__),'check':result}
    write(scratch/'sequential'/pair['pair_id'].split(':')[1]/arm/'check.json',row);return row


def route_command(tools,folder,mapped,pcf,seed):
    need(type(seed) is int and seed in SEEDS,'Fixed route seed required')
    return [tools['nextpnr']['path'],'--hx8k','--package','ct256','--json',str(mapped),'--pcf',str(pcf),
        '--asc',str(folder/'routed.asc'),'--report',str(folder/'report.json'),'--detailed-timing-report',
        '--write',str(folder/'packed.json'),'--freq','12','--seed',str(seed),'--threads','1']


def report_metrics(report):
    clocks = report.get('fmax');need(type(clocks) is dict and len(clocks) == 1,'Exactly one timed clock required')
    clock,value = next(iter(clocks.items()))
    need(type(clock) is str and clock and set(value) == {'achieved','constraint'} and type(value['achieved']) in (int,float)
        and math.isfinite(value['achieved']) and value['achieved'] > 0 and type(value['constraint']) in (int,float)
        and value['constraint'] == 12,'Fixed12MHz finite full-harness Fmax required')
    resources = report.get('utilization');need(type(resources) is dict and 'ICESTORM_LC' in resources,'Native utilization required')
    for name,row in resources.items():
        need(type(name) is str and set(row) == {'used','available'} and all(type(row[k]) is int and row[k] >= 0 for k in ('used','available'))
            and row['used'] <= row['available'],'Strict routed resource counts required')
    need(all(resources.get(k,{}).get('used') == n for k,n in [('ICESTORM_RAM',0),('ICESTORM_PLL',0),('SB_IO',4)]),'ZeroRAM/PLL andfourIO required')
    need(type(report.get('critical_paths')) is list and type(report.get('detailed_net_timings')) is list,'Detailed native timing report required')
    return {'clock':clock,'fmax_mhz':value['achieved'],'period_ns':1000/value['achieved'],'constraint_mhz':12,
        'meets_12mhz':value['achieved'] >= 12,'utilization':resources}


def validate_packed(packed, report, tools):
    need(set(packed.get('modules',{})) == {'top'},'One packed top module required')
    top = packed['modules']['top'];settings = top['settings'];cells = top['cells']
    need(settings.get('arch.type') == 'hx8k' and settings.get('arch.package') == 'ct256'
        and settings.get('target_freq') == '12000000.000000' and settings.get('threads') == '00000000000000000000000000000001',
        'Packed device/frequency/thread settings differ')
    counts = Counter(c['type'] for c in cells.values())
    need(set(counts) <= {'ICESTORM_LC','SB_IO','SB_GB'} and counts['SB_IO'] == 4 and counts['SB_GB'] == 1,
        'Exact packed LC/4IO/1GB inventory required')
    ff = 0
    for cell in cells.values():
        if cell['type'] != 'ICESTORM_LC':continue
        value = cell['parameters'].get('DFF_ENABLE')
        need(type(value) is str and re.fullmatch('[01]+',value) and int(value,2) in (0,1),'Defined packed FF enable required')
        ff += int(value,2)
    need(ff == 132,'Exactly132 packed FFs required')
    for kind in ('ICESTORM_LC','SB_IO','SB_GB'):
        need(report['utilization'].get(kind,{}).get('used') == counts[kind],'Packed resources disagree with native report')
    ports = top.get('ports',{});need(set(ports) == {'clk','serial_in','capture','serial_out'},'Exact four packed top ports required')
    assignments = {};selected = set()
    for name,port in ports.items():
        need(port.get('direction') == ('output' if name == 'serial_out' else 'input') and type(port.get('bits')) is list
            and len(port['bits']) == 1 and type(port['bits'][0]) is int,'Exact packed scalar port required')
        matches = [(key,cell) for key,cell in cells.items() if cell['type'] == 'SB_IO' and cell['connections'].get('PACKAGE_PIN') == port['bits']]
        need(len(matches) == 1 and matches[0][0] not in selected,'Unique packed IO driver/port assignment required')
        key,cell = matches[0];selected.add(key)
        match = re.fullmatch(r'X(\d+)/Y(\d+)/io(\d+)',cell['attributes'].get('NEXTPNR_BEL',''))
        need(match is not None and [int(match[i]) for i in (1,2,3)] == tools['pins'][name]['location'], 'Packed IO BEL differs from fixed package pin')
        assignments[name] = {'cell':key,'package_pin':tools['pins'][name]['pin'],'location':tools['pins'][name]['location']}
    need(len({tuple(row['location']) for row in assignments.values()}) == 4,'Distinct packed IO locations required')
    clock_io = cells[assignments['clk']['cell']]
    gb = next(cell for cell in cells.values() if cell['type'] == 'SB_GB')
    raw_clock,global_clock = gb['connections']['USER_SIGNAL_TO_GLOBAL_BUFFER'],gb['connections']['GLOBAL_BUFFER_OUTPUT']
    need(all(type(bits) is list and len(bits) == 1 and type(bits[0]) is int for bits in (raw_clock,global_clock))
        and raw_clock != global_clock and clock_io['connections'].get('D_IN_0') == raw_clock,'Actual topclock IO/global-buffer chain required')
    for cell in cells.values():
        if cell['type'] != 'ICESTORM_LC' or int(cell['parameters']['DFF_ENABLE'],2) == 0:continue
        negative = cell['parameters'].get('NEG_CLK')
        need(cell['connections'].get('CLK') == global_clock and type(negative) is str and re.fullmatch('0+',negative),
            'All132 packed FFs require the same positive global clock')
    clock = next(iter(report['fmax']))
    need(top.get('netnames',{}).get(clock,{}).get('bits') == global_clock,'Reported Fmax clock must be actual global FF clock')
    return {'ff_count':ff,'primitive_counts':dict(counts),'pin_assignments':assignments,
        'clock':clock,'clock_wire':global_clock[0]}


def routed_arm(pair,arm,seed,folder,tools,owner,scratch,gate):
    folder.mkdir(parents=True);started = now();execution = None;error = None;metrics = {};command = None
    mapping = scratch/'mapping'/pair['pair_id'].split(':')[1]/arm/'ice40-netlist.json'
    try:
        need(utc(started) >= utc(gate['route_started_at_utc']),'Route predates all64 sequential gate')
        copy(scratch/'common.pcf',folder/'common.pcf')
        command = route_command(tools,folder,mapping,folder/'common.pcf',seed)
        write(folder/'route-command.json',{'command':command,'started_at_utc':started,'timeout_seconds':180,
            'route_gate_sha256':sha(scratch/'route-gate.json'),'mapped_netlist_sha256':sha(mapping)})
        execution = run_owned(command,folder/'route.log',owner,180)
        need(execution['returncode'] == 0 and execution['timed_out'] is False,'Route failed/timeout; preserve any partial outputs')
        need(all((folder/name).is_file() for name in ('report.json','packed.json','routed.asc')),'Successful route missing native output')
        report = read(folder/'report.json');packed = read(folder/'packed.json')
        metrics = report_metrics(report);metrics['packed_inventory'] = validate_packed(packed,report,tools)
        need((folder/'routed.asc').read_text().startswith('.comment from next-pnr'),'Native ASC identity missing')
        analysis = paths.classify_paths(read(mapping),packed,report)
        metrics['path_audit'] = analysis;metrics['path_classification'] = analysis['classification']
    except Exception as exc: error = repr(exc)
    row = {'schema':'isaforge-v10d-timing-route-v1','pair_id':pair['pair_id'],'arm':arm,'seed':seed,'success':error is None,
        'status':'complete' if error is None else 'timeout' if execution and execution['timed_out'] else 'failed',
        'error':error,'execution':execution,'started_at_utc':started,'completed_at_utc':now(),'command':command,
        'route_gate_sha256':sha(scratch/'route-gate.json'),'mapped_netlist_sha256':sha(mapping),'nextpnr':tools['nextpnr'],
        'device':'iCE40HX8K','package':'CT256','target_frequency_mhz':12,'threads':1,'path_classification':'unknown',**metrics}
    for key,name in [('command_sha256','route-command.json'),('log_sha256','route.log'),('report_sha256','report.json'),('packed_json_sha256','packed.json'),('asc_sha256','routed.asc'),('pcf_sha256','common.pcf')]:
        row[key] = sha(folder/name) if (folder/name).is_file() else None
    write(folder/'route.json',row);return row


def distribution(values):
    return {'count':len(values),'mean':statistics.fmean(values),'median':statistics.median(values),'minimum':min(values),'maximum':max(values),
        'lower':sum(v<0 for v in values),'equal':sum(v==0 for v in values),'higher':sum(v>0 for v in values)}


def summary(pairs,mappings,checks,routes):
    mi = {(r['pair_id'],r['arm']):r for r in mappings};ci = {(r['pair_id'],r['arm']):r for r in checks};ri = {(r['pair_id'],r['arm'],r['seed']):r for r in routes}
    need(len(mi) == len(mappings) and len(ci) == len(checks) and len(ri) == len(routes),'Duplicate timing records')
    expected = {(p['pair_id'],a) for p in pairs for a in ARMS};grid = {(p['pair_id'],a,s) for p in pairs for a in ARMS for s in SEEDS}
    need(len(pairs) == 32 and len(expected) == 64 and set(mi) <= expected and set(ci) <= expected and set(ri) <= grid,'Unknown or filtered cohort identity')
    matrix = [{'pair_id':p['pair_id'],'arm':a,'seed':s,'status':ri[p['pair_id'],a,s]['status'] if (p['pair_id'],a,s) in ri else 'not-run',
        'error':ri[p['pair_id'],a,s].get('error') if (p['pair_id'],a,s) in ri else 'Phase gate incomplete or interrupted'} for p in pairs for a in ARMS for s in SEEDS]
    complete = set(mi) == set(ci) == expected and set(ri) == grid and all(r['success'] is True for r in mappings+routes) and all(r['verified'] is True for r in checks)
    paired = [];per_pair = []
    if complete:
        for p in pairs:
            local = []
            for seed in SEEDS:
                a,b = (ri[p['pair_id'],arm,seed] for arm in ARMS)
                row = {'pair_id':p['pair_id'],'formula':p['formula'],'constant_u32':p['constant_u32'],'context':p['context'],'seed':seed,
                    'original_fmax_mhz':a['fmax_mhz'],'csd_fmax_mhz':b['fmax_mhz'],'original_period_ns':a['period_ns'],'csd_period_ns':b['period_ns'],'original_meets_12mhz':a['meets_12mhz'],'csd_meets_12mhz':b['meets_12mhz'],
                    'csd_minus_original_period_ns':b['period_ns']-a['period_ns'],'csd_minus_original_fmax_mhz':b['fmax_mhz']-a['fmax_mhz'],
                    'original_utilization':a['utilization'],'csd_utilization':b['utilization'],
                    'original_path_classification':a['path_classification'],'csd_path_classification':b['path_classification']}
                for arm in ARMS:
                    m = mi[p['pair_id'],arm];row[arm+'_wrapped_primitive_counts'] = m['primitive_counts'];row[arm+'_bare_lut4'] = m['bare_lut4'];row[arm+'_bare_carry'] = m['bare_carry']
                paired.append(row);local.append(row)
            per_pair.append({k:p[k] for k in ('pair_id','formula','constant_u32','context')} | {'mean_csd_minus_original_period_ns':statistics.fmean(r['csd_minus_original_period_ns'] for r in local),
                'mean_csd_minus_original_fmax_mhz':statistics.fmean(r['csd_minus_original_fmax_mhz'] for r in local)})
    primary = None
    if complete:
        primary = {'paired_period_ns':distribution([r['mean_csd_minus_original_period_ns'] for r in per_pair]),
            'by_constant_period_ns':{str(k):distribution([r['mean_csd_minus_original_period_ns'] for r in per_pair if r['constant_u32']==k]) for k in harness.CONSTANTS},
            'by_context_period_ns':{k:distribution([r['mean_csd_minus_original_period_ns'] for r in per_pair if r['context']==k]) for k in harness.CONTEXTS}}
    return {'schema':'isaforge-v10d-timing-summary-v1','complete':complete,'primary':primary,'paired_routes':paired,'per_pair':per_pair,'failure_matrix':matrix,
        'available_route_records':len(routes),'successful_routes':sum(r['success'] is True for r in routes),'scope':recipe()['limits']}


def recheck(bindings,tools):
    need(all(p.is_file() and sha(p) == value for p,value in bindings.items()),'Timing source/input/release mutated');validate_tools(tools)


def guard(scratch,stage):
    need(area.workspace_bytes(scratch,stage) <= MAX_ATTEMPT_BYTES,'Attempt exceeded monitored4GiB workspace guard; retain evidence')


def phase(jobs,operation,output,name,stage,scratch,owner,failures,bindings,tools):
    # Bounded submission means a detected mutation prevents unstarted jobs.
    pending = {};iterator = iter(jobs);completed = 0;pool = ThreadPoolExecutor(max_workers=2)
    try:
        def submit():
            recheck(bindings,tools);guard(scratch,stage)
            job = next(iterator,None)
            if job is None:return
            key,args = job;pending[pool.submit(operation,*args)] = key
        submit();submit()
        while pending:
            ready,_ = wait(pending,timeout=1,return_when=FIRST_COMPLETED);guard(scratch,stage)
            for future in ready:
                key = pending.pop(future);completed += 1
                try:
                    row = future.result();output[key] = row
                    if row.get('success',row.get('verified')) is not True: failures.append({'phase':name,'job':key,'error':row.get('error')})
                except Exception as exc: failures.append({'phase':name,'job':key,'error':repr(exc)})
                write(stage/f'{name}-progress-{completed:04d}.json',{'phase':name,'completed':completed,'failures':failures,'at_utc':now()});submit()
    except BaseException:
        area.cancel(owner,failures);raise
    finally:
        try: pool.shutdown(wait=True,cancel_futures=True)
        except BaseException as exc:failures.append({'phase':'worker-pool-cleanup','error':repr(exc)});area.cancel(owner,failures)


def pack(scratch,stage,done):
    write(scratch/'completion.json',done);files = []
    with zipfile.ZipFile(stage/'raw-evidence.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in sorted(scratch.rglob('*')):
            need(not p.is_symlink(),'Raw evidence symlink forbidden')
            if not p.is_file():continue
            name = p.relative_to(ROOT).as_posix();need(name.startswith(PREFIX+'attempt-0000/'),'Raw archive escaped attempt')
            data = p.read_bytes();archive.writestr(name,data);files.append({'path':name,'size':len(data),'sha256':digest(data)})
    write(stage/'raw-evidence.json',{'schema':'isaforge-v10d-timing-raw-evidence-v1','attempt':done['attempt'],'archive':'raw-evidence.zip',
        'archive_sha256':sha(stage/'raw-evidence.zip'),'completion_sha256':sha(stage/'completion.json'),'files':files})


def collect(root,approval,*,attempt='attempt-0000',workers=2):
    root = Path(root).resolve();need(attempt == 'attempt-0000' and type(workers) is int and workers == 2,'One fixed attempt/twoworkers required')
    need(not (root/'measurements').exists() and not (root/'timing-release.json').exists(),'Single attempt; preserve all earlier outcomes')
    manifest,r,pairs,tools,review,bindings = validate_approval(root,approval)
    need(shutil.disk_usage(root).free >= MIN_FREE_BYTES,'At least8GiB free required')
    stage = root/'measurements'/attempt;scratch = ROOT/PREFIX/attempt
    need(not stage.exists() and not scratch.exists(),'Fresh timing attempt directories required');stage.mkdir(parents=True);scratch.mkdir(parents=True)
    release = {'schema':'isaforge-v10d-timing-release-v1','attempt':attempt,'released_at_utc':now(),'collection_repository':str(ROOT),
        'preparation_sha256':sha(root/'preparation.json'),'approval_sha256':sha(approval),'freeze_commit':review['freeze_commit'],
        'collector_sha256':sha(__file__),'sequential_checker_sha256':sha(harness.__file__),'tools_sha256':sha(root/'tools.json'),
        'wrapped_synthesis_jobs':64,'route_jobs':192,'paired_route_seeds':list(SEEDS),'workers':2,'threads_per_route':1,
        'native_environment':frozen.native_environment(tools['area_tools'])}
    write(root/'timing-release.json',release);bindings[root/'timing-release.json'] = sha(root/'timing-release.json')
    for name in ('preparation.json','pairs.json','recipe.json','tools.json','wrapper.v','common.pcf'):copy(root/name,scratch/name)
    copy(approval,scratch/'approval.json');copy(root/'timing-release.json',scratch/'release.json')
    copy(__file__,scratch/'collector-source.py');copy(harness.__file__,scratch/'sequential-checker-source.py');copy(frozen.__file__,scratch/'frozen-owner-source.py')
    copy(area.__file__,scratch/'resource-helper-source.py');copy(paths.__file__,scratch/'path-checker-source.py')
    owner = frozen.HardwareWorkers(tools['area_tools']);mappings = {};checks = {};routes = {};failures = [];gate = None;interruption = None
    def ordered(rows):return [rows[p['pair_id']+'/'+a] for p in pairs for a in ARMS if p['pair_id']+'/'+a in rows]
    try:
        jobs = [(p['pair_id']+'/'+a,(root,p,a,scratch/'mapping'/p['pair_id'].split(':')[1]/a,tools,owner)) for p in pairs for a in ARMS]
        phase(jobs,mapped_arm,mappings,'mapping',stage,scratch,owner,failures,bindings,tools)
        jobs = [(p['pair_id']+'/'+a,(p,a,mappings.get(p['pair_id']+'/'+a),scratch)) for p in pairs for a in ARMS]
        phase(jobs,sequential_check,checks,'sequential-check',stage,scratch,owner,failures,bindings,tools)
        write(stage/'mappings.json',ordered(mappings));write(stage/'sequential-checks.json',ordered(checks))
        if not failures and len(mappings) == len(checks) == 64 and all(c['verified'] is True for c in checks.values()):
            recheck(bindings,tools)
            gate = {'schema':'isaforge-v10d-timing-route-gate-v1','route_started_at_utc':now(),
                'mappings_sha256':sha(stage/'mappings.json'),'sequential_checks_sha256':sha(stage/'sequential-checks.json'),
                'required_verified_arms':64,'transactions_per_arm':2148,'edges_per_frame':99,'boundary_ff_count':132}
            need(all(utc(c['completed_at_utc']) <= utc(gate['route_started_at_utc']) for c in checks.values()),'Sequential completion after route gate')
            write(stage/'route-gate.json',gate);copy(stage/'route-gate.json',scratch/'route-gate.json')
            jobs = [(p['pair_id']+'/'+a+'/'+str(s),(p,a,s,scratch/'routes'/p['pair_id'].split(':')[1]/a/f'seed-{s}',tools,owner,scratch,gate)) for p in pairs for a in ARMS for s in SEEDS]
            phase(jobs,routed_arm,routes,'route',stage,scratch,owner,failures,bindings,tools)
    except BaseException as exc:interruption = exc;failures.append({'phase':'interruption-or-resource','error':repr(exc)});area.cancel(owner,failures)
    try:recheck(bindings,tools)
    except Exception as exc:failures.append({'phase':'provenance','error':repr(exc)})
    mapping_rows,check_rows = ordered(mappings),ordered(checks)
    route_rows = [routes[p['pair_id']+'/'+a+'/'+str(s)] for p in pairs for a in ARMS for s in SEEDS if p['pair_id']+'/'+a+'/'+str(s) in routes]
    for name,rows in [('mappings.json',mapping_rows),('sequential-checks.json',check_rows),('routes.json',route_rows)]:
        if not (stage/name).exists():write(stage/name,rows)
        copy(stage/name,scratch/name)
    report = summary(pairs,mapping_rows,check_rows,route_rows)
    try:need(area.workspace_bytes(scratch,stage)+area.workspace_bytes(scratch)+4*1024**2 <= MAX_ATTEMPT_BYTES,'Insufficient4GiB archive workspace allowance')
    except Exception as exc:failures.append({'phase':'archive-resource-reservation','error':repr(exc)})
    if failures:report['complete'] = False;report['primary'] = None
    write(stage/'summary.json',report);copy(stage/'summary.json',scratch/'summary.json')
    done = {'schema':'isaforge-v10d-timing-measurements-v1','complete':report['complete'],'attempt':attempt,'pair_count':32,
        'mapping_jobs_completed':len(mapping_rows),'successful_mappings':sum(r['success'] is True for r in mapping_rows),
        'sequential_checks_completed':len(check_rows),'verified_sequential_arms':sum(r['verified'] is True for r in check_rows),
        'route_jobs_completed':len(route_rows),'successful_routes':sum(r['success'] is True for r in route_rows),'planned_routes':192,
        'route_started_at_utc':gate['route_started_at_utc'] if gate else None,'route_gate_sha256':sha(stage/'route-gate.json') if gate else None,
        'failures':failures,'completed_at_utc':now(),'workers':2,'new_estimator_fits':0,'scratch_directory':scratch.relative_to(ROOT).as_posix(),
        'preparation_sha256':sha(root/'preparation.json'),'approval_sha256':sha(approval),'release_sha256':sha(root/'timing-release.json'),
        'tools_sha256':sha(root/'tools.json'),'collector_sha256':sha(__file__),'sequential_checker_sha256':sha(harness.__file__),
        **{key:sha(stage/name) for key,name in [('mappings_sha256','mappings.json'),('sequential_checks_sha256','sequential-checks.json'),('routes_sha256','routes.json'),('summary_sha256','summary.json')]}}
    write(stage/'completion.json',done);write(root/'measurements/completion.json',done)
    for p in sorted(stage.glob('*progress*.json')):copy(p,scratch/'progress'/p.name)
    pack(scratch,stage,done)
    if interruption is not None:raise interruption
    need(done['complete'],'Incomplete fixed timing attempt retained; primary remains pending')
    return done


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','validate','collect'))
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--area-root',type=Path);parser.add_argument('--audit',type=Path);parser.add_argument('--approval',type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':result = prepare(args.root,args.area_root,args.audit)
    elif args.action == 'validate':
        m,r,p,t,b = validate_preparation(args.root,check_runtime=True);result = {'status':'valid','pairs':len(p),'bindings':len(b),'new_native_jobs':0}
    else:
        if args.approval is None:parser.error('collect needs --approval')
        result = collect(args.root,args.approval)
    print(json.dumps(result,indent=2))
