"""Render the read-only diagnosis and inspect existing frozen feature values."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diagnose_support as ds


FEATURES = (
    'sog_and_count', 'sog_or_count', 'sog_not_count', 'sog_xor_count', 'sog_estimated_total_area',
    'original_gate_count', 'original_word_mul_count', 'original_word_multiply_operand_bits',
    'original_word_multiply_partial_terms_proxy', 'mapping_selected_cover_gate_count',
    'v5_norm_v3_mul_constant_adder_bits', 'v5_norm_v3_mul_constant_csd_terms',
    'v5_original_mul_constant_operands', 'v5_original_mul_constant_popcount',
    'v5_original_mul_constant_digits', 'v5_norm_v3_adder_sum_bits',
    'v5_norm_v3_adder_carry_bits', 'v5_norm_v3_adder_carry_run_max')


def main():
    full_bytes = ((HERE / 'diagnosis.json').read_bytes() if (HERE / 'diagnosis.json').exists()
                  else gzip.decompress((HERE / 'diagnosis.json.gz').read_bytes()))
    data = json.loads(full_bytes)
    ds.audit.need(data['script_sha256'] == ds.filehash(HERE / 'diagnose_support.py'), 'Diagnosis source differs')
    for formula, query in data['queries'].items():
        for model, record in query['by_model'].items():
            ds.audit.need(not record['training_exact_float64_collisions'] and not record['training_exact_float32_collisions']
                          and not record['consumed_v8_float32_collisions'], 'Unexpected query collision')
            if model != 'sog_tuned':
                ds.audit.need(record['trees_in_conflicting_target_leaf'] == 0, 'Conflicting-target leaf found')
    root = ds.REPO / 'results/2026-10-15-v8-application-transfer'
    training = ds.audit.read(root / 'training/training-data.json')
    features = ds.audit.read(root / 'features.json')
    vectors = {r['formula']: v for r, v in zip(training['rows'], training['values'])}
    vectors.update({r['formula']: r['values'] for r in features['records']})
    columns = training['columns']
    snapshot = {}
    reference_formulas = [
        'mul(in0,addi(0,84))',
        'mul(in0,addi(lui(1103515648),-403))',
        'xor(addi(mulhsu(andi(in1,63),srai(in0,31)),7),andi(in0,3412423858))',
    ]
    for formula in [*ds.QUERIES, *reference_formulas]:
        vector = vectors[formula]
        snapshot[formula] = {n: vector[columns.index(n)] for n in FEATURES}
        snapshot[formula]['original_vs_rewritten119_changed_coordinates'] = sum(a != b for a, b in zip(vector[194:313], vector[336:455]))
        if formula in data['queries']:
            snapshot[formula]['per_model_semantic_splits_in_last_three_levels'] = {}
            for model in ('legacy_original336', 'legacy_rewritten336'):
                paths = data['queries'][formula]['by_model'][model]['all_300_tree_leaf_records']
                names = [split['column'] for record in paths for split in record['last_splits']]
                snapshot[formula]['per_model_semantic_splits_in_last_three_levels'][model] = {
                    'semantic_split_count': sum(n.startswith(('v5_', 'rewritten_')) for n in names),
                    'all_split_count': len(names)}
    (HERE / 'feature-snapshots.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    proposed = []
    constants = sorted(c * scale for c in (11, 85, 341, 511) for scale in (1, 4))
    for constant in constants:
        for context, formula in (
            ('direct_product', f'mul(in0,addi(0,{constant}))'),
            ('add_after_product', f'add(mul(in0,addi(0,{constant})),in1)'),
            ('sub_before_product', f'mul(sub(in0,in1),addi(0,{constant}))'),
            ('masked_sub_before_product', f'mul(sub(andi(in0,63),in1),addi(0,{constant}))'),
        ):
            proposed.append({'formula': formula, 'context': context, 'constant_u32': constant})
    shifts = (1, 2, 3, 4, 8, 12, 24, 30)
    for shift in shifts:
        for operation in ('add', 'sub'):
            proposed.append({'formula': f'sub(srai({operation}(in0,in1),{shift}),srai(in1,31))',
                'context': operation + '_signed_shift_sign_sub', 'shift': shift})
    known = {r['formula'] for r in training['rows']} | {r['formula'] for r in features['records']}
    ds.audit.need(len(proposed) == len({r['formula'] for r in proposed}) == 48, 'Proposal count differs')
    ds.audit.need(not any(r['formula'] in known for r in proposed), 'Proposed original formula already in inspected training/V8')
    for record in proposed:
        ds.audit.parse(record['formula'])
    (HERE / 'proposed-experiment-inputs.json').write_text(json.dumps({
        'schema': 'v9-coverage-augmentation-proposal-v1', 'status': 'proposal-only-not-frozen-or-approved',
        'label_budget_ceiling': 48, 'new_model_fit_count_proposed': 1,
        'fitted_model_or_labels_created': False,
        'original1665_and_consumed_v8_exact_formula_duplicates': [],
        'remaining_before_release': 'Check the complete consumed ledger and physical RTL/tool identities; seal complete inputs and recipe before any new target release.',
        'features': 'Existing mapping217 only', 'model': 'Same frozen ET300 parameters and zero rule',
        'inputs': proposed}, indent=2) + '\n')
    # A compact reader-facing file omits only the 10,500 detailed leaf records;
    # the full records remain in diagnosis.json and its deterministic gzip copy.
    compact = {k: v for k, v in data.items() if k not in ('queries', 'training_feature_collisions', 'training_support', 'consumed_support')}
    compact['training_support'] = data['training_support']
    compact['consumed_support'] = {k: v for k, v in data['consumed_support'].items() if k != 'constant_low_multiply_rows'}
    compact['training_feature_collisions'] = {m: {k: v for k, v in c.items() if k != 'largest_conflicting_groups'}
                                              for m, c in data['training_feature_collisions'].items()}
    compact['queries'] = {}
    for formula, query in data['queries'].items():
        slim = {k: v for k, v in query.items() if k != 'by_model'}
        slim['by_model'] = {}
        for model, record in query['by_model'].items():
            item = {k: v for k, v in record.items() if k not in (
                'all_300_tree_leaf_records', 'nearest_training_rows', 'top_training_influences',
                'path_feature_occurrences', 'last_split_feature_counts', 'second_last_split_feature_counts')}
            item['nearest_training_rows'] = [{k: n[k] for k in ('training_row', 'formula', 'lut4_count',
                'mean_range_scaled_absolute_distance', 'differing_columns')} for n in record['nearest_training_rows']]
            item['top_training_influences'] = [{k: n[k] for k in ('training_row', 'formula', 'lut4_count',
                'weight', 'prediction_contribution_lut4')} for n in record['top_training_influences'][:5]]
            item['top_path_features'] = record['path_feature_occurrences'][:5]
            slim['by_model'][model] = item
        compact['queries'][formula] = slim
    (HERE / 'diagnosis-summary.json').write_text(json.dumps(compact, indent=2) + '\n')
    with (HERE / 'diagnosis.json.gz').open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
            compressed.write(full_bytes)

    lines = [
        'V9 development diagnosis: sparse context support dominates; no query feature collisions.',
        '',
        'Read-only inspection of original 1,665 training rows and consumed V8 targets/features.',
        'No fits, new labels, synthesis, feature extraction, or model changes. All input/model hashes checked before/after.',
        'Frozen forest predictions replayed exactly, and every tree leaf value reconstructed from its original training targets.',
        '',
        '1. Training coverage',
        '72 low-multiply nodes / 72 rows; only 26 rows have a constant low-multiply operand (1.56% of training).',
        'There are 116 high-multiply nodes in 115 rows: mulh 38, mulhu 40, mulhsu 38.',
        'Seven of the 26 constant-low rows have zero target area. Ten use zero, one, minus one, or a power of two.',
        'The 26 low-constant parents are: root 2, variable add 1, add-immediate 7, mask 5, arithmetic shift 4, logical shift 5, XOR-immediate 2.',
        'Only direct full-width constant products: 84 -> 153 LUT4 and 1103515245 -> 574 LUT4.',
        'Only variable add around a constant product: add(mul(in0,1103515245),in1), expressed with decoded immediate nodes -> 635 LUT4.',
        'No low-constant training operand is 54, 2025, or 3456. No constant product has a two-input subtraction (masked or unmasked) as its variable operand.',
        'The seven original queries have zero exact formula matches in training.',
        'After folding constant-only subtrees, aliasing immediate operations and ignoring constant values, matched training shapes are:',
    ]
    for formula, query in data['queries'].items():
        matches = query['same_generic_input_shape']
        lines.append(f"  {query['lut4_count']:4} LUT4 | {formula} | {len(matches)} generic-input shape matches")
    lines += [
        'The same shape-count results hold when retaining in0/in1 identity.',
        'There are 300 training rows with signed right shift, but zero with the cap-miss four-operation shape sub(sra(add(I,I),C),sra(I,C)).',
        'Shape matching is a coverage diagnostic, not an equivalence theorem.',
        '',
        'All low-multiply constant operand occurrence counts (unsigned RV32 values):',
    ]
    for constant, count in data['training_support']['low_multiply_constant_operands_u32'].items():
        signed = int(constant) if int(constant) < 2**31 else int(constant) - 2**32
        lines.append(f'  {signed:12} ({int(constant):10} unsigned): {count}')
    lines += [
        '',
        '2. Predictions and nearest examples',
        'Target | Mapping | Original336 | Rewritten336 | Dual | SOG | original formula',
    ]
    for formula, query in data['queries'].items():
        models = query['by_model']
        points = ' | '.join(f'{models[m]["replayed_point"]:8.3f}' for m in ds.VIEWS)
        lines.append(f'{query["lut4_count"]:6} | {points} | {formula}')
    lines += [
        '',
        'Nearest neighbors use mean absolute feature difference divided by ORIGINAL TRAINING coordinate range; no target is used in distance.',
        'For mul(sub(in0,in1),54), nearest mapping row is xori(mul(addi(in0,-33),7),2): target 122; distance 0.04437, 136 differing coordinates.',
        'For mul(in0,2025), nearest mapping row is mul(in0,84): target 153; distance 0.04749, 131 differing coordinates.',
        'For the cap query, nearest mapping row is xori(sub(andi(add(in0,in1),16777215),srai(add(in0,in1),16)),3): target 66; distance 0.01888, 83 differing coordinates.',
        'The full five-neighbor lists for every query/view are retained in diagnosis-summary.json.',
        '',
        '3. Representation collisions versus geometry',
        'No query has an exact float64 OR float32 vector collision with training in ANY of the five views; no query collides with another consumed V8 circuit either.',
        'All seven mapping query vectors are inside each training coordinate range. Being inside coordinate ranges does not establish local/context coverage.',
        'Global training float32 collision statistics:',
    ]
    for model, record in data['training_feature_collisions'].items():
        lines.append(f"  {model}: {record['float32_unique_vectors']} unique / 1665; {record['conflicting_target_group_count']} conflicting groups, {record['conflicting_target_row_count']} rows; best possible empirical vector-only MAE lower bound {record['irreducible_in_sample_mae_if_only_this_vector']:.6f} LUT4.")
    lines += [
        'Mapping/dual conflicting groups differ by only 1 LUT4 and do not contain these queries. Strict feature collisions therefore do not explain the large misses.',
        'SOG nevertheless supplies weak local cost geometry: mul(in0,2025), target 326, has coarse estimated total area 1261 and XOR count 403.',
        'Its nearest SOG training row is a signed/high-product/masked context with target 48, coarse area 1272 and XOR count 402. These are near, not identical, vectors.',
        'Graph/mapping views distinguish these contexts better, but still lack nearby observed targets for the positive constant products and sub-before-mul contexts.',
        'The legacy features already include constant-operand count, popcount and signed-digit count: 54 -> (1,4,3), 2025 -> (1,8,4), 3456 -> (1,4,3).',
        'Their v5_norm_v3_mul_constant_adder_bits and mul_constant_csd_terms values are zero for all six V8 constant products because their small constants have been expanded into other operations in that analysis.',
        'The original generic word partial-term proxy remains 800..1024 for these constant products; it is not a specialized constant-multiply mapped cost.',
        'Original versus rewritten suffix changes only 1..19 of the 119 coordinates on these queries. Existing suffix features participate in 157..220 of the 900 last-three-level splits per query.',
        'This is not evidence that the added semantic features are ignored, nor proof that another large block would repair the missing support.',
        '',
        '4. Tree routing and averaging',
        'For mapping, original336, rewritten336 and dual, ALL 300 leaves reached by each of the seven queries have a SINGLE distinct training target.',
        'Some leaves contain several rows with the same target; none of those four models has within-leaf conflicting-target averaging on any query.',
        'For SOG, all six constant-product queries also have pure-target leaves; only the cap query reaches six conflicting-target leaves.',
        'The main effect is averaging DIFFERENT pure-target leaves across the 300 trees, routed to different contexts:',
        '  True201 sub-before-mul: mapping median tree prediction314, range93..692, mean301.22.',
        '    30.0% weight comes from srai(mul(xori(in0,-257),-17),13), target253; 16.0% from a masked variable product, target314; 14.0% from another variable product, target340.',
        '    Rewritten still assigns38.33% weight to that shifted negative-constant target253 and predicts286.77.',
        '  True326 mul2025: SOG median48, 243/300 trees at or below cap64; mean62.61.',
        '    63.0% weight comes from the target48 high-product context; another17.0% from a target116 high-product context. Combined high-multiply influence80.33%.',
        '  True56 cap case: mapping median64, mean64.7767; 174/300 trees are at/below64, yet the forest mean crosses the cap.',
        '    20.44% of mapping influence is the target66 masked-add/shift row; 11.32% is a target64 add/shift row; 9.0% is a target49 add/shift row.',
        '    Original336 and rewritten336 means63.11 and62.2867; rewritten median63 and212/300 trees at/below64.',
        'Tree disagreement is descriptive. A majority of trees below64 is not a calibrated feasibility probability and is not a justified safety policy.',
        '',
        '5. Small concrete next experiment',
        'Test DATA SUPPORT first, retaining the frozen mapping217 features and ET300 recipe. Do not append another 119-feature block.',
        'Propose a predeclared 48-circuit development batch:',
        '  32 constant-product circuits: constants {11,85,341,511} each multiplied by {1,4}; cross these 8 constants with 4 contexts:',
        '    mul(in0,addi(0,K)); add(mul(in0,addi(0,K)),in1); mul(sub(in0,in1),addi(0,K)); mul(sub(andi(in0,63),in1),addi(0,K)).',
        '  16 signed-shift circuits: sub(srai(add(in0,in1),k),srai(in1,31)) and sub(srai(sub(in0,in1),k),srai(in1,31)), for k={1,2,3,4,8,12,24,30}.',
        'This crosses positive-constant density/trailing-zero variation with the missing composition contexts; it does not duplicate the V8 constants or shift-5/16 cases.',
        'Every proposed addi(0,K) has a positive signed-12-bit immediate (maximum 2044), so the constant encoding does not require extra operations.',
        'All 48 original formulas parse and have no exact formula match in the inspected original 1665 or consumed V8. The complete older consumed ledger still needs checking before any label release.',
        'Exact proposed inputs and the fixed one-fit recipe are retained in proposed-experiment-inputs.json. This is a proposal, not a frozen experiment or approval to collect targets.',
        'Before any new targets, check duplicates/equivalences and seal the entire input pool and acquisition recipe. Retain every original RTL and outcome; source/ROI variants are not independent application units.',
        'Then compare ONE augmented mapping217 forest (original 1665 + the complete new batch) with the existing frozen mapping forest. Keep parameters, weights and zero rule fixed; do not tune to the seven rows.',
        'Primary development checks: all consumed V8 rows; six constant-product MAE/bias separately; the signed-shift case and complete cap32/64/128 false accepts/rejects; original-support regression checks.',
        'If augmentation repairs these contexts with unchanged features, coverage was the actionable bottleneck. If it does not, use the newly measured context matrix to isolate a specific residual mapping-cost interaction before designing a small feature or learner change.',
        'V8 is now consumed development evidence. Improved V8 numbers would not be fresh validation. Later freeze the winner and test an untouched application-family cohort.',
        'Merit-only already matches the cap64/budget1 oracle on V8, so fixing the cap miss can at most match that reference here; this endpoint cannot demonstrate added acquisition value on this pool.',
    ]
    prose = '\n'.join(lines) + '\n'
    # Keep numeric prose readable without altering the quoted formula grammar.
    for a, b in {
        'True201': 'True 201', 'true201': 'true 201', 'True326': 'True 326', 'true326': 'true 326',
        'True56': 'True 56', 'true56': 'true 56', 'median314': 'median 314', 'range93': 'range 93',
        'mean301': 'mean 301', 'target253': 'target 253', 'target314': 'target 314', 'target340': 'target 340',
        'assigns38': 'assigns 38', 'predicts286': 'predicts 286', 'median48': 'median 48', 'cap64': 'cap64',
        'mean62': 'mean 62', 'target48': 'target 48', 'another17': 'another 17', 'target116': 'target 116',
        'influence80': 'influence 80', 'median64': 'median 64', 'mean64': 'mean 64',
        'target66': 'target 66', 'target64': 'target 64', 'target49': 'target 49',
        'means63': 'means 63', 'and62': 'and 62', 'median63': 'median 63', 'and212': 'and 212',
        'below64': 'below 64', 'are66': 'are 66',
    }.items():
        prose = prose.replace(a, b)
    (HERE / 'report.txt').write_text(prose)
    files = [HERE / n for n in ('diagnose_support.py', 'render_report.py', 'diagnosis-run.log',
        'diagnosis.json', 'diagnosis.json.gz', 'diagnosis-summary.json', 'feature-snapshots.json',
        'proposed-experiment-inputs.json', 'report.txt') if (HERE / n).is_file()]
    manifest = {'schema': 'v9-readonly-development-diagnosis-manifest-v1', 'model_fit_calls': 0,
        'new_labels': 0, 'files': [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': ds.filehash(p)} for p in files]}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'report': str(HERE / 'report.txt'), 'full_gzip_bytes': (HERE / 'diagnosis.json.gz').stat().st_size,
                      'compact_json_bytes': (HERE / 'diagnosis-summary.json').stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
