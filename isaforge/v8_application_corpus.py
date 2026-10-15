"""Input-only coverage and overlap accounting for application transfer.

Identity matches establish related inputs under declared tests. Absence of a
match does not prove functional novelty. Equivalent originals keep separate
physical area targets; shared formulas keep every program membership.
"""
from __future__ import annotations
from collections import defaultdict
import copy
import hashlib
import json
import math
import struct

from .features import parse_formula
from . import area_model_v8 as v8
from . import structural_features_v5 as legacy
from . import semantic_features_v7 as semantic
from .v5_corpus import equivalence_key, skeleton


def vector_key(values):
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError('Finite vector required')
    return hashlib.sha256(b''.join(struct.pack('!d', float(v) if v else 0.) for v in values)).hexdigest()


def application_rows(programs):
    """Accept complete extractor pools, retaining all occurrences and helpers."""
    result = []
    seen_programs = set()
    for spec, candidates in programs:
        name = spec['benchmark']
        if (not isinstance(name, str) or not name or not isinstance(spec['family'], str) or not spec['family']
                or name in seen_programs or type(spec['primary_family']) is not bool):
            raise ValueError('Unique programs and explicit primary-family role required')
        seen_programs.add(name)
        if not candidates:
            raise ValueError('Zero-candidate program is a coverage failure: ' + name)
        trace = spec['traceTotalInstructions']
        if type(trace) is not int or trace <= 0:
            raise ValueError('Positive integer complete computation trace count required')
        seen = set()
        for candidate in candidates:
            formula = parse_formula(candidate['formula']).canonical()
            if formula in seen:
                raise ValueError('Extractor must provide one canonical formula per program')
            seen.add(formula)
            if type(candidate['traceTotalInstructions']) is not int or candidate['traceTotalInstructions'] != trace:
                raise ValueError('Candidate uses a different trace denominator')
            for key in ('runs', 'overlapSafeSaved'):
                if type(candidate[key]) is not int or not 0 <= candidate[key] <= trace:
                    raise ValueError('Invalid dynamic candidate count: ' + key)
            if not candidate.get('occurrences'):
                raise ValueError('Complete occurrence evidence required')
            identifier = hashlib.sha256(formula.encode()).hexdigest()
            result.append({**copy.deepcopy(candidate), 'formula': formula, 'candidate_id': name + ':' + identifier,
                           'benchmark': name, 'family': spec['family'],
                           'primary_family': spec['primary_family']})
    return sorted(result, key=lambda r: (r['benchmark'], r['formula']))


def append_rewritten(record):
    """Extend an already bound frozen V6 input record, without any target I/O."""
    if (len(record['values']) != 336 or any(isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) or v < 0 for v in record['values'])):
        raise ValueError('Frozen V6 full336 input required')
    modes = copy.deepcopy(semantic.analyze_modes(record['formula'], budget=v8.PROOF_BUDGET))
    normalized = modes['combined']['normalized_formula']
    features = legacy.feature_dict(normalized)
    return {**copy.deepcopy(record), 'values': [*record['values'], *(features[n] for n in legacy.FEATURE_NAMES)],
            'v7_combined_normalized_formula': normalized, 'v7_modes': modes}


def identity_channels(record):
    formula = parse_formula(record['formula']).canonical()
    old_normal = parse_formula(record['normalized_formula']).canonical()
    new_normal = parse_formula(record['v7_combined_normalized_formula']).canonical()
    values = record['values']
    if len(values) != 455:
        raise ValueError('Full455 identity evidence required')
    forms = {formula, old_normal, new_normal}
    result = {
        'canonical': {formula},
        'original_or_normalized': forms,
        'commutative_normalized': {equivalence_key(f) for f in forms},
        'ordered_skeleton': {skeleton(f) for f in forms},
    }
    for view in v8.VIEWS:
        result[view + '_vector'] = {vector_key([values[i] for i in v8.view_indices(view)])}
    return result


def novelty_ledger(consumed, fresh):
    """Report all channels separately; never remove a familiar primary row."""
    index = defaultdict(lambda: defaultdict(set))
    seen = set()
    for record in consumed:
        formula = parse_formula(record['formula']).canonical()
        if formula in seen:
            raise ValueError('Consumed registry must be canonical unique')
        seen.add(formula)
        for channel, keys in identity_channels(record).items():
            for key in keys:
                index[channel][key].add(formula)
    rows = []
    fresh_seen = set()
    for record in fresh:
        formula = parse_formula(record['formula']).canonical()
        if formula in fresh_seen:
            raise ValueError('Fresh feature registry must be canonical unique')
        fresh_seen.add(formula)
        matches = {}
        for channel, keys in identity_channels(record).items():
            matches[channel] = sorted({f for key in keys for f in index[channel].get(key, ())})
        rows.append({'formula': formula, 'matches': matches,
                     'no_declared_identity_match': not any(matches[c] for c in
                         ('canonical', 'original_or_normalized', 'commutative_normalized')),
                     'strict_no_declared_match': not any(matches.values())})
    return {'schema': 'isaforge-v8-input-novelty-v1', 'consumed_unique_formulas': len(seen),
            'fresh_unique_formulas': len(fresh_seen), 'records': rows,
            'primary_rows_removed': 0,
            'scope': 'No match under these declared tests does not prove functional novelty. '
                     'Feature/skeleton matches are diagnostic, not equivalence proofs. '
                     'Strict no-match secondary excludes every listed channel; complete primary retains all rows.'}
