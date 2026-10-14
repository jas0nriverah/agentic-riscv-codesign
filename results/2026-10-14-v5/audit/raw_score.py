"""Independent V5 raw-cell and score recount. Requires complete released labels."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib,json,math,statistics,subprocess,sys
import numpy as np
REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
BASE=REPO/'results/2026-10-14-v5';OUT=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/v5-independent-audit')
sys.path.insert(0,str(REPO))
from isaforge.rtl import generate_rtl
CAPS=(16,32,64,128,256);SCOPES=('known_families','unseen_compositions');VIEWS={'sog_tuned','original_graph','dual_graph','dual_semantics'}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def close(a,b,context):
 if isinstance(a,dict):
  require(set(a)==set(b),context+' fields');[close(a[k],b[k],context+'.'+k) for k in a]
 elif isinstance(a,list):
  require(len(a)==len(b),context+' length');[close(x,y,context) for x,y in zip(a,b)]
 elif isinstance(a,(int,float)):
  require(isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10),f'{context}: {a} != {b}')
 else:require(a==b,context+' value')
def keyed(rows):
 d={(r['benchmark'],r['candidate_id']):r for r in rows};require(len(d)==len(rows),'Duplicate identity');return d
def check(r):
 p=(BASE/r['path']).resolve();require(sha(p)==r['sha256'],'Frozen hash changed: '+str(p));return p
def divide(a,b):return a/b if b else None
def metrics(y,p):
 require(len(y)==len(p)>0,'Complete metric arrays required')
 errors=[abs(b-a) for a,b in zip(y,p)];ape=[100*e/a for a,e in zip(y,errors) if a>0];zero=[e for a,e in zip(y,errors) if a==0]
 confusion={}
 for cap in CAPS:
  truth=[a<=cap for a in y];guess=[b<=cap for b in p]
  fa=sum(g and not t for g,t in zip(guess,truth));fr=sum(not g and t for g,t in zip(guess,truth));feasible=sum(truth);infeasible=len(y)-feasible;proposed=sum(guess)
  confusion[str(cap)]={'true_accept_count':sum(g and t for g,t in zip(guess,truth)),'true_reject_count':sum(not g and not t for g,t in zip(guess,truth)),
   'false_accept_count':fa,'false_reject_count':fr,'true_feasible_count':feasible,'true_infeasible_count':infeasible,'predicted_feasible_count':proposed,
   'false_accept_rate_among_true_infeasible':divide(fa,infeasible),'false_reject_rate_among_true_feasible':divide(fr,feasible),'infeasible_fraction_among_predicted_feasible':divide(fa,proposed)}
 return {'sample_count':len(y),'mae_lut4':statistics.mean(errors),'rmsle':math.sqrt(statistics.mean((math.log1p(b)-math.log1p(a))**2 for a,b in zip(y,p))),
  'positive_mape_percent':statistics.mean(ape) if ape else None,'positive_median_ape_percent':statistics.median(ape) if ape else None,
  'positive_count':len(ape),'zero_count':len(zero),'zero_target_mae_lut4':statistics.mean(zero) if zero else None,'cap_feasibility':confusion,
  'signed_bias_lut4':statistics.mean(b-a for a,b in zip(y,p)), 'absolute_error_quantiles':{str(q):float(np.quantile(errors,q)) for q in (.5,.9,.95,.99)},
  'maximum_underprediction_lut4':max(0.,max(a-b for a,b in zip(y,p)))}
def bootstrap(d,s,c):
 names=sorted(set(s));clusters=sorted(set(c));cell_sums=[];cell_counts=[]
 for group in clusters:
  cell_sums.append([sum(d[i] for i in range(len(d)) if c[i]==group and s[i]==stratum) for stratum in names])
  cell_counts.append([sum(c[i]==group and s[i]==stratum for i in range(len(d))) for stratum in names])
 sums=np.array(cell_sums);counts=np.array(cell_counts);rng=np.random.default_rng(2026101418);samples=[];attempts=0
 while len(samples)<10000 and attempts<1000000:
  draws=rng.integers(0,len(clusters),size=(min(512,10000-len(samples),1000000-attempts),len(clusters)))
  for draw in draws:
   weights=np.bincount(draw,minlength=len(clusters));denom=weights@counts
   if np.all(denom>0):samples.append(float(np.mean((weights@sums)/denom)))
  attempts+=len(draws)
 require(len(samples)==10000,'Bootstrap valid draw limit exceeded')
 return {'macro_stratum_mae_difference_lut4':statistics.mean(statistics.mean(d[i] for i in range(len(d)) if s[i]==stratum) for stratum in names),
  'descriptive_cluster_bootstrap_95_interval':np.quantile(samples,[.025,.975]).tolist(),'replicates':10000,'cluster_count':len(clusters),'attempts':attempts,
  'empty_stratum_draws_rejected':attempts-10000,'seed':2026101418,'cluster_sizes':{group:sum(x==group for x in c) for group in clusters},
  'scope':'post-freeze descriptive cluster resampling, conditional on curated strata','v5_smaller_absolute_error_count':sum(v<0 for v in d),
  'equal_absolute_error_count':sum(v==0 for v in d),'v5_larger_absolute_error_count':sum(v>0 for v in d)}
manifest=read(BASE/'freeze.json');freeze_sha=sha(BASE/'freeze.json');release=read(BASE/'label-release.json')
stamp=lambda x:datetime.fromisoformat(x.replace('Z','+00:00'))
require(release['freeze_sha256']==freeze_sha and release['candidate_sha256']==manifest['test_candidate_sha256'],'Release hash mismatch')
require(stamp(release['released_at_utc'])>stamp(manifest['frozen_at_utc']),'Release predates freeze')
completion=read(BASE/'corpus/test/completion.json')
require(completion['complete'] is True and completion['measured_count']==256 and not completion['failures'],'Test collection incomplete; no audit label reads authorized')
require(completion['release']==release and completion['collector_sha256']==sha(REPO/'scripts/measure_v5.py'),'Completion lineage mismatch')
for r in manifest['files']:check(r)
for e in manifest['models'].values():
 for k in ('artifact','schema','predictions'):check(e[k])
raw={}
for cohort,count in [('development',512),('test',256)]:
 base=BASE/'corpus'/cohort;gen=REPO/'generated/v5-corpus'/cohort;done=read(base/'completion.json')
 require(done['complete'] is True and done['measured_count']==count and not done['failures'],'Incomplete raw cohort')
 for name,key in [('candidates.json','candidate_sha256'),('dataset.json','dataset_sha256'),('verification.json','verification_sha256')]:require(sha(base/name)==done[key],'Completion digest mismatch')
 declared=read(base/'candidates.json');labeled=read(base/'dataset.json');require(len(declared)==len(labeled)==count,'Raw cohort count mismatch')
 labels=keyed(labeled);require(set(labels)==set(keyed(declared)),'Raw cohort identities')
 sums=Counter();comparisons=0
 for i,batch in enumerate(read(base/'verification.json')):
  folder=gen/'verification'/f'batch-{i*128:04d}'
  require(batch['verified'] is True and batch['formula_count']==128 and batch['total_comparisons']==128*batch['vectors_per_formula'],'Verification incomplete')
  require(sha(folder/'verification.v')==batch['rtl_sha256'] and sha(folder/'vectors.txt')==batch['vectors_sha256'],'Retained verification hash')
  require(sha(REPO/'isaforge/v4_validation.py')==batch['v4_validation_override_sha256'],'Verification wrapper source hash')
  if batch.get('signed_overflow_workaround_applied'):
   require(sha(folder/'yosys-boundary-cross-check/eval.log')==batch['independent_yosys_log_sha256'],'Independent incident log hash')
  comparisons+=batch['total_comparisons']
 for candidate in declared:
  row=labels[(candidate['benchmark'],candidate['candidate_id'])];require(all(row[k]==v for k,v in candidate.items()),'Labeled candidate input changed')
  require(row['correctness_verified'] is True and row['measurement_source']=='rtl_synthesis','Unverified/nonhardware label')
  folder=gen/'circuits'/hashlib.sha256(row['formula'].encode()).hexdigest()[:20];m=read(folder/'metrics.json');netlist=read(folder/'ice40-netlist.json')
  cells=Counter(cell['type'] for module in netlist['modules'].values() for cell in module.get('cells',{}).values())
  require(row['lut4_count']==m['ice40_lut4_count']==cells['SB_LUT4'],'Raw LUT4 mismatch')
  require(row['carry_count']==m['ice40_carry_count']==cells['SB_CARRY'],'Raw carry mismatch')
  require(m['formula']==row['formula'] and row['synthesis_tool']==m['tool']==done['tool'],'Original formula/tool mismatch')
  require(row['rtl_sha256']==m['rtl_sha256']==sha(folder/'candidate.v')==hashlib.sha256(generate_rtl(row['formula']).encode()).hexdigest(),'Original RTL mismatch')
  for filename,key in [('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]:require(sha(folder/filename)==m[key],'Raw target file digest mismatch')
  require(Counter(cell['type'] for cell in netlist['modules']['candidate'].get('cells',{}).values())==Counter(m['ice40_cell_types']),'Mapped candidate cell type recount mismatch')
  sums.update(cells)
 raw[cohort]={'circuits':count,'raw_lut4_sum':sums['SB_LUT4'],'raw_carry_sum':sums['SB_CARRY'],'verification_comparisons':comparisons,'all_target_resource_counts_and_hashes_verified':True}
 print('raw',cohort,json.dumps(raw[cohort]),flush=True)
if '--raw-only' in sys.argv:
 commit=subprocess.check_output(['git','rev-parse','fc338e8'],cwd=REPO,text=True).strip()
 all_records=list(manifest['files'])+[r for e in manifest['models'].values() for r in (e['artifact'],e['schema'],e['predictions'])]
 for r in all_records:
  path=check(r);data=subprocess.check_output(['git','show',f'{commit}:{path.relative_to(REPO)}'],cwd=REPO)
  require(hashlib.sha256(data).hexdigest()==r['sha256'],'Freeze commit mismatch')
 require(sha(BASE/'freeze.json')==freeze_sha,'Freeze changed during raw audit')
 report={'status':'passed','audit_source_sha256':sha(Path(__file__)),'frozen_commit':commit,'freeze_sha256':freeze_sha,
  'raw':raw,'frozen_records_verified_against_commit':len(all_records),'no_evaluator_imports':True,
  'no_model_fitting_or_loading':True,'no_new_measurement':True,
  'limits':['Resource labels independently recounted; semantic verification is retained sampled evidence, not a new formal proof.',
  'No score/CI recomputation in this raw-only pass; a separate statistical audit owns those checks.']}
 (OUT/'raw-provenance.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 print('INDEPENDENT RAW/PROVENANCE AUDIT PASSED',flush=True)
 raise SystemExit(0)
scored=read(BASE/'evaluation.json');require(scored['freeze_sha256']==freeze_sha,'Score freeze mismatch')
declared=read(BASE/'corpus/test/candidates.json');truth=keyed(read(BASE/'corpus/test/dataset.json'));clusters=read(BASE/'test-clusters.json')
y=[truth[(r['benchmark'],r['candidate_id'])]['lut4_count'] for r in declared];s=[r['stratum'] for r in declared];scopes=[r['evaluation_scope'] for r in declared];c=[clusters['component_by_formula'][r['formula']] for r in declared]
require(len(y)==256 and len(set(s))==8,'Declared full endpoint')
models={};predictions={}
for name,entry in sorted(manifest['models'].items()):
 rows=keyed(read(check(entry['predictions'])));require(set(rows)==set(truth),'Prediction coverage')
 p=[rows[(r['benchmark'],r['candidate_id'])]['predicted_lut4'] for r in declared];predictions[name]=p
 require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in p),'Invalid prediction')
 model={'all':metrics(y,p),'by_scope':{}}
 close(model['all'],scored['models'][name]['all'],name+'.all')
 reported=keyed(scored['models'][name]['candidate_errors']);require(set(reported)==set(truth),'Complete candidate error coverage')
 for i,r in enumerate(declared):
  er=reported[(r['benchmark'],r['candidate_id'])];require(all(er[k]==v for k,v in r.items()),'Candidate error input mismatch')
  for field,value in [('lut4_count',y[i]),('predicted_lut4',p[i]),('signed_error_lut4',p[i]-y[i]),('absolute_error_lut4',abs(p[i]-y[i]))]:close(value,er[field],name+'.error.'+field)
 for scope in SCOPES:
  ix=[i for i in range(256) if scopes[i]==scope];require(len(ix)==128,'Scope completeness')
  m=metrics([y[i] for i in ix],[p[i] for i in ix]);m['by_stratum']={}
  for stratum in sorted(set(s)):
   sel=[i for i in ix if s[i]==stratum];require(len(sel)==16,'Balanced stratum completeness')
   m['by_stratum'][stratum]=metrics([y[i] for i in sel],[p[i] for i in sel])
  m['macro_stratum_mae_lut4']=statistics.mean(t['mae_lut4'] for t in m['by_stratum'].values())
  if name in VIEWS:
   bound=[math.inf if rows[(r['benchmark'],r['candidate_id'])]['upper_lut4'] is None else rows[(r['benchmark'],r['candidate_id'])]['upper_lut4'] for r in declared]
   covered=[a<=b for a,b in zip(y,bound)];groups=sorted(set(c[i] for i in ix));finite=[math.isfinite(bound[i]) for i in ix]
   m['upper_bound']={'candidate_coverage':statistics.mean(covered[i] for i in ix),'whole_component_coverage':statistics.mean(all(covered[i] for i in ix if c[i]==g) for g in groups),
    'finite_fraction':statistics.mean(finite),'mean_upper_minus_target_lut4':statistics.mean(bound[i]-y[i] for i in ix) if all(finite) else None,
    'assumption':'complete-group exchangeability; unestablished under composition shift'}
   for stratum in sorted(set(s)):
    sel=[i for i in ix if s[i]==stratum];gs=set(c[i] for i in sel)
    m['by_stratum'][stratum]['upper_bound_candidate_coverage']=statistics.mean(covered[i] for i in sel)
    m['by_stratum'][stratum]['upper_bound_whole_component_coverage']=statistics.mean(all(covered[i] for i in sel if c[i]==g) for g in gs)
  close(m,scored['models'][name]['by_scope'][scope],name+'.'+scope);model['by_scope'][scope]=m
 models[name]=model
 print('metrics',name,{scope:model['by_scope'][scope]['macro_stratum_mae_lut4'] for scope in SCOPES},flush=True)
paired={}
for scope in SCOPES:
 ix=[i for i in range(256) if scopes[i]==scope];paired[scope]={}
 for name,p in sorted(predictions.items()):
  if name=='dual_semantics':continue
  d=[abs(predictions['dual_semantics'][i]-y[i])-abs(p[i]-y[i]) for i in ix]
  b=bootstrap(d,[s[i] for i in ix],[c[i] for i in ix]);close(b,scored['paired_comparisons'][scope][name],scope+'.'+name+'.bootstrap');paired[scope][name]=b
  print('paired',scope,name,b['macro_stratum_mae_difference_lut4'],b['descriptive_cluster_bootstrap_95_interval'],flush=True)
require(sha(BASE/'freeze.json')==freeze_sha,'Freeze changed during score audit')
for r in manifest['files']:check(r)
commit=subprocess.check_output(['git','rev-parse','fc338e8'],cwd=REPO,text=True).strip()
for r in manifest['files']:
 path=check(r);data=subprocess.check_output(['git','show',f'{commit}:{path.relative_to(REPO)}'],cwd=REPO)
 require(hashlib.sha256(data).hexdigest()==r['sha256'],'Source freeze commit mismatch')
report={'status':'passed','audit_source_sha256':sha(Path(__file__)),'frozen_commit':commit,'freeze_sha256':freeze_sha,'evaluation_sha256':sha(BASE/'evaluation.json'),
 'raw':raw,'models':models,'paired_comparisons':paired,'candidate_error_count_verified':1536,'bootstrap_results_verified':10,
 'no_evaluator_imports':True,'no_model_fitting_or_loading':True,'no_new_measurement':True,
 'limits':['Recorded verification is sampled, not formal equivalence; hashes/recounts do not prove absence of prior access.',
 'Synthetic isolated LUT4 scopes do not establish application, acquisition, CPU performance or energy benefits.',
 'Cluster bootstrap and interval coverage are descriptive on curated groups; composition/application exchangeability is not established.']}
(OUT/'raw-score.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print('INDEPENDENT RAW/SCORE AUDIT PASSED',flush=True)
