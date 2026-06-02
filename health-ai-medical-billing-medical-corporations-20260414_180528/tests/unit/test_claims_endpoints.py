import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from fastapi import HTTPException


class TestListClaimsEndpoint:
    def test_list_claims_basic(self):
        from app.schemas.claim import ClaimResponse

        claim = ClaimResponse(
            id=1,
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 1000},
            status="pending",
            created_at=datetime.utcnow(),
        )

        assert claim.id == 1
        assert claim.patient_id == 1
        assert claim.status == "pending"

    def test_claim_response_model(self):
        from app.schemas.claim import ClaimResponse

        response = ClaimResponse(
            id=2,
            patient_id=1,
            provider_id=1,
            claim_data={"amount": 500},
            status="submitted",
            denial_prediction=0.5,
            created_at=datetime.utcnow(),
        )

        assert response.denial_prediction == 0.5
        assert response.status == "submitted"


class TestGetClaimEndpoint:
    @patch("app.api.v1.claims.get_db")
    def test_get_claim_found(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.patient_id = 1
        claim.provider_id = 1
        claim.claim_data = {"amount": 1000}
        claim.status = "pending"
        claim.denial_prediction = None
        claim.denial_confidence = None
        claim.denial_reasons = None
        claim.recommendations = None
        claim.created_at = datetime.utcnow()
        claim.updated_at = None
        claim.diagnosis_codes = None
        claim.procedure_codes = None
        claim.submission_date = None

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        from app.api.v1.claims import get_claim
        import asyncio

        result = asyncio.run(get_claim(claim_id=1, db=mock_db))

        assert result.id == 1

    @patch("app.api.v1.claims.get_db")
    def test_get_claim_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value = mock_db

        from app.api.v1.claims import get_claim
        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_claim(claim_id=999, db=mock_db))

        assert exc_info.value.status_code == 404


class TestGetClaimDocumentEndpoint:
    @patch("app.api.v1.claims.get_db")
    def test_get_claim_document(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.document_text = "Original denial letter text..."
        claim.document_filename = "denial.pdf"

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        from app.api.v1.claims import get_claim_document
        import asyncio

        result = asyncio.run(get_claim_document(claim_id=1, db=mock_db))

        assert result["claim_id"] == 1
        assert result["document_text"] == "Original denial letter text..."
        assert result["filename"] == "denial.pdf"

    @patch("app.api.v1.claims.get_db")
    def test_get_claim_document_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value = mock_db

        from app.api.v1.claims import get_claim_document
        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_claim_document(claim_id=999, db=mock_db))

        assert exc_info.value.status_code == 404

    @patch("app.api.v1.claims.get_db")
    def test_get_claim_document_no_document(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.document_text = None

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        from app.api.v1.claims import get_claim_document
        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_claim_document(claim_id=1, db=mock_db))

        assert exc_info.value.status_code == 404


class TestSubmitClaimEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.get_db")
    @patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
    async def test_submit_claim_low_risk(self, mock_predict, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_predict.return_value = (0.2, 0.8, [], [])

        mock_claim_instance = MagicMock()
        mock_claim_instance.id = 1
        mock_claim_instance.status = "submitted"
        mock_claim_instance.denial_prediction = 0.2
        mock_claim_instance.denial_confidence = 0.8
        mock_claim_instance.denial_reasons = []
        mock_claim_instance.recommendations = []

        def add_side_effect(claim):
            claim.id = 1

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=add_side_effect)

        from app.api.v1.claims import submit_claim
        from app.schemas.claim import ClaimSubmitRequest

        request = ClaimSubmitRequest(
            patient_id=1,
            provider_id=1,
            claim_data={
                "amount": 1000,
                "payer_name": "Synthetic Health Plan",
                "subscriber_id": "SYN-SUB-001",
                "service_date": "2026-01-15",
                "place_of_service_code": "11",
            },
        )

        result = await submit_claim(request=request, db=mock_db)

        assert result.status == "submitted"


class TestAnalyzeDocumentValidation:
    def test_analyze_document_empty_text(self):
        from app.schemas.claim import DocumentAnalysisRequest
        from fastapi import HTTPException

        doc_request = DocumentAnalysisRequest(document_text="")

        with pytest.raises(HTTPException) as exc_info:
            if not doc_request.document_text or not doc_request.document_text.strip():
                raise HTTPException(status_code=400, detail="Document text is required")

        assert exc_info.value.status_code == 400

    def test_analyze_document_short_text(self):
        from app.schemas.claim import DocumentAnalysisRequest
        from fastapi import HTTPException

        doc_request = DocumentAnalysisRequest(document_text="Short")

        with pytest.raises(HTTPException) as exc_info:
            if len(doc_request.document_text.strip()) < 10:
                raise HTTPException(status_code=400, detail="Document text is too short")

        assert exc_info.value.status_code == 400


class TestDocumentSurfaceInspection:
    def test_upload_surface_inspection_returns_metadata_without_values(self):
        from app.api.v1.claims import _inspect_document_surfaces

        result = _inspect_document_surfaces(
            source_id="UPLOAD-SYNTHETIC",
            document_id="UPLOAD-DOC-SYNTHETIC",
            source_filename="synthetic-member-id-denial.txt",
            source_mime_type="text/plain",
            visible_text=(
                "Synthetic uploaded denial. Member ID: SYN-MEMBER-UPLOAD. "
                "Claim Number: SYN-CLAIM-UPLOAD. Appeal review is needed."
            ),
            metadata={
                "processed_filename": "synthetic-member-id-denial.txt",
                "processed_size_bytes": 128,
            },
        )
        payload = result.model_dump_json()

        assert result.surface_count >= 3
        assert result.blocking_surface_count >= 2
        assert result.values_redacted is True
        assert {surface.surface for surface in result.surface_scans} >= {
            "source_filename",
            "visible_text",
            "metadata",
        }
        assert "SYN-MEMBER-UPLOAD" not in payload
        assert "SYN-CLAIM-UPLOAD" not in payload

    def test_document_analysis_response_accepts_surface_inspection(self):
        from app.api.v1.claims import _inspect_document_surfaces
        from app.schemas.claim import DocumentAnalysisResponse

        inspection = _inspect_document_surfaces(
            source_id="UPLOAD-SYNTHETIC-CLEAN",
            document_id="UPLOAD-DOC-SYNTHETIC-CLEAN",
            source_filename="synthetic-denial.txt",
            source_mime_type="text/plain",
            visible_text=(
                "Synthetic uploaded denial without identifier labels. "
                "Appeal review remains source grounded."
            ),
        )

        response = DocumentAnalysisResponse(
            document_type="denial_letter",
            analysis="Synthetic analysis.",
            recommendations=[],
            document_surface_inspection=inspection,
        )

        assert response.document_surface_inspection is not None
        assert response.document_surface_inspection.values_redacted is True


class TestBatchAnalyzeDocumentsValidation:
    def test_batch_analyze_exceeds_limit(self):
        from app.schemas.claim import BatchDocumentAnalysisRequest
        from fastapi import HTTPException

        documents = [{"document_text": f"Document {i} with enough text"} for i in range(25)]
        request = BatchDocumentAnalysisRequest(documents=documents)

        with pytest.raises(HTTPException) as exc_info:
            if len(request.documents) > 20:
                raise HTTPException(status_code=400, detail="Maximum 20 documents per batch")

        assert exc_info.value.status_code == 400
        assert "20" in str(exc_info.value.detail)


class TestUploadDocumentValidation:
    def test_upload_file_too_large(self):
        from fastapi import HTTPException

        file_size = 20 * 1024 * 1024

        with pytest.raises(HTTPException) as exc_info:
            if file_size > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

        assert exc_info.value.status_code == 400
        assert "10MB" in str(exc_info.value.detail)
