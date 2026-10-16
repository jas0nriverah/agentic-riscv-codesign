"""Synthetic V13 joint-fold, saved-graph, release and30-spied-fit checks only."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import zipfile
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('develop_v13_coverage',ROOT/'scripts/develop_v13_coverage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture(autouse=True)
def no_native_or_real_fit(monkeypatch):
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('Native jobs forbidden'))
    monkeypatch.setattr(m,'ExtraTreesRegressor',lambda *a,**k:pytest.fail('Real fitting forbidden'))
    monkeypatch.setattr(m.v6,'FeatureExtractor',lambda *a,**k:pytest.fail('Native feature extraction forbidden'))


def toy(old=1713,new=48):
    rows=[]
    for i in range(old):
        row={'formula':f'addi(in0,{i+1})','source':'original1665' if i<1665 else 'coverage48','cohort':'original1713',
            'stratum':m.STRATA[i%9],'lut4_count':i%150}
        if i<1665:row.update(inherited_component='old-'+str(i),development_index=i)
        else:row['context']='v9-context-'+str((i-1665)//8)
        rows.append(row)
    for j in range(new):
        i=old+j;rows.append({'formula':f'addi(in1,{j+1})','source':'coverage_v13','cohort':'coverage48','context':'new-context-'+str(j//4),
            'family':'new-family-'+str(j//16),'stratum':m.STRATA[j%9],'candidate_id':'SYNTHETIC-'+str(j),'lut4_count':200+j})
    x=np.zeros((len(rows),217),dtype='<f4');x[:,0]=np.arange(len(rows))+1
    return rows,x,[[r['formula']] for r in rows]


def test_shared_transitive_closure_excludes_new_linked_to_heldout_old_from_both():
    rows,x,a=toy();a[1713].append(rows[0]['formula']);x[1717]=x[1713];rows[1]['inherited_component']=rows[0]['inherited_component']
    groups=m.build_groups(rows,x,a);split=m.assign_folds(rows,groups)
    linked=(0,1,1713,1714,1715,1716,1717,1718,1719,1720)
    assert len({groups['row_components'][i] for i in linked})==1
    fold=split['fold_ids'][0];d=split['folds'][fold]
    assert all(i in d['validation_indices'] and i not in d['training_indices'] and i not in d['control_training_indices'] for i in linked)
    assert all(i<1713 for d in split['folds'] for i in d['control_training_indices']) and split['feasible']
    assert len({groups['row_components'][i] for i in range(1665,1673)})==1


def test_targets_and_unused_metadata_cannot_change_geometry_or_folds():
    rows,x,a=toy();g=m.build_groups(rows,x,a);s=m.assign_folds(rows,g)
    for r in rows:r.update(lut4_count=-9999,residual=float('nan'),predicted_lut4=1000000,benchmark='POISON')
    assert m.build_groups(rows,x,a)==g and m.assign_folds(rows,g)==s


def test_v9_v13_context_names_do_not_accidentally_share_group():
    rows,x,a=toy();rows[1665]['context']=rows[1713]['context']='same-name'
    g=m.build_groups(rows,x,a);assert g['row_components'][1665]!=g['row_components'][1713]


def test_control_training_requires_all9_strata_even_when_new_rows_fill_gap():
    rows,x,a=toy();target=m.STRATA[0]
    for r in rows[:1713]:
        if r['stratum']==target:r['source']='original1665';r['inherited_component']='all-old-one-stratum'
    split=m.assign_folds(rows,m.build_groups(rows,x,a))
    assert split['feasible'] is False and any(not d['control_training_has_all9strata'] for d in split['folds'])


def test_primary_denominator_remains1713_and_secondary48_family_denominators():
    rows,x,a=toy();y=np.asarray([r['lut4_count'] for r in rows],dtype=float);p=y.copy();p[1713:]+=1000
    scores=m.cohort_scores(rows,y,p)
    assert scores['original1713']['pooled']['count']==1713 and scores['original1713']['macro_stratum_mae_lut4']==0
    assert scores['coverage48']['pooled']['count']==48 and scores['coverage48']['pooled']['mae_lut4']==1000
    assert sum(v['pooled']['count'] for v in scores['coverage_by_family'].values())==48
    d=m.paired_decisions(np.array([65.]),np.array([64.]),np.array([66.]))['64']
    assert d['control_wrong_augmented_correct_count']==1 and d['control_accept_augmented_reject_count']==1


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'SYNTHETIC';root.mkdir();rows,x,a=toy();zero=np.zeros(1761,dtype=bool);zero[0]=True
    source=tmp_path/'source.py';source.write_text('# SYNTHETIC source\n');entry=tmp_path/'authorized-input.json';m.write(entry,{'synthetic':True})
    monkeypatch.setattr(m,'source_paths',lambda:[source]);monkeypatch.setattr(m.v12,'runtime',lambda:{'synthetic':True,'files':[{'path':str(source),'sha256':m.sha(source)}]})
    monkeypatch.setattr(m,'load_inputs',lambda root:(copy.deepcopy(rows),x.copy(),zero.copy(),copy.deepcopy(a),{entry:m.sha(entry)}))
    m.prepare(root);return root,source,entry


def test_prepare_validates_exact_joint1761_and_single_freeze(prepared):
    root,_,_=prepared;manifest,data,x,g,s,b=m.validate(root)
    assert x.shape==(1761,217) and x.dtype==np.dtype('<f4') and len(manifest['fit_schedule'])==30
    assert {j['view'] for j in manifest['fit_schedule']}=={'control','augmented'} and all(f['control_training_has_all9strata'] for f in s['folds'])
    with pytest.raises(ValueError,match='Fresh'):m.prepare(root)


@pytest.mark.parametrize('name',['matrix.npy','split.json','groups.json','recipe.json','fitting.json','source','input'])
def test_saved_input_mutations_fail(prepared,name):
    root,source,entry=prepared;p=source if name=='source' else entry if name=='input' else root/'fitting'/name;p.write_bytes(p.read_bytes()+b'POISON')
    with pytest.raises((ValueError,UnicodeDecodeError)):m.validate(root)


class SpyForest:
    calls=[];fail_on=None
    def __init__(self,**params):self.params=params
    def get_params(self,deep=True):return self.params
    def fit(self,x,y):
        assert x.shape[1]==217 and x.dtype==np.dtype('<f4')
        self.mean=float(np.mean(y));self.calls.append({'parameters':self.params.copy(),'training_rows':[int(v)-1 for v in x[:,0]],'targets':y.copy()})
        if len(self.calls)==self.fail_on:raise RuntimeError('SYNTHETIC failed fit')
        return self
    def predict(self,x):return np.full(len(x),self.mean)


def release(root,monkeypatch):
    out=root/'fitting';audit=out/'independent-input-audit.json';m.write(audit,{'status':'pass','preparation_sha256':m.sha(out/'preparation.json')})
    review=out/'fit-approval.json';m.write(review,{'status':'approved-v13-thirty-matched-coverage-fits','maximum_fits':30,'preparation_sha256':m.sha(out/'preparation.json'),
        'runner_sha256':m.sha(m.__file__),'reviewed_at_utc':m.now(),'freeze_commit':'a'*40,'independent_input_audit':m.record(audit,out)})
    monkeypatch.setattr(m,'git_freeze',lambda b,c:None);monkeypatch.setattr(m,'ExtraTreesRegressor',SpyForest);SpyForest.calls=[];SpyForest.fail_on=None
    monkeypatch.setattr(m.v6,'estimator_fingerprint',lambda e:m.v12.digest({'parameters':e.params,'mean':e.mean}))
    return review


def test_exact30_spied_fits_matching_assessment_all1761_and_no_final_fit(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);done=m.fit(root,approval);stage=root/'fitting/fit-attempt-0000'
    assert done['complete'] and done['fits_attempted']==done['fits_completed']==len(SpyForest.calls)==30
    assert len(list((stage/'models').iterdir()))==30
    for seed in m.SEEDS:
        cp=m.read(stage/'predictions'/f'control-seed-{seed}.json');ap=m.read(stage/'predictions'/f'augmented-seed-{seed}.json')
        assert len(cp)==len(ap)==1761 and cp[0]['predicted_lut4']==ap[0]['predicted_lut4']==0
        assert [(p['formula'],p['fold']) for p in cp]==[(p['formula'],p['fold']) for p in ap]
        for fold in range(5):
            ci=next(i for i,j in enumerate(m.schedule()) if (j['seed'],j['view'],j['fold'])==(seed,'control',fold));ai=ci+5
            control=SpyForest.calls[ci];aug=SpyForest.calls[ai]
            assert set(control['training_rows'])=={i for i,p in enumerate(cp) if i<1713 and p['fold']!=fold}
            assert set(aug['training_rows'])=={i for i,p in enumerate(ap) if p['fold']!=fold}
            assert np.array_equal(control['targets'],np.array([cp[i]['lut4_count'] for i in control['training_rows']]))
    summary=m.read(stage/'summary.json');assert summary['scores']['control'][str(m.SEEDS[0])]['original1713']['pooled']['count']==1713
    with pytest.raises(ValueError,match='single fit attempt'):m.fit(root,approval)
    assert len(SpyForest.calls)==30


def test_failed_fit_retains_claim_failure_receipt_and_blocks_retry(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);SpyForest.fail_on=3
    with pytest.raises(RuntimeError,match='failed fit'):m.fit(root,approval)
    out=root/'fitting';done=m.read(out/'fit-attempt-0000/completion.json')
    assert done['complete'] is False and done['fits_attempted']==3 and done['fits_completed']==2
    assert (out/'fit-claim.json').exists() and (out/'fit-attempt-0000/receipts/03-start.json').exists()
    with pytest.raises(ValueError,match='single fit attempt'):m.fit(root,approval)


def test_review_must_follow_input_preparation(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);body=m.read(approval);body['reviewed_at_utc']='2000-01-01T00:00:00+00:00';approval.write_text(json.dumps(body))
    with pytest.raises(ValueError,match='reviewed30'):m.fit(root,approval)
    assert not (root/'fitting/fit-claim.json').exists() and not SpyForest.calls


def test_model_save_load_mismatch_aborts_before_scoring(prepared,monkeypatch):
    root,_,_=prepared;approval=release(root,monkeypatch);original=m.joblib.load
    def broken(path):
        e=original(path);e.mean+=1;return e
    monkeypatch.setattr(m.joblib,'load',broken)
    with pytest.raises(ValueError,match='roundtrip'):m.fit(root,approval)
    assert not (root/'fitting/fit-attempt-0000/predictions').exists()


def test_runtime_change_stops_next_slot(prepared,monkeypatch):
    root,source,_=prepared;approval=release(root,monkeypatch);original=SpyForest.fit
    def mutate(self,x,y):
        r=original(self,x,y)
        if len(self.calls)==1:source.write_text('SYNTHETIC mutation')
        return r
    monkeypatch.setattr(SpyForest,'fit',mutate)
    with pytest.raises(ValueError,match='changed'):m.fit(root,approval)
    done=m.read(root/'fitting/fit-attempt-0000/completion.json');assert done['fits_attempted']==done['fits_completed']==1


def test_feature_worker_rejects_unclaimed_payload_before_any_extraction(tmp_path):
    with pytest.raises(FileNotFoundError):m.feature_worker({'root':str(tmp_path),'formula':'xor(in0,in1)'})


def graph_archive():
    """Synthetic hand-built32xor graph; no Yosys and no study inputs."""
    from isaforge import graph_features_v5 as g,masterrtl_baseline as sog,structural_features_v5 as sem
    from isaforge.mapping_features_v6 import feature_vector
    from isaforge.rtl import generate_rtl
    formula='xor(in0,in1)';tool={'version':'SYNTHETIC','executable_sha256':'a'*64};sub='c'*64;collection='/SYNTHETIC'
    gc={'schema':g.SCHEMA,'pipeline':g.PIPELINE,'tool':tool,'runtime_source_sha256':g.source_hashes(),'feature_columns':list(g.CHANNEL_COLUMNS),'scope':'generic combinational synthesis; no ABC, target mapping or measured labels'}
    sc={'pipeline':sog.PIPELINE,'tool':{**tool,'executable':'yosys'},'runtime_source_sha256':sog._source_hashes(),'feature_columns':list(sog.FEATURE_COLUMNS),'weights':sog.WEIGHTS}
    key=m.hashlib.sha256(json.dumps({'formula':formula,'context':gc},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    skey=m.hashlib.sha256(json.dumps({'formula':formula,**sc},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    ports={'in0':{'direction':'input','bits':list(range(2,34))},'in1':{'direction':'input','bits':list(range(34,66))},'result':{'direction':'output','bits':list(range(66,98))}}
    cells={str(i):{'type':'$_XOR_','connections':{'A':[i+2],'B':[i+34],'Y':[i+66]},'port_directions':{'A':'input','B':'input','Y':'output'}} for i in range(32)}
    graph={'modules':{'candidate':{'ports':ports,'cells':cells}}};word={'modules':{'candidate':{'ports':ports,'cells':{}}}};channel=g.channel_features(graph,word);sv,counts=sog.netlist_features(graph)
    cache='cache/'+sub;generic=cache+'/generic/'+key;sg=cache+'/sog/'+skey;files={}
    def put(n,v):files[n]=(json.dumps(v,sort_keys=True)+'\n').encode() if not isinstance(v,str) else v.encode()
    for folder in (generic,sg):put(folder+'/candidate.v',generate_rtl(formula))
    put(generic+'/extract.ys',g.PIPELINE);put(generic+'/extract.log','SYNTHETIC');put(generic+'/graph.json',graph);put(generic+'/word.json',word)
    hashes=lambda folder:{n.rsplit('/',1)[1]:m.hashlib.sha256(b).hexdigest() for n,b in files.items() if n.startswith(folder+'/')}
    put(generic+'/features.json',{'formula':formula,'cache_key':key,'context':gc,'feature_columns':list(g.CHANNEL_COLUMNS),'feature_values':channel.tolist(),'files_sha256':hashes(generic)})
    absolute=Path(collection)/'features/attempt-0000'/sg
    from isaforge.synthesis import _yosys_quote
    put(sg+'/sog.ys',f'read_verilog {_yosys_quote(absolute/"candidate.v")}\n{sog.PIPELINE}\ncheck -assert\nwrite_json {_yosys_quote(absolute/"sog.json")}\nwrite_verilog {_yosys_quote(absolute/"sog.v")}\nstat\n')
    put(sg+'/sog.log','SYNTHETIC');put(sg+'/sog.json',graph);put(sg+'/sog.v','SYNTHETIC')
    put(sg+'/features.json',{'formula':formula,'cache_key':skey,'context':sc,'feature_values':sv,'primitive_cell_counts':counts,'files_sha256':hashes(sg)})
    features=sem.feature_dict(formula);values=np.concatenate((sv,channel,channel,np.zeros(len(channel)),[features[n] for n in sem.FEATURE_NAMES],feature_vector(graph)))
    row={'formula':formula,'normalized_formula':formula,'cache_subdir':sub,'original_cache_key':key,'normalized_cache_key':key,'sog_cache_key':skey,'values':values.tolist(),'original_graph_sha256':m.hashlib.sha256(files[generic+'/graph.json']).hexdigest(),'mapping_source_sha256':m.v6.source_hashes()['mapping_features_v6.py']}
    for p,folder in [('original',generic),('normalized',generic),('sog',sg)]:row[p+'_manifest_sha256']=m.hashlib.sha256(files[folder+'/features.json']).hexdigest()
    return files,row,tool,collection


def zipped(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    stream.seek(0);return zipfile.ZipFile(stream)


def test_saved_handgraph_reconstructs336_and_selected217_without_native():
    files,r,tool,collection=graph_archive()
    with zipped(files) as z:values,native=m.replay_feature_record(z,r,tool,collection)
    assert len(values)==336 and len(native)==2 and len(values[m.v6.mapping_indices()])==217


@pytest.mark.parametrize('poison',['script','rtl','word','graph','values','source','normalization'])
def test_reauthenticated_feature_poisons_fail(poison):
    files,r,tool,collection=graph_archive();folder='cache/'+r['cache_subdir']+'/generic/'+r['original_cache_key']
    if poison in ('script','rtl','word','graph'):
        name={'script':'extract.ys','rtl':'candidate.v','word':'word.json','graph':'graph.json'}[poison]
        if poison=='script':files[folder+'/'+name]=b'abc\n'
        elif poison=='rtl':files[folder+'/'+name]=b'module POISON; endmodule\n'
        else:
            body=json.loads(files[folder+'/'+name]);body['modules']['candidate']['cells']={'POISON':{'type':'$POISON'}};files[folder+'/'+name]=json.dumps(body).encode()
        manifest=json.loads(files[folder+'/features.json']);manifest['files_sha256'][name]=m.hashlib.sha256(files[folder+'/'+name]).hexdigest();files[folder+'/features.json']=json.dumps(manifest).encode()
    elif poison=='values':r['values'][0]+=1
    elif poison=='source':r['mapping_source_sha256']='f'*64
    else:r['normalized_formula']='add(in0,in1)'
    with zipped(files) as z:
        with pytest.raises((ValueError,KeyError)):m.replay_feature_record(z,r,tool,collection)


@pytest.fixture
def feature_plan(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'ROOT',tmp_path);root=tmp_path/'SYNTHETIC';root.mkdir();source=tmp_path/'source.py';source.write_text('# SYNTHETIC')
    for path,body in [('preparation.json',{}),('measurement-tools.json',{}),('measurements/completion.json',{}),('measurements/attempt-0000/labels.json',[])]:m.write(root/path,body)
    raw=root/'measurements/attempt-0000/raw-evidence.zip';raw.write_bytes(b'SYNTHETIC NOT A ZIP')
    candidates=m.inputs.fixed_candidates();tools={'executables':{'yosys':{'version':'SYNTHETIC','sha256':'a'*64}},'environment':{'PATH':'SYNTHETIC','SDKROOT':'SYNTHETIC'}};old=tmp_path/'old-input.json';m.write(old,{'synthetic':True})
    bound={p:m.sha(p) for p in root.rglob('*') if p.is_file()}
    monkeypatch.setattr(m,'source_paths',lambda:[source]);monkeypatch.setattr(m,'old_inputs',lambda:({'frozen_tool':{'version':'SYNTHETIC','executable_sha256':'a'*64}},None,[old]))
    monkeypatch.setattr(m,'measurement_inputs',lambda r:(copy.deepcopy(candidates),{c['formula']:1 for c in candidates},copy.deepcopy(tools),bound.copy()))
    monkeypatch.setattr(m.v12,'runtime',lambda:{'synthetic':True,'files':[{'path':str(source),'sha256':m.sha(source)}]})
    m.prepare_features(root);return root,source


def feature_release(root,monkeypatch):
    report=root/'independent-measurement-audit.json';m.write(report,{'schema':'isaforge-v13-independent-measurement-audit-v1','status':'pass','complete':True,
        'completion_sha256':m.sha(root/'measurements/completion.json'),'labels_sha256':m.sha(root/'measurements/attempt-0000/labels.json'),
        'raw_archive_sha256':m.sha(root/'measurements/attempt-0000/raw-evidence.zip')})
    approval=root/'feature-approval.json';m.write(approval,{'status':'approved-v13-forty-eight-feature-extractions','feature_plan_sha256':m.sha(root/'feature-plan.json'),
        'measurement_completion_sha256':m.sha(root/'measurements/completion.json'),'runner_sha256':m.sha(m.__file__),'maximum_extractions':48,
        'reviewed_at_utc':m.now(),'freeze_commit':'a'*40,'independent_measurement_audit':m.record(report,root)})
    class Collector:
        @staticmethod
        def validate_tools(tools):pass
    monkeypatch.setattr(m,'measurement_collector',lambda r:(Collector,'v13b'));monkeypatch.setattr(m,'git_freeze',lambda b,c:None);monkeypatch.setattr(m,'feature_guard',lambda s:None)
    return approval


class SyntheticOwner:
    events=[]
    def __init__(self,tools):pass
    def cancel(self):self.events.append('cancel')


def test_feature_plan_exact48_and_no_native_or_overwrite(feature_plan):
    root,source=feature_plan;plan,candidates,targets,tools,b=m.validate_feature_plan(root)
    assert len(candidates)==48 and plan['policy']['candidate_extractions']==48 and plan['policy']['native_upper_bound']
    with pytest.raises(ValueError,match='Fresh'):m.prepare_features(root)


def test_exact48_spied_candidate_extractions_and_separate96_channel_counter(feature_plan,monkeypatch):
    root,_=feature_plan;approval=feature_release(root,monkeypatch);calls=[]
    import measure_v10_csd_hardware as owned
    monkeypatch.setattr(owned,'HardwareWorkers',SyntheticOwner)
    def worker(payload,log,owner):
        calls.append(copy.deepcopy(payload))
        cache=Path(payload['cache']);cache.mkdir(parents=True)
        for name in ('SYNTHETIC-generic.ys','SYNTHETIC-sog.ys'):(cache/name).write_text('# SYNTHETIC')
        return {'formula':payload['formula'],'values':[0.]*336}
    monkeypatch.setattr(m,'run_feature_worker',worker)
    done=m.extract_features(root,approval)
    assert done['complete'] and done['completed_extractions']==len(calls)==48 and done['native_graph_invocations']==96
    assert (root/'feature-claim.json').exists() and (root/'features/attempt-0000/raw-evidence.zip').exists()
    assert all(set(p)=={'root','claim_sha256','formula','cache','frozen_tool','result'} for p in calls)
    with pytest.raises(ValueError,match='single approved'):m.extract_features(root,approval)


def test_feature_interruption_cancels_before_executor_join_and_retains_evidence(feature_plan,monkeypatch):
    root,_=feature_plan;approval=feature_release(root,monkeypatch);events=[]
    import measure_v10_csd_hardware as owned
    class Owner:
        def __init__(self,tools):pass
        def cancel(self):events.append('cancel');raise RuntimeError('SYNTHETIC cleanup failure')
    class Pool:
        def __init__(self,**kwargs):pass
        def submit(self,*a):return object()
        def shutdown(self,**kwargs):events.append('join')
    def interrupted(values):raise KeyboardInterrupt('SYNTHETIC interruption')
    monkeypatch.setattr(owned,'HardwareWorkers',Owner);monkeypatch.setattr(m,'ThreadPoolExecutor',Pool);monkeypatch.setattr(m,'as_completed',interrupted)
    with pytest.raises(KeyboardInterrupt):m.extract_features(root,approval)
    assert events.index('cancel')<events.index('join')
    done=m.read(root/'features/completion.json');assert done['complete'] is False and done['completed_extractions']==0
    assert (root/'feature-claim.json').exists() and (root/'features/attempt-0000/raw-evidence.zip').exists()
    assert any(f.get('stage')=='cleanup' for f in done['failures'])


def test_measurement_review_label_digest_mismatch_blocks_features_before_claim(feature_plan,monkeypatch):
    root,_=feature_plan;approval=feature_release(root,monkeypatch);p=root/'independent-measurement-audit.json';body=m.read(p);body['labels_sha256']='f'*64;p.write_text(json.dumps(body))
    body=m.read(approval);body['independent_measurement_audit']=m.record(p,root);approval.write_text(json.dumps(body))
    with pytest.raises(ValueError,match='target/raw'):m.extract_features(root,approval)
    assert not (root/'feature-claim.json').exists()


def test_runtime_file_change_during_feature_stage_stops_later_workers(feature_plan,monkeypatch):
    root,source=feature_plan;approval=feature_release(root,monkeypatch);calls=[]
    import measure_v10_csd_hardware as owned
    monkeypatch.setattr(owned,'HardwareWorkers',SyntheticOwner)
    def worker(payload,log,owner):
        calls.append(payload['formula']);source.write_text('SYNTHETIC runtime corruption')
        return {'formula':payload['formula'],'values':[0.]*336}
    monkeypatch.setattr(m,'run_feature_worker',worker)
    with pytest.raises(ValueError,match='Incomplete feature'):m.extract_features(root,approval)
    done=m.read(root/'features/completion.json');assert done['complete'] is False and 0<len(calls)<=2
    assert (root/'feature-claim.json').exists()


def test_old_saved_matrix_and_tool_read_no_evaluation_targets_or_models(monkeypatch):
    original=m.read;seen=[]
    def guard(path):
        name=str(path)
        assert '/corpus/test/' not in name and '/corpus/calibration/' not in name and not name.endswith('.joblib')
        assert not any(x in name for x in ('point-predictions.json','summary.json','evaluation.json'))
        seen.append(name);return original(path)
    monkeypatch.setattr(m,'read',guard)
    data,x,paths=m.old_inputs()
    assert len(data['rows'])==1713 and x.shape==(1713,217) and set(data['frozen_tool'])=={'version','executable_sha256'}
    assert len(paths)==6 and len(seen)==3


def test_feature_tool_mismatch_rejected_before_any_native(feature_plan,monkeypatch):
    root,_=feature_plan
    monkeypatch.setattr(m,'old_inputs',lambda:({'frozen_tool':{'version':'DIFFERENT','executable_sha256':'f'*64}},None,[]))
    with pytest.raises(ValueError,match='mismatch'):m.validate_feature_plan(root)


def test_owned_feature_worker_whitelists_formula_and_blocks_cache_retry(tmp_path,monkeypatch):
    root=tmp_path/'SYNTHETIC';root.mkdir();c=m.inputs.fixed_candidates()[0];key=c['candidate_id'].split(':')[1];tool={'version':'SYNTHETIC','executable_sha256':'a'*64}
    m.write(root/'feature-plan.json',{'frozen_tool':tool});m.write(root/'candidates.json',[c]);m.write(root/'feature-claim.json',{'runner_sha256':m.sha(m.__file__),'feature_plan_sha256':m.sha(root/'feature-plan.json')})
    stage=root/'features/attempt-0000';payload={'root':str(root),'claim_sha256':m.sha(root/'feature-claim.json'),'formula':c['formula'],
        'cache':str(stage/'cache'/key),'result':str(stage/'workers'/key/'result.json'),'frozen_tool':tool,'lut4_count':9999999,'residual':-100000}
    calls=[]
    class Extractor:
        def __init__(self,cache,frozen_tool):assert frozen_tool==tool
        def matrix(self,rows,workers):
            calls.append(rows);assert rows==[{'formula':c['formula']}] and workers==1
            return np.zeros((1,336)),[{'formula':c['formula'],'values':[0.]*336}]
    monkeypatch.setattr(m.v6,'FeatureExtractor',Extractor);m.feature_worker(payload)
    assert len(calls)==1 and set(m.read(payload['result']))=={'formula','values'}
    with pytest.raises(ValueError,match='Fresh per-original'):m.feature_worker(payload)
    assert len(calls)==1
