"""Authorized exact28 historical-only fits and zero-label MD5 model preparation.

No target outcome loader, measurement provider, replay or native entry point.
Old fitted artifacts are never loaded. Existing estimator classes are reused
without tuning. Adaptive target branches remain unobserved.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import md5_offline_controller as identity

PREREG=identity.PREREG
SOURCE='scripts/freeze_md5_historical28_models.py'
TEST_SOURCE='tests/test_freeze_md5_historical28_models.py'
AUDIT=PREREG/'historical-cohort-contract-audit-v2/audit.json'
AUDIT_SHA='e5776dec80bf37196752cc5d5051e7e378175dde21840ac970e3ce4feca4ea45'
AUDIT_HELPER_SHA='d4f34c60afe8b829cab913fa281f9233bc7ae18cb3bbf45a17040f08ec5f80ed'
AUDIT_MANIFEST_SHA='f8e8df96e43b6d6dde5699b4c4f90b481feffbf66c715884f1cb28a8cecbba6d'
ADAPTER_SHA='782199d586ea553a998def3c02af76edc8e9ce30cc8349546735fa952e0af6b8'
CERT_HELPER='scripts/certify_md5_heldout_roster.py'
CERT_HELPER_SHA='e8d3297a0e07d646b7e7300f524a99ecf55222e2acd5c0cac65d4daa050ebd96'
STATIC={'frequency','merit','calibrated_latency','random','raw_regression','ranking',
        'normalized_xgb','feasible_benefit_xgb','factorized_feasibility_xgb'}


def require(value,message):
    if not value: raise ValueError(message)


def digest(value): return identity.digest(value)
def sha(path): return identity.sha(path)
def read(path): return json.loads(path.read_text())


def load_source_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def preflight():
    """All identity/source/package pins precede any historical deserialization/fit."""
    require(sha(ROOT/'isaforge/md5_offline_controller.py')==ADAPTER_SHA,'Reviewed adapter changed')
    pool=identity.load_public_pool(ROOT)
    contract=read(ROOT/identity.V1/'controller-contract.json')
    dependencies=dict(python=platform.python_version(),packages={name:importlib.metadata.version(name)
        for name in contract['dependencies']['packages']})
    require(dependencies==contract['dependencies'],'Frozen dependency versions changed')
    path=ROOT/AUDIT
    require(sha(path)==AUDIT_SHA and path.with_name(path.name+'.sha256').read_text().strip()==AUDIT_SHA,
        'Historical28 audit changed')
    audit=read(path)
    audit_manifest=ROOT/AUDIT.parent/'artifact-manifest.json'
    require(sha(audit_manifest)==AUDIT_MANIFEST_SHA and
        audit_manifest.with_name(audit_manifest.name+'.sha256').read_text().strip()==AUDIT_MANIFEST_SHA,
        'Historical audit manifest changed')
    require(audit['status']=='passed_bounded_historical28_contract_audit' and
        audit['model_fits']==audit['model_predictions']==audit['md5_candidate_outcomes_read']==0 and
        audit['cohort']['retained_ids']==contract['fitting_contract']['required_ids'] and
        audit['cohort']['rows']==28 and audit['cohort']['group_count']==7 and
        all(v=='pass' for v in audit['gates'].values()),'Exact28 audit authority differs')
    bindings={str(path.relative_to(ROOT)):AUDIT_SHA,
              str(path.relative_to(ROOT))+'.sha256':sha(path.with_name(path.name+'.sha256')),
              str(audit_manifest.relative_to(ROOT)):AUDIT_MANIFEST_SHA}
    for name,item in audit['input_files'].items():
        if name.startswith(('isaforge/','src/','scripts/')) and name.endswith('.py') or name=='pyproject.toml':
            require(sha(ROOT/name)==item['sha256'],'Audited runtime source changed: '+name)
            bindings[name]=item['sha256']
    for name,expected in ((CERT_HELPER,CERT_HELPER_SHA),
        (str(AUDIT.parent/'audit.py'),AUDIT_HELPER_SHA)):
        require(sha(ROOT/name)==expected,'Bound pure input helper changed: '+name);bindings[name]=expected
    for path,expected in pool.bindings: bindings[str(path.relative_to(ROOT))]=expected
    for name in (SOURCE,TEST_SOURCE):bindings[name]=sha(ROOT/name)
    # Only now import the reviewed pure framing and public-discovery helpers.
    framing=load_source_module(ROOT/AUDIT.parent/'audit.py','md5_historical28_framing')
    independent=read(ROOT/PREREG/'independent-cohort-audit.json')
    history_path=next(name for name in independent['input_bindings'] if name.endswith('/history.json'))
    expected=independent['input_bindings'][history_path]
    require(sha(ROOT/history_path)==expected and
        (ROOT/(history_path+'.sha256')).read_text().strip()==expected,'Historical container changed')
    training,skipped=framing.frame_allowlisted((ROOT/history_path).read_bytes(),set(audit['cohort']['retained_ids']))
    require([r['candidate_id'] for r in training]==audit['cohort']['retained_ids'] and
        skipped==audit['cohort']['skipped_record_ids_only'] and
        digest(training)==audit['cohort']['exact_training_rows_codesign_digest'], 'Exact28 training rows/order changed')
    bindings[history_path]=expected
    bindings[history_path+'.sha256']=sha(ROOT/(history_path+'.sha256'))
    public_helper=load_source_module(ROOT/CERT_HELPER,'md5_public_input_helper')
    data=public_helper.public_inputs()  # No extraction or candidate outcomes.
    from isaforge import budgeted_selection as b
    from isaforge.latency_features import candidate_features
    from isaforge.speedup_corpus import family
    from isaforge.ranking import grouped_labels
    from isaforge.model import validate_training_rows
    calibration_path=public_helper.BASE/'inputs/latency-calibration.json'
    preregistration=read(ROOT/PREREG/'preregistration.json')
    expected=preregistration['source_artifact_sha256'][str(calibration_path)]
    require(sha(ROOT/calibration_path)==expected,'Public calibration changed')
    calibration=read(ROOT/calibration_path);bindings[str(calibration_path)]=expected
    public=[]
    baseline=data['discovery']['baseline_performance']
    for mapping,candidate in zip(pool.validate(),data['candidates']):
        require(mapping['formula']==candidate['formula'] and mapping['name']==candidate['name'],'Public roster order changed')
        latency=candidate_features(candidate,data['program'],baseline['cycles'],baseline['instructions'],calibration)
        public.append(dict(candidate_id=mapping['preparation_candidate_id'],
            benchmark='beebs-nettle-md5:'+pool.logical_namespace,formula=candidate['formula'],
            **candidate['features'],latency_features=latency))
    public=b.public_rows(public)
    require(len(public)==12 and [r['candidate_id'] for r in public]==list(pool.ids),'Exact12 public IDs required')
    validate_training_rows(training)
    families={family(r['formula']) for r in public}
    require(all('md5' not in r['workload_group'].lower() and family(r['formula']) not in families
        and b.validate_outcome(r) for r in training),'Training source/family leakage')
    grouped_labels(training)  # Validate viability; never fit.
    historical_protocol=history_path.replace('history.json','protocol.json')
    expected=audit['input_files'][historical_protocol]['sha256']
    require(sha(ROOT/historical_protocol)==expected,'Historical context protocol changed')
    protocol=read(ROOT/historical_protocol);bindings[historical_protocol]=expected
    contexts={name:copy.deepcopy(protocol['contexts'][name]) for name in sorted({r['benchmark'] for r in training})}
    contexts[public[0]['benchmark']]=dict(context_id=pool.logical_namespace,workload_group='beebs-nettle-md5',
        archived_hardware_context_id=pool.archived_hardware_context,
        identity_scope='Preparation/public model namespace only; no native plan or release.',
        compiler_flags=read(ROOT/public_helper.BASE/'plan.json')['compiler_flags'],
        public_baseline_performance=baseline)
    bindings.update(data['input_sha256'])
    for name in (str(PREREG/'preregistration.json'),str(PREREG/'independent-cohort-audit.json'),
                 str(PREREG/'independent-cohort-audit.json.sha256')):
        bindings[name]=sha(ROOT/name)
    for name,expected in bindings.items():require(sha(ROOT/name)==expected,'Input changed during preflight: '+name)
    return dict(pool=pool,contract=contract,audit=audit,training=training,public=public,contexts=contexts,
        source_bindings=bindings,dependencies=dependencies,history_container=history_path,
        baseline=baseline,calibration=calibration)


def revalidate(data):
    data['pool'].validate()
    for name,expected in data['source_bindings'].items():
        require(sha(ROOT/name)==expected,'Bound input changed: '+name)


def initial_controls(public,training,predictions,semantic,seed,policies):
    """Source-matched query-one scores; only truly static rules get full orders."""
    from isaforge import budgeted_selection as b,count_selection as count
    ordered=copy.deepcopy(public);random.Random(seed).shuffle(ordered)
    indexed={kind:{r['candidate_id']:r for r in rows} for kind,rows in predictions.items()}
    per_op=statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in training)
    clock=min(r['routed_fmax_min_mhz'] for r in training)
    sem={r['candidate_id']:r for r in semantic}
    result=[]
    for policy in policies[:14]:
        def score(row):
            identity=row['candidate_id'];analytic=row['latency_features']['estimated_speedup']
            if policy=='frequency':return (row['runs'],)
            if policy=='merit':return (row['saved'],)
            if policy=='calibrated_latency':return (analytic,)
            if policy=='random':return (0,)
            if policy=='raw_regression':return (indexed['raw'][identity]['mean'],)
            if policy=='ranking':return (indexed['ranking'][identity]['rank_score'],)
            if policy=='normalized_xgb':return (indexed['normalized'][identity]['mean'],)
            if policy=='feasible_benefit_xgb':return (indexed['utility'][identity]['mean_fractional_cycle_savings'],)
            if policy=='factorized_feasibility_xgb':return (indexed['feasibility'][identity]['decision_score'],)
            if policy=='latency_cost_heuristic':
                area=per_op*row['tree_op_count']
                return (int(area<=64 and clock>=12),max(0.,analytic-1.)/max(1.,area),analytic)
            if policy in ('hybrid_gp_zero_shot','hybrid_gp_adapt'):
                return (b.hybrid_score(row,indexed['hardware'][identity],1.,64,12.),analytic)
            estimate=sem[identity] if policy.endswith('_semantic') else indexed['hardware'][identity]
            return (count.count_score(row,estimate,1.,64,12.),analytic)
        ranked=sorted(ordered,key=score,reverse=True)
        result.append(dict(policy=policy,seed=seed,planned_budget=3,endpoint_kind='B3_initial',
            paid_prefix=[],target_labels_read=0,chosen_id=ranked[0]['candidate_id'],
            initial_scores=[dict(candidate_id=r['candidate_id'],score=list(score(r))) for r in ordered],
            full_static_order=[r['candidate_id'] for r in ranked] if policy in STATIC else None,
            order_scope='complete static rule order' if policy in STATIC else 'query-one only; paid-incumbent/adaptive branches unobserved'))
    return result


class InitialProofCaptured(Exception): pass


def finite_initial(public,training,posterior,*,policy,seed,budget):
    """Stop from on_acquire BEFORE search reserves/charges or calls a provider."""
    from isaforge import finite_selection as f
    captured=[]
    def capture(proof): captured.append(proof);raise InitialProofCaptured()
    def forbidden_provider(_):raise AssertionError('Target outcome provider must never run')
    try:
        f.search(public,training,forbidden_provider,posterior=posterior,policy=policy,
            area_cap=64,clock_mhz=12.,seed=seed,budget=budget,on_acquire=capture)
    except InitialProofCaptured:pass
    require(len(captured)==1 and captured[0]['event']['charged_before_query']==0 and
        captured[0]['successful_paid_ids']==[],'Only zero-paid initial proof required')
    return dict(policy=policy,seed=seed,planned_budget=budget,endpoint_kind='independent_planned_horizon_initial',
        proof=captured[0],realized_trajectory=None,paid_target_queries=0)


def estimator_count(name,model):
    if name in ('hardware','semantic'):return dict(estimator_fits=len(model.models),scaler_fits=1,constant_members=0)
    if name=='ranking':return dict(estimator_fits=1,scaler_fits=0,constant_members=0)
    members=model._models if name=='raw' else model.models
    return dict(estimator_fits=sum(m is not None for m in members),scaler_fits=0,
        constant_members=(20 if not members else sum(m is None for m in members)))


def preprocessing(name,model):
    from isaforge import budgeted_selection as b,semantic_selection as s
    value=dict(model_family=name)
    if name in ('hardware','semantic'):
        value.update(columns=list(s.COLUMNS if name=='semantic' else b.STRUCTURAL_COLUMNS),
            input_scaler=dict(mean=model.scaler.mean_.tolist(),scale=model.scaler.scale_.tolist()),
            outputs={key:dict(mean=center,scale=scale,kernel=gp.kernel_.get_params(),alpha=gp.alpha)
                for key,(gp,center,scale) in model.models.items()},device_fit_probability=model.device_fit_probability)
    if hasattr(model,'area_per_op'):value['area_per_tree_operation']=model.area_per_op
    if hasattr(model,'constant'):value['constant']=model.constant
    if hasattr(model,'constants'):value['member_constants']=model.constants
    if hasattr(model,'member_seeds'):value['member_seeds']=model.member_seeds
    return value


def run_fits(data,output,seal):
    """No model choice: exact existing constructors, settings and row ordering."""
    import joblib
    from isaforge import budgeted_selection as b,semantic_selection as s,joint_hardware as j,finite_selection as f
    from isaforge.model import SpeedupPredictor
    from isaforge.ranking import SpeedupRanker
    from isaforge.feasible_benefit import FeasibleBenefitPredictor
    from isaforge.feasibility_selection import FeasibilitySelectionPredictor
    training,public=data['training'],data['public'];ids=[r['candidate_id'] for r in training]
    receipts=[];predictions=[];orders=[]
    def fit_export(name,model,folder,*,seed):
        revalidate(data)
        folder.mkdir(parents=True,exist_ok=False)
        start=time.monotonic_ns()
        receipt=dict(model_family=name,seed=seed,high_level_fit_calls=1,training_ids=ids,
            training_rows_sha256=digest(training),fit_monotonic_start_ns=start,status='started')
        receipts.append(receipt);seal(output/'progress.json',dict(status='fitting',invoked_fit_calls=len(receipts),receipts=receipts))
        model.fit(copy.deepcopy(training));end=time.monotonic_ns()
        if hasattr(model,'training_ids'):
            require(len(model.training_ids)==len(ids) and set(model.training_ids)==set(ids),'Estimator training IDs differ')
            if name!='ranking':require(model.training_ids==ids,'Estimator training order differs')
            receipt['estimator_internal_training_id_order']=list(model.training_ids)
        receipt.update(status='complete',fit_monotonic_end_ns=end,fit_seconds=(end-start)/1e9,**estimator_count(name,model))
        joblib.dump(model,folder/'model.joblib',compress=3)
        seal(folder/'preprocessing.json',preprocessing(name,model));seal(folder/'fit-receipt.json',receipt)
        seal(output/'progress.json',dict(status='fitting',invoked_fit_calls=len(receipts),receipts=receipts))
        return model
    semantic=fit_export('semantic',s.SemanticHardwareSurrogate(),output/'semantic',seed=None)
    semantic_predictions=semantic.predict(public)
    seal(output/'semantic/predictions.json',semantic_predictions);seal(output/'semantic/snapshot.json',semantic.snapshot())
    posterior=j.JointHardwarePosterior.from_fitted(semantic,training,public)  # No refit.
    joint=posterior.joint()
    for values in joint['outputs'].values():
        for key in ('mean','covariance','observation_covariance'):values[key]=values[key].tolist()
    seal(output/'joint/initial.json',posterior.snapshot());seal(output/'joint/distribution.json',joint)
    seal(output/'joint/marginals.json',posterior.predict())
    for seed in range(5):
        constructors=(('raw',SpeedupPredictor(seed=seed)),('ranking',SpeedupRanker(seed=seed)),
            ('normalized',b.NormalizedSpeedupPredictor(seed)),('hardware',b.HardwareSurrogate()),
            ('utility',FeasibleBenefitPredictor(seed)),('feasibility',FeasibilitySelectionPredictor(seed)))
        predicted={};models={};prediction_receipts=[]
        for name,model in constructors:
            folder=output/'models'/f'seed{seed}'/name
            models[name]=fit_export(name,model,folder,seed=seed)
            began=time.monotonic_ns()
            values=model.predict(public,area_cap=64) if name in ('utility','feasibility') else model.predict(public)
            predicted[name]=values
            # Authenticate saved objects without any validation refit.
            loaded=joblib.load(folder/'model.joblib')
            repeated=loaded.predict(public,area_cap=64) if name in ('utility','feasibility') else loaded.predict(public)
            require(digest(repeated)==digest(values),'Saved estimator predictions changed')
            prediction_receipts.append(dict(model_family=name,public_digest=digest(public),
                predictions_digest=digest(values),prediction_and_export_validation_seconds=(time.monotonic_ns()-began)/1e9,
                export_prediction_exact=True,validation_refits=0))
            seal(folder/'predictions.json',values)
        seal(output/'predictions'/f'seed{seed}.json',dict(seed=seed,values=predicted,receipts=prediction_receipts))
        predictions.append(dict(seed=seed,values=predicted))
        orders.extend(initial_controls(public,training,predicted,semantic_predictions,seed,list(data['pool'].policies)))
        draws,metadata=f.normal_draws(seed)
        seal(output/'fantasies'/f'seed{seed}.json',dict(normals=draws.tolist(),metadata=metadata))
        for policy in f.POLICIES:
            for budget in (1,2,3):
                proof=finite_initial(public,training,posterior,policy=policy,seed=seed,budget=budget)
                seal(output/'initial-proofs'/policy/f'seed{seed}-B{budget}.json',proof)
                orders.append(proof)
    seal(output/'initial-orders.json',orders)
    require(len(receipts)==31 and len(orders)==115,'Exact31 family fits and115 initial records required')
    require(not posterior.observed_ids and not posterior.conditioned_ids,'No target conditioning allowed')
    return dict(high_level_fit_calls=len(receipts),estimator_fits=sum(r['estimator_fits'] for r in receipts),
        scaler_fits=sum(r['scaler_fits'] for r in receipts),constant_members=sum(r['constant_members'] for r in receipts),
        receipts=receipts,initial_order_records=len(orders),finite_initial_proofs=45,
        full_static_orders=45,validation_refits=0,semantic_initial_shared_with_joint=True)


def build(output):
    output=Path(output).resolve()
    require(output.parent==(ROOT/PREREG).resolve() and not output.exists(),'Fresh direct model preparation directory required')
    data=preflight();revalidate(data)
    output.mkdir()
    def seal(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        payload=identity.pack(value)+b'\n';path.write_bytes(payload)
        path.with_name(path.name+'.sha256').write_text(sha(path)+'\n')
    pre=dict(schema='isaforge-md5-historical28-zero-label-model-preparation-v1',
        scope='Consumed MD5 workload; prospective candidate/family-heldout development, not unseen-workload generalization.',
        candidate_dispatch_enabled=False,measurement_authorization=False,new_pool_labels=0,target_outcomes_read=0,
        historical_md5_labels_excluded=True,native_jobs=0,expected_high_level_fit_calls=31,
        expected_training_rows=28,training_rows_digest=digest(data['training']),public_rows_digest=digest(data['public']),
        history_container=data['history_container'],source_bindings=data['source_bindings'],dependencies=data['dependencies'],
        logical_public_namespace=data['pool'].logical_namespace,archived_hardware_context=data['pool'].archived_hardware_context,
        policies=list(data['pool'].policies),seeds=list(range(5)),evaluation_area_caps=[64],clock_mhz=12.,budgets=[1,2,3],
        no_outcome_evidence='Pinned public preregistration, reviewed preparation+erratum and bounded identity audit report zero new-pool labels; no target outcome path opened.',
        order_rule='Only truly static controls have complete orders. Cost/zero-shot GP/adaptive/count/semantic rules have query-one scores only; finite plannedB1/B2/B3 initial proofs distinct. No realized target trajectories.',
        cost_rule='Fit, inference, export validation and initial acquisition host times distinct; historical label/baseline/calibration costs are not free or summed into overlapping scopes.',
        limitations=['No fresh correctness/hardware/performance labels; no paid-prefix replay or superiority result.',
            'Five dependent seeds; Gaussian/noise/device assumptions and bootstrap disagreement are uncalibrated.',
            'Joblib objects are trusted local artifacts, require exact bound source/package versions; not a portable untrusted model format.',
            'A real released controller and hardware protocol remain separately reviewed and unauthorized.'])
    seal(output/'pre-fit-protocol.json',pre)
    for name,value in (('history28',data['training']),('public12',data['public']),('contexts',data['contexts']),
        ('id-remap',data['pool'].validate()),('source-bindings',data['source_bindings'])):
        seal(output/'inputs'/(name+'.json'),value)
    result=dict(**pre,status='incomplete',model_artifacts_created=False,model_fit_calls=0)
    try:
        counts=run_fits(data,output,seal);revalidate(data)
        result.update(status='zero_label_models_complete_not_released',model_artifacts_created=True,
            model_fit_calls=counts['high_level_fit_calls'],fit_accounting=counts)
    except BaseException as error:
        progress=read(output/'progress.json') if (output/'progress.json').exists() else {}
        result.update(status='failed_preserve_partial_no_retry',failure=repr(error),
            model_fit_calls=progress.get('invoked_fit_calls',0),
            model_artifacts_created=any(output.rglob('*.joblib')))
        raise
    finally:
        seal(output/'model-preparation.json',result)
        manifest={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
        seal(output/'artifact-manifest.json',manifest)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/PREREG/'model-preparation-v1')
    args=parser.parse_args(argv);value=build(args.output)
    print(json.dumps({key:value[key] for key in ('status','model_fit_calls','candidate_dispatch_enabled','target_outcomes_read','native_jobs')}))


if __name__=='__main__':main()
