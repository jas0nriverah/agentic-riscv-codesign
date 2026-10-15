#!/usr/bin/env python3
"""Pure V8 point/selection arithmetic engine; no file I/O or model fitting.

A separate parent-owned wrapper must validate freeze/artifact/measurement lineage
before calling evaluate. All test fixtures are synthetic. Program declarations
are mandatory so an empty/missing pool cannot silently alter family weights.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import math
import random
import statistics
import numpy as np
from isaforge.features import parse_formula

MODELS=('mapping_v6','legacy_original336','legacy_rewritten336','dual_graph','sog_tuned','masterrtl_fixed')
CAPS=(32,64,128)
BUDGETS=(1,3,5)
RANDOM_SEEDS=tuple(range(2026101501,2026101506))
STRATEGIES=('predicted_area_feasible_merit','merit','frequency','random')
PRIMARY=('legacy_rewritten336','mapping_v6')


def _integer(value,label,positive=False):
    if type(value) is not int or value<(1 if positive else 0):raise ValueError(label+' must be a nonnegative integer'+(' greater than zero' if positive else ''))
    return value

def _text(value,label):
    if not isinstance(value,str) or not value:raise ValueError(label+' must be a nonempty string')
    return value

def _point(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('Predicted LUT4 must be finite nonnegative')
    return float(value)


def error_metrics(actual,prediction):
    if not actual or len(actual)!=len(prediction):raise ValueError('Nonempty complete metric vectors required')
    y=[_integer(v,'Measured LUT4') for v in actual];p=[_point(v) for v in prediction]
    residual=[b-a for a,b in zip(y,p)];ae=[abs(e) for e in residual]
    positive=[(a,e) for a,e in zip(y,ae) if a>0];zero=[e for a,e in zip(y,ae) if a==0]
    return {'count':len(y),'mae_lut4':statistics.fmean(ae),'signed_bias_lut4':statistics.fmean(residual),
        'rmsle':math.sqrt(statistics.fmean((math.log1p(b)-math.log1p(a))**2 for a,b in zip(y,p))),
        'positive_target_count':len(positive),'positive_mape_percent':statistics.fmean(e/a for a,e in positive)*100 if positive else None,
        'zero_target_count':len(zero),'zero_mae_lut4':statistics.fmean(zero) if zero else None,
        'p95_absolute_error_lut4':float(np.quantile(ae,.95)),'p99_absolute_error_lut4':float(np.quantile(ae,.99)),
        'worst_absolute_error_lut4':max(ae),'maximum_underprediction_lut4':max(max(-e,0) for e in residual),
        'underprediction_count':sum(e<0 for e in residual),'overprediction_count':sum(e>0 for e in residual),'exact_prediction_count':sum(e==0 for e in residual),
        'caps':{str(cap):{'false_accept_count':sum(b<=cap<a for a,b in zip(y,p)),
            'false_reject_count':sum(a<=cap<b for a,b in zip(y,p)),
            'predicted_feasible_count':sum(b<=cap for b in p),'actually_feasible_count':sum(a<=cap for a in y),'count':len(y)} for cap in CAPS}}


@dataclass(frozen=True)
class PublicCandidate:
    candidate_id:str
    formula:str
    saved:int
    runs:int
    point:float


def acquisition_order(candidates,strategy,cap,seed):
    """No actual resource, oracle or correctness outcome is an input."""
    _integer(cap,'Cap');ordered=sorted(candidates,key=lambda r:(r.formula,r.candidate_id))
    if strategy=='random':random.Random(seed).shuffle(ordered);return ordered
    if strategy=='frequency':return sorted(ordered,key=lambda r:(-r.runs,r.formula,r.candidate_id))
    if strategy=='merit':return sorted(ordered,key=lambda r:(-r.saved,r.formula,r.candidate_id))
    if strategy=='predicted_area_feasible_merit':
        return sorted(ordered,key=lambda r:(0,-r.saved,r.formula,r.candidate_id) if r.point<=cap else (1,r.point-cap,-r.saved,r.formula,r.candidate_id))
    raise ValueError('Unknown fixed acquisition strategy')


def selection_case(candidates,measure,*,cap,budget,strategy,seed,trace_count):
    """One unit per distinct attempted candidate; only measured feasible wins."""
    _integer(cap,'Cap');_integer(budget,'Budget',positive=True);_integer(trace_count,'Trace count',positive=True)
    if len({r.candidate_id for r in candidates})!=len(candidates):raise ValueError('Candidate identities must be unique')
    attempts=[];feasible=[]
    for candidate in acquisition_order(candidates,strategy,cap,seed)[:budget]:
        actual=_integer(measure(candidate.formula),'Measured LUT4')
        attempts.append({'candidate_id':candidate.candidate_id,'formula':candidate.formula,'measured_lut4':actual,
            'actual_area_violation':actual>cap,'overlapSafeSaved':candidate.saved})
        if actual<=cap and candidate.saved>0:feasible.append((candidate,actual))
    selected=min(feasible,key=lambda item:(-item[0].saved,item[0].formula,item[0].candidate_id)) if feasible else None
    return {'strategy':strategy,'cap_lut4':cap,'budget':budget,'seed':seed,'candidate_measurements':len(attempts),'attempts':attempts,
        'attempted_actual_area_violations':sum(r['actual_area_violation'] for r in attempts),
        'selected_candidate_id':None if selected is None else selected[0].candidate_id,
        'selected_actual_lut4':None if selected is None else selected[1],
        'selected_overlapSafeSaved':0 if selected is None else selected[0].saved,'baseline_overlapSafeSaved':0}


def _inputs(rows,measurements,predictions,expected_programs):
    declared={}
    for program in expected_programs:
        name=_text(program['benchmark'],'Declared benchmark');family=_text(program['family'],'Family')
        if name in declared:raise ValueError('Duplicate declared program')
        if type(program['primary_family']) is not bool:raise ValueError('primary_family must be an actual bool')
        trace=_integer(program['traceTotalInstructions'],'Trace count',positive=True)
        declared[name]={'benchmark':name,'family':family,'primary_family':program['primary_family'],'traceTotalInstructions':trace}
    if not declared:raise ValueError('Declared program manifest required')
    family_roles=defaultdict(set)
    for p in declared.values():family_roles[p['family']].add(p['primary_family'])
    if any(len(v)>1 for v in family_roles.values()):raise ValueError('A family cannot mix primary and related-source roles')
    if not any(p['primary_family'] for p in declared.values()):raise ValueError('At least one primary family required')
    clean={};program_formulas=set();by_program=defaultdict(list)
    for row in rows:
        name=_text(row['benchmark'],'Benchmark');identity=_text(row['candidate_id'],'Candidate ID')
        if name not in declared:raise ValueError('Undeclared program row')
        if type(row['primary_family']) is not bool:raise ValueError('primary_family must be an actual bool')
        if row.get('program',name)!=name:raise ValueError('Program/benchmark aliases differ')
        for key in ('family','primary_family','traceTotalInstructions'):
            if row[key]!=declared[name][key] or (key=='traceTotalInstructions' and type(row[key]) is not int):raise ValueError('Program metadata or trace count mismatch')
        formula=parse_formula(row['formula']).canonical();key=(name,identity)
        if key in clean or (name,formula) in program_formulas:raise ValueError('Duplicate program/candidate or canonical formula row')
        saved=_integer(row['overlapSafeSaved'],'Saved instructions');runs=_integer(row['runs'],'Runs')
        if saved>declared[name]['traceTotalInstructions']:raise ValueError('Overlap-safe savings exceed trace instruction count')
        clean[key]={**declared[name],'candidate_id':identity,'formula':formula,'overlapSafeSaved':saved,'runs':runs}
        program_formulas.add((name,formula));by_program[name].append(key)
    if set(by_program)!=set(declared):raise ValueError('Missing or empty declared program pool; primary comparison incomplete')
    labels={}
    for row in measurements:
        formula=parse_formula(row['formula']).canonical()
        if formula in labels:raise ValueError('Each original canonical formula must have exactly one physical label')
        labels[formula]=_integer(row['lut4_count'],'Measured LUT4')
    if set(labels)!={r['formula'] for r in clean.values()}:raise ValueError('Measurements must cover complete original formula union exactly')
    if set(predictions)!=set(MODELS):raise ValueError('Exactly the six fixed predictor keys required')
    points={}
    for model,records in predictions.items():
        values={};formula_points={}
        for row in records:
            key=(row['benchmark'],row['candidate_id'])
            if key not in clean or key in values or parse_formula(row['formula']).canonical()!=clean[key]['formula']:raise ValueError('Prediction row identity/coverage differs')
            if row.get('upper_lut4') is not None or row.get('upper_margin_lut4') is not None:raise ValueError('Point-only pilot rejects inherited upper bounds')
            point=_point(row['predicted_lut4']);formula=clean[key]['formula']
            if formula in formula_points and formula_points[formula]!=point:raise ValueError('Same original canonical formula must have identical point across programs')
            formula_points[formula]=point;values[key]=point
        if set(values)!=set(clean):raise ValueError('Each predictor must cover every declared application row exactly')
        points[model]=values
    return declared,clean,by_program,labels,points


def evaluate(rows,measurements,predictions,*,expected_programs):
    """Compute the fixed pilot endpoints after separate lineage/label validation."""
    declared,clean,by_program,labels,points=_inputs(rows,measurements,predictions,expected_programs)
    by_family=defaultdict(list)
    for name,p in declared.items():by_family[p['family']].append(name)
    primary_families=sorted(f for f,names in by_family.items() if declared[names[0]]['primary_family'])
    scores={}
    for model in MODELS:
        program_scores={name:error_metrics([labels[clean[k]['formula']] for k in keys],[points[model][k] for k in keys]) for name,keys in by_program.items()}
        families={family:{'program_count':len(names),'programs':sorted(names),'primary_family':declared[names[0]]['primary_family'],
            'equal_program_mae_lut4':statistics.fmean(program_scores[n]['mae_lut4'] for n in names),
            'application_formula_rows':sum(len(by_program[n]) for n in names)} for family,names in by_family.items()}
        all_keys=sorted(clean);primary_keys=[k for k in all_keys if clean[k]['primary_family']]
        scores[model]={'primary_equal_family_mae_lut4':statistics.fmean(families[f]['equal_program_mae_lut4'] for f in primary_families),
            'by_program':program_scores,'by_family':families,
            'pooled_all_application_rows':error_metrics([labels[clean[k]['formula']] for k in all_keys],[points[model][k] for k in all_keys]),
            'pooled_primary_application_rows':error_metrics([labels[clean[k]['formula']] for k in primary_keys],[points[model][k] for k in primary_keys])}
    challenger,baseline=PRIMARY
    deltas={f:scores[challenger]['by_family'][f]['equal_program_mae_lut4']-scores[baseline]['by_family'][f]['equal_program_mae_lut4'] for f in primary_families}
    primary={'challenger':challenger,'baseline':baseline,'difference_lut4':statistics.fmean(deltas.values()),'paired_family_differences_lut4':deltas,
        'leave_one_family_out_difference_lut4':{f:statistics.fmean(v for g,v in deltas.items() if g!=f) if len(deltas)>1 else None for f in deltas},
        'family_count':len(primary_families),'scope':'Descriptive finite-family pilot; no population confidence interval or nominal coverage claim'}
    decisions=[]
    # Acquisition is completed using PUBLIC fields before oracle construction.
    for model in MODELS:
        for name in sorted(declared):
            metadata=declared[name];candidates=[PublicCandidate(clean[k]['candidate_id'],clean[k]['formula'],clean[k]['overlapSafeSaved'],clean[k]['runs'],points[model][k]) for k in by_program[name]]
            for cap in CAPS:
                for budget in BUDGETS:
                    for seed in RANDOM_SEEDS:
                        for strategy in STRATEGIES:
                            value=selection_case(candidates,labels.__getitem__,cap=cap,budget=budget,strategy=strategy,seed=seed,trace_count=metadata['traceTotalInstructions'])
                            decisions.append({**metadata,'model':model,**value})
    for result in decisions:
        candidates=[clean[k] for k in by_program[result['benchmark']]]
        feasible=[r for r in candidates if labels[r['formula']]<=result['cap_lut4'] and r['overlapSafeSaved']>0]
        oracle=min(feasible,key=lambda r:(-r['overlapSafeSaved'],r['formula'],r['candidate_id'])) if feasible else None
        saved=0 if oracle is None else oracle['overlapSafeSaved']
        result.update({'oracle_candidate_id':None if oracle is None else oracle['candidate_id'],'oracle_overlapSafeSaved':saved,
            'oracle_full_pool_label_count':len(candidates),'retained_oracle_savings_fraction':result['selected_overlapSafeSaved']/saved if saved else None,
            'normalized_regret_percent_trace_instructions':100*(saved-result['selected_overlapSafeSaved'])/result['traceTotalInstructions']})
    decision_summary={}
    for model in MODELS:
        for strategy in STRATEGIES:
            for cap in CAPS:
                for budget in BUDGETS:
                    key=f'{model}/{strategy}/cap{cap}/budget{budget}';selected=[r for r in decisions if r['model']==model and r['strategy']==strategy and r['cap_lut4']==cap and r['budget']==budget]
                    program_means={n:statistics.fmean(r['normalized_regret_percent_trace_instructions'] for r in selected if r['benchmark']==n) for n in declared}
                    family_means={f:statistics.fmean(program_means[n] for n in names) for f,names in by_family.items()}
                    conditional=[r['retained_oracle_savings_fraction'] for r in selected if r['primary_family'] and r['retained_oracle_savings_fraction'] is not None]
                    program_retention={}
                    for name in declared:
                        values=[r['retained_oracle_savings_fraction'] for r in selected if r['benchmark']==name and r['retained_oracle_savings_fraction'] is not None]
                        program_retention[name]=statistics.fmean(values) if values else None
                    family_retention={}
                    for family,names in by_family.items():
                        values=[program_retention[n] for n in names if program_retention[n] is not None]
                        family_retention[family]={'eligible_program_count':len(values),'program_count':len(names),
                            'conditional_equal_eligible_program_retention':statistics.fmean(values) if values else None}
                    eligible=[family_retention[f]['conditional_equal_eligible_program_retention'] for f in primary_families
                              if family_retention[f]['conditional_equal_eligible_program_retention'] is not None]
                    per_seed={}
                    for seed in RANDOM_SEEDS:
                        program_seed={r['benchmark']:r['normalized_regret_percent_trace_instructions'] for r in selected if r['seed']==seed}
                        per_seed[str(seed)]=statistics.fmean(statistics.fmean(program_seed[n] for n in by_family[f]) for f in primary_families)
                    decision_summary[key]={'model':model,'strategy':strategy,'cap_lut4':cap,'budget':budget,
                        'primary_equal_family_normalized_regret_percent':statistics.fmean(family_means[f] for f in primary_families),
                        'by_family_normalized_regret_percent':family_means,'by_program_normalized_regret_percent':program_means,
                        'primary_positive_oracle_program_seed_count':len(conditional),'primary_conditional_pooled_program_seed_retention':statistics.fmean(conditional) if conditional else None,
                        'per_seed_primary_equal_family_normalized_regret_percent':per_seed,
                        'by_family_conditional_retention':family_retention,'eligible_primary_family_count':len(eligible),
                        'primary_family_count':len(primary_families),
                        'primary_equal_eligible_family_conditional_retention':statistics.fmean(eligible) if eligible else None}
    return {'schema':'isaforge-v8-pure-application-evaluation-v1','point_only':True,'lineage_validated_by_engine':False,
        'lineage_scope':'Caller must independently validate frozen artifacts, source/cohort/predictions, target release and complete measurements before invoking this pure engine.',
        'primary':primary,'scores':scores,'selection':{'primary_cap_lut4':64,'primary_attempt_budget':1,'caps':list(CAPS),'budgets':list(BUDGETS),
            'seeds':list(RANDOM_SEEDS),'strategies':list(STRATEGIES),'details':decisions,'aggregates':decision_summary,
            'seed_scope':'All seeds retained; means describe ordering sensitivity on fixed programs, not independent population replicates.',
            'ordering_scope':'Feasible predictions first by saved,formula,id; remaining by ascending point-cap then saved,formula,id. Spend min(budget,poolsize) attempts; final actual feasible and oracle ties use saved,formula,id only.',
            'cost_scope':'One query per attempted candidate in each simulated program/policy case; physical union synthesis is deduplicated separately.',
            'zero_oracle_policy':'Baseline saved0; normalized regret0 if oracle0; retention undefined/null and conditional denominator explicit.',
            'benefit_scope':'Single-instruction overlap-safe saved retired instructions; never CPU cycles, frequency/speedup, or additive multi-instruction benefit.'},
        'counts':{'primary_families':len(primary_families),'all_families':len(by_family),'programs':len(declared),'application_formula_rows':len(clean),'unique_original_formula_labels':len(labels)},
        'limitations':['All complete known/familiar formulas retained; novelty subsets need a separately frozen input-only family-completeness guard.',
            'Measured feasibility is required for final selection; a point prediction is acquisition ordering only.']}
