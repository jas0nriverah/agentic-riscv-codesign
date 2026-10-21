"""The fixed bundle encodes order/roles without label or execution access."""
import pytest
from isaforge.ordered_hardware_descriptors import descriptors

def test_order_and_operand_roles():
    assert descriptors('sub(in0,in1)') != descriptors('sub(in1,in0)')
    assert descriptors('xor(srli(in0,2),slli(in1,30))') != descriptors('xor(slli(in0,30),srli(in1,2))')

def test_immediate_bits_and_width():
    a=descriptors('andi(in0,255)'); b=descriptors('andi(in0,256)')
    assert len(a)==45
    assert a[10]==8 and b[10]==9
    assert a[9]==8 and b[9]==1
    assert descriptors('srli(andi(in0,255),4)')[10]==4

def test_negative_literal_conservative_width():
    assert descriptors('andi(in0,-1)')[10]==32
    assert descriptors('slt(in0,in1)')[10]==1
    assert descriptors('srai(in0,31)')[10]==32

def test_padding_and_overflow():
    assert descriptors('add(in0,in1)')[11:44]==[0.0]*33
    assert descriptors('add(add(add(add(add(in0,in1),in0),in1),in0),in1)')[-1]==1

@pytest.mark.parametrize('formula',["__import__('os')",'add(in0,label)', 'add(in2,in0)'])
def test_reject_unsupported_formula(formula):
    with pytest.raises(ValueError): descriptors(formula)
