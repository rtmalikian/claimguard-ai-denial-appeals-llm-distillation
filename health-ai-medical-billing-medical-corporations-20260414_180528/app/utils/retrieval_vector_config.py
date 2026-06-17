import logging
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.retrieval import HASH_EMBEDDING_MODEL
from app.services.retrieval_semantic_provider import (
    private_embedding_provider_config_status,
)


logger = logging.getLogger(__name__)

PRODUCTION_ENVS = {"prod", "production"}
HASH_EMBEDDING_BACKENDS = {"hash", "local_hash", "deterministic_hash"}
LOCAL_VECTOR_BACKENDS = {
    "encrypted_local_metadata",
    "local_encrypted_metadata",
    "local_metadata",
}
CHROMA_VECTOR_BACKENDS = {"chroma", "chromadb", "chroma_local"}


def _str_value(settings_like, name: str, default: str = "") -> str:
    value = getattr(settings_like, name, default)
    if value is None:
        return default
    return str(value).strip()


def _bool_value(settings_like, name: str) -> bool:
    return getattr(settings_like, name, False) is True


def _looks_like_url_or_secret_bearing_backend(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


def validate_retrieval_vector_startup_config(settings_like=None) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    app_env = _str_value(runtime_settings, "APP_ENV", "development").lower()
    embedding_backend = _str_value(runtime_settings, "RETRIEVAL_EMBEDDING_BACKEND", "hash").lower()
    embedding_model = _str_value(
        runtime_settings,
        "RETRIEVAL_EMBEDDING_MODEL",
        HASH_EMBEDDING_MODEL,
    )
    vector_backend = _str_value(
        runtime_settings,
        "RETRIEVAL_VECTOR_BACKEND",
        "encrypted_local_metadata",
    ).lower()
    semantic_backend_configured = _bool_value(
        runtime_settings,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED",
    )
    embedding_model_approved = _bool_value(
        runtime_settings,
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED",
    )
    hash_fallback_disabled = _bool_value(
        runtime_settings,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
    )
    app_env_is_production = app_env in PRODUCTION_ENVS
    vector_backend_has_url_or_credentials = _looks_like_url_or_secret_bearing_backend(
        vector_backend
    )
    private_provider_status = private_embedding_provider_config_status(runtime_settings)

    blockers: list[str] = []
    if not semantic_backend_configured:
        blockers.append("semantic_embedding_backend_not_configured")
    if embedding_backend in HASH_EMBEDDING_BACKENDS:
        blockers.append("hash_embedding_backend_is_fallback_only")
    if not embedding_model or embedding_model == HASH_EMBEDDING_MODEL:
        blockers.append("embedding_model_not_production_semantic_model")
    if not embedding_model_approved:
        blockers.append("embedding_model_not_approved_for_production")
    if not vector_backend or vector_backend in LOCAL_VECTOR_BACKENDS:
        blockers.append("production_vector_backend_not_configured")
    if vector_backend in CHROMA_VECTOR_BACKENDS:
        # ChromaDB is a valid local persistent vector backend.
        # Remove the "not configured" blocker if it was added above.
        blockers = [b for b in blockers if b != "production_vector_backend_not_configured"]
    if not hash_fallback_disabled:
        blockers.append("hash_fallback_not_disabled_for_production")
    if vector_backend_has_url_or_credentials:
        blockers.append("vector_backend_setting_must_not_store_url_or_credentials")
    blockers.extend(private_provider_status["blockers"])

    safe_context = {
        "raw_source_text_included": False,
        "raw_vector_values_included": False,
        "raw_embedding_service_url_included": False,
        "raw_credentials_included": False,
        "raw_phi_included": False,
        "private_embedding_endpoint_value_included": False,
        "private_embedding_token_value_included": False,
    }
    report = {
        "app_env": app_env,
        "app_env_is_production": app_env_is_production,
        "semantic_backend_configured": semantic_backend_configured,
        "embedding_backend_is_hash_fallback": embedding_backend in HASH_EMBEDDING_BACKENDS,
        "embedding_model_is_hash_fallback": embedding_model == HASH_EMBEDDING_MODEL,
        "embedding_model_configured": bool(embedding_model),
        "embedding_model_approved": embedding_model_approved,
        "production_vector_backend_configured": (
            bool(vector_backend)
            and vector_backend not in LOCAL_VECTOR_BACKENDS
            and not vector_backend_has_url_or_credentials
        ),
        "vector_backend_has_url_or_credentials": vector_backend_has_url_or_credentials,
        "vector_backend_is_chroma": vector_backend in CHROMA_VECTOR_BACKENDS,
        "hash_fallback_disabled_for_production": hash_fallback_disabled,
        "private_embedding_provider_requested": private_provider_status[
            "provider_requested"
        ],
        "private_embedding_provider_ready": private_provider_status["provider_ready"],
        "private_embedding_endpoint_configured": private_provider_status[
            "private_embedding_endpoint_configured"
        ],
        "private_embedding_endpoint_uses_https_or_loopback": private_provider_status[
            "private_embedding_endpoint_uses_https_or_loopback"
        ],
        "private_embedding_token_configured": private_provider_status[
            "private_embedding_token_configured"
        ],
        "private_embedding_dimensions_configured": private_provider_status[
            "private_embedding_dimensions_configured"
        ],
        "blockers": blockers,
        "startup_ready": not blockers,
        "fail_fast_required": app_env_is_production and bool(blockers),
        "safe_context": safe_context,
    }

    log_payload = {
        key: value
        for key, value in report.items()
        if key not in {"blockers"}
    }
    log_payload["blocker_count"] = len(blockers)
    log_payload["blockers"] = blockers
    if blockers:
        logger.warning(
            "retrieval_vector_startup_config_validation_failed",
            extra={"retrieval_vector_startup_config": log_payload},
        )
    else:
        logger.info(
            "retrieval_vector_startup_config_validation_passed",
            extra={"retrieval_vector_startup_config": log_payload},
        )
    if report["fail_fast_required"]:
        raise RuntimeError("Retrieval vector startup configuration is not production-ready.")
    return report
