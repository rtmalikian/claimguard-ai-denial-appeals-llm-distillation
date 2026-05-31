import json
import math
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from app.core.config import settings
from app.services.retrieval import (
    EmbeddingProvider,
    EmbeddingResult,
    HASH_EMBEDDING_MODEL,
    HashEmbeddingProvider,
)


HASH_BACKENDS = {"hash", "local_hash", "deterministic_hash"}
DEFAULT_PRIVATE_EMBEDDING_URL_ENV = "RETRIEVAL_PRIVATE_EMBEDDING_URL"
DEFAULT_PRIVATE_EMBEDDING_TOKEN_ENV = "RETRIEVAL_PRIVATE_EMBEDDING_TOKEN"
PRIVATE_EMBEDDING_TIMEOUT_SECONDS = "RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS"
PRIVATE_EMBEDDING_DIMENSIONS = "RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS"


class RetrievalEmbeddingProviderConfigError(ValueError):
    pass


class RetrievalEmbeddingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrivateEmbeddingProviderConfig:
    endpoint_url: str
    backend_name: str
    model_name: str
    dimensions: int
    timeout_seconds: float
    token: str = ""


def _setting_value(settings_like: Any, key: str, default: Any = "") -> Any:
    value = getattr(settings_like, key, None)
    if value not in (None, ""):
        return value
    return os.environ.get(key, default)


def _str_setting(settings_like: Any, key: str, default: str = "") -> str:
    return str(_setting_value(settings_like, key, default) or "").strip()


def _bool_setting(settings_like: Any, key: str) -> bool:
    value = _setting_value(settings_like, key, False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_setting(settings_like: Any, key: str, default: int = 0) -> int:
    raw_value = _setting_value(settings_like, key, default)
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RetrievalEmbeddingProviderConfigError(
            "private embedding dimensions are not configured safely"
        ) from exc


def _float_setting(settings_like: Any, key: str, default: float = 10.0) -> float:
    raw_value = _setting_value(settings_like, key, default)
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise RetrievalEmbeddingProviderConfigError(
            "private embedding timeout is not configured safely"
        ) from exc


def _is_loopback_host(hostname: str | None) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _endpoint_allowed(endpoint_url: str) -> bool:
    parsed = urlparse(endpoint_url)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    if parsed.scheme == "http" and _is_loopback_host(parsed.hostname):
        return True
    return False


def private_embedding_provider_config_status(settings_like=None) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    backend_name = _str_setting(runtime_settings, "RETRIEVAL_EMBEDDING_BACKEND", "hash").lower()
    model_name = _str_setting(
        runtime_settings,
        "RETRIEVAL_EMBEDDING_MODEL",
        HASH_EMBEDDING_MODEL,
    )
    semantic_backend_configured = _bool_setting(
        runtime_settings,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    )
    embedding_model_approved = _bool_setting(
        runtime_settings,
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    )
    hash_fallback_disabled = _bool_setting(
        runtime_settings,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
    )
    endpoint_url = _str_setting(runtime_settings, DEFAULT_PRIVATE_EMBEDDING_URL_ENV)
    token = _str_setting(runtime_settings, DEFAULT_PRIVATE_EMBEDDING_TOKEN_ENV)
    timeout_seconds = _float_setting(
        runtime_settings,
        PRIVATE_EMBEDDING_TIMEOUT_SECONDS,
        10.0,
    )
    dimensions = _int_setting(runtime_settings, PRIVATE_EMBEDDING_DIMENSIONS, 0)
    provider_requested = backend_name not in HASH_BACKENDS
    endpoint_configured = bool(endpoint_url)
    endpoint_allowed = _endpoint_allowed(endpoint_url) if endpoint_configured else False

    blockers: list[str] = []
    if provider_requested:
        if not semantic_backend_configured:
            blockers.append("semantic_backend_not_attested_for_private_provider")
        if not embedding_model_approved:
            blockers.append("embedding_model_not_approved_for_private_provider")
        if not hash_fallback_disabled:
            blockers.append("hash_fallback_not_disabled_for_private_provider")
        if not endpoint_configured:
            blockers.append("private_embedding_endpoint_not_configured")
        elif not endpoint_allowed:
            blockers.append("private_embedding_endpoint_must_use_https_or_loopback")
        if not model_name or model_name == HASH_EMBEDDING_MODEL:
            blockers.append("private_embedding_model_not_configured")
        if dimensions <= 0:
            blockers.append("private_embedding_dimensions_not_configured")
        if timeout_seconds <= 0:
            blockers.append("private_embedding_timeout_not_positive")

    return {
        "provider_requested": provider_requested,
        "provider_ready": provider_requested and not blockers,
        "backend_is_hash_fallback": backend_name in HASH_BACKENDS,
        "semantic_backend_configured": semantic_backend_configured,
        "embedding_model_approved": embedding_model_approved,
        "hash_fallback_disabled_for_production": hash_fallback_disabled,
        "private_embedding_endpoint_configured": endpoint_configured,
        "private_embedding_endpoint_uses_https_or_loopback": endpoint_allowed,
        "private_embedding_token_configured": bool(token),
        "private_embedding_dimensions_configured": dimensions > 0,
        "private_embedding_timeout_configured": timeout_seconds > 0,
        "blockers": blockers,
        "safe_context": {
            "raw_text_included": False,
            "embedding_endpoint_value_included": False,
            "embedding_token_value_included": False,
            "private_embedding_endpoint_value_included": False,
            "private_embedding_token_value_included": False,
            "vector_values_included": False,
        },
    }


def _private_provider_config(settings_like=None) -> PrivateEmbeddingProviderConfig:
    runtime_settings = settings_like or settings
    status = private_embedding_provider_config_status(runtime_settings)
    if status["blockers"]:
        raise RetrievalEmbeddingProviderConfigError(
            "private semantic embedding provider is not safely configured"
        )
    return PrivateEmbeddingProviderConfig(
        endpoint_url=_str_setting(runtime_settings, DEFAULT_PRIVATE_EMBEDDING_URL_ENV),
        token=_str_setting(runtime_settings, DEFAULT_PRIVATE_EMBEDDING_TOKEN_ENV),
        backend_name=_str_setting(runtime_settings, "RETRIEVAL_EMBEDDING_BACKEND"),
        model_name=_str_setting(runtime_settings, "RETRIEVAL_EMBEDDING_MODEL"),
        dimensions=_int_setting(runtime_settings, PRIVATE_EMBEDDING_DIMENSIONS),
        timeout_seconds=_float_setting(
            runtime_settings,
            PRIVATE_EMBEDDING_TIMEOUT_SECONDS,
            10.0,
        ),
    )


class PrivateSemanticEmbeddingProvider:
    def __init__(self, config: PrivateEmbeddingProviderConfig):
        self._config = config
        self.model_name = config.model_name
        self.backend_name = config.backend_name
        self.dimensions = config.dimensions

    def embed(self, text: str) -> EmbeddingResult:
        payload = json.dumps(
            {"input": text, "model": self.model_name},
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        http_request = request.Request(
            self._config.endpoint_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(
                http_request,
                timeout=self._config.timeout_seconds,
            ) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RetrievalEmbeddingProviderError(
                "private semantic embedding request failed without raw content"
            ) from exc

        vector = self._extract_vector(response_payload)
        return EmbeddingResult(
            vector=vector,
            model=self.model_name,
            backend=self.backend_name,
        )

    def _extract_vector(self, payload: Any) -> list[float]:
        candidate: Any = None
        if isinstance(payload, dict):
            if isinstance(payload.get("embedding"), list):
                candidate = payload["embedding"]
            elif isinstance(payload.get("vector"), list):
                candidate = payload["vector"]
            elif isinstance(payload.get("data"), list) and payload["data"]:
                first = payload["data"][0]
                if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                    candidate = first["embedding"]
        if not isinstance(candidate, list):
            raise RetrievalEmbeddingProviderError(
                "private semantic embedding response did not include a vector"
            )
        if len(candidate) != self.dimensions:
            raise RetrievalEmbeddingProviderError(
                "private semantic embedding response dimensions do not match configuration"
            )
        vector: list[float] = []
        for value in candidate:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise RetrievalEmbeddingProviderError(
                    "private semantic embedding response contained a non-numeric value"
                ) from exc
            if not math.isfinite(number):
                raise RetrievalEmbeddingProviderError(
                    "private semantic embedding response contained a non-finite value"
                )
            vector.append(number)
        return vector


def build_retrieval_embedding_provider(settings_like=None) -> EmbeddingProvider:
    runtime_settings = settings_like or settings
    backend_name = _str_setting(runtime_settings, "RETRIEVAL_EMBEDDING_BACKEND", "hash")
    if backend_name.strip().lower() in HASH_BACKENDS:
        return HashEmbeddingProvider()
    return PrivateSemanticEmbeddingProvider(_private_provider_config(runtime_settings))
