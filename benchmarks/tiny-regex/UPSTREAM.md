# tiny-regex-c source snapshot

The vendored sources are unmodified files from `kokke/tiny-regex-c` at commit
`f2632c6d9ed25272987471cdb8b70395c2460bdb` (Unlicense). `re.c`, `re.h`, and
`tests/test1.c` are retained under `upstream/`; their SHA-256 and Git blob IDs
are recorded in `SOURCE_PIN.json`. The root `LICENSE` is the exact upstream
Unlicense file.

`adapter.c` calls the unchanged upstream test `main` and treats its failure
count as the benchmark result. The only operational changes are suppressed
console output, a no-op diagnostic printer for the failure-only path, and
freestanding C-locale ASCII implementations of `isdigit`, `isalpha`, and
`isspace`. Fixed test strings are ASCII; no arbitrary locale or non-ASCII
behavior is claimed. The complete 76-case original suite remains the timed
workload. The host reproduction command is recorded in the source census.
