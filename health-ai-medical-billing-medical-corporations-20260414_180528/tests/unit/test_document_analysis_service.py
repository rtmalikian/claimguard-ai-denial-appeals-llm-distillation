import pytest
from unittest.mock import MagicMock, patch
from app.services.document_analysis import DocumentAnalysisService


class TestDocumentAnalysisBuildPrompt:
    def test_build_analysis_prompt(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "This is a denial letter for claim #123."
        extracted = {
            "payer_name": "Blue Cross",
            "denial_code": "CO16",
        }

        prompt = service._build_analysis_prompt(text, extracted)

        assert "denial letter" in prompt.lower()
        assert "Blue Cross" in prompt
        assert "CO16" in prompt
        assert len(prompt) > 100

    def test_build_analysis_prompt_truncates_long_text(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        long_text = "x" * 3000
        extracted = {}

        prompt = service._build_analysis_prompt(long_text, extracted)

        assert len(prompt) < len(long_text) * 3


class TestDocumentAnalysisEdgeCases:
    def test_empty_extracted_fields(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        prompt = service._build_analysis_prompt("Short text", {})

        assert "Short text" in prompt

    def test_all_extracted_fields(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Denial letter"
        extracted = {
            "payer_name": "Aetna",
            "denial_reason": "Missing info",
            "denial_code": "CO29",
            "claim_amount": 1500.0,
            "service_date": "01/15/2024",
            "patient_name": "John Doe",
            "policy_number": "ABC-123",
            "procedure_codes": ["99213"],
        }

        prompt = service._build_analysis_prompt(text, extracted)

        assert "Aetna" in prompt
        assert "CO29" in prompt
        assert "1500" in prompt


class TestDocumentAnalysisServiceInit:
    def test_service_initialization(self):
        mock_db = MagicMock()

        service = DocumentAnalysisService(mock_db)

        assert service.db == mock_db
        assert hasattr(service, "llm")


class TestDocumentAnalysisServiceClassVariables:
    def test_model_not_loaded_initially(self):
        assert DocumentAnalysisService._model_loaded is False
        assert DocumentAnalysisService._model_load_attempted is False

    def test_class_variables_accessible(self):
        assert hasattr(DocumentAnalysisService, "_model_loaded")
        assert hasattr(DocumentAnalysisService, "_model_load_attempted")
