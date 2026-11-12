import os
import re
import subprocess
import sys

# main's decoder, so every .s line is seen exactly as the candidate finder saw the machine code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from tracing import decode  # noqa: E402

# instructions that can change which instruction runs next, as in src/candidates.py
JUMPS = {"beq", "bne", "blt", "bge", "bltu", "bgeu", "jal", "jalr"}
ABI = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1"] + [f"a{i}" for i in range(8)] + \
      [f"s{i}" for i in range(2, 12)] + [f"t{i}" for i in range(3, 7)]
LISTED = re.compile(r"^\s*(\d+)\s+([0-9a-f]{4})\s+([0-9A-F]+)\s")
CONTINUED = re.compile(r"^\s*(\d+)\s{6}([0-9A-F]+)\s*$")


class Line:
    # one line of the .s file: its text, and if it is an instruction, the machine words it became
    def __init__(self, number, text):
        self.number, self.text = number, text
        self.section, self.offset, self.words = None, None, []
        self.relocated = False

    @property
    def stripped(self):
        return self.text.split("#")[0].strip()

    @property
    def isLabel(self):
        return bool(re.fullmatch(r"[\w.$]+:", self.stripped))

    @property
    def isInstruction(self):
        return bool(self.words) and not self.stripped.startswith(".")

    @property
    def ops(self):
        # (op, rd, rs1, rs2, imm) per machine word, from main's decoder
        return [effects(w) for w in self.words]

    @property
    def endsBlock(self):
        return any(op[0] in JUMPS for op in self.ops)

    def reads(self):
        # registers read before the line writes them, over all its words
        seen, written = set(), set()
        for op, rd, rs1, rs2, imm in self.ops:
            for r in (rs1, rs2):
                if r and r not in written:
                    seen.add(r)
            if rd:
                written.add(rd)
        return seen

    def writes(self):
        return {rd for op, rd, rs1, rs2, imm in self.ops if rd}


def effects(word):
    # decode() leaves system instructions unknown; csrr and friends still write rd, which liveness needs
    op = decode(word)
    if op[0] != "unknown":
        return op
    opcode = word & 0x7F
    if opcode == 0x73:
        funct3 = (word >> 12) & 7
        rd = (word >> 7) & 31 if funct3 else None
        rs1 = (word >> 15) & 31 if funct3 in (1, 2, 3) else None
        return "system", rd, rs1, None, None
    if opcode == 0x0F:
        return "fence", None, None, None, None
    if opcode == 0x0B:
        return "custom0", (word >> 7) & 31, (word >> 15) & 31, (word >> 20) & 31, None
    raise ValueError(f"cannot decode {word:#010x}")


def scan(sPath, workDir, prefix, flags):
    # assembles the .s with a listing and reads which words and relocations each line produced
    base = os.path.join(workDir, os.path.basename(sPath))
    listing, obj = base + ".lst", base + ".o"
    subprocess.run([prefix + "gcc", *flags, "-c", sPath, "-o", obj, f"-Wa,-aln={listing}"], check=True)
    lines = [Line(i + 1, t) for i, t in enumerate(open(sPath).read().split("\n"))]

    current = None
    for line in lines:
        # tracks the section so listing offsets can be matched with relocation offsets
        s = line.stripped
        m = re.match(r"\.section\s+([\w.]+)", s)
        if s in (".text", ".data", ".bss"):
            current = s
        elif m:
            current = m.group(1)
        line.section = current

    for row in open(listing):
        m = LISTED.match(row)
        if m:
            line = lines[int(m.group(1)) - 1]
            line.offset = int(m.group(2), 16)
            line.words += words(m.group(3))
            continue
        m = CONTINUED.match(row)
        if m:
            lines[int(m.group(1)) - 1].words += words(m.group(2))

    relocs = {}
    text = subprocess.run([prefix + "objdump", "-r", obj], capture_output=True, text=True, check=True).stdout
    section = None
    for row in text.splitlines():
        m = re.match(r"RELOCATION RECORDS FOR \[(.+)\]:", row)
        if m:
            section = m.group(1)
            continue
        m = re.match(r"([0-9a-f]{8}) (R_RISCV_\w+)", row)
        if m:
            relocs.setdefault(section, set()).add(int(m.group(1), 16))
    for line in lines:
        if line.isInstruction:
            span = range(line.offset, line.offset + 4 * len(line.words))
            line.relocated = any(o in span for o in relocs.get(line.section, ()))
    return lines


def words(hexBytes):
    # the listing prints bytes in memory order; RISC-V is little-endian
    out = []
    for i in range(0, len(hexBytes) - 7, 8):
        chunk = bytes.fromhex(hexBytes[i:i + 8])
        out.append(int.from_bytes(chunk, "little"))
    return out


def blocks(lines):
    # straight runs of instruction lines that end at a label or a jump, like the finder's blocks
    current = []
    for line in lines:
        if line.isLabel:
            if current:
                yield current
            current = []
        elif line.isInstruction:
            current.append(line)
            if line.endsBlock:
                yield current
                current = []
    if current:
        yield current


def functionOf(lines):
    # the function each line belongs to: the nearest preceding label that is not a .L label
    name, out = None, {}
    for line in lines:
        if line.isLabel and not line.stripped.startswith(".L"):
            name = line.stripped[:-1]
        out[line.number] = name
    return out
