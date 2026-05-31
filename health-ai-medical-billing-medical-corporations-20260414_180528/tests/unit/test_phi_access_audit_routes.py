import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch


def _mock_request():
    request = MagicMock()
    request.headers = {}
    request.client.host = "127.0.0.1"
    return request


def test_get_claim_logs_metadata_only_access_event():
    from app.api.v1.claims import get_claim

    claim = MagicMock()
    claim.id = 77
    claim.patient_id = 10
    claim.provider_id = 20
    claim.claim_data = {"amount": 150}
    claim.status = "pending"
    claim.denial_prediction = None
    claim.denial_confidence = None
    claim.denial_reasons = None
    claim.recommendations = None
    claim.created_at = datetime.utcnow()
    claim.updated_at = None
    claim.diagnosis_codes = []
    claim.procedure_codes = []
    claim.submission_date = None
    claim.document_text = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = claim

    with patch("app.api.v1.claims.log_audit") as log_audit:
        result = asyncio.run(
            get_claim(
                claim_id=77,
                request=_mock_request(),
                current_user={"id": 3, "role": "billing_staff"},
                db=db,
            )
        )

    assert result.id == 77
    log_audit.assert_called_once()
    _, kwargs = log_audit.call_args
    assert kwargs["action"] == "claim_viewed"
    assert kwargs["user_id"] == 3
    assert kwargs["claim_id"] == 77
    assert kwargs["details"]["claim_id"] == 77
    assert "document_text" not in kwargs["details"]


def test_patient_mrn_lookup_logs_presence_not_raw_mrn():
    from app.api.v1.patients import get_patient_by_mrn

    patient = MagicMock()
    patient.id = 44
    patient.mrn = "SYNTH-MRN-0044"
    patient.first_name = "Synthetic"
    patient.last_name = "Patient"
    patient.date_of_birth = None
    patient.created_at = datetime.utcnow()

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = patient

    with patch("app.api.v1.patients.log_audit") as log_audit:
        result = asyncio.run(
            get_patient_by_mrn(
                mrn="SYNTH-MRN-0044",
                request=_mock_request(),
                current_user={"id": 9, "role": "admin"},
                db=db,
            )
        )

    assert result.id == 44
    log_audit.assert_called_once()
    _, kwargs = log_audit.call_args
    assert kwargs["action"] == "patient_viewed"
    assert kwargs["user_id"] == 9
    assert kwargs["details"] == {
        "patient_id": 44,
        "lookup": "mrn",
        "mrn_present": True,
    }
    assert "SYNTH-MRN-0044" not in str(kwargs["details"])
