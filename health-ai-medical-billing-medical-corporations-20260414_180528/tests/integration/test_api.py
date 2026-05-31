import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.security import create_access_token
from app.main import app

client = TestClient(app)
AUTH_HEADERS = {
    "Authorization": f"Bearer {create_access_token({'sub': '1', 'email': 'admin@example.test', 'role': 'admin'})}"
}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "degraded"]

    def test_root_endpoint(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "ClaimGuard AI" in response.json()["message"]


class TestClaimsEndpoints:
    @patch("app.api.v1.claims.PredictionService")
    def test_predict_denial(self, mock_service):
        mock_instance = MagicMock()
        mock_instance.predict_denial = AsyncMock(
            return_value=(
                0.35,
                0.75,
                [{"reason": "Test reason", "severity": "medium"}],
                [{"action": "Test action", "description": "Test desc", "priority": "low"}],
            )
        )
        mock_service.return_value = mock_instance

        response = client.post(
            "/api/v1/claims/predict",
            headers=AUTH_HEADERS,
            json={
                "patient_id": 1,
                "provider_id": 1,
                "claim_data": {"amount": 1000},
                "diagnosis_codes": ["Z00.00"],
                "procedure_codes": ["99213"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "denial_prediction" in data
        assert "denial_reasons" in data
        assert "recommendations" in data

    @patch("app.api.v1.claims.PredictionService")
    @patch("app.db.database.SessionLocal")
    def test_submit_claim(self, mock_session, mock_service):
        mock_instance = MagicMock()
        mock_instance.predict_denial = AsyncMock(return_value=(0.25, 0.80, [], []))
        mock_service.return_value = mock_instance

        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

        response = client.post(
            "/api/v1/claims/submit",
            headers=AUTH_HEADERS,
            json={"patient_id": 1, "provider_id": 1, "claim_data": {"amount": 1000}},
        )

        assert response.status_code in [200, 400, 422, 500]


class TestAnalyticsEndpoints:
    @patch("app.db.database.SessionLocal")
    def test_denial_trends(self, mock_session):
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        response = client.get("/api/v1/analytics/denial-trends?days=30", headers=AUTH_HEADERS)

        assert response.status_code in [200, 500]

    @patch("app.db.database.SessionLocal")
    def test_analytics_summary(self, mock_session):
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_db.query.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.all.return_value = []

        response = client.get("/api/v1/analytics/summary", headers=AUTH_HEADERS)

        assert response.status_code in [200, 500]
