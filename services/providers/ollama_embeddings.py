"""
Ollama embedding provider implementation.

Provides embeddings via Ollama embedding models (nomic-embed-text, mxbai-embed-large, etc.).
"""

import logging
from typing import List, Optional
import httpx

from services.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Ollama embedding provider.

    Supports any Ollama embedding model:
    - nomic-embed-text (768D)
    - mxbai-embed-large (1024D)
    - etc.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        dimension: Optional[int] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize Ollama embedding provider.

        Args:
            base_url: Ollama server URL
            model: Embedding model name
            dimension: Expected embedding dimension (auto-detected if None)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension = dimension  # Will be auto-detected on first call
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

        # Known dimensions for common models
        self._known_dimensions = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
        }

    async def _ensure_initialized(self) -> None:
        """Ensure HTTP client is initialized."""
        if not self._initialized or self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            )
            self._initialized = True
            logger.info(
                f"[OllamaEmbeddingProvider] Initialized with model {self.model}"
            )

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector (e.g., 768D for nomic-embed-text)
        """
        if not text or not isinstance(text, str):
            raise ValueError(f"Invalid text input: {text}")

        await self._ensure_initialized()

        try:
            response = await self._client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()

            data = response.json()
            embeddings = data.get("embedding", [])

            if not embeddings:
                raise ValueError("No embeddings returned from Ollama")

            # Auto-detect dimension on first call
            if self._dimension is None:
                self._dimension = len(embeddings)
                logger.info(
                    f"[OllamaEmbeddingProvider] Auto-detected dimension: {self._dimension}D"
                )
            elif len(embeddings) != self._dimension:
                logger.warning(
                    f"Expected {self._dimension}D embedding, got {len(embeddings)}D"
                )

            return embeddings

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
            raise

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(
                    f"Model {self.model} not found. Install via: ollama pull {self.model}"
                )
            raise

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Note: Ollama doesn't support native batching, so we process sequentially.
        This could be optimized in the future with concurrent requests.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            emb = await self.embed(text)
            embeddings.append(emb)

        logger.debug(
            f"[OllamaEmbeddingProvider] Generated {len(embeddings)} embeddings"
        )
        return embeddings

    def get_dimension(self) -> int:
        """
        Get embedding vector dimension.

        Returns:
            Dimension (e.g., 768, 1024)
        """
        # Return known dimension if available
        if self._dimension is not None:
            return self._dimension

        # Return known dimension for this model
        if self.model in self._known_dimensions:
            return self._known_dimensions[self.model]

        # Default fallback (will be auto-detected on first embed call)
        logger.warning(
            f"Dimension for {self.model} unknown, returning default 768. "
            "Will be auto-detected on first embedding."
        )
        return 768

    def get_model_id(self) -> str:
        """
        Get embedding model identifier.

        Returns:
            Model ID (e.g., "nomic-embed-text")
        """
        return self.model

    def get_provider_id(self) -> str:
        """
        Get provider identifier.

        Returns:
            Provider ID ("ollama")
        """
        return "ollama"


# Singleton instance
_ollama_embedding_instance: Optional[OllamaEmbeddingProvider] = None


async def get_ollama_embedding_provider(
    base_url: str = None,
    model: str = None,
) -> OllamaEmbeddingProvider:
    """
    Get or create singleton Ollama embedding provider.

    Environment variables:
        LYRA_OLLAMA_URL: Ollama base URL (default: http://localhost:11434)
        LYRA_EMBEDDING_MODEL: Embedding model (default: nomic-embed-text)

    Args:
        base_url: Override base URL
        model: Override model

    Returns:
        OllamaEmbeddingProvider instance
    """
    global _ollama_embedding_instance

    if _ollama_embedding_instance is None:
        import os

        actual_url = base_url or os.environ.get(
            "LYRA_OLLAMA_URL", "http://localhost:11434"
        )
        actual_model = model or os.environ.get("LYRA_EMBEDDING_MODEL", "nomic-embed-text")

        logger.info(f"Initializing OllamaEmbeddingProvider with model: {actual_model}")
        _ollama_embedding_instance = OllamaEmbeddingProvider(
            base_url=actual_url,
            model=actual_model,
        )
        await _ollama_embedding_instance._ensure_initialized()

    return _ollama_embedding_instance


async def close_ollama_embedding_provider() -> None:
    """Close singleton Ollama embedding provider."""
    global _ollama_embedding_instance

    if _ollama_embedding_instance:
        await _ollama_embedding_instance.close()
        _ollama_embedding_instance = None
