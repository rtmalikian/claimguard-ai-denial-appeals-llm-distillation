import logging
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

PLACEHOLDER_ENCRYPTION_KEY_MARKERS = (
    "your-encryption-key",
    "32-byte-encryption-key",
    "change-in-production",
    "<generate-fernet-key>",
)


class EncryptionConfigurationError(ValueError):
    pass


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


def is_placeholder_encryption_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in PLACEHOLDER_ENCRYPTION_KEY_MARKERS)


def is_valid_fernet_key(key: str) -> bool:
    try:
        Fernet(key.encode())
    except (TypeError, ValueError):
        return False
    return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


class EncryptionService:
    def __init__(self, keys: Optional[list[str] | str] = None, app_env: Optional[str] = None):
        self.app_env = (app_env or settings.APP_ENV or "development").lower()
        configured_keys = self._resolve_keys(keys)
        self.uses_ephemeral_key = False

        if not configured_keys:
            if self._requires_persistent_keys():
                raise EncryptionConfigurationError(
                    "ENCRYPTION_KEYS must contain at least one valid Fernet key in production."
                )
            configured_keys = [generate_fernet_key()]
            self.uses_ephemeral_key = True
            logger.warning(
                "No valid ENCRYPTION_KEYS configured; using an ephemeral development key. "
                "Encrypted values will not survive application restarts."
            )

        self.keys = configured_keys
        self.primary_key = configured_keys[0]
        self.ciphers = [Fernet(key.encode()) for key in configured_keys]
        self.cipher = MultiFernet(self.ciphers)

    def _requires_persistent_keys(self) -> bool:
        return self.app_env in {"prod", "production"}

    def _resolve_keys(self, keys: Optional[list[str] | str]) -> list[str]:
        raw_keys = self._raw_keys(keys)
        resolved_keys = []
        placeholders = []

        for key in raw_keys:
            if is_placeholder_encryption_key(key):
                placeholders.append(key)
                continue
            if not is_valid_fernet_key(key):
                raise EncryptionConfigurationError(
                    "Invalid Fernet encryption key configured. Generate a key with "
                    "`python3 scripts/generate_fernet_key.py` and set ENCRYPTION_KEYS."
                )
            resolved_keys.append(key)

        if placeholders:
            if self._requires_persistent_keys():
                raise EncryptionConfigurationError(
                    "Placeholder encryption keys are forbidden in production. Generate a key "
                    "with `python3 scripts/generate_fernet_key.py` and set ENCRYPTION_KEYS."
                )
            logger.warning(
                "Ignoring placeholder ENCRYPTION_KEY/ENCRYPTION_KEYS values in %s.",
                self.app_env,
            )

        return resolved_keys

    def _raw_keys(self, keys: Optional[list[str] | str]) -> list[str]:
        if keys is None:
            return settings.configured_encryption_keys
        if isinstance(keys, str):
            return [key.strip() for key in keys.split(",") if key.strip()]
        return [key.strip() for key in keys if key and key.strip()]

    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def rotate(self, encrypted_data: str) -> str:
        return self.cipher.rotate(encrypted_data.encode()).decode()

    def encrypt_dict(self, data: dict) -> dict:
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.encrypt(value)
            elif isinstance(value, dict):
                result[key] = self.encrypt_dict(value)
            else:
                result[key] = value
        return result

    def decrypt_dict(self, data: dict) -> dict:
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 50:
                try:
                    result[key] = self.decrypt(value)
                except Exception:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self.decrypt_dict(value)
            else:
                result[key] = value
        return result

    def rotate_dict(self, data: dict) -> dict:
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 50:
                try:
                    result[key] = self.rotate(value)
                except Exception:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self.rotate_dict(value)
            else:
                result[key] = value
        return result


encryption_service = EncryptionService()
