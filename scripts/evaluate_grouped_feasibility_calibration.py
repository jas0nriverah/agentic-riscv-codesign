"""Fixed nested workload/family-held-out feasibility calibration diagnostic.

Consumed development data only. No promotion, target dispatch or model sweep.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
import math
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, budgeted_selection as b
from isaforge.feasibility_selection import FeasibilitySelectionPredictor, feasibility_label
from isaforge.speedup_corpus import family
from isaforge.ranking import SpeedupRanker
from scripts import evaluate_feasibility_model_families as screen
from scripts.evaluate_ast_path_feasibility import probability_metrics

CAP = 64
BUDGETS = (1, 2, 3)
POLICIES = ('raw_factorized', 'calibrated_factorized', 'pairwise', 'merit', 'calibrated_latency', 'frequency', 'random')
SETTINGS = dict(method='group-balanced logistic calibration of clipped logit score',
    C=1.0, solver='lbfgs', seed=0, minimum_calibration_groups=5,
    fallback='identity for fewer than five groups, one class, or nonpositive fitted slope',
    clipping=1e-6, model='unchanged 20-member feasibility XGBoost ensemble',
    cap=CAP, budgets=list(BUDGETS), random_seeds=list(range(5)),
    scope='retrospective consumed development; nested workload and canonical-family holdouts',
    primary='workload-macro verified cycle reduction at B3; probability metrics secondary',
    promotion='none automatically; fresh prospective measurement required')


def fit_calibrator(records):
    """Only inner-held-out predictions/labels enter this fixed calibration fit."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    counts = Counter(r['group'] for r in records)
    labels = [r['label'] for r in records]
    fallback = dict(kind='identity', slope=1., intercept=0., groups=len(counts), rows=len(records))
    if len(counts) < SETTINGS['minimum_calibration_groups'] or len(set(labels)) < 2:
        return dict(fallback, reason='insufficient_groups_or_classes')
    c.require(all(r['label'] in (0,1) and math.isfinite(r['score']) and 0 <= r['score'] <= 1
                  for r in records), 'Invalid calibration records')
    x = np.array([[_logit(r['score'])] for r in records])
    # Equal total weight per workload; overall weight sum remains n records.
    weights = np.array([len(records)/(len(counts)*counts[r['group']]) for r in records])
    model = LogisticRegression(C=1., solver='lbfgs', random_state=0, max_iter=1000)
    model.fit(x, labels, sample_weight=weights)
    slope, intercept = float(model.coef_[0,0]), float(model.intercept_[0])
    if slope <= 0:
        return dict(fallback, reason='nonpositive_slope')
    return dict(kind='logistic', slope=slope, intercept=intercept,
                groups=len(counts), rows=len(records), reason=None)


def _logit(value):
    p = min(1-SETTINGS['clipping'], max(SETTINGS['clipping'], float(value)))
    return math.log(p/(1-p))


def apply_calibrator(calibrator, scores):
    from scipy.special import expit
    c.require(all(math.isfinite(float(s)) and 0 <= s <= 1 for s in scores), 'Invalid scores')
    if calibrator['kind'] == 'identity':
        return list(scores)
    return [float(expit(calibrator['slope']*_logit(s)+calibrator['intercept'])) for s in scores]


def split(rows, failures, group):
    return screen._split_with_failures(rows, failures, group)


def orders(public, raw, calibrated, rank_scores):
    import random
    ids = [r['candidate_id'] for r in public]
    indexed = dict(zip(ids,public))
    result = {}
    for name, scores in [('raw_factorized',raw),('calibrated_factorized',calibrated)]:
        result[name] = sorted(ids, key=lambda i: (
            -scores[i]*max(0,indexed[i]['latency_features']['estimated_saved_cycles']/indexed[i]['latency_features']['baseline_cycles']),
            -indexed[i]['latency_features']['estimated_speedup'],i))
    result['pairwise'] = sorted(ids,key=lambda i:(-rank_scores[i],i))
    for name,key in [('merit','saved'),('frequency','runs')]:
        result[name] = sorted(ids,key=lambda i:(-indexed[i][key],i))
    result['calibrated_latency'] = sorted(ids,key=lambda i:(-indexed[i]['latency_features']['estimated_speedup'],i))
    for seed in range(5):
        shuffled=sorted(ids);random.Random(seed).shuffle(shuffled);result[f'random:{seed}']=shuffled
    return result


def run(corpus_path, output):
    from scripts.export_expanded_selection_corpus import authenticate
    corpus_path, output = Path(corpus_path).resolve(), Path(output).resolve()
    corpus = authenticate(corpus_path)
    if isinstance(corpus,tuple):corpus=corpus[0]
    rows, failures=corpus['rows'],corpus['failed_attempts']
    c.require(all(isinstance(r.get('measurement_seconds'), (int,float)) and
                  math.isfinite(r['measurement_seconds']) and r['measurement_seconds'] >= 0
                  for r in rows+failures), 'All replay attempts require known measured cost')
    c.require(not output.exists(), 'Fresh output required')
    output.mkdir(parents=True)
    protocol=dict(SETTINGS, corpus_sha256=c.sha(corpus_path/'corpus.json'),
        source_bindings={n:c.sha(ROOT/n) for n in ('scripts/evaluate_grouped_feasibility_calibration.py',
        'scripts/export_expanded_selection_corpus.py','isaforge/feasibility_selection.py','isaforge/ranking.py',
        'scripts/evaluate_feasibility_model_families.py','scripts/evaluate_ast_path_feasibility.py')})
    c.seal(output/'protocol.json',protocol)
    started=time.monotonic();folds=[];runs=[];metrics=[]
    groups=sorted({r['workload_group'] for r in rows})
    for group in groups:
        training,target,failed,excluded=split(rows,failures,group)
        target_families={family(r['formula']) for r in target+failed}
        available_failures=[r for r in failures if r['workload_group']!=group and family(r['formula']) not in target_families]
        records=[];inner_splits=[]
        for inner in sorted({r['workload_group'] for r in training}):
            inner_train,valid,inner_failed,inner_excluded=split(training,available_failures,inner)
            if len(inner_train)<3 or len({r['workload_group'] for r in inner_train})<2:
                inner_splits.append(dict(group=inner,status='skipped_insufficient_training'));continue
            predictor=FeasibilitySelectionPredictor(seed=0).fit(inner_train)
            predictions=predictor.predict([screen._public(r) for r in valid],area_cap=CAP)
            records.extend(dict(group=inner,candidate_id=r['candidate_id'],label=feasibility_label(r,CAP),
                score=p['feasibility_score_mean']) for r,p in zip(valid,predictions))
            inner_splits.append(dict(group=inner,status='fit',training_ids=[r['candidate_id'] for r in inner_train],
                validation_ids=[r['candidate_id'] for r in valid],excluded_ids=inner_excluded))
        calibrator=fit_calibrator(records)
        model=FeasibilitySelectionPredictor(seed=0).fit(training)
        pool=target+failed;public=[screen._public(r) for r in pool]
        pred=model.predict(public,area_cap=CAP)
        rank_scores={r['candidate_id']:r['rank_score'] for r in SpeedupRanker(seed=0).fit(training).predict(public)}
        raw={r['candidate_id']:p['feasibility_score_mean'] for r,p in zip(pool,pred)}
        cal=dict(zip(raw,apply_calibrator(calibrator,list(raw.values()))))
        known=[r['candidate_id'] for r in target];labels=[feasibility_label(r,CAP) for r in target]
        for name,values in [('raw_factorized',raw),('calibrated_factorized',cal)]:
            metrics.append(dict(group=group,model=name,**probability_metrics(labels,[values[i] for i in known])))
        fold=dict(group=group,training_ids=[r['candidate_id'] for r in training],target_ids=[r['candidate_id'] for r in pool],
            excluded_ids=excluded,inner_splits=inner_splits,calibration_records=records,calibrator=calibrator,
            predictions=dict(raw_factorized=raw,calibrated_factorized=cal,pairwise=rank_scores))
        folds.append(fold)
        for context in sorted({r['benchmark'] for r in pool}):
            context_rows=[r for r in pool if r['benchmark']==context];byid={r['candidate_id']:r for r in context_rows}
            success={i:r for i,r in byid.items() if r.get('status','success')=='success'}
            failure={i:r for i,r in byid.items() if r.get('status')=='failed'}
            oracle=max([1.]+[r['speedup'] for r in success.values() if b._feasible(r,CAP,12.)])
            censored=any(r.get('reference_censored',True) for r in failure.values())
            for policy,order in orders([screen._public(r) for r in context_rows],raw,cal,rank_scores).items():
                name,_,seed=policy.partition(':')
                for budget in BUDGETS:
                    result=screen._evaluate_group(name,[byid[i] for i in order],success,failure,oracle,censored,
                        seed=int(seed or 0),budget=min(budget,len(order)))
                    runs.append(dict(result,group=group,context=context,requested_budget=budget,
                        effective_budget=min(budget,len(order))))
        c.seal(output/'folds.json',folds)
        print(f'{group}: {len(training)} training; {len(records)} inner OOF; {calibrator["kind"]}',flush=True)
    grouped=[]
    for group in groups:
        for policy in POLICIES:
            for budget in BUDGETS:
                points=[r for r in runs if r['group']==group and r['policy']==policy and r['requested_budget']==budget]
                grouped.append(dict(group=group,policy=policy,budget=budget,
                    reduction=statistics.mean(r['verified_cycle_reduction'] for r in points),
                    measurement_seconds=statistics.mean(r['measurement_seconds'] for r in points),
                    regret=(statistics.mean(r['cycle_reduction_regret'] for r in points)
                            if all(r['cycle_reduction_regret'] is not None for r in points) else None)))
    summary=[dict(policy=p,budget=B,mean_cycle_reduction=statistics.mean(r['reduction'] for r in grouped if r['policy']==p and r['budget']==B),
        mean_measurement_seconds=statistics.mean(r['measurement_seconds'] for r in grouped if r['policy']==p and r['budget']==B)) for p in POLICIES for B in BUDGETS]
    for item in summary:
        complete=[r['regret'] for r in grouped if r['policy']==item['policy'] and r['budget']==item['budget'] and r['regret'] is not None]
        item.update(complete_oracle_workloads=len(complete), mean_cycle_reduction_regret=statistics.mean(complete) if complete else None)
    paired=[]
    index={(r['group'],r['policy'],r['budget']):r for r in grouped}
    for base in ('raw_factorized','pairwise','merit','calibrated_latency'):
        for budget in BUDGETS:
            differences={g:index[g,'calibrated_factorized',budget]['reduction']-index[g,base,budget]['reduction'] for g in groups}
            paired.append(dict(baseline=base,budget=budget,**screen._paired_group_bootstrap(differences)))
    result=dict(scope=SETTINGS['scope'],promotion='not promoted',workloads=len(groups),successful_rows=len(rows),
        failed_attempts=len(failures),calibration_kinds=dict(Counter(f['calibrator']['kind'] for f in folds)),
        calibration_fallback_reasons=dict(Counter(f['calibrator']['reason'] for f in folds if f['calibrator']['kind']=='identity')),
        probability_metric_scope='Successful known outcomes only; failures are charged unknown outcomes',macro_probability_metrics={m:{k:statistics.mean(r[k] for r in metrics if r['model']==m) for k in ('brier','log_loss')} for m in ('raw_factorized','calibrated_factorized')},
        summary=summary,paired_workload_bootstrap=paired,elapsed_seconds=time.monotonic()-started)
    for n,v in [('result.json',result),('metrics.json',metrics),('runs.json',runs),('grouped.json',grouped)]:c.seal(output/n,v)
    c.seal(output/'manifest.json',{p.name:c.sha(p) for p in output.iterdir() if p.is_file()})
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--corpus',type=Path,default=ROOT/'results/2026-10-28-expanded-selection-corpus-r2');p.add_argument('--output',type=Path,default=ROOT/'reports/2026-10-28-grouped-feasibility-calibration-r1');a=p.parse_args();run(a.corpus,a.output)
