"""
Provider registry for managing model and embedding providers.

Centralized registry for all ModelProvider and EmbeddingProvider instances.
Supports dynamic registration, retrieval, and lifecycle management.
"""

import logging
from typing import Dict, List, Optional, Union
from services.providers.base import ModelProvider, EmbeddingProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Centralized registry for model and embedding providers.

    Manages the lifecycle of all providers in the ESMM pipeline.
    Providers are registered by ID and can be retrieved, listed, and closed.
    """

    # Class-level storage (singleton pattern)
    _model_providers: Dict[str, ModelProvider] = {}
    _embedding_providers: Dict[str, EmbeddingProvider] = {}

    @classmethod
    def register_model(cls, provider_id: str, provider: ModelProvider) -> None:
        """
        Register a model provider.

        Args:
            provider_id: Unique identifier for the provider (e.g., "ollama_mistral")
            provider: ModelProvider instance
        """
        if provider_id in cls._model_providers:
            logger.warning(
                f"[ProviderRegistry] Overwriting existing provider: {provider_id}"
            )

        cls._model_providers[provider_id] = provider
        logger.info(f"[ProviderRegistry] Registered model provider: {provider_id}")

    @classmethod
    def register_embedding(
        cls, provider_id: str, provider: EmbeddingProvider
    ) -> None:
        """
        Register an embedding provider.

        Args:
            provider_id: Unique identifier for the provider (e.g., "ollama_nomic")
            provider: EmbeddingProvider instance
        """
        if provider_id in cls._embedding_providers:
            logger.warning(
                f"[ProviderRegistry] Overwriting existing embedding provider: {provider_id}"
            )

        cls._embedding_providers[provider_id] = provider
        logger.info(f"[ProviderRegistry] Registered embedding provider: {provider_id}")

    @classmethod
    def get_model(cls, provider_id: str) -> ModelProvider:
        """
        Get a registered model provider.

        Args:
            provider_id: Provider identifier

        Returns:
            ModelProvider instance

        Raises:
            KeyError: If provider not found
        """
        if provider_id not in cls._model_providers:
            available = ", ".join(cls._model_providers.keys())
            raise KeyError(
                f"Model provider '{provider_id}' not found. "
                f"Available: [{available}]"
            )

        return cls._model_providers[provider_id]

    @classmethod
    def get_embedding(cls, provider_id: str) -> EmbeddingProvider:
        """
        Get a registered embedding provider.

        Args:
            provider_id: Provider identifier

        Returns:
            EmbeddingProvider instance

        Raises:
            KeyError: If provider not found
        """
        if provider_id not in cls._embedding_providers:
            available = ", ".join(cls._embedding_providers.keys())
            raise KeyError(
                f"Embedding provider '{provider_id}' not found. "
                f"Available: [{available}]"
            )

        return cls._embedding_providers[provider_id]

    @classmethod
    def list_model_providers(cls) -> List[str]:
        """
        List all registered model provider IDs.

        Returns:
            List of provider IDs
        """
        return list(cls._model_providers.keys())

    @classmethod
    def list_embedding_providers(cls) -> List[str]:
        """
        List all registered embedding provider IDs.

        Returns:
            List of provider IDs
        """
        return list(cls._embedding_providers.keys())

    @classmethod
    def unregister_model(cls, provider_id: str) -> None:
        """
        Unregister a model provider.

        Args:
            provider_id: Provider identifier
        """
        if provider_id in cls._model_providers:
            del cls._model_providers[provider_id]
            logger.info(f"[ProviderRegistry] Unregistered model provider: {provider_id}")
        else:
            logger.warning(
                f"[ProviderRegistry] Attempted to unregister unknown provider: {provider_id}"
            )

    @classmethod
    def unregister_embedding(cls, provider_id: str) -> None:
        """
        Unregister an embedding provider.

        Args:
            provider_id: Provider identifier
        """
        if provider_id in cls._embedding_providers:
            del cls._embedding_providers[provider_id]
            logger.info(
                f"[ProviderRegistry] Unregistered embedding provider: {provider_id}"
            )
        else:
            logger.warning(
                f"[ProviderRegistry] Attempted to unregister unknown embedding provider: {provider_id}"
            )

    @classmethod
    def clear_all(cls) -> None:
        """
        Clear all registered providers WITHOUT closing them.

        Useful for test isolation - removes all providers from registry
        without calling close() on them.

        For production shutdown with proper cleanup, use close_all() instead.
        """
        cls._model_providers.clear()
        cls._embedding_providers.clear()
        logger.debug("[ProviderRegistry] All providers cleared from registry")

    @classmethod
    async def close_all(cls) -> None:
        """
        Close all registered providers (cleanup on shutdown).

        Calls close() on all providers that support it, then clears the registry.
        """
        logger.info("[ProviderRegistry] Closing all providers...")

        # Close model providers
        for provider_id, provider in cls._model_providers.items():
            try:
                if hasattr(provider, "close"):
                    await provider.close()
                    logger.debug(f"[ProviderRegistry] Closed {provider_id}")
            except Exception as e:
                logger.error(
                    f"[ProviderRegistry] Error closing {provider_id}: {e}"
                )

        # Close embedding providers
        for provider_id, provider in cls._embedding_providers.items():
            try:
                if hasattr(provider, "close"):
                    await provider.close()
                    logger.debug(f"[ProviderRegistry] Closed {provider_id}")
            except Exception as e:
                logger.error(
                    f"[ProviderRegistry] Error closing {provider_id}: {e}"
                )

        # Clear registries
        cls._model_providers.clear()
        cls._embedding_providers.clear()

        logger.info("[ProviderRegistry] All providers closed")

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """
        Get registry statistics.

        Returns:
            Dict with counts of registered providers
        """
        return {
            "model_providers": len(cls._model_providers),
            "embedding_providers": len(cls._embedding_providers),
            "total_providers": len(cls._model_providers)
            + len(cls._embedding_providers),
        }


# Convenience functions for common operations


def get_provider(provider_id: str) -> Union[ModelProvider, EmbeddingProvider]:
    """
    Get a provider (model or embedding) by ID.

    Tries model providers first, then embedding providers.

    Args:
        provider_id: Provider identifier

    Returns:
        ModelProvider or EmbeddingProvider instance

    Raises:
        KeyError: If provider not found in either registry
    """
    # Try model providers first
    try:
        return ProviderRegistry.get_model(provider_id)
    except KeyError:
        pass  # OK: fallthrough to embedding registry

    # Try embedding providers
    try:
        return ProviderRegistry.get_embedding(provider_id)
    except KeyError:
        pass  # OK: fallthrough to raise KeyError with clear message

    # Not found in either
    raise KeyError(
        f"Provider '{provider_id}' not found in model or embedding registries"
    )


async def health_check_all() -> Dict[str, Dict]:
    """
    Run health checks on all registered model providers.

    Returns:
        Dict mapping provider_id -> health check result
    """
    results = {}

    for provider_id in ProviderRegistry.list_model_providers():
        provider = ProviderRegistry.get_model(provider_id)
        try:
            health = await provider.health_check()
            results[provider_id] = health
        except Exception as e:
            results[provider_id] = {
                "status": "error",
                "error": str(e),
            }

    return results
