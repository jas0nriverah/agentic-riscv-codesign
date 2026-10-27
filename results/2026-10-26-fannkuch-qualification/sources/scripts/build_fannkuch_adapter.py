#!/usr/bin/env python3
"""Apply only the reviewed freestanding ABI changes to pinned Fannkuch C."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/fannkuch/FANNKUCH_REDUX_PIN.json"
SOURCE = ROOT / "benchmarks/fannkuch/fannkuchredux_upstream.c"
OUTPUT = ROOT / "benchmarks/fannkuch/fannkuchredux_isaforge.c"

ADAPTER = r'''
_Static_assert(CHAR_BIT == 8, "ISAForge requires 8-bit bytes");
_Static_assert(sizeof(int) == 4, "ISAForge requires 32-bit int");
_Static_assert(INT_MIN == INT32_MIN && INT_MAX == INT32_MAX,
               "ISAForge requires signed 32-bit int");

static int encode_result(int checksum, int maximum_flips)
{
    uint32_t packed;

    if (checksum < -32768 || checksum > 32767 ||
        maximum_flips < 0 || maximum_flips > 32767) {
        return -1;
    }
    packed = ((uint32_t)(checksum + 32768) << 15) |
             (uint32_t)maximum_flips;
    return (int)packed;
}

static int decode_result(int result, int *checksum_out, int *maximum_flips_out)
{
    if (result < 0 || checksum_out == 0 || maximum_flips_out == 0) {
        return 0;
    }
    *checksum_out = (int)((uint32_t)result >> 15) - 32768;
    *maximum_flips_out = (int)((uint32_t)result & 0x7fffU);
    return 1;
}

void initialise_benchmark(void)
{
}

void warm_caches(int max_iterations)
{
    (void)max_iterations;
}

int benchmark(void)
{
    int checksum = 0;
    int maximum_flips = fannkuchredux(7, &checksum);

    return encode_result(checksum, maximum_flips);
}

int verify_benchmark(int result)
{
    int checksum;
    int maximum_flips;

    if (!decode_result(result, &checksum, &maximum_flips)) {
        return 0;
    }
    return checksum == 228 && maximum_flips == 16;
}
'''.lstrip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def adapt(source: str) -> str:
    replacements = (
        ("#include <stdio.h>\n#include <stdlib.h>\n", "#include <limits.h>\n#include <stdint.h>\n"),
        ("int fannkuchredux(int n)\n", "static int fannkuchredux(int n, int *checksum_out)\n"),
        (
            '                printf("%d\\n", checksum);\n'
            "                return maxFlipsCount;",
            "                *checksum_out = checksum;\n"
            "                return maxFlipsCount;",
        ),
    )
    result = source
    for old, new in replacements:
        if result.count(old) != 1:
            raise SystemExit(f"expected one exact source fragment, found {result.count(old)}: {old!r}")
        result = result.replace(old, new, 1)

    main_marker = "\nint main(int argc, char *argv[])\n"
    if result.count(main_marker) != 1:
        raise SystemExit("expected exactly one pinned command-line main")
    result = result.split(main_marker, 1)[0].rstrip() + "\n\n" + ADAPTER
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify output without writing")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record = manifest.get("extracted_source")
    if not isinstance(record, dict) or sha256(SOURCE.read_bytes()) != record.get("sha256"):
        raise SystemExit("extracted source does not match its pinned extraction hash")
    result = adapt(SOURCE.read_text(encoding="utf-8")).encode("utf-8")

    adapter_record = manifest.get("adapted_source")
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != result:
            raise SystemExit("checked-in adapter does not match the strict deterministic transform")
        if not isinstance(adapter_record, dict) or adapter_record.get("sha256") != sha256(result):
            raise SystemExit("adapted-source hash is missing or stale in the pin manifest")
        print(f"verified {OUTPUT.relative_to(ROOT)} sha256={sha256(result)}")
        return 0

    OUTPUT.write_bytes(result)
    print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
