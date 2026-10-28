"""Fit the current grouped-screen models for one leak-safe agent replay.

This is an inference adapter, not a new model version. It uses the existing
pairwise ranker and factorized feasibility model with the screen's fixed
workload/family holdout, then exports only predictions and provenance.
"""
from __future__ import annotations

import math
import time
from typing import Any

from . import budgeted_selection as b, codesign as c
from .bounded_selector import GROUPED_PREDICTION_FIELDS, GROUPED_PREDICTION_SCHEMA
from .factorized_selection_experiment import FeasibilitySelectionPredictor
from .model import validate_training_rows
from .ranking import SpeedupRanker
from .speedup_corpus import family

AREA_CAP_LUT4 = 64
CLOCK_MHZ = 12.0
SOURCES = (
    'isaforge/current_grouped_predictions.py',
    'isaforge/bounded_selector.py',
    'isaforge/budgeted_selection.py',
    'isaforge/factorized_selection_experiment.py',
    'isaforge/feasibility_selection.py',
    'isaforge/model.py',
    'isaforge/ranking.py',
    'isaforge/features.py',
    'isaforge/speedup_corpus.py',
    'isaforge/prospective_selection.py',
    'isaforge/codesign.py',
)


def fit_current_grouped_predictions(training: list[dict[str, Any]],
                                    public: list[dict[str, Any]], *,
                                    target_workload_group: str,
                                    target_formula_families: list[str] | tuple[str, ...],
                                    seed: int = 0,
                                    area_cap_lut4: int = AREA_CAP_LUT4) -> tuple[dict, dict]:
    """Return an outcome-free current-model bundle plus its public provenance.

    The target workload and every family in the full target workload roster
    must already be excluded from ``training``. Incomplete target outcomes are
    not accepted by this function or represented in its result.
    """
    c.require(type(seed) is int and seed >= 0, 'Invalid grouped model seed')
    c.require(area_cap_lut4 == AREA_CAP_LUT4,
              'This replay is frozen to the current screen primary +64 LUT4 cap')
    c.require(isinstance(target_workload_group, str) and target_workload_group,
              'Target workload group is required')
    public = b.public_rows(public)
    validate_training_rows(training)
    c.require(training and len({row['workload_group'] for row in training}) >= 2,
              'At least two historical workload groups are required')
    target_families = set(target_formula_families)
    c.require(target_families and all(isinstance(value, str) and value
                                      for value in target_families),
              'Full target formula-family roster is required')
    c.require(all(row['workload_group'] != target_workload_group and
                  family(row['formula']) not in target_families for row in training),
              'Training rows include the target workload or related family')
    c.require(all(row['benchmark'].split(':', 1)[0] == target_workload_group
                  for row in public), 'Target public rows disagree with the held-out group')

    started = time.monotonic()
    ranker = SpeedupRanker(seed=seed).fit(training)
    ranker_fit_seconds = time.monotonic() - started
    started = time.monotonic()
    rank_predictions = ranker.predict(public)
    ranker_prediction_seconds = time.monotonic() - started
    rank_by_id = {row['candidate_id']: float(row['rank_score']) for row in rank_predictions}
    c.require(set(rank_by_id) == {row['candidate_id'] for row in public} and
              all(math.isfinite(value) for value in rank_by_id.values()),
              'Ranker did not score the full public pool')
    rank_order = sorted(rank_by_id,
                        key=lambda identity: (-rank_by_id[identity], identity))
    rank_position = {identity: position for position, identity in enumerate(rank_order, 1)}

    started = time.monotonic()
    feasibility = FeasibilitySelectionPredictor(seed=seed).fit(training)
    feasibility_fit_seconds = time.monotonic() - started
    started = time.monotonic()
    feasibility_predictions = feasibility.predict(public, area_cap=area_cap_lut4)
    feasibility_prediction_seconds = time.monotonic() - started
    feasibility_by_id = {row['candidate_id']: row for row in feasibility_predictions}
    c.require(set(feasibility_by_id) == {row['candidate_id'] for row in public},
              'Feasibility model did not score the full public pool')

    rows = []
    for candidate in public:
        identity = candidate['candidate_id']
        estimate = feasibility_by_id[identity]
        rows.append(dict(candidate_id=identity,
            pairwise_rank_score=rank_by_id[identity],
            pairwise_rank_position=rank_position[identity],
            factorized_feasibility_probability=estimate['feasibility_score_mean'],
            factorized_feasibility_disagreement=estimate['feasibility_score_std'],
            factorized_decision_score=estimate['decision_score']))
    c.require(all(math.isfinite(value) for row in rows
                  for key, value in row.items() if key != 'candidate_id'),
              'A current grouped model returned a nonfinite score')
    c.require(all(set(row) == {'candidate_id', *GROUPED_PREDICTION_FIELDS}
                  for row in rows), 'Unexpected current prediction field')

    model_bundle = dict(schema=GROUPED_PREDICTION_SCHEMA, seed=seed, rows=rows)
    metadata = dict(schema=GROUPED_PREDICTION_SCHEMA,
        scope='consumed-data whole-workload holdout; all target-workload formula families excluded',
        prediction_policy='zero-shot scores frozen before target measurements',
        target_workload_group=target_workload_group,
        target_formula_families=sorted(target_families),
        area_cap_lut4=area_cap_lut4, minimum_routed_fmax_mhz=CLOCK_MHZ,
        pairwise_ranker=dict(name='XGBRanker', objective='rank:pairwise', seed=seed,
            score_semantics='relative ordering score; not speedup or probability'),
        factorized_feasibility=dict(name='FeasibilitySelectionPredictor', seed=seed,
            score_semantics='uncalibrated probability-like ranking score; not guaranteed probability',
            disagreement_semantics='ensemble disagreement only; not a calibrated interval',
            decision_score_semantics='feasibility_score_mean times nonnegative analytic cycle reduction'),
        training_rows=len(training),
        training_workload_groups=sorted({row['workload_group'] for row in training}),
        training_ids_sha256=c.digest(sorted(row['candidate_id'] for row in training)),
        target_public_ids_sha256=c.digest(sorted(row['candidate_id'] for row in public)),
        model_source_fingerprint=c.digest({name: c.sha(c.ROOT/name) for name in SOURCES}),
        model_fit_and_prediction_seconds=dict(
            ranker_fit=ranker_fit_seconds,
            ranker_prediction=ranker_prediction_seconds,
            feasibility_fit=feasibility_fit_seconds,
            feasibility_prediction=feasibility_prediction_seconds),
        uncertainty_calibrated=False)
    c.require(not ({'label', 'speedup', 'candidate_cycles', 'area_delta_lut4',
                    'routed_fmax_min_mhz', 'correctness_verified'} & set(metadata)),
              'Target labels are not permitted in model provenance')
    return model_bundle, metadata
