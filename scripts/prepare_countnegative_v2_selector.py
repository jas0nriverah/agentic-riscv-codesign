"""Freeze the countnegative-v2 transfer-selection study before candidate labels.

This reuses the current model/control recipes. It never opens candidate
outcomes, launches candidate hardware jobs, or changes the baseline archive.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import budgeted_selection as b
from isaforge import campaign_evidence as evidence
from isaforge import codesign as c
from isaforge import current_grouped_predictions as grouped
from isaforge import factorized_selection_experiment as factorized
from isaforge import countnegative_v2_workload as workload
from isaforge.speedup_corpus import family
from scripts.reproduce_codesign import restore_archive
from scripts import export_expanded_selection_corpus as expanded_corpus


SOURCE = "scripts/prepare_countnegative_v2_selector.py"
QUALIFICATION = ROOT / "results/2026-10-28-countnegative-v2-qualification-r1"
BASELINE_ROOT = ROOT / "generated/countnegative-v2-selection-baseline-r1"
HISTORY = ROOT / "results/2026-10-28-expanded-selection-corpus-r2/corpus.json"
OUTPUT = ROOT / "results/2026-10-28-countnegative-v2-selector-prereg-r2"
SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
AREA_CAPS = (32, 64, 128)
CLOCK_MHZ = 12.0
PRIMARY_AREA_CAP = 64
PRIMARY_BUDGET = 3

SOURCES = tuple(dict.fromkeys((
    SOURCE, 'scripts/execute_countnegative_v2_selector.py', 'scripts/export_expanded_selection_corpus.py',
    'tests/test_countnegative_v2_selector.py',
    'docs/countnegative-selection-study-contract-2026-10-28.md',
    *workload.GATE_SOURCES,
    'scripts/export_agent_observability.py',
    'isaforge/guarded_attempts.py', 'isaforge/guarded_evidence.py',
    'isaforge/qualified_workload.py', 'isaforge/bounded_workload.py',
    'isaforge/partitioned_workload.py', 'isaforge/workload_experiment.py',
    'isaforge/assembly_lowering.py', 'isaforge/relocation_guard.py', 'isaforge/latency_features.py',
    'isaforge/campaign_evidence.py', 'isaforge/prospective_inputs.py',
    'isaforge/budgeted_selection.py', 'isaforge/feasible_benefit_experiment.py',
    'isaforge/feasible_benefit.py', 'isaforge/factorized_selection_experiment.py',
    'isaforge/feasibility_selection.py', 'isaforge/current_grouped_predictions.py',
    'isaforge/bounded_selector.py', 'isaforge/selector_decision_support.py',
    'isaforge/selection_provider.py', 'isaforge/codex_chat_selector.py',
    'isaforge/agent_memory.py', 'isaforge/routed_selection.py',
    'isaforge/model.py', 'isaforge/ranking.py', 'isaforge/features.py',
    'isaforge/prospective_selection.py', 'isaforge/speedup_corpus.py', 'isaforge/codesign.py',
)))


def require(condition, message):
    c.require(bool(condition), message)


def _manifest(root: Path):
    manifest = c.unseal(root / "manifest.json")
    require(isinstance(manifest, dict) and manifest, "Authenticated nonempty manifest required")
    for relative, digest in manifest.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file() and c.sha(path) == digest,
                "Manifest entry differs: " + relative)
    return manifest


def _baseline():
    _manifest(QUALIFICATION)
    qualification = c.unseal(QUALIFICATION / "qualification.json")
    protocol = c.unseal(QUALIFICATION / "protocol.json")
    require(qualification.get("status") == "accepted" and
            qualification.get("target_candidate_attempts") == 0 and
            qualification.get("accepted") == {workload.WORKLOAD: "generated/countnegative-v2-qualification-2026-10-28-r1"},
            "Accepted zero-candidate countnegative-v2 qualification required")
    require(protocol.get("candidate_dispatch_enabled") is False and
            protocol.get("target_candidate_attempts") == 0,
            "The accepted qualification must remain candidate-label-free")
    if not BASELINE_ROOT.exists():
        archive_record = c.unseal(QUALIFICATION / "archive-manifest.json")
        restore_archive(QUALIFICATION, archive_record, BASELINE_ROOT)
    workload.validate_inputs(BASELINE_ROOT)
    workload.require_zero_candidates(BASELINE_ROOT)
    public, context, before = workload.baseline_public(BASELINE_ROOT)
    require(1 <= len(public) <= workload.POOL_SIZE and
            len({row["candidate_id"] for row in public}) == len(public),
            "Complete unique actual public pool required")
    require(context["workload_group"] == workload.GROUP and
            public[0]["benchmark"].split(":", 1)[0] == workload.GROUP,
            "Target workload identity differs")
    require(not list((BASELINE_ROOT / "attempt-ledger").glob("candidate_*.json")),
            "Candidate attempt ledger must be empty before fit")
    return public, context, before, qualification, protocol


def _history():
    manifest = c.unseal(HISTORY.parent / "manifest.json")
    require(manifest.get("corpus.json") == c.sha(HISTORY),
            "Historical corpus manifest binding differs")
    corpus, authenticated_manifest = expanded_corpus.authenticate(HISTORY.parent)
    require(authenticated_manifest == manifest, "Expanded corpus manifest changed during authentication")
    rows, failures = corpus.get("rows", []), corpus.get("failed_attempts", [])
    require(corpus.get("successful_labels") == len(rows) == 156 and
            len(failures) == 4 and corpus.get("total_candidate_attempts") == 160 and
            len(corpus.get("independent_workload_groups", [])) == 17,
            "Expected authenticated historical 156-label / 160-attempt corpus")
    require(len({row["candidate_id"] for row in rows + failures}) == 160,
            "Historical attempt identities must be unique")
    require(all(b.validate_outcome(row) for row in rows),
            "Only verified historical successful labels may be fitted")
    return corpus


RECENT_PUBLIC_ROSTERS = (
    'results/2026-10-28-tiny-regex-c-selector-prereg-r5/inputs/public.json',
    'results/2026-10-28-pulpino-sudoku-selector-prereg-r4/inputs/public.json',
    'results/2026-10-27-ascon-selector-prereg-v3/inputs/public.json',
    'results/2026-10-28-nanocobs-v2-selector-prereg-r1/inputs/public.json',
)


def recent_public_overlap(public):
    """Read public rosters descriptively; no public-only record is injected into fitting."""
    target = {family(row['formula']) for row in public}
    return [dict(path=name, sha256=c.sha(ROOT / name),
        candidate_count=len(rows), families=sorted({family(r['formula']) for r in rows}),
        overlapping_families=sorted(target & {family(r['formula']) for r in rows}),
        target_overlap_candidate_ids=sorted(row['candidate_id'] for row in public
            if family(row['formula']) in {family(r['formula']) for r in rows}))
        for name in RECENT_PUBLIC_ROSTERS for rows in [c.unseal(ROOT / name)]]


def history_contexts(corpus):
    """Merge actual source-prereg contexts authenticated by sealed study releases."""
    contexts, bindings = dict(corpus['contexts']), {}
    for source in corpus['new_source_contexts']:
        study_root = (ROOT / source['study_root']).resolve()
        require(study_root.is_relative_to(ROOT), 'Historical study root escapes repository')
        study_manifest_path = study_root / 'manifest.json'
        study_manifest = c.unseal(study_manifest_path)
        release_path = study_root / 'release.json'
        require(study_manifest.get('release.json') == c.sha(release_path),
                'Historical release is not bound to study manifest')
        release = c.unseal(release_path)
        prereg_root = (ROOT / release['preregistration']).resolve()
        require(prereg_root.is_relative_to(ROOT), 'Historical preregistration escapes repository')
        manifest_path = prereg_root / 'manifest.json'
        require(release['preregistration_manifest_sha256'] == c.sha(manifest_path),
                'Historical preregistration manifest differs from released binding')
        manifest = c.unseal(manifest_path)
        context_path = prereg_root / 'inputs/context.json'
        require(manifest.get('inputs/context.json') == c.sha(context_path),
                'Historical context differs from preregistration manifest')
        context = c.unseal(context_path)
        require(context['context_id'] == source['context_id'] == release['target_context_id'] and
                context['workload_group'] + ':' + context['context_id'] == source['source_id'],
                'Historical source-context identity differs')
        key = source['source_id']
        require(key not in contexts or contexts[key] == context, 'Conflicting historical provenance context')
        contexts[key] = context
        for path in (study_manifest_path, release_path, manifest_path, context_path):
            for bound in (path, Path(str(path) + '.sha256')):
                bindings[bound.relative_to(ROOT).as_posix()] = c.sha(bound)
    require({row['benchmark'] for row in corpus['rows']} <= set(contexts),
            'Authenticated contexts must cover every historical benchmark')
    return contexts, bindings


CORRECTNESS_LIMITATION = (
    'One original deterministic 20x20 matrix and aggregate checksum0x1778de; '
    'not arbitrary-matrix verification, and aggregate checksums can have collisions.')


def split_training(history, public):
    families = {family(row['formula']) for row in public}
    training = [row for row in history if row['workload_group'] != workload.GROUP and
                family(row['formula']) not in families]
    included = {row['candidate_id'] for row in training}
    return training, [row for row in history if row['candidate_id'] not in included]


def freeze(output=OUTPUT):
    started = time.monotonic()
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and not output.exists(),
            "Use a fresh in-repository preregistration directory")
    public, context, before, qualification, qualification_protocol = _baseline()
    corpus = _history()
    target_families = sorted({family(row["formula"]) for row in public})
    historical_families = {family(row["formula"]) for row in corpus["rows"]}
    overlapping = sorted(set(target_families) & historical_families)
    training, excluded = split_training(corpus['rows'], public)
    require(training and len(training) + len(excluded) == len(corpus['rows']),
            'Nonempty family-disjoint fitting cohort required')
    require(all(row["workload_group"] != workload.GROUP and
                family(row["formula"]) not in set(target_families) for row in training),
            "Target workload or operation family leaked into fitting rows")

    contexts, context_bindings = history_contexts(corpus)
    contexts[public[0]["benchmark"]] = context
    calibration = evidence._calibration(BASELINE_ROOT)
    baseline_record = c.unseal(BASELINE_ROOT / "measurements/baseline/measurement.json")
    cost_provenance = dict(
        historical=dict(successful_labels=156, failures=4, charged_attempts=160,
            candidate_wall_seconds=corpus["total_candidate_attempt_wall_seconds"],
            corpus_sha256=c.sha(HISTORY)),
        target_qualification=dict(status=qualification["status"], candidate_attempts=0,
            protocol_sha256=c.sha(QUALIFICATION / "protocol.json"),
            result_sha256=c.sha(QUALIFICATION / "qualification.json"),
            archive_sha256=c.sha(QUALIFICATION / "raw.tar.gz")),
        target_baseline=dict(context_id=context["context_id"],
            measurement_sha256=c.sha(BASELINE_ROOT / "measurements/baseline/measurement.json"),
            performance=baseline_record["performance"], resources=baseline_record["resources"],
            minimum_routed_fmax_mhz=min(r["limiting_internal_fmax_mhz"] for r in baseline_record["routes"])),
        calibration=dict(native_commands=calibration["native_commands"],
            native_command_seconds=calibration["native_command_seconds"],
            labels_collected=calibration["application_labels_collected"]),
        note="Historical, qualification, baseline, calibration, model-fit, agent, and candidate-evaluation timers are separately reported; overlapping native and wrapper scopes are not summed.")
    inputs = {name: c.sha(ROOT / name) for name in SOURCES if name != SOURCE}
    inputs.update(context_bindings)
    for name in RECENT_PUBLIC_ROSTERS:
        inputs[name] = c.sha(ROOT / name)
        inputs[name + '.sha256'] = c.sha(ROOT / (name + '.sha256'))
    for name in ('provenance.json', 'provenance.json.sha256', 'corpus.json.sha256'):
        path = HISTORY.parent / name
        inputs[path.relative_to(ROOT).as_posix()] = c.sha(path)
    inputs.update({
        "results/2026-10-28-countnegative-v2-qualification-r1/manifest.json": c.sha(QUALIFICATION / "manifest.json"),
        "results/2026-10-28-countnegative-v2-qualification-r1/archive-manifest.json": c.sha(QUALIFICATION / "archive-manifest.json"),
        "results/2026-10-28-countnegative-v2-qualification-r1/raw.tar.gz": c.sha(QUALIFICATION / "raw.tar.gz"),
        "results/2026-10-28-expanded-selection-corpus-r2/corpus.json": c.sha(HISTORY),
        "results/2026-10-28-expanded-selection-corpus-r2/manifest.json": c.sha(HISTORY.parent / "manifest.json"),
    })

    output.mkdir(parents=True)
    for relative, value in (
        ("inputs/public.json", public), ("inputs/context.json", context),
        ("inputs/before.json", before), ("inputs/history-all.json", corpus["rows"]),
        ("inputs/historical-failures.json", corpus["failed_attempts"]),
        ("inputs/contexts.json", contexts), ("inputs/family-exclusions.json", excluded),
        ("inputs/cost-provenance.json", cost_provenance),
    ):
        c.seal(output / relative, value)
    selection = output / "selection"
    model_started = time.monotonic()
    selection_protocol = factorized.freeze(training, public, contexts, selection,
        target_workload=workload.GROUP, target_labels_observed=0,
        calibration_cost_seconds=calibration["native_command_seconds"],
        cost_provenance=cost_provenance, input_bindings=inputs,
        scope="prospective source holdout")
    fit_seconds = time.monotonic() - model_started
    filtered_history = c.unseal(selection / "controls11/model/history.json")
    require(sorted(row['candidate_id'] for row in filtered_history) ==
            sorted(row['candidate_id'] for row in training),
            'Every model and agent memory must use exactly the family-excluded fitting roster')
    agent_rows, agent_metadata = [], []
    for seed in SEEDS:
        bundle, metadata = grouped.fit_current_grouped_predictions(
            filtered_history, public, target_workload_group=workload.GROUP,
            target_formula_families=target_families, seed=seed,
            area_cap_lut4=PRIMARY_AREA_CAP)
        agent_rows.append(bundle)
        agent_metadata.append(metadata)
    c.seal(output / "agent-predictions.json", agent_rows)
    c.seal(output / "agent-model-metadata.json", agent_metadata)
    primary_fit_costs = c.unseal(selection / "controls11/model/predictions.json")
    utility_fit_costs = c.unseal(selection / "controls11/utility-inference-costs.json")
    factorized_fit_costs = c.unseal(selection / "feasibility-costs.json")

    agent_protocol = dict(
        schema="isaforge-countnegative-v2-bounded-agent-prereg-v1",
        scope="one prospective live current-Codex chat-relay episode with host-measured target observations",
        provider="codex-chat-bridge",
        model_label="current Codex chat model; exact deployment ID unavailable",
        model_id_available=False, api_key_available=bool(__import__("os").environ.get("OPENAI_API_KEY")),
        tools=["list_candidates", "predict", "measure", "finalize"],
        structured_action="one strict JSON object per response through the local bridge; no Responses API call is claimed",
        model_bundle="seed-0 XGBRanker objective=rank:pairwise trained on historical measured whole-program speedup orderings, plus a 20-member XGBClassifier hardware-feasibility ensemble multiplied by public analytic cycle savings; target workload/families excluded",
        ml_training=dict(rows=len(filtered_history), workload_groups=len({r["workload_group"] for r in filtered_history}), labels="historical whole-program measured speedup; measured area/timing feasibility", xgb_ranker=dict(objective="rank:pairwise", n_estimators=80, max_depth=2, learning_rate=0.05), feasibility=dict(members=20, objective="binary:logistic", calibrated=False)),
        llm_training="No LLM fine-tuning. Prompt-based current Codex model receives structured state, predictions and bounded retrieved historical examples through a tool loop.",
        memory=dict(mode="hybrid", top_k=3, max_memory_bytes=40_000,
            store="local TF-IDF / truncated-SVD historical memory; one measured record per chunk",
            retrieval="lexical plus latent-semantic cosine with reciprocal-rank fusion",
            knowledge_graph="available in the memory subsystem and logged in provenance; not queried in hybrid mode",
            corpus="same dynamically sized family-excluded historical fitting set",
            target_outcomes="never indexed or retrieved; only the agent's own paid observations are returned in the active request"),
        human_in_loop="Codex orchestration relays model JSON; the human sets objective and budgets and may intervene, with no human review of each action. The host validates action schema, identity and budget before dispatch.",
        attempts=PRIMARY_BUDGET, area_cap_lut4=PRIMARY_AREA_CAP,
        minimum_routed_fmax_mhz=CLOCK_MHZ, model_calls=12, tool_calls=20,
        complete_public_roster_required_before_decision_board=True,
        stop_rule="Host finalizes the best paid verified feasible improvement, otherwise the baseline.",
        agent_trials=[0], agent_trial_count=1,
        observability=["provider/decision/tool/measurement counts", "public request hashes",
            "pre-measure decision context hashes", "retrieved record IDs and source hashes",
            "host-measured outcome and charge", "final selection and regret",
            "verified SQLite projection of decisions, model calls, retrievals, contexts and tools"],
        limitations=[
            "The Codex bridge uses the active chat model with broader workspace tools available; it is a cooperative relay, not a security sandbox.",
            "Exact model ID, token usage and model-only latency are unavailable for the chat bridge.",
            "Only one LLM episode is planned; it is exploratory, not a multi-seed agent-quality estimate.",
            "The workload is fixed-matrix aggregate-count transfer, not independent-family confirmation.",
            "The current dataset contains no combined-instruction outcomes; selections are single instructions.",
            CORRECTNESS_LIMITATION,
            "The timed benchmark includes the original kernel and checksum return; initialization uses the unchanged harness convention.",
        ])
    c.seal(output / "agent-protocol.json", agent_protocol)

    source_bindings = {name: c.sha(ROOT / name) for name in SOURCES}
    manifests = {path.relative_to(ROOT).as_posix(): c.sha(path) for path in (
        QUALIFICATION / 'manifest.json', QUALIFICATION / 'protocol.json',
        QUALIFICATION / 'qualification.json', QUALIFICATION / 'archive-manifest.json',
        QUALIFICATION / 'raw.tar.gz', HISTORY, HISTORY.parent / 'manifest.json')}
    roster = dict(schema="isaforge-countnegative-v2-source-family-audit-v1",
        target_families=target_families, overlapping_families=overlapping,
        novel_target_families=sorted(set(target_families) - historical_families),
        target_candidate_count=len(public),
        overlap_candidate_ids=sorted(row["candidate_id"] for row in public
                                     if family(row["formula"]) in set(overlapping)),
        excluded_historical_success_ids=[row["candidate_id"] for row in excluded],
        training_rows=len(filtered_history), training_workload_groups=sorted(
            {row["workload_group"] for row in filtered_history}),
        interpretation="Exact operation-tree families are excluded from training. A deterministic integer matrix benchmark and exact-family holdout are descriptive; recent public overlap is recorded below and does not establish domain independence.")
    roster['recent_public_rosters_descriptive_only'] = recent_public_overlap(public)
    roster['descriptive_public_rows_added_to_training'] = 0
    roster['expanded_corpus_note'] = 'Prior measured target labels may enter training from the authenticated expanded corpus only after current target workload/family exclusion; descriptive roster objects are never fitting inputs.'
    c.seal(output / "source-family-audit.json", roster)
    c.seal(output / "model-fit-costs.json", dict(
        primary_predictor_fit_and_prediction_seconds=[dict(seed=row["seed"], **row["inference_seconds"])
            for row in primary_fit_costs],
        utility_model_fit_and_prediction_seconds=utility_fit_costs,
        factorized_feasibility_fit_and_prediction_seconds=factorized_fit_costs,
        grouped_model_fit_and_prediction_seconds=[m["model_fit_and_prediction_seconds"] for m in agent_metadata],
        factorized_package_freeze_operation_seconds=fit_seconds,
        total_zero_label_package_build_operation_seconds=time.monotonic() - started,
        packages={name: importlib.metadata.version(name) for name in
                  ("numpy", "scipy", "xgboost", "scikit-learn")},
        target_labels_read=0, target_labels_observed=0, candidate_attempts=0))

    prereg = dict(schema="isaforge-countnegative-v2-selector-prereg-v1",
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        scope="related-domain transfer pilot; not independent workload-family confirmation",
        target_workload=workload.GROUP, target_context_id=context["context_id"],
        target_labels_read=0, target_labels_observed=0, candidate_attempts_before_fit=0,
        target_public_pool_size=len(public), target_candidate_ids=[row["candidate_id"] for row in public],
        target_families=target_families, target_family_overlap_count=len(overlapping),
        historical_rows=156, historical_failed_attempts=4, historical_attempts=160,
        family_excluded_training_rows=len(filtered_history),
        family_excluded_training_groups=sorted({row["workload_group"] for row in filtered_history}),
        excluded_successes=len(excluded), excluded_ids_sha256=c.digest(sorted(row["candidate_id"] for row in excluded)),
        model_schema=selection_protocol["schema"],
        selection_protocol_sha256=c.sha(selection / "protocol.json"),
        selection_manifest={path.relative_to(selection).as_posix(): c.sha(path)
                            for path in sorted(selection.rglob("*")) if path.is_file()},
        agent_protocol_sha256=c.sha(output / "agent-protocol.json"),
        agent_predictions_sha256=c.sha(output / "agent-predictions.json"),
        agent_model_metadata_sha256=c.sha(output / "agent-model-metadata.json"),
        source_family_audit_sha256=c.sha(output / "source-family-audit.json"),
        primary=dict(area_cap_lut4=PRIMARY_AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
                     budgets=list(BUDGETS), endpoint="best verified feasible whole-program speedup by budget; cycle-reduction regret to complete measured pool"),
        policies=[*selection_protocol["policies"], "codex_chat_agent_hybrid_memory"],
        seeds=list(SEEDS), agent_seeds=[0], area_caps=list(AREA_CAPS), clock_mhz=CLOCK_MHZ,
        target_baseline=dict(cycles=baseline_record["performance"]["cycles"],
            instructions=baseline_record["performance"]["instructions"],
            lut4=baseline_record["resources"]["lut4_count"],
            minimum_routed_fmax_mhz=min(r["limiting_internal_fmax_mhz"] for r in baseline_record["routes"]),
            correctness_verified=True),
        measurement_plan="Run one prospective live agent episode first, allowing only one-at-a-time host measurement feedback and at most three paid attempts. Only after the episode closes, serially measure all remaining pool members (one attempt each) to establish the complete reference pool. Then run the prespecified non-agent policy replay from hidden per-policy callbacks at budgets one, two and three. The physical dataset collection costs one attempt per actual pool member; replay trajectories do not erase that cost.",
        source_bindings=source_bindings, input_bindings=inputs,
        evidence_bindings=manifests,
        model_packages={name: importlib.metadata.version(name) for name in
                        ("numpy", "scipy", "xgboost", "scikit-learn")},
        model_protocol=dict(existing_pairwise_ranker="XGBRanker rank:pairwise, 80 trees, depth 2, learning rate .05, fixed seed; no target labels",
            existing_factorized_model="existing feasibility/analytic-benefit XGBoost recipe, seeds 0-4, fixed current settings",
            active_learning="existing hybrid Gaussian-process acquisition and paid-update implementation; no retuning",
            confidence="all uncertainty/disagreement outputs remain uncalibrated"),
        agent_protocol=agent_protocol, cost_provenance=cost_provenance,
        factorized_fit_operation_seconds=fit_seconds,
        created_operation_seconds=time.monotonic() - started,
        status="zero-label package frozen; requires commit and push before any candidate dispatch",
        limitations=agent_protocol["limitations"] + [
            "One previously screened fixed-matrix source and one Codex-agent episode are included.",
            "Candidate measurements will be collected to build an oracle; only charged per-policy prefixes count toward selector budgets.",
            "Hardware timing is FPGA synthesis/routing on the established toolchain, not silicon measurement.",
            "Individual-instruction results do not establish multi-instruction composition.",
        ])
    prereg['effective_budgets'] = {str(b): workload.variable.effective_policy_budget(b, len(public)) for b in BUDGETS}
    prereg['agent_protocol']['attempts'] = workload.variable.effective_policy_budget(PRIMARY_BUDGET, len(public))
    c.seal(output / "agent-protocol.json", prereg['agent_protocol'])
    prereg['agent_protocol_sha256'] = c.sha(output / "agent-protocol.json")
    c.seal(output / "preregistration.json", prereg)
    for name in SOURCES:
        destination = output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (output / 'README.md').write_text(
        '# Countnegative v2 prospective selector preregistration\n\n'
        'Zero target labels. Existing model families and settings; source and target exact operation families excluded from every fit and agent memory. '
        'Matched budgets 1, 2 and 3, effective min(B,N), and area caps 32, 64 and 128 LUT4. '
        'One live relay episode precedes complete-pool one-attempt oracle collection and posthoc matched-budget policy controls. '
        'Commit and push all bindings before dispatch. See preregistration.json for exact cardinality, training exclusions, predictions, model costs and limitations.\n')
    entries = {path.relative_to(output).as_posix(): c.sha(path)
               for path in sorted(output.rglob("*")) if path.is_file() and
               path.name not in ("manifest.json", "manifest.json.sha256")}
    c.seal(output / "manifest.json", entries)
    return prereg


def authenticate(output=OUTPUT, *, verify_live_sources=True):
    output = Path(output).resolve()
    prereg = c.unseal(output / "preregistration.json")
    require(prereg.get("schema") == "isaforge-countnegative-v2-selector-prereg-v1" and
            prereg.get("target_labels_read") == prereg.get("target_labels_observed") == 0 and
            prereg.get("candidate_attempts_before_fit") == 0,
            "Expected zero-label countnegative-v2 selection preregistration")
    for relative, digest in _manifest(output).items():
        require(c.sha(output / relative) == digest, "Prerelease artifact changed: " + relative)
    for name, digest in prereg["source_bindings"].items():
        require(c.sha(output / "sources" / name) == digest,
                "Frozen source copy differs: " + name)
        if verify_live_sources:
            require(c.sha(ROOT / name) == digest, "Frozen source changed: " + name)
    for name, digest in prereg["input_bindings"].items():
        if verify_live_sources:
            require(c.sha(ROOT / name) == digest, "Frozen model input changed: " + name)
    for name, version in prereg["model_packages"].items():
        require(importlib.metadata.version(name) == version,
                "Frozen model package version differs: " + name)
    protocol = c.unseal(output / "selection/protocol.json")
    require(protocol.get("target_labels_read") == protocol.get("target_labels_observed") == 0 and
            protocol.get("target_workload") == workload.GROUP and
            protocol.get("policies") == prereg["policies"][:-1],
            "Frozen selector policy/model contract differs")
    c.require(c.sha(output / "selection/protocol.json") == prereg["selection_protocol_sha256"],
              "Selector protocol changed")
    return prereg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "verify"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = freeze(args.output) if args.command == "freeze" else authenticate(args.output)
    print({"status": "verified", "target_labels_read": result.get("target_labels_read"),
           "target_labels_observed": result.get("target_labels_observed"),
           "candidate_attempts_before_fit": result.get("candidate_attempts_before_fit"),
           "training_rows": result.get("family_excluded_training_rows"),
           "policies": len(result.get("policies", [])), "output": str(args.output)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
