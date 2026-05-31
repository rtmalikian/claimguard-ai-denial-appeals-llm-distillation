import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    @patch("app.db.database.get_db")
    def test_health_check_returns_status(self, mock_db):
        mock_db.return_value = MagicMock()

        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert data["status"] in ["healthy", "degraded"]


class TestMainApp:
    def test_app_exists(self):
        from app.main import app

        assert app is not None

    def test_app_has_routes(self):
        from app.main import app

        routes = [route.path for route in app.routes]
        assert len(routes) > 0

    def test_health_endpoint_exists(self):
        from app.main import app

        paths = [route.path for route in app.routes]
        assert "/health" in paths
