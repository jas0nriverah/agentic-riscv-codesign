"""One fixed duration-removal adaptive-GP development ablation; no native jobs.

prepare seals all nine cases' unchanged cached initial predictions before run
opens target outcomes. run seals each paid-update acquisition before releasing
that query's outcome. replay repeats the same bounded experiment, excluding only
explicit host-inference timers from deterministic numerical comparisons.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import importlib.metadata
import math
from pathlib import Path
import shutil
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b,codesign as c,count_selection as count
from isaforge import factorized_selection_experiment as e
from isaforge.speedup_corpus import family
from scripts.export_guarded_corpus import _csv
from scripts.report_blind_campaign import POLICY_LABELS,endpoints_for_source
from scripts.report_budget_campaign import table
from scripts.reproduce_guarded_sha256 import _manifest,_hashes,_inventory

SCHEMA='isaforge-count-acquisition-development-v1'
OUTPUT=ROOT/'results/2026-10-22-count-acquisition-development'
CORPUS=ROOT/'results/2026-10-22-eleven-source-corpus/corpus.json'
EXPANDED=ROOT/'results/2026-10-22-expanded-history-verified'
BLIND=ROOT/'results/2026-10-21-blind-campaign'
DCT=ROOT/'results/2026-10-21-jfdctint-campaign'
LIVE=ROOT/'results/2026-10-22-live-gp-campaign'
TARGETS=('beebs-aha-compress','beebs-ndes','beebs-nettle-md5','beebs-jfdctint')
CAPS=(32,64,128);SEEDS=(0,1,2,3,4);BUDGETS=(1,2,3)
POLICIES={**POLICY_LABELS,count.POLICY:'Adaptive GP without inverse duration'}
SOURCES=tuple(dict.fromkeys(('scripts/evaluate_count_acquisition.py',*count.SOURCES,*e.SOURCES,
    'scripts/report_blind_campaign.py','scripts/report_budget_campaign.py','scripts/export_guarded_corpus.py',
    'scripts/reproduce_guarded_sha256.py')))
PACKAGES=('numpy','scipy','scikit-learn','xgboost')
FILES={'public.json':'controls11/model/public.json','history.json':'controls11/model/history.json',
       'predictions.json':'controls11/model/predictions.json','model-protocol.json':'protocol.json'}
HOST_TIMERS={'inference_seconds','mean_inference_seconds','paid_update_host_seconds'}
LIMITATIONS=[
    'All five target sources are consumed development data; old/expanded cohorts of one source are not independent targets.',
    'Only the adaptive GP inverse-duration acquisition factor is removed. Features, GP settings, benefit units and paid updates are unchanged.',
    'All twelve controls are exact archived replay, not newly measured native searches or retuned models.',
    'Five seeds are dependent. Source macro is computed separately for old and expanded AHA/NDES/MD5; DCT and Expint remain separate.',
    'Cached initial predictions are reused; only successful paid target observations enter subsequent GP fits.',
    'Every failed query is charged. Unknown outcomes are not negative hardware, correctness or performance labels.',
    'Historical90 attempts and qualified clock scopes are retained once; no uninterrupted wall-time or total-cost advantage is established.',
    'The provider boundary is cooperative local isolation, not an operating-system sandbox.',
    'Bootstrap/GP probabilities remain uncalibrated; no policy is promoted or selected from this bounded development comparison.']


def specs():
    result=[]
    for cohort in ('old','expanded'):
        for source in TARGETS:
            native=DCT if source==TARGETS[-1] else BLIND/'targets'/source
            result.append(dict(case_id=cohort+'__'+source,cohort=cohort,source=source,
                package=EXPANDED/'experiments'/cohort/source,audit=native/'audit.json',outer=native/'outer-times.json'))
    result.append(dict(case_id='fresh__beebs-expint',cohort='fresh',source='beebs-expint',
                       package=LIVE/'selection',audit=LIVE/'audit.json',outer=LIVE/'outer-times.json'))
    return result


def stable(value):
    if isinstance(value,(list,tuple)):return [stable(item) for item in value]
    if isinstance(value,dict):return {key:stable(item) for key,item in value.items() if key not in HOST_TIMERS}
    return value


def inventory(root):
    return {name:c.sha(Path(root)/name) for name in sorted(_inventory(root))}


def seal_manifest(root):
    c.seal(Path(root)/'manifest.json',{name:digest for name,digest in inventory(root).items()
        if name not in ('manifest.json','manifest.json.sha256')})


def planned_protocol():
    # Authenticating files by checksum does not expose labels to the search.
    for root in (CORPUS.parent,EXPANDED,BLIND,DCT,LIVE):_manifest(root)
    bindings={str(path.relative_to(ROOT)):c.sha(path) for path in
              (CORPUS,CORPUS.parent/'manifest.json',EXPANDED/'manifest.json',BLIND/'manifest.json',DCT/'manifest.json',LIVE/'manifest.json')}
    cases=[]
    expected_rows=(44,33,29,38,68,55,50,71,67)
    for spec,expected in zip(specs(),expected_rows):
        package=spec['package'];protocol=c.unseal(package/'protocol.json')
        _hashes(package,protocol['artifacts'])
        public=b.public_rows(c.unseal(package/FILES['public.json']))
        history=c.unseal(package/FILES['history.json']);predictions=c.unseal(package/FILES['predictions.json'])
        c.require(len(history)==expected and [row['candidate_id'] for row in history]==protocol['historical_training_ids'] and
            all(b.validate_outcome(row) and row['workload_group']!=spec['source'] for row in history),
            'Exact target-excluded original fitting cohort required')
        target_families={family(row['formula']) for row in public}
        c.require(all(family(row['formula']) not in target_families for row in history) and
            len({row['workload_group'] for row in history})>=2 and protocol['policies']==list(POLICY_LABELS),
            'Unchanged twelve controls and whole-source/family exclusions required')
        c.require([row['seed'] for row in predictions]==list(SEEDS) and all(
            len(row['hardware'])==len(public) and {value['candidate_id'] for value in row['hardware']}=={value['candidate_id'] for value in public}
            for row in predictions),'Complete cached initial prediction grid required')
        files={name:c.sha(package/original) for name,original in FILES.items()}
        for path in [package/name for name in FILES.values()]+[package/'report.json',spec['audit'],spec['outer']]:
            bindings[path.relative_to(ROOT).as_posix()]=c.sha(path)
        cases.append(dict(case_id=spec['case_id'],cohort=spec['cohort'],source=spec['source'],
            package=package.relative_to(ROOT).as_posix(),audit=spec['audit'].relative_to(ROOT).as_posix(),
            outer=spec['outer'].relative_to(ROOT).as_posix(),public_ids=[row['candidate_id'] for row in public],
            fitting_ids=protocol['historical_training_ids'],fitting_rows=len(history),
            fitting_groups=sorted({row['workload_group'] for row in history}),
            fitting_recorded_seconds=sum(row['measurement_seconds'] for row in history),
            original_cost_provenance=protocol['cost_provenance'],cached_files=files,
            archived_control_report_sha256=c.sha(package/'report.json')))
    return dict(schema=SCHEMA,scope='consumed-data development',new_policy=count.POLICY,
        change='Remove only expected inverse duration from existing adaptive GP acquisition.',cases=cases,
        initial_prediction_policy='Copy every unchanged cached initial package before any target scoring; zero initial refits.',
        update_policy='Fit the identical frozen GP to the identical historical cohort plus only successful paid target outcomes.',
        surrogate_factory='isaforge.budgeted_selection.HardwareSurrogate',gp_settings=b.GP_SETTINGS,
        feature_columns=list(b.STRUCTURAL_COLUMNS),benefit='max(0, public estimated_speedup - incumbent_speedup)',
        policies=list(POLICIES),area_caps=list(CAPS),seeds=list(SEEDS),budgets=list(BUDGETS),clock_mhz=12.,
        primary=dict(cohorts=['old','expanded'],sources=list(TARGETS[:3]),cap=64,budget=3,
            metric='Source-macro verified cycle reduction and regret; count-only versus original adaptive GP and merit.'),
        secondary=['All1/2/3 endpoints and all caps','First-query paired comparisons','DCT+32 separately','Consumed Expint separately'],
        corpus_path=CORPUS.relative_to(ROOT).as_posix(),input_bindings=bindings,
        source_bindings={name:c.sha(ROOT/name) for name in SOURCES},
        packages={name:importlib.metadata.version(name) for name in PACKAGES},
        timing_exclusions=sorted(HOST_TIMERS),tuning=False,new_native_jobs=0,limitations=LIMITATIONS)


def prepare(output):
    output=Path(output).resolve();c.require(not output.exists(),'Fresh prepared output required')
    c.require(not any(output.is_relative_to(path) or path.is_relative_to(output) for path in
        (CORPUS.parent,EXPANDED,BLIND,DCT,LIVE)),'Output must be outside frozen inputs')
    protocol=planned_protocol();output.mkdir(parents=True)
    c.seal(output/'protocol.json',protocol)
    for spec in specs():
        folder=output/'inputs'/spec['case_id'];folder.mkdir(parents=True)
        for name,original in FILES.items():
            for suffix in ('','.sha256'):shutil.copyfile(str(spec['package']/original)+suffix,str(folder/name)+suffix)
    c.seal(output/'prediction-release.json',dict(protocol_sha256=c.sha(output/'protocol.json'),
        case_ids=[row['case_id'] for row in protocol['cases']],initial_prediction_files=inventory(output/'inputs'),
        target_scoring_started=False,initial_model_refits=0,initial_model_predictions=0))
    c.seal(output/'prepared.json',dict(protocol_sha256=c.sha(output/'protocol.json'),
        prediction_release_sha256=c.sha(output/'prediction-release.json'),new_model_fits=0,new_native_jobs=0))
    return protocol


def authenticate(root):
    root=Path(root);protocol=c.unseal(root/'protocol.json');release=c.unseal(root/'prediction-release.json')
    c.require(protocol==planned_protocol(),'Prepared source, settings, input or cohort changed')
    c.require(protocol['schema']==SCHEMA and c.unseal(root/'prepared.json')==dict(protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'),new_model_fits=0,new_native_jobs=0),
        'Prepared prediction release binding differs')
    c.require(release['protocol_sha256']==c.sha(root/'protocol.json') and release['target_scoring_started'] is False and
        release['case_ids']==[row['case_id'] for row in protocol['cases']] and
        release['initial_prediction_files']==inventory(root/'inputs'),'Complete exact initial prediction inventory required')
    for case in protocol['cases']:
        folder=root/'inputs'/case['case_id']
        c.require(_inventory(folder)=={name+suffix for name in FILES for suffix in ('','.sha256')},
                  'Every cached initial package file required')
        for name,expected in case['cached_files'].items():c.require(c.sha(folder/name)==expected,'Cached initial input changed')
    return protocol


def annotate(result,labels,outer,cap,censored):
    reference=max([1.]+[row['speedup'] for row in labels.values() if b._feasible(row,cap,12)])
    for point in result['curve']:
        attempted=[labels[identity] for identity in point['attempted_ids']]
        point.update(target_outer_operation_seconds=sum(outer[identity] for identity in point['attempted_ids']),
            known_infeasible_attempts=sum(row.get('status','success')=='success' and not b._feasible(row,cap,12) for row in attempted),
            unknown_attempts=sum(row.get('status','success')!='success' for row in attempted),
            gap_to_best_verified=reference-point['best_speedup'],
            reference_kind='best verified; full pool censored' if censored else 'measured fixed-pool oracle')


def summarize_new(source,runs,outcomes,censored):
    """Same cycle-reduction equations as the unchanged twelve-policy presenter."""
    labels={row['candidate_id']:row for row in outcomes};result=[]
    c.require({(run['cap'],run['seed']) for run in runs}=={(cap,seed) for cap in CAPS for seed in SEEDS} and len(runs)==15,
              'Complete new-policy cap/seed grid required')
    for cap in CAPS:
        reference=max([1.]+[row['speedup'] for row in outcomes if b._feasible(row,cap,12)])
        ref_gain=1-1/reference
        for budget in BUDGETS:
            points=[run['curve'][budget-1] for run in runs if run['cap']==cap]
            for point in points:
                attempted=[labels[identity] for identity in point['attempted_ids']]
                best=max([1.]+[row['speedup'] for row in attempted if b._feasible(row,cap,12)])
                c.require(len(point['attempted_ids'])==len(set(point['attempted_ids']))==budget and
                    point['best_speedup']==best and point['target_measurement_seconds']==sum(row['measurement_seconds'] for row in attempted),
                    'New endpoint differs from uniquely charged outcomes')
            gains=[1-1/point['best_speedup'] for point in points];fractions=[gain/ref_gain for gain in gains] if ref_gain>0 else []
            result.append(dict(workload_group=source,policy=count.POLICY,cap=cap,budget=budget,dependent_seed_count=5,
                mean_best_verified_speedup=statistics.mean(point['best_speedup'] for point in points),
                mean_verified_cycle_reduction=statistics.mean(gains),reference_speedup=reference,reference_cycle_reduction=ref_gain,
                mean_cycle_reduction_regret=statistics.mean(ref_gain-gain for gain in gains),
                mean_oracle_cycle_reduction_fraction=statistics.mean(fractions) if fractions else None,
                at_least_90_percent_oracle_gain_runs=sum(value>=.9-1e-12 for value in fractions),
                oracle_gain_fraction_defined=ref_gain>0,improving_reference_hits=sum(reference>1 and point['best_speedup']==reference for point in points),
                reference_is_baseline=reference==1,reference_complete=not censored,regret_is_lower_bound=censored,
                mean_charged_attempts=budget,**{'mean_'+key:statistics.mean(point.get(key,0) for point in points) for key in
                    ('target_measurement_seconds','target_outer_operation_seconds','known_infeasible_attempts','unknown_attempts','inference_seconds')}))
    return result


def macro(endpoints):
    result=[]
    for cohort in ('old','expanded'):
        for policy in POLICIES:
            for cap in CAPS:
                for budget in BUDGETS:
                    rows=[row for row in endpoints if row['cohort']==cohort and row['workload_group'] in TARGETS[:3] and
                          (row['policy'],row['cap'],row['budget'])==(policy,cap,budget)]
                    c.require(len(rows)==3 and {row['workload_group'] for row in rows}==set(TARGETS[:3]),'Three distinct primary source units required')
                    result.append(dict(cohort=cohort,policy=policy,cap=cap,budget=budget,source_count=3,
                        **{key:statistics.mean(row[key] for row in rows) for key in
                            ('mean_verified_cycle_reduction','mean_cycle_reduction_regret','mean_target_measurement_seconds','mean_target_outer_operation_seconds')},
                        independent_units='Three sources; old/expanded reported separately; dependent seeds are not extra sources.'))
    return result


def verdict(delta):
    return 'tie' if abs(delta)<=1e-14 else ('win' if delta>0 else 'loss')


def run(root):
    root=Path(root).resolve();protocol=authenticate(root)
    c.require(not (root/'started.json').exists() and not (root/'report.json').exists(),'Fresh prepared run required; preserve failures')
    c.seal(root/'started.json',dict(protocol_sha256=c.sha(root/'protocol.json'),new_native_jobs=0))
    corpus=c.unseal(CORPUS);all_endpoints=[];comparisons=[];first=[];timings=[];new_reports={}
    began=time.monotonic()
    for case in protocol['cases']:
        identity=case['case_id'];folder=root/'inputs'/identity
        public=c.unseal(folder/'public.json');history=c.unseal(folder/'history.json');predictions=c.unseal(folder/'predictions.json')
        audit=c.unseal(ROOT/case['audit']);outer=c.unseal(ROOT/case['outer']);censored=e.checked_outcomes(public,audit['outcomes'],audit)
        labels={row['candidate_id']:row for row in audit['outcomes']}
        c.require(set(outer)==set(labels) and all(outer[key]>=row['measurement_seconds'] for key,row in labels.items()),'Complete qualified paid durations required')
        controls=ROOT/case['package']/'report.json';control=c.unseal(controls)
        c.require(c.sha(controls)==case['archived_control_report_sha256'] and
            control['protocol_sha256']==case['cached_files']['model-protocol.json'] and
            control['native_audit_digest']==c.digest(audit) and control['outcomes_sha256']==c.digest(audit['outcomes']),
            'Exact unchanged archived control report/native binding required')
        destination=root/'controls'/identity/'report.json';destination.parent.mkdir(parents=True)
        for suffix in ('','.sha256'):shutil.copyfile(str(controls)+suffix,str(destination)+suffix)
        runs=[];started=time.monotonic()
        for prediction in predictions:
            seed=prediction['seed']
            for cap in CAPS:
                released=[];trajectory=root/'acquisitions'/identity/f'cap{cap}-seed{seed}'
                def acquire(event):
                    c.require(event['charged_before_query']==len(released) and event['attempted_ids_before_query']==released,
                              'Only the charged prefix may influence acquisition')
                    c.seal(trajectory/f'{len(released):02d}.json',event)
                def provider(candidate):
                    event=c.unseal(trajectory/f'{len(released):02d}.json')
                    c.require(event['candidate_id']==candidate['candidate_id'] and candidate['candidate_id'] not in released,
                              'Chosen prediction must be sealed before one charged release')
                    released.append(candidate['candidate_id'])
                    return copy.deepcopy(labels[candidate['candidate_id']])
                searched=count.search(public,history,provider,area_cap=cap,clock_mhz=12.,seed=seed,budget=3,
                    predictions=prediction,surrogate_factory=b.HardwareSurrogate,on_acquire=acquire)
                c.require(len(released)==3,'All three attempts must remain charged')
                annotate(searched,labels,outer,cap,censored)
                runs.append(dict(cap=cap,seed=seed,**searched))
                old=next(value for value in control['runs'] if (value['policy'],value['cap'],value['seed'])==('hybrid_gp_adapt',cap,seed))
                first.append(dict(case_id=identity,cohort=case['cohort'],source=case['source'],cap=cap,seed=seed,
                    original_id=old['curve'][0]['attempted_ids'][0],count_only_id=searched['curve'][0]['attempted_ids'][0],
                    original_verified_cycle_reduction=1-1/old['curve'][0]['best_speedup'],
                    count_only_verified_cycle_reduction=1-1/searched['curve'][0]['best_speedup'],
                    result=verdict(1/old['curve'][0]['best_speedup']-1/searched['curve'][0]['best_speedup'])))
        new_report=dict(case_id=identity,source=case['source'],cohort=case['cohort'],runs=runs,reference_censored=censored,
            outcomes_sha256=c.digest(audit['outcomes']),protocol_sha256=c.sha(root/'protocol.json'),
            prediction_release_sha256=c.sha(root/'prediction-release.json'),new_native_jobs=0)
        c.seal(root/'new-policy'/identity/'report.json',new_report);new_reports[identity]=new_report
        endpoints=endpoints_for_source(case['source'],control,audit['outcomes'])+summarize_new(case['source'],runs,audit['outcomes'],censored)
        all_endpoints.extend(dict(case_id=identity,cohort=case['cohort'],**row) for row in endpoints)
        for row in [value for value in endpoints if value['policy']==count.POLICY]:
            for comparator in ('hybrid_gp_adapt','hybrid_gp_zero_shot','merit'):
                old=next(value for value in endpoints if (value['policy'],value['cap'],value['budget'])==(comparator,row['cap'],row['budget']))
                delta=row['mean_verified_cycle_reduction']-old['mean_verified_cycle_reduction']
                comparisons.append(dict(case_id=identity,cohort=case['cohort'],source=case['source'],cap=row['cap'],budget=row['budget'],
                    comparator=comparator,count_only_cycle_reduction=row['mean_verified_cycle_reduction'],
                    control_cycle_reduction=old['mean_verified_cycle_reduction'],cycle_reduction_change=delta,
                    count_only_regret=row['mean_cycle_reduction_regret'],control_regret=old['mean_cycle_reduction_regret'],result=verdict(delta),
                    significance_established=False))
        timings.append(dict(case_id=identity,new_search_host_monotonic_seconds=time.monotonic()-started,
            paid_gp_update_fit_calls=sum(value['paid_update_calls'] for value in runs),
            paid_gp_update_host_seconds=sum(value['paid_update_host_seconds'] for value in runs),initial_refits=0,
            initial_cached_inference_seconds=[row['inference_seconds']['hybrid_gp_adapt'] for row in predictions]))
    source_macro=macro(all_endpoints)
    costs=dict(unique_successful_labels=87,preserved_failed_attempts=3,unique_charged_attempts=90,
        unique_recorded_attempt_seconds=corpus['total_candidate_attempt_wall_seconds'],
        preserved_failures=corpus['failed_attempts'],clock_accounting=corpus['clock_accounting'],
        qualification_costs=corpus['qualification_costs'],historical_qualification_costs=corpus['historical_qualification_costs'],
        actual_calendar_wall_seconds=None,
        note='All90 native attempts counted once globally. Folds/policies reuse labels; paid replay sums are overlapping counterfactual costs, not additional native jobs or measured live-search durations.')
    result=dict(schema=SCHEMA,scope=protocol['scope'],protocol_sha256=c.sha(root/'protocol.json'),
        prediction_release_sha256=c.sha(root/'prediction-release.json'),policies=list(POLICIES),
        cases=9,distinct_target_sources=5,new_policy_trajectories=135,new_policy_seed_endpoints=405,
        archived_control_trajectories=1620,archived_control_seed_endpoints=4860,endpoints=all_endpoints,
        primary_source_macro=source_macro,primary=[row for row in source_macro if row['cap']==64 and row['budget']==3],
        comparisons=comparisons,first_query_comparisons=first,
        first_query_counts=dict(Counter(row['result'] for row in first)),
        q3_comparison_counts={comparator:dict(Counter(row['result'] for row in comparisons if row['budget']==3 and row['comparator']==comparator))
            for comparator in ('hybrid_gp_adapt','hybrid_gp_zero_shot','merit')},
        regressed_endpoints=[row for row in comparisons if row['result']=='loss'],costs=costs,
        representation_resolved=False,calibration_established=False,superiority_established=False,
        tuning=False,new_native_jobs=0,limitations=LIMITATIONS)
    c.seal(root/'report.json',result)
    c.seal(root/'runtime-costs.json',dict(records=timings,total_host_monotonic_seconds=time.monotonic()-began,
        scope='New paid-GP refits and cooperative replay only; cached initial fits are reused, native measurement durations are not rerun.'))
    for name,values in (('endpoints.csv',all_endpoints),('source-macro.csv',source_macro),('comparisons.csv',comparisons),
        ('first-query-comparisons.csv',first),('regressed-endpoints.csv',result['regressed_endpoints'])):_csv(root/name,values)
    primary_comparisons=[row for row in comparisons if row['cap']==64 and row['budget']==3]
    text=['# One duration-removal adaptive-GP development ablation',
        'Nine archived cohort/source cases, five dependent seeds, caps32/64/128 and budgets1/2/3. '
        'One new adaptive policy removes solely inverse duration. All12 controls, initial predictions, fitting cohorts, Gaussian feasibility, '
        'public speedup-improvement units and successful-paid update rules remain unchanged. All inputs/predictions were sealed before scoring; '
        'each dynamic acquisition prediction was sealed before its outcome provider released a label.',
        table([['Case','Comparator','Count gain%','Control gain%','Difference pp','Result'],['---']*6]+[
            [row['case_id'],row['comparator'],f"{100*row['count_only_cycle_reduction']:.9f}",
             f"{100*row['control_cycle_reduction']:.9f}",f"{100*row['cycle_reduction_change']:.9f}",row['result']] for row in primary_comparisons]),
        f"First-query paired outcomes over135 dependent case/cap/seed entries: {result['first_query_counts']}. "
        f"Query-three mean comparisons over27 cohort/source/cap endpoints: {result['q3_comparison_counts']}. "
        'Allcaps/budgets and every regression remain in CSV/JSON; source macros treat old/expanded AHA/NDES/MD5 separately. '
        'DCT and consumed Expint remain separate regression cases. These counts are descriptive, not independent-source significance.',
        'Semantic representation is still unresolved: removing a duration factor cannot distinguish the demonstrated NDES hardware-feature alias, '
        'repair constant semantics or add missing timing/device failure classes. The consumed first-query diagnosis justified this single ablation; '
        'full-trajectory regressions must be retained and no policy is promoted. Expint’s entire pool has only11 saved cycles /31843baseline cycles of headroom.',
        f"All90 earlier native attempts, including3 failures, remain uniquely charged once at{costs['unique_recorded_attempt_seconds']:.6f} recorded seconds. "
        'Only paid GP update fits and host replay are newly executed. Ledger/native/CLI/observer/qualification scopes overlap; historical clock qualifications '
        'are preserved. No uninterrupted elapsed-wall-time, broad generalization, calibrated confidence or total-cost advantage is established.',
        'Replay with `python scripts/evaluate_count_acquisition.py replay --root results/2026-10-22-count-acquisition-development --output generated/reproduction/count-acquisition`. '
        'Use a fresh output. Exact acquisition predictions, paid choices, numerical curves, all controls and all non-host-timing results must reproduce.']
    (root/'README.md').write_text('\n\n'.join(text)+'\n');seal_manifest(root)
    return result


def replay(reference,output):
    reference,output=Path(reference).resolve(),Path(output).resolve();_manifest(reference);authenticate(reference)
    original=c.unseal(reference/'report.json')
    prepare(output);result=run(output)
    c.require(c.sha(reference/'prediction-release.json')==c.sha(output/'prediction-release.json'),
              'Cached initial prediction release changed')
    c.require(stable(original)==stable(result),'Count-only deterministic numerical replay differs')
    for spec in specs():
        for directory in ('new-policy','controls'):
            left=c.unseal(reference/directory/spec['case_id']/'report.json');right=c.unseal(output/directory/spec['case_id']/'report.json')
            c.require(stable(left)==stable(right),'Exact paid observations, predictions or controls differ')
    left=inventory(reference/'acquisitions');right=inventory(output/'acquisitions')
    c.require(left==right,'Pre-release paid acquisition snapshots differ')
    c.seal(output/'replay-verification.json',dict(reference_manifest_sha256=c.sha(reference/'manifest.json'),
        compared_new_trajectories=135,compared_new_seed_endpoints=405,archived_controls_unchanged=True,
        excluded_host_timer_keys=sorted(HOST_TIMERS),new_native_jobs=0))
    seal_manifest(output);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','run','replay'))
    parser.add_argument('--root',type=Path,default=OUTPUT);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.output or args.root);print(dict(cases=len(result['cases']),new_model_fits=0,new_native_jobs=0))
    elif args.command=='run':
        result=run(args.root);print({key:result[key] for key in ('cases','new_policy_trajectories','new_policy_seed_endpoints','first_query_counts','q3_comparison_counts','new_native_jobs')})
    else:
        c.require(args.output is not None,'Fresh replay --output required');result=replay(args.root,args.output)
        print(dict(verified_new_trajectories=result['new_policy_trajectories'],new_native_jobs=0))


if __name__=='__main__':main()
