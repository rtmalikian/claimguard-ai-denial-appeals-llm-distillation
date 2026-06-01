#!/usr/bin/env python3
"""Audit public/government source-note coverage without downloading content."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_REGISTRY = DISTILL_DIR / "data" / "source_registry.json"
DEFAULT_MANIFEST = DISTILL_DIR / "data" / "corpus" / "manifest.json"
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "public_source_note_coverage_report.json"
PUBLIC_LICENSE_STATUS = "public_government_source"
PUBLIC_SOURCE_TYPE = "public_government_source"
REQUIRED_NOTE_MARKERS = (
    "Source URL:",
    "Corpus role:",
    "Safety notes:",
    "Use constraints:",
    "not exported to MLX SFT training splits",
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_sanitized_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing JSON file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_source_path(raw_path: str, base_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidate = (REPO_ROOT / path).resolve()
    if candidate.exists():
        return candidate
    return (base_path.parent / path).resolve()


def registry_sources(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payload, errors = load_json(path)
    if errors:
        return [], errors
    if not isinstance(payload, list):
        return [], ["source registry must be a JSON array"]
    sources = [source for source in payload if isinstance(source, dict)]
    if len(sources) != len(payload):
        return sources, ["source registry rows must be JSON objects"]
    public_sources = [
        source
        for source in sources
        if source.get("license_status") == PUBLIC_LICENSE_STATUS
        and source.get("phi_status") == "no_phi"
    ]
    return public_sources, []


def manifest_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payload, errors = load_json(path)
    if errors:
        return [], errors
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        return [], ["corpus manifest must be a list or object with records"]
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        return records, ["corpus manifest records must be JSON objects"]
    return records, []


def source_url_from_note(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "Source URL:":
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if stripped:
                    return stripped
    return ""


def audit_public_source_notes(
    *,
    registry_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    public_sources, registry_errors = registry_sources(registry_path)
    records, manifest_errors = manifest_records(manifest_path)
    blockers.extend(registry_errors)
    blockers.extend(manifest_errors)

    expected_by_url = {
        str(source.get("url", "")).strip(): str(source.get("source_id", "")).strip()
        for source in public_sources
        if source.get("url") and source.get("source_id")
    }
    public_note_records = [
        record
        for record in records
        if record.get("source_type") == PUBLIC_SOURCE_TYPE
        and record.get("document_role") == "rule_source"
    ]
    note_urls: dict[str, list[str]] = defaultdict(list)
    checked_note_count = 0
    missing_file_count = 0
    checksum_mismatch_count = 0
    phi_finding_count = 0
    marker_missing_count = 0
    invalid_training_flag_count = 0

    for record in public_note_records:
        document_id = str(record.get("document_id") or "unknown_document")
        source_path_raw = record.get("source_url_or_path")
        if not isinstance(source_path_raw, str) or not source_path_raw:
            blockers.append(f"{document_id}: source_url_or_path is required")
            missing_file_count += 1
            continue
        source_path = resolve_source_path(source_path_raw, manifest_path)
        if not source_path.exists():
            blockers.append(f"{document_id}: source note file is missing")
            missing_file_count += 1
            continue
        text = source_path.read_text(encoding="utf-8")
        checked_note_count += 1
        if sha256_text(text) != record.get("checksum"):
            blockers.append(f"{document_id}: source note checksum mismatch")
            checksum_mismatch_count += 1
        note_url = source_url_from_note(text)
        if note_url:
            note_urls[note_url].append(document_id)
        else:
            blockers.append(f"{document_id}: source note missing Source URL value")
        missing_markers = [marker for marker in REQUIRED_NOTE_MARKERS if marker not in text]
        if missing_markers:
            blockers.append(f"{document_id}: source note missing required markers")
            marker_missing_count += len(missing_markers)
        findings = scan_text(source_path, text)
        if findings:
            finding_types = sorted({finding["finding_type"] for finding in findings})
            blockers.append(f"{document_id}: public source note has PHI/PII-like findings: {finding_types}")
            phi_finding_count += len(findings)
        if record.get("training_eligible") is not False:
            blockers.append(f"{document_id}: public source note must not be training eligible")
            invalid_training_flag_count += 1
        if record.get("split") != "none":
            blockers.append(f"{document_id}: public source note split must be none")
            invalid_training_flag_count += 1
        if record.get("phi_status") != "no_phi":
            blockers.append(f"{document_id}: public source note phi_status must be no_phi")
            invalid_training_flag_count += 1

    missing_registry_source_ids = [
        source_id
        for url, source_id in sorted(expected_by_url.items(), key=lambda item: item[1])
        if url not in note_urls
    ]
    duplicate_registry_source_ids = [
        expected_by_url[url]
        for url, document_ids in note_urls.items()
        if url in expected_by_url and len(document_ids) > 1
    ]
    if missing_registry_source_ids:
        blockers.append("public source notes missing registry coverage")
    if duplicate_registry_source_ids:
        blockers.append("public source notes duplicate registry coverage")

    report = {
        "artifact": "public_source_note_coverage_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "warning_count": len(warnings),
        "warnings": warnings,
        "evidence": {
            "registry_path": str(registry_path),
            "manifest_path": str(manifest_path),
            "expected_public_source_count": len(expected_by_url),
            "public_source_note_record_count": len(public_note_records),
            "checked_note_count": checked_note_count,
            "covered_registry_source_count": len(
                [url for url in expected_by_url if url in note_urls]
            ),
            "missing_registry_source_ids": missing_registry_source_ids,
            "duplicate_registry_source_ids": duplicate_registry_source_ids,
            "missing_file_count": missing_file_count,
            "checksum_mismatch_count": checksum_mismatch_count,
            "marker_missing_count": marker_missing_count,
            "invalid_training_flag_count": invalid_training_flag_count,
            "phi_scan": {
                "finding_count": phi_finding_count,
                "values_redacted": True,
            },
            "training_exclusion_attested": invalid_training_flag_count == 0,
            "downloads_performed": False,
        },
        "notes": [
            "This audit reads checked-in registry metadata and local no-PHI source notes only.",
            "It does not download, scrape, call external services, or mark public rule sources training eligible.",
            "Public source notes are retrieval/governance context, not paired denial/appeal training documents.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = audit_public_source_notes(registry_path=args.registry, manifest_path=args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_sanitized_report_json(args.output, report, REPO_ROOT)
    print(
        f"wrote public source note coverage report to {args.output} "
        f"ready={report['ready']} blocked={report['blocker_count']}"
    )
    if args.fail_on_blocked and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
