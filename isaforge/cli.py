"""Small reproducible entry points for dataset construction and offline experiments."""

import argparse
import json
from pathlib import Path


def read_rows(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{path}: expected a JSON array of objects")
    return value


def write_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dataset = sub.add_parser("dataset", help="Join existing candidates with optional measurements")
    dataset.add_argument("--benchmark", required=True)
    dataset.add_argument("--candidates", required=True)
    dataset.add_argument("--measurements")
    dataset.add_argument("--output", required=True)
    evaluate = sub.add_parser("evaluate", help="Leave one whole benchmark out per fold")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--seed", type=int, default=0)
    evaluate.add_argument("--output", required=True)
    select = sub.add_parser("select", help="Compare budgeted single-candidate selection policies")
    select.add_argument("--dataset", required=True)
    select.add_argument("--benchmark", required=True)
    select.add_argument("--budget", type=int, required=True)
    select.add_argument("--area-cap", type=float)
    select.add_argument("--seed", type=int, default=0)
    select.add_argument("--output", required=True)
    demo = sub.add_parser("demo", help="Run an explicitly synthetic smoke experiment")
    demo.add_argument("--output", default="generated/demo")
    demo.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "dataset":
            from .dataset import build_dataset
            result = build_dataset(args.benchmark, read_rows(args.candidates),
                                   read_rows(args.measurements) if args.measurements else None)
        elif args.command == "evaluate":
            from .evaluation import leave_one_benchmark_out
            result = leave_one_benchmark_out(read_rows(args.dataset), seed=args.seed)
        elif args.command == "select":
            from .selection import evaluate_policies
            rows = read_rows(args.dataset)
            target = [row for row in rows if row.get("benchmark") == args.benchmark]
            if not target:
                raise ValueError(f"No rows for benchmark {args.benchmark!r}")
            training = [row for row in rows if row.get("benchmark") != args.benchmark]
            result = evaluate_policies(target, args.budget, area_cap=args.area_cap,
                                       seed=args.seed, training_rows=training)
        else:
            from .demo import demo_rows
            from .evaluation import leave_one_benchmark_out
            from .selection import evaluate_policies
            rows = demo_rows()
            root = Path(args.output)
            write_json(root / "dataset.json", rows)
            write_json(root / "evaluation.json", leave_one_benchmark_out(rows, seed=args.seed))
            write_json(root / "selection.json", evaluate_policies(
                [row for row in rows if row["benchmark"] == "synthetic_2"],
                budget=4, area_cap=34, seed=args.seed,
                training_rows=[row for row in rows if row["benchmark"] != "synthetic_2"],
            ))
            print(f"Synthetic smoke experiment written to {root}; not hardware or simulator evidence.")
            return 0
        write_json(args.output, result)
        print(f"Wrote {args.output}")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
