"""Read existing partial input evidence only; never rerun a workload or extract candidates."""
from collections import Counter
import gzip,hashlib,json
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src')]
from candidates import readProgram
raw=ROOT/'generated/v11-reserved-inputs/attempt-0000'
plan=json.loads((raw/'input-plan.json').read_text())
output=Path(__file__).with_name('partial-volume-diagnosis.json')
if output.exists():raise FileExistsError('Existing diagnosis immutable')
report={'schema':'isaforge-v11-existing-partial-diagnosis-v1','input_plan_sha256':hashlib.sha256((raw/'input-plan.json').read_bytes()).hexdigest(),'records':{},'no_workload_reexecution_candidates_labels_models_features_fits':True}
for name in ['ammunition','pm']:
 folder=raw/name;path=folder/(name+'.jsonl.gz.partial');beg=time.perf_counter();lines=size=0
 with gzip.open(path,'rb') as f:
  while chunk:=f.read(8*1024*1024):lines+=chunk.count(b'\n');size+=len(chunk)
 program=readProgram(folder/'O2'/(name+'.elf'),plan['tools']['objdump']['path'])
 pcs=Counter();symbols=Counter();sample=0
 with gzip.open(path,'rt') as f:
  for line in f:
   record=json.loads(line);pc=int(record['pc'],16);pcs[pc]+=1;symbols[program.get(pc,{}).get('symbol','unknown')]+=1
   sample+=1
   if sample==500000:break
 elf=folder/'O2'/(name+'.elf');check=folder/'O2-selfcheck.log'
 report['records'][name]={'partial_path':str(path.relative_to(ROOT)),'partial_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'compressed_bytes':path.stat().st_size,'uncompressed_jsonl_bytes':size,'retained_measured_commits':lines,'gzip_crc_and_eof_valid':True,'complete_measurement_window':False,'diagnostic_read_seconds':time.perf_counter()-beg,'first_measured_commits_sample':sample,'sample_symbol_counts':dict(symbols.most_common(15)),'sample_hottest_pcs':[{'pc':hex(pc),'count':count,'symbol':program.get(pc,{}).get('symbol')} for pc,count in pcs.most_common(10)],'elf_to_O2_selfcheck_log_mtime_gap_seconds':check.stat().st_mtime-elf.stat().st_mtime,'elf_to_partial_final_mtime_gap_seconds':path.stat().st_mtime-elf.stat().st_mtime,'timing_note':'File-mtime gaps are approximate phase evidence, not benchmark/native timing measurements. Fixed trace deadline300s; surfaced PermissionError can mask original termination context. No complete trace/count is inferred from a valid partial gzip.'}
 print(name,lines,size,dict(symbols.most_common(4)),flush=True)
report['interpretation']='Both original untraced selfchecks and O0/O2 snapshots pass. The retained incomplete measured windows contain tens of millions of commits; Python marker parsing, JSON formatting, CountedTrace JSON reparsing and gzip compression are in the synchronous producer-consumer path. This establishes substantial trace volume and processing overhead, not a proof of nontermination or an exact attribution of bottleneck cost. A future prelabel-reviewed native compressed raw-commit spool plus offline unchanged decoder/marker validation could separate execution/capture from JSON processing without shortening the ROI; no such new run or budget amendment is performed here.'
output.write_text(json.dumps(report,indent=2)+'\n')
