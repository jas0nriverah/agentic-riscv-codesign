import json
import sys
from collections import Counter

# instructions that can change which instruction runs next
JUMPS = {"beq", "bne", "blt", "bge", "bltu", "bgeu", "jal", "jalr"}


def findBlocks(records, starts):
    # cuts the addresses into straight runs with one way in and one way out
    blocks = []
    current = []
    for pc in sorted(records):
        if current and (pc in starts or pc != current[-1] + 4):
            blocks.append(current)
            current = []
        current.append(pc)
        if records[pc]["op"] in JUMPS:
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


def main():
    # counts how many times each address ran
    runs = Counter()
    records = {}
    starts = set()
    previous = None
    for line in open(sys.argv[1]):
        record = json.loads(line)
        pc = int(record["pc"], 16)
        runs[pc] += 1
        records[pc] = record
        # an address reached by a jump starts a block
        if previous is None or pc != previous + 4:
            starts.add(pc)
        previous = pc

    blocks = findBlocks(records, starts)

    # stops with an error when a block has addresses that ran a different number of times
    mixed = [b for b in blocks if len({runs[pc] for pc in b}) != 1]
    if mixed:
        sys.exit("MIXED BLOCK COUNTS")


if __name__ == "__main__":
    main()
