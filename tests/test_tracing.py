"""Validate real Spike log boundaries, counters and failure behavior."""
import importlib.util
import io
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("tracing", Path(__file__).parents[1] / "src/tracing.py")
tracing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracing)


def commit(word, suffix=""):
    return f"core   0: 3 0x80000100 (0x{word:08x}){suffix}\n"


def test_real_commit_format_and_counter_validation():
    output = io.StringIO()
    lines = ["diagnostic\n", commit(0xc02027f3, " x15 0x00000064"),
             commit(0x00150513, " x10 0x00000001"),
             commit(0xc02027f3, " x15 0x00000066")]
    result = tracing.parse_trace(lines, output)
    assert result["instret_delta"] == 2
    assert result["trace_instructions"] == 1
    assert '"op":"addi"' in output.getvalue()


def test_counter_wrap():
    result = tracing.parse_trace([commit(0xc02027f3, " x15 0xffffffff"),
                                  commit(0xc02027f3, " x15 0x00000000")], io.StringIO())
    assert result["instret_delta"] == 1


@pytest.mark.parametrize("lines, message", [
    ([], "found 0"),
    ([commit(0xc02027f3, " x15 0x64")], "found 1"),
    ([commit(0xc02027f3)], "destination"),
    (["core broken\n"], "Malformed"),
    ([commit(0xc02027f3, " x15 0x64"), commit(0xc02027f3, " x15 0x70")], "mismatch"),
    ([commit(0xc02027f3, " x15 0x64"), commit(0), commit(0xc02027f3, " x15 0x66")], "unknown=1"),
])
def test_invalid_or_truncated_trace_fails(lines, message):
    with pytest.raises(ValueError, match=message):
        tracing.parse_trace(lines, io.StringIO())
