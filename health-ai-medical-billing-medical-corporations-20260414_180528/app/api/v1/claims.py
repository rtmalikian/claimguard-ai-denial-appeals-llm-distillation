import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.limiter import limiter
from app.core.auth import (
    ADMIN_ROLES,
    READ_ROLES,
    ROLE_ADMIN,
    ROLE_BILLING_STAFF,
    ROLE_VIEWER,
    WRITE_ROLES,
    get_client_ip,
    require_roles,
)

from app.db.database import get_db
from app.schemas.claim import (
    ClaimPredictionRequest,
    ClaimPredictionResponse,
    ClaimSubmitRequest,
    ClaimSubmitResponse,
    ClaimStatusUpdateRequest,
    ClaimStatusUpdateResponse,
    ClaimResponse,
    ClaimDocumentAuditDashboardResponse,
    ClaimDocumentAuditEvent,
    ClaimDocumentDeleteRequest,
    ClaimDocumentDeleteResponse,
    ClaimDocumentGovernance,
    ClaimDocumentGovernanceSummary,
    ClaimDocumentResponse,
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    BatchDocumentAnalysisRequest,
    BatchDocumentAnalysisResponse,
    BatchClaimUploadResult,
    BatchClaimUploadServiceLine,
    BatchClaimUploadValidationIssue,
    BatchClaimsUploadResponse,
)
from app.schemas.corpus import (
    CorpusDocumentSurfaceInspectRequest,
    CorpusDocumentSurfaceInspectResponse,
)
from app.schemas.denial_workflow import DenialWorkflowAnalysisRequest
from app.services.corpus import CorpusSafetyService
from app.services.prediction import PredictionService
from app.services.document_analysis import DocumentAnalysisService
from app.services.denial_workflow import DenialWorkflowService
from app.services.claim_state import (
    CANONICAL_CLAIM_STATUSES,
    LEGACY_READABLE_CLAIM_STATUSES,
    allowed_next_claim_statuses,
    is_readable_claim_status,
    normalize_claim_status,
    validate_claim_status_transition,
)
from app.services.ocr import OcrService, OcrServiceError
from app.models import AuditLog, Claim, Patient, Provider
from app.utils.audit import log_audit
from app.utils.edi_parser import (
    EDI837Claim,
    EDIParserError,
    estimate_edi_837_batch_size,
    parse_edi_837,
)
from app.utils.healthcare_codes import validate_claim_billing_codes
from datetime import datetime, date

router = APIRouter(prefix="/claims", tags=["claims"])
logger = logging.getLogger(__name__)

CLAIM_DOCUMENT_ACCESS_SCOPE_OWNER = "owner"
CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM = "billing_team"
CLAIM_DOCUMENT_ACCESS_SCOPE_ADMIN_ONLY = "admin_only"
CLAIM_SOFT_DELETE_REASON = "operator_requested_retention_or_privacy_review"
CLAIM_DOCUMENT_AUDIT_ACTIONS = {
    "document_analyzed",
    "document_uploaded",
    "claim_document_viewed",
    "claim_document_retired",
    "claim_document_governance_viewed",
    "claim_document_audit_dashboard_viewed",
}
SAFE_CLAIM_DOCUMENT_AUDIT_DETAIL_KEYS = {
    "claim_id",
    "document_type",
    "text_length",
    "source_filename_present",
    "source_file_extension",
    "source_mime_type",
    "original_size",
    "processed_size",
    "was_resized",
    "was_converted",
    "ocr_engine",
    "ocr_model",
    "ocr_pages",
    "access_scope",
    "retention_until",
    "deleted_at",
    "deleted_by_user_id",
    "deletion_reason",
    "document_available",
    "document_retired",
    "document_retention_expired",
    "surface_count",
    "surface_blocking_count",
    "surface_residual_risk_score",
    "surface_deidentification_status",
    "active_count",
    "deleted_count",
    "expired_active_count",
    "retained_without_expiration_count",
    "skip",
    "limit",
    "result_count",
}
EDI_BATCH_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
EDI_BATCH_UPLOAD_EXTENSIONS = {".edi", ".txt"}
EDI_BATCH_UPLOAD_MAX_CLAIMS = 250
EDI_BATCH_UPLOAD_MAX_SEGMENTS = 5000
CLAIM_DOCUMENT_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
CLAIM_DOCUMENT_UPLOAD_EXTENSIONS = (
    ".pdf",
    ".txt",
    ".text",
    ".denial",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
)
DISALLOWED_INNER_UPLOAD_EXTENSIONS = {
    ".asp",
    ".aspx",
    ".bash",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".htm",
    ".html",
    ".jar",
    ".js",
    ".jsp",
    ".jspx",
    ".mjs",
    ".php",
    ".phtml",
    ".pl",
    ".ps1",
    ".py",
    ".rb",
    ".scr",
    ".sh",
    ".svg",
    ".vbs",
    ".war",
    ".zsh",
}
DOCUMENT_ANALYSIS_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")
HUMAN_REVIEW_HIGH_RISK_THRESHOLD = 0.5
HUMAN_REVIEW_NEXT_ACTION_STANDARD = "continue_standard_claim_workflow"
HUMAN_REVIEW_NEXT_ACTION_REQUIRED = "route_to_billing_reviewer_before_next_payer_action"


def _claim_status_error_detail(
    *,
    error_code: str,
    message: str,
    current_status: str | None = None,
    requested_status: str | None = None,
    blocker_codes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "error_code": error_code,
        "message": message,
        "field": "status",
        "current_status": current_status,
        "requested_status": requested_status,
        "allowed_next_statuses": (
            list(allowed_next_claim_statuses(current_status))
            if current_status
            else []
        ),
        "allowed_statuses": list(CANONICAL_CLAIM_STATUSES),
        "readable_legacy_statuses": list(LEGACY_READABLE_CLAIM_STATUSES),
        "blocker_codes": blocker_codes or [],
        "safe_context": {
            "raw_claim_data_included": False,
            "raw_document_text_included": False,
            "raw_transition_reason_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
        },
    }


def _claim_code_error_detail(issues: list[object]) -> dict[str, object]:
    return {
        "error_code": "invalid_healthcare_codes",
        "message": "Claim contains invalid healthcare billing code formats.",
        "issue_count": len(issues),
        "issues": [issue.safe_detail() for issue in issues],
        "safe_context": {
            "raw_code_values_included": False,
            "raw_claim_data_included": False,
            "raw_document_text_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
        },
    }


@dataclass(frozen=True)
class RequiredClaimFieldIssue:
    field: str
    error_code: str
    accepted_metadata_keys: tuple[str, ...]
    parser_stage: str = "required_claim_field_validation"
    severity: str = "error"

    def safe_detail(self) -> dict[str, object]:
        return {
            "field": self.field,
            "error_code": self.error_code,
            "accepted_metadata_keys": list(self.accepted_metadata_keys),
            "parser_stage": self.parser_stage,
            "severity": self.severity,
            "safe_context": {
                "raw_claim_data_included": False,
                "raw_field_value_included": False,
                "raw_document_text_included": False,
                "patient_identifier_included": False,
                "provider_identifier_included": False,
            },
        }


PAYER_METADATA_KEYS = ("payer", "payer_name", "payer_identifier")
SUBSCRIBER_METADATA_KEYS = ("subscriber", "subscriber_id", "policy_number")
SERVICE_DATE_METADATA_KEYS = ("service_date", "date_of_service")
CLAIM_AMOUNT_METADATA_KEYS = (
    "amount",
    "claim_amount",
    "billed_amount",
    "charge_amount",
    "total_charge_amount",
)
CLAIM_SERVICE_LINE_COLLECTION_KEYS = ("service_lines", "line_items", "lines")
CLAIM_SERVICE_LINE_PROCEDURE_KEYS = (
    "procedure_code",
    "cpt_code",
    "hcpcs_code",
    "code",
)
DIAGNOSIS_POINTER_METADATA_KEYS = (
    "diagnosis_pointer",
    "diagnosis_pointers",
    "diagnosis_pointer_numbers",
)


@dataclass(frozen=True)
class ClaimDataValueIssue:
    field: str
    field_path: str
    error_code: str
    parser_stage: str = "claim_data_value_validation"
    severity: str = "error"

    def safe_detail(self) -> dict[str, object]:
        return {
            "field": self.field,
            "field_path": self.field_path,
            "error_code": self.error_code,
            "parser_stage": self.parser_stage,
            "severity": self.severity,
            "safe_context": {
                "raw_claim_data_included": False,
                "raw_field_value_included": False,
                "raw_document_text_included": False,
                "patient_identifier_included": False,
                "provider_identifier_included": False,
            },
        }


@dataclass(frozen=True)
class DiagnosisProcedureLinkageIssue:
    field: str
    field_path: str
    error_code: str
    parser_stage: str = "diagnosis_procedure_linkage_validation"
    severity: str = "error"

    def safe_detail(self) -> dict[str, object]:
        return {
            "field": self.field,
            "field_path": self.field_path,
            "error_code": self.error_code,
            "parser_stage": self.parser_stage,
            "severity": self.severity,
            "safe_context": {
                "raw_code_values_included": False,
                "raw_claim_data_included": False,
                "raw_field_value_included": False,
                "raw_document_text_included": False,
                "patient_identifier_included": False,
                "provider_identifier_included": False,
                "clinical_medical_necessity_asserted": False,
            },
        }


def _metadata_value_present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_metadata_value_present(item) for item in value.values())
    if isinstance(value, list):
        return any(_metadata_value_present(item) for item in value)
    return value is not None


def _first_present_metadata_value(claim_data: dict, keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in claim_data and _metadata_value_present(claim_data.get(key)):
            return claim_data.get(key)
    return None


def _is_valid_service_date_metadata(value: object) -> bool:
    if isinstance(value, (datetime, date)):
        return True
    if not isinstance(value, str):
        return False

    normalized = value.strip()
    if not normalized:
        return False
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            datetime.strptime(normalized[:10], date_format)
            return True
        except ValueError:
            continue
    return False


def validate_required_claim_submission_fields(
    claim_data: object,
) -> list[RequiredClaimFieldIssue]:
    data = claim_data if isinstance(claim_data, dict) else {}
    issues: list[RequiredClaimFieldIssue] = []

    if _first_present_metadata_value(data, PAYER_METADATA_KEYS) is None:
        issues.append(
            RequiredClaimFieldIssue(
                field="payer",
                error_code="missing_payer_metadata",
                accepted_metadata_keys=PAYER_METADATA_KEYS,
            )
        )

    if _first_present_metadata_value(data, SUBSCRIBER_METADATA_KEYS) is None:
        issues.append(
            RequiredClaimFieldIssue(
                field="subscriber",
                error_code="missing_subscriber_metadata",
                accepted_metadata_keys=SUBSCRIBER_METADATA_KEYS,
            )
        )

    service_date_value = _first_present_metadata_value(data, SERVICE_DATE_METADATA_KEYS)
    if service_date_value is None:
        issues.append(
            RequiredClaimFieldIssue(
                field="service_date",
                error_code="missing_service_date_metadata",
                accepted_metadata_keys=SERVICE_DATE_METADATA_KEYS,
            )
        )
    elif not _is_valid_service_date_metadata(service_date_value):
        issues.append(
            RequiredClaimFieldIssue(
                field="service_date",
                error_code="invalid_service_date_metadata",
                accepted_metadata_keys=SERVICE_DATE_METADATA_KEYS,
            )
        )

    return issues


def _claim_amount_to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace(",", "")
    if not normalized:
        return None

    parenthesized_negative = normalized.startswith("(") and normalized.endswith(")")
    if parenthesized_negative:
        normalized = normalized[1:-1].strip()
    if normalized.startswith("$"):
        normalized = normalized[1:].strip()

    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    return -amount if parenthesized_negative else amount


def _claim_amount_value_issues_for_mapping(
    data: dict,
    *,
    prefix: str | None = None,
) -> list[ClaimDataValueIssue]:
    issues: list[ClaimDataValueIssue] = []
    for key in CLAIM_AMOUNT_METADATA_KEYS:
        if key not in data:
            continue
        amount = _claim_amount_to_decimal(data.get(key))
        if amount is not None and amount < 0:
            issues.append(
                ClaimDataValueIssue(
                    field=key,
                    field_path=f"{prefix}.{key}" if prefix else key,
                    error_code="negative_claim_amount_metadata",
                )
            )

    for collection_key in CLAIM_SERVICE_LINE_COLLECTION_KEYS:
        collection = data.get(collection_key)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            if isinstance(item, dict):
                issues.extend(
                    _claim_amount_value_issues_for_mapping(
                        item,
                        prefix=(
                            f"{prefix}.{collection_key}[{index}]"
                            if prefix
                            else f"{collection_key}[{index}]"
                        ),
                    )
                )
    return issues


def validate_claim_data_values(claim_data: object) -> list[ClaimDataValueIssue]:
    data = claim_data if isinstance(claim_data, dict) else {}
    return _claim_amount_value_issues_for_mapping(data)


def _non_empty_sequence_count(values: object) -> int:
    if values is None:
        return 0
    if isinstance(values, str):
        return 1 if values.strip() else 0
    if isinstance(values, (list, tuple, set)):
        return sum(1 for value in values if _metadata_value_present(value))
    return 1 if _metadata_value_present(values) else 0


def _service_line_procedure_count(claim_data: dict) -> int:
    count = 0
    for collection_key in CLAIM_SERVICE_LINE_COLLECTION_KEYS:
        collection = claim_data.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            if any(
                _metadata_value_present(item.get(key))
                for key in CLAIM_SERVICE_LINE_PROCEDURE_KEYS
            ):
                count += 1
    return count


def _pointer_values(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in re.split(r"[,:;\s]+", value.strip()) if item]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _append_diagnosis_pointer_issues(
    *,
    issues: list[DiagnosisProcedureLinkageIssue],
    value: object,
    diagnosis_count: int,
    field: str,
    field_path: str,
) -> None:
    for pointer in _pointer_values(value):
        normalized = str(pointer or "").strip()
        if not normalized.isdigit():
            issues.append(
                DiagnosisProcedureLinkageIssue(
                    field=field,
                    field_path=field_path,
                    error_code="invalid_diagnosis_pointer_format",
                )
            )
            continue
        pointer_index = int(normalized)
        if pointer_index < 1 or pointer_index > diagnosis_count:
            issues.append(
                DiagnosisProcedureLinkageIssue(
                    field=field,
                    field_path=field_path,
                    error_code="diagnosis_pointer_out_of_range",
                )
            )


def validate_diagnosis_procedure_linkage(
    *,
    diagnosis_codes: object,
    procedure_codes: object,
    claim_data: object,
) -> list[DiagnosisProcedureLinkageIssue]:
    data = claim_data if isinstance(claim_data, dict) else {}
    diagnosis_count = _non_empty_sequence_count(diagnosis_codes)
    procedure_count = _non_empty_sequence_count(procedure_codes)
    procedure_count += _service_line_procedure_count(data)
    issues: list[DiagnosisProcedureLinkageIssue] = []

    if procedure_count and diagnosis_count == 0:
        issues.append(
            DiagnosisProcedureLinkageIssue(
                field="diagnosis_codes",
                field_path="diagnosis_codes",
                error_code="missing_diagnosis_codes_for_procedure_linkage",
            )
        )
        return issues

    if diagnosis_count == 0:
        return issues

    for key in DIAGNOSIS_POINTER_METADATA_KEYS:
        if key in data:
            _append_diagnosis_pointer_issues(
                issues=issues,
                value=data.get(key),
                diagnosis_count=diagnosis_count,
                field=key,
                field_path=key,
            )

    for collection_key in CLAIM_SERVICE_LINE_COLLECTION_KEYS:
        collection = data.get(collection_key)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue
            for key in DIAGNOSIS_POINTER_METADATA_KEYS:
                if key in item:
                    _append_diagnosis_pointer_issues(
                        issues=issues,
                        value=item.get(key),
                        diagnosis_count=diagnosis_count,
                        field=key,
                        field_path=f"{collection_key}[{index}].{key}",
                    )

    return issues


def _diagnosis_procedure_linkage_error_detail(
    issues: list[DiagnosisProcedureLinkageIssue],
) -> dict[str, object]:
    return {
        "error_code": "invalid_diagnosis_procedure_linkage",
        "message": (
            "Claim procedure metadata requires diagnosis support and valid "
            "diagnosis-pointer references."
        ),
        "issue_count": len(issues),
        "issues": [issue.safe_detail() for issue in issues],
        "safe_context": {
            "raw_code_values_included": False,
            "raw_claim_data_included": False,
            "raw_field_values_included": False,
            "raw_document_text_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
            "clinical_medical_necessity_asserted": False,
        },
    }


def _claim_data_value_error_detail(
    issues: list[ClaimDataValueIssue],
) -> dict[str, object]:
    return {
        "error_code": "invalid_claim_data_values",
        "message": "Claim contains invalid structured claim metadata values.",
        "issue_count": len(issues),
        "issues": [issue.safe_detail() for issue in issues],
        "safe_context": {
            "raw_claim_data_included": False,
            "raw_field_values_included": False,
            "raw_document_text_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
        },
    }


def _required_claim_fields_error_detail(
    issues: list[RequiredClaimFieldIssue],
) -> dict[str, object]:
    return {
        "error_code": "missing_required_claim_fields",
        "message": (
            "Claim submission requires payer, subscriber, and service date metadata."
        ),
        "issue_count": len(issues),
        "issues": [issue.safe_detail() for issue in issues],
        "safe_context": {
            "raw_claim_data_included": False,
            "raw_field_values_included": False,
            "raw_document_text_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
        },
    }


def _raise_for_missing_required_claim_fields(
    request: object, *, endpoint_name: str
) -> None:
    issues = validate_required_claim_submission_fields(
        _safe_attr(request, "claim_data", {})
    )
    if not issues:
        return

    logger.warning(
        "claim_required_field_validation_failed",
        extra={
            "claim_required_field_validation": {
                "endpoint": endpoint_name,
                "issue_count": len(issues),
                "issue_types": sorted({issue.error_code for issue in issues}),
                "claim_data_key_count": len(_safe_attr(request, "claim_data", {}) or {}),
                "safe_context": {
                    "raw_claim_data_included": False,
                    "raw_field_values_included": False,
                    "patient_identifier_included": False,
                    "provider_identifier_included": False,
                },
            }
        },
    )
    raise HTTPException(
        status_code=400,
        detail=_required_claim_fields_error_detail(issues),
    )


def _raise_for_invalid_claim_data_values(
    request: object, *, endpoint_name: str
) -> None:
    issues = validate_claim_data_values(_safe_attr(request, "claim_data", {}))
    if not issues:
        return

    logger.warning(
        "claim_data_value_validation_failed",
        extra={
            "claim_data_value_validation": {
                "endpoint": endpoint_name,
                "issue_count": len(issues),
                "issue_types": sorted({issue.error_code for issue in issues}),
                "issue_fields": sorted({issue.field for issue in issues}),
                "claim_data_key_count": len(_safe_attr(request, "claim_data", {}) or {}),
                "safe_context": {
                    "raw_claim_data_included": False,
                    "raw_field_values_included": False,
                    "patient_identifier_included": False,
                    "provider_identifier_included": False,
                },
            }
        },
    )
    raise HTTPException(
        status_code=400,
        detail=_claim_data_value_error_detail(issues),
    )


def _raise_for_invalid_diagnosis_procedure_linkage(
    request: object, *, endpoint_name: str
) -> None:
    issues = validate_diagnosis_procedure_linkage(
        diagnosis_codes=_safe_attr(request, "diagnosis_codes", None),
        procedure_codes=_safe_attr(request, "procedure_codes", None),
        claim_data=_safe_attr(request, "claim_data", {}),
    )
    if not issues:
        return

    logger.warning(
        "diagnosis_procedure_linkage_validation_failed",
        extra={
            "diagnosis_procedure_linkage_validation": {
                "endpoint": endpoint_name,
                "issue_count": len(issues),
                "issue_types": sorted({issue.error_code for issue in issues}),
                "issue_fields": sorted({issue.field for issue in issues}),
                "diagnosis_code_count": _non_empty_sequence_count(
                    _safe_attr(request, "diagnosis_codes", None)
                ),
                "procedure_code_count": _non_empty_sequence_count(
                    _safe_attr(request, "procedure_codes", None)
                ),
                "claim_data_key_count": len(_safe_attr(request, "claim_data", {}) or {}),
                "safe_context": {
                    "raw_code_values_included": False,
                    "raw_claim_data_included": False,
                    "raw_field_values_included": False,
                    "patient_identifier_included": False,
                    "provider_identifier_included": False,
                    "clinical_medical_necessity_asserted": False,
                },
            }
        },
    )
    raise HTTPException(
        status_code=400,
        detail=_diagnosis_procedure_linkage_error_detail(issues),
    )


def _raise_for_invalid_claim_codes(request: object, *, endpoint_name: str) -> None:
    issues = validate_claim_billing_codes(
        diagnosis_codes=_safe_attr(request, "diagnosis_codes", None),
        procedure_codes=_safe_attr(request, "procedure_codes", None),
    )
    if not issues:
        return

    logger.warning(
        "claim_healthcare_code_validation_failed",
        extra={
            "claim_code_validation": {
                "endpoint": endpoint_name,
                "issue_count": len(issues),
                "issue_types": sorted({issue.error_code for issue in issues}),
                "diagnosis_code_count": len(_safe_attr(request, "diagnosis_codes", []) or []),
                "procedure_code_count": len(_safe_attr(request, "procedure_codes", []) or []),
                "safe_context": {
                    "raw_code_values_included": False,
                    "raw_claim_data_included": False,
                    "patient_identifier_included": False,
                    "provider_identifier_included": False,
                },
            }
        },
    )
    raise HTTPException(status_code=400, detail=_claim_code_error_detail(issues))


def _current_user_id(current_user: dict) -> Optional[int]:
    return current_user.get("id") if isinstance(current_user, dict) else None


def _request_ip(request: Optional[Request]) -> Optional[str]:
    return get_client_ip(request) if request is not None else None


def _active_claims_query(db: Session):
    return db.query(Claim).filter(Claim.deleted_at.is_(None))


def _safe_attr(obj: object, field_name: str, default: object = None) -> object:
    value = getattr(obj, field_name, default)
    if type(value).__module__.startswith("unittest.mock"):
        return default
    return value


def _item_value(item: object, field_name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(field_name, default)
    return _safe_attr(item, field_name, default)


def _build_claim_human_review_gate(
    *,
    prediction: float | None,
    confidence: float | None,
    reasons: list[object] | None,
    recommendations: list[object] | None,
) -> dict[str, object]:
    normalized_prediction = float(prediction or 0.0)
    normalized_confidence = float(confidence or 0.0)
    reason_items = reasons or []
    recommendation_items = recommendations or []
    high_reason_count = sum(
        1
        for reason in reason_items
        if str(_item_value(reason, "severity", "") or "").lower() == "high"
    )
    high_recommendation_count = sum(
        1
        for recommendation in recommendation_items
        if str(_item_value(recommendation, "priority", "") or "").lower() == "high"
    )

    review_reasons: list[str] = []
    if normalized_prediction > HUMAN_REVIEW_HIGH_RISK_THRESHOLD:
        review_reasons.append("high_denial_risk_score")
    if high_reason_count:
        review_reasons.append("high_severity_denial_reason")
    if high_recommendation_count:
        review_reasons.append("high_priority_recommendation")

    review_required = bool(review_reasons)
    return {
        "human_review_required": review_required,
        "human_review_status": "required" if review_required else "not_required",
        "human_review_reasons": review_reasons,
        "human_review_threshold": HUMAN_REVIEW_HIGH_RISK_THRESHOLD,
        "human_review_next_action": (
            HUMAN_REVIEW_NEXT_ACTION_REQUIRED
            if review_required
            else HUMAN_REVIEW_NEXT_ACTION_STANDARD
        ),
        "safe_context": {
            "raw_claim_data_included": False,
            "raw_reason_text_included": False,
            "raw_recommendation_text_included": False,
            "patient_identifier_included": False,
            "provider_identifier_included": False,
            "risk_score_above_threshold": (
                normalized_prediction > HUMAN_REVIEW_HIGH_RISK_THRESHOLD
            ),
            "confidence_present": normalized_confidence > 0,
            "high_severity_reason_count": high_reason_count,
            "high_priority_recommendation_count": high_recommendation_count,
        },
    }


def _parse_document_ai_analysis(
    analysis: object,
    *,
    processing_stage: str,
    fallback_summary: str = "Analysis completed",
    plain_text_summary: bool = True,
) -> dict:
    if not isinstance(analysis, str):
        return {}
    json_match = DOCUMENT_ANALYSIS_JSON_BLOCK_RE.search(analysis)
    if not json_match:
        return {"summary": analysis[:500]} if plain_text_summary else {}

    try:
        parsed_analysis = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        logger.warning(
            "document_analysis_json_parse_failed",
            extra={
                "document_analysis_parse_error": {
                    "error_code": "invalid_analysis_json",
                    "processing_stage": processing_stage,
                    "analysis_present": bool(analysis),
                    "analysis_type": type(analysis).__name__,
                    "analysis_length": len(analysis),
                    "safe_context": {
                        "raw_analysis_included": False,
                        "raw_document_text_included": False,
                        "matched_value_included": False,
                    },
                    "exception_type": type(exc).__name__,
                }
            },
        )
        return {"summary": analysis[:500] if analysis else fallback_summary}

    if not isinstance(parsed_analysis, dict):
        logger.warning(
            "document_analysis_json_parse_failed",
            extra={
                "document_analysis_parse_error": {
                    "error_code": "unexpected_analysis_json_type",
                    "processing_stage": processing_stage,
                    "analysis_present": bool(analysis),
                    "analysis_type": type(analysis).__name__,
                    "analysis_length": len(analysis),
                    "json_value_type": type(parsed_analysis).__name__,
                    "safe_context": {
                        "raw_analysis_included": False,
                        "raw_document_text_included": False,
                        "matched_value_included": False,
                    },
                }
            },
        )
        return {"summary": analysis[:500] if analysis else fallback_summary}

    return parsed_analysis


def _claim_document_access_scope(claim: Claim) -> str:
    value = _safe_attr(
        claim,
        "document_access_scope",
        CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
    )
    if value in {
        CLAIM_DOCUMENT_ACCESS_SCOPE_OWNER,
        CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
        CLAIM_DOCUMENT_ACCESS_SCOPE_ADMIN_ONLY,
    }:
        return str(value)
    return CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM


def _claim_document_has_text(claim: Claim) -> bool:
    document_text = _safe_attr(claim, "document_text")
    return isinstance(document_text, str) and bool(document_text.strip())


def _claim_document_retention_expired(claim: Claim) -> bool:
    retention_until = _safe_attr(claim, "document_retention_until")
    if not isinstance(retention_until, datetime):
        return False
    now = datetime.utcnow()
    if retention_until.tzinfo is not None:
        now = datetime.now(retention_until.tzinfo)
    return retention_until <= now


def _claim_document_retired(claim: Claim) -> bool:
    return isinstance(_safe_attr(claim, "document_deleted_at"), datetime)


def _can_view_claim_document(claim: Claim, current_user: dict | None) -> bool:
    if not _claim_document_has_text(claim):
        return False
    if _claim_document_retired(claim) or _claim_document_retention_expired(claim):
        return False
    if not isinstance(current_user, dict):
        return True
    role = current_user.get("role")
    user_id = _current_user_id(current_user)
    access_scope = _claim_document_access_scope(claim)
    if role == ROLE_ADMIN:
        return True
    if access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_ADMIN_ONLY:
        return False
    if access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM:
        return role == ROLE_BILLING_STAFF
    if access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_OWNER:
        return user_id is not None and _safe_attr(claim, "document_created_by_user_id") == user_id
    return False


def _can_retire_claim_document(claim: Claim, current_user: dict | None) -> bool:
    if not _claim_document_has_text(claim) or _claim_document_retired(claim):
        return False
    if not isinstance(current_user, dict):
        return True
    if current_user.get("role") == ROLE_ADMIN:
        return True
    user_id = _current_user_id(current_user)
    return user_id is not None and _safe_attr(claim, "document_created_by_user_id") == user_id


def _claim_document_governance(
    claim: Claim,
    current_user: dict | None,
) -> ClaimDocumentGovernance | None:
    if not _claim_document_has_text(claim):
        return None
    return ClaimDocumentGovernance(
        access_scope=_claim_document_access_scope(claim),
        retention_until=_safe_attr(claim, "document_retention_until"),
        deleted_at=_safe_attr(claim, "document_deleted_at"),
        deleted_by_user_id=_safe_attr(claim, "document_deleted_by_user_id"),
        deletion_reason=_safe_attr(claim, "document_deletion_reason"),
        created_by_user_id=_safe_attr(claim, "document_created_by_user_id"),
        is_retired=_claim_document_retired(claim),
        is_retention_expired=_claim_document_retention_expired(claim),
        can_view_document=_can_view_claim_document(claim, current_user),
        can_retire_document=_can_retire_claim_document(claim, current_user),
    )


def _claim_response_for_user(claim: Claim, current_user: dict | None) -> ClaimResponse:
    governance = _claim_document_governance(claim, current_user)
    human_review_gate = _build_claim_human_review_gate(
        prediction=_safe_attr(claim, "denial_prediction"),
        confidence=_safe_attr(claim, "denial_confidence"),
        reasons=_safe_attr(claim, "denial_reasons", []) or [],
        recommendations=_safe_attr(claim, "recommendations", []) or [],
    )
    return ClaimResponse(
        id=_safe_attr(claim, "id"),
        patient_id=_safe_attr(claim, "patient_id"),
        provider_id=_safe_attr(claim, "provider_id"),
        claim_data=_safe_attr(claim, "claim_data", {}) or {},
        diagnosis_codes=_safe_attr(claim, "diagnosis_codes"),
        procedure_codes=_safe_attr(claim, "procedure_codes"),
        submission_date=_safe_attr(claim, "submission_date"),
        status=_safe_attr(claim, "status", "pending") or "pending",
        denial_prediction=_safe_attr(claim, "denial_prediction"),
        denial_confidence=_safe_attr(claim, "denial_confidence"),
        deleted_at=_safe_attr(claim, "deleted_at"),
        denial_reasons=_safe_attr(claim, "denial_reasons"),
        recommendations=_safe_attr(claim, "recommendations"),
        human_review_required=bool(human_review_gate["human_review_required"]),
        human_review_status=str(human_review_gate["human_review_status"]),
        human_review_reasons=list(human_review_gate["human_review_reasons"]),
        human_review_threshold=float(human_review_gate["human_review_threshold"]),
        human_review_next_action=str(human_review_gate["human_review_next_action"]),
        document_text=None,
        document_filename=(
            _safe_attr(claim, "document_filename")
            if governance and governance.can_view_document
            else None
        ),
        document_governance=governance,
        document_available=bool(governance and governance.can_view_document),
        created_at=_safe_attr(claim, "created_at", datetime.utcnow()),
        updated_at=_safe_attr(claim, "updated_at"),
        patient=_safe_attr(claim, "patient"),
    )


def _apply_claim_document_access_scope(query, current_user: dict | None):
    if not isinstance(current_user, dict):
        return query
    role = current_user.get("role")
    user_id = _current_user_id(current_user)
    if role == ROLE_ADMIN:
        return query
    if role == ROLE_BILLING_STAFF:
        predicates = [Claim.document_access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM]
        if user_id is not None:
            predicates.append(
                (Claim.document_access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_OWNER)
                & (Claim.document_created_by_user_id == user_id)
            )
        return query.filter(or_(*predicates))
    if role == ROLE_VIEWER:
        return query.filter(Claim.document_access_scope == CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM)
    return query.filter(Claim.id == -1)


def _visible_claim_documents_query(
    db: Session,
    *,
    current_user: dict | None,
    include_deleted: bool,
):
    query = _active_claims_query(db).filter(Claim.document_text.isnot(None))
    if not include_deleted:
        query = query.filter(Claim.document_deleted_at.is_(None))
    return _apply_claim_document_access_scope(query, current_user)


def _claim_document_counts(claims: list[Claim], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        value = _safe_attr(claim, field_name, None) or "unknown"
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _safe_claim_document_audit_details(details: dict | None) -> dict:
    if not isinstance(details, dict):
        return {}
    return {
        key: details[key]
        for key in SAFE_CLAIM_DOCUMENT_AUDIT_DETAIL_KEYS
        if key in details
    }


def _safe_upload_basename(filename: str | None, default: str = "") -> str:
    if not filename:
        return default
    return os.path.basename(str(filename).replace("\\", "/"))


def _source_file_suffixes(filename: str | None) -> list[str]:
    basename = _safe_upload_basename(filename).lower()
    if "." not in basename:
        return []
    return [f".{part}" for part in basename.split(".")[1:] if part]


def _source_file_extension(filename: str | None) -> str | None:
    suffixes = _source_file_suffixes(filename)
    return suffixes[-1] if suffixes else None


def _has_disallowed_inner_upload_extension(filename: str | None) -> bool:
    suffixes = _source_file_suffixes(filename)
    return any(
        suffix in DISALLOWED_INNER_UPLOAD_EXTENSIONS
        for suffix in suffixes[:-1]
    )


async def _read_upload_bytes_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    return await file.read(max_bytes + 1)


def _get_or_create_document_defaults(db: Session) -> tuple[int, int]:
    patient = db.query(Patient).filter(Patient.mrn == "SYNTH-DOC-DEFAULT").first()
    if not patient:
        patient = Patient(
            mrn="SYNTH-DOC-DEFAULT",
            first_name="Synthetic",
            last_name="Document",
        )
        db.add(patient)
        db.flush()

    provider = db.query(Provider).filter(Provider.npi == "1234567893").first()
    if not provider:
        provider = Provider(
            npi="1234567893",
            name="Synthetic Document Intake Provider",
            specialty="Revenue Cycle",
        )
        db.add(provider)
        db.flush()

    return patient.id, provider.id


async def _build_denial_workflow(
    *,
    document_text: str,
    document_type: str,
    source_document_id: str,
    source_title: str,
):
    return await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(
            document_text=document_text,
            document_type=document_type,
            source_document_id=source_document_id,
            source_title=source_title,
            generate_draft=True,
            use_llm=False,
        )
    )


def _safe_surface_metadata(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, str] = {}
    for key, item in value.items():
        if item is None:
            continue
        text = str(item)
        if len(text) > 120:
            text = f"{text[:117]}..."
        safe[str(key)] = text
    return safe


def _inspect_document_surfaces(
    *,
    source_id: str,
    document_id: str,
    source_filename: str | None,
    source_mime_type: str | None,
    visible_text: str | None = None,
    ocr_text: str | None = None,
    metadata: dict | None = None,
) -> CorpusDocumentSurfaceInspectResponse:
    return CorpusSafetyService().inspect_document_surfaces(
        CorpusDocumentSurfaceInspectRequest(
            source_id=source_id,
            document_id=document_id,
            document_role="denial_letter",
            source_filename=source_filename,
            source_mime_type=source_mime_type,
            visible_text=visible_text,
            ocr_text=ocr_text,
            metadata=_safe_surface_metadata(metadata),
        )
    )


def _raise_batch_claim_upload_error(
    *,
    status_code: int,
    error_code: str,
    parser_stage: str,
    message: str,
    source_filename_present: bool,
    source_file_extension: str | None,
    source_mime_type: str | None,
    content_length: int | None = None,
    field: str | None = None,
    claim_index: int | None = None,
    segment_index: int | None = None,
    segment_id: str | None = None,
    segment_count: int | None = None,
    safe_context: dict | None = None,
) -> None:
    merged_safe_context = {
        "edi_parser": "edi_837",
        "raw_filename_included": False,
        "raw_edi_text_included": False,
        "raw_segment_included": False,
    }
    if safe_context:
        merged_safe_context.update(safe_context)
    detail = {
        "error_code": error_code,
        "parser_stage": parser_stage,
        "message": message,
        "source_filename_present": source_filename_present,
        "source_file_extension": source_file_extension,
        "source_mime_type": source_mime_type,
        "content_length": content_length,
        "field": field,
        "claim_index": claim_index,
        "segment_index": segment_index,
        "segment_id": segment_id,
        "segment_count": segment_count,
        "safe_context": merged_safe_context,
    }
    logger.warning(
        "EDI 837 batch upload rejected",
        extra={"claim_batch_upload_error": detail},
    )
    raise HTTPException(
        status_code=status_code,
        detail=detail,
    )


def _raise_upload_document_error(
    *,
    status_code: int,
    error_code: str,
    processing_stage: str,
    message: str,
    source_filename_present: bool,
    source_file_extension: str | None,
    source_mime_type: str | None,
    content_length: int | None = None,
    max_upload_size_bytes: int | None = None,
    processed_size_bytes: int | None = None,
    exception_type: str | None = None,
    text_length: int | None = None,
    safe_context: dict[str, object] | None = None,
) -> None:
    merged_safe_context = {
        "upload_surface": "claim_document_upload",
        "raw_filename_included": False,
        "raw_document_text_included": False,
        "raw_file_bytes_included": False,
        "raw_pdf_parser_error_included": False,
        "raw_exception_message_included": False,
    }
    if safe_context:
        merged_safe_context.update(safe_context)
    detail = {
        "error_code": error_code,
        "processing_stage": processing_stage,
        "message": message,
        "source_filename_present": source_filename_present,
        "source_file_extension": source_file_extension,
        "source_mime_type": source_mime_type,
        "content_length": content_length,
        "max_upload_size_bytes": max_upload_size_bytes,
        "processed_size_bytes": processed_size_bytes,
        "exception_type": exception_type,
        "text_length": text_length,
        "safe_context": merged_safe_context,
    }
    logger.warning(
        "Claim document upload rejected",
        extra={"claim_document_upload_error": detail},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _log_batch_document_analysis_failure(
    *,
    error_code: str,
    processing_stage: str,
    document_index: int,
    document_text: object,
    document_type: str | None,
    exception: Exception | None = None,
) -> None:
    safe_document_text = document_text if isinstance(document_text, str) else ""
    detail = {
        "error_code": error_code,
        "processing_stage": processing_stage,
        "document_index": document_index,
        "document_text_present": bool(safe_document_text),
        "document_text_length": len(safe_document_text),
        "document_type": document_type,
        "exception_type": type(exception).__name__ if exception else None,
        "safe_context": {
            "upload_surface": "batch_document_analysis",
            "raw_document_text_included": False,
            "raw_exception_message_included": False,
            "raw_prompt_included": False,
            "raw_model_response_included": False,
        },
    }
    logger.warning(
        "Batch document analysis failed",
        extra={"document_batch_analysis_error": detail},
    )


def _batch_claim_validation_issue(issue) -> BatchClaimUploadValidationIssue:
    return BatchClaimUploadValidationIssue(
        message=issue.message,
        field=issue.field,
        error_code=issue.error_code,
        parser_stage=issue.parser_stage,
        severity=issue.severity,
        claim_index=issue.claim_index,
        segment_index=issue.segment_index,
        segment_id=issue.segment_id,
    )


def _batch_claim_service_line(service_line) -> BatchClaimUploadServiceLine:
    return BatchClaimUploadServiceLine(
        segment_index=service_line.segment_index,
        segment_id=service_line.segment_id,
        procedure_code=service_line.procedure_code,
        procedure_modifiers=service_line.procedure_modifiers,
        charge_amount=service_line.charge_amount,
        unit_count=service_line.unit_count,
        revenue_code=service_line.revenue_code,
        product_service_qualifier=service_line.product_service_qualifier,
        diagnosis_pointers=service_line.diagnosis_pointers,
    )


def _batch_claim_procedure_codes(claim: EDI837Claim) -> list[str]:
    seen = set()
    codes = []
    for service_line in claim.service_lines:
        code = service_line.procedure_code
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _batch_claim_upload_result(claim: EDI837Claim) -> BatchClaimUploadResult:
    has_errors = any(issue.severity == "error" for issue in claim.validation_issues)
    return BatchClaimUploadResult(
        claim_index=claim.claim_index,
        status="validation_failed" if has_errors else "ready_for_claim_review",
        claim_control_number=claim.claim_control_number,
        total_charge_amount=claim.total_charge_amount,
        place_of_service_code=claim.place_of_service_code,
        facility_code_qualifier=claim.facility_code_qualifier,
        claim_frequency_code=claim.claim_frequency_code,
        payer_name=claim.payer_name,
        payer_identifier=claim.payer_identifier,
        diagnosis_codes=claim.diagnosis_codes,
        procedure_codes=_batch_claim_procedure_codes(claim),
        service_line_count=len(claim.service_lines),
        service_lines=[
            _batch_claim_service_line(service_line)
            for service_line in claim.service_lines
        ],
        validation_issues=[
            _batch_claim_validation_issue(issue)
            for issue in claim.validation_issues
        ],
    )


@router.post("/predict", response_model=ClaimPredictionResponse)
async def predict_denial(
    request: ClaimPredictionRequest,
    http_request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    _raise_for_invalid_claim_codes(request, endpoint_name="predict_denial")
    _raise_for_invalid_diagnosis_procedure_linkage(
        request, endpoint_name="predict_denial"
    )
    _raise_for_invalid_claim_data_values(request, endpoint_name="predict_denial")
    service = PredictionService(db)
    prediction, confidence, reasons, recommendations = await service.predict_denial(request)
    human_review_gate = _build_claim_human_review_gate(
        prediction=prediction,
        confidence=confidence,
        reasons=reasons,
        recommendations=recommendations,
    )
    prediction_metadata = service.build_prediction_metadata(
        request,
        reasons,
        recommendations,
    )
    if not isinstance(prediction_metadata, dict):
        prediction_metadata = {}
    log_audit(
        db=db,
        action="claim_denial_predicted",
        user_id=_current_user_id(current_user),
        details={
            "patient_id_present": request.patient_id is not None,
            "provider_id_present": request.provider_id is not None,
            "diagnosis_code_count": len(request.diagnosis_codes or []),
            "procedure_code_count": len(request.procedure_codes or []),
            "claim_data_keys": sorted((request.claim_data or {}).keys()),
            "denial_prediction": prediction,
            "denial_confidence": confidence,
            "reason_count": len(reasons),
            "recommendation_count": len(recommendations),
            "human_review_required": human_review_gate["human_review_required"],
            "human_review_status": human_review_gate["human_review_status"],
            "human_review_reason_count": len(
                human_review_gate["human_review_reasons"]
            ),
            "human_review_reasons": human_review_gate["human_review_reasons"],
            "human_review_threshold": human_review_gate["human_review_threshold"],
            "prediction_metadata": prediction_metadata,
            "safe_context": human_review_gate["safe_context"],
        },
        ip_address=_request_ip(http_request),
    )
    return ClaimPredictionResponse(
        denial_prediction=prediction,
        denial_confidence=confidence,
        denial_reasons=reasons,
        recommendations=recommendations,
        prediction_metadata=prediction_metadata,
        human_review_required=bool(human_review_gate["human_review_required"]),
        human_review_status=str(human_review_gate["human_review_status"]),
        human_review_reasons=list(human_review_gate["human_review_reasons"]),
        human_review_threshold=float(human_review_gate["human_review_threshold"]),
        human_review_next_action=str(human_review_gate["human_review_next_action"]),
    )


@router.post("/submit", response_model=ClaimSubmitResponse)
async def submit_claim(
    request: ClaimSubmitRequest,
    http_request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    _raise_for_invalid_claim_codes(request, endpoint_name="submit_claim")
    _raise_for_invalid_diagnosis_procedure_linkage(
        request, endpoint_name="submit_claim"
    )
    _raise_for_missing_required_claim_fields(request, endpoint_name="submit_claim")
    _raise_for_invalid_claim_data_values(request, endpoint_name="submit_claim")
    service = PredictionService(db)
    prediction, confidence, reasons, recommendations = await service.predict_denial(request)
    human_review_gate = _build_claim_human_review_gate(
        prediction=prediction,
        confidence=confidence,
        reasons=reasons,
        recommendations=recommendations,
    )
    prediction_metadata = service.build_prediction_metadata(
        request,
        reasons,
        recommendations,
    )
    if not isinstance(prediction_metadata, dict):
        prediction_metadata = {}

    claim = Claim(
        patient_id=request.patient_id,
        provider_id=request.provider_id,
        claim_data=request.claim_data,
        diagnosis_codes=request.diagnosis_codes,
        procedure_codes=request.procedure_codes,
        submission_date=datetime.utcnow(),
        status="submitted",
        denial_prediction=prediction,
        denial_confidence=confidence,
        denial_reasons=[r.model_dump() for r in reasons],
        recommendations=[r.model_dump() for r in recommendations],
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    log_audit(
        db=db,
        action="claim_submitted",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "patient_id_present": request.patient_id is not None,
            "provider_id_present": request.provider_id is not None,
            "diagnosis_code_count": len(request.diagnosis_codes or []),
            "procedure_code_count": len(request.procedure_codes or []),
            "claim_data_keys": sorted((request.claim_data or {}).keys()),
            "status": claim.status,
            "denial_prediction": prediction,
            "denial_confidence": confidence,
            "high_denial_risk": prediction > 0.5,
            "human_review_required": human_review_gate["human_review_required"],
            "human_review_status": human_review_gate["human_review_status"],
            "human_review_reason_count": len(
                human_review_gate["human_review_reasons"]
            ),
            "human_review_reasons": human_review_gate["human_review_reasons"],
            "human_review_threshold": human_review_gate["human_review_threshold"],
            "prediction_metadata": prediction_metadata,
            "safe_context": human_review_gate["safe_context"],
        },
        ip_address=_request_ip(http_request),
    )

    message = "Claim submitted successfully"
    if human_review_gate["human_review_required"]:
        message = (
            "Claim submitted with high denial risk; human review is required "
            "before the next payer action"
        )
    elif prediction > 0.3:
        message = "Claim submitted with moderate denial risk - consider recommendations"

    return ClaimSubmitResponse(
        claim_id=claim.id,
        status=claim.status,
        denial_prediction=prediction,
        denial_confidence=confidence,
        denial_reasons=reasons,
        recommendations=recommendations,
        prediction_metadata=prediction_metadata,
        human_review_required=bool(human_review_gate["human_review_required"]),
        human_review_status=str(human_review_gate["human_review_status"]),
        human_review_reasons=list(human_review_gate["human_review_reasons"]),
        human_review_threshold=float(human_review_gate["human_review_threshold"]),
        human_review_next_action=str(human_review_gate["human_review_next_action"]),
        message=message,
    )


@router.get("/", response_model=List[ClaimResponse])
async def list_claims(
    request: Request = None,
    skip: int = 0,
    limit: int = 100,
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    patient_mrn: Optional[str] = Query(None, description="Filter by patient MRN"),
    patient_first_name: Optional[str] = Query(None, description="Filter by patient's first name"),
    patient_last_name: Optional[str] = Query(None, description="Filter by patient's last name"),
    patient_dob: Optional[date] = Query(
        None, description="Filter by patient's date of birth (YYYY-MM-DD)"
    ),
    status_filter: Optional[str] = Query(None, description="Filter by claim status"),
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    from app.utils.patient_search_validator import validate_patient_search

    has_patient_filter = any(
        [patient_id, patient_mrn, patient_first_name, patient_last_name, patient_dob]
    )
    if has_patient_filter:
        is_valid, error_message = validate_patient_search(
            mrn=patient_mrn,
            first_name=patient_first_name,
            last_name=patient_last_name,
            date_of_birth=patient_dob,
            patient_id=patient_id,
        )

        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

    query = (
        _active_claims_query(db)
        .options(joinedload(Claim.patient))
        .join(Patient)
        .filter(Patient.deleted_at.is_(None))
    )

    if has_patient_filter:
        if patient_id:
            query = query.filter(Patient.id == patient_id)

        if patient_mrn:
            query = query.filter(Patient.mrn == patient_mrn)

        if patient_first_name:
            query = query.filter(Patient.first_name.ilike(f"%{patient_first_name}%"))

        if patient_last_name:
            query = query.filter(Patient.last_name.ilike(f"%{patient_last_name}%"))

        if patient_dob:
            query = query.filter(Patient.date_of_birth == patient_dob)

    if status_filter:
        if not is_readable_claim_status(status_filter):
            raise HTTPException(
                status_code=400,
                detail=_claim_status_error_detail(
                    error_code="invalid_claim_status_filter",
                    message="Claim status filter is not supported.",
                    requested_status=normalize_claim_status(status_filter),
                    blocker_codes=["status_filter_is_not_supported"],
                ),
            )
        query = query.filter(Claim.status == normalize_claim_status(status_filter))

    claims = query.order_by(Claim.created_at.desc()).offset(skip).limit(limit).all()
    log_audit(
        db=db,
        action="claims_listed",
        user_id=_current_user_id(current_user),
        details={
            "skip": skip,
            "limit": limit,
            "result_count": len(claims),
            "patient_filter_present": has_patient_filter,
            "patient_id_filter_present": patient_id is not None,
            "patient_mrn_filter_present": patient_mrn is not None,
            "patient_first_name_filter_present": patient_first_name is not None,
            "patient_last_name_filter_present": patient_last_name is not None,
            "patient_dob_filter_present": patient_dob is not None,
            "status_filter_present": status_filter is not None,
            "status_filter": status_filter,
        },
        ip_address=_request_ip(request),
    )
    return [_claim_response_for_user(claim, current_user) for claim in claims]


@router.get(
    "/documents/governance-summary",
    response_model=ClaimDocumentGovernanceSummary,
)
async def claim_document_governance_summary(
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    claims = _visible_claim_documents_query(
        db,
        current_user=current_user,
        include_deleted=True,
    ).all()
    active_claims = [claim for claim in claims if not _claim_document_retired(claim)]
    deleted_claims = [claim for claim in claims if _claim_document_retired(claim)]
    expired_active_count = sum(
        1 for claim in active_claims if _claim_document_retention_expired(claim)
    )
    retained_without_expiration_count = sum(
        1
        for claim in active_claims
        if not isinstance(_safe_attr(claim, "document_retention_until"), datetime)
    )
    result = ClaimDocumentGovernanceSummary(
        active_count=len(active_claims),
        deleted_count=len(deleted_claims),
        expired_active_count=expired_active_count,
        retained_without_expiration_count=retained_without_expiration_count,
        counts_by_access_scope=_claim_document_counts(
            active_claims,
            "document_access_scope",
        ),
    )
    log_audit(
        db=db,
        action="claim_document_governance_viewed",
        user_id=_current_user_id(current_user),
        details={
            "active_count": result.active_count,
            "deleted_count": result.deleted_count,
            "expired_active_count": result.expired_active_count,
            "retained_without_expiration_count": (
                result.retained_without_expiration_count
            ),
        },
        ip_address=_request_ip(request),
    )
    return result


@router.get(
    "/documents/audit",
    response_model=ClaimDocumentAuditDashboardResponse,
)
async def claim_document_audit_dashboard(
    request: Request = None,
    claim_id: Optional[int] = Query(None, description="Filter by claim ID"),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    query = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(CLAIM_DOCUMENT_AUDIT_ACTIONS))
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit * 3)
    )
    events: list[ClaimDocumentAuditEvent] = []
    counts_by_action: dict[str, int] = {}
    for audit_log in query.all():
        if claim_id is not None and audit_log.claim_id != claim_id:
            continue
        details = _safe_claim_document_audit_details(audit_log.details)
        counts_by_action[audit_log.action] = counts_by_action.get(audit_log.action, 0) + 1
        events.append(
            ClaimDocumentAuditEvent(
                id=audit_log.id,
                action=audit_log.action,
                user_id=audit_log.user_id,
                claim_id=audit_log.claim_id,
                timestamp=audit_log.timestamp or datetime.utcnow(),
                details=details,
            )
        )
        if len(events) >= limit:
            break
    result = ClaimDocumentAuditDashboardResponse(
        event_count=len(events),
        claim_id=claim_id,
        counts_by_action=counts_by_action,
        events=events,
    )
    log_audit(
        db=db,
        action="claim_document_audit_dashboard_viewed",
        user_id=_current_user_id(current_user),
        details={
            "claim_id": claim_id,
            "limit": limit,
            "result_count": result.event_count,
        },
        ip_address=_request_ip(request),
    )
    return result


@router.post("/batch-upload", response_model=BatchClaimsUploadResponse)
async def batch_upload_claims(
    request: Request = None,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    original_filename = _safe_upload_basename(file.filename)
    source_filename_present = bool(original_filename)
    source_file_extension = _source_file_extension(original_filename)
    raw_mime_type = getattr(file, "content_type", None)
    source_mime_type = raw_mime_type if isinstance(raw_mime_type, str) else None

    if _has_disallowed_inner_upload_extension(original_filename):
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="suspicious_extension_chain",
            parser_stage="file_validation",
            message="Uploaded EDI 837 filename contains a blocked inner extension.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            safe_context={
                "inner_extension_chain_checked": True,
            },
        )

    if source_file_extension not in EDI_BATCH_UPLOAD_EXTENSIONS:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="unsupported_file_type",
            parser_stage="file_validation",
            message="Batch claim uploads accept EDI 837 files with .edi or .txt extensions.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
        )

    content = await _read_upload_bytes_with_limit(file, EDI_BATCH_UPLOAD_MAX_BYTES)
    content_length = len(content)
    if content_length == 0:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="empty_file",
            parser_stage="file_validation",
            message="Uploaded EDI 837 file is empty.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
        )
    if content_length > EDI_BATCH_UPLOAD_MAX_BYTES:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="file_too_large",
            parser_stage="file_validation",
            message="Uploaded EDI 837 file exceeds the 10 MB limit.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
        )

    try:
        edi_text = content.decode("utf-8")
    except UnicodeDecodeError:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="invalid_text_encoding",
            parser_stage="text_decode",
            message="Uploaded EDI 837 file must be UTF-8 text.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
        )

    batch_size = estimate_edi_837_batch_size(edi_text)
    if batch_size.segment_count > EDI_BATCH_UPLOAD_MAX_SEGMENTS:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="too_many_segments",
            parser_stage="pre_parse_batch_validation",
            message="Uploaded EDI 837 file exceeds the supported segment count.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
            field="segment_count",
            segment_count=batch_size.segment_count,
            safe_context={
                "pre_parse_guard": True,
                "raw_claim_values_included": False,
                "max_segment_count": EDI_BATCH_UPLOAD_MAX_SEGMENTS,
            },
        )

    if batch_size.claim_count > EDI_BATCH_UPLOAD_MAX_CLAIMS:
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code="too_many_claims",
            parser_stage="pre_parse_batch_validation",
            message="Uploaded EDI 837 file exceeds the supported claim count.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
            field="claim_count",
            segment_count=batch_size.segment_count,
            safe_context={
                "pre_parse_guard": True,
                "raw_claim_values_included": False,
                "claim_count": batch_size.claim_count,
                "max_claim_count": EDI_BATCH_UPLOAD_MAX_CLAIMS,
            },
        )

    try:
        parse_result = parse_edi_837(edi_text)
    except EDIParserError as exc:
        parser_detail = exc.safe_detail()
        _raise_batch_claim_upload_error(
            status_code=400,
            error_code=parser_detail["error_code"],
            parser_stage=parser_detail["parser_stage"],
            message=str(exc),
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=content_length,
            field=parser_detail["field"],
            claim_index=parser_detail["claim_index"],
            segment_index=parser_detail["segment_index"],
            segment_id=parser_detail["segment_id"],
            segment_count=parser_detail["segment_count"],
            safe_context=parser_detail["safe_context"],
        )

    upload_document_id = uuid.uuid4().hex[:12].upper()
    document_surface_inspection = _inspect_document_surfaces(
        source_id=f"EDI-BATCH-{upload_document_id}",
        document_id=f"EDI-BATCH-DOC-{upload_document_id}",
        source_filename=original_filename,
        source_mime_type=source_mime_type or "application/edi-x12",
        visible_text=edi_text,
        metadata={
            "source_filename_present": source_filename_present,
            "source_file_extension": source_file_extension,
            "source_mime_type": source_mime_type or "application/edi-x12",
            "upload_size_bytes": content_length,
            "edi_parser": "edi_837",
            "segment_count": parse_result.segment_count,
            "claim_count": len(parse_result.claims),
        },
    )
    claim_results = [
        _batch_claim_upload_result(claim)
        for claim in parse_result.claims
    ]
    invalid_claim_count = sum(
        1 for claim in claim_results if claim.status == "validation_failed"
    )
    valid_claim_count = len(claim_results) - invalid_claim_count

    log_audit(
        db=db,
        action="claims_batch_uploaded",
        user_id=_current_user_id(current_user),
        details={
            "source_filename_present": source_filename_present,
            "source_file_extension": source_file_extension,
            "source_mime_type": source_mime_type or "application/edi-x12",
            "original_size": content_length,
            "processed_size": content_length,
            "was_resized": False,
            "was_converted": False,
            "document_type": "edi_837_claim_batch",
            "claim_count": len(claim_results),
            "valid_claim_count": valid_claim_count,
            "invalid_claim_count": invalid_claim_count,
            "validation_issue_count": len(parse_result.validation_issues),
            "segment_count": parse_result.segment_count,
            "access_scope": CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
            "document_access_scope": CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
            "surface_count": document_surface_inspection.surface_count,
            "surface_blocking_count": (
                document_surface_inspection.blocking_surface_count
            ),
            "surface_residual_risk_score": (
                document_surface_inspection.residual_risk_score
            ),
            "surface_deidentification_status": (
                document_surface_inspection.deidentification_status
            ),
        },
        ip_address=_request_ip(request),
    )

    return BatchClaimsUploadResponse(
        accepted=bool(claim_results),
        source_filename_present=source_filename_present,
        source_file_extension=source_file_extension,
        source_mime_type=source_mime_type or "application/edi-x12",
        segment_count=parse_result.segment_count,
        claim_count=len(claim_results),
        valid_claim_count=valid_claim_count,
        invalid_claim_count=invalid_claim_count,
        validation_issue_count=len(parse_result.validation_issues),
        interchange_control_number=parse_result.interchange_control_number,
        group_control_number=parse_result.group_control_number,
        transaction_control_number=parse_result.transaction_control_number,
        document_surface_inspection=document_surface_inspection,
        claims=claim_results,
    )


@router.patch("/{claim_id}/status", response_model=ClaimStatusUpdateResponse)
async def update_claim_status(
    claim_id: int,
    status_request: ClaimStatusUpdateRequest,
    request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    requested_status = normalize_claim_status(status_request.status)
    claim = db.query(Claim).filter(Claim.deleted_at.is_(None), Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    current_status = normalize_claim_status(_safe_attr(claim, "status", "pending") or "pending")
    transition_allowed, blocker_codes = validate_claim_status_transition(
        current_status,
        requested_status,
    )
    if not transition_allowed:
        status_code = 400 if "requested_status_is_not_canonical" in blocker_codes else 409
        raise HTTPException(
            status_code=status_code,
            detail=_claim_status_error_detail(
                error_code=(
                    "invalid_claim_status"
                    if status_code == 400
                    else "invalid_claim_status_transition"
                ),
                message=(
                    "Claim status is not supported."
                    if status_code == 400
                    else "Claim status transition is not allowed."
                ),
                current_status=current_status,
                requested_status=requested_status,
                blocker_codes=blocker_codes,
            ),
        )

    claim.status = requested_status
    if requested_status == "submitted" and not _safe_attr(claim, "submission_date"):
        claim.submission_date = datetime.utcnow()
    db.commit()
    db.refresh(claim)

    allowed_next = list(allowed_next_claim_statuses(claim.status))
    log_audit(
        db=db,
        action="claim_status_updated",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "previous_status": current_status,
            "status": claim.status,
            "allowed_next_status_count": len(allowed_next),
            "transition_reason_present": bool(
                status_request.transition_reason
                and status_request.transition_reason.strip()
            ),
            "transition_reason_length": len(status_request.transition_reason or ""),
        },
        ip_address=_request_ip(request),
    )
    return ClaimStatusUpdateResponse(
        claim_id=claim.id,
        previous_status=current_status,
        status=claim.status,
        allowed_next_statuses=allowed_next,
        transition_allowed=True,
        message="Claim status updated.",
    )


@router.delete("/{claim_id}", status_code=204)
async def delete_claim(
    claim_id: int,
    request: Request = None,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.deleted_at.is_(None), Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    deleted_at = datetime.utcnow()
    claim.deleted_at = deleted_at
    claim.deleted_by_user_id = _current_user_id(current_user)
    claim.deletion_reason = CLAIM_SOFT_DELETE_REASON
    db.commit()

    log_audit(
        db=db,
        action="claim_deleted",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "soft_deleted": True,
            "document_present": bool(_safe_attr(claim, "document_text")),
            "status": normalize_claim_status(
                _safe_attr(claim, "status", "pending") or "pending"
            ),
        },
        ip_address=_request_ip(request),
    )


@router.post("/{claim_id}/restore", response_model=ClaimResponse)
async def restore_claim(
    claim_id: int,
    request: Request = None,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    patient = _safe_attr(claim, "patient")
    if patient is not None and _safe_attr(patient, "deleted_at") is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot restore claim while patient is deleted",
        )

    was_deleted = _safe_attr(claim, "deleted_at") is not None
    if was_deleted:
        claim.deleted_at = None
        claim.deleted_by_user_id = None
        claim.deletion_reason = None
        db.commit()
        db.refresh(claim)

    log_audit(
        db=db,
        action="claim_restored",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "was_deleted": was_deleted,
            "patient_deleted": False,
        },
        ip_address=_request_ip(request),
    )
    return _claim_response_for_user(claim, current_user)


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: int,
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.deleted_at.is_(None), Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    governance = _claim_document_governance(claim, current_user)
    log_audit(
        db=db,
        action="claim_viewed",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "document_available": bool(governance and governance.can_view_document),
            "document_retired": bool(governance and governance.is_retired),
            "document_retention_expired": bool(
                governance and governance.is_retention_expired
            ),
            "access_scope": (
                governance.access_scope if governance else None
            ),
        },
        ip_address=_request_ip(request),
    )
    return _claim_response_for_user(claim, current_user)


@router.get("/{claim_id}/document", response_model=ClaimDocumentResponse)
async def get_claim_document(
    claim_id: int,
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.deleted_at.is_(None), Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not claim.document_text:
        raise HTTPException(status_code=404, detail="No document attached to this claim")
    if _claim_document_retired(claim):
        raise HTTPException(status_code=410, detail="Claim document is retired")
    if _claim_document_retention_expired(claim):
        raise HTTPException(status_code=410, detail="Claim document retention period has expired")
    if not _can_view_claim_document(claim, current_user):
        raise HTTPException(status_code=403, detail="Claim document is not accessible for this role")
    governance = _claim_document_governance(claim, current_user)
    log_audit(
        db=db,
        action="claim_document_viewed",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "document_available": True,
            "access_scope": _claim_document_access_scope(claim),
            "retention_until": (
                governance.retention_until.isoformat()
                if governance and governance.retention_until
                else None
            ),
            "document_retired": False,
            "document_retention_expired": False,
        },
        ip_address=_request_ip(request),
    )
    return {
        "claim_id": claim.id,
        "filename": claim.document_filename,
        "document_text": claim.document_text,
        "governance": governance,
    }


@router.post("/{claim_id}/document/delete", response_model=ClaimDocumentDeleteResponse)
async def retire_claim_document(
    claim_id: int,
    delete_request: ClaimDocumentDeleteRequest,
    request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.deleted_at.is_(None), Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not _claim_document_has_text(claim):
        raise HTTPException(status_code=404, detail="No document attached to this claim")
    if not _can_retire_claim_document(claim, current_user):
        raise HTTPException(status_code=403, detail="Only admins or document owners can retire claim documents")

    claim.document_deleted_at = datetime.utcnow()
    claim.document_deleted_by_user_id = _current_user_id(current_user)
    claim.document_deletion_reason = delete_request.deletion_reason.strip()[:255]
    db.commit()
    db.refresh(claim)
    deleted_at = claim.document_deleted_at or datetime.utcnow()
    log_audit(
        db=db,
        action="claim_document_retired",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "claim_id": claim.id,
            "access_scope": _claim_document_access_scope(claim),
            "deleted_at": deleted_at.isoformat(),
            "deleted_by_user_id": claim.document_deleted_by_user_id,
            "deletion_reason": claim.document_deletion_reason,
        },
        ip_address=_request_ip(request),
    )
    return ClaimDocumentDeleteResponse(
        claim_id=claim.id,
        deleted=True,
        deleted_at=deleted_at,
        deleted_by_user_id=claim.document_deleted_by_user_id,
        deletion_reason=claim.document_deletion_reason or "retention_or_privacy_review",
    )


@router.post("/analyze-document", response_model=DocumentAnalysisResponse)
@limiter.limit("5/minute")
async def analyze_document(
    request: Request,
    doc_request: DocumentAnalysisRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    if not doc_request.document_text or not doc_request.document_text.strip():
        raise HTTPException(status_code=400, detail="Document text is required and cannot be empty")

    if len(doc_request.document_text.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Document text is too short (minimum 10 characters)"
        )

    service = DocumentAnalysisService(db)
    result = await service.analyze_document(
        document_text=doc_request.document_text, document_type=doc_request.document_type
    )
    denial_workflow = await _build_denial_workflow(
        document_text=doc_request.document_text,
        document_type=doc_request.document_type or "denial_letter",
        source_document_id="document_analysis_text",
        source_title="Document analysis request",
    )
    patient_id, provider_id = _get_or_create_document_defaults(db)

    ai_analysis = _parse_document_ai_analysis(
        result.analysis,
        processing_stage="analyze_document_analysis_parse",
    )

    claim = Claim(
        patient_id=patient_id,
        provider_id=provider_id,
        claim_data={
            "document_type": result.document_type,
            "amount": result.claim_amount or 0,
            "service_date": result.service_date,
            "ai_analysis": ai_analysis.get(
                "summary", result.analysis[:500] if result.analysis else ""
            ),
            "appeal_strategy": result.appeal_strategy
            or ai_analysis.get("estimated_success_rate", ""),
            "full_analysis": result.analysis,
            "denial_workflow": denial_workflow.model_dump(mode="json"),
        },
        diagnosis_codes=result.extracted_codes or [],
        procedure_codes=[],
        submission_date=datetime.utcnow(),
        status="draft",
        denial_prediction=0.5
        if ai_analysis.get("appeal_strength") == "moderate"
        else (0.3 if ai_analysis.get("appeal_strength") == "strong" else 0.7),
        denial_confidence=0.7,
        denial_reasons=[
            {
                "reason": result.denial_reason or "Document analyzed",
                "severity": "medium",
                "code": result.denial_code,
            }
        ],
        recommendations=[r.model_dump() for r in result.recommendations]
        if result.recommendations
        else [],
        document_text=doc_request.document_text,
        document_filename=None,
        document_access_scope=CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
        document_created_by_user_id=_current_user_id(current_user),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    log_audit(
        db=db,
        action="document_analyzed",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "document_type": doc_request.document_type,
            "text_length": len(doc_request.document_text),
            "extracted_amount": result.claim_amount,
            "denial_code": result.denial_code,
            "access_scope": CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
        },
        ip_address=_request_ip(request),
    )

    return DocumentAnalysisResponse(
        claim_id=claim.id,
        document_type=result.document_type,
        payer_name=result.payer_name,
        denial_reason=result.denial_reason,
        denial_code=result.denial_code,
        claim_amount=result.claim_amount,
        service_date=result.service_date,
        patient_name=result.patient_name,
        policy_number=result.policy_number,
        extracted_codes=result.extracted_codes,
        analysis=result.analysis,
        recommendations=result.recommendations,
        appeal_strategy=result.appeal_strategy,
        denial_workflow=denial_workflow,
        analyzed_at=result.analyzed_at,
    )


@router.post("/upload-document", response_model=DocumentAnalysisResponse)
async def upload_document(
    request: Request = None,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    from app.utils.file_processing import FileProcessingError, FileProcessor
    from app.utils.format import format_file_size

    original_filename = _safe_upload_basename(file.filename, default="unknown")
    source_filename_present = bool(original_filename)
    source_file_extension = _source_file_extension(original_filename)
    raw_mime_type = getattr(file, "content_type", None)
    source_mime_type = raw_mime_type if isinstance(raw_mime_type, str) else None

    if _has_disallowed_inner_upload_extension(original_filename):
        _raise_upload_document_error(
            status_code=400,
            error_code="suspicious_extension_chain",
            processing_stage="file_validation",
            message="Uploaded claim document filename contains a blocked inner extension.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            safe_context={
                "inner_extension_chain_checked": True,
            },
        )

    if source_file_extension not in CLAIM_DOCUMENT_UPLOAD_EXTENSIONS:
        _raise_upload_document_error(
            status_code=400,
            error_code="unsupported_file_type",
            processing_stage="file_validation",
            message=(
                "Unsupported claim document file type. Supported types: "
                f"{', '.join(CLAIM_DOCUMENT_UPLOAD_EXTENSIONS)}"
            ),
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
        )

    content = await _read_upload_bytes_with_limit(
        file,
        CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
    )
    original_size = len(content)
    if original_size == 0:
        _raise_upload_document_error(
            status_code=400,
            error_code="empty_file",
            processing_stage="file_validation",
            message="Uploaded claim document is empty.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=original_size,
            max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
        )
    if original_size > CLAIM_DOCUMENT_UPLOAD_MAX_BYTES:
        _raise_upload_document_error(
            status_code=400,
            error_code="file_too_large",
            processing_stage="file_validation",
            message="Uploaded claim document exceeds the 10 MB limit before processing.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=original_size,
            max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
        )

    try:
        processed_file = FileProcessor.process_file(
            file_bytes=content,
            filename=original_filename,
            max_size_mb=10,
        )
    except FileProcessingError as exc:
        _raise_upload_document_error(
            status_code=400,
            error_code="file_processing_failed",
            processing_stage="file_processing",
            message="Uploaded claim document could not be processed safely.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=source_mime_type,
            content_length=original_size,
            max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
            exception_type=type(exc).__name__,
        )

    if processed_file.processed_size > 10 * 1024 * 1024:
        _raise_upload_document_error(
            status_code=400,
            error_code="processed_file_too_large",
            processing_stage="file_processing",
            message="Uploaded claim document exceeds the 10 MB limit after processing.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=processed_file.file_type,
            content_length=original_size,
            max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
            processed_size_bytes=processed_file.processed_size,
        )

    text = ""
    ocr_result = None

    if processed_file.file_type == "application/pdf":
        try:
            from pypdf import PdfReader

            pdf_reader = PdfReader(BytesIO(processed_file.content))
            for page in pdf_reader.pages:
                text += (page.extract_text() or "") + "\n"
        except Exception as exc:
            _raise_upload_document_error(
                status_code=400,
                error_code="pdf_text_extraction_failed",
                processing_stage="text_extraction",
                message="Uploaded PDF text could not be extracted safely.",
                source_filename_present=source_filename_present,
                source_file_extension=source_file_extension,
                source_mime_type=processed_file.file_type,
                content_length=original_size,
                max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
                processed_size_bytes=processed_file.processed_size,
                exception_type=type(exc).__name__,
            )

        if len(text.strip()) < 25:
            try:
                ocr_result = await OcrService().extract_text_from_pdf_scan(
                    processed_file.content,
                    processed_file.processed_filename,
                )
                text = ocr_result.text
            except OcrServiceError as e:
                raise HTTPException(status_code=e.status_code, detail=e.to_detail())
    elif processed_file.file_type.startswith("image/"):
        try:
            ocr_result = await OcrService().extract_text_from_image_bytes(
                processed_file.content,
                processed_file.processed_filename,
            )
            text = ocr_result.text
        except OcrServiceError as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_detail())
    else:
        text = processed_file.content.decode("utf-8", errors="ignore")

    if not text.strip():
        _raise_upload_document_error(
            status_code=400,
            error_code="text_extraction_empty",
            processing_stage="text_extraction",
            message="Uploaded claim document did not yield extractable text.",
            source_filename_present=source_filename_present,
            source_file_extension=source_file_extension,
            source_mime_type=processed_file.file_type,
            content_length=original_size,
            max_upload_size_bytes=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES,
            processed_size_bytes=processed_file.processed_size,
            text_length=len(text.strip()),
        )

    inspection_metadata = {
        "processed_filename": processed_file.processed_filename,
        "file_type": processed_file.file_type,
        "original_size_bytes": original_size,
        "processed_size_bytes": processed_file.processed_size,
        "was_resized": processed_file.was_resized,
        "was_converted": processed_file.was_converted,
    }
    if ocr_result:
        inspection_metadata.update(ocr_result.metadata())
    upload_document_id = uuid.uuid4().hex[:12].upper()
    document_surface_inspection = _inspect_document_surfaces(
        source_id=f"UPLOAD-{upload_document_id}",
        document_id=f"UPLOAD-DOC-{upload_document_id}",
        source_filename=original_filename,
        source_mime_type=processed_file.file_type,
        visible_text=None if ocr_result else text,
        ocr_text=text if ocr_result else None,
        metadata=inspection_metadata,
    )

    service = DocumentAnalysisService(db)
    result = await service.analyze_document(document_text=text, document_type="denial_letter")
    denial_workflow = await _build_denial_workflow(
        document_text=text,
        document_type="denial_letter",
        source_document_id=f"uploaded_claim_document_{upload_document_id}",
        source_title="Uploaded claim document",
    )
    patient_id, provider_id = _get_or_create_document_defaults(db)

    ai_analysis = _parse_document_ai_analysis(
        result.analysis,
        processing_stage="upload_document_analysis_parse",
    )

    processing_info = {
        "source_filename_present": bool(original_filename),
        "source_file_extension": _source_file_extension(original_filename),
        "source_mime_type": processed_file.file_type,
        "original_size": format_file_size(original_size),
        "processed_size": format_file_size(processed_file.processed_size),
        "was_resized": processed_file.was_resized,
        "was_converted": processed_file.was_converted,
    }
    ocr_metadata = ocr_result.metadata() if ocr_result else None
    if ocr_metadata:
        processing_info["ocr"] = ocr_metadata

    claim = Claim(
        patient_id=patient_id,
        provider_id=provider_id,
        claim_data={
            "document_type": result.document_type,
            "amount": result.claim_amount or 0,
            "service_date": result.service_date,
            "ai_analysis": ai_analysis.get(
                "summary", result.analysis[:500] if result.analysis else ""
            ),
            "appeal_strategy": result.appeal_strategy
            or ai_analysis.get("estimated_success_rate", ""),
            "full_analysis": result.analysis,
            "denial_workflow": denial_workflow.model_dump(mode="json"),
            "processing_info": processing_info,
            "document_surface_inspection": document_surface_inspection.model_dump(
                mode="json"
            ),
        },
        diagnosis_codes=result.extracted_codes or [],
        procedure_codes=[],
        submission_date=datetime.utcnow(),
        status="draft",
        denial_prediction=0.5
        if ai_analysis.get("appeal_strength") == "moderate"
        else (0.3 if ai_analysis.get("appeal_strength") == "strong" else 0.7),
        denial_confidence=0.7,
        denial_reasons=[
            {
                "reason": result.denial_reason or "Document analyzed",
                "severity": "medium",
                "code": result.denial_code,
            }
        ],
        recommendations=[r.model_dump() for r in result.recommendations]
        if result.recommendations
        else [],
        document_text=text,
        document_filename=processed_file.processed_filename,
        document_access_scope=CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
        document_created_by_user_id=_current_user_id(current_user),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    log_audit(
        db=db,
        action="document_uploaded",
        user_id=_current_user_id(current_user),
        claim_id=claim.id,
        details={
            "source_filename_present": bool(original_filename),
            "source_file_extension": _source_file_extension(original_filename),
            "source_mime_type": processed_file.file_type,
            "original_size": original_size,
            "processed_size": processed_file.processed_size,
            "was_resized": processed_file.was_resized,
            "was_converted": processed_file.was_converted,
            "ocr_engine": ocr_metadata.get("engine") if ocr_metadata else None,
            "ocr_model": ocr_metadata.get("model") if ocr_metadata else None,
            "ocr_pages": ocr_metadata.get("pages") if ocr_metadata else None,
            "document_type": "denial_letter",
            "extracted_amount": result.claim_amount,
            "denial_code": result.denial_code,
            "access_scope": CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
            "surface_count": document_surface_inspection.surface_count,
            "surface_blocking_count": (
                document_surface_inspection.blocking_surface_count
            ),
            "surface_residual_risk_score": (
                document_surface_inspection.residual_risk_score
            ),
            "surface_deidentification_status": (
                document_surface_inspection.deidentification_status
            ),
        },
        ip_address=_request_ip(request),
    )

    return DocumentAnalysisResponse(
        claim_id=claim.id,
        document_type=result.document_type,
        payer_name=result.payer_name,
        denial_reason=result.denial_reason,
        denial_code=result.denial_code,
        claim_amount=result.claim_amount,
        service_date=result.service_date,
        patient_name=result.patient_name,
        policy_number=result.policy_number,
        extracted_codes=result.extracted_codes,
        analysis=result.analysis,
        recommendations=result.recommendations,
        appeal_strategy=result.appeal_strategy,
        denial_workflow=denial_workflow,
        ocr_engine=ocr_metadata.get("engine") if ocr_metadata else None,
        ocr_model=ocr_metadata.get("model") if ocr_metadata else None,
        ocr_pages=ocr_metadata.get("pages") if ocr_metadata else None,
        ocr_duration_ms=ocr_metadata.get("duration_ms") if ocr_metadata else None,
        ocr_warnings=ocr_metadata.get("warnings") if ocr_metadata else None,
        document_surface_inspection=document_surface_inspection,
        analyzed_at=result.analyzed_at,
    )


@router.post("/analyze-documents-batch", response_model=BatchDocumentAnalysisResponse)
async def analyze_documents_batch(
    request: BatchDocumentAnalysisRequest,
    http_request: Request = None,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    if len(request.documents) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 documents per batch")

    results = []
    successful = 0
    failed = 0

    for document_index, doc in enumerate(request.documents):
        raw_doc_text = doc.get("document_text", "")
        doc_text = raw_doc_text if isinstance(raw_doc_text, str) else ""
        if not doc_text or len(doc_text.strip()) < 10:
            _log_batch_document_analysis_failure(
                error_code="document_text_too_short",
                processing_stage="document_validation",
                document_index=document_index,
                document_text=raw_doc_text,
                document_type=request.document_type,
            )
            failed += 1
            continue

        try:
            service = DocumentAnalysisService(db)
            result = await service.analyze_document(
                document_text=doc_text, document_type=request.document_type
            )
            denial_workflow = await _build_denial_workflow(
                document_text=doc_text,
                document_type=request.document_type or "denial_letter",
                source_document_id=f"batch_document_{document_index + 1}",
                source_title=f"Batch document {document_index + 1}",
            )
            patient_id, provider_id = _get_or_create_document_defaults(db)

            ai_analysis = _parse_document_ai_analysis(
                result.analysis,
                processing_stage="batch_document_analysis_parse",
                fallback_summary="",
                plain_text_summary=False,
            )

            claim = Claim(
                patient_id=patient_id,
                provider_id=provider_id,
                claim_data={
                    "document_type": result.document_type,
                    "amount": result.claim_amount or 0,
                    "ai_analysis": ai_analysis.get("summary", ""),
                    "denial_workflow": denial_workflow.model_dump(mode="json"),
                    "batch": True,
                },
                diagnosis_codes=result.extracted_codes or [],
                procedure_codes=[],
                submission_date=datetime.utcnow(),
                status="draft",
                denial_prediction=0.5,
                denial_confidence=0.7,
                denial_reasons=[
                    {
                        "reason": result.denial_reason or "Document analyzed",
                        "severity": "medium",
                        "code": result.denial_code,
                    }
                ],
                recommendations=[r.model_dump() for r in result.recommendations]
                if result.recommendations
                else [],
                document_text=doc_text,
                document_filename=None,
                document_access_scope=CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
                document_created_by_user_id=_current_user_id(current_user),
            )
            db.add(claim)
            db.commit()
            db.refresh(claim)

            results.append(
                DocumentAnalysisResponse(
                    claim_id=claim.id,
                    document_type=result.document_type,
                    payer_name=result.payer_name,
                    denial_reason=result.denial_reason,
                    denial_code=result.denial_code,
                    claim_amount=result.claim_amount,
                    service_date=result.service_date,
                    patient_name=result.patient_name,
                    policy_number=result.policy_number,
                    extracted_codes=result.extracted_codes,
                    analysis=result.analysis,
                    recommendations=result.recommendations,
                    appeal_strategy=result.appeal_strategy,
                    denial_workflow=denial_workflow,
                    analyzed_at=result.analyzed_at,
                )
            )
            successful += 1
        except Exception as exc:
            _log_batch_document_analysis_failure(
                error_code="document_analysis_failed",
                processing_stage="document_analysis",
                document_index=document_index,
                document_text=doc_text,
                document_type=request.document_type,
                exception=exc,
            )
            failed += 1
            continue

    log_audit(
        db=db,
        action="documents_batch_analyzed",
        user_id=_current_user_id(current_user),
        details={
            "document_count": len(request.documents),
            "successful": successful,
            "failed": failed,
            "document_type": request.document_type,
            "access_scope": CLAIM_DOCUMENT_ACCESS_SCOPE_BILLING_TEAM,
        },
        ip_address=_request_ip(http_request),
    )

    return BatchDocumentAnalysisResponse(
        total=len(request.documents),
        successful=successful,
        failed=failed,
        results=results,
    )
