import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from asmscan import ABI, blocks, functionOf, scan  # noqa: E402
from isaforge.features import parse_formula  # noqa: E402

# PROVISIONAL assembly-level rewriting for any candidate formula.
# A site is a set of instruction lines in one block whose dataflow is exactly the formula:
# same operator tree, operands in the same order, the same immediates, and leaves in0/in1
# bound to two different values. It is fused only when, inside the block, every
# intermediate is dead (overwritten before the block ends and read by no other line) and
# the fused instruction has a legal position. Anything else is logged as skipped, with why.
R_OPS = {"add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu", "mul", "mulh", "mulhu", "mulhsu"}
I_OPS = {"addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu"}


class Mismatch(Exception):
    pass


def lastWriter(block, pos, reg):
    # the position in the block that last wrote reg before pos, or None if it came from outside
    for k in range(pos - 1, -1, -1):
        if reg in block[k].writes():
            return k
    return None


def match(tree, block, root):
    # binds the formula onto the block with its root at position root; raises Mismatch or returns
    # (members, inputs) where inputs maps in0/in1 to (register, writer position)
    members, inputs, reasons = set(), {}, []

    def visit(node, pos):
        line = block[pos]
        if len(line.words) != 1:
            raise Mismatch("multi-word line")
        op, rd, rs1, rs2, imm = line.ops[0]
        if op != node.value:
            raise Mismatch("operator")
        members.add(pos)
        if op in R_OPS:
            roles = [("reg", rs1), ("reg", rs2)]
        elif op in I_OPS:
            roles = [("reg", rs1), ("imm", imm)]
        else:
            roles = [("imm", imm)]
        if len(roles) != len(node.children):
            raise Mismatch("arity")
        for (role, value), child in zip(roles, node.children):
            if role == "imm":
                if child.children or not isinstance(child.value, int):
                    raise Mismatch("immediate")
                # a linker-filled immediate reads as 0 here, so its value can't be compared; the
                # site is still logged, and it can't be fused because the value moves with the code
                if line.relocated:
                    reasons.append(f"line {line.number}: immediate is filled in by the linker "
                                   f"(address constant; it changes when fused code moves)")
                elif child.value != value:
                    raise Mismatch("immediate")
            elif not child.children and isinstance(child.value, int):
                if child.value != 0 or value != 0:
                    raise Mismatch("x0 operand")
            elif child.value in ("in0", "in1"):
                if value == 0:
                    raise Mismatch("input is x0")
                key = (value, lastWriter(block, pos, value))
                if inputs.setdefault(child.value, key) != key:
                    raise Mismatch("input bound twice")
            else:
                w = lastWriter(block, pos, value) if value else None
                if w is None:
                    raise Mismatch("operand not computed in the block")
                visit(child, w)

    visit(tree, root)
    if len(inputs) == 2 and inputs["in0"] == inputs["in1"]:
        raise Mismatch("in0 and in1 are one value")
    return members, inputs, reasons


def finderCounts(block, members, inputs, root):
    # the finder's rule, on the original code: no other line may change an input before the root.
    # A site failing it could still be fused at its first member, but the finder never counted it,
    # so fusing it would make the measurement disagree with the prediction it is meant to test
    for reg, w in inputs.values():
        for k in range((w + 1) if w is not None else 0, root):
            if k not in members and reg in block[k].writes():
                return [f"not counted by the finder: line {block[k].number} overwrites input {ABI[reg]} "
                        f"before the root (fusible at the first member, left alone on purpose)"]
    return []


def check(block, members, inputs, root):
    # legality on the block as already rewritten; returns (placement position or None, reasons)
    reasons = []
    for m in sorted(members - {root}):
        reg = block[m].ops[0][1]
        for k in range(m + 1, len(block)):
            if reg in block[k].reads() and k not in members:
                reasons.append(f"intermediate {ABI[reg]} from line {block[m].number} is read by line {block[k].number}")
                break
            if reg in block[k].writes():
                break
        else:
            reasons.append(f"intermediate {ABI[reg]} from line {block[m].number} may be live after the block")
    out = block[root].ops[0][1]
    if not out:
        reasons.append("result goes to x0")
    if reasons:
        return None, reasons

    # at the root, like the finder assumes: no line (member or not) may change an input before it
    if all(not any(reg in block[k].writes() for k in range((w + 1) if w is not None else 0, root))
           for reg, w in inputs.values()):
        return root, []
    # at the first member: every input is ready there and nothing else touches the result register
    first = min(members)
    if all(w is None or w < first for _, w in inputs.values()) and \
            not any(k not in members and (out in block[k].reads() or out in block[k].writes())
                    for k in range(first + 1, root)):
        return first, []
    return None, ["no legal position: a member overwrites an input before the root, and the result "
                  "register is used between the first member and the root"]


class FusedLine:
    # the custom instruction in the in-memory block: what later sites see once a site is fused
    def __init__(self, number, rd, rs1, rs2):
        self.number, self.words, self.relocated = number, [0], False
        self.ops = [("custom0", rd, rs1, rs2, None)]
        self.stripped = "(fused)"

    def reads(self):
        return {r for r in self.ops[0][2:4] if r}

    def writes(self):
        return {self.ops[0][1]} if self.ops[0][1] else set()


def rewrite(files, manifest, workDir, prefix, flags, scanned=None):
    # sites are found on the original code (so every one gets labels and a log entry) and decided
    # in priority order; each fusion is applied to the in-memory block before the next site is checked.
    # `scanned` (path -> lines from asmscan.scan) lets a caller reuse one scan for many formulas
    sites, edits, defined = [], {}, set()
    for path in files:
        stem = re.sub(r"\W", "_", os.path.basename(path)[:-2])
        lines = scanned[path] if scanned and path in scanned else scan(path, workDir, prefix, flags)
        functions = functionOf(lines)
        defined |= {f for f in functions.values() if f}
        original = list(blocks(lines))
        current = [list(b) for b in original]
        taken = {}  # original line number -> formula of the fused site that consumed it
        for slot in manifest["slots"]:  # list order is the priority order
            tree = parse_formula(slot["formula"])
            for b, block in enumerate(original):
                for root in range(len(block)):
                    try:
                        members, inputs, reasons = match(tree, block, root)
                    except Mismatch:
                        continue
                    site = {"id": f"{stem}_{len(sites)}", "file": os.path.basename(path), "slot": slot["slot"],
                            "formula": slot["formula"], "function": functions[block[root].number],
                            "lines": [block[m].number for m in sorted(members)], "root_line": block[root].number,
                            "original": [block[m].stripped for m in sorted(members)]}
                    if len(members) != slot["size"]:
                        reasons.append(f"{len(members)} instructions but the candidate has size {slot['size']}")
                    if not reasons:
                        reasons = finderCounts(block, members, inputs, root)
                    clash = sorted({taken[n] for n in site["lines"] if n in taken})
                    if not reasons and clash:
                        reasons.append("overlaps a fused site of " + ", ".join(clash))
                    if not reasons:
                        # the same site on the block as rewritten so far
                        cur = current[b]
                        at = next(i for i, l in enumerate(cur) if l is block[root])
                        try:
                            now, nowInputs, _ = match(tree, cur, at)
                            if sorted(cur[m].number for m in now) != site["lines"]:
                                raise Mismatch("members changed")
                            place, reasons = check(cur, now, nowInputs, at)
                        except Mismatch:
                            reasons = ["no longer matches after an earlier fusion in this block"]
                    site["status"] = "skipped" if reasons else "fused"
                    site["reasons"] = reasons
                    if not reasons:
                        regs = [nowInputs[n][0] if n in nowInputs else 0 for n in ("in0", "in1")]
                        rd = cur[at].ops[0][1]
                        site["fused"] = f".insn r 0x0b, {slot['funct3']}, 2, {ABI[rd]}, {ABI[regs[0]]}, {ABI[regs[1]]}"
                        site["placed_at"] = "root" if place == at else "first member"
                        site["placed_line"] = cur[place].number
                        fused = FusedLine(cur[place].number, rd, *regs)
                        current[b] = [fused if i == place else l for i, l in enumerate(cur)
                                      if i == place or i not in now]
                        for n in site["lines"]:
                            taken[n] = slot["formula"]
                    site["labels"] = [f"hws_{site['id']}_{i}" for i in range(len(members))]
                    sites.append(site)
                    edits.setdefault(path, []).append(site)
    return sites, edits, sorted(defined)


def write(path, outDir, edits):
    # the marked copy only adds labels (no code changes); the fused copy applies the fused sites
    lines = open(path).read().split("\n")
    labels, replace, delete = {}, {}, set()
    for site in edits.get(path, []):
        for number, label in zip(site["lines"], site["labels"]):
            labels.setdefault(number, []).append(label)
        if site["status"] == "fused":
            for number in site["lines"]:
                delete.add(number)
            replace[site["placed_line"]] = f"\t{site['fused']}\t# fused: {site['formula']}"
    stem = os.path.basename(path)[:-2]
    marked, fused = [], []
    for number, text in enumerate(lines, 1):
        marked += [f"{label}:" for label in labels.get(number, [])] + [text]
        if number in replace:
            fused.append(replace[number])
        elif number not in delete:
            fused.append(text)
    with open(os.path.join(outDir, stem + ".marked.s"), "w") as f:
        f.write("\n".join(marked))
    with open(os.path.join(outDir, stem + ".fused.s"), "w") as f:
        f.write("\n".join(fused))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--prefix", default="riscv-none-elf-")
    parser.add_argument("--flags", default="-march=rv32im -mabi=ilp32")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    manifest = json.load(open(args.manifest))
    sites, edits, functions = rewrite(args.files, manifest, args.out, args.prefix, args.flags.split())
    for path in args.files:
        write(path, args.out, edits)
    with open(os.path.join(args.out, "sites.json"), "w") as f:
        json.dump({"priority": manifest["priority"], "functions": functions, "sites": sites}, f, indent=1)
    fused = sum(s["status"] == "fused" for s in sites)
    print(f"{args.out}: {fused} fused, {len(sites) - fused} skipped")


if __name__ == "__main__":
    main()
