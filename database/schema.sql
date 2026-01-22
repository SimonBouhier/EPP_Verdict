-- ============================================================================
-- LYRA CLEAN - UNIFIED ISPACE DATABASE SCHEMA
-- ============================================================================
-- Purpose: Replace CSV-in-RAM with persistent, indexed SQLite storage
-- Performance: O(1) lookups via indexes, zero memory bloat
-- Author: Refactoring from Lyra_Uni_3 legacy
-- ============================================================================

-- ============================================================================
-- TABLE 1: CONCEPTS (replaces nodes.csv)
-- ============================================================================
-- Stores semantic concepts with pre-computed density metrics
CREATE TABLE IF NOT EXISTS concepts (
    -- Primary Key
    id TEXT PRIMARY KEY NOT NULL,           -- Concept identifier (e.g., "entropy", "milk")

    -- Semantic Metrics
    rho_static REAL NOT NULL DEFAULT 0.0,   -- Pre-computed density ∈ [0, 1]
                                             -- ρ = avg(PPMI_weights_incident) / max_global

    degree INTEGER NOT NULL DEFAULT 0,       -- Node degree (# connections)

    -- Optional: Future-ready for embeddings
    embedding BLOB,                          -- Vector representation (e.g., 768-dim float32)
    embedding_model TEXT,                    -- Model used (e.g., "sentence-transformers/all-MiniLM-L6-v2")

    -- Metadata
    created_at REAL NOT NULL,                -- Unix timestamp
    last_accessed REAL,                      -- For cache eviction strategies
    access_count INTEGER DEFAULT 0           -- Popularity metric
);

-- Indexes for O(1) lookups
CREATE INDEX IF NOT EXISTS idx_concepts_id ON concepts(id);
CREATE INDEX IF NOT EXISTS idx_concepts_rho ON concepts(rho_static DESC);
CREATE INDEX IF NOT EXISTS idx_concepts_degree ON concepts(degree DESC);

-- ============================================================================
-- TABLE 2: RELATIONS (replaces edges.csv)
-- ============================================================================
-- Stores weighted semantic relations between concepts
CREATE TABLE IF NOT EXISTS relations (
    -- Composite Primary Key
    source TEXT NOT NULL,                    -- Source concept
    target TEXT NOT NULL,                    -- Target concept

    -- Semantic Weights
    weight REAL NOT NULL DEFAULT 0.0,        -- PPMI weight (co-occurrence strength)
    kappa REAL NOT NULL DEFAULT 0.5,         -- Local curvature κ ∈ [0, 1]
                                             -- κ ≈ Jaccard(neighbors(source), neighbors(target))

    -- Metadata
    created_at REAL NOT NULL,                -- Unix timestamp

    PRIMARY KEY (source, target),
    FOREIGN KEY (source) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES concepts(id) ON DELETE CASCADE
);

-- Critical Indexes for neighbor queries (most frequent operation)
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source, weight DESC);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target, weight DESC);
CREATE INDEX IF NOT EXISTS idx_relations_weight ON relations(weight DESC);

-- ============================================================================
-- TABLE 3: SESSIONS (replaces memory_store RAM)
-- ============================================================================
-- Persistent conversation sessions (no more data loss on restart)
CREATE TABLE IF NOT EXISTS sessions (
    -- Primary Key
    session_id TEXT PRIMARY KEY NOT NULL,    -- UUID v4

    -- Session Metadata
    created_at REAL NOT NULL,                -- Session start time
    last_activity REAL NOT NULL,             -- Last message timestamp

    -- Configuration Snapshot
    profile TEXT DEFAULT 'balanced',         -- Bezier profile (e.g., "creative", "safe")
    params_snapshot TEXT,                    -- JSON snapshot of τc, ρ, κ at session start

    -- Analytics
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity DESC);

-- ============================================================================
-- TABLE 4: EVENTS (replaces memory_store.append())
-- ============================================================================
-- Immutable event log (append-only, zero mutation)
CREATE TABLE IF NOT EXISTS events (
    -- Primary Key
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign Key
    session_id TEXT NOT NULL,

    -- Event Type
    event_type TEXT NOT NULL,                -- 'user_message', 'assistant_message',
                                             -- 'system_event', 'param_update'

    -- Event Data
    role TEXT,                               -- 'user', 'assistant', 'system'
    content TEXT,                            -- Message text or JSON payload

    -- Context Injection Metadata
    injected_concepts TEXT,                  -- JSON array of concepts used
    graph_weight REAL DEFAULT 0.0,           -- Contextual weight from graph

    -- Timing
    timestamp REAL NOT NULL,                 -- Unix timestamp
    latency_ms REAL,                         -- Processing time

    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);

-- ============================================================================
-- TABLE 5: TRAJECTORIES (Bezier curves execution log)
-- ============================================================================
-- Stores physics engine state at each step (for analysis/replay)
CREATE TABLE IF NOT EXISTS trajectories (
    -- Primary Key
    trajectory_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign Key
    session_id TEXT NOT NULL,
    event_id INTEGER,                        -- Associated event (optional)

    -- Trajectory Point
    t_param REAL NOT NULL,                   -- Time parameter t ∈ [0, 1]

    -- Physics State (Bezier outputs)
    tau_c REAL NOT NULL,                     -- Tension τc(t)
    rho REAL NOT NULL,                       -- Focus ρ(t)
    delta_r REAL NOT NULL,                   -- Scheduling δr(t)
    kappa REAL,                              -- Optional: curvature κ(t)

    -- Metadata
    timestamp REAL NOT NULL,

    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_trajectories_session ON trajectories(session_id, t_param);

-- ============================================================================
-- TABLE 6: PROFILES (Bezier curve definitions)
-- ============================================================================
-- Pre-configured Bezier control points for different interaction modes
CREATE TABLE IF NOT EXISTS profiles (
    -- Primary Key
    profile_name TEXT PRIMARY KEY NOT NULL,  -- e.g., "creative", "safe", "analytical"

    -- Description
    description TEXT,

    -- Bezier Control Points (JSON format)
    -- Each curve: [P0, P1, P2, P3] where Pi = [t, value]
    tau_c_curve TEXT NOT NULL,               -- JSON: [[0,0.8], [0.3,1.2], [0.7,0.9], [1,1.0]]
    rho_curve TEXT NOT NULL,                 -- JSON: [[0,0.0], [0.2,0.5], [0.8,0.3], [1,0.0]]
    delta_r_curve TEXT NOT NULL,             -- JSON: [[0,0.0], [0.5,0.2], [0.8,-0.1], [1,0.0]]
    kappa_curve TEXT,                        -- Optional: [[0,0.5], [0.5,0.7], [1,0.5]]

    -- Metadata
    created_at REAL NOT NULL,
    is_default INTEGER DEFAULT 0             -- Boolean flag for default profile
);

-- Insert default profiles
INSERT OR IGNORE INTO profiles (profile_name, description, tau_c_curve, rho_curve, delta_r_curve, created_at, is_default) VALUES
('balanced', 'Balanced exploration-exploitation',
 '[[0, 1.0], [0.3, 1.1], [0.7, 0.95], [1, 1.0]]',
 '[[0, 0.0], [0.3, 0.4], [0.7, 0.2], [1, 0.0]]',
 '[[0, 0.0], [0.5, 0.1], [0.8, -0.05], [1, 0.0]]',
 strftime('%s', 'now'), 1),

('creative', 'High exploration, loose constraints',
 '[[0, 1.3], [0.2, 1.5], [0.6, 1.2], [1, 1.0]]',
 '[[0, 0.5], [0.3, 0.7], [0.7, 0.4], [1, 0.2]]',
 '[[0, 0.2], [0.4, 0.3], [0.8, 0.1], [1, 0.0]]',
 strftime('%s', 'now'), 0),

('safe', 'Conservative, structured responses',
 '[[0, 0.7], [0.3, 0.8], [0.7, 0.75], [1, 0.8]]',
 '[[0, -0.3], [0.3, -0.2], [0.7, -0.1], [1, 0.0]]',
 '[[0, -0.2], [0.5, -0.1], [0.8, 0.0], [1, 0.0]]',
 strftime('%s', 'now'), 0),

('analytical', 'High precision, low temperature',
 '[[0, 0.6], [0.2, 0.65], [0.8, 0.7], [1, 0.75]]',
 '[[0, -0.5], [0.3, -0.3], [0.7, -0.2], [1, 0.0]]',
 '[[0, -0.3], [0.5, -0.2], [0.8, -0.05], [1, 0.0]]',
 strftime('%s', 'now'), 0);

-- ============================================================================
-- TABLE 7: SESSION_ADJUSTMENTS (Phase 2 - Adaptive Consciousness)
-- ============================================================================
-- Stores adaptation rules output (adjustments suggestions + metrics at each turn)
CREATE TABLE IF NOT EXISTS session_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    adjustments TEXT NOT NULL,      -- JSON object with tau_c, rho, delta_r adjustments
    metrics TEXT NOT NULL,          -- JSON object with coherence, pressure, fit, tension, stability_score
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_adjustments_session 
ON session_adjustments(session_id, turn_number DESC);

-- ============================================================================
-- TABLE 8: SEMANTIC_MEMORY (Phase 3 - Semantic Memory)
-- ============================================================================
-- Stores semantic memory entries with 1024D embeddings for vector recall
CREATE TABLE IF NOT EXISTS semantic_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    embeddings BLOB NOT NULL,       -- JSON array of 1024 floats (mxbai-embed-large)
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_semantic_memory_session 
ON semantic_memory(session_id, turn_number DESC);

CREATE INDEX IF NOT EXISTS idx_semantic_memory_timestamp 
ON semantic_memory(session_id, timestamp DESC);

-- ============================================================================
-- VIEWS (Convenience queries)
-- ============================================================================

-- Top concepts by connectivity (replaces DataFrame sorts)
CREATE VIEW IF NOT EXISTS v_top_concepts AS
SELECT id, rho_static, degree, access_count
FROM concepts
ORDER BY degree DESC, rho_static DESC
LIMIT 1000;

-- Recent session activity
CREATE VIEW IF NOT EXISTS v_active_sessions AS
SELECT s.session_id, s.last_activity, s.message_count, s.profile,
       COUNT(e.event_id) as event_count
FROM sessions s
LEFT JOIN events e ON s.session_id = e.session_id
WHERE s.last_activity > strftime('%s', 'now') - 86400  -- Last 24h
GROUP BY s.session_id
ORDER BY s.last_activity DESC;

-- ============================================================================
-- PERFORMANCE NOTES
-- ============================================================================
-- Expected Query Patterns:
--
-- 1. Neighbor Lookup (most frequent):
--    SELECT target, weight, kappa FROM relations
--    WHERE source = :concept ORDER BY weight DESC LIMIT 20;
--    → O(log N) via idx_relations_source
--
-- 2. Session History:
--    SELECT role, content, timestamp FROM events
--    WHERE session_id = :sid ORDER BY timestamp ASC LIMIT 50;
--    → O(log N) via idx_events_session
--
-- 3. Concept Metadata:
--    SELECT rho_static, degree FROM concepts WHERE id = :concept;
--    → O(1) via primary key
--
-- ============================================================================
-- MIGRATION CHECKLIST
-- ============================================================================
-- [ ] Run migrate_data.py to populate concepts + relations from CSV
-- [ ] Verify index creation: SELECT * FROM sqlite_master WHERE type='index';
-- [ ] Benchmark neighbor query: EXPLAIN QUERY PLAN SELECT ...
-- [ ] Set PRAGMA journal_mode=WAL for concurrent reads
-- [ ] Set PRAGMA synchronous=NORMAL for performance
-- ============================================================================
