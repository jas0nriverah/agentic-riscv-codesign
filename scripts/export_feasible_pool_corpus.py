"""Append the authenticated fresh candidate pool without inventing a workload."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.speedup_corpus import family
from scripts.export_guarded_corpus import FIELDS, _csv

PREVIOUS = ROOT/'results/2026-10-21-six-workload-corpus'
CAMPAIGN = ROOT/'results/2026-10-21-disjoint-sha256-campaign'


def export(previous, campaign, output):
    previous,campaign,output=map(lambda p:Path(p).resolve(),(previous,campaign,output))
    c.require(not output.exists(),'Fresh corpus directory required')
    c.require(not output.is_relative_to(previous) and not output.is_relative_to(campaign),
              'Keep consumed corpus outside original evidence roots')
    manifest=c.unseal(previous/'manifest.json')
    for name,expected in manifest.items():
        path=(previous/name).resolve()
        c.require(path.is_relative_to(previous) and c.sha(path)==expected,'Historical corpus changed')
    old=c.unseal(previous/'corpus.json')
    audit=c.unseal(campaign/'audit.json')
    c.require(audit['outcomes']==c.unseal(campaign/'outcomes.json'),'Audited pool outcomes differ')
    c.require(audit['attempt_collection_complete'] and audit['candidate_wall_seconds_complete']
              and not audit['unattempted'],'Complete charged pool required')
    public=b.public_rows(audit['public'])
    group='embench-nettle-sha256'
    c.require(all(row['benchmark'].split(':',1)[0]==group for row in public),'Different target source')
    rows=[dict(row) for row in old['rows']]
    failed=[dict(row) for row in old['failed_attempts']]
    labels={row['candidate_id']:row for row in audit['outcomes']}
    c.require(len(labels)==len(public) and set(labels)=={row['candidate_id'] for row in public},
              'One unique outcome per public candidate required')
    for candidate in public:
        row=labels[candidate['candidate_id']]
        successful=b.validate_outcome(row,candidate)
        enriched=dict(row,workload_group=group,candidate_family=family(row['formula']),
            measurement_timer_scope='guarded attempt ledger wall including validation overhead')
        if successful:
            rows.append({**{key:enriched[key] for key in FIELDS},
                'measurement_record_seconds':row.get('measurement_record_seconds'),
                'measurement_timer_scope':enriched['measurement_timer_scope']})
        else:
            c.require('failure_class' in row and type(row.get('reference_censored')) is bool,
                      'Failure classification required')
            c.require(not any(key in row for key in ('speedup','candidate_cycles','area_delta_lut4')),
                      'Failed attempt must not contain fabricated labels')
            enriched['correctness_verified']=None if row['reference_censored'] else False
            failed.append(enriched)
    c.require(len({row['candidate_id'] for row in rows+failed})==len(rows)+len(failed),
              'Duplicate corpus candidate identity')
    context=c.unseal(ROOT/'results/2026-10-21-feasible-benefit-preregistration/baseline/context.json')
    c.require(context['context_id']==audit['context_id'],'Target provenance context differs')
    contexts={**old['contexts'],public[0]['benchmark']:context}
    groups=sorted({row['workload_group'] for row in rows})
    c.require(groups==old['independent_workload_groups'],'A fresh pool is not a new workload')
    corpus=dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Consumed original six workloads plus fresh disjoint SHA256 candidates; no new source-generalization claim.',
        rows=rows,failed_attempts=failed,contexts=contexts,successful_labels=len(rows),
        independent_workload_groups=groups,
        historical_costs=dict(successful_labels=old['successful_labels'],failed_attempts=len(old['failed_attempts']),
            total_candidate_attempts=old['total_candidate_attempts'],
            total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'],
            source_corpus_sha256=c.sha(previous/'corpus.json')),
        new_candidate_attempts=audit['charged_candidate_attempts'],
        total_candidate_attempts=old['total_candidate_attempts']+audit['charged_candidate_attempts'],
        new_candidate_wall_seconds=audit['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=old['total_candidate_attempt_wall_seconds']+audit['candidate_wall_seconds'],
        new_collection_costs={key:audit[key] for key in ('native_command_seconds','native_command_count',
            'baseline_wall_seconds','baseline_record_seconds') if key in audit},
        reference_censored_candidates=sorted({row['candidate_id'] for row in failed if row.get('reference_censored')}),
        timer_note='Historical measurement-record and guarded attempt-ledger walls retain their distinct scopes. Native command durations overlap these timers. Baseline/setup, calibration, fitting and inference remain separate.',
        new_native_jobs=0)
    output.mkdir(parents=True)
    c.seal(output/'corpus.json',corpus)
    _csv(output/'verified-labels.csv',rows)
    _csv(output/'failed-attempts.csv',failed)
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(Path(__file__)),
        previous_manifest_sha256=c.sha(previous/'manifest.json'),
        audit_sha256=c.sha(campaign/'audit.json'),outcomes_sha256=c.sha(campaign/'outcomes.json'),
        campaign_provenance_sha256=c.sha(campaign/'provenance.json'),new_native_jobs=0))
    (output/'README.md').write_text(
        '# Expanded measured selection dataset\n\n'
        f"{len(rows)} verified whole-program speedup/hardware labels, {len(failed)} separately retained failures, "
        f"{len(groups)} source workloads, {len(contexts)} explicit contexts and "
        f"{corpus['total_candidate_attempts']} candidate attempts. Six disjoint SHA256 candidates add "
        'new instruction measurements on the original full source/input; they do not add a seventh workload.\n\n'
        'The new model comparison excluded the entire SHA256 source and then related formula families from fitting. '
        'This combined export becomes consumed development data for subsequent protocols. Future source holdouts '
        'must exclude all contexts of the source together. Failures are not zero-speedup labels; the unresolved '
        'historical UD infrastructure attempt still censors that complete pool.\n\n'
        'Regenerate with `python scripts/export_feasible_pool_corpus.py --output generated/expanded-model-corpus`. '
        'The CLI first authenticates and replays the new processor evidence, prelabel Git checkpoint and fixed policies. '
        'JSON and CSV retain signed cycle benefit, integrated LUT4/timing/correctness and distinct cost scopes.\n')
    c.seal(output/'manifest.json',{path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return corpus


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,default=PREVIOUS)
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from scripts.reproduce_disjoint_sha256 import replay
    replay(campaign=args.campaign)
    result=export(args.previous,args.campaign,args.output)
    print(dict(successful_labels=result['successful_labels'],failed_attempts=len(result['failed_attempts']),
        workload_groups=len(result['independent_workload_groups']),contexts=len(result['contexts']),new_native_jobs=0))


if __name__=='__main__':
    main()
