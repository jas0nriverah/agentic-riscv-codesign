"""Label-free diverse RV32 input acquisition; no model/oracle/target mapping calls."""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json
import math
import random
import re
import struct
from .features import candidate_id, parse_formula
from .probe_corpus import STRATA, formula_shape
from .v5_corpus import equivalence_key, signatures, skeleton
from .graph_features_v5 import _normalized_root
from .structural_features_v5 import normalize_formula as current_normalize

SEEDS={'calibration':2026101441,'test':2026101442}
FAMILIES_PER_STRATUM=12
VARIANTS=2
MINIMUM_COMPONENTS=8
MAX_TREE_OPERATIONS=15
MAX_FAMILY_DRAWS=2000
MAX_FEATURE_REPAIRS=8
CONSTANTS=(-2047,-1365,-257,-33,-1,1,3,7,17,63,129,511,1023,1365,2047)
MASKS=(3,15,255,65535,16777215,1431655765,2863311530,252645135,4042322160)
SHIFTS=(1,2,3,5,7,11,13,16,19,23,29,31)
MULTIPLY=('mul','mulh','mulhu','mulhsu')

def digest(value):
    return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()

def tree_operations(formula):
    def visit(n):return int(bool(n.children))+sum(visit(c) for c in n.children)
    return visit(parse_formula(formula))

def _vector_key(values):
    if not isinstance(values,(tuple,list)) or not values:raise ValueError('Nonempty feature vector required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('Finite numeric feature vector required')
    return hashlib.sha256(b''.join(struct.pack('!d',float(v) if v else 0.) for v in values)).hexdigest()

def identity_keys(formula, record=None):
    """Sufficient identities, cross-channel skeletons, V5 and full V6 vectors.

    These checks cannot establish complete functional nonequivalence. Literal
    variants and symmetric input functions may be related beyond these rules.
    """
    f=parse_formula(formula).canonical();sig=signatures(f)
    normalized={sig['normalized_formula'],_normalized_root(current_normalize(f))}
    if record is not None:
        if parse_formula(record['formula']).canonical()!=f:raise ValueError('Feature formula identity differs')
        normalized.add(parse_formula(record['normalized_formula']).canonical())
    keys={('formula',x) for x in {f,*normalized}}
    keys.add(('equivalence',sig['equivalence_key']))
    for x in normalized:keys.add(('equivalence',equivalence_key(x)))
    keys.update(('skeleton',skeleton(x)) for x in {f,*normalized})
    if record is not None:
        values=record['values']
        if len(values)!=336:raise ValueError('Expected frozen V5 313 plus mapping23 features')
        keys.add(('v5_vector',_vector_key(values[:313])))
        keys.add(('v6_vector',_vector_key(values)))
    return keys

def component_map(rows, records=None):
    formulas=[r['formula'] for r in rows]
    if len(formulas)!=len(set(formulas)):raise ValueError('Component rows require unique formulas')
    byrecord={} if records is None else {r['formula']:r for r in records}
    if records is not None and (len(byrecord)!=len(records) or set(byrecord)!=set(formulas)):
        raise ValueError('Complete unique feature coverage required')
    parent={f:f for f in formulas};seen={}
    def find(f):
        while parent[f]!=f:parent[f]=parent[parent[f]];f=parent[f]
        return f
    for f in formulas:
        for key in identity_keys(f,byrecord.get(f)):
            if key in seen:
                a,b=find(f),find(seen[key]);parent[max(a,b)]=min(a,b)
            else:seen[key]=f
    members=defaultdict(list)
    for f in formulas:members[find(f)].append(f)
    ids={k:digest(sorted(v)) for k,v in members.items()}
    return {f:ids[find(f)] for f in formulas}

def inspect_seal(consumed, cohorts, consumed_records, cohort_records, *, families=FAMILIES_PER_STRATUM, minimum=MINIMUM_COMPONENTS):
    """Find whole-family input-only rejections; never inspect measured outcomes."""
    if set(cohorts)!=set(SEEDS) or set(cohort_records)!=set(SEEDS):raise ValueError('Calibration and test both required')
    if not 1<=minimum<=families:raise ValueError('Invalid component coverage requirement')
    allrows=[*consumed,*cohorts['calibration'],*cohorts['test']]
    records=[*consumed_records,*cohort_records['calibration'],*cohort_records['test']]
    groups=component_map(allrows,records);owners=defaultdict(set);rejected=[]
    for r in consumed:owners[groups[r['formula']]].add('consumed')
    for scope,rows in cohorts.items():
        if len(rows)!=len(STRATA)*families*VARIANTS:raise ValueError('Declared balanced candidate count differs')
        strata=Counter(r['stratum'] for r in rows)
        if strata!=Counter({s:families*VARIANTS for s in STRATA}):raise ValueError('Declared stratum coverage differs')
        familyrows=defaultdict(list)
        for r in rows:
            if r.get('evaluation_scope')!=scope:raise ValueError('Candidate scope differs')
            if formula_shape(r['formula'])[1]!=2 or tree_operations(r['formula'])>MAX_TREE_OPERATIONS:
                raise ValueError('Candidate violates two-input or operation budget')
            familyrows[r['structural_family_id']].append(r)
            owners[groups[r['formula']]].add(scope)
        if len(familyrows)!=len(STRATA)*families:raise ValueError('Family count differs')
        for family,pair in familyrows.items():
            if len(pair)!=VARIANTS or {r['variant_index'] for r in pair}!={0,1} or len({r['stratum'] for r in pair})!=1:
                raise ValueError('Each structural family requires exactly two variants in one stratum')
            if len({skeleton(r['formula']) for r in pair})!=1:raise ValueError('Constant variants must retain original skeleton')
    freshgroups={groups[r['formula']] for rows in cohorts.values() for r in rows}
    invalid={g for g in freshgroups if len(owners[g])>1}
    # Strong-equivalent families merging within one scope would reduce the
    # declared independent-family count. Reject all involved families before labels.
    bygroup=defaultdict(set)
    for scope,rows in cohorts.items():
        for r in rows:bygroup[groups[r['formula']]].add((scope,r['structural_family_id']))
    invalid.update(g for g,v in bygroup.items() if len(v)>1)
    for scope,rows in cohorts.items():
        for r in rows:
            if groups[r['formula']] in invalid:
                rejected.append({'scope':scope,'family_id':r['structural_family_id'],'formula':r['formula'],
                  'component':groups[r['formula']],'owners':sorted(owners[groups[r['formula']]]),'reason':'cross-cohort or merged structural-family component'})
    counts={scope:{s:len({groups[r['formula']] for r in rows if r['stratum']==s}) for s in STRATA} for scope,rows in cohorts.items()}
    if not rejected and any(n<minimum for c in counts.values() for n in c.values()):raise ValueError('Too few strong components per stratum')
    return {'schema':'isaforge-v6-input-seal-v1','status':'rejected' if rejected else 'sealed','rejections':rejected,
      'component_by_formula':{r['formula']:groups[r['formula']] for rows in cohorts.values() for r in rows},
      'scope_counts':{s:len(r) for s,r in cohorts.items()},'stratum_component_counts':counts,
      'consumed_formula_count':len(consumed),'cross_cohort_component_count':len({g for g in invalid if len(owners[g])>1}),
      'feature_columns_count':336,'v5_identity_columns_count':313,'minimum_components_per_stratum':minimum,
      'limitations':['Sufficient normalized, commutative, exact-vector and ordered-skeleton grouping; complete functional nonequivalence is not proved.',
      'Synthetic grammar families are not independently sourced applications or evidence of exchangeability.']}


def _shape(stratum,rng):
    """Random topology/operator template with typed literal placeholders."""
    a,b=rng.sample(('in0','in1'),2)
    literal_index=0
    def op(options,*children):
        nonlocal literal_index
        bound=[]
        for child in children:
            if child in ('C','M','S'):
                child+=str(literal_index);literal_index+=1
            bound.append(child)
        return rng.choice(options)+'('+','.join(bound)+')'
    def wrap(x,n,mode='mixed'):
        for _ in range(n):
            choice=rng.randrange(4)
            if mode=='logic':x=op(('andi','ori','xori'),x,'M')
            elif choice==0:x=op(('slli','srli','srai'),x,'S')
            elif choice==1:x=op(('addi','xori'),x,'C')
            elif choice==2:x=op(('add','sub','xor'),x,rng.choice((a,b)))
            else:x=op(('andi','ori'),x,'M')
        return x
    if stratum=='arithmetic_chain':
        x=op(('add','sub'),a,b)
        for _ in range(rng.randint(3,8)):
            x=op(('addi',),x,'C') if rng.randrange(3)==0 else op(('add','sub'),x,wrap(rng.choice((a,b)),rng.randrange(2)))
        return x
    if stratum=='shared_diamond':
        shared=wrap(op(('add','sub','xor','and','or'),a,b),rng.randrange(2))
        left=wrap(shared,rng.randint(1,2));right=wrap(shared,rng.randint(1,2))
        return wrap(op(('add','sub','xor','or'),left,right),rng.randrange(2))
    if stratum=='parallel_branches':
        left=a;right=b
        for _ in range(rng.randint(2,4)):left=op(('addi','xori','andi','ori','slli','srli','srai'),left,rng.choice(('C','M','S')))
        for _ in range(rng.randint(2,4)):right=op(('addi','xori','andi','ori','slli','srli','srai'),right,rng.choice(('C','M','S')))
        return wrap(op(('add','sub','and','or','xor'),left,right),rng.randint(0,2))
    if stratum=='mask_logic':
        def branch(x,depth):
            if not depth:return op(('andi','xori','ori'),x,'M')
            if rng.randrange(2):return op(('and','or','xor'),branch(x,depth-1),rng.choice((a,b)))
            return op(('andi','ori','xori'),branch(x,depth-1),'M')
        return op(('and','or','xor'),branch(a,rng.randint(1,3)),branch(b,rng.randint(1,3)))
    if stratum=='constant_shifts':
        left=op(('slli','srli','srai'),wrap(a,rng.randint(0,2)),'S')
        right=op(('slli','srli','srai'),wrap(b,rng.randint(0,2)),'S')
        return wrap(op(('add','sub','and','or','xor'),left,right),rng.randint(0,3))
    if stratum=='variable_shifts':
        data=wrap(a,rng.randint(1,3));amount=op(('andi',),wrap(b,rng.randint(1,3)),'31')
        return wrap(op(('sll','srl','sra'),data,amount),rng.randint(0,3))
    if stratum=='comparators':
        comparison=op(('slt','sltu'),wrap(a,rng.randint(1,3)),wrap(b,rng.randint(1,3)))
        if rng.randrange(2):comparison=op(('add','xor','or'),comparison,op(('slti','sltiu'),wrap(a,rng.randrange(2)),'C'))
        return wrap(comparison,rng.randint(0,2))
    if stratum=='multiplication':
        left=wrap(a,rng.randint(0,3));right=wrap(b,rng.randint(0,3))
        return wrap(op(MULTIPLY,left,right),rng.randint(0,3))
    raise ValueError('Unknown stratum')

def _instantiate(template,rng):
    # Immediate types follow the operation, rather than a shared token draw.
    # Template placeholders are not parsed until every literal is replaced.
    formula=template
    tokens=list(dict.fromkeys(re.findall(r'(?<=[,(])[CMS][0-9]+(?=[,)])',template)))
    literals={token:str(rng.choice({'C':CONSTANTS,'M':MASKS,'S':SHIFTS}[token[0]])) for token in tokens}
    # Unique template-node bindings are sampled independently. A copied shared
    # subtree retains token IDs and therefore exactly the same literal values.
    formula=re.sub(r'(?<=[,(])([CMS][0-9]+)(?=[,)])',lambda m:literals[m[1]],formula)
    node=parse_formula(formula)
    def fix(n):
        if not n.children:return n.canonical()
        children=[fix(c) for c in n.children]
        if n.value in ('slli','srli','srai'):children[-1]=str(int(children[-1])%32 or 1)
        return str(n.value)+'('+','.join(children)+')'
    return fix(node)

class Generator:
    """Deterministic bounded stream; no label, prediction or estimator argument."""
    def __init__(self,consumed,*,families=FAMILIES_PER_STRATUM):
        if type(families) is not int or not 1<=families<=FAMILIES_PER_STRATUM:raise ValueError('Invalid family budget')
        self.families=families;self.rng={s:random.Random(seed) for s,seed in SEEDS.items()}
        self.blocked=set().union(*(identity_keys(f) for f in consumed)) if consumed else set()
        self.draws=Counter();self.rejections=[]
    def family(self,scope,stratum,slot):
        if scope not in SEEDS or stratum not in STRATA:raise ValueError('Unknown scope or stratum')
        rng=self.rng[scope];family_id=f'v6_{scope}_{stratum}_{slot:02d}'
        for _ in range(MAX_FAMILY_DRAWS):
            self.draws[(scope,stratum,slot)]+=1;attempt=self.draws[(scope,stratum,slot)]
            template=_shape(stratum,rng);formulas=[_instantiate(template,rng) for _ in range(VARIANTS)]
            if len(set(formulas))!=VARIANTS or any(tree_operations(f)>MAX_TREE_OPERATIONS or formula_shape(f)[1]!=2 for f in formulas):
                self.rejections.append({'scope':scope,'family_id':family_id,'attempt':attempt,'formulas':formulas,'reason':'shape budget or identical variants'});continue
            keys=[identity_keys(f) for f in formulas]
            if any(k&self.blocked for k in keys):
                self.rejections.append({'scope':scope,'family_id':family_id,'attempt':attempt,'formulas':formulas,'reason':'consumed or acquired identity/skeleton overlap'});continue
            self.blocked.update(set.union(*keys))
            return [{'benchmark':f'v6_{scope}_{stratum}','candidate_id':candidate_id(f'v6_{scope}_{stratum}',f),
              'formula':f,'stratum':stratum,'evaluation_scope':scope,'structural_family_id':family_id,
              'variant_index':i,'generation_attempt':attempt,'tree_operations':tree_operations(f),
              'size':formula_shape(f)[0],'runs':1,'places':1,'saved':0,'saved_percent':0,
              'provenance':'fixed-seed random synthetic grammar, input-only structural-family acquisition',**signatures(f)} for i,f in enumerate(formulas)]
        raise ValueError(f'Bounded family acquisition exhausted: {family_id}')
    def generate(self):
        return {scope:[r for stratum in STRATA for slot in range(self.families) for r in self.family(scope,stratum,slot)] for scope in SEEDS}
    def replace(self,cohorts,rejections):
        bad={(r['scope'],r['family_id']) for r in rejections};result={}
        for scope,rows in cohorts.items():
            result[scope]=[]
            for offset in range(0,len(rows),VARIANTS):
                pair=rows[offset:offset+VARIANTS];row=pair[0]
                if (scope,row['structural_family_id']) in bad:
                    pair=self.family(scope,row['stratum'],int(row['structural_family_id'].rsplit('_',1)[1]))
                result[scope].extend(pair)
        return result


def validate_inputs(corpus_root, repo_root=None):
    """Recheck input freezes, bytes, runtime sources and strong grouping only.

    Returns the frozen seal/cohorts/records/component maps without reading any
    label, prediction, estimator or measurement file.
    """
    from pathlib import Path
    root=Path(corpus_root).resolve()
    repo=Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
    def read(p):return json.loads(p.read_text())
    def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    seal=read(root/'input-seal.json');manifest=read(root/'consumed-manifest.json')
    if seal['status']!='sealed-inputs-only' or seal['schema']!='isaforge-v6-input-seal-v1':raise ValueError('Sealed V6 inputs required')
    if seal['consumed_manifest_sha256']!=file_sha(root/'consumed-manifest.json'):raise ValueError('Consumed input manifest changed')
    for name,key in (('acquisition-history.json','acquisition_history_sha256'),('consumed-features.json','consumed_features_sha256'),
                     ('acquisition-plan.json','acquisition_plan_sha256'),('generation-rejections.json','generation_rejections_sha256')):
        if seal[key]!=file_sha(root/name):raise ValueError('Input acquisition evidence changed: '+name)
    for name,expected in seal['attempt_files_sha256'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or not name.startswith('attempts/'):raise ValueError('Attempt identity must be relative to attempts')
        if file_sha(root/p)!=expected:raise ValueError('Input attempt evidence changed: '+name)
    required={'isaforge/v6_corpus.py','scripts/prepare_v6_inputs.py','docs/v6-protocol.md','isaforge/area_model_v6.py','isaforge/mapping_features_v6.py'}
    if not required<=set(seal['source_sha256']):raise ValueError('Incomplete frozen acquisition/runtime sources')
    for name,expected in seal['source_sha256'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:raise ValueError('Source identity must be repository relative')
        if file_sha(repo/p)!=expected:raise ValueError('Input/runtime source changed: '+name)
    for source in manifest['sources']:
        source_path=repo/source['path'];freeze_path=repo/source['freeze_path']
        if file_sha(freeze_path)!=source['freeze_sha256']:raise ValueError('Original consumed input freeze changed')
        original=read(freeze_path)
        recorded={(freeze_path.parent/r['path']).resolve():r['sha256'] for r in original['files']}
        if recorded.get(source_path.resolve())!=source['sha256'] or file_sha(source_path)!=source['sha256']:
            raise ValueError('Consumed input source differs from original freeze')
    consumed=[{'formula':f} for f in manifest['formulas']]
    if len(consumed)!=manifest['canonical_unique_count']:raise ValueError('Consumed formula count differs')
    consumed_features=read(root/'consumed-features.json');cohorts={};records={};components={};freezes={};feature_columns=None
    for scope in SEEDS:
        folder=root/scope;freeze=read(folder/'freeze.json');freezes[scope]=freeze
        if freeze['schema']!='isaforge-v6-input-freeze-v1' or freeze['status']!='sealed-inputs-only' or freeze['scope']!=scope:
            raise ValueError('Cohort input freeze differs')
        for name,key in (('candidates.json','candidate_sha256'),('features.json','features_sha256'),('components.json','components_sha256')):
            if file_sha(folder/name)!=freeze[key]:raise ValueError('Frozen cohort file changed: '+scope+'/'+name)
        if freeze['seal_sha256']!=file_sha(root/'input-seal.json') or freeze['consumed_manifest_sha256']!=file_sha(root/'consumed-manifest.json'):
            raise ValueError('Cohort input seal provenance differs')
        if freeze['source_sha256']!=seal['source_sha256'] or freeze['frozen_tool']!=seal['frozen_tool']:
            raise ValueError('Cohort input source/tool identity differs')
        cohorts[scope]=read(folder/'candidates.json');features=read(folder/'features.json');records[scope]=features['records']
        components[scope]=read(folder/'components.json')['component_by_formula']
        if any('lut4_count' in r or 'predicted_lut4' in r for r in cohorts[scope]):raise ValueError('Acquisition candidates cannot contain labels/predictions')
        if len(cohorts[scope])!=192 or freeze['candidate_count']!=192:raise ValueError('Exactly192 inputs per scope required')
        if len(features['columns'])!=336 or features['columns']!=freeze['feature_columns']:raise ValueError('Full336 feature schema required')
        if feature_columns is not None and features['columns']!=feature_columns:raise ValueError('Cross-cohort feature columns differ')
        feature_columns=features['columns']
        if any(r.get('v5_values')!=r['values'][:313] for r in records[scope]):raise ValueError('V5 identity feature prefix differs')
        if freeze['stratum_component_counts']!=seal['stratum_component_counts'][scope]:raise ValueError('Frozen component coverage differs')
    if consumed_features['columns']!=feature_columns:raise ValueError('Consumed feature schema differs')
    rebuilt=inspect_seal(consumed,cohorts,consumed_features['records'],records)
    if rebuilt['status']!='sealed':raise ValueError('Frozen inputs fail independence seal')
    for key in ('component_by_formula','scope_counts','stratum_component_counts','consumed_formula_count','cross_cohort_component_count'):
        if rebuilt[key]!=seal[key]:raise ValueError('Frozen component seal replay differs: '+key)
    for scope,rows in cohorts.items():
        if components[scope]!={r['formula']:seal['component_by_formula'][r['formula']] for r in rows}:raise ValueError('Frozen cohort component map differs')
    return {'seal':seal,'cohorts':cohorts,'records':records,'components':components,'freezes':freezes,'columns':feature_columns}
