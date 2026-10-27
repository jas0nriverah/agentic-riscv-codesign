"""Baseline-only Ascon v1.3.0 transfer qualification on guarded PicoRV32."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

from . import budgeted_selection as b
from . import codesign as c
from . import guarded_workload as g
from . import campaign_evidence as evidence
from .speedup_corpus import family
from scripts import audit_ascon_source_family as source_family
from scripts import build_ascon128_v13_target_adapter as target_builder
from scripts import preflight_ascon128_v13 as host_preflight

SOURCE = "isaforge/ascon_workload.py"
QUALIFIER = "scripts/qualify_ascon.py"
WORKLOAD = "ascon128v13"
GROUP = "ascon128v13-kat-v13"
PROGRAM = "benchmarks/ascon/ascon128v13_isaforge.c"
SOURCE_MANIFEST = "benchmarks/ascon/ASCON128_V13_SOURCES.json"
COPY_MANIFEST = "benchmarks/ascon/ASCON128_V13_COPY_MANIFEST.json"
TARGET_MANIFEST = "benchmarks/ascon/ASCON128_V13_TARGET_ADAPTER_MANIFEST.json"
TARGET_CONTRACT = "docs/ascon-target-adapter-contract-2026-10-27.md"
SOURCE_FAMILY_REPORT = "results/2026-10-27-ascon-source-family-audit/report.json"
HOST_RESULT = "results/2026-10-26-ascon-host-preflight-r3/result.json"
HISTORY = "results/2026-10-26-lift-selection-corpus/corpus.json"
REFERENCE = "generated/codesign-crc32-2026-10-19-r1"
POOL_SIZE = 12
EXPECTED_RESULT_U32 = 0x06CF04E8
PARTITION = g.q.partition_spec(6400, 6528)
NATIVE_LIMITS = dict(commands=480, seconds=3600, command_seconds=180,
                     workers=1, build_workers=2, candidate_attempts=1)

_copy_manifest = c.unseal(c.ROOT / COPY_MANIFEST)
UPSTREAM_FILES = tuple(sorted(row["repository_path"]
    for row in _copy_manifest["files"].values()))

PROTOCOL = dict(
    schema="isaforge-ascon-v13-baseline-only-v1",
    workload_group=GROUP,
    pool_size=POOL_SIZE,
    minimum_calibrated_cycle_reduction=0.005,
    minimum_timed_replacements=10,
    joint_gate="At least one same candidate meets both public numeric thresholds.",
    unchanged_input=True,
    unchanged_algorithm=True,
    unchanged_upstream_source=True,
    source_change="Deterministic single-translation-unit composition plus a freestanding KAT stress-loop ABI adapter; upstream crypto implementation body preserved.",
    correctness=("All 1,089 ordered length pairs, exact host-loop KAT equality, target encryption/decryption lengths, "
                 "round-trip plaintext, first-byte tamper rejection, call counts, and KAT-derived 32-bit ciphertext fingerprint."),
    target_bytewise_kat_comparison=False,
    target_kat_fingerprint_fnv32="06cf04e8",
    original_input="mlen=0..32 outer and adlen=0..32 inner, inclusive; key/nonce/message/AD bytes initialized to their indices.",
    compiler_flags=list(g.q.bounded.compact.FLAGS),
    isa="rv32i_zicsr",
    abi="ilp32",
    optimization="-Os",
    clock_mhz=12,
    route_seeds=[1, 2, 3],
    memory_partition=PARTITION,
    candidate_dispatch_enabled=False,
    target_candidate_attempts=0,
    candidate_dispatch="Disabled for baseline-only qualification.",
    model_fit_during_qualification=False,
    scientific_scope="Same-domain cryptography transfer/readiness evidence; not an independent confirmatory family.",
)

RAW_PUBLIC = evidence._public
GATE_SOURCES = tuple(dict.fromkeys((
    SOURCE, QUALIFIER, "scripts/reproduce_codesign.py",
    "isaforge/observed_command.py", "scripts/build_ascon128_v13_target_adapter.py",
    "scripts/build_ascon128_v13_target_manifest.py",
    "scripts/preflight_ascon128_v13.py", "scripts/audit_ascon_source_family.py",
    PROGRAM, SOURCE_MANIFEST, COPY_MANIFEST, TARGET_MANIFEST,
    "benchmarks/ascon/ascon128v13_host_preflight.c",
    "tests/ascon_fake_crypto_api.c", "tests/test_ascon_preflight.py",
    "tests/test_ascon_target_adapter.py", "tests/test_ascon_workload.py",
    "docs/ascon-adapter-contract-2026-10-26.md", TARGET_CONTRACT,
    "docs/ascon-source-family-audit-2026-10-27.md",
    SOURCE_FAMILY_REPORT, HOST_RESULT,
    g.SOURCE, g.QUALIFIED_SOURCE, g.guard.SOURCE, g.attempts.SOURCE,
    g.EVIDENCE_SOURCE, *g.AUTHENTICATION_SOURCES,
    "isaforge/bounded_workload.py", "isaforge/partitioned_workload.py",
    "isaforge/workload_experiment.py", "isaforge/assembly_lowering.py",
    "isaforge/relocation_guard.py", "isaforge/latency_features.py",
    *b.SOURCES, "scripts/blind_campaign.py",
    "hardware/embench_firmware.c", "hardware/embench_memory.c",
    *UPSTREAM_FILES,
)))


def verify_source_pins() -> dict:
    source, copy, source_sha = host_preflight.verify_source_copy()
    c.require(target_builder.build_source() == (c.ROOT / PROGRAM).read_bytes(),
              "Generated Ascon target translation unit differs from pinned sources")
    target = c.unseal(c.ROOT / TARGET_MANIFEST)
    c.require(target.get("schema") == "isaforge-ascon-v13-target-adapter-manifest-v1" and
              target.get("upstream", {}).get("commit") == source["commit"] and
              target.get("target_translation_unit") == PROGRAM and
              target.get("target_translation_unit_sha256") == c.sha(c.ROOT / PROGRAM) and
              target.get("source_bindings", {}).get(
                  "scripts/build_ascon128_v13_target_adapter.py") ==
                  c.sha(c.ROOT / "scripts/build_ascon128_v13_target_adapter.py"),
              "Ascon target adapter manifest differs from the generated program")
    for name, digest in target.get("source_bindings", {}).items():
        c.require(c.sha(c.ROOT / name) == digest,
                  "Ascon target adapter binding changed: " + name)
    host = c.unseal(c.ROOT / HOST_RESULT)
    c.require(host.get("status") == "passed" and
              host.get("upstream_commit") == source["commit"] and
              host.get("full_serialized_byte_equality") is True and
              host.get("records") == 1089 and host.get("encryptions") == 1089 and
              host.get("total_decryptions") == 2178 and
              host.get("ciphertext_bytes_compared") == 34848 and
              host.get("target_labels") == 0,
              "Passing exact host KAT checkpoint required")
    family_report = source_family.build_report()
    c.require(c.unseal(c.ROOT / SOURCE_FAMILY_REPORT) == family_report and
              family_report["eligibility"]["independent_confirmatory_family"] is False and
              family_report["eligibility"]["target_labels"] == 0,
              "Pinned pre-target source-family audit differs")
    return dict(source_manifest_sha256=source_sha,
        copy_manifest_sha256=c.sha(c.ROOT / COPY_MANIFEST),
        target_manifest_sha256=c.sha(c.ROOT / TARGET_MANIFEST),
        target_adapter_sha256=c.sha(c.ROOT / PROGRAM),
        source_family_audit_sha256=c.sha(c.ROOT / SOURCE_FAMILY_REPORT),
        host_result_sha256=c.sha(c.ROOT / HOST_RESULT))


def upstream_record() -> dict:
    pins = verify_source_pins()
    source = json.loads((c.ROOT / SOURCE_MANIFEST).read_text())
    return dict(suite=source["suite"], tag=source["tag"], commit=source["commit"],
        repository="https://github.com/ascon/ascon-c",
        source_manifest=SOURCE_MANIFEST,
        source_manifest_sha256=pins["source_manifest_sha256"],
        copy_manifest=COPY_MANIFEST,
        copy_manifest_sha256=pins["copy_manifest_sha256"],
        target_manifest=TARGET_MANIFEST,
        target_manifest_sha256=pins["target_manifest_sha256"],
        target_adapter=PROGRAM,
        target_adapter_sha256=pins["target_adapter_sha256"],
        source_family_audit=SOURCE_FAMILY_REPORT,
        source_family_audit_sha256=pins["source_family_audit_sha256"],
        host_kat_result=HOST_RESULT,
        host_kat_result_sha256=pins["host_result_sha256"],
        cases=1089, encryptions=1089, decryptions=2178,
        ciphertext_bytes=34848, target_fingerprint="fnv1a32:06cf04e8",
        target_bytewise_kat_comparison=False)


def public_projection(root, plan, discovery, baseline, calibration):
    rows = RAW_PUBLIC(root, plan, discovery, baseline, calibration)
    for row in rows:
        c.require(row["benchmark"] == "embench-" + WORKLOAD + ":" + plan["context_id"],
                  "Unexpected Ascon public workload projection")
        row["benchmark"] = GROUP + ":" + plan["context_id"]
    return rows


@contextmanager
def registration():
    """Register this exact Ascon workload, then restore all shared globals."""
    q, bounded, campaign = g.q, g.q.bounded, g.q.bounded.campaign
    previous = (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
        q.SOURCE, q.WORKLOADS, q.POOL_SIZE,
        bounded.SOURCE, bounded.WORKLOADS, bounded.POOL_SIZE,
        campaign.WORKLOADS, campaign.POOL_SIZE, evidence._public)
    mapping = {WORKLOAD: "../../ascon/ascon128v13_isaforge.c"}
    g.SOURCE = SOURCE
    g.WORKLOADS = dict(mapping)
    g.POOL_SIZE = q.POOL_SIZE = bounded.POOL_SIZE = campaign.POOL_SIZE = POOL_SIZE
    g.NATIVE_LIMITS = dict(NATIVE_LIMITS)
    q.WORKLOADS = bounded.WORKLOADS = campaign.WORKLOADS = dict(mapping)
    q.SOURCE = "isaforge/qualified_workload.py"
    bounded.SOURCE = "isaforge/bounded_workload.py"
    evidence._public = public_projection
    try:
        yield
    finally:
        (g.SOURCE, g.WORKLOADS, g.POOL_SIZE, g.NATIVE_LIMITS,
         q.SOURCE, q.WORKLOADS, q.POOL_SIZE,
         bounded.SOURCE, bounded.WORKLOADS, bounded.POOL_SIZE,
         campaign.WORKLOADS, campaign.POOL_SIZE, evidence._public) = previous


def check_plan(plan):
    verify_source_pins()
    with registration():
        g.check_plan(plan)
    c.require(plan.get("workload") == WORKLOAD and
              plan.get("workload_group") == GROUP and
              plan.get("pool_size") == POOL_SIZE and
              plan.get("memory_partition") == PARTITION and
              plan.get("native_limits") == NATIVE_LIMITS and
              plan.get("opportunity_source_protocol") == PROTOCOL and
              plan.get("upstream") == upstream_record(),
              "Fixed pinned Ascon target context required")
    c.require(plan.get("compiler_flags") == list(g.q.bounded.compact.FLAGS) and
              plan.get("configuration", {}).get("frequency_mhz") == 12.0 and
              plan.get("configuration", {}).get("route_seeds") == [1, 2, 3],
              "Ascon compiler, frequency, or route protocol changed")
    c.require(plan.get("inputs", {}).get("program.c") == c.sha(c.ROOT / PROGRAM),
              "Ascon target adapter input changed")
    for name in GATE_SOURCES:
        c.require(plan.get("source_bindings", {}).get(name) == c.sha(c.ROOT / name),
                  "Ascon qualification source binding differs: " + name)
    c.require(c.digest({key: value for key, value in plan.items() if key != "context_id"}) ==
              plan.get("context_id"), "Invalid Ascon native context identity")


def require_zero_candidates(root):
    root = Path(root)
    ledger = list((root / "attempt-ledger").glob("candidate_*.json"))
    artifacts = list((root / "measurements").glob("candidate_*"))
    c.require(not ledger and not artifacts,
              "Ascon baseline qualification requires zero candidate attempts")


def validate_inputs(root):
    root = Path(root)
    require_zero_candidates(root)
    plan = c.unseal(root / "plan.json")
    check_plan(plan)
    c.require((root / "inputs/embench_firmware.c").read_bytes() ==
              (c.ROOT / "hardware/embench_firmware.c").read_bytes(),
              "Generic benchmark harness changed")
    for name, digest in plan["inputs"].items():
        c.require(c.sha(root / "inputs" / name) == digest,
                  "Bound Ascon input changed: " + name)
    c.require(c.sha(root / "inputs/program.c") == c.sha(c.ROOT / PROGRAM),
              "Compiled Ascon translation unit differs from its pinned adapter")
    return plan


def prepare(reference, output):
    pins = verify_source_pins()
    output = Path(output)
    c.require(not output.exists(), "Fresh Ascon qualification root required")
    with registration():
        plan = g.prepare(reference, output, WORKLOAD, POOL_SIZE,
            program_limit=PARTITION["program_limit"], stack_floor=PARTITION["stack_floor"])
    plan.pop("context_id")
    plan["source_bindings"] = {
        str((c.ROOT / name).resolve().relative_to(c.ROOT)): digest
        for name, digest in plan["source_bindings"].items()}
    plan.update(upstream=upstream_record(), workload_group=GROUP,
        opportunity_source_protocol=PROTOCOL,
        runtime_support=("One generated freestanding RV32 translation unit containing the pinned Ascon v1.3.0 "
                         "reference implementation and the original 1,089-case length-pair stress loop."),
        output_check=PROTOCOL["correctness"],
        harness_derivation=("Unchanged hardware/embench_firmware.c cycle/profile markers; the complete workload "
                           "runs in benchmark(), and the count/fingerprint verifier runs after timing."),
        selection_evidence_scope=("Baseline-only public candidate opportunity check; no candidate measurements, "
                                  "model fitting, or speedup labels."),
        context_amendment=("Original guarded RV32I_zicsr/ILP32--Os, existing PCPI interface, integrated 8 KiB SoC, "
                           "and 6400/6528 memory partition retained."),
        source_family_scope="Same-domain crypto transfer; not independent confirmation.",
        target_correctness_limitation="No bytewise RV32 KAT comparison; target uses a 32-bit fingerprint plus runtime checks.")
    for name in GATE_SOURCES:
        plan["source_bindings"][name] = c.sha(c.ROOT / name)
        destination = output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / name, destination)
    plan["inputs"] = {path.name: c.sha(path) for path in (output / "inputs").iterdir()}
    plan["source_snapshot_sha256"] = c.digest({name: plan["source_bindings"][name]
        for name in sorted(plan["source_bindings"])})
    plan["context_id"] = c.digest(plan)
    c.seal(output / "plan.json", plan)
    validate_inputs(output)
    return plan


def opportunity_gate(public):
    public = b.public_rows(public)
    c.require(len(public) == POOL_SIZE, "Exactly twelve public formulas required")
    passing = [row["candidate_id"] for row in public
        if row["latency_features"]["estimated_cycle_reduction"] >=
           PROTOCOL["minimum_calibrated_cycle_reduction"] and
           b.occurrence_count(row) >= PROTOCOL["minimum_timed_replacements"]]
    return dict(schema=PROTOCOL["schema"] + "-gate", protocol=PROTOCOL,
        passed=bool(passing), qualifying_candidate_ids=passing,
        public_digest=c.digest(public),
        maximum_public_cycle_reduction=max(
            row["latency_features"]["estimated_cycle_reduction"] for row in public),
        maximum_timed_replacements=max(b.occurrence_count(row) for row in public),
        target_candidate_attempts=0, measured_candidate_labels_used=False)


def exact_candidate_family_audit(public):
    """Compare the emitted Ascon formula families to authenticated prior pools."""
    public = b.public_rows(public)
    prior = source_family.build_report()
    prior_sets = {name: set(row["formula_families"])
                  for name, row in prior["reference_pools"].items()}
    candidates = []
    intersections = {name: [] for name in sorted(prior_sets)}
    for row in public:
        candidate_family = family(row["formula"])
        overlap = sorted(name for name, values in prior_sets.items()
                         if candidate_family in values)
        item = dict(candidate_id=row["candidate_id"], formula=row["formula"],
            formula_family=candidate_family, exact_prior_family_overlap=overlap,
            eligible_for_unseen_formula_family_training=not overlap)
        candidates.append(item)
        for name in overlap:
            intersections[name].append(candidate_family)
    return dict(schema="isaforge-ascon-target-formula-family-audit-v1",
        source_family_report_sha256=c.sha(c.ROOT / SOURCE_FAMILY_REPORT),
        workload_group=GROUP, public_candidate_pool_sha256=c.digest(public),
        candidate_count=len(candidates),
        unique_target_formula_family_count=len({row["formula_family"] for row in candidates}),
        candidates=candidates,
        exact_intersections_by_reference_pool={name: sorted(set(values))
            for name, values in intersections.items()},
        target_outcomes_read=False, target_labels=0, model_fits=0,
        same_domain_transfer=True, independent_confirmatory_family=False)


def discovery_public(root):
    root = Path(root)
    plan = validate_inputs(root)
    with registration():
        discovery = g.authenticate_discovery(root)
        c.require(discovery["baseline_performance"]["benchmark_result_u32"] ==
                  EXPECTED_RESULT_U32,
                  "Baseline profile fingerprint differs from the pinned Ascon KAT")
        calibration = evidence._calibration(root)
        rows = public_projection(root, plan, discovery,
            {"performance": discovery["baseline_performance"]}, calibration)
    public = b.public_rows(rows)
    family_audit = exact_candidate_family_audit(public)
    audit_path = root / "target-formula-family-audit.json"
    if audit_path.exists():
        c.require(c.unseal(audit_path) == family_audit,
                  "Ascon compiler-derived family audit changed")
    else:
        c.seal(audit_path, family_audit)
    return public


def opportunity(root):
    root = Path(root)
    c.require(not (root / "opportunity.json").exists(),
              "Preserve prior Ascon opportunity result")
    public = discovery_public(root)
    result = opportunity_gate(public)
    c.seal(root / "opportunity.json", result)
    c.require(result["passed"], "Ascon public useful-opportunity gate rejected this source")
    return result


def check_opportunity(root):
    root = Path(root)
    recorded = c.unseal(root / "opportunity.json")
    derived = opportunity_gate(discovery_public(root))
    c.require(recorded == derived and derived["passed"],
              "Accepted unchanged Ascon opportunity gate required")
    return recorded


class Evaluator(g.Evaluator):
    def __init__(self, root):
        validate_inputs(root)
        with registration():
            super().__init__(root)

    def discover(self):
        with registration():
            result = super().discover()
        c.require(result["baseline_performance"]["benchmark_result_u32"] ==
                  EXPECTED_RESULT_U32,
                  "Baseline profile fingerprint differs from the pinned Ascon KAT")
        require_zero_candidates(self.root)
        return result

    def measure(self, name):
        c.require(name == "baseline",
                  "Ascon candidate dispatch is disabled during baseline qualification")
        require_zero_candidates(self.root)
        check_opportunity(self.root)
        with registration():
            result = super().measure(name)
        c.require(result["performance"]["benchmark_result_u32"] == EXPECTED_RESULT_U32,
                  "Routed Ascon baseline fingerprint differs from the pinned KAT")
        require_zero_candidates(self.root)
        return result


def baseline_public(root):
    root = Path(root)
    validate_inputs(root)
    check_opportunity(root)
    with registration():
        rows, context, before = g.baseline_public(root)
    before["workload"] = GROUP
    context["workload_group"] = GROUP
    c.require(before["public_sha256"] == c.digest(rows) and
              opportunity_gate(rows) == c.unseal(root / "opportunity.json"),
              "Ascon public discovery and routed-baseline projections differ")
    c.require(rows and rows[0]["latency_features"]["baseline_cycles"] > 0,
              "Ascon public baseline counters missing")
    context["context_transfer"] = (
        "Pinned Ascon v1.3.0 crypto implementation on the guarded RV32I PicoRV32 path; "
        "same-domain cryptography transfer with target KAT fingerprint limitation.")
    return rows, context, before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "discover", "opportunity",
        "baseline", "public", "freeze"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path)
    args = parser.parse_args(argv)
    began, status = time.monotonic(), "interrupted"
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        if args.command == "prepare":
            c.require(args.reference_root is not None, "Preserved reference required")
            result = prepare(args.reference_root, args.root)
        elif args.command == "opportunity":
            result = opportunity(args.root)
        elif args.command == "public":
            rows, context, before = baseline_public(args.root)
            for name, value in (("public.json", rows), ("context.json", context),
                                ("before.json", before)):
                c.seal(args.root / name, value)
            result = dict(context_id=context["context_id"], candidates=len(rows),
                exact_formula_family_overlap=sorted({row["formula_family"] for row in
                    exact_candidate_family_audit(rows)["candidates"]
                    if row["exact_prior_family_overlap"]}))
        else:
            evaluator = Evaluator(args.root)
            try:
                if args.command == "freeze":
                    check_opportunity(args.root)
                    with registration():
                        result = g.attempts.freeze_pool(evaluator,
                            scope="dataset-expansion")
                    require_zero_candidates(args.root)
                elif args.command == "baseline":
                    result = evaluator.measure("baseline")
                else:
                    result = evaluator.discover()
            finally:
                evaluator.runner.lock.close()
        status = "success"
        print(json.dumps(result, indent=2))
    except Exception:
        status = "failed"
        raise
    finally:
        if args.root.exists():
            folder = args.root / "outer-timing"
            folder.mkdir(exist_ok=True)
            sequence = len(list(folder.glob("*.json")))
            c.seal(folder / f"{sequence:03d}-{args.command}.json", dict(
                schema="isaforge-wrapper-outer-time-v1", command=args.command,
                status=status, started_at_utc=stamp,
                duration_seconds=time.monotonic() - began))


if __name__ == "__main__":
    main()
