"""
Tests for provider layer: ABC contracts, dataclasses, OllamaProvider, Registry.

No real network calls - all HTTP interactions are mocked.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from services.providers.base import (
    ModelProvider,
    EmbeddingProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)
from services.providers.ollama import OllamaProvider
from services.providers.ollama_embeddings import OllamaEmbeddingProvider
from services.providers.registry import ProviderRegistry, get_provider, health_check_all
from tests.conftest import MockProvider, MockEmbeddingProvider


# ============================================================================
# TEST ABC CONTRACTS
# ============================================================================

class TestABCContracts:
    """Test that ABC interfaces cannot be instantiated directly."""

    def test_model_provider_not_instantiable(self):
        """ModelProvider ABC cannot be instantiated."""
        with pytest.raises(TypeError):
            ModelProvider()

    def test_embedding_provider_not_instantiable(self):
        """EmbeddingProvider ABC cannot be instantiated."""
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_mock_provider_is_valid(self):
        """MockProvider is a valid ModelProvider implementation."""
        mock = MockProvider("test", "model-1", ["response"])
        assert isinstance(mock, ModelProvider)

    def test_mock_embedding_is_valid(self):
        """MockEmbeddingProvider is a valid EmbeddingProvider implementation."""
        mock = MockEmbeddingProvider()
        assert isinstance(mock, EmbeddingProvider)


# ============================================================================
# TEST STRUCTURED DATACLASSES
# ============================================================================

class TestStructuredDataclasses:
    """Test StructuredQuery, StructuredResponse, ModelMetadata dataclasses."""

    def test_structured_query_defaults(self):
        """StructuredQuery has correct default values."""
        query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
        assert query.temperature == 0.7
        assert query.max_tokens == 4096
        assert query.context_window == 8192
        assert query.top_p == 0.9
        assert query.repeat_penalty == 1.0

    def test_structured_query_keep_alive(self):
        """StructuredQuery stores keep_alive value (Phase 2)."""
        query = StructuredQuery(
            messages=[{"role": "user", "content": "test"}],
            keep_alive="5m"
        )
        assert query.keep_alive == "5m"

    def test_structured_response_success(self):
        """StructuredResponse with success=True."""
        response = StructuredResponse(
            text="hello",
            tokens={"prompt": 10, "completion": 5, "total": 15},
            latency_ms=100.0,
            model="test-model",
            success=True,
        )
        assert response.success is True
        assert response.text == "hello"
        assert response.error is None

    def test_structured_response_failure(self):
        """StructuredResponse with success=False and error message."""
        response = StructuredResponse(
            text="",
            tokens={"prompt": 0, "completion": 0, "total": 0},
            latency_ms=50.0,
            model="test-model",
            success=False,
            error="timeout",
        )
        assert response.success is False
        assert response.error == "timeout"

    def test_model_metadata(self):
        """ModelMetadata stores all fields correctly."""
        metadata = ModelMetadata(
            provider_id="test",
            model_id="m1",
            architecture_family="transformer",
            context_window=8192,
            supports_vram_management=True,
        )
        assert metadata.provider_id == "test"
        assert metadata.model_id == "m1"
        assert metadata.supports_vram_management is True


# ============================================================================
# TEST OLLAMA PROVIDER
# ============================================================================

class TestOllamaProvider:
    """Test OllamaProvider with mocked HTTP calls."""

    def _make_mock_response(self, json_data: dict, status_code: int = 200):
        """Helper to create mock httpx.Response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = json_data
        mock_response.status_code = status_code
        mock_response.text = str(json_data)
        return mock_response

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """OllamaProvider.generate() returns success response."""
        provider = OllamaProvider(model="test-model")
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({
            "message": {"content": "réponse"},
            "eval_count": 10,
            "prompt_eval_count": 20,
        })

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        assert response.success is True
        assert response.text == "réponse"
        assert response.tokens["completion"] == 10
        assert response.tokens["prompt"] == 20

    @pytest.mark.asyncio
    async def test_generate_empty_response(self):
        """OllamaProvider handles empty response from Ollama."""
        provider = OllamaProvider(model="test-model", max_retries=1)
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({
            "message": {"content": ""},
        })

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        # Empty response triggers ValueError → retry → final failure
        assert response.success is False

    @pytest.mark.asyncio
    async def test_generate_http_error(self):
        """OllamaProvider handles HTTP 500 error."""
        provider = OllamaProvider(model="test-model", max_retries=1)
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({}, status_code=500)
        http_error = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response
        )

        with patch.object(provider._client, 'post', side_effect=http_error):
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        assert response.success is False
        assert "500" in response.error

    @pytest.mark.asyncio
    async def test_generate_network_error(self):
        """OllamaProvider handles network connection error."""
        provider = OllamaProvider(model="test-model", max_retries=1)
        await provider._ensure_initialized()

        with patch.object(provider._client, 'post', side_effect=httpx.ConnectError("Connection refused")):
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        assert response.success is False
        assert "Network error" in response.error

    @pytest.mark.asyncio
    async def test_generate_retry_on_failure(self):
        """OllamaProvider retries on transient failures (Phase 2)."""
        provider = OllamaProvider(model="test-model", max_retries=3)
        await provider._ensure_initialized()

        # Fail twice, succeed on 3rd attempt
        mock_response_success = self._make_mock_response({
            "message": {"content": "success"},
            "eval_count": 5,
            "prompt_eval_count": 10,
        })

        call_count = 0

        async def side_effect_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.RequestError("Transient error")
            return mock_response_success

        with patch.object(provider._client, 'post', side_effect=side_effect_fn) as mock_post:
            mock_response_success.raise_for_status = MagicMock()
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        assert response.success is True
        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_generate_no_retry_on_404(self):
        """OllamaProvider does not retry on 404 (model not found)."""
        provider = OllamaProvider(model="test-model", max_retries=3)
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({}, status_code=404)
        http_error = httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response
        )

        call_count = 0

        async def side_effect_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise http_error

        with patch.object(provider._client, 'post', side_effect=side_effect_fn):
            query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
            response = await provider.generate(query)

        assert response.success is False
        assert call_count == 1  # No retries on 404

    @pytest.mark.asyncio
    async def test_list_models(self):
        """OllamaProvider lists available models."""
        provider = OllamaProvider(model="test-model")
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({
            "models": [
                {"name": "mistral:7b"},
                {"name": "llama3:8b"}
            ]
        })

        with patch.object(provider._client, 'get', return_value=mock_response) as mock_get:
            mock_response.raise_for_status = MagicMock()
            models = await provider.list_models()

        assert models == ["mistral:7b", "llama3:8b"]

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """OllamaProvider health check returns healthy status."""
        provider = OllamaProvider(model="mistral:7b")
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({
            "models": [{"name": "mistral:7b"}]
        })

        with patch.object(provider._client, 'get', return_value=mock_response) as mock_get:
            mock_response.raise_for_status = MagicMock()
            health = await provider.health_check()

        assert health["status"] == "healthy"
        assert health["connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """OllamaProvider health check handles connection failure."""
        provider = OllamaProvider(model="test-model")
        await provider._ensure_initialized()

        with patch.object(provider._client, 'get', side_effect=httpx.ConnectError("Connection refused")):
            health = await provider.health_check()

        assert health["connected"] is False
        assert "error" in health

    @pytest.mark.asyncio
    async def test_preload_model(self):
        """OllamaProvider preloads model successfully."""
        provider = OllamaProvider(model="test-model")
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({})

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_response.raise_for_status = MagicMock()
            result = await provider.preload_model("test-model")

        assert result is True

    @pytest.mark.asyncio
    async def test_unload_model(self):
        """OllamaProvider unloads model successfully."""
        provider = OllamaProvider(model="test-model")
        await provider._ensure_initialized()

        mock_response = self._make_mock_response({})

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_response.raise_for_status = MagicMock()
            result = await provider.unload_model("test-model")

        assert result is True

    def test_metadata(self):
        """OllamaProvider metadata has correct values."""
        provider = OllamaProvider(model="test-model")
        metadata = provider.get_metadata()

        assert metadata.provider_id == "ollama"
        assert metadata.supports_vram_management is True

    @pytest.mark.asyncio
    async def test_no_model_raises(self):
        """OllamaProvider without model raises ValueError on generate."""
        provider = OllamaProvider(model=None)
        await provider._ensure_initialized()

        query = StructuredQuery(messages=[{"role": "user", "content": "test"}])

        with pytest.raises(ValueError, match="No model specified"):
            await provider.generate(query)


# ============================================================================
# TEST OLLAMA EMBEDDING PROVIDER
# ============================================================================

class TestOllamaEmbeddingProvider:
    """Test OllamaEmbeddingProvider with mocked HTTP calls."""

    def _make_mock_response(self, json_data: dict, status_code: int = 200):
        """Helper to create mock httpx.Response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = json_data
        mock_response.status_code = status_code
        mock_response.text = str(json_data)
        return mock_response

    @pytest.mark.asyncio
    async def test_embed_success(self):
        """OllamaEmbeddingProvider embeds text successfully."""
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")
        await provider._ensure_initialized()

        embedding_vector = [0.1] * 768
        mock_response = self._make_mock_response({"embedding": embedding_vector})

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_response.raise_for_status = MagicMock()
            result = await provider.embed("test text")

        assert len(result) == 768
        assert result == embedding_vector

    @pytest.mark.asyncio
    async def test_embed_auto_dimension(self):
        """OllamaEmbeddingProvider auto-detects dimension on first call."""
        provider = OllamaEmbeddingProvider(model="test-embed")
        await provider._ensure_initialized()

        embedding_vector = [0.1] * 1024  # Different dimension
        mock_response = self._make_mock_response({"embedding": embedding_vector})

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_response.raise_for_status = MagicMock()
            await provider.embed("test")

        assert provider.get_dimension() == 1024

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """OllamaEmbeddingProvider embeds multiple texts."""
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")
        await provider._ensure_initialized()

        embedding_vector = [0.1] * 768
        mock_response = self._make_mock_response({"embedding": embedding_vector})

        with patch.object(provider._client, 'post', return_value=mock_response) as mock_post:
            mock_response.raise_for_status = MagicMock()
            results = await provider.embed_batch(["text1", "text2", "text3"])

        assert len(results) == 3
        assert all(len(r) == 768 for r in results)

    @pytest.mark.asyncio
    async def test_embed_empty_text(self):
        """OllamaEmbeddingProvider raises ValueError on empty text."""
        provider = OllamaEmbeddingProvider()

        with pytest.raises(ValueError, match="Invalid text input"):
            await provider.embed("")

    def test_known_dimensions(self):
        """OllamaEmbeddingProvider knows dimensions for common models."""
        provider_nomic = OllamaEmbeddingProvider(model="nomic-embed-text")
        assert provider_nomic.get_dimension() == 768

        provider_mxbai = OllamaEmbeddingProvider(model="mxbai-embed-large")
        assert provider_mxbai.get_dimension() == 1024

    def test_provider_id(self):
        """OllamaEmbeddingProvider returns correct provider_id."""
        provider = OllamaEmbeddingProvider()
        assert provider.get_provider_id() == "ollama"


# ============================================================================
# TEST PROVIDER REGISTRY
# ============================================================================

class TestProviderRegistry:
    """Test ProviderRegistry with clean_registry fixture."""

    def test_register_and_get_model(self):
        """Registry can register and retrieve model provider."""
        mock = MockProvider("test", "model-1", ["response"])
        ProviderRegistry.register_model("test", mock)

        retrieved = ProviderRegistry.get_model("test")
        assert retrieved is mock

    def test_register_and_get_embedding(self):
        """Registry can register and retrieve embedding provider."""
        mock = MockEmbeddingProvider()
        ProviderRegistry.register_embedding("test-embed", mock)

        retrieved = ProviderRegistry.get_embedding("test-embed")
        assert retrieved is mock

    def test_get_unknown_raises(self):
        """Registry raises KeyError for unknown model provider."""
        with pytest.raises(KeyError, match="not found"):
            ProviderRegistry.get_model("inexistant")

    def test_get_unknown_embedding_raises(self):
        """Registry raises KeyError for unknown embedding provider."""
        with pytest.raises(KeyError, match="not found"):
            ProviderRegistry.get_embedding("inexistant")

    def test_list_model_providers(self):
        """Registry lists all registered model providers."""
        mock1 = MockProvider("p1", "m1", ["r1"])
        mock2 = MockProvider("p2", "m2", ["r2"])
        mock3 = MockProvider("p3", "m3", ["r3"])

        ProviderRegistry.register_model("p1", mock1)
        ProviderRegistry.register_model("p2", mock2)
        ProviderRegistry.register_model("p3", mock3)

        providers = ProviderRegistry.list_model_providers()
        assert len(providers) == 3
        assert set(providers) == {"p1", "p2", "p3"}

    def test_list_embedding_providers(self):
        """Registry lists all registered embedding providers."""
        mock1 = MockEmbeddingProvider()
        mock2 = MockEmbeddingProvider()

        ProviderRegistry.register_embedding("e1", mock1)
        ProviderRegistry.register_embedding("e2", mock2)

        providers = ProviderRegistry.list_embedding_providers()
        assert len(providers) == 2
        assert set(providers) == {"e1", "e2"}

    def test_overwrite_warning(self):
        """Registry overwrites when registering same ID twice."""
        mock1 = MockProvider("p1", "m1", ["r1"])
        mock2 = MockProvider("p1", "m2", ["r2"])

        ProviderRegistry.register_model("test", mock1)
        ProviderRegistry.register_model("test", mock2)

        retrieved = ProviderRegistry.get_model("test")
        assert retrieved is mock2  # Second one wins

    def test_unregister_model(self):
        """Registry can unregister model provider."""
        mock = MockProvider("p1", "m1", ["r1"])
        ProviderRegistry.register_model("test", mock)
        ProviderRegistry.unregister_model("test")

        with pytest.raises(KeyError):
            ProviderRegistry.get_model("test")

    def test_get_stats(self):
        """Registry returns correct stats."""
        mock_model1 = MockProvider("p1", "m1", ["r1"])
        mock_model2 = MockProvider("p2", "m2", ["r2"])
        mock_embed = MockEmbeddingProvider()

        ProviderRegistry.register_model("m1", mock_model1)
        ProviderRegistry.register_model("m2", mock_model2)
        ProviderRegistry.register_embedding("e1", mock_embed)

        stats = ProviderRegistry.get_stats()
        assert stats["model_providers"] == 2
        assert stats["embedding_providers"] == 1
        assert stats["total_providers"] == 3

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Registry closes all providers on close_all()."""
        mock1 = MockProvider("p1", "m1", ["r1"])
        mock2 = MockProvider("p2", "m2", ["r2"])

        # Mock the close methods
        mock1.close = AsyncMock()
        mock2.close = AsyncMock()

        ProviderRegistry.register_model("m1", mock1)
        ProviderRegistry.register_model("m2", mock2)

        await ProviderRegistry.close_all()

        # Verify close was called
        mock1.close.assert_called_once()
        mock2.close.assert_called_once()

        # Verify registry is empty
        assert len(ProviderRegistry.list_model_providers()) == 0

    def test_clear_all(self):
        """Registry clear_all() empties registry without closing (Phase 2)."""
        mock1 = MockProvider("p1", "m1", ["r1"])
        mock2 = MockProvider("p2", "m2", ["r2"])

        # Mock close methods
        mock1.close = MagicMock()
        mock2.close = MagicMock()

        ProviderRegistry.register_model("m1", mock1)
        ProviderRegistry.register_model("m2", mock2)

        ProviderRegistry.clear_all()

        # Verify registry is empty
        assert len(ProviderRegistry.list_model_providers()) == 0

        # Verify close was NOT called
        mock1.close.assert_not_called()
        mock2.close.assert_not_called()

    def test_convenience_get_provider(self):
        """get_provider() finds provider in model or embedding registry."""
        mock_model = MockProvider("p1", "m1", ["r1"])
        mock_embed = MockEmbeddingProvider()

        ProviderRegistry.register_model("model1", mock_model)
        ProviderRegistry.register_embedding("embed1", mock_embed)

        # Should find in model registry
        retrieved_model = get_provider("model1")
        assert retrieved_model is mock_model

        # Should find in embedding registry
        retrieved_embed = get_provider("embed1")
        assert retrieved_embed is mock_embed

        # Should raise if not found in either
        with pytest.raises(KeyError):
            get_provider("nonexistent")
