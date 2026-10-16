"""One retained V13 record through the snapshotted V11 DirectoryArchive; no jobs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
def forbidden(*a,**k):raise AssertionError('Native/model/feature/target work forbidden during compatibility replay')
subprocess.Popen=forbidden
original_open=Path.open
opened=[]
def checked_open(self,*args,**kwargs):
    if self.suffix=='.joblib' or 'measurements' in self.parts or self.name in ('labels.json','original-training.json','evaluation.json','development-data.json'):forbidden()
    opened.append(str(self))
    return original_open(self,*args,**kwargs)
Path.open=checked_open
spec=importlib.util.spec_from_file_location('v11_feature_compatibility_snapshot',HERE/'predict-source.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=ROOT
m.v6.load_model=forbidden;m.v6.FeatureExtractor.matrix=forbidden
for name in ('fit','measurement_inputs','old_inputs','extract_features'):setattr(m.replay,name,forbidden)
source=ROOT/'results/2026-10-15-v13b-coverage-recovery';stage=source/'features/attempt-0000'
read=lambda p:json.loads(p.read_bytes())
manifest=read(stage/'raw-evidence.json');completion=read(source/'features/completion.json');plan=read(source/'feature-plan.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(stage/'raw-evidence.zip')==manifest['archive_sha256']
entries={r['path']:r for r in manifest['files']}
with zipfile.ZipFile(stage/'raw-evidence.zip') as z:
    data=z.read('features.json');assert hashlib.sha256(data).hexdigest()==completion['features_sha256']==entries['features.json']['sha256']
    record=json.loads(data)['records'][0]
    assert record['cache_subdir']==record['candidate_id'].split(':')[1]
    selected=sorted(n for n in entries if n.startswith('cache/'+record['cache_subdir']+'/'))
    assert len(selected)==12
    total=0
    for n in selected:
        p=Path(n);assert not p.is_absolute() and '..' not in p.parts
        data=z.read(n);assert len(data)==entries[n]['bytes'] and hashlib.sha256(data).hexdigest()==entries[n]['sha256']
        destination=HERE/'stage'/p;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data);total+=len(data)
archive=m.DirectoryArchive(HERE/'stage')
values,channels=m.replay.replay_feature_record(archive,record,plan['frozen_tool'],completion['collection_root'])
assert values.shape==(336,) and np.array_equal(values,np.asarray(record['values'],dtype=float))
assert len(m.v6.mapping_indices())==217 and values[m.v6.mapping_indices()].shape==(217,)
assert record['original_cache_key']==record['normalized_cache_key'] and len(channels)==2
(HERE/'record.json').write_text(json.dumps(record,indent=2)+'\n')
report=dict(schema='isaforge-v11-feature-layout-compatibility-v1',status='pass',scope='One existing committed V13 input-feature record; not a V11 pool extraction or prediction. Historical collection_root authenticates saved SOG command strings; extracted bytes are unchanged.',driver_sha256=sha(Path(__file__)),predict_source_snapshot_sha256=sha(HERE/'predict-source.py'),shared_replay_source_sha256=sha(ROOT/'scripts/develop_v13_coverage.py'),historical_archive_sha256=sha(stage/'raw-evidence.zip'),historical_feature_completion_sha256=sha(source/'features/completion.json'),candidate_id=record['candidate_id'],formula=record['formula'],cache_subdir=record['cache_subdir'],selected_files=len(selected),selected_uncompressed_bytes=total,full_features=336,selected_features=217,full_vector_exact=True,original_normalized_cache_shared=True,retained_native_channels=len(channels),native_channel_paths=sorted(channels),original_generic_zero_override=bool(values[list(m.v6.columns()).index('original_gate_count')]==0),native_jobs=0,new_feature_extractions=0,models_loaded=0,predictions=0,target_files_opened=0,fits=0,opened_paths=sorted(set(opened)))
(HERE/'compatibility-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='opened_paths'},indent=2))
