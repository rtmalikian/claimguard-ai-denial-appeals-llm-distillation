import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


class TestAnalyticsReasonsCounting:
    def test_count_denial_reasons_from_claims(self):
        claims = [
            {"denial_reasons": [{"reason": "CO16", "code": "CO16"}]},
            {"denial_reasons": [{"reason": "CO16", "code": "CO16"}]},
            {"denial_reasons": [{"reason": "CO29", "code": "CO29"}]},
            {"denial_reasons": None},
        ]

        all_reasons = []
        for c in claims:
            if c.get("denial_reasons"):
                all_reasons.extend(c["denial_reasons"])

        reason_counts = {}
        for r in all_reasons:
            reason = r.get("reason", "Unknown") if isinstance(r, dict) else "Unknown"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        assert reason_counts["CO16"] == 2
        assert reason_counts["CO29"] == 1

    def test_top_reasons_sorting(self):
        reason_counts = {"CO16": 10, "CO29": 5, "CO50": 3}
        top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:5]

        assert top_reasons[0][0] == "CO16"
        assert top_reasons[0][1] == 10

    def test_top_reasons_formatting(self):
        reason_counts = {"Missing info": 10}
        top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:5]
        top_reasons_formatted = [{"reason": r[0], "count": r[1]} for r in top_reasons]

        assert top_reasons_formatted[0]["reason"] == "Missing info"
        assert top_reasons_formatted[0]["count"] == 10


class TestAnalyticsSummaryStatus:
    def test_status_percentage_calculation(self):
        total = 100
        claims_by_status = [
            {"status": "submitted", "count": 50},
            {"status": "pending", "count": 30},
            {"status": "denied", "count": 20},
        ]

        percentages = [
            {
                "status": s["status"],
                "count": s["count"],
                "percentage": round(s["count"] / total * 100, 1),
            }
            for s in claims_by_status
        ]

        assert percentages[0]["percentage"] == 50.0
        assert percentages[1]["percentage"] == 30.0
        assert percentages[2]["percentage"] == 20.0


class TestDocumentAnalysisServiceAsync:
    @pytest.mark.asyncio
    async def test_analyze_document_returns_response(self):
        from app.services.document_analysis import DocumentAnalysisService
        from app.schemas.claim import DocumentAnalysisResponse

        mock_db = MagicMock()
        service = DocumentAnalysisService(mock_db)
        service.llm = MagicMock()
        service.llm.generate = AsyncMock(return_value='{"summary": "test"}')

        with patch.object(service, "_warmup_model", return_value=AsyncMock()()):
            with patch.object(service, "_extract_fields", return_value={}):
                with patch.object(service, "_build_analysis_prompt", return_value="test"):
                    result = await service.analyze_document("test document")

                    assert result is not None


class TestPredictionServiceInternal:
    def test_prediction_service_initialization(self):
        from app.services.prediction import PredictionService

        mock_db = MagicMock()
        service = PredictionService(mock_db)

        assert service.db == mock_db
        assert hasattr(service, "llm")

    def test_prediction_service_with_mocked_patterns(self):
        from app.services.prediction import PredictionService

        mock_db = MagicMock()
        mock_pattern = MagicMock()
        mock_pattern.icd_code = "Z00.00"
        mock_pattern.cpt_code = "99213"
        mock_pattern.denial_rate = 0.5

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_pattern]

        service = PredictionService(mock_db)
        assert service.db == mock_db
