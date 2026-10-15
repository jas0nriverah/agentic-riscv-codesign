"""Independent input-only V8 snapshot audit; never reruns timed normalization."""
from pathlib import Path
import argparse,collections,hashlib,importlib.util,itertools,json,math,random,struct,subprocess,sys,time,zipfile

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(value,message):
 if not value:raise AssertionError(message)
def check_files(record,base):
 for entry in record['files']:
  p=(base/entry['path']).resolve();need(sha(p)==entry['sha256'],'Manifest file SHA changed: '+str(p))
def run(repo,prepared,training,consumed,out):
 sys.path[:0]=[str(repo),str(repo/'scripts')]
 import numpy as np,z3
 from isaforge import area_model_v6 as v6,area_model_v8 as v8,structural_features_v5 as legacy
 from isaforge.structural_features_v4 import normalize_formula as v4normal
 spec=importlib.util.spec_from_file_location('independent_v7_helpers',repo/'tests/test_semantic_features_v7_independent.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 began=time.perf_counter(); source_files=[Path(__file__),repo/'tests/test_semantic_features_v7_independent.py',repo/'isaforge/v8_application_corpus.py',repo/'scripts/prepare_v8_applications.py',repo/'scripts/prepare_v8_training.py',repo/'scripts/prepare_v8_consumed.py']
 sources={str(p):sha(p) for p in source_files}
 inp=read(prepared/'input-preparation.json');start=read(prepared/'input-start.json');train=read(training/'preparation.json');cstart=read(consumed/'start.json');complete=read(consumed/'completion.json')
 for m,b in [(inp,prepared),(start,prepared),(train,training),(cstart,consumed)]:check_files(m,b)
 for entry in (complete['start'],complete['features']):need(sha(consumed/entry['path'])==entry['sha256'],'Consumed completion binding')
 need(inp['runtime_source_sha256']==start['runtime_source_sha256']==train['runtime_source_sha256']==cstart['runtime_source_sha256']==v8.source_hashes(),'Shared V8 source identity')
 envs=[start['environment'],train['preparation_environment'],cstart['environment']]
 need(all(e['solver']==envs[0]['solver'] for e in envs),'Shared proof native identity')
 rows=read(prepared/'rows.json');programs=read(prepared/'programs.json');feat=read(prepared/'features.json');creg=read(consumed/'features.json');tdata=read(training/'training-data.json');ledger=read(prepared/'novelty.json')
 need(feat['columns']==creg['columns']==tdata['columns']==list(v8.columns()),'Exact455 columns')
 records=feat['records'];formulas=[r['formula'] for r in records]
 need(len(rows)==152 and len(records)==len(set(formulas))==146 and len(creg['records'])==2764,'Exact complete row/formula counts')
 need(len(programs)==5 and sum(r['primary_family'] for r in rows)==150,'Primary/related source membership')
 expected={'bitcount':47,'fft':6,'ndes':47,'h264_dec':50,'isqrt':2}
 need(dict(collections.Counter(r['benchmark'] for r in rows))==expected,'All ROI pool memberships')
 preflight=read(out/'preflight-at-audit-start.json');fields=('occurrences','runs','overlapSafeSaved','traceTotalInstructions','formula')
 for name,count in expected.items():
  p=preflight['programs'][name];raw=read(repo/p['all_roi_candidates']['path']);actual=[r for r in rows if r['benchmark']==name]
  clean=lambda xs:{r['formula']:{k:r[k] for k in fields} for r in xs}
  need(clean(raw)==clean(actual),'Original complete pool/occurrence/merit equality: '+name)
  need(all(r['traceTotalInstructions']==p['trace_instruction_count'] for r in actual),'Complete trace denominators')
 x=np.asarray([r['values'] for r in records]);need(x.shape==(146,455) and np.isfinite(x).all() and (x>=0).all(),'Finite455 inputs')
 # Independent archive restore, with no external cache or native subprocess.
 am=read(repo/'benchmarks/application-v8/feature-evidence-manifest.json');ap=repo/'benchmarks/application-v8'/am['archive']['path']
 need(sha(ap)==am['archive']['sha256'] and am['input_features_sha256']==sha(prepared/'features.json'),'Feature archive binding')
 cache=out/'restored-feature-cache';need(not cache.exists(),'Fresh isolated cache required');cache.mkdir()
 with zipfile.ZipFile(ap) as z:
  need(len(z.namelist())==len(set(z.namelist()))==len(am['files']),'Unique complete archive members')
  need(set(z.namelist())=={e['path'] for e in am['files']},'Archive inventory')
  for e in am['files']:
   dst=(cache/e['path']).resolve();need(dst.is_relative_to(cache.resolve()),'Safe cache restore');b=z.read(e['path']);need(hashlib.sha256(b).hexdigest()==e['sha256'] and len(b)==e['bytes'],'Archive member hash');dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
 native=[];oldpopen=subprocess.Popen
 def forbidden(*a,**kw):native.append(str(a));raise AssertionError('Native subprocess prohibited in restored cache replay')
 subprocess.Popen=forbidden
 try:prefix,pr=v6.FeatureExtractor(cache,frozen_tool=inp['frozen_tool']).matrix([{'formula':f} for f in formulas],workers=1)
 finally:subprocess.Popen=oldpopen
 need(np.array_equal(prefix,x[:,:336]) and not native,'Exact V6full336 replay from standalone archive')
 for r,q in zip(records,pr):
  for k in ('formula','normalized_formula','original_cache_key','normalized_cache_key','sog_cache_key','sog_manifest_sha256','original_manifest_sha256','normalized_manifest_sha256','original_graph_sha256','mapping_source_sha256'):need(r[k]==q[k],'Prefix provenance replay: '+k)
 # Recompute only deterministic descriptors of FIRST recorded accepted/fallback forms.
 # Never call analyze_modes or retry the timed-unknown proposed rewrite.
 modes=collections.defaultdict(collections.Counter);fallback=[];query_stats={};steps=interpreter=0
 rng=random.Random(2026101518);pairs=list(itertools.product(h.BOUNDARY,repeat=2))+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(32)]
 smt=out/'independent-accepted-smt2';smt.mkdir(exist_ok=True)
 for r in records:
  need(r['v8_runtime_source_sha256']==v8.source_hashes(),'Per-record V8 sources')
  need(r['v8_extraction_environment']['solver']==envs[0]['solver'],'Per-record native solver')
  need(r['v8_feature_schema']==v8.FEATURE_SCHEMA,'Per-record455 schema')
  need(r['v7_modes']['combined']['features']=={**r['v7_modes']['bit']['features'],**r['v7_modes']['affine']['features']},'Independent8+8 feature nesting')
  for mode,m in r['v7_modes'].items():
   md=m['metadata'];modes[mode][md['status']]+=1
   need(md['runtime_source_sha256']=={k:v8.source_hashes()[k] for k in ('semantic_features_v7.py','features.py')},'Proof runtime identity')
   need(md['budget']==dict(v8.PROOF_BUDGET.__dict__) and md['original_zero_override'] is False,'Proof budget/original zero contract')
   need(md['solver']==envs[0]['solver'],'Proof solver identity')
   for attempt in md['attempts']:
    p=attempt['proof'];need(hashlib.sha256(p['query_smt2'].encode()).hexdigest()==p['query_sha256'],'Retained attempted query hash')
   def callback(n,step,solver,result):
    text=solver.to_smt2();key=hashlib.sha256(text.encode()).hexdigest();need(result=='unsat','Accepted local independent proof');(smt/(key+'.smt2')).write_text(text);query_stats[key]=result
   steps+=h.replay_certificate(m,z3,callback)
   a=h.independent_parse(r['formula']);b=h.independent_parse(m['normalized_formula'])
   for left,right in pairs:need(h.recursive_word(a,left,right)==h.recursive_word(b,left,right),'Independent arithmetic equality');interpreter+=1
   if md['status']=='fallback_original':need(m['normalized_formula']==r['formula'] and not md['certificate']['steps'],'Retained all-mode original fallback')
  if r['v7_modes']['combined']['metadata']['status']=='fallback_original':
   attempts=[p for m in r['v7_modes'].values() for p in m['metadata']['attempts']]
   need(any(p['proof'].get('solver_result')=='unknown' for p in attempts),'Unknown failure evidence retained')
   fallback.append({'formula':r['formula'],'engine':r['v7_modes']['combined']['metadata']['proof_engine'],'unknown_query_sha256':[p['proof']['query_sha256'] for p in attempts]})
  nf=r['v7_combined_normalized_formula'];need(nf==r['v7_modes']['combined']['normalized_formula'],'Recorded final normalization')
  suffix=legacy.feature_dict(nf);need(r['values'][336:]==[suffix[n] for n in legacy.FEATURE_NAMES],'Exact119 suffix from first recorded form')
 # Independently assembled declared novelty channels; no production ledger helper.
 comm={'add','and','or','xor','mul','mulh','mulhu'}
 def text(n):
  if not isinstance(n,tuple):return str(n)
  return n[0]+'('+','.join(text(c) for c in n[1:])+')'
 def skel(n):return ('C' if isinstance(n,int) else 'I') if not isinstance(n,tuple) else n[0]+'('+','.join(skel(c) for c in n[1:])+')'
 def equiv(n):
  if not isinstance(n,tuple):return str(n)
  cs=[equiv(c) for c in n[1:]]
  if n[0] in comm:cs.sort()
  return n[0]+'('+','.join(cs)+')'
 def vector(v):return hashlib.sha256(b''.join(struct.pack('!d',float(n) if n else 0.) for n in v)).hexdigest()
 def channels(r):
  forms={r['formula'],r['normalized_formula'],r['v7_combined_normalized_formula']}
  out={'canonical':{r['formula']},'original_or_normalized':forms,'commutative_normalized':{equiv(h.independent_parse(v4normal(f))) for f in forms},'ordered_skeleton':{skel(h.independent_parse(f)) for f in forms}}
  for name,ix in [('mapping217',list(range(194))+list(range(313,336))),('legacy_original336',list(range(194))+list(range(313,336))+list(range(194,313))),('legacy_rewritten336',list(range(194))+list(range(313,336))+list(range(336,455)))]:out[name+'_vector']={vector([r['values'][i] for i in ix])}
  return out
 index=collections.defaultdict(lambda:collections.defaultdict(set));old={r['formula']:r for r in creg['records']};need(len(old)==2764,'Unique consumed identities')
 for f,r in old.items():
  for c,keys in channels(r).items():
   for k in keys:index[c][k].add(f)
 replay=[];counts=collections.Counter();byformula={r['formula']:r for r in records}
 for r in records:
  matches={c:sorted({f for k in keys for f in index[c].get(k,())}) for c,keys in channels(r).items()}
  replay.append({'formula':r['formula'],'matches':matches,'no_declared_identity_match':not any(matches[c] for c in ('canonical','original_or_normalized','commutative_normalized')),'strict_no_declared_match':not any(matches.values())})
  for c,v in matches.items():counts[c]+=bool(v)
 need(replay==ledger['records'],'Exact independent novelty ledger reconstruction')
 strict={r['formula'] for r in replay if r['strict_no_declared_match']}
 strict_program={n:sum(r['formula'] in strict for r in rows if r['benchmark']==n) for n in expected}
 # Training336 and archived suffix119 remain exact for all original1665 records.
 td={r['formula']:values for r,values in zip(tdata['rows'],tdata['values'])};need(len(td)==1665,'Exact1665 training identities')
 training_diff=[f for f,v in td.items() if old[f]['values']!=v]
 familiar_prefix=[f for f in formulas if f in old];need(all(byformula[f]['values'][:336]==old[f]['values'][:336] for f in familiar_prefix),'Familiar exact frozen336 features')
 need(not training_diff,'Consumed1665 full455 differs from archive-derived training representation')
 need(all(sha(p)==digest for p,digest in sources.items()),'Audit sources unchanged')
 report={'schema':'isaforge-v8-independent-input-audit-v1','status':'pass','inputs':{str(p):sha(p) for p in (prepared/'input-preparation.json',prepared/'features.json',prepared/'rows.json',prepared/'novelty.json',training/'preparation.json',consumed/'completion.json')},'audit_source_sha256':sources,'application_rows':152,'unique_original_formulas':146,'primary_family_rows':150,'related_source_rows':2,'consumed_formulas':2764,'training_rows':1665,'training_consumed_full455_differences':training_diff,'sources_and_native_solver_consistent':True,'exact_restored_prefix_columns':336,'deterministic_suffix_columns':119,'native_subprocess_calls':len(native),'feature_archive':am['archive'],'restored_files':len(am['files']),'cache_directories':am['cache_directories'],'modes':{m:dict(c) for m,c in modes.items()},'fallback_records':fallback,'accepted_local_certificate_steps_reproved':steps,'unique_independent_accepted_local_queries':len(query_stats),'unknown_rewrite_retries':0,'independent_recursive_word_comparisons':interpreter,'novelty_match_unique_counts':dict(counts),'strict_no_declared_match_unique':len(strict),'strict_no_declared_match_program_counts':strict_program,'strict_novel_complete_primary_family_macro_available':all(strict_program[n]>0 for n in ('bitcount','fft','ndes','h264_dec')),'original_zero_unique_count':int(v6.v5.original_zero(x[:,:313]).sum()),'scope':'No experiment fit, fresh label, or actual model prediction. Replayed raw input graphs/first proof ledger only; unknown rewrite was retained without retry. Absence of declared identity match is not complete functional novelty.','elapsed_seconds':time.perf_counter()-began}
 (out/'input-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('inputs','audit_source_sha256')},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();
 for n in ('repo','prepared','training','consumed','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();run(a.repo.resolve(),a.prepared.resolve(),a.training.resolve(),a.consumed.resolve(),a.output.resolve())
