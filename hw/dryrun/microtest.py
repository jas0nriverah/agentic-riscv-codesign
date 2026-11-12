import argparse
import itertools
import os
import random
import sys

# the ML branch's Python reference, vendored unmodified under hw/isaforge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isaforge.rtl import BOUNDARIES, evaluate_formula  # noqa: E402

FORMULA = "slli(andi(xor(in0,in1),255),2)"
SEED = 20261020
RANDOM_PAIRS = 1000
# the timed blocks are this long and twice this long, so fixed overhead cancels
TIMED = 64
FUSED = ".insn r 0x0b, 0, 2, {rd}, {rs1}, {rs2}"

# every program ends like main's startup: (result << 1) | 1 stored to tohost
TAIL = """
pass:
    li      a0, 1
    j       finish
fail:
    slli    a0, s3, 1
    ori     a0, a0, 1
finish:
    la      t0, tohost
    sw      a0, 0(t0)
hang:
    j       hang

    .section .tohost, "aw", @progbits
    .align  6
    .globl  tohost
tohost:   .dword 0
    .align  6
    .globl  fromhost
fromhost: .dword 0
    .section .bss
    .align  2
    .globl  instret_start, instret_stop
instret_start: .word 0
instret_stop:  .word 0
"""
HEAD = """    .section .text.start, "ax", @progbits
    .globl _start
_start:
    la      sp, __stack_top
    li      s3, 0
"""
# the harness counts cycles between these two stores, like Embench's hooks
WINDOW_START = """    csrr    t5, instret
    la      t6, instret_start
    sw      t5, 0(t6)
"""
WINDOW_STOP = """    csrr    t5, instret
    la      t6, instret_stop
    sw      t5, 0(t6)
"""


def reference(a, b):
    # a hand-written second reference, independent of the ML branch's evaluator
    return ((a ^ b) & 0xFF) << 2


def vectors():
    # boundary pairs, byte-edge pairs, then seeded random pairs
    pairs = list(itertools.product(BOUNDARIES, repeat=2))
    edges = (0x00, 0x7F, 0x80, 0xFF, 0x100, 0xFFFFFF00, 0xFFFFFFFF, 0xA5A5A5A5, 0x5A5A5A5A)
    pairs += list(itertools.product(edges, repeat=2))
    rng = random.Random(SEED)
    pairs += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(RANDOM_PAIRS)]
    out = []
    for a, b in pairs:
        want = evaluate_formula(FORMULA, a, b)
        if want != reference(a, b):
            sys.exit(f"the two Python references disagree on {a:#x}, {b:#x}")
        out.append((a, b, want))
    return out


def checkProgram(table):
    # every vector through the custom instruction, then register aliasing cases
    body = HEAD + """    la      s0, vectors
    li      s1, {count}
check:
    lw      t0, 0(s0)
    lw      t1, 4(s0)
    lw      t2, 8(s0)
    addi    s3, s3, 1
    {fused}
    bne     t3, t2, fail
    addi    s0, s0, 12
    bne     s3, s1, check
""".format(count=len(table), fused=FUSED.format(rd="t3", rs1="t0", rs2="t1"))
    # rd == rs1, rd == rs2, rs1 == rs2 and rd == x0
    cases = [
        ("t0", "t0", "t1", 0x12345678, 0x000000F0, reference(0x12345678, 0xF0)),
        ("t1", "t0", "t1", 0xFFFFFF01, 0x80000003, reference(0xFFFFFF01, 0x80000003)),
        ("t3", "t0", "t0", 0xDEADBEEF, 0xDEADBEEF, 0),
        ("zero", "t0", "t1", 0x000000FF, 0x00000000, 0),
    ]
    for rd, rs1, rs2, a, b, want in cases:
        check = "zero" if rd == "zero" else rd
        body += f"""    addi    s3, s3, 1
    li      t0, {a:#x}
    li      t1, {b:#x}
    li      t3, 0x55555555
    {FUSED.format(rd=rd, rs1=rs1, rs2=rs2)}
    li      t2, {want:#x}
    bne     {check}, t2, fail
"""
        if rd == "zero":
            # writing x0 must not touch any other register
            body += """    li      t2, 0x55555555
    bne     t3, t2, fail
"""
    body += "    j       pass\n" + TAIL + "\n    .section .rodata\n    .align 2\nvectors:\n"
    body += "".join(f"    .word {a:#010x}, {b:#010x}, {w:#010x}\n" for a, b, w in table)
    return body, len(table) + len(cases)


def timingProgram(kind, repeat):
    # one window around `repeat` copies of a block, so two lengths give cycles per block
    blocks = {
        "fused": [FUSED.format(rd="t3", rs1="t0", rs2="t1")],
        "original": ["xor     t3, t0, t1", "andi    t3, t3, 255", "slli    t3, t3, 2"],
        "xor": ["xor     t3, t0, t1"],
    }
    body = HEAD + "    li      t0, 0x12345678\n    li      t1, 0x9abcdef0\n" + WINDOW_START
    body += "".join(f"    {line}\n" for _ in range(repeat) for line in blocks[kind])
    return body + WINDOW_STOP + "    j       pass\n" + TAIL


def trapProgram(funct3, funct7, opcode):
    # an encoding the unit must not claim: the core has to trap instead of passing
    return HEAD + f"""    li      t0, 1
    li      t1, 2
    .insn r {opcode:#x}, {funct3}, {funct7}, t3, t0, t1
    j       pass
""" + TAIL


TRAPS = {
    "trap-f3-1": (1, 2, 0x0B),  # same funct7, other funct3
    "trap-f7-1": (0, 1, 0x0B),  # the ML branch's earlier encoding for this formula
    "trap-f7-3": (0, 3, 0x0B),
    "trap-custom1": (0, 2, 0x2B),  # same funct fields on custom-1
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    def write(name, text):
        with open(os.path.join(args.outdir, name + ".S"), "w") as f:
            f.write(text)

    table = vectors()
    text, checks = checkProgram(table)
    write("micro-check", text)
    for kind in ("fused", "original", "xor"):
        write(f"micro-{kind}-1x", timingProgram(kind, TIMED))
        write(f"micro-{kind}-2x", timingProgram(kind, 2 * TIMED))
    for name, fields in TRAPS.items():
        write(name, trapProgram(*fields))
    print(f"{checks} checks ({len(table)} vectors, seed {SEED}), timed block x{TIMED}/x{2 * TIMED}")


if __name__ == "__main__":
    main()
