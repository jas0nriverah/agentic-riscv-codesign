"""Fresh-source replay boundaries; synthetic timers/models launch no native jobs."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from unittest.mock import Mock
import pytest
from isaforge import codesign as c
from scripts import reproduce_jfdctint as r


def manifest(root):
    c.seal(root/'manifest.json', {p.relative_to(root).as_posix(): c.sha(p)
        for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in ('manifest.json','manifest.json.sha256')})


@pytest.fixture
def fixture(tmp_path):
    prereg, raw, selection = tmp_path/'prereg', tmp_path/'raw', tmp_path/'selection'
    shutil.copytree(r.PREREG, prereg)
    shutil.copytree(prereg/'selection', selection)
    shutil.copytree(prereg/'baseline', raw)
    outer = c.unseal(prereg/'protocol.json')
    public = c.unseal(selection/'controls11/model/public.json')
    outcomes = [dict(row, status='failed', measurement_seconds=2.0, error='synthetic unavailable',
                     failure_class='infrastructure_unknown', reference_censored=True) for row in public]
    failures = [dict(name=name, classification='infrastructure_unknown', error='synthetic unavailable',
                     elapsed_seconds=2.0, reference_censored=True) for name in outer['native_order']]
    audited = dict(context_id=outer['context_id'], protocol_sha256=c.sha(raw/'evaluation-protocol.json'),
        public=public, pool_names=outer['native_order'], outcomes=outcomes,
        attempt_collection_complete=True, candidate_wall_seconds_complete=True, charged_candidate_attempts=6,
        unattempted=[], failed_or_interrupted=failures,
        reference_censored_candidates=outer['native_order'], new_native_jobs=0)
    for index,name in enumerate(outer['native_order']):
        start = datetime(2026,10,22,tzinfo=timezone.utc)+timedelta(seconds=index*10)
        c.seal(raw/'attempt-ledger'/(name+'.json'), dict(status='failed', elapsed_seconds=2.0,
            started_at_utc=(start+timedelta(seconds=1)).isoformat()))
        c.seal(raw/'outer-timing'/f'{index+5:03d}-measure.json', dict(schema='isaforge-wrapper-outer-time-v1',
            command='measure',candidate=name,status='failed',elapsed_seconds=4.0,
            started_at_utc=start.isoformat(),scope='Complete CLI operation through lock close and JSON formatting; synthetic test'))
    before=c.unseal(raw/'commands.json')
    c.seal(raw/'commands.json',before+[{'log':'synthetic paid command'}])
    for name in r.FINAL_REPORTS:
        if name.endswith('.json'): c.seal(selection/name, {'synthetic_fixture':True})
    return dict(prereg=prereg,raw=raw,selection=selection,outer=outer,audit=audited,outcomes=outcomes)


def test_actual_zero_label_prereg_inventory_and_inputs_without_fitting():
    assert r.check_prelabel(r.PREREG/'selection',r.PREREG)==c.sha(r.PREREG/'manifest.json')


def test_canonical_baseline_copy_and_command_prefix(fixture):
    f=fixture;r.check_baselines(f['prereg'],f['raw'],f['selection'])
    values=c.unseal(f['raw']/'commands.json');values[0]['log']='changed';c.seal(f['raw']/'commands.json',values)
    with pytest.raises(ValueError,match='receipt prefix'):
        r.check_baselines(f['prereg'],f['raw'],f['selection'])


def test_outer_timers_cover_each_candidate_and_match_failed_ledger(fixture):
    f=fixture
    expected={row['candidate_id']:4.0 for row in f['audit']['public']}
    assert r.candidate_outer_times(f['raw'],f['audit'],f['prereg'])==expected


@pytest.mark.parametrize('change,error',[
    ('duplicate','Duplicate'),('duration','enclose attempt ledger'),('timestamp','timestamp'),
    ('status','terminal status'),('scope','timer scope'),('prefix','Artifact checksum'),
    ('missing','Complete unique'),('extra','Only candidate'),('unpaired','Unpaired')])
def test_bad_timer_proof_is_rejected(fixture,change,error):
    f=fixture;path=f['raw']/'outer-timing/005-measure.json';value=c.unseal(path)
    if change=='duplicate': c.seal(f['raw']/'outer-timing/011-measure.json',value)
    elif change=='missing':
        path.unlink();Path(str(path)+'.sha256').unlink()
    elif change=='unpaired': (f['raw']/'outer-timing/unbound.txt').write_text('x')
    elif change=='prefix':
        prefix=f['raw']/'outer-timing/000-prepare.json';c.seal(prefix,{'tampered':True})
    else:
        if change=='duration':value['elapsed_seconds']=1.0
        if change=='timestamp':value['started_at_utc']='invalid'
        if change=='status':value['status']='success'
        if change=='scope':value['scope']='record only'
        if change=='extra':value['command']='audit'
        c.seal(path,value)
    with pytest.raises(ValueError,match=error):r.candidate_outer_times(f['raw'],f['audit'],f['prereg'])


def test_omitted_frozen_model_cannot_hide_in_resealed_prereg(fixture):
    f=fixture;path=next((f['prereg']/'selection/feasibility-models/seed-0').glob('member*.json'))
    path.unlink();manifest(f['prereg'])
    with pytest.raises(ValueError,match='frozen selection inventory'):
        r.check_prelabel(f['selection'],f['prereg'])


def test_source_history_is_complete_and_target_free(fixture):
    f=fixture;rows=c.unseal(f['prereg']/'inputs/history.json');rows.pop()
    c.seal(f['prereg']/'inputs/history.json',rows);manifest(f['prereg'])
    with pytest.raises(ValueError,match='historical outcomes'):
        r.check_prelabel(f['selection'],f['prereg'])


def test_zero_attempt_release_requires_exact_commit_and_baseline(fixture,tmp_path):
    f=fixture;release=tmp_path/'release.json'
    row=dict(schema='isaforge-jfdctint-release-v1',prelabel_commit='a'*40,remote_commit='a'*40,
        pushed_branch='ai-guided-ml',target_labels_observed=0,released_at_utc='2026-10-21T20:54:28+00:00',
        native_order=f['audit']['pool_names'],prereg_manifest_sha256=c.sha(f['prereg']/'manifest.json'),
        context_id=f['audit']['context_id'],evaluation_protocol_sha256=f['audit']['protocol_sha256'],zero_candidate_attempts=True)
    c.seal(release,row);assert r._release(release,'a'*40,f['prereg'],f['audit'])==row
    row['zero_candidate_attempts']=1;c.seal(release,row)
    with pytest.raises(ValueError,match='release receipt'):r._release(release,'a'*40,f['prereg'],f['audit'])


def test_refits_check_five_seeds_all_caps_and_both_exported_models(tmp_path,monkeypatch):
    root=tmp_path/'selection';public=[{'candidate_id':'p'}];history=[{'candidate_id':'h'}]
    predictions=[dict(seed=seed,by_cap={str(cap):[{'score':seed+cap}] for cap in r.AREA_CAPS}) for seed in range(5)]
    original=[dict(seed=seed,value=seed) for seed in range(5)]
    c.seal(root/'controls11/model/predictions.json',original)
    c.seal(root/'controls11/utility-predictions.json',predictions)
    monkeypatch.setattr(r.experiment,'authenticate',lambda path:dict(public=public,history=history,predictions=predictions))
    monkeypatch.setattr(r.b,'zero_shot',lambda h,p,seed:dict(seed=seed,value=seed))
    seen=[]
    class Model:
        def __init__(self,seed):self.seed=seed
        def fit(self,rows):assert rows==history;seen.append(self.seed);return self
        def predict(self,rows,*,area_cap):assert rows==public;return [{'score':self.seed+area_cap}]
        def save(self,path):return {'seed':self.seed}
    monkeypatch.setattr(r,'FeasibleBenefitPredictor',Model)
    monkeypatch.setattr(r,'FeasibilitySelectionPredictor',Model)
    for name in ('controls11/utility-models','feasibility-models'):
        for seed in range(5):c.seal(root/name/f'seed-{seed}'/'schema.json',dict(seed=seed))
    assert r.verify_refits(root)==dict(original_control_prediction_refits=5,
        utility_prediction_and_model_refits=5,feasibility_prediction_and_model_refits=5)
    assert seen==[seed for seed in range(5) for unused in range(2)]


def test_checked_native_failures_and_censorship_cannot_be_changed(fixture):
    f=fixture
    assert r.experiment.checked_outcomes(f['audit']['public'],f['outcomes'],f['audit']) is True
    changed=copy.deepcopy(f['audit']);changed['failed_or_interrupted'][0]['reference_censored']=False
    with pytest.raises(ValueError,match='native classification'):
        r.experiment.checked_outcomes(changed['public'],f['outcomes'],changed)


def pack_synthetic(fixture,monkeypatch,tmp_path):
    f=fixture;campaign=tmp_path/'campaign';release=f['raw']/'release.json'
    c.seal(release,dict(schema='isaforge-jfdctint-release-v1',prelabel_commit='a'*40,remote_commit='a'*40,
        pushed_branch='ai-guided-ml',target_labels_observed=0,released_at_utc='2026-10-21T20:54:28+00:00',
        native_order=f['audit']['pool_names'],prereg_manifest_sha256=c.sha(f['prereg']/'manifest.json'),
        context_id=f['audit']['context_id'],evaluation_protocol_sha256=f['audit']['protocol_sha256'],zero_candidate_attempts=True))
    git=Mock();monkeypatch.setattr(r,'check_prelabel_commit',git)
    monkeypatch.setattr(r.workload,'audit',lambda path:copy.deepcopy(f['audit']))
    def pack(native,path,*,prelabel_commit):
        assert prelabel_commit is None
        assert r.workload.g.SOURCE==r.workload.SOURCE
        c.seal(path/'manifest.json',{})
    monkeypatch.setattr(r.guarded_evidence,'pack',pack)
    assert r.pack_campaign(f['raw'],campaign,f['selection'],f['prereg'],'a'*40,release)==f['audit']
    return campaign,git


def test_packer_and_complete_twelve_policy_replay_register_native_and_bind_timers(fixture,monkeypatch,tmp_path):
    f=fixture;campaign,git=pack_synthetic(f,monkeypatch,tmp_path)
    def native(*args):
        assert r.workload.g.SOURCE==r.workload.SOURCE
        return copy.deepcopy(f['audit'])
    monkeypatch.setattr(r.guarded_evidence,'replay',native)
    refits=dict(original_control_prediction_refits=5,utility_prediction_and_model_refits=5,
                feasibility_prediction_and_model_refits=5)
    monkeypatch.setattr(r,'verify_refits',lambda path:refits)
    evaluate=Mock(return_value=dict(trajectories=180,endpoints=540,new_native_jobs=0))
    monkeypatch.setattr(r.experiment,'evaluate',evaluate)
    result=r.replay(campaign,f['raw'],prereg=f['prereg'],selection=f['selection'])
    assert result['endpoints']==540 and result['new_native_jobs']==0
    assert git.call_count==2
    evaluate.assert_called_once_with(f['selection'],f['outcomes'],native_audit=f['audit'],
        outer_times={row['candidate_id']:4.0 for row in f['audit']['public']},verify=True)
    assert r.workload.g.SOURCE==r.workload.GUARDED_SOURCE


def test_final_inventory_requires_exactly_six_report_artifacts(fixture,monkeypatch,tmp_path):
    f=fixture;campaign,git=pack_synthetic(f,monkeypatch,tmp_path)
    provenance=c.unseal(campaign/'provenance.json')
    for suffix in ('','.sha256'):
        name='controls11/model/report.json'+suffix
        (f['selection']/name).unlink();provenance['selection_manifest'].pop(name)
    c.seal(campaign/'provenance.json',provenance);manifest(campaign)
    native=Mock();monkeypatch.setattr(r.guarded_evidence,'replay',native)
    with pytest.raises(ValueError,match='three sealed final reports'):
        r.replay(campaign,f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called()


def test_wrong_git_checkpoint_stops_before_native_or_refits(fixture,monkeypatch,tmp_path):
    f=fixture;campaign,git=pack_synthetic(f,monkeypatch,tmp_path)
    git.side_effect=ValueError('Git checkpoint differs')
    native=Mock();refits=Mock()
    monkeypatch.setattr(r.guarded_evidence,'replay',native);monkeypatch.setattr(r,'verify_refits',refits)
    with pytest.raises(ValueError,match='Git checkpoint'):
        r.replay(campaign,f['raw'],prereg=f['prereg'],selection=f['selection'])
    native.assert_not_called();refits.assert_not_called()


@pytest.mark.parametrize('key,value',[
    ('schema','unknown'),('remote_commit','b'*40),('pushed_branch','main'),
    ('target_labels_observed',False),('target_labels_observed',1),
    ('released_at_utc','not-a-date'),('released_at_utc','2026-10-21T20:54:28'),
    ('native_order',[]),('released_at_utc','2026-10-22T00:00:01+00:00')])
def test_release_requires_pushed_zero_label_receipt_and_precedes_all_operations(fixture,tmp_path,key,value):
    f=fixture;path=tmp_path/'release.json'
    record=dict(schema='isaforge-jfdctint-release-v1',prelabel_commit='a'*40,remote_commit='a'*40,
        pushed_branch='ai-guided-ml',target_labels_observed=0,released_at_utc='2026-10-21T20:54:28+00:00',
        native_order=f['audit']['pool_names'],prereg_manifest_sha256=c.sha(f['prereg']/'manifest.json'),
        context_id=f['audit']['context_id'],evaluation_protocol_sha256=f['audit']['protocol_sha256'],
        zero_candidate_attempts=True)
    c.seal(path,record)
    assert r._release(path,'a'*40,f['prereg'],f['audit'],raw=f['raw'])==record
    record[key]=value;c.seal(path,record)
    with pytest.raises(ValueError):r._release(path,'a'*40,f['prereg'],f['audit'],raw=f['raw'])
