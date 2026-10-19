"""One explicit amendment before any V8 fit, prediction or target release."""
from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess
repo=Path(__file__).parent/'agentic-riscv-codesign'
root=repo/'results/2026-10-15-v8-application-transfer'
original='771bd389d355efeb8ff8215a521ffd07bcb85319'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==original
assert not any((root/n).exists() for n in ['training-start.json','point-freeze.json','models','point-predictions','label-release.json','measurements'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rec(p,base):return {'path':os.path.relpath(p,base),'sha256':sha(p)}
def write(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def original_bytes(p):return subprocess.check_output(['git','show',original+':'+p.relative_to(repo).as_posix()],cwd=repo)
amend=root/'pre-fit-amendments/0000';amend.mkdir(parents=True,exist_ok=False)
seal=root/'input-seal.json';prep=root/'training/preparation.json';test=repo/'tests/test_seal_v8_application_inputs.py'
for p,n in [(seal,'original-input-seal.json'),(prep,'original-training-preparation.json'),(test,'original-test_seal_v8_application_inputs.py')]:
 b=original_bytes(p)
 if p!=test:assert p.read_bytes()==b
 (amend/n).write_bytes(b)
for name in ['v8-final-focused-tests.log','v8-final-focused-tests-corrected.log','v8-final-focused-tests-with-scorer.log','v8-input-checkpoint-ci-failures.log']:
 shutil.copyfile(repo.parent/name,amend/name)
fixed_data={n:sha(root/n) for n in ['rows.json','features.json','programs.json','novelty.json','training/training-data.json','prelabel-audit.zip','materialization-coverage.json']}
for n,d in fixed_data.items():assert hashlib.sha256(original_bytes(root/n)).hexdigest()==d
added=[repo/'scripts/score_v8_applications.py',repo/'tests/test_score_v8_applications.py']
assert sha(added[0])=='847892e109deee1b97ce68f9c424be61ccc950d18ac853d3fa9d371850382fcb'
assert sha(added[1])=='6ce835f75557efcfc077d34349e64ff3129f91b2299ccf7ec7f260af1f1f8b40'
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
record={'schema':'isaforge-v8-pre-fit-amendment-v1','amended_at_utc':stamp,'original_commit':original,
 'reason':'Correct one synthetic test fixture omission and bind the independently reviewed raw-evidence scoring wrapper before any fits or target release. The production model, pure evaluator, collector, cohort, feature outcomes and original training labels are unchanged.',
 'original_input_seal_sha256':sha(amend/'original-input-seal.json'),'original_training_preparation_sha256':sha(amend/'original-training-preparation.json'),
 'test_correction':{'path':str(test.relative_to(repo)),'old_sha256':sha(amend/'original-test_seal_v8_application_inputs.py'),'new_sha256':sha(test),'change':'Create synthetic tests/test_semantic_features_v7_independent.py in the test-only repository fixture.'},
 'added_sources':[rec(p,repo) for p in added],'byte_identical_data':fixed_data,'new_estimator_fits':0,'model_predictions_read':False,'fresh_application_labels_read':False,
 'validation':'151 V8 tests and 7 subtests passed. Earlier fixture failure retained. Local full suite also has an independently diagnosed existing macOS 200ms process-start timeout failure; not claimed green.',
 'preservation':'Original complete checkpoint remains in Git; exact changed seal/preparation/test bytes and failed test logs are retained here.'}
write(amend/'amendment.json',record)
retained=sorted(p for p in amend.iterdir() if p.is_file())
for p in [prep,seal]:
 d=json.loads(p.read_text());found=0
 for entry in d['files']:
  resolved=(p.parent/entry['path']).resolve()
  if resolved==test:entry['sha256']=sha(test);found+=1
  elif resolved==prep:entry['sha256']=sha(prep)
 assert found==1
 known={(p.parent/e['path']).resolve() for e in d['files']}
 for extra in added+retained:
  if extra not in known:d['files'].append(rec(extra,p.parent))
 d['pre_fit_amendment']=rec(amend/'amendment.json',p.parent)
 d['amended_at_utc']=stamp
 if p==seal:d['sealed_at_utc']=stamp
 write(p,d)
for n,d in fixed_data.items():assert sha(root/n)==d
for p in [prep,seal]:
 for e in json.loads(p.read_text())['files']:assert sha(p.parent/e['path'])==e['sha256'],e['path']
print(json.dumps({'input_seal_sha256':sha(seal),'training_preparation_sha256':sha(prep),'amendment_sha256':sha(amend/'amendment.json')},indent=2))
