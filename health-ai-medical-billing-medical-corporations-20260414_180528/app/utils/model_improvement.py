"""Compliance gates for user-data model-improvement opt-in."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ENVS = {"prod", "production"}


@dataclass(frozen=True)
class ModelImprovementComplianceStatus:
    enabled: bool
    legal_approval_confirmed: bool
    baa_confirmed: bool
    consent_notice_version: str | None
    approval_reference_configured: bool
    ready: bool
    blockers: list[str]

    def model_dump(self) -> dict:
        return asdict(self)


def _str_value(settings_like, name: str, default: str = "") -> str:
    value = getattr(settings_like, name, default)
    if value is None:
        return default
    return str(value).strip()


def _bool_value(settings_like, name: str) -> bool:
    return getattr(settings_like, name, False) is True


def _configured_report_path(settings_like) -> Path | None:
    raw_path = _str_value(
        settings_like,
        "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT",
        "llm-distill/evals/reports/model_improvement_evidence_report.json",
    )
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _load_evidence_report(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _blocked_requirement_ids(report: dict[str, Any] | None) -> list[str]:
    if not isinstance(report, dict):
        return []
    blocked_ids: list[str] = []
    requirements = report.get("requirements")
    if not isinstance(requirements, list):
        return blocked_ids
    for item in requirements:
        if not isinstance(item, dict) or item.get("status") != "blocked":
            continue
        requirement_id = item.get("requirement_id")
        if isinstance(requirement_id, str) and requirement_id:
            blocked_ids.append(requirement_id)
    return blocked_ids


def model_improvement_compliance_status(
    settings_like=None,
) -> ModelImprovementComplianceStatus:
    runtime_settings = settings_like or settings
    consent_notice_version = (
        _str_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION")
        or None
    )
    approval_reference_configured = bool(
        _str_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE")
    )
    blockers: list[str] = []
    if not _bool_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED"):
        blockers.append("user_data_model_improvement_disabled")
    if not _bool_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED"):
        blockers.append("legal_approval_missing")
    if not _bool_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED"):
        blockers.append("baa_confirmation_missing")
    if not consent_notice_version:
        blockers.append("consent_notice_version_missing")
    if not approval_reference_configured:
        blockers.append("approval_reference_missing")

    return ModelImprovementComplianceStatus(
        enabled=_bool_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED"),
        legal_approval_confirmed=_bool_value(
            runtime_settings,
            "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
        ),
        baa_confirmed=_bool_value(
            runtime_settings,
            "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
        ),
        consent_notice_version=consent_notice_version,
        approval_reference_configured=approval_reference_configured,
        ready=not blockers,
        blockers=blockers,
    )


def validate_model_improvement_opt_in(
    *,
    requested: bool,
    legal_approval_attested: bool = False,
    baa_attested: bool = False,
    consent_attested: bool = False,
    consent_notice_version: str | None = None,
) -> ModelImprovementComplianceStatus:
    status = model_improvement_compliance_status()
    if not requested:
        return status
    if not status.ready:
        raise ValueError(
            "User-data model improvement is disabled pending legal, BAA, and "
            f"consent readiness: {', '.join(status.blockers)}."
        )
    if not legal_approval_attested:
        raise ValueError("Model-improvement opt-in requires legal approval attestation.")
    if not baa_attested:
        raise ValueError("Model-improvement opt-in requires BAA attestation.")
    if not consent_attested:
        raise ValueError("Model-improvement opt-in requires consent attestation.")

    expected_version = status.consent_notice_version or ""
    supplied_version = (consent_notice_version or "").strip()
    if supplied_version != expected_version:
        raise ValueError(
            "Model-improvement opt-in requires the configured consent notice version."
        )
    return status


def validate_model_improvement_startup_config(
    *,
    settings_like=None,
    evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    app_env = _str_value(runtime_settings, "APP_ENV", "development").lower()
    app_env_is_production = app_env in PRODUCTION_ENVS
    enabled = _bool_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED")
    legal_approval_confirmed = _bool_value(
        runtime_settings,
        "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
    )
    baa_confirmed = _bool_value(
        runtime_settings,
        "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
    )
    consent_notice_version_configured = bool(
        _str_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION")
    )
    approval_reference_configured = bool(
        _str_value(runtime_settings, "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE")
    )

    evidence_report_configured = _configured_report_path(runtime_settings) is not None
    evidence_report_checked = evidence_report is not None
    if enabled and evidence_report is None:
        report_path = _configured_report_path(runtime_settings)
        if report_path is not None:
            evidence_report = _load_evidence_report(report_path)
            evidence_report_checked = evidence_report is not None

    report_ready = (
        evidence_report.get("model_improvement_ready") is True
        if isinstance(evidence_report, dict)
        else None
    )
    report_safe_to_review = (
        evidence_report.get("safe_to_review") is True
        if isinstance(evidence_report, dict)
        else None
    )
    report_blocked_requirement_ids = _blocked_requirement_ids(evidence_report)

    blockers: list[str] = []
    if enabled:
        if not legal_approval_confirmed:
            blockers.append("legal_approval_missing")
        if not baa_confirmed:
            blockers.append("baa_confirmation_missing")
        if not consent_notice_version_configured:
            blockers.append("consent_notice_version_missing")
        if not approval_reference_configured:
            blockers.append("approval_reference_missing")
        if not evidence_report_configured:
            blockers.append("model_improvement_evidence_report_path_missing")
        elif not evidence_report_checked:
            blockers.append("model_improvement_evidence_report_unavailable")
        if evidence_report_checked and report_ready is not True:
            blockers.append("model_improvement_evidence_report_not_ready")
        if evidence_report_checked and report_safe_to_review is not True:
            blockers.append("model_improvement_evidence_report_not_safe_to_review")
        if report_blocked_requirement_ids:
            blockers.append("model_improvement_evidence_report_has_blocked_requirements")

    safe_context = {
        "approval_reference_value_included": False,
        "consent_notice_version_value_included": False,
        "evidence_report_path_included": False,
        "raw_evidence_report_included": False,
        "raw_user_data_included": False,
        "raw_phi_included": False,
        "raw_secret_included": False,
        "raw_legal_document_included": False,
    }
    report = {
        "app_env": app_env,
        "app_env_is_production": app_env_is_production,
        "enabled": enabled,
        "legal_approval_confirmed": legal_approval_confirmed,
        "baa_confirmed": baa_confirmed,
        "consent_notice_version_configured": consent_notice_version_configured,
        "approval_reference_configured": approval_reference_configured,
        "evidence_report_configured": evidence_report_configured,
        "evidence_report_checked": evidence_report_checked,
        "evidence_report_ready": report_ready,
        "evidence_report_safe_to_review": report_safe_to_review,
        "evidence_report_blocked_requirement_ids": report_blocked_requirement_ids,
        "blockers": blockers,
        "startup_ready": not blockers,
        "fail_fast_required": app_env_is_production and enabled and bool(blockers),
        "safe_context": safe_context,
    }

    log_payload = {
        key: value
        for key, value in report.items()
        if key not in {"blockers"}
    }
    log_payload["blocker_count"] = len(blockers)
    log_payload["blockers"] = blockers
    if blockers:
        logger.warning(
            "model_improvement_startup_config_validation_failed",
            extra={"model_improvement_startup_config": log_payload},
        )
    else:
        logger.info(
            "model_improvement_startup_config_validation_passed",
            extra={"model_improvement_startup_config": log_payload},
        )
    if report["fail_fast_required"]:
        raise RuntimeError(
            "User-data model improvement startup configuration is not production-ready."
        )
    return report
