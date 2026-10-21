"""Replay one predeclared consumed-data hardware descriptor ablation."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import copy
import importlib.metadata
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

def load_label_free_case(folder):
    """Authenticate the frozen runtime and public artifacts without parsing outcomes."""
    folder = Path(folder).resolve()
    protocol = c.unseal(folder/'protocol.json')
    c.require(protocol['schema'] == 'isaforge-budgeted-selection-v1' and
              protocol['target_labels_read'] == 0, 'Expected frozen label-free protocol')
    for name, expected in protocol['source_bindings'].items():
        path = (ROOT/name).resolve()
        c.require(not Path(name).is_absolute() and path.is_relative_to(ROOT.resolve()), 'Source escapes repository')
        c.require(c.sha(path) == expected, 'Frozen model source changed: '+name)
    for name, expected in protocol['packages'].items():
        c.require(importlib.metadata.version(name) == expected, 'Frozen model dependency changed: '+name)
    c.require({'public.json','history.json','predictions.json'} <= protocol['artifacts'].keys(),
              'Missing frozen artifact bindings')
    for name, expected in protocol['artifacts'].items():
        path = (folder/name).resolve()
        c.require(not Path(name).is_absolute() and path.is_relative_to(folder), 'Artifact escapes input root')
        c.require(c.sha(path) == expected, 'Frozen artifact changed: '+name)
    result = {name:c.unseal(folder/(name+'.json')) for name in ('public','history','predictions')}
    b.public_rows(result['public'])
    c.require([r['candidate_id'] for r in result['history']] == protocol['historical_training_ids'],
              'Frozen training cohort differs')
    # Byte/sidecar checks do not parse report labels. Bind these bytes for scoring later.
    report_path = folder/'report.json'
    report_hash = c.sha(report_path)
    c.require(report_hash == Path(str(report_path)+'.sha256').read_text().strip(), 'Cached report changed')
    result.update(protocol=protocol, protocol_sha256=c.sha(folder/'protocol.json'), report_sha256=report_hash)
    return result


def load_scoring_report(folder, case):
    """Call only after predictions are sealed; authenticate all released outcomes."""
    folder = Path(folder)
    c.require(c.sha(folder/'protocol.json') == case['protocol_sha256'], 'Protocol changed after fitting')
    c.require(c.sha(folder/'report.json') == case['report_sha256'], 'Report changed after fitting')
    report = c.unseal(folder/'report.json')
    c.require(report['protocol_sha256'] == case['protocol_sha256'], 'Report/protocol binding differs')
    labels = {}
    for run in report['runs']:
        for event in run['events']:
            if 'observation' in event:
                row = event['observation']; identity = row['candidate_id']
                c.require(identity not in labels or labels[identity] == row, 'Conflicting recorded outcomes')
                labels[identity] = row
    public = case['public']
    c.require(set(labels) == {r['candidate_id'] for r in public}, 'Complete recorded attempted pool required')
    for row in public: b.validate_outcome(labels[row['candidate_id']], row)
    c.require(c.digest([labels[r['candidate_id']] for r in public]) == report['outcomes_sha256'],
              'Frozen outcome binding differs')
    return report, labels


def run(output):
    output=Path(output)
    c.require(not output.exists(),'Fresh output directory required')
    output.mkdir(parents=True)
    inputs = {}
    data={}
    for target,folder in TARGETS.items():
        data[target]=load_label_free_case(ROOT/folder)
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
        report, labels=load_scoring_report(ROOT/TARGETS[target],d)
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
                        if variant=='existing':
                            old=next(r for r in report['runs'] if r['policy']==policy and r['seed']==seed and r['area_delta_lut4_cap']==cap)
                            c.require(b.stable(result['curve'])==b.stable([{k:p[k] for k in result['curve'][0]} for p in old['curve']]), 'Existing search curve differs from archive')
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
