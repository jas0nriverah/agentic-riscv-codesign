"""Read-only fixed48 input audit; never open new target labels or run native tools."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,shutil,sys,zipfile
repo=(Path(__file__).resolve().parent.parent/'agentic-riscv-codesign').resolve();sys.path.insert(0,str(repo))
from isaforge.features import parse_formula
from isaforge.rtl import generate_rtl
from isaforge.v5_corpus import equivalence_key
root=repo/'results/2026-10-15-v9-coverage-development';v8=repo/'results/2026-10-15-v8-application-transfer'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(v,m):
 if not v:raise AssertionError(m)
def canon(s):return parse_formula(s).canonical()
def forms(r):
 result={canon(r['formula'])}
 if 'normalized_formula' in r:result.add(canon(r['normalized_formula']))
 if 'v7_modes' in r:
  for mode in ['bit','affine','combined']:
   value=r['v7_modes'].get(mode,{})
   if value.get('metadata',{}).get('status')=='accepted':result.add(canon(value['normalized_formula']))
 elif 'v7_combined_normalized_formula' in r:result.add(canon(r['v7_combined_normalized_formula']))
 return result
manifest=read(root/'preparation.json');recipe=read(root/'recipe.json');candidates=read(root/'candidates.json');before={}
need(manifest['status']=='prepared-inputs-only' and manifest['new_labels_read'] is False and manifest['model_fits']==0,'Input-only contract differs')
for e in manifest['files']:
 p=(root/e['path']).resolve();need(p.is_relative_to(repo) and sha(p)==e['sha256'],'Bound input/source mismatch');need(p not in before,'Duplicate binding');before[p]=e['sha256']
for key in ['candidates','recipe']:need(sha(root/manifest[key]['path'])==manifest[key]['sha256'],'Named artifact digest mismatch')
expected=[]
for c in sorted(x*y for x in [11,85,341,511] for y in [1,4]):
 expected.extend([f'mul(in0,addi(0,{c}))',f'add(mul(in0,addi(0,{c})),in1)',f'mul(sub(in0,in1),addi(0,{c}))',f'mul(sub(andi(in0,63),in1),addi(0,{c}))'])
for shift in [1,2,3,4,8,12,24,30]:
 for op in ['add','sub']:expected.append(f'sub(srai({op}(in0,in1),{shift}),srai(in1,31))')
need([r['formula'] for r in candidates]==expected and len(set(expected))==48,'Fixed48 candidate pool differs')
rtls=[]
for row in candidates:
 f=row['formula'];need(canon(f)==f,'Noncanonical candidate');need(row['candidate_id']=='v9-coverage:'+hashlib.sha256(f.encode()).hexdigest(),'Candidate ID mismatch')
 pending=[parse_formula(f)];count=0
 while pending:
  n=pending.pop();pending.extend(n.children)
  if n.children:
   count+=1
   if n.value in ['addi','andi']:need(-2048<=n.children[-1].value<=2047,'Nonencodable signed12 immediate')
   if n.value in ['srai','srli','slli']:need(0<=n.children[-1].value<=31,'Nonencodable shift immediate')
 need(row['operation_count']==count and 2<=count<=4,'Candidate operation count mismatch')
 rtls.append({'formula':f,'rtl_sha256':hashlib.sha256(generate_rtl(f).encode()).hexdigest()})
index=read(v8/'archive-indexes/prelabel.json');archive=v8/'archive-indexes'/index['archive']['path'];need(sha(archive)==index['archive']['sha256'],'Historical archive SHA mismatch')
entries={e['path']:e for e in index['files']}
with zipfile.ZipFile(archive) as z:
 need(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(entries),'Historical archive membership mismatch')
 for info in z.infolist():
  value=z.read(info);e=entries[info.filename];need(hashlib.sha256(value).hexdigest()==e['sha256'] and len(value)==e.get('bytes',e.get('size')),'Historical archive bytes mismatch')
 base=json.loads(z.read('consumed/features.json'));need(len(base['records'])==2764,'Prior2764 registry mismatch')
fresh=read(v8/'features.json');need(len(fresh['records'])==146,'V8 original union mismatch')
union=defaultdict(set);sources=defaultdict(set)
for name,records in [('pre_v8_consumed',base['records']),('v8_consumed',fresh['records'])]:
 for row in records:
  need(canon(row['formula'])==row['formula'],'Noncanonical consumed original')
  union[row['formula']].update(forms(row));sources[row['formula']].add(name)
ledger=read(root/'consumed-input-ledger.json')
need(ledger['records']==[{'formula':f,'accepted_forms':sorted(union[f]),'sources':sorted(sources[f])} for f in sorted(union)],'Complete consumed identity ledger mismatch')
need(len(union)==2881 and sum(len(v)==2 for v in sources.values())==29,'Consumed source union/count mismatch')
identities=read(root/'identity-analysis.json');need([r['formula'] for r in identities]==expected,'Identity ledger candidate coverage mismatch')
status=Counter(v['metadata']['status'] for r in identities for v in r['v7_modes'].values());need(status=={'accepted':144},'Unexpected first identity proof status')
prior_forms=set().union(*union.values());prior_commutative={equivalence_key(f) for f in prior_forms};seen=set();seen_comm=set()
for row in identities:
 fs=forms(row);comm={equivalence_key(f) for f in fs}
 need(row['formula'] not in union and not (fs&prior_forms) and not (comm&prior_commutative),'A declared consumed identity match was missed')
 need(not(fs&seen) and not(comm&seen_comm),'A within-proposal identity alias was missed');seen.update(fs);seen_comm.update(comm)
duplicates=read(root/'duplicate-analysis.json')
need(duplicates['canonical_original_seen_count']==duplicates['declared_functional_alias_count']==duplicates['within_proposal_functional_alias_pairs']==0,'Duplicate report summary differs')
need(recipe['measurement']=={'workers':2,'verification_seed':2026101519,'vectors_per_formula':2148,'original_rtl_only':True,'new_measurement_count':48},'Fixed measurement recipe differs')
original=read(v8/'training/training-data.json');need(recipe['frozen_tool']==original['frozen_tool'],'Original frozen tool identity mismatch')
tool=shutil.which('yosys');need(tool is not None and sha(Path(tool))==recipe['frozen_tool']['executable_sha256'],'Current Yosys executable digest mismatch')
need(not any((root/n).exists() for n in ['label-release.json','measurements','fit-attempt.json','training-start.json','evaluation.json']),'New target/model stage already exists')
need(not (repo/'generated/v9-coverage-measurements').exists(),'New measurement scratch already exists')
need(all(sha(p)==h for p,h in before.items()),'Prepared bytes changed during review')
result={'schema':'isaforge-v9-independent-coverage-input-review-v1','status':'pass','decision':'GO for parent commit and separately bound fixed48 measurement release','preparation_sha256':sha(root/'preparation.json'),'recipe_sha256':sha(root/'recipe.json'),'candidates_sha256':sha(root/'candidates.json'),'flat_files_verified':len(before),'fixed_originals':48,'original_training_rows':1665,'consumed_unique_originals':2881,'pre_v8_consumed_originals':2764,'v8_originals':146,'shared_originals':29,'accepted_new_identity_modes':144,'canonical_original_matches':0,'declared_functional_aliases':0,'within_proposal_alias_pairs':0,'all_immediates_encodable':True,'frozen_tool':recipe['frozen_tool'],'current_yosys_executable_hash_matches':True,'new_targets_fits_or_native_calls_by_review':0,'collector_source_sha256':sha(repo/'scripts/measure_v9_coverage.py'),'trainer_source_sha256':sha(repo/'scripts/train_v9_coverage.py'),'rtl_identities':rtls,'scope':'Input-only review. Complete declared consumed registry and saved accepted V5/V7 identities plus frozen commutative equivalence; skeletons are diagnostics, no exhaustive functional novelty claim. All48 retained; no outcome-aware replacement or fresh-confirmation claim.'}
out=Path(__file__).with_name('coverage-input-review.json');need(not out.exists(),'Report already exists');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rtl_identities'},indent=2))
