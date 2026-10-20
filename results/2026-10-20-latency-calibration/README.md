# Independent PicoRV32 operation-latency calibration

222 fixed instruction/input cases passed semantic checks and the unextended-core custom-op trap control. Eight serial native commands cost 5.095776124944678 command-seconds. The firmware occupies 3,212 bytes under the unchanged 4,096-byte guard. Two RTL runs, no synthesis, no new application labels.

The fixed SoC measures ALU operations at 4 cycles, immediate shifts at `4 + floor(s/4) + s%4`, and the existing one-wait PCPI add datapath at 5 cycles. These are launch-to-launch spans under this memory/interface configuration. They are not arbitrary PicoRV32 timings, area predictions, routed-clock results, or an assertion that multiple custom-instruction speedups add.

The [plan](plan.json) records all cases before execution, tool/input/source identities and a bounded eight-command budget. [Raw command receipts](commands.json), both simulator traces, firmware, disassembly, inputs, and source copies are authenticated by [manifest](manifest.json). The [report](report.json) is independently reconstructed from those traces. Original application results are untouched.

```sh
make reproduce-model-analysis
python scripts/calibrate_picorv32_latency.py audit --root results/2026-10-20-latency-calibration
```

Fresh collection uses a fresh directory:

```sh
python scripts/calibrate_picorv32_latency.py prepare \
  --reference-root generated/codesign-crc32-2026-10-19-r1 \
  --root generated/latency-calibration-new
python scripts/calibrate_picorv32_latency.py collect --root generated/latency-calibration-new
```

Calibrated costs feed the [model diagnosis](../../docs/model-analysis.md). Choosing to investigate this rule followed examination of consumed application data; the independent operation measurement is not a new held-out workload experiment. The manifest predates this explanatory README and intentionally covers the immutable evidence files only.
