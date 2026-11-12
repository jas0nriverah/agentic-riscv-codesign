import argparse
import csv
import re

# Reads the post-route clk->clk critical path from nextpnr logs and writes one row per seed.
# Cell and net names in these reports are borrowed by synthesis from nearby signals
# (a LUT named fused.unit.active... can be plain PicoRV32 branch logic), so every
# classification here is structural, done on the Yosys netlist by critcone.py,
# critends.py and critgroups.py, never by name.


def readPath(logPath):
    # the clk->clk report after routing: (kind, cumulative ns, role, name) per line, plus the final Fmax
    lines = open(logPath).read().splitlines()
    start = next(i for i, l in enumerate(lines)
                 if "Critical path report for clock" in l and "posedge -> posedge" in l)
    steps = []
    for line in lines[start + 1:]:
        if line.startswith("Info: Critical path report") or "Max frequency" in line:
            break
        m = re.match(r"Info:\s+(clk-to-q|logic|routing|setup)\s+[\d.]+\s+([\d.]+)\s+(Source|Net)\s+(\S+)", line)
        if m:
            steps.append((m.group(1), float(m.group(2)), m.group(3), m.group(4)))
            continue
        m = re.match(r"Info:\s+Sink\s+(\S+)", line)
        if m:
            steps.append(("sink", None, "Sink", m.group(1)))
    fmax = float(re.search(r"([\d.]+) MHz", [l for l in lines if "Max frequency" in l][-1]).group(1))
    return {"fmax": fmax, "ns": [s[1] for s in steps if s[1] is not None][-1],
            "stages": sum(1 for s in steps if s[0] == "logic"), "steps": steps}


def cellOf(lcPin):
    # nextpnr names a logic cell after the LUT, carry or lone flip-flop (_DFFLC) packed into it; drops the pin
    return re.sub(r"(_DFFLC|_LC|\$CARRY)\.\w+$", "", lcPin)


def arcs(path):
    # each hop along the path: the net it travels on and the cell and pin it enters
    out, net = [], None
    for kind, _, role, name in path["steps"]:
        if role == "Net":
            net = name
        elif role == "Sink":
            out.append((net, cellOf(name), name.rsplit(".", 1)[1]))
    return out


def main():
    # imported here because those modules import readPath from this one
    from critcone import Netlist, unitOnArc
    from critends import ends
    from critgroups import sharedCells

    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True)
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    netlist = Netlist(args.netlist)
    rows = []
    for seed in args.seeds:
        path = readPath(f"{args.routes}/seed{seed}/nextpnr.log")
        start, end, pin = ends(path, netlist)
        onArc, reason = unitOnArc(path, netlist)
        shared = sharedCells(path, netlist)
        rows.append({"core": args.core, "seed": seed, "fmax_mhz": path["fmax"], "path_ns": path["ns"],
                     "logic_stages": path["stages"], "start": start, "end": end, "end_pin": pin,
                     "unit_on_arc": onArc, "unit_on_arc_reason": reason,
                     "shared_with_unit": shared["unit"], "shared_with_pcpi_handshake": shared["handshake"],
                     "shared_with_mul": shared["mul"], "shared_with_div": shared["div"]})
        print(",".join(str(v) for v in rows[-1].values()))

    # appends so both cores land in one table; the make rule starts the file fresh
    with open(args.out, "a", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        if out.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
