import argparse
import json
import os
import subprocess
import sys
from collections import Counter

# main's candidate finder and decoder, imported unmodified, so each site is exactly one it counted
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import candidates as finder  # noqa: E402
from tracing import decode  # noqa: E402


def readProgram(elf, prefix):
    # finder.readProgram with the configured objdump instead of riscv64-unknown-elf-objdump
    text = subprocess.run([prefix + "objdump", "-d", elf], capture_output=True, text=True, check=True).stdout
    program = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":") and len(parts[1]) == 8:
            pc = int(parts[0][:-1], 16)
            op, rd, rs1, rs2, imm = decode(int(parts[1], 16))
            program[pc] = {"op": op, "rd": rd, "rs1": rs1, "rs2": rs2, "imm": imm}
    return program


def sites(trace, elf, prefix):
    # every (formula, instruction set) the finder accepted, with how often its block ran
    runs, starts, previous = Counter(), set(), None
    for line in open(trace):
        pc = int(json.loads(line)["pc"], 16)
        runs[pc] += 1
        if previous is None or pc != previous + 4:
            starts.add(pc)
        previous = pc
    program = readProgram(elf, prefix)
    out = {}
    for block in finder.findBlocks(program, starts):
        if runs[block[0]] == 0:
            continue
        sources = finder.findSources(block, program)
        lastWrites = finder.findLastWrites(block, program)
        for candidate in finder.findPotentialCandidates(block, program, finder.findArrows(block, program)):
            if finder.followsRules(candidate, block, program, sources, lastWrites):
                formula = finder.describe(candidate, block, program, sources)
                out.setdefault(formula, []).append({"pcs": sorted(block[i] for i in candidate),
                                                    "root": block[max(candidate)], "runs": runs[block[0]]})
    return out, runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    parser.add_argument("elf")
    parser.add_argument("candidates")
    parser.add_argument("out")
    parser.add_argument("--prefix", default="riscv-none-elf-")
    args = parser.parse_args()
    found, runs = sites(args.trace, args.elf, args.prefix)

    # the sites must add up to exactly what the finder reported, or they aren't its sites
    reported = {c["formula"]: c for c in json.load(open(args.candidates))}
    for formula, entry in reported.items():
        size = entry["size"]
        saved = sum((size - 1) * s["runs"] for s in found.get(formula, []))
        if saved != entry["saved"] or len(found.get(formula, [])) != entry["places"]:
            sys.exit(f"{formula}: sites give saved {saved}, places {len(found.get(formula, []))}; "
                     f"the finder reported {entry['saved']}, {entry['places']}")
    with open(args.out, "w") as f:
        json.dump({"sites": found, "runs": {f"{pc:#x}": n for pc, n in runs.items()}}, f)
    print(f"{len(found)} formulas, {sum(len(v) for v in found.values())} sites; all match {args.candidates}")


if __name__ == "__main__":
    main()
