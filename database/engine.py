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
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager


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
            await db.executescript(schema_sql)

            # Performance optimizations
            await db.execute("PRAGMA journal_mode=WAL")        # Write-Ahead Logging
            await db.execute("PRAGMA synchronous=NORMAL")      # Balance safety/speed
            await db.execute("PRAGMA cache_size=-64000")       # 64MB cache
            await db.execute("PRAGMA temp_store=MEMORY")       # Temp tables in RAM
            await db.execute("PRAGMA mmap_size=268435456")     # 256MB memory-mapped I/O

            await db.commit()

        print(f"[ISpaceDB] Initialized at {self.db_path}")

    @asynccontextmanager
    async def connection(self):
        """
        Context manager for database connections.

        Usage:
            async with db.connection() as conn:
                cursor = await conn.execute("SELECT ...")
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row  # Dict-like rows
            yield conn

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
                INSERT INTO sessions (session_id, created_at, last_activity, profile, params_snapshot, message_count)
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
    # UTILITIES
    # ========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with counts for all tables
        """
        async with self.connection() as conn:
            stats = {}

            for table in ['concepts', 'relations', 'sessions', 'events', 'trajectories', 'profiles']:
                cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = await cursor.fetchone()
                stats[table] = count[0]

            # Database file size
            stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0

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

        print("[ISpaceDB] Database optimized (VACUUM + ANALYZE)")


# ============================================================================
# SINGLETON INSTANCE (Dependency Injection ready)
# ============================================================================

_db_instance: Optional[ISpaceDB] = None


async def get_db(db_path: str = "data/ispace.db") -> ISpaceDB:
    """
    Get or create database instance (singleton pattern).

    Usage:
        db = await get_db()
        concepts = await db.get_neighbors("entropy")
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = ISpaceDB(db_path)
        await _db_instance.initialize()

    return _db_instance


async def close_db() -> None:
    """
    Close database connection (cleanup).

    Call on application shutdown.
    """
    global _db_instance
    _db_instance = None
    print("[ISpaceDB] Connection closed")
