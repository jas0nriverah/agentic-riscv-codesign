#!/usr/bin/env python3
"""Prepare and operate the bounded current-Codex Ascon selector session."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from isaforge import ascon_selector_controller as controller
from isaforge import ascon_workload as ascon
from isaforge import guarded_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    release = sub.add_parser("freeze-release")
    release.add_argument("--output", type=Path, default=controller.RELEASE_DEFAULT)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=controller.CAMPAIGN_DEFAULT)
    action = sub.add_parser("action")
    action.add_argument("--root", type=Path, default=controller.CAMPAIGN_DEFAULT)
    action.add_argument("--json", required=True, help="One JSON object with tool and arguments")
    request = sub.add_parser("request")
    request.add_argument("--root", type=Path, default=controller.CAMPAIGN_DEFAULT)
    recover = sub.add_parser("recover")
    recover.add_argument("--root", type=Path, default=controller.CAMPAIGN_DEFAULT)
    audit = sub.add_parser("audit")
    audit.add_argument("--root", type=Path, default=controller.CAMPAIGN_DEFAULT)
    args = parser.parse_args(argv)

    if args.command == "freeze-release":
        value = controller.freeze_release(args.output)
        print(json.dumps({"release": str(args.output), "target": value["target"],
            "candidates": value["candidate_count"], "target_labels": value["target_labels_observed"],
            "dispatch_gate": value["dispatch_gate"]}, indent=2))
    elif args.command == "prepare":
        print(json.dumps(controller.prepare_campaign(args.root), indent=2))
    elif args.command == "request":
        print(json.dumps(controller.request(args.root), indent=2, allow_nan=False))
    elif args.command == "action":
        try:
            action = json.loads(args.json)
        except json.JSONDecodeError as error:
            parser.error("--json must contain one valid JSON object: " + str(error))
        print(json.dumps(controller.call(args.root, action), indent=2, allow_nan=False))
    elif args.command == "recover":
        print(json.dumps(controller.recover_interrupted(args.root), indent=2))
    else:
        with ascon.registration():
            result = guarded_evidence.audit(args.root)
        print(json.dumps({"context_id": result["context_id"],
            "charged_candidate_attempts": result["charged_candidate_attempts"],
            "attempt_collection_complete": result["attempt_collection_complete"],
            "candidate_wall_seconds": result["candidate_wall_seconds"],
            "reference_censored_candidates": result["reference_censored_candidates"],
            "best_verified_references": result["best_verified_references"]}, indent=2))


if __name__ == "__main__":
    main()
