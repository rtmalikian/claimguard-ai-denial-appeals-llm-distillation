#!/usr/bin/env python3
"""Merge reviewed teacher labels into ClaimGuard supervised records."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_sanitized_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


DEFAULT_SEED_INPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "seed_synthetic_supervised.jsonl"
)
DEFAULT_REVIEWED_OUTPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "reviewed_supervised.jsonl"
)
DEFAULT_REVIEW_REPORT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_label_ingestion_report.json"
)
REQUIRED_OUTPUT_KEYS = {
    "case_summary",
    "known_from_documents",
    "inferred",
    "missing_needs_human_verification",
    "cited_rules",
    "plan_type",
    "denial_type",
    "recommended_route",
    "deadline_table",
    "evidence_gaps",
    "draft_sections",
    "follow_up_plan",
    "human_review_required",
    "warnings",
}
UNSAFE_PHRASES = [
    "ready to file",
    "guaranteed coverage",
    "guaranteed approval",
    "independent medical judgment",
    "legal advice",
]


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def custom_id_to_example_id(custom_id: str) -> str:
    if not custom_id.startswith("teacher-label-vs"):
        return custom_id
    scenario = custom_id.replace("teacher-label-", "")
    return f"cg-{scenario}-"


def extract_response_content(response_record: dict[str, Any]) -> tuple[str, str | None]:
    custom_id = response_record.get("custom_id")
    if not isinstance(custom_id, str) or not custom_id:
        raise ValueError("teacher response record missing custom_id")

    if "teacher_output" in response_record:
        output = response_record["teacher_output"]
        if isinstance(output, dict):
            return custom_id, json.dumps(output, sort_keys=True)
        if isinstance(output, str):
            return custom_id, output
        raise ValueError(f"{custom_id}: teacher_output must be dict or string")

    response = response_record.get("response", {})
    body = response.get("body", {}) if isinstance(response, dict) else {}
    choices = body.get("choices", []) if isinstance(body, dict) else []
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return custom_id, content
    error = response_record.get("error") or response.get("error") if isinstance(response, dict) else None
    return custom_id, None if error else ""


def parse_teacher_json(custom_id: str, content: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if content is None:
        return None, f"{custom_id}: teacher response has error or no content"
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, f"{custom_id}: invalid teacher JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{custom_id}: teacher JSON must be an object"
    return payload, None


def validate_teacher_output(custom_id: str, payload: dict[str, Any]) -> list[str]:
    errors = []
    missing = sorted(REQUIRED_OUTPUT_KEYS - set(payload))
    if missing:
        errors.append(f"missing output keys: {missing}")
    if payload.get("human_review_required") is not True:
        errors.append("human_review_required must be true")
    draft_sections = payload.get("draft_sections")
    if not isinstance(draft_sections, list) or not draft_sections:
        errors.append("draft_sections must be a non-empty list")
    else:
        if not any(
            isinstance(section, dict)
            and (
                section.get("draft_status") == "draft_for_human_review"
                or "draft_for_human_review" in str(section.get("body", ""))
            )
            for section in draft_sections
        ):
            errors.append("draft_sections must preserve draft_for_human_review")
    for group_key in [
        "known_from_documents",
        "inferred",
        "missing_needs_human_verification",
        "cited_rules",
    ]:
        if not isinstance(payload.get(group_key), list):
            errors.append(f"{group_key} must be a list")
    serialized = json.dumps(payload, sort_keys=True).lower()
    for phrase in UNSAFE_PHRASES:
        if phrase in serialized and phrase not in {"legal advice"}:
            errors.append(f"unsafe phrase present: {phrase}")
    if "legal advice" in serialized and "not legal advice" not in serialized:
        errors.append("legal advice phrase must appear only as a safety disclaimer")
    return [f"{custom_id}: {error}" for error in errors]


def seed_record_by_custom_id(seed_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping = {}
    for record in seed_records:
        example_id = record["example_id"]
        parts = example_id.split("-")
        if len(parts) < 2:
            continue
        custom_id = f"teacher-label-{parts[1]}"
        mapping[custom_id] = record
    return mapping


def reviewed_record(
    seed_record: dict[str, Any],
    teacher_output: dict[str, Any],
    teacher_model: str,
    review_status: str,
) -> dict[str, Any]:
    record = deepcopy(seed_record)
    record["expected_output"] = teacher_output
    record["teacher_label"] = {
        "label_source": review_status,
        "teacher_model": teacher_model,
        "teacher_review_status": review_status,
        "human_review_required": True,
    }
    record["sft_messages"] = [
        *record["sft_messages"][:-1],
        {"role": "assistant", "content": json.dumps(teacher_output, sort_keys=True)},
    ]
    record["quality_gates"] = {
        "draft_for_human_review_present": True,
        "human_review_required": True,
        "has_source_status_groups": True,
        "has_quality_checks": bool(teacher_output.get("quality_checks", [])),
    }
    return record


def assert_no_phi(path: Path) -> None:
    findings = scan_text(path, path.read_text(encoding="utf-8"))
    if findings:
        summary = Counter(finding["finding_type"] for finding in findings)
        raise ValueError(f"{path} has PHI/PII-like findings: {dict(summary)}")


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path_is_within(path, REPO_ROOT):
        write_sanitized_report_json(path, payload, REPO_ROOT)
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-input", type=Path, default=DEFAULT_SEED_INPUT)
    parser.add_argument("--teacher-responses", type=Path, required=True)
    parser.add_argument("--reviewed-output", type=Path, default=DEFAULT_REVIEWED_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument("--teacher-model", default="teacher_model_reviewed")
    parser.add_argument(
        "--review-status",
        default="large_teacher_reviewed",
        choices=["large_teacher_reviewed", "human_reviewed"],
    )
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--skip-phi-scan", action="store_true")
    args = parser.parse_args()

    seed_records = load_jsonl(args.seed_input)
    teacher_responses = load_jsonl(args.teacher_responses)
    seed_by_custom_id = seed_record_by_custom_id(seed_records)

    reviewed_records = []
    errors = []
    seen_custom_ids = set()
    for response_record in teacher_responses:
        custom_id, content = extract_response_content(response_record)
        seen_custom_ids.add(custom_id)
        seed_record = seed_by_custom_id.get(custom_id)
        if seed_record is None:
            errors.append(f"{custom_id}: no matching seed record")
            continue
        payload, parse_error = parse_teacher_json(custom_id, content)
        if parse_error:
            errors.append(parse_error)
            continue
        validation_errors = validate_teacher_output(custom_id, payload)
        if validation_errors:
            errors.extend(validation_errors)
            continue
        reviewed_records.append(
            reviewed_record(seed_record, payload, args.teacher_model, args.review_status)
        )

    missing_custom_ids = sorted(set(seed_by_custom_id) - seen_custom_ids)
    if missing_custom_ids and not args.allow_partial:
        errors.extend(f"{custom_id}: missing teacher response" for custom_id in missing_custom_ids)

    if not errors:
        write_jsonl(args.reviewed_output, reviewed_records)
        if not args.skip_phi_scan:
            try:
                assert_no_phi(args.reviewed_output)
            except ValueError as exc:
                errors.append(str(exc))

    report = {
        "seed_input": str(args.seed_input),
        "teacher_responses": str(args.teacher_responses),
        "reviewed_output": str(args.reviewed_output),
        "teacher_model": args.teacher_model,
        "review_status": args.review_status,
        "seed_record_count": len(seed_records),
        "teacher_response_count": len(teacher_responses),
        "reviewed_record_count": len(reviewed_records),
        "missing_response_count": len(missing_custom_ids),
        "error_count": len(errors),
        "errors": errors,
        "training_gate": {
            "training_allowed": not errors and bool(reviewed_records),
            "reason": "all teacher labels validated" if not errors else "label validation errors remain",
        },
    }
    write_report(args.report_output, report)
    if errors:
        print(f"teacher label ingestion failed; report written to {args.report_output}")
        return 1
    print(f"wrote {len(reviewed_records)} reviewed records to {args.reviewed_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
