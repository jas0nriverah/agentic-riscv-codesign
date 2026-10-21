"""Source relocation provenance must survive automatic instruction lowering."""
import copy
from pathlib import Path

import pytest

from isaforge import relocation_guard as guard, codesign as c


@pytest.mark.parametrize('assembly',[
    'lui s0,%hi(a)','addi s0,s0,%lo(a)',
    'auipc t0,%pcrel_hi(.LC0)','addi t0,t0,%pcrel_lo(.L0)',
    'lui a5,%hi(_ctype_+1)','addi a5,a5,%lo(_ctype_+1)',
    'lui t0,%tprel_hi(tls)','addi a0,a0,a',
    'li a0,symbol','lui a0,symbol+4','auipc a0,0',
    'addi a0,a0,4; add a0,a0,a1','addi a0,a0,4\nadd a0,a0,a1',
    'addi a0,a0,4 # comment\nadd a0,a0,a1',
    'lw a0,0(a1)','jal ra,function','addi invalid,a0,4',
])
def test_symbolic_pc_relative_and_unsupported_source_is_rejected(assembly):
    assert guard.statement_issue(assembly) is not None


@pytest.mark.parametrize('assembly',[
    'lui s0,4096','lui x5,0x12345','li a0,-42','addi s0,s0,-2048',
    'slli a0,a0,2','srai a0,a0,31','andi a5,a0,0xff',
    'add a0,a0,a1','sltu a0,a0,zero','mv a0,s1','not a0,a1',
    'neg a0,a1','seqz a0,a0','snez a0,a0','zext.b a0,a0',
    'addi a0,a0,4 # comment mentioning %hi(symbol)',
])
def test_literal_operations_and_register_pointer_inputs_remain_eligible(assembly):
    assert guard.statement_issue(assembly) is None


def fixture():
    sites=[dict(site=0,assembly='lui s0,%hi(a)',function='benchmark'),
           dict(site=1,assembly='addi s0,s0,%lo(a)',function='benchmark'),
           dict(site=2,assembly='slli a0,a0,2',function='benchmark'),
           dict(site=3,assembly='add a0,a0,s0',function='benchmark')]
    unsafe=dict(name='address',formula='addi(lui(4096),1860)',occurrences=[dict(sites=[0,1])])
    safe=dict(name='offset',formula='add(in0,slli(in1,2))',occurrences=[dict(sites=[2,3])])
    return sites,unsafe,safe


def test_assess_only_removed_statements_so_preserved_symbolic_inputs_are_safe():
    sites,unsafe,safe=fixture()
    checked=guard.assess_candidate(unsafe,sites)
    assert not checked['safe'] and [r['site'] for r in checked['unsafe_sites']]==[0,1]
    assert guard.require_relocation_free(safe,sites)['safe']
    with pytest.raises(ValueError,match='relocatable'):
        guard.require_relocation_free(unsafe,sites)


def test_filter_requires_fresh_shortlisting_and_preserves_original_evidence():
    sites,unsafe,safe=fixture()
    source=dict(executable_candidates=[unsafe,safe],executable_formula_count=2,
                pool=[unsafe],pool_rule='old rule',selected_rank_indices=[0],
                eligible_formula_count=2,excluded_uncalibrated_formulas=[])
    before=copy.deepcopy(source)
    result=guard.filter_executable_candidates(source,sites)
    assert source==before
    assert [r['name'] for r in result['executable_candidates']]==['offset']
    assert result['executable_formula_count']==1
    assert result['relocation_guard']['rejected_count']==1
    assert all(key not in result for key in ('pool','pool_rule','selected_rank_indices',
                                            'eligible_formula_count','excluded_uncalibrated_formulas'))
    result['executable_candidates'][0]['name']='modified copy'
    assert source==before


@pytest.mark.parametrize('bad',[
    dict(occurrences=[dict(sites=[0,99])]),
    dict(occurrences=[dict(sites=[0,0])]),
    dict(occurrences=[dict(sites=[0,1]),dict(sites=[1,2])]),
    dict(occurrences=[]),dict(occurrences=[dict(sites=[True])]),
])
def test_missing_or_overlapping_sites_fail_closed(bad):
    with pytest.raises(ValueError):
        guard.assess_candidate(bad,fixture()[0])


def test_recorded_edn_failure_is_identified_without_changing_any_pool():
    root=c.ROOT/'generated/extended-edn-2026-10-20'
    if not (root/'discovery/discovery.json').exists():
        pytest.skip('Preserved local processor evidence is not restored')
    before=c.sha(root/'discovery/discovery.json')
    result=guard.audit_root(root)
    candidate=next(row for row in result['frozen_pool'] if row['name']=='candidate_17')
    assert not candidate['safe']
    assert [row['site'] for row in candidate['unsafe_sites']]==[533,544]
    failure=root/'measurements/candidate_17/attempt-000'
    raw=c.read(failure/'simulation/simulation.json')
    validation=c.read(failure/'firmware/validation.json')
    assert raw['first_violation']['kind']=='ram-write'
    assert raw['first_violation']['address']==5956
    assert validation['program_and_bss_end']==5952
    original=(root/'discovery/attempt-000/marked/symbols.txt').read_text().splitlines()
    rewritten=(failure/'firmware/symbols.txt').read_text().splitlines()
    assert any(row.split()[-1]=='a' for row in original)
    assert not any(row.split()[-1]=='a' for row in rewritten)
    assert c.sha(root/'discovery/discovery.json')==before
