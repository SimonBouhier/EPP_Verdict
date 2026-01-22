"""
Tests unitaires Phase 1 : Metriques passives
"""
import pytest
import sys
from pathlib import Path

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.consciousness.metrics import ConsciousnessMonitor, ConsciousnessMetrics


class TestConsciousnessMetrics:
    """Tests metriques epistemiques"""
    
    def test_monitor_level_0_returns_none(self):
        """Level 0 ne calcule pas de metriques"""
        monitor = ConsciousnessMonitor(level=0)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        assert metrics is None
    
    def test_monitor_level_1_returns_metrics(self):
        """Level 1 calcule metriques"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.6,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        assert metrics is not None
        assert isinstance(metrics, ConsciousnessMetrics)
        assert 0.0 <= metrics.coherence <= 1.0
        assert 0.0 <= metrics.tension <= 1.0
        assert 0.0 <= metrics.fit <= 1.0
        assert 0.0 <= metrics.pressure <= 1.0
    
    def test_high_coherence_scenario(self):
        """Contexte fort -> haute coherence"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=8.0,  # Fort
            num_concepts=10,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=150
        )
        assert metrics.coherence > 0.7  # Attendu haute
    
    def test_low_coherence_scenario(self):
        """Contexte faible -> basse coherence"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=0.5,  # Tres faible
            num_concepts=5,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=150
        )
        assert metrics.coherence < 0.3  # Attendu basse
    
    def test_high_pressure_scenario(self):
        """Tau_c eleve -> haute pression"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.8, "rho": 0.0, "delta_r": 0.5},  # Eleves
            response_length=150
        )
        assert metrics.pressure >= 0.6  # Attendu haute (0.3*0.5 + 0.7*1.8/2.8 = 0.15 + 0.45 = 0.6)
    
    def test_low_pressure_scenario(self):
        """Tau_c bas, delta_r bas -> basse pression"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 0.3, "rho": 0.0, "delta_r": 0.0},  # Bas
            response_length=150
        )
        assert metrics.pressure < 0.4  # Attendu basse
    
    def test_high_tension_scenario(self):
        """Coherence basse + pressure haute -> haute tension"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=1.0,  # Faible
            num_concepts=5,
            physics_state={"tau_c": 1.8, "rho": 0.0, "delta_r": 0.5},  # Haute pression
            response_length=150
        )
        assert metrics.tension > 0.6  # Attendu haute
    
    def test_good_fit_with_positive_rho(self):
        """Rho positif (expansif) + response longue -> bon fit"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.5, "delta_r": 0.0},  # Expansif
            response_length=250  # Reponse longue
        )
        assert metrics.fit > 0.7  # Attendu bon fit
    
    def test_good_fit_with_negative_rho(self):
        """Rho negatif (concis) + response courte -> bon fit"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": -0.5, "delta_r": 0.0},  # Concis
            response_length=100  # Reponse courte
        )
        assert metrics.fit > 0.7  # Attendu bon fit
    
    def test_metrics_dict_serialization(self):
        """Metriques serialisables en JSON"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        metrics_dict = metrics.dict()
        assert "coherence" in metrics_dict
        assert "tension" in metrics_dict
        assert "fit" in metrics_dict
        assert "pressure" in metrics_dict
        assert "stability_score" in metrics_dict
        
        # Verifier que tous les values sont des floats
        for key in ["coherence", "tension", "fit", "pressure", "stability_score"]:
            assert isinstance(metrics_dict[key], (int, float))
            assert 0.0 <= metrics_dict[key] <= 1.0 or key == "stability_score"
    
    def test_zero_concepts_edge_case(self):
        """Aucun concept injecte -> coherence 0"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=0.0,
            num_concepts=0,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=150
        )
        assert metrics.coherence == 0.0
    
    def test_empty_response_edge_case(self):
        """Reponse vide (0 mots) -> calcul valide"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=0
        )
        assert isinstance(metrics, ConsciousnessMetrics)
        assert metrics.fit < 0.5  # Mauvais fit pour response vide
    
    def test_stability_score_calculation(self):
        """Stability score = (coherence + fit) / 2 - tension * 0.5"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.6,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=150
        )
        
        expected_stability = (metrics.coherence + metrics.fit) / 2 - metrics.tension * 0.5
        assert abs(metrics.stability_score - expected_stability) < 0.001
    
    def test_metrics_normalization_bounds(self):
        """Tous les metriques sont normalisees [0,1]"""
        monitor = ConsciousnessMonitor(level=1)
        
        # Test avec extremes
        test_cases = [
            {"weight": 0.0, "concepts": 0, "tau_c": 0.0, "delta_r": 0.0, "length": 0},
            {"weight": 100.0, "concepts": 100, "tau_c": 10.0, "delta_r": 10.0, "length": 10000},
            {"weight": 5.0, "concepts": 7, "tau_c": 1.0, "delta_r": 0.0, "length": 150},
        ]
        
        for case in test_cases:
            metrics = monitor.compute_metrics(
                context_weight=case["weight"],
                num_concepts=case["concepts"],
                physics_state={"tau_c": case["tau_c"], "rho": 0.0, "delta_r": case["delta_r"]},
                response_length=case["length"]
            )
            
            assert 0.0 <= metrics.coherence <= 1.0, f"coherence out of bounds: {metrics.coherence}"
            assert 0.0 <= metrics.tension <= 1.0, f"tension out of bounds: {metrics.tension}"
            assert 0.0 <= metrics.fit <= 1.0, f"fit out of bounds: {metrics.fit}"
            assert 0.0 <= metrics.pressure <= 1.0, f"pressure out of bounds: {metrics.pressure}"


class TestConsciousnessMetricsIntegration:
    """Tests d'integration (requierent serveur)"""
    
    @pytest.mark.skip(reason="Requiert serveur API actif")
    def test_api_consciousness_level_0(self):
        """Test API avec consciousness_level=0"""
        pass
    
    @pytest.mark.skip(reason="Requiert serveur API actif")
    def test_api_consciousness_level_1(self):
        """Test API avec consciousness_level=1"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
