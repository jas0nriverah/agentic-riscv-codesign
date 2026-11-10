#!/usr/bin/env python3
"""One fixed coverage fit, retained development gates, then frozen fresh points.

Never launches synthesis. Historical panels are consumed development checks.
Fresh labels are read only by score-fresh, after a sealed model and points.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
import numpy as np
from isaforge import area_model_v6 as v6
from isaforge.features import parse_formula
import predict as base_inference

SCHEMA = 'isaforge-targeted-coverage-v1'
CAPS = (32, 64, 128)
NAMES = ('base', 'augmented217', 'scoped_augmented217')
PANELS = {'research-baselines':192, 'application-transfer':327,
          'arithmetic-stress':32, 'selection-validation':40}
MAX_FITS, MAX_SECONDS = 3, 120
ROUTE = {'schema':'original-ast-input-only-v1',
         'variable_shift':'Any sll/srl/sra node whose second operand subtree contains in0 or in1.',
         'mixed_arithmetic':'At least one add/addi/sub and at least one xor/xori anywhere, with no mul/mulh/mulhu/mulhsu anywhere.',
         'operator':'variable_shift OR mixed_arithmetic', 'otherwise':'base',
         'normalization':False, 'label_or_prediction_inputs':False}


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def need(value, message):
    if not value: raise ValueError(message)
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
def walk(node):
    yield node
    for child in node.children: yield from walk(child)
def route(formula):
    nodes = list(walk(parse_formula(formula))); ops = {n.value for n in nodes}
    variable = any(n.value in ('sll','srl','sra') and
                   any(c.value in ('in0','in1') for c in walk(n.children[1])) for n in nodes)
    mixed = bool(ops & {'add','addi','sub'}) and bool(ops & {'xor','xori'}) and not bool(ops & v6.MULTIPLY)
    return {'source_model':'augmented217' if variable or mixed else 'base',
            'coverage_classes':[n for n, yes in [('variable-shift',variable),('mixed-arithmetic-xor',mixed)] if yes]}
def source_hashes():
    return {str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__), ROOT/'scripts/predict.py',
            ROOT/'tests/test_train_targeted_coverage.py', *sorted((ROOT/'isaforge').glob('*.py'))]}
def relative(path): return str(Path(path).resolve().relative_to(ROOT))
def authenticate(output):
    protocol = read(output/'protocol.json')
    need(protocol['schema']==SCHEMA and protocol['route']==ROUTE, 'Protocol/schema/route differs')
    need(protocol['sources_sha256']==source_hashes(), 'Bound source differs')
    for name, digest in protocol['inputs_sha256'].items():
        need(sha(ROOT/name)==digest, 'Frozen input differs: '+name)
    return protocol
def feature_matrix(rows, payload):
    return base_inference.matrix(rows, payload)


def prepare(output, training, fresh):
    need(not output.exists(), 'Fresh output required')
    need(not (training/'labels.json').exists() and not (fresh/'labels.json').exists(), 'Freeze protocol before any new labels')
    train_rows, fresh_rows = read(training/'candidates.json'), read(fresh/'candidates.json')
    need(len(train_rows)==64 and len(fresh_rows)==40, 'Predeclared64 training and40 test rows required')
    need(not ({r['formula'] for r in train_rows} & {r['formula'] for r in fresh_rows}), 'Train/test formula overlap')
    for folder in (training,fresh):
        need(read(folder/'novelty.json')['status']=='pass', 'Input-only novelty screen must pass')
    paths = [ROOT/'results/feature-comparison'/n for n in ('inputs.npz','columns.json','rows.json')]
    paths += [ROOT/'models/base'/n for n in ('model.joblib','model.json')]
    for panel in PANELS:
        paths += [ROOT/'results'/panel/'features.json']
        paths += ([ROOT/'results'/panel/'candidates.json', ROOT/'results'/panel/'labels.json'] if panel=='selection-validation'
                  else [ROOT/'results'/panel/'observations.json'])
    for folder in (training,fresh):
        paths += [folder/n for n in ('candidates.json','novelty.json')]
    paths += [training/'plan.json', fresh/'plan.json']
    paths += sorted(training.glob('pre-native-*.json'))
    protocol = {'schema':SCHEMA,'created_at_utc':now(),'training':relative(training),'fresh':relative(fresh),
        'original_training_count':1665,'new_training_count':64,'fresh_test_count':40,
        'configuration':v6.FIXED_PARAMETERS,'feature_columns':list(v6.columns()),
        'selected_columns':list(v6.mapping_columns()),'zero_override':'original_gate_count equals0 -> prediction0',
        'route':ROUTE,'primary_candidate':'augmented217','secondary_candidate':'scoped_augmented217',
        'development_panels':PANELS,'motivating_panel':'selection-validation',
        'development_rule':'MAE and positive-target MAPE strictly lower on consumed40; maximum underprediction and each false_accept/false_reject count at every cap32/64/128 no worse than base separately on EACH retained panel. Other retained-panel accuracy is descriptive.',
        'fresh_rule':'MAE and positive-target MAPE strictly lower; maximum underprediction and each false_accept/false_reject count at every cap32/64/128 no worse than base on complete40.',
        'eligibility_rule':'Each named policy assessed separately; both its development and fresh gates must pass. No posthoc routing or gate changes.',
        'planned_fits':1,'maximum_fits':MAX_FITS,'maximum_wall_seconds':MAX_SECONDS,'workers':1,'native_threads':1,
        'native_jobs':0,'consumed40_training_rows':0,'selected128_used':False,
        'missing_rule':'Every declared row retained; any missing/failed feature/label blocks complete-cohort eligibility. No replacements or outcome-dependent retries.',
        'chronology':'Protocol and both cohorts before new labels; training labels; one fit; model and all fresh points before any fresh labels; independent fresh gate.',
        'scope':'Experimental isolated iCE40 LUT4 point estimates. No calibrated safety, full CPU, timing, routing, power or energy guarantee.',
        'sources_sha256':source_hashes(),'inputs_sha256':{relative(p):sha(p) for p in paths}}
    write(output/'protocol.json',protocol)
    return {'protocol_sha256':sha(output/'protocol.json'),'fits':0}


def model_metrics(values, targets):
    p, y = np.asarray(values,dtype=float), np.asarray(targets,dtype=float)
    need(p.shape==y.shape and p.ndim==1 and len(y)>0 and np.isfinite(p).all() and np.isfinite(y).all()
         and (p>=0).all() and (y>=0).all(), 'Complete finite nonnegative aligned points/targets required')
    error=np.abs(p-y); positive=y>0
    return {'count':len(y),'mae_lut4':float(error.mean()),
        'positive_mape_percent':float((error[positive]/y[positive]).mean()*100) if positive.any() else None,
        'positive_count':int(positive.sum()),'zero_count':int((~positive).sum()),
        'maximum_underprediction_lut4':float(max(0,(y-p).max())),
        'caps':{str(cap):{'false_accept':int(((p<=cap)&(y>cap)).sum()),
            'false_reject':int(((p>cap)&(y<=cap)).sum()),'actual_accept':int((y<=cap).sum()),
            'predicted_accept':int((p<=cap).sum())} for cap in CAPS}}
def compare(base, candidate):
    return {'mae_strictly_improved':candidate['mae_lut4']<base['mae_lut4'],
        'positive_mape_strictly_improved':candidate['positive_mape_percent'] is not None and base['positive_mape_percent'] is not None and candidate['positive_mape_percent']<base['positive_mape_percent'],
        'maximum_underprediction_no_worse':candidate['maximum_underprediction_lut4']<=base['maximum_underprediction_lut4'],
        'all_cap_directions_no_worse':all(candidate['caps'][str(cap)][kind]<=base['caps'][str(cap)][kind]
                                       for cap in CAPS for kind in ('false_accept','false_reject'))}
def development_metrics(panels):
    metrics={panel:{name:model_metrics(p['models'][name],p['actual_lut4']) for name in NAMES}
             for panel,p in panels.items()}
    gates={}
    for name in NAMES[1:]:
        checks={panel:compare(m['base'],m[name]) for panel,m in metrics.items()}
        accuracy=all(checks['selection-validation'][key] for key in ('mae_strictly_improved','positive_mape_strictly_improved'))
        safety=all(c['maximum_underprediction_no_worse'] and c['all_cap_directions_no_worse'] for c in checks.values())
        gates[name]={'panels':checks,'motivating_accuracy_improved':accuracy,'every_panel_budget_and_tail_no_worse':safety,
                     'development_gate_passed':accuracy and safety}
    return {'panels':metrics,'gates':gates,'fresh_test':False,'scope':'Consumed retrospective development regression checks; no independent test claim.'}


def points(rows, x, candidate, base):
    b=np.asarray([r['predicted_lut4'] for r in base.predict_features(rows,x)])
    a=np.asarray([r['predicted_lut4'] for r in candidate.predict_features(rows,x)])
    routes=[route(r['formula']) for r in rows]
    s=np.where([r['source_model']=='augmented217' for r in routes],a,b)
    return {'base':b.tolist(),'augmented217':a.tolist(),'scoped_augmented217':s.tolist()}, routes
def retained_panel(name):
    folder=ROOT/'results'/name
    if name=='selection-validation':
        rows, labels=read(folder/'candidates.json'),read(folder/'labels.json')
        y=labels_for(rows,labels)
    else:
        saved=read(folder/'observations.json')['rows']
        rows=[{'candidate_id':r['id'],'formula':r['formula']} for r in saved]
        y=[r['measured_lut4'] for r in saved]
    # Older feature caches retain id rather than candidate_id.
    payload=read(folder/'features.json')
    need([r['formula'] for r in payload['records']]==[r['formula'] for r in rows], 'Retained feature order differs')
    x=feature_matrix([{'formula':r['formula']} for r in rows],payload)
    need(len(rows)==PANELS[name], 'Retained panel count differs')
    return rows,x,y
def labels_for(rows,labels):
    need(len(rows)==len(labels) and all(l.get('status')=='complete' for l in labels), 'Complete successful labels required')
    for row,label in zip(rows,labels):
        need(row['candidate_id']==label['candidate_id'] and row['formula']==label['formula'], 'Label order/identity differs')
        need(type(label['lut4']) is int and label['lut4']>=0, 'Measured nonnegative integer LUT4 required')
    return [l['lut4'] for l in labels]
def load(output):
    authenticate(output); seal=read(output/'model-freeze.json')
    need(seal['schema']==SCHEMA and seal['protocol_sha256']==sha(output/'protocol.json') and seal['fits_completed']==1,
         'Exact one-fit protocol seal required')
    for name,digest in seal['files_sha256'].items(): need(sha(output/name)==digest, 'Frozen fitted file differs: '+name)
    model=v6.load_model(output/'model.joblib')
    need(model.kind=='mapping_v6' and model.training_formula_count==1729 and
         model.calibration['status']=='uncalibrated' and model.calibration['upper_margin_lut4'] is None and
         model.training_provenance['protocol_sha256']==sha(output/'protocol.json'),
         'Exact uncalibrated1729-row augmented mapping model required')
    return model


def run(output):
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    protocol=authenticate(output); training=ROOT/protocol['training']; fresh=ROOT/protocol['fresh']
    need(not (output/'run-start.json').exists(), 'Fit already attempted; preserve attempt')
    need(not (fresh/'labels.json').exists(), 'Fresh labels must remain unavailable before fit')
    rows=read(training/'candidates.json'); payload=read(training/'features.json'); labels=read(training/'labels.json')
    xnew=feature_matrix(rows,payload); ynew=np.asarray(labels_for(rows,labels),dtype=float)
    with np.load(ROOT/'results/feature-comparison/inputs.npz',allow_pickle=False) as data:
        original_x,original_y=data['x'],data['y']
    old_names=read(ROOT/'results/feature-comparison/columns.json')
    need(original_x.shape==(1665,336) and original_y.shape==(1665,), 'Original1665 training data contract differs')
    xold=original_x[:,[old_names.index(n) for n in v6.columns()]]
    x,y=np.vstack([xold,xnew]),np.concatenate([original_y,ynew])
    base=base_inference.load('base'); started=time.monotonic(); fits=[]
    write(output/'run-start.json',{'started_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
          'training_features_sha256':sha(training/'features.json'),'training_labels_sha256':sha(training/'labels.json'),
          'planned_fits':1,'maximum_fits':MAX_FITS,'maximum_wall_seconds':MAX_SECONDS})
    def deadline(signum,frame): raise TimeoutError('Predeclared120-second total fit-stage budget exhausted')
    previous=signal.signal(signal.SIGALRM,deadline); signal.setitimer(signal.ITIMER_REAL,MAX_SECONDS)
    try:
        with threadpool_limits(limits=1):
            model=ExtraTreesRegressor(**v6.FIXED_PARAMETERS); began=time.monotonic()
            model.fit(x[:,v6.mapping_indices()],y)
            fits.append({'fit_index':1,'seed':v6.FIXED_PARAMETERS['random_state'],'feature_count':217,
                         'training_count':1729,'fit_seconds':time.monotonic()-began})
            write(output/'timings.json',fits)
            candidate=v6.V6Predictor(estimator=model,kind='mapping_v6',feature_columns=v6.columns(),training_formula_count=1729,
                calibration=v6.uncalibrated(),feature_minimum=x.min(axis=0).tolist(),feature_maximum=x.max(axis=0).tolist(),
                frozen_tool=base.frozen_tool,runtime_source_sha256=v6.source_hashes(),
                training_provenance={'experimental_only':True,'protocol_sha256':sha(output/'protocol.json'),
                    'original_count':1665,'targeted_count':64,'training_features_sha256':sha(training/'features.json'),
                    'training_labels_sha256':sha(training/'labels.json'),'consumed40_training_count':0})
            v6.save_model(candidate,output/'model.joblib')
            panels={}
            for name in PANELS:
                r,features,targets=retained_panel(name); p,routes=points(r,features,candidate,base)
                panels[name]={'candidate_ids':[z['candidate_id'] for z in r],'formulas':[z['formula'] for z in r],
                              'actual_lut4':targets,'models':p,'routes':routes}
            write(output/'development-predictions.json',panels)
            write(output/'development-metrics.json',development_metrics(panels))
        seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
              'fits_completed':len(fits),'wall_seconds':time.monotonic()-started,
              'files_sha256':{n:sha(output/n) for n in ('model.joblib','model.json','timings.json','development-predictions.json','development-metrics.json','run-start.json')}}
        write(output/'model-freeze.json',seal)
        return seal
    except BaseException as error:
        write(output/'failure.json',{'error':str(error),'fits_completed':len(fits),'wall_seconds':time.monotonic()-started});raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)


def freeze_fresh(output):
    protocol=authenticate(output); fresh=ROOT/protocol['fresh']
    need(not (fresh/'labels.json').exists(), 'Fresh prediction freeze must precede labels')
    candidate=load(output); base=base_inference.load('base')
    rows=read(fresh/'candidates.json'); features=read(fresh/'features.json'); x=feature_matrix(rows,features)
    predictions,routes=points(rows,x,candidate,base)
    write(output/'fresh-predictions.json',{'created_at_utc':now(),'candidate_ids':[r['candidate_id'] for r in rows],
        'formulas':[r['formula'] for r in rows],'models':predictions,'routes':routes})
    seal={'schema':SCHEMA,'frozen_at_utc':now(),'protocol_sha256':sha(output/'protocol.json'),
        'model_freeze_sha256':sha(output/'model-freeze.json'),'predictions_sha256':sha(output/'fresh-predictions.json'),
        'features_sha256':sha(fresh/'features.json'),'candidates_sha256':sha(fresh/'candidates.json'),'fresh_labels_present':False}
    write(output/'fresh-point-freeze.json',seal);return seal


def score_fresh(output):
    protocol=authenticate(output); load(output); fresh=ROOT/protocol['fresh']; seal=read(output/'fresh-point-freeze.json')
    for key,path in [('protocol_sha256',output/'protocol.json'),('model_freeze_sha256',output/'model-freeze.json'),
                     ('predictions_sha256',output/'fresh-predictions.json'),('features_sha256',fresh/'features.json'),
                     ('candidates_sha256',fresh/'candidates.json')]:
        need(seal[key]==sha(path), 'Fresh sealed payload differs: '+key)
    rows=read(fresh/'candidates.json'); labels=read(fresh/'labels.json'); y=labels_for(rows,labels)
    saved=read(output/'fresh-predictions.json')
    need(saved['candidate_ids']==[r['candidate_id'] for r in rows] and saved['formulas']==[r['formula'] for r in rows], 'Fresh point alignment differs')
    metrics={name:model_metrics(saved['models'][name],y) for name in NAMES}; development=read(output/'development-metrics.json')
    gates={}
    for name in NAMES[1:]:
        checks=compare(metrics['base'],metrics[name]); passed=all(checks.values())
        gates[name]={'checks':checks,'fresh_gate_passed':passed,
             'development_gate_passed':development['gates'][name]['development_gate_passed'],
             'scoped_experimental_eligibility':passed and development['gates'][name]['development_gate_passed']}
    result={'schema':SCHEMA,'models':metrics,'gates':gates,'fresh_labels_sha256':sha(fresh/'labels.json'),
        'fresh_point_freeze_sha256':sha(output/'fresh-point-freeze.json'),'scope':protocol['scope'],'fits':1,'new_native_jobs':0}
    write(output/'fresh-metrics.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','freeze-fresh','score-fresh'))
    parser.add_argument('--output',type=Path,default=ROOT/'results/targeted-coverage')
    parser.add_argument('--training',type=Path,default=ROOT/'results/targeted-coverage-data')
    parser.add_argument('--fresh',type=Path,default=ROOT/'results/targeted-coverage-validation')
    args=parser.parse_args(); output=args.output.resolve()
    result=prepare(output,args.training.resolve(),args.fresh.resolve()) if args.command=='prepare' else {
        'run':run,'freeze-fresh':freeze_fresh,'score-fresh':score_fresh}[args.command](output)
    print(json.dumps(result,indent=2))
