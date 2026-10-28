"""Bounded retrospective ordinary-workload versus strict-family sensitivity.

No prospective claim, tuning, model promotion, or native measurement dispatch.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import random
import math
import statistics
import time
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge.features import parse_formula
from isaforge.speedup_corpus import family
from isaforge.ranking import SpeedupRanker, PARAMETERS
from isaforge.feasibility_selection import FeasibilitySelectionPredictor, MODEL_SETTINGS
from scripts import evaluate_feasibility_model_families as screen
from scripts.export_expanded_selection_corpus import authenticate
from scripts.prepare_countnegative_v2_selector import history_contexts

POLICIES = ('pairwise', 'raw_factorized', 'merit', 'calibrated_latency', 'frequency', 'exact_cache_latency', 'random')
SPLITS = ('workload_only', 'workload_and_family')
BUDGETS = (1, 2, 3)
CODEGEN = ('isaforge/rtl.py', 'isaforge/core_experiment.py', 'isaforge/soc_experiment.py',
           'isaforge/core_routing.py', 'isaforge/codesign.py')
SOURCES = ('scripts/evaluate_workload_transfer.py', 'tests/test_workload_transfer.py',
           'docs/workload-transfer-sensitivity-contract-2026-10-28.md', 'scripts/prepare_countnegative_v2_selector.py',
           'scripts/export_expanded_selection_corpus.py', 'scripts/evaluate_feasibility_model_families.py',
           'isaforge/ranking.py', 'isaforge/feasibility_selection.py', 'isaforge/features.py',
           'isaforge/model.py', 'isaforge/budgeted_selection.py', 'isaforge/speedup_corpus.py')


def compatibility(context):
    """Unknown provenance is incompatible; source hashes describe historical builds."""
    try:
        provenance = context['baseline_provenance']
        values = {k: context[k] for k in ('hardware_inputs', 'compiler_flags',
                  'linker_input_sha256', 'memory_partition', 'clock_mhz')}
        values['compiler_sha256'] = provenance['compiler_sha256']
        values['codegen'] = {k: provenance['source_bindings'][k] for k in CODEGEN}
        if any(v is None or v == {} or v == [] or v == '' for v in values.values()):
            return None
        hashes = list(values['codegen'].values()) + list(values['hardware_inputs'].values()) + [values['compiler_sha256'], values['linker_input_sha256']]
        if any(not isinstance(v, str) or len(v) != 64 or any(ch not in '0123456789abcdef' for ch in v) for v in hashes):
            return None
        if not isinstance(values['compiler_flags'], list) or not all(isinstance(flag, str) for flag in values['compiler_flags']):
            return None
        if not isinstance(values['clock_mhz'], (int, float)) or not math.isfinite(values['clock_mhz']) or values['clock_mhz'] <= 0:
            return None
        return json.dumps(values, sort_keys=True, separators=(',', ':'))
    except (KeyError, TypeError, AttributeError):
        return None


def exact_key(row):
    return parse_formula(row['formula']).canonical()


def cache_predictions(training, public, contexts):
    """Conservative historical summaries, never target-label replacements or bounds."""
    predictions = []
    for target in public:
        target_context = compatibility(contexts.get(target['benchmark'], {}))
        exact = [r for r in training if exact_key(r) == exact_key(target)]
        compatible = [r for r in exact if target_context is not None and
                      compatibility(contexts.get(r['benchmark'], {})) == target_context]
        item = dict(candidate_id=target['candidate_id'], exact_formula=exact_key(target),
                    exact_training_ids=[r['candidate_id'] for r in exact],
                    compatible_training_ids=[r['candidate_id'] for r in compatible],
                    target_context_known=target_context is not None,
                    incompatible_exact_records=len(exact)-len(compatible), hit=bool(compatible))
        if compatible:
            item.update(historical_max_area=max(r['area_delta_lut4'] for r in compatible),
                historical_min_fmax=min(r['routed_fmax_min_mhz'] for r in compatible),
                historical_all_device_fit=all(r['device_fits'] for r in compatible))
        item['historically_infeasible'] = bool(compatible) and (
            item['historical_max_area'] > 64 or item['historical_min_fmax'] < 12 or
            not item['historical_all_device_fit'])
        predictions.append(item)
    return predictions


def split(rows, failures, group, kind):
    strict, target, failed, excluded = screen._split_with_failures(rows, failures, group)
    return (strict if kind == 'workload_and_family' else
            [r for r in rows if r['workload_group'] != group]), target, failed, excluded


def policy_orders(public, rank, factorized, cache):
    byid = {r['candidate_id']: r for r in public}
    latency = lambda i: -byid[i]['latency_features']['estimated_speedup']
    result = dict(pairwise=sorted(byid, key=lambda i: (-rank[i], i)),
        raw_factorized=sorted(byid, key=lambda i: (-factorized[i], latency(i), i)))
    for name, key in (('merit', 'saved'), ('frequency', 'runs')):
        result[name] = sorted(byid, key=lambda i: (-byid[i][key], i))
    result['calibrated_latency'] = sorted(byid, key=lambda i: (latency(i), i))
    cached = {r['candidate_id']: r for r in cache}
    result['exact_cache_latency'] = sorted(byid, key=lambda i: (
        cached[i]['historically_infeasible'], latency(i), i))
    for seed in range(5):
        ids = sorted(byid); random.Random(seed).shuffle(ids)
        result[f'random:{seed}'] = ids
    return result


def summarize(runs):
    grouped = []
    for kind in SPLITS:
        for group in sorted({r['workload_group'] for r in runs}):
            for policy in POLICIES:
                for budget in BUDGETS:
                    points = [r for r in runs if (r['split'], r['workload_group'], r['policy'], r['requested_budget']) == (kind, group, policy, budget)]
                    grouped.append(dict(split=kind, workload_group=group, policy=policy, budget=budget,
                        reduction=statistics.mean(r['verified_cycle_reduction'] for r in points),
                        regret=statistics.mean(r['cycle_reduction_regret'] for r in points) if all(r['cycle_reduction_regret'] is not None for r in points) else None,
                        measurement_seconds=statistics.mean(r['measurement_seconds'] for r in points)))
    macro=[]; paired=[]
    for kind in SPLITS:
        for policy in POLICIES:
            for budget in BUDGETS:
                points=[r for r in grouped if (r['split'],r['policy'],r['budget'])==(kind,policy,budget)]
                complete=[r for r in points if r['regret'] is not None]
                macro.append(dict(split=kind,policy=policy,budget=budget,workloads=len(points),complete_oracles=len(complete),
                    mean_cycle_reduction=statistics.mean(r['reduction'] for r in points),
                    mean_regret=statistics.mean(r['regret'] for r in complete) if complete else None,
                    mean_measurement_seconds=statistics.mean(r['measurement_seconds'] for r in points)))
                base={r['workload_group']:r for r in grouped if (r['split'],r['policy'],r['budget'])==(kind,'merit',budget)}
                paired.append(dict(split=kind,policy=policy,budget=budget,metric='cycle reduction advantage versus merit',
                    **screen._paired_group_bootstrap({r['workload_group']:r['reduction']-base[r['workload_group']]['reduction'] for r in points})))
    for contrast in paired:
        contrast['interpretation'] = 'Positive means higher verified cycle reduction than merit; workload is the bootstrap unit.'
    return grouped, macro, paired


def run(corpus_path, output):
    corpus_path, output = Path(corpus_path).resolve(), Path(output).resolve()
    c.require(output.is_relative_to(ROOT) and not output.exists(), 'Fresh repository-local output required')
    corpus, manifest = authenticate(corpus_path)
    c.require(corpus_path.name == '2026-10-28-expanded-selection-corpus-r2', 'Only frozen expanded r2 is allowed')
    rows, failures = corpus['rows'], corpus['failed_attempts']
    c.require(all(type(r.get('measurement_seconds')) in (int, float) and
                  math.isfinite(r['measurement_seconds']) and r['measurement_seconds'] >= 0
                  for r in rows + failures), 'Every attempt requires finite nonnegative measured cost')
    groups=sorted({r['workload_group'] for r in rows})
    c.require(len(groups)==17 and len(rows)==156 and len(failures)==4, 'Frozen cohort differs')
    contexts, context_bindings = history_contexts(corpus)
    output.mkdir(parents=True)
    protocol=dict(schema='isaforge-workload-transfer-sensitivity-v1', scope='exploratory consumed-data paired sensitivity; no promotion',
        corpus_sha256=c.sha(corpus_path/'corpus.json'),manifest_sha256=c.sha(corpus_path/'manifest.json'),
        source_bindings={n:c.sha(ROOT/n) for n in SOURCES},context_bindings=context_bindings,
        policies=POLICIES,splits=SPLITS,budgets=BUDGETS,model_seed=0,random_seeds=list(range(5)),
        packages={name:importlib.metadata.version(name) for name in ('numpy','scipy','xgboost','scikit-learn')},
        feasibility_parameters=MODEL_SETTINGS,pairwise_parameters=PARAMETERS,feasibility_model='unchanged 20-member FeasibilitySelectionPredictor',
        area_cap=64,clock_mhz=12,primary='Historical strict-family B3 remains primary; new results exploratory',
        cache_codegen_keys=CODEGEN,cache_context_rule=compatibility.__doc__,cache_rule=cache_predictions.__doc__,
        training_information='Identical success cohort available to both ML and cache; ML uses existing mixed contexts; cache conservative compatible subset',
        limitation='Split difference changes training size/composition and cannot isolate memorization',
        failure_handling='Unknown failures remain charged actual attempts; never fit or replace outcomes',
        historical_costs=corpus.get('historical_costs'),historical_attempt_seconds=corpus.get('total_candidate_attempt_wall_seconds'))
    c.seal(output/'protocol.json',protocol)  # Must precede every fit.
    folds=[];runs=[]
    for kind in SPLITS:
        for group in groups:
            training,target,failed,excluded=split(rows,failures,group,kind)
            pool=sorted(target+failed,key=lambda r:r['candidate_id']);public=[screen._public(r) for r in pool]
            cache=cache_predictions(training,public,contexts)
            if kind=='workload_and_family':
                c.require(all(not r['exact_training_ids'] for r in cache), 'Strict split exact-formula leak')
            times={}
            start=time.monotonic();ranker=SpeedupRanker(seed=0).fit(training);times['rank_fit_seconds']=time.monotonic()-start
            start=time.monotonic();model=FeasibilitySelectionPredictor(seed=0).fit(training);times['feasibility_fit_seconds']=time.monotonic()-start
            start=time.monotonic();rank={r['candidate_id']:r['rank_score'] for r in ranker.predict(public)};times['rank_predict_seconds']=time.monotonic()-start
            start=time.monotonic();pred=model.predict(public,area_cap=64);times['feasibility_predict_seconds']=time.monotonic()-start
            factorized={r['candidate_id']:r['decision_score'] for r in pred}
            snapshots=[]
            for benchmark in sorted({r['benchmark'] for r in pool}):
                members=[r for r in pool if r['benchmark']==benchmark];byid={r['candidate_id']:r for r in members}
                orders=policy_orders([screen._public(r) for r in members],rank,factorized,cache)
                snapshots.append(dict(benchmark=benchmark,public=[screen._public(r) for r in members],orders=orders))
                success={i:r for i,r in byid.items() if r.get('status','success')=='success'};failure={i:r for i,r in byid.items() if r.get('status')=='failed'}
                oracle=max([1.]+[r['speedup'] for r in success.values() if screen._feasible(r)])
                censored=any(r.get('reference_censored',True) for r in failure.values())
                for policy,ids in orders.items():
                    name,_,seed=policy.partition(':')
                    for budget in BUDGETS:
                        point=screen._evaluate_group(name,[byid[i] for i in ids],success,failure,oracle,censored,seed=int(seed or 0),budget=min(budget,len(ids)))
                        runs.append(dict(point,split=kind,workload_group=group,benchmark=benchmark,requested_budget=budget,effective_budget=min(budget,len(ids))))
            folds.append(dict(split=kind,workload_group=group,training_ids=[r['candidate_id'] for r in training],
                training_groups=sorted({r['workload_group'] for r in training}),training_families=sorted({family(r['formula']) for r in training}),
                target_families=sorted({family(r['formula']) for r in pool}),family_excluded_ids=excluded if kind=='workload_and_family' else [],
                available_training_seconds=sum(r['measurement_seconds'] for r in training),timing=times,
                rank_predictions=rank,feasibility_predictions=pred,cache=cache,cache_hit_rate=statistics.mean(r['hit'] for r in cache),public_order_snapshots=snapshots))
            c.seal(output/'folds.json',folds)
            print(f'{kind} {group}: {len(training)} training',flush=True)
    grouped,macro,paired=summarize(runs)
    result=dict(protocol_sha256=c.sha(output/'protocol.json'),macro=macro,paired_vs_merit=paired,
        interpretation='Exploratory consumed-data sensitivity; no superiority, prospective confirmation, or promotion')
    for name,data in [('runs.json',runs),('grouped.json',grouped),('result.json',result)]:c.seal(output/name,data)
    c.seal(output/'manifest.json',{p.name:c.sha(p) for p in output.iterdir() if p.is_file()})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,default=ROOT/'results/2026-10-28-expanded-selection-corpus-r2')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.corpus,a.output)
