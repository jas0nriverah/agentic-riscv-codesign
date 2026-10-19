"""Evidence gates reject plausible but incorrect processor measurements."""
from copy import deepcopy

import pytest

from isaforge.core_experiment import (
    LENGTHS, SUCCESS, compare_runs, crc32_fusion_source,
    crc32_oracle, make_vectors, oracle, validate_crc32_simulation,
    validate_simulation,
)


def simulation_fixture(custom=True, latency=1):
    vectors = make_vectors(7)
    words = []
    for f in range(2):
        for a, b in vectors:
            words.extend((0, f, 1, a, b, oracle(f, a, b), 0, 0))
        for s in range(3):
            a, b = vectors[-1-s]
            for n in LENGTHS:
                words.extend((1, f, n, a, b, oracle(f, a, b, n),
                              50 + n * (16 if custom else 23),
                              10 + n * (4 if custom else (6 if f == 0 else 5))))
    count = 2 * len(vectors) + 6 * sum(LENGTHS) if custom else 0
    return vectors, dict(status=SUCCESS, words=words, pcpi_handshakes=count,
                         pcpi_valid_cycles=count * (latency + 1),
                         pcpi_wait_cycles=count * latency)


def test_wraparound_and_logical_shift_semantics():
    assert oracle(0, 0xFFFFFFFF, 0) == 1020
    assert oracle(0, 0xFFFFFFFF, 0xFFFFFFFF) == 0
    assert oracle(1, 0, 0x80000000) == 0x800000
    assert oracle(1, 0xFFFFFFFF, 0xFFFFFFFF) == 0xFF000000
    assert oracle(0, 0x12345678, 0xFFFFFFFF, 0) == 0x12345678


def test_measurement_gates_preserve_actual_instruction_deletion():
    vectors, raw_base = simulation_fixture(custom=False)
    _, raw_custom = simulation_fixture()
    base = validate_simulation(raw_base, vectors, custom=False, latency=1)
    custom = validate_simulation(raw_custom, vectors, custom=True, latency=1)
    comparisons = compare_runs(base, custom)
    assert len(comparisons) == 36
    assert max(r["deleted_instructions"] for r in comparisons) == 2048
    for row in comparisons:
        if row["iterations"] == 0:
            assert row["cycle_ratio"] == 1
    custom[-1]["instructions"] += 1
    with pytest.raises(ValueError, match="instruction delta"):
        compare_runs(base, custom)


@pytest.mark.parametrize("fault", ["checksum", "missing", "extra", "reorder", "status", "handshake", "latency", "wait"])
def test_rejects_incorrect_or_incomplete_simulation(fault):
    vectors, raw = simulation_fixture()
    if fault == "checksum":
        raw["words"][5] ^= 1
    elif fault == "missing":
        raw["words"] = raw["words"][:-8]
    elif fault == "extra":
        raw["words"].extend(raw["words"][-8:])
    elif fault == "reorder":
        raw["words"][:16] = raw["words"][8:16] + raw["words"][:8]
    elif fault == "status":
        raw["status"] = 0
    elif fault == "handshake":
        raw["pcpi_handshakes"] += 1
    elif fault == "latency":
        raw["pcpi_valid_cycles"] += 1
    elif fault == "wait":
        raw["pcpi_wait_cycles"] -= 1
    with pytest.raises(ValueError):
        validate_simulation(raw, vectors, custom=True, latency=1)


def test_rejects_different_workloads_in_cycle_comparison():
    vectors, raw_base = simulation_fixture(custom=False)
    _, raw_custom = simulation_fixture()
    base = validate_simulation(raw_base, vectors, custom=False, latency=1)
    custom = validate_simulation(raw_custom, vectors, custom=True, latency=1)
    custom[-1]["input_b"] ^= 1
    with pytest.raises(ValueError, match="workloads differ"):
        compare_runs(base, custom)


def test_rejects_zero_work_cycle_overhead_mismatch():
    vectors, raw_base = simulation_fixture(custom=False)
    _, raw_custom = simulation_fixture()
    base = validate_simulation(raw_base, vectors, custom=False, latency=1)
    custom = validate_simulation(raw_custom, vectors, custom=True, latency=1)
    zero = next(row for row in custom if row["kind"] == "timed" and row["iterations"] == 0)
    zero["cycles"] += 1
    with pytest.raises(ValueError, match="zero-work cycle overhead"):
        compare_runs(base, custom)


def test_crc32_full_checksum_instead_of_only_low15_bits():
    crc = crc32_oracle()
    assert crc & 32767 == 11433
    raw = dict(status=SUCCESS, words=[crc, 11433, 90000, 22000, 1],
               pcpi_handshakes=172 * 1024 * 2)
    assert validate_crc32_simulation(raw, 3)["full_checksum"] == crc
    wrong = deepcopy(raw)
    wrong["words"][0] ^= 0x80000000  # Upstream low15-bit check alone would pass.
    with pytest.raises(ValueError, match="full CRC32"):
        validate_crc32_simulation(wrong, 3)
    wrong = deepcopy(raw)
    wrong["pcpi_handshakes"] -= 1024
    with pytest.raises(ValueError, match="instruction count"):
        validate_crc32_simulation(wrong, 3)


def test_crc32_source_rewrite_requires_exact_upstream_macro():
    original = "license\n#define UPDC32(octet,crc) (crc_32_tab[((crc)^((BYTE)octet)) & 0xff] ^ ((crc) >> 8))\nunchanged\n"
    modified = crc32_fusion_source(original)
    assert modified.startswith("license\n") and modified.endswith("unchanged\n")
    assert '.insn r 0x0b, 0, 1' in modified
    assert '.insn r 0x0b, 1, 1' in modified
    with pytest.raises(ValueError, match="macro differs"):
        crc32_fusion_source("different macro")
