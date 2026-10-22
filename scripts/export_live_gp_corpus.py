"""Append the completed live GP source while preserving all historical evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b,codesign as c
from isaforge.speedup_corpus import family
from scripts.export_guarded_corpus import FIELDS,_csv
from scripts.report_live_gp_campaign import CAMPAIGN,PREREG,load
from scripts.reproduce_guarded_sha256 import _manifest

PREVIOUS=ROOT/'results/2026-10-21-ten-source-corpus'
OUTPUT=ROOT/'results/2026-10-22-eleven-source-corpus'


def export(previous,campaign,prereg,output):
    previous,campaign,prereg,output=map(lambda path:Path(path).resolve(),(previous,campaign,prereg,output))
    c.require(not output.exists() and not any(output.is_relative_to(path) or path.is_relative_to(output)
              for path in (previous,campaign,prereg)), 'Fresh corpus outside sealed inputs required')
    _manifest(previous);old=c.unseal(previous/'corpus.json')
    c.require(old['successful_labels']==len(old['rows'])==81 and len(old['failed_attempts'])==3 and
              old['total_candidate_attempts']==84 and len(old['independent_workload_groups'])==10 and len(old['contexts'])==11,
              'Complete81-success/3-failure/84-attempt corpus required')
    case=load(campaign,prereg);group=case['group'];audit=case['audit']
    c.require(case['cohort']['historical_costs']['source_corpus_sha256']==c.sha(previous/'corpus.json') and
              case['cohort']['historical_costs']['total_candidate_wall_seconds']==old['total_candidate_attempt_wall_seconds'],
              'Export history must equal the frozen prelabel training source and costs')
    c.require(group not in {row['workload_group'] for row in old['rows']+old['failed_attempts']},
              'The entire new source must be absent from historical data')
    rows,failures=list(old['rows']),list(old['failed_attempts'])
    labels={row['candidate_id']:row for row in case['outcomes']}
    for public in case['public']:
        row=labels[public['candidate_id']]
        enriched=dict(row,workload_group=group,candidate_family=family(row['formula']),
            measurement_timer_scope='recorded monotonic guarded-attempt elapsed including validation overhead; paired UTC/monotonic observations remain separate',
            outer_operation_seconds=case['outer_times'][row['candidate_id']])
        if b.validate_outcome(row,public):
            rows.append({**{key:enriched[key] for key in FIELDS},
                **{key:enriched.get(key) for key in ('measurement_record_seconds','measurement_timer_scope','outer_operation_seconds')}})
        else:
            c.require('failure_class' in row and type(row.get('reference_censored')) is bool,
                      'Failed attempts need explicit classification and censorship')
            enriched['correctness_verified']=None if row['reference_censored'] else False
            failures.append(enriched)
    c.require(len({row['candidate_id'] for row in rows+failures})==len(rows)+len(failures), 'Duplicate corpus candidate identity')
    benchmark=case['public'][0]['benchmark'];contexts=dict(old['contexts'])
    c.require(benchmark not in contexts and case['context']['workload_group']==group and
              case['context']['context_id']==audit['context_id'], 'Distinct complete source context required')
    contexts[benchmark]=case['context']
    clock=dict(historical=old['clock_accounting'],current=case['clock'])
    groups=sorted({row['workload_group'] for row in rows+failures})
    c.require(len(rows)+len(failures)==84+audit['charged_candidate_attempts'], 'Every charged attempt must remain represented')
    corpus=dict(schema='isaforge-consumed-guarded-corpus-v1',
        scope='Consumed ten-source history plus completed bounded native-GP source; every exported target label is now development data.',
        rows=rows,failed_attempts=failures,contexts=contexts,successful_labels=len(rows),independent_workload_groups=groups,
        historical_costs=dict(successful_labels=81,failed_attempts=3,total_candidate_attempts=84,
            total_candidate_wall_seconds=old['total_candidate_attempt_wall_seconds'],source_corpus_sha256=c.sha(previous/'corpus.json')),
        preserved_original_rows_digest=c.digest(old['rows']),preserved_original_failed_attempts_digest=c.digest(old['failed_attempts']),
        new_candidate_attempts=audit['charged_candidate_attempts'],total_candidate_attempts=84+audit['charged_candidate_attempts'],
        new_candidate_wall_seconds=audit['candidate_wall_seconds'],
        total_candidate_attempt_wall_seconds=old['total_candidate_attempt_wall_seconds']+audit['candidate_wall_seconds'],
        new_collection_costs={key:audit[key] for key in ('native_command_count','native_command_seconds','baseline_wall_seconds','baseline_record_seconds')},
        new_candidate_outer_operation_seconds=sum(case['outer_times'].values()),qualification_costs=case['cohort']['qualification'],
        historical_qualification_costs=old.get('qualification_costs'),historical_clock_accounting=old['clock_accounting'],
        current_paired_clock_accounting=case['clock'],clock_accounting=clock,actual_calendar_wall_seconds=None,
        reference_censored_candidates=sorted(row['candidate_id'] for row in failures if row.get('reference_censored')),
        new_live_native_attempts=3,new_oracle_reference_attempts=audit['charged_candidate_attempts']-3,
        timer_note='Original mixed-scope historical charges and their clock amendment remain unchanged. New CLI/ledger/native and paired-observer durations overlap; UTC and monotonic endpoint deltas are retained separately. Uninterrupted calendar wall time and adaptive-time savings are not established. Every historical candidate attempt is counted once; setup/calibration, qualification and model runtime remain separate.',
        split_unit='Entire source workload; all compiler/hardware contexts of a source must remain in the same held-out group.',
        new_model_fits=0,new_native_jobs=0)
    c.require(corpus['rows'][:81]==old['rows'] and corpus['failed_attempts'][:3]==old['failed_attempts'],
              'Historical rows and failed attempts must be preserved exactly')
    output.mkdir(parents=True)
    c.seal(output/'corpus.json',corpus);c.seal(output/'clock-accounting.json',clock)
    _csv(output/'verified-labels.csv',rows);_csv(output/'failed-attempts.csv',failures)
    c.seal(output/'provenance.json',dict(source_sha256=c.sha(Path(__file__)),report_loader_sha256=c.sha(ROOT/'scripts/report_live_gp_campaign.py'),
        previous_manifest_sha256=c.sha(previous/'manifest.json'),campaign_manifest_sha256=c.sha(campaign/'manifest.json'),
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),new_model_fits=0,new_native_jobs=0))
    (output/'README.md').write_text('# Consumed measured corpus after live GP collection\n\n'
        f"{len(rows)} verified successful labels, {len(failures)} preserved failures, {len(groups)} source workloads, {len(contexts)} contexts and {corpus['total_candidate_attempts']} charged candidate attempts. "
        'Original81 rows and three failures remain exactly unchanged. Unknown infrastructure failures carry no fabricated performance, correctness or hardware labels.\n\n'
        'The new source used three actual adaptive native GP queries before three separately measured oracle-reference candidates. '
        'Other policy/seed endpoints are charged cooperative replay. All six outcomes are now consumed development data; the live seed does not establish broad generalization. '
        'Keep every context of the same source together in held-out splits, with related-family exclusions.\n\n'
        'Historical84-attempt costs are counted once. Historical clock-accounting failures and qualification remain separate from the new paired UTC/monotonic observations; '
        'no uninterrupted elapsed-wall-time saving is claimed. This exporter performs zero model fits and zero native jobs. '
        'Run live_gp_campaign replay separately for complete raw, live-choice and deterministic model verification.\n')
    c.seal(output/'manifest.json',{path.name:c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return corpus


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,default=PREVIOUS)
    parser.add_argument('--campaign',type=Path,default=CAMPAIGN)
    parser.add_argument('--preregistration',type=Path,default=PREREG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();result=export(args.previous,args.campaign,args.preregistration,args.output)
    print(dict(successful_labels=result['successful_labels'],failed_attempts=len(result['failed_attempts']),
        total_candidate_attempts=result['total_candidate_attempts'],sources=len(result['independent_workload_groups']),
        contexts=len(result['contexts']),new_model_fits=0,new_native_jobs=0))


if __name__=='__main__':main()
