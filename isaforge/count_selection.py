"""One count-budget adaptive GP ablation: remove inverse duration, nothing else.

Uses the frozen hardware surrogate, public analytic speedup improvement, input
features, Gaussian feasibility factors, tie ordering and successful-paid update
rule. Initial predictions are supplied from a sealed existing package. This is
cooperative provider isolation; the caller owns unreleased target outcomes.
"""
from __future__ import annotations

import copy
import math
import random
import time

from . import budgeted_selection as b,codesign as c

POLICY='hybrid_gp_adapt_count'
SOURCES=('isaforge/count_selection.py',*b.SOURCES)


def count_score(row,estimate,incumbent,area_cap,clock_mhz):
    """Frozen hybrid_score with solely its final inverse-time factor removed."""
    gain=max(0.,row['latency_features']['estimated_speedup']-incumbent)
    area=b._probability_below(estimate['area_delta_lut4_mean'],estimate['area_delta_lut4_std'],area_cap)
    timing=b._probability_below(-estimate['routed_fmax_min_mhz_mean'],estimate['routed_fmax_min_mhz_std'],-clock_mhz)
    return gain*area*timing*estimate['device_fit_probability']


def search(public,training,provider,*,area_cap,clock_mhz=12.,seed,budget,predictions,
           surrogate_factory=b.HardwareSurrogate,on_acquire=None):
    public=b.public_rows(public)
    c.require(type(budget) is int and 0<budget<=len(public),'Invalid query budget')
    c.require(type(seed) is int and seed>=0,'Invalid seed')
    c.require(b._number(area_cap,'area cap')>=0,'Negative area cap')
    b._number(clock_mhz,'clock MHz',positive=True)
    training=copy.deepcopy(list(training))
    c.require(training and all(b.validate_outcome(row) for row in training),'Successful measured history required')
    c.require(not {row['candidate_id'] for row in training}&{row['candidate_id'] for row in public},'Target identity in history')
    initial=copy.deepcopy(predictions['hardware'])
    estimates={row['candidate_id']:row for row in initial}
    c.require(len(estimates)==len(initial)==len(public) and set(estimates)=={row['candidate_id'] for row in public},
              'Complete unique cached initial hardware predictions required')
    for row in initial:
        for key in ('area_delta_lut4','routed_fmax_min_mhz','log_measurement_seconds'):
            for suffix in ('mean','std'):b._number(row[key+'_'+suffix],key+' '+suffix)
            c.require(row[key+'_std']>=0,'Nonnegative cached uncertainty required')
        c.require(0<=b._number(row['device_fit_probability'],'fit probability')<=1,'Invalid fit probability')
    cached=b._number(predictions.get('inference_seconds',{}).get('hybrid_gp_adapt',0.),'Cached initial inference seconds')
    c.require(cached>=0,'Nonnegative cached inference required')
    c.require(callable(surrogate_factory) and (on_acquire is None or callable(on_acquire)),
              'Callable surrogate factory and optional acquisition observer required')
    ordered=copy.deepcopy(public);random.Random(seed).shuffle(ordered)
    observations,attempts,events,curve=[],[],[],[]
    update_seconds=0.;updates=0
    while len(attempts)<budget:
        feasible=[row for row in observations if b._feasible(row,area_cap,clock_mhz) and row['speedup']>1]
        incumbent=max([1.]+[row['speedup'] for row in feasible])
        estimates={row['candidate_id']:row for row in initial}
        if observations:
            began=time.monotonic()
            values=surrogate_factory().fit(training+observations).predict(ordered)
            update_seconds+=time.monotonic()-began;updates+=1
            estimates={row['candidate_id']:row for row in values}
        def score(row):
            return count_score(row,estimates[row['candidate_id']],incumbent,area_cap,clock_mhz),row['latency_features']['estimated_speedup']
        chosen=max(ordered,key=score)
        c.require(all(math.isfinite(value) for value in score(chosen)),'Finite acquisition required')
        events.append(dict(action='acquire',candidate_id=chosen['candidate_id'],policy=POLICY,
            charged_before_query=len(attempts),paid_target_ids_before_query=[row['candidate_id'] for row in observations],
            attempted_ids_before_query=list(attempts),score=score(chosen),hardware_predictions=list(estimates.values())))
        if on_acquire is not None:on_acquire(copy.deepcopy(events[-1]))
        # Charge before dispatch. Exceptions stop collection; there is no retry.
        attempts.append(chosen['candidate_id'])
        try:
            outcome=copy.deepcopy(provider(copy.deepcopy(chosen)))
            success=b.validate_outcome(outcome,chosen)
        except BaseException as error:
            events.append(dict(action='measure-exception',candidate_id=chosen['candidate_id'],charged=len(attempts),error=repr(error)))
            raise
        events.append(dict(action='measure-complete' if success else 'measure-failed',candidate_id=chosen['candidate_id'],
                           charged=len(attempts),observation=outcome))
        if success:observations.append(outcome)
        ordered=[row for row in ordered if row['candidate_id']!=chosen['candidate_id']]
        feasible=[row for row in observations if b._feasible(row,area_cap,clock_mhz) and row['speedup']>1]
        best=min(feasible,key=lambda row:(-row['speedup'],row['area_delta_lut4'],row['candidate_id'])) if feasible else None
        seconds=sum(event['observation']['measurement_seconds'] for event in events if 'observation' in event)
        curve.append(dict(budget=len(attempts),best_speedup=best['speedup'] if best else 1.,selected_id=best['candidate_id'] if best else None,
            attempted_ids=list(attempts),measured_ids=[row['candidate_id'] for row in observations],
            failed_attempts=len(attempts)-len(observations),target_measurement_seconds=seconds,
            inference_seconds=cached+update_seconds))
    return dict(policy=POLICY,curve=curve,events=events,cached_initial_predictions_reused=True,
        cached_initial_inference_seconds=cached,paid_update_host_seconds=update_seconds,paid_update_calls=updates)
