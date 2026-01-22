# LYRA-ACE ESMM — Feuille de Route Implémentation

**Destinataire:** Claude Code (VSCode)  
**Date:** 2026-01-21  
**Version:** 1.0  
**Priorité:** Haute

---

## 📋 Contexte

Lyra-ACE évolue vers le protocole ESMM (Exploration Sémantique Multi-Modèles). Cette feuille de route détaille les modifications à apporter au codebase pour supporter :

1. **Canonicalisation sémantique** (résolution d'entités)
2. **Calcul κ différé** (Jaccard immédiat, Ollivier en batch)
3. **Tables ESMM** (runs, cycles, triplets, cochain, gaps)
4. **Relations canoniques** (normalisation des types de relations)

Le fichier `schema_v2.sql` est fourni et remplace entièrement `schema.sql`.

---

## 🗂️ Fichiers à Modifier/Créer

### Priorité 1 — Fondations (Obligatoire)

| Fichier | Action | Description |
|---------|--------|-------------|
| `database/schema.sql` | **REMPLACER** | Par le contenu de `schema_v2.sql` |
| `database/engine.py` | **MODIFIER** | Ajouter méthodes pour aliases, pending_kappa, ESMM |
| `database/__init__.py` | **MODIFIER** | Exporter nouvelles classes/fonctions |

### Priorité 2 — Services Nouveaux

| Fichier | Action | Description |
|---------|--------|-------------|
| `services/entity_resolver.py` | **CRÉER** | Canonicalisation par embeddings |
| `services/relation_normalizer.py` | **CRÉER** | Normalisation des types de relations |
| `services/kappa_worker.py` | **CRÉER** | Job de recalcul κ Ollivier en arrière-plan |

### Priorité 3 — Modifications Existantes

| Fichier | Action | Description |
|---------|--------|-------------|
| `app/llm_client.py` | **MODIFIER** | Ajouter `ModelRotator` pour ESMM |
| `database/graph_delta.py` | **MODIFIER** | Intégrer canonicalisation avant insertion |
| `services/injector.py` | **MODIFIER** | Résoudre aliases dans `extract_context()` |

### Priorité 4 — Documentation

| Fichier | Action | Description |
|---------|--------|-------------|
| `docs/fr/ARCHITECTURE.md` | **METTRE À JOUR** | Nouvelle architecture ESMM |
| `docs/fr/DATABASE.md` | **CRÉER/MAJ** | Documentation schema_v2 |
| `docs/fr/ESMM_PROTOCOL.md` | **CRÉER** | Documentation du protocole ESMM |
| `docs/fr/CHANGELOG.md` | **METTRE À JOUR** | Ajouter entrée v2.0 |

---

## 📝 Spécifications Détaillées

### 1. Remplacement de `database/schema.sql`

```bash
# Simplement remplacer le fichier
cp schema_v2.sql database/schema.sql
```

**Important:** La base sera recréée à neuf. Aucune migration nécessaire.

---

### 2. Modifications de `database/engine.py`

#### 2.1 Nouvelles méthodes à ajouter à `ISpaceDB`

```python
# ============================================================================
# CANONICALISATION (Aliases)
# ============================================================================

async def resolve_concept(self, concept: str) -> str:
    """
    Résout un concept vers sa forme canonique.
    
    Args:
        concept: Concept brut (ex: "Intelligence Artificielle")
        
    Returns:
        Concept canonique (ex: "ia") ou le concept original si pas d'alias
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            "SELECT canonical_id FROM concept_aliases WHERE alias = ?",
            (concept.lower().strip(),)
        )
        row = await cursor.fetchone()
        return row[0] if row else concept.lower().strip()


async def add_alias(
    self,
    alias: str,
    canonical_id: str,
    similarity: float,
    method: str = "embedding"
) -> None:
    """
    Ajoute un alias pour un concept canonique.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            INSERT OR IGNORE INTO concept_aliases 
            (alias, canonical_id, similarity, fusion_method, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (alias.lower().strip(), canonical_id, similarity, method, time.time())
        )
        await conn.commit()


async def get_concept_with_aliases(self, concept_id: str) -> Dict[str, Any]:
    """
    Récupère un concept avec tous ses aliases.
    """
    async with self.connection() as conn:
        # Concept principal
        cursor = await conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        )
        concept = dict(await cursor.fetchone()) if cursor else None
        
        if not concept:
            return None
            
        # Aliases
        cursor = await conn.execute(
            "SELECT alias, similarity FROM concept_aliases WHERE canonical_id = ?",
            (concept_id,)
        )
        aliases = [{"alias": row[0], "similarity": row[1]} for row in await cursor.fetchall()]
        concept["aliases"] = aliases
        
        return concept


# ============================================================================
# CALCUL κ DIFFÉRÉ
# ============================================================================

async def queue_kappa_recalc(
    self,
    source: str,
    target: str,
    priority: int = 0
) -> None:
    """
    Ajoute une arête à la queue de recalcul κ Ollivier.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO pending_kappa_recalc 
            (source, target, priority, queued_at)
            VALUES (?, ?, ?, ?)
            """,
            (source, target, priority, time.time())
        )
        await conn.commit()


async def get_pending_kappa_batch(self, limit: int = 100) -> List[Dict]:
    """
    Récupère un batch d'arêtes en attente de recalcul κ.
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT source, target, priority, queued_at, attempts
            FROM pending_kappa_recalc
            ORDER BY priority DESC, queued_at ASC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]


async def mark_kappa_recalc_done(self, source: str, target: str) -> None:
    """
    Supprime une arête de la queue après recalcul réussi.
    """
    async with self.connection() as conn:
        await conn.execute(
            "DELETE FROM pending_kappa_recalc WHERE source = ? AND target = ?",
            (source, target)
        )
        await conn.commit()


async def mark_kappa_recalc_failed(
    self,
    source: str,
    target: str,
    error: str
) -> None:
    """
    Marque un échec de recalcul (incrémente attempts).
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE pending_kappa_recalc 
            SET attempts = attempts + 1, last_error = ?
            WHERE source = ? AND target = ?
            """,
            (error, source, target)
        )
        await conn.commit()


# ============================================================================
# RELATIONS CANONIQUES
# ============================================================================

async def get_canonical_relation(self, relation: str) -> Optional[str]:
    """
    Normalise un type de relation vers sa forme canonique.
    
    Args:
        relation: Relation brute (ex: "provoque", "engendre")
        
    Returns:
        Relation canonique (ex: "cause") ou None si non trouvée
    """
    relation_lower = relation.lower().strip()
    
    async with self.connection() as conn:
        # Chercher directement
        cursor = await conn.execute(
            "SELECT canonical FROM canonical_relations WHERE canonical = ?",
            (relation_lower,)
        )
        if await cursor.fetchone():
            return relation_lower
        
        # Chercher dans les aliases (JSON array)
        cursor = await conn.execute(
            "SELECT canonical, aliases FROM canonical_relations"
        )
        for row in await cursor.fetchall():
            aliases = json.loads(row[1])
            if relation_lower in [a.lower() for a in aliases]:
                return row[0]
        
        return None  # Relation inconnue


async def get_all_canonical_relations(self) -> List[Dict]:
    """
    Récupère toutes les relations canoniques avec leurs métadonnées.
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM canonical_relations"
        )
        return [dict(row) for row in await cursor.fetchall()]


# ============================================================================
# ESMM: RUNS
# ============================================================================

async def create_esmm_run(
    self,
    config: Dict,
    models: List[str],
    seed_type: str = "standard"
) -> int:
    """
    Crée un nouveau run ESMM.
    
    Returns:
        run_id
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO esmm_runs (config, models_used, seed_type, status, started_at)
            VALUES (?, ?, ?, 'initializing', ?)
            """,
            (json.dumps(config), json.dumps(models), seed_type, time.time())
        )
        await conn.commit()
        return cursor.lastrowid


async def update_esmm_run_status(
    self,
    run_id: int,
    status: str,
    current_cycle: str = None,
    current_iteration: int = None,
    error_message: str = None
) -> None:
    """
    Met à jour le statut d'un run ESMM.
    """
    async with self.connection() as conn:
        updates = ["status = ?"]
        params = [status]
        
        if current_cycle is not None:
            updates.append("current_cycle = ?")
            params.append(current_cycle)
        if current_iteration is not None:
            updates.append("current_iteration = ?")
            params.append(current_iteration)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if status == "completed":
            updates.append("completed_at = ?")
            params.append(time.time())
            
        params.append(run_id)
        
        await conn.execute(
            f"UPDATE esmm_runs SET {', '.join(updates)} WHERE run_id = ?",
            params
        )
        await conn.commit()


async def finalize_esmm_run(
    self,
    run_id: int,
    stats: Dict[str, Any]
) -> None:
    """
    Finalise un run ESMM avec les statistiques finales.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE esmm_runs SET
                status = 'completed',
                completed_at = ?,
                cycles_completed = ?,
                total_questions = ?,
                total_triplets = ?,
                triplets_injected = ?,
                concepts_created = ?,
                relations_created = ?,
                final_cochain_size = ?,
                coverage_score = ?,
                consensus_density = ?,
                epistemic_diversity = ?,
                structural_stability = ?
            WHERE run_id = ?
            """,
            (
                time.time(),
                stats.get("cycles_completed", 0),
                stats.get("total_questions", 0),
                stats.get("total_triplets", 0),
                stats.get("triplets_injected", 0),
                stats.get("concepts_created", 0),
                stats.get("relations_created", 0),
                stats.get("final_cochain_size"),
                stats.get("coverage_score"),
                stats.get("consensus_density"),
                stats.get("epistemic_diversity"),
                stats.get("structural_stability"),
                run_id
            )
        )
        await conn.commit()


# ============================================================================
# ESMM: CYCLES
# ============================================================================

async def log_exploration_cycle(
    self,
    run_id: int,
    cycle_type: str,
    iteration: int,
    question_template: str,
    question_rendered: str,
    responses: Dict[str, str],
    target_concepts: List[str] = None,
    response_latencies: Dict[str, float] = None
) -> int:
    """
    Enregistre un cycle d'exploration.
    
    Returns:
        cycle_id
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO exploration_cycles (
                run_id, cycle_type, iteration, question_template, question_rendered,
                target_concepts, responses, response_latencies, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, cycle_type, iteration, question_template, question_rendered,
                json.dumps(target_concepts) if target_concepts else None,
                json.dumps(responses),
                json.dumps(response_latencies) if response_latencies else None,
                time.time()
            )
        )
        await conn.commit()
        return cursor.lastrowid


async def update_cycle_extraction(
    self,
    cycle_id: int,
    triplets_extracted: int,
    triplets_data: List[Dict],
    consensus_map: Dict[str, float],
    exploration_metrics: Dict[str, float]
) -> None:
    """
    Met à jour un cycle avec les résultats d'extraction.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE exploration_cycles SET
                triplets_extracted = ?,
                triplets_data = ?,
                consensus_map = ?,
                exploration_metrics = ?,
                completed_at = ?
            WHERE cycle_id = ?
            """,
            (
                triplets_extracted,
                json.dumps(triplets_data),
                json.dumps(consensus_map),
                json.dumps(exploration_metrics),
                time.time(),
                cycle_id
            )
        )
        await conn.commit()


# ============================================================================
# ESMM: TRIPLETS
# ============================================================================

async def store_triplet_extraction(
    self,
    subject: str,
    relation: str,
    object_: str,
    confidence: float,
    extraction_method: str,
    model_source: str,
    cycle_id: int = None,
    event_id: int = None,
    source_text: str = None
) -> int:
    """
    Stocke un triplet extrait (avant injection dans le graphe).
    
    Returns:
        extraction_id
    """
    async with self.connection() as conn:
        # Canonicaliser
        subject_canonical = await self.resolve_concept(subject)
        object_canonical = await self.resolve_concept(object_)
        relation_canonical = await self.get_canonical_relation(relation) or relation.lower()
        
        cursor = await conn.execute(
            """
            INSERT INTO triplet_extractions (
                cycle_id, event_id, subject, subject_canonical,
                relation, relation_canonical, object, object_canonical,
                confidence, extraction_method, model_source, source_text,
                extracted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id, event_id, subject, subject_canonical,
                relation, relation_canonical, object_, object_canonical,
                confidence, extraction_method, model_source,
                source_text[:100] if source_text else None,
                time.time()
            )
        )
        await conn.commit()
        return cursor.lastrowid


async def mark_triplet_injected(
    self,
    extraction_id: int,
    delta_id: int
) -> None:
    """
    Marque un triplet comme injecté dans le graphe.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE triplet_extractions 
            SET injected_to_graph = 1, delta_id = ?
            WHERE extraction_id = ?
            """,
            (delta_id, extraction_id)
        )
        await conn.commit()


async def skip_triplet_injection(
    self,
    extraction_id: int,
    reason: str
) -> None:
    """
    Marque un triplet comme non-injecté avec raison.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE triplet_extractions 
            SET injection_skipped_reason = ?
            WHERE extraction_id = ?
            """,
            (reason, extraction_id)
        )
        await conn.commit()


# ============================================================================
# ESMM: COCHAIN (0-Cochaîne)
# ============================================================================

async def upsert_cochain_entry(
    self,
    concept_id: str,
    consensus_score: float,
    model_agreement: float,
    semantic_consistency: float,
    structural_centrality: float,
    stability_score: float,
    signature_vector: List[float],
    epistemic_type: str,
    contributing_models: Dict[str, float],
    triplet_count: int,
    run_id: int = None
) -> None:
    """
    Insère ou met à jour une entrée de la 0-cochaîne.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            INSERT INTO cochain_entries (
                concept_id, consensus_score, model_agreement, semantic_consistency,
                structural_centrality, stability_score, signature_vector,
                epistemic_type, contributing_models, triplet_count, run_id, computed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(concept_id) DO UPDATE SET
                consensus_score = excluded.consensus_score,
                model_agreement = excluded.model_agreement,
                semantic_consistency = excluded.semantic_consistency,
                structural_centrality = excluded.structural_centrality,
                stability_score = excluded.stability_score,
                signature_vector = excluded.signature_vector,
                epistemic_type = excluded.epistemic_type,
                contributing_models = excluded.contributing_models,
                triplet_count = excluded.triplet_count,
                run_id = excluded.run_id,
                computed_at = excluded.computed_at
            """,
            (
                concept_id, consensus_score, model_agreement, semantic_consistency,
                structural_centrality, stability_score, json.dumps(signature_vector),
                epistemic_type, json.dumps(contributing_models), triplet_count,
                run_id, time.time()
            )
        )
        await conn.commit()


async def get_cochain_entry(self, concept_id: str) -> Optional[Dict]:
    """
    Récupère une entrée de la cochaîne.
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM cochain_entries WHERE concept_id = ?",
            (concept_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        entry = dict(row)
        entry["signature_vector"] = json.loads(entry["signature_vector"])
        entry["contributing_models"] = json.loads(entry["contributing_models"])
        return entry


async def get_cochain_by_type(
    self,
    epistemic_type: str,
    min_consensus: float = 0.0,
    limit: int = 100
) -> List[Dict]:
    """
    Récupère les entrées de cochaîne par type épistémique.
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT * FROM cochain_entries 
            WHERE epistemic_type = ? AND consensus_score >= ?
            ORDER BY consensus_score DESC
            LIMIT ?
            """,
            (epistemic_type, min_consensus, limit)
        )
        entries = []
        for row in await cursor.fetchall():
            entry = dict(row)
            entry["signature_vector"] = json.loads(entry["signature_vector"])
            entry["contributing_models"] = json.loads(entry["contributing_models"])
            entries.append(entry)
        return entries


async def export_cochain_for_viz(self) -> List[Dict]:
    """
    Exporte la cochaîne pour visualisation externe.
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT concept_id, consensus_score, epistemic_type, signature_vector
            FROM cochain_entries
            ORDER BY consensus_score DESC
            """
        )
        points = []
        for row in await cursor.fetchall():
            sig = json.loads(row[3])
            points.append({
                "id": row[0],
                "consensus": row[1],
                "type": row[2],
                "x": sig[0] if len(sig) > 0 else 0,
                "y": sig[1] if len(sig) > 1 else 0,
                "z": sig[2] if len(sig) > 2 else 0
            })
        return points


# ============================================================================
# ESMM: KNOWLEDGE GAPS
# ============================================================================

async def add_knowledge_gap(
    self,
    gap_type: str,
    details: Dict,
    priority: float,
    run_id: int = None
) -> int:
    """
    Ajoute une lacune de connaissance identifiée.
    
    Returns:
        gap_id
    """
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO knowledge_gaps (run_id, gap_type, details, priority, detected_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, gap_type, json.dumps(details), priority, time.time())
        )
        await conn.commit()
        return cursor.lastrowid


async def get_active_gaps(
    self,
    gap_type: str = None,
    limit: int = 50
) -> List[Dict]:
    """
    Récupère les lacunes non-adressées.
    """
    async with self.connection() as conn:
        if gap_type:
            cursor = await conn.execute(
                """
                SELECT * FROM knowledge_gaps 
                WHERE addressed = 0 AND gap_type = ?
                ORDER BY priority DESC LIMIT ?
                """,
                (gap_type, limit)
            )
        else:
            cursor = await conn.execute(
                """
                SELECT * FROM knowledge_gaps 
                WHERE addressed = 0
                ORDER BY priority DESC LIMIT ?
                """,
                (limit,)
            )
        
        gaps = []
        for row in await cursor.fetchall():
            gap = dict(row)
            gap["details"] = json.loads(gap["details"])
            gaps.append(gap)
        return gaps


async def mark_gap_addressed(
    self,
    gap_id: int,
    cycle_id: int
) -> None:
    """
    Marque une lacune comme adressée.
    """
    async with self.connection() as conn:
        await conn.execute(
            """
            UPDATE knowledge_gaps 
            SET addressed = 1, addressed_at = ?, addressed_by_cycle_id = ?
            WHERE gap_id = ?
            """,
            (time.time(), cycle_id, gap_id)
        )
        await conn.commit()
```

---

### 3. Nouveau fichier: `services/entity_resolver.py`

```python
"""
LYRA-ACE - Entity Resolver (Canonicalisation Sémantique)
========================================================

Résout les variantes d'un même concept vers une forme canonique.
Utilise les embeddings pour détecter les quasi-doublons.

Seuils:
- SIMILARITY_THRESHOLD = 0.92 (fusion automatique)
- REVIEW_THRESHOLD = 0.85 (log pour review manuel)
"""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

from app.embeddings import get_embeddings
from database import get_db, ISpaceDB

logger = logging.getLogger(__name__)

# Seuils de similarité
SIMILARITY_THRESHOLD = 0.92  # Au-dessus: fusion automatique
REVIEW_THRESHOLD = 0.85      # Entre 0.85 et 0.92: log pour review


@dataclass
class ResolutionResult:
    """Résultat de la résolution d'entité."""
    original: str
    canonical: str
    is_new: bool
    similarity: Optional[float] = None
    method: str = "exact"  # "exact" | "alias" | "embedding" | "new"


class EntityResolver:
    """
    Résolveur d'entités par embeddings.
    
    Usage:
        resolver = EntityResolver(db)
        result = await resolver.resolve("Intelligence Artificielle")
        # result.canonical = "ia" (si alias existe)
    """
    
    def __init__(self, db: ISpaceDB):
        self.db = db
        self._embedding_cache: dict = {}
    
    async def resolve(
        self,
        concept: str,
        auto_create: bool = True
    ) -> ResolutionResult:
        """
        Résout un concept vers sa forme canonique.
        
        Args:
            concept: Concept à résoudre
            auto_create: Si True, crée le concept s'il n'existe pas
            
        Returns:
            ResolutionResult avec le concept canonique
        """
        normalized = self._normalize(concept)
        
        # 1. Vérifier si c'est déjà un concept canonique
        existing = await self.db.get_concept(normalized)
        if existing:
            return ResolutionResult(
                original=concept,
                canonical=normalized,
                is_new=False,
                method="exact"
            )
        
        # 2. Vérifier si c'est un alias connu
        canonical = await self.db.resolve_concept(normalized)
        if canonical != normalized:
            return ResolutionResult(
                original=concept,
                canonical=canonical,
                is_new=False,
                method="alias"
            )
        
        # 3. Chercher par similarité d'embedding
        match = await self._find_similar(normalized)
        if match:
            canonical_id, similarity = match
            
            # Créer l'alias
            await self.db.add_alias(
                alias=normalized,
                canonical_id=canonical_id,
                similarity=similarity,
                method="embedding"
            )
            
            logger.info(
                f"[EntityResolver] Merged '{concept}' -> '{canonical_id}' "
                f"(similarity={similarity:.3f})"
            )
            
            return ResolutionResult(
                original=concept,
                canonical=canonical_id,
                is_new=False,
                similarity=similarity,
                method="embedding"
            )
        
        # 4. Nouveau concept
        if auto_create:
            await self._create_concept(normalized)
            
        return ResolutionResult(
            original=concept,
            canonical=normalized,
            is_new=True,
            method="new"
        )
    
    async def _find_similar(
        self,
        concept: str,
        top_k: int = 5
    ) -> Optional[Tuple[str, float]]:
        """
        Cherche un concept similaire par embedding.
        
        Returns:
            (canonical_id, similarity) si trouvé, None sinon
        """
        # Obtenir l'embedding du nouveau concept
        new_embedding = await get_embeddings(concept)
        
        # Récupérer les candidats (top concepts par degré)
        # TODO: Optimiser avec un index vectoriel (FAISS) pour les gros graphes
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, embedding FROM concepts 
                WHERE embedding IS NOT NULL
                ORDER BY degree DESC
                LIMIT 500
                """
            )
            candidates = await cursor.fetchall()
        
        best_match = None
        best_similarity = 0.0
        
        for row in candidates:
            candidate_id = row[0]
            candidate_embedding = self._deserialize_embedding(row[1])
            
            if candidate_embedding is None:
                continue
            
            similarity = self._cosine_similarity(new_embedding, candidate_embedding)
            
            if similarity >= SIMILARITY_THRESHOLD and similarity > best_similarity:
                best_match = candidate_id
                best_similarity = similarity
            elif similarity >= REVIEW_THRESHOLD:
                logger.warning(
                    f"[EntityResolver] Review needed: '{concept}' ~ '{candidate_id}' "
                    f"(similarity={similarity:.3f})"
                )
        
        if best_match:
            return (best_match, best_similarity)
        return None
    
    async def _create_concept(self, concept: str) -> None:
        """
        Crée un nouveau concept avec son embedding.
        """
        import time
        
        embedding = await get_embeddings(concept)
        
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO concepts 
                (id, rho_static, degree, embedding, embedding_model, 
                 embedding_updated_at, source, created_at)
                VALUES (?, 0.0, 0, ?, 'mxbai-embed-large', ?, 'extracted', ?)
                """,
                (
                    concept,
                    self._serialize_embedding(embedding),
                    time.time(),
                    time.time()
                )
            )
            await conn.commit()
    
    def _normalize(self, concept: str) -> str:
        """Normalise un concept (lowercase, strip, espaces simples)."""
        return " ".join(concept.lower().strip().split())
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcule la similarité cosinus."""
        import math
        
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def _serialize_embedding(self, embedding: List[float]) -> bytes:
        """Sérialise un embedding pour stockage BLOB."""
        import json
        return json.dumps(embedding).encode('utf-8')
    
    def _deserialize_embedding(self, blob: bytes) -> Optional[List[float]]:
        """Désérialise un embedding depuis BLOB."""
        if not blob:
            return None
        import json
        try:
            return json.loads(blob.decode('utf-8'))
        except:
            return None


# Singleton
_resolver_instance: Optional[EntityResolver] = None


async def get_entity_resolver() -> EntityResolver:
    """Retourne l'instance singleton du resolver."""
    global _resolver_instance
    if _resolver_instance is None:
        db = await get_db()
        _resolver_instance = EntityResolver(db)
    return _resolver_instance
```

---

### 4. Nouveau fichier: `services/relation_normalizer.py`

```python
"""
LYRA-ACE - Relation Normalizer
==============================

Normalise les types de relations extraits vers des formes canoniques.
"""

from typing import Optional, Dict, List
from database import get_db, ISpaceDB


class RelationNormalizer:
    """
    Normalise les relations vers leur forme canonique.
    
    Usage:
        normalizer = RelationNormalizer(db)
        canonical = await normalizer.normalize("provoque")
        # canonical = "cause"
    """
    
    def __init__(self, db: ISpaceDB):
        self.db = db
        self._cache: Dict[str, str] = {}
        self._loaded = False
    
    async def _load_cache(self) -> None:
        """Charge toutes les relations canoniques en cache."""
        if self._loaded:
            return
            
        import json
        
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT canonical, aliases FROM canonical_relations"
            )
            for row in await cursor.fetchall():
                canonical = row[0]
                aliases = json.loads(row[1])
                
                # Mapper le canonical vers lui-même
                self._cache[canonical] = canonical
                
                # Mapper tous les aliases vers le canonical
                for alias in aliases:
                    self._cache[alias.lower()] = canonical
        
        self._loaded = True
    
    async def normalize(self, relation: str) -> str:
        """
        Normalise une relation vers sa forme canonique.
        
        Args:
            relation: Relation brute
            
        Returns:
            Relation canonique ou la relation originale si inconnue
        """
        await self._load_cache()
        
        normalized = relation.lower().strip().replace(" ", "_")
        return self._cache.get(normalized, normalized)
    
    async def get_inverse(self, relation: str) -> Optional[str]:
        """
        Retourne la relation inverse si elle existe.
        """
        canonical = await self.normalize(relation)
        
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT inverse FROM canonical_relations WHERE canonical = ?",
                (canonical,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def is_symmetric(self, relation: str) -> bool:
        """
        Vérifie si une relation est symétrique (A-R-B implique B-R-A).
        """
        canonical = await self.normalize(relation)
        
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT symmetric FROM canonical_relations WHERE canonical = ?",
                (canonical,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


# Singleton
_normalizer_instance: Optional[RelationNormalizer] = None


async def get_relation_normalizer() -> RelationNormalizer:
    """Retourne l'instance singleton du normalizer."""
    global _normalizer_instance
    if _normalizer_instance is None:
        db = await get_db()
        _normalizer_instance = RelationNormalizer(db)
    return _normalizer_instance
```

---

### 5. Nouveau fichier: `services/kappa_worker.py`

```python
"""
LYRA-ACE - Kappa Recalculation Worker
=====================================

Job de fond pour recalculer les courbures κ Ollivier.
Exécuté périodiquement (cron) ou à la demande.
"""

import asyncio
import logging
from typing import Optional

from database import get_db, ISpaceDB
from database.graph_delta import KappaCalculator

logger = logging.getLogger(__name__)


class KappaWorker:
    """
    Worker pour recalcul κ Ollivier différé.
    
    Usage:
        worker = KappaWorker()
        processed = await worker.process_batch(limit=100)
    """
    
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.calculator = KappaCalculator(alpha=alpha)
    
    async def process_batch(
        self,
        limit: int = 100,
        max_attempts: int = 3
    ) -> int:
        """
        Traite un batch d'arêtes en attente.
        
        Args:
            limit: Nombre max d'arêtes à traiter
            max_attempts: Abandonne après N tentatives
            
        Returns:
            Nombre d'arêtes traitées avec succès
        """
        db = await get_db()
        
        # Récupérer le batch
        pending = await db.get_pending_kappa_batch(limit)
        
        if not pending:
            return 0
        
        processed = 0
        
        for edge in pending:
            if edge["attempts"] >= max_attempts:
                logger.warning(
                    f"[KappaWorker] Abandoning {edge['source']} -> {edge['target']} "
                    f"after {edge['attempts']} attempts"
                )
                await db.mark_kappa_recalc_done(edge["source"], edge["target"])
                continue
            
            try:
                # Calculer κ complet
                kappa_data = await db.compute_kappa_live(
                    source=edge["source"],
                    target=edge["target"],
                    kappa_alpha=self.alpha,
                    store_history=True
                )
                
                if kappa_data:
                    # Mettre à jour la relation
                    async with db.connection() as conn:
                        await conn.execute(
                            """
                            UPDATE relations 
                            SET kappa = ?, kappa_method = 'ollivier'
                            WHERE source = ? AND target = ?
                            """,
                            (kappa_data["kappa_hybrid"], edge["source"], edge["target"])
                        )
                        await conn.commit()
                    
                    # Supprimer de la queue
                    await db.mark_kappa_recalc_done(edge["source"], edge["target"])
                    processed += 1
                    
            except Exception as e:
                logger.error(
                    f"[KappaWorker] Failed {edge['source']} -> {edge['target']}: {e}"
                )
                await db.mark_kappa_recalc_failed(
                    edge["source"], edge["target"], str(e)
                )
        
        logger.info(f"[KappaWorker] Processed {processed}/{len(pending)} edges")
        return processed
    
    async def run_continuous(
        self,
        interval_seconds: int = 60,
        batch_size: int = 50
    ) -> None:
        """
        Exécute le worker en continu.
        
        Args:
            interval_seconds: Pause entre les batches
            batch_size: Taille des batches
        """
        logger.info(f"[KappaWorker] Starting continuous mode (interval={interval_seconds}s)")
        
        while True:
            try:
                processed = await self.process_batch(limit=batch_size)
                
                if processed == 0:
                    # Rien à faire, attendre plus longtemps
                    await asyncio.sleep(interval_seconds * 2)
                else:
                    await asyncio.sleep(interval_seconds)
                    
            except Exception as e:
                logger.error(f"[KappaWorker] Error in continuous loop: {e}")
                await asyncio.sleep(interval_seconds)


async def run_kappa_worker_once(limit: int = 100) -> int:
    """
    Fonction utilitaire pour exécuter le worker une fois.
    
    Returns:
        Nombre d'arêtes traitées
    """
    worker = KappaWorker()
    return await worker.process_batch(limit=limit)
```

---

### 6. Modification de `graph_delta.py`

Ajouter l'intégration avec le resolver dans `apply_delta()`:

```python
# Dans la méthode apply_delta() de ISpaceDB (engine.py)
# AVANT l'insertion, résoudre les entités:

from services.entity_resolver import get_entity_resolver

async def apply_delta(self, delta: GraphDelta, ...) -> GraphDelta:
    # ... code existant ...
    
    # NOUVEAU: Canonicaliser les concepts
    resolver = await get_entity_resolver()
    
    source_result = await resolver.resolve(delta.source)
    delta.source = source_result.canonical
    
    if delta.target:
        target_result = await resolver.resolve(delta.target)
        delta.target = target_result.canonical
    
    # ... suite du code existant ...
```

---

## 📚 Documentation à Créer/Mettre à Jour

### `docs/fr/DATABASE.md`

```markdown
# Base de Données Lyra-ACE

## Schema v2

Le schéma v2 introduit le support complet du protocole ESMM.

### Tables Principales

| Table | Description |
|-------|-------------|
| `concepts` | Nœuds du graphe sémantique |
| `concept_aliases` | Aliases pour canonicalisation |
| `relations` | Arêtes avec poids et courbure |
| `canonical_relations` | Types de relations normalisés |

### Tables ESMM

| Table | Description |
|-------|-------------|
| `esmm_runs` | Exécutions du protocole |
| `exploration_cycles` | Historique des cycles |
| `triplet_extractions` | Triplets extraits |
| `cochain_entries` | 0-Cochaîne de consensus |
| `knowledge_gaps` | Lacunes identifiées |

### Canonicalisation

Le système résout automatiquement les variantes:
- "IA" → "ia"
- "Intelligence Artificielle" → "ia"
- "AI" → "ia"

Seuil de fusion par embedding: 0.92

### Calcul κ Différé

1. À l'insertion: κ Jaccard (instantané)
2. En arrière-plan: κ Ollivier (batch)

Table `pending_kappa_recalc` gère la queue.
```

### `docs/fr/ESMM_PROTOCOL.md`

```markdown
# Protocole ESMM (Exploration Sémantique Multi-Modèles)

## Vue d'Ensemble

ESMM enrichit le graphe sémantique via consensus multi-LLM.

## Modèles

| Modèle | Persona | Température |
|--------|---------|-------------|
| deepseek-r1 | Rigoureux | 0.6 |
| llama3.3 | Créatif | 1.0 |
| mistral | Pragmatique | 0.7 |
| gemma3 | Sceptique | 0.5 |

## Cycles

### Cycle A: Divergent
Questions de contraste et transposition.

### Cycle B: Débat
Avocat → Critique → Synthèse (3 rounds).

### Cycle C: Méta
Réflexion sur biais et relations inattendues.

## 0-Cochaîne

Score de consensus:
```
C(v) = α·model_agreement + β·semantic_consistency + γ·structural_centrality
```

Types épistémiques:
- **Généralist** (>0.7): Vérités stables
- **Specialized** (<0.3): Connaissances de niche
- **Hybrid**: Entre les deux
```

### `docs/fr/CHANGELOG.md`

Ajouter:

```markdown
## [2.0.0] - 2026-01-21

### Ajouté
- Schema v2 avec support ESMM complet
- Table `concept_aliases` pour canonicalisation sémantique
- Table `canonical_relations` avec 20 types de relations
- Tables ESMM: runs, cycles, triplets, cochain, gaps
- Service `EntityResolver` pour fusion par embeddings
- Service `RelationNormalizer` pour normalisation des relations
- Worker `KappaWorker` pour calcul différé
- Triggers automatiques pour mise à jour des degrés

### Modifié
- `engine.py`: 30+ nouvelles méthodes DB
- `graph_delta.py`: Intégration canonicalisation

### Performance
- Kappa Jaccard à l'insertion (O(1))
- Kappa Ollivier en batch différé
- Indexes optimisés pour patterns ESMM
```

---

## ✅ Checklist d'Implémentation

### Phase 1: Fondations DB
- [ ] Remplacer `database/schema.sql` par `schema_v2.sql`
- [ ] Supprimer `data/ispace.db` existant (ou renommer en backup)
- [ ] Ajouter méthodes aliases à `engine.py`
- [ ] Ajouter méthodes pending_kappa à `engine.py`
- [ ] Ajouter méthodes canonical_relations à `engine.py`
- [ ] Tester: `pytest tests/database/`

### Phase 2: Services
- [ ] Créer `services/entity_resolver.py`
- [ ] Créer `services/relation_normalizer.py`
- [ ] Créer `services/kappa_worker.py`
- [ ] Ajouter exports dans `services/__init__.py`
- [ ] Tester: `pytest tests/services/`

### Phase 3: Intégration
- [ ] Modifier `graph_delta.py` pour canonicalisation
- [ ] Modifier `injector.py` pour résolution aliases
- [ ] Tester intégration: `pytest tests/integration/`

### Phase 4: ESMM Core
- [ ] Ajouter méthodes ESMM runs à `engine.py`
- [ ] Ajouter méthodes ESMM cycles à `engine.py`
- [ ] Ajouter méthodes ESMM triplets à `engine.py`
- [ ] Ajouter méthodes ESMM cochain à `engine.py`
- [ ] Ajouter méthodes ESMM gaps à `engine.py`

### Phase 5: Documentation
- [ ] Créer/MAJ `docs/fr/DATABASE.md`
- [ ] Créer `docs/fr/ESMM_PROTOCOL.md`
- [ ] MAJ `docs/fr/ARCHITECTURE.md`
- [ ] MAJ `docs/fr/CHANGELOG.md`

---

## 🚀 Commande de Démarrage

```bash
# 1. Backup de l'ancienne DB (optionnel)
mv data/ispace.db data/ispace_v1_backup.db

# 2. Lancer le serveur (crée la nouvelle DB)
python -m uvicorn app.main:app --reload

# 3. Vérifier la création
sqlite3 data/ispace.db ".tables"
# Doit afficher les 18 tables du schema_v2
```

---

**Questions?** Contacter l'architecte pour clarifications.
