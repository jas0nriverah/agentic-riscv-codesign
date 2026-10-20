"""Refit the preregistered fixed models on authenticated historical labels only.

No target candidate outcomes are loaded or used for fitting. This verifier is
separate from frozen code, never rewrites predictions, and ignores only recorded
fit/inference timers. It launches no native hardware tools.
"""
from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c
from isaforge import prospective_selection as selection
from isaforge.model import SpeedupPredictor
from isaforge.ranking import SpeedupRanker
from isaforge.speedup_corpus import family
from isaforge.workload_audit import import_automatic
from scripts.analyze_speedup_model import authenticated_calibration

DEFAULT_HISTORY=(c.ROOT/'generated/automatic-aha-mont64-2026-10-19',
                 c.ROOT/'generated/automatic-crc32-2026-10-20')


def training_rows(history,features,public,protocol):
    """Reconstruct the exact historical split; never use target outcomes."""
    c.require(c.digest(history)==protocol['input_digests']['history'], 'Historical corpus changed')
    c.require(c.digest(features)==protocol['input_digests']['history_features'], 'Historical feature corpus changed')
    mapping={r['candidate_id']:r for r in features}
    c.require(len(mapping)==len(features), 'Duplicate historical feature identity')
    families={family(r['formula']) for r in public}
    target_benchmarks={r['benchmark'] for r in public}
    fit=[]; excluded=[]
    for row in history:
        c.require(row['workload_group']!=protocol['target_workload'] and row['benchmark'] not in target_benchmarks,
                  'Target workload/context in historical training')
        if family(row['formula']) in families:
            excluded.append(row['candidate_id']); continue
        extra=mapping[row['candidate_id']]
        c.require(all(row[k]==extra[k] for k in ('benchmark','formula',*selection.FEATURE_COLUMNS)),
                  'Historical feature identity differs')
        fit.append({**row,'latency_features':extra['latency_features']})
    c.require(excluded==protocol['excluded_related_ids'], 'Family exclusions changed')
    c.require(len(history)==protocol['historical_available_rows'] and len(fit)==protocol['historical_fit_rows'],
              'Historical fitting counts changed')
    c.require(sorted({r['workload_group'] for r in fit})==protocol['fit_workload_groups'], 'Fitting workload groups changed')
    c.require(sum(r['measurement_seconds'] for r in history)==protocol['historical_candidate_wall_seconds'], 'Historical label cost changed')
    return fit


def verify_predictions(training,public,frozen,seeds):
    c.require([r['seed'] for r in frozen]==seeds, 'Frozen prediction seeds changed')
    counts={name:0 for name in ('regression','ranking','execution')}
    for record in frozen:
        seed=record['seed']
        regressor=SpeedupPredictor(seed=seed).fit(training)
        actual=dict(regression=regressor.predict(public),
                    ranking=SpeedupRanker(seed=seed).fit(training).predict(public),
                    execution=selection.execution_predictions(training,public,seed,regressor))
        c.require(set(record)=={'seed','regression','ranking','execution','inference_seconds'}, 'Unknown frozen prediction fields')
        c.require(set(record['inference_seconds'])=={'regression_zero_shot','ranking_zero_shot','execution_regression_zero_shot'}, 'Unexpected timer fields')
        for name,values in actual.items():
            c.require(values==record[name], 'Exact fixed prediction replay differs: '+name+' seed '+str(seed))
            counts[name]+=len(values)
    return counts


def verify(snapshot, history_roots=DEFAULT_HISTORY,
           analysis_snapshot=c.ROOT/'results/2026-10-20-model-analysis'):
    snapshot=Path(snapshot); analysis_snapshot=Path(analysis_snapshot)
    protocol=c.unseal(snapshot/'protocol.json')
    c.require(protocol['target_labels_read']==0, 'Protocol did not declare label-free freezing')
    for name,digest in protocol['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Frozen source changed: '+name)
    for name,version in protocol['packages'].items():
        c.require(importlib.metadata.version(name)==version, 'Frozen dependency changed: '+name)
    for name,digest in protocol['artifacts'].items():
        c.require(c.sha(snapshot/name)==digest, 'Frozen artifact changed: '+name)
    public=selection.public_rows(c.unseal(snapshot/'public.json'))
    frozen=c.unseal(snapshot/'predictions.json')
    c.require(len(public)==protocol['target_candidates'], 'Frozen target pool count changed')
    target_context=protocol['contexts'][public[0]['benchmark']]
    provenance=target_context['baseline_provenance']
    # Portable preregistrations include these immutable baseline metadata copies.
    # Live freeze directories may omit them; raw target audit belongs to the
    # collection replay wrapper and is never needed for historical fitting.
    archives={'target-plan.json':'plan.json','target-discovery.json':'discovery/discovery.json',
              'target-baseline.json':'measurements/baseline/measurement.json'}
    if any((snapshot/name).exists() for name in archives):
        for archived,original in archives.items():
            c.require((snapshot/archived).exists() and c.sha(snapshot/archived)==provenance['artifacts'][original],
                      'Frozen target baseline archive changed: '+archived)
        target_plan=c.read(snapshot/'target-plan.json')
        c.require(target_plan['compiler_flags']==target_context['compiler_flags'] and
                  target_plan['context_id']==target_context['context_id'] and
                  target_plan['inputs']['soc_link.ld']==target_context['linker_input_sha256'] and
                  target_plan['memory_partition']==target_context['memory_partition'], 'Target compilation/memory context changed')
    c.require(c.sha(analysis_snapshot/'protocol.json')==provenance['analysis_protocol_sha256'],
              'Historical analysis protocol changed')
    analysis=c.unseal(analysis_snapshot/'protocol.json')
    for name,digest in analysis['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Historical analysis source changed: '+name)
    for name,digest in analysis['baseline_bindings'].items():
        c.require(c.sha(analysis_snapshot/name)==digest, 'Historical baseline evidence changed: '+name)
    for name,key in (('public-predictions.json','predictions_sha256'),
                     ('calibration.json','calibration_sha256'),('baseline-inputs.json','baseline_inputs_sha256')):
        c.require(c.sha(analysis_snapshot/name)==analysis[key], 'Historical analysis artifact changed: '+name)
    calibration,calibration_plan=authenticated_calibration(c.ROOT/'results/2026-10-20-latency-calibration')
    c.require(calibration['context_id']==analysis['calibration_id'], 'Calibration identity changed')
    c.require(c.unseal(analysis_snapshot/'calibration.json')==calibration, 'Historical calibration projection changed')
    c.require(calibration['native_command_seconds']==protocol['calibration_command_seconds'], 'Calibration cost changed')
    history=[]
    for root in history_roots:
        root=Path(root).resolve(); imported=import_automatic(root); history.extend(imported['rows'])
        benchmark=imported['rows'][0]['benchmark']; context=protocol['contexts'][benchmark]
        for name,digest in context['baseline_provenance']['artifacts'].items():
            c.require(c.sha(root/name)==digest, 'Historical context artifact changed: '+name)
        plan=c.unseal(root/'plan.json')
        c.require(plan['compiler_flags']==context['compiler_flags'] and plan['context_id']==context['context_id'], 'Historical compiler context changed')
        for name,digest in context['hardware_inputs'].items():
            c.require(c.sha(root/'inputs'/name)==digest==calibration_plan['inputs'][name], 'Historical calibration hardware changed')
    features=c.unseal(analysis_snapshot/'public-predictions.json')
    training=training_rows(history,features,public,protocol)
    c.require(selection.support(training,public)==protocol['support'], 'Feature support changed')
    c.require(selection.support(training,public,True)==protocol['execution_support'], 'Execution feature support changed')
    counts=verify_predictions(training,public,frozen,protocol['seeds'])
    return dict(protocol_sha256=c.sha(snapshot/'protocol.json'), predictions_sha256=c.sha(snapshot/'predictions.json'),
        historical_available_rows=len(history),historical_fit_rows=len(training),target_candidates=len(public),
        target_labels_used_for_fit=0,seeds=protocol['seeds'],exact_prediction_rows=counts,
        new_model_variants=0,new_native_jobs=0,ignored_fields=['inference_seconds'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--history-root',type=Path,action='append')
    parser.add_argument('--analysis-snapshot',type=Path,default=c.ROOT/'results/2026-10-20-model-analysis')
    args=parser.parse_args(argv)
    print(verify(args.snapshot,args.history_root or DEFAULT_HISTORY,args.analysis_snapshot))


if __name__=='__main__': main()
