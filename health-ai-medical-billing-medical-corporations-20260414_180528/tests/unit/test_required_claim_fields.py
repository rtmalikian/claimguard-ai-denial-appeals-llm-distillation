from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def test_required_claim_field_validator_accepts_complete_synthetic_metadata():
    from app.api.v1.claims import validate_required_claim_submission_fields

    issues = validate_required_claim_submission_fields(
        {
            "payer": {"name": "Synthetic Health Plan"},
            "subscriber": {"id": "SYN-SUB-001"},
            "service_date": "2026-01-15",
        }
    )

    assert issues == []


def test_required_claim_field_validator_returns_safe_missing_metadata_issues():
    from app.api.v1.claims import validate_required_claim_submission_fields

    issues = validate_required_claim_submission_fields({"amount": 250})
    details = [issue.safe_detail() for issue in issues]

    assert [issue.error_code for issue in issues] == [
        "missing_payer_metadata",
        "missing_subscriber_metadata",
        "missing_service_date_metadata",
    ]
    assert details[0]["safe_context"]["raw_claim_data_included"] is False
    assert "250" not in str(details)


def test_required_claim_field_validator_rejects_invalid_service_date_safely():
    from app.api.v1.claims import validate_required_claim_submission_fields

    issues = validate_required_claim_submission_fields(
        {
            "payer_name": "Synthetic Health Plan",
            "subscriber_id": "SYN-SUB-001",
            "service_date": "not-a-date",
        }
    )

    assert [issue.error_code for issue in issues] == ["invalid_service_date_metadata"]
    assert "not-a-date" not in str([issue.safe_detail() for issue in issues])


def test_claim_data_value_validator_rejects_negative_amounts_safely():
    from app.api.v1.claims import validate_claim_data_values

    issues = validate_claim_data_values(
        {
            "amount": "-250.00",
            "service_lines": [{"charge_amount": -125}],
        }
    )
    details = [issue.safe_detail() for issue in issues]

    assert [issue.error_code for issue in issues] == [
        "negative_claim_amount_metadata",
        "negative_claim_amount_metadata",
    ]
    assert details[0]["field_path"] == "amount"
    assert details[1]["field_path"] == "service_lines[0].charge_amount"
    assert details[0]["safe_context"]["raw_claim_data_included"] is False
    assert "-250" not in str(details)
    assert "-125" not in str(details)


def test_diagnosis_procedure_linkage_requires_diagnosis_support_safely():
    from app.api.v1.claims import validate_diagnosis_procedure_linkage

    issues = validate_diagnosis_procedure_linkage(
        diagnosis_codes=[],
        procedure_codes=["99213"],
        claim_data={},
    )
    details = [issue.safe_detail() for issue in issues]

    assert [issue.error_code for issue in issues] == [
        "missing_diagnosis_codes_for_procedure_linkage"
    ]
    assert details[0]["field"] == "diagnosis_codes"
    assert details[0]["safe_context"]["raw_code_values_included"] is False
    assert "99213" not in str(details)


def test_diagnosis_procedure_linkage_rejects_invalid_pointer_safely():
    from app.api.v1.claims import validate_diagnosis_procedure_linkage

    issues = validate_diagnosis_procedure_linkage(
        diagnosis_codes=["Z00.00"],
        procedure_codes=["99213"],
        claim_data={"service_lines": [{"diagnosis_pointers": ["not-a-pointer"]}]},
    )
    details = [issue.safe_detail() for issue in issues]

    assert [issue.error_code for issue in issues] == [
        "invalid_diagnosis_pointer_format"
    ]
    assert details[0]["field_path"] == "service_lines[0].diagnosis_pointers"
    assert details[0]["safe_context"]["clinical_medical_necessity_asserted"] is False
    assert "not-a-pointer" not in str(details)


@pytest.mark.asyncio
@patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
async def test_submit_claim_blocks_missing_required_metadata_before_prediction(mock_predict):
    from app.api.v1.claims import submit_claim
    from app.schemas.claim import ClaimSubmitRequest

    db = MagicMock()
    request = ClaimSubmitRequest(
        patient_id=1,
        provider_id=1,
        claim_data={"amount": 250},
        diagnosis_codes=["Z00.00"],
        procedure_codes=["99213"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_claim(
            request=request,
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "missing_required_claim_fields"
    assert detail["issue_count"] == 3
    assert detail["safe_context"]["raw_claim_data_included"] is False
    assert "250" not in str(detail)
    mock_predict.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
async def test_predict_denial_blocks_negative_amount_before_prediction(mock_predict):
    from app.api.v1.claims import predict_denial
    from app.schemas.claim import ClaimPredictionRequest

    db = MagicMock()
    request = ClaimPredictionRequest(
        patient_id=1,
        provider_id=1,
        claim_data={
            "payer_name": "Synthetic Health Plan",
            "subscriber_id": "SYN-SUB-001",
            "service_date": "2026-01-15",
            "amount": -250,
        },
        diagnosis_codes=["Z00.00"],
        procedure_codes=["99213"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await predict_denial(
            request=request,
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_claim_data_values"
    assert detail["issues"][0]["field"] == "amount"
    assert detail["issues"][0]["safe_context"]["raw_field_value_included"] is False
    assert "-250" not in str(detail)
    mock_predict.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
async def test_predict_denial_blocks_missing_diagnosis_linkage_before_prediction(mock_predict):
    from app.api.v1.claims import predict_denial
    from app.schemas.claim import ClaimPredictionRequest

    db = MagicMock()
    request = ClaimPredictionRequest(
        patient_id=1,
        provider_id=1,
        claim_data={
            "payer_name": "Synthetic Health Plan",
            "subscriber_id": "SYN-SUB-001",
            "service_date": "2026-01-15",
        },
        diagnosis_codes=[],
        procedure_codes=["99213"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await predict_denial(
            request=request,
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_diagnosis_procedure_linkage"
    assert detail["issues"][0]["error_code"] == "missing_diagnosis_codes_for_procedure_linkage"
    assert detail["safe_context"]["clinical_medical_necessity_asserted"] is False
    assert "99213" not in str(detail)
    mock_predict.assert_not_called()
