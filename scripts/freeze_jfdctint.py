"""Freeze twelve selection policies before the fresh BEEBS DCT candidate labels."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, beebs_workload as workload
from isaforge import factorized_selection_experiment as experiment
from isaforge import campaign_evidence

CORPUS = ROOT/'results/2026-10-21-model-training-corpus/corpus.json'
BASELINES = ('plan.json', 'discovery/discovery.json',
    'measurements/baseline/measurement.json', 'commands.json',
    'evaluation-protocol.json', 'attempt-ledger/baseline.json',
    'public.json', 'context.json', 'before.json')


def freeze(native, output):
    started = time.monotonic()
    native, output = Path(native).resolve(), Path(output).resolve()
    c.require(output.is_relative_to(ROOT) and not output.exists(), 'Fresh in-repository preregistration required')
    public, context, before = workload.baseline_public(native)
    c.require(not list((native/'attempt-ledger').glob('candidate_*.json')), 'Candidate attempts already exist')
    c.require(c.unseal(native/'public.json') == public and c.unseal(native/'context.json') == context and
              c.unseal(native/'before.json') == before, 'Prepared BEEBS public baseline differs')
    corpus = c.unseal(CORPUS)
    c.require(corpus['successful_labels'] == len(corpus['rows']) == 39 and
              len(corpus['independent_workload_groups']) == 6 and len(corpus['contexts']) == 7 and
              corpus['total_candidate_attempts'] == 42 and len(corpus['failed_attempts']) == 3,
              'Expected complete consumed 39-label six-source history')
    history = corpus['rows']
    c.require(all(row['workload_group'] != workload.GROUP for row in history + corpus['failed_attempts']),
              'Fresh target source already has historical outcomes')
    contexts = dict(corpus['contexts'])
    contexts[public[0]['benchmark']] = context
    costs = dict(historical_training_available=dict(successful_labels=39, failed_attempts=3,
        recorded_invalid_executions=sum(not row['reference_censored'] for row in corpus['failed_attempts']),
        censored_unknown_attempts=sum(row['reference_censored'] for row in corpus['failed_attempts']),
        total_candidate_attempts=42, total_candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
        source_corpus_sha256=c.sha(CORPUS)),
        target_baseline=context['baseline_provenance'],
        note='All 42 historical/development attempts are charged, including two recorded invalid executions and one infrastructure-censored unknown. Fitting excludes all three failures. Baseline/setup, calibration, model costs, outer operations, ledger and native commands retain separate potentially overlapping scopes.')
    for name, value in (('history.json', history), ('historical-failures.json', corpus['failed_attempts']),
                        ('public.json', public), ('contexts.json', contexts), ('cost-provenance.json', costs)):
        c.seal(output/'inputs'/name, value)
    for name in BASELINES:
        for suffix in ('', '.sha256'):
            target = output/'baseline'/(name+suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(native/(name+suffix), target)
    outer = {}
    for path in sorted((native/'outer-timing').glob('*')):
        target = output/'baseline/outer-timing'/path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        outer[path.name] = c.sha(path)
    c.require(outer, 'Baseline/setup outer operation timers required')
    bindings = {path.relative_to(ROOT).as_posix(): c.sha(path)
                for path in sorted((output/'baseline').rglob('*')) if path.is_file()}
    bindings.update({path.relative_to(ROOT).as_posix(): c.sha(path)
                     for path in sorted((output/'inputs').iterdir()) if path.is_file()})
    bindings[CORPUS.relative_to(ROOT).as_posix()] = c.sha(CORPUS)
    c.seal(output/'inputs/bindings.json', bindings)
    calibration = campaign_evidence._calibration(native)
    protocol = experiment.freeze(history, public, contexts, output/'selection',
        target_workload=workload.GROUP, target_labels_observed=0,
        calibration_cost_seconds=calibration['native_command_seconds'],
        cost_provenance=costs, input_bindings=bindings, scope='prospective source holdout')
    c.require(workload.baseline_public(native) == (public, context, before), 'Baseline changed during fitting')
    c.require(not list((native/'attempt-ledger').glob('candidate_*.json')), 'Candidate attempt during fitting')
    for name in BASELINES:
        c.require(c.sha(native/name) == c.sha(output/'baseline'/name), 'Prelabel baseline changed: ' + name)
    experiment.authenticate(output/'selection')
    evaluation = c.unseal(native/'evaluation-protocol.json')
    c.seal(output/'protocol.json', dict(schema='isaforge-jfdctint-preregistration-v1',
        scope='prospective source holdout', target_workload=workload.GROUP, context_id=context['context_id'],
        target_candidate_attempts_before_and_after_fit=0, target_candidate_labels_observed=0,
        baseline_files=list(BASELINES), baseline_outer_files=outer,
        source_history=CORPUS.relative_to(ROOT).as_posix(), selection_policy_count=12,
        selection_protocol_sha256=c.sha(output/'selection/protocol.json'),
        source_bindings={name: c.sha(ROOT/name) for name in
            ('scripts/freeze_jfdctint.py', workload.SOURCE, *experiment.SOURCES)},
        native_order=evaluation['pool_names'], native_candidate_budget=6,
        per_policy_attempt_budgets=[1, 2, 3], area_caps=[32, 64, 128], clock_mhz=12,
        freeze_outer_operation_seconds=time.monotonic()-started,
        limitations=protocol['limitations']))
    (output/'README.md').write_text(
        '# Fresh-source pre-measurement checkpoint\n\n'
        'Pinned BEEBS integer JPEG DCT, full original input and 64-coefficient verifier. '
        'The baseline/public protocol was authenticated before and after fitting, with zero candidate attempts both times. '
        'The source has no historical candidate outcomes. All 39 measured rows from six earlier Embench sources '
        'are available; related formula families are excluded identically for every learned policy. '
        'Both previous SHA contexts remain together in the training source group.\n\n'
        'One fixed new hypothesis separates learned hardware feasibility from the independently calibrated '
        'cycle benefit, alongside eleven unchanged policies. Five seeds, caps32/64/128, '
        'attempt budgets1/2/3 and a six-candidate declared-pool oracle are fixed. '
        'The primary endpoint is best verified feasible speedup at three attempts, +64LUT4 and12MHz. '
        'No post-label retuning, confidence guarantee, arbitrary RTL generation or combined-set result is claimed.\n\n'
        'All 42 historical attempts remain charged:39 successful labels, two recorded invalid executions '
        'and one infrastructure-censored unknown. Candidate-bootstrap spreads are estimator disagreement. '
        'The later campaign binds the complete manifest to the pushed Git checkpoint.\n\n'
        'Working command: `python scripts/freeze_jfdctint.py --native generated/beebs-jfdctint-2026-10-21-r2 '
        '--output results/2026-10-21-jfdctint-preregistration`. This refuses execution after any target attempt.\n')
    c.seal(output/'manifest.json', {path.relative_to(output).as_posix(): c.sha(path)
        for path in sorted(output.rglob('*')) if path.is_file()})
    return dict(preregistration=str(output), fitting_rows=protocol['historical_fitting_rows'],
                groups=protocol['historical_postfilter_groups'], target_labels_observed=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, default=ROOT/'generated/beebs-jfdctint-2026-10-21-r2')
    parser.add_argument('--output', type=Path, default=ROOT/'results/2026-10-21-jfdctint-preregistration')
    args = parser.parse_args()
    print(freeze(args.native, args.output))


if __name__ == '__main__':
    main()
