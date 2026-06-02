import pytest
from datetime import datetime
from app.models import Claim, AuditLog, Patient, Provider, DenialPattern


class TestClaimModel:
    def test_claim_creation(self):
        claim = Claim(
            id=1,
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 1000},
            status="submitted",
        )

        assert claim.id == 1
        assert claim.patient_id == 1
        assert claim.status == "submitted"

    def test_claim_creation_with_status(self):
        claim = Claim(
            patient_id=1,
            provider_id=1,
            claim_data={},
            status="pending",
        )

        assert claim.status == "pending"

    def test_claim_with_denial_info(self):
        claim = Claim(
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 500},
            status="denied",
            denial_prediction=0.85,
            denial_confidence=0.92,
            denial_reasons=[{"reason": "Missing info", "code": "CO16"}],
        )

        assert claim.status == "denied"
        assert claim.denial_prediction == 0.85
        assert claim.denial_confidence == 0.92

    def test_claim_with_document(self):
        claim = Claim(
            patient_id=1,
            provider_id=1,
            claim_data={},
            document_text="Original document text...",
            document_filename="denial_letter.pdf",
        )

        assert claim.document_text is not None
        assert claim.document_filename == "denial_letter.pdf"

    def test_claim_with_codes(self):
        claim = Claim(
            patient_id=1,
            provider_id=1,
            claim_data={},
            diagnosis_codes=["Z00.00"],
            procedure_codes=["99213"],
        )

        assert claim.diagnosis_codes == ["Z00.00"]
        assert claim.procedure_codes == ["99213"]

    def test_claim_soft_delete_metadata(self):
        deleted_at = datetime.utcnow()
        claim = Claim(
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 100},
            deleted_at=deleted_at,
            deleted_by_user_id=12,
            deletion_reason="synthetic retention review",
        )

        assert claim.deleted_at == deleted_at
        assert claim.deleted_by_user_id == 12
        assert claim.deletion_reason == "synthetic retention review"

    def test_claim_high_frequency_indexes(self):
        assert Claim.__table__.c.patient_id.index is True
        assert Claim.__table__.c.status.index is True
        assert Claim.__table__.c.submission_date.index is True
        assert Claim.__table__.c.denial_prediction.index is True


class TestAuditLogModel:
    def test_audit_log_creation(self):
        log = AuditLog(
            action="document_analyzed",
            user_id=1,
            details={"model": "qwen2.5"},
        )

        assert log.action == "document_analyzed"
        assert log.user_id == 1

    def test_audit_log_with_claim(self):
        log = AuditLog(
            action="claim_submitted",
            user_id=2,
            claim_id=5,
            details={"amount": 1000},
        )

        assert log.claim_id == 5

    def test_audit_log_with_ip(self):
        log = AuditLog(
            action="api_access",
            user_id=1,
            ip_address="10.0.0.1",
        )

        assert log.ip_address == "10.0.0.1"


class TestPatientModel:
    def test_patient_creation(self):
        patient = Patient(
            id=1,
            mrn="MRN-12345",
            demographics_encrypted="encrypted_data",
        )

        assert patient.mrn == "MRN-12345"
        assert patient.demographics_encrypted == "encrypted_data"

    def test_patient_soft_delete_metadata(self):
        deleted_at = datetime.utcnow()
        patient = Patient(
            id=1,
            mrn="MRN-12345",
            deleted_at=deleted_at,
            deleted_by_user_id=12,
            deletion_reason="synthetic retention review",
        )

        assert patient.deleted_at == deleted_at
        assert patient.deleted_by_user_id == 12
        assert patient.deletion_reason == "synthetic retention review"

    def test_patient_mrn_index(self):
        assert Patient.__table__.c.mrn.index is True


class TestProviderModel:
    def test_provider_creation(self):
        provider = Provider(
            id=1,
            npi="1234567893",
            name="Dr. Smith",
            specialty="Internal Medicine",
        )

        assert provider.npi == "1234567893"
        assert provider.name == "Dr. Smith"
        assert provider.specialty == "Internal Medicine"

    def test_provider_rejects_invalid_npi_check_digit(self):
        with pytest.raises(ValueError) as exc_info:
            Provider(
                id=1,
                npi="1234567890",
                name="Dr. Smith",
                specialty="Internal Medicine",
            )

        assert str(exc_info.value) == "provider_npi_failed_check_digit_validation"

    def test_provider_normalizes_npi_spacing(self):
        provider = Provider(
            id=1,
            npi=" 123 456 7893 ",
            name="Dr. Smith",
            specialty="Internal Medicine",
        )

        assert provider.npi == "1234567893"


class TestDenialPatternModel:
    def test_denial_pattern_creation(self):
        pattern = DenialPattern(
            icd_code="Z00.00",
            cpt_code="99213",
            payer_id="BCBS",
            denial_rate=0.35,
            common_reasons=["Missing documentation", "Coding error"],
        )

        assert pattern.icd_code == "Z00.00"
        assert pattern.cpt_code == "99213"
        assert pattern.denial_rate == 0.35
        assert len(pattern.common_reasons) == 2

    def test_denial_pattern_with_values(self):
        pattern = DenialPattern(
            icd_code="Z00.00",
            denial_rate=0.0,
        )

        assert pattern.denial_rate == 0.0
        assert pattern.icd_code == "Z00.00"
