"""Authenticate and exactly replay the disjoint-pool SHA256 ML comparison.

The complete prelabel manifest is Git-bound; portable native evidence rederives
both public features and private outcomes. Refit original controls and exported
utility models, then verify all eleven equal-budget policies. No native jobs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c, budgeted_selection as b
from isaforge import feasible_benefit_experiment as e, guarded_evidence, training_workload as t
from isaforge.feasible_benefit import FeasibleBenefitPredictor, AREA_CAPS
from isaforge.speedup_corpus import family
from scripts.reproduce_budget_campaign import check_prelabel_commit
from scripts.reproduce_guarded_sha256 import _path, _inventory, _hashes, _manifest

PREREG=ROOT/'results/2026-10-21-feasible-benefit-preregistration'
SELECTION=ROOT/'results/2026-10-21-disjoint-sha256-selection'
CAMPAIGN=ROOT/'results/2026-10-21-disjoint-sha256-campaign'
OUTPUT=ROOT/'generated/reproduction/disjoint-sha256'
SOURCE='scripts/reproduce_disjoint_sha256.py'
SOURCES=(SOURCE,'scripts/reproduce_guarded_sha256.py',
         'scripts/reproduce_budget_campaign.py','scripts/reproduce_prospective.py')
WORKLOAD='embench-nettle-sha256'
BASELINES=('plan.json','discovery/discovery.json','measurements/baseline/measurement.json',
           'commands.json','evaluation-protocol.json','attempt-ledger/baseline.json',
           'public.json','context.json','before.json')
FINAL_REPORTS={'report.json','report.json.sha256','model/report.json','model/report.json.sha256'}


def required_selection(selection):
    selection=Path(selection)
    protocol=c.unseal(selection/'protocol.json')
    c.require(protocol.get('schema')=='isaforge-feasible-benefit-freeze-v1' and
              protocol.get('scope')=='consumed-source fresh-candidate-pool' and
              protocol.get('target_workload')==WORKLOAD and
              type(protocol.get('target_labels_read')) is int and protocol['target_labels_read']==0 and
              type(protocol.get('target_labels_observed')) is int and protocol['target_labels_observed']==0,
              'Expected a zero-label disjoint SHA256 model freeze')
    artifacts=protocol.get('artifacts')
    _hashes(selection,artifacts)
    c.require(not {'protocol.json','protocol.json.sha256'} & set(artifacts),
              'Frozen protocol cannot include its own inventory')
    return set(artifacts)|{'protocol.json','protocol.json.sha256'},protocol


def check_inputs(prereg,selection_protocol,outer):
    prereg=Path(prereg)
    bindings=c.unseal(prereg/'inputs/bindings.json')
    c.require(bindings==selection_protocol['input_bindings'], 'Preregistration/model input bindings differ')
    _hashes(ROOT,bindings)
    _hashes(ROOT,outer['source_bindings'])
    history=c.unseal(prereg/'inputs/history.json')
    public=c.unseal(prereg/'inputs/public.json')
    contexts=c.unseal(prereg/'inputs/contexts.json')
    costs=c.unseal(prereg/'inputs/cost-provenance.json')
    c.require(c.digest(history)==selection_protocol['history_digest'] and
              c.digest(public)==selection_protocol['public_digest'] and
              c.digest(contexts)==selection_protocol['contexts_digest'], 'Frozen input digest differs')
    c.require(costs==selection_protocol['cost_provenance'], 'Frozen historical cost provenance differs')
    corpus=c.unseal(_path(ROOT,outer['source_history']))
    derived=[row for row in corpus['rows'] if row['workload_group']!=WORKLOAD]
    c.require(history==derived and len(history)==27 and
              len({row['workload_group'] for row in history})==5,
              'Expected all 27 source-excluded historical rows from five groups')
    context=c.unseal(prereg/'baseline/context.json')
    expected_contexts={key:value for key,value in corpus['contexts'].items()
                       if key in {row['benchmark'] for row in history}}
    expected_contexts[public[0]['benchmark']]=context
    c.require(contexts==expected_contexts, 'Historical/native context assembly differs')
    c.require(public==c.unseal(prereg/'baseline/public.json'), 'Frozen public/native pool differs')
    c.require(costs['historical_training_available']==corpus['historical_costs'] and
              costs['target_baseline']==context['baseline_provenance'], 'Historical/baseline costs differ')
    consumed=costs['consumed_development']
    c.require(consumed['candidate_attempts']==corpus['total_candidate_attempts'] and
              consumed['successful_labels']==corpus['successful_labels'] and
              consumed['candidate_wall_seconds']==corpus['total_candidate_attempt_wall_seconds'] and
              consumed['old_sha_labels_excluded_from_fit']==6 and
              consumed['old_sha_candidate_wall_seconds']==corpus['new_candidate_wall_seconds'],
              'Consumed development cost accounting differs')
    families={family(row['formula']) for row in public}
    fitted=[row for row in history if family(row['formula']) not in families]
    c.require([row['candidate_id'] for row in fitted]==selection_protocol['historical_training_ids'] and
              len({row['workload_group'] for row in fitted})>=2, 'Historical family-filter cohort differs')


def check_prelabel(selection,prereg):
    selection,prereg=Path(selection),Path(prereg)
    entries=_manifest(prereg)
    required,inner=required_selection(selection)
    c.require({name for name in entries if name.startswith('selection/')}=={'selection/'+name for name in required},
              'Preregistration must contain complete frozen selection inventory')
    c.require({name.removeprefix('selection/') for name in _inventory(prereg) if name.startswith('selection/')}==required,
              'Unexpected or omitted preregistered model file')
    for name in required:
        c.require(c.sha(_path(selection,name))==entries['selection/'+name], 'Changed prelabel selection artifact: '+name)
    outer=c.unseal(prereg/'protocol.json')
    c.require(outer.get('schema')=='isaforge-feasible-benefit-preregistration-v1' and
              outer.get('target_workload')==WORKLOAD and
              type(outer.get('target_candidate_attempts_before_and_after_fit')) is int and
              outer['target_candidate_attempts_before_and_after_fit']==0 and
              type(outer.get('target_candidate_labels_observed')) is int and
              outer['target_candidate_labels_observed']==0, 'Invalid zero-label preregistration scope')
    c.require(outer.get('baseline_files')==list(BASELINES), 'Complete fixed baseline-copy list required')
    required_baselines={'baseline/'+name+suffix for name in BASELINES for suffix in ('','.sha256')}
    c.require(required_baselines|{'protocol.json','protocol.json.sha256','inputs/bindings.json','inputs/bindings.json.sha256'}<=set(entries),
              'Preregistration baseline/input/protocol inventory incomplete')
    c.require(outer['selection_protocol_sha256']==c.sha(selection/'protocol.json'), 'Preregistered model protocol differs')
    for name in BASELINES:c.unseal(prereg/'baseline'/name)
    check_inputs(prereg,inner,outer)
    return c.sha(prereg/'manifest.json')


def check_baselines(prereg,raw,selection):
    prereg,raw,selection=map(Path,(prereg,raw,selection))
    outer=c.unseal(prereg/'protocol.json')
    c.require(outer.get('baseline_files')==list(BASELINES), 'Complete fixed baseline-copy list required')
    plan=c.unseal(raw/'plan.json');t.check_plan(plan)
    c.require(plan['context_id']==outer['context_id'], 'Archived disjoint baseline context differs')
    for name in BASELINES:
        if name!='commands.json':
            c.require(c.sha(_path(raw,name))==c.sha(_path(prereg,'baseline/'+name)),
                      'Preregistered native baseline changed: '+name)
    before=c.unseal(prereg/'baseline/commands.json')
    evaluation=c.unseal(raw/'evaluation-protocol.json');commands=c.unseal(raw/'commands.json')
    c.require(isinstance(before,list) and before==evaluation['baseline_receipts'] and commands[:len(before)]==before,
              'Preregistered baseline receipt prefix differs')
    c.require(evaluation['pool_names']==outer['native_order'] and evaluation['maximum_candidate_attempts']==6,
              'Disjoint pool/attempt budget differs')
    public=c.unseal(raw/'public.json')
    c.require(public==c.unseal(selection/'model/public.json'), 'Native/frozen model public rows differ')
    c.require(not {row['formula'] for row in public} & set(t.EXCLUDED_FORMULAS), 'Historical literal formula leaked into disjoint pool')


def verify_refits(selection):
    selection=Path(selection)
    case=e.authenticate(selection)
    public,history=case['public'],case['history']
    original=c.unseal(selection/'model/predictions.json')
    utility=case['predictions']
    with tempfile.TemporaryDirectory(prefix='isaforge-disjoint-refit-') as temporary:
        for frozen in original:
            seed=frozen['seed']
            refit=b.zero_shot(history,public,seed)
            c.require(b.stable(refit)==b.stable(frozen), 'Original control prediction refit differs')
            model=FeasibleBenefitPredictor(seed).fit(history)
            values=next(row for row in utility if row['seed']==seed)['by_cap']
            c.require(all(model.predict(public,area_cap=cap)==values[str(cap)] for cap in AREA_CAPS),
                      'Feasible utility prediction refit differs')
            saved=model.save(Path(temporary)/f'seed-{seed}')
            frozen_schema=c.unseal(selection/'utility-models'/f'seed-{seed}'/'schema.json')
            c.require(saved==frozen_schema, 'Exported utility model refit differs')
    return dict(original_control_prediction_refits=len(original),utility_prediction_and_model_refits=len(utility))


def authenticate_outcomes(native,archived,selection):
    """Raw audit rederives labels, identities and charged timer scopes exactly."""
    c.require(native['attempt_collection_complete'] and native['candidate_wall_seconds_complete'] and
              native['charged_candidate_attempts']==6 and not native['unattempted'], 'Complete six-attempt native audit required')
    public=c.unseal(Path(selection)/'model/public.json')
    c.require(native['public']==public, 'Replayed native/frozen public pool differs')
    c.require(native['outcomes']==archived and len(archived)==len(public), 'Archived outcomes differ from rederived native evidence')
    for outcome,row in zip(archived,public):b.validate_outcome(outcome,row)
    return bool(native['reference_censored_candidates'])


def replay(campaign=CAMPAIGN,output=OUTPUT,*,prereg=PREREG,selection=SELECTION):
    campaign,output,prereg,selection=map(Path,(campaign,output,prereg,selection))
    entries=_manifest(campaign)
    c.require({'provenance.json','provenance.json.sha256','outcomes.json','outcomes.json.sha256',
               'audit.json','audit.json.sha256','native/manifest.json','native/manifest.json.sha256'}<=set(entries), 'Campaign provenance/outcomes/native manifest missing')
    provenance=c.unseal(campaign/'provenance.json')
    c.require(provenance.get('schema')=='isaforge-disjoint-sha256-campaign-provenance-v1', 'Unknown disjoint campaign provenance')
    c.require(check_prelabel(selection,prereg)==provenance['prereg_manifest_sha256'], 'Preregistration manifest differs from campaign')
    check_prelabel_commit(prereg,provenance['prelabel_commit'])
    sources=provenance.get('source_bindings')
    c.require(isinstance(sources,dict) and set(SOURCES)<=set(sources), 'Reproducer/helper source bindings required')
    _hashes(ROOT,sources)
    _hashes(selection,provenance.get('selection_manifest'),exact=True)
    required,_=required_selection(selection)
    c.require(set(provenance['selection_manifest'])==required|FINAL_REPORTS, 'Final selection must add exactly both sealed reports')
    c.require(c.sha(campaign/'outcomes.json')==provenance['outcomes_sha256'], 'Campaign outcome file binding differs')
    if (campaign/'selection-manifest.json').exists():
        c.require(c.unseal(campaign/'selection-manifest.json')==provenance['selection_manifest'], 'Separate selection manifest differs')
    with t.registration():native=guarded_evidence.replay(campaign/'native',output)
    c.require(c.unseal(campaign/'audit.json')==native, 'Archived raw audit differs from rederived native evidence')
    check_baselines(prereg,output,selection)
    c.require(native['context_id']==provenance['context_id'] and
              native['protocol_sha256']==provenance['evaluation_protocol_sha256'], 'Native campaign context/protocol binding differs')
    archived=c.unseal(campaign/'outcomes.json')
    censored=authenticate_outcomes(native,archived,selection)
    refits=verify_refits(selection)
    result=e.evaluate(selection,archived,reference_censored=censored,verify=True)
    c.require(native.get('new_native_jobs')==result.get('new_native_jobs')==0, 'Replay unexpectedly reports native jobs')
    c.require(result['trajectories']==165 and result['endpoints']==495, 'Complete eleven-policy replay required')
    return dict(target_workload=WORKLOAD,context_id=native['context_id'],
        charged_candidate_attempts=native['charged_candidate_attempts'],trajectories=result['trajectories'],
        endpoints=result['endpoints'],**refits,new_native_jobs=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('replay',),nargs='?',default='replay')
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--preregistration',type=Path,default=PREREG)
    parser.add_argument('--selection',type=Path,default=SELECTION)
    args=parser.parse_args(argv)
    print(replay(args.campaign,args.output,prereg=args.preregistration,selection=args.selection))

if __name__=='__main__':main()
