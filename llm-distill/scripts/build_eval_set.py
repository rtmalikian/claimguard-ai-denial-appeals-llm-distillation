#!/usr/bin/env python3
"""Create a small synthetic evaluation set for denial workflow validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SYNTHETIC_CASES = [
    {
        "example_id": "cg-vs01-commercial-mednec-001",
        "task": "end_to_end_denial_workflow",
        "input": {
            "document_text": (
                "Denial Notice. Insurance: Example Health. Date of Service: "
                "2026-04-10. Denial Date: 2026-04-20. Claim Number: SYN-1001. "
                "Reason for Denial: The MRI is denied because it is not medically "
                "necessary under the plan policy."
            )
        },
        "expected_output": {
            "denial_type": "medical_necessity",
            "recommended_route": "formal_internal_appeal",
            "human_review_required": True,
            "must_include": ["payer_policy", "clinician_lmn", "draft_for_human_review"],
        },
    },
    {
        "example_id": "cg-vs08-coding-modifier-001",
        "task": "route_selection",
        "input": {
            "document_text": (
                "EOB. Payer: Example Health. Claim Number: SYN-2001. Denial Code: "
                "CO-4. Reason for Denial: Procedure code is inconsistent with the "
                "modifier. Corrected claim accepted within 30 days."
            )
        },
        "expected_output": {
            "denial_type": "coding_billing",
            "recommended_route": "corrected_claim_or_reopening",
            "human_review_required": True,
            "must_include": ["preserve appeal deadline", "proof-of-submission"],
        },
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "eval" / "synthetic_eval.jsonl",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in SYNTHETIC_CASES:
            handle.write(json.dumps(record) + "\n")
    print(f"wrote {len(SYNTHETIC_CASES)} synthetic eval records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
