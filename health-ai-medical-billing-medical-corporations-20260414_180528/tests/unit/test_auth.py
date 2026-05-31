from datetime import datetime
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import ROLE_ADMIN, ROLE_VIEWER, bootstrap_admin_user
from app.core.security import create_access_token, get_password_hash
from app.core.config import settings
from app.core.security import verify_password
from app.db.database import Base, get_db
from app.main import app
from app.models import User


def auth_headers(role: str = "admin") -> dict[str, str]:
    token = create_access_token(
        {"sub": "1", "email": f"{role}@example.test", "full_name": "Synthetic User", "role": role}
    )
    return {"Authorization": f"Bearer {token}"}


def make_user(role: str = "admin") -> User:
    return User(
        id=1,
        email=f"{role}@example.test",
        full_name="Synthetic User",
        hashed_password=get_password_hash("synthetic-password"),
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def bootstrap_env(monkeypatch):
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "new-synthetic-password")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_NAME", "Synthetic Admin")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_SYNC_FROM_ENV", False)


class TestAuthEndpoints:
    def test_login_success_returns_token_and_user(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = make_user()
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.test", "password": "synthetic-password"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert data["user"]["role"] == "admin"

    def test_login_failure_is_generic(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "missing@example.test", "password": "wrong-password"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_me_requires_valid_token(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = make_user()
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client = TestClient(app)
            response = client.get("/api/v1/auth/me", headers=auth_headers())
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["email"] == "admin@example.test"

    def test_logout_requires_valid_token(self):
        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client = TestClient(app)
            response = client.post("/api/v1/auth/logout", headers=auth_headers())
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"


class TestAuthProtection:
    def test_protected_api_rejects_missing_token(self):
        client = TestClient(app)
        response = client.get("/api/v1/analytics/summary")

        assert response.status_code == 401
        assert response.json()["detail"] == "Missing bearer token"

    def test_protected_api_rejects_invalid_token(self):
        client = TestClient(app)
        response = client.get(
            "/api/v1/analytics/summary",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    def test_viewer_cannot_access_write_endpoint(self):
        client = TestClient(app)
        response = client.post(
            "/api/v1/claims/predict",
            headers=auth_headers("viewer"),
            json={"patient_id": 1, "provider_id": 1, "claim_data": {"amount": 100}},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient role permissions"

    def test_root_and_docs_remain_public(self):
        client = TestClient(app)

        assert client.get("/").status_code == 200
        assert client.get("/docs").status_code == 200


class TestBootstrapAdmin:
    def test_bootstrap_skips_when_credentials_missing(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "")
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "")

        bootstrap_admin_user(db_session)

        assert db_session.query(User).count() == 0

    def test_bootstrap_creates_admin_from_env(self, db_session, bootstrap_env):
        bootstrap_admin_user(db_session)

        user = db_session.query(User).filter(User.email == "admin@example.test").first()
        assert user is not None
        assert user.full_name == "Synthetic Admin"
        assert user.role == ROLE_ADMIN
        assert user.is_active is True
        assert verify_password("new-synthetic-password", user.hashed_password)

    def test_bootstrap_preserves_existing_admin_password_when_sync_disabled(self, db_session, bootstrap_env):
        user = User(
            email="admin@example.test",
            full_name="Existing Admin",
            hashed_password=get_password_hash("old-synthetic-password"),
            role=ROLE_ADMIN,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        bootstrap_admin_user(db_session)
        db_session.refresh(user)

        assert verify_password("old-synthetic-password", user.hashed_password)
        assert not verify_password("new-synthetic-password", user.hashed_password)

    def test_bootstrap_sync_updates_env_user_password_without_logging_secret(
        self, db_session, bootstrap_env, monkeypatch, caplog
    ):
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_SYNC_FROM_ENV", True)
        user = User(
            email="admin@example.test",
            full_name="Existing User",
            hashed_password=get_password_hash("old-synthetic-password"),
            role=ROLE_VIEWER,
            is_active=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        caplog.set_level(logging.INFO, logger="app.core.auth")

        bootstrap_admin_user(db_session)
        db_session.refresh(user)

        assert user.full_name == "Synthetic Admin"
        assert user.role == ROLE_ADMIN
        assert user.is_active is True
        assert verify_password("new-synthetic-password", user.hashed_password)
        assert "new-synthetic-password" not in caplog.text

    def test_bootstrap_sync_creates_env_admin_when_other_admin_exists(
        self, db_session, bootstrap_env, monkeypatch
    ):
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_SYNC_FROM_ENV", True)
        other_admin = User(
            email="other-admin@example.test",
            full_name="Other Admin",
            hashed_password=get_password_hash("other-synthetic-password"),
            role=ROLE_ADMIN,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(other_admin)
        db_session.commit()

        bootstrap_admin_user(db_session)

        env_admin = db_session.query(User).filter(User.email == "admin@example.test").first()
        assert env_admin is not None
        assert env_admin.role == ROLE_ADMIN
        assert verify_password("new-synthetic-password", env_admin.hashed_password)
