"""Measured-program corpus and leakage-controlled cross-workload evaluation.

The first producer imports authenticated CRC32 processor measurements. Evaluation
refuses a single workload; unit fixtures never become research observations.
No new area model, architecture, or model hyperparameter search is introduced.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import random
import re
import time

from . import codesign as c
from .codesign_audit import audit
from .evaluation import _metrics
from .features import FEATURE_COLUMNS, parse_formula
from .model import SpeedupPredictor, validate_training_rows
from .selection import _measurement, run_policy

LABEL_KIND = 'rtl_application_speedup_at_common_routed_clock'


def validate_isa(disassembly):
    """Fail closed on M/C/F/D/A instructions or an unknown custom encoding.

    This is an instruction-encoding compatibility gate for the existing RV32I
    core, not a replacement for executing the program and its self-check.
    """
    words = re.findall(r'^\s*[0-9a-f]+:\s+([0-9a-f]{4,16})\s', disassembly, re.M)
    c.require(words, 'No disassembled instructions')
    custom = 0
    for raw in words:
        c.require(len(raw) == 8, 'Compressed or non-RV32 instruction')
        word = int(raw,16); opcode = word & 127
        funct3, funct7 = (word >> 12) & 7, word >> 25
        c.require(opcode in (0x03,0x0f,0x13,0x17,0x23,0x33,0x37,0x63,0x67,0x6f,0x73,0x0b),
                  'Opcode outside RV32I/CSR/custom contract')
        if opcode == 0x33:
            c.require(funct7 == 0 or (funct7 == 0x20 and funct3 in (0,5)), 'M-extension or unsupported register operation')
        if opcode == 0x13 and funct3 in (1,5):
            c.require(funct7 == 0 or (funct3 == 5 and funct7 == 0x20), 'Unsupported immediate shift')
        if opcode in (0x03,0x23,0x63,0x67,0x0f):
            allowed = {0x03:(0,1,2,4,5),0x23:(0,1,2),0x63:(0,1,4,5,6,7),0x67:(0,),0x0f:(0,)}
            c.require(funct3 in allowed[opcode], 'Unsupported load/store/branch/fence encoding')
        if opcode == 0x73:
            c.require(word in (0x00000073,0x00100073) or word & 0xfffff07f in (0xc0002073,0xc0202073),
                      'CSR unsupported by the configured 32-bit-counter core')
        if opcode == 0x0b:
            c.require(word & 0xfe00707f == 0x0200000b, 'Unsupported custom instruction encoding')
            custom += 1
    return {'instruction_words_checked':len(words),'custom_static_sites':custom,'isa':'rv32i_zicsr + custom-0/funct7=1/funct3=0'}


def family(formula):
    """Conservative operation-tree family: ignore constants and input renaming."""
    commutative = {'add','and','or','xor','mul'}
    def shape(node):
        if not node.children: return 'constant' if isinstance(node.value,int) else 'input'
        children = [shape(child) for child in node.children]
        if node.value in commutative: children.sort()
        return str(node.value)+'('+','.join(children)+')'
    return shape(parse_formula(formula))


def import_crc32(root):
    root = Path(root).resolve()
    proof = audit(root)
    plan = c.read(root/'plan.json')
    processor = {'core':plan['core_commit'],'isa':plan['configuration']['isa'],
                 'ram_bytes':plan['configuration']['ram_bytes'],'clock_mhz':12.0,'pcpi_wait_cycles':1,
                 'compiler_sha256':plan['tools']['gcc']['sha256'],
                 'hardware':{p:h for p,h in plan['source_bindings'].items() if p in
                             ('hardware/soc_top.v','hardware/pcpi_single.v','hardware/soc_start.S','hardware/soc_link.ld')}}
    processor_id = c.digest(processor)
    inputs = {'seed':0,'updates_per_repetition':1024,'measured_repetitions':170,
              'crc_source_sha256':plan['inputs']['crc32.c'],'harness_sha256':plan['inputs']['core_crc_firmware.c']}
    rows = []
    for observed in c.read(root/'observations.json'):
        record = c.unseal(root/'measurements'/observed['evaluation_id']/'measurement.json')
        firmware = root/record['firmware_image']
        isa = validate_isa((firmware.parent/'disassembly.txt').read_text())
        c.require(isa['custom_static_sites'] > 0, 'Custom instruction absent from executable')
        identity = {'workload':'embench-crc32','source_revision':plan['embench_commit'],
                    'input_id':c.digest(inputs),'processor_id':processor_id,'formula':observed['formula'],
                    'implementation_sha256':record['implementation_sha256'],
                    'firmware_sha256':c.sha(firmware),'measurement_context_id':plan['context_id']}
        rows.append({**observed,'candidate_id':c.digest(identity),'discovery_candidate_id':observed['candidate_id'],
                     'sample_identity':identity,'workload_group':'embench-crc32','workload':'embench-crc32',
                     'processor_id':processor_id,'input_configuration':inputs,'label_kind':LABEL_KIND,
                     'candidate_family':family(observed['formula']),'correctness_verified':True,
                     'custom_execution_count':record['performance']['protocol_statistics']['pcpi_handshakes'],
                     'area_cap':proof['baseline']['resources']['lut4_count']+128,
                     'feature_provenance':'Frozen RV32IM discovery proxies; measured execution is RV32I. Re-extract on the target ISA for the next cohort.',
                     'isa_validation':isa})
    return {'schema':'isaforge-measured-speedup-corpus-v1','producer':'authenticated CRC32 processor measurements',
            'processor_contexts':{processor_id:processor},'source_contexts':[plan['context_id']],
            'rows':rows,'readiness':readiness(rows)}


def validate(rows):
    c.require(rows and len({r['candidate_id'] for r in rows}) == len(rows), 'Nonempty unique speedup samples required')
    validate_training_rows(rows)
    c.require(len({r['processor_id'] for r in rows}) == 1, 'Mixed processor/compiler configurations require an explicit context-aware model')
    c.require(all(r['label_kind'] == LABEL_KIND and r['measurement_source'] == 'synthesis_estimate' for r in rows), 'Measured RTL program labels required')
    for row in rows:
        _measurement(row)
        c.require(row['candidate_id'] == c.digest(row['sample_identity']), 'Sample identity mismatch')
        c.require(row['candidate_family'] == family(row['formula']), 'Candidate family mismatch')
        c.require(row['correctness_verified'] is True and row['custom_execution_count'] > 0, 'Unverified program execution')
        c.require(isinstance(row['workload_group'],str) and row['workload_group'], 'Explicit workload family required')
        c.require(row['sample_identity']['processor_id'] == row['processor_id'] and
                  row['sample_identity']['workload'] == row['workload'] and
                  row['sample_identity']['formula'] == row['formula'], 'Sample context mismatch')
    c.require(all(len({r['workload_group'] for r in rows if r['workload']==workload})==1
                  for workload in {r['workload'] for r in rows}), 'A workload cannot cross family splits')


def readiness(rows):
    validate(rows)
    groups = sorted({r['workload_group'] for r in rows})
    return {'measured_rows':len(rows),'workload_groups':groups,'group_count':len(groups),
            'cross_workload_ready':len(groups)>=3,
            'missing':'At least three independently grouped workload pools and nonempty training after related-candidate exclusion.' if len(groups)<3 else None,
            'single_workload_scores_are_generalization_evidence':False}


def split(rows, held_out):
    test = [r for r in rows if r['workload_group'] == held_out]
    c.require(test, 'Unknown held-out workload group')
    families = {r['candidate_family'] for r in test}
    train = [r for r in rows if r['workload_group'] != held_out and r['candidate_family'] not in families]
    excluded = [r['candidate_id'] for r in rows if r['workload_group'] != held_out and r['candidate_family'] in families]
    return train,test,excluded


class TransferTools(c.LiveSelectionTools):
    def __init__(self, candidates, measure, budget, area_cap, seed, training):
        super().__init__(candidates,measure,budget,area_cap,seed)
        self.training = copy.deepcopy(training)

    @property
    def training_size(self): return len(self.training)+len(self.observations)

    def predict(self, ids):
        public = {r['candidate_id']:r for r in self.list_candidates()}
        model = SpeedupPredictor(seed=self.seed).fit(self.training+list(self.observations.values()))
        predictions = model.predict([public[i] for i in ids])
        self.record({'action':'predict','historical_training_ids':[r['candidate_id'] for r in self.training],
                     'paid_target_training_ids':self.measured_candidate_ids,'predictions':predictions,'warnings':model.warnings})
        return predictions


def run_transfer_policy(tools, policy):
    """Future transfer acquisition uses the predicted mean to break UCB ties.

    The frozen six-candidate study retains its original seeded tie behavior.
    This change addresses an observed tie, not a retrospectively scored gain.
    """
    if policy != 'active_learning': return run_policy(tools,policy,bootstrap=2)
    candidates = tools.list_candidates()
    random.Random(tools.seed).shuffle(candidates)
    while tools.remaining_budget:
        candidates = [r for r in candidates if r['candidate_id'] not in tools.measured_candidate_ids]
        if not candidates: break
        predictions = {r['candidate_id']:r for r in tools.predict([r['candidate_id'] for r in candidates])}
        chosen = max(candidates,key=lambda r:(predictions[r['candidate_id']]['upper'],predictions[r['candidate_id']]['mean']))
        tools.measure(chosen['candidate_id'])
    selected = tools.choose_final()
    return {'policy':policy,'measurements_used':tools.measurements_used,'measured_candidate_ids':tools.measured_candidate_ids,
            'selected':selected,'best_speedup':selected['speedup'] if selected else 1.0}


def evaluate(rows, output, *, seeds=(0,1,2,3,4), budgets=(1,2,3)):
    status = readiness(rows)
    c.require(status['cross_workload_ready'], 'Cross-workload evaluation needs at least three workload groups; CRC32 alone is adaptation only')
    output = Path(output)
    c.require(not output.exists(), 'Use a fresh evaluation directory')
    # Validate every split before producing any score; do not quietly omit a
    # difficult/empty fold after reading its labels.
    folds = [(g,*split(rows,g)) for g in status['workload_groups']]
    c.require(all(len(train)>=2 for _,train,_,_ in folds), 'Related-candidate exclusions leave insufficient training; collect more workloads')
    output.mkdir(parents=True)
    c.seal(output/'protocol.json',{'model':'Existing SpeedupPredictor: 20 bootstrap XGBoost models, 80 trees, depth 2; no tuning',
                                 'seeds':seeds,'budgets':budgets,'data_sha256':c.digest(rows),
                                 'source_sha256':c.sha(__file__),'target':'measured application elapsed-speedup ratio',
                                 'acquisition':'Largest upper ensemble quantile, then predicted mean, then seeded order; no tuning on future folds',
                                 'split':'Whole workload/source family held out; shared operation-tree families removed from training'})
    reports = []
    for group,train,test,excluded in folds:
        began = time.monotonic()
        public = [{k:r[k] for k in ('candidate_id','benchmark','formula',*FEATURE_COLUMNS)} for r in test]
        predictor = SpeedupPredictor(seed=0).fit(train)
        predictions = predictor.predict(public)
        # Freeze zero-shot predictions before scoring. Target adaptation is a
        # separate policy run, charged one observation for every queried design.
        c.seal(output/(c.digest(group)+'-predictions.json'),predictions)
        selection = []
        for benchmark in sorted({r['benchmark'] for r in test}):
            pool = [r for r in test if r['benchmark']==benchmark]
            labels = {r['candidate_id']:r for r in pool}
            caps = {r['area_cap'] for r in pool}; c.require(len(caps)==1,'Mixed area caps')
            cap = next(iter(caps))
            oracle = max([1.0]+[r['speedup'] for r in pool if r['area']<=cap and r['timing_feasible']])
            for seed in seeds:
                for budget in budgets:
                    for policy in c.POLICIES:
                        tools = TransferTools(pool,lambda r:copy.deepcopy(labels[r['candidate_id']]),budget,cap,seed,train)
                        result = run_transfer_policy(tools,policy)
                        selection.append({**result,'benchmark':benchmark,'seed':seed,'budget':budget,
                                          'regret':oracle-result['best_speedup'],'oracle_speedup':oracle,
                                          'target_measurement_seconds':sum(labels[i]['measurement_seconds'] for i in tools.attempts),
                                          'events':tools.events})
        reports.append({'held_out_group':group,'training_rows':len(train),'training_workloads':sorted({r['workload'] for r in train}),
                        'excluded_related_candidate_ids':excluded,'zero_shot_metrics':_metrics([r['speedup'] for r in test],predictions),
                        'selection_with_paid_target_adaptation':selection,'seconds':time.monotonic()-began,'warnings':predictor.warnings})
    report = {'folds':reports,'label_kind':LABEL_KIND,'historical_collection_rows':len(rows),
              'historical_collection_seconds':sum(r['measurement_seconds'] for r in rows),
              'limitations':['No hyperparameter tuning. Reusing inspected workload folds for revisions makes them development data.',
                             'Operation-tree families exclude close variants but do not prove arbitrary semantic independence; curated workload/source groups remain required.',
                             'Ensemble disagreement is not calibrated confidence. Corpus provenance must remain attached.']}
    c.seal(output/'report.json',report)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    export=sub.add_parser('export'); export.add_argument('--root',type=Path,required=True); export.add_argument('--output',type=Path,required=True)
    evaluate_parser=sub.add_parser('evaluate'); evaluate_parser.add_argument('--corpus',type=Path,required=True); evaluate_parser.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    if args.command=='export':
        result=import_crc32(args.root); c.seal(args.output,result); print(result['readiness'])
    else:
        evaluate(c.unseal(args.corpus)['rows'],args.output)


if __name__=='__main__': main()
