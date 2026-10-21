"""Frozen ablation inputs must authenticate before fitting or privileged scoring."""
import importlib.util
from pathlib import Path
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('descriptor_ablation',ROOT/'scripts/ablate_hardware_descriptors.py')
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)

@pytest.fixture
def folder(tmp_path):
    path=tmp_path/'case';path.mkdir()
    for name in ('protocol','public','history','predictions','report'):
        for suffix in ('.json','.json.sha256'):
            shutil.copyfile(ROOT/a.TARGETS['sha256']/(name+suffix),path/(name+suffix))
    return path

def test_label_free_loading_does_not_parse_report(folder,monkeypatch):
    original=a.c.unseal; opened=[]
    def unseal(path):
        opened.append(Path(path).name)
        assert Path(path).name!='report.json'
        return original(path)
    monkeypatch.setattr(a.c,'unseal',unseal)
    case=a.load_label_free_case(folder)
    assert len(case['history'])==21
    assert set(opened)=={'protocol.json','public.json','history.json','predictions.json'}

@pytest.mark.parametrize('name',['protocol','public','history','predictions','report'])
def test_corrupt_bytes_rejected(folder,name):
    with (folder/(name+'.json')).open('a') as stream: stream.write(' ')
    with pytest.raises(ValueError): a.load_label_free_case(folder)

@pytest.mark.parametrize('change',['source','package','artifact_escape','resealed_public'])
def test_protocol_and_runtime_bindings(folder,change):
    protocol=a.c.unseal(folder/'protocol.json')
    if change=='source': protocol['source_bindings']['isaforge/budgeted_selection.py']='0'*64
    elif change=='package': protocol['packages']['numpy']='0.0.0'
    elif change=='artifact_escape': protocol['artifacts']['../escape.json']='0'*64
    else:
        public=a.c.unseal(folder/'public.json');public[0]['runs']+=1
        a.c.seal(folder/'public.json',public)
    a.c.seal(folder/'protocol.json',protocol)
    with pytest.raises(ValueError): a.load_label_free_case(folder)

@pytest.mark.parametrize('change',['protocol_binding','outcomes_binding','conflicting_outcomes','postfit_report_change'])
def test_privileged_report_bindings(folder,change):
    case=a.load_label_free_case(folder)
    report=a.c.unseal(folder/'report.json')
    if change=='protocol_binding': report['protocol_sha256']='0'*64
    elif change=='outcomes_binding': report['outcomes_sha256']='0'*64
    elif change=='conflicting_outcomes':
        event=next(e for r in report['runs'][1:] for e in r['events'] if 'observation' in e)
        event['observation']['measurement_seconds']+=1
    a.c.seal(folder/'report.json',report)
    if change!='postfit_report_change': case['report_sha256']=a.c.sha(folder/'report.json')
    else:
        with (folder/'report.json').open('a') as stream: stream.write(' ')
    with pytest.raises(ValueError): a.load_scoring_report(folder,case)

def test_authentic_report_has_bound_complete_outcomes(folder):
    case=a.load_label_free_case(folder)
    report,labels=a.load_scoring_report(folder,case)
    assert len(labels)==6
    assert report['outcomes_sha256']==a.c.digest([labels[r['candidate_id']] for r in case['public']])
