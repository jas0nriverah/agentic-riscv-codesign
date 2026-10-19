"""Independent universal QF_BV32 rule/reconstruction lemmas; no data or labels."""
from pathlib import Path
import argparse,hashlib,importlib.metadata,json,sys,time

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(deps,output):
    sys.path.insert(0,str(deps));import z3
    output.mkdir(parents=True,exist_ok=True)
    x,y,z,c,a,b=z3.BitVecs('x y z c a b',32)
    rules={
      'or_sub_repeated':((x|c)-x,(~x)&c),
      'sub_and_repeated':(x-(x&c),x&(~c)),
      'add_associative':((x+y)+z,x+(y+z)),
      'add_commutative':(x+y,y+x),
      'sub_as_inverse':(x-y,x+(-y)),
      'inverse_distributes_add':(-(x+y),(-x)+(-y)),
      'additive_cancellation':((x+y)-y,x),
      'coefficient_merge':(a*x+b*x,(a+b)*x),
      'coefficient_subtract':(a*x-b*x,(a-b)*x),
      'coefficient_distributes':(a*(x+y),a*x+a*y),
      'coefficient_reassociate':(a*(b*x),(a*b)*x),
      'coefficient_zero':(z3.BitVecVal(0,32)*x,z3.BitVecVal(0,32)),
      'coefficient_one':(z3.BitVecVal(1,32)*x,x),
    }
    for k in range(32):
        rules[f'left_shift_coefficient_{k:02}']=(x<<k,x*z3.BitVecVal(1<<k,32))
        rules[f'left_shift_add_distribution_{k:02}']=((x+y)<<k,(x<<k)+(y<<k))
        rules[f'left_shift_sub_distribution_{k:02}']=((x-y)<<k,(x<<k)-(y<<k))
    # RV32's entire shift word is masked, including values >=32 and negative.
    rules['rv32_shift_amount_mask']=(x<<(c&31),x<<z3.ZeroExt(27,z3.Extract(4,0,c)))
    results=[]
    for name,(src,tgt) in rules.items():
        # Polynomial simplification is itself Z3's bit-vector tactic, not a
        # Python algebraic rewrite or an assumed equality in the query.
        solver=z3.Then(z3.With('simplify',som=True),'qfbv').solver();solver.set(timeout=500)
        solver.add(src!=tgt);smt=solver.to_smt2();p=output/(name+'.smt2')
        p.write_text('(set-logic QF_BV)\n(set-option :timeout 500)\n'+smt)
        began=time.perf_counter();verdict=solver.check();elapsed=time.perf_counter()-began
        item={'name':name,'result':str(verdict),'elapsed_seconds':elapsed,'smt2_sha256':sha(p),'timeout_ms':500}
        if verdict==z3.sat:item['counterexample']=str(solver.model())
        if verdict==z3.unknown:item['reason_unknown']=solver.reason_unknown()
        # Parse the archived formula back independently: exact query replay.
        replay=z3.Then(z3.With('simplify',som=True),'qfbv').solver();replay.set(timeout=500)
        replay.add(z3.parse_smt2_file(str(p)));item['replayed_result']=str(replay.check());results.append(item)
    library=next((deps/'z3/lib').glob('libz3.*'))
    report={'status':'pass' if all(r['result']==r['replayed_result']=='unsat' for r in results) else 'FAIL',
      'scope':'Universal rules/affine reconstruction lemmas only; no formulas, features, labels or fits read',
      'logic':'QF_BV','word_bits':32,'solver_version':z3.get_version_string(),
      'solver_distribution_version':importlib.metadata.version('z3-solver'),
      'solver_library_sha256':sha(library),'solver_python_sha256':sha(deps/'z3/z3.py'),
      'solver_pipeline':['simplify(som=True)','qfbv'],'timeout_ms_per_query':500,
      'source_sha256':sha(__file__),'proof_count':len(results),'results':results,
      'proof_scope_limit':'Generic lemmas require separate local rewrite/congruence validation to certify a particular implementation or reconstructed formula.'}
    (output.parent/'generic-proofs.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--deps',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.deps.resolve(),a.output.resolve())
