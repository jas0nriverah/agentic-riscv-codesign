import argparse
import json
import re

from critpath import arcs, cellOf, readPath

# The structural test behind the clock-period rule in hw/README.md: is the fused unit's
# logic on the critical arc? A unit register is a flip-flop holding the unit's state
# (fused...active or engine...active, and the result register, which drives the core's pcpi_rd port).
UNIT_REGISTER = re.compile(r"(fused|engine)(\.\w+)*\.(active|result)|(cpu\.)?pcpi_rd")


class Netlist:
    # the synthesized core_top: who drives and who reads every bit, and every name of every bit
    def __init__(self, path):
        module = json.load(open(path))["modules"]["core_top"]
        self.cells, self.names = module["cells"], module["netnames"]
        self.aliases, self.driver, self.readers, self.dOf = {}, {}, {}, {}
        for name, net in self.names.items():
            for bit in net["bits"]:
                self.aliases.setdefault(bit, []).append(name)
        for name, cell in self.cells.items():
            for pin, direction in cell["port_directions"].items():
                for bit in cell["connections"][pin]:
                    if not isinstance(bit, int):
                        continue
                    if direction == "output":
                        self.driver[bit] = name
                    else:
                        self.readers.setdefault(bit, []).append(name)
            if self.isRegister(name):
                self.dOf[cell["connections"]["D"][0]] = name
        self.unit = {c for c in self.cells if self.isRegister(c) and
                     any(UNIT_REGISTER.fullmatch(a) for a in self.aliases.get(self.q(c), []))}
        self.back = self.coneBack(self.unit)
        self.forward = self.coneForward(self.unit)
        self.backNets = {b for c in self.back for b in self.outputs(c)}

    def isRegister(self, cell):
        return self.cells[cell]["type"].startswith("SB_DFF")

    def q(self, cell):
        return self.cells[cell]["connections"]["Q"][0]

    def inputs(self, cell):
        c = self.cells[cell]
        return [b for p, d in c["port_directions"].items() if d == "input"
                for b in c["connections"][p] if isinstance(b, int)]

    def outputs(self, cell):
        c = self.cells[cell]
        return [b for p, d in c["port_directions"].items() if d == "output"
                for b in c["connections"][p] if isinstance(b, int)]

    def coneBack(self, registers):
        # combinational logic computing the next state of these registers
        cone, todo = set(), [b for r in registers for b in self.inputs(r)]
        while todo:
            cell = self.driver.get(todo.pop())
            if cell is None or self.isRegister(cell) or cell in cone:
                continue
            cone.add(cell)
            todo.extend(self.inputs(cell))
        return cone

    def coneForward(self, registers):
        # combinational logic whose output depends on these registers
        cone, todo = set(), [self.q(r) for r in registers]
        while todo:
            for cell in self.readers.get(todo.pop(), []):
                if self.isRegister(cell) or cell in cone:
                    continue
                cone.add(cell)
                todo.extend(self.outputs(cell))
        return cone

    def registerAt(self, lc):
        # the flip-flop packed into a logic cell named after either the flip-flop or the LUT feeding its D
        cell = cellOf(lc)
        if cell not in self.cells:
            return None
        if self.isRegister(cell):
            return cell
        out = self.outputs(cell)
        return self.dOf.get(out[0]) if out else None

    def bit(self, net, cell, pin):
        # the netlist bit a reported net is; falls back to the cell's pin for names nextpnr made up
        m = re.fullmatch(r"(.+)\[(\d+)\]", net or "")
        name, index = (m.group(1), int(m.group(2))) if m else (net, 0)
        if name in self.names and index < len(self.names[name]["bits"]):
            return self.names[name]["bits"][index]
        connection = self.cells.get(cell, {}).get("connections", {}).get(pin)
        return connection[0] if connection else None


def unitOnArc(path, netlist):
    # (a) the arc starts or (b) ends at a unit register, or (c) it enters a cell that depends on the
    # unit's state through a net that is unit logic (it feeds a unit register); returns (bool, reason)
    if not netlist.unit:
        return False, "no unit in this core"
    start = netlist.registerAt(path["steps"][0][3])
    end = netlist.registerAt([s for s in path["steps"] if s[2] == "Sink"][-1][3])
    if start in netlist.unit:
        return True, f"starts at unit register {start}"
    if end in netlist.unit:
        return True, f"ends at unit register {end}"
    for net, cell, pin in arcs(path):
        if cell in netlist.forward and netlist.bit(net, cell, pin) in netlist.backNets:
            return True, f"enters {cell}.{pin} on unit logic {net}"
    return False, "unit logic not on the arc"


def selfTest(netlist):
    # synthetic paths built from nextpnr's real naming that must count as on the arc, so a
    # naming change cannot quietly turn the check into "never on the arc"; returns the failures
    if not netlist.unit:
        return ["no unit registers found (run it on a fused netlist)"]
    register = sorted(netlist.unit)[0]
    cases = {"starts at a unit register": [("clk-to-q", 0.5, "Source", register + "_DFFLC.O"),
                                           ("sink", None, "Sink", "core_DFFLC.D")]}
    # nextpnr names the capturing cell after the LUT feeding D, or after the flip-flop when D
    # comes straight from another register (e.g. a result bit that is just rs1[i])
    for unit in sorted(netlist.unit):
        feeding = netlist.driver.get(netlist.cells[unit]["connections"]["D"][0])
        kind = "LUT" if feeding and not netlist.isRegister(feeding) else "lone flip-flop"
        name = f"ends at a unit register ({kind})"
        if name not in cases:
            sink = feeding + "_LC.I0" if kind == "LUT" else unit + "_DFFLC.D"
            cases[name] = [("clk-to-q", 0.5, "Source", "core_DFFLC.O"), ("sink", None, "Sink", sink)]
    entry = next(((cell, pin, bit) for cell in sorted(netlist.forward) for pin in ("I0", "I1", "I2", "I3")
                  for bit in netlist.cells[cell]["connections"].get(pin, [])[:1] if bit in netlist.backNets), None)
    if entry:
        cell, pin, bit = entry
        name = min(netlist.aliases[bit], key=len)
        bits = netlist.names[name]["bits"]
        net = f"{name}[{bits.index(bit)}]" if len(bits) > 1 else name
        cases["enters unit-dependent logic on unit logic"] = [
            ("clk-to-q", 0.5, "Source", "core_DFFLC.O"), ("routing", 1.0, "Net", net),
            ("sink", None, "Sink", f"{cell}_LC.{pin}")]
    return [name for name, steps in cases.items() if not unitOnArc({"steps": steps}, netlist)[0]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--routes")
    parser.add_argument("--seeds", nargs="+")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    netlist = Netlist(args.netlist)
    if args.selftest:
        failures = selfTest(netlist)
        if failures:
            raise SystemExit("on-arc self-test failed: " + ", ".join(failures))
        print(f"on-arc self-test passed ({len(netlist.unit)} unit registers)")
        return
    print(f"unit registers {len(netlist.unit)}, logic feeding them {len(netlist.back)} cells, "
          f"logic reading them {len(netlist.forward)} cells")
    for seed in args.seeds:
        path = readPath(f"{args.routes}/seed{seed}/nextpnr.log")
        cells = list(dict.fromkeys(c for _, c, _ in arcs(path)))
        onArc, reason = unitOnArc(path, netlist)
        print(f"seed {seed}: on arc {onArc} ({reason}); path cells feeding unit registers: "
              f"{[c for c in cells if c in netlist.back] or 'none'}; path cells reading unit registers: "
              f"{[c for c in cells if c in netlist.forward] or 'none'}")


if __name__ == "__main__":
    main()
