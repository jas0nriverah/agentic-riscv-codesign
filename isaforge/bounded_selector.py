"""Four-tool, host-enforced instruction selection over authenticated replay.

The remote policy gets serialized allowlisted data, never the provider, ledger,
filesystem paths or unqueried outcomes. Python callbacks are trusted test/local
policies, not a sandbox. Native guarded measurement integration and joint sets
remain separate milestones. Existing frozen predictors are unchanged.
"""
from __future__ import annotations

import copy
from pathlib import Path
import random
import statistics
import time

from . import budgeted_selection as b
from . import codesign as c
from .model import _number, validate_training_rows
from .speedup_corpus import family

SCHEMA = 'isaforge-bounded-selector-v1'
PROMPT = (
    'Select one RISC-V custom instruction, or the unchanged baseline. Maximize '
    'VERIFIED FEASIBLE whole-program speedup within the measurement-attempt '
    'budget. Predictions are uncalibrated, not measurements. Consider all '
    'provided heuristics, structure, uncertainty, area, timing and measurement '
    'cost. Use only list_candidates, predict, measure and finalize. Every '
    'submitted measure request, including an invalid ID or repeat, consumes an '
    'attempt; failed measurements also count. No unqueried outcome is available. '
    'Only a paid, correct, device-fitting, area/timing-feasible improving '
    'candidate can be finalized. You may stop early. Provide a short decision '
    'summary, not private chain of thought. Single instructions only; individual '
    'speedups and area cannot be added. This is consumed-data replay, not fresh '
    'hardware measurement or an unseen-workload experiment.'
)
BENEFIT_FIELDS = ('mean', 'lower', 'upper', 'std',
                  'saved_cycles_per_occurrence_mean', 'one_cycle_floor_members')
HARDWARE_FIELDS = ('area_delta_lut4_mean', 'area_delta_lut4_std',
                   'routed_fmax_min_mhz_mean', 'routed_fmax_min_mhz_std',
                   'log_measurement_seconds_mean', 'log_measurement_seconds_std',
                   'device_fit_probability')
MEASURED_FIELDS = ('baseline_cycles', 'candidate_cycles', 'speedup',
                   'area_delta_lut4', 'routed_fmax_min_mhz', 'device_fits',
                   'correctness_verified', 'measurement_seconds')


def _project_prediction(value, fields):
    result = {}
    for field in fields:
        if field in value:
            result[field] = _number(value[field], field)
    return result


def _observation(row):
    """Never send raw exceptions, source paths or arbitrary outcome metadata."""
    result = dict(candidate_id=row['candidate_id'], formula=row['formula'],
                  status=row.get('status', 'success'))
    if result['status'] == 'success':
        result.update({key: row[key] for key in MEASURED_FIELDS})
    else:
        result.update(error='Evaluation failed; no correctness/performance/hardware label.',
                      measurement_seconds=row['measurement_seconds'])
    return result


class ReplaySelectionSession:
    """Private evaluator state; the policy sees only ``request`` and tool results.

    Charges are atomically written before any provider lookup. A killed process
    leaves an explicitly pending attempt and cannot silently resume/retry. The
    final fallback is the best paid feasible improvement, otherwise baseline.
    """

    def __init__(self, public, training, predictions, provider, *, area_cap,
                 clock_mhz=12.0, budget=3, max_tool_calls=20, ledger_path,
                 historical_available_rows=None, historical_attempt_seconds=0.0):
        self.public = b.public_rows(public)
        c.require(len({r['benchmark'] for r in self.public}) == 1, 'One target context required')
        validate_training_rows(training)
        b.public_rows([{key: copy.deepcopy(row[key]) for key in b.PUBLIC_KEYS} for row in training])
        for row in training:
            b.validate_outcome(row)
        c.require(len({r['workload_group'] for r in training}) >= 2,
                  'At least two fitting historical groups required')
        targets = {family(r['formula']) for r in self.public}
        target_group = self.public[0]['benchmark'].split(':')[0]
        c.require(all(r['benchmark'] != self.public[0]['benchmark'] and
                      r['workload_group'] != target_group and
                      family(r['formula']) not in targets for r in training),
                  'Target context or related formula in fitting history')
        c.require(type(budget) is int and 0 < budget <= len(self.public), 'Invalid attempt budget')
        c.require(type(max_tool_calls) is int and 0 < max_tool_calls <= 100, 'Invalid tool limit')
        self.area_cap = _number(area_cap, 'area cap')
        c.require(self.area_cap >= 0, 'Negative area cap')
        self.clock_mhz = _number(clock_mhz, 'clock MHz', positive=True)
        self.budget, self.max_tool_calls = budget, max_tool_calls
        self.training = copy.deepcopy(training)
        self.provider = provider
        self._rows = {r['candidate_id']: r for r in self.public}
        self.predictions = {}
        for name in ('raw', 'normalized', 'ranking', 'hardware'):
            values = predictions[name]
            c.require(len(values) == len(self.public) and
                      {v['candidate_id'] for v in values} == self._rows.keys(),
                      'Complete unique prediction pool required')
            allowed = HARDWARE_FIELDS if name == 'hardware' else (
                ('rank_score',) if name == 'ranking' else BENEFIT_FIELDS)
            self.predictions[name] = {v['candidate_id']: _project_prediction(v, allowed)
                                      for v in values}
            for value in self.predictions[name].values():
                required = set(HARDWARE_FIELDS) if name == 'hardware' else (
                    {'rank_score'} if name == 'ranking' else {'mean', 'lower', 'upper', 'std'})
                c.require(required <= value.keys(), 'Incomplete prediction fields')
                c.require(all(value[key] >= 0 for key in value if key.endswith('_std') or key == 'std'),
                          'Negative predictive spread')
                if name == 'hardware':
                    c.require(0 <= value['device_fit_probability'] <= 1, 'Invalid device-fit probability')
        self.seed = predictions['seed']
        c.require(type(self.seed) is int and self.seed >= 0, 'Invalid seed')
        self.path = Path(ledger_path)
        c.require(not self.path.exists(), 'Preserve prior selection ledger')
        self.started = time.monotonic()
        self.observations, self.attempted_ids, self.messages = [], [], []
        self.calls, self.charged, self.model_calls = 0, 0, 0
        self._hardware_cache_version = 0
        self._hardware_cache = copy.deepcopy(self.predictions['hardware'])
        self.hardware_refit_seconds = 0.0
        available = len(training) if historical_available_rows is None else historical_available_rows
        c.require(type(available) is int and available >= len(training), 'Invalid history count')
        cost = _number(historical_attempt_seconds, 'historical attempt seconds')
        c.require(cost >= 0, 'Negative historical cost')
        self.ledger = dict(schema=SCHEMA, scope='consumed-data development replay',
            status='running', selected_id=None, best_speedup=1.0,
            constraints=dict(area_delta_lut4_cap=self.area_cap, clock_mhz=self.clock_mhz),
            limits=dict(measurement_attempts=budget, tool_calls=max_tool_calls),
            seed=self.seed, public_sha256=c.digest(self.public),
            training_sha256=c.digest(self.training), predictions_sha256=c.digest(predictions),
            historical_available_rows=available, historical_fit_rows=len(training),
            historical_fitting_groups=sorted({r['workload_group'] for r in training}),
            historical_attempt_seconds=cost, events=[], model_events=[], curve=[],
            fallback='best paid verified feasible improvement, else baseline',
            uncertainty_calibrated=False, new_native_jobs=0,
            timer_scope='Replay observation durations retain original record/ledger scope; not live evaluation wall time.',
            source_bindings={name: c.sha(c.ROOT/name) for name in
                ('isaforge/bounded_selector.py', 'isaforge/budgeted_selection.py')})
        self._persist()

    @property
    def finished(self):
        return self.ledger['status'] != 'running'

    def _best(self):
        feasible = [row for row in self.observations
                    if b._feasible(row, self.area_cap, self.clock_mhz) and row['speedup'] > 1]
        return min(feasible, key=lambda r: (-r['speedup'], r['area_delta_lut4'], r['candidate_id'])) if feasible else None

    def _persist(self):
        self.ledger.update(charged_attempts=self.charged, tool_calls=self.calls,
            model_calls=self.model_calls, hardware_refit_seconds=self.hardware_refit_seconds,
            host_elapsed_seconds=time.monotonic()-self.started,
            replayed_target_measurement_seconds=sum(e.get('replayed_measurement_seconds', 0)
                                                    for e in self.ledger['events']))
        c.seal(self.path, self.ledger)

    def request(self):
        """This JSON object is the entire remote model's visible state."""
        history = [{key: copy.deepcopy(row[key]) for key in
                    (*b.PUBLIC_KEYS, *MEASURED_FIELDS, 'workload_group')} for row in self.training]
        best = self._best()
        return copy.deepcopy(dict(schema=SCHEMA+'-request', instructions=PROMPT,
            scope=self.ledger['scope'], seed=self.seed,
            constraints=self.ledger['constraints'],
            remaining=dict(measurement_attempts=self.budget-self.charged,
                           tool_calls=self.max_tool_calls-self.calls),
            baseline=dict(candidate_id=None, speedup=1.0),
            historical_available_rows=self.ledger['historical_available_rows'],
            historical_fit_rows=len(history), historical_measurements=history,
            historical_attempt_seconds=self.ledger['historical_attempt_seconds'],
            candidates=self.public, observations=[_observation(r) for r in self.observations],
            attempted_candidate_ids=list(self.attempted_ids),
            incumbent=dict(candidate_id=best['candidate_id'] if best else None,
                           speedup=best['speedup'] if best else 1.0),
            uncertainty_calibrated=False, messages=self.messages))

    def _predictions(self, identities):
        if self._hardware_cache_version != len(self.observations):
            start = time.monotonic()
            values = b.HardwareSurrogate().fit(self.training+self.observations).predict(self.public)
            self.hardware_refit_seconds += time.monotonic()-start
            self._hardware_cache = {v['candidate_id']: _project_prediction(v, HARDWARE_FIELDS) for v in values}
            self._hardware_cache_version = len(self.observations)
        proxy = statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in self.training)
        clock = min(r['routed_fmax_min_mhz'] for r in self.training)
        best = self._best()
        incumbent = best['speedup'] if best else 1.0
        result = []
        for identity in identities:
            row, hardware = self._rows[identity], self._hardware_cache[identity]
            outside = [key for key in b.STRUCTURAL_COLUMNS if not
                       min(r[key] for r in self.training) <= row[key] <= max(r[key] for r in self.training)]
            result.append(dict(candidate_id=identity,
                raw_regression=self.predictions['raw'][identity],
                normalized_xgb=self.predictions['normalized'][identity],
                ranking=self.predictions['ranking'][identity], hardware_gp=hardware,
                calibrated_latency_speedup=row['latency_features']['estimated_speedup'],
                heuristic_area_lut4=proxy*row['tree_op_count'],
                heuristic_min_clock_mhz=clock,
                acquisition=b.hybrid_score(row, hardware, incumbent, self.area_cap, self.clock_mhz),
                zero_shot_acquisition=b.hybrid_score(row, self.predictions['hardware'][identity],
                                                   incumbent, self.area_cap, self.clock_mhz),
                paid_target_ids=[r['candidate_id'] for r in self.observations],
                outside_training_ranges=outside, uncertainty_calibrated=False))
        return result

    def _point(self):
        best = self._best()
        return dict(budget=self.charged, selected_id=best['candidate_id'] if best else None,
            best_speedup=best['speedup'] if best else 1.0, attempted_ids=list(self.attempted_ids),
            measured_ids=[r['candidate_id'] for r in self.observations],
            replayed_target_measurement_seconds=sum(e.get('replayed_measurement_seconds', 0)
                                                    for e in self.ledger['events']))

    def stop(self, reason):
        if not self.finished:
            best = self._best()
            self.ledger.update(status=reason, selected_id=best['candidate_id'] if best else None,
                               best_speedup=best['speedup'] if best else 1.0)
            self._persist()

    def _result(self, event, result):
        event.update(public_result=copy.deepcopy(result), status=result['status'])
        if ('charged_attempt' in event and
                (not self.ledger['curve'] or self.ledger['curve'][-1]['budget'] != self.charged)):
            self.ledger['curve'].append(self._point())
        self.messages.append(dict(tool=event.get('tool'), result=copy.deepcopy(result)))
        self._persist()
        return copy.deepcopy(result)

    def call(self, action):
        if self.finished:
            return dict(status='error', error='Session closed.')
        if self.calls >= self.max_tool_calls:
            self.stop('tool_limit')
            return dict(status='error', error='Tool-call budget exhausted.')
        self.calls += 1
        tool = action.get('tool') if isinstance(action, dict) else None
        event = dict(sequence=self.calls, tool=tool if isinstance(tool, str) else None,
                     charged_before=self.charged, status='pending')
        self.ledger['events'].append(event)
        # Even malformed/repeated measurement requests are charged before lookup.
        if tool == 'measure' and self.charged < self.budget:
            self.charged += 1
            event['charged_attempt'] = self.charged
            self._persist()
        error = lambda message: self._result(event, dict(status='error', error=message))
        if not isinstance(action, dict) or set(action) != {'tool', 'arguments'} or not isinstance(action['arguments'], dict):
            return error('Expected one tool and an arguments object.')
        arguments = action['arguments']
        if tool == 'list_candidates':
            if arguments:
                return error('list_candidates accepts no arguments.')
            return self._result(event, dict(status='ok', candidates=copy.deepcopy(self.public)))
        if tool == 'predict':
            identities = arguments.get('candidate_ids')
            if (set(arguments) != {'candidate_ids'} or not isinstance(identities, list) or
                not identities or any(type(i) is not str for i in identities) or
                len(set(identities)) != len(identities) or not set(identities) <= self._rows.keys()):
                return error('predict requires unique public candidate IDs.')
            return self._result(event, dict(status='ok', predictions=self._predictions(identities)))
        if tool == 'measure':
            if 'charged_attempt' not in event:
                return error('Measurement-attempt budget exhausted.')
            identity = arguments.get('candidate_id')
            if set(arguments) != {'candidate_id'} or type(identity) is not str or identity not in self._rows:
                self.ledger['curve'].append(self._point())
                return error('measure requires one public candidate ID; attempt charged.')
            event['candidate_id'] = identity
            if identity in self.attempted_ids:
                self.ledger['curve'].append(self._point())
                return error('Candidate already attempted; repeat charged without a new evaluation.')
            self.attempted_ids.append(identity)
            self._persist()
            start = time.monotonic()
            try:
                outcome = copy.deepcopy(self.provider(copy.deepcopy(self._rows[identity])))
                success = b.validate_outcome(outcome, self._rows[identity])
            except BaseException as exc:
                event.update(status='interrupted' if not isinstance(exc, Exception) else 'provider_error',
                             provider_exception_type=type(exc).__name__,
                             replayed_measurement_seconds_unknown=True,
                             provider_elapsed_seconds=time.monotonic()-start)
                self.ledger['curve'].append(self._point())
                self.stop(event['status'])
                if not isinstance(exc, Exception):
                    raise
                return dict(status='error', error='Evaluation unavailable; attempt charged and session stopped.')
            event.update(observation=outcome, replayed_measurement_seconds=outcome['measurement_seconds'],
                         provider_elapsed_seconds=time.monotonic()-start)
            if success:
                self.observations.append(outcome)
            self.ledger['curve'].append(self._point())
            return self._result(event, dict(status='ok' if success else 'failed', observation=_observation(outcome)))
        if tool == 'finalize':
            identity, summary = arguments.get('candidate_id'), arguments.get('summary')
            if (set(arguments) != {'candidate_id', 'summary'} or
                not isinstance(summary, str) or not 0 < len(summary) <= 1000 or
                (identity is not None and type(identity) is not str)):
                return error('finalize requires a candidate ID or null and a short summary.')
            chosen = next((r for r in self.observations if r['candidate_id'] == identity), None)
            if identity is not None and (chosen is None or not b._feasible(chosen, self.area_cap, self.clock_mhz) or chosen['speedup'] <= 1):
                return error('Choice must be a paid verified feasible improvement, or null baseline.')
            self.ledger.update(status='finalized', selected_id=identity,
                best_speedup=chosen['speedup'] if chosen else 1.0, decision_summary=summary)
            return self._result(event, dict(status='ok', selected_id=identity,
                                           speedup=self.ledger['best_speedup']))
        return error('Unknown tool; only list_candidates, predict, measure and finalize are allowed.')


class MatchedBaselinePolicy:
    """Existing fixed policies using only the same serialized four-tool channel.

    This is a deterministic control, not an LLM. It consumes full measurement
    budgets exactly as the preserved experiments do, including failed attempts.
    """
    def __init__(self, policy):
        c.require(policy in b.POLICIES, 'Unknown matched baseline')
        self.policy = policy
        self.identity = dict(provider='deterministic-matched-control', policy=policy)
        self.last_usage = {}

    def choose(self, request):
        rows = copy.deepcopy(request['candidates'])
        random.Random(request['seed']).shuffle(rows)
        attempted = set(request['attempted_candidate_ids'])
        rows = [r for r in rows if r['candidate_id'] not in attempted]
        if request['remaining']['measurement_attempts'] == 0 or not rows:
            return dict(tool='finalize', arguments=dict(
                candidate_id=request['incumbent']['candidate_id'], summary='Best paid verified feasible candidate; baseline if none.'))
        estimates = None
        if self.policy not in ('frequency', 'merit', 'calibrated_latency', 'random'):
            messages = request['messages']
            if (messages and messages[-1]['tool'] == 'predict' and
                    messages[-1]['result']['status'] == 'ok'):
                estimates = {p['candidate_id']: p for p in messages[-1]['result']['predictions']}
            if estimates is None or not {r['candidate_id'] for r in rows} <= estimates.keys():
                return dict(tool='predict', arguments=dict(candidate_ids=[r['candidate_id'] for r in rows]))
        def score(row):
            analytic = row['latency_features']['estimated_speedup']
            if self.policy == 'frequency': return (row['runs'],)
            if self.policy == 'merit': return (row['saved'],)
            if self.policy == 'calibrated_latency': return (analytic,)
            if self.policy == 'random': return (0,)
            value = estimates[row['candidate_id']]
            if self.policy == 'latency_cost_heuristic':
                area = value['heuristic_area_lut4']
                return (int(area <= request['constraints']['area_delta_lut4_cap'] and
                            value['heuristic_min_clock_mhz'] >= request['constraints']['clock_mhz']),
                        max(0, analytic-request['incumbent']['speedup'])/max(1, area), analytic)
            if self.policy == 'raw_regression': return (value['raw_regression']['mean'],)
            if self.policy == 'normalized_xgb': return (value['normalized_xgb']['mean'],)
            if self.policy == 'ranking': return (value['ranking']['rank_score'],)
            return (value['acquisition' if self.policy == 'hybrid_gp_adapt' else 'zero_shot_acquisition'], analytic)
        return dict(tool='measure', arguments=dict(candidate_id=max(rows, key=score)['candidate_id']))


def run_selector(session, policy, *, max_model_calls=12):
    """Remote provider chooses; deterministic host owns every acceptance/charge."""
    c.require(type(max_model_calls) is int and 0 < max_model_calls <= 100, 'Invalid model limit')
    session.ledger['policy_identity'] = copy.deepcopy(getattr(policy, 'identity', {'provider': 'trusted-local-test'}))
    session.ledger['max_model_calls'] = max_model_calls
    while not session.finished and session.model_calls < max_model_calls:
        if session.calls >= session.max_tool_calls:
            session.stop('tool_limit')
            break
        session.model_calls += 1
        event = dict(call=session.model_calls, status='pending')
        session.ledger['model_events'].append(event)
        session._persist()
        start = time.monotonic()
        try:
            action = policy.choose(session.request())
            event.update(status='complete', elapsed_seconds=time.monotonic()-start,
                         usage=copy.deepcopy(getattr(policy, 'last_usage', {})))
        except BaseException as exc:
            event.update(status='model_error' if isinstance(exc, Exception) else 'interrupted', error_type=type(exc).__name__,
                         usage=copy.deepcopy(getattr(policy, 'last_usage', {})),
                         elapsed_seconds=time.monotonic()-start)
            session.stop(event['status'])
            if not isinstance(exc, Exception):
                raise
            break
        finally:
            event['provider_trace'] = copy.deepcopy(getattr(policy, 'last_trace', []))
            event['memory_trace'] = copy.deepcopy(getattr(policy, 'last_memory_trace', {}))
            session._persist()
        try:
            session.call(action)
            event['tool_sequence'] = session.calls
            session._persist()
        except Exception as exc:
            event.update(status='host_error', error_type=type(exc).__name__)
            session.stop('host_error')
            break
    session.stop('model_call_limit')
    return copy.deepcopy(session.ledger)
