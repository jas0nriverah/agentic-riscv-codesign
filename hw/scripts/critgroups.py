import argparse
import re

from critcone import UNIT_REGISTER, Netlist
from critpath import arcs, readPath

# register groups whose next-state logic a critical path may share cells with; the mul/div
# patterns skip their input ports, which are only aliases of the core's own registers
PORT = r"(?!pcpi_(valid|insn|rs1|rs2)$)"
GROUPS = {
    "unit": UNIT_REGISTER,
    "handshake": re.compile(r"cpu\.pcpi_(valid|timeout|timeout_counter)"),
    "mul": re.compile(r"cpu\.genblk\d+\.genblk\d+\.pcpi_mul\." + PORT + r"\w+"),
    "div": re.compile(r"cpu\.genblk\d+\.pcpi_div\." + PORT + r"\w+"),
}


def groupCones(netlist):
    # the logic computing each group's next state, computed once per netlist
    if not hasattr(netlist, "groupCones"):
        netlist.groupCones = {}
        for group, pattern in GROUPS.items():
            registers = {c for c in netlist.cells if netlist.isRegister(c) and
                         any(pattern.fullmatch(a) for a in netlist.aliases.get(netlist.q(c), []))}
            netlist.groupCones[group] = netlist.coneBack(registers)
    return netlist.groupCones


def sharedCells(path, netlist):
    # how many cells on the path also compute the next state of each group (shared, not exclusive, logic)
    cells = list(dict.fromkeys(c for _, c, _ in arcs(path)))
    return {group: sum(c in cone for c in cells) for group, cone in groupCones(netlist).items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    args = parser.parse_args()
    netlist = Netlist(args.netlist)
    for seed in args.seeds:
        path = readPath(f"{args.routes}/seed{seed}/nextpnr.log")
        print(f"seed {seed}: cells shared with next-state logic of {sharedCells(path, netlist)}")


if __name__ == "__main__":
    main()
