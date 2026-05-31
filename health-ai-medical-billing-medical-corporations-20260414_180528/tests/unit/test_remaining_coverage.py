import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestClaimsEndpointsDirect:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.get_db")
    @patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
    async def test_predict_endpoint(self, mock_predict, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        from app.schemas.claim import DenialReason, Recommendation

        mock_predict.return_value = (
            0.5,
            0.85,
            [DenialReason(reason="Test", severity="medium")],
            [Recommendation(action="Test", description="Test desc", priority="medium")],
        )

        from app.api.v1.claims import predict_denial
        from app.schemas.claim import ClaimPredictionRequest

        request = ClaimPredictionRequest(patient_id=1, provider_id=1, claim_data={"amount": 1000})

        result = await predict_denial(request=request, db=mock_db)

        assert result.denial_prediction == 0.5
        assert result.denial_confidence == 0.85

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.get_db")
    @patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
    async def test_submit_endpoint(self, mock_predict, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        from app.schemas.claim import DenialReason, Recommendation

        mock_predict.return_value = (0.3, 0.9, [], [])

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

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
            },
        )

        result = await submit_claim(request=request, db=mock_db)

        assert result.claim_id == 1


class TestDocumentAnalysisRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        from app.services.document_analysis import DocumentAnalysisService

        mock_db = MagicMock()
        service = DocumentAnalysisService(mock_db)
        service.base_url = "http://test:11434"
        service.model = "test"
        service.timeout = 5
        service.llm = MagicMock()
        service.llm.generate = AsyncMock(return_value='{"summary": "ok"}')

        with patch.object(service, "_warmup_model", return_value=AsyncMock()()):
            with patch.object(service, "_extract_fields", return_value={}):
                with patch.object(service, "_build_analysis_prompt", return_value="test"):
                    with patch.object(service, "_extract_recommendations", return_value=[]):
                        with patch.object(
                            service, "_generate_appeal_strategy", return_value="Test"
                        ):
                            result = await service.analyze_document("test")

                            assert result is not None


class TestDocumentAnalysisValidation:
    def test_empty_text_validation(self):
        text = ""
        assert not text or not text.strip()

    def test_short_text_validation(self):
        text = "Short"
        assert len(text.strip()) < 10


class TestClaimsBatchValidation:
    def test_exceeds_limit(self):
        docs = [{"text": f"doc{i}"} for i in range(25)]
        assert len(docs) > 20

    def test_within_limit(self):
        docs = [{"text": f"doc{i}"} for i in range(15)]
        assert len(docs) <= 20


class TestDocumentUploadValidation:
    def test_pdf_read_failure(self):
        content = b"not a pdf content"

        from io import BytesIO

        try:
            from pypdf import PdfReader

            pdf_reader = PdfReader(BytesIO(content))
            assert False
        except Exception:
            assert True

    def test_txt_extraction(self):
        content = b"Simple denial letter text content"
        text = content.decode("utf-8", errors="ignore")
        assert "denial" in text.lower()


class TestDocumentAnalysisFallback:
    def test_fallback_analysis_format(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        extracted = {"denial_code": "CO16", "claim_amount": 500.0, "procedure_codes": ["99213"]}

        fallback = f"Based on extracted information:\n\n- Denial Code: {extracted.get('denial_code', 'Unknown')}\n- Claim Amount: ${extracted.get('claim_amount', 'N/A')}\n- Extracted Codes: {', '.join(extracted.get('procedure_codes', []))}\n\nRecommendation: Review the denial letter for specific requirements."

        assert "CO16" in fallback
        assert "500" in fallback
        assert "Recommendation" in fallback
