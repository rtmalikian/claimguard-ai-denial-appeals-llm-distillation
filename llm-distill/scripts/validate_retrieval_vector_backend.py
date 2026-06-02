#!/usr/bin/env python3
"""Validate retrieval vector backend evidence without storing values."""

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

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import write_source_controlled_report_json  # noqa: E402

DEFAULT_EVIDENCE = (
    DISTILL_DIR
    / "data"
    / "retrieval_vector_backend"
    / "vector_backend_evidence.template.json"
)
DEFAULT_REPORT = DISTILL_DIR / "evals" / "reports" / "retrieval_vector_backend_report.json"
DEFAULT_PRIVATE_ENV_RENDERER = DISTILL_DIR / "scripts" / "render_retrieval_vector_private_env.py"
DEFAULT_PRIVATE_PROVIDER_LOADER = (
    REPO_ROOT
    / "health-ai-medical-billing-medical-corporations-20260414_180528"
    / "app"
    / "services"
    / "retrieval_semantic_provider.py"
)
DEFAULT_RUNTIME_PRIVATE_EVIDENCE_RENDERER = (
    DISTILL_DIR / "scripts" / "render_retrieval_vector_runtime_private_evidence.py"
)
EXPECTED_ARTIFACT = "claimguard_retrieval_vector_backend_evidence"
FORBIDDEN_VALUE_KEY_FRAGMENTS = {
    "api_key",
    "authorization_header",
    "credential",
    "document_content",
    "embedding_service_url",
    "password",
    "raw_document",
    "secret",
    "source_text",
    "token",
    "vector_value",
    "vector_values",
}
ALLOWED_BOOLEAN_FLAG_KEYS = {
    "contains_secrets",
    "no_phi_or_secret_values_attested",
    "no_source_text_or_vector_values_attested",
    "source_text_redaction_verified",
}
RUNBOOK_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: not production-ready",
    "Configure semantic backend settings in private runtime configuration only",
    "Configure production vector backend settings in private runtime configuration",
    "render_retrieval_vector_private_env.py",
    "redacted booleans/counts only",
    "Do not store embedding service URLs",
    "hash embedding fallback development-only",
    "Reindex active retrieval and corpus chunks",
    "vector_backend_ready=false",
)
REINDEX_CHECKLIST_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: not reindexed for production.",
    "approved semantic embedding model required",
    "production vector backend required",
    "hash fallback disabled for production required",
    "application reindex operation available",
    "active retrieval chunks reindexed required",
    "stored hash embeddings absent required",
    "reindex job completion required",
    "reindex audit required",
    "vector backend health check required",
    "retrieval quality smoke check required",
    "boolean-only evidence",
    "no raw source text",
    "vector_backend_ready=false",
)
RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS = (
    "ClaimGuard AI is architected by Raphael Malikian",
    "Current status: not runtime-smoked for production.",
    "approved semantic embedding model required",
    "production vector backend required",
    "hash fallback disabled for production required",
    "active retrieval chunks reindexed required",
    "stored hash embeddings absent required",
    "vector backend health check required",
    "retrieval quality smoke check required",
    "backup restore review required",
    "rollback or disable path required",
    "metadata-only audit required",
    "boolean-only evidence",
    "no raw source text",
    "no raw vector values",
    "no embedding service URLs",
    "vector_backend_ready=false",
)
PRIVATE_ENV_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "RETRIEVAL_PRODUCTION_EMBEDDING_BACKEND",
    "RETRIEVAL_PRODUCTION_EMBEDDING_MODEL",
    "RETRIEVAL_PRODUCTION_VECTOR_BACKEND",
    "RETRIEVAL_VECTOR_PRIVATE_ENV_SUMMARY_PATH",
    "RETRIEVAL_EMBEDDING_BACKEND",
    "RETRIEVAL_EMBEDDING_MODEL",
    "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    "RETRIEVAL_VECTOR_BACKEND",
    "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
    "hash_fallback_disabled_for_production",
    "embedding_backend_value_included",
    "embedding_model_value_included",
    "vector_backend_value_included",
    "retrieval vector evidence report is not ready",
    "_validate_private_retrieval_vector_summary",
    "evidence_report_checked",
    "evidence_report_ready",
    "private_retrieval_vector_summary_checked",
    "private_retrieval_vector_summary_path_value_included",
    "private_retrieval_vector_summary_environment_variable_count",
    "private_retrieval_vector_summary_backend_value_count",
    "private_retrieval_vector_summary_evidence_report_count",
    "private_retrieval_vector_summary_raw_values_included",
    "raw_source_text_or_vector_values_included",
    "service_urls_included",
    "unsupported fields",
    "0600",
    "values_redacted",
)
PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS = (
    "PrivateSemanticEmbeddingProvider",
    "build_retrieval_embedding_provider",
    "private_embedding_provider_config_status",
    "RETRIEVAL_PRIVATE_EMBEDDING_URL",
    "RETRIEVAL_PRIVATE_EMBEDDING_TOKEN",
    "RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS",
    "private_embedding_endpoint_value_included",
    "private_embedding_token_value_included",
    "raw_text_included",
    "vector_values_included",
    "https",
    "loopback",
    "HashEmbeddingProvider",
)
RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS = (
    "RenderConfig",
    "refusing_to_write_inside_source_control",
    "claimguard_retrieval_vector_backend_evidence",
    "RETRIEVAL_VECTOR_HEALTH_EVIDENCE_REF",
    "RETRIEVAL_QUALITY_SMOKE_EVIDENCE_REF",
    "RETRIEVAL_VECTOR_REINDEX_AUDIT_EVIDENCE_REF",
    "RETRIEVAL_VECTOR_PRIVATE_RUNTIME_SUMMARY_PATH",
    "_validate_private_runtime_summary",
    "private_runtime_summary_checked",
    "private_runtime_summary_path_value_included",
    "private_runtime_summary_reindexed_chunk_count",
    "private_runtime_summary_vector_health_check_count",
    "private_runtime_summary_retrieval_quality_query_count",
    "private_runtime_summary_backup_restore_check_count",
    "private_runtime_summary_raw_values_included",
    "unsupported fields",
    "private_reference_values_included",
    "raw_source_text_included",
    "raw_vector_values_included",
    "vector_backend_ready_if_validated",
    "0600",
    "values_redacted",
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from report_output_sanitizer import sanitize_report_value  # noqa: E402
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


def false_value(section: dict[str, Any], key: str) -> bool:
    return section.get(key) is False


def positive_int_value(section: dict[str, Any], key: str) -> bool:
    value = section.get(key)
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


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
                findings.append(f"{child_path}: raw vector, source text, secret, or document value key is not allowed")
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
        "backend_configuration",
        "index_state",
        "governance_controls",
        "runtime_validation",
    ]:
        if not isinstance(evidence.get(section_name), dict):
            blockers.append(f"{section_name} section is required")
    return requirement(
        requirement_id="retrieval_vector_backend_evidence_format",
        name="Retrieval vector backend evidence has the required structure",
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
    attested_no_phi = bool_value(evidence, "no_phi_or_secret_values_attested")
    attested_no_values = bool_value(evidence, "no_source_text_or_vector_values_attested")

    blockers: list[str] = []
    if phi_findings:
        finding_types = sorted({finding["finding_type"] for finding in phi_findings})
        blockers.append(f"vector backend evidence contains PHI/PII-like metadata findings: {finding_types}")
    if forbidden_key_findings:
        blockers.extend(forbidden_key_findings)
    if not attested_no_phi:
        blockers.append("no_phi_or_secret_values_attested is not true")
    if not attested_no_values:
        blockers.append("no_source_text_or_vector_values_attested is not true")

    return requirement(
        requirement_id="retrieval_vector_backend_no_phi_secret_or_values",
        name="Vector backend evidence contains no PHI, secrets, source text, or vector values",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "evidence_path": str(evidence_path),
            "phi_finding_count": len(phi_findings),
            "phi_finding_types": sorted({finding["finding_type"] for finding in phi_findings}),
            "forbidden_value_key_count": len(forbidden_key_findings),
            "no_phi_or_secret_values_attested": attested_no_phi,
            "no_source_text_or_vector_values_attested": attested_no_values,
            "values_redacted": True,
        },
    )


def backend_configuration_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("backend_configuration", {})
    required_flags = {
        "source_control_private_env_renderer_documented": "source_control_private_env_renderer_not_documented",
        "source_control_private_embedding_provider_loader_documented": "source_control_private_embedding_provider_loader_not_documented",
        "semantic_backend_configured": "semantic_embedding_backend_not_configured",
        "embedding_model_configured": "embedding_model_not_configured",
        "embedding_model_approved": "embedding_model_not_approved",
        "production_vector_backend_configured": "production_vector_backend_not_configured",
        "hash_fallback_disabled_for_production": "hash_fallback_not_disabled_for_production",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    if bool_value(section, "contains_secrets"):
        blockers.append("backend_configuration_contains_secrets_attested_true")
    return requirement(
        requirement_id="retrieval_vector_backend_configuration",
        name="Production semantic embedding and vector backend configuration is attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "semantic_backend_configured": bool_value(section, "semantic_backend_configured"),
            "embedding_model_configured": bool_value(section, "embedding_model_configured"),
            "embedding_model_approved": bool_value(section, "embedding_model_approved"),
            "production_vector_backend_configured": bool_value(section, "production_vector_backend_configured"),
            "hash_fallback_disabled_for_production": bool_value(section, "hash_fallback_disabled_for_production"),
            "source_control_private_env_renderer_documented": bool_value(section, "source_control_private_env_renderer_documented"),
            "source_control_private_embedding_provider_loader_documented": bool_value(section, "source_control_private_embedding_provider_loader_documented"),
            "contains_secrets": bool_value(section, "contains_secrets"),
        },
    )


def private_env_renderer_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("backend_configuration", {})
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
    renderer_inside_source_control = path_is_within(renderer_path, REPO_ROOT)
    if not renderer_configured:
        blockers.append("source_control_private_env_renderer_not_documented")
    if not renderer_inside_source_control:
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
        requirement_id="retrieval_vector_backend_private_env_renderer",
        name="Source-controlled retrieval vector backend private env renderer is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_env_renderer_documented": renderer_configured,
            "private_env_renderer_path": str(renderer_path),
            "private_env_renderer_exists": renderer_path.exists(),
            "private_env_renderer_inside_source_control": renderer_inside_source_control,
            "required_marker_count": len(PRIVATE_ENV_RENDERER_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_renderer_text_included": False,
            "raw_env_values_included": False,
            "private_output_required": True,
            "values_redacted": True,
        },
    )


def private_provider_loader_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("backend_configuration", {})
    loader_configured = bool_value(
        section,
        "source_control_private_embedding_provider_loader_documented",
    )
    configured_path = str_value(
        section,
        "source_control_private_embedding_provider_loader_path",
    )
    loader_path = (
        resolve_repo_path(configured_path, evidence_path)
        if configured_path
        else DEFAULT_PRIVATE_PROVIDER_LOADER
    )
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS)
    loader_inside_source_control = path_is_within(loader_path, REPO_ROOT)
    if not loader_configured:
        blockers.append("source_control_private_embedding_provider_loader_not_documented")
    if not loader_inside_source_control:
        blockers.append(
            "source_control_private_embedding_provider_loader_must_be_inside_repo"
        )
    elif not loader_path.exists():
        blockers.append("source_control_private_embedding_provider_loader_missing")
    else:
        try:
            loader_text = loader_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            loader_text = ""
            blockers.append("source_control_private_embedding_provider_loader_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS
            if marker in loader_text
        )
        missing_marker_count = (
            len(PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_private_embedding_provider_loader_required_markers_missing")

    return requirement(
        requirement_id="retrieval_vector_backend_private_provider_loader",
        name="Source-controlled retrieval semantic provider loader is available",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_private_embedding_provider_loader_documented": loader_configured,
            "private_embedding_provider_loader_path": str(loader_path),
            "private_embedding_provider_loader_exists": loader_path.exists(),
            "private_embedding_provider_loader_inside_source_control": (
                loader_inside_source_control
            ),
            "required_marker_count": len(PRIVATE_PROVIDER_LOADER_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_loader_text_included": False,
            "raw_endpoint_or_token_values_included": False,
            "raw_source_text_or_vector_values_included": False,
            "values_redacted": True,
        },
    )


def operator_runbook_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    runbook_configured = bool_value(section, "source_control_runbook_documented")
    configured_path = str_value(section, "source_control_runbook_path")
    runbook_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS)
    runbook_inside_source_control = bool(
        runbook_path and path_is_within(runbook_path, REPO_ROOT)
    )
    if not runbook_configured:
        blockers.append("source_control_runbook_not_documented")
    if runbook_path is None:
        blockers.append("source_control_runbook_path_missing")
    elif not runbook_inside_source_control:
        blockers.append("source_control_runbook_must_be_inside_repo")
    elif not runbook_path.exists():
        blockers.append("source_control_runbook_missing")
    else:
        try:
            runbook_text = runbook_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            runbook_text = ""
            blockers.append("source_control_runbook_must_be_utf8")
        present_marker_count = sum(
            1 for marker in RUNBOOK_REQUIRED_MARKERS if marker in runbook_text
        )
        missing_marker_count = len(RUNBOOK_REQUIRED_MARKERS) - present_marker_count
        if missing_marker_count:
            blockers.append("source_control_runbook_required_markers_missing")

    return requirement(
        requirement_id="retrieval_vector_backend_operator_runbook",
        name="Source-controlled retrieval vector backend runbook is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_runbook_documented": runbook_configured,
            "runbook_path": str(runbook_path) if runbook_path else None,
            "runbook_exists": bool(runbook_path and runbook_path.exists()),
            "runbook_inside_source_control": runbook_inside_source_control,
            "required_marker_count": len(RUNBOOK_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_runbook_text_included": False,
            "values_redacted": True,
        },
    )


def reindex_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("index_state", {})
    checklist_configured = bool_value(section, "source_control_reindex_checklist_documented")
    configured_path = str_value(section, "source_control_reindex_checklist_path")
    checklist_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(REINDEX_CHECKLIST_REQUIRED_MARKERS)
    checklist_inside_source_control = bool(
        checklist_path and path_is_within(checklist_path, REPO_ROOT)
    )
    if not checklist_configured:
        blockers.append("source_control_reindex_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_reindex_checklist_path_missing")
    elif not checklist_inside_source_control:
        blockers.append("source_control_reindex_checklist_must_be_inside_repo")
    elif not checklist_path.exists():
        blockers.append("source_control_reindex_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_reindex_checklist_must_be_utf8")
        present_marker_count = sum(
            1 for marker in REINDEX_CHECKLIST_REQUIRED_MARKERS if marker in checklist_text
        )
        missing_marker_count = len(REINDEX_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        if missing_marker_count:
            blockers.append("source_control_reindex_checklist_required_markers_missing")

    return requirement(
        requirement_id="retrieval_vector_backend_reindex_checklist",
        name="Source-controlled retrieval vector reindex checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_reindex_checklist_documented": checklist_configured,
            "checklist_path": str(checklist_path) if checklist_path else None,
            "checklist_exists": bool(checklist_path and checklist_path.exists()),
            "reindex_checklist_inside_source_control": checklist_inside_source_control,
            "required_marker_count": len(REINDEX_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def runtime_smoke_checklist_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_validation", {})
    checklist_configured = bool_value(
        section,
        "source_control_runtime_smoke_checklist_documented",
    )
    configured_path = str_value(section, "source_control_runtime_smoke_checklist_path")
    checklist_path = resolve_repo_path(configured_path, evidence_path) if configured_path else None
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS)
    checklist_inside_source_control = bool(
        checklist_path and path_is_within(checklist_path, REPO_ROOT)
    )
    if not checklist_configured:
        blockers.append("source_control_runtime_smoke_checklist_not_documented")
    if checklist_path is None:
        blockers.append("source_control_runtime_smoke_checklist_path_missing")
    elif not checklist_inside_source_control:
        blockers.append("source_control_runtime_smoke_checklist_must_be_inside_repo")
    elif not checklist_path.exists():
        blockers.append("source_control_runtime_smoke_checklist_missing")
    else:
        try:
            checklist_text = checklist_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            checklist_text = ""
            blockers.append("source_control_runtime_smoke_checklist_must_be_utf8")
        present_marker_count = sum(
            1 for marker in RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS if marker in checklist_text
        )
        missing_marker_count = (
            len(RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS) - present_marker_count
        )
        if missing_marker_count:
            blockers.append("source_control_runtime_smoke_checklist_required_markers_missing")

    return requirement(
        requirement_id="retrieval_vector_backend_runtime_smoke_checklist",
        name="Source-controlled retrieval vector runtime smoke checklist is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_runtime_smoke_checklist_documented": checklist_configured,
            "checklist_path": str(checklist_path) if checklist_path else None,
            "checklist_exists": bool(checklist_path and checklist_path.exists()),
            "runtime_smoke_checklist_inside_source_control": (
                checklist_inside_source_control
            ),
            "required_marker_count": len(RUNTIME_SMOKE_CHECKLIST_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_checklist_text_included": False,
            "values_redacted": True,
        },
    )


def runtime_private_evidence_renderer_requirement(evidence_path: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_validation", {})
    renderer_configured = bool_value(
        section,
        "source_control_runtime_private_evidence_renderer_documented",
    )
    configured_path = str_value(section, "runtime_private_evidence_renderer_path")
    renderer_path = (
        resolve_repo_path(configured_path, evidence_path)
        if configured_path
        else DEFAULT_RUNTIME_PRIVATE_EVIDENCE_RENDERER
    )
    blockers: list[str] = []
    present_marker_count = 0
    missing_marker_count = len(RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS)
    renderer_inside_source_control = path_is_within(renderer_path, REPO_ROOT)
    if not renderer_configured:
        blockers.append("source_control_runtime_private_evidence_renderer_not_documented")
    if not renderer_inside_source_control:
        blockers.append(
            "source_control_runtime_private_evidence_renderer_must_be_inside_repo"
        )
    elif not renderer_path.exists():
        blockers.append("source_control_runtime_private_evidence_renderer_missing")
    else:
        try:
            renderer_text = renderer_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            renderer_text = ""
            blockers.append("source_control_runtime_private_evidence_renderer_must_be_utf8")
        present_marker_count = sum(
            1
            for marker in RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS
            if marker in renderer_text
        )
        missing_marker_count = (
            len(RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS)
            - present_marker_count
        )
        if missing_marker_count:
            blockers.append(
                "source_control_runtime_private_evidence_renderer_required_markers_missing"
            )

    return requirement(
        requirement_id="retrieval_vector_backend_runtime_private_evidence_renderer",
        name="Source-controlled retrieval runtime private evidence renderer is documented",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            "source_control_runtime_private_evidence_renderer_documented": renderer_configured,
            "runtime_private_evidence_renderer_path": str(renderer_path),
            "runtime_private_evidence_renderer_exists": renderer_path.exists(),
            "runtime_private_evidence_renderer_inside_source_control": (
                renderer_inside_source_control
            ),
            "required_marker_count": len(RUNTIME_PRIVATE_EVIDENCE_RENDERER_REQUIRED_MARKERS),
            "present_marker_count": present_marker_count,
            "missing_marker_count": missing_marker_count,
            "raw_renderer_text_included": False,
            "raw_private_reference_values_included": False,
            "raw_source_text_or_vector_values_included": False,
            "values_redacted": True,
        },
    )


def index_state_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("index_state", {})
    required_flags = {
        "application_reindex_operation_available": "application_reindex_operation_not_available",
        "active_retrieval_chunks_indexed": "active_retrieval_chunks_not_indexed",
        "stored_hash_embeddings_absent": "stored_hash_embeddings_still_present",
        "reindex_job_completed": "reindex_job_not_completed",
        "reindex_audit_checked": "reindex_audit_not_checked",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="retrieval_vector_backend_index_state",
        name="Retrieval chunks are indexed with production semantic embeddings",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def governance_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("governance_controls", {})
    required_flags = {
        "source_control_runbook_documented": "source_control_runbook_not_documented",
        "role_scoped_access_verified": "role_scoped_access_not_verified",
        "retention_delete_verified": "retention_delete_not_verified",
        "audit_dashboard_verified": "audit_dashboard_not_verified",
        "encrypted_storage_verified": "encrypted_storage_not_verified",
        "source_text_redaction_verified": "source_text_redaction_not_verified",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    return requirement(
        requirement_id="retrieval_vector_backend_governance",
        name="Vector backend access, retention, audit, and redaction controls are verified",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={key: bool_value(section, key) for key in required_flags},
    )


def runtime_validation_requirement(evidence: dict[str, Any]) -> dict[str, Any]:
    section = evidence.get("runtime_validation", {})
    required_flags = {
        "vector_backend_health_checked": "vector_backend_health_not_checked",
        "retrieval_quality_smoke_passed": "retrieval_quality_smoke_not_passed",
        "backup_restore_reviewed": "backup_restore_not_reviewed",
        "disable_or_rollback_path_reviewed": "disable_or_rollback_path_not_reviewed",
        "health_evidence_reference_configured": "health_evidence_reference_not_configured",
        "quality_evidence_reference_configured": "quality_evidence_reference_not_configured",
        "reindex_evidence_reference_configured": "reindex_evidence_reference_not_configured",
    }
    summary_true_flags = {
        "private_runtime_summary_path_configured": "private_runtime_summary_path_not_configured",
        "private_runtime_summary_checked": "private_runtime_summary_not_checked",
    }
    summary_false_flags = {
        "private_runtime_summary_path_value_included": "private_runtime_summary_path_value_included",
        "private_runtime_summary_raw_values_included": "private_runtime_summary_raw_values_included",
    }
    summary_positive_counts = {
        "private_runtime_summary_reindexed_chunk_count": "private_runtime_summary_reindexed_chunk_count_missing",
        "private_runtime_summary_vector_health_check_count": "private_runtime_summary_vector_health_check_count_missing",
        "private_runtime_summary_retrieval_quality_query_count": "private_runtime_summary_retrieval_quality_query_count_missing",
        "private_runtime_summary_backup_restore_check_count": "private_runtime_summary_backup_restore_check_count_missing",
    }
    blockers = [
        blocker
        for key, blocker in required_flags.items()
        if not bool_value(section, key)
    ]
    blockers.extend(
        blocker
        for key, blocker in summary_true_flags.items()
        if not bool_value(evidence, key)
    )
    blockers.extend(
        blocker
        for key, blocker in summary_false_flags.items()
        if not false_value(evidence, key)
    )
    blockers.extend(
        blocker
        for key, blocker in summary_positive_counts.items()
        if not positive_int_value(evidence, key)
    )
    return requirement(
        requirement_id="retrieval_vector_backend_runtime_validation",
        name="Vector backend health, quality, backup, and rollback validation are attested",
        status="blocked" if blockers else "ready",
        blockers=blockers,
        evidence={
            **{key: bool_value(section, key) for key in required_flags},
            **{key: bool_value(evidence, key) for key in summary_true_flags},
            **{key: bool_value(evidence, key) for key in summary_false_flags},
            **{key: evidence.get(key, 0) for key in summary_positive_counts},
            "private_runtime_reference_values_included": False,
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
        backend_configuration_requirement(evidence),
        private_env_renderer_requirement(evidence_path, evidence),
        private_provider_loader_requirement(evidence_path, evidence),
        operator_runbook_requirement(evidence_path, evidence),
        reindex_checklist_requirement(evidence_path, evidence),
        index_state_requirement(evidence),
        governance_requirement(evidence),
        runtime_smoke_checklist_requirement(evidence_path, evidence),
        runtime_private_evidence_renderer_requirement(evidence_path, evidence),
        runtime_validation_requirement(evidence),
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
    vector_backend_ready = not blocked_items

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": (
            "Validate production retrieval vector backend evidence without storing "
            "PHI, secrets, source text, vector values, or production document content."
        ),
        "evidence_path": str(evidence_path),
        "requirements": requirements,
        "ready_item_count": ready_item_count,
        "blocked_item_count": len(blocked_items),
        "blocked_items": blocked_items,
        "safe_to_review": safe_to_review,
        "vector_backend_ready": vector_backend_ready,
        "notes": [
            "This validator reads a local JSON evidence packet only and does not call vector stores or embedding providers.",
            "Embedding service URLs, credentials, vector values, source text, and production document details must remain outside source control.",
            "A template evidence file is expected to be safe_to_review=true but vector_backend_ready=false until configuration, reindex, governance, and runtime evidence are complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_report(args.evidence)
    safe_report = sanitize_report_value(report, REPO_ROOT)
    write_source_controlled_report_json(args.report, safe_report, REPO_ROOT)
    print(
        f"Wrote {args.report} vector_backend_ready={report['vector_backend_ready']} "
        f"safe_to_review={report['safe_to_review']} blocked={report['blocked_item_count']}"
    )
    if args.fail_on_blocked and not report["vector_backend_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
