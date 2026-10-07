import json
import re
import sys

# matches the instruction that reads the counter
MARKER = re.compile(r"\(0xc0202[0-9a-f][7f]3\)")

# operation names picked by funct3 or by funct7 and funct3
BRANCHES = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}
LOADS = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}
STORES = {0: "sb", 1: "sh", 2: "sw"}
MATH_IMM = {0: "addi", 2: "slti", 3: "sltiu", 4: "xori", 6: "ori", 7: "andi"}
MATH = {(0, 0): "add", (32, 0): "sub", (0, 1): "sll", (0, 2): "slt", (0, 3): "sltu",
        (0, 4): "xor", (0, 5): "srl", (32, 5): "sra", (0, 6): "or", (0, 7): "and",
        (1, 0): "mul", (1, 1): "mulh", (1, 2): "mulhsu", (1, 3): "mulhu",
        (1, 4): "div", (1, 5): "divu", (1, 6): "rem", (1, 7): "remu"}


def bits(word, high, low):
    # pulls out the bits from high down to low
    return (word >> low) & ((1 << (high - low + 1)) - 1)


def signed(value, width):
    # turns the field into a negative number when its top bit is set
    return value - (1 << width) if value >> (width - 1) else value


def decode(word):
    # splits one instruction into op rd rs1 rs2 imm
    opcode = bits(word, 6, 0)
    rd = bits(word, 11, 7)
    funct3 = bits(word, 14, 12)
    rs1 = bits(word, 19, 15)
    rs2 = bits(word, 24, 20)
    funct7 = bits(word, 31, 25)
    # immediate used by most instruction families
    imm12 = signed(bits(word, 31, 20), 12)

    # math between two registers
    if opcode == 0b0110011:
        return MATH.get((funct7, funct3), "unknown"), rd, rs1, rs2, None
    # math between a register and an immediate
    if opcode == 0b0010011:
        # shift left by an immediate
        if funct3 == 1:
            return "slli", rd, rs1, None, rs2
        # shift right by an immediate
        if funct3 == 5:
            return ("srai" if funct7 == 32 else "srli"), rd, rs1, None, rs2
        return MATH_IMM[funct3], rd, rs1, None, imm12
    # reads a value from memory
    if opcode == 0b0000011:
        return LOADS.get(funct3, "unknown"), rd, rs1, None, imm12
    # writes a value to memory
    if opcode == 0b0100011:
        return STORES.get(funct3, "unknown"), None, rs1, rs2, signed((funct7 << 5) | rd, 12)
    # jumps if the comparison of two registers is true
    if opcode == 0b1100011:
        imm = (bits(word, 31, 31) << 12) | (bits(word, 7, 7) << 11) | (bits(word, 30, 25) << 5) | (bits(word, 11, 8) << 1)
        return BRANCHES.get(funct3, "unknown"), None, rs1, rs2, signed(imm, 13)
    # jumps to a nearby address
    if opcode == 0b1101111:
        imm = (bits(word, 31, 31) << 20) | (bits(word, 19, 12) << 12) | (bits(word, 20, 20) << 11) | (bits(word, 30, 21) << 1)
        return "jal", rd, None, None, signed(imm, 21)
    # jumps to the address held in a register
    if opcode == 0b1100111:
        return "jalr", rd, rs1, None, imm12
    # load upper immediate
    if opcode == 0b0110111:
        return "lui", rd, None, None, signed(word & 0xFFFFF000, 32)
    # add upper immediate to the current address
    if opcode == 0b0010111:
        return "auipc", rd, None, None, signed(word & 0xFFFFF000, 32)
    return "unknown", None, None, None, None


def main():
    # opens the trace file named on the command line
    out = open(sys.argv[1], "w")
    readings = []
    linesBetween = 0
    unknown = 0

    # reads the Spike log one line at a time
    for seq, line in enumerate(sys.stdin):
        if MARKER.search(line):
            # saves the counter value
            readings.append(int(line.split()[-1], 16))
        elif len(readings) == 1:
            # writes one record for this instruction
            parts = line.split()
            # raw bits of the instruction as a number
            word = int(parts[4].strip("()"), 16)
            op, rd, rs1, rs2, imm = decode(word)
            record = {"pc": parts[3], "raw": f"0x{word:08x}", "op": op,
                      "rd": rd, "rs1": rs1, "rs2": rs2, "imm": imm, "seq": seq}
            out.write(json.dumps(record) + "\n")
            linesBetween += 1
            # counts instructions the decoder did not recognize
            unknown += op == "unknown"

    out.close()

    # compares the counter with the log
    counter = readings[1] - readings[0]

    # stops with an error when the checks fail
    if counter != linesBetween + 1 or unknown != 0:
        sys.exit("MISMATCH")


# runs main only when this file is run directly
if __name__ == "__main__":
    main()
