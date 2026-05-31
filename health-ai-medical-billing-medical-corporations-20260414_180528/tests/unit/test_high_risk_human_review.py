from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("app.api.v1.claims.log_audit")
@patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
async def test_predict_denial_returns_human_review_gate_for_high_risk(
    mock_predict,
    mock_log_audit,
):
    from app.api.v1.claims import predict_denial
    from app.schemas.claim import ClaimPredictionRequest, DenialReason, Recommendation

    mock_db = MagicMock()
    mock_predict.return_value = (
        0.82,
        0.91,
        [DenialReason(reason="Synthetic authorization gap", severity="high")],
        [
            Recommendation(
                action="Review synthetic authorization packet",
                description="Confirm source evidence before any payer action.",
                priority="high",
            )
        ],
    )

    request = ClaimPredictionRequest(
        patient_id=101,
        provider_id=202,
        claim_data={"amount": 750, "service_date": "2026-01-15"},
    )

    result = await predict_denial(
        request=request,
        current_user={"id": 7, "role": "billing_staff"},
        db=mock_db,
    )

    assert result.human_review_required is True
    assert result.human_review_status == "required"
    assert result.human_review_reasons == [
        "high_denial_risk_score",
        "high_severity_denial_reason",
        "high_priority_recommendation",
    ]
    assert result.human_review_threshold == 0.5
    assert result.human_review_next_action == (
        "route_to_billing_reviewer_before_next_payer_action"
    )

    audit_details = mock_log_audit.call_args.kwargs["details"]
    assert audit_details["human_review_required"] is True
    assert audit_details["human_review_reason_count"] == 3
    assert audit_details["patient_id_present"] is True
    assert audit_details["provider_id_present"] is True
    assert "patient_id" not in audit_details
    assert "provider_id" not in audit_details
    assert audit_details["safe_context"]["raw_claim_data_included"] is False
    assert audit_details["safe_context"]["raw_reason_text_included"] is False


@pytest.mark.asyncio
@patch("app.api.v1.claims.log_audit")
@patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
async def test_submit_claim_high_risk_requires_human_review_before_next_action(
    mock_predict,
    mock_log_audit,
):
    from app.api.v1.claims import submit_claim
    from app.schemas.claim import ClaimSubmitRequest, DenialReason, Recommendation

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock(side_effect=lambda claim: setattr(claim, "id", 303))
    mock_predict.return_value = (
        0.67,
        0.88,
        [DenialReason(reason="Synthetic coding issue", severity="medium")],
        [
            Recommendation(
                action="Review synthetic modifier support",
                description="Connect recommendation to claim fields before payer action.",
                priority="high",
            )
        ],
    )

    request = ClaimSubmitRequest(
        patient_id=101,
        provider_id=202,
        claim_data={
            "amount": 750,
            "payer_name": "Synthetic Health Plan",
            "subscriber_id": "SYN-SUB-303",
            "service_date": "2026-01-15",
        },
        diagnosis_codes=["Z00.00"],
        procedure_codes=["99213"],
    )

    result = await submit_claim(
        request=request,
        current_user={"id": 7, "role": "billing_staff"},
        db=mock_db,
    )

    assert result.claim_id == 303
    assert result.status == "submitted"
    assert result.human_review_required is True
    assert result.human_review_status == "required"
    assert result.human_review_reasons == [
        "high_denial_risk_score",
        "high_priority_recommendation",
    ]
    assert "human review is required" in result.message

    audit_details = mock_log_audit.call_args.kwargs["details"]
    assert audit_details["human_review_required"] is True
    assert audit_details["human_review_status"] == "required"
    assert audit_details["human_review_reason_count"] == 2
    assert "patient_id" not in audit_details
    assert "provider_id" not in audit_details
    assert audit_details["safe_context"]["patient_identifier_included"] is False


def test_claim_response_computes_review_gate_for_high_risk_dashboard_rows():
    from app.api.v1.claims import _claim_response_for_user

    claim = MagicMock()
    claim.id = 404
    claim.patient_id = 101
    claim.provider_id = 202
    claim.claim_data = {"amount": 1200, "service_date": "2026-01-15"}
    claim.diagnosis_codes = ["Z00.00"]
    claim.procedure_codes = ["99213"]
    claim.submission_date = datetime.utcnow()
    claim.status = "submitted"
    claim.denial_prediction = 0.71
    claim.denial_confidence = 0.84
    claim.denial_reasons = [{"reason": "Synthetic support gap", "severity": "high"}]
    claim.recommendations = []
    claim.document_text = None
    claim.created_at = datetime.utcnow()
    claim.updated_at = None
    claim.patient = None

    response = _claim_response_for_user(claim, {"id": 7, "role": "billing_staff"})

    assert response.human_review_required is True
    assert response.human_review_status == "required"
    assert response.human_review_reasons == [
        "high_denial_risk_score",
        "high_severity_denial_reason",
    ]
