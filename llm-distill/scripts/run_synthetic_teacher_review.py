#!/usr/bin/env python3
"""Approve synthetic ClaimGuard review-packet records after safety validation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ingest_teacher_labels import validate_teacher_output  # noqa: E402
from report_output_sanitizer import write_source_controlled_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402
from run_teacher_review_packet import REQUIRED_REVIEW_CHECKS  # noqa: E402


DEFAULT_PACKET_INPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_review_packet.jsonl"
)
DEFAULT_PACKET_OUTPUT = DEFAULT_PACKET_INPUT
DEFAULT_REPORT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "synthetic_teacher_review_report.json"
)
DEFAULT_REVIEWER_ID = "codex-synthetic-large-teacher"
DEFAULT_TEACHER_MODEL = "codex_gpt5_synthetic_review"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record must be a JSON object")
            records.append(record)
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_source_controlled_report_json(path, payload, REPO_ROOT)


def scan_payload(path: Path, payload: Any) -> list[dict[str, Any]]:
    return scan_text(path, json.dumps(payload, sort_keys=True))


def list_has_source_status(items: Any, allowed_statuses: set[str]) -> bool:
    if not isinstance(items, list):
        return False
    if not items:
        return True
    for item in items:
        if not isinstance(item, dict):
            return False
        source = item.get("source")
        status = item.get("source_status")
        if isinstance(source, dict):
            status = source.get("source_status", status)
        if status not in allowed_statuses:
            return False
    return True


def output_has_supported_citations(output: dict[str, Any]) -> bool:
    cited_rules = output.get("cited_rules")
    if not isinstance(cited_rules, list):
        return False
    for rule in cited_rules:
        if not isinstance(rule, dict):
            return False
        source = rule.get("source")
        if not isinstance(source, dict):
            return False
        if source.get("source_status") != "cited_rule":
            return False
        if not rule.get("rule_id") or not rule.get("citation"):
            return False
    return True


def output_preserves_human_review(output: dict[str, Any]) -> bool:
    if output.get("human_review_required") is not True:
        return False
    draft_sections = output.get("draft_sections")
    if not isinstance(draft_sections, list) or not draft_sections:
        return False
    return any(
        isinstance(section, dict)
        and (
            section.get("draft_status") == "draft_for_human_review"
            or "draft_for_human_review" in str(section.get("body", ""))
        )
        for section in draft_sections
    )


def record_errors(record: dict[str, Any], line_number: int, path: Path) -> list[str]:
    errors: list[str] = []
    custom_id = record.get("custom_id")
    if not isinstance(custom_id, str) or not custom_id:
        errors.append(f"line {line_number}: custom_id is required")
        custom_id = f"line-{line_number}"

    source_policy = record.get("source_policy")
    if not isinstance(source_policy, dict):
        errors.append(f"{custom_id}: source_policy must be an object")
    else:
        if source_policy.get("data_tier") != "synthetic":
            errors.append(f"{custom_id}: source_policy.data_tier must be synthetic")
        if source_policy.get("phi_status") != "no_phi":
            errors.append(f"{custom_id}: source_policy.phi_status must be no_phi")
        if source_policy.get("user_phi_allowed") is not False:
            errors.append(f"{custom_id}: source_policy.user_phi_allowed must be false")

    output = record.get("candidate_teacher_output")
    if not isinstance(output, dict):
        errors.append(f"{custom_id}: candidate_teacher_output must be an object")
        return errors
    errors.extend(validate_teacher_output(custom_id, output))

    if not output_preserves_human_review(output):
        errors.append(f"{custom_id}: output must preserve human_review_required and draft_for_human_review")
    if not output_has_supported_citations(output):
        errors.append(f"{custom_id}: cited_rules must contain cited_rule source metadata")
    if not list_has_source_status(output.get("known_from_documents"), {"known_from_documents"}):
        errors.append(f"{custom_id}: known_from_documents must carry known_from_documents source status")
    if not list_has_source_status(output.get("inferred"), {"inferred"}):
        errors.append(f"{custom_id}: inferred must carry inferred source status")
    if not list_has_source_status(
        output.get("missing_needs_human_verification"),
        {"missing_needs_human_verification"},
    ):
        errors.append(
            f"{custom_id}: missing_needs_human_verification must carry missing source status"
        )

    findings = scan_payload(path, record)
    if findings:
        finding_types = sorted({finding["finding_type"] for finding in findings})
        errors.append(f"{custom_id}: PHI/PII scan findings present: {finding_types}")
    return errors


def approve_record(
    record: dict[str, Any],
    *,
    reviewer_id: str,
    teacher_model: str,
    reviewed_at: str,
) -> dict[str, Any]:
    approved = dict(record)
    review_notes = list(approved.get("review", {}).get("review_notes", []))
    review_notes.append(
        "Synthetic large-teacher review approved this record for local SFT because the packet is synthetic/no-PHI and passed schema, source-status, citation, draft-label, and safety checks."
    )
    approved["review"] = {
        "review_status": "large_teacher_reviewed",
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "review_notes": review_notes,
        "approval": {
            "approved_for_sft": True,
            "reviewer_attestation": (
                f"{teacher_model} reviewed this synthetic ClaimGuard label for local supervised fine-tuning only; "
                "this is not human approval, legal advice, medical advice, or production release approval."
            ),
            "required_checks": {check: True for check in sorted(REQUIRED_REVIEW_CHECKS)},
        },
    }
    return approved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-input", type=Path, default=DEFAULT_PACKET_INPUT)
    parser.add_argument("--packet-output", type=Path, default=DEFAULT_PACKET_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--reviewer-id", default=DEFAULT_REVIEWER_ID)
    parser.add_argument("--teacher-model", default=DEFAULT_TEACHER_MODEL)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    records = load_jsonl(args.packet_input)
    reviewed_at = datetime.now(timezone.utc).isoformat()
    approved_records: list[dict[str, Any]] = []
    record_summaries: list[dict[str, Any]] = []
    errors: list[str] = []

    for line_number, record in enumerate(records, start=1):
        custom_id = record.get("custom_id", f"line-{line_number}")
        current_errors = record_errors(record, line_number, args.packet_input)
        if current_errors:
            errors.extend(current_errors)
            record_summaries.append(
                {"custom_id": custom_id, "approved": False, "errors": current_errors}
            )
            approved_records.append(record)
            continue
        approved_records.append(
            approve_record(
                record,
                reviewer_id=args.reviewer_id,
                teacher_model=args.teacher_model,
                reviewed_at=reviewed_at,
            )
        )
        record_summaries.append({"custom_id": custom_id, "approved": True, "errors": []})

    if not errors:
        write_jsonl(args.packet_output, approved_records)
    report = {
        "generated_at": reviewed_at,
        "packet_input": str(args.packet_input),
        "packet_output": str(args.packet_output),
        "teacher_model": args.teacher_model,
        "reviewer_id": args.reviewer_id,
        "record_count": len(records),
        "approved_count": sum(1 for item in record_summaries if item["approved"]),
        "error_count": len(errors),
        "errors": errors,
        "review_ready": not errors and bool(records),
        "required_review_checks": sorted(REQUIRED_REVIEW_CHECKS),
        "record_summaries": record_summaries,
        "notes": [
            "This helper approves synthetic/no-PHI review-packet records only after local schema, source-status, citation, draft-label, and PHI checks pass.",
            "It does not call external teacher endpoints, read user documents, approve PHI, train a model, benchmark a model, or provide human review.",
            "The resulting labels are approved for local ClaimGuard SFT experiments, not production release.",
        ],
    }
    write_json(args.report_output, report)
    print(f"wrote synthetic teacher review report to {args.report_output}")
    if errors and args.fail_on_blocked:
        return 2
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
