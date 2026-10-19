# V11 feature-layout compatibility evidence

This is one **historical V13 input-feature** replay, not a new V11 circuit extraction, model load, prediction or target measurement. It checks compatibility of the proposed per-original cache layout with the frozen raw-graph replay helper.

The retained driver copied and hash-checked 12 cache files (7,126,948 bytes) for one existing committed formula. The replay reconstructed all 336 feature columns and the selected 217 exactly. Original and normalized generic channels share a cache for this formula, giving two native-channel identities in the archived evidence. No new native jobs were run.

The driver, exact executed prediction-source snapshot, selected record and audit receipt are copied byte-for-byte from `generated/v11-feature-compatibility/attempt-0000/`. The local extracted cache is not duplicated here: its source is the existing committed V13 raw ZIP, identified by SHA256 in the receipt. The driver uses that original local scratch path and requires a fresh scratch directory for another execution. These saved checks are not evidence that a later runner version or the complete V11 pool has passed.

The separate implementation review and full-pool admission remain required. The manifest authenticates this small evidence package; the receipt records the helper/archive identities and zero new model/native/label calls.
