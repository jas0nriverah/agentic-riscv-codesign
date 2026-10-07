import json
import sys
from collections import Counter


def main():
    # counts how many times each address ran
    runs = Counter()
    ops = {}
    for line in open(sys.argv[1]):
        record = json.loads(line)
        runs[record["pc"]] += 1
        ops[record["pc"]] = record["op"]


if __name__ == "__main__":
    main()
