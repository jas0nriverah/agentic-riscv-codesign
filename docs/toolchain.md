# Reproduce the measured Embench runs

The eight programs execute their upstream `verify_benchmark` self-check on Spike.
A zero Spike exit code means the program's check passed. The trace window is
bounded by the two `instret` reads in `benchmarks/embench-hooks.c`; the decoder
requires the retired-instruction delta to equal the recorded instruction count
plus the stop marker and rejects missing markers or unknown instructions.

These are actual RISC-V executions, compiled from the pinned Embench source.
Spike reports architectural retired instructions, not target hardware cycles.
Do not present the instruction counts or estimated fusion savings as measured
CPU speedup, energy reduction, or complete core performance.

## Tool versions used on Apple Silicon macOS

- [xPack GNU RISC-V Embedded GCC 15.2.0-1](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v15.2.0-1), Darwin ARM64.
- Archive SHA-256: `6588e8351455fad8aca37551f0e5a5543f3346bfa9a837cf03cbd3bdd4989f8f`.
- [Official Spike source](https://github.com/riscv-software-src/riscv-isa-sim), revision `f8a060b7bea8da6f738f193ed1b66b665978d092`, reports `1.1.1-dev`.
- Embench submodule revision `0466a18e4f6b47e19598d7c6ba72916d54b68f65`.
- Compiler flags: `-march=rv32im -mabi=ilp32 -O2 -std=gnu17 -DCPU_MHZ=1 -DWARMUP_HEAT=1`.
- Spike flags: `--isa=rv32im_zicntr -m16`.

`CPU_MHZ=1` selects the upstream repetition factor; it does not set a simulated
clock. Each workload runs one warmup before the measured region; Spike does not
model cache timing in this experiment. The custom
bare-metal linker places the program at `0x80000000` in 16 MiB of RAM and uses
Spike's `tohost` exit protocol. A linker RWX LOAD-segment warning is expected
for this simple bare-metal memory layout.

## Install tools locally

Run from a directory used for development tools. Set the absolute path explicitly;
these commands do not alter your shell startup files.

```sh
mkdir -p work/toolchains
curl -fL --retry 3 https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v15.2.0-1/xpack-riscv-none-elf-gcc-15.2.0-1-darwin-arm64.tar.gz -o work/toolchains/gcc.tar.gz
shasum -a 256 work/toolchains/gcc.tar.gz
# Compare the output with the SHA-256 above before extracting.
tar -xzf work/toolchains/gcc.tar.gz -C work/toolchains
brew install dtc boost
git clone https://github.com/riscv-software-src/riscv-isa-sim.git work/toolchains/spike-source
git -C work/toolchains/spike-source checkout f8a060b7bea8da6f738f193ed1b66b665978d092
mkdir -p work/toolchains/spike-build
cd work/toolchains/spike-build
../spike-source/configure --prefix="$(cd .. && pwd)/spike" --with-boost=/opt/homebrew
make -j6
make install
```

Commit logging is included by this Spike revision; an `--enable-commitlog`
configure argument is unnecessary. Homebrew's `spike` cask is a LEGO app, so
installing that cask does not supply the RISC-V simulator. xPack includes the
newlib headers/libraries required by these benchmarks.

## Run and save evidence

From the repository root, replace `/absolute/toolchains` with the install path:

```sh
git submodule update --init benchmarks/embench
python3 src/run_real_benchmarks.py \
  --cc /absolute/toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc \
  --spike /absolute/toolchains/spike/bin/spike \
  --spike-source /absolute/toolchains/spike-source
```

The runner rebuilds each ELF, runs its self-check, then records and validates the
complete measurement trace. It fails immediately if compilation, simulation,
or trace validation fails. Evidence is saved in `generated/real/benchmarks.json`
with exact commands, exit codes, compiler versions, source revision, ELF hashes,
trace hashes, and counters. Build/run/trace logs are adjacent. Streamed decoded
traces and small counter summaries are in `generated/traces/`. Raw Spike logs
are piped directly into the decoder to avoid storing a second large trace.
Allow several gigabytes of disk space for all eight decoded traces.

To extract candidates with the same toolchain:

```sh
make candidates \
  CC=/absolute/toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc \
  OBJDUMP=/absolute/toolchains/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-objdump \
  SPIKE=/absolute/toolchains/spike/bin/spike
```

`generated/` is ignored by Git. Preserve the small JSON reports and selected
candidate evidence with presentation materials; regenerate the bulky traces
using the pinned versions when needed.
