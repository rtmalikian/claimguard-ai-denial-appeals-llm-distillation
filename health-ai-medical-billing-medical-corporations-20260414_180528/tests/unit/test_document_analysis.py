import pytest
from app.services.document_analysis import DocumentAnalysisService


class TestFieldExtraction:
    def test_extract_payer_name(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Payer: Blue Cross Blue Shield"
        result = service._extract_fields(text)
        assert result.get("payer_name") == "Blue Cross Blue Shield"

    def test_extract_denial_code(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Denial Code: CO16"
        result = service._extract_fields(text)
        assert result.get("denial_code") == "CO16"

    def test_extract_claim_amount(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Amount: $250.00"
        result = service._extract_fields(text)
        assert result.get("claim_amount") == 250.0

    def test_extract_patient_name(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Patient: John Smith"
        result = service._extract_fields(text)
        assert result.get("patient_name") == "John Smith"

    def test_extract_policy_number(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Policy: BCB-9876543"
        result = service._extract_fields(text)
        assert result.get("policy_number") == "BCB-9876543"

    def test_extract_generated_synthetic_denial_fields_without_placeholder_identity(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = """
        Training synthetic corpus pair PAIR-SYN-LARGE-0001.

        Aster Health Plan
        Synthetic adverse benefit determination
        Case reference SYN-CASE-0001
        Coverage reference SYN-COVERAGE-0017

        Administrative context: Synthetic member placeholder [PATIENT_0001];
        provider group Northgate Surgical Center; service window 2026-Q1; service
        reviewed home health skilled nursing visit; procedure code G0299; billed
        amount $612.00.
        Determination rationale: required documentation was missing or incomplete.
        """
        result = service._extract_fields(text)

        assert result.get("payer_name") == "Aster Health Plan"
        assert result.get("denial_reason") == "required documentation was missing or incomplete."
        assert result.get("claim_amount") == 612.0
        assert "G0299" in result.get("procedure_codes", [])
        assert "patient_name" not in result
        assert "policy_number" not in result

    def test_extract_procedure_code(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "CPT: 99214"
        result = service._extract_fields(text)
        assert "99214" in result.get("procedure_codes", [])

    def test_extract_multiple_fields(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = """
        Insurance: Aetna
        Denial Code: CO29
        Amount: $500.00
        Patient: Jane Doe
        Policy: AET-12345
        """
        result = service._extract_fields(text)

        assert result.get("payer_name") == "Aetna"
        assert result.get("denial_code") == "CO29"
        assert result.get("claim_amount") == 500.0
        assert result.get("patient_name") == "Jane Doe"
        assert result.get("policy_number") == "AET-12345"

    def test_extract_no_matches(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "This is just some random text without any claim data"
        result = service._extract_fields(text)

        assert result == {}


class TestEdgeCases:
    def test_empty_text(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        result = service._extract_fields("")
        assert result == {}

    def test_whitespace_only(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        result = service._extract_fields("   \n\t  ")
        assert result == {}

    def test_case_insensitive(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "DENIAL CODE: co16"
        result = service._extract_fields(text)
        assert result.get("denial_code") == "co16"

    def test_special_characters_in_amount(self):
        service = DocumentAnalysisService.__new__(DocumentAnalysisService)

        text = "Amount: $1,234.56"
        result = service._extract_fields(text)
        assert result.get("claim_amount") == 1234.56
