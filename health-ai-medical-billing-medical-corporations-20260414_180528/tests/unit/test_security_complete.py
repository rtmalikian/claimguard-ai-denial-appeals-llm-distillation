import pytest
from datetime import timedelta
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    EncryptionService,
    encryption_service,
)


class TestEncryptionService:
    def test_encrypt_returns_different_string(self):
        service = EncryptionService()
        original = "sensitive_data_123"
        encrypted = service.encrypt(original)

        assert encrypted != original
        assert len(encrypted) > len(original)

    def test_decrypt_returns_original(self):
        service = EncryptionService()
        original = "sensitive_data_123"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_dict_simple(self):
        service = EncryptionService()
        data = {"name": "John", "ssn": "123-45-6789"}

        result = service.encrypt_dict(data)

        decrypted = service.decrypt_dict(result)
        assert decrypted["name"] == "John"
        assert decrypted["ssn"] == "123-45-6789"

    def test_encrypt_dict_nested(self):
        service = EncryptionService()
        data = {"user": {"name": "John", "password": "secret"}}

        result = service.encrypt_dict(data)

        decrypted = service.decrypt_dict(result)
        assert decrypted["user"]["name"] == "John"
        assert decrypted["user"]["password"] == "secret"

    def test_encrypt_dict_non_string_values(self):
        service = EncryptionService()
        data = {"age": 25, "active": True}

        result = service.encrypt_dict(data)

        assert result["age"] == 25
        assert result["active"] is True

    def test_decrypt_dict_simple(self):
        service = EncryptionService()
        original = {"name": "John", "ssn": "123-45-6789"}
        encrypted = service.encrypt_dict(original)

        result = service.decrypt_dict(encrypted)

        assert result["name"] == "John"
        assert result["ssn"] == "123-45-6789"

    def test_decrypt_dict_nested(self):
        service = EncryptionService()
        original = {"user": {"name": "John", "password": "secret"}}
        encrypted = service.encrypt_dict(original)

        result = service.decrypt_dict(encrypted)

        assert result["user"]["name"] == "John"
        assert result["user"]["password"] == "secret"

    def test_decrypt_dict_non_encrypted_values(self):
        service = EncryptionService()
        data = {"age": 25, "short": "abc"}

        result = service.decrypt_dict(data)

        assert result["age"] == 25
        assert result["short"] == "abc"

    def test_decrypt_dict_mixed(self):
        service = EncryptionService()
        data = {"name": "John", "ssn": "123-45-6789", "age": 30}

        result = service.decrypt_dict(data)

        assert result["name"] == "John"
        assert result["ssn"] == "123-45-6789"
        assert result["age"] == 30


class TestEncryptionServiceSingleton:
    def test_encryption_service_singleton(self):
        assert encryption_service is not None
        assert isinstance(encryption_service, EncryptionService)

    def test_singleton_encrypt_decrypt(self):
        original = "test data"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == original


class TestTokenExpiration:
    def test_token_with_custom_expiration(self):
        token = create_access_token({"sub": "user123"}, expires_delta=timedelta(hours=1))

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert "exp" in payload

    def test_token_with_minutes_expiration(self):
        token = create_access_token({"sub": "user456"}, expires_delta=timedelta(minutes=15))

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user456"

    def test_token_default_expiration(self):
        token = create_access_token({"sub": "user789"})

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user789"


class TestTokenEdgeCases:
    def test_decode_empty_token(self):
        payload = decode_token("")
        assert payload is None

    def test_decode_malformed_token(self):
        payload = decode_token("not.a.valid.token")
        assert payload is None

    def test_decode_token_missing_secret(self):
        from jose import jwt
        from app.core.config import settings

        payload = decode_token(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        )
        assert payload is None

    def test_create_token_with_additional_claims(self):
        token = create_access_token(
            {"sub": "user123", "role": "admin", "permissions": ["read", "write"]}
        )

        payload = decode_token(token)

        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]


class TestPasswordHashEdgeCases:
    def test_hash_long_password(self):
        long_password = "a" * 100
        hash_result = get_password_hash(long_password)

        assert verify_password(long_password, hash_result) is True

    def test_hash_unicode_password(self):
        unicode_password = "пароль密码🔐"
        hash_result = get_password_hash(unicode_password)

        assert verify_password(unicode_password, hash_result) is True
