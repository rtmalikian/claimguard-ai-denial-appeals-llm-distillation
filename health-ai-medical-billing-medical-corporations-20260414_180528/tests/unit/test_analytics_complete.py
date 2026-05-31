import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from types import SimpleNamespace


class TestDenialTrendsEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_denial_trends_empty(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_denial_trends

        result = await get_denial_trends(days=30, db=mock_db)

        assert result.trends is not None
        assert result.summary["total_claims"] == 0

    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_denial_trends_with_data(self, mock_get_db):
        mock_db = MagicMock()

        claim = MagicMock()
        claim.id = 1
        claim.created_at = datetime.utcnow()
        claim.denial_prediction = 0.7
        claim.denial_reasons = [{"reason": "CO16"}]

        mock_db.query.return_value.filter.return_value.all.return_value = [claim]
        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_denial_trends

        result = await get_denial_trends(days=30, db=mock_db)

        assert len(result.trends) >= 1

    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_denial_trends_28_days(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_denial_trends

        result = await get_denial_trends(days=28, db=mock_db)

        assert len(result.trends) == 4

    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_denial_trends_single_period(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_denial_trends

        result = await get_denial_trends(days=7, db=mock_db)

        assert len(result.trends) == 1


class TestAnalyticsSummaryEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_analytics_summary(self, mock_get_db):
        mock_db = MagicMock()

        mock_db.query.return_value.scalar.return_value = 50
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10
        mock_db.query.return_value.filter.return_value.count.return_value = 40
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_analytics_summary

        result = await get_analytics_summary(db=mock_db)

        assert result.total_claims == 50

    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_analytics_summary_zero_claims(self, mock_get_db):
        mock_db = MagicMock()

        mock_db.query.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_analytics_summary

        result = await get_analytics_summary(db=mock_db)

        assert result.total_claims == 0
        assert result.predicted_denial_rate == 0

    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_analytics_summary_with_patterns(self, mock_get_db):
        mock_db = MagicMock()

        mock_db.query.return_value.scalar.return_value = 100
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.count.return_value = 100
        mock_db.query.return_value.all.return_value = []

        pattern = MagicMock()
        pattern.icd_code = "Z00.00"
        pattern.cpt_code = "99213"
        pattern.denial_rate = 0.35

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            pattern
        ]

        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_analytics_summary

        result = await get_analytics_summary(db=mock_db)

        assert len(result.top_denial_patterns) == 1
        assert result.top_denial_patterns[0].pattern == "Z00.00 / 99213"


class TestPredictionAccuracyEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.v1.analytics.get_db")
    async def test_get_prediction_accuracy_counts_finalized_synthetic_outcomes(
        self,
        mock_get_db,
    ):
        mock_db = MagicMock()
        event_time = datetime.utcnow() - timedelta(days=1)
        claims = [
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="denied",
                denial_prediction=0.8,
            ),
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="paid",
                denial_prediction=0.2,
            ),
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="paid",
                denial_prediction=0.7,
            ),
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="denied",
                denial_prediction=0.3,
            ),
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="pending",
                denial_prediction=0.9,
            ),
            SimpleNamespace(
                created_at=event_time,
                submission_date=event_time,
                status="denied",
                denial_prediction=None,
            ),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = claims
        mock_get_db.return_value = mock_db

        from app.api.v1.analytics import get_prediction_accuracy

        result = await get_prediction_accuracy(
            days=30,
            bucket_days=30,
            threshold=0.5,
            db=mock_db,
        )

        assert len(result.periods) == 1
        assert result.summary["total_claims_in_window"] == 6
        assert result.summary["evaluated_claims"] == 4
        assert result.summary["excluded_claims"] == 2
        assert result.summary["accuracy"] == 0.5
        assert result.summary["precision"] == 0.5
        assert result.summary["recall"] == 0.5
        assert result.summary["false_positive_rate"] == 0.5
        assert result.periods[0].true_positives == 1
        assert result.periods[0].true_negatives == 1
        assert result.periods[0].false_positives == 1
        assert result.periods[0].false_negatives == 1

    def test_prediction_accuracy_report_excludes_non_final_claims(self):
        from app.api.v1.analytics import _prediction_accuracy_report

        generated_at = datetime.utcnow()
        claims = [
            SimpleNamespace(
                created_at=generated_at - timedelta(days=1),
                submission_date=None,
                status="submitted",
                denial_prediction=0.95,
            ),
            SimpleNamespace(
                created_at=generated_at - timedelta(days=1),
                submission_date=None,
                status="approved",
                denial_prediction=0.1,
            ),
        ]

        periods, summary = _prediction_accuracy_report(
            claims,
            days=30,
            bucket_days=30,
            threshold=0.5,
            generated_at=generated_at,
        )

        assert len(periods) == 1
        assert summary["total_claims_in_window"] == 2
        assert summary["evaluated_claims"] == 1
        assert summary["excluded_claims"] == 1
        assert summary["accuracy"] == 1.0
