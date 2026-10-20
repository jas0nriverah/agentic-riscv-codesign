import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from baseline import countLuts, differentWords, readFmax  # noqa: E402
from isaforge.features import candidate_id  # noqa: E402

BASE_LUTS = 2439
PREFIX = os.environ.get("RISCV_PREFIX", "riscv-none-elf-")


def load(path):
    with open(path) as f:
        return json.load(f)


def symbols(elf):
    # every symbol's address, and the function each address falls in
    text = subprocess.run([PREFIX + "nm", "-n", elf], capture_output=True, text=True, check=True).stdout
    table = [(int(a, 16), t, n) for a, t, n in (l.split() for l in text.splitlines() if len(l.split()) == 3)]
    return {n: a for a, _, n in table}, sorted((a, n) for a, t, n in table if t in "tT" and not n.startswith("hws_"))


def functionAt(functions, pc):
    best = None
    for a, n in functions:
        if a > pc:
            break
        best = n
    return best


def microtests(build, manifest, problems):
    out = {"checks": manifest["micro_checks"], "runs": {}}
    for name, spec in manifest["microtests"].items():
        run = load(f"{build}/runs/micro/{name}.json")
        ok = (not run["error"] and run["exit_word"] == 1) if spec["expect"] == "pass" else run["error"] == "processor trap"
        out["runs"][name] = {"expect": spec["expect"], "core": spec["core"], "ok": ok,
                             "error": run["error"], "exit_word": run["exit_word"]}
        if not ok:
            problems.append(f"microtest {name} on the {spec['core']} core should {spec['expect']}: {run}")

    def perInsn(name):
        one, two = load(f"{build}/runs/micro/{name}-1x.json"), load(f"{build}/runs/micro/{name}-2x.json")
        return (two["window_cycles"] - one["window_cycles"]) / 64

    out["cycles_per_insn"] = {s["formula"]: perInsn(f"micro-s{s['slot']}") for s in manifest["slots"]}
    out["cycles_per_xor"] = perInsn("micro-xor")
    return out


def reconcile(program, build, manifest, sizes, problems):
    # the rewriter's sites against the finder's, with the trace's run counts for both
    rewrite = load(f"{build}/sw/{program}/sites.json")
    finder = load(f"generated/hw/engine/finder/{program}.json")
    runs = {int(pc, 16): n for pc, n in finder["runs"].items()}
    labels, _ = symbols(f"{build}/programs/{program}-marked.elf")
    _, functions = symbols(f"generated/programs/{program}.elf")
    rewritten = set(rewrite["functions"])

    ours = {}
    for site in rewrite["sites"]:
        pcs = [labels[l] for l in site["labels"]]
        site["pcs"] = [f"{pc:#010x}" for pc in pcs]
        site["runs"] = runs.get(pcs[site["lines"].index(site["root_line"])], 0)
        ours[frozenset(pcs)] = site

    per = {}
    for slot in manifest["slots"]:
        formula, size = slot["formula"], sizes[slot["formula"]]
        fused = [s for s in rewrite["sites"] if s["formula"] == formula and s["status"] == "fused"]
        predicted = sum((size - 1) * s["runs"] for s in fused)
        gaps = defaultdict(lambda: {"sites": 0, "runs": 0, "saved": 0})
        finderSaved, matched = 0, set()
        for fs in finder["sites"].get(formula, []):
            saved = (size - 1) * fs["runs"]
            finderSaved += saved
            site = ours.get(frozenset(fs["pcs"]))
            if site is not None and site["formula"] == formula:
                matched.add(site["id"])
                if site["status"] == "fused":
                    continue
                reason = "skipped by the rewriter: " + "; ".join(site["reasons"])
            else:
                fn = functionAt(functions, fs["root"])
                reason = (f"in {fn}, which is library code the rewriter does not see" if fn not in rewritten
                          else f"in {fn}: the rewriter found no matching site (UNEXPLAINED)")
                if fn in rewritten:
                    problems.append(f"{program}: finder site of {formula} at {fs['root']:#x} not found by the rewriter")
            g = gaps[reason]
            g["sites"] += 1
            g["runs"] += fs["runs"]
            g["saved"] += saved
        extra = [s for s in fused if s["id"] not in matched and s["runs"]]
        for s in extra:
            problems.append(f"{program}: fused site {s['id']} ran {s['runs']} times but the finder did not count it")
        per[formula] = {"finder_saved": finderSaved, "predicted_saved": predicted,
                        "fused_sites": len(fused), "fused_sites_executed": sum(1 for s in fused if s["runs"]),
                        "gap": finderSaved - predicted, "gap_reasons": dict(gaps)}
    return per, rewrite["sites"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--programs", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build, problems = args.build, []
    manifest = load(f"{build}/manifest.json")
    sizes = {s["formula"]: s["size"] for s in manifest["slots"]}
    with open("hw/results/baseline.csv") as f:
        base = {r["benchmark"]: r for r in csv.DictReader(f)}

    micro = microtests(build, manifest, problems)

    # area, Fmax, and the provisional period rule from the critical-path check
    luts = countLuts(f"{build}/synth/core_top.json")
    perSeed = {s: readFmax(f"{build}/route/seed{s}/report.json")[0] for s in args.seeds}
    fmax = statistics.median(perSeed.values())
    with open(f"{build}/critical_paths.csv") as f:
        crit = list(csv.DictReader(f))
    onArc = [r["seed"] for r in crit if r["unit_on_arc"] == "True"]
    if sorted(r["seed"] for r in crit) != sorted(args.seeds):
        problems.append(f"critical-path table covers {[r['seed'] for r in crit]}")
    basePeriod = 1000 / float(base["crc32"]["fmax_mhz"])
    routedPeriod = 1000 / fmax
    # PROVISIONAL rule (hw/README.md): never credit a faster clock, always take a slower one
    period = max(basePeriod, routedPeriod)

    programs, rows = {}, []
    for p in args.programs:
        row = base[p]
        # the marked build must be the baseline image, or the labels moved code
        if differentWords(f"generated/hw/programs/{p}.bin", f"{build}/programs/{p}-marked.bin") != []:
            problems.append(f"{p}: the labelled control build differs from the baseline image")
        stock = load(f"{build}/runs/stock/{p}.json")
        stockSame = (not stock["error"] and stock["exit_word"] == 1 and
                     stock["window_cycles"] == int(row["cycles"]) and stock["instret"] == int(row["instret"]))
        if not stockSame:
            problems.append(f"{p}: stock program on the engine core {stock} vs baseline {row['cycles']}, {row['instret']}")
        fused = load(f"{build}/runs/fused/{p}.json")
        if fused["error"] or fused["exit_word"] != 1:
            problems.append(f"{p}: fused program failed: error {fused['error']}, exit word {fused['exit_word']}")
        per, sites = reconcile(p, build, manifest, sizes, problems)
        measured = int(row["instret"]) - fused["instret"]
        predicted = sum(v["predicted_saved"] for v in per.values())
        if measured != predicted:
            problems.append(f"{p}: instret saved {measured}, predicted from fused sites {predicted}")
        cycles = fused["window_cycles"]
        programs[p] = {"verified": not fused["error"] and fused["exit_word"] == 1, "stock_unchanged": stockSame,
                       "baseline_cycles": int(row["cycles"]), "cycles": cycles,
                       "cycles_saved": int(row["cycles"]) - cycles,
                       "baseline_instret": int(row["instret"]), "instret": fused["instret"],
                       "instret_saved": measured, "instret_saved_predicted": predicted, "per_formula": per,
                       "sites": sites}
        formulas = [s["formula"] for s in manifest["slots"]]
        ids = [candidate_id(p, f) for f in formulas]
        rows.append({"candidate_id": ids[0] if len(ids) == 1 else ids, "benchmark": p,
                     "formula": formulas[0] if len(formulas) == 1 else formulas,
                     "measurement_source": "hardware", "baseline_cycles": int(row["cycles"]),
                     "candidate_cycles": cycles, "baseline_period_ns": round(basePeriod, 4),
                     "candidate_period_ns": round(period, 4), "luts": luts,
                     "speedup": round((int(row["cycles"]) * basePeriod) / (cycles * period), 4),
                     "speedup_cycles_only": round(int(row["cycles"]) / cycles, 4)})

    result = {"provisional": True, "id": manifest["id"], "slots": manifest["slots"],
              "priority": manifest["priority"], "microtest": micro,
              "luts": {"baseline": BASE_LUTS, "engine": luts, "delta": luts - BASE_LUTS},
              "fmax_mhz": {"per_seed": {s: round(v, 2) for s, v in perSeed.items()}, "median": round(fmax, 2),
                           "min": round(min(perSeed.values()), 2), "max": round(max(perSeed.values()), 2)},
              "critical_path": {"unit_on_arc_seeds": onArc, "rows": crit},
              "period_rule": {"rule": "T_fused = max(T_base, T_fused_measured)",
                              "candidate_period_ns": round(period, 4), "routed_period_ns": round(routedPeriod, 4),
                              "used": "routed (slower than the baseline)" if routedPeriod > basePeriod
                                      else "baseline (the routed clock is not slower)"},
              "programs": programs, "rows": rows, "problems": problems}
    # report.json is kept even when a check fails; results.json exists only for a clean build
    for path in [os.path.join(build, "report.json")] + ([] if problems else [args.out]):
        with open(path, "w") as f:
            json.dump(result, f, indent=1)
    with open(os.path.join(build, "rows.jsonl"), "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    for p, v in programs.items():
        print(f"{p}: instret saved {v['instret_saved']} (predicted {v['instret_saved_predicted']}), "
              f"cycles saved {v['cycles_saved']}")
    print(f"LUT4 {luts} ({luts - BASE_LUTS:+d}), Fmax median {fmax:.2f}, unit on arc in seeds {onArc or 'none'}")
    if problems:
        sys.exit("ENGINE CHECK FAILED\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
