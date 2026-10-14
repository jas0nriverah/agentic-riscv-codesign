"""Fresh Git clone, both archive restores and exact frozen V6 score replay."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/2026-10-14-v6';OUT=BASE/'audit'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,what):
 if not ok:raise AssertionError(what)

def run(commit):
    need(len(commit)==40 and set(commit)<={'0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f'},'Exact final evidence commit required')
    for scope in ('calibration','test'):need(read(BASE/'corpus'/scope/'completion.json')['complete'] is True,'Both stages complete before replay')
    clone=ROOT.parent/'v6-relocated-repository';need(not clone.exists(),'Fresh clone destination')
    before=time.perf_counter();subprocess.run(['git','clone','--no-local','--quiet',str(ROOT),str(clone)],check=True)
    subprocess.run(['git','checkout','--quiet',commit],cwd=clone,check=True)
    need(not(clone/'.git/objects/info/alternates').exists(),'Independent Git object database')
    moved=clone/'results/2026-10-14-v6'
    for relative in ('point-freeze.json','calibration-freeze.json','corpus/calibration/raw-evidence.zip','corpus/test/raw-evidence.zip','evaluation.json'):
        need(sha(moved/relative)==sha(BASE/relative),'Exact committed bundle bytes')
        need(not(moved/relative).samefile(BASE/relative),'No hardlinked evidence files')
    need(not(clone/'generated/v6-measurements').exists(),'Both raw archive destinations begin absent')
    archives={}
    for scope in ('calibration','test'):
        result=subprocess.run([str(ROOT/'.venv/bin/python'),str(clone/'scripts/measure_v6.py'),'restore','--scope',scope,'--root',str(moved)],cwd=clone,capture_output=True,text=True)
        (OUT/f'clone-restore-{scope}.log').write_text(result.stdout+result.stderr)
        need(result.returncode==0,'Portable archive restore '+scope)
        manifest=read(moved/'corpus'/scope/'raw-evidence.json')
        for entry in manifest['files']:
            path=clone/entry['path'];need(path.stat().st_size==entry['size'] and sha(path)==entry['sha256'],'Restored bytes')
            need(not path.samefile(ROOT/entry['path']),'No hardlinked raw files')
        archives[scope]={'files':len(manifest['files']),'archive_sha256':manifest['archive_sha256']}
    # No graph/feature caches are copied; the frozen scorer consumes only the
    # committed point matrices/predictions and restored verified original targets.
    need(not(clone/'generated/v5-features').exists(),'No borrowed original graph cache')
    output=OUT/'clone-evaluation.json';timed=time.perf_counter()
    score=subprocess.run([str(ROOT/'.venv/bin/python'),str(clone/'scripts/evaluate_v6.py'),'score','--root',str(moved),'--output',str(output)],cwd=clone,capture_output=True,text=True)
    (OUT/'clone-score.log').write_text(score.stdout+score.stderr);need(score.returncode==0,'Frozen relocated scorer')
    expected=read(BASE/'evaluation.json');actual=read(output)
    expected.pop('evaluated_at_utc',None);actual.pop('evaluated_at_utc',None)
    need(actual==expected,'Every evaluation field matches except execution timestamp')
    report={'status':'pass','final_evidence_commit':commit,'clone':'Fresh --no-local clone with independent objects/no alternates',
            'no_hardlinked_evidence':True,'both_raw_destinations_initially_absent':True,'no_graph_feature_cache_copied':True,
            'archives':archives,'exact_all_score_fields_except_timestamp':True,'score_seconds':time.perf_counter()-timed,
            'clone_restore_score_total_seconds':time.perf_counter()-before,'original_venv_executable_used':True,
            'new_estimator_fits':0,'new_hardware_measurements':0,'audit_source_sha256':sha(Path(__file__))}
    (OUT/'clone-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);args=parser.parse_args();run(args.commit)
