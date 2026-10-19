#!/usr/bin/env python3
"""Replay declared postmeasurement policies on all authenticated V10d alternatives."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_v10d_timing as audit_module
import select_v10d_implementations as selector


def hashed(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def policies(audit):
    candidates = selector.alternatives_from_audit(audit)
    result = {}
    for name in ('unconstrained', 'common_12mhz', 'original_worst_case_limits'):
        rows = []
        for pair, alternatives in candidates:
            original = next(x for x in alternatives if x['arm'] == 'original')
            if name == 'original_worst_case_limits':
                budgets = {cap: max(r[key] for r in original['observations']) for cap, key in selector.CAPS.items()}
                budgets['min_fmax_mhz'] = min(r['fmax_mhz'] for r in original['observations'])
            else:
                budgets = {'min_fmax_mhz': 12} if name == 'common_12mhz' else {}
            rows.append({**pair, 'budgets': budgets, **selector.choose(alternatives, budgets)})
        result[name] = {'formulas': rows, 'counts': {
            'formulas': len(rows),
            'chosen_original': sum(r['chosen_arm'] == 'original' for r in rows),
            'chosen_csd': sum(r['chosen_arm'] == 'csd' for r in rows),
            'no_feasible_implementation': sum(r['chosen_arm'] is None for r in rows),
            'both_arms_feasible': sum(all(a['feasible'] for a in r['alternatives']) for r in rows),
            'single_arm_pareto_front': sum(len(r['pareto_front_all']) == 1 for r in rows),
            'two_arm_pareto_front': sum(len(r['pareto_front_all']) == 2 for r in rows),
            'csd_violated_constraints_by_formula': dict(Counter(v['budget'] for r in rows for a in r['alternatives'] if a['arm'] == 'csd' for v in a['violations'])),
        }}
    return result


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
                         'svg.hashsalt': 'isaforge-measured-selection', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1, 1.25], 'wspace': .35})
    fig.subplots_adjust(left=.08, right=.97, top=.78, bottom=.22)
    fig.suptitle('Implementation choices change when hardware costs are constrained', x=.03, y=.98, ha='left', fontsize=17)
    fig.text(.03, .90, 'Complete 32-formula development cohort · measured original/CSD alternatives · every constraint checked across three seeds', fontsize=10)
    names=list(data['policies'])
    labels=['No explicit caps', '12 MHz only', 'Original worst-case limits']
    original=[data['policies'][n]['counts']['chosen_original'] for n in names]
    csd=[data['policies'][n]['counts']['chosen_csd'] for n in names]
    axes[0].barh(range(3),csd,color='#167d8d',label='Choose CSD')
    axes[0].barh(range(3),original,left=csd,color='#8293ac',label='Retain original')
    for i,(c,o) in enumerate(zip(csd,original)):
        if c:axes[0].text(c/2,i,str(c),ha='center',va='center',color='white',fontweight='bold')
        if o:axes[0].text(c+o/2,i,str(o),ha='center',va='center',color='white',fontweight='bold')
    axes[0].set_yticks(range(3),labels);axes[0].invert_yaxis();axes[0].set_xlim(0,32);axes[0].set_xlabel('Formula count');axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.18),ncol=2,frameon=False)
    rows=data['policies']['original_worst_case_limits']['formulas']
    for arm,color,label in [('csd','#167d8d','CSD satisfies original limits'),('original','#8293ac','Original retained')]:
        selected=[r for r in rows if r['chosen_arm']==arm]
        x=[];y=[]
        for r in selected:
            a={a['arm']:a for a in r['alternatives']}
            x.append(a['csd']['max_resources']['carry']-a['original']['max_resources']['carry'])
            y.append(r['csd_worst_minus_original_period_ns'])
        axes[1].scatter(x,y,c=color,s=50,label=label,edgecolors='white',linewidths=.5)
    axes[1].axvline(0,color='#8997a4',lw=1);axes[1].axhline(0,color='#8997a4',lw=1);axes[1].grid(alpha=.15)
    axes[1].set_xlabel('CSD − original carry cells');axes[1].set_ylabel('Worst observed period: CSD − original (ns)')
    axes[1].legend(loc='lower left',frameon=False,fontsize=9)
    fig.text(.03,.08,'Original limits cap each resource at its original maximum and require the original minimum Fmax.\nThis is a postmeasurement lookup, not learned selection or a CPU budget. All 64 arms / 192 observations are retained; 72 path attributions remain unknown.',fontsize=10)
    for extension in ('png','svg','pdf'):
        fig.savefig(output/('v10d-constrained-selection.'+extension),dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def run(root, output, skip_figures=False):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.exists(): raise ValueError('Fresh output directory required')
    sources=[Path(__file__).resolve(),Path(selector.__file__).resolve(),Path(audit_module.__file__).resolve(),
             ROOT/'docs/v10d-selection-policy.md',ROOT/'tests/test_select_v10d_implementations.py']
    before=[hashed(p) for p in sources]
    audit=audit_module.run(root)
    if audit['status']!='pass' or not audit['complete'] or audit['failures']:raise ValueError('Complete authenticated raw evidence required')
    data={'schema':'isaforge-v10d-declared-policy-replay-v1','scope':'Postmeasurement development; no ML, CPU/board/power/generalization or measurement-saving claim.',
          'objective':list(selector.OBJECTIVE),'policies':policies(audit),
          'audit_result_canonical_sha256':selector.data_sha(audit),
          'audit_counts':{k:audit[k] for k in ('archive_members_verified','mappings_recounted','sequential_transactions_checked','routes_verified','path_classification_counts')},
          'native_jobs_run':0,'model_fits':0,'labels_rewritten':0}
    if [hashed(p) for p in sources]!=before:raise ValueError('Analysis sources changed during replay')
    output.mkdir(parents=True)
    write(output/'policy-results.json',data)
    if not skip_figures:render(data,output)
    write(output/'manifest.json',{'schema':'isaforge-v10d-policy-replay-manifest-v1','sources':before,
        'raw_preparation_sha256':audit['preparation_sha256'],'raw_completion_sha256':audit['completion_sha256'],
        'raw_archive_sha256':audit['archive_sha256'],'files':[hashed(p) for p in sorted(output.iterdir()) if p.is_file()]})
    return {name:policy['counts'] for name,policy in data['policies'].items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--skip-figures',action='store_true')
    args=parser.parse_args();print(json.dumps(run(args.root,args.output,args.skip_figures),indent=2))
