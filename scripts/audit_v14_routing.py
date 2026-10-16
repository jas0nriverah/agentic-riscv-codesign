#!/usr/bin/env python3
"""Replay the single frozen V14 route; no alternate gate, fits or native tools.

Separate AST traversal comes from the retained V13 diagnosis. Frozen V7 syntax
and the reviewed standard-library metric engine are shared and disclosed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import audit_v13_comparison as arithmetic
import diagnose_v13_regressions as diagnosis


def run(root):
    root=Path(root).resolve();base=diagnosis.V13/'fitting';stage=base/'fit-attempt-0000';seen={}
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def read(path):
        path=Path(path).resolve();body=path.read_bytes();digest=hashlib.sha256(body).hexdigest()
        arithmetic.need(path not in seen or seen[path]==digest,'Evidence changed while replaying');seen[path]=digest
        return arithmetic.loads(body)
    data=read(base/'fitting.json');rows=data['rows'];ids=read(base/'split.json')['fold_ids']
    plan=read(root/'routing-plan.json');result=read(root/'routing-results.json');saved=read(root/'routing-predictions.json')
    arithmetic.need(plan['schema']=='isaforge-v14-exploratory-routing-plan-v1' and arithmetic.exact(plan['variants_scored'],1)
        and plan['threshold_search'] is False and plan['seeds']==list(arithmetic.SEEDS),'Exactly one fixed routing plan required')
    arithmetic.need(len(rows)==1761 and len(saved)==5283 and result['routing_plan_sha256']==sha(root/'routing-plan.json')
        and result['prediction_sha256']==sha(root/'routing-predictions.json'),'Full5283selectedpoints/plan digest required')
    descriptors=[diagnosis.describe(r['formula']) for r in rows];scores={};equal_control=equal_aug=0;differences=[]
    for sidx,seed in enumerate(arithmetic.SEEDS):
        control=arithmetic.verify_points(read(stage/'predictions'/f'control-seed-{seed}.json'),rows,data['original_zero'],ids)
        aug=arithmetic.verify_points(read(stage/'predictions'/f'augmented-seed-{seed}.json'),rows,data['original_zero'],ids);selected=[]
        for i,(row,description) in enumerate(zip(rows,descriptors)):
            flag=description['prospective_fixed_route_tag'];value=aug[i] if flag else control[i];selected.append(value)
            matches=[{'product':node['operation'],'product_path':path,'operand_index':c['operand'],'pattern_path':c['path'],'pattern':c['rule']}
                for node in description['high_half_nodes'] for path in node['occurrence_paths'] for c in node['operand_correlations'] if c['input_containing_shared_atom']]
            expected={'seed':seed,'formula':row['formula'],'cohort':row['cohort'],'fold':ids[i],'use_augmented':flag,'matches':matches,'predicted_lut4':value}
            arithmetic.need(arithmetic.exact(saved[sidx*1761+i],expected),'Selected point/route reason/row identity differs')
            equal_aug+=int(flag);equal_control+=int(not flag)
        scores[str(seed)]={name:arithmetic.cohort_scores(rows,points) for name,points in [('control',control),('augmented',aug),('routed',selected)]}
        differences.extend(arithmetic.arithmetic.compare(result['scores'][str(seed)],scores[str(seed)],f'/scores/{seed}'))
    deltas=[scores[str(s)]['routed']['original1713']['macro_stratum_mae_lut4']-scores[str(s)]['control']['original1713']['macro_stratum_mae_lut4'] for s in arithmetic.SEEDS]
    arithmetic.need(arithmetic.exact(result['primary_routed_minus_control'],{'per_seed':deltas,'mean':statistics.fmean(deltas)}),'Original primary differs')
    route_counts={cohort:sum(d['prospective_fixed_route_tag'] for row,d in zip(rows,descriptors) if row['cohort']==cohort) for cohort in ('original1713','coverage48')}
    arithmetic.need(arithmetic.exact(result['routed_counts'],route_counts),'Input-only route counts differ')
    for entry in plan['files']:
        path=(ROOT/entry['path']).resolve();arithmetic.need(path.is_relative_to(ROOT) and sha(path)==entry['sha256'],'Frozen source/input differs');seen[path]=entry['sha256']
    for path in (Path(__file__),ROOT/'scripts/diagnose_v13_regressions.py',root/'diagnosis.json',root/'routing-source-review.json'):
        seen[path]=sha(path)
    initial=root/'independent-routing-audit-initial.json'
    if initial.exists():seen[initial]=sha(initial)
    arithmetic.need(all(sha(p)==h for p,h in seen.items()),'Evidence mutated during replay')
    return {'schema':'isaforge-v14-independent-routing-audit-v2','status':'pass','complete':True,'audit_source_sha256':sha(__file__),
        'routing_plan_sha256':sha(root/'routing-plan.json'),'routing_results_sha256':sha(root/'routing-results.json'),
        'routing_predictions_sha256':sha(root/'routing-predictions.json'),'freeze_commit':result['freeze_commit'],'point_rows_verified':5283,
        'exact_control_fallback_points':equal_control,'exact_augmented_inside_gate_points':equal_aug,'input_route_counts':route_counts,
        'all3_original_primary_deltas':deltas,'all_scores_caps_tails_recomputed':True,'score_roundoff_differences':differences,
        'scope':'One frozen posthoc consumed-development gate only. Independent AST traversal/point selection via diagnosis; shared frozenV7 syntaxhelper and reviewedstdlibmetricengine. No alternate gate, fits, model/native inference, newlabels or promotion claim.',
        'initial_review_driver_failure_retained':initial.name if initial.exists() else None,'new_fits':0,'native_jobs':0,'new_labels':0,'alternate_gates_scored':0,
        'evidence':[{'path':p.relative_to(ROOT).as_posix(),'sha256':h} for p,h in sorted(seen.items())]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT/'results/2026-10-16-v14-specialist-development');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=run(args.root);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('evidence','score_roundoff_differences')},indent=2))
