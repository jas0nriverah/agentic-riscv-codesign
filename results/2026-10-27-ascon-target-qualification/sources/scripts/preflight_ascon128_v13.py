"""Run the pinned Ascon-128 v1.3.0 host KAT and verifier preflight only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c

SOURCE = "scripts/preflight_ascon128_v13.py"
WRAPPER = "benchmarks/ascon/ascon128v13_host_preflight.c"
SOURCE_MANIFEST = "benchmarks/ascon/ASCON128_V13_SOURCES.json"
COPY_MANIFEST = "benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json"
CONTRACT = "docs/ascon-adapter-contract-2026-10-26.md"
TEST = "tests/test_ascon_preflight.py"
FAKE_API = "tests/ascon_fake_crypto_api.c"
KAT = "benchmarks/ascon/upstream/crypto_aead/ascon128v13/LWC_AEAD_KAT_128_128.txt"
REFDIR = "benchmarks/ascon/upstream/crypto_aead/ascon128v13/ref"
TESTDIR = "benchmarks/ascon/upstream/tests"
DEFAULT_OUTPUT = "results/2026-10-26-ascon-host-preflight-r3"
UPSTREAM_COMMIT = "b7ca60bbf86479785de08b75aab2425dce4e9e8b"
FIELDS = ("Count", "Key", "Nonce", "PT", "AD", "CT")
EXPECTED_CASES = 1089


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def bindings() -> dict[str, str]:
    source = json.loads((ROOT / SOURCE_MANIFEST).read_text())
    copies = c.unseal(ROOT / COPY_MANIFEST)
    names = [SOURCE, WRAPPER, SOURCE_MANIFEST, COPY_MANIFEST, CONTRACT, TEST, FAKE_API,
             *(item["repository_path"] for item in copies["files"].values())]
    return {name: c.sha(ROOT / name) for name in names}


def verify_source_copy() -> tuple[dict, dict, str]:
    source_path = ROOT / SOURCE_MANIFEST
    source = json.loads(source_path.read_text())
    copy = c.unseal(ROOT / COPY_MANIFEST)
    require(source.get("suite") == "ascon/ascon-c" and source.get("tag") == "v1.3.0" and
            source.get("commit") == UPSTREAM_COMMIT,
            "Pinned upstream repository/tag/commit required")
    require(copy.get("schema") == "isaforge-ascon-v13-source-copy-v1" and
            copy.get("commit") == UPSTREAM_COMMIT and copy.get("tag") == "v1.3.0" and
            copy.get("source_manifest_sha256") == c.sha(source_path) and
            copy.get("exact_byte_copies") is True,
            "Authenticated exact-copy manifest required")
    require(set(copy.get("files", {})) == set(source.get("files", {})),
            "Upstream copy manifest must cover every source-manifest entry")
    copied_bytes = 0
    for name, item in source["files"].items():
        copied = copy["files"][name]
        require(copied.get("upstream_path") == item["upstream_path"] and
                copied.get("bytes") == item["bytes"] and
                copied.get("sha256") == item["sha256"],
                "Copied source metadata differs from pinned upstream: " + name)
        path = ROOT / copied["repository_path"]
        require(path.is_file() and path.stat().st_size == item["bytes"] and
                c.sha(path) == item["sha256"],
                "Copied upstream bytes differ: " + name)
        copied_bytes += item["bytes"]
    kat_meta = source["files"]["known_answer_vectors"]
    require(kat_meta.get("count") == EXPECTED_CASES and
            ROOT.joinpath(KAT).stat().st_size == kat_meta["bytes"],
            "Complete 1,089-record KAT file required")
    return source, copy, str(c.sha(source_path))


def parse_kat(raw: bytes) -> list[dict[str, str]]:
    require(raw.endswith(b"\n\n"), "KAT serialization must end with one blank line")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("KAT serialization must be ASCII") from error
    blocks = text[:-2].split("\n\n")
    records = []
    for index, block in enumerate(blocks, 1):
        lines = block.split("\n")
        require(len(lines) == len(FIELDS), f"record {index}: exactly six fields required")
        record = {}
        for field, line in zip(FIELDS, lines):
            prefix = field + " = "
            require(line.startswith(prefix), f"record {index}: expected {field} field")
            value = line[len(prefix):]
            if field == "Count":
                require(value.isdigit() and value == str(index),
                        f"record {index}: nonconsecutive Count")
            else:
                require(len(value) % 2 == 0 and value == value.upper() and
                        all(ch in "0123456789ABCDEF" for ch in value),
                        f"record {index}: malformed uppercase hexadecimal {field}")
            record[field] = value
        records.append(record)
    require(len(records) == EXPECTED_CASES,
            f"expected {EXPECTED_CASES} records, found {len(records)}")
    return records


def validate_record_inputs(records: list[dict[str, str]]) -> dict:
    require(len(records) == EXPECTED_CASES, "Exactly 1,089 ordered records required")
    key = bytes(range(16)).hex().upper()
    nonce = bytes(range(16)).hex().upper()
    index = 0
    ciphertext_bytes = 0
    for mlen in range(33):
        for adlen in range(33):
            row = records[index]
            expected = {
                "Count": str(index + 1),
                "Key": key,
                "Nonce": nonce,
                "PT": bytes(range(mlen)).hex().upper(),
                "AD": bytes(range(adlen)).hex().upper(),
            }
            for field, value in expected.items():
                require(row[field] == value,
                        f"record {index + 1}: {field} differs from pinned input construction")
            require(len(row["CT"]) == 2 * (mlen + 16),
                    f"record {index + 1}: ciphertext length differs")
            ciphertext_bytes += len(row["CT"]) // 2
            index += 1
    return dict(records=index, encryptions=index, valid_decryptions=index,
        tamper_rejection_decryptions=index, total_decryptions=2 * index,
        field_values_compared=6 * index, ciphertext_bytes_compared=ciphertext_bytes,
        ordered_input_pairs=33 * 33)


def compare_records(actual: list[dict[str, str]], expected: list[dict[str, str]]) -> int:
    require(len(actual) == len(expected) == EXPECTED_CASES,
            "Both KAT sources must contain exactly 1,089 records")
    compared = 0
    for index, (actual_row, expected_row) in enumerate(zip(actual, expected), 1):
        for field in FIELDS:
            require(actual_row[field] == expected_row[field],
                    f"record {index}: {field} differs from the pinned KAT")
            compared += 1
    return compared


def parse_call_summary(stderr: bytes) -> dict[str, int]:
    expected = (b"ASCON_HOST_PREFLIGHT PASS cases=1089 encryptions=1089 "
                b"decryptions=2178\n")
    require(stderr == expected,
            "Host wrapper did not report the exact checked crypto API call counts")
    return dict(cases=1089, encryptions=1089, decryptions=2178)


def _run(argv: list[str], cwd: Path, timeout: int = 300) -> dict:
    started = time.perf_counter()
    try:
        completed = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False)
        returncode, stdout, stderr, timed_out = (completed.returncode,
            completed.stdout, completed.stderr, False)
    except subprocess.TimeoutExpired as error:
        returncode, stdout, stderr, timed_out = (None, error.stdout or b"",
            error.stderr or b"", True)
    elapsed = time.perf_counter() - started
    return dict(argv=argv, cwd=str(cwd), returncode=returncode,
        stdout=stdout, stderr=stderr, timed_out=timed_out,
        monotonic_elapsed_seconds=elapsed)


def _write_command(output: Path, stem: str, record: dict) -> dict:
    (output / f"{stem}.stdout").write_bytes(record.pop("stdout"))
    (output / f"{stem}.stderr").write_bytes(record.pop("stderr"))
    return record


def _seal_manifest(output: Path) -> None:
    entries = {p.relative_to(output).as_posix(): c.sha(p)
        for p in sorted(output.rglob("*")) if p.is_file() and
        p.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output / "manifest.json", entries)


def preflight(output: Path, cc: str = "cc") -> dict:
    output = output.resolve()
    require(output.is_relative_to(ROOT) and not output.exists() and
            not output.is_relative_to(ROOT / "benchmarks/ascon"),
            "A fresh repository-local results directory is required")
    source, copy, source_manifest_sha = verify_source_copy()
    source_hashes = bindings()
    compiler = shutil.which(cc)
    require(compiler is not None, f"Host C compiler not found: {cc}")
    version = subprocess.run([compiler, "--version"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(version.returncode == 0, "Host compiler version query failed")

    output.mkdir(parents=True)
    build_dir = output / "build"
    build_dir.mkdir()
    binary = build_dir / "ascon128v13-host-preflight"
    wrapper = ROOT / WRAPPER
    reference = ROOT / REFDIR
    api_header = ROOT / TESTDIR / "crypto_aead.h"
    aead_c = reference / "aead.c"
    compile_argv = [compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I", str(reference), "-I", str(api_header.parent), str(wrapper), str(aead_c),
        "-o", str(binary)]
    protocol = dict(schema="isaforge-ascon-v13-host-preflight-protocol-v1",
        status="frozen_host_only_preflight_no_target_authorization",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        upstream=dict(repository="https://github.com/ascon/ascon-c", tag="v1.3.0",
            commit=UPSTREAM_COMMIT, source_manifest_sha256=source_manifest_sha,
            copy_manifest_sha256=c.sha(ROOT / COPY_MANIFEST)),
        source_bindings=source_hashes,
        wrapper_negative_controls=["encrypt failure", "ciphertext length mismatch",
            "valid-ciphertext decrypt failure", "recovered-length mismatch",
            "plaintext mismatch", "accepted tampered ciphertext"],
        original_pairs=dict(message_length_inclusive=[0, 32],
            associated_data_length_inclusive=[0, 32], loop_order="message then associated data",
            record_count=EXPECTED_CASES),
        checks=dict(encryptions=EXPECTED_CASES, valid_decryptions=EXPECTED_CASES,
            tamper_rejection_decryptions=EXPECTED_CASES, secret_nonce_argument=None,
            byte_initialization="key/nonce/message/associated-data byte i equals i",
            full_kat_field_comparison=True, full_serialized_byte_comparison=True),
        buffer_bytes=dict(message=32, associated_data=32, recovered=32,
            ciphertext=48, key=16, nonce=16),
        host_compiler=dict(path=compiler, version=version.stdout.decode("utf-8", "replace")),
        host_platform=platform.platform(), host_machine=platform.machine(),
        compile_argv=compile_argv, compiler_cwd=str(ROOT),
        candidate_dispatch_enabled=False, target_compile=False, target_jobs=0,
        native_jobs=0, new_measurements=0, target_labels=0,
        area_cap_lut4=64, target_clock_mhz=12.0,
        selection_pool_size_gate=12, target_opportunity_gate=dict(cycle_reduction=0.005,
            minimum_timed_replacements=10), model_fit=False,
        source_manifest_entry_count=len(source["files"]),
        source_copy_exact_byte_count=sum(row["bytes"] for row in copy["files"].values()))
    c.seal(output / "protocol.json", protocol)
    c.seal(output / "source-manifest.json", source_hashes)

    report = dict(schema="isaforge-ascon-v13-host-preflight-result-v1",
        protocol_sha256=c.sha(output / "protocol.json"), status="started",
        output=output.relative_to(ROOT).as_posix(), upstream_commit=UPSTREAM_COMMIT,
        source_manifest_sha256=source_manifest_sha,
        source_copy_file_count=len(copy["files"]), native_jobs=0, target_labels=0)
    try:
        compilation = _run(compile_argv, ROOT)
        compilation_public = _write_command(output, "compile", compilation)
        c.seal(output / "compile.json", compilation_public)
        require(compilation_public["returncode"] == 0 and not compilation_public["timed_out"],
                "Host adapter compilation failed; see compile stderr")

        run_argv = [str(binary)]
        execution = _run(run_argv, ROOT, timeout=300)
        stdout = execution.pop("stdout")
        stderr = execution.pop("stderr")
        (output / "generated-kat.txt").write_bytes(stdout)
        (output / "run.stderr").write_bytes(stderr)
        c.seal(output / "run.json", execution)
        require(execution["returncode"] == 0 and not execution["timed_out"],
                "Host wrapper failed one or more generator/verifier checks")

        expected_raw = (ROOT / KAT).read_bytes()
        generated = parse_kat(stdout)
        expected = parse_kat(expected_raw)
        observed_calls = parse_call_summary(stderr)
        counts = validate_record_inputs(expected)
        validate_record_inputs(generated)
        compared = compare_records(generated, expected)
        require(stdout == expected_raw,
                "Generated KAT serialization differs byte-for-byte from pinned oracle")
        report.update(status="passed", wrapper_exit_status=execution["returncode"],
            records=counts["records"], encryptions=counts["encryptions"],
            valid_decryptions=counts["valid_decryptions"],
            tamper_rejection_decryptions=counts["tamper_rejection_decryptions"],
            total_decryptions=counts["total_decryptions"],
            observed_api_call_counts=observed_calls,
            field_values_compared=compared,
            ciphertext_bytes_compared=counts["ciphertext_bytes_compared"],
            generated_bytes=len(stdout), expected_bytes=len(expected_raw),
            generated_kat_sha256=c.sha(output / "generated-kat.txt"),
            expected_kat_sha256=c.sha(ROOT / KAT),
            full_serialized_byte_equality=True,
            compile_monotonic_seconds=compilation_public["monotonic_elapsed_seconds"],
            run_monotonic_seconds=execution["monotonic_elapsed_seconds"],
            target_qualification="not_authorized_or_attempted",
            scientific_scope="correctness/readiness evidence only; not a measured speedup label")
    except Exception as error:
        report.update(status="failed", failure=repr(error),
            partial_generated_bytes=(output / "generated-kat.txt").stat().st_size
                if (output / "generated-kat.txt").exists() else None,
            target_qualification="not_authorized_or_attempted")
    finally:
        c.seal(output / "result.json", report)
        _seal_manifest(output)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"),
        help="host C compiler (default: CC environment variable or cc)")
    args = parser.parse_args(argv)
    report = preflight(args.output, args.cc)
    print(json.dumps({key: report.get(key) for key in
        ("status", "records", "encryptions", "total_decryptions", "failure",
         "native_jobs", "target_labels", "output")}, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
