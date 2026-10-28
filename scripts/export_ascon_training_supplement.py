#!/usr/bin/env python3
"""Export verified Ascon v5 outcomes as explicitly incomplete training evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isaforge import ascon_training_supplement as supplement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=supplement.OUTPUT)
    parser.add_argument('--source', type=Path, default=supplement.SOURCE_ROOT)
    parser.add_argument('--historical', type=Path, default=supplement.HISTORY_ROOT)
    args = parser.parse_args(argv)
    value = supplement.export(args.output, source=args.source, historical=args.historical)
    print(dict(training_rows=len(value['training_rows']), unmeasured_candidates=9,
        evaluation_eligible=False, independent_confirmatory_families=0,
        new_model_fits=0, new_native_jobs=0, output=str(args.output)))


if __name__ == '__main__':
    main()
