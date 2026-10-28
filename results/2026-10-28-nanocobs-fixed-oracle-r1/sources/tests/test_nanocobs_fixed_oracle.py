import ctypes
import unittest

from scripts import audit_nanocobs_fixed_oracle as audit


class CorruptEncoder:
    def cobs_encode(self, source, source_length, output, capacity, output_length):
        expected = bytearray(audit.encode_oracle(bytes(source[:source_length])))
        expected[0] ^= 0x01
        for index, value in enumerate(expected):
            output[index] = value
        ctypes.cast(output_length, ctypes.POINTER(ctypes.c_size_t))[0] = len(expected)
        return audit.SUCCESS


class FixedOracleTests(unittest.TestCase):
    def test_known_short_frames(self):
        self.assertEqual(audit.encode_oracle(b""), b"\x01\x00")
        self.assertEqual(audit.encode_oracle(b"\x00"), b"\x01\x01\x00")
        self.assertEqual(audit.encode_oracle(b"A\x00B"), b"\x02A\x02B\x00")
        self.assertEqual(audit.decode_oracle(b"\x02A\x02B\x00"), (b"A\x00B", 5))

    def test_exact_original_vector_shape_and_order(self):
        payloads = audit.fixed_payloads()
        self.assertEqual(len(payloads), 8215)
        self.assertEqual(payloads[0], ("binary-n0-m0", b""))
        self.assertEqual(payloads[1], ("binary-n1-m0", b"\x00"))
        self.assertEqual(payloads[-1], ("run-data-n12", b"A" * 12))

    def test_corrupted_output_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "encoded bytes differ"):
            audit.audit_payload(CorruptEncoder(), "corrupt", b"A")

    def test_oracle_rejects_payloads_outside_declared_scope(self):
        with self.assertRaisesRegex(ValueError, "<=12-byte"):
            audit.encode_oracle(b"A" * 13)

    def test_decoder_rejects_bad_delimiter_and_overlong_code(self):
        with self.assertRaisesRegex(ValueError, "terminal zero"):
            audit.decode_oracle(b"\x01")
        with self.assertRaisesRegex(ValueError, "code exceeds"):
            audit.decode_oracle(b"\x03A\x00")


if __name__ == "__main__":
    unittest.main()
