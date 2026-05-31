import base64
import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

NVIDIA_CHAT_MAX_RETRIES = 2
NVIDIA_CHAT_RETRY_BACKOFF_SECONDS = 0.5
NVIDIA_CHAT_RETRY_MAX_BACKOFF_SECONDS = 4.0
NVIDIA_SLOW_REQUEST_THRESHOLD_SECONDS = 30.0
NVIDIA_RETRIABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
NVIDIA_REQUIRED_PROVIDERS = {"nvidia_nim", "nvidia_nemotron_parse"}


class NvidiaServiceError(Exception):
    def __init__(self, message: str, error_type: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {
            "error": self.error_type,
            "message": self.message,
            "provider": "nvidia_nim",
        }


def validate_nvidia_startup_config(settings_like=None) -> dict[str, Any]:
    runtime_settings = settings_like or settings
    app_env = str(getattr(runtime_settings, "APP_ENV", "development") or "development").lower()
    llm_provider = str(getattr(runtime_settings, "LLM_PROVIDER", "") or "")
    ocr_engine = str(getattr(runtime_settings, "OCR_ENGINE", "") or "")
    nvidia_required = (
        llm_provider in NVIDIA_REQUIRED_PROVIDERS
        or ocr_engine in NVIDIA_REQUIRED_PROVIDERS
    )
    base_url = str(getattr(runtime_settings, "NVIDIA_BASE_URL", "") or "").strip()
    api_key = str(getattr(runtime_settings, "NVIDIA_API_KEY", "") or "")
    model = str(getattr(runtime_settings, "NVIDIA_MODEL", "") or "").strip()
    ocr_model = str(getattr(runtime_settings, "NVIDIA_OCR_MODEL", "") or "").strip()
    timeout = getattr(runtime_settings, "NVIDIA_TIMEOUT", None)
    parsed_base_url = urlparse(base_url)
    blockers: list[str] = []

    if nvidia_required and not api_key.strip():
        blockers.append("nvidia_api_key_missing")
    if nvidia_required and not model:
        blockers.append("nvidia_model_missing")
    if nvidia_required and ocr_engine == "nvidia_nemotron_parse" and not ocr_model:
        blockers.append("nvidia_ocr_model_missing")
    if nvidia_required and parsed_base_url.scheme != "https":
        blockers.append("nvidia_base_url_not_https")
    if nvidia_required and not parsed_base_url.netloc:
        blockers.append("nvidia_base_url_missing_host")
    if nvidia_required and (parsed_base_url.username or parsed_base_url.password):
        blockers.append("nvidia_base_url_contains_credentials")
    try:
        timeout_value = int(timeout)
    except (TypeError, ValueError):
        if nvidia_required:
            blockers.append("nvidia_timeout_invalid")
        timeout_value = None
    else:
        if nvidia_required and timeout_value <= 0:
            blockers.append("nvidia_timeout_invalid")

    safe_context = {
        "raw_api_key_included": False,
        "raw_authorization_header_included": False,
        "raw_prompt_included": False,
        "raw_response_included": False,
        "raw_ocr_bytes_included": False,
        "raw_document_text_included": False,
    }
    report = {
        "provider": "nvidia_nim",
        "app_env": app_env,
        "nvidia_required": nvidia_required,
        "llm_provider": llm_provider,
        "ocr_engine": ocr_engine,
        "api_key_present": bool(api_key.strip()),
        "base_url_scheme": parsed_base_url.scheme or None,
        "base_url_host_present": bool(parsed_base_url.netloc),
        "base_url_credentials_present": bool(parsed_base_url.username or parsed_base_url.password),
        "model_present": bool(model),
        "ocr_model_present": bool(ocr_model),
        "timeout_seconds": timeout_value,
        "blockers": blockers,
        "startup_ready": not blockers,
        "fail_fast_required": app_env == "production" and bool(blockers),
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
            "nvidia_startup_config_validation_failed",
            extra={"nvidia_startup_config": log_payload},
        )
    else:
        logger.info(
            "nvidia_startup_config_validation_passed",
            extra={"nvidia_startup_config": log_payload},
        )
    if report["fail_fast_required"]:
        raise RuntimeError("NVIDIA startup configuration is not production-ready.")
    return report


class NvidiaService:
    def __init__(self):
        self.base_url = settings.NVIDIA_BASE_URL.rstrip("/")
        self.api_key = settings.NVIDIA_API_KEY
        self.model = settings.NVIDIA_MODEL
        self.ocr_model = settings.NVIDIA_OCR_MODEL
        self.timeout = settings.NVIDIA_TIMEOUT
        self.max_retries = NVIDIA_CHAT_MAX_RETRIES
        self.retry_backoff_seconds = NVIDIA_CHAT_RETRY_BACKOFF_SECONDS
        self.retry_max_backoff_seconds = NVIDIA_CHAT_RETRY_MAX_BACKOFF_SECONDS
        self.slow_request_threshold_seconds = NVIDIA_SLOW_REQUEST_THRESHOLD_SECONDS

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise NvidiaServiceError(
                "NVIDIA_API_KEY is not configured.",
                "nvidia_api_key_missing",
                status_code=503,
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def health_check(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "status": "missing_api_key",
                "provider": "nvidia_nim",
                "base_url": self.base_url,
                "model": self.model,
                "ocr_model": self.ocr_model,
            }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
            response.raise_for_status()
            return {
                "status": "ok",
                "provider": "nvidia_nim",
                "base_url": self.base_url,
                "model": self.model,
                "ocr_model": self.ocr_model,
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "provider": "nvidia_nim",
                "base_url": self.base_url,
                "model": self.model,
                "ocr_model": self.ocr_model,
                "error": type(exc).__name__,
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        timeout: int | None = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat_completion(
            messages=messages,
            model=model or self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        timeout: int | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        request_timeout = timeout or self.timeout
        response, attempt_count, elapsed_seconds = await self._post_chat_completion_with_retry(
            payload=payload,
            model=model,
            timeout=request_timeout,
        )
        self._log_slow_request(
            model=model,
            timeout=request_timeout,
            attempt_count=attempt_count,
            elapsed_seconds=elapsed_seconds,
        )

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content is None:
            content = ""
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        content = str(content).strip()
        if not content:
            raise NvidiaServiceError(
                "NVIDIA NIM returned an empty response.",
                "nvidia_empty_response",
                status_code=503,
            )
        return content

    async def _post_chat_completion_with_retry(
        self,
        *,
        payload: dict[str, Any],
        model: str,
        timeout: int,
    ) -> tuple[httpx.Response, int, float]:
        max_attempts = max(1, 1 + int(self.max_retries))
        started_at = time.monotonic()
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                response = await self._post_chat_completion(payload=payload, timeout=timeout)
                response.raise_for_status()
                return response, attempt, time.monotonic() - started_at
            except NvidiaServiceError:
                raise
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if self._should_retry_status(status_code) and attempt < max_attempts:
                    await self._schedule_retry(
                        error_code="nvidia_http_status_retry",
                        model=model,
                        timeout=timeout,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        status_code=status_code,
                    )
                    continue
                logger.error(
                    "nvidia_http_status_error",
                    extra={
                        "nvidia_error": {
                            "error_code": "nvidia_http_status_error",
                            "provider": "nvidia_nim",
                            "endpoint": "chat_completions",
                            "status_code": status_code,
                            "model": model,
                            "attempt_count": attempt,
                            "max_attempts": max_attempts,
                            "retriable": self._should_retry_status(status_code),
                            "raw_prompt_included": False,
                            "raw_response_included": False,
                        }
                    },
                )
                raise NvidiaServiceError(
                    "NVIDIA NIM returned an HTTP error.",
                    "nvidia_http_status_error",
                    status_code=503,
                ) from exc
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt < max_attempts:
                    await self._schedule_retry(
                        error_code="nvidia_unavailable_retry",
                        model=model,
                        timeout=timeout,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        exception_type=type(exc).__name__,
                    )
                    continue
                logger.error(
                    "nvidia_unavailable",
                    extra={
                        "nvidia_error": {
                            "error_code": "nvidia_unavailable",
                            "provider": "nvidia_nim",
                            "endpoint": "chat_completions",
                            "model": model,
                            "attempt_count": attempt,
                            "max_attempts": max_attempts,
                            "exception_type": type(exc).__name__,
                            "raw_prompt_included": False,
                            "raw_response_included": False,
                        }
                    },
                )
                raise NvidiaServiceError(
                    "NVIDIA NIM is unavailable.",
                    "nvidia_unavailable",
                    status_code=503,
                ) from exc
            except Exception as exc:
                logger.error(
                    "nvidia_request_failed",
                    extra={
                        "nvidia_error": {
                            "error_code": "nvidia_request_failed",
                            "provider": "nvidia_nim",
                            "endpoint": "chat_completions",
                            "model": model,
                            "attempt_count": attempt,
                            "max_attempts": max_attempts,
                            "exception_type": type(exc).__name__,
                            "raw_prompt_included": False,
                            "raw_response_included": False,
                        }
                    },
                )
                raise NvidiaServiceError(
                    "NVIDIA NIM request failed.",
                    "nvidia_request_failed",
                    status_code=503,
                ) from exc

        raise NvidiaServiceError(
            "NVIDIA NIM request failed.",
            "nvidia_request_failed",
            status_code=503,
        )

    async def _post_chat_completion(
        self,
        *,
        payload: dict[str, Any],
        timeout: int,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        return status_code in NVIDIA_RETRIABLE_STATUS_CODES

    def _retry_delay(self, attempt: int) -> float:
        delay = self.retry_backoff_seconds * (2 ** max(0, attempt - 1))
        return min(delay, self.retry_max_backoff_seconds)

    async def _schedule_retry(
        self,
        *,
        error_code: str,
        model: str,
        timeout: int,
        attempt: int,
        max_attempts: int,
        status_code: int | None = None,
        exception_type: str | None = None,
    ) -> None:
        delay_seconds = self._retry_delay(attempt)
        logger.warning(
            "nvidia_retry_scheduled",
            extra={
                "nvidia_retry": {
                    "error_code": error_code,
                    "provider": "nvidia_nim",
                    "endpoint": "chat_completions",
                    "model": model,
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "delay_seconds": delay_seconds,
                    "timeout_seconds": timeout,
                    "status_code": status_code,
                    "exception_type": exception_type,
                    "raw_prompt_included": False,
                    "raw_response_included": False,
                }
            },
        )
        await self._sleep_before_retry(delay_seconds)

    async def _sleep_before_retry(self, delay_seconds: float) -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    def _log_slow_request(
        self,
        *,
        model: str,
        timeout: int,
        attempt_count: int,
        elapsed_seconds: float,
    ) -> None:
        if elapsed_seconds < self.slow_request_threshold_seconds:
            return
        logger.warning(
            "nvidia_slow_request",
            extra={
                "nvidia_request": {
                    "provider": "nvidia_nim",
                    "endpoint": "chat_completions",
                    "model": model,
                    "elapsed_ms": round(elapsed_seconds * 1000, 2),
                    "timeout_seconds": timeout,
                    "attempt_count": attempt_count,
                    "slow_threshold_seconds": self.slow_request_threshold_seconds,
                    "raw_prompt_included": False,
                    "raw_response_included": False,
                }
            },
        )

    async def transcribe_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str,
        timeout: int | None = None,
    ) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            }
        ]
        return await self.chat_completion(
            messages=messages,
            model=self.ocr_model,
            temperature=0,
            max_tokens=4096,
            timeout=timeout or settings.OCR_TIMEOUT,
        )


nvidia_service = NvidiaService()
