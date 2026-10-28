# Preserved scoring launch-order failure

The first read-only scoring launch occurred before the collection process finished writing native-audit.json, and failed with FileNotFoundError. After confirming collection exit status0, the same frozen scoring command succeeded. Candidate measurements were not retried, no model or policy changed, and the final archive/native audit/deterministic policy replay verified. This is orchestration failure evidence, not an additional candidate failure or measurement.
