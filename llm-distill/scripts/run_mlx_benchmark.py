#!/usr/bin/env python3
"""Benchmark ClaimGuard prompts against a local MLX-LM chat endpoint."""

from __future__ import annotations

import argparse
import json
import platform
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS = (
    REPO_ROOT / "llm-distill" / "data" / "distillation" / "seed_synthetic_supervised.jsonl"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "local_mlx_benchmark_report.json"
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
SCHEMA_CONTRACT_NAME = "strict_claim_guard_json_v1"
STRICT_SCHEMA_CONTRACT = """STRICT OUTPUT SCHEMA:
Return one JSON object only. Required keys: case_summary, known_from_documents, inferred, missing_needs_human_verification, cited_rules, plan_type, denial_type, recommended_route, deadline_table, evidence_gaps, draft_sections, follow_up_plan, human_review_required, warnings.
The following keys MUST be arrays, not strings: known_from_documents, inferred, missing_needs_human_verification, cited_rules, deadline_table, evidence_gaps, draft_sections, warnings.
draft_sections MUST be an array of objects. Include at least one object with section_id="appeal_letter", draft_status="draft_for_human_review", and body containing "draft_for_human_review".
denial_type MUST be one of: medical_necessity, out_of_network, coding_billing, missing_documentation, unknown. Assign denial_type only from document.text, not from available_source_snippets, appeal route, payer regime, or service category. Use medical_necessity when document.text explicitly says medical necessity, clinical criteria, or necessity was not established. Do not infer medical_necessity solely from outpatient service, imaging, pre-service authorization, organization determination, or appeal-rights language. Use unknown when document.text lacks an explicit denial-reason phrase or the reason is ambiguous, procedural, or only describes plan/regime/appeal status. Do not invent new denial_type strings or use route/status labels as denial_type.
human_review_required MUST be true. Do not output prose outside JSON."""


def load_records(path: Path, split: str | None, limit: int | None) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if split and record.get("dataset_split") != split:
                continue
            if "sft_messages" not in record:
                raise ValueError(f"{path}:{line_number}: missing sft_messages")
            if "expected_output" not in record:
                raise ValueError(f"{path}:{line_number}: missing expected_output")
            records.append(record)
            if limit and len(records) >= limit:
                break
    if not records:
        raise ValueError(f"{path}: no records matched split={split!r}")
    return records


def token_estimate(text: str) -> int:
    return max(1, len(text.split()))


def post_chat_completion(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
    max_tokens: int,
) -> tuple[dict[str, Any] | None, str | None, float]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        return None, str(exc.reason if hasattr(exc, "reason") else exc), time.perf_counter() - start
    except TimeoutError as exc:
        return None, str(exc), time.perf_counter() - start
    elapsed = time.perf_counter() - start
    try:
        return json.loads(response_body), None, elapsed
    except json.JSONDecodeError as exc:
        return None, f"invalid endpoint JSON: {exc}", elapsed


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else ""


def parse_model_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload, None
        return None, "model output JSON is not an object"
    except json.JSONDecodeError as exc:
        return None, str(exc)


def score_payload(expected: dict[str, Any], actual: dict[str, Any] | None) -> dict[str, Any]:
    if actual is None:
        return {
            "json_valid": False,
            "required_keys_present": False,
            "route_match": False,
            "denial_type_match": False,
            "human_review_required": False,
            "draft_for_human_review": False,
            "score": 0,
            "max_score": 6,
        }
    required_keys_present = REQUIRED_OUTPUT_KEYS <= set(actual)
    route_match = actual.get("recommended_route") == expected.get("recommended_route")
    denial_type_match = actual.get("denial_type") == expected.get("denial_type")
    human_review_required = actual.get("human_review_required") is True
    draft_sections = actual.get("draft_sections") or []
    draft_for_human_review = any(
        section.get("draft_status") == "draft_for_human_review"
        or "draft_for_human_review" in str(section.get("body", ""))
        for section in draft_sections
        if isinstance(section, dict)
    )
    checks = {
        "json_valid": True,
        "required_keys_present": required_keys_present,
        "route_match": route_match,
        "denial_type_match": denial_type_match,
        "human_review_required": human_review_required,
        "draft_for_human_review": draft_for_human_review,
    }
    return {
        **checks,
        "score": sum(1 for value in checks.values() if value),
        "max_score": len(checks),
    }


def expected_payload(record: dict[str, Any]) -> dict[str, Any]:
    assistant_message = record["sft_messages"][-1]
    return json.loads(assistant_message["content"])


def prompt_messages(
    record: dict[str, Any],
    strict_schema_contract: bool,
) -> list[dict[str, str]]:
    messages = [
        {"role": message["role"], "content": message["content"]}
        for message in record["sft_messages"][:-1]
    ]
    if not strict_schema_contract:
        return messages
    for message in messages:
        if message["role"] == "system":
            message["content"] = (
                message["content"].rstrip() + "\n\n" + STRICT_SCHEMA_CONTRACT
            )
            return messages
    return [{"role": "system", "content": STRICT_SCHEMA_CONTRACT}, *messages]


def dry_run_response(record: dict[str, Any]) -> str:
    return record["sft_messages"][-1]["content"]


def benchmark_record(
    record: dict[str, Any],
    base_url: str,
    model: str,
    timeout: float,
    max_tokens: int,
    dry_run: bool,
    strict_schema_contract: bool,
) -> dict[str, Any]:
    messages = prompt_messages(record, strict_schema_contract)
    expected = expected_payload(record)
    prompt_text = json.dumps(messages, sort_keys=True)
    if dry_run:
        response_json = None
        error = None
        elapsed = 0.0
        content = dry_run_response(record)
    else:
        response_json, error, elapsed = post_chat_completion(
            base_url=base_url,
            model=model,
            messages=messages,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        content = extract_content(response_json) if response_json else ""

    parsed, parse_error = parse_model_json(content) if content else (None, "empty model output")
    score = score_payload(expected, parsed)
    output_tokens = None
    if response_json:
        usage = response_json.get("usage") or {}
        output_tokens = usage.get("completion_tokens")
    output_token_estimate = output_tokens or (token_estimate(content) if content else 0)
    tokens_per_second = (
        round(output_token_estimate / elapsed, 4)
        if elapsed > 0 and output_token_estimate and not error
        else None
    )
    return {
        "example_id": record["example_id"],
        "dataset_split": record.get("dataset_split"),
        "teacher_review_status": record["teacher_label"].get("teacher_review_status"),
        "request": {
            "prompt_token_estimate": token_estimate(prompt_text),
            "max_tokens": max_tokens,
            "schema_contract": {
                "enabled": strict_schema_contract,
                "name": SCHEMA_CONTRACT_NAME if strict_schema_contract else None,
            },
        },
        "runtime": {
            "dry_run": dry_run,
            "duration_seconds": round(elapsed, 4),
            "output_token_estimate": output_token_estimate,
            "tokens_per_second": tokens_per_second,
            "endpoint_error": error,
            "parse_error": parse_error,
        },
        "score": score,
    }


def summarize(results: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    endpoint_errors = [result for result in results if result["runtime"]["endpoint_error"]]
    scored = [result["score"] for result in results]
    total_score = sum(item["score"] for item in scored)
    total_max = sum(item["max_score"] for item in scored)
    durations = [
        result["runtime"]["duration_seconds"]
        for result in results
        if result["runtime"]["duration_seconds"] > 0
    ]
    tokens_per_second = [
        result["runtime"]["tokens_per_second"]
        for result in results
        if result["runtime"]["tokens_per_second"] is not None
    ]
    return {
        "record_count": len(results),
        "dry_run": dry_run,
        "endpoint_available": not dry_run and not endpoint_errors,
        "endpoint_error_count": len(endpoint_errors),
        "score_ratio": round(total_score / total_max, 4) if total_max else 0.0,
        "total_score": total_score,
        "max_score": total_max,
        "latency_seconds_avg": round(sum(durations) / len(durations), 4) if durations else None,
        "tokens_per_second_avg": round(sum(tokens_per_second) / len(tokens_per_second), 4)
        if tokens_per_second
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default="http://localhost:8080/v1")
    parser.add_argument("--model", default="Qwen/Qwen3-4B-MLX-4bit")
    parser.add_argument("--split")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-tokens", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-strict-schema-contract",
        action="store_true",
        help="Do not append the ClaimGuard strict JSON schema contract to benchmark prompts.",
    )
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Exit 0 and write a report when the local endpoint is unavailable.",
    )
    args = parser.parse_args()

    records = load_records(args.records, args.split, args.limit)
    strict_schema_contract = not args.no_strict_schema_contract
    results = [
        benchmark_record(
            record=record,
            base_url=args.base_url,
            model=args.model,
            timeout=args.timeout,
            max_tokens=args.max_tokens,
            dry_run=args.dry_run,
            strict_schema_contract=strict_schema_contract,
        )
        for record in records
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "base_url": args.base_url,
        "records": str(args.records),
        "schema_contract": {
            "enabled": strict_schema_contract,
            "name": SCHEMA_CONTRACT_NAME if strict_schema_contract else None,
            "required_output_keys": sorted(REQUIRED_OUTPUT_KEYS),
        },
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "summary": summarize(results, args.dry_run),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote MLX benchmark report to {args.output}")
    if payload["summary"]["endpoint_error_count"] and not args.allow_unavailable:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
