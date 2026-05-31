from typing import Any

import httpx

from app.core.config import settings
from app.services.nvidia import nvidia_service


class LLMProviderError(Exception):
    def __init__(self, message: str, error_type: str, provider: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.provider = provider
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {
            "error": self.error_type,
            "message": self.message,
            "provider": self.provider,
        }


class OpenAICompatibleLLMService:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: int = 120,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
            response.raise_for_status()
            status = "ok"
        except Exception as exc:
            return {
                "status": "unavailable",
                "provider": self.provider,
                "base_url": self.base_url,
                "model": self.model,
                "error": type(exc).__name__,
            }
        return {
            "status": status,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
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
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"{self.provider} is unavailable.",
                "llm_provider_unavailable",
                self.provider,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"{self.provider} returned an HTTP error.",
                "llm_provider_http_error",
                self.provider,
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"{self.provider} request failed.",
                "llm_provider_request_failed",
                self.provider,
            ) from exc

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
            raise LLMProviderError(
                f"{self.provider} returned an empty response.",
                "llm_provider_empty_response",
                self.provider,
            )
        return content


mlx_service = OpenAICompatibleLLMService(
    provider="mlx_lm",
    base_url=settings.MLX_BASE_URL,
    model=settings.MLX_MODEL,
    timeout=settings.MLX_TIMEOUT,
)


def get_configured_llm_service():
    if settings.LLM_PROVIDER == "mlx_lm":
        return mlx_service
    if settings.LLM_PROVIDER == "nvidia_nim":
        return nvidia_service
    return mlx_service
