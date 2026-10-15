"""Synthetic archive/lineage/secondary-metric contracts; no real target files."""
import copy
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
spec=importlib.util.spec_from_file_location('score_v8_applications',ROOT/'scripts/score_v8_applications.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    c=m.collector;root=tmp_path/'synthetic';root.mkdir();directory=root/'measurements';stage=directory/'attempt-0000';stage.mkdir(parents=True)
    monkeypatch.setattr(c,'ROOT',tmp_path);monkeypatch.setattr(c,'UNIQUE_COUNT',2);monkeypatch.setattr(c,'ROW_COUNT',3)
    def put(path,value):c.write(path,value)
    formulas=['add(in0,in1)','xor(in0,in1)'];tool={'version':'SYNTHETIC_TEST_ONLY','executable_sha256':'a'*64}
    rows=[{'benchmark':p,'candidate_id':str(i),'formula':f,'family':p,'primary_family':True,
        'traceTotalInstructions':100,'overlapSafeSaved':5+i,'runs':5} for i,(p,f) in enumerate([('a',formulas[0]),('a',formulas[1]),('b',formulas[0])])]
    programs=[{k:row[k] for k in ('benchmark','family','primary_family','traceTotalInstructions')} for row in [rows[0],rows[2]]]
    predictions={model:[{**{k:r[k] for k in ('benchmark','candidate_id','formula')},'model':model,'calibration_status':'point_only_application_pilot','predicted_lut4':1.,'upper_lut4':None,
        'outside_training_feature_ranges':None if model=='masterrtl_fixed' else 1,
        'tree_disagreement_lut4':None if model=='masterrtl_fixed' else .25} for r in rows] for model in m.MODELS}
    point={'files':[{'path':os.path.relpath(m.__file__,root),'sha256':m.sha(m.__file__)}],'models':{}}
    for model in m.MODELS:
        path=root/(model+'.json');put(path,predictions[model]);point['models'][model]={'predictions':{'path':path.name,'sha256':m.sha(path)}}
    inputs={'files':[],'frozen_tool':tool};review={'freeze_commit':'b'*40,'reviewed_at_utc':'2026-10-15T10:00:00+00:00'}
    put(root/'point-freeze.json',point);put(root/'input-seal.json',inputs);put(root/'label-approval.json',review)
    monkeypatch.setattr(c,'validate_approval',lambda *_:(point,inputs,rows,review))
    release={'schema':'isaforge-v8-application-label-release-v1','point_freeze_sha256':m.sha(root/'point-freeze.json'),
        'input_seal_sha256':m.sha(root/'input-seal.json'),'approval_sha256':m.sha(root/'label-approval.json'),'freeze_commit':review['freeze_commit'],
        'collector_sha256':m.sha(c.__file__),'verification_seed':c.VERIFY_SEED,'vectors_per_formula':2148,'workers':2,
        'released_at_utc':'2026-10-15T10:01:00+00:00'}
    put(root/'label-release.json',release)
    raw={};prefix=c.PREFIX+'attempt-0000/'
    def member(name,data):raw[prefix+name]=data
    rtl=m.verification_source(formulas).encode();rng=random.Random(c.VERIFY_SEED);pairs=list(itertools.product(m.BOUNDARIES,repeat=2))
    pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2048))
    vectors=('\n'.join(' '.join([f'{a:08x}',f'{b:08x}',*(['00000000']*2)]) for a,b in pairs)+'\n').encode()
    member('verification/batch-0000/verification.v',rtl);member('verification/batch-0000/vectors.txt',vectors)
    proofs=[{'verified':True,'formula_count':2,'vectors_per_formula':2148,'total_comparisons':4296,'random_seed':c.VERIFY_SEED,
        'v4_validation_override_sha256':m.sha(ROOT/'isaforge/v4_validation.py'),'rtl_sha256':m.digest(rtl),'vectors_sha256':m.digest(vectors)}]
    metrics=[];labels=[]
    for formula in formulas:
        folder='circuits/'+m.digest(formula.encode())[:20]+'/'
        parts={'candidate.v':m.generate_rtl(formula).encode(),'ice40.ys':b'SYNTHETIC_SCRIPT','ice40.log':b'SYNTHETIC_LOG',
            'ice40-netlist.json':json.dumps({'modules':{'candidate':{'cells':{'one':{'type':'SB_LUT4'}}}}}).encode()}
        metric={'formula':formula,'tool':tool['version'],'tool_sha256':tool['executable_sha256'],'measurement_source':'rtl_synthesis',
            'measured_at_utc':'2026-10-15T10:02:00+00:00','ice40_lut4_count':1,'ice40_carry_count':0,'ice40_cell_types':{'SB_LUT4':1}}
        for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256')]:
            member(folder+name,parts[name]);metric[key]=m.digest(parts[name])
        member(folder+'metrics.json',json.dumps(metric).encode());metrics.append(metric)
        labels.append({'formula':formula,'lut4_count':1,'carry_count':0,'rtl_sha256':metric['rtl_sha256'],
            'measurement_source':'rtl_synthesis','correctness_verified':True})
    put(stage/'labels.json',labels);put(stage/'unique-measurements.json',metrics);put(stage/'verification.json',proofs)
    done={'schema':'isaforge-v8-application-measurements-v1','complete':True,'failures':[],'attempt':'attempt-0000',
        'unique_original_formulas':2,'application_rows':3,'verification_seed':c.VERIFY_SEED,'vectors_per_formula':2148,
        'collector_sha256':m.sha(c.__file__),'release_sha256':m.sha(root/'label-release.json'),'frozen_tool':tool,
        'original_rtl_only':True,'legacy_measurements_reused':False,'scratch_directory':c.PREFIX+'attempt-0000',
        'completed_at_utc':'2026-10-15T10:03:00+00:00','verification_batch_sizes':[2]}
    def rebuild():
        for name,key in [('labels.json','labels_sha256'),('unique-measurements.json','unique_measurements_sha256'),('verification.json','verification_sha256')]:done[key]=m.sha(stage/name)
        put(stage/'completion.json',done);put(directory/'completion.json',done)
        archive=directory/'raw-evidence.zip'
        with zipfile.ZipFile(archive,'w') as stream:
            for name,data in raw.items():stream.writestr(name,data)
        put(directory/'raw-evidence.json',{'schema':'isaforge-v8-original-raw-evidence-v1','archive':archive.name,
            'archive_sha256':m.sha(archive),'completion_sha256':m.sha(directory/'completion.json'),'compiler_objects_included':False,
            'files':[{'path':name,'size':len(data),'sha256':m.digest(data)} for name,data in raw.items()]})
    rebuild()
    novelty={'schema':'isaforge-v8-input-novelty-v1','fresh_unique_formulas':2,'primary_rows_removed':0,'records':[
        {'formula':f,'matches':{'canonical':[],'original_or_normalized':[],'commutative_normalized':[],'ordered_skeleton':[],
            'mapping217_vector':[],'legacy_original336_vector':[],'legacy_rewritten336_vector':[]},
            'no_declared_identity_match':True,'strict_no_declared_match':True} for f in formulas]}
    put(root/'programs.json',programs);put(root/'novelty.json',novelty)
    return dict(root=root,stage=stage,directory=directory,rows=rows,labels=labels,predictions=predictions,
        programs=programs,novelty=novelty,done=done,release=release,raw=raw,rebuild=rebuild,proofs=proofs,metrics=metrics,point=point)


def test_valid_portable_archive_scores_all_program_rows_without_native_tools(evidence,monkeypatch):
    monkeypatch.setattr(m.collector.subprocess,'Popen',lambda *a,**k:pytest.fail('No native execution during scoring'))
    value=m.score(evidence['root'])
    assert value['primary']['difference_lut4']==0
    assert value['counts']['application_formula_rows']==3 and value['counts']['unique_original_formula_labels']==2
    assert value['provenance']['raw_netlists_recounted']==2
    assert value['secondary_diagnostics']['ood']['masterrtl_fixed']['missing_diagnostic_rows']==3
    assert not (m.collector.ROOT/'generated').exists()
    with pytest.raises(ValueError,match='immutable'):m.score(evidence['root'])


def test_approval_gate_precedes_fresh_label_reads(tmp_path,monkeypatch):
    monkeypatch.setattr(m.collector,'validate_approval',lambda *a:(_ for _ in ()).throw(ValueError('approval blocked')))
    monkeypatch.setattr(m,'read',lambda *a:pytest.fail('Fresh label reads forbidden before approval'))
    with pytest.raises(ValueError,match='approval blocked'):m.validate_measurements(tmp_path)


@pytest.mark.parametrize('field,value',[('complete',False),('failures',[{'stage':'synthesis'}]),('unique_original_formulas',1),('legacy_measurements_reused',True),('original_rtl_only',False),('scratch_directory','generated/other/attempt-0000'),('completed_at_utc','2026-10-15T09:00:00+00:00')])
def test_incomplete_or_reused_measurements_block_scoring(evidence,field,value):
    evidence['done'][field]=value;evidence['rebuild']()
    with pytest.raises(ValueError):m.validate_measurements(evidence['root'])


def test_labels_cannot_diverge_from_retained_metric_and_raw_count(evidence):
    evidence['labels'][0]['lut4_count']=2;m.collector.write(evidence['stage']/'labels.json',evidence['labels']);evidence['rebuild']()
    with pytest.raises(ValueError,match='raw resource count'):m.validate_measurements(evidence['root'])


def test_duplicate_labels_rejected_even_with_refreshed_hashes(evidence):
    m.collector.write(evidence['stage']/'labels.json',[evidence['labels'][0]]*2);evidence['rebuild']()
    with pytest.raises(ValueError,match='complete unique'):m.validate_measurements(evidence['root'])


def test_seeded_proof_cannot_be_replaced_with_other_vectors(evidence):
    key=next(k for k in evidence['raw'] if k.endswith('/vectors.txt'))
    data=evidence['raw'][key];evidence['raw'][key]=b'ffffffff'+data[8:]
    evidence['proofs'][0]['vectors_sha256']=m.digest(evidence['raw'][key])
    m.collector.write(evidence['stage']/'verification.json',evidence['proofs']);evidence['rebuild']()
    with pytest.raises(ValueError,match='vector seed'):m.validate_measurements(evidence['root'])


def test_archive_missing_original_rtl_is_rejected(evidence):
    key=next(k for k in evidence['raw'] if k.endswith('/candidate.v'));del evidence['raw'][key];evidence['rebuild']()
    with pytest.raises(ValueError,match='Required raw'):m.validate_measurements(evidence['root'])


def test_raw_netlist_is_recounted_after_all_hashes_are_consistently_updated(evidence):
    metric=evidence['metrics'][0];folder='circuits/'+m.digest(metric['formula'].encode())[:20]+'/'
    prefix=m.collector.PREFIX+'attempt-0000/'
    netlist=json.dumps({'modules':{'candidate':{'cells':{'one':{'type':'SB_LUT4'},'two':{'type':'SB_LUT4'}}}}}).encode()
    evidence['raw'][prefix+folder+'ice40-netlist.json']=netlist;metric['netlist_sha256']=m.digest(netlist)
    evidence['raw'][prefix+folder+'metrics.json']=json.dumps(metric).encode()
    m.collector.write(evidence['stage']/'unique-measurements.json',evidence['metrics']);evidence['rebuild']()
    with pytest.raises(ValueError,match='cell recount'):m.validate_measurements(evidence['root'])


def test_release_approval_commit_identity_cannot_change(evidence):
    evidence['release']['freeze_commit']='c'*40;m.collector.write(evidence['root']/'label-release.json',evidence['release'])
    evidence['done']['release_sha256']=m.sha(evidence['root']/'label-release.json');evidence['rebuild']()
    with pytest.raises(ValueError,match='Release identity'):m.validate_measurements(evidence['root'])


def test_scorer_must_be_bound_to_original_approved_sources(evidence):
    evidence['point']['files']=[]
    with pytest.raises(ValueError,match='Scorer source'):m.validate_measurements(evidence['root'])


def test_novel_secondary_cannot_replace_a_missing_primary_family(evidence):
    n=copy.deepcopy(evidence['novelty']);r=n['records'][0]
    r['matches']['canonical']=[r['formula']];r['no_declared_identity_match']=False;r['strict_no_declared_match']=False
    result=m.diagnostics(evidence['rows'],evidence['labels'],evidence['predictions'],evidence['programs'],n)
    secondary=result['novelty']['strict_no_declared_match']
    assert secondary['missing_primary_families']==['b'] and not secondary['family_complete']
    assert secondary['complete_family_primary_difference_lut4'] is None
    assert secondary['scores']['mapping_v6']['complete_primary_family_macro_mae_lut4'] is None


def test_inconsistent_novelty_or_shared_ood_is_rejected(evidence):
    n=copy.deepcopy(evidence['novelty']);n['records'][0]['strict_no_declared_match']=False
    with pytest.raises(ValueError,match='novelty flags'):m.diagnostics(evidence['rows'],evidence['labels'],evidence['predictions'],evidence['programs'],n)
    predictions=copy.deepcopy(evidence['predictions']);predictions['mapping_v6'][2]['outside_training_feature_ranges']=2
    with pytest.raises(ValueError,match='Shared formula'):m.diagnostics(evidence['rows'],evidence['labels'],predictions,evidence['programs'],evidence['novelty'])
