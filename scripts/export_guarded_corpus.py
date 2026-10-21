"""Export authenticated consumed history plus a completed guarded workload."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c, guarded_selection as selection
from isaforge.prospective_selection import PUBLIC_KEYS
from isaforge.speedup_corpus import family

SOURCE='scripts/export_guarded_corpus.py'
DEFAULT_SELECTION=ROOT/'results/2026-10-21-sha256-selection'
DEFAULT_TARGET=ROOT/'generated/reproduction/guarded-sha256'
FIELDS=(*PUBLIC_KEYS,'workload_group','candidate_family','speedup','area','area_cap',
    'area_delta_lut4','routed_fmax_min_mhz','device_fits','timing_feasible','correctness_verified',
    'measurement_source','measurement_seconds','baseline_cycles','candidate_cycles',
    'baseline_period_ns','candidate_period_ns')


def history_interpretations():
    root=selection.CORPUS.parent
    manifest=c.unseal(root/'manifest.json'); name='failed-attempt-interpretation.json'
    c.require(c.sha(root/name)==manifest[name],'Historical failure interpretation changed')
    return c.unseal(root/name)['rows'],c.sha(root/'manifest.json')


def _csv(path,rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,sort_keys=True,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def export(selection_root,target_root,output,*,history_raw_root=selection.HISTORY_RAW):
    selection_root,target_root,output=map(lambda p:Path(p).resolve(),(selection_root,target_root,output))
    c.require(not output.exists(),'Use a fresh corpus output directory')
    c.require(not output.is_relative_to(target_root) and not output.is_relative_to(selection_root),
              'Corpus output must be outside native/selection evidence roots')
    history,costs=selection.authenticate_history(history_raw_root)
    report=selection.evaluate(selection_root,target_root,history_raw_root=history_raw_root,verify=True)
    c.require(report['historical_costs']==costs,'Historical attempt costs differ')
    checked=report['raw_audit']
    c.require(checked['attempt_collection_complete'] and checked['candidate_wall_seconds_complete'] and
              not checked['unattempted'] and len(checked['outcomes'])==len(checked['public']),
              'Complete charged guarded pool required before consumed export')
    protocol=c.unseal(selection_root/'protocol.json'); model=c.unseal(selection_root/'model/protocol.json')
    group=protocol['target_workload']; contexts={**history['contexts'],**model['contexts']}
    rows=[dict(row,measurement_record_seconds=row.get('measurement_record_seconds'),
               measurement_timer_scope='historical measurement record wall') for row in history['rows']]
    annotations,history_manifest=history_interpretations(); failed=[]
    for row in history['failed_attempts']:
        match=[v for v in annotations if v['workload']==row['workload_group'] and v['formula']==row['formula']]
        c.require(len(match)==1 and match[0]['failure_reason']==row['error'] and
                  match[0]['measurement_seconds']==row['measurement_seconds'],'Historical failure identity differs')
        item=match[0]
        failed.append(dict(row,failure_class=item['failure_class'],reference_censored=item['reference_censored'],
            correctness_verified=item['correctness_verified'],measurement_timer_scope='historical failed-attempt wall'))
    for row in checked['outcomes']:
        enriched=dict(row,workload_group=group,candidate_family=family(row['formula']),
                      measurement_timer_scope='guarded attempt ledger wall including validation overhead')
        if row.get('status','success')=='success': rows.append(enriched)
        else:
            c.require('failure_class' in row and type(row.get('reference_censored')) is bool,'Failure classification missing')
            c.require(not any(k in row for k in ('speedup','candidate_cycles','area_delta_lut4')),'Failed attempt has invented labels')
            enriched['correctness_verified']=None if row['reference_censored'] else False
            failed.append(enriched)
    canonical=[{**{k:row[k] for k in FIELDS},'measurement_record_seconds':row.get('measurement_record_seconds'),
                'measurement_timer_scope':row['measurement_timer_scope']} for row in rows]
    c.require(len({r['candidate_id'] for r in canonical+failed})==len(canonical)+len(failed),'Duplicate corpus candidate identity')
    corpus=dict(schema='isaforge-consumed-guarded-corpus-v1',scope='Consumed data for later protocols; no new held-out claim.',
        rows=canonical,failed_attempts=failed,contexts=contexts,successful_labels=len(canonical),
        independent_workload_groups=sorted({r['workload_group'] for r in canonical}),
        historical_costs=costs,new_candidate_attempts=checked['charged_candidate_attempts'],
        total_candidate_attempts=costs['total_candidate_attempts']+checked['charged_candidate_attempts'],
        new_candidate_wall_seconds=checked['candidate_wall_seconds'],
        new_collection_costs={key:checked[key] for key in ('native_command_seconds','native_command_count',
            'baseline_wall_seconds','baseline_record_seconds') if key in checked},
        total_candidate_attempt_wall_seconds=costs['total_candidate_wall_seconds']+checked['candidate_wall_seconds'],
        timer_note='Old success durations are measurement-record wall; new durations are attempt-ledger wall including validation overhead. Optional measurement_record_seconds retains the narrower new measurement timer. Native commands overlap these scopes; setup/baselines/calibration/inference are separate.',
        reference_censored_candidates=checked['reference_censored_candidates'],new_native_jobs=0)
    bindings={SOURCE:c.sha(ROOT/SOURCE),**protocol['source_bindings'],**model['source_bindings']}
    provenance=dict(source_bindings=bindings,packages=model['packages'],history_corpus_sha256=c.sha(selection.CORPUS),
        history_manifest_sha256=history_manifest,selection_protocol_sha256=c.sha(selection_root/'protocol.json'),
        selection_report_sha256=c.sha(selection_root/'report.json'),evaluation_protocol_sha256=c.sha(target_root/'evaluation-protocol.json'),
        context_id=checked['context_id'],replay_verified=True,new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'corpus.json',corpus); c.seal(output/'provenance.json',provenance)
    _csv(output/'verified-labels.csv',canonical); _csv(output/'failed-attempts.csv',failed)
    c.seal(output/'manifest.json',{p.name:c.sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    return corpus


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-root',type=Path,default=DEFAULT_SELECTION)
    parser.add_argument('--target-root',type=Path,default=DEFAULT_TARGET)
    parser.add_argument('--history-raw-root',type=Path,default=selection.HISTORY_RAW)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    result=export(args.selection_root,args.target_root,args.output,history_raw_root=args.history_raw_root)
    print(dict(successful_labels=result['successful_labels'],failed_attempts=len(result['failed_attempts']),
               workload_groups=len(result['independent_workload_groups']),new_native_jobs=0))


if __name__=='__main__': main()
