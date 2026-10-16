#!/usr/bin/env python3
"""Post-outcome V13 error diagnosis; no gated points, fits, native jobs or labels.

The single prospective route tag is the parent's fixed AST hypothesis. Its reach
is input-only; this script never substitutes predictions or scores that policy.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge.features import parse_formula
from isaforge import semantic_features_v7 as semantic

V13=ROOT/'results/2026-10-15-v13b-coverage-recovery'
SEEDS=(2026101421,2026101422,2026101423)
HIGH=frozenset(('mulh','mulhu','mulhsu'))
MASK=(1<<32)-1


def need(value,message):
    if not value:raise ValueError(message)
def sha(body):return hashlib.sha256(body).hexdigest()
def mean(values):return math.fsum(values)/len(values)
def symbols(node):
    if not node.children:return {node.value} if node.value in ('in0','in1') else set()
    return set().union(*(symbols(c) for c in node.children))


def correlations(node,path=()):
    result=[];match=semantic._correlation(node) # pure syntax helper, never its proof engine
    if match is not None:
        replacement,rule,atoms=match
        input_symbols=sorted(set().union(*(symbols(a) for a in atoms)))
        zero,one=semantic._known(replacement);possible=MASK^zero
        result.append({'path':list(path),'rule':rule,'formula':node.canonical(),'shared_atoms':[a.canonical() for a in atoms],
            'input_symbols':input_symbols,'input_containing_shared_atom':bool(input_symbols),
            'algebraic_replacement':replacement.canonical(),'replacement_possible_one_bits':possible.bit_count(),
            'replacement_unsigned_width':possible.bit_length(),'replacement_sign_bit_known_zero':bool(zero&(1<<31))})
    for i,c in enumerate(node.children):result.extend(correlations(c,path+(i,)))
    return result


def describe(formula):
    root=parse_formula(formula);nodes={};all_correlations=correlations(root)
    def visit(node,path=()):
        if node.value in HIGH and node.children:
            key=node.canonical()
            if key in nodes:nodes[key]['occurrence_paths'].append(list(path))
            else:
                operands=semantic._operand_rows(node)[:2] # independent known bits only, no SMT
                matches=[{'operand':j,**r} for j,c in enumerate(node.children) for r in correlations(c)]
                nodes[key]={'operation':node.value,'formula':key,'occurrence_paths':[list(path)],
                    'operand_input_symbols':[sorted(symbols(c)) for c in node.children],
                    'shared_input_symbols':sorted(symbols(node.children[0])&symbols(node.children[1])),
                    'independent_known_bit_operands':operands,'operand_correlations':matches}
        for i,c in enumerate(node.children):visit(c,path+(i,))
    visit(root)
    tag=any(c['input_containing_shared_atom'] for n in nodes.values() for c in n['operand_correlations'])
    return {'high_half_nodes':list(nodes.values()),'contains_high_half':bool(nodes),'contains_mulhsu':any(n['operation']=='mulhsu' for n in nodes.values()),
        'correlations_anywhere':all_correlations,'prospective_fixed_route_tag':tag}


def summarize(records):
    need(bool(records),'Nonempty diagnosis denominator required')
    deltas=[r['mean_absolute_error_change_lut4'] for r in records]
    return {'count':len(records),'prediction_changed_any_seed':sum(r['prediction_changed_any_seed'] for r in records),
        'prediction_changed_all_seeds':sum(r['prediction_changed_all_seeds'] for r in records),
        'mean_ae_hurt_rows':sum(d>0 for d in deltas),'mean_ae_helped_rows':sum(d<0 for d in deltas),'mean_ae_tied_rows':sum(d==0 for d in deltas),
        'ae_hurt_all_seeds':sum(all(x['absolute_error_change_lut4']>0 for x in r['per_seed'].values()) for r in records),
        'ae_helped_all_seeds':sum(all(x['absolute_error_change_lut4']<0 for x in r['per_seed'].values()) for r in records),
        'gross_ae_loss_lut4':math.fsum(max(0,d) for d in deltas),'gross_ae_gain_lut4':math.fsum(max(0,-d) for d in deltas),
        'net_ae_change_lut4':math.fsum(deltas),'pooled_mae_change_lut4':mean(deltas),
        'control_mae_lut4':mean([r['control_mean_absolute_error_lut4'] for r in records]),
        'augmented_mae_lut4':mean([r['augmented_mean_absolute_error_lut4'] for r in records])}


def run():
    evidence={}
    def body(path):
        path=Path(path).resolve();data=path.read_bytes();digest=sha(data);need(path not in evidence or evidence[path]==digest,'Evidence changed during diagnosis');evidence[path]=digest;return data
    def read(path):return json.loads(body(path))
    fitting=V13/'fitting';stage=fitting/'fit-attempt-0000';data=read(fitting/'fitting.json');rows=data['rows'];split=read(fitting/'split.json');ids=split['fold_ids']
    need(len(rows)==len(ids)==1761 and len({r['formula'] for r in rows})==1761,'Exact1761 input rows required')
    need(all(r['cohort']=='original1713' for r in rows[:1713]) and all(r['cohort']=='coverage48' for r in rows[1713:]),'Fixed1713/48 order required')
    done=read(stage/'completion.json');summary=read(stage/'summary.json')
    need(done['complete'] is True and done['fits_completed']==done['fits_attempted']==30 and done['summary_sha256']==sha(body(stage/'summary.json')),'Complete frozen30-fit study required')
    for name in ('preparation.json','recipe.json','fit-approval.json','independent-input-audit.json','independent-results-audit.json','independent-model-inference.json'):read(fitting/name)
    descriptors=[describe(r['formula']) for r in rows];points={}
    for seed in SEEDS:
        for view in ('control','augmented'):
            records=read(stage/'predictions'/f'{view}-seed-{seed}.json')
            need(len(records)==1761 and all(all(p[k]==v for k,v in r.items()) and p['fold']==ids[i] for i,(p,r) in enumerate(zip(records,rows))),'OOF identity/fold mismatch')
            points[view,seed]=[p['predicted_lut4'] for p in records]
    old=[]
    for i,r in enumerate(rows[:1713]):
        paired={}
        for seed in SEEDS:
            c,a=points['control',seed][i],points['augmented',seed][i];target=r['lut4_count']
            need(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in (c,a,target)),'Finite nonnegative outcomes required')
            paired[str(seed)]={'control_lut4':c,'augmented_lut4':a,'prediction_change_lut4':a-c,'control_absolute_error_lut4':abs(c-target),
                'augmented_absolute_error_lut4':abs(a-target),'absolute_error_change_lut4':abs(a-target)-abs(c-target)}
        old.append({'row_index':i,'formula':r['formula'],'formula_sha256':sha(r['formula'].encode()),'stratum':r['stratum'],'target_lut4':r['lut4_count'],'fold':ids[i],
            'original_zero_override':data['original_zero'][i],'per_seed':paired,
            'prediction_changed_any_seed':any(x['prediction_change_lut4']!=0 for x in paired.values()),'prediction_changed_all_seeds':all(x['prediction_change_lut4']!=0 for x in paired.values()),
            'control_mean_absolute_error_lut4':mean([x['control_absolute_error_lut4'] for x in paired.values()]),
            'augmented_mean_absolute_error_lut4':mean([x['augmented_absolute_error_lut4'] for x in paired.values()]),
            'mean_absolute_error_change_lut4':mean([x['absolute_error_change_lut4'] for x in paired.values()]),'structure':descriptors[i]})
    strata={s:summarize([r for r in old if r['stratum']==s]) for s in sorted({r['stratum'] for r in old})}
    primary=mean([v['pooled_mae_change_lut4'] for v in strata.values()])
    need(abs(primary-summary['primary_augmented_minus_control_original1713_macro_mae_lut4']['mean'])<1e-10,'Independent paired diagnosis disagrees with primary')
    folds=[]
    for fold in range(5):
        new_train=[r for i,r in enumerate(rows) if i>=1713 and ids[i]!=fold];new_val=[r for i,r in enumerate(rows) if i>=1713 and ids[i]==fold]
        for j in [x for x in range(1,31) if (x-1)%5==fold]:
            receipt=read(stage/'receipts'/f'{j:02d}-start.json');expected=[i for i in range(1761) if ids[i]!=fold and (receipt['view']=='augmented' or i<1713)]
            need(receipt['training_indices']==expected and receipt['validation_indices']==[i for i in range(1761) if ids[i]==fold],'Frozen training membership mismatch')
        folds.append({'fold':fold,'old_validation':summarize([r for r in old if r['fold']==fold]),'new_training_rows':len(new_train),'new_validation_rows':len(new_val),
            'new_training_family_counts':dict(Counter(r['family'] for r in new_train)),'new_validation_family_counts':dict(Counter(r['family'] for r in new_val)),
            'new_training_context_counts':dict(Counter(r['context'] for r in new_train)),'new_validation_context_counts':dict(Counter(r['context'] for r in new_val))})
    high=[r for r in old if r['structure']['contains_high_half']];nonhigh=[r for r in old if not r['structure']['contains_high_half']]
    node_rows=[n for r in high for n in r['structure']['high_half_nodes']]
    support={'old_high_product_formulas':len(high),'old_mulhsu_formulas':sum(r['structure']['contains_mulhsu'] for r in old),
        'old_high_half_operator_counts':dict(Counter(n['operation'] for n in node_rows)),
        'old_high_product_nodes_with_shared_operand_input':sum(bool(n['shared_input_symbols']) for n in node_rows),
        'old_high_product_nodes_with_operand_correlation':sum(bool(n['operand_correlations']) for n in node_rows),
        'old_operand_possible_one_bits_histogram':dict(sorted(Counter(str(o['possible_one_bits']) for n in node_rows for o in n['independent_known_bit_operands']).items())),
        'old_operand_interpreted_width_histogram':dict(sorted(Counter(str(o['interpreted_width']) for n in node_rows for o in n['independent_known_bit_operands']).items())),
        'old_high_product_rows':high}
    tag_counts={name:{'rows':len(indices),'fixed_tag_true':sum(descriptors[i]['prospective_fixed_route_tag'] for i in indices),
        'contains_high_half':sum(descriptors[i]['contains_high_half'] for i in indices)} for name,indices in [('original1713',range(1713)),('coverage48',range(1713,1761))]}
    for path in (Path(__file__),ROOT/'isaforge/features.py',ROOT/'isaforge/semantic_features_v7.py',ROOT/'isaforge/area_model_v6.py',ROOT/'scripts/develop_v13_coverage.py'):body(path)
    need(all(sha(p.read_bytes())==h for p,h in evidence.items()),'Evidence mutated during diagnosis')
    result={'schema':'isaforge-v13-collateral-regression-diagnosis-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Post-outcome consumed-development diagnosis of the single fixed V13 control/augmentation comparison. No new predictor or gated scores.',
        'original1713':summarize(old),'nine_stratum_macro_mae_change_lut4':primary,'by_stratum':strata,
        'old_high_half_descriptive':summarize(high),'old_non_high_half_descriptive':summarize(nonhigh),
        'top10_hurt':sorted(old,key=lambda r:(-r['mean_absolute_error_change_lut4'],r['formula_sha256']))[:10],
        'top10_helped':sorted(old,key=lambda r:(r['mean_absolute_error_change_lut4'],r['formula_sha256']))[:10],
        'high_product_support':support,'folds':folds,'all_original_row_changes':old,
        'single_prospective_route':{'definition':'AST contains mulh/mulhu/mulhsu with an operand subtree matching frozenV7 or_sub/sub_and and a shared atom containing in0/in1. No width/mask/label threshold or formula whitelist.',
            'input_only_reach':tag_counts,'gated_predictions_created':False,'gated_metrics_computed':False,
            'preservation_argument':'A later hard route that returns the exact incumbent outside this predicate preserves all its outputs there by construction. This is logic, not an empirical gated-model result.',
            'limitation':'Input-containing atoms can still be semantically constant through cancellation. Patterns and independent known bits are existing pure syntax analysis; no new local solver proof/normalization was executed. Generalization beyond covered shapes is unresolved.'},
        'interpretation':'Broad global refitting changes unrelated heldout predictions. Error decomposition and fold membership describe coexistence, not causal attribution to any one new family, split or feature. Saved trees were not needed; no leaf-level influence claim.',
        'new_fits':0,'native_jobs':0,'new_labels':0,'models_loaded':0,'gate_or_threshold_sweeps':0,
        'evidence':[{'path':p.relative_to(ROOT).as_posix(),'sha256':h} for p,h in sorted(evidence.items())]}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'results/2026-10-16-v14-specialist-development/diagnosis.json');a=p.parse_args();result=run()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('schema','original1713','nine_stratum_macro_mae_change_lut4','single_prospective_route','new_fits','native_jobs','new_labels','models_loaded')},indent=2))
