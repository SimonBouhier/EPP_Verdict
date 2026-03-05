"""
LYRA CLEAN - DATABASE ENGINE
============================

Async SQLite engine with connection pooling and performance optimizations.

Key Features:
- Zero CSV loading (all data in SQLite)
- O(1) concept lookups via indexes
- WAL mode for concurrent reads
- Context managers for safe transactions

Author: Refactored from Lyra_Uni_3 legacy
"""
from __future__ import annotations

import aiosqlite
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager

from database.graph_delta import (
    GraphDelta, DeltaBatch, DeltaOperation,
    KappaCalculator, DeltaValidationError, MutationLimitExceededError
)
from database.pool import SQLiteConnectionPool, get_pool, close_pool

logger = logging.getLogger(__name__)


class ISpaceDB:
    """
    Unified database engine for Lyra Clean.

    Replaces:
    - lyra_core/graph_loader.py (CSV loading)
    - lyra_core/memory_store.py (RAM cache)
    - ispacenav/graph_store.py (separate SQLite)

    Performance:
    - Indexed queries: O(log N)
    - Connection pooling via aiosqlite
    - WAL mode: concurrent reads + single writer
    """

    def __init__(self, db_path: str = "data/ispace.db"):
        """
        Initialize database engine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
        self._pool: Optional[SQLiteConnectionPool] = None

    async def initialize(self) -> None:
        """
        Initialize database with schema and performance optimizations.

        Must be called before any queries.
        """
        # Read schema from file
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Create database and apply schema
        async with aiosqlite.connect(self.db_path) as db:
            # Migrations AVANT le schema (pour colonnes manquantes sur DB existantes)
            # Doit s'executer avant executescript car le schema contient des CREATE INDEX
            # sur ces colonnes qui echoueraient sinon
            migrations = [
                "ALTER TABLE concepts ADD COLUMN domain TEXT DEFAULT 'general'",
                "ALTER TABLE concepts ADD COLUMN is_active INTEGER DEFAULT 1",
                "ALTER TABLE concept_aliases ADD COLUMN is_active INTEGER DEFAULT 1",
                "ALTER TABLE relations ADD COLUMN is_active INTEGER DEFAULT 1",
                "ALTER TABLE knowledge_gaps ADD COLUMN suggested_question TEXT",
                "ALTER TABLE attestations ADD COLUMN consensus_meta TEXT",
            ]

            # Phase 0.2: Migration embedding versioning
            # Copie les embeddings existants vers concept_embeddings (idempotent)
            phase02_migration = """
            INSERT OR IGNORE INTO concept_embeddings (concept_id, model_id, dimension, embedding, created_at)
            SELECT
                id,
                COALESCE(embedding_model, 'mxbai-embed-large'),
                CASE COALESCE(embedding_model, 'mxbai-embed-large')
                    WHEN 'mxbai-embed-large' THEN 1024
                    WHEN 'nomic-embed-text' THEN 768
                    ELSE length(embedding) / 4  -- float32 = 4 bytes
                END,
                embedding,
                COALESCE(embedding_updated_at, unixepoch('now'))
            FROM concepts
            WHERE embedding IS NOT NULL
            """
            # AUDIT[A2-005] 🟢 ACCEPTED: ALTER TABLE échoue si colonne existe déjà — migrations idempotentes.
            for migration in migrations:
                try:
                    await db.execute(migration)
                except Exception:
                    pass  # Table inexistante ou colonne deja presente
            await db.commit()

            # Maintenant appliquer le schema complet (tables + index)
            await db.executescript(schema_sql)

            # Phase 0.2: Copier embeddings existants vers concept_embeddings
            # S'exécute après le schema car la table concept_embeddings doit exister
            try:
                await db.execute(phase02_migration)
                await db.commit()
            except Exception as e:
                # Peut échouer si aucun embedding ou table vide - OK
                pass

            # Performance optimizations
            await db.execute("PRAGMA journal_mode=WAL")        # Write-Ahead Logging
            await db.execute("PRAGMA synchronous=NORMAL")      # Balance safety/speed
            await db.execute("PRAGMA cache_size=-64000")       # 64MB cache
            await db.execute("PRAGMA temp_store=MEMORY")       # Temp tables in RAM
            await db.execute("PRAGMA mmap_size=268435456")     # 256MB memory-mapped I/O
            await db.execute("PRAGMA busy_timeout=30000")      # 30s wait on lock contention

            await db.commit()

            # Seed metrological frames if table is empty
            try:
                cursor = await db.execute("SELECT COUNT(*) FROM metrological_frames")
                count = (await cursor.fetchone())[0]
                if count == 0:
                    from services.solana.metrological_frame import (
                        create_blockchain_tps_frame,
                        create_general_knowledge_frame,
                    )
                    for factory in [create_blockchain_tps_frame, create_general_knowledge_frame]:
                        frame = factory()
                        frame_dict = frame.model_dump()
                        await db.execute(
                            """
                            INSERT OR IGNORE INTO metrological_frames
                            (frame_id, version, domain, metric, description,
                             parameters, required_sources, governance, frame_hash, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                frame_dict["frame_id"],
                                frame_dict["version"],
                                frame_dict["domain"],
                                frame_dict["metric"],
                                frame_dict["description"],
                                json.dumps(frame_dict.get("parameters", {})),
                                frame_dict.get("required_sources", 1),
                                json.dumps(frame_dict.get("governance", {})),
                                frame.compute_frame_hash(),
                                "system_seed",
                            )
                        )
                    await db.commit()
            # AUDIT[A2-005] 🟡 FRAGILE: except:pass masque potentiellement des erreurs de seeding frames.
            except Exception:
                pass  # Table may not exist yet in older schemas

        # Initialize connection pool
        self._pool = await get_pool(str(self.db_path), pool_size=10)

        logger.info("Initialized at %s (pool: 10 connections)", self.db_path)

    @asynccontextmanager
    async def connection(self):
        """
        Context manager for database connections.

        Uses connection pool for better performance under load.
        Pool handles busy_timeout and connection reuse.

        Usage:
            async with db.connection() as conn:
                cursor = await conn.execute("SELECT ...")
        """
        if self._pool:
            async with self._pool.acquire() as conn:
                yield conn
        else:
            # Fallback for pre-initialization or tests
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA busy_timeout=30000")
                yield conn

    # ========================================================================
    # QUERY HELPERS
    # ========================================================================

    async def execute_scalar(self, sql: str, params: tuple = ()) -> Any:
        """
        Execute query and return single scalar value.

        Args:
            sql: SQL query (should return single value)
            params: Query parameters

        Returns:
            First column of first row, or None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
            return row[0] if row else None

    async def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute query and return all rows as dicts.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            List of row dicts
        """
        async with self.connection() as conn:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ========================================================================
    # CONCEPT QUERIES (replaces graph_loader.py)
    # ========================================================================

    async def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve concept metadata.

        Args:
            concept_id: Concept identifier (e.g., "entropy")

        Returns:
            Dict with keys: id, rho_static, degree, access_count
            None if concept not found

        Performance: O(1) via primary key index
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, rho_static, degree, access_count, last_accessed
                FROM concepts
                WHERE id = ?
                """,
                (concept_id,)
            )
            row = await cursor.fetchone()

            if row:
                # Update access tracking
                await conn.execute(
                    """
                    UPDATE concepts
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE id = ?
                    """,
                    (time.time(), concept_id)
                )
                await conn.commit()

                return dict(row)
            return None

    async def get_neighbors(
        self,
        concept_id: str,
        limit: int = 20,
        min_weight: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get semantic neighbors of a concept (most frequent operation).

        Args:
            concept_id: Source concept
            limit: Maximum neighbors to return
            min_weight: Minimum PPMI weight threshold

        Returns:
            List of dicts with keys: target, weight, kappa

        Performance: O(log N) via idx_relations_source

        Example:
            neighbors = await db.get_neighbors("entropy", limit=10)
            # [{"target": "information", "weight": 0.85, "kappa": 0.62}, ...]
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT target, weight, kappa
                FROM relations
                WHERE source = ? AND weight >= ?
                ORDER BY weight DESC
                LIMIT ?
                """,
                (concept_id, min_weight, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # AUDIT[A2-007] 🟡 FRAGILE: retourne [] sur exception — erreur d'embedding invisible.
    async def get_multi_neighbors(
        self,
        concept_ids: List[str],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get neighbors for multiple concepts (batch query).

        Args:
            concept_ids: List of concept identifiers
            limit: Total neighbors to return (top weighted)

        Returns:
            Aggregated list of neighbors, sorted by weight

        Performance: Single query vs N queries = ~10x faster
        """
        if not concept_ids:
            return []

        placeholders = ','.join('?' * len(concept_ids))

        async with self.connection() as conn:
            # AUDIT[A4-007] 🟡 FRAGILE: f-string SQL — valeurs internes uniquement, pas d'input user.
            cursor = await conn.execute(
                f"""
                SELECT target, weight, kappa, source
                FROM relations
                WHERE source IN ({placeholders})
                ORDER BY weight DESC
                LIMIT ?
                """,
                (*concept_ids, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def search_concepts(
        self,
        pattern: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search concepts by pattern (case-insensitive).

        Args:
            pattern: SQL LIKE pattern (e.g., "entr%")
            limit: Maximum results

        Returns:
            List of matching concepts with metadata
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, rho_static, degree, access_count
                FROM concepts
                WHERE id LIKE ?
                ORDER BY degree DESC, rho_static DESC
                LIMIT ?
                """,
                (pattern, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_concept(
        self,
        concept_id: str,
        rho_static: float = 0.0,
        embedding: bytes = None,
        embedding_model: str = None,
        source: str = "manual",
        first_seen_model: str = None
    ) -> None:
        """
        Ajoute un nouveau concept au graphe.

        Args:
            concept_id: Identifiant canonique
            rho_static: Densite pre-calculee
            embedding: Vecteur d'embedding (bytes)
            embedding_model: Modele d'embedding (OBLIGATOIRE si embedding fourni)
            source: Source du concept
            first_seen_model: Modele ayant introduit le concept

        Raises:
            ValueError: Si embedding fourni sans embedding_model
        """
        # Phase 0.2: embedding_model obligatoire si embedding fourni
        if embedding is not None and embedding_model is None:
            raise ValueError("embedding_model is required when embedding is provided")

        now = time.time()
        async with self.connection() as conn:
            # AUDIT[A4-002] 🔴→✅ FIXED Phase 4.1: INSERT OR IGNORE préserve les métadonnées existantes.
            await conn.execute(
                """
                INSERT OR IGNORE INTO concepts
                (id, rho_static, degree, embedding, embedding_model, embedding_updated_at, source, first_seen_model, created_at)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    concept_id, rho_static, embedding, embedding_model,
                    now if embedding else None,
                    source, first_seen_model, now
                )
            )

            # Phase 0.2: Also write to concept_embeddings for versioning
            if embedding is not None and embedding_model is not None:
                # Calculate dimension from blob size (float32 = 4 bytes)
                dimension = len(embedding) // 4
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO concept_embeddings
                    (concept_id, model_id, dimension, embedding, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (concept_id, embedding_model, dimension, embedding, now)
                )

            await conn.commit()

    async def get_concepts_with_embeddings(
        self,
        limit: int = 1000,
        model_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Recupere les concepts avec leurs embeddings pour recherche de similarite.

        Phase 0.2: Si model_id est specifie, retourne les embeddings de ce modele
        depuis concept_embeddings. Sinon, utilise concepts.embedding (legacy).

        Args:
            limit: Nombre maximum de concepts
            model_id: Modele d'embedding specifique (optionnel)

        Returns:
            Liste de dicts avec id et embedding
        """
        if model_id:
            return await self.get_concepts_with_embeddings_for_model(model_id, limit)

        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, embedding
                FROM concepts
                WHERE embedding IS NOT NULL
                ORDER BY degree DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_concepts_with_embeddings_for_model(
        self,
        model_id: str,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Recupere les concepts avec embeddings pour un modele specifique.

        Phase 0.2: Cherche dans concept_embeddings pour le model_id specifie.

        Args:
            model_id: Identifiant du modele d'embedding
            limit: Nombre maximum de concepts

        Returns:
            Liste de dicts avec id, embedding, model_id, dimension
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT ce.concept_id as id, ce.embedding, ce.model_id, ce.dimension
                FROM concept_embeddings ce
                JOIN concepts c ON ce.concept_id = c.id
                WHERE ce.model_id = ?
                ORDER BY c.degree DESC
                LIMIT ?
                """,
                (model_id, limit)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_relation(self, source: str, target: str) -> Optional[Dict]:
        """
        Recupere une relation specifique.

        Args:
            source: Concept source
            target: Concept cible

        Returns:
            Dict avec les donnees de la relation ou None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT source, target, weight, kappa, kappa_method, relation_type,
                       confidence, model_source, extraction_count
                FROM relations
                WHERE source = ? AND target = ?
                """,
                (source, target)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_edge_kappa(
        self,
        source: str,
        target: str,
        kappa: float,
        method: str = "hybrid"
    ) -> None:
        """
        Met a jour la courbure kappa d'une arete.

        Args:
            source: Concept source
            target: Concept cible
            kappa: Nouvelle valeur de kappa
            method: Methode de calcul ('jaccard', 'ollivier', 'hybrid')
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                UPDATE relations
                SET kappa = ?, kappa_method = ?, updated_at = ?
                WHERE source = ? AND target = ?
                """,
                (kappa, method, time.time(), source, target)
            )
            await conn.commit()

    async def log_kappa_history(
        self,
        source: str,
        target: str,
        kappa_ollivier: float,
        kappa_jaccard: float,
        kappa_hybrid: float,
        alpha: float = 0.5
    ) -> None:
        """
        Enregistre un calcul de kappa dans l'historique.
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO kappa_history
                (source, target, kappa_ollivier, kappa_jaccard, kappa_hybrid, alpha, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (source, target, kappa_ollivier, kappa_jaccard, kappa_hybrid, alpha, time.time())
            )
            await conn.commit()

    # AUDIT[A4-001] 🔴→✅ FIXED Phase 4.2: utilise ON CONFLICT DO UPDATE, relation_type préservé.
    async def upsert_relations_batch(
        self,
        relations: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Insere ou met a jour un lot de relations en une transaction.

        Optimise pour les insertions massives (ESMM extraction).
        Utilise INSERT ... ON CONFLICT DO UPDATE.

        Args:
            relations: Liste de dicts avec:
                - source: Concept source (required)
                - target: Concept cible (required)
                - weight: Poids PPMI (default: 0.5)
                - kappa: Courbure (default: 0.5)
                - relation_type: Type de relation (default: 'semantic')
                - confidence: Score de confiance (default: weight)
                - model_source: Modele ayant extrait (optional)

        Returns:
            Dict avec:
                - inserted: Nombre de nouvelles relations
                - updated: Nombre de relations mises a jour
                - errors: Nombre d'erreurs

        Example:
            result = await db.upsert_relations_batch([
                {"source": "A", "target": "B", "weight": 0.8},
                {"source": "C", "target": "D", "weight": 0.6, "relation_type": "causes"}
            ])
        """
        if not relations:
            return {"inserted": 0, "updated": 0, "errors": 0}

        inserted = 0
        updated = 0
        errors = 0
        now = time.time()

        async with self.connection() as conn:
            for rel in relations:
                try:
                    source = rel.get("source")
                    target = rel.get("target")
                    if not source or not target:
                        errors += 1
                        continue

                    weight = rel.get("weight", 0.5)
                    kappa = rel.get("kappa", 0.5)
                    relation_type = rel.get("relation_type", "semantic")
                    confidence = rel.get("confidence", weight)
                    model_source = rel.get("model_source")

                    # Verifier si existe deja
                    cursor = await conn.execute(
                        "SELECT 1 FROM relations WHERE source = ? AND target = ?",
                        (source, target)
                    )
                    exists = await cursor.fetchone()

                    await conn.execute(
                        """
                        INSERT INTO relations (
                            source, target, weight, kappa, relation_type,
                            confidence, model_source, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source, target) DO UPDATE SET
                            weight = (relations.weight + excluded.weight) / 2,
                            kappa = excluded.kappa,
                            confidence = (relations.confidence + excluded.confidence) / 2,
                            extraction_count = relations.extraction_count + 1,
                            updated_at = excluded.updated_at
                        """,
                        (source, target, weight, kappa, relation_type,
                         confidence, model_source, now, now)
                    )

                    if exists:
                        updated += 1
                    else:
                        inserted += 1

                except Exception:
                    # AUDIT[A2-009] 🟡 FRAGILE: erreur de batch silencieuse — seul le compteur errors est incrémenté.
                    errors += 1

            await conn.commit()

        return {"inserted": inserted, "updated": updated, "errors": errors}

    # ========================================================================
    # SESSION MANAGEMENT (replaces memory_store.py)
    # ========================================================================

    async def create_session(
        self,
        session_id: str,
        profile: str = "balanced",
        params_snapshot: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Create new conversation session.

        Args:
            session_id: UUID v4
            profile: Bezier profile name
            params_snapshot: Initial parameters (optional)
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, created_at, last_activity, profile, params_snapshot, message_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    time.time(),
                    time.time(),
                    profile,
                    json.dumps(params_snapshot) if params_snapshot else None
                )
            )
            await conn.commit()

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        role: Optional[str] = None,
        content: Optional[str] = None,
        injected_concepts: Optional[List[str]] = None,
        graph_weight: float = 0.0,
        latency_ms: Optional[float] = None
    ) -> int:
        """
        Append event to session (immutable log).

        Args:
            session_id: Session UUID
            event_type: 'user_message', 'assistant_message', 'system_event'
            role: 'user', 'assistant', 'system'
            content: Message text or JSON payload
            injected_concepts: Concepts used in context injection
            graph_weight: Contextual weight from graph
            latency_ms: Processing time

        Returns:
            event_id: Auto-incremented ID
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO events (
                    session_id, event_type, role, content,
                    injected_concepts, graph_weight, timestamp, latency_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event_type,
                    role,
                    content,
                    json.dumps(injected_concepts) if injected_concepts else None,
                    graph_weight,
                    time.time(),
                    latency_ms
                )
            )

            # Update session metadata
            await conn.execute(
                """
                UPDATE sessions
                SET last_activity = ?, message_count = message_count + 1
                WHERE session_id = ?
                """,
                (time.time(), session_id)
            )

            await conn.commit()
            return cursor.lastrowid

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve session event history.

        Args:
            session_id: Session UUID
            limit: Maximum events to return
            event_types: Filter by event types (e.g., ['user_message', 'assistant_message'])

        Returns:
            List of events, ordered by timestamp ASC

        Performance: O(log N) via idx_events_session
        """
        event_type_filter = ""
        params: Tuple = (session_id,)

        if event_types:
            placeholders = ','.join('?' * len(event_types))
            event_type_filter = f"AND event_type IN ({placeholders})"
            params = (session_id, *event_types)

        async with self.connection() as conn:
            cursor = await conn.execute(
                f"""
                SELECT event_id, event_type, role, content, timestamp,
                       injected_concepts, graph_weight, latency_ms
                FROM events
                WHERE session_id = ? {event_type_filter}
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (*params, limit)
            )
            rows = await cursor.fetchall()

            # Parse JSON fields
            events = []
            for row in rows:
                event = dict(row)
                if event['injected_concepts']:
                    event['injected_concepts'] = json.loads(event['injected_concepts'])
                events.append(event)

            return events

    async def get_conversation_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Get formatted conversation history (user/assistant messages only).

        Args:
            session_id: Session UUID
            limit: Maximum messages

        Returns:
            List of dicts with keys: role, content
            Format compatible with Ollama API
        """
        events = await self.get_session_history(
            session_id,
            limit=limit,
            event_types=['user_message', 'assistant_message']
        )

        return [
            {"role": e['role'], "content": e['content']}
            for e in events
            if e['role'] and e['content']
        ]

    async def cleanup_old_sessions(
        self,
        max_age_days: int = 30,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Nettoie les sessions inactives depuis plus de max_age_days.

        Args:
            max_age_days: Age maximum en jours (defaut: 30)
            dry_run: Si True, retourne uniquement le compte sans supprimer

        Returns:
            Dict avec:
            - sessions_deleted: Nombre de sessions supprimees
            - events_deleted: Nombre d'evenements supprimes
            - trajectories_deleted: Nombre de trajectoires supprimees
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        async with self.connection() as conn:
            # Compter les sessions a supprimer
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE last_activity < ?",
                (cutoff_time,)
            )
            sessions_count = (await cursor.fetchone())[0]

            if dry_run:
                # Mode simulation: compter sans supprimer
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM events e
                    JOIN sessions s ON e.session_id = s.session_id
                    WHERE s.last_activity < ?
                    """,
                    (cutoff_time,)
                )
                events_count = (await cursor.fetchone())[0]

                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM trajectories t
                    JOIN sessions s ON t.session_id = s.session_id
                    WHERE s.last_activity < ?
                    """,
                    (cutoff_time,)
                )
                trajectories_count = (await cursor.fetchone())[0]

                return {
                    "sessions_deleted": sessions_count,
                    "events_deleted": events_count,
                    "trajectories_deleted": trajectories_count,
                    "dry_run": True
                }

            # Supprimer (CASCADE supprime events et trajectories)
            await conn.execute(
                "DELETE FROM sessions WHERE last_activity < ?",
                (cutoff_time,)
            )
            await conn.commit()

            # Nettoyer les graph_deltas orphelins
            await conn.execute(
                """
                UPDATE graph_deltas SET session_id = NULL
                WHERE session_id NOT IN (SELECT session_id FROM sessions)
                """
            )
            await conn.commit()

            return {
                "sessions_deleted": sessions_count,
                "events_deleted": 0,  # CASCADE, pas compte exact
                "trajectories_deleted": 0,  # CASCADE
                "dry_run": False
            }

    async def get_inactive_sessions(
        self,
        min_age_days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Liste les sessions inactives.

        Args:
            min_age_days: Age minimum d'inactivite
            limit: Nombre maximum de resultats

        Returns:
            Liste de sessions avec leur derniere activite
        """
        cutoff_time = time.time() - (min_age_days * 24 * 60 * 60)

        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT session_id, profile, message_count, last_activity, created_at
                FROM sessions
                WHERE last_activity < ?
                ORDER BY last_activity ASC
                LIMIT ?
                """,
                (cutoff_time, limit)
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ========================================================================
    # TRAJECTORY LOGGING (Physics engine state)
    # ========================================================================

    async def log_trajectory_point(
        self,
        session_id: str,
        t_param: float,
        tau_c: float,
        rho: float,
        delta_r: float,
        kappa: Optional[float] = None,
        event_id: Optional[int] = None
    ) -> None:
        """
        Log Bezier trajectory point.

        Args:
            session_id: Session UUID
            t_param: Time parameter t ∈ [0, 1]
            tau_c, rho, delta_r: Physics parameters at t
            kappa: Optional curvature
            event_id: Associated event (optional)
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO trajectories (
                    session_id, event_id, t_param,
                    tau_c, rho, delta_r, kappa, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, event_id, t_param, tau_c, rho, delta_r, kappa, time.time())
            )
            await conn.commit()

    # ========================================================================
    # PROFILE MANAGEMENT (Bezier curves)
    # ========================================================================

    async def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Bezier profile configuration.

        Args:
            profile_name: Profile identifier (e.g., "creative", "safe")

        Returns:
            Dict with keys: profile_name, tau_c_curve, rho_curve, delta_r_curve
            Curves are parsed JSON lists
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT profile_name, description,
                       tau_c_curve, rho_curve, delta_r_curve, kappa_curve
                FROM profiles
                WHERE profile_name = ?
                """,
                (profile_name,)
            )
            row = await cursor.fetchone()

            if row:
                profile = dict(row)
                # Parse JSON curves
                for key in ['tau_c_curve', 'rho_curve', 'delta_r_curve', 'kappa_curve']:
                    if profile[key]:
                        profile[key] = json.loads(profile[key])
                return profile
            return None

    async def list_profiles(self) -> List[Dict[str, str]]:
        """
        List all available Bezier profiles.

        Returns:
            List of dicts with keys: profile_name, description
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT profile_name, description, is_default
                FROM profiles
                ORDER BY is_default DESC, profile_name ASC
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ========================================================================
    # CONSCIOUSNESS ADJUSTMENTS (Phase 2)
    # ========================================================================

    async def get_last_consciousness_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent consciousness metrics for a session.

        Args:
            session_id: Session UUID

        Returns:
            ConsciousnessMetrics dict or None if no metrics exist
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT metrics FROM session_adjustments
                WHERE session_id = ?
                ORDER BY turn_number DESC
                LIMIT 1
                """,
                (session_id,)
            )
            row = await cursor.fetchone()

            if row and row[0]:
                import json
                try:
                    metrics_dict = json.loads(row[0])
                    # Convert to ConsciousnessMetrics-like object
                    from services.consciousness.metrics import ConsciousnessMetrics
                    return ConsciousnessMetrics(
                        coherence=metrics_dict.get("coherence", 0.0),
                        tension=metrics_dict.get("tension", 0.0),
                        fit=metrics_dict.get("fit", 0.0),
                        pressure=metrics_dict.get("pressure", 0.0)
                    )
                except (json.JSONDecodeError, KeyError):
                    return None  # OK: JSON corrompu en DB, dégradation gracieuse

            return None

    async def store_consciousness_metrics(
        self,
        session_id: str,
        turn_number: int,
        metrics: Dict[str, Any],
        adjustments: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store consciousness metrics and adjustments for a session turn.

        Args:
            session_id: Session UUID
            turn_number: Turn/message number in the session
            metrics: ConsciousnessMetrics dict (coherence, tension, fit, pressure, stability_score)
            adjustments: Optional adjustment suggestions (tau_c_multiplier, rho_shift, etc.)
        """
        import json

        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO session_adjustments (session_id, turn_number, metrics, adjustments, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_number,
                    json.dumps(metrics),
                    json.dumps(adjustments) if adjustments else "{}",
                    time.time()
                )
            )
            await conn.commit()

    # ========================================================================
    # UTILITIES
    # ========================================================================

    # AUDIT[A2-006] 🟡 FRAGILE: retourne {} sur exception — indistinguable de "pas de données".
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with counts for all tables
        """
        async with self.connection() as conn:
            stats = {}

            tables = [
                'concepts', 'relations', 'sessions', 'events',
                'attestations', 'esmm_runs', 'cochain_entries',
                'triplet_extractions', 'knowledge_gaps',
            ]
            for table in tables:
                try:
                    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = await cursor.fetchone()
                    stats[table] = count[0]
                except Exception:
                    stats[table] = 0  # Table may not exist yet
            # AUDIT[A2-006] 🟡 FRAGILE: stats silencieusement à 0 si table n'existe pas.
            # Attestations anchored on-chain
            try:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM attestations WHERE solana_tx_signature IS NOT NULL"
                )
                stats['attestations_anchored'] = (await cursor.fetchone())[0]
            # AUDIT[§5.2] 🟡 FRAGILE: except silencieux sur stats anchored — 0 indiscernable de table absente.
            except Exception:
                stats['attestations_anchored'] = 0

            # Database file size
            stats['db_size_mb'] = round(
                self.db_path.stat().st_size / (1024 * 1024), 2
            ) if self.db_path.exists() else 0

            return stats

    async def vacuum(self) -> None:
        """
        Optimize database (reclaim space, rebuild indexes).

        Run periodically (e.g., weekly) for maintenance.
        """
        async with self.connection() as conn:
            await conn.execute("VACUUM")
            await conn.execute("ANALYZE")
            await conn.commit()

        logger.info("Database optimized (VACUUM + ANALYZE)")

    # ========================================================================
    # GRAPH DELTA OPERATIONS (Lyra-ACE)
    # ========================================================================

    async def apply_delta(
        self,
        delta: GraphDelta,
        session_id: Optional[str] = None,
        kappa_alpha: float = 0.5
    ) -> GraphDelta:
        """
        Applique un delta atomique au graphe.

        Args:
            delta: Delta à appliquer
            session_id: Session associée (pour audit)
            kappa_alpha: Coefficient α pour calcul κ hybride

        Returns:
            Delta enrichi avec old_values et new_kappa

        Raises:
            DeltaValidationError: Si le delta est invalide
            ValueError: Si l'opération échoue (ex: nœud inexistant)
        """
        if not delta.validate():
            raise DeltaValidationError(f"Invalid delta: {delta}")

        calculator = KappaCalculator(alpha=kappa_alpha)

        async with self.connection() as conn:
            try:
                # Récupérer les anciennes valeurs si modification
                if delta.operation in {DeltaOperation.UPDATE_EDGE, DeltaOperation.DELETE_EDGE}:
                    cursor = await conn.execute(
                        "SELECT weight, kappa FROM relations WHERE source = ? AND target = ?",
                        (delta.source, delta.target)
                    )
                    row = await cursor.fetchone()
                    if row:
                        delta.old_weight = row[0]
                        delta.old_kappa = row[1]
                    elif delta.operation == DeltaOperation.UPDATE_EDGE:
                        raise ValueError(f"Edge {delta.source} -> {delta.target} not found for update")

                # Appliquer l'opération
                if delta.operation == DeltaOperation.ADD_NODE:
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO concepts (id, rho_static, degree, created_at)
                        VALUES (?, 0.0, 0, ?)
                        """,
                        (delta.source, time.time())
                    )

                elif delta.operation == DeltaOperation.ADD_EDGE:
                    # Calculer κ pour la nouvelle arête
                    kappa_data = await self._compute_kappa_for_edge(
                        conn, delta.source, delta.target, delta.weight, calculator
                    )
                    delta.new_kappa = kappa_data["kappa_hybrid"]

                    await conn.execute(
                        """
                        -- AUDIT[A4-001] 🔴→✅ FIXED Phase 4.2: ON CONFLICT préserve relation_type et metadata.
                        INSERT INTO relations (source, target, weight, kappa, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(source, target) DO UPDATE SET
                            weight = excluded.weight,
                            kappa = excluded.kappa,
                            updated_at = excluded.created_at
                        """,
                        (delta.source, delta.target, delta.weight, delta.new_kappa, time.time())
                    )

                    # Mettre à jour les degrés
                    await self._update_degrees(conn, delta.source, delta.target, increment=True)

                elif delta.operation == DeltaOperation.UPDATE_EDGE:
                    kappa_data = await self._compute_kappa_for_edge(
                        conn, delta.source, delta.target, delta.weight, calculator
                    )
                    delta.new_kappa = kappa_data["kappa_hybrid"]

                    await conn.execute(
                        """
                        UPDATE relations SET weight = ?, kappa = ?
                        WHERE source = ? AND target = ?
                        """,
                        (delta.weight, delta.new_kappa, delta.source, delta.target)
                    )

                elif delta.operation == DeltaOperation.DELETE_EDGE:
                    await conn.execute(
                        "DELETE FROM relations WHERE source = ? AND target = ?",
                        (delta.source, delta.target)
                    )
                    await self._update_degrees(conn, delta.source, delta.target, increment=False)

                elif delta.operation == DeltaOperation.DELETE_NODE:
                    # Supprimer le nœud (CASCADE supprime les arêtes)
                    await conn.execute(
                        "DELETE FROM concepts WHERE id = ?",
                        (delta.source,)
                    )

                # Enregistrer le delta dans l'historique
                delta.applied_at = time.time()
                cursor = await conn.execute(
                    """
                    INSERT INTO graph_deltas (
                        session_id, operation, source, target,
                        old_weight, new_weight, old_kappa, new_kappa,
                        confidence, model_source, reason, timestamp, applied_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id, delta.operation.value, delta.source, delta.target,
                        delta.old_weight, delta.weight, delta.old_kappa, delta.new_kappa,
                        delta.confidence, delta.model_source, delta.reason,
                        delta.timestamp, delta.applied_at
                    )
                )
                delta.delta_id = cursor.lastrowid

                await conn.commit()
                return delta

            except Exception as e:
                await conn.rollback()
                raise

    async def apply_delta_batch(
        self,
        batch: DeltaBatch,
        kappa_alpha: float = 0.5
    ) -> List[GraphDelta]:
        """
        Applique un lot de deltas avec vérification de limite.

        Args:
            batch: Lot de deltas
            kappa_alpha: Coefficient α pour κ hybride

        Returns:
            Liste des deltas appliqués (enrichis)

        Raises:
            MutationLimitExceededError: Si le batch dépasse 5% du graphe
        """
        # Vérifier la taille du graphe
        stats = await self.get_stats()
        graph_size = stats["concepts"] + stats["relations"]

        if not batch.validate_batch_size(graph_size):
            max_allowed = int(graph_size * batch.max_mutation_ratio)
            raise MutationLimitExceededError(
                f"Batch size {len(batch.deltas)} exceeds limit {max_allowed} "
                f"({batch.max_mutation_ratio*100}% of {graph_size} elements)"
            )

        applied = []
        for delta in batch.deltas:
            result = await self.apply_delta(delta, batch.session_id, kappa_alpha)
            applied.append(result)

        return applied

    async def _compute_kappa_for_edge(
        self,
        conn,
        source: str,
        target: str,
        weight: float,
        calculator: KappaCalculator
    ) -> Dict[str, float]:
        """Calcule κ hybride pour une arête."""
        # Récupérer les degrés
        cursor = await conn.execute(
            "SELECT degree FROM concepts WHERE id = ?", (source,)
        )
        row = await cursor.fetchone()
        degree_u = row[0] if row else 0

        cursor = await conn.execute(
            "SELECT degree FROM concepts WHERE id = ?", (target,)
        )
        row = await cursor.fetchone()
        degree_v = row[0] if row else 0

        # Récupérer les voisins pour Jaccard
        cursor = await conn.execute(
            "SELECT target FROM relations WHERE source = ?", (source,)
        )
        neighbors_u = {row[0] for row in await cursor.fetchall()}

        cursor = await conn.execute(
            "SELECT target FROM relations WHERE source = ?", (target,)
        )
        neighbors_v = {row[0] for row in await cursor.fetchall()}

        return calculator.compute_hybrid(
            degree_u, degree_v, weight, neighbors_u, neighbors_v
        )

    async def _update_degrees(
        self,
        conn,
        source: str,
        target: str,
        increment: bool
    ):
        """Met à jour les degrés des nœuds après ajout/suppression d'arête."""
        delta = 1 if increment else -1
        await conn.execute(
            "UPDATE concepts SET degree = MAX(0, degree + ?) WHERE id = ?",
            (delta, source)
        )
        await conn.execute(
            "UPDATE concepts SET degree = MAX(0, degree + ?) WHERE id = ?",
            (delta, target)
        )

    async def compute_kappa_live(
        self,
        source: str,
        target: str,
        kappa_alpha: float = 0.5,
        store_history: bool = False
    ) -> Optional[Dict[str, float]]:
        """
        Calcule κ en temps réel pour une arête existante.

        Args:
            source: Concept source
            target: Concept cible
            kappa_alpha: Coefficient α hybride
            store_history: Si True, enregistre dans kappa_history

        Returns:
            Dict avec kappa_ollivier, kappa_jaccard, kappa_hybrid, alpha
            None si l'arête n'existe pas
        """
        calculator = KappaCalculator(alpha=kappa_alpha)

        async with self.connection() as conn:
            # Vérifier que l'arête existe
            cursor = await conn.execute(
                "SELECT weight FROM relations WHERE source = ? AND target = ?",
                (source, target)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            weight = row[0]
            kappa_data = await self._compute_kappa_for_edge(
                conn, source, target, weight, calculator
            )

            if store_history:
                await conn.execute(
                    """
                    INSERT INTO kappa_history
                    (source, target, kappa_ollivier, kappa_jaccard, kappa_hybrid, alpha, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source, target,
                        kappa_data["kappa_ollivier"],
                        kappa_data["kappa_jaccard"],
                        kappa_data["kappa_hybrid"],
                        kappa_data["alpha"],
                        time.time()
                    )
                )
                await conn.commit()

            return kappa_data

    async def get_delta_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 100,
        include_rolled_back: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des deltas.

        Args:
            session_id: Filtrer par session (None = tous)
            limit: Nombre max de résultats
            include_rolled_back: Inclure les deltas annulés

        Returns:
            Liste de deltas (plus récents en premier)
        """
        async with self.connection() as conn:
            where_clauses = []
            params = []

            if session_id:
                where_clauses.append("session_id = ?")
                params.append(session_id)

            if not include_rolled_back:
                where_clauses.append("rolled_back_at IS NULL")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor = await conn.execute(
                f"""
                SELECT delta_id, session_id, operation, source, target,
                       old_weight, new_weight, old_kappa, new_kappa,
                       confidence, model_source, reason, timestamp,
                       applied_at, rolled_back_at
                FROM graph_deltas
                {where_sql}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (*params, limit)
            )

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def rollback_deltas(
        self,
        session_id: str,
        to_timestamp: Optional[float] = None,
        delta_ids: Optional[List[int]] = None
    ) -> int:
        """
        Annule des deltas (restore état précédent).

        Args:
            session_id: Session dont annuler les deltas
            to_timestamp: Annuler tous les deltas après ce timestamp
            delta_ids: Ou liste explicite de delta_ids à annuler

        Returns:
            Nombre de deltas annulés

        Note:
            Les deltas sont annulés en ordre inverse (LIFO)
        """
        async with self.connection() as conn:
            # Récupérer les deltas à annuler
            if delta_ids:
                placeholders = ','.join('?' * len(delta_ids))
                cursor = await conn.execute(
                    f"""
                    SELECT delta_id, operation, source, target, old_weight, old_kappa
                    FROM graph_deltas
                    WHERE delta_id IN ({placeholders})
                      AND session_id = ?
                      AND rolled_back_at IS NULL
                    ORDER BY timestamp DESC
                    """,
                    (*delta_ids, session_id)
                )
            elif to_timestamp:
                cursor = await conn.execute(
                    """
                    SELECT delta_id, operation, source, target, old_weight, old_kappa
                    FROM graph_deltas
                    WHERE session_id = ?
                      AND applied_at >= ?
                      AND rolled_back_at IS NULL
                    ORDER BY applied_at DESC
                    """,
                    (session_id, to_timestamp)
                )
            else:
                # Fallback: rollback ALL unrolled deltas for this session (LIFO)
                cursor = await conn.execute(
                    """
                    SELECT delta_id, operation, source, target, old_weight, old_kappa
                    FROM graph_deltas
                    WHERE session_id = ?
                      AND rolled_back_at IS NULL
                    ORDER BY timestamp DESC
                    """,
                    (session_id,)
                )

            deltas_to_rollback = await cursor.fetchall()
            rollback_count = 0
            rollback_time = time.time()

            for row in deltas_to_rollback:
                delta_id, operation, source, target, old_weight, old_kappa = row

                # Inverser l'opération
                if operation == DeltaOperation.ADD_EDGE.value:
                    await conn.execute(
                        "DELETE FROM relations WHERE source = ? AND target = ?",
                        (source, target)
                    )
                    await self._update_degrees(conn, source, target, increment=False)

                elif operation == DeltaOperation.DELETE_EDGE.value and old_weight is not None:
                    await conn.execute(
                        """
                        -- AUDIT[A4-001] 🔴→✅ FIXED Phase 4.2: ON CONFLICT préserve metadata lors du rollback.
                        INSERT INTO relations (source, target, weight, kappa, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(source, target) DO UPDATE SET
                            weight = excluded.weight,
                            kappa = excluded.kappa,
                            updated_at = excluded.created_at
                        """,
                        (source, target, old_weight, old_kappa or 0.5, time.time())
                    )
                    await self._update_degrees(conn, source, target, increment=True)

                elif operation == DeltaOperation.UPDATE_EDGE.value and old_weight is not None:
                    await conn.execute(
                        "UPDATE relations SET weight = ?, kappa = ? WHERE source = ? AND target = ?",
                        (old_weight, old_kappa or 0.5, source, target)
                    )

                elif operation == DeltaOperation.ADD_NODE.value:
                    await conn.execute(
                        "DELETE FROM concepts WHERE id = ?",
                        (source,)
                    )

                # Marquer comme rolled back
                await conn.execute(
                    "UPDATE graph_deltas SET rolled_back_at = ? WHERE delta_id = ?",
                    (rollback_time, delta_id)
                )
                rollback_count += 1

            await conn.commit()
            return rollback_count

    async def get_graph_mutation_stats(self) -> Dict[str, Any]:
        """
        Statistiques sur les mutations du graphe.

        Returns:
            Dict avec counts par opération, taux de rollback, etc.
        """
        async with self.connection() as conn:
            stats = {}

            # Comptage par opération
            cursor = await conn.execute(
                """
                SELECT operation, COUNT(*) as count,
                       SUM(CASE WHEN rolled_back_at IS NOT NULL THEN 1 ELSE 0 END) as rolled_back
                FROM graph_deltas
                GROUP BY operation
                """
            )
            rows = await cursor.fetchall()
            stats["by_operation"] = {row[0]: {"total": row[1], "rolled_back": row[2]} for row in rows}

            # Comptage par modèle source
            cursor = await conn.execute(
                """
                SELECT model_source, COUNT(*) as count
                FROM graph_deltas
                WHERE rolled_back_at IS NULL
                GROUP BY model_source
                """
            )
            rows = await cursor.fetchall()
            stats["by_model"] = {row[0]: row[1] for row in rows}

            # Stats temporelles
            cursor = await conn.execute(
                """
                SELECT COUNT(*), AVG(confidence)
                FROM graph_deltas
                WHERE rolled_back_at IS NULL
                  AND timestamp > ?
                """,
                (time.time() - 86400,)  # Dernières 24h
            )
            row = await cursor.fetchone()
            stats["last_24h"] = {
                "count": row[0],
                "avg_confidence": round(row[1], 3) if row[1] else 0
            }

            return stats

    # ========================================================================
    # CANONICALISATION (Aliases)
    # ========================================================================

    async def resolve_concept(self, concept: str) -> str:
        """
        Resout un concept vers sa forme canonique.

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

    async def get_concept_with_aliases(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupere un concept avec tous ses aliases.
        """
        async with self.connection() as conn:
            # Concept principal
            cursor = await conn.execute(
                "SELECT * FROM concepts WHERE id = ?", (concept_id,)
            )
            row = await cursor.fetchone()
            concept = dict(row) if row else None

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

    # ========================================================================
    # CALCUL KAPPA DIFFERE
    # ========================================================================

    async def queue_kappa_recalc(
        self,
        source: str,
        target: str,
        priority: int = 0
    ) -> None:
        """
        Ajoute une arete a la queue de recalcul kappa Ollivier.
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
        Recupere un batch d'aretes en attente de recalcul kappa.
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
        Supprime une arete de la queue apres recalcul reussi.
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
        Marque un echec de recalcul (incremente attempts).
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

    # ========================================================================
    # RELATIONS CANONIQUES
    # ========================================================================

    async def get_canonical_relation(self, relation: str) -> Optional[str]:
        """
        Normalise un type de relation vers sa forme canonique.

        Args:
            relation: Relation brute (ex: "provoque", "engendre")

        Returns:
            Relation canonique (ex: "cause") ou None si non trouvee
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
        Recupere toutes les relations canoniques avec leurs metadonnees.
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM canonical_relations"
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ========================================================================
    # ESMM: RUNS
    # ========================================================================

    async def create_esmm_run(
        self,
        config: Dict,
        models: List[str],
        seed_type: str = "standard"
    ) -> int:
        """
        Cree un nouveau run ESMM.

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
        Met a jour le statut d'un run ESMM.
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

    # ========================================================================
    # ESMM: CYCLES
    # ========================================================================

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
        Met a jour un cycle avec les resultats d'extraction.
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

    # ========================================================================
    # ESMM: TRIPLETS
    # ========================================================================

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
        Marque un triplet comme injecte dans le graphe.
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
        Marque un triplet comme non-injecte avec raison.
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

    # ========================================================================
    # ESMM: COCHAIN (0-Cochaine)
    # ========================================================================

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
        Insere ou met a jour une entree de la 0-cochaine.
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
        Recupere une entree de la cochaine.
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
        Recupere les entrees de cochaine par type epistemique.
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
        Exporte la cochaine pour visualisation externe.
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

    # ========================================================================
    # ESMM: KNOWLEDGE GAPS
    # ========================================================================

    async def add_knowledge_gap(
        self,
        gap_type: str,
        details: Dict,
        priority: float,
        run_id: int = None
    ) -> int:
        """
        Ajoute une lacune de connaissance identifiee.

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
        Recupere les lacunes non-adressees.
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
        Marque une lacune comme adressee.
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

    # ========================================================================
    # EMBEDDING VERSIONING (Phase 0.2)
    # ========================================================================

    async def store_concept_embedding(
        self,
        concept_id: str,
        model_id: str,
        dimension: int,
        embedding: bytes
    ) -> None:
        """
        Stocke un embedding versionné dans concept_embeddings.

        Args:
            concept_id: Identifiant du concept
            model_id: Identifiant du modèle d'embedding
            dimension: Dimension du vecteur
            embedding: Vecteur float32 sérialisé

        Note:
            Utilise INSERT OR IGNORE pour idempotence (UNIQUE constraint)
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO concept_embeddings
                (concept_id, model_id, dimension, embedding, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (concept_id, model_id, dimension, embedding, time.time())
            )
            await conn.commit()

    async def get_concept_embedding(
        self,
        concept_id: str,
        model_id: str
    ) -> Optional[bytes]:
        """
        Récupère un embedding pour un concept et un modèle donné.

        Args:
            concept_id: Identifiant du concept
            model_id: Identifiant du modèle

        Returns:
            Embedding blob ou None si non trouvé
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT embedding FROM concept_embeddings
                WHERE concept_id = ? AND model_id = ?
                """,
                (concept_id, model_id)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_concepts_needing_migration(
        self,
        target_model: str,
        limit: int = 100
    ) -> List[str]:
        """
        Retourne les concept_ids qui ont un embedding mais pas pour target_model.

        Args:
            target_model: Modèle cible de la migration
            limit: Nombre maximum de concepts à retourner

        Returns:
            Liste de concept_ids à migrer
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT DISTINCT c.id
                FROM concepts c
                WHERE c.embedding IS NOT NULL
                  AND c.id NOT IN (
                      SELECT concept_id FROM concept_embeddings WHERE model_id = ?
                  )
                LIMIT ?
                """,
                (target_model, limit)
            )
            return [row[0] for row in await cursor.fetchall()]

    async def create_embedding_migration(
        self,
        from_model: str,
        to_model: str,
        dim_from: int,
        dim_to: int,
        triggered_by: str = "manual"
    ) -> int:
        """
        Crée une entrée de migration et retourne migration_id.

        Args:
            from_model: Modèle source
            to_model: Modèle cible
            dim_from: Dimension source
            dim_to: Dimension cible
            triggered_by: Source du déclenchement ('manual', 'config_change', 'cli')

        Returns:
            migration_id
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO embedding_migrations
                (from_model, to_model, dimension_from, dimension_to, status, started_at, triggered_by)
                VALUES (?, ?, ?, ?, 'running', ?, ?)
                """,
                (from_model, to_model, dim_from, dim_to, time.time(), triggered_by)
            )
            await conn.commit()
            return cursor.lastrowid

    async def update_embedding_migration(
        self,
        migration_id: int,
        **kwargs
    ) -> None:
        """
        Met à jour les champs d'une migration.

        Args:
            migration_id: ID de la migration
            **kwargs: Champs à mettre à jour (concepts_migrated, concepts_failed, status, error_log, etc.)
        """
        if not kwargs:
            return

        valid_fields = {
            'status', 'concepts_total', 'concepts_migrated', 'concepts_failed',
            'started_at', 'completed_at', 'error_log'
        }

        updates = []
        params = []
        for key, value in kwargs.items():
            if key in valid_fields:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return

        params.append(migration_id)

        async with self.connection() as conn:
            await conn.execute(
                f"UPDATE embedding_migrations SET {', '.join(updates)} WHERE migration_id = ?",
                params
            )
            await conn.commit()

    async def get_embedding_migration(self, migration_id: int) -> Optional[Dict]:
        """
        Récupère les détails d'une migration.

        Args:
            migration_id: ID de la migration

        Returns:
            Dict avec les détails ou None
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM embedding_migrations WHERE migration_id = ?",
                (migration_id,)
            )
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('error_log'):
                    result['error_log'] = json.loads(result['error_log'])
                return result
            return None

    async def finalize_embedding_migration(
        self,
        migration_id: int,
        target_model: str
    ) -> int:
        """
        Copie concept_embeddings → concepts.embedding pour le modèle cible.

        Args:
            migration_id: ID de la migration
            target_model: Modèle dont copier les embeddings

        Returns:
            Nombre de concepts mis à jour

        Raises:
            ValueError: Si la migration a des échecs (concepts_failed > 0)
        """
        # Check migration status
        migration = await self.get_embedding_migration(migration_id)
        if not migration:
            raise ValueError(f"Migration {migration_id} not found")

        if migration.get('concepts_failed', 0) > 0:
            raise ValueError(
                f"Cannot finalize migration {migration_id}: {migration['concepts_failed']} concepts failed"
            )

        async with self.connection() as conn:
            # Update concepts.embedding from concept_embeddings
            cursor = await conn.execute(
                """
                UPDATE concepts
                SET embedding = (
                    SELECT ce.embedding FROM concept_embeddings ce
                    WHERE ce.concept_id = concepts.id AND ce.model_id = ?
                ),
                embedding_model = ?,
                embedding_updated_at = ?
                WHERE id IN (
                    SELECT concept_id FROM concept_embeddings WHERE model_id = ?
                )
                """,
                (target_model, target_model, time.time(), target_model)
            )
            updated_count = cursor.rowcount

            # Mark migration as completed
            await conn.execute(
                """
                UPDATE embedding_migrations
                SET status = 'completed', completed_at = ?
                WHERE migration_id = ?
                """,
                (time.time(), migration_id)
            )

            await conn.commit()
            return updated_count

    async def rollback_embedding_migration(
        self,
        migration_id: int
    ) -> int:
        """
        Annule une migration en supprimant les embeddings du modèle cible.

        Args:
            migration_id: ID de la migration

        Returns:
            Nombre d'embeddings supprimés
        """
        migration = await self.get_embedding_migration(migration_id)
        if not migration:
            raise ValueError(f"Migration {migration_id} not found")

        target_model = migration['to_model']

        async with self.connection() as conn:
            # Delete embeddings for the target model
            cursor = await conn.execute(
                "DELETE FROM concept_embeddings WHERE model_id = ?",
                (target_model,)
            )
            deleted_count = cursor.rowcount

            # Mark migration as rolled back
            await conn.execute(
                """
                UPDATE embedding_migrations
                SET status = 'rolled_back', completed_at = ?
                WHERE migration_id = ?
                """,
                (time.time(), migration_id)
            )

            await conn.commit()
            return deleted_count

    async def count_concepts_with_embeddings(self) -> int:
        """
        Compte le nombre de concepts avec embeddings.

        Returns:
            Nombre de concepts avec embedding non-null
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM concepts WHERE embedding IS NOT NULL"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # ATTESTATIONS (Phase 0.3)
    # =========================================================================

    async def store_attestation(self, attestation: Dict[str, Any]) -> int:
        """
        Stocke une attestation cristallisée en DB.

        Args:
            attestation: Dict issu de EpistemicAttestation.model_dump()
                Doit contenir : claim_hash, subject, predicate, object,
                consensus_score, model_votes, signature_5d, etc.

        Returns:
            attestation_id
        """
        import json

        # Extract signature 5D components
        sig = attestation.get("signature_5d", {})

        # Serialize model_votes to JSON
        model_votes_json = json.dumps(attestation.get("model_votes", []))

        # Build portable JSON if not provided
        portable_json = attestation.get("portable_json")
        if portable_json is None:
            portable_json = json.dumps(
                attestation,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
                separators=(",", ":"),
            )

        # ADR-010: Serialize consensus_meta to JSON string
        consensus_meta_raw = attestation.get("consensus_meta")
        consensus_meta_json = (
            json.dumps(consensus_meta_raw, sort_keys=True, ensure_ascii=False)
            if consensus_meta_raw is not None
            else None
        )

        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO attestations (
                    claim_hash, subject, predicate, object,
                    consensus_score, models_consulted, models_agreeing, model_votes,
                    sig_agreement, sig_semantic_consistency, sig_centrality,
                    sig_stability, sig_relation_diversity,
                    epistemic_type, confidence_tier,
                    metrological_frame, source_anchor, run_id, question,
                    timestamp, protocol_version,
                    validation_count, previous_hash, portable_json,
                    consensus_meta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attestation["claim_hash"],
                    attestation["subject"],
                    attestation["predicate"],
                    attestation["object"],
                    attestation["consensus_score"],
                    attestation["models_consulted"],
                    attestation["models_agreeing"],
                    model_votes_json,
                    sig.get("agreement", 0.0),
                    sig.get("semantic_consistency", 0.0),
                    sig.get("centrality", 0.0),
                    sig.get("stability", 0.0),
                    sig.get("relation_diversity", 0.0),
                    attestation["epistemic_type"],
                    attestation["confidence_tier"],
                    attestation.get("metrological_frame"),
                    attestation.get("source_anchor"),
                    attestation.get("run_id"),
                    attestation.get("question"),
                    attestation["timestamp"],
                    attestation.get("protocol_version", "0.3"),
                    attestation.get("validation_count", 1),
                    attestation.get("previous_hash"),
                    portable_json,
                    consensus_meta_json,
                )
            )
            await conn.commit()
            return cursor.lastrowid

    async def update_attestation_diversity_bonus(
        self,
        claim_hash: str,
        diversity_bonus_factor: float,
        adjusted_consensus_score: float,
    ) -> None:
        """Update diversity bonus fields for an attestation (R-2.2.1).

        This is a post-hoc enrichment, NOT a modification of immutable
        epistemic content (ADR-007 safe). The consensus_score and
        confidence_tier remain unchanged.
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                UPDATE attestations
                SET diversity_bonus_factor = ?,
                    adjusted_consensus_score = ?
                WHERE claim_hash = ?
                """,
                (round(diversity_bonus_factor, 4), round(adjusted_consensus_score, 4), claim_hash),
            )
            await conn.commit()

    # ========================================================================
    # ADR-010: BACKFILL PRE-ADR-010 ATTESTATIONS
    # ========================================================================

    async def backfill_consensus_meta(self) -> int:
        """Backfill attestations that have no consensus_meta with a stub.

        Returns the number of attestations updated.
        """
        stub = json.dumps({
            "methodology": {
                "consensus_method": "hash_exact_v1",
                "note": "pre-ADR-010, metadata unavailable",
            }
        }, ensure_ascii=False)

        async with self.connection() as conn:
            cursor = await conn.execute(
                "UPDATE attestations SET consensus_meta = ? WHERE consensus_meta IS NULL",
                (stub,),
            )
            await conn.commit()
            return cursor.rowcount

    # ========================================================================
    # COMMIT-REVEAL (R-2.2.3)
    # ========================================================================

    async def store_commit(
        self,
        run_id: int,
        model_id: str,
        phase: str,
        response_hash: str,
    ) -> int:
        """Store a commit hash for a model response before reveal."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO commit_reveal (run_id, model_id, phase, response_hash)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, model_id, phase, response_hash),
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_commit(
        self,
        run_id: int,
        model_id: str,
        phase: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a commit record for a specific model/phase/run."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT commit_id, run_id, model_id, phase, response_hash,
                       committed_at, revealed_at, verified
                FROM commit_reveal
                WHERE run_id = ? AND model_id = ? AND phase = ?
                ORDER BY committed_at DESC LIMIT 1
                """,
                (run_id, model_id, phase),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "commit_id": row[0],
                "run_id": row[1],
                "model_id": row[2],
                "phase": row[3],
                "response_hash": row[4],
                "committed_at": row[5],
                "revealed_at": row[6],
                "verified": row[7],
            }

    async def verify_and_update_commit(
        self,
        run_id: int,
        model_id: str,
        phase: str,
        revealed_response: str,
    ) -> bool:
        """Verify a commit by comparing hash of revealed response.

        Returns True if hash matches, False otherwise. Updates the commit record.
        """
        import hashlib
        import time

        commit = await self.get_commit(run_id, model_id, phase)
        if commit is None:
            return False

        revealed_hash = hashlib.sha256(revealed_response.encode()).hexdigest()
        match = revealed_hash == commit["response_hash"]

        async with self.connection() as conn:
            await conn.execute(
                """
                UPDATE commit_reveal
                SET revealed_at = ?, verified = ?
                WHERE commit_id = ?
                """,
                (time.time(), 1 if match else 0, commit["commit_id"]),
            )
            await conn.commit()

        return match

    async def update_attestation_commit_verified(
        self,
        claim_hash: str,
        verified: bool,
    ) -> None:
        """Update commit_reveal_verified column in attestations (R-2.2.3)."""
        async with self.connection() as conn:
            await conn.execute(
                """
                UPDATE attestations
                SET commit_reveal_verified = ?
                WHERE claim_hash = ?
                """,
                (1 if verified else 0, claim_hash),
            )
            await conn.commit()

    async def get_attestation_by_hash(self, claim_hash: str) -> Optional[Dict]:
        """
        Récupère une attestation par son hash (la plus récente si plusieurs).

        Args:
            claim_hash: SHA-256 du triplet + frame

        Returns:
            Dict attestation ou None
        """
        import json

        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    attestation_id, claim_hash, subject, predicate, object,
                    consensus_score, models_consulted, models_agreeing, model_votes,
                    sig_agreement, sig_semantic_consistency, sig_centrality,
                    sig_stability, sig_relation_diversity,
                    epistemic_type, confidence_tier,
                    metrological_frame, source_anchor, run_id, question,
                    timestamp, protocol_version,
                    validation_count, previous_hash, portable_json,
                    adjusted_consensus_score, diversity_bonus_factor,
                    commit_reveal_verified
                FROM attestations
                WHERE claim_hash = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (claim_hash,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return self._row_to_attestation_dict(row)

    async def get_attestations_by_subject(
        self,
        subject: str,
        min_consensus: float = 0.0,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Récupère les attestations concernant un sujet.

        Args:
            subject: Sujet à chercher
            min_consensus: Score minimum
            limit: Nombre max de résultats

        Returns:
            Liste d'attestations triées par consensus DESC
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    attestation_id, claim_hash, subject, predicate, object,
                    consensus_score, models_consulted, models_agreeing, model_votes,
                    sig_agreement, sig_semantic_consistency, sig_centrality,
                    sig_stability, sig_relation_diversity,
                    epistemic_type, confidence_tier,
                    metrological_frame, source_anchor, run_id, question,
                    timestamp, protocol_version,
                    validation_count, previous_hash, portable_json
                FROM attestations
                WHERE subject = ? AND consensus_score >= ?
                ORDER BY consensus_score DESC
                LIMIT ?
                """,
                (subject, min_consensus, limit)
            )
            rows = await cursor.fetchall()
            return [self._row_to_attestation_dict(row) for row in rows]

    async def get_attestations_by_question(
        self,
        question: str,
        min_consensus: float = 0.0,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Récupère les attestations correspondant à une question exacte.
        ADR-013 : utilisé pour le cache-hit épistémique.

        Args:
            question: Texte exact de la question
            min_consensus: Score minimum de consensus
            limit: Nombre max de résultats

        Returns:
            Liste d'attestations triées par timestamp DESC (plus récentes en premier)
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    attestation_id, claim_hash, subject, predicate, object,
                    consensus_score, models_consulted, models_agreeing, model_votes,
                    sig_agreement, sig_semantic_consistency, sig_centrality,
                    sig_stability, sig_relation_diversity,
                    epistemic_type, confidence_tier,
                    metrological_frame, source_anchor, run_id, question,
                    timestamp, protocol_version,
                    validation_count, previous_hash, portable_json
                FROM attestations
                WHERE question = ? AND consensus_score >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (question, min_consensus, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_attestation_dict(row) for row in rows]

    async def get_attestation_history(self, claim_hash: str) -> List[Dict]:
        """
        Récupère l'historique de revalidation d'un claim.

        Toutes les attestations partageant le même claim_hash,
        triées par timestamp ASC (première → dernière validation).

        Args:
            claim_hash: Hash du claim

        Returns:
            Liste chronologique des attestations
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    attestation_id, claim_hash, subject, predicate, object,
                    consensus_score, models_consulted, models_agreeing, model_votes,
                    sig_agreement, sig_semantic_consistency, sig_centrality,
                    sig_stability, sig_relation_diversity,
                    epistemic_type, confidence_tier,
                    metrological_frame, source_anchor, run_id, question,
                    timestamp, protocol_version,
                    validation_count, previous_hash, portable_json
                FROM attestations
                WHERE claim_hash = ?
                ORDER BY timestamp ASC
                """,
                (claim_hash,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_attestation_dict(row) for row in rows]

    def _row_to_attestation_dict(self, row) -> Dict:
        """Convert a database row to an attestation dictionary."""
        import json

        model_votes = row[8]
        if isinstance(model_votes, str):
            model_votes = json.loads(model_votes)

        return {
            "attestation_id": row[0],
            "claim_hash": row[1],
            "subject": row[2],
            "predicate": row[3],
            "object": row[4],
            "consensus_score": row[5],
            "models_consulted": row[6],
            "models_agreeing": row[7],
            "model_votes": model_votes,
            "sig_agreement": row[9],
            "sig_semantic_consistency": row[10],
            "sig_centrality": row[11],
            "sig_stability": row[12],
            "sig_relation_diversity": row[13],
            "epistemic_type": row[14],
            "confidence_tier": row[15],
            "metrological_frame": row[16],
            "source_anchor": row[17],
            "run_id": row[18],
            "question": row[19],
            "timestamp": row[20],
            "protocol_version": row[21],
            "validation_count": row[22],
            "previous_hash": row[23],
            "portable_json": row[24],
            "adjusted_consensus_score": row[25] if len(row) > 25 else None,
            "diversity_bonus_factor": row[26] if len(row) > 26 else 1.0,
            "commit_reveal_verified": row[27] if len(row) > 27 else None,
        }

    # ========================================================================
    # METROLOGICAL FRAMES
    # ========================================================================

    async def store_frame(self, frame_data: Dict[str, Any]) -> None:
        """Stocke un MetrologicalFrame en DB."""
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO metrological_frames
                (frame_id, version, domain, metric, description,
                 parameters, required_sources, governance, frame_hash, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    frame_data["frame_id"],
                    frame_data["version"],
                    frame_data["domain"],
                    frame_data["metric"],
                    frame_data["description"],
                    json.dumps(frame_data.get("parameters", {})),
                    frame_data.get("required_sources", 1),
                    json.dumps(frame_data.get("governance", {})),
                    frame_data["frame_hash"],
                    frame_data.get("created_by", "system"),
                )
            )
            await conn.commit()

    async def get_frame(self, frame_id: str, version: Optional[str] = None) -> Optional[Dict]:
        """Récupère un frame par ID (dernière version si non spécifié)."""
        async with self.connection() as conn:
            if version:
                cursor = await conn.execute(
                    "SELECT * FROM metrological_frames WHERE frame_id = ? AND version = ?",
                    (frame_id, version)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM metrological_frames WHERE frame_id = ? ORDER BY created_at DESC LIMIT 1",
                    (frame_id,)
                )
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)

    async def list_frames(self) -> List[Dict]:
        """Liste tous les frames (dernière version de chaque)."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT DISTINCT frame_id, version, domain, metric, frame_hash, created_at
                FROM metrological_frames
                ORDER BY domain, frame_id
                """
            )
            return [dict(row) for row in await cursor.fetchall()]

    # ========================================================================
    # ADR-012 : Source Anchor Snapshots
    # ========================================================================

    async def store_source_anchor_snapshot(self, snap: Dict[str, Any]) -> None:
        """
        Stocke un snapshot source_anchor en SQLite.
        INSERT OR IGNORE — contrainte UNIQUE (source_id, query_hash, source_version).
        """
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO source_anchor_snapshots
                    (snapshot_id, source_id, source_version, query_hash,
                     raw_response, source_anchor, fetched_at, frame_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap["snapshot_id"],
                    snap["source_id"],
                    snap["source_version"],
                    snap["query_hash"],
                    snap["raw_response"],
                    snap["source_anchor"],
                    snap["fetched_at"],
                    snap["frame_id"],
                ),
            )
            await conn.commit()

    async def get_snapshot_by_anchor(self, source_anchor: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le snapshot correspondant à un source_anchor (None si absent).
        Utilisé pour vérifier l'intégrité off-chain avant ancrage on-chain.
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT snapshot_id, source_id, source_version, query_hash,
                       raw_response, source_anchor, fetched_at, frame_id
                FROM source_anchor_snapshots
                WHERE source_anchor = ?
                LIMIT 1
                """,
                (source_anchor,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def is_snapshot_fresh(
        self, source_id: str, query_hash: str, max_age_hours: int
    ) -> bool:
        """
        True si un snapshot récent (< max_age_hours) existe pour (source_id, query_hash).
        Utilisé pour décider si un re-fetch est nécessaire (TTL ADR-012).
        """
        import time as _time
        cutoff = _time.time() - max_age_hours * 3600
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 1
                FROM source_anchor_snapshots
                WHERE source_id = ? AND query_hash = ? AND fetched_at >= ?
                LIMIT 1
                """,
                (source_id, query_hash, cutoff),
            )
            row = await cursor.fetchone()
            return row is not None

    # ========================================================================
    # MODEL TRACK RECORD
    # ========================================================================

    async def record_model_prediction(
        self,
        model_id: str,
        provider_id: str,
        claim_hash: str,
        predicted_confidence: float,
        predicted_agreed: bool,
    ) -> int:
        """Enregistre une prédiction de modèle pour tracking Brier."""
        async with self.connection() as conn:
            # AUDIT[A4-010] 🟢 ACCEPTED: INSERT OR IGNORE — protège contre doublons en retry. Corrigé Phase 3.2.
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO model_track_record
                (model_id, provider_id, claim_hash, predicted_confidence, predicted_agreed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (model_id, provider_id, claim_hash, predicted_confidence, int(predicted_agreed))
            )
            await conn.commit()
            return cursor.lastrowid

    async def resolve_prediction(
        self,
        claim_hash: str,
        actual_outcome: bool,
        resolution_source: str = "manual",
    ) -> int:
        """
        Résout toutes les prédictions pour un claim donné.
        Calcule le Brier score pour chaque prédiction.

        Returns:
            Nombre de prédictions résolues
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT record_id, predicted_confidence, predicted_agreed
                FROM model_track_record
                WHERE claim_hash = ? AND actual_outcome IS NULL
                """,
                (claim_hash,)
            )
            rows = await cursor.fetchall()

            resolved = 0
            for row in rows:
                record_id = row[0]
                predicted = row[1]  # confidence [0, 1]
                agreed = row[2]     # 1 or 0

                # Brier score : (prediction - outcome)²
                effective_prediction = predicted if agreed else (1.0 - predicted)
                actual = 1.0 if actual_outcome else 0.0
                brier = (effective_prediction - actual) ** 2

                await conn.execute(
                    """
                    UPDATE model_track_record
                    SET actual_outcome = ?, resolved_at = ?, resolution_source = ?, brier_score = ?
                    WHERE record_id = ?
                    """,
                    (int(actual_outcome), time.time(), resolution_source, round(brier, 6), record_id)
                )
                resolved += 1

            await conn.commit()
            return resolved

    async def get_model_brier_score(
        self,
        model_id: str,
        window_days: int = 90,
    ) -> Optional[Dict[str, Any]]:
        """Calcule le Brier score d'un modèle sur une fenêtre glissante."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    AVG(brier_score) as avg_brier,
                    MIN(brier_score) as best,
                    MAX(brier_score) as worst
                FROM model_track_record
                WHERE model_id = ?
                  AND actual_outcome IS NOT NULL
                  AND created_at > unixepoch('now') - (? * 86400)
                """,
                (model_id, window_days)
            )
            row = await cursor.fetchone()
            if not row or row[0] == 0:
                return None
            return {
                "model_id": model_id,
                "total_resolved": row[0],
                "avg_brier_score": round(row[1], 4),
                "best_brier": round(row[2], 4),
                "worst_brier": round(row[3], 4),
            }

    async def get_all_model_brier_scores(
        self,
        window_days: int = 90,
    ) -> List[Dict[str, Any]]:
        """Return Brier stats + computed weight for all models with resolved predictions.

        Uses the v_model_brier_scores view (schema.sql).
        Weight formula: max(0.0, 1.0 - avg_brier_score). Cold start models
        (no resolved predictions) do not appear — they get weight 1.0 by default
        in the orchestrator.

        Returns:
            List of dicts sorted by avg_brier_score ascending, each containing:
            model_id, provider_id, total_predictions, resolved_predictions,
            avg_brier_score, best_brier, worst_brier, weight.
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM v_model_brier_scores"
            )
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                avg_brier = round(row[4], 4) if row[4] is not None else 0.0
                results.append({
                    "model_id": row[0],
                    "provider_id": row[1],
                    "total_predictions": row[2],
                    "resolved_predictions": row[3],
                    "avg_brier_score": avg_brier,
                    "best_brier": round(row[5], 4) if row[5] is not None else None,
                    "worst_brier": round(row[6], 4) if row[6] is not None else None,
                    "weight": round(max(0.0, 1.0 - avg_brier), 4),
                })
            return results

    # ========================================================================
    # TIER TRANSITIONS
    # ========================================================================

    async def log_tier_transition(
        self,
        claim_hash: str,
        old_tier: str,
        new_tier: str,
        reason: str,
        attestation_id: Optional[int] = None,
        run_id: Optional[int] = None,
    ) -> int:
        """Logue un changement de niveau de confiance."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO tier_transitions
                (claim_hash, old_tier, new_tier, reason, attestation_id, run_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (claim_hash, old_tier, new_tier, reason, attestation_id, run_id)
            )
            await conn.commit()
            return cursor.lastrowid

    # ========================================================================
    # ATTESTATION QUERIES & STATUS
    # ========================================================================

    async def get_latest_attestation(self) -> Optional[Dict]:
        """Retourne la dernière attestation stockée (par timestamp)."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM attestations
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            col_names = [d[0] for d in cursor.description]
            result = dict(zip(col_names, row))
            # Deserialize JSON fields
            for json_field in ("model_votes", "signature_5d"):
                if json_field in result and isinstance(result[json_field], str):
                    try:
                        result[json_field] = json.loads(result[json_field])
                    # AUDIT[§5.2] 🟡→✅ FIXED Phase 4.3: loggé au lieu d'avalé.
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.debug(f"JSON field '{json_field}' not deserializable: {e}")
            return result

    async def get_attestation_count(self) -> int:
        """Retourne le nombre total d'attestations."""
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM attestations")
            row = await cursor.fetchone()
            return row[0] if row else 0

    # AUDIT[A4-003] 🔴→✅ FIXED Phase 3.2: submission_status ajouté au schéma.
    async def update_attestation_submission_status(
        self,
        claim_hash: str,
        status: str,
    ) -> bool:
        """
        Met à jour le statut de soumission d'une attestation.

        Args:
            claim_hash: Hash du claim
            status: Nouveau statut (local | queued | submitted)

        Returns:
            True si mise à jour, False si claim_hash non trouvé
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE attestations
                SET submission_status = ?
                WHERE claim_hash = ?
                """,
                (status, claim_hash)
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ========================================================================
    # SOLANA TX UPDATE
    # ========================================================================

    # AUDIT[A4-004] 🟡 FRAGILE: UPDATE sur table append-only (contradicts design doc).
    async def update_attestation_solana_tx(
        self,
        claim_hash: str,
        tx_signature: str,
        slot: Optional[int] = None,
    ) -> bool:
        """
        Met à jour une attestation après ancrage on-chain.

        Args:
            claim_hash: Hash du claim ancré
            tx_signature: Signature de la transaction Solana
            slot: Slot Solana (optionnel)

        Returns:
            True si mise à jour, False si claim_hash non trouvé
        """
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE attestations
                SET solana_tx_signature = ?,
                    solana_slot = ?,
                    anchored_at = ?
                WHERE claim_hash = ?
                  AND solana_tx_signature IS NULL
                """,
                (tx_signature, slot, time.time(), claim_hash)
            )
            await conn.commit()
            return cursor.rowcount > 0


# ============================================================================
# SINGLETON INSTANCE (Dependency Injection ready)
# ============================================================================

_db_instance: Optional[ISpaceDB] = None


# AUDIT[A1-001] 🔴→✅ FIXED Phase 4.3: warning si db_path change entre appels.
async def get_db(db_path: Optional[str] = None) -> ISpaceDB:
    """
    Get or create database instance (singleton pattern).

    Uses config_loader to resolve the DB path if not provided.
    Fallback: "data/epp.db".

    Usage:
        db = await get_db()
        concepts = await db.get_neighbors("entropy")
    """
    global _db_instance

    if _db_instance is None:
        if db_path is None:
            try:
                from services.config_loader import get_value
                db_path = get_value("database", "path", "data/epp.db")
            except Exception:
                db_path = "data/epp.db"  # OK: fallback vers chemin par défaut si config indisponible
        _db_instance = ISpaceDB(db_path)
        await _db_instance.initialize()
    elif db_path is not None and str(_db_instance.db_path) != str(db_path):
        import logging
        logging.getLogger("database.engine").warning(
            f"get_db() called with db_path='{db_path}' but instance already exists for '{_db_instance.db_path}'. Returning existing."
        )

    return _db_instance


async def close_db() -> None:
    """
    Close database connection and pool (cleanup).

    Call on application shutdown.
    """
    global _db_instance

    # Close the connection pool
    await close_pool()

    _db_instance = None
    logger.info("Connection and pool closed")
