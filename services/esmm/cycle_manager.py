"""
ESMM Phase 3 - EXPLORATION CYCLE MANAGER
=========================================

Gere les trois types de cycles d'exploration:
- DIVERGENT: Exploration large depuis concepts seed
- DEBATE: Dialectique sur contradictions
- META: Reflexion sur connaissances extraites

Optimisations:
- Selection dynamique des concepts (centralite, stabilite, diversite)
- Cache des reponses modeles
- Rotation des templates (anti-redondance)
- Timeouts adaptatifs par type de cycle

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import time
import asyncio
import logging
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

from .cycle_prompts import (
    CycleType,
    CYCLE_TEMPLATES,
    SYSTEM_PROMPTS,
    get_template,
    get_system_prompt,
    format_triplets_for_prompt,
    get_template_count
)
from .consensus_engine import ConsensusTriplet

if TYPE_CHECKING:
    from database.engine import ISpaceDB
    from .multi_provider_rotator import MultiProviderRotator
    from .triplet_extractor import TripletExtractor

logger = logging.getLogger(__name__)

# Phase 4.5.1 — Max length for sanitized concept names in prompts
_MAX_CONCEPT_LEN = 200


def _sanitize_concept(value: str) -> str:
    """Sanitize a concept string before template insertion (Phase 4.5.1).

    Strips XML-like tags, control characters, and truncates to safe length
    to prevent prompt injection via concept names.
    """
    import re
    # Strip XML/HTML tags
    cleaned = re.sub(r"<[^>]*>", "", value)
    # Strip control characters (keep printable + common whitespace)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    # Truncate
    return cleaned[:_MAX_CONCEPT_LEN].strip()


# ============================================================================
# TIMEOUTS PAR TYPE DE CYCLE (secondes)
# ============================================================================

# AUDIT[A8-006] 🟡 FRAGILE: timeouts hardcodés — config.yaml::esmm.timeout_per_cycle_seconds ignoré.
CYCLE_TIMEOUTS = {
    CycleType.DIVERGENT: 60,   # Exploration simple (60s: cold models need warmup)
    CycleType.DEBATE: 60,      # Dialectique complexe
    CycleType.META: 60         # Meta-reflexion
}


@dataclass
class CycleResult:
    """
    Resultat d'un cycle d'exploration.

    Attributes:
        cycle_id: ID du cycle dans la DB
        cycle_type: Type de cycle (DIVERGENT, DEBATE, META)
        iteration: Numero d'iteration du cycle
        question: Question posee aux modeles
        responses: Reponses brutes par modele
        triplets_extracted: Nombre de triplets extraits
        consensus_triplets: Liste des triplets avec consensus
        exploration_metrics: Metriques du cycle
        duration_ms: Duree du cycle en millisecondes
    """
    cycle_id: int
    cycle_type: CycleType
    iteration: int
    question: str
    responses: Dict[str, str]
    triplets_extracted: int
    consensus_triplets: List[ConsensusTriplet]
    exploration_metrics: Dict[str, float]
    duration_ms: float
    # ADR-010: diagnostics threading
    vote_entropy: float = 0.0
    semantic_dispersion: Optional[float] = None
    triplets_before_consensus: int = 0
    triplets_after_consensus: int = 0


class ExplorationCycleManager:
    """
    Gestionnaire des cycles d'exploration ESMM.

    Orchestre l'execution des cycles divergent, debate et meta
    avec selection dynamique des concepts et caching.
    """

    def __init__(
        self,
        db: "ISpaceDB",
        model_rotator: "MultiProviderRotator",
        triplet_extractor: "TripletExtractor",
        run_id: int,
        models: List[str] = None
    ):
        """
        Initialise le gestionnaire de cycles.

        Args:
            db: Instance de la base de donnees
            model_rotator: Multi-provider rotator pour orchestration des LLMs
            triplet_extractor: Extracteur de triplets multi-modeles
            run_id: ID du run ESMM courant
            models: Liste des modeles a utiliser
        """
        self.db = db
        self.model_rotator = model_rotator
        self.triplet_extractor = triplet_extractor
        self.run_id = run_id
        if not models:
            raise ValueError("models list is required - no hardcoded defaults")
        self.models = models

        # Map model names to provider IDs for MultiProviderRotator
        self.provider_ids = [
            f"ollama-{model.replace(':', '_').replace('.', '_')}"
            for model in self.models
        ]
        self.provider_to_model = dict(zip(self.provider_ids, self.models))

        # Cache des reponses modeles (evite retraitement)
        self._response_cache: Dict[str, Dict[str, str]] = {}
        self._cache_max_size = 100

        # Index de rotation des templates (anti-redondance)
        self._template_rotation_index: Dict[CycleType, int] = defaultdict(int)

        # Compteurs de cycles par type
        self._cycle_counts: Dict[CycleType, int] = defaultdict(int)

        # Triplets recents pour cycles META
        self._recent_triplets: List[ConsensusTriplet] = []
        self._recent_triplets_max = 20

        # Cache des gaps pour selection priorisee
        self._active_gaps: List[Any] = []
        self._gaps_last_updated: float = 0.0

        # Statistiques pour metriques
        self._stats: Dict[str, int] = {
            "retry_successes": 0,
            "retry_failures": 0,
            "gaps_used": 0
        }

        logger.info(
            "[ExplorationCycleManager] Initialized",
            extra={"run_id": run_id, "models": self.models}
        )

    async def execute_cycle(
        self,
        cycle_type: CycleType,
        iteration: int,
        context: Optional[Dict[str, Any]] = None,
        model_weights: Optional[Dict[str, float]] = None,
    ) -> CycleResult:
        """
        Execute un cycle d'exploration complet.

        Pipeline:
        1. Selection des concepts cibles
        2. Generation de la question
        3. Appel multi-modeles
        4. Extraction et consensus
        5. Logging du cycle

        Args:
            cycle_type: Type de cycle a executer
            iteration: Numero d'iteration
            context: Contexte optionnel (triplets recents, domaine, etc.)

        Returns:
            CycleResult avec les triplets extraits et metriques
        """
        start_time = time.time()
        context = context or {}

        logger.info(
            f"[CycleManager] Starting {cycle_type.value} cycle",
            extra={"iteration": iteration, "run_id": self.run_id}
        )

        # 1. Selection des concepts cibles
        target_concepts = await self._select_target_concepts(cycle_type)

        # 2. Generation de la question
        question = self._generate_question(cycle_type, target_concepts, context)

        # 3. Appel multi-modeles avec timeout adaptatif
        timeout = self._get_timeout(cycle_type)
        responses = await self._query_models(question, cycle_type, timeout)

        # 3b. RETRY LOGIC pour cycles META vides (max 3 retries)
        META_MAX_RETRIES = 3
        if not responses and cycle_type == CycleType.META:
            for retry_attempt in range(1, META_MAX_RETRIES + 1):
                logger.warning(
                    f"[CycleManager] RETRY {retry_attempt}/{META_MAX_RETRIES} "
                    f"- Empty response on META cycle",
                    extra={"iteration": iteration, "attempt": retry_attempt}
                )

                retry_responses = await self._retry_with_simplified_prompt(
                    question, cycle_type, timeout
                )

                if retry_responses:
                    logger.info(
                        f"[CycleManager] RETRY SUCCESS (attempt {retry_attempt}/"
                        f"{META_MAX_RETRIES})",
                        extra={
                            "iteration": iteration,
                            "responses_count": len(retry_responses),
                            "models_responded": list(retry_responses.keys())
                        }
                    )
                    self._stats["retry_successes"] = self._stats.get("retry_successes", 0) + 1
                    responses = retry_responses
                    break
            else:
                logger.error(
                    f"[CycleManager] RETRY EXHAUSTED after {META_MAX_RETRIES} attempts",
                    extra={"iteration": iteration}
                )
                self._stats["retry_failures"] = self._stats.get("retry_failures", 0) + 1

        # 3c. COMMIT — hash responses before debate (R-2.2.3)
        if responses and self.run_id:
            import hashlib as _hashlib
            for model_id, response_text in responses.items():
                try:
                    response_hash = _hashlib.sha256(response_text.encode()).hexdigest()
                    await self.db.store_commit(
                        self.run_id, model_id, cycle_type.value, response_hash
                    )
                except Exception as e:
                    logger.warning(f"Commit store failed for {model_id}: {e}")

        # 4. Extraction et consensus
        extraction_result = await self._extract_triplets_from_responses(
            responses, cycle_type, context, model_weights=model_weights
        )

        # 5. Logging du cycle dans la DB
        cycle_id = await self._log_cycle(
            cycle_type=cycle_type,
            iteration=iteration,
            question=question,
            responses=responses,
            target_concepts=target_concepts,
            extraction_result=extraction_result
        )

        # Mettre a jour les triplets recents
        self._update_recent_triplets(extraction_result.get("consensus_triplets", []))

        duration_ms = (time.time() - start_time) * 1000

        # Incrementer le compteur
        self._cycle_counts[cycle_type] += 1

        result = CycleResult(
            cycle_id=cycle_id,
            cycle_type=cycle_type,
            iteration=iteration,
            question=question,
            responses=responses,
            triplets_extracted=extraction_result.get("triplets_extracted", 0),
            consensus_triplets=extraction_result.get("consensus_triplets", []),
            exploration_metrics={
                "target_concepts_count": len(target_concepts),
                "models_used": len(self.models),
                "responses_count": len(responses),
                "timeout_seconds": timeout
            },
            duration_ms=round(duration_ms, 2),
            vote_entropy=extraction_result.get("vote_entropy", 0.0),
            semantic_dispersion=extraction_result.get("semantic_dispersion"),
            triplets_before_consensus=extraction_result.get("triplets_before_consensus", 0),
            triplets_after_consensus=extraction_result.get("triplets_after_consensus", 0),
        )

        logger.info(
            f"[CycleManager] Cycle complete",
            extra={
                "cycle_type": cycle_type.value,
                "iteration": iteration,
                "triplets": result.triplets_extracted,
                "duration_ms": result.duration_ms
            }
        )

        return result

    # ========================================================================
    # SELECTION DYNAMIQUE DES CONCEPTS
    # ========================================================================

    async def _select_target_concepts(
        self,
        cycle_type: CycleType,
        n: int = 5
    ) -> List[str]:
        """
        Selectionne les concepts cibles selon le type de cycle.

        Priorite donnee aux gaps detectes, puis fallback sur la strategie standard.

        Strategies:
        - DIVERGENT: Gaps ISOLATED > concepts a faible degre
        - DEBATE: Gaps UNSTABLE/CONTRADICTION > triplets controverses
        - META: Gaps BRIDGE > concepts recemment extraits

        Args:
            cycle_type: Type de cycle
            n: Nombre de concepts a selectionner

        Returns:
            Liste d'IDs de concepts
        """
        # Essayer d'abord d'utiliser les gaps actifs
        gap_concepts = await self._get_concepts_from_gaps(cycle_type, n)
        if gap_concepts:
            self._stats["gaps_used"] += len(gap_concepts)
            logger.info(
                f"[CycleManager] Using {len(gap_concepts)} concepts from gaps for {cycle_type.value}",
                extra={"gap_concepts": gap_concepts[:3]}
            )
            if len(gap_concepts) >= n:
                return gap_concepts[:n]
            # Completer avec la selection standard
            n_remaining = n - len(gap_concepts)
        else:
            gap_concepts = []
            n_remaining = n

        # Fallback sur la selection standard
        try:
            async with self.db.connection() as conn:
                if cycle_type == CycleType.DIVERGENT:
                    # Priorise concepts a faible couverture
                    cursor = await conn.execute("""
                        SELECT id FROM concepts
                        WHERE degree IS NOT NULL AND degree < 10
                        ORDER BY degree ASC, RANDOM()
                        LIMIT ?
                    """, (n_remaining,))

                elif cycle_type == CycleType.DEBATE:
                    # Triplets controverses
                    cursor = await conn.execute("""
                        SELECT DISTINCT source, target
                        FROM relations
                        WHERE weight < 0.7
                        ORDER BY weight ASC
                        LIMIT ?
                    """, (n * 2,))  # Paires

                elif cycle_type == CycleType.META:
                    # Concepts recemment extraits
                    cursor = await conn.execute("""
                        SELECT DISTINCT subject_canonical
                        FROM triplet_extractions
                        ORDER BY extracted_at DESC
                        LIMIT ?
                    """, (n,))

                else:
                    cursor = await conn.execute(
                        "SELECT id FROM concepts ORDER BY RANDOM() LIMIT ?",
                        (n,)
                    )

                rows = await cursor.fetchall()

                # Aplatir les resultats
                concepts = []
                for row in rows:
                    if isinstance(row, (list, tuple)):
                        concepts.extend([r for r in row if r])
                    else:
                        concepts.append(row)

                # Combiner gaps + concepts standards (eviter doublons)
                all_concepts = gap_concepts + [c for c in concepts if c not in gap_concepts]
                return all_concepts[:n]

        except Exception as e:
            logger.warning(f"[CycleManager] Error selecting concepts: {e}")
            # Fallback: concepts aleatoires + gaps
            fallback = await self._get_random_concepts(n_remaining)
            return (gap_concepts + fallback)[:n]

    async def _get_random_concepts(self, n: int) -> List[str]:
        """Fallback: selection aleatoire de concepts."""
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT id FROM concepts ORDER BY RANDOM() LIMIT ?",
                    (n,)
                )
                return [row[0] for row in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"[CycleManager] Fallback concept selection failed: {e}")
            return ["concept", "relation", "property"]  # Defaults

    async def _get_concepts_from_gaps(
        self,
        cycle_type: CycleType,
        n: int
    ) -> List[str]:
        """
        Extrait des concepts des gaps actifs selon le type de cycle.

        Mapping:
        - DIVERGENT -> Gaps ISOLATED (concepts a faible degre)
        - DEBATE -> Gaps UNSTABLE + CONTRADICTION (relations problematiques)
        - META -> Gaps BRIDGE (ponts manquants entre domaines)

        Args:
            cycle_type: Type de cycle
            n: Nombre de concepts souhaites

        Returns:
            Liste de concepts extraits des gaps
        """
        try:
            async with self.db.connection() as conn:
                concepts = []

                if cycle_type == CycleType.DIVERGENT:
                    # Gaps ISOLATED -> concept_id
                    cursor = await conn.execute("""
                        SELECT json_extract(details, '$.concept_id') as concept
                        FROM knowledge_gaps
                        WHERE gap_type = 'isolated' AND addressed = 0
                        ORDER BY priority DESC
                        LIMIT ?
                    """, (n,))
                    rows = await cursor.fetchall()
                    concepts = [row[0] for row in rows if row[0]]

                elif cycle_type == CycleType.DEBATE:
                    # Gaps UNSTABLE + CONTRADICTION -> source, target
                    cursor = await conn.execute("""
                        SELECT json_extract(details, '$.source') as src,
                               json_extract(details, '$.target') as tgt
                        FROM knowledge_gaps
                        WHERE gap_type IN ('unstable', 'contradiction') AND addressed = 0
                        ORDER BY priority DESC
                        LIMIT ?
                    """, (n,))
                    rows = await cursor.fetchall()
                    for row in rows:
                        if row[0]:
                            concepts.append(row[0])
                        if row[1] and row[1] not in concepts:
                            concepts.append(row[1])

                elif cycle_type == CycleType.META:
                    # Gaps BRIDGE -> representative_a, representative_b
                    cursor = await conn.execute("""
                        SELECT json_extract(details, '$.representative_a') as rep_a,
                               json_extract(details, '$.representative_b') as rep_b
                        FROM knowledge_gaps
                        WHERE gap_type = 'bridge' AND addressed = 0
                        ORDER BY priority DESC
                        LIMIT ?
                    """, (n,))
                    rows = await cursor.fetchall()
                    for row in rows:
                        if row[0]:
                            concepts.append(row[0])
                        if row[1] and row[1] not in concepts:
                            concepts.append(row[1])

                return concepts[:n]

        except Exception as e:
            logger.debug(f"[CycleManager] No gaps available for {cycle_type.value}: {e}")
            return []

    # ========================================================================
    # GENERATION DE QUESTIONS
    # ========================================================================

    def _generate_question(
        self,
        cycle_type: CycleType,
        concepts: List[str],
        context: Dict[str, Any]
    ) -> str:
        """
        Genere une question pour le cycle avec rotation anti-redondance.

        Args:
            cycle_type: Type de cycle
            concepts: Concepts cibles
            context: Contexte additionnel

        Returns:
            Question formatee
        """
        # Obtenir le template avec rotation
        template_index = self._template_rotation_index[cycle_type]
        template = get_template(cycle_type, template_index)

        # Incrementer l'index pour le prochain appel
        template_count = get_template_count(cycle_type)
        self._template_rotation_index[cycle_type] = (template_index + 1) % template_count

        # Formater selon le type
        try:
            # Phase 4.5.1 — sanitize concepts before template insertion
            safe = [_sanitize_concept(c) for c in concepts]

            if cycle_type == CycleType.DIVERGENT:
                concept = safe[0] if safe else "concept"
                return template.format(concept=concept)

            elif cycle_type == CycleType.DEBATE:
                if len(safe) >= 2:
                    return template.format(
                        thesis=safe[0],
                        antithesis=safe[1],
                        concept_a=safe[0],
                        concept_b=safe[1]
                    )
                return template.format(
                    thesis=safe[0] if safe else "thesis",
                    antithesis="antithesis",
                    concept_a=safe[0] if safe else "A",
                    concept_b="B"
                )

            elif cycle_type == CycleType.META:
                # Formater les triplets recents
                recent_str = format_triplets_for_prompt(self._recent_triplets)
                domain = _sanitize_concept(context.get("domain", "general"))
                return template.format(
                    recent_triplets=recent_str or "aucun triplet recent",
                    domain=domain
                )

        except KeyError as e:
            logger.warning(f"[CycleManager] Template formatting error: {e}")

        # Fallback
        return f"Quelles relations existent pour {concepts[0] if concepts else 'ce concept'}?"

    # ========================================================================
    # APPEL MULTI-MODELES
    # ========================================================================

    async def _query_models(
        self,
        question: str,
        cycle_type: CycleType,
        timeout: int
    ) -> Dict[str, str]:
        """
        Interroge les modeles avec le system prompt approprie.

        Args:
            question: Question a poser
            cycle_type: Type de cycle (pour le system prompt)
            timeout: Timeout en secondes

        Returns:
            Dict model -> reponse
        """
        system_prompt = get_system_prompt(cycle_type)
        responses = {}

        try:
            # Utiliser le model rotator pour les appels sequentiels
            messages = [{"role": "user", "content": question}]
            result = await asyncio.wait_for(
                self.model_rotator.batch_sequential_providers(
                    provider_ids=self.provider_ids,
                    questions=[messages],
                    system_prompt=system_prompt,
                    temperature=0.3
                ),
                timeout=timeout
            )

            # Extraire les reponses et mapper provider_ids -> model names
            for provider_id, provider_responses in result.results.items():
                model_name = self.provider_to_model.get(provider_id, provider_id)
                if provider_responses and len(provider_responses) > 0:
                    responses[model_name] = provider_responses[0].text

        except asyncio.TimeoutError:
            logger.warning(
                f"[CycleManager] Timeout after {timeout}s",
                extra={"cycle_type": cycle_type.value}
            )
        except Exception as e:
            logger.error(f"[CycleManager] Model query error: {e}")

        return responses

    async def _retry_with_simplified_prompt(
        self,
        original_question: str,
        cycle_type: CycleType,
        timeout: int
    ) -> Dict[str, str]:
        """
        Retry avec un prompt simplifie pour recuperer d'une reponse vide.

        Simplifie le prompt pour maximiser les chances de reponse.

        Args:
            original_question: Question originale
            cycle_type: Type de cycle
            timeout: Timeout en secondes

        Returns:
            Dict model -> reponse, ou dict vide si echec
        """
        # Simplifier la question pour META cycles
        simplified_question = (
            "Analysez les concepts mentionnes et identifiez les relations principales. "
            "Repondez sous forme de triplets (sujet, relation, objet). "
            f"Question originale: {original_question[:200]}"
        )

        logger.info(
            "[CycleManager] Retrying with simplified prompt",
            extra={"simplified_length": len(simplified_question)}
        )

        # System prompt simplifie
        simplified_system = (
            "Tu es un assistant qui extrait des triplets de connaissance. "
            "Reponds avec une liste de triplets au format: sujet | relation | objet"
        )

        responses = {}

        try:
            messages = [{"role": "user", "content": simplified_question}]
            result = await asyncio.wait_for(
                self.model_rotator.batch_sequential_providers(
                    provider_ids=self.provider_ids,
                    questions=[messages],
                    system_prompt=simplified_system,
                    temperature=0.5  # Plus creatif pour retry
                ),
                timeout=timeout
            )

            for provider_id, provider_responses in result.results.items():
                model_name = self.provider_to_model.get(provider_id, provider_id)
                if provider_responses and len(provider_responses) > 0:
                    responses[model_name] = provider_responses[0].text

        except asyncio.TimeoutError:
            logger.warning("[CycleManager] Retry timeout")
        except Exception as e:
            logger.error(f"[CycleManager] Retry error: {e}")

        return responses

    # ========================================================================
    # EXTRACTION DE TRIPLETS
    # ========================================================================

    async def _extract_triplets_from_responses(
        self,
        responses: Dict[str, str],
        cycle_type: CycleType,
        context: Dict[str, Any],
        model_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Extrait les triplets des reponses avec consensus.

        Args:
            responses: Reponses par modele
            cycle_type: Type de cycle
            context: Contexte additionnel

        Returns:
            Dict avec triplets_extracted, consensus_triplets, etc.
        """
        if not responses:
            return {
                "triplets_extracted": 0,
                "consensus_triplets": [],
                "models_contributed": []
            }

        # Combiner toutes les reponses en un texte
        combined_text = "\n\n".join([
            f"[{model}]: {response}"
            for model, response in responses.items()
        ])

        try:
            # Utiliser l'extracteur de triplets
            result = await self.triplet_extractor.extract_from_text(
                text=combined_text,
                cycle_id=None,  # Sera set plus tard
                inject_to_graph=True,
                model_weights=model_weights,
            )

            return {
                "triplets_extracted": result.triplets_extracted,
                "consensus_triplets": result.consensus_triplets,
                "triplets_injected": result.triplets_injected,
                "new_concepts": result.new_concepts_created,
                "models_contributed": list(responses.keys()),
                "vote_entropy": result.vote_entropy,
                "semantic_dispersion": result.semantic_dispersion,
                "triplets_before_consensus": result.triplets_before_consensus,
                "triplets_after_consensus": result.triplets_after_consensus,
            }

        # AUDIT[A2-013] 🟡 FRAGILE: échecs d'extraction individuels accumulés sans arrêt.
        except Exception as e:
            logger.error(f"[CycleManager] Triplet extraction error: {e}")
            return {
                "triplets_extracted": 0,
                "consensus_triplets": [],
                "error": str(e)
            }

    # ========================================================================
    # LOGGING
    # ========================================================================

    async def _log_cycle(
        self,
        cycle_type: CycleType,
        iteration: int,
        question: str,
        responses: Dict[str, str],
        target_concepts: List[str],
        extraction_result: Dict[str, Any]
    ) -> int:
        """
        Enregistre le cycle dans la base de donnees.

        Returns:
            cycle_id
        """
        try:
            # Log du cycle
            cycle_id = await self.db.log_exploration_cycle(
                run_id=self.run_id,
                cycle_type=cycle_type.value,
                iteration=iteration,
                question_template=get_template(cycle_type, self._template_rotation_index[cycle_type] - 1),
                question_rendered=question,
                responses=responses,
                target_concepts=target_concepts,
                response_latencies={}  # TODO: track latencies
            )

            # Mise a jour avec les resultats d'extraction
            triplets_data = [
                {
                    "subject": t.subject,
                    "relation": t.relation,
                    "object": t.object,
                    "consensus_score": t.consensus_score
                }
                for t in extraction_result.get("consensus_triplets", [])
            ]

            consensus_map = {
                t.triplet_hash: t.consensus_score
                for t in extraction_result.get("consensus_triplets", [])
            }

            await self.db.update_cycle_extraction(
                cycle_id=cycle_id,
                triplets_extracted=extraction_result.get("triplets_extracted", 0),
                triplets_data=triplets_data,
                consensus_map=consensus_map,
                exploration_metrics={
                    "target_concepts": len(target_concepts),
                    "models_used": len(self.models),
                    "responses_count": len(responses)
                }
            )

            return cycle_id

        except Exception as e:
            logger.error(f"[CycleManager] Error logging cycle: {e}")
            return -1

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _get_timeout(self, cycle_type: CycleType) -> int:
        """Retourne le timeout en secondes pour un type de cycle."""
        return CYCLE_TIMEOUTS.get(cycle_type, 45)

    def _update_recent_triplets(
        self,
        new_triplets: List[ConsensusTriplet]
    ) -> None:
        """Met a jour la liste des triplets recents pour cycles META."""
        self._recent_triplets.extend(new_triplets)
        # Garder seulement les plus recents
        if len(self._recent_triplets) > self._recent_triplets_max:
            self._recent_triplets = self._recent_triplets[-self._recent_triplets_max:]

    def get_cycle_counts(self) -> Dict[str, int]:
        """Retourne les compteurs de cycles par type."""
        return {ct.value: count for ct, count in self._cycle_counts.items()}

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du manager.

        Returns:
            Dict avec retry_successes, retry_failures, gaps_used, cycle_counts
        """
        return {
            **self._stats,
            "cycle_counts": self.get_cycle_counts()
        }

    def clear_caches(self) -> None:
        """Vide les caches internes."""
        self._response_cache.clear()
        self._recent_triplets.clear()


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

async def create_cycle_manager(
    db: "ISpaceDB",
    run_id: int,
    models: List[str] = None,
    providers: Dict = None,
    min_consensus: float = 0.5,
) -> ExplorationCycleManager:
    """
    Factory function pour ExplorationCycleManager.

    Initialise les composants necessaires (model_rotator, triplet_extractor).

    Args:
        db: Instance de la base de donnees
        run_id: ID du run ESMM
        models: Liste des modeles a utiliser
        providers: Dict {provider_id: ModelProvider} pre-configured (D6).
                   If provided, uses these instead of creating OllamaProvider.
                   Fallback: OllamaProvider if providers is None.

    Returns:
        Instance configuree de ExplorationCycleManager
    """
    from .multi_provider_rotator import MultiProviderRotator
    from .triplet_extractor import get_triplet_extractor

    if not models:
        raise ValueError("models list is required - no hardcoded defaults")

    # Use provided providers or fallback to OllamaProvider (D6)
    if providers is None:
        from services.providers.ollama import OllamaProvider
        providers = {}
        for model in models:
            provider_id = f"ollama-{model.replace(':', '_').replace('.', '_')}"
            providers[provider_id] = OllamaProvider(model=model, timeout=120.0)

    model_rotator = MultiProviderRotator(providers=providers)
    triplet_extractor = await get_triplet_extractor(models=models, min_consensus=min_consensus)

    return ExplorationCycleManager(
        db=db,
        model_rotator=model_rotator,
        triplet_extractor=triplet_extractor,
        run_id=run_id,
        models=models
    )
