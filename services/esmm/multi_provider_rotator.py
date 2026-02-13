"""
Multi-Provider Rotator for ESMM.

Provider-agnostic model rotation supporting Ollama, OpenAI, Anthropic, and any
provider implementing the ModelProvider interface.

This replaces the Ollama-specific ModelRotator with a universal implementation.
"""

import time
import asyncio
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

from services.providers.base import ModelProvider, StructuredQuery, StructuredResponse

logger = logging.getLogger(__name__)


@dataclass
class ProviderResponse:
    """Response from a provider in the rotation."""

    provider_id: str
    model: str
    text: str
    latency_ms: float
    tokens: Dict[str, int]
    success: bool
    error: Optional[str] = None


@dataclass
class RotationResult:
    """Result of a complete rotation cycle across providers."""

    responses: Dict[str, ProviderResponse]  # provider_id -> response
    total_duration_ms: float
    providers_processed: int
    providers_failed: int


@dataclass
class BatchProviderResult:
    """Result of batch sequential multi-provider processing."""

    results: Dict[str, List[ProviderResponse]]  # provider_id -> [responses]
    total_duration_ms: float
    providers_processed: int
    questions_per_provider: int


class MultiProviderRotator:
    """
    Universal model rotator supporting any ModelProvider.

    Replaces Ollama-specific ModelRotator with provider-agnostic implementation.
    Supports VRAM management for providers that need it (Ollama), and handles
    API providers (OpenAI, Anthropic) transparently.

    Key Features:
    - Provider-agnostic rotation
    - Optional VRAM management (provider-specific)
    - Batch processing
    - Graceful degradation on failures
    """

    def __init__(
        self,
        providers: Dict[str, ModelProvider],
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ):
        """
        Initialize multi-provider rotator.

        Args:
            providers: Dict mapping provider_id -> ModelProvider instance
            default_temperature: Default generation temperature
            default_max_tokens: Default max tokens to generate
        """
        self.providers = providers
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        logger.info(
            f"[MultiProviderRotator] Initialized with {len(providers)} providers: "
            f"{', '.join(providers.keys())}"
        )

    async def generate_single(
        self,
        provider_id: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        unload_after: bool = True,
    ) -> ProviderResponse:
        """
        Generate with a single provider.

        Args:
            provider_id: Provider identifier
            messages: Chat messages
            temperature: Generation temperature (uses default if None)
            max_tokens: Max tokens (uses default if None)
            unload_after: If True and provider supports VRAM, unload after

        Returns:
            ProviderResponse with result
        """
        if provider_id not in self.providers:
            return ProviderResponse(
                provider_id=provider_id,
                model="unknown",
                text="",
                latency_ms=0.0,
                tokens={"prompt": 0, "completion": 0, "total": 0},
                success=False,
                error=f"Provider '{provider_id}' not found",
            )

        provider = self.providers[provider_id]
        start_time = time.time()

        try:
            # For Ollama: control keep_alive to manage VRAM
            # unload_after=True → keep_alive=0 (unload immediately)
            # unload_after=False → keep_alive="5m" (keep loaded)
            metadata = provider.get_metadata()
            keep_alive_value = None
            if metadata.supports_vram_management:
                keep_alive_value = 0 if unload_after else "5m"

            query = StructuredQuery(
                messages=messages,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
                keep_alive=keep_alive_value,
            )

            response = await provider.generate(query)
            latency_ms = (time.time() - start_time) * 1000

            # Explicit unload after generation if requested
            if unload_after and metadata.supports_vram_management:
                await provider.unload_model(metadata.model_id)

            logger.info(
                f"[MultiProviderRotator] {provider_id} generated {len(response.text)} chars "
                f"in {latency_ms:.0f}ms (success={response.success})"
            )

            return ProviderResponse(
                provider_id=provider_id,
                model=response.model,
                text=response.text,
                latency_ms=response.latency_ms,
                tokens=response.tokens,
                success=response.success,
                error=response.error,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"[MultiProviderRotator] {provider_id} failed: {error_msg}")

            return ProviderResponse(
                provider_id=provider_id,
                model="unknown",
                text="",
                latency_ms=latency_ms,
                tokens={"prompt": 0, "completion": 0, "total": 0},
                success=False,
                error=error_msg,
            )

    async def rotate_and_process(
        self,
        provider_ids: List[str],
        question: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        stop_on_first_success: bool = False,
    ) -> RotationResult:
        """
        Process question with multiple providers sequentially.

        Args:
            provider_ids: List of provider IDs to use
            question: User question
            system_prompt: Optional system prompt
            temperature: Generation temperature
            stop_on_first_success: Stop after first successful generation

        Returns:
            RotationResult with all responses
        """
        start_time = time.time()
        responses: Dict[str, ProviderResponse] = {}
        providers_failed = 0

        # Build messages — XML boundary delimiters (Phase 4.5.1)
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": f"<system_instruction>\n{system_prompt}\n</system_instruction>"
            })
        messages.append({
            "role": "user",
            "content": f"<user_query>\n{question}\n</user_query>"
        })

        logger.info(
            f"[MultiProviderRotator] Starting rotation with {len(provider_ids)} providers"
        )

        for i, provider_id in enumerate(provider_ids):
            logger.info(
                f"[MultiProviderRotator] Processing provider {i+1}/{len(provider_ids)}: {provider_id}"
            )

            response = await self.generate_single(
                provider_id=provider_id,
                messages=messages,
                temperature=temperature,
                unload_after=True,  # Always unload to free resources
            )

            responses[provider_id] = response

            if not response.success:
                providers_failed += 1

            if stop_on_first_success and response.success:
                logger.info(
                    f"[MultiProviderRotator] Success with {provider_id}, stopping rotation"
                )
                break

        total_duration_ms = (time.time() - start_time) * 1000

        result = RotationResult(
            responses=responses,
            total_duration_ms=total_duration_ms,
            providers_processed=len(responses),
            providers_failed=providers_failed,
        )

        logger.info(
            f"[MultiProviderRotator] Rotation complete: {result.providers_processed} providers, "
            f"{providers_failed} failed, {total_duration_ms:.0f}ms total"
        )

        return result

    async def batch_process(
        self,
        provider_id: str,
        questions: List[str],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        unload_when_done: bool = True,
    ) -> List[ProviderResponse]:
        """
        Process multiple questions with a single provider.

        Args:
            provider_id: Provider identifier
            questions: List of questions
            system_prompt: Optional system prompt
            temperature: Generation temperature
            unload_when_done: Unload model after batch (if supported)

        Returns:
            List of ProviderResponse for each question
        """
        logger.info(
            f"[MultiProviderRotator] Batch processing {len(questions)} questions with {provider_id}"
        )

        provider = self.providers.get(provider_id)
        if not provider:
            error_resp = ProviderResponse(
                provider_id=provider_id,
                model="unknown",
                text="",
                latency_ms=0.0,
                tokens={"prompt": 0, "completion": 0, "total": 0},
                success=False,
                error=f"Provider '{provider_id}' not found",
            )
            return [error_resp] * len(questions)

        # Preload model if VRAM management supported
        metadata = provider.get_metadata()
        if metadata.supports_vram_management:
            await provider.preload_model(metadata.model_id, keep_alive="5m")
            logger.debug(f"[MultiProviderRotator] Preloaded {metadata.model_id}")

        responses = []
        for i, question in enumerate(questions):
            # XML boundary delimiters (Phase 4.5.1)
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": f"<system_instruction>\n{system_prompt}\n</system_instruction>"
                })
            messages.append({
                "role": "user",
                "content": f"<user_query>\n{question}\n</user_query>"
            })

            # Only unload on last question if requested
            is_last = i == len(questions) - 1
            unload = unload_when_done and is_last

            response = await self.generate_single(
                provider_id=provider_id,
                messages=messages,
                temperature=temperature,
                unload_after=unload,
            )
            responses.append(response)

        return responses

    async def batch_sequential_providers(
        self,
        provider_ids: List[str],
        questions: List[str],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> BatchProviderResult:
        """
        Process multiple questions with multiple providers, one provider at a time.

        OPTIMAL STRATEGY:
        1. For each provider:
           a. Preload the model (if VRAM-managed)
           b. Process ALL questions
           c. Unload the model
        2. Move to next provider

        Args:
            provider_ids: List of provider IDs to use
            questions: List of questions to process
            system_prompt: Optional system prompt
            temperature: Generation temperature

        Returns:
            BatchProviderResult with all responses organized by provider
        """
        start_time = time.time()
        results: Dict[str, List[ProviderResponse]] = {}

        logger.info(
            f"[MultiProviderRotator] Batch sequential: {len(provider_ids)} providers × "
            f"{len(questions)} questions"
        )

        for provider_idx, provider_id in enumerate(provider_ids):
            logger.info(
                f"[MultiProviderRotator] Loading provider {provider_idx+1}/{len(provider_ids)}: {provider_id}"
            )

            provider_responses = await self.batch_process(
                provider_id=provider_id,
                questions=questions,
                system_prompt=system_prompt,
                temperature=temperature,
                unload_when_done=True,
            )

            results[provider_id] = provider_responses

            logger.info(
                f"[MultiProviderRotator] Provider {provider_id} done: "
                f"{len(provider_responses)} responses"
            )

        total_duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f"[MultiProviderRotator] Batch sequential complete: "
            f"{len(provider_ids)} providers × {len(questions)} questions "
            f"in {total_duration_ms:.0f}ms"
        )

        return BatchProviderResult(
            results=results,
            total_duration_ms=total_duration_ms,
            providers_processed=len(provider_ids),
            questions_per_provider=len(questions),
        )
