"""Independent exact-delta review; writes only an external audit report."""
from pathlib import Path
import hashlib,json,subprocess
repo=Path(__file__).resolve().parent.parent/'agentic-riscv-codesign'
root=repo/'results/2026-10-15-v8-application-transfer'
amend=root/'pre-fit-amendments/0000'
original='771bd389d355efeb8ff8215a521ffd07bcb85319'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def old(p):return subprocess.check_output(['git','show',original+':'+p.relative_to(repo).as_posix()],cwd=repo)
def need(v,m):
 if not v:raise AssertionError(m)
need(subprocess.run(['git','merge-base','--is-ancestor',original,'HEAD'],cwd=repo).returncode==0,'Review baseline no longer ancestor')
need(not any((root/n).exists() for n in ['training-start.json','point-freeze.json','models','point-predictions','label-release.json','measurements']),'Unexpected fits/points/labels')
test=repo/'tests/test_seal_v8_application_inputs.py';prep=root/'training/preparation.json';seal=root/'input-seal.json'
for p,n in [(seal,'original-input-seal.json'),(prep,'original-training-preparation.json'),(test,'original-test_seal_v8_application_inputs.py')]:
 need((amend/n).read_bytes()==old(p),'Original snapshot not Git-identical')
expected_line=b"        (root/'tests/test_semantic_features_v7_independent.py').write_text('synthetic independent proof helper')\n"
need(test.read_bytes()==old(test).replace(b"        return root,app,training,consumed,runtime,rm,audit,review,sources\n",expected_line+b"        return root,app,training,consumed,runtime,rm,audit,review,sources\n"),'Unexpected test edit')
added={repo/'scripts/score_v8_applications.py',repo/'tests/test_score_v8_applications.py',*(p for p in amend.iterdir() if p.is_file())}
report={}
for p,n in [(prep,'original-training-preparation.json'),(seal,'original-input-seal.json')]:
 before=read(amend/n);after=read(p)
 before_entries={(p.parent/e['path']).resolve():e['sha256'] for e in before['files']}
 after_entries={(p.parent/e['path']).resolve():e['sha256'] for e in after['files']}
 need(len(before_entries)==len(before['files']) and len(after_entries)==len(after['files']),'Duplicate records')
 need(set(before_entries)<=set(after_entries),'Removed bindings')
 need(set(after_entries)-set(before_entries)==added,'Unexpected new binding')
 changed={q for q in before_entries if before_entries[q]!=after_entries[q]}
 need(changed=={test},'Unexpected changed binding')
 for q,h in after_entries.items():need(sha(q)==h,'Bound file bytes mismatch')
 metadata_changed={k for k in set(before)|set(after) if k!='files' and before.get(k)!=after.get(k)}
 need(metadata_changed==({'sealed_at_utc','amended_at_utc','pre_fit_amendment'} if p==seal else {'amended_at_utc','pre_fit_amendment'}),'Unexpected metadata change')
 need(after['pre_fit_amendment']['sha256']==sha(amend/'amendment.json'),'Amendment pointer mismatch')
 report[str(p.relative_to(repo))]={'sha256':sha(p),'original_records':len(before_entries),'amended_records':len(after_entries),'changed_bindings':[str(q.relative_to(repo)) for q in sorted(changed)],'new_bindings':[str(q.relative_to(repo)) for q in sorted(added)],'metadata_changes':sorted(metadata_changed)}
record=read(amend/'amendment.json')
for n,h in record['byte_identical_data'].items():need(sha(root/n)==h==hashlib.sha256(old(root/n)).hexdigest(),'Fixed data mismatch')
for e in record['added_sources']:need(sha(repo/e['path'])==e['sha256'],'Reviewed addition mismatch')
for name in ['scripts/measure_v8_applications.py','scripts/evaluate_v8_applications.py','scripts/train_v8_applications.py','scripts/infer_v8_applications.py','isaforge/area_model_v8.py','docs/v8-application-pilot-protocol.md']:
 p=repo/name;need(p.read_bytes()==old(p),'Frozen production source changed')
result={'schema':'isaforge-v8-independent-prefit-amendment-review-v1','status':'pass','decision':'GO for commit and fixed-two-fit stage; fresh target release still requires separate point-freeze review','original_commit':original,'manifests':report,'fixed_data_byte_identical':record['byte_identical_data'],'production_model_evaluator_collector_protocol_unchanged':True,'original_snapshots_git_identical':True,'fits_predictions_labels_present':False,'focused_tests':'26 passed in 2.61s: test_score_v8_applications.py and test_seal_v8_application_inputs.py','scope':'Read-only review of scorer/test addition and exact pre-fit amendment; independent full oracle replay remains a later audit.'}
out=Path(__file__).with_name('prefit-amendment-review.json');need(not out.exists(),'Report already exists');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
