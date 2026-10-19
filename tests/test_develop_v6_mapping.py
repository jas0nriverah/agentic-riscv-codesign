"""Read-only generic-cache provenance and fixed-study boundaries."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import develop_v6_mapping as study
from isaforge.rtl import generate_rtl


def fixture_cache(folder):
    formula='addi(in0,1)';record={'formula':formula,'original_cache_key':'fixture'}
    for name in ('candidate.v','extract.ys','word.json','graph.json','extract.log'):
        (folder/name).write_text(generate_rtl(formula) if name=='candidate.v' else '{}')
    manifest={'formula':formula,'cache_key':'fixture','context':{'schema':study.SCHEMA,
        'pipeline':study.PIPELINE,'runtime_source_sha256':study.graph_sources()},
        'files_sha256':{n:study.sha(folder/n) for n in ('candidate.v','extract.ys','word.json','graph.json','extract.log')}}
    study.write(folder/'features.json',manifest);record['original_manifest_sha256']=study.sha(folder/'features.json')
    return record


def test_cached_graph_missing_or_mutated_never_regenerates(tmp_path):
    with pytest.raises(ValueError,match='regeneration forbidden'):study.cached_graph(tmp_path,{'formula':'addi(in0,1)'})
    record=fixture_cache(tmp_path)
    path,provenance=study.cached_graph(tmp_path,record)
    assert path==tmp_path/'graph.json' and provenance['formula']=='addi(in0,1)'
    (tmp_path/'graph.json').write_text('changed graph')
    with pytest.raises(ValueError,match='bytes changed'):study.cached_graph(tmp_path,record)


def test_cache_manifest_identity_rejects_another_formula(tmp_path):
    record=fixture_cache(tmp_path)
    with pytest.raises(ValueError,match='identity'):study.cached_graph(tmp_path,{**record,'formula':'addi(in0,2)'})


def test_fixed_seeds_and_safe_output_only(tmp_path):
    with pytest.raises(ValueError,match='fixed'):study.run(tmp_path,tmp_path,tmp_path,tmp_path,seeds=(13,))
    with pytest.raises(ValueError,match='outside repository'):study.run(tmp_path,tmp_path,tmp_path,study.ROOT/'generated/forbidden')
    (tmp_path/'retained').write_text('evidence')
    with pytest.raises(ValueError,match='overwritten'):study.run(tmp_path,tmp_path,tmp_path,tmp_path)
