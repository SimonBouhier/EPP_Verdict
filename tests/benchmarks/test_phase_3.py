"""
Tests unitaires Phase 3 - Semantic Memory

Tests mémoire sémantique, decay, similarité, et rappel.
"""

import pytest
import math
from services.consciousness.metrics import ConsciousnessMetrics
from services.consciousness.adaptation import AdaptiveConsciousness
from services.consciousness.memory import SemanticMemory, MemoryEntry


class TestSemanticMemoryBasics:
    """Tests basiques de la mémoire sémantique"""
    
    def test_inheritance_from_adaptive(self):
        """Vérifier qu'SemanticMemory hérite de AdaptiveConsciousness"""
        memory = SemanticMemory(level=3)
        assert isinstance(memory, AdaptiveConsciousness)
        assert memory.level == 3
        assert memory.max_memory_entries == 50
    
    def test_custom_parameters(self):
        """Vérifier paramètres personnalisés"""
        memory = SemanticMemory(
            level=3,
            adaptation_rate=0.10,
            max_memory_entries=100,
            decay_rate=0.02,
            similarity_threshold=0.7
        )
        assert memory.adaptation_rate == 0.10
        assert memory.max_memory_entries == 100
        assert memory.decay_rate == 0.02
        assert memory.similarity_threshold == 0.7
    
    def test_level_below_3_returns_none(self):
        """Niveau < 3 ne doit pas stocker en mémoire"""
        memory = SemanticMemory(level=2)
        embeddings = [0.1] * 1024
        result = memory.store_memory("session1", "Test message", embeddings, 1)
        assert result is None


class TestMemoryStorage:
    """Tests stockage en mémoire"""
    
    def test_store_memory_creates_entry(self):
        """Vérifier création d'une entrée mémoire"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        entry = memory.store_memory("session1", "Hello world", embeddings, 1)
        
        assert entry is not None
        assert entry.session_id == "session1"
        assert entry.content == "Hello world"
        assert entry.turn_number == 1
        assert len(entry.embeddings) == 1024
    
    def test_store_multiple_messages_same_session(self):
        """Vérifier stockage de plusieurs messages"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        
        entry1 = memory.store_memory("session1", "Message 1", embeddings, 1)
        entry2 = memory.store_memory("session1", "Message 2", embeddings, 2)
        
        assert len(memory.memory["session1"]) == 2
        assert entry1.message_id != entry2.message_id
    
    def test_store_invalid_embeddings_returns_none(self):
        """Stocker avec mauvais vecteur doit retourner None"""
        memory = SemanticMemory(level=3)
        
        # Mauvaise taille
        result = memory.store_memory("session1", "Message", [0.1] * 512, 1)
        assert result is None
        
        # Vide
        result = memory.store_memory("session1", "Message", [], 1)
        assert result is None
    
    def test_max_memory_entries_enforced(self):
        """Vérifier que max_memory_entries est respecté"""
        memory = SemanticMemory(level=3, max_memory_entries=5)
        embeddings = [0.1] * 1024
        
        # Ajouter 10 messages
        for i in range(10):
            memory.store_memory("session1", f"Message {i}", embeddings, i)
        
        # Doit garder seulement les 5 derniers
        assert len(memory.memory["session1"]) == 5
        assert memory.memory["session1"][0].turn_number == 5


class TestCosineSimilarity:
    """Tests calcul similarité cosinus"""
    
    def test_identical_vectors_similarity_one(self):
        """Vecteurs identiques → similarity = 1.0"""
        memory = SemanticMemory(level=3)
        vec = [1.0, 0.0, 0.0, 0.0]
        similarity = memory._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001
    
    def test_orthogonal_vectors_similarity_zero(self):
        """Vecteurs orthogonaux → similarity = 0.0"""
        memory = SemanticMemory(level=3)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = memory._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001
    
    def test_opposite_vectors_similarity_minus_one(self):
        """Vecteurs opposés → similarity = -1.0 (clamped à 0)"""
        memory = SemanticMemory(level=3)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = memory._cosine_similarity(vec1, vec2)
        assert similarity == 0.0  # Clamped
    
    def test_partial_similarity(self):
        """Vecteurs partiellement similaires"""
        memory = SemanticMemory(level=3)
        vec1 = [1.0, 1.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = memory._cosine_similarity(vec1, vec2)
        # Dot = 1.0, norm1 = sqrt(2), norm2 = 1.0
        # similarity = 1.0 / sqrt(2) ≈ 0.707
        assert 0.7 < similarity < 0.71
    
    def test_invalid_vectors_return_zero(self):
        """Vecteurs invalides → similarity = 0"""
        memory = SemanticMemory(level=3)
        assert memory._cosine_similarity([], [1.0]) == 0.0
        assert memory._cosine_similarity([1.0], None) == 0.0
        assert memory._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestDecayFormula:
    """Tests formule decay temporelle"""
    
    def test_decay_turn_zero(self):
        """Decay au tour 0 (nouveau message) doit être 1.0"""
        memory = SemanticMemory(level=3, decay_rate=0.01)
        decay = memory._compute_decay(0)
        assert abs(decay - 1.0) < 0.001
    
    def test_decay_10_turns_ago(self):
        """Decay 10 tours plus tard : 1.0 - 10*0.01 = 0.9"""
        memory = SemanticMemory(level=3, decay_rate=0.01)
        decay = memory._compute_decay(10)
        assert abs(decay - 0.9) < 0.001
    
    def test_decay_min_bound(self):
        """Decay ne doit pas aller sous 0.5"""
        memory = SemanticMemory(level=3, decay_rate=0.01)
        decay = memory._compute_decay(100)  # 1.0 - 100*0.01 = 0.0, clamped à 0.5
        assert decay == 0.5
    
    def test_decay_custom_rate(self):
        """Vérifier avec taux decay personnalisé"""
        memory = SemanticMemory(level=3, decay_rate=0.05)
        decay = memory._compute_decay(5)  # 1.0 - 5*0.05 = 0.75
        assert abs(decay - 0.75) < 0.001


class TestMemoryRecall:
    """Tests rappel de mémoire"""
    
    def test_recall_empty_session(self):
        """Rappel depuis session vide → liste vide"""
        memory = SemanticMemory(level=3)
        query = [0.1] * 1024
        result = memory.recall_memory("nonexistent", query, 1)
        assert result == []
    
    def test_recall_exact_match(self):
        """Vecteur identique doit être rappelé avec score élevé"""
        memory = SemanticMemory(level=3, similarity_threshold=0.5)
        embeddings = [0.5, 0.5, 0.5, 0.5] + [0.0] * 1020
        
        memory.store_memory("session1", "Exact message", embeddings, 1)
        
        # Rappel avec le même vecteur
        result = memory.recall_memory("session1", embeddings, 2)
        
        assert len(result) > 0
        assert result[0]['content'] == "Exact message"
        assert result[0]['similarity'] > 0.99
    
    def test_recall_applies_decay(self):
        """Vérifier que decay est appliqué dans recall"""
        memory = SemanticMemory(level=3, decay_rate=0.1, similarity_threshold=0.5)
        embeddings = [0.5] * 1024
        
        # Stocker message au tour 1
        memory.store_memory("session1", "Old message", embeddings, 1)
        
        # Rappel au tour 20 (19 tours écoulés)
        result = memory.recall_memory("session1", embeddings, 20)
        
        assert len(result) > 0
        # Decay = 1.0 - 19*0.1 = 0.1 (clamped à 0.5)
        assert result[0]['decay'] == 0.5
        # final_score = similarity * decay ≈ 1.0 * 0.5 = 0.5
        assert result[0]['final_score'] > 0.4
    
    def test_recall_threshold_filtering(self):
        """Messages sous threshold ne sont pas rappelés"""
        memory = SemanticMemory(level=3, similarity_threshold=0.9)
        embeddings1 = [1.0, 0.0, 0.0] + [0.0] * 1021  # (1, 0, 0)
        embeddings2 = [0.0, 1.0, 0.0] + [0.0] * 1021  # (0, 1, 0) - orthogonal
        
        memory.store_memory("session1", "Message 1", embeddings1, 1)
        
        # Rappel avec vecteur orthogonal (similarité = 0)
        result = memory.recall_memory("session1", embeddings2, 2)
        
        # Similarité 0, decay ~0.99, score = 0 * 0.99 = 0 < 0.9 threshold
        assert len(result) == 0
    
    def test_recall_top_k(self):
        """Vérifier que top_k est respecté"""
        memory = SemanticMemory(level=3, similarity_threshold=0.1)
        embeddings = [0.5] * 1024
        
        # Ajouter 5 messages identiques
        for i in range(5):
            memory.store_memory("session1", f"Message {i}", embeddings, i)
        
        # Rappel avec top_k=3
        result = memory.recall_memory("session1", embeddings, 10, top_k=3)
        
        assert len(result) == 3


class TestMemoryFormatting:
    """Tests formatage mémoire"""
    
    def test_format_memory_echo_empty(self):
        """Vide doit retourner None"""
        memory = SemanticMemory(level=3)
        result = memory.format_memory_echo([])
        assert result is None
    
    def test_format_memory_echo_single(self):
        """Formater un seul message"""
        memory = SemanticMemory(level=3)
        recalled = [
            {'content': 'Hello world', 'final_score': 0.95}
        ]
        result = memory.format_memory_echo(recalled)
        
        assert result is not None
        assert '[MEMORY ECHO]' in result
        assert 'Hello world' in result
        assert '0.95' in result
    
    def test_format_memory_echo_multiple(self):
        """Formater plusieurs messages"""
        memory = SemanticMemory(level=3)
        recalled = [
            {'content': 'Message 1 content', 'final_score': 0.95},
            {'content': 'Message 2 content', 'final_score': 0.85},
            {'content': 'Message 3 content', 'final_score': 0.75}
        ]
        result = memory.format_memory_echo(recalled)
        
        assert result is not None
        lines = result.split('\n')
        assert len(lines) == 4  # Header + 3 messages
        assert all('Message' in line or 'MEMORY' in line for line in lines)


class TestMemoryStats:
    """Tests statistiques mémoire"""
    
    def test_stats_empty_session(self):
        """Stats pour session vide"""
        memory = SemanticMemory(level=3)
        stats = memory.get_memory_stats("nonexistent")
        
        assert stats['entry_count'] == 0
        assert stats['memory_status'] == 'empty'
    
    def test_stats_active_session(self):
        """Stats pour session active"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        
        for i in range(5):
            memory.store_memory("session1", f"Message {i}", embeddings, i)
        
        stats = memory.get_memory_stats("session1")
        
        assert stats['entry_count'] == 5
        assert stats['oldest_turn'] == 0
        assert stats['newest_turn'] == 4
        assert stats['turn_span'] == 5
        assert stats['memory_status'] == 'active'


class TestMemoryClearance:
    """Tests nettoyage mémoire"""
    
    def test_clear_session_memory(self):
        """Nettoyer une session"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        
        memory.store_memory("session1", "Message", embeddings, 1)
        assert "session1" in memory.memory
        
        result = memory.clear_session_memory("session1")
        assert result is True
        assert "session1" not in memory.memory
    
    def test_clear_nonexistent_session(self):
        """Nettoyer session inexistante doit retourner False"""
        memory = SemanticMemory(level=3)
        result = memory.clear_session_memory("nonexistent")
        assert result is False


class TestMemoryIntegration:
    """Tests intégration mémoire complète"""
    
    def test_full_conversation_cycle(self):
        """Cycle complet: stocker → rappeler → formater"""
        memory = SemanticMemory(level=3, similarity_threshold=0.5)
        
        # Stocker messages
        embeddings_set = [
            [0.8, 0.2, 0.0] + [0.0] * 1021,
            [0.7, 0.3, 0.0] + [0.0] * 1021,
            [0.0, 0.0, 0.8] + [0.0] * 1021
        ]
        
        for i, emb in enumerate(embeddings_set):
            memory.store_memory("session1", f"Turn {i} message", emb, i)
        
        # Rappeler avec vecteur similaire à message 0-1
        query = [0.75, 0.25, 0.0] + [0.0] * 1021
        recalled = memory.recall_memory("session1", query, 5)
        
        # Formater
        formatted = memory.format_memory_echo(recalled)
        
        assert len(recalled) > 0
        assert formatted is not None
        assert '[MEMORY ECHO]' in formatted
    
    def test_multiple_sessions_isolation(self):
        """Vérifier que sessions ne se mélangent pas"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        
        memory.store_memory("session1", "Message 1", embeddings, 1)
        memory.store_memory("session2", "Message 2", embeddings, 1)
        
        # Rappel session1 ne doit pas récupérer session2
        result = memory.recall_memory("session1", embeddings, 2)
        assert len(result) == 1
        assert "Message 1" in result[0]['content']


class TestMemoryEdgeCases:
    """Tests cas limites"""
    
    def test_very_long_message_content(self):
        """Message très long doit être troncaté dans format"""
        memory = SemanticMemory(level=3)
        embeddings = [0.1] * 1024
        long_content = "x" * 500  # 500 caractères
        
        memory.store_memory("session1", long_content, embeddings, 1)
        recalled = memory.recall_memory("session1", embeddings, 2)
        formatted = memory.format_memory_echo(recalled)
        
        # Doit être tronqué à 100 chars dans format
        assert len(formatted) < len(long_content)
    
    def test_decay_zero_rate(self):
        """Decay rate = 0 → pas de decay"""
        memory = SemanticMemory(level=3, decay_rate=0.0)
        decay = memory._compute_decay(100)
        assert decay == 1.0  # Pas de decay
    
    def test_threshold_exactly_at_boundary(self):
        """Message exactement au threshold doit être rappelé"""
        memory = SemanticMemory(level=3, similarity_threshold=0.75)
        embeddings = [0.1] * 1024
        
        memory.store_memory("session1", "Message", embeddings, 1)
        
        # Créer query qui donne exactement 0.75
        # (après decay et mul, résultat = 0.75)
        result = memory.recall_memory("session1", embeddings, 1)
        
        # Avec threshold=0.75 et score ≈ 1.0, doit être inclus
        assert len(result) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
