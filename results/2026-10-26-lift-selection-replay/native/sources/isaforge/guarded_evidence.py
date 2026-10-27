"""Portable read-only audit and archive for guarded development measurements.

The native evaluator owns preregistration and attempt ledgers. This module
authenticates those records, including interrupted and partially collected
pools, without starting native tools or inventing missing labels/costs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from pathlib import Path
import shutil
import subprocess

from . import campaign_evidence as prior, codesign as c
from .workload_experiment import validate_execution, verify_cache

SOURCE = 'isaforge/guarded_evidence.py'
SCHEMA = 'isaforge-guarded-evidence-v1'


def _path(root, name):
    c.require(isinstance(name,str) and name and not Path(name).is_absolute(), 'Relative evidence path required')
    path=(Path(root)/name).resolve()
    c.require(path.is_relative_to(Path(root).resolve()), 'Evidence path escapes root')
    return path


@contextmanager
def _read_lock(root):
    path=Path(root)/'.native.lock'
    if not path.exists():
        yield
        return
    with path.open('r') as stream:
        try:
            fcntl.flock(stream,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Native evaluator is active; audit after collection stops') from None
        yield


def _baseline(root,adapter,discovery,protocol,commands):
    """Recount frozen baseline evidence without hiding current target files."""
    prefix=protocol['baseline_receipts']
    c.require(prefix and commands[:len(prefix)]==prefix, 'Frozen baseline receipt prefix differs')
    c.require(all(r['failure'] is None and r['returncode']==r['expected_returncode'] for r in prefix),
              'Failed native command in frozen baseline prefix')
    c.require(all(not row['log'].startswith('measurements/') or row['log'].startswith('measurements/baseline/')
                  for row in prefix), 'Candidate receipt preceded protocol freeze')
    c.require(c.sha(root/'discovery/discovery.json')==protocol['discovery_sha256'], 'Frozen discovery changed')
    path=root/'measurements/baseline/measurement.json'
    c.require(c.sha(path)==protocol['baseline_sha256'], 'Frozen baseline changed')
    baseline=verify_cache(path.parent,path.name)
    c.require(baseline['name']=='baseline' and baseline['context_id']==protocol['context_id'], 'Baseline context differs')
    c.require(baseline['evaluation_id']==c.digest([protocol['context_id'],protocol['discovery_sha256'],'baseline']),
              'Baseline evaluation identity differs')
    raw=c.read(_path(root,discovery['profile'])); memory=adapter.validate_memory(raw)
    performance=validate_execution(raw)
    c.require(raw['markers']==2 and sum(raw['region_counts'].values())+1==performance['instructions'], 'Baseline profile counters differ')
    c.require(performance==baseline['performance']==discovery['baseline_performance'], 'Baseline performance differs')
    image=_path(root,discovery['baseline_image'])
    c.require(c.sha(image)==c.sha(image.parent.parent/'original/firmware.hex'), 'Marked baseline differs')
    c.require(c.sha(_path(root,baseline['firmware_image']))==baseline['firmware_sha256'], 'Baseline firmware changed')
    c.require(image.read_text()==adapter.memory_image(image.with_suffix('.bin').read_bytes()), 'Baseline RAM packing differs')
    adapter.memory_symbols(image)
    c.require(prior.validate_isa((image.parent/'disassembly.txt').read_text())['custom_static_sites']==0,
              'Baseline contains custom instructions')
    folder=path.parent
    sims=[_path(folder,p) for p in baseline['artifacts'] if p.endswith('/simulation/simulation.json')]
    plain=[_path(folder,p) for p in baseline['artifacts'] if p.endswith('/unobserved-control/simulation.json')]
    c.require(len(sims)==len(plain)==1, 'Baseline observer comparison missing')
    adapter.validate_memory(c.read(sims[0]))
    c.require(validate_execution(c.read(sims[0]))==validate_execution(c.read(plain[0]))==performance,
              'Observed/unobserved baseline differs')
    attempt=sims[0].parent.parent
    c.require(c.validate_netlist(c.read(attempt/'synthesis/ice40-netlist.json'))==baseline['resources'], 'Baseline netlist recount differs')
    routes=[dict(seed=seed,**c.timing_summary(c.read(attempt/f'synthesis/route-{seed}.json'),protocol['clock_mhz'])) for seed in (1,2,3)]
    c.require(routes==baseline['routes'] and all(r['internal_timing_pass'] and r['device_fits'] for r in routes),
              'Baseline route recount differs')
    c.require(baseline['speedup']==1.0, 'Baseline speedup differs')
    guards=verify_cache(root/'guard-controls','controls.json')
    c.require([(r['detected_kind'],r['raw']['first_violation']['address']) for r in guards['controls']]==
              [('stack-pointer',adapter.PARTITION['stack_floor']-4),('ram-write',adapter.PARTITION['program_limit'])],
              'Declared guard controls differ')
    for row in guards['controls']:
        observed=c.read(root/'guard-controls'/row['name']/'guard-simulation/simulation.json')
        c.require(observed==row['raw'] and observed['stack_initialized'] and observed['stack_violations']>0 and
                  observed['first_violation']['kind']==row['detected_kind'], 'Guard raw evidence differs')
    return baseline,memory


def _ledger(root,name,protocol,commands):
    """Authenticate one charged attempt, retaining nullable interrupted costs."""
    path=root/'attempt-ledger'/(name+'.json'); row=c.unseal(path)
    expected=c.digest([protocol['context_id'],protocol['discovery_sha256'],name])
    c.require(row.get('schema')=='isaforge-guarded-attempt-v1' and row['context_id']==protocol['context_id'] and row['name']==name and row['evaluation_id']==expected,
              'Attempt ledger identity differs')
    c.require(row['status'] in ('started','success','failed','interrupted'), 'Unknown attempt status')
    start=row['receipt_start']
    minimum=0 if name=='baseline' else len(protocol['baseline_receipts'])
    c.require(type(start) is int and minimum<=start<=len(commands), 'Invalid attempt receipt start')
    c.require(c.digest(commands[:start])==row['receipt_prefix_sha256'], 'Attempt receipt prefix differs')
    c.require(isinstance(row['started_at_utc'],str) and row['started_at_utc'], 'Attempt start time missing')
    base=root/'measurements'/name
    attempts=[p for p in base.glob('attempt-*') if p.is_dir()]
    c.require(len(attempts)<=1, 'Multiple native attempts for one charged candidate')
    if attempts:
        c.require(attempts[0].name=='attempt-000', 'Attempt number differs from one-attempt contract')
    terminal=row['status']!='started'
    end=row.get('receipt_end') if terminal else len(commands)
    c.require(type(end) is int and start<=end<=len(commands), 'Invalid attempt receipt end')
    c.require(all(r['log'].startswith('measurements/'+name+'/') for r in commands[start:end]),
              'Attempt receipt scope differs')
    elapsed=row.get('elapsed_seconds')
    if elapsed is not None: prior._seconds(elapsed)
    if row['status'] in ('success','failed'):
        c.require(elapsed is not None, 'Completed attempt wall time missing')
    native_seconds=sum(r['elapsed_seconds'] for r in commands[start:end])
    if elapsed is not None:
        c.require(elapsed+1e-6>=native_seconds, 'Attempt wall time is shorter than its native commands')
    if terminal:
        c.require(isinstance(row.get('artifacts'),dict), 'Terminal attempt artifact manifest required')
        actual={str(p.relative_to(base)):c.sha(p) for p in base.rglob('*') if p.is_file() and 'obj_dir' not in p.parts}
        c.require(actual==row['artifacts'], 'Attempt artifact membership/hash differs')
    if row['status']=='success':
        c.require((base/'measurement.json').exists() and c.sha(base/'measurement.json')==row['record_sha256'],
                  'Successful attempt record changed')
        c.require(not list(base.rglob('failure.json')), 'Success also contains failure evidence')
    else:
        c.require(not (base/'measurement.json').exists(), 'Unsuccessful ledger contains successful measurement')
        if terminal:
            c.require(isinstance(row.get('error'),str) and row['error'], 'Failure/interruption reason missing')
    return row,start,end


def _failure(row,base):
    raw_path=base/'attempt-000/simulation/simulation.json'
    malformed=False
    try:
        raw=c.read(raw_path) if raw_path.exists() else {}
        if not isinstance(raw,dict): raw={}; malformed=True
    except (ValueError,OSError):
        # A killed simulator can leave truncated JSON. It remains preserved
        # unknown evidence, rather than blocking archival or becoming a label.
        raw={}; malformed=True
    words=raw.get('words',[])
    complete=(len(words)==5 and words[0]==0x49534146 and raw.get('markers')==2 and raw.get('partial_report_bits')==0)
    reason='unknown'; invalid=False
    if raw.get('stack_violations',0)>0:
        reason='memory_contract_failure'; invalid=True
    elif complete and words[4]==0:
        reason='recorded_self_check_failure'; invalid=True
    elif raw.get('fault',0) or raw.get('trapped',False):
        reason='recorded_execution_failure'; invalid=True
    elif any(text in row.get('error','') for text in ('Less than 2 GiB free','No space left on device')):
        reason='infrastructure_unknown'
    return dict(name=row['name'],status=row['status'],classification=reason,
        correctness_verified=False if invalid else None,reference_censored=not invalid,
        elapsed_seconds=row.get('elapsed_seconds'),error=row.get('error'),
        incomplete_raw_simulation=malformed,
        native_command_seconds_lower_bound=None)


def _audit(root):
    from . import guarded_workload as native
    root=Path(root).resolve(); plan=c.unseal(root/'plan.json'); native.check_plan(plan)
    c.require(c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'], 'Invalid guarded context')
    for name,digest in plan['source_bindings'].items():
        c.require(c.sha(_path(c.ROOT,name))==digest, 'Bound source changed: '+name)
    for name,digest in plan['inputs'].items():
        c.require(c.sha(_path(root/'inputs',name))==digest, 'Bound input changed: '+name)
    protocol=c.unseal(root/'evaluation-protocol.json')
    c.require(protocol.get('schema')=='isaforge-guarded-measurement-protocol-v1' and
              protocol['context_id']==plan['context_id'] and protocol['attempts_per_candidate']==1,
              'Evaluation protocol context/attempt contract differs')
    c.require(protocol['clock_mhz']==12.0 and protocol['route_seeds']==[1,2,3], 'Unsupported measurement clock/routes')
    c.require(protocol['scope'] in ('engineering-validation','dataset-expansion'), 'Unknown guarded measurement scope')
    c.require(protocol['source_bindings']==plan['source_bindings'], 'Protocol source bindings differ')
    for name,digest in protocol['source_bindings'].items():
        c.require(c.sha(_path(c.ROOT,name))==digest, 'Frozen evaluation source changed: '+name)
    c.require(protocol['source_bindings'].get(SOURCE)==c.sha(c.ROOT/SOURCE), 'Evidence auditor source not frozen')
    discovery=native.authenticate_discovery(root); adapter=native.adapter_for_plan(plan)
    names=[r['name'] for r in discovery['pool']]
    c.require(names==protocol['pool_names'] and len(set(names))==len(names), 'Frozen guarded pool differs')
    commands=prior._receipts(root,allow_failures=True)
    prior._observations(root,adapter,commands)
    baseline,memory=_baseline(root,adapter,discovery,protocol,commands)
    ledgers=root/'attempt-ledger'
    baseline_ledger,_,baseline_end=_ledger(root,'baseline',protocol,commands)
    c.require(baseline_ledger['status']=='success' and baseline_end==len(protocol['baseline_receipts']),
              'Accepted baseline ledger must terminate frozen prefix')
    paths=[p for p in ledgers.glob('*.json') if p.stem!='baseline'] if ledgers.exists() else []
    c.require(all(p.stem in names for p in paths), 'Attempt ledger outside declared pool')
    c.require(type(protocol['maximum_candidate_attempts']) is int and protocol['maximum_candidate_attempts']==len(names)
              and len(paths)<=protocol['maximum_candidate_attempts'],
              'Candidate attempt budget exceeded')
    measured_dirs={p.name for p in (root/'measurements').iterdir() if p.is_dir()}-{'baseline'}
    c.require(measured_dirs<={p.stem for p in paths}, 'Native candidate directory has no charged ledger')
    calibration=prior._calibration(root)
    public=prior._public(root,plan,discovery,baseline,calibration)
    features={r['candidate_id']:r for r in public}
    successful=[]; failed=[]; ledgers_checked=[]; spans=[]; outcomes=[]
    mapping={r['name']:r for r in discovery['pool']}
    for name in names:
        if not (ledgers/(name+'.json')).exists(): continue
        row,start,end=_ledger(root,name,protocol,commands)
        spans.append((start,end,name)); ledgers_checked.append(row)
        if row['status']=='success':
            record=prior._audit_success(root,mapping[name],baseline,commands,adapter)
            successful.append(dict(name=name,candidate_id=mapping[name]['candidate_id'],speedup=record['speedup'],
                cycles=record['performance']['cycles'],area_delta_lut4=record['added_lut4'],
                timing_feasible=record['timing_feasible'],measurement_seconds=row['elapsed_seconds'],
                measurement_record_seconds=record['elapsed_seconds'],
                record_sha256=c.sha(root/'measurements'/name/'measurement.json')))
            observed=prior._outcome(features[mapping[name]['candidate_id']],record,baseline)
            observed['measurement_record_seconds']=record['elapsed_seconds']
            observed['measurement_seconds']=row['elapsed_seconds']
            outcomes.append(observed)
        else:
            failure=_failure(row,root/'measurements'/name)
            failure['native_command_seconds_lower_bound']=sum(r['elapsed_seconds'] for r in commands[start:end])
            failed.append(failure)
            if row.get('elapsed_seconds') is not None:
                outcomes.append(dict(features[mapping[name]['candidate_id']],status='failed',
                    measurement_seconds=row['elapsed_seconds'],error=row.get('error','Unfinished native attempt'),
                    failure_class=failure['classification'],reference_censored=failure['reference_censored']))
    cursor=len(protocol['baseline_receipts'])
    for start,end,name in sorted(spans):
        c.require(start==cursor, 'Attempt receipt spans overlap or leave uncharged commands')
        cursor=end
    c.require(cursor==len(commands), 'Post-freeze native receipts lack a charged attempt')
    complete=(len(ledgers_checked)==len(names) and all(r['status'] in ('success','failed') for r in ledgers_checked))
    unknown=[r['name'] for r in failed if r['reference_censored']]
    unattempted=[name for name in names if not (ledgers/(name+'.json')).exists()]
    unknown+=unattempted
    references=[]
    for cap in protocol['area_caps']:
        prior._seconds(cap)
        feasible=[r for r in successful if r['timing_feasible'] and r['area_delta_lut4']<=cap and r['speedup']>1]
        selected=min(feasible,key=lambda r:(-r['speedup'],r['area_delta_lut4'],r['name'])) if feasible else None
        references.append(dict(area_delta_lut4_cap=cap,best_verified_speedup=selected['speedup'] if selected else 1.0,
            selected_name=selected['name'] if selected else None,baseline_retained=selected is None,
            complete_pool_reference=complete and not unknown))
    elapsed=[r.get('elapsed_seconds') for r in ledgers_checked]
    return dict(schema=SCHEMA,scope=protocol['scope'],context_id=plan['context_id'],
        protocol_sha256=c.sha(root/'evaluation-protocol.json'),source_bindings=plan['source_bindings'],
        pool_names=names,public=public,outcomes=outcomes,charged_candidate_attempts=len(ledgers_checked),successful=successful,failed_or_interrupted=failed,
        unattempted=unattempted,attempt_collection_complete=complete,reference_censored_candidates=unknown,
        candidate_wall_seconds=sum(v for v in elapsed if v is not None),candidate_wall_seconds_complete=all(v is not None for v in elapsed),
        native_command_seconds=sum(r['elapsed_seconds'] for r in commands),native_command_count=len(commands),
        baseline_wall_seconds=baseline_ledger['elapsed_seconds'],baseline_record_seconds=baseline['elapsed_seconds'],
        baseline_memory=memory,best_verified_references=references,
        cost_note='Candidate/baseline wall and native command scopes overlap; unknown interrupted wall time is not fabricated.',
        new_native_jobs=0)


def audit(root):
    root=Path(root).resolve()
    with _read_lock(root): return _audit(root)


def pack(root,snapshot,*,prelabel_commit=None):
    from scripts.reproduce_codesign import pack_archive
    root,snapshot=Path(root).resolve(),Path(snapshot).resolve()
    c.require(not snapshot.exists(), 'Preserve prior guarded evidence snapshot')
    c.require(not snapshot.is_relative_to(root), 'Snapshot must be outside native experiment root')
    with _read_lock(root):
        result=_audit(root)
        if prelabel_commit is not None:
            c.require(len(prelabel_commit)==40 and all(ch in '0123456789abcdef' for ch in prelabel_commit), 'Exact prelabel commit required')
            relative=(root/'evaluation-protocol.json').relative_to(c.ROOT).as_posix()
            shown=subprocess.run(['git','show',prelabel_commit+':'+relative],cwd=c.ROOT,capture_output=True,check=False)
            import hashlib
            c.require(shown.returncode==0 and hashlib.sha256(shown.stdout).hexdigest()==result['protocol_sha256'],
                      'Prelabel commit protocol differs')
        snapshot.mkdir(parents=True)
        archive=pack_archive(root,snapshot/'raw.tar.gz')
    c.seal(snapshot/'archive-manifest.json',archive)
    c.seal(snapshot/'audit.json',result)
    c.seal(snapshot/'provenance.json',dict(prelabel_commit=prelabel_commit,
        protocol_path=str((root/'evaluation-protocol.json').relative_to(c.ROOT)) if root.is_relative_to(c.ROOT) else None,
        chronology='Git commit authenticated' if prelabel_commit else 'Receipt-prefix/source hashes only; external commit chronology not established'))
    sources=dict(result['source_bindings']); sources[SOURCE]=c.sha(c.ROOT/SOURCE)
    sources['scripts/reproduce_codesign.py']=c.sha(c.ROOT/'scripts/reproduce_codesign.py')
    sources['scripts/reproduce_prospective.py']=c.sha(c.ROOT/'scripts/reproduce_prospective.py')
    c.seal(snapshot/'source-manifest.json',sources)
    c.seal(snapshot/'manifest.json',{p.relative_to(snapshot).as_posix():c.sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()})
    return result


def replay(snapshot,output):
    from scripts.reproduce_codesign import restore_archive
    from scripts.reproduce_prospective import authenticate_files
    snapshot,output=Path(snapshot),Path(output)
    authenticate_files(snapshot,'manifest.json')
    for name,digest in c.unseal(snapshot/'source-manifest.json').items():
        c.require(c.sha(_path(c.ROOT,name))==digest, 'Frozen replay source changed: '+name)
    provenance=c.unseal(snapshot/'provenance.json')
    if provenance['prelabel_commit'] is not None:
        import hashlib
        commit=provenance['prelabel_commit']; relative=provenance['protocol_path']
        c.require(isinstance(commit,str) and len(commit)==40 and all(ch in '0123456789abcdef' for ch in commit)
                  and isinstance(relative,str) and not Path(relative).is_absolute() and '..' not in Path(relative).parts,
                  'Invalid archived prelabel Git provenance')
        shown=subprocess.run(['git','show',commit+':'+relative],cwd=c.ROOT,capture_output=True,check=False)
        c.require(shown.returncode==0 and hashlib.sha256(shown.stdout).hexdigest()==c.unseal(snapshot/'audit.json')['protocol_sha256'],
                  'Archived prelabel Git protocol differs')
    restore_archive(snapshot,c.unseal(snapshot/'archive-manifest.json'),output)
    result=audit(output)
    c.require(result==c.unseal(snapshot/'audit.json'), 'Guarded processor evidence replay differs')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('audit','pack','replay'))
    parser.add_argument('--root',type=Path); parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--output',type=Path); parser.add_argument('--prelabel-commit')
    args=parser.parse_args(argv)
    if args.command=='audit':
        c.require(args.root is not None,'--root required'); result=audit(args.root)
    elif args.command=='pack':
        c.require(args.root is not None and args.snapshot is not None,'--root and --snapshot required')
        result=pack(args.root,args.snapshot,prelabel_commit=args.prelabel_commit)
    else:
        c.require(args.snapshot is not None and args.output is not None,'--snapshot and --output required')
        result=replay(args.snapshot,args.output)
    print({k:result[k] for k in ('context_id','charged_candidate_attempts','attempt_collection_complete','new_native_jobs')})


if __name__=='__main__': main()
