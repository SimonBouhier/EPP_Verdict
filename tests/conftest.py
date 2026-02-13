"""
Shared test fixtures for provider layer tests.

Provides MockProvider, MockVRAMProvider, MockEmbeddingProvider and clean_registry fixture.
"""

import pytest
from typing import List, Dict, Any, Optional
from services.providers.base import (
    ModelProvider,
    EmbeddingProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)
from services.providers.registry import ProviderRegistry


class MockProvider(ModelProvider):
    """
    Mock implementation of ModelProvider for testing.

    Provides configurable responses and tracks call counts.
    """

    def __init__(
        self,
        provider_id: str,
        model_id: str,
        responses: List[str],
        should_fail: bool = False,
    ):
        """
        Initialize mock provider.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier
            responses: List of responses to cycle through
            should_fail: If True, generate() always returns failure
        """
        self.provider_id_value = provider_id
        self.model_id_value = model_id
        self.responses = responses
        self.should_fail = should_fail
        self.generate_count = 0
        self.unload_count = 0
        self.preload_count = 0
        self._response_index = 0
        self.last_query: Optional[StructuredQuery] = None

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """Generate response (cycles through preset responses)."""
        self.last_query = query  # Store for test inspection
        self.generate_count += 1

        if self.should_fail:
            return StructuredResponse(
                text="",
                tokens={"prompt": 0, "completion": 0, "total": 0},
                latency_ms=10.0,
                model=self.model_id_value,
                success=False,
                error="Mock provider set to fail",
            )

        # Cycle through responses
        response_text = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1

        # Estimate tokens
        prompt_tokens = sum(len(m.get("content", "")) for m in query.messages) // 4
        completion_tokens = len(response_text) // 4

        return StructuredResponse(
            text=response_text,
            tokens={
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            latency_ms=10.0,
            model=self.model_id_value,
            success=True,
        )

    async def list_models(self) -> List[str]:
        """List models (returns single model)."""
        return [self.model_id_value]

    async def health_check(self) -> Dict[str, Any]:
        """Health check (always healthy)."""
        return {
            "status": "healthy",
            "connected": True,
            "model": self.model_id_value,
        }

    def get_metadata(self) -> ModelMetadata:
        """Get metadata."""
        return ModelMetadata(
            provider_id=self.provider_id_value,
            model_id=self.model_id_value,
            architecture_family="mock",
            context_window=8192,
            supports_vram_management=False,
        )

    async def close(self) -> None:
        """Close (no-op for mock)."""
        pass


class MockVRAMProvider(MockProvider):
    """
    Mock provider with VRAM management support.

    Tracks preload/unload calls.
    """

    def get_metadata(self) -> ModelMetadata:
        """Get metadata with VRAM support enabled."""
        return ModelMetadata(
            provider_id=self.provider_id_value,
            model_id=self.model_id_value,
            architecture_family="mock_vram",
            context_window=8192,
            supports_vram_management=True,
        )

    async def preload_model(self, model: str, keep_alive: str = "5m") -> bool:
        """Preload model (increments counter)."""
        self.preload_count += 1
        return True

    async def unload_model(self, model: str) -> bool:
        """Unload model (increments counter)."""
        self.unload_count += 1
        return True


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock implementation of EmbeddingProvider for testing.
    """

    def __init__(self, dimension: int = 768, model_id: str = "mock-embed"):
        """
        Initialize mock embedding provider.

        Args:
            dimension: Embedding dimension
            model_id: Model identifier
        """
        self.dimension_value = dimension
        self.model_id_value = model_id
        self.embed_count = 0

    async def embed(self, text: str) -> List[float]:
        """Generate embedding (returns fixed values)."""
        if not text:
            raise ValueError("Text cannot be empty")

        self.embed_count += 1
        return [0.1] * self.dimension_value

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.embed(text) for text in texts]

    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension_value

    def get_model_id(self) -> str:
        """Get model identifier."""
        return self.model_id_value

    def get_provider_id(self) -> str:
        """Get provider identifier."""
        return "mock"


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Clean ProviderRegistry before and after each test.

    Ensures test isolation by clearing all registered providers.
    """
    # Setup: clear registry
    ProviderRegistry.clear_all()
    yield
    # Teardown: clear registry again
    ProviderRegistry.clear_all()


@pytest.fixture(autouse=True)
async def reset_all_singletons():
    """
    Reset ALL singletons before AND after each test.
    Setup + teardown = ceinture ET bretelles.
    Phase 4.0.0: couvre 16 singletons au lieu de 2.
    """
    await _reset_singletons()
    yield
    await _reset_singletons()


async def _reset_singletons():
    """Reset tous les singletons connus. Erreurs loggées, jamais avalées."""
    import logging
    log = logging.getLogger("test.reset")

    # 1. Pool (le plus critique — contient les connexions DB)
    try:
        from database.pool import close_pool
        await close_pool()
    except Exception as e:
        log.warning(f"close_pool failed: {e}")

    # 2. Pool auxiliaires: cache + concurrency limiter
    try:
        import database.pool as pool_mod
        pool_mod._concept_cache = None
        pool_mod._concurrency_limiter = None
    except Exception as e:
        log.warning(f"pool aux reset failed: {e}")

    # 3. Engine DB instance
    try:
        import database.engine as engine_mod
        engine_mod._db_instance = None
    except Exception as e:
        log.warning(f"engine reset failed: {e}")

    # 4. Config loader
    try:
        from services.config_loader import reset_config
        reset_config()
    except (ImportError, Exception) as e:
        log.warning(f"config reset failed: {e}")

    # 5. Entity resolver
    try:
        import services.entity_resolver as er_mod
        er_mod._resolver_instance = None
    except (ImportError, AttributeError) as e:
        log.warning(f"entity_resolver reset failed: {e}")

    # 6. Relation normalizer
    try:
        import services.relation_normalizer as rn_mod
        rn_mod._normalizer_instance = None
    except (ImportError, AttributeError) as e:
        log.warning(f"relation_normalizer reset failed: {e}")

    # 7. Session storage
    try:
        import services.session_storage as ss_mod
        ss_mod._storage_instance = None
    except (ImportError, AttributeError) as e:
        log.warning(f"session_storage reset failed: {e}")

    # 8. Semantic memory
    try:
        from services.consciousness.memory import clear_semantic_memory
        clear_semantic_memory()
    except (ImportError, Exception) as e:
        log.warning(f"semantic_memory reset failed: {e}")

    # 9. Triplet extractor
    try:
        import services.esmm.triplet_extractor as te_mod
        if te_mod._extractor_instance is not None:
            await te_mod.close_triplet_extractor()
    except (ImportError, Exception) as e:
        log.warning(f"triplet_extractor reset failed: {e}")

    # 10. Model rotator
    try:
        import services.esmm.model_rotator as mr_mod
        if mr_mod._rotator_instance is not None:
            await mr_mod.close_model_rotator()
    except (ImportError, Exception) as e:
        log.warning(f"model_rotator reset failed: {e}")

    # 11. Ollama provider
    try:
        import services.providers.ollama as ollama_mod
        if ollama_mod._ollama_instance is not None:
            await ollama_mod.close_ollama_provider()
    except (ImportError, Exception) as e:
        log.warning(f"ollama_provider reset failed: {e}")

    # 12. Ollama embedding provider
    try:
        import services.providers.ollama_embeddings as oe_mod
        if oe_mod._ollama_embedding_instance is not None:
            await oe_mod.close_ollama_embedding_provider()
    except (ImportError, Exception) as e:
        log.warning(f"ollama_embedding reset failed: {e}")

    # 13. LLM client (legacy)
    try:
        import app.llm_client as llm_mod
        if llm_mod._client_instance is not None:
            await llm_mod.close_ollama_client()
        if llm_mod._multi_model_instance is not None:
            await llm_mod.close_multi_model_client()
    except (ImportError, Exception) as e:
        log.warning(f"llm_client reset failed: {e}")
