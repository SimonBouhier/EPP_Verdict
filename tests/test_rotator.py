"""
Tests for MultiProviderRotator.

Tests rotation, batch processing, VRAM management, and provider orchestration.
"""

import pytest
from services.esmm.multi_provider_rotator import (
    MultiProviderRotator,
    ProviderResponse,
    RotationResult,
    BatchProviderResult,
)
from tests.conftest import MockProvider, MockVRAMProvider


@pytest.mark.asyncio
class TestMultiProviderRotator:
    """Tests for MultiProviderRotator."""

    async def test_init(self):
        """MultiProviderRotator initializes with providers dict."""
        mock_a = MockProvider("mock", "model-a", ["response-a"])
        mock_b = MockProvider("mock", "model-b", ["response-b"])

        rotator = MultiProviderRotator(providers={"a": mock_a, "b": mock_b})

        assert rotator is not None
        assert len(rotator.providers) == 2
        assert "a" in rotator.providers
        assert "b" in rotator.providers

    async def test_generate_single_success(self):
        """generate_single returns success for valid provider."""
        mock = MockProvider("mock", "model-test", ["Hello from mock"])
        rotator = MultiProviderRotator(providers={"test": mock})

        response = await rotator.generate_single(
            provider_id="test",
            messages=[{"role": "user", "content": "test question"}],
        )

        assert response.success is True
        assert response.provider_id == "test"
        assert response.text == "Hello from mock"
        assert mock.generate_count == 1

    async def test_generate_single_unknown_provider(self):
        """generate_single returns failure for unknown provider."""
        mock = MockProvider("mock", "model-test", ["response"])
        rotator = MultiProviderRotator(providers={"test": mock})

        response = await rotator.generate_single(
            provider_id="nonexistent",
            messages=[{"role": "user", "content": "test"}],
        )

        assert response.success is False
        assert "not found" in response.error.lower()
        assert mock.generate_count == 0

    async def test_generate_single_provider_fails(self):
        """generate_single returns failure when provider fails."""
        mock = MockProvider("mock", "model-test", ["response"], should_fail=True)
        rotator = MultiProviderRotator(providers={"test": mock})

        response = await rotator.generate_single(
            provider_id="test",
            messages=[{"role": "user", "content": "test"}],
        )

        assert response.success is False
        assert response.error is not None
        assert mock.generate_count == 1

    async def test_rotate_and_process(self):
        """rotate_and_process calls all providers."""
        mock_a = MockProvider("mock", "model-a", ["response-a"])
        mock_b = MockProvider("mock", "model-b", ["response-b"])
        mock_c = MockProvider("mock", "model-c", ["response-c"])

        rotator = MultiProviderRotator(
            providers={"a": mock_a, "b": mock_b, "c": mock_c}
        )

        result = await rotator.rotate_and_process(
            provider_ids=["a", "b", "c"],
            question="test question"
        )

        assert isinstance(result, RotationResult)
        assert len(result.responses) == 3
        assert result.providers_processed == 3
        assert result.providers_failed == 0
        assert all(r.success for r in result.responses.values())

    async def test_rotate_and_process_with_failure(self):
        """rotate_and_process tracks failures correctly."""
        mock_a = MockProvider("mock", "model-a", ["response-a"])
        mock_b = MockProvider("mock", "model-b", ["response-b"], should_fail=True)
        mock_c = MockProvider("mock", "model-c", ["response-c"])

        rotator = MultiProviderRotator(
            providers={"a": mock_a, "b": mock_b, "c": mock_c}
        )

        result = await rotator.rotate_and_process(
            provider_ids=["a", "b", "c"],
            question="test"
        )

        assert result.providers_processed == 3
        assert result.providers_failed == 1
        assert sum(1 for r in result.responses.values() if r.success) == 2
        assert sum(1 for r in result.responses.values() if not r.success) == 1

    async def test_rotate_stop_on_first_success(self):
        """rotate_and_process stops after first success when configured."""
        mock_a = MockProvider("mock", "model-a", ["response-a"])
        mock_b = MockProvider("mock", "model-b", ["response-b"])
        mock_c = MockProvider("mock", "model-c", ["response-c"])

        rotator = MultiProviderRotator(
            providers={"a": mock_a, "b": mock_b, "c": mock_c}
        )

        result = await rotator.rotate_and_process(
            provider_ids=["a", "b", "c"],
            question="test",
            stop_on_first_success=True,
        )

        # Only first provider should be called
        assert mock_a.generate_count == 1
        assert mock_b.generate_count == 0
        assert mock_c.generate_count == 0
        assert result.providers_processed == 1
        assert len(result.responses) == 1

    async def test_rotate_with_system_prompt(self):
        """rotate_and_process includes system prompt in messages."""
        mock = MockProvider("mock", "model-test", ["response"])
        rotator = MultiProviderRotator(providers={"test": mock})

        await rotator.rotate_and_process(
            provider_ids=["test"],
            question="test question",
            system_prompt="You are a helpful assistant",
        )

        assert mock.generate_count == 1
        assert mock.last_query is not None
        messages = mock.last_query.messages
        assert messages[0]["role"] == "system"
        # Phase 4.5.1: XML boundary delimiters wrap content
        assert "You are a helpful assistant" in messages[0]["content"]
        assert "<system_instruction>" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "test question" in messages[1]["content"]
        assert "<user_query>" in messages[1]["content"]

    async def test_batch_process(self):
        """batch_process handles multiple questions for single provider."""
        mock = MockProvider("mock", "model-test", ["answer-1", "answer-2", "answer-3"])
        rotator = MultiProviderRotator(providers={"test": mock})

        responses = await rotator.batch_process(
            provider_id="test",
            questions=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
                [{"role": "user", "content": "q3"}],
            ],
        )

        assert len(responses) == 3
        assert all(r.success for r in responses)
        assert responses[0].text == "answer-1"
        assert responses[1].text == "answer-2"
        assert responses[2].text == "answer-3"
        assert mock.generate_count == 3

    async def test_batch_process_unknown_provider(self):
        """batch_process returns failures for unknown provider."""
        mock = MockProvider("mock", "model-test", ["response"])
        rotator = MultiProviderRotator(providers={"test": mock})

        responses = await rotator.batch_process(
            provider_id="nonexistent",
            questions=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
            ],
        )

        assert len(responses) == 2
        assert all(not r.success for r in responses)
        assert all("not found" in r.error.lower() for r in responses)
        assert mock.generate_count == 0

    async def test_batch_sequential_providers(self):
        """batch_sequential_providers processes multiple providers × questions."""
        mock_a = MockProvider("mock", "model-a", ["a1", "a2", "a3"])
        mock_b = MockProvider("mock", "model-b", ["b1", "b2", "b3"])

        rotator = MultiProviderRotator(providers={"a": mock_a, "b": mock_b})

        result = await rotator.batch_sequential_providers(
            provider_ids=["a", "b"],
            questions=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
                [{"role": "user", "content": "q3"}],
            ],
        )

        assert isinstance(result, BatchProviderResult)
        assert len(result.results) == 2
        assert "a" in result.results
        assert "b" in result.results
        assert len(result.results["a"]) == 3
        assert len(result.results["b"]) == 3
        assert all(r.success for r in result.results["a"])
        assert all(r.success for r in result.results["b"])

    async def test_vram_unload_on_rotation(self):
        """VRAM providers are unloaded after each generation in rotation."""
        mock_a = MockVRAMProvider("mock", "model-a", ["response-a"])
        mock_b = MockVRAMProvider("mock", "model-b", ["response-b"])

        rotator = MultiProviderRotator(providers={"a": mock_a, "b": mock_b})

        result = await rotator.rotate_and_process(
            provider_ids=["a", "b"],
            question="test"
        )

        assert mock_a.generate_count == 1
        assert mock_b.generate_count == 1
        assert mock_a.unload_count >= 1  # Vérifie l'unload
        assert mock_b.unload_count >= 1  # Vérifie l'unload
        assert all(r.success for r in result.responses.values())

    async def test_vram_preload_on_batch(self):
        """VRAM provider is preloaded once before batch processing."""
        mock = MockVRAMProvider("mock", "model-test", ["r1", "r2", "r3"])
        rotator = MultiProviderRotator(providers={"test": mock})

        await rotator.batch_process(
            provider_id="test",
            questions=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
                [{"role": "user", "content": "q3"}],
            ],
        )

        # Preload should be called once before batch
        assert mock.preload_count == 1
        assert mock.generate_count == 3

    async def test_no_vram_on_cloud_provider(self):
        """Cloud providers (no VRAM support) are not unloaded."""
        mock = MockProvider("mock", "model-test", ["response"])
        rotator = MultiProviderRotator(providers={"test": mock})

        await rotator.rotate_and_process(
            provider_ids=["test"],
            question="test"
        )

        # No VRAM management for cloud provider
        assert mock.unload_count == 0

    async def test_generate_count_tracking(self):
        """Providers track generate call counts correctly."""
        mock_a = MockProvider("mock", "model-a", ["r1", "r2"])
        mock_b = MockProvider("mock", "model-b", ["r3", "r4"])

        rotator = MultiProviderRotator(providers={"a": mock_a, "b": mock_b})

        await rotator.batch_sequential_providers(
            provider_ids=["a", "b"],
            questions=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
            ],
        )

        # Each provider should have been called twice
        assert mock_a.generate_count == 2
        assert mock_b.generate_count == 2
