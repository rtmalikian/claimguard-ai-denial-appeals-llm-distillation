from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.claim import ClaimPredictionRequest, ClaimSubmitRequest
from app.utils.healthcare_codes import (
    is_valid_claim_frequency_code,
    is_valid_carc_group_code,
    is_valid_carc_reason_code,
    is_valid_cpt_hcpcs_code,
    is_valid_icd10_code,
    is_valid_ndc_code,
    is_valid_npi,
    is_valid_place_of_service_code,
    is_valid_rarc_code,
    is_valid_revenue_code,
    lookup_carc_reason_code_status,
    lookup_rarc_code_status,
    validate_administrative_claim_codes,
    validate_claim_billing_codes,
)


def test_healthcare_code_format_validators_accept_common_synthetic_codes():
    assert is_valid_npi("1234567893") is True
    assert is_valid_icd10_code("Z00.00") is True
    assert is_valid_icd10_code("E119") is True
    assert is_valid_cpt_hcpcs_code("99213") is True
    assert is_valid_cpt_hcpcs_code("G0299") is True
    assert is_valid_carc_group_code("CO") is True
    assert is_valid_carc_reason_code("16") is True
    assert is_valid_rarc_code("N123") is True
    assert is_valid_place_of_service_code("11") is True
    assert is_valid_ndc_code("12345-6789-01") is True
    assert is_valid_ndc_code("N412345678901") is True
    assert is_valid_claim_frequency_code("1") is True
    assert is_valid_revenue_code("0450") is True


def test_healthcare_code_format_validators_reject_bad_formats():
    assert is_valid_npi("1234567890") is False
    assert is_valid_icd10_code("12345") is False
    assert is_valid_cpt_hcpcs_code("ABCDE") is False
    assert is_valid_carc_group_code("ZZ") is False
    assert is_valid_carc_reason_code("AB") is False
    assert is_valid_rarc_code("X123") is False
    assert is_valid_place_of_service_code("30") is False
    assert is_valid_ndc_code("N4ABC") is False
    assert is_valid_ndc_code("123456789") is False
    assert is_valid_claim_frequency_code("9") is False
    assert is_valid_revenue_code("45A") is False


def test_carc_rarc_seed_database_returns_safe_lifecycle_metadata():
    from app.utils.carc_rarc_database import load_carc_rarc_code_database

    database = load_carc_rarc_code_database()
    summary = database.summary()

    assert summary["carc_seed_count"] >= 50
    assert summary["rarc_seed_count"] >= 20
    assert summary["official_descriptions_included"] is False
    assert summary["comprehensive_code_list"] is False
    assert database.carc_reason_codes["P12"].status == "active"
    assert database.carc_reason_codes["D4"].status == "inactive"
    assert database.rarc_codes["MA38"].status == "inactive"


def test_carc_reason_code_lifecycle_lookup_accepts_active_and_unknown_safe_codes():
    active_lookup = lookup_carc_reason_code_status("P12")
    unknown_lookup = lookup_carc_reason_code_status("Z999")

    assert is_valid_carc_reason_code("P12") is True
    assert active_lookup.status == "active"
    assert active_lookup.category == "workers_comp_fee_schedule"
    assert active_lookup.safe_metadata()["raw_code_value_included"] is False
    assert is_valid_carc_reason_code("Z999") is True
    assert unknown_lookup.status == "format_valid_unconfirmed"
    assert unknown_lookup.record_found is False


def test_carc_reason_code_lifecycle_lookup_rejects_inactive_seed_codes():
    lookup = lookup_carc_reason_code_status("D4")

    assert is_valid_carc_reason_code("D4") is False
    assert lookup.status == "inactive"
    assert lookup.category == "missing_information"
    assert lookup.replacement == "16_with_remark"
    assert "D4" not in str(lookup.safe_metadata())


def test_rarc_lifecycle_lookup_accepts_active_and_rejects_inactive_seed_codes():
    active_lookup = lookup_rarc_code_status("M20")
    inactive_lookup = lookup_rarc_code_status("MA38")
    unconfirmed_lookup = lookup_rarc_code_status("N123")

    assert is_valid_rarc_code("M20") is True
    assert active_lookup.status == "active"
    assert active_lookup.category == "procedure_code_metadata"
    assert is_valid_rarc_code("N123") is True
    assert unconfirmed_lookup.status == "format_valid_unconfirmed"
    assert is_valid_rarc_code("MA38") is False
    assert inactive_lookup.status == "inactive"
    assert inactive_lookup.safe_metadata()["raw_code_value_included"] is False


def test_claim_billing_code_validation_returns_safe_issue_metadata():
    issues = validate_claim_billing_codes(
        diagnosis_codes=["Z00.00", "not-a-code"],
        procedure_codes=["99213", "bad-code"],
    )

    assert [issue.error_code for issue in issues] == [
        "invalid_icd10_code",
        "invalid_cpt_hcpcs_code",
    ]
    issue_detail = issues[0].safe_detail()
    assert issue_detail["field"] == "diagnosis_codes"
    assert issue_detail["index"] == 1
    assert issue_detail["safe_context"]["raw_code_value_included"] is False
    assert "not-a-code" not in str(issue_detail)


def test_administrative_code_validation_returns_safe_issue_metadata():
    issues = validate_administrative_claim_codes(
        place_of_service_codes=["11", "30"],
        ndc_codes=["12345-6789-01", "N4ABC"],
        claim_frequency_codes=["1", "9"],
        revenue_codes=["0450", "45A"],
    )

    assert [issue.error_code for issue in issues] == [
        "invalid_place_of_service_code",
        "invalid_ndc_code",
        "invalid_claim_frequency_code",
        "invalid_revenue_code",
    ]
    serialized = str([issue.safe_detail() for issue in issues])
    assert "30" not in serialized
    assert "N4ABC" not in serialized
    assert "45A" not in serialized
    assert all(
        issue.safe_detail()["safe_context"]["raw_code_value_included"] is False
        for issue in issues
    )


@pytest.mark.asyncio
async def test_predict_denial_blocks_invalid_claim_codes_before_prediction():
    from app.api.v1.claims import predict_denial

    request = ClaimPredictionRequest(
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        diagnosis_codes=["BAD"],
        procedure_codes=["99213"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await predict_denial(
            request=request,
            current_user={"id": 42, "role": "billing_staff"},
            db=MagicMock(),
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_healthcare_codes"
    assert detail["issue_count"] == 1
    assert detail["issues"][0]["error_code"] == "invalid_icd10_code"
    assert detail["safe_context"]["raw_code_values_included"] is False
    assert "BAD" not in str(detail)


@pytest.mark.asyncio
async def test_submit_claim_blocks_invalid_claim_codes_before_commit():
    from app.api.v1.claims import submit_claim

    db = MagicMock()
    request = ClaimSubmitRequest(
        patient_id=1,
        provider_id=1,
        claim_data={"synthetic": True},
        diagnosis_codes=["Z00.00"],
        procedure_codes=["ABCDE"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_claim(
            request=request,
            current_user={"id": 42, "role": "billing_staff"},
            db=db,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["error_code"] == "invalid_healthcare_codes"
    assert detail["issues"][0]["error_code"] == "invalid_cpt_hcpcs_code"
    assert detail["safe_context"]["raw_claim_data_included"] is False
    db.add.assert_not_called()
    db.commit.assert_not_called()
