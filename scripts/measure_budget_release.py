#!/usr/bin/env python3
"""Joint-frozen budget release32/40; reuse immutable native measurement runner."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import validate_selected_features as prior
from isaforge.features import parse_formula
# A private module instance keeps the prior CLI and imported historical helpers intact.
RUNNER=ROOT/'scripts/measure_guarded_revision.py'
SPEC=importlib.util.spec_from_file_location('_budget_release_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
TRAIN=ROOT/'results/budget-release-data'
TEST=ROOT/'results/budget-release-validation'
POLICY=dict(native.POLICY)
PROOF_SEEDS={'train':2026111001,'test':2026111002}
TRAIN_TEMPLATES=(
 ('compound_signed_addxor_reverse','add(xor(sra(xori(addi(in0,47),19),andi(xor(in0,in1),{k})),in1),in0)',[1,3,7,31]),
 ('compound_signed_subdata_addxor','xor(add(sra(addi(xori(sub(in0,in1),19),47),andi(or(in0,in1),{k})),in1),in0)',[1,3,7,31]),
 ('compound_signed_xor_dualadd','xor(sra(addi(xori(in0,19),47),andi(and(in0,in1),{k})),add(in0,in1))',[1,3,7,31]),
 ('compound_signed_anddata_addxor','add(sra(xori(addi(and(in0,in1),47),19),andi(in1,{k})),xor(in0,in1))',[1,3,7,31]),
 ('signed_add_boolean_or_addxor','or(add(sra(in0,andi(in1,{k})),xor(in0,in1)),in1)',[1,3,7,31]),
 ('signed_add_boolean_and_addxor','and(add(sra(in0,andi(in1,{k})),xor(in0,in1)),in1)',[1,3,7,31]),
 ('signed_add_boolean_xoror_add','add(xor(sra(in0,andi(in1,{k})),or(in0,in1)),in0)',[1,3,7,31]),
 ('signed_add_boolean_anddata_reverse','xor(add(sra(and(in0,in1),andi(in1,{k})),in1),in0)',[1,3,7,31]),
)
TEST_TEMPLATES=(
 ('heldout_compound_signed_add_xor','xor(add(sra(xori(addi(or(in0,in1),61),23),andi(in0,{k})),in1),in0)',[1,3,7,31]),
 ('heldout_compound_signed_xor_dualsub','xor(sra(addi(xori(in1,23),61),andi(or(in0,in1),{k})),sub(in0,in1))',[1,3,7,31]),
 ('heldout_compound_signed_add_dualxor','add(sra(xori(addi(in1,61),23),andi(xor(in0,in1),{k})),xor(in0,in1))',[1,3,7,31]),
 ('heldout_compound_signed_xordata_addxor','xor(add(sra(addi(xori(xor(in0,in1),23),61),andi(and(in0,in1),{k})),in1),in0)',[1,3,7,31]),
 ('heldout_signed_add_boolean_or_addxor','or(add(sra(in1,andi(xor(in0,in1),{k})),in0),xor(in0,in1))',[1,3,7,31]),
 ('heldout_signed_add_boolean_and_addxor','and(add(sra(in1,andi(or(in0,in1),{k})),in0),xor(in0,in1))',[1,3,7,31]),
 ('heldout_signed_add_boolean_or_shiftand','xor(add(sra(in0,andi(and(in0,in1),{k})),or(in0,in1)),in1)',[1,3,7,31]),
 ('heldout_signed_add_boolean_add_andxor','add(and(sra(in1,andi(in0,{k})),xor(in0,in1)),in0)',[1,3,7,31]),
 ('control_static_signed_reverse_xor','xor(srai(in1,{k}),add(in0,or(in0,in1)))',[2,9,17,27]),
 ('control_unsigned_offset_and','and(srl(addi(in1,61),andi(in0,{k})),or(in0,in1))',[1,3,7,31]),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def candidates(kind):
    need(kind in ('train','test'),'Unknown cohort')
    rows=[]
    for name,template,values in TRAIN_TEMPLATES if kind=='train' else TEST_TEMPLATES:
        for k in values:
            formula=parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id':'budget-release-'+kind+':'+prior.sha_bytes(formula.encode()),
                         'formula':formula,'template':name,'parameter':k})
    need(len(rows)==len({r['formula'] for r in rows})==(32 if kind=='train' else 40),'Exact unique cohort required')
    return rows

def inventory():
    """Extend the latest hash-bound inventory with only the last72 formulas/aliases."""
    paths=[ROOT/'results/signed-refinement-data'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    paths += [ROOT/'results/signed-refinement-validation'/n for n in ('candidates.json','novelty.json','plan.json')]
    history=set()
    for path in paths:history.update(prior.formula_strings(read(path)))
    return sorted(history),paths

def draft_novelty():
    configure_runner()
    return native.draft_novelty()

def prepare():
    need(not TRAIN.exists() and not TEST.exists(),'Fresh directories required')
    history,paths,reports=draft_novelty()
    need(not any(r['historical_identity_overlap'] or r['across_cohort_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap'] for rs in reports.values() for r in rs),'Input-only collision; stop before freeze or native jobs')
    for kind,out in [('train',TRAIN),('test',TEST)]:
        write(out/'candidates.json',candidates(kind))
        write(out/'novelty.json',{'status':'pass','historical_count':len(history),'joint_new_count':72,
            'previous_latest_consumed_count':72,'comparisons':reports[kind],
            'scope':'Canonical, commutative V4, V4/V5 normalized identities and V7 aliases against latest frozen all-prior inventory including last32train+40test and saved aliases. Original constant-erased AST skeletons screened against all prior and across train/test. Finite identity screens, not exhaustive semantic equivalence or application independence.'})
    write(TRAIN/'historical-formulas.json',history)
    tools=read(ROOT/'results/signed-refinement-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(TRAIN/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_budget_release.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'budget-release-joint32train40test-v1','frozen_at_utc':now(),'policy':POLICY,
        'training_count':32,'test_count':40,'training_templates':TRAIN_TEMPLATES,'test_templates':TEST_TEMPLATES,
        'proof_random_seeds':PROOF_SEEDS,'runner':'Private module configuration of immutable scripts/measure_guarded_revision.py run/worker/pack; child command executes this wrapper.',
        'success_rule':'Candidate policies and exact evaluation gates frozen separately before labels. Retain all complete consumed panels and named remaining tradeoffs; choose only from preregistered development hierarchy before any fresh labels. Fresh complete40 must pass preregistered criteria against base and current comparators.',
        'chronology':'Both cohorts/protocol freeze and audit; both cohorts label-free features; independent pretrain receipt; original training RTL verification then labels; development candidate selection and all ordered base/current/candidate fresh points+models freeze; independent prelabel receipt; original fresh RTL verification then labels.',
        'native_accounting':'Elapsed wall time summed over features, train-labels and test-labels, including subprocess startup/verification/extraction/synthesis/failures. Both-cohort features charged training180s; shared300s, at most2workers, no overlapping stages. Audit/model idle time excluded.',
        'missing_rule':'Keep all72 rows and all failures. No retries, replacements or complete-cohort primary result with missing cases.',
        'scope':'Synthetic budget-release-targeted32 training; fresh16 compound signed add/xor plus16 signed addBoolean variable-shift/mixed circuits and8 controls. No application transfer, calibrated bounds, timing, power, full-core or CPU claim.',
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
        'inputs':{str(p.relative_to(ROOT)):sha(p) for out in (TRAIN,TEST) for p in sorted(out.iterdir()) if p.is_file()},
        'prior_inventory_sources':{str(p.relative_to(ROOT)):sha(p) for p in paths},'fits':0,'target_label_jobs':0,'native_feature_jobs':0}
    write(TRAIN/'plan.json',plan);write(TEST/'plan.json',plan);return plan

def validate():
    plan=read(TRAIN/'plan.json');need(plan['policy']==POLICY,'Policy changed')
    need(read(TEST/'plan.json')==plan,'Joint cohort plan differs')
    for kind,out in [('train',TRAIN),('test',TEST)]:need(read(out/'candidates.json')==candidates(kind),'Cohort changed')
    for section in ('sources','inputs','prior_inventory_sources'):
        for path,digest in plan[section].items():need(sha(ROOT/path)==digest,'Frozen binding changed: '+path)
    for tool in read(TRAIN/'tools.json').values():need(sha(tool['path'])==tool['sha256'],'Tool changed')
    return plan

def verify_point_freeze():
    freeze=read(TEST/'point-freeze.json');need(freeze['target_label_jobs']==0,'Fresh points must precede labels')
    need(bool(freeze['bindings']),'Point/model bindings required')
    for path,digest in freeze['bindings'].items():need(sha(ROOT/path)==digest,'Point/model binding changed: '+path)
    return freeze

def worker(kind,stage,index):
    """Use new preregistered proof seeds without changing the historical runner."""
    if stage!='verify':
        return ORIGINAL_WORKER(kind,stage,index)
    validate();out=TRAIN if kind=='train' else TEST;rows=read(out/'candidates.json')
    need((out/'label-attempt.json').exists(),'Owned single attempt required')
    if kind=='test':verify_point_freeze()
    from isaforge.rtl import verify_rtl_batch
    proof=verify_rtl_batch([r['formula'] for r in rows],out/'raw/verification',
                         random_vectors=POLICY['random_vectors'],seed=PROOF_SEEDS[kind],timeout=180)
    need(proof['verified'] is True and proof['formula_count']==len(rows) and
         proof['total_comparisons']==POLICY['vectors_per_formula']*len(rows),
         'Complete original RTL verification required')
    write(out/'raw/verification/result.json',proof)

ORIGINAL_WORKER=native.worker

def configure_runner():
    """Configure only a private in-memory module; every source file stays unchanged."""
    native.TRAIN=TRAIN;native.TEST=TEST;native.POLICY=POLICY
    native.TRAIN_TEMPLATES=TRAIN_TEMPLATES;native.TEST_TEMPLATES=TEST_TEMPLATES
    native.candidates=candidates;native.inventory=inventory;native.validate=validate
    native.verify_point_freeze=verify_point_freeze;native.worker=worker;native.__file__=str(Path(__file__).resolve())
    return native

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['draft','prepare','features','train-labels','test-labels','worker','pack'])
    parser.add_argument('--kind',choices=['train','test'],default='train');parser.add_argument('--stage',choices=['feature','verify','label']);parser.add_argument('--index',type=int)
    args=parser.parse_args();runner=configure_runner()
    if args.command=='draft':
        history,paths,reports=draft_novelty();result={'historical_count':len(history),'collisions':[r for rs in reports.values() for r in rs if r['historical_identity_overlap'] or r['across_cohort_identity_overlap'] or r['historical_skeleton_overlap'] or r['train_test_skeleton_overlap']]}
    elif args.command=='prepare':result=prepare()
    elif args.command=='worker':runner.worker(args.kind,args.stage,args.index);return
    elif args.command=='pack':result=runner.pack(args.kind)
    else:result=runner.run(args.command)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
