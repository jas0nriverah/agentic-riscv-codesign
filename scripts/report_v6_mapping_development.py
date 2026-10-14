#!/usr/bin/env python3
"""Plot the fixed mapping-feature development ablation and all strata."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
data = json.loads((args.root/'summary.json').read_text())
args.output.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                     'axes.spines.top':False,'axes.spines.right':False,
                     'pdf.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'isaforge-v6-mapping-development'})
fig, axes = plt.subplots(1,2,figsize=(12.4,5.5),layout='constrained',gridspec_kw={'width_ratios':[1,1.4]})
views = ('dual_graph','dual_graph_plus_mapping')
labels = ('Dual graph\n194 features','Dual graph + cuts/reuse\n217 features')
for seed in sorted(data['scores'][views[0]]):
    values = [data['scores'][v][seed]['macro_stratum_mae_lut4'] for v in views]
    axes[0].plot([0,1],values,'o-',color='#86a5b6',alpha=.7,lw=1.2,ms=4)
means = [data['by_view'][v]['macro_mae_mean'] for v in views]
sd = [data['by_view'][v]['macro_mae_sample_sd'] for v in views]
axes[0].errorbar([0,1],means,yerr=sd,fmt='s',color='#145b83',capsize=6,ms=7)
for i,m in enumerate(means):
    axes[0].annotate(f'{m:.3f}',(i,m),xytext=(14,0),textcoords='offset points',va='center',weight='bold')
axes[0].set_xticks([0,1],labels);axes[0].set_xlim(-.25,1.55)
axes[0].set_ylabel('Fitting-only OOF macro-stratum MAE (LUT4)')
axes[0].set_title('A  |  Three fixed seeds, matched controls',loc='left')
axes[0].grid(axis='y',alpha=.15)
delta=data['paired_differences']['per_stratum_mean_difference']
names=list(delta);values=[delta[n] for n in names]
axes[1].barh(range(len(names)),values,color=['#237c83' if x<0 else '#ba6a37' for x in values])
axes[1].set_yticks(range(len(names)),[n.replace('_',' ').capitalize() for n in names]);axes[1].invert_yaxis()
axes[1].axvline(0,color='#344e60',lw=.8)
axes[1].set_xlim(min(values)*1.25,max(values)*1.65)
for i,v in enumerate(values):
    axes[1].text(v+(-.025 if v<0 else .025),i,f'{v:+.3f}',va='center',ha='right' if v<0 else 'left',fontsize=9)
axes[1].set_xlabel('MAE change: added descriptors − dual graph (LUT4)')
axes[1].set_title('B  |  Every stratum; negative favors new features',loc='left')
axes[1].grid(axis='x',alpha=.15);axes[1].set_axisbelow(True)
fig.suptitle('Mapping-aware features: development evidence only',fontsize=15,weight='bold')
fig.text(.02,-.035,'Same 1,665 fitting formulas, five structural folds, 300-tree configuration; 30 fits. Lines pair seeds; error bars are sample SD, not confidence intervals.\nAll eight nonmultiplication strata improve on average; multiplication worsens. Cut budgets truncate 929 graphs; all remain included. Fresh validation is required.',fontsize=9)
for ext in ('png','svg','pdf'):
    metadata={'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else {}
    fig.savefig(args.output/f'mapping-development.{ext}',dpi=250,bbox_inches='tight',metadata=metadata)
plt.close(fig)
(args.output/'mapping-development-data.json').write_text(json.dumps(data,indent=2)+'\n')
(args.output/'mapping-development-provenance.json').write_text(json.dumps({
    'summary_sha256':hashlib.sha256((args.root/'summary.json').read_bytes()).hexdigest(),
    'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope':'Development only. No calibration or independent test score.'},indent=2)+'\n')
print(args.output)
