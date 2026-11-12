import argparse
import csv
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from baseline import countLuts, readFmax  # noqa: E402

# Probe: the stock core with ENABLE_FAST_MUL=1 and no fused units, measured exactly like the
# baseline (same programs, window, frozen pins, seeds) and compared with the sequential baseline.
# It changes nothing about the baseline; it answers what the multiplier choice is worth.
HW = "hw"
OUT = "generated/hw/fastmul"
PREFIX = os.environ.get("RISCV_PREFIX", "riscv-none-elf-")


def run(cmd, log=None, **kw):
    with open(log, "w") if log else open(os.devnull, "w") as f:
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT, **kw)


def symbol(elf, name):
    text = subprocess.run([PREFIX + "nm", elf], capture_output=True, text=True, check=True).stdout
    return "0x" + next(l.split()[0] for l in text.splitlines() if l.split()[-1] == name)


def geomean(values):
    product = 1.0
    for v in values:
        product *= v
    return product ** (1 / len(values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--programs", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--freq", default="12")
    parser.add_argument("--max-cycles", default="4000000000")
    parser.add_argument("--out", required=True, help="path stem; writes <stem>.csv and <stem>.json")
    args = parser.parse_args()
    for sub in ("sim", "synth", "runs", "route"):
        os.makedirs(f"{OUT}/{sub}", exist_ok=True)

    run(["verilator", "--cc", "--exe", "--build", "-j", "4", "-O3", "-Wno-fatal", "--top-module", "core_top",
         "-GFAST_MUL=1", "-CFLAGS", "-std=c++17", "--Mdir", f"{OUT}/sim", f"{HW}/rtl/picorv32.v",
         f"{HW}/rtl/core_top.v", f"{HW}/sim/core_sim.cpp", "-o", "Vcore_top"], f"{OUT}/sim/build.log")
    runs = {}
    for p in args.programs:
        elf = f"generated/hw/programs/{p}.elf"
        out = subprocess.run([f"{OUT}/sim/Vcore_top", f"generated/hw/programs/{p}.bin", symbol(elf, "tohost"),
                              symbol(elf, "instret_start"), symbol(elf, "instret_stop"), args.max_cycles],
                             capture_output=True, text=True).stdout
        runs[p] = json.loads(out)
        with open(f"{OUT}/runs/{p}.json", "w") as f:
            f.write(out)

    with open(f"{OUT}/synth.ys", "w") as f:
        f.write(f"read_verilog {HW}/rtl/picorv32.v {HW}/rtl/core_top.v\nchparam -set FAST_MUL 1 core_top\n"
                f"synth_ice40 -top core_top\ncheck -assert\nwrite_json {OUT}/synth/core_top.json\n"
                f"tee -o {OUT}/synth/stat.txt stat\n")
    run(["yosys", "-q", "-l", f"{OUT}/synth/yosys.log", "-s", f"{OUT}/synth.ys"])
    procs = []
    for s in args.seeds:
        os.makedirs(f"{OUT}/route/seed{s}", exist_ok=True)
        procs.append(subprocess.Popen(["nextpnr-ice40", "--hx8k", "--package", "ct256", "--json", f"{OUT}/synth/core_top.json",
                                       "--pcf", f"{HW}/synth/core_top.pcf", "--freq", args.freq, "--seed", s,
                                       "--threads", "1", "--report", f"{OUT}/route/seed{s}/report.json",
                                       "--log", f"{OUT}/route/seed{s}/nextpnr.log", "--quiet"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for proc in procs:
        if proc.wait():
            sys.exit("nextpnr failed")
    run(["python3", f"{HW}/scripts/critpath.py", "--core", "fastmul", "--netlist", f"{OUT}/synth/core_top.json",
         "--routes", f"{OUT}/route", "--seeds", *args.seeds, "--out", f"{OUT}/critical_paths.csv"])

    base = {r["benchmark"]: r for r in csv.DictReader(open(f"{HW}/results/baseline.csv"))}
    luts = countLuts(f"{OUT}/synth/core_top.json")
    perSeed = {s: readFmax(f"{OUT}/route/seed{s}/report.json")[0] for s in args.seeds}
    fmax = statistics.median(perSeed.values())
    baseFmax = float(base[args.programs[0]]["fmax_mhz"])
    basePeriod, period = 1000 / baseFmax, max(1000 / baseFmax, 1000 / fmax)
    crit = list(csv.DictReader(open(f"{OUT}/critical_paths.csv")))
    mulArc = sum(1 for r in crit if "pcpi_mul" in r["start"] and "pcpi_mul" in r["end"])

    rows, problems = [], []
    for p in args.programs:
        r, b = runs[p], base[p]
        ok = r["error"] is None and r["exit_word"] == 1 and r["instret"] == int(b["instret"])
        if not ok:
            problems.append(f"{p}: {r} vs baseline instret {b['instret']}")
        bc, fc = int(b["cycles"]), r["window_cycles"]
        rows.append({"benchmark": p, "baseline_cycles": bc, "fastmul_cycles": fc, "cycle_delta": fc - bc,
                     "instret": r["instret"], "verified_and_instret_match": ok,
                     "speedup_cycles_only": round(bc / fc, 4), "speedup_max_rule": round((bc * basePeriod) / (fc * period), 4),
                     "luts": luts, "baseline_luts": int(b["luts"]), "fmax_mhz": round(fmax, 2),
                     "fmax_min_mhz": round(min(perSeed.values()), 2), "fmax_max_mhz": round(max(perSeed.values()), 2),
                     "baseline_fmax_mhz": baseFmax, "mul_on_critical_arc_seeds": mulArc})
    with open(args.out + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = {"probe": "stock core, ENABLE_FAST_MUL=1, no fused units; not a baseline change",
               "luts": luts, "lut_delta": luts - int(base[args.programs[0]]["luts"]),
               "fmax_mhz": {"per_seed": {s: round(v, 2) for s, v in perSeed.items()}, "median": round(fmax, 2),
                            "min": round(min(perSeed.values()), 2), "max": round(max(perSeed.values()), 2)},
               "period_ns": {"baseline": round(basePeriod, 4), "fastmul_routed": round(1000 / fmax, 4), "used": round(period, 4)},
               "multiplier_on_critical_arc_seeds": mulArc, "critical_paths": crit,
               "geomean_speedup_cycles_only": round(geomean([r["speedup_cycles_only"] for r in rows]), 4),
               "geomean_speedup_max_rule": round(geomean([r["speedup_max_rule"] for r in rows]), 4),
               "programs": rows, "problems": problems}
    with open(args.out + ".json", "w") as f:
        json.dump(summary, f, indent=1)
    for r in rows:
        print(f"{r['benchmark']:14} {r['baseline_cycles']:>10} -> {r['fastmul_cycles']:>10}  cycles-only {r['speedup_cycles_only']}  "
              f"max rule {r['speedup_max_rule']}  ok {r['verified_and_instret_match']}")
    print(f"LUT4 {luts} ({luts - int(base[args.programs[0]]['luts']):+d}), Fmax median {fmax:.2f}, multiplier on the arc in "
          f"{mulArc}/{len(crit)} seeds; geomean cycles-only {summary['geomean_speedup_cycles_only']}, "
          f"max rule {summary['geomean_speedup_max_rule']}")
    if problems:
        sys.exit("PROBE CHECK FAILED\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
