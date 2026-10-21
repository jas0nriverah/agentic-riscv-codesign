"""Authenticate and replay the prospective guarded SHA256 experiment.

Git authenticates the exact prelabel manifest. Its complete frozen selection
inventory and baseline copies are checked against the final selection and
portable native archive before exact prediction/policy replay. No compiler,
simulator, synthesis or routing process is launched.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c, guarded_evidence, guarded_selection
from scripts.reproduce_budget_campaign import check_prelabel_commit
from scripts.reproduce_prospective import authenticate_files

PREREG=ROOT/'results/2026-10-21-sha256-preregistration'
SELECTION=ROOT/'results/2026-10-21-sha256-selection'
CAMPAIGN=ROOT/'results/2026-10-21-sha256-campaign'
SNAPSHOT=CAMPAIGN/'native'
OUTPUT=ROOT/'generated/reproduction/guarded-sha256'
SOURCE='scripts/reproduce_guarded_sha256.py'
REPORTER='scripts/report_guarded_selection.py'
WORKLOAD='embench-nettle-sha256'
BASELINES={
    'plan.json':'baseline/plan.json',
    'discovery/discovery.json':'baseline/discovery.json',
    'measurements/baseline/measurement.json':'baseline/measurement.json',
    'commands.json':'baseline/commands.json',
    'evaluation-protocol.json':'baseline/evaluation-protocol.json',
    'attempt-ledger/baseline.json':'baseline/attempt-ledger.json',
}


def _path(root,name):
    c.require(isinstance(name,str) and name and not Path(name).is_absolute() and
              '..' not in Path(name).parts and Path(name).as_posix()==name,
              'Canonical relative artifact path required')
    root=Path(root).resolve();path=(root/name).resolve()
    c.require(path.is_relative_to(root),'Artifact path escapes root')
    return path


def _inventory(root):
    root=Path(root)
    return {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}


def _hashes(root,entries,*,exact=False):
    c.require(isinstance(entries,dict),'Artifact hash mapping required')
    for name,expected in entries.items():
        path=_path(root,name)
        c.require(path.is_file() and c.sha(path)==expected,'Artifact checksum differs: '+name)
    if exact:
        c.require(set(entries)==_inventory(root),'Complete final selection inventory required')


def _manifest(root):
    root=Path(root)
    entries=c.unseal(root/'manifest.json')
    _hashes(root,entries)
    authenticated=authenticate_files(root,'manifest.json')
    c.require(authenticated==entries,'Manifest changed during authentication')
    expected=_inventory(root)-{'manifest.json','manifest.json.sha256'}
    c.require(set(entries)==expected,'Manifest must cover the complete artifact inventory')
    return entries


def required_selection(selection):
    selection=Path(selection)
    protocol=c.unseal(selection/'protocol.json')
    c.require(protocol.get('schema')=='isaforge-guarded-selection-v1' and
              protocol.get('scope')=='prospective' and protocol.get('target_workload')==WORKLOAD and
              type(protocol.get('target_labels_read')) is int and protocol['target_labels_read']==0,
              'Expected a zero-target-label prospective SHA256 selection protocol')
    artifacts=protocol.get('artifacts')
    _hashes(selection,artifacts)
    c.require(not {'protocol.json','protocol.json.sha256'} & set(artifacts),
              'Frozen protocol cannot include its own hash inventory')
    return set(artifacts)|{'protocol.json','protocol.json.sha256'},protocol


def check_prelabel(selection,prereg):
    selection,prereg=Path(selection),Path(prereg)
    entries=_manifest(prereg)
    required,selection_protocol=required_selection(selection)
    declared={name for name in entries if name.startswith('selection/')}
    c.require(declared=={'selection/'+name for name in required},
              'Preregistration must contain the complete frozen selection inventory')
    c.require({name.removeprefix('selection/') for name in _inventory(prereg) if name.startswith('selection/')}==required,
              'Unexpected or omitted preregistered selection file')
    for name in required:
        c.require(c.sha(_path(selection,name))==entries['selection/'+name],
                  'Changed prelabel selection artifact: '+name)
    protocol=c.unseal(prereg/'protocol.json')
    c.require(protocol.get('schema')=='isaforge-guarded-preregistration-v1' and
              type(protocol.get('target_labels_read')) is int and protocol['target_labels_read']==0 and
              protocol.get('target_workload')==WORKLOAD,'Invalid SHA256 preregistration scope')
    c.require(protocol.get('baseline_files')==BASELINES,'Complete fixed baseline-copy mapping required')
    c.require(protocol.get('selection_source_bindings')==selection_protocol['source_bindings'],
              'Preregistered selection sources differ')
    required_baselines={name+suffix for name in BASELINES.values() for suffix in ('','.sha256')}
    c.require(required_baselines|{'protocol.json','protocol.json.sha256'}<=set(entries),
              'Preregistration baseline/protocol inventory incomplete')
    for name in BASELINES.values():
        c.unseal(_path(prereg,name))
    return c.sha(prereg/'manifest.json')


def check_baselines(prereg,raw,selection):
    prereg,raw,selection=map(Path,(prereg,raw,selection))
    protocol=c.unseal(prereg/'protocol.json')
    c.require(protocol.get('baseline_files')==BASELINES,'Complete fixed baseline-copy mapping required')
    plan=c.unseal(raw/'plan.json')
    c.require(plan['context_id']==protocol['context_id'] and plan['workload']=='nettle-sha256',
              'Archived SHA256 baseline context differs')
    for native,copied in BASELINES.items():
        if native=='commands.json':
            continue  # The archived receipt list also contains paid target work.
        c.require(c.sha(_path(raw,native))==c.sha(_path(prereg,copied)),
                  'Preregistered baseline copy differs from native archive: '+native)
    before=c.unseal(prereg/BASELINES['commands.json'])
    evaluation=c.unseal(raw/'evaluation-protocol.json')
    commands=c.unseal(raw/'commands.json')
    c.require(isinstance(before,list) and before==evaluation['baseline_receipts'] and
              commands[:len(before)]==before,'Preregistered baseline receipt prefix differs')
    selection_protocol=c.unseal(selection/'protocol.json')
    c.require(c.sha(raw/'evaluation-protocol.json')==selection_protocol['evaluation_protocol_sha256'],
              'Selection/native protocol binding differs')


def replay(campaign=CAMPAIGN,output=OUTPUT,*,prereg=PREREG,selection=SELECTION):
    campaign,output,prereg,selection=map(Path,(campaign,output,prereg,selection))
    entries=_manifest(campaign)
    c.require({'provenance.json','provenance.json.sha256','native/manifest.json',
               'native/manifest.json.sha256'}<=set(entries),'Campaign provenance/native manifest missing')
    provenance=c.unseal(campaign/'provenance.json')
    c.require(provenance.get('schema')=='isaforge-guarded-campaign-provenance-v1',
              'Unknown guarded campaign provenance')
    manifest_sha=check_prelabel(selection,prereg)
    c.require(manifest_sha==provenance['prereg_manifest_sha256'],'Preregistration manifest differs from campaign')
    check_prelabel_commit(prereg,provenance['prelabel_commit'])
    sources=provenance.get('source_bindings')
    c.require(isinstance(sources,dict) and set(sources)=={SOURCE,REPORTER},
              'Reproducer and reporter source bindings required')
    _hashes(ROOT,sources)
    _hashes(selection,provenance.get('selection_manifest'),exact=True)
    required,_=required_selection(selection)
    c.require(required|{'report.json','report.json.sha256'}<=set(provenance['selection_manifest']),
              'Final selection manifest omits frozen artifacts or report')
    if (campaign/'selection-manifest.json').exists():
        c.require(c.unseal(campaign/'selection-manifest.json')==provenance['selection_manifest'],
                  'Separate final selection manifest differs')
    native=guarded_evidence.replay(campaign/'native',output)
    check_baselines(prereg,output,selection)
    result=guarded_selection.evaluate(selection,output,
        history_raw_root=ROOT/'generated/reproduction/budget-campaign',verify=True)
    c.require(native.get('new_native_jobs')==result.get('new_native_jobs')==0,
              'Replay unexpectedly reports new native jobs')
    return dict(target_workload=WORKLOAD,context_id=native['context_id'],
        charged_candidate_attempts=native['charged_candidate_attempts'],
        policy_seed_cap_budget_outcomes=result['selection']['policy_seed_cap_budget_outcomes'],
        exact_historical_prediction_refit=True,new_native_jobs=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('replay',),nargs='?',default='replay')
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--preregistration',type=Path,default=PREREG)
    parser.add_argument('--selection',type=Path,default=SELECTION)
    args=parser.parse_args(argv)
    print(replay(args.campaign,args.output,prereg=args.preregistration,selection=args.selection))


if __name__=='__main__':
    main()
