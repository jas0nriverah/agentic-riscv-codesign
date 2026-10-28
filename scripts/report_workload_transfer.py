"""Derive readable tables and figures from sealed transfer sensitivity; no fits."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isaforge import codesign as c

LABELS={'pairwise':'Pairwise XGBoost','raw_factorized':'Feasibility utility','merit':'Merit','calibrated_latency':'Analytic latency','frequency':'Frequency','exact_cache_latency':'Exact cache + latency','random':'Random (5 seeds)'}
SPLITS={'workload_only':'Ordinary workload holdout','workload_and_family':'Workload + formula-family holdout'}


def load_sealed(root):
    manifest=c.unseal(root/'manifest.json')
    for name,digest in manifest.items():
        c.require(c.sha(root/name)==digest,'Changed sealed input: '+name)
    return {n:c.unseal(root/(n+'.json')) for n in ('protocol','result','folds','grouped','runs')}


def report(source, old, output):
    source,old,output=map(lambda p:Path(p).resolve(),(source,old,output))
    c.require(not output.exists() and output.is_relative_to(ROOT),'Fresh local derived output required')
    raw=load_sealed(source);historical=load_sealed(old)
    result,folds=raw['result'],raw['folds'];macro=result['macro']
    oldrows=historical['result']['summary']
    agreement=[]
    for row in macro:
        if row['split']!='workload_and_family' or row['policy']=='exact_cache_latency':continue
        previous=next(r for r in oldrows if r['policy']==row['policy'] and r['budget']==row['budget'])
        difference=row['mean_cycle_reduction']-previous['mean_cycle_reduction']
        c.require(abs(difference)<1e-14,'Strict historical selection disagrees')
        agreement.append(dict(policy=row['policy'],budget=row['budget'],difference=difference))
    cache_stats=[];cohorts=[];examples=[]
    for kind in SPLITS:
        selected=[f for f in folds if f['split']==kind];records=[r for f in selected for r in f['cache']]
        cache_stats.append(dict(split=kind,target_attempts=len(records),context_known=sum(r['target_context_known'] for r in records),
            exact_match_attempts=sum(bool(r['exact_training_ids']) for r in records),compatible_hit_attempts=sum(r['hit'] for r in records),
            historically_infeasible_hits=sum(r['hit'] and r['historically_infeasible'] for r in records),
            workloads_with_hits=sum(any(r['hit'] for r in f['cache']) for f in selected),
            incompatible_exact_record_pairs=sum(r['incompatible_exact_records'] for r in records)))
        for f in selected:
            cohorts.append(dict(split=kind,workload=f['workload_group'],rows=len(f['training_ids']),groups=len(f['training_groups']),families=len(f['training_families']),
                excluded=len(f['family_excluded_ids']),training_seconds=f['available_training_seconds'],
                fit_seconds=f['timing']['rank_fit_seconds']+f['timing']['feasibility_fit_seconds'],
                hits=sum(r['hit'] for r in f['cache']),pool=len(f['cache'])))
            examples.extend(dict(workload=f['workload_group'],**r) for r in f['cache'] if r['hit'])
    output.mkdir(parents=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'pairwise':'#2563eb','raw_factorized':'#c2410c','merit':'#111827','calibrated_latency':'#16a34a','frequency':'#a16207','exact_cache_latency':'#9333ea','random':'#6b7280'}
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),sharey=True)
    for ax,(kind,title) in zip(axes,SPLITS.items()):
        for policy,label in LABELS.items():
            points=sorted([r for r in macro if r['split']==kind and r['policy']==policy],key=lambda r:r['budget'])
            ax.plot([r['budget'] for r in points],[100*r['mean_cycle_reduction'] for r in points],label=label,color=colors[policy],marker='o',linewidth=1.7,
                    linestyle='--' if policy in ('calibrated_latency','random','exact_cache_latency') else '-')
        ax.set(title=title,xlabel='Paid candidate attempts (effective min(B,N))',xticks=[1,2,3],xlim=(.9,3.1));ax.grid(alpha=.2)
    axes[0].set_ylabel('Mean verified cycle reduction (%) — 17 workloads')
    fig.suptitle('Consumed-data sensitivity: ordinary pairwise ties merit at B3',fontsize=13)
    handles,labels=axes[1].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=4,fontsize=9)
    fig.subplots_adjust(bottom=.24,top=.83,wspace=.09)
    fig.savefig(output/'selection.png',dpi=180);fig.savefig(output/'selection.svg');plt.close(fig)
    svg = output/'selection.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    lines=['# Workload transfer sensitivity — derived summary','',
        'Ordinary workload-held-out pairwise XGBoost **ties merit at B3: 1.8079% mean cycle reduction**. Under strict workload-and-family exclusion it reaches 1.7480%, below merit’s 1.8079%. The historical strict-family B3 comparison remains primary. No model is promoted; these are already consumed development data, with no new native measurement or estimator fit in this report.','',
        '![Both holdout comparisons](selection.png)','',
        'Every mean selection result averages 17 workload groups equally. Regret averages only 15 groups with complete oracles. Four unknown failures remain charged, and two censored workloads retain lower-bound references. Random uses five dependent seeds; other policies use fixed model seed zero. All target choices, including cache hits, pay actual verification and measurement costs.','',
        '## Selection and complete-oracle regret','',
        'Each cell is **cycle reduction % / regret percentage points**. Budgets are requested B1/B2/B3 with effective min(B,N).','']
    for kind,title in SPLITS.items():
        lines.extend(['### '+title,'','| Policy | B1 | B2 | B3 | B3 native seconds |','|---|---:|---:|---:|---:|'])
        for policy,label in LABELS.items():
            pts=[next(r for r in macro if (r['split'],r['policy'],r['budget'])==(kind,policy,b)) for b in (1,2,3)]
            cells=[f"{100*r['mean_cycle_reduction']:.4f} / {100*r['mean_regret']:.4f}" for r in pts]
            lines.append('| '+label+' | '+' | '.join(cells)+f" | {pts[-1]['mean_measurement_seconds']:.2f} |")
        lines.append('')
    lines.extend(['## Exact cache coverage','','Compatibility is fixed before fitting: actual hardware, compiler, linker/memory/clock and hardware code-generation/device/routing source hashes must match. Historical max area/minimum Fmax/all-device-fit summaries are observations, not bounds. ML receives the same success cohort; its existing features use mixed contexts while the cache conservatively accepts only compatible records.','',
        '| Split | Known contexts | Exact matches | Compatible hits | Hit workloads | Infeasible hits | Rejected exact record pairs |','|---|---:|---:|---:|---:|---:|---:|'])
    for s in cache_stats:
        lines.append(f"| {SPLITS[s['split']]} | {s['context_known']}/{s['target_attempts']} | {s['exact_match_attempts']}/{s['target_attempts']} | {s['compatible_hit_attempts']}/{s['target_attempts']} | {s['workloads_with_hits']}/17 | {s['historically_infeasible_hits']} | {s['incompatible_exact_record_pairs']} |")
    lines.extend(['','All 160 target contexts have sufficient provenance for a comparison; this does not mean all historical records are compatible. Ordinary holdout exposes 28 target attempts with an exact formula in training, but only eight have compatible historical records (5.0%). Strict exclusion has zero exact matches and zero hits, as asserted before fitting. The strict cache therefore equals analytic latency. No compatibility rule was broadened after scoring.','',
        '| Compatible example (target workload) | Exact formula | Historical area / Fmax | Fit | Training record IDs |','|---|---|---:|---|---|'])
    for r in examples:
        lines.append(f"| {r['workload']} | `{r['exact_formula']}` | {r['historical_max_area']} LUT4 / {r['historical_min_fmax']:.3f} MHz | {'historically infeasible' if r['historically_infeasible'] else 'historically feasible'} | "+', '.join('`'+i+'`' for i in r['compatible_training_ids'])+' |')
    lines.extend(['','## Training cohorts','','The strict split changes cohort size and composition. A split difference cannot identify a causal memorization effect. IDs, families, public predictions and complete orders remain in the sealed raw folds.','',
        '| Held-out workload | Ordinary rows / groups | Strict rows / groups | Additional family exclusions | Ordinary cache hits |','|---|---:|---:|---:|---:|'])
    for g in sorted({r['workload'] for r in cohorts}):
        a=next(r for r in cohorts if r['workload']==g and r['split']=='workload_only');b=next(r for r in cohorts if r['workload']==g and r['split']=='workload_and_family')
        lines.append(f"| {g} | {a['rows']} / {a['groups']} | {b['rows']} / {b['groups']} | {b['excluded']} | {a['hits']}/{a['pool']} |")
    lines.extend(['','## Paired uncertainty versus merit','','Difference and percentile 95% interval are percentage points of verified cycle reduction, bootstrapping whole workloads. Positive favors the listed policy; this is not a superiority test on untouched workloads.','',
        '| Split | Policy | Budget | Difference (pp) | 95% interval (pp) | Wins / ties / losses |','|---|---|---:|---:|---:|---:|'])
    for r in result['paired_vs_merit']:
        if r['policy']=='merit':continue
        lines.append(f"| {SPLITS[r['split']]} | {LABELS[r['policy']]} | {r['budget']} | {100*r['mean']:.4f} | [{100*r['lower_95']:.4f}, {100*r['upper_95']:.4f}] | {r['wins']} / {r['ties']} / {r['losses']} |")
    lines.extend(['','## Historical agreement and next improvement','','All 18 overlapping strict-split selection macro values (six existing policies × three budgets) reproduce the previous nested-calibration diagnostic’s uncalibrated controls to numerical tolerance below 1e-14. This report changes no historical result. The new cache is an additional comparator.','',
        'The evidence directs the next model improvement toward feasibility and useful ordering under strict transfer: pairwise still trails merit at strict B3, feasibility utility trails both, and eight compatible cache hits are too sparse to explain the full policy difference. Preserve operand order and constants in future structural evidence, inspect existing feasibility misses and cohort support, then freeze one bounded change against an untouched workload with matched controls. These are research directions, not demonstrated improvements. Do not tune repeatedly on this consumed sensitivity or infer that the ordinary/strict gap proves memorization.','',
        '## Reproduction','',f'Raw sealed source: `{source.relative_to(ROOT)}`. Historical comparison: `{old.relative_to(ROOT)}`. This generator authenticates both manifests, reads existing predictions/results and creates tables/plots only.','',
        '```sh',f'.venv/bin/python scripts/report_workload_transfer.py --source {source.relative_to(ROOT)} --historical {old.relative_to(ROOT)} --output reports/2026-10-28-workload-transfer-summary-r2','```',''])
    (output/'README.md').write_text('\n'.join(lines))
    c.seal(output/'summary.json',dict(raw_manifest_sha256=c.sha(source/'manifest.json'),historical_manifest_sha256=c.sha(old/'manifest.json'),reporter_sha256=c.sha(Path(__file__)),
        cache_coverage=cache_stats,cohorts=cohorts,compatible_examples=examples,historical_strict_agreement=agreement,macro=macro,paired_vs_merit=result['paired_vs_merit']))
    c.seal(output/'manifest.json',{p.name:c.sha(p) for p in output.iterdir() if p.is_file()})
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'reports/2026-10-28-workload-transfer-sensitivity-r1')
    p.add_argument('--historical',type=Path,default=ROOT/'reports/2026-10-28-grouped-feasibility-calibration-r1')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(report(a.source,a.historical,a.output))
