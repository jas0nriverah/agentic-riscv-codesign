"""Bounded historical-only audit; no fitting, predictions, native jobs, or MD5 outcomes."""
from pathlib import Path
import collections
import copy
import hashlib
import json
import math
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PREREG = ROOT/'results/2026-10-26-md5-candidate-heldout-prereg'
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
READS = {}
REPORT = dict(schema='isaforge-md5-historical28-contract-audit-v1', status='running',
              authorization='Exact28 historical non-MD5 rows/contracts only; no fits, predictions, native jobs or MD5 candidate outcomes.',
              model_fits=0, model_predictions=0, native_jobs=0, tests_run=0, md5_candidate_outcomes_read=0,
              gates={}, rows=[], contexts=[])

def require(ok, message):
    if not ok:
        raise ValueError(message)

def rel(path):
    return str(Path(path).resolve().relative_to(ROOT))

def read(path, purpose, expected=None):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), 'Read escapes repository')
    data = path.read_bytes()
    hashed = hashlib.sha256(data).hexdigest()
    entry = READS.setdefault(rel(path), dict(sha256=hashed, purposes=[]))
    require(entry['sha256']==hashed, 'Input changed during audit: '+rel(path))
    if purpose not in entry['purposes']:
        entry['purposes'].append(purpose)
    require(expected is None or hashed==expected, 'Pinned SHA256 mismatch: '+rel(path))
    return data

def sealed(path, purpose, expected=None):
    data = read(path, purpose, expected)
    sidecar = read(str(path)+'.sha256', 'SHA256 sidecar').decode().strip()
    require(sidecar==hashlib.sha256(data).hexdigest(), 'Sidecar mismatch: '+rel(path))
    return json.loads(data)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def frame_allowlisted(data, ids):
    """Hash container; decode only exact-ID records, skipping excluded payload opaque."""
    text=data.decode(); depth=0; inside=False; escape=False; start=None
    allowed=[]; skipped=[]
    for i,ch in enumerate(text):
        if inside:
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch=='"': inside=False
        elif ch=='"': inside=True
        elif ch in '[{':
            if ch=='{' and depth==1: start=i
            depth+=1
        elif ch in ']}':
            depth-=1
            if ch=='}' and depth==1:
                frame=text[start:i+1]
                identity=re.findall(r'"candidate_id"\s*:\s*"([a-f0-9]{64})"',frame)
                require(len(identity)==1, 'Nonunique candidate_id in framed historical row')
                if identity[0] in ids: allowed.append(json.loads(frame))
                else: skipped.append(identity[0])
    require(depth==0 and not inside, 'Unbalanced history container')
    return allowed,skipped

def main():
    audit=sealed(PREREG/'independent-cohort-audit.json','cohort identity authority',
                 'c0c58c9f6e89bb12cc954cf54ffe84eb22b23b911f8dbc1ecb8842e6debc2f8b')
    contract=sealed(PREREG/'controller-preparation-v1/controller-contract.json','controller contract',
                    '0a4997edbdb9db2d8fd612dd6ccee9520830467c5421043a6df3d13d8ade672e')
    erratum=sealed(PREREG/'controller-preparation-v1-erratum-2026-10-26/erratum.json','scope/semantics erratum',
                   'f6a2f4b74a658a8916b15cdfbf4aee74e9e40a50a7bd5d08c171200ace7a68e7')
    roster=json.loads(read(PREREG/'roster.json','public roster/family exclusion',audit['roster']['file_sha256']))
    cohort=audit['cohort_amendment']; ids=cohort['retained_training_ids']
    require(len(ids)==len(set(ids))==28 and ids==contract['fitting_contract']['required_ids'], '28-ID authority mismatch')
    require(erratum['binds']['controller_contract_sha256']==READS[rel(PREREG/'controller-preparation-v1/controller-contract.json')]['sha256'], 'Erratum contract mismatch')
    for name,hashed in contract['identity_basis']['recipe_source_sha256'].items():
        read(ROOT/name,'controller-bound recipe source',hashed)
    for name in ['isaforge/campaign_evidence.py','isaforge/workload_audit.py',
                 'isaforge/workload_experiment.py','isaforge/workload_probe.py','isaforge/latency_features.py']:
        read(ROOT/name,'historical producer/validator source')
    history_path=next(name for name in audit['input_bindings'] if name.endswith('/history.json'))
    rows,skipped=frame_allowlisted(read(ROOT/history_path,'hash complete non-MD5 container; deserialize exact28 records only',audit['input_bindings'][history_path]),set(ids))
    read(str(ROOT/history_path)+'.sha256','history SHA256 sidecar',None)
    require(read(str(ROOT/history_path)+'.sha256','history SHA256 sidecar').decode().strip()==audit['input_bindings'][history_path], 'History sidecar mismatch')
    require([r['candidate_id'] for r in rows]==ids and skipped==[cohort['excluded_related_rows'][0]['candidate_id']], 'History cohort membership/order drift')
    protocol_path=ROOT/history_path.replace('history.json','protocol.json')
    protocol=sealed(protocol_path,'historical fit/public context contracts')
    require(protocol['artifacts']['history.json']==audit['input_bindings'][history_path], 'Historical protocol/history binding mismatch')
    groups=dict(collections.Counter(r['workload_group'] for r in rows))
    require(groups==cohort['retained_group_counts'] and len(groups)==7,'Historical group drift')
    identity=[{k:r[k] for k in ['candidate_id','benchmark','workload_group','formula']} for r in rows]
    require(digest(identity)==cohort['retained_public_identity_digest'],'Public identity projection changed')
    from isaforge import budgeted_selection as b, semantic_selection as s
    from isaforge import model, ranking, features, codesign as c
    from isaforge import workload_experiment as w, assembly_lowering as lowering
    from isaforge.latency_features import candidate_features
    from isaforge.speedup_corpus import family
    from isaforge.feasibility_selection import feasibility_label
    from isaforge.feasible_benefit import decision_utility
    roster_families={family(r['formula']) for r in roster}
    require(all('md5' not in r['workload_group'].lower() and 'md5' not in r['benchmark'].lower() and family(r['formula']) not in roster_families for r in rows),'Target/family leakage')
    require(all(r['candidate_family']==family(r['formula']) for r in rows),'Stored family mismatch')
    model.validate_training_rows(rows)
    require({r['measurement_source'] for r in rows}=={'synthesis_estimate'},'Measurement source mismatch')
    require(all(b.validate_outcome(r) for r in rows),'Invalid historical outcome contract')
    public=[{k:copy.deepcopy(r[k]) for k in b.PUBLIC_KEYS} for r in rows]
    base_matrix=model.feature_matrix(rows); structural=b.structural_matrix(rows); semantic=s.semantic_matrix(public)
    require(all(len(v)==35 and all(finite(x) for x in v) for v in base_matrix),'Invalid35-column features')
    require(all(len(v)==31 and all(finite(x) for x in v) for v in structural),'Invalid31-column structural features')
    require(all(len(v)==37 and all(finite(x) for x in v) for v in semantic),'Invalid37-column semantic features')
    REPORT['gates']['cohort_and_exclusions']='pass'
    REPORT['gates']['training_row_and_feature_contracts']='pass'
    REPORT['cohort']=dict(rows=28,groups=groups,group_count=7,context_count=len({r['benchmark'] for r in rows}),
        retained_ids=ids,retained_ids_codesign_digest=digest(ids),public_identity_digest=digest(identity),
        exact_training_rows_codesign_digest=digest(rows),skipped_record_ids_only=skipped,
        historical_md5_rows=0,roster_family_overlaps=0)
    ctx_cache={}
    for row in rows:
        benchmark=row['benchmark']
        if benchmark not in ctx_cache:
            ctx=protocol['contexts'][benchmark]; root=Path(ctx['baseline_provenance']['root'])
            require('md5' not in str(root).lower() and root.is_relative_to(ROOT/'generated'),'Unsafe historical root')
            plan=sealed(root/'plan.json','non-target native plan',ctx['baseline_provenance']['artifacts']['plan.json'])
            require(plan['context_id']==ctx['context_id']==benchmark.split(':',1)[1] and
                    digest({k:v for k,v in plan.items() if k!='context_id'})==plan['context_id'],'Native context digest differs')
            require(plan['configuration']['ram_bytes']==ctx['ram_bytes']==8192 and ctx['clock_mhz']==12.,'Hardware context mismatch')
            discovery=sealed(root/'discovery/discovery.json','public historical discovery',ctx['baseline_provenance']['artifacts']['discovery/discovery.json'])
            baseline=sealed(root/'measurements/baseline/measurement.json','non-target baseline',ctx['baseline_provenance']['artifacts']['measurements/baseline/measurement.json'])
            for name,hashed in ctx['hardware_inputs'].items():read(root/'inputs'/name,'historical hardware identity',hashed)
            for name,hashed in plan['source_bindings'].items():read(ROOT/name,'native plan source identity',hashed)
            image=root/discovery['baseline_image'];program_path=image.parent/'disassembly.txt'
            expected=discovery['artifacts'].get(str(program_path.relative_to(root/'discovery')))
            require(expected is not None,'Baseline disassembly not bound by discovery')
            program=lowering.read_program(read(program_path,'public baseline instructions',expected).decode())
            calibration_path=root/'inputs/latency-calibration.json'
            if calibration_path.exists():
                calibration=json.loads(read(calibration_path,'historical baseline-only latency calibration',plan['inputs']['latency-calibration.json']))
            else:
                # The original automatic baselines predate storing the shared calibration in inputs.
                calroot=ROOT/'results/2026-10-20-latency-calibration'
                cp=sealed(calroot/'plan.json','shared historical calibration hardware contract')
                calibration=sealed(calroot/'report.json','shared baseline-only calibration report')
                for name in ('picorv32.v','soc_top.v','pcpi_single.v'):
                    require(ctx['hardware_inputs'][name]==cp['inputs'][name],'Shared calibration hardware mismatch')
            ctx_cache[benchmark]=(ctx,root,plan,discovery,baseline,program,calibration)
            REPORT['contexts'].append(dict(benchmark=benchmark,root=rel(root),context_id=plan['context_id'],
                rows=sum(r['benchmark']==benchmark for r in rows),compiler_flags=ctx['compiler_flags'],
                ram_bytes=ctx['ram_bytes'],stack_bytes=ctx['stack_bytes'],hardware_context_id=ctx['hardware_context_id']))
        ctx,root,plan,discovery,baseline,program,calibration=ctx_cache[benchmark]
        matches=[v for v in discovery['pool'] if v['formula']==row['formula']]
        require(len(matches)==1,'Historical formula is not unique in declared pool')
        candidate=matches[0];base=root/'measurements'/candidate['name']
        require(candidate['candidate_id']==digest([plan['context_id'],row['formula']]),'Discovery identity mismatch')
        require(candidate['features']=={k:row[k] for k in features.FEATURE_COLUMNS},'Historical discovery features differ')
        derived=features.extract_features(dict(formula=row['formula'],size=row['size'],runs=row['runs'],places=row['places'],saved=row['saved'],savedPercent=row['saved_percent']))
        require(derived==candidate['features'],'Formula-derived features differ')
        latency=candidate_features(candidate,program,baseline['performance']['cycles'],baseline['performance']['instructions'],calibration)
        if 'region_custom_instructions' in row['latency_features']:latency['region_custom_instructions']=candidate['region_custom_instructions']
        require(latency==row['latency_features'],'Baseline-only latency features differ')
        record=sealed(base/'measurement.json','exact allowlisted candidate measurement contract')
        require(record['candidate_id']==candidate['candidate_id'] and record['context_id']==plan['context_id'] and
                record['formula']==row['formula'] and record['features']==candidate['features'],'Candidate record join differs')
        require(record['evaluation_id']==digest([plan['context_id'],READS[rel(root/'discovery/discovery.json')]['sha256'],candidate['name']]),'Evaluation identity mismatch')
        if row['candidate_id']!=candidate['candidate_id']:
            processor=dict(core=plan['core_commit'],isa=plan['configuration']['isa'],ram_bytes=plan['configuration']['ram_bytes'],clock_mhz=12.,pcpi_wait_cycles=1,
                compiler_sha256=plan['tools']['gcc']['sha256'],hardware={p:h for p,h in plan['source_bindings'].items() if p in ('hardware/soc_top.v','hardware/pcpi_single.v','hardware/soc_start.S','hardware/soc_link.ld')})
            inputs=dict(source_sha256=plan['inputs']['program.c'],harness_sha256=plan['inputs']['embench_firmware.c'],cpu_mhz_repetition_scale=1,warmup_repetitions=1,inputs='Unmodified upstream initialisation and self-check')
            sample=dict(workload=row['workload_group'],source_revision=plan['embench_commit'],input_id=digest(inputs),processor_id=digest(processor),formula=record['formula'],firmware_sha256=record['firmware_sha256'],measurement_context_id=plan['context_id'],implementation_sha256=digest(c.generate_rtl(record['formula'])))
            require(digest(sample)==row['candidate_id'],'Original automatic sample identity mismatch')
        require(record['performance']['upstream_self_check'] is True and record['controls']['stock_on_extension_identical'] is True and
                record['controls']['custom_on_baseline_traps'] is True and record['controls']['instruction_reduction_matches_profile'] is True,'Correctness controls incomplete')
        require(row['baseline_cycles']==baseline['performance']['cycles'] and row['candidate_cycles']==record['performance']['cycles'] and
                row['speedup']==record['speedup']==row['baseline_cycles']/row['candidate_cycles'],'Cycle/speedup arithmetic differs')
        require(row['area']==record['resources']['lut4_count'] and row['area_delta_lut4']==record['added_lut4']==row['area']-baseline['resources']['lut4_count'] and
                row['area_cap']==baseline['resources']['lut4_count']+128,'Integrated area arithmetic differs')
        require([r['seed'] for r in record['routes']]==[1,2,3] and record['frequency_mhz']==12.,'Native timing settings differ')
        require(row['routed_fmax_min_mhz']==min(r['limiting_internal_fmax_mhz'] for r in record['routes']) and
                row['device_fits']==all(r['device_fits'] for r in record['routes']) and
                row['timing_feasible']==record['timing_feasible']==all(r['device_fits'] and r['internal_timing_pass'] for r in record['routes']),'Hardware labels differ')
        for name,hashed in record['artifacts'].items():
            artifact=(base/name).resolve();require(artifact.is_relative_to(base.resolve()),'Candidate artifact path escape')
            read(artifact,'exact allowlisted candidate raw evidence hash',hashed)
        simulation_paths=[name for name in record['artifacts'] if name.endswith('/simulation/simulation.json')]
        require(len(simulation_paths)==1,'Exactly one native candidate simulation required')
        simulation_path=base/simulation_paths[0];attempt=simulation_path.parent.parent
        performance=w.validate_execution(json.loads(read(simulation_path,'raw authorized-candidate execution recount')),candidate)
        require(performance==record['performance'] and performance['benchmark_result_u32']==baseline['performance']['benchmark_result_u32'],'Raw candidate execution differs')
        stock=json.loads(read(attempt/'stock-on-extension/simulation.json','raw stock-on-extension control'))
        require(w.validate_execution(stock)==baseline['performance'],'Raw stock control differs')
        require(c.validate_netlist(json.loads(read(attempt/'synthesis/ice40-netlist.json','raw integrated netlist recount')))==record['resources'],'Raw netlist resource recount differs')
        routes=[dict(seed=seed,**c.timing_summary(json.loads(read(attempt/f'synthesis/route-{seed}.json','raw route summary recount')),12.)) for seed in (1,2,3)]
        require(routes==record['routes'],'Raw three-route recount differs')
        expected_seconds=row.get('measurement_record_seconds')
        if expected_seconds is None:
            require(row['measurement_seconds']==record['elapsed_seconds'],'Historical record duration differs')
            timer='measurement record elapsed'
        else:
            require(expected_seconds==record['elapsed_seconds'],'Inner measurement-record elapsed differs')
            ledger=sealed(root/'attempt-ledger'/(candidate['name']+'.json'),'exact allowlisted successful charged attempt')
            require(ledger['status']=='success' and ledger['elapsed_seconds']==row['measurement_seconds'] and ledger['record_sha256']==READS[rel(base/'measurement.json')]['sha256'],'Guarded charged duration/record differs')
            timer='guarded ledger elapsed; separate inner measurement record'
        require(finite(row['measurement_seconds']) and row['measurement_seconds']>0 and math.isfinite(math.log(row['measurement_seconds'])),'Invalid log duration')
        REPORT['rows'].append(dict(candidate_id=row['candidate_id'],discovery_candidate_id=candidate['candidate_id'],name=candidate['name'],benchmark=benchmark,
            formula=row['formula'],family=family(row['formula']),measurement_path=rel(base/'measurement.json'),measurement_sha256=READS[rel(base/'measurement.json')]['sha256'],
            row_codesign_digest=digest(row),timer_scope=timer,measurement_seconds=row['measurement_seconds'],record_seconds=record['elapsed_seconds'],
            outcome_contract='pass',raw_execution_controls_resources_routes='pass',features_and_latency='pass'))
    REPORT['gates']['per_candidate_native_record_and_raw_recounts']='pass'
    ordered,labels,qids,rank_groups=ranking.grouped_labels(rows)
    require(any(g['distinct_labels']>1 for g in rank_groups),'No unequal within-context rank pair')
    pairs=sum(sum(a['speedup']!=brow['speedup'] for i,a in enumerate(members) for brow in members[i+1:])
        for group in sorted({r['benchmark'] for r in rows}) for members in [[r for r in rows if r['benchmark']==group]])
    REPORT['ranking']=dict(groups=rank_groups,unequal_unordered_within_context_pairs=pairs,viable=True)
    REPORT['gates']['ranking_pair_viability']='pass'
    per_op=statistics.median(r['area_delta_lut4']/r['tree_op_count'] for r in rows)
    require(finite(per_op) and per_op>0,'Invalid historical area-per-op median')
    min_clock=min(r['routed_fmax_min_mhz'] for r in rows)
    logs=[math.log(r['measurement_seconds']) for r in rows]
    normalized=[(r['baseline_cycles']-r['candidate_cycles'])/b.occurrence_count(r) for r in rows]
    require(all(finite(v) for v in normalized+logs),'Invalid normalized benefit or log duration')
    caps={}
    for cap in [32,64,128]:
        y=[feasibility_label(r,cap) for r in rows];u=[decision_utility(r,cap) for r in rows]
        matrix=[v+[cap/(per_op*r['tree_op_count'])] for r,v in zip(rows,structural)]
        require(all(len(v)==32 and all(finite(x) for x in v) for v in matrix) and all(finite(x) for x in u),'Cap feature/target invalid')
        caps[str(cap)]=dict(class_counts=dict(collections.Counter(y)),utility_distinct_values=len(set(u)),matrix_codesign_digest=digest(matrix))
    REPORT['proxies']=dict(area_per_operation_median_lut4=per_op,minimum_historical_fmax_mhz=min_clock,
        measurement_seconds_sum=sum(r['measurement_seconds'] for r in rows),measurement_seconds_min=min(r['measurement_seconds'] for r in rows),
        measurement_seconds_max=max(r['measurement_seconds'] for r in rows),log_duration_mean=statistics.mean(logs),log_duration_population_std=statistics.pstdev(logs),
        log_duration_codesign_digest=digest(logs),normalized_benefit_codesign_digest=digest(normalized),
        positive_timing_rows=sum(r['routed_fmax_min_mhz']>=12 for r in rows),device_fit_rows=sum(r['device_fits'] for r in rows),
        feature_dimensions=dict(raw=35,structural_and_count_gp=31,semantic_and_fixed_joint=37,cap_conditioned=32),
        feature_matrix_digests=dict(raw=digest(base_matrix),structural=digest(structural),semantic=digest(semantic)),caps=caps)
    REPORT['gates']['area_duration_normalized_targets_and_class_inputs']='pass'
    REPORT['constant_fallback_source_check']=dict(status='pass_source_only_not_executed',
        classifier='isaforge/feasibility_selection.py:87-104: per-bootstrap constant0/1 if single class; consumes seed draw before branch',
        utility='isaforge/feasible_benefit.py:79-91: constant if complete replicated utility target constant',
        raw='isaforge/model.py:65-67: explicit constant fallback; no confidence claim',
        normalized='isaforge/budgeted_selection.py:115-126: explicit constant fallback')
    REPORT['cost_accounting']=dict(retained28_attempt_seconds=REPORT['proxies']['measurement_seconds_sum'],
        frozen_prelabel_historical_available=protocol['cost_provenance']['historical_training_available'],
        caveat='The retained28 sum is not total historical acquisition cost. Frozen aggregate includes45 successes and3 failures/48 attempts, excluded rows included. Failure records were not reopened. Candidate/ledger/setup/calibration/outer observers overlap and must not be summed. No uninterrupted calendar-time or new-pool cost claim.',
        excluded_historical_labels_used_as_model_input=False)
    REPORT['limitations']=[
        'No MD5 candidate outcomes, excluded-row numerical fields, other candidate outcome records, full corpus or raw archive opened.',
        'The original29-row file was hashed/framed; only exact28 records were JSON-deserialized. The excluded frame was inspected only for candidate_id.',
        'All raw artifact hashes for exact28 candidate records checked; raw candidate simulation, stock control, netlist and three route JSONs recounted using frozen pure validators.',
        'No compiler/simulator/synthesis/routing rerun; no complete historical chronological receipt or baseline raw-memory/correctness audit; baseline sealed contracts used.',
        'Calibration/feature equality and successful source contracts establish input admissibility, not predictive calibration, new-pool benefit, or feasibility.',
        'Timing/device labels all positive cannot validate negative-boundary classification or transfer.',
        'Future complete rebuilt models/predictions/proxy bindings and controller acceptance/release remain separate gates; no dispatch authorization.']
    REPORT['status']='passed_bounded_historical28_contract_audit'

if __name__=='__main__':
    try:
        main()
    except Exception as error:
        REPORT['status']='failed_stopped_no_repairs'
        REPORT['failure']=dict(type=type(error).__name__,message=str(error))
    REPORT['input_files']=READS
    path=OUT/'audit.json'
    path.write_text(json.dumps(REPORT,sort_keys=True,indent=2,allow_nan=False)+'\n')
    path.with_name(path.name+'.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'\n')
    print(json.dumps({k:REPORT.get(k) for k in ['status','failure','cohort','proxies','ranking']},sort_keys=True))
    if REPORT['status']!='passed_bounded_historical28_contract_audit':sys.exit(1)
