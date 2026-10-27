"""Fake-only controller tests; these never fit models or run native tools."""
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from isaforge import ascon_selector_controller as controller
from isaforge import codesign as c


@pytest.fixture(autouse=True)
def forbid_native_and_model_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Native tools and model fitting are forbidden in these tests")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(controller.baseline.HardwareSurrogate, "fit", forbidden)
    monkeypatch.setattr(controller, "_CandidateCapableEvaluator", forbidden)


def campaign(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    root.mkdir()
    control = root / "selector-controller"
    control.mkdir()
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "release.json").write_text("{}\n")
    state = dict(status="ready", tool_calls=0, charged_attempts=0,
        attempted_handles=[], attempted_ids=[], attempts=[], observations=[],
        context_id="fake-context", release_sha256="fake-release", finalized=None,
        model_fit_seconds=0.0, model_inference_seconds=0.0)
    handles = [dict(handle="C01", candidate_id="id-1", name="candidate_00",
                    formula="and(in0,in1)"),
               dict(handle="C02", candidate_id="id-2", name="candidate_01",
                    formula="or(in0,in1)")]
    public = [{"candidate_id": row["candidate_id"], "formula": row["formula"],
               "benchmark": "fake-workload"} for row in handles]
    events = []
    meta = dict(control=control, events=events,
        release={"dispatch_gate": {"branch": "ai-guided-ml"}})

    def load(_root, _release_directory=controller.RELEASE_DEFAULT, *, allow_inflight=False):
        meta["allow_inflight"] = allow_inflight
        return state, handles, public, meta

    monkeypatch.setattr(controller, "_load_campaign", load)
    return root, control, release_dir, state, handles, public, meta


def test_release_source_bindings_authenticate_zero_label_inputs():
    bindings = controller._release_sources()
    assert bindings[controller.SOURCE] == c.sha(controller.ROOT / controller.SOURCE)
    assert bindings["tests/test_ascon_selector_controller.py"] == c.sha(
        controller.ROOT / "tests/test_ascon_selector_controller.py")


def test_relocated_context_ignores_only_root_specific_artifact_receipts(tmp_path):
    root = tmp_path / "restored"
    root.mkdir()
    artifact = root / "plan.json"
    artifact.write_text('{"context":"same"}\n')
    digest = c.sha(artifact)
    restored = {"context_id": "same-context", "workload_group": "ascon",
        "baseline_provenance": {"root": str(root), "artifacts": {"plan.json": digest},
            "source_bindings": {"model.py": "source-hash"}}}
    frozen = {"context_id": "same-context", "workload_group": "ascon",
        "baseline_provenance": {"root": "/old/qualification/root",
            "artifacts": {"plan.json": "old-root-hash"},
            "source_bindings": {"model.py": "source-hash"}}}
    controller._require(controller._portable_context(restored) ==
                        controller._portable_context(frozen), "portable projection differs")
    controller._verify_restored_baseline_provenance(root, restored,
        {"artifacts": {"plan.json": digest}})

    bad_source = {**frozen, "baseline_provenance": {
        **frozen["baseline_provenance"], "source_bindings": {"model.py": "changed"}}}
    assert controller._portable_context(restored) != controller._portable_context(bad_source)
    with pytest.raises(ValueError, match="Restored baseline artifact differs"):
        controller._verify_restored_baseline_provenance(root, restored,
            {"artifacts": {"plan.json": "wrong-hash"}})


def test_prediction_output_filters_by_stable_handle(monkeypatch, tmp_path):
    handles = [dict(handle="C01", candidate_id="id-1"),
               dict(handle="C02", candidate_id="id-2")]
    public = [{"candidate_id": "id-1"}, {"candidate_id": "id-2"}]
    monkeypatch.setattr(controller, "_prediction_tables", lambda rows: ({"frozen": {}}, {}))
    monkeypatch.setattr(controller, "_dynamic_gp", lambda *args: ({}, 0.0, 0.0))
    monkeypatch.setattr(controller, "_public_candidate", lambda handle, *args: {"handle": handle})

    result = controller._request_candidate_outputs(
        tmp_path, {}, handles, public, ["C02"])
    assert result == [{"handle": "C02"}]
    with pytest.raises(ValueError, match="unknown candidate handle"):
        controller._request_candidate_outputs(tmp_path, {}, handles, public, ["C03"])


def test_invalid_measure_is_rejected_without_charge_or_stuck_event(tmp_path, monkeypatch):
    root, control, release_dir, state, _, _, meta = campaign(tmp_path, monkeypatch)
    monkeypatch.setattr(controller, "_validate_postpush",
                        lambda *_: pytest.fail("Unknown handle must fail before dispatch gate"))

    result = controller.call(root,
        {"tool": "measure", "arguments": {"handle": "C99"}},
        release_directory=release_dir)

    assert result["status"] == "error"
    assert state["charged_attempts"] == 0
    assert state["attempts"] == []
    assert meta["events"][0]["status"] == "rejected"
    assert not (control / "attempt-01.json").exists()
    assert c.unseal(control / "session.json")["charged_attempts"] == 0


def test_measure_persists_reservation_before_fake_evaluator_and_terminal_result(
        tmp_path, monkeypatch):
    root, control, release_dir, state, handles, public, meta = campaign(tmp_path, monkeypatch)
    (release_dir / "release.json").write_text('{"fake":true}\n')
    calls = []

    def check_release(_):
        assert not (control / "attempt-01.json").exists()

    class FakeEvaluator:
        def __init__(self, _root):
            self.runner = SimpleNamespace(lock=SimpleNamespace(close=lambda: None))

        def measure(self, name):
            slot = c.unseal(control / "attempt-01.json")
            assert slot["status"] == "started"
            calls.append(name)

    outcome = dict(status="success", candidate_id="id-1", baseline_cycles=100,
        candidate_cycles=90, speedup=100 / 90, area_delta_lut4=12,
        routed_fmax_min_mhz=40.0, correctness_verified=True, device_fits=True,
        timing_feasible=True, measurement_seconds=1.2)
    monkeypatch.setattr(controller, "_validate_postpush", check_release)
    monkeypatch.setattr(controller, "_CandidateCapableEvaluator", FakeEvaluator)
    monkeypatch.setattr(controller, "_audit_after_attempt", lambda *_: (outcome, {"audit": True}))
    monkeypatch.setattr(controller, "_measured_public_row",
        lambda _public, row: {**row, "workload_group": "fake", "candidate_family": "and"})

    result = controller.call(root,
        {"tool": "measure", "arguments": {"handle": "C01"}},
        release_directory=release_dir)

    slot = c.unseal(control / "attempt-01.json")
    assert calls == ["candidate_00"]
    assert slot["status"] == "success" and slot["tool_sequence"] == 1
    assert state["charged_attempts"] == 1
    assert state["attempts"][0]["status"] == "success"
    assert meta["events"][0]["status"] == "success"
    assert result["observation"]["candidate_cycles"] == 90


def test_unexpected_evaluator_error_is_charged_unknown_and_never_retried(
        tmp_path, monkeypatch):
    root, control, release_dir, state, _, _, meta = campaign(tmp_path, monkeypatch)
    (release_dir / "release.json").write_text('{"fake":true}\n')
    calls = []

    class FakeEvaluator:
        def __init__(self, _root):
            self.runner = SimpleNamespace(lock=SimpleNamespace(close=lambda: None))

        def measure(self, _name):
            calls.append("measure")
            raise RuntimeError("simulated interruption")

    monkeypatch.setattr(controller, "_validate_postpush", lambda *_: None)
    monkeypatch.setattr(controller, "_CandidateCapableEvaluator", FakeEvaluator)

    first = controller.call(root,
        {"tool": "measure", "arguments": {"handle": "C01"}},
        release_directory=release_dir)
    second = controller.call(root,
        {"tool": "measure", "arguments": {"handle": "C02"}},
        release_directory=release_dir)

    assert first["status"] == "error" and second["status"] == "error"
    assert calls == ["measure"]
    assert state["charged_attempts"] == 1
    assert state["status"] == "stopped_unknown_outcome"
    assert c.unseal(control / "attempt-01.json")["status"] == "unknown"
    assert meta["events"][0]["status"] == "unknown"


def test_recovery_closes_inflight_slot_and_reconciles_state_and_event(
        tmp_path, monkeypatch):
    root, control, release_dir, state, handles, _, meta = campaign(tmp_path, monkeypatch)
    state.update(tool_calls=1, charged_attempts=1, attempted_handles=["C01"],
        attempted_ids=["id-1"], attempts=[dict(slot=1, handle="C01", candidate_id="id-1",
                                                 status="started")])
    event = dict(sequence=1, action={"tool": "measure", "arguments": {"handle": "C01"}},
        status="reserved", charged_before=0, charged_attempt=1, candidate_handle="C01")
    meta["events"].append(event)
    slot = dict(schema="isaforge-ascon-selector-attempt-v1", slot=1, handle="C01",
        candidate_id="id-1", name="candidate_00", formula=handles[0]["formula"],
        context_id="fake-context", release_sha256="fake-release", tool_sequence=1,
        status="started")
    controller._durable_seal(control / "attempt-01.json", slot)
    meta["slots"] = [slot]

    result = controller.recover_interrupted(root, release_directory=release_dir)

    assert meta["allow_inflight"] is True
    assert result == {"status": "stopped_unknown_outcome", "charged_attempts": 1}
    assert state["attempts"][0]["status"] == "unknown_interrupted"
    assert event["status"] == "unknown_interrupted"
    assert c.unseal(control / "attempt-01.json")["status"] == "unknown_interrupted"
    assert state["observations"] == []
