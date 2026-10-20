import argparse
import csv
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isaforge.features import parse_formula  # noqa: E402

# PROVISIONAL selection experiments. Two ways to pick up to 3 formulas for one core:
#   frequency  rank canonical formulas by saved summed over the 8 programs (finder saved, or the
#              rewriter's placeable saved from placeability.csv), take the top 3 that don't conflict
#   oracle     from the single-candidate measurements, estimate every non-conflicting set of up to
#              3 within a LUT budget, assuming cycles and LUTs add, and rank by the geometric mean
#              of the estimated per-program speedup
# Conflict rule (as in the frequency-ranking baseline): two formulas conflict if, in any program,
# a site the finder counted for one shares an instruction with a site it counted for the other.
PROGRAMS = ["aha-mont64", "crc32", "edn", "huffbench", "matmult-int", "nettle-aes", "nettle-sha256", "wikisort"]
BASE_PERIOD = 1000 / 61.48


def canonical(formula):
    return parse_formula(formula).canonical()


def finderSites():
    # (program, pc) instructions of every finder-counted site, per canonical formula
    sites = {}
    for p in PROGRAMS:
        for f, ss in json.load(open(f"generated/hw/engine/finder/{p}.json"))["sites"].items():
            sites.setdefault(canonical(f), set()).update((p, pc) for s in ss for pc in s["pcs"])
    return sites


def conflicts(a, b, sites):
    return bool(sites.get(a, set()) & sites.get(b, set()))


def geomean(values):
    product = 1.0
    for v in values:
        product *= v
    return product ** (1 / len(values))


def baseline():
    return {r["benchmark"]: int(r["cycles"]) for r in csv.DictReader(open("hw/results/baseline.csv"))}


def writeRequest(path, formulas, sizes):
    with open(path, "w") as f:
        json.dump([{"formula": x, "size": sizes[x]} for x in formulas], f, indent=1)


def frequency(args):
    sites = finderSites()
    total, sizes = {}, {}
    if args.placeable:
        for r in csv.DictReader(open("hw/engine/results/placeability.csv")):
            total[r["formula"]] = total.get(r["formula"], 0) + int(r["placeable_saved"])
            sizes[r["formula"]] = int(r["size"])
    else:
        for p in PROGRAMS:
            for c in json.load(open(f"generated/candidates/{p}.json")):
                f = canonical(c["formula"])
                total[f] = total.get(f, 0) + c["saved"]
                sizes[f] = c["size"]
    picked, log = [], []
    for i, f in enumerate(sorted(total, key=lambda f: (-total[f], f)), 1):
        if total[f] <= 0:
            break
        clash = [g for g in picked if conflicts(f, g, sites)]
        log.append({"rank": i, "formula": f, "total_saved": total[f],
                    "outcome": "conflicts with " + ", ".join(clash) if clash else "picked"})
        if not clash:
            picked.append(f)
        if len(picked) == 3:
            break
    for e in log:
        print(f"{e['rank']:>3} {e['total_saved']:>8} {e['formula']:55} {e['outcome']}")
    writeRequest(args.out, picked, sizes)
    with open(args.out.replace(".request.json", ".selection.json"), "w") as f:
        json.dump({"method": "frequency", "ranked_by": "placeable_saved" if args.placeable else "finder_saved",
                   "log": log, "picked": picked}, f, indent=1)
    print(f"wrote {args.out}")


def oracle(args):
    # per formula: LUT delta, routed Fmax, and cycles saved in every program, each measured alone
    sites = finderSites()
    base = baseline()
    measured, sizes = {}, {}
    for r in csv.DictReader(open(args.sweep)):
        if r["status"] != "ok" or r["formula"] in measured:
            continue
        build = json.load(open(f"hw/engine/results/builds/{os.path.basename(r['build'])}.json"))
        measured[r["formula"]] = {"luts": build["luts"]["delta"], "fmax": build["fmax_mhz"]["median"],
                                  "saved": {p: build["programs"][p]["cycles_saved"] for p in PROGRAMS}}
        sizes[r["formula"]] = int(r["size"])
    formulas = sorted(measured)
    estimates = []
    for n in (1, 2, 3):
        for combo in itertools.combinations(formulas, n):
            if any(conflicts(a, b, sites) for a, b in itertools.combinations(combo, 2)):
                continue
            luts = sum(measured[f]["luts"] for f in combo)
            if luts > args.budget:
                continue
            saved = {p: sum(measured[f]["saved"][p] for f in combo) for p in PROGRAMS}
            cyclesOnly = {p: base[p] / (base[p] - saved[p]) for p in PROGRAMS}
            # the set's clock is unknown before it is built; the slowest member is the pessimistic guess
            period = max(BASE_PERIOD, 1000 / min(measured[f]["fmax"] for f in combo))
            ruled = {p: cyclesOnly[p] * BASE_PERIOD / period for p in PROGRAMS}
            estimates.append({"formulas": list(combo), "est_luts": luts,
                              "est_fmax_min_member": min(measured[f]["fmax"] for f in combo),
                              "est_geomean_cycles_only": geomean(cyclesOnly.values()),
                              "est_geomean_max_rule": geomean(ruled.values()),
                              "est_cycles_saved": saved})
    estimates.sort(key=lambda e: (-e["est_geomean_cycles_only"], e["est_luts"]))
    top = estimates[:args.keep]
    for i, e in enumerate(top, 1):
        print(f"{i} est geomean cycles-only {e['est_geomean_cycles_only']:.4f} (max rule, pessimistic "
              f"{e['est_geomean_max_rule']:.4f}) LUT +{e['est_luts']}: {', '.join(e['formulas'])}")
        writeRequest(f"{args.out}-set{i}.request.json", e["formulas"], sizes)
    with open(f"{args.out}.estimates.json", "w") as f:
        json.dump({"method": "oracle", "budget": args.budget, "sweep": args.sweep, "sets_considered": len(estimates),
                   "formulas_measured_alone": len(formulas), "assumption": "cycles and LUTs add; clock = slowest member",
                   "top": top}, f, indent=1)
    print(f"{len(estimates)} non-conflicting sets within +{args.budget} LUT4; wrote {args.keep} requests")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("frequency")
    f.add_argument("--placeable", action="store_true")
    f.add_argument("--out", required=True)
    o = sub.add_parser("oracle")
    o.add_argument("--sweep", default="hw/engine/results/sweep-top10-placeable.csv")
    o.add_argument("--budget", type=int, required=True)
    o.add_argument("--keep", type=int, default=3)
    o.add_argument("--out", required=True)
    args = parser.parse_args()
    (frequency if args.mode == "frequency" else oracle)(args)


if __name__ == "__main__":
    main()
