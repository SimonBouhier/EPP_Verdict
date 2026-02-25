"""
ESMM Phase 2 - TRIPLET EXTRACTOR
=================================

Main orchestrator for multi-model triplet extraction with consensus.

Pipeline:
1. Multi-model generation (batch_sequential_models)
2. Parse + validation (TripletValidator)
3. Consensus voting (ConsensusEngine)
4. Entity resolution (EntityResolver)
5. Relation normalization (RelationNormalizer)
6. Duplicate detection (cache + DB)
7. Graph injection (GraphDelta)
8. Extraction logging

Key Optimizations:
- tenacity retry for transient failures
- LRU cache for duplicate detection
- Lazy initialization with asyncio.Lock
- Model whitelist for security
- Structured logging for observability

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import hashlib
import asyncio
import time
import logging
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from .multi_provider_rotator import MultiProviderRotator, BatchProviderResult
from .triplet_validator import TripletValidator
from .consensus_engine import ConsensusEngine, ConsensusTriplet
from .prompts import get_triplet_extraction_prompt
from services.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# MODEL VALIDATION (Phase 0.3 — Provider-agnostic)
# ============================================================================
# Per Axiom 1 (Obsolescence permanente des modèles):
# Any model implementing the ModelProvider interface enters the system.
# No hardcoded whitelist — validation happens via ProviderRegistry at runtime.


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ExtractionResult:
    """
    Result of triplet extraction pipeline.

    Contains both extraction metrics and the actual consensus triplets.
    """
    triplets_extracted: int
    triplets_injected: int
    triplets_skipped: int
    consensus_triplets: List[ConsensusTriplet]
    new_concepts_created: int
    duration_ms: float
    models_used: List[str]
    input_hash: str  # SHA256 hash of input text for audit
    skipped_reasons: Dict[str, int] = field(default_factory=dict)
    # ADR-010: diagnostics from ConsensusResult
    vote_entropy: float = 0.0
    semantic_dispersion: Optional[float] = None
    triplets_before_consensus: int = 0
    triplets_after_consensus: int = 0
    # ADR-011-v2: raw per-model triplets for fingerprinting
    raw_model_triplets: Dict[str, List] = field(default_factory=dict)


@dataclass
class InjectionResult:
    """Result of a single triplet injection."""
    success: bool
    delta_id: Optional[int] = None
    extraction_id: Optional[int] = None
    reason: Optional[str] = None


# ============================================================================
# TRIPLET EXTRACTOR
# ============================================================================

class TripletExtractor:
    """
    Main orchestrator for multi-model triplet extraction.

    Coordinates the entire pipeline from text input to graph injection,
    with multi-model consensus for reliability.

    Thread Safety:
    - Uses asyncio.Lock for lazy initialization
    - Duplicate cache is not thread-safe (single-request use only)

    Usage:
        extractor = TripletExtractor(db=db, models=["llama3.1:8b", "mistral:7b"])
        result = await extractor.extract_from_text(
            text="Entropy increases in isolated systems.",
            inject_to_graph=True
        )
    """

    def __init__(
        self,
        db,
        models: List[str] = None,
        min_consensus: float = 0.5,
        min_confidence: float = 0.5,
    ):
        """
        Initialize triplet extractor.

        Args:
            db: ISpaceDB instance for database operations
            models: List of model names to use (required, no default)
            min_consensus: Minimum agreement ratio for consensus (0.0-1.0)
            min_confidence: Minimum confidence for triplet validation

        Raises:
            ValueError: If models list is empty or not provided
        """
        self.db = db

        # Models must be provided explicitly (Phase 0.3 — no hardcoded defaults)
        if not models:
            raise ValueError("models list is required - no hardcoded defaults")
        self.models = models

        # Configuration
        self.min_confidence = min_confidence
        self.min_consensus = min_consensus

        # Components
        self.validator = TripletValidator(min_confidence=min_confidence)
        self.consensus_engine = ConsensusEngine(min_agreement=min_consensus)

        # Lazy initialized components (with lock)
        self._entity_resolver = None
        self._relation_normalizer = None
        self._init_lock = asyncio.Lock()

        # Duplicate cache (LRU-like, session-scoped)
        self._duplicate_cache: Dict[str, bool] = {}
        self._cache_max_size = 1000

        # Prompt cache
        self._prompt_cache: Dict[str, str] = {}

        logger.info(
            f"[TripletExtractor] Initialized",
            extra={
                "models": self.models,
                "min_consensus": min_consensus,
                "min_confidence": min_confidence
            }
        )

    async def _get_entity_resolver(self):
        """
        Get or lazily initialize EntityResolver (thread-safe).
        """
        if self._entity_resolver is None:
            async with self._init_lock:
                if self._entity_resolver is None:
                    from services.entity_resolver import get_entity_resolver
                    self._entity_resolver = await get_entity_resolver(db=self.db)
        return self._entity_resolver

    async def _get_relation_normalizer(self):
        """
        Get or lazily initialize RelationNormalizer (thread-safe).
        """
        if self._relation_normalizer is None:
            async with self._init_lock:
                if self._relation_normalizer is None:
                    from services.relation_normalizer import get_relation_normalizer
                    self._relation_normalizer = await get_relation_normalizer(db=self.db)
        return self._relation_normalizer

    def _get_cached_prompt(self, text: str) -> str:
        """
        Get or cache the extraction prompt for a text.

        Uses first 8 chars of text hash as cache key.
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:8]
        if text_hash not in self._prompt_cache:
            self._prompt_cache[text_hash] = get_triplet_extraction_prompt(text)
            # Limit cache size
            if len(self._prompt_cache) > 100:
                # Remove oldest entries (simple approach)
                keys_to_remove = list(self._prompt_cache.keys())[:50]
                for k in keys_to_remove:
                    del self._prompt_cache[k]
        return self._prompt_cache[text_hash]

    def _check_duplicate_cached(self, triplet_hash: str) -> Optional[bool]:
        """
        Check if triplet exists in local cache.

        Returns:
            True if exists, False if not exists, None if not in cache
        """
        return self._duplicate_cache.get(triplet_hash)

    def _add_to_duplicate_cache(self, triplet_hash: str, exists: bool) -> None:
        """
        Add triplet to duplicate cache with LRU-like eviction.
        """
        if len(self._duplicate_cache) >= self._cache_max_size:
            # Simple eviction: remove first 10% of entries
            keys_to_remove = list(self._duplicate_cache.keys())[:100]
            for k in keys_to_remove:
                del self._duplicate_cache[k]
        self._duplicate_cache[triplet_hash] = exists

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def _generate_with_retry(
        self,
        rotator: MultiProviderRotator,
        provider_ids: List[str],
        text: str
    ) -> BatchProviderResult:
        """
        Generate with automatic retry on transient failures.

        Retries up to 3 times with exponential backoff for:
        - Timeouts
        - VRAM exhaustion
        - Network errors
        """
        # MultiProviderRotator expects questions as List[List[Dict]]
        # Each question is a list of messages
        messages = [{"role": "user", "content": text}]

        return await rotator.batch_sequential_providers(
            provider_ids=provider_ids,
            questions=[messages],  # List of questions (each question is list of messages)
            system_prompt=self._get_cached_prompt(text),
            temperature=0.3  # Low temperature for consistency
        )

    async def extract_from_text(
        self,
        text: str,
        cycle_id: Optional[int] = None,
        event_id: Optional[int] = None,
        session_id: Optional[str] = None,
        inject_to_graph: bool = True,
        model_weights: Optional[Dict[str, float]] = None,
    ) -> ExtractionResult:
        """
        Extract triplets from text with multi-model consensus.

        Pipeline:
        1. Generate responses from multiple models
        2. Parse and validate LLM outputs
        3. Compute consensus across models
        4. Resolve entities and normalize relations
        5. Detect duplicates (cache + DB)
        6. Inject new triplets to graph
        7. Log extractions

        Args:
            text: Input text to extract triplets from
            cycle_id: Optional exploration cycle ID for logging
            event_id: Optional event ID for logging
            session_id: Optional session ID for delta tracking
            inject_to_graph: If True, inject triplets to graph

        Returns:
            ExtractionResult with metrics and consensus triplets
        """
        start_time = time.time()
        input_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        logger.info(
            "[TripletExtractor] Extraction started",
            extra={
                "input_hash": input_hash,
                "text_length": len(text),
                "models": self.models,
                "min_consensus": self.min_consensus
            }
        )

        # =====================================================================
        # STEP 1: Multi-model generation
        # =====================================================================
        # Create MultiProviderRotator with model-specific Ollama providers
        # Each model gets its own OllamaProvider instance
        from services.providers.ollama import OllamaProvider

        providers = {}
        for model in self.models:
            # Create a provider ID that includes the model name
            provider_id = f"ollama-{model.replace(':', '_').replace('.', '_')}"
            # Create a dedicated OllamaProvider instance for this model
            providers[provider_id] = OllamaProvider(model=model, timeout=120.0)
            logger.debug(f"[TripletExtractor] Created provider {provider_id} for model {model}")

        if not providers:
            raise RuntimeError("No models configured for extraction")

        rotator = MultiProviderRotator(providers=providers)
        provider_ids = list(providers.keys())

        try:
            result = await self._generate_with_retry(rotator, provider_ids, text)
        except RetryError as e:
            logger.error(f"[TripletExtractor] Generation failed after retries: {e}")
            raise
        except Exception as e:
            logger.error(f"[TripletExtractor] Generation error: {e}")
            raise

        # =====================================================================
        # STEP 2: Parse + Validation
        # =====================================================================
        model_triplets: Dict[str, List] = {}

        # Map provider_ids back to model names for consensus
        # provider_id format: "ollama-llama3_1_8b" -> model: "llama3.1:8b"
        provider_to_model = {
            provider_id: model
            for model, provider_id in zip(self.models, provider_ids)
        }

        for provider_id, responses in result.results.items():
            model_name = provider_to_model.get(provider_id, provider_id)
            model_triplets[model_name] = []
            for response in responses:
                try:
                    raw = self.validator.parse_llm_output(response.text)
                    valid, _ = self.validator.validate_batch(raw)
                    model_triplets[model_name].extend(valid)
                # AUDIT[A2-014] 🟡 FRAGILE: JSON invalide du LLM → retourne liste vide — perte silencieuse de triplets.
                except Exception as e:
                    logger.warning(
                        f"[TripletExtractor] Validation failed for {model_name}: {e}"
                    )

        total_raw = sum(len(t) for t in model_triplets.values())
        logger.debug(
            f"[TripletExtractor] Validated {total_raw} triplets from "
            f"{len(model_triplets)} models"
        )

        # =====================================================================
        # STEP 3: Consensus
        # =====================================================================
        consensus_result = await self.consensus_engine.compute_consensus(
            model_triplets,
            pre_filter_confidence=self.min_confidence * 0.6,
            model_weights=model_weights,
        )
        consensus_triplets = consensus_result.triplets

        logger.info(
            "[TripletExtractor] Consensus computed",
            extra={
                "triplets_before_consensus": consensus_result.triplets_before_consensus,
                "triplets_after_consensus": consensus_result.triplets_after_consensus,
                "models_contributed": list(model_triplets.keys())
            }
        )

        # =====================================================================
        # STEP 4-7: Resolution + Injection
        # =====================================================================
        entity_resolver = await self._get_entity_resolver()
        relation_normalizer = await self._get_relation_normalizer()

        injected = 0
        skipped = 0
        new_concepts = 0
        skipped_reasons: Dict[str, int] = defaultdict(int)
        deltas_to_apply = []

        for triplet in consensus_triplets:
            # Check duplicate cache first
            cached = self._check_duplicate_cached(triplet.triplet_hash)
            if cached is True:
                skipped += 1
                skipped_reasons["duplicate_cached"] += 1
                continue

            # Resolve entities
            try:
                subject_result = await entity_resolver.resolve(triplet.subject)
                object_result = await entity_resolver.resolve(triplet.object)
            except Exception as e:
                logger.warning(f"[TripletExtractor] Entity resolution failed: {e}")
                skipped += 1
                skipped_reasons["resolution_failed"] += 1
                continue

            if subject_result.is_new:
                new_concepts += 1
            if object_result.is_new:
                new_concepts += 1

            # Normalize relation
            try:
                relation_canonical = await relation_normalizer.normalize(
                    triplet.relation
                )
            except Exception as e:
                logger.warning(f"[TripletExtractor] Relation normalization failed: {e}")
                relation_canonical = "related_to"  # Fallback

            # Check DB duplicate
            try:
                existing = await self._check_db_duplicate(
                    subject_result.canonical_id,
                    object_result.canonical_id,
                    relation_canonical
                )
            except Exception as e:
                logger.warning(f"[TripletExtractor] DB check failed: {e}")
                existing = None

            if existing:
                self._add_to_duplicate_cache(triplet.triplet_hash, True)
                skipped += 1
                skipped_reasons["duplicate_db"] += 1
                continue

            self._add_to_duplicate_cache(triplet.triplet_hash, False)

            # Prepare for batch insert
            deltas_to_apply.append({
                "subject": subject_result.canonical_id,
                "object": object_result.canonical_id,
                "relation": relation_canonical,
                "weight": triplet.consensus_score,
                "models": triplet.contributing_models,
                "triplet": triplet
            })

        # =====================================================================
        # STEP 7: Batch injection
        # =====================================================================
        if inject_to_graph and deltas_to_apply:
            injected = await self._batch_inject(
                deltas_to_apply, cycle_id, event_id, session_id
            )

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "[TripletExtractor] Extraction complete",
            extra={
                "input_hash": input_hash,
                "triplets_extracted": len(consensus_triplets),
                "triplets_injected": injected,
                "triplets_skipped": skipped,
                "new_concepts": new_concepts,
                "duration_ms": round(duration_ms, 2),
                "skipped_reasons": dict(skipped_reasons)
            }
        )

        return ExtractionResult(
            triplets_extracted=len(consensus_triplets),
            triplets_injected=injected,
            triplets_skipped=skipped,
            consensus_triplets=consensus_triplets,
            new_concepts_created=new_concepts,
            duration_ms=round(duration_ms, 2),
            models_used=self.models,
            input_hash=input_hash,
            skipped_reasons=dict(skipped_reasons),
            vote_entropy=consensus_result.vote_entropy,
            semantic_dispersion=consensus_result.semantic_dispersion,
            triplets_before_consensus=consensus_result.triplets_before_consensus,
            triplets_after_consensus=consensus_result.triplets_after_consensus,
            raw_model_triplets=dict(model_triplets),
        )

    async def _check_db_duplicate(
        self,
        source: str,
        target: str,
        relation_type: str
    ) -> Optional[Dict]:
        """
        Check if a relation already exists in the database.
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT weight, extraction_count
                    FROM relations
                    WHERE source = ? AND target = ? AND relation_type = ?
                    """,
                    (source, target, relation_type)
                )
                row = await cursor.fetchone()
                if row:
                    return {"weight": row[0], "count": row[1]}
        except Exception as e:
            logger.warning(f"[TripletExtractor] DB duplicate check error: {e}")
        return None

    async def _batch_inject(
        self,
        deltas: List[Dict],
        cycle_id: Optional[int],
        event_id: Optional[int],
        session_id: Optional[str]
    ) -> int:
        """
        Inject multiple triplets to the graph.

        Each triplet:
        1. Creates a graph delta (add_edge)
        2. Stores extraction record
        3. Links extraction to delta

        Returns:
            Number of successfully injected triplets
        """
        injected = 0

        for delta_data in deltas:
            try:
                # Insert relation directly
                async with self.db.connection() as conn:
                    # Insert relation
                    await conn.execute(
                        """
                        INSERT INTO relations (source, target, relation_type, weight, model_source)
                        VALUES (?, ?, ?, ?, ?)
                        -- AUDIT[A3-004] 🔴→✅ FIXED Phase 4.1: ON CONFLICT aligné sur PK (source, target).
                        ON CONFLICT(source, target) DO UPDATE SET
                            weight = MAX(weight, excluded.weight),
                            extraction_count = extraction_count + 1
                        """,
                        (
                            delta_data["subject"],
                            delta_data["object"],
                            delta_data["relation"],
                            delta_data["weight"],
                            ",".join(delta_data["models"])
                        )
                    )
                    await conn.commit()

                # Store extraction record if method exists
                if hasattr(self.db, 'store_triplet_extraction'):
                    try:
                        await self.db.store_triplet_extraction(
                            subject=delta_data["triplet"].subject,
                            relation=delta_data["triplet"].relation,
                            object_=delta_data["triplet"].object,
                            confidence=delta_data["triplet"].consensus_score,
                            extraction_method="llm_structured",
                            model_source=",".join(delta_data["models"]),
                            cycle_id=cycle_id,
                            event_id=event_id
                        )
                    except Exception as e:
                        logger.debug(f"[TripletExtractor] Extraction log skipped: {e}")

                injected += 1

            except Exception as e:
                logger.error(
                    f"[TripletExtractor] Injection failed: {e}",
                    extra={"triplet": delta_data["triplet"].triplet_hash}
                )

        return injected

    def clear_caches(self) -> None:
        """Clear all caches (duplicate + prompt)."""
        self._duplicate_cache.clear()
        self._prompt_cache.clear()
        logger.debug("[TripletExtractor] Caches cleared")


# ============================================================================
# VERDICT RESPONSE PARSING (VERIFY mode)
# ============================================================================


def _parse_verdict_response(
    text: str,
    claim_text: str = "",
) -> Dict[str, Any]:
    """
    Parse a VERIFY-mode verdict response from an LLM.

    Expected JSON format:
        {"verdict": "SUPPORTED", "confidence": 0.85,
         "evidence": [...], "reasoning": "..."}

    Returns:
        Dict with keys: verdict, confidence, evidence, reasoning, triplets
        where triplets includes the verdict-as-triplet encoding.
    """
    import json
    import re

    # Try to extract JSON from the response
    text = text.strip()

    # Try direct JSON parse first
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if parsed is None:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "confidence": 0.0,
            "evidence": [],
            "reasoning": "Failed to parse LLM response as JSON",
            "claim_type": "empirical",
            "triplets": [],
        }

    verdict = parsed.get("verdict", "INSUFFICIENT_EVIDENCE")
    confidence = float(parsed.get("confidence", 0.0))
    evidence = parsed.get("evidence", [])
    reasoning = parsed.get("reasoning", "")

    # Extract and normalize claim_type
    claim_type = parsed.get("claim_type", "empirical")
    valid_claim_types = {"empirical", "definitional", "normative", "speculative"}
    if claim_type.lower() not in valid_claim_types:
        claim_type = "empirical"
    else:
        claim_type = claim_type.lower()

    # Normalize verdict value
    valid_verdicts = {"SUPPORTED", "CONTESTED", "INSUFFICIENT_EVIDENCE"}
    if verdict.upper() not in valid_verdicts:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = verdict.upper()

    # Build triplets list: verdict triplet + evidence triplets
    triplets = []

    # Verdict-as-triplet (S5 encoding)
    triplets.append({
        "subject": claim_text,
        "relation": "verdict",
        "object": verdict,
        "confidence": confidence,
    })

    # Evidence triplets
    for ev in evidence:
        if isinstance(ev, dict) and "subject" in ev and "object" in ev:
            triplets.append({
                "subject": ev.get("subject", ""),
                "relation": ev.get("relation", "related_to"),
                "object": ev.get("object", ""),
                "confidence": float(ev.get("confidence", 0.5)),
            })

    return {
        "verdict": verdict,
        "confidence": confidence,
        "evidence": evidence,
        "reasoning": reasoning,
        "claim_type": claim_type,
        "triplets": triplets,
    }


# ============================================================================
# SINGLETON
# ============================================================================

_extractor_instance: Optional[TripletExtractor] = None
_extractor_lock = asyncio.Lock()


async def get_triplet_extractor(
    db=None,
    models: List[str] = None,
    min_consensus: float = 0.5,
    min_confidence: float = 0.5
) -> TripletExtractor:
    """
    Get or create singleton TripletExtractor instance.

    If db is explicitly provided and differs from the current instance's db,
    the singleton is invalidated and recreated with the new db.
    When db is None, falls back to get_db() (config-based default).
    """
    global _extractor_instance

    # If db explicitly provided and different from current instance's db,
    # invalidate singleton (caller wants a specific DB)
    if db is not None and _extractor_instance is not None:
        if _extractor_instance.db is not db:
            _extractor_instance = None

    if _extractor_instance is None:
        async with _extractor_lock:
            if _extractor_instance is None:
                if db is None:
                    from database import get_db
                    db = await get_db()
                _extractor_instance = TripletExtractor(
                    db=db,
                    models=models,
                    min_consensus=min_consensus,
                    min_confidence=min_confidence
                )

    return _extractor_instance


async def close_triplet_extractor() -> None:
    """Close and clear the singleton extractor."""
    global _extractor_instance
    if _extractor_instance:
        _extractor_instance.clear_caches()
        _extractor_instance = None
