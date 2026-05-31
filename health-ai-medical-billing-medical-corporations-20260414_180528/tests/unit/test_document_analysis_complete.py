import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestDocumentAnalysisServiceWarmup:
    @pytest.mark.asyncio
    async def test_warmup_model(self):
        mock_db = MagicMock()

        with patch(
            "app.services.document_analysis.DocumentAnalysisService._model_load_attempted", False
        ):
            with patch(
                "app.services.document_analysis.DocumentAnalysisService._model_loaded", False
            ):
                from app.services.document_analysis import DocumentAnalysisService

                service = DocumentAnalysisService(mock_db)
                service.base_url = "http://localhost:11434"
                service.model = "qwen2.5:1.5b"
                service.timeout = 30

                await service._warmup_model()


class TestDocumentAnalysisFieldExtraction:
    def test_extract_fields_with_payer(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Payer: Blue Cross Blue Shield"
        result = service._extract_fields(text)

        assert result.get("payer_name") == "Blue Cross Blue Shield"

    def test_extract_fields_with_denial_code(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Denial Code: CO16"
        result = service._extract_fields(text)

        assert result.get("denial_code") == "CO16"

    def test_extract_fields_with_amount(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Amount: $500.00"
        result = service._extract_fields(text)

        assert result.get("claim_amount") == 500.0

    def test_extract_fields_with_patient(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Patient: John Doe"
        result = service._extract_fields(text)

        assert result.get("patient_name") == "John Doe"

    def test_extract_fields_case_insensitive(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "DENIAL CODE: co29"
        result = service._extract_fields(text)

        assert result.get("denial_code") == "co29"


class TestDocumentAnalysisBuildPrompt:
    def test_build_prompt_with_extracted(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "This is a denial letter."
        extracted = {"payer_name": "Aetna", "denial_code": "CO16", "claim_amount": 1000.0}

        prompt = service._build_analysis_prompt(text, extracted)

        assert "denial letter" in prompt.lower()
        assert "Aetna" in prompt
        assert "CO16" in prompt

    def test_build_prompt_truncates_long_text(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        long_text = "x" * 5000
        extracted = {}

        prompt = service._build_analysis_prompt(long_text, extracted)

        assert len(prompt) < 3000


class TestDocumentAnalysisRecommendations:
    def test_extract_recommendations_with_denial_code(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        ai_analysis = "Standard analysis"
        extracted = {"denial_code": "CO16"}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) >= 1

    def test_extract_recommendations_with_procedure_codes(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        ai_analysis = "Standard analysis"
        extracted = {"procedure_codes": ["99213"]}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) >= 1

    def test_extract_recommendations_medical_necessity(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        ai_analysis = "Medical necessity issue identified"
        extracted = {}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert any("medical necessity" in r.action.lower() for r in recommendations)

    def test_extract_recommendations_max_count(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        ai_analysis = "Medical necessity and coding issues found"
        extracted = {"denial_code": "CO16", "procedure_codes": ["99213"]}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) <= 5


class TestDocumentAnalysisAppealStrategy:
    def test_strategy_co16(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        extracted = {"denial_code": "CO16"}
        strategy = service._generate_appeal_strategy("", extracted)

        assert "medical" in strategy.lower()

    def test_strategy_co29(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        extracted = {"denial_code": "CO29"}
        strategy = service._generate_appeal_strategy("", extracted)

        assert len(strategy) > 0

    def test_strategy_medical_necessity(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        extracted = {"denial_reason": "Medical necessity not established"}
        strategy = service._generate_appeal_strategy("", extracted)

        assert "medical necessity" in strategy.lower()

    def test_strategy_default(self):
        from app.services.document_analysis import DocumentAnalysisService

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        extracted = {}
        strategy = service._generate_appeal_strategy("", extracted)

        assert len(strategy) > 0
