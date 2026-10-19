#!/usr/bin/env python3
"""Read-only V9 diagnosis using original 1665 training rows and consumed V8.

No fitting, synthesis, normalization, feature extraction, or label collection.
Only hash-bound feature vectors, targets and frozen forests are inspected.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = next(p for p in (HERE.parent / 'agentic-riscv-codesign', *HERE.parents, Path.cwd())
            if (p / 'isaforge/area_model_v8.py').is_file())
sys.path[:0] = [str(HERE), str(HERE.parent / 'v8-label-audit'), str(REPO)]
import audit
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.tree import DecisionTreeRegressor


def forbidden_fit(*args, **kwargs):
    raise RuntimeError('Read-only diagnosis forbids model fitting')


ExtraTreesRegressor.fit = forbidden_fit
DecisionTreeRegressor.fit = forbidden_fit

VIEWS = {
    'mapping_v6': [*range(194), *range(313, 336)],
    'legacy_original336': [*range(194), *range(313, 336), *range(194, 313)],
    'legacy_rewritten336': [*range(194), *range(313, 336), *range(336, 455)],
    'dual_graph': list(range(194)), 'sog_tuned': list(range(14)),
}
QUERIES = (
    'mul(sub(in0,in1),addi(0,54))',
    'add(mul(in0,addi(0,54)),in1)',
    'mul(in0,addi(0,2025))',
    'mul(sub(andi(in0,63),in1),addi(0,54))',
    'mul(in0,addi(lui(4096),-640))',
    'mul(in0,addi(0,54))',
    'sub(srai(add(in0,in1),5),srai(in1,31))',
)
ALIASES = {'addi': 'add', 'andi': 'and', 'ori': 'or', 'xori': 'xor',
    'slli': 'sll', 'srli': 'srl', 'srai': 'sra', 'slti': 'slt', 'sltiu': 'sltu'}
COMMUTATIVE = {'add', 'and', 'or', 'xor', 'mul'}


def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def has_inputs(node):
    return any(has_inputs(c) for c in node[1:]) if isinstance(node, tuple) else node in ('in0', 'in1')


def walk(node, ancestors=()):
    if isinstance(node, tuple):
        yield node, ancestors
        for child in node[1:]:
            yield from walk(child, ancestors + (node[0],))


def shape(node, generic_inputs=False):
    """Fold constant-only subtrees; ignore constant values; alias immediate ops.

    This is a structural diagnostic, not a feature or equivalence certificate.
    Generic-input mode additionally erases input identity/reuse distinctions.
    """
    if not has_inputs(node):
        return 'C'
    if not isinstance(node, tuple):
        return 'I' if generic_inputs else node
    op = ALIASES.get(node[0], node[0])
    children = [shape(c, generic_inputs) for c in node[1:]]
    if op in COMMUTATIVE:
        children.sort()
    return op + '(' + ','.join(children) + ')'


def record_summary(row, tree):
    events = []
    for node, ancestors in walk(tree):
        if node[0] not in ('mul', 'mulh', 'mulhu', 'mulhsu'):
            continue
        constants = [audit.evaluate(c, 0, 0) for c in node[1:] if not has_inputs(c)]
        events.append({'operation': node[0], 'constant_operands_u32': constants,
            'parent': ancestors[-1] if ancestors else 'ROOT', 'ancestors': list(ancestors),
            'operand_shapes': [shape(c, True) for c in node[1:]]})
    return {**row, 'shape': shape(tree), 'generic_input_shape': shape(tree, True),
            'multiply_events': events}


def np_summary(values):
    values = np.asarray(values, dtype=float)
    return {'min': float(values.min()), 'p05': float(np.quantile(values, .05)),
        'median': float(np.median(values)), 'mean': float(values.mean()),
        'p95': float(np.quantile(values, .95)), 'max': float(values.max())}


def group_of(record):
    events = record['multiply_events']
    if any(e['operation'] != 'mul' for e in events):
        return 'multiply_high'
    if any(e['constant_operands_u32'] for e in events):
        return 'constant_operand_low_multiply'
    if events:
        return 'variable_operand_low_multiply'
    return 'no_multiply'


def support_counts(records):
    op_nodes, constant_nodes, constants, context = Counter(), Counter(), Counter(), Counter()
    rows_by_op = Counter()
    low_constant_rows = []
    shift_rows = []
    for i, record in enumerate(records):
        op_rows = set()
        for event in record['multiply_events']:
            op = event['operation']
            op_rows.add(op)
            op_nodes[op] += 1
            if event['constant_operands_u32']:
                constant_nodes[op] += 1
                if op == 'mul':
                    constants.update(event['constant_operands_u32'])
                    context[event['parent']] += 1
        rows_by_op.update(op_rows)
        if group_of(record) == 'constant_operand_low_multiply':
            low_constant_rows.append(i)
        if 'srai(' in record['formula'] or 'sra(' in record['formula']:
            shift_rows.append(i)
    return {'multiply_node_counts': dict(op_nodes), 'rows_containing_operation': dict(rows_by_op),
        'multiply_constant_node_counts': dict(constant_nodes),
        'low_multiply_constant_operands_u32': dict(sorted(constants.items())),
        'constant_low_multiply_parent_counts': dict(context),
        'constant_low_multiply_rows': [records[i] for i in low_constant_rows],
        'signed_right_shift_row_count': len(shift_rows),
        'groups': dict(Counter(group_of(r) for r in records))}


def feature_collisions(x, y, records):
    groups = defaultdict(list)
    for i, row in enumerate(np.asarray(x, dtype=np.float32)):
        groups[row.tobytes()].append(i)
    conflicts = [ids for ids in groups.values() if len(set(y[ids])) > 1]
    return {'float32_unique_vectors': len(groups),
        'duplicate_vector_group_count': sum(len(ids) > 1 for ids in groups.values()),
        'conflicting_target_group_count': len(conflicts),
        'conflicting_target_row_count': sum(len(ids) for ids in conflicts),
        'irreducible_in_sample_mae_if_only_this_vector': float(sum(np.abs(y[ids] - np.median(y[ids])).sum() for ids in conflicts) / len(y)),
        'largest_conflicting_groups': [
            {'target_span_lut4': float(np.ptp(y[ids])), 'rows': [records[i] for i in ids]}
            for ids in sorted(conflicts, key=lambda ids: -np.ptp(y[ids]))[:8]]}


def nearest(x, query, y, records, names):
    span = np.ptp(x, axis=0)
    live = span > 0
    distance = np.abs(x[:, live] - query[live]) / span[live]
    distance = distance.mean(axis=1)
    ranking = sorted(range(len(records)), key=lambda i: (distance[i], records[i]['formula']))
    same64 = np.flatnonzero(np.all(x == query, axis=1))
    same32 = np.flatnonzero(np.all(x.astype(np.float32) == query.astype(np.float32), axis=1))
    examples = []
    for i in ranking[:5]:
        delta = np.abs(x[i] - query)
        differing = np.flatnonzero(delta != 0)
        biggest = sorted(differing, key=lambda j: -(delta[j] / span[j] if span[j] > 0 else float('inf')))[:8]
        examples.append({'training_row': int(i), **records[i],
            'mean_range_scaled_absolute_distance': float(distance[i]),
            'differing_columns': len(differing),
            'largest_scaled_feature_differences': [{'column': names[j], 'query': float(query[j]),
                'training': float(x[i, j]), 'training_range': float(span[j])} for j in biggest]})
    return {'distance_definition': 'Mean absolute coordinate difference divided by original-training coordinate range; constant training columns excluded. Descriptive, not a learned metric.',
        'nonconstant_training_columns': int(live.sum()),
        'training_exact_float64_collisions': [records[i] for i in same64],
        'training_exact_float32_collisions': [records[i] for i in same32],
        'nearest_training_rows': examples,
        'outside_training_columns': [names[j] for j in range(x.shape[1]) if query[j] < x[:, j].min() or query[j] > x[:, j].max()]}


def forest_trace(estimator, x, query, y, records, names):
    weights = np.zeros(len(records))
    leaves = []
    path_columns = Counter()
    last_columns = Counter()
    last_parent_columns = Counter()
    class_weights = defaultdict(float)
    class_prediction = defaultdict(float)
    q = np.asarray(query, dtype=np.float32).reshape(1, -1)
    for tree_index, tree in enumerate(estimator.estimators_):
        node = int(tree.apply(q)[0])
        training_leaf = tree.apply(x)
        ids = np.flatnonzero(training_leaf == node)
        value = float(tree.tree_.value[node, 0, 0])
        audit.need(len(ids) == tree.tree_.n_node_samples[node] and len(ids) > 0, 'Leaf membership/sample count differs')
        audit.need(abs(float(y[ids].mean()) - value) < 1e-9, 'Leaf target mean differs')
        weights[ids] += 1 / (len(estimator.estimators_) * len(ids))
        path = tree.decision_path(q).indices
        splits = [int(n) for n in path if tree.tree_.children_left[n] != -1]
        for n in splits:
            path_columns[names[tree.tree_.feature[n]]] += 1
        if splits:
            last_columns[names[tree.tree_.feature[splits[-1]]]] += 1
        if len(splits) >= 2:
            last_parent_columns[names[tree.tree_.feature[splits[-2]]]] += 1
        leaves.append({'tree': tree_index, 'leaf': node, 'leaf_prediction': value,
            'training_rows': [int(i) for i in ids], 'leaf_training_count': len(ids),
            'leaf_distinct_targets': len(set(y[ids])),
            'depth': len(splits),
            'last_splits': [{'column': names[tree.tree_.feature[n]], 'threshold': float(tree.tree_.threshold[n]),
                'query_value': float(query[tree.tree_.feature[n]]),
                'training_subtree_count': int(tree.tree_.n_node_samples[n])} for n in splits[-3:]]})
    for i, weight in enumerate(weights):
        name = group_of(records[i])
        class_weights[name] += float(weight)
        class_prediction[name] += float(weight * y[i])
    audit.need(abs(weights.sum() - 1) < 1e-10, 'Leaf influence weights do not sum to one')
    predictions = [r['leaf_prediction'] for r in leaves]
    prediction = float(estimator.predict(q)[0])
    audit.need(abs(float(weights @ y) - prediction) < 1e-9, 'Weighted training target reconstruction differs')
    top = sorted(range(len(records)), key=lambda i: (-weights[i], records[i]['formula']))[:15]
    return {'replayed_point': prediction, 'weighted_training_targets_reconstruct_point': float(weights @ y),
        'tree_predictions': np_summary(predictions),
        'trees_at_or_below_cap64': sum(p <= 64 for p in predictions),
        'trees_in_multisample_leaf': sum(r['leaf_training_count'] > 1 for r in leaves),
        'trees_in_conflicting_target_leaf': sum(r['leaf_distinct_targets'] > 1 for r in leaves),
        'leaf_training_count': np_summary([r['leaf_training_count'] for r in leaves]),
        'training_group_influence_weights': dict(class_weights),
        'training_group_prediction_contributions': dict(class_prediction),
        'top_training_influences': [{'training_row': i, **records[i], 'weight': float(weights[i]),
                                    'prediction_contribution_lut4': float(weights[i] * y[i])} for i in top if weights[i]],
        'path_feature_occurrences': path_columns.most_common(20),
        'last_split_feature_counts': last_columns.most_common(15),
        'second_last_split_feature_counts': last_parent_columns.most_common(15),
        'all_300_tree_leaf_records': leaves}


def run(root):
    paths = {}
    def load(relative):
        path = (root / relative).resolve()
        paths[str(path)] = filehash(path)
        return audit.read(path)
    training = load('training/training-data.json')
    feature_records = load('features.json')
    points = load('point-freeze.json')
    completion = load('measurements/completion.json')
    labels = load('measurements/' + completion['attempt'] + '/labels.json')
    rows = load('rows.json')
    training_rows = [record_summary(r, audit.parse(r['formula'])) for r in training['rows']]
    x = np.asarray(training['values'], dtype=float)
    y = np.asarray([r['lut4_count'] for r in training_rows])
    columns = training['columns']
    audit.need(x.shape == (1665, 455) and feature_records['columns'] == columns, 'Exact original full455 training required')
    fresh = {r['formula']: r for r in feature_records['records']}
    actual = {r['formula']: r['lut4_count'] for r in labels}
    consumed = [record_summary({'formula': f, 'lut4_count': actual[f]}, audit.parse(f)) for f in sorted(fresh)]
    query_outputs = {}
    for formula in QUERIES:
        summary = record_summary({'formula': formula, 'lut4_count': actual[formula]}, audit.parse(formula))
        same_shape = [r for r in training_rows if r['shape'] == summary['shape']]
        generic_shape = [r for r in training_rows if r['generic_input_shape'] == summary['generic_input_shape']]
        query_outputs[formula] = {**summary,
            'exact_original_training_formula_matches': [r for r in training_rows if r['formula'] == formula],
            'same_folded_constant_agnostic_shape': same_shape,
            'same_generic_input_shape': generic_shape,
            'by_model': {}}
    global_collisions = {}
    for model, indices in VIEWS.items():
        entry = points['models'][model]
        model_path = (root / entry['artifact']['path']).resolve()
        audit.need(filehash(model_path) == entry['artifact']['sha256'], 'Frozen model digest differs')
        paths[str(model_path)] = filehash(model_path)
        schema = load(entry['schema']['path'])
        artifact = joblib.load(model_path)
        estimator = artifact.estimator
        audit.need(len(estimator.estimators_) == 300 and estimator.n_features_in_ == len(indices), 'Frozen forest dimensions differ')
        selected = x[:, indices]
        names = [columns[i] for i in indices]
        if 'selected_columns' in schema:
            audit.need(schema['selected_columns'] == names and schema['selected_indices'] == indices, 'Explicit feature selection differs')
        global_collisions[model] = feature_collisions(selected, y, training_rows)
        predicted = load(entry['predictions']['path'])
        frozen_points = {r['formula']: r['predicted_lut4'] for r in predicted}
        for formula in QUERIES:
            query = np.asarray(fresh[formula]['values'])[indices]
            data = nearest(selected, query, y, training_rows, names)
            data.update(forest_trace(estimator, selected, query, y, training_rows, names))
            audit.need(abs(data['replayed_point'] - frozen_points[formula]) < 1e-9, 'Frozen point replay differs')
            data['frozen_point'] = frozen_points[formula]
            data['consumed_v8_float32_collisions'] = [
                {'formula': f, 'actual_lut4': actual[f]} for f, r in fresh.items() if f != formula and
                np.array_equal(np.asarray(r['values'])[indices].astype(np.float32), query.astype(np.float32))]
            query_outputs[formula]['by_model'][model] = data
        audit.need(filehash(model_path) == paths[str(model_path)], 'Frozen artifact mutated')
    # Context coverage for exact cap pattern while allowing shifts/constants and
    # input names to vary is captured by the two declared shape definitions.
    training_support = support_counts(training_rows)
    consumed_support = support_counts(consumed)
    support = {'schema': 'v9-consumed-development-support-diagnosis-v1',
        'scope': 'Read-only diagnosis of original1665 and consumed V8. No fitting or label collection. V8 cannot supply a fresh generalization claim after any tuning.',
        'training_rows': len(training_rows), 'consumed_unique_circuits': len(consumed),
        'training_support': training_support, 'consumed_support': consumed_support,
        'training_feature_collisions': global_collisions, 'queries': query_outputs,
        'feature_distance_and_collision_scope': 'Vector equality is exact after declared float32 casting, matching sklearn input precision; it does not establish functional equivalence. Range-scaled distance is descriptive and trained only on original training ranges.',
        'leaf_influence_scope': 'Each tree contributes its leaf target mean; row weights are sum over trees of 1/(300*leaf_count). These reconstruct the point exactly but are descriptive routing influences, not causal effects.',
        'model_fit_calls': 0, 'new_labels': 0,
        'script_sha256': filehash(__file__), 'oracle_source_sha256': filehash(Path(audit.__file__)),
        'input_files_sha256': paths}
    for path, before in paths.items():
        audit.need(filehash(path) == before, 'Diagnosis input bytes changed')
    return support


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO / 'results/2026-10-15-v8-application-transfer')
    parser.add_argument('--output', type=Path, default=HERE / 'diagnosis.json')
    args = parser.parse_args()
    value = run(args.root.resolve())
    with args.output.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write('\n')
    compact = {'output': str(args.output), 'original_training_support': {k: v for k, v in value['training_support'].items() if k != 'constant_low_multiply_rows'},
        'queries': {f: {'actual': q['lut4_count'], 'same_shape_count': len(q['same_folded_constant_agnostic_shape']),
            'generic_shape_count': len(q['same_generic_input_shape']),
            'models': {name: {'point': r['replayed_point'], 'training_collisions': len(r['training_exact_float32_collisions']),
                'conflicting_leaves': r['trees_in_conflicting_target_leaf'],
                'top_influences': [(n['formula'], n['lut4_count'], n['weight']) for n in r['top_training_influences'][:3]]}
                       for name, r in q['by_model'].items()}} for f, q in value['queries'].items()}}
    print(json.dumps(compact, indent=2))


if __name__ == '__main__':
    main()
