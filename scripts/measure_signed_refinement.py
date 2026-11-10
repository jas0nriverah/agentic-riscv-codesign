#!/usr/bin/env python3
"""Joint-frozen signed refinement32/40; reuse immutable native measurement runner."""
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
SPEC=importlib.util.spec_from_file_location('_signed_refinement_native',RUNNER)
native=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(native)
TRAIN=ROOT/'results/signed-refinement-data'
TEST=ROOT/'results/signed-refinement-validation'
POLICY=dict(native.POLICY)
PROOF_SEEDS={'train':2026110905,'test':2026110906}
TRAIN_TEMPLATES=(
 ('compound_signed_sub_xor','sub(xor(sra(addi(xori(in0,13),37),andi(add(in0,in1),{k})),in1),in0)',[1,5,15,31]),
 ('compound_signed_add_offset','add(xori(sra(addi(xori(in0,13),37),andi(or(in0,in1),{k})),7),in1)',[1,5,15,31]),
 ('compound_signed_xor_sub','xor(sub(sra(xori(addi(in0,13),37),andi(add(in0,in1),{k})),in0),in1)',[1,5,15,31]),
 ('compound_signed_adddata_sub','sub(sra(addi(xori(add(in0,in1),13),37),andi(in0,{k})),in1)',[1,5,15,31]),
 ('signed_add_boolean_or','xor(add(in0,sra(in1,andi(in0,{k}))),or(in0,in1))',[1,5,15,31]),
 ('signed_add_boolean_ordata','xor(add(in0,sra(or(in0,in1),andi(in0,{k}))),and(in0,in1))',[1,5,15,31]),
 ('signed_add_boolean_oradd','xor(add(or(in0,in1),sra(in1,andi(in0,{k}))),and(in0,in1))',[1,5,15,31]),
 ('signed_add_boolean_orroot','or(xor(add(in0,sra(in1,andi(in0,{k}))),in1),and(in0,in1))',[1,5,15,31]),
)
TEST_TEMPLATES=(
 ('heldout_compound_signed_add_xor','xor(add(sra(addi(xori(in1,29),83),andi(sub(in0,in1),{k})),in0),in1)',[1,7,15,31]),
 ('heldout_compound_signed_or_sub','sub(or(sra(xori(addi(in1,29),83),andi(xor(in0,in1),{k})),in0),in1)',[1,7,15,31]),
 ('heldout_compound_signed_ordata_add','add(sra(addi(xori(or(in0,in1),29),83),andi(in1,{k})),xor(in0,in1))',[1,7,15,31]),
 ('heldout_signed_add_boolean_reverse','xor(add(in1,sra(in0,andi(in1,{k}))),and(in0,in1))',[1,7,15,31]),
 ('heldout_signed_add_boolean_xordata','xor(add(in0,sra(xor(in0,in1),andi(in0,{k}))),or(in0,in1))',[1,7,15,31]),
 ('heldout_signed_add_boolean_androot','and(xor(add(in0,sra(in1,andi(in0,{k}))),in1),or(in0,in1))',[1,7,15,31]),
 ('control_signed_variable_offset_sub','xor(sub(sra(addi(in0,83),andi(in1,{k})),in0),or(in0,in1))',[1,7,15,31]),
 ('control_unsigned_compound_add','xor(add(srl(addi(xori(in0,29),83),andi(in1,{k})),in1),in0)',[1,7,15,31]),
 ('control_static_signed_mixed','xor(sub(srai(or(in0,in1),{k}),in0),srli(in1,5))',[2,9,18,27]),
 ('control_variable_left_boolean','or(sll(xor(in0,in1),andi(in1,{k})),and(in0,in1))',[1,7,15,31]),
)
read,write,need,sha,now=prior.read,prior.write,prior.need,prior.sha,prior.now
skeleton=native.skeleton

def candidates(kind):
    need(kind in ('train','test'),'Unknown cohort')
    rows=[]
    for name,template,values in TRAIN_TEMPLATES if kind=='train' else TEST_TEMPLATES:
        for k in values:
            formula=parse_formula(template.format(k=k)).canonical()
            rows.append({'candidate_id':'signed-refinement-'+kind+':'+prior.sha_bytes(formula.encode()),
                         'formula':formula,'template':name,'parameter':k})
    need(len(rows)==len({r['formula'] for r in rows})==(32 if kind=='train' else 40),'Exact unique cohort required')
    return rows

def inventory():
    """Extend the latest hash-bound inventory with only the last72 formulas/aliases."""
    paths=[ROOT/'results/guarded-revision-data'/n for n in ('historical-formulas.json','candidates.json','novelty.json','plan.json')]
    paths += [ROOT/'results/guarded-revision-validation'/n for n in ('candidates.json','novelty.json','plan.json')]
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
    tools=read(ROOT/'results/guarded-revision-data/tools.json')
    for tool in tools.values():need(sha(tool['path'])==tool['sha256'],'Native binary differs')
    write(TRAIN/'tools.json',tools)
    sources=[Path(__file__),RUNNER,ROOT/'scripts/measure_budget_preserving_coverage.py',ROOT/'scripts/measure_targeted_coverage.py',ROOT/'scripts/validate_selected_features.py',ROOT/'tests/test_measure_signed_refinement.py',*sorted((ROOT/'isaforge').glob('*.py'))]
    plan={'schema':'signed-refinement-joint32train40test-v1','frozen_at_utc':now(),'policy':POLICY,
        'training_count':32,'test_count':40,'training_templates':TRAIN_TEMPLATES,'test_templates':TEST_TEMPLATES,
        'proof_random_seeds':PROOF_SEEDS,'runner':'Private module configuration of immutable scripts/measure_guarded_revision.py run/worker/pack; child command executes this wrapper.',
        'success_rule':'Candidate policies and exact evaluation gates frozen separately before labels. Retain all complete consumed panels and named remaining tradeoffs; choose only from preregistered development hierarchy before any fresh labels. Fresh complete40 must pass preregistered criteria against base and current comparators.',
        'chronology':'Both cohorts/protocol freeze and audit; both cohorts label-free features; independent pretrain receipt; original training RTL verification then labels; development candidate selection and all ordered base/current/candidate fresh points+models freeze; independent prelabel receipt; original fresh RTL verification then labels.',
        'native_accounting':'Elapsed wall time summed over features, train-labels and test-labels, including subprocess startup/verification/extraction/synthesis/failures. Both-cohort features charged training180s; shared300s, at most2workers, no overlapping stages. Audit/model idle time excluded.',
        'missing_rule':'Keep all72 rows and all failures. No retries, replacements or complete-cohort primary result with missing cases.',
        'scope':'Synthetic refinement-targeted32 training; fresh24 composition variants spanning compound signed data and signed addBoolean plus16 variable/mixed controls. No application transfer, calibrated bounds, timing, power, full-core or CPU claim.',
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

def configure_runner():
    """Configure only a private in-memory module; every source file stays unchanged."""
    native.TRAIN=TRAIN;native.TEST=TEST;native.POLICY=POLICY
    native.TRAIN_TEMPLATES=TRAIN_TEMPLATES;native.TEST_TEMPLATES=TEST_TEMPLATES
    native.candidates=candidates;native.inventory=inventory;native.validate=validate
    native.verify_point_freeze=verify_point_freeze;native.__file__=str(Path(__file__).resolve())
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
