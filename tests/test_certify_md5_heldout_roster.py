"""Synthetic-only offline certificate checks; no historical outcome access."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts import certify_md5_heldout_roster as w


@pytest.fixture(autouse=True)
def prohibit_native_extraction_models_and_results(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Forbidden native/extraction/model entry point')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(w.lowering,'extract',forbidden)
    for name in ('extractCandidates','findPotentialCandidates','readProgram'):
        monkeypatch.setattr(w.lowering.discovery,name,forbidden)
    monkeypatch.setattr(w.lowering.interpreter,'verify_candidates',forbidden)
    for name in ('simulate','synthesize','verify_datapath'):
        monkeypatch.setattr(w.c.ProcessorEvaluator,name,forbidden)
    from isaforge.model import SpeedupPredictor
    from isaforge.ranking import SpeedupRanker
    for cls in (SpeedupPredictor,SpeedupRanker):
        for name in ('fit','predict'):
            monkeypatch.setattr(cls,name,forbidden)
    real_open = Path.open
    def checked_open(path,*args,**kwargs):
        assert not path.resolve().is_relative_to(w.SOURCE_ROOT/'results'), 'Real result/model files forbidden'
        assert 'measurements' not in path.parts and 'attempt-ledger' not in path.parts, 'Outcome files forbidden'
        return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',checked_open)


def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True)+'\n')


@pytest.fixture
def synthetic(tmp_path,monkeypatch):
    monkeypatch.setattr(w,'ROOT',tmp_path)
    base=tmp_path/w.BASE; folder=base/'discovery/attempt-000'
    folder.mkdir(parents=True)
    source='.type benchmark, @function\nbenchmark:\n'
    words=[]
    for index in range(12):
        shift=index+2; pc=index*12
        source+=f'\tslli a2,a1,{shift}\n\tadd a0,a0,a2\n\taddi a2,zero,0\n'
        words.extend([(pc,(shift<<20)|0x59613),(pc+4,0x00c50533),(pc+8,0x00000613)])
    source+='.size benchmark, .-benchmark\n'
    marked,sites=w.lowering.mark_assembly(source)
    (folder/'program.s').write_text(source);(folder/'marked.S').write_text(marked)
    (folder/'marked').mkdir();(folder/'original').mkdir()
    symbols=''.join(f'{site["site"]*4:08x} T __isaforge_begin_{site["site"]}\n'
                    f'{site["site"]*4+4:08x} T __isaforge_end_{site["site"]}\n' for site in sites)
    (folder/'marked/symbols.txt').write_text(symbols)
    (folder/'marked/disassembly.txt').write_text('00000000 <benchmark>:\n'+''.join(
        f' {pc:x}: {raw:08x} synthetic\n' for pc,raw in words))
    for rel in ('marked/firmware.hex','original/firmware.hex'):
        (folder/rel).write_text('00000000\n')
    plan={'workload':'nettle-md5','synthetic_public_only':True,
          'source_bindings':{name:w.c.sha(w.SOURCE_ROOT/name) for name in w.SOURCES[1:]}}
    plan['context_id']=w.c.digest(plan)
    rows=[]
    for i in range(12):
        rows.append(dict(name=f'candidate_{i:02d}',formula=f'add(in0,slli(in1,{i+2}))',
            occurrences=[dict(pcs=[hex(i*12),hex(i*12+4)],blockStart=hex(i*12),
                blockRuns=4,size=2,sites=[i*3,i*3+1],inputs=[10,11],output=10)]))
    discovery=dict(workload='nettle-md5',context_id=plan['context_id'],
        block_starts=[i*12 for i in range(12)],executable_candidates=rows,
        artifacts={'attempt-000/'+rel:w.c.sha(folder/rel) for rel in w.PUBLIC_FILES})
    save_json(base/'plan.json',plan);save_json(base/'discovery/discovery.json',discovery)
    prereg=tmp_path/w.PREREG;prereg.mkdir(parents=True)
    save_json(prereg/'independent-cohort-audit.json',{'synthetic':True,'admissible_groups':7})
    audit_sha=w.c.sha(prereg/'independent-cohort-audit.json')
    (prereg/'independent-cohort-audit.json.sha256').write_text(audit_sha+'\n')
    monkeypatch.setattr(w,'AUDIT_SHA256',audit_sha)
    roster=[{'name':r['name'],'formula':r['formula']} for r in rows]
    (prereg/'roster.json').write_bytes(w.compact(roster))
    roster_sha=w.c.sha(prereg/'roster.json');monkeypatch.setattr(w,'ROSTER_SHA256',roster_sha)
    protocol=dict(eligibility_pending=True,candidate_dispatch_enabled=False,new_pool_labels=0,
        historical_md5_labels_excluded=True,existing_context_id=plan['context_id'],
        roster={'sha256':roster_sha},source_artifact_sha256={
            (w.BASE/name).as_posix():w.c.sha(base/name) for name in ('plan.json','discovery/discovery.json')})
    save_json(prereg/'preregistration.json',protocol)
    def rebind():
        plan['context_id']=w.c.digest({k:v for k,v in plan.items() if k!='context_id'})
        save_json(base/'plan.json',plan)
        discovery['context_id']=plan['context_id']
        protocol['existing_context_id']=plan['context_id']
        discovery['artifacts']={'attempt-000/'+rel:w.c.sha(folder/rel) for rel in w.PUBLIC_FILES}
        save_json(base/'discovery/discovery.json',discovery)
        protocol['source_artifact_sha256'][(w.BASE/'plan.json').as_posix()]=w.c.sha(base/'plan.json')
        protocol['source_artifact_sha256'][(w.BASE/'discovery/discovery.json').as_posix()]=w.c.sha(base/'discovery/discovery.json')
        save_json(prereg/'preregistration.json',protocol)
        save_json(prereg/'artifact-manifest.json',{name:w.c.sha(prereg/name) for name in ('preregistration.json','roster.json')})
    rebind()
    return dict(base=base,folder=folder,prereg=prereg,output=prereg/'offline-certificates-test',
                discovery=discovery,protocol=protocol,plan=plan,roster=roster,rebind=rebind)


def test_all_twelve_real_pure_block_checks_and_certificate_hashes(synthetic):
    f=synthetic;result=w.build(f['output'])
    assert result['status']=='offline_certificates_complete_eligibility_pending'
    assert len(result['certificates'])==12 and result['native_jobs']==0
    assert result['candidate_dispatch_enabled'] is False and result['new_pool_labels']==0
    assert result['verifier_contract']['random_seed']==20261019
    assert result['roster_codesign_digest']==w.c.digest(f['roster'])
    assert result['roster_file_sha256']!=result['roster_codesign_digest']
    for name in ('independent-cohort-audit.json','independent-cohort-audit.json.sha256'):
        assert result['preregistration_sha256'][name]==w.c.sha(f['prereg']/name)
    for cert in result['certificates']:
        assert cert['lowering_check']['comparisons']==64
        assert cert['relocation_check']['safe'] is True
        assert cert['candidate_id']==w.c.digest([result['context_id'],cert['formula']])
        assert w.c.sha(f['output']/cert['assembly'])==cert['assembly_sha256']
    assert len(list(f['output'].glob('candidate_*.S')))==12
    manifest=json.loads((f['output']/'artifact-manifest.json').read_text())
    assert all(w.c.sha(f['output']/name)==digest for name,digest in manifest.items())


def test_refuses_existing_or_outside_output_before_reading_inputs(synthetic):
    f=synthetic
    with pytest.raises(ValueError,match='Fresh direct'):
        w.build(f['base']/'outside')
    w.build(f['output'])
    with pytest.raises(ValueError,match='Fresh direct'):
        w.build(f['output'])


def test_rejects_exact_roster_byte_change_before_output(synthetic):
    f=synthetic
    with (f['prereg']/'roster.json').open('ab') as stream:stream.write(b'\n')
    with pytest.raises(ValueError,match='artifact changed'):
        w.build(f['output'])
    assert not f['output'].exists()


def test_rejects_changed_public_baseline_hash_before_output(synthetic):
    f=synthetic;(f['folder']/'program.s').write_text('changed')
    with pytest.raises(ValueError,match='baseline input changed'):
        w.build(f['output'])
    assert not f['output'].exists()


def test_rejects_changed_expected_pure_dependency_before_output(synthetic):
    f=synthetic
    f['plan']['source_bindings']['isaforge/assembly_lowering.py']='0'*64
    f['rebind']()
    with pytest.raises(ValueError,match='Bound pure dependency changed'):
        w.build(f['output'])
    assert not f['output'].exists()


@pytest.mark.parametrize('name',('independent-cohort-audit.json','independent-cohort-audit.json.sha256'))
def test_rejects_changed_independent_audit_or_sidecar_before_output(synthetic,name):
    f=synthetic;(f['prereg']/name).write_text('changed')
    with pytest.raises(ValueError,match='Independent cohort audit'):
        w.build(f['output'])
    assert not f['output'].exists()


def test_rejects_wrong_site_map_without_skipping_candidate(synthetic):
    f=synthetic
    f['discovery']['executable_candidates'][0]['occurrences'][0]['sites']=[1,0]
    f['rebind']()
    with pytest.raises(ValueError,match='source-PC'):
        w.build(f['output'])
    record=json.loads((f['output']/'certificates.json').read_text())
    assert record['status']=='rejected' and record['failed_candidate']=='candidate_00'
    assert record['certificates']==[] and record['candidate_dispatch_enabled'] is False


def test_rejects_symbolic_relocation_without_compiling(synthetic):
    f=synthetic
    source=(f['folder']/'program.s').read_text().replace('slli a2,a1,2\n','slli a2,a1,%lo(symbol)\n',1)
    (f['folder']/'program.s').write_text(source)
    marked,_=w.lowering.mark_assembly(source);(f['folder']/'marked.S').write_text(marked)
    f['rebind']()
    with pytest.raises(ValueError,match='relocatable'):
        w.build(f['output'])
    assert json.loads((f['output']/'certificates.json').read_text())['status']=='rejected'


def test_stops_on_second_formula_mismatch_and_preserves_first(synthetic):
    f=synthetic
    f['discovery']['executable_candidates'][1]['occurrences'][0]['inputs']=[11,10]
    f['rebind']()
    with pytest.raises(ValueError,match='Input binding changed'):
        w.build(f['output'])
    record=json.loads((f['output']/'certificates.json').read_text())
    assert record['failed_candidate']=='candidate_01' and len(record['certificates'])==1
    assert len(list(f['output'].glob('candidate_*.S')))==1


def test_unknown_block_fails_closed_without_opaque_skip(synthetic):
    f=synthetic
    p=f['folder']/'marked/disassembly.txt'
    p.write_text(p.read_text().replace('00000613','00000073',1));f['rebind']()
    # Removing the reset exposes the scratch register, so the existing legality
    # check rejects this opaque block even before sampled interpretation.
    with pytest.raises(ValueError,match='Illegal fusion'):
        w.build(f['output'])
    assert json.loads((f['output']/'certificates.json').read_text())['status']=='rejected'


def test_changed_input_output_formula_semantics_fail_before_interpreter(synthetic):
    data=w.public_inputs();candidate=copy.deepcopy(data['candidates'][0])
    candidate['formula']='sub(in0,slli(in1,2))'
    with pytest.raises(ValueError,match='Formula differs'):
        w.certify_candidate(candidate,data)
