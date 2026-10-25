# Original-input lift qualification target

The three C files, both headers, `README` and `changeLog.txt` are unchanged
TACLeBench files from commit `c6a0d73e47bbd2bc86e34637156fb26dd4d5cf08`.
[Separate provenance](../LIFT_SOURCES.json) binds the primary archive and every
upstream file; locally computed Git blob IDs are not independent fetch evidence.
Original GPL notices and upstream documentation are retained.

`isaforge_adapter.c` asserts ILP32,16-bit short and8-bit bytes. It includes
`lift.c`, `liftlibio.c` and `liftlibcontrol.c` in that order, renames only upstream
`main`, retains every original `lift_*` symbol/storage object and checks original
array sizes. This is a declared single translation unit `-Os` build, not a claim
of binary identity with the upstream separate-object build.

The adapter calls the original initialization outside timing, then original
`lift_main` and `lift_return` inside timing. It preserves all1,001 iterations,
zero digital/ADC stimuli, controller state initialization, level table and
checksum4,005,888. The existing generic harness calls the original return check
again after timing. It is a fixed-input aggregate check, not a universal proof.

`isaforge.lift_workload` scopes and restores the existing source registration and
reuses guarded extraction, relocation rejection, lowering, memory checks and
baseline routing. Qualification requires twelve executable calibrated formulas
and one formula meeting both0.5% public estimated cycle reduction and ten timed
replacements. RV32I_zicsr/ILP32 `-Os`, integrated8KiB RAM and6400/6528 partition
are retained. Code/stack fit and pool qualification remain untested until the
serialized native qualification runs. A rejection is preserved without retuning
inputs, memory, pool or gates. Candidate dispatch remains disabled.
