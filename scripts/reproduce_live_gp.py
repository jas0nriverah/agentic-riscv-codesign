"""Explicit post-collection amendment for one host-only endpoint timer.

Every native/model/decision check delegates to the frozen live controller.
Only endpoint mean_inference_seconds is compared descriptively: both archived
and freshly replayed values are preserved. Paid measurement durations, paired
clocks, predictions, policies, endpoint membership and all scientific values
remain exact. The original strict failure and frozen runtime remain intact.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from isaforge.model import _number
from scripts import live_gp_campaign as frozen

SOURCE='scripts/reproduce_live_gp.py'
CONTRACT='isaforge-live-gp-host-inference-amendment-v1'
FAILURE=ROOT/'results/2026-10-22-live-gp-replay-failure'
HOST_FIELD='mean_inference_seconds'
IDENTITY=('workload_group','policy','cap','budget')


def endpoint_comparison(archived,replayed):
    """Ignore precisely one top-level host timer; preserve both raw values."""
    c.require(isinstance(archived,list) and isinstance(replayed,list) and len(archived)==len(replayed) and archived,
              'Complete identical endpoint membership required')
    identities=set();observations=[]
    for left,right in zip(archived,replayed):
        c.require(isinstance(left,dict) and isinstance(right,dict) and set(left)==set(right) and
                  HOST_FIELD in left and all(key in left for key in IDENTITY), 'Exact endpoint field inventory required')
        identity=tuple(left[key] for key in IDENTITY)
        c.require(identity not in identities and identity==tuple(right[key] for key in IDENTITY),
                  'Unique identical endpoint identities and order required')
        identities.add(identity)
        # Canonical JSON equality also rejects type changes such as true versus 1.
        c.require(c.digest({key:value for key,value in left.items() if key!=HOST_FIELD}) ==
                  c.digest({key:value for key,value in right.items() if key!=HOST_FIELD}),
                  'Scientific endpoint, decision or paid measurement cost differs')
        a=_number(left[HOST_FIELD],'archived host inference seconds')
        b=_number(right[HOST_FIELD],'replayed host inference seconds')
        c.require(a>=0 and b>=0,'Nonnegative host inference durations required')
        observations.append(dict(**dict(zip(IDENTITY,identity)),archived_mean_inference_seconds=a,
            replayed_mean_inference_seconds=b,changed=a!=b))
    return dict(allowed_host_field=HOST_FIELD,endpoint_count=len(archived),
        changed_host_timer_rows=sum(row['changed'] for row in observations),observations=observations,
        scientific_fields_exact=True,paid_measurement_costs_exact=True,tolerance_used=False)


def strict_failure(path,campaign,provenance):
    path=Path(path).resolve();frozen.prior._manifest(path)
    failure=c.unseal(path/'failure.json');log=path/'strict-replay.log'
    c.require(failure.get('schema')=='isaforge-live-gp-strict-replay-failure-v1' and
              failure.get('prelabel_commit')==provenance['prelabel_commit'] and
              failure.get('campaign_manifest_sha256')==c.sha(Path(campaign)/'manifest.json') and
              failure.get('frozen_runtime_sha256')==c.sha(ROOT/frozen.SOURCE) and
              failure.get('strict_log_sha256')==c.sha(log) and
              failure.get('error')=='Final campaign decisions or costs differ' and
              failure.get('source_changed') is False and failure.get('raw_or_model_artifacts_changed') is False and
              'ValueError: Final campaign decisions or costs differ' in log.read_text(),
              'Exact preserved frozen strict replay failure required')
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        manifest_sha256=c.sha(path/'manifest.json'),failure_sha256=c.sha(path/'failure.json'),
        log_sha256=c.sha(log),frozen_runtime_sha256=failure['frozen_runtime_sha256'],
        error=failure['error'])


def replay(campaign,output,*,failure_path=FAILURE):
    campaign,output=map(lambda path:Path(path).resolve(),(campaign,output))
    frozen.prior._manifest(campaign)
    provenance=c.unseal(campaign/'provenance.json');prereg=ROOT/provenance['preregistration']
    cohort,group,target,_=frozen.authenticate(prereg)
    frozen.fresh_output(output,prereg=prereg,native=target['original_root'],cohort=cohort,extra=(campaign,failure_path))
    c.require(provenance['schema']==frozen.SCHEMA+'-campaign' and provenance['source_bindings']==cohort['source_bindings'] and
              provenance['prereg_manifest_sha256']==c.sha(prereg/'manifest.json'),'Campaign/prelabel binding differs')
    failure=strict_failure(failure_path,campaign,provenance)
    frozen.prior.check_git_checkpoint(prereg,provenance['prelabel_commit'])
    raw=output/'native'
    audited=frozen.workload().replay(campaign/'native',raw);frozen.check_baseline(prereg,group,raw)
    frozen.prior.check_release(campaign/'release.json',prereg,provenance['prelabel_commit'],raws={group:raw})
    checked,times,live,whole=frozen.check_collection(prereg,raw,campaign/'collection',campaign/'release.json')
    c.require(checked==audited==c.unseal(campaign/'audit.json') and times==c.unseal(campaign/'outer-times.json'),
              'Replayed native outcomes/timers differ')
    selection=campaign/'selection';required,_=frozen.prior.required_selection(prereg/'targets'/group/'selection')
    c.require(frozen.prior._inventory(selection)==required|frozen.prior.FINAL_REPORTS,'Complete final selection package required')
    for name in required:
        c.require(c.sha(selection/name)==c.sha(prereg/'targets'/group/'selection'/name),'Prelabel model changed')
    refits=frozen.prior.verify_refits(selection)
    report=frozen.experiment.evaluate(selection,audited['outcomes'],native_audit=audited,outer_times=times,verify=True)
    archived=c.unseal(campaign/'endpoints.json')
    replayed=frozen.endpoints_for_source(group,report,audited['outcomes'])
    comparison=endpoint_comparison(archived,replayed)
    c.require(frozen.b.stable(provenance['live_best'])==frozen.b.stable(live['search']['curve'][-1]) and
              provenance['collection_paired_durations']==whole['durations'],'Final campaign decisions or paired costs differ')
    c.require(report['trajectories']==180 and report['endpoints']==540 and report['new_native_jobs']==0,
              'Complete twelve-policy hardware-free replay required')
    c.seal(output/'archived-endpoints.json',archived);c.seal(output/'replayed-endpoints.json',replayed)
    c.seal(output/'host-inference-comparison.json',comparison)
    shutil.copyfile(Path(failure_path)/'strict-replay.log',output/'strict-replay-failure.log')
    result=dict(charged_candidate_attempts=audited['charged_candidate_attempts'],trajectories=report['trajectories'],
        endpoints=report['endpoints'],**refits,new_native_jobs=0,live_trace_exact=True,
        accounting_contract=CONTRACT,phase='post-collection host-inference accounting amendment',
        adapter_source_bindings={SOURCE:c.sha(ROOT/SOURCE)},frozen_runtime_source_sha256=c.sha(ROOT/frozen.SOURCE),
        campaign_manifest_sha256=c.sha(campaign/'manifest.json'),prelabel_commit=provenance['prelabel_commit'],
        preserved_strict_failure=failure,host_inference_comparison_sha256=c.sha(output/'host-inference-comparison.json'),
        archived_endpoints_sha256=c.sha(output/'archived-endpoints.json'),replayed_endpoints_sha256=c.sha(output/'replayed-endpoints.json'),
        changed_host_timer_rows=comparison['changed_host_timer_rows'],
        limitation='Only mean_inference_seconds is host-dependent. All scientific values, paid costs, predictions and paired clocks match exactly; no input or timer is rewritten.')
    c.seal(output/'host-inference-amendment.json',result)
    frozen.prior._seal_manifest(output)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('replay',))
    parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--strict-failure',type=Path,default=FAILURE)
    args=parser.parse_args(argv)
    print(replay(args.campaign,args.output,failure_path=args.strict_failure))


if __name__=='__main__':main()
