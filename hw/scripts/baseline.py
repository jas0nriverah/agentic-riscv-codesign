import argparse
import csv
import json
import statistics
import sys
from collections import Counter


def countLines(path):
    # counts the instructions in a Spike trace one line each
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def differentWords(a, b):
    # lists the word offsets where two program images differ
    with open(a, "rb") as f:
        first = f.read()
    with open(b, "rb") as f:
        second = f.read()
    if len(first) != len(second):
        return None
    return [i for i in range(0, len(first), 4) if first[i:i + 4] != second[i:i + 4]]


def countLuts(netlistPath):
    # counts the SB_LUT4 cells the way the ML branch counted them
    modules = json.load(open(netlistPath))["modules"]
    types = Counter(cell["type"] for module in modules.values()
                    if not module.get("attributes", {}).get("blackbox")
                    for cell in module.get("cells", {}).values())
    return types["SB_LUT4"]


def readFmax(reportPath):
    # takes the slowest clock in one nextpnr report
    report = json.load(open(reportPath))
    return min(clock["achieved"] for clock in report["fmax"].values()), report["utilization"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--programs", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # one area and one Fmax for the stock core, the median over the routing seeds like the ML branch
    luts = countLuts("generated/hw/synth/core_top.json")
    perSeed = {}
    for seed in args.seeds:
        fmax, utilization = readFmax(f"generated/hw/route/seed{seed}/report.json")
        perSeed[seed] = fmax
        cells = utilization["ICESTORM_LC"]
        print(f"seed {seed}: fmax {fmax:.2f} MHz, {cells['used']}/{cells['available']} logic cells")
    fmax = round(statistics.median(perSeed.values()), 2)

    rows = []
    problems = []
    for program in args.programs:
        # the two builds must run the same code or the instret comparison means nothing
        words = differentWords(f"generated/programs/{program}.bin", f"generated/hw/programs/{program}.bin")
        if words is None or len(words) != 1:
            problems.append(f"{program}: PicoRV32 image differs from the Spike image at {words}")

        run = json.load(open(f"generated/hw/runs/{program}.json"))
        # tracing.py already stops unless Spike's counter equals the trace lines plus one
        spikeInstret = countLines(f"generated/traces/{program}.jsonl") + 1
        match = run["instret"] == spikeInstret
        if not match:
            problems.append(f"{program}: PicoRV32 instret {run['instret']} vs Spike {spikeInstret}")
        rows.append({"benchmark": program, "cycles": run["window_cycles"], "instret": run["instret"],
                     "spike_instret": spikeInstret, "match": match, "luts": luts, "fmax_mhz": fmax})

    with open(args.out, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(",".join(str(v) for v in row.values()))
    # reports every mismatch instead of hiding it
    if problems:
        sys.exit("CROSS-CHECK FAILED\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
