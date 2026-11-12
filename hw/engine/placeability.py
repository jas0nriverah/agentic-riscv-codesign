import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from asmscan import scan  # noqa: E402
from isaforge.features import parse_formula  # noqa: E402
from rewrite import rewrite, write  # noqa: E402

# Placeability pre-check: for every candidate of every program, what the rewriter would fuse if
# that formula were alone on a core, against what the finder counted. Rewriter only, no hardware.
# The runs per site come from the Spike trace through the finder's run counts, and the sites'
# addresses from a labelled link that doesn't move code (the engine checks that elsewhere).
MULS = re.compile(r"\bmul(h|hu|hsu)?\(")
EN = "generated/hw/engine"


def symbols(elf, prefix):
    text = subprocess.run([prefix + "nm", "-n", elf], capture_output=True, text=True, check=True).stdout
    table = [(int(a, 16), t, n) for a, t, n in (l.split() for l in text.splitlines() if len(l.split()) == 3)]
    return {n: a for a, _, n in table}, sorted((a, n) for a, t, n in table if t in "tT" and not n.startswith("hws_"))


def functionAt(functions, pc):
    best = None
    for a, n in functions:
        if a > pc:
            break
        best = n
    return best


def sourceFiles(program):
    # the same order as the engine links: hooks, main, beebsc, then the program's own file
    folder = f"{EN}/asm/{program}"
    fixed = [f"{folder}/{n}.s" for n in ("embench-hooks", "main", "beebsc")]
    own = [f for f in sorted(glob.glob(f"{folder}/*.s")) if f not in fixed]
    assert len(own) == 1, own
    return fixed + own


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="riscv-none-elf-")
    parser.add_argument("--cflags", required=True)
    parser.add_argument("--ldflags", required=True)
    parser.add_argument("--programs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cflags, ldflags = args.cflags.split(), args.ldflags.split()
    work = f"{EN}/placeability"
    rows = []
    for program in args.programs:
        files = sourceFiles(program)
        folder = f"{work}/{program}"
        os.makedirs(folder, exist_ok=True)
        scanned = {path: scan(path, folder, args.prefix, cflags) for path in files}
        finder = json.load(open(f"{EN}/finder/{program}.json"))
        runs = {int(pc, 16): n for pc, n in finder["runs"].items()}
        _, functions = symbols(f"generated/programs/{program}.elf", args.prefix)
        candidates = json.load(open(f"generated/candidates/{program}.json"))
        for rank, c in enumerate(candidates, 1):
            formula = parse_formula(c["formula"]).canonical()
            manifest = {"slots": [{"slot": 0, "funct3": 0, "formula": formula, "size": c["size"]}], "priority": [formula]}
            sites, edits, defined = rewrite(files, manifest, folder, args.prefix, cflags, scanned)
            for path in files:
                write(path, folder, edits)
            # the labelled link gives every site its addresses; labels only, so the code doesn't move
            marked = [f"{folder}/{os.path.basename(p)[:-2]}.marked.s" for p in files]
            elf = f"{folder}/marked.elf"
            subprocess.run([args.prefix + "gcc", *cflags, *ldflags, "hw/sw/startup.S", *marked, "-lm", "-o", elf],
                           check=True, capture_output=True)
            labels, _ = symbols(elf, args.prefix)
            byPcs = {}
            for s in sites:
                pcs = [labels[l] for l in s["labels"]]
                s["pcs"] = pcs
                s["runs"] = runs.get(pcs[s["lines"].index(s["root_line"])], 0)
                byPcs[frozenset(pcs)] = s
            fused = [s for s in sites if s["status"] == "fused"]
            placeableSaved = sum((c["size"] - 1) * s["runs"] for s in fused)
            gaps = defaultdict(lambda: [0, 0])
            finderSites = finder["sites"].get(c["formula"], finder["sites"].get(formula, []))
            for fs in finderSites:
                s = byPcs.get(frozenset(fs["pcs"]))
                if s is not None and s["status"] == "fused":
                    continue
                if s is not None:
                    reason = "; ".join(s["reasons"])
                else:
                    fn = functionAt(functions, fs["root"])
                    reason = (f"in {fn}: library code the rewriter does not see" if fn not in defined
                              else f"in {fn}: not matched by the rewriter (UNEXPECTED)")
                reason = re.sub(r"line \d+", "line N", reason)
                gaps[reason][0] += 1
                gaps[reason][1] += (c["size"] - 1) * fs["runs"]
            rows.append({"program": program, "rank": rank, "formula": formula, "size": c["size"],
                         "has_mul": bool(MULS.search(formula)), "finder_saved": c["saved"], "finder_sites": c["places"],
                         "placeable_sites": len(fused), "placeable_sites_executed": sum(1 for s in fused if s["runs"]),
                         "placeable_saved": placeableSaved, "gap": c["saved"] - placeableSaved,
                         "gap_reasons": " | ".join(f"{n} sites/{saved}: {r}" for r, (n, saved) in gaps.items())})
        done = [r for r in rows if r["program"] == program]
        print(f"{program}: {len(done)} candidates, {sum(r['placeable_saved'] > 0 for r in done)} placeable, "
              f"{sum(r['gap'] == 0 for r in done)} fully placeable", flush=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}: {len(rows)} rows")


if __name__ == "__main__":
    main()
