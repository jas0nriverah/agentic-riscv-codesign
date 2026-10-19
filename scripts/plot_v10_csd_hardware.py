#!/usr/bin/env python3
"""Unfrozen presentation helper for the complete fixed V10 paired study.

Actual rendering requires a complete hash-bound collector audit. This script
does not launch tools, fit models, select circuits, or amend experimental files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
CONSTANTS = (11, 44, 85, 340, 341, 511, 1364, 2044)
CONTEXTS = ('direct_product', 'add_after_product', 'sub_before_product', 'masked_sub_before_product')
CONTEXT_LABELS = ('Kx', 'Kx + y', 'K(x − y)', 'K((x & 63) − y)')
ARMS = ('original', 'csd')


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError('Exact nonnegative integer resource counts required')
    return value


def formula(constant, context):
    product = f'mul(in0,addi(0,{constant}))'
    return {'direct_product': product, 'add_after_product': f'add({product},in1)',
        'sub_before_product': f'mul(sub(in0,in1),addi(0,{constant}))',
        'masked_sub_before_product': f'mul(sub(andi(in0,63),in1),addi(0,{constant}))'}[context]


def actual_data(root, audit_path):
    root, audit_path = Path(root).resolve(), Path(audit_path).resolve()
    if (root/'preparation-failure.json').exists():
        raise ValueError('Failed input preparation has no publishable hardware outcome')
    preparation_path = root/'preparation.json';preparation = read(preparation_path)
    if (preparation.get('schema') != 'isaforge-v10-csd-hardware-preparation-v1'
            or preparation.get('status') != 'prepared-inputs-only'
            or preparation.get('new_measurements') != 0 or preparation.get('model_fits') != 0):
        raise ValueError('Completed fixed input-only preparation required')
    paths = [preparation_path, audit_path, Path(__file__).resolve()]
    bound = {}
    for entry in preparation['files']:
        path = (root/entry['path']).resolve()
        if path in bound or sha(path) != entry['sha256']:
            raise ValueError('Duplicate or changed prepared input/source binding')
        bound[path] = entry['sha256'];paths.append(path)
    def bound_read(entry):
        path = (root/entry['path']).resolve()
        if bound.get(path) != entry['sha256']:
            raise ValueError('Input absent from complete preparation bindings')
        return read(path)
    recipe, pairs = bound_read(preparation['recipe']), bound_read(preparation['pairs'])
    if (recipe.get('pairs') != 32 or recipe.get('fresh_synthesis_jobs') != 64
            or recipe.get('model_fits') != 0 or recipe.get('constants') != list(CONSTANTS)
            or recipe.get('contexts') != list(CONTEXTS) or recipe.get('arms') != list(ARMS)
            or recipe['measurement'].get('vectors_per_arm') != 2148
            or recipe['rtl_equivalence'].get('pairs') != 32):
        raise ValueError('Fixed complete32-pair/64-arm recipe required')
    completion_path = root/'measurements/completion.json';completion = read(completion_path)
    attempt = completion['attempt'];stage = root/'measurements'/attempt
    if (completion.get('schema') != 'isaforge-v10-csd-hardware-measurements-v1'
            or completion.get('complete') is not True or completion.get('failures') != []
            or completion.get('pair_count') != 32 or completion.get('universal_actual_rtl_pairs_proved') != 32
            or completion.get('fresh_synthesis_jobs_completed') != 64 or completion.get('planned_fresh_synthesis_jobs') != 64
            or completion.get('vectors_per_arm') != 2148 or completion.get('verification_seed') != 2026101522
            or completion.get('legacy_measurements_reused') is not False or completion.get('new_estimator_fits') != 0
            or completion.get('preparation_sha256') != sha(preparation_path)
            or read(stage/'completion.json') != completion):
        raise ValueError('All32 universal RTL proofs and64 fresh audited arms required')
    for name, key in (('measurement-approval.json', 'approval_sha256'), ('label-release.json', 'release_sha256')):
        if sha(root/name) != completion[key]:
            raise ValueError('Reviewed measurement release changed')
        paths.append(root/name)
    proofs_path, metrics_path = stage/'rtl-equivalence.json', stage/'arm-measurements.json'
    if sha(proofs_path) != completion['rtl_equivalence_sha256'] or sha(metrics_path) != completion['arm_measurements_sha256']:
        raise ValueError('Completed proof/arm record digests differ')
    archive_path = stage/'raw-evidence.json';archive = read(archive_path)
    if (archive.get('schema') != 'isaforge-v10-csd-raw-evidence-v1' or archive.get('attempt') != attempt
            or archive.get('completion_sha256') != sha(stage/'completion.json')
            or archive.get('archive') != 'raw-evidence.zip' or archive.get('archive_sha256') != sha(stage/'raw-evidence.zip')):
        raise ValueError('Raw evidence archive is not bound to this completed attempt')
    proofs, metrics = read(proofs_path), read(metrics_path)
    expected_order = [(constant, context) for constant in CONSTANTS for context in CONTEXTS]
    if len(pairs) != 32 or [(p['constant_u32'], p['context']) for p in pairs] != expected_order:
        raise ValueError('All fixed32 constant/context rows required in declared order')
    pair_ids = {p['pair_id'] for p in pairs}
    proof_index = {p['pair_id']: p for p in proofs}
    metric_index = {(m['pair_id'], m['arm']): m for m in metrics}
    if (len(proofs) != 32 or len(proof_index) != 32 or set(proof_index) != pair_ids
            or any(p.get('proved') is not True or p.get('status') != 'proved' or p.get('returncode') != 0
                   or p.get('timed_out') is not False for p in proofs)
            or len(metrics) != 64 or len(metric_index) != 64
            or set(metric_index) != {(p, arm) for p in pair_ids for arm in ARMS}):
        raise ValueError('Exact32 successful proofs and64 unique arm records required')
    rows, expected_audit_pairs = [], []
    for pair in pairs:
        original = formula(pair['constant_u32'], pair['context'])
        identity = hashlib.sha256(original.encode()).hexdigest()
        if pair['formula'] != original or pair['pair_id'] != 'v10-csd:'+identity:
            raise ValueError('Fixed original formula/identity differs')
        row = {'pair_id': pair['pair_id'], 'source_candidate_id': pair['source_candidate_id'],
            'constant_u32': pair['constant_u32'], 'context': pair['context'],
            'original_formula': original, 'csd_formula': pair['rewritten_formula'],
            'original_formula_sha256': identity, 'arms': {}}
        for arm in ARMS:
            metric = metric_index[pair['pair_id'], arm]
            if (metric.get('actual_rtl_verified') is not True or metric.get('mapped_netlist_verified') is not True
                    or metric.get('vectors_per_arm') != 2148 or metric.get('random_seed') != 2026101522
                    or metric.get('measurement_source') != 'fresh-rtl-synthesis' or metric.get('new_fit') is not False
                    or metric.get('rtl_sha256') != pair['arms'][arm]['rtl']['sha256']
                    or metric.get('formula') != pair['arms'][arm]['formula']):
                raise ValueError('Fresh arm verification/formula identity differs')
            row['arms'][arm] = {'lut4': count(metric['lut4_count']), 'carry': count(metric['carry_count']),
                'rtl_sha256': metric['rtl_sha256'], 'netlist_sha256': metric['netlist_sha256']}
        row['lut4_delta'] = row['arms']['csd']['lut4']-row['arms']['original']['lut4']
        row['carry_delta'] = row['arms']['csd']['carry']-row['arms']['original']['carry']
        rows.append(row)
        expected_audit_pairs.append({'pair_id': pair['pair_id'], 'formula': pair['formula'], 'context': pair['context'],
            'original_lut4': row['arms']['original']['lut4'], 'csd_lut4': row['arms']['csd']['lut4'],
            'csd_minus_original_lut4': row['lut4_delta']})
    audit = read(audit_path)
    if (audit.get('schema') != 'isaforge-v10-paired-hardware-audit-v1' or audit.get('complete') is not True
            or audit.get('failures') != [] or audit.get('fresh_arm_records_recounted') != 64
            or audit.get('sampled_source_and_mapped_comparisons') != 64*2148*2
            or audit['proof_review'].get('records_reviewed') != 32 or audit['proof_review'].get('pairs_proved') != 32
            or audit['proof_review'].get('attempt') != attempt or audit.get('pair_results') != expected_audit_pairs
            or audit.get('mean_csd_minus_original_lut4') != statistics.fmean(r['lut4_delta'] for r in rows)):
        raise ValueError('Complete auditor report must match every paired count and full verification denominator')
    paths += [completion_path, stage/'completion.json', proofs_path, metrics_path, archive_path, stage/'raw-evidence.zip']
    return {'synthetic': False, 'rows': rows, 'attempt': attempt,
        'verification': {'universal_source_pairs': 32, 'universal_actual_rtl_pairs': 32,
            'fresh_synthesis_arms': 64, 'sampled_vectors_per_arm': 2148, 'sampled_rtl_plus_mapped_comparisons': 274944}}, paths


def synthetic_data():
    rows = []
    for i, constant in enumerate(CONSTANTS):
        for j, context in enumerate(CONTEXTS):
            original = 80+13*i+7*j
            delta = (11 if (i+j) % 7 == 0 else -6-9*i+2*j)
            rows.append({'pair_id': f'SYNTHETIC-{i}-{j}', 'constant_u32': constant, 'context': context,
                'original_formula': formula(constant, context), 'csd_formula': 'SYNTHETIC_LAYOUT_ONLY',
                'arms': {'original': {'lut4': original, 'carry': 10+i+j},
                         'csd': {'lut4': original+delta, 'carry': 7+i+j}},
                'lut4_delta': delta, 'carry_delta': -3})
    return {'synthetic': True, 'rows': rows, 'attempt': 'SYNTHETIC — NO MEASUREMENTS'}, [Path(__file__).resolve()]


def summaries(rows, resource):
    changes = [r[resource+'_delta'] for r in rows]
    return {'count': len(rows), 'original_mean': statistics.fmean(r['arms']['original'][resource] for r in rows),
        'csd_mean': statistics.fmean(r['arms']['csd'][resource] for r in rows),
        'mean_delta': statistics.fmean(changes), 'median_delta': statistics.median(changes),
        'minimum_delta': min(changes), 'maximum_delta': max(changes),
        'wins': sum(d < 0 for d in changes), 'ties': changes.count(0), 'losses': sum(d > 0 for d in changes)}


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 13,
        'axes.labelsize': 11, 'xtick.labelsize': 10, 'ytick.labelsize': 11,
        'axes.spines.top': False, 'axes.spines.right': False,
        'figure.facecolor': 'white', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'svg.hashsalt': 'isaforge-v10-csd-hardware'})
    rows = data['rows'];lut = summaries(rows, 'lut4');carry = summaries(rows, 'carry')
    original = np.array([r['arms']['original']['lut4'] for r in rows]).reshape(8, 4)
    csd = np.array([r['arms']['csd']['lut4'] for r in rows]).reshape(8, 4)
    delta = csd-original;limit = max(1, int(abs(delta).max()));maximum = max(1, int(max(original.max(), csd.max())))
    title = 'SYNTHETIC LAYOUT — NO EXPERIMENTAL RESULTS' if data['synthetic'] else 'V10 · fixed CSD implementation versus original RTL'
    title_color = '#A13E31' if data['synthetic'] else '#1D2832'
    fig = plt.figure(figsize=(16.8, 11.8));grid = fig.add_gridspec(2, 3, height_ratios=[1.8, 1], hspace=.46, wspace=.42)
    fig.subplots_adjust(left=.065, right=.965, top=.83, bottom=.105)
    fig.suptitle(title, x=.04, ha='left', y=.976, fontsize=20, color=title_color)
    fig.text(.04, .932, 'All 32 fixed constant/context pairs · 64 fresh original/CSD synthesis arms · no predictor fit or circuit selection', fontsize=12)
    fig.text(.04, .898, 'Wrapping unsigned32 arithmetic · isolated iCE40 LUT4 resource proxy · consumed development study', fontsize=11, color='#48515C')
    for i, (matrix, label) in enumerate(((original, 'A  Original LUT4'), (csd, 'B  CSD LUT4'), (delta, 'C  Paired Δ LUT4 · CSD − original'))):
        ax = fig.add_subplot(grid[0, i])
        kwargs = {'cmap': 'RdBu_r', 'norm': TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)} if i == 2 else {'cmap': 'viridis', 'vmin': 0, 'vmax': maximum}
        picture = ax.imshow(matrix, aspect='auto', **kwargs)
        ax.set_title(label, loc='left', pad=15);ax.set_yticks(range(8), [str(c) for c in CONSTANTS])
        ax.set_ylabel('Constant K');ax.set_xticks(range(4), CONTEXT_LABELS, rotation=22, ha='right')
        ax.set_xticks(np.arange(-.5, 4), minor=True);ax.set_yticks(np.arange(-.5, 8), minor=True)
        ax.grid(which='minor', color='white', linewidth=1.4);ax.tick_params(which='minor', bottom=False, left=False)
        for (y, x), value in np.ndenumerate(matrix):
            rgba = picture.cmap(picture.norm(value));luminance = .2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            ax.text(x, y, f'{value:+d}' if i == 2 else str(value), ha='center', va='center', fontsize=12,
                color='black' if luminance > .57 else 'white')
        bar = fig.colorbar(picture, ax=ax, fraction=.047, pad=.035)
        bar.set_label('CSD − original LUT4' if i == 2 else 'LUT4 count')
    ax = fig.add_subplot(grid[1, 0]);ys = np.arange(4)
    values = [statistics.fmean(r['lut4_delta'] for r in rows if r['context'] == c) for c in CONTEXTS]
    ax.barh(ys, values, color=['#B14E45' if v > 0 else '#2C719E' for v in values], height=.58)
    ax.set_yticks(ys, CONTEXT_LABELS);ax.invert_yaxis();ax.axvline(0, color='#273642', linewidth=1)
    low, high = min(0, min(values)), max(0, max(values));span = max(1, high-low)
    ax.set_xlim(low-.25*span, high+.3*span);ax.grid(axis='x', color='#E1E5E9', linewidth=.7);ax.set_axisbelow(True)
    for y, value in zip(ys, values):
        ax.text(value+(.02*span if value >= 0 else -.02*span), y, f'{value:+.2f}', va='center', ha='left' if value >= 0 else 'right')
    ax.set_title('D  Descriptive context means · 8 pairs each', loc='left', pad=16)
    ax.set_xlabel('CSD − original LUT4; negative favors CSD')
    ax = fig.add_subplot(grid[1, 1]);ax.axis('off')
    table_rows = []
    for label, key in (('Original mean', 'original_mean'), ('CSD mean', 'csd_mean'), ('Mean paired Δ', 'mean_delta'),
        ('Median paired Δ', 'median_delta'), ('Minimum / maximum Δ', None), ('Wins / ties / losses', 'counts')):
        values = []
        for stats in (lut, carry):
            if key is None: text = f"{stats['minimum_delta']:+d} / {stats['maximum_delta']:+d}"
            elif key == 'counts': text = f"{stats['wins']} / {stats['ties']} / {stats['losses']}"
            else: text = f'{stats[key]:.2f}'
            values.append(text)
        table_rows.append([label, *values])
    table = ax.table(cellText=table_rows, colLabels=['All 32 pairs', 'LUT4', 'Carry'], colWidths=[.56, .25, .25],
        cellLoc='right', loc='upper center', bbox=[-.08, .03, 1.14, .94])
    table.auto_set_font_size(False);table.set_fontsize(10.5)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor('#D5DCE2');cell.set_linewidth(.5)
        if row == 0: cell.set_facecolor('#EAF0F4');cell.set_text_props(weight='bold')
        elif row % 2 == 0: cell.set_facecolor('#F4F7F9')
        if column == 0: cell.set_text_props(ha='left')
    ax.set_title('E  Primary LUT4 · carry descriptive', loc='left', pad=16)
    ax = fig.add_subplot(grid[1, 2]);ax.axis('off');ax.set_title('F  Verification and scope', loc='left', pad=16)
    text = ('LAYOUT VALUES ARE INVENTED.\nNo hardware outcomes are shown.\nRequired, not yet observed:\n\n' if data['synthetic'] else '')
    text += ('32 universal source QF_BV proofs\n32 universal actual-RTL pair proofs\n64 fresh synthesis arms, all retained\n\n'
             'Per arm: 100 boundary + 2,048 seeded\nsamples at RTL and mapped netlist.\nMapped verification is sampled.\n\n'
             'No population confidence interval;\nno device timing or CPU speedup claim.')
    ax.text(0, .97, text, transform=ax.transAxes, va='top', fontsize=11, linespacing=1.42, color=title_color if data['synthetic'] else '#36434E')
    fig.text(.04, .035, 'x = in0; y = in1. Negative Δ reduces LUT4. Original and CSD heatmaps share a zero-based scale; paired Δ uses a symmetric scale.\nAll fixed pairs and losses shown. Full formulas, both arm counts and evidence hashes are in figure-data.json / figure-manifest.json.', fontsize=10, color='#48515C')
    figures = [('v10-csd-paired-hardware', fig)]
    table_fig, axes = plt.subplots(1, 2, figsize=(17.5, 10.2));table_fig.subplots_adjust(left=.035, right=.97, top=.84, bottom=.1, wspace=.1)
    table_fig.suptitle(title+' · full paired table', x=.035, ha='left', y=.976, fontsize=19, color=title_color)
    table_fig.text(.035, .919, 'Every constant/context pair · wrapping unsigned32 arithmetic · Δ = CSD − original · LUT4 primary, carry descriptive', fontsize=12)
    for half, ax in enumerate(axes):
        ax.axis('off');shown = rows[16*half:16*(half+1)]
        cells = [[str(r['constant_u32']), CONTEXT_LABELS[CONTEXTS.index(r['context'])],
            str(r['arms']['original']['lut4']), str(r['arms']['csd']['lut4']), f"{r['lut4_delta']:+d}",
            f"{r['arms']['original']['carry']} → {r['arms']['csd']['carry']}", f"{r['carry_delta']:+d}"] for r in shown]
        table = ax.table(cellText=cells, colLabels=['K', 'Original context', 'Orig.\nLUT4', 'CSD\nLUT4', 'Δ\nLUT4', 'Carry\norig. → CSD', 'Δ\ncarry'],
            colWidths=[.08, .3, .1, .1, .1, .17, .09], cellLoc='center', bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False);table.set_fontsize(10.5)
        for (row, column), cell in table.get_celld().items():
            cell.set_edgecolor('#D5DCE2');cell.set_linewidth(.6)
            if row == 0: cell.set_facecolor('#EAF0F4');cell.set_text_props(weight='bold')
            elif ((row-1)//4) % 2 == 1: cell.set_facecolor('#F1F5F8')
            if row > 0 and column == 4:
                cell.set_text_props(color='#A03C33' if shown[row-1]['lut4_delta'] > 0 else '#185E8C', weight='bold')
    table_fig.text(.035, .035, 'Fixed eight-constant × four-context grid. No pair filtering or outcome-based rewrite selection. No population CI, device timing or CPU speedup claim.\nUniversal actual-RTL pair equality is separate from 2,148 sampled mapped-netlist checks per arm. Full original/CSD formulas remain in figure-data.json.', fontsize=10.5, color='#48515C')
    figures.append(('v10-csd-full-paired-table', table_fig))
    files = []
    for name, figure in figures:
        for extension in ('png', 'svg', 'pdf'):
            path = output/(name+'.'+extension);figure.savefig(path, dpi=220, facecolor='white', bbox_inches='tight', pad_inches=.2);files.append(path)
        plt.close(figure)
    return files


def run(root, audit_path, output, *, synthetic=False):
    output = Path(output).resolve()
    if synthetic and not output.is_relative_to(ROOT/'generated'):
        raise ValueError('Synthetic layout must stay under generated/')
    data, paths = synthetic_data() if synthetic else actual_data(root, audit_path)
    output.mkdir(parents=True, exist_ok=False)
    data['summaries'] = {resource: summaries(data['rows'], resource) for resource in ('lut4', 'carry')}
    data['by_constant'] = {str(constant): {resource: summaries([r for r in data['rows'] if r['constant_u32'] == constant], resource)
        for resource in ('lut4', 'carry')} for constant in CONSTANTS}
    data['by_context'] = {context: {resource: summaries([r for r in data['rows'] if r['context'] == context], resource)
        for resource in ('lut4', 'carry')} for context in CONTEXTS}
    data_path = output/'figure-data.json';write(data_path, data)
    files = render(data, output)
    manifest = {'schema': 'isaforge-v10-csd-hardware-figure-manifest-v1', 'synthetic': synthetic,
        'source_files': [{'path': str(p), 'sha256': sha(p)} for p in sorted(set(paths))],
        'figure_data': {'path': data_path.name, 'sha256': sha(data_path)},
        'figures': [{'path': p.name, 'sha256': sha(p)} for p in files],
        'scope': 'Complete fixed32 paired isolated-datapath LUT4 study; carry descriptive; no population inference or CPU timing claim.'}
    write(output/'figure-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--synthetic-layout-only', action='store_true')
    args = parser.parse_args()
    if not args.synthetic_layout_only and (args.root is None or args.audit is None):
        parser.error('Actual results require --root and --audit')
    print(json.dumps(run(args.root, args.audit, args.output, synthetic=args.synthetic_layout_only), indent=2))
