"""Create a zero-label MD5 controller contract, never models or measurements.

Only explicit public preregistration inputs and recipe source text are read.
Project controller/model modules are parsed as text, never imported or called.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
PREREG = Path('results/2026-10-26-md5-candidate-heldout-prereg')
SOURCE = 'scripts/prepare_md5_heldout_controller.py'
CERTS = PREREG/'offline-certificates-v1'
ROSTER_SHA256 = 'c4ac398adbd28f3ef975d60a73b0863b20974a794259ed3141050bbc7e60cdd9'
CERTIFICATE_SHA256 = '3f04654ebb63be2a71bb7f6fe69ea6511d7e9b7aad668e232fcd3f46d4a65a1a'
AUDIT_SHA256 = 'c0c58c9f6e89bb12cc954cf54ffe84eb22b23b911f8dbc1ecb8842e6debc2f8b'
RECIPE_SOURCES = (
    'scripts/g723_selection_campaign.py', 'scripts/tacle_selection_campaign.py',
    'isaforge/tacle_workload.py', 'isaforge/budgeted_selection.py',
    'isaforge/model.py', 'isaforge/ranking.py', 'isaforge/features.py',
    'isaforge/prospective_selection.py', 'isaforge/speedup_corpus.py',
    'isaforge/feasible_benefit.py', 'isaforge/feasible_benefit_experiment.py',
    'isaforge/feasibility_selection.py', 'isaforge/factorized_selection_experiment.py',
    'isaforge/count_selection.py', 'isaforge/semantic_selection.py',
    'isaforge/structural_features_v3.py', 'isaforge/area_model_v2.py',
    'isaforge/area_model.py', 'isaforge/rtl.py', 'isaforge/joint_hardware.py',
    'isaforge/finite_selection.py', 'isaforge/codesign.py',
    'isaforge/guarded_attempts.py', 'isaforge/observed_command.py', 'pyproject.toml')
PACKAGES = ('numpy','scipy','scikit-learn','xgboost','joblib')
EXPECTED_POLICIES = (
    'frequency','merit','calibrated_latency','latency_cost_heuristic','random',
    'raw_regression','ranking','normalized_xgb','hybrid_gp_zero_shot','hybrid_gp_adapt',
    'feasible_benefit_xgb','factorized_feasibility_xgb','hybrid_gp_adapt_count',
    'hybrid_gp_adapt_count_semantic','fixed_joint_myopic','fixed_joint_lookahead',
    'fixed_joint_heuristic_fallback')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value,sort_keys=True,allow_nan=False).encode()


def digest(value):
    """Exact codesign.digest convention, without importing runtime modules."""
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_json(path, expected=None):
    actual = sha(path)
    require(path.with_name(path.name+'.sha256').read_text().strip() == actual,
            'SHA256 sidecar mismatch: '+str(path))
    require(expected is None or actual == expected, 'Pinned evidence changed: '+str(path))
    return json.loads(path.read_text())


def read_public_inputs(root):
    """Allowlist only; no native root, fitted files, ledger or outcomes opened."""
    prereg = root/PREREG
    prereg_manifest=json.loads((prereg/'artifact-manifest.json').read_text())
    roster = json.loads((prereg/'roster.json').read_text())
    require(sha(prereg/'roster.json') == ROSTER_SHA256 == prereg_manifest['roster.json'] and
            sha(prereg/'preregistration.json')==prereg_manifest['preregistration.json'], 'Exact preregistration changed')
    protocol=json.loads((prereg/'preregistration.json').read_text())
    require(protocol['candidate_dispatch_enabled'] is False and protocol['new_pool_labels']==0 and
            protocol['historical_md5_labels_excluded'] is True and protocol['eligibility_pending'] is True,
            'Preregistration authorization boundary changed')
    require(len(roster) == 12 and len({r['name'] for r in roster}) == 12 and
            len({r['formula'] for r in roster}) == 12 and
            all(set(r)=={'name','formula'} for r in roster), 'Exact twelve-row roster required')
    audit = verified_json(prereg/'independent-cohort-audit.json',AUDIT_SHA256)
    identities = verified_json(prereg/'cross-context-identity-audit-v2.json')
    require(identities['authorization']['bounded_identity_membership_gate'] == 'passed' and
            identities['authorization']['candidate_dispatch'] is False and
            identities['authorization']['new_pool_labels'] == 0, 'Identity eligibility gate changed')
    certificate = verified_json(root/CERTS/'certificates.json',CERTIFICATE_SHA256)
    manifest = verified_json(root/CERTS/'artifact-manifest.json')
    require(manifest['certificates.json']==CERTIFICATE_SHA256 and
            certificate['context_id']==protocol['existing_context_id'], 'Certificate context/manifest changed')
    require(certificate['status']=='offline_certificates_complete_eligibility_pending' and
            certificate['candidate_dispatch_enabled'] is False and certificate['new_pool_labels']==0 and
            certificate['eligibility_pending'] is True and len(certificate['certificates'])==12,
            'Incomplete or authorizing certificate package')
    require(certificate['roster_file_sha256']==ROSTER_SHA256 and
            certificate['roster_codesign_digest']==digest(roster), 'Certificate roster binding changed')
    for row, cert in zip(roster,certificate['certificates']):
        require(all(row[key]==cert[key] for key in ('name','formula')) and
                cert['candidate_id']==digest([certificate['context_id'],row['formula']]) and
                cert['relocation_check']['safe'] is True and cert['lowering_check']['passed'] is True and
                cert['lowering_check']['comparisons']==64*cert['lowering_check']['blocks'],
                'Ordered certificate identity/check mismatch')
        assembly = cert['assembly']
        require(assembly == row['name']+'.S' and
                sha(root/CERTS/assembly)==cert['assembly_sha256']==manifest[assembly],
                'Emitted assembly changed')
    cohort = audit['cohort_amendment']
    require(audit['roster']['file_sha256']==ROSTER_SHA256 and
            cohort['retained_fitting_rows']==len(cohort['retained_training_ids'])==28 and
            len(set(cohort['retained_training_ids']))==28 and cohort['retained_group_count']==7 and
            cohort['retained_target_workload_rows']==0 and cohort['remaining_roster_family_overlap'] is False,
            'Common amended historical cohort changed')
    evidence = {str(PREREG/name):sha(prereg/name) for name in (
        'roster.json','preregistration.json','artifact-manifest.json','independent-cohort-audit.json',
        'independent-cohort-audit.json.sha256','cross-context-identity-audit-v2.json',
        'cross-context-identity-audit-v2.json.sha256')}
    evidence.update({str(CERTS/name):sha(root/CERTS/name) for name in
                     ('certificates.json','certificates.json.sha256','artifact-manifest.json',
                      'artifact-manifest.json.sha256')})
    return dict(roster=roster,audit=audit,certificate=certificate,evidence_sha256=evidence)


def recipe_snapshot(texts, audit):
    """Freeze source expressions/defaults without executing source or models."""
    snapshots = {}
    declared = {}
    constructors = {'XGBRegressor','XGBClassifier','GaussianProcessRegressor','Matern','StandardScaler'}
    for name,text in texts.items():
        hashed = hashlib.sha256(text.encode()).hexdigest()
        expected = audit['source_bindings'].get(name)
        require(expected is None or hashed==expected, 'Audited recipe source changed: '+name)
        entry = dict(sha256=hashed,archived_audit_binding_verified=expected is not None)
        if name.endswith('.py'):
            tree = ast.parse(text)
            assignments = {target.id:node.value for node in tree.body if isinstance(node,ast.Assign)
                           for target in node.targets if isinstance(target,ast.Name)}
            declared[name]=assignments
            entry['settings_expressions']={key:ast.unparse(value) for key,value in assignments.items()
                if key.endswith('SETTINGS') or key in ('PARAMETERS','EXTRA_COLUMNS','COLUMNS','STRUCTURAL_COLUMNS')}
            entry['constructor_calls']=[ast.unparse(node) for node in ast.walk(tree)
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in constructors]
            entry['model_constructor_defaults']=[ast.unparse(node.args) for node in ast.walk(tree)
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='__init__']
        snapshots[name]=entry
    base = ast.literal_eval(declared['isaforge/budgeted_selection.py']['POLICIES'])
    old = declared['isaforge/tacle_workload.py']['POLICIES']
    require(isinstance(old,ast.Tuple) and isinstance(old.elts[0],ast.Starred) and
            ast.unparse(old.elts[0].value)=='b.POLICIES', 'Fourteen-policy declaration changed')
    extras = [ast.literal_eval(x) for x in old.elts[1:]]
    finite = declared['isaforge/finite_selection.py']
    finite_names = [ast.literal_eval(finite[x.id]) for x in finite['POLICIES'].elts]
    policies = [*base,*extras,*finite_names]
    require(tuple(policies)==EXPECTED_POLICIES, 'Exact existing seventeen policies required')
    require(ast.unparse(declared['scripts/g723_selection_campaign.py']['POLICIES'])=='[*OLD_POLICIES, *f.POLICIES]',
            'Existing seventeen-policy composition changed')
    return snapshots,policies


def contract(data,snapshots,policies,dependencies):
    certs=data['certificate'];cohort=data['audit']['cohort_amendment']
    source_hashes={name:row['sha256'] for name,row in snapshots.items()}
    identity_basis=dict(schema='isaforge-md5-candidate-heldout-preparation-context-v1',
        archived_hardware_context_id=certs['context_id'],roster_file_sha256=ROSTER_SHA256,
        certificates_file_sha256=CERTIFICATE_SHA256,recipe_source_sha256=source_hashes,
        ordered_training_ids=cohort['retained_training_ids'],seeds=[0,1,2,3,4],
        area_delta_lut4=64,clock_mhz=12.,planned_budgets=[1,2,3])
    context_id=digest(identity_basis)
    remap=[dict(name=row['name'],formula=row['formula'],
        archived_context_id=certs['context_id'],archived_candidate_id=cert['candidate_id'],
        preparation_context_id=context_id,preparation_candidate_id=digest([context_id,row['formula']]),
        assembly_path=str(CERTS/cert['assembly']),assembly_sha256=cert['assembly_sha256'])
        for row,cert in zip(data['roster'],certs['certificates'])]
    definitions=[]
    for index,name in enumerate(policies):
        if index<10: path,entry='isaforge/budgeted_selection.py','search'
        elif index<12: path,entry='isaforge/feasible_benefit.py','search (factorized aliases decision_score only)'
        elif index<14: path,entry='isaforge/count_selection.py','search; semantic policy passes SemanticHardwareSurrogate'
        else: path,entry='isaforge/finite_selection.py','search/acquisition'
        definitions.append(dict(policy=name,definition_source=path,definition_sha256=source_hashes[path],
            entrypoint=entry,update=('fixed-initial joint Gaussian conditioning on verified paid prefix' if index>=14
                else 'dynamic successful-paid-prefix refit with unchanged recipe' if name in
                ('hybrid_gp_adapt','hybrid_gp_adapt_count','hybrid_gp_adapt_count_semantic')
                else 'fixed initial scoring; no target refit'),
            endpoint_execution=('independent B1/B2/B3 horizons; also report B3 prefixes separately' if index>=14
                else 'one B3 trajectory; B1/B2 are its prefixes')))
    return dict(schema='isaforge-md5-controller-preparation-v1',status='preparation_only_eligibility_pending',
        candidate_dispatch_enabled=False,dispatch=False,new_pool_labels=0,model_artifacts_created=False,
        model_fits=0,model_predictions=0,measurement_authorization=False,native_jobs=0,
        preparation_context_id=context_id,identity_basis=identity_basis,id_remap=remap,
        identity_rule='Preparation IDs use codesign.digest([preparation_context_id,formula]); archived IDs remain evidence only. No native plan/pool seal is created. Future release must bind this remap explicitly; old 12-pool seal is non-authorizing.',
        evidence_sha256=data['evidence_sha256'],dependencies=dependencies,policies=definitions,
        primary=dict(area_delta_lut4=64,clock_mhz=12.,budget=3,
            endpoint='best verified feasible whole-program cycle reduction = 1 - candidate_cycles/baseline_cycles',
            hardware='complete integrated PicoRV32 PCPI SoC; minimum routed Fmax over seeds 1,2,3; device fit required',
            baseline_fallback='Unmodified verified baseline always available: speedup1 / reduction0; select baseline if no paid verified feasible improvement'),
        comparisons=dict(evaluation_area_caps=[64],model_cap_replica_settings_unchanged=[32,64,128],
            budgets=[1,2,3],seeds=[0,1,2,3,4],seeds_are_dependent=True,
            primary_simple_comparators=['frequency','merit','calibrated_latency','latency_cost_heuristic','random'],
            b1_b2='Show all B3 prefixes. Finite controls also have separate planned-B1/B2 endpoints; never splice budget-specific winners into one trajectory.'),
        fitting_contract=dict(required_ids=cohort['retained_training_ids'],rows=28,groups=7,
            public_identity_digest=cohort['retained_public_identity_digest'],historical_md5_labels_excluded=True,
            family_exclusions='All historical MD5 plus every roster operation-tree family; same exact28 rows for all learned policies.',
            stale_artifact_rule='Old29-row weights/scalers/centers/proxies/predictions/covariances are invalid. Never load/reuse them. Future rebuild of unchanged recipes requires separate authorization; this package does not fit.',
            pending_checks=['Verify all28 historical training contracts on separately authorized historical-only access.',
                'Verify at least one unequal within-context ranking pair without target labels.',
                'Bind freshly rebuilt weights/scalers/predictions/covariances/fantasy tables, same cohort and dependencies before root release.']),
        collection_contract=dict(authorizing=False,maximum_unique_candidate_attempts=12,retries=0,
            live=dict(policy='fixed_joint_lookahead',seed=0,planned_budget=3,area_delta_lut4=64,clock_mhz=12.),
            sequence='Future authorized controller seals each chosen live acquisition before dispatch; seals full B3 live trace before remainder reference collection in fixed roster order. No reference outcome can exist in policy-accessible state before its paid query.',
            proof_before_dispatch=['source/model/package/cohort/public-pool/ID-remap digests','chosen ID and emitted assembly SHA256',
                'planned horizon and exact attempted prefix','verified paid observation IDs only','initial/current model or joint state digest, predictions and acquisition/tie proof','durable charged attempt reservation'],
            paid_prefix_only='Update each policy only from its own charged successful verified observations; no unpaid/reference/other-policy observations. Preserve distinct dynamic-refit and fixed-initial conditioning semantics.',
            charging='Reserve/charge before native invocation; every attempt including terminal failures consumes one of12 and one query for any policy requesting it. No duplicates, retry, replacement or hidden cache discount.',
            failures='Known invalid outcomes remain failures; infrastructure/timeouts/interruption remain unknown, never fabricated Gaussian or negative labels. No numerical GP update from failures.',
            interruption='Stop collection immediately on exception/interruption or ambiguous seal/ledger completion. Preserve proof/partial artifacts and reservation; no automatic resume/retry. Root must review explicit recovery.',
            replay='Other seeds/policies/planned horizons use charged cooperative replay after collection; each sees only its own requested paid prefix. Replay counts/time are distinct from actual native attempts; no new native jobs.'),
        costs=dict(scopes=['historical label attempts including exclusions and failures','baseline/qualification and calibration setup',
            'initial fitting and per-policy inference','paid target refits/conditioning/acquisition','authentication/validation refits',
            'candidate ledger/native command durations','per-candidate CLI and paired query observer','whole collection paired observer','offline replay'],
            rule='Report scopes separately with start/end and failed-attempt costs; overlapping timers cannot be summed. Historical training is not free; any amortization is explicit. Preserve unknown elapsed cost after interruption.'),
        reference=dict(complete_only_if='All12 unique attempts resolved with verified outcomes or classified known-invalid terminal failures; no infrastructure-censored unknowns.',
            censored='Retain best verified feasible reference. Any gap/regret to unresolved full-pool optimum is a lower bound; zero verified-reference gap does not establish complete-pool optimality.',
            oracle='Privileged post-policy scorer only; never selection/model input.'),
        stop_rules=['Any roster/assembly/evidence/dependency/cohort/identity discrepancy stops preparation/release.',
            'If re-extraction or stale fitted artifacts are required, stop; no native or model action is authorized.',
            'No dispatch until separate complete model/controller release, independent review and root measurement decision.'],
        limitations=['Consumed-workload fresh-candidate development, not untouched-workload/family confirmation.',
            'Five seeds are dependent; no significance, calibrated confidence, ML superiority or generalization claim.',
            'Offline64-vector block checks do not establish assembler acceptance, whole-program correctness or hardware feasibility.',
            'Alias identity pass is bounded to16 audited contexts and declared syntax canonicalization; no universal semantic/global-unmeasured assertion.',
            'Broad historical summary-metric exposure is a provenance caveat only, never a pool or policy selection input.'])


def build(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    require(output.parent==(root/PREREG).resolve() and not output.exists(), 'Fresh direct preparation subdirectory required')
    data=read_public_inputs(root)
    snapshots,policies=recipe_snapshot({name:(root/name).read_text() for name in RECIPE_SOURCES},data['audit'])
    dependencies=dict(python=platform.python_version(),packages={name:importlib.metadata.version(name) for name in PACKAGES})
    result=contract(data,snapshots,policies,dependencies)
    result['preparation_builder_sha256']=sha(root/SOURCE)
    output.mkdir()
    for name,value in (('controller-contract.json',result),('id-remap.json',result['id_remap']),
                       ('recipe-source-snapshots.json',snapshots)):
        path=output/name;path.write_bytes(encoded(value)+b'\n')
        path.with_name(name+'.sha256').write_text(sha(path)+'\n')
    (output/'README.md').write_text('# MD5 zero-label controller preparation\n\n'
        'Preparation only: dispatch=false, model_artifacts_created=false, measurement_authorization=false.\n\n'
        'See [contract](controller-contract.json), [explicit ID remap](id-remap.json), '
        '[source/settings snapshots](recipe-source-snapshots.json), and [prior roster](../roster.json). '
        'No runtime dispatcher or fitted model is created. The old pool seal grants no authority.\n')
    manifest={p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    path=output/'artifact-manifest.json';path.write_bytes(encoded(manifest)+b'\n')
    path.with_name(path.name+'.sha256').write_text(sha(path)+'\n')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/PREREG/'controller-preparation-v1')
    args=parser.parse_args(argv)
    value=build(ROOT,args.output)
    print(json.dumps({key:value[key] for key in ('status','candidate_dispatch_enabled','model_artifacts_created','measurement_authorization')}))


if __name__=='__main__':
    main()
