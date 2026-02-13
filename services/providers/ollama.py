"""
Ollama provider implementation.

Adapts local Ollama models to the universal ModelProvider interface.
Includes VRAM management via keep_alive parameter.
"""

import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx

from services.providers.base import (
    ModelProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)

logger = logging.getLogger(__name__)


class OllamaProvider(ModelProvider):
    """
    Ollama provider with VRAM management.

    Features:
    - Sequential model loading/unloading via keep_alive
    - Health checking
    - Model listing
    - Connection pooling
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: Optional[str] = None,
        timeout: float = 120.0,
        num_ctx: int = 8192,
        unload_delay_ms: float = 100.0,
        max_retries: int = 3,
    ):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama server URL
            model: Default model name (can be None if specified in queries)
            timeout: Request timeout in seconds
            num_ctx: Context window size
            unload_delay_ms: Delay after unload before next operation
            max_retries: Maximum retry attempts on network errors (default: 3)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.unload_delay_ms = unload_delay_ms
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure HTTP client is initialized."""
        if not self._initialized or self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=30.0,
                ),
            )
            self._initialized = True
            logger.info(f"[OllamaProvider] Initialized, base_url={self.base_url}")

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """
        Generate response using Ollama with retry logic.

        Args:
            query: Structured query with messages and parameters

        Returns:
            Normalized response
        """
        await self._ensure_initialized()

        # Determine which model to use
        model_to_use = self.model
        if not model_to_use:
            raise ValueError("No model specified in OllamaProvider and none in query")

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            start_time = time.time()

            try:
                # Use keep_alive from query if specified, otherwise default to 0 (unload)
                keep_alive_value = query.keep_alive if query.keep_alive is not None else 0

                payload = {
                    "model": model_to_use,
                    "messages": query.messages,
                    "stream": False,
                    "keep_alive": keep_alive_value,
                    "options": {
                        "temperature": query.temperature,
                        "num_predict": query.max_tokens,
                        "num_ctx": query.context_window or self.num_ctx,
                        "top_k": query.top_k or 40,
                        "top_p": query.top_p,
                        "repeat_penalty": query.repeat_penalty,
                    },
                }

                response = await self._client.post(
                    f"{self.base_url}/api/chat", json=payload
                )
                response.raise_for_status()

                data = response.json()
                latency_ms = (time.time() - start_time) * 1000

                # Extract text
                text = data.get("message", {}).get("content", "")

                if not text:
                    raise ValueError("Empty response from Ollama")

                # Extract tokens (Ollama provides accurate counts)
                tokens = {
                    "prompt": data.get("prompt_eval_count", 0),
                    "completion": data.get("eval_count", 0),
                    "total": 0,
                }
                tokens["total"] = tokens["prompt"] + tokens["completion"]

                logger.info(
                    f"[OllamaProvider] {model_to_use} generated {len(text)} chars "
                    f"in {latency_ms:.0f}ms"
                )

                # Brief delay for VRAM release
                if self.unload_delay_ms > 0:
                    await asyncio.sleep(self.unload_delay_ms / 1000)

                return StructuredResponse(
                    text=text,
                    tokens=tokens,
                    latency_ms=latency_ms,
                    model=model_to_use,
                    success=True,
                    raw_response=data,
                )

            except httpx.HTTPStatusError as e:
                latency_ms = (time.time() - start_time) * 1000
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

                # Don't retry on 404 (model not found)
                if e.response.status_code == 404:
                    logger.error(f"[OllamaProvider] Model {model_to_use} not found: {last_error}")
                    break

            except httpx.RequestError as e:
                latency_ms = (time.time() - start_time) * 1000
                last_error = f"Network error: {str(e)}"

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                last_error = f"Unexpected error: {str(e)}"

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"[OllamaProvider] Retry attempt {attempt + 1}/{self.max_retries} "
                    f"for {model_to_use}, waiting {wait_time}s... ({last_error})"
                )
                await asyncio.sleep(wait_time)

        # All retries failed
        final_error = f"Failed after {self.max_retries} attempts: {last_error}"
        logger.error(f"[OllamaProvider] {model_to_use} {final_error}")

        return StructuredResponse(
            text="",
            tokens={"prompt": 0, "completion": 0, "total": 0},
            latency_ms=0.0,
            model=model_to_use,
            success=False,
            error=final_error,
        )

    async def list_models(self) -> List[str]:
        """
        List available models on Ollama server.

        Returns:
            List of model names (e.g., ["mistral:7b", "llama3.1:8b"])
        """
        await self._ensure_initialized()

        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            logger.debug(f"[OllamaProvider] Found {len(models)} models")
            return models

        except Exception as e:
            logger.error(f"[OllamaProvider] Failed to list models: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Ollama server health.

        Returns:
            Dict with status, available models, latency
        """
        await self._ensure_initialized()

        start_time = time.time()

        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]

            is_available = self.model in models if self.model else len(models) > 0

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "models_available": len(models),
                "models": models,
                "default_model": self.model,
                "default_model_available": is_available,
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
        return ModelMetadata(
            provider_id="ollama",
            model_id=self.model or "unknown",
            architecture_family="unknown",  # Ollama doesn't expose this
            context_window=self.num_ctx,
            supports_vram_management=True,
        )

    # VRAM management (Ollama-specific)

    async def preload_model(self, model: str, keep_alive: str = "5m") -> bool:
        """
        Preload a model into VRAM.

        Args:
            model: Model name
            keep_alive: How long to keep model loaded

        Returns:
            True if successful
        """
        await self._ensure_initialized()

        try:
            payload = {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": keep_alive,
                "options": {"num_predict": 0},
            }

            logger.info(f"[OllamaProvider] Preloading {model}...")
            response = await self._client.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            logger.info(f"[OllamaProvider] {model} preloaded")
            return True

        except Exception as e:
            logger.warning(f"[OllamaProvider] Preload failed for {model}: {e}")
            return False

    async def unload_model(self, model: str) -> bool:
        """
        Unload a model from VRAM.

        Args:
            model: Model name

        Returns:
            True if successful
        """
        await self._ensure_initialized()

        try:
            payload = {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,  # Unload immediately
                "options": {"num_predict": 0},
            }

            response = await self._client.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            logger.debug(f"[OllamaProvider] {model} unloaded")

            # Brief delay for VRAM release
            if self.unload_delay_ms > 0:
                await asyncio.sleep(self.unload_delay_ms / 1000)

            return True

        except Exception as e:
            logger.warning(f"[OllamaProvider] Unload failed for {model}: {e}")
            return False


# Singleton instance
_ollama_instance: Optional[OllamaProvider] = None


async def get_ollama_provider(
    base_url: str = None,
    model: str = None,
    num_ctx: int = None,
) -> OllamaProvider:
    """
    Get or create singleton Ollama provider.

    Environment variables:
        LYRA_OLLAMA_URL: Ollama base URL (default: http://localhost:11434)
        LYRA_MODEL: Default model name
        LYRA_NUM_CTX: Context window size (default: 8192)

    Args:
        base_url: Override base URL
        model: Override model
        num_ctx: Override context window

    Returns:
        OllamaProvider instance
    """
    global _ollama_instance

    if _ollama_instance is None:
        import os

        actual_url = base_url or os.environ.get(
            "LYRA_OLLAMA_URL", "http://localhost:11434"
        )
        actual_model = model or os.environ.get("LYRA_MODEL", "gpt-oss:20b")
        actual_ctx = num_ctx or int(os.environ.get("LYRA_NUM_CTX", "8192"))

        logger.info(
            f"Initializing OllamaProvider with model: {actual_model}, context: {actual_ctx} tokens"
        )
        _ollama_instance = OllamaProvider(
            base_url=actual_url, model=actual_model, num_ctx=actual_ctx
        )
        await _ollama_instance._ensure_initialized()

    return _ollama_instance


async def close_ollama_provider() -> None:
    """Close singleton Ollama provider."""
    global _ollama_instance

    if _ollama_instance:
        await _ollama_instance.close()
        _ollama_instance = None
