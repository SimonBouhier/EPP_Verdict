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
    ASSESS_TEMPLATES,
    CHALLENGE_TEMPLATES,
    ADJUDICATE_TEMPLATES,
    get_template,
    get_system_prompt,
    format_triplets_for_prompt
)

# Dual-mode: Claim Verification (VERIFY)
from .question_seeder import InputType, classify_input
from .verdict_encoder import encode_verdict_as_triplets
from .triplet_extractor import _parse_verdict_response
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

# Relation Vocabulary — Source unique de vérité (11 groupes)
from .relation_vocabulary import (
    RELATION_GROUPS as RELATION_VOCABULARY_GROUPS,
    build_synonym_map, get_canonical, are_relations_compatible,
)

# ADR-011-v2: Semantic Fingerprinting
from .fingerprint_config import FingerprintConfig, load_fingerprint_config
from .fingerprint_expand import MicroGraph, ExpandResult, build_expand_prompt, parse_expand_response, expand_terms
from .fingerprint_match import (
    ClassifiedNeighbor, MatchResult,
    jaro_winkler_similarity, classify_neighbor,
    match_neighbor_pair, compute_weighted_overlap,
    find_connected_components, match_fingerprints,
)
from .fingerprint_apply import (
    AlignmentEntry, AlignmentTable,
    select_canonical, build_alignment_table, apply_alignment_to_triplets,
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
    "ASSESS_TEMPLATES",
    "CHALLENGE_TEMPLATES",
    "ADJUDICATE_TEMPLATES",
    "get_template",
    "get_system_prompt",
    "format_triplets_for_prompt",
    # Dual-mode: Claim Verification
    "InputType",
    "classify_input",
    "encode_verdict_as_triplets",
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
    # Relation Vocabulary
    "RELATION_VOCABULARY_GROUPS",
    "build_synonym_map",
    "get_canonical",
    "are_relations_compatible",
    # ADR-011-v2: Semantic Fingerprinting
    "FingerprintConfig",
    "load_fingerprint_config",
    "MicroGraph",
    "ExpandResult",
    "build_expand_prompt",
    "parse_expand_response",
    "expand_terms",
    "ClassifiedNeighbor",
    "MatchResult",
    "jaro_winkler_similarity",
    "classify_neighbor",
    "match_neighbor_pair",
    "compute_weighted_overlap",
    "find_connected_components",
    "match_fingerprints",
    "AlignmentEntry",
    "AlignmentTable",
    "select_canonical",
    "build_alignment_table",
    "apply_alignment_to_triplets",
]
