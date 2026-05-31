#!/usr/bin/env python3
"""Build and validate offline review packets for ClaimGuard teacher labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ingest_teacher_labels import REQUIRED_OUTPUT_KEYS, validate_teacher_output  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


DEFAULT_SEED_INPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "seed_synthetic_supervised.jsonl"
)
DEFAULT_PACKET_OUTPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_review_packet.jsonl"
)
DEFAULT_RESPONSE_OUTPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_responses_from_review.jsonl"
)
DEFAULT_REPORT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "teacher_review_packet_report.json"
)
REVIEWED_STATUSES = {"human_reviewed", "large_teacher_reviewed"}
REQUIRED_REVIEW_CHECKS = {
    "no_phi_pii",
    "source_grounded",
    "output_schema_valid",
    "human_review_gate_preserved",
    "draft_marked_for_human_review",
    "unsafe_claims_absent",
    "citations_supported",
    "minimum_necessary",
}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing JSONL file: {path}"]
    records = []
    errors = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSONL: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(f"{path}:{line_number}: record must be a JSON object")
                continue
            records.append(record)
    if not records:
        errors.append(f"{path}: no records")
    return records, errors


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def stable_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def custom_id_for_seed(seed_record: dict[str, Any]) -> str:
    example_id = seed_record.get("example_id", "")
    parts = example_id.split("-")
    if len(parts) >= 2 and parts[1].startswith("vs"):
        return f"teacher-label-{parts[1]}"
    return f"teacher-label-{example_id}"


def default_review_block() -> dict[str, Any]:
    return {
        "review_status": "pending_review",
        "reviewer_id": None,
        "reviewed_at": None,
        "review_notes": [],
        "approval": {
            "approved_for_sft": False,
            "reviewer_attestation": "",
            "required_checks": {check: False for check in sorted(REQUIRED_REVIEW_CHECKS)},
        },
    }


def build_packet_record(
    seed_record: dict[str, Any],
    existing_review: dict[str, Any] | None,
) -> dict[str, Any]:
    custom_id = custom_id_for_seed(seed_record)
    review = existing_review if isinstance(existing_review, dict) else default_review_block()
    candidate_output = seed_record["expected_output"]
    return {
        "custom_id": custom_id,
        "example_id": seed_record["example_id"],
        "dataset_split": seed_record["dataset_split"],
        "task": seed_record["task"],
        "micro_skill_ids": seed_record["micro_skill_ids"],
        "red_team_tags": seed_record.get("red_team_tags", []),
        "source_policy": seed_record["source_policy"],
        "input": seed_record["input"],
        "candidate_teacher_output": candidate_output,
        "candidate_output_required_keys": sorted(REQUIRED_OUTPUT_KEYS),
        "input_fingerprint": stable_hash(
            {
                "example_id": seed_record["example_id"],
                "input": seed_record["input"],
                "micro_skill_ids": seed_record["micro_skill_ids"],
            }
        ),
        "review": review,
        "instructions": [
            "Review or replace candidate_teacher_output using only synthetic/public/de-identified evidence.",
            "Do not add PHI/PII, real claim identifiers, real patient details, secrets, or unsupported citations.",
            "Use a pseudonymous reviewer_id such as role initials or an internal review code, not an email address.",
            "Set review.review_status to human_reviewed or large_teacher_reviewed only after every required_check is true.",
            "Set review.approval.approved_for_sft=true only when the label is safe for supervised fine-tuning.",
        ],
    }


def existing_reviews_by_custom_id(packet_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    reviews = {}
    for record in packet_records:
        custom_id = record.get("custom_id")
        review = record.get("review")
        if isinstance(custom_id, str) and isinstance(review, dict):
            reviews[custom_id] = review
    return reviews


def output_summary(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {"is_object": False}
    draft_sections = output.get("draft_sections", [])
    quality_checks = output.get("quality_checks", [])
    return {
        "is_object": True,
        "required_key_count": len(REQUIRED_OUTPUT_KEYS & set(output)),
        "missing_required_keys": sorted(REQUIRED_OUTPUT_KEYS - set(output)),
        "human_review_required": output.get("human_review_required"),
        "draft_section_count": len(draft_sections) if isinstance(draft_sections, list) else None,
        "quality_check_count": len(quality_checks) if isinstance(quality_checks, list) else None,
        "denial_type": output.get("denial_type"),
        "recommended_route": output.get("recommended_route"),
    }


def validate_packet_records(
    packet_records: list[dict[str, Any]],
    seed_records: list[dict[str, Any]],
) -> dict[str, Any]:
    seed_by_custom_id = {custom_id_for_seed(record): record for record in seed_records}
    seen_ids = set()
    approved_records = []
    pending_records = []
    errors = []
    warnings = []
    summaries = []

    for line_number, record in enumerate(packet_records, start=1):
        custom_id = record.get("custom_id")
        if not isinstance(custom_id, str) or not custom_id:
            errors.append(f"line {line_number}: custom_id is required")
            continue
        if custom_id in seen_ids:
            errors.append(f"{custom_id}: duplicate review packet record")
        seen_ids.add(custom_id)
        seed_record = seed_by_custom_id.get(custom_id)
        if seed_record is None:
            errors.append(f"{custom_id}: no matching seed record")
            continue
        expected_fingerprint = stable_hash(
            {
                "example_id": seed_record["example_id"],
                "input": seed_record["input"],
                "micro_skill_ids": seed_record["micro_skill_ids"],
            }
        )
        if record.get("input_fingerprint") != expected_fingerprint:
            errors.append(f"{custom_id}: input_fingerprint does not match seed input")

        output = record.get("candidate_teacher_output")
        review = record.get("review")
        approval = review.get("approval", {}) if isinstance(review, dict) else {}
        required_checks = approval.get("required_checks", {}) if isinstance(approval, dict) else {}
        approved = approval.get("approved_for_sft") is True if isinstance(approval, dict) else False
        review_status = review.get("review_status") if isinstance(review, dict) else None
        summaries.append(
            {
                "custom_id": custom_id,
                "example_id": seed_record["example_id"],
                "approved_for_sft": approved,
                "review_status": review_status,
                "micro_skill_ids": seed_record["micro_skill_ids"],
                "output_summary": output_summary(output),
            }
        )
        if not approved:
            pending_records.append(custom_id)
            continue

        if review_status not in REVIEWED_STATUSES:
            errors.append(f"{custom_id}: approved records require review_status in {sorted(REVIEWED_STATUSES)}")
        if not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"].strip():
            errors.append(f"{custom_id}: approved records require a non-empty pseudonymous reviewer_id")
        if not isinstance(review.get("reviewed_at"), str) or not review["reviewed_at"].strip():
            errors.append(f"{custom_id}: approved records require reviewed_at")
        if not isinstance(approval.get("reviewer_attestation"), str) or not approval["reviewer_attestation"].strip():
            errors.append(f"{custom_id}: approved records require reviewer_attestation")
        if not isinstance(required_checks, dict):
            errors.append(f"{custom_id}: required_checks must be an object")
        else:
            missing_checks = sorted(REQUIRED_REVIEW_CHECKS - set(required_checks))
            false_checks = sorted(
                check for check in REQUIRED_REVIEW_CHECKS if required_checks.get(check) is not True
            )
            if missing_checks:
                errors.append(f"{custom_id}: required_checks missing {missing_checks}")
            if false_checks:
                errors.append(f"{custom_id}: required_checks not true {false_checks}")
        if not isinstance(output, dict):
            errors.append(f"{custom_id}: candidate_teacher_output must be an object")
        else:
            errors.extend(validate_teacher_output(custom_id, output))
        approved_records.append(record)

    missing_seed_ids = sorted(set(seed_by_custom_id) - seen_ids)
    if missing_seed_ids:
        errors.extend(f"{custom_id}: missing review packet record" for custom_id in missing_seed_ids)

    if pending_records:
        warnings.append(f"{len(pending_records)} record(s) still pending review approval")

    return {
        "approved_records": approved_records,
        "approved_count": len(approved_records),
        "pending_custom_ids": pending_records,
        "pending_count": len(pending_records),
        "validation_errors": errors,
        "validation_error_count": len(errors),
        "warnings": warnings,
        "record_summaries": summaries,
    }


def response_records_from_approved(
    approved_packet_records: list[dict[str, Any]],
    teacher_model: str,
) -> list[dict[str, Any]]:
    response_records = []
    for record in approved_packet_records:
        review = record["review"]
        response_records.append(
            {
                "custom_id": record["custom_id"],
                "teacher_output": record["candidate_teacher_output"],
                "review_metadata": {
                    "review_status": review["review_status"],
                    "reviewer_id": review["reviewer_id"],
                    "reviewed_at": review["reviewed_at"],
                    "teacher_model": teacher_model,
                    "source": "offline_teacher_review_packet",
                },
            }
        )
    return response_records


def phi_scan(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "finding_count": None, "findings": []}
    findings = scan_text(path, path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "exists": True,
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-input", type=Path, default=DEFAULT_SEED_INPUT)
    parser.add_argument("--packet-input", type=Path)
    parser.add_argument("--packet-output", type=Path, default=DEFAULT_PACKET_OUTPUT)
    parser.add_argument("--response-output", type=Path, default=DEFAULT_RESPONSE_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--teacher-model", default="offline_teacher_or_human_review")
    parser.add_argument("--export-responses", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--fail-on-unapproved", action="store_true")
    args = parser.parse_args()

    seed_records, seed_errors = load_jsonl(args.seed_input)
    existing_packet_records: list[dict[str, Any]] = []
    existing_packet_errors: list[str] = []
    packet_source = args.packet_input or args.packet_output
    if packet_source.exists():
        existing_packet_records, existing_packet_errors = load_jsonl(packet_source)

    existing_reviews = existing_reviews_by_custom_id(existing_packet_records)
    packet_records = [
        build_packet_record(seed_record, existing_reviews.get(custom_id_for_seed(seed_record)))
        for seed_record in seed_records
    ]
    write_jsonl(args.packet_output, packet_records)

    validation = validate_packet_records(packet_records, seed_records)
    packet_scan = phi_scan(args.packet_output)
    response_records: list[dict[str, Any]] = []
    response_scan = {"path": str(args.response_output), "exists": False, "finding_count": None, "findings": []}
    export_errors: list[str] = []
    if packet_scan["finding_count"]:
        export_errors.append("review packet PHI/PII scan must have zero findings before response export")
    if args.export_responses:
        if validation["validation_error_count"]:
            export_errors.append("review packet validation errors block response export")
        if validation["pending_count"] and not args.allow_partial:
            export_errors.append("all records must be approved before response export unless --allow-partial is set")
        if not export_errors:
            response_records = response_records_from_approved(
                validation["approved_records"],
                args.teacher_model,
            )
            write_jsonl(args.response_output, response_records)
            response_scan = phi_scan(args.response_output)
            if response_scan["finding_count"]:
                export_errors.append("exported teacher response PHI/PII scan must have zero findings")

    review_packet_ready = not seed_errors and not existing_packet_errors and packet_scan["finding_count"] == 0
    response_export_ready = (
        args.export_responses
        and not export_errors
        and not validation["validation_error_count"]
        and validation["approved_count"] > 0
        and (args.allow_partial or validation["pending_count"] == 0)
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "export_responses" if args.export_responses else "build_packet",
        "seed_input": str(args.seed_input),
        "packet_input": str(packet_source),
        "packet_output": str(args.packet_output),
        "response_output": str(args.response_output),
        "teacher_model": args.teacher_model,
        "seed_record_count": len(seed_records),
        "packet_record_count": len(packet_records),
        "approved_count": validation["approved_count"],
        "pending_count": validation["pending_count"],
        "pending_custom_ids": validation["pending_custom_ids"],
        "validation_error_count": len(seed_errors) + len(existing_packet_errors) + validation["validation_error_count"],
        "validation_errors": seed_errors + existing_packet_errors + validation["validation_errors"],
        "warnings": validation["warnings"],
        "packet_phi_scan": packet_scan,
        "export_requested": args.export_responses,
        "exported_response_count": len(response_records),
        "response_phi_scan": response_scan,
        "export_error_count": len(export_errors),
        "export_errors": export_errors,
        "review_packet_ready": review_packet_ready,
        "response_export_ready": response_export_ready,
        "training_ready": response_export_ready and validation["pending_count"] == 0,
        "required_review_checks": sorted(REQUIRED_REVIEW_CHECKS),
        "record_summaries": validation["record_summaries"],
        "notes": [
            "This script builds and validates an offline review packet; it does not call teacher endpoints or approve labels.",
            "Completed review packets should use synthetic/public/de-identified data only and a pseudonymous reviewer_id.",
            "Response export writes ingestion-compatible JSONL only after approved records pass schema, safety, and PHI checks.",
        ],
    }
    write_json(args.report_output, report)
    print(f"wrote teacher review packet report to {args.report_output}")

    if seed_errors or existing_packet_errors or validation["validation_error_count"] or export_errors:
        return 1
    if args.fail_on_unapproved and validation["pending_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
