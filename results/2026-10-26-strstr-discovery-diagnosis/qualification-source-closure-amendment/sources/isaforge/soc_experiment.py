"""Measure and synthesize CRC32 on a complete synchronous-memory PicoRV32 SoC.

The FPGA top has only clk/resetn inputs and six status/result output pins. All
program/data memory lives in initialized 8 KiB synchronous writable RAM, so
downstream routing times core-to-memory paths without external-RAM assumptions.
Previous core-only artifacts are deliberately preserved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from .core_experiment import CORE_COMMIT, CORE_URL, SUCCESS, crc32_fusion_source, validate_crc32_simulation

HARDWARE = Path(__file__).resolve().parents[1] / "hardware"
RAM_BYTES = 8192
EXPECTED_PORTS = {"clk": "input", "resetn": "input", "trap": "output", "done": "output",
                  "passed": "output", "fault": "output", "report_strobe": "output", "report_bit": "output"}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def memory_image(binary: bytes) -> str:
    if len(binary) > 4096:
        raise ValueError("program image must reserve at least 4 KiB for stack")
    image = binary + bytes(RAM_BYTES - len(binary))
    return "".join(f"{int.from_bytes(image[i:i+4], 'little'):08x}\n" for i in range(0, RAM_BYTES, 4))


def compare_prior_firmware(current: bytes, previous: bytes) -> dict:
    if (len(current) != len(previous) or current[4:] != previous[4:]
            or int.from_bytes(current[:4], "little") != 0x00002137
            or int.from_bytes(previous[:4], "little") != 0x00010137):
        raise ValueError("SoC firmware must differ from prior core firmware only in the initial stack instruction")
    return dict(previous_binary_sha256=hashlib.sha256(previous).hexdigest(),
                current_binary_sha256=hashlib.sha256(current).hexdigest(),
                different_byte_offsets=[i for i, (a, b) in enumerate(zip(current, previous)) if a != b],
                previous_stack_top="0x10000", current_stack_top="0x2000",
                all_other_binary_bytes_identical=True)


def validate_soc_measurement(raw: dict, fusion_mask: int) -> dict:
    if raw.get("fault") != 0 or raw.get("partial_report_bits") != 0:
        raise ValueError("memory bounds fault or incomplete serial result report")
    measured = validate_crc32_simulation(raw, fusion_mask)
    handshakes = measured["protocol_statistics"]["pcpi_handshakes"]
    if raw.get("pcpi_valid_cycles") != handshakes or raw.get("pcpi_wait_cycles") != 0:
        raise ValueError("SoC PCPI combinational response differs from configured latency")
    return measured


def validate_netlist(netlist: dict, *, bram_limit=32, lut_limit=7680) -> dict:
    """Reject accidental external-memory tops and designs exceeding HX8K."""
    top = netlist["modules"]["soc_top"]
    ports = top["ports"]
    if {name: p["direction"] for name, p in ports.items()} != EXPECTED_PORTS:
        raise ValueError("SoC must expose only clock/reset and status/report pins")
    if any(len(p["bits"]) != 1 for p in ports.values()):
        raise ValueError("SoC package ports must all be scalar")
    types = Counter(cell["type"] for name, module in netlist["modules"].items()
                    if not module.get("attributes", {}).get("blackbox")
                    for cell in module.get("cells", {}).values())
    brams, luts = types.get("SB_RAM40_4K", 0), types.get("SB_LUT4", 0)
    if not (16 <= brams <= bram_limit) or luts > lut_limit:
        raise ValueError("synchronous 8 KiB memory did not map into HX8K resource limits")
    ram_cells = {name: cell for name, cell in top.get("cells", {}).items() if cell["type"] == "SB_RAM40_4K"}
    program_ram = {name: cell for name, cell in ram_cells.items() if name.startswith("memory.")}
    if len(program_ram) != 16:
        raise ValueError("the 8 KiB program/data memory must map into exactly 16 BRAM blocks")
    if any(cell["connections"].get(port) != ports["clk"]["bits"]
           for cell in ram_cells.values() for port in ("RCLK", "WCLK")):
        raise ValueError("all on-chip BRAM read/write clocks must use the SoC clock")
    return dict(cell_types=dict(sorted(types.items())), lut4_count=luts,
                carry_count=types.get("SB_CARRY", 0), memory_blocks=brams,
                flip_flop_count=sum(n for typ, n in types.items() if typ.startswith("SB_DFF")),
                top_ports={name: dict(direction=p["direction"], width=len(p["bits"])) for name, p in sorted(ports.items())},
                program_data_memory_blocks=len(program_ram), all_bram_clocks_use_top_clock=True,
                fits_hx8k_resource_counts=True)


def run_experiment(output_dir: Path, core_dir: Path, toolchain_prefix: str) -> dict:
    output, core = output_dir.resolve(), core_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commands = []

    def execute(args, log: Path, *, expected_code=0, timeout=600):
        started = time.monotonic()
        result = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr)
        commands.append(dict(argv=[str(a) for a in args], working_directory=str(Path.cwd()),
                             exit_code=result.returncode, log=str(log.relative_to(output)),
                             elapsed_seconds=time.monotonic() - started))
        write_json(output / "commands.json", commands)
        if result.returncode != expected_code:
            raise RuntimeError(f"command failed; see {log}")
        return result.stdout

    revision = execute(["git", "-C", core, "rev-parse", "HEAD"], output / "core-revision.log").strip()
    if revision != CORE_COMMIT or execute(["git", "-C", core, "status", "--porcelain"], output / "core-status.log").strip():
        raise ValueError("SoC requires the exact clean pinned upstream PicoRV32 source")
    sources = output / "sources"
    sources.mkdir(exist_ok=True)
    for path in HARDWARE.glob("soc_*"):
        if path.is_file():
            shutil.copy2(path, sources / path.name)
    for path in (HARDWARE / "pcpi_candidates.v", HARDWARE / "core_crc_firmware.c", core / "picorv32.v", core / "COPYING"):
        shutil.copy2(path, sources / path.name)
    embench = HARDWARE.parent / "benchmarks/embench"
    benchmark_sources = sources / "embench"
    benchmark_sources.mkdir(exist_ok=True)
    for path in (embench / "support").glob("*.h"):
        shutil.copy2(path, benchmark_sources / path.name)
    shutil.copy2(embench / "support/beebsc.c", benchmark_sources / "beebsc.c")
    original = (embench / "src/crc32/crc_32.c").read_text()
    (benchmark_sources / "crc32-upstream.c").write_text(original)
    (benchmark_sources / "crc32-fused.c").write_text(crc32_fusion_source(original))
    embench_revision = execute(["git", "-C", embench, "rev-parse", "HEAD"], output / "embench-revision.log").strip()
    gcc, objcopy, objdump, nm = (toolchain_prefix + suffix for suffix in ("gcc", "objcopy", "objdump", "nm"))
    tools = {"gcc": execute([gcc, "--version"], output / "gcc-version.log").splitlines()[0],
             "verilator": execute(["verilator", "--version"], output / "verilator-version.log").strip(),
             "yosys": execute(["yosys", "-V"], output / "yosys-version.log").strip()}
    firmware = {}
    for mask, name in ((0, "stock"), (0, "source-control"), (3, "both")):
        folder = output / "firmware" / name
        folder.mkdir(parents=True, exist_ok=True)
        elf, binary = folder / "firmware.elf", folder / "firmware.bin"
        execute([gcc, "-march=rv32i_zicsr", "-mabi=ilp32", "-O2", "-std=gnu17", "-nostdlib", "-nostartfiles",
                 "-ffreestanding", "-fno-builtin", "-ffunction-sections", "-fdata-sections",
                 "-msmall-data-limit=0", "-mno-relax", "-DCPU_MHZ=1", f"-DFUSION_MASK={mask}",
                 "-I", benchmark_sources, "-Wl,--no-relax", "-Wl,--gc-sections", "-Wl,-T," + str(sources / "soc_link.ld"),
                 sources / "soc_start.S", sources / "core_crc_firmware.c",
                 benchmark_sources / ("crc32-upstream.c" if name == "stock" else "crc32-fused.c"),
                 benchmark_sources / "beebsc.c", "-lgcc", "-o", elf], folder / "compile.log")
        execute([objcopy, "-O", "binary", elf, binary], folder / "objcopy.log")
        execute([objdump, "-d", elf], folder / "disassembly.txt")
        symbols = execute([nm, "-n", elf], folder / "symbols.txt")
        end = next(int(line.split()[0], 16) for line in symbols.splitlines() if line.split()[-1] == "_program_end")
        if end > 4096:
            raise ValueError("ELF data/BSS exceeds the bounded program region")
        (folder / "firmware.hex").write_text(memory_image(binary.read_bytes()))
        firmware[name] = dict(directory=folder, program_bytes=len(binary.read_bytes()), program_end=end,
                              binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                              elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                              memory_image_sha256=hashlib.sha256((folder / "firmware.hex").read_bytes()).hexdigest())
    source_control_binary_identical = firmware["stock"]["binary_sha256"] == firmware["source-control"]["binary_sha256"]
    prior_comparisons = {}
    for name in ("stock", "both"):
        previous = HARDWARE.parent / f"generated/core/crc32-{name}.bin"
        if previous.exists():
            prior_comparisons[name] = compare_prior_firmware((firmware[name]["directory"] / "firmware.bin").read_bytes(), previous.read_bytes())

    def model(name, mask, image):
        folder = output / "simulation" / name
        folder.mkdir(parents=True, exist_ok=True)
        # Per-configuration init image is the only generated top-source change.
        top_source = (sources / "soc_top.v").read_text().replace('"firmware.hex"', '"' + str(image) + '"')
        (folder / "soc_top.v").write_text(top_source)
        execute(["verilator", "--cc", "--exe", "--build", "-j", "2", "-Wno-fatal", "--top-module", "soc_top",
                 "--Mdir", folder / "obj_dir", f"-GEXTENSION_MASK={mask}", sources / "picorv32.v",
                 sources / "pcpi_candidates.v", folder / "soc_top.v", sources / "soc_sim.cpp"], folder / "build.log")
        return folder / "obj_dir" / "Vsoc_top"

    measurements = {}
    configs = (("baseline", 0, "stock", 0), ("custom", 3, "both", 3),
               ("source-control", 0, "source-control", 0), ("stock-on-custom", 3, "stock", 0))
    for name, extension, program, fusion in configs:
        executable = model(name, extension, firmware[program]["directory"] / "firmware.hex")
        raw = json.loads(execute([executable], output / "simulation" / name / "simulation.json"))
        measurements[name] = validate_soc_measurement(raw, fusion)
        measurements[name].update(extension_mask=extension, fusion_mask=fusion, firmware=program)
        print(f"SoC {name}: {measurements[name]['cycles']} cycles; full CRC checksum passes", flush=True)
        write_json(output / "measurements.json", measurements)
    for control in ("source-control", "stock-on-custom"):
        for field in ("cycles", "instructions", "full_checksum", "benchmark_result", "protocol_statistics"):
            if measurements[control][field] != measurements["baseline"][field]:
                raise ValueError(f"SoC {control} differs from baseline execution")
    deleted = measurements["baseline"]["instructions"] - measurements["custom"]["instructions"]
    if deleted != 170 * 1024 * 3:
        raise ValueError("SoC actual instruction deletion differs from the two fused patterns")

    # RAM inference integration checks use the same top and response controller.
    memory_checks = []
    for name, expected_code in (("memory_check", 0), ("invalid_memory", 7)):
        folder = output / "firmware" / name
        folder.mkdir(parents=True, exist_ok=True)
        execute([gcc, "-march=rv32i", "-mabi=ilp32", "-nostdlib", "-nostartfiles", "-Wl,-T," + str(sources / "soc_link.ld"),
                 sources / f"soc_{name}.S", "-o", folder / "firmware.elf"], folder / "compile.log")
        execute([objcopy, "-O", "binary", folder / "firmware.elf", folder / "firmware.bin"], folder / "objcopy.log")
        (folder / "firmware.hex").write_text(memory_image((folder / "firmware.bin").read_bytes()))
        executable = model(name, 0, folder / "firmware.hex")
        raw = json.loads(execute([executable], output / "simulation" / name / "simulation.json", expected_code=expected_code))
        if name == "memory_check":
            if raw["status"] != SUCCESS or raw["words"] != [0x00EFDD44] or raw["fault"] or raw["partial_report_bits"]:
                raise ValueError("synchronous RAM byte-mask/sign-extension self-check failed")
        elif not raw["fault"] or raw["status"] == SUCCESS:
            raise ValueError("out-of-range RAM access did not produce a hardware fault")
        memory_checks.append(dict(name=name, passed=True, evidence=raw))
    synthesis = []
    for name, extension, program in (("baseline", 0, "stock"), ("custom", 3, "both"), ("source-control", 0, "source-control")):
        folder = output / "synthesis" / name
        folder.mkdir(parents=True, exist_ok=True)
        # Use the exact same elaborated top source and image as the simulation.
        top = output / "simulation" / name / "soc_top.v"
        script, netlist = folder / "ice40.ys", folder / "ice40-netlist.json"
        quote = lambda p: '"' + str(p).replace('\\', '\\\\').replace('"', '\\"') + '"'
        script.write_text("read_verilog " + " ".join(quote(p) for p in (sources / "picorv32.v", sources / "pcpi_candidates.v", top))
                          + f"\nchparam -set EXTENSION_MASK {extension} soc_top\n"
                          + "synth_ice40 -top soc_top\ncheck -assert\nwrite_json " + quote(netlist) + "\nstat\n")
        execute(["yosys", "-s", script], folder / "ice40.log")
        counts = validate_netlist(json.loads(netlist.read_text()))
        synthesis.append(dict(configuration=name, extension_mask=extension, firmware=program,
                              netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
                              firmware_image_sha256=firmware[program]["memory_image_sha256"], **counts))
        print(f"SoC synthesis {name}: {counts['lut4_count']} LUT4, {counts['memory_blocks']} BRAM", flush=True)
        write_json(output / "synthesis.json", synthesis)
    summary = dict(scope="closed PicoRV32 SoC with initialized synchronous on-chip memory, full source-modified Embench CRC32 benchmark",
                   provenance=dict(upstream_url=CORE_URL, upstream_commit=revision, embench_commit=embench_revision,
                                   tools=tools, source_sha256={str(p.relative_to(sources)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources.rglob("*")) if p.is_file()}),
                   configuration=dict(top="soc_top", ram_bytes=RAM_BYTES, ram_words=2048, ram_word_bits=32,
                                      memory="one synchronous read/request edge followed by native-interface acknowledgement; same RTL in simulation and synthesis",
                                      memory_ports="internal byte-write RAM shared by instructions/data; no external address/data/ready pins",
                                      program_limit_bytes=4096, stack_top="0x2000", minimum_stack_reservation_bytes=4096,
                                      reset_cycles=8, pcpi_response_latency=0, cpu="same RV32I configuration as the core experiment except stack address",
                                      package_pins=8, result_stream="32 LSB-first bits per MMIO word, one bit per clk rising edge while report_strobe=1",
                                      benchmark_repetitions=170, crc_updates_per_repetition=1024,
                                      warmup_repetitions=1, independent_full_checksum_repetitions=1),
                   firmware={name: {k: v for k, v in data.items() if k != "directory"} for name, data in firmware.items()},
                   prior_core_firmware_comparison=prior_comparisons,
                   measurements=measurements, synthesis=synthesis, memory_checks=memory_checks,
                   controls=dict(source_wrapper_binary_identical_to_stock=source_control_binary_identical,
                                 source_wrapper_execution_identical_to_stock=True, stock_on_extended_core_identical=True,
                                 byte_write_and_signed_unsigned_loads_passed=True, out_of_bounds_memory_fault_passed=True),
                   comparisons=dict(baseline_cycles=measurements["baseline"]["cycles"], custom_cycles=measurements["custom"]["cycles"],
                                    cycle_ratio=measurements["baseline"]["cycles"] / measurements["custom"]["cycles"],
                                    deleted_instructions=deleted, lut4_delta=synthesis[1]["lut4_count"] - synthesis[0]["lut4_count"]),
                   limitations=["Full benchmark is a RV32I port with GCC constant multiplication lowered to shifts/adds/subtracts; original RV32IM Spike traces remain separate evidence.",
                                "The source macro lowers two extracted formulas; this is not an automatic patch of the prior ELF.",
                                "RAM is initialized by the FPGA image; reset does not reload RAM. Standalone simulations each instantiate a new initialized design.",
                                "Resource limits establish potential HX8K fit; only actual place-and-route establishes routing feasibility and achieved clock.",
                                "These measurements are architectural cycles. A paired clock analysis is required for wall-time comparison.",
                                "The simple single-bit report protocol is synchronous to clk; reset/status/report boundary pins need declared external timing assumptions in routing."])
    write_json(output / "summary.json", summary)
    return summary


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("generated/soc"))
    parser.add_argument("--core-dir", type=Path, default=Path("../toolchains/picorv32"))
    parser.add_argument("--toolchain-prefix", default="riscv-none-elf-")
    args = parser.parse_args(argv)
    run_experiment(args.output_dir, args.core_dir, args.toolchain_prefix)


if __name__ == "__main__":
    main()
