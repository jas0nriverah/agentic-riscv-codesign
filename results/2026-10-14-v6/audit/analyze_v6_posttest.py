#!/usr/bin/env python3
"""Consumed V6 post-test decomposition. No fitting or frozen scoring changes."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def checked(e,root):
    p=(root/e['path']).resolve();assert sha(p)==e['sha256'];return p

def run(root,audit_path,output):
    audit=read(audit_path);assert audit['status']=='passed' and audit['stage']=='test'
    point=read(root/'point-freeze.json');start=read(root/'training-start.json');old=checked(point['source_v5_freeze'],root).parent
    oldfreeze=read(old/'freeze.json');entries={(old/e['path']).resolve():e['sha256'] for e in oldfreeze['files']}
    dataset=old/'development-data.json';assert sha(dataset)==entries[dataset.resolve()]
    split=read(old/'split.json');indices=start['fit_indices'];assert indices==split['fit_indices'] and len(indices)==1665
    data=read(dataset);fit=np.array([data[i]['lut4_count'] for i in indices],float);minimum,maximum=float(fit.min()),float(fit.max())
    models=audit['models'];names=list(models);rows=models[names[0]]['candidate_errors'];y=np.array([r['lut4_count'] for r in rows]);strata=np.array([r['stratum'] for r in rows]);stratum_names=sorted(set(strata));groups=read(root/'corpus/test/components.json')['component_by_formula']
    reference=np.array([r['predicted_lut4'] for r in models['dual_graph']['candidate_errors']]);base_error=np.abs(reference-y)
    above=y>maximum;lower_bound=np.maximum(y-maximum,0);summaries={};all_errors={};decomposition={}
    for name,cell in models.items():
        records=cell['candidate_errors'];assert [r['formula'] for r in records]==[r['formula'] for r in rows]
        assert [r['lut4_count'] for r in records]==y.tolist()
        p=np.array([r['predicted_lut4'] for r in records]);ae=np.abs(p-y);error=p-y;delta=ae-base_error
        order=np.argsort(-ae,kind='stable');total=ae.sum();fractions={}
        for label,k in [('largest_1',1),('largest_1_percent',math.ceil(.01*len(rows))),('largest_5_percent',math.ceil(.05*len(rows))),('largest_10_percent',math.ceil(.1*len(rows)))]:
            fractions[label]={'row_count':k,'absolute_error_sum_lut4':float(ae[order[:k]].sum()),'fraction_of_all_absolute_error':float(ae[order[:k]].sum()/total) if total else None}
        def cell_metrics(mask):
            return {'count':int(mask.sum()),'mae_lut4':float(ae[mask].mean()) if mask.any() else None,'signed_bias_lut4':float(error[mask].mean()) if mask.any() else None,
              'maximum_underprediction_lut4':float(np.maximum(-error[mask],0).max()) if mask.any() else None,'underprediction_count':int((error[mask]<0).sum()),
              'absolute_error_sum_lut4':float(ae[mask].sum()),'fraction_of_all_absolute_error':float(ae[mask].sum()/total) if total else None}
        summaries[name]={'macro_stratum_mae_lut4':cell['macro_stratum_mae_lut4'],'mae_minus_dual_graph':float(delta.mean()),
          'error_concentration':fractions,'targets_above_original_fit_maximum':cell_metrics(above),'targets_at_or_below_original_fit_maximum':cell_metrics(~above),
          'maximum_point_prediction_lut4':float(p.max()),'point_predictions_above_original_fit_maximum_count':int((p>maximum+1e-9).sum()),
          'above_fit_maximum_by_stratum':{s:cell_metrics(above&(strata==s)) for s in stratum_names}}
        decomposition[name]={s:{'mae_lut4':float(ae[strata==s].mean()),'mae_minus_dual_graph':float(delta[strata==s].mean()),
          'contribution_to_eight_stratum_macro_difference':float(delta[strata==s].mean()/8),'count':int((strata==s).sum())} for s in stratum_names}
        assert abs(sum(c['contribution_to_eight_stratum_macro_difference'] for c in decomposition[name].values())-summaries[name]['mae_minus_dual_graph'])<1e-10
        all_errors[name]=[{**records[i],'signed_error_lut4':float(error[i]),'component':groups[records[i]['formula']],
          'target_above_original_fit_maximum':bool(above[i]),'absolute_error_minus_dual_graph':float(delta[i])} for i in order]
        if name in ('mapping_v6','router_v6'):assert np.all(p<=maximum+1e-9)
    delta=np.abs(np.array([r['predicted_lut4'] for r in models['mapping_v6']['candidate_errors']])-y)-base_error
    primarycases=[{**r,'component':groups[r['formula']],'mapping_point':models['mapping_v6']['candidate_errors'][i]['predicted_lut4'],
      'dual_graph_point':float(reference[i]),'paired_absolute_error_difference_lut4':float(delta[i]),'target_above_original_fit_maximum':bool(above[i])} for i,r in enumerate(rows)]
    result={'schema':'isaforge-v6-post-test-diagnostic-v1','scope':'POST-TEST CONSUMED ANALYSIS; separate from frozen primary/scorer; no new fitting or outcome-based replacement',
      'analysis_source_sha256':sha(Path(__file__)),'independent_test_audit_sha256':sha(audit_path),'evaluation_sha256':sha(root/'evaluation.json'),
      'point_freeze_sha256':sha(root/'point-freeze.json'),'calibration_freeze_sha256':sha(root/'calibration-freeze.json'),
      'original_fit_reference':{'rows':1665,'dataset_sha256':sha(dataset),'fitting_minimum_lut4':minimum,'fitting_maximum_lut4':maximum,
         'test_above_maximum_count':int(above.sum()),'test_target_maximum_lut4':float(y.max()),'above_maximum_target_values':y[above].tolist(),
         'above_maximum_count_by_stratum':{s:int((above&(strata==s)).sum()) for s in stratum_names},
         'unavoidable_mae_lower_bound_for_predictions_bounded_by_fit_maximum':float(lower_bound.mean())},
      'models':summaries,'per_stratum_decomposition_vs_dual_graph':decomposition,'all_models_all_errors_sorted':all_errors,
      'all192_paired_primary_cases':primarycases,
      'limits':['These diagnoses are motivated by consumed fresh-test outcomes and do not form a new independent test or revise the frozen primary comparison.',
        'ExtraTrees outputs average fitted leaf targets and cannot exceed the fitting-target maximum; old controls differ in method and lineage, so this common cutoff is not every historical model training maximum.',
        'Post-test stratum/tail contrasts are descriptive; no added multiplicity-adjusted hypothesis or new interval is claimed.']}
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=run(a.root.resolve(),a.audit.resolve(),a.output);print(json.dumps({'fit_reference':r['original_fit_reference'],'summary':{n:{k:v for k,v in c.items() if k in ('macro_stratum_mae_lut4','mae_minus_dual_graph','targets_above_original_fit_maximum')} for n,c in r['models'].items()}},indent=2))
