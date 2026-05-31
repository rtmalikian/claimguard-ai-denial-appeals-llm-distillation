import pytest
from unittest.mock import MagicMock, patch
from datetime import date


class TestPatientSchemas:
    def test_patient_create(self):
        from app.schemas.claim import PatientCreate

        patient = PatientCreate(
            mrn="MRN-001", first_name="John", last_name="Doe", date_of_birth=date(1990, 1, 15)
        )

        assert patient.mrn == "MRN-001"
        assert patient.first_name == "John"
        assert patient.last_name == "Doe"
        assert patient.date_of_birth == date(1990, 1, 15)

    def test_patient_create_optional_fields(self):
        from app.schemas.claim import PatientCreate

        patient = PatientCreate(mrn="MRN-002")

        assert patient.mrn == "MRN-002"
        assert patient.first_name is None
        assert patient.last_name is None
        assert patient.date_of_birth is None

    def test_patient_response(self):
        from app.schemas.claim import PatientResponse
        from datetime import datetime

        patient = PatientResponse(
            id=1,
            mrn="MRN-001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 15),
            created_at=datetime.utcnow(),
        )

        assert patient.id == 1
        assert patient.mrn == "MRN-001"


class TestPatientModel:
    def test_patient_creation(self):
        from app.models import Patient

        patient = Patient(
            id=1,
            mrn="MRN-12345",
            first_name="Jane",
            last_name="Smith",
            date_of_birth=date(1985, 6, 20),
        )

        assert patient.mrn == "MRN-12345"
        assert patient.first_name == "Jane"
        assert patient.last_name == "Smith"
        assert patient.date_of_birth == date(1985, 6, 20)

    def test_patient_with_minimal_data(self):
        from app.models import Patient

        patient = Patient(mrn="MRN-67890")

        assert patient.mrn == "MRN-67890"
        assert patient.first_name is None


class TestClaimSearchParameters:
    def test_claim_response_with_patient(self):
        from app.schemas.claim import ClaimResponse
        from datetime import datetime

        claim = ClaimResponse(
            id=1,
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 1000},
            status="pending",
            created_at=datetime.utcnow(),
            patient={
                "id": 1,
                "mrn": "MRN-001",
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": date(1990, 1, 15),
                "created_at": datetime.utcnow(),
            },
        )

        assert claim.id == 1
        assert claim.patient is not None


class TestDateParsing:
    def test_date_from_string(self):
        dob_str = "1990-01-15"
        parsed_date = date.fromisoformat(dob_str)

        assert parsed_date == date(1990, 1, 15)

    def test_date_formatting(self):
        dob = date(1990, 1, 15)
        formatted = dob.isoformat()

        assert formatted == "1990-01-15"
