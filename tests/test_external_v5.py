"""External cohort identity, source verification and meaningful oracle failures."""
import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('collect_external_v5',Path(__file__).parents[1]/'scripts/collect_external_v5.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_fixed_cohort_and_fetch_files():
    manifest=collector.read(collector.FIXTURE/'fetch.json')
    assert tuple(manifest['programs'])==('dijkstra','adpcm_dec','anagram')
    assert manifest['commit']=='c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08'
    files=collector.source_files(manifest)
    assert len(files)==14
    assert 'bench/sequential/dijkstra/input.c' in files
    assert len({record['family'] for record in manifest['programs'].values()})==3


def test_source_download_rejects_mutation_before_use(tmp_path):
    manifest={'programs':{name:{'directory':name,'files_sha256':{}} for name in collector.PROGRAMS}}
    reference=tmp_path/'reference';reference.mkdir()
    p=reference/'dijkstra'/'input.c';p.parent.mkdir();p.write_text('pinned input')
    manifest['programs']['dijkstra']['files_sha256']={'dijkstra/input.c':collector.sha(p)}
    collector.fetch_sources(manifest,tmp_path/'sources',reference)
    (tmp_path/'sources/dijkstra/input.c').write_text('changed input')
    with pytest.raises(ValueError,match='Retained upstream source mismatch'):
        collector.fetch_sources(manifest,tmp_path/'sources',reference)


def test_adpcm_complete_fixed_vector_oracle():
    values=collector.independent_adpcm_two_code()
    assert values==[0,0,-1,-1]
    assert sum(values)==-2
    # A checksum alone cannot distinguish these two output vectors.
    wrong=[0,-1,0,-1]
    assert sum(wrong)==sum(values) and wrong!=values


def test_anagram_witness_rejects_bad_letters_unknown_words_and_no_termination():
    dictionary={'duke','yip','arm','ram'}
    def buffer(text):
        return list(text.encode())+[0]*(30-len(text))
    assert collector.anagram_witness(buffer('duke yip arm '),'mary updike',dictionary)=='duke yip arm '
    with pytest.raises(ValueError,match='letter multiset'):
        collector.anagram_witness(buffer('duke yip yip '),'mary updike',dictionary)
    with pytest.raises(ValueError,match='outside'):
        collector.anagram_witness(buffer('duke yip xxx '),'mary updike',dictionary)
    with pytest.raises(ValueError,match='termination'):
        collector.anagram_witness([65]*30,'mary updike',dictionary)


def test_htif_output_is_exactly_one_record():
    line=json.dumps({'kind':'external-output','values':[0,0,-1,-1],'upstream_status':0})+'\n'
    assert collector.parse_output('Spike diagnostic\n'+line)['values']==[0,0,-1,-1]
    with pytest.raises(ValueError,match='got 2'):
        collector.parse_output(line+line)


def test_application_filter_excludes_wrappers_and_splits_symbols():
    program={0:{'symbol':'main'},4:{'symbol':'dijkstra_find'},8:{'symbol':'dijkstra_find'},12:{'symbol':'external_snapshot'}}
    runs={0:1,4:2,8:2,12:1}
    scoped,starts=collector.filtered_counts(program,runs,{0},'dijkstra')
    assert dict(scoped)=={4:2,8:2}
    assert starts=={0,4,12}


def test_input_only_selection_is_order_invariant():
    rows=[{'formula':f'addi(in0,{i})'} for i in range(300)]
    selected=collector.downselect(rows)
    assert len(selected)==200
    assert selected==collector.downselect(list(reversed(rows)))
    assert selected!=collector.downselect(rows,seed=1)


def fake_spike(tmp_path, mode='success'):
    import sys
    executable=tmp_path/'fake-spike'
    source=f'''#!{sys.executable}
import json,os,sys,time
path=next(arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--log='))
with open(path,'w') as log:
    log.write('core   0: 3 0x80000100 (0xc02027f3) x15 0x00000064\\n')
    log.write('core   0: 3 0x80000104 (0x00150513) x10 0x00000001\\n')
    log.write('core   0: 3 0x80000108 (0xc02027f3) x15 0x00000066\\n')
print(json.dumps({{'kind':'external-output','values':[1],'upstream_status':0}}),flush=True)
if {mode!r}=='hang':
    while True: time.sleep(1)
'''
    executable.write_text(source)
    executable.chmod(0o700)
    return str(executable)


def test_commit_pipe_does_not_mix_htif_output(tmp_path, monkeypatch):
    monkeypatch.setattr(collector,'ROOT',tmp_path)
    trace=tmp_path/'trace.jsonl.gz'
    summary,runs,starts=collector.collect_trace_external(fake_spike(tmp_path),tmp_path/'input.elf',trace,tmp_path/'trace.log',2)
    assert summary['validated'] and summary['trace_instructions']==1
    assert dict(runs)=={0x80000104:1}
    assert collector.parse_output(Path(summary['program_output']).read_text())['values']==[1]
    assert not trace.with_suffix(trace.suffix+'.partial').exists()


def test_trace_deadline_retains_partial_evidence_and_stops_owned_process(tmp_path, monkeypatch):
    monkeypatch.setattr(collector,'ROOT',tmp_path)
    trace=tmp_path/'trace.jsonl.gz'
    with pytest.raises(RuntimeError,match='Spike trace exit'):
        collector.collect_trace_external(fake_spike(tmp_path,'hang'),tmp_path/'input.elf',trace,tmp_path/'trace.log',0.2)
    assert trace.with_suffix(trace.suffix+'.partial').exists()
    assert not trace.exists()


def test_build_uses_only_manifest_listed_sources(tmp_path):
    directory=tmp_path/'input';directory.mkdir()
    (directory/'listed.c').write_text('listed')
    (directory/'extra.c').write_text('unmanifested')
    spec={'files_sha256':{'input/listed.c':'digest','input/input.h':'digest'}}
    assert collector.upstream_c_sources(spec,tmp_path)==[directory/'listed.c']


def test_command_timeout_preserves_log(tmp_path,monkeypatch):
    import sys,subprocess
    monkeypatch.setattr(collector,'ROOT',tmp_path)
    log=tmp_path/'command.log'
    with pytest.raises(subprocess.TimeoutExpired):
        collector.command([sys.executable,'-c','import time;print("before timeout",flush=True);time.sleep(10)'],log,0.1)
    assert 'before timeout' in log.read_text()


def test_incomplete_execution_is_preserved_before_fetch_or_rebuild(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(collector,'ROOT',tmp_path)
    output=tmp_path/'generated/external-v5/attempt'
    output.mkdir(parents=True)
    (output/'report.json').write_text('{"status":"interrupted"}')
    with pytest.raises(ValueError,match='Prior incomplete attempt is preserved'):
        collector.collect(SimpleNamespace(output=output))
    assert (output/'report.json').read_text()=='{"status":"interrupted"}'
