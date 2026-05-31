import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.claim import ClaimPredictionRequest
from app.services.contract_rates import evaluate_contract_rates
from app.services.prediction import PredictionService


def test_service_line_contract_rate_finding_is_metadata_only():
    findings = evaluate_contract_rates(
        {
            "service_lines": [
                {
                    "procedure_code": "99213",
                    "billed_amount": "240.00",
                    "allowed_amount": "120.00",
                }
            ]
        },
        ["99213"],
    )

    assert len(findings) == 1
    finding = findings[0].to_dict()
    serialized = json.dumps(finding, sort_keys=True)

    assert finding["finding_type"] == "charge_exceeds_contract_rate"
    assert finding["severity"] == "high"
    assert finding["procedure_code"] == "99213"
    assert finding["ratio"] == 2.0
    assert finding["safe_context"]["raw_amount_values_included"] is False
    assert finding["safe_context"]["raw_claim_data_included"] is False
    assert finding["safe_context"]["explicit_contract_metadata_used"] is True
    assert "$" not in serialized
    assert "240.00" not in serialized
    assert "120.00" not in serialized


def test_root_contract_rate_finding_uses_first_structured_procedure_code():
    findings = evaluate_contract_rates(
        {
            "amount": 300,
            "contract_rate": 150,
        },
        ["97110"],
    )

    assert len(findings) == 1
    assert findings[0].finding_type == "charge_exceeds_contract_rate"
    assert findings[0].procedure_code == "97110"
    assert findings[0].ratio == 2.0


def test_charge_master_mismatch_uses_explicit_structured_metadata():
    findings = evaluate_contract_rates(
        {
            "service_lines": {
                "A0428": {
                    "billed_amount": 100,
                    "charge_master_rate": 180,
                }
            }
        },
        [],
    )

    assert len(findings) == 1
    assert findings[0].finding_type == "charge_master_mismatch"
    assert findings[0].procedure_code == "A0428"
    assert findings[0].safe_context["explicit_charge_master_metadata_used"] is True


def test_absent_explicit_rate_metadata_returns_no_findings():
    findings = evaluate_contract_rates(
        {
            "service_lines": [
                {
                    "procedure_code": "99213",
                    "billed_amount": 250,
                }
            ],
            "payer_name": "Synthetic Health Plan",
        },
        ["99213"],
    )

    assert findings == []


@pytest.mark.asyncio
async def test_prediction_includes_contract_rate_reason_without_raw_amounts():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    service = PredictionService(mock_db)
    service._analyze_with_ai = AsyncMock(return_value={"reasons": [], "recommendations": []})

    request = ClaimPredictionRequest(
        patient_id=1,
        provider_id=1,
        claim_data={
            "service_lines": [
                {
                    "procedure_code": "99213",
                    "billed_amount": 260,
                    "allowed_amount": 100,
                }
            ]
        },
        procedure_codes=["99213"],
    )

    prediction, confidence, reasons, recommendations = await service.predict_denial(request)
    serialized_reasons = json.dumps([reason.model_dump() for reason in reasons], sort_keys=True)

    assert prediction > 0
    assert confidence > 0
    assert any(reason.code == "CO-45" for reason in reasons)
    assert any("contract-rate check" in reason.reason for reason in reasons)
    assert any("contract rate" in rec.description for rec in recommendations)
    assert "$" not in serialized_reasons
    assert "260" not in serialized_reasons
    assert "100" not in serialized_reasons
