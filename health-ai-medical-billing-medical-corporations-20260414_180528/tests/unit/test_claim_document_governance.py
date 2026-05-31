import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.claims import (
    _claim_response_for_user,
    claim_document_audit_dashboard,
    get_claim_document,
    retire_claim_document,
)
from app.models import AuditLog, Claim
from app.schemas.claim import ClaimDocumentDeleteRequest


def _claim(**overrides) -> Claim:
    values = {
        "id": 7,
        "patient_id": 1,
        "provider_id": 1,
        "claim_data": {"amount": 100},
        "status": "analyzed",
        "document_text": "Synthetic denial document text for governance testing.",
        "document_filename": "synthetic-denial.txt",
        "document_access_scope": "billing_team",
        "document_created_by_user_id": 22,
        "created_at": datetime.utcnow(),
    }
    values.update(overrides)
    return Claim(**values)


def test_claim_response_redacts_legacy_document_text_for_list_and_detail_views():
    claim = _claim()

    viewer_response = _claim_response_for_user(claim, {"id": 33, "role": "viewer"})
    billing_response = _claim_response_for_user(claim, {"id": 44, "role": "billing_staff"})

    assert viewer_response.document_text is None
    assert viewer_response.document_filename is None
    assert viewer_response.document_available is False
    assert viewer_response.document_governance is not None
    assert viewer_response.document_governance.can_view_document is False
    assert billing_response.document_text is None
    assert billing_response.document_filename == "synthetic-denial.txt"
    assert billing_response.document_available is True


def test_get_claim_document_blocks_viewer_from_billing_team_document():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = _claim()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_claim_document(
                claim_id=7,
                current_user={"id": 33, "role": "viewer"},
                db=mock_db,
            )
        )

    assert exc_info.value.status_code == 403


def test_get_claim_document_blocks_expired_retention_window():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = _claim(
        document_retention_until=datetime.utcnow() - timedelta(days=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_claim_document(
                claim_id=7,
                current_user={"id": 1, "role": "admin"},
                db=mock_db,
            )
        )

    assert exc_info.value.status_code == 410


def test_retire_claim_document_sets_soft_delete_metadata():
    mock_db = MagicMock()
    claim = _claim()
    mock_db.query.return_value.filter.return_value.first.return_value = claim

    result = asyncio.run(
        retire_claim_document(
            claim_id=7,
            delete_request=ClaimDocumentDeleteRequest(
                deletion_reason="synthetic privacy review"
            ),
            current_user={"id": 1, "role": "admin"},
            db=mock_db,
        )
    )

    assert result.deleted is True
    assert claim.document_deleted_at is not None
    assert claim.document_deleted_by_user_id == 1
    assert claim.document_deletion_reason == "synthetic privacy review"
    assert mock_db.commit.called


def test_claim_document_audit_dashboard_returns_safe_metadata_only():
    mock_db = MagicMock()
    audit_log = AuditLog(
        id=12,
        action="document_uploaded",
        claim_id=7,
        user_id=1,
        timestamp=datetime.utcnow(),
        details={
            "filename": "synthetic-denial.txt",
            "document_text": "do not surface document text",
            "source_file_extension": ".txt",
            "surface_count": 3,
        },
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        audit_log
    ]

    result = asyncio.run(
        claim_document_audit_dashboard(
            claim_id=None,
            limit=100,
            current_user={"id": 1, "role": "admin"},
            db=mock_db,
        )
    )

    assert result.event_count == 1
    assert result.events[0].details == {
        "source_file_extension": ".txt",
        "surface_count": 3,
    }
