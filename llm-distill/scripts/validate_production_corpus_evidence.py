#!/usr/bin/env python3
"""Validate production corpus evidence without storing document values."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "production_corpus_evidence"
    / "corpus_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "production_corpus_evidence_report.json"
DEFAULT_MANIFEST = DISTILL_DIR / "data" / "corpus" / "manifest.json"
DEFAULT_PRIVATE_MANIFEST_PATH_ENV = "PRODUCTION_CORPUS_PRIVATE_MANIFEST_PATH"
DEFAULT_PRIVATE_EVIDENCE_RENDERER = (
    DISTILL_DIR / "scripts" / "render_production_corpus_private_evidence.py"
)
EXPECTED_ARTIFACT = "claimguard_production_corpus_evidence"
REQUIRED_PAIR_ROLES = {"denial_letter", "appeal_letter"}
PRODUCTION_PAIR_SOURCE_TYPES = {
    "approved_public_denial_appeal_pair",
    "public_government_deidentified_pair",
    "public_government_denial_appeal_pair",
    "real_deidentified_pair",
    "real_world_deidentified_pair",
}
TRAINING_ALLOWED_PHI_STATUSES = {"deidentified", "no_phi"}
TRAINING_ALLOWED_REVIEW_STATUSES = {
    "training_approved",
    "privacy_review_passed",
    "expert_determination_passed",
}
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "approval_reference",
    "authorization_header",
    "checksum",
    "credential",
    "password",
    "raw_document",
    "secret",
    "source_path",
    "source_url",
    "source_url_or_path",
    "token",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "contains_approval_reference_values",
    "contains_raw_document_content",
    "no_phi_or_secret_values_attested",
    "no_raw_document_content_attested",
}
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: not production-ready",
    "Keep raw denial letters and raw appeal letters quarantined and encrypted",
    "Do not store raw documents",
    "Machine de-identification is a draft safety step only",
    "Safe Harbor-style automation",
    "Expert Determination",
    "Approved non-synthetic denial/appeal pair required",
    "Pair ids reviewed outside source control required",
    "production_corpus_ready=false",
)
PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: approved non-synthetic pair not complete for production.",
    "approved non-synthetic denial/appeal pair required",
    "denial letter role required",
    "appeal letter role required",
    "shared pair id required",
    "pair ids reviewed outside source control required",
    "source documents reviewed outside source control required",
    "privacy review required",
    "license review required",
    "residual-risk review required",
    "training scope review required",
    "no-PHI review required",
    "source license scope documented required",
    "boolean-only evidence",
    "no raw denial letters",
    "no raw appeal letters",
    "no source paths",
    "no source URLs",
    "no checksums",
    "no approval reference values",
    "no PHI",
    "production_corpus_ready=false",
)
COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: corpus collection and licensing review not complete for production.",
    "source inventory required",
    "source category documented required",
    "license terms reviewed outside source control required",
    "terms-of-use review required",
    "payer policy reuse restrictions reviewed required",
    "public source scope documented required",
    "real de-identified source scope documented required",
    "collection owner documented outside source control required",
    "privacy review required",
    "license review required",
    "residual-risk review required",
    "training scope review required",
    "no-PHI review required",
    "source license scope documented required",
    "boolean-only evidence",
    "no raw denial letters",
    "no raw appeal letters",
    "no source paths",
    "no source URLs",
    "no checksums",
    "no approval reference values",
    "no PHI",
    "production_corpus_ready=false",
)
PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "claimguard_production_corpus_evidence",
    "approved non-synthetic denial/appeal pair",
    "production_corpus_ready",
    "source_control_private_evidence_renderer_documented",
    "pair_ids_reviewed_outside_source_control",
    "source_documents_reviewed_outside_source_control",
    "no_raw_document_content_attested",
    "private_manifest_path_env",
    "DEFAULT_PRIVATE_SUMMARY_PATH_ENV",
    "private_summary_path_env",
    "private_production_corpus_summary_checked",
    "private production corpus summary",
    "private_production_corpus_summary_private_reference_count",
    "private_production_corpus_summary_source_document_review_count",
    "private_manifest_path_value_included",
    "private_summary_path_value_included",
    "private_manifest_metadata_checked",
    "private_manifest_complete_pair_count",
    "approval_reference_value_included",
    "raw_document_content_included",
    "0600",
    "values_redacted",
)
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
FORBIDDEN_ENV_KEY_FRAGMENTS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "raw",
    "secret",
    "token",
}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def bool_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is True


def false_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is False


def positive_int_value(section: dict[str, Any], key: str) -> bool:
    value = section.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def int_value(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key)
    return value if isinstance(value, int) and value >= 0 else default


def str_value(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    return value if isinstance(value, str) else ""


def requirement(
    *,
    requirement_id: str,
    name: str,
    status: str,
    evidence: dict[str, Any],
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def resolve_path(raw_path: str, base_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidate = (REPO_ROOT / path).resolve()
    if candidate.exists():
        return candidate
    return (base_path.parent / path).resolve()


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def private_manifest_env_key(evidence: dict[str, Any]) -> str:
    env_name = str_value(evidence, "private_manifest_path_env")
    return env_name or DEFAULT_PRIVATE_MANIFEST_PATH_ENV


def validate_private_manifest_env_key(env_name: str) -> list[str]:
    blockers: list[str] = []
    if not ENV_KEY_RE.match(env_name):
        blockers.append("private_manifest_path_env_invalid")
    if any(fragment in env_name.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS):
        blockers.append("private_manifest_path_env_secret_like")
    return blockers


def private_manifest_path_from_env(env_name: str) -> tuple[Path | None, list[str]]:
    blockers = validate_private_manifest_env_key(env_name)
    if blockers:
        return None, blockers
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        return None, ["private_manifest_path_env_value_missing"]
    if "\n" in raw_path or "\r" in raw_path or "\t" in raw_path or "#" in raw_path:
        return None, ["private_manifest_path_env_value_invalid"]
    manifest_path = Path(raw_path).expanduser().resolve()
    if path_is_within(manifest_path, REPO_ROOT):
        return None, ["private_manifest_path_must_be_outside_source_control"]
    return manifest_path, []


def find_forbidden_value_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            child_path = f"{path}.{key_text}"
            if (
                key_lower not in ALLOWED_BOOLEAN_FLAG_KEYS
                and any(fragment in key_lower for fragment in FORBIDDEN_VALUE_KEY_FRAGMENTS)
                and not isinstance(child, bool)
                and child not in (None, "", [])
            ):
                findings.append(f"{child_path}: raw approval, source, checksum, secret, or document value key is not allowed")
            findings.extend(find_forbidden_value_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden_value_keys(child, f"{path}[{index}]"))
    return findings


def evidence_format_requirement(evidence: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(evidence, dict):
        blockers.append("evidence must be a JSON object")
        evidence = {}
    if evidence.get("artifact") != EXPECTED_ARTIFACT:
        blockers.append(f"artifact must be {EXPECTED_ARTIFACT}")
    for section_name in ["corpus_review", "pairing_requirements"]:
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="production_corpus_evidence_format",
        name="Production corpus evidence has the required structure",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "artifact": evidence.get("artifact") if isinstance(evidence, dict) else None,
            "version_configured": bool(evidence.get("version")) if isinstance(evidence, dict) else False,
            "evidence_status": evidence.get("evidence_status") if isinstance(evidence, dict) else None,
        },
    )


def no_values_requirement(evidence_path: Path, evidence: Any) -> dict[str, Any]:
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    phi_findings = scan_text(evidence_path, evidence_text) if evidence_text else []
    forbidden_key_findings = find_forbidden_value_keys(evidence)
    if not isinstance(evidence, dict):
        evidence = {}
    no_phi_attested = bool_value(evidence, "no_phi_or_secret_values_attested")
    no_raw_content_attested = bool_value(evidence, "no_raw_document_content_attested")

    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"production corpus evidence contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not no_phi_attested:
        blockers.append("no_phi_or_secret_values_attested is not true")
    if not no_raw_content_attested:
        blockers.append("no_raw_document_content_attested is not true")

    return requirement(
        requirement_id="production_corpus_no_phi_secret_or_document_values",
        name="Production corpus evidence contains no PHI, secrets, source values, or raw documents",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": no_phi_attested,
            "no_raw_document_content_attested": no_raw_content_attested,
            "values_redacted": True,
        },
    )


def corpus_review_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("corpus_review", {})
    required_flags = {
        "source_control_review_runbook_documented": "source_control_review_runbook_not_documented",
        "source_control_collection_license_checklist_documented": "source_control_collection_license_checklist_not_documented",
        "source_control_private_evidence_renderer_documented": "source_control_private_evidence_renderer_not_documented",
        "privacy_review_attested": "privacy_review_not_attested",
        "license_review_attested": "license_review_not_attested",
        "residual_risk_review_attested": "residual_risk_review_not_attested",
        "training_scope_reviewed": "training_scope_not_reviewed",
        "no_phi_review_attested": "no_phi_review_not_attested",
        "source_license_scope_documented": "source_license_scope_not_documented",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    if bool_value(section, "contains_approval_reference_values"):
        blockers.append("corpus_review_contains_approval_reference_values")
    if bool_value(section, "contains_raw_document_content"):
        blockers.append("corpus_review_contains_raw_document_content")
    return requirement(
        requirement_id="production_corpus_manual_review_attestations",
        name="Production corpus privacy, license, residual-risk, and training-scope review is attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            key: bool_value(section, key)
            for key in [
                *required_flags.keys(),
                "contains_approval_reference_values",
                "contains_raw_document_content",
            ]
        },
    )


def operator_runbook_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("corpus_review", {})
    runbook_configured = bool_value(section, "source_control_review_runbook_documented")
    configured_path = str_value(section, "source_control_review_runbook_path")
    runbook_path = resolve_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS)
    if not runbook_configured:
        blockers.append("source_control_review_runbook_not_documented")
    if runbook_path is None:
        blockers.append("source_control_review_runbook_path_missing")
    elif not runbook_path.exists():
        blockers.append("source_control_review_runbook_missing")
    else:
        try:
            runbook_text = runbook_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            runbook_text = ""
            blockers.append("source_control_review_runbook_must_be_utf8")
        present_marker_count = sum(
            1 for marker in RUNBOOK_REQUIRED_MARKERS if marker in runbook_text
        )
        missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS) - present_marker_count
        if missing_marker_count:
            blockers.append("source_control_review_runbook_required_markers_missing")

    return requirement(
        requirement_id="production_corpus_operator_runbook",
        name="Source-controlled production corpus review runbook is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_review_runbook_documented": runbook_configured,
            "runbook_path": str(runbook_path) if runbook_path else None,
            "runbook_exists": bool(runbook_path and runbook_path.exists()),
            "required_marker_count": len(RUNBOOK_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_runbook_text_included": False,
            "values_redacted": True,
        },
    )


def collection_license_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("corpus_review", {})
    checklist_configured = bool_value(
        section,
        "source_control_collection_license_checklist_documented",
    )
    configured_path = str_value(
        section,
        "source_control_collection_license_checklist_path",
    )
    checklist_path = resolve_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS)
    if not checklist_configured:
        blockers.append("source_control_collection_license_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_collection_license_checklist_path_missing")
    elif not checklist_path.exists():
        blockers.append("source_control_collection_license_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_collection_license_checklist_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS
            if marker in checklist_text
        )
        missing_marker_count = (
            len(COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_collection_license_checklist_required_markers_missing")

    return requirement(
        requirement_id="production_corpus_collection_license_checklist",
        name="Source-controlled production corpus collection/license checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_collection_license_checklist_documented": checklist_configured,
            "collection_license_checklist_path": str(checklist_path) if checklist_path else None,
            "collection_license_checklist_exists": bool(checklist_path and checklist_path.exists()),
            "required_marker_count": len(COLLECTION_LICENSE_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def pair_source_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("pairing_requirements", {})
    checklist_configured = bool_value(
        section,
        "source_control_pair_source_checklist_documented",
    )
    configured_path = str_value(section, "source_control_pair_source_checklist_path")
    checklist_path = resolve_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS)
    if not checklist_configured:
        blockers.append("source_control_pair_source_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_pair_source_checklist_path_missing")
    elif not checklist_path.exists():
        blockers.append("source_control_pair_source_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_pair_source_checklist_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS
            if marker in checklist_text
        )
        missing_marker_count = (
            len(PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_pair_source_checklist_required_markers_missing")

    return requirement(
        requirement_id="production_corpus_pair_source_checklist",
        name="Source-controlled production corpus pair/source checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_pair_source_checklist_documented": checklist_configured,
            "pair_source_checklist_path": str(checklist_path) if checklist_path else None,
            "pair_source_checklist_exists": bool(checklist_path and checklist_path.exists()),
            "required_marker_count": len(PAIR_SOURCE_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def private_evidence_renderer_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("corpus_review", {})
    renderer_configured = bool_value(
        section,
        "source_control_private_evidence_renderer_documented",
    )
    configured_path = str_value(section, "private_evidence_renderer_path")
    renderer_path = (
        resolve_path(configured_path, evidence_path)
        if configured_path
        else DEFAULT_PRIVATE_EVIDENCE_RENDERER
    )
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS)
    if not renderer_configured:
        blockers.append("source_control_private_evidence_renderer_not_documented")
    if not renderer_path.exists():
        blockers.append("source_control_private_evidence_renderer_missing")
    else:
        try:
            renderer_text = renderer_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            renderer_text = ""
            blockers.append("source_control_private_evidence_renderer_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS
            if marker in renderer_text
        )
        missing_marker_count = (
            len(PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_private_evidence_renderer_markers_missing")

    return requirement(
        requirement_id="production_corpus_private_evidence_renderer",
        name="Source-controlled production corpus private evidence renderer is available",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_evidence_renderer_documented": renderer_configured,
            "private_evidence_renderer_path": str(renderer_path),
            "private_evidence_renderer_exists": renderer_path.exists(),
            "required_marker_count": len(PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_renderer_text_included": False,
            "private_output_required": True,
            "values_redacted": True,
        },
    )


def private_summary_metadata_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    required_true_flags = {
        "private_manifest_path_configured": "private_manifest_path_not_configured",
        "private_summary_path_configured": "private_summary_path_not_configured",
        "private_manifest_metadata_checked": "private_manifest_metadata_not_checked",
        "private_production_corpus_summary_checked": "private_production_corpus_summary_not_checked",
    }
    required_false_flags = {
        "private_manifest_path_value_included": "private_manifest_path_value_included",
        "private_summary_path_value_included": "private_summary_path_value_included",
        "approval_reference_value_included": "approval_reference_value_included",
        "raw_private_values_included": "raw_private_values_included",
        "raw_document_content_included": "raw_document_content_included",
        "source_document_values_included": "source_document_values_included",
        "pair_id_values_included": "pair_id_values_included",
        "source_paths_or_urls_included": "source_paths_or_urls_included",
        "checksum_values_included": "checksum_values_included",
        "credential_values_included": "credential_values_included",
        "phi_or_secret_values_included": "phi_or_secret_values_included",
        "production_document_content_included": "production_document_content_included",
    }
    required_positive_counts = {
        "private_manifest_record_count": "private_manifest_record_count_missing",
        "private_manifest_candidate_role_count": "private_manifest_candidate_role_count_missing",
        "private_manifest_complete_pair_count": "private_manifest_complete_pair_count_missing",
        "private_production_corpus_summary_manifest_record_count": "private_production_corpus_summary_manifest_record_count_missing",
        "private_production_corpus_summary_candidate_role_count": "private_production_corpus_summary_candidate_role_count_missing",
        "private_production_corpus_summary_complete_pair_count": "private_production_corpus_summary_complete_pair_count_missing",
        "private_production_corpus_summary_private_reference_count": "private_production_corpus_summary_private_reference_count_missing",
        "private_production_corpus_summary_pair_review_count": "private_production_corpus_summary_pair_review_count_missing",
        "private_production_corpus_summary_source_document_review_count": "private_production_corpus_summary_source_document_review_count_missing",
        "private_production_corpus_summary_privacy_review_count": "private_production_corpus_summary_privacy_review_count_missing",
        "private_production_corpus_summary_license_review_count": "private_production_corpus_summary_license_review_count_missing",
        "private_production_corpus_summary_residual_risk_review_count": "private_production_corpus_summary_residual_risk_review_count_missing",
        "private_production_corpus_summary_training_scope_review_count": "private_production_corpus_summary_training_scope_review_count_missing",
    }
    blockers = [
        blocker
        for key, blocker in required_true_flags.items()
        if not bool_value(evidence, key)
    ]
    blockers.extend(
        blocker
        for key, blocker in required_false_flags.items()
        if not false_value(evidence, key)
    )
    blockers.extend(
        blocker
        for key, blocker in required_positive_counts.items()
        if not positive_int_value(evidence, key)
    )

    private_manifest_env = str_value(evidence, "private_manifest_path_env")
    private_summary_env = str_value(evidence, "private_summary_path_env")
    if str_value(evidence, "manifest_path"):
        blockers.append("private_manifest_path_env_required_for_ready_evidence")
    if not private_manifest_env:
        blockers.append("private_manifest_path_env_not_configured")
    else:
        blockers.extend(validate_private_manifest_env_key(private_manifest_env))
    if not private_summary_env:
        blockers.append("private_summary_path_env_not_configured")
    else:
        if not ENV_KEY_RE.match(private_summary_env):
            blockers.append("private_summary_path_env_invalid")
        if any(fragment in private_summary_env.lower() for fragment in FORBIDDEN_ENV_KEY_FRAGMENTS):
            blockers.append("private_summary_path_env_secret_like")

    manifest_record_count = int_value(evidence, "private_manifest_record_count", 0)
    manifest_candidate_role_count = int_value(
        evidence,
        "private_manifest_candidate_role_count",
        0,
    )
    manifest_complete_pair_count = int_value(
        evidence,
        "private_manifest_complete_pair_count",
        0,
    )
    summary_manifest_record_count = int_value(
        evidence,
        "private_production_corpus_summary_manifest_record_count",
        0,
    )
    summary_candidate_role_count = int_value(
        evidence,
        "private_production_corpus_summary_candidate_role_count",
        0,
    )
    summary_complete_pair_count = int_value(
        evidence,
        "private_production_corpus_summary_complete_pair_count",
        0,
    )
    pair_review_count = int_value(
        evidence,
        "private_production_corpus_summary_pair_review_count",
        0,
    )
    source_document_review_count = int_value(
        evidence,
        "private_production_corpus_summary_source_document_review_count",
        0,
    )
    if (
        summary_manifest_record_count
        and summary_manifest_record_count != manifest_record_count
    ):
        blockers.append("private_summary_manifest_record_count_mismatch")
    if (
        summary_candidate_role_count
        and summary_candidate_role_count != manifest_candidate_role_count
    ):
        blockers.append("private_summary_candidate_role_count_mismatch")
    if (
        summary_complete_pair_count
        and summary_complete_pair_count != manifest_complete_pair_count
    ):
        blockers.append("private_summary_complete_pair_count_mismatch")
    if pair_review_count and pair_review_count < manifest_complete_pair_count:
        blockers.append("private_summary_pair_review_count_below_complete_pair_count")
    if (
        source_document_review_count
        and source_document_review_count < manifest_candidate_role_count
    ):
        blockers.append(
            "private_summary_source_document_review_count_below_candidate_role_count"
        )

    return requirement(
        requirement_id="production_corpus_private_summary_metadata",
        name="Private production-corpus manifest and summary metadata is checked without exposing values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            **{key: bool_value(evidence, key) for key in required_true_flags},
            **{key: bool_value(evidence, key) for key in required_false_flags},
            **{key: evidence.get(key, 0) for key in required_positive_counts},
            "private_manifest_path_env": private_manifest_env or None,
            "private_summary_path_env": private_summary_env or None,
            "manifest_path_value_included": bool(str_value(evidence, "manifest_path")),
            "values_redacted": True,
        },
    )


def manifest_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payload, errors = load_json(path)
    if errors:
        return [], errors
    raw_records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(raw_records, list):
        return [], ["manifest_records_not_list"]
    return [record for record in raw_records if isinstance(record, dict)], []


def is_production_training_pair_candidate(record: dict[str, Any]) -> bool:
    return (
        str(record.get("source_type") or "") in PRODUCTION_PAIR_SOURCE_TYPES
        and bool(record.get("training_eligible"))
        and str(record.get("document_role") or "") in REQUIRED_PAIR_ROLES
        and str(record.get("phi_status") or "") in TRAINING_ALLOWED_PHI_STATUSES
        and str(record.get("review_status") or "") in TRAINING_ALLOWED_REVIEW_STATUSES
        and bool(record.get("pair_id"))
    )


def manifest_pair_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    pairing = evidence.get("pairing_requirements", {})
    min_pairs = int_value(pairing, "minimum_approved_non_synthetic_pair_count", 1)
    configured_manifest_path = str_value(evidence, "manifest_path")
    manifest_path_source = "source_control_or_relative_path"
    manifest_path_value_included = True
    manifest_path_label: str | None
    manifest_env_name = ""
    manifest_path_errors: list[str] = []
    if configured_manifest_path:
        manifest_path = resolve_path(configured_manifest_path, evidence_path)
        manifest_path_label = str(manifest_path)
    elif str_value(evidence, "private_manifest_path_env") or bool_value(
        evidence,
        "private_manifest_path_configured",
    ):
        manifest_path_source = "private_env"
        manifest_path_value_included = False
        manifest_env_name = private_manifest_env_key(evidence)
        manifest_path_label = f"<private_manifest_path_env:{manifest_env_name}>"
        manifest_path, manifest_path_errors = private_manifest_path_from_env(
            manifest_env_name
        )
    else:
        manifest_path = DEFAULT_MANIFEST
        manifest_path_label = str(manifest_path)
    blockers = list(manifest_path_errors)
    if manifest_path and manifest_path_source == "private_env":
        if not manifest_path.exists():
            blockers.append("private_manifest_path_missing")
            records, errors = [], []
        elif not manifest_path.is_file():
            blockers.append("private_manifest_path_not_file")
            records, errors = [], []
        else:
            records, errors = manifest_records(manifest_path)
    else:
        records, errors = manifest_records(manifest_path) if manifest_path else ([], [])
    blockers.extend(errors)

    counts_by_source_type: Counter[str] = Counter()
    training_source_types: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    production_pair_roles: dict[str, set[str]] = defaultdict(set)
    for record in records:
        source_type = str(record.get("source_type") or "unknown")
        document_role = str(record.get("document_role") or "unknown")
        counts_by_source_type[source_type] += 1
        role_counts[document_role] += 1
        if record.get("training_eligible"):
            training_source_types[source_type] += 1
        if is_production_training_pair_candidate(record):
            production_pair_roles[str(record["pair_id"])].add(document_role)

    complete_pair_count = sum(
        1 for roles in production_pair_roles.values() if REQUIRED_PAIR_ROLES.issubset(roles)
    )
    if complete_pair_count < min_pairs:
        blockers.append("approved_non_synthetic_pair_count_below_minimum")
    if not bool_value(pairing, "denial_and_appeal_roles_required"):
        blockers.append("denial_and_appeal_roles_not_required")
    if not bool_value(pairing, "pair_ids_reviewed_outside_source_control"):
        blockers.append("pair_ids_not_reviewed_outside_source_control")
    if not bool_value(pairing, "source_documents_reviewed_outside_source_control"):
        blockers.append("source_documents_not_reviewed_outside_source_control")

    return requirement(
        requirement_id="production_corpus_manifest_pair_evidence",
        name="Manifest includes approved non-synthetic denial/appeal training pairs",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "manifest_path": manifest_path_label,
            "manifest_path_source": manifest_path_source,
            "private_manifest_path_env": manifest_env_name or None,
            "manifest_path_value_included": manifest_path_value_included,
            "record_count": len(records),
            "counts_by_source_type": dict(sorted(counts_by_source_type.items())),
            "training_source_types": dict(sorted(training_source_types.items())),
            "role_counts": dict(sorted(role_counts.items())),
            "accepted_production_source_types": sorted(PRODUCTION_PAIR_SOURCE_TYPES),
            "complete_production_pair_count": complete_pair_count,
            "minimum_required_production_pair_count": min_pairs,
            "denial_and_appeal_roles_required": bool_value(pairing, "denial_and_appeal_roles_required"),
            "pair_ids_reviewed_outside_source_control": bool_value(pairing, "pair_ids_reviewed_outside_source_control"),
            "source_documents_reviewed_outside_source_control": bool_value(pairing, "source_documents_reviewed_outside_source_control"),
            "values_redacted": True,
        },
    )


def build_report(evidence_path: Path = DEFAULT_EVIDENCE) -> dict[str, Any]:
    evidence, errors = load_json(evidence_path)
    if errors:
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}

    requirements = [
        evidence_format_requirement(evidence),
        no_values_requirement(evidence_path, evidence),
        corpus_review_requirement(evidence),
        operator_runbook_requirement(evidence_path, evidence),
        collection_license_checklist_requirement(evidence_path, evidence),
        pair_source_checklist_requirement(evidence_path, evidence),
        private_evidence_renderer_requirement(evidence_path, evidence),
        private_summary_metadata_requirement(evidence),
        manifest_pair_requirement(evidence_path, evidence),
    ]
    if errors:
        requirements[0]["blockers"].extend(errors)
        requirements[0]["status"] = "blocked"

    blocked_items = [item for item in requirements if item["status"] == "blocked"]
    ready_item_count = sum(1 for item in requirements if item["status"] == "ready")
    safe_to_review = all(
        item["status"] == "ready"
        for item in requirements[:2]
    )
    production_corpus_ready = not blocked_items

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate production denial/appeal corpus evidence without storing "
            "PHI, secrets, approval values, source paths, checksums, or raw documents."
        ),
        "evidence_path": str(evidence_path),
        "requirements": requirements,
        "ready_item_count": ready_item_count,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "safe_to_review": safe_to_review,
        "production_corpus_ready": production_corpus_ready,
        "notes": [
            "This validator reads local JSON and manifest metadata only; it does not open raw source documents.",
            "Approval references, source paths, checksums, raw denial letters, raw appeal letters, PHI, and production document details must remain outside the evidence packet.",
            "A template evidence file is expected to be safe_to_review=true but production_corpus_ready=false until approved non-synthetic paired corpus evidence is present.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.evidence)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.report} production_corpus_ready={report['production_corpus_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and not report["production_corpus_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
