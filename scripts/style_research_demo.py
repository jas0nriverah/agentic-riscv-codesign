#!/usr/bin/env python3
"""Apply a presentation-only readability fix to the frozen demo renderer.

Keep measured content and the archive-bound renderer unchanged. Full-width
workload tables avoid splitting cycle counts and hiding correctness columns.
"""
from pathlib import Path
import argparse

STYLE = '''<style id="isaforge-readable-tables">
.grid{display:block}
.grid table{font-size:14px}
.grid td{white-space:nowrap;overflow-wrap:normal}
.grid th{white-space:normal}
.grid .panel{padding:22px 26px}
@media(max-width:650px){.grid .panel{padding:16px}}
</style>'''


def apply(path):
    path = Path(path)
    html = path.read_text()
    if STYLE in html:
        return
    if html.count('</style><main>') != 1 or '<title>ISAForge · measured instruction selection</title>' not in html:
        raise ValueError('Expected the frozen ISAForge demo HTML')
    path.write_text(html.replace('</style><main>', '</style>' + STYLE + '<main>', 1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    apply(parser.parse_args().path)
