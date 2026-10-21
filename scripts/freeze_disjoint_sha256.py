"""Freeze the fixed ML comparison after authenticating zero native attempts.

Requires the already prepared disjoint SHA256 baseline. This command does not
start hardware jobs, read target candidate outcomes or change model settings.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c, training_workload as t
from isaforge import feasible_benefit_experiment as e

NATIVE_FILES = ('plan.json', 'discovery/discovery.json',
    'measurements/baseline/measurement.json', 'commands.json',
    'evaluation-protocol.json', 'attempt-ledger/baseline.json',
    'public.json', 'context.json', 'before.json')
CORPUS = ROOT/'results/2026-10-21-six-workload-corpus/corpus.json'


def freeze(native, output):
    native, output = Path(native).resolve(), Path(output).resolve()
    c.require(not output.exists(), 'Fresh preregistration directory required')
    public, context, before = t.baseline_public(native)
    c.require(not list((native/'attempt-ledger').glob('candidate_*.json')),
              'Candidate attempts already exist')
    c.require(c.unseal(native/'public.json') == public and
              c.unseal(native/'context.json') == context, 'Public baseline changed')
    corpus = c.unseal(CORPUS)
    history = [row for row in corpus['rows'] if row['workload_group'] != 'embench-nettle-sha256']
    c.require(len(history) == 27, 'Expected 27 source-excluded historical labels')
    contexts = {key:val for key,val in corpus['contexts'].items()
                if key in {row['benchmark'] for row in history}}
    contexts[public[0]['benchmark']] = context
    previous = c.unseal(ROOT/'results/2026-10-21-sha256-selection/model/protocol.json')
    costs = dict(historical_training_available=corpus['historical_costs'],
        consumed_development=dict(candidate_attempts=corpus['total_candidate_attempts'],
            successful_labels=corpus['successful_labels'],
            candidate_wall_seconds=corpus['total_candidate_attempt_wall_seconds'],
            old_sha_labels_excluded_from_fit=6,
            old_sha_candidate_wall_seconds=corpus['new_candidate_wall_seconds']),
        target_baseline=context['baseline_provenance'],
        note='Historical and target candidate wall, command time, calibration, baseline/setup and inference have separate potentially overlapping scopes. Failed historical attempts remain charged. All old SHA labels informed development but are excluded from fitting.')
    for name, value in (('history.json',history), ('public.json',public),
                        ('contexts.json',contexts), ('cost-provenance.json',costs)):
        c.seal(output/'inputs'/name, value)
    for name in NATIVE_FILES:
        for suffix in ('', '.sha256'):
            destination = output/'baseline'/(name+suffix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(native/(name+suffix), destination)
    bindings = {str((output/'baseline'/name).relative_to(ROOT)):c.sha(output/'baseline'/name)
                for name in NATIVE_FILES}
    bindings[str(CORPUS.relative_to(ROOT))] = c.sha(CORPUS)
    for name in ('history.json','public.json','contexts.json','cost-provenance.json'):
        bindings[str((output/'inputs'/name).relative_to(ROOT))] = c.sha(output/'inputs'/name)
    c.seal(output/'inputs/bindings.json', bindings)
    protocol = e.freeze(history,public,contexts,output/'selection',
        target_workload='embench-nettle-sha256',target_labels_observed=0,
        calibration_cost_seconds=previous['calibration_command_seconds'],
        cost_provenance=costs,scope='consumed-source fresh-candidate-pool',input_bindings=bindings)
    public_after, context_after, before_after = t.baseline_public(native)
    c.require((public_after, context_after, before_after) == (public, context, before),
              'Native baseline changed during fit')
    c.require(not list((native/'attempt-ledger').glob('candidate_*.json')),
              'Candidate attempt during fit')
    for name in NATIVE_FILES:
        c.require(c.sha(native/name) == c.sha(output/'baseline'/name),
                  'Native prelabel artifact changed: '+name)
    e.authenticate(output/'selection')
    c.seal(output/'protocol.json', dict(schema='isaforge-feasible-benefit-preregistration-v1',
        scope='Fresh disjoint candidates on consumed original SHA256 source/input; no unseen-source claim.',
        target_workload='embench-nettle-sha256',context_id=context['context_id'],
        target_candidate_attempts_before_and_after_fit=0,target_candidate_labels_observed=0,
        baseline_files=list(NATIVE_FILES),source_history=str(CORPUS.relative_to(ROOT)),
        selection_protocol_sha256=c.sha(output/'selection/protocol.json'),
        source_bindings={name:c.sha(ROOT/name) for name in
                         ('scripts/freeze_disjoint_sha256.py','isaforge/training_workload.py',*e.SOURCES)},
        native_candidate_budget=6,per_policy_attempt_budgets=[1,2,3],
        area_caps=[32,64,128],clock_mhz=12,
        native_order=['candidate_01','candidate_12','candidate_23','candidate_32','candidate_43','candidate_56'],
        candidate_rule=t.POOL_RULE,selection_policy_count=11,
        limitations=['Fresh candidates share formula families and source/input with earlier SHA measurements.',
            'All six historical workloads informed development; all old SHA labels are excluded from fitting.',
            'No retuning after this freeze.',
            'Utility and bootstrap spread are not speedup or calibrated confidence.',
            'All six outcomes are measured for an oracle and cooperative budgeted replay; not a live adaptive hardware search.',
            'Single-instruction decisions only; selected sets require joint measurements.']))
    (output/'README.md').write_text(
        '# Pre-measurement ML checkpoint\n\n'
        'Frozen before the six disjoint SHA256 candidate attempts. The native baseline was '
        'authenticated immediately before and after fitting, with zero candidate ledgers both times. '
        'The complete source-bound JSON models and predictions for eleven policies are in `selection/`; '
        'baseline inputs, partition, pool and native evaluation protocol are under `baseline/`. '
        'The later campaign provenance records the Git checkpoint.\n\n'
        'This is fresh-candidate evidence on consumed SHA256 source/input, not unseen-workload generalization. '
        'All 27 available non-SHA successful labels and three historical failures are charged separately. '
        'All six old SHA labels are excluded from fitting but retained as development cost. '
        'Related-family exclusions are identical for all learned policies.\n\n'
        'The preparation command was `python scripts/freeze_disjoint_sha256.py`; it requires the '
        'unmeasured native pool and refuses reuse after candidate attempts. For prediction reproduction '
        'after collection, use `python -m isaforge.feasible_benefit_experiment freeze` with the sealed '
        '`inputs/` files, area caps32/64/128, fixed five seeds, calibration5.095776124944678seconds, '
        '`--target-labels-observed 0` and `--scope "consumed-source fresh-candidate-pool"`. '
        'That refit reproduces the original predictions, not a new prospective claim.\n')
    manifest = {str(path.relative_to(output)):c.sha(path)
                for path in sorted(output.rglob('*')) if path.is_file()}
    c.seal(output/'manifest.json', manifest)
    return dict(preregistration=str(output),fitting_rows=protocol['historical_fitting_rows'],
        groups=protocol['historical_postfilter_groups'],files=len(manifest),target_labels_observed=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,default=ROOT/'generated/disjoint-sha256-2026-10-21')
    parser.add_argument('--output',type=Path,default=ROOT/'results/2026-10-21-feasible-benefit-preregistration')
    args = parser.parse_args()
    print(freeze(args.native,args.output))


if __name__ == '__main__':
    main()
