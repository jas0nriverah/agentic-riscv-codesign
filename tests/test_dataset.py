import unittest

from isaforge.dataset import build_dataset
from isaforge.features import candidate_id


def candidate(formula="add(in0,addi(in1,1))"):
    return {"formula": formula, "size": 2, "runs": 10, "places": 1,
            "saved": 10, "savedPercent": 5}


def measurement(**changes):
    record = {"candidate_id": candidate_id("crc32", candidate()["formula"]),
              "measurement_source": "gem5", "baseline_cycles": 1000,
              "candidate_cycles": 500, "baseline_period_ns": 2,
              "candidate_period_ns": 3, "area": 20}
    record.update(changes)
    return record


class DatasetTests(unittest.TestCase):
    def test_inference_has_no_fabricated_labels(self):
        row = build_dataset("crc32", [candidate()])[0]
        self.assertEqual(row["runs"], 10)
        self.assertEqual(row["benchmark"], "crc32")
        for field in ("speedup", "area", "measurement_source", "candidate_cycles"):
            self.assertNotIn(field, row)

    def test_speedup_includes_period_penalty(self):
        row = build_dataset("crc32", [candidate()], [measurement()])[0]
        self.assertAlmostEqual(row["speedup"], 4 / 3)
        self.assertEqual(row["measurement_source"], "gem5")
        self.assertEqual(row["candidate_period_ns"], 3)

    def test_actual_shorter_hardware_period_is_preserved(self):
        row = build_dataset("crc32", [candidate()], [measurement(
            measurement_source="hardware", candidate_period_ns=1)])[0]
        self.assertEqual(row["speedup"], 4)
        self.assertEqual(row["candidate_period_ns"], 1)

    def test_partial_labels_allowed_and_join_by_id(self):
        second = candidate("sub(in0,addi(in1,1))")
        rows = build_dataset("crc32", [second, candidate()], [measurement()])
        self.assertNotIn("speedup", rows[0])
        self.assertIn("speedup", rows[1])

    def test_rejects_duplicate_and_missing_and_mismatched_ids(self):
        bad = [measurement(candidate_id="unknown"), measurement(candidate_id=None),
               measurement(benchmark="aes"), measurement(formula="sub(in0,in1)")]
        for record in bad:
            with self.subTest(record=record), self.assertRaises(ValueError):
                build_dataset("crc32", [candidate()], [record])
        with self.assertRaises(ValueError):
            build_dataset("crc32", [candidate()], [measurement(), measurement()])
        with self.assertRaises(ValueError):
            build_dataset("crc32", [candidate(), candidate(" add(in0,addi(in1,1)) ")])
        bad_candidate = {**candidate(), "candidate_id": "wrong"}
        with self.assertRaises(ValueError):
            build_dataset("crc32", [bad_candidate])

    def test_rejects_bad_measurements(self):
        changes = [{"baseline_cycles": 0}, {"candidate_cycles": -1},
                   {"baseline_period_ns": float("nan")}, {"candidate_period_ns": float("inf")},
                   {"area": -1}, {"area": True}, {"area": float("nan")},
                   {"measurement_source": "guessed"}, {"measurement_source": {}},
                   {"speedup": 2}, {"candidate_cycles": 10**1000}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_dataset("crc32", [candidate()], [measurement(**change)])
        record = measurement()
        del record["area"]
        with self.assertRaises(ValueError):
            build_dataset("crc32", [candidate()], [record])

    def test_extreme_timing_products_keep_finite_ratio(self):
        row = build_dataset("crc32", [candidate()], [measurement(
            baseline_cycles=1e308, candidate_cycles=1e-308,
            baseline_period_ns=1e-308, candidate_period_ns=1e308)])[0]
        self.assertEqual(row["speedup"], 1)

    def test_nonrepresentable_ratio_rejected(self):
        with self.assertRaisesRegex(ValueError, "speedup"):
            build_dataset("crc32", [candidate()], [measurement(
                baseline_cycles=1e308, candidate_cycles=1e-308)])

    def test_explicit_synthetic_provenance_and_zero_area(self):
        row = build_dataset("crc32", [candidate()], [measurement(
            measurement_source="synthetic", area=0)])[0]
        self.assertEqual(row["measurement_source"], "synthetic")
        self.assertEqual(row["area"], 0)


if __name__ == "__main__":
    unittest.main()
