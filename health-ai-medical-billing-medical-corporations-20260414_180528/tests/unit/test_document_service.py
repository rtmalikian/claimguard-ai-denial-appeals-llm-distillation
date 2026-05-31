import pytest
from app.services.document_analysis import DocumentAnalysisService


class TestRecommendationExtraction:
    def test_recommendations_with_denial_code(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = "The claim was denied due to missing documentation."
        extracted = {"denial_code": "CO16"}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) >= 1
        assert any(
            "denial code" in r.action.lower() or "code" in r.action.lower() for r in recommendations
        )

    def test_recommendations_with_procedure_codes(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = "Standard analysis completed."
        extracted = {"procedure_codes": ["99214", "99215"]}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) >= 1
        assert any(
            "coding" in r.action.lower() or "procedure" in r.action.lower() for r in recommendations
        )

    def test_recommendations_medical_necessity(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = "The claim involves medical necessity determination."
        extracted = {}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert any("medical necessity" in r.action.lower() for r in recommendations)

    def test_recommendations_limit(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = "Medical necessity and coding issues identified."
        extracted = {"denial_code": "CO16", "procedure_codes": ["99214"]}

        recommendations = service._extract_recommendations(ai_analysis, extracted)

        assert len(recommendations) <= 5


class TestAppealStrategy:
    def test_appeal_strategy_co16(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = ""
        extracted = {"denial_code": "CO16"}

        strategy = service._generate_appeal_strategy(ai_analysis, extracted)

        assert "medical records" in strategy.lower() or "medical necessity" in strategy.lower()

    def test_appeal_strategy_co29(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = ""
        extracted = {"denial_code": "CO29"}

        strategy = service._generate_appeal_strategy(ai_analysis, extracted)

        assert "eligibility" in strategy.lower() or "coverage" in strategy.lower()

    def test_appeal_strategy_medical_necessity(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = ""
        extracted = {"denial_reason": "Medical necessity not established"}

        strategy = service._generate_appeal_strategy(ai_analysis, extracted)

        assert "medical necessity" in strategy.lower()

    def test_appeal_strategy_default(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        ai_analysis = ""
        extracted = {}

        strategy = service._generate_appeal_strategy(ai_analysis, extracted)

        assert len(strategy) > 0


class TestFieldExtractionEdgeCases:
    def test_extract_date_formats(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        result = service._extract_fields("Service Date: 01/15/2024")
        assert result.get("service_date") == "01/15/2024"

        result = service._extract_fields("Date of Service: 1-15-24")
        assert result.get("service_date") == "1-15-24"

    def test_extract_procedure_code_format(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        result = service._extract_fields("CPT: 99214")
        assert "99214" in result.get("procedure_codes", [])

    def test_extract_group_number(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        result = service._extract_fields("Group: ABC-12345-XYZ")
        assert result.get("policy_number") == "ABC-12345-XYZ"

    def test_extract_multiple_procedure_codes(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "CPT: 99214 CPT: 99215"
        result = service._extract_fields(text)

        assert len(result.get("procedure_codes", [])) >= 1
