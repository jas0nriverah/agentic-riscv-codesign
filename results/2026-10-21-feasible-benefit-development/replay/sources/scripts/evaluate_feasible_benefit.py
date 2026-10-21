#!/usr/bin/env python3
"""One fixed feasible-benefit model evaluated on consumed historical cohorts."""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.feasible_benefit import (AREA_CAPS, CLOCK_MHZ, MODEL_SETTINGS,
    BUDGET_FEATURE, FeasibleBenefitPredictor, decision_utility, search)
from isaforge.speedup_corpus import family
from scripts.ablate_hardware_descriptors import load_label_free_case, load_scoring_report, TARGETS

DECLARATION = 'results/2026-10-21-feasible-benefit-development/protocol.md'
SOURCES = ('isaforge/feasible_benefit.py', 'scripts/evaluate_feasible_benefit.py',
           'scripts/ablate_hardware_descriptors.py', *b.SOURCES)
POLICY = 'feasible_benefit_xgb'


def verify_cohort(case):
    public, history, protocol = case['public'],case['history'],case['protocol']
    c.require(len(history) == protocol['historical_fit_rows'], 'Frozen cohort count differs')
    groups = {r['workload_group'] for r in history}
    c.require(protocol['target_workload'] not in groups, 'Target workload leaked into history')
    c.require(not {r['benchmark'] for r in history} & {r['benchmark'] for r in public}, 'Target context in history')
    c.require(not {family(r['formula']) for r in history} & {family(r['formula']) for r in public},
              'Related target formula family in history')
    c.require(len(groups) >= 2, 'Independent post-exclusion history groups required')
    return dict(fitting_candidates=len(history), cap_training_rows=3*len(history),
                effective_sample_weight=len(history), historical_groups=sorted(groups),
                historical_available_candidates=protocol['historical_available_rows'],
                excluded_related_ids=protocol['excluded_related_ids'],
                historical_available_attempt_seconds=protocol.get('cost_provenance',{}).get(
                    'total_candidate_wall_seconds',protocol['historical_candidate_wall_seconds']),
                historical_cost_provenance=protocol.get('cost_provenance',{}),
                baseline_setup_calibration_seconds=protocol['calibration_command_seconds'],
                contexts=protocol['contexts'])


def summarize(runs):
    rows = []
    for target in TARGETS:
        for cap in AREA_CAPS:
            for policy in (*b.POLICIES,POLICY):
                selected = [r for r in runs if r['target']==target and r['cap']==cap and r['policy']==policy]
                for budget in (1,2,3):
                    points = [r['curve'][budget-1] for r in selected]
                    rows.append(dict(target=target,cap=cap,policy=policy,budget=budget,dependent_seed_count=len(points),
                        mean_best_speedup=statistics.mean(p['best_speedup'] for p in points),
                        min_best_speedup=min(p['best_speedup'] for p in points),max_best_speedup=max(p['best_speedup'] for p in points),
                        mean_gap_to_best_verified=statistics.mean(p['gap_to_best_verified'] for p in points),
                        mean_target_measurement_seconds=statistics.mean(p['target_measurement_seconds'] for p in points),
                        mean_known_infeasible_attempts=statistics.mean(p['known_infeasible_attempts'] for p in points),
                        mean_unknown_attempts=statistics.mean(p['unknown_attempts'] for p in points)))
    return rows


def run(output):
    output = Path(output)
    c.require(not output.exists(), 'Fresh model-evaluation output directory required')
    cases = {name:load_label_free_case(ROOT/folder) for name,folder in TARGETS.items()}
    cohorts = {name:verify_cohort(case) for name,case in cases.items()}
    output.mkdir(parents=True)
    # Preserve exact authoring sources before fits. No target reports parsed yet.
    for source in SOURCES:
        path=output/'sources'/source;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((ROOT/source).read_bytes())
    protocol = dict(schema='isaforge-feasible-benefit-development-v1',scope='consumed-data development',
        declaration_sha256=c.sha(ROOT/DECLARATION),source_bindings={p:c.sha(ROOT/p) for p in SOURCES},
        input_bindings={name:{file:c.sha(ROOT/TARGETS[name]/file) for file in
            ('protocol.json','public.json','history.json','predictions.json','report.json')} for name in TARGETS},
        packages={name:importlib.metadata.version(name) for name in ('numpy','scipy','xgboost','scikit-learn')},
        seeds=list(range(5)),area_caps=list(AREA_CAPS),clock_mhz=CLOCK_MHZ,budgets=[1,2,3],
        primary_cap=64, policies=[*b.POLICIES,POLICY],model_settings=MODEL_SETTINGS,
        columns=[*b.STRUCTURAL_COLUMNS,BUDGET_FEATURE],cohorts=cohorts,
        utility='signed saved cycles / exact replacement count if actual feasible, else zero decision utility; failed utility unknown',
        acquisition='zero-shot mean feasible normalized savings * public replacements / public baseline cycles',
        uncertainty_calibrated=False,target_labels_read_before_freeze=0,new_native_jobs=0)
    c.seal(output/'protocol.json',protocol)
    predictions={}; fitting=[]
    for name,case in cases.items():
        predictions[name]=[]
        for seed in range(5):
            began=time.monotonic(); model=FeasibleBenefitPredictor(seed).fit(case['history'])
            values={str(cap):model.predict(case['public'],area_cap=cap) for cap in AREA_CAPS}
            elapsed=time.monotonic()-began
            predictions[name].append(dict(seed=seed,by_cap=values))
            fitting.append(dict(target=name,seed=seed,fit_and_all_caps_prediction_host_seconds=elapsed,
                historical_lut4_per_tree_operation=model.area_per_op,unique_measured_candidates=len(case['history'])))
    c.seal(output/'predictions.json',predictions)
    c.seal(output/'fitting.json',fitting)
    # Privileged scoring begins only after every target-label-free prediction is sealed.
    runs=[]; diagnostics=[]
    for name,case in cases.items():
        report,labels=load_scoring_report(ROOT/TARGETS[name],case)
        for cap in AREA_CAPS:
            oracle=max([1.0]+[r['speedup'] for r in labels.values() if b._feasible(r,cap,CLOCK_MHZ)])
            for seed in range(5):
                frozen=next(p for p in case['predictions'] if p['seed']==seed)
                utility=next(p for p in predictions[name] if p['seed']==seed)['by_cap'][str(cap)]
                known=[r for r in labels.values() if r.get('status','success')=='success']
                lookup={p['candidate_id']:p for p in utility}
                diagnostics.append(dict(target=name,cap=cap,seed=seed,known_utility_labels=len(known),
                    unknown_utility_labels=len(labels)-len(known),
                    normalized_feasible_utility_mae=statistics.mean(abs(
                        lookup[r['candidate_id']]['mean_saved_cycles_per_occurrence']-decision_utility(r,cap)) for r in known),
                    predicted_beneficial_but_known_infeasible=sum(
                        lookup[r['candidate_id']]['mean_fractional_cycle_savings']>0 and not b._feasible(r,cap,CLOCK_MHZ) for r in known)))
                for policy in (*b.POLICIES,POLICY):
                    provider=lambda row:copy.deepcopy(labels[row['candidate_id']])
                    if policy==POLICY:
                        result=search(case['public'],provider,area_cap=cap,seed=seed,budget=3,predictions=utility)
                    else:
                        result=b.search(case['public'],case['history'],provider,area_cap=cap,clock_mhz=CLOCK_MHZ,
                            seed=seed,budget=3,policy=policy,predictions=frozen)
                        old=next(r for r in report['runs'] if r['policy']==policy and r['seed']==seed and r['area_delta_lut4_cap']==cap)
                        c.require(b.stable(result['curve'])==b.stable([{k:p[k] for k in result['curve'][0]} for p in old['curve']]),
                                  'Frozen comparator curve changed: '+policy)
                    for point in result['curve']:
                        attempted=[labels[identity] for identity in point['attempted_ids']]
                        point.update(gap_to_best_verified=oracle-point['best_speedup'],
                            reference_kind='best verified; full pool infrastructure censored' if name=='ud' else 'measured fixed-pool oracle',
                            known_infeasible_attempts=sum(r.get('status','success')=='success' and not b._feasible(r,cap,CLOCK_MHZ) for r in attempted),
                            unknown_attempts=sum(r.get('status','success')!='success' for r in attempted))
                    runs.append(dict(target=name,cap=cap,seed=seed,policy=policy,**result))
    summary=summarize(runs)
    c.seal(output/'report.json',dict(protocol_sha256=c.sha(output/'protocol.json'),
        predictions_sha256=c.sha(output/'predictions.json'),runs=runs,summary=summary,diagnostics=diagnostics,
        trajectories=len(runs),endpoints=sum(len(r['curve']) for r in runs),new_native_jobs=0,
        limitations=['Consumed data; no prospective generalization.', 'Seed/cap/budget repetitions dependent.',
                    'Replicated caps are weighted decision contexts, not new measured labels.',
                    'Utility predictions are not measured speedup predictions or calibrated feasibility.',
                    'UD full pool is censored; regret gaps are lower bounds.',
                    'Historical mixed timer scopes do not measure complete search lifetime.']))
    lines=['# Feasible-benefit XGBoost development experiment','',
           'One fixed model; consumed data; no native measurements. All frozen comparators reproduce their archived curves exactly.','',
           '| Target | Policy | +64 mean speedup at budgets 1 / 2 / 3 | Mean target seconds at budgets 1 / 2 / 3 |',
           '|---|---|---|---|']
    for name in TARGETS:
        for policy in (*b.POLICIES,POLICY):
            points=[r for r in summary if r['target']==name and r['cap']==64 and r['policy']==policy]
            lines.append('| '+name+' | '+policy+' | '+' / '.join(f"{r['mean_best_speedup']:.9f}" for r in points)+' | '+
                         ' / '.join(f"{r['mean_target_measurement_seconds']:.3f}" for r in points)+' |')
    lines.extend(['','Complete events, all caps/seeds, unknown and known-infeasible attempts, regret and utility diagnostics are in report.json. Historical attempt/setup/context costs are in protocol.json; fit/predict host costs are separate in fitting.json. Target times are replayed historical costs, not live wall time.'])
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    c.seal(output/'manifest.json',{str(p.relative_to(output)):c.sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    return dict(trajectories=len(runs),endpoints=sum(len(r['curve']) for r in runs),new_native_jobs=0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    print(run(parser.parse_args().output))
