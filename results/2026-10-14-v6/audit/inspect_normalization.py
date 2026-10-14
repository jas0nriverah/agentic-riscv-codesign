"""Read-only, consumed-test diagnosis; no rewrites, fitting or hardware calls."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from isaforge.rtl import parse_formula
MASK=(1<<32)-1
def collect(n):
    if not n.children and isinstance(n.value,int):return {},n.value&MASK
    if n.children and n.value in ('sll','slli') and not n.children[1].children and isinstance(n.children[1].value,int):
        a,c=collect(n.children[0]);k=1<<(n.children[1].value&31)
        return {s:(v*k)&MASK for s,v in a.items() if (v*k)&MASK},(c*k)&MASK
    if n.children and n.value in ('add','addi','sub'):
        a,c=collect(n.children[0]);b,d=collect(n.children[1]);sign=-1 if n.value=='sub' else 1
        for s,v in b.items():
            a[s]=(a.get(s,0)+sign*v)&MASK
            if not a[s]:del a[s]
        return a,(c+sign*d)&MASK
    return {n.canonical():1},0
def signed(v):return v-(1<<32) if v&(1<<31) else v
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=ROOT/'results/2026-10-14-v6';source=base/'audit/v6-posttest-diagnostics.json';data=json.loads(source.read_text())
features={r['formula']:r for r in json.loads((base/'corpus/test/features.json').read_text())['records']}
records=[]
for r in data['all_models_all_errors_sorted']['mapping_v6'][:10]:
    atoms,constant=collect(parse_formula(r['formula']))
    records.append({k:r[k] for k in ('formula','lut4_count','predicted_lut4','absolute_error_lut4','stratum')}|
       {'frozen_current_v5_normalized_formula':features[r['formula']]['normalized_formula'],
        'diagnostic_modular_affine_atoms':{k:signed(v) for k,v in sorted(atoms.items())},
        'diagnostic_modular_affine_constant_signed':signed(constant)})
result={'scope':'Consumed V6 test diagnosis only; no new performance evidence or frozen changes',
        'source_sha256':sha(Path(__file__)),'diagnostic_input_sha256':sha(source),
        'test_features_sha256':sha(base/'corpus/test/features.json'),'largest_mapping_errors':records,
        'normalizer_source_sha256':{n:sha(ROOT/'isaforge'/n) for n in ('structural_features_v3.py','structural_features_v4.py','structural_features_v5.py')},
        'warning':'Coefficient collector is diagnostic only; no replacement AST is generated and no equivalence proof is claimed.'}
(base/'audit/normalization-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(records,indent=2))
