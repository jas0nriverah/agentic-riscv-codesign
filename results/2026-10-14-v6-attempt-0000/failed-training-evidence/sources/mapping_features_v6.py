"""Bounded four-leaf cut/reuse descriptors of existing generic bit-level DAGs.

Inspired by established priority-cut/area-flow mapping methods. This module does
not map technology, optimize Boolean functions, estimate dedicated carries, or
claim an optimal LUT count. Only AND/OR/XOR/NOT/MUX single-bit cells are accepted.
Eight retained nontrivial cuts and eight partial merge states are fixed budgets;
all truncation is visible. Counts describe the chosen generic implementation.
"""
from __future__ import annotations
from collections import Counter
import heapq
import itertools

CUT_SIZE=4
CUT_BUDGET=8
PRIMITIVES={'$_AND_':('A','B'),'$_OR_':('A','B'),'$_XOR_':('A','B'),
            '$_NOT_':('A',),'$_MUX_':('A','B','S')}
FEATURE_NAMES=(
    'retained_cut_count','cuts_size0_count','cuts_size1_count','cuts_size2_count','cuts_size3_count','cuts_size4_count',
    'alternative_cuts_mean','selected_cut_leaves_mean','selected_cut_depth_max','output_cut_depth_mean',
    'area_flow_output_sum','area_flow_output_mean','selected_cover_gate_count',
    'shared_output_cone_gate_fraction','exclusive_output_cone_gate_fraction','shared_internal_gate_fraction',
    'reconvergent_input_support_gate_fraction','output_mffc_size_mean','output_mffc_size_max',
    'truncated_gate_count','discarded_merge_states','direct_fanin_fallback_count','unreachable_gate_count')


def _graph(netlist):
    if set(netlist.get('modules',{}))!={'candidate'}:raise ValueError('Expected one flattened candidate module')
    module=netlist['modules']['candidate'];inputs=set();outputs=[]
    for port in module.get('ports',{}).values():
        if port.get('direction') not in ('input','output'):raise ValueError('Unsupported graph port direction')
        for bit in port['bits']:
            if type(bit) is not int and bit not in ('0','1'):raise ValueError('Undefined graph bit')
            if port['direction']=='input':
                if type(bit) is not int:raise ValueError('Constant primary input')
                inputs.add(bit)
            else:outputs.append(bit)
    drivers={}
    for cell in module.get('cells',{}).values():
        kind=cell['type'];pins=PRIMITIVES.get(kind)
        if pins is None:raise ValueError(f'Unsupported generic primitive {kind}')
        expected={*pins,'Y'}
        if set(cell['connections'])!=expected or set(cell['port_directions'])!=expected:
            raise ValueError('Primitive port schema mismatch')
        for port in expected:
            if len(cell['connections'][port])!=1 or cell['port_directions'][port]!=('output' if port=='Y' else 'input'):
                raise ValueError('Expected single-bit primitive pins')
        out=cell['connections']['Y'][0]
        if type(out) is not int or out in inputs or out in drivers:raise ValueError('Invalid or multiple graph driver')
        drivers[out]=tuple(cell['connections'][p][0] for p in pins)
    for bit in [*outputs,*(b for pins in drivers.values() for b in pins)]:
        if type(bit) is int:
            if bit not in inputs and bit not in drivers:raise ValueError('Undriven graph bit')
        elif bit not in ('0','1'):raise ValueError('Undefined graph constant')
    # Kahn traversal rejects cycles even in disconnected logic and avoids Python
    # recursion-depth dependence on long arithmetic chains.
    consumers={b:set() for b in drivers};indegree={}
    for out,pins in drivers.items():
        parents={b for b in pins if b in drivers}
        indegree[out]=len(parents)
        for b in parents:consumers[b].add(out)
    ready=[b for b,d in indegree.items() if d==0];heapq.heapify(ready);order=[]
    while ready:
        bit=heapq.heappop(ready);order.append(bit)
        for consumer in sorted(consumers[bit]):
            indegree[consumer]-=1
            if indegree[consumer]==0:heapq.heappush(ready,consumer)
    if len(order)!=len(drivers):raise ValueError('Cyclic combinational graph')
    roots=sorted({b for b in outputs if b in drivers});reachable=set(roots)
    for bit in reversed(order):
        if bit in reachable:reachable.update(b for b in drivers[bit] if b in drivers)
    return inputs,outputs,{b:drivers[b] for b in order if b in reachable},len(drivers)-len(reachable)


def analyze(netlist):
    inputs,outputs,drivers,unreachable=_graph(netlist)
    roots=sorted({b for b in outputs if b in drivers});order=list(drivers)
    fanout=Counter(b for pins in drivers.values() for b in set(pins) if type(b) is int)
    fanout.update(roots)  # Duplicate output aliases represent one physical root.
    cuts={b:(frozenset((b,)),) for b in inputs};depth={b:0 for b in inputs};flow={b:0. for b in inputs}
    supports={b:1<<i for i,b in enumerate(sorted(inputs))}
    selected={};retained={};truncated=set();discarded=0;reconvergent=0;fallbacks=0

    def rank(cut):
        return (max((depth[b] for b in cut),default=0),len(cut),sum(flow[b] for b in cut),tuple(sorted(cut)))

    def prune(states,node):
        nonlocal discarded
        # Subset dominance is structural only; no logical don't-cares implied.
        kept=[]
        for cut in sorted(states,key=lambda c:(len(c),tuple(sorted(c)))):
            if not any(old<=cut for old in kept):kept.append(cut)
        kept.sort(key=rank)
        if len(kept)>CUT_BUDGET:
            truncated.add(node);discarded+=len(kept)-CUT_BUDGET;kept=kept[:CUT_BUDGET]
        return kept

    for bit,pins in drivers.items():
        variables=sorted({b for b in pins if type(b) is int})
        states=[frozenset()]
        for parent in variables:
            merged={a|b for a,b in itertools.product(states,cuts[parent]) if len(a|b)<=CUT_SIZE}
            states=prune(merged,bit)
        # Always retain eligibility of the direct fanin cut. Partial-budget
        # pruning can discard combinations needed by later fanins.
        if not states:fallbacks+=1
        states=prune(set(states)|{frozenset(variables)},bit)
        if not states:raise ValueError('No feasible structural cut in supported graph')
        chosen=states[0];retained[bit]=tuple(states);selected[bit]=chosen
        depth[bit]=1+max((depth[b] for b in chosen),default=0)
        flow[bit]=(1.+sum(flow[b] for b in chosen))/max(fanout[bit],1)
        cuts[bit]=tuple(states)+(frozenset((bit,)),)
        support=0
        for parent in variables:
            if support & supports[parent]:reconvergent+=1;break
            support|=supports[parent]
        supports[bit]=0
        for parent in variables:supports[bit]|=supports[parent]
    # Output ownership is exact reachability for distinct driven output signals.
    ownership={b:0 for b in order}
    for i,b in enumerate(roots):ownership[b]|=1<<i
    for bit in reversed(order):
        for parent in set(drivers[bit]):
            if parent in ownership:ownership[parent]|=ownership[bit]
    shared=sum(mask.bit_count()>1 for mask in ownership.values());count=len(order)
    covered=set();pending=roots.copy()
    while pending:
        bit=pending.pop()
        if bit not in drivers or bit in covered:continue
        covered.add(bit);pending.extend(selected[bit])
    # Exact structural MFFC node counts for each output root, using reference
    # decrements. This is generic gate count, never target mapped local area.
    mffc=[]
    for root in roots:
        removed={root};pending=[root];references={}
        while pending:
            bit=pending.pop()
            for parent in set(drivers[bit]):
                if parent not in drivers:continue
                references[parent]=references.get(parent,fanout[parent])-1
                if references[parent]==0 and parent not in removed:
                    removed.add(parent);pending.append(parent)
        mffc.append(len(removed))
    sizes=Counter(len(c) for values in retained.values() for c in values)
    mean=lambda values:sum(values)/len(values) if values else 0.
    values={'retained_cut_count':sum(map(len,retained.values())),
        **{f'cuts_size{i}_count':sizes[i] for i in range(5)},
        'alternative_cuts_mean':mean([len(c)-1 for c in retained.values()]),
        'selected_cut_leaves_mean':mean([len(c) for c in selected.values()]),
        'selected_cut_depth_max':max((depth[b] for b in order),default=0),
        'output_cut_depth_mean':mean([depth[b] for b in roots]),
        'area_flow_output_sum':sum(flow[b] for b in roots),'area_flow_output_mean':mean([flow[b] for b in roots]),
        'selected_cover_gate_count':len(covered),'shared_output_cone_gate_fraction':shared/count if count else 0.,
        'exclusive_output_cone_gate_fraction':(count-shared)/count if count else 0.,
        'shared_internal_gate_fraction':sum(fanout[b]>1 for b in order)/count if count else 0.,
        'reconvergent_input_support_gate_fraction':reconvergent/count if count else 0.,
        'output_mffc_size_mean':mean(mffc),'output_mffc_size_max':max(mffc,default=0),
        'truncated_gate_count':len(truncated),'discarded_merge_states':discarded,'direct_fanin_fallback_count':fallbacks,'unreachable_gate_count':unreachable}
    return {'values':values,'cuts':retained,'selected_cuts':selected,'depth':depth,'area_flow':flow,
            'output_mffc_sizes':mffc,'reachable_gate_count':count,'cut_budget':CUT_BUDGET,'cut_size':CUT_SIZE}


def feature_dict(netlist):return analyze(netlist)['values']
def feature_vector(netlist):
    values=feature_dict(netlist)
    return [float(values[name]) for name in FEATURE_NAMES]
