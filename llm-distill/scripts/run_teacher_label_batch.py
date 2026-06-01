#!/usr/bin/env python3
"""Preflight or run ClaimGuard teacher-label requests against a configured endpoint."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report_output_sanitizer import write_sanitized_report_json
from run_phi_scan import scan_text


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUESTS = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_label_requests.jsonl"
)
DEFAULT_RESPONSE_OUTPUT = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "teacher_responses_pending.jsonl"
)
DEFAULT_REPORT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "teacher_label_batch_preflight_report.json"
)
PLACEHOLDER_MODEL = "TEACHER_MODEL_TO_BE_SET_BY_OPERATOR"
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


def is_local_url(base_url: str) -> bool:
    lowered = base_url.lower()
    return lowered.startswith("http://localhost") or lowered.startswith("http://127.0.0.1")


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records = []
    errors = []
    if not path.exists():
        return records, [f"missing request file: {path}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSONL: {exc}")
                continue
            records.append(record)
    if not records:
        errors.append(f"{path}: no request records")
    return records, errors


def validate_request(record: dict[str, Any], line_number: int) -> list[str]:
    errors = []
    custom_id = record.get("custom_id", f"line-{line_number}")
    if not isinstance(custom_id, str) or not custom_id:
        errors.append(f"line {line_number}: custom_id is required")
    if record.get("method") != "POST":
        errors.append(f"{custom_id}: method must be POST")
    if record.get("url") != "/v1/chat/completions":
        errors.append(f"{custom_id}: url must be /v1/chat/completions")
    body = record.get("body")
    if not isinstance(body, dict):
        errors.append(f"{custom_id}: body must be an object")
        return errors
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        errors.append(f"{custom_id}: body.messages must contain system and user messages")
    else:
        roles = [message.get("role") for message in messages if isinstance(message, dict)]
        if roles[:2] != ["system", "user"]:
            errors.append(f"{custom_id}: first messages must be system then user")
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                errors.append(f"{custom_id}: messages[{index}] must be an object")
                continue
            if message.get("role") not in {"system", "user", "assistant"}:
                errors.append(f"{custom_id}: messages[{index}].role is invalid")
            if not isinstance(message.get("content"), str) or not message["content"].strip():
                errors.append(f"{custom_id}: messages[{index}].content must be non-empty text")
    response_format = body.get("response_format")
    if response_format != {"type": "json_object"}:
        errors.append(f"{custom_id}: response_format must request json_object")
    if body.get("temperature") != 0:
        errors.append(f"{custom_id}: temperature must be 0")
    model = body.get("model")
    if not isinstance(model, str) or not model:
        errors.append(f"{custom_id}: body.model must be set")
    if messages and isinstance(messages, list):
        user_message = messages[1].get("content") if len(messages) > 1 and isinstance(messages[1], dict) else ""
        for key in REQUIRED_OUTPUT_KEYS:
            if key not in user_message:
                errors.append(f"{custom_id}: user prompt missing required output key {key}")
    return errors


def request_summary(record: dict[str, Any]) -> dict[str, Any]:
    body = record.get("body", {}) if isinstance(record.get("body"), dict) else {}
    messages = body.get("messages", []) if isinstance(body, dict) else []
    prompt_chars = sum(
        len(message.get("content", ""))
        for message in messages
        if isinstance(message, dict) and isinstance(message.get("content"), str)
    )
    return {
        "custom_id": record.get("custom_id"),
        "model": body.get("model"),
        "message_count": len(messages) if isinstance(messages, list) else None,
        "prompt_chars": prompt_chars,
    }


def existing_response_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            custom_id = record.get("custom_id")
            if isinstance(custom_id, str):
                ids.add(custom_id)
    return ids


def request_payload(record: dict[str, Any], model: str) -> dict[str, Any]:
    body = dict(record["body"])
    body["model"] = model
    return body


def post_teacher_request(
    *,
    base_url: str,
    api_key: str,
    record: dict[str, Any],
    model: str,
    timeout: float,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + record["url"]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(request_payload(record, model)).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return {
            "custom_id": record["custom_id"],
            "started_at": started_at,
            "duration_seconds": round(time.perf_counter() - start, 4),
            "response": {
                "status_code": exc.code,
                "body": safe_json(response_body),
            },
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "custom_id": record["custom_id"],
            "started_at": started_at,
            "duration_seconds": round(time.perf_counter() - start, 4),
            "response": None,
            "error": type(exc).__name__,
        }
    return {
        "custom_id": record["custom_id"],
        "started_at": started_at,
        "duration_seconds": round(time.perf_counter() - start, 4),
        "response": {
            "status_code": status_code,
            "body": safe_json(response_body),
        },
        "error": None,
    }


def safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_body": text[:4000]}


def write_jsonl_append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_sanitized_report_json(path, payload, REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--response-output", type=Path, default=DEFAULT_RESPONSE_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--base-url", default=os.environ.get("TEACHER_BASE_URL", ""))
    parser.add_argument("--model", default=os.environ.get("TEACHER_MODEL", PLACEHOLDER_MODEL))
    parser.add_argument("--api-key-env", default="TEACHER_API_KEY")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    records, load_errors = load_jsonl(args.requests)
    validation_errors: list[str] = []
    for line_number, record in enumerate(records, start=1):
        validation_errors.extend(validate_request(record, line_number))

    scan_findings = []
    if args.requests.exists():
        scan_findings = scan_text(args.requests, args.requests.read_text(encoding="utf-8"))

    run_blockers = list(load_errors) + validation_errors
    if scan_findings:
        run_blockers.append(f"request file has {len(scan_findings)} PHI/PII-like finding(s)")
    if not args.base_url:
        run_blockers.append("teacher base URL is required for --run")
    if args.model == PLACEHOLDER_MODEL:
        run_blockers.append("teacher model must be set before --run")
    api_key = os.environ.get(args.api_key_env, "")
    if args.base_url and not is_local_url(args.base_url) and not api_key:
        run_blockers.append(f"{args.api_key_env} is required for non-local teacher endpoint")

    existing_ids = existing_response_ids(args.response_output) if args.resume else set()
    runnable_records = [
        record
        for record in records
        if not (args.resume and record.get("custom_id") in existing_ids)
    ]
    if args.limit is not None:
        runnable_records = runnable_records[: args.limit]

    request_summaries = [request_summary(record) for record in records]
    run_results: list[dict[str, Any]] = []
    if args.run and not run_blockers:
        for record in runnable_records:
            result = post_teacher_request(
                base_url=args.base_url,
                api_key=api_key,
                record=record,
                model=args.model,
                timeout=args.timeout,
            )
            write_jsonl_append(args.response_output, result)
            run_results.append(
                {
                    "custom_id": result["custom_id"],
                    "status_code": result.get("response", {}).get("status_code")
                    if isinstance(result.get("response"), dict)
                    else None,
                    "error": result.get("error"),
                    "duration_seconds": result.get("duration_seconds"),
                }
            )
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    response_error_count = sum(1 for result in run_results if result.get("error"))
    response_success_count = sum(
        1 for result in run_results if result.get("error") is None and result.get("status_code") == 200
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "run" if args.run else "preflight",
        "requests": str(args.requests),
        "response_output": str(args.response_output),
        "base_url_configured": bool(args.base_url),
        "base_url_is_local": is_local_url(args.base_url) if args.base_url else None,
        "model": args.model,
        "api_key_env": args.api_key_env,
        "api_key_present": bool(api_key),
        "request_count": len(records),
        "request_summaries": request_summaries,
        "validation_error_count": len(load_errors) + len(validation_errors),
        "validation_errors": load_errors + validation_errors,
        "phi_scan": {
            "finding_count": len(scan_findings),
            "findings": scan_findings,
        },
        "resume": args.resume,
        "existing_response_count": len(existing_ids),
        "planned_request_count": len(runnable_records),
        "run_blocked": bool(run_blockers),
        "run_blockers": run_blockers,
        "run_attempted": args.run and not run_blockers,
        "run_results": run_results,
        "response_success_count": response_success_count,
        "response_error_count": response_error_count,
        "notes": [
            "Preflight mode validates request shape and safety without sending data.",
            "Run mode writes teacher responses to an ignored JSONL path for ingestion.",
            "Secrets are read only from the named environment variable and are not written to reports.",
        ],
    }
    write_report(args.report_output, report)
    print(f"wrote teacher label batch report to {args.report_output}")
    if args.run and run_blockers:
        return 2
    if args.run and response_error_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
