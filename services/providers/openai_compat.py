"""
OpenAI-compatible provider implementation.

Supports any API that implements the OpenAI /v1/chat/completions format:
- OpenAI (GPT-4o-mini, GPT-4o, etc.)
- Kimi K2.5
- DeepSeek
- Other OpenAI-compatible APIs
"""

import time
import logging
from typing import List, Dict, Any, Optional
import httpx

from services.providers.base import (
    ModelProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)

logger = logging.getLogger(__name__)


class OpenAICompatProvider(ModelProvider):
    """
    OpenAI-compatible API provider.

    Works with any service that implements the OpenAI API format.
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 120.0,
        organization: Optional[str] = None,
    ):
        """
        Initialize OpenAI-compatible provider.

        Args:
            base_url: API base URL (e.g., "https://api.openai.com/v1")
            api_key: API key for authentication
            model: Model identifier
            timeout: Request timeout in seconds
            organization: Optional organization ID (OpenAI-specific)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.organization = organization
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure HTTP client is initialized."""
        if not self._initialized or self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.organization:
                headers["OpenAI-Organization"] = self.organization

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers=headers,
            )
            self._initialized = True
            logger.info(f"[OpenAICompatProvider] Initialized, base_url={self.base_url}")

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """
        Generate response using OpenAI-compatible API.

        Args:
            query: Structured query with messages and parameters

        Returns:
            Normalized response
        """
        await self._ensure_initialized()

        start_time = time.time()

        try:
            payload = {
                "model": self.model,
                "messages": query.messages,
                "temperature": query.temperature,
                "max_tokens": query.max_tokens,
                "top_p": query.top_p,
                "frequency_penalty": query.repeat_penalty - 1.0,  # Map repeat_penalty
                "presence_penalty": 0.0,
                "stream": False,
            }

            response = await self._client.post(
                f"{self.base_url}/chat/completions", json=payload
            )
            response.raise_for_status()

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            # Extract text from first choice
            text = data["choices"][0]["message"]["content"]

            # Extract token usage
            usage = data.get("usage", {})
            tokens = {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            }

            logger.info(
                f"[OpenAICompatProvider] {self.model} generated {len(text)} chars "
                f"in {latency_ms:.0f}ms"
            )

            return StructuredResponse(
                text=text,
                tokens=tokens,
                latency_ms=latency_ms,
                model=self.model,
                success=True,
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"[OpenAICompatProvider] {self.model} failed: {error_msg}")

            return StructuredResponse(
                text="",
                tokens={"prompt": 0, "completion": 0, "total": 0},
                latency_ms=latency_ms,
                model=self.model,
                success=False,
                error=error_msg,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"[OpenAICompatProvider] {self.model} failed: {error_msg}")

            return StructuredResponse(
                text="",
                tokens={"prompt": 0, "completion": 0, "total": 0},
                latency_ms=latency_ms,
                model=self.model,
                success=False,
                error=error_msg,
            )

    async def list_models(self) -> List[str]:
        """
        List available models (if supported by the API).

        Not all OpenAI-compatible APIs support /v1/models endpoint.

        Returns:
            List of model names, or [self.model] if listing not supported
        """
        await self._ensure_initialized()

        try:
            response = await self._client.get(f"{self.base_url}/models")
            response.raise_for_status()

            data = response.json()
            models = [m["id"] for m in data.get("data", [])]
            logger.debug(f"[OpenAICompatProvider] Found {len(models)} models")
            return models

        except Exception as e:
            logger.warning(
                f"[OpenAICompatProvider] Failed to list models (not supported?): {e}"
            )
            # Fallback: return the configured model
            return [self.model]

    async def health_check(self) -> Dict[str, Any]:
        """
        Check API health by attempting to list models.

        Returns:
            Dict with status and latency
        """
        await self._ensure_initialized()

        start_time = time.time()

        try:
            # Try to list models as a health check
            response = await self._client.get(f"{self.base_url}/models")
            response.raise_for_status()

            latency_ms = (time.time() - start_time) * 1000

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "model": self.model,
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "status": "unhealthy",
                "connected": False,
                "latency_ms": latency_ms,
                "error": str(e),
            }

    def get_metadata(self) -> ModelMetadata:
        """
        Get provider metadata.

        Returns:
            Metadata with provider and model info
        """
        # Infer architecture family from model name (heuristic)
        architecture = "transformer_dense"
        if "mixtral" in self.model.lower() or "moe" in self.model.lower():
            architecture = "transformer_moe"

        return ModelMetadata(
            provider_id="openai_compat",
            model_id=self.model,
            architecture_family=architecture,
            context_window=8192,  # Default, should be configurable
            supports_vram_management=False,
        )


# Factory functions for specific providers

async def create_openai_provider(
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    organization: Optional[str] = None,
) -> OpenAICompatProvider:
    """
    Create OpenAI provider (official API).

    Environment variables:
        OPENAI_API_KEY: API key

    Args:
        api_key: Override API key
        model: Model to use
        organization: Organization ID

    Returns:
        OpenAICompatProvider configured for OpenAI
    """
    import os

    actual_key = api_key or os.environ.get("OPENAI_API_KEY")
    provider = OpenAICompatProvider(
        base_url="https://api.openai.com/v1",
        api_key=actual_key,
        model=model,
        organization=organization,
    )
    await provider._ensure_initialized()
    return provider


async def create_kimi_provider(
    api_key: Optional[str] = None,
    model: str = "moonshot-v1-8k",
) -> OpenAICompatProvider:
    """
    Create Kimi K2.5 provider (Moonshot AI).

    Environment variables:
        KIMI_API_KEY: API key

    Args:
        api_key: Override API key
        model: Model to use

    Returns:
        OpenAICompatProvider configured for Kimi
    """
    import os

    actual_key = api_key or os.environ.get("KIMI_API_KEY")
    provider = OpenAICompatProvider(
        base_url="https://api.moonshot.cn/v1",
        api_key=actual_key,
        model=model,
    )
    await provider._ensure_initialized()
    return provider


async def create_deepseek_provider(
    api_key: Optional[str] = None,
    model: str = "deepseek-chat",
) -> OpenAICompatProvider:
    """
    Create DeepSeek provider.

    Environment variables:
        DEEPSEEK_API_KEY: API key

    Args:
        api_key: Override API key
        model: Model to use

    Returns:
        OpenAICompatProvider configured for DeepSeek
    """
    import os

    actual_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    provider = OpenAICompatProvider(
        base_url="https://api.deepseek.com/v1",
        api_key=actual_key,
        model=model,
    )
    await provider._ensure_initialized()
    return provider
