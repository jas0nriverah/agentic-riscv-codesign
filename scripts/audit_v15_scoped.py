#!/usr/bin/env python3
"""Read-only, stdlib-only V15 replay: no producer imports, native jobs or models."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from collections import Counter
import argparse
import hashlib
import itertools
import json
import math
import random
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MASK = (1 << 32)-1
SEED = 2026101915
PARAMETERS = (31,47,79,95,111,127,143,159)
SHIFTS = (2,4,6,8,10,12,14,16)
TEMPLATES = (
    ('xor_then_constmul','mul(xor(in0,in1),addi(0,{p}))',PARAMETERS),
    ('constmul_then_xor','xor(mul(in0,addi(0,{p})),in1)',PARAMETERS),
    ('xor_signed_shift','sub(srai(xor(in0,in1),{p}),srai(in1,31))',SHIFTS),
    ('and_signed_shift','sub(srai(and(in0,in1),{p}),srai(in1,31))',SHIFTS))


def require(ok, message):
    if not ok: raise ValueError(message)


def read(path):
    def unique(items):
        out = {}
        for key,value in items:
            require(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2), b''): h.update(block)
    return h.hexdigest()


def stamp(value):
    d = datetime.fromisoformat(value)
    require(d.tzinfo is not None and d.utcoffset().total_seconds()==0, 'UTC required')
    return d


def parse(formula):
    tokens = re.findall(r'in[01]|[A-Za-z_][A-Za-z_0-9]*|-?\d+|[(),]',formula)
    require(''.join(tokens)==formula, 'Noncanonical formula tokens')
    position = 0
    def node():
        nonlocal position
        value = tokens[position]; position += 1
        if re.fullmatch(r'-?\d+',value): return int(value)
        if value in ('in0','in1'): return value
        require(tokens[position]=='(', 'Formula open parenthesis'); position += 1
        a=node(); require(tokens[position]==',','Formula comma'); position += 1
        b=node(); require(tokens[position]==')','Formula close parenthesis'); position += 1
        return value,a,b
    out=node(); require(position==len(tokens),'Trailing formula tokens'); return out


def render(tree, module='candidate'):
    lines=[]; counter=0
    def expression(n):
        nonlocal counter
        if type(n) is int: return "32'h%08x" % (n & MASK)
        if type(n) is str: return n
        op,a,b=n; a=expression(a); b=expression(b); name='n'+str(counter); counter += 1
        if op=='srai':
            lines.extend(["wire [31:0] shift_%s = %s;"%(name,b),"wire [31:0] value_%s = %s;"%(name,a)])
            previous='value_'+name
            for i in range(5):
                width=1<<i; stage='stage_%s_%d'%(name,i)
                lines.append('wire [31:0] %s = shift_%s[%d] ? {{%d{%s[31]}}, %s[31:%d]} : %s;'%(stage,name,i,width,previous,previous,width,previous))
                previous=stage
            lines.append('wire [31:0] %s = %s;'%(name,previous))
        else:
            symbol={'xor':'^','and':'&','mul':'*','addi':'+','sub':'-'}[op]
            lines.append('wire [31:0] %s = %s %s %s;'%(name,a,symbol,b))
        return name
    output=expression(tree)
    return '\n'.join(['module '+module+'(input wire [31:0] in0, in1, output wire [31:0] result);',*lines,'assign result = '+output+';','endmodule',''])


def evaluate(n,a,b):
    if type(n) is int: return n & MASK
    if type(n) is str: return a if n=='in0' else b
    op,l,r=n; l=evaluate(l,a,b); r=evaluate(r,a,b)
    if op=='xor': return l ^ r
    if op=='and': return l & r
    if op=='mul': return (l*r)&MASK
    if op=='addi': return (l+r)&MASK
    if op=='sub': return (l-r)&MASK
    if op=='srai': return ((l-(1<<32) if l & (1<<31) else l) >> (r & 31)) & MASK
    raise ValueError('Unsupported stress operation')


def formulas(data):
    if type(data) is dict:
        if type(data.get('formula')) is str:
            yield data['formula']
            yield from (x for x in data.get('accepted_forms',[]) if type(x) is str)
        for key,value in data.items():
            if key not in ('formula','accepted_forms'): yield from formulas(value)
    elif type(data) is list:
        for value in data: yield from formulas(value)


def mean(values): return math.fsum(values)/len(values)
def quantile(values,q):
    a=sorted(values); z=(len(a)-1)*q; lo=math.floor(z); hi=math.ceil(z)
    return a[lo]+(a[hi]-a[lo])*(z-lo)


def calculate(rows,points,labels):
    y=[x['lut4'] for x in labels]; result={}
    for model,records in points['models'].items():
        p=[z['predicted_lut4'] for z in records]; error=[v-u for u,v in zip(y,p)]; absolute=list(map(abs,error))
        by={name:mean([v for v,r in zip(absolute,rows) if r['template']==name]) for name,_,_ in TEMPLATES}
        under=[u-v for u,v in zip(y,p)]; index=max(range(32),key=lambda i:under[i])
        result[model]={'macro_template_mae':mean(list(by.values())),'template_mae':by,'pooled_mae':mean(absolute),
            'bias':mean(error),'rmsle':math.sqrt(mean([(math.log1p(v)-math.log1p(u))**2 for u,v in zip(y,p)])),
            'absolute_error_quantiles':{str(q):quantile(absolute,q/100) for q in (90,95,99)},
            'worst_underprediction':{'lut4':max(0,under[index]),'candidate_id':rows[index]['candidate_id']},
            'caps':{str(c):{'false_accept':sum(v<=c<u for u,v in zip(y,p)),'false_reject':sum(u<=c<v for u,v in zip(y,p)),
                'predicted_accept':sum(v<=c for v in p),'actual_accept':sum(u<=c for u in y),'total':32} for c in (32,64,128)}}
    return {'models':result,'delta_v15_minus_v6':result['V15']['macro_template_mae']-result['V6']['macro_template_mae'],
        'delta_v15_minus_v9':result['V15']['macro_template_mae']-result['V9']['macro_template_mae']}


def run(root):
    root=Path(root).resolve(); require(root.is_relative_to(ROOT/'results'),'Repository result root required')
    plan=read(root/'plan.json'); rows=read(root/'candidates.json'); done=read(root/'attempt/completion.json')
    claim=read(root/'claim.json'); freeze=read(root/'point-freeze.json'); points=read(root/'attempt/predictions.json')
    labels=read(root/'attempt/labels.json'); declared=read(root/'attempt/metrics.json'); manifest=read(root/'attempt/raw-evidence.json')
    require(done['complete'] is True and done['failures']==[] and done['candidate_count']==done['completed_mapping_count']==32 and done['fits']==0,'Complete32 required')
    require(0<=done['elapsed_seconds']<=900,'Whole900s deadline')
    expected=[{'candidate_id':'v15-stress:'+hashlib.sha256(f.format(p=p).encode()).hexdigest(),'formula':f.format(p=p),'template':name,'parameter':p} for name,f,ps in TEMPLATES for p in ps]
    require(rows==expected and len(set(r['formula'] for r in rows))==32,'Exact frozen32 original templates required')
    require(plan['templates']==[{'name':n,'formula':f,'parameters':list(ps)} for n,f,ps in TEMPLATES],'Final frozen template plan changed')
    for name,key in [('candidates.json','candidates_sha256'),('novelty.json','novelty_sha256'),('tools.json','tools_sha256'),('runtime.json','runtime_sha256')]:
        require(sha(root/name)==plan[key],'Prepared '+name+' hash')
    require(claim['plan_sha256']==freeze['plan_sha256']==sha(root/'plan.json') and claim['freeze_commit']==freeze['freeze_commit'],'Claim/plan/freeze identity')
    require(done['point_freeze_sha256']==manifest['point_freeze_sha256']==sha(root/'point-freeze.json'),'Completion/freeze identity')
    require(freeze['features_sha256']==sha(root/'attempt/features.json') and freeze['predictions_sha256']==sha(root/'attempt/predictions.json'),'Prelabel point bytes')
    require(freeze['candidate_count']==32 and freeze['prediction_count']==96 and freeze['fits']==freeze['labels_read']==0,'96 prelabel point count')
    require(stamp(plan['created_at_utc'])<=stamp(claim['started_at_utc'])<=stamp(freeze['frozen_at_utc'])<=stamp(done['completed_at_utc']),'Plan/claim/freeze/completion chronology')
    for entry in plan['bindings']:
        path=(ROOT/entry['path']).resolve(); require(path.is_relative_to(ROOT) and sha(path)==entry['sha256'],'Prepared scientific binding changed')
    commit=claim['freeze_commit']; require(re.fullmatch('[0-9a-f]{40}',commit),'Git freeze identity')
    for path in [ROOT/p for p in plan['source_paths']]+[root/n for n in ('plan.json','candidates.json','novelty.json','tools.json','runtime.json')]:
        body=subprocess.check_output(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        require(hashlib.sha256(body).hexdigest()==sha(path),'Producer frozen Git bytes changed')
    novelty=read(root/'novelty.json'); require(novelty['status']=='pass' and novelty['all32_absent'] is True,'Novelty receipt')
    for comparison in novelty['comparisons']:
        path=ROOT/comparison['path']; require(sha(path)==comparison['sha256'],'Novelty reference changed')
        known=set(formulas(read(path))); require(not known.intersection(r['formula'] for r in rows),'Novelty overlap')
    amendment=plan['input_amendment']; archive=ROOT/amendment['archive']; oldmanifest=read(archive/'manifest.json')
    require(amendment['id']=='V15-I1' and sha(archive/'manifest.json')==amendment['manifest_sha256'],'Pre-freeze amendment manifest')
    for e in oldmanifest['files']: require(sha(archive/e['path'])==e['sha256'] and (archive/e['path']).stat().st_size==e['bytes'],'Archived rejected input bytes')
    old=read(archive/'candidates.json'); rejected=read(archive/'overlap-receipt.json')
    require(old[:24]==rows[:24] and len(old)==32 and {r['template'] for r in old[24:]}=={'sub_signed_shift'},'Whole fourth template amendment')
    require(all(v==0 and type(v) is int for v in rejected['calls'].values()) and stamp(rejected['recorded_at_utc'])<stamp(plan['created_at_utc']),'Input-only pre-freeze rejection receipt')
    require(len(set().union(*(set(v['overlap']) for v in rejected['comparisons'])))==4,'Retained four duplicate inputs')
    inventory={e['path']:e for e in manifest['files']}; require(len(inventory)==len(manifest['files']),'Unique raw inventory')
    actual={p.relative_to(root).as_posix() for p in (root/'raw').rglob('*') if p.is_file()}
    require(set(inventory)==actual,'Exact complete retained raw file closure')
    for name,e in inventory.items():
        safe=PurePosixPath(name); path=root/name
        require(not safe.is_absolute() and '..' not in safe.parts and not path.is_symlink() and path.stat().st_size==e['bytes'] and sha(path)==e['sha256'],'Raw file identity: '+name)
    features=read(root/'attempt/features.json'); require(len(features['columns'])==336 and len(features['records'])==32,'Full336 feature shape')
    require(set(points['models'])=={'V6','V9','V15'} and len(points['routes'])==32,'Exact model/routes')
    for model,values in points['models'].items():
        require(len(values)==32,'Full32 model points')
        for r,p in zip(rows,values):
            require(r['candidate_id']==p['candidate_id'] and r['formula']==p['formula'],'Ordered point identity')
            require(type(p['predicted_lut4']) in (int,float) and math.isfinite(p['predicted_lut4']) and p['predicted_lut4']>=0 and p['upper_lut4'] is None and p['calibration_status']=='uncalibrated','Uncalibrated finite point')
    require(points['models']['V15']==points['models']['V9'] and all(z['source_model']=='V9' for z in points['routes']),'All32 covered-domain routes equal V9')
    require(points==read(root/'raw/inference/result.json'),'Frozen inference result identity')
    runtime=read(root/'runtime.json'); tools=read(root/'tools.json')
    expected_models={'V6':('1a1828d7089554fed050769aff5007c383fbd5158e063d6da89f366104f47f56',1665),'V9':('dbcfb6c8143900bfda567407c35bd1ced6600cf042db5485a8750bfdbebe977d',1713)}
    require(set(plan['models'])==set(expected_models),'Exact frozen pair manifest')
    for name,(digest,count) in expected_models.items():
        model=plan['models'][name]; artifact=ROOT/model['path']; metadata=artifact.with_suffix('.json')
        require(model['sha256']==sha(artifact)==digest and model['training_rows']==count and sha(metadata)==model['metadata_sha256'],'Exact frozen artifact metadata')
        info=read(metadata); require(info['kind']=='mapping_v6' and info['training_formula_count']==count and info['calibration']['status']=='uncalibrated' and info['calibration']['upper_margin_lut4'] is None,'Frozen raw model contract')
    receipts=[]
    def receipt(folder,kind):
        w=read(folder/'worker.json')
        require(w['complete'] is True and w['returncode']==0 and type(w['returncode']) is int and w['primary_error'] is None and w['cleanup_errors']==w['remaining_owned_children']==[],'Successful cleaned worker')
        require(w['timeout_seconds']==360 and 0<=w['elapsed_seconds']<=370 and w['log_sha256']==sha(folder/'worker.log'),'Worker deadline/log')
        a,b=stamp(w['started_at_utc']),stamp(w['completed_at_utc'])
        require(stamp(claim['started_at_utc'])<=a<=b<=stamp(done['completed_at_utc']),'Worker attempt chronology')
        require(abs((b-a).total_seconds()-w['elapsed_seconds'])<=1,'Worker elapsed timestamp consistency')
        if kind in ('feature','inference'):
            action='feature-worker' if kind=='feature' else 'prediction-worker'
            require(w['command'][1:5]==[str(ROOT/'scripts/evaluate_v15_scoped.py'),action,'--root',str(root)],'Owned scientific worker source/root')
        else:
            invocation=w['python_invocation']; require(invocation['resolved']==runtime['files'][0]['path'] and invocation['sha256']==runtime['files'][0]['sha256'] and invocation['invoked']==w['command'][0],'Recorded pinned worker interpreter')
        receipts.append((a,b,kind)); return w
    inference=receipt(root/'raw/inference','inference'); require(stamp(inference['completed_at_utc'])<=stamp(freeze['frozen_at_utc']),'Points froze before inference completed')
    trees=[parse(r['formula']) for r in rows]; recounts=[]
    require([x['candidate_id'] for x in labels]==[r['candidate_id'] for r in rows],'Full ordered32 labels')
    for row,tree,label,feature in zip(rows,trees,labels,features['records']):
        key=row['candidate_id'].split(':')[1]; folder=root/'raw/circuits'/key; source=render(tree)
        require((folder/'candidate.v').read_text()==source,'Independent original RTL rendering')
        net=read(folder/'ice40-netlist.json'); cells=Counter(c['type'] for c in net['modules']['candidate']['cells'].values())
        require(set(cells)<={'SB_LUT4','SB_CARRY'},'Unexpected mapped top-module primitive')
        metric=read(folder/'metrics.json'); require(metric==read(folder/'worker.result.json'),'Mapping metric/result differs')
        require(metric['formula']==row['formula']==label['formula'] and label['lut4']==metric['ice40_lut4_count']==cells['SB_LUT4'] and metric['ice40_carry_count']==cells['SB_CARRY'] and metric['ice40_cell_types']==dict(cells),'Independent primitive label recount')
        for name,keyname in [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]: require(metric[keyname]==sha(folder/name),'Mapping member hash')
        expected_script='read_verilog "'+str(folder/'candidate.v')+'"\nsynth_ice40 -top candidate\ncheck -assert\nwrite_json "'+str(folder/'ice40-netlist.json')+'"\nstat\n'
        require((folder/'ice40.ys').read_text()==expected_script,'Original synthesis script')
        w=receipt(folder,'map'); payload=json.loads(w['command'][-1]); require(payload['kind']=='map' and payload['formula']==row['formula'] and payload['folder']==str(folder),'Owned mapping command identity')
        require(stamp(freeze['frozen_at_utc'])<=stamp(w['started_at_utc'])<=stamp(metric['measured_at_utc'])<=stamp(w['completed_at_utc']),'No target mapping before96point freeze')
        featurefolder=root/'raw/features'/key; fw=receipt(featurefolder,'feature')
        require(fw['command'][-1]==row['formula'] and fw['command'][2]=='feature-worker','Owned feature command identity')
        require(stamp(fw['completed_at_utc'])<=stamp(inference['started_at_utc']),'All features precede inference')
        require(feature==read(featurefolder/'result.json') and feature['formula']==row['formula'] and len(feature['values'])==336 and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in feature['values']),'Saved per-original features')
        recounts.append({'candidate_id':row['candidate_id'],'lut4':cells['SB_LUT4'],'carry':cells['SB_CARRY']})
    folder=root/'raw/verification'; proof=read(root/'attempt/verification.json')
    require(len(proof)==1 and proof[0]==read(folder/'worker.result.json'),'Single complete verification receipt')
    proof=proof[0]; require(proof['verified'] is True and proof['formula_count']==32 and proof['vectors_per_formula']==2148 and proof['total_comparisons']==68736 and proof['random_seed']==SEED and proof['signed_overflow_workaround_applied'] is False,'Verification scope')
    require((folder/'verification.log').read_text()=='2148 vectors passed\n','Recorded native verification success')
    require(sha(folder/'verification.v')==proof['rtl_sha256'] and sha(folder/'vectors.txt')==proof['vectors_sha256'],'Verification saved hashes')
    verilog='module verification_top(input wire [31:0] in0, in1, '+', '.join('output wire [31:0] out_'+str(i) for i in range(32))+');\n'
    verilog+='\n'.join('candidate_%d c%d(.in0(in0), .in1(in1), .result(out_%d));'%(i,i,i) for i in range(32))+'\nendmodule\n'
    verilog+='\n'.join(render(tree,'candidate_'+str(i)) for i,tree in enumerate(trees))
    require((folder/'verification.v').read_text()==verilog,'Independent32-module verification RTL')
    boundaries=(0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,0xffffffff)
    pairs=list(itertools.product(boundaries,repeat=2)); rng=random.Random(SEED); pairs += [(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
    with (folder/'vectors.txt').open() as stream:
        for a,b in pairs: require(stream.readline()==' '.join('%08x'%z for z in (a,b,*[evaluate(t,a,b) for t in trees]))+'\n','Independent68736 expected RV32 outcomes')
        require(stream.read()=='','Extra verification vectors')
    vw=receipt(folder,'verify'); require(stamp(freeze['frozen_at_utc'])<=stamp(vw['started_at_utc']),'Verification preceded point freeze')
    require(all(stamp(vw['completed_at_utc'])<=a for a,b,k in receipts if k=='map'),'Target mapping before full verification')
    events=sorted([(a,1) for a,b,k in receipts]+[(b,-1) for a,b,k in receipts]); active=0; maximum=0
    for t,delta in events: active+=delta; maximum=max(maximum,active)
    require(active==0 and maximum<=2 and len(receipts)==66,'Owned worker concurrency/count')
    computed=calculate(rows,points,labels); comparisons=[]
    def compare(a,b,path=''):
        if type(a) is dict:
            for k,v in a.items(): compare(v,b[k],path+'/'+k)
        elif type(a) in (int,float):
            require(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12),'Independent metric mismatch '+path); comparisons.append(abs(a-b))
        else: require(a==b,'Metric identity '+path)
    compare(computed,declared)
    inputs=[root/n for n in ('plan.json','claim.json','candidates.json','point-freeze.json','novelty.json','attempt/completion.json','attempt/metrics.json','attempt/raw-evidence.json','attempt/labels.json','attempt/predictions.json','attempt/features.json','attempt/verification.json')]
    return {'schema':'isaforge-v15-independent-review-v1','status':'pass','complete':True,'reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
        'auditor':{'path':Path(__file__).relative_to(ROOT).as_posix(),'sha256':sha(__file__)},'producer_freeze_commit':commit,
        'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs],
        'original_count':32,'prediction_count':96,'template_count':4,'mapped_netlists_recounted':32,'original_RTL_renderings_checked':32,
        'verification_expected_outcomes_recomputed':68736,'raw_files_hashed':len(inventory),'raw_bytes_hashed':sum(e['bytes'] for e in inventory.values()),
        'successful_cleaned_owned_workers':len(receipts),'maximum_overlapping_workers':maximum,'point_freeze_precedes_all_targets':True,
        'input_amendment':{'id':'V15-I1','retained_first24':True,'whole_fourth_template_replaced_before_claim':True,'rejected_unique_overlap_count':4},
        'metrics':computed,'metric_numeric_comparisons':len(comparisons),'maximum_metric_difference':max(comparisons),
        'V15_relative_MAE_change_vs_V6_percent':100*computed['delta_v15_minus_v6']/computed['models']['V6']['macro_template_mae'],
        'native_jobs':0,'models_loaded':0,'fits':0,
        'limits':['Independent stdlib-only limited-grammar RTL renderer, RV32 vector oracle, primitive recount and metric arithmetic; no producer/scorer modules imported.',
            'Saved successful Verilator execution authenticated; no native rerun, universal proof or mapped-netlist functional proof.',
            'V15-I1 pre-freeze input-only rejection authenticated from retained receipts; absence of unrecorded historical activity cannot be proved.',
            'All32 are covered-domain syntactic stress and route to V9: V15 equals V9 by construction. No fresh application-transfer or router-generalization result.',
            'Source/model/input and raw-byte lineage checked; OS hermeticity, historical live disk peaks and absence of external processes cannot be independently reconstructed.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    report=run(a.root)
    with a.output.open('x') as stream: json.dump(report,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps({k:report[k] for k in ('status','mapped_netlists_recounted','verification_expected_outcomes_recomputed','raw_files_hashed','maximum_overlapping_workers','V15_relative_MAE_change_vs_V6_percent')},indent=2))
