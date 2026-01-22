"""
Tests unitaires Phase 2 - AdaptiveConsciousness

Tests d'adaptation graduelle, application paramètres, et gestion règles.
"""

import pytest
from services.consciousness.metrics import ConsciousnessMetrics, ConsciousnessMonitor
from services.consciousness.adaptation import AdaptiveConsciousness


class TestAdaptiveConsciousnessBasics:
    """Tests basiques adaptabilité"""
    
    def test_inheritance_from_monitor(self):
        """Vérifier qu'AdaptiveConsciousness hérite de ConsciousnessMonitor"""
        adaptive = AdaptiveConsciousness(level=2)
        assert isinstance(adaptive, ConsciousnessMonitor)
        assert adaptive.level == 2
        assert adaptive.adaptation_rate == 0.05
    
    def test_custom_adaptation_rate(self):
        """Vérifier taux d'adaptation personnalisé"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.10)
        assert adaptive.adaptation_rate == 0.10
    
    def test_level_below_2_returns_none(self):
        """Niveau < 2 ne doit pas suggérer d'ajustements"""
        monitor = AdaptiveConsciousness(level=1)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.8, fit=0.5, pressure=0.9
        )
        result = monitor.suggest_adjustments(
            metrics,
            {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        )
        assert result is None


class TestAdaptationRules:
    """Tests des 5 règles d'adaptation"""
    
    def test_rule_1_high_tension_reduces_tau_c(self):
        """Règle 1: tension > 0.75 → tau_c *= 0.95"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.80, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert 'tau_c_multiplier' in adjustments
        assert adjustments['tau_c_multiplier'] == 0.95
        assert 'High tension' in adjustments['reason']
    
    def test_rule_2_low_coherence_adjusts_rho_positive(self):
        """Règle 2: coherence < 0.3, rho > 0 → rho_shift = -0.05"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.2, tension=0.3, fit=0.5, pressure=0.3
        )
        profile = {'tau_c': 1.0, 'rho': 0.5, 'delta_r': 0.0}  # rho > 0
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert 'rho_shift' in adjustments
        assert adjustments['rho_shift'] == -0.05
        assert 'Low coherence' in adjustments['reason']
    
    def test_rule_2_low_coherence_adjusts_rho_negative(self):
        """Règle 2: coherence < 0.3, rho < 0 → rho_shift = +0.05"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.2, tension=0.3, fit=0.5, pressure=0.3
        )
        profile = {'tau_c': 1.0, 'rho': -0.5, 'delta_r': 0.0}  # rho < 0
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert adjustments['rho_shift'] == 0.05
    
    def test_rule_3_good_fit_and_stability_encourage_exploration(self):
        """Règle 3: fit > 0.8 ET stability > 0.7 → delta_r *= 1.025"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.8, tension=0.2, fit=0.85, pressure=0.3
        )
        # stability = 0.5 * (0.8 + 0.85) - 0.5 * 0.2 = 0.825 - 0.1 = 0.725 > 0.7
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.5}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert 'delta_r_multiplier' in adjustments
        assert adjustments['delta_r_multiplier'] == 1.025  # 1.0 + 0.05 * 0.5
        assert 'High fit' in adjustments['reason']
    
    def test_rule_4_very_high_pressure_reduces_load(self):
        """Règle 4: pressure > 0.85 → tau_c *= 0.925, delta_r *= 0.95"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.3, fit=0.5, pressure=0.90
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.5}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert 'tau_c_multiplier' in adjustments
        assert adjustments['tau_c_multiplier'] == 0.925  # 1.0 - 0.05 * 1.5
        assert 'delta_r_multiplier' in adjustments
        assert adjustments['delta_r_multiplier'] == 0.95
        assert 'Very high pressure' in adjustments['reason']
    
    def test_rule_5_long_session_stable_tension_no_adjustment(self):
        """Règle 5: session > 30 msgs + tension [0.4, 0.6] → None"""
        adaptive = AdaptiveConsciousness(level=2)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.50, fit=0.5, pressure=0.3
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(
            metrics, profile, session_length=35
        )
        
        assert adjustments is None


class TestMultipleRulesTrigger:
    """Tests quand plusieurs règles se déclenchent"""
    
    def test_high_tension_and_low_coherence(self):
        """Vérifier combinaison tension élevée + cohérence basse"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.2, tension=0.80, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.3, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        assert 'tau_c_multiplier' in adjustments
        assert 'rho_shift' in adjustments
        assert 'High tension' in adjustments['reason']
        assert 'Low coherence' in adjustments['reason']
    
    def test_high_pressure_and_high_tension(self):
        """Vérifier combinaison pression + tension très élevées"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.80, fit=0.5, pressure=0.90
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.5}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert adjustments is not None
        # tau_c affecté par règle 1 + 4 → devrait être <= 0.927
        assert adjustments['tau_c_multiplier'] <= 0.9275
        assert 'delta_r_multiplier' in adjustments


class TestBoundsEnforcement:
    """Tests enforcement des bornes de paramètres"""
    
    def test_tau_c_lower_bound(self):
        """tau_c doit rester >= 0.5"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 0.6, 'rho': 0.0, 'delta_r': 0.0}
        adjustments = {'tau_c_multiplier': 0.5}  # Très agressif
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert result['tau_c'] == 0.5  # Enforced lower bound
    
    def test_tau_c_upper_bound(self):
        """tau_c doit rester <= 2.0"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.5, 'rho': 0.0, 'delta_r': 0.0}
        adjustments = {'tau_c_multiplier': 2.0}  # Dépasse bound
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert result['tau_c'] == 2.0  # Enforced upper bound
    
    def test_rho_bounds(self):
        """rho doit rester dans [-1, 1]"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.0, 'rho': 0.9, 'delta_r': 0.0}
        adjustments = {'rho_shift': 0.5}  # Dépasse bound
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert result['rho'] == 1.0  # Clamped
    
    def test_delta_r_bounds(self):
        """delta_r doit rester dans [-1, 1]"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.0, 'rho': 0.0, 'delta_r': 0.8}
        adjustments = {'delta_r_multiplier': 2.0}  # Dépasse bound
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert result['delta_r'] == 1.0  # Clamped


class TestAdjustmentApplication:
    """Tests application des ajustements"""
    
    def test_apply_tau_c_multiplier(self):
        """Vérifier application correcte multiplicateur tau_c"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.1}
        adjustments = {'tau_c_multiplier': 0.95}
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert abs(result['tau_c'] - 0.95) < 0.001
        assert result['rho'] == 0.2  # Inchangé
        assert result['delta_r'] == 0.1  # Inchangé
    
    def test_apply_rho_shift(self):
        """Vérifier application correcte shift rho"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.0, 'rho': 0.5, 'delta_r': 0.0}
        adjustments = {'rho_shift': -0.05}
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert abs(result['rho'] - 0.45) < 0.001
        assert result['tau_c'] == 1.0  # Inchangé
    
    def test_apply_multiple_adjustments(self):
        """Vérifier application simultanée multiplicateurs"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {'tau_c': 1.0, 'rho': 0.3, 'delta_r': 0.5}
        adjustments = {
            'tau_c_multiplier': 0.95,
            'rho_shift': -0.05,
            'delta_r_multiplier': 0.95
        }
        
        result = adaptive.apply_adjustments(current, adjustments)
        assert abs(result['tau_c'] - 0.95) < 0.001
        assert abs(result['rho'] - 0.25) < 0.001
        assert abs(result['delta_r'] - 0.475) < 0.001


class TestSerializationAndMetadata:
    """Tests sérialisation et métadonnées"""
    
    def test_adjustments_include_reason(self):
        """Vérifier que suggestions incluent raison"""
        adaptive = AdaptiveConsciousness(level=2)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.80, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert 'reason' in adjustments
        assert isinstance(adjustments['reason'], str)
        assert len(adjustments['reason']) > 0
    
    def test_adjustments_include_triggered_by(self):
        """Vérifier que suggestions incluent métriques"""
        adaptive = AdaptiveConsciousness(level=2)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.80, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        assert 'triggered_by' in adjustments
        assert adjustments['triggered_by']['tension'] == 0.80
        assert adjustments['triggered_by']['coherence'] == 0.5


class TestEdgeCases:
    """Tests cas limites"""
    
    def test_no_profile_supplied_uses_defaults(self):
        """Si profil incomplet, utiliser defaults"""
        adaptive = AdaptiveConsciousness(level=2)
        current = {}  # Vide
        adjustments = {'tau_c_multiplier': 0.95}
        
        result = adaptive.apply_adjustments(current, adjustments)
        # Doit utiliser tau_c default = 1.0
        assert abs(result['tau_c'] - 0.95) < 0.001
    
    def test_zero_adaptation_rate(self):
        """Vérifier comportement avec taux 0%"""
        adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.0)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.80, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        adjustments = adaptive.suggest_adjustments(metrics, profile)
        
        # Doit quand même suggérer avec multiplicateur 1.0 (no change)
        assert adjustments is not None
        assert adjustments['tau_c_multiplier'] == 1.0
    
    def test_long_session_high_tension_overrides_rule5(self):
        """Règle 5 ne s'active que si tension vraiment stable"""
        adaptive = AdaptiveConsciousness(level=2)
        metrics = ConsciousnessMetrics(
            coherence=0.5, tension=0.7501, fit=0.5, pressure=0.5
        )
        profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
        # tension > 0.75, donc Règle 1 doit s'activer même avec Règle 5
        adjustments = adaptive.suggest_adjustments(
            metrics, profile, session_length=35
        )
        
        # Règle 1 doit s'activer (tension > 0.75)
        assert adjustments is not None
        assert 'High tension' in adjustments['reason']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
