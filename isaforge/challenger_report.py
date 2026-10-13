"""Render the literature-informed model study from saved numerical evidence."""
import argparse
import html
import json
from pathlib import Path


def render(repo, output):
    def read(name): return json.loads((repo/name).read_text())
    dev=read('results/2026-10-13-v3/models/development-evaluation.json')
    probe=read('results/2026-10-13-v3/probe-evaluation.json')
    reference=read('results/2026-10-13-v3/masterrtl/development-evaluation.json')
    dev['macro_program_metrics'].update(reference['macro_program_metrics'])
    aliases={'resource_v2':'V2 resource regression','v1_xgboost_log':'Initial XGBoost architecture',
             'v2_residual_xgb':'Previous residual XGBoost','v3_original':'Regularized model, original features',
             'v3_structural':'New structural challenger', 'masterrtl_sog':'MasterRTL recipe adapted to LUT4'}
    def fmt(v):return '—' if v is None else f'{v:,.3f}'
    rows=[]
    for key,model in probe['models'].items():
        m=model['pooled']; d=dev['macro_program_metrics'][key]
        rows.append('<tr><td>'+html.escape(aliases.get(key,key))+'</td>'+''.join('<td>'+fmt(v)+'</td>' for v in
            [d['macro_program_mae_lut4'],m['mae_lut4'],m['rmsle'],m['positive_mape_percent']])+'</tr>')
    strata=[]
    for name,m in probe['models']['v3_structural']['by_stratum'].items():
        base=probe['models']['masterrtl_sog']['by_stratum'][name]
        residual=probe['models']['v2_residual_xgb']['by_stratum'][name]
        strata.append(f'<tr><td>{html.escape(name)}</td><td>{m["sample_count"]}</td><td>{fmt(base["mae_lut4"])}</td><td>{fmt(residual["mae_lut4"])}</td><td>{fmt(m["mae_lut4"])}</td></tr>')
    choice=dev['final_selection']['structural']['selected_candidate']
    text='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ISAForge · Research-informed model improvement</title>
<style>body{font:17px/1.6 system-ui,sans-serif;color:#183047;background:#f5f7fa;max-width:1080px;margin:40px auto;padding:0 24px}h1{line-height:1.15;font-size:38px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;background:white;font-size:15px}th,td{padding:12px;text-align:right;border-bottom:1px solid #d8e0e8}th:first-child,td:first-child{text-align:left}th{background:#e3edf3}a{color:#086e8a}.note{padding:18px;border-left:4px solid #078493;background:#e5f2f2}.small{font-size:14px;color:#486074}code{background:#e3eaf0;padding:2px 5px}li{margin:8px 0}</style>
<h1>ISAForge: a matched test of six area predictors</h1><p class="small">13 October 2026 · Development comparisons and a separately frozen synthetic probe</p>
<p class="note"><strong>The MasterRTL adaptation wins this fresh test.</strong> On the same 192 unseen circuits, its mean absolute error is 35.07 LUT4, versus 41.59 for our previous residual model and 56.40 for the structural challenger. This is 15.69% lower MAE than the previous residual model and 37.82% lower than the new challenger. We retain the unsuccessful structural revision and all six models’ results. No weights or features were changed after opening this test.</p>
<h2>What published models report</h2>
<table><tr><th>System</th><th>Reported result</th><th>What it measures</th></tr>
<tr><td><a href="https://users.cs.duke.edu/~lkw34/papers/fang-presynthesis-tcad2024.pdf">MasterRTL, Table III</a></td><td>16% area MAPE; R 0.98</td><td>Whole ASIC designs</td></tr>
<tr><td><a href="https://arxiv.org/pdf/2201.06848">HLS GNN, Table 5: PNA-I</a></td><td>21.45% LUT MAPE</td><td>Unseen real FPGA programs; inferred auxiliary features</td></tr>
<tr><td>Same paper: PNA-R</td><td>16.96% LUT MAPE</td><td>Requires HLS intermediate features</td></tr>
<tr><td><a href="https://arxiv.org/html/2509.15782v2">CIDRE, Table I</a></td><td>1.39× CRC32 estimated speedup</td><td>Eight 2-input/1-output instructions; RV64 ASIC processor</td></tr>
<tr><td><a href="https://arxiv.org/abs/2508.07725">ARISE</a></td><td>7.39% average instruction-count reduction</td><td>Embench; up to 16 extensions</td></tr></table>
<p>These are reference results, not a shared leaderboard. Our target is isolated iCE40 LUT4 count for small RV32 instruction formulas. Different devices, tools, circuit scales, workloads, and feature costs prevent a superiority claim.</p>
<h2>What changed</h2><p>The new feature module follows the papers’ emphasis on circuit structure: live carry spans, demanded mux cones, comparator patterns, multiplier columns, sharing, and algebraic simplification. A small fixed candidate grid compares a physical-resource regression with regularized residual corrections and a current-model fallback. A separate matched baseline transfers the released MasterRTL recipe to our LUT4 target; we did not train a GNN.</p>
<p>On the earlier frozen final set, the current structural model had 23.154 LUT4 MAE and 39.888% MAPE on positive labels; residual XGBoost had 33.165 LUT4 MAE and 32.481% positive-label MAPE. Absolute error and relative error favor different models.</p>
<h2>Measured comparison</h2><p>All six models below fit the same 713 distinct development formulas. The matched reference follows the released MasterRTL 14-feature bit-graph recipe and 25-tree/depth-12 XGBoost configuration, with its ASIC target changed to our LUT4 labels. It requires Yosys preprocessing; our formula models do not. This is a matched transfer of a published recipe, not replication of the paper’s ASIC results. Development evaluation holds out whole programs and excludes identical formulas from training; the v3 grid additionally uses nested folds for model selection. The 192 synthetic probe formulas are excluded from training and were scored after model freeze.</p>
<table><tr><th>Model</th><th>Development macro MAE</th><th>Fresh probe MAE</th><th>Probe RMSLE</th><th>Probe positive MAPE (%)</th></tr>'''+''.join(rows)+'''</table>
<p class="small">MAE is in LUT4. Percentage error uses all 181 positive labels; all 11 true zeros remain in MAE/RMSLE. Errors above 100% are retained: large overpredictions on tiny circuits amplify MAPE. Development macro averages weight programs equally; the probe has eight equal 24-circuit strata. These are different populations.</p>
<p>Selected structural configuration before probe access: <code>'''+html.escape(choice)+'''</code>.</p>
<p>The independently recomputed paired difference is 21.33 LUT4 in favor of MasterRTL versus v3, with a descriptive 95% stratified bootstrap interval of [2.88, 40.58]. Against the previous residual model, the difference is 6.52 LUT4 with interval [−4.89, 18.04], which includes zero. These formula-level intervals condition on the eight curated strata; they do not establish real-workload superiority.</p><h2>Every probe stratum</h2><table><tr><th>Stratum</th><th>Circuits</th><th>MasterRTL adapted MAE</th><th>Previous residual MAE</th><th>Structural challenger MAE</th></tr>'''+''.join(strata)+'''</table>
<p class="note">The synthetic probe is a test of unseen formula compositions, not a new executed workload or a replication of the published ASIC benchmark. No model or feature tuning is permitted on these results while retaining an untouched-test claim. The prior processor result remains separate: 8.6% fewer CRC32 cycles, 4.35% more LUT4s, and 1.022–1.140× conditional post-route runtime estimates.</p>
<h2>What the errors teach us</h2><p>MasterRTL has lower mean error in seven of eight strata, but loses on variable shifts. The largest relative-error failure in our structural model is a masked multiplication that synthesizes to one LUT4 but was predicted as 675.36 LUT4. RV32 truncation collapses it to a single two-bit Boolean function; this is a missed simplification, not just a percentage-metric artifact. MasterRTL also has failures: one 88-LUT4 signed-multiply formula is predicted at 1,379.64 LUT4. All cases remain in the results. The next model revision should target these simplifications and variable-shift behavior, and requires another untouched evaluation set.</p><h2>Inference cost</h2><p>For all 192 formulas, MasterRTL feature extraction plus inference took 7.431 seconds with an empty cache and one worker; the median of 20 warm cached batches was 0.205 seconds. The structural challenger took 0.047 seconds per warm batch. MasterRTL’s cached timing still includes file reads, integrity checks, and graph traversal. Loading and process startup are excluded. The stronger predictor therefore has a preprocessing cost that formula-only models avoid.</p>
<h2>Research figures</h2><p>Each figure is available as a vector PDF and SVG, plus a 300 dpi PNG. The figure bundle includes captions, numerical plot data, input hashes, and explicit descriptions of uncertainty and sample units.</p><div id="figure-gallery"></div>
<h2>Reproduce and inspect</h2><p>Source, full predictions, fold selection, feature ablation, model artifacts, provenance hashes, and verified/synthesized probe evidence are in <a href="ISAForge-research-evidence.zip">the evidence archive</a>. Repository changes are on <a href="https://github.com/jas0nriverah/agentic-riscv-codesign/pull/3">draft PR #3</a>. See <a href="ISAForge-research-results.html">the preceding research report</a> for original prospective workload and processor results.</p></html>'''
    figures = sorted((output.parent/'research-figures').glob('*.png'))
    gallery = ''.join(f'<figure><a href="research-figures/{p.stem}.pdf"><img src="research-figures/{p.name}" alt="{html.escape(p.stem)}" style="width:100%;background:white"></a><figcaption><a href="research-figures/{p.stem}.pdf">Vector PDF</a> · <a href="research-figures/{p.stem}.svg">SVG</a> · <a href="research-figures/{p.name}">PNG</a></figcaption></figure>' for p in figures)
    text=text.replace('<div id="figure-gallery"></div>',gallery)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd());parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(render(args.repo,args.output))


if __name__=='__main__':main()
