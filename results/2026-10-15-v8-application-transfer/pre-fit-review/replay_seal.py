"""Independent flat/member/copy audit of V8 portable input materialization only."""
from pathlib import Path,PurePosixPath
import argparse,collections,hashlib,json,math,sys,tarfile,time,zipfile

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,m):
 if not v:raise AssertionError(m)
def run(repo,seal_root,out):
 sys.path.insert(0,str(repo))
 from isaforge import area_model_v8 as v8
 start=time.perf_counter();seal=read(seal_root/'input-seal.json');prep=read(seal_root/'training/preparation.json')
 before={str(seal_root/n):sha(seal_root/n) for n in ('input-seal.json','training/preparation.json')}
 flat={};counts=collections.Counter()
 for record,base in [(seal,seal_root),(prep,seal_root/'training')]:
  for e in record['files']:
   p=(base/e['path']).resolve();need(p.is_relative_to(repo),'Nonportable flat reference');need(p.is_file() and sha(p)==e['sha256'],'Flat SHA mismatch: '+str(p))
   need(p not in flat or flat[p]==e['sha256'],'Conflicting flat SHA');flat[p]=e['sha256']
 need(seal['status']=='sealed-inputs-only' and seal['new_estimator_fits']==0 and seal['fresh_labels_read'] is False and seal['model_predictions_read'] is False,'Input-only stage')
 need(seal['runtime_source_sha256']==prep['runtime_source_sha256']==v8.source_hashes(),'Current recipe runtime identity')
 need(prep['fixed_parameters']==v8.FIXED_PARAMETERS and prep['training_formula_count']==1665 and prep['full_feature_count']==455 and prep['new_estimator_fits']==0,'Fixed1665/ET300seed1401 recipe')
 must=[repo/'scripts/train_v8_applications.py',repo/'scripts/infer_v8_applications.py',repo/'scripts/evaluate_v8_applications.py',repo/'scripts/measure_v8_applications.py',repo/'scripts/seal_v8_application_inputs.py',repo/'scripts/archive_v8_feature_inputs.py',repo/'scripts/train_v6.py',repo/'scripts/measure_v6.py',repo/'scripts/evaluate_v6.py',repo/'docs/v8-application-pilot-protocol.md',repo/'tests/test_semantic_features_v7_independent.py',repo/'benchmarks/application-v8/evidence/feature-audit/input-audit.json',repo/'benchmarks/application-v8/evidence/feature-audit/replay_inputs.py']
 need(all(p in flat for p in must),'Required source/audit missing from flat release')
 need(all(repo/'isaforge'/n in flat for n in v8.source_hashes()),'Feature runtime source missing')
 indexes={};byte_inventory=collections.defaultdict(list);originalbytes={}
 for e in seal['archive_manifests']:
  p=(seal_root/e['path']).resolve();need(sha(p)==e['sha256'] and p in flat,'Archive index flat binding')
  idx=read(p);a=(p.parent/idx['archive']['path']).resolve();s=(p.parent/idx['source_manifest']['path']).resolve()
  need(a in flat and s in flat and sha(a)==idx['archive']['sha256'] and sha(s)==idx['source_manifest']['sha256'],'Archive/source manifest binding')
  entries={x['path']:x for x in idx['files']};need(len(entries)==len(idx['files'])>0,'Unique archive inventory')
  seen=set()
  def check(n,b):
   pp=PurePosixPath(n);need(not pp.is_absolute() and '..' not in pp.parts and '\\' not in n and str(pp)==n,'Unsafe archive member');need(n not in seen and n in entries,'Duplicate/unlisted member');seen.add(n);en=entries[n];need(len(b)==en['bytes'] and hashlib.sha256(b).hexdigest()==en['sha256'],'Member bytes mismatch');byte_inventory[(en['sha256'],en['bytes'])].append((str(p),n))
   if p.stem=='prelabel':originalbytes[n]=b
  if zipfile.is_zipfile(a):
   with zipfile.ZipFile(a) as z:
    for info in z.infolist():
     need(not info.is_dir() and ((info.external_attr>>16)&0o170000)!=0o120000,'Special ZIP member');check(info.filename,z.read(info))
  else:
   with tarfile.open(a,'r:*') as tar:
    for info in tar:
     need(info.isfile(),'Special TAR member');check(info.name,tar.extractfile(info).read())
  need(seen==set(entries),'Archive coverage mismatch');indexes[p.stem]={'members':len(entries),'archive_sha256':sha(a),'index_sha256':sha(p)}
 need(set(indexes)=={'v7','runtime','prelabel','features'},'Exactly4 archive indexes')
 copies={}
 for archived,local in [('application/rows.json','rows.json'),('application/features.json','features.json'),('application/programs.json','programs.json'),('application/novelty.json','novelty.json'),('training/training-data.json','training/training-data.json')]:
  need(originalbytes[archived]==(seal_root/local).read_bytes(),'Original prepared bytes changed: '+local);copies[local]=sha(seal_root/local)
 originalprep=json.loads(originalbytes['training/preparation.json']);need(hashlib.sha256(originalbytes['training/preparation.json']).hexdigest()==prep['original_preparation_sha256'],'Original training preparation identity')
 need(prep['runtime_source_sha256']==originalprep['runtime_source_sha256'] and prep['training_data']['sha256']==originalprep['training_data']['sha256'],'Training recipe unchanged')
 prior=repo.parent
 for label,directory in [('application',prior/'v8-application-inputs-attempt-0000'),('training',prior/'v8-training-preparation-attempt-0001'),('consumed',prior/'v8-consumed-inputs-attempt-0002')]:
  for p in directory.rglob('*.json'):need(originalbytes[label+'/'+p.relative_to(directory).as_posix()]==p.read_bytes(),'Exact original working attempt preserved')
 cov=read(seal_root/'materialization-coverage.json');need(cov['uncovered_inputs']==0,'Uncovered materialization inputs')
 exceptions=[]
 for row in cov['records']:
  k=(row['sha256'],row['bytes']);p=Path(row['original_path']);need(p.is_file() and sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],'Original dropped input changed')
  if row['status']=='exact-bytes-in-published-archive':
   need(k in byte_inventory and row['archive_matches'],'Missing exact archived bytes')
   for m in row['archive_matches']:need((m['archive_index'],m['member']) in byte_inventory[k],'False coverage match')
  else:
   need(row['status']=='explicit-nondistributed-dependency-or-failed-partial' and row['exception']['sha256']==row['sha256'],'Unknown omission status');exceptions.append(row)
 need(len(exceptions)==4 and sum('mpeg2' in e['original_path'] for e in exceptions)==1 and sum('/toolchains/' in e['original_path'] for e in exceptions)==3,'Only4 declared exception types')
 # Reconstruct dropped set independently from the exact archived original files.
 verified={}
 for label,n in [('application','input-preparation.json'),('training','preparation.json'),('consumed','start.json')]:
  base={'application':prior/'v8-application-inputs-attempt-0000','training':prior/'v8-training-preparation-attempt-0001','consumed':prior/'v8-consumed-inputs-attempt-0002'}[label]
  original=json.loads(originalbytes[label+'/'+n])
  for e in original['files']:verified[(base/e['path']).resolve()]=e['sha256']
 dropped={p for p in verified if p not in flat};need(dropped=={Path(r['original_path']) for r in cov['records']},'Coverage ledger does not match all dropped flat inputs')
 review=read(seal_root/'independent-input-review.json');need(review['status']=='approved-for-input-seal','Independent input review gate')
 for key,member in [('input_preparation_sha256','application/input-preparation.json'),('training_preparation_sha256','training/preparation.json'),('consumed_completion_sha256','consumed/completion.json')]:need(review[key]==hashlib.sha256(originalbytes[member]).hexdigest(),'Independent review original evidence binding')
 need(review['runtime_audit_sha256']==sha(repo/'benchmarks/application-v8/evidence/runtime-replay.json'),'Runtime review identity')
 for e in review['published_audit_files']:
  p=repo/e['path'];need(p in flat and sha(p)==e['sha256'] and p.stat().st_size==e['bytes'],'Published independent proof audit not bound')
 need(not any((seal_root/n).exists() for n in ('training-start.json','point-freeze.json','label-release.json','measurements','models','point-predictions')),'Unexpected fits/points/labels in input-only seal')
 for p,d in before.items():need(sha(p)==d,'Seal changed during audit')
 report={'schema':'isaforge-v8-independent-portable-input-seal-audit-v1','status':'pass','input_seal_sha256':sha(seal_root/'input-seal.json'),'materialized_training_preparation_sha256':sha(seal_root/'training/preparation.json'),'training_runner_sha256':sha(repo/'scripts/train_v8_applications.py'),'seal_source_sha256':sha(repo/'scripts/seal_v8_application_inputs.py'),'collector_source_sha256':sha(repo/'scripts/measure_v8_applications.py'),'audit_source_sha256':sha(__file__),'flat_unique_files_verified':len(flat),'archives':indexes,'exact_original_copies':copies,'dropped_bindings':len(dropped),'exact_archive_covered':len(dropped)-4,'explicit_omission_count':len(exceptions),'explicit_omissions':[{'original_path':r['original_path'],'sha256':r['sha256'],'bytes':r['bytes']} for r in exceptions],'first_native_features_proofs_fallback_byte_identical':True,'original1665_training_data_byte_identical':True,'current_named455_recipe_and_required_sources_bound':True,'new_fits_model_predictions_or_labels':0,'scope':'Approves exact portable input/source materialization for parent commit and subsequent separately reviewed fixed-two-fit gate. Does not authorize target-label release; no fit/model prediction/normalization rerun performed.','elapsed_seconds':time.perf_counter()-start}
 out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();
 for n in ('repo','root','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();run(a.repo.resolve(),a.root.resolve(),a.output.resolve())
