import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestAppealsEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.v1.appeals.llm_service.generate", new_callable=AsyncMock)
    @patch("app.api.v1.appeals.get_db")
    async def test_generate_appeal_with_llm(self, mock_get_db, mock_generate):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.claim_data = {"amount": 1000, "service_date": "2024-01-15"}
        claim.diagnosis_codes = []
        claim.procedure_codes = []
        claim.denial_reasons = [{"code": "CO16", "reason": "Missing info"}]
        claim.denial_prediction = 0.5

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        mock_generate.return_value = (
            '{"appeal_letter": "Test appeal letter", "supporting_evidence": ["evidence1"]}'
        )

        from app.api.v1.appeals import generate_appeal
        from app.schemas.analytics import AppealGenerateRequest

        request = AppealGenerateRequest(claim_id=1, appeal_reason="Service was medically necessary")

        result = await generate_appeal(request=request, db=mock_db)

        assert result.claim_id == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.appeals.get_db")
    async def test_generate_appeal_fallback(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.claim_data = {"amount": 1000, "service_date": "2024-01-15"}
        claim.diagnosis_codes = []
        claim.procedure_codes = []
        claim.denial_reasons = []
        claim.denial_prediction = 0.5

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        from app.api.v1.appeals import generate_appeal
        from app.schemas.analytics import AppealGenerateRequest

        request = AppealGenerateRequest(claim_id=1, appeal_reason="Service was medically necessary")

        with patch(
            "app.api.v1.appeals.llm_service.generate",
            side_effect=Exception("NVIDIA unavailable"),
        ):
            result = await generate_appeal(request=request, db=mock_db)

        assert result.claim_id == 1
        assert "CLM-000001" in result.appeal_letter

    @pytest.mark.asyncio
    @patch("app.api.v1.appeals.get_db")
    async def test_generate_appeal_claim_not_found(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value = mock_db

        from app.api.v1.appeals import generate_appeal
        from app.schemas.analytics import AppealGenerateRequest
        from fastapi import HTTPException

        request = AppealGenerateRequest(claim_id=999, appeal_reason="Test")

        with pytest.raises(HTTPException) as exc_info:
            await generate_appeal(request=request, db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.appeals.get_db")
    async def test_generate_appeal_invalid_json(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.claim_data = {"amount": 1000}
        claim.diagnosis_codes = []
        claim.procedure_codes = []
        claim.denial_reasons = []
        claim.denial_prediction = 0.5

        mock_db.query.return_value.filter.return_value.first.return_value = claim
        mock_get_db.return_value = mock_db

        from app.api.v1.appeals import generate_appeal
        from app.schemas.analytics import AppealGenerateRequest

        request = AppealGenerateRequest(claim_id=1, appeal_reason="Test")

        with patch(
            "app.api.v1.appeals.llm_service.generate", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = "This is not JSON output"

            result = await generate_appeal(request=request, db=mock_db)

        assert result.claim_id == 1
        assert "CLM-000001" in result.appeal_letter


class TestGenerateFallbackLetter:
    def test_fallback_letter_structure(self):
        mock_claim = MagicMock()
        mock_claim.id = 123
        mock_claim.denial_reasons = [{"code": "CO16", "reason": "Missing info"}]
        mock_claim.claim_data = {"amount": 1500.00, "service_date": "2024-01-15"}

        from app.api.v1.appeals import generate_fallback_letter

        letter, evidence = generate_fallback_letter(
            mock_claim, "Service was medically necessary", "Prior authorization obtained"
        )

        assert "CLM-000123" in letter
        assert "CO16" in letter
        assert "$1,500.00" in letter
        assert "Service was medically necessary" in letter
        assert "Prior authorization obtained" in letter
        assert len(evidence) > 0

    def test_fallback_letter_no_denial_reasons(self):
        mock_claim = MagicMock()
        mock_claim.id = 456
        mock_claim.denial_reasons = []
        mock_claim.claim_data = {}

        from app.api.v1.appeals import generate_fallback_letter

        letter, _ = generate_fallback_letter(mock_claim, "Appealing for coverage review", "")

        assert "CLM-000456" in letter
        assert "Not specified" in letter

    def test_fallback_letter_empty_context(self):
        mock_claim = MagicMock()
        mock_claim.id = 789
        mock_claim.denial_reasons = [{"code": "CO29"}]
        mock_claim.claim_data = {"amount": 2000.00}

        from app.api.v1.appeals import generate_fallback_letter

        letter, _ = generate_fallback_letter(mock_claim, "Requesting review", "")

        assert "CLM-000789" in letter
        assert "CO29" in letter
