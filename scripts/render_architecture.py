"""Render the README architecture diagram as editable SVG and a PNG preview."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets'
BLUE, GREEN, ORANGE = '#2453df', '#00876b', '#a84716'
INK, MUTED, LINE = '#142033', '#4e607a', '#687d99'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'isaforge-architecture'})
fig, ax = plt.subplots(figsize=(11, 13.2))
fig.patch.set_facecolor('white')
ax.set_xlim(0, 1100); ax.set_ylim(1320, 0); ax.axis('off')
fig.subplots_adjust(0, 0, 1, 1)


def text(x, y, label, size=14, color=INK, weight='normal', **kw):
    ax.text(x, y, label, fontsize=size, color=color, weight=weight, va='top', **kw)


def panel(y, h, title, subtitle, color, fill, edge):
    ax.add_patch(FancyBboxPatch((24,y),1052,h,boxstyle='round,pad=0,rounding_size=18',
                              linewidth=.85,edgecolor=edge,facecolor=fill))
    text(50,y+23,title,15,color,'bold')
    text(50,y+54,subtitle,12,MUTED)


def box(x,y,title,lines,edge,width=420,height=122):
    ax.add_patch(FancyBboxPatch((x,y),width,height,boxstyle='round,pad=0,rounding_size=12',
                              linewidth=.7,edgecolor=edge,facecolor='white'))
    text(x+20,y+17,title,14,weight='bold')
    for i,line in enumerate(lines):text(x+20,y+51+24*i,line,11.6,MUTED)


def arrow(points, color=LINE, dash=False):
    for a,b in zip(points[:-2],points[1:-1]):
        ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=1.3,ls='--' if dash else '-')
    ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=15,
                                linewidth=1.3,color=color,linestyle='--' if dash else '-'))


panel(24,414,'CANDIDATE DISCOVERY + MEASUREMENT',
      'Pinned software inputs · RV32 semantics · traceable hardware labels', BLUE,'#f0f6ff','#c8daff')
box(50,112,'Workload execution',['Embench C programs → GCC → Spike', 'Self-checks · instruction traces · pinned tools'],'#c8daff')
box(630,112,'Candidate extraction',['≤2 inputs · one output · 2–4 operations', 'Trace candidates + separate synthetic probe'],'#c8daff')
arrow([(480,173),(618,173)])
text(549,144,'Trace',11,MUTED,ha='center')
box(630,290,'RTL verification + synthesis',['Verilator vs RV32 integer oracle', 'Yosys → actual isolated iCE40 LUT4 count'],'#c8daff')
arrow([(840,244),(840,280)])
box(50,290,'Versioned circuit evidence',['713 development + 192 fresh probe formulas', 'Measured labels · logs · hashes · provenance'],'#c8daff')
arrow([(619,352),(481,352)])
text(550,319,'Verified labels',10.5,MUTED,ha='center')
arrow([(260,450),(260,527)],BLUE)
text(286,466,'Formula inputs + training labels',13,BLUE,'bold')
text(286,493,'Probe labels stay hidden until every model is frozen',11.5,MUTED)

panel(539,297,'LEARNING + CONTROLLED COMPARISON',
      'Predict isolated LUT4 resources · assess generalization and inference cost',GREEN,'#effbf6','#b1e6d0')
box(50,628,'Feature extraction + training',['Formula features or pre-ABC SOG graphs', 'Six predictors · identical training cohort'],'#b1e6d0')
box(630,628,'Frozen evaluation + reporting',['Program holdouts + unseen synthetic probe', 'MAE · RMSLE · MAPE · timing · figures'],'#b1e6d0')
arrow([(480,689),(618,689)],GREEN)
text(549,651,'Freeze',11,GREEN,ha='center',weight='bold')
text(50,780,'Evidence gate',11.5,GREEN,'bold')
text(198,780,'Same data + target · no test-set tuning · all failures retained',11.5,MUTED)

text(550,868,'SEPARATE PROCESSOR CASE STUDY',11,LINE,'bold',ha='center')
text(550,895,'Uses extracted CRC32 formulas; ML scores do not establish CPU speedup.',11.5,MUTED,ha='center')
panel(938,307,'RISC-V PROCESSOR + FPGA VALIDATION',
      'Two custom instructions integrated through PicoRV32 PCPI',ORANGE,'#fff8ef','#f1d1ae')
box(50,1027,'Complete CRC32 execution',['Baseline and extended SoC · same workload', 'Checksums · memory controls · cycle counts'],'#f1d1ae')
box(630,1027,'Matched FPGA implementation',['Whole-SoC LUT4 + BRAM · paired routing', 'Post-route timing estimates · three seeds'],'#f1d1ae')
arrow([(480,1088),(618,1088)],ORANGE)
text(549,1049,'Map + route',10.5,ORANGE,ha='center',weight='bold')
text(50,1182,'Measured: RTL cycles and mapped resources',11.4,ORANGE,'bold')
text(50,1208,'Estimated: cycle/Fmax runtime · no physical-board or energy measurement',11.4,MUTED)
text(50,1280,'ISAForge',12,INK,'bold')
text(1050,1280,'Reproducible evidence from source to result',11,MUTED,ha='right')
OUT.mkdir(parents=True,exist_ok=True)
for ext in ('svg','png'):
    fig.savefig(OUT/f'architecture.{ext}',dpi=180,facecolor='white',
                metadata={'Date': None} if ext == 'svg' else None)
plt.close(fig)
print(OUT/'architecture.svg')
