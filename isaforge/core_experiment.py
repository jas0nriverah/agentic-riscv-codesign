"""Actual pinned PicoRV32/PCPI cycle and whole-core resource experiment.

This is a formula recurrence microbenchmark, not an integrated Embench speedup.
The saved firmware, disassembly, commands, logs, and netlists make that scope
auditable. No clock frequency or wall-time performance is inferred from cycles.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import time

from .features import candidate_id

CORE_URL = "https://github.com/YosysHQ/picorv32.git"
CORE_COMMIT = "ef203c2b0a3fb793280f5114941416c425c5b461"
FORMULAS = ("slli(andi(xor(in0,in1),255),2)", "xor(in0,srli(in1,8))")
LENGTHS = (0, 1, 8, 64, 256, 1024)
SUCCESS = 0x600D600D
MASK32 = (1 << 32) - 1
HARDWARE = Path(__file__).resolve().parents[1] / "hardware"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def oracle(formula_index: int, a: int, b: int, n: int = 1) -> int:
    if formula_index not in (0, 1) or n < 0:
        raise ValueError("invalid formula index or iteration count")
    a, b = a & MASK32, b & MASK32
    for _ in range(n):
        a = ((a ^ b) & 255) << 2 if formula_index == 0 else a ^ (b >> 8)
        b = (b + 0x9E3779B9) & MASK32
    return a


def make_vectors(seed: int) -> list[tuple[int, int]]:
    boundaries = (0, 1, 255, 0x7FFFFFFF, 0x80000000, MASK32)
    vectors = [(a, b) for a in boundaries for b in boundaries]
    rng = random.Random(seed)
    vectors.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(128))
    return vectors


def validate_simulation(raw: dict, vectors: list[tuple[int, int]], *, custom: bool,
                        latency: int) -> list[dict]:
    """Reject missing, reordered, incorrect, or protocol-inconsistent evidence."""
    if raw.get("status") != SUCCESS:
        raise ValueError("firmware did not report self-check success")
    words = raw.get("words", [])
    expected_records = 2 * (len(vectors) + 3 * len(LENGTHS))
    if len(words) != expected_records * 8:
        raise ValueError("missing or extra firmware records")
    expected = []
    for f in range(2):
        expected.extend((0, f, 1, a, b) for a, b in vectors)
        for s in range(3):
            a, b = vectors[-1-s]
            expected.extend((1, f, n, a, b) for n in LENGTHS)
    records = []
    for offset, exp in enumerate(expected):
        record = words[offset * 8:(offset + 1) * 8]
        if tuple(record[:5]) != exp:
            raise ValueError("firmware vector or record ordering differs")
        kind, f, n, a, b, result, cycles, instret = record
        if result != oracle(f, a, b, n):
            raise ValueError("processor result differs from independent host oracle")
        if kind == 1 and (cycles <= 0 or instret <= 0):
            raise ValueError("invalid architectural counters")
        records.append(dict(kind="timed" if kind else "direct_self_check",
                            formula_index=f, iterations=n, input_a=a, input_b=b,
                            result=result, cycles=cycles, instructions=instret))
    handshakes = 2 * len(vectors) + 6 * sum(LENGTHS) if custom else 0
    if raw.get("pcpi_handshakes") != handshakes:
        raise ValueError("PCPI handshake count differs from actual custom instruction count")
    if custom:
        if raw.get("pcpi_valid_cycles") != handshakes * (latency + 1):
            raise ValueError("PCPI valid-to-ready latency differs from configuration")
        if raw.get("pcpi_wait_cycles") != handshakes * latency:
            raise ValueError("PCPI wait protocol differs from configuration")
    return records


def compare_runs(baseline: list[dict], custom: list[dict]) -> list[dict]:
    """Keep identical input/length/counter windows and real instruction deletion."""
    if len(baseline) != len(custom):
        raise ValueError("run lengths differ")
    comparisons = []
    for base, extended in zip(baseline, custom):
        for field in ("kind", "formula_index", "iterations", "input_a", "input_b", "result"):
            if base[field] != extended[field]:
                raise ValueError("baseline/custom workloads differ")
        if base["kind"] != "timed":
            continue
        n, f = base["iterations"], base["formula_index"]
        expected_deleted = (2 if f == 0 else 1) * n
        deleted = base["instructions"] - extended["instructions"]
        if deleted != expected_deleted:
            raise ValueError("retired instruction delta does not match actual replacement")
        if n == 0 and base["cycles"] != extended["cycles"]:
            raise ValueError("zero-work cycle overhead differs between configurations")
        comparisons.append(dict(formula_index=f, formula=FORMULAS[f], iterations=n,
                                input_a=base["input_a"], input_b=base["input_b"],
                                result=base["result"], baseline_cycles=base["cycles"],
                                custom_cycles=extended["cycles"],
                                baseline_instructions=base["instructions"],
                                custom_instructions=extended["instructions"],
                                deleted_instructions=deleted,
                                cycle_ratio=base["cycles"] / extended["cycles"],
                                cycles_saved=base["cycles"] - extended["cycles"]))
    return comparisons


def crc32_oracle() -> int:
    """Bitwise CRC oracle, independent of Embench's 256-entry table."""
    seed, crc = 0, MASK32
    for _ in range(1024):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        crc ^= (seed >> 16) & 255
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return (~crc) & MASK32


def crc32_fusion_source(original: str) -> str:
    """Override exactly the update macro; retain licensed upstream source."""
    macro = "#define UPDC32(octet,crc) (crc_32_tab[((crc)^((BYTE)octet)) & 0xff] ^ ((crc) >> 8))"
    if original.count(macro) != 1:
        raise ValueError("upstream CRC update macro differs")
    replacement = r'''
// ISAForge source-level lowering of two extracted formulas; no binary NOP patch.
static inline DWORD isaforge_update(DWORD octet, DWORD crc, const DWORD *table) {
    DWORD offset, entry, result;
#if FUSION_MASK & 1
    __asm__ volatile (".insn r 0x0b, 0, 1, %0, %1, %2"
                      : "=r"(offset) : "r"(crc), "r"(octet));
    entry = *(const DWORD *)((const char *)table + offset);
#else
    entry = table[(crc ^ (BYTE)octet) & 255u];
#endif
#if FUSION_MASK & 2
    __asm__ volatile (".insn r 0x0b, 1, 1, %0, %1, %2"
                      : "=r"(result) : "r"(entry), "r"(crc));
#else
    result = entry ^ (crc >> 8);
#endif
    return result;
}
#define UPDC32(octet,crc) isaforge_update((octet),(crc),crc_32_tab)
'''
    return original.replace(macro, replacement)


def validate_crc32_simulation(raw: dict, fusion_mask: int) -> dict:
    words = raw.get("words", [])
    if (raw.get("status") != SUCCESS or len(words) != 5
            or words[0] != crc32_oracle() or words[1] != 11433 or words[4] != 1):
        raise ValueError("full CRC32 checksum or upstream self-check failed")
    if words[2] <= 0 or words[3] <= 0:
        raise ValueError("CRC32 counters invalid")
    expected_handshakes = fusion_mask.bit_count() * (170 + 2) * 1024
    if raw.get("pcpi_handshakes") != expected_handshakes:
        raise ValueError("CRC32 custom instruction count differs from update count")
    return dict(full_checksum=words[0], benchmark_result=words[1],
                cycles=words[2], instructions=words[3], self_check_passed=True,
                protocol_statistics={k: v for k, v in raw.items() if k != "words"})


def run_experiment(output_dir: Path, core_dir: Path, toolchain_prefix: str,
                   latencies=(0, 1, 4, 16, 24), seed=20261013, synthesize=True,
                   crc32=True) -> dict:
    output, core = output_dir.resolve(), core_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commands = []

    def execute(args, log: Path, timeout=300, expected_code=0):
        started = time.monotonic()
        process = subprocess.run([str(a) for a in args], capture_output=True,
                                 text=True, timeout=timeout)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(process.stdout + process.stderr)
        commands.append(dict(argv=[str(a) for a in args], exit_code=process.returncode,
                             log=str(log.relative_to(output)),
                             elapsed_seconds=time.monotonic() - started))
        write_json(output / "commands.json", commands)
        if process.returncode != expected_code:
            raise RuntimeError(f"command failed; see {log}")
        return process.stdout

    if not core.exists():
        execute(["git", "clone", CORE_URL, core], output / "clone.log")
        execute(["git", "-C", core, "checkout", CORE_COMMIT], output / "checkout.log")
    revision = execute(["git", "-C", core, "rev-parse", "HEAD"], output / "revision.log").strip()
    if revision != CORE_COMMIT:
        raise ValueError(f"core checkout must be pinned to {CORE_COMMIT}")
    if execute(["git", "-C", core, "status", "--porcelain"], output / "core-status.log").strip():
        raise ValueError("upstream core checkout must be clean")
    # Preserve the exact licensed input and harness alongside all measurement logs.
    sources = output / "sources"
    sources.mkdir(exist_ok=True)
    for path in HARDWARE.glob("core_*"):
        if path.is_file():
            shutil.copy2(path, sources / path.name)
    shutil.copy2(HARDWARE / "pcpi_candidates.v", sources / "pcpi_candidates.v")
    shutil.copy2(core / "picorv32.v", sources / "picorv32.v")
    shutil.copy2(core / "COPYING", sources / "PicoRV32-COPYING")
    vectors = make_vectors(seed)
    (sources / "vectors.h").write_text(
        f"#define VECTOR_COUNT {len(vectors)}\nstatic const uint32_t vectors[][2] = {{\n"
        + "".join(f"{{0x{a:08x}u,0x{b:08x}u}},\n" for a, b in vectors) + "};\n")
    gcc, objcopy, objdump = (toolchain_prefix + suffix for suffix in ("gcc", "objcopy", "objdump"))
    tool_versions = {"gcc": execute([gcc, "--version"], output / "gcc-version.log").splitlines()[0],
                     "verilator": execute(["verilator", "--version"], output / "verilator-version.log").strip(),
                     "yosys": execute(["yosys", "-V"], output / "yosys-version.log").strip()}
    for name, custom in (("baseline", False), ("custom", True)):
        elf = output / f"{name}.elf"
        execute([gcc, "-march=rv32i_zicsr", "-mabi=ilp32", "-O2", "-nostdlib", "-nostartfiles",
                 "-ffreestanding", "-fno-builtin", "-msmall-data-limit=0", "-mno-relax",
                 f"-DCUSTOM={int(custom)}", "-I", sources, "-Wl,--no-relax", "-Wl,-T," + str(sources / "core_link.ld"),
                 sources / "core_start.S", sources / "core_firmware.c", "-o", elf], output / f"{name}-compile.log")
        execute([objcopy, "-O", "binary", elf, output / f"{name}.bin"], output / f"{name}-objcopy.log")
        execute([objdump, "-d", elf], output / f"{name}-disassembly.txt")
    illegal_images = []
    for name, instruction in (("wrong-funct7", "0x0400000b"), ("wrong-funct3", "0x0200700b"),
                               ("wrong-opcode", "0x0200002b")):
        elf = output / f"illegal-{name}.elf"
        binary = output / f"illegal-{name}.bin"
        execute([gcc, "-march=rv32i", "-mabi=ilp32", "-nostdlib", "-nostartfiles",
                 "-DINVALID_INSN=" + instruction, "-Wl,-T," + str(sources / "core_link.ld"),
                 sources / "core_illegal.S", "-o", elf], output / f"illegal-{name}-compile.log")
        execute([objcopy, "-O", "binary", elf, binary], output / f"illegal-{name}-objcopy.log")
        illegal_images.append((name, binary))

    def build_model(name: str, mask: int, latency: int) -> Path:
        folder = output / name
        folder.mkdir(exist_ok=True)
        execute(["verilator", "--cc", "--exe", "--build", "-j", "2", "-Wno-fatal",
                 "--top-module", "core_top", "--Mdir", folder / "obj_dir",
                 f"-GEXTENSION_MASK={mask}", f"-GPCPI_LATENCY={latency}",
                 sources / "picorv32.v", sources / "pcpi_candidates.v", sources / "core_top.v",
                 sources / "core_sim.cpp"], folder / "build.log")
        return folder / "obj_dir" / "Vcore_top"

    baseline_model = build_model("baseline-core", 0, 1)
    baseline_raw = json.loads(execute([baseline_model, output / "baseline.bin"], output / "baseline-sim.json"))
    baseline_records = validate_simulation(baseline_raw, vectors, custom=False, latency=1)
    write_json(output / "baseline-records.json", baseline_records)
    # Negative control proves custom instructions are genuinely unsupported on baseline.
    execute([baseline_model, output / "custom.bin"], output / "baseline-custom-illegal.log", expected_code=6)
    measurements = []
    models = {}
    for latency in latencies:
        model = build_model(f"custom-latency-{latency}", 3, latency)
        models[latency] = model
        raw = json.loads(execute([model, output / "custom.bin"], output / f"custom-latency-{latency}" / "sim.json"))
        records = validate_simulation(raw, vectors, custom=True, latency=latency)
        write_json(output / f"custom-latency-{latency}" / "records.json", records)
        comparisons = compare_runs(baseline_records, records)
        # Same baseline firmware on the extended core checks a stable execution setting.
        control = json.loads(execute([model, output / "baseline.bin"], output / f"custom-latency-{latency}" / "baseline-control.json"))
        control_records = validate_simulation(control, vectors, custom=False, latency=latency)
        if control_records != baseline_records:
            raise ValueError("extension altered execution of baseline firmware")
        for name, binary in illegal_images:
            execute([model, binary], output / f"custom-latency-{latency}" / f"illegal-{name}.log", expected_code=6)
        measurements.append(dict(pcpi_response_latency=latency, protocol_statistics={k: v for k, v in raw.items() if k != "words"},
                                 baseline_on_extended_core_matches=True, comparisons=comparisons))
        print(f"PicoRV32 latency {latency}: all self-checks, host oracles, counters and controls passed", flush=True)
        write_json(output / "measurements.json", measurements)
    synthesis = []
    if synthesize:
        for mask, name, latency in ((0, "baseline", 1), (1, "formula0", 1), (2, "formula1", 1),
                                    (3, "both", 1), (3, "both-combinational", 0)):
            folder = output / "synthesis" / name
            folder.mkdir(parents=True, exist_ok=True)
            netlist = folder / "ice40-netlist.json"
            script = folder / "ice40.ys"
            quote = lambda p: '"' + str(p).replace('\\', '\\\\').replace('"', '\\"') + '"'
            script.write_text("read_verilog " + " ".join(quote(sources / p) for p in ("picorv32.v", "pcpi_candidates.v", "core_top.v"))
                              + f"\nchparam -set EXTENSION_MASK {mask} -set PCPI_LATENCY {latency} core_top\n"
                              + "synth_ice40 -top core_top\ncheck -assert\nwrite_json " + quote(netlist) + "\nstat\n")
            execute(["yosys", "-s", script], folder / "ice40.log", timeout=600)
            modules = json.loads(netlist.read_text())["modules"]
            types = Counter(cell["type"] for module in modules.values() if not module.get("attributes", {}).get("blackbox")
                            for cell in module.get("cells", {}).values())
            synthesis.append(dict(configuration=name, extension_mask=mask, pcpi_response_latency=latency,
                                  cell_types=dict(sorted(types.items())), lut4_count=types.get("SB_LUT4", 0),
                                  carry_count=types.get("SB_CARRY", 0),
                                  flip_flop_count=sum(count for typ, count in types.items() if typ.startswith("SB_DFF")),
                                  memory_blocks=types.get("SB_RAM40_4K", 0),
                                  netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest()))
            print(f"Whole core {name}: {synthesis[-1]['lut4_count']} LUT4", flush=True)
            write_json(output / "synthesis.json", synthesis)
        for row in synthesis:
            row["lut4_delta_from_baseline"] = row["lut4_count"] - synthesis[0]["lut4_count"]
        write_json(output / "synthesis.json", synthesis)
    benchmark_measurements = []
    if crc32:
        embench = HARDWARE.parent / "benchmarks/embench"
        benchmark_sources = sources / "embench"
        benchmark_sources.mkdir(exist_ok=True)
        for path in (embench / "support").glob("*.h"):
            shutil.copy2(path, benchmark_sources / path.name)
        shutil.copy2(embench / "support/beebsc.c", benchmark_sources / "beebsc.c")
        original = (embench / "src/crc32/crc_32.c").read_text()
        (benchmark_sources / "crc32-upstream.c").write_text(original)
        (benchmark_sources / "crc32-fused.c").write_text(crc32_fusion_source(original))
        benchmark_revision = execute(["git", "-C", embench, "rev-parse", "HEAD"], output / "embench-revision.log").strip()
        for mask, name in ((0, "stock"), (0, "source-control"), (1, "formula0"), (2, "formula1"), (3, "both")):
            elf = output / f"crc32-{name}.elf"
            execute([gcc, "-march=rv32i_zicsr", "-mabi=ilp32", "-O2", "-std=gnu17", "-nostdlib", "-nostartfiles",
                     "-ffreestanding", "-fno-builtin", "-ffunction-sections", "-fdata-sections",
                     "-msmall-data-limit=0", "-mno-relax", "-DCPU_MHZ=1", "-DCUSTOM=0", f"-DFUSION_MASK={mask}",
                     "-I", benchmark_sources, "-Wl,--no-relax", "-Wl,--gc-sections", "-Wl,-T," + str(sources / "core_link.ld"),
                     sources / "core_start.S", sources / "core_crc_firmware.c",
                     benchmark_sources / ("crc32-upstream.c" if name == "stock" else "crc32-fused.c"),
                     benchmark_sources / "beebsc.c", "-lgcc", "-o", elf], output / f"crc32-{name}-compile.log")
            execute([objcopy, "-O", "binary", elf, output / f"crc32-{name}.bin"], output / f"crc32-{name}-objcopy.log")
            execute([objdump, "-d", elf], output / f"crc32-{name}-disassembly.txt")
        baseline_crc_raw = json.loads(execute([baseline_model, output / "crc32-stock.bin"], output / "crc32-stock-sim.json", timeout=600))
        baseline_crc = validate_crc32_simulation(baseline_crc_raw, 0)
        source_control_raw = json.loads(execute([baseline_model, output / "crc32-source-control.bin"], output / "crc32-source-control-sim.json", timeout=600))
        if validate_crc32_simulation(source_control_raw, 0) != baseline_crc:
            raise ValueError("CRC32 source wrapper changed baseline execution without custom instructions")
        for latency in (0, 1):
            model = models.get(latency) or build_model(f"custom-latency-{latency}", 3, latency)
            stock_raw = json.loads(execute([model, output / "crc32-stock.bin"], output / f"crc32-stock-extended-latency-{latency}.json", timeout=600))
            if validate_crc32_simulation(stock_raw, 0) != baseline_crc:
                raise ValueError("extended core changed stock CRC32 execution")
            for mask, name in ((1, "formula0"), (2, "formula1"), (3, "both")):
                raw = json.loads(execute([model, output / f"crc32-{name}.bin"], output / f"crc32-{name}-latency-{latency}.json", timeout=600))
                measured = validate_crc32_simulation(raw, mask)
                expected_handshakes = measured["protocol_statistics"]["pcpi_handshakes"]
                if raw["pcpi_valid_cycles"] != expected_handshakes * (latency + 1) or raw["pcpi_wait_cycles"] != expected_handshakes * latency:
                    raise ValueError("CRC32 PCPI protocol latency differs")
                benchmark_measurements.append(dict(name=name, fusion_mask=mask, pcpi_response_latency=latency,
                                                     baseline=baseline_crc, custom=measured,
                                                     cycle_ratio=baseline_crc["cycles"] / measured["cycles"],
                                                     cycles_saved=baseline_crc["cycles"] - measured["cycles"],
                                                     instructions_saved=baseline_crc["instructions"] - measured["instructions"],
                                                     stock_firmware_on_extended_core_matches=True,
                                                     firmware_sha256=hashlib.sha256((output / f"crc32-{name}.elf").read_bytes()).hexdigest()))
                print(f"Embench CRC32 {name}, latency {latency}: {measured['cycles']} cycles, self-check and full checksum passed", flush=True)
                write_json(output / "crc32-measurements.json", benchmark_measurements)
    provenance = dict(upstream_url=CORE_URL, upstream_commit=revision,
                      tools=tool_versions, seed=seed, random_vectors=128, boundary_vectors=36,
                      source_sha256={str(p.relative_to(sources)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources.rglob("*")) if p.is_file()},
                      firmware_sha256={name: hashlib.sha256((output / f"{name}.elf").read_bytes()).hexdigest() for name in ("baseline", "custom")})
    candidate_rows = json.loads((HARDWARE.parent / "results/2026-10-13/candidates/crc32.json").read_text())
    candidate_metadata = []
    for f, formula in enumerate(FORMULAS):
        row = next(r for r in candidate_rows if r["formula"] == formula)
        candidate_metadata.append(dict(formula_index=f, candidate_id=candidate_id("crc32", formula), formula=formula,
                                       source_benchmark="crc32", original_size=row["size"],
                                       occurrence_functions=sorted({s for o in row["occurrences"] for s in o["symbols"]}),
                                       overlap_safe_saved=row["overlapSafeSaved"],
                                       encoding=dict(opcode="0x0b", funct7=1, funct3=f)))
    summary = dict(scope="PicoRV32 formula recurrence microbenchmark and source-modified Embench CRC32 RV32I port",
                   candidates=candidate_metadata, provenance=provenance,
                   core_configuration=dict(isa="RV32I plus counter reads, no compressed/multiply/divide/IRQ",
                                           dual_port_register_file=True, barrel_shifter=False, two_stage_shift=True,
                                           registers_initialized_zero=True, counters64=False, ram_bytes=65536,
                                           memory="external zero-wait native memory; mem_ready=1; byte stores",
                                           reset_cycles=8, common_clock=True),
                   timing_window="rdcycle before/after leaf call; includes call, loop setup/control, return and surrounding counter-window instructions",
                   lengths=list(LENGTHS), samples_per_length=3, direct_checks_per_firmware=2 * len(vectors),
                   measurements=measurements, synthesis=synthesis,
                   crc32_benchmark=dict(measurements=benchmark_measurements, source_revision=benchmark_revision if crc32 else None,
                                        implementation="upstream stock C versus source-level UPDC32 lowering with one/two .insn formulas; same GCC flags, random generator, table and repetitions",
                                        repetitions=170, updates_per_repetition=1024, cpu_mhz_macro=1,
                                        warmup_repetitions=1, extra_full_checksum_repetitions=1,
                                        source_wrapper_without_custom_matches_stock=True,
                                        reference_checksum=crc32_oracle(),
                                        measured_window="upstream benchmark() including rand_beebs software constant multiplication, CRC loop, calls and control; warmup/checksum/verification excluded",
                                        isa_port="RV32I; GCC lowers the random generator constant multiplication to shifts/adds/subtracts. libgcc is linked but __mulsi3 is not called. Different from the original RV32IM Spike trace compiler target.",
                                        stock_firmware_sha256=hashlib.sha256((output / "crc32-stock.elf").read_bytes()).hexdigest() if crc32 else None),
                   negative_controls=dict(custom_firmware_traps_on_baseline=True,
                                          malformed_funct7_funct3_opcode_trap_on_each_custom_latency=True),
                   limitations=["Recurrence microbenchmark ratios are separate from the source-modified CRC32 benchmark results. No eight-workload integrated speedup study is claimed.",
                                "The CRC32 baseline is the original C compiled for RV32I with software multiplication; custom variants lower the UPDC32 source macro. Compiler register allocation can change, so benchmark instruction deltas need not equal extracted binary savings.",
                                "Cycles compare identical zero-wait memory settings on a small multicycle core; results do not transfer unchanged to other cores or memory systems.",
                                "PCPI latency is valid-to-ready wait cycles, not complete instruction cycles; data/decode path and core scheduling contribute separately.",
                                "No place-and-route, clock-period, fmax or wall-time speedup measurement; cycle ratios assume equal achievable clocks.",
                                "Whole-core iCE40 synthesis excludes external RAM/peripherals and reports all cell types; LUT4 alone is not physical area.",
                                "Boundary/random self-checks and host oracles are testing, not a formal proof."])
    write_json(output / "summary.json", summary)
    return summary


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("generated/core"))
    parser.add_argument("--core-dir", type=Path, default=Path("../toolchains/picorv32"))
    parser.add_argument("--toolchain-prefix", default="riscv-none-elf-")
    parser.add_argument("--latencies", type=int, nargs="+", default=[0, 1, 4, 16, 24])
    parser.add_argument("--seed", type=int, default=20261013)
    parser.add_argument("--skip-synthesis", action="store_true")
    parser.add_argument("--skip-crc32", action="store_true")
    args = parser.parse_args(argv)
    if any(value < 0 or value > 64 for value in args.latencies):
        parser.error("latencies must be between 0 and 64")
    run_experiment(args.output_dir, args.core_dir, args.toolchain_prefix,
                   tuple(args.latencies), args.seed, not args.skip_synthesis, not args.skip_crc32)


if __name__ == "__main__":
    main()
