"""One fixed, label-free development descriptor bundle; no frozen source edits."""
from __future__ import annotations
import math
from .features import parse_formula

SLOTS = 4
CLASSES = ('arithmetic', 'logic', 'left', 'right', 'signed_right', 'other')

def descriptors(formula):
    root = parse_formula(formula)
    nodes = []
    def visit(node):
        if node.children:
            nodes.append(node)
            for child in node.children: visit(child)
    visit(root)
    def kind(node):
        if node.children: return 4
        if isinstance(node.value, int): return 3
        return 1 if node.value == 'in0' else 2
    def width(node):
        if not node.children:
            return min(32, (node.value & 0xffffffff).bit_length()) if isinstance(node.value, int) else 32
        op = node.value
        if op in ('slt','sltu','slti','sltiu'): return 1
        if op in ('and','andi'): return min(width(c) for c in node.children)
        if op in ('or','ori','xor','xori'): return max(width(c) for c in node.children)
        if op == 'srli' and isinstance(node.children[1].value, int):
            return max(0, width(node.children[0])-(node.children[1].value & 31))
        if op == 'slli' and isinstance(node.children[1].value, int):
            return min(32, width(node.children[0])+(node.children[1].value & 31))
        return 32
    result = []
    for slot in range(SLOTS):
        if slot >= len(nodes): result.extend([0.0]*11); continue
        node = nodes[slot]; op = node.value
        group = ('arithmetic' if op in ('add','addi','sub') else 'logic' if op in ('and','andi','or','ori','xor','xori') else
                 'left' if op in ('sll','slli') else 'right' if op in ('srl','srli') else
                 'signed_right' if op in ('sra','srai') else 'other')
        children = list(node.children)
        immediate = next((c.value for c in reversed(children) if isinstance(c.value, int)), 0)
        result.extend([float(group == k) for k in CLASSES])
        result.extend([kind(children[0]), kind(children[1]) if len(children)>1 else 0,
                       math.copysign(math.log2(1+abs(immediate)), immediate),
                       (immediate & 0xffffffff).bit_count(), width(node)])
    return result+[max(0, len(nodes)-SLOTS)]
