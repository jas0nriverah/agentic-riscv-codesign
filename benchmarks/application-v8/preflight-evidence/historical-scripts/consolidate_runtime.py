"""Summarize admitted input-only scopes without retrace, labels or predictions."""
from pathlib import Path
import hashlib,json,sys
OUT=Path(__file__).resolve().parent;REPO=OUT.parent/'agentic-riscv-codesign';REF=OUT.parent/'references/tacle-bench';ROOT=REPO/'generated/application-input-feasibility'
sys.path[:0]=[str(REPO)]
from isaforge.features import parse_formula
from isaforge.structural_features_v5 import normalize_formula

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def nodes(n):
 yield n
 for c in n.children:yield from nodes(c)
def constant(n):return not any(x.value in ('in0','in1') for x in nodes(n))
def correlated(n):
 if n.value!='sub':return False
 a,b=n.children
 def masked(q,op,x):
  if q.value not in (op,op+'i'):return False
  l,r=q.children
  return (l==x and constant(r)) or (q.value==op and r==x and constant(l))
 return masked(a,'or',b) or masked(b,'and',a)
paths=[REPO/'results/2026-10-14-v6/corpus/consumed-features.json',REPO/'results/2026-10-14-v6/corpus/calibration/features.json',REPO/'results/2026-10-14-v6/corpus/test/features.json'];consumed=sum((read(p)['records'] for p in paths),[])
exact={parse_formula(r['formula']).canonical() for r in consumed};normal={r['normalized_formula'] for r in consumed}
video=read(OUT/'video-runtime-feasibility.json');old=read(OUT/'runtime-feasibility.json');allroi=read(OUT/'all-roi-companion.json');records={}
for n,r in {**old['records'],**video['records']}.items():
 upstream={s:sha(REF/s) for s in r['upstream_source_sha256']};assert upstream==r['upstream_source_sha256']
 folder=ROOT/n;source=folder/'candidates-all-roi'/(n+'.json');out={'status':r['status'],'all_upstream_bytes_unchanged':True,'upstream_sha256':upstream,'elf_sha256':sha(folder/'O2'/(n+'.elf')),'captured_outputs':r.get('captured_outputs'),'independent_complete_oracle': n=='bitcount','scope':f'Complete declared {n}_main; init/status/outputprobes excluded; allcalledhelpers retained.'}
 if source.exists():
  rows=read(source);features=[]
  for row in rows:
   key=parse_formula(row['formula']).canonical();tree=parse_formula(key);ops=[x.value for x in nodes(tree)];norm=normalize_formula(key)
   features.append({'formula':key,'normalized_v5_formula':norm,'exact_consumed':key in exact,'normalized_v5_consumed':norm in normal,'correlated_bit_pattern':any(correlated(x) for x in nodes(tree)),'mulh_count':ops.count('mulh'),'mulhu_count':ops.count('mulhu'),'mulhsu_count':ops.count('mulhsu')})
  out.update(candidate_count=len(rows),candidate_sha256=sha(source),input_only_formula_screen=features,exact_overlap=sum(x['exact_consumed'] for x in features),normalized_overlap=sum(x['normalized_v5_consumed'] for x in features),new_bit_pattern_formula_count=sum(x['correlated_bit_pattern'] for x in features),high_product_formula_count=sum(bool(x['mulh_count']+x['mulhu_count']+x['mulhsu_count']) for x in features),trace_sha256=sha(folder/(n+'.jsonl.gz')))
  if n in allroi['records']:out.update(retired_instructions=allroi['records'][n]['retired_instructions'],kernel_candidate_count=allroi['records'][n]['kernel_candidate_count'],fusion=allroi['records'][n]['fusion_verification'])
  else:out.update(retired_instructions=r['all-roi']['retired_instructions'],kernel_candidate_count=r['kernel']['candidate_count'],fusion=r['all-roi']['fusion_verification'])
 else:
  partial=folder/(n+'.jsonl.gz.partial');out.update(error=r.get('error'),candidate_count=None,trace_complete=False,partial_trace={'path':str(partial.relative_to(REPO)),'bytes':partial.stat().st_size,'sha256':sha(partial)},failure_interpretation='300s owned-group timer ended incomplete streaming trace; observed PermissionError in cleanup masks original trace exception. No completed trace/summary or candidate pool. No rerun/window shrink. No process remains at final check.')
 records[n]=out
write(OUT/'runtime-summary.json',{'status':'unsealed-input-feasibility-only','source_reference_commit':'c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08','consumed_unique_input_formulas':len(exact),'consumed_input_sha256':{str(p.relative_to(REPO)):sha(p) for p in paths},'records':records,'primary_proposed_family_map':{'bitcount':'bitcount','fft':'fft','ndes':'des','h264_dec':'video'},'related_source_secondary':{'isqrt':'MiBench-basicmath'},'failed_family_member':'mpeg2: no complete pool; explicit admission decision needed before any future seal','no_predictions_fit_target_mapping_seal':True,'script_sha256':sha(__file__)})
for n,x in records.items():print(n,x.get('candidate_count'),x.get('exact_overlap'),x.get('high_product_formula_count'),x.get('new_bit_pattern_formula_count'),flush=True)
