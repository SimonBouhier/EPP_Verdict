"""
Provider package for universal LLM model interfaces.

This package implements the AXIOM 1 of the EPP framework:
"No model is a component. Every model is a consumable."

All providers (Ollama, OpenAI, Anthropic, etc.) implement the same ModelProvider
interface, making them interchangeable in the ESMM pipeline.
"""

from services.providers.base import (
    ModelProvider,
    EmbeddingProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)

from services.providers.ollama import OllamaProvider, get_ollama_provider
from services.providers.openai_compat import (
    OpenAICompatProvider,
    create_openai_provider,
    create_kimi_provider,
    create_deepseek_provider,
)
from services.providers.anthropic import AnthropicProvider, create_anthropic_provider
from services.providers.ollama_embeddings import (
    OllamaEmbeddingProvider,
    get_ollama_embedding_provider,
)
from services.providers.registry import ProviderRegistry, get_provider, health_check_all

__all__ = [
    # Base interfaces
    "ModelProvider",
    "EmbeddingProvider",
    "StructuredQuery",
    "StructuredResponse",
    "ModelMetadata",
    # Providers
    "OllamaProvider",
    "OpenAICompatProvider",
    "AnthropicProvider",
    "OllamaEmbeddingProvider",
    # Factory functions
    "get_ollama_provider",
    "create_openai_provider",
    "create_kimi_provider",
    "create_deepseek_provider",
    "create_anthropic_provider",
    "get_ollama_embedding_provider",
    # Registry
    "ProviderRegistry",
    "get_provider",
    "health_check_all",
]
