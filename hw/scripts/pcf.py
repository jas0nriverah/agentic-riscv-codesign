import json
import re
import sys

# turns one placed nextpnr design into a PCF that pins every top-level port where it landed
# follows placement_pins in the ML branch's isaforge/core_routing.py


def readPins(chipdbPath, package):
    # maps each I/O location in IceStorm's chip database to its package pin name
    pins = {}
    section = ""
    for raw in open(chipdbPath):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("."):
            section = line
        elif section == f".pins {package}":
            pin, x, y, z = line.split()
            pins[(int(x), int(y), int(z))] = pin
    if not pins:
        sys.exit(f"package {package} is missing from {chipdbPath}")
    return pins


def main():
    placedPath, chipdbPath, package, outPath = sys.argv[1:5]
    pins = readPins(chipdbPath, package)
    module = next(iter(json.load(open(placedPath))["modules"].values()))

    # names each net that leaves the chip after the port bit it carries
    ports = {}
    for name, port in module["ports"].items():
        for i, bit in enumerate(port["bits"]):
            ports[bit] = name if len(port["bits"]) == 1 else f"{name}[{i + port.get('offset', 0)}]"

    # every SB_IO cell sits on one package pin
    mapping = {}
    for cell in module["cells"].values():
        if cell["type"] not in ("SB_IO", "SB_GB_IO"):
            continue
        port = ports[cell["connections"]["PACKAGE_PIN"][0]]
        location = re.fullmatch(r"X(\d+)/Y(\d+)/io(\d+)", cell["attributes"]["NEXTPNR_BEL"])
        mapping[port] = pins[tuple(map(int, location.groups()))]

    # stops when a port is missing or two ports share a pin
    if set(mapping) != set(ports.values()) or len(set(mapping.values())) != len(mapping):
        sys.exit("placement does not give every port its own pin")

    with open(outPath, "w") as out:
        for port, pin in sorted(mapping.items()):
            out.write(f"set_io {port} {pin}\n")


if __name__ == "__main__":
    main()
