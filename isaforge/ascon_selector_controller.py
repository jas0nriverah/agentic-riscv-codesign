"""Source-bound, three-query Ascon selector over the guarded PicoRV32 evaluator.

This module is separate from ``ascon_workload.Evaluator``: that entrypoint is
and remains baseline-only. A fresh campaign is restored from the accepted
baseline archive, and every candidate action is reserved durably before the
generic one-attempt evaluator can launch native tools. The current Codex chat
can drive the four-action JSON interface; it is not an isolated model API.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from . import ascon_workload as ascon
from . import budgeted_selection as baseline
from . import codesign as c
from . import factorized_selection_experiment as factorized
from . import feasible_benefit_experiment as benefit
from . import guarded_evidence
from . import guarded_workload as guarded
from .speedup_corpus import family

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "isaforge/ascon_selector_controller.py"
PREREG = ROOT / "results/2026-10-27-ascon-selector-prereg-v3"
QUALIFICATION = ROOT / "results/2026-10-27-ascon-target-qualification"
CAMPAIGN_DEFAULT = ROOT / "generated/ascon-native-selector-2026-10-27-v5"
RELEASE_DEFAULT = ROOT / "results/2026-10-27-ascon-selector-controller-release-v5"
MAX_QUERIES = 3
MAX_TOOL_CALLS = 20
AREA_CAP = 64
CLOCK_FLOOR_MHZ = 12.0
FAILURE_UNKNOWN = {"unknown", "infrastructure_unknown"}
TERMINAL_ATTEMPT_STATUSES = {"success", "failed", "unknown", "unknown_interrupted"}
TERMINAL_EVENT_STATUSES = {
    "complete", "success", "failed", "unknown", "unknown_interrupted",
    "rejected", "error", "finalized",
}
INFLIGHT_EVENT_STATUSES = {"started", "reserved"}

POLICY_UPDATE_SEMANTICS = {
    "xgboost_regression": "Fit once on the frozen family-filtered historical cohort; no target-label refit.",
    "xgboost_pairwise_ranker": "Fit once on the frozen family-filtered historical cohort; rank_score is not speedup or confidence.",
    "xgboost_normalized": "Fit once on the frozen family-filtered historical cohort; output is normalized saved-cycle-per-occurrence, not speedup.",
    "feasible_benefit_xgb": "Fit once; utility and ensemble spread are not measured speedup or calibrated uncertainty.",
    "factorized_feasibility_xgb": "Fit once; bootstrap feasibility scores are uncalibrated disagreement.",
    "hybrid_gp_zero_shot": "Use the frozen initial hardware-posterior predictions throughout.",
    "hybrid_gp_adapt": "Refit the existing hardware surrogate on historical rows plus this policy's own verified successful paid prefix; failures do not enter the numeric fit.",
    "codex_chat_llm_agent": "No model refit; the current chat model receives public data, model predictions, constraints, and only outcomes returned by its own paid actions.",
    "fixed_joint_posterior": "Not in the frozen Ascon policy set; separate fixed-initial Gaussian conditioning contract, not equivalent to hybrid_gp_adapt refitting.",
}

ADDED_SOURCES = (
    SOURCE,
    "scripts/run_ascon_selector_controller.py",
    "scripts/prepare_ascon_selector_prereg.py",
    "docs/ascon-selector-policy-semantics-2026-10-27.md",
    "docs/joint-posterior-update-contract.md",
    "docs/paid-update-semantics.md",
    "tests/test_ascon_selector_controller.py",
)


def _require(ok: bool, message: str) -> None:
    c.require(bool(ok), message)


def _durable_seal(path: Path, value: dict) -> None:
    """Atomic JSON+digest write, flushed before any subsequent dispatch."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    digest = hashlib.sha256(data).hexdigest()
    sidecar = Path(str(path) + ".sha256")
    temporary_sidecar = sidecar.with_name(sidecar.name + ".tmp")
    with temporary_sidecar.open("w", encoding="ascii") as stream:
        stream.write(digest + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_sidecar, sidecar)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_seal(path: Path) -> dict:
    path = Path(path)
    _require(c.sha(path) == Path(str(path) + ".sha256").read_text().strip(),
             "Controller journal checksum differs: " + path.name)
    return c.read(path)


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                            capture_output=True, check=False)
    _require(result.returncode == 0, "Git release check failed: " + " ".join(args))
    return result.stdout.strip()


def _release_sources() -> dict[str, str]:
    target_protocol = c.unseal(ROOT / "generated/ascon-target-qualification-2026-10-27/evaluation-protocol.json")
    bindings = dict(target_protocol["source_bindings"])
    prereg = c.unseal(PREREG / "preregistration.json")
    qualification = c.unseal(QUALIFICATION / "qualification.json")
    _require(prereg["target_labels_read"] == prereg["target_labels_observed"] == 0 and
             prereg["native_candidate_attempts_before_freeze"] == 0,
             "Ascon prelabel release must remain zero-label")
    _require(qualification["status"] == "accepted" and
             qualification["target_candidate_attempts"] == 0,
             "Baseline-only Ascon qualification must remain candidate-free")
    for name in ADDED_SOURCES:
        path = ROOT / name
        _require(path.is_file(), "Required controller release source missing: " + name)
        bindings[name] = c.sha(path)
    return dict(sorted(bindings.items()))


def _release_inputs() -> dict[str, str]:
    prereg_manifest = c.unseal(PREREG / "manifest.json")
    result = {str((PREREG / name).relative_to(ROOT)): digest
              for name, digest in prereg_manifest.items()}
    qualification_manifest = c.unseal(QUALIFICATION / "manifest.json")
    result.update({str((QUALIFICATION / name).relative_to(ROOT)): digest
                   for name, digest in qualification_manifest.items()})
    for name in ("manifest.json", "manifest.json.sha256"):
        result[str((PREREG / name).relative_to(ROOT))] = c.sha(PREREG / name)
        result[str((QUALIFICATION / name).relative_to(ROOT))] = c.sha(QUALIFICATION / name)
    return dict(sorted(result.items()))


def _candidate_map(public: list[dict], discovery: dict) -> list[dict]:
    by_id = {row["candidate_id"]: row for row in discovery["pool"]}
    _require(len(public) == 12 and set(by_id) == {row["candidate_id"] for row in public},
             "Exact twelve-candidate ID bijection required")
    result = []
    for index, row in enumerate(public, 1):
        native = by_id[row["candidate_id"]]
        _require(native["formula"] == row["formula"], "Public/native formula mapping differs")
        result.append(dict(handle=f"C{index:02d}", candidate_id=row["candidate_id"],
            name=native["name"], formula=row["formula"],
            assembly_sha256=native["assembly_sha256"], public_sha256=c.digest(row)))
    _require(len({r["handle"] for r in result}) == len(result) and
             len({r["candidate_id"] for r in result}) == len(result),
             "Candidate handle map must be bijective")
    return result


def freeze_release(output: Path = RELEASE_DEFAULT) -> dict:
    """Freeze the candidate-capable release without reading target labels."""
    from scripts import prepare_ascon_selector_prereg as prereg_script
    prereg_script.authenticate()
    output = Path(output).resolve()
    _require(output.is_relative_to(ROOT) and not output.exists(),
             "Use a new in-repository release directory")
    public = c.unseal(PREREG / "inputs/public.json")
    native_root = ROOT / "generated/ascon-target-qualification-2026-10-27"
    discovery = c.unseal(native_root / "discovery/discovery.json")
    _require(not list((native_root / "attempt-ledger").glob("candidate_*.json")) and
             not list((native_root / "measurements").glob("candidate_*")),
             "Preserve baseline-only root with zero candidate attempts")
    handles = _candidate_map(public, discovery)
    evaluation = c.unseal(native_root / "evaluation-protocol.json")
    _require(evaluation["maximum_candidate_attempts"] == 12 and
             evaluation["attempts_per_candidate"] == 1 and
             evaluation["context_id"] == c.unseal(native_root / "plan.json")["context_id"],
             "Generic one-attempt target contract differs")
    release = dict(schema="isaforge-ascon-selector-controller-release-v1",
        status="candidate-capable; native dispatch requires committed-and-pushed source gate",
        target=ascon.GROUP, target_context_id=evaluation["context_id"],
        target_labels_read=0, target_labels_observed=0, candidate_attempts_before_release=0,
        candidate_count=12, candidate_handles=handles,
        policy="codex_chat_llm_agent", provider="current Codex chat model; not isolated API provider",
        tools={"list_candidates": {}, "predict": {"handles": "unique C01..C12 handles"},
               "measure": {"handle": "one unattempted stable candidate handle"},
               "finalize": {"handle": "paid feasible improvement or null baseline", "summary": "<=500 chars"}},
        constraints=dict(area_delta_lut4_cap=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
                         evaluation_budget=MAX_QUERIES, max_tool_calls=MAX_TOOL_CALLS,
                         routes=[1, 2, 3], one_attempt_per_candidate=True),
        update_semantics=POLICY_UPDATE_SEMANTICS,
        paid_update_rule="Reserve before evaluator dispatch. Only successful, correctness-verified outcomes enter numeric updates. Known failures consume a query but are not labels. Unknown/interrupted outcomes stop the session and are never retried.",
        uncertainty="All XGBoost ensemble/bootstrap spread and GP intervals are uncalibrated unless separately calibrated; ranking score is not speedup.",
        comparison="The frozen controls use the same seed-0 model artifacts, candidate features, area/timing limits, and at most three logical queries. Full-pool oracle replay occurs only after the LLM decision trace is sealed and every reference attempt resolves.",
        costs="Keep candidate evaluation wall/native command time, fixed model fit/inference time, adaptive GP refit time, and LLM request-to-action wall time separate. The current chat does not expose model-only latency or tokens.",
        independent_family_confirmation=False,
        baseline_only_qualification_sha256=c.sha(QUALIFICATION / "qualification.json"),
        prelabel_manifest_sha256=c.sha(PREREG / "manifest.json"),
        evaluation_protocol_sha256=c.sha(native_root / "evaluation-protocol.json"),
        source_bindings=_release_sources(), input_bindings=_release_inputs(),
        dispatch_gate={"branch": "ai-guided-ml", "head_must_equal": "origin/ai-guided-ml",
                       "every_bound_file_must_be_committed_unchanged": True},
        native_dispatch_enabled=True)
    output.mkdir(parents=True)
    c.seal(output / "release.json", release)
    manifest = {p.relative_to(output).as_posix(): c.sha(p) for p in sorted(output.rglob("*"))
                if p.is_file() and p.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output / "manifest.json", manifest)
    return release


def authenticate_release(directory: Path = RELEASE_DEFAULT, *, require_pushed: bool = False) -> dict:
    from scripts import prepare_ascon_selector_prereg as prereg_script
    directory = Path(directory).resolve()
    manifest = _read_seal(directory / "manifest.json")
    _require(manifest == {p.relative_to(directory).as_posix(): c.sha(p)
             for p in sorted(directory.rglob("*")) if p.is_file() and
             p.name not in ("manifest.json", "manifest.json.sha256")},
             "Controller release manifest differs")
    release = _read_seal(directory / "release.json")
    _require(release.get("schema") == "isaforge-ascon-selector-controller-release-v1" and
             release.get("native_dispatch_enabled") is True and
             release.get("target_labels_read") == release.get("target_labels_observed") == 0,
             "Exact zero-label controller release required")
    _require(release["source_bindings"] == _release_sources() and
             release["input_bindings"] == _release_inputs(),
             "Source or frozen input binding differs")
    _require(len(release["candidate_handles"]) == 12 and
             release["constraints"]["evaluation_budget"] == 3 and
             release["constraints"]["area_delta_lut4_cap"] == 64 and
             release["constraints"]["minimum_routed_fmax_mhz"] == 12.0,
             "Frozen Ascon selection budget changed")
    # This checks that the untouched qualification root still has zero labels.
    prereg_script.authenticate()
    if require_pushed:
        branch = _git("branch", "--show-current")
        head = _git("rev-parse", "HEAD")
        remote = _git("rev-parse", "refs/remotes/origin/ai-guided-ml")
        _require(branch == "ai-guided-ml" and head == remote,
                 "Native dispatch requires the release pushed to origin/ai-guided-ml")
        for name, expected in release["source_bindings"].items():
            shown = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT,
                capture_output=True, check=False)
            _require(shown.returncode == 0 and hashlib.sha256(shown.stdout).hexdigest() == expected,
                     "Bound source is not present unchanged in pushed HEAD: " + name)
            dirty = _git("status", "--porcelain", "--", name)
            _require(not dirty, "Bound source has local changes: " + name)
        for name, expected in release["input_bindings"].items():
            shown = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT,
                capture_output=True, check=False)
            _require(shown.returncode == 0 and hashlib.sha256(shown.stdout).hexdigest() == expected,
                     "Frozen input is not present unchanged in pushed HEAD: " + name)
            dirty = _git("status", "--porcelain", "--", name)
            _require(not dirty, "Frozen input has local changes: " + name)
    return release


def _prelabel_from_root(root: Path) -> tuple[list[dict], dict, dict]:
    """Authenticate the baseline archive projection before any candidate labels."""
    from scripts.blind_campaign import _manifest as verify_manifest
    from scripts import prepare_ascon_selector_prereg as prereg_script
    verify_manifest(PREREG)
    verify_manifest(QUALIFICATION)
    prereg = _read_seal(PREREG / "preregistration.json")
    prefix = Path("generated/ascon-target-qualification-2026-10-27")
    for name, expected in prereg["input_bindings"].items():
        source = (root / Path(name).relative_to(prefix) if name.startswith(str(prefix))
                  else ROOT / name)
        _require(c.sha(source) == expected, "Prelabel source differs: " + name)
    with ascon.registration():
        public, context, before = ascon.baseline_public(root)
    _require(public == c.unseal(PREREG / "inputs/public.json") and
             _portable_context(context) == _portable_context(
                 c.unseal(PREREG / "inputs/context.json")) and
             context["context_id"] == prereg["target_context_id"] and
             before["workload"] == ascon.GROUP,
             "Restored target baseline differs from the sealed prelabel pool")
    _verify_restored_baseline_provenance(root, context, before)
    frozen = factorized.authenticate(PREREG / "selection")
    _require(len(frozen["history"]) == 90 and prereg["target_labels_observed"] == 0,
             "Family-safe frozen model package differs")
    return public, context, before


def _portable_context(context: dict) -> dict:
    """Drop only root-local provenance that necessarily changes on archive restore."""
    result = copy.deepcopy(context)
    provenance = result.get("baseline_provenance")
    _require(isinstance(provenance, dict), "Baseline provenance is required")
    provenance.pop("root", None)
    provenance.pop("artifacts", None)
    return result


def _verify_restored_baseline_provenance(root: Path, context: dict, before: dict) -> None:
    root = Path(root).resolve()
    provenance = context.get("baseline_provenance")
    _require(isinstance(provenance, dict) and
             Path(provenance.get("root", "")).resolve() == root and
             isinstance(provenance.get("artifacts"), dict) and provenance["artifacts"],
             "Restored baseline provenance root or artifact map is invalid")
    _require(isinstance(before.get("artifacts"), dict),
             "Routed baseline artifact map is missing")
    for artifact_map in (provenance["artifacts"], before.get("artifacts", {})):
        for name, expected in artifact_map.items():
            relative = Path(name)
            path = (root / relative).resolve()
            _require(not relative.is_absolute() and path.is_relative_to(root) and
                     c.sha(path) == expected,
                     "Restored baseline artifact differs: " + str(name))


def prepare_campaign(root: Path = CAMPAIGN_DEFAULT,
                     release_directory: Path = RELEASE_DEFAULT) -> dict:
    """Restore a fresh native root from the immutable baseline-only archive."""
    from scripts.reproduce_codesign import restore_archive
    release = authenticate_release(release_directory)
    root = Path(root).resolve()
    _require(root.is_relative_to(ROOT) and not root.exists(),
             "Use a fresh repository-local selector campaign root")
    archive = c.unseal(QUALIFICATION / "archive-manifest.json")
    restore_archive(QUALIFICATION, archive, root)
    public, context, before = _prelabel_from_root(root)
    discovery = c.unseal(root / "discovery/discovery.json")
    handles = _candidate_map(public, discovery)
    control = root / "selector-controller"
    control.mkdir()
    c.seal(control / "release.json", release)
    c.seal(control / "candidate-handles.json", dict(
        context_id=context["context_id"], discovery_sha256=c.sha(root / "discovery/discovery.json"),
        public_sha256=c.digest(public), handles=handles))
    session = dict(schema="isaforge-ascon-native-selector-session-v1", status="ready",
        policy="codex_chat_llm_agent", provider="current Codex chat model; not isolated API provider",
        target=ascon.GROUP, context_id=context["context_id"], release_sha256=c.sha(Path(release_directory).resolve() / "release.json"),
        area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
        max_candidate_attempts=MAX_QUERIES, max_tool_calls=MAX_TOOL_CALLS,
        tool_calls=0, charged_attempts=0, attempted_handles=[], attempted_ids=[], attempts=[], observations=[],
        finalized=None, model_fit_seconds=0.0, model_inference_seconds=0.0,
        request_to_action_wall_seconds=None, llm_model_only_seconds=None, llm_token_count=None,
        cost_scopes="Native evaluator, model fit/inference, and request/action relay are separate; model-only latency and token use unavailable from current Codex chat.")
    _durable_seal(control / "session.json", session)
    _durable_seal(control / "session-events.json", {"events": []})
    return dict(root=str(root), context_id=context["context_id"], candidates=len(handles),
                charged_attempts=0, native_jobs=0)


@contextmanager
def _session_lock(root: Path):
    path = Path(root) / "selector-controller/.session.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Selector session already active") from None
        yield


def _load_campaign(root: Path, release_directory: Path = RELEASE_DEFAULT, *,
                   allow_inflight: bool = False) -> tuple[dict, list[dict], list[dict], dict]:
    release = authenticate_release(release_directory)
    root = Path(root).resolve()
    with ascon.registration():
        plan = guarded.authenticate_plan(root)
    protocol = c.unseal(root / "evaluation-protocol.json")
    _require(protocol["context_id"] == plan["context_id"] == release["target_context_id"] and
             protocol["maximum_candidate_attempts"] == 12 and
             protocol["attempts_per_candidate"] == 1 and
             c.sha(root / "evaluation-protocol.json") == release["evaluation_protocol_sha256"],
             "Generic guarded evaluator protocol differs from controller release")
    before = c.unseal(root / "before.json")
    for name, expected in before["artifacts"].items():
        _require(c.sha(root / name) == expected, "Frozen target baseline changed: " + name)
    control = root / "selector-controller"
    root_release = _read_seal(control / "release.json")
    binding = _read_seal(control / "candidate-handles.json")
    state = _read_seal(control / "session.json")
    public = c.unseal(root / "public.json")
    discovery = c.unseal(root / "discovery/discovery.json")
    handles = _candidate_map(public, discovery)
    _require(root_release == release and binding["handles"] == handles and
             binding["context_id"] == state["context_id"] == release["target_context_id"] and
             binding["discovery_sha256"] == c.sha(root / "discovery/discovery.json") and
             binding["public_sha256"] == c.digest(public) and
             state["release_sha256"] == c.sha(Path(release_directory).resolve() / "release.json"),
             "Campaign identity differs from committed controller release")
    events = _read_seal(control / "session-events.json")["events"]
    event_sequences = [row.get("sequence") for row in events]
    _require(event_sequences == list(range(1, len(events) + 1)) and
             len(events) <= state["tool_calls"] <= MAX_TOOL_CALLS and
             (allow_inflight or len(events) == state["tool_calls"]),
             "Controller tool-call journal differs from its event log")
    event_statuses = [row.get("status") for row in events]
    _require(all(status in TERMINAL_EVENT_STATUSES | INFLIGHT_EVENT_STATUSES
                 for status in event_statuses),
             "Controller event journal contains an invalid status")
    _require(allow_inflight or all(status not in INFLIGHT_EVENT_STATUSES
                                   for status in event_statuses),
             "Controller event journal has an unfinished call; recover before continuing")
    slots = sorted(control.glob("attempt-*.json"))
    slot_records = [_read_seal(path) for path in slots]
    state_attempts = state.get("attempts", [])
    _require(len(slot_records) <= MAX_QUERIES and
             [row.get("slot") for row in slot_records] == list(range(1, len(slot_records) + 1)) and
             state["charged_attempts"] == len(state_attempts) == len(state["attempted_handles"]) ==
             len(state.get("attempted_ids", [])) and
             (len(state_attempts) <= len(slot_records) if allow_inflight else
              len(state_attempts) == len(slot_records)),
             "Controller charge journal differs from durable reservations")
    by_handle = {row["handle"]: row for row in handles}
    record_handles = [row.get("handle") for row in slot_records]
    record_ids = [row.get("candidate_id") for row in slot_records]
    _require(state["attempted_handles"] == record_handles[:len(state["attempted_handles"])] and
             state.get("attempted_ids", []) == record_ids[:len(state.get("attempted_ids", []))],
             "Controller attempted identities differ from durable reservations")
    for index, (path, record) in enumerate(zip(slots, slot_records), 1):
        entry = by_handle.get(record.get("handle"))
        _require(path.name == f"attempt-{index:02d}.json" and entry is not None and
                 record.get("schema") == "isaforge-ascon-selector-attempt-v1" and
                 record.get("candidate_id") == entry["candidate_id"] and
                 record.get("name") == entry["name"] and
                 record.get("formula") == entry["formula"] and
                 record.get("context_id") == state["context_id"] and
                 record.get("release_sha256") == state["release_sha256"] and
                 record.get("status") in TERMINAL_ATTEMPT_STATUSES | {"started"},
                 "Durable attempt slot identity or terminal status differs")
        if index <= len(state_attempts):
            prior = state_attempts[index - 1]
            _require(prior.get("slot") == index and prior.get("handle") == record["handle"] and
                     prior.get("candidate_id") == record["candidate_id"] and
                     (prior.get("status") == record["status"] or
                      (allow_inflight and prior.get("status") == "started" and
                       record.get("status") in TERMINAL_ATTEMPT_STATUSES)),
                     "Controller attempt state differs from its durable slot")
            if record.get("outcome") is not None and prior.get("outcome_sha256") is not None:
                _require(prior["outcome_sha256"] == c.digest(record["outcome"]),
                         "Controller outcome digest differs from durable slot")
        elif not allow_inflight:
            _require(False, "Controller attempt state is missing a durable slot")

    if allow_inflight:
        reconciled = []
        for index, record in enumerate(slot_records, 1):
            prior = state_attempts[index - 1] if index <= len(state_attempts) else {}
            row = dict(slot=index, handle=record["handle"],
                       candidate_id=record["candidate_id"], status=record["status"])
            if record.get("outcome") is not None:
                row["outcome_sha256"] = c.digest(record["outcome"])
            if record.get("error_type"):
                row["error_type"] = record["error_type"]
            reconciled.append(row)
        state["attempts"] = reconciled
        state["charged_attempts"] = len(slot_records)
        state["attempted_handles"] = record_handles
        state["attempted_ids"] = record_ids
    else:
        _require(state["attempted_handles"] == record_handles and
                 state.get("attempted_ids", []) == record_ids and
                 all(row.get("status") != "started" for row in slot_records),
                 "Unresolved reservation requires explicit recovery before continuing")
        for record, event in zip(slot_records, events):
            if record.get("tool_sequence") is not None:
                matching = next((row for row in events
                                 if row.get("sequence") == record["tool_sequence"]), None)
                _require(matching is not None and
                         matching.get("status") == record.get("status"),
                         "Controller attempt event differs from its terminal slot")
        unknown = any(record.get("status") in {"unknown", "unknown_interrupted"} or
            (record.get("status") == "failed" and
             (record.get("outcome") or {}).get("failure_class") in FAILURE_UNKNOWN)
            for record in slot_records)
        _require(not unknown or state.get("status") != "ready",
                 "Unknown attempt requires recovery and a stopped selector session")
        _validate_paid_observation_prefix(state, slot_records, public)
    return state, handles, public, dict(release=release, events=events, control=control,
                                        slots=slot_records)


def _training() -> list[dict]:
    return c.unseal(PREREG / "selection/controls11/model/history.json")


def _validate_paid_observation_prefix(state: dict, slots: list[dict], public: list[dict]) -> None:
    """Bind model updates to the exact ordered outcomes in charged terminal slots."""
    public_by_id = {row["candidate_id"]: row for row in public}
    expected = []
    for slot in slots:
        outcome = slot.get("outcome")
        if slot.get("status") not in {"success", "failed"}:
            continue
        _require(isinstance(outcome, dict),
                 "Terminal measured attempt is missing its authenticated outcome")
        identity = slot.get("candidate_id")
        row = public_by_id.get(identity)
        _require(row is not None and outcome.get("candidate_id") == identity,
                 "Paid outcome identity differs from its frozen public candidate")
        valid = baseline.validate_outcome(outcome, row)
        _require((slot["status"] == "success" and valid) or
                 (slot["status"] == "failed" and not valid),
                 "Paid outcome status differs from its terminal attempt slot")
        expected.append(outcome)
    _require(c.digest(expected) == c.digest(state.get("observations", [])),
             "Model observations differ from the ordered terminal paid prefix")


def _prediction_tables(public: list[dict]) -> tuple[dict, dict]:
    selection = PREREG / "selection"
    models = next(row for row in c.unseal(selection / "controls11/model/predictions.json")
                  if row["seed"] == 0)
    feasibility = next(row for row in c.unseal(selection / "feasibility-predictions.json")
                       if row["seed"] == 0)["by_cap"][str(AREA_CAP)]
    utility = next(row for row in c.unseal(selection / "controls11/utility-predictions.json")
                   if row["seed"] == 0)["by_cap"][str(AREA_CAP)]
    tables = {name: {row["candidate_id"]: row for row in values}
              for name, values in models.items() if isinstance(values, list)}
    tables["feasibility"] = {row["candidate_id"]: row for row in feasibility}
    tables["utility"] = {row["candidate_id"]: row for row in utility}
    _require(all(len(table) == len(public) for table in tables.values()),
             "Frozen predictor tables must cover the exact target pool")
    return tables, {}


def _measured_public_row(public_row: dict, outcome: dict) -> dict:
    result = copy.deepcopy(outcome)
    result["workload_group"] = ascon.GROUP
    result["candidate_family"] = family(public_row["formula"])
    return result


def _eligible(outcome: dict) -> bool:
    return (outcome.get("status", "success") == "success" and
            outcome.get("correctness_verified") is True and
            outcome.get("device_fits") is True and
            outcome.get("timing_feasible") is True and
            outcome.get("area_delta_lut4", math.inf) <= AREA_CAP and
            outcome.get("routed_fmax_min_mhz", -math.inf) >= CLOCK_FLOOR_MHZ and
            outcome.get("speedup", 1.0) > 1.0)


class _CandidateCapableEvaluator(guarded.Evaluator):
    """Generic guarded processor path with Ascon KAT verification at the boundary."""
    def __init__(self, root: Path):
        with ascon.registration():
            ascon.check_plan(c.unseal(Path(root) / "plan.json"))
            super().__init__(root)

    def discover(self):
        with ascon.registration():
            result = super().discover()
        _require(result["baseline_performance"]["benchmark_result_u32"] == ascon.EXPECTED_RESULT_U32,
                 "Ascon baseline KAT fingerprint differs")
        return result

    def measure(self, name: str):
        with ascon.registration():
            if name != "baseline":
                discovery = self.discover()
                _require(name in {row["name"] for row in discovery["pool"]},
                         "Candidate handle did not resolve inside the frozen pool")
            result = super().measure(name)
        _require(result["performance"]["benchmark_result_u32"] == ascon.EXPECTED_RESULT_U32,
                 "Candidate changed the pinned Ascon KAT fingerprint")
        return result


def _audit_after_attempt(root: Path, handle: str) -> tuple[dict, dict]:
    with ascon.registration():
        audit = guarded_evidence.audit(root)
    binding = _read_seal(root / "selector-controller/candidate-handles.json")
    record = next(row for row in binding["handles"] if row["handle"] == handle)
    attempt = next((row for row in audit["outcomes"] if row.get("candidate_id") == record["candidate_id"]), None)
    _require(attempt is not None, "Guarded audit did not return the charged attempt")
    _require(audit["charged_candidate_attempts"] <= 12, "Generic native attempt limit exceeded")
    return attempt, audit


def _public_candidate(handle: str, binding: dict, public: list[dict], predictions: dict | None,
                      dynamic: dict | None) -> dict:
    entry = next(row for row in binding if row["handle"] == handle)
    row = next(row for row in public if row["candidate_id"] == entry["candidate_id"])
    identity = entry["candidate_id"]
    result = dict(handle=handle, formula=row["formula"], public_features={k: copy.deepcopy(v)
        for k, v in row.items() if k not in ("candidate_id", "benchmark")})
    if predictions is not None:
        model = {name: copy.deepcopy(table[identity]) for name, table in predictions.items()}
        model["hybrid_gp_adaptive"] = copy.deepcopy(dynamic.get(identity)) if dynamic else None
        model["uncertainty_calibrated"] = False
        result["predictions"] = model
    return result


def _dynamic_gp(root: Path, state: dict, public: list[dict], prediction_tables: dict,
                handles: list[dict]) -> tuple[dict, float, float]:
    public_by_id = {row["candidate_id"]: row for row in public}
    successes = [row for row in state["observations"] if row.get("status") == "success"]
    successful_ids = [row.get("candidate_id") for row in successes]
    _require(len(set(successful_ids)) == len(successful_ids),
             "Successful paid-prefix identities must be unique")
    for outcome in successes:
        public_row = public_by_id.get(outcome.get("candidate_id"))
        _require(public_row is not None and baseline.validate_outcome(outcome, public_row),
                 "Adaptive GP input is not a verified successful paid outcome")
    # Bind the cache to the full verified result rows. Candidate IDs alone do
    # not identify the labels used by a refit and could return stale predictions.
    key = c.digest(successes)
    cache = state.get("adaptive_gp_cache")
    if cache and cache["paid_prefix_sha256"] == key:
        return cache["predictions"], 0.0, 0.0
    remaining = [row for row in public if row["candidate_id"] not in set(state["attempted_ids"])]
    if not successes:
        initial = prediction_tables["hardware"]
        return initial, 0.0, 0.0
    training = _training()
    started = time.monotonic()
    model = baseline.HardwareSurrogate().fit(training + successes)
    fit_seconds = time.monotonic() - started
    started = time.monotonic()
    predicted = model.predict(remaining if remaining else public)
    inference_seconds = time.monotonic() - started
    values = {row["candidate_id"]: row for row in predicted}
    for row in public:
        values.setdefault(row["candidate_id"], prediction_tables["hardware"][row["candidate_id"]])
    state["adaptive_gp_cache"] = dict(paid_prefix_sha256=key, predictions=values)
    state["model_fit_seconds"] += fit_seconds
    state["model_inference_seconds"] += inference_seconds
    return values, fit_seconds, inference_seconds


def _request_candidate_outputs(root: Path, state: dict, handles: list[dict], public: list[dict],
                               chosen_handles: list[str]) -> list[dict]:
    tables, _ = _prediction_tables(public)
    dynamic, _, _ = _dynamic_gp(root, state, public, tables, handles)
    by_handle = {entry["handle"]: entry for entry in handles}
    _require(len(by_handle) == len(handles) and all(handle in by_handle for handle in chosen_handles),
             "Prediction request contains an unknown candidate handle")
    return [_public_candidate(handle, handles, public, tables, dynamic)
            for handle in chosen_handles]


def _validate_postpush(release: dict) -> None:
    _require(release["dispatch_gate"]["branch"] == _git("branch", "--show-current") == "ai-guided-ml",
             "Candidate measurement requires branch ai-guided-ml")
    _require(_git("rev-parse", "HEAD") == _git("rev-parse", "refs/remotes/origin/ai-guided-ml"),
             "Candidate measurement requires the exact source release pushed to origin")
    for name, expected in {**release["source_bindings"], **release["input_bindings"]}.items():
        result = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT,
                                capture_output=True, check=False)
        _require(result.returncode == 0 and hashlib.sha256(result.stdout).hexdigest() == expected,
                 "Required release input is not in pushed HEAD: " + name)
        _require(not _git("status", "--porcelain", "--", name),
                 "Required release input has uncommitted changes: " + name)


def _handle_row(handle: str, handles: list[dict], public: list[dict]) -> tuple[dict, dict]:
    row = next((item for item in handles if item["handle"] == handle), None)
    _require(row is not None, "Unknown/stale candidate handle; no evaluation charged")
    public_row = next(item for item in public if item["candidate_id"] == row["candidate_id"])
    _require(public_row["formula"] == row["formula"], "Candidate handle formula binding differs")
    return row, public_row


def _write_state(control: Path, state: dict, events: list[dict]) -> None:
    _durable_seal(control / "session.json", state)
    _durable_seal(control / "session-events.json", {"events": events})


def _reserve_candidate(state: dict, entry: dict, control: Path, release_sha256: str,
                       tool_sequence: int) -> dict:
    """Durably reserve one query before state mutation or evaluator dispatch."""
    handle = entry["handle"]
    _require(handle not in state["attempted_handles"],
             "Candidate already attempted; no retry and no new query charged")
    _require(state["charged_attempts"] < MAX_QUERIES, "Three-query budget exhausted")
    slot = state["charged_attempts"] + 1
    reservation = dict(schema="isaforge-ascon-selector-attempt-v1", slot=slot,
        handle=handle, candidate_id=entry["candidate_id"], name=entry["name"],
        formula=entry["formula"], context_id=state["context_id"],
        release_sha256=release_sha256, tool_sequence=tool_sequence, status="started",
        reserved_at_monotonic_ns=time.monotonic_ns())
    path = control / f"attempt-{slot:02d}.json"
    _require(not path.exists(), "Attempt slot already exists; never retry")
    _durable_seal(path, reservation)
    state["charged_attempts"] = slot
    state["attempted_handles"].append(handle)
    state["attempted_ids"].append(entry["candidate_id"])
    state["attempts"].append(dict(slot=slot, handle=handle,
        candidate_id=entry["candidate_id"], status="started"))
    return reservation


def call(root: Path, action: dict, *, release_directory: Path = RELEASE_DEFAULT) -> dict:
    """Execute one allowlisted agent action; only ``measure`` reaches native tools."""
    root = Path(root).resolve()
    with _session_lock(root):
        state, handles, public, meta = _load_campaign(root, release_directory)
        events = meta["events"]
        if state["status"] != "ready":
            return dict(status="error", error="Selector session is closed; no retry or continuation.")
        if state["tool_calls"] >= MAX_TOOL_CALLS:
            state["status"] = "tool_limit"
            _write_state(meta["control"], state, events)
            return dict(status="error", error="Tool-call limit reached.")
        state["tool_calls"] += 1
        event = dict(sequence=state["tool_calls"], action=copy.deepcopy(action),
                     status="started", charged_before=state["charged_attempts"])
        events.append(event)
        _write_state(meta["control"], state, events)
        reserved = False
        try:
            _require(isinstance(action, dict) and set(action) == {"tool", "arguments"} and
                     isinstance(action["arguments"], dict),
                     "Expected one tool and an arguments object.")
            tool, args = action["tool"], action["arguments"]
            if tool == "list_candidates" and args == {}:
                result = dict(status="ok", candidates=[_public_candidate(row["handle"], handles, public,
                    _prediction_tables(public)[0], None) for row in handles],
                    constraints=dict(area_delta_lut4_cap=AREA_CAP,
                        minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
                        remaining_attempts=MAX_QUERIES-state["charged_attempts"]))
            elif tool == "predict" and set(args) == {"handles"} and isinstance(args["handles"], list):
                selected = args["handles"]
                _require(selected and len(set(selected)) == len(selected) and
                         all(type(item) is str for item in selected),
                         "predict requires unique candidate handles")
                for handle in selected:
                    _handle_row(handle, handles, public)
                candidates = _request_candidate_outputs(root, state, handles, public, selected)
                result = dict(status="ok", candidates=candidates, paid_successes=sum(
                    row.get("status", "success") == "success" for row in state["observations"]),
                    uncalibrated_uncertainty=True)
            elif tool == "measure" and set(args) == {"handle"} and type(args["handle"]) is str:
                handle = args["handle"]
                entry, _ = _handle_row(handle, handles, public)
                _require(handle not in state["attempted_handles"],
                         "Candidate already attempted; no retry and no new query charged")
                _require(state["charged_attempts"] < MAX_QUERIES, "Three-query budget exhausted")
                _validate_postpush(meta["release"])
                reservation = _reserve_candidate(state, entry, meta["control"],
                    c.sha(Path(release_directory).resolve() / "release.json"), event["sequence"])
                reserved = True
                path = meta["control"] / f"attempt-{reservation['slot']:02d}.json"
                event.update(status="reserved", charged_attempt=reservation["slot"],
                             candidate_handle=handle)
                _write_state(meta["control"], state, events)
                started = time.monotonic()
                evaluator = None
                try:
                    evaluator = _CandidateCapableEvaluator(root)
                    try:
                        evaluator.measure(entry["name"])
                    finally:
                        evaluator.runner.lock.close()
                        evaluator = None
                    measured, audit = _audit_after_attempt(root, handle)
                    measured = _measured_public_row(
                        next(row for row in public if row["candidate_id"] == entry["candidate_id"]), measured)
                    outcome_status = measured.get("status", "success")
                    _require(outcome_status in {"success", "failed"},
                             "Guarded audit returned a nonterminal candidate outcome")
                    reservation.update(status=outcome_status, outcome=measured,
                        audit_sha256=c.digest(audit), controller_elapsed_seconds=time.monotonic()-started)
                    state["attempts"][-1].update(status=outcome_status,
                        outcome_sha256=c.digest(measured))
                    state["observations"].append(measured)
                    if outcome_status == "success":
                        state.pop("adaptive_gp_cache", None)
                        result = dict(status="ok", observation={
                            "handle": handle, "formula": entry["formula"],
                            "baseline_cycles": measured["baseline_cycles"],
                            "candidate_cycles": measured["candidate_cycles"],
                            "speedup": measured["speedup"],
                            "added_lut4": measured["area_delta_lut4"],
                            "routed_fmax_min_mhz": measured["routed_fmax_min_mhz"],
                            "correctness_verified": measured["correctness_verified"],
                            "measurement_seconds": measured["measurement_seconds"],
                            "device_fits": measured["device_fits"],
                            "timing_feasible": measured["timing_feasible"]})
                    else:
                        result = dict(status="failed", handle=handle,
                            failure_class=measured.get("failure_class"),
                            measurement_seconds=measured.get("measurement_seconds"),
                            numeric_update=False)
                        if measured.get("failure_class") in FAILURE_UNKNOWN:
                            state["status"] = "stopped_unknown_outcome"
                    _durable_seal(path, reservation)
                except BaseException as error:
                    if evaluator is not None:
                        try:
                            evaluator.runner.lock.close()
                        except Exception:
                            pass
                    reservation.update(status="unknown", error_type=type(error).__name__,
                                       controller_elapsed_seconds=time.monotonic()-started)
                    state["attempts"][-1].update(status="unknown", error_type=type(error).__name__)
                    _durable_seal(path, reservation)
                    state["status"] = "stopped_unknown_outcome"
                    event.update(status="unknown", error_type=type(error).__name__)
                    _write_state(meta["control"], state, events)
                    if not isinstance(error, Exception):
                        raise
                    return dict(status="error", error="Attempt remains charged; session stopped without retry.")
                event["status"] = reservation["status"]
                event["public_result"] = result
            elif tool == "finalize" and set(args) == {"handle", "summary"}:
                handle, summary = args["handle"], args["summary"]
                _require(handle is None or type(handle) is str,
                         "finalize handle must be a paid handle or null")
                _require(isinstance(summary, str) and 0 < len(summary) <= 500,
                         "finalize summary must be 1..500 characters")
                if handle is not None:
                    _handle_row(handle, handles, public)
                    _require(handle in state["attempted_handles"],
                             "Only a paid candidate can be finalized")
                    candidate_id = next(x["candidate_id"] for x in handles if x["handle"] == handle)
                    outcome = next((row for row in state["observations"]
                                    if row.get("candidate_id") == candidate_id), None)
                    _require(outcome is not None and _eligible(outcome),
                             "Final candidate must be paid, correct, feasible, and improve speedup")
                state["finalized"] = dict(handle=handle, summary=summary)
                state["status"] = "finalized"
                best = max([1.0] + [row["speedup"] for row in state["observations"] if _eligible(row)])
                result = dict(status="ok", finalized=state["finalized"],
                              best_verified_feasible_speedup=best,
                              charged_attempts=state["charged_attempts"])
                event.update(status="finalized", public_result=result)
            else:
                _require(False,
                         "Only list_candidates, predict, measure and finalize are allowed.")
        except Exception as error:
            if reserved:
                # An error after a durable reservation is never rewritten as a
                # free rejection. Leave recovery to conservatively close it.
                raise
            event.update(status="rejected" if isinstance(error, ValueError) else "error",
                         error_type=type(error).__name__, error=str(error))
            _write_state(meta["control"], state, events)
            return dict(status="error", error=str(error))

        if event.get("status") == "started":
            event["status"] = "complete"
        event["public_result"] = copy.deepcopy(result)
        _write_state(meta["control"], state, events)
        return result


def request(root: Path, *, release_directory: Path = RELEASE_DEFAULT) -> dict:
    """Return the complete public state for one current-chat model action."""
    root = Path(root).resolve()
    with _session_lock(root):
        state, handles, public, _ = _load_campaign(root, release_directory)
        _require(state["status"] == "ready", "Selector session is closed")
        predictions, _ = _prediction_tables(public)
        candidates = [_public_candidate(row["handle"], handles, public, predictions, None)
                      for row in handles]
        return dict(schema="isaforge-ascon-native-selector-request-v1",
        instructions=("Choose an action using only this state and the four allowlisted tools. "
            "Predictions are not measurements. Keep the baseline unless a paid, correct, "+
            "area/timing-feasible candidate improves whole-program speedup. Each valid "+
            "unattempted measure action consumes one query before PicoRV32 evaluation. "
            "Unknown/interrupted attempts stop; never retry. The candidate pool is related-domain crypto transfer, not independent-family confirmation."),
        scope="prospective same-domain Ascon transfer", policy=state["policy"],
        constraints=dict(area_delta_lut4_cap=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_FLOOR_MHZ,
                         remaining_candidate_attempts=MAX_QUERIES-state["charged_attempts"],
                         remaining_tool_calls=MAX_TOOL_CALLS-state["tool_calls"]),
        training=dict(successful_family_filtered_labels=90, historical_workload_groups=14,
            related_rows_excluded=32, charged_historical_attempts=126,
            training_labels_used="whole-program measured cycle speedup and integrated hardware outcomes"),
        candidates=candidates, observations=[dict(handle=next(x["handle"] for x in handles
            if x["candidate_id"]==row["candidate_id"]), **{k:v for k,v in row.items() if k not in
            ("candidate_id", "benchmark", "workload_group", "candidate_family")})
            for row in state["observations"]], attempted_handles=state["attempted_handles"],
        tool_actions=[{"tool":"list_candidates","arguments":{}},
            {"tool":"predict","arguments":{"handles":["C01"]}},
            {"tool":"measure","arguments":{"handle":"C01"}},
            {"tool":"finalize","arguments":{"handle":None,"summary":"retain baseline"}}],
        uncertainty_calibrated=False,
        cost_scopes={"candidate_evaluation":"native evaluator/attempt ledger", "model_fit_and_inference":"controller host timers",
                     "llm_model_only":"unavailable from current chat", "request_to_action":"not separately metered by this request API"})


def recover_interrupted(root: Path, *, release_directory: Path = RELEASE_DEFAULT) -> dict:
    """Mark any durable in-flight selector slot unknown and prohibit all retries."""
    root = Path(root).resolve()
    with _session_lock(root):
        state, handles, public, meta = _load_campaign(root, release_directory, allow_inflight=True)
        events = meta["events"]
        observations = {row.get("candidate_id"): row for row in state["observations"]}
        for index, original in enumerate(meta["slots"], 1):
            attempt = copy.deepcopy(original)
            path = meta["control"] / f"attempt-{index:02d}.json"
            if attempt.get("status") == "started":
                attempt.update(status="unknown_interrupted", recovered_at_utc=time.time())
                _durable_seal(path, attempt)
            status = attempt["status"]
            state_row = state["attempts"][index - 1]
            state_row.update(status=status)
            if attempt.get("outcome") is not None:
                state_row["outcome_sha256"] = c.digest(attempt["outcome"])
            if attempt.get("error_type"):
                state_row["error_type"] = attempt["error_type"]

            outcome = attempt.get("outcome")
            if status in {"success", "failed"} and outcome is not None:
                prior = observations.get(attempt["candidate_id"])
                _require(prior is None or c.digest(prior) == c.digest(outcome),
                         "Recovered outcome differs from the session observation")
                if prior is None:
                    state["observations"].append(outcome)
                    observations[attempt["candidate_id"]] = outcome
            else:
                state["observations"] = [row for row in state["observations"]
                    if row.get("candidate_id") != attempt["candidate_id"]]
                observations.pop(attempt["candidate_id"], None)

            sequence = attempt.get("tool_sequence")
            event = next((row for row in events if row.get("sequence") == sequence), None)
            if event is None:
                # The reservation file is written only after the measure event
                # has been durably appended. Missing it means the journal write
                # was interrupted; preserve the charged attempt and stop.
                state["status"] = "stopped_unknown_outcome"
                sequence = sequence if type(sequence) is int else max(
                    [row.get("sequence", 0) for row in events] + [0]) + 1
                event = dict(sequence=sequence,
                    action={"tool": "measure", "arguments": {"handle": attempt["handle"]}},
                    status=status, charged_before=index - 1, charged_attempt=index,
                    candidate_handle=attempt["handle"], recovered=True)
                events.append(event)
                events.sort(key=lambda row: row["sequence"])
            else:
                _require(event.get("candidate_handle") in (None, attempt["handle"]),
                         "Recovered event points to a different candidate")
                event.update(status=status, charged_attempt=index,
                             candidate_handle=attempt["handle"], recovered=True)
            if status == "unknown_interrupted" or status == "unknown" or (
                    status == "failed" and (outcome or {}).get("failure_class") in FAILURE_UNKNOWN):
                state["status"] = "stopped_unknown_outcome"
                event["public_result"] = dict(status="error",
                    error="Attempt remains charged; session stopped without retry.")
            elif outcome is not None:
                event["public_result"] = dict(status=status, recovered=True,
                                              outcome=copy.deepcopy(outcome))

        for event in events:
            if event.get("status") not in INFLIGHT_EVENT_STATUSES:
                continue
            has_slot = any(slot.get("tool_sequence") == event.get("sequence")
                           for slot in meta["slots"])
            if has_slot:
                continue
            result = event.get("public_result")
            action = event.get("action") or {}
            tool = action.get("tool") if isinstance(action, dict) else None
            if (tool in {"list_candidates", "predict"} and isinstance(result, dict) and
                    result.get("status") == "ok"):
                # The durable public response proves the read-only action
                # completed; repair only its event marker during recovery.
                event.update(status="complete", recovered=True)
            else:
                # An interrupted call without a durable result is never
                # replayed. Stop conservatively while preserving its charge.
                event.update(status="unknown_interrupted", recovered=True,
                             reason="event had no durable terminal result")
                state["status"] = "stopped_unknown_outcome"

        recovered_slots = [_read_seal(meta["control"] / f"attempt-{index:02d}.json")
                           for index in range(1, len(meta["slots"]) + 1)]
        _validate_paid_observation_prefix(state, recovered_slots, public)
        if len(events) != state["tool_calls"]:
            # A call may have updated the session counter before the event
            # journal reached disk. Never silently erase that audit gap.
            state["status"] = "stopped_unknown_outcome"
            existing = {row["sequence"] for row in events}
            for sequence in range(1, state["tool_calls"] + 1):
                if sequence not in existing:
                    events.append(dict(sequence=sequence, status="unknown_interrupted",
                        action=None, recovered=True, reason="event journal was incomplete"))
            events.sort(key=lambda row: row["sequence"])
        _write_state(meta["control"], state, events)
        return dict(status=state["status"], charged_attempts=state["charged_attempts"])
