"""Synthetic saved evidence only: no target collection, model loading or scoring."""
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
import audit_v11e_targets as audit

T0='2026-10-16T00:00:00+00:00'
T1='2026-10-16T00:00:01+00:00'
T2='2026-10-16T00:00:02+00:00'
T3='2026-10-16T00:00:03+00:00'
T4='2026-10-16T00:00:04+00:00'
T5='2026-10-16T00:00:05+00:00'

def encode(v): return (json.dumps(v,indent=2,allow_nan=False)+'\n').encode()
def h(v): return hashlib.sha256(v).hexdigest()

@pytest.fixture(autouse=True)
def no_native(monkeypatch):
    import subprocess
    def forbidden(*args,**kwargs): raise AssertionError('No native/ML calls in raw auditor tests')
    monkeypatch.setattr(subprocess,'Popen',forbidden)

class MemoryArchive:
    def __init__(self): self.entries={}; self.files={}
    def put(self,name,body):
        self.files[name]=body; self.entries[name]={'path':name,'sha256':h(body),'bytes':len(body)}
    def putjson(self,name,value): self.put(name,encode(value))
    def body(self,name): audit.need(name in self.files,'Missing archived evidence: '+name); return self.files[name]
    def json(self,name): return audit.loads(self.body(name))
    def text(self,name): return self.body(name).decode()
    def hash(self,name): return self.entries[name]['sha256']


def tools():
    return {'executables':{'python':{'path':'/native/python','sha256':'1'*64},'yosys':{'path':'/native/bin/yosys','sha256':'2'*64,'version':'Yosys 0.63+42 (git sha1 abcdef)'},
        'abc':{'path':'/native/bin/yosys-abc','sha256':'3'*64},'verilator':{'path':'/native/bin/verilator','sha256':'4'*64},'cxx':{'path':'/usr/bin/c++','sha256':'5'*64}},
        'resolved_commands':{'verilator':{'path':'/native/bin/verilator','sha256':'4'*64},'c++':{'path':'/Library/Developer/CommandLineTools/usr/bin/clang','sha256':'6'*64}},
        'environment':{'PATH':'/Library/Developer/CommandLineTools/usr/bin:/native/bin:/usr/bin','SDKROOT':'/sdk'},
        'yosys_data':{'path':'/native/share/yosys','files':[{'path':'ice40/cells_sim.v','sha256':'7'*64}]},
        'verilator_include':{'path':'/native/share/verilator/include','files':[]},
        'sdk':{'path':'/sdk','settings':{'path':'/sdk/SDKSettings.json','sha256':'8'*64},'libcxx_include':{'path':'/sdk/include','files':[]}}}

SOURCE="import json\np=json.loads('null')\n"  # synthetic literal worker, not executed
ABS='/producer/repo/generated/v11e-transfer-targets/attempt-0000'


def worker(a,folder,kind,payload,start=T1,end=T2):
    a.put(folder+'/worker.log',b'')
    row={'schema':'isaforge-v11-target-worker-v1','kind':kind,'complete':True,'returncode':0,'primary_error':None,'cleanup_errors':[],
        'remaining_owned_children':[],'timeout_seconds':360,'elapsed_seconds':1.1,'started_at_utc':start,'completed_at_utc':end,
        'python_invocation':{'invoked':'/producer/repo/.venv/bin/python','resolved':'/native/python','sha256':'1'*64},
        'command':['/producer/repo/.venv/bin/python','-c',SOURCE,json.dumps(payload)],'log_sha256':h(b'')}
    a.putjson(folder+'/worker.json',row); return row


def batch(formulas=('ori(in0,0)',),fallback=False):
    a=MemoryArchive(); folder='verification/batch-0000'; absolute=ABS+'/'+folder
    a.put(folder+'/verification.v',audit.verification_rtl(formulas)); a.put(folder+'/verification.cpp',audit.verification_cpp(len(formulas)))
    trees=[audit.oracle.parse(f) for f in formulas]
    matrix=''.join(' '.join(f'{v:08x}' for v in (x,y,*[audit.oracle.evaluate(t,x,y) for t in trees]))+'\n' for x,y in audit.pairs()).encode()
    a.put(folder+'/vectors.txt',matrix); a.put(folder+'/verilator-build.log',b'build success')
    a.put(folder+'/verification.log',b'2148 vectors passed\n')
    proof={'verified':True,'formula_count':len(formulas),'vectors_per_formula':2148,'total_comparisons':2148*len(formulas),'random_seed':audit.SEED,
        'v4_validation_override_sha256':'a'*64,'rtl_sha256':a.hash(folder+'/verification.v'),'vectors_sha256':a.hash(folder+'/vectors.txt'),
        'tool':'Verilator 5.050','oracle':'Python integer RV32 semantics','signed_overflow_workaround_applied':False}
    if fallback:
        incident={'formula_index':0,'formula':formulas[0],'vector_index':1,'got_hex':'1','expected_hex':'0',
            'resolution':'identical RTL rebuilt with defined signed wrapping; boundary cross-check in Yosys',
            'original_error':'RTL correctness failed: Mismatch formula 0 vector 1 got 1 expected 0\n'}
        proof.update({'signed_overflow_workaround_applied':True,'incident':incident,'compiler_path':'/Library/Developer/CommandLineTools/usr/bin/c++','compiler_version':'Apple clang version 17',
            'build_command':['/native/bin/verilator','--cc','--exe','--build','-j','2','-Wno-fatal','-CFLAGS','-fwrapv','--top-module','verification_top','--Mdir',absolute+'/obj_dir_wrapv',absolute+'/verification.v',absolute+'/verification.cpp'],
            'independent_yosys_boundary_comparisons':100,'oracle':'Python RV32 integer semantics; Verilator with defined signed overflow; Yosys boundary cross-check'})
        a.putjson(folder+'/initial-failure.json',incident); a.put(folder+'/initial-failure.log',incident['original_error'][len('RTL correctness failed: '):].encode())
        a.put(folder+'/verification.log',a.body(folder+'/initial-failure.log')); a.put(folder+'/verification-wrapv.log',b'2148 vectors passed\n'); a.put(folder+'/verilator-wrapv-build.log',b'build success')
        cross=folder+'/yosys-boundary-cross-check'; cp=absolute+'/yosys-boundary-cross-check'
        ps=list(itertools.product(audit.oracle.BOUNDARIES,repeat=2)); values=[audit.oracle.evaluate(trees[0],x,y) for x,y in ps]
        a.put(cross+'/candidate.v',audit.original_rtl(formulas[0])); a.put(cross+'/eval.ys',('\n'.join([f'read_verilog "{cp}/candidate.v"','prep -top candidate',*[f'eval -set in0 {x} -set in1 {y} -show result' for x,y in ps]])+'\n').encode())
        a.put(cross+'/eval.log',(tools()['executables']['yosys']['version']+'\n'+''.join(f"Eval result: \\result = 32'{v:032b}.\n" for v in values)).encode())
        a.putjson(cross+'/observations.json',[{'in0':x,'in1':y,'result':v} for (x,y),v in zip(ps,values)])
        proof['independent_yosys_log_sha256']=a.hash(cross+'/eval.log'); a.putjson(folder+'/validation-resolution.json',proof)
    a.putjson(folder+'/worker.result.json',proof)
    payload={'kind':'verify','formulas':list(formulas),'folder':absolute,'seed':audit.SEED,'result':absolute+'/worker.result.json'}
    worker(a,folder,'verify',payload)
    return a,folder,list(formulas),proof


def check_batch(v):
    a,folder,formulas,proof=v
    return audit.verify_batch(a,folder,formulas,proof,tools(),SOURCE,ABS+'/'+folder,T0,T3,'a'*64)


def netlist(types=()):
    return {'modules':{'candidate':{'ports':{n:{'direction':d,'bits':list(range(i*32+2,i*32+34))} for i,(n,d) in enumerate([('in0','input'),('in1','input'),('result','output')])},
        'cells':{str(i):{'type':t} for i,t in enumerate(types)}}}}


def mapping(formula='ori(in0,0)',types=()):
    a=MemoryArchive(); folder='circuits/'+h(formula.encode()); absolute=ABS+'/'+folder; t=tools(); y=t['executables']['yosys']
    gate={'verified_at_utc':T3}; gate_sha='b'*64
    a.putjson(folder+'/measurement-start.json',{'formula':formula,'started_at_utc':T3,'verification_gate_sha256':gate_sha})
    a.put(folder+'/candidate.v',audit.original_rtl(formula)); a.putjson(folder+'/ice40-netlist.json',netlist(types))
    script=f'read_verilog "{absolute}/candidate.v"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "{absolute}/ice40-netlist.json"\nstat\n'
    a.put(folder+'/ice40.ys',script.encode()); log=y['version']+f"\nParsing Verilog input from `{absolute}/candidate.v'\nParsing Verilog input from `/native/share/yosys/ice40/cells_sim.v'\n"
    if types: log+='Running ABC command: /native/bin/yosys-abc -s -f test\n'
    a.put(folder+'/ice40.log',log.encode()); counts=audit.recount(netlist(types))
    raw={'formula':formula,'tool':y['version'],'measurement_source':'rtl_synthesis','ice40_lut4_count':counts['lut4'],'ice40_carry_count':counts['carry'],
        'ice40_cell_types':counts['primitive_counts'],'command':[y['path'],'-s',absolute+'/ice40.ys'],'generic_measurement':'omitted; irrelevant to LUT4 label','measured_at_utc':T4,
        **{key:a.hash(folder+'/'+name) for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]}}
    metric={**raw,'ice40_ff_count':counts['ff'],'ice40_bram_count':counts['bram'],'tool_sha256':y['sha256'],
        'abc_invocations':[{'path':t['executables']['abc']['path'],'sha256':t['executables']['abc']['sha256']}] if types else [],
        'data_invocations':{'ice40/cells_sim.v':{'sha256':'7'*64,'resolved_path':'/native/share/yosys/ice40/cells_sim.v','logged_paths':['/native/share/yosys/ice40/cells_sim.v']}}}
    for name,value in [('metrics.json',raw),('worker.result.json',raw),('measurement.json',metric)]: a.putjson(folder+'/'+name,value)
    payload={'kind':'map','formula':formula,'folder':absolute,'executable':y['path'],'version':y['version'],'result':absolute+'/worker.result.json'}
    worker(a,folder,'map',payload,T3,T5)
    return a,formula,metric,gate,gate_sha


def check_mapping(v):
    a,f,m,g,gs=v
    return audit.verify_mapping(a,f,m,tools(),SOURCE,ABS+'/circuits/'+h(f.encode()),g,gs,T5)


@pytest.mark.parametrize('formula',[
    *[f'{op}(in0,in1)' for op in ('add','sub','and','or','xor','sll','srl','sra','slt','sltu','mul','mulh','mulhsu','mulhu')],
    *[f'{op}(in0,-1)' for op in ('addi','andi','ori','xori','slli','srli','srai','slti','sltiu')],
    'lui(-2147483648)','add(mulhu(in0,in1),mulhu(in0,in1))','srai(sll(in0,in1),31)'])
def test_full_grammar_independent_renderer_matches_frozen_bytes(formula):
    from isaforge.rtl import generate_rtl
    assert audit.original_rtl(formula)==generate_rtl(formula).encode()


def test_original_batch_and_all_outputs():
    v=batch(('ori(in0,0)','mulhu(in0,in1)','sra(in0,in1)'))
    assert check_batch(v)[1:]==(6444,0)

@pytest.mark.parametrize('poison',['expected','input','extra','missing','harness','rtl','cleanup','seed','boolcount'])
def test_reauthenticated_batch_corruption(poison):
    a,folder,fs,p=batch(); v=(a,folder,fs,p)
    if poison in ('expected','input'):
        words=a.text(folder+'/vectors.txt').splitlines(); fields=words[0].split(); fields[-1 if poison=='expected' else 0]='00000001'; words[0]=' '.join(fields)
        a.put(folder+'/vectors.txt',('\n'.join(words)+'\n').encode()); p['vectors_sha256']=a.hash(folder+'/vectors.txt')
    elif poison=='extra': a.put(folder+'/vectors.txt',a.body(folder+'/vectors.txt')+a.body(folder+'/vectors.txt').splitlines()[0]+b'\n'); p['vectors_sha256']=a.hash(folder+'/vectors.txt')
    elif poison=='missing': a.put(folder+'/vectors.txt',b'\n'.join(a.body(folder+'/vectors.txt').splitlines()[1:])+b'\n'); p['vectors_sha256']=a.hash(folder+'/vectors.txt')
    elif poison=='harness': a.put(folder+'/verification.cpp',a.body(folder+'/verification.cpp').replace(b'top.out_0 != want',b'false'))
    elif poison=='rtl': a.put(folder+'/verification.v',audit.verification_rtl(['ori(in0,1)'])); p['rtl_sha256']=a.hash(folder+'/verification.v')
    elif poison=='cleanup':
        w=a.json(folder+'/worker.json'); w['cleanup_errors']=['permission denied']; a.putjson(folder+'/worker.json',w)
    elif poison=='seed': p['random_seed']+=1
    else: p['formula_count']=True
    a.putjson(folder+'/worker.result.json',p)
    with pytest.raises(ValueError): check_batch(v)


def test_signed_wrap_fallback_actual_clt_alias_and_100_boundary_outputs():
    assert check_batch(batch(fallback=True))[1:]==(2148,100)

@pytest.mark.parametrize('poison',['boundary','incident','candidate','flag','initial','observation','version'])
def test_signed_wrap_fallback_corruption(poison):
    v=batch(fallback=True); a,folder,fs,p=v; cross=folder+'/yosys-boundary-cross-check'
    if poison=='boundary': a.put(cross+'/eval.log',a.body(cross+'/eval.log').replace(b"32'00000000000000000000000000000000",b"32'00000000000000000000000000000001",1)); p['independent_yosys_log_sha256']=a.hash(cross+'/eval.log')
    elif poison=='incident': p['incident']['formula_index']=1; a.putjson(folder+'/initial-failure.json',p['incident'])
    elif poison=='candidate': a.put(cross+'/candidate.v',audit.original_rtl('ori(in0,1)'))
    elif poison=='flag': p['build_command'].remove('-fwrapv')
    elif poison=='initial': a.put(folder+'/initial-failure.log',b'')
    elif poison=='observation': a.putjson(cross+'/observations.json',[])
    else: a.put(cross+'/eval.log',a.body(cross+'/eval.log').replace(tools()['executables']['yosys']['version'].encode(),b'Yosys OTHER')); p['independent_yosys_log_sha256']=a.hash(cross+'/eval.log')
    a.putjson(folder+'/validation-resolution.json',p); a.putjson(folder+'/worker.result.json',p)
    with pytest.raises(ValueError): check_batch(v)


def test_zero_wire_mapping_no_abc_remains_zero():
    counts,_=check_mapping(mapping()); assert counts=={'lut4':0,'carry':0,'ff':0,'bram':0,'primitive_counts':{}}


def test_all_ff_bram_resource_variants_are_recounted():
    types=['SB_LUT4']*2+['SB_CARRY']*3+sorted(audit.FF_TYPES)+sorted(audit.BRAM_TYPES)
    counts,_=check_mapping(mapping(types=types))
    assert (counts['lut4'],counts['carry'],counts['ff'],counts['bram'])==(2,3,20,4)

@pytest.mark.parametrize('poison',['netlist','unknown','script','version','abc','data','early','late','metricbool','rtl','python'])
def test_reauthenticated_mapping_poison(poison):
    v=mapping(types=['SB_LUT4']); a,f,m,g,gs=v; folder='circuits/'+h(f.encode())
    if poison in ('netlist','unknown'):
        a.putjson(folder+'/ice40-netlist.json',netlist(['SB_LUT4']*2 if poison=='netlist' else ['$add'])); m['netlist_sha256']=a.hash(folder+'/ice40-netlist.json')
    elif poison=='script': a.put(folder+'/ice40.ys',a.body(folder+'/ice40.ys').replace(b'synth_ice40',b'synth')); m['script_sha256']=a.hash(folder+'/ice40.ys')
    elif poison in ('version','abc','data'):
        old,new={'version':(tools()['executables']['yosys']['version'],'Yosys WRONG'),'abc':('/native/bin/yosys-abc','/foreign/abc'),'data':('/native/share/yosys/ice40/cells_sim.v','/foreign/cells_sim.v')}[poison]
        a.put(folder+'/ice40.log',a.text(folder+'/ice40.log').replace(old,new).encode()); m['log_sha256']=a.hash(folder+'/ice40.log')
    elif poison=='early':
        start=a.json(folder+'/measurement-start.json'); start['started_at_utc']=T2; a.putjson(folder+'/measurement-start.json',start)
    elif poison=='late': m['measured_at_utc']='2026-10-17T00:00:00+00:00'
    elif poison=='metricbool': m['ice40_lut4_count']=True
    elif poison=='rtl': a.put(folder+'/candidate.v',audit.original_rtl('ori(in0,1)')); m['rtl_sha256']=a.hash(folder+'/candidate.v')
    else:
        row=a.json(folder+'/worker.json'); row['python_invocation']['sha256']='f'*64; a.putjson(folder+'/worker.json',row)
    a.putjson(folder+'/measurement.json',m)
    raw={k:value for k,value in m.items() if k not in {'ice40_ff_count','ice40_bram_count','tool_sha256','abc_invocations','data_invocations'}}
    a.putjson(folder+'/metrics.json',raw); a.putjson(folder+'/worker.result.json',raw)
    with pytest.raises(ValueError): check_mapping(v)


def pool():
    f='ori(in0,0)'; cid=audit.identifier(f); names=[n for n in audit.FAMILIES if n!='recursion']
    c=[{'candidate_id':cid,'formula':f,'programs':names,'families':sorted(set(audit.FAMILIES.values()))}]
    m=[{'program':name,'family':family,'status':'empty' if name=='recursion' else 'complete','canonical_count':0 if name=='recursion' else 1,'canonical_ids':[] if name=='recursion' else [cid]} for name,family in audit.FAMILIES.items()]
    return c,m


def test_full_familiar_shared_zero_pool_retained():
    c,m=pool(); assert audit.verify_pool(c,m)==5
    points={'schema':'isaforge-v11e-frozen-point-predictions-v1','candidate_count':1,'models':{name:[{**c[0],'predicted_lut4':0,'upper_lut4':None,'calibration_status':'uncalibrated'}] for name in ('V6','V9')}}
    p=audit.verify_points(points,c); assert p['V6']==[{'id':c[0]['candidate_id'],'prediction':0}]

@pytest.mark.parametrize('poison',['missing','extra','emptyfamily','recursion','boolcount','foreign','candidate'])
def test_pool_poison(poison):
    c,m=pool()
    if poison=='missing': m.pop()
    elif poison=='extra': m.append(copy.deepcopy(m[0]))
    elif poison=='emptyfamily': m[0].update(status='empty',canonical_count=0,canonical_ids=[])
    elif poison=='recursion': m[-1].update(status='complete',canonical_count=1,canonical_ids=[c[0]['candidate_id']])
    elif poison=='boolcount': m[0]['canonical_count']=True
    elif poison=='foreign': m[0]['canonical_ids']=['foreign']
    else: c[0]['programs']=[]
    with pytest.raises(ValueError): audit.verify_pool(c,m)

@pytest.mark.parametrize('poison',['missingmodel','missingpoint','duplicate','nonfinite','negative','bool','foreign','calibrated'])
def test_point_poison(poison):
    c,_=pool(); row={**c[0],'predicted_lut4':1,'upper_lut4':None,'calibration_status':'uncalibrated'}
    r={'schema':'isaforge-v11e-frozen-point-predictions-v1','candidate_count':1,'models':{'V6':[row],'V9':[copy.deepcopy(row)]}}
    if poison=='missingmodel': del r['models']['V9']
    elif poison=='missingpoint': r['models']['V9']=[]
    elif poison=='duplicate': r['models']['V9']*=2
    elif poison=='nonfinite': row['predicted_lut4']=float('nan')
    elif poison=='negative': row['predicted_lut4']=-1
    elif poison=='bool': row['predicted_lut4']=True
    elif poison=='foreign': row['candidate_id']='foreign'
    else: row['upper_lut4']=3
    with pytest.raises(ValueError): audit.verify_points(r,c)


def test_parallel_mapping_intervals():
    assert audit.check_parallel([(T0,T2),(T1,T2),(T2,T3)])==2
    with pytest.raises(ValueError): audit.check_parallel([(T0,T3),(T1,T3),(T2,T3)])


def test_portable_exact_installed_inventory_not_host_paths(tmp_path,monkeypatch):
    repo=tmp_path/'repo'; root=repo/'results/study'; root.mkdir(parents=True); (repo/'source.py').write_bytes(b'code')
    monkeypatch.setattr(audit,'PACKAGING_COUNTS',(1,2,336)); monkeypatch.setattr(audit,'ROOT',repo); producer=audit.norm('/producer/repo'); inv=audit.installed_records(tools(),{'files':[]})
    entries=[{'path':'../../source.py','sha256':h(b'code'),'bytes':4},{'path':'../../../../native/python','sha256':'1'*64}]
    result,local=audit.authenticate_bindings(entries,root,producer,inv); assert len(result)==2 and len(local)==1
    entries[-1]['path']='../../../../foreign/python'
    with pytest.raises(ValueError): audit.authenticate_bindings(entries,root,producer,inv)


def test_duplicate_json_and_nonfinite_rejected():
    for body in (b'{"x":1,"x":2}',b'{"x":NaN}'):
        with pytest.raises(ValueError): audit.loads(body)


def test_partial_never_publishes_labels(tmp_path,monkeypatch):
    root=tmp_path/'study'; (root/'measurements').mkdir(parents=True); (root/'measurements/completion.json').write_bytes(encode({'schema':'isaforge-v11-transfer-target-completion-v1','complete':False}))
    monkeypatch.setattr(audit,'ROOT',tmp_path); out=tmp_path/'audit'
    with pytest.raises(ValueError): audit.publish(root,out)
    assert {p.name for p in out.iterdir()}=={'audit-failure.json'}


def test_worker_literal_is_read_not_executed():
    assert audit.worker_source(b"WORKER = 'print(1)'\n")== 'print(1)'
    with pytest.raises(ValueError): audit.worker_source(b"WORKER='a'\nWORKER='b'\n")


def complete_fixture(tmp_path,monkeypatch,poison=None,profile='legacy'):
    """Tiny complete five-family/one-global-wire package, independently sealed."""
    import os
    import posixpath
    repo=tmp_path/'repo'; root=repo/'results/pred'; inp=repo/'results/inputs'; stage=root/'measurements/attempt-0000'
    for p in (root,inp,stage): p.mkdir(parents=True,exist_ok=True)
    def put(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(v if isinstance(v,bytes) else encode(v)); return p
    def record(p): return {'path':os.path.relpath(p,root),'sha256':audit.sha(p),'bytes':p.stat().st_size}
    for name in audit.MANDATORY_SOURCES: put(repo/name,(ROOT/name).read_bytes())
    put(repo/'scripts/audit_v11c_recovery.py',(ROOT/'scripts/audit_v11c_recovery.py').read_bytes())
    if profile=='v11d':
        for name in ('scripts/predict_v11d_transfer.py','tests/test_predict_v11d_transfer.py'): put(repo/name,(ROOT/name).read_bytes())
    t=tools(); t['schema']='isaforge-v13b-coverage-tools-v1'
    t['environment']=audit.public_environment(t)
    if poison=='environment': t['environment']['PATH']='/arbitrary:'+t['environment']['PATH']
    base={'executables':{k:t['executables'][k] for k in ('yosys','abc')},'yosys_data':t['yosys_data']}
    basepath=put(repo/audit.BASE_TOOLS,base); basehash=audit.sha(basepath); t['inherited_inventory']={'path':audit.BASE_TOOLS,'sha256':basehash}
    put(root/'tools.json',t); put(root/'measurement-tools.json',t); put(root/'runtime.json',{'files':[]})
    c,m=pool(); put(inp/'candidates.json',c); put(inp/'memberships.json',m)
    for row in m: put(inp/'original-candidate-files'/(row['program']+'.json'),[] if not row['canonical_count'] else [{'formula':c[0]['formula']}])
    recovery=repo/'results/recovery'; rstage=recovery/'run/attempt-0000'; records={}; completed=[]; reviews={}
    for row in m:
        name=row['program']; rows=[] if not row['canonical_count'] else [{'formula':c[0]['formula']}]
        if poison=='recovery-omission' and name=='ammunition': rows.append({'formula':'ori(in0,1)'})
        p=put(recovery/'candidates'/(name+'.json'),rows)
        records[name]={'candidate_count':len(rows),'status':'complete' if rows else 'empty','family':row['family'],'candidate_file':{'path':os.path.relpath(p,recovery),'sha256':audit.sha(p)}}
        reviews[name]={'candidate_count':len(rows),'status':records[name]['status']}
        completed.extend({**r,'benchmark':name,'family':row['family']} for r in rows)
    put(rstage/'programs.json',records); put(rstage/'completed-rows.json',completed); put(rstage/'evidence-manifest.json',{'synthetic':True}); put(recovery/'preparation.json',{'synthetic':True})
    cd={'schema':'isaforge-v11c-recovery-completion-v1','complete':True,'failures':[],'completed_at_utc':T0,'completed_program_formula_rows':len(completed),'programs_sha256':audit.sha(rstage/'programs.json'),'completed_rows_sha256':audit.sha(rstage/'completed-rows.json')}
    put(recovery/'completion.json',cd); put(rstage/'completion.json',cd)
    cr={'schema':'isaforge-v11c-independent-recovery-audit-v1','status':'pass','complete':True,'source_sha256':audit.sha(repo/'scripts/audit_v11c_recovery.py'),'independence':'synthetic shared parser/extractor scope',
        'program_count':6,'reused_program_count':4,'recovered_program_count':2,'labels_predictions_features_fits':0,'audited_at_utc':T0,'programs':reviews,'program_formula_rows':len(completed),'unique_canonical_formulas':len({r['formula'] for r in completed}),
        'preparation_sha256':audit.sha(recovery/'preparation.json'),'completion_sha256':audit.sha(recovery/'completion.json'),'evidence_manifest_sha256':audit.sha(rstage/'evidence-manifest.json')}
    review_path=put(recovery/'raw-audit.json',cr)
    put(inp/'preparation.json',{'schema':'isaforge-v11-model-comparison-inputs-v1','status':'prepared-inputs-only','unique_canonical_originals':1,'program_formula_memberships':5,'source_root':'../recovery','audit_independence':cr['independence'],'reviewed_audit':{'path':'../recovery/raw-audit.json','sha256':audit.sha(review_path)}})
    columns=[f'f{i}' for i in range(336)]; selected=columns[:217]; frozen={'version':t['executables']['yosys']['version'],'executable_sha256':t['executables']['yosys']['sha256']}
    models={}; expected_models={}; metadata_hashes={}
    for name,count in [('V6',1665),('V9',1713)]:
        rel=f'models/{name}.joblib'; artifact=put(repo/rel,b'synthetic model '+name.encode()); ah=audit.sha(artifact)
        meta=put(artifact.with_suffix('.json'),{'artifact_sha256':ah,'training_formula_count':count,'kind':'mapping_v6','calibration':{'status':'uncalibrated'},'feature_columns':columns,'mapping_columns':selected,'frozen_tool':frozen})
        expected_models[name]=(rel,ah,count); metadata_hashes[name]=audit.sha(meta)
        models[name]={'artifact':{'path':rel,'sha256':ah},'metadata':{'path':str(meta.relative_to(repo)),'sha256':audit.sha(meta)}}
    put(inp/'predictors.json',models)
    feature_source=repo/'results/features'; feature_source.mkdir()
    fp=put(feature_source/'feature-plan.json',{'columns':columns,'selected_columns':selected,'selected_indices':list(range(217)),'input_root':'../inputs','frozen_tool':frozen})
    feature=put(feature_source/'features/attempt-0000/features.json',{'columns':columns,'records':[{**c[0],'values':[0]*336}]})
    fzip=put(feature_source/'features/attempt-0000/raw-evidence.zip',b'hash-bound synthetic feature payload')
    fmanifest=put(feature_source/'features/attempt-0000/raw-evidence.json',{'archive_sha256':audit.sha(fzip)})
    fdone={'schema':'isaforge-v11-transfer-feature-completion-v1','complete':False,'failures':[{'stage':'archive-final','error':"AbortStage('Owned stage deadline')"}],'cleanup_failures':[],'candidate_count':1,'completed_extractions':1,'new_predictions':0,'new_labels':0,'new_fits':0,'completed_at_utc':T0,'features_sha256':audit.sha(feature),'raw_archive_sha256':audit.sha(fzip),'raw_manifest_sha256':audit.sha(fmanifest)}
    if poison=='featurecount': fdone['completed_extractions']=0
    if poison=='shortfeatures': put(feature,{'columns':columns,'records':[]}); fdone['features_sha256']=audit.sha(feature)
    put(feature_source/'features/completion.json',fdone); put(feature_source/'features/attempt-0000/completion.json',fdone)
    put(feature_source/'features/attempt-0000/replay/result.json',{'complete':True,'records':1,'native_channels':2,'features_sha256':audit.sha(feature)})
    terminal=put(feature_source/'archive-failure/terminal-observation.json',{'synthetic':True})
    packaged=repo/'results/packaged'; packaged.mkdir()
    put(packaged/'packaging-plan.json',{'original_root':feature_source.relative_to(repo).as_posix()})
    with zipfile.ZipFile(packaged/'raw-evidence.zip','w') as z: z.writestr('features.json',feature.read_bytes())
    put(packaged/'raw-evidence.json',{'archive_sha256':audit.sha(packaged/'raw-evidence.zip'),'files':[{'path':'features.json','sha256':audit.sha(feature),'bytes':feature.stat().st_size}]})
    put(packaged/'completion.json',{'complete':True,'error':None,'original_completion_remains_false':True,'completed_at_utc':T0,'archive_sha256':audit.sha(packaged/'raw-evidence.zip')})
    review={'schema':'isaforge-v11d-independent-feature-packaging-audit-v1','status':'pass','complete':True,'records':1,'native_channels':2,'full_columns':336,'original_completion_remains_false':True,'audited_at_utc':T0,
        **{k:audit.sha(p) for k,p in [('completion_sha256',packaged/'completion.json'),('archive_sha256',packaged/'raw-evidence.zip'),('manifest_sha256',packaged/'raw-evidence.json'),('original_completion_sha256',feature_source/'features/completion.json'),('features_sha256',feature),('auditor_sha256',repo/'scripts/audit_v11d_feature_packaging.py'),('tests_sha256',repo/'tests/test_audit_v11d_feature_packaging.py'),('shared_helper_sha256',repo/'scripts/recover_v11d_feature_archive.py')]}}
    reviewed=put(packaged/'audit.json',review)
    admission={'schema':'isaforge-v11-recovered-feature-admission-v1','source_feature_root':'../features','recovery_root':'../packaged','original_completion_remains_false':True,'reviewed_recovery_audit':record(reviewed),'reviewed_recovery_audit_sha256':audit.sha(reviewed),
        **{k:record(p) for k,p in [('source_feature_plan',fp),('source_failed_completion',feature_source/'features/completion.json'),('source_terminal_observation',terminal),('features',feature),('recovery_completion',packaged/'completion.json'),('recovery_archive',packaged/'raw-evidence.zip'),('recovery_manifest',packaged/'raw-evidence.json')]}}
    ip=put(root/'inference-plan.json',{'input_root':'../inputs','feature_admission':admission,'raw_replay_native_channels':2})
    pstage=root/'predictions/attempt-0000'
    log=put(pstage/'worker.log',b''); runner=repo/'scripts/predict_v11e_transfer.py'
    predo={'status':'approved-v11e-recovered-feature-frozen-predictions','reviewed_at_utc':T0,'freeze_commit':'a'*40,'runner_sha256':audit.sha(runner),'tests_sha256':audit.sha(repo/'tests/test_predict_v11e_transfer.py'),'candidate_count':1,'maximum_predictions':2,'inference_plan_sha256':audit.sha(ip),'recovery_completion_sha256':audit.sha(packaged/'completion.json'),'features_sha256':audit.sha(feature)}
    claim={'claimed_at_utc':T0,'runner_sha256':audit.sha(runner),'inference_plan_sha256':audit.sha(ip),'maximum_predictions':2}
    put(root/'prediction-approval.json',predo); claim['approval_sha256']=audit.sha(root/'prediction-approval.json')
    put(root/'prediction-approval.json',predo); put(root/'prediction-claim.json',claim)
    pw={'schema':'isaforge-v11e-prediction-worker-v1','action':'inference-worker','complete':True,'returncode':0,'primary_error':None,'cleanup_errors':[],'remaining_owned_children':[],'runner_sha256':audit.sha(runner),'log_sha256':audit.sha(log),'started_at_utc':T0,'completed_at_utc':T0}
    pw.update({'timeout_seconds':300,'elapsed_seconds':1,'command':['/native/python','/producer/repo/scripts/predict_v11e_transfer.py','inference-worker','--root','/producer/repo/results/pred','--payload',json.dumps({'claim_sha256':audit.sha(root/'prediction-claim.json')})]})
    put(pstage/'worker.json',pw)
    result={'schema':'isaforge-v11e-frozen-point-predictions-v1','candidate_count':1,'raw_replay_records':1,'raw_replay_native_channels':2,'source_failed_completion_sha256':audit.sha(feature_source/'features/completion.json'),'recovery_completion_sha256':audit.sha(packaged/'completion.json'),'models':{n:[{**c[0],'predicted_lut4':0,'upper_lut4':None,'calibration_status':'uncalibrated'}] for n in ('V6','V9')},
        **{key:audit.sha(p) for key,p in [('inference_plan_sha256',ip),('features_sha256',feature),('input_preparation_sha256',inp/'preparation.json'),('predictor_manifest_sha256',inp/'predictors.json'),('membership_sha256',inp/'memberships.json'),('runner_sha256',runner)]}}
    if poison=='point': result['models']['V9']=[]
    put(pstage/'result.json',result)
    pdone={'schema':'isaforge-v11e-frozen-point-completion-v1','feature_admission':admission,'new_native_jobs':0,'new_feature_extractions':0,'complete':True,'failures':[],'candidate_count':1,'prediction_count':2,'new_labels':0,'new_fits':0,'calibration_jobs':0,'completed_at_utc':T0,
        **{key:audit.sha(p) for key,p in [('worker_receipt_sha256',pstage/'worker.json'),('worker_log_sha256',log),('approval_sha256',root/'prediction-approval.json'),('claim_sha256',root/'prediction-claim.json')]}}
    put(root/'predictions/completion.json',pdone); put(pstage/'completion.json',pdone)
    files=[record(p) for p in sorted(repo.rglob('*')) if p.is_file() and p!=root/'measurement-tools.json']
    for path,hh in audit.installed_records(t,{'files':[]}).items():
        if poison=='installed' and str(path)=='/native/python': continue
        files.append({'path':posixpath.relpath(str(path),'/producer/repo/results/pred'),'sha256':hh,'bytes':10})
    freeze={'schema':'isaforge-v11e-recovered-feature-point-freeze-v1','feature_admission':admission,'complete':True,'frozen_at_utc':T0,'candidate_count':1,'prediction_count':2,'columns':columns,'selected_columns':selected,'selected_indices':list(range(217)),'frozen_tool':frozen,'fits':0,'calibration_jobs':0,'labels_read':0,'files':files,
        **{key:audit.sha(p) for key,p in [('inference_plan_sha256',ip),('input_preparation_sha256',inp/'preparation.json'),('feature_completion_sha256',feature_source/'features/completion.json'),('prediction_completion_sha256',root/'predictions/completion.json'),('point_predictions_sha256',pstage/'result.json')]}}
    put(root/'point-freeze.json',freeze)
    plan={'schema':'isaforge-v11-transfer-target-plan-v1','status':'prepared-no-target-jobs','created_at_utc':T0,'point_freeze_sha256':audit.sha(root/'point-freeze.json'),'prediction_completion_sha256':audit.sha(root/'predictions/completion.json'),'prediction_frozen_at_utc':T0,'policy':audit.POLICY,'program_formula_memberships':5,'tools':{'path':'measurement-tools.json','sha256':audit.sha(root/'measurement-tools.json')},'files':files+[record(root/'point-freeze.json')],
        'budget':{'candidate_count':1,'verification_batches':1,'expected_rtl_comparisons':2148,'maximum_mapping_attempts':1,'maximum_attempt_seconds':3600,'uncapped_serial_batch_worker_bound_seconds':360*2+600+10*2,'engineering_amendment':'One 3600-second attempt including packaging; unfinished full pool remains failed.'}}
    put(root/'measurement-plan.json',plan)
    common={'candidate_count':1,'point_freeze_sha256':audit.sha(root/'point-freeze.json'),'prediction_completion_sha256':audit.sha(root/'predictions/completion.json'),'measurement_plan_sha256':audit.sha(root/'measurement-plan.json'),'tools_sha256':audit.sha(root/'measurement-tools.json'),'collector_sha256':audit.sha(repo/'scripts/measure_v11e_transfer.py')}
    approval={**common,'status':'approved-v11-full-pool-original-targets','maximum_new_labels':1,'expected_rtl_comparisons':2148,'collector_tests_sha256':audit.sha(repo/'tests/test_measure_v11e_transfer.py'),'freeze_commit':'a'*40,'reviewed_at_utc':T0}
    put(root/'measurement-approval.json',approval)
    release={**common,'schema':'isaforge-v11-target-release-v1','freeze_commit':'a'*40,'approval_sha256':audit.sha(root/'measurement-approval.json'),'policy':audit.POLICY,'released_at_utc':T0}; put(root/'label-release.json',release)
    a,folder,fs,proof=batch(); proof['v4_validation_override_sha256']=audit.sha(repo/'isaforge/v4_validation.py'); a.putjson(folder+'/worker.result.json',proof)
    native_source=audit.worker_source((repo/'scripts/measure_v6.py').read_bytes())
    w=a.json(folder+'/worker.json'); w['command'][2]=native_source; a.putjson(folder+'/worker.json',w)
    gate={'verified_at_utc':T3,'formula_count':1,'comparison_count':2148,'verification_sha256':h(json.dumps([proof],sort_keys=True).encode())}; a.putjson('verification-gate.json',gate)
    ma,f,metric,_,_=mapping(); mf='circuits/'+h(f.encode()); st=ma.json(mf+'/measurement-start.json'); st['verification_gate_sha256']=a.hash('verification-gate.json'); ma.putjson(mf+'/measurement-start.json',st)
    w=ma.json(mf+'/worker.json'); w['command'][2]=native_source; ma.putjson(mf+'/worker.json',w)
    for name,body in ma.files.items(): a.put(name,body)
    labels=[{**c[0],'lut4_count':0,'carry_count':0,'ff_count':0,'bram_count':0,'rtl_sha256':metric['rtl_sha256'],'correctness_verified':True,'measurement_source':'rtl_synthesis'}]
    if poison=='label': labels[0]['lut4_count']=1
    for name,value in [('verification.json',[proof]),('unique-measurements.json',[metric]),('labels.json',labels)]: put(stage/name,value); a.put('stage/'+name,(stage/name).read_bytes())
    done={'schema':'isaforge-v11-transfer-target-completion-v1','attempt':'attempt-0000','complete':True,'failures':[],'primary_available':True,'candidate_count':1,'new_physical_measurements':1,'mapping_attempts':1,'verified_comparisons':2148,'verification_batch_sizes':[1],'verification_seed':audit.SEED,'vectors_per_original':2148,'mapping_workers':2,'original_rtl_only':True,'historical_labels_reused':False,'new_fits':0,'freeze_commit':'a'*40,'completed_at_utc':T5,
        **{key:audit.sha(p) for key,p in [('point_freeze_sha256',root/'point-freeze.json'),('prediction_completion_sha256',root/'predictions/completion.json'),('release_sha256',root/'label-release.json'),('measurement_plan_sha256',root/'measurement-plan.json'),('tools_sha256',root/'measurement-tools.json'),('approval_sha256',root/'measurement-approval.json'),('collector_sha256',repo/'scripts/measure_v11e_transfer.py'),('verification_sha256',stage/'verification.json'),('unique_measurements_sha256',stage/'unique-measurements.json'),('labels_sha256',stage/'labels.json')]}}
    put(stage/'completion.json',done); put(root/'measurements/completion.json',done); a.put('stage/completion.json',encode(done))
    for name in ('measurement-plan.json','measurement-tools.json','measurement-approval.json','label-release.json','point-freeze.json'): a.put(name,(root/name).read_bytes())
    for name in audit.MANDATORY_SOURCES: a.put('sources/'+name,(repo/name).read_bytes())
    if profile=='v11d':
        for name in ('scripts/predict_v11d_transfer.py','tests/test_predict_v11d_transfer.py'): a.put('sources/'+name,(repo/name).read_bytes())
    archive=stage/'raw-evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in a.files.items(): z.writestr(name,body)
    put(stage/'raw-evidence.json',{'schema':'isaforge-v11-target-archive-v1','complete':True,'attempt':'attempt-0000','archive_sha256':audit.sha(archive),'completion_sha256':audit.sha(stage/'completion.json'),'files':list(a.entries.values()),'compiler_objects_included':False})
    monkeypatch.setattr(audit,'PACKAGING_COUNTS',(1,2,336)); monkeypatch.setattr(audit,'ROOT',repo); monkeypatch.setattr(audit,'MODELS',expected_models); monkeypatch.setattr(audit,'MODEL_METADATA_SHA',metadata_hashes); monkeypatch.setattr(audit,'BASE_TOOLS_SHA',basehash)
    return root,stage


def test_complete_archive_to_independently_derived_scoring_inputs(tmp_path,monkeypatch):
    root,stage=complete_fixture(tmp_path,monkeypatch)
    report,resources,payload=audit.run(root)
    assert report['status']=='pass' and report['rtl_comparisons']==2148 and report['prediction_count']==2
    assert report['program_formula_memberships']==5 and resources[0]['lut4']==0 and payload['labels'][0]['lut4']==0
    assert payload['outcomes'][-1]['status']=='empty'

@pytest.mark.parametrize('poison',['label','featurecount','shortfeatures','point','environment','installed','recovery-omission'])
def test_complete_reauthenticated_package_poison(tmp_path,monkeypatch,poison):
    root,_=complete_fixture(tmp_path,monkeypatch,poison)
    with pytest.raises(ValueError): audit.run(root)


def test_exact_v11d_profile_same_numeric_schema(tmp_path,monkeypatch):
    root,_=complete_fixture(tmp_path,monkeypatch,profile='v11d')
    report,_,_=audit.run(root)
    assert report['closure']['predictor_runner']=='scripts/predict_v11e_transfer.py'


def test_independent_batch_renderers_match_actual_frozen_writer_without_native(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from isaforge import rtl
    fs=['mulhu(in0,in1)','srai(sll(in0,in1),31)','lui(-2147483648)']
    monkeypatch.setattr(rtl.shutil,'which',lambda _: '/pinned/verilator')
    seen=[]
    def saved_stub(command,**kwargs):
        seen.append(command)
        stdout='Verilator synthetic\n' if command[-1]=='--version' else '2148 vectors passed\n' if command[0].endswith('Vverification_top') else ''
        return SimpleNamespace(returncode=0,stdout=stdout,stderr='')
    monkeypatch.setattr(rtl.subprocess,'run',saved_stub)
    rtl.verify_rtl_batch(fs,tmp_path,random_vectors=2048,seed=audit.SEED)
    assert len(seen)==3
    assert (tmp_path/'verification.v').read_bytes()==audit.verification_rtl(fs)
    assert (tmp_path/'verification.cpp').read_bytes()==audit.verification_cpp(len(fs))
    assert audit.verify_vectors((tmp_path/'vectors.txt').read_bytes(),fs)==6444


def rewrite_archive(stage,mutator):
    p=stage/'raw-evidence.zip'
    with zipfile.ZipFile(p) as z: members={n:z.read(n) for n in z.namelist()}
    mutator(members)
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
        for n,body in members.items(): z.writestr(n,body)
    manifest=audit.read(stage/'raw-evidence.json'); manifest['archive_sha256']=audit.sha(p)
    manifest['files']=[{'path':n,'bytes':len(b),'sha256':h(b)} for n,b in members.items()]
    (stage/'raw-evidence.json').write_bytes(encode(manifest))

@pytest.mark.parametrize('poison',['unsafe','missing-source','missing-vector','foreign-circuit','duplicate-zip','unbound-source'])
def test_archive_corruption_fails_closed(tmp_path,monkeypatch,poison):
    root,stage=complete_fixture(tmp_path,monkeypatch)
    def change(members):
        if poison=='unsafe': members['../outside']=b'bad'
        elif poison=='missing-source': del members['sources/isaforge/v4_validation.py']
        elif poison=='missing-vector': del members['verification/batch-0000/vectors.txt']
        elif poison=='foreign-circuit': members['circuits/'+('f'*64)+'/extra.json']=b'{}'
        elif poison=='unbound-source': members['sources/foreign.py']=b'print(1)'
    rewrite_archive(stage,change)
    if poison=='duplicate-zip':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(stage/'raw-evidence.zip','a') as z: z.writestr('verification-gate.json',b'{}')
        m=audit.read(stage/'raw-evidence.json'); m['archive_sha256']=audit.sha(stage/'raw-evidence.zip'); (stage/'raw-evidence.json').write_bytes(encode(m))
    with pytest.raises(ValueError): audit.run(root)


def test_whole_attempt_resource_lower_bound(tmp_path,monkeypatch):
    root,stage=complete_fixture(tmp_path,monkeypatch)
    manifest=audit.read(stage/'raw-evidence.json'); lower=sum(r['bytes'] for r in manifest['files'])+(stage/'raw-evidence.zip').stat().st_size+(stage/'raw-evidence.json').stat().st_size
    monkeypatch.setitem(audit.POLICY,'maximum_attempt_bytes',lower-1)
    with pytest.raises(ValueError,match='whole-attempt'): audit.Archive(stage)


def test_alias_cannot_use_unsealed_path():
    audit.command_alias('/Library/Developer/CommandLineTools/usr/bin/c++','c++',tools())
    with pytest.raises(ValueError): audit.command_alias('/foreign/c++','c++',tools())


def test_policy_and_all327_recipe_match_new_collector():
    import measure_v11e_transfer as collector
    assert audit.POLICY==collector.POLICY and audit.POLICY['attempt_seconds']==3600
    assert audit.PACKAGING_COUNTS==(327,806,336)


def test_failed_original_cannot_be_retroactively_complete(tmp_path,monkeypatch):
    root,stage=complete_fixture(tmp_path,monkeypatch)
    source=root.parent/'features'; done=audit.read(source/'features/completion.json'); done['complete']=True
    (source/'features/completion.json').write_bytes(encode(done))
    with pytest.raises(ValueError): audit.run(root)
