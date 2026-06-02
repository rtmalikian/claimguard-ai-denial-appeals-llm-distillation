import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.auth import ADMIN_ROLES, require_roles
from app.core.config import settings
from app.db.database import get_db
from app.models import Claim, Patient, Provider

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
REPO_ROOT = Path(__file__).resolve().parents[4]
PHI_PLAN_READINESS_REPORT = (
    REPO_ROOT / "llm-distill" / "evals" / "reports" / "phi_plan_production_readiness_report.json"
)
SAFE_TOKEN_RE = re.compile(r"[^a-z0-9_]+")
SAFE_REQUIREMENT_NAMES = {
    "current_runtime_default_safe": "Current runtime default remains safe",
    "production_compose_startup_guard_env": "Production compose startup guard env",
    "file_ingestion_surface_audit_ready": "File-ingestion surface audit",
    "monitoring_gate_metrics_ready": "Prometheus PHIplan gate metrics",
    "monitoring_readiness_endpoint_ready": "PHIplan readiness endpoint",
    "manual_production_gate_packet_evidence": "Manual production gate packet",
    "student_default_cutover_external_approval": "Student default cutover approval",
    "user_data_model_improvement_external_approval": "User-data model improvement approval",
    "production_semantic_vector_backend": "Production semantic vector backend",
    "production_corpus_expansion_beyond_synthetic": "Production corpus beyond synthetic data",
    "production_prediction_fairness_monitoring": "Production prediction fairness monitoring",
    "synthetic_900_adapter_training_status": "Synthetic-900 adapter training status",
    "external_phi_service_guard": "External PHI service guard",
}


def _bool_metric(value: bool) -> int:
    return 1 if value else 0


def _configured_metric(value: str | None) -> int:
    return 1 if value and value.strip() else 0


def _metric_line(name: str, value: int | float) -> str:
    return f"{name} {value}"


def _help_block(name: str, description: str, metric_type: str = "gauge") -> list[str]:
    return [
        f"# HELP {name} {description}",
        f"# TYPE {name} {metric_type}",
    ]


def _safe_context() -> dict[str, bool]:
    return {
        "raw_report_paths_included": False,
        "raw_evidence_included": False,
        "raw_approval_or_reference_values_included": False,
        "raw_phi_included": False,
        "raw_document_text_included": False,
        "raw_secret_included": False,
    }


def _safe_status(value: Any) -> str:
    status = str(value or "unknown").strip().lower()
    return status if status in {"ready", "blocked", "warning", "unknown"} else "unknown"


def _safe_identifier(value: Any) -> str:
    raw_value = str(value or "unknown_requirement").strip().lower()
    safe_value = SAFE_TOKEN_RE.sub("_", raw_value).strip("_")
    return safe_value[:120] if safe_value else "unknown_requirement"


def _safe_message_token(value: Any) -> str:
    raw_value = str(value or "").strip().lower()
    if raw_value.startswith("missing file:"):
        return "missing_file"
    if raw_value.startswith("invalid json:"):
        return "invalid_json"
    if "/" in raw_value or "\\" in raw_value or "@" in raw_value:
        return "redacted_value"
    safe_value = SAFE_TOKEN_RE.sub("_", raw_value).strip("_")
    return safe_value[:160] if safe_value else "unspecified"


def _safe_message_tokens(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_safe_message_token(value) for value in values]


def _safe_requirement_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "requirement_id": "unknown_requirement",
            "name": "",
            "status": "unknown",
            "blockers": [],
            "warnings": [],
        }
    requirement_id = _safe_identifier(item.get("requirement_id"))
    return {
        "requirement_id": requirement_id,
        "name": SAFE_REQUIREMENT_NAMES.get(requirement_id, ""),
        "status": _safe_status(item.get("status")),
        "blockers": _safe_message_tokens(item.get("blockers")),
        "warnings": _safe_message_tokens(item.get("warnings")),
    }


def _requirement_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return sorted(
        {
            _safe_identifier(item.get("requirement_id"))
            for item in items
            if isinstance(item, dict) and item.get("requirement_id")
        }
    )


def _safe_phi_plan_readiness_payload(
    report_path: Path | None = None,
) -> dict[str, Any]:
    report_path = report_path or PHI_PLAN_READINESS_REPORT
    base_payload: dict[str, Any] = {
        "report_available": False,
        "status": "unavailable",
        "safe_current_state": False,
        "production_ready": False,
        "blocked_item_count": 0,
        "warning_item_count": 0,
        "blocked_requirement_ids": [],
        "warning_requirement_ids": [],
        "ready_requirement_ids": [],
        "blocked_items": [],
        "warning_items": [],
        "safe_context": _safe_context(),
    }
    if not report_path.exists():
        return base_payload
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {**base_payload, "status": "invalid_json"}
    if not isinstance(report, dict):
        return {**base_payload, "status": "invalid_report"}

    requirements = report.get("requirements")
    requirement_items = requirements if isinstance(requirements, list) else []
    blocked_items = [
        _safe_requirement_summary(item)
        for item in report.get("blocked_items", [])
        if isinstance(item, dict)
    ]
    warning_items = [
        _safe_requirement_summary(item)
        for item in report.get("warning_items", [])
        if isinstance(item, dict)
    ]
    ready_requirement_ids = sorted(
        {
            _safe_identifier(item.get("requirement_id"))
            for item in requirement_items
            if isinstance(item, dict) and item.get("status") == "ready"
        }
    )
    production_ready = bool(report.get("production_ready"))
    return {
        **base_payload,
        "report_available": True,
        "status": "ready" if production_ready else "blocked",
        "safe_current_state": bool(report.get("safe_current_state")),
        "production_ready": production_ready,
        "blocked_item_count": len(blocked_items),
        "warning_item_count": len(warning_items),
        "blocked_requirement_ids": _requirement_ids(report.get("blocked_items")),
        "warning_requirement_ids": _requirement_ids(report.get("warning_items")),
        "ready_requirement_ids": ready_requirement_ids,
        "blocked_items": blocked_items,
        "warning_items": warning_items,
    }


def build_prometheus_metrics(db: Session) -> str:
    total_claims = db.query(func.count(Claim.id)).scalar() or 0
    pending_claims = (
        db.query(func.count(Claim.id)).filter(Claim.status == "pending").scalar() or 0
    )
    submitted_claims = (
        db.query(func.count(Claim.id)).filter(Claim.status == "submitted").scalar() or 0
    )
    predicted_denials = (
        db.query(func.count(Claim.id))
        .filter(Claim.denial_prediction.isnot(None), Claim.denial_prediction > 0.5)
        .scalar()
        or 0
    )
    average_prediction = db.query(func.avg(Claim.denial_prediction)).scalar()
    patient_records = db.query(func.count(Patient.id)).scalar() or 0
    provider_records = db.query(func.count(Provider.id)).scalar() or 0

    metrics: list[str] = []
    metric_values: list[tuple[str, str, int | float]] = [
        (
            "claimguard_claims_total",
            "Total claim records visible to the application database.",
            total_claims,
        ),
        (
            "claimguard_claims_pending_total",
            "Total claim records currently marked pending.",
            pending_claims,
        ),
        (
            "claimguard_claims_submitted_total",
            "Total claim records currently marked submitted.",
            submitted_claims,
        ),
        (
            "claimguard_predicted_denials_total",
            "Total claim records with denial prediction above the current review threshold.",
            predicted_denials,
        ),
        (
            "claimguard_denial_prediction_average_score",
            "Average denial prediction score across scored claim records.",
            round(float(average_prediction or 0.0), 6),
        ),
        (
            "claimguard_patient_records_total",
            "Total patient records counted without exposing patient identifiers.",
            patient_records,
        ),
        (
            "claimguard_provider_records_total",
            "Total provider records counted without exposing provider identifiers.",
            provider_records,
        ),
        (
            "claimguard_student_default_enabled",
            "Whether the local student model is configured as the default.",
            _bool_metric(settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT),
        ),
        (
            "claimguard_student_auto_launch_requested",
            "Whether supervised student runtime auto-launch has been requested.",
            _bool_metric(settings.CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH),
        ),
        (
            "claimguard_student_cutover_approved",
            "Whether student default cutover approval has been attested.",
            _bool_metric(settings.CLAIMGUARD_STUDENT_DEFAULT_CUTOVER_APPROVED),
        ),
        (
            "claimguard_student_approval_reference_configured",
            "Whether a non-secret student cutover approval reference is configured.",
            _configured_metric(settings.CLAIMGUARD_STUDENT_DEFAULT_APPROVAL_REFERENCE),
        ),
        (
            "claimguard_student_runtime_supervised",
            "Whether supervised student runtime operation has been attested.",
            _bool_metric(settings.CLAIMGUARD_STUDENT_RUNTIME_SUPERVISED),
        ),
        (
            "claimguard_student_rollback_to_nvidia_enabled",
            "Whether rollback-to-NVIDIA is enabled for the denial workflow.",
            _bool_metric(settings.CLAIMGUARD_STUDENT_ROLLBACK_TO_NVIDIA),
        ),
        (
            "claimguard_model_improvement_enabled",
            "Whether user-data model improvement is enabled.",
            _bool_metric(settings.USER_DATA_MODEL_IMPROVEMENT_ENABLED),
        ),
        (
            "claimguard_model_improvement_legal_approved",
            "Whether user-data model improvement legal approval has been attested.",
            _bool_metric(settings.USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED),
        ),
        (
            "claimguard_model_improvement_baa_confirmed",
            "Whether user-data model improvement BAA coverage has been attested.",
            _bool_metric(settings.USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED),
        ),
        (
            "claimguard_model_improvement_consent_notice_configured",
            "Whether a user-data model improvement consent notice version is configured.",
            _configured_metric(settings.USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION),
        ),
        (
            "claimguard_model_improvement_approval_reference_configured",
            "Whether a non-secret user-data model improvement approval reference is configured.",
            _configured_metric(settings.USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE),
        ),
        (
            "claimguard_model_improvement_evidence_report_configured",
            "Whether user-data model improvement evidence report configuration is present.",
            _configured_metric(settings.USER_DATA_MODEL_IMPROVEMENT_EVIDENCE_REPORT),
        ),
        (
            "claimguard_prediction_fairness_evidence_report_configured",
            "Whether prediction fairness evidence report configuration is present.",
            _configured_metric(settings.PREDICTION_FAIRNESS_EVIDENCE_REPORT),
        ),
        (
            "claimguard_manual_gate_packet_report_configured",
            "Whether manual production gate packet report configuration is present.",
            _configured_metric(settings.PHI_PLAN_MANUAL_GATE_PACKET_REPORT),
        ),
        (
            "claimguard_production_corpus_evidence_report_configured",
            "Whether production corpus evidence report configuration is present.",
            _configured_metric(settings.PRODUCTION_CORPUS_EVIDENCE_REPORT),
        ),
        (
            "claimguard_backup_disaster_recovery_evidence_report_configured",
            "Whether backup and disaster-recovery evidence report configuration is present.",
            _configured_metric(settings.BACKUP_DISASTER_RECOVERY_EVIDENCE_REPORT),
        ),
        (
            "claimguard_dependency_security_evidence_report_configured",
            "Whether dependency security evidence report configuration is present.",
            _configured_metric(settings.DEPENDENCY_SECURITY_EVIDENCE_REPORT),
        ),
        (
            "claimguard_clearinghouse_submission_evidence_report_configured",
            "Whether clearinghouse submission evidence report configuration is present.",
            _configured_metric(settings.CLAIMGUARD_CLEARINGHOUSE_SUBMISSION_EVIDENCE_REPORT),
        ),
        (
            "claimguard_retrieval_semantic_backend_configured",
            "Whether semantic retrieval backend configuration has been attested.",
            _bool_metric(settings.RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED),
        ),
        (
            "claimguard_retrieval_embedding_model_approved",
            "Whether the configured retrieval embedding model is approved for production use.",
            _bool_metric(settings.RETRIEVAL_EMBEDDING_MODEL_APPROVED),
        ),
        (
            "claimguard_retrieval_hash_fallback_disabled_for_production",
            "Whether hash retrieval fallback is disabled for production use.",
            _bool_metric(settings.RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION),
        ),
        (
            "claimguard_retrieval_hash_embedding_backend_active",
            "Whether the current retrieval embedding backend is the local hash fallback.",
            _bool_metric(
                str(settings.RETRIEVAL_EMBEDDING_BACKEND or "").strip().lower()
                == "hash"
            ),
        ),
        (
            "claimguard_conservative_runtime_defaults",
            "Whether student default, student auto-launch, and user-data model improvement remain disabled.",
            _bool_metric(
                not settings.CLAIMGUARD_STUDENT_USE_BY_DEFAULT
                and not settings.CLAIMGUARD_STUDENT_ENABLE_AUTO_LAUNCH
                and not settings.USER_DATA_MODEL_IMPROVEMENT_ENABLED
            ),
        ),
    ]

    for name, description, value in metric_values:
        metrics.extend(_help_block(name, description))
        metrics.append(_metric_line(name, value))

    metrics.extend(
        _help_block(
            "claimguard_prometheus_no_phi_context",
            "Always 1 when this endpoint returns counts and flags without raw PHI or document content.",
        )
    )
    metrics.append(_metric_line("claimguard_prometheus_no_phi_context", 1))
    return "\n".join(metrics) + "\n"


@router.get("/metrics")
async def prometheus_metrics(
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    _ = current_user
    return Response(
        content=build_prometheus_metrics(db),
        media_type=PROMETHEUS_CONTENT_TYPE,
    )


@router.get("/phi-plan-readiness")
async def phi_plan_readiness(
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
):
    _ = current_user
    return _safe_phi_plan_readiness_payload()
