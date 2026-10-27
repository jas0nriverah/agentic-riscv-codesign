import copy
import shutil
import subprocess

import pytest

from scripts import preflight_ascon128_v13 as preflight


def test_pinned_upstream_kat_has_all_exact_ordered_records():
    raw = (preflight.ROOT / preflight.KAT).read_bytes()
    rows = preflight.parse_kat(raw)
    checks = preflight.validate_record_inputs(rows)
    assert len(rows) == 1089
    assert rows[0]["PT"] == rows[0]["AD"] == ""
    assert rows[-1]["Count"] == "1089"
    assert checks["encryptions"] == 1089
    assert checks["total_decryptions"] == 2178
    assert checks["field_values_compared"] == 6534
    assert checks["ciphertext_bytes_compared"] == 34848


def test_parser_requires_exact_field_order_and_consecutive_counts():
    raw = b"Count = 1\nKey = 000102030405060708090A0B0C0D0E0F\nNonce = 000102030405060708090A0B0C0D0E0F\nPT = \nAD = \nCT = 00000000000000000000000000000000\n\n"
    with pytest.raises(ValueError, match="expected 1089 records"):
        preflight.parse_kat(raw)


@pytest.mark.parametrize("mutate, message", [
    (lambda lines: [lines[1], lines[0], *lines[2:]], "expected Count field"),
    (lambda lines: ["Count = 2", *lines[1:]], "nonconsecutive Count"),
    (lambda lines: [*lines[:2], "Nonce = 0x00", *lines[3:]], "malformed uppercase hexadecimal Nonce"),
])
def test_parser_rejects_malformed_or_noncanonical_single_record(mutate, message):
    lines = ["Count = 1", "Key = 000102030405060708090A0B0C0D0E0F",
        "Nonce = 000102030405060708090A0B0C0D0E0F", "PT = ", "AD = ",
        "CT = 00000000000000000000000000000000"]
    raw = ("\n".join(mutate(lines)) + "\n\n").encode("ascii")
    with pytest.raises(ValueError, match=message):
        preflight.parse_kat(raw)


def test_record_input_validation_detects_wrong_length_pair_or_ciphertext_size():
    rows = preflight.parse_kat((preflight.ROOT / preflight.KAT).read_bytes())
    wrong_input = copy.deepcopy(rows)
    wrong_input[0]["AD"] = "00"
    with pytest.raises(ValueError, match="AD differs"):
        preflight.validate_record_inputs(wrong_input)
    wrong_ciphertext = copy.deepcopy(rows)
    wrong_ciphertext[0]["CT"] = "00"
    with pytest.raises(ValueError, match="ciphertext length differs"):
        preflight.validate_record_inputs(wrong_ciphertext)


def test_fieldwise_comparison_checks_every_field_in_every_record():
    rows = preflight.parse_kat((preflight.ROOT / preflight.KAT).read_bytes())
    assert preflight.compare_records(rows, copy.deepcopy(rows)) == 6534
    mutated = copy.deepcopy(rows)
    mutated[1088]["CT"] = "00" * 48
    with pytest.raises(ValueError, match="record 1089: CT differs"):
        preflight.compare_records(mutated, rows)


def test_runtime_call_receipt_requires_exact_encryption_and_decryption_counts():
    summary = b"ASCON_HOST_PREFLIGHT PASS cases=1089 encryptions=1089 decryptions=2178\n"
    assert preflight.parse_call_summary(summary) == {
        "cases": 1089, "encryptions": 1089, "decryptions": 2178,
    }
    with pytest.raises(ValueError, match="exact checked crypto API call counts"):
        preflight.parse_call_summary(summary.replace(b"decryptions=2178", b"decryptions=2177"))


@pytest.mark.parametrize("fault, reason", [
    (1, "encryption failed"),
    (2, "unexpected ciphertext length"),
    (3, "valid ciphertext was rejected"),
    (4, "unexpected plaintext length"),
    (5, "did not recover the original plaintext"),
    (6, "tampered ciphertext was accepted"),
])
def test_c_wrapper_fails_closed_under_fake_crypto_api_faults(tmp_path, fault, reason):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("host C compiler unavailable")
    refdir = preflight.ROOT / preflight.REFDIR
    testdir = preflight.ROOT / preflight.TESTDIR
    binary = tmp_path / f"wrapper-fault-{fault}"
    command = [compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        f"-DASCON_FAULT={fault}", "-I", str(refdir), "-I", str(testdir),
        str(preflight.ROOT / preflight.WRAPPER),
        str(preflight.ROOT / "tests/ascon_fake_crypto_api.c"), "-o", str(binary)]
    built = subprocess.run(command, cwd=preflight.ROOT, capture_output=True, check=False)
    assert built.returncode == 0, built.stderr.decode("utf-8", "replace")
    run = subprocess.run([str(binary)], cwd=preflight.ROOT,
        capture_output=True, check=False, timeout=10)
    assert run.returncode != 0
    assert reason.encode() in run.stderr


def test_copied_upstream_sources_match_all_pinned_hashes():
    source, copied, source_digest = preflight.verify_source_copy()
    assert source["commit"] == "b7ca60bbf86479785de08b75aab2425dce4e9e8b"
    assert len(copied["files"]) == 13
    assert source_digest == copied["source_manifest_sha256"]
