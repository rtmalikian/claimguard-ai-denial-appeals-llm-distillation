"""
Audit logging utility for HIPAA compliance.
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any

from app.models import AuditLog
from app.utils.phi import scan_text_for_phi


SENSITIVE_AUDIT_DETAIL_KEYS = {
    "access_token",
    "address",
    "analysis",
    "api_key",
    "appeal_letter",
    "attachment_filename",
    "attachment_filenames",
    "authorization_number",
    "auth_number",
    "content",
    "date_of_birth",
    "deletion_reason",
    "dob",
    "document_content",
    "document_text",
    "email",
    "filename",
    "first_name",
    "full_analysis",
    "full_name",
    "hidden_text",
    "last_name",
    "member_id",
    "member_name",
    "mrn",
    "ocr_text",
    "original_filename",
    "password",
    "patient_name",
    "phone",
    "policy_id",
    "policy_number",
    "processed_filename",
    "prompt",
    "raw_text",
    "response",
    "secret",
    "social_security_number",
    "source_document_id",
    "source_filename",
    "ssn",
    "subscriber_id",
    "token",
    "visible_text",
}


def _redacted_value_summary(value: Any, finding_count: int = 0) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "redacted": True,
        "value_present": value not in (None, "", [], {}),
    }
    if isinstance(value, str):
        summary["character_count"] = len(value)
    elif isinstance(value, dict):
        summary["field_count"] = len(value)
    elif isinstance(value, (list, tuple, set)):
        summary["item_count"] = len(value)
    if finding_count:
        summary["phi_finding_count"] = finding_count
    return summary


def _audit_key_is_sensitive(key: str) -> bool:
    return key.lower().replace("-", "_") in SENSITIVE_AUDIT_DETAIL_KEYS


def _sanitize_audit_value(key: str, value: Any) -> Any:
    if _audit_key_is_sensitive(key):
        finding_count = 0
        if isinstance(value, str):
            finding_count = len(scan_text_for_phi(value))
        return _redacted_value_summary(value, finding_count=finding_count)

    if isinstance(value, dict):
        return sanitize_audit_details(value)
    if isinstance(value, list):
        return [_sanitize_audit_value("", item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_audit_value("", item) for item in value]
    if isinstance(value, str):
        findings = scan_text_for_phi(value)
        if findings:
            return _redacted_value_summary(value, finding_count=len(findings))
    return value


def sanitize_audit_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return audit metadata with raw PHI/PII-like values stripped."""
    if not isinstance(details, dict):
        return {}
    return {str(key): _sanitize_audit_value(str(key), value) for key, value in details.items()}


def log_audit(
    db: Session,
    action: str,
    claim_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Actions:
    - document_analyzed: A document was analyzed
    - document_uploaded: A document was uploaded
    - claim_created: A claim was created
    - claim_viewed: A claim was viewed
    - document_viewed: Original document was viewed
    - api_access: General API access
    """
    audit_log = AuditLog(
        user_id=user_id,
        claim_id=claim_id,
        action=action,
        details=sanitize_audit_details(details),
        ip_address=ip_address,
        timestamp=datetime.utcnow(),
    )
    db.add(audit_log)
    db.commit()
    return audit_log
