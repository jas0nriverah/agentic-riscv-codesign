"""Same-chain coverage, multi-chain abstention and prospective fixed cohorts."""
import importlib.util
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('abstention',Path(__file__).parents[1]/'scripts/abstain_boundary_coverage.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
SUPPORT={'supported_cells':['narrow_unshared','narrow_shared','wide_unshared']}


def test_formula_only_training_support_matches_frozen_inputs():
 rows=r.read(r.previous.OUT/'training-manifest.json')['rows']
 result=r.derive_support([row['formula'] for row in rows])
 assert result['training_formula_count']==1857 and result['eligible_formula_count']==32 and result['eligible_chain_count']==32
 assert result['cell_counts']=={'narrow_shared':4,'narrow_unshared':8,'wide_unshared':20}
 assert result['supported_cells']==SUPPORT['supported_cells'] or set(result['supported_cells'])==set(SUPPORT['supported_cells'])


def test_mixed_chains_cannot_fabricate_supported_cell_from_aggregate_features():
 f='xor(add(sra(slli(andi(addi(xori(in0,7),11),255),24),andi(xori(in1,13),1)),sra(addi(xori(in1,13),7),in0)),or(in0,in1))'
 cells=r.chain_cells(f)
 assert [c['cell'] for c in cells]==['narrow_unshared','wide_shared']
 old=r.local.features(f)
 assert old[10]==8 and old[7]==1 # Aggregate shortcut would falsely imply narrow/shared.
 p,d=r.guard([f],[128.],[145.],SUPPORT)
 assert p==[145.] and d[0]['unsupported_cells']==['wide_shared'] and d[0]['blocked_caps']==[128]


def test_width17_is_wide_and_width16_narrow_without_label_or_margin_rules():
 template='xor(add(sra(andi(addi(xori(in0,7),11),{mask}),in1),in0),and(in0,in1))'
 assert r.chain_cells(template.format(mask=65535))[0]['cell']=='narrow_unshared'
 assert r.chain_cells(template.format(mask=131071))[0]['cell']=='wide_unshared'


def test_supported_narrow_change_preserved_but_fullword_shared_override_abstains():
 narrow='xor(add(sra(slli(andi(addi(xori(or(in0,in1),7),11),255),24),in1),in0),or(in0,in1))'
 wide='xor(add(sra(addi(xori(xor(in0,in1),7),11),in1),xor(in0,in1)),and(in0,in1))'
 p,d=r.guard([narrow,wide],[128.,128.],[141.7,131.94],SUPPORT)
 assert p==[128.,131.94] and d[0]['supported_new_caps']==[128] and d[1]['blocked_caps']==[128]


def fixture():
 pool=[{'cohort':'general','reserved_control':i>=24,'template':'general'} for i in range(32)]
 pool +=[{'cohort':'unsupported','reserved_control':False,'template':'unsupported'} for _ in range(8)]
 pool +=[{'cohort':'challenge','reserved_control':False,'template':'a' if i%2==0 else 'b'} for i in range(88)]
 values={n:[130.]*128 for n in r.NAMES}
 for i in range(40,46):values[r.NAME][i]=128.
 details={'coverage_guard':[{'blocked_caps':[128] if 32<=i<40 else []} for i in range(128)]}
 freshness={'representations':{k:{'cluster_representatives':list(range(128)),'historical_matches':[]} for k in ('coverage','augmented')}}
 return pool,values,details,freshness


def test_fixed40_retained_and_both_supported_and_blocked_activity_predeclared():
 pool,v,d,f=fixture();s=r.choose(pool,v,d,f);cov=r.coverage(pool,v,d,s,f)
 assert s['selected_pool_indices'][:40]==list(range(40)) and s['selected_active_pool_indices']==list(range(40,46))
 assert cov['passed'] and cov['blocked_override_count']==8
 d['coverage_guard']=[{'blocked_caps':[]} for _ in range(128)]
 assert not r.coverage(pool,v,d,s,f)['checks']['at_least_one_fixed_blocked_override']


def test_freshness_in_either_representation_excludes_without_replacing_fixed_rows():
 pool,v,d,f=fixture();f['representations']['augmented']['historical_matches']=[40]
 f['representations']['coverage']['cluster_representatives'][41]=32
 s=r.choose(pool,v,d,f)
 assert s['selected_active_pool_indices']==[42,43,44,45] and s['selected_pool_indices'][:40]==list(range(40))
 assert s['historical_collision_active_pool_indices']==[40] and s['fixed_collision_active_pool_indices']==[41]


def test_abstention_cannot_hide_new_false_rejection_or_loss_of_learned_accuracy():
 values={n:[130.] for n in r.NAMES};values[r.CURRENT]=[128.];values[r.LEARNED]=[128.];values[r.BUDGET]=[140.]
 metrics=r.panel_metrics({'actual_lut4':[125.],'models':values})
 assert not metrics['checks']['caps']['128']['false_reject_no_worse_signed']
 assert not metrics['checks']['accuracy_no_worse'][r.LEARNED]['mae_lut4']
 assert not r.passed(metrics['checks'])
