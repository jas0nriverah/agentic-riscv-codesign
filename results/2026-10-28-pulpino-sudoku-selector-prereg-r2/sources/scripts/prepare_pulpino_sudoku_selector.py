#!/usr/bin/env python3
"""Freeze Sudoku workload ML/agent comparisons before candidate labels exist."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import campaign_evidence as evidence
from isaforge import codesign as c
from isaforge import current_grouped_predictions as grouped
from isaforge import factorized_selection_experiment as factorized
from isaforge import pulpino_sudoku_workload as workload
from isaforge.speedup_corpus import family
from scripts.reproduce_codesign import restore_archive

SOURCE = 'scripts/prepare_pulpino_sudoku_selector.py'
QUALIFICATION = ROOT / 'results/2026-10-28-pulpino-sudoku-qualification-r1'
BASELINE_ROOT = ROOT / 'generated/pulpino-sudoku-selection-baseline-r1'
HISTORY = ROOT / workload.HISTORY
OUTPUT = ROOT / 'results/2026-10-28-pulpino-sudoku-selector-prereg-r2'
SEEDS = (0, 1, 2, 3, 4)
BUDGETS = (1, 2, 3)
AREA_CAPS = (32, 64, 128)
CLOCK_MHZ = 12.0
PRIMARY_AREA_CAP = 64
PRIMARY_BUDGET = 3

SOURCES = tuple(dict.fromkeys((
    SOURCE,
    'scripts/execute_pulpino_sudoku_selector.py',
    'scripts/qualify_pulpino_sudoku.py',
    'scripts/build_pulpino_sudoku_adapter.py',
    'scripts/export_agent_observability.py',
    'tests/test_pulpino_sudoku_selector.py',
    workload.SOURCE, workload.QUALIFIER, workload.TEST, workload.CONTRACT,
    workload.PIN, workload.ADAPTER, workload.ADAPTER_BUILDER,
    workload.UPSTREAM_C, workload.UPSTREAM_H, workload.LICENSE,
    'isaforge/guarded_workload.py', 'isaforge/guarded_attempts.py',
    'isaforge/guarded_evidence.py', 'isaforge/qualified_workload.py',
    'isaforge/bounded_workload.py', 'isaforge/partitioned_workload.py',
    'isaforge/workload_experiment.py', 'isaforge/assembly_lowering.py',
    'isaforge/relocation_guard.py', 'isaforge/campaign_evidence.py',
    'isaforge/prospective_inputs.py', 'isaforge/budgeted_selection.py',
    'isaforge/feasible_benefit_experiment.py', 'isaforge/feasible_benefit.py',
    'isaforge/factorized_selection_experiment.py',
    'isaforge/feasibility_selection.py', 'isaforge/current_grouped_predictions.py',
    'isaforge/bounded_selector.py', 'isaforge/selector_decision_support.py',
    'isaforge/selection_provider.py', 'isaforge/codex_chat_selector.py',
    'isaforge/agent_memory.py', 'isaforge/routed_selection.py',
    'isaforge/model.py', 'isaforge/ranking.py', 'isaforge/features.py',
    'isaforge/prospective_selection.py', 'isaforge/speedup_corpus.py',
    'isaforge/codesign.py', 'docs/pulpino-sudoku-adapter-contract-2026-10-28.md',
    'docs/pulpino-sudoku-selection-study-contract-2026-10-28.md',
    'docs/agent-evals.md', 'docs/agent-memory-operations.md',
    'docs/ml-agent-integration-2026-10-28.md',
    'hardware/embench_firmware.c', 'hardware/embench_memory.c',
    'hardware/checked_sim.cpp', 'hardware/stack_monitor.hpp',
    'scripts/reproduce_codesign.py', 'scripts/qualify_opportunity_sources.py',
)))
QUALIFICATION_INPUTS = (
    'results/2026-10-28-pulpino-sudoku-qualification-r1/qualification.json',
    'results/2026-10-28-pulpino-sudoku-qualification-r1/protocol.json',
    'results/2026-10-28-pulpino-sudoku-qualification-r1/manifest.json',
    'results/2026-10-28-pulpino-sudoku-qualification-r1/archive-manifest.json',
    'results/2026-10-28-pulpino-sudoku-qualification-r1/raw.tar.gz',
)


def require(condition, message):
    c.require(bool(condition), message)


def _manifest(root):
    manifest = c.unseal(root / 'manifest.json')
    require(isinstance(manifest, dict) and manifest, 'Authenticated nonempty qualification manifest required')
    for relative, digest in manifest.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file() and c.sha(path) == digest,
                'Qualification manifest entry differs: ' + relative)
    return manifest


def _baseline():
    _manifest(QUALIFICATION)
    qualification = c.unseal(QUALIFICATION / 'qualification.json')
    protocol = c.unseal(QUALIFICATION / 'protocol.json')
    require(qualification.get('status') == 'accepted' and
            qualification.get('target_candidate_attempts') == 0 and
            qualification.get('accepted') == {workload.WORKLOAD:
                'generated/pulpino-sudoku-qualification-2026-10-28-r1'},
            'Accepted zero-candidate Sudoku qualification required')
    require(protocol.get('candidate_dispatch_enabled') is False and
            protocol.get('target_candidate_attempts') == 0,
            'Baseline qualification must remain candidate-label-free')
    if not BASELINE_ROOT.exists():
        archive = c.unseal(QUALIFICATION / 'archive-manifest.json')
        restore_archive(QUALIFICATION, archive, BASELINE_ROOT)
    workload.validate_inputs(BASELINE_ROOT)
    workload.require_zero_candidates(BASELINE_ROOT)
    public, context, before = workload.baseline_public(BASELINE_ROOT)
    require(len(public) == workload.POOL_SIZE == 12 and
            len({row['candidate_id'] for row in public}) == 12,
            'Complete unique twelve-candidate public pool required')
    require(context['workload_group'] == workload.GROUP and
            public[0]['benchmark'].split(':', 1)[0] == workload.GROUP,
            'Target workload identity differs')
    require(not list((BASELINE_ROOT / 'attempt-ledger').glob('candidate_*.json')),
            'Candidate attempt ledger must be empty before fit')
    return public, context, before, qualification, protocol


def _history():
    manifest = c.unseal(HISTORY.parent / 'manifest.json')
    require(manifest.get('corpus.json') == c.sha(HISTORY),
            'Historical corpus manifest binding differs')
    corpus = c.unseal(HISTORY)
    rows, failures = corpus.get('rows', []), corpus.get('failed_attempts', [])
    require(corpus.get('successful_labels') == len(rows) == 122 and
            len(failures) == 4 and corpus.get('total_candidate_attempts') == 126 and
            len(corpus.get('independent_workload_groups', [])) == 14,
            'Expected authenticated historical 122-label / 126-attempt corpus')
    require(all(campaign_row['candidate_id'] for campaign_row in rows + failures),
            'Historical attempt identities required')
    return corpus


def freeze(output=OUTPUT):
    started = time.monotonic()
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT) and not output.exists(),
            'Use a fresh in-repository preregistration directory')
    public, context, before, qualification, qualification_protocol = _baseline()
    corpus = _history()
    target_families = sorted({family(row['formula']) for row in public})
    historical_families = {family(row['formula']) for row in corpus['rows']}
    overlapping = sorted(set(target_families) & historical_families)
    training = [row for row in corpus['rows'] if family(row['formula']) not in set(target_families)]
    excluded = [row for row in corpus['rows'] if family(row['formula']) in set(target_families)]
    require(len(target_families) == 9 and len(overlapping) == 3 and
            len(training) == 106 and len(excluded) == 16 and
            len({row['workload_group'] for row in training}) == 14,
            'Expected family-disjoint 106-row / 14-workload fitting cohort')
    require(all(row['workload_group'] != workload.GROUP and
                family(row['formula']) not in set(target_families) for row in training),
            'Target workload or operation family leaked into fitting rows')

    contexts = dict(corpus['contexts'])
    contexts[public[0]['benchmark']] = context
    calibration = evidence._calibration(BASELINE_ROOT)
    baseline = c.unseal(BASELINE_ROOT / 'measurements/baseline/measurement.json')
    cost_provenance = dict(
        historical=dict(successful_labels=122, failures=4, charged_attempts=126,
            candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
            corpus_sha256=c.sha(HISTORY)),
        target_qualification=dict(status=qualification['status'], candidate_attempts=0,
            protocol_sha256=c.sha(QUALIFICATION / 'protocol.json'),
            result_sha256=c.sha(QUALIFICATION / 'qualification.json'),
            archive_sha256=c.sha(QUALIFICATION / 'raw.tar.gz')),
        target_baseline=dict(context_id=context['context_id'],
            measurement_sha256=c.sha(BASELINE_ROOT / 'measurements/baseline/measurement.json'),
            performance=baseline['performance'], resources=baseline['resources'],
            minimum_routed_fmax_mhz=min(r['limiting_internal_fmax_mhz'] for r in baseline['routes']),
            memory_check=c.unseal(BASELINE_ROOT / 'discovery/discovery.json')['memory_check']),
        calibration=dict(native_commands=calibration['native_commands'],
            native_command_seconds=calibration['native_command_seconds'],
            labels_collected=calibration['application_labels_collected']),
        note='Historical, target qualification, baseline, calibration, model-fit, agent and candidate-evaluation timers are separately reported; overlapping native and wrapper scopes are not summed.')
    inputs = {name: c.sha(ROOT / name) for name in SOURCES if name != SOURCE}
    inputs.update({name: c.sha(ROOT / name) for name in QUALIFICATION_INPUTS})
    inputs.update({
        'results/2026-10-26-lift-selection-corpus/corpus.json': c.sha(HISTORY),
        'results/2026-10-26-lift-selection-corpus/manifest.json': c.sha(HISTORY.parent / 'manifest.json'),
    })

    output.mkdir(parents=True)
    for relative, value in (
        ('inputs/public.json', public), ('inputs/context.json', context),
        ('inputs/before.json', before), ('inputs/history-all.json', corpus['rows']),
        ('inputs/historical-failures.json', corpus['failed_attempts']),
        ('inputs/contexts.json', contexts), ('inputs/family-exclusions.json', excluded),
        ('inputs/cost-provenance.json', cost_provenance),
    ):
        c.seal(output / relative, value)
    selection = output / 'selection'
    fit_started = time.monotonic()
    selection_protocol = factorized.freeze(corpus['rows'], public, contexts, selection,
        target_workload=workload.GROUP, target_labels_observed=0,
        calibration_cost_seconds=calibration['native_command_seconds'],
        cost_provenance=cost_provenance, input_bindings=inputs,
        scope='prospective source holdout')
    freeze_seconds = time.monotonic() - fit_started
    filtered_history = c.unseal(selection / 'controls11/model/history.json')
    agent_rows, agent_metadata = [], []
    for seed in SEEDS:
        bundle, metadata = grouped.fit_current_grouped_predictions(
            filtered_history, public, target_workload_group=workload.GROUP,
            target_formula_families=target_families, seed=seed,
            area_cap_lut4=PRIMARY_AREA_CAP)
        agent_rows.append(bundle)
        agent_metadata.append(metadata)
    c.seal(output / 'agent-predictions.json', agent_rows)
    c.seal(output / 'agent-model-metadata.json', agent_metadata)
    model_costs = c.unseal(selection / 'controls11/model/predictions.json')
    utility_costs = c.unseal(selection / 'controls11/utility-inference-costs.json')
    feasibility_costs = c.unseal(selection / 'feasibility-costs.json')

    agent_protocol = dict(
        schema='isaforge-pulpino-sudoku-bounded-agent-prereg-v1',
        scope='one prospective live Codex chat-relay episode with host-measured target observations',
        provider='codex-chat-bridge', model_label='current Codex chat model; exact deployment ID unavailable',
        model_id_available=False, api_key_available=bool(os.environ.get('OPENAI_API_KEY')),
        tools=['list_candidates', 'predict', 'measure', 'finalize'],
        structured_action='one strict JSON object per response through the local bridge; host enforces identities, correctness, area, timing, and budget',
        model_bundle='Seed-zero XGBRanker rank:pairwise trained on historical whole-program measured speedup orderings plus a 20-member XGBoost hardware-feasibility ensemble multiplied by public analytic cycle savings; all target workload labels and target operation families excluded.',
        ml_training=dict(rows=106, workload_groups=14,
            labels='historical measured whole-program speedup orderings and verified area/timing feasibility',
            ranker=dict(objective='rank:pairwise', n_estimators=80, max_depth=2, learning_rate=0.05),
            feasibility=dict(members=20, objective='binary:logistic', calibrated=False)),
        llm_training='No LLM fine-tuning. Prompt-based current Codex model receives structured candidate state, frozen ML predictions, public heuristics, hybrid retrieved approved historical examples, and only its own paid measurements.',
        memory=dict(mode='hybrid', top_k=3, max_memory_bytes=40000,
            store='local TF-IDF / truncated-SVD historical memory; one measured record per chunk',
            retrieval='lexical plus latent-semantic cosine fused by reciprocal-rank fusion',
            knowledge_graph='typed graph support is available but is not queried in the frozen hybrid episode',
            corpus='same family-excluded 106-row historical training set',
            target_outcomes='never indexed or retrieved; only the agent own paid observations are returned'),
        human_in_loop='Human relay passes structured request/action between the active chat model and host. The host performs schema/candidate/budget checks and rejects unsafe measurements; no separate approval click is claimed.',
        model_routing='This episode uses the current Codex chat relay. The Responses API provider supports bounded escalation when configured, but no cross-provider routing is used or evaluated here.',
        attempts=PRIMARY_BUDGET, area_cap_lut4=PRIMARY_AREA_CAP,
        minimum_routed_fmax_mhz=CLOCK_MHZ, model_calls=12, tool_calls=20,
        stop_rule='Stop within three charged measurements; host finalizes the best paid verified feasible candidate or baseline.',
        agent_trials=[0], agent_trial_count=1,
        observability=['provider, decision, tool, and hardware-attempt counts',
            'hashes of public requests and pre-measure contexts', 'retrieved record IDs/source hashes',
            'host-measured outcomes, attempt charges, final choice, and regret',
            'verified SQLite projection; sealed JSON remains authoritative'],
        limitations=['One agent episode is exploratory and has no model-family or agent-superiority power.',
            'Current Codex model ID, provider tokens, and isolated inference latency are unavailable.',
            'The current relay is cooperative, not an isolated tool sandbox.',
            'One fixed Sudoku puzzle; no arbitrary-puzzle generalization.',
            'Single-instruction pool; no combined instruction labels.'])
    c.seal(output / 'agent-protocol.json', agent_protocol)

    source_bindings = {name: c.sha(ROOT / name) for name in SOURCES}
    evidence_bindings = {relative: c.sha(ROOT / relative) for relative in QUALIFICATION_INPUTS}
    evidence_bindings.update({
        'history/corpus.json': c.sha(HISTORY),
        'history/manifest.json': c.sha(HISTORY.parent / 'manifest.json'),
    })
    roster = dict(schema='isaforge-pulpino-sudoku-source-family-audit-v1',
        target_families=target_families, overlapping_families=overlapping,
        novel_target_families=sorted(set(target_families) - historical_families),
        target_candidate_count=len(public),
        overlap_candidate_ids=sorted(row['candidate_id'] for row in public
                                     if family(row['formula']) in set(overlapping)),
        excluded_historical_success_ids=[row['candidate_id'] for row in excluded],
        training_rows=len(filtered_history),
        training_workload_groups=sorted({row['workload_group'] for row in filtered_history}),
        family_definition='Canonical operator-tree shape that ignores constants and input identities and sorts children for commutative add/and/or/xor/mul nodes.',
        interpretation='Target source and every canonical operator-tree family in the target pool are excluded from training. This is one held-out workload and remains too small for a broad generalization claim.')
    c.seal(output / 'source-family-audit.json', roster)
    c.seal(output / 'model-fit-costs.json', dict(
        primary_model_fit_and_prediction_seconds=[dict(seed=row['seed'], **row['inference_seconds'])
            for row in model_costs], utility_model_fit_and_prediction_seconds=utility_costs,
        factorized_feasibility_fit_and_prediction_seconds=feasibility_costs,
        grouped_model_fit_and_prediction_seconds=[m['model_fit_and_prediction_seconds'] for m in agent_metadata],
        factorized_package_freeze_operation_seconds=freeze_seconds,
        total_zero_label_package_build_operation_seconds=time.monotonic() - started,
        packages={name: importlib.metadata.version(name) for name in ('numpy','scipy','xgboost','scikit-learn')},
        target_labels_read=0, target_labels_observed=0, candidate_attempts=0))

    prereg = dict(schema='isaforge-pulpino-sudoku-selector-prereg-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        scope='prospective held-out workload and canonical operation-family transfer pilot',
        target_workload=workload.GROUP, target_context_id=context['context_id'],
        target_labels_read=0, target_labels_observed=0, candidate_attempts_before_fit=0,
        target_public_pool_size=len(public), target_candidate_ids=[row['candidate_id'] for row in public],
        target_families=target_families, target_family_overlap_count=len(overlapping),
        historical_rows=122, historical_failed_attempts=4, historical_attempts=126,
        family_excluded_training_rows=len(filtered_history),
        family_excluded_training_groups=sorted({row['workload_group'] for row in filtered_history}),
        excluded_successes=len(excluded), excluded_ids_sha256=c.digest(sorted(row['candidate_id'] for row in excluded)),
        selection_protocol_sha256=c.sha(selection / 'protocol.json'),
        selection_manifest={path.relative_to(selection).as_posix(): c.sha(path)
                            for path in sorted(selection.rglob('*')) if path.is_file()},
        agent_protocol_sha256=c.sha(output / 'agent-protocol.json'),
        agent_predictions_sha256=c.sha(output / 'agent-predictions.json'),
        agent_model_metadata_sha256=c.sha(output / 'agent-model-metadata.json'),
        source_family_audit_sha256=c.sha(output / 'source-family-audit.json'),
        primary=dict(area_cap_lut4=PRIMARY_AREA_CAP, minimum_routed_fmax_mhz=CLOCK_MHZ,
            budgets=list(BUDGETS), endpoint='best verified feasible whole-program speedup by measurement budget; cycle-reduction regret to complete measured pool'),
        policies=selection_protocol['policies'], seeds=list(SEEDS), agent_seeds=[0],
        area_caps=list(AREA_CAPS), clock_mhz=CLOCK_MHZ,
        target_baseline=dict(cycles=baseline['performance']['cycles'],
            instructions=baseline['performance']['instructions'], lut4=baseline['resources']['lut4_count'],
            minimum_routed_fmax_mhz=min(r['limiting_internal_fmax_mhz'] for r in baseline['routes']),
            correctness_verified=True,
            stack_max_bytes=cost_provenance['target_baseline']['memory_check']['max_stack_bytes'],
            stack_headroom_bytes=cost_provenance['target_baseline']['memory_check']['stack_headroom_bytes']),
        measurement_plan='Run the live agent first with a maximum of three sequential real candidate measurements. After it finalizes, measure every remaining candidate once to establish the 12-candidate oracle. Replay all prespecified non-agent policies using each policy’s own one-at-a-time observation prefix at budgets 1, 2, and 3. The physical dataset collection costs up to twelve candidate evaluations; replay prefixes do not erase that cost.',
        source_bindings=source_bindings, input_bindings=inputs,
        evidence_bindings=evidence_bindings,
        model_packages={name: importlib.metadata.version(name) for name in ('numpy','scipy','xgboost','scikit-learn')},
        model_protocol=dict(existing_pairwise_ranker='XGBRanker rank:pairwise, fixed 80 trees/depth 2/learning rate .05; historical labels only',
            factorized_model='existing 20-member feasibility XGBoost ensemble × public analytic cycle savings; seeds 0-4; not a speedup-magnitude model',
            active_learning='existing frozen Gaussian-process acquisition and paid-update controls; no tuning',
            heuristic_controls='frequency, merit, calibrated latency, random and the existing non-agent policies',
            uncertainty='all ensemble spreads/classifier scores remain uncalibrated; extrapolation support is diagnostic only'),
        agent_protocol=agent_protocol, cost_provenance=cost_provenance,
        factorized_fit_operation_seconds=freeze_seconds,
        created_operation_seconds=time.monotonic() - started,
        status='zero-label preregistration frozen; commit and push before candidate dispatch',
        limitations=agent_protocol['limitations'] + [
            'One held-out workload does not establish broad generalization.',
            'Pool is the top-12 executable shortlist from the existing merit-oriented extractor, not all legal instructions.',
            'Historical model-selection decisions are development evidence; this run tests zero-shot transfer on a held-out workload.',
            'The measured oracle is complete only if all twelve attempts produce classifiable outcomes.',
            'FPGA synthesis/routing and RTL simulation are not silicon measurements.',
            'Single-instruction measurements do not establish combined-instruction performance.'])
    c.seal(output / 'preregistration.json', prereg)
    for name in SOURCES:
        destination = output / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (output / 'README.md').write_text(
        '# PULPino Sudoku prospective selection preregistration\n\n'
        'This zero-label package freezes the second selector preregistration after code review of the preserved r1 snapshot. The r1 directory remains unchanged but must not be released: its guard did not recheck candidate-ledger emptiness at agent startup, cost reporting could omit a charged job after result-projection failure, and family wording overstated the canonicalization. This r2 package contains no Sudoku candidate measurements.\n\n'
        '## Frozen cohort and models\n\n'
        '- Target: one pinned 9×9 Sudoku puzzle run twice; 12 legal, executable single-instruction candidates with calibrated public cycle-opportunity features.\n'
        '- Historical data: 122 successful measured labels and 4 failed attempts across 14 workload groups. Exclude the target workload and all target canonical operation-tree families before fitting: 106 rows / 14 groups remain; 16 historical successes are excluded.\n'
        '- Models: existing pairwise XGBoost speedup ranker, factorized feasibility XGBoost plus public analytic cycle savings, existing regression/ranking/active-learning controls. No new model family or hyperparameter sweep.\n'
        '- Agent: one current Codex chat relay with frozen seed-zero ML outputs, public frequency/merit/timing signals, hybrid historical retrieval, and four structured tools. No LLM fine-tuning or cross-provider routing claim.\n\n'
        '## Budget and evidence\n\n'
        'Primary evaluation: 64 added LUT4, at least 12 MHz across all three routes, and a maximum of three charged measurements. The LLM agent runs first and sees only public information and its own paid outcomes. The remaining candidates are measured only after finalization to establish the complete measured oracle; non-agent policy replays release each policy only its own paid prefix. Physical corpus construction can cost twelve candidate evaluations.\n\n'
        'The endpoint is best verified feasible whole-program speedup by budget and cycle-reduction regret versus the measured pool oracle. Correctness, timing, area, evaluation count and measured evaluation time are reported separately. No superiority claim is preregistered.\n\n'
        'The qualification found baseline **1,024,889 cycles / 198,711 instructions**, a **2,288-byte image**, **3,968-byte observed stack** with **1,792-byte headroom**, no stack/guard violations, **1,653 LUT4**, 295 carry cells, 655 flip-flops, 20 BRAMs, and routed timing above 12 MHz on all three seeds. These are baseline measurements, not candidate speedups.\n\n'
        '## Release rule\n\n'
        'Candidate dispatch is blocked until the preregistration, source, and evidence hashes are committed and pushed to `ai-guided-ml`. The executor verifies the exact local and remote commit and rechecks zero candidate attempts immediately before agent startup. See `preregistration.json`, `agent-protocol.json`, `source-family-audit.json`, `model-fit-costs.json`, and `manifest.json`.\n')
    entries = {path.relative_to(output).as_posix(): c.sha(path)
               for path in sorted(output.rglob('*')) if path.is_file() and
               path.name not in ('manifest.json', 'manifest.json.sha256')}
    c.seal(output / 'manifest.json', entries)
    return prereg


def authenticate(output=OUTPUT, *, verify_live_sources=True):
    output = Path(output).resolve()
    prereg = c.unseal(output / 'preregistration.json')
    require(prereg.get('schema') == 'isaforge-pulpino-sudoku-selector-prereg-v1' and
            prereg.get('target_labels_read') == prereg.get('target_labels_observed') == 0 and
            prereg.get('candidate_attempts_before_fit') == 0,
            'Expected zero-label PULPino Sudoku preregistration')
    manifest = c.unseal(output / 'manifest.json')
    for relative, digest in manifest.items():
        require(c.sha(output / relative) == digest, 'Prerelease artifact changed: ' + relative)
    for name, digest in prereg['source_bindings'].items():
        require(c.sha(output / 'sources' / name) == digest,
                'Frozen source copy differs: ' + name)
        if verify_live_sources:
            require(c.sha(ROOT / name) == digest, 'Frozen source changed: ' + name)
    for name, digest in prereg['input_bindings'].items():
        if verify_live_sources:
            require(c.sha(ROOT / name) == digest, 'Frozen model input changed: ' + name)
    for name, digest in prereg['evidence_bindings'].items():
        if name.startswith('results/') and verify_live_sources:
            require(c.sha(ROOT / name) == digest, 'Frozen qualification/history evidence changed: ' + name)
    for name, version in prereg['model_packages'].items():
        require(importlib.metadata.version(name) == version, 'Frozen dependency differs: ' + name)
    case = factorized.authenticate(output / 'selection')
    require(c.sha(output / 'selection/protocol.json') == prereg['selection_protocol_sha256'],
            'Frozen selection protocol changed')
    require(case['protocol']['target_labels_read'] == case['protocol']['target_labels_observed'] == 0 and
            case['protocol']['target_workload'] == workload.GROUP and
            case['protocol']['policies'] == prereg['policies'],
            'Frozen selection model/policy contract differs')
    return prereg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'verify'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = freeze(args.output) if args.command == 'freeze' else authenticate(args.output)
    print(dict(status='verified', target_labels_read=result.get('target_labels_read'),
        target_labels_observed=result.get('target_labels_observed'),
        candidate_attempts_before_fit=result.get('candidate_attempts_before_fit'),
        training_rows=result.get('family_excluded_training_rows'),
        policy_count=len(result.get('policies', [])), output=str(args.output)))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
