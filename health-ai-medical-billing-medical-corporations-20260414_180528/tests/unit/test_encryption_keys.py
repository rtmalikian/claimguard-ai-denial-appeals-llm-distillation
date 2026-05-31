import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.security import (
    EncryptionConfigurationError,
    EncryptionService,
    generate_fernet_key,
    is_valid_fernet_key,
)


def test_generate_fernet_key_returns_valid_key():
    key = generate_fernet_key()

    assert is_valid_fernet_key(key)
    cipher = Fernet(key.encode())
    token = cipher.encrypt(b"synthetic billing metadata")

    assert cipher.decrypt(token) == b"synthetic billing metadata"


def test_settings_prefers_encryption_keys_over_deprecated_single_key():
    primary = generate_fernet_key()
    old_key = generate_fernet_key()
    deprecated_key = generate_fernet_key()

    settings = Settings(
        ENCRYPTION_KEYS=f"{primary},{old_key}",
        ENCRYPTION_KEY=deprecated_key,
    )

    assert settings.configured_encryption_keys == [primary, old_key]


def test_encryption_service_rejects_placeholder_in_production():
    with pytest.raises(EncryptionConfigurationError, match="Placeholder encryption keys"):
        EncryptionService(
            keys=["your-encryption-key-change-in-production-32-chars"],
            app_env="production",
        )


def test_encryption_service_rejects_invalid_non_placeholder_key():
    with pytest.raises(EncryptionConfigurationError, match="Invalid Fernet encryption key"):
        EncryptionService(keys=["not-a-valid-fernet-key"], app_env="development")


def test_encryption_service_uses_ephemeral_key_only_outside_production():
    service = EncryptionService(keys=[], app_env="development")
    encrypted = service.encrypt("synthetic claim attribute")

    assert service.uses_ephemeral_key is True
    assert service.decrypt(encrypted) == "synthetic claim attribute"


def test_encryption_service_requires_key_in_production():
    with pytest.raises(EncryptionConfigurationError, match="ENCRYPTION_KEYS"):
        EncryptionService(keys=[], app_env="production")


def test_encryption_service_decrypts_with_old_rotation_key():
    old_key = generate_fernet_key()
    primary_key = generate_fernet_key()
    old_service = EncryptionService(keys=[old_key], app_env="test")
    encrypted_with_old_key = old_service.encrypt("synthetic denial reason")

    service = EncryptionService(keys=[primary_key, old_key], app_env="test")

    assert service.decrypt(encrypted_with_old_key) == "synthetic denial reason"


def test_encryption_service_rotates_ciphertext_to_primary_key():
    old_key = generate_fernet_key()
    primary_key = generate_fernet_key()
    encrypted_with_old_key = EncryptionService(keys=[old_key], app_env="test").encrypt(
        "synthetic denial reason"
    )
    service = EncryptionService(keys=[primary_key, old_key], app_env="test")

    rotated = service.rotate(encrypted_with_old_key)

    assert rotated != encrypted_with_old_key
    assert service.decrypt(rotated) == "synthetic denial reason"
    primary_decrypted = Fernet(primary_key.encode()).decrypt(rotated.encode()).decode()
    assert primary_decrypted == "synthetic denial reason"
    with pytest.raises(InvalidToken):
        Fernet(old_key.encode()).decrypt(rotated.encode())


def test_encryption_service_rotates_dict_values():
    old_key = generate_fernet_key()
    primary_key = generate_fernet_key()
    old_service = EncryptionService(keys=[old_key], app_env="test")
    data = {"claim": {"reason": old_service.encrypt("synthetic authorization issue")}}
    service = EncryptionService(keys=[primary_key, old_key], app_env="test")

    rotated = service.rotate_dict(data)

    assert rotated["claim"]["reason"] != data["claim"]["reason"]
    assert service.decrypt_dict(rotated) == {"claim": {"reason": "synthetic authorization issue"}}
