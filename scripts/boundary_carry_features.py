#!/usr/bin/env python3
"""Pure carry-refined localized original-AST features; no labels or native tools.

This helper lives outside isaforge/ to preserve all frozen source inventories.
The bit analysis includes independent possible-carry sets for ADD/ADDI and is conservative RV32 known-bit propagation, not a calibrated
uncertainty or area estimate. LUI immediates are already decoded32-bit values.
"""
from __future__ import annotations
from functools import lru_cache
from isaforge.features import parse_formula,Expression
from isaforge.rtl import evaluate_formula
MASK=(1<<32)-1
COLUMNS=(
 'local_chain_count',
 'local_data_control_input_overlap','local_data_postadd_input_overlap','local_data_outerxor_input_overlap',
 'local_control_postadd_input_overlap','local_control_outerxor_input_overlap','local_postadd_outerxor_input_overlap',
 'local_data_postadd_shared_subtrees','local_data_outerxor_shared_subtrees','local_postadd_outerxor_shared_subtrees',
 'local_data_unknown_span_min','local_data_unknown_lsb_max','local_control_unknown_bits_max',
 'local_data_and_input_joins','local_data_or_input_joins','local_data_xor_input_joins')
SCHEMA={
 'columns':list(COLUMNS),'count':16,
 'chains':'Original root xor; either operand add; either operand of that SAME add DIRECT sra, shift-control contains in0/in1 and OWN data subtree contains both addi and xori. Enumerate root-child then add-child order, all matches.',
 'aggregation':'Chain count sums matches; data unknown span is minimum over chains; every other column is maximum over chains. All16 zero when no chain.',
 'input_overlap':'Cardinality of intersection of two operand input sets {in0,in1}, six pairings among data/control/post-add sibling/outer-XOR sibling. Range0..2.',
 'shared_subtrees':'Cardinality of intersection of unique input-bearing NONLEAF subtree keys. Keys retain original operations and raw literal values; only add/and/or/xor child order is sorted (commutative). Input leaves and constant-only subtrees excluded.',
 'widths':'Conservative known-zero/known-one32bit masks. Unknown span=highest unknown bit-lowest+1, or0 if fully known; unknown lowbit=lowest unknown index, or32 if fully known. Control unknown count counts only unknown LOW5bits, as required by RV32 shift semantics.',
 'known_bits':'ADD/ADDI propagate per-bit possiblecarry sets from{0}, ignoring operand correlations conservatively; discard carryout32. Other rules: inputs unknown; literal bits exact modulo2^32; lui passes its decoded child bits. Fully known operands evaluate exactRV32. and/or/xor and their immediate forms propagate known bits; shifts with known low5control bits shift masks with logicalzero or known arithmetic sign fill. Unknown shifts and non-add arithmetic conservatively unknown; comparisons have knownzero bits31..1. No algebraic or formula normalization.',
 'input_joins':'Count AND/OR/XOR nodes in the OWN data subtree whose both operands are input-bearing. Includes original tree occurrences; immediate Boolean ops not counted.',
 'learning_scope':'ALL original rootxor/add/directcompoundSRA chains, including outer-input/wide cases. No Boolean/narrow-only restriction or cap, target, prediction, ID or case lookup.',
 'inference_inputs':'Original formula only. The literal16 is architectural halfword coverage-cell boundary, not a fitted error/cap margin.'}


def walk(node):
 yield node
 for child in node.children:yield from walk(child)


@lru_cache(maxsize=32768)
def dependencies(node):
 if not node.children:return frozenset([node.value]) if node.value in ('in0','in1') else frozenset()
 return frozenset().union(*(dependencies(c) for c in node.children))


def chains(formula):
 root=parse_formula(formula)
 if root.value!='xor':return []
 matches=[]
 for i,add in enumerate(root.children):
  if add.value!='add':continue
  for j,shift in enumerate(add.children):
   if shift.value=='sra' and dependencies(shift.children[1]) and {'addi','xori'}<={n.value for n in walk(shift.children[0])}:
    matches.append((shift.children[0],shift.children[1],add.children[1-j],root.children[1-i]))
 return matches


def add_masks(za,oa,zb,ob,width=32):
 """Best bit masks for independent abstract operands; correlation is ignored."""
 if not 1<=width<=32:raise ValueError('Width must be1..32')
 mask=(1<<width)-1;za&=mask;oa&=mask;zb&=mask;ob&=mask
 if za&oa or zb&ob:raise ValueError('Knownzero/one masks overlap')
 carry={0};zero=one=0
 for bit in range(width):
  a=(0,) if za&(1<<bit) else (1,) if oa&(1<<bit) else (0,1)
  b=(0,) if zb&(1<<bit) else (1,) if ob&(1<<bit) else (0,1)
  totals={x+y+c for x in a for y in b for c in carry}
  values={v&1 for v in totals};carry={v>>1 for v in totals}
  if values=={0}:zero|=1<<bit
  elif values=={1}:one|=1<<bit
 return zero&mask,one&mask


@lru_cache(maxsize=32768)
def known_bits(node):
 if not node.children:
  if isinstance(node.value,int):return (~node.value)&MASK,node.value&MASK
  return 0,0
 bits=[known_bits(c) for c in node.children];op=node.value
 if op=='lui':return bits[0]
 if all((z|o)==MASK for z,o in bits):
  literal_node=Expression(op,tuple(Expression(o) for z,o in bits));value=evaluate_formula(literal_node,0,0)
  return (~value)&MASK,value&MASK
 z0,o0=bits[0];z1,o1=bits[1] if len(bits)>1 else (0,0)
 if op in ('add','addi'):return add_masks(z0,o0,z1,o1)
 if op in ('and','andi'):return z0|z1,o0&o1
 if op in ('or','ori'):return z0&z1,o0|o1
 if op in ('xor','xori'):return (z0&z1)|(o0&o1),(z0&o1)|(o0&z1)
 if op in ('slt','slti','sltu','sltiu'):return MASK^1,0
 if op in ('sll','slli','srl','srli','sra','srai') and ((z1|o1)&31)==31:
  amount=o1&31
  if not amount:return z0,o0
  if op in ('sll','slli'):return ((z0<<amount)|((1<<amount)-1))&MASK,(o0<<amount)&MASK
  high=MASK^((1<<(32-amount))-1)
  if op in ('srl','srli'):return (z0>>amount)|high,o0>>amount
  return (z0>>amount)|(high if z0&(1<<31) else 0),(o0>>amount)|(high if o0&(1<<31) else 0)
 return 0,0


def unknown_shape(node):
 z,o=known_bits(node);unknown=MASK^(z|o)
 if not unknown:return 0,32,0
 low=(unknown&-unknown).bit_length()-1
 return unknown.bit_length()-low,low,unknown.bit_count()


@lru_cache(maxsize=32768)
def subtree_key(node):
 if not node.children:return str(node.value)
 children=[subtree_key(c) for c in node.children]
 if node.value in ('add','and','or','xor'):children.sort()
 return str(node.value)+'('+','.join(children)+')'


def nonleaf_subtrees(node):
 return {subtree_key(n) for n in walk(node) if n.children and dependencies(n)}


def learning_scope(formula):
 return bool(chains(formula))


def features(formula):
 matches=chains(formula)
 if not matches:return [0]*16
 records=[]
 for data,control,post,outer in matches:
  operands=(data,control,post,outer);deps=[dependencies(n) for n in operands];trees=[nonleaf_subtrees(n) for n in operands]
  span,low,_=unknown_shape(data)
  record=[1,*[len(deps[a]&deps[b]) for a,b in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))],
   *[len(trees[a]&trees[b]) for a,b in ((0,2),(0,3),(2,3))],span,low,((MASK^(known_bits(control)[0]|known_bits(control)[1]))&31).bit_count(),
   *[sum(n.value==op and all(dependencies(c) for c in n.children) for n in walk(data)) for op in ('and','or','xor')]]
  records.append(record)
 result=[max(row[i] for row in records) for i in range(16)]
 result[0]=len(records);result[10]=min(row[10] for row in records)
 return result
