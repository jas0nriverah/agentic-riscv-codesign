from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "benchmarks/fannkuch/FANNKUCH_REDUX_PIN.json"
UPSTREAM = ROOT / "benchmarks/fannkuch/fannkuchredux_upstream.c"
ADAPTER = ROOT / "benchmarks/fannkuch/fannkuchredux_isaforge.c"
ORACLE = ROOT / "benchmarks/fannkuch/upstream/fannkuchredux-output.txt"


class FannkuchHostAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

    def test_source_generators_reproduce_checked_in_bytes(self) -> None:
        if not self.cc:
            self.skipTest("no host C compiler available")
        for script in (
            "scripts/extract_fannkuch_source.py",
            "scripts/build_fannkuch_adapter.py",
        ):
            with self.subTest(script=script):
                subprocess.run(
                    [sys.executable, script, "--check"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_pinned_unmodified_program_matches_exact_n7_oracle(self) -> None:
        if not self.cc:
            self.skipTest("no host C compiler available")
        reference = json.loads(PIN.read_text(encoding="utf-8"))["correctness_reference"]
        expected = ORACLE.read_bytes()
        self.assertEqual(hashlib.sha256(expected).hexdigest(), reference["sha256"])
        self.assertEqual(expected.decode("utf-8"), reference["expected_output"])
        with tempfile.TemporaryDirectory(prefix="isaforge-fannkuch-upstream-") as temp:
            executable = Path(temp) / "fannkuch-upstream"
            subprocess.run(
                [self.cc, "-std=c99", "-O2", str(UPSTREAM), "-o", str(executable)],
                check=True,
                capture_output=True,
            )
            completed = subprocess.run([str(executable)], check=True, capture_output=True)
        self.assertEqual(completed.stdout, expected)

    def test_adapter_encoding_verifier_and_corruption_controls(self) -> None:
        if not self.cc:
            self.skipTest("no host C compiler available")
        harness = r'''
#include <limits.h>
#include <stdint.h>
void initialise_benchmark(void);
void warm_caches(int);
int benchmark(void);
int verify_benchmark(int);
#include "benchmarks/fannkuch/fannkuchredux_isaforge.c"

int main(void)
{
    int result;
    int checksum = 0;
    int flips = 0;
    int expected = (int)(((uint32_t)(228 + 32768) << 15) | 16U);

    initialise_benchmark();
    warm_caches(1);
    warm_caches(INT_MAX);
    result = benchmark();
    if (result != expected || !verify_benchmark(result)) return 1;
    if (verify_benchmark(result ^ (1 << 15))) return 2;
    if (verify_benchmark(result ^ 1)) return 3;
    if (verify_benchmark(-1) || verify_benchmark(INT_MIN)) return 4;
    if (encode_result(-32768, 0) != 0) return 5;
    if (encode_result(32767, 32767) != INT_MAX) return 6;
    if (!decode_result(encode_result(-32768, 0), &checksum, &flips) ||
        checksum != -32768 || flips != 0) return 7;
    if (!decode_result(encode_result(32767, 32767), &checksum, &flips) ||
        checksum != 32767 || flips != 32767) return 8;
    if (!decode_result(encode_result(228, 0), &checksum, &flips) ||
        checksum != 228 || flips != 0) return 9;
    if (!decode_result(encode_result(228, 32767), &checksum, &flips) ||
        checksum != 228 || flips != 32767) return 10;
    if (decode_result(-1, &checksum, &flips)) return 11;
    if (encode_result(INT_MIN, 16) != -1) return 12;
    if (encode_result(INT_MAX, 16) != -1) return 13;
    if (encode_result(228 + 65536, 16) != -1) return 14;
    if (encode_result(228, 16 + 32768) != -1) return 15;
    if (encode_result(228, -1) != -1) return 16;
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="isaforge-fannkuch-adapter-") as temp:
            temp_path = Path(temp)
            harness_path = temp_path / "adapter_test.c"
            executable = temp_path / "adapter-test"
            harness_path.write_text(harness, encoding="utf-8")
            subprocess.run(
                [self.cc, "-std=c11", "-O2", "-I", str(ROOT), str(harness_path), "-o", str(executable)],
                check=True,
                capture_output=True,
            )
            subprocess.run([str(executable)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
