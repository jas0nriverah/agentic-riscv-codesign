#!/usr/bin/env python3
"""New32training plusfixed128freshpool;300s shared native."""
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
SPEC=importlib.util.spec_from_file_location('_boundary_coverage_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
TRAIN=ROOT/'results/boundary-coverage-data'
OUT=ROOT/'results/boundary-coverage-validation'
POLICY={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
PROOF_SEEDS={'train':2026111103,'test':2026111104}
PARAMETERS=((3,17,1),(13,47,1),(29,109,1),(101,293,1),(3,17,3),(13,47,3),(29,109,3),(101,293,3))
TRAIN_VALUES=GENERAL_VALUES=(1,3,7,31)
TRAIN_TEMPLATES=(
 ('sharing_anddata_orcontrol','xor(add(sra(addi(xori(and(in0,in1),31),97),andi(or(in0,in1),{k})),in1),xor(in0,in1))'),
 ('sharing_ordata_andcontrol','xor(add(sra(xori(addi(or(in0,in1),97),31),andi(and(in0,in1),{k})),in0),xor(in0,in1))'),
 ('sharing_xordata_addcontrol','xor(add(sra(addi(xori(xor(in0,in1),31),97),andi(add(in0,in1),{k})),in0),or(in0,in1))'),
 ('sharing_plain_input_orroot','xor(add(sra(xori(addi(in0,97),31),andi(xori(in1,31),{k})),in1),or(in0,in1))'),
 ('narrow_signed8_orroot','xor(add(sra(slli(andi(addi(xori(in0,31),97),255),24),andi(xori(in1,31),{k})),in1),or(in0,in1))'),
 ('narrow_signed16_xoradd','xor(add(sra(slli(andi(xori(addi(xor(in0,in1),97),31),65535),16),andi(in0,{k})),xor(in0,in1)),in1)'),
 ('narrow_sign8_before_add','xor(add(sra(addi(slli(andi(xori(in1,31),255),24),97),andi(or(in0,in1),{k})),or(in0,in1)),xor(in0,in1))'),
 ('narrow_sign16_before_xor','xor(add(sra(xori(slli(andi(addi(and(in0,in1),97),65535),16),31),andi(add(in0,in1),{k})),add(in0,in1)),xor(in0,in1))'),
)
GENERAL_TEMPLATES=(
 ('general_shared_ordata','xor(add(sra(addi(xori(or(in0,in1),19),83),andi(in0,{k})),or(in0,in1)),xor(in0,in1))'),
 ('general_shared_anddata','xor(add(sra(xori(addi(and(in0,in1),83),19),andi(or(in0,in1),{k})),or(in0,in1)),and(in0,in1))'),
 ('general_existing_scope_xorcontrol','xor(add(sra(addi(xori(in0,19),83),andi(xor(in0,in1),{k})),xor(in0,in1)),in1)'),
 ('general_signed8_ordata','xor(add(sra(slli(andi(xori(addi(or(in0,in1),83),19),255),24),andi(in1,{k})),in0),or(in0,in1))'),
 ('general_signed16_andcontrol','xor(add(sra(slli(andi(addi(xori(in1,19),83),65535),16),andi(and(in0,in1),{k})),and(in0,in1)),in0)'),
 ('general_existing_scope_xordata','xor(add(sra(addi(xori(xor(in0,in1),19),83),andi(in1,{k})),and(in0,in1)),in0)'),
)
CONTROL_TEMPLATES=(
 ('control_low16_xor_dualadd','xor(sra(xori(addi(andi(and(in0,in1),65535),83),19),andi(in1,{k})),add(in0,in1))'),
 ('control_wrappedxor_add_or','add(sra(xor(addi(xori(in1,19),83),in0),andi(and(in0,in1),{k})),or(in0,in1))'),
 ('control_unsigned_ordata','xor(add(srl(addi(xori(or(in0,in1),19),83),andi(in0,{k})),in1),and(in0,in1))'),
 ('control_static_signed8','xor(add(srai(slli(andi(addi(xori(in1,19),83),255),24),{k}),in0),or(in0,in1))'),
)
CHALLENGE_TEMPLATES=(
 ('challenge_share_and_or','xor(add(sra(addi(xori(and(in0,in1),{c}),{d}),andi(or(in0,in1),{k})),or(in0,in1)),xor(in0,in1))'),
 ('challenge_share_or_and','xor(add(sra(xori(addi(or(in0,in1),{d}),{c}),andi(and(in0,in1),{k})),and(in0,in1)),or(in0,in1))'),
 ('challenge_share_xor_input','xor(add(sra(addi(xori(xor(in0,in1),{c}),{d}),andi(in1,{k})),xor(in0,in1)),and(in0,in1))'),
 ('challenge_share_xor_and','xor(add(sra(xori(addi(xor(in0,in1),{d}),{c}),andi(in0,{k})),and(in0,in1)),or(in0,in1))'),
 ('challenge_share_or_xor','xor(add(sra(addi(xori(or(in0,in1),{c}),{d}),andi(xor(in0,in1),{k})),in1),or(in0,in1))'),
 ('challenge_share_and_add','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(add(in0,in1),{k})),or(in0,in1)),and(in0,in1))'),
 ('challenge_signed8_oradd','xor(add(sra(slli(andi(addi(xori(in0,{c}),{d}),255),24),andi(in1,{k})),or(in0,in1)),in0)'),
 ('challenge_signed16_androot','xor(add(sra(slli(andi(xori(addi(in1,{d}),{c}),65535),16),andi(in0,{k})),in0),and(in0,in1))'),
 ('challenge_signed8_xordata','xor(add(sra(slli(andi(addi(xori(xor(in0,in1),{c}),{d}),255),24),andi(and(in0,in1),{k})),xor(in0,in1)),in1)'),
 ('challenge_signed8_preadd','xor(add(sra(addi(slli(andi(xori(and(in0,in1),{c}),255),24),{d}),andi(or(in0,in1),{k})),and(in0,in1)),xor(in0,in1))'),
 ('challenge_signed16_prexor','xor(add(sra(xori(slli(andi(addi(or(in0,in1),{d}),65535),16),{c}),andi(in1,{k})),or(in0,in1)),in0)'),
 ('challenge_low16_sharedxor','xor(add(sra(addi(xori(andi(xor(in0,in1),65535),{c}),{d}),andi(or(in0,in1),{k})),xor(in0,in1)),or(in0,in1))'),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def training_candidates():
    rows=[]
    for name,template in TRAIN_TEMPLATES:
        for k in TRAIN_VALUES:
            f=parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id':'boundary-coverage-train:'+prior.sha_bytes(f.encode()),'formula':f,'template':name,'parameter':k})
    need(len(rows)==len({r['formula'] for r in rows})==32,'Exact32noveltraining required')
    return rows

def pool_candidates():
    rows=[]
    def append(formula,template,parameter,cohort,control=False):
        f=parse_formula(formula).canonical()
        rows.append({'candidate_id':'boundary-coverage-pool:'+prior.sha_bytes(f.encode()),
                     'formula':f,'template':template,'parameter':parameter,'cohort':cohort,
                     'pool_index':len(rows),'reserved_control':control})
    for name,template in GENERAL_TEMPLATES:
        for k in GENERAL_VALUES:append(template.format(k=k),name,k,'general')
    for name,template in CONTROL_TEMPLATES:
        for k in (1,3):append(template.format(k=k),name,k,'general',True)
    for name,template in CHALLENGE_TEMPLATES:
        for c,d,k in PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],'challenge')
    need(len(rows)==len({r['formula'] for r in rows})==128,'Exact unique fixed128pool required')
    return rows

def selected():
    seal=read(OUT/'selection.json');indices=seal['selected_pool_indices'];pool=read(OUT/'pool-candidates.json')
    need(32<=len(indices)<=48 and len(indices)==len(set(indices)),'General32 plus at most16active required')
    need(indices[:32]==list(range(32)),'All fixed general32 must lead selected order')
    need(all(type(i) is int and 0<=i<len(pool) for i in indices),'Valid selected pool indices required')
    rows=[pool[i] for i in indices]
    need(read(OUT/'candidates.json')==rows,'Selected candidates differ from exact pool subset')
    need(sum(r['reserved_control'] for r in rows)==8,'All8 fixed controls required')
    need({r['pool_index'] for r in rows if r['reserved_control']}=={r['pool_index'] for r in pool if r['reserved_control']},'Reserved controls changed')
    full=read(OUT/'pool-features.json');subset=read(OUT/'features.json')
    need(subset=={'columns':full['columns'],'records':[full['records'][i] for i in indices]},'Selected features differ from exact pool subset')
    return rows

def inventory():
    paths=[ROOT/'results/boundary-refinement-validation'/n for n in ('historical-formulas.json','pool-candidates.json','candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

def draft_novelty():
    history,paths=inventory();known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history};train_skeletons={skeleton(r['formula']) for r in training_candidates()};seen=set();reports={'train':[],'test':[]}
    from isaforge.semantic_features_v7 import analyze_modes,Budget
    for kind,rows in [('train',training_candidates()),('test',pool_candidates())]:
        for row in rows:
            modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500))
            forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
            keys=set().union(*(prior.identity_keys(f) for f in forms))
            reports[kind].append({'candidate_id':row['candidate_id'],'forms':sorted(forms),
                'historical_identity_overlap':sorted(keys&known),'within_identity_overlap':sorted(keys&seen),
                'historical_skeleton_overlap':skeleton(row['formula']) in old_skeletons,
                'train_test_skeleton_overlap':kind=='test' and skeleton(row['formula']) in train_skeletons})
            seen.update(keys)
    return history,paths,reports

def prepare():
    need(not TRAIN.exists() and not OUT.exists(),'Fresh directories required')
    history,paths,reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap'] for rs in reports.values() for r in rs),'Input-only collision; stop before freeze/native jobs')
    write(TRAIN/'candidates.json',training_candidates());write(OUT/'pool-candidates.json',pool_candidates())
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    for kind,dest in [('train',TRAIN),('test',OUT)]:
        write(dest/'historical-formulas.json',history);write(dest/'tools.json',tools)
        write(dest/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':160,'previous_latest_consumed_count':128,'comparisons':reports[kind],
              'scope':'Canonical,commutativeV4,V4/V5identities,V7aliases and original constant-erasedASTs againstallprior including all128+200previouslabelled/unlabelledpoolrows; jointtraining/testidentity and skeletonscreens. Finite screens,not exhaustiveequivalence orapplicationindependence.'})
    sources=[Path(__file__),RUNNER,ROOT/'scripts/boundary_coverage_features.py',ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_boundary_coverage.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'boundary-coverage-train32-pool128-v1','frozen_at_utc':now(),'policy':POLICY,
          'training_count':32,'training_sharing_count':16,'training_narrow_count':16,'pool_count':128,'general_count':32,'general_inroute_count':24,'general_learning_scope_count':16,'general_existing_scope_only_count':8,'general_control_count':8,'challenge_pool_count':96,'maximum_selected_count':48,'all_pool_rows_consumed_for_future_novelty':True,
          'training_templates':TRAIN_TEMPLATES,'training_parameter_sequence':TRAIN_VALUES,'general_templates':GENERAL_TEMPLATES,'general_parameter_sequence':GENERAL_VALUES,'challenge_templates':CHALLENGE_TEMPLATES,'challenge_parameter_sequence':PARAMETERS,'control_templates':CONTROL_TEMPLATES,'control_parameter_sequence':[1,3],'proof_random_seeds':PROOF_SEEDS,
          'design_assumptions':'Input-only32training=16Booleaninputsharing(4plaininput,4ANDdata,4ORdata,4XORdata)+16signed8/16narrow/sign-placementcompounds. All8trainingfamilies spanmasks1/3/7/31,includingwide-shiftandpost-addhigh-costcontrasts;notonlycheapcircuits,nocostguarantee. Newgeneral32fixed16newlearning-scope+8existing-structural-only+8outside-familycontrasts;challenge96novelsharing/narrowfamilieswithlowmasks. No consumedlabelsfit;everytraininginput/representation/fitlimit frozenbeforelabels. No synthesisfiltering,replacements,extensionorretries.',
          'selection_rule':'Allgeneral32alwayslabelledfirstinpoolorder. Up to16challenge rows inside the frozen learned scope with NEW actual cap correction candidate<=cap<previous_structural (not vsrelease and not inheritedmedian changes);roundrobinsortedtemplatesandfixedparameterorder. Reservegeneralfeaturekeys;excludehistory/train/general andwithinpool217/augmentedfeaturecollisions per prospectivelyboundmodelprotocol. General/historycollisionblockswithoutreplacement. Coverage>=4activelearnedcorrectionsacross>=2templatesand>=1cap128correction. Noquotafill.',
          'success_rule':'One matchedpair217/217+16AST forestfits preregisteredseparatelybeforetraininglabels;finitecandidatehierarchy,gatesandroutingboundinmodelprotocol,no postlabelsearch. General32,conditionalactive+SAME8generalcontrols,andactive-onlygates evaluatedseparately,nopooledsuccess orindependenceclaimforsharedcontrols. All128points/selection frozenbeforefreshlabels.',
          'chronology':'Jointtraining+freshinput/protocolfreezeandindependentpreflight;all160label-freenativefeatures;independentpretrainreceipt;original32trainingRTLproof+labels;matchedfitsanddevelopmentselection;all128orderedpoints/featurecollisions/selection/subsetfreeze;independentprelabelreceipt;allselectedfreshoriginalRTLproof+labels.',
          'native_accounting':'Sumelapsedwalltimeall32train+128poolfeatures,trainverification/labels,andselectedfreshverification/labels includingstartup/extraction/synthesis/failures;shared300s,max2workers,nooverlappingstages. Audit/fittingidleexcluded.',
          'missing_rule':'Retainall32training+128poolrows/features/pointsandallselectedlabels/failures;no retries,replacements,extensions,orcompletecohortprimarywithmissingcases.',
          'scope':'ExperimentalBooleansharing/narrowsignedsyntheticcoverage;fixedgeneral32andseparateconditionalchallengeonly,no unbiasedapplicationtransfer,calibratedbound,timing,power,fullcoreorCPUclaim.',
          'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{str(p.relative_to(ROOT)):sha(p) for dest in (TRAIN,OUT) for p in sorted(dest.iterdir()) if p.is_file()},
          'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(TRAIN/'plan.json',plan);write(OUT/'plan.json',plan);return plan

def validate():
    p=read(TRAIN/'plan.json');need(read(OUT/'plan.json')==p and p['policy']==POLICY,'Jointfrozenprotocolchanged')
    need(read(TRAIN/'candidates.json')==training_candidates() and read(OUT/'pool-candidates.json')==pool_candidates(),'Frozencohortchanged')
    for section in ('sources','inputs','prior_inventory_sources'):
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

def run(stage):
    validate();native.receipt(TRAIN/'preflight-audit.json');feature=stage=='features';training=stage!='test-labels';dest=TRAIN if training else OUT
    attempt=TRAIN/'feature-attempt.json' if feature else dest/'label-attempt.json';need(not attempt.exists(),'Singleattemptonly;noretries')
    used=0 if feature else read(TRAIN/('feature-completion.json' if training else 'completion.json'))['total_native_elapsed_seconds']
    if not feature:
        need(read(TRAIN/'feature-completion.json')['complete'],'Completefeaturesrequired')
        native.receipt(TRAIN/'pretrain-audit.json' if training else OUT/'prelabel-audit.json')
        if not training:need(read(TRAIN/'completion.json')['complete'],'Completetraininglabelsrequired');point_freeze()
    budget=300-used;need(budget>0,'Nativebudgetexhausted');began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'stage':stage,'policy':POLICY,'fits':0})
    def owned(kind,phase,index=None):
        out=TRAIN if kind=='train' else OUT;folder=out/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log';command=[sys.executable,str(Path(__file__).resolve()),'worker','--kind',kind,'--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Sharednativedeadlineexhausted')
            with log.open('x') as stream:
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
        result={'kind':kind,'stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
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
        elapsed=time.monotonic()-began;result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':elapsed,'total_native_elapsed_seconds':used+elapsed,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,'label_count':sum(r['status']=='complete' for r in read(dest/'labels.json')) if (dest/'labels.json').exists() else 0}
        write(dest/('feature-completion.json' if feature else 'completion.json'),result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['draft','prepare','features','train-labels','test-labels','worker','pack']);p.add_argument('--kind',choices=['train','test'],default='train');p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args();configure_runner()
    if a.command=='draft':
        history,paths,reports=draft_novelty();r={'historical_count':len(history),'collisions':[r for rs in reports.values() for r in rs if r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap']]}
    elif a.command=='prepare':r=prepare()
    elif a.command=='worker':worker(a.kind,a.stage,a.index);return
    elif a.command=='pack':r=native.pack(a.kind)
    else:r=run(a.command)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
