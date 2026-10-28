"""Render sealed nanocobs selection results without fitting or native jobs."""
from __future__ import annotations
import argparse
import csv
import platform
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from isaforge import codesign as c

RESULTS = ROOT / 'results/2026-10-28-nanocobs-v2-selection-r1'
OUTPUT = Path(__file__).resolve().parent
CAP = 64
LABELS = dict(frequency='Frequency', merit='Merit', calibrated_latency='Calibrated latency',
    latency_cost_heuristic='Latency / cost', random='Random', ranking='Pairwise XGBoost',
    raw_regression='Raw regression', normalized_xgb='Normalized XGBoost',
    feasible_benefit_xgb='Feasible-benefit XGBoost',
    factorized_feasibility_xgb='Factorized XGBoost',
    hybrid_gp_zero_shot='GP zero shot', hybrid_gp_adapt='GP paid updates',
    codex_chat_agent_hybrid_memory='LLM relay (one episode)')
AGENT = 'codex_chat_agent_hybrid_memory'
CONVENTIONAL = {'frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic', 'random'}


def reduction(speedup):
    return 100 * (1 - 1 / speedup)


def load_results(root):
    root = Path(root).resolve()
    manifest = c.unseal(root / 'manifest.json')
    for name, digest in manifest.items():
        path = (root / name).resolve()
        c.require(path.is_relative_to(root) and path.is_file() and c.sha(path) == digest,
                  'Sealed result changed: ' + name)
    return dict(report=c.unseal(root / 'study-report.json'),
        outcomes=c.unseal(root / 'outcomes.json'), audit=c.unseal(root / 'native-audit.json'),
        policies=c.unseal(root / 'factorized-policy-report.json'),
        manifest_sha256=c.sha(root / 'manifest.json'))


def candidate_rows(data):
    audit = data['audit']
    c.require(len(audit['public']) == len(audit['pool_names']) == len(data['outcomes']),
              'Complete candidate roster required')
    names = {row['candidate_id']: name for row, name in zip(audit['public'], audit['pool_names'])}
    c.require(set(names) == {row['candidate_id'] for row in data['outcomes']}, 'Candidate IDs differ')
    selected = data['report']['agent']['selected_id']
    attempted = set(data['report']['agent']['attempted_ids'])
    rows = []
    for item in data['outcomes']:
        success = item.get('status', 'success') == 'success'
        feasible = success and item['correctness_verified'] and item['device_fits'] and (
            item['area_delta_lut4'] <= CAP and item['routed_fmax_min_mhz'] >= 12)
        row = dict(candidate=names[item['candidate_id']], candidate_id=item['candidate_id'],
            formula=item['formula'], status=item.get('status', 'success'),
            baseline_cycles=item.get('baseline_cycles'), candidate_cycles=item.get('candidate_cycles'),
            speedup=item.get('speedup'), cycle_reduction_percent=(reduction(item['speedup']) if success else None),
            added_lut4=item.get('area_delta_lut4'), total_lut4=item.get('area'),
            min_routed_fmax_mhz=item.get('routed_fmax_min_mhz'),
            correctness_verified=item.get('correctness_verified'), device_fits=item.get('device_fits'),
            feasible_at_plus64=bool(feasible), reference_censored=item.get('reference_censored', False),
            measured_by_live_agent=item['candidate_id'] in attempted, selected_by_live_agent=item['candidate_id'] == selected,
            measurement_seconds=item['measurement_seconds'])
        rows.append(row)
    return sorted(rows, key=lambda row: row['candidate'])


def budget_rows(data):
    report, policies = data['report'], data['policies']
    runs = [row for row in policies['runs'] if row.get('cap', row.get('area_delta_lut4_cap')) == CAP]
    rows = []
    for policy in sorted({row['policy'] for row in runs}):
        selected = [row for row in runs if row['policy'] == policy]
        budgets = sorted({point['budget'] for row in selected for point in row['curve']})
        for budget in budgets:
            points = [next(p for p in row['curve'] if p['budget'] == budget) for row in selected]
            values = [reduction(point['best_speedup']) for point in points]
            summary = next(s for s in policies['summary'] if s['policy'] == policy and
                s.get('cap', s.get('area_delta_lut4_cap')) == CAP and s['budget'] == budget)
            rows.append(dict(policy=policy, budget=budget, dependent_seed_count=len(points),
                mean_cycle_reduction_percent=statistics.mean(values), min_cycle_reduction_percent=min(values),
                max_cycle_reduction_percent=max(values), mean_best_speedup=summary['mean_best_speedup'],
                mean_measurement_seconds=summary['mean_target_measurement_seconds'],
                cycle_reduction_regret=summary.get('mean_cycle_reduction_regret'),
                actual_attempts_used=budget, scope='posthoc charged-prefix replay; seeds dependent'))
    for point in report['agent']['budget_endpoints']:
        value = 100 * point['best_so_far_cycle_reduction']
        rows.append(dict(policy=AGENT, budget=point['budget'], dependent_seed_count=1,
            mean_cycle_reduction_percent=value, min_cycle_reduction_percent=value,
            max_cycle_reduction_percent=value, mean_best_speedup=point['best_verified_feasible_speedup'],
            mean_measurement_seconds=report['agent']['target_measurement_seconds'],
            cycle_reduction_regret=point.get('cycle_reduction_regret'),
            actual_attempts_used=point['actual_attempts_used'],
            scope='one live episode; terminal choice carried forward after early stop'))
    return rows


def write_csv(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def save(fig, output, name):
    fig.savefig(output / (name + '.png'), dpi=220, facecolor='white')
    fig.savefig(output / (name + '.svg'), facecolor='white')
    svg = output / (name + '.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    plt.close(fig)


def plot_budget(data, rows, output):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), sharey=True)
    colors = plt.get_cmap('tab10').colors
    for ax, conventional in zip(axes, (True, False)):
        keys = sorted({r['policy'] for r in rows if r['policy'] != AGENT and
                       (r['policy'] in CONVENTIONAL) == conventional})
        for index, key in enumerate(keys):
            series = sorted((r for r in rows if r['policy'] == key), key=lambda r: r['budget'])
            x = [r['budget'] for r in series]
            ax.plot(x, [r['mean_cycle_reduction_percent'] for r in series],
                color=colors[index], marker=['o','s','^','D','v','P','X'][index % 7],
                linewidth=1.5, markersize=5, alpha=.85, label=LABELS.get(key, key))
        agent = sorted((r for r in rows if r['policy'] == AGENT), key=lambda r: r['budget'])
        ax.plot([r['budget'] for r in agent], [r['mean_cycle_reduction_percent'] for r in agent],
            color='#121c2a', marker='*', markerfacecolor='white', markersize=12, linewidth=2.2,
            linestyle='--', label=LABELS[AGENT], zorder=8)
        actual = [r for r in agent if r['budget'] <= data['report']['agent']['charged_attempts']]
        ax.scatter([r['budget'] for r in actual], [r['mean_cycle_reduction_percent'] for r in actual],
            color='#121c2a', marker='*', s=170, zorder=9)
        oracle = data['report'].get('oracle_speedup')
        if oracle is not None:
            ax.axhline(reduction(oracle), color='#7b8692', linestyle=':', linewidth=1.1,
                       label='Complete-pool feasible oracle')
        ax.set(title='Conventional controls' if conventional else 'Existing learned controls',
               xlabel='Paid-evaluation budget cap', xticks=[1,2,3])
        ax.grid(alpha=.2)
        ax.spines[['top','right']].set_visible(False)
        ax.legend(loc='upper center', bbox_to_anchor=(.5,-.16), ncol=2, frameon=False, fontsize=8)
    axes[0].set_ylabel('Best verified feasible cycle reduction (%)')
    fig.suptitle('Nanocobs: matched-budget selection at +64 LUT4 and 12 MHz', fontsize=14)
    fig.text(.5,.865,'Replay curves: five dependent seeds; relay: one episode. Dashed relay line carries an early-stop choice forward.',
             ha='center', fontsize=9, color='#4f5e6b')
    fig.subplots_adjust(bottom=.31, top=.80, wspace=.15)
    save(fig, output, 'budgeted-selection')


def plot_tradeoff(rows, output):
    fig, ax = plt.subplots(figsize=(9,5.5), constrained_layout=True)
    successes = [r for r in rows if r['status'] == 'success']
    for feasible, color, label in ((True,'#258474','Feasible at +64 LUT4 / 12 MHz'),
                                   (False,'#c27144','Outside feasibility constraints')):
        selected = [r for r in successes if r['feasible_at_plus64'] == feasible]
        ax.scatter([r['added_lut4'] for r in selected], [r['cycle_reduction_percent'] for r in selected],
            c=color, s=65, label=label, zorder=3)
    for row in successes:
        ax.annotate(row['candidate'].replace('candidate_','C'),
            (row['added_lut4'],row['cycle_reduction_percent']), xytext=((-19, 10) if row['candidate'] == 'candidate_02' else (5, -13) if row['candidate'] == 'candidate_03' else (5, 5)),
            textcoords='offset points', fontsize=9)
        if row['selected_by_live_agent']:
            ax.scatter([row['added_lut4']], [row['cycle_reduction_percent']], s=210,
                facecolors='none', edgecolors='#162432', linewidths=1.8, label='Relay selection', zorder=5)
    ax.axvline(CAP, color='#162432', linestyle='--', linewidth=1.3, label='+64 LUT4 cap')
    ax.axhline(0, color='#84909b', linewidth=.8)
    ax.set(title='Nanocobs: measured area and whole-program benefit', xlabel='Added LUT4 cells',
           ylabel='Measured whole-program cycle reduction (%)')
    ax.grid(alpha=.2)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    save(fig, output, 'candidate-tradeoff')


def display(value, digits=3):
    if value is None:
        return '—'
    return f'{value:.{digits}f}' if isinstance(value, float) else str(value)


def build(results=RESULTS, output=OUTPUT):
    results, output = Path(results).resolve(), Path(output).resolve()
    data = load_results(results)
    candidates, budgets = candidate_rows(data), budget_rows(data)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'candidates.csv', candidates)
    write_csv(output / 'matched-budgets.csv', budgets)
    plot_budget(data, budgets, output)
    plot_tradeoff(candidates, output)
    report = data['report']
    agent = report['agent']
    budget_cap = max(row['budget'] for row in agent['budget_endpoints'])
    decisions = len(agent.get('model_events', []))
    lines = ['# Nanocobs selection: measured comparison', '',
        f"Prelabel commit `{report['prelabel_commit']}`; {len(candidates)} one-attempt candidate outcomes. "
        f"Complete measured reference: **{report['complete_measured_reference_pool']}**. "
        f"The relay used **{report['agent']['charged_attempts']}** paid attempts in one episode.", '',
        'The non-agent results are posthoc replays on the same measured pool, with only each policy’s paid prefix revealed. '
        'Five dependent policy seeds are not five independent workloads. Physical oracle collection and policy replay costs are separate. '
        'A dashed relay curve carries an early-stop result into larger budget caps; it adds no measurements.', '',
        f"The agent used {agent['charged_attempts']} of {budget_cap} allowed paid evaluations; {budget_cap-agent['charged_attempts']} remained unused. "
        f"There were {decisions} logged model decisions. The provider_calls field ({agent.get('provider_calls', 'unavailable')}) is bridge API telemetry, not a count of model decisions. "
        f"Live measurement cost was {display(agent.get('target_measurement_seconds'))} seconds; the enclosing evaluation-wrapper cost was {display(agent.get('target_outer_operation_seconds'))} seconds. These overlap and must not be summed.", '',
        '![Matched budgets](budgeted-selection.png)', '', '![Area and benefit](candidate-tradeoff.png)', '',
        '## Every candidate', '',
        '| Candidate | Status | Cycles | Reduction % | Added LUT4 | Min MHz | Feasible +64 | Seconds |',
        '|---|---|---:|---:|---:|---:|---|---:|']
    for row in candidates:
        lines.append('| ' + ' | '.join(display(row[k]) for k in (
            'candidate','status','candidate_cycles','cycle_reduction_percent','added_lut4',
            'min_routed_fmax_mhz','feasible_at_plus64','measurement_seconds')) + ' |')
    lines += ['', 'Full formulas, identities, self-check/device status and relay membership are in [candidates.csv](candidates.csv).', '',
        '## Same-budget comparison at +64 LUT4', '',
        '| Policy | B1 reduction % | B2 reduction % | B3 reduction % | Scope |',
        '|---|---:|---:|---:|---|']
    for policy in sorted({r['policy'] for r in budgets}):
        series = {r['budget']:r for r in budgets if r['policy'] == policy}
        values = [display(series[b]['mean_cycle_reduction_percent']) if b in series else '—' for b in (1,2,3)]
        lines.append('| ' + ' | '.join([LABELS.get(policy,policy), *values,
            'One live relay episode' if policy == AGENT else 'Five dependent replay seeds (mean)']) + ' |')
    lines += ['', 'No general superiority or multi-instruction improvement follows from one fixed workload. '
        'The timed region includes the scalar reference and checker; their shared source limits correctness coverage, supplemented by the independent fixed-input host oracle. '
        'Unknown outcomes remain censored; a complete-pool oracle is reported only when available.', '',
        'The original frozen verifier omitted the SQLite action-context count; the [separate verification amendment](../../results/2026-10-28-nanocobs-selection-verification-r1/README.md) preserves the failure and successful full replay with the corrected verifier.', '', '## Reproduction', '', '```sh',
        '.venv/bin/python scripts/verify_nanocobs_selection.py',
        '.venv/bin/python reports/2026-10-28-nanocobs-selection/build_report.py', '```', '',
        f"Input sealed manifest SHA256: `{data['manifest_sha256']}`. "
        'This builder verifies result hashes and performs no model fitting, native jobs or LLM calls.']
    (output / 'README.md').write_text('\n'.join(lines) + '\n')
    c.seal(output / 'report-provenance.json', dict(
        input_manifest_sha256=data['manifest_sha256'], script_sha256=c.sha(__file__),
        python=platform.python_version(), matplotlib=matplotlib.__version__,
        artifacts={p.name:c.sha(p) for p in sorted(output.iterdir()) if p.is_file() and
                   p.name not in ('report-provenance.json','report-provenance.json.sha256','build_report.py')}))
    return dict(candidates=len(candidates), budget_rows=len(budgets), output=str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=RESULTS)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(build(args.results, args.output))
