#!/usr/bin/env python3
"""Build an offline research demo from a ledger and sealed prospective evidence.

Read-only analysis: no model fitting, native evaluations, or external resources.
"""
from __future__ import annotations

import argparse
from html import escape
import io
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isaforge import codesign as c
from isaforge import experiment_ledger as ledger


def _close(actual, expected, message):
    c.require(type(actual) in (int, float) and math.isfinite(actual)
              and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), message)


def workload_rows(data):
    """Join on exact context; preserve the unmodified baseline as incumbent."""
    result = []
    for context in data['contexts']:
        plan = json.loads(context['plan_json'])
        c.require(plan['schema'] == 'isaforge-automatic-workload-v1', 'Uniform demo accepts automatic evidence only')
        if context['status'] != 'verified_complete':
            continue
        records = [r for r in data['measurements'] if r['context_id'] == context['context_id']]
        baseline = [r for r in records if r['candidate_id'] is None and r['name'] == 'baseline']
        c.require(len(baseline) == 1, 'Exactly one baseline required per complete context')
        baseline = baseline[0]
        c.require(baseline['correctness_verified'] == 1 and baseline['timing_feasible'] == 1
                  and baseline['frequency_mhz'] == 12, 'Baseline must be correct and feasible at 12 MHz')
        cap = baseline['integrated_lut4'] + 128
        feasible = [r for r in records if r['correctness_verified'] == 1 and r['timing_feasible'] == 1
                    and r['frequency_mhz'] == 12 and r['integrated_lut4'] <= cap]
        for record in records:
            _close(record['speedup'], baseline['cycles'] / record['cycles'], 'Ledger cycle/speedup mismatch')
        best = min(feasible, key=lambda r: (-r['speedup'], r['integrated_lut4'], r['name']))
        result.append(dict(context=context, baseline=baseline, best=best, area_cap=cap,
                           candidates=sum(r['candidate_id'] is not None for r in records)))
    return result


def load_selection(directory, data, workloads):
    directory = Path(directory)
    protocol = c.unseal(directory / 'protocol.json')
    report = c.unseal(directory / 'report.json')
    c.require(protocol['schema'] == 'isaforge-prospective-selection-v1', 'Unsupported prospective schema')
    c.require(report['protocol_sha256'] == c.sha(directory / 'protocol.json'), 'Report/protocol binding differs')
    c.require(report['contexts'] == protocol['contexts'], 'Selection contexts differ')
    c.require(protocol['target_labels_read'] == 0, 'Protocol was not frozen label-free')
    c.require({'public.json', 'predictions.json'} <= protocol['artifacts'].keys(), 'Missing frozen public/prediction artifacts')
    for relative, expected in protocol['artifacts'].items():
        path = (directory / relative).resolve()
        c.require(path.is_relative_to(directory.resolve()), 'Selection artifact escapes directory')
        c.require(c.sha(path) == expected, 'Frozen selection artifact changed: ' + relative)
    public = c.unseal(directory / 'public.json')
    c.unseal(directory / 'predictions.json')
    c.require(len(public) == protocol['target_candidates'] and len({r['candidate_id'] for r in public}) == len(public),
              'Public candidate count/identity mismatch')
    benchmarks = {r['benchmark'] for r in public}
    c.require(len(benchmarks) == 1, 'One exact target benchmark context required')
    benchmark = next(iter(benchmarks))
    targets = [w for w in workloads if benchmark.endswith(':' + w['context']['context_id'])]
    c.require(len(targets) == 1, 'Prospective target must join one verified ledger context by exact benchmark suffix')
    target = targets[0]
    c.require(protocol['target_workload'].removeprefix('embench-') == target['context']['workload'], 'Target workload differs')
    c.require(protocol['area_cap'] == target['area_cap'], 'Prospective area cap must equal baseline +128 LUT4')
    candidate_rows = [r for r in data['candidates'] if r['context_id'] == target['context']['context_id']]
    labels = {}
    for row in public:
        matches = [r for r in candidate_rows if r['formula'] == row['formula']]
        c.require(len(matches) == 1, 'Public formula does not join one ledger candidate')
        candidate = matches[0]
        c.require(all(row.get(k) == v for k, v in json.loads(candidate['features_json']).items()), 'Public/ledger features differ')
        matches = [r for r in data['measurements'] if r['context_id'] == target['context']['context_id']
                   and r['candidate_id'] == candidate['candidate_id']]
        c.require(len(matches) == 1, 'Candidate does not join one verified measurement')
        labels[row['candidate_id']] = matches[0]
    c.require(len(labels) == len(candidate_rows) == report['oracle_label_count'], 'Complete target pool required')
    _close(report['oracle_speedup'], target['best']['speedup'], 'Reported oracle differs from ledger feasible optimum')
    policies, seeds, budgets = protocol['policies'], protocol['seeds'], protocol['budgets']
    c.require(len(set(policies)) == len(policies) and len(set(seeds)) == len(seeds)
              and len(set(budgets)) == len(budgets) and policies and seeds and budgets, 'Unique policies/seeds/budgets required')
    groups = {}
    for run in report['runs']:
        key = (run['policy'], run['seed'])
        c.require(key not in groups and key[0] in policies and key[1] in seeds, 'Unexpected or duplicate policy run')
        c.require([p['budget'] for p in run['curve']] == budgets, 'Policy budgets differ from frozen protocol')
        for point in run['curve']:
            ids = point['measured_ids']
            c.require(len(ids) == point['budget'] and len(set(ids)) == len(ids) and set(ids) <= labels.keys(),
                      'Invalid charged measurement list')
            eligible = [labels[i] for i in ids if labels[i]['timing_feasible'] == 1
                        and labels[i]['correctness_verified'] == 1 and labels[i]['frequency_mhz'] == 12
                        and labels[i]['integrated_lut4'] <= target['area_cap']]
            best = max([1.0] + [r['speedup'] for r in eligible])
            _close(point['best_speedup'], best, 'Policy endpoint differs from paid feasible labels')
            _close(point['regret'], report['oracle_speedup'] - best, 'Policy regret differs')
        groups[key] = run
    c.require(set(groups) == {(p, s) for p in policies for s in seeds}, 'Missing policy/seed runs')
    summary = []
    for policy in policies:
        for budget in budgets:
            points = [point for seed in seeds for point in groups[policy, seed]['curve'] if point['budget'] == budget]
            matches = [r for r in report['summary'] if r['policy'] == policy and r['budget'] == budget]
            c.require(len(matches) == 1, 'Missing or duplicate summary row')
            row = matches[0]
            for output, field in [('mean_best_speedup', 'best_speedup'), ('mean_regret', 'regret'),
                                  ('mean_target_candidate_wall_seconds', 'target_candidate_wall_seconds')]:
                _close(row[output], statistics.mean(p[field] for p in points), 'Summary arithmetic differs')
            c.require(row['oracle_hits'] == sum(p['regret'] == 0 for p in points), 'Oracle-hit count differs')
            summary.append(row)
    c.require(len(summary) == len(report['summary']), 'Unexpected summary rows')
    return dict(protocol=protocol, report=report, target_context_id=target['context']['context_id'], summary=summary,
                hashes={name: c.sha(directory / name) for name in ('protocol.json', 'report.json')})


def _chart(selection):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    protocol = selection['protocol']
    with plt.rc_context({'svg.hashsalt': 'isaforge-demo', 'font.size': 9}):
        fig, ax = plt.subplots(figsize=(9, 3.9), layout='constrained')
        for policy in protocol['policies']:
            rows = sorted([r for r in selection['summary'] if r['policy'] == policy], key=lambda r:r['budget'])
            ax.plot([r['budget'] for r in rows], [r['mean_best_speedup'] for r in rows], marker='o',
                    linewidth=1.6, markersize=4, label=policy.replace('_', ' '))
        ax.axhline(selection['report']['oracle_speedup'], color='#263849', linestyle='--', label='measured pool oracle')
        ax.set(xlabel='Charged candidate evaluations', ylabel='Best verified feasible speedup (×)',
               xticks=sorted(protocol['budgets']))
        ax.grid(alpha=.18)
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=False, fontsize=8)
        stream = io.StringIO()
        fig.savefig(stream, format='svg', metadata={'Date': None})
        plt.close(fig)
        svg = stream.getvalue()
        return svg[svg.index('<svg'):]


def _table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+escape(str(h))+'</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>'+''.join('<td>'+escape(str(cell))+'</td>' for cell in row)+'</tr>' for row in rows) + '</tbody></table></div>'


def render(data, selection):
    workloads = workload_rows(data)
    target = selection['target_context_id']
    protocol, report = selection['protocol'], selection['report']
    complete_ids = {w['context']['context_id'] for w in workloads}
    candidates = [r for r in data['candidates'] if r['context_id'] in complete_ids]
    measurements = [r for r in data['measurements'] if r['context_id'] in complete_ids]
    routes = [r for r in data['routes'] if r['context_id'] in complete_ids]
    metrics = [('workloads', len({w['context']['workload'] for w in workloads})), ('candidates', len(candidates)),
               ('measured designs', len(measurements)), ('routing results', len(routes))]
    sections = []
    for workload in workloads:
        context, baseline, best = workload['context'], workload['baseline'], workload['best']
        cohort = 'Prospective target' if context['context_id'] == target else 'Consumed development evidence'
        sections.append('<article class="panel"><div class="eyebrow">'+escape(cohort)+'</div><h2>'+escape(context['workload'])+'</h2>'
            + _table(['Design', 'Whole-program cycles', 'Speedup', 'Integrated LUT4', 'Correct / 12 MHz'],
                     [('Baseline', f"{baseline['cycles']:,}", '1.0000×', baseline['integrated_lut4'], 'Passed / passed'),
                      (best['name'], f"{best['cycles']:,}", f"{best['speedup']:.4f}×", best['integrated_lut4'], 'Passed / passed')])
            + '<p>Best measured single instruction under baseline +128 LUT4 ('+str(workload['area_cap'])+' total), with the baseline retained as an option.</p>'
            + '<details><summary>Exact build context</summary><code>'+escape(context['context_id'])+'</code></details></article>')
    comparison = _table(['Policy', 'Budget', 'Mean best speedup', 'Mean regret', 'Oracle hits', 'Mean target wall seconds'],
        [(r['policy'].replace('_',' '),r['budget'],f"{r['mean_best_speedup']:.4f}×",f"{r['mean_regret']:.4f}",
          f"{r['oracle_hits']}/{len(protocol['seeds'])}",f"{r['mean_target_candidate_wall_seconds']:.2f}") for r in selection['summary']])
    diagnostics = _table(['Model', 'Central 90% ensemble interval coverage', 'Mean interval width'],
        [(name, f"{statistics.mean(r['ensemble_interval_coverage'] for r in report['diagnostics'] if r['model']==name):.1%}",
          f"{statistics.mean(r['mean_interval_width'] for r in report['diagnostics'] if r['model']==name):.4f}")
         for name in sorted({r['model'] for r in report['diagnostics']})])
    cost_rows = [(next(cn['workload'] for cn in data['contexts'] if cn['context_id']==r['context_id']),
                  r['kind'].replace('_',' '), r['phase'].replace('_',' '), r['records'], f"{r['seconds']:.2f}")
                 for r in data['cost_summary']]
    failure_rows = [(next(cn['workload'] for cn in data['contexts'] if cn['context_id']==r['context_id']),r['kind'],
                     json.loads(r['detail_json']).get('error') or json.loads(r['detail_json']).get('failure'),r['authentication'])
                    for r in data['failures']]
    provenance = _table(['Workload', 'Status', 'Context identity', 'Evidence manifest SHA256'],
        [(r['workload'],r['status'],r['context_id'],r['manifest_sha256']) for r in data['contexts']])
    limits = ['One prospective workload; the five seed runs reuse the same candidate labels and are dependent repetitions, not five workload tests.',
              'Bootstrap ensemble intervals are descriptive spread, not calibrated confidence. Feature-support ranges do not establish coverage under workload shift.',
              'Candidate pools were shortlisted by merit. Their measured oracle covers only those pools.',
              'Simulated processor cycles and FPGA synthesis/routing estimates; no physical-board, energy, production, or hiring-outcome claims.',
              'Single instructions are measured separately. Their speedups and area changes cannot be added for instruction sets.',
              'The original CRC32 source-adapter experiment is excluded from uniform automatic-workload counts. Incomplete contexts never contribute verified labels.']
    limits += report.get('limitations', [])
    cost_extra = _table(['Selection cost category', 'Recorded seconds', 'Scope'],
        [('Historical candidates',f"{protocol['historical_candidate_wall_seconds']:.2f}",'Prior candidate wall time; setup excluded'),
         ('Independent latency calibration',f"{protocol['calibration_command_seconds']:.2f}",'Command wall time; separate timer scope'),
         ('Frozen model fitting and prediction',f"{sum(r['fit_and_predict_seconds'] for r in report['runs']):.2f}",
          'Recorded across model policies and seeds; excluded from target evaluation axis')])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISAForge · measured instruction selection</title><style>
:root{color-scheme:light;--ink:#142a3c;--muted:#566977;--line:#dae4e8;--accent:#087e83}*{box-sizing:border-box}body{margin:0;background:#f3f7f8;color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1180px;margin:auto;padding:38px 24px 70px}header{background:#102b3d;color:#fff;padding:40px;border-radius:18px}h1{font-size:clamp(28px,4vw,44px);line-height:1.12;max-width:800px;margin:10px 0 18px}h2{font-size:22px;margin:8px 0 16px}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:700;color:#087e83}header .eyebrow{color:#7ee0d3}header p{max-width:820px;color:#d2e1e8}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}.metric,.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:22px}.metric strong{display:block;font-size:32px}.metric span{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}.panel{margin-bottom:20px}p{color:var(--muted)}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}td{overflow-wrap:anywhere}code{font-size:11px;overflow-wrap:anywhere}details{margin-top:14px}summary{cursor:pointer;color:var(--accent)}.chart{background:white;overflow:auto}.chart svg{width:100%;height:auto;min-width:640px}.note{border-left:3px solid var(--accent);padding-left:15px}li{margin-bottom:8px}@media(max-width:650px){main{padding:18px 12px}header{padding:25px}.metrics{grid-template-columns:repeat(2,1fr)}.grid{display:block}.panel{padding:16px}}
</style><main><header><div class="eyebrow">ISAForge · local research prototype</div><h1>Choosing custom instructions with measured evidence.</h1><p>A reproducible comparison of fixed learned predictors and architectural heuristics on real RISC-V workloads. The question is whether better predictions find verified performance with fewer hardware evaluations.</p></header>
<div class="metrics">''' + ''.join('<div class="metric"><strong>'+str(v)+'</strong><span>'+escape(k)+'</span></div>' for k,v in metrics) + '</div><div class="grid">' + ''.join(sections) + '''</div>
<section class="panel"><div class="eyebrow">Frozen before target labels</div><h2>Prospective selection comparison</h2><p>''' + escape(str(len(protocol['policies']))) + ' policies · ' + escape(', '.join(map(str,protocol['budgets']))) + ' evaluation budgets · ' + str(len(protocol['seeds'])) + ' dependent seed repetitions. Models fit ' + str(protocol['historical_fit_rows']) + ' historical rows after related-family exclusions. All policies use the same target pool and constraints.</p><div class="chart">' + _chart(selection) + '</div><p class="note">Each curve shows the mean best verified feasible speedup over seed runs. No confidence bands: these runs share one workload and its labels. The dashed line is the fully measured pool oracle.</p>' + comparison + '</section><section class="panel"><h2>Uncertainty has limits</h2>' + diagnostics + '<p>Central ensemble ranges can miss measured outcomes. These results do not establish calibrated confidence or broad workload generalization.</p></section><section class="panel"><h2>Evaluation costs stay visible</h2><p>Command wall time, evaluation wall time, and failed-attempt wall time overlap. Read each scope separately; adding them would double count work. Cached replay is not a fresh native evaluation.</p>' + _table(['Workload','Timer category','Phase','Records','Seconds'],cost_rows) + cost_extra + '</section><section class="panel"><h2>Failures are part of the evidence</h2>' + (_table(['Workload','Stage','Recorded failure','Evidence status'],failure_rows) if failure_rows else '<p>No failure records were present in the imported contexts.</p>') + '</section><section class="panel"><h2>What this experiment establishes</h2><ul>' + ''.join('<li>'+escape(x)+'</li>' for x in dict.fromkeys(limits)) + '</ul></section><section class="panel"><h2>Reproducible evidence</h2><p>Raw evidence remains authoritative. This page reads its SQLite analysis projection and sealed selection snapshots. Labels in this analysis view must stay outside selection-policy access.</p>' + provenance + '<details><summary>Selection snapshot identities</summary>' + _table(['Artifact','SHA256'],selection['hashes'].items()) + '</details><details><summary>Frozen selection source identities</summary>' + _table(['Source','SHA256'],protocol.get('source_bindings',{}).items()) + '</details></section></main></html>'


def build(database, selection_dir, output):
    data = ledger.export(database)
    workloads = workload_rows(data)
    selection = load_selection(selection_dir, data, workloads)
    html = render(data, selection)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    return {'output': str(output), 'verified_workload_contexts': len(workloads),
            'prospective_context_id': selection['target_context_id']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--selection-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.db,args.selection_dir,args.output)))
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(2, f'Demo evidence error: {error}\n')


if __name__ == '__main__':
    main()
