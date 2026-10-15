#!/usr/bin/env python3
"""Render all fixed V10d pairs only after a fresh portable raw-evidence audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_v10d_hardware as verifier
import plot_v10_csd_hardware as presentation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Use a fresh figure directory; preserve earlier outputs')
    audit = verifier.run(root)
    if not audit['complete'] or audit['status'] != 'pass' or audit['failures']:
        raise ValueError('Incomplete hardware comparison has no primary result figure')
    pairs = presentation.read(root / 'pairs.json')
    counts = {row['pair_id']: row for row in audit['pairs']}
    if len(pairs) != len(counts) or len(counts) != 32:
        raise ValueError('All 32 audited pairs are required')
    rows = []
    for pair in pairs:
        value = counts[pair['pair_id']]
        rows.append({
            'pair_id': pair['pair_id'], 'source_candidate_id': pair['source_candidate_id'],
            'constant_u32': pair['constant_u32'], 'context': pair['context'],
            'original_formula': pair['formula'], 'csd_formula': pair['rewritten_formula'],
            'arms': {'original': {'lut4': value['original_lut4'], 'carry': value['original_carry']},
                     'csd': {'lut4': value['csd_lut4'], 'carry': value['csd_carry']}},
            'lut4_delta': value['csd_minus_original_lut4'],
            'carry_delta': value['csd_minus_original_carry'],
            'prior_v9_comparison': {k: v for k, v in value.items()
                                    if k.startswith(('prior_', 'fresh_minus_prior_'))},
        })
    data = {'synthetic': False, 'study': 'V10d', 'rows': rows,
            'proof_method': 'Shared reviewed modular-algebra checker on authenticated native RTL frontends',
            'raw_measurement_audit': 'Independent concrete word, source RTL, mapped netlist and resource replay',
            'first_attempt': 'V10c: 16 SAT passes, 16 timeouts, zero area jobs; preserved separately',
            'verification': {'source_pairs': 32, 'actual_rtl_pairs': audit['rtl_pairs_proved_shared_checker'],
                             'fresh_synthesis_arms': audit['arms_recounted'],
                             'source_and_mapped_sample_comparisons': audit['source_and_mapped_sample_comparisons']},
            'summaries': {resource: presentation.summaries(rows, resource) for resource in ('lut4', 'carry')},
            'audited_summary': audit['summary']}
    output.mkdir(parents=True)
    presentation.write(output / 'independent-audit.json', audit)
    presentation.write(output / 'figure-data.json', data)
    figures = presentation.render(data, output)
    (output / 'captions.md').write_text(
        'All 32 fixed constant/context pairs, with fresh original and CSD mappings. '
        'LUT4 changes are primary; carry counts remain separate. Universal source proofs '
        'are inherited unchanged. Actual RTL equality is established by the reviewed '
        'word-level checker on native Yosys frontend JSON, with independently sampled '
        'word/RTL/mapped output checks. The first SAT attempt remains recorded with '
        '16 passes and 16 timeouts. No circuit filtering, model fit, timing, power, '
        'CPU speedup, population confidence interval or independent transfer claim.\n')
    sources = [Path(__file__), Path(verifier.__file__), Path(presentation.__file__),
               root / 'preparation.json', root / 'measurement-approval.json', root / 'label-release.json',
               root / 'measurements/completion.json']
    sources += list((root / 'measurements/attempt-0000').glob('*.json'))
    sources += [root / 'measurements/attempt-0000/raw-evidence.zip']
    manifest = {'schema': 'isaforge-v10d-publication-figures-v1', 'synthetic': False,
                'source_files': [{'path': str(p.resolve()), 'sha256': sha(p)} for p in sorted(set(sources))],
                'files': [{'path': p.name, 'sha256': sha(p)} for p in sorted(output.iterdir()) if p.is_file()],
                'figure_count': len(figures), 'pair_count': len(rows)}
    presentation.write(output / 'figure-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.output), indent=2))
