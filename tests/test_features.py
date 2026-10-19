import unittest

from isaforge.features import FEATURE_COLUMNS, candidate_id, extract_features, parse_formula


def candidate(formula="add(mul(in0,in1),addi(in0,-3))", **changes):
    record = {"formula": formula, "size": 3, "runs": 10, "places": 2,
              "saved": 20, "savedPercent": 12.5}
    record.update(changes)
    return record


class FeatureTests(unittest.TestCase):
    def test_tree_counts_depth_constants_and_dynamic_features(self):
        features = extract_features(candidate())
        self.assertEqual(tuple(features), FEATURE_COLUMNS)
        self.assertEqual(features["depth"], 2)
        self.assertEqual(features["tree_op_count"], 3)
        self.assertEqual(features["input_count"], 2)
        self.assertEqual(features["constant_count"], 1)
        self.assertEqual(features["max_abs_constant"], 3)
        self.assertEqual(features["op_add"], 1)
        self.assertEqual(features["op_addi"], 1)
        self.assertEqual(features["op_mul"], 1)
        self.assertEqual(features["op_sub"], 0)
        self.assertEqual(features["saved_percent"], 12.5)
        self.assertNotIn("speedup", FEATURE_COLUMNS)
        self.assertNotIn("area", FEATURE_COLUMNS)

    def test_shared_subexpression_is_counted_as_tree(self):
        features = extract_features(candidate("add(mul(in0,in1),mul(in0,in1))", size=2, saved=10))
        self.assertEqual(features["size"], 2)
        self.assertEqual(features["tree_op_count"], 3)
        self.assertEqual(features["op_mul"], 2)

    def test_repeated_literals_and_lui(self):
        features = extract_features(candidate("add(lui(4096),addi(0,4096))"))
        self.assertEqual(features["input_count"], 0)
        self.assertEqual(features["constant_count"], 3)
        self.assertEqual(features["unique_constant_count"], 2)
        self.assertEqual(features["max_abs_constant"], 4096)

    def test_ids_are_deterministic_and_benchmark_scoped(self):
        identity = candidate_id("crc32", "add(in0,in1)")
        self.assertEqual(len(identity), 64)
        self.assertEqual(identity, candidate_id("crc32", " add ( in0 , in1 ) "))
        self.assertNotEqual(identity, candidate_id("aes", "add(in0,in1)"))
        self.assertNotEqual(identity, candidate_id("crc32", "sub(in0,in1)"))

    def test_rejects_unsafe_unsupported_and_malformed_formulas(self):
        invalid = ["", "in0", "add(in0)", "add(in0,in1,0)", "add(in0,in2)",
                   "load(in0,4)", "addi(in0,in1)", "lui(in0)", "add(in0,in1);print(1)",
                   "__import__('os').system('id')", "add(in0,in1) trailing", "add(in0,1.2)",
                   "add(in0,4294967296)", "add(in0,-2147483649)"]
        for formula in invalid:
            with self.subTest(formula=formula), self.assertRaises(ValueError):
                parse_formula(formula)

    def test_rejects_extreme_nesting(self):
        with self.assertRaisesRegex(ValueError, "nesting"):
            parse_formula("addi(" * 130 + "in0" + ",1)" * 130)

    def test_candidate_metadata_validation(self):
        invalid = [{"size": 1}, {"size": True}, {"runs": -1}, {"runs": 1.2},
                   {"places": 0}, {"saved": 19}, {"savedPercent": float("nan")},
                   {"savedPercent": float("inf")}, {"savedPercent": -1},
                   {"savedPercent": True}, {"savedPercent": 10**1000}]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                extract_features(candidate(**change))
        with self.assertRaises(ValueError):
            extract_features({"formula": "add(in0,in1)"})

    def test_savings_can_exceed_100_for_overlapping_occurrences(self):
        self.assertEqual(extract_features(candidate(savedPercent=120))["saved_percent"], 120)


if __name__ == "__main__":
    unittest.main()
