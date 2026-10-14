"""Input-only independent certificates/interpreter audit of the frozen1665 fit inputs."""
from pathlib import Path
import argparse,hashlib,importlib.util,itertools,json,math,sys,time

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def need(condition,message):
    if not condition:raise AssertionError(message)

def run(root,deps,output):
    sys.path[:0]=[str(deps),str(root)];import z3
    from isaforge import semantic_features_v7 as semantics
    spec=importlib.util.spec_from_file_location('v7_independent_test_helpers',root/'tests/test_semantic_features_v7_independent.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    old=root/'results/2026-10-14-v5';freeze=read(old/'freeze.json');entries={e['path']:e['sha256'] for e in freeze['files']}
    for name in ('development-features.json','split.json'):need(sha(old/name)==entries[name],'Frozen fitting input hash '+name)
    split=read(old/'split.json');rows=read(old/'development-features.json')['records'];indices=split['fit_indices']
    need(len(indices)==len(set(indices))==1665,'Exact original fitting indices')
    formulas=[rows[i]['formula'] for i in indices]
    sources={str(p.relative_to(root)):sha(p) for p in (root/'isaforge/semantic_features_v7.py',root/'isaforge/features.py',
                  root/'tests/test_semantic_features_v7_independent.py',Path(__file__))}
    output.mkdir(parents=True,exist_ok=True);queries=output/'independent-local-smt2';queries.mkdir(exist_ok=True)
    stats={m:{'rows':0,'changed':0,'accepted_steps':0,'statuses':{},'attempt_results':{}} for m in ('bit','affine','combined')}
    query_results={};records=[];pairs=list(itertools.product(helpers.BOUNDARY,repeat=2))
    import random
    rng=random.Random(2026101446);pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(32))
    began=time.perf_counter();cpu=time.process_time();comparisons=operand_checks=0
    for order,formula in enumerate(formulas):
        need(time.process_time()-cpu<900,'900CPU-second audit budget exhausted; incomplete audit')
        results=semantics.analyze_modes(formula)
        need(set(results)==set(stats),'All three independent/combined analyses required')
        need(results['combined']['features']=={**results['bit']['features'],**results['affine']['features']},'Exact feature nesting')
        original=helpers.independent_parse(formula);row={'fit_order':order,'original_index':indices[order],'formula':formula,'modes':{}}
        for mode,record in results.items():
            cell=stats[mode];cell['rows']+=1;metadata=record['metadata'];status=metadata['status']
            cell['statuses'][status]=cell['statuses'].get(status,0)+1
            changed=record['normalized_formula']!=record['original_formula'];cell['changed']+=changed
            need(tuple(record['features'])==semantics.FEATURE_NAMES_BY_MODE[mode],'Exact feature order')
            need(all(math.isfinite(v) and v>=0 for v in record['features'].values()),'Finite nonnegative formula-only features')
            need(metadata['original_zero_override'] is False,'No semantic-original zero override')
            references=[]
            def retain_query(number,step,solver,result):
                text='(set-logic QF_BV)\n(set-option :timeout 500)\n'+solver.to_smt2();key=hashlib.sha256(text.encode()).hexdigest()
                p=queries/(key+'.smt2')
                if p.exists():need(p.read_text()==text,'Query digest collision')
                else:p.write_text(text)
                need(result=='unsat','Independent local statement not proved')
                query_results[key]={'result':result,'smt2_sha256':sha(p),'timeout_ms':500}
                references.append({'step':number,'kind':step['kind'],'query_sha256':key})
            count=helpers.replay_certificate(record,z3,retain_query);cell['accepted_steps']+=count
            final=helpers.independent_parse(record['normalized_formula'])
            for x,y in pairs:
                need(helpers.recursive_word(original,x,y)==helpers.recursive_word(final,x,y),'Independent recursive arithmetic mismatch')
                comparisons+=1
            for operand in metadata['normalized_multiply_operands']:
                term=helpers.independent_parse(operand['formula']);low=operand['unsigned_minimum'];high=operand['unsigned_maximum']
                need(0<=low<=high<=helpers.WORD,'Valid operand range')
                need(high.bit_count()==operand['possible_one_bits'] and high.bit_length()==operand['unsigned_width'],'Operand support metadata')
                for x,y in pairs:
                    value=helpers.recursive_word(term,x,y)
                    need(low<=value<=high and value&low==low and value&(~high&helpers.WORD)==0,'Operand known bits/range inconsistent')
                    if operand['signed']:
                        signed=value-(1<<32) if value>=1<<31 else value;bits=operand['interpreted_width']
                        need(-(1<<(bits-1))<=signed<(1<<(bits-1)),'Signed interpreted width unsound')
                    operand_checks+=1
            for attempt in metadata['attempts']:
                verdict=attempt['proof']['result'];cell['attempt_results'][verdict]=cell['attempt_results'].get(verdict,0)+1
            row['modes'][mode]={'normalized_formula':record['normalized_formula'],'features':record['features'],
                'status':status,'independent_local_queries':references,'certificate':metadata['certificate'],
                'attempts':metadata['attempts']}
        records.append(row)
        if (order+1)%200==0:print(json.dumps({'rows':order+1,'elapsed_seconds':time.perf_counter()-began}),flush=True)
    # Re-execute public matrix API on every fitting formula with poisoned
    # nonformula fields. No target labels are opened or supplied here.
    poison=[{'formula':formula,'lut4_count':float('nan'),'stratum':'POISON','component':'POISON',
             'residual':float('inf'),'predicted_lut4':1e100,'upper_margin_lut4':-1} for formula in formulas]
    for mode in stats:
        matrix,repeated=semantics.feature_matrix(poison,mode=mode)
        expected=[[r['modes'][mode]['features'][name] for name in semantics.FEATURE_NAMES_BY_MODE[mode]] for r in records]
        need(matrix==expected,'All fitting inputs ignore poisoned metadata: '+mode)
        need([r['normalized_formula'] for r in repeated]==[r['modes'][mode]['normalized_formula'] for r in records],
             'Repeated analysis normal forms exact: '+mode)
    need(all(sha(root/name)==value for name,value in sources.items()),'Sources unchanged throughout actual audit')
    report={'status':'pass','scope':'All1665 original fitting inputs only; no target-label files, no calibration/test inputs, no fitting/hardware',
       'source_sha256':sources,'v5_freeze_sha256':sha(old/'freeze.json'),'input_features_sha256':sha(old/'development-features.json'),
       'split_sha256':sha(old/'split.json'),'fit_indices_sha256':digest(indices),'fit_formula_sha256':digest(formulas),
       'rows':len(formulas),'modes':stats,'independent_local_queries':query_results,'solver_version':z3.get_version_string(),
       'proof_method':'Independent32-bit local inequality miters + exact ordered path/context replay from original to final',
       'interpreter_method':'Separate tokenizer/parser and recursive Python integer word arithmetic; no production evaluation imports',
       'interpreter_input_pairs_per_mode_formula':len(pairs),'interpreter_comparisons':comparisons,'operand_known_bit_checks':operand_checks,
       'poisoned_metadata_formula_mode_rows_reexecuted':len(formulas)*len(stats),'poisoned_metadata_features_and_normal_forms_exact':True,
       'cpu_seconds':time.process_time()-cpu,'elapsed_seconds':time.perf_counter()-began,'cpu_budget_seconds':900,
       'limits':['Boundary/random interpreter checks supplement formal local proofs; no population or prediction-quality claim.',
                 'Certificates prove semantic equality, never original implementation area or mapping optimality.']}
    (output/'fitting-input-records.json').write_text(json.dumps(records,indent=2)+'\n')
    report['records_sha256']=sha(output/'fitting-input-records.json');(output/'fitting-input-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='independent_local_queries'},indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.root.resolve(),a.deps.resolve(),a.output.resolve())
