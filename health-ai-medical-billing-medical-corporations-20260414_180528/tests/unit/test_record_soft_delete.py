import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from app.api.v1.claims import _active_claims_query, delete_claim, restore_claim
from app.api.v1.patients import _active_patients_query
from app.models import Claim


def test_active_patient_query_filters_soft_deleted_records():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = "filtered-patients"

    result = _active_patients_query(mock_db)

    assert result == "filtered-patients"
    assert mock_query.filter.called


def test_active_claim_query_filters_soft_deleted_records():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = "filtered-claims"

    result = _active_claims_query(mock_db)

    assert result == "filtered-claims"
    assert mock_query.filter.called


def test_delete_claim_sets_soft_delete_metadata():
    mock_db = MagicMock()
    claim = Claim(
        id=7,
        patient_id=1,
        provider_id=1,
        claim_data={"amount": 100},
        status="pending",
        document_text="Synthetic denial document.",
        created_at=datetime.utcnow(),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = claim

    asyncio.run(
        delete_claim(
            claim_id=7,
            current_user={"id": 12, "role": "admin"},
            db=mock_db,
        )
    )

    assert claim.deleted_at is not None
    assert claim.deleted_by_user_id == 12
    assert claim.deletion_reason == "operator_requested_retention_or_privacy_review"
    assert mock_db.commit.called


def test_restore_claim_clears_soft_delete_metadata():
    deleted_at = datetime.utcnow()
    mock_db = MagicMock()
    claim = Claim(
        id=7,
        patient_id=1,
        provider_id=1,
        claim_data={"amount": 100},
        status="pending",
        deleted_at=deleted_at,
        deleted_by_user_id=12,
        deletion_reason="synthetic retention review",
        created_at=datetime.utcnow(),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = claim

    result = asyncio.run(
        restore_claim(
            claim_id=7,
            current_user={"id": 12, "role": "admin"},
            db=mock_db,
        )
    )

    assert result.deleted_at is None
    assert claim.deleted_at is None
    assert claim.deleted_by_user_id is None
    assert claim.deletion_reason is None
    assert mock_db.commit.called
