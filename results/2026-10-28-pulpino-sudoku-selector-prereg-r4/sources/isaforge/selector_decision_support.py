"""Leak-safe decision support for the grouped XGBoost selection agent.

The board only rearranges public candidate features, frozen model predictions,
and outcomes already disclosed by a paid measurement. It is advisory: it does
not filter candidates, update a model, or predict an unmeasured hardware label.
"""
from __future__ import annotations

import copy

from . import budgeted_selection as b, codesign as c
from .model import _number

SCHEMA = 'isaforge-grouped-decision-board-v1'
PREDICTION_FIELDS = {
    'pairwise_rank_score', 'pairwise_rank_position',
    'factorized_feasibility_probability',
    'factorized_feasibility_disagreement', 'factorized_decision_score',
}


def _paid_status(row: dict, *, area_cap: float, clock_mhz: float) -> dict:
    """Summarize one already disclosed outcome without inventing a label."""
    status = row.get('status', 'success')
    result = dict(status='failed_no_performance_or_hardware_label')
    if status == 'failed':
        result['measurement_seconds'] = _number(row['measurement_seconds'], 'measurement seconds')
        return result

    correctness = row['correctness_verified'] is True
    device_fits = row['device_fits'] is True
    area = _number(row['area_delta_lut4'], 'measured area delta')
    fmax = _number(row['routed_fmax_min_mhz'], 'measured routed Fmax')
    area_fits = area <= area_cap
    timing_fits = fmax >= clock_mhz
    feasible = correctness and device_fits and area_fits and timing_fits
    if not correctness:
        label = 'incorrect'
    elif not device_fits:
        label = 'device_infeasible'
    elif not area_fits:
        label = 'area_infeasible'
    elif not timing_fits:
        label = 'timing_infeasible'
    else:
        label = ('verified_feasible_improvement' if row['speedup'] > 1
                 else 'verified_feasible_no_speedup')
    result.update(status=label, correctness_verified=correctness,
        device_fits=device_fits, area_delta_lut4=area, area_fits=area_fits,
        routed_fmax_min_mhz=fmax, timing_fits=timing_fits,
        verified_feasible=feasible, speedup=_number(row['speedup'], 'measured speedup'))
    return result


def build_grouped_decision_board(candidates: list[dict], predictions: dict[str, dict],
                                 attempted_candidate_ids: list[str],
                                 paid_observations: list[dict], *, area_cap: float,
                                 clock_mhz: float) -> dict:
    """Build a readable, outcome-blind ranking board from host-approved inputs.

    ``predictions`` must be the frozen grouped-model bundle. ``paid_observations``
    may include only results already returned by the measurement tool.
    """
    public = b.public_rows(candidates)
    identities = {row['candidate_id'] for row in public}
    c.require(set(predictions) == identities, 'Decision board needs a complete prediction pool')
    c.require(type(attempted_candidate_ids) is list and
              len(set(attempted_candidate_ids)) == len(attempted_candidate_ids) and
              set(attempted_candidate_ids) <= identities,
              'Decision board has invalid attempted candidate IDs')
    area_cap = _number(area_cap, 'area cap')
    clock_mhz = _number(clock_mhz, 'clock MHz', positive=True)
    attempted = set(attempted_candidate_ids)
    paid_by_id = {}
    for row in paid_observations:
        identity = row.get('candidate_id')
        c.require(identity in attempted and identity not in paid_by_id,
                  'Paid observations must be unique and previously attempted')
        if row.get('status', 'success') == 'failed':
            c.require('speedup' not in row and 'area_delta_lut4' not in row and
                      'routed_fmax_min_mhz' not in row,
                      'Failed attempts cannot expose fabricated outcome labels')
        else:
            b.validate_outcome(row, next(r for r in public if r['candidate_id'] == identity))
        paid_by_id[identity] = row

    rows = []
    for candidate in public:
        identity = candidate['candidate_id']
        score = predictions[identity]
        c.require(set(score) == PREDICTION_FIELDS,
                  'Decision board accepts only the frozen grouped score fields')
        rank_position = _number(score['pairwise_rank_position'], 'pairwise rank position', positive=True)
        c.require(float(rank_position).is_integer(), 'Pairwise rank position must be an integer')
        feasibility = _number(score['factorized_feasibility_probability'],
                              'factorized feasibility score')
        c.require(0 <= feasibility <= 1, 'Factorized feasibility score is outside [0, 1]')
        disagreement = _number(score['factorized_feasibility_disagreement'],
                               'factorized score disagreement')
        utility = _number(score['factorized_decision_score'], 'factorized decision score')
        c.require(disagreement >= 0 and utility >= 0, 'Negative model score or spread')
        analytic_speedup = _number(candidate['latency_features']['estimated_speedup'],
                                   'analytic latency speedup', positive=True)
        paid = paid_by_id.get(identity)
        rows.append(dict(candidate_id=identity, formula=candidate['formula'],
            attempted=identity in attempted,
            pairwise_rank_position=int(rank_position),
            pairwise_rank_score=_number(score['pairwise_rank_score'], 'pairwise rank score'),
            analytic_latency_speedup=analytic_speedup,
            analytic_cycle_reduction=1.0-1.0/analytic_speedup,
            factorized_feasibility_score=feasibility,
            factorized_score_disagreement=disagreement,
            factorized_decision_score=utility,
            merit_saved_cycles=_number(candidate['saved'], 'merit saved cycles'),
            frequency_count=_number(candidate['runs'], 'frequency count'),
            paid_verification=(_paid_status(paid, area_cap=area_cap, clock_mhz=clock_mhz)
                               if paid is not None else None)))
    c.require(sorted(row['pairwise_rank_position'] for row in rows) ==
              list(range(1, len(rows)+1)),
              'Pairwise rank positions must form one complete unique ordering')
    rows.sort(key=lambda row: (row['pairwise_rank_position'], row['candidate_id']))
    recommended = next((row['candidate_id'] for row in rows if not row['attempted']), None)
    return dict(schema=SCHEMA, scope='public features + frozen predictions + paid observations only',
        area_cap_lut4=area_cap, minimum_routed_fmax_mhz=clock_mhz,
        uncertainty_calibrated=False,
        score_semantics=dict(pairwise_rank='relative ordering only; not speedup or probability',
            factorized_feasibility_score='uncalibrated ranking signal; never a hard feasibility gate',
            factorized_score_disagreement='uncalibrated ensemble spread; not an interval',
            analytic_latency_speedup='calibrated analytic estimate; not a measured outcome'),
        advisory_default_candidate_id=recommended,
        advisory_basis='highest pairwise-ranked unattempted candidate; LLM may override with a concise evidence-based decision summary',
        unattempted_candidates=sum(not row['attempted'] for row in rows),
        rows=rows)
