# Contributing

The `latest` branch is the focused research snapshot: model code, two pretrained forests, three benchmark panels and concise documentation. Start with [the model](docs/model.md), [evaluation definitions](docs/benchmarks.md) and [reproduction](docs/reproduce.md).

Keep benchmark observations and pretrained weights immutable. Add a separately declared evaluation when changing a model; do not silently tune on reported tests and relabel them as fresh. Report zero targets, large underpredictions, hardware-budget mistakes and negative results alongside average improvements.

Saved models bind their runtime source files. Preserve the existing package files when using those weights, or explicitly produce and validate a new compatible artifact. Model versions inside the serialized runtime are implementation identities, not a changelog for the README.

Run `make test`, `make reproduce` and a cached prediction smoke check for functional changes. Inspect regenerated figures visually. Keep builds, traces, caches and disposable outputs in `generated/`. Historical experiment-specific protocols, scripts and tests remain available in the [immutable research archive](https://github.com/jas0nriverah/agentic-riscv-codesign/tree/b64716a2b94b332fdbced677869620bb949c073d).
