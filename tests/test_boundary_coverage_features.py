"""Meaningful localized features, same-node binding and conservative bit masks."""
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import boundary_coverage_features as f
from isaforge.features import parse_formula
from isaforge.rtl import evaluate_formula


def test_localized_schema_and_input_dependency_sharing():
 formula='xor(add(sra(addi(xori(and(in0,in1),11),73),andi(xor(in0,in1),1)),in1),xor(in0,in1))'
 v=dict(zip(f.COLUMNS,f.features(formula)))
 assert len(f.COLUMNS)==16 and len(set(f.COLUMNS))==16
 assert v['local_chain_count']==1 and v['local_data_control_input_overlap']==2
 assert v['local_data_postadd_input_overlap']==1 and v['local_data_outerxor_input_overlap']==2
 assert v['local_data_and_input_joins']==1 and v['local_data_or_input_joins']==0
 assert v['local_control_unknown_bits_max']==1 and f.learning_scope(formula)


def test_commutative_nonleaf_sharing_does_not_count_input_leaves():
 formula='xor(add(sra(addi(xori(xor(in0,in1),11),73),in1),xor(in1,in0)),xor(in0,in1))'
 v=dict(zip(f.COLUMNS,f.features(formula)))
 assert v['local_data_postadd_shared_subtrees']==1
 assert v['local_data_outerxor_shared_subtrees']==1
 assert v['local_postadd_outerxor_shared_subtrees']==1


def test_same_direct_shift_and_own_data_are_required():
 assert f.features('xor(add(sra(in0,in1),in0),sra(addi(xori(in0,11),73),in1))')==[0]*16
 assert not f.learning_scope('xor(add(sra(addi(xori(in0,11),73),in1),in0),in1)')
 assert f.learning_scope('xor(add(sra(slli(andi(addi(xori(in0,11),73),255),24),in1),in0),in1)')


def test_narrow_width_positions_decoded_lui_and_rv32_shift_bits():
 assert f.unknown_shape(parse_formula('andi(in0,65535)'))==(16,0,16)
 assert f.unknown_shape(parse_formula('slli(andi(in0,255),24)'))==(8,24,8)
 assert f.known_bits(parse_formula('lui(65536)'))==(f.MASK^65536,65536)
 assert f.unknown_shape(parse_formula('srl(in0,ori(andi(in1,4294967264),3))'))==(29,0,29)


def test_known_masks_are_sound_against_exact_rv32_semantics():
 rng=random.Random(20261111)
 expressions=['andi(addi(in0,73),255)','slli(andi(xori(in0,11),255),24)',
  'srai(ori(andi(in0,255),2147483648),7)','xor(andi(in0,255),ori(in1,4294967040))',
  'sra(in0,ori(andi(in1,4294967264),3))','add(andi(in0,0),17)','slt(in0,in1)','lui(65536)']
 for formula in expressions:
  z,o=f.known_bits(parse_formula(formula));assert not z&o
  for _ in range(128):
   value=evaluate_formula(formula,rng.getrandbits(32),rng.getrandbits(32))
   assert value&o==o and value&z==0


def test_multiple_chain_aggregation_is_explicit():
 a='sra(slli(andi(addi(xori(in0,11),73),255),24),in1)'
 b='sra(addi(xori(in1,11),73),in0)'
 values=dict(zip(f.COLUMNS,f.features(f'xor(add({a},in1),add({b},in0))')))
 assert values['local_chain_count']==2 and values['local_data_unknown_span_min']==8
 assert values['local_data_unknown_lsb_max']==24


def test_shift_control_feature_ignores_irrelevant_upper27bits():
 formula='xor(add(sra(addi(xori(in0,11),73),ori(andi(in1,4294967264),3)),in1),and(in0,in1))'
 values=dict(zip(f.COLUMNS,f.features(formula)))
 assert values['local_control_unknown_bits_max']==0
