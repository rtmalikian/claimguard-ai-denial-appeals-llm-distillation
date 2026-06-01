#!/usr/bin/env python3
"""Audit generated denial notices against the app document-analysis extractor."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_CORPUS_DIR = DISTILL_DIR / "data" / "corpus" / "generated_synthetic_pairs"
DEFAULT_MANIFEST = DEFAULT_CORPUS_DIR / "manifest_synthetic_900.json"
DEFAULT_OUTPUT = DISTILL_DIR / "evals" / "reports" / "synthetic_document_analysis_extraction_report.json"
EXPECTED_ARTIFACT = "synthetic_document_analysis_extraction_audit"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(DISTILL_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(DISTILL_DIR / "scripts"))

from app.services.document_analysis import DocumentAnalysisService  # noqa: E402
from report_output_sanitizer import write_sanitized_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing manifest: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def record_path(record: dict[str, Any], corpus_dir: Path) -> Path | None:
    raw_path = record.get("path") or record.get("text_path") or record.get("source_url_or_path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    for candidate in [REPO_ROOT / path, corpus_dir / path]:
        if candidate.exists():
            return candidate
    return REPO_ROOT / path


def build_report(manifest_path: Path, corpus_dir: Path, *, min_denials: int) -> dict[str, Any]:
    manifest, errors = load_json(manifest_path)
    blockers = list(errors)
    records = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(records, list):
        records = []
        if not errors:
            blockers.append("manifest records must be a JSON list")

    service = DocumentAnalysisService.__new__(DocumentAnalysisService)
    checked_denial_count = 0
    missing_file_count = 0
    read_error_count = 0
    phi_finding_count = 0
    missing_payer_name_count = 0
    missing_denial_reason_count = 0
    missing_claim_amount_count = 0
    missing_procedure_code_count = 0
    unexpected_patient_name_count = 0
    unexpected_policy_number_count = 0
    sample_failures: list[dict[str, str]] = []

    def add_sample(document_id: str, field: str, detail: str) -> None:
        if len(sample_failures) < 20:
            sample_failures.append(
                {
                    "document_id": document_id,
                    "field": field,
                    "detail": detail,
                }
            )

    for record in records:
        if not isinstance(record, dict) or record.get("document_role") != "denial_letter":
            continue
        checked_denial_count += 1
        document_id = str(record.get("document_id") or record.get("id") or f"denial-{checked_denial_count}")
        path = record_path(record, corpus_dir)
        if path is None or not path.exists():
            missing_file_count += 1
            add_sample(document_id, "path", "missing denial text file")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            read_error_count += 1
            add_sample(document_id, "path", "denial text is not UTF-8")
            continue

        findings = scan_text(path, text)
        phi_finding_count += len(findings)
        if findings:
            add_sample(document_id, "phi_scan", "PHI/PII-like finding detected")

        extracted = service._extract_fields(text)
        if not extracted.get("payer_name"):
            missing_payer_name_count += 1
            add_sample(document_id, "payer_name", "payer name was not extracted")
        if not extracted.get("denial_reason"):
            missing_denial_reason_count += 1
            add_sample(document_id, "denial_reason", "denial rationale was not extracted")
        if extracted.get("claim_amount") is None:
            missing_claim_amount_count += 1
            add_sample(document_id, "claim_amount", "claim amount was not extracted")
        if not extracted.get("procedure_codes"):
            missing_procedure_code_count += 1
            add_sample(document_id, "procedure_codes", "procedure code was not extracted")
        if extracted.get("patient_name"):
            unexpected_patient_name_count += 1
            add_sample(document_id, "patient_name", "synthetic placeholder was extracted as a patient name")
        if extracted.get("policy_number"):
            unexpected_policy_number_count += 1
            add_sample(document_id, "policy_number", "synthetic coverage placeholder was extracted as a coverage reference")

    if checked_denial_count < min_denials:
        blockers.append(f"checked denial count must be at least {min_denials}")
    for key, count in {
        "missing_file_count": missing_file_count,
        "read_error_count": read_error_count,
        "phi_finding_count": phi_finding_count,
        "missing_payer_name_count": missing_payer_name_count,
        "missing_denial_reason_count": missing_denial_reason_count,
        "missing_claim_amount_count": missing_claim_amount_count,
        "missing_procedure_code_count": missing_procedure_code_count,
        "unexpected_patient_name_count": unexpected_patient_name_count,
        "unexpected_policy_number_count": unexpected_policy_number_count,
    }.items():
        if count:
            blockers.append(f"{key} must be 0")

    ready = not blockers
    return {
        "artifact": EXPECTED_ARTIFACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "warning_count": 0,
        "warnings": [],
        "evidence": {
            "manifest_path": str(manifest_path),
            "corpus_dir": str(corpus_dir),
            "checked_denial_count": checked_denial_count,
            "minimum_required_denial_count": min_denials,
            "missing_file_count": missing_file_count,
            "read_error_count": read_error_count,
            "phi_finding_count": phi_finding_count,
            "missing_payer_name_count": missing_payer_name_count,
            "missing_denial_reason_count": missing_denial_reason_count,
            "missing_claim_amount_count": missing_claim_amount_count,
            "missing_procedure_code_count": missing_procedure_code_count,
            "unexpected_patient_name_count": unexpected_patient_name_count,
            "unexpected_policy_number_count": unexpected_policy_number_count,
            "sample_failures": sample_failures,
        },
        "notes": [
            "This audit calls the local DocumentAnalysisService field extractor only.",
            "It does not call NVIDIA, teacher endpoints, model servers, OCR services, or production APIs.",
            "The generated denial notices remain synthetic stress-test data and are not production corpus evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-denials", type=int, default=800)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.manifest, args.corpus_dir, min_denials=args.min_denials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_sanitized_report_json(args.output, report, REPO_ROOT)
    print(f"wrote synthetic document-analysis extraction report to {args.output}")
    if report["blockers"] and args.fail_on_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
