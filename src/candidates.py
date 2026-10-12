import json
import subprocess
import sys
from collections import Counter

from tracing import decode

# instructions that can change which instruction runs next
JUMPS = {"beq", "bne", "blt", "bge", "bltu", "bgeu", "jal", "jalr"}

# operations allowed inside a custom instruction
ELIGIBLE = {"add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
            "addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu",
            "lui", "mul", "mulh", "mulhu", "mulhsu"}


def readProgram(elfPath):
    # reads every instruction in the compiled program including ones the trace never saw
    text = subprocess.run(["riscv64-unknown-elf-objdump", "-d", elfPath],
                          capture_output=True, text=True).stdout
    program = {}
    for line in text.splitlines():
        parts = line.split()
        # instruction lines start with an address and the raw bits like 80000280: 00a447b3
        if len(parts) >= 2 and parts[0].endswith(":") and len(parts[1]) == 8:
            pc = int(parts[0][:-1], 16)
            op, rd, rs1, rs2, imm = decode(int(parts[1], 16))
            program[pc] = {"op": op, "rd": rd, "rs1": rs1, "rs2": rs2, "imm": imm}
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
    allowed = [records[pc]["op"] in ELIGIBLE for pc in block]

    # neighbours of each instruction through arrows in either direction
    neighbours = {i: set() for i in range(len(block))}
    for a, b in arrows:
        if allowed[a] and allowed[b]:
            neighbours[a].add(b)
            neighbours[b].add(a)

    potentialCandidates = set()
    for start in range(len(block)):
        if not allowed[start]:
            continue
        # sets still waiting to be grown
        stack = [frozenset([start])]
        while stack:
            candidate = stack.pop()
            if candidate in potentialCandidates:
                continue
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
    inputs, outputs = findInputsAndOutputs(candidate, sources, lastWrites)

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


def main():
    # counts how many times each address ran
    runs = Counter()
    starts = set()
    previous = None
    for line in open(sys.argv[1]):
        record = json.loads(line)
        pc = int(record["pc"], 16)
        runs[pc] += 1
        # an address reached by a jump starts a block
        if previous is None or pc != previous + 4:
            starts.add(pc)
        previous = pc

    program = readProgram(sys.argv[2])
    blocks = findBlocks(program, starts)

    # stops with an error when a block has addresses that ran a different number of times
    mixed = [b for b in blocks if len({runs[pc] for pc in b}) != 1]
    if mixed:
        sys.exit("MIXED BLOCK COUNTS")

    # keeps the potential candidates that follow the rules and merges the ones that do identical work
    patterns = {}
    for block in blocks:
        if runs[block[0]] == 0:
            continue
        sources = findSources(block, program)
        lastWrites = findLastWrites(block, program)
        for candidate in findPotentialCandidates(block, program, findArrows(block, program)):
            if followsRules(candidate, block, program, sources, lastWrites):
                formula = describe(candidate, block, program, sources)
                entry = patterns.setdefault(formula, {"size": len(candidate), "runs": 0, "places": 0})
                entry["runs"] += runs[block[0]]
                entry["places"] += 1

    # ranks the patterns by how many instructions each would save
    total = sum(runs.values())
    ranked = []
    for formula, entry in patterns.items():
        saved = (entry["size"] - 1) * entry["runs"]
        ranked.append({"formula": formula, "size": entry["size"], "runs": entry["runs"],
                       "places": entry["places"], "saved": saved,
                       "savedPercent": round(100 * saved / total, 3)})
    ranked.sort(key=lambda p: -p["saved"])

    # writes the ranked list to the file named on the command line
    with open(sys.argv[3], "w") as out:
        json.dump(ranked, out, indent=1)


if __name__ == "__main__":
    main()
