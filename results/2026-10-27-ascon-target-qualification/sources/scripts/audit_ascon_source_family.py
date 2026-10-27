"""Hash-check Ascon source motifs against existing public crypto candidate pools.

This is source-level overlap evidence only. It deliberately does not infer an
Ascon target candidate pool or treat shared operations as exact tree aliases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import codesign as c
from isaforge.speedup_corpus import family

SOURCE_MANIFEST = "benchmarks/ascon/ASCON128_V13_SOURCES.json"
COPY_MANIFEST = "benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json"
EXPECTED_SOURCE_MANIFEST_SHA256 = "fd178acbcf69e2bfef9c4a7b1307e6a72e3b49b5e9a38f815e6c2cc9d9c77c5e"
EXPECTED_COPY_MANIFEST_SHA256 = "e895f69681da185a2ccfe6f629399c695eb5ff434611d56da2674c2e85e842e6"
POOL_INPUTS = {
    "aha_compress": (
        "results/2026-10-21-blind-preregistration/targets/beebs-aha-compress/public.json",
        "2501d74d163d3cbca784624d26da024d7c0f61a3f6fd3024b115e895e0f84886",
    ),
    "ndes": (
        "results/2026-10-21-blind-preregistration/targets/beebs-ndes/public.json",
        "9d958b0ae3a97bd21ecfa29e33376ac20d34925e7e92ce11d4f77e2bbc107bb1",
    ),
    "nettle_md5": (
        "results/2026-10-21-blind-preregistration/targets/beebs-nettle-md5/public.json",
        "30e97ee872225aedd1210597bfaef48ac24ecd4d012747f5bc9d8e907f31c53d",
    ),
    "nettle_sha256": (
        "results/2026-10-21-sha256-preregistration/selection/model/public.json",
        "fe2ccfae4013d5f16c4bddb21c8f52ca9691d6d8d9bef546edb2e996ff7dd51d",
    ),
}
ASCON_SOURCE_MOTIFS = {
    "complemented_and": {
        "source": "benchmarks/ascon/upstream/crypto_aead/ascon128v13/ref/round.h:22-26",
        "operation_shape": "x XOR ((NOT y) AND z); the complemented-AND subtree uses two source values",
        "related_existing_candidate_families": ["and(input,xori(input,constant))"],
    },
    "rotate_diffusion": {
        "source": "benchmarks/ascon/upstream/crypto_aead/ascon128v13/ref/round.h:8-9,34-38",
        "operation_shape": "64-bit rotate-right built from shifts and OR, then XOR-combined",
        "related_existing_candidate_families": [
            "xor(input,srli(input,constant))",
            "xor(input,slli(input,constant))",
            "or(input,slli(input,constant))",
        ],
    },
}
TARGET_OUTCOME_FIELDS = {
    "speedup", "cycle_reduction", "cycles", "area_delta_lut4",
    "routed_fmax_min_mhz", "measurement_seconds", "device_fits", "status",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_report() -> dict:
    source_manifest_path = ROOT / SOURCE_MANIFEST
    copy_manifest_path = ROOT / COPY_MANIFEST
    source_digest = sha256(source_manifest_path)
    copy_digest = sha256(copy_manifest_path)
    c.require(source_digest == EXPECTED_SOURCE_MANIFEST_SHA256,
              "Pinned Ascon source manifest changed")
    c.require(copy_digest == EXPECTED_COPY_MANIFEST_SHA256,
              "Pinned Ascon copy manifest changed")
    source_manifest = c.read(source_manifest_path)
    copy_manifest = c.read(copy_manifest_path)
    c.require(source_manifest["commit"] == "b7ca60bbf86479785de08b75aab2425dce4e9e8b" and
              copy_manifest["commit"] == source_manifest["commit"],
              "Pinned Ascon commit mismatch")
    c.require(set(source_manifest["files"]) == set(copy_manifest["files"]),
              "Upstream and copied Ascon file inventories differ")
    copied_files = {}
    for key, row in copy_manifest["files"].items():
        upstream = source_manifest["files"][key]
        c.require(row["sha256"] == upstream["sha256"] and row["bytes"] == upstream["bytes"],
                  "Copied Ascon entry differs from pinned upstream manifest: " + key)
        path = ROOT / row["repository_path"]
        actual = sha256(path)
        c.require(actual == row["sha256"], "Ascon copied source hash mismatch: " + row["repository_path"])
        c.require(path.stat().st_size == row["bytes"],
                  "Ascon copied source size mismatch: " + row["repository_path"])
        copied_files[row["repository_path"]] = actual

    pools = {}
    family_sets = {}
    for workload, (relative, expected_digest) in POOL_INPUTS.items():
        path = ROOT / relative
        actual_digest = sha256(path)
        c.require(actual_digest == expected_digest, "Historical public pool hash mismatch: " + relative)
        rows = c.read(path)
        c.require(isinstance(rows, list) and rows, "Public candidate pool must be a nonempty list")
        families = set()
        for row in rows:
            c.require("candidate_id" in row and "formula" in row,
                      "Public candidate identity and formula required")
            c.require(not (TARGET_OUTCOME_FIELDS & set(row)),
                      "Target outcome field appeared in a public-pool row")
            families.add(family(row["formula"]))
        pools[workload] = dict(path=relative, sha256=actual_digest,
            candidate_count=len(rows), unique_formula_family_count=len(families),
            formula_families=sorted(families))
        family_sets[workload] = families

    exact_pool_intersections = {}
    for index, left in enumerate(sorted(family_sets)):
        for right in sorted(family_sets)[index + 1:]:
            overlap = sorted(family_sets[left] & family_sets[right])
            if overlap:
                exact_pool_intersections[left + "__" + right] = overlap

    motif_presence = {}
    for motif, details in ASCON_SOURCE_MOTIFS.items():
        motif_presence[motif] = {
            "source": details["source"],
            "operation_shape": details["operation_shape"],
            "related_existing_candidate_families": {
                template: sorted(name for name, values in family_sets.items() if template in values)
                for template in details["related_existing_candidate_families"]
            },
        }
    return dict(
        schema="isaforge-ascon-source-family-audit-v1",
        status="source_level_crypto_overlap_confirmed_exact_target_pool_pending",
        audit_script_sha256=sha256(ROOT / "scripts/audit_ascon_source_family.py"),
        ascon=dict(repository="https://github.com/ascon/ascon-c", tag="v1.3.0",
            commit=source_manifest["commit"], source_manifest_sha256=source_digest,
            copy_manifest_sha256=copy_digest, copied_file_count=len(copied_files),
            copied_bytes=sum((ROOT / name).stat().st_size for name in copied_files)),
        reference_pools=pools,
        ascon_source_motifs=motif_presence,
        exact_formula_family_intersections_between_existing_pools=exact_pool_intersections,
        interpretation=(
            "Ascon implements a cryptographic permutation with complemented-AND, XOR, and rotate/shift/OR motifs. "
            "The complemented-AND subtree and rotation-related primitives have exact family-name matches in existing "
            "public crypto candidate pools. This confirms source-level crypto-family overlap, not that an entire Ascon "
            "candidate tree is an alias. The compiler-derived Ascon candidate roster does not exist yet, so exact "
            "candidate-family exclusion cannot be completed before target lowering/discovery."
        ),
        eligibility=dict(independent_confirmatory_family=False,
            same_domain_crypto_transfer_lead=True,
            exact_ascon_candidate_family_audit="pending target candidate extraction",
            target_jobs=0, target_labels=0, model_fits=0, candidate_dispatch_enabled=False),
        limitations=[
            "Source motifs are not target-compiler dataflow graphs; RV32I lowering can change expression trees.",
            "Existing family identities canonicalize operation trees and commutative child order, but do not prove arbitrary bit-vector equivalence.",
            "This audit reads only hash-pinned public candidate features and no target outcomes.",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
        default=ROOT / "results/2026-10-27-ascon-source-family-audit")
    args = parser.parse_args()
    output = args.output.resolve()
    c.require(not output.exists(), "Refusing to overwrite prior evidence; choose a fresh output path")
    report = build_report()
    output.mkdir(parents=True)
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "report.json.sha256").write_text(sha256(report_path) + "\n")
    print(json.dumps(dict(status=report["status"], output=str(output),
        copied_files=report["ascon"]["copied_file_count"],
        crypto_pool_count=len(report["reference_pools"]),
        target_jobs=report["eligibility"]["target_jobs"],
        target_labels=report["eligibility"]["target_labels"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
