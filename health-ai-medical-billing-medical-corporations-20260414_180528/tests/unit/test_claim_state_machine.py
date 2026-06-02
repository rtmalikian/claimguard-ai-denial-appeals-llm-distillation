from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models import Claim
from app.schemas.claim import ClaimStatusUpdateRequest
from app.services.claim_state import (
    allowed_next_claim_statuses,
    is_canonical_claim_status,
    is_readable_claim_status,
    validate_claim_status_transition,
)


def test_claim_state_machine_allows_expected_forward_transitions():
    allowed, blockers = validate_claim_status_transition("submitted", "denied")

    assert allowed is True
    assert blockers == []
    assert "appealed" in allowed_next_claim_statuses("denied")
    assert is_canonical_claim_status("partially_paid") is True
    assert is_canonical_claim_status("in_review") is True

    allowed, blockers = validate_claim_status_transition("submitted", "accepted")
    assert allowed is True
    assert blockers == []

    allowed, blockers = validate_claim_status_transition("accepted", "in_review")
    assert allowed is True
    assert blockers == []

    allowed, blockers = validate_claim_status_transition("appealed", "appeal_approved")
    assert allowed is True
    assert blockers == []

    allowed, blockers = validate_claim_status_transition("appeal_denied", "timely_filing")
    assert allowed is True
    assert blockers == []


def test_claim_state_machine_blocks_terminal_and_unknown_statuses():
    allowed, blockers = validate_claim_status_transition("paid", "denied")

    assert allowed is False
    assert blockers == ["transition_not_allowed"]

    allowed, blockers = validate_claim_status_transition("submitted", "approved")

    assert allowed is False
    assert blockers == ["requested_status_is_not_canonical"]
    assert is_readable_claim_status("approved") is True
    assert is_readable_claim_status("accepted") is True


def test_claim_state_machine_treats_legacy_analyzed_as_draft_for_transition():
    allowed, blockers = validate_claim_status_transition("analyzed", "submitted")

    assert allowed is True
    assert blockers == []
    assert allowed_next_claim_statuses("analyzed") == (
        "pending",
        "scrubbing",
        "submitted",
        "write_off",
    )


@pytest.mark.asyncio
async def test_update_claim_status_allows_submitted_to_denied_and_logs_metadata_only():
    from app.api.v1.claims import update_claim_status

    claim = Claim(
        id=17,
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        status="submitted",
        submission_date=datetime.utcnow(),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = claim

    with patch("app.api.v1.claims.log_audit") as mock_log:
        result = await update_claim_status(
            claim_id=17,
            status_request=ClaimStatusUpdateRequest(
                status="denied",
                transition_reason="Synthetic operator note; not logged raw.",
            ),
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert result.claim_id == 17
    assert result.previous_status == "submitted"
    assert result.status == "denied"
    assert result.allowed_next_statuses == ["appealed", "timely_filing", "write_off"]
    assert claim.status == "denied"
    db.commit.assert_called_once()
    mock_log.assert_called_once()
    audit_details = mock_log.call_args.kwargs["details"]
    assert audit_details["previous_status"] == "submitted"
    assert audit_details["status"] == "denied"
    assert audit_details["transition_reason_present"] is True
    assert "Synthetic operator note" not in str(audit_details)


@pytest.mark.asyncio
async def test_update_claim_status_blocks_pending_to_paid_with_safe_error():
    from app.api.v1.claims import update_claim_status

    claim = Claim(
        id=18,
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        status="pending",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = claim

    with pytest.raises(HTTPException) as exc_info:
        await update_claim_status(
            claim_id=18,
            status_request=ClaimStatusUpdateRequest(status="paid"),
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 409
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_claim_status_transition"
    assert detail["current_status"] == "pending"
    assert detail["requested_status"] == "paid"
    assert detail["allowed_next_statuses"] == ["scrubbing", "submitted", "write_off"]
    assert detail["safe_context"]["raw_claim_data_included"] is False
    assert detail["safe_context"]["raw_transition_reason_included"] is False
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_claim_status_blocks_noncanonical_legacy_write_status():
    from app.api.v1.claims import update_claim_status

    claim = Claim(
        id=19,
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        status="submitted",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = claim

    with pytest.raises(HTTPException) as exc_info:
        await update_claim_status(
            claim_id=19,
            status_request=ClaimStatusUpdateRequest(status="approved"),
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_claim_status"
    assert "approved" in detail["readable_legacy_statuses"]
    assert "approved" not in detail["allowed_statuses"]
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_claim_status_allows_expanded_review_state_and_logs_safely():
    from app.api.v1.claims import update_claim_status

    claim = Claim(
        id=20,
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        status="accepted",
        submission_date=datetime.utcnow(),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = claim

    with patch("app.api.v1.claims.log_audit") as mock_log:
        result = await update_claim_status(
            claim_id=20,
            status_request=ClaimStatusUpdateRequest(
                status="in_review",
                transition_reason="Synthetic review queue note; not logged raw.",
            ),
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert result.claim_id == 20
    assert result.previous_status == "accepted"
    assert result.status == "in_review"
    assert result.allowed_next_statuses == [
        "denied",
        "paid",
        "partially_paid",
        "write_off",
    ]
    assert claim.status == "in_review"
    db.commit.assert_called_once()
    mock_log.assert_called_once()
    assert "Synthetic review queue note" not in str(mock_log.call_args.kwargs["details"])
