#!/usr/bin/env python3
"""Fixed general32/sharing8/legacy8/challenge80;zero new training labels."""
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
SPEC=importlib.util.spec_from_file_location('_boundary_feasibility_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
OUT=ROOT/'results/boundary-feasibility-validation'
POLICY={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128],
        'budget_accounting':'summed_worker_process_seconds','stage_wall_safety_reserve_seconds':1.0}
PROOF_SEED=2026111108
PARAMETERS=((11,47,1),(23,97,1),(47,157,1),(163,353,1),(11,47,3),(23,97,3),(47,157,3),(163,353,3))
FIXED_PARAMETERS=((11,47,1),(47,157,3))
GENERAL_VALUES=(1,3,7,31)
GENERAL_TEMPLATES=(
 ('general_and_complement','xor(add(sra(addi(xori(and(in0,in1),29),113),andi(addi(xori(in1,15),2),{k})),in1),or(in0,in1))'),
 ('general_or_complement','xor(add(sra(xori(addi(or(in0,in1),113),29),andi(addi(xori(in0,15),2),{k})),in0),xor(in0,in1))'),
 ('general_signed8_preadd','xor(add(sra(addi(slli(andi(xori(and(in0,in1),29),255),24),113),andi(addi(xori(addi(in0,5),15),2),{k})),in1),and(in0,in1))'),
 ('general_signed8_postadd','xor(add(sra(slli(andi(addi(xori(in1,29),113),255),24),andi(addi(addi(in0,9),2),{k})),in1),or(in0,in1))'),
 ('general_plain_outerinput','xor(add(sra(xori(addi(in1,113),29),andi(addi(addi(in0,9),2),{k})),in0),in1)'),
 ('general_signed16_preadd_outerinput','xor(add(sra(addi(slli(andi(xori(in1,29),65535),16),113),andi(addi(xori(in0,15),2),{k})),in0),in1)'),
)
CONTROL_TEMPLATES=(
 ('control_wrappedxor_rootadd','add(sra(xor(xori(addi(in1,113),29),in0),andi(addi(xori(in0,15),2),{k})),and(in0,in1))'),
 ('control_low16_dualadd','xor(sra(xori(addi(andi(xor(in0,in1),65535),113),29),andi(addi(xori(in1,15),2),{k})),add(in0,in1))'),
 ('control_unsigned_ordata','xor(add(srl(xori(addi(or(in0,in1),113),29),andi(addi(addi(in1,9),2),{k})),in1),xor(in0,in1))'),
 ('control_static_signed8','xor(add(srai(slli(andi(xori(addi(in0,113),29),255),24),{k}),in0),xor(in0,in1))'),
)
SHARING_TEMPLATES=(
 ('sharing_full_xor','xor(add(sra(addi(xori(xor(in0,in1),{c}),{d}),andi(addi(xori(in1,15),2),{k})),xor(in0,in1)),xor(in0,in1))'),
 ('sharing_low16_beforeadd_xor','xor(add(sra(addi(xori(andi(xor(in0,in1),65535),{c}),{d}),andi(addi(xori(in0,15),2),{k})),xor(in0,in1)),and(in0,in1))'),
 ('sharing_full_and','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(addi(addi(in1,9),2),{k})),and(in0,in1)),and(in0,in1))'),
 ('sharing_signed8_preadd_or','xor(add(sra(addi(slli(andi(xori(or(in0,in1),{c}),255),24),{d}),andi(addi(xori(in0,15),2),{k})),or(in0,in1)),xor(in0,in1))'),
)
LEGACY_TEMPLATES=(
 ('legacy_signed16_and_repeat','xor(add(sra(slli(andi(xori(addi(and(in0,in1),{d}),{c}),65535),16),andi(addi(xori(addi(in0,5),15),2),{k})),and(in0,in1)),or(in0,in1))'),
 ('legacy_or_complement','xor(add(sra(addi(xori(or(in0,in1),{c}),{d}),andi(addi(xori(in1,15),2),{k})),in0),xor(in0,in1))'),
 ('legacy_signed8_preadd_xor_repeat','xor(add(sra(addi(slli(andi(xori(xor(in0,in1),{c}),255),24),{d}),andi(addi(xori(addi(in1,5),15),2),{k})),xor(in0,in1)),and(in0,in1))'),
 ('legacy_signed8_postadd','xor(add(sra(slli(andi(xori(addi(in1,{d}),{c}),255),24),andi(addi(addi(in0,9),2),{k})),in0),or(in0,in1))'),
)
CHALLENGE_TEMPLATES=(
 ('challenge_plain_boolean','xor(add(sra(xori(addi(in0,{d}),{c}),andi(addi(addi(in1,9),2),{k})),in1),xor(in0,in1))'),
 ('challenge_plain_outerinput','xor(add(sra(addi(xori(in1,{c}),{d}),andi(addi(xori(in0,15),2),{k})),in0),in1)'),
 ('challenge_and_complement','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(addi(xori(in1,15),2),{k})),in0),and(in0,in1))'),
 ('challenge_or_complement','xor(add(sra(addi(xori(or(in0,in1),{c}),{d}),andi(addi(xori(in0,15),2),{k})),in1),or(in0,in1))'),
 ('challenge_xor_complement','xor(add(sra(xori(addi(xor(in0,in1),{d}),{c}),andi(addi(addi(in1,9),2),{k})),in0),xor(in0,in1))'),
 ('challenge_signed8_preadd_outerinput','xor(add(sra(addi(slli(andi(xori(in0,{c}),255),24),{d}),andi(addi(addi(in1,9),2),{k})),in1),in0)'),
 ('challenge_signed8_postadd_or','xor(add(sra(slli(andi(xori(addi(or(in0,in1),{d}),{c}),255),24),andi(addi(xori(in0,15),2),{k})),in1),xor(in0,in1))'),
 ('challenge_signed16_preadd_outerinput','xor(add(sra(addi(slli(andi(xori(and(in0,in1),{c}),65535),16),{d}),andi(addi(xori(in1,15),2),{k})),in0),in1)'),
 ('challenge_signed16_postadd_outerinput','xor(add(sra(slli(andi(addi(xori(in1,{c}),{d}),65535),16),andi(addi(addi(in0,9),2),{k})),in1),in0)'),
 ('challenge_signed16_xor_repeat','xor(add(sra(slli(andi(xori(addi(xor(in0,in1),{d}),{c}),65535),16),andi(addi(xori(in0,15),2),{k})),xor(in0,in1)),in1)'),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def pool_candidates():
    rows=[]
    def append(formula,template,parameter,cohort,control=False):
        f=parse_formula(formula).canonical()
        rows.append({'candidate_id':'boundary-feasibility-pool:'+prior.sha_bytes(f.encode()),'formula':f,'template':template,'parameter':parameter,'cohort':cohort,'pool_index':len(rows),'reserved_control':control})
    for name,template in GENERAL_TEMPLATES:
        for k in GENERAL_VALUES:append(template.format(k=k),name,k,'general')
    for name,template in CONTROL_TEMPLATES:
        for k in (1,3):append(template.format(k=k),name,k,'general',True)
    for cohort,templates in [('sharing',SHARING_TEMPLATES),('legacy',LEGACY_TEMPLATES)]:
        for name,template in templates:
            for c,d,k in FIXED_PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],cohort)
    for name,template in CHALLENGE_TEMPLATES:
        for c,d,k in PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],'challenge')
    need(len(rows)==len({r['formula'] for r in rows})==128,'Exact unique fixed128pool required')
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
    paths=[ROOT/'results/boundary-corroboration-data'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    paths += [ROOT/'results/boundary-corroboration-validation'/n for n in ('pool-candidates.json','candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

def draft_novelty():
    history,paths=inventory();known=set().union(*(prior.identity_keys(f) for f in history))
    old_skeletons={skeleton(f) for f in history};seen=set();reports=[]
    from isaforge.semantic_features_v7 import analyze_modes,Budget
    for row in pool_candidates():
        modes=analyze_modes(row['formula'],budget=Budget(proof_timeout_ms=500))
        forms={row['formula'],*(m['normalized_formula'] for m in modes.values())}
        keys=set().union(*(prior.identity_keys(f) for f in forms))
        reports.append({'candidate_id':row['candidate_id'],'forms':sorted(forms),
                        'historical_identity_overlap':sorted(keys&known),'within_identity_overlap':sorted(keys&seen),
                        'historical_skeleton_overlap':skeleton(row['formula']) in old_skeletons})
        seen.update(keys)
    return history,paths,reports

def prepare():
    need(not OUT.exists(),'Fresh directory required')
    history,paths,reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap'] for r in reports),
         'Input-only collision; stop before freeze or native jobs')
    write(OUT/'pool-candidates.json',pool_candidates());write(OUT/'historical-formulas.json',history)
    write(OUT/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':128,
          'previous_latest_consumed_count':160,'comparisons':reports,
          'scope':'Canonical,commutative V4,V4/V5normalized identities,V7aliases and original constant-erased AST skeletons against all-prior including all32newtraining+128prior boundary-corroboration pool rows,even79unlabelled. Finite screens,not exhaustive semantic equivalence or application independence.'})
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(OUT/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/boundary_carry_features.py',ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_boundary_feasibility.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'boundary-feasibility-pool128-v1','frozen_at_utc':now(),'policy':POLICY,
          'new_training_label_count':0,'pool_count':128,'general_count':32,'general_target_count':24,'general_control_count':8,'sharing_count':8,'legacy_count':8,'challenge_count':80,'maximum_selected_count':64,'all_pool_rows_consumed_for_future_novelty':True,
          'general_templates':GENERAL_TEMPLATES,'general_parameters':GENERAL_VALUES,'control_templates':CONTROL_TEMPLATES,'control_parameters':[1,3],'sharing_templates':SHARING_TEMPLATES,'legacy_templates':LEGACY_TEMPLATES,'sharing_legacy_parameters':FIXED_PARAMETERS,'challenge_templates':CHALLENGE_TEMPLATES,'challenge_parameters':PARAMETERS,'proof_random_seed':PROOF_SEED,
          'design_assumptions':'Fixed128 freshinputpool:completegeneral32(24rootclass+8outside),mandatorysharing8,mandatorylegacy8,challenge80. NewASTcompositions add carry-bearing ADDI(+2) to variable shiftcontrol and alter outerBoolean siblings; sign-placement andouter-inputstructures retained. Mask3andwider expose controlcarry. Mandatorylegacy covers narrow16AND/repeatedpostAND andsign8-beforeADDI-XOR/repeatedpostXOR;sharingincludesfullword/high-costandnarrowcontrasts. Newtuples prospectivelyfixed;no nativecost/predictions used forchoice. No cost,safety,orsemantic-independence guarantee.',
          'selection_rule':'Alwayslabel general32+sharing8+legacy8 firstinpoolorder. Atmost16NEWcapacceptances classifier<=cap<latestcorroborated_augmented,roundrobinsortedchallenge templatesandfixedparameterorder;reserveall48fixed217/233keys andexcludehistorical/withinpoolduplicates perboundmodelprotocol. Require>=4actions/>=2templates/128,legacy8>=1veto oldabstention<=64<classifier,sharing8>=1veto oldlearned217<=128<classifier. No quotafill,replacement,extensionorlabelselection.',
          'success_rule':'Zero newtraininglabels;reuseexactfrozen1889orderedtrainingrows/targets fromcorroboration;twofixedmatched217/233multioutputfeasibilityclassifierfits boundseparately. No probability-threshold/grid/featurechanges. Release-first exact0.5tie-accept policyandallretainedhardgates frozenbeforefits/nativejobs. General32/sharing8/legacy8/conditional-full(actions+SAME8generalcontrols)/active-only scoredseparately,full denominators,nopooledsuccess orsharedcontrolindependenceclaim. All128probabilities/selection frozenbeforelabels.',
          'chronology':'Inputs/protocol/schema/classes/policyfreeze+independentpreflight+explicit parent-authorization.json bound to exact plan/protocol beforeanynativejobs/fits;all128nativefeatures;matchedclassifiersfitonlyold1889training;allpoolprobabilities/monotonicity/classmaps/freshness/selection/exactsubsetfreeze;independentprelabel+authorization;allselectedoriginalRTLproof+labels.',
          'native_accounting':'SUM of worker process intervals from launch through reap,including startup/extraction/verification/synthesis/failures,all128features+selectedlabels;shared300worker-seconds,max2workers. Stage wall deadline=(remaining summed budget minus1second safety reserve)/2. Track both actual summed worker time and stage wall time;budget overrun isfailure. Audit/fitting/host-bookkeeping timeexcluded.',
          'missing_rule':'Retainall128poolrows/features/probabilities/pointsandeveryselectedlabel/failure;noretries,replacements,extensions,orcompletecohortprimarywithmissingcases.',
          'scope':'Uncalibratedbudget-feasibilityclassificationonfixedsyntheticgeneral/sharing/legacypanelsandconditionalchallenge. Objectivechangesfromregression;representationablationisolates16columnswithinclassifieronly. No unbiasedgeneralization,hardware-safetycertificate,timing,power,fullcoreorCPUclaim.',
          'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
          'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(OUT/'plan.json',plan);return plan

def validate():
    p=read(OUT/'plan.json');need(p['policy']==POLICY and read(OUT/'pool-candidates.json')==pool_candidates(),'Frozen protocol/cohort changed')
    for section in ('sources','inputs','prior_inventory_sources'):
        for path,digest in p[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed:'+path)
    for tool in read(OUT/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
    return p

def point_freeze():
    p=read(OUT/'point-freeze.json');need(p['target_label_jobs']==0 and bool(p['bindings']),'Prelabel point/model freeze required')
    for path,digest in p['bindings'].items():need(sha(ROOT/path)==digest,'Frozen point/model changed:'+path)
    selected()
    return p


def worker(stage,index):
    from collections import Counter
    validate();need((OUT/('feature-attempt.json' if stage=='feature' else 'label-attempt.json')).exists(),'Owned single attempt required')
    if stage=='feature':
        row=read(OUT/'pool-candidates.json')[index];folder=OUT/'raw/features'/str(index);tools=read(OUT/'tools.json')
        tool={'version':tools['yosys']['version'],'executable_sha256':tools['yosys']['sha256']}
        _,records=v6.FeatureExtractor(folder/'cache',frozen_tool=tool).matrix([{'formula':row['formula']}],workers=1)
        write(folder/'result.json',{**row,**records[0],'status':'complete'})
        return
    point_freeze();rows=selected()
    if stage=='verify':
        from isaforge.rtl import verify_rtl_batch
        p=verify_rtl_batch([r['formula'] for r in rows],OUT/'raw/verification',random_vectors=2048,seed=PROOF_SEED,timeout=180)
        need(p['verified'] is True and p['formula_count']==len(rows) and p['total_comparisons']==2148*len(rows),'Complete selected originalRTL verification required')
        write(OUT/'raw/verification/result.json',p)
    else:
        proof=read(OUT/'raw/verification/result.json')
        need(proof['verified'] and proof['total_comparisons']==2148*len(rows),'Selected originalRTL verification required')
        from isaforge.synthesis import run_synthesis
        from isaforge.rtl import generate_rtl
        row=rows[index];folder=OUT/'raw/labels'/str(index);metrics=run_synthesis(row['formula'],folder,timeout=120)
        counts=Counter(c['type'] for c in read(folder/'ice40-netlist.json')['modules']['candidate']['cells'].values())
        need(counts['SB_LUT4']==metrics['ice40_lut4_count'],'LUT recount differs')
        need((folder/'candidate.v').read_text()==generate_rtl(row['formula']),'Selected originalRTL differs')
        write(folder/'result.json',{**row,'status':'complete','lut4':counts['SB_LUT4'],'carry':counts['SB_CARRY'],
              'rtl_sha256':metrics['rtl_sha256'],'metrics_sha256':sha(folder/'metrics.json'),'netlist_sha256':sha(folder/'ice40-netlist.json'),
              'measurement_source':'Actual Yosys synth_ice40 defaults selected originalRTL;SB_LUT4only'})

def configure_runner():
    native.TRAIN=OUT;native.TEST=OUT;native.validate=validate;native.verify_point_freeze=point_freeze
    native.__file__=str(Path(__file__).resolve());return native

def parent_authorization(stage):
    """An explicit parent receipt authorizes only the exact frozen experiment."""
    receipt=read(OUT/'parent-authorization.json')
    need(receipt.get('status')=='approved' and receipt.get('approved_by')=='parent','Explicit parent authorization required')
    need(stage in receipt.get('authorized_stages',[]),'Parent has not authorized this native stage')
    need(receipt.get('plan_sha256')==sha(OUT/'plan.json'),'Parent authorization plan differs')
    need(receipt.get('protocol_sha256')==sha(ROOT/'results/boundary-feasibility/protocol.json'),'Parent authorization protocol differs')
    return receipt

def run(stage):
    validate();parent_authorization(stage);native.receipt(OUT/'preflight-audit.json');feature=stage=='features'
    attempt=OUT/('feature-attempt.json' if feature else 'label-attempt.json')
    need(not attempt.exists(),'Single attempt only;no retries')
    used=0 if feature else read(OUT/'feature-completion.json')['total_native_elapsed_seconds']
    if not feature:
        need(read(OUT/'feature-completion.json')['complete'],'Complete features required')
        native.receipt(OUT/'prelabel-audit.json');point_freeze()
    rows=pool_candidates() if feature else selected()
    budget=POLICY['total_native_seconds']-used;reserve=POLICY['stage_wall_safety_reserve_seconds']
    need(budget>reserve,'Summed native budget exhausted')
    wall_budget=(budget-reserve)/POLICY['workers']
    began=time.monotonic();deadline=began+wall_budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'stage':stage,'stage_wall_budget_seconds':wall_budget,'budget_definition':'summed worker process seconds','policy':POLICY,'fits':0})
    def owned(phase,index=None):
        folder=OUT/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log'
        command=[sys.executable,str(Path(__file__).resolve()),'worker','--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();job_began=time.monotonic();native_began=None;process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Shared native deadline exhausted')
            with log.open('x') as stream:
                native_began=time.monotonic()
                process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:raise TimeoutError('Shared native deadline')
                need(code==0,'Worker failed:'+str(log))
        except Exception as caught:error=repr(caught)
        finally:
            if process:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        native_elapsed=0.0 if native_began is None else time.monotonic()-native_began
        result={'native_elapsed_seconds':native_elapsed,'job_wall_elapsed_seconds':time.monotonic()-job_began,'kind':'test','stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
        write(folder/'worker.json',result);jobs.append(result);return result
    def retained(phase):
        records=[]
        for i,row in enumerate(rows):
            p=OUT/'raw'/(phase+'s')/str(i)/'result.json'
            records.append(read(p) if p.exists() else {**row,'status':'failed','error':'No complete native result;see retained worker evidence'})
        return records
    phase='feature' if feature else 'label'
    try:
        if not feature:
            proof=owned('verify')
            if proof['error']:failures.append(proof)
            need(not failures,'Original RTL verification failed;labels forbidden')
        with ThreadPoolExecutor(max_workers=POLICY['workers']) as pool:results=list(pool.map(lambda i:owned(phase,i),range(len(rows))))
        failures.extend(r for r in results if r['error']);records=retained(phase)
        if feature:
            write(OUT/'pool-features.json',{'columns':list(v6.columns()),'records':records})
            need(len(v6.columns())==336 and all(r['status']=='complete' and len(r['values'])==336 for r in records),'Incomplete336features;no replacements')
        else:write(OUT/'labels.json',records)
        need(not failures,'Incomplete stage;every failure retained;no retries or replacements')
    except Exception as error:
        failures.append({'stage':'attempt','error':repr(error)})
        write(OUT/('pool-features.json' if feature else 'labels.json'),{'columns':list(v6.columns()),'records':retained(phase)} if feature else retained(phase))
    finally:
        elapsed=time.monotonic()-began
        summed=sum(r['native_elapsed_seconds'] for r in jobs)
        if used+summed>POLICY['total_native_seconds']:failures.append({'stage':'budget','error':'Summed worker process budget exceeded'})
        result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':summed,'total_native_elapsed_seconds':used+summed,'summed_worker_native_seconds':summed,'total_summed_worker_native_seconds':used+summed,'stage_wall_elapsed_seconds':elapsed,'stage_wall_budget_seconds':wall_budget,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,'label_count':sum(r['status']=='complete' for r in read(OUT/'labels.json')) if (OUT/'labels.json').exists() else 0}
        write(OUT/('feature-completion.json' if feature else 'completion.json'),result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['draft','prepare','features','labels','worker','pack']);p.add_argument('--stage',choices=['feature','verify','label']);p.add_argument('--index',type=int);a=p.parse_args();configure_runner()
    if a.command=='draft':
        history,paths,reports=draft_novelty();r={'historical_count':len(history),'collisions':[r for r in reports if r['historical_identity_overlap'] or r['within_identity_overlap'] or r['historical_skeleton_overlap']]}
    elif a.command=='prepare':r=prepare()
    elif a.command=='worker':worker(a.stage,a.index);return
    elif a.command=='pack':r=native.pack('test')
    else:r=run(a.command)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
