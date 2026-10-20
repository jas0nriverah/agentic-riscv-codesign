"""Bounded baseline feasibility pilot for the next measured-speedup cohort.

Reuses the pinned RV32I PicoRV32 SoC and serial harness. No custom speedup
labels, synthesis, model fitting, or selection conclusions are produced here.
All three declared workloads, including memory-budget failures, are retained.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from . import codesign as c
from .codesign_audit import audit
from .speedup_corpus import validate_isa

WORKLOADS = {'aha-mont64':'aha-mont64/mont64.c', 'nettle-sha256':'nettle-sha256/nettle-sha256.c',
             'matmult-int':'matmult-int/matmult-int.c'}


def validate_baseline(raw):
    words=raw.get('words',[])
    c.require(raw.get('status')==0x600d600d and len(words)==5 and words[0]==0x49534146 and words[4]==1,
              'Upstream benchmark self-check failed')
    c.require(words[2]>0 and words[3]>0 and raw.get('fault')==0 and raw.get('partial_report_bits')==0,
              'Invalid counters or memory/report fault')
    c.require(all(raw.get(k)==0 for k in ('pcpi_handshakes','pcpi_valid_cycles','pcpi_wait_cycles')), 'Unexpected custom instruction')
    return {'cycles':words[2],'instructions':words[3],'benchmark_result_u32':words[1],
            'upstream_self_check':True,'custom_instructions':0}


def run(reference, output):
    reference, output=Path(reference).resolve(),Path(output).resolve()
    audit(reference)
    base=c.read(reference/'plan.json')
    files={f'hardware/{name}':c.sha(c.ROOT/'hardware'/name) for name in ('embench_firmware.c','embench_memory.c')}
    files.update({f'benchmarks/embench/src/{p}':c.sha(c.ROOT/'benchmarks/embench/src'/p) for p in WORKLOADS.values()})
    plan={'schema':'isaforge-next-workloads-baseline-v1','reference_context':base['context_id'],
          'source_sha256':c.sha(__file__),'files':files,'workloads':WORKLOADS,
          'isa':'rv32i_zicsr','abi':'ilp32','optimization':'-O2','cpu_mhz_scale':1,'ram_bytes':8192,
          'program_data_limit':4096,'stack_reservation':4096,'custom_interface':'unchanged two-input one-output PCPI; disabled for baselines',
          'native_workers':1,'build_workers':2,'max_commands':24,'command_seconds':60,'total_native_seconds':240,
          'scope':'Compatibility, memory fit, and upstream self-check. No new instruction-speedup labels.'}
    if output.exists():
        c.require(c.unseal(output/'probe-plan.json')==plan,'Probe protocol changed')
    else:
        output.mkdir(parents=True)
        c.seal(output/'probe-plan.json',plan)
        shutil.copytree(reference/'inputs',output/'inputs')
        for name in ('embench_firmware.c','embench_memory.c'):
            shutil.copyfile(c.ROOT/'hardware'/name,output/'inputs'/name)
        (output/'probe-source.py').write_bytes(Path(__file__).read_bytes())
    inputs=output/'inputs'
    tools={k:v['path'] for k,v in base['tools'].items()}
    commands=c.unseal(output/'commands.json') if (output/'commands.json').exists() else []

    def execute(args,log):
        c.require(c.sha(__file__)==plan['source_sha256'],'Probe source changed')
        for path,expected in files.items():c.require(c.sha(c.ROOT/path)==expected,'Probe input changed')
        for name,expected in base['inputs'].items():c.require(c.sha(inputs/name)==expected,'Pinned input changed')
        for name in ('embench_firmware.c','embench_memory.c'):
            c.require(c.sha(inputs/name)==files['hardware/'+name],'Harness changed')
        for tool in base['tools'].values():c.require(c.sha(tool['path'])==tool['sha256'],'Tool changed')
        remaining=plan['total_native_seconds']-sum(r['seconds'] for r in commands)
        c.require(remaining>0 and len(commands)<plan['max_commands'],'Probe budget exhausted')
        c.require(shutil.disk_usage(output).free>2*1024**3,'Less than 2 GiB free')
        args=list(map(str,args));began=time.monotonic();process=None;error=None
        try:
            with log.open('x') as stream:
                process=subprocess.Popen(args,cwd=output,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                process.wait(timeout=min(remaining,plan['command_seconds']))
            c.require(process.returncode==0,'Command failed: '+str(log))
        except BaseException as exception:
            error=repr(exception)
            if process is not None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
            raise
        finally:
            commands.append({'argv':args,'seconds':time.monotonic()-began,'returncode':process.returncode if process else None,
                             'error':error,'log':str(log.relative_to(output)),'sha256':c.sha(log) if log.exists() else None})
            c.seal(output/'commands.json',commands)
        return log.read_text()

    results=[]
    for workload,source in WORKLOADS.items():
        folder=output/workload;result_path=folder/'result.json'
        if result_path.exists():
            record=c.unseal(result_path)
            for path,expected in record['artifacts'].items():c.require(c.sha(folder/path)==expected,'Probe evidence changed')
            results.append(record);continue
        folder.mkdir(exist_ok=True)
        attempt=folder/f'attempt-{len(list(folder.glob("attempt-*"))):03d}';attempt.mkdir()
        began=time.monotonic();record={'workload':workload,'status':'failed'}
        try:
            program=attempt/'program.c';shutil.copyfile(c.ROOT/'benchmarks/embench/src'/source,program)
            elf,binary,image=attempt/'firmware.elf',attempt/'firmware.bin',attempt/'firmware.hex'
            execute([tools['gcc'],'-march=rv32i_zicsr','-mabi=ilp32','-O2','-std=gnu17','-nostdlib','-nostartfiles',
                     '-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections','-msmall-data-limit=0','-mno-relax',
                     '-DCPU_MHZ=1','-I',inputs,'-Wl,--no-relax','-Wl,--gc-sections','-Wl,-T,'+str(inputs/'soc_link.ld'),
                     inputs/'soc_start.S',inputs/'embench_firmware.c',inputs/'embench_memory.c',program,inputs/'beebsc.c',
                     '-lgcc','-o',elf],attempt/'compile.log')
            execute([tools['objcopy'],'-O','binary',elf,binary],attempt/'objcopy.log')
            assembly=execute([tools['objdump'],'-d',elf],attempt/'disassembly.txt')
            record['isa_validation']=validate_isa(assembly)
            c.require(record['isa_validation']['custom_static_sites']==0,'Unexpected custom baseline opcode')
            symbols=execute([tools['nm'],'-n',elf],attempt/'symbols.txt')
            record['program_and_bss_end']=next(int(r.split()[0],16) for r in symbols.splitlines() if r.split()[-1]=='_program_end')
            image.write_text(c.memory_image(binary.read_bytes()))
            top=attempt/'soc_top.v';top.write_text((inputs/'soc_top.v').read_text().replace('"firmware.hex"','"'+str(image)+'"'))
            datapath=attempt/'candidate.v';datapath.write_text(c.generate_rtl('add(in0,in1)'))
            execute([tools['verilator'],'--cc','--exe','--build','-j','2','-Wno-fatal','--top-module','soc_top',
                     '--Mdir',attempt/'obj_dir','-GEXTENSION_MASK=0',inputs/'picorv32.v',inputs/'pcpi_single.v',datapath,top,inputs/'soc_sim.cpp'],attempt/'build.log')
            raw=json.loads(execute([attempt/'obj_dir/Vsoc_top'],attempt/'simulation.json'))
            record.update(status='passed',performance=validate_baseline(raw))
        except (ValueError,subprocess.SubprocessError,OSError) as error:
            record['error']=str(error)
            if (attempt/'compile.log').exists() and 'firmware must leave at least 4 KiB' in (attempt/'compile.log').read_text():
                record['status']='does_not_fit_current_memory_contract'
        record['seconds']=time.monotonic()-began
        record['artifacts']={str(p.relative_to(folder)):c.sha(p) for p in folder.rglob('*') if p.is_file() and 'obj_dir' not in p.parts}
        c.seal(result_path,record);results.append(record)
        print(json.dumps({k:v for k,v in record.items() if k!='artifacts'}),flush=True)
    report={'plan':plan,'results':results,'native_commands':len(commands),'native_seconds':sum(r['seconds'] for r in commands),
            'new_candidate_speedup_labels':0,'cross_workload_model_trained':False}
    c.seal(output/'probe-report.json',report)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv);run(args.reference_root,args.output)


if __name__=='__main__':main()
