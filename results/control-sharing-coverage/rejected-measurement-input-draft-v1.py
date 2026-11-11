#!/usr/bin/env python3
"""New targeted control/shared-AND32 and fixedfresh96;300 summed worker seconds."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import validate_selected_features as prior
from isaforge.features import parse_formula
from isaforge import area_model_v6 as v6
RUNNER=ROOT/'scripts/measure_guarded_revision.py'
SPEC=importlib.util.spec_from_file_location('_control_sharing_coverage_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
TRAIN=ROOT/'results/control-sharing-coverage-data'
OUT=ROOT/'results/control-sharing-coverage-validation'
POLICY={'total_native_seconds': 300, 'workers': 2, 'fits': 0, 'retries': 0, 'replacement_candidates': 0, 'random_vectors': 2048, 'vectors_per_formula': 2148, 'caps_lut4': [32, 64, 128], 'budget_accounting': 'summed_worker_process_seconds', 'stage_wall_safety_reserve_seconds': 1.0}
PROOF_SEEDS={'train':2026111109,'test':2026111110}
TRAIN_PARAMETERS=((3,17,1),(19,67,3),(59,173,7),(167,389,31))
PARAMETERS=((5,29,1),(17,71,1),(41,139,1),(157,347,1),(5,29,3),(17,71,3),(41,139,3),(157,347,3))
FIXED_PARAMETERS=((5,29,1),(41,139,3))
GENERAL_VALUES=(1,3,7,31)
TRAIN_TEMPLATES=(
 ('and_control_plain_othercomplement','xor(add(sra(addi(xori(in0,{c}),{d}),andi(and(in0,xori(srli(in1,1),7)),{k})),in1),in0)'),
 ('and_control_plain_datacomplement','xor(add(sra(xori(addi(in1,{d}),{c}),andi(and(xori(in1,7),srai(in0,1)),{k})),in0),in1)'),
 ('and_control_signed8','xor(add(sra(slli(andi(addi(xori(in0,{c}),{d}),255),24),andi(and(xori(in1,7),in0),{k})),in1),in0)'),
 ('and_control_signed16_preadd','xor(add(sra(addi(slli(andi(xori(in1,{c}),65535),16),{d}),andi(and(xori(in0,7),srli(in1,1)),{k})),in0),in1)'),
 ('shared_and_full_xori_addi','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(xori(srli(in0,1),7),{k})),and(in0,in1)),and(in0,in1))'),
 ('shared_and_full_addi_xori','xor(add(sra(addi(xori(and(in0,in1),{c}),{d}),andi(addi(srai(in1,2),5),{k})),and(in0,in1)),and(in0,in1))'),
 ('shared_and_signed8_postadd','xor(add(sra(slli(andi(xori(addi(and(in0,in1),{d}),{c}),255),24),andi(xori(in0,7),{k})),and(in0,in1)),and(in0,in1))'),
 ('shared_and_signed16_preadd','xor(add(sra(addi(slli(andi(xori(and(in0,in1),{c}),65535),16),{d}),andi(xori(in1,7),{k})),and(in0,in1)),and(in0,in1))'),
)
GENERAL_TEMPLATES=(
 ('general_andcontrol_full','xor(add(sra(xori(addi(in1,97),23),andi(and(xori(srli(in0,1),7),in1),{k})),in0),in1)'),
 ('general_andcontrol_signed8','xor(add(sra(slli(andi(xori(addi(in0,97),23),255),24),andi(and(xori(in1,7),srli(in0,1)),{k})),in1),in0)'),
 ('general_andcontrol_ordata','xor(add(sra(addi(xori(or(in0,in1),23),97),andi(and(xori(in0,7),srli(in1,1)),{k})),in1),in0)'),
 ('general_sharedand_xori_addi','xor(add(sra(xori(addi(and(in0,in1),97),23),andi(xor(srli(in1,1),in1),{k})),and(in0,in1)),and(in0,in1))'),
 ('general_sharedand_addi_xori','xor(add(sra(addi(xori(and(in0,in1),23),97),andi(xor(srai(in0,2),in0),{k})),and(in0,in1)),and(in0,in1))'),
 ('general_sharedand_signed16_prexor','xor(add(sra(xori(slli(andi(addi(and(in0,in1),97),65535),16),23),andi(xori(in1,7),{k})),and(in0,in1)),and(in0,in1))'),
)
CONTROL_TEMPLATES=(
 ('control_unsigned_andcontrol','xor(add(srl(xori(addi(in1,97),23),andi(and(xori(in0,7),srli(in1,1)),{k})),in0),in1)'),
 ('control_static_andsharing','xor(add(srai(xori(addi(and(in0,in1),97),23),{k}),and(in0,in1)),and(in0,in1))'),
 ('control_rootadd_sharedand','add(sra(addi(xori(and(in0,in1),23),97),andi(xor(srli(in1,1),in0),{k})),and(in0,in1))'),
 ('control_directxor_sra','xor(sra(xori(addi(and(in0,in1),97),23),andi(and(in0,srli(in1,1)),{k})),and(in0,in1))'),
)
SHARING_TEMPLATES=(
 ('sharing_and_full_signedcontrol','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(xor(srai(in1,1),in1),{k})),and(in0,in1)),and(in0,in1))'),
 ('sharing_and_signed8','xor(add(sra(addi(slli(andi(xori(and(in0,in1),{c}),255),24),{d}),andi(xor(srli(in0,1),in0),{k})),and(in0,in1)),and(in0,in1))'),
 ('sharing_xor_full','xor(add(sra(xori(addi(xor(in0,in1),{d}),{c}),andi(and(in0,srli(in1,1)),{k})),xor(in0,in1)),or(in0,in1))'),
 ('sharing_xor_low16_preadd','xor(add(sra(addi(xori(andi(xor(in0,in1),65535),{c}),{d}),andi(xori(srai(in0,1),7),{k})),xor(in0,in1)),or(in0,in1))'),
)
LEGACY_TEMPLATES=(
 ('legacy_and_signed16_repeat','xor(add(sra(slli(andi(xori(addi(and(in0,in1),{d}),{c}),65535),16),andi(xor(srli(in0,1),in0),{k})),and(in0,in1)),or(in0,in1))'),
 ('legacy_xor_signed8_preadd_repeat','xor(add(sra(addi(slli(andi(xori(xor(in0,in1),{c}),255),24),{d}),andi(xor(srai(in1,1),in1),{k})),xor(in0,in1)),and(in0,in1))'),
 ('legacy_and_low16_preadd','xor(add(sra(xori(addi(andi(and(in0,in1),65535),{d}),{c}),andi(and(xori(in0,7),srli(in1,1)),{k})),in1),or(in0,in1))'),
 ('legacy_signed8_outerinput','xor(add(sra(slli(andi(addi(xori(in0,{c}),{d}),255),24),andi(xori(srli(in1,1),7),{k})),in1),in0)'),
)
CHALLENGE_TEMPLATES=(
 ('challenge_andcontrol_full','xor(add(sra(addi(xori(in1,{c}),{d}),andi(and(in1,xori(srai(in0,1),7)),{k})),in0),in1)'),
 ('challenge_andcontrol_signed8','xor(add(sra(slli(andi(xori(addi(in1,{d}),{c}),255),24),andi(and(xori(in0,7),srai(in1,1)),{k})),in0),in1)'),
 ('challenge_andcontrol_signed16','xor(add(sra(addi(slli(andi(xori(in0,{c}),65535),16),{d}),andi(and(xori(in1,7),srli(in0,1)),{k})),in1),in0)'),
 ('challenge_sharedand_full','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(xor(srli(in0,1),in0),{k})),and(in0,in1)),and(in0,in1))'),
 ('challenge_sharedand_alternate','xor(add(sra(addi(xori(and(in0,in1),{c}),{d}),andi(xor(srai(in1,2),in1),{k})),and(in0,in1)),and(in0,in1))'),
 ('challenge_sharedand_signed16','xor(add(sra(slli(andi(addi(xori(and(in0,in1),{c}),{d}),65535),16),andi(xor(srli(in1,2),in1),{k})),and(in0,in1)),and(in0,in1))'),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def training_candidates():
    rows=[]
    for name,template in TRAIN_TEMPLATES:
        for c,d,k in TRAIN_PARAMETERS:
            f=parse_formula(template.format(c=c,d=d,k=k)).canonical()
            rows.append({'candidate_id':'control-sharing-train:'+prior.sha_bytes(f.encode()),'formula':f,'template':name,'parameter':[c,d,k]})
    need(len(rows)==len({r['formula'] for r in rows})==32,'Exact32noveltraining required')
    return rows

def pool_candidates():
    rows=[]
    def append(formula,template,parameter,cohort,control=False):
        f=parse_formula(formula).canonical()
        rows.append({'candidate_id':'control-sharing-pool:'+prior.sha_bytes(f.encode()),'formula':f,'template':template,'parameter':parameter,'cohort':cohort,'pool_index':len(rows),'reserved_control':control})
    for name,template in GENERAL_TEMPLATES:
        for k in GENERAL_VALUES:append(template.format(k=k),name,k,'general')
    for name,template in CONTROL_TEMPLATES:
        for k in (1,3):append(template.format(k=k),name,k,'general',True)
    for cohort,templates in [('sharing',SHARING_TEMPLATES),('legacy',LEGACY_TEMPLATES)]:
        for name,template in templates:
            for c,d,k in FIXED_PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],cohort)
    for name,template in CHALLENGE_TEMPLATES:
        for c,d,k in PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],'challenge')
    need(len(rows)==len({r['formula'] for r in rows})==96,'Exact unique fixed96pool required')
    return rows

def selected():
    seal=read(OUT/'selection.json');indices=seal['selected_pool_indices'];pool=read(OUT/'pool-candidates.json')
    need(48<=len(indices)<=64 and len(indices)==len(set(indices)),'Fixedgeneral32+sharing8+legacy8 plus at most16active required')
    need(indices[:48]==list(range(48)),'All fixedgeneral32+sharing8+legacy8 must lead selected order')
    need(all(type(i) is int and 0<=i<len(pool) for i in indices),'Valid selected pool indices required')
    rows=[pool[i] for i in indices]
    need(read(OUT/'candidates.json')==rows,'Selected candidates differ from exact pool subset')
    need(sum(r['reserved_control'] for r in rows)==8,'All8 fixed controls required')
    need({r['pool_index'] for r in rows if r['reserved_control']}=={r['pool_index'] for r in pool if r['reserved_control']},'Reserved controls changed')
    full=read(OUT/'pool-features.json');subset=read(OUT/'features.json')
    need(subset=={'columns':full['columns'],'records':[full['records'][i] for i in indices]},'Selected features differ from exact pool subset')
    return rows

def inventory():
    paths=[ROOT/'results/boundary-feasibility-validation'/n for n in ('historical-formulas.json','pool-candidates.json','candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

MASK=(1<<32)-1

def modular_normalize(node):
 """Two sound decoded-RV32 identities; intentionally not exhaustive equivalence."""
 if not isinstance(node,tuple):return node
 op,args=node;args=tuple(modular_normalize(x) for x in args)
 if op=='addi' and isinstance(args[1],int) and isinstance(args[0],tuple) and args[0][0]=='addi' and isinstance(args[0][1][1],int):
  return modular_normalize(('addi',(args[0][1][0],(args[0][1][1]+args[1])&MASK)))
 if op=='andi' and isinstance(args[1],int) and args[1]>0 and args[1]&(args[1]+1)==0 and isinstance(args[0],tuple) and args[0][0]=='addi' and isinstance(args[0][1][1],int) and args[0][1][1]%(args[1]+1)==0:
  return modular_normalize(('andi',(args[0][1][0],args[1])))
 return op,args


def formula_string(node):
 if not isinstance(node,tuple):return str(node)
 return node[0]+'('+','.join(formula_string(n) for n in node[1])+')'


def formula_tree(formula):
 def convert(n):return (n.value,tuple(convert(c) for c in n.children)) if n.children else n.value
 return convert(parse_formula(formula))

def modular_formula(formula):return formula_string(modular_normalize(formula_tree(formula)))


def draft_novelty():
    history,paths=inventory();known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history};mh={modular_formula(f) for f in history};ms={skeleton(f) for f in mh};mk=set().union(*(prior.identity_keys(f) for f in mh));mod_seen=set();train_skeletons={skeleton(r['formula']) for r in training_candidates()};seen=set();reports={'train':[],'test':[]}
    from isaforge.semantic_features_v7 import analyze_modes,Budget
    for kind,rows in [('train',training_candidates()),('test',pool_candidates())]:
        for row in rows:
            modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500))
            forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
            keys=set().union(*(prior.identity_keys(f) for f in forms));mf=modular_formula(row['formula']);keys_mod=prior.identity_keys(mf)
            reports[kind].append({'candidate_id':row['candidate_id'],'forms':sorted(forms),
                'historical_identity_overlap':sorted(keys&known),'within_identity_overlap':sorted(keys&seen),
                'historical_skeleton_overlap':skeleton(row['formula']) in old_skeletons,
                'train_test_skeleton_overlap':kind=='test' and skeleton(row['formula']) in train_skeletons,'modular_normalized_formula':mf,'historical_modular_skeleton_overlap':skeleton(mf) in ms,'historical_modular_identity_overlap':sorted(keys_mod&mk),'joint_modular_identity_overlap':sorted(keys_mod&mod_seen)})
            seen.update(keys);mod_seen.update(keys_mod)
    return history,paths,reports

def profile_audit():
    """Same-chain input-only profile coverage, never consumed labels in fitting."""
    from collections import Counter
    import boundary_carry_features as block
    def profiles(formula):
        result=[]
        for data,control,post,outer in block.chains(formula):
            both=any(n.value=='and' and all(block.dependencies(c) for c in n.children) and set().union(*(block.dependencies(c) for c in n.children))=={'in0','in1'} for n in block.walk(control))
            repeat=post.value=='and' and all(block.dependencies(c) for c in post.children) and block.subtree_key(post)==block.subtree_key(outer) and block.nonleaf_subtrees(post)<=block.nonleaf_subtrees(data)
            result.append({'both_input_and_control':both,'repeated_and_data_post_outer':repeat,'control_unknown_bits':block.features(formula)[12],'data_unknown_span':block.unknown_shape(data)[0],
                           'data':data.canonical(),'control':control.canonical(),'post':post.canonical(),'outer':outer.canonical()})
        return result
    diagnosis=ROOT/'results/control-sharing-coverage/prior-coverage-diagnosis.json'
    oldpath=ROOT/'results/boundary-corroboration/training-manifest.json'
    old=read(oldpath)['rows'];new=training_candidates();need(len(old)==1889 and len(new)==32,'Fixed training counts required')
    vectors={name:[tuple(block.features(r['formula'])) for r in rows] for name,rows in [('old1889',old),('new32',new),('combined1921',old+new)]}
    targets=[]
    for row in read(diagnosis)['consumed_failure_examples']:
        f=row['formula'];v=tuple(block.features(f))
        targets.append({'selected_index':row['selected_index'],'formula':f,'features16':list(v),'profiles':profiles(f),'matches':{name:{'first10':sum(x[:10]==v[:10] for x in xs),'full16':xs.count(v)} for name,xs in vectors.items()}})
    result={'schema':'control-sharing-input-profile-audit-v1','created_at_utc':now(),'scope':'Formula-only coverage audit. Consumed failure mechanisms informed the prospective design; no consumed labels are copied/fitted. All new training costs measured only after freeze. Coordinate matches do not establish cost transfer,causation or safety.',
            'sources':{str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'scripts/boundary_carry_features.py',diagnosis,oldpath)},'old_training_count':1889,'new_training_count':32,
            'new_training':[dict(r,features16=block.features(r['formula']),profiles=profiles(r['formula'])) for r in new],
            'cohort_profiles':[dict(r,features16=block.features(r['formula']),profiles=profiles(r['formula'])) for r in pool_candidates()],
            'group_counts':{name:sum(any(p[name] for p in profiles(r['formula'])) for r in new) for name in ('both_input_and_control','repeated_and_data_post_outer')},'consumed_target_profiles':targets}
    target=ROOT/'results/control-sharing-coverage/measurement-input-profile-audit.json'
    if (TRAIN/'plan.json').exists() or (OUT/'plan.json').exists():
        existing=read(target);need({k:v for k,v in existing.items() if k!='created_at_utc'}=={k:v for k,v in result.items() if k!='created_at_utc'},'Frozenprofile audit replay differs');return existing
    write(target,result);return result

def prepare():
    need(not TRAIN.exists() and not OUT.exists(),'Fresh directories required')
    history,paths,reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap'] or r['historical_modular_skeleton_overlap'] or r['historical_modular_identity_overlap'] or r['joint_modular_identity_overlap'] for rs in reports.values() for r in rs),'Input-only collision; stop before freeze/native jobs')
    write(TRAIN/'candidates.json',training_candidates());write(OUT/'pool-candidates.json',pool_candidates())
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    for kind,dest in [('train',TRAIN),('test',OUT)]:
        write(dest/'historical-formulas.json',history);write(dest/'tools.json',tools)
        write(dest/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':128,'previous_latest_consumed_count':128,'comparisons':reports[kind],
              'scope':'Canonical,commutativeV4,V4/V5identities,V7aliases and original constant-erasedASTs againstallprior includingall128latestfeasibilityrows(even72unlabelled),latest56labels,andallolderlabelled/unlabelled128/200pools; jointtraining/testidentity and skeletonscreens. Finite screens,not exhaustiveequivalence orapplicationindependence.'})
    design_audit=ROOT/'results/control-sharing-coverage/measurement-input-profile-audit.json'
    audit=read(design_audit)
    for path,digest in audit['sources'].items():need(sha(ROOT/path)==digest,'Inputprofileaudit binding changed:'+path)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/boundary_carry_features.py',ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_control_sharing_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'control-sharing-train32-pool96-v1','frozen_at_utc':now(),'policy':POLICY,
          'training_count':32,'and_control_training_count':16,'shared_and_training_count':16,'pool_count':96,'general_count':32,'sharing_count':8,'legacy_count':8,'challenge_count':48,'maximum_selected_count':64,'all_pool_rows_consumed_for_future_novelty':True,
          'training_templates':TRAIN_TEMPLATES,'training_parameters':TRAIN_PARAMETERS,'general_templates':GENERAL_TEMPLATES,'general_parameters':GENERAL_VALUES,'control_templates':CONTROL_TEMPLATES,'control_parameters':[1,3],'sharing_templates':SHARING_TEMPLATES,'legacy_templates':LEGACY_TEMPLATES,'sharing_legacy_parameters':FIXED_PARAMETERS,'challenge_templates':CHALLENGE_TEMPLATES,'challenge_parameters':PARAMETERS,'proof_random_seeds':PROOF_SEEDS,
          'design_assumptions':'Fixed32newtraining=16binaryAND-both-inputcontrolcontrasts+16exactsharedANDdata/post/outercontrasts. Eachblock has8fullword+8signed8/16rows; masks1/3/7/31 and low/highimmediates includehighcostcontrasts,withoutcostfiltering. Fresh96=completegeneral32+mandatorysharing8+legacy8+challenge48. Genuinecontrolbit-selection/dependency/data-placement variants,not no-opwrappernovelty. Original/alias/modular/skeletonnovelty required jointlybeforelabels. No target labels/predictions used forinputchoice;no cost/safetyguarantee.',
          'selection_rule':'Fixed48(general32/sharing8/legacy8)alwayslabelled firstinpoolorder. Atmost16NEWcapacceptances versusfrozenfeasibility_augmented,deterministicroundrobinchallenge templates/parameterorder,217/233historical+newtrain+fixed48featurefreshness. Require>=4actions/>=2templates/128,legacy64veto oldabstention,sharing128veto oldlearned217 perboundmodelprotocol. No quotas/refills/extensions/replacements.',
          'success_rule':'ONE fixed233classifierfit on old1889+new32=1921;features/parameters/equalweightnestedoutputs/probability0.5tiepolicy unchanged. Frozen1889classifier reused withoutrefit asbaseline. Allretainedpanels/expandedrepairandrejectiontargets and separatefreshgeneral/sharing/legacy/conditional-full(actions+same8generalcontrols)/active-only hardgates fixedbeforelabels. All96probabilities/selection frozenbeforefreshlabels;no pooledsuccess/sharedcontrolindependenceclaim.',
          'chronology':'Joint32train+96pool/schema/policy/protocolfreeze+independentpreflight+parentauthorization;all128nativefeatures;featurefreshness/pretrainaudit;32originaltrainingRTLproof+labels;onefixedfit/developmentselection;all96points/selection/fixed48+actions<=16freeze+prelabelaudit/parentauthorization;allselectedoriginalRTLproof+labels.',
          'native_accounting':'TRUE SUM of worker process launch-through-reap intervals,includingstartup/extraction/proof/synthesis/failures,shared300worker-seconds,max2workers. Eachstage wall deadline=(remaining summed budget minus1s reserve)/2;reportactualsummedprocess andstagewall separately. Anybudgetoverrunfails. Fit/audit/hostbookkeepingexcluded. No overlappingnative stages.',
          'missing_rule':'Retainall32training+96poolrows/features/probabilitiesandallselectedlabels/failures;noretries,replacements,extensions,orcompletecohortprimarywithmissingcases.',
          'scope':'Uncalibratedtargetedcontrol/sharingcoverageintervention withinfixed233feasibilityclassifier;notrepresentationablation,nounbiasedapplicationtransfer/hardware-safetycertificate/timing/power/fullcoreorCPUclaim.',
          'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{str(p.relative_to(ROOT)):sha(p) for dest in (TRAIN,OUT) for p in sorted(dest.iterdir()) if p.is_file()},
          'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'design_audit_inputs':{str(design_audit.relative_to(ROOT)):sha(design_audit)},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(TRAIN/'plan.json',plan);write(OUT/'plan.json',plan);return plan

def validate():
    p=read(TRAIN/'plan.json');need(read(OUT/'plan.json')==p and p['policy']==POLICY,'Jointfrozenprotocolchanged')
    need(read(TRAIN/'candidates.json')==training_candidates() and read(OUT/'pool-candidates.json')==pool_candidates(),'Frozencohortchanged')
    for section in ('sources','inputs','prior_inventory_sources','design_audit_inputs'):
        for path,digest in p[section].items():need(sha(ROOT/path)==digest,'Frozenbindingchanged:'+path)
    for tool in read(TRAIN/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Toolchanged')
    return p

def point_freeze():
    p=read(OUT/'point-freeze.json');need(p['target_label_jobs']==0 and bool(p['bindings']),'Prelabel point/model freeze required')
    for path,digest in p['bindings'].items():need(sha(ROOT/path)==digest,'Frozen point/model changed:'+path)
    selected()
    return p


def worker(kind,stage,index):
    from collections import Counter
    validate();dest=TRAIN if kind=='train' else OUT
    need((TRAIN/'feature-attempt.json' if stage=='feature' else dest/'label-attempt.json').exists(),'Owned singleattemptrequired')
    rows=training_candidates() if kind=='train' else (pool_candidates() if stage=='feature' else selected())
    if kind=='test' and stage!='feature':point_freeze()
    if stage=='feature':
        row=rows[index];folder=dest/'raw/features'/str(index);tools=read(TRAIN/'tools.json')
        tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
        _,records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1)
        write(folder/'result.json',{**row,**records[0],'status':'complete'});return
    if stage=='verify':
        from isaforge.rtl import verify_rtl_batch
        p=verify_rtl_batch([r['formula'] for r in rows],dest/'raw/verification',random_vectors=2048,seed=PROOF_SEEDS[kind],timeout=180)
        need(p['verified'] is True and p['formula_count']==len(rows) and p['total_comparisons']==2148*len(rows),'CompleteoriginalRTLverificationrequired')
        write(dest/'raw/verification/result.json',p)
    else:
        proof=read(dest/'raw/verification/result.json');need(proof['verified'] and proof['total_comparisons']==2148*len(rows),'OriginalRTLverificationrequired')
        from isaforge.synthesis import run_synthesis
        from isaforge.rtl import generate_rtl
        row=rows[index];folder=dest/'raw/labels'/str(index);metrics=run_synthesis(row['formula'],folder,timeout=120)
        counts=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values())
        need(counts['SB_LUT4']==metrics['ice40_lut4_count'],'LUTrecountdiffers');need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'OriginalRTLdiffers')
        write(folder/'result.json',{**row,'status':'complete','lut4':counts['SB_LUT4'],'carry':counts['SB_CARRY'],'rtl_sha256':metrics['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json'),'measurement_source':'ActualYosys synth_ice40defaults originalRTL;SB_LUT4only'})

def configure_runner():
    native.TRAIN=TRAIN;native.TEST=OUT;native.validate=validate;native.verify_point_freeze=point_freeze
    native.__file__=str(Path(__file__).resolve());return native

def parent_authorization(stage):
    """An explicit parent receipt authorizes only the exact frozen experiment."""
    receipt=read(TRAIN/'parent-authorization.json')
    need(receipt.get('status')=='approved' and receipt.get('approved_by')=='parent','Explicit parent authorization required')
    need(stage in receipt.get('authorized_stages',[]),'Parent has not authorized this native stage')
    need(receipt.get('plan_sha256')==sha(TRAIN/'plan.json'),'Parent authorization plan differs')
    need(receipt.get('protocol_sha256')==sha(ROOT/'results/control-sharing-coverage/protocol.json'),'Parent authorization protocol differs')
    return receipt

def run(stage):
    validate();parent_authorization(stage);native.receipt(TRAIN/'preflight-audit.json');feature=stage=='features';training=stage!='test-labels';dest=TRAIN if training else OUT
    attempt=TRAIN/'feature-attempt.json' if feature else dest/'label-attempt.json';need(not attempt.exists(),'Singleattemptonly;noretries')
    used=0 if feature else read(TRAIN/('feature-completion.json' if training else 'completion.json'))['total_native_elapsed_seconds']
    if not feature:
        need(read(TRAIN/'feature-completion.json')['complete'],'Completefeaturesrequired')
        native.receipt(TRAIN/'pretrain-audit.json' if training else OUT/'prelabel-audit.json')
        if not training:need(read(TRAIN/'completion.json')['complete'],'Completetraininglabelsrequired');point_freeze()
    budget=300-used;reserve=POLICY['stage_wall_safety_reserve_seconds'];need(budget>reserve,'Summednativebudgetexhausted');wall_budget=(budget-reserve)/2;began=time.monotonic();deadline=began+wall_budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'stage':stage,'stage_wall_budget_seconds':wall_budget,'budget_definition':'summed worker process seconds','policy':POLICY,'fits':0})
    def owned(kind,phase,index=None):
        out=TRAIN if kind=='train' else OUT;folder=out/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log';command=[sys.executable,str(Path(__file__).resolve()),'worker','--kind',kind,'--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();job_began=time.monotonic();native_began=None;process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Sharednativedeadlineexhausted')
            with log.open('x') as stream:
                native_began=time.monotonic()
                process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:raise TimeoutError('Sharednativedeadline')
                need(code==0,'Workerfailed:'+str(log))
        except Exception as caught:error=repr(caught)
        finally:
            if process:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        native_elapsed=0.0 if native_began is None else time.monotonic()-native_began
        result={'native_elapsed_seconds':native_elapsed,'job_wall_elapsed_seconds':time.monotonic()-job_began,'kind':kind,'stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
        write(folder/'worker.json',result);jobs.append(result);return result
    def rows_for(kind,phase):return training_candidates() if kind=='train' else (pool_candidates() if phase=='feature' else selected())
    def retained(kind,phase):
        out=TRAIN if kind=='train' else OUT;records=[]
        for i,row in enumerate(rows_for(kind,phase)):
            p=out/'raw'/(phase+'s')/str(i)/'result.json';records.append(read(p) if p.exists() else {**row,'status':'failed','error':'Nocomplete nativeresult;seeretainedevidence'})
        return records
    def batch(kind,phase):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda i:owned(kind,phase,i),range(len(rows_for(kind,phase)))))
        failures.extend(r for r in results if r['error'])
    try:
        if feature:
            for kind,out in [('train',TRAIN),('test',OUT)]:
                batch(kind,'feature');records=retained(kind,'feature');write(out/('features.json' if kind=='train' else 'pool-features.json'),{'columns':list(v6.columns()),'records':records})
                need(len(v6.columns())==336 and all(r['status']=='complete' and len(r['values'])==336 for r in records),'Incomplete336features;noreplacements')
        else:
            kind='train' if training else 'test';proof=owned(kind,'verify')
            if proof['error']:failures.append(proof)
            need(not failures,'OriginalRTLverificationfailed;labelsforbidden');batch(kind,'label');write(dest/'labels.json',retained(kind,'label'))
        need(not failures,'Incompletestage;allfailuresretained;noretries')
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
        if feature:
            for kind,out in [('train',TRAIN),('test',OUT)]:write(out/('features.json' if kind=='train' else 'pool-features.json'),{'columns':list(v6.columns()),'records':retained(kind,'feature')})
        else:write(dest/'labels.json',retained('train' if training else 'test','label'))
    finally:
        elapsed=time.monotonic()-began;summed=sum(r['native_elapsed_seconds'] for r in jobs)
        if used+summed>300:failures.append({'stage':'budget','error':'Summedworkerprocessbudgetexceeded'})
        result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':summed,'total_native_elapsed_seconds':used+summed,'summed_worker_native_seconds':summed,'total_summed_worker_native_seconds':used+summed,'stage_wall_elapsed_seconds':elapsed,'stage_wall_budget_seconds':wall_budget,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,'label_count':sum(r['status']=='complete' for r in read(dest/'labels.json')) if (dest/'labels.json').exists() else 0}
        write(dest/('feature-completion.json' if feature else 'completion.json'),result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['draft','profile-audit','prepare','features','train-labels','test-labels','worker','pack']);p.add_argument('--kind',choices=['train','test'],default='train');p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args();configure_runner()
    if a.command=='draft':
        history,paths,reports=draft_novelty();r={'historical_count':len(history),'collisions':[r for rs in reports.values() for r in rs if r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap'] or r['historical_modular_skeleton_overlap'] or r['historical_modular_identity_overlap'] or r['joint_modular_identity_overlap']]}
    elif a.command=='profile-audit':r=profile_audit()
    elif a.command=='prepare':r=prepare()
    elif a.command=='worker':worker(a.kind,a.stage,a.index);return
    elif a.command=='pack':r=native.pack(a.kind)
    else:r=run(a.command)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
