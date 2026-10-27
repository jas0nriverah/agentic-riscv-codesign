"""Freeze ISAForge's existing selector models for a label-free Ascon transfer.

This command fits only the already-selected model recipes on authenticated
historical measurements and the public Ascon pool. It never opens candidate
outcomes or dispatches a native candidate evaluation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import ascon_workload as workload
from isaforge import budgeted_selection as baseline
from isaforge import campaign_evidence as evidence
from isaforge import codesign as c
from isaforge import factorized_selection_experiment as experiment
from isaforge.speedup_corpus import family
from scripts.blind_campaign import _manifest as verify_manifest


SOURCE = "scripts/prepare_ascon_selector_prereg.py"
NATIVE = ROOT / "generated/ascon-target-qualification-2026-10-27"
QUALIFICATION = ROOT / "results/2026-10-27-ascon-target-qualification"
HISTORY = ROOT / "results/2026-10-26-lift-selection-corpus/corpus.json"
OUTPUT = ROOT / "results/2026-10-27-ascon-selector-prereg"
GROUP = workload.GROUP
AREA_CAP = 64
CLOCK_FLOOR_MHZ = 12.0
QUERY_BUDGET = 3


def require(condition, message):
    c.require(bool(condition), message)


def authenticated_inputs():
    """Read only the accepted baseline/public packet and authenticated history."""
    verify_manifest(HISTORY.parent)
    verify_manifest(QUALIFICATION)
    workload.verify_source_pins()
    workload.validate_inputs(NATIVE)
    public, context, before = workload.baseline_public(NATIVE)

    qual_protocol = c.unseal(QUALIFICATION / "protocol.json")
    qual_record = c.unseal(QUALIFICATION / "qualification.json")
    require(qual_protocol.get("schema") == "isaforge-ascon-v13-baseline-only-v1-qualification",
            "Accepted baseline-only Ascon qualification required")
    require(qual_record.get("status") == "accepted" and
            qual_record.get("target_candidate_attempts") == 0 and
            qual_record.get("accepted") == {"ascon128v13": "generated/ascon-target-qualification-2026-10-27"},
            "Qualification must remain accepted with zero candidate attempts")
    require(qual_protocol.get("candidate_dispatch_enabled") is False and
            qual_protocol.get("target_candidate_attempts") == 0,
            "Baseline-only candidate-dispatch boundary changed")
    require(not list((NATIVE / "attempt-ledger").glob("candidate_*.json")) and
            not list((NATIVE / "measurements").glob("candidate_*")),
            "Candidate attempt artifacts appeared before prelabel freeze")
    require(len(public) == workload.POOL_SIZE == 12 and
            len({row["candidate_id"] for row in public}) == len(public),
            "Complete unique public Ascon pool required")
    require(public[0]["benchmark"].split(":", 1)[0] == GROUP and
            context["workload_group"] == GROUP and before["workload"] == GROUP,
            "Exact Ascon target identity required")

    corpus = c.unseal(HISTORY)
    attempts = list(corpus["rows"]) + list(corpus["failed_attempts"])
    require(corpus["successful_labels"] == len(corpus["rows"]) == 122 and
            len(corpus["failed_attempts"]) == 4 and
            corpus["total_candidate_attempts"] == len(attempts) == 126 and
            len(corpus["independent_workload_groups"]) == 14 and
            len(corpus["contexts"]) == 15,
            "Complete authenticated 122-label/4-failure corpus required")
    require(len({row["candidate_id"] for row in attempts}) == len(attempts),
            "Historical candidate identities must be unique")
    require(sum(row["measurement_seconds"] for row in attempts) ==
            corpus["total_candidate_attempt_wall_seconds"],
            "Historical paid measurement duration must include every attempt")
    require(all(baseline.validate_outcome(row) for row in corpus["rows"]),
            "Only verified successful labels may fit the models")
    return public, context, before, corpus, qual_protocol, qual_record


def binding_map():
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "README.md",
        ROOT / "docs/ascon-target-adapter-contract-2026-10-27.md",
        ROOT / "docs/ascon-source-family-audit-2026-10-27.md",
        ROOT / "results/2026-10-27-ascon-source-family-audit/report.json",
        ROOT / "results/2026-10-26-ascon-host-preflight-r3/result.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/plan.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/public.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/context.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/before.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/opportunity.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/target-formula-family-audit.json",
        ROOT / "generated/ascon-target-qualification-2026-10-27/measurements/baseline/measurement.json",
        ROOT / "results/2026-10-27-ascon-target-qualification/protocol.json",
        ROOT / "results/2026-10-27-ascon-target-qualification/qualification.json",
        ROOT / "results/2026-10-27-ascon-target-qualification/archive-manifest.json",
        ROOT / "results/2026-10-27-ascon-target-qualification/raw.tar.gz",
        HISTORY,
        HISTORY.parent / "manifest.json",
        HISTORY.parent / "manifest.json.sha256",
        ROOT / workload.SOURCE,
        ROOT / "scripts/qualify_ascon.py",
        ROOT / "scripts/audit_ascon_source_family.py",
        ROOT / "isaforge/speedup_corpus.py",
        ROOT / "isaforge/codex_chat_selector.py",
    ]
    for timer in sorted((NATIVE / "outer-timing").glob("*.json")):
        if not timer.name.endswith(".sha256"):
            paths.append(timer)
    paths = list(dict.fromkeys(paths))
    for path in paths:
        require(path.is_file(), "Missing prelabel input: " + str(path.relative_to(ROOT)))
    return {path.relative_to(ROOT).as_posix(): c.sha(path) for path in paths}


def freeze(output=OUTPUT):
    started = time.monotonic()
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and not output.exists(),
            "Use a fresh in-repository Ascon preregistration directory")
    public, context, before, corpus, qual_protocol, qual_record = authenticated_inputs()
    all_target_families = sorted({family(row["formula"]) for row in public})
    filtered = [row for row in corpus["rows"] if family(row["formula"]) not in set(all_target_families)]
    excluded = [row["candidate_id"] for row in corpus["rows"] if family(row["formula"]) in set(all_target_families)]
    require(len(all_target_families) == 7 and len(filtered) == 90 and len(excluded) == 32 and
            len({row["workload_group"] for row in filtered}) == 14,
            "Expected exact family-safe cohort: 90 labels across 14 workload groups")

    contexts = dict(corpus["contexts"])
    contexts[public[0]["benchmark"]] = context
    bindings = binding_map()
    c.seal(output / "inputs/public.json", public)
    c.seal(output / "inputs/context.json", context)
    c.seal(output / "inputs/history.json", corpus["rows"])
    c.seal(output / "inputs/historical-failures.json", corpus["failed_attempts"])
    c.seal(output / "inputs/contexts.json", contexts)

    calibration = evidence._calibration(NATIVE)
    baseline_measurement = c.unseal(NATIVE / "measurements/baseline/measurement.json")
    cost_provenance = dict(
        historical_training=dict(successful_labels=122, failed_attempts=4, attempts=126,
            candidate_wall_seconds=corpus["total_candidate_attempt_wall_seconds"],
            corpus=HISTORY.relative_to(ROOT).as_posix(), corpus_sha256=c.sha(HISTORY)),
        target_qualification=dict(status=qual_record["status"], target_candidate_attempts=0,
            recorded_subprocess_seconds=qual_record["recorded_subprocess_monotonic_seconds"],
            protocol_sha256=c.sha(QUALIFICATION / "protocol.json"),
            archive_sha256=c.sha(QUALIFICATION / "raw.tar.gz")),
        target_baseline=dict(context["baseline_provenance"],
            measurement_sha256=c.sha(NATIVE / "measurements/baseline/measurement.json"),
            recorded_performance=baseline_measurement.get("performance"),
            recorded_resources=baseline_measurement.get("resources")),
        processor_calibration=dict(native_commands=calibration["native_commands"],
            native_command_seconds=calibration["native_command_seconds"],
            application_labels_collected=calibration["application_labels_collected"]),
        note="Historical failures remain charged. Qualification, baseline, calibration, model fit, selector relay, and candidate-evaluation times are distinct scopes; overlapping timers are not summed.")

    selection = output / "selection"
    fit_started = time.monotonic()
    protocol = experiment.freeze(
        corpus["rows"], public, contexts, selection,
        target_workload=GROUP,
        target_labels_observed=0,
        calibration_cost_seconds=calibration["native_command_seconds"],
        cost_provenance=cost_provenance,
        input_bindings=bindings,
        scope="prospective source holdout",
    )
    model_freeze_seconds = time.monotonic() - fit_started
    verified = experiment.authenticate(selection)
    require(len(verified["history"]) == 90 and
            len(protocol["historical_postfilter_groups"]) == 14 and
            protocol["target_labels_read"] == protocol["target_labels_observed"] == 0,
            "Frozen model package does not match the declared zero-label cohort")

    controller = dict(
        status="prelabel model package frozen; native controller not yet released",
        agent_policy="current Codex chat model, relayed through bounded list/predict/measure/finalize actions",
        agent_tools=["list_candidates", "predict", "measure", "finalize"],
        action_handles="Use session-local C01..C12 handles bound to complete immutable candidate IDs; reject stale/unknown handles before charging.",
        candidate_attempts=0,
        native_dispatch_enabled=False,
        max_charged_attempts=QUERY_BUDGET,
        area_delta_lut4_cap=AREA_CAP,
        minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
        one_to_three_instruction_combinations=False,
        model_is_frozen_during_episode=True,
        policies=[*baseline.POLICIES, experiment.controls.POLICY, experiment.POLICY,
                  "codex_chat_llm_agent"],
        shared_information=("Same public pool, training rows, fixed model predictions, baseline, area/timing limits, paid outcomes, and three-attempt cap. The oracle remains hidden until all policy decisions are sealed."),
        primary_endpoint="best verified feasible whole-program speedup by query 3; regret to complete measured 12-candidate pool if every reference attempt resolves",
        limitations=[
            "Ascon is related-domain cryptography transfer, not an independent workload-family test.",
            "The current chat model carries conversation context and is not an isolated provider run.",
            "The live LLM attempt, operator relay time, model-only latency, and token count are not yet recorded.",
            "No candidate measurements or outcomes are included in this preregistration.",
            "This package alone does not authorize native dispatch; the guarded controller and pushed source release must follow.",
        ],
    )
    c.seal(output / "llm-controller-preregistration.json", controller)
    prelabel = dict(
        schema="isaforge-ascon-selector-prereg-v1",
        scope="prospective same-domain crypto workload transfer; not independent-family confirmation",
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        target_workload=GROUP,
        target_context_id=context["context_id"],
        target_labels_read=0,
        target_labels_observed=0,
        native_candidate_attempts_before_freeze=0,
        public_candidate_count=len(public),
        target_candidate_families=all_target_families,
        excluded_related_history_ids=excluded,
        historical_available_labels=122,
        historical_attempts_including_failures=126,
        historical_family_safe_training_labels=len(verified["history"]),
        historical_family_safe_groups=protocol["historical_postfilter_groups"],
        selection_protocol_sha256=c.sha(selection / "protocol.json"),
        selection_manifest={path.relative_to(selection).as_posix(): c.sha(path)
                            for path in sorted(selection.rglob("*")) if path.is_file()},
        input_bindings=bindings,
        candidate_ids=[row["candidate_id"] for row in public],
        candidate_formulas=[row["formula"] for row in public],
        baseline_only_qualification_sha256=c.sha(QUALIFICATION / "qualification.json"),
        source_family_audit_sha256=c.sha(ROOT / "results/2026-10-27-ascon-source-family-audit/report.json"),
        policies=controller["policies"],
        seeds=list(experiment.SEEDS),
        budgets=list(experiment.BUDGETS),
        primary=dict(area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
                     max_charged_attempts=QUERY_BUDGET),
        cost_provenance=cost_provenance,
        native_dispatch_enabled=False,
        model_fits=5,
        model_freeze_outer_operation_seconds=model_freeze_seconds,
        limitations=controller["limitations"],
    )
    prelabel["prelabel_freeze_operation_seconds"] = time.monotonic() - started
    c.seal(output / "preregistration.json", prelabel)
    inventory = {path.relative_to(output).as_posix(): c.sha(path)
                 for path in sorted(output.rglob("*")) if path.is_file() and
                 path.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output / "manifest.json", inventory)
    return prelabel


def authenticate(output=OUTPUT):
    output = Path(output).resolve()
    verify_manifest(output)
    prereg = c.unseal(output / "preregistration.json")
    require(prereg.get("schema") == "isaforge-ascon-selector-prereg-v1" and
            prereg.get("target_labels_read") == prereg.get("target_labels_observed") == 0 and
            prereg.get("native_candidate_attempts_before_freeze") == 0 and
            prereg.get("native_dispatch_enabled") is False,
            "Expected zero-label/no-dispatch Ascon preregistration")
    for name, digest in prereg["input_bindings"].items():
        require(c.sha(ROOT / name) == digest, "Prelabel input changed: " + name)
    native_public, context, before = workload.baseline_public(NATIVE)
    require(native_public == c.unseal(output / "inputs/public.json") and
            context == c.unseal(output / "inputs/context.json") and
            context["context_id"] == prereg["target_context_id"] and
            before["workload"] == GROUP,
            "Current baseline/public target differs from preregistration")
    corpus = c.unseal(HISTORY)
    require(c.unseal(output / "inputs/history.json") == corpus["rows"] and
            c.unseal(output / "inputs/historical-failures.json") == corpus["failed_attempts"],
            "Historical outcome/failure data differs")
    case = experiment.authenticate(output / "selection")
    require(c.sha(output / "selection/protocol.json") == prereg["selection_protocol_sha256"] and
            len(case["history"]) == prereg["historical_family_safe_training_labels"] == 90 and
            case["protocol"]["historical_postfilter_groups"] == prereg["historical_family_safe_groups"],
            "Frozen selection models or family-excluded cohort differ")
    require(not list((NATIVE / "attempt-ledger").glob("candidate_*.json")) and
            not list((NATIVE / "measurements").glob("candidate_*")),
            "Native candidate attempt appeared before controller release")
    return dict(preregistration=prereg, frozen_models=case)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--output", type=Path, default=OUTPUT)
    auth_parser = sub.add_parser("authenticate")
    auth_parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze(args.output)
        print({"target": result["target_workload"],
               "public_candidates": result["public_candidate_count"],
               "historical_labels": result["historical_family_safe_training_labels"],
               "historical_groups": len(result["historical_family_safe_groups"]),
               "target_labels_read": result["target_labels_read"],
               "native_dispatch_enabled": result["native_dispatch_enabled"]})
    else:
        result = authenticate(args.output)
        print({"authenticated": True,
               "target": result["preregistration"]["target_workload"],
               "candidate_attempts": 0})


if __name__ == "__main__":
    main()
