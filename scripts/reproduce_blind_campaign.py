"""Explicit replay adapter for the frozen cohort's mixed-clock diagnostics.

The frozen strict checker remains unchanged. Calendar start timestamps and
monotonic durations are retained separately; inferred UTC end instants are
reported as diagnostics, not used as a common-clock enclosure proof. Native
one-attempt receipts and the source-bound blocking collector establish order.
No timing correction, tolerance, policy change or native retry is performed.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c
from isaforge.model import _number
from scripts import blind_campaign as frozen

SOURCE = 'scripts/reproduce_blind_campaign.py'
COLLECTOR = 'scripts/collect_blind_campaign.py'
CONTRACT = 'isaforge-blind-monotonic-accounting-v1'
COLLECTION = ROOT/'results/2026-10-21-blind-collection'
LIMITATIONS = [
    'Recorded monotonic elapsed durations are not established uninterrupted calendar wall times.',
    'UTC starts and monotonic durations use different clocks; adding them does not prove end-time enclosure.',
    'The cause of clock disagreement is unproven; suspend and clock adjustment cannot be distinguished from these records.',
    'Blocking source-bound subprocess calls, unique attempts and contiguous native receipt spans support serial collection.',
    'No UTC timestamps or elapsed durations were edited, corrected or given a tolerance.',
    'This is a post-collection accounting amendment, outside the prelabel freeze; it changes no frozen model, candidate, policy, label or measurement.']


def collection_binding(collection, *, logical_path=None):
    collection = Path(collection).resolve()
    frozen._manifest(collection)
    return dict(path=logical_path if logical_path is not None else (str(collection.relative_to(ROOT)) if collection.is_relative_to(ROOT) else str(collection)),
        **{name.replace('.json','')+'_sha256':c.sha(collection/name) for name in
           ('manifest.json','protocol.json','commands.json','summary.json')})


def _candidate_timers(root, prefix, names):
    root = Path(root)
    frozen._hashes(root/'outer-timing',prefix)
    extras = frozen._inventory(root/'outer-timing')-set(prefix)
    records = {name for name in extras if name.endswith('.json')}
    c.require(extras == records|{name+'.sha256' for name in records}, 'Unpaired candidate timer artifacts')
    result = {}
    for name in sorted(records):
        row = c.unseal(root/'outer-timing'/name)
        candidate = row.get('candidate')
        c.require(row.get('schema') == 'isaforge-wrapper-outer-time-v1' and row.get('command') == 'measure' and
                  candidate in names and candidate not in result, 'Unique declared candidate measure timers required')
        c.require(isinstance(row.get('scope'),str) and row['scope'].startswith('Complete CLI operation through lock close'),
                  'Complete source-bound CLI timer scope required')
        result[candidate] = row
    c.require(list(result) == names, 'Complete frozen timer order required')
    return result


def clock_audits(prereg, roots, audits, collection, *, commit, release_path, logical_collection_path=None):
    """Authenticate all clocks without deriving actual UTC end instants."""
    prereg, collection = Path(prereg), Path(collection)
    cohort = c.unseal(prereg/'cohort.json')
    c.require(set(roots) == set(audits) == set(cohort['targets']), 'Complete native cohort required')
    binding = collection_binding(collection,logical_path=logical_collection_path)
    protocol, commands, summary = (c.unseal(collection/name) for name in ('protocol.json','commands.json','summary.json'))
    expected_order = {group:target['native_order'] for group,target in cohort['targets'].items()}
    c.require(protocol.get('schema') == 'isaforge-blind-collection-v1' and
              protocol.get('prereg_manifest_sha256') == c.sha(prereg/'manifest.json') and
              protocol.get('release_sha256') == c.sha(release_path) and protocol.get('prelabel_commit') == commit and
              protocol.get('source_sha256') == c.sha(ROOT/COLLECTOR) == cohort['source_bindings'].get(COLLECTOR) and
              protocol.get('order') == expected_order and
              all(type(protocol.get(key)) is int for key in ('workers','build_workers','attempts_per_candidate')) and protocol.get('workers') == 1 and
              protocol.get('build_workers') == 2 and protocol.get('attempts_per_candidate') == 1,
              'Frozen blocking collector source/protocol/order required')
    expected = [(group,name) for group,names in expected_order.items() for name in names]
    c.require([(row['workload_group'],row['candidate']) for row in commands] == expected,
              'Complete unique serial collector command order required')
    c.require(summary.get('historical_costs') == cohort['historical_costs'], 'Historical collection charges differ')
    release = frozen.check_release(release_path,prereg,commit,raws=roots)
    released = frozen._utc(release['released_at_utc'])
    by_identity = {(row['workload_group'],row['candidate']):row for row in commands}
    previous_recorded_start = released
    previous_parent_derived_end = None
    results = {}
    total_parent = total_ledger = 0.0
    success = failure = 0
    for group,target in cohort['targets'].items():
        root, audit = Path(roots[group]),audits[group]
        names = target['native_order']
        c.require(audit['pool_names'] == names and len(audit['public']) == target['pool_size'] == len(names),
                  'Audited/native declared pool differs')
        frozen.experiment.checked_outcomes(audit['public'],audit['outcomes'],audit)
        timer_rows = _candidate_timers(root,target['baseline_outer_files'],names)
        native_protocol = c.unseal(root/'evaluation-protocol.json')
        native_commands = c.unseal(root/'commands.json')
        c.require(native_commands[:len(native_protocol['baseline_receipts'])] == native_protocol['baseline_receipts'],
                  'Native baseline receipt prefix differs')
        cursor = len(native_protocol['baseline_receipts'])
        previous_cli_derived_end = max(frozen._utc(row['started_at_utc'])+timedelta(seconds=
            _number(row['elapsed_seconds'],'baseline monotonic elapsed seconds',positive=True))
            for name in target['baseline_outer_files'] if name.endswith('.json')
            for row in (c.unseal(root/'outer-timing'/name),))
        rows, outer_times = [], {}
        for name, public in zip(names,audit['public']):
            outer, parent = timer_rows[name],by_identity[group,name]
            ledger = c.unseal(root/'attempt-ledger'/(name+'.json'))
            parent_seconds = _number(parent.get('elapsed_seconds'),'collector monotonic elapsed seconds',positive=True)
            outer_seconds = _number(outer.get('elapsed_seconds'),'CLI monotonic elapsed seconds',positive=True)
            ledger_seconds = _number(ledger.get('elapsed_seconds'),'ledger monotonic elapsed seconds',positive=True)
            c.require(parent_seconds >= outer_seconds >= ledger_seconds, 'Monotonic duration scope ordering differs')
            c.require(ledger['status'] in ('success','failed') and outer.get('status') == parent.get('attempt_status') == ledger['status'] and
                      type(parent.get('returncode')) is int and (parent['returncode'] == 0) == (ledger['status'] == 'success') and
                      parent.get('ledger_seconds') == ledger_seconds and not parent.get('ledger_error'),
                      'Collector/CLI/native terminal status or duration differs')
            argv = parent.get('argv',[])
            c.require(isinstance(argv,list) and len(argv) == 8 and isinstance(argv[0],str) and bool(argv[0]) and
                      argv[1:] == ['-m','isaforge.blind_workload','measure','--root',target['original_root'],'--candidate',name],
                      'Collector candidate dispatch differs from frozen root/order')
            c.require((collection/group/(name+'.stdout.txt')).is_file() and
                      (collection/group/(name+'.stderr.txt')).is_file(), 'Complete collector output logs required')
            ps,os,ls = (frozen._utc(row.get('started_at_utc')) for row in (parent,outer,ledger))
            c.require(previous_recorded_start <= ps <= os <= ls and released < ps,
                      'Globally ordered recorded UTC starts after release required')
            previous_recorded_start = ls
            start,end = ledger['receipt_start'],ledger['receipt_end']
            c.require(type(start) is int and type(end) is int and start == cursor and start < end <= len(native_commands),
                      'Contiguous nonempty one-attempt native receipt spans required')
            receipts = native_commands[start:end]
            c.require(all(row['log'].startswith('measurements/'+name+'/') for row in receipts),
                      'Candidate receipt scope differs')
            native_seconds = sum(_number(row['elapsed_seconds'],'native command monotonic elapsed seconds',positive=True) for row in receipts)
            c.require(ledger_seconds >= native_seconds, 'Native command durations exceed charged ledger duration')
            cursor = end
            # These derived ends deliberately remain diagnostic. They combine clocks.
            pe,oe,le = (stamp+timedelta(seconds=seconds) for stamp,seconds in
                        ((ps,parent_seconds),(os,outer_seconds),(ls,ledger_seconds)))
            checks = dict(cli_encloses_ledger_derived_end=oe >= le,cli_derived_serial_order=os >= previous_cli_derived_end,
                collector_encloses_cli_derived_end=pe >= oe,
                collector_derived_serial_order=True if previous_parent_derived_end is None else ps >= previous_parent_derived_end)
            rows.append(dict(candidate=name,candidate_id=public['candidate_id'],
                collector_started_at_utc=parent['started_at_utc'],cli_started_at_utc=outer['started_at_utc'],
                ledger_started_at_utc=ledger['started_at_utc'],collector_monotonic_elapsed_seconds=parent_seconds,
                cli_monotonic_elapsed_seconds=outer_seconds,ledger_monotonic_elapsed_seconds=ledger_seconds,
                native_command_monotonic_elapsed_seconds=native_seconds,receipt_start=start,receipt_end=end,
                cli_minus_ledger_derived_end_seconds=(oe-le).total_seconds(),
                cli_derived_serial_gap_seconds=(os-previous_cli_derived_end).total_seconds(),
                collector_minus_cli_derived_end_seconds=(pe-oe).total_seconds(),
                collector_derived_serial_gap_seconds=None if previous_parent_derived_end is None else (ps-previous_parent_derived_end).total_seconds(),
                mixed_clock_diagnostics=checks))
            previous_cli_derived_end,previous_parent_derived_end = oe,pe
            outer_times[public['candidate_id']] = outer_seconds
            total_parent += parent_seconds; total_ledger += ledger_seconds
            success += ledger['status'] == 'success'; failure += ledger['status'] == 'failed'
        c.require(cursor == len(native_commands), 'Uncharged native receipts remain after final candidate')
        # Retain the exact frozen result. Only its documented mixed-clock checks
        # may fail after every independent integrity/ordering check above passes.
        try:
            strict_times = frozen.candidate_outer_times(root,audit,target['baseline_outer_files'])
        except ValueError as error:
            c.require(str(error) in ('Outer timestamps must enclose attempt ledger','Serial candidate timer order differs'),
                      'Unexpected frozen strict checker failure: '+str(error))
            strict = dict(passed=False,error_type=type(error).__name__,error=str(error))
            c.require(any(not all(row['mixed_clock_diagnostics'].values()) for row in rows),
                      'Strict failure lacks a preserved mixed-clock diagnostic')
        else:
            c.require(strict_times == outer_times, 'Frozen/adapter outer durations differ')
            strict = dict(passed=True,error_type=None,error=None)
        results[group] = dict(schema=CONTRACT,phase='post-collection accounting amendment',context_id=audit['context_id'],collection=binding,
            frozen_strict_checker=strict,rows=rows,outer_times=outer_times,
            mixed_clock_violation_counts={key:sum(not row['mixed_clock_diagnostics'][key] for row in rows)
                for key in rows[0]['mixed_clock_diagnostics']},
            independent_proof=dict(one_attempt_per_candidate=True,contiguous_scoped_native_receipts=True,
                source_bound_blocking_collector=True,recorded_utc_starts_globally_ordered=True,
                monotonic_duration_scopes_ordered=True),actual_calendar_wall_seconds=None,limitations=LIMITATIONS)
    c.require(summary.get('attempted_candidates') == len(commands) == success+failure and
              summary.get('successful') == success and summary.get('failed') == failure and
              summary.get('complete_subprocess_seconds') == total_parent and summary.get('ledger_seconds') == total_ledger,
              'Complete collector count/monotonic cost totals differ')
    return results,binding


def pack(prereg,targets,output,*,commit,release_path,collection=COLLECTION):
    prereg,output,release_path = map(lambda path:Path(path).resolve(),(prereg,output,release_path))
    targets = frozen._targets(targets); cohort = frozen.check_preregistration(prereg)
    c.require(set(targets) == set(cohort['targets']) and not output.exists() and not output.is_relative_to(prereg),
              'Fresh complete campaign outside preregistration required')
    frozen.check_git_checkpoint(prereg,commit)
    audits = {}
    for group,raw in targets.items():
        frozen.check_baseline(prereg,group,raw)
        audits[group] = frozen.workload().audit(raw)
        c.require(audits[group]['public'] == c.unseal(prereg/'targets'/group/'public.json'), 'Native/frozen public pool differs')
    clocks,binding = clock_audits(prereg,targets,audits,collection,commit=commit,release_path=release_path)
    output.mkdir(parents=True)
    for suffix in ('','.sha256'): shutil.copyfile(str(release_path)+suffix,str(output/'release.json')+suffix)
    reports = {}
    for group,raw in targets.items():
        folder = output/'targets'/group
        shutil.copytree(prereg/'targets'/group/'selection',folder/'selection')
        frozen.verify_refits(folder/'selection')
        report = frozen.experiment.evaluate(folder/'selection',audits[group]['outcomes'],native_audit=audits[group],outer_times=clocks[group]['outer_times'])
        c.require(report['trajectories'] == 180 and report['endpoints'] == 540, 'Complete twelve-policy report required')
        frozen.workload().pack(raw,folder/'native',prelabel_commit=None)
        for name,value in (('audit.json',audits[group]),('outer-times.json',clocks[group]['outer_times']),('clock-audit.json',clocks[group])):
            c.seal(folder/name,value)
        reports[group] = dict(charged_candidate_attempts=audits[group]['charged_candidate_attempts'],
            candidate_wall_seconds=audits[group]['candidate_wall_seconds'],trajectories=180,endpoints=540)
    c.seal(output/'provenance.json',dict(schema=frozen.SCHEMA+'-campaign',prelabel_commit=commit,
        prereg_manifest_sha256=c.sha(prereg/'manifest.json'),release_sha256=c.sha(output/'release.json'),
        source_bindings=cohort['source_bindings'],targets=reports,new_native_jobs=0,
        accounting_contract=CONTRACT,accounting_phase='post-collection accounting amendment',adapter_source_bindings={SOURCE:c.sha(ROOT/SOURCE)},collection=binding,
        clock_audits={group:c.sha(output/'targets'/group/'clock-audit.json') for group in reports},
        actual_calendar_wall_seconds=None,accounting_limitations=LIMITATIONS))
    frozen._seal_manifest(output)
    return reports


def replay(campaign,output,*,prereg,collection=COLLECTION):
    campaign,output,prereg = map(lambda path:Path(path).resolve(),(campaign,output,prereg))
    frozen._manifest(campaign); cohort = frozen.check_preregistration(prereg)
    provenance = c.unseal(campaign/'provenance.json')
    c.require(provenance.get('schema') == frozen.SCHEMA+'-campaign' and provenance.get('accounting_contract') == CONTRACT and
              provenance.get('accounting_phase') == 'post-collection accounting amendment' and
              provenance.get('adapter_source_bindings') == {SOURCE:c.sha(ROOT/SOURCE)} and
              provenance.get('collection') == collection_binding(collection,logical_path=provenance.get('collection',{}).get('path')) and
              provenance.get('source_bindings') == cohort['source_bindings'] and
              provenance.get('prereg_manifest_sha256') == c.sha(prereg/'manifest.json') and
              provenance.get('release_sha256') == c.sha(campaign/'release.json') and
              provenance.get('actual_calendar_wall_seconds') is None and provenance.get('accounting_limitations') == LIMITATIONS and
              set(provenance['targets']) == set(provenance.get('clock_audits',{})) == set(cohort['targets']) and not output.exists(),
              'Complete qualified accounting provenance and fresh replay output required')
    commit = provenance['prelabel_commit']; frozen.check_git_checkpoint(prereg,commit)
    raws,audits = {},{}
    for group in cohort['targets']:
        folder = campaign/'targets'/group; selection = folder/'selection'
        required,_ = frozen.required_selection(prereg/'targets'/group/'selection')
        c.require(frozen._inventory(selection) == required|frozen.FINAL_REPORTS, 'Exactly three sealed final reports required')
        for name in required:
            c.require(c.sha(selection/name) == c.sha(prereg/'targets'/group/'selection'/name), 'Changed prelabel model: '+name)
        raws[group] = output/group
        audits[group] = frozen.workload().replay(folder/'native',raws[group])
        c.require(audits[group] == c.unseal(folder/'audit.json'), 'Archived/native audit differs')
        frozen.check_baseline(prereg,group,raws[group])
    clocks,binding = clock_audits(prereg,raws,audits,collection,commit=commit,release_path=campaign/'release.json',
        logical_collection_path=provenance['collection']['path'])
    results = {}
    for group in cohort['targets']:
        folder = campaign/'targets'/group
        c.require(c.sha(folder/'clock-audit.json') == provenance['clock_audits'][group] and
                  c.unseal(folder/'clock-audit.json') == clocks[group] and
                  c.unseal(folder/'outer-times.json') == clocks[group]['outer_times'], 'Clock/duration audit replay differs')
        refits = frozen.verify_refits(folder/'selection')
        report = frozen.experiment.evaluate(folder/'selection',audits[group]['outcomes'],native_audit=audits[group],outer_times=clocks[group]['outer_times'],verify=True)
        c.require(report['trajectories'] == 180 and report['endpoints'] == 540 and report['new_native_jobs'] == 0,
                  'Complete hardware-free replay required')
        results[group] = dict(charged_candidate_attempts=audits[group]['charged_candidate_attempts'],
            candidate_wall_seconds=audits[group]['candidate_wall_seconds'],trajectories=180,endpoints=540)
        c.require(results[group] == provenance['targets'][group], 'Campaign attempt/monotonic duration totals differ')
        results[group].update(refits)
    return dict(targets=results,accounting_contract=CONTRACT,new_native_jobs=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('pack','replay'))
    parser.add_argument('--preregistration',type=Path,required=True)
    parser.add_argument('--collection',type=Path,default=COLLECTION)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--target',action='append',default=[])
    parser.add_argument('--commit');parser.add_argument('--release',type=Path);parser.add_argument('--campaign',type=Path)
    args = parser.parse_args(argv)
    if args.command == 'pack':
        targets = {}
        for value in args.target:
            group,sep,root = value.partition('=')
            c.require(sep and group not in targets,'Unique workload=root declarations required'); targets[group] = root
        c.require(args.release is not None,'Release required')
        result = pack(args.preregistration,targets,args.output,commit=args.commit,release_path=args.release,collection=args.collection)
    else:
        c.require(args.campaign is not None,'Campaign required')
        result = replay(args.campaign,args.output,prereg=args.preregistration,collection=args.collection)
    print(result)


if __name__ == '__main__': main()
