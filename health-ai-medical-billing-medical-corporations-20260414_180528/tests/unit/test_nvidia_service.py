import logging

import httpx
import pytest

from app.services.nvidia import (
    NvidiaService,
    NvidiaServiceError,
    validate_nvidia_startup_config,
)


def _service() -> NvidiaService:
    service = NvidiaService()
    service.api_key = "synthetic-test-key"
    service.base_url = "https://synthetic-nvidia.example/v1"
    service.retry_backoff_seconds = 0.25
    service.retry_max_backoff_seconds = 1.0
    service.slow_request_threshold_seconds = 999
    return service


def _chat_response(status_code: int, content: str = "Synthetic approved response") -> httpx.Response:
    request = httpx.Request(
        "POST",
        "https://synthetic-nvidia.example/v1/chat/completions",
    )
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": content}}]},
        request=request,
    )


def _settings(**overrides):
    defaults = {
        "APP_ENV": "development",
        "LLM_PROVIDER": "nvidia_nim",
        "OCR_ENGINE": "nvidia_nemotron_parse",
        "NVIDIA_API_KEY": "synthetic-test-key",
        "NVIDIA_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "NVIDIA_MODEL": "synthetic-chat-model",
        "NVIDIA_OCR_MODEL": "synthetic-ocr-model",
        "NVIDIA_TIMEOUT": 120,
    }
    defaults.update(overrides)
    return type("SyntheticSettings", (), defaults)()


def test_validate_nvidia_startup_config_passes_with_safe_metadata(caplog):
    with caplog.at_level(logging.INFO, logger="app.services.nvidia"):
        result = validate_nvidia_startup_config(_settings())

    assert result["startup_ready"] is True
    assert result["blockers"] == []
    assert result["api_key_present"] is True
    assert result["safe_context"]["raw_api_key_included"] is False
    assert result["safe_context"]["raw_authorization_header_included"] is False
    log_payload = caplog.records[-1].nvidia_startup_config
    assert log_payload["startup_ready"] is True
    assert "synthetic-test-key" not in str(log_payload)


def test_validate_nvidia_startup_config_warns_in_development_without_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.nvidia"):
        result = validate_nvidia_startup_config(
            _settings(
                NVIDIA_API_KEY="",
                NVIDIA_BASE_URL="http://synthetic.example/v1",
            )
        )

    assert result["startup_ready"] is False
    assert result["fail_fast_required"] is False
    assert "nvidia_api_key_missing" in result["blockers"]
    assert "nvidia_base_url_not_https" in result["blockers"]
    log_payload = caplog.records[-1].nvidia_startup_config
    assert log_payload["safe_context"]["raw_api_key_included"] is False
    assert "NVIDIA_API_KEY" not in str(log_payload)


def test_validate_nvidia_startup_config_fails_fast_in_production():
    with pytest.raises(RuntimeError) as exc_info:
        validate_nvidia_startup_config(
            _settings(
                APP_ENV="production",
                NVIDIA_API_KEY="",
                NVIDIA_BASE_URL="https://synthetic.example/v1",
            )
        )

    assert str(exc_info.value) == "NVIDIA startup configuration is not production-ready."


def test_validate_nvidia_startup_config_detects_embedded_base_url_credentials():
    result = validate_nvidia_startup_config(
        _settings(NVIDIA_BASE_URL="https://user:secret" + chr(64) + "synthetic.example/v1")
    )

    assert result["startup_ready"] is False
    assert "nvidia_base_url_contains_credentials" in result["blockers"]
    assert result["base_url_credentials_present"] is True


def test_validate_nvidia_startup_config_does_not_block_non_nvidia_runtime():
    result = validate_nvidia_startup_config(
        _settings(
            LLM_PROVIDER="deterministic_fallback",
            OCR_ENGINE="tesseract",
            NVIDIA_API_KEY="",
            NVIDIA_BASE_URL="http://user:secret" + chr(64) + "synthetic.example/v1",
            NVIDIA_MODEL="",
            NVIDIA_OCR_MODEL="",
            NVIDIA_TIMEOUT=0,
        )
    )

    assert result["nvidia_required"] is False
    assert result["startup_ready"] is True
    assert result["blockers"] == []
    assert result["base_url_credentials_present"] is True


@pytest.mark.asyncio
async def test_chat_completion_retries_connect_errors_with_safe_metadata(monkeypatch, caplog):
    service = _service()
    service.max_retries = 2
    calls = 0
    delays = []

    async def fake_post_chat_completion(*, payload, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("synthetic connection unavailable")
        return _chat_response(200)

    async def fake_sleep(delay_seconds):
        delays.append(delay_seconds)

    monkeypatch.setattr(service, "_post_chat_completion", fake_post_chat_completion)
    monkeypatch.setattr(service, "_sleep_before_retry", fake_sleep)

    with caplog.at_level(logging.WARNING, logger="app.services.nvidia"):
        result = await service.chat_completion(
            messages=[{"role": "user", "content": "Synthetic denial summary"}],
            model="synthetic-model",
        )

    assert result == "Synthetic approved response"
    assert calls == 3
    assert delays == [0.25, 0.5]
    retry_metadata = [
        record.nvidia_retry
        for record in caplog.records
        if hasattr(record, "nvidia_retry")
    ]
    assert [item["attempt"] for item in retry_metadata] == [1, 2]
    assert {item["error_code"] for item in retry_metadata} == {"nvidia_unavailable_retry"}
    assert all(item["raw_prompt_included"] is False for item in retry_metadata)
    assert all(item["raw_response_included"] is False for item in retry_metadata)


@pytest.mark.asyncio
async def test_chat_completion_retries_retriable_status_codes(monkeypatch):
    service = _service()
    service.max_retries = 1
    calls = 0
    delays = []

    async def fake_post_chat_completion(*, payload, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _chat_response(503, "temporary unavailable")
        return _chat_response(200, "Recovered synthetic response")

    async def fake_sleep(delay_seconds):
        delays.append(delay_seconds)

    monkeypatch.setattr(service, "_post_chat_completion", fake_post_chat_completion)
    monkeypatch.setattr(service, "_sleep_before_retry", fake_sleep)

    result = await service.chat_completion(
        messages=[{"role": "user", "content": "Synthetic appeal prompt"}],
        model="synthetic-model",
    )

    assert result == "Recovered synthetic response"
    assert calls == 2
    assert delays == [0.25]


@pytest.mark.asyncio
async def test_chat_completion_does_not_retry_non_retriable_status(monkeypatch, caplog):
    service = _service()
    service.max_retries = 2
    calls = 0
    delays = []

    async def fake_post_chat_completion(*, payload, timeout):
        nonlocal calls
        calls += 1
        return _chat_response(400, "bad synthetic request")

    async def fake_sleep(delay_seconds):
        delays.append(delay_seconds)

    monkeypatch.setattr(service, "_post_chat_completion", fake_post_chat_completion)
    monkeypatch.setattr(service, "_sleep_before_retry", fake_sleep)

    with caplog.at_level(logging.ERROR, logger="app.services.nvidia"):
        with pytest.raises(NvidiaServiceError) as exc_info:
            await service.chat_completion(
                messages=[{"role": "user", "content": "Synthetic malformed prompt"}],
                model="synthetic-model",
            )

    assert exc_info.value.error_type == "nvidia_http_status_error"
    assert calls == 1
    assert delays == []
    error_metadata = caplog.records[-1].nvidia_error
    assert error_metadata["status_code"] == 400
    assert error_metadata["retriable"] is False
    assert error_metadata["raw_prompt_included"] is False
    assert error_metadata["raw_response_included"] is False


@pytest.mark.asyncio
async def test_chat_completion_logs_slow_request_without_raw_content(monkeypatch, caplog):
    service = _service()
    service.max_retries = 0
    service.slow_request_threshold_seconds = 0

    async def fake_post_chat_completion(*, payload, timeout):
        return _chat_response(200, "Synthetic slow response")

    monkeypatch.setattr(service, "_post_chat_completion", fake_post_chat_completion)

    with caplog.at_level(logging.WARNING, logger="app.services.nvidia"):
        result = await service.chat_completion(
            messages=[{"role": "user", "content": "Synthetic slow prompt"}],
            model="synthetic-model",
        )

    assert result == "Synthetic slow response"
    request_metadata = caplog.records[-1].nvidia_request
    assert request_metadata["endpoint"] == "chat_completions"
    assert request_metadata["attempt_count"] == 1
    assert request_metadata["raw_prompt_included"] is False
    assert request_metadata["raw_response_included"] is False
