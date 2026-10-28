"""Authenticate baseline-only evidence before prospective instruction selection.

Freeze never opens target candidate measurements. Evaluation is an explicit,
separate operation after collection; neither operation starts native tools.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import codesign as c, partitioned_workload as partition, prospective_selection as selection
from .assembly_lowering import read_program, verify_lowering
from .latency_features import candidate_features
from .speedup_corpus import validate_isa
from .workload_audit import import_automatic
from .workload_experiment import validate_execution, verify_cache
from scripts.analyze_speedup_model import authenticated_calibration

SOURCE = 'isaforge/prospective_inputs.py'
DEFAULT_HISTORY = (c.ROOT/'generated/automatic-aha-mont64-2026-10-19',
                   c.ROOT/'generated/automatic-crc32-2026-10-20')


def reject_candidate_measurements(root):
    """Inspect names only; never read a candidate outcome to decide eligibility."""
    root=Path(root)
    baseline=root/'measurements/baseline/measurement.json'
    found=[p for p in (root/'measurements').rglob('measurement.json') if p!=baseline]
    c.require(not found, 'Prospective freeze refused: target candidate measurements already exist')


def authenticate_baseline(root):
    root=Path(root).resolve()
    reject_candidate_measurements(root)
    plan=c.unseal(root/'plan.json')
    c.require(c.digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'], 'Invalid target context')
    c.require(plan.get('memory_partition')==partition.PARTITION, 'Unchecked memory partition')
    c.require(plan['compiler_flags']==list(partition.compact.FLAGS), 'Unexpected target compiler flags')
    for name,digest in plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Target source changed: '+name)
    for name,digest in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name)==digest, 'Target input changed: '+name)
    commands=c.unseal(root/'commands.json')
    for command in commands:
        c.require(not command['log'].startswith('measurements/') or
                  command['log'].startswith('measurements/baseline/'), 'Candidate attempt exists before freeze')
        c.require(c.sha(root/command['log'])==command['log_sha256'], 'Native baseline log changed')
        c.require(command['returncode']==command['expected_returncode'] and command['failure'] is None,
                  'Failed preparation command')
        if command['argv'][0]==plan['tools']['gcc']['path']:
            flags=plan['compiler_flags']
            c.require(command['argv'][1:1+len(flags)]==flags, 'Compiler receipt flags differ')
    guards=verify_cache(root/'guard-controls','controls.json')
    c.require([r['detected_kind'] for r in guards['controls']]==['stack-pointer','ram-write'], 'Guard negative controls missing')
    for row in guards['controls']:
        raw=row['raw']
        c.require(raw['stack_initialized'] and raw['stack_violations']>0 and
                  raw['first_violation']['kind']==row['detected_kind'], 'Guard failed to detect violation')
    discovery=verify_cache(root/'discovery','discovery.json')
    c.require(discovery['context_id']==plan['context_id'], 'Target discovery context differs')
    baseline=verify_cache(root/'measurements/baseline','measurement.json')
    c.require(baseline['context_id']==plan['context_id'] and baseline['name']=='baseline', 'Baseline context differs')
    c.require(baseline['evaluation_id']==c.digest([plan['context_id'],c.sha(root/'discovery/discovery.json'),'baseline']), 'Baseline evaluation identity differs')
    profile=c.read(root/discovery['profile'])
    memory=partition.validate_memory(profile)
    performance=validate_execution(profile)
    c.require(profile['markers']==2 and sum(profile['region_counts'].values())+1==performance['instructions'], 'Profile counters differ')
    c.require(performance==baseline['performance']==discovery['baseline_performance'], 'Baseline performance differs')
    image=root/discovery['baseline_image']
    c.require(c.sha(image)==c.sha(image.parent.parent/'original/firmware.hex'), 'Marked baseline changed')
    c.require(c.sha(root/baseline['firmware_image'])==baseline['firmware_sha256'], 'Measured baseline firmware changed')
    partition.memory_symbols(image)
    c.require(validate_isa((image.parent/'disassembly.txt').read_text())['custom_static_sites']==0,
              'Baseline contains custom instructions')
    baseline_folder=root/'measurements/baseline'
    simulations=[baseline_folder/p for p in baseline['artifacts'] if p.endswith('/simulation/simulation.json')]
    controls=[baseline_folder/p for p in baseline['artifacts'] if p.endswith('/unobserved-control/simulation.json')]
    c.require(len(simulations)==len(controls)==1, 'Missing baseline observer comparison')
    c.require(validate_execution(c.read(controls[0]))==performance, 'Unobserved baseline differs')
    partition.validate_memory(c.read(simulations[0]))
    c.require(validate_execution(c.read(simulations[0]))==performance, 'Measured baseline simulation differs')
    attempt=simulations[0].parent.parent
    c.require(c.validate_netlist(c.read(attempt/'synthesis/ice40-netlist.json'))==baseline['resources'], 'Baseline resource recount differs')
    routes=[{'seed':seed,**c.timing_summary(c.read(attempt/f'synthesis/route-{seed}.json'),12.0)} for seed in (1,2,3)]
    c.require(routes==baseline['routes'] and all(r['internal_timing_pass'] and r['device_fits'] for r in routes), 'Baseline timing infeasible')
    c.require(baseline['speedup']==1.0, 'Baseline speedup differs')
    return plan,discovery,baseline,commands,memory


def context(root, plan, commands):
    root=Path(root).resolve()
    hardware={name:c.sha(root/'inputs'/name) for name in ('picorv32.v','soc_top.v','pcpi_single.v')}
    bindings={name:c.sha(root/name) for name in ('plan.json','commands.json','discovery/discovery.json',
                                               'measurements/baseline/measurement.json')}
    return dict(compiler_flags=plan.get('compiler_flags',plan['configuration'].get('compiler_flags')),
        ram_bytes=plan['configuration']['ram_bytes'],
        stack_bytes=plan['configuration'].get('stack_bytes',4096),hardware_context_id=c.digest(dict(hardware=hardware,linker=plan['inputs']['soc_link.ld'],
            compiler_flags=plan['compiler_flags'],configuration=plan['configuration'],
            memory_partition=plan.get('memory_partition',dict(stack_floor=4096,stack_bytes=4096)))),
        clock_mhz=12.0,hardware_inputs=hardware,context_id=plan['context_id'],
        linker_input_sha256=plan['inputs']['soc_link.ld'],memory_partition=plan.get('memory_partition',
            dict(ram_bytes=8192,stack_floor=4096,stack_bytes=4096)),
        pool_rule=plan.get('pool_rule','Top instruction-saving merit shortlist'),
        baseline_provenance=dict(root=str(root),artifacts=bindings,source_bindings=plan['source_bindings'],
            compiler_sha256=plan['tools']['gcc']['sha256'],input_bindings=plan['inputs'],
            setup_command_seconds=sum(r['elapsed_seconds'] for r in commands if not r['log'].startswith('measurements/')),
            baseline_command_seconds=sum(r['elapsed_seconds'] for r in commands if r['log'].startswith('measurements/baseline/')),
            all_command_seconds=sum(r['elapsed_seconds'] for r in commands),
            note='Command durations are distinct from overlapping candidate wall durations.'))


def freeze_workload(target_root, output, *, history_roots=DEFAULT_HISTORY,
                    analysis_snapshot=c.ROOT/'results/2026-10-20-model-analysis'):
    """Explicitly invoked by the coordinator only after baseline acceptance."""
    target_root=Path(target_root).resolve(); output=Path(output)
    c.require(not output.exists(), 'Use a fresh prospective output')
    plan,discovery,baseline,commands,memory=authenticate_baseline(target_root)
    calibration_root=c.ROOT/'results/2026-10-20-latency-calibration'
    calibration,calibration_plan=authenticated_calibration(calibration_root)
    c.require(c.read(target_root/'inputs/latency-calibration.json')==calibration, 'Target calibration projection differs')
    for name in ('picorv32.v','soc_top.v','pcpi_single.v'):
        c.require(c.sha(target_root/'inputs'/name)==calibration_plan['inputs'][name], 'Calibration hardware mismatch: '+name)
    image=target_root/discovery['baseline_image']
    program=read_program((image.parent/'disassembly.txt').read_text())
    from . import assembly_lowering as lowering
    marked,sites=lowering.mark_assembly((image.parent.parent/'program.s').read_text())
    c.require(marked==(image.parent.parent/'marked.S').read_text(), 'Marked assembly differs')
    site_map=lowering.map_sites(sites,(image.parent/'symbols.txt').read_text())
    regenerated=partition.extract_pool(program,c.read(target_root/discovery['profile']),site_map,plan['pool_size'],calibration)
    c.require(len(regenerated['pool'])==len(discovery['pool']), 'Re-extracted pool size differs')
    for derived,candidate in zip(regenerated['pool'],discovery['pool']):
        c.require(all(candidate[k]==v for k,v in derived.items()), 'Re-extracted candidate differs')
        c.require(lowering.lower(marked,candidate)==(target_root/candidate['assembly']).read_text(), 'Lowered assembly differs')
    workload='embench-'+plan['workload']; benchmark=workload+':'+plan['context_id']
    public=[]
    for candidate in discovery['pool']:
        c.require(candidate['candidate_id']==c.digest([plan['context_id'],candidate['formula']]), 'Discovery candidate identity differs')
        c.require(verify_lowering(candidate,program,discovery['block_starts'])==candidate['lowering_check'], 'Candidate legality differs')
        public.append(dict(candidate_id=candidate['candidate_id'],benchmark=benchmark,formula=candidate['formula'],
            **candidate['features'],latency_features=candidate_features(candidate,program,
                baseline['performance']['cycles'],baseline['performance']['instructions'],calibration)))
    c.require(len(public)==plan['pool_size'], 'Incomplete target pool')
    history=[]; contexts={benchmark:context(target_root,plan,commands)}
    for root in history_roots:
        root=Path(root).resolve(); imported=import_automatic(root); history.extend(imported['rows'])
        historical_plan=c.unseal(root/'plan.json')
        contexts[imported['rows'][0]['benchmark']]=context(root,historical_plan,c.unseal(root/'commands.json'))
    snapshot=Path(analysis_snapshot)
    analysis_plan=c.unseal(snapshot/'protocol.json')
    for name,digest in analysis_plan['source_bindings'].items():
        c.require(c.sha(c.ROOT/name)==digest, 'Historical analysis source changed: '+name)
    for name,key in (('calibration.json','calibration_sha256'),('baseline-inputs.json','baseline_inputs_sha256')):
        c.require(c.sha(snapshot/name)==analysis_plan[key], 'Historical analysis input changed: '+name)
    c.require(c.unseal(snapshot/'calibration.json')==calibration, 'Historical calibration projection differs')
    features_path=snapshot/'public-predictions.json'
    c.require(c.sha(features_path)==analysis_plan['predictions_sha256'], 'Historical execution features changed')
    c.require(analysis_plan['calibration_id']==calibration['context_id'], 'Historical calibration differs')
    for name,digest in analysis_plan['baseline_bindings'].items():
        c.require(c.sha(snapshot/name)==digest, 'Historical baseline projection changed')
    features=c.unseal(features_path)
    contexts[benchmark]['baseline_provenance'].update(memory_check=memory,
        guard_controls_sha256=c.sha(target_root/'guard-controls/controls.json'),
        calibration_report_sha256=c.sha(calibration_root/'report.json'),
        calibration_plan_sha256=c.sha(calibration_root/'plan.json'),
        analysis_protocol_sha256=c.sha(snapshot/'protocol.json'),historical_features_sha256=c.sha(features_path),
        prospective_input_source_sha256=c.sha(c.ROOT/SOURCE),
        context_transfer='Target -Os/4352-byte stack floor differs explicitly from historical -O2/4096-byte floor.')
    # Recheck names immediately before writing frozen predictions.
    reject_candidate_measurements(target_root)
    return selection.freeze(history,features,public,contexts,output,target_workload=workload,
        calibration_cost_seconds=calibration['native_command_seconds'],
        area_cap=baseline['resources']['lut4_count']+128,budgets=tuple(range(1,min(3,len(public))+1)))


def evaluate_workload(root, target_root, *, verify=False):
    root=Path(root); target_root=Path(target_root).resolve()
    protocol=c.unseal(root/'protocol.json'); public=c.unseal(root/'public.json')
    c.require(c.sha(c.ROOT/SOURCE)==protocol['contexts'][public[0]['benchmark']]['baseline_provenance']['prospective_input_source_sha256'], 'Input adapter source changed')
    partition.audit(target_root)
    plan=c.unseal(target_root/'plan.json')
    benchmark='embench-'+plan['workload']+':'+plan['context_id']
    c.require({r['benchmark'] for r in public}=={benchmark}, 'Target context changed')
    provenance=protocol['contexts'][benchmark]['baseline_provenance']
    # commands.json grows during collection; the baseline/discovery contracts do not.
    for name,digest in provenance['artifacts'].items():
        if name!='commands.json': c.require(c.sha(target_root/name)==digest, 'Frozen baseline changed: '+name)
    discovery=c.unseal(target_root/'discovery/discovery.json'); baseline=c.unseal(target_root/'measurements/baseline/measurement.json')
    mapping={r['candidate_id']:r for r in public}; outcomes=[]
    for candidate in discovery['pool']:
        record=c.unseal(target_root/'measurements'/candidate['name']/'measurement.json')
        row=mapping[candidate['candidate_id']]
        outcomes.append({**row,'speedup':record['speedup'],'area':record['resources']['lut4_count'],
            'area_cap':baseline['resources']['lut4_count']+128,'timing_feasible':record['timing_feasible'],
            'measurement_source':'synthesis_estimate','measurement_seconds':record['elapsed_seconds'],
            'baseline_cycles':baseline['performance']['cycles'],'candidate_cycles':record['performance']['cycles'],
            'baseline_period_ns':1000/12,'candidate_period_ns':1000/12})
    return selection.evaluate(root,outcomes,area_cap=protocol['area_cap'],verify=verify)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('freeze','evaluate','replay'))
    parser.add_argument('--target-root',type=Path,required=True); parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--history-root',type=Path,action='append'); parser.add_argument('--analysis-snapshot',type=Path,default=c.ROOT/'results/2026-10-20-model-analysis')
    args=parser.parse_args(argv)
    if args.command=='freeze':
        result=freeze_workload(args.target_root,args.root,history_roots=args.history_root or DEFAULT_HISTORY,analysis_snapshot=args.analysis_snapshot)
        print({'target_labels_read':0,'fit_rows':result['historical_fit_rows']})
    else:
        result=evaluate_workload(args.root,args.target_root,verify=args.command=='replay')
        print({'new_native_jobs':0,'runs':len(result['runs'])})


if __name__=='__main__': main()
