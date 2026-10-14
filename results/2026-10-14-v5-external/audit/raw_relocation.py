"""Post-release external raw recount and archive relocation; no fitting/synthesis."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib,importlib.util,json,shutil,subprocess,sys,time

REPO=Path('/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign')
BASE=REPO/'results/2026-10-14-v5-external'
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,what):
 if not ok:raise AssertionError(what)
stamp=lambda value:datetime.fromisoformat(value.replace('Z','+00:00'))
done=read(BASE/'measurements/completion.json')
need(done.get('complete') is True and not done['failures'],'Only completed authorized target collection may be read')
manifest=read(BASE/'freeze.json');release=read(BASE/'label-release.json');approval=read(BASE/'label-approval.json')
need(done['release']==release and release['parent_review']==approval,'Reviewed release chain')
need(release['freeze_sha256']==sha(BASE/'freeze.json')==approval['freeze_sha256'],'Release/freeze hashes')
need(stamp(manifest['frozen_at_utc'])<=stamp(approval['reviewed_at_utc'])<=stamp(release['released_at_utc']),'Freeze/review/release chronology')
need(approval['approved_for_label_release'] is True and release['authorized_after_parent_review'] is True,'Explicit parent approval')
attempt=BASE/'measurements'/done['attempt'];scratch=(BASE/done['scratch_directory']).resolve()
need(scratch.is_relative_to(REPO/'generated/external-v5/target-measurements'),'Owned portable raw lookup')
for name,key in [('dataset.json','dataset_sha256'),('verification.json','verification_sha256'),('unique-measurements.json','unique_measurements_sha256')]:need(sha(attempt/name)==done[key],name)
need(done['collector_sha256']==sha(REPO/'scripts/measure_external_v5.py'),'Frozen collector identity')
need(done['tool']==manifest['measurement_tool']['version'] and done['tool_sha256']==manifest['measurement_tool']['executable_sha256'],'Frozen Yosys binary identity')
proofs=read(attempt/'verification.json');need(len(proofs)==1,'One complete verification batch')
proof=proofs[0];need(proof['verified'] is True and proof['formula_count']==79 and proof['vectors_per_formula']==2148 and proof['total_comparisons']==79*2148,'Complete sampled verification')
verification=scratch/'verification'
need(sha(verification/'verification.v')==proof['rtl_sha256'] and sha(verification/'vectors.txt')==proof['vectors_sha256'],'Retained verification source/vector bytes')
need(sha(REPO/'isaforge/v4_validation.py')==proof['v4_validation_override_sha256'],'Verification wrapper hash')
if proof.get('signed_overflow_workaround_applied'):
 need(sha(verification/'yosys-boundary-cross-check/eval.log')==proof['independent_yosys_log_sha256'],'Signed-wrap boundary cross-check evidence')
from isaforge.rtl import generate_rtl
rows=read(BASE/'candidates.json');labels=read(attempt/'dataset.json');unique=read(attempt/'unique-measurements.json')
metrics={r['formula']:r for r in unique};need(len(unique)==len(metrics)==79 and len(rows)==len(labels)==80,'79 unique/80 weighted rows')
need(set(metrics)=={r['formula'] for r in rows},'Complete original formula coverage')
resources=Counter();netlist_hashes={}
for formula,metric in metrics.items():
 folder=scratch/'circuits'/hashlib.sha256(formula.encode()).hexdigest()[:20]
 need(read(folder/'metrics.json')==metric,'Retained per-circuit metric')
 for name,key in [('candidate.v','rtl_sha256'),('ice40-netlist.json','netlist_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256')]:need(sha(folder/name)==metric[key],'Original synthesis artifact hash')
 need(metric['rtl_sha256']==hashlib.sha256(generate_rtl(formula).encode()).hexdigest(),'Original emitted RTL')
 need(metric['formula']==formula and metric['tool']==done['tool'] and metric['tool_sha256']==done['tool_sha256'],'Circuit tool/formula identity')
 need(stamp(metric['measured_at_utc'])>=stamp(release['released_at_utc']),'Targets measured after release')
 netlist=read(folder/'ice40-netlist.json');cells=Counter(c['type'] for c in netlist['modules']['candidate'].get('cells',{}).values())
 need(dict(cells)==metric['ice40_cell_types'],'Independent mapped candidate primitive recount')
 need(cells['SB_LUT4']==metric['ice40_lut4_count'] and cells['SB_CARRY']==metric['ice40_carry_count'],'Independent LUT4/carry targets')
 resources.update(cells);netlist_hashes[formula]=metric['netlist_sha256']
label_index={(r['benchmark'],r['candidate_id']):r for r in labels};need(len(label_index)==80,'Distinct expanded identities')
for row in rows:
 label=label_index[(row['benchmark'],row['candidate_id'])];metric=metrics[row['formula']]
 need(all(label[k]==v for k,v in row.items()),'Unchanged frozen weighted input')
 need(label['lut4_count']==metric['ice40_lut4_count'] and label['carry_count']==metric['ice40_carry_count'] and label['rtl_sha256']==metric['rtl_sha256'],'Expanded unique-circuit targets')
 need(label['correctness_verified'] is True and label['measurement_source']=='rtl_synthesis','Verified synthesis labels')

raw_summary={'status':'pass','freeze_sha256':sha(BASE/'freeze.json'),'unique_original_netlists_recounted':79,
 'weighted_program_rows_verified':80,'raw_unique_lut4_sum':resources['SB_LUT4'],'raw_unique_carry_sum':resources['SB_CARRY'],
 'verification_comparisons':proof['total_comparisons'],'all_original_rtl_script_log_netlist_hashes_match':True,
 'new_hardware_measurement':False,'limits':'Retained sampled verification, not a new simulation or formal proof.'}
(OUT/'raw-provenance.json').write_text(json.dumps(raw_summary,indent=2)+'\n')
if '--raw-only' in sys.argv:
 print(json.dumps(raw_summary,indent=2));raise SystemExit(0)
# Restore into a genuinely separate clone, without alternates or original caches.
need((BASE/'raw-evidence.zip').is_file(),'Parent must package complete evidence before relocation')
clone=OUT/'relocated-repository';need(not clone.exists(),'Fresh relocation destination')
subprocess.run(['git','clone','--no-local','--quiet',str(REPO),str(clone)],check=True)
need(not(clone/'.git/objects/info/alternates').exists(),'Relocation has independent Git objects')
moved=clone/'results/2026-10-14-v5-external';shutil.copytree(BASE,moved,dirs_exist_ok=True)
spec=importlib.util.spec_from_file_location('archive_external_independent',REPO/'scripts/archive_external_v5.py');archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)
need(not(clone/'generated/external-v5/target-measurements').exists(),'Raw destination begins absent')
archive_manifest=archive.restore(moved,clone)
for record in archive_manifest['files']:
 p=clone/record['path'];need(sha(p)==record['sha256'] and p.stat().st_size==record['size'],'Independent restored archive bytes')
need(not any({'obj_dir','obj_dir_wrapv'}.intersection(Path(r['path']).parts) for r in archive_manifest['files']),'Compiler objects excluded')
output=OUT/'relocated-evaluation.json';t=time.perf_counter()
run=subprocess.run([str(REPO/'.venv/bin/python'),str(clone/'scripts/evaluate_external_v5.py'),'score','--root',str(moved),'--output',str(output)],cwd=clone,capture_output=True,text=True)
(OUT/'relocated-score.log').write_text(run.stdout+run.stderr);need(run.returncode==0,'Relocated frozen scorer replay')
relocated=read(output);original=read(BASE/'evaluation.json')
relocated.pop('evaluated_at_utc',None);original.pop('evaluated_at_utc',None)
need(relocated==original,'All relocated score fields match except execution timestamp')
summary={'status':'pass','freeze_sha256':sha(BASE/'freeze.json'),'freeze_commit':approval['freeze_commit'],
 'unique_original_netlists_recounted':79,'weighted_program_rows_verified':80,'raw_unique_lut4_sum':resources['SB_LUT4'],'raw_unique_carry_sum':resources['SB_CARRY'],
 'verification_comparisons':proof['total_comparisons'],'all_original_rtl_script_log_netlist_hashes_match':True,
 'archive_files_restored':len(archive_manifest['files']),'archive_sha256':archive_manifest['archive_sha256'],
 'fresh_relocated_git_clone':True,'independent_git_objects':True,'relocated_score_all_fields_exact_except_timestamp':True,
 'relocated_score_seconds':time.perf_counter()-t,'new_model_fitting':False,'new_hardware_measurement':False,
 'limitations':'Recounts retained mapped primitives and sampled verification evidence; no new simulation, formal proof or CPU benchmark.'}
(OUT/'raw-relocation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
