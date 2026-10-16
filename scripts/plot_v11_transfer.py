#!/usr/bin/env python3
"""Prospective V11b-E1 figures from caller-authenticated scoring inputs.

This helper does not admit a cohort. Actual mode requires a caller-reviewed
payload digest; synthetic mode is visibly marked on every figure. A path uses
its exact byte SHA256; a dict uses sorted compact JSON (allow_nan=False).
Optional overlap is the input stager's global-original overlap.json; identity
channels are expanded through saved memberships. Its digest
must also be reviewed in actual mode. No models or native jobs are invoked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_v11_transfer as scoring

COLORS = {'V6': '#687887', 'V9': '#147D92'}
FAMILY_NAMES = {'arbitrary-precision-bit-strings': 'Bit strings', 'audio-beamforming': 'Audio beamforming',
                'numeric-template-matching': 'Template matching', 'fm-reception': 'FM reception',
                'integer-recurrences': 'Integer recurrences'}
CHANNELS = ('canonical', 'direct', 'component')
SCOPE = ('Frozen V6/V9 · V11b-E1 · original RTL mapped to iCE40 LUT4. '
         'Inputs exposed before withheld labels; chronology/admission must be authenticated upstream. '
         'Shared originals retain program memberships. Descriptive fixed panel; no population CI, CPU timing or safety claim.')


def need(ok, message):
    if not ok: raise ValueError(message)


def digest(body): return hashlib.sha256(body).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def sha(path): return digest(Path(path).read_bytes())


def read_input(value):
    if type(value) is dict or type(value) is list:
        return json.loads(canonical(value)), digest(canonical(value))
    body = Path(value).read_bytes()
    def unique(items):
        result = {}
        for k, v in items:
            need(k not in result, 'Duplicate JSON key'); result[k] = v
        return result
    return json.loads(body, object_pairs_hook=unique), digest(body)


def check_review(actual, reviewed, synthetic, name):
    need(synthetic or reviewed == actual, 'Explicit caller-reviewed '+name+' SHA256 required; internal consistency is not cohort admission')


def prepare_data(payload, *, synthetic_preview=False, reviewed_payload_sha256=None,
                 overlap=None, reviewed_overlap_sha256=None):
    need(type(synthetic_preview) is bool, 'Explicit boolean synthetic-preview marker required')
    inputs, payload_hash = read_input(payload)
    check_review(payload_hash, reviewed_payload_sha256, synthetic_preview, 'payload')
    core = {'outcomes', 'membership', 'labels', 'predictions'}
    need(type(inputs) is dict and core <= set(inputs) <= core | {'metadata'}, 'score() inputs plus optional metadata required')
    result = scoring.score(**{k: inputs[k] for k in core})
    need(result['coverage']['empty_programs'] == ['recursion'], 'Fixed V11 reporting contract requires explicit empty recursion')
    families = list(result['per_family'])
    lofo = []
    for omitted in families:
        scores = {m: scoring.mean([result['per_family'][f]['equal_eligible_program_mae'][m] for f in families if f != omitted]) for m in scoring.MODELS}
        lofo.append({'omitted_family': omitted, 'retained_families': 4, **scores, 'delta_v9_minus_v6': scores['V9'] - scores['V6']})
    y = {r['id']: r['lut4'] for r in inputs['labels']}
    p = {m: {r['id']: r['prediction'] for r in inputs['predictions'][m]} for m in scoring.MODELS}
    ids = sorted(y)
    points = [{'id': i, 'actual': y[i], **{m: p[m][i] for m in scoring.MODELS}} for i in ids]
    familiarity = None; overlap_hash = None; records = None
    if overlap is not None:
        overlap_payload, overlap_hash = read_input(overlap)
        check_review(overlap_hash, reviewed_overlap_sha256, synthetic_preview, 'overlap')
        need(type(overlap_payload) is dict and overlap_payload.get('schema') == 'isaforge-v11-input-overlap-v1', 'Input-stager overlap schema required')
        need(type(overlap_payload.get('reference_original_count')) is int and overlap_payload['reference_original_count'] == 2929, 'Fixed pre-reservation reference must contain 2929 originals')
        records = overlap_payload['records']
        need(type(records) is list and len(records) == len(ids), 'Exactly one global-original overlap record per score ID required')
        by_id = {}
        def forms(values):
            need(type(values) is list and all(type(v) is str and v for v in values) and len(set(values)) == len(values), 'Distinct declared identity strings required')
            return set(values)
        for r in records:
            identity = r['candidate_id']
            need(identity in y and identity not in by_id, 'Missing/extra/duplicate overlap original'); flags = {}
            need(type(r['pre_reservation_canonical_seen']) is bool, 'Strict canonical familiarity boolean required')
            match = r['pre_reservation_matches']
            saved = forms(match['saved_accepted_form']); v4 = forms(match['frozen_commutative_v4_normalization'])
            closed = forms(match['accepted_identity_component_originals']); forms(match['ordered_skeleton'])
            need(saved | v4 <= closed, 'Direct identities must be contained in accepted components')
            need(not r['pre_reservation_canonical_seen'] or r['formula'] in saved, 'Canonical original missing from saved identities')
            flags['pre_reservation'] = {'canonical': r['pre_reservation_canonical_seen'], 'saved_alias': bool(saved),
                'v4_alias': bool(v4), 'direct': bool(saved | v4), 'component': bool(closed)}
            need(set(r['training_overlap']) == set(scoring.MODELS), 'Both model training overlap channels required')
            for model in scoring.MODELS:
                item = r['training_overlap'][model]
                need(type(item['canonical_seen']) is bool, 'Strict training canonical boolean required')
                direct = forms(item['declared_alias_originals']); component = forms(item['accepted_identity_component_originals'])
                need(direct <= component <= closed and direct <= saved | v4, 'Training identities must be subsets of declared reference identities')
                need(not item['canonical_seen'] or r['formula'] in direct, 'Canonical training identity absent from direct channel')
                flags[model] = {'canonical': item['canonical_seen'], 'direct': bool(direct), 'component': bool(component)}
            by_id[identity] = flags
        familiarity = {}
        for reference in ('pre_reservation', 'V6', 'V9'):
            familiarity[reference] = {}
            channels = ('canonical', 'saved_alias', 'v4_alias', 'direct', 'component') if reference == 'pre_reservation' else CHANNELS
            for channel in channels:
                cell = {}
                for name, flag in (('familiar', True), ('unfamiliar', False)):
                    group = [i for member in inputs['membership'] for i in member['canonical_ids'] if by_id[i][reference][channel] is flag]
                    cell[name] = {'membership_count': len(group), 'unique_original_count': len(set(group)),
                                  'metrics': scoring.paired(group, y, p)}
                familiarity[reference][channel] = cell
    return {'schema': 'isaforge-v11-transfer-figure-data-v1', 'synthetic_preview': synthetic_preview,
            'admission': 'SYNTHETIC preview; invented layout fixture only' if synthetic_preview else 'Caller-reviewed digests supplied; plotter does not independently authenticate experiment admission',
            'payload_sha256': payload_hash, 'overlap_sha256': overlap_hash, 'scope': SCOPE,
            'scoring_inputs': inputs, 'score': result, 'global_unique_points': points,
            'leave_one_family_out': lofo, 'familiarity': familiarity, 'overlap_records': records,
            'source_sha256': {'plotter': sha(__file__), 'unchanged_pure_scorer': sha(scoring.__file__),
                              'reporting_plan': sha(Path(__file__).resolve().parents[1]/'docs/v11-comparison-reporting-plan.md')}}


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 13,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.axisbelow': True,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42, 'svg.hashsalt': 'v11-transfer', 'figure.facecolor': 'white'})
    output = Path(output); result = data['score']; coverage = result['coverage']; files = []
    mark = 'SYNTHETIC · ' if data['synthetic_preview'] else ''
    footer = ('SYNTHETIC layout fixture; no V11 observations. ' if data['synthetic_preview'] else '') + 'Frozen V6/V9 · V11b-E1 · iCE40 original-RTL LUT4; descriptive, no CI or CPU timing claim.'
    def heading(fig, title, subtitle):
        fig.suptitle(mark + title, x=.055, y=.98, ha='left', fontsize=19, color='#20323F')
        fig.text(.055, .922, subtitle, fontsize=10.5, color='#475761')
        fig.text(.055, .035, footer, fontsize=9, color='#475761')
    def save(fig, name):
        for suffix in ('png', 'svg', 'pdf'):
            path = output/(name+'.'+suffix); fig.savefig(path, dpi=200, facecolor='white'); files.append(path)
        plt.close(fig)
    def legend(fig):
        fig.legend([plt.Line2D([], [], marker='o', ls='', color=COLORS[m], markersize=8) for m in scoring.MODELS],
                   ['Frozen '+m for m in scoring.MODELS], loc='upper right', bbox_to_anchor=(.95, .985), ncol=2, frameon=False)
    families = list(result['per_family'])
    fig, ax = plt.subplots(figsize=(12, 7.4)); fig.subplots_adjust(left=.29, right=.94, top=.84, bottom=.27)
    heading(fig, 'Primary and family area error', 'Equal family / equal eligible-program MAE; negative Δ (V9 − V6) favors V9.'); legend(fig)
    pairs = [result['primary']['scores']] + [result['per_family'][f]['equal_eligible_program_mae'] for f in families]
    labels = ['E1 primary · five families'] + [FAMILY_NAMES[f]+'\n'+str(len(result['per_family'][f]['eligible_programs']))+' eligible program; '+str(result['per_family'][f]['program_formula_rows'])+' memberships' for f in families]
    maximum = max(c[m] for c in pairs for m in scoring.MODELS)
    for i, cell in enumerate(pairs):
        ax.plot([cell['V6'], cell['V9']], [i, i], color='#B8C3CC', lw=2)
        for m, shift in (('V6', -.065), ('V9', .065)): ax.scatter(cell[m], i+shift, s=62, color=COLORS[m], zorder=3)
        ax.text(maximum*1.04 if maximum else .05, i, f"Δ {cell['delta_v9_minus_v6']:+.2f}", va='center', fontsize=10)
    ax.set_yticks(range(6), labels); ax.invert_yaxis(); ax.set_xlim(0, maximum*1.25 if maximum else 1); ax.set_xlabel('Mean absolute error · LUT4 (zero baseline)'); ax.grid(axis='x', color='#E1E7EB')
    fig.text(.055, .105, f"{coverage['unique_canonical_originals']} unique physical targets; {coverage['program_formula_rows']} memberships. Complete: ammunition, audiobeam, pm, fmref, fac; recursion empty (error unavailable).\nOriginal equal-all-program endpoint remains undefined. E1 gives the eligible factorial program the recurrence-family weight.", fontsize=9.5)
    save(fig, '01-primary-families')

    fig, axes = plt.subplots(1, 2, figsize=(12, 7)); fig.subplots_adjust(left=.09, right=.96, top=.83, bottom=.28, wspace=.18)
    heading(fig, 'Measured versus predicted area', f"Every global original once (N={len(data['global_unique_points'])}); identical zero-preserving scales, all outliers retained.")
    points = data['global_unique_points']; maximum = max(v[k] for v in points for k in ('actual', 'V6', 'V9')); upper = max(1, maximum*1.13)
    for ax, model in zip(axes, scoring.MODELS):
        ax.scatter([r['actual'] for r in points], [r[model] for r in points], color=COLORS[model], alpha=.65, s=28, edgecolors='none', rasterized=True, clip_on=False)
        ax.plot([0, upper], [0, upper], color='#485963', ls='--', lw=1, label='Identity')
        ax.set_xscale('symlog', linthresh=1); ax.set_yscale('symlog', linthresh=1)
        ax.set_xlim(0, upper); ax.set_ylim(0, upper); ax.set_aspect('equal'); ax.set_title('Frozen '+model, loc='left'); ax.set_xlabel('Measured LUT4 · symlog (linear 0–1)'); ax.grid(color='#E1E7EB', alpha=.6)
    axes[0].set_ylabel('Predicted LUT4 · symlog (linear 0–1)')
    fig.text(.09, .105, 'Dashed line: prediction = measurement. Zero targets and zero predictions remain visible; no percent-error substitution.\nUnique-original display; pooled errors retain every membership. Inputs exposed before withheld labels; upstream audits authenticate chronology.', fontsize=9.5)
    save(fig, '02-measured-predicted')

    fig, axes = plt.subplots(1, 2, figsize=(14, 7.7)); fig.subplots_adjust(left=.08, right=.97, top=.83, bottom=.33, wspace=.32)
    heading(fig, 'Membership tails and fixed-cap mistakes', f"Membership weighting · n={coverage['program_formula_rows']}; repeated formulas keep every program membership."); legend(fig)
    names = [('P90 AE','absolute_error_p90'), ('P95 AE','absolute_error_p95'), ('P99 AE','absolute_error_p99'), ('Max AE','maximum_absolute_error'), ('Max under','maximum_underprediction')]
    x = np.arange(len(names)); pooled = result['pooled_membership_metrics']; rows = []
    for m, offset in (('V6', -.18), ('V9', .18)):
        axes[0].bar(x+offset, [pooled[m][k] for _, k in names], .32, color=COLORS[m])
        for cap in scoring.CAPS:
            c = pooled[m]['cap_decisions'][str(cap)]
            rows.append([m, str(cap), str(c['false_accept_count']), str(c['false_reject_count']), str(c['all_rows_denominator']), str(c['truly_feasible_denominator']), str(c['predicted_feasible_denominator'])])
    axes[0].set_xticks(x, [n for n, _ in names], rotation=20, ha='right'); axes[0].set_ylabel('Absolute / underprediction error · LUT4'); axes[0].set_ylim(bottom=0); axes[0].grid(axis='y', color='#E1E7EB'); axes[0].set_title('All membership tails', loc='left')
    axes[1].axis('off'); axes[1].set_title('Cap errors and explicit denominators', loc='left')
    table = axes[1].table(cellText=rows, colLabels=['Model','Cap','FA','FR','All n','True\nfeasible','Pred.\nfeasible'], loc='center', cellLoc='center', colWidths=[.14,.10,.09,.09,.13,.20,.22])
    table.auto_set_font_size(False); table.set_fontsize(10); table.scale(1, 2.2)
    summaries = []
    for m in scoring.MODELS:
        c = pooled[m]; z = 'unavailable' if c['zero_area_mae'] is None else f"{c['zero_area_mae']:.3f}"
        summaries.append(f"{m}: pooled MAE {c['mae']:.3f}; bias {c['bias_prediction_minus_actual']:+.3f}; RMSLE {c['rmsle']:.3f}; zero n={c['zero_area_count']}, zero MAE={z}")
    fig.text(.08, .14, '\n'.join(summaries)+'\nFA: predicted ≤ cap, actual > cap. FR: actual ≤ cap, predicted > cap. Infeasible denominators = all n − feasible.', fontsize=10)
    fig.text(.08, .075, 'All caps fixed prospectively at 32 / 64 / 128 LUT4. These counts do not establish calibrated safety or instruction-selector quality.', fontsize=9.5)
    save(fig, '03-tails-caps')

    fig, axes = plt.subplots(1, 2, figsize=(14, 7.7)); fig.subplots_adjust(left=.20, right=.97, top=.82, bottom=.23, wspace=.45)
    heading(fig, 'Sensitivity and familiarity diagnostics', 'All five omissions retained; leave-one-family-out values are sensitivity diagnostics, not a confidence interval.')
    lofo = data['leave_one_family_out']; values = [r['delta_v9_minus_v6'] for r in lofo]
    axes[0].barh(range(5), values, color=['#147D92' if v < 0 else '#B45E4A' for v in values]); axes[0].set_yticks(range(5), [FAMILY_NAMES[r['omitted_family']] for r in lofo]); axes[0].invert_yaxis(); axes[0].axvline(0, color='#485963', lw=1)
    extent = max(map(abs, values), default=0) or 1; axes[0].set_xlim(-1.25*extent, 1.25*extent); axes[0].set_xlabel('Omitting named family: Δ MAE (V9 − V6)'); axes[0].grid(axis='x', color='#E1E7EB')
    for i, v in enumerate(values): axes[0].text(extent*1.08, i, f'{v:+.2f}', ha='right', va='center', fontsize=9)
    axes[1].axis('off'); axes[1].set_title('Familiarity · diagnostic counts only', loc='left')
    if data['familiarity'] is None:
        axes[1].text(0, .60, 'Overlap records not supplied.\nNo familiarity or novelty inference.', fontsize=12)
    else:
        rows = []
        for reference, label in (('pre_reservation','Pre-reservation'), ('V6','V6 training'), ('V9','V9 training')):
            for channel in data['familiarity'][reference]:
                cell = data['familiarity'][reference][channel]
                rows.append([label, channel.replace('_', ' ').replace('v4', 'V4'), str(cell['familiar']['membership_count']), str(cell['unfamiliar']['membership_count']), str(cell['familiar']['unique_original_count'])])
        table = axes[1].table(cellText=rows, colLabels=['Reference','Channel','Seen\nrows','Unseen\nrows','Seen\nunique'], loc='center', cellLoc='center', colWidths=[.32,.25,.14,.15,.15]); table.auto_set_font_size(False); table.set_fontsize(9); table.scale(1, 1.7)
    fig.text(.08, .135, 'Canonical / saved alias / V4 alias / direct union / component identity are distinct; skeleton matches are never identity.\nBoth familiarity strata and their counts/errors (empty = unavailable) are retained at full precision in figure-data.json.', fontsize=10)
    fig.text(.08, .075, 'Shared formulas, helpers and source ancestry prevent treating memberships or omission results as independent replications.', fontsize=9.5)
    save(fig, '04-sensitivity-overlap')
    return files


def run(payload, output_dir, *, synthetic_preview=False, reviewed_payload_sha256=None,
        overlap=None, reviewed_overlap_sha256=None):
    data = prepare_data(payload, synthetic_preview=synthetic_preview, reviewed_payload_sha256=reviewed_payload_sha256,
                        overlap=overlap, reviewed_overlap_sha256=reviewed_overlap_sha256)
    output = Path(output_dir); need(not output.exists(), 'Fresh figure output directory required'); output.mkdir(parents=True)
    data_path = output/'figure-data.json'; data_path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    files = render(data, output)
    manifest = {'schema': 'isaforge-v11-transfer-figure-manifest-v1', 'synthetic_preview': synthetic_preview,
                'scope': data['scope'], 'admission': data['admission'], 'payload_sha256': data['payload_sha256'],
                'overlap_sha256': data['overlap_sha256'], 'source_sha256': data['source_sha256'],
                'files': [{'path': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size} for p in [data_path, *files]]}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def synthetic_fixture():
    """Invented, small layout fixture. Never reads actual V11 evidence."""
    outcomes = []; membership = []; labels = []; predictions = {m: [] for m in scoring.MODELS}
    ys = [0, 1, 16, 31, 32, 63, 64, 127, 128, 400, 3000]
    for i, y in enumerate(ys):
        identity = 'SYNTHETIC-'+str(i); labels.append({'id':identity, 'lut4':y})
        for m, value in [('V6', max(0, y*.8 + (i%3)*9)), ('V9', max(0, y*1.1 - (i%4)*12))]: predictions[m].append({'id':identity, 'prediction':value})
    for i, (name, family) in enumerate(scoring.PROGRAM_FAMILIES.items()):
        ids = [] if name == 'recursion' else ['SYNTHETIC-'+str(j) for j in sorted({i, i+5, 0})]
        outcomes.append({'program':name, 'family':family, 'status':'complete' if ids else 'empty', 'canonical_count':len(ids)})
        membership.append({'program':name, 'canonical_ids':ids})
    # Keep all global IDs represented; largest outlier belongs to ammunition.
    membership[0]['canonical_ids'].append('SYNTHETIC-10'); outcomes[0]['canonical_count'] += 1
    payload = {'outcomes':outcomes, 'membership':membership, 'labels':labels, 'predictions':predictions}
    records = []
    for i in range(len(ys)):
        formula = 'SYNTHETIC-formula-'+str(i); seen = i%3 == 0
        direct = [formula] if seen else (['SYNTHETIC-reference-'+str(i)] if i%3 == 1 else [])
        component = direct or ['SYNTHETIC-reference-component-'+str(i)]
        records.append({'candidate_id':'SYNTHETIC-'+str(i), 'formula':formula,
            'pre_reservation_canonical_seen':seen, 'pre_reservation_matches':{'saved_accepted_form':direct,
            'frozen_commutative_v4_normalization':direct, 'accepted_identity_component_originals':component,
            'ordered_skeleton':['SYNTHETIC-structural-only']}, 'training_overlap':{m:{'canonical_seen':seen,
            'declared_alias_originals':direct, 'accepted_identity_component_originals':component} for m in scoring.MODELS}})
    return payload, {'schema':'isaforge-v11-input-overlap-v1', 'reference_original_count':2929, 'records':records}



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reviewed-payload-sha256'); parser.add_argument('--overlap', type=Path); parser.add_argument('--reviewed-overlap-sha256')
    parser.add_argument('--synthetic-preview', action='store_true')
    args = parser.parse_args()
    if args.synthetic_preview and args.payload is None:
        payload, overlap = synthetic_fixture(); need(args.overlap is None, 'Built-in synthetic fixture includes its overlap')
    else:
        need(args.payload is not None, 'A reviewed payload or explicit built-in synthetic preview required'); payload, overlap = args.payload, args.overlap
    run(payload, args.output, synthetic_preview=args.synthetic_preview, reviewed_payload_sha256=args.reviewed_payload_sha256,
        overlap=overlap, reviewed_overlap_sha256=args.reviewed_overlap_sha256)
