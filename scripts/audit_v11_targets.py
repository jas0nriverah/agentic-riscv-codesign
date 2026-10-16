#!/usr/bin/env python3
"""Independent saved-evidence V11 target admission; stdlib, no native or ML calls.

The pinned V9 u32 oracle is shared. RTL/harness rendering, vector regeneration,
archive checks, worker chronology and mapped-resource recount are independent.
This authenticates recorded execution, not a new simulator run or universal proof.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import posixpath
import random
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT/'results/2026-10-15-v9-coverage-development/independent-audit/unsigned_oracle.py'
ORACLE_SHA = '6d97a070e15e7ccad75051cf641ea7526be9ed25239b3622c405755985d983c3'
ATTEMPT, PREFIX, SEED, VECTORS = 'attempt-0000', 'generated/v11-transfer-targets', 2026101611, 2148
FAMILIES = {'ammunition':'arbitrary-precision-bit-strings','audiobeam':'audio-beamforming',
            'pm':'numeric-template-matching','fmref':'fm-reception','fac':'integer-recurrences',
            'recursion':'integer-recurrences'}
FF_TYPES = set('SB_DFF SB_DFFE SB_DFFSR SB_DFFR SB_DFFSS SB_DFFS SB_DFFESR SB_DFFER SB_DFFESS SB_DFFES SB_DFFN SB_DFFNE SB_DFFNSR SB_DFFNR SB_DFFNSS SB_DFFNS SB_DFFNESR SB_DFFNER SB_DFFNESS SB_DFFNES'.split())
BRAM_TYPES = set('SB_RAM40_4K SB_RAM40_4KNR SB_RAM40_4KNW SB_RAM40_4KNRNW'.split())
POLICY = {'seed':SEED,'random_vectors':2048,'boundary_vectors':100,'vectors_per_original':2148,
          'verification_batch_maximum':128,'mapping_workers':2,'worker_seconds':360,'poll_seconds':.25,
          'archive_seconds':300,'initial_free_bytes':16*1024**3,'minimum_free_bytes':8*1024**3,
          'maximum_attempt_bytes':8*1024**3,'maximum_archive_bytes':6*1024**3,
          'maximum_log_bytes':64*1024**2,'maximum_raw_file_bytes':1024**3,
          'retries':0,'replacement_candidates':0,'historical_labels_reused':False,'original_rtl_only':True,'new_fits':0}
MANDATORY_SOURCES = ('scripts/measure_v11_transfer.py','tests/test_measure_v11_transfer.py',
    'scripts/audit_v11_targets.py','tests/test_audit_v11_targets.py','scripts/measure_v6.py',
    'scripts/evaluate_v6.py','scripts/predict_v11_transfer.py','scripts/prepare_v11_model_comparison.py',
    'scripts/score_v11_transfer.py','isaforge/rtl.py','isaforge/v4_validation.py','isaforge/v4_corpus.py',
    'docs/v11-comparison-reporting-plan.md','docs/v11b-transfer-protocol.md')
MODELS = {'V6':('results/2026-10-14-v6/models/mapping_v6.joblib','1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56',1665),
          'V9':('results/2026-10-15-v9-coverage-development/fit-attempt-0000/models/mapping-coverage.joblib','dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d',1713)}
MODEL_METADATA_SHA = {'V6':'42d21cd093ed9b863668fcc01d12ed4d09ebb1590e0bdffb408fdf66d5f74676',
                      'V9':'0af6acebfd07cfa0688c36777a14bff816a5c254032050bcf75b1ff1c947dd06'}
BASE_TOOLS = 'results/2026-10-15-v10d-csd-hardware/tools.json'
BASE_TOOLS_SHA = 'ee267f729fb235c4a60b0688b9130cea987bcbf7076a347b0316d8f7089f547a'
PREDICTOR_SOURCES = {
    'c5866c012e6451eb30b6666383df07863fecf2299eb30ed6486178343cf5c51c':'scripts/predict_v11_transfer.py',
    '2d70ea85b6217281ea76f4616a502f44c984ec5f8ebd0a0de2becabd9a01b7d7':'scripts/predict_v11d_transfer.py'}


def need(condition, message):
    if not condition: raise ValueError(message)
def digest(body): return hashlib.sha256(body).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for body in iter(lambda:stream.read(1024**2),b''): h.update(body)
    return h.hexdigest()
def loads(body):
    def unique(items):
        result={}
        for k,v in items: need(k not in result,'Duplicate JSON key'); result[k]=v
        return result
    return json.loads(body,object_pairs_hook=unique,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def read(path): return loads(Path(path).read_bytes())
def same(a,b): return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def integer(value):
    need(type(value) is int and value>=0,'Nonnegative integer required'); return value
def finite(value):
    try: good=type(value) in (int,float) and math.isfinite(value) and value>=0
    except OverflowError: good=False
    need(good,'Finite nonnegative value required'); return value
def utc(value):
    d=datetime.fromisoformat(value); need(d.tzinfo is not None and d.utcoffset().total_seconds()==0,'UTC timestamp required'); return d
def hash_value(value): need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'SHA256 required'); return value
def norm(path): return PurePosixPath(posixpath.normpath(str(path)))
def identifier(formula): return 'v11-original:'+digest(formula.encode())
def oracle_module():
    need(sha(ORACLE)==ORACLE_SHA,'Pinned independent u32 oracle changed')
    spec=importlib.util.spec_from_file_location('v11_independent_unsigned_oracle',ORACLE)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
oracle=oracle_module()


def canonical(formula):
    tree=oracle.parse(formula)
    def text(node):
        if isinstance(node,tuple): return node[0]+'('+','.join(map(text,node[1:]))+')'
        return str(node)
    need(text(tree)==formula,'Canonical original formula required'); return formula


def original_rtl(formula,module='candidate'):
    """Independent full frozen grammar emitter, including RV32 mux shifts."""
    need(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',module),'Invalid module')
    tree=oracle.parse(formula); names={}
    lines=[f'module {module}(input wire [31:0] in0, in1, output wire [31:0] result);']
    binary={'add':'+','addi':'+','sub':'-','and':'&','andi':'&','or':'|','ori':'|','xor':'^','xori':'^','mul':'*'}
    def emit(node):
        if type(node) is int: return f"32'h{node&0xffffffff:08x}"
        if isinstance(node,str): return node
        if node in names: return names[node]
        op=node[0]; args=[emit(v) for v in node[1:]]; a=args[0]; b=args[1] if len(args)>1 else ''
        n=f'n{len(names)}'; names[node]=n
        if op=='lui': expr=a
        elif op in binary: expr=a+' '+binary[op]+' '+b
        elif op in ('sll','slli','srl','srli','sra','srai'):
            lines.extend([f'wire [31:0] shift_{n} = {b};',f'wire [31:0] value_{n} = {a};']); prior=f'value_{n}'
            for bit in range(5):
                distance=2**bit
                if op in ('sll','slli'): shifted='{'+f"{prior}[{31-distance}:0], {distance}'b0"+'}'
                elif op in ('srl','srli'): shifted='{'+f"{distance}'b0, {prior}[31:{distance}]"+'}'
                else: shifted='{{'+str(distance)+'{'+f'{prior}[31]'+'}}, '+f'{prior}[31:{distance}]'+'}'
                stage=f'stage_{n}_{bit}'; lines.append(f'wire [31:0] {stage} = shift_{n}[{bit}] ? {shifted} : {prior};'); prior=stage
            expr=prior
        elif op in ('slt','slti','sltu','sltiu'):
            condition=f'$signed({a}) < $signed({b})' if op in ('slt','slti') else f'{a} < {b}'
            expr="{31'b0, ("+condition+')}'
        elif op in ('mulh','mulhsu','mulhu'):
            left,right,product=f'a_{n}',f'b_{n}',f'p_{n}'
            lines.extend([f'wire [31:0] {left} = {a};',f'wire [31:0] {right} = {b};'])
            sign_a='{32{'+left+'[31]}}' if op!='mulhu' else "32'b0"
            sign_b='{32{'+right+'[31]}}' if op=='mulh' else "32'b0"
            lines.append(f'wire signed [63:0] {product} = $signed({{{sign_a}, {left}}}) * $signed({{{sign_b}, {right}}});')
            expr=product+'[63:32]'
        else: raise ValueError('Unsupported RTL operation')
        lines.append(f'wire [31:0] {n} = {expr};'); return n
    result=emit(tree); lines.extend([f'assign result = {result};','endmodule','']); return '\n'.join(lines).encode()


def verification_rtl(formulas):
    ports=', '.join(f'output wire [31:0] out_{i}' for i in range(len(formulas)))
    lines=[f'module verification_top(input wire [31:0] in0, in1, {ports});']
    lines.extend(f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(formulas)))
    lines.append('endmodule'); lines.extend(original_rtl(f,f'candidate_{i}').decode() for i,f in enumerate(formulas)); return '\n'.join(lines).encode()


def verification_cpp(count):
    integer(count); need(count>0,'Nonempty verification batch')
    lines=['#include "Vverification_top.h"','#include "verilated.h"','#include <fstream>','#include <iostream>','#include <cstdint>',
        'int main(int argc, char **argv) { Verilated::commandArgs(argc, argv);',
        'Vverification_top top; std::ifstream vectors(argv[1]); uint32_t a,b,want; unsigned count=0;',
        'while(vectors >> std::hex >> a >> b) { top.in0=a; top.in1=b; top.eval();']
    for i in range(count):
        lines.append(f'if (!(vectors >> std::hex >> want) || top.out_{i} != want) {{ std::cerr << "Mismatch formula {i} vector " << std::dec << count << " got " << std::hex << top.out_{i} << " expected " << want << "\\n"; return 1; }}')
    lines.extend(['++count; }','std::cout << count << " vectors passed\\n"; top.final(); return 0; }']); return '\n'.join(lines).encode()


def pairs():
    yield from itertools.product(oracle.BOUNDARIES,repeat=2)
    rng=random.Random(SEED)
    for _ in range(2048): yield rng.getrandbits(32),rng.getrandbits(32)


def verify_vectors(body,formulas):
    lines=body.decode().splitlines(); need(len(lines)==VECTORS,'Exactly2148 input vectors required')
    trees=[oracle.parse(f) for f in formulas]
    for index,((a,b),line) in enumerate(zip(pairs(),lines)):
        expected=' '.join(f'{v:08x}' for v in (a,b,*[oracle.evaluate(t,a,b) for t in trees]))
        need(line==expected,f'Independent vector/input/output differs at{index}')
    need(body.endswith(b'\n'),'Vector EOF newline differs'); return len(formulas)*VECTORS


def recount(netlist):
    """Count instantiated primitives, never library definitions or cached labels."""
    need(type(netlist) is dict and type(netlist.get('modules')) is dict and 'candidate' in netlist['modules'],'Missing candidate netlist')
    module=netlist['modules']['candidate']; ports=module['ports']
    need(set(ports)=={'in0','in1','result'},'Original datapath ports differ')
    for name,direction in [('in0','input'),('in1','input'),('result','output')]:
        need(ports[name]['direction']==direction and len(ports[name]['bits'])==32,'Original32-bit port required')
    need(type(module.get('cells')) is dict,'Mapped cell dictionary required')
    counts=Counter()
    for cell in module['cells'].values():
        need(type(cell) is dict and type(cell.get('type')) is str,'Invalid instantiated cell')
        counts[cell['type']]+=1
    need(set(counts)<={'SB_LUT4','SB_CARRY'}|FF_TYPES|BRAM_TYPES,'Unsupported mapped primitive')
    return {'lut4':counts['SB_LUT4'],'carry':counts['SB_CARRY'],'ff':sum(counts[t] for t in FF_TYPES),
            'bram':sum(counts[t] for t in BRAM_TYPES),'primitive_counts':dict(counts)}


def check_parallel(intervals,maximum=2):
    events=[]
    for start,end in intervals:
        a,b=utc(start),utc(end); need(a<=b,'Worker negative duration')
        if a!=b: events.extend([(a,1),(b,-1)])
    active=0; peak=0
    for _,change in sorted(events,key=lambda x:(x[0],x[1])):
        active+=change; peak=max(peak,active)
    need(peak<=maximum,'More than2 overlapping mapping workers'); return peak


class Archive:
    def __init__(self,stage):
        self.stage=Path(stage); self.manifest=read(self.stage/'raw-evidence.json'); m=self.manifest
        need(m['schema']=='isaforge-v11-target-archive-v1' and m['complete'] is True and m['attempt']==ATTEMPT,'Complete raw target archive required')
        self.path=self.stage/'raw-evidence.zip'; need(sha(self.path)==m['archive_sha256'],'Raw archive SHA differs')
        need(self.path.stat().st_size<=POLICY['maximum_archive_bytes'],'Archive byte cap exceeded')
        self.zip=zipfile.ZipFile(self.path); self.entries={}
        for row in m['files']:
            name=row['path']; p=PurePosixPath(name)
            need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and str(p)==name,'Unsafe archive path')
            need(name not in self.entries and not {'obj_dir','obj_dir_wrapv'}.intersection(p.parts),'Duplicate/compiler-object archive member')
            integer(row['bytes']); hash_value(row['sha256']); self.entries[name]=row
        names=self.zip.namelist(); need(len(names)==len(set(names)) and set(names)==set(self.entries),'Archive inventory incomplete/duplicate')
        allowed={'measurement-plan.json','measurement-tools.json','measurement-approval.json','label-release.json','point-freeze.json','verification-gate.json'}
        need(all(n in allowed or PurePosixPath(n).parts[0] in {'sources','stage','verification','circuits'} for n in names),'Unexpected archive top-level evidence')
        for info in self.zip.infolist():
            need(not info.is_dir() and not stat.S_ISLNK(info.external_attr>>16),'Archive links/directories forbidden')
            row=self.entries[info.filename]; need(info.file_size==row['bytes'],'Archive byte size differs')
            cap=POLICY['maximum_log_bytes'] if info.filename.endswith('.log') else POLICY['maximum_raw_file_bytes']
            need(info.file_size<=cap,'Archived raw/log byte cap exceeded')
            h=hashlib.sha256(); size=0
            with self.zip.open(info) as stream:
                for body in iter(lambda:stream.read(1024**2),b''): h.update(body); size+=len(body)
            need(size==row['bytes'] and h.hexdigest()==row['sha256'],'Archive member SHA differs')
        need(sha(self.stage/'completion.json')==m['completion_sha256'],'Archive completion SHA differs')
        for name in ('completion.json','verification.json','unique-measurements.json','labels.json'):
            need(self.body('stage/'+name)==(self.stage/name).read_bytes(),'Live/archive stage bytes differ')
        # stage/... entries already count those physical stage files once.
        minimum_retained=sum(r['bytes'] for r in self.entries.values())+self.path.stat().st_size+(self.stage/'raw-evidence.json').stat().st_size
        need(minimum_retained<=POLICY['maximum_attempt_bytes'],'Retained evidence exceeds whole-attempt cap')
    def body(self,name): need(name in self.entries,'Missing archived evidence: '+name); return self.zip.read(name)
    def json(self,name): return loads(self.body(name))
    def text(self,name): return self.body(name).decode()
    def hash(self,name): need(name in self.entries,'Missing archived evidence: '+name); return self.entries[name]['sha256']
    def close(self): self.zip.close()


def native_log(text,metric,tools,original_path):
    observed_yosys(text,tools)
    observed=[]; abc=tools['executables']['abc']
    for quoted,plain in re.findall(r'Running ABC command:\s*(?:"([^"]+)"|(\S+))',text):
        name=quoted or plain
        if name=='<yosys-exe-dir>/yosys-abc': name=str(PurePosixPath(tools['executables']['yosys']['path']).parent/'yosys-abc')
        need(norm(name)==norm(abc['path']),'Actual ABC path differs')
        observed.append({'path':abc['path'],'sha256':abc['sha256']})
    need(same(observed,metric['abc_invocations']),'ABC invocation record differs')  # zero/wire can omit ABC
    base=norm(tools['yosys_data']['path']); inventory={r['path']:r['sha256'] for r in tools['yosys_data']['files']}; data={}
    for name in re.findall(r"Parsing Verilog input from [`']([^']+)'",text):
        if name==original_path: continue
        path=norm(name); need(path.is_absolute() and path.is_relative_to(base),'Unsealed Yosys library path')
        relative=path.relative_to(base).as_posix(); need(relative in inventory,'Unsealed Yosys library member')
        row=data.setdefault(relative,{'sha256':inventory[relative],'resolved_path':str(path),'logged_paths':[]})
        if name not in row['logged_paths']: row['logged_paths'].append(name)
    need('ice40/cells_sim.v' in data and same(data,metric['data_invocations']),'Yosys data provenance differs')


def observed_yosys(text,tools):
    version=tools['executables']['yosys']['version']
    need(type(version) is str and version.strip() and version in text,'Observed Yosys version differs')


def command_alias(invoked,name,tools):
    """Validate the saved which() alias and its separately pinned resolved target.

    We cannot resolve producer symlinks on a portable replay host. The sealed
    resolved_commands entry records the actual resolution in the worker env.
    """
    resolved=tools['resolved_commands'][name]
    hash_value(resolved['sha256']); need(norm(resolved['path']).is_absolute(),'Resolved command identity missing')
    candidates={norm(resolved['path'])}
    for parent in tools['environment']['PATH'].split(':'):
        if parent and PurePosixPath(parent).is_absolute(): candidates.add(norm(PurePosixPath(parent)/name))
    need(norm(invoked) in candidates,'Unsealed command alias')


def worker_source(body):
    tree=ast.parse(body); values=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORKER' for t in node.targets): values.append(ast.literal_eval(node.value))
    need(len(values)==1 and type(values[0]) is str,'Single frozen WORKER literal required'); return values[0]


def check_worker(archive,folder,kind,payload,tools,source,after,before):
    row=archive.json(folder+'/worker.json'); command=row['command']
    need(row['schema']=='isaforge-v11-target-worker-v1' and row['kind']==kind and row['complete'] is True,'Incomplete owned worker')
    need(type(row['returncode']) is int and row['returncode']==0 and row['primary_error'] is None and row['cleanup_errors']==[] and row['remaining_owned_children']==[],'Worker execution/cleanup failed')
    need(type(row['timeout_seconds']) is int and row['timeout_seconds']==360 and finite(row['elapsed_seconds'])<=370,'Worker budget differs')
    need(utc(after)<=utc(row['started_at_utc'])<=utc(row['completed_at_utc'])<=utc(before),'Worker chronology differs')
    need((utc(row['completed_at_utc'])-utc(row['started_at_utc'])).total_seconds()<=370,'Worker wall-clock budget differs')
    identity=row['python_invocation']; expected=tools['executables']['python']
    need(identity['resolved']==expected['path'] and identity['sha256']==expected['sha256'],'Worker Python identity differs')
    need(type(command) is list and len(command)==4 and command[:3]==[identity['invoked'],'-c',source],'Frozen worker command differs')
    need(same(loads(command[3]),payload),'Exact worker payload differs')
    need(archive.hash(folder+'/worker.log')==row['log_sha256'],'Worker log hash differs')
    return row


def verify_batch(archive,folder,formulas,proof,tools,source,absolute_folder,after,before,override_sha):
    need(same(proof,archive.json(folder+'/worker.result.json')),'Verification worker result differs')
    expected={'verified':True,'formula_count':len(formulas),'vectors_per_formula':2148,'total_comparisons':2148*len(formulas),'random_seed':SEED,
              'v4_validation_override_sha256':override_sha,'rtl_sha256':archive.hash(folder+'/verification.v'),'vectors_sha256':archive.hash(folder+'/vectors.txt')}
    need(all(k in proof and same(proof[k],v) for k,v in expected.items()),'Incomplete batch verification')
    need(type(proof['signed_overflow_workaround_applied']) is bool and type(proof['tool']) is str and proof['tool'].strip(),'Simulator identity required')
    need(archive.body(folder+'/verification.v')==verification_rtl(formulas),'Independent original batch RTL differs')
    need(archive.body(folder+'/verification.cpp')==verification_cpp(len(formulas)),'Harness does not check every batch output')
    comparisons=verify_vectors(archive.body(folder+'/vectors.txt'),formulas)
    archive.body(folder+'/verilator-build.log')
    payload={'kind':'verify','formulas':formulas,'folder':absolute_folder,'seed':SEED,'result':absolute_folder+'/worker.result.json'}
    worker=check_worker(archive,folder,'verify',payload,tools,source,after,before)
    fallback=proof['signed_overflow_workaround_applied']; boundary=0
    if not fallback:
        need(proof['oracle']=='Python integer RV32 semantics' and archive.text(folder+'/verification.log').strip()=='2148 vectors passed','Original RTL runtime success missing')
        need(not any(n.startswith(folder+'/initial-failure') or n==folder+'/validation-resolution.json' for n in archive.entries),'Undeclared fallback evidence')
    else:
        incident=archive.json(folder+'/initial-failure.json'); need(same(incident,proof['incident']),'Fallback incident differs')
        i=integer(incident['formula_index']); j=integer(incident['vector_index']); need(i<len(formulas) and j<VECTORS and incident['formula']==formulas[i],'Fallback incident index/formula differs')
        a,b=list(pairs())[j]; expected_hex=f'{oracle.evaluate(oracle.parse(formulas[i]),a,b):x}'
        got,expected_value=incident['got_hex'],incident['expected_hex']
        need(re.fullmatch('[0-9a-f]+',got) and re.fullmatch('[0-9a-f]+',expected_value) and int(got,16)!=int(expected_value,16) and int(expected_value,16)==int(expected_hex,16),'Fallback expected/got mismatch invalid')
        mismatch=f'Mismatch formula {i} vector {j} got {got} expected {expected_value}'
        need(incident['original_error'].startswith('RTL correctness failed: ') and mismatch in incident['original_error']
             and mismatch in archive.text(folder+'/initial-failure.log') and mismatch in archive.text(folder+'/verification.log'),'Initial failure not preserved')
        need(incident['resolution']=='identical RTL rebuilt with defined signed wrapping; boundary cross-check in Yosys','Fallback resolution differs')
        need(archive.text(folder+'/verification-wrapv.log').strip()=='2148 vectors passed','Defined-wrap runtime success missing')
        archive.body(folder+'/verilator-wrapv-build.log')
        command=[tools['resolved_commands']['verilator']['path'],'--cc','--exe','--build','-j','2','-Wno-fatal','-CFLAGS','-fwrapv','--top-module','verification_top','--Mdir',absolute_folder+'/obj_dir_wrapv',absolute_folder+'/verification.v',absolute_folder+'/verification.cpp']
        # shutil.which retains the PATH alias rather than resolving symlinks.
        observed=proof['build_command']; need(type(observed) is list and observed[1:]==command[1:],'Defined-wrap exact build command differs')
        command_alias(observed[0],'verilator',tools); command_alias(proof['compiler_path'],'c++',tools)
        need(type(proof['compiler_version']) is str and proof['compiler_version'].strip(),'Compiler provenance missing')
        need(same(proof,archive.json(folder+'/validation-resolution.json')),'Fallback final resolution differs')
        cross=folder+'/yosys-boundary-cross-check'; absolute_cross=absolute_folder+'/yosys-boundary-cross-check'
        need(archive.body(cross+'/candidate.v')==original_rtl(formulas[i]),'Fallback candidate RTL changed')
        boundary_pairs=list(itertools.product(oracle.BOUNDARIES,repeat=2))
        script='\n'.join([f'read_verilog "{absolute_cross}/candidate.v"','prep -top candidate',*[f'eval -set in0 {x} -set in1 {y} -show result' for x,y in boundary_pairs]])+'\n'
        need(archive.text(cross+'/eval.ys')==script,'Boundary Yosys command differs')
        observed_yosys(archive.text(cross+'/eval.log'),tools)
        values=re.findall(r"Eval result: \\result = (32'[01]+|[0-9]+)\.",archive.text(cross+'/eval.log'))
        values=[int(v.split("'")[1],2) if "'" in v else int(v) for v in values]
        wanted=[oracle.evaluate(oracle.parse(formulas[i]),x,y) for x,y in boundary_pairs]
        need(values==wanted,'Independent100-boundary outputs differ')
        observations=[{'in0':x,'in1':y,'result':v} for (x,y),v in zip(boundary_pairs,wanted)]
        need(same(observations,archive.json(cross+'/observations.json')) and integer(proof['independent_yosys_boundary_comparisons'])==100 and proof['independent_yosys_log_sha256']==archive.hash(cross+'/eval.log'),'Boundary evidence differs')
        need(proof['oracle']=='Python RV32 integer semantics; Verilator with defined signed overflow; Yosys boundary cross-check','Fallback oracle disclosure differs'); boundary=100
    return worker,comparisons,boundary


def verify_mapping(archive,formula,metric,tools,source,absolute_folder,gate,gate_sha,before):
    folder='circuits/'+digest(formula.encode()); start=archive.json(folder+'/measurement-start.json')
    need(start['formula']==formula and start['verification_gate_sha256']==gate_sha and utc(start['started_at_utc'])>=utc(gate['verified_at_utc']),'Mapping precedes complete RTL gate')
    need(archive.body(folder+'/candidate.v')==original_rtl(formula),'Mapping is not exact original RTL')
    counts=recount(archive.json(folder+'/ice40-netlist.json'))  # derive BEFORE cached metrics/labels
    need(same(metric,archive.json(folder+'/measurement.json')),'Stage/enhanced metric differs')
    raw=archive.json(folder+'/metrics.json'); need(same(raw,archive.json(folder+'/worker.result.json')),'Raw worker metrics differ')
    enhanced_keys={'ice40_ff_count','ice40_bram_count','tool_sha256','abc_invocations','data_invocations'}
    need(same(raw,{k:v for k,v in metric.items() if k not in enhanced_keys}),'Enhanced/raw metric differs')
    for resource,key in [('lut4','ice40_lut4_count'),('carry','ice40_carry_count'),('ff','ice40_ff_count'),('bram','ice40_bram_count')]:
        need(integer(metric[key])==counts[resource],'Independent netlist resource recount differs: '+resource)
    need(type(metric['ice40_cell_types']) is dict and all(type(v) is int and v>0 for v in metric['ice40_cell_types'].values()) and same(metric['ice40_cell_types'],counts['primitive_counts']),'Primitive count table differs')
    yosys=tools['executables']['yosys']
    need(metric['formula']==formula and metric['measurement_source']=='rtl_synthesis' and metric['tool']==yosys['version'] and metric['tool_sha256']==yosys['sha256'],'Synthesis tool/formula identity differs')
    script=f'read_verilog "{absolute_folder}/candidate.v"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{absolute_folder}/ice40-netlist.json"\nstat\n'
    need(archive.text(folder+'/ice40.ys')==script and metric['command']==[yosys['path'],'-s',absolute_folder+'/ice40.ys'],'Mapping recipe/command differs')
    for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]: need(metric[key]==archive.hash(folder+'/'+name),'Mapped raw file hash differs')
    native_log(archive.text(folder+'/ice40.log'),metric,tools,absolute_folder+'/candidate.v')
    payload={'kind':'map','formula':formula,'folder':absolute_folder,'executable':yosys['path'],'version':yosys['version'],'result':absolute_folder+'/worker.result.json'}
    worker=check_worker(archive,folder,'map',payload,tools,source,start['started_at_utc'],before)
    need(utc(worker['started_at_utc'])<=utc(metric['measured_at_utc'])<=utc(worker['completed_at_utc']),'Measurement timestamp outside worker')
    return counts,worker


def installed_records(tools,runtime):
    """Exact recorded runtime identities only; never a blanket host-path exemption."""
    result={}
    def add(path,h):
        p=norm(path); need(p.is_absolute(),'Absolute installed inventory path required'); hash_value(h)
        need(p not in result or result[p]==h,'Conflicting installed identity'); result[p]=h
    for row in tools['executables'].values(): add(row['path'],row['sha256'])
    for key in ('yosys_data','verilator_include'):
        for row in tools[key]['files']: add(norm(tools[key]['path'])/row['path'],row['sha256'])
    sdk=tools['sdk']; add(sdk['settings']['path'],sdk['settings']['sha256'])
    for row in sdk['libcxx_include']['files']: add(norm(sdk['libcxx_include']['path'])/row['path'],row['sha256'])
    for row in runtime['files']: add(row['path'],row['sha256'])
    return result


def public_environment(tools):
    parents=sorted({str(norm(row['path']).parent) for row in tools['executables'].values()})
    return {'PATH':':'.join([*parents,'/usr/bin','/bin']),'ABC':tools['executables']['abc']['path'],
            'LANG':'C','LC_ALL':'C','TZ':'UTC','SDKROOT':tools['sdk']['path']}


def authenticate_bindings(entries,root,producer,installed):
    """Relocate scientific files, retain native inventory without host execution."""
    logical_root=norm(producer/root.relative_to(ROOT).as_posix()); result={}; local={}
    for row in entries:
        need(type(row['path']) is str and not PurePosixPath(row['path']).is_absolute() and '\\' not in row['path'],'Relative binding required')
        path=norm(logical_root/row['path']); h=hash_value(row['sha256']); need(path not in result,'Duplicate resolved binding')
        if 'bytes' in row: integer(row['bytes'])
        result[path]=h
        if path in installed:
            need(installed[path]==h,'Installed identity differs from inventory'); continue
        need(path.is_relative_to(producer),'Unrecorded outside-repository binding')
        actual=ROOT/path.relative_to(producer).as_posix()
        need(actual.is_file() and not actual.is_symlink() and sha(actual)==h,'Saved scientific/source bytes changed: '+str(actual))
        if 'bytes' in row: need(actual.stat().st_size==integer(row['bytes']),'Saved binding size differs')
        local[path]=actual
    return result,local


def verify_pool(candidates,memberships):
    need(type(candidates) is list and bool(candidates),'Nonempty whole original pool required')
    formulas=[canonical(c['formula']) for c in candidates]; ids=[c['candidate_id'] for c in candidates]
    need(formulas==sorted(set(formulas)) and ids==[identifier(f) for f in formulas],'Sorted unique original pool/IDs differ')
    need(type(memberships) is list and len(memberships)==6 and {r['program'] for r in memberships}==set(FAMILIES),'All six original outcomes required')
    seen=set(); programs={i:[] for i in ids}; total=0
    for row in memberships:
        name=row['program']; count=integer(row['canonical_count']); members=row['canonical_ids']
        need(name not in seen and row['family']==FAMILIES[name] and row['status']==('complete' if count else 'empty'),'Program outcome differs')
        need(type(members) is list and len(members)==len(set(members))==count and set(members)<=set(ids),'Whole canonical membership differs')
        need(name!='recursion' or count==0,'Empty recursion must remain empty'); seen.add(name); total+=count
        for i in members: programs[i].append(name)
    need(all(programs.values()) and all(any(r['canonical_count'] for r in memberships if r['family']==f) for f in set(FAMILIES.values())),'Every original/family must remain represented')
    for c in candidates:
        need(type(c['programs']) is list and len(c['programs'])==len(set(c['programs'])) and set(c['programs'])==set(programs[c['candidate_id']]) and c['families']==sorted({FAMILIES[n] for n in c['programs']}),'Candidate cross-program membership differs')
    return total


def verify_points(result,candidates):
    need(result['schema']=='isaforge-v11-frozen-point-predictions-v1' and integer(result['candidate_count'])==len(candidates) and set(result['models'])=={'V6','V9'},'Exact two frozen point sets required')
    predictions={}
    for name,rows in result['models'].items():
        need(type(rows) is list and len(rows)==len(candidates),'All originals need both frozen points')
        for row,c in zip(rows,candidates):
            need(row['candidate_id']==c['candidate_id'] and row['formula']==c['formula'],'Frozen point order/original differs')
            finite(row['predicted_lut4']); need(row['upper_lut4'] is None and row['calibration_status']=='uncalibrated','Raw uncalibrated points required')
        predictions[name]=[{'id':r['candidate_id'],'prediction':r['predicted_lut4']} for r in rows]
    return predictions


def verify_features(data,completion,candidates,columns):
    n=len(candidates)
    need(completion['schema']=='isaforge-v11-transfer-feature-completion-v1' and completion['complete'] is True
         and completion['failures']==completion['cleanup_failures']==[],'Complete original feature stage required')
    need(integer(completion['candidate_count'])==integer(completion['completed_extractions'])==n,'AllN feature jobs required')
    for key in ('new_predictions','new_labels','new_fits'): need(integer(completion[key])==0,'Feature stage scope differs')
    need(data['columns']==columns and len(columns)==336 and type(data['records']) is list and len(data['records'])==n,'FullN by336 feature matrix required')
    for row,c in zip(data['records'],candidates):
        need(row['candidate_id']==c['candidate_id'] and row['formula']==c['formula'] and type(row['values']) is list and len(row['values'])==336,'Feature original order/width differs')
        for value in row['values']: finite(value)


def input_lineage(input_root,prep,candidates,memberships,bound):
    """Rejoin the entire admitted C pool, without rerunning its shared parsers."""
    source=(input_root/prep['source_root']).resolve(); need(source.is_relative_to(ROOT),'Repository recovery root required')
    audit_path=bound((input_root/prep['reviewed_audit']['path']).resolve())
    need(sha(audit_path)==prep['reviewed_audit']['sha256'],'Reviewed recovery audit identity changed')
    review=read(audit_path); done=read(bound(source/'completion.json')); stage=source/'run/attempt-0000'
    need(review['schema']=='isaforge-v11c-independent-recovery-audit-v1' and review['status']=='pass' and review['complete'] is True,'Complete reviewed C raw audit required')
    need(review['source_sha256']==sha(bound(ROOT/'scripts/audit_v11c_recovery.py')) and review['independence']==prep['audit_independence'],'Recovery audit source/scope differs')
    need(done['schema']=='isaforge-v11c-recovery-completion-v1' and done['complete'] is True and done['failures']==[] and same(done,read(bound(stage/'completion.json'))),'Complete admitted recovery required')
    for k,v in [('program_count',6),('reused_program_count',4),('recovered_program_count',2),('labels_predictions_features_fits',0)]: need(integer(review[k])==v,'Recovery audit count/scope differs')
    for key,path in [('preparation_sha256',source/'preparation.json'),('completion_sha256',source/'completion.json'),('evidence_manifest_sha256',stage/'evidence-manifest.json')]: need(review[key]==sha(bound(path)),'Recovery audit input identity differs')
    need(utc(review['audited_at_utc'])>=utc(done['completed_at_utc']),'Recovery audit precedes completion')
    records=read(bound(stage/'programs.json')); completed=read(bound(stage/'completed-rows.json'))
    need(set(records)==set(review['programs'])==set(FAMILIES),'Recovery omits/extends reserved programs')
    by_formula={}; expected_members=[]; expected_completed=[]
    for name,family in FAMILIES.items():
        row=records[name]; observed=review['programs'][name]; entry=row['candidate_file']
        path=bound((source/entry['path']).resolve()); rows=read(path); n=integer(row['candidate_count'])
        need(sha(path)==entry['sha256'] and type(rows) is list and len(rows)==n and len({r['formula'] for r in rows})==n,'Recovery original candidates differ')
        need(row['family']==family and row['status']==('complete' if n else 'empty') and observed['status']==row['status'] and integer(observed['candidate_count'])==n,'Recovery admitted outcome differs')
        copy_path=bound(input_root/'original-candidate-files'/(name+'.json')); need(copy_path.read_bytes()==path.read_bytes(),'Staged originals are not byte-identical to admitted C pool')
        ids=[]
        for r in rows:
            formula=canonical(r['formula']); by_formula.setdefault(formula,[]).append(name); ids.append(identifier(formula)); expected_completed.append({**r,'benchmark':name,'family':family})
        expected_members.append({'program':name,'family':family,'status':row['status'],'canonical_count':n,'canonical_ids':sorted(ids)})
    expected_candidates=[{'candidate_id':identifier(f),'formula':f,'programs':programs,'families':sorted({FAMILIES[n] for n in programs})} for f,programs in sorted(by_formula.items())]
    need(same(completed,expected_completed) and same(candidates,expected_candidates) and same(memberships,expected_members),'Staged pool omits/changes admitted recovery originals')
    need(integer(review['program_formula_rows'])==integer(done['completed_program_formula_rows'])==len(completed) and integer(review['unique_canonical_formulas'])==len(candidates),'Admitted full-pool denominator differs')
    for key,path in [('programs_sha256',stage/'programs.json'),('completed_rows_sha256',stage/'completed-rows.json')]: need(done[key]==sha(path),'Recovery compact pool hash differs')
    return {'reviewed_recovery_audit_sha256':sha(audit_path),'recovery_completion_sha256':sha(source/'completion.json'),'scope':review['independence']}


def provenance(root,archive,producer):
    """Authenticate saved full-pool seals without model loading or production APIs."""
    plan=read(root/'measurement-plan.json'); tools=read(root/'measurement-tools.json')
    need(plan['schema']=='isaforge-v11-transfer-target-plan-v1' and plan['status']=='prepared-no-target-jobs' and same(plan['policy'],POLICY),'Exact target recipe required')
    need(tools['schema']=='isaforge-v13b-coverage-tools-v1' and same(tools,read(root/'tools.json')),'Same pinned feature/target tools required')
    runtime=read(root/'runtime.json'); installed=installed_records(tools,runtime)
    need(same(tools['environment'],public_environment(tools)),'Exact public native environment differs')
    bindings,local=authenticate_bindings(plan['files'],root,producer,installed)
    need(all(bindings.get(path)==h for path,h in installed.items()),'Target plan omits installed runtime/tool dependency')
    logical_root=norm(producer/root.relative_to(ROOT).as_posix())
    def bound(path):
        path=Path(path); key=norm(producer/path.relative_to(ROOT).as_posix())
        need(key in local and local[key]==path and bindings[key]==sha(path),'Missing target-plan scientific binding: '+str(path))
        return path
    base=read(bound(ROOT/BASE_TOOLS))
    need(tools['inherited_inventory']=={'path':BASE_TOOLS,'sha256':BASE_TOOLS_SHA} and sha(ROOT/BASE_TOOLS)==BASE_TOOLS_SHA,'Frozen native inventory anchor differs')
    need(tools['yosys_data']==base['yosys_data'] and all(tools['executables'][k]==v for k,v in base['executables'].items()),'Frozen Yosys/ABC/data identities differ')
    freeze=read(bound(root/'point-freeze.json')); feature_plan=read(bound(root/'feature-plan.json'))
    need(freeze['schema']=='isaforge-v11-transfer-point-freeze-v1' and freeze['complete'] is True,'Complete point seal required')
    point_bindings,_=authenticate_bindings(freeze['files'],root,producer,installed)
    need(all(bindings.get(p)==h for p,h in point_bindings.items()),'Target plan omits frozen point dependencies')
    need(all(point_bindings.get(path)==h for path,h in installed.items()),'Point freeze omits installed runtime/tool dependency')
    input_root=(root/feature_plan['input_root']).resolve(); need(input_root.is_relative_to(ROOT),'Repository input stage required')
    prep=read(bound(input_root/'preparation.json')); candidates=read(bound(input_root/'candidates.json')); memberships=read(bound(input_root/'memberships.json'))
    total=verify_pool(candidates,memberships); n=len(candidates)
    need(prep['schema']=='isaforge-v11-model-comparison-inputs-v1' and prep['status']=='prepared-inputs-only' and integer(prep['unique_canonical_originals'])==n and integer(prep['program_formula_memberships'])==total,'Full input-stage denominator differs')
    need(integer(prep['pre_reservation_reference_count'])==2929 if 'pre_reservation_reference_count' in prep else True,'Novelty reference count differs')
    lineage=input_lineage(input_root,prep,candidates,memberships,bound)
    for row in memberships:
        original=read(bound(input_root/'original-candidate-files'/(row['program']+'.json')))
        need(type(original) is list and len(original)==row['canonical_count'] and {identifier(canonical(c['formula'])) for c in original}==set(row['canonical_ids']),'Original byte-copy memberships differ')
    result=read(bound(root/'predictions/attempt-0000/result.json')); predictions=verify_points(result,candidates)
    runner_sha=hash_value(result['runner_sha256']); need(runner_sha in PREDICTOR_SOURCES,'Unrecognized frozen predictor runner')
    runner=bound(ROOT/PREDICTOR_SOURCES[runner_sha]); need(sha(runner)==runner_sha,'Frozen predictor runner bytes differ')
    if runner.name=='predict_v11d_transfer.py':
        bound(ROOT/'tests/test_predict_v11d_transfer.py')
        need(archive.hash('sources/scripts/predict_v11d_transfer.py')==runner_sha,'Missing archived V11d recovery runner')
    done=read(bound(root/'predictions/completion.json')); need(same(done,read(bound(root/'predictions/attempt-0000/completion.json'))),'Prediction root/stage completion differs')
    need(done['schema']=='isaforge-v11-frozen-point-completion-v1' and done['complete'] is True and done['failures']==[],'Complete saved inference required')
    for k,v in [('candidate_count',n),('prediction_count',2*n),('new_labels',0),('new_fits',0),('calibration_jobs',0)]: need(integer(done[k])==v,'Saved inference count/scope differs')
    features=read(bound(root/'features/completion.json')); need(same(features,read(bound(root/'features/attempt-0000/completion.json'))),'Feature stage/root completion differs')
    feature_data=read(bound(root/'features/attempt-0000/features.json'))
    verify_features(feature_data,features,candidates,feature_plan['columns'])
    for key,path in [('features_sha256',root/'features/attempt-0000/features.json'),('raw_archive_sha256',root/'features/attempt-0000/raw-evidence.zip'),('raw_manifest_sha256',root/'features/attempt-0000/raw-evidence.json')]:
        need(features[key]==sha(bound(path)),'Feature archive/data seal differs')
    replay=read(bound(root/'features/attempt-0000/replay/result.json'))
    need(replay['complete'] is True and integer(replay['records'])==n and replay['features_sha256']==features['features_sha256'],'Full raw-feature replay receipt required')
    for key,path in [('feature_plan_sha256',root/'feature-plan.json'),('input_preparation_sha256',input_root/'preparation.json'),('feature_completion_sha256',root/'features/completion.json'),('prediction_completion_sha256',root/'predictions/completion.json'),('point_predictions_sha256',root/'predictions/attempt-0000/result.json')]:
        need(freeze[key]==sha(bound(path)),'Point-freeze digest differs')
    need(freeze['columns']==feature_plan['columns'] and len(freeze['columns'])==336 and freeze['selected_columns']==feature_plan['selected_columns'] and len(freeze['selected_columns'])==217 and freeze['selected_indices']==feature_plan['selected_indices'],'Frozen336/217 schema differs')
    need(freeze['frozen_tool']==feature_plan['frozen_tool']=={'version':tools['executables']['yosys']['version'],'executable_sha256':tools['executables']['yosys']['sha256']},'Frozen feature Yosys identity differs')
    indices=freeze['selected_indices']; need(len(indices)==217 and len(set(indices))==217 and all(type(i) is int and 0<=i<336 for i in indices) and [freeze['columns'][i] for i in indices]==freeze['selected_columns'],'Feature selection differs')
    for k in ('fits','calibration_jobs','labels_read'): need(integer(freeze[k])==0,'Point freeze scope differs')
    need(integer(freeze['candidate_count'])==n and integer(freeze['prediction_count'])==2*n and utc(freeze['frozen_at_utc'])>=utc(done['completed_at_utc']),'Frozen point chronology/count differs')
    models=read(bound(input_root/'predictors.json')); need(set(models)=={'V6','V9'},'Exact predictor artifacts required')
    for name,(relative,h,count) in MODELS.items():
        entry=models[name]; need(norm(entry['artifact']['path'])==PurePosixPath(relative) and entry['artifact']['sha256']==h,'Frozen model artifact differs')
        artifact=bound(ROOT/relative); need(sha(artifact)==h,'Frozen artifact bytes changed')
        metadata_path=ROOT/entry['metadata']['path']; metadata=read(bound(metadata_path))
        need(sha(metadata_path)==entry['metadata']['sha256']==MODEL_METADATA_SHA[name] and metadata['artifact_sha256']==h and integer(metadata['training_formula_count'])==count and metadata['kind']=='mapping_v6' and metadata['calibration']['status']=='uncalibrated','Frozen predictor metadata differs')
        need(metadata['feature_columns']==freeze['columns'] and metadata['mapping_columns']==freeze['selected_columns'] and metadata['frozen_tool']==freeze['frozen_tool'],'Frozen predictor feature tool/schema differs')
    for key,path in [('feature_plan_sha256',root/'feature-plan.json'),('features_sha256',root/'features/attempt-0000/features.json'),('input_preparation_sha256',input_root/'preparation.json'),('predictor_manifest_sha256',input_root/'predictors.json'),('membership_sha256',input_root/'memberships.json'),('runner_sha256',runner)]: need(result[key]==sha(bound(path)),'Point source/input seal differs')
    review=read(bound(root/'prediction-approval.json')); claim=read(bound(root/'prediction-claim.json')); worker=read(bound(root/'predictions/attempt-0000/worker.json'))
    need(review['status']=='approved-v11-full-pool-frozen-predictions' and worker['schema']=='isaforge-v11-prediction-worker-v1' and worker['action']=='inference-worker' and worker['complete'] is True and type(worker['returncode']) is int and worker['returncode']==0 and worker['primary_error'] is None and worker['cleanup_errors']==worker['remaining_owned_children']==[],'Successful saved inference release/worker required')
    need(utc(features['completed_at_utc'])<=utc(review['reviewed_at_utc'])<=utc(claim['claimed_at_utc'])<=utc(worker['started_at_utc'])<=utc(worker['completed_at_utc'])<=utc(done['completed_at_utc']),'Inference release chronology differs')
    for key,path in [('worker_receipt_sha256',root/'predictions/attempt-0000/worker.json'),('worker_log_sha256',root/'predictions/attempt-0000/worker.log'),('approval_sha256',root/'prediction-approval.json'),('claim_sha256',root/'prediction-claim.json')]: need(done[key]==sha(bound(path)),'Inference execution provenance differs')
    need(worker['log_sha256']==sha(root/'predictions/attempt-0000/worker.log') and worker['runner_sha256']==runner_sha,'Inference worker source/log differs')
    expected_budget={'candidate_count':n,'verification_batches':(n+127)//128,'expected_rtl_comparisons':2148*n,'maximum_mapping_attempts':n,'maximum_attempt_seconds':360*((n+127)//128+(n+1)//2)+600+10*(n+(n+127)//128)}
    need(same(plan['budget'],expected_budget) and integer(plan['program_formula_memberships'])==total,'Complete target budget differs')
    need(plan['point_freeze_sha256']==sha(root/'point-freeze.json') and plan['prediction_completion_sha256']==sha(root/'predictions/completion.json') and plan['prediction_frozen_at_utc']==freeze['frozen_at_utc'] and utc(plan['created_at_utc'])>=utc(freeze['frozen_at_utc']),'Target plan predates/changes frozen predictions')
    need(plan['tools']=={'path':'measurement-tools.json','sha256':sha(root/'measurement-tools.json')},'Target tools seal differs')
    approval=read(root/'measurement-approval.json'); release=read(root/'label-release.json')
    expected={'candidate_count':n,'point_freeze_sha256':sha(root/'point-freeze.json'),'prediction_completion_sha256':sha(root/'predictions/completion.json'),'measurement_plan_sha256':sha(root/'measurement-plan.json'),'tools_sha256':sha(root/'measurement-tools.json'),'collector_sha256':sha(ROOT/'scripts/measure_v11_transfer.py')}
    need(approval['status']=='approved-v11-full-pool-original-targets' and release['schema']=='isaforge-v11-target-release-v1' and all(same(approval[k],v) and same(release[k],v) for k,v in expected.items()),'Exact separately approved target release differs')
    need(integer(approval['maximum_new_labels'])==n and integer(approval['expected_rtl_comparisons'])==2148*n and approval['collector_tests_sha256']==sha(ROOT/'tests/test_measure_v11_transfer.py'),'Target approval budget/source differs')
    need(re.fullmatch('[0-9a-f]{40}',approval['freeze_commit']) and release['freeze_commit']==approval['freeze_commit'] and release['approval_sha256']==sha(root/'measurement-approval.json') and same(release['policy'],POLICY),'Target Git-release receipt differs')
    need(utc(plan['created_at_utc'])<=utc(approval['reviewed_at_utc'])<=utc(release['released_at_utc']),'Target approval/release chronology differs')
    for name in ('measurement-plan.json','measurement-tools.json','measurement-approval.json','label-release.json','point-freeze.json'): need(archive.body(name)==(root/name).read_bytes(),'Archived control seal differs')
    for name in MANDATORY_SOURCES:
        bound(ROOT/name); need('sources/'+name in archive.entries,'Missing archived required source')
    source_names=[p for p in archive.entries if p.startswith('sources/')]
    for name in source_names:
        relative=PurePosixPath(name).relative_to('sources'); path=bound(ROOT/str(relative)); need(archive.hash(name)==sha(path),'Archived/live source differs')
    need(archive.hash('sources/scripts/audit_v11_targets.py')==sha(__file__),'Auditor source differs from prelabel frozen pipeline')
    return candidates,memberships,predictions,plan,tools,approval,release,freeze,{'scientific_files':len(local),'recorded_installed_files':len(installed),'archived_sources':len(source_names),'input_root':str(input_root.relative_to(ROOT)),'predictor_runner':PREDICTOR_SOURCES[runner_sha],'predictor_runner_sha256':runner_sha,'recovery_lineage':lineage}


def run(root):
    """Return admitted raw audit/resources/scoring inputs. Does not compute errors."""
    root=Path(root).resolve(); need(root.is_relative_to(ROOT),'Repository result root required')
    stage=root/'measurements'/ATTEMPT; done=read(root/'measurements/completion.json')
    need(done['schema']=='isaforge-v11-transfer-target-completion-v1' and done['complete'] is True and done['failures']==[] and done['primary_available'] is True and same(done,read(stage/'completion.json')),'Incomplete targets: no admitted labels/scoring inputs')
    archive=Archive(stage)
    try:
        metrics=read(stage/'unique-measurements.json'); need(type(metrics) is list and bool(metrics),'Complete raw metric list required')
        first=metrics[0]; suffix='/'+PREFIX+'/'+ATTEMPT+'/circuits/'+digest(first['formula'].encode())+'/ice40.ys'
        command=first['command']; need(type(command) is list and len(command)==3 and command[1]=='-s' and command[2].endswith(suffix),'Producer scratch command identity differs')
        producer=norm(command[2][:-len(suffix)]); need(producer.is_absolute(),'Absolute producer root required')
        candidates,memberships,predictions,plan,tools,approval,release,freeze,closure=provenance(root,archive,producer)
        n=len(candidates); formulas=[c['formula'] for c in candidates]
        need([m['formula'] for m in metrics]==formulas,'ExactlyN ordered original mapped results required')
        expected={'attempt':ATTEMPT,'candidate_count':n,'new_physical_measurements':n,'mapping_attempts':n,'verified_comparisons':2148*n,'verification_batch_sizes':[len(formulas[i:i+128]) for i in range(0,n,128)],'verification_seed':SEED,'vectors_per_original':2148,'mapping_workers':2,'original_rtl_only':True,'historical_labels_reused':False,'new_fits':0}
        need(all(same(done[k],v) for k,v in expected.items()),'Target completion full-pool counts differ')
        for key,path in [('point_freeze_sha256',root/'point-freeze.json'),('prediction_completion_sha256',root/'predictions/completion.json'),('release_sha256',root/'label-release.json'),('measurement_plan_sha256',root/'measurement-plan.json'),('tools_sha256',root/'measurement-tools.json'),('approval_sha256',root/'measurement-approval.json'),('collector_sha256',ROOT/'scripts/measure_v11_transfer.py')]: need(done[key]==sha(path),'Completion provenance differs')
        need(done['freeze_commit']==approval['freeze_commit'] and utc(done['completed_at_utc'])>=utc(release['released_at_utc']),'Completion release chronology differs')
        for name,key in [('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256'),('labels.json','labels_sha256')]: need(sha(stage/name)==done[key],'Stage output digest differs')
        source=worker_source(archive.body('sources/scripts/measure_v6.py'))
        gate=archive.json('verification-gate.json'); proofs=read(stage/'verification.json')
        need(len(proofs)==(n+127)//128 and integer(gate['formula_count'])==n and integer(gate['comparison_count'])==2148*n and gate['verification_sha256']==digest(json.dumps(proofs,sort_keys=True).encode()),'Complete verification gate differs')
        need(utc(release['released_at_utc'])<=utc(gate['verified_at_utc'])<=utc(done['completed_at_utc']),'Verification gate chronology differs')
        scratch=producer/PREFIX/ATTEMPT; comparisons=0; boundary=0; last=release['released_at_utc']; fallback=[]
        expected_batches=set()
        for index,offset in enumerate(range(0,n,128)):
            folder=f'verification/batch-{offset:04d}'; expected_batches.add(folder.split('/')[1])
            worker,count,cross=verify_batch(archive,folder,formulas[offset:offset+128],proofs[index],tools,source,str(scratch/folder),last,gate['verified_at_utc'],archive.hash('sources/isaforge/v4_validation.py'))
            comparisons+=count; boundary+=cross; last=worker['completed_at_utc']
            if cross: fallback.append({'batch_offset':offset,'incident':proofs[index]['incident'],'boundary_comparisons':cross})
        need({PurePosixPath(p).parts[1] for p in archive.entries if p.startswith('verification/')}==expected_batches,'Foreign/missing verification batch')
        expected_circuits={digest(f.encode()) for f in formulas}
        need({PurePosixPath(p).parts[1] for p in archive.entries if p.startswith('circuits/')}==expected_circuits,'Foreign/missing original mapping')
        resources=[]; intervals=[]; labels=[]
        for c,metric in zip(candidates,metrics):
            f=c['formula']; folder='circuits/'+digest(f.encode())
            counts,worker=verify_mapping(archive,f,metric,tools,source,str(scratch/folder),gate,archive.hash('verification-gate.json'),done['completed_at_utc'])
            intervals.append((worker['started_at_utc'],worker['completed_at_utc']))
            resources.append({'id':c['candidate_id'],'formula':f,**counts,'rtl_sha256':metric['rtl_sha256'],'netlist_sha256':metric['netlist_sha256']})
            labels.append({'id':c['candidate_id'],'lut4':counts['lut4']})
        peak=check_parallel(intervals)
        generated=read(stage/'labels.json'); need(len(generated)==n,'Generated labels omit originals')
        for c,resource,row in zip(candidates,resources,generated):
            expected={**c,'lut4_count':resource['lut4'],'carry_count':resource['carry'],'ff_count':resource['ff'],'bram_count':resource['bram'],'rtl_sha256':resource['rtl_sha256'],'correctness_verified':True,'measurement_source':'rtl_synthesis'}
            need(same(row,expected),'Generated labels disagree with independent mapped recount')
        need(comparisons==2148*n,'Full RTL comparison total differs')
        report={'schema':'isaforge-v11-independent-target-audit-v1','status':'pass','complete':True,'audited_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_sha256':sha(__file__),'source_tests_sha256':sha(ROOT/'tests/test_audit_v11_targets.py'),'oracle_sha256':ORACLE_SHA,
            'measurement_plan_sha256':sha(root/'measurement-plan.json'),'point_freeze_sha256':sha(root/'point-freeze.json'),'completion_sha256':sha(root/'measurements/completion.json'),
            'raw_archive_sha256':sha(stage/'raw-evidence.zip'),'raw_manifest_sha256':sha(stage/'raw-evidence.json'),'program_count':6,'family_count':5,
            'program_formula_memberships':sum(r['canonical_count'] for r in memberships),'original_count':n,'prediction_count':2*n,'rtl_comparisons':comparisons,
            'mapped_netlists_recounted':n,'maximum_overlapping_mapping_workers':peak,'fallback_incidents':fallback,'fallback_boundary_comparisons':boundary,
            'closure':closure,'native_jobs':0,'model_artifacts_loaded':0,'fits':0,
            'scope':['Independent primitive recount precedes generated-label comparison; all global originals and full memberships retained.',
                'Pinned V9 unsigned oracle shared; full-grammar RTL/harness renderer, vector regeneration and provenance checks independently implemented.',
                'Saved point/feature/model bytes authenticated; no inference or feature extraction is replayed here. Prior input audit shares frozen parser/extractor as disclosed in its seal.',
                'Recorded native execution lineage and sampled original RTL comparisons, not universal or mapped-netlist functional proof.',
                'Exact native tool/runtime identities checked against sealed inventory without requiring producer installations on replay host; producer Git validation is authenticated by saved approval/source closure, not rerun.',
                'Final retained file sizes/receipts checked; historical live resource peaks cannot be independently reconstructed. Local trace/cache/model dependencies must be present; Git alone is not self-contained.']}
        payload={'outcomes':[{k:r[k] for k in ('program','family','status','canonical_count')} for r in memberships],
            'membership':[{'program':r['program'],'canonical_ids':r['canonical_ids']} for r in memberships],
            'labels':labels,'predictions':predictions,'metadata':{'endpoint':'V11b-E1','independent_target_audit_source_sha256':sha(__file__),
                'point_freeze_sha256':report['point_freeze_sha256'],'original_endpoint_available':False,'scope':'Complete full-pool measured isolated LUT4 targets; no CPU, power, timing or refitting claim.'}}
        return report,resources,payload
    finally: archive.close()


def publish(root,output):
    """Fresh destination; failure never emits labels or scoring inputs."""
    output=Path(output); need(not output.exists(),'Fresh independent audit destination required'); output.mkdir(parents=True)
    try:
        report,resources,payload=run(root)
    except Exception as error:
        (output/'audit-failure.json').write_text(json.dumps({'schema':'isaforge-v11-independent-target-audit-v1','status':'fail','complete':False,'error':repr(error),'source_sha256':sha(__file__)},indent=2)+'\n')
        raise
    for name,value in [('audit.json',report),('resources.json',resources),('labels.json',payload['labels']),('scoring-inputs.json',payload)]:
        with (output/name).open('x') as stream: json.dump(value,stream,indent=2,allow_nan=False); stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); print(json.dumps(publish(args.root,args.output),indent=2,allow_nan=False))
