import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from baseline import countLuts, differentWords, readFmax  # noqa: E402
from isaforge.features import candidate_id, parse_formula  # noqa: E402
from microtest import TIMED, TRAPS  # noqa: E402

DR = "generated/hw/dryrun"
BASE_LUTS = 2439
OBJDUMP = os.environ.get("RISCV_PREFIX", "riscv-none-elf-") + "objdump"


def load(path):
    with open(path) as f:
        return json.load(f)


def baseline():
    # the committed baseline, one row per program
    with open("hw/results/baseline.csv") as f:
        return {row["benchmark"]: row for row in csv.DictReader(f)}


def chainSites(elf):
    # finds xor/zext.b/slli-by-2 chains in the unrewritten program, the code the rewriter replaced
    text = subprocess.run([OBJDUMP, "-d", "-M", "no-aliases", elf],
                          capture_output=True, text=True, check=True).stdout
    lines = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].strip().endswith(":"):
            lines.append((int(parts[0].strip()[:-1], 16), parts[2].strip(),
                          parts[3].strip() if len(parts) > 3 else ""))
    sites = []
    for (pc, op1, a1), (_, op2, a2), (_, op3, a3) in zip(lines, lines[1:], lines[2:]):
        x = a1.split(",")[0]
        if op1 == "xor" and op2 == "andi" and a2 == f"{x},{x},255" and op3 == "slli":
            y = a3.split(",")
            if y[1] == x and y[2] in ("2", "0x2"):
                sites.append(pc)
    return sites


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formula", required=True)
    parser.add_argument("--programs", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    problems = []
    base = baseline()

    # the candidate as the finder reported it
    candidate = next(c for c in load("generated/candidates/crc32.json") if c["formula"] == args.formula)

    # the control must be byte-identical to the baseline image, so compiling via .s changed nothing
    if differentWords("generated/hw/programs/crc32.bin", f"{DR}/programs/crc32-control.bin") != []:
        problems.append("crc32 built through assembly differs from the baseline PicoRV32 image")

    # where the replaced chains sat in the baseline program and how often each ran in Spike's trace
    runs = Counter()
    with open("generated/traces/crc32.jsonl") as f:
        for line in f:
            runs[int(json.loads(line)["pc"], 16)] += 1
    rewrite = load(f"{DR}/sw/rewrite.json")
    sitePcs = chainSites(f"{DR}/programs/crc32-control.elf")
    if len(sitePcs) != len(rewrite["sites"]):
        problems.append(f"{len(rewrite['sites'])} rewritten sites but {len(sitePcs)} chains in the program")
    sites = [{**site, "pc": f"{pc:#010x}", "runs": runs[pc]} for site, pc in zip(rewrite["sites"], sitePcs)]
    executed = sum(s["runs"] for s in sites)
    size = candidate["size"]

    # the fused program on the fused core
    fused = load(f"{DR}/runs/fused/crc32-fused.json")
    if fused["error"] or fused["exit_word"] != 1:
        problems.append(f"fused crc32 failed: error {fused['error']}, exit word {fused['exit_word']}")
    baseCycles, baseInstret = int(base["crc32"]["cycles"]), int(base["crc32"]["instret"])
    instretSaved = baseInstret - fused["instret"]
    if instretSaved != (size - 1) * executed:
        problems.append(f"instret saved {instretSaved} vs (size-1)*sites executed {(size - 1) * executed}")
    if instretSaved != candidate["saved"]:
        problems.append(f"instret saved {instretSaved} vs candidate saved {candidate['saved']}")

    # every stock program on the fused core must match the baseline exactly
    stock = {}
    for program in args.programs:
        run = load(f"{DR}/runs/fused/stock-{program}.json")
        row = base[program]
        same = (not run["error"] and run["exit_word"] == 1 and
                run["window_cycles"] == int(row["cycles"]) and run["instret"] == int(row["instret"]))
        stock[program] = {"cycles": run["window_cycles"], "instret": run["instret"],
                          "baseline_cycles": int(row["cycles"]), "baseline_instret": int(row["instret"]),
                          "identical": same}
        if not same:
            problems.append(f"stock {program} on the fused core: {run} vs baseline cycles {row['cycles']}, "
                            f"instret {row['instret']}")

    # microtests: the vectors pass, unclaimed encodings trap, and the stock core traps on the new one
    micro = {"check": load(f"{DR}/runs/fused/micro-check.json")}
    if micro["check"]["error"] or micro["check"]["exit_word"] != 1:
        problems.append(f"microtest failed on the fused core: {micro['check']}")
    for name in TRAPS:
        run = load(f"{DR}/runs/fused/{name}.json")
        micro[name] = run["error"]
        if run["error"] != "processor trap":
            problems.append(f"{name} did not trap on the fused core: {run}")
    for name in ("micro-check", "trap-f3-1"):
        run = load(f"{DR}/runs/stock/{name}.json")
        micro[f"stock-{name}"] = run["error"]
        if run["error"] != "processor trap":
            problems.append(f"{name} did not trap on the stock core: {run}")
    perBlock = {}
    for kind in ("fused", "original", "xor"):
        one = load(f"{DR}/runs/fused/micro-{kind}-1x.json")
        two = load(f"{DR}/runs/fused/micro-{kind}-2x.json")
        perBlock[kind] = (two["window_cycles"] - one["window_cycles"]) / TIMED
    micro["cycles_per_block"] = perBlock
    cyclesSavedPredicted = round((perBlock["original"] - perBlock["fused"]) * executed)

    # area and Fmax with the baseline's synthesis, pins and seeds
    luts = countLuts(f"{DR}/synth/core_top.json")
    perSeed = {s: readFmax(f"{DR}/route/seed{s}/report.json")[0] for s in args.seeds}
    fmax = statistics.median(perSeed.values())
    baseFmax = float(base["crc32"]["fmax_mhz"])

    basePeriod, fusedPeriod = 1000 / baseFmax, 1000 / fmax
    speedup = (baseCycles * basePeriod) / (fused["window_cycles"] * fusedPeriod)
    row = {"candidate_id": candidate_id("crc32", args.formula),
           "benchmark": "crc32", "formula": parse_formula(args.formula).canonical(),
           "measurement_source": "hardware",
           "baseline_cycles": baseCycles, "candidate_cycles": fused["window_cycles"],
           "baseline_period_ns": round(basePeriod, 4), "candidate_period_ns": round(fusedPeriod, 4),
           "luts": luts, "speedup": round(speedup, 4)}

    result = {
        "provisional": True,
        "candidate": candidate,
        "encoding": {"opcode": "0x0b", "funct7": 2, "funct3": 0},
        "sites": sites, "skipped_sites": rewrite["skipped"], "sites_executed": executed,
        "fused_run": fused,
        "instret": {"baseline": baseInstret, "fused": fused["instret"], "saved": instretSaved,
                    "size_minus_1_times_sites": (size - 1) * executed, "candidate_saved": candidate["saved"]},
        "cycles": {"baseline": baseCycles, "fused": fused["window_cycles"],
                   "saved": baseCycles - fused["window_cycles"], "saved_predicted_from_microtest": cyclesSavedPredicted},
        "stock_on_fused_core": stock,
        "microtest": micro,
        "luts": {"baseline": BASE_LUTS, "fused": luts, "delta": luts - BASE_LUTS},
        "fmax_mhz": {"per_seed": {s: round(v, 2) for s, v in perSeed.items()},
                     "median": round(fmax, 2), "min": round(min(perSeed.values()), 2),
                     "max": round(max(perSeed.values()), 2), "baseline_median": baseFmax},
        "speedup_cycles_only": round(baseCycles / fused["window_cycles"], 4),
        "measurement_row": row,
        "problems": problems,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
    print(json.dumps(result, indent=1))
    # reports every mismatch instead of hiding it
    if problems:
        sys.exit("DRY RUN CHECK FAILED\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
