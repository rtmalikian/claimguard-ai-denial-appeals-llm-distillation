from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.prediction import PredictionService, CircuitBreaker
from app.schemas.claim import ClaimPredictionRequest


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        assert cb.state == "closed"
        assert cb.failures == 0

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_func():
            raise Exception("Test error")

        with pytest.raises(Exception):
            cb.call(failing_func)
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "open"

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        cb.failures = 1

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.failures == 0

    def test_open_circuit_uses_total_elapsed_seconds_after_day_boundary(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=60)
        cb.state = "open"
        cb.failures = 1
        cb.last_failure_time = datetime.utcnow() - timedelta(days=1, seconds=1)

        def success_func():
            return "recovered"

        result = cb.call(success_func)

        assert result == "recovered"
        assert cb.state == "closed"
        assert cb.failures == 0


class TestPredictionService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def sample_request(self):
        return ClaimPredictionRequest(
            patient_id=1,
            provider_id=1,
            claim_data={"service_date": "2024-01-01", "amount": 1000},
            diagnosis_codes=["Z00.00"],
            procedure_codes=["99213"],
        )

    @pytest.mark.asyncio
    async def test_predict_denial_returns_tuple(self, mock_db, sample_request):
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = PredictionService(mock_db)
        service.llm = MagicMock()
        service.llm.generate = AsyncMock(return_value='{"reasons": [], "recommendations": []}')

        result = await service.predict_denial(sample_request)

        assert len(result) == 4
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)
        assert isinstance(result[2], list)
        assert isinstance(result[3], list)

    @pytest.mark.asyncio
    async def test_denials_with_high_risk_patterns(self, mock_db, sample_request):
        mock_pattern = MagicMock()
        mock_pattern.icd_code = "Z00.00"
        mock_pattern.cpt_code = "99213"
        mock_pattern.denial_rate = 0.7
        mock_pattern.common_reasons = ["Missing documentation", "Invalid ICD-10"]

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_pattern]
        mock_db.query.return_value = mock_query

        service = PredictionService(mock_db)
        service.llm = MagicMock()
        service.llm.generate = AsyncMock(return_value='{"reasons": [], "recommendations": []}')

        prediction, confidence, reasons, recommendations = await service.predict_denial(
            sample_request
        )

        assert prediction > 0
        assert len(reasons) > 0
        assert reasons[0].driver_category == "diagnosis_procedure_pattern"
        assert reasons[0].source_field == "diagnosis_codes_or_procedure_codes"
        metadata = service.build_prediction_metadata(
            sample_request,
            reasons,
            recommendations,
        )
        assert metadata["threshold"]["high_risk_threshold"] == 0.5
        assert metadata["fairness"]["demographic_parity_metric_available"] is True
        assert "diagnosis_procedure_pattern" in metadata["explainability"][
            "feature_driver_categories"
        ]
        assert "documentation_gap" in metadata["explainability"][
            "feature_driver_categories"
        ]
