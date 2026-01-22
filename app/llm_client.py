"""
LYRA CLEAN - ASYNC OLLAMA CLIENT
=================================

Non-blocking HTTP client for Ollama API.

Replaces:
- lyra_core/ollama_wrapper.py (blocking requests)

Key improvements:
- Async I/O (httpx instead of requests)
- Connection pooling
- Timeout handling
- Retry logic
"""
from __future__ import annotations

import httpx
import time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from core.physics import PhysicsState, map_tau_to_temperature, map_rho_to_penalties


class OllamaClient:
    """
    Async client for Ollama API.

    Features:
    - Non-blocking HTTP requests
    - Connection pooling (reuse TCP connections)
    - Automatic retries on network errors
    - Timeout protection
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gpt-oss:20b",
        timeout: float = 120.0,
        max_retries: int = 3
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL
            model: Default model name
            timeout: Request timeout (seconds)
            max_retries: Max retry attempts on failure
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """
        Initialize HTTP client with connection pooling.

        Must be called before making requests.
        """
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0
            )
        )

    async def close(self) -> None:
        """Close HTTP client and release connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def session(self):
        """
        Context manager for client lifecycle.

        Usage:
            async with client.session():
                response = await client.chat(...)
        """
        await self.initialize()
        try:
            yield self
        finally:
            await self.close()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if Ollama server is reachable.

        Returns:
            Dict with keys: connected (bool), models (list), error (str)

        Example:
            health = await client.health_check()
            if health["connected"]:
                print(f"Models: {health['models']}")
        """
        try:
            if not self._client:
                await self.initialize()

            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]

            return {
                "connected": True,
                "models": models,
                "model": self.model,
                "available": self.model in models
            }

        except Exception as e:
            return {
                "connected": False,
                "models": [],
                "error": str(e)
            }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        physics_state: PhysicsState,
        model: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Ollama.

        Args:
            messages: List of {role, content} dicts
            physics_state: Current physics state (for parameter mapping)
            model: Model override (uses default if None)
            stream: Enable streaming (not implemented yet)

        Returns:
            Dict with keys:
            - text: Generated response
            - model: Model used
            - latency_ms: Generation time
            - tokens: Token counts (approximate)

        Example:
            response = await client.chat(
                messages=[
                    {"role": "system", "content": "You are Lyra"},
                    {"role": "user", "content": "Hello"}
                ],
                physics_state=state
            )
            print(response["text"])
        """
        if not self._client:
            await self.initialize()

        # Map physics parameters to Ollama options
        temperature = map_tau_to_temperature(physics_state.tau_c)
        penalties = map_rho_to_penalties(physics_state.rho)

        # Build request payload
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,  # Max tokens (generous window)
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.0 + penalties["frequency_penalty"],
                # Note: Ollama doesn't have presence_penalty, use repeat_penalty
            }
        }

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = await self._client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                latency_ms = (time.time() - start_time) * 1000

                # Extract response text
                text = data.get("message", {}).get("content", "")

                if not text:
                    raise ValueError("Empty response from Ollama")

                # Estimate tokens (rough)
                prompt_text = " ".join(m["content"] for m in messages)
                prompt_tokens = len(prompt_text) // 4
                completion_tokens = len(text) // 4

                return {
                    "text": text,
                    "model": payload["model"],
                    "latency_ms": latency_ms,
                    "tokens": {
                        "prompt": prompt_tokens,
                        "completion": completion_tokens,
                        "total": prompt_tokens + completion_tokens
                    }
                }

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text}"
                if e.response.status_code == 404:
                    # Model not found, don't retry
                    break

            except httpx.RequestError as e:
                last_error = f"Network error: {str(e)}"

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                await httpx.AsyncClient().aclose()  # Reset connection
                await httpx.AsyncClient()  # Reinitialize
                # Note: In production, use proper backoff library

        # All retries failed
        raise RuntimeError(f"Ollama request failed after {self.max_retries} attempts: {last_error}")

    async def list_models(self) -> List[str]:
        """
        List available models on Ollama server.

        Returns:
            List of model names

        Example:
            models = await client.list_models()
            # ["gpt-oss:20b", "llama3:latest", ...]
        """
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            data = response.json()
            return [m["name"] for m in data.get("models", [])]

        except Exception:
            return []


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_client_instance: Optional[OllamaClient] = None


async def get_ollama_client(
    base_url: str = "http://localhost:11434",
    model: str = "gpt-oss:20b"
) -> OllamaClient:
    """
    Get or create Ollama client instance (singleton).

    Usage:
        client = await get_ollama_client()
        response = await client.chat(messages, physics_state)
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = OllamaClient(base_url=base_url, model=model)
        await _client_instance.initialize()

    return _client_instance


async def close_ollama_client() -> None:
    """
    Close Ollama client (cleanup on shutdown).
    """
    global _client_instance

    if _client_instance:
        await _client_instance.close()
        _client_instance = None
