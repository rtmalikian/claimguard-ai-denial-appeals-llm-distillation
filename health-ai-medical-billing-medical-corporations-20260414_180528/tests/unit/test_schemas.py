import pytest
from datetime import datetime
from app.schemas.claim import (
    ClaimBase,
    ClaimCreate,
    ClaimPredictionRequest,
    ClaimPredictionResponse,
    ClaimSubmitRequest,
    ClaimSubmitResponse,
    ClaimResponse,
    DocumentAnalysisRequest,
    DocumentAnalysisResponse,
    Recommendation,
    DenialReason,
    BatchDocumentAnalysisRequest,
    BatchDocumentAnalysisResponse,
)


class TestClaimSchemas:
    def test_claim_base_defaults(self):
        claim = ClaimBase(
            patient_id=1,
            provider_id=2,
            claim_data={"amount": 1000},
        )

        assert claim.patient_id == 1
        assert claim.provider_id == 2
        assert claim.diagnosis_codes is None
        assert claim.procedure_codes is None

    def test_claim_create_with_codes(self):
        claim = ClaimCreate(
            patient_id=1,
            provider_id=2,
            claim_data={"amount": 500},
            diagnosis_codes=["Z00.00"],
            procedure_codes=["99213"],
        )

        assert len(claim.diagnosis_codes) == 1
        assert len(claim.procedure_codes) == 1

    def test_claim_prediction_request(self):
        request = ClaimPredictionRequest(
            patient_id=1,
            provider_id=2,
            claim_data={"service": "office"},
        )

        assert request.patient_id == 1

    def test_recommendation_schema(self):
        rec = Recommendation(
            action="Submit appeal",
            description="File formal appeal within 30 days",
            priority="high",
        )

        assert rec.action == "Submit appeal"
        assert rec.priority == "high"

    def test_denial_reason_schema(self):
        reason = DenialReason(
            reason="Missing documentation",
            severity="high",
            code="CO16",
        )

        assert reason.code == "CO16"
        assert reason.severity == "high"

    def test_denial_reason_optional_code(self):
        reason = DenialReason(
            reason="Unknown error",
            severity="medium",
        )

        assert reason.code is None

    def test_document_analysis_request_defaults(self):
        request = DocumentAnalysisRequest()

        assert request.document_text is None
        assert request.document_type == "denial_letter"

    def test_document_analysis_response(self):
        response = DocumentAnalysisResponse(
            document_type="denial_letter",
            payer_name="Aetna",
            denial_code="CO16",
            analysis="The denial is valid.",
            recommendations=[
                Recommendation(action="Test", description="Test desc", priority="high")
            ],
        )

        assert response.payer_name == "Aetna"
        assert response.denial_code == "CO16"
        assert len(response.recommendations) == 1

    def test_claim_submit_response(self):
        response = ClaimSubmitResponse(
            claim_id=1,
            status="pending",
            denial_prediction=0.75,
            denial_confidence=0.9,
            denial_reasons=[DenialReason(reason="Test", severity="high")],
            recommendations=[Recommendation(action="Test", description="Test", priority="high")],
            message="Claim submitted successfully",
        )

        assert response.claim_id == 1
        assert response.denial_prediction == 0.75

    def test_batch_document_analysis_request(self):
        request = BatchDocumentAnalysisRequest(
            documents=[
                {"text": "Document 1", "type": "denial_letter"},
                {"text": "Document 2", "type": "EOB"},
            ],
        )

        assert len(request.documents) == 2

    def test_batch_document_analysis_response(self):
        response = BatchDocumentAnalysisResponse(
            total=5,
            successful=4,
            failed=1,
            results=[],
        )

        assert response.total == 5
        assert response.successful == 4
        assert response.failed == 1

    def test_claim_response_from_attributes(self):
        response = ClaimResponse(
            id=1,
            patient_id=1,
            provider_id=2,
            claim_data={"amount": 100},
            status="submitted",
            created_at=datetime.utcnow(),
        )

        assert response.id == 1
        assert response.status == "submitted"
