import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ENVS = {"prod", "production"}


def _str_value(settings_like, name: str, default: str = "") -> str:
    value = getattr(settings_like, name, default)
    if value is None:
        return default
    return str(value).strip()


def _configured_report_path(settings_like) -> Path | None:
    raw_path = _str_value(
        settings_like,
        "DEPENDENCY_SECURITY_EVIDENCE_REPORT",
        "llm-distill/evals/reports/dependency_security_evidence_report.json",
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
    requirements = report.get("requirements")
    if not isinstance(requirements, list):
        return []
    blocked_ids: list[str] = []
    for item in requirements:
        if not isinstance(item, dict) or item.get("status") != "blocked":
            continue
        requirement_id = item.get("requirement_id")
        if isinstance(requirement_id, str) and requirement_id:
            blocked_ids.append(requirement_id)
    return blocked_ids


def validate_dependency_security_startup_config(
    *,
    settings_like=None,
    evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    app_env = _str_value(runtime_settings, "APP_ENV", "development").lower()
    app_env_is_production = app_env in PRODUCTION_ENVS
    report_path = _configured_report_path(runtime_settings)
    evidence_report_configured = report_path is not None
    evidence_report_checked = evidence_report is not None

    if evidence_report is None and report_path is not None:
        evidence_report = _load_evidence_report(report_path)
        evidence_report_checked = evidence_report is not None

    report_ready = (
        evidence_report.get("dependency_security_ready") is True
        if isinstance(evidence_report, dict)
        else None
    )
    report_safe_to_review = (
        evidence_report.get("safe_to_review") is True
        if isinstance(evidence_report, dict)
        else None
    )
    blocked_requirement_ids = _blocked_requirement_ids(evidence_report)

    blockers: list[str] = []
    if not evidence_report_configured:
        blockers.append("dependency_security_evidence_report_path_missing")
    elif not evidence_report_checked:
        blockers.append("dependency_security_evidence_report_unavailable")
    if evidence_report_checked and report_ready is not True:
        blockers.append("dependency_security_evidence_report_not_ready")
    if evidence_report_checked and report_safe_to_review is not True:
        blockers.append("dependency_security_evidence_report_not_safe_to_review")
    if blocked_requirement_ids:
        blockers.append("dependency_security_evidence_report_has_blocked_requirements")

    safe_context = {
        "evidence_report_path_included": False,
        "raw_evidence_report_included": False,
        "raw_scanner_output_included": False,
        "raw_vulnerability_details_included": False,
        "raw_registry_url_included": False,
        "approval_reference_value_included": False,
        "raw_phi_included": False,
        "raw_secret_included": False,
    }
    report = {
        "app_env": app_env,
        "app_env_is_production": app_env_is_production,
        "evidence_report_configured": evidence_report_configured,
        "evidence_report_checked": evidence_report_checked,
        "evidence_report_ready": report_ready,
        "evidence_report_safe_to_review": report_safe_to_review,
        "evidence_report_blocked_requirement_ids": blocked_requirement_ids,
        "blockers": blockers,
        "startup_ready": not blockers,
        "fail_fast_required": app_env_is_production and bool(blockers),
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
            "dependency_security_startup_config_validation_failed",
            extra={"dependency_security_startup_config": log_payload},
        )
    else:
        logger.info(
            "dependency_security_startup_config_validation_passed",
            extra={"dependency_security_startup_config": log_payload},
        )
    if report["fail_fast_required"]:
        raise RuntimeError(
            "Dependency security startup configuration is not production-ready."
        )
    return report
