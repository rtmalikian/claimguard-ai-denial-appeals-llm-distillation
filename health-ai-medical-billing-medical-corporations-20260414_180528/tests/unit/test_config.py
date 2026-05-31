import pytest
from app.core.config import Settings, settings


class TestSettings:
    def test_settings_creation(self):
        settings_obj = Settings()

        assert settings_obj.APP_NAME == "ClaimGuard AI"
        assert hasattr(settings_obj, "DATABASE_URL")
        assert hasattr(settings_obj, "NVIDIA_BASE_URL")
        assert hasattr(settings_obj, "NVIDIA_MODEL")
        assert hasattr(settings_obj, "NVIDIA_OCR_MODEL")

    def test_database_url_default(self):
        settings_obj = Settings()

        assert settings_obj.DATABASE_URL is not None
        assert (
            "postgresql" in settings_obj.DATABASE_URL.lower()
            or settings_obj.DATABASE_URL.startswith("sqlite")
        )

    def test_nvidia_settings(self):
        settings_obj = Settings()

        assert settings_obj.LLM_PROVIDER == "nvidia_nim"
        assert settings_obj.NVIDIA_BASE_URL.startswith("https://")
        assert settings_obj.NVIDIA_MODEL is not None
        assert settings_obj.NVIDIA_OCR_MODEL is not None
        assert settings_obj.NVIDIA_TIMEOUT > 0

    def test_security_settings(self):
        settings_obj = Settings()

        assert settings_obj.SECRET_KEY is not None
        assert settings_obj.ALGORITHM == "HS256"
        assert settings_obj.ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_api_settings(self):
        settings_obj = Settings()

        assert settings_obj.API_V1_PREFIX == "/api/v1"
        assert settings_obj.APP_ENV in ["development", "production", "test"]


class TestSettingsSingleton:
    def test_settings_is_singleton(self):
        assert settings is not None
        assert settings.APP_NAME == "ClaimGuard AI"

    def test_settings_accessible(self):
        assert settings.DATABASE_URL is not None
        assert settings.NVIDIA_BASE_URL is not None
