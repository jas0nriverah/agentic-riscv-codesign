"""Charge a small independent instruction-latency calibration; no workload labels.

Reuses NativeRunner, the pinned SoC, compiler and PCPI interface. The instruction
cases and semantic answers are fixed before execution. This is a microbenchmark,
not a new workload or a routed hardware measurement.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c

ALU = ('add', 'sub', 'and', 'or', 'xor', 'slt', 'sltu',
       'addi', 'andi', 'ori', 'xori', 'slti', 'sltiu', 'lui')
SHIFTS = ('slli', 'srli', 'srai')
SOURCES = ('scripts/calibrate_picorv32_latency.py', 'hardware/latency_sim.cpp',
           'isaforge/codesign.py', 'isaforge/rtl.py')


def signed(value):
    return value if value < 2**31 else value-2**32


def cases():
    result = []
    for a, b in ((0xa5a55a5a, 0x5aa5a55a), (0x7fffffff, 0xffffffff)):
        for op in ALU:
            values = dict(add=a+b, sub=a-b, **{'and': a & b, 'or': a | b}, xor=a ^ b,
                          slt=int(signed(a)<signed(b)), sltu=int(a<b), addi=a-3,
                          andi=a & 255, ori=a | 255, xori=a ^ 255,
                          slti=int(signed(a)<-3), sltiu=int(a<0xfffffffd), lui=0x12345000)
            imm = -3 if op in ('addi', 'slti', 'sltiu') else 255
            assembly = (f'{op} t2,0x12345' if op=='lui' else
                        f'{op} t2,t0,{imm}' if op in ('addi','andi','ori','xori','slti','sltiu') else f'{op} t2,t0,t1')
            result.append(dict(op=op, immediate=None, a=a, b=b, assembly=assembly,
                               expected=values[op] & 0xffffffff))
        for op in SHIFTS:
            for amount in range(32):
                value = a << amount if op=='slli' else (signed(a) if op=='srai' else a) >> amount
                result.append(dict(op=op, immediate=amount, a=a, b=b,
                                   assembly=f'{op} t2,t0,{amount}', expected=value & 0xffffffff))
    # Place custom operations last, so the unextended-core trap control also
    # checks every ordinary operation before reaching the unsupported opcode.
    for a, b in ((0xa5a55a5a, 0x5aa5a55a), (0x7fffffff, 0xffffffff)):
        result.append(dict(op='pcpi', immediate=None, a=a, b=b,
                           assembly='.insn r 0x0b,0,1,t2,t0,t1', expected=(a+b) & 0xffffffff))
    return result


def firmware(rows):
    lines = ['.option norvc', '.option norelax', '.section .text.start', '.global _start', '_start:']
    operands = None
    for index, row in enumerate(rows):
        if operands != (row['a'], row['b']):
            lines += [f'li t0,{row["a"]}', f'li t1,{row["b"]}']
            operands = row['a'], row['b']
        lines += [f'.global probe_{index}', f'probe_{index}:', row['assembly'],
                  f'li t3,{row["expected"]}', 'bne t2,t3,fail']
    lines += ['li s0,0x10000000', 'li t0,0x49534146', 'sw t0,0(s0)',
              f'li t0,{len(rows)}', 'sw t0,0(s0)', 'li t0,0x600d600d', 'sw t0,4(s0)',
              '1: j 1b', 'fail:', 'li s0,0x10000000', 'li t0,0xdead0003', 'sw t0,4(s0)', '2: j 2b']
    return '\n'.join(lines)+'\n'


def prepare(reference, output):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    c.require(not output.exists(), 'Use a fresh calibration directory')
    old = c.read(reference/'plan.json')
    c.require(old['core_commit']==c.CORE_COMMIT, 'Pinned core required')
    output.mkdir(parents=True)
    inputs = output/'inputs'; inputs.mkdir()
    for name in ('picorv32.v', 'COPYING', 'soc_top.v', 'pcpi_single.v', 'soc_link.ld'):
        c.require(c.sha(reference/'inputs'/name)==old['inputs'][name], 'Reference input changed')
        shutil.copyfile(reference/'inputs'/name, inputs/name)
    shutil.copyfile(c.ROOT/'hardware/latency_sim.cpp', inputs/'latency_sim.cpp')
    rows = cases()
    (inputs/'firmware.S').write_text(firmware(rows))
    (inputs/'candidate.v').write_text(c.generate_rtl('add(in0,in1)'))
    plan = dict(schema='isaforge-picorv32-latency-calibration-v1', core_commit=c.CORE_COMMIT,
                scope='Independent operation microbenchmark; no application labels or hardware synthesis.',
                cases=rows, tools={k:old['tools'][k] for k in ('gcc','objcopy','objdump','nm','verilator')},
                source_bindings={p:c.sha(c.ROOT/p) for p in SOURCES},
                inputs={p.name:c.sha(p) for p in inputs.iterdir()},
                limits=dict(commands=8, native_seconds=180, command_seconds=60, build_workers=2),
                expected_rule='ALU 4; immediate shift 4+floor(amount/4)+(amount mod 4); PCPI 5.',
                applicability='Pinned synchronous RAM, dual-port registers, TWO_STAGE_SHIFT=1, BARREL_SHIFTER=0, one-wait PCPI; not arbitrary contexts.')
    plan['context_id']=c.digest(plan)
    c.write(output/'plan.json', plan)
    return plan


class Runner(c.NativeRunner):
    def check(self):
        plan=copy.deepcopy(self.plan); identity=plan.pop('context_id')
        c.require(c.digest(plan)==identity, 'Calibration plan changed')
        for path, expected in plan['source_bindings'].items():
            c.require(c.sha(c.ROOT/path)==expected, 'Calibration source changed: '+path)
        for name, expected in plan['inputs'].items():
            c.require(c.sha(self.root/'inputs'/name)==expected, 'Calibration input changed: '+name)
        for tool in plan['tools'].values():
            c.require(c.sha(tool['path'])==tool['sha256'], 'Native tool changed')

    def run(self, args, log, *, expected=0, timeout=None):
        limits=self.plan['limits']
        remaining=limits['native_seconds']-sum(r['elapsed_seconds'] for r in self.receipts)
        c.require(len(self.receipts)<limits['commands'] and remaining>0, 'Calibration budget exhausted')
        return super().run(args, log, expected=expected, timeout=min(remaining, limits['command_seconds']))


def audit(root):
    """Check preserved raw traces and semantic self-checks without native jobs."""
    root=Path(root); plan=c.read(root/'plan.json')
    core_plan=copy.deepcopy(plan); identity=core_plan.pop('context_id')
    c.require(c.digest(core_plan)==identity, 'Calibration plan changed')
    for name, expected in plan['inputs'].items():
        c.require(c.sha(root/'inputs'/name)==expected, 'Frozen input changed')
    receipts=c.unseal(root/'commands.json')
    c.require(len(receipts)==8 and all(r['failure'] is None for r in receipts), 'Incomplete calibration')
    for receipt in receipts:
        c.require(c.sha(root/receipt['log'])==receipt['log_sha256'], 'Calibration log changed')
    symbols={r.split()[-1]:int(r.split()[0],16) for r in (root/'symbols.txt').read_text().splitlines() if len(r.split())==3}
    raw=c.read(root/'extended/simulation.json'); control=c.read(root/'stock/simulation.json')
    c.require(raw['passed'] and not raw['trapped'] and raw['words']==[0x49534146,len(plan['cases'])], 'Semantic self-check failed')
    c.require((raw['handshakes'],raw['valid_cycles'],raw['wait_cycles'])==(2,4,2), 'PCPI handshake mismatch')
    first_custom=next(i for i,r in enumerate(plan['cases']) if r['op']=='pcpi')
    c.require(control['trapped'] and not control['passed'] and control['last_pc']==symbols[f'probe_{first_custom}'], 'Stock core must trap at custom opcode')
    c.require(symbols['_program_end']<=4096, 'Calibration exceeds memory guard')
    observed=[]
    for i,row in enumerate(plan['cases']):
        pc=symbols[f'probe_{i}']; span=raw['spans'][str(pc)]
        c.require(span['count']==1 and span['min']==span['max']==span['cycles'], 'Unexpected calibration execution')
        expected=5 if row['op']=='pcpi' else 4+(row['immediate']//4+row['immediate']%4 if row['op'] in SHIFTS else 0)
        if row['op']!='pcpi':
            c.require(control['spans'][str(pc)]==span, 'Stock/extended ordinary instruction latency differs')
        observed.append(dict(index=i, op=row['op'], immediate=row['immediate'], cycles=span['cycles'], expected_cycles=expected))
    return dict(context_id=identity, cases=len(observed), rows=observed,
                rule_matches_all=all(r['cycles']==r['expected_cycles'] for r in observed),
                semantic_checks_passed=True, stock_trap_control_passed=True,
                program_and_bss_end=symbols['_program_end'], native_commands=len(receipts),
                native_command_seconds=sum(r['elapsed_seconds'] for r in receipts),
                application_labels_collected=0, hardware_synthesis_runs=0)


def collect(root):
    runner=Runner(root); root=runner.root; inputs=root/'inputs'
    c.require(not runner.receipts, 'Preserve a previous attempt; use a fresh directory')
    t={k:v['path'] for k,v in runner.plan['tools'].items()}
    runner.run([t['gcc'],'-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-nostartfiles','-Wl,--no-relax',
                '-Wl,-T,'+str(inputs/'soc_link.ld'),inputs/'firmware.S','-o',root/'firmware.elf'],root/'compile.log')
    runner.run([t['objcopy'],'-O','binary',root/'firmware.elf',root/'firmware.bin'],root/'objcopy.log')
    runner.run([t['objdump'],'-d',root/'firmware.elf'],root/'disassembly.txt')
    runner.run([t['nm'],'-n',root/'firmware.elf'],root/'symbols.txt')
    (root/'firmware.hex').write_text(c.memory_image((root/'firmware.bin').read_bytes()))
    core=(inputs/'picorv32.v').read_text()
    for old,new in (
        ('reg [63:0] count_cycle, count_instr;','reg [63:0] count_cycle; reg [63:0] count_instr /* verilator public_flat_rd */;'),
        ('reg [31:0] reg_pc, reg_next_pc, reg_op1, reg_op2, reg_out;',
         'reg [31:0] reg_pc /* verilator public_flat_rd */; reg [31:0] reg_next_pc, reg_op1, reg_op2, reg_out;')):
        c.require(core.count(old)==1, 'Pinned observation register changed'); core=core.replace(old,new)
    (root/'profile_core.v').write_text(core)
    top=(inputs/'soc_top.v').read_text().replace('.LATENCY(0)','.LATENCY(1)').replace('"firmware.hex"','"'+str(root/'firmware.hex')+'"')
    (root/'soc_top.v').write_text(top)
    for mode,mask in (('extended',1),('stock',0)):
        folder=root/mode; folder.mkdir()
        runner.run([t['verilator'],'--cc','--exe','--build','-j','2','-Wno-fatal','--top-module','soc_top',
                    '--Mdir',folder/'obj_dir',f'-GEXTENSION_MASK={mask}',root/'profile_core.v',inputs/'pcpi_single.v',
                    inputs/'candidate.v',root/'soc_top.v',inputs/'latency_sim.cpp'],folder/'build.log')
        runner.run([folder/'obj_dir/Vsoc_top'],folder/'simulation.json',expected=0 if mask else 6)
    report=audit(root); c.seal(root/'report.json',report)
    c.require(report['rule_matches_all'],'Calibration disagrees with the declared rule; preserve failure and do not apply it')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','collect','audit')); p.add_argument('--root',type=Path,required=True)
    p.add_argument('--reference-root',type=Path)
    args=p.parse_args()
    if args.command=='prepare':
        c.require(args.reference_root is not None, 'Reference context required'); result=prepare(args.reference_root,args.root)
        print({'context_id':result['context_id'],'cases':len(result['cases'])})
    else:
        result=collect(args.root) if args.command=='collect' else audit(args.root)
        print({k:v for k,v in result.items() if k!='rows'})


if __name__=='__main__':
    main()
