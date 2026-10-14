"""Exact handgraph checks for bounded structural descriptors, not LUT labels."""
from copy import deepcopy
import pytest
from isaforge.mapping_features_v6 import analyze,feature_dict,feature_vector,FEATURE_NAMES,CUT_BUDGET


def graph(cells,outputs,inputs=(1,2,3,4,5,6)):
    kinds={'and':('A','B'),'xor':('A','B'),'or':('A','B'),'not':('A',),'mux':('A','B','S')}
    records={}
    for out,kind,pins in cells:
        conn=dict(zip(kinds[kind],([p] for p in pins)));conn['Y']=[out]
        records[str(out)]={'type':'$_'+kind.upper()+'_','connections':conn,
            'port_directions':{p:'output' if p=='Y' else 'input' for p in conn}}
    return {'modules':{'candidate':{'ports':{'in':{'direction':'input','bits':list(inputs)},
        'result':{'direction':'output','bits':outputs}},'cells':records}}}


def test_empty_wire_constant_and_constant_only_gate():
    value=feature_dict(graph([],['0','1',1]))
    assert all(v==0 for v in value.values())
    result=analyze(graph([(7,'and',('0','1'))],[7]))
    assert result['selected_cuts'][7]==frozenset()
    assert result['values']['cuts_size0_count']==1
    assert result['values']['selected_cover_gate_count']==1  # no constant folding


def test_four_input_chain_fits_one_structural_cut():
    result=analyze(graph([(7,'and',(1,2)),(8,'xor',(7,3)),(9,'or',(8,4))],[9]))
    assert frozenset((1,2,3,4)) in result['cuts'][9]
    assert result['depth'][9]==1
    assert result['values']['selected_cover_gate_count']==1
    assert result['output_mffc_sizes']==[3]


def test_five_inputs_require_two_cut_levels():
    result=analyze(graph([(7,'and',(1,2)),(8,'xor',(7,3)),(9,'or',(8,4)),(10,'and',(9,5))],[10]))
    assert result['depth'][10]==2
    assert all(len(c)<=4 for values in result['cuts'].values() for c in values)
    assert all(len(values)<=CUT_BUDGET for values in result['cuts'].values())


def test_reconvergence_and_exact_output_mffc_reference_counts():
    cells=[(7,'and',(1,2)),(8,'xor',(7,3)),(9,'or',(7,4)),(10,'and',(8,9))]
    result=analyze(graph(cells,[10]))
    assert result['output_mffc_sizes']==[4]  # shared7 becomes removable after8 and9
    assert result['values']['reconvergent_input_support_gate_fraction']==.25
    assert result['values']['shared_internal_gate_fraction']==.25
    assert result['values']['shared_output_cone_gate_fraction']==0


def test_multioutput_reuse_aliases_and_external_output_reference():
    cells=[(7,'and',(1,2)),(8,'xor',(7,3)),(9,'or',(7,4))]
    result=analyze(graph(cells,[8,9]))
    assert result['output_mffc_sizes']==[1,1]
    assert result['values']['shared_output_cone_gate_fraction']==pytest.approx(1/3)
    assert feature_dict(graph(cells,[8,8,9]))==result['values']
    assert analyze(graph(cells,[7,8,9]))['output_mffc_sizes']==[1,1,1]


def test_deterministic_order_and_unreachable_logic():
    cells=[(7,'and',(1,2)),(8,'xor',(7,3)),(9,'or',(4,5))]
    a=feature_dict(graph(cells,[8]));b=feature_dict(graph(list(reversed(cells)),[8]))
    assert a==b and a['unreachable_gate_count']==1
    assert len(feature_vector(graph(cells,[8])))==len(FEATURE_NAMES)


@pytest.mark.parametrize('broken', ['cycle','unsupported','undriven','undefined','driver'])
def test_invalid_graphs_fail_closed(broken):
    net=graph([(7,'and',(1,2)),(8,'xor',(7,3))],[8])
    c=net['modules']['candidate']['cells']
    if broken=='cycle':c['7']['connections']['A']=[8]
    if broken=='unsupported':c['7']['type']='$_DFF_P_'
    if broken=='undriven':c['7']['connections']['A']=[99]
    if broken=='undefined':c['7']['connections']['A']=['x']
    if broken=='driver':c['8']['connections']['Y']=[7]
    with pytest.raises(ValueError):analyze(net)


def test_real_cut_budget_truncation_and_retained_cut_separation():
    cells=[];frontier=list(range(1,33));next_bit=33
    while len(frontier)>1:
        following=[]
        for a,b in zip(frontier[::2],frontier[1::2]):
            cells.append((next_bit,'and',(a,b)));following.append(next_bit);next_bit+=1
        frontier=following
    result=analyze(graph(cells,frontier,range(1,33)))
    assert result['values']['truncated_gate_count']>0
    assert result['values']['discarded_merge_states']>0
    parents={out:pins for out,_,pins in cells}
    def separates(node,cut):
        if node in cut:return True
        return node in parents and all(separates(p,cut) for p in parents[node])
    for root,values in result['cuts'].items():
        assert len(values)<=CUT_BUDGET
        assert all(len(c)<=4 and separates(root,c) for c in values)


def test_budget_can_exhaust_partial_combinations_but_direct_cut_survives(monkeypatch):
    import isaforge.mapping_features_v6 as mapping
    monkeypatch.setattr(mapping,'CUT_BUDGET',1)
    cells=[(7,'and',(1,2)),(8,'and',(7,3)),(9,'and',(8,4)),(10,'not',(5,)),(11,'and',(9,10))]
    result=mapping.analyze(graph(cells,[11]))
    assert result['values']['direct_fanin_fallback_count']>0
    assert result['selected_cuts'][11]==frozenset((9,10))
    assert result['depth'][11]==2


def test_long_chain_is_iterative_and_exact_structural_mffc():
    cells=[(bit,'not',((1 if bit==7 else bit-1),)) for bit in range(7,1507)]
    result=analyze(graph(cells,[1506]))
    assert result['reachable_gate_count']==1500
    assert result['output_mffc_sizes']==[1500]
    assert result['values']['selected_cover_gate_count']==1
