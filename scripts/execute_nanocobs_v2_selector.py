"""Release, run, and score the frozen nanocobs-v2 instruction-selection study.

The LLM episode runs first and measures candidates one at a time. The remaining
pool is collected only after the agent finalizes, to build a measured oracle.
The later fixed-policy trajectories use a callback that reveals only each
policy's charged observations. They are offline counterfactuals, not free
physical evaluations.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import agent_memory, bounded_selector, campaign_evidence as evidence
from isaforge import codesign as c
from isaforge import current_grouped_predictions as grouped
from isaforge import factorized_selection_experiment as factorized
from isaforge import guarded_attempts as attempts
from isaforge import guarded_evidence, guarded_workload as guarded
from isaforge import nanocobs_v2_workload as workload
from isaforge.codex_chat_selector import CodexChatSelectionProvider
from isaforge.routed_selection import summarize_model_events
from scripts.prepare_nanocobs_v2_selector import (OUTPUT as PREREG, SOURCES,
    authenticate as authenticate_prereg)
from scripts.reproduce_codesign import pack_archive, restore_archive
from scripts.export_agent_observability import export as export_agent_observability


SOURCE = "scripts/execute_nanocobs_v2_selector.py"
QUALIFICATION = ROOT / "results/2026-10-28-nanocobs-v2-qualification-r1"
STUDY = ROOT / "generated/nanocobs-v2-selection-study-r1"
NATIVE = STUDY / "native"
RELEASE = STUDY / "release.json"
RESULTS = ROOT / "results/2026-10-28-nanocobs-v2-selection-r1"
BRANCH = "ai-guided-ml"
AREA_CAP = 64
CLOCK_MHZ = 12.0
BUDGET = 3
MAX_MODEL_CALLS = 12
MAX_TOOL_CALLS = 20

EXECUTION_SOURCES = tuple(dict.fromkeys((*SOURCES, SOURCE)))


def require(condition, message):
    c.require(bool(condition), message)


def _git(*args, check=True):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    if check:
        require(result.returncode == 0, "Git command failed: " + " ".join(args[:2]))
    return result


def _commit_file(commit, path):
    shown = _git("show", f"{commit}:{path}", check=False)
    require(shown.returncode == 0, "Prelabel commit is missing: " + path)
    return hashlib.sha256(shown.stdout).hexdigest()


def _remote_head():
    result = _git("ls-remote", "origin", f"refs/heads/{BRANCH}")
    fields = result.stdout.decode().strip().split()
    require(len(fields) == 2 and fields[1] == f"refs/heads/{BRANCH}",
            "Expected exact pushed prelabel branch head")
    return fields[0]


def _inventory(folder):
    folder = Path(folder).resolve()
    return {path.relative_to(folder).as_posix(): c.sha(path)
            for path in sorted(folder.rglob("*")) if path.is_file() and
            path.name not in ("manifest.json", "manifest.json.sha256")}


def _archive_inventory(folder):
    folder = Path(folder).resolve()
    return {path.relative_to(folder).as_posix(): c.sha(path)
            for path in sorted(folder.rglob("*")) if path.is_file() and
            "obj_dir" not in path.parts and path.name != ".native.lock"}


def _verify_committed_prereg(commit, *, dispatch=True):
    prereg = authenticate_prereg(PREREG, verify_live_sources=dispatch)
    require(_git("cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode == 0,
            "Frozen prelabel commit is not available locally")
    if dispatch:
        require(_git("rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip() == BRANCH,
                "Candidate measurements require the ai-guided-ml branch")
        require(_git("rev-parse", "HEAD").stdout.decode().strip() == commit == _remote_head(),
                "Local and pushed branch must equal the frozen prelabel commit")
        dirty = _git("status", "--porcelain", "--untracked-files=no", "--", *EXECUTION_SOURCES,
                     PREREG.relative_to(ROOT).as_posix()).stdout.decode().strip()
        require(not dirty, "Frozen source or preregistration has tracked changes")
    require(_git("ls-tree", "-r", "--name-only", commit, "--",
                 PREREG.relative_to(ROOT).as_posix()).returncode == 0,
            "Committed preregistration tree unavailable")
    entries = c.unseal(PREREG / "manifest.json")
    for relative, expected in entries.items():
        repo_path = (PREREG / relative).relative_to(ROOT).as_posix()
        require(_commit_file(commit, repo_path) == expected,
                "Pushed commit differs from preregistration artifact: " + relative)
    for path, expected in prereg["source_bindings"].items():
        require(_commit_file(commit, path) == expected,
                "Pushed source differs from frozen prelabel source: " + path)
    for path, expected in prereg["input_bindings"].items():
        require(_commit_file(commit, path) == expected,
                "Pushed source differs from frozen model input: " + path)
    for path, expected in prereg["evidence_bindings"].items():
        require(_commit_file(commit, path) == expected,
                "Pushed commit differs from frozen evidence: " + path)
    return prereg


def _verify_release(*, dispatch=True, native_root=NATIVE, receipt_path=RELEASE):
    require(Path(receipt_path).is_file(), "Run the release command after committing and pushing preregistration")
    record = c.unseal(receipt_path)
    require(record.get("schema") == "isaforge-nanocobs-v2-selection-release-v1" and
            record.get("candidate_attempts_at_release") == 0 and
            record.get("target_labels_at_release") == 0,
            "Zero-label target release receipt required")
    prereg = _verify_committed_prereg(record["prelabel_commit"], dispatch=dispatch)
    require(record["preregistration_manifest_sha256"] == c.sha(PREREG / "manifest.json") and
            record["target_context_id"] == prereg["target_context_id"] and
            record["source_bindings"] == prereg["source_bindings"] and
            record["pushed_remote_head"] == record["prelabel_commit"] and
            record["restored_qualification_archive_sha256"] == c.sha(QUALIFICATION / "raw.tar.gz"),
            "Release receipt does not match preregistration")
    workload.validate_inputs(native_root)
    discovery = _discover_target(native_root)
    require([row["name"] for row in discovery["pool"]] == record["pool_names"] and
            len(record["pool_names"]) == prereg["target_public_pool_size"],
            "Released target candidate pool differs")
    _require_release_roster(prereg, record, discovery)
    return prereg, record, discovery


def _require_release_roster(prereg, record, discovery):
    roster = [dict(name=r['name'], candidate_id=r['candidate_id'], formula=r['formula'])
              for r in discovery['pool']]
    require(record['pool_roster'] == roster and
            [r['candidate_id'] for r in roster] == prereg['target_candidate_ids'] and
            discovery['context_id'] == record['target_context_id'],
            'Released candidate IDs, formulas or context differ')


@contextmanager
def _target_registration():
    """Use the generic guarded evaluator under the pinned nanocobs-v2 context."""
    with workload.registration():
        yield


def _discover_target(root):
    with _target_registration():
        return guarded.authenticate_discovery(root)


def _audit_target(root):
    with _target_registration():
        return guarded_evidence.audit(root)


class ReleaseBoundEvaluator(guarded.Evaluator):
    # Preserve the frozen workload's separate fixed reference/probe TUs on every
    # original, marked and candidate firmware link; bypass only baseline dispatch.
    compile_program = workload.Evaluator.compile_program

    def discover(self):
        with _target_registration():
            return super().discover()

    def measure(self, name):
        started = time.monotonic()
        if name != "baseline":
            _, release_record, discovery = _verify_release()
            require(name in {row['name'] for row in discovery['pool']},
                    'Candidate outside signed actual pool')
        try:
            with _target_registration():
                return super().measure(name)
        finally:
            if name != "baseline":
                pool = _discover_target(NATIVE)["pool"]
                candidate = next((row for row in pool if row["name"] == name), None)
                if candidate is not None:
                    state_path = attempts.ledger_path(NATIVE, name)
                    timer_path = STUDY / "outer-times" / (candidate["candidate_id"] + ".json")
                    if state_path.is_file() and not timer_path.exists():
                        state = attempts.read_attempt(NATIVE, name)
                        if state["status"] in ("success", "failed", "interrupted"):
                            _seal_outer_time(candidate["candidate_id"], time.monotonic()-started,
                                             state.get("started_at_utc"), state["status"])


def release():
    require(not STUDY.exists(), "Preserve prior study/native roots")
    commit = _git("rev-parse", "HEAD").stdout.decode().strip()
    prereg = _verify_committed_prereg(commit)
    archive = c.unseal(QUALIFICATION / "archive-manifest.json")
    (ROOT / "generated").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nanocobs-v2-release-stage-", dir=ROOT / "generated") as temp:
        staged = Path(temp) / "native"
        restore_archive(QUALIFICATION, archive, staged)
        workload.validate_inputs(staged)
        workload.require_zero_candidates(staged)
        discovery = _discover_target(staged)
        require(len(discovery["pool"]) == prereg["target_public_pool_size"] and
                not list((staged / "attempt-ledger").glob("candidate_*.json")),
                "Fresh actual-pool native baseline required")
        # Finish all fallible source and discovery checks before creating the
        # permanent one-shot study root.
        STUDY.mkdir(parents=True)
        shutil.move(str(staged), str(NATIVE))
    record = dict(schema="isaforge-nanocobs-v2-selection-release-v1",
        released_at_utc=datetime.now(timezone.utc).isoformat(),
        prelabel_commit=commit, pushed_remote_head=_remote_head(), branch=BRANCH,
        preregistration=str(PREREG.relative_to(ROOT)),
        preregistration_manifest_sha256=c.sha(PREREG / "manifest.json"),
        target_context_id=prereg["target_context_id"], pool_names=[row["name"] for row in discovery["pool"]],
        pool_roster=[dict(name=r['name'], candidate_id=r['candidate_id'], formula=r['formula'])
                     for r in discovery['pool']],
        candidate_attempts_at_release=0, target_labels_at_release=0,
        candidate_attempts=0, source_bindings=prereg["source_bindings"],
        restored_qualification_archive_sha256=c.sha(QUALIFICATION / "raw.tar.gz"),
        status="released after exact local/remote commit verification")
    c.seal(RELEASE, record)
    return record


def _evaluator():
    _verify_release()
    with _target_registration():
        return ReleaseBoundEvaluator(NATIVE)


def _target_maps(prereg):
    public = c.unseal(PREREG / "inputs/public.json")
    discovery = _discover_target(NATIVE)
    by_id = {row["candidate_id"]: row["name"] for row in discovery["pool"]}
    require(set(by_id) == {row["candidate_id"] for row in public},
            "Frozen public pool and native discovery identities differ")
    return public, by_id


def _live_outcome(evaluator, public_row, name):
    """Charge one native outcome and expose only its verified projection."""
    try:
        record = evaluator.measure(name)
    except Exception as error:
        state_path = attempts.ledger_path(NATIVE, name)
        require(state_path.is_file(), "Failed dispatch has no charged attempt ledger")
        state = attempts.read_attempt(NATIVE, name)
        require(state["status"] == "failed",
                "Only terminal failures may be returned to the selector")
        elapsed = state["elapsed_seconds"]
        failure = guarded_evidence._failure(state, NATIVE / "measurements" / name)
        return dict(public_row, status="failed", error="Measured attempt failed; no usable label.",
                    failure_class=failure["classification"],
                    measurement_seconds=elapsed,
                    reference_censored=failure["reference_censored"])
    state = attempts.read_attempt(NATIVE, name)
    require(state["status"] == "success", "Successful outcome needs a successful host ledger")
    baseline = c.unseal(NATIVE / "measurements/baseline/measurement.json")
    row = evidence._outcome(public_row, record, baseline)
    row["measurement_record_seconds"] = record["elapsed_seconds"]
    row["measurement_seconds"] = state["elapsed_seconds"]
    row["measurement_source"] = "synthesis_estimate"
    require(bounded_selector.b.validate_outcome(row, public_row),
            "Host measurement projection failed target outcome validation")
    return row


def _seal_outer_time(candidate_id, seconds, started, status):
    folder = STUDY / "outer-times"
    folder.mkdir(exist_ok=True)
    path = folder / (candidate_id + ".json")
    require(not path.exists(), "Preserve prior candidate outer timer")
    c.seal(path, dict(schema="isaforge-nanocobs-v2-candidate-outer-time-v1",
        candidate_id=candidate_id, started_at_utc=started,
        elapsed_seconds=seconds, status=status,
        scope="In-process wrapper around release verification and one guarded measurement call."))


def _agent_attempt_costs(native_root, study_root, native_job_ids, names, returned_ids):
    """Account for every charged native attempt, including undisclosed results."""
    attempts_rows, outer_values = [], []
    for identity in sorted(native_job_ids):
        require(identity in names, "Charged native attempt is outside the released candidate map")
        state = attempts.read_attempt(native_root, names[identity])
        elapsed = state.get("elapsed_seconds")
        timer_path = Path(study_root) / "outer-times" / (identity + ".json")
        timer = c.unseal(timer_path) if timer_path.is_file() else None
        if timer is not None:
            require(timer.get("candidate_id") == identity and
                    timer.get("status") == state["status"] and
                    type(timer.get("elapsed_seconds")) in (float, int) and
                    timer["elapsed_seconds"] >= 0 and
                    (elapsed is None or timer["elapsed_seconds"] >= elapsed),
                    "Agent outer timer differs from its durable native attempt")
            outer_values.append((identity, timer["elapsed_seconds"]))
        attempts_rows.append(dict(candidate_id=identity, name=names[identity],
            status=state["status"], measurement_seconds=elapsed,
            outer_operation_seconds=(timer["elapsed_seconds"] if timer else None),
            outcome_returned_to_selector=identity in returned_ids))
    known_measurements = sum(row["measurement_seconds"] for row in attempts_rows
                             if row["measurement_seconds"] is not None)
    measurement_unknown = [row["candidate_id"] for row in attempts_rows
                           if row["measurement_seconds"] is None]
    known_outer = sum(value for _, value in outer_values)
    outer_unknown = [row["candidate_id"] for row in attempts_rows
                     if row["outer_operation_seconds"] is None]
    return dict(attempts=attempts_rows,
        known_measurement_seconds=known_measurements,
        measurement_seconds=(None if measurement_unknown else known_measurements),
        measurement_time_complete=not measurement_unknown,
        measurement_time_unknown_ids=measurement_unknown,
        known_outer_operation_seconds=known_outer,
        outer_operation_seconds=(None if outer_unknown else known_outer),
        outer_operation_time_complete=not outer_unknown,
        outer_operation_time_unknown_ids=outer_unknown)


def _require_interactive_relay(stream=None):
    stream = sys.stdin if stream is None else stream
    isatty = getattr(stream, "isatty", None)
    require(callable(isatty) and isatty(),
            "Agent relay requires an interactive PTY; no episode was started")


class ProspectiveLiveSelectionSession(bounded_selector.ReplaySelectionSession):
    """Keep the tested allowlist/ledger while correcting replay-only framing."""

    def __init__(self, *args, **kwargs):
        self.live_native_jobs = 0
        super().__init__(*args, **kwargs)
        self.ledger["scope"] = "prospective live measurement on a source- and exact-family-held-out workload"
        self.ledger["new_native_jobs"] = 0
        self.ledger["timer_scope"] = (
            "Live selection session elapsed time; overlaps model response, local retrieval, and hardware measurement.")
        self._persist()

    def request(self):
        request = super().request()
        request["scope"] = self.ledger["scope"]
        old = "This is consumed-data replay, not fresh hardware measurement or an unseen-workload experiment."
        new = ("This is a prospective live hardware-measurement session on a new workload group. "
               "The target source and exact operator-tree families are excluded from training; "
               "this is one full original 8,215-case nanocobs differential probe and does not establish broad workload generalization. "
               "Each measure action triggers one real, one-attempt target evaluation.")
        require(old in request["instructions"], "Replay prompt wording changed; review prospective adapter")
        request["instructions"] = request["instructions"].replace(old, new)
        return request

    def _persist(self):
        super()._persist()
        self.ledger["new_native_jobs"] = self.live_native_jobs
        self.ledger["timer_scope"] = (
            "Live selection session elapsed time; overlaps model response, local retrieval, and hardware measurement.")
        self.ledger["returned_observation_measurement_seconds"] = sum(
            event.get("observation", {}).get("measurement_seconds", 0)
            for event in self.ledger["events"] if "charged_attempt" in event)
        self.ledger.pop("replayed_target_measurement_seconds", None)
        c.seal(self.path, self.ledger)


def run_agent():
    _require_interactive_relay()
    prereg, release_record, _ = _verify_release()
    workload.require_zero_candidates(NATIVE)
    agent_dir = STUDY / "agent"
    require(not agent_dir.exists(), "Preserve prior LLM-agent episode")
    agent_dir.mkdir(parents=True)
    public, names = _target_maps(prereg)
    train = c.unseal(PREREG / "selection/controls11/model/history.json")
    bundles = c.unseal(PREREG / "agent-predictions.json")
    metadata = c.unseal(PREREG / "agent-model-metadata.json")
    bundle, model_metadata = bundles[0], metadata[0]
    require(bundle["seed"] == 0 and bundle["schema"] == grouped.GROUPED_PREDICTION_SCHEMA,
            "Frozen seed-zero agent model bundle required")
    live_model_metadata = copy.deepcopy(model_metadata)
    live_model_metadata["source_screen_scope"] = live_model_metadata["scope"]
    live_model_metadata["scope"] = (
        "prospective target-source and canonical operator-tree-family holdout; zero target labels at model freeze")
    _verify_release()
    c.seal(agent_dir / "execution-protocol.json", dict(
        schema="isaforge-nanocobs-v2-live-agent-episode-v1",
        prelabel_commit=release_record["prelabel_commit"],
        preregistration_manifest_sha256=release_record["preregistration_manifest_sha256"],
        target_labels_seen_by_model=0,
        policy="Codex chat relay with the seed-zero frozen pairwise/factorized predictions and split-scoped hybrid retrieval memory.",
        prediction_sha256=c.digest(bundle), model_metadata_sha256=c.digest(live_model_metadata),
        source_screen_metadata_sha256=c.digest(model_metadata),
        source_screen_scope=model_metadata["scope"],
        memory_mode="hybrid", memory_source="dynamically sized target-family-excluded measured historical rows",
        area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
        charged_measurement_budget=BUDGET, max_model_calls=MAX_MODEL_CALLS,
        max_tool_calls=MAX_TOOL_CALLS, target_outcomes_available_only_after_measure=True,
        provider="current Codex chat model through the local JSON bridge; exact model ID and token usage unavailable"))
    evaluator = _evaluator()
    outcomes = {}
    native_job_ids = set()

    def provider(row):
        identity = row["candidate_id"]
        require(identity in names and identity not in outcomes,
                "Only one first measurement per known candidate is allowed")
        try:
            value = _live_outcome(evaluator, row, names[identity])
            outcomes[identity] = value
            return value
        finally:
            # Count a native job from the persistent one-attempt ledger, even
            # when result projection raises after native dispatch began.
            state_path = attempts.ledger_path(NATIVE, names[identity])
            if state_path.is_file() and identity not in native_job_ids:
                attempts.read_attempt(NATIVE, names[identity])
                native_job_ids.add(identity)
                session.live_native_jobs = len(native_job_ids)
                session._persist()

    chat = CodexChatSelectionProvider(model_label="current Codex chat model; exact deployment ID unavailable",
        request_directory=agent_dir / "public-requests")
    policy = agent_memory.MemoryAugmentedPolicy(chat, mode="hybrid", top_k=3,
                                                 max_memory_bytes=40_000)
    session = ProspectiveLiveSelectionSession(public, train, None, provider,
        area_cap=AREA_CAP, clock_mhz=CLOCK_MHZ, budget=workload.effective_policy_budget(BUDGET, len(public)),
        max_tool_calls=MAX_TOOL_CALLS, ledger_path=agent_dir / "ledger.json",
        historical_available_rows=len(train),
        historical_attempt_seconds=c.unseal(PREREG / "inputs/cost-provenance.json")
            ["historical"]["candidate_wall_seconds"],
        grouped_predictions=bundle, grouped_model_metadata=live_model_metadata)
    try:
        result = bounded_selector.run_selector(session, policy, max_model_calls=MAX_MODEL_CALLS)
    finally:
        evaluator.runner.lock.close()
    require(session.finished and session.charged <= BUDGET,
            "LLM agent episode must end within its frozen attempt budget")
    require(session.ledger["status"] in ("finalized", "host_fallback"),
            "Agent episode must close through agent finalization or explicit host fallback")
    require(session.ledger.get("decision_rationale") == result.get("decision_rationale"),
            "Decision rationale differs from the authoritative host ledger")
    cost_accounting = _agent_attempt_costs(NATIVE, STUDY, native_job_ids, names, outcomes)
    session.ledger["native_attempt_cost_accounting"] = cost_accounting
    session._persist()
    observability_protocol = dict(
        schema="isaforge-nanocobs-v2-live-agent-observability-v1",
        target=workload.GROUP, target_context_id=prereg["target_context_id"],
        provider="codex-chat-bridge",
        model_label="current Codex chat model; exact deployment ID unavailable",
        prelabel_commit=release_record["prelabel_commit"],
        preregistration_manifest_sha256=release_record["preregistration_manifest_sha256"],
        budget=BUDGET, area_cap_lut4=AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
        memory=dict(mode="hybrid", corpus_rows=len(train), target_families_excluded=True,
            lexical="TF-IDF cosine", semantic="TF-IDF + truncated-SVD cosine",
            fusion="reciprocal-rank fusion; k=60",
            knowledge_graph="typed graph constructed and source-hashed; separate graph mode is available but not queried in this episode",
            max_retrieved_bytes=40_000),
        tools=["list_candidates", "predict", "measure", "finalize"],
        model_routing="single current Codex chat model; no cross-provider routing or API model selection in this episode",
        telemetry="SQLite is a read-only analysis projection; sealed JSON ledger remains authoritative",
        token_usage="unavailable for current Codex chat bridge")
    c.seal(agent_dir / "protocol.json", observability_protocol)
    report = dict(schema="isaforge-nanocobs-v2-live-agent-report-v1",
        protocol_sha256=c.sha(agent_dir / "protocol.json"),
        target_workload=workload.GROUP, target_context_id=prereg["target_context_id"],
        status=result["status"], provider=policy.identity,
        seed=0, budget=BUDGET, charged_attempts=session.charged,
        new_native_jobs=session.live_native_jobs,
        live_session_elapsed_seconds=session.ledger["host_elapsed_seconds"],
        tool_calls=session.ledger["tool_calls"], provider_calls=session.ledger["provider_calls"],
        decision_elapsed_seconds=sum(event.get("elapsed_seconds", 0)
                                     for event in session.ledger["model_events"]),
        unique_target_labels_revealed_to_model=len(outcomes),
        attempted_candidate_ids=list(session.attempted_ids),
        budget_curve=session.ledger["curve"],
        runs=[dict(target=workload.GROUP, policy="codex-chat-bridge-hybrid-memory",
            status=result["status"], speedup=result.get("best_speedup", 1.0),
            charged_attempts=session.charged, ledger="ledger.json",
            ledger_sha256=c.sha(agent_dir / "ledger.json"))],
        selected_id=result.get("selected_id"), best_speedup=result.get("best_speedup"),
        decision_rationale=result.get("decision_rationale"),
        ledger_sha256=c.sha(agent_dir / "ledger.json"),
        model_events=session.ledger["model_events"],
        model_usage=summarize_model_events(session.ledger["model_events"])
            if any(event.get("provider_trace") for event in session.ledger["model_events"])
            else dict(model_decision_calls=len(session.ledger["model_events"]),
                token_usage_available=False, token_usage=None,
                reason="Current Codex chat relay does not expose provider token metadata"),
        memory_traces=[event.get("memory_trace") for event in session.ledger["model_events"]],
        target_outcomes=outcomes,
        actual_agent_measurement_seconds=cost_accounting["measurement_seconds"],
        known_agent_measurement_seconds=cost_accounting["known_measurement_seconds"],
        agent_measurement_time_complete=cost_accounting["measurement_time_complete"],
        agent_measurement_time_unknown_ids=cost_accounting["measurement_time_unknown_ids"],
        agent_outer_operation_seconds=cost_accounting["outer_operation_seconds"],
        known_agent_outer_operation_seconds=cost_accounting["known_outer_operation_seconds"],
        agent_outer_operation_time_complete=cost_accounting["outer_operation_time_complete"],
        agent_outer_operation_time_unknown_ids=cost_accounting["outer_operation_time_unknown_ids"],
        agent_attempt_costs=cost_accounting["attempts"],
        interpretation="One live interactive selection episode. Target measurements are real PicoRV32/synthesis results, but the agent is a current-chat relay, not an isolated API model or multi-seed estimate.")
    c.seal(agent_dir / "report.json", report)
    c.seal(agent_dir / "manifest.json", _inventory(agent_dir))
    observability_path = STUDY / "agent-observability.sqlite"
    observability_summary = export_agent_observability(agent_dir, observability_path)
    agent_database = agent_dir / "observability.sqlite"
    shutil.move(str(observability_path), str(agent_database))
    c.seal(agent_dir / "observability-export.json", dict(
        schema="isaforge-nanocobs-v2-agent-observability-export-v1",
        database_sha256=c.sha(agent_database), projection=observability_summary,
        authority="sealed JSON protocol, report, requests and ledger; SQLite is derived"))
    c.seal(agent_dir / "manifest.json", _inventory(agent_dir))
    print(json.dumps({"status": report["status"], "charged_attempts": report["charged_attempts"],
        "selected_id": report["selected_id"], "output": str(agent_dir)}, indent=2))
    return report


def collect_remaining():
    prereg, release_record, discovery = _verify_release()
    agent_report_path = STUDY / "agent/report.json"
    require(agent_report_path.is_file(), "Run and finalize the bounded LLM episode before oracle collection")
    agent_report = c.unseal(agent_report_path)
    require(agent_report.get("status") in ("finalized", "host_fallback"),
            "Agent episode must be closed before complete-pool measurement")
    evaluator = _evaluator()
    started = time.monotonic()
    try:
        report = evaluator.collect()
    finally:
        evaluator.runner.lock.close()
    audit = _audit_target(NATIVE)
    require(audit["attempt_collection_complete"] and audit["charged_candidate_attempts"] == len(_discover_target(NATIVE)["pool"]),
            "All actual pool one-attempt outcomes required to establish the reference pool")
    c.seal(STUDY / "native-audit.json", audit)
    c.seal(STUDY / "collection-report.json", report)
    c.seal(STUDY / "collection-operation.json", dict(
        schema="isaforge-nanocobs-v2-collection-operation-v1",
        elapsed_seconds=time.monotonic() - started,
        target_attempts=audit["charged_candidate_attempts"],
        target_native_command_count=audit["native_command_count"],
        target_native_command_seconds=audit["native_command_seconds"],
        collection_complete=audit["attempt_collection_complete"],
        note="This actual corpus-building run measures every pool candidate once; it is not a three-query search-cost result."))
    return audit


def _outcomes(audit):
    public = c.unseal(PREREG / "inputs/public.json")
    by_id = {row["candidate_id"]: row for row in public}
    mapping = {row["candidate_id"]: row["name"] for row in _discover_target(NATIVE)["pool"]}
    baseline = c.unseal(NATIVE / "measurements/baseline/measurement.json")
    outcomes = []
    outer_times = {}
    for candidate in public:
        identity = candidate["candidate_id"]
        name = mapping[identity]
        attempt = attempts.read_attempt(NATIVE, name)
        timer = c.unseal(STUDY / "outer-times" / (identity + ".json"))
        require(timer["candidate_id"] == identity and timer["status"] == attempt["status"] and
                timer["elapsed_seconds"] >= attempt["elapsed_seconds"] and
                timer["elapsed_seconds"] > 0,
                "Candidate wrapper timer does not enclose its charged measurement")
        outer_times[identity] = timer["elapsed_seconds"]
        if attempt["status"] == "success":
            record = c.unseal(NATIVE / "measurements" / name / "measurement.json")
            outcome = evidence._outcome(candidate, record, baseline)
            outcome["measurement_record_seconds"] = record["elapsed_seconds"]
            outcome["measurement_seconds"] = attempt["elapsed_seconds"]
            outcome["measurement_source"] = "synthesis_estimate"
        else:
            native_failure = next((row for row in audit["failed_or_interrupted"]
                                   if row["name"] == name), None)
            require(native_failure is not None and attempt["status"] == "failed",
                    "Unknown or interrupted measurement prevents complete-pool policy scoring")
            outcome = dict(candidate, status="failed", error=native_failure["error"],
                failure_class=native_failure["classification"],
                reference_censored=native_failure["reference_censored"],
                measurement_seconds=attempt["elapsed_seconds"])
        outcomes.append(outcome)
    require(len(outcomes) == len(by_id) and
            {row["candidate_id"] for row in outcomes} == set(by_id),
            "Complete unique target outcome roster required")
    return outcomes, outer_times


def _stable_policy_report(value):
    if isinstance(value, (list, tuple)):
        return [_stable_policy_report(item) for item in value]
    if isinstance(value, dict):
        return {key: _stable_policy_report(item) for key, item in value.items()
                if key not in ("inference_seconds", "replay_search_host_seconds")}
    return value


def _verified_reference(outcomes, cap):
    values = [row["speedup"] for row in outcomes
        if row.get("status", "success") == "success" and row["correctness_verified"]
        and row["device_fits"] and row["area_delta_lut4"] <= cap
        and row["routed_fmax_min_mhz"] >= CLOCK_MHZ and row["speedup"] > 1.0]
    return max([1.0, *values])


def _cycle_reduction(speedup):
    return 1.0 - 1.0 / speedup


def _annotate_cycle_reduction_metrics(report, outcomes):
    oracle_available = report.get("oracle_available", True)
    for run in report.get("runs", []):
        cap = run.get("area_delta_lut4_cap", run.get("cap"))
        if type(cap) is not int:
            continue
        verified_reference = _verified_reference(outcomes, cap)
        for point in run.get("curve", []):
            if "regret" in point:
                point["speedup_ratio_regret_to_oracle"] = point.pop("regret")
            if "regret_lower_bound_to_verified" in point:
                point["speedup_ratio_regret_lower_bound_to_verified"] = point.pop(
                    "regret_lower_bound_to_verified")
            if "gap_to_best_verified" in point:
                point["speedup_ratio_gap_to_best_verified"] = point.pop("gap_to_best_verified")
            best = point.get("best_speedup", 1.0)
            point["best_so_far_cycle_reduction"] = _cycle_reduction(best)
            if oracle_available:
                point["cycle_reduction_regret"] = max(
                    0.0, _cycle_reduction(verified_reference) - _cycle_reduction(best))
                point["cycle_reduction_regret_lower_bound_to_verified"] = None
            else:
                point["cycle_reduction_regret"] = None
                point["cycle_reduction_regret_lower_bound_to_verified"] = max(
                    0.0, _cycle_reduction(verified_reference) - _cycle_reduction(best))
    for row in report.get("summary", []):
        if "mean_regret" in row:
            row["mean_speedup_ratio_regret_to_oracle"] = row.pop("mean_regret")
        if "mean_regret_lower_bound_to_verified" in row:
            row["mean_speedup_ratio_regret_lower_bound_to_verified"] = row.pop(
                "mean_regret_lower_bound_to_verified")
        if "mean_gap_to_best_verified" in row:
            row["mean_speedup_ratio_gap_to_best_verified"] = row.pop(
                "mean_gap_to_best_verified")
        policy = row.get("policy")
        cap = row.get("area_delta_lut4_cap", row.get("cap"))
        budget = row.get("budget")
        points = [point for run in report.get("runs", [])
            if run.get("policy") == policy and
               run.get("area_delta_lut4_cap", run.get("cap")) == cap
            for point in run.get("curve", []) if point.get("budget") == budget]
        if oracle_available:
            values = [point["cycle_reduction_regret"] for point in points]
            row["mean_cycle_reduction_regret"] = statistics.mean(values) if values else None
            row["mean_cycle_reduction_regret_lower_bound_to_verified"] = None
        else:
            values = [point["cycle_reduction_regret_lower_bound_to_verified"] for point in points]
            row["mean_cycle_reduction_regret"] = None
            row["mean_cycle_reduction_regret_lower_bound_to_verified"] = (
                statistics.mean(values) if values else None)
    return report


def _sanitize_reference_report(report, outcomes, censored_ids):
    """Never expose oracle regret when an unknown outcome can beat the pool."""
    if not censored_ids:
        report["oracle_available"] = True
        report["oracle_status"] = "complete measured feasible pool"
        return report
    references = {cap: _verified_reference(outcomes, cap) for cap in (32, 64, 128)}
    report["oracle_available"] = False
    report["oracle_status"] = "censored by unresolved/infrastructure-unknown candidate outcomes"
    report["reference_censored_candidates"] = list(censored_ids)
    for oracle in report.get("oracles", []):
        cap = oracle.get("area_delta_lut4_cap")
        if cap in references and "speedup" in oracle:
            oracle["verified_best_speedup_lower_bound"] = references[cap]
            oracle["speedup"] = None
            oracle["reference_complete"] = False
    for run in report.get("runs", []):
        cap = run.get("area_delta_lut4_cap", run.get("cap"))
        if cap not in references:
            continue
        for point in run.get("curve", []):
            if "regret" in point:
                point["regret"] = None
            point["regret_lower_bound_to_verified"] = max(
                0.0, references[cap] - point.get("best_speedup", 1.0))
            point["reference_kind"] = "best verified lower bound; full pool censored"
    for row in report.get("summary", []):
        if "mean_regret" in row:
            row["mean_regret"] = None
        if "oracle_hits" in row:
            row["oracle_hits"] = None
        if "cap" in row and row["cap"] in references:
            row["mean_regret_lower_bound_to_verified"] = statistics.mean(
                point.get("regret_lower_bound_to_verified", 0.0)
                for run in report.get("runs", [])
                if run.get("area_delta_lut4_cap", run.get("cap")) == row["cap"]
                and run.get("policy") == row.get("policy")
                for point in run.get("curve", [])
                if point.get("budget") == row.get("budget"))
    return report


def _sanitize_scoring_reports(scoring_root, factorized_report, outcomes, audit):
    censored_ids = sorted(audit["reference_censored_candidates"])
    model_path = scoring_root / "controls11/model/report.json"
    control_path = scoring_root / "controls11/report.json"
    model_report = _sanitize_reference_report(c.unseal(model_path), outcomes, censored_ids)
    model_report = _annotate_cycle_reduction_metrics(model_report, outcomes)
    c.seal(model_path, model_report)
    control_report = _sanitize_reference_report(c.unseal(control_path), outcomes, censored_ids)
    control_report = _annotate_cycle_reduction_metrics(control_report, outcomes)
    control_report.pop("control_report_sha256", None)
    control_report["model_report_stable_sha256"] = c.digest(_stable_policy_report(model_report))
    c.seal(control_path, control_report)
    factorized_report = _sanitize_reference_report(factorized_report, outcomes, censored_ids)
    factorized_report = _annotate_cycle_reduction_metrics(factorized_report, outcomes)
    factorized_report.pop("control_report_sha256", None)
    factorized_report["control_report_stable_sha256"] = c.digest(
        _stable_policy_report(control_report))
    c.seal(scoring_root / "report.json", factorized_report)
    return factorized_report


def _agent_budget_endpoints(agent, budgets, *, oracle, verified_reference):
    curve = agent.get("budget_curve", [])
    result = []
    for limit in budgets:
        available = [point for point in curve if point.get("budget", 0) <= limit]
        point = max(available, key=lambda row: row.get("budget", 0)) if available else dict(
            budget=0, selected_id=None, best_speedup=1.0, attempted_ids=[])
        best_speedup = point.get("best_speedup", 1.0)
        result.append(dict(budget=limit, actual_attempts_used=point.get("budget", 0),
            selected_id=point.get("selected_id"), best_verified_feasible_speedup=point.get("best_speedup", 1.0),
            best_so_far_cycle_reduction=_cycle_reduction(best_speedup),
            cycle_reduction_regret=(max(0.0, _cycle_reduction(oracle)-_cycle_reduction(best_speedup))
                                     if oracle is not None else None),
            cycle_reduction_regret_lower_bound_to_verified=(
                max(0.0, _cycle_reduction(verified_reference)-_cycle_reduction(best_speedup))
                if oracle is None else None),
            attempted_candidate_ids=point.get("attempted_ids", [])))
    return result


def evaluate():
    prereg, release_record, _ = _verify_release()
    budgets = prereg["primary"]["budgets"]
    require(not RESULTS.exists(), "Preserve prior scored study outputs")
    audit = c.unseal(STUDY / "native-audit.json")
    collection = c.unseal(STUDY / "collection-report.json")
    require(collection.get("collection_complete") is True and
            audit.get("attempt_collection_complete") is True,
            "Complete source-bound target collection required")
    outcomes, outer_times = _outcomes(audit)
    scoring_root = STUDY / "scoring/selection"
    require(not scoring_root.exists(), "Preserve prior derived scoring package")
    scoring_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PREREG / "selection", scoring_root)
    factorized_report = factorized.evaluate(scoring_root, outcomes,
        native_audit=audit, outer_times=outer_times)
    factorized_report = _sanitize_scoring_reports(scoring_root, factorized_report, outcomes, audit)
    c.seal(STUDY / "outer-times.json", outer_times)
    c.seal(STUDY / "outcomes.json", outcomes)
    agent = c.unseal(STUDY / "agent/report.json")
    successes = [row for row in outcomes if row.get("status", "success") == "success"]
    feasible = [row for row in successes if row["correctness_verified"] and row["device_fits"]
                and row["area_delta_lut4"] <= AREA_CAP and row["routed_fmax_min_mhz"] >= CLOCK_MHZ]
    feasible_improving = [row for row in feasible if row["speedup"] > 1.0]
    censored_ids = sorted(audit["reference_censored_candidates"])
    complete = audit["attempt_collection_complete"] and not censored_ids
    oracle = max([1.0] + [row["speedup"] for row in feasible]) if complete else None
    verified_reference = max([1.0] + [row["speedup"] for row in feasible])
    selected = next((row for row in outcomes if row["candidate_id"] == agent.get("selected_id")), None)
    selected_speedup = selected["speedup"] if selected and selected.get("status", "success") == "success" else 1.0
    best_agent_speedup = max([1.0] + [row["speedup"] for row in agent["target_outcomes"].values()
        if row.get("status", "success") == "success" and row["correctness_verified"] and
        row["device_fits"] and row["area_delta_lut4"] <= AREA_CAP and
        row["routed_fmax_min_mhz"] >= CLOCK_MHZ and row["speedup"] > 1.0])
    reduction = lambda speedup: 1.0 - 1.0 / speedup
    agent_curve = _agent_budget_endpoints(agent, budgets, oracle=oracle,
                                          verified_reference=verified_reference)
    report = dict(schema="isaforge-nanocobs-v2-selection-study-report-v1",
        scope=prereg["scope"], prelabel_commit=release_record["prelabel_commit"],
        preregistration_manifest_sha256=release_record["preregistration_manifest_sha256"],
        target_workload=workload.GROUP, target_context_id=prereg["target_context_id"],
        historical_labels=122, historical_failures=4,
        family_filtered_training_rows=prereg["family_excluded_training_rows"],
        target_candidates=len(outcomes), target_attempts=audit["charged_candidate_attempts"],
        candidate_failures=len(audit["failed_or_interrupted"]),
        reference_censored_candidates=censored_ids,
        complete_measured_reference_pool=complete,
        observed_feasible_candidate_count=len(feasible),
        observed_feasible_improving_candidate_count=len(feasible_improving),
        oracle_feasible_candidate_count=len(feasible) if complete else None,
        oracle_feasible_improving_candidate_count=len(feasible_improving) if complete else None,
        oracle_speedup=oracle,
        agent=dict(provider=agent["provider"], status=agent["status"],
            charged_attempts=agent["charged_attempts"], attempted_ids=agent["attempted_candidate_ids"],
            selected_id=agent["selected_id"], selected_measured_speedup=selected_speedup,
            best_verified_feasible_speedup=best_agent_speedup,
            budget_endpoints=agent_curve,
            cycle_reduction_regret=(max(0.0, reduction(oracle)-reduction(best_agent_speedup))
                                    if oracle is not None else None),
            model_events=agent["model_events"], model_usage=agent["model_usage"],
            memory_traces=agent["memory_traces"],
            decision_rationale_sha256=c.digest(agent["decision_rationale"]),
            target_measurement_seconds=agent["actual_agent_measurement_seconds"],
            target_measurement_seconds_known=agent["known_agent_measurement_seconds"],
            target_measurement_time_complete=agent["agent_measurement_time_complete"],
            target_measurement_time_unknown_ids=agent["agent_measurement_time_unknown_ids"],
            target_outer_operation_seconds=agent["agent_outer_operation_seconds"],
            target_outer_operation_seconds_known=agent["known_agent_outer_operation_seconds"],
            target_outer_operation_time_complete=agent["agent_outer_operation_time_complete"],
            target_outer_operation_time_unknown_ids=agent["agent_outer_operation_time_unknown_ids"],
            target_attempt_costs=agent["agent_attempt_costs"],
            live_session_elapsed_seconds=agent["live_session_elapsed_seconds"],
            decision_elapsed_seconds=agent["decision_elapsed_seconds"],
            tool_calls=agent["tool_calls"], provider_calls=agent["provider_calls"],
            new_native_jobs=agent["new_native_jobs"]),
        factorized_policy_report_sha256=c.digest(factorized_report),
        matched_nonagent_summary=[row for row in factorized_report["summary"]
            if row["cap"] == AREA_CAP and row["budget"] in budgets],
        seed_zero_nonagent_trajectories=[run for run in factorized_report["runs"]
            if run.get("cap", run.get("area_delta_lut4_cap")) == AREA_CAP and run["seed"] == 0],
        nonagent_trajectories=factorized_report["trajectories"],
        nonagent_endpoints=factorized_report["endpoints"],
        actual_dataset_collection=dict(candidate_evaluations=audit["charged_candidate_attempts"],
            candidate_failures=len(audit["failed_or_interrupted"]),
            candidate_wall_seconds=audit["candidate_wall_seconds"],
            candidate_outer_operation_seconds=sum(outer_times.values()),
            native_command_seconds=audit["native_command_seconds"],
            scope="full-pool corpus/oracle collection; costs every actual pool member once, irrespective of replay budget"),
        policy_costs_note="Each non-agent policy is replayed with one-at-a-time outcome release and counts only its own B1/B2/B3 prefix. Those are offline counterfactual decision costs on already collected target labels; actual corpus construction measured the complete pool.",
        baseline=dict(c.unseal(PREREG / "inputs/cost-provenance.json")["target_baseline"]),
        source_family_audit=c.unseal(PREREG / "source-family-audit.json"),
        inference_training_cost=c.unseal(PREREG / "model-fit-costs.json"),
        hardware_training_cost=prereg["cost_provenance"]["historical"],
        limitations=prereg["limitations"] + [
            "One fixed nanocobs source and differential probe are not sufficient to establish broad workload generalization; exact operation-tree-family holdout is also a stricter, narrower transfer test.",
            "The LLM result is one current-chat relay episode without an available deployment ID, provider tokens or isolated API execution.",
            "Five ML seeds are dependent algorithm runs on one candidate pool, not independent workload replicates.",
            "An unresolved or infrastructure-censored outcome makes exhaustive-oracle speedup and regret unavailable; conclusively incorrect candidates are disqualified as infeasible.",
            "This study evaluates individual instructions; it does not test combined instruction sets or full processor implementation of selected combinations.",
        ],
        superiority_established=False,
        new_native_jobs=dict(agent=agent["new_native_jobs"],
            full_pool_collection=audit["charged_candidate_attempts"], scoring_replay=0))
    RESULTS.mkdir(parents=True)
    (RESULTS / "README.md").write_text(
        "# Nanocobs v2 selector transfer pilot\n\n"
        "This is one fixed nanocobs workload with source and exact operator-tree families excluded from model fitting. It does not establish broad workload generalization. "
        "The prelabel commit and complete measurement accounting are embedded in `study-report.json`.\n\n"
        "The LLM selector ran first as one live current-Codex chat-relay episode, with at most three real candidate measurements returned one at a time. "
        "Only after it finalized were the remaining candidates measured to form the complete pool. The frequency, merit, latency/cost, random, "
        "XGBoost, factorized feasibility, and active-learning policies are replayed under the same one-to-three query budgets. Their target observations "
        "are counterfactual callback releases from the fully collected dataset; the physical dataset build itself cost all candidate evaluations.\n\n"
        "The unit-level metrics are whole-program cycles, speedup, correctness, LUT4 increment, minimum routed Fmax, paid attempts, and actual evaluation time. "
        "See `factorized-policy-report.json`, `outcomes.json`, `native-audit.json`, the verified SQLite agent trace, and archived `native.tar.gz` for full evidence.\n\n"
        "The Codex relay is cooperative rather than sandboxed; exact model ID, token use and model-only latency are unavailable. One agent episode and one workload "
        "are not enough for an agent-quality or generalization claim. Individual-instruction measurements do not demonstrate combined-instruction performance.\n")
    c.seal(RESULTS / "study-report.json", report)
    c.seal(RESULTS / "factorized-policy-report.json", factorized_report)
    scoring_output = RESULTS / "scoring"
    scoring_output.mkdir()
    for source, destination in (
        (scoring_root / "report.json", scoring_output / "factorized-report.json"),
        (scoring_root / "controls11/report.json", scoring_output / "matched-controls-report.json"),
        (scoring_root / "controls11/model/report.json", scoring_output / "primary-model-report.json"),
    ):
        c.seal(destination, c.unseal(source))
    c.seal(RESULTS / "outcomes.json", outcomes)
    c.seal(RESULTS / "native-audit.json", audit)
    c.seal(RESULTS / "outer-times.json", outer_times)
    c.seal(RESULTS / "agent-report.json", agent)
    c.seal(RESULTS / "release.json", c.unseal(RELEASE))
    archive_record = pack_archive(NATIVE, RESULTS / "native.tar.gz")
    c.seal(RESULTS / "archive-manifest.json", archive_record)
    shutil.copytree(STUDY / "agent", RESULTS / "agent")
    c.seal(RESULTS / "manifest.json", _inventory(RESULTS))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("release", "agent", "collect", "evaluate", "verify"))
    args = parser.parse_args(argv)
    if args.command == "release":
        result = release()
    elif args.command == "agent":
        result = run_agent()
    elif args.command == "collect":
        result = collect_remaining()
    elif args.command == "evaluate":
        result = evaluate()
    else:
        result = c.unseal(RESULTS / "study-report.json")
        expected = c.unseal(RESULTS / "manifest.json")
        require(_inventory(RESULTS) == expected, "Scored study manifest differs")
        agent = c.unseal(RESULTS / "agent-report.json")
        ledger = c.unseal(RESULTS / "agent/ledger.json")
        require(agent["ledger_sha256"] == c.sha(RESULTS / "agent/ledger.json") and
                ledger.get("decision_rationale") == agent.get("decision_rationale") and
                ledger.get("status") == agent.get("status") and
                ledger.get("selected_id") == agent.get("selected_id"),
                "Agent report differs from the host-authoritative decision ledger")
        costs = ledger.get("native_attempt_cost_accounting")
        require(isinstance(costs, dict) and
                agent.get("agent_attempt_costs") == costs.get("attempts") and
                agent.get("actual_agent_measurement_seconds") == costs.get("measurement_seconds") and
                agent.get("known_agent_measurement_seconds") == costs.get("known_measurement_seconds") and
                agent.get("agent_measurement_time_complete") == costs.get("measurement_time_complete") and
                agent.get("agent_outer_operation_seconds") == costs.get("outer_operation_seconds") and
                agent.get("known_agent_outer_operation_seconds") == costs.get("known_outer_operation_seconds"),
                "Agent cost report differs from durable host-ledger accounting")
        archive_record = c.unseal(RESULTS / "archive-manifest.json")
        require(_inventory(RESULTS / "agent") ==
                c.unseal(RESULTS / "agent/manifest.json"),
                "Agent evidence package manifest differs")
        observability = c.unseal(RESULTS / "agent/observability-export.json")
        database = RESULTS / "agent/observability.sqlite"
        require(c.sha(database) == observability["database_sha256"],
                "SQLite observability projection checksum differs")
        with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True) as db:
            require(db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                    "SQLite observability projection fails integrity check")
            counts = dict(release_id=observability["projection"]["release_id"],
                episodes=db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
                decisions=db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
                model_calls=db.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0],
                retrievals=db.execute("SELECT COUNT(*) FROM retrievals").fetchone()[0],
                context_windows=db.execute("SELECT COUNT(*) FROM context_windows").fetchone()[0],
                decision_rationales=db.execute("SELECT COUNT(*) FROM decision_rationales").fetchone()[0],
                rationale_measurements=db.execute("SELECT COUNT(*) FROM rationale_measurements").fetchone()[0],
                rationale_selection_decisions=db.execute(
                    "SELECT COUNT(*) FROM rationale_selection_decisions").fetchone()[0],
                host_events=db.execute("SELECT COUNT(*) FROM host_events").fetchone()[0],
                missing_token_rows=db.execute(
                    "SELECT COUNT(*) FROM model_calls WHERE total_tokens IS NULL").fetchone()[0])
            expected_counts = dict(observability["projection"], missing_token_rows=counts["missing_token_rows"])
            require(counts == expected_counts,
                    "SQLite observability row counts differ from the sealed export receipt")
            require(counts["missing_token_rows"] == counts["model_calls"],
                    "Current Codex relay token limitation must remain explicit")
        with tempfile.TemporaryDirectory(prefix="isaforge-nanocobs-v2-verify-") as temp:
            restored = Path(temp) / "native"
            restore_archive(RESULTS, archive_record, restored)
            require(_archive_inventory(restored) == {row["path"]: row["sha256"]
                    for row in archive_record["files"]},
                    "Archived raw native evidence differs from its manifest")
            prereg, release_record, _ = _verify_release(dispatch=False,
                native_root=restored, receipt_path=RESULTS / "release.json")
            require(result["prelabel_commit"] == release_record["prelabel_commit"] and
                    result["target_context_id"] == prereg["target_context_id"],
                    "Scored result and frozen target disagree")
            archived_audit = c.unseal(RESULTS / "native-audit.json")
            require(_audit_target(restored) == archived_audit,
                    "Regenerated native audit differs from the preserved audit")
            outcomes = c.unseal(RESULTS / "outcomes.json")
            outer_times = c.unseal(RESULTS / "outer-times.json")
            require(archived_audit["outcomes"] == outcomes,
                    "Scored outcomes differ from the restored raw-evidence audit")
            scoring_temp = Path(temp) / "scoring"
            scoring_temp.mkdir()
            scoring_root = scoring_temp / "selection"
            shutil.copytree(PREREG / "selection", scoring_root)
            replay = factorized.evaluate(scoring_root, outcomes,
                native_audit=archived_audit, outer_times=outer_times)
            replay = _sanitize_scoring_reports(scoring_root, replay, outcomes, archived_audit)
            scored_replay = c.unseal(RESULTS / "factorized-policy-report.json")
            require(_stable_policy_report(replay) == _stable_policy_report(scored_replay),
                    "Prespecified policy trajectories do not reproduce deterministically")
            for generated, saved in (
                (scoring_root / "report.json", RESULTS / "scoring/factorized-report.json"),
                (scoring_root / "controls11/report.json", RESULTS / "scoring/matched-controls-report.json"),
                (scoring_root / "controls11/model/report.json", RESULTS / "scoring/primary-model-report.json"),
            ):
                require(_stable_policy_report(c.unseal(generated)) ==
                        _stable_policy_report(c.unseal(saved)),
                        "Derived policy scorer report differs: " + saved.name)
        print("Verified archived evidence and deterministic policy replay; no new native jobs or target labels acquired. The paid-update GP refits during replay are recorded separately.")
        return 0
    if args.command == "release":
        print({"prelabel_commit": result["prelabel_commit"], "remote": result["pushed_remote_head"],
               "candidate_attempts": result["candidate_attempts"]})
    elif args.command == "agent":
        # The provider may block for a JSON action; emit only progress state.
        pass
    elif args.command == "collect":
        print({"charged_attempts": result["charged_candidate_attempts"],
               "collection_complete": result["attempt_collection_complete"],
               "failures": len(result["failed_or_interrupted"])})
    elif args.command == "evaluate":
        print({"target_attempts": result["target_attempts"],
               "agent_selected_id": result["agent"]["selected_id"],
               "oracle_speedup": result["oracle_speedup"],
               "oracle_regret": result["agent"]["cycle_reduction_regret"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
