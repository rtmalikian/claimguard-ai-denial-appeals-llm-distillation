import json
from types import SimpleNamespace

import pytest

from app.utils.retrieval_vector_config import validate_retrieval_vector_startup_config


def _settings(**overrides):
    values = {
        "APP_ENV": "development",
        "RETRIEVAL_EMBEDDING_BACKEND": "hash",
        "RETRIEVAL_EMBEDDING_MODEL": "claimguard-hash-embedding-v1",
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED": False,
        "RETRIEVAL_VECTOR_BACKEND": "encrypted_local_metadata",
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": False,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": False,
        "RETRIEVAL_PRIVATE_EMBEDDING_URL": "",
        "RETRIEVAL_PRIVATE_EMBEDDING_TOKEN": "",
        "RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS": 0,
        "RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_development_hash_fallback_reports_blockers_without_fail_fast():
    report = validate_retrieval_vector_startup_config(_settings())

    assert report["startup_ready"] is False
    assert report["fail_fast_required"] is False
    assert "hash_embedding_backend_is_fallback_only" in report["blockers"]
    assert report["safe_context"]["raw_source_text_included"] is False
    assert report["safe_context"]["raw_vector_values_included"] is False


def test_production_hash_fallback_fails_fast():
    with pytest.raises(RuntimeError):
        validate_retrieval_vector_startup_config(_settings(APP_ENV="production"))


def test_production_semantic_backend_passes_when_all_flags_are_attested():
    report = validate_retrieval_vector_startup_config(
        _settings(
            APP_ENV="production",
            RETRIEVAL_EMBEDDING_BACKEND="semantic",
            RETRIEVAL_EMBEDDING_MODEL="synthetic-approved-semantic-v1",
            RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
            RETRIEVAL_VECTOR_BACKEND="pgvector",
            RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
            RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
            RETRIEVAL_PRIVATE_EMBEDDING_URL="https://embedding-provider.example/v1/embed",
            RETRIEVAL_PRIVATE_EMBEDDING_TOKEN="synthetic-token",
            RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS=128,
        )
    )

    assert report["startup_ready"] is True
    assert report["fail_fast_required"] is False
    assert report["blockers"] == []
    assert report["private_embedding_provider_ready"] is True
    assert report["private_embedding_endpoint_configured"] is True


def test_vector_backend_url_or_credentials_are_not_emitted():
    raw_backend = "postgresql://runtime_user:runtime_pw@localhost:5432/vector"
    with pytest.raises(RuntimeError) as exc_info:
        validate_retrieval_vector_startup_config(
            _settings(
                APP_ENV="production",
                RETRIEVAL_EMBEDDING_BACKEND="semantic",
                RETRIEVAL_EMBEDDING_MODEL="synthetic-approved-semantic-v1",
                RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
                RETRIEVAL_VECTOR_BACKEND=raw_backend,
                RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
                RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
                RETRIEVAL_PRIVATE_EMBEDDING_URL="https://embedding-provider.example/v1/embed",
                RETRIEVAL_PRIVATE_EMBEDDING_TOKEN="synthetic-token",
                RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS=128,
            )
        )

    serialized = json.dumps(getattr(exc_info.value, "__dict__", {}), sort_keys=True)
    assert raw_backend not in str(exc_info.value)
    assert raw_backend not in serialized


def test_semantic_backend_requires_private_provider_configuration_without_emitting_url():
    raw_endpoint = "http://embedding-provider.example/v1/embed"
    with pytest.raises(RuntimeError) as exc_info:
        validate_retrieval_vector_startup_config(
            _settings(
                APP_ENV="production",
                RETRIEVAL_EMBEDDING_BACKEND="semantic",
                RETRIEVAL_EMBEDDING_MODEL="synthetic-approved-semantic-v1",
                RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
                RETRIEVAL_VECTOR_BACKEND="pgvector",
                RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
                RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
                RETRIEVAL_PRIVATE_EMBEDDING_URL=raw_endpoint,
                RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS=128,
            )
        )

    serialized = json.dumps(getattr(exc_info.value, "__dict__", {}), sort_keys=True)
    assert raw_endpoint not in str(exc_info.value)
    assert raw_endpoint not in serialized
