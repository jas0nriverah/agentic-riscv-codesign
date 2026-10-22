"""Arithmetic-only diagnosis must not fit models or release a new policy."""
import math
import hashlib
import io
import tarfile

import pytest

from isaforge import codesign as c
from scripts import diagnose_current_models as d


def test_first_query_decomposition_reproduces_frozen_score_and_exposes_cost_flip():
    public=[dict(candidate_id='larger',latency_features=dict(estimated_speedup=1.2,estimated_cycle_reduction=1-1/1.2)),
            dict(candidate_id='cheaper',latency_features=dict(estimated_speedup=1.1,estimated_cycle_reduction=1-1/1.1))]
    hardware=dict(area_delta_lut4_mean=20.,area_delta_lut4_std=1.,routed_fmax_min_mhz_mean=60.,
        routed_fmax_min_mhz_std=1.,device_fit_probability=.9,log_measurement_seconds_std=0.)
    values={row['candidate_id']:d.acquisition(row,dict(hardware,log_measurement_seconds_mean=0. if index==0 else -math.log(3)),64)
            for index,row in enumerate(public)}
    assert d.choose(public,values,0)=='cheaper'
    assert d.choose(public,values,0,'count_only_score')=='larger'
    assert values['larger']['positive_calibrated_speedup_gain']==pytest.approx(.2)
    assert values['larger']['count_only_score']==pytest.approx(.18)
    assert values['cheaper']['expected_inverse_seconds']==pytest.approx(3.)


def test_ranking_counts_ties_and_constraint_disagreements_within_context_only():
    common=dict(benchmark='source:context',workload_group='source',device_fits=True,routed_fmax_min_mhz=60.)
    rows=[dict(common,candidate_id='a',speedup=1.3,area_delta_lut4=70),
          dict(common,candidate_id='b',speedup=1.2,area_delta_lut4=20),
          dict(common,candidate_id='c',speedup=1.2,area_delta_lut4=40)]
    rows.append(dict(common,candidate_id='other-context',benchmark='source:other',speedup=1.1,area_delta_lut4=10))
    pairs=d.rank_pairs(rows)
    assert sum(row['all_pairs'] for row in pairs)==3
    assert sum(row['unequal_pairs'] for row in pairs)==2
    assert sum(row['tied_pairs'] for row in pairs)==1
    assert pairs[0]['faster_infeasible_slower_feasible_pairs']=={'32':1,'64':2,'128':0}


def test_existing_semantic_features_separate_ndes_but_preserve_dct_counterexample():
    rows=c.unseal(d.CORPUS)['rows']
    ndes=d.descriptor_pair(rows,'add(in0,slli(in1,2))','slli(add(in0,in1),2)')
    assert ndes['original_hardware_features_equal'] is True
    assert ndes['existing_v3_features_equal'] is False
    assert ndes['differing_v3_features']['v3_edge_adder_shift']==[1.,0.]
    dct=d.descriptor_pair(rows,'addi(lui(-16384),315)','addi(lui(4096),-1650)')
    assert dct['original_hardware_features_equal'] is False
    assert dct['differing_original_features']=={'max_abs_constant':[16384,4096]}
    assert dct['existing_v3_features_equal'] is True and dct['added_lut4']==[33,15]


def test_complete_readonly_diagnosis_never_calls_fitting_or_prediction(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('No new model jobs permitted')
    monkeypatch.setattr(d.b.HardwareSurrogate,'fit',forbidden)
    monkeypatch.setattr(d.b.HardwareSurrogate,'predict',forbidden)
    # Force every generated discovery root to be absent without moving inputs.
    monkeypatch.setattr(d,'original_discovery_path',lambda context:tmp_path/'absent-generated-discovery.json')
    result=d.run(tmp_path/'diagnosis')
    assert result==dict(successful_labels=87,sources=11,contexts=12,cached_first_choices=270,
                       unique_first_cases=135,cost_flips=20,new_model_fits=0,new_native_jobs=0)
    value=c.unseal(tmp_path/'diagnosis/diagnosis.json')
    assert value['corpus']['feasible_counts']=={'32':12,'64':44,'128':87}
    assert value['total_within_context_pairs']==319 and value['unequal_within_context_pairs']==294
    assert value['count_only_first_query_outcomes']==dict(improved=5,worsened=0,tied=130)
    assert value['raw_ranking_feature_aliases']['unique_vectors']==87
    assert value['new_model_predictions']==value['new_policy_trajectories']==0
    fresh=next(row for row in value['frozen_cohorts'] if row['source']=='beebs-expint')
    near=next(row for row in fresh['scaling']['nearest_training_neighbors'] if row['formula']=='add(in0,slli(in1,3))')
    assert near['nearest_training_formula']=='slli(add(in0,in1),2)'
    assert near['nearest_training_added_lut4']==40
    assert near['standardized_euclidean_distance']==pytest.approx(2.698598261722176e-9)
    assert all(row['complete_member_scores_equal'] for row in value['cached_classifier_pair_checks'])
    provenance=c.unseal(tmp_path/'diagnosis/provenance.json')
    assert len(provenance['original_discovery_bytes'])==12
    assert not any(name.startswith('generated/') for name in provenance['input_bindings'])
    for name,digest in provenance['original_discovery_bytes'].items():
        assert c.sha(tmp_path/'diagnosis'/name)==digest
    d._manifest(tmp_path/'diagnosis')
    with pytest.raises(ValueError,match='Fresh diagnosis'):d.run(tmp_path/'diagnosis')


def test_archive_reader_preserves_json_bytes_and_rejects_nonregular_members(tmp_path):
    payload=b'{"pool"  : []}\n\n'
    digest=hashlib.sha256(payload).hexdigest()
    def archive(*,symlink=False):
        with tarfile.open(tmp_path/'raw.tar.gz','w:gz') as stream:
            member=tarfile.TarInfo(d.DISCOVERY_MEMBER);member.size=len(payload)
            if symlink:member.type=tarfile.SYMTYPE;member.linkname='/outside.json'
            stream.addfile(member,None if symlink else io.BytesIO(payload))
        return dict(archive='raw.tar.gz',sha256=c.sha(tmp_path/'raw.tar.gz'),
                    files=[dict(path=d.DISCOVERY_MEMBER,bytes=len(payload),sha256=digest)])
    assert d.archived_discovery(tmp_path,archive(),digest)==payload
    with pytest.raises(ValueError,match='context-bound'):
        d.archived_discovery(tmp_path,archive(),'0'*64)
    with pytest.raises(ValueError,match='regular'):
        d.archived_discovery(tmp_path,archive(symlink=True),digest)
