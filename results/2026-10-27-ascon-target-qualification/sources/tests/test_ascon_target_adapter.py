from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import build_ascon128_v13_target_adapter as builder
from scripts import build_ascon128_v13_target_manifest as manifest_builder
from scripts import preflight_ascon128_v13 as preflight
from isaforge import codesign as c


ROOT = builder.ROOT
PROGRAM = builder.OUTPUT
FAKE_API = ROOT / "tests/ascon_fake_crypto_api.c"


def _compile(compiler: str, output: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([compiler, *map(str, args), "-o", str(output)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_generated_target_translation_unit_is_exact_and_uses_pinned_sources():
    source = builder.build_source()
    assert PROGRAM.read_bytes() == source
    assert hashlib.sha256(source).hexdigest() == \
        "a9f7ba82739d242558fe8f4a7995cdfca8e4526cf7b1cef32627ff85b69f8168"
    assert b"ASCON_V13_EXPECTED_KAT_FNV32 0x06cf04e8u" in source
    assert b"ASCON_V13_EXPECTED_CASES 1089U" in source
    assert b"ASCON_V13_EXPECTED_ENCRYPTIONS 1089U" in source
    assert b"ASCON_V13_EXPECTED_DECRYPTIONS 2178U" in source
    verbatim_notice = (ROOT / preflight.WRAPPER).read_text().split(
        "// This file has been modified.", 1)[0].encode()
    assert source.startswith(verbatim_notice)


def test_target_adapter_manifest_authenticates_all_relevant_sources():
    recorded = c.unseal(manifest_builder.OUTPUT)
    assert recorded == manifest_builder.build_manifest()
    assert recorded["qualification"] == dict(target_jobs=0,
        candidate_dispatch_enabled=False, candidate_attempts=0,
        target_labels=0, model_fits=0)
    assert recorded["source_family_evidence"]["independent_confirmatory_family"] is False
    for name, digest in recorded["source_bindings"].items():
        assert c.sha(ROOT / name) == digest


def test_same_target_loop_emits_every_pinned_kat_bytewise(tmp_path):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("host C compiler unavailable")
    binary = tmp_path / "ascon-target-host-kat"
    result = _compile(compiler, binary, "-std=c99", "-O2", "-Wall", "-Wextra",
        "-Werror", "-Wno-unused-function", "-DASCON_V13_EMIT_HOST_KAT=1",
        "-DASCON_V13_HOST_TEST_MAIN=1", str(PROGRAM))
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    completed = subprocess.run([str(binary)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == (ROOT / preflight.KAT).read_bytes()
    assert completed.stderr == (
        b"ASCON_TARGET_HOST PASS cases=1089 encryptions=1089 "
        b"decryptions=2178 hash=06cf04e8\n")
    records = preflight.parse_kat(completed.stdout)
    assert preflight.validate_record_inputs(records)["ciphertext_bytes_compared"] == 34848


@pytest.mark.parametrize(("fault", "failure_code", "failure_case"), [
    (0, 7, 1089),  # self-consistent fake output must still fail the KAT fingerprint
    (1, 1, 1),     # encryption failure
    (2, 2, 1),     # incorrect ciphertext length
    (3, 3, 1),     # valid ciphertext rejected
    (4, 4, 1),     # recovered length mismatch
    (5, 5, 34),    # wrong recovered plaintext at first nonempty message
    (6, 6, 1),     # tampered ciphertext accepted
])
def test_target_loop_fails_closed_for_fake_api_outputs(
        tmp_path, fault: int, failure_code: int, failure_case: int):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("host C compiler unavailable")
    binary = tmp_path / f"ascon-target-fault-{fault}"
    result = _compile(compiler, binary, "-std=c99", "-O2", "-Wall", "-Wextra",
        "-Werror", "-Wno-unused-function", "-DASCON_V13_FAKE_API=1",
        "-DASCON_V13_HOST_TEST_MAIN=1",
        f"-DASCON_FAULT={fault}", "-I", str(ROOT / preflight.REFDIR),
        "-I", str(ROOT / preflight.TESTDIR), str(PROGRAM), str(FAKE_API))
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    completed = subprocess.run([str(binary)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert completed.returncode == 1
    assert completed.stdout == b""
    assert completed.stderr == (
        f"ASCON_TARGET_HOST FAIL code={failure_code} case={failure_case}\n"
    ).encode()
