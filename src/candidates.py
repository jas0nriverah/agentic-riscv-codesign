import argparse
import json
import subprocess
from collections import Counter

from tracing import decode

# instructions that can change which instruction runs next
JUMPS = {"beq", "bne", "blt", "bge", "bltu", "bgeu", "jal", "jalr"}

# operations allowed inside a custom instruction
ELIGIBLE = {"add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
            "addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu",
            "lui", "mul", "mulh", "mulhu", "mulhsu"}


def readProgram(elfPath, objdump="riscv64-unknown-elf-objdump"):
    # reads every instruction in the compiled program including ones the trace never saw
    text = subprocess.run([objdump, "-d", str(elfPath)],
                          capture_output=True, text=True, check=True).stdout
    program = {}
    symbol = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("<") and parts[1].endswith(">:"):
            symbol = parts[1][1:-2]
        # instruction lines start with an address and the raw bits like 80000280: 00a447b3
        if len(parts) >= 2 and parts[0].endswith(":") and len(parts[1]) == 8:
            pc = int(parts[0][:-1], 16)
            op, rd, rs1, rs2, imm = decode(int(parts[1], 16))
            program[pc] = {"op": op, "rd": rd, "rs1": rs1, "rs2": rs2, "imm": imm,
                           "symbol": symbol}
    return program


def findBlocks(program, starts):
    # cuts the program into straight runs with one way in and one way out
    starts = set(starts)
    for pc, record in program.items():
        # a block also starts wherever a branch or jump in the code can land
        # jalr jumps to an address held in a register so its target is unknown here
        if record["op"] in JUMPS and record["op"] != "jalr":
            starts.add(pc + record["imm"])

    blocks = []
    current = []
    for pc in sorted(program):
        if current and (pc in starts or pc != current[-1] + 4):
            blocks.append(current)
            current = []
        current.append(pc)
        if program[pc]["op"] in JUMPS:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


# an arrow goes from one instruction to a later one that uses its result
# blocks only show which instructions run together while arrows show which ones are related
# a group can only become one custom instruction if arrows connect all of it
# arrows coming into a group from outside are the inputs it needs
def findArrows(block, records):
    # finds which earlier instruction in the block feeds each instruction
    lastWriter = {}
    arrows = []
    for i, pc in enumerate(block):
        record = records[pc]
        for reg in (record["rs1"], record["rs2"]):
            # register zero always reads as 0 so it never carries a result
            if reg and reg in lastWriter:
                arrows.append((lastWriter[reg], i))
        if record["rd"]:
            lastWriter[record["rd"]] = i
    return arrows


# a potential candidate is a connected set of allowed instructions that one new instruction could replace
def findPotentialCandidates(block, records, arrows, maxSize=5):
    # lists every connected set of 2 to maxSize allowed instructions
    if maxSize < 2:
        raise ValueError("maxSize must be at least 2")
    allowed = [records[pc]["op"] in ELIGIBLE for pc in block]

    # neighbours of each instruction through arrows in either direction
    neighbours = {i: set() for i in range(len(block))}
    for a, b in arrows:
        if allowed[a] and allowed[b]:
            neighbours[a].add(b)
            neighbours[b].add(a)

    potentialCandidates = set()
    visited = set()
    for start in range(len(block)):
        if not allowed[start]:
            continue
        # sets still waiting to be grown
        stack = [frozenset([start])]
        while stack:
            candidate = stack.pop()
            if candidate in visited:
                continue
            visited.add(candidate)
            if len(candidate) >= 2:
                potentialCandidates.add(candidate)
            if len(candidate) == maxSize:
                continue
            for member in candidate:
                for n in neighbours[member]:
                    # only adds instructions numbered after the start so each set is found once
                    if n > start and n not in candidate:
                        stack.append(candidate | {n})
    return potentialCandidates


def findSources(block, records):
    # lists the registers each instruction reads and which instruction in the block wrote them
    lastWriter = {}
    sources = []
    for i, pc in enumerate(block):
        record = records[pc]
        reads = []
        for reg in (record["rs1"], record["rs2"]):
            # register zero always reads as 0 so it is never an input
            if reg:
                reads.append((reg, lastWriter.get(reg)))
        sources.append(reads)
        if record["rd"]:
            lastWriter[record["rd"]] = i
    return sources


def findLastWrites(block, records):
    # lists the instructions whose result is still in its register when the block ends
    lastWriter = {}
    for i, pc in enumerate(block):
        if records[pc]["rd"]:
            lastWriter[records[pc]["rd"]] = i
    return set(lastWriter.values())


def findInputsAndOutputs(candidate, sources, lastWrites):
    # finds the values that cross into and out of the candidate
    inputs = set()
    # a result still in its register when the block ends might be needed later
    outputs = {member for member in candidate if member in lastWrites}
    for reader, reads in enumerate(sources):
        for reg, writer in reads:
            # value made outside and used inside
            if reader in candidate and writer not in candidate:
                inputs.add((reg, writer))
            # value made inside and used outside
            if reader not in candidate and writer in candidate:
                outputs.add(writer)
    return inputs, outputs


def followsRules(candidate, block, records, sources, lastWrites):
    # checks that the candidate could really become one instruction
    if len(candidate) < 2 or any(records[block[k]]["op"] not in ELIGIBLE for k in candidate):
        return False
    inputs, outputs = findInputsAndOutputs(candidate, sources, lastWrites)

    # Opaque instructions have unknown register effects; do not move work past them.
    if any(records[block[k]]["op"] == "unknown"
           for k in range(min(candidate), max(candidate) + 1)):
        return False

    # A connected graph can still contain dead branches. The formula must contain
    # every original operation that is credited as removed.
    contributing = set()
    pending = [max(candidate)]
    while pending:
        member = pending.pop()
        if member in contributing:
            continue
        contributing.add(member)
        pending.extend(writer for _, writer in sources[member]
                       if writer in candidate)
    if contributing != set(candidate):
        return False

    # one instruction reads at most two registers and writes one
    if len(inputs) > 2 or len(outputs) != 1:
        return False

    # the new instruction sits where the last member was so that member must give the result
    last = max(candidate)
    if outputs != {last}:
        return False

    # every input must still be in its register when the new instruction runs
    for reg, writer in inputs:
        first = 0 if writer is None else writer + 1
        for k in range(first, last):
            if k not in candidate and records[block[k]]["rd"] == reg:
                return False
    return True


def describe(candidate, block, records, sources):
    # writes what the candidate computes with in0 and in1 for inputs so identical work gets identical text
    names = {}

    def build(member):
        record = records[block[member]]
        writers = dict(sources[member])
        parts = []
        for reg in (record["rs1"], record["rs2"]):
            if reg is None:
                continue
            if reg == 0:
                parts.append("0")
            elif writers[reg] in candidate:
                parts.append(build(writers[reg]))
            else:
                parts.append(names.setdefault((reg, writers[reg]), f"in{len(names)}"))
        if record["imm"] is not None:
            parts.append(str(record["imm"]))
        return f"{record['op']}({','.join(parts)})"

    return build(max(candidate))


def extractCandidates(program, runs, starts, maxSize=5, limit=None):
    """Extract legal formulas and auditable occurrence/overlap metadata.

    ``saved`` remains the historical occurrence heuristic. ``overlapSafeSaved``
    is a conservative single-formula instruction reduction under the assumption
    that each legal occurrence can be replaced by one instruction. Neither is a
    cycle or speedup measurement.
    """
    if maxSize < 2:
        raise ValueError("maxSize must be at least 2")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    missing = set(runs) - set(program)
    if missing:
        raise ValueError(f"trace addresses absent from RV32 ELF: {sorted(missing)[:5]}")
    blocks = findBlocks(program, starts)
    mixed = [b for b in blocks if len({runs[pc] for pc in b}) != 1]
    if mixed:
        raise ValueError(f"MIXED BLOCK COUNTS: first block starts at {mixed[0][0]:#x}")

    patterns = {}
    for block in blocks:
        if runs[block[0]] == 0:
            continue
        sources = findSources(block, program)
        lastWrites = findLastWrites(block, program)
        potential = findPotentialCandidates(block, program, findArrows(block, program), maxSize)
        for candidate in sorted(potential, key=lambda c: tuple(sorted(c))):
            if followsRules(candidate, block, program, sources, lastWrites):
                formula = describe(candidate, block, program, sources)
                entry = patterns.setdefault(formula, {"size": len(candidate), "runs": 0,
                                                       "occurrences": []})
                # Expressions can have shared or repeated nodes in different
                # occurrences. Keep one formula identity, with the smallest
                # representative size for the historical heuristic.
                entry["size"] = min(entry["size"], len(candidate))
                entry["runs"] += runs[block[0]]
                entry["occurrences"].append({
                    "blockStart": f"0x{block[0]:08x}",
                    "pcs": [f"0x{block[k]:08x}" for k in sorted(candidate)],
                    "blockRuns": runs[block[0]], "size": len(candidate),
                    "symbols": sorted({program[block[k]]["symbol"] for k in candidate
                                       if program[block[k]].get("symbol")}),
                })

    total = sum(runs.values())
    ranked = []
    for formula, entry in patterns.items():
        occurrences = entry["occurrences"]
        # Prefer larger occurrences, then earliest PCs. Accept only disjoint
        # static PC sets within each block; do not sum overlapping executions.
        # This is deterministic and conservative, not optimal set packing.
        used = {}
        for occurrence in sorted(occurrences, key=lambda o: (-o["size"], o["pcs"])):
            block_used = used.setdefault(occurrence["blockStart"], set())
            pcs = set(occurrence["pcs"])
            selected = block_used.isdisjoint(pcs)
            occurrence["selectedForSavings"] = selected
            if selected:
                block_used.update(pcs)
        selected = [o for o in occurrences if o["selectedForSavings"]]
        saved = (entry["size"] - 1) * entry["runs"]
        safe = sum((o["size"] - 1) * o["blockRuns"] for o in selected)
        ranked.append({
            "formula": formula, "size": entry["size"], "runs": entry["runs"],
            "places": len(occurrences), "saved": saved,
            "savedPercent": round(100 * saved / total, 3),
            "traceTotalInstructions": total,
            "occurrences": occurrences,
            "sizeVariants": sorted({o["size"] for o in occurrences}),
            "occurrenceSaved": sum((o["size"] - 1) * o["blockRuns"] for o in occurrences),
            "nonOverlappingPlaces": len(selected),
            "nonOverlappingRuns": sum(o["blockRuns"] for o in selected),
            "overlapSafeSaved": safe,
            "overlapSafeSavedPercent": round(100 * safe / total, 3),
            "overlapSelectionMethod": "deterministic-greedy-pc-disjoint",
        })
    ranked.sort(key=lambda p: (-p["saved"], p["formula"]))
    return ranked if limit is None else ranked[:limit]


def readTrace(tracePath):
    runs = Counter()
    starts = set()
    previous = None
    with open(tracePath) as trace:
        for line in trace:
            record = json.loads(line)
            pc = int(record["pc"], 16)
            runs[pc] += 1
            if previous is None or pc != previous + 4:
                starts.add(pc)
            previous = pc
    # The measurement region may end in the middle of a static basic block.
    if previous is not None:
        starts.add(previous + 4)
    return runs, starts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract RV32 custom-instruction candidates")
    parser.add_argument("trace")
    parser.add_argument("elf")
    parser.add_argument("output")
    parser.add_argument("--max-size", type=int, default=5,
                        help="maximum distinct operations (legacy default: 5; study: 4)")
    parser.add_argument("--limit", type=int, help="retain first N legacy-merit-ranked formulas")
    parser.add_argument("--objdump", default="riscv64-unknown-elf-objdump")
    args = parser.parse_args(argv)
    if args.max_size < 2 or (args.limit is not None and args.limit < 1):
        parser.error("--max-size must be >=2 and --limit must be positive")
    try:
        runs, starts = readTrace(args.trace)
        ranked = extractCandidates(readProgram(args.elf, args.objdump), runs, starts,
                                   args.max_size, args.limit)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.exit(1, f"candidate extraction failed: {exc}\n")
    with open(args.output, "w") as out:
        json.dump(ranked, out, indent=1)
        out.write("\n")


if __name__ == "__main__":
    main()
