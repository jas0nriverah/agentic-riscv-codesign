import argparse
import csv
import json
import os
import subprocess

# Compares the selection experiments: each one is a request file, measured by make hw-measure,
# plus (for the oracle) the estimate it was chosen on. Writes experiments.csv/.json and prints a
# table with per-program speedups under both rules, the geometric means, LUTs, Fmax, and how many
# hardware builds each method needed.
PROGRAMS = ["aha-mont64", "crc32", "edn", "huffbench", "matmult-int", "nettle-aes", "nettle-sha256", "wikisort"]
R = "hw/engine/results"


def geomean(values):
    product = 1.0
    for v in values:
        product *= v
    return product ** (1 / len(values))


def buildId(request):
    return subprocess.run(["python3", "hw/engine/units.py", "--candidates", request, "--allow-mul", "--id-only"],
                          capture_output=True, text=True, check=True).stdout.strip()


def load(request):
    ident = buildId(request)
    path = f"generated/hw/engine/{ident}/results.json"
    if not os.path.exists(path):
        path = f"{R}/builds/{ident}.json"
    return ident, json.load(open(path))


def summarize(name, method, request, result, buildsNeeded, estimate=None):
    # the full result is archived with the other measured cores
    os.makedirs(f"{R}/builds", exist_ok=True)
    with open(f"{R}/builds/{result['id']}.json", "w") as f:
        json.dump(result, f, indent=1)
    rows = {r["benchmark"]: r for r in result["rows"]}
    ruled = {p: rows[p]["speedup"] for p in PROGRAMS}
    cyc = {p: rows[p]["speedup_cycles_only"] for p in PROGRAMS}
    out = {"experiment": name, "method": method, "build": result["id"], "formulas": result["priority"],
           "luts_delta": result["luts"]["delta"], "fmax_median": result["fmax_mhz"]["median"],
           "fmax_min": result["fmax_mhz"]["min"], "fmax_max": result["fmax_mhz"]["max"],
           "unit_on_arc_seeds": len(result["critical_path"]["unit_on_arc_seeds"]),
           "geomean_max_rule": round(geomean(ruled.values()), 4), "geomean_cycles_only": round(geomean(cyc.values()), 4),
           "hardware_builds_needed": buildsNeeded, "request": request}
    for p in PROGRAMS:
        out[f"{p}_max_rule"] = ruled[p]
        out[f"{p}_cycles_only"] = cyc[p]
        out[f"{p}_cycles_saved"] = result["programs"][p]["cycles_saved"]
    if estimate:
        out.update({"est_luts_delta": estimate["est_luts"], "est_geomean_cycles_only": round(estimate["est_geomean_cycles_only"], 4),
                    "est_geomean_max_rule_pessimistic": round(estimate["est_geomean_max_rule"], 4),
                    "est_cycles_saved": estimate["est_cycles_saved"]})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-candidate-builds", type=int, required=True,
                        help="how many single-candidate cores the oracle's estimates rest on")
    parser.add_argument("--out", default=f"{R}/experiments")
    args = parser.parse_args()
    experiments = []
    ident, res = load(f"{R}/frequency-top3.request.json")
    experiments.append(summarize("E frequency (finder saved)", "frequency", f"{R}/frequency-top3.request.json", res, 1))
    ident, res = load(f"{R}/frequency-placeable-top3.request.json")
    experiments.append(summarize("C1 frequency (placeable saved)", "frequency-placeable",
                                 f"{R}/frequency-placeable-top3.request.json", res, 1))
    seen = {}
    for budget in (100, 250, 500):
        est = json.load(open(f"{R}/oracle-lut{budget}.estimates.json"))
        for i, e in enumerate(est["top"], 1):
            request = f"{R}/oracle-lut{budget}-set{i}.request.json"
            ident, res = load(request)
            seen.setdefault(ident, []).append(f"+{budget}/set{i}")
            experiments.append(summarize(f"C2 oracle +{budget} set {i}", "oracle", request, res,
                                         args.single_candidate_builds + len(seen), e))
    # the oracle's build count: the single-candidate cores plus every distinct set actually built
    for x in experiments:
        if x["method"] == "oracle":
            x["hardware_builds_needed"] = args.single_candidate_builds + len(seen)
    with open(args.out + ".json", "w") as f:
        json.dump({"experiments": experiments, "distinct_oracle_cores": seen}, f, indent=1)
    fields = [k for k in experiments[-1] if k != "est_cycles_saved"]
    with open(args.out + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(experiments)
    print(f"{'experiment':30} {'LUT':>5} {'fmax':>6} {'arc':>3} {'gm max':>7} {'gm cyc':>7} {'est cyc':>7} {'builds':>6}  formulas")
    for x in experiments:
        print(f"{x['experiment']:30} {x['luts_delta']:>+5} {x['fmax_median']:>6} {x['unit_on_arc_seeds']:>3} "
              f"{x['geomean_max_rule']:>7} {x['geomean_cycles_only']:>7} {x.get('est_geomean_cycles_only', ''):>7} "
              f"{x['hardware_builds_needed']:>6}  {', '.join(x['formulas'])}")


if __name__ == "__main__":
    main()
