"""Independent external freeze replay. Never read external target measurements."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,time,subprocess
from collections import Counter
import numpy as np

REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
OUT=Path(__file__).resolve().parent
BASE=REPO/'results/2026-10-14-v5-external'
EXPECTED_SHA='9504e132d5e7469b7a53d0a3d965fd0fc8896d17854d7445176ebac8ddaeeb48'
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(condition,message):
 if not condition:raise AssertionError(message)
def checked(record,base=BASE):
 p=(base/record['path']).resolve();need(sha(p)==record['sha256'],str(p));return p
def absent(*a,**k):raise RuntimeError('Independent audit forbids native process invocation')

need(sha(BASE/'freeze.json')==EXPECTED_SHA,'Exact declared freeze')
need(not(BASE/'label-release.json').exists(),'External labels must remain sealed')
need(not(BASE/'measurements').exists(),'No external target measurement directory')
import evaluate_external_v5 as evaluator
manifest,rows,predictions,overlap=evaluator.validate_freeze(BASE)
records=list(manifest['files'])+[entry[k] for entry in manifest['models'].values() for k in ('artifact','schema','predictions')]
hashes={str(checked(r)):r['sha256'] for r in records}
need(len(rows)==80 and len({r['formula'] for r in rows})==79,'80 rows/79 formulas')
need(Counter(r['benchmark'] for r in rows)==Counter({'external_v5_dijkstra':5,'external_v5_adpcm_dec':47,'external_v5_anagram':28}),'Program weighting')
families={'external_v5_dijkstra':'graph_shortest_paths','external_v5_adpcm_dec':'speech_codec','external_v5_anagram':'multiset_word_search'}
need(all(r['family']==families[r['benchmark']]==r['stratum'] for r in rows),'Exact family mapping')
old_base=checked(manifest['model_source_freeze']).parent
old=read(old_base/'freeze.json')
for name,entry in manifest['models'].items():
 for key in ('artifact','schema'):
  need(checked(entry[key])==checked(old['models'][name][key],old_base),'Unchanged original model identity')

# Reference inputs/features only: never open consumed test dataset/target labels.
from isaforge.structural_features_v5 import normalize_formula
from isaforge.v5_corpus import skeleton
feature_data=read(BASE/'features.json');features=feature_data['records']
feature_by_formula={r['formula']:r for r in features}
indices={}
for source,input_name,feature_name in [('development','development-data.json','development-features.json'),('consumed_v5_test','corpus/test/candidates.json','test-features.json')]:
 inputs=read(old_base/input_name);f=read(old_base/feature_name)['records']
 need({r['formula'] for r in inputs}=={r['formula'] for r in f},'Reference feature identities')
 indices[source]={'exact':{r['formula'] for r in inputs},'normalized':{normalize_formula(r['formula']) for r in inputs},
  'full_feature':{tuple(r['values']) for r in f},'original_skeleton':{skeleton(r['formula']) for r in inputs},
  'normalized_skeleton':{skeleton(normalize_formula(r['formula'])) for r in inputs}}
novel_counts={'strict_novel':Counter(),'formula_novel':Counter()}
for row,declared in zip(rows,overlap['records']):
 formula=row['formula'];n=normalize_formula(formula)
 keys={'exact':formula,'normalized':n,'full_feature':tuple(feature_by_formula[formula]['values']),
  'original_skeleton':skeleton(formula),'normalized_skeleton':skeleton(n)}
 hits={source:{kind:value in index[kind] for kind,value in keys.items()} for source,index in indices.items()}
 need(hits==declared['overlap'],'Independent overlap flags')
 strict=not any(v for family in hits.values() for v in family.values())
 novel=not any(v for family in hits.values() for k,v in family.items() if k in ('exact','normalized','full_feature'))
 need(strict==declared['strict_novel'] and novel==declared['formula_novel'],'Independent novelty assignment')
 if strict:novel_counts['strict_novel'][row['family']]+=1
 if novel:novel_counts['formula_novel'][row['family']]+=1

# Reconstruct features from copied raw graph evidence, prohibiting native calls.
source_cache=REPO/'generated/external-v5/features';cache=OUT/'cache'
need(not cache.exists(),'Audit cache must begin absent')
t=time.perf_counter();shutil.copytree(source_cache,cache);copy_seconds=time.perf_counter()-t
from isaforge import area_model_v5 as v5,area_model_v4 as v4,masterrtl_baseline as master,graph_features_v5 as graph
master.tool_identity=absent;graph.tool_identity=absent
subprocess.run=absent;subprocess.Popen=absent;subprocess.check_output=absent
dual=v5.load_model(checked(manifest['models']['dual_semantics']['artifact']),cache)
unique=[{'formula':r['formula']} for r in features]
t=time.perf_counter();matrix,reconstructed=v5.FeatureExtractor(cache,frozen_tool=dual.frozen_tool).matrix(unique,workers=1);feature_seconds=time.perf_counter()-t
need(np.array_equal(matrix,np.asarray([r['values'] for r in features])),'All 79 feature vectors reconstructed exactly')
semantic_records=lambda records:[{k:v for k,v in r.items() if k!='cache_hit'} for r in records]
need(semantic_records(reconstructed)==semantic_records(features),'All normalized/cache keys and graph hashes reconstructed exactly')
results={}
for name,entry in manifest['models'].items():
 t=time.perf_counter()
 model=v5.load_model(checked(entry['artifact']),cache) if name in v5.VIEWS else master.load_model(checked(entry['artifact']),cache/'masterrtl-fixed') if name=='masterrtl_fixed' else v4.load_model(checked(entry['artifact']),cache/'v4')
 load_seconds=time.perf_counter()-t
 t=time.perf_counter();actual=model.predict(rows);elapsed=time.perf_counter()-t
 need(actual==predictions[name],f'Exact all-field replay {name}')
 poisoned=[{**r,'lut4_count':999999,'carry_count':-100,'correctness_verified':False,'target':{'area':0}} for r in rows]
 need(model.predict(poisoned)==actual,f'Outcome metadata ignored {name}')
 values={}
 for row in actual:
  if row['formula'] in values:need(values[row['formula']]==row['predicted_lut4'],'Repeated original formula')
  values[row['formula']]=row['predicted_lut4']
 results[name]={'rows':len(actual),'unique_formulas':len(values),'exact_all_fields_match':True,
                'poisoned_outcome_fields_ignored':True,'load_seconds':load_seconds,'populated_cache_inference_seconds':elapsed}
for path,digest in hashes.items():need(sha(path)==digest,'Frozen evidence remained unchanged')
need(sha(BASE/'freeze.json')==EXPECTED_SHA and not(BASE/'label-release.json').exists() and not(BASE/'measurements').exists(),'Exact seal retained')
summary={'status':'pass','phase':'external pre-release; no external target label read or collected','freeze_sha256':EXPECTED_SHA,
 'models':results,'frozen_unique_file_count':len(hashes),'declared_manifest_file_count':len(manifest['files']),
 'program_formula_rows':80,'unique_original_formulas':79,'feature_vectors_reconstructed':79,
 'feature_values':int(matrix.size),'feature_replay_seconds':feature_seconds,'isolated_cache_copy_seconds':copy_seconds,
 'feature_metadata_scope':'All fields exact except operational cache_hit changes from cold preparation to cached replay',
 'native_process_calls':0,'timing_scope':'Populated isolated cache; excludes cache copy; no cold inference measurement',
 'reference_formula_counts':{s:len(i['exact']) for s,i in indices.items()},'novel_rows_by_family':{k:dict(v) for k,v in novel_counts.items()},
 'novel_three_family_macro_available':False,'git_commit_check':'Pending parent commit; this audit does not authorize bypassing committed-review gate'}
(OUT/'pre-release.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
