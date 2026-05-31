import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)

PRODUCTION_ENVS = {"prod", "production"}


def _str_value(settings_like, name: str, default: str = "") -> str:
    value = getattr(settings_like, name, default)
    if value is None:
        return default
    return str(value).strip()


def _bool_value(settings_like, name: str) -> bool:
    return getattr(settings_like, name, False) is True


def _status_bool(student_status: Any | None, name: str) -> bool | None:
    if student_status is None:
        return None
    value = getattr(student_status, name, None)
    return value if isinstance(value, bool) else None


def validate_student_default_startup_config(
    *,
    settings_like=None,
    student_status: Any | None = None,
) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    app_env = _str_value(runtime_settings, "APP_ENV", "development").lower()
    app_env_is_production = app_env in PRODUCTION_ENVS
    student_default_requested = _bool_value(
        runtime_settings,
        "CLAIMGUARD_STUDENT_USE_BY_DEFAULT",
    )
    auto_launch_requested = _bool_value(
        runtime_settings,
        "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH",
    )
    student_runtime_requested = student_default_requested or auto_launch_requested
    cutover_approved = _bool_value(
        runtime_settings,
        "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
    )
    approval_reference_configured = bool(
        _str_value(runtime_settings, "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE")
    )
    runtime_supervised = _bool_value(
        runtime_settings,
        "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED",
    )
    rollback_to_nvidia = _bool_value(
        runtime_settings,
        "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA",
    )
    accepted_for_denial_workflow = _status_bool(
        student_status,
        "accepted_for_denial_workflow",
    )
    runtime_checked = _status_bool(student_status, "runtime_checked")
    runtime_available = _status_bool(student_status, "runtime_available")
    default_cutover_ready = _status_bool(student_status, "default_cutover_ready")
    effective_use_by_default = _status_bool(student_status, "effective_use_by_default")

    blockers: list[str] = []
    if student_runtime_requested:
        if student_default_requested and student_status is None:
            blockers.append("student_default_status_not_checked")
        if auto_launch_requested and student_status is None:
            blockers.append("student_auto_launch_status_not_checked")
        if accepted_for_denial_workflow is not True:
            blockers.append("student_readiness_evidence_not_release_ready")
        if not cutover_approved:
            blockers.append("student_cutover_approval_missing")
        if not approval_reference_configured:
            blockers.append("student_cutover_approval_reference_missing")
        if not runtime_supervised:
            blockers.append("student_runtime_supervision_missing")
        if runtime_checked is not True:
            blockers.append("student_runtime_health_not_checked")
        elif runtime_available is not True:
            blockers.append("student_runtime_health_not_ok")
        if rollback_to_nvidia:
            blockers.append("rollback_to_nvidia_flag_enabled")
    if student_default_requested:
        if default_cutover_ready is not True or effective_use_by_default is not True:
            blockers.append("student_default_cutover_status_not_ready")

    safe_context = {
        "approval_reference_value_included": False,
        "raw_runtime_response_included": False,
        "raw_prompt_included": False,
        "raw_document_text_included": False,
        "raw_phi_included": False,
        "raw_secret_included": False,
    }
    report = {
        "app_env": app_env,
        "app_env_is_production": app_env_is_production,
        "student_default_requested": student_default_requested,
        "student_auto_launch_requested": auto_launch_requested,
        "cutover_approved": cutover_approved,
        "approval_reference_configured": approval_reference_configured,
        "runtime_supervised": runtime_supervised,
        "rollback_to_nvidia": rollback_to_nvidia,
        "student_status_checked": student_status is not None,
        "accepted_for_denial_workflow": accepted_for_denial_workflow,
        "runtime_checked": runtime_checked,
        "runtime_available": runtime_available,
        "default_cutover_ready": default_cutover_ready,
        "effective_use_by_default": effective_use_by_default,
        "blockers": blockers,
        "startup_ready": not blockers,
        "fail_fast_required": app_env_is_production
        and student_runtime_requested
        and bool(blockers),
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
            "student_default_startup_config_validation_failed",
            extra={"student_default_startup_config": log_payload},
        )
    else:
        logger.info(
            "student_default_startup_config_validation_passed",
            extra={"student_default_startup_config": log_payload},
        )
    if report["fail_fast_required"]:
        raise RuntimeError(
            "ClaimGuard student default startup configuration is not production-ready."
        )
    return report
