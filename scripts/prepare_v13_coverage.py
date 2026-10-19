#!/usr/bin/env python3
"""Seal48 targeted development originals; no native tools, features, solver or fit."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge.features import IMMEDIATE_OPERATIONS,parse_formula
from isaforge.v5_corpus import equivalence_key,skeleton

V9='results/2026-10-15-v9-coverage-development'
V12='results/2026-10-15-v12-target-transform'
V11='results/2026-10-15-v11-reserved-transfer'
V11_ROWS_SHA='19223417e1a497efe0450132c9eb31e5d70796791163740d5ca2adcccb8d0420'
V11_REVIEW_SHA='99c3360e25bb42ad5e9d692740e7890d187bb2187aa419a6d06ec6bf656f4113'
V9_SHA='468d264af46134f6717e317c9fcdc10c47f0f45e5938ec5da2999793d2977dca'
V12_SHA='3934bf7dd0ef2c6c5dbc47e3ddd3a627f32523a9861c41697baa45e6d4e35377'
MASKS=(255,341,1365,2047)
SHIFTS=(1,8,16,31)
SCHEMA='isaforge-v13-coverage-preparation-v1'


def need(condition,message):
    if not condition:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    def unique(items):
        out={}
        for k,v in items:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def record(path,root):return {'path':os.path.relpath(Path(path).resolve(),Path(root).resolve()),'sha256':sha(path)}
def canonical(formula):return parse_formula(formula).canonical()
def identical(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)


def syntax(formula):
    root=parse_formula(formula);ops=set();tree_ops=[];inputs=Counter();operand_rows=[]
    def symbols(node):
        if not node.children:return {node.value} if node.value in ('in0','in1') else set()
        return set().union(*(symbols(c) for c in node.children))
    def visit(node):
        if not node.children:
            if node.value in ('in0','in1'):inputs[node.value]+=1
            else:need(False,'Literal must be an encodable immediate operand')
            return
        ops.add(node.canonical());tree_ops.append(node.value)
        if node.value in IMMEDIATE_OPERATIONS:
            immediate=node.children[-1]
            need(not immediate.children and type(immediate.value) is int,'Literal immediate required')
            if node.value in ('slli','srli','srai'):need(0<=immediate.value<=31,'Shift immediate outside5bits')
            else:need(-2048<=immediate.value<=2047,'Immediate outside signed12')
            pending=node.children[:-1]
        else:pending=node.children
        supports=[symbols(c) for c in node.children]
        operand_rows.append({'operator':node.value,'formula':node.canonical(),'operand_input_sets':[sorted(x) for x in supports],
            'shared_input_symbols':sorted(set.intersection(*supports)) if supports else []})
        for c in pending:visit(c)
    visit(root)
    need(root.canonical()==formula and set(inputs)=={'in0','in1'} and 2<=len(ops)<=4,'Canonical syntactic two-input2..4-operation original required')
    return {'operation_count':len(ops),'tree_operation_count':len(tree_ops),'input_occurrences':dict(sorted(inputs.items())),
        'operator_counts':dict(sorted(Counter(tree_ops).items())),'operand_support':operand_rows}


def fixed_candidates():
    rows=[]
    def add(family,context,stratum,formula,**parameters):
        detail=syntax(formula)
        rows.append({'candidate_id':'v13-coverage:'+hashlib.sha256(formula.encode()).hexdigest(),'formula':formula,
            'family':family,'context':context,'stratum':stratum,'parameters':parameters,'operation_count':detail['operation_count']})
    for identity in ('or_sub','sub_and_complement'):
        for k in MASKS:
            for shift in (8,16):
                operand=f'sub(ori(in0,{k}),in0)' if identity=='or_sub' else f'sub(in0,andi(in0,{-k-1}))'
                add('correlated_high_products',identity,'multiplication',f'mulhsu({operand},slli(in1,{shift}))',mask=k,shift=shift)
    for context,template in (
        ('cancel_x_mask_y','sub(add(sub(in0,in1),andi(in1,{k})),in0)'),
        ('masked_x_repeat_y','add(sub(add(in0,in1),andi(in0,{k})),in1)'),
        ('repeat_x_or_y','sub(add(sub(in0,in1),in0),ori(in1,{k}))'),
        ('cancel_x_xor_y','add(sub(add(in0,in1),in0),xori(in1,{k}))')):
        for k in MASKS:add('affine_masked_chains',context,'arithmetic_chain',template.format(k=k),mask=k)
    for context,stratum,template in (
        ('unsigned_compare_post_sub','comparators','sub(sltu(addi(in0,63),slli(in1,{s})),in0)'),
        ('signed_compare_post_sub','comparators','sub(slt(slli(in0,{s}),xori(in1,-1365)),in1)'),
        ('arithmetic_shift_chain','constant_shifts','srai(add(srli(in0,{s}),in1),1)'),
        ('masked_variable_shift','variable_shifts','sra(slli(in0,{s}),andi(in1,31))')):
        for shift in SHIFTS:add('comparator_shift_compositions',context,stratum,template.format(s=shift),shift=shift)
    need(len(rows)==len({r['formula'] for r in rows})==48,'Exactly48 unique canonical originals required')
    need(Counter(r['family'] for r in rows)==Counter({f:16 for f in ('correlated_high_products','affine_masked_chains','comparator_shift_compositions')}),'Fixed16/16/16 allocation required')
    return rows


def accepted_forms(row):
    forms={canonical(row['formula']),canonical(row['normalized_formula'])}
    for mode in ('bit','affine','combined'):
        saved=row['v7_modes'][mode]
        need(saved['metadata']['status'] in ('accepted','fallback','rejected'),'Unknown retained identity status')
        if saved['metadata']['status']=='accepted':forms.add(canonical(saved['normalized_formula']))
    return forms


def merge_ledger(prior,new_rows,identities,fitting):
    union={};sources=defaultdict(set)
    def add(formula,forms,source):
        need(canonical(formula)==formula,'Historical canonical original required')
        union.setdefault(formula,set()).update(canonical(f) for f in [formula,*forms]);sources[formula].add(source)
    need(len(prior)==len({r['formula'] for r in prior})==2881,'Complete2881-formula consumed ledger required')
    for r in prior:
        for source in r['sources']:add(r['formula'],r['accepted_forms'],'v9_prior:'+source)
    imap={r['formula']:r for r in identities}
    need(len(new_rows)==len(imap)==48 and {r['formula'] for r in new_rows}==set(imap),'Complete48 V9 original identities required')
    for r in new_rows:add(r['formula'],accepted_forms(imap[r['formula']]),'v9_coverage48')
    rows=fitting['rows'];aliases=fitting['aliases']
    need(len(rows)==len(aliases)==1713 and len({r['formula'] for r in rows})==1713,'Complete1713 fitting input whitelist required')
    need(Counter(r['source'] for r in rows)==Counter(original1665=1665,coverage48=48),'V12 original/coverage membership differs')
    need({r['formula'] for r in rows if r['source']=='coverage48'}==set(imap),'V12 coverage original membership differs')
    for r,forms in zip(rows,aliases):
        need(r['formula'] in union,'Fitting original absent from complete consumed ledger')
        add(r['formula'],forms,'v12_fitting:'+r['source'])
    return [{'formula':f,'accepted_forms':sorted(union[f]),'sources':sorted(sources[f])} for f in sorted(union)]


def load_ledger(repository=ROOT):
    repository=Path(repository).resolve();paths=[]
    def frozen(directory,expected,names):
        root=repository/directory;p=root/'preparation.json';need(sha(p)==expected,'Frozen preparation identity differs');manifest=read(p);paths.append(p)
        bindings={(root/e['path']).resolve():e['sha256'] for e in manifest['files']};output=[]
        for name in names:
            path=root/name;need(bindings.get(path.resolve())==sha(path),'Unbound historical identity input');paths.append(path);output.append(read(path))
        return output
    prior,new,identities=frozen(V9,V9_SHA,('consumed-input-ledger.json','candidates.json','identity-analysis.json'))
    fitting,=frozen(V12,V12_SHA,('fitting.json',))
    ledger=merge_ledger(prior['records'],new,identities,fitting)
    # V11 inputs are exposed even though its physical labels remain uncollected.
    v11_rows=repository/V11/'completed-rows.json';v11_review=repository/V11/'input-review/input-package-review.json'
    need(sha(v11_rows)==V11_ROWS_SHA and sha(v11_review)==V11_REVIEW_SHA,'Exact later V11 input-only provenance required')
    review=read(v11_review);exposed=read(v11_rows)
    need(review['status']=='passed' and review['completed_rows_sha256']==V11_ROWS_SHA and len(exposed)==318
        and len({r['formula'] for r in exposed})==196,'Complete V11 exposed-input registry required')
    union={r['formula']:{'forms':set(r['accepted_forms']),'sources':set(r['sources'])} for r in ledger}
    for r in exposed:
        f=canonical(r['formula']);need(f==r['formula'],'V11 canonical original required')
        item=union.setdefault(f,{'forms':{f},'sources':set()});item['sources'].add('v11_input_only:'+r['benchmark'])
    ledger=[{'formula':f,'accepted_forms':sorted(v['forms']),'sources':sorted(v['sources'])} for f,v in sorted(union.items())]
    return ledger,[*paths,v11_rows,v11_review]


def keys(forms):
    forms={canonical(f) for f in forms}
    return {'accepted_form':forms,'commutative_v4_normalization':{equivalence_key(f) for f in forms},'ordered_skeleton':{skeleton(f) for f in forms}}


def diagnostics(ledger,candidates):
    index=defaultdict(lambda:defaultdict(set))
    for r in ledger:
        for channel,values in keys(r['accepted_forms']).items():
            for key in values:index[channel][key].add(r['formula'])
    rows=[];internal=[];proposal_keys=[]
    for r in candidates:
        f=r['formula'];k=keys([f]);proposal_keys.append(k)
        matches={c:sorted({old for key in values for old in index[c].get(key,())}) for c,values in k.items()}
        rows.append({'candidate_id':r['candidate_id'],'formula':f,'canonical_original_seen':f in {x['formula'] for x in ledger},'matches':matches,
            'declared_alias_seen':bool(matches['accepted_form'] or matches['commutative_v4_normalization'])})
    for i,r in enumerate(candidates):
        for j in range(i):
            shared={c:sorted(proposal_keys[i][c]&proposal_keys[j][c]) for c in proposal_keys[i] if proposal_keys[i][c]&proposal_keys[j][c]}
            if shared:internal.append({'candidate_a':candidates[j]['candidate_id'],'candidate_b':r['candidate_id'],'shared_keys':shared,
                'declared_alias':bool(set(shared)&{'accepted_form','commutative_v4_normalization'})})
    return {'schema':'isaforge-v13-input-overlap-v1','consumed_unique_originals':len(ledger),'proposed_originals':48,'records':rows,
        'canonical_original_seen_count':sum(r['canonical_original_seen'] for r in rows),'declared_alias_seen_count':sum(r['declared_alias_seen'] for r in rows),
        'within_proposal_matches':internal,'within_proposal_declared_alias_pairs':sum(r['declared_alias'] for r in internal),
        'scope':'All48 retained. Frozen V4 commutativity/normalization and saved accepted aliases only; skeleton overlap is diagnostic. No new solver, feature collision or exhaustive non-equivalence claim.'}


def recipe():
    return {'schema':'isaforge-v13-coverage-input-recipe-v1','candidates':48,'allocation':{'correlated_high_products':16,'affine_masked_chains':16,'comparator_shift_compositions':16},
        'masks':list(MASKS),'high_product_shifts':[8,16],'composition_shifts':list(SHIFTS),'target':'Original emitted CPU-encodable RV32 RTL LUT4; semantic simplification never changes target.',
        'selection':'Fixed templates informed by consumed V9 errors. No outcomes, scores, overlap-driven replacement or claim of independent novelty.',
        'future_collection_policy':{'seed':2026101529,'random_vectors':2048,'boundary_vectors':100,'total_vectors':2148,'workers':2,'timeout_seconds':360,'arms':'All48 original RTL only; no retries/replacements','release':'Separate exact tool/source/verification contract before native calls'},
        'preparation_calls':{'native_jobs':0,'feature_extractions':0,'solver_queries':0,'fits':0,'new_target_reads':0},
        'future_comparison':{'status':'Requires separate input/feature/measurement/fitting release','features':'Unchanged mapping217 selected from original336; original generic-zero override',
            'target_scale':'raw LUT4 only; V12 log candidate not promoted','trees':300,'criterion':'squared_error','min_samples_leaf':1,'max_features':1.0,'n_jobs':1,
            'seeds':[2026101421,2026101422,2026101423],'folds':5,'maximum_fits':30,'control':'Original1713 training rows only in each training partition',
            'candidate':'Same original training partition plus new coverage rows belonging to that partition','assessment':'Identical held-out original rows and held-out new rows for both predictors',
            'primary':'Three-seed mean nine-stratum macro OOF MAE difference augmented minus control on original1713; equal strata',
            'secondary':['New48 OOF challenge errors with family/stratum denominators','P99,worstAE,maximum-underprediction','cap64 false accept/reject separately; caps32/128 sensitivity'],
            'grouping':'Rebuild common transitive original V5 components + saved accepted identities/commutative keys + exact selected217float32 collisions + entire new template contexts; deterministic V12 greedy rule; freeze before fitting.',
            'gate':'Require five nonempty validation folds and all nine strata in every training partition. Preserve overlaps/failures; stop rather than weaken groups. No final refit or consumed V6/V8 target replay in30-fit budget.'},
        'scope':'Targeted consumed-development data augmentation, not residual correction, independent transfer, calibration or CPU benefit.'}


def required_sources(repository=ROOT):
    repository=Path(repository).resolve()
    names=('__init__','features','rtl','synthesis','probe_corpus','area_model','area_model_v2',
        'structural_features_v3','structural_features_v4','v4_corpus','v5_corpus')
    return [repository/'scripts/prepare_v13_coverage.py',repository/'tests/test_prepare_v13_coverage.py',
        repository/'docs/v13-coverage-protocol.md',*[repository/'isaforge'/f'{n}.py' for n in names]]


def coverage_diagnostics(candidates):
    return {'schema':'isaforge-v13-syntax-coverage-v1','families':dict(Counter(r['family'] for r in candidates)),'contexts':dict(Counter(r['context'] for r in candidates)),
        'strata':dict(Counter(r['stratum'] for r in candidates)),'records':[{'candidate_id':r['candidate_id'],**syntax(r['formula'])} for r in candidates],
        'scope':'Syntactic operand-symbol overlap and immediate/mask support only, not feature extraction, RTL proof or physical area prediction.',
        'mask_support':[{'mask':k,'possible_one_bits':k.bit_count(),'unsigned_bit_width':k.bit_length(),'holes_below_top_bit':k.bit_length()-k.bit_count()} for k in MASKS]}


def prepare(root,repository=ROOT):
    root=Path(root).resolve();need(not root.exists(),'Fresh preparation root required');root.mkdir(parents=True)
    try:
        candidates=fixed_candidates();ledger,inputs=load_ledger(repository);sources=required_sources(repository);before={p:sha(p) for p in [*inputs,*sources]}
        overlap=diagnostics(ledger,candidates)
        coverage=coverage_diagnostics(candidates)
        write(root/'candidates.json',candidates);write(root/'consumed-input-ledger.json',{'schema':'isaforge-v13-consumed-input-ledger-v1','records':ledger,'historical_target_values_used':False})
        write(root/'duplicate-analysis.json',overlap);write(root/'coverage-diagnostics.json',coverage);write(root/'recipe.json',recipe())
        need(all(sha(p)==h for p,h in before.items()),'Sources/inputs changed during preparation')
        produced=[root/n for n in ('candidates.json','consumed-input-ledger.json','duplicate-analysis.json','coverage-diagnostics.json','recipe.json')]
        manifest={'schema':SCHEMA,'status':'prepared-inputs-only','created_at_utc':datetime.now(timezone.utc).isoformat(),'candidate_count':48,
            **recipe()['preparation_calls'],'historical_target_values_used':False,'files':[record(p,root) for p in [*sources,*inputs,*produced]],
            'source_paths':[os.path.relpath(p,root) for p in sources],'input_paths':[os.path.relpath(p,root) for p in inputs],
            'duplicate_summary':{k:overlap[k] for k in ('canonical_original_seen_count','declared_alias_seen_count','within_proposal_declared_alias_pairs')},
            'measurement_gate':'No measurement or fit release. Separate collector/features/tool/verification protocol required.'}
        write(root/'preparation.json',manifest);return manifest
    except BaseException as error:
        write(root/'preparation-failure.json',{'schema':'isaforge-v13-preparation-failure-v1','error':str(error),'native_jobs':0,'fits':0});raise


def validate_preparation(root):
    root=Path(root).resolve();manifest=read(root/'preparation.json')
    need(manifest['schema']==SCHEMA and manifest['status']=='prepared-inputs-only' and not (root/'preparation-failure.json').exists(),'Complete input-only preparation required')
    paths={}
    for e in manifest['files']:
        p=(root/e['path']).resolve();need((p.is_relative_to(ROOT) or p.is_relative_to(root)) and p not in paths and sha(p)==e['sha256'],'Changed/duplicate bound input');paths[p]=e['sha256']
    need(set(manifest['source_paths'])=={os.path.relpath(p,root) for p in required_sources()} and all(p in paths for p in required_sources()),'Complete source closure required')
    ledger,inputs=load_ledger();need(set(manifest['input_paths'])=={os.path.relpath(p,root) for p in inputs} and all(p in paths for p in inputs),'Exact historical input closure required')
    produced={root/n for n in ('candidates.json','consumed-input-ledger.json','duplicate-analysis.json','coverage-diagnostics.json','recipe.json')}
    need(set(paths)==set(required_sources())|set(inputs)|produced,'Exact prepared source/input/output closure required')
    need(manifest['candidate_count']==48 and all(type(manifest[k]) is int and manifest[k]==0 for k in recipe()['preparation_calls'])
        and manifest['historical_target_values_used'] is False,'Input-only counters differ')
    candidates=read(root/'candidates.json');need(identical(candidates,fixed_candidates()) and identical(read(root/'recipe.json'),recipe()),'Fixed48 recipe differs')
    need(read(root/'consumed-input-ledger.json')['records']==ledger and read(root/'duplicate-analysis.json')==diagnostics(ledger,candidates),'Prepared input/overlap replay differs')
    need(identical(read(root/'coverage-diagnostics.json'),coverage_diagnostics(candidates)),'Operand coverage replay differs')
    overlap=read(root/'duplicate-analysis.json')
    need(manifest['duplicate_summary']=={k:overlap[k] for k in ('canonical_original_seen_count','declared_alias_seen_count','within_proposal_declared_alias_pairs')},'Overlap summary differs')
    return manifest,recipe(),candidates


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT/'results/2026-10-15-v13-coverage-development');p.add_argument('--validate',action='store_true')
    args=p.parse_args();result=validate_preparation(args.root)[0] if args.validate else prepare(args.root)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','source_paths','input_paths')},indent=2))
