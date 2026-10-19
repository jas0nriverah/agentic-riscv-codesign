"""Independent post-release mapped-cell/vector recount; no evaluator/model imports."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse,hashlib,itertools,json,random,sys

ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/2026-10-14-v6';OUT=BASE/'audit'
sys.path.insert(0,str(ROOT))
from isaforge.features import parse_formula
from isaforge.rtl import generate_rtl
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,what):
 if not ok:raise AssertionError(what)
stamp=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
MOD=2**32
def signed(value):return value if value<MOD//2 else value-MOD
ALIASES={'addi':'add','andi':'and','ori':'or','xori':'xor','slli':'sll','srli':'srl','srai':'sra','slti':'slt','sltiu':'sltu'}
OPS={'add':lambda a,b:a+b,'sub':lambda a,b:a-b,'and':lambda a,b:a&b,'or':lambda a,b:a|b,'xor':lambda a,b:a^b,
     'sll':lambda a,b:a*2**(b%32),'srl':lambda a,b:a//2**(b%32),'sra':lambda a,b:signed(a)//2**(b%32),
     'slt':lambda a,b:int(signed(a)<signed(b)),'sltu':lambda a,b:int(a<b),'mul':lambda a,b:a*b,
     'mulh':lambda a,b:(signed(a)*signed(b))//MOD,'mulhu':lambda a,b:(a*b)//MOD,'mulhsu':lambda a,b:(signed(a)*b)//MOD}
def program(formula):
    instructions=[];memo={}
    def compile(node):
        if node in memo:return memo[node]
        args=tuple(compile(n) for n in node.children);index=len(instructions)
        instructions.append((node.value,args));memo[node]=index;return index
    compile(parse_formula(formula));return instructions
def oracle(instructions,a,b):
    values=[]
    for token,args in instructions:
        if not args:value=token if isinstance(token,int) else a if token=='in0' else b
        elif token=='lui':value=values[args[0]]  # Formula contract already stores the resulting immediate.
        else:value=OPS[ALIASES.get(token,token)](values[args[0]],values[args[1]])
        values.append(value%MOD)
    return values[-1]

def audit(scope):
    directory=BASE/'corpus'/scope;done=read(directory/'completion.json')
    need(done.get('complete') is True and not done['failures'],'Explicit complete target stage required')
    need(done['scope']==scope and done['legacy_measurements_reused'] is False,'Fresh original target scope')
    release=read(directory/'label-release.json');approval=read(directory/'label-approval.json')
    need(done['release']==release and release['parent_review']==approval and approval['scope']==scope and approval['approved_for_label_release'] is True,'Stage parent approval chain')
    freeze=BASE/('point-freeze.json' if scope=='calibration' else 'calibration-freeze.json')
    need(sha(freeze)==approval['freeze_sha256']==release['freeze_sha256'],'Stage freeze identity')
    need(stamp(read(freeze)['frozen_at_utc'])<=stamp(approval['reviewed_at_utc'])<=stamp(release['released_at_utc'])<=stamp(done['completed_at_utc']),'Stage chronology')
    need(done['collector_sha256']==sha(ROOT/'scripts/measure_v6.py'),'Frozen collector bytes')
    attempt=directory/done['attempt'];scratch=(BASE/done['scratch_directory']).resolve()
    need(scratch.is_relative_to(ROOT/'generated/v6-measurements'/scope),'Portable owned stage path')
    for name,key in [('dataset.json','dataset_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:need(sha(attempt/name)==done[key],'Stage evidence hash')
    rows=read(directory/'candidates.json');formulas=sorted(r['formula'] for r in rows)
    unique=read(attempt/'unique-measurements.json');metrics={m['formula']:m for m in unique}
    need(len(rows)==len(set(formulas))==len(unique)==192 and set(metrics)==set(formulas),'192 original formula coverage')
    sums=Counter()
    for formula,metric in metrics.items():
        folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
        need(read(folder/'metrics.json')==metric,'Retained circuit metrics')
        for name,key in [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]:need(sha(folder/name)==metric[key],'Retained native mapping bytes')
        need((folder/'candidate.v').read_text()==generate_rtl(formula),'Original emitted circuit')
        need(metric['tool']==done['tool'] and metric['tool_sha256']==done['tool_sha256'] and metric['measurement_source']=='rtl_synthesis','Target tool and source')
        need(stamp(release['released_at_utc'])<=stamp(metric['measured_at_utc'])<=stamp(done['completed_at_utc']),'Post-release original mapping')
        cells=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate'].get('cells',{}).values())
        need(dict(cells)==metric['ice40_cell_types'] and cells['SB_LUT4']==metric['ice40_lut4_count'] and cells['SB_CARRY']==metric['ice40_carry_count'],'Independent primitive recount')
        sums.update(cells)
    labels=read(attempt/'dataset.json');label_index={(r['benchmark'],r['candidate_id']):r for r in labels}
    need(len(label_index)==192,'Distinct complete labeled identities')
    for row in rows:
        label=label_index[(row['benchmark'],row['candidate_id'])];metric=metrics[row['formula']]
        need(all(label[k]==v for k,v in row.items()),'Unchanged frozen candidate')
        need(label['lut4_count']==metric['ice40_lut4_count'] and label['carry_count']==metric['ice40_carry_count'] and label['rtl_sha256']==metric['rtl_sha256'],'Original expanded targets')
    proofs=read(attempt/'verification.json');need([p['formula_count'] for p in proofs]==[128,64],'Exact verification batches')
    comparisons=0;seed=2026101520+(scope=='test')
    boundary=(0,1,2,31,32,33,0x7fffffff,0x80000000,0x80000001,0xffffffff)
    for index,proof in enumerate(proofs):
        batch=formulas[index*128:index*128+proof['formula_count']];folder=scratch/'verification'/f'batch-{index*128:04d}'
        outputs=', '.join(f'output wire [31:0] out_{i}' for i in range(len(batch)))
        source=[f'module verification_top(input wire [31:0] in0, in1, {outputs});']
        source += [f'candidate_{i} c{i}(.in0(in0), .in1(in1), .result(out_{i}));' for i in range(len(batch))]+['endmodule']
        source += [generate_rtl(f,f'candidate_{i}') for i,f in enumerate(batch)]
        need((folder/'verification.v').read_text()=='\n'.join(source),'Exact sorted verification formula batch')
        need(sha(folder/'verification.v')==proof['rtl_sha256'] and sha(folder/'vectors.txt')==proof['vectors_sha256'],'Verification bytes')
        need(proof['verified'] is True and proof['random_seed']==seed and proof['vectors_per_formula']==2148 and proof['total_comparisons']==len(batch)*2148,'Sampled verification coverage')
        need(proof['v4_validation_override_sha256']==sha(ROOT/'isaforge/v4_validation.py'),'Signed wrap verifier source')
        if proof.get('signed_overflow_workaround_applied'):need(sha(folder/'yosys-boundary-cross-check/eval.log')==proof['independent_yosys_log_sha256'],'Signed wrap independent boundary evidence')
        rng=random.Random(seed);pairs=list(itertools.product(boundary,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048)]
        programs=[program(f) for f in batch];lines=(folder/'vectors.txt').read_text().splitlines();need(len(lines)==2148,'Vector count')
        for text,pair in zip(lines,pairs):
            values=[int(v,16) for v in text.split()];need(len(values)==len(batch)+2 and tuple(values[:2])==pair,'Seeded boundary/random inputs')
            need([oracle(p,*pair) for p in programs]==values[2:],'Independent RV32 postfix oracle all retained outputs')
            comparisons+=len(batch)
    archive=read(directory/'raw-evidence.json');need(sha(directory/'raw-evidence.zip')==archive['archive_sha256'] and sha(directory/'completion.json')==archive['completion_sha256'],'Portable raw archive binding')
    result={'status':'pass','scope':scope,'original_netlists_recounted':192,'lut4_sum':sums['SB_LUT4'],'carry_sum':sums['SB_CARRY'],
            'all_retained_oracle_outputs_recomputed':comparisons,'oracle':'Separately implemented postfix RV32 evaluator; no production evaluator imported.',
            'sampled_verification_not_formal_proof':True,'raw_archive_sha256':archive['archive_sha256'],'fresh_target_file_reads':scope,
            'new_model_fitting':False,'new_hardware_execution':False,'audit_source_sha256':sha(Path(__file__))}
    write_path=OUT/f'{scope}-raw-oracle.json';write_path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=('calibration','test'),required=True);args=parser.parse_args();audit(args.scope)
