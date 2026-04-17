"""
Services package for EPP_Verdict.

Exports:
- ContextInjector: Semantic context injection
- ConversationMemory: Session history management
- SessionStorage: Save/load session management
- EntityResolver: Semantic entity resolution (ESMM)
- RelationNormalizer: Canonical relation mapping (ESMM)
"""
from .injector import (
    ContextInjector,
    ConversationMemory,
    GraphContext,
    extract_keywords,
    build_system_prompt
)
from .session_storage import (
    SessionStorage,
    get_session_storage
)
from .entity_resolver import (
    EntityResolver,
    ResolutionResult,
    get_entity_resolver,
    SIMILARITY_THRESHOLD,
    REVIEW_THRESHOLD
)
from .relation_normalizer import (
    RelationNormalizer,
    get_relation_normalizer
)

__all__ = [
    # Context & Memory
    'ContextInjector',
    'ConversationMemory',
    'GraphContext',
    'extract_keywords',
    'build_system_prompt',
    # Session
    'SessionStorage',
    'get_session_storage',
    # ESMM: Entity Resolution
    'EntityResolver',
    'ResolutionResult',
    'get_entity_resolver',
    'SIMILARITY_THRESHOLD',
    'REVIEW_THRESHOLD',
    # ESMM: Relation Normalization
    'RelationNormalizer',
    'get_relation_normalizer',
]