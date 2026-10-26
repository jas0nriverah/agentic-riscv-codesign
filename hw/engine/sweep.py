import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

# Single-candidate sweep: each program's top N candidates, each measured alone on its own core.
# A formula that tops several programs is built once; its row is per source program.
PROGRAMS = ["aha-mont64", "crc32", "edn", "huffbench", "matmult-int", "nettle-aes", "nettle-sha256", "wikisort"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--placeable", action="store_true",
                        help="rank by finder saved but keep only candidates hw/engine/results/placeability.csv "
                             "says the rewriter can fuse somewhere (placeable_saved > 0)")
    parser.add_argument("--plan", action="store_true", help="print the candidate list and the mul count, build nothing")
    parser.add_argument("--allow-mul", action="store_true")
    parser.add_argument("--skip-mul", action="store_true", help="leave mul candidates out of the plan")
    parser.add_argument("--jobs", default="8")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.out is None:
        args.out = f"hw/engine/results/sweep-top{args.top}" + ("-placeable" if args.placeable else "")
    os.makedirs("generated/hw/engine/requests", exist_ok=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    placeable = None
    if args.placeable:
        placeable = {(r["program"], r["formula"]): int(r["placeable_saved"])
                     for r in csv.DictReader(open("hw/engine/results/placeability.csv"))}
    wanted = []
    for p in PROGRAMS:
        taken = 0
        for rank, c in enumerate(json.load(open(f"generated/candidates/{p}.json")), 1):
            if placeable is not None and placeable.get((p, c["formula"]), 0) <= 0:
                continue
            wanted.append((p, rank, c))
            taken += 1
            if taken == args.top:
                break
    if args.skip_mul:
        wanted = [(p, rank, c) for p, rank, c in wanted if not re.search(r"\bmul", c["formula"])]
    distinct = sorted({c["formula"] for _, _, c in wanted})
    withMul = [f for f in distinct if re.search(r"\bmul", f)]
    print(f"{len(wanted)} rows, {len(distinct)} distinct formulas to build, {len(withMul)} with mul", flush=True)
    if args.plan:
        for p, rank, c in wanted:
            flag = "MUL " if c["formula"] in withMul else "    "
            print(f"  {p:14} finder rank {rank:>3}  {flag}{c['formula']}")
        return
    if withMul and not args.allow_mul:
        sys.exit("mul candidates in the plan; rerun with --allow-mul to build them: " + ", ".join(withMul))

    builds = {}
    for p, rank, c in wanted:
        if c["formula"] in builds:
            continue
        request = f"generated/hw/engine/requests/{hashlib.sha256(c['formula'].encode()).hexdigest()[:12]}.json"
        # rewritten only when it changes: a fresh timestamp would make make rebuild the whole core
        text = json.dumps([{"formula": c["formula"], "size": c["size"], "benchmark": p}])
        if not os.path.exists(request) or open(request).read() != text:
            with open(request, "w") as f:
                f.write(text)
        env = dict(os.environ, **({"ALLOW_MUL": "1"} if args.allow_mul else {}))
        cmd = ["make", f"-j{args.jobs}", "hw-measure", f"CANDIDATES={request}"] + (["ALLOW_MUL=1"] if args.allow_mul else [])
        print(f"building {c['formula']}", flush=True)
        run = subprocess.run(cmd, capture_output=True, text=True, env=env)
        ident = subprocess.run(["python3", "hw/engine/units.py", "--candidates", request, "--id-only"] +
                               (["--allow-mul"] if args.allow_mul else []), capture_output=True, text=True)
        build = f"generated/hw/engine/{ident.stdout.strip()}" if ident.returncode == 0 else None
        report = f"{build}/report.json" if build and os.path.exists(f"{build}/report.json") else None
        if report:
            # each build's full result, with every fused and skipped site, kept next to the table
            os.makedirs(os.path.join(os.path.dirname(args.out), "builds"), exist_ok=True)
            shutil.copy(report, os.path.join(os.path.dirname(args.out), "builds", os.path.basename(build) + ".json"))
        builds[c["formula"]] = {"ok": run.returncode == 0, "report": json.load(open(report)) if report else None,
                                "error": None if run.returncode == 0 else (run.stdout + run.stderr)[-600:], "build": build}
        print(f"  {'ok' if run.returncode == 0 else 'FAILED'} {build}", flush=True)

    rows = []
    for p, rank, c in wanted:
        b = builds[c["formula"]]
        r = b["report"]
        row = {"program": p, "rank": rank, "formula": c["formula"], "size": c["size"], "runs": c["runs"],
               "saved": c["saved"], "has_mul": bool(re.search(r"\bmul", c["formula"])), "status": "ok" if b["ok"] else "FAILED"}
        if r:
            prog = r["programs"][p]
            per = prog["per_formula"][c["formula"]]
            crit = r["critical_path"]
            row.update({
                "fused_sites": per["fused_sites"], "predicted_saved": per["predicted_saved"],
                "instret_delta": prog["instret_saved"], "cycle_delta": prog["cycles_saved"],
                "cycles_per_instr_saved": round(prog["cycles_saved"] / prog["instret_saved"], 2) if prog["instret_saved"] else "",
                "gap": per["gap"], "gap_reasons": " | ".join(f"{g['sites']} sites/{g['saved']}: {k}" for k, g in per["gap_reasons"].items()),
                "luts": r["luts"]["engine"], "lut_delta": r["luts"]["delta"],
                "fmax_median": r["fmax_mhz"]["median"], "fmax_min": r["fmax_mhz"]["min"], "fmax_max": r["fmax_mhz"]["max"],
                "on_critical_path_seeds": len(crit["unit_on_arc_seeds"]),
                "speedup": next(x["speedup"] for x in r["rows"] if x["benchmark"] == p),
                "speedup_cycles_only": round(prog["baseline_cycles"] / prog["cycles"], 4),
                "verified": prog["verified"], "stock_unchanged": all(v["stock_unchanged"] for v in r["programs"].values()),
                "other_programs": "; ".join(f"{q}: -{v['instret_saved']} instr, -{v['cycles_saved']} cyc"
                                            for q, v in r["programs"].items() if q != p and v["instret_saved"]),
                "micro_ok": all(v["ok"] for v in r["microtest"]["runs"].values()),
                "cycles_per_custom": r["microtest"]["cycles_per_insn"][c["formula"]],
                "problems": " | ".join(r["problems"]), "build": b["build"]})
        else:
            row["problems"] = b["error"]
        rows.append(row)

    fields = list(dict.fromkeys(list(rows[0]) + [k for r in rows for k in r]))
    with open(args.out + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}.csv ({len(rows)} rows, {len(builds)} builds)")
    if not all(b["ok"] for b in builds.values()):
        sys.exit("some builds failed; see the problems column")


if __name__ == "__main__":
    main()
