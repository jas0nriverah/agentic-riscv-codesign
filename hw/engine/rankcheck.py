import argparse
import csv
from collections import defaultdict

# How well does the finder's `saved` predict measured cycles saved? Spearman rank correlation per
# program over a sweep's rows, with average ranks for ties, plus the geometric mean of speedups.


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(xs, ys):
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def geomean(values):
    product = 1.0
    for v in values:
        product *= v
    return product ** (1 / len(values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sweep")
    parser.add_argument("--out")
    args = parser.parse_args()
    rows = [r for r in csv.DictReader(open(args.sweep)) if r["status"] == "ok"]
    byProgram = defaultdict(list)
    for r in rows:
        byProgram[r["program"]].append(r)
    out = []
    for p, rs in byProgram.items():
        saved = [int(r["saved"]) for r in rs]
        cycles = [int(r["cycle_delta"]) for r in rs]
        instr = [int(r["instret_delta"]) for r in rs]
        rho = spearman(saved, cycles)
        rhoInstr = spearman(saved, instr)
        best = max(rs, key=lambda r: int(r["cycle_delta"]))
        top = max(rs, key=lambda r: int(r["saved"]))
        out.append({"program": p, "candidates": len(rs),
                    "rho_saved_vs_cycles": "" if rho is None else round(rho, 3),
                    "rho_saved_vs_instret": "" if rhoInstr is None else round(rhoInstr, 3),
                    "finder_top_is_best": top is best,
                    "best_by_cycles": best["formula"], "best_cycles_saved": best["cycle_delta"],
                    "finder_top": top["formula"], "finder_top_cycles_saved": top["cycle_delta"],
                    "geomean_speedup": round(geomean([float(r["speedup"]) for r in rs]), 4),
                    "geomean_cycles_only": round(geomean([float(r["speedup_cycles_only"]) for r in rs]), 4)})
    for o in out:
        print(f"{o['program']:14} n={o['candidates']:>2} rho(saved,cycles)={str(o['rho_saved_vs_cycles']):>6} "
              f"rho(saved,instret)={str(o['rho_saved_vs_instret']):>6} finder top is best: {o['finder_top_is_best']}")
    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)


if __name__ == "__main__":
    main()
