#!/usr/bin/env python3
"""Fixed general32 +unsupported8 +challenge88;zero fits,300s native."""
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
SPEC=importlib.util.spec_from_file_location('_boundary_abstention_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
OUT=ROOT/'results/boundary-abstention-validation'
POLICY={'total_native_seconds':300,'workers':2,'fits':0,'retries':0,'replacement_candidates':0,
        'random_vectors':2048,'vectors_per_formula':2148,'caps_lut4':[32,64,128]}
PROOF_SEED=2026111105
PARAMETERS=((5,29,1),(11,71,1),(41,131,1),(137,311,1),(5,29,3),(11,71,3),(41,131,3),(137,311,3))
GENERAL_SUPPORTED_VALUES=(1,31)
GENERAL_SUPPORTED_TEMPLATES=(
 ('general_plain_addi_xori_or','xor(add(sra(addi(xori(in0,13),101),andi(xori(in1,7),{k})),in1),or(in0,in1))'),
 ('general_plain_xori_addi_and','xor(add(sra(xori(addi(in1,101),13),andi(addi(in0,5),{k})),in0),and(in0,in1))'),
 ('general_anddata_directpost','xor(add(sra(addi(xori(and(in0,in1),13),101),andi(xori(in1,7),{k})),in0),xor(in0,in1))'),
 ('general_ordata_directpost','xor(add(sra(xori(addi(or(in0,in1),101),13),andi(xori(in0,7),{k})),in1),and(in0,in1))'),
 ('general_signed8_after','xor(add(sra(slli(andi(xori(addi(in0,101),13),255),24),andi(addi(in1,5),{k})),in1),or(in0,in1))'),
 ('general_signed8_beforeadd','xor(add(sra(addi(slli(andi(xori(in1,13),255),24),101),andi(xori(in0,7),{k})),in0),and(in0,in1))'),
 ('general_signed16_shared','xor(add(sra(slli(andi(xori(addi(and(in0,in1),101),13),65535),16),andi(xori(in1,7),{k})),and(in0,in1)),xor(in0,in1))'),
 ('general_signed16_beforexor','xor(add(sra(xori(slli(andi(addi(or(in0,in1),101),65535),16),13),andi(xori(in0,7),{k})),in1),and(in0,in1))'),
)
GENERAL_EXISTING_TEMPLATES=(
 ('general_oldscope_xordata','xor(add(sra(addi(xori(xor(in0,in1),13),101),andi(xori(in1,7),{k})),in0),in1)'),
 ('general_oldscope_andswitch','xor(add(sra(xori(addi(in0,101),13),andi(and(in0,in1),{k})),in1),in0)'),
)
CONTROL_TEMPLATES=(
 ('control_wrappedxor_rootadd','add(sra(xor(addi(xori(in0,13),101),in1),andi(xori(in1,7),{k})),xor(in0,in1))'),
 ('control_low16_directxor','xor(sra(addi(xori(andi(or(in0,in1),65535),13),101),andi(xori(in0,7),{k})),add(in0,in1))'),
 ('control_unsigned_outerand','xor(add(srl(xori(addi(or(in0,in1),101),13),andi(xori(in1,7),{k})),in0),and(in0,in1))'),
 ('control_static_signed8','xor(add(srai(slli(andi(addi(xori(in0,13),101),255),24),{k}),in1),or(in0,in1))'),
)
UNSUPPORTED_PARAMETERS=((5,29,1),(41,131,3))
UNSUPPORTED_TEMPLATES=(
 ('unsupported_fullword_xor_shared','xor(add(sra(addi(xori(xor(in0,in1),{c}),{d}),andi(xori(in0,7),{k})),xor(in0,in1)),or(in0,in1))'),
 ('unsupported_fullword_and_shared','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(xori(in1,7),{k})),and(in0,in1)),or(in0,in1))'),
 ('unsupported_fullword_or_shared','xor(add(sra(addi(xori(or(in0,in1),{c}),{d}),andi(xori(in0,7),{k})),or(in0,in1)),and(in0,in1))'),
 ('unsupported_sign8_beforeadd_shared','xor(add(sra(addi(slli(andi(xori(xor(in0,in1),{c}),255),24),{d}),andi(xori(in1,7),{k})),xor(in0,in1)),or(in0,in1))'),
)
CHALLENGE_TEMPLATES=(
 ('challenge_plain_addi_xori','xor(add(sra(addi(xori(in1,{c}),{d}),andi(xori(in0,7),{k})),in0),and(in0,in1))'),
 ('challenge_plain_xori_addi','xor(add(sra(xori(addi(in0,{d}),{c}),andi(addi(in1,5),{k})),in1),or(in0,in1))'),
 ('challenge_anddata_directpost','xor(add(sra(xori(addi(and(in0,in1),{d}),{c}),andi(xori(in0,7),{k})),in1),or(in0,in1))'),
 ('challenge_ordata_directpost','xor(add(sra(addi(xori(or(in0,in1),{c}),{d}),andi(xori(in1,7),{k})),in0),xor(in0,in1))'),
 ('challenge_xordata_directpost','xor(add(sra(xori(addi(xor(in0,in1),{d}),{c}),andi(xori(in0,7),{k})),in1),and(in0,in1))'),
 ('challenge_signed8_after','xor(add(sra(slli(andi(addi(xori(in1,{c}),{d}),255),24),andi(addi(in0,5),{k})),in0),and(in0,in1))'),
 ('challenge_signed16_ordata','xor(add(sra(slli(andi(addi(xori(or(in0,in1),{c}),{d}),65535),16),andi(addi(in1,5),{k})),in0),xor(in0,in1))'),
 ('challenge_signed8_beforeadd','xor(add(sra(addi(slli(andi(xori(and(in0,in1),{c}),255),24),{d}),andi(xori(in0,7),{k})),in1),or(in0,in1))'),
 ('challenge_signed16_shared','xor(add(sra(xori(slli(andi(addi(and(in0,in1),{d}),65535),16),{c}),andi(addi(in0,5),{k})),and(in0,in1)),or(in0,in1))'),
 ('challenge_low16_plain','xor(add(sra(andi(addi(xori(in1,{c}),{d}),65535),andi(addi(in0,5),{k})),in0),and(in0,in1))'),
 ('challenge_signed8_xor_shared','xor(add(sra(slli(andi(xori(addi(xor(in0,in1),{d}),{c}),255),24),andi(xori(in1,7),{k})),xor(in0,in1)),or(in0,in1))'),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def pool_candidates():
    rows=[]
    def append(formula,template,parameter,cohort,control=False):
        f=parse_formula(formula).canonical()
        rows.append({'candidate_id':'boundary-abstention-pool:'+prior.sha_bytes(f.encode()),'formula':f,'template':template,'parameter':parameter,'cohort':cohort,'pool_index':len(rows),'reserved_control':control})
    for name,template in GENERAL_SUPPORTED_TEMPLATES:
        for k in GENERAL_SUPPORTED_VALUES:append(template.format(k=k),name,k,'general')
    for name,template in GENERAL_EXISTING_TEMPLATES:
        for k in (1,3,7,31):append(template.format(k=k),name,k,'general')
    for name,template in CONTROL_TEMPLATES:
        for k in (1,3):append(template.format(k=k),name,k,'general',True)
    for name,template in UNSUPPORTED_TEMPLATES:
        for c,d,k in UNSUPPORTED_PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],'unsupported')
    for name,template in CHALLENGE_TEMPLATES:
        for c,d,k in PARAMETERS:append(template.format(c=c,d=d,k=k),name,[c,d,k],'challenge')
    need(len(rows)==len({r['formula'] for r in rows})==128,'Exact unique fixed128pool required')
    return rows

def selected():
    seal=read(OUT/'selection.json');indices=seal['selected_pool_indices'];pool=read(OUT/'pool-candidates.json')
    need(40<=len(indices)<=56 and len(indices)==len(set(indices)),'Fixedgeneral32+unsupported8 plus at most16active required')
    need(indices[:40]==list(range(40)),'All fixedgeneral32+unsupported8 must lead selected order')
    need(all(type(i) is int and 0<=i<len(pool) for i in indices),'Valid selected pool indices required')
    rows=[pool[i] for i in indices]
    need(read(OUT/'candidates.json')==rows,'Selected candidates differ from exact pool subset')
    need(sum(r['reserved_control'] for r in rows)==8,'All8 fixed controls required')
    need({r['pool_index'] for r in rows if r['reserved_control']}=={r['pool_index'] for r in pool if r['reserved_control']},'Reserved controls changed')
    full=read(OUT/'pool-features.json');subset=read(OUT/'features.json')
    need(subset=={'columns':full['columns'],'records':[full['records'][i] for i in indices]},'Selected features differ from exact pool subset')
    return rows

def inventory():
    paths=[ROOT/'results/boundary-coverage-data'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    paths += [ROOT/'results/boundary-coverage-validation'/n for n in ('pool-candidates.json','candidates.json','novelty.json','plan.json')]
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
          'scope':'Canonical,commutative V4,V4/V5normalized identities,V7aliases and original constant-erased AST skeletons against all-prior including all32newtraining+128prior boundary-coverage pool rows,evenunlabelled. Finite screens,not exhaustive semantic equivalence or application independence.'})
    tools=read(ROOT/'results/budget-release-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(OUT/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/boundary_coverage_features.py',ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_boundary_abstention.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'boundary-abstention-pool128-v1','frozen_at_utc':now(),'policy':POLICY,
          'training_count':0,'pool_count':128,'general_count':32,'general_supported_count':16,'general_existing_scope_only_count':8,'general_control_count':8,'fixed_unsupported_count':8,'challenge_pool_count':88,'maximum_selected_count':56,'all_pool_rows_consumed_for_future_novelty':True,
          'general_supported_templates':GENERAL_SUPPORTED_TEMPLATES,'general_supported_parameters':GENERAL_SUPPORTED_VALUES,'general_existing_templates':GENERAL_EXISTING_TEMPLATES,'general_existing_parameters':[1,3,7,31],'challenge_templates':CHALLENGE_TEMPLATES,'challenge_parameter_sequence':PARAMETERS,'control_templates':CONTROL_TEMPLATES,'unsupported_templates':UNSUPPORTED_TEMPLATES,'control_parameters':[1,3],'unsupported_parameters':UNSUPPORTED_PARAMETERS,'proof_random_seed':PROOF_SEED,
          'design_assumptions':'Fixed128inputpool covers plain-input Boolean-outer,AND/OR/XOR-sharing,narrow8/16sign-placement andoutside-familycontrasts. General32=16supportedlearning(8templates xlow/widemasks1/31)+8oldscope+8outsidecontrols. Separate8fullword/shared-data-postadd contrasts use prospectivelyfixedsmall/large(c,d,k)=(5,29,1)/(41,131,3) and are ALWAYSlabelled and scored,includingabstentions. Challenge88=11supportedtemplates x8lowmask/immediatetuples. All128rows/features/pointsretained;input-onlydesign,notnativefiltering;no cost/safetyguarantee.',
          'selection_rule':'Alwayslabel fixedgeneral32+fixedunsupported8 firstinpoolorder. Select atmost16supportedNEWlearnedcapcorrections versusprevious_structural fromchallenge,deterministic roundrobinsortedtemplatesandfixedparameterorder. Reserveall40fixed217/233keys;excludehistory andwithinpoolduplicates,withallcollisionrulesfrozeninmodelprotocol. Require>=4selectedactionsacross>=2templatesincludingcap128,and>=1counterfactualblockedlearnedoverrideinthefixedunsupported8. Noquotafill,poolextensionorreplacement.',
          'success_rule':'Zero fits; same frozen1857-row217forest and unchangedrawmeans. Freeze mechanismjoint-cell trainingcoverageabstention,gatesandsourcebeforefeatures. Score completegeneral32,unsupported8,conditional-full(actives+SAME8generaloutsidecontrols),andactive-onlyseparately withaccuracy/tail no-worseversusrelease+previous_structural+learned217,FA<=release andFR<=signed separately32/64/128;no pooling/independenceclaim,noremovalofabstentionsfromdenominators. All128points/abstentionreports/selection/subsetfrozenbeforelabels.',
          'chronology':'Fixed128pool/protocol/zero-fitpolicyseal+independentpreflight;all128nativefeatures;allpoints,coveragecells,abstentions,featurecollisions,deterministicfixed40+active<=16subsetfreeze;independentprelabelreceipt;allselectedoriginalRTLproofandlabels.',
          'native_accounting':'Sumelapsedwalltimeall128poolfeatures+selectedverification/labels includingstartup/extraction/synthesis/failures;shared300s,max2workers,nooverlap. Audit/modelidleexcluded.',
          'missing_rule':'Retainall128poolrows/features/points andeveryselectedlabel/failure;no retries,replacements,extensions,orcompletecohortprimarywithmissingcases.',
          'scope':'Uncalibrated mechanism-coverageabstentiontestedon fixedsyntheticgeneral/unsupportedpanelsandseparateconditionalchallenge;no unbiasedgeneralization,applicationtransfer,hardware-safetycertificate,timing,power,fullcoreorCPUclaim.',
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

def run(stage):
    validate();native.receipt(OUT/'preflight-audit.json');feature=stage=='features'
    attempt=OUT/('feature-attempt.json' if feature else 'label-attempt.json')
    need(not attempt.exists(),'Single attempt only;no retries')
    used=0 if feature else read(OUT/'feature-completion.json')['total_native_elapsed_seconds']
    if not feature:
        need(read(OUT/'feature-completion.json')['complete'],'Complete features required')
        native.receipt(OUT/'prelabel-audit.json');point_freeze()
    rows=pool_candidates() if feature else selected()
    budget=POLICY['total_native_seconds']-used;need(budget>0,'Native budget exhausted')
    began=time.monotonic();deadline=began+budget;jobs=[];failures=[]
    write(attempt,{'started_at_utc':now(),'budget_seconds':budget,'prior_native_elapsed_seconds':used,'stage':stage,'policy':POLICY,'fits':0})
    def owned(phase,index=None):
        folder=OUT/'raw'/('verification' if phase=='verify' else phase+'s/'+str(index))
        folder.mkdir(parents=True,exist_ok=True);log=folder/'worker.log'
        command=[sys.executable,str(Path(__file__).resolve()),'worker','--stage',phase]
        if index is not None:command+=['--index',str(index)]
        started=now();process=None;error=None;code=None
        try:
            remaining=deadline-time.monotonic();need(remaining>0,'Shared native deadline exhausted')
            with log.open('x') as stream:
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
        result={'kind':'test','stage':phase,'index':index,'started_at_utc':started,'finished_at_utc':now(),'returncode':code,'error':error,'log_sha256':sha(log) if log.exists() else None}
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
        result={'completed_at_utc':now(),'complete':not failures,'stage':stage,'native_elapsed_seconds':elapsed,'total_native_elapsed_seconds':used+elapsed,'native_budget_seconds':budget,'fits':0,'failures':failures,'native_worker_jobs':jobs,'policy':POLICY,'label_count':sum(r['status']=='complete' for r in read(OUT/'labels.json')) if (OUT/'labels.json').exists() else 0}
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
