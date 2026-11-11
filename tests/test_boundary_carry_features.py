"""Independent abstract carry soundness and immutable frozen feature behavior."""
import itertools
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import boundary_carry_features as f
import boundary_coverage_features as frozen
from isaforge.features import parse_formula
from isaforge.rtl import evaluate_formula


def abstract_operands(width):
 for trits in itertools.product((0,1,2),repeat=width):
  z=sum(1<<i for i,v in enumerate(trits) if v==0);o=sum(1<<i for i,v in enumerate(trits) if v==1)
  values=[v for v in range(1<<width) if v&z==0 and v&o==o]
  yield z,o,values


def test_all_low4_abstract_pairs_equal_concrete_addition_masks():
 operands=list(abstract_operands(4));pairs=0;concrete=0
 for za,oa,av in operands:
  for zb,ob,bv in operands:
   results=[(a+b)&15 for a in av for b in bv];known_one=15;possible_one=0
   for value in results:known_one&=value;possible_one|=value
   assert f.add_masks(za,oa,zb,ob,4)==(15^possible_one,known_one)
   pairs+=1;concrete+=len(results)
 assert pairs==6561 and concrete==65536


def test_mod32_wrap_negative_immediates_and_decoded_lui():
 for formula,expected in [('addi(4294967295,1)',0),('addi(0,-1)',4294967295),('add(2147483648,2147483648)',0),('lui(65536)',65536)]:
  assert f.known_bits(parse_formula(formula))==(f.MASK^expected,expected)


def test_carry_recovers_narrow_sign_placement_after_positive_or_negative_addi():
 for amount in (97,-1,65535,16777216):
  node=parse_formula(f'addi(slli(andi(in0,255),24),{amount})')
  span,low,count=f.unknown_shape(node)
  assert (span,low,count)==(8,24,8)
  z,o=f.known_bits(node)
  assert (z|o)&0xffffff==0xffffff


def test_nested_addi_precision_propagates_through_boolean_and_shift_nodes():
 formula='srli(xori(addi(slli(andi(in0,255),24),97),3),4)'
 assert f.unknown_shape(parse_formula(formula))==(8,20,8)
 assert f.unknown_shape(parse_formula('sra(in0,ori(andi(in1,4294967264),3))'))==(32,0,32)
 # Count unknown low5 controlbits only, despite upper27 being unknown.
 expr='xor(add(sra(addi(xori(in0,7),11),ori(andi(in1,4294967264),3)),in1),in0)'
 assert dict(zip(f.COLUMNS,f.features(expr)))['local_control_unknown_bits_max']==0


def test_known_bits_sound_with_correlated_operands_and_rv32_boundaries():
 rng=random.Random(20261112)
 expressions=['add(in0,in0)','addi(slli(andi(in0,255),24),97)','addi(slli(andi(in1,65535),16),-1)',
  'xor(addi(slli(andi(in0,255),24),97),addi(slli(andi(in0,255),24),-1))',
  'srai(addi(slli(andi(in0,255),24),97),7)','add(andi(in0,255),andi(in0,65535))']
 values=[0,1,31,32,0x7fffffff,0x80000000,0xffffffff]
 for formula in expressions:
  z,o=f.known_bits(parse_formula(formula));assert not z&o and z<=f.MASK and o<=f.MASK
  for a,b in [*itertools.product(values,repeat=2),*((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(256))]:
   actual=evaluate_formula(formula,a,b);assert actual&z==0 and actual&o==o


def test_frozen_helper_vectors_and_function_objects_are_unchanged():
 formula='xor(add(sra(addi(slli(andi(xori(in0,7),255),24),97),in1),in1),and(in0,in1))'
 old_fn=frozen.known_bits;before=frozen.features(formula);new=f.features(formula);after=frozen.features(formula)
 assert before==after and frozen.known_bits is old_fn
 assert before[10]==32 and new[10]==8 and new[11]==24


def test_all_root_chains_scope_and_same_node_binding():
 expr='xor(add(sra(addi(xori(in0,7),11),in1),in1),in0)'
 assert f.learning_scope(expr) and not frozen.learning_scope(expr)
 assert f.features('xor(add(sra(in0,in1),in0),sra(addi(xori(in0,7),11),in1))')==[0]*16
