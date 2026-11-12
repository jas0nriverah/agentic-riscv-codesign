import argparse
import json
import re

# PROVISIONAL assembly-level rewriting for one candidate:
#   xor X,A,B ; andi Y,X,255 ; slli Z,Y,2  ->  .insn r 0x0b, 0, 2, Z, A, B
# The fused instruction goes where the slli was, so a site is only rewritten when
# A and B still hold their values there and X and Y are dead after their one use.
# Liveness is only proven inside the block: a value that may live past the block
# end is treated as live, so such a site is skipped and logged, never guessed.

REGS = {"zero", "ra", "sp", "gp", "tp", "fp"} | {f"t{i}" for i in range(7)} | \
       {f"s{i}" for i in range(12)} | {f"a{i}" for i in range(8)} | {f"x{i}" for i in range(32)}
# instructions that end a block; labels end one too
ENDS = {"j", "jal", "jr", "jalr", "call", "tail", "ret", "mret",
        "beq", "bne", "blt", "bge", "bltu", "bgeu", "bgt", "ble", "bgtu", "bleu",
        "beqz", "bnez", "blez", "bgez", "bltz", "bgtz"}
# instructions whose register operands are all reads
NO_WRITE = {"sb", "sh", "sw", "fence", "ecall", "ebreak"} | ENDS
INSN = ".insn r 0x0b, 0, 2, {z}, {a}, {b}"


def parse(line):
    # splits an instruction line into its operation and register names, or None for anything else
    text = line.split("#")[0].strip()
    if not text or text.endswith(":") or text.startswith("."):
        return None
    op, _, rest = text.partition("\t") if "\t" in text else text.partition(" ")
    operands = [o.strip() for o in rest.split(",")] if rest.strip() else []
    return op, operands


def registers(operand):
    # the register names inside one operand, including the base in 0(a5)
    return [r for r in re.findall(r"[a-z][a-z0-9]*", operand) if r in REGS]


def effects(op, operands):
    # which registers an instruction reads and writes
    if op in NO_WRITE or not operands:
        return {r for o in operands for r in registers(o)}, set()
    written = set(registers(operands[0]))
    return {r for o in operands[1:] for r in registers(o)}, written


def blocks(lines):
    # groups instruction line numbers into straight runs that end at a label or a jump
    current = []
    for number, line in enumerate(lines):
        text = line.split("#")[0].strip()
        if text.endswith(":"):
            if current:
                yield current
            current = []
            continue
        parsed = parse(line)
        if parsed is None:
            continue
        current.append(number)
        if parsed[0] in ENDS:
            yield current
            current = []
    if current:
        yield current


def deadAfter(reg, use, block, info):
    # true when reg is overwritten later in the block before anything else reads it
    for k in block[block.index(use) + 1:]:
        reads, writes = info[k]
        if reg in reads:
            return False
        if reg in writes:
            return True
    return False


def nextReader(reg, start, block, info):
    # the first later instruction that reads reg, or None if reg is overwritten first
    for k in block[block.index(start) + 1:]:
        reads, writes = info[k]
        if reg in reads:
            return k
        if reg in writes:
            return None
    return None


def immediate(text):
    return int(text, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("out")
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    lines = open(args.source).read().split("\n")
    info = {}
    for number, line in enumerate(lines):
        parsed = parse(line)
        if parsed:
            info[number] = effects(*parsed)

    sites, skipped = [], []
    replace, delete = {}, set()
    for block in blocks(lines):
        for first in block:
            op, operands = parse(lines[first])
            if op != "xor" or len(operands) != 3:
                continue
            x, a, b = operands
            second = nextReader(x, first, block, info)
            if second is None:
                continue
            op2, ops2 = parse(lines[second])
            if op2 != "andi" or ops2[1] != x or immediate(ops2[2]) != 255:
                continue
            y = ops2[0]
            third = nextReader(y, second, block, info)
            if third is None:
                continue
            op3, ops3 = parse(lines[third])
            if op3 != "slli" or ops3[1] != y or immediate(ops3[2]) != 2:
                continue
            z = ops3[0]
            chain = [lines[k].strip() for k in (first, second, third)]
            reasons = []
            # the xor result may only feed the andi, and the andi result only the slli
            if x != y and not deadAfter(x, second, block, info):
                reasons.append(f"{x} may be read after the andi")
            if x == y and nextReader(x, second, block, info) != third:
                reasons.append(f"{x} is read before the slli")
            if y != z and not deadAfter(y, third, block, info):
                reasons.append(f"{y} may be read after the slli")
            # every instruction between the xor and the slli still runs and must not see x or y
            for k in block[block.index(first) + 1:block.index(third)]:
                if k in (second,):
                    continue
                reads, _ = info[k]
                if x in reads or y in reads:
                    reasons.append(f"line {k + 1} reads an intermediate")
            # A and B are read at the slli position so nothing in between may change them
            for k in block[block.index(first):block.index(third)]:
                _, writes = info[k]
                if a in writes or b in writes:
                    reasons.append(f"line {k + 1} overwrites an input before the slli")
            site = {"line": first + 1, "original": chain,
                    "fused": INSN.format(z=z, a=a, b=b)}
            if reasons:
                skipped.append({**site, "reasons": reasons})
                continue
            replace[third] = "\t" + site["fused"]
            delete.update((first, second))
            sites.append(site)

    out = [replace.get(n, line) for n, line in enumerate(lines) if n not in delete]
    with open(args.out, "w") as f:
        f.write("\n".join(out))
    with open(args.log, "w") as f:
        json.dump({"source": args.source, "sites": sites, "skipped": skipped}, f, indent=1)
    print(f"rewrote {len(sites)} site(s), skipped {len(skipped)}")
    for site in sites + skipped:
        print(json.dumps(site))


if __name__ == "__main__":
    main()
