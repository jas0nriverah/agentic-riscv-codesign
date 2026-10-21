"""Plot recorded GP states; this script fits no models and runs no evaluations."""
from pathlib import Path
import argparse
import hashlib
import json
from statistics import NormalDist
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
output = parser.parse_args().output.resolve()
if output.exists():
    raise ValueError('Use a fresh figure output directory')
output.mkdir(parents=True)
path = ROOT/'metrics.json'
assert hashlib.sha256(path.read_bytes()).hexdigest() == Path(str(path)+'.sha256').read_text().strip()
metrics = json.loads(path.read_text())
sha = metrics['targets']['sha256']
names = ('00', '11', '22', '33', '44', '57')
assert len(sha['public_candidates']) == len(names)
labels = {row['candidate_id']: name for row, name in zip(sha['public_candidates'], names)}
colors = dict(zip(names, plt.get_cmap('tab10').colors))
markers = dict(zip(names, ('o', 'D', 's', '^', 'v', 'X')))
states = sorted((r for r in sha['paid_area_updates'] if r['area_cap'] == 64), key=lambda r:r['charged_before_query'])
assert [r['charged_before_query'] for r in states] == [0, 1, 2]
fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.3), sharex=True, sharey=True)
z = NormalDist().inv_cdf(.95)
for ax, state in zip(axes, states):
    ax.plot([0, 120], [0, 120], color='#9ca3af', linewidth=.9, label='_identity')
    ax.axvline(64, color='#64748b', linestyle='--', linewidth=.9)
    ax.axhline(64, color='#64748b', linestyle='--', linewidth=.9)
    for row in state['estimates']:
        name = labels[row['candidate_id']]
        ax.errorbar(row['actual_area_delta_lut4'], row['gp_area_mean'], yerr=z*row['gp_area_std'],
                    fmt=markers[name], color=colors[name], capsize=3, markersize=6,
                    markerfacecolor='white' if name == '00' else colors[name],
                    label='Candidate '+name, linewidth=1.1)
    count = state['charged_before_query']
    ax.set_title('Before target queries' if count == 0 else f"After {count} paid {'query' if count == 1 else 'queries'}")
    ax.set(xlim=(0, 115), ylim=(0, 115), xlabel='Measured added LUT4')
    ax.grid(alpha=.15)
axes[0].set_ylabel('Frozen GP predicted added LUT4')
handles, legend_labels = axes[0].get_legend_handles_labels()
fig.legend(handles, legend_labels, loc='lower center', bbox_to_anchor=(.5, .055), ncol=6, frameon=False, fontsize=8)
fig.suptitle('SHA256: paid measurements change predictions without making uncertainty reliable', fontsize=12)
fig.text(.5, .015, 'Bars: nominal 90% GP intervals, uncalibrated. Dashed lines: +64 LUT4 cap. Queried candidates removed; 00/11 initially overlap.', ha='center', fontsize=8)
fig.tight_layout(rect=(0, .16, 1, .91))
for suffix in ('png', 'svg'):
    fig.savefig(output/('area-confidence.'+suffix), dpi=180)
plt.close(fig)
