"""
ESMM - Exploration Sémantique Multi-Modèles
============================================

Module principal pour le protocole ESMM de Lyra-ACE.

Phase 1: Fondations
- populate_graph: Chargement des concepts depuis topics.txt
- relation_generator: Génération de relations par similarité d'embeddings
- seed_injector: Injection de la graine sémantique dialectique
- model_rotator: Rotation séquentielle des modèles pour gestion VRAM

Phase 2: Extracteur de triplets
- consensus_engine: Vote multi-modèles avec scoring configurable
- triplet_extractor: Orchestrateur d'extraction avec retry et cache

Phase 3: Protocole ESMM complet
- cycle_prompts: Templates pour cycles divergent/debate/meta
- cycle_manager: Gestion des cycles d'exploration
- gap_detector: Détection des lacunes de connaissances
- cochain_builder: Construction de la 0-cochaîne épistémique
- coverage_analyzer: Métriques de couverture sémantique
- orchestrator: Orchestrateur principal du protocole

Author: Lyra-ACE ESMM Protocol
Version: 3.0
"""

from .populate_graph import GraphPopulator
from .relation_generator import RelationGenerator
from .seed_injector import SeedInjector
from .model_rotator import (
    ModelRotator,
    get_model_rotator,
    close_model_rotator,
    RotatedResponse,
    RotationResult,
    BatchModelResult
)
from .prompts import (
    CANONICAL_RELATIONS,
    get_triplet_extraction_prompt,
    get_triplet_validation_prompt,
    get_relation_generation_prompt,
    get_concept_extraction_prompt,
    is_canonical_relation,
    normalize_relation
)
from .triplet_validator import (
    TripletValidator,
    ExtractedTriplet,
    ValidationResult,
    validate_triplet_quick,
    extract_and_validate
)
from .consensus_engine import (
    ConsensusEngine,
    ConsensusTriplet,
    create_consensus_engine
)
from .triplet_extractor import (
    TripletExtractor,
    ExtractionResult,
    get_triplet_extractor,
    close_triplet_extractor,
)

# Phase 3: Protocole ESMM complet
from .cycle_prompts import (
    CycleType,
    CYCLE_TEMPLATES,
    DIVERGENT_TEMPLATES,
    DEBATE_TEMPLATES,
    META_TEMPLATES,
    get_template,
    get_system_prompt,
    format_triplets_for_prompt
)
from .cycle_manager import (
    ExplorationCycleManager,
    CycleResult,
    create_cycle_manager
)
from .gap_detector import (
    KnowledgeGapDetector,
    KnowledgeGap,
    GapType,
    create_gap_detector
)
from .cochain_builder import (
    CochainBuilder,
    CochainEntry,
    EpistemicType,
    create_cochain_builder
)
from .coverage_analyzer import (
    CoverageAnalyzer,
    CoverageMetrics,
    create_coverage_analyzer
)
from .orchestrator import (
    ESMMOrchestrator,
    ESMMRunConfig,
    ESMMRunResult,
    ESMMRunState,
    run_esmm_protocol,
    resume_esmm_protocol
)

__all__ = [
    # Phase 1: Graph Population
    "GraphPopulator",
    "RelationGenerator",
    "SeedInjector",
    # VRAM Management
    "ModelRotator",
    "get_model_rotator",
    "close_model_rotator",
    "RotatedResponse",
    "RotationResult",
    "BatchModelResult",
    # Prompts
    "CANONICAL_RELATIONS",
    "get_triplet_extraction_prompt",
    "get_triplet_validation_prompt",
    "get_relation_generation_prompt",
    "get_concept_extraction_prompt",
    "is_canonical_relation",
    "normalize_relation",
    # Validation
    "TripletValidator",
    "ExtractedTriplet",
    "ValidationResult",
    "validate_triplet_quick",
    "extract_and_validate",
    # Phase 2: Triplet Extraction
    "ConsensusEngine",
    "ConsensusTriplet",
    "create_consensus_engine",
    "TripletExtractor",
    "ExtractionResult",
    "get_triplet_extractor",
    "close_triplet_extractor",
    # Phase 3: Cycle Prompts
    "CycleType",
    "CYCLE_TEMPLATES",
    "DIVERGENT_TEMPLATES",
    "DEBATE_TEMPLATES",
    "META_TEMPLATES",
    "get_template",
    "get_system_prompt",
    "format_triplets_for_prompt",
    # Phase 3: Cycle Manager
    "ExplorationCycleManager",
    "CycleResult",
    "create_cycle_manager",
    # Phase 3: Gap Detector
    "KnowledgeGapDetector",
    "KnowledgeGap",
    "GapType",
    "create_gap_detector",
    # Phase 3: Cochain Builder
    "CochainBuilder",
    "CochainEntry",
    "EpistemicType",
    "create_cochain_builder",
    # Phase 3: Coverage Analyzer
    "CoverageAnalyzer",
    "CoverageMetrics",
    "create_coverage_analyzer",
    # Phase 3: Orchestrator
    "ESMMOrchestrator",
    "ESMMRunConfig",
    "ESMMRunResult",
    "ESMMRunState",
    "run_esmm_protocol",
    "resume_esmm_protocol",
]
