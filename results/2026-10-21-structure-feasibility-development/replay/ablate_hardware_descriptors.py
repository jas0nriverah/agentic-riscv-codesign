"""Replay one predeclared consumed-data hardware descriptor ablation."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import copy
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge.ordered_hardware_descriptors import descriptors
TARGETS = {'edn':'results/2026-10-20-budget-campaign/selection/embench-edn',
           'ud':'results/2026-10-20-budget-campaign/selection/embench-ud',
           'sha256':'results/2026-10-21-sha256-selection/model'}
BASE_MATRIX = b.structural_matrix

def augmented_matrix(rows):
    return [base+descriptors(row['formula']) for base,row in zip(BASE_MATRIX(rows),rows)]

def run(output):
    output=Path(output)
    c.require(not output.exists(),'Fresh output directory required')
    output.mkdir(parents=True)
    inputs = {}
    data={}
    for target,folder in TARGETS.items():
        data[target]={name:c.read(ROOT/folder/(name+'.json')) for name in ('public','history','predictions','protocol')}
        for name in ('public','history','predictions','protocol','report'):
            path=ROOT/folder/(name+'.json'); inputs[str(path.relative_to(ROOT))]=c.sha(path)
    c.seal(output/'protocol.json',dict(scope='consumed-data development',new_native_jobs=0,
        declaration_sha256=c.sha(ROOT/'results/2026-10-21-structure-feasibility-development/protocol.md'),
        source_hashes={p:c.sha(ROOT/p) for p in ('scripts/ablate_hardware_descriptors.py','isaforge/ordered_hardware_descriptors.py',*b.SOURCES)},
        input_hashes=inputs,gp_settings=b.GP_SETTINGS,descriptor_slots=4,added_dimensions=45,
        target_cohorts={k:dict(rows=len(v['history']),postfilter_groups=sorted({r['workload_group'] for r in v['history']}),
                              historical_seconds=v['protocol']['historical_candidate_wall_seconds'],
                              cost_provenance=v['protocol']['cost_provenance']) for k,v in data.items()}))
    predictions={}; fit_times={}
    for target,d in data.items():
        for variant in ('existing','augmented'):
            with patch.object(b,'structural_matrix',augmented_matrix) if variant=='augmented' else nullcontext():
                began=time.monotonic(); values=b.HardwareSurrogate().fit(d['history']).predict(d['public'])
                fit_times[target+':'+variant]=time.monotonic()-began
            if variant=='existing':
                archived=d['predictions'][0]['hardware']
                c.require(b.stable(values)==b.stable(archived),'Existing GP must exactly reproduce archive')
            predictions[target+':'+variant]=values
    c.seal(output/'predictions.json',predictions)
    # Privileged labels are opened only after predictions have been sealed.
    runs=[]; diagnostics=[]
    for target,d in data.items():
        report=c.read(ROOT/TARGETS[target]/'report.json')
        labels={e['candidate_id']:e['observation'] for run in report['runs'] for e in run['events'] if 'observation' in e}
        for variant in ('existing','augmented'):
            pred=copy.deepcopy(d['predictions'][0]); pred['hardware']=predictions[target+':'+variant]
            pred['inference_seconds']={k:fit_times[target+':'+variant] for k in b.POLICIES}
            known=[(p,labels[p['candidate_id']]) for p in pred['hardware'] if labels[p['candidate_id']].get('status','success')=='success']
            for cap in (32,64,128):
                diagnostics.append(dict(target=target,variant=variant,cap=cap,known=len(known),unknown=len(labels)-len(known),
                    area_mae=statistics.mean(abs(p['area_delta_lut4_mean']-r['area_delta_lut4']) for p,r in known),
                    false_feasible_mean=sum(p['area_delta_lut4_mean']<=cap<r['area_delta_lut4'] for p,r in known),
                    area_brier=statistics.mean((b._probability_below(p['area_delta_lut4_mean'],p['area_delta_lut4_std'],cap)-float(r['area_delta_lut4']<=cap))**2 for p,r in known)))
                for policy in ('hybrid_gp_zero_shot','hybrid_gp_adapt','calibrated_latency','latency_cost_heuristic'):
                    if variant=='augmented' and not policy.startswith('hybrid'): continue
                    for seed in range(5):
                        with patch.object(b,'structural_matrix',augmented_matrix) if variant=='augmented' else nullcontext():
                            result=b.search(d['public'],d['history'],lambda row:labels[row['candidate_id']],area_cap=cap,
                                clock_mhz=12,policy=policy,seed=seed,budget=3,predictions=pred)
                        oracle=max([1.0]+[r['speedup'] for r in labels.values() if b._feasible(r,cap,12)])
                        for point in result['curve']:
                            point['gap_to_best_verified']=oracle-point['best_speedup']
                        runs.append(dict(target=target,variant=variant,cap=cap,policy=policy,seed=seed,**result))
    c.seal(output/'report.json',dict(runs=runs,diagnostics=diagnostics,new_native_jobs=0,
        limitations=['All six workloads consumed; no generalization claim.','UD reference censored; gaps are lower bounds.',
                    'Mixed timer scopes; inference and historical costs separate.','Uncalibrated GP probabilities.']))
    lines=['# Fixed descriptor development ablation','', 'Consumed development data; no native jobs. Existing GP predictions reproduce archived bytes exactly.', '',
           '| Target | Variant/policy | +64 speedup at budgets 1 / 2 / 3 | Target seconds at budgets 1 / 2 / 3 |','|---|---|---|---|']
    for r in runs:
        if r['cap']==64 and r['seed']==0:
            lines.append('| '+r['target']+' | '+r['variant']+'/'+r['policy']+' | '+ ' / '.join(f"{p['best_speedup']:.9f}" for p in r['curve'])+' | '+' / '.join(f"{p['target_measurement_seconds']:.3f}" for p in r['curve'])+' |')
    lines.extend(['','Full caps, seeds, attempt identities, predictions and paid update events are retained in report.json. Heuristic wins and negative outcomes are retained.','',
                  'These are exact historical cohorts, not new six-fold cross-validation. EDN/UD use 15 fitting rows, SHA256 21; workload/family exclusions remain unchanged. Historical/setup costs are in protocol.json. UD includes an infrastructure-censored attempt, never assigned hardware infeasibility.'])
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    return runs
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);run(parser.parse_args().output)
