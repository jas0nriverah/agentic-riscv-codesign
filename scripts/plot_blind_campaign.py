"""Plot seven predeclared policies from authenticated blind-campaign tables.

The method list is fixed before viewing blind policy results. This presenter
uses source-specific means of five dependent seeds, with no confidence bands,
model fitting, native jobs, posthoc policy choice or cross-source aggregation.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import budgeted_selection as b, codesign as c
from isaforge import factorized_selection_experiment as experiment
from scripts.report_blind_campaign import POLICY_LABELS
from scripts.reproduce_guarded_sha256 import _manifest

# Predeclared while serial blind collection was still running. Never change
# these representatives based on the target curves or replace them with winners.
METHODS = ('frequency', 'merit', 'calibrated_latency', 'latency_cost_heuristic',
           'random', 'hybrid_gp_adapt', 'factorized_feasibility_xgb')
LABELS = ('Frequency', 'Instruction merit', 'Calibrated latency', 'Latency + cost',
          'Random', 'Adaptive GP', 'Fixed feasibility classifier')
COLORS = ('#0072B2', '#E69F00', '#009E73', '#CC79A7', '#999999', '#D55E00', '#332288')
MARKERS = ('o', 's', '^', 'D', 'x', 'v', 'P')
STYLES = ('-', '--', '-.', ':', '--', '-.', '-')
REPORT = ROOT/'generated/reproduction/blind-report'


def _number(value, name):
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError('Finite numeric '+name+' required') from None
    c.require(math.isfinite(result), 'Finite numeric '+name+' required')
    return result


def _boolean(value):
    c.require(value in ('True', 'False'), 'Explicit reference completeness required')
    return value == 'True'


def read_curves(report):
    """Use the derived mean of per-seed cycle reductions, never mean speedup."""
    report = Path(report).resolve()
    _manifest(report)
    c.require(set(METHODS[:-1]) <= set(b.POLICIES) and METHODS[-1] == experiment.POLICY,
              'Predeclared method identities differ from frozen policy keys')
    with (report/'endpoints.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    sources = sorted({row['workload_group'] for row in rows})
    c.require(1 <= len(sources) <= 3, 'One to three complete independent sources required')
    expected = {(source, policy, cap, budget) for source in sources for policy in POLICY_LABELS
                for cap in (32, 64, 128) for budget in (1, 2, 3)}
    actual = [(row['workload_group'], row['policy'], int(row['cap']), int(row['budget'])) for row in rows]
    c.require(len(actual) == len(expected) and set(actual) == expected,
              'Complete unique twelve-policy source/cap/budget table required')
    c.require(all(int(row['dependent_seed_count']) == 5 for row in rows),
              'Exactly five dependent seed means required')
    curves = []
    for source in sources:
        selected = [row for row in rows if row['workload_group'] == source and int(row['cap']) == 64]
        references = {_number(row['reference_cycle_reduction'], 'reference cycle reduction') for row in selected}
        complete = {_boolean(row['reference_complete']) for row in selected}
        c.require(len(references) == len(complete) == 1, 'One reference per source/cap required')
        reference = next(iter(references))
        c.require(0 <= reference < 1, 'Reference must be a fractional cycle reduction')
        methods = []
        for policy, label in zip(METHODS, LABELS):
            values = sorted((row for row in selected if row['policy'] == policy), key=lambda row: int(row['budget']))
            gains = [0.0]+[_number(row['mean_verified_cycle_reduction'], 'mean verified cycle reduction') for row in values]
            c.require(all(0 <= gain <= reference+1e-12 for gain in gains) and
                      all(lower <= upper+1e-12 for lower, upper in zip(gains, gains[1:])),
                      'Verified cycle reduction must be nondecreasing and bounded by reference')
            methods.append(dict(policy=policy, label=label, queries=[0, 1, 2, 3],
                mean_verified_cycle_reduction=gains, mean_verified_cycle_reduction_percent=[100*gain for gain in gains]))
        curves.append(dict(workload_group=source, reference_cycle_reduction=reference,
            reference_complete=next(iter(complete)),
            reference_kind='measured declared-pool oracle' if next(iter(complete)) else 'best verified; full-pool optimum censored',
            methods=methods))
    return curves


def build(report, output):
    report, output = Path(report).resolve(), Path(output).resolve()
    c.require(not output.exists() and not output.is_relative_to(report),
              'Fresh plot output outside the authenticated report required')
    curves = read_curves(report)
    clock_path = report/'clock-accounting.json'
    clock = c.unseal(clock_path) if clock_path.exists() else None
    if clock is not None:
        c.require(clock['contract'] == 'isaforge-blind-monotonic-accounting-v1' and
                  clock['phase'] == 'post-collection accounting amendment' and
                  clock['actual_calendar_wall_seconds'] is None,
                  'Explicit qualified clock accounting must remain attached to the plot')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MaxNLocator, ScalarFormatter

    with plt.rc_context({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False}):
        figure, axes = plt.subplots(1, len(curves), figsize=(max(10, 4.15*len(curves)), 5.0), squeeze=False)
        for axis, source in zip(axes[0], curves):
            for index, method in enumerate(source['methods']):
                axis.plot(method['queries'], method['mean_verified_cycle_reduction_percent'],
                    label=method['label'], color=COLORS[index], marker=MARKERS[index],
                    linestyle=STYLES[index], linewidth=1.8 if index == len(METHODS)-1 else 1.25,
                    markersize=5, markerfacecolor='white' if index < 4 else COLORS[index],
                    markeredgewidth=1.05, zorder=3+index/10)
            reference = 100*source['reference_cycle_reduction']
            axis.axhline(reference, color='#222222', linestyle=(0, (5, 3)), linewidth=1.1, zorder=2)
            reference_label = 'Pool oracle' if source['reference_complete'] else 'Best verified (censored)'
            axis.text(.03, .96, f'{reference_label}: {reference:.5g}%', transform=axis.transAxes,
                      va='top', fontsize=8, color='#222222')
            axis.set_title(source['workload_group'], fontsize=10, pad=10)
            axis.set_xlabel('Charged candidate attempts')
            axis.set_ylabel('Verified whole-program cycle reduction (%)')
            axis.set_xticks([0, 1, 2, 3])
            axis.set_xlim(-.08, 3.08)
            axis.set_ylim(0, reference*1.22 if reference > 0 else .01)
            axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
            formatter = ScalarFormatter(useOffset=False)
            formatter.set_powerlimits((-3, 4))
            axis.yaxis.set_major_formatter(formatter)
            axis.grid(axis='y', color='#DDDDDD', linewidth=.6)
            axis.set_axisbelow(True)
        handles = [Line2D([0], [0], color=color, marker=marker, linestyle=style,
                         label=label, markersize=5) for color, marker, style, label
                   in zip(COLORS, MARKERS, STYLES, LABELS)]
        handles.append(Line2D([0], [0], color='#222222', linestyle=(0, (5, 3)), label='Declared-pool reference'))
        figure.suptitle('Blind source selection: +64 LUT4, minimum routed Fmax 12 MHz', y=.98, fontsize=12)
        figure.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, .12), ncol=4,
                      frameon=False, fontsize=8, columnspacing=1.8)
        figure.text(.5, .065, 'Means across five dependent seeds; no confidence intervals. Each panel starts at 0; vertical scales differ.',
                    ha='center', fontsize=8)
        figure.text(.5, .038, 'Coincident curves overlap. Seven methods were fixed before results; all 12 policies remain in the report tables.',
                    ha='center', fontsize=8)
        figure.text(.5, .012,
            'Clock accounting is qualified: original strict-check failures are retained; uninterrupted calendar wall time is unknown.'
            if clock is not None else 'The plot shows charged attempt counts; no elapsed-time advantage is claimed.',
            ha='center', fontsize=8)
        figure.subplots_adjust(left=.075 if len(curves) > 1 else .17, right=.98, bottom=.35, top=.84, wspace=.36)
        output.mkdir(parents=True)
        for suffix in ('png', 'svg', 'pdf'):
            figure.savefig(output/('blind-primary-curves.'+suffix), dpi=220,
                           metadata={'Creator': 'ISAForge predeclared blind-campaign plot'})
        plt.close(figure)
    metadata = dict(schema='isaforge-blind-primary-plot-v1',
        input_report=str(report), input_manifest_sha256=c.sha(report/'manifest.json'),
        input_endpoints_sha256=c.sha(report/'endpoints.csv'), plot_source_sha256=c.sha(Path(__file__)),
        clock_accounting_sha256=c.sha(clock_path) if clock is not None else None,
        clock_accounting=clock,
        policies=list(METHODS), omitted_policies_present_in_tables=[policy for policy in POLICY_LABELS if policy not in METHODS],
        method_selection='Fixed while blind collection was running, before blind policy results; no posthoc best-policy selection.',
        area_delta_lut4_cap=64, minimum_routed_fmax_mhz=12, budgets=[0, 1, 2, 3],
        y_axis='100 times mean across five dependent seeds of (1 - 1 / best verified feasible speedup)',
        baseline_at_query_zero=0, independent_unit='source workload', confidence_intervals=False,
        vertical_scales='Separate source panels, each starting at zero.', curves=curves,
        reference_scope='Declared measured candidate pool; censored references are best verified lower bounds on the unresolved optimum.',
        new_model_fits=0, new_native_jobs=0,
        outputs={path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    c.seal(output/'metadata.json', metadata)
    c.seal(output/'manifest.json', {path.name: c.sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return dict(sources=len(curves), plotted_policies=len(METHODS), formats=['png', 'svg', 'pdf'],
                new_model_fits=0, new_native_jobs=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=REPORT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.report, args.output))


if __name__ == '__main__':
    main()
