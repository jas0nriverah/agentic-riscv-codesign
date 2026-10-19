#!/usr/bin/env python3
"""Portable raw V10d timing audit; never import collectors or launch native tools.

Mapped transaction verification reuses the frozen reviewed sequential checker.
Timing is the full registered harness endpoint, not attributed arithmetic delay.
"""
from __future__ import annotations
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import audit_v10d_hardware as area
import prepare_v10_timing as sequential
import v10d_timing_paths as paths

need, sha, loads, read, stamp, execution = area.need, area.sha, area.loads, area.read, area.stamp, area.execution
independent = area.independent
PREFIX = 'generated/v10d-timing/'
ARMS = ('original','csd')
SEEDS = (1,2,3)


def exact(value, expected):
    if type(value) is not type(expected):return False
    if type(value) is dict:return set(value)==set(expected) and all(exact(value[k],expected[k]) for k in value)
    if type(value) is list:return len(value)==len(expected) and all(exact(a,b) for a,b in zip(value,expected))
    return value==expected


def finite(value, *, positive=False):
    return type(value) in (int,float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def report_metrics(report):
    """Read the native single-clock Fmax and utilization; reject implicit domains."""
    clocks = report.get('fmax')
    need(type(clocks) is dict and len(clocks) == 1, 'Exactly one timed clock required')
    clock,value = next(iter(clocks.items()))
    need(type(clock) is str and clock and set(value) == {'achieved','constraint'}
        and finite(value['achieved'],positive=True) and type(value['constraint']) in (int,float)
        and value['constraint'] == 12, 'Fixed12MHz full-harness clock required')
    resources = report.get('utilization')
    need(type(resources) is dict and resources and 'ICESTORM_LC' in resources, 'Native utilization required')
    for name,row in resources.items():
        need(type(name) is str and set(row) == {'used','available'}
            and all(independent.integer(row[k]) for k in ('used','available'))
            and row['used'] <= row['available'], 'Strict routed resource inventory required')
    for name in ('ICESTORM_RAM','ICESTORM_PLL'):
        need(resources.get(name,{}).get('used') == 0, 'Unexpected RAM/PLL in fixed combinational harness')
    need(type(report.get('critical_paths')) is list and type(report.get('detailed_net_timings')) is list, 'Detailed native timing report required')
    return {'clock':clock,'fmax_mhz':value['achieved'],'period_ns':1000/value['achieved'],
        'constraint_mhz':12,'meets_12mhz':value['achieved'] >= 12,'utilization':resources}


def route_command(tools, folder, mapped, pcf, seed):
    need(type(seed) is int and seed in SEEDS, 'Fixed paired route seed required')
    return [tools['nextpnr']['path'],'--hx8k','--package','ct256','--json',str(mapped),'--pcf',str(pcf),
        '--asc',str(folder/'routed.asc'),'--report',str(folder/'report.json'),'--detailed-timing-report','--write',str(folder/'packed.json'),
        '--freq','12','--seed',str(seed),'--threads','1']


def mapping_script(folder):
    return '\n'.join([f'read_verilog {independent.quoted(folder/"candidate.v")}',
        f'read_verilog {independent.quoted(folder/"wrapper.v")}', 'synth_ice40 -top timing_top','check -assert',
        f'write_json {independent.quoted(folder/"ice40-netlist.json")}'])+'\n'


def archive_content(stage, done, attempt):
    raw = read(stage/'raw-evidence.json')
    need(raw.get('schema') == 'isaforge-v10d-timing-raw-evidence-v1' and raw['attempt'] == attempt
        and raw['archive'] == 'raw-evidence.zip' and raw['completion_sha256'] == sha((stage/'completion.json').read_bytes())
        and raw['archive_sha256'] == sha((stage/'raw-evidence.zip').read_bytes()), 'Archive/completion identity differs')
    index = {e['path']:e for e in raw['files']};need(len(index) == len(raw['files']), 'Duplicate archive binding')
    prefix = PREFIX+attempt+'/';content = {}
    with zipfile.ZipFile(stage/'raw-evidence.zip') as archive:
        need(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(index), 'Raw archive membership differs')
        for info in archive.infolist():
            p = PurePosixPath(info.filename);entry = index[info.filename]
            need(info.filename.startswith(prefix) and str(p) == info.filename and not p.is_absolute() and '..' not in p.parts
                and '\\' not in info.filename and not info.is_dir() and ((info.external_attr >> 16)&0o170000) in (0,0o100000), 'Unsafe raw archive member')
            data = archive.read(info)
            need(type(entry['size']) is int and entry['size'] >= 0 and len(data) == entry['size'] and sha(data) == entry['sha256'], 'Raw archive member changed')
            content[info.filename[len(prefix):]] = data
    return raw,content


def paired_results(pairs, routes):
    need(all(type(r['seed']) is int and r['seed'] in SEEDS and r['success'] is True
        and finite(r['fmax_mhz'],positive=True) and finite(r['period_ns'],positive=True)
        and r['period_ns']==1000/r['fmax_mhz'] for r in routes), 'Strict matched route endpoint values required')
    index = {(r['pair_id'],r['arm'],r['seed']):r for r in routes}
    keys = {(p['pair_id'],arm,seed) for p in pairs for arm in ARMS for seed in SEEDS}
    need(len(index) == len(routes) == 192 and set(index) == keys and all(r['success'] is True for r in routes), 'Complete192 successful route grid required')
    output = []
    for pair in pairs:
        for seed in SEEDS:
            a,b = (index[pair['pair_id'],arm,seed] for arm in ARMS)
            output.append({'pair_id':pair['pair_id'],'formula':pair['formula'],'constant_u32':pair['constant_u32'],
                'context':pair['context'],'seed':seed,'original_fmax_mhz':a['fmax_mhz'],'csd_fmax_mhz':b['fmax_mhz'],
                'original_period_ns':a['period_ns'],'csd_period_ns':b['period_ns'],
                'csd_minus_original_period_ns':b['period_ns']-a['period_ns'],
                'csd_minus_original_fmax_mhz':b['fmax_mhz']-a['fmax_mhz'],
                'original_utilization':a['utilization'],'csd_utilization':b['utilization'],
                'original_meets_12mhz':a['meets_12mhz'],'csd_meets_12mhz':b['meets_12mhz'],
                'original_path_classification':a.get('path_classification','unknown'),
                'csd_path_classification':b.get('path_classification','unknown')})
    def dist(values):
        return {'count':len(values),'mean':statistics.fmean(values),'median':statistics.median(values),
            'minimum':min(values),'maximum':max(values),'lower':sum(v<0 for v in values),
            'equal':sum(v==0 for v in values),'higher':sum(v>0 for v in values)}
    per_pair = [{'pair_id':p['pair_id'],'formula':p['formula'],'constant_u32':p['constant_u32'],'context':p['context'],
        'mean_csd_minus_original_period_ns':statistics.fmean(r['csd_minus_original_period_ns'] for r in output if r['pair_id']==p['pair_id']),
        'mean_csd_minus_original_fmax_mhz':statistics.fmean(r['csd_minus_original_fmax_mhz'] for r in output if r['pair_id']==p['pair_id'])} for p in pairs]
    summary = {'primary':{'paired_period_ns':dist([r['mean_csd_minus_original_period_ns'] for r in per_pair]),
        'paired_fmax_mhz':dist([r['mean_csd_minus_original_fmax_mhz'] for r in per_pair])},
        'per_pair':per_pair,'paired_period_ns':dist([r['csd_minus_original_period_ns'] for r in output]),
        'paired_fmax_mhz':dist([r['csd_minus_original_fmax_mhz'] for r in output]),
        'by_constant_period_ns':{str(k):dist([r['csd_minus_original_period_ns'] for r in output if r['constant_u32']==k]) for k in independent.CONSTANTS},
        'by_context_period_ns':{k:dist([r['csd_minus_original_period_ns'] for r in output if r['context']==k]) for k in independent.CONTEXTS},
        'scope':'Full-harness single-clock Fmax and reciprocal period; no arithmetic-only timing, CPU, power or population claim.'}
    return output,summary


def verify_mapping_bytes(pair, arm, candidate, wrapper, script, log, netlist_bytes, folder, tools, provenance, *, retain_sequential_failure=False):
    """Authenticate native inputs and independently recount the kept boundary."""
    need(arm in ARMS and sha(candidate) == pair['arms'][arm]['candidate_rtl']['sha256'], 'Wrapped arm source differs')
    need(wrapper.decode() == sequential.wrapper_rtl() and script.decode() == mapping_script(folder), 'Common wrapper or native mapping script differs')
    text = log.decode();parsed = re.findall(r"Parsing Verilog input from [`']([^']+)'",text)
    need(str(folder/'wrapper.v') in parsed, 'Actual wrapper input missing')
    # The frozen independent provenance helper accepts one source; remove only
    # the one exact wrapper parse line, then authenticate every remaining input.
    filtered = re.sub(r"^.*Parsing Verilog input from [`']"+re.escape(str(folder/'wrapper.v'))+r"'.*\n?",'',text,flags=re.MULTILINE)
    need(len(parsed)-len(re.findall(r"Parsing Verilog input from [`']([^']+)'",filtered)) == 1, 'Wrapper parsed repeatedly')
    independent.verify_provenance(filtered,provenance,tools['area_tools'],folder/'candidate.v')
    netlist = loads(netlist_bytes)
    need(netlist.get('creator') == tools['area_tools']['executables']['yosys']['version'], 'Mapped JSON creator differs')
    counts=dict(Counter(cell['type'] for cell in netlist['modules']['timing_top']['cells'].values() if cell['type']!='$scopeinfo'))
    need(counts.get('SB_DFF')==132 and set(counts)<={'SB_DFF','SB_LUT4','SB_CARRY'}, 'Mapped basic132FF primitive inventory differs')
    try:
        samples=independent.vectors();expected=independent.expected_values(pair['constant_u32'],pair['context'],samples)
        result=sequential.check_transactions(netlist,samples,expected)
        need(result['verified'] is True and result['transactions']==2148 and result['edges_per_parallel_frame']==99
            and result['initial_state_seed']==2026101524, 'Exact2148×99 sequential contract required')
        return counts,result
    except Exception as error:
        if not retain_sequential_failure:raise
        return counts,{'_sequential_error':repr(error)}


def verify_route_bytes(report_bytes, packed_bytes, asc_bytes, log_bytes, tools):
    """Read raw native endpoint evidence; no reconstruction of physical timing."""
    metrics = report_metrics(loads(report_bytes));packed = loads(packed_bytes)
    need(type(packed.get('modules')) is dict and set(packed['modules']) == {'top'}, 'Exactly one packed timing module required')
    module = next(iter(packed['modules'].values()))
    need(type(module.get('cells')) is dict and module['cells'], 'Packed physical cells required')
    need(packed.get('creator') == 'Next Generation Place and Route (Version )', 'Packed native creator differs')
    settings=module.get('settings',{})
    need(settings.get('arch.type')=='hx8k' and settings.get('arch.package')=='ct256'
        and settings.get('threads')=='00000000000000000000000000000001' and settings.get('target_freq')=='12000000.000000', 'Packed device/frequency/thread settings differ')
    cells = module['cells'];counts = Counter(cell['type'] for cell in cells.values())
    need(set(counts) <= {'ICESTORM_LC','SB_IO','SB_GB'} and counts.get('SB_IO')==4 and counts.get('SB_GB')==1, 'Packed fixed harness resource types differ')
    need(all(metrics['utilization'].get(k,{}).get('used')==counts.get(k,0) for k in ('SB_IO','SB_GB')), 'Packed IO/GB counts differ from report')
    need(all(type(cell.get('connections')) is dict and type(cell.get('parameters',{})) is dict for cell in cells.values()), 'Packed physical cell structure differs')
    ff=0
    for cell in cells.values():
        if cell['type']=='ICESTORM_LC':
            value=cell['parameters'].get('DFF_ENABLE')
            need(type(value) is str and re.fullmatch('[01]+',value) is not None and int(value,2) in (0,1), 'Defined packed FF enable required')
            ff+=int(value,2)
    need(ff==132, 'Exactly132 packed FFs required')
    # Packed iCE40 LC use is directly recountable; logical FF/carry counts are
    # separately recovered from the prepack mapped netlist, never conflated.
    need(counts.get('ICESTORM_LC',0) == metrics['utilization']['ICESTORM_LC']['used'], 'Packed LC count disagrees with native report')
    need(asc_bytes.startswith(b'.comment from next-pnr\n')
        and b'\n.device 8k\n' in asc_bytes and len(asc_bytes) > 30, 'Retained routed HX8K ASC required')
    log = log_bytes.decode()
    need('Program finished normally.' in log and 'ERROR:' not in log, 'Successful native route log required')
    assignments={};ports=module.get('ports',{})
    need(set(ports)=={'clk','serial_in','capture','serial_out'} and set(tools['pins'])==set(ports), 'Exact four packed top pins required')
    for name,port in ports.items():
        need(port['direction']==('output' if name=='serial_out' else 'input') and type(port['bits']) is list
            and len(port['bits'])==1 and type(port['bits'][0]) is int and port['bits'][0]>=0, 'Packed scalar pin identity differs')
        matches=[(n,c) for n,c in cells.items() if c['type']=='SB_IO' and c['connections'].get('PACKAGE_PIN')==port['bits']]
        need(len(matches)==1, 'Unique packed package IO required')
        cellname,cell=matches[0];bel=cell.get('attributes',{}).get('NEXTPNR_BEL','');match=re.fullmatch(r'X(\d+)/Y(\d+)/io(\d+)',bel)
        location=[int(v) for v in match.groups()] if match else None;pin=tools['pins'][name]
        need(pin['pin']=={'clk':'J3','serial_in':'L5','capture':'T6','serial_out':'D8'}[name]
            and type(pin['location']) is list and len(pin['location'])==3 and all(type(v) is int and v>=0 for v in pin['location'])
            and location==pin['location'], 'Actual packed pin placement differs from frozen PCF/package inventory')
        assignments[name]={'cell':cellname,'package_pin':pin['pin'],'location':location}
    need(len({a['cell'] for a in assignments.values()})==len({tuple(a['location']) for a in assignments.values()})==4, 'Packed IO pin/BEL identities collide')
    def scalar(bits):
        need(type(bits) is list and len(bits)==1 and type(bits[0]) is int and bits[0]>=0, 'Defined scalar clock wire required');return bits[0]
    clock_input=scalar(cells[assignments['clk']['cell']]['connections'].get('D_IN_0'))
    buffer=next(c for c in cells.values() if c['type']=='SB_GB')
    need(scalar(buffer['connections'].get('USER_SIGNAL_TO_GLOBAL_BUFFER'))==clock_input, 'Packed global clock input differs from clk IO')
    clock_wire=scalar(buffer['connections'].get('GLOBAL_BUFFER_OUTPUT'))
    need(clock_wire!=clock_input, 'Global clock output must be distinct')
    for cell in cells.values():
        if cell['type']=='ICESTORM_LC' and int(cell['parameters']['DFF_ENABLE'],2)==1:
            need(scalar(cell['connections'].get('CLK'))==clock_wire and type(cell['parameters'].get('NEG_CLK')) is str
                and re.fullmatch('0+',cell['parameters']['NEG_CLK']) is not None, 'All132FFs must use exact rising-edge wrapper clock')
    clock=metrics['clock'];need(scalar(module.get('netnames',{}).get(clock,{}).get('bits'))==clock_wire, 'Reported timing clock must identify actual wrapper global clock')
    metrics['packed_inventory']={'ff_count':ff,'primitive_counts':dict(counts),'pin_assignments':assignments,'clock':clock,'clock_wire':clock_wire}
    return metrics


def verify_support(bindings, root, prep):
    required = ['scripts/measure_v10d_timing.py','tests/test_measure_v10d_timing.py','docs/v10d-timing-protocol.md',
        'scripts/audit_v10d_timing.py','tests/test_audit_v10d_timing.py','scripts/prepare_v10_timing.py',
        'tests/test_prepare_v10_timing.py','docs/v10-timing-direction.md','scripts/v10d_timing_paths.py','tests/test_v10d_timing_paths.py']
    declared={(root/path).resolve() for path in prep['required_source_paths']}
    for name in required:
        path=ROOT/name
        need(path in declared and bindings.get(path)==sha(path.read_bytes()), 'Required timing source/test/protocol missing')
    preflight=ROOT/'results/2026-10-15-v10d-timing-preflight';final_path=preflight/'final-test-review.json';final=read(final_path)
    need(bindings.get(final_path)==sha(final_path.read_bytes()) and final.get('synthetic') is True
        and exact(final.get('native_route_jobs_total'),2) and exact(final.get('native_synthesis_jobs'),0)
        and exact(final.get('study_candidate_jobs'),0) and final.get('no_native_retries') is True
        and final['helper_source']['sha256']==sha(Path(paths.__file__).read_bytes())
        and final['helper_tests']['sha256']==sha((ROOT/'tests/test_v10d_timing_paths.py').read_bytes()), 'Final two-toy preflight review differs')
    need(len(final['packages'])==2 and {(ROOT/p['path']).resolve() for p in final['packages']}=={preflight,preflight/'constant-zero'}, 'Exactly two preserved preflight packages required')
    for package in final['packages']:
        folder=(ROOT/package['path']).resolve()
        need(set(package['files'])=={'README.md','raw-evidence.zip','raw-evidence.json','path-classification-review.json'}, 'Complete preflight package required')
        for name,digest in package['files'].items():
            path=folder/name;need(bindings.get(path)==sha(path.read_bytes())==digest, 'Preflight package bytes unbound/changed')
        raw,review=read(folder/'raw-evidence.json'),read(folder/'path-classification-review.json')
        need(sha((folder/'raw-evidence.zip').read_bytes())==raw['archive_sha256'] and review.get('synthetic') is True
            and exact(review.get('study_candidate_jobs'),0) and exact(review.get('native_synthesis_jobs'),0)
            and exact(review.get('native_route_jobs'),1) and review['shared_helper_sha256']==sha(Path(paths.__file__).read_bytes()), 'Synthetic preflight lineage differs')
        with zipfile.ZipFile(folder/'raw-evidence.zip') as archive:
            index={e['path']:e for e in raw['files']}
            need(len(archive.namelist())==len(set(archive.namelist()))==len(index)==len(raw['files']) and set(archive.namelist())==set(index), 'Preflight member closure differs')
            for name,e in index.items():
                data=archive.read(name);need(type(e['bytes']) is int and len(data)==e['bytes'] and sha(data)==e['sha256'], 'Preflight member changed')


def preparation(root):
    prep = read(root/'preparation.json')
    need(prep.get('schema') == 'isaforge-v10d-timing-preparation-v1' and prep.get('status') == 'prepared-inputs-only'
        and not (root/'preparation-failure.json').exists() and type(prep.get('new_native_jobs')) is int and prep['new_native_jobs']==0
        and type(prep.get('model_fits')) is int and prep['model_fits']==0, 'Input-only timing preparation required')
    bindings={}
    for entry in prep['files']:
        need(set(entry)=={'path','sha256'} and type(entry['path']) is str and not Path(entry['path']).is_absolute(), 'Relative flat binding required')
        path=(root/entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in bindings and sha(path.read_bytes())==entry['sha256'], 'Bound timing input/source changed')
        bindings[path]=entry['sha256']
    def bound(entry):
        path=(root/entry['path']).resolve();need(bindings.get(path)==entry['sha256'], 'Reference missing from preparation bindings');return path
    verify_support(bindings,root,prep)
    need(prep['area_preparation']['sha256']=='7c3b89e1405f8c999ac7cc95ceeb7f71971e5cd7a94225a9b1b600651c057560'
        and prep['area_completion']['sha256']=='83676a2f949bad0276160e7d8a82aa2ded2beaf2352c9fe9d47706de7dbf3f3c', 'Exact completed V10d area input required')
    area_root=(root/prep['area_root']).resolve();area_prep=read(bound(prep['area_preparation']))
    need(bound(prep['area_preparation'])==area_root/'preparation.json' and bound(prep['area_completion'])==area_root/'measurements/completion.json', 'Area root identity differs')
    area_report=area.run(area_root)
    need(area_report['status']=='pass' and area_report['complete'] is True and len(area_report['pairs'])==32
        and read(bound(prep['area_audit']))==area_report, 'Complete freshly replayed V10d area audit required')
    for entry in area_prep['files']:
        need(bindings.get((area_root/entry['path']).resolve())==entry['sha256'], 'Inherited area input/source missing')
    pairs,tools,recipe=(read(bound(prep[k])) for k in ('pairs','tools','recipe'))
    original_pairs=read(area_root/area_prep['pairs']['path'])
    need(len(pairs)==32 and len({p['pair_id'] for p in pairs})==32 and [(p['constant_u32'],p['context']) for p in pairs]==list(itertools.product(independent.CONSTANTS,independent.CONTEXTS)), 'Full32 timing grid required')
    for p,prior in zip(pairs,original_pairs):
        need(all(p[k]==prior[k] for k in ('pair_id','source_candidate_id','constant_u32','context','formula','rewritten_formula')) and type(p['constant_u32']) is int and set(p['arms'])==set(ARMS), 'Timing cohort/formula lineage changed')
        for arm in ARMS:
            area_pair=next(row for row in area_report['pairs'] if row['pair_id']==p['pair_id'])
            need(type(p['arms'][arm]['bare_lut4']) is int and type(p['arms'][arm]['bare_carry']) is int
                and p['arms'][arm]['bare_lut4']==area_pair[arm+'_lut4'] and p['arms'][arm]['bare_carry']==area_pair[arm+'_carry'], 'Copied bare area count differs')
            need(p['arms'][arm]['formula']==prior['arms'][arm]['formula'] and p['arms'][arm]['candidate_rtl']['sha256']==prior['arms'][arm]['rtl']['sha256']
                and bound(p['arms'][arm]['candidate_rtl']).is_relative_to(root), 'Exact original/CSD bytes required')
    need(bound(prep['wrapper']).read_text()==sequential.wrapper_rtl() and bound(prep['pcf']).read_text()==sequential.PCF, 'Fixed common wrapper/PCF differs')
    need(json.dumps(recipe,sort_keys=True)==json.dumps(fixed_recipe(),sort_keys=True), 'Fixed192-route timing recipe differs')
    need(tools['area_tools']==read(area_root/area_prep['tools']['path']), 'Inherited synthesis tool identity changed')
    history=tools['historical_protocol'];path=(ROOT/history['path']).resolve()
    need(path.is_relative_to(ROOT) and bindings.get(path)==history['sha256'], 'Historical route protocol missing from preparation')
    routing=read(path)
    need(routing['device']=='iCE40HX8K' and routing['package']=='CT256' and routing['target_frequency_mhz']==12 and routing['seeds']==[1,2,3]
        and routing['nextpnr_binary_sha256']==tools['nextpnr']['sha256'] and routing['nextpnr_version_output']==tools['nextpnr']['version_output']
        and routing['chipdb_sha256']==tools['chipdb']['sha256'], 'Inherited fixed route tool/device policy differs')

    need(bindings.get(Path(sequential.__file__).resolve())==sha(Path(sequential.__file__).read_bytes())
        and bindings.get(Path(paths.__file__).resolve())==sha(Path(paths.__file__).read_bytes())
        and bindings.get(Path(__file__).resolve())==sha(Path(__file__).read_bytes()), 'Auditor/shared sequential checker source unbound')
    return prep,pairs,tools,recipe,bindings,bound,area_report


def fixed_recipe():
    return {'schema':'isaforge-v10d-timing-recipe-v1','timing':sequential.recipe(),
        'mapping_script':['read_verilog candidate.v','read_verilog wrapper.v','synth_ice40 -top timing_top','check -assert','write_json ice40-netlist.json'],
        'route_detailed_timing_report':True,'all64_sequential_checks_before_any_route':True,'automatic_retries':False,
        'bootstrap':False,'clock_relaxation':False,'min_free_bytes':8*1024**3,'workspace_guard_bytes':4*1024**3,
        'primary':'32 equal-weight formula means of three paired seed csd-minus-original reciprocal-Fmax periods in ns',
        'incomplete_primary':None,'retained_route_slots':192,
        'limits':'Common132FF four-pin harness timing; no arithmetic-only delay, CPU performance, power, board validation or population inference.'}


def unique_records(rows, keys, expected):
    result={}
    for row in rows:
        key=tuple(row[k] for k in keys)
        need(key not in result and key in expected, 'Duplicate/foreign phase record')
        if 'seed' in keys:need(type(row['seed']) is int and row['seed'] in SEEDS,'Exact integer route seed required')
        result[key]=row
    return result


def record_chronology(row):
    need(stamp(row['completed_at_utc'])>=stamp(row['started_at_utc']), 'Phase completion predates start')


def file_hashes(row, content, stem, fields):
    for key,name in fields:
        digest=row[key]
        need((digest is None and stem+name not in content) or (digest is not None and sha(content[stem+name])==digest), 'Raw phase file hash differs: '+name)


def verify_mapping(pair, arm, row, content, folder, tools):
    stem='mapping/'+pair['pair_id'].split(':')[1]+'/'+arm+'/'
    need(row.get('schema')=='isaforge-v10d-timing-mapping-v1' and row['pair_id']==pair['pair_id'] and row['arm']==arm
        and type(row['success']) is bool, 'Strict mapping identity required');record_chronology(row)
    need(loads(content[stem+'mapping.json'])==row,'Archived mapping record differs')
    file_hashes(row,content,stem,[('candidate_rtl_sha256','candidate.v'),('wrapper_rtl_sha256','wrapper.v'),('script_sha256','ice40.ys'),('log_sha256','ice40.log'),('netlist_sha256','ice40-netlist.json')])
    need(row['command']==[tools['area_tools']['executables']['yosys']['path'],'-s',str(folder/'ice40.ys')], 'Actual mapping command differs')
    need(row['bare_lut4']==pair['arms'][arm]['bare_lut4'] and row['bare_carry']==pair['arms'][arm]['bare_carry']
        and all(independent.integer(row[k]) for k in ('bare_lut4','bare_carry')), 'Bare resource identity differs')
    if not row['success']:
        need(row['error'] is not None and row['status'] in ('failed','timeout'), 'Failed mapping lacks error');return None,None
    need(execution(row['execution']) and row['error'] is None and row['status']=='complete', 'Successful mapping native status differs')
    counts,check=verify_mapping_bytes(pair,arm,*(content[stem+name] for name in ('candidate.v','wrapper.v','ice40.ys','ice40.log','ice40-netlist.json')),folder,tools,row,retain_sequential_failure=True)
    need(row['primitive_counts']==counts and all(independent.integer(v) and v>0 for v in row['primitive_counts'].values()), 'Mapped primitive recount differs')
    return loads(content[stem+'ice40-netlist.json']),check


def verify_check(pair, arm, row, mapping, check, content, checker_sha):
    stem='sequential/'+pair['pair_id'].split(':')[1]+'/'+arm+'/'
    need(row.get('schema')=='isaforge-v10d-timing-sequential-record-v1' and row['pair_id']==pair['pair_id'] and row['arm']==arm
        and type(row['verified']) is bool and row['sequential_checker_sha256']==checker_sha,'Strict sequential record required');record_chronology(row)
    need(loads(content[stem+'check.json'])==row and row['netlist_sha256']==(mapping['netlist_sha256'] if mapping else None), 'Sequential/raw mapped identity differs')
    if mapping and mapping['success'] is True:
        need(stamp(row['started_at_utc'])>=stamp(mapping['completed_at_utc']), 'Sequential check predates mapped completion')
        if '_sequential_error' in check:
            need(row['verified'] is False and row['check'] is None and row['error']==check['_sequential_error'], 'Recorded sequential failure replay differs')
        else:need(row['verified'] is True and row['error'] is None and exact(row['check'],check), 'Shared sequential replay differs')
    else:need(row['verified'] is False and row['check'] is None and row['error'] is not None, 'Failed mapping cannot pass sequential gate')


def verify_route(pair, arm, seed, row, content, folder, mapped_folder, tools, gate, gate_sha, mapping_graph):
    stem='routes/'+pair['pair_id'].split(':')[1]+'/'+arm+'/seed-'+str(seed)+'/'
    need(row.get('schema')=='isaforge-v10d-timing-route-v1' and row['pair_id']==pair['pair_id'] and row['arm']==arm
        and type(row['seed']) is int and row['seed']==seed and type(row['success']) is bool, 'Strict route identity required');record_chronology(row)
    need(loads(content[stem+'route.json'])==row and row['route_gate_sha256']==gate_sha
        and stamp(row['started_at_utc'])>=stamp(gate['route_started_at_utc']), 'Route record/gate chronology differs')
    expected_command=route_command(tools,folder,mapped_folder/'ice40-netlist.json',folder/'common.pcf',seed)
    need(row['command']==expected_command and row['nextpnr']==tools['nextpnr'] and row['device']=='iCE40HX8K' and row['package']=='CT256'
        and type(row['target_frequency_mhz']) is int and row['target_frequency_mhz']==12 and type(row['threads']) is int and row['threads']==1, 'Fixed native route policy/tool differs')
    file_hashes(row,content,stem,[('command_sha256','route-command.json'),('log_sha256','route.log'),('report_sha256','report.json'),('packed_json_sha256','packed.json'),('asc_sha256','routed.asc'),('pcf_sha256','common.pcf')])
    command=loads(content[stem+'route-command.json'])
    need(command=={'command':expected_command,'started_at_utc':row['started_at_utc'],'timeout_seconds':180,
        'route_gate_sha256':gate_sha,'mapped_netlist_sha256':row['mapped_netlist_sha256']}, 'Archived prelaunch route command differs')
    need(content[stem+'common.pcf'].decode()==sequential.PCF and row['mapped_netlist_sha256']==sha(content['mapping/'+pair['pair_id'].split(':')[1]+'/'+arm+'/ice40-netlist.json']), 'Route read different mapped source/PCF')
    if not row['success']:
        need(row['error'] is not None and row['status'] in ('failed','timeout'), 'Failed route lacks retained error');return None
    need(execution(row['execution']) and row['error'] is None and row['status']=='complete','Successful route native status differs')
    metrics=verify_route_bytes(*(content[stem+name] for name in ('report.json','packed.json','routed.asc','route.log')),tools)
    need(all(exact(row[k],v) for k,v in metrics.items()), 'Native report endpoint values or fixed12MHz success differ')
    path_audit=paths.classify_paths(mapping_graph,loads(content[stem+'packed.json']),loads(content[stem+'report.json']))
    need(row['path_classification']==path_audit['classification'] and exact(row['path_audit'],path_audit), 'Packed path classification replay differs')
    return metrics


def study_summary(pairs,mappings,checks,routes,failures):
    expected={(p['pair_id'],a) for p in pairs for a in ARMS};grid={(p['pair_id'],a,s) for p in pairs for a in ARMS for s in SEEDS}
    mi=unique_records(mappings,('pair_id','arm'),expected);ci=unique_records(checks,('pair_id','arm'),expected);ri=unique_records(routes,('pair_id','arm','seed'),grid)
    complete=set(mi)==set(ci)==expected and set(ri)==grid and all(r['success'] is True for r in mappings+routes) and all(r['verified'] is True for r in checks)
    matrix=[{'pair_id':p['pair_id'],'arm':a,'seed':s,'status':ri[p['pair_id'],a,s]['status'] if (p['pair_id'],a,s) in ri else 'not-run',
        'error':ri[p['pair_id'],a,s].get('error') if (p['pair_id'],a,s) in ri else 'Phase gate incomplete or interrupted'} for p in pairs for a in ARMS for s in SEEDS]
    paired=[];per_pair=[];primary=None
    if complete:
        paired,summary=paired_results(pairs,routes);per_pair=summary['per_pair']
        for row in paired:
            for arm in ARMS:
                m=mi[row['pair_id'],arm];row[arm+'_wrapped_primitive_counts']=m['primitive_counts'];row[arm+'_bare_lut4']=m['bare_lut4'];row[arm+'_bare_carry']=m['bare_carry']
        primary={'paired_period_ns':summary['primary']['paired_period_ns'],
            'by_constant_period_ns':{str(k):area.distribution([r['mean_csd_minus_original_period_ns'] for r in per_pair if r['constant_u32']==k]) for k in independent.CONSTANTS},
            'by_context_period_ns':{k:area.distribution([r['mean_csd_minus_original_period_ns'] for r in per_pair if r['context']==k]) for k in independent.CONTEXTS}}
    return {'schema':'isaforge-v10d-timing-summary-v1','complete':complete and not failures,'primary':primary if not failures else None,
        'paired_routes':paired,'per_pair':per_pair,'failure_matrix':matrix,'available_route_records':len(routes),
        'successful_routes':sum(r['success'] is True for r in routes),'scope':fixed_recipe()['limits']}


def run(root):
    root=Path(root).resolve();prep,pairs,tools,recipe,bindings,bound,area_report=preparation(root)
    done=read(root/'measurements/completion.json');attempt=done['attempt'];stage=root/'measurements'/attempt
    need(attempt=='attempt-0000' and done.get('schema')=='isaforge-v10d-timing-measurements-v1' and type(done['complete']) is bool
        and done['pair_count']==32 and type(done['pair_count']) is int and type(done['failures']) is list
        and done['preparation_sha256']==sha((root/'preparation.json').read_bytes()) and read(stage/'completion.json')==done, 'Strict timing completion/root identity required')
    for k,value in [('workers',2),('planned_routes',192),('new_estimator_fits',0)]:need(type(done[k]) is int and done[k]==value,'Fixed completion count differs')
    need(done['scratch_directory']==PREFIX+attempt,'Exact raw attempt required')
    for name,key in [('measurement-approval.json','approval_sha256'),('timing-release.json','release_sha256'),('tools.json','tools_sha256')]:
        need(sha((root/name).read_bytes())==done[key], 'Completed reviewed input changed')
    approval,release=read(root/'measurement-approval.json'),read(root/'timing-release.json')
    need(approval.get('status')=='approved-v10d-timing-measurements' and re.fullmatch('[0-9a-f]{40}',approval['freeze_commit'])
        and release.get('schema')=='isaforge-v10d-timing-release-v1' and release['attempt']==attempt and release['freeze_commit']==approval['freeze_commit'], 'Exact parent release required')
    for key,value in [('preparation_sha256',done['preparation_sha256']),('recipe_sha256',prep['recipe']['sha256']),('pairs_sha256',prep['pairs']['sha256']),
        ('collector_sha256',done['collector_sha256']),('sequential_checker_sha256',done['sequential_checker_sha256'])]:need(approval[key]==value,'Approval/source identity differs')
    need(stamp(approval['reviewed_at_utc'])>=stamp(prep['created_at_utc']) and stamp(release['released_at_utc'])>=stamp(approval['reviewed_at_utc']), 'Release chronology differs')
    for k in ('preparation_sha256','approval_sha256','collector_sha256','sequential_checker_sha256','tools_sha256'):need(release[k]==done[k],'Release digest differs')
    for k,n in [('wrapped_synthesis_jobs',64),('route_jobs',192),('workers',2),('threads_per_route',1)]:need(type(release[k]) is int and release[k]==n,'Strict release counts required')
    need(release['paired_route_seeds']==[1,2,3] and all(type(s) is int for s in release['paired_route_seeds']), 'Exact paired seed release required')
    base=independent.absolute(release['collection_repository'])
    parents=sorted({str(independent.absolute(e['path']).parent) for e in tools['area_tools']['executables'].values()})
    need(release['native_environment']=={'PATH':':'.join([*parents,'/usr/bin','/bin']),'ABC':tools['area_tools']['executables']['abc']['path'],'LANG':'C','LC_ALL':'C','TZ':'UTC'}, 'Pinned native environment differs')
    raw,content=archive_content(stage,done,attempt)
    for name,path in [('preparation.json',root/'preparation.json'),('pairs.json',bound(prep['pairs'])),('recipe.json',bound(prep['recipe'])),
        ('tools.json',bound(prep['tools'])),('wrapper.v',bound(prep['wrapper'])),('common.pcf',bound(prep['pcf'])),
        ('approval.json',root/'measurement-approval.json'),('release.json',root/'timing-release.json')]:need(content[name]==path.read_bytes(),'Archived preparation/release bytes differ')
    need(loads(content['completion.json'])==done,'Archived completion differs')
    for name,path,key in [('collector-source.py',ROOT/'scripts/measure_v10d_timing.py','collector_sha256'),
        ('sequential-checker-source.py',Path(sequential.__file__),'sequential_checker_sha256')]:
        need(sha(content[name])==done[key]==bindings.get(path.resolve()), 'Bound archived collector/checker source differs')
    need(done['sequential_checker_sha256']==sha(Path(sequential.__file__).read_bytes()),'Current shared sequential checker differs')
    for name,path in [('frozen-owner-source.py',ROOT/'scripts/measure_v10_csd_hardware.py'),('resource-helper-source.py',ROOT/'scripts/measure_v10d_csd_hardware.py'),('path-checker-source.py',Path(paths.__file__))]:
        need(sha(content[name])==bindings.get(path.resolve()),'Native ownership/resource source binding differs')
    phases={}
    for name,key in [('mappings.json','mappings_sha256'),('sequential-checks.json','sequential_checks_sha256'),('routes.json','routes_sha256'),('summary.json','summary_sha256')]:
        data=(stage/name).read_bytes();need(sha(data)==done[key] and content[name]==data,'Stage/raw phase identity differs');phases[name]=loads(data)
    expected={(p['pair_id'],a) for p in pairs for a in ARMS};grid={(p['pair_id'],a,s) for p in pairs for a in ARMS for s in SEEDS}
    pmap={p['pair_id']:p for p in pairs};mappings,checks,routes=(phases[name] for name in ('mappings.json','sequential-checks.json','routes.json'))
    mi=unique_records(mappings,('pair_id','arm'),expected);ci=unique_records(checks,('pair_id','arm'),expected);ri=unique_records(routes,('pair_id','arm','seed'),grid)
    graphs={};replays={};mapped_arms=[]
    for (pid,arm),row in mi.items():
        folder=base/PREFIX/attempt/'mapping'/pid.split(':')[1]/arm
        graph,check=verify_mapping(pmap[pid],arm,row,content,folder,tools);graphs[pid,arm]=graph;replays[pid,arm]=check
        need(stamp(row['started_at_utc'])>=stamp(release['released_at_utc']), 'Mapping started before release')
        if check is not None:mapped_arms.append({'pair_id':pid,'arm':arm,'formula':pmap[pid]['arms'][arm]['formula'],
            'primitive_counts':row['primitive_counts'],'bare_lut4':row['bare_lut4'],'bare_carry':row['bare_carry'],
            'transactions':check.get('transactions',0),'inventory':check.get('boundary'),'sequential_error':check.get('_sequential_error')})
    for (pid,arm),row in ci.items():verify_check(pmap[pid],arm,row,mi.get((pid,arm)),replays.get((pid,arm)),content,done['sequential_checker_sha256'])
    gate=None;gate_sha=done['route_gate_sha256']
    if done['route_started_at_utc'] is not None:
        data=(stage/'route-gate.json').read_bytes();gate=loads(data)
        need(sha(data)==gate_sha and content['route-gate.json']==data and gate['schema']=='isaforge-v10d-timing-route-gate-v1'
            and gate['route_started_at_utc']==done['route_started_at_utc'] and gate['mappings_sha256']==done['mappings_sha256']
            and gate['sequential_checks_sha256']==done['sequential_checks_sha256'] and set(mi)==set(ci)==expected
            and all(r['success'] is True for r in mappings) and all(r['verified'] is True for r in checks), 'All64 mapped/sequential arms required before route gate')
        for k,v in [('required_verified_arms',64),('transactions_per_arm',2148),('edges_per_frame',99),('boundary_ff_count',132)]:need(type(gate[k]) is int and gate[k]==v,'Strict route gate contract differs')
        need(all(stamp(r['completed_at_utc'])<=stamp(gate['route_started_at_utc']) for r in checks), 'Route gate predates sequential check')
    else:need(gate_sha is None and not routes, 'Routes without full sequential gate')
    audited_routes=[]
    for (pid,arm,seed),row in ri.items():
        need(gate is not None,'Ungated route')
        folder=base/PREFIX/attempt/'routes'/pid.split(':')[1]/arm/f'seed-{seed}';mapped=base/PREFIX/attempt/'mapping'/pid.split(':')[1]/arm
        metrics=verify_route(pmap[pid],arm,seed,row,content,folder,mapped,tools,gate,gate_sha,graphs[pid,arm])
        audited_routes.append(dict(row))
    summary=study_summary(pairs,mappings,checks,routes,done['failures'])
    need(exact(summary,phases['summary.json']) and summary['complete'] is done['complete'], 'Independent full-cohort summary differs')
    counts={'mapping_jobs_completed':len(mappings),'successful_mappings':sum(r['success'] is True for r in mappings),
        'sequential_checks_completed':len(checks),'verified_sequential_arms':sum(r['verified'] is True for r in checks),
        'route_jobs_completed':len(routes),'successful_routes':sum(r['success'] is True for r in routes)}
    need(all(type(done[k]) is int and done[k]==v for k,v in counts.items()),'Exact completion denominators differ')
    need(all(stamp(row['completed_at_utc'])<=stamp(done['completed_at_utc']) for row in mappings+checks+routes),'Completion predates phase record')
    if done['complete']:need(not done['failures'] and len(mapped_arms)==64 and len(routes)==192,'Complete fixed study with failures/missing rows')
    return {'schema':'isaforge-v10d-timing-independent-portable-audit-v1','status':'pass','complete':done['complete'],
        'preparation_sha256':done['preparation_sha256'],'completion_sha256':sha((stage/'completion.json').read_bytes()),
        'archive_sha256':raw['archive_sha256'],'audit_source_sha256':sha(Path(__file__).read_bytes()),
        'shared_sequential_checker_sha256':done['sequential_checker_sha256'],'area_completion_sha256':area_report['completion_sha256'],
        'archive_members_verified':len(content),'mappings_recounted':len(mapped_arms),
        'sequential_transactions_checked':sum(r['transactions'] for r in mapped_arms),
        'sequential_edge_lane_comparisons':sum(r['transactions']*99 for r in mapped_arms),
        'routes_verified':len(routes),'successful_routes':counts['successful_routes'],'failures':done['failures'],
        'mapped_arms':mapped_arms,'routes':audited_routes,'paired_results':summary['paired_routes'] if done['complete'] else [],
        'per_pair':summary['per_pair'] if done['complete'] else [],'summary':summary if done['complete'] else None,
        'failure_matrix':summary['failure_matrix'],
        'path_classification_counts':dict(Counter(r.get('path_classification','unknown') for r in routes)),
        'timing_miss_counts':{arm:sum(r['arm']==arm and r['success'] is True and r['meets_12mhz'] is False for r in routes) for arm in ARMS},
        'independence':'No native tools or collector imports. Portable raw hashes/commands, source lineage, resources and report arithmetic independently checked. Mapped99-edge transactions reuse the frozen reviewed sequential checker. Critical path classification is descriptive; full-harness Fmax is not arithmetic-only timing, CPU, power or population evidence.'}


audit=run
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=run(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(result,indent=2))
