# Presentation stopping-point validation

One bounded implementation adds archive-only reproduction of the preserved countnegative rejection. No model training, candidate measurement, or new workload run was performed.

- Latest focused replay tests: **8 passed**, including traversal, symlink, duplicate, dot-path and corrupted-member rejection, protected output paths, and a real exact replay with subprocesses and original-native-root reads forbidden.
- Full suite: **4,293 passed / 181 subtests passed / one failed** in 259.27 seconds. The failure is the previously documented `test_capture_v11_spooled.py` blocked-pipe cleanup check. This full run preceded the final dot-path guard/test addition; the latest focused run covers that change. No cleanup fix is claimed. The reported leftover PID was absent at the final process check.
- `make reproduce`: all six frozen model metrics match.
- `make reproduce-speedup`: original CRC32 and automatic-workload evidence and policy replays pass.
- `make reproduce-countnegative-diagnosis`: exact report/file-hash replay succeeds from the committed archive, with zero native jobs and zero candidate labels. Use a fresh generated output path on repetition.

The raw full-suite failure and existing result-replay logs are preserved alongside `validation.json`. This validation does not establish a model improvement or ML superiority.
