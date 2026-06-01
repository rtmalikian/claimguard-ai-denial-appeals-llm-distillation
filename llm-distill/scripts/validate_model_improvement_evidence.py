#!/usr/bin/env python3
"""Validate model-improvement approval evidence without storing values."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "model_improvement_evidence"
    / "model_improvement_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "model_improvement_evidence_report.json"
DEFAULT_PRIVATE_ENV_RENDERER = DISTILL_DIR / "scripts" / "render_model_improvement_private_env.py"
EXPECTED_ARTIFACT = "claimguard_model_improvement_evidence"
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "approval_reference",
    "authorization_header",
    "baa_document",
    "consent_notice",
    "credential",
    "document_content",
    "legal_document",
    "password",
    "raw_document",
    "secret",
    "token",
    "user_data",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "approval_reference_configured",
    "consent_notice_version_configured",
    "no_approval_reference_values_attested",
    "no_phi_or_secret_values_attested",
    "no_user_data_content_attested",
    "stores_approval_reference_values",
    "stores_user_data_content",
}
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: not production-ready",
    "USER_DATA_MODEL_IMPROVEMENT_ENABLED",
    "Store approval references only in approved private runtime configuration",
    "render_model_improvement_private_env.py",
    "redacted booleans/counts only",
    "Do not store approval reference values",
    "Do not use external PHI de-identification services",
    "Do not train on raw PHI",
    "Approved corpus import must not automatically opt",
    "Model improvement requested",
    "model_improvement_ready=false",
)
PRIVATE_ENV_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "USER_DATA_MODEL_IMPROVEMENT_ENABLED",
    "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
    "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
    "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION",
    "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE",
    "USER_DATA_MODEL_IMPROVEMENT_PRIVATE_SUMMARY_PATH",
    "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT",
    "_validate_private_model_improvement_summary",
    "model-improvement evidence report is not ready",
    "evidence_report_checked",
    "evidence_report_ready",
    "private_model_improvement_summary_checked",
    "private_model_improvement_summary_path_value_included",
    "private_model_improvement_summary_environment_variable_count",
    "private_model_improvement_summary_private_reference_count",
    "private_model_improvement_summary_consent_notice_count",
    "private_model_improvement_summary_raw_values_included",
    "unsupported fields",
    "approval_reference_value_included",
    "consent_notice_value_included",
    "raw_env_values_included",
    "0600",
    "values_redacted",
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    if not path.exists():
        return None, [f"missing evidence file: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {path}: {exc}"]


def bool_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is True


def str_value(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    return value if isinstance(value, str) else ""


def false_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is False


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
                findings.append(
                    f"{child_path}: raw approval, consent, user-data, secret, or document value key is not allowed"
                )
            findings.extend(find_forbidden_value_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden_value_keys(child, f"{path}[{index}]"))
    return findings


def resolve_repo_path(raw_path: str, base_path: Path) -> Path:
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


def evidence_format_requirement(evidence: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(evidence, dict):
        blockers.append("evidence must be a JSON object")
        evidence = {}
    if evidence.get("artifact") != EXPECTED_ARTIFACT:
        blockers.append(f"artifact must be {EXPECTED_ARTIFACT}")
    for section_name in [
        "legal_controls",
        "runtime_controls",
        "safety_boundaries",
        "review_boundaries",
    ]:
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="model_improvement_evidence_format",
        name="Model-improvement evidence has the required structure",
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
    no_approval_values_attested = bool_value(evidence, "no_approval_reference_values_attested")
    no_user_data_attested = bool_value(evidence, "no_user_data_content_attested")

    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"model-improvement evidence contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not no_phi_attested:
        blockers.append("no_phi_or_secret_values_attested is not true")
    if not no_approval_values_attested:
        blockers.append("no_approval_reference_values_attested is not true")
    if not no_user_data_attested:
        blockers.append("no_user_data_content_attested is not true")

    return requirement(
        requirement_id="model_improvement_no_phi_secret_or_values",
        name="Model-improvement evidence contains no PHI, secrets, approval references, or user data",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": no_phi_attested,
            "no_approval_reference_values_attested": no_approval_values_attested,
            "no_user_data_content_attested": no_user_data_attested,
            "values_redacted": True,
        },
    )


def legal_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("legal_controls", {})
    required_flags = {
        "source_control_approval_runbook_documented": "source_control_approval_runbook_not_documented",
        "source_control_private_env_renderer_documented": "source_control_private_env_renderer_not_documented",
        "model_improvement_requested": "model_improvement_not_requested",
        "legal_approval_attested": "legal_approval_not_attested",
        "baa_confirmed": "baa_not_confirmed",
        "consent_notice_version_configured": "consent_notice_version_not_configured",
        "approval_reference_configured": "approval_reference_not_configured",
        "data_use_scope_documented": "data_use_scope_not_documented",
        "retention_policy_reviewed": "retention_policy_not_reviewed",
        "revocation_path_reviewed": "revocation_path_not_reviewed",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="model_improvement_legal_controls",
        name="Legal, BAA, consent, approval, scope, retention, and revocation controls are attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def approval_runbook_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("legal_controls", {})
    runbook_configured = bool_value(section, "source_control_approval_runbook_documented")
    configured_path = str_value(section, "source_control_approval_runbook_path")
    runbook_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS)
    if not runbook_configured:
        blockers.append("source_control_approval_runbook_not_documented")
    if runbook_path is None:
        blockers.append("source_control_approval_runbook_path_missing")
        runbook_inside_repo = False
    else:
        runbook_inside_repo = path_is_within(runbook_path, REPO_ROOT)
        if not runbook_inside_repo:
            blockers.append("source_control_approval_runbook_must_be_inside_repo")
        if not runbook_path.exists():
            blockers.append("source_control_approval_runbook_missing")
    if runbook_path is not None and runbook_inside_repo and runbook_path.exists():
        try:
            runbook_text = runbook_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            runbook_text = ""
            blockers.append("source_control_approval_runbook_must_be_utf8")
        present_marker_count = sum(
            1 for marker in RUNBOOK_REQUIRED_MARKERS if marker in runbook_text
        )
        missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS) - present_marker_count
        if missing_marker_count:
            blockers.append("source_control_approval_runbook_required_markers_missing")

    return requirement(
        requirement_id="model_improvement_approval_runbook",
        name="Source-controlled model-improvement approval runbook is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_approval_runbook_documented": runbook_configured,
            "runbook_path": str(runbook_path) if runbook_path else None,
            "runbook_inside_source_control": bool(runbook_path and runbook_inside_repo),
            "runbook_exists": bool(runbook_path and runbook_path.exists()),
            "required_marker_count": len(RUNBOOK_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_runbook_text_included": False,
            "values_redacted": True,
        },
    )


def private_env_renderer_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("legal_controls", {})
    renderer_configured = bool_value(section, "source_control_private_env_renderer_documented")
    configured_path = str_value(section, "source_control_private_env_renderer_path")
    renderer_path = (
        resolve_repo_path(configured_path, evidence_path)
        if configured_path
        else DEFAULT_PRIVATE_ENV_RENDERER
    )
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(PRIVATE_ENV_RENDERER_REQUIRED_MARKERS)
    if not renderer_configured:
        blockers.append("source_control_private_env_renderer_not_documented")
    renderer_inside_repo = path_is_within(renderer_path, REPO_ROOT)
    if not renderer_inside_repo:
        blockers.append("source_control_private_env_renderer_must_be_inside_repo")
    elif not renderer_path.exists():
        blockers.append("source_control_private_env_renderer_missing")
    else:
        try:
            renderer_text = renderer_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            renderer_text = ""
            blockers.append("source_control_private_env_renderer_must_be_utf8")
        present_marker_count = sum(
            1 for marker in PRIVATE_ENV_RENDERER_REQUIRED_MARKERS if marker in renderer_text
        )
        missing_marker_count = (
            len(PRIVATE_ENV_RENDERER_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_private_env_renderer_required_markers_missing")

    return requirement(
        requirement_id="model_improvement_private_env_renderer",
        name="Source-controlled model-improvement private env renderer is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_env_renderer_documented": renderer_configured,
            "private_env_renderer_path": str(renderer_path),
            "private_env_renderer_inside_source_control": renderer_inside_repo,
            "private_env_renderer_exists": renderer_path.exists(),
            "required_marker_count": len(PRIVATE_ENV_RENDERER_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_renderer_text_included": False,
            "approval_reference_value_included": False,
            "consent_notice_value_included": False,
            "private_output_required": True,
            "values_redacted": True,
        },
    )


def runtime_controls_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_controls", {})
    required_flags = {
        "model_improvement_disabled_by_default": "model_improvement_not_disabled_by_default",
        "per_request_attestations_required": "per_request_attestations_not_required",
        "approved_corpus_import_does_not_auto_opt_in": "approved_corpus_import_auto_opt_in_not_blocked",
        "audit_logging_reviewed": "audit_logging_not_reviewed",
        "frontend_readiness_blockers_visible": "frontend_readiness_blockers_not_visible",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="model_improvement_runtime_controls",
        name="Runtime controls keep model improvement explicit, attested, audited, and visible",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def safety_boundaries_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("safety_boundaries", {})
    required_true_flags = {
        "external_phi_deidentification_disabled_by_default": (
            "external_phi_deidentification_not_disabled_by_default"
        ),
        "raw_phi_training_disabled": "raw_phi_training_not_disabled",
        "production_user_data_excluded_until_approval": (
            "production_user_data_not_excluded_until_approval"
        ),
        "training_jobs_require_ready_evidence_packet": (
            "training_jobs_do_not_require_ready_evidence_packet"
        ),
        "revocation_blocks_future_training_use": (
            "revocation_does_not_block_future_training_use"
        ),
    }
    blockers = [
        blocker
        for key, blocker in required_true_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="model_improvement_safety_boundaries",
        name="Model-improvement safety boundaries keep PHI and user data excluded until approvals are ready",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_true_flags},
    )


def review_boundaries_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("review_boundaries", {})
    required_false_flags = {
        "stores_approval_reference_values": "approval_reference_values_stored",
        "stores_user_data_content": "user_data_content_stored",
        "stores_raw_legal_or_baa_documents": "raw_legal_or_baa_documents_stored",
        "stores_credentials_or_tokens": "credentials_or_tokens_stored",
    }
    blockers = [
        blocker
        for key, blocker in required_false_flags.items()
        if not false_value(section, key)
    ]
    return requirement(
        requirement_id="model_improvement_review_boundaries",
        name="Evidence packet stores no approval values, user data, raw legal documents, or credentials",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "approval_reference_values_absent": false_value(section, "stores_approval_reference_values"),
            "user_data_content_absent": false_value(section, "stores_user_data_content"),
            "raw_legal_or_baa_documents_absent": false_value(section, "stores_raw_legal_or_baa_documents"),
            "credentials_or_tokens_absent": false_value(section, "stores_credentials_or_tokens"),
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
        legal_controls_requirement(evidence),
        approval_runbook_requirement(evidence_path, evidence),
        private_env_renderer_requirement(evidence_path, evidence),
        runtime_controls_requirement(evidence),
        safety_boundaries_requirement(evidence),
        review_boundaries_requirement(evidence),
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
    model_improvement_ready = not blocked_items

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate user-data model-improvement approval evidence without storing "
            "PHI, secrets, approval references, legal documents, consent documents, "
            "raw user data, or production document content."
        ),
        "evidence_path": str(evidence_path),
        "requirements": requirements,
        "ready_item_count": ready_item_count,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "safe_to_review": safe_to_review,
        "model_improvement_ready": model_improvement_ready,
        "notes": [
            "This validator reads a local JSON evidence packet only and does not call external legal, BAA, consent, or approval systems.",
            "Approval references, consent notices, legal documents, user data, PHI, secrets, and production document details must remain outside source control.",
            "A template evidence file is expected to be safe_to_review=true but model_improvement_ready=false until approval, runtime controls, and safety-boundary attestations are complete.",
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
        f"Wrote {args.report} model_improvement_ready={report['model_improvement_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and not report["model_improvement_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
