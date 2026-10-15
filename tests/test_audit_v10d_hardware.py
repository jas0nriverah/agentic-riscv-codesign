"""Synthetic portable V10d audit contracts; no native tools or collector imports."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path);module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m = load('audit_v10d_hardware', ROOT/'scripts/audit_v10d_hardware.py')
old_tests = load('v10_audit_test_fixtures', ROOT/'tests/test_audit_v10_hardware.py')


class Word:
    def __init__(self):
        self.a=list(range(2,34));self.b=list(range(34,66));self.next=66;self.cells={};self.result=self.a
    def constant(self,value,width=32): return [str((value>>i)&1) for i in range(width)]
    def op(self,kind,a,b,select=None):
        output=list(range(self.next,self.next+32));self.next+=32
        connections={'A':list(a),'B':list(b),'Y':output}
        if kind=='$mux': params={'WIDTH':32};connections['S']=list(select)
        else: params={'A_SIGNED':0,'B_SIGNED':0,'A_WIDTH':len(a),'B_WIDTH':len(b),'Y_WIDTH':32}
        self.cells[str(len(self.cells))]={'type':kind,'parameters':params,'connections':connections,
            'port_directions':{p:'output' if p=='Y' else 'input' for p in connections}}
        return output
    def data(self):
        return json.loads(json.dumps({'creator':'SYNTHETIC','modules':{'candidate':{'attributes':{},'ports':{
            'in0':{'direction':'input','bits':self.a},'in1':{'direction':'input','bits':self.b},
            'result':{'direction':'output','bits':self.result}},'cells':self.cells,'netnames':{}}}}))


def word_case(constant,context):
    word=Word();operand=word.a
    if context=='masked_sub_before_product': operand=word.op('$and',operand,word.constant(63))
    if context in ('sub_before_product','masked_sub_before_product'): operand=word.op('$sub',operand,word.b)
    word.result=word.op('$mul',operand,word.constant(constant))
    if context=='add_after_product': word.result=word.op('$add',word.result,word.b)
    return word.data()


@pytest.mark.parametrize('context',m.independent.CONTEXTS)
def test_independent_concrete_word_dag_matches_fixed_unsigned_oracle(context):
    samples=m.independent.vectors()
    for constant in (11,511,2044):
        assert m.word_samples(word_case(constant,context),samples)==m.independent.expected_values(constant,context,samples)


def test_actual_slice_mux_shift_provenance_and_result_bit_order():
    word=Word();shifted=['0']*9+word.a[:23]
    word.result=word.op('$sub',word.op('$mux',word.a,shifted,select=['1']),word.a)
    samples=[(0,0),(1,1),(0xffffffff,7),(0x80000001,99)]
    assert m.word_samples(word.data(),samples)==[(511*a)&0xffffffff for a,b in samples]
    graph=word.data();graph['modules']['candidate']['ports']['result']['bits'].reverse()
    assert m.word_samples(graph,samples)!=[(511*a)&0xffffffff for a,b in samples]
    shifted_word=Word();shifted_word.result=shifted_word.op('$shl',shifted_word.a,shifted_word.constant(32,6))
    assert m.word_samples(shifted_word.data(),samples)==[0]*len(samples)


@pytest.mark.parametrize('poison',['signed','unknown-bit','bool-bit','unknown-cell','cycle','double-driver'])
def test_word_json_unknown_or_signed_semantics_fail_closed(poison):
    graph=word_case(11,'direct_product');cell=graph['modules']['candidate']['cells']['0']
    if poison=='signed': cell['parameters']['A_SIGNED']=1
    elif poison=='unknown-bit': cell['connections']['A'][0]='x'
    elif poison=='bool-bit': cell['connections']['A'][0]=True
    elif poison=='unknown-cell': cell['type']='$div'
    elif poison=='cycle': cell['connections']['A']=list(cell['connections']['Y'])
    else: graph['modules']['candidate']['cells']['double']=copy.deepcopy(cell)
    with pytest.raises(ValueError): m.word_samples(graph,[(1,0)])


def test_wrong_coefficient_proving_equal_to_itself_still_disagrees_with_oracle():
    graph=word_case(13,'direct_product');samples=[(1,0),(0xffffffff,1),(7,9)]
    assert m.algebra.prove_pair(graph,graph)['proved'] is True
    assert m.word_samples(graph,samples)!=m.independent.expected_values(11,'direct_product',samples)


def test_unique_json_keys_and_explicit_shared_proof_scope_no_collector_imports():
    with pytest.raises(ValueError): m.loads('{"a":1,"a":2}')
    tree=ast.parse(Path(m.__file__).read_text())
    modules={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    modules.update(alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names)
    assert not any(name and ('measure_' in name or 'isaforge' in name or name in ('subprocess','numpy','z3')) for name in modules)
    assert 'not an independent universal proof' in m.__doc__


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    # Reuse the prior auditor's independently hand-built mapped fixture only.
    old_root,old_content,metric,old_done,*_=old_tests.evidence.__wrapped__(tmp_path,monkeypatch)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    checker=tmp_path/'scripts/prove_v10_rtl_algebra.py';checker.write_bytes(Path(m.algebra.__file__).read_bytes())
    monkeypatch.setattr(m.algebra,'__file__',str(checker))
    collector=tmp_path/'scripts/measure_v10d_csd_hardware.py';collector.write_bytes(b'SYNTHETIC collector identity, never imported')
    root=tmp_path/'v10d';shutil.copytree(old_root,root)
    # Small dependency fixture for contract speed; full2148 diagnostics tested above.
    samples=[(0,0),(1,0),(0xffffffff,1),(0x80000001,0x7fffffff)]
    monkeypatch.setattr(m.independent,'vectors',lambda:samples)
    def dump(path,value): path.write_text(json.dumps(value,indent=2)+'\n')
    def rec(path):
        import os
        return {'path':os.path.relpath(path,root),'sha256':m.sha(path.read_bytes())}
    pairs=m.read(root/'pairs.json');tools=m.read(root/'tools.json');source=m.read(old_root/'preparation.json')
    history_stage=old_root/'measurements/attempt-0000'
    old_proofs=[{'pair_id':pair['pair_id'],'proved':i<16,'status':'proved' if i<16 else 'timeout'} for i,pair in enumerate(pairs)]
    dump(history_stage/'rtl-equivalence.json',old_proofs);dump(history_stage/'arm-measurements.json',[])
    old_done.update({'universal_actual_rtl_pairs_proved':16,'fresh_synthesis_jobs_completed':0,
        'rtl_equivalence_sha256':m.sha((history_stage/'rtl-equivalence.json').read_bytes()),
        'arm_measurements_sha256':m.sha((history_stage/'arm-measurements.json').read_bytes())})
    dump(history_stage/'completion.json',old_done);dump(old_root/'measurements/completion.json',old_done)
    old_raw=m.read(history_stage/'raw-evidence.json');old_raw['completion_sha256']=m.sha((history_stage/'completion.json').read_bytes());dump(history_stage/'raw-evidence.json',old_raw)
    monkeypatch.setattr(m,'V10C_NATIVE_COMPLETION_SHA',m.sha((old_root/'measurements/completion.json').read_bytes()))
    review_root=tmp_path/'results/2026-10-15-v10-hardware-preparation';review_root.mkdir(parents=True)
    dump(review_root/'independent-algebra-review.json',{'status':'go-within-accepted-unsigned-json-scope','checker_sha256':m.sha(checker.read_bytes())})
    for name in ('evidence-manifest.json','synthetic-algebra-evidence.zip','synthetic-timing-evidence.zip'):
        (review_root/name).write_bytes(b'SYNTHETIC retained support evidence')
    monkeypatch.setattr(m,'V10C_PREPARATION_SHA',m.sha((old_root/'preparation.json').read_bytes()))
    prior=[]
    for pair in pairs:
        prior.append({'formula':pair['formula'],'ice40_lut4_count':64,'ice40_carry_count':64,
            'rtl_sha256':pair['arms']['original']['rtl']['sha256'],'tool_sha256':tools['executables']['yosys']['sha256']})
    dump(root/'prior-v9-originals.json',prior);dump(root/'premeasurement-amendment.json',{
        'schema':'isaforge-v10d-proof-method-amendment-v1','same_inputs_rtl_csd_source_proofs_tools':True,
        'new_area_outcomes_read':False,'old_run_marked_complete':False,'model_fits':0,
        'previous_input_commit':'f7e04033a4bf52d5095dc7027d1d8a21a4f6e884',
        'previous_native_commit':'888dc3ea6cdc4403d8cbfab38a51771c0fbf07d8',
        'previous_native_outcome':{'pairs':32,'sat_proved':16,'sat_timeout':16,'area_measurements':0}})
    recipe={'schema':'isaforge-v10d-csd-hardware-recipe-v1','pairs':32,'arms':list(m.ARMS),'frontend_jobs':64,'frontend_timeout_seconds':60,
        'frontend_middle_commands':m.FRONTEND_COMMANDS,'required_proof_pairs':32,'all_proofs_before_any_area':True,'fresh_synthesis_jobs':64,
        'measurement_timeout_seconds_per_arm':360,'workers':2,'verification_seed':m.independent.SEED,'vectors_per_arm':2148,
        'alternatives':1,'filtering':False,'replacements':False,'automatic_retries':False,'model_fits':0,'limits':'SYNTHETIC'}
    dump(root/'recipe.json',recipe)
    files=[]
    for entry in source['files']:
        files.append(rec((old_root/entry['path']).resolve()))
    files += [rec(path) for path in (old_root/'preparation.json',collector,checker)]
    files += [rec(path) for path in [old_root/'measurements/completion.json',old_root/'measurement-approval.json',old_root/'label-release.json',*history_stage.iterdir(),*review_root.iterdir()] if path.is_file()]
    files += [rec(path) for path in root.rglob('*') if path.is_file() and 'measurements' not in path.parts and path.name not in ('preparation.json','measurement-approval.json','label-release.json')]
    unique={entry['path']:entry for entry in files}
    prep={'schema':'isaforge-v10d-csd-hardware-preparation-v1','status':'prepared-inputs-only','new_native_jobs':0,
        'new_area_outcomes_read':False,'model_fits':0,'files':list(unique.values()),'pairs':rec(root/'pairs.json'),'tools':rec(root/'tools.json'),
        'recipe':rec(root/'recipe.json'),'source_preparation':rec(old_root/'preparation.json'),
        'previous_native_completion':rec(old_root/'measurements/completion.json'),
        'prior_v9_originals':rec(root/'prior-v9-originals.json'),'amendment':rec(root/'premeasurement-amendment.json')}
    dump(root/'preparation.json',prep)
    approval={'status':'approved-v10d-csd-hardware-measurements','freeze_commit':'a'*40,'preparation_sha256':m.sha((root/'preparation.json').read_bytes()),
        'recipe_sha256':prep['recipe']['sha256'],'pairs_sha256':prep['pairs']['sha256'],'collector_sha256':m.sha(collector.read_bytes()),'checker_sha256':m.sha(checker.read_bytes())}
    dump(root/'measurement-approval.json',approval)
    base=m.PurePosixPath('/nonexistent/original machine/repository')
    release={'schema':'isaforge-v10d-csd-hardware-release-v1','attempt':'attempt-0000','freeze_commit':'a'*40,
        'preparation_sha256':approval['preparation_sha256'],'approval_sha256':m.sha((root/'measurement-approval.json').read_bytes()),
        'collector_sha256':approval['collector_sha256'],'checker_sha256':approval['checker_sha256'],
        'tools_sha256':m.sha((root/'tools.json').read_bytes()),'prior_v9_originals_sha256':m.sha((root/'prior-v9-originals.json').read_bytes()),
        'pairs':32,'frontend_jobs':64,'fresh_synthesis_jobs':64,'workers':2,'verification_seed':m.independent.SEED,'vectors_per_arm':2148,
        'collection_repository':str(base),'native_environment':{'PATH':'/nonexistent/yosys/bin:/usr/bin:/bin','ABC':tools['executables']['abc']['path'],'LANG':'C','LC_ALL':'C','TZ':'UTC'}}
    dump(root/'label-release.json',release)
    content={name:(root/name).read_bytes() for name in ('pairs.json','tools.json','recipe.json','preparation.json','prior-v9-originals.json','premeasurement-amendment.json')}
    content.update({'approval.json':(root/'measurement-approval.json').read_bytes(),'release.json':(root/'label-release.json').read_bytes(),
        'collector-source.py':collector.read_bytes(),'checker-source.py':checker.read_bytes(),
        'frozen-measurement-source.py':(tmp_path/'scripts/measure_v10_csd_hardware.py').read_bytes()})
    for pair in pairs: content['source-proofs/'+pair['pair_id'].split(':')[1]+'/proof.json']=(root/pair['proof']['path']).read_bytes()
    frontends=[];graphs={}
    for pair in pairs:
        for arm in m.ARMS:
            stem='frontend/'+pair['pair_id'].split(':')[1]+'/'+arm+'/';path=base/m.PREFIX/'attempt-0000'/stem/'candidate.v'
            graph=word_case(pair['constant_u32'],pair['context']);graph['creator']=tools['executables']['yosys']['version']
            graph['modules']['candidate']['attributes']['src']=str(path)+':1.1-9.1';graphs[pair['pair_id'],arm]=graph
            content.update({stem+'candidate.v':(root/pair['arms'][arm]['rtl']['path']).read_bytes(),
                stem+'frontend.ys':m.frontend_script(base,'attempt-0000',pair['pair_id'],arm).encode(),
                stem+'frontend.log':f"Parsing Verilog input from `{path}' to AST representation.\n".encode(),stem+'word.json':json.dumps(graph).encode()})
            row={'schema':'isaforge-v10d-frontend-v1','pair_id':pair['pair_id'],'arm':arm,'success':True,'status':'complete',
                'execution':{'returncode':0,'timed_out':False,'elapsed_seconds':.01},'started_at_utc':'2026-10-15T12:00:01+00:00',
                'completed_at_utc':'2026-10-15T12:00:02+00:00','yosys':tools['executables']['yosys'],'error':None,
                'command':[tools['executables']['yosys']['path'],'-s',str(path.with_name('frontend.ys'))],
                **{key:m.sha(content[stem+name]) for name,key in [('candidate.v','candidate_rtl_sha256'),('frontend.ys','script_sha256'),('frontend.log','log_sha256'),('word.json','word_json_sha256')]}}
            frontends.append(row);content[stem+'frontend.json']=json.dumps(row).encode()
    proofs=[]
    for pair in pairs:
        result=m.loads(json.dumps(m.algebra.prove_pair(*(graphs[pair['pair_id'],arm] for arm in m.ARMS))))
        row={'schema':'isaforge-v10d-actual-rtl-proof-v1','pair_id':pair['pair_id'],'proved':True,'checker_sha256':approval['checker_sha256'],
            'checker_result':result,'frontend_records':{arm:next(f for f in frontends if (f['pair_id'],f['arm'])==(pair['pair_id'],arm)) for arm in m.ARMS},
            'started_at_utc':'2026-10-15T12:00:03+00:00','completed_at_utc':'2026-10-15T12:00:04+00:00','elapsed_seconds':.01,'error':None}
        proofs.append(row)
    pair=pairs[0];stem='circuits/'+pair['pair_id'].split(':')[1]+'/original/'
    old_stem=stem
    for name in ('candidate.v','ice40-netlist.json'):
        content[stem+name]=old_content[old_stem+name]
    content[stem+'ice40.ys']=m.measurement_script(base,'attempt-0000',stem,samples).encode()
    expected=m.independent.expected_values(11,'direct_product',samples)
    content[stem+'vectors.txt']=''.join(f'{a:08x} {b:08x} {y:08x}\n' for (a,b),y in zip(samples,expected)).encode()
    content[stem+'observations.txt']=''.join(f'{y:08x} {y:08x}\n' for y in expected).encode()
    path=base/m.PREFIX/'attempt-0000'/stem/'candidate.v';alias='/nonexistent/yosys/bin/../share/yosys/ice40/cells_sim.v'
    content[stem+'ice40.log']=(''.join(f"Eval result: \\result = 32'{y:032b}.\n" for y in expected)+
        'Running ABC command: "<yosys-exe-dir>/yosys-abc" -s -f <abc-temp-dir>/abc.script 2>&1\n'+
        f"Parsing Verilog input from `{path}' to AST representation.\nParsing Verilog input from `{alias}' to AST representation.\n").encode()
    metric['measured_at_utc']='2026-10-15T12:00:07+00:00';metrics=[metric]
    gate={'schema':'isaforge-v10d-area-gate-v1','measurement_started_at_utc':'2026-10-15T12:00:05+00:00'}
    start={'pair_id':pair['pair_id'],'arm':'original','started_at_utc':'2026-10-15T12:00:06+00:00'}
    done={'schema':'isaforge-v10d-csd-hardware-measurements-v1','complete':False,'attempt':'attempt-0000','failures':[{'phase':'SYNTHETIC other63arms missing'}],
        'pair_count':32,'frontend_jobs_completed':64,'successful_frontend_jobs':64,'proof_records':32,'universal_actual_rtl_pairs_proved':32,
        'fresh_synthesis_jobs_completed':1,'planned_fresh_synthesis_jobs':64,'workers':2,'vectors_per_arm':2148,'verification_seed':m.independent.SEED,
        'new_estimator_fits':0,'legacy_measurements_reused':False,'scratch_directory':m.PREFIX+'attempt-0000',
        'measurement_started_at_utc':gate['measurement_started_at_utc'],'summary_sha256':None,
        **{key:release[key] for key in ('preparation_sha256','approval_sha256','collector_sha256','checker_sha256','tools_sha256','prior_v9_originals_sha256')},
        'release_sha256':m.sha((root/'label-release.json').read_bytes())}
    stage=root/'measurements/attempt-0000'
    def persist():
        for f in frontends:
            fs='frontend/'+f['pair_id'].split(':')[1]+'/'+f['arm']+'/'
            for name,key in [('candidate.v','candidate_rtl_sha256'),('frontend.ys','script_sha256'),('frontend.log','log_sha256'),('word.json','word_json_sha256')]:
                f[key]=m.sha(content[fs+name])
            content[fs+'frontend.json']=json.dumps(f).encode()
        for proof in proofs: content['algebra-proofs/'+proof['pair_id'].split(':')[1]+'/proof.json']=json.dumps(proof).encode()
        for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256'),('vectors.txt','vectors_sha256'),('observations.txt','observations_sha256')]: metric[key]=m.sha(content[stem+name])
        for name,value,key in [('frontends.json',frontends,'frontends_sha256'),('algebra-proofs.json',proofs,'algebra_proofs_sha256'),('arm-measurements.json',metrics,'arm_measurements_sha256')]:
            dump(stage/name,value);content[name]=(stage/name).read_bytes();done[key]=m.sha(content[name])
        gate['all32_proof_sha256']=done['algebra_proofs_sha256'];gate['all64_frontend_sha256']=done['frontends_sha256'];dump(stage/'measurement-gate.json',gate)
        content['measurement-gate.json']=(stage/'measurement-gate.json').read_bytes();done['measurement_gate_sha256']=m.sha(content['measurement-gate.json'])
        start['measurement_gate_sha256']=done['measurement_gate_sha256'];content[stem+'measurement-start.json']=json.dumps(start).encode()
        content['measurement-start/'+pair['pair_id'].split(':')[1]+'/original.json']=content[stem+'measurement-start.json']
        dump(stage/'completion.json',done);dump(root/'measurements/completion.json',done);content['completion.json']=(stage/'completion.json').read_bytes()
        with zipfile.ZipFile(stage/'raw-evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in content.items(): archive.writestr(m.PREFIX+'attempt-0000/'+name,data)
        dump(stage/'raw-evidence.json',{'schema':'isaforge-v10d-raw-evidence-v1','attempt':'attempt-0000','archive':'raw-evidence.zip',
            'archive_sha256':m.sha((stage/'raw-evidence.zip').read_bytes()),'completion_sha256':m.sha((stage/'completion.json').read_bytes()),
            'files':[{'path':m.PREFIX+'attempt-0000/'+name,'sha256':m.sha(data),'size':len(data)} for name,data in content.items()]})
    persist()
    return root,content,frontends,proofs,metric,done,gate,start,stem,persist


def test_portable_archive_with_all32_proofs_but_missing_arms_keeps_primary_null(evidence):
    root,*_=evidence;report=m.run(root)
    assert report['status']=='pass' and report['complete'] is False and report['summary'] is None and report['pairs']==[]
    assert report['rtl_pairs_proved_shared_checker']==32 and report['frontend_records_verified']==64 and report['arms_recounted']==1
    assert 'not an independent universal checker' in report['independence']


@pytest.mark.parametrize('poison',['frontend-rtl','frontend-script','frontend-json-source','frontend-signed','wrong-coefficient','proof-frontend','proof-gate','arm-start','arm-count','vectors','netlist','arm-total','fake-complete'])
def test_reauthenticated_lineage_chronology_and_measurement_poison_rejected(evidence,poison):
    root,content,frontends,proofs,metric,done,gate,start,stem,persist=evidence
    f=frontends[0];fs='frontend/'+f['pair_id'].split(':')[1]+'/'+f['arm']+'/'
    if poison=='frontend-rtl': content[fs+'candidate.v']+=b' changed RTL'
    elif poison=='frontend-script': content[fs+'frontend.ys']+=b'opt\n'
    elif poison=='frontend-json-source':
        graph=m.loads(content[fs+'word.json']);graph['modules']['candidate']['attributes']['src']='/wrong/candidate.v:1.1-9.1';content[fs+'word.json']=json.dumps(graph).encode()
    elif poison=='frontend-signed':
        graph=m.loads(content[fs+'word.json']);graph['modules']['candidate']['cells']['0']['parameters']['A_SIGNED']=1;content[fs+'word.json']=json.dumps(graph).encode()
    elif poison=='wrong-coefficient':
        for frontend in frontends[:2]:
            location='frontend/'+frontend['pair_id'].split(':')[1]+'/'+frontend['arm']+'/word.json'
            graph=m.loads(content[location]);graph['modules']['candidate']['cells']['0']['connections']['B']=[str((13>>i)&1) for i in range(32)];content[location]=json.dumps(graph).encode()
        # Even an updated equal/equal polynomial result cannot repair wrong semantics.
        a,b=[m.loads(content['frontend/'+f['pair_id'].split(':')[1]+'/'+arm+'/word.json']) for arm in m.ARMS]
        proofs[0]['checker_result']=m.loads(json.dumps(m.algebra.prove_pair(a,b)))
    elif poison=='proof-frontend': proofs[0]['frontend_records']['original']=copy.deepcopy(f);proofs[0]['frontend_records']['original']['word_json_sha256']='0'*64
    elif poison=='proof-gate': gate['measurement_started_at_utc']='2026-10-15T12:00:03+00:00';done['measurement_started_at_utc']=gate['measurement_started_at_utc']
    elif poison=='arm-start': start['started_at_utc']='2026-10-15T12:00:04+00:00'
    elif poison=='arm-count': metric['carry_count']=True
    elif poison=='vectors': content[stem+'vectors.txt']+=b'00000000 00000000 00000000\n'
    elif poison=='netlist':
        graph=m.loads(content[stem+'ice40-netlist.json']);graph['modules']['candidate']['ports']['result']['bits']=['0']*32;content[stem+'ice40-netlist.json']=json.dumps(graph).encode()
    elif poison=='arm-total':
        # Preserve current distinct row count and inject a count mismatch.
        done['fresh_synthesis_jobs_completed']=2
    else: done['complete']=True;done['failures']=[]
    persist()
    with pytest.raises(ValueError): m.run(root)


@pytest.mark.parametrize('dropped',['native-archive','native-proofs','review'])
def test_mandatory_historical_failure_and_review_bindings_cannot_be_dropped(evidence,dropped):
    root,*_=evidence;prep=m.read(root/'preparation.json')
    bindings={(root/entry['path']).resolve():entry['sha256'] for entry in prep['files']}
    source_path=(root/prep['source_preparation']['path']).resolve()
    target=(source_path.parent/'measurements/attempt-0000'/('raw-evidence.zip' if dropped=='native-archive' else 'rtl-equivalence.json')) if dropped!='review' else m.ROOT/'results/2026-10-15-v10-hardware-preparation/synthetic-algebra-evidence.zip'
    del bindings[target]
    with pytest.raises(ValueError): m.verify_history(root,prep,bindings,source_path,m.read(root/'pairs.json'),m.sha(Path(m.algebra.__file__).read_bytes()))


def test_complete_paired_summary_preserves_all32_lut_carry_and_prior_differences(evidence):
    root,*_=evidence;pairs=m.read(root/'pairs.json');prior=m.read(root/'prior-v9-originals.json');tools=m.read(root/'tools.json')
    metrics=[]
    for i,pair in enumerate(pairs):
        for arm in m.ARMS:
            metrics.append({'pair_id':pair['pair_id'],'arm':arm,'lut4_count':64+i+(3 if arm=='csd' else 0),
                'carry_count':64+(1 if arm=='csd' else 0)})
    rows,summary=m.paired_results(pairs,metrics,prior,tools)
    assert len(rows)==32 and summary['lut4']['count']==32 and summary['lut4']['mean']==3
    assert summary['carry_descriptive']['mean']==1 and summary['fresh_original_v9_lut4_disagreements']==31
    assert len(summary['by_constant_lut4'])==8 and len(summary['by_context_lut4'])==4
    with pytest.raises(ValueError): m.paired_results(pairs,metrics[:-1]+[metrics[0]],prior,tools)
