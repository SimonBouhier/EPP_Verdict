"""
LYRA CLEAN - API MODELS
=======================

Pydantic models for request/response validation.

All models are immutable (frozen=True equivalent via Config).
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """
    User chat message request.

    Example:
        {
            "text": "What is entropy?",
            "session_id": "abc-123",
            "profile": "creative",
            "enable_context": true,
            "consciousness_level": 1,
            "model": "mistral:7b",
            "use_esmm": true
        }
    """
    text: str = Field(..., min_length=1, max_length=50000, description="User message")
    session_id: Optional[str] = Field(None, description="Session UUID (auto-created if None)")
    profile: str = Field("balanced", description="Bezier profile name")
    enable_context: bool = Field(True, description="Enable semantic context injection")
    max_history: int = Field(50, ge=0, le=500, description="Max conversation history messages")
    consciousness_level: int = Field(0, ge=0, le=3, description="Consciousness level: 0=off, 1=passive, 2=adaptive, 3=full")
    model: Optional[str] = Field(None, description="Override LLM model (None = use server default)")
    use_esmm: bool = Field(False, description="Enable ESMM triplet context injection")

    model_config = ConfigDict(frozen=False)  # Allow mutation for backward compat

    @field_validator('consciousness_level')
    @classmethod
    def validate_consciousness_level(cls, v):
        if v not in [0, 1, 2, 3]:
            raise ValueError("consciousness_level must be 0, 1, 2, or 3")
        return v


class ChatResponse(BaseModel):
    """
    LLM response with metadata.

    Example:
        {
            "text": "Entropy is a measure...",
            "session_id": "abc-123",
            "physics_state": {...},
            "context": {...},
            "latency": {...},
            "consciousness": {...}
        }
    """
    text: str = Field(..., description="LLM generated response")
    session_id: str = Field(..., description="Session UUID")
    model: Optional[str] = Field(None, description="LLM model name used for generation")

    # Physics state at generation time
    physics_state: Dict[str, float] = Field(..., description="τc, ρ, δr, κ at time t")

    # Context metadata
    context: Optional[Dict[str, Any]] = Field(None, description="Semantic context metadata")

    # Performance metrics
    latency: Dict[str, float] = Field(
        ...,
        description="Latency breakdown (ms): context_extraction, llm_generation, total"
    )

    # Token estimates
    tokens: Dict[str, int] = Field(
        default_factory=dict,
        description="Token counts: prompt, completion, total (approximate)"
    )

    # Consciousness metrics (Phase 1+)
    consciousness: Optional[Dict[str, float]] = Field(
        None,
        description="Epistemological metrics if consciousness_level >= 1: coherence, tension, fit, pressure, stability_score"
    )

    # Semantic memory echo (Phase 3)
    memory_echo: Optional[str] = Field(
        None,
        description="Formatted memory recall from semantic memory if consciousness_level >= 3"
    )

    # ESMM context info (when use_esmm=True)
    esmm_context: Optional[Dict[str, Any]] = Field(
        None,
        description="ESMM triplet context info: enabled, triplets_used, avg_consensus"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# SESSION MODELS
# ============================================================================

class SessionCreateRequest(BaseModel):
    """
    Create new session request.

    Example:
        {
            "profile": "creative",
            "metadata": {"user_id": "user-123"}
        }
    """
    profile: str = Field("balanced", description="Initial Bezier profile")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    model_config = ConfigDict(frozen=False)


class SessionResponse(BaseModel):
    """
    Session information.

    Example:
        {
            "session_id": "abc-123",
            "profile": "creative",
            "created_at": "2025-01-01T12:00:00Z",
            "message_count": 15
        }
    """
    session_id: str
    profile: str
    created_at: str  # ISO format
    last_activity: str  # ISO format
    message_count: int
    total_tokens: int = 0

    model_config = ConfigDict(frozen=True)


class SessionHistoryResponse(BaseModel):
    """
    Session conversation history.

    Example:
        {
            "session_id": "abc-123",
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "..."},
                {"role": "assistant", "content": "Hi!", "timestamp": "..."}
            ]
        }
    """
    session_id: str
    messages: List[Dict[str, Any]]
    total_messages: int

    model_config = ConfigDict(frozen=True)


# ============================================================================
# PROFILE MODELS
# ============================================================================

class ProfileResponse(BaseModel):
    """
    Bezier profile configuration.

    Example:
        {
            "profile_name": "creative",
            "description": "High exploration...",
            "tau_c_curve": [[0, 1.3], [0.3, 1.5], ...],
            "preview": [
                {"t": 0.0, "tau_c": 1.30, "rho": 0.50},
                {"t": 0.5, "tau_c": 1.45, "rho": 0.65}
            ]
        }
    """
    profile_name: str
    description: str
    tau_c_curve: List[List[float]]
    rho_curve: List[List[float]]
    delta_r_curve: List[List[float]]
    kappa_curve: Optional[List[List[float]]] = None
    is_default: bool = False

    # Optional: trajectory preview
    preview: Optional[List[Dict[str, float]]] = Field(
        None,
        description="Sampled trajectory points for visualization"
    )

    model_config = ConfigDict(frozen=True)


class ProfileListResponse(BaseModel):
    """
    List of available profiles.

    Example:
        {
            "profiles": [
                {"name": "balanced", "description": "...", "is_default": true},
                {"name": "creative", "description": "...", "is_default": false}
            ]
        }
    """
    profiles: List[Dict[str, Any]]

    model_config = ConfigDict(frozen=True)


# ============================================================================
# SYSTEM MODELS
# ============================================================================

class HealthResponse(BaseModel):
    """
    System health check.

    Example:
        {
            "status": "healthy",
            "database": {"connected": true, "concepts": 15234},
            "ollama": {"connected": true, "model": "gpt-oss:20b"},
            "version": "1.0.0"
        }
    """
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    database: Dict[str, Any]
    ollama: Dict[str, Any]
    version: str
    uptime_seconds: float = 0.0

    model_config = ConfigDict(frozen=True)


class StatsResponse(BaseModel):
    """
    System statistics.

    Example:
        {
            "database": {"concepts": 15234, "relations": 245678, "sessions": 42},
            "performance": {"avg_response_time_ms": 850, "requests_total": 1523}
        }
    """
    database: Dict[str, Any]
    performance: Dict[str, float]
    cache: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(frozen=True)


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """
    Standard error response.

    Example:
        {
            "error": "session_not_found",
            "message": "Session abc-123 does not exist",
            "details": {...}
        }
    """
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context")

    model_config = ConfigDict(frozen=True)


# ============================================================================
# MULTI-MODEL MODELS (Lyra-ACE)
# ============================================================================

class MultiModelRequest(BaseModel):
    """
    Requête de génération multi-modèles.

    Example:
        {
            "text": "Explain quantum entanglement",
            "models": ["llama3.1:8b", "mistral"],
            "session_id": "abc-123",
            "profile": "analytical",
            "stop_on_first_success": false
        }
    """
    text: str = Field(..., min_length=1, max_length=10000)
    models: List[str] = Field(..., min_length=1, max_length=5)
    session_id: Optional[str] = None
    profile: str = Field("balanced")
    stop_on_first_success: bool = Field(False)

    model_config = ConfigDict(frozen=False)


class MultiModelResponseItem(BaseModel):
    """Réponse d'un modèle individuel."""
    model: str
    text: str
    latency_ms: float
    tokens: Dict[str, int]
    success: bool
    error: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class ConsensusMetricsModel(BaseModel):
    """Métriques de consensus."""
    num_models: int
    num_successful: int
    response_lengths: List[int]
    length_variance: float
    avg_latency_ms: float
    model_weights: Dict[str, float]

    model_config = ConfigDict(frozen=True)


class MultiModelResponse(BaseModel):
    """
    Réponse agrégée multi-modèles.

    Example:
        {
            "best_response": "Quantum entanglement is...",
            "best_model": "llama3.1:8b",
            "responses": {...},
            "consensus": {...},
            "session_id": "abc-123"
        }
    """
    best_response: str
    best_model: str
    responses: Dict[str, MultiModelResponseItem]
    consensus: ConsensusMetricsModel
    session_id: str
    physics_state: Dict[str, float]

    model_config = ConfigDict(frozen=True)


# ============================================================================
# BATCH MULTI-MODEL MODELS (VRAM-Optimized)
# ============================================================================

class BatchMultiModelRequest(BaseModel):
    """
    Requête de génération batch multi-modèles avec batching séquentiel.

    STRATÉGIE VRAM:
    - Charge modèle 1 → traite TOUTES les questions → décharge
    - Charge modèle 2 → traite TOUTES les questions → décharge
    - etc.

    Example:
        {
            "questions": [
                "What is entropy?",
                "Explain photosynthesis",
                "What is gravity?"
            ],
            "models": ["llama3.1:8b", "mistral:7b"],
            "profile": "analytical",
            "system_prompt": "You are a science teacher."
        }
    """
    questions: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of questions to process"
    )
    models: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of models to use"
    )
    session_id: Optional[str] = None
    profile: str = Field("balanced", description="Bézier profile name")
    system_prompt: Optional[str] = Field(
        None,
        max_length=5000,
        description="Optional system prompt for all questions"
    )

    model_config = ConfigDict(frozen=False)


class BatchModelResponseItem(BaseModel):
    """Réponse d'une question pour un modèle."""
    question_index: int
    text: str
    latency_ms: float
    tokens: Dict[str, int]
    success: bool
    error: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class BatchMultiModelResponse(BaseModel):
    """
    Réponse du batch multi-modèles.

    Les réponses sont organisées par modèle, chaque modèle ayant
    une liste de réponses correspondant aux questions d'entrée.

    Example:
        {
            "responses": {
                "llama3.1:8b": [...],
                "mistral:7b": [...]
            },
            "models_processed": 2,
            "questions_processed": 3,
            "total_duration_ms": 15000.0,
            "vram_managed": true
        }
    """
    responses: Dict[str, List[BatchModelResponseItem]]
    models_processed: int
    questions_processed: int
    total_duration_ms: float
    vram_managed: bool
    session_id: str
    physics_state: Dict[str, float]

    model_config = ConfigDict(frozen=True)


# ============================================================================
# GRAPH DELTA MODELS (Lyra-ACE)
# ============================================================================

class GraphDeltaRequest(BaseModel):
    """
    Requête d'application d'un delta.

    Example:
        {
            "operation": "add_edge",
            "source": "entropy",
            "target": "information",
            "weight": 0.85,
            "confidence": 0.9,
            "reason": "Strong semantic relationship"
        }
    """
    operation: str = Field(..., pattern="^(add_node|add_edge|update_edge|delete_edge|delete_node)$")
    source: str = Field(..., min_length=1)
    target: Optional[str] = None
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    model_source: str = Field("api")
    reason: Optional[str] = None

    model_config = ConfigDict(frozen=False)


class GraphDeltaResponse(BaseModel):
    """Réponse après application d'un delta."""
    delta_id: int
    operation: str
    source: str
    target: Optional[str]
    old_weight: Optional[float]
    new_weight: Optional[float]
    old_kappa: Optional[float]
    new_kappa: Optional[float]
    applied_at: float

    model_config = ConfigDict(frozen=True)


class KappaResponse(BaseModel):
    """Réponse du calcul de κ."""
    source: str
    target: str
    kappa_ollivier: float
    kappa_jaccard: float
    kappa_hybrid: float
    alpha: float

    model_config = ConfigDict(frozen=True)


# ============================================================================
# ESMM PHASE 1 MODELS
# ============================================================================

class PopulateRequest(BaseModel):
    """
    Requête de population du graphe depuis topics.txt.

    Example:
        {
            "source_file": "data/topics.txt",
            "generate_embeddings": true,
            "batch_size": 50,
            "skip_existing": true
        }
    """
    source_file: str = Field("data/topics.txt", description="Chemin vers le fichier topics")
    generate_embeddings: bool = Field(True, description="Générer les embeddings via Ollama")
    batch_size: int = Field(50, ge=1, le=200, description="Taille du batch pour les embeddings")
    skip_existing: bool = Field(True, description="Ignorer les concepts déjà existants")

    model_config = ConfigDict(frozen=False)


class PopulateResponse(BaseModel):
    """Réponse de population du graphe."""
    concepts_loaded: int
    concepts_skipped: int
    embeddings_generated: int
    embeddings_failed: int
    duplicates_found: int
    duration_ms: float
    errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class GenerateRelationsRequest(BaseModel):
    """
    Requête de génération de relations par similarité.

    Example:
        {
            "similarity_threshold": 0.6,
            "confidence": 0.7,
            "max_neighbors": 20,
            "limit_concepts": null
        }
    """
    similarity_threshold: float = Field(0.6, ge=0.3, le=0.95, description="Seuil de similarité [0.3, 0.95]")
    confidence: float = Field(0.7, ge=0.1, le=1.0, description="Confiance des relations auto-générées")
    max_neighbors: int = Field(20, ge=1, le=100, description="Nombre max de voisins par concept")
    limit_concepts: Optional[int] = Field(None, ge=1, description="Limite de concepts à traiter")

    model_config = ConfigDict(frozen=False)


class GenerateRelationsResponse(BaseModel):
    """Réponse de génération de relations."""
    relations_created: int
    relations_skipped: int
    concepts_processed: int
    average_similarity: float
    duration_ms: float
    errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class InjectSeedRequest(BaseModel):
    """
    Requête d'injection de la graine ESMM.

    Example:
        {
            "seed_type": "standard",
            "generate_embeddings": true,
            "skip_existing_concepts": true
        }
    """
    seed_type: str = Field("standard", pattern="^(minimal|standard|extended)$", description="Type de graine")
    generate_embeddings: bool = Field(True, description="Générer les embeddings pour nouveaux concepts")
    skip_existing_concepts: bool = Field(True, description="Ne pas écraser les concepts existants")

    model_config = ConfigDict(frozen=False)


class InjectSeedResponse(BaseModel):
    """Réponse d'injection de la graine."""
    concepts_created: int
    relations_created: int
    concepts_existed: int
    duration_ms: float
    seed_type: str
    errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class SimilarConceptsRequest(BaseModel):
    """Requête de recherche de concepts similaires."""
    concept_id: str = Field(..., min_length=1, description="ID du concept source")
    top_k: int = Field(10, ge=1, le=100, description="Nombre de résultats")
    min_similarity: float = Field(0.5, ge=0.0, le=1.0, description="Similarité minimum")

    model_config = ConfigDict(frozen=False)


class SimilarConceptsResponse(BaseModel):
    """Réponse de recherche de concepts similaires."""
    concept_id: str
    similar_concepts: List[Dict[str, Any]]
    count: int

    model_config = ConfigDict(frozen=True)


class Phase1StatsResponse(BaseModel):
    """Statistiques complètes de la Phase 1."""
    population: Dict[str, Any] = Field(..., description="Stats de population")
    relations: Dict[str, Any] = Field(..., description="Stats de relations")
    seed: Dict[str, Any] = Field(..., description="Stats de la graine")

    model_config = ConfigDict(frozen=True)


# ============================================================================
# ESMM PHASE 2 MODELS - Triplet Extraction
# ============================================================================

class TripletExtractionRequest(BaseModel):
    """
    Requête d'extraction de triplets avec consensus multi-modèles.

    Example:
        {
            "text": "L'entropie augmente dans les systèmes isolés...",
            "models": ["llama3.1:8b", "mistral:7b"],
            "min_consensus": 0.5,
            "min_confidence": 0.5,
            "inject_to_graph": true
        }
    """
    text: str = Field(..., min_length=10, max_length=50000, description="Texte à analyser")
    models: Optional[List[str]] = Field(
        None,
        description="Modèles à utiliser (défaut: llama3.1:8b, gpt-oss:20b)"
    )
    min_consensus: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Ratio minimum de modèles devant extraire le triplet"
    )
    min_confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Confiance minimum par triplet"
    )
    inject_to_graph: bool = Field(
        True,
        description="Injecter les triplets validés dans le graphe"
    )
    session_id: Optional[str] = Field(None, description="Session ID pour audit")

    model_config = ConfigDict(frozen=False)

    @field_validator('text')
    @classmethod
    def validate_text_content(cls, v):
        """Validation sémantique: texte non vide après nettoyage."""
        cleaned = v.strip()
        if len(cleaned) < 10:
            raise ValueError("Texte trop court après nettoyage")
        if cleaned.count(' ') < 2:
            raise ValueError("Le texte doit contenir au moins 3 mots")
        return cleaned

    @field_validator('models')
    @classmethod
    def validate_models_whitelist(cls, v):
        """Vérifie que les modèles sont dans la whitelist autorisée."""
        if v is None:
            return v
        from services.esmm.triplet_extractor import ALLOWED_MODELS
        invalid = set(v) - ALLOWED_MODELS
        if invalid:
            raise ValueError(f"Modèles non autorisés: {invalid}")
        return v


class ExtractedTripletResponse(BaseModel):
    """Triplet extrait avec métriques de consensus."""
    subject: str
    relation: str
    object: str
    consensus_score: float = Field(..., description="Score combiné agreement*0.6 + confidence*0.4")
    agreement_ratio: float = Field(..., description="Ratio de modèles ayant extrait ce triplet")
    avg_confidence: float = Field(..., description="Confiance moyenne des modèles")
    std_confidence: float = Field(..., description="Écart-type des confiances (controverse)")
    contributing_models: List[str] = Field(..., description="Modèles ayant extrait ce triplet")
    triplet_hash: str = Field(..., description="Hash SHA256 pour traçabilité")
    injected: bool = Field(..., description="True si injecté dans le graphe")
    skip_reason: Optional[str] = Field(None, description="Raison si non injecté")

    model_config = ConfigDict(frozen=True)


class TripletExtractionResponse(BaseModel):
    """
    Réponse complète de l'extraction de triplets.

    Example:
        {
            "triplets": [...],
            "triplets_extracted": 5,
            "triplets_injected": 4,
            "triplets_skipped": 1,
            "new_concepts_created": 2,
            "models_used": ["llama3.1:8b", "mistral:7b"],
            "duration_ms": 8500.0
        }
    """
    triplets: List[ExtractedTripletResponse]
    triplets_extracted: int = Field(..., description="Nombre total de triplets avec consensus")
    triplets_injected: int = Field(..., description="Nombre de triplets injectés dans le graphe")
    triplets_skipped: int = Field(..., description="Nombre de triplets ignorés (doublons)")
    new_concepts_created: int = Field(..., description="Nouveaux concepts créés")
    models_used: List[str] = Field(..., description="Modèles utilisés pour l'extraction")
    duration_ms: float = Field(..., description="Durée totale de l'extraction")
    input_hash: str = Field(..., description="Hash du texte d'entrée pour audit")
    skipped_reasons: Dict[str, int] = Field(
        default_factory=dict,
        description="Raisons des rejets agrégées"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# ESMM PHASE 3 MODELS - ESMM Run
# ============================================================================

# Whitelist des modeles autorises pour ESMM
ALLOWED_ESMM_MODELS = {
    "llama3.3:70b", "llama3.1:8b", "llama3.1:70b", "llama3.2:3b",
    "deepseek-r1:8b", "deepseek-r1:14b", "deepseek-r1:32b", "deepseek-r1:70b",
    "mistral", "mistral:7b", "mixtral:8x7b", "mistral-nemo:12b",
    "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b", "qwen2.5:72b",
    "gemma2:9b", "gemma2:27b",
    "phi3:14b", "phi4:14b",
    "gpt-oss:20b",
}


class ESMMRunRequest(BaseModel):
    """
    Requete pour demarrer un run ESMM Phase 3.

    Example:
        {
            "models": ["mistral", "gpt-oss:20b"],
            "seed_type": "standard",
            "cycles_per_type": {"divergent": 3, "debate": 2, "meta": 1},
            "min_consensus": 0.5,
            "adaptive_cycles": true
        }
    """
    models: List[str] = Field(
        default=["mistral", "gpt-oss:20b"],
        min_length=1,
        max_length=5,
        description="Modeles a utiliser (whitelist)"
    )
    seed_type: str = Field(
        default="standard",
        pattern="^(minimal|standard|extended)$",
        description="Type de graine semantique"
    )
    cycles_per_type: Optional[Dict[str, int]] = Field(
        default=None,
        description="Nombre de cycles par type (divergent, debate, meta)"
    )
    min_consensus: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Seuil minimum de consensus"
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Seuil minimum de confiance"
    )
    adaptive_cycles: bool = Field(
        default=True,
        description="Adapter dynamiquement les cycles"
    )
    detect_gaps: bool = Field(
        default=True,
        description="Detecter les lacunes de connaissances"
    )
    build_cochain: bool = Field(
        default=True,
        description="Construire la 0-cochaine"
    )
    max_total_cycles: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Limite de cycles pour eviter boucles infinies"
    )

    model_config = ConfigDict(frozen=False)

    @field_validator('models')
    @classmethod
    def validate_models(cls, v):
        """Verifie que les modeles sont dans la whitelist."""
        invalid = set(v) - ALLOWED_ESMM_MODELS
        if invalid:
            raise ValueError(f"Modeles non autorises: {invalid}")
        return v


class ESMMRunStatusResponse(BaseModel):
    """
    Statut d'un run ESMM en cours.

    Example:
        {
            "run_id": 1,
            "status": "running",
            "current_cycle": "divergent",
            "cycles_completed": 3,
            "progress_percent": 50.0
        }
    """
    run_id: int
    status: str = Field(..., description="Status: initializing, running, paused, completed, failed")
    current_cycle: Optional[str] = Field(None, description="Type de cycle en cours")
    current_iteration: Optional[int] = Field(None, description="Iteration du cycle")
    cycles_completed: int = Field(default=0, description="Nombre de cycles termines")
    progress_percent: float = Field(default=0.0, description="Progression estimee [0-100]")
    started_at: Optional[str] = Field(None, description="Timestamp de debut ISO")
    error_message: Optional[str] = Field(None, description="Message d'erreur si failed")

    model_config = ConfigDict(frozen=True)


class ESMMRunResultResponse(BaseModel):
    """
    Resultat complet d'un run ESMM termine.

    Example:
        {
            "run_id": 1,
            "status": "completed",
            "cycles_completed": 6,
            "total_triplets": 45,
            "triplets_injected": 38,
            "cochain_size": 120,
            "gaps_detected": 15,
            "coverage_score": 0.72,
            "consensus_density": 0.68,
            "duration_ms": 180000.0
        }
    """
    run_id: int
    status: str
    cycles_completed: int
    total_triplets: int = Field(..., description="Total de triplets extraits")
    triplets_injected: int = Field(..., description="Triplets injectes dans le graphe")
    cochain_size: int = Field(..., description="Taille de la 0-cochaine")
    gaps_detected: int = Field(default=0, description="Lacunes detectees")
    coverage_score: float = Field(..., description="Score de couverture [0,1]")
    consensus_density: float = Field(..., description="Densite de consensus [0,1]")
    epistemic_diversity: Optional[float] = Field(None, description="Diversite epistemique [0,1]")
    structural_stability: Optional[float] = Field(None, description="Stabilite structurelle [0,1]")
    duration_ms: float = Field(..., description="Duree totale en ms")
    errors: List[str] = Field(default_factory=list, description="Erreurs rencontrees")

    model_config = ConfigDict(frozen=True)


class CycleResultResponse(BaseModel):
    """Resultat d'un cycle d'exploration individuel."""
    cycle_id: int
    cycle_type: str = Field(..., description="Type: divergent, debate, meta")
    iteration: int
    question: str
    triplets_extracted: int
    duration_ms: float
    target_concepts: Optional[List[str]] = None

    model_config = ConfigDict(frozen=True)


class KnowledgeGapResponse(BaseModel):
    """Lacune de connaissance detectee."""
    gap_id: int
    gap_type: str = Field(..., description="Type: isolated, unstable, bridge")
    priority: float = Field(..., description="Priorite [0,1]")
    details: Dict[str, Any]
    suggested_question: Optional[str] = None
    addressed: bool = Field(default=False)

    model_config = ConfigDict(frozen=True)


class CochainEntryResponse(BaseModel):
    """Entree de la 0-cochaine."""
    concept_id: str
    consensus_score: float
    model_agreement: float
    semantic_consistency: float
    structural_centrality: float
    stability_score: float
    epistemic_type: str = Field(..., description="Type: generalist, specialized, hybrid")
    signature_vector: List[float] = Field(..., description="Vecteur 5D normalise")
    triplet_count: int

    model_config = ConfigDict(frozen=True)


class CoverageMetricsResponse(BaseModel):
    """Metriques de couverture du graphe."""
    coverage_score: float = Field(..., description="Score composite [0,1]")
    consensus_density: float
    epistemic_diversity: float
    structural_stability: float
    graph_density: float
    isolated_ratio: float
    clustering_coefficient: float

    model_config = ConfigDict(frozen=True)


# ============================================================================
# UTILITIES
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    Rough token estimation (4 chars ≈ 1 token).

    Args:
        text: Input text

    Returns:
        Approximate token count
    """
    return len(text) // 4


def format_timestamp(unix_time: float) -> str:
    """
    Format Unix timestamp as ISO 8601.

    Args:
        unix_time: Unix timestamp (seconds)

    Returns:
        ISO format string (e.g., "2025-01-01T12:00:00Z")
    """
    return datetime.fromtimestamp(unix_time).isoformat() + "Z"
