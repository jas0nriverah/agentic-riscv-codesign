#!/usr/bin/env python3
"""Create or check the authenticated Ascon target-adapter source manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from scripts import build_ascon128_v13_target_adapter as adapter
from scripts import preflight_ascon128_v13 as preflight
from scripts.audit_ascon_source_family import build_report as build_family_report

OUTPUT = ROOT / "benchmarks/ascon/ASCON128_V13_TARGET_ADAPTER_MANIFEST.json"
SOURCE_FAMILY_REPORT = "results/2026-10-27-ascon-source-family-audit/report.json"
HOST_RESULT = "results/2026-10-26-ascon-host-preflight-r3/result.json"
TARGET_HASH = "0x06cf04e8"

BOUND_FILES = (
    "scripts/build_ascon128_v13_target_adapter.py",
    "scripts/build_ascon128_v13_target_manifest.py",
    "scripts/preflight_ascon128_v13.py",
    "scripts/audit_ascon_source_family.py",
    "benchmarks/ascon/ascon128v13_host_preflight.c",
    "benchmarks/ascon/ascon128v13_isaforge.c",
    "benchmarks/ascon/ASCON128_V13_SOURCES.json",
    "benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json",
    "docs/ascon-adapter-contract-2026-10-26.md",
    "docs/ascon-source-family-audit-2026-10-27.md",
    "docs/ascon-target-adapter-contract-2026-10-27.md",
    "tests/ascon_fake_crypto_api.c",
    "tests/test_ascon_preflight.py",
    "tests/test_ascon_target_adapter.py",
    HOST_RESULT,
    SOURCE_FAMILY_REPORT,
)


def build_manifest() -> dict:
    source, copy, source_digest = preflight.verify_source_copy()
    expected_source = adapter.build_source()
    target_path = ROOT / "benchmarks/ascon/ascon128v13_isaforge.c"
    c.require(target_path.read_bytes() == expected_source,
              "Generated Ascon target adapter differs from deterministic source")
    host = c.read(ROOT / HOST_RESULT)
    c.require(host.get("status") == "passed" and
              host.get("full_serialized_byte_equality") is True and
              host.get("records") == 1089 and host.get("ciphertext_bytes_compared") == 34848 and
              host.get("target_labels") == 0,
              "Authenticated host KAT checkpoint required")
    family = build_family_report()
    family_saved = c.read(ROOT / SOURCE_FAMILY_REPORT)
    c.require(family == family_saved and
              family["eligibility"]["independent_confirmatory_family"] is False and
              family["eligibility"]["target_labels"] == 0,
              "Authenticated source-family audit changed")

    bindings = {name: c.sha(ROOT / name) for name in BOUND_FILES}
    for item in copy["files"].values():
        path = item["repository_path"]
        bindings[path] = c.sha(ROOT / path)
    return dict(
        schema="isaforge-ascon-v13-target-adapter-manifest-v1",
        status="target-adapter-source-and-host-loop-verified; no target qualification",
        upstream=dict(repository=source["suite"], tag=source["tag"],
            commit=source["commit"], source_manifest_sha256=source_digest,
            copy_manifest_sha256=c.sha(ROOT / preflight.COPY_MANIFEST),
            exact_byte_copies=True),
        target_translation_unit="benchmarks/ascon/ascon128v13_isaforge.c",
        target_translation_unit_sha256=c.sha(target_path),
        generator="scripts/build_ascon128_v13_target_adapter.py",
        kat_fingerprint=dict(algorithm="FNV-1a-32 over ciphertext bytes in KAT record order",
            value=TARGET_HASH, ciphertext_bytes=34848, source_kat_sha256=source["files"]["known_answer_vectors"]["sha256"]),
        host_loop_evidence=dict(result=HOST_RESULT,
            result_sha256=c.sha(ROOT / HOST_RESULT), exact_serialized_kat_equality=True,
            cases=1089, encryptions=1089, decryptions=2178, target_bytewise_kat_comparison=False),
        source_family_evidence=dict(report=SOURCE_FAMILY_REPORT,
            report_sha256=c.sha(ROOT / SOURCE_FAMILY_REPORT),
            independent_confirmatory_family=False, exact_target_formula_audit="pending discovery"),
        qualification=dict(target_jobs=0, candidate_dispatch_enabled=False,
            candidate_attempts=0, target_labels=0, model_fits=0),
        source_bindings=dict(sorted(bindings.items())),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--replace", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    manifest = build_manifest()
    if args.check:
        c.require(OUTPUT.is_file() and c.unseal(OUTPUT) == manifest,
                  "Ascon target-adapter manifest differs from current pinned sources")
        print(f"verified {OUTPUT.relative_to(ROOT)}")
    elif args.write:
        c.require(not OUTPUT.exists(), "Manifest already exists; use --check or --replace")
        c.seal(OUTPUT, manifest)
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
    else:
        c.seal(OUTPUT, manifest)
        print(f"replaced {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
