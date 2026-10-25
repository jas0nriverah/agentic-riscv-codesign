"""Reject relocatable source operands before freezing future executable pools.

Decoded constants lose symbolic relocation provenance. Removing a statement
such as ``lui s0,%hi(a)`` may both bake in an obsolete address and remove the
last linker reference retaining its data section. This conservative guard uses
the original marked assembly, never measured candidate outcomes. It does not
repair, retry, relabel or modify an existing experiment.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re

from . import assembly_lowering as lowering, codesign as c
from .workload_experiment import verify_cache

SOURCE = 'isaforge/relocation_guard.py'
SCHEMA = 'isaforge-relocation-source-guard-v1'
REGISTERS = frozenset(['zero','ra','sp','gp','tp','fp'] +
    [f'x{i}' for i in range(32)] + [f'a{i}' for i in range(8)] +
    [f's{i}' for i in range(12)] + [f't{i}' for i in range(7)])
LITERAL = re.compile(r'[-+]?(?:0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+)\Z')
REGISTER_OPS = frozenset('add sub and or xor sll srl sra slt sltu'.split())
IMMEDIATE_OPS = frozenset('addi andi ori xori slli srli srai slti sltiu'.split())
UNARY_OPS = frozenset('mv not neg seqz snez sltz sgtz zext.b'.split())


def statement_issue(assembly):
    """Return a rejection reason, or None for closed literal/register grammar.

    Even constant-looking relocation modifiers are rejected. Unrecognized
    grammar fails closed; this is a source-provenance guard, not an assembler.
    AUIPC is always rejected because its semantics depend on instruction PC.
    """
    c.require(isinstance(assembly,str),'Assembly statement must be text')
    if '\n' in assembly or '\r' in assembly:
        return 'not_one_source_statement'
    text=assembly.split('#',1)[0].strip()
    if not text or ';' in text:
        return 'not_one_source_statement'
    if '%' in text:
        return 'relocation_modifier'
    parts=text.split(None,1)
    op=parts[0]
    operands=[item.strip() for item in parts[1].split(',')] if len(parts)==2 else []
    if op=='auipc':
        return 'pc_relative_operation'
    if op in REGISTER_OPS:
        return None if len(operands)==3 and all(r in REGISTERS for r in operands) else 'unsupported_register_operands'
    if op in UNARY_OPS:
        return None if len(operands)==2 and all(r in REGISTERS for r in operands) else 'unsupported_register_operands'
    if op in IMMEDIATE_OPS:
        if len(operands)!=3 or not all(r in REGISTERS for r in operands[:2]):
            return 'unsupported_immediate_operands'
        return None if LITERAL.fullmatch(operands[2]) else 'symbolic_or_unsupported_immediate'
    if op in ('lui','li'):
        if len(operands)!=2 or operands[0] not in REGISTERS:
            return 'unsupported_immediate_operands'
        return None if LITERAL.fullmatch(operands[1]) else 'symbolic_or_unsupported_immediate'
    return 'unsupported_statement_opcode'


def _sites(sites):
    c.require(isinstance(sites,list),'Original mark_assembly site list required')
    table={}
    for row in sites:
        c.require(isinstance(row,dict) and type(row.get('site')) is int and row['site']>=0 and
                  row['site'] not in table and isinstance(row.get('assembly'),str),'Invalid or duplicate source site')
        table[row['site']]=row
    return table


def assess_candidate(candidate,sites):
    """Assess only statements removed by a candidate; register inputs may be pointers.

    ``sites`` is the original list returned by mark_assembly, before lowering.
    Existing lowering legality/mapping checks remain independently required.
    """
    table=_sites(sites)
    c.require(isinstance(candidate,dict) and isinstance(candidate.get('occurrences'),list) and
              candidate['occurrences'],'Executable occurrences required')
    used=set()
    for occurrence in candidate['occurrences']:
        indices=occurrence.get('sites')
        c.require(isinstance(indices,list) and indices and
                  all(type(i) is int and i in table for i in indices),'Candidate references unknown source site')
        c.require(len(set(indices))==len(indices) and used.isdisjoint(indices),'Overlapping source occurrences')
        used.update(indices)
    unsafe=[]
    for index in sorted(used):
        row=table[index]
        issue=statement_issue(row['assembly'])
        if issue is not None:
            unsafe.append(dict(site=index,assembly=row['assembly'],reason=issue,
                               function=row.get('function'),source_line=row.get('source_line')))
    return dict(safe=not unsafe,checked_sites=len(used),unsafe_sites=unsafe,
                rule='Every removed statement must use supported register operands and literal immediates; no symbolic relocation or PC-relative operation.')


def require_relocation_free(candidate,sites):
    result=assess_candidate(candidate,sites)
    c.require(result['safe'],'Candidate removes relocatable or unsupported source operands: '+
              ', '.join(f"{r['site']}:{r['reason']}" for r in result['unsafe_sites']))
    return result


def filter_executable_candidates(extraction,sites):
    """Return a fresh, unshortlisted extraction for future pool selection.

    This deliberately removes the old ``pool`` and its selection metadata: a
    caller must apply its predeclared pool rule to the filtered full list. An
    existing frozen pool must never be silently filtered/reselected in place.
    """
    c.require(isinstance(extraction,dict) and isinstance(extraction.get('executable_candidates'),list),
              'Full executable candidate list required before shortlisting')
    accepted,rejected=[],[]
    for candidate in extraction['executable_candidates']:
        result=assess_candidate(candidate,sites)
        if result['safe']:
            accepted.append(copy.deepcopy(candidate))
        else:
            rejected.append(dict(name=candidate.get('name'),formula=candidate.get('formula'),**result))
    result=copy.deepcopy(extraction)
    for key in ('pool','pool_rule','selected_rank_indices','eligible_formula_count','excluded_uncalibrated_formulas'):
        result.pop(key,None)
    result.update(executable_candidates=accepted,executable_formula_count=len(accepted),
                  relocation_guard=dict(schema=SCHEMA,source_sha256=c.sha(__file__),
                      input_executable_count=len(extraction['executable_candidates']),
                      rejected_count=len(rejected),rejections=rejected))
    return result


def audit_root(root):
    """Read-only re-extraction and source-risk counts; never open candidate labels."""
    root=Path(root).resolve()
    plan=c.unseal(root/'plan.json')
    c.require(c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'],'Invalid context')
    discovery=verify_cache(root/'discovery','discovery.json')
    base_image=root/discovery['baseline_image']
    folder=base_image.parent.parent
    assembly=(folder/'program.s').read_text()
    marked,sites=lowering.mark_assembly(assembly)
    c.require(marked==(folder/'marked.S').read_text(),'Original marked assembly differs')
    site_map=lowering.map_sites(sites,(base_image.parent/'symbols.txt').read_text())
    program=lowering.read_program((base_image.parent/'disassembly.txt').read_text())
    profile=c.read(root/discovery['profile'])
    extracted=lowering.extract(program,profile,site_map,plan['pool_size'])
    c.require(extracted['executable_formula_count']==discovery['executable_formula_count'],
              'Re-extracted formula count differs')
    by_name={row['name']:row for row in extracted['executable_candidates']}
    frozen=[]
    for candidate in discovery['pool']:
        original=by_name[candidate['name']]
        c.require(all(candidate[key]==value for key,value in original.items()),'Frozen candidate differs from re-extraction')
        for occurrence in candidate['occurrences']:
            c.require([site_map[int(pc,16)]['site'] for pc in occurrence['pcs']]==occurrence['sites'],
                      'Source-PC mapping differs')
        frozen.append(dict(name=candidate['name'],formula=candidate['formula'],**assess_candidate(candidate,sites)))
    filtered=filter_executable_candidates(extracted,sites)
    return dict(schema=SCHEMA,context_id=plan['context_id'],workload=plan['workload'],
        executable_count=extracted['executable_formula_count'],
        rejected_executable_count=filtered['relocation_guard']['rejected_count'],
        retained_executable_count=filtered['executable_formula_count'],frozen_pool_count=len(frozen),
        flagged_frozen_pool_count=sum(not row['safe'] for row in frozen),frozen_pool=frozen,
        scope='Label-free source-provenance diagnosis of existing pools; all frozen pools/results remain unchanged.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args(argv)
    print(json.dumps(audit_root(args.root),indent=2))


if __name__=='__main__':
    main()
