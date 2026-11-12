import argparse
import re

from critcone import Netlist
from critpath import readPath

# Yosys may keep only the mul/div input-port name for PicoRV32's operand registers;
# picorv32.v drives pcpi_rs1/pcpi_rs2 from reg_op1/reg_op2 (lines 191-192)
OPERAND_PORT = re.compile(r"cpu\.genblk\d+(\.genblk\d+)?\.pcpi_(mul|div)\.pcpi_rs([12])")


def registerName(netlist, cell):
    # the register's most readable name and bit: plain names before ones synthesis made up
    if cell is None:
        return "?"
    bit = netlist.q(cell)
    names = sorted(netlist.aliases.get(bit, [cell]), key=lambda n: ("_SB_" in n, n.count("."), len(n)))
    name = names[0]
    shown = OPERAND_PORT.sub(lambda m: f"cpu.reg_op{m.group(3)}", name)
    bits = netlist.names.get(name, {}).get("bits", [])
    return f"{shown}[{bits.index(bit)}]" if len(bits) > 1 else shown


def ends(path, netlist):
    # the registers the critical path launches from and is captured by, and the capture pin
    sink = [s for s in path["steps"] if s[2] == "Sink"][-1][3]
    start = netlist.registerAt(path["steps"][0][3])
    end = netlist.registerAt(sink)
    return registerName(netlist, start), registerName(netlist, end), sink.rsplit(".", 1)[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    args = parser.parse_args()
    netlist = Netlist(args.netlist)
    for seed in args.seeds:
        path = readPath(f"{args.routes}/seed{seed}/nextpnr.log")
        start, end, pin = ends(path, netlist)
        print(f"seed {seed}: {path['fmax']} MHz, {path['ns']} ns, {path['stages']} logic stages, "
              f"{start} -> {end} ({pin})")


if __name__ == "__main__":
    main()
