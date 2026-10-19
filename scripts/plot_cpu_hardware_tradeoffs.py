#!/usr/bin/env python3
"""Render the committed CRC32 integrated-SoC tradeoff; no hardware/ML jobs.

All timing-derived runtimes are modeled from RTL-simulated cycles. Fmax is a
routed nextpnr estimate, not measured board frequency/runtime. LUT4×runtime is
an explicitly derived resource-time proxy, not energy or total silicon area.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE_DIR=Path('results/2026-10-13-prospective/soc')
SOURCE_SHA256={
    'summary.json':'9512485685eee439e4b8758f5ce5f052f5a2fb396be00e06f191212cbc9c4229',
    'routing-summary.json':'ec498f1165e6b0e57bd6a3061cb7cf58e27e936bbe762995d541e2ea1c164062',
}
BASELINE='#637483';CUSTOM='#007F88';WORSE='#B24935';INK='#21313D';GRID='#E1E7EB'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def require(condition,message):
    if not condition:raise ValueError(message)
def positive(value): return type(value) in (int,float) and math.isfinite(value) and value>0


def derive_data(summary,routing):
    """Derive every plotted value from the two summaries; reject unmatched runs."""
    require(routing['device']=='iCE40HX8K' and routing['package']=='CT256','Wrong target')
    require(routing['top_module']==summary['configuration']['top']=='soc_top','Wrong integration boundary')
    require(routing['memory_boundary']=='onchip_initialized_memory','Closed synchronous-memory boundary required')
    require(routing['seeds']==[1,2,3] and routing['all_runs_passed'] is True,'All three declared seeds required')
    require(routing['configurations']==['baseline','custom'],'Both configurations required')
    clock=routing['target_frequency_mhz'];require(clock==12.,'Original common12MHz constraint required')
    measurements=summary['measurements'];cycles={}
    for name in ('baseline','custom'):
        m=measurements[name]
        require(type(m['cycles']) is int and m['cycles']>0 and m['self_check_passed'] is True,'Valid simulated cycles/selfchecks required')
        require(m['protocol_statistics']['fault']==0 and m['protocol_statistics']['partial_report_bits']==0,'Fault-free complete reports required')
        cycles[name]=m['cycles']
    require(measurements['baseline']['full_checksum']==measurements['custom']['full_checksum'] and
            measurements['baseline']['benchmark_result']==measurements['custom']['benchmark_result'],'Matched CRC outputs required')
    require(summary['controls']['source_wrapper_execution_identical_to_stock'] is True and
            summary['controls']['stock_on_extended_core_identical'] is True,'Original cycle controls required')
    require(all(measurements[n]['cycles']==cycles['baseline'] for n in ('source-control','stock-on-custom')),'Control cycles differ')
    synth={}
    for row in summary['synthesis']:
        require(row['configuration'] not in synth,'Duplicate synthesis configuration');synth[row['configuration']]=row
    require(all(name in synth for name in ('baseline','custom')),'Both synthesized configurations required')
    resources=[]
    for name,key in [('LUT4','lut4_count'),('Flip-flops','flip_flop_count'),('Carry cells','carry_count'),('BRAM blocks','memory_blocks')]:
        a,b=[synth[c][key] for c in ('baseline','custom')]
        require(type(a) is int and type(b) is int and a>0 and b>=0,'Invalid resource counts')
        resources.append({'resource':name,'source_key':key,'baseline':a,'custom':b,'delta':b-a,'ratio':b/a,'change_percent':100*(b/a-1)})
    for config in ('baseline','custom'):
        require(synth[config]['netlist_sha256']==routing['netlist_sha256'][config],'Synthesis/routing netlist identity differs')
        require(synth[config]['all_bram_clocks_use_top_clock'] is True,'Synchronous RAM timing boundary differs')
    runs={}
    for row in routing['runs']:
        key=(row['configuration'],row['seed'])
        require(key not in runs,'Duplicate routing configuration/seed')
        require(key[0] in ('baseline','custom') and key[1] in (1,2,3),'Unexpected routing configuration/seed')
        require(row['returncode']==0 and row['status']=='routed_and_internal_timing_passed' and
                row['internal_timing_pass'] is True and row['device_fits'] is True and row['all_io_constrained'] is True,
                'Incomplete routing/timing run')
        require(positive(row['limiting_internal_fmax_mhz']),'Invalid modeled Fmax');runs[key]=row
    require(set(runs)=={(c,s) for c in ('baseline','custom') for s in (1,2,3)},'All six matched routing runs required')
    lut_ratio=resources[0]['ratio'];runtime_cases=[];timing=[]
    for seed in (1,2,3):
        clocks={c:runs[c,seed]['limiting_internal_fmax_mhz'] for c in ('baseline','custom')}
        times={c:cycles[c]/(clocks[c]*1e6) for c in ('baseline','custom')}
        ratio=times['custom']/times['baseline']
        timing.append({'seed':seed,'baseline_fmax_mhz':clocks['baseline'],'custom_fmax_mhz':clocks['custom'],
                       'custom_over_baseline_fmax':clocks['custom']/clocks['baseline'],
                       'routing_report_sha256':{c:runs[c,seed]['report_sha256'] for c in ('baseline','custom')}})
        runtime_cases.append({'case':'seed'+str(seed),'label':'Seed '+str(seed),'clock_basis':'each configuration at its own modeled Fmax',
            'baseline_seconds':times['baseline'],'custom_seconds':times['custom'],'custom_over_baseline_runtime':ratio,
            'runtime_change_percent':100*(ratio-1),'baseline_over_custom_speedup':1/ratio,
            'lut4_times_runtime_ratio':lut_ratio*ratio,'lut4_times_runtime_change_percent':100*(lut_ratio*ratio-1)})
    times={c:cycles[c]/(clock*1e6) for c in ('baseline','custom')};ratio=cycles['custom']/cycles['baseline']
    runtime_cases.append({'case':'common12mhz','label':'Common12MHz','clock_basis':'both configurations at the same12MHz',
        'baseline_seconds':times['baseline'],'custom_seconds':times['custom'],'custom_over_baseline_runtime':ratio,
        'runtime_change_percent':100*(ratio-1),'baseline_over_custom_speedup':1/ratio,
        'lut4_times_runtime_ratio':lut_ratio*ratio,'lut4_times_runtime_change_percent':100*(lut_ratio*ratio-1)})
    require(summary['comparisons']['baseline_cycles']==cycles['baseline'] and
            summary['comparisons']['custom_cycles']==cycles['custom'],'Summary cycle comparison differs')
    require(math.isclose(summary['comparisons']['cycle_ratio'],cycles['baseline']/cycles['custom'],rel_tol=0,abs_tol=1e-14),'Recorded cycle ratio differs')
    require(summary['comparisons']['lut4_delta']==resources[0]['delta'],'Recorded LUT4 delta differs')
    return {'schema':'isaforge-crc32-cpu-hardware-tradeoff-data-v1','workload':'Source-modified full Embench CRC32,170 measured repetitions ×1,024 CRC updates',
        'boundary':'Closed PicoRV32 SoC with8KiB initialized synchronous on-chip memory; iCE40HX8K CT256',
        'resources':resources,'simulated_cycles':cycles,'custom_over_baseline_cycles':cycles['custom']/cycles['baseline'],
        'common_clock_mhz':clock,'timing_pairs':timing,'runtime_cases':runtime_cases,
        'derived_formulas':{'runtime_seconds':'simulated_cycles / (frequency_mhz * 1e6)',
            'runtime_ratio':'custom_runtime_seconds / baseline_runtime_seconds',
            'speedup':'baseline_runtime_seconds / custom_runtime_seconds',
            'lut4_times_runtime_ratio':'(custom_LUT4 / baseline_LUT4) * runtime_ratio'},
        'interpretation':{'cycles':'RTL simulation includes PCPI response latency, instruction execution and SoC integration; no further latency subtraction.',
            'frequency':'nextpnr routed internal timing model; no board-validated Fmax.',
            'runtime':'Derived timing model/common-clock calculation, not measured board runtime.',
            'proxy':'LUT4 count × runtime only; not energy, total die area, power or an optimization objective.',
            'seeds':'All three matched routing seeds shown; placement sensitivity, not confidence intervals or independent workload replications.',
            'external_io':'Reset/status external timing assumptions are not fully constrained; internal synchronous timing scope retained.'},
        'controls':{'source_control_cycles':measurements['source-control']['cycles'],'stock_on_custom_cycles':measurements['stock-on-custom']['cycles']}}


def actual_data(root=ROOT):
    root=Path(root).resolve();sources=[];docs={}
    for filename,expected in SOURCE_SHA256.items():
        p=root/SOURCE_DIR/filename;require(sha(p)==expected,'Committed CRC32 source hash differs: '+filename)
        docs[filename]=read(p);sources.append({'path':str(SOURCE_DIR/filename),'sha256':expected})
    data=derive_data(docs['summary.json'],docs['routing-summary.json']);data['sources']=sources
    return data


def render(data,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.titlesize':13,
        'axes.labelsize':10.5,'axes.spines.top':False,'axes.spines.right':False,
        'axes.axisbelow':True,'figure.facecolor':'white','savefig.facecolor':'white',
        'svg.fonttype':'none','svg.hashsalt':'isaforge-crc32-hardware-tradeoffs','pdf.fonttype':42})
    fig,axes=plt.subplots(2,2,figsize=(14.8,10.7))
    fig.subplots_adjust(left=.13,right=.96,top=.81,bottom=.16,wspace=.39,hspace=.55)
    fig.suptitle('CRC32: integrated hardware cost versus runtime',x=.035,y=.975,ha='left',fontsize=21,color=INK)
    fig.text(.035,.927,'Closed PicoRV32 SoC · iCE40HX8K · full source-modified benchmark · all three matched routing seeds',fontsize=11.5,color=INK)
    fig.text(.035,.888,f"RTL-simulated cycles: {data['simulated_cycles']['baseline']:,} baseline → {data['simulated_cycles']['custom']:,} custom ({100*(data['custom_over_baseline_cycles']-1):.2f}%) · latency and SoC integration included",fontsize=11,color=BASELINE)
    ax=axes[0,0];rs=data['resources']
    for i,r in enumerate(rs):
        ax.barh(i,r['change_percent'],height=.47,color=CUSTOM,zorder=3)
        if not r['change_percent']:ax.scatter([0],[i],color=CUSTOM,s=30,zorder=4)
        ax.text(1.025,i,f"{r['baseline']:,} → {r['custom']:,}",transform=ax.get_yaxis_transform(),ha='left',va='center',fontsize=10.5,color=INK)
        ax.text(r['change_percent']+.12,i+.03,f"{r['change_percent']:+.2f}%",va='center',fontsize=9.5,color=CUSTOM)
    ax.set_yticks(range(4),[r['resource'] for r in rs]);ax.invert_yaxis();ax.set_xlim(-.1,5.5)
    ax.set_xticks([0,1,2,3,4,5]);ax.xaxis.set_major_formatter(PercentFormatter(xmax=100,decimals=0))
    ax.grid(axis='x',color=GRID,linewidth=.7);ax.set_xlabel('Custom resource increase relative to baseline')
    ax.set_title('A   Exact synthesized resource counts',loc='left',pad=15)
    ax.text(1.025,1.025,'baseline → custom',transform=ax.transAxes,ha='left',fontsize=9,color=BASELINE)
    ax=axes[0,1]
    for i,row in enumerate(data['timing_pairs']):
        a,b=row['baseline_fmax_mhz'],row['custom_fmax_mhz']
        ax.plot([a,b],[i,i],color='#B9C6CD',linewidth=2,zorder=1)
        ax.scatter([a],[i],color=BASELINE,s=58,zorder=3,label='Baseline' if i==0 else None)
        ax.scatter([b],[i],color=CUSTOM,s=58,marker='D',zorder=3,label='Custom' if i==0 else None)
        ax.annotate(f'{a:.2f}',(a,i),xytext=(0,10),textcoords='offset points',ha='center',fontsize=9.5,color=BASELINE)
        ax.annotate(f'{b:.2f}',(b,i),xytext=(0,-18),textcoords='offset points',ha='center',fontsize=9.5,color=CUSTOM)
    ax.set_yticks(range(3),['Seed 1','Seed 2','Seed 3']);ax.set_ylim(2.5,-.5);ax.set_xlim(65.5,73.7)
    ax.grid(axis='x',color=GRID,linewidth=.7);ax.set_xlabel('Routed internal Fmax estimate (MHz)')
    ax.set_title('B   Routed frequency varies by seed',loc='left',pad=15)
    ax.legend(frameon=False,loc='upper right',bbox_to_anchor=(1.02,1.035),ncol=2,fontsize=9,handletextpad=.3,columnspacing=.8)
    cases=data['runtime_cases'];labels=['Seed 1','Seed 2','Seed 3','Common 12 MHz']
    for index,(key,title,xlim,xlabel) in enumerate([
        ('custom_over_baseline_runtime','C   Runtime derived from cycles ÷ clock',(.84,1.025),'Custom / baseline runtime; lower is better'),
        ('lut4_times_runtime_ratio','D   LUT4 × runtime: a derived proxy',(.87,1.075),'Custom / baseline LUT4 × runtime; lower is better')]):
        ax=axes[1,index]
        for i,row in enumerate(cases):
            ratio=row[key];color=WORSE if ratio>1 else CUSTOM
            ax.plot([1,ratio],[i,i],color='#CFD8DE',linewidth=2,zorder=1)
            ax.scatter([ratio],[i],color=color,s=64,marker='s' if i==3 else 'o',zorder=3)
            change=100*(ratio-1)
            ax.annotate(f'{ratio:.4f}  ({change:+.2f}%)',(ratio,i),xytext=(0,-17),textcoords='offset points',ha='center',fontsize=9.5,color=color)
        ax.axhline(2.5,color=GRID,linewidth=1,linestyle='--');ax.axvline(1,color=BASELINE,linewidth=1.1,linestyle=':')
        ax.set_yticks(range(4),labels);ax.set_ylim(3.55,-.48);ax.set_xlim(*xlim);ax.set_xlabel(xlabel)
        ax.grid(axis='x',color=GRID,linewidth=.7);ax.set_title(title,loc='left',pad=15)
        if index==0:
            common=cases[-1]
            ax.text(0,-.23,f"Seeds: each design at its own modeled Fmax.\nCommon clock: {common['baseline_seconds']:.3f} s baseline → {common['custom_seconds']:.3f} s custom.",transform=ax.transAxes,fontsize=9.5,color=BASELINE,va='top',linespacing=1.5)
        else:
            worse=sum(c['lut4_times_runtime_ratio']>1 for c in cases[:3])
            ax.text(0,-.23,f'Product increases in {worse} of 3 modeled-Fmax cases.\nProxy uses LUT4 only; not energy or total silicon area.',transform=ax.transAxes,fontsize=9.5,color=BASELINE,va='top',linespacing=1.5)
    fig.text(.035,.052,'Cycles from RTL simulation; clocks from nextpnr after routing. No physical board runtime, power or energy measurement.',fontsize=10,color=INK)
    fig.text(.035,.025,'Three seeds describe placement sensitivity; no confidence intervals. Full precision, formulas and source hashes: figure-data.json.',fontsize=9.5,color=BASELINE)
    stem=output/'crc32-hardware-tradeoffs'
    fig.savefig(stem.with_suffix('.png'),dpi=200,metadata={'Title':'CRC32 integrated hardware cost versus runtime'})
    fig.savefig(stem.with_suffix('.svg'),metadata={'Date':None,'Title':'CRC32 integrated hardware cost versus runtime'})
    fig.savefig(stem.with_suffix('.pdf'),metadata={'CreationDate':None,'ModDate':None,'Title':'CRC32 integrated hardware cost versus runtime','Subject':'Routed timing model and RTL-simulated cycles; LUT4-time proxy is not energy'})
    plt.close(fig)


def run(output,root=ROOT):
    output=Path(output).resolve();data=actual_data(root)
    output.mkdir(parents=True)
    write(output/'figure-data.json',data)
    render(data,output)
    caption=('CRC32 hardware tradeoffs for a closed PicoRV32 SoC on iCE40HX8K. '
        'A: exact synthesized resources, baseline to custom. B: all three matched routed internal Fmax estimates. '
        'C: simulated cycles divided by each design’s modeled Fmax, plus both designs at common12MHz. '
        'D: (custom/baseline LUT4) × (custom/baseline runtime), a resource-time diagnostic only; not energy or total silicon area. '
        'The product is worse for seeds1/2 and better for seed3; common-clock comparison is shown separately. '
        'PCPI latency and SoC integration are included in simulated cycles. Timing is modeled, not board-validated; no power/energy measurements or confidence intervals.\n')
    (output/'captions.md').write_text(caption)
    files=[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()]
    write(output/'figure-manifest.json',{'schema':'isaforge-cpu-hardware-tradeoff-figures-v1','sources':data['sources'],
        'plot_source':{'path':'scripts/plot_cpu_hardware_tradeoffs.py','sha256':sha(Path(__file__))},'files':files,
        'native_jobs':0,'model_jobs':0,'new_measurements':0})
    return {'status':'rendered','output':str(output),'matched_seeds':3,'figure_files':3,'runtime_cases':4}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'docs/figures/cpu-hardware-tradeoffs')
    p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args();print(json.dumps(run(args.output,args.root)))
if __name__=='__main__':main()
