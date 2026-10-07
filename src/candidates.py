import json
import sys
from collections import Counter

# instructions that can change which instruction runs next
JUMPS = {"beq", "bne", "blt", "bge", "bltu", "bgeu", "jal", "jalr"}


def findBlocks(ops, starts):
    # cuts the addresses into straight runs with one way in and one way out
    blocks = []
    current = []
    for pc in sorted(ops):
        if current and (pc in starts or pc != current[-1] + 4):
            blocks.append(current)
            current = []
        current.append(pc)
        if ops[pc] in JUMPS:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def main():
    # counts how many times each address ran
    runs = Counter()
    ops = {}
    starts = set()
    previous = None
    for line in open(sys.argv[1]):
        record = json.loads(line)
        pc = int(record["pc"], 16)
        runs[pc] += 1
        ops[pc] = record["op"]
        # an address reached by a jump starts a block
        if previous is None or pc != previous + 4:
            starts.add(pc)
        previous = pc

    blocks = findBlocks(ops, starts)

    # stops with an error when a block has addresses that ran a different number of times
    mixed = [b for b in blocks if len({runs[pc] for pc in b}) != 1]
    if mixed:
        sys.exit("MIXED BLOCK COUNTS")


if __name__ == "__main__":
    main()
