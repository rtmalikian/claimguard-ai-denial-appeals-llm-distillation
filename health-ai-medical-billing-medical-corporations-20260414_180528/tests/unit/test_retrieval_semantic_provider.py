import json
from types import SimpleNamespace

import pytest

from app.services.retrieval import HASH_EMBEDDING_MODEL, HashEmbeddingProvider
from app.services.retrieval_semantic_provider import (
    PrivateSemanticEmbeddingProvider,
    RetrievalEmbeddingProviderConfigError,
    RetrievalEmbeddingProviderError,
    build_retrieval_embedding_provider,
    private_embedding_provider_config_status,
)


def _settings(**overrides):
    values = {
        "RETRIEVAL_EMBEDDING_BACKEND": "hash",
        "RETRIEVAL_EMBEDDING_MODEL": HASH_EMBEDDING_MODEL,
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED": False,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": False,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": False,
        "RETRIEVAL_PRIVATE_EMBEDDING_URL": "",
        "RETRIEVAL_PRIVATE_EMBEDDING_TOKEN": "",
        "RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS": 0,
        "RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _semantic_settings(**overrides):
    values = {
        "RETRIEVAL_EMBEDDING_BACKEND": "private_semantic",
        "RETRIEVAL_EMBEDDING_MODEL": "synthetic-private-semantic-v1",
        "RETRIEVAL_EMBEDDING_MODEL_APPROVED": True,
        "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED": True,
        "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION": True,
        "RETRIEVAL_PRIVATE_EMBEDDING_URL": "https://embedding-provider.example/v1/embed",
        "RETRIEVAL_PRIVATE_EMBEDDING_TOKEN": "synthetic-token",
        "RETRIEVAL_PRIVATE_EMBEDDING_DIMENSIONS": 3,
        "RETRIEVAL_PRIVATE_EMBEDDING_TIMEOUT_SECONDS": 7,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_hash_backend_builds_default_hash_provider():
    provider = build_retrieval_embedding_provider(_settings())

    assert isinstance(provider, HashEmbeddingProvider)
    assert provider.model_name == HASH_EMBEDDING_MODEL


def test_private_provider_status_redacts_endpoint_and_token_values():
    raw_endpoint = "https://embedding-provider.example/v1/embed"
    raw_token = "synthetic-token"
    report = private_embedding_provider_config_status(
        _semantic_settings(
            RETRIEVAL_PRIVATE_EMBEDDING_URL=raw_endpoint,
            RETRIEVAL_PRIVATE_EMBEDDING_TOKEN=raw_token,
        )
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["provider_ready"] is True
    assert report["private_embedding_endpoint_configured"] is True
    assert report["private_embedding_token_configured"] is True
    assert report["safe_context"]["embedding_endpoint_value_included"] is False
    assert report["safe_context"]["embedding_token_value_included"] is False
    assert report["safe_context"]["private_embedding_endpoint_value_included"] is False
    assert report["safe_context"]["private_embedding_token_value_included"] is False
    assert raw_endpoint not in serialized
    assert raw_token not in serialized


def test_private_provider_requires_safe_endpoint_without_emitting_value():
    raw_endpoint = "http://embedding-provider.example/v1/embed"
    report = private_embedding_provider_config_status(
        _semantic_settings(RETRIEVAL_PRIVATE_EMBEDDING_URL=raw_endpoint)
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["provider_ready"] is False
    assert "private_embedding_endpoint_must_use_https_or_loopback" in report["blockers"]
    assert raw_endpoint not in serialized


def test_private_provider_builds_from_safe_runtime_config():
    provider = build_retrieval_embedding_provider(_semantic_settings())

    assert isinstance(provider, PrivateSemanticEmbeddingProvider)
    assert provider.backend_name == "private_semantic"
    assert provider.model_name == "synthetic-private-semantic-v1"
    assert provider.dimensions == 3


def test_private_provider_posts_text_and_returns_vector(monkeypatch):
    captured = {}

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(http_request.header_items())
        captured["body"] = http_request.data.decode("utf-8")
        return _FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr(
        "app.services.retrieval_semantic_provider.request.urlopen",
        fake_urlopen,
    )
    provider = build_retrieval_embedding_provider(_semantic_settings())
    result = provider.embed("Synthetic prior authorization appeal text")

    request_payload = json.loads(captured["body"])
    assert result.vector == [0.1, 0.2, 0.3]
    assert result.backend == "private_semantic"
    assert result.model == "synthetic-private-semantic-v1"
    assert request_payload["model"] == "synthetic-private-semantic-v1"
    assert request_payload["input"] == "Synthetic prior authorization appeal text"
    assert captured["headers"]["Authorization"] == "Bearer synthetic-token"
    assert captured["timeout"] == 7


def test_private_provider_errors_do_not_emit_raw_text_or_endpoint(monkeypatch):
    raw_text = "Synthetic source text that must not appear in errors"
    raw_endpoint = "https://embedding-provider.example/v1/embed"

    def fake_urlopen(http_request, timeout):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(
        "app.services.retrieval_semantic_provider.request.urlopen",
        fake_urlopen,
    )
    provider = build_retrieval_embedding_provider(
        _semantic_settings(RETRIEVAL_PRIVATE_EMBEDDING_URL=raw_endpoint)
    )

    with pytest.raises(RetrievalEmbeddingProviderError) as exc_info:
        provider.embed(raw_text)

    assert raw_text not in str(exc_info.value)
    assert raw_endpoint not in str(exc_info.value)


def test_private_provider_config_error_does_not_emit_endpoint():
    raw_endpoint = "http://embedding-provider.example/v1/embed"

    with pytest.raises(RetrievalEmbeddingProviderConfigError) as exc_info:
        build_retrieval_embedding_provider(
            _semantic_settings(RETRIEVAL_PRIVATE_EMBEDDING_URL=raw_endpoint)
        )

    assert raw_endpoint not in str(exc_info.value)
