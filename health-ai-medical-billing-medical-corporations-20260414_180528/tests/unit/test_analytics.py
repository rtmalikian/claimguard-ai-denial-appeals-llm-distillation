import pytest
from datetime import datetime
from app.schemas.analytics import (
    DenialTrendData,
    DenialTrendResponse,
    ClaimsByStatus,
    TopDenialPatterns,
    AnalyticsSummary,
    PredictionAccuracyPeriod,
    PredictionAccuracyResponse,
    AppealGenerateRequest,
    AppealGenerateResponse,
)


class TestAnalyticsSchemas:
    def test_denial_trend_data(self):
        data = DenialTrendData(
            period="2024-01",
            total_claims=100,
            predicted_denials=25,
            denial_rate=0.25,
            top_reasons=[{"reason": "CO16", "count": 10}],
        )

        assert data.period == "2024-01"
        assert data.total_claims == 100
        assert data.denial_rate == 0.25

    def test_claims_by_status(self):
        status = ClaimsByStatus(
            status="denied",
            count=25,
            percentage=25.0,
        )

        assert status.status == "denied"
        assert status.count == 25

    def test_top_denial_patterns(self):
        pattern = TopDenialPatterns(
            pattern="Missing documentation",
            count=15,
            percentage=15.0,
        )

        assert pattern.pattern == "Missing documentation"
        assert pattern.count == 15

    def test_analytics_summary(self):
        summary = AnalyticsSummary(
            total_claims=100,
            pending_claims=10,
            processed_claims=90,
            predicted_denial_rate=0.25,
            claims_by_status=[ClaimsByStatus(status="denied", count=25, percentage=25.0)],
            top_denial_patterns=[TopDenialPatterns(pattern="CO16", count=10, percentage=40.0)],
        )

        assert summary.total_claims == 100
        assert summary.predicted_denial_rate == 0.25
        assert len(summary.claims_by_status) == 1

    def test_prediction_accuracy_period(self):
        period = PredictionAccuracyPeriod(
            period="2026-01-01 to 2026-01-31",
            evaluated_claims=4,
            predicted_denials=2,
            actual_denials=2,
            true_positives=1,
            true_negatives=1,
            false_positives=1,
            false_negatives=1,
            accuracy=0.5,
            precision=0.5,
            recall=0.5,
            false_positive_rate=0.5,
            actual_denial_rate=0.5,
            predicted_denial_rate=0.5,
        )

        assert period.evaluated_claims == 4
        assert period.false_negatives == 1

    def test_prediction_accuracy_response(self):
        response = PredictionAccuracyResponse(
            periods=[],
            summary={
                "total_claims_in_window": 0,
                "evaluated_claims": 0,
                "excluded_claims": 0,
            },
            generated_at=datetime.utcnow(),
        )

        assert response.summary["evaluated_claims"] == 0

    def test_denial_trend_response(self):
        response = DenialTrendResponse(
            trends=[
                DenialTrendData(
                    period="2024-01",
                    total_claims=50,
                    predicted_denials=12,
                    denial_rate=0.24,
                    top_reasons=[],
                )
            ],
            summary={"average_rate": 0.24},
            generated_at=datetime.utcnow(),
        )

        assert len(response.trends) == 1
        assert response.summary["average_rate"] == 0.24

    def test_appeal_generate_request(self):
        request = AppealGenerateRequest(
            claim_id=1,
            appeal_reason="Medical necessity",
            additional_context="Prior authorization obtained",
        )

        assert request.claim_id == 1
        assert request.appeal_reason == "Medical necessity"

    def test_appeal_generate_request_optional_context(self):
        request = AppealGenerateRequest(
            claim_id=2,
            appeal_reason="Coding error",
        )

        assert request.claim_id == 2
        assert request.additional_context is None

    def test_appeal_generate_response(self):
        response = AppealGenerateResponse(
            claim_id=1,
            appeal_letter="Formal appeal letter text...",
            supporting_evidence=["Medical records", "Doctor's notes"],
            generated_at=datetime.utcnow(),
        )

        assert response.claim_id == 1
        assert "Formal appeal" in response.appeal_letter
        assert len(response.supporting_evidence) == 2
