"""Independent frozen inference/calibration audit; never read V5 test labels."""
from pathlib import Path
import hashlib,json,math,shutil,statistics,subprocess,sys,time
from datetime import datetime
import numpy as np

REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
BASE=REPO/'results/2026-10-14-v5'
OUT=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/v5-independent-audit')
sys.path.insert(0,str(REPO))
NAMES={'sog_tuned','original_graph','dual_graph','dual_semantics','masterrtl_fixed','v4_frozen'}
VIEWS=NAMES-{'masterrtl_fixed','v4_frozen'}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def record(r):
 p=(BASE/r['path']).resolve();require(sha(p)==r['sha256'],f'Hash mismatch {p}');return p
def keyed(rows):
 r={(x['benchmark'],x['candidate_id']):x for x in rows}
 require(len(r)==len(rows),'Duplicate identities');return r
def close(a,b,context):
 if isinstance(a,(list,tuple)):
  require(len(a)==len(b),context+' length');[close(x,y,context) for x,y in zip(a,b)]
 elif isinstance(a,dict):
  require(set(a)==set(b),context+' keys');[close(a[k],b[k],context+'.'+k) for k in a]
 elif isinstance(a,(int,float)):
  require(isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10),context+' number')
 else:require(a==b,context+' value')
def copy_entry(source,key,destination):
 target=destination/key
 if not target.exists():shutil.copytree(source/key,target)
 require((target/'features.json').is_file(),'Incomplete copied graph cache')
def absent(*args,**kwargs):raise RuntimeError('Independent audit: Yosys invocation forbidden')

require((BASE/'freeze.json').exists(),'Training has not produced a freeze')
test_files_exist={p:(BASE/p).exists() for p in ('label-release.json','corpus/test/dataset.json','corpus/test/completion.json')}
manifest=read(BASE/'freeze.json');require(set(manifest['models'])==NAMES,'Six comparators required')
freeze_sha=sha(BASE/'freeze.json')
files={str(record(r).relative_to(REPO)):r['sha256'] for r in manifest['files']}
for entry in manifest['models'].values():
 for k in ('artifact','schema','predictions'):
  p=record(entry[k]);files[str(p.relative_to(REPO))]=entry[k]['sha256']
rows=read(BASE/'development-data.json');candidates=read(BASE/'corpus/test/candidates.json')
require(len(rows)==2057 and len(candidates)==256,'Complete declared inputs required')
require(not ({r['formula'] for r in rows}&{r['formula'] for r in candidates}),'Canonical cohort overlap')
indexed=keyed(candidates)
split=read(BASE/'split.json');fit=split['fit_indices'];cal=split['calibration_indices'];mapping=split['component_by_formula']
require(set(fit)|set(cal)==set(range(2057)) and not set(fit)&set(cal),'Partition coverage')
require(len(set(fit))==len(fit) and len(set(cal))==len(cal),'Duplicate partition indices')
groups=np.array([mapping[r['formula']] for r in rows]);strata=np.array([r.get('stratum','workload') for r in rows])
require(not(set(groups[fit])&set(groups[cal])),'Fit/calibration component leakage')
folds=split['fold_validation_indices'];require(len(folds)==5,'Five folds required')
require(sorted(i for ix in folds for i in ix)==sorted(fit),'OOF validation coverage')
for valid in folds:require(not(set(groups[valid])&set(groups[list(set(fit)-set(valid))])),'CV component leakage')
start=read(BASE/'training-start.json');stamp=lambda x:datetime.fromisoformat(x.replace('Z','+00:00'))
require(stamp(read(BASE/'corpus/test/freeze.json')['frozen_at_utc'])<=stamp(start['started_at_utc'])<=stamp(manifest['frozen_at_utc']),'Input/training/bundle chronology')
for entry in manifest['models'].values():require(stamp(start['started_at_utc'])<=stamp(entry['frozen_at_utc'])<=stamp(manifest['frozen_at_utc']),'Model chronology')
for r in start['dataset_sources']:record(r)
features=read(BASE/'development-features.json')['records'];testfeatures=read(BASE/'test-features.json')['records']
require([r['formula'] for r in features]==[r['formula'] for r in rows],'Development feature row order')
require([r['formula'] for r in testfeatures]==[r['formula'] for r in candidates],'Test feature row order')
x=np.array([r['values'] for r in features]);xt=np.array([r['values'] for r in testfeatures])
y=np.array([r['lut4_count'] for r in rows])
from isaforge import area_model_v5 as v5,graph_features_v5 as graph,masterrtl_baseline as master,area_model_v4 as old
from isaforge.v5_corpus import group_components,seal_inputs
seal=seal_inputs(rows,candidates,features,testfeatures)
close(seal,read(BASE/'input-seal.json'),'Input seal reconstruction')
require(group_components(rows,features,include_skeletons=True)==mapping,'Fit grouping reconstruction')
require(group_components(candidates,testfeatures,include_skeletons=True)==read(BASE/'test-clusters.json')['component_by_formula'],'Test grouping reconstruction')
require(x.shape==(2057,len(v5.columns())) and xt.shape==(256,len(v5.columns())),'Feature schema')
require(np.isfinite(x).all() and np.isfinite(xt).all(),'Finite features')
viewsets=[set(v5.view_indices(view)) for view in v5.VIEWS]
require(all(a<b for a,b in zip(viewsets,viewsets[1:])),'Nested feature controls')
# Copy only referenced retained evidence; shared caches are never opened for writes.
cache=OUT/'cache';cache.mkdir(exist_ok=True)
for r in testfeatures:
 copy_entry(REPO/'generated/v5-features/generic',r['original_cache_key'],cache/'v5/generic')
 copy_entry(REPO/'generated/v5-features/generic',r['normalized_cache_key'],cache/'v5/generic')
 copy_entry(REPO/'generated/v5-features/sog',r['sog_cache_key'],cache/'v5/sog')
master_schema=read(record(manifest['models']['masterrtl_fixed']['schema']))
master_keyer=master.SOGExtractor(cache/'master',frozen_tool=master_schema['tool'])
for r in candidates:
 _,key=master_keyer.key(r['formula']);copy_entry(REPO/'generated/v5-features/sog',key,cache/'master')
old_schema=read(record(manifest['models']['v4_frozen']['schema']))
old_keyer=master.SOGExtractor(cache/'v4',frozen_tool=old_schema['frozen_tool'])
from isaforge.structural_features_v4 import normalize_formula
for r in candidates:
 _,key=old_keyer.key(normalize_formula(r['formula']));copy_entry(REPO/'generated/masterrtl-baseline/sog-cache',key,cache/'v4')
# Mandatory misses fail before they can launch a tool or write a cache result.
master.tool_identity=absent;graph.tool_identity=absent
results={};development=read(BASE/'development-evaluation.json')
for name in sorted(NAMES):
 entry=manifest['models'][name];path=record(entry['artifact']);schema=read(record(entry['schema']))
 t=time.perf_counter()
 model=v5.load_model(path,cache/'v5') if name in VIEWS else master.load_model(path,cache/'master') if name=='masterrtl_fixed' else old.load_model(path,cache/'v4')
 loading=time.perf_counter()-t
 expected=read(record(entry['predictions']));target=keyed(expected)
 require(set(target)==set(indexed),'Prediction coverage')
 for k,r in target.items():require(r['formula']==indexed[k]['formula'],'Prediction formula mismatch')
 times=[]
 for run in range(3):
  t=time.perf_counter();actual=model.predict(candidates);times.append(time.perf_counter()-t)
  require(actual==expected,f'Actual artifact predictions differ: {name}')
 poisoned=[{**r,'lut4_count':999999,'carry_count':float('nan'),'correctness_verified':False,'speedup':-1} for r in candidates]
 require(model.predict(poisoned)==expected,'Outcome fields affect inference')
 result={'actual_frozen_predictions_exact_match':True,'outcome_poisoning_invariant':True,'load_seconds':loading,
   'first_copied_cache_batch_seconds':times[0],'warm_copied_cache_seconds':times[1:],
   'median_warm_copied_cache_seconds':statistics.median(times[1:]),'without_yosys_lookup':True,
   'timing_scope':'All graphs were copied before timing; first batch is not cold feature extraction. In-memory full feature+prediction; excludes copying, process startup and JSON IO.'}
 if name in VIEWS:
  selection=development['views'][name];candidatescores=selection['selection_metrics']
  chosen=min(candidatescores,key=lambda c:(candidatescores[c]['macro_stratum_mae_lut4'],c))
  require(chosen==model.configuration==schema['configuration']==selection['selected'],'Selection not fitting-only six-grid minimum')
  require(set(candidatescores)==set(v5.CONFIGS),'Fixed six configurations')
  close(model.estimator.get_params(),schema['fitted_parameters'],'Fitted parameters')
  close(x[fit].min(axis=0).tolist(),model.feature_minimum,'Fit-only feature minima')
  close(x[fit].max(axis=0).tolist(),model.feature_maximum,'Fit-only feature maxima')
  cp=np.array([r['predicted_lut4'] for r in model.predict_features([rows[i] for i in cal],x[cal])])
  maxima=sorted(float(max((y[cal]-cp)[groups[cal]==g])) for g in sorted(set(groups[cal])))
  alpha=model.calibration['alpha'];rank=math.ceil((len(maxima)+1)*(1-alpha))
  margin=None if rank>len(maxima) else max(0.,maxima[rank-1])
  require(rank==132 and len(maxima)==145,'Expected complete calibration groups')
  close(margin,model.calibration['upper_margin_lut4'],'Independent calibration margin')
  close(model.calibration,schema['calibration'],'Calibration metadata')
  close(model.predict_features(candidates,xt),expected,'Frozen feature versus cached graph inference')
  result['calibration']={'group_count':len(maxima),'rank':rank,'independent_upper_margin_lut4':margin,'fit_only_feature_ranges_verified':True}
 results[name]=result
 print(name,json.dumps(result),flush=True)
require(sha(BASE/'freeze.json')==freeze_sha,'Freeze changed during audit')
for path,digest in files.items():require(sha(REPO/path)==digest,'Frozen file changed during audit')
commit=subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,capture_output=True,text=True,check=True).stdout.strip()
committed=True
for path,digest in files.items():
 p=subprocess.run(['git','show',f'{commit}:{path}'],cwd=REPO,capture_output=True)
 if p.returncode or hashlib.sha256(p.stdout).hexdigest()!=digest:committed=False;break
report={'status':'passed','audit_source_sha256':sha(Path(__file__)),'freeze_sha256':freeze_sha,
 'git_revision':commit,'all_frozen_files_match_current_commit':committed,'frozen_file_count':len(files),
 'test_labels_read':False,'test_label_files_existence_only':test_files_exist,'model_fits_performed':False,'shared_cache_modified':False,
 'counts':{'development':2057,'test':256,'fit':len(fit),'calibration':len(cal),'calibration_groups':len(set(groups[cal]))},
 'models':results,'limits':['No V5 test labels read; no area accuracy, raw target count, or application result audited in this phase.',
 'All inference timings use copied populated caches; no cold extraction or cost-savings claim.',
 'Calibration coverage still assumes exchangeable complete groups and is not guaranteed on new compositions or applications.',
 'Hashes and commits establish retained consistency, not unrecorded historical access.']}
(OUT/'freeze-only.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print('FREEZE-ONLY INDEPENDENT AUDIT PASSED',flush=True)
