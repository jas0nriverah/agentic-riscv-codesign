"""Reproducible model diagnosis and calibrated latency baseline on consumed pools.

No hyperparameter search, no new XGBoost variant, and no generalization claim.
The freeze step reads public candidate features, baseline discovery, and an
independent instruction calibration only. Analysis then opens measured outcomes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import importlib.metadata
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c, speedup_corpus as corpus
from isaforge.assembly_lowering import read_program
from isaforge.features import FEATURE_COLUMNS
from isaforge.latency_features import candidate_features
from isaforge.model import SpeedupPredictor, feature_matrix
from isaforge.ranking import SpeedupRanker
from isaforge.selection_pilot import pair_accuracy
from isaforge.selection_pilot import public_rows
from scripts.calibrate_picorv32_latency import audit as audit_calibration

SOURCES = ('scripts/analyze_speedup_model.py', 'isaforge/latency_features.py',
           'isaforge/model.py', 'isaforge/features.py', 'isaforge/ranking.py',
           'isaforge/speedup_corpus.py', 'isaforge/selection_pilot.py',
           'isaforge/assembly_lowering.py', 'isaforge/codesign.py',
           'scripts/calibrate_picorv32_latency.py', 'hardware/latency_sim.cpp',
           'src/tracing.py', 'src/candidates.py', 'src/verify_candidate_fusions.py')


def authenticated_calibration(root):
    root=Path(root)
    raw=audit_calibration(root)
    c.require(raw==c.unseal(root/'report.json'), 'Calibration report differs from raw evidence')
    plan=c.read(root/'plan.json')
    for name,expected in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==expected, 'Calibration source changed: '+name)
    return raw,plan


def freeze(pilot, calibration_root, workload_roots, output):
    output=Path(output); pilot=Path(pilot); calibration_root=Path(calibration_root)
    c.require(not output.exists(), 'Use a fresh analysis directory')
    calibration,calibration_plan=authenticated_calibration(calibration_root)
    c.require(calibration['context_id']==calibration_plan['context_id'], 'Calibration identity mismatch')
    public=c.unseal(pilot/'public.json')
    predictions, evidence, baseline_inputs = [], {}, []
    for root in map(Path,workload_roots):
        plan=c.unseal(root/'plan.json'); discovery=c.unseal(root/'discovery/discovery.json')
        bare_plan=copy.deepcopy(plan); identity=bare_plan.pop('context_id')
        c.require(c.digest(bare_plan)==identity,'Baseline plan digest mismatch')
        c.require(plan['context_id']==discovery['context_id'], 'Baseline context mismatch')
        for name,expected in plan['source_bindings'].items():
            c.require(c.sha(c.ROOT/name)==expected,'Baseline source changed: '+name)
        for name in ('picorv32.v','soc_top.v','pcpi_single.v','soc_link.ld'):
            c.require(c.sha(root/'inputs'/name)==plan['inputs'][name]==calibration_plan['inputs'][name],
                      'Latency calibration hardware mismatch: '+name)
        image=root/discovery['baseline_image']
        disassembly=image.parent/'disassembly.txt'
        rel=str(disassembly.relative_to(root/'discovery'))
        c.require(c.sha(disassembly)==discovery['artifacts'][rel], 'Baseline disassembly changed')
        program=read_program(disassembly.read_text())
        matching=[r for r in public if r['benchmark'].endswith(':'+plan['context_id'])]
        c.require(len(matching)==len(discovery['pool']), 'Public pool mismatch')
        for row in matching:
            candidate=next(r for r in discovery['pool'] if r['formula']==row['formula'])
            c.require(all(candidate['features'][k]==row[k] for k in FEATURE_COLUMNS), 'Feature mismatch')
            baseline=discovery['baseline_performance']
            features=candidate_features(candidate,program,baseline['cycles'],baseline['instructions'],calibration)
            predictions.append({**row,'latency_features':features})
            pcs={int(pc,16) for o in candidate['occurrences'] for pc in o['pcs']}
            baseline_inputs.append(dict(candidate_id=row['candidate_id'],
                                        occurrences=candidate['occurrences'],
                                        program={str(pc):program[pc] for pc in sorted(pcs)},
                                        baseline_cycles=baseline['cycles'],baseline_instructions=baseline['instructions']))
        for name,path in (('plan.json',root/'plan.json'),('discovery.json',root/'discovery/discovery.json'),
                          ('disassembly.txt',disassembly)):
            evidence['baseline-evidence/'+plan['context_id']+'/'+name]=path.read_bytes()
    c.require({r['candidate_id'] for r in predictions}=={r['candidate_id'] for r in public}, 'Incomplete prediction pool')
    output.mkdir(parents=True)
    for name,data in evidence.items():
        path=output/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    c.seal(output/'public-predictions.json',predictions)
    c.seal(output/'baseline-inputs.json',baseline_inputs)
    c.seal(output/'calibration.json',calibration)
    protocol=dict(scope='Consumed-data diagnostic; calibrated heuristic, not an improved learned model or an untouched test.',
                  source_bindings={p:c.sha(c.ROOT/p) for p in SOURCES},
                  baseline_bindings={name:c.sha(output/name) for name in evidence},
                  packages={p:importlib.metadata.version(p) for p in ('numpy','xgboost','scikit-learn')},
                  pilot_public_sha256=c.sha(pilot/'public.json'), calibration_id=calibration['context_id'],
                  pilot_artifacts={name:c.sha(pilot/name) for name in ('protocol.json','corpus.json','report.json')},
                  calibration_sha256=c.sha(output/'calibration.json'),
                  predictions_sha256=c.sha(output/'public-predictions.json'),
                  baseline_inputs_sha256=c.sha(output/'baseline-inputs.json'),
                  seeds=[0,1,2,3,4], budgets=[1,2,3,4,5,6],
                  hypothesis='Missing execution exposure and operand-dependent shift costs explain ranking collapse; calibrate a strong baseline before considering residual learning.',
                  target_labels_used_by_latency_predictor=0, trained_model_variants_added=0,
                  calibration_cost=calibration['native_command_seconds'], calibration_native_commands=calibration['native_commands'],
                  limitations=['Feature choice is informed by already consumed development results.',
                               'All twelve candidates are positive and feasible; no constraint-learning or slowdown evidence.',
                               'Top-six merit shortlists and only two programs limit every conclusion.',
                               'Operation latencies assume unchanged surrounding instruction costs; final whole-program measurement remains mandatory.',
                               'Latency merit does not predict area or routed timing, or compose instruction sets.',
                               'Historical timings are replayed; these are not fresh end-to-end policy wall times.'])
    c.seal(output/'protocol.json',protocol)
    return protocol


def support(training, public):
    """Descriptive training-range checks, never calibrated OOD probabilities."""
    ranges={k:(min(r[k] for r in training),max(r[k] for r in training)) for k in FEATURE_COLUMNS}
    return [dict(candidate_id=r['candidate_id'],
                 outside_training_ranges=[k for k,(lo,hi) in ranges.items() if not lo<=r[k]<=hi],
                 changed_training_constants=[k for k,(lo,hi) in ranges.items() if lo==hi and r[k]!=lo]) for r in public]


def latency_search(public, provider, area_cap, budget, seed):
    keys={'candidate_id','benchmark','formula',*FEATURE_COLUMNS,'latency_features'}
    public=[{k:copy.deepcopy(v) for k,v in row.items() if k in keys} for row in public]
    tools=c.LiveSelectionTools(public,provider,budget,area_cap,seed)
    ordered=copy.deepcopy(public); random.Random(seed).shuffle(ordered)
    ordered.sort(key=lambda r:-r['latency_features']['estimated_speedup'])
    curve=[]
    for row in ordered[:budget]:
        tools.measure(row['candidate_id']); best=tools.choose_final()
        curve.append(dict(budget=tools.measurements_used, best_speedup=best['speedup'] if best else 1.0,
                          selected_id=best['candidate_id'] if best else None,
                          measured_ids=tools.measured_candidate_ids,
                          target_measurement_seconds=sum(r['measurement_seconds'] for r in tools.observations.values())))
    return curve


def stable(value):
    if isinstance(value,dict): return {k:stable(v) for k,v in value.items() if k!='analysis_seconds'}
    if isinstance(value,list): return [stable(v) for v in value]
    return value


def analyze(root,pilot,verify=False):
    began=time.monotonic(); root=Path(root); pilot=Path(pilot)
    protocol=c.unseal(root/'protocol.json')
    for p,h in protocol['source_bindings'].items(): c.require(c.sha(c.ROOT/p)==h,'Analysis source changed: '+p)
    for p,v in protocol['packages'].items(): c.require(importlib.metadata.version(p)==v,'Analysis dependency changed')
    c.require(c.sha(root/'public-predictions.json')==protocol['predictions_sha256'],'Predictions changed')
    c.require(c.sha(root/'baseline-inputs.json')==protocol['baseline_inputs_sha256'],'Baseline projection changed')
    c.require(c.sha(root/'calibration.json')==protocol['calibration_sha256'],'Calibration changed')
    for name,expected in protocol['baseline_bindings'].items():
        c.require(c.sha(root/name)==expected,'Baseline evidence changed: '+name)
    for name,expected in protocol['pilot_artifacts'].items():
        c.require(c.sha(pilot/name)==expected,'Pilot artifact changed: '+name)
    c.require(c.sha(pilot/'public.json')==protocol['pilot_public_sha256'],'Pilot public features changed')
    c.require(verify or not (root/'report.json').exists(),'Preserve prior report')
    public=c.unseal(root/'public-predictions.json'); calibration=c.unseal(root/'calibration.json')
    mapping={r['candidate_id']:r for r in public}
    for row in c.unseal(root/'baseline-inputs.json'):
        predicted=candidate_features(row,{int(k):v for k,v in row['program'].items()},
                                     row['baseline_cycles'],row['baseline_instructions'],calibration)
        c.require(predicted==mapping[row['candidate_id']]['latency_features'],'Latency prediction replay differs')
    # Target outcomes are opened only after the public prediction replay.
    rows=c.unseal(pilot/'corpus.json')['rows']; corpus.validate(rows)
    pilot_protocol=c.unseal(pilot/'protocol.json')
    c.require(c.digest(rows)==pilot_protocol['corpus_sha256'],'Pilot corpus digest mismatch')
    c.require(public_rows(rows)==c.unseal(pilot/'public.json'),'Pilot public features mismatch')
    previous=c.unseal(pilot/'report.json')
    c.require({r['candidate_id'] for r in rows}==set(mapping),'Measured/public identity mismatch')
    constants={k:rows[0][k] for k in FEATURE_COLUMNS if len({r[k] for r in rows})==1}
    identical_columns=defaultdict(list)
    for k in FEATURE_COLUMNS:
        if k not in constants: identical_columns[tuple(r[k] for r in rows)].append(k)
    duplicate_vectors=defaultdict(list)
    for row,vector in zip(rows,feature_matrix(rows)): duplicate_vectors[tuple(vector)].append(row['candidate_id'])
    folds=[]; calibration_queries=[]
    for group in sorted({r['workload_group'] for r in rows}):
        training,target,excluded=corpus.split(rows,group)
        candidates=[mapping[r['candidate_id']] for r in target]
        actual=[r['speedup'] for r in target]
        diag=[]
        for seed in protocol['seeds']:
            reg=SpeedupPredictor(seed=seed).fit(training); rank=SpeedupRanker(seed=seed).fit(training)
            predictions=reg.predict(candidates); ranks=rank.predict(candidates)
            counts=Counter()
            for model in reg._models:
                counts.update({FEATURE_COLUMNS[int(k[1:])]:int(v) for k,v in model.get_booster().get_score(importance_type='weight').items()})
            tied_groups=defaultdict(list)
            for r,p in zip(target,predictions): tied_groups[p['mean']].append(r['name'])
            diag.append(dict(seed=seed,regression_split_counts=dict(sorted(counts.items())),
                             regression_unique_predictions=len(tied_groups),
                             tied_prediction_groups=[v for v in tied_groups.values() if len(v)>1],
                             regression_mae=statistics.mean(abs(y-p['mean']) for y,p in zip(actual,predictions)),
                             regression_pair_accuracy=pair_accuracy(actual,[p['mean'] for p in predictions]),
                             ranking_pair_accuracy=pair_accuracy(actual,[p['rank_score'] for p in ranks]),
                             ensemble_interval_coverage=statistics.mean(p['lower']<=y<=p['upper'] for y,p in zip(actual,predictions)),
                             mean_interval_width=statistics.mean(p['upper']-p['lower'] for p in predictions)))
        label_range=min(r['speedup'] for r in training),max(r['speedup'] for r in training)
        comparison=[]
        for row in target:
            features=mapping[row['candidate_id']]['latency_features']
            measured_savings=row['baseline_cycles']-row['candidate_cycles']
            comparison.append(dict(name=row['name'],candidate_id=row['candidate_id'],formula=row['formula'],
                                   runs=row['runs'], measured_saved_cycles=measured_savings,
                                   measured_saved_cycles_per_execution=measured_savings/row['runs'],
                                   measured_speedup=row['speedup'],**features))
        labels={r['candidate_id']:r for r in target}
        cap=target[0]['area_cap']; oracle=max([1.0]+[r['speedup'] for r in target if r['area']<=cap and r['timing_feasible']])
        for seed in protocol['seeds']:
            curve=latency_search(candidates,lambda row:copy.deepcopy(labels[row['candidate_id']]),cap,max(protocol['budgets']),seed)
            for point in curve: point['regret']=oracle-point['best_speedup']
            calibration_queries.append(dict(held_out_group=group,policy='calibrated_latency',seed=seed,curve=curve))
        folds.append(dict(held_out_group=group,training_rows=len(training),
                          training_workloads=len({r['workload_group'] for r in training}),excluded_related_ids=excluded,
                          training_label_range=label_range,
                          target_labels_outside_training_range=sum(not label_range[0]<=r['speedup']<=label_range[1] for r in target),
                          expected_unique_rows_per_bootstrap=len(training)*(1-(1-1/len(training))**len(training)),
                          probability_omitting_any_particular_training_row=(1-1/len(training))**len(training),
                          support=support(training,candidates),diagnostics=diag,comparison=comparison,
                          latency_mae=statistics.mean(abs(r['measured_speedup']-r['estimated_speedup']) for r in comparison),
                          latency_pair_accuracy=pair_accuracy(actual,[r['estimated_speedup'] for r in comparison]),
                          oracle_speedup=oracle))
    summary=copy.deepcopy(previous['summary'])
    for group in sorted({r['workload_group'] for r in rows}):
        for budget in protocol['budgets']:
            points=[p for r in calibration_queries if r['held_out_group']==group for p in r['curve'] if p['budget']==budget]
            summary.append(dict(held_out_group=group,budget=budget,policy='calibrated_latency',
                                mean_best_speedup=statistics.mean(p['best_speedup'] for p in points),
                                mean_regret=statistics.mean(p['regret'] for p in points),oracle_hits=sum(p['regret']==0 for p in points),
                                mean_target_measurement_seconds=statistics.mean(p['target_measurement_seconds'] for p in points)))
    report=dict(scope=protocol['scope'], corpus_rows=len(rows),workload_groups=len(folds),
                feature_count=len(FEATURE_COLUMNS),constant_features=constants,
                identical_varying_columns=[v for v in identical_columns.values() if len(v)>1],
                duplicate_feature_vectors=[v for v in duplicate_vectors.values() if len(v)>1],
                positive_labels=sum(r['speedup']>1 for r in rows),negative_labels=sum(r['speedup']<1 for r in rows),
                infeasible_labels=sum(r['area']>r['area_cap'] or not r['timing_feasible'] for r in rows),
                folds=folds,latency_runs=calibration_queries,summary=summary,
                original_pilot_outcomes=sum(len(r['curve']) for r in previous['runs']),
                new_latency_policy_outcomes=sum(len(r['curve']) for r in calibration_queries),
                calibration=calibration,workload_generalization_established=False,
                learned_model_improvement_established=False,trained_model_variants_added=0,
                limitations=protocol['limitations'],analysis_seconds=time.monotonic()-began)
    if verify: c.require(stable(report)==stable(c.unseal(root/'report.json')),'Analysis replay differs')
    else: c.seal(root/'report.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=('freeze','analyze','verify'))
    p.add_argument('--root',type=Path,required=True); p.add_argument('--pilot',type=Path,required=True)
    p.add_argument('--calibration',type=Path); p.add_argument('--workload-root',type=Path,action='append',default=[])
    args=p.parse_args()
    if args.command=='freeze':
        c.require(args.calibration and args.workload_root,'Calibration and baseline workload roots required')
        result=freeze(args.pilot,args.calibration,args.workload_root,args.root)
        print({'scope':result['scope'],'target_labels_used':0})
    else:
        result=analyze(args.root,args.pilot,args.command=='verify')
        print({'rows':result['corpus_rows'],'constant_features':len(result['constant_features']),
               'latency_mae':{f['held_out_group']:f['latency_mae'] for f in result['folds']},
               'new_latency_policy_outcomes':result['new_latency_policy_outcomes'],
               'learned_model_improvement_established':False})


if __name__=='__main__': main()
