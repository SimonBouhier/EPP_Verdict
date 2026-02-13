"""
Anthropic provider implementation.

Implements the Anthropic Messages API for Claude models.
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


class AnthropicProvider(ModelProvider):
    """
    Anthropic API provider for Claude models.

    Implements the Messages API format with separated system prompts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307",
        timeout: float = 120.0,
        anthropic_version: str = "2023-06-01",
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., claude-3-haiku-20240307)
            timeout: Request timeout in seconds
            anthropic_version: API version header
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.anthropic_version = anthropic_version
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure HTTP client is initialized."""
        if not self._initialized or self._client is None:
            if not self.api_key:
                raise ValueError("Anthropic API key is required")

            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            }

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers=headers,
            )
            self._initialized = True
            logger.info(f"[AnthropicProvider] Initialized for model {self.model}")

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """
        Generate response using Anthropic Messages API.

        Args:
            query: Structured query with messages and parameters

        Returns:
            Normalized response
        """
        await self._ensure_initialized()

        start_time = time.time()

        try:
            # Anthropic requires system prompt separate from messages
            system_prompt = None
            messages = []

            for msg in query.messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    messages.append(msg)

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": query.max_tokens,
                "temperature": query.temperature,
                "top_p": query.top_p,
            }

            # Add system prompt if present
            if system_prompt:
                payload["system"] = system_prompt

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages", json=payload
            )
            response.raise_for_status()

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            # Extract text from content blocks
            text = ""
            for block in data.get("content", []):
                if block["type"] == "text":
                    text += block["text"]

            # Extract token usage
            usage = data.get("usage", {})
            tokens = {
                "prompt": usage.get("input_tokens", 0),
                "completion": usage.get("output_tokens", 0),
                "total": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }

            logger.info(
                f"[AnthropicProvider] {self.model} generated {len(text)} chars "
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
            logger.error(f"[AnthropicProvider] {self.model} failed: {error_msg}")

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
            logger.error(f"[AnthropicProvider] {self.model} failed: {error_msg}")

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
        List available models.

        Anthropic doesn't provide a models endpoint, so we return known models.

        Returns:
            List of known Claude models
        """
        # Known Claude models as of January 2025
        known_models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ]

        logger.debug(f"[AnthropicProvider] Returning {len(known_models)} known models")
        return known_models

    async def health_check(self) -> Dict[str, Any]:
        """
        Check API health by attempting a minimal request.

        Returns:
            Dict with status and latency
        """
        await self._ensure_initialized()

        start_time = time.time()

        try:
            # Minimal request to check health
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 10,
            }

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages", json=payload
            )
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
        # Infer context window from model name
        context_window = 200000  # Claude 3 default
        if "opus" in self.model:
            context_window = 200000
        elif "sonnet" in self.model:
            context_window = 200000
        elif "haiku" in self.model:
            context_window = 200000

        return ModelMetadata(
            provider_id="anthropic",
            model_id=self.model,
            architecture_family="transformer_dense",
            context_window=context_window,
            supports_vram_management=False,
        )


# Factory function

async def create_anthropic_provider(
    api_key: Optional[str] = None,
    model: str = "claude-3-haiku-20240307",
) -> AnthropicProvider:
    """
    Create Anthropic provider.

    Environment variables:
        ANTHROPIC_API_KEY: API key

    Args:
        api_key: Override API key
        model: Model to use

    Returns:
        AnthropicProvider instance
    """
    import os

    actual_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    provider = AnthropicProvider(
        api_key=actual_key,
        model=model,
    )
    await provider._ensure_initialized()
    return provider
