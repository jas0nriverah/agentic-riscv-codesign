"""Render the prospective inference and architectural research evidence."""
import argparse
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


NAMES = {'v1': 'Original XGBoost', 'resource': 'Structural linear model', 'v2': 'Structural + XGBoost residual'}
COLORS = ['#94a3b8', '#087e8b', '#e88942']


def render(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stage2 = json.loads(Path('generated/holdout/evaluation.json').read_text())
    final = json.loads(Path('generated/final-holdout/evaluation.json').read_text())
    core = json.loads(Path('generated/core/summary.json').read_text())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, report, title in zip(axs, [stage2, final], ['First prospective test', 'Final independent test']):
        values = [report['accuracy'][name]['distinct_novel_formulas']['mae_lut4'] for name in NAMES]
        ax.bar(range(3), values, color=COLORS)
        ax.set_xticks(range(3), ['Original\nXGBoost', 'Structural\nlinear', 'Structural +\nXGBoost'])
        ax.set_title(f"{title}\n{report['novel_formula_count']} distinct new formulas")
        ax.set_ylabel('Mean absolute error (LUT4)')
        ax.set_ylim(0, max(values) * 1.22)
        for i, v in enumerate(values): ax.text(i, v + max(values)*.035, f'{v:.1f}', ha='center')
    fig.suptitle('Frozen models trained on the original 301 circuits', y=1.02)
    fig.tight_layout();fig.savefig(output/'prospective-model-comparison.png', dpi=180, bbox_inches='tight');plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    benchmarks = final['test_benchmarks']
    x = np.arange(len(benchmarks))
    for i, name in enumerate(NAMES):
        values = [final['accuracy'][name]['per_program'][b]['novel']['mae_lut4'] for b in benchmarks]
        ax.bar(x + (i-1)*.25, values, .25, label=NAMES[name], color=COLORS[i])
    ax.set_xticks(x, benchmarks);ax.set_ylabel('Novel-formula MAE (LUT4)');ax.legend(frameon=False)
    ax.set_title('Final test: errors vary substantially across programs')
    fig.tight_layout();fig.savefig(output/'final-program-errors.png', dpi=180);plt.close(fig)

    strategies = ['frequency', 'merit', 'random', 'model:v1', 'model:resource', 'model:v2', 'model:conservative']
    labels = ['Frequency', 'Merit', 'Random', 'Original XGBoost', 'Structural linear', 'Structural + XGBoost', 'Conservative margin']
    scores = np.array([[next(r for r in final['selection']['summaries'] if r['strategy']==s and r['cap']==cap and r['budget']==1)['retention']['mean'] for cap in (32,64,128)] for s in strategies])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.imshow(scores, vmin=0, vmax=1, cmap='YlGnBu', aspect='auto')
    ax.set_xticks(range(3), ['32 LUT4', '64 LUT4 (primary)', '128 LUT4'])
    ax.set_yticks(range(len(labels)), labels)
    for (i,j), v in np.ndenumerate(scores):
        ax.text(j, i, f'{100*v:.1f}%', color='white' if v>.65 else '#182537', ha='center', va='center')
    ax.set_title('Final test: oracle instruction savings retained\nOne target measurement; macro average over five programs')
    fig.tight_layout();fig.savefig(output/'final-selection-comparison.png', dpi=180);plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for index in (0,1):
        values = []
        for run in core['measurements']:
            records = [r for r in run['comparisons'] if r['formula_index']==index and r['iterations']==1024]
            values.append((run['pcpi_response_latency'], np.mean([r['cycle_ratio'] for r in records])))
        ax.plot(*zip(*values), marker='o', label=f'Formula {index}')
    ax.axhline(1, color='#64748b', linestyle='--')
    ax.set_xlabel('Configured custom-unit response latency (cycles)');ax.set_ylabel('Baseline cycles / custom cycles')
    ax.set_title('Recurrence tests: fewer instructions can still be slower');ax.legend(frameon=False)
    fig.tight_layout();fig.savefig(output/'pcpi-latency-tradeoff.png', dpi=180);plt.close(fig)

    rows = ''.join(f"<tr><td>{html.escape(NAMES[n])}</td><td>{m['distinct_novel_formulas']['mae_lut4']:.2f}</td><td>{m['distinct_novel_formulas']['rmsle']:.3f}</td><td>{m['distinct_novel_formulas']['spearman']:.3f}</td></tr>" for n,m in final['accuracy'].items())
    primary = ''.join(f"<tr><td>{html.escape(s)}</td><td>{next(r for r in final['selection']['summaries'] if r['strategy']==s and r['cap']==64 and r['budget']==1)['retention']['mean']*100:.1f}%</td></tr>" for s in strategies)
    crc = next(r for r in core['crc32_benchmark']['measurements'] if r['name']=='both' and r['pcpi_response_latency']==0)
    soc_section = '<p>The on-chip-memory extension is still being validated; the core experiment below has external zero-wait memory.</p>'
    soc_path = Path('generated/soc/summary.json')
    if soc_path.exists():
        soc = json.loads(soc_path.read_text())
        c = soc['comparisons']
        soc_section = f"<h3>Self-contained FPGA system</h3><p>The subsequent SoC includes 8 KiB initialized synchronous memory in both simulation and synthesis. CRC cycles decrease from <strong>{c['baseline_cycles']:,}</strong> to <strong>{c['custom_cycles']:,}</strong> ({100*(1-c['custom_cycles']/c['baseline_cycles']):.2f}% fewer). Whole-SoC LUT4 rises from 1,633 to 1,704 (+4.35%); both use 20 of 32 device BRAMs.</p>"
        route_path = Path('generated/soc/routing/summary.json')
        if route_path.exists():
            route = json.loads(route_path.read_text())
            rows_t, baseline_ms, custom_ms = [], [], []
            for seed in route['seeds']:
                b = next(r for r in route['runs'] if r['configuration']=='baseline' and r['seed']==seed)
                v = next(r for r in route['runs'] if r['configuration']=='custom' and r['seed']==seed)
                bf, vf = b['limiting_internal_fmax_mhz'], v['limiting_internal_fmax_mhz']
                bt, vt = c['baseline_cycles']/bf/1000, c['custom_cycles']/vf/1000
                baseline_ms.append(bt);custom_ms.append(vt)
                rows_t.append(f'<tr><td>{seed}</td><td>{bf:.2f}</td><td>{vf:.2f}</td><td>{bt/vt:.3f}×</td></tr>')
            fig, ax = plt.subplots(figsize=(8,4.5));x=np.arange(len(route['seeds']))
            ax.bar(x-.18, baseline_ms, .36, color=COLORS[0], label='Baseline')
            ax.bar(x+.18, custom_ms, .36, color=COLORS[1], label='Custom')
            ax.set_xticks(x, [f'Seed {s}' for s in route['seeds']]);ax.set_ylabel('Estimated CRC time at routed Fmax (ms)')
            ax.set_title('Complete on-chip-memory SoC: all matched routing seeds');ax.legend(frameon=False)
            fig.tight_layout();fig.savefig(output/'soc-routed-runtime.png', dpi=180);plt.close(fig)
            soc_section += '<p>Nextpnr routed both implementations for HX8K CT256 with identical eight-pin constraints and seeds 1–3. All six designs fit and pass the common 12 MHz constraint. The following estimates use each routed implementation\'s register-to-register Fmax; they are not board measurements.</p><table><tr><th>Seed</th><th>Baseline Fmax, MHz</th><th>Custom Fmax, MHz</th><th>Estimated runtime ratio</th></tr>'+''.join(rows_t)+'</table><img src="soc-routed-runtime.png" alt="Matched-seed estimated whole-SoC runtime"><p>On-chip memory timing is included. Reset release and status observation remain external-interface assumptions; power, temperature and physical hardware operation were not measured. The three seeds show placement sensitivity rather than a statistical population.</p>'
    body = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>ISAForge — prospective research results</title>
<style>body{{font:17px/1.6 system-ui,sans-serif;color:#182537;max-width:1100px;margin:45px auto;padding:0 22px}}h1{{line-height:1.15}}h2{{margin-top:38px}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #dbe3e9}}img{{max-width:100%;height:auto}}.lead{{font-size:21px}}.note{{background:#edf5f6;padding:18px;border-left:4px solid #087e8b}}small{{color:#526170}}a{{color:#087e8b}}</style>
<h1>ISAForge: measured cost prediction and verified RISC-V instruction integration</h1><p><small>Research checkpoint · October 13, 2026 · frozen models, prospective tests, and retained negative results</small></p>
<p class="lead">A structural linear model transfers better than the tested tree models on the final workload group. Custom instructions reduce full CRC benchmark cycles, but learned selection does not beat simple merit on the primary prospective endpoint.</p>
<div class="note"><strong>What we can claim:</strong> actual inference on new workloads; improved resource prediction over our original model; verified whole-program cycle reduction; a reproducible finite-pool selection comparison.<br><strong>What we cannot claim:</strong> superiority over a named published system, a calibrated probability of feasibility, or measured board-level runtime.</div>
<h2>Experimental separation</h2><table><tr><th>Stage</th><th>Programs</th><th>Candidate rows</th><th>Distinct circuits</th><th>Role</th></tr>
<tr><td>Original development</td><td>8</td><td>339</td><td>301</td><td>Train all frozen models</td></tr>
<tr><td>First prospective test</td><td>6 (4 with candidates)</td><td>198</td><td>167</td><td>Independent model test; later policy calibration</td></tr>
<tr><td>Final independent test</td><td>5</td><td>561</td><td>453</td><td>No model or policy changes after scoring</td></tr></table>
<p>All 19 programs passed upstream self-checks. There are 1,098 benchmark-candidate rows and 713 distinct formulas across all stages. The verifier performed 1,035,204 formula/input comparisons across the three collections. Statemate and nsichneu produced no safe candidates; their coverage failures remain in the evidence.</p>
<h2>Actual model inference</h2><img src="prospective-model-comparison.png" alt="Prospective heldout model errors"><p>Final metrics below use 331 distinct formulas absent from both original training and policy calibration. They include 60 zero-LUT formulas; nonzero-subset and program-level results are saved separately.</p>
<table><tr><th>Frozen model</th><th>MAE (LUT4)</th><th>RMSLE</th><th>Spearman</th></tr>{rows}</table>
<img src="final-program-errors.png" alt="Errors by final test program"><p>The structural model fits seven nonnegative resource coefficients. Backward bit-demand and operand-width features let it extrapolate beyond examples seen in training. The XGBoost residual improves the first prospective group but loses to the simpler model on the final group. Selecting a deployment model after this comparison does not create another unbiased evaluation.</p>
<p>All predictions were produced by loading the saved models in a separate process. Inference receives only formula and identity fields. The bundle includes every prediction, model hash, load time, and 20 warm-batch timings; local timings are illustrative CPU measurements, not a controlled systems benchmark.</p>
<h2>Does prediction improve selection?</h2><img src="final-selection-comparison.png" alt="Final one measurement selection results"><table><tr><th>Policy, 64-LUT cap / one measurement</th><th>Mean oracle savings retained</th></tr>{primary}</table>
<p>The primary endpoint ties simple merit. The earlier prospective test is a negative result for point-feasibility ranking: it retained 85.5% versus merit's 100%. A subsequent conservative margin was calibrated on that earlier group and frozen before the final test. Its final result is a tie, not demonstrated superiority.</p>
<p>Random ordering uses 100 seeds averaged within each program; deterministic policies run once. Five-program bootstrap intervals are descriptive. Historical training and calibration labels are outside the target measurement budget. The objective is instruction savings for one candidate under an isolated LUT cap, not multi-instruction set optimization or CPU runtime.</p>
<h2>Processor validation</h2><p>The complete CRC32 port produces checksum <code>0x65842ca9</code> and passes the upstream verification. Both custom instructions reduce cycles from <strong>{crc['baseline']['cycles']:,}</strong> to <strong>{crc['custom']['cycles']:,}</strong>: <strong>{100*(1-crc['custom']['cycles']/crc['baseline']['cycles']):.2f}% fewer cycles</strong>, or a {crc['cycle_ratio']:.3f}× cycle ratio. Whole-core synthesis changes from 1,488 to 1,570 LUT4 (+5.51%).</p>
<p>This initial result uses PicoRV32 RV32I, identical zero-wait external-memory behavior, source-level inline custom instructions, stock/source-wrapper controls, and full checksum checks. It is separate from the RV32IM extraction corpus. Recompilation affects register allocation, so instruction counts are measured again instead of assumed from the extractor.</p>
<img src="pcpi-latency-tradeoff.png" alt="Cycle ratio versus custom unit response latency">{soc_section}
<h2>Research position</h2><p><a href="https://arxiv.org/abs/2509.15782">CIDRE</a> and <a href="https://arxiv.org/abs/2508.07725">ARISE</a> establish important prior work in automatic instruction selection and extraction. Our heuristic baselines are not reproductions of these systems. The supported contribution is an open, measured study of cost-model transfer, decision failures, and verified integration. A claim against prior systems requires matched implementations and workloads.</p>
<p>Remaining proposal work includes a validated speedup predictor, multi-instruction selection with overlap/resource accounting, an adaptive measurement policy, and a controlled LLM-versus-non-LLM comparison. Current empirical margins are not a calibrated confidence guarantee. These gaps remain visible rather than being counted as completed.</p>
<p><a href="https://github.com/jas0nriverah/agentic-riscv-codesign/pull/3">Source and draft PR</a> · <a href="ISAForge-research-evidence.zip">Research evidence bundle</a> · <a href="ISAForge-research-direction.html">Primary-source research review</a></p></html>'''
    path = output/'ISAForge-research-results.html';path.write_text(body)
    return path


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output', type=Path, required=True)
    print(render(parser.parse_args().output))
