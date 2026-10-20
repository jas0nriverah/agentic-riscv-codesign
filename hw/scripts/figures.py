import argparse
import csv
import os
from collections import defaultdict
from xml.sax.saxutils import escape

# Figures for the root README, written as SVG in a light and a dark variant so GitHub can
# swap them by theme (<picture> with prefers-color-scheme). Every plotted number comes from a
# committed CSV under hw/engine/results. Standard library only; `make hw-figures` runs it.
SWEEP = "hw/engine/results/sweep-top3.csv"
FREQ = "hw/engine/results/frequency-top3.csv"
PROGRAMS = ["aha-mont64", "crc32", "edn", "huffbench", "matmult-int", "nettle-aes", "nettle-sha256", "wikisort"]
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

# GitHub's own page surfaces, so a figure blends in; series colors from a CVD-validated palette
THEMES = {
    "light": {"bg": "#ffffff", "ink": "#1f2328", "muted": "#656d76", "line": "#d0d7de", "grid": "#eaeef2",
              "box": "#f6f8fa", "blue": "#2a78d6", "orange": "#eb6834", "onblue": "#ffffff"},
    "dark": {"bg": "#0d1117", "ink": "#e6edf3", "muted": "#8b949e", "line": "#30363d", "grid": "#21262d",
             "box": "#161b22", "blue": "#3987e5", "orange": "#d95926", "onblue": "#ffffff"},
}


def width(text, size):
    # a safe estimate for the system sans-serif stacks GitHub readers have
    return 0.56 * size * len(text)


class Svg:
    def __init__(self, w, h, theme):
        self.w, self.h, self.t = w, h, theme
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                      f'font-family="{FONT}">', f'<rect width="{w}" height="{h}" fill="{theme["bg"]}"/>']

    def text(self, x, y, s, size=13, color=None, anchor="start", weight="normal", baseline="middle", halo=False):
        ring = f' paint-order="stroke" stroke="{self.t["bg"]}" stroke-width="3" stroke-linejoin="round"' if halo else ""
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color or self.t["ink"]}" '
                          f'text-anchor="{anchor}" font-weight="{weight}" dominant-baseline="{baseline}"{ring}>'
                          f'{escape(s)}</text>')

    def lines(self, x, y, rows, size=13, color=None, anchor="start", weight="normal", gap=1.35):
        # several lines centered vertically on y
        top = y - (len(rows) - 1) * size * gap / 2
        for i, row in enumerate(rows):
            self.text(x, top + i * size * gap, row, size, color, anchor, weight)

    def box(self, x, y, w, h, rows, fill=None, stroke=None, color=None, size=13, weight="normal", r=6):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or self.t["box"]}" '
                          f'stroke="{stroke or self.t["line"]}" stroke-width="1.2"/>')
        self.lines(x + w / 2, y + h / 2, rows, size, color, "middle", weight)

    def arrow(self, x1, y1, x2, y2, color=None):
        c = color or self.t["muted"]
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" '
                          f'stroke-width="1.5" marker-end="url(#head)"/>')

    def line(self, x1, y1, x2, y2, color=None, w=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                          f'stroke="{color or self.t["line"]}" stroke-width="{w}"{d}/>')

    def rect(self, x, y, w, h, fill, rx=0):
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"/>')

    def dot(self, x, y, r, fill):
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{self.t["bg"]}" '
                          f'stroke-width="1.5"/>')

    def save(self, path):
        head = (f'<defs><marker id="head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" '
                f'markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill="{self.t["muted"]}"/></marker></defs>')
        with open(path, "w") as f:
            f.write("\n".join(self.parts[:2] + [head] + self.parts[2:] + ["</svg>", ""]))


# --- 1. the team pipeline, with the hardware stage highlighted

def pipeline(theme, path):
    t = THEMES[theme]
    stages = [
        (["Embench programs", "benchmarks/embench, 8 programs"], False),
        (["Spike", "commit log → src/tracing.py"], False),
        (["Candidate finder", "src/candidates.py"], False),
        (["Selection", "frequency ranking or ML-guided"], False),
        (["Hardware measurement (hw/)", "PicoRV32 + PCPI unit, Verilator, Yosys, nextpnr"], True),
        (["ML side / selection", "rows feed the next round"], False),
    ]
    carries = [
        ["ELF per program", "-march=rv32im -mabi=ilp32 -O2, main's linker script"],
        ["trace .jsonl", "one line per retired instruction"],
        ["candidates JSON", "formula, size, runs, places, saved"],
        ["selected formulas", "1 to 3 per core"],
        ["measurement rows", "candidate_id, cycles, periods, LUTs, speedup"],
    ]
    bw, bh, gap, x0, y0 = 330, 52, 46, 40, 24
    s = Svg(720, y0 + len(stages) * bh + (len(stages) - 1) * gap + 24, t)
    for i, (rows, hot) in enumerate(stages):
        y = y0 + i * (bh + gap)
        if hot:
            s.box(x0, y, bw, bh, [rows[0]], fill=t["blue"], stroke=t["blue"], color=t["onblue"], weight="bold", size=14)
            s.text(x0 + bw / 2, y + bh - 12, rows[1], 11, t["onblue"], "middle")
        else:
            s.box(x0, y, bw, bh, [rows[0]], weight="bold", size=14)
            s.text(x0 + bw / 2, y + bh - 12, rows[1], 11, t["muted"], "middle")
        if i < len(carries):
            s.arrow(x0 + bw / 2, y + bh + 2, x0 + bw / 2, y + bh + gap - 3)
            s.text(x0 + bw / 2 + 16, y + bh + gap / 2 - 8, carries[i][0], 13, t["ink"], weight="bold")
            s.text(x0 + bw / 2 + 16, y + bh + gap / 2 + 9, carries[i][1], 12, t["muted"])
    s.save(path)


# --- 2. one measurement end to end: two lanes that meet at the checks

def measurement(theme, path):
    t = THEMES[theme]
    hw = [["candidate formula"], ["hw/isaforge/rtl.py → unit Verilog"],
          ["unit in core_top via PCPI", "custom-0, funct7=2, funct3=slot"], ["Yosys synth_ice40"],
          ["nextpnr-ice40", "frozen PCF, seeds 1–10"], ["LUT4 count; Fmax median, min, max"]]
    sw = [["program .s", "main's flags, stopped at assembly"], ["rewriter: dependent chain → .insn"],
          ["ELF", "hw/sw/startup.S, main's linker script"], ["Verilator run on the modified core"],
          ["cycles in the window, instret"]]
    bw, bh, gap, top = 380, 46, 26, 54
    lx, rx = 40, 460
    s = Svg(880, top + 6 * (bh + gap) + 90 + 30 + 54 + 30, t)
    s.text(lx + bw / 2, 26, "Hardware lane", 14, t["ink"], "middle", "bold")
    s.text(rx + bw / 2, 26, "Software lane", 14, t["ink"], "middle", "bold")
    for x, lane in ((lx, hw), (rx, sw)):
        for i, rows in enumerate(lane):
            y = top + i * (bh + gap)
            s.box(x, y, bw, bh, rows, size=13 if len(rows) == 1 else 12)
            if i < len(lane) - 1:
                s.arrow(x + bw / 2, y + bh + 2, x + bw / 2, y + bh + gap - 3)
    yChecks = top + 6 * (bh + gap) + 10
    for x, n in ((lx, len(hw)), (rx, len(sw))):
        yEnd = top + (n - 1) * (bh + gap) + bh
        s.line(x + bw / 2, yEnd + 2, x + bw / 2, yChecks - 14, t["muted"], 1.5)
    s.line(lx + bw / 2, yChecks - 14, rx + bw / 2, yChecks - 14, t["muted"], 1.5)
    s.arrow(440, yChecks - 14, 440, yChecks - 3)
    s.box(lx, yChecks, rx + bw - lx, 90,
          ["checks, any failure fails the build",
           "verify_benchmark passes  ·  stock programs unchanged on the modified core",
           "instret delta = Σ (size − 1) × runs over fused sites  ·  critical-path check"], size=13)
    s.arrow(440, yChecks + 92, 440, yChecks + 90 + 30 - 3)
    s.box(lx, yChecks + 120, rx + bw - lx, 54,
          ["measurement row",
           "candidate_id, baseline and candidate cycles, periods, luts, speedup, speedup_cycles_only"],
          fill=t["blue"], stroke=t["blue"], color=t["onblue"], size=13)
    s.save(path)


# --- 3. the sweep: cycles saved against instructions saved

def sweepScatter(theme, path):
    t = THEMES[theme]
    rows = list(csv.DictReader(open(SWEEP)))
    groups = defaultdict(list)
    for r in rows:
        groups[(int(r["instret_delta"]), int(r["cycle_delta"]))].append((r["program"], int(r["rank"])))
    ratios = [float(r["cycles_per_instr_saved"]) for r in rows if r["cycles_per_instr_saved"]]

    W, H, left, right, top, bottom = 880, 560, 72, 24, 64, 56
    pw, ph = W - left - right, H - top - bottom
    xmax, ymax = max(x for x, _ in groups) * 1.14, max(y for _, y in groups) * 1.1
    s = Svg(W, H, t)
    X = lambda v: left + pw * v / xmax
    Y = lambda v: top + ph - ph * v / ymax
    s.text(left, 22, f"Cycles saved per instruction saved ranges from {min(ratios):.1f} to {max(ratios):.1f}",
           16, t["ink"], weight="bold")
    s.text(left, 44, f"{len(rows)} rows from 21 single-candidate cores: each program's top 3 candidates, "
           "each measured alone; 5 rows fused nothing", 12, t["muted"])
    # grid and axes in counts, thousands on x and millions on y
    for v in range(0, int(xmax), 100_000):
        s.line(X(v), top, X(v), top + ph, t["grid"])
        s.text(X(v), top + ph + 16, f"{v // 1000}k" if v else "0", 12, t["muted"], "middle")
    for v in range(0, int(ymax), 500_000):
        s.line(left, Y(v), left + pw, Y(v), t["grid"])
        s.text(left - 8, Y(v), f"{v / 1e6:.1f}M" if v else "0", 12, t["muted"], "end")
    s.line(left, top + ph, left + pw, top + ph, t["line"])
    s.line(left, top, left, top + ph, t["line"])
    s.text(left + pw / 2, H - 14, "instructions saved in the source program's measured window (count)", 12, t["muted"], "middle")
    s.parts.append(f'<text transform="translate(18,{top + ph / 2}) rotate(-90)" font-size="12" fill="{t["muted"]}" '
                   f'text-anchor="middle" dominant-baseline="middle">cycles saved in the same window (count)</text>')
    # reference lines from the origin, clipped at the plot's edge
    for ratio in (1, 4, 12):
        xEnd = min(xmax, ymax / ratio)
        s.line(X(0), Y(0), X(xEnd), Y(xEnd * ratio), t["muted"], 1, "5,4")
        atTop = xEnd * ratio >= ymax
        label = f"{ratio} cycle{'s' if ratio > 1 else ''} per instruction"
        lx, ly = X(xEnd) - 6, Y(xEnd * ratio) + (14 if atTop else -8)
        s.text(lx, ly, label, 12, t["muted"], "end", halo=True)

    # labels: each point to its right (flipped left if it would leave the plot). The small sites
    # crowd the corner, so those get one group label; the table in hw/engine/README.md names each
    placed, labels = [], []
    ordered = sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    small = [((x, y), m) for (x, y), m in ordered if 0 < x < 0.1 * xmax]
    th = 16

    def place(px, py, text):
        tw = width(text, 12)
        for side in (1, -1):
            bx = px + 9 if side > 0 else px - 9 - tw
            box = (bx - 3, py - th / 2, bx + tw + 3, py + th / 2)
            inside = box[0] >= left and box[2] <= left + pw
            clash = any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed)
            if inside and not clash:
                placed.append(box)
                return bx if side > 0 else bx + tw, side
        raise SystemExit(f"could not place {text!r}")

    for (x, y), members in ordered:
        if ((x, y), members) in small:
            continue
        byProgram = defaultdict(list)
        for program, rank in members:
            byProgram[program].append(rank)
        parts = [f"{p} #{'/#'.join(map(str, sorted(r)))}" for p, r in byProgram.items()]
        text = ", ".join(parts) if (x or y) else "fused nothing: " + ", ".join(parts)
        px, py = X(x), Y(y)
        ly = py - 10 if (x, y) == (0, 0) else py  # the origin label sits off the x axis
        ax, side = place(px, ly, text)
        labels.append((px, py, ax, ly, text, side, 0))
    if small:
        byProgram = defaultdict(list)
        for _, members in small:
            for program, rank in members:
                byProgram[program].append(rank)
        names = ", ".join(f"{p} #{'/#'.join(map(str, sorted(r)))}" for p, r in sorted(byProgram.items()))
        lo, hi = min(x for (x, _), _ in small), max(x for (x, _), _ in small)
        rows = [f"{len(small)} small sites, {lo // 1000}k to {hi // 1000}k instructions:", names]
        xs, ys = [X(x) for (x, _), _ in small], [Y(y) for (_, y), _ in small]
        tw = max(width(r, 12) for r in rows)
        ax = max(xs) + 12
        # two lines, moved up until they clear every placed label and the points themselves
        for row in range(40):
            ay = min(ys) - 14 - row * 17
            box = (ax - 3, ay - th, ax + tw + 3, ay + th)
            if not any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed):
                break
        placed.append(box)
        for i, r in enumerate(rows):
            labels.append((None, None, ax, ay - 8 + i * 16, r, 1, 0))
        # a bracket from the label down to the cluster's extent
        s.line(ax - 6, ay + th - 2, ax - 6, max(ys) + 4, t["muted"], 0.8)
        s.line(ax - 6, max(ys) + 4, max(xs) + 2, max(ys) + 4, t["muted"], 0.8)
    for px, py, ax, ay, text, side, dy in labels:
        if dy and px is not None:
            s.line(px, py, ax - 2 if side > 0 else ax + 2, ay, t["muted"], 0.8)
    for (x, y) in groups:
        s.dot(X(x), Y(y), 5.5, t["blue"])
    for px, py, ax, ay, text, side, dy in labels:
        s.text(ax, ay, text, 12, t["ink"], "start" if side > 0 else "end", halo=True)
    s.save(path)


# --- 4. the frequency-ranked core: speedup per program under both rules

def frequencyBars(theme, path):
    t = THEMES[theme]
    rows = {r["benchmark"]: r for r in csv.DictReader(open(FREQ))}
    cyclesOnly = [float(rows[p]["speedup_cycles_only"]) for p in PROGRAMS]
    ruled = [float(rows[p]["speedup"]) for p in PROGRAMS]
    below = sum(v < 1 for v in ruled)

    W, H, left, right, top, bottom = 880, 470, 64, 24, 92, 64
    pw, ph = W - left - right, H - top - bottom
    lo, hi = 0.90, 1.20
    s = Svg(W, H, t)
    Y = lambda v: top + ph - ph * (v - lo) / (hi - lo)
    s.text(left, 22, f"Frequency-ranked core: the slower clock leaves {below} of {len(PROGRAMS)} programs below stock",
           16, t["ink"], weight="bold")
    s.text(left, 44, "one core with the top 3 non-conflicting formulas by total finder saved; "
           "+747 LUT4, Fmax 57.09 vs. 61.48 MHz", 12, t["muted"])
    # legend
    for i, (color, name) in enumerate(((t["blue"], "cycles only"), (t["orange"], "with T_fused = max(T_base, T_measured)"))):
        x = left + i * 150
        s.rect(x, 62, 14, 14, color, 2)
        s.text(x + 20, 69, name, 12, t["ink"])
    for v in (0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2):
        s.line(left, Y(v), left + pw, Y(v), t["grid"] if v != 1.0 else t["ink"], 1 if v != 1.0 else 1.2)
        s.text(left - 8, Y(v), f"{v:.2f}", 12, t["muted"], "end")
    s.parts.append(f'<text transform="translate(18,{top + ph / 2}) rotate(-90)" font-size="12" fill="{t["muted"]}" '
                   f'text-anchor="middle" dominant-baseline="middle">speedup over the stock core (bars start at 1.0 = stock)</text>')
    slot = pw / len(PROGRAMS)
    bw = slot * 0.34
    for i, p in enumerate(PROGRAMS):
        cx = left + slot * (i + 0.5)
        for j, (v, color) in enumerate(((cyclesOnly[i], t["blue"]), (ruled[i], t["orange"]))):
            x = cx - bw - 2 if j == 0 else cx + 2
            y0, y1 = Y(max(v, 1.0)), Y(min(v, 1.0))
            s.rect(x, y0, bw, max(y1 - y0, 0), color)
            s.text(x + bw / 2, (y0 - 9) if v >= 1 else (y1 + 10), f"{v:.3f}", 11, t["ink"], "middle")
        s.text(cx, top + ph + 18, p, 12, t["ink"], "middle")
    s.save(path)


FIGURES = {"pipeline": pipeline, "measurement": measurement,
           "sweep-cycles-vs-instructions": sweepScatter, "frequency-top3-speedup": frequencyBars}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="hw/docs/img")
    parser.add_argument("--only", nargs="*", default=list(FIGURES))
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name in args.only:
        for theme in THEMES:
            FIGURES[name](theme, os.path.join(args.out, f"{name}-{theme}.svg"))
    print(f"wrote {len(args.only) * len(THEMES)} SVGs to {args.out}")


if __name__ == "__main__":
    main()
