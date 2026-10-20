"""Archive and replay the prospective, equal-budget multi-workload campaign.

Historical native archives are reused rather than duplicated. Replay refits the
fixed models, authenticates processor evidence, and reruns paid-label policies;
it launches no compiler, simulator, synthesis, or routing jobs.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c
from isaforge import campaign_evidence as evidence
from scripts.reproduce_codesign import pack_archive, restore_archive
from scripts.reproduce_prospective import authenticate_files

SNAPSHOT = ROOT / 'results/2026-10-20-budget-campaign'
PREREG = ROOT / 'results/2026-10-20-budget-preregistration'
HISTORY = ('results/2026-10-19-automatic-aha-mont64',
           'results/2026-10-20-automatic-crc32',
           'results/2026-10-20-slre-transfer')


def restore_history(output):
    roots = []
    for name in HISTORY:
        snapshot = ROOT/name
        archive = c.unseal(snapshot/'archive-manifest.json')
        if 'experiment' in archive:
            archive = archive['experiment']
        target = Path(output)/snapshot.name
        restore_archive(snapshot, archive, target)
        roots.append(target)
    return roots


def check_prelabel(selection, prereg):
    selection = Path(selection)
    entries = authenticate_files(prereg, 'manifest.json')
    cohort = c.unseal(selection/'cohort.json')
    # Derive the complete prelabel inventory from the sealed cohort, rather than
    # accepting a manifest that silently omitted every selection artifact.
    required = {'selection/cohort.json', 'selection/cohort.json.sha256'}
    for name, target in cohort['targets'].items():
        baseline = 'selection/'+target['baseline_snapshot']
        required.update((baseline, baseline+'.sha256'))
        required.update('selection/'+name+'/'+artifact for artifact in target['selection_artifacts'])
    declared = {name for name in entries if name.startswith('selection/')}
    c.require(declared == required, 'Preregistration must contain the complete frozen selection inventory')
    for name, digest in entries.items():
        # Qualification logs and the amended protocol are independently kept in
        # preregistration; selection artifacts must remain byte-for-byte equal.
        if name.startswith('selection/'):
            path = (selection/name.removeprefix('selection/')).resolve()
            c.require(path.is_relative_to(selection.resolve()), 'Prelabel selection path escapes root')
            c.require(c.sha(path) == digest,
                      'Changed prelabel selection artifact: '+name)
    return c.sha(Path(prereg)/'manifest.json')


def check_prelabel_commit(prereg, commit):
    """Authenticate the claimed commit's exact manifest bytes, without Git writes."""
    c.require(isinstance(commit, str) and len(commit) == 40 and
              all(x in '0123456789abcdef' for x in commit), 'Exact pushed prelabel Git commit required')
    prereg = Path(prereg).resolve()
    c.require(prereg.is_relative_to(ROOT.resolve()), 'Preregistration must be inside the checkout')
    relative = prereg.relative_to(ROOT.resolve()).as_posix()+'/manifest.json'
    result = subprocess.run(['git','show',commit+':'+relative], cwd=ROOT, capture_output=True, check=False)
    c.require(result.returncode == 0, 'Prelabel commit does not contain the preregistration manifest')
    c.require(hashlib.sha256(result.stdout).hexdigest() == c.sha(prereg/'manifest.json'),
              'Prelabel Git commit manifest differs from the supplied preregistration')


def pool_qualification(root, plan, receipts):
    """Recompute a too-small calibrated pool from a successful checked baseline.

    A successful compiler/profile command does not establish that the declared
    candidate pool exists. Reuse the original extractor and latency filter,
    without lowering/installing or measuring any custom candidate.
    """
    root = Path(root)
    c.require(all(r['failure'] is None and r['returncode'] == r['expected_returncode'] for r in receipts),
              'Pool qualification requires successful expected native commands')
    adapter = evidence._adapter(plan)
    if hasattr(adapter, 'check_plan'): adapter.check_plan(plan)
    if hasattr(adapter, 'validate_runtime_inputs'): adapter.validate_runtime_inputs(root)
    evidence._observations(root, adapter, receipts)
    attempts = list((root/'discovery').glob('attempt-*'))
    c.require(len(attempts) == 1 and not (root/'discovery/discovery.json').exists(),
              'Pool qualification needs exactly one incomplete discovery attempt')
    attempt = attempts[0]
    calibration = evidence._calibration(root)
    c.require(c.read(root/'inputs/latency-calibration.json') == calibration, 'Qualification calibration differs')
    marked, sites = evidence.lowering.mark_assembly((attempt/'program.s').read_text())
    c.require(marked == (attempt/'marked.S').read_text(), 'Qualification marked assembly differs')
    image = attempt/'marked/firmware.hex'
    c.require(c.sha(image) == c.sha(attempt/'original/firmware.hex'), 'Qualification baseline bytes changed')
    c.require(evidence.validate_isa((image.parent/'disassembly.txt').read_text())['custom_static_sites'] == 0,
              'Qualification baseline contains a custom instruction')
    program = evidence.lowering.read_program((image.parent/'disassembly.txt').read_text())
    mapped = evidence.lowering.map_sites(sites, (image.parent/'symbols.txt').read_text())
    profile_path = attempt/'profile/simulation.json'
    profile_log = profile_path.relative_to(root).as_posix()
    c.require(any(r['log'] == profile_log and r['returncode'] == r['expected_returncode'] == 0 for r in receipts),
              'Pool qualification lacks a successful checked profile receipt')
    raw = c.read(profile_path); performance = evidence.validate_execution(raw)
    adapter.validate_memory(raw)
    c.require(raw['markers'] == 2 and sum(raw['region_counts'].values())+1 == performance['instructions'],
              'Qualification profile counters differ')
    result = evidence.partition.EXTRACT(program, raw, mapped, plan['pool_size'])
    table = evidence.partition.latency.latency_table(calibration)
    count = 0
    for candidate in result['executable_candidates']:
        try:
            for occurrence in candidate['occurrences']:
                for pc in occurrence['pcs']:
                    evidence.partition.latency.instruction_latency(program[int(pc,16)], table)
        except ValueError:
            continue
        count += 1
    c.require(count < plan['pool_size'], 'Qualification actually has the declared calibrated candidate pool')
    return count


def failed_cost(root):
    root = Path(root)
    c.require(not list((root/'measurements').rglob('measurement.json')),
              'Qualification failure unexpectedly contains a measurement')
    c.require(not any(path.is_dir() and path.name != 'baseline'
                      for path in (root/'measurements').glob('*')),
              'Qualification failure contains a candidate attempt')
    plan = c.unseal(root/'plan.json')
    c.require(c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == plan['context_id'],
              'Failed qualification context digest differs')
    for name, digest in plan['source_bindings'].items():
        c.require(c.sha(ROOT/name) == digest, 'Failed qualification source changed')
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name) == digest, 'Failed qualification input changed')
    rows = evidence._receipts(root, allow_failures=True)
    c.require(all(not r['log'].startswith('measurements/') or
                  r['log'].startswith('measurements/baseline/') for r in rows),
              'Qualification failure contains a candidate receipt')
    bad = [r for r in rows if r['failure'] or r['returncode'] != r['expected_returncode']]
    record = c.unseal(root/'qualification-failure.json')
    c.require(record['context_id'] == plan['context_id'] and
              record['candidate_labels_read'] == 0, 'Missing failed qualification evidence')
    extra = {}
    if record.get('phase') == 'candidate pool qualification':
        count = pool_qualification(root, plan, rows)
        c.require(type(record.get('eligible_formula_count')) is int and record['eligible_formula_count'] == count,
                  'Recorded eligible formula count differs from recomputation')
        extra = dict(phase=record['phase'], eligible_formula_count=count)
    else:
        c.require(bad, 'Missing failed native qualification command')
    return dict(workload=plan['workload'], context_id=plan['context_id'],
                commands=len(rows), command_seconds=sum(r['elapsed_seconds'] for r in rows),
                reason=record['reason'], candidate_labels=0, **extra)


def diagnostic_cost(root):
    """Authenticate one static link-map diagnostic, never a hardware outcome."""
    root = Path(root)
    c.require(not (root/'measurements').exists(), 'Link diagnostic contains measurements or candidate attempts')
    plan = c.unseal(root/'plan.json')
    c.require(c.digest({k:v for k,v in plan.items() if k != 'context_id'}) == plan['context_id'],
              'Link diagnostic context digest differs')
    c.require(plan.get('diagnostic') == 'Exact original link with map emission; no simulator/candidate labels',
              'Unexpected diagnostic scope')
    for name, digest in plan['source_bindings'].items():
        c.require(c.sha(ROOT/name) == digest, 'Link diagnostic source changed: '+name)
    for name, digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name) == digest, 'Link diagnostic input changed: '+name)
    rows = evidence._receipts(root)
    c.require(len(rows) == 1, 'Exactly one static diagnostic command required')
    row = rows[0]; argv = row['argv']
    flags = plan['compiler_flags']; start = 1+len(flags)
    c.require(len(argv) > start+2 and argv[start] == '-I', 'Diagnostic compiler prefix differs')
    inputs = Path(argv[start+1]); mapping = Path(row['cwd'])/'diagnostic.map'
    expected = [plan['tools']['gcc']['path'], *flags, '-I', str(inputs),
        '-Wl,--no-relax', '-Wl,--gc-sections', '-Wl,-T,'+str(inputs/'soc_link.ld'),
        *[str(inputs/name) for name in ('soc_start.S','embench_firmware.c','embench_memory.c','program.c','beebsc.c')],
        '-lgcc', '-Wl,-Map,'+str(mapping), '-o', str(Path(row['cwd'])/'diagnostic.elf')]
    c.require(argv == expected and row['returncode'] == row['expected_returncode'] == 1,
              'Diagnostic must be the exact failed original link plus map emission')
    c.require(not any('candidate_' in value or '/measurements/' in value for value in argv),
              'Candidate command is not a static qualification diagnostic')
    summary = c.unseal(root/'diagnostic-summary.json')
    c.require(summary['context_id'] == plan['context_id'] and summary['workload'] == plan['workload']
              and summary['candidate_labels_read'] == 0, 'Diagnostic identity or label count differs')
    c.require(c.sha(root/'diagnostic.map') == summary['map_sha256'], 'Diagnostic map changed')
    program_end = [line.strip() for line in (root/'diagnostic.map').read_text().splitlines()
                   if '_program_end = .' in line]
    c.require(program_end and program_end == summary['program_end'], 'Diagnostic program-end projection differs')
    return dict(workload=plan['workload'], context_id=plan['context_id'], commands=1,
        command_seconds=row['elapsed_seconds'], candidate_labels=0, map_sha256=summary['map_sha256'],
        program_end=program_end, scope='Static failed link diagnosis; no hardware or candidate labels.')


def pack(selection, targets, failures, snapshot, prereg, commit, *, diagnostics=()):
    selection, snapshot, prereg = (Path(p).resolve() for p in (selection, snapshot, prereg))
    targets, failures, diagnostics = ([Path(p).resolve() for p in group]
                                     for group in (targets, failures, diagnostics))
    c.require(not snapshot.exists(), 'Preserve existing experiment snapshots')
    roots = targets+failures+diagnostics
    c.require(len(set(roots)) == len(roots), 'Native roots must be distinct; duplicate roots would double-count costs')
    prelabel_hash = check_prelabel(selection, prereg)
    check_prelabel_commit(prereg, commit)
    report = evidence.evaluate(selection, targets, verify=True)
    failure_costs = [failed_cost(root) for root in failures]
    diagnostic_costs = [diagnostic_cost(root) for root in diagnostics]
    snapshot.mkdir(parents=True)
    shutil.copytree(selection, snapshot/'selection')
    archives = {}
    for root in map(Path, targets):
        name = 'target-'+c.unseal(root/'plan.json')['workload']
        archives[name] = pack_archive(root, snapshot/(name+'.tar.gz'))
    for index, root in enumerate(map(Path, failures)):
        name = 'qualification-failure-'+str(index)
        archives[name] = pack_archive(root, snapshot/(name+'.tar.gz'))
    for index, root in enumerate(map(Path, diagnostics)):
        name = 'link-diagnostic-'+str(index)
        archives[name] = pack_archive(root, snapshot/(name+'.tar.gz'))
    c.seal(snapshot/'archive-manifest.json', archives)
    c.seal(snapshot/'qualification-costs.json', failure_costs)
    c.seal(snapshot/'diagnostic-costs.json', diagnostic_costs)
    sources = {name: digest for root in map(Path, list(targets)+list(failures)+list(diagnostics))
               for name, digest in c.unseal(root/'plan.json')['source_bindings'].items()}
    for name in report['targets']:
        sources.update(c.unseal(selection/name/'protocol.json')['source_bindings'])
    for name in (evidence.SOURCE, 'scripts/reproduce_budget_campaign.py',
                 'scripts/reproduce_codesign.py', 'scripts/reproduce_prospective.py'):
        sources[name] = c.sha(ROOT/name)
    c.require(all(c.sha(ROOT/name) == digest for name,digest in sources.items()),
              'Source manifest differs from current checkout')
    c.seal(snapshot/'source-manifest.json', sources)
    c.seal(snapshot/'provenance.json', dict(
        prelabel_commit=commit, preregistration=str(prereg.relative_to(ROOT)),
        preregistration_manifest_sha256=prelabel_hash,
        history_manifests={name:c.sha(ROOT/name/'archive-manifest.json') for name in HISTORY},
        source_storage='Git plus source hashes; native archives also retain their original source snapshots.',
        costs='Candidate wall times, native command times, setup, historical labels and inference have separate scopes; do not add overlapping timers.'))
    c.seal(snapshot/'manifest.json', {p.relative_to(snapshot).as_posix():c.sha(p)
        for p in sorted(snapshot.rglob('*')) if p.is_file()})
    return dict(snapshot=str(snapshot), targets=len(targets), failed_qualifications=len(failures),
                static_link_diagnostics=len(diagnostics), new_native_jobs=0)


def replay(snapshot, output):
    snapshot, output = map(Path, (snapshot, output))
    authenticate_files(snapshot, 'manifest.json')
    provenance = c.unseal(snapshot/'provenance.json')
    prereg = ROOT/provenance['preregistration']
    c.require(check_prelabel(snapshot/'selection', prereg) ==
              provenance['preregistration_manifest_sha256'], 'Prelabel manifest differs')
    check_prelabel_commit(prereg, provenance['prelabel_commit'])
    for name, digest in c.unseal(snapshot/'source-manifest.json').items():
        c.require(c.sha(ROOT/name) == digest, 'Frozen source changed: '+name)
    for name, digest in provenance['history_manifests'].items():
        c.require(c.sha(ROOT/name/'archive-manifest.json') == digest, 'Historical archive changed')
    targets, failures, diagnostics = [], [], []
    for name, archive in c.unseal(snapshot/'archive-manifest.json').items():
        target = output/name
        restore_archive(snapshot, archive, target)
        if name.startswith('target-'): targets.append(target)
        elif name.startswith('qualification-failure-'): failures.append(target)
        elif name.startswith('link-diagnostic-'): diagnostics.append(target)
        else: raise ValueError('Unknown campaign archive category: '+name)
    c.require([failed_cost(root) for root in failures] == c.unseal(snapshot/'qualification-costs.json'),
              'Failed qualification replay differs')
    c.require([diagnostic_cost(root) for root in diagnostics] == c.unseal(snapshot/'diagnostic-costs.json'),
              'Static link diagnostic replay differs')
    history = restore_history(output/'history')
    report = evidence.evaluate(snapshot/'selection', targets, history_roots=history, verify=True)
    return dict(target_workloads=list(report['targets']),
        candidate_attempts=sum(len(r['analytic_cycle_residuals'])+len(r['failed_attempts'])
                               for r in report['audits'].values()),
        policy_budget_seed_endpoints=sum(r['policy_seed_cap_budget_outcomes'] for r in report['targets'].values()),
        failed_qualification_command_seconds=sum(failed_cost(root)['command_seconds'] for root in failures),
        static_link_diagnostic_command_seconds=sum(diagnostic_cost(root)['command_seconds'] for root in diagnostics),
        exact_historical_prediction_refit=True, new_native_jobs=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack','replay'))
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--output', type=Path, default=ROOT/'generated/reproduction/budget-campaign')
    parser.add_argument('--preregistration', type=Path, default=PREREG)
    parser.add_argument('--prelabel-commit')
    parser.add_argument('--selection-root', type=Path)
    parser.add_argument('--target-root', type=Path, action='append')
    parser.add_argument('--failed-root', type=Path, action='append')
    parser.add_argument('--diagnostic-root', type=Path, action='append')
    args = parser.parse_args(argv)
    if args.command == 'pack':
        c.require(all((args.prelabel_commit,args.selection_root,args.target_root)), 'Pack requires frozen selection and target roots')
        result = pack(args.selection_root, args.target_root, args.failed_root or [],
                      args.snapshot, args.preregistration, args.prelabel_commit,
                      diagnostics=args.diagnostic_root or [])
    else:
        result = replay(args.snapshot, args.output)
    print(result)


if __name__ == '__main__':
    main()
