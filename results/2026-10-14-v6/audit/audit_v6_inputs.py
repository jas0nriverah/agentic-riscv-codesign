#!/usr/bin/env python3
"""Read-only independent V6 input-seal replay. No model, label or tool call."""
import argparse,hashlib,json,math
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(repo,root):
    import sys
    sys.path.insert(0,str(repo))
    from isaforge.features import parse_formula,candidate_id
    from isaforge.structural_features_v4 import normalize_formula as v4norm
    from isaforge.structural_features_v5 import normalize_formula as v5norm
    from isaforge.graph_features_v5 import _normalized_root
    from isaforge.mapping_features_v6 import FEATURE_NAMES
    from isaforge.area_model_v5 import columns as v5columns
    def skeleton(n):return str(n.value)+'('+','.join(skeleton(c) for c in n.children)+')' if n.children else 'C' if isinstance(n.value,int) else 'I'
    def commute(n):
        if not n.children:return str(n.value)
        parts=[commute(c) for c in n.children]
        if n.value in ('add','and','or','xor','mul','mulh','mulhu'):parts.sort()
        return str(n.value)+'('+','.join(parts)+')'
    def ops(n):return int(bool(n.children))+sum(ops(c) for c in n.children)
    seal=read(root/'input-seal.json');consumed=read(root/'consumed-manifest.json');old=read(root/'consumed-features.json')
    assert seal['status']=='sealed-inputs-only' and seal['consumed_manifest_sha256']==sha(root/'consumed-manifest.json')
    assert seal['consumed_features_sha256']==sha(root/'consumed-features.json')
    for name,key in [('acquisition-plan.json','acquisition_plan_sha256'),('generation-rejections.json','generation_rejections_sha256'),('acquisition-history.json','acquisition_history_sha256')]:assert seal[key]==sha(root/name)
    for name,h in seal['attempt_files_sha256'].items():assert sha(root/name)==h
    for name,h in seal['source_sha256'].items():assert sha(repo/name)==h
    frozen_vectors={}
    for source in consumed['sources']:
        p=repo/source['path'];f=repo/source['freeze_path'];assert sha(p)==source['sha256'] and sha(f)==source['freeze_sha256']
        ledger={(f.parent/e['path']).resolve():e['sha256'] for e in read(f)['files']};assert ledger[p.resolve()]==sha(p)
        for r in read(p)['records']:
            if r['formula'] in frozen_vectors:assert r['values']==frozen_vectors[r['formula']]
            frozen_vectors[r['formula']]=r['values']
    assert len(frozen_vectors)==consumed['canonical_unique_count']==2380
    assert set(frozen_vectors)==set(consumed['formulas'])
    for r in old['records']:assert r['values'][:313]==frozen_vectors[r['formula']]
    assert len(old['records'])==2380 and {r['formula'] for r in old['records']}==set(frozen_vectors)
    expected_columns=list(v5columns())+['mapping_'+n for n in FEATURE_NAMES]
    assert old['columns']==expected_columns
    rows={};records={};components={};all_formulas=set(frozen_vectors);all_records=list(old['records']);owners={f:'consumed' for f in frozen_vectors}
    for scope in ('calibration','test'):
        folder=root/scope;freeze=read(folder/'freeze.json');r=read(folder/'candidates.json');features=read(folder/'features.json');comp=read(folder/'components.json')
        assert freeze['scope']==scope and freeze['status']=='sealed-inputs-only'
        for name,key in [('candidates.json','candidate_sha256'),('features.json','features_sha256'),('components.json','components_sha256')]:assert freeze[key]==sha(folder/name)
        assert freeze['seal_sha256']==sha(root/'input-seal.json') and freeze['source_sha256']==seal['source_sha256']
        assert freeze['frozen_tool']==seal['frozen_tool'] and freeze['consumed_manifest_sha256']==sha(root/'consumed-manifest.json')
        assert features['columns']==freeze['feature_columns']==expected_columns
        assert len(r)==len(features['records'])==192
        assert Counter(v['stratum'] for v in r)==Counter({s:24 for s in seal['stratum_component_counts'][scope]})
        assert len(set(v['formula'] for v in r))==192 and not {v['formula'] for v in r}&all_formulas
        assert [v['formula'] for v in features['records']]==[v['formula'] for v in r]
        families=defaultdict(list)
        for v,rec in zip(r,features['records']):
            f=v['formula'];assert candidate_id(v['benchmark'],f)==v['candidate_id'];node=parse_formula(f)
            assert node.canonical()==f and 'in0' in f and 'in1' in f and ops(node)<=15
            assert not {'lut4_count','carry_count','predicted_lut4'}&v.keys()
            assert rec['v5_values']==rec['values'][:313] and len(rec['values'])==336
            assert all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in rec['values'])
            families[v['structural_family_id']].append(v);owners[f]=scope
        assert len(families)==96
        for pair in families.values():assert len(pair)==2 and {v['variant_index'] for v in pair}=={0,1} and len({skeleton(parse_formula(v['formula'])) for v in pair})==1
        rows[scope]=r;records[scope]=features['records'];components[scope]=comp['component_by_formula'];all_records+=features['records'];all_formulas.update(v['formula'] for v in r)
    assert len(all_records)==len(all_formulas)==2764
    parent={f:f for f in all_formulas};seen={}
    def find(f):
        while parent[f]!=f:parent[f]=parent[parent[f]];f=parent[f]
        return f
    for r in all_records:
        f=r['formula'];current=_normalized_root(v5norm(f));assert r['normalized_formula']==current
        forms={f,v4norm(f),current};keys={('formula',v) for v in forms}
        keys|={('skeleton',skeleton(parse_formula(v))) for v in forms}
        keys|={('equivalence',commute(parse_formula(v4norm(v)))) for v in forms}
        keys|={('v5vector',tuple(r['values'][:313])),('v6vector',tuple(r['values']))}
        for key in keys:
            if key in seen:
                a,b=find(f),find(seen[key]);parent[max(a,b)]=min(a,b)
            else:seen[key]=f
    members=defaultdict(list)
    for f in all_formulas:members[find(f)].append(f)
    ids={k:hashlib.sha256((json.dumps(sorted(v),sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest() for k,v in members.items()}
    freshids={};counts={};sizes={};tree_range={}
    for scope,r in rows.items():
        freshids[scope]=set();bystratum=defaultdict(set);bygroup=defaultdict(list)
        for v in r:
            f=v['formula'];g=ids[find(f)];assert g==components[scope][f]==seal['component_by_formula'][f]
            group=members[find(f)];assert len(group)==2 and {owners[q] for q in group}=={scope}
            freshids[scope].add(g);bystratum[v['stratum']].add(g);bygroup[g].append(v['stratum'])
        assert all(len(set(s))==1 for s in bygroup.values());counts[scope]={s:len(g) for s,g in bystratum.items()}
        assert counts[scope]==seal['stratum_component_counts'][scope] and set(counts[scope].values())=={12}
        sizes[scope]=dict(Counter(len(v) for v in bygroup.values()))
        tree_range[scope]=[min(ops(parse_formula(v['formula'])) for v in r),max(ops(parse_formula(v['formula'])) for v in r)]
    assert not freshids['calibration']&freshids['test']
    return {'status':'passed','audit_source_sha256':sha(Path(__file__)),'input_seal_sha256':sha(root/'input-seal.json'),
      'consumed_unique':2380,'fresh_formulas':384,'scope_rows':{s:len(r) for s,r in rows.items()},'strong_components_per_stratum':counts,
      'component_size_distribution':sizes,'tree_operation_ranges':tree_range,'cross_cohort_components':0,
      'normalized_skeleton_equivalence_and_both_vector_identity_replay':True,'all_source_and_attempt_hashes_verified':True,
      'labels_read':0,'models_or_predictions_read':0,'hardware_calls':0,
      'limitations':['Sufficient input/skeleton/vector grouping cannot prove full functional nonequivalence.',
      'Twelve structural grammar components per stratum do not prove independent application families or exchangeability.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.repo.resolve(),a.corpus.resolve());a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))
