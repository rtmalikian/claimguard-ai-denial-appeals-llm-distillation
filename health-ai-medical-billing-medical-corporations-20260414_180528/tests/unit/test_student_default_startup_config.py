import json
import logging
from types import SimpleNamespace

import pytest

from app.utils.student_default_config import validate_student_default_startup_config


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "CLAIMGUARD_STUDENT_USE_BY_DEFAULT": False,
        "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED": False,
        "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE": "",
        "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED": False,
        "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA": False,
        "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _status(**overrides):
    values = {
        "accepted_for_denial_workflow": True,
        "runtime_checked": True,
        "runtime_available": True,
        "default_cutover_ready": True,
        "effective_use_by_default": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_student_default_off_is_startup_ready_without_status_check(caplog):
    with caplog.at_level(logging.INFO, logger="app.utils.student_default_config"):
        report = validate_student_default_startup_config(settings_like=_settings())

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["student_default_requested"] is False
    assert report["student_auto_launch_requested"] is False
    assert report["student_status_checked"] is False
    assert report["blockers"] == []
    assert report["safe_context"]["approval_reference_value_included"] is False
    assert caplog.records[-1].student_default_startup_config["startup_ready"] is True


def test_student_default_requested_in_development_reports_blockers_without_fail_fast(caplog):
    with caplog.at_level(logging.WARNING, logger="app.utils.student_default_config"):
        report = validate_student_default_startup_config(
            settings_like=_settings(CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True),
            student_status=_status(
                accepted_for_denial_workflow=False,
                runtime_checked=False,
                runtime_available=False,
                default_cutover_ready=False,
                effective_use_by_default=False,
            ),
        )

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "student_readiness_evidence_not_release_ready" in report["blockers"]
    assert "student_cutover_approval_missing" in report["blockers"]
    assert "student_cutover_approval_reference_missing" in report["blockers"]
    assert "student_runtime_supervision_missing" in report["blockers"]
    assert "student_runtime_health_not_checked" in report["blockers"]
    assert "student_default_cutover_status_not_ready" in report["blockers"]
    log_payload = caplog.records[-1].student_default_startup_config
    assert log_payload["safe_context"]["raw_phi_included"] is False


def test_student_auto_launch_requested_in_development_reports_blockers_without_fail_fast():
    report = validate_student_default_startup_config(
        settings_like=_settings(CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=True),
        student_status=_status(
            accepted_for_denial_workflow=False,
            runtime_checked=False,
            runtime_available=False,
        ),
    )

    assert report["student_default_requested"] is False
    assert report["student_auto_launch_requested"] is True
    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "student_readiness_evidence_not_release_ready" in report["blockers"]
    assert "student_cutover_approval_missing" in report["blockers"]
    assert "student_cutover_approval_reference_missing" in report["blockers"]
    assert "student_runtime_supervision_missing" in report["blockers"]
    assert "student_runtime_health_not_checked" in report["blockers"]
    assert "student_default_cutover_status_not_ready" not in report["blockers"]


def test_student_default_requested_in_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_student_default_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            ),
            student_status=_status(default_cutover_ready=False, effective_use_by_default=False),
        )

    assert str(exc_info.value) == (
        "ClaimGuard student default startup configuration is not production-ready."
    )


def test_student_auto_launch_requested_in_production_fails_fast_when_unready():
    with pytest.raises(RuntimeError) as exc_info:
        validate_student_default_startup_config(
            settings_like=_settings(
                APP_ENV="production",
                CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=True,
            ),
            student_status=_status(runtime_checked=False),
        )

    assert str(exc_info.value) == (
        "ClaimGuard student default startup configuration is not production-ready."
    )


def test_student_default_requested_in_production_passes_when_all_gates_are_ready():
    report = validate_student_default_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="synthetic-reference",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
        ),
        student_status=_status(),
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["approval_reference_configured"] is True
    assert report["blockers"] == []


def test_student_auto_launch_requested_in_production_passes_when_runtime_gates_are_ready():
    report = validate_student_default_startup_config(
        settings_like=_settings(
            APP_ENV="production",
            CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="synthetic-reference",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
        ),
        student_status=_status(default_cutover_ready=False, effective_use_by_default=False),
    )

    assert report["student_default_requested"] is False
    assert report["student_auto_launch_requested"] is True
    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["blockers"] == []


def test_student_default_startup_report_does_not_emit_approval_reference_value():
    raw_reference = "synthetic-reference-value-should-not-be-written"
    report = validate_student_default_startup_config(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE=raw_reference,
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
        ),
        student_status=_status(),
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["approval_reference_configured"] is True
    assert raw_reference not in serialized


def test_rollback_flag_blocks_requested_student_default_cutover():
    report = validate_student_default_startup_config(
        settings_like=_settings(
            CLAIMGUARD_STUDENT_USE_BY_DEFAULT=True,
            CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED=True,
            CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE="synthetic-reference",
            CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED=True,
            CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA=True,
        ),
        student_status=_status(default_cutover_ready=False, effective_use_by_default=False),
    )

    assert report["startup_ready"] is False
    assert "rollback_to_nvidia_flag_enabled" in report["blockers"]
    assert "student_default_cutover_status_not_ready" in report["blockers"]
