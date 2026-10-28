"""Compare pinned nanocobs against a small paper-derived host oracle.

This is an untimed, host-only audit of the original <=12-byte fixed vectors.
It does not qualify general COBS inputs or provide target evidence.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "results/2026-10-28-nanocobs-source-preflight-r1"
PIN_PATH = PREFLIGHT / "source-pin.json"
UPSTREAM = PREFLIGHT / "inputs/upstream"
SOURCE_REL = "inputs/upstream/cobs.c"
HEADER_REL = "inputs/upstream/cobs.h"
SOURCE_URL = "https://www.stuartcheshire.org/papers/COBSforToN/"
MAX_PAYLOAD = 12
PAYLOAD_LIMITATION = "This audit covers only the pinned probe's <=12-byte payloads."
SUCCESS = 0
PINNED_COMMIT = "8d47d35ebe81c7caecc2b8954b1355d223ecabcb"
PINNED_HASHES = {
    SOURCE_REL: "7cc86cb168a76e153c202b330824787f6daa1cb7734e9030fc10da8ee1d88aa9",
    HEADER_REL: "9923b13fb8d3f3d7d3000290670fdc099d1cb0af9ff9fe65cac82514842f8745",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_sources() -> dict[str, Path]:
    pins = json.loads(PIN_PATH.read_text())
    records = pins.get("inputs", {})
    if pins.get("repository") != "https://github.com/charlesnicholson/nanocobs" or \
            pins.get("commit") != PINNED_COMMIT:
        raise ValueError("source pin identity does not match the reviewed commit")
    paths = {rel: PREFLIGHT / rel for rel in (SOURCE_REL, HEADER_REL)}
    for rel, path in paths.items():
        expected = PINNED_HASHES[rel]
        if records.get(rel) != expected or not path.is_file() or sha256(path) != expected:
            raise ValueError(f"pinned source hash mismatch: {rel}")
    return paths


def fixed_payloads() -> list[tuple[str, bytes]]:
    payloads: list[tuple[str, bytes]] = []
    for length in range(MAX_PAYLOAD + 1):
        for mask in range(1 << length):
            payloads.append((f"binary-n{length}-m{mask}", bytes(
                1 if (mask >> index) & 1 else 0 for index in range(length))))
    for length in range(1, MAX_PAYLOAD + 1):
        for fill, value in (("zero", 0), ("data", 0x41)):
            payloads.append((f"run-{fill}-n{length}", bytes([value]) * length))
    if len(payloads) != 8215:
        raise AssertionError("fixed-vector count changed")
    return payloads


def encode_oracle(payload: bytes) -> bytes:
    """COBS code-byte/zero-run encoder, restricted to short fixed payloads."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(PAYLOAD_LIMITATION)
    encoded = bytearray([0])  # code-byte placeholder
    code_index = 0
    code = 1
    for value in payload:
        if value == 0:
            encoded[code_index] = code
            code_index = len(encoded)
            encoded.append(0)
            code = 1
        else:
            encoded.append(value)
            code += 1
    encoded[code_index] = code
    encoded.append(0)  # frame delimiter
    return bytes(encoded)


def decode_oracle(frame: bytes) -> tuple[bytes, int]:
    """Decode one short COBS frame; return payload and bytes consumed."""
    if len(frame) < 2 or frame[-1] != 0:
        raise ValueError("frame must include terminal zero delimiter")
    body = frame[:-1]
    if 0 in body:
        raise ValueError("encoded body contains zero")
    decoded = bytearray()
    offset = 0
    while offset < len(body):
        code = body[offset]
        if code == 0:
            raise ValueError("zero code byte")
        end = offset + code
        if end > len(body):
            raise ValueError("code exceeds frame")
        decoded.extend(body[offset + 1:min(end, len(body))])
        offset = end
        if code != 0xFF and offset < len(body):
            decoded.append(0)
    return bytes(decoded), len(frame)


def ctypes_api(library_path: Path):
    library = ctypes.CDLL(str(library_path))
    byte_ptr = ctypes.POINTER(ctypes.c_ubyte)
    size_ptr = ctypes.POINTER(ctypes.c_size_t)
    library.cobs_encode.argtypes = [byte_ptr, ctypes.c_size_t, byte_ptr,
                                    ctypes.c_size_t, size_ptr]
    library.cobs_encode.restype = ctypes.c_int
    library.cobs_decode.argtypes = [byte_ptr, ctypes.c_size_t, byte_ptr,
                                    ctypes.c_size_t, size_ptr, size_ptr]
    library.cobs_decode.restype = ctypes.c_int
    return library


def c_array(data: bytes):
    # Keep non-null source storage even for the empty-payload API case.
    return (ctypes.c_ubyte * max(1, len(data)))(*(data or b"\0"))


def audit_payload(library, name: str, payload: bytes) -> dict:
    expected_frame = encode_oracle(payload)
    capacity = len(expected_frame) + 8
    source = c_array(payload)
    output = (ctypes.c_ubyte * capacity)(*([0xA5] * capacity))
    output_length = ctypes.c_size_t(0xBAD)
    status = library.cobs_encode(source, len(payload), output, capacity,
                                 ctypes.byref(output_length))
    if status != SUCCESS:
        raise AssertionError(f"{name}: encoder status {status}")
    actual_frame = bytes(output[:output_length.value])
    if actual_frame != expected_frame:
        raise AssertionError(f"{name}: encoded bytes differ from independent oracle")
    if bytes(output[output_length.value:]) != bytes([0xA5]) * (capacity - output_length.value):
        raise AssertionError(f"{name}: encoder changed bytes past reported output")
    if actual_frame[-1] != 0 or 0 in actual_frame[:-1]:
        raise AssertionError(f"{name}: invalid delimiter/body")
    # For this <254-byte scope, the COBS body is at most payload + one code byte;
    # the trailing zero delimiter is framing and is counted separately.
    if len(actual_frame) - 1 > len(payload) + 1:
        raise AssertionError(f"{name}: COBS body exceeds the paper's one-byte bound")

    expected_decoded, expected_consumed = decode_oracle(expected_frame)
    decoded = (ctypes.c_ubyte * (MAX_PAYLOAD + 8))(*([0xA5] * (MAX_PAYLOAD + 8)))
    decoded_length = ctypes.c_size_t(0xBAD)
    consumed = ctypes.c_size_t(0xBAD)
    frame_array = c_array(actual_frame)
    decode_status = library.cobs_decode(frame_array, len(actual_frame), decoded,
                                        MAX_PAYLOAD + 8,
                                        ctypes.byref(decoded_length),
                                        ctypes.byref(consumed))
    if decode_status != SUCCESS:
        raise AssertionError(f"{name}: decoder status {decode_status}")
    actual_decoded = bytes(decoded[:decoded_length.value])
    if (actual_decoded != expected_decoded or actual_decoded != payload or
            decoded_length.value != len(payload) or consumed.value != expected_consumed):
        raise AssertionError(f"{name}: independent decode/consumption mismatch")
    if bytes(decoded[decoded_length.value:]) != bytes([0xA5]) * (
            len(decoded) - decoded_length.value):
        raise AssertionError(f"{name}: decoder changed bytes past reported output")
    return {"name": name, "payload_hex": payload.hex(),
            "encoded_hex": actual_frame.hex(), "decoded_hex": actual_decoded.hex(),
            "encoded_length": len(actual_frame), "consumed": consumed.value}


def run_audit(output: Path, clang: str = "clang", timeout: int = 30) -> dict:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"fresh output directory required: {output}")
    output.mkdir(parents=True)
    try:
        return _run_audit(output, clang, timeout)
    except BaseException as error:
        failure = {"schema": "nanocobs-fixed-independent-host-audit-failure-v1",
                   "created_at_utc": datetime.now(timezone.utc).isoformat(),
                   "status": "failed", "error": repr(error),
                   "pinned_commit": PINNED_COMMIT,
                   "expected_source_sha256": PINNED_HASHES}
        (output / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def _run_audit(output: Path, clang: str, timeout: int) -> dict:
    sources = pinned_sources()
    compiler_path = Path(shutil.which(clang) or clang).resolve()
    if not compiler_path.is_file():
        raise FileNotFoundError(f"clang executable not found: {clang}")
    version = subprocess.run([str(compiler_path), "--version"], capture_output=True,
                             text=True, timeout=min(timeout, 10), check=False)
    if version.returncode != 0:
        raise RuntimeError("clang --version failed")
    lib_path = output / "libnanocobs_host.so"
    command = [str(compiler_path), "-shared", "-fPIC", "-Os", "-DCOBS_SWAR_WORD_BITS=32",
               "-I", str(UPSTREAM), str(sources[SOURCE_REL]), "-o", str(lib_path)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=timeout, check=False)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        completed = error
        timed_out = True
    log = {"compiler_path": str(compiler_path),
           "compiler_sha256": sha256(compiler_path),
           "compiler_version": version.stdout.strip(),
           "compiler_version_stderr": version.stderr.strip(),
           "argv": command, "timeout_seconds": timeout, "timed_out": timed_out,
           "returncode": None if timed_out else completed.returncode,
           "stdout": (completed.stdout or "") if isinstance(completed.stdout, str) else "",
           "stderr": (completed.stderr or "") if isinstance(completed.stderr, str) else ""}
    (output / "compiler.json").write_text(json.dumps(log, indent=2) + "\n")
    if timed_out or completed.returncode != 0 or not lib_path.is_file():
        raise RuntimeError("local clang host build failed; see compiler.json")
    library = ctypes_api(lib_path)
    records = [audit_payload(library, name, payload)
               for name, payload in fixed_payloads()]
    payload_blob = b"".join(len(payload).to_bytes(2, "little") + payload
                            for _, payload in fixed_payloads())
    output_blob = b"".join(bytes.fromhex(item["encoded_hex"]) for item in records)
    report = {
        "schema": "nanocobs-fixed-independent-host-audit-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "host-only; untimed audit; no target calls or candidate labels",
        "oracle": "Independent short-frame COBS code-byte/zero-run encoder and decoder",
        "primary_specification": SOURCE_URL,
        "max_payload_bytes": MAX_PAYLOAD,
        "limitation": PAYLOAD_LIMITATION,
        "source_pin": json.loads(PIN_PATH.read_text()),
        "verified_source_sha256": {rel: sha256(path) for rel, path in sources.items()},
        "compiler": log,
        "compiler_artifact_sha256": sha256(lib_path),
        "payload_count": len(records), "passed_count": len(records),
        "payload_vectors_sha256": hashlib.sha256(payload_blob).hexdigest(),
        "encoded_outputs_sha256": hashlib.sha256(output_blob).hexdigest(),
        "records": records,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = {p.relative_to(output).as_posix(): sha256(p)
                for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="fresh directory for compiler and audit evidence")
    parser.add_argument("--clang", default=shutil.which("clang") or "clang")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    report = run_audit(args.output, args.clang, args.timeout)
    print(json.dumps({"payload_count": report["payload_count"],
                      "passed_count": report["passed_count"],
                      "report": str(args.output / "report.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
