#!/usr/bin/env python3
"""Deterministically extract the pinned C listing from its rendered HTML."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/fannkuch/FANNKUCH_REDUX_PIN.json"
HTML = ROOT / "benchmarks/fannkuch/upstream/fannkuchredux-gcc-1.html"
OUTPUT = ROOT / "benchmarks/fannkuch/fannkuchredux_upstream.c"


class ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._h2_depth = 0
        self._h2_text: list[str] = []
        self._source_heading_seen = False
        self._capturing = False
        self._finished = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "h2":
            self._h2_depth += 1
            self._h2_text = []
        elif tag == "pre" and self._source_heading_seen and not self._finished:
            self._capturing = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._h2_depth:
            self._h2_depth -= 1
            if "".join(self._h2_text).strip().lower() == "source code":
                self._source_heading_seen = True
        elif tag == "pre" and self._capturing:
            self._capturing = False
            self._finished = True

    def handle_data(self, data: str) -> None:
        if self._h2_depth:
            self._h2_text.append(data)
        if self._capturing:
            self.parts.append(data)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    completed = subprocess.run(
        ["git", "hash-object", "--stdin"], input=data, check=True, capture_output=True
    )
    return completed.stdout.decode("ascii").strip()


def extract(html: bytes, manifest: dict[str, object]) -> bytes:
    program = manifest["program"]
    assert isinstance(program, dict)
    expected_sha = program["sha256"]
    expected_blob = program["git_blob_sha1"]
    if sha256(html) != expected_sha or git_blob_sha1(html) != expected_blob:
        raise SystemExit("pinned HTML bytes do not match the source manifest")

    parser = ListingParser()
    parser.feed(html.decode("utf-8"))
    parser.close()
    if not parser._finished or not parser.parts:
        raise SystemExit("could not locate exactly one source-code <pre> block")
    source = "".join(parser.parts).strip() + "\n"
    if sum(part.count("\n") for part in parser.parts) < 10:
        raise SystemExit("extracted source is unexpectedly short")
    return source.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify output without writing")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = extract(HTML.read_bytes(), manifest)

    recorded = manifest.get("extracted_source")
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != result:
            raise SystemExit("checked-in extracted C does not match deterministic extraction")
        if not isinstance(recorded, dict) or recorded.get("sha256") != sha256(result):
            raise SystemExit("extracted-source hash is missing or stale in the pin manifest")
        print(f"verified {OUTPUT.relative_to(ROOT)} sha256={sha256(result)}")
        return 0

    OUTPUT.write_bytes(result)
    print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={sha256(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
