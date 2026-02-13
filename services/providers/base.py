"""
Base interfaces for LLM model providers.

Defines the universal contract that all LLM providers (Ollama, OpenAI, Anthropic, etc.)
must implement to be compatible with the ESMM pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class StructuredQuery:
    """Query structure sent to any LLM provider."""
    messages: List[Dict[str, str]]  # [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 8192
    top_p: float = 0.9
    top_k: Optional[int] = None
    repeat_penalty: float = 1.0
    keep_alive: Optional[Any] = None  # Ollama-specific: 0 (unload), "5m" (keep), None (provider default)


@dataclass
class StructuredResponse:
    """Normalized response from any LLM provider."""
    text: str
    tokens: Dict[str, int]  # {"prompt": X, "completion": Y, "total": Z}
    latency_ms: float
    model: str
    success: bool
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None  # For debugging


@dataclass
class ModelMetadata:
    """Provider and model metadata."""
    provider_id: str          # "ollama", "openai", "anthropic"
    model_id: str             # "mistral:7b", "gpt-4o-mini", "claude-3-haiku"
    architecture_family: str  # "transformer_dense", "transformer_moe"
    context_window: int
    supports_vram_management: bool = False


# Architecture families (for diversity measurement)
# Order matters: longer/more specific prefixes first (mixtral before mistral)
ARCHITECTURE_FAMILIES = {
    # Mixture of Experts (check before dense — "mixtral" contains "mistral")
    "mixtral": "transformer_moe",
    "deepseek": "transformer_moe",
    # Dense transformers
    "mistral": "transformer_dense",
    "llama": "transformer_dense",
    "qwen": "transformer_dense",
    "gemma": "transformer_dense",
    "phi": "transformer_dense",
    # API models (architecture not always public)
    "gpt": "openai_family",
    "claude": "anthropic_family",
    "gemini": "google_family",
}


def infer_architecture_family(model_id: str) -> str:
    """
    Infère la famille d'architecture à partir du model_id.

    Phase 4.5.3 : strip le préfixe provider (``ollama::``), puis utilise le
    premier segment du model_id (avant ``:``, ``-``, ``_``, ``.``, chiffre)
    pour éviter le spoofing par substring.
    """
    import re
    model_lower = model_id.lower().strip()
    # Strip provider prefix ("ollama::mistral:7b" → "mistral:7b")
    if "::" in model_lower:
        model_lower = model_lower.split("::", 1)[1]
    # Extract first meaningful token: "llama3.1:8b" → "llama", "deepseek-r1" → "deepseek"
    first_token = re.split(r"[:\-_./\d]", model_lower)[0]

    for prefix, family in ARCHITECTURE_FAMILIES.items():
        if first_token == prefix:
            return family
    return "unknown"


class ModelProvider(ABC):
    """
    Universal interface for LLM model providers.

    Any model (Ollama local, OpenAI API, Anthropic API, etc.) that implements
    this interface can be used interchangeably in the ESMM pipeline.

    AXIOM 1: No model is a component. Every model is a consumable.
    The value resides in the protocol (ESMM), the attested graph, and the 5D signature.
    """

    @abstractmethod
    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """
        Generate a response from the model.

        Args:
            query: Structured query with messages and parameters

        Returns:
            Normalized response with text, tokens, latency
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        List all models available on this provider.

        Returns:
            List of model identifiers (e.g., ["mistral:7b", "llama3.1:8b"])
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider connectivity and health.

        Returns:
            Dict with status info: {"status": "healthy", "latency_ms": 123, ...}
        """
        pass

    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        """
        Get provider/model metadata.

        Returns:
            Metadata with provider_id, model_id, architecture, etc.
        """
        pass

    # Optional VRAM management (default implementation = no-op)
    # Only providers with VRAM constraints (like Ollama) need to override

    async def preload_model(self, model: str, keep_alive: str = "5m") -> bool:
        """
        Preload a model into VRAM (optional, provider-specific).

        Args:
            model: Model identifier
            keep_alive: How long to keep model loaded

        Returns:
            True if successful
        """
        return True

    async def unload_model(self, model: str) -> bool:
        """
        Unload a model from VRAM (optional, provider-specific).

        Args:
            model: Model identifier

        Returns:
            True if successful
        """
        return True


class EmbeddingProvider(ABC):
    """
    Universal interface for embedding providers.

    Separated from ModelProvider because embeddings have different semantics
    (vector output instead of text, batching requirements, etc.).
    """

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector (e.g., 768D for nomic-embed-text)
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batched for efficiency).

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get embedding vector dimension.

        Returns:
            Dimension (e.g., 768, 1024, 1536)
        """
        pass

    @abstractmethod
    def get_model_id(self) -> str:
        """
        Get embedding model identifier.

        Returns:
            Model ID (e.g., "nomic-embed-text", "text-embedding-3-small")
        """
        pass

    @abstractmethod
    def get_provider_id(self) -> str:
        """
        Get provider identifier.

        Returns:
            Provider ID (e.g., "ollama", "openai")
        """
        pass
