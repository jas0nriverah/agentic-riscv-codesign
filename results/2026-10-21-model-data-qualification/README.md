# Additional-workload qualification attempts

Preserved negative data-collection evidence while improving the selection model. These diagnostics create no candidate performance labels and do not change any existing experiment. No source inputs, core, ISA or memory partition were changed to make a workload fit.

- `sglib-combined`: the pinned RV32I object compile succeeds, but its 8,192-byte heap plus 400-byte array and 80-byte hash storage already exceed 8KiB before code/stack. Symbols, object and compiler record retained.
- `qrduino`: source inspection finds an 8,192-byte heap. This is a static rejection, not an execution or compiler result. The exact source hash and lines are retained.
- `minver`: a generic full-source firmware link with software arithmetic has program/BSS end13,704, exceeding8KiB by5,512bytes. The earlier SHA-specific wrapper probe also failed; that unsuitable wrapper is not evidence that floating-point software is unsupported. Both diagnostics/logs/maps retained.

The next bounded experiment therefore uses six previously unmeasured SHA256 formulas from the unchanged full original source/input. It tests new candidate decisions on consumed source, not a seventh workload or independent source generalization. Its protocol/models/predictions were committed before candidate measurements.

A zero-label preparation error was also retained: the target context map was initially keyed by context hash rather than benchmark:context. Validation stopped before model fitting or candidate measurement; the key was corrected and preparation restarted in a fresh directory. The fixed ML hypothesis was not changed.
