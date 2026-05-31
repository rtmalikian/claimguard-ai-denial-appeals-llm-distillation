import pytest
from unittest.mock import MagicMock
from app.api.v1.appeals import generate_fallback_letter


class TestAppealFallback:
    def test_generate_fallback_letter(self):
        mock_claim = MagicMock()
        mock_claim.id = 123
        mock_claim.denial_reasons = [{"code": "CO16", "reason": "Missing information"}]
        mock_claim.claim_data = {"amount": 1500.00, "service_date": "2024-01-15"}

        letter, evidence = generate_fallback_letter(
            mock_claim, "Service was medically necessary", "Prior authorization was obtained"
        )

        assert "CLM-000123" in letter
        assert "CO16" in letter
        assert "$1,500.00" in letter
        assert "Service was medically necessary" in letter
        assert isinstance(evidence, list)
        assert len(evidence) > 0

    def test_generate_fallback_letter_no_denial(self):
        mock_claim = MagicMock()
        mock_claim.id = 456
        mock_claim.denial_reasons = []
        mock_claim.claim_data = {}

        letter, evidence = generate_fallback_letter(mock_claim, "Appealing for coverage review", "")

        assert "CLM-000456" in letter
        assert "Not specified" in letter

    def test_evidence_contains_required_items(self):
        mock_claim = MagicMock()
        mock_claim.id = 1
        mock_claim.denial_reasons = []
        mock_claim.claim_data = {}

        _, evidence = generate_fallback_letter(mock_claim, "Test", "")

        assert "Medical records and clinical notes" in evidence
        assert "Physician's treatment plan" in evidence
        assert "Prior authorization documentation" in evidence

    def test_generate_fallback_letter_all_codes(self):
        mock_claim = MagicMock()
        mock_claim.id = 789
        mock_claim.denial_reasons = [{"code": "CO29", "reason": "Patient eligibility"}]
        mock_claim.claim_data = {"amount": 2000.00, "service_date": "2024-02-20"}

        letter, _ = generate_fallback_letter(
            mock_claim, "Eligibility verified", "Coverage confirmed"
        )

        assert "CO29" in letter
        assert "Patient eligibility" in letter
        assert "$2,000.00" in letter
