"""One fixed consumed-data whole-source diagnosis; no tuning or native jobs.

Both SHA contexts share a source fold and family exclusion. Selection stays
within each context, then contexts are averaged within source for macro metrics.
Bootstrap seeds are dependent repetitions, not independent source observations.
"""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasible_benefit import search
from isaforge.feasibility_selection import (FeasibilitySelectionPredictor,
    AREA_CAPS,CLOCK_MHZ,MODEL_SETTINGS,BUDGET_FEATURE,feasibility_label)
from isaforge.prospective_selection import PUBLIC_KEYS
from isaforge.speedup_corpus import family

CORPUS=ROOT/'results/2026-10-21-model-training-corpus/corpus.json'
SEEDS=(0,1,2,3,4)
METHODS=('factorized_feasibility_xgb','independent_hardware_gp','training_feasibility_prior')
SOURCES=('scripts/diagnose_factorized_selection.py','isaforge/feasibility_selection.py',
         'isaforge/feasible_benefit.py',*b.SOURCES)


def folds(corpus):
    success=corpus['rows'];failed=corpus['failed_attempts'];all_rows=success+failed
    c.require(len({r['candidate_id'] for r in all_rows})==len(all_rows),'Unique corpus candidate IDs required')
    for row in success:c.require(b.validate_outcome(row),'Successful fitting rows required')
    for row in failed:c.require(not b.validate_outcome(row),'Failed rows must have unknown hardware labels')
    c.require(len(success)==corpus['successful_labels'] and len(all_rows)==corpus['total_candidate_attempts'],
              'Corpus measurement counts differ')
    groups=sorted({r['workload_group'] for r in all_rows})
    c.require(groups==sorted(corpus['independent_workload_groups']),'Source grouping differs')
    result=[]
    for source in groups:
        target=[r for r in all_rows if r['workload_group']==source]
        families={family(r['formula']) for r in target}
        available=[r for r in success if r['workload_group']!=source]
        fitting=[r for r in available if family(r['formula']) not in families]
        fit_groups=sorted({r['workload_group'] for r in fitting})
        c.require(len(fit_groups)>=2,'At least two post-family-filter historical sources required: '+source)
        contexts=sorted({r['benchmark'] for r in target})
        c.require(all(sum(r['benchmark']==context for r in target)>=3 for context in contexts),
                  'Three-attempt context pool required')
        public=[{k:copy.deepcopy(r[k]) for k in PUBLIC_KEYS} for r in target]
        b.public_rows(public)
        result.append(dict(source=source,target=target,public=public,fitting=fitting,
            target_contexts=contexts,target_ids=[r['candidate_id'] for r in target],
            fitting_ids=[r['candidate_id'] for r in fitting],fitting_groups=fit_groups,
            excluded_related_ids=[r['candidate_id'] for r in available if family(r['formula']) in families],
            historical_available_successes=len(available),
            historical_available_attempt_seconds=sum(r['measurement_seconds'] for r in all_rows if r['workload_group']!=source),
            fitting_label_seconds=sum(r['measurement_seconds'] for r in fitting)))
    return result


def gp_feasibility(estimate,cap):
    return (b._probability_below(estimate['area_delta_lut4_mean'],estimate['area_delta_lut4_std'],cap)*
            b._probability_below(-estimate['routed_fmax_min_mhz_mean'],estimate['routed_fmax_min_mhz_std'],-CLOCK_MHZ)*
            estimate['device_fit_probability'])


def cap_violations(by_cap,method):
    """Monotonicity checks are label-free, including failed-attempt public rows."""
    maps={cap:{r['candidate_id']:r[method] for r in by_cap[str(cap)]} for cap in AREA_CAPS}
    pairs=[]
    for left,right in zip(AREA_CAPS,AREA_CAPS[1:]):
        for identity,value in maps[left].items():
            if value>maps[right][identity]:
                pairs.append(dict(candidate_id=identity,lower_cap=left,upper_cap=right,
                                  decrease=value-maps[right][identity]))
    return pairs


def stable(value):
    if isinstance(value,(list,tuple)):return [stable(v) for v in value]
    if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in
        ('selection_host_seconds','replay_search_host_seconds','inference_seconds')}
    return value


def run(output,*,corpus_path=CORPUS):
    output,corpus_path=Path(output),Path(corpus_path)
    c.require(not output.exists(),'Fresh diagnosis directory required')
    corpus=c.unseal(corpus_path);cohorts=folds(corpus)
    output.mkdir(parents=True)
    costs=dict(unique_successful_labels=len(corpus['rows']),unique_failed_attempts=len(corpus['failed_attempts']),
        unique_attempts=corpus['total_candidate_attempts'],
        recorded_verification_failures=sum(r.get('reference_censored') is False for r in corpus['failed_attempts']),
        unknown_infrastructure_attempts=sum(r.get('reference_censored') is True for r in corpus['failed_attempts']),
        failed_attempt_seconds=sum(r['measurement_seconds'] for r in corpus['failed_attempts']),
        unique_recorded_attempt_seconds=sum(r['measurement_seconds'] for r in corpus['rows']+corpus['failed_attempts']),
        declared_recorded_attempt_seconds=corpus['total_candidate_attempt_wall_seconds'],
        timer_note=corpus['timer_note'])
    c.require(abs(costs['unique_recorded_attempt_seconds']-costs['declared_recorded_attempt_seconds'])<1e-8,
              'Corpus unique attempt cost differs')
    protocol=dict(schema='isaforge-factorized-source-diagnosis-v1',scope='consumed-data development',
        corpus_path=str(corpus_path.resolve()),corpus_sha256=c.sha(corpus_path),
        source_bindings={name:c.sha(ROOT/name) for name in SOURCES},
        packages={name:importlib.metadata.version(name) for name in ('numpy','scipy','xgboost','scikit-learn')},
        seeds=list(SEEDS),area_caps=list(AREA_CAPS),clock_mhz=CLOCK_MHZ,
        model_settings=MODEL_SETTINGS,budget_feature=BUDGET_FEATURE,methods=list(METHODS),
        selection_policies=[METHODS[0],'latency_cost_heuristic'],selection_budgets=[1,3],
        failure_policy='Exclude from fitting/Brier; retain public query options and charged recorded attempts.',
        source_fold_policy='All contexts of source held out together; remove entire target pool formula families from other sources.',
        aggregation='Brier over successful source rows; seeds averaged per source; contexts averaged within source for selection; macro over sources.',
        cohorts=[{k:v for k,v in fold.items() if k not in ('target','public','fitting')} for fold in cohorts],
        costs=costs,new_native_jobs=0,calibration_claim=False,tuning=False)
    c.seal(output/'protocol.json',protocol)
    predictions=[];timings=[]
    for fold in cohorts:
        began=time.monotonic();gp=b.HardwareSurrogate().fit(fold['fitting']).predict(fold['public'])
        gp_seconds=time.monotonic()-began
        gp_map={row['candidate_id']:row for row in gp}
        prior={cap:statistics.mean(feasibility_label(r,cap) for r in fold['fitting']) for cap in AREA_CAPS}
        for seed in SEEDS:
            began=time.monotonic();model=FeasibilitySelectionPredictor(seed).fit(fold['fitting'])
            by_cap={}
            for cap in AREA_CAPS:
                values=model.predict(fold['public'],area_cap=cap)
                by_cap[str(cap)]=[dict(candidate_id=row['candidate_id'],
                    factorized_feasibility_xgb=row['feasibility_score_mean'],
                    independent_hardware_gp=gp_feasibility(gp_map[row['candidate_id']],cap),
                    training_feasibility_prior=prior[cap],factorized_prediction=row) for row in values]
            timings.append(dict(source=fold['source'],seed=seed,classifier_fit_and_predict_seconds=time.monotonic()-began,
                shared_gp_fit_and_predict_seconds=gp_seconds,historical_lut4_per_operation=model.area_per_op))
            predictions.append(dict(source=fold['source'],seed=seed,by_cap=by_cap,hardware_predictions=gp))
    c.seal(output/'predictions.json',predictions)
    c.seal(output/'timings.json',timings)
    # Retrospective labels were consumed, but score only after sealing all predictions.
    brier=[];violations=[];runs=[]
    for fold in cohorts:
        outcomes={row['candidate_id']:row for row in fold['target']}
        known=[r for r in fold['target'] if r.get('status','success')=='success']
        for predicted in [p for p in predictions if p['source']==fold['source']]:
            seed=predicted['seed']
            for method in METHODS:
                inconsistent=cap_violations(predicted['by_cap'],method)
                violations.append(dict(source=fold['source'],seed=seed,method=method,violation_count=len(inconsistent),
                    public_candidates=len(fold['public']),adjacent_cap_pairs=2*len(fold['public']),
                    violations=inconsistent))
            for cap in AREA_CAPS:
                estimates={row['candidate_id']:row for row in predicted['by_cap'][str(cap)]}
                for method in METHODS:
                    brier.append(dict(source=fold['source'],cap=cap,seed=seed,method=method,
                        known_rows=len(known),excluded_unknown_rows=len(outcomes)-len(known),
                        brier=statistics.mean((estimates[r['candidate_id']][method]-feasibility_label(r,cap))**2 for r in known)))
                for context in fold['target_contexts']:
                    public=[r for r in fold['public'] if r['benchmark']==context]
                    context_outcomes=[outcomes[r['candidate_id']] for r in public]
                    reference=max([1.0]+[r['speedup'] for r in context_outcomes if b._feasible(r,cap,CLOCK_MHZ)])
                    censored=any(r.get('reference_censored') is True for r in context_outcomes)
                    for policy in (METHODS[0],'latency_cost_heuristic'):
                        began=time.monotonic()
                        if policy==METHODS[0]:
                            adapter=[dict(candidate_id=r['candidate_id'],area_cap=cap,
                                mean_fractional_cycle_savings=estimates[r['candidate_id']]['factorized_prediction']['decision_score'],
                                original_prediction=estimates[r['candidate_id']]['factorized_prediction']) for r in public]
                            result=search(public,lambda r:copy.deepcopy(outcomes[r['candidate_id']]),
                                area_cap=cap,seed=seed,budget=3,predictions=adapter)
                        else:
                            # The heuristic never uses raw/ranking/normalized predictions;
                            # provide empty maps rather than fitting unrelated models.
                            fixed=dict(raw=[],ranking=[],normalized=[],hardware=predicted['hardware_predictions'],inference_seconds={})
                            result=b.search(public,fold['fitting'],lambda r:copy.deepcopy(outcomes[r['candidate_id']]),
                                area_cap=cap,clock_mhz=CLOCK_MHZ,seed=seed,budget=3,policy=policy,predictions=fixed)
                        elapsed=time.monotonic()-began
                        for point in result['curve']:
                            point.update(gap_to_best_verified=reference-point['best_speedup'],
                                reference_kind='best verified; full pool censored' if censored else 'measured fixed-pool oracle')
                        runs.append(dict(source=fold['source'],context=context,cap=cap,seed=seed,policy=policy,
                                         selection_host_seconds=elapsed,**result))
    source_brier=[];source_selection=[]
    for fold in cohorts:
        source=fold['source']
        for cap in AREA_CAPS:
            for method in METHODS:
                values=[r['brier'] for r in brier if r['source']==source and r['cap']==cap and r['method']==method]
                source_brier.append(dict(source=source,cap=cap,method=method,mean_brier=statistics.mean(values)))
            for policy in (METHODS[0],'latency_cost_heuristic'):
                for budget in (1,3):
                    selected=[r for r in runs if r['source']==source and r['cap']==cap and r['policy']==policy]
                    points=[r['curve'][budget-1] for r in selected]
                    source_selection.append(dict(source=source,cap=cap,policy=policy,budget=budget,
                        contexts=len(fold['target_contexts']),mean_best_speedup=statistics.mean(p['best_speedup'] for p in points),
                        mean_gap_to_best_verified=statistics.mean(p['gap_to_best_verified'] for p in points),
                        mean_recorded_target_seconds=statistics.mean(p['target_measurement_seconds'] for p in points),
                        mean_failed_attempts=statistics.mean(p['failed_attempts'] for p in points)))
    macro_brier=[dict(cap=cap,method=method,sources=len(cohorts),source_macro_brier=statistics.mean(
        r['mean_brier'] for r in source_brier if r['cap']==cap and r['method']==method)) for cap in AREA_CAPS for method in METHODS]
    source_violations=[dict(source=fold['source'],method=method,mean_violation_count=statistics.mean(
        r['violation_count'] for r in violations if r['source']==fold['source'] and r['method']==method),
        mean_violation_fraction=statistics.mean(r['violation_count']/r['adjacent_cap_pairs'] for r in violations
            if r['source']==fold['source'] and r['method']==method)) for fold in cohorts for method in METHODS]
    macro_violations=[dict(method=method,sources=len(cohorts),source_macro_violation_fraction=statistics.mean(
        r['mean_violation_fraction'] for r in source_violations if r['method']==method)) for method in METHODS]
    macro_selection=[]
    for cap in AREA_CAPS:
        for policy in (METHODS[0],'latency_cost_heuristic'):
            for budget in (1,3):
                selected=[r for r in source_selection if r['cap']==cap and r['policy']==policy and r['budget']==budget]
                macro_selection.append(dict(cap=cap,policy=policy,budget=budget,sources=len(cohorts),
                    source_macro_best_speedup=statistics.mean(r['mean_best_speedup'] for r in selected),
                    source_macro_gap_to_best_verified=statistics.mean(r['mean_gap_to_best_verified'] for r in selected),
                    source_macro_recorded_target_seconds=statistics.mean(r['mean_recorded_target_seconds'] for r in selected)))
    report=dict(protocol_sha256=c.sha(output/'protocol.json'),predictions_sha256=c.sha(output/'predictions.json'),
        per_seed_brier=brier,per_source_brier=source_brier,source_macro_brier=macro_brier,
        cross_cap_violations=violations,per_source_cross_cap_violations=source_violations,
        source_macro_cross_cap_violations=macro_violations,selection_runs=runs,per_source_selection=source_selection,
        source_macro_selection=macro_selection,costs=costs,new_native_jobs=0,
        limitations=['Six consumed sources are not prospective evidence or calibrated confidence.',
            'Candidate-bootstrap seed repetitions and cap replicas are dependent.',
            'All contexts of each source share a single held-out fitting cohort.',
            'UD unknown outcomes do not become hardware infeasibility or complete-pool oracles.',
            'Unique historical attempts are charged once globally; repeated fold/seed replay is not new measurement cost.',
            'Historical timer scopes differ and overlap with setup/native-command scopes.'])
    c.seal(output/'report.json',report)
    c.seal(output/'manifest.json',{str(path.relative_to(output)):c.sha(path) for path in sorted(output.rglob('*')) if path.is_file()})
    return report


def replay(reference,output,*,corpus_path=CORPUS):
    reference=Path(reference)
    manifest=c.unseal(reference/'manifest.json')
    expected={str(path.relative_to(reference)) for path in reference.rglob('*') if path.is_file()}-{'manifest.json','manifest.json.sha256'}
    c.require(set(manifest)==expected,'Complete diagnosis manifest required')
    for name,digest in manifest.items():
        path=(reference/name).resolve()
        c.require(not Path(name).is_absolute() and path.is_relative_to(reference.resolve()) and c.sha(path)==digest,
                  'Diagnosis artifact changed')
    protocol=c.unseal(reference/'protocol.json')
    c.require(protocol.get('schema')=='isaforge-factorized-source-diagnosis-v1' and
              protocol.get('scope')=='consumed-data development','Unknown diagnosis protocol')
    c.require(set(protocol['source_bindings'])==set(SOURCES),'Missing diagnosis source bindings')
    c.require(set(protocol['packages'])=={'numpy','scipy','xgboost','scikit-learn'},'Missing diagnosis package bindings')
    c.require(c.sha(corpus_path)==protocol['corpus_sha256'],'Diagnosis corpus changed')
    for name,digest in protocol['source_bindings'].items():c.require(c.sha(ROOT/name)==digest,'Diagnosis source changed')
    for name,version in protocol['packages'].items():c.require(importlib.metadata.version(name)==version,'Diagnosis dependency changed')
    result=run(output,corpus_path=corpus_path)
    c.require(c.unseal(Path(output)/'predictions.json')==c.unseal(reference/'predictions.json'),'Diagnosis predictions differ')
    c.require(stable(result)==stable(c.unseal(reference/'report.json')),'Diagnosis replay differs')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,default=CORPUS)
    parser.add_argument('--replay',type=Path)
    args=parser.parse_args(argv)
    result=(replay(args.replay,args.output,corpus_path=args.corpus) if args.replay else run(args.output,corpus_path=args.corpus))
    print(dict(sources=len({r['source'] for r in result['per_source_brier']}),
        selection_trajectories=len(result['selection_runs']),new_native_jobs=0))

if __name__=='__main__':main()
