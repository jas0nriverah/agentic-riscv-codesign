from __future__ import annotations

import json
from pathlib import Path

import pytest

from isaforge import ascon_workload as workload
from isaforge import codesign as c
from isaforge.speedup_corpus import family
from scripts import qualify_ascon


def test_source_and_host_evidence_pins_are_closed_before_target_work():
    pins = workload.verify_source_pins()
    assert pins["target_adapter_sha256"] == c.sha(c.ROOT / workload.PROGRAM)
    assert pins["source_family_audit_sha256"] == c.sha(c.ROOT / workload.SOURCE_FAMILY_REPORT)
    assert workload.POOL_SIZE == 12
    assert workload.PARTITION == dict(ram_bytes=8192, program_limit=6400,
        stack_floor=6528, stack_bytes=1664, minimum_guard_bytes=128)
    assert workload.PROTOCOL["candidate_dispatch_enabled"] is False
    assert workload.PROTOCOL["target_candidate_attempts"] == 0
    assert workload.PROTOCOL["model_fit_during_qualification"] is False
    assert workload.PROTOCOL["target_bytewise_kat_comparison"] is False
    assert workload.PROTOCOL["minimum_calibrated_cycle_reduction"] == 0.005
    assert workload.PROTOCOL["minimum_timed_replacements"] == 10


def test_qualification_binds_only_existing_source_paths():
    assert len(qualify_ascon.SOURCES) == len(set(qualify_ascon.SOURCES))
    assert all((c.ROOT / name).is_file() for name in qualify_ascon.SOURCES)
    assert qualify_ascon.PHASES == (
        "prepare", "discover", "opportunity", "baseline", "public", "freeze")


def test_registration_is_scoped_and_restored_after_exception():
    g = workload.g
    before = (g.SOURCE, dict(g.WORKLOADS), g.POOL_SIZE, dict(g.NATIVE_LIMITS),
        g.q.SOURCE, dict(g.q.WORKLOADS), g.q.POOL_SIZE,
        g.q.bounded.SOURCE, dict(g.q.bounded.WORKLOADS), g.q.bounded.POOL_SIZE,
        dict(g.q.bounded.campaign.WORKLOADS), g.q.bounded.campaign.POOL_SIZE,
        workload.evidence._public)
    with pytest.raises(RuntimeError, match="registration unwind"):
        with workload.registration():
            assert g.WORKLOADS == {workload.WORKLOAD:
                "../../ascon/ascon128v13_isaforge.c"}
            assert g.POOL_SIZE == workload.POOL_SIZE
            assert g.q.bounded.POOL_SIZE == workload.POOL_SIZE
            raise RuntimeError("registration unwind")
    after = (g.SOURCE, dict(g.WORKLOADS), g.POOL_SIZE, dict(g.NATIVE_LIMITS),
        g.q.SOURCE, dict(g.q.WORKLOADS), g.q.POOL_SIZE,
        g.q.bounded.SOURCE, dict(g.q.bounded.WORKLOADS), g.q.bounded.POOL_SIZE,
        dict(g.q.bounded.campaign.WORKLOADS), g.q.bounded.campaign.POOL_SIZE,
        workload.evidence._public)
    assert after == before


def test_exact_target_family_audit_marks_seen_families_as_training_overlap():
    path = c.ROOT / "results/2026-10-21-blind-preregistration/targets/beebs-ndes/public.json"
    rows = json.loads(path.read_text())
    overlapping = next(row for row in rows
        if family(row["formula"]) == "or(input,slli(input,constant))")
    audit = workload.exact_candidate_family_audit([overlapping])
    assert audit["candidate_count"] == 1
    candidate = audit["candidates"][0]
    assert candidate["formula_family"] == "or(input,slli(input,constant))"
    assert "ndes" in candidate["exact_prior_family_overlap"]
    assert candidate["eligible_for_unseen_formula_family_training"] is False
    assert audit["target_outcomes_read"] is False
    assert audit["target_labels"] == audit["model_fits"] == 0
    assert audit["independent_confirmatory_family"] is False


def test_baseline_qualification_rejects_any_candidate_attempt_artifact(tmp_path):
    workload.require_zero_candidates(tmp_path)
    ledger = tmp_path / "attempt-ledger"
    ledger.mkdir()
    (ledger / "candidate_000.json").write_text("{}\n")
    with pytest.raises(ValueError, match="zero candidate attempts"):
        workload.require_zero_candidates(tmp_path)
