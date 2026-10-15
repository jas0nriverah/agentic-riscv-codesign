#!/usr/bin/env python3
"""Portable V10d evidence audit; no native tools, models, or collector imports.

Formal identity replay shares the separately reviewed RTL algebra checker and
is explicitly not an independent universal proof implementation. Concrete word
JSON evaluation and mapped hardware/resource replay are independent checks.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import re
import statistics
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import audit_v10_hardware as independent
import prove_v10_rtl_algebra as algebra

PREFIX = 'generated/v10d-csd-hardware/'
ARMS = ('original', 'csd')
FRONTEND_COMMANDS = ['hierarchy -check -top candidate', 'proc', 'opt_clean', 'check -assert']
V10C_PREPARATION_SHA = '366deab82a91f674ddf0bbdd53f583740a9bea4af42eae760caac6643a7cf121'
V10C_NATIVE_COMPLETION_SHA = '32587bef93c12d2cac0411afba0a92abf0a11bbc285023be89899f46f123e374'
need = independent.need
sha = independent.sha


def loads(data):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key');result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def read(path): return loads(Path(path).read_bytes())


def stamp(value):
    need(type(value) is str, 'UTC timestamp string required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(result.tzinfo is not None and result.utcoffset() == timedelta(0), 'UTC-aware chronology required')
    return result


def execution(value):
    need(set(value) == {'returncode', 'timed_out', 'elapsed_seconds'}
        and (type(value['returncode']) is int or value['returncode'] is None)
        and type(value['timed_out']) is bool and independent.elapsed(value['elapsed_seconds']), 'Strict native execution record required')
    return value['returncode'] == 0 and value['timed_out'] is False


def frontend_script(base, attempt, pair_id, arm):
    folder = base/PREFIX/attempt/'frontend'/pair_id.split(':')[1]/arm
    return '\n'.join([f'read_verilog {independent.quoted(folder/"candidate.v")}', *FRONTEND_COMMANDS,
        f'write_json {independent.quoted(folder/"word.json")}'])+'\n'


def measurement_script(base, attempt, stem, samples):
    # Reuse the prior independent script specification, never collector code.
    old = str(base/'generated/v10-csd-hardware')
    return independent.arm_script(base, attempt, stem, samples).replace(old, str(base/'generated/v10d-csd-hardware'))


def word_samples(data, samples):
    """Concrete unsigned evaluation of actual wires; no polynomial evaluation.

    The reviewed checker validates supported word-cell semantics first. This
    evaluator supplies a complementary sample check, not another formal proof.
    """
    algebra.Circuit(data, width=32)
    module = data['modules']['candidate'];cells = list(module['cells'].values())
    known = set(module['ports']['in0']['bits']+module['ports']['in1']['bits']) | {'0', '1'}
    schedule = []
    while cells:
        ready = [cell for cell in cells if all(bit in known for port,bits in cell['connections'].items() if port != 'Y' for bit in bits)]
        need(ready, 'Cyclic/undriven word graph');schedule.extend(ready)
        known.update(bit for cell in ready for bit in cell['connections']['Y']);cells = [cell for cell in cells if cell not in ready]
    result = []
    for a, b in samples:
        values = {'0': 0, '1': 1}
        for name, value in [('in0', a), ('in1', b)]:
            values.update({bit: (value >> i) & 1 for i,bit in enumerate(module['ports'][name]['bits'])})
        def word(bits): return sum(values[bit] << i for i,bit in enumerate(bits))
        for cell in schedule:
            c = cell['connections'];left, right = word(c['A']), word(c['B']);kind = cell['type']
            if kind == '$add': value = left+right
            elif kind == '$sub': value = left-right
            elif kind == '$mul': value = left*right
            elif kind == '$and': value = left & right
            elif kind == '$shl': value = 0 if right >= 32 else left << right
            else:
                need(kind == '$mux', 'Unsupported concrete word operation');value = right if word(c['S']) else left
            values.update({bit: (value >> i) & 1 for i,bit in enumerate(c['Y'])})
        result.append(word(module['ports']['result']['bits']))
    return result


def archive_content(stage, done, attempt):
    raw_path = stage/'raw-evidence.json';raw = read(raw_path)
    need(raw.get('schema') == 'isaforge-v10d-raw-evidence-v1' and raw['attempt'] == attempt and raw['archive'] == 'raw-evidence.zip'
        and raw['completion_sha256'] == sha((stage/'completion.json').read_bytes())
        and raw['archive_sha256'] == sha((stage/'raw-evidence.zip').read_bytes()), 'Archive/completion identity differs')
    index = {entry['path']: entry for entry in raw['files']};need(len(index) == len(raw['files']), 'Duplicate raw binding')
    content = {};prefix = PREFIX+attempt+'/'
    with zipfile.ZipFile(stage/'raw-evidence.zip') as archive:
        need(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(index), 'Archive coverage differs')
        for info in archive.infolist():
            path = PurePosixPath(info.filename);entry = index[info.filename]
            need(info.filename.startswith(prefix) and not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename
                and str(path) == info.filename and not info.is_dir() and ((info.external_attr >> 16) & 0o170000) in (0,0o100000), 'Unsafe archive member')
            data = archive.read(info)
            need(type(entry['size']) is int and entry['size'] >= 0 and len(data) == entry['size'] and sha(data) == entry['sha256'], 'Archived member changed')
            content[info.filename[len(prefix):]] = data
    return raw, content


def verify_frontend(pair, arm, record, content, tools, base, attempt):
    stem = 'frontend/'+pair['pair_id'].split(':')[1]+'/'+arm+'/'
    need(record.get('schema') == 'isaforge-v10d-frontend-v1' and record['pair_id'] == pair['pair_id'] and record['arm'] == arm,
        'Frontend arm identity differs')
    need(record['candidate_rtl_sha256'] == pair['arms'][arm]['rtl']['sha256']
        and record['yosys'] == tools['executables']['yosys'], 'Frontend RTL/tool identity differs')
    for name,key in [('candidate.v','candidate_rtl_sha256'),('frontend.ys','script_sha256'),('frontend.log','log_sha256')]:
        need(sha(content[stem+name]) == record[key], 'Raw frontend digest differs')
    need(loads(content[stem+'frontend.json']) == record, 'Archived frontend record differs')
    native_success = execution(record['execution'])
    need(type(record['success']) is bool and stamp(record['completed_at_utc']) >= stamp(record['started_at_utc']), 'Strict frontend chronology required')
    need(content[stem+'frontend.ys'].decode() == frontend_script(base,attempt,pair['pair_id'],arm), 'Actual word frontend script differs')
    path = base/PREFIX/attempt/stem/'candidate.v';log = content[stem+'frontend.log'].decode()
    need(record['command'] == [tools['executables']['yosys']['path'],'-s',str(path.with_name('frontend.ys'))], 'Frontend command differs')
    if not record['success']:
        need(record['status'] in ('timeout','failed') and (not native_success or record['error'] is not None), 'Failed frontend has no execution/parse failure')
        if record['word_json_sha256'] is not None:
            need(sha(content[stem+'word.json']) == record['word_json_sha256'], 'Partial frontend JSON digest differs')
        return None, 0
    need(native_success and record['status'] == 'complete' and record['error'] is None
        and sha(content[stem+'word.json']) == record['word_json_sha256'], 'Successful frontend evidence differs')
    need(re.findall(r"Parsing Verilog input from [`']([^']+)'",log) == [str(path)], 'Frontend read a different or additional RTL source')
    data = loads(content[stem+'word.json'])
    need(data.get('creator') == tools['executables']['yosys']['version']
        and data['modules']['candidate'].get('attributes',{}).get('src','').startswith(str(path)+':'), 'Parsed JSON creator/source lineage differs')
    samples = independent.vectors();expected = independent.expected_values(pair['constant_u32'],pair['context'],samples)
    need(word_samples(data,samples) == expected, 'Word frontend JSON disagrees with fixed original unsigned oracle')
    return data, len(samples)


def verify_measurement(pair, arm, metric, content, tools, base, attempt, gate, gate_hash):
    stem = 'circuits/'+pair['pair_id'].split(':')[1]+'/'+arm+'/'
    need(metric['source_candidate_id'] == pair['source_candidate_id'] and metric['formula'] == pair['arms'][arm]['formula']
        and metric['original_formula'] == pair['formula'] and metric['measurement_source'] == 'fresh-rtl-synthesis'
        and metric['actual_rtl_verified'] is True and metric['mapped_netlist_verified'] is True
        and type(metric['vectors_per_arm']) is int and metric['vectors_per_arm'] == 2148
        and type(metric['random_seed']) is int and metric['random_seed'] == independent.SEED and metric['new_fit'] is False,
        'Fresh arm formula/seed/verification identity differs')
    need(independent.integer(metric['lut4_count']) and independent.integer(metric['carry_count'])
        and set(metric['ice40_cell_types']) <= {'SB_LUT4','SB_CARRY'}
        and all(independent.integer(value) and value > 0 for value in metric['ice40_cell_types'].values()), 'Strict arm resource counts required')
    for name,key in [('candidate.v','rtl_sha256'),('ice40.ys','script_sha256'),('ice40.log','log_sha256'),('ice40-netlist.json','netlist_sha256'),('vectors.txt','vectors_sha256'),('observations.txt','observations_sha256')]:
        need(sha(content[stem+name]) == metric[key], 'Raw arm digest differs')
    need(metric['rtl_sha256'] == pair['arms'][arm]['rtl']['sha256'], 'Measured RTL differs from sealed arm')
    start = loads(content[stem+'measurement-start.json'])
    need(content[stem+'measurement-start.json'] == content['measurement-start/'+pair['pair_id'].split(':')[1]+'/'+arm+'.json'], 'Canonical arm start differs from prelaunch event')
    need(start['pair_id'] == pair['pair_id'] and start['arm'] == arm and start['measurement_gate_sha256'] == gate_hash
        and stamp(start['started_at_utc']) >= gate and stamp(metric['measured_at_utc']) >= stamp(start['started_at_utc']),
        'Arm work started before full proof gate or completion precedes start')
    samples = independent.vectors();expected = independent.expected_values(pair['constant_u32'],pair['context'],samples)
    need(content[stem+'ice40.ys'].decode() == measurement_script(base,attempt,stem,samples), 'Actual synthesis script differs from fixed flow')
    need(content[stem+'vectors.txt'].decode() == ''.join(f'{a:08x} {b:08x} {y:08x}\n' for (a,b),y in zip(samples,expected)), 'Saved vectors/oracle differ')
    need(content[stem+'observations.txt'].decode() == ''.join(f'{y:08x} {y:08x}\n' for y in expected), 'Saved sampled outputs differ')
    log = content[stem+'ice40.log'].decode();observed = re.findall(r"Eval result: \\result = ([^\n]+)\.",log)
    need(len(observed) == log.count('Eval result:') and all(re.fullmatch(r"32'[01]{32}|[0-9]+",value) for value in observed), 'Malformed/undefined raw RTL outputs')
    need([int(value.split("'")[1],2) if "'" in value else int(value) for value in observed] == expected, 'Raw RTL log disagrees with unsigned oracle')
    counts = independent.verify_mapped(loads(content[stem+'ice40-netlist.json']),samples,expected)
    need(counts == metric['ice40_cell_types'] and counts.get('SB_LUT4',0) == metric['lut4_count']
        and counts.get('SB_CARRY',0) == metric['carry_count'] and execution(metric['execution']), 'Independent resource/execution replay differs')
    independent.verify_provenance(log,metric,tools,base/PREFIX/attempt/stem/'candidate.v')
    return len(samples)*2


def distribution(values):
    return {'count':len(values),'mean':statistics.fmean(values),'median':statistics.median(values),
        'minimum':min(values),'maximum':max(values),'lower':sum(value < 0 for value in values),
        'equal':values.count(0),'higher':sum(value > 0 for value in values)}


def paired_results(pairs, metrics, prior, tools):
    index = {(row['pair_id'],row['arm']):row for row in metrics}
    need(len(index) == len(metrics) == 64, 'Exactly64 unique fresh arm records required')
    old = {row['formula']:row for row in prior};need(len(old) == len(prior), 'Duplicate prior original formula')
    output = []
    for pair in pairs:
        a,b = (index[pair['pair_id'],arm] for arm in ARMS);history = old[pair['formula']]
        need(independent.integer(history['ice40_lut4_count']) and independent.integer(history['ice40_carry_count']), 'Strict prior resource counts required')
        output.append({'pair_id':pair['pair_id'],'formula':pair['formula'],'constant_u32':pair['constant_u32'],'context':pair['context'],
            'original_lut4':a['lut4_count'],'csd_lut4':b['lut4_count'],'csd_minus_original_lut4':b['lut4_count']-a['lut4_count'],
            'original_carry':a['carry_count'],'csd_carry':b['carry_count'],'csd_minus_original_carry':b['carry_count']-a['carry_count'],
            'prior_v9_original_lut4':history['ice40_lut4_count'],'prior_v9_original_carry':history['ice40_carry_count'],
            'fresh_minus_prior_original_lut4':a['lut4_count']-history['ice40_lut4_count'],
            'fresh_minus_prior_original_carry':a['carry_count']-history['ice40_carry_count'],
            'prior_original_rtl_equal':history['rtl_sha256'] == pair['arms']['original']['rtl']['sha256'],
            'prior_original_tool_equal':history['tool_sha256'] == tools['executables']['yosys']['sha256']})
    def groups(key, field):
        return {str(value):distribution([row[field] for row in output if row[key] == value]) for value in sorted({row[key] for row in output})}
    return output, {'lut4':distribution([row['csd_minus_original_lut4'] for row in output]),
        'carry_descriptive':distribution([row['csd_minus_original_carry'] for row in output]),
        'by_constant_lut4':groups('constant_u32','csd_minus_original_lut4'),'by_context_lut4':groups('context','csd_minus_original_lut4'),
        'fresh_original_v9_lut4_disagreements':sum(row['fresh_minus_prior_original_lut4'] != 0 for row in output),
        'fresh_original_v9_carry_disagreements':sum(row['fresh_minus_prior_original_carry'] != 0 for row in output)}


def verify_history(root, prep, bindings, source_path, pairs, checker_sha):
    old_root = source_path.parent;completion_path = old_root/'measurements/completion.json'
    need((root/prep['previous_native_completion']['path']).resolve() == completion_path
        and prep['previous_native_completion']['sha256'] == V10C_NATIVE_COMPLETION_SHA, 'Exact retained V10c native completion required')
    stage = old_root/'measurements/attempt-0000'
    paths = [completion_path,stage/'completion.json',stage/'rtl-equivalence.json',stage/'arm-measurements.json',
        stage/'raw-evidence.json',stage/'raw-evidence.zip',old_root/'measurement-approval.json',old_root/'label-release.json']
    need(all(bindings.get(path) == sha(path.read_bytes()) for path in paths), 'Mandatory old native failure evidence missing/changed')
    previous = read(completion_path);proofs = read(stage/'rtl-equivalence.json');raw = read(stage/'raw-evidence.json')
    need(sha(completion_path.read_bytes()) == V10C_NATIVE_COMPLETION_SHA and read(stage/'completion.json') == previous
        and previous['complete'] is False and type(previous['universal_actual_rtl_pairs_proved']) is int
        and previous['universal_actual_rtl_pairs_proved'] == 16 and type(previous['fresh_synthesis_jobs_completed']) is int
        and previous['fresh_synthesis_jobs_completed'] == 0 and previous['pair_count'] == 32
        and len(proofs) == 32 and {row['pair_id'] for row in proofs} == {pair['pair_id'] for pair in pairs}
        and all(type(row['proved']) is bool for row in proofs) and sum(row['proved'] for row in proofs) == 16
        and sum(row['status'] == 'timeout' for row in proofs) == 16 and read(stage/'arm-measurements.json') == [],
        'V10c16-proved/16-timeout/0-area outcome must remain incomplete')
    need(sha((stage/'rtl-equivalence.json').read_bytes()) == previous['rtl_equivalence_sha256']
        and sha((stage/'arm-measurements.json').read_bytes()) == previous['arm_measurements_sha256']
        and raw['completion_sha256'] == sha((stage/'completion.json').read_bytes())
        and raw['archive_sha256'] == sha((stage/'raw-evidence.zip').read_bytes()), 'Old native sidecar/archive linkage differs')
    amendment_path = (root/prep['amendment']['path']).resolve();amendment = read(amendment_path)
    need(bindings.get(amendment_path) == prep['amendment']['sha256']
        and amendment.get('schema') == 'isaforge-v10d-proof-method-amendment-v1'
        and amendment.get('same_inputs_rtl_csd_source_proofs_tools') is True and amendment.get('new_area_outcomes_read') is False
        and amendment.get('old_run_marked_complete') is False and type(amendment.get('model_fits')) is int and amendment['model_fits'] == 0
        and amendment.get('previous_input_commit') == 'f7e04033a4bf52d5095dc7027d1d8a21a4f6e884'
        and amendment.get('previous_native_commit') == '888dc3ea6cdc4403d8cbfab38a51771c0fbf07d8'
        and amendment.get('previous_native_outcome') == {'pairs':32,'sat_proved':16,'sat_timeout':16,'area_measurements':0}, 'Explicit preserved-history amendment required')
    review_root = ROOT/'results/2026-10-15-v10-hardware-preparation'
    reviews = [review_root/name for name in ('independent-algebra-review.json','evidence-manifest.json','synthetic-algebra-evidence.zip','synthetic-timing-evidence.zip')]
    need(all(bindings.get(path) == sha(path.read_bytes()) for path in reviews), 'Mandatory reviewed-checker support evidence missing')
    review = read(reviews[0])
    need(review.get('status') == 'go-within-accepted-unsigned-json-scope' and review['checker_sha256'] == checker_sha,
        'Exact reviewed formal-checker scope required')
    return {'complete':False,'sat_pairs_proved':16,'sat_pairs_timeout':16,'fresh_area_arms':0,'completion_sha256':V10C_NATIVE_COMPLETION_SHA}


def run(root):
    root = Path(root).resolve();prep_path = root/'preparation.json';prep = read(prep_path)
    need(not (root/'preparation-failure.json').exists() and prep.get('schema') == 'isaforge-v10d-csd-hardware-preparation-v1'
        and prep.get('status') == 'prepared-inputs-only' and prep.get('new_area_outcomes_read') is False
        and type(prep.get('new_native_jobs')) is int and prep['new_native_jobs'] == 0
        and type(prep.get('model_fits')) is int and prep['model_fits'] == 0, 'Input-only V10d preparation required')
    bindings = {}
    for entry in prep['files']:
        need(set(entry) == {'path','sha256'} and isinstance(entry['path'],str) and not Path(entry['path']).is_absolute(), 'Relative preparation binding required')
        path = (root/entry['path']).resolve()
        need(path.is_relative_to(ROOT) and path not in bindings and sha(path.read_bytes()) == entry['sha256'], 'Prepared source/input changed')
        bindings[path] = entry['sha256']
    def bound(entry):
        path = (root/entry['path']).resolve();need(bindings.get(path) == entry['sha256'], 'Reference absent from flat preparation');return path
    pairs_path, tools_path, recipe_path = (bound(prep[name]) for name in ('pairs','tools','recipe'))
    pairs, tools, recipe = read(pairs_path),read(tools_path),read(recipe_path)
    source_path = bound(prep['source_preparation']);old = read(source_path)
    need(sha(source_path.read_bytes()) == V10C_PREPARATION_SHA, 'Exact frozen V10c input lineage required')
    for entry in old['files']:
        need(bindings.get((source_path.parent/entry['path']).resolve()) == entry['sha256'], 'Inherited source binding missing/changed')
    need(sha(pairs_path.read_bytes()) == old['pairs']['sha256'] and sha(tools_path.read_bytes()) == old['tools']['sha256'], 'Inherited pair/tool bytes changed')
    need(len(pairs) == 32 and [(pair['constant_u32'],pair['context']) for pair in pairs] == list(itertools.product(independent.CONSTANTS,independent.CONTEXTS)), 'Complete fixed32 grid required')
    pmap = {pair['pair_id']:pair for pair in pairs};need(len(pmap) == 32, 'Duplicate pair identity')
    for pair in pairs:
        need(type(pair['constant_u32']) is int, 'Exact integer constant required')
        original,csd = independent.source_formulas(pair['constant_u32'],pair['context']);identity = sha(original.encode())
        need(pair['formula'] == original and pair['rewritten_formula'] == csd and pair['pair_id'] == 'v10-csd:'+identity
            and pair['source_candidate_id'] == 'v9-coverage:'+identity and set(pair['arms']) == set(ARMS), 'Fixed formula/CSD identity changed')
        for arm,formula in [('original',original),('csd',csd)]:
            need(pair['arms'][arm]['formula'] == formula and bound(pair['arms'][arm]['rtl']).is_relative_to(root), 'Copied exact RTL arm required')
    need(recipe.get('schema') == 'isaforge-v10d-csd-hardware-recipe-v1'
        and all(type(recipe.get(key)) is int and recipe[key] == value for key,value in {'pairs':32,'frontend_jobs':64,'frontend_timeout_seconds':60,
            'required_proof_pairs':32,'fresh_synthesis_jobs':64,'measurement_timeout_seconds_per_arm':360,'workers':2,
            'verification_seed':independent.SEED,'vectors_per_arm':2148,'alternatives':1,'model_fits':0}.items())
        and recipe['arms'] == list(ARMS) and recipe['frontend_middle_commands'] == FRONTEND_COMMANDS
        and recipe['all_proofs_before_any_area'] is True and all(recipe[key] is False for key in ('filtering','replacements','automatic_retries')), 'Fixed V10d recipe differs')
    done_path = root/'measurements/completion.json';done = read(done_path);attempt = done['attempt']
    need(attempt == 'attempt-0000' and done.get('schema') == 'isaforge-v10d-csd-hardware-measurements-v1'
        and type(done['complete']) is bool and isinstance(done['failures'],list)
        and all(independent.integer(done[key]) for key in ('pair_count','frontend_jobs_completed','successful_frontend_jobs','proof_records',
            'universal_actual_rtl_pairs_proved','fresh_synthesis_jobs_completed','planned_fresh_synthesis_jobs','workers','vectors_per_arm','verification_seed','new_estimator_fits'))
        and done['pair_count'] == 32 and done['planned_fresh_synthesis_jobs'] == 64 and done['workers'] == 2
        and done['vectors_per_arm'] == 2148 and done['verification_seed'] == independent.SEED
        and done['new_estimator_fits'] == 0 and done['legacy_measurements_reused'] is False
        and done['scratch_directory'] == PREFIX+attempt, 'Strict completion/cohort identity required')
    stage = root/'measurements'/attempt;need(read(stage/'completion.json') == done, 'Root/stage completion differs')
    need(done['preparation_sha256'] == sha(prep_path.read_bytes()), 'Completed preparation identity differs')
    for name,key in [('measurement-approval.json','approval_sha256'),('label-release.json','release_sha256')]:
        need(sha((root/name).read_bytes()) == done[key], 'Reviewed release changed')
    release,approval = read(root/'label-release.json'),read(root/'measurement-approval.json')
    base = independent.absolute(release['collection_repository'])
    need(release['schema'] == 'isaforge-v10d-csd-hardware-release-v1' and release['attempt'] == attempt
        and approval['status'] == 'approved-v10d-csd-hardware-measurements'
        and approval['freeze_commit'] == release['freeze_commit'] and re.fullmatch('[0-9a-f]{40}',approval['freeze_commit'])
        and all(approval[key] == value for key,value in {'preparation_sha256':done['preparation_sha256'],'recipe_sha256':prep['recipe']['sha256'],
            'pairs_sha256':prep['pairs']['sha256'],'collector_sha256':done['collector_sha256'],'checker_sha256':done['checker_sha256']}.items())
        and all(release[key] == done[key] for key in ('preparation_sha256','approval_sha256','collector_sha256','checker_sha256','tools_sha256','prior_v9_originals_sha256')),
        'Exact approved release required')
    need(all(type(release[key]) is int and release[key] == value for key,value in {'pairs':32,'frontend_jobs':64,'fresh_synthesis_jobs':64,'workers':2,
        'verification_seed':independent.SEED,'vectors_per_arm':2148}.items()), 'Strict declared release counts required')
    parents = sorted({str(independent.absolute(entry['path']).parent) for entry in tools['executables'].values()})
    need(release['native_environment'] == {'PATH':':'.join([*parents,'/usr/bin','/bin']),'ABC':tools['executables']['abc']['path'],'LANG':'C','LC_ALL':'C','TZ':'UTC'}, 'Pinned environment ledger differs')
    prior_path = bound(prep['prior_v9_originals']);prior = read(prior_path)
    need(sha(prior_path.read_bytes()) == done['prior_v9_originals_sha256'] and sha(tools_path.read_bytes()) == done['tools_sha256'], 'Prior/tool record digest differs')
    raw,content = archive_content(stage,done,attempt)
    for name,path in [('pairs.json',pairs_path),('tools.json',tools_path),('recipe.json',recipe_path),('preparation.json',prep_path),
        ('approval.json',root/'measurement-approval.json'),('release.json',root/'label-release.json'),('prior-v9-originals.json',prior_path),
        ('premeasurement-amendment.json',bound(prep['amendment']))]:
        need(content[name] == path.read_bytes(), 'Archived input bytes differ: '+name)
    need(loads(content['completion.json']) == done, 'Archived completion differs')
    for archived,path,key in [('collector-source.py',ROOT/'scripts/measure_v10d_csd_hardware.py','collector_sha256'),
        ('checker-source.py',Path(algebra.__file__),'checker_sha256')]:
        need(sha(content[archived]) == done[key] == bindings.get(path.resolve()), 'Frozen collector/checker source differs')
    need(sha(content['frozen-measurement-source.py']) == bindings.get((ROOT/'scripts/measure_v10_csd_hardware.py').resolve()), 'Frozen measurement implementation differs')
    need(done['checker_sha256'] == sha(Path(algebra.__file__).read_bytes()), 'Shared formal checker used for replay differs')
    history = verify_history(root,prep,bindings,source_path,pairs,done['checker_sha256'])
    for pair in pairs:
        source = content['source-proofs/'+pair['pair_id'].split(':')[1]+'/proof.json']
        need(sha(source) == pair['proof']['sha256'] == bindings.get((root/pair['proof']['path']).resolve()), 'Inherited source proof changed')
    phases = {}
    for name,key in [('frontends.json','frontends_sha256'),('algebra-proofs.json','algebra_proofs_sha256'),('arm-measurements.json','arm_measurements_sha256')]:
        data = (stage/name).read_bytes();need(sha(data) == done[key] and content[name] == data, 'Stage/archive phase records differ')
        phases[name] = loads(data)
    frontends,proofs,metrics = (phases[name] for name in ('frontends.json','algebra-proofs.json','arm-measurements.json'))
    front_index = {};graphs = {};word_comparisons = 0
    for record in frontends:
        key = record['pair_id'],record['arm'];need(key not in front_index and key[0] in pmap and key[1] in ARMS, 'Duplicate/foreign frontend')
        front_index[key] = record;graph,compared = verify_frontend(pmap[key[0]],key[1],record,content,tools,base,attempt)
        graphs[key] = graph;word_comparisons += compared
    proof_index = {};proved = 0
    for proof in proofs:
        key = proof['pair_id'];need(key not in proof_index and key in pmap, 'Duplicate/foreign universal proof');proof_index[key] = proof
        need(proof.get('schema') == 'isaforge-v10d-actual-rtl-proof-v1' and type(proof['proved']) is bool
            and proof['checker_sha256'] == done['checker_sha256'] and independent.elapsed(proof['elapsed_seconds'])
            and stamp(proof['completed_at_utc']) >= stamp(proof['started_at_utc']), 'Strict shared proof wrapper required')
        need(loads(content['algebra-proofs/'+key.split(':')[1]+'/proof.json']) == proof, 'Archived proof wrapper differs')
        evidence = {arm:front_index.get((key,arm)) for arm in ARMS}
        need(proof['frontend_records'] == evidence, 'Universal proof uses different frontend records')
        replay = None;error = None
        if all(evidence[arm] and evidence[arm]['success'] is True for arm in ARMS):
            need(all(stamp(proof['started_at_utc']) >= stamp(evidence[arm]['completed_at_utc']) for arm in ARMS), 'Universal proof began before its frontend completed')
            try: replay = loads(json.dumps(algebra.prove_pair(*(graphs[key,arm] for arm in ARMS),width=32)))
            except Exception as exception: error = repr(exception)
        else: error = "ValueError('Both actual frontends must succeed')"
        need(proof['checker_result'] == replay and proof['error'] == error
            and proof['proved'] is bool(replay is not None and replay.get('proved') is True and replay.get('status') == 'proved'), 'Shared reviewed proof replay differs')
        proved += proof['proved']
    expected_keys = {(pair['pair_id'],arm) for pair in pairs for arm in ARMS}
    gate = None;comparisons = 0
    if done['measurement_started_at_utc'] is not None:
        data = (stage/'measurement-gate.json').read_bytes();gate_record = loads(data)
        need(sha(data) == done['measurement_gate_sha256'] and content['measurement-gate.json'] == data
            and gate_record['schema'] == 'isaforge-v10d-area-gate-v1'
            and gate_record['all32_proof_sha256'] == done['algebra_proofs_sha256']
            and gate_record['all64_frontend_sha256'] == done['frontends_sha256']
            and gate_record['measurement_started_at_utc'] == done['measurement_started_at_utc']
            and set(front_index) == expected_keys and len(proofs) == proved == 32, 'Complete32/64 proof gate required before any area')
        gate = stamp(done['measurement_started_at_utc'])
        need(all(stamp(record['completed_at_utc']) <= gate for record in proofs), 'Area gate predates a universal proof')
    else: need(done['measurement_gate_sha256'] is None and not metrics, 'Area records without a proof gate')
    metric_index = {}
    for metric in metrics:
        key = metric['pair_id'],metric['arm'];need(key not in metric_index and key in expected_keys and gate is not None, 'Duplicate/foreign/ungated arm')
        metric_index[key] = metric;comparisons += verify_measurement(pmap[key[0]],key[1],metric,content,tools,base,attempt,gate,done['measurement_gate_sha256'])
    need(done['frontend_jobs_completed'] == len(frontends) and done['successful_frontend_jobs'] == sum(record['success'] for record in frontends)
        and done['proof_records'] == len(proofs) and done['universal_actual_rtl_pairs_proved'] == proved
        and done['fresh_synthesis_jobs_completed'] == len(metrics), 'Completion counts differ from replayed phase records')
    pairs_out = [];summary_out = None
    if done['complete']:
        need(not done['failures'] and gate is not None and set(metric_index) == expected_keys
            and set(front_index) == expected_keys and all(record['success'] for record in frontends) and proved == 32, 'All32 proofs/64 frontends/64 fresh arms required')
        pairs_out,summary_out = paired_results(pairs,metrics,prior,tools)
        published = {'schema':'isaforge-v10d-paired-summary-v1','complete':True,'pairs':pairs_out,**summary_out,'scope':recipe['limits']}
        data = (stage/'summary.json').read_bytes()
        need(sha(data) == done['summary_sha256'] and content['summary.json'] == data and loads(data) == published, 'Independent complete summary differs')
    else: need(done['summary_sha256'] is None, 'Incomplete primary must stay null')
    return {'schema':'isaforge-v10d-independent-portable-audit-v1','status':'pass','complete':done['complete'],
        'preparation_sha256':sha(prep_path.read_bytes()),'completion_sha256':sha((stage/'completion.json').read_bytes()),
        'archive_sha256':raw['archive_sha256'],'frontends_sha256':done['frontends_sha256'],'algebra_proofs_sha256':done['algebra_proofs_sha256'],
        'arm_measurements_sha256':done['arm_measurements_sha256'],'audit_source_sha256':sha(Path(__file__).read_bytes()),
        'independent_helper_sha256':sha(Path(independent.__file__).read_bytes()),'shared_checker_sha256':done['checker_sha256'],
        'archive_members_verified':len(content),'frontend_records_verified':len(frontends),'word_json_sample_comparisons':word_comparisons,
        'rtl_pairs_proved_shared_checker':proved,'arms_recounted':len(metrics),'source_and_mapped_sample_comparisons':comparisons,
        'failures':done['failures'],'pairs':pairs_out,'summary':summary_out,
        'retained_v10c_native_outcome':history,
        'independence':'No native tools/collector/model imports. Independent fixed formulas, vectors, unsigned concrete word evaluation, raw RTL observations and mapped primitive/resource recount. Universal word equality replays the shared reviewed algebra checker; not an independent universal checker or independent native RTL retranslation. Authenticated frontend source/commands/JSON lineage. No universal mapped equivalence, timing, CPU, power or ASIC claim.'}


audit = run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args();result = run(args.root);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({key:value for key,value in result.items() if key != 'pairs'},indent=2))
