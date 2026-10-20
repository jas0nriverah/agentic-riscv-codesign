import argparse
import csv
import json
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.transforms import IdentityTransform  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

# Charts for hw/README.md, drawn only from the committed result files under hw/engine/results.
# make hw-plots writes them to hw/docs/img, which is committed so GitHub can show them.
SWEEP = "hw/engine/results/sweep-top3.csv"
FREQ = "hw/engine/results/frequency-top3.json"
PROGRAMS = ["aha-mont64", "crc32", "edn", "huffbench", "matmult-int", "nettle-aes", "nettle-sha256", "wikisort"]

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e5e4e0"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def thousands(x, _):
    return f"{x / 1000:,.0f}k" if x else "0"


def millions(x, _):
    return f"{x / 1e6:.1f}M" if x else "0"


def placeLabels(ax, points):
    # labels are laid out in pixels after the layout is final: each goes to the right of its point,
    # moves up a row while it would overlap one already placed, flips to the left side when it would
    # leave the plot, and gets a thin leader back to its point once it has moved
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    identity = IdentityTransform()
    axesBox = ax.get_window_extent(renderer)
    placed = []
    for x, y, text in sorted(points, key=lambda p: (p[1], p[0])):
        px, py = ax.transData.transform((x, y))
        for row in range(60):
            dy = row * 17
            for side in (1, -1):
                label = ax.text(px + side * 10, py + dy, text, transform=identity, fontsize=8.5, color=INK,
                                va="center", ha="left" if side > 0 else "right", zorder=5)
                box = label.get_window_extent(renderer)
                if box.x0 >= axesBox.x0 and box.x1 <= axesBox.x1 and \
                        not any(box.expanded(1.08, 1.25).overlaps(b) for b in placed):
                    break
                label.remove()
                label = None
            if label:
                break
        if label is None:
            raise SystemExit(f"could not place the label {text!r}")
        placed.append(box)
        if dy:
            inv = ax.transData.inverted()
            lx, ly = inv.transform((box.x0 - 2 if side > 0 else box.x1 + 2, (box.y0 + box.y1) / 2))
            ax.plot([x, lx], [y, ly], color=INK2, lw=0.6, zorder=2)


def sweepScatter(out):
    rows = list(csv.DictReader(open(SWEEP)))
    groups = defaultdict(list)
    for r in rows:
        groups[(int(r["instret_delta"]), int(r["cycle_delta"]))].append((r["program"], int(r["rank"])))
    ratios = [float(r["cycles_per_instr_saved"]) for r in rows if r["cycles_per_instr_saved"]]

    fig, ax = plt.subplots(figsize=(9.5, 6.2), dpi=150)
    xs, ys = zip(*groups)
    xmax, ymax = max(xs) * 1.12, max(ys) * 1.12
    for ratio in (1, 4, 12):
        # from the origin, clipped at the top or right edge of the plot
        xEnd = min(xmax, ymax / ratio)
        ax.plot([0, xEnd], [0, xEnd * ratio], color=INK2, lw=0.8, ls=(0, (4, 3)), zorder=1)
        atTop = xEnd * ratio >= ymax
        ax.annotate(f"{ratio} cycle{'s' if ratio > 1 else ''} per instruction", (xEnd, xEnd * ratio),
                    xytext=(-6, -4 if atTop else 4), textcoords="offset points", fontsize=8.5, color=INK2,
                    ha="right", va="top" if atTop else "bottom",
                    bbox=dict(boxstyle="square,pad=0.15", facecolor=SURFACE, edgecolor="none"))
    ax.scatter(xs, ys, s=64, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3)

    labels = []
    for (x, y), members in groups.items():
        byProgram = defaultdict(list)
        for program, rank in members:
            byProgram[program].append(rank)
        parts = [f"{p} #{'/#'.join(map(str, sorted(r)))}" for p, r in byProgram.items()]
        text = ", ".join(parts) if (x or y) else "fused nothing: " + ", ".join(parts)
        labels.append((x, y, text))
    ax.set_xlim(-0.012 * xmax, xmax)
    ax.set_ylim(-0.012 * ymax, ymax)

    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.yaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_xlabel("instructions saved in the source program's measured window (count)")
    ax.set_ylabel("cycles saved in the same window (count)")
    ax.set_title(f"Cycles saved per instruction saved ranges from {min(ratios):.1f} to {max(ratios):.1f}", pad=26)
    ax.text(0, 1.02, f"{len(rows)} rows from 21 single-candidate cores: each program's top 3 candidates, each measured "
            "alone on its own core; 5 rows fused nothing", transform=ax.transAxes, fontsize=9, color=INK2)
    fig.tight_layout()
    placeLabels(ax, labels)
    fig.savefig(os.path.join(out, "sweep-cycles-vs-instructions.png"))
    plt.close(fig)


def frequencyBars(out):
    result = json.load(open(FREQ))
    rows = {r["benchmark"]: r for r in result["rows"]}
    cyclesOnly = [rows[p]["speedup_cycles_only"] for p in PROGRAMS]
    ruled = [rows[p]["speedup"] for p in PROGRAMS]
    below = sum(v < 1 for v in ruled)
    luts, fmax = result["luts"]["delta"], result["fmax_mhz"]["median"]

    fig, ax = plt.subplots(figsize=(9.5, 5.4), dpi=150)
    width, centers = 0.38, range(len(PROGRAMS))
    bars = [ax.bar([c - width / 2 - 0.01 for c in centers], [v - 1 for v in cyclesOnly], width, bottom=1.0,
                   color=BLUE, label="cycles only"),
            ax.bar([c + width / 2 + 0.01 for c in centers], [v - 1 for v in ruled], width, bottom=1.0,
                   color=ORANGE, label="with T_fused = max(T_base, T_measured)")]
    ax.axhline(1.0, color=INK2, lw=0.8, zorder=1)
    for group, values in zip(bars, (cyclesOnly, ruled)):
        for bar, value in zip(group, values):
            ax.annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, 2 if value >= 1 else -2), textcoords="offset points", fontsize=7.5,
                        color=INK, ha="center", va="bottom" if value >= 1 else "top")
    ax.set_ylim(0.9, 1.22)
    ax.set_xticks(list(centers), PROGRAMS, rotation=20, ha="right")
    ax.set_ylabel("speedup over the stock core (ratio; bars start at 1.0 = stock)")
    ax.set_xlabel("program")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", frameon=False, fontsize=9)
    ax.set_title(f"Frequency-ranked core: the slower clock leaves {below} of {len(PROGRAMS)} programs below stock", pad=26)
    ax.text(0, 1.02, f"one core with the top 3 non-conflicting formulas by total finder saved; {luts:+d} LUT4, "
            f"Fmax median {fmax:.2f} MHz vs. 61.48 baseline", transform=ax.transAxes, fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "frequency-top3-speedup.png"))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="hw/docs/img")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    sweepScatter(args.out)
    frequencyBars(args.out)
    print(f"wrote {args.out}/sweep-cycles-vs-instructions.png and frequency-top3-speedup.png")


if __name__ == "__main__":
    main()
