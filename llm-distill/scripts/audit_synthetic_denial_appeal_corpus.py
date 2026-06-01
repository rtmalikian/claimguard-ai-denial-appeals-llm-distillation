#!/usr/bin/env python3
"""Audit the generated synthetic denial/appeal corpus formatting contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_CORPUS_DIR = DISTILL_DIR / "data" / "corpus" / "generated_synthetic_pairs"
DEFAULT_GENERATION_REPORT = DEFAULT_CORPUS_DIR / "generation_report.json"
DEFAULT_MANIFEST = DEFAULT_CORPUS_DIR / "manifest_synthetic_900.json"
DEFAULT_VISUAL_RENDER_REPORT = DEFAULT_CORPUS_DIR / "visual_render_report.json"
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / (
    "synthetic_denial_appeal_corpus_format_audit_report.json"
)
REQUIRED_ROLES = {"denial_letter", "appeal_letter"}
REQUIRED_SPLITS = {"train", "valid", "test"}
EXPECTED_VARIANT_COUNTS = {
    "denial_format": 8,
    "appeal_format": 8,
    "layout_profile": 12,
    "typography_profile": 8,
    "length_profile": 6,
}
PROFILE_MATRIX_FAMILIES = ("layout_profile", "typography_profile", "length_profile")
PROFILE_PREFIXES = {
    "corpus_role": "- Corpus role: ",
    "layout_profile": "- Layout profile: ",
    "typography_profile": "- Typography profile: ",
    "length_profile": "- Length profile: ",
    "format_profile": "- Format family: ",
}
FORBIDDEN_UNSUPPORTED_APPEAL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bmust be filed by\b",
        r"\bdeadline is\b",
        r"\bguarantee(?:d|s)? approval\b",
        r"\bwill be approved\b",
        r"\bpursuant to\b",
        r"\bunder\s+(?:42\s+CFR|ERISA|Medicare|Medicaid)\b",
        r"\bfinal legal advice\b",
        r"\bmedical advice\b",
        r"\bready to file\b",
        r"\bfiling-ready appeal\b",
    ]
]

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_sanitized_report_json  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_source_path(raw_path: str, manifest_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    repo_candidate = (REPO_ROOT / path).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (manifest_path.parent / path).resolve()


def resolve_report_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def manifest_records(path: Path) -> tuple[list[dict[str, Any]], list[str], Any | None]:
    payload, errors = load_json(path)
    if errors:
        return [], errors, payload
    raw_records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        return [], ["synthetic corpus manifest must be a list or object with records"], payload
    records = [record for record in raw_records if isinstance(record, dict)]
    if len(records) != len(raw_records):
        return records, ["synthetic corpus manifest records must all be JSON objects"], payload
    return records, [], payload


def profile_metadata(text: str) -> dict[str, str]:
    profile: dict[str, str] = {}
    for line in text.splitlines():
        for key, prefix in PROFILE_PREFIXES.items():
            if line.startswith(prefix):
                profile[key] = line.removeprefix(prefix).strip()
    return profile


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", text))


def stats(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "average": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "average": round(sum(values) / len(values), 2),
    }


def expected_variant_minimum(family: str, pair_count: int | None) -> int:
    expected = EXPECTED_VARIANT_COUNTS[family]
    if pair_count is None:
        return expected
    return min(expected, max(1, pair_count))


def nested_profile_counters() -> dict[str, Counter[str]]:
    return {family: Counter() for family in PROFILE_MATRIX_FAMILIES}


def profile_matrix_coverage(
    *,
    group_profiles: dict[str, dict[str, Counter[str]]],
    group_record_counts: Counter[str],
    capacity_divisor: int,
) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for group_name, family_counts in sorted(group_profiles.items()):
        record_count = group_record_counts[group_name]
        variant_capacity = max(1, record_count // capacity_divisor)
        coverage[group_name] = {}
        for family in PROFILE_MATRIX_FAMILIES:
            counts = family_counts[family]
            required_variant_count = min(
                EXPECTED_VARIANT_COUNTS[family],
                variant_capacity,
            )
            variant_count = len(counts)
            coverage[group_name][family] = {
                "record_count": record_count,
                "variant_count": variant_count,
                "required_variant_count": required_variant_count,
                "ready": variant_count >= required_variant_count,
                "counts": dict(sorted(counts.items())),
            }
    return coverage


def empty_appeal_quality_contract() -> dict[str, Any]:
    return {
        "checked_appeal_count": 0,
        "missing_draft_status_count": 0,
        "missing_human_review_header_count": 0,
        "missing_not_filing_ready_notice_count": 0,
        "missing_source_grounding_count": 0,
        "missing_deadline_verification_count": 0,
        "missing_phi_minimization_count": 0,
        "missing_route_alignment_count": 0,
        "missing_appeal_level_alignment_count": 0,
        "missing_denial_type_alignment_count": 0,
        "unsupported_deadline_or_citation_claim_count": 0,
        "ready": False,
    }


def update_appeal_quality_contract(
    contract: dict[str, Any],
    *,
    text: str,
    record: dict[str, Any],
) -> None:
    contract["checked_appeal_count"] += 1
    text_lower = text.lower()
    appeal_route = str(record.get("appeal_route") or "")
    appeal_level = str(record.get("appeal_level") or "")
    denial_type = str(record.get("denial_type") or "")
    if "draft_for_human_review" not in text:
        contract["missing_draft_status_count"] += 1
    if not text.startswith("Draft for human review."):
        contract["missing_human_review_header_count"] += 1
    if "not filing-ready" not in text_lower:
        contract["missing_not_filing_ready_notice_count"] += 1
    if not (
        "connect each assertion to the denial notice, source record, or coding rationale" in text_lower
        or "source-grounded" in text_lower
    ):
        contract["missing_source_grounding_count"] += 1
    if "current deadline" not in text_lower and "allowed submission window" not in text_lower:
        contract["missing_deadline_verification_count"] += 1
    if "minimum necessary phi scope" not in text_lower and "minimum necessary placeholder" not in text_lower:
        contract["missing_phi_minimization_count"] += 1
    if appeal_route and f"route metadata {appeal_route}".lower() not in text_lower:
        contract["missing_route_alignment_count"] += 1
    if appeal_level and f"appeal level {appeal_level}".lower() not in text_lower:
        contract["missing_appeal_level_alignment_count"] += 1
    if denial_type and f"denial rationale for {denial_type}".lower() not in text_lower:
        contract["missing_denial_type_alignment_count"] += 1
    if any(pattern.search(text) for pattern in FORBIDDEN_UNSUPPORTED_APPEAL_PATTERNS):
        contract["unsupported_deadline_or_citation_claim_count"] += 1


def audit_corpus(
    *,
    corpus_dir: Path,
    generation_report_path: Path,
    manifest_path: Path,
    visual_render_report_path: Path,
    min_pairs: int,
    max_pairs: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    generation_report, generation_errors = load_json(generation_report_path)
    visual_render_report, visual_render_errors = load_json(visual_render_report_path)
    records, manifest_errors, manifest_payload = manifest_records(manifest_path)
    blockers.extend(generation_errors)
    blockers.extend(visual_render_errors)
    blockers.extend(manifest_errors)

    output_dir = corpus_dir
    reported_pair_count = None
    reported_letter_count = None
    generation_counts: dict[str, Any] = {}
    generation_phi_scan: dict[str, Any] = {}
    generation_safety: dict[str, Any] = {}
    if isinstance(generation_report, dict):
        if generation_report.get("artifact") != "synthetic_denial_appeal_corpus":
            blockers.append("generation report artifact must be synthetic_denial_appeal_corpus")
        reported_pair_count = generation_report.get("pair_count")
        reported_letter_count = generation_report.get("letter_count")
        generation_counts = (
            generation_report.get("counts")
            if isinstance(generation_report.get("counts"), dict)
            else {}
        )
        generation_phi_scan = (
            generation_report.get("phi_scan")
            if isinstance(generation_report.get("phi_scan"), dict)
            else {}
        )
        generation_safety = (
            generation_report.get("safety")
            if isinstance(generation_report.get("safety"), dict)
            else {}
        )
        if isinstance(generation_report.get("output_dir"), str):
            output_dir = resolve_report_path(
                generation_report["output_dir"],
                generation_report_path.parent,
            )
        if not isinstance(reported_pair_count, int) or not (
            min_pairs <= reported_pair_count <= max_pairs
        ):
            blockers.append(f"generation report pair_count must be between {min_pairs} and {max_pairs}")
        if not isinstance(reported_letter_count, int) or reported_letter_count != (
            reported_pair_count or 0
        ) * 2:
            blockers.append("generation report letter_count must equal pair_count * 2")
        if generation_phi_scan.get("finding_count") != 0:
            blockers.append("generation report PHI scan must have zero findings")
        if generation_safety.get("synthetic_only") is not True:
            blockers.append("generation report must declare synthetic_only=true")
        if generation_safety.get("real_patient_data_used") is not False:
            blockers.append("generation report must declare real_patient_data_used=false")
        if generation_safety.get("real_claim_data_used") is not False:
            blockers.append("generation report must declare real_claim_data_used=false")
    elif not generation_errors:
        blockers.append("generation report must be a JSON object")

    readme_path = output_dir / "README.md"
    documentation = {
        "path": str(readme_path),
        "exists": readme_path.exists(),
        "required_marker_count": 0,
        "phi_scan_finding_count": None,
        "ready": False,
    }
    if readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
        readme_markers = [
            "ClaimGuard AI is architected by Raphael Malikian",
            "synthetic denial/appeal pairs",
            "Synthetic formatting profile",
            "layout, typography",
            "actual CSS font stacks",
            "rendered_html",
            "draft_for_human_review",
            "manifest_synthetic_",
            "generation_report.json",
            "visual_render_report.json",
        ]
        documentation["required_marker_count"] = sum(
            1 for marker in readme_markers if marker in readme_text
        )
        readme_findings = scan_text(readme_path, readme_text)
        documentation["phi_scan_finding_count"] = len(readme_findings)
        if documentation["required_marker_count"] != len(readme_markers):
            blockers.append("synthetic corpus README is missing required documentation markers")
        if readme_findings:
            blockers.append("synthetic corpus README must have zero PHI/PII scan findings")
        documentation["ready"] = (
            documentation["required_marker_count"] == len(readme_markers)
            and len(readme_findings) == 0
        )
    else:
        blockers.append("synthetic corpus README must exist")

    visual_rendering = {
        "path": str(visual_render_report_path),
        "exists": visual_render_report_path.exists(),
        "ready": False,
        "visual_record_count": None,
        "rendered_html_count": None,
        "font_family_count": None,
        "layout_profile_count": None,
        "typography_profile_count": None,
        "phi_scan_finding_count": None,
    }
    if isinstance(visual_render_report, dict):
        visual_evidence = (
            visual_render_report.get("evidence")
            if isinstance(visual_render_report.get("evidence"), dict)
            else {}
        )
        visual_variant_counts = (
            visual_evidence.get("variant_counts")
            if isinstance(visual_evidence.get("variant_counts"), dict)
            else {}
        )
        visual_phi_scan = (
            visual_evidence.get("phi_scan")
            if isinstance(visual_evidence.get("phi_scan"), dict)
            else {}
        )
        visual_rendering.update(
            {
                "ready": visual_render_report.get("ready") is True,
                "visual_record_count": visual_evidence.get("visual_record_count"),
                "rendered_html_count": visual_evidence.get("rendered_html_count"),
                "font_family_count": visual_variant_counts.get("font_family"),
                "layout_profile_count": visual_variant_counts.get("layout_profile"),
                "typography_profile_count": visual_variant_counts.get("typography_profile"),
                "phi_scan_finding_count": visual_phi_scan.get("finding_count"),
            }
        )
        if visual_render_report.get("artifact") != "synthetic_denial_appeal_visual_layouts":
            blockers.append("visual render report artifact must be synthetic_denial_appeal_visual_layouts")
        if visual_render_report.get("ready") is not True:
            blockers.append("visual render report must be ready")
        if visual_evidence.get("visual_record_count") != reported_letter_count:
            blockers.append("visual render report record count must match generated letter_count")
        if visual_evidence.get("rendered_html_count") != reported_letter_count:
            blockers.append("visual render report rendered_html_count must match generated letter_count")
        if visual_evidence.get("pair_count") != reported_pair_count:
            blockers.append("visual render report pair_count must match generated pair_count")
        if visual_evidence.get("missing_source_count") != 0:
            blockers.append("visual render report missing_source_count must be zero")
        if visual_evidence.get("checksum_mismatch_count") != 0:
            blockers.append("visual render report checksum_mismatch_count must be zero")
        if visual_evidence.get("html_existing_count") != 0:
            blockers.append("visual render report html_existing_count must be zero")
        if visual_phi_scan.get("finding_count") != 0:
            blockers.append("visual render report PHI scan must have zero findings")
        if visual_variant_counts.get("font_family") != EXPECTED_VARIANT_COUNTS["typography_profile"]:
            blockers.append("visual render report must include all expected font-family variants")
        if visual_variant_counts.get("layout_profile") != EXPECTED_VARIANT_COUNTS["layout_profile"]:
            blockers.append("visual render report must include all expected layout variants")
        if visual_variant_counts.get("typography_profile") != EXPECTED_VARIANT_COUNTS["typography_profile"]:
            blockers.append("visual render report must include all expected typography variants")
    elif not visual_render_errors:
        blockers.append("visual render report must be a JSON object")

    role_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    denial_format_counts: Counter[str] = Counter()
    appeal_format_counts: Counter[str] = Counter()
    layout_counts: Counter[str] = Counter()
    typography_counts: Counter[str] = Counter()
    length_counts: Counter[str] = Counter()
    pair_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    text_hashes: Counter[str] = Counter()
    pair_signatures: Counter[str] = Counter()
    word_counts: list[int] = []
    word_counts_by_length: dict[str, list[int]] = defaultdict(list)
    phi_finding_types: Counter[str] = Counter()
    role_profile_counts: dict[str, dict[str, Counter[str]]] = defaultdict(nested_profile_counters)
    split_profile_counts: dict[str, dict[str, Counter[str]]] = defaultdict(nested_profile_counters)
    appeal_quality_contract = empty_appeal_quality_contract()
    content_contract = {
        "checked_file_count": 0,
        "missing_file_count": 0,
        "checksum_mismatch_count": 0,
        "profile_missing_count": 0,
        "profile_mismatch_count": 0,
        "missing_marker_count": 0,
        "invalid_training_gate_count": 0,
        "split_path_mismatch_count": 0,
    }
    missing_files: list[str] = []
    duplicate_document_ids: list[str] = []
    seen_document_ids: set[str] = set()
    record_text_hash_by_role: dict[tuple[str, str], str] = {}

    for record in records:
        document_id = str(record.get("document_id") or "unknown_document")
        role = str(record.get("document_role") or "unknown_role")
        split = str(record.get("split") or "unknown_split")
        pair_id = str(record.get("pair_id") or "")
        role_counts[role] += 1
        split_counts[split] += 1
        if document_id in seen_document_ids:
            duplicate_document_ids.append(document_id)
        seen_document_ids.add(document_id)
        if role not in REQUIRED_ROLES:
            blockers.append(f"{document_id}: document_role must be denial_letter or appeal_letter")
        if split not in REQUIRED_SPLITS:
            blockers.append(f"{document_id}: split must be train, valid, or test")
        if pair_id:
            pair_records[pair_id].append(record)
        else:
            blockers.append(f"{document_id}: pair_id is required")
        for key, expected in [
            ("source_type", "synthetic_deidentified_pair"),
            ("phi_status", "no_phi"),
            ("deidentification_status", "training_eligible"),
            ("license_status", "synthetic_allowed"),
            ("review_status", "training_approved"),
        ]:
            if record.get(key) != expected:
                content_contract["invalid_training_gate_count"] += 1
                blockers.append(f"{document_id}: {key} must be {expected}")
        if record.get("training_eligible") is not True:
            content_contract["invalid_training_gate_count"] += 1
            blockers.append(f"{document_id}: training_eligible must be true")
        if record.get("residual_risk_score") not in {0, 0.0}:
            content_contract["invalid_training_gate_count"] += 1
            blockers.append(f"{document_id}: residual_risk_score must be 0.0")

        source_path = record.get("source_url_or_path")
        if not isinstance(source_path, str) or not source_path:
            content_contract["missing_file_count"] += 1
            blockers.append(f"{document_id}: source_url_or_path is required")
            continue
        resolved_source = resolve_source_path(source_path, manifest_path)
        if not resolved_source.exists():
            content_contract["missing_file_count"] += 1
            missing_files.append(source_path)
            continue
        try:
            text = resolved_source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            blockers.append(f"{document_id}: source file must be UTF-8 text")
            continue
        content_contract["checked_file_count"] += 1
        actual_checksum = sha256_text(text)
        if actual_checksum != record.get("checksum"):
            content_contract["checksum_mismatch_count"] += 1
            blockers.append(f"{document_id}: checksum must match source text")
        text_hashes[actual_checksum] += 1
        if pair_id and role in REQUIRED_ROLES:
            record_text_hash_by_role[(pair_id, role)] = actual_checksum
        findings = scan_text(resolved_source, text)
        for finding in findings:
            phi_finding_types[str(finding.get("finding_type", "unknown"))] += 1
        if findings:
            blockers.append(f"{document_id}: source text must have zero PHI/PII scan findings")

        if f"/letters/{split}/" not in resolved_source.as_posix():
            content_contract["split_path_mismatch_count"] += 1
            blockers.append(f"{document_id}: source path must live under letters/{split}/")

        profile = profile_metadata(text)
        for key in PROFILE_PREFIXES:
            if key not in profile:
                content_contract["profile_missing_count"] += 1
                blockers.append(f"{document_id}: missing synthetic formatting profile field {key}")
        for key in ["layout_profile", "typography_profile", "length_profile", "format_profile"]:
            if profile.get(key) != record.get(key):
                content_contract["profile_mismatch_count"] += 1
                blockers.append(f"{document_id}: {key} must match manifest metadata")
        if profile.get("corpus_role") != role:
            content_contract["profile_mismatch_count"] += 1
            blockers.append(f"{document_id}: corpus role marker must match document_role")

        marker_failures: list[str] = []
        if "Synthetic formatting profile" not in text:
            marker_failures.append("formatting_profile_header")
        if role == "denial_letter":
            denial_format_counts[str(record.get("format_profile", "unknown"))] += 1
            if not text.startswith("Training synthetic corpus pair "):
                marker_failures.append("denial_training_header")
            if "Determination rationale:" not in text:
                marker_failures.append("denial_rationale")
            if "not connected to any real person" not in text:
                marker_failures.append("synthetic_no_real_person_notice")
        elif role == "appeal_letter":
            appeal_format_counts[str(record.get("format_profile", "unknown"))] += 1
            if not text.startswith("Draft for human review."):
                marker_failures.append("appeal_human_review_header")
            if "draft_for_human_review" not in text:
                marker_failures.append("draft_status_marker")
            if "not filing-ready" not in text:
                marker_failures.append("not_filing_ready_notice")
            update_appeal_quality_contract(
                appeal_quality_contract,
                text=text,
                record=record,
            )
        for marker in marker_failures:
            content_contract["missing_marker_count"] += 1
            blockers.append(f"{document_id}: missing content marker {marker}")

        layout_counts[str(record.get("layout_profile", "unknown"))] += 1
        typography_counts[str(record.get("typography_profile", "unknown"))] += 1
        length_profile = str(record.get("length_profile", "unknown"))
        length_counts[length_profile] += 1
        if role in REQUIRED_ROLES:
            for family in PROFILE_MATRIX_FAMILIES:
                role_profile_counts[role][family][str(record.get(family, "unknown"))] += 1
        if split in REQUIRED_SPLITS:
            for family in PROFILE_MATRIX_FAMILIES:
                split_profile_counts[split][family][str(record.get(family, "unknown"))] += 1
        current_word_count = word_count(text)
        word_counts.append(current_word_count)
        word_counts_by_length[length_profile].append(current_word_count)

    for pair_id, pair_items in sorted(pair_records.items()):
        roles = {str(item.get("document_role")) for item in pair_items}
        if roles != REQUIRED_ROLES or len(pair_items) != 2:
            blockers.append(f"{pair_id}: pair must contain exactly one denial and one appeal record")
            continue
        split_values = {str(item.get("split")) for item in pair_items}
        if len(split_values) != 1:
            blockers.append(f"{pair_id}: denial and appeal must share the same split")
        for key in [
            "layout_profile",
            "typography_profile",
            "length_profile",
            "payer_type",
            "denial_type",
            "appeal_route",
            "appeal_level",
        ]:
            values = {str(item.get(key)) for item in pair_items}
            if len(values) != 1:
                blockers.append(f"{pair_id}: paired records must share {key}")
        denial_hash = record_text_hash_by_role.get((pair_id, "denial_letter"), "")
        appeal_hash = record_text_hash_by_role.get((pair_id, "appeal_letter"), "")
        pair_signatures[sha256_text(denial_hash + "\n" + appeal_hash)] += 1

    pair_count = reported_pair_count if isinstance(reported_pair_count, int) else len(pair_records)
    letter_count = reported_letter_count if isinstance(reported_letter_count, int) else len(records)
    complete_pair_count = sum(
        1
        for pair_items in pair_records.values()
        if {str(item.get("document_role")) for item in pair_items} == REQUIRED_ROLES
        and len(pair_items) == 2
    )
    if duplicate_document_ids:
        blockers.append("synthetic corpus document_id values must be unique")
    if reported_letter_count is not None and len(records) != reported_letter_count:
        blockers.append("manifest record count must match generation report letter_count")
    if reported_pair_count is not None and complete_pair_count != reported_pair_count:
        blockers.append("manifest must preserve all denial/appeal pair relationships")
    missing_roles = sorted(REQUIRED_ROLES - set(role_counts))
    if missing_roles:
        blockers.append(f"synthetic corpus must include required document roles: {missing_roles}")
    missing_splits = sorted(REQUIRED_SPLITS - set(split_counts))
    if missing_splits:
        blockers.append(f"synthetic corpus must include required train/valid/test splits: {missing_splits}")
    if content_contract["missing_file_count"]:
        blockers.append(f"manifest references missing source files: {missing_files[:5]}")

    duplicate_text_group_count = sum(1 for count in text_hashes.values() if count > 1)
    duplicate_pair_group_count = sum(1 for count in pair_signatures.values() if count > 1)
    if duplicate_text_group_count:
        blockers.append("every synthetic letter must have unique text content")
    if duplicate_pair_group_count:
        blockers.append("every synthetic denial/appeal pair signature must be unique")

    actual_counts = {
        "denial_format": dict(sorted(denial_format_counts.items())),
        "appeal_format": dict(sorted(appeal_format_counts.items())),
        "layout_profile": dict(sorted(layout_counts.items())),
        "typography_profile": dict(sorted(typography_counts.items())),
        "length_profile": dict(sorted(length_counts.items())),
        "split": dict(sorted(split_counts.items())),
        "document_role": dict(sorted(role_counts.items())),
    }
    for family in EXPECTED_VARIANT_COUNTS:
        actual_variant_count = len(actual_counts[family])
        required_variant_count = expected_variant_minimum(family, pair_count)
        if actual_variant_count < required_variant_count:
            blockers.append(
                f"{family} must include at least {required_variant_count} variants; "
                f"found {actual_variant_count}"
            )
        report_values = generation_counts.get(family)
        if isinstance(report_values, dict) and set(report_values) != set(actual_counts[family]):
            blockers.append(f"generation report counts.{family} must match manifest/file audit values")

    word_stats = stats(word_counts)
    if (
        isinstance(word_stats["min"], int)
        and isinstance(word_stats["max"], int)
        and word_stats["max"] - word_stats["min"] < 50
    ):
        blockers.append("synthetic corpus document lengths must vary by at least 50 words")

    appeal_quality_contract["ready"] = (
        appeal_quality_contract["checked_appeal_count"] == role_counts.get("appeal_letter", 0)
        and all(
            appeal_quality_contract[key] == 0
            for key in [
                "missing_draft_status_count",
                "missing_human_review_header_count",
                "missing_not_filing_ready_notice_count",
                "missing_source_grounding_count",
                "missing_deadline_verification_count",
                "missing_phi_minimization_count",
                "missing_route_alignment_count",
                "missing_appeal_level_alignment_count",
                "missing_denial_type_alignment_count",
                "unsupported_deadline_or_citation_claim_count",
            ]
        )
    )
    if appeal_quality_contract["ready"] is not True:
        blockers.append(
            "synthetic appeal quality contract must pass draft, source-grounding, "
            "deadline/citation safety, PHI-minimization, and route-correctness checks"
        )

    profile_coverage = {
        "document_role": profile_matrix_coverage(
            group_profiles=role_profile_counts,
            group_record_counts=role_counts,
            capacity_divisor=1,
        ),
        "split": profile_matrix_coverage(
            group_profiles=split_profile_counts,
            group_record_counts=split_counts,
            capacity_divisor=2,
        ),
    }
    for dimension, dimension_coverage in profile_coverage.items():
        for group_name, family_coverage in dimension_coverage.items():
            for family, family_evidence in family_coverage.items():
                if family_evidence["ready"] is not True:
                    blockers.append(
                        f"{dimension} {group_name} must include at least "
                        f"{family_evidence['required_variant_count']} {family} variants; "
                        f"found {family_evidence['variant_count']}"
                    )

    report = {
        "artifact": "synthetic_denial_appeal_corpus_format_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "warning_count": len(warnings),
        "warnings": warnings,
        "evidence": {
            "corpus_dir": str(output_dir),
            "generation_report": str(generation_report_path),
            "manifest": str(manifest_path),
            "pair_count": pair_count,
            "letter_count": letter_count,
            "manifest_record_count": len(records),
            "complete_pair_count": complete_pair_count,
            "unique_text_count": len(text_hashes),
            "duplicate_text_group_count": duplicate_text_group_count,
            "duplicate_pair_group_count": duplicate_pair_group_count,
            "counts": actual_counts,
            "profile_matrix_coverage": profile_coverage,
            "appeal_quality_contract": appeal_quality_contract,
            "generation_report_counts": generation_counts,
            "content_contract": content_contract,
            "documentation": documentation,
            "visual_rendering": visual_rendering,
            "word_count": {
                **word_stats,
                "range": (
                    word_stats["max"] - word_stats["min"]
                    if isinstance(word_stats["max"], int) and isinstance(word_stats["min"], int)
                    else None
                ),
                "by_length_profile": {
                    key: stats(values)
                    for key, values in sorted(word_counts_by_length.items())
                },
            },
            "phi_scan": {
                "finding_count": sum(phi_finding_types.values()),
                "finding_types": dict(sorted(phi_finding_types.items())),
                "values_redacted": True,
            },
            "safety": generation_safety,
            "manifest_version": (
                manifest_payload.get("version")
                if isinstance(manifest_payload, dict)
                else None
            ),
        },
        "notes": [
            "This audit checks file-level formatting markers and metadata; it does not train or call external models.",
            "Plain-text letters keep typography metadata, and rendered HTML companions apply actual CSS font stacks and layout wrappers.",
            "All appeal letters must remain draft_for_human_review and not filing-ready.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--generation-report", type=Path, default=DEFAULT_GENERATION_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--visual-render-report", type=Path, default=DEFAULT_VISUAL_RENDER_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-pairs", type=int, default=800)
    parser.add_argument("--max-pairs", type=int, default=1000)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = audit_corpus(
        corpus_dir=args.corpus_dir,
        generation_report_path=args.generation_report,
        manifest_path=args.manifest,
        visual_render_report_path=args.visual_render_report,
        min_pairs=args.min_pairs,
        max_pairs=args.max_pairs,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_sanitized_report_json(args.output, report, REPO_ROOT)
    print(f"wrote synthetic corpus format audit report to {args.output}")
    if args.fail_on_blocked and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
