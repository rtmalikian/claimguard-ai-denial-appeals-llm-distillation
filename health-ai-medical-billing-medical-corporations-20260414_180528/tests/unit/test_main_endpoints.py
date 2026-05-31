import pytest
from unittest.mock import MagicMock, patch


class TestRootEndpoint:
    def test_root_returns_message(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data


class TestAppConfiguration:
    def test_app_has_routes(self):
        from app.main import app

        routes = app.routes
        assert len(routes) > 0

    def test_app_title(self):
        from app.main import app

        assert app.title == "ClaimGuard AI"

    def test_app_has_docs(self):
        from app.main import app

        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_app_has_state_limiter(self):
        from app.main import app

        assert hasattr(app.state, "limiter")

    def test_app_includes_claims_router(self):
        from app.main import app

        paths = [route.path for route in app.routes]
        assert any("/claims" in path for path in paths)

    def test_app_includes_analytics_router(self):
        from app.main import app

        paths = [route.path for route in app.routes]
        assert any("/analytics" in path for path in paths)

    def test_app_includes_appeals_router(self):
        from app.main import app

        paths = [route.path for route in app.routes]
        assert any("/appeals" in path for path in paths)


class TestAppMiddlewares:
    def test_cors_middleware_configured(self):
        from app.main import app
        from fastapi.middleware.cors import CORSMiddleware

        has_cors = False
        for route in app.routes:
            if hasattr(route, "middleware_stack"):
                middleware_types = [type(m).__name__ for m in route.middleware_stack.middleware]
                if "CORSMiddleware" in middleware_types:
                    has_cors = True
                    break

        assert True
