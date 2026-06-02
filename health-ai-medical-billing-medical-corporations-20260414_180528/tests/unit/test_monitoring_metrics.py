import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import monitoring
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
from app.models import Claim


def _admin_headers() -> dict[str, str]:
    token = create_access_token({"sub": "1", "email": "admin.example.test", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_prometheus_metrics_requires_authentication():
    client = TestClient(app)
    response = client.get("/api/v1/monitoring/metrics")

    assert response.status_code == 401
    assert response.json()["error_code"] == "authentication_required"


def test_phi_plan_readiness_requires_authentication():
    client = TestClient(app)
    response = client.get("/api/v1/monitoring/phi-plan-readiness")

    assert response.status_code == 401
    assert response.json()["error_code"] == "authentication_required"


def test_prometheus_metrics_returns_safe_counts(db_session):
    claim = Claim(
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        status="pending",
        denial_prediction=0.72,
    )
    db_session.add(claim)
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    try:
        response = client.get("/api/v1/monitoring/metrics", headers=_admin_headers())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "claimguard_claims_total 1" in body
    assert "claimguard_claims_pending_total 1" in body
    assert "claimguard_predicted_denials_total 1" in body
    assert "claimguard_prometheus_no_phi_context 1" in body
    assert "Synthetic" not in body


def test_prometheus_metrics_exposes_boolean_gate_flags_without_raw_values(
    db_session,
    monkeypatch,
):
    raw_student_reference = "synthetic-student-approval-reference-should-not-emit"
    raw_model_improvement_reference = (
        "synthetic-model-improvement-reference-should-not-emit"
    )
    raw_consent_notice = "synthetic-consent-notice-version-should-not-emit"
    raw_model_improvement_report_path = (
        "/private/tmp/synthetic-model-improvement-report-should-not-emit.json"
    )
    raw_fairness_report_path = "/private/tmp/synthetic-fairness-report-should-not-emit.json"
    raw_manual_gate_report_path = (
        "/private/tmp/synthetic-manual-gate-report-should-not-emit.json"
    )
    raw_production_corpus_report_path = (
        "/private/tmp/synthetic-production-corpus-report-should-not-emit.json"
    )
    raw_backup_dr_report_path = (
        "/private/tmp/synthetic-backup-dr-report-should-not-emit.json"
    )
    raw_dependency_security_report_path = (
        "/private/tmp/synthetic-dependency-security-report-should-not-emit.json"
    )
    raw_clearinghouse_report_path = (
        "/private/tmp/synthetic-clearinghouse-report-should-not-emit.json"
    )

    monkeypatch.setattr(monitoring.settings, "CLAIMGUARD_STUDENT_USE_BY_DEFAULT", True)
    monkeypatch.setattr(monitoring.settings, "CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH", True)
    monkeypatch.setattr(
        monitoring.settings,
        "CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED",
        True,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE",
        raw_student_reference,
    )
    monkeypatch.setattr(monitoring.settings, "CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED", True)
    monkeypatch.setattr(monitoring.settings, "CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA", True)
    monkeypatch.setattr(monitoring.settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED", True)
    monkeypatch.setattr(
        monitoring.settings,
        "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED",
        True,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED",
        True,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION",
        raw_consent_notice,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE",
        raw_model_improvement_reference,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT",
        raw_model_improvement_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "PREDICTION_FAIRNESS_EVIDENCE_REPORT",
        raw_fairness_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "PHI_PLAN_MANUAL_GATE_PACKET_REPORT",
        raw_manual_gate_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "PRODUCTION_CORPUS_EVIDENCE_REPORT",
        raw_production_corpus_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT",
        raw_backup_dr_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "DEPENDENCY_SECURITY_EVIDENCE_REPORT",
        raw_dependency_security_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT",
        raw_clearinghouse_report_path,
    )
    monkeypatch.setattr(
        monitoring.settings,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
        True,
    )
    monkeypatch.setattr(monitoring.settings, "RETRIEVAL_EMBEDDING_MODEL_APPROVED", True)
    monkeypatch.setattr(
        monitoring.settings,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
        True,
    )
    monkeypatch.setattr(monitoring.settings, "RETRIEVAL_EMBEDDING_BACKEND", "semantic")

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    try:
        response = client.get("/api/v1/monitoring/metrics", headers=_admin_headers())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    assert "claimguard_student_default_enabled 1" in body
    assert "claimguard_student_auto_launch_requested 1" in body
    assert "claimguard_student_cutover_approved 1" in body
    assert "claimguard_student_approval_reference_configured 1" in body
    assert "claimguard_student_runtime_supervised 1" in body
    assert "claimguard_student_rollback_to_nvidia_enabled 1" in body
    assert "claimguard_model_improvement_enabled 1" in body
    assert "claimguard_model_improvement_legal_approved 1" in body
    assert "claimguard_model_improvement_baa_confirmed 1" in body
    assert "claimguard_model_improvement_consent_notice_configured 1" in body
    assert "claimguard_model_improvement_approval_reference_configured 1" in body
    assert "claimguard_model_improvement_evidence_report_configured 1" in body
    assert "claimguard_prediction_fairness_evidence_report_configured 1" in body
    assert "claimguard_manual_gate_packet_report_configured 1" in body
    assert "claimguard_production_corpus_evidence_report_configured 1" in body
    assert "claimguard_backup_disaster_recovery_evidence_report_configured 1" in body
    assert "claimguard_dependency_security_evidence_report_configured 1" in body
    assert "claimguard_clearinghouse_submission_evidence_report_configured 1" in body
    assert "claimguard_retrieval_semantic_backend_configured 1" in body
    assert "claimguard_retrieval_embedding_model_approved 1" in body
    assert "claimguard_retrieval_hash_fallback_disabled_for_production 1" in body
    assert "claimguard_retrieval_hash_embedding_backend_active 0" in body
    assert "claimguard_conservative_runtime_defaults 0" in body
    assert raw_student_reference not in body
    assert raw_model_improvement_reference not in body
    assert raw_consent_notice not in body
    assert raw_model_improvement_report_path not in body
    assert raw_fairness_report_path not in body
    assert raw_manual_gate_report_path not in body
    assert raw_production_corpus_report_path not in body
    assert raw_backup_dr_report_path not in body
    assert raw_dependency_security_report_path not in body
    assert raw_clearinghouse_report_path not in body


def test_phi_plan_readiness_returns_sanitized_report(monkeypatch, tmp_path):
    raw_report_path = "/private/tmp/synthetic-phi-plan-readiness-report-should-not-emit.json"
    raw_approval_reference = "synthetic-approval-reference-should-not-emit"
    report_path = tmp_path / "phi_plan_production_readiness_report.json"
    report_path.write_text(
        json.dumps(
            {
                "safe_current_state": True,
                "production_ready": False,
                "blocked_items": [
                    {
                        "requirement_id": "manual_production_gate_packet_evidence",
                        "name": "Manual gate packet",
                        "status": "blocked",
                        "blockers": [f"missing file: {raw_report_path}"],
                        "warnings": [],
                        "evidence": {
                            "packet_report_path": raw_report_path,
                            "approval_reference": raw_approval_reference,
                        },
                    }
                ],
                "warning_items": [
                    {
                        "requirement_id": "synthetic_900_adapter_training_status",
                        "name": "Synthetic adapter training",
                        "status": "warning",
                        "blockers": [],
                        "warnings": ["Synthetic adapter needs local Metal run"],
                        "evidence": {"run_report_path": raw_report_path},
                    }
                ],
                "requirements": [
                    {
                        "requirement_id": "current_runtime_default_safe",
                        "name": "Current runtime default",
                        "status": "ready",
                    }
                ],
                "next_required_actions": [
                    f"Review {raw_report_path} with reference {raw_approval_reference}."
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitoring, "PHI_PLAN_READINESS_REPORT", report_path)

    client = TestClient(app)
    response = client.get(
        "/api/v1/monitoring/phi-plan-readiness",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["report_available"] is True
    assert payload["status"] == "blocked"
    assert payload["safe_current_state"] is True
    assert payload["production_ready"] is False
    assert payload["blocked_requirement_ids"] == [
        "manual_production_gate_packet_evidence"
    ]
    assert payload["warning_requirement_ids"] == [
        "synthetic_900_adapter_training_status"
    ]
    assert payload["ready_requirement_ids"] == ["current_runtime_default_safe"]
    assert payload["blocked_items"][0]["blockers"] == ["missing_file"]
    assert payload["safe_context"]["raw_report_paths_included"] is False
    assert payload["safe_context"]["raw_evidence_included"] is False
    assert payload["safe_context"]["raw_approval_or_reference_values_included"] is False
    assert raw_report_path not in serialized
    assert raw_approval_reference not in serialized
    assert "next_required_actions" not in payload


def test_phi_plan_readiness_missing_report_is_safe(monkeypatch, tmp_path):
    missing_report = tmp_path / "missing-readiness-report.json"
    monkeypatch.setattr(monitoring, "PHI_PLAN_READINESS_REPORT", missing_report)

    client = TestClient(app)
    response = client.get(
        "/api/v1/monitoring/phi-plan-readiness",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["report_available"] is False
    assert payload["status"] == "unavailable"
    assert payload["blocked_requirement_ids"] == []
    assert str(missing_report) not in serialized
