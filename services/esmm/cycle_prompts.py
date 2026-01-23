"""
ESMM Phase 3 - CYCLE PROMPTS
============================

Templates de questions pour les trois types de cycles d'exploration.
Chaque type de cycle a des objectifs différents:
- DIVERGENT: Exploration large, découverte de relations
- DEBATE: Dialectique, synthèse de contradictions
- META: Réflexion sur connaissances extraites, détection lacunes

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

from typing import Dict, List
from enum import Enum


class CycleType(str, Enum):
    """Types de cycles d'exploration."""
    DIVERGENT = "divergent"   # Exploration large depuis concepts seed
    DEBATE = "debate"         # Dialectique sur contradictions
    META = "meta"             # Réflexion sur connaissances extraites


# ============================================================================
# TEMPLATES DIVERGENT - Exploration large
# ============================================================================

DIVERGENT_TEMPLATES: List[str] = [
    # Relations fondamentales
    "Quelles sont les relations fondamentales entre {concept} et d'autres concepts? "
    "Liste les connexions causales, hiérarchiques et associatives.",

    # Propriétés essentielles
    "Décris les propriétés essentielles de {concept}. "
    "Quels attributs le caractérisent et le distinguent?",

    # Causalité
    "Quels concepts sont causalement liés à {concept}? "
    "Identifie les causes et les effets directs.",

    # Taxonomie
    "Comment {concept} s'inscrit-il dans une taxonomie? "
    "Quels sont ses hyperonymes, hyponymes et concepts frères?",

    # Contexte d'usage
    "Dans quels domaines et contextes {concept} est-il pertinent? "
    "Quelles relations le lient à ces domaines?",

    # Analogies
    "Quels concepts sont analogues ou similaires à {concept}? "
    "Explique les bases de ces similarités.",

    # Composants
    "De quoi {concept} est-il composé? Quels sont ses constituants "
    "et comment interagissent-ils?",

    # Fonctions
    "Quelles fonctions ou rôles {concept} remplit-il? "
    "Dans quels processus est-il impliqué?",
]


# ============================================================================
# TEMPLATES DEBATE - Dialectique
# ============================================================================

DEBATE_TEMPLATES: List[str] = [
    # Thesis/Antithesis classique
    "Compare et contraste {thesis} avec {antithesis}. "
    "Quelles sont leurs relations, tensions et complémentarités?",

    # Synthèse
    "Y a-t-il une synthèse possible entre {concept_a} et {concept_b}? "
    "Comment réconcilier ces perspectives apparemment opposées?",

    # Limites mutuelles
    "Quelles sont les limites de {thesis} que {antithesis} révèle, "
    "et vice-versa? Explore les angles morts de chaque concept.",

    # Contextes de validité
    "Dans quels contextes {thesis} est-il plus approprié que {antithesis}, "
    "et inversement? Identifie les conditions de validité de chacun.",

    # Évolution historique
    "Comment la relation entre {concept_a} et {concept_b} a-t-elle évolué? "
    "Y a-t-il eu des inversions de perspective?",

    # Médiation
    "Quels concepts peuvent servir de médiateurs entre {thesis} et {antithesis}? "
    "Identifie les ponts conceptuels possibles.",
]


# ============================================================================
# TEMPLATES META - Réflexion
# ============================================================================

META_TEMPLATES: List[str] = [
    # Analyse de lacunes
    "En analysant ces relations: {recent_triplets}, quelles lacunes identifies-tu? "
    "Quels concepts ou relations manquent pour compléter ce réseau?",

    # Concepts fondamentaux manquants
    "Quels concepts fondamentaux manquent pour comprendre {domain}? "
    "Identifie les présupposés implicites non explorés.",

    # Cohérence du réseau
    "Le réseau de connaissances suivant est-il cohérent: {recent_triplets}? "
    "Y a-t-il des contradictions ou des incohérences?",

    # Généralisations possibles
    "À partir de ces relations: {recent_triplets}, quelles généralisations "
    "ou patterns peux-tu identifier?",

    # Questions ouvertes
    "Quelles questions importantes restent sans réponse dans ce domaine: {domain}? "
    "Identifie les zones d'incertitude.",

    # Connexions manquantes
    "Quels liens entre domaines distincts manquent dans: {recent_triplets}? "
    "Y a-t-il des ponts interdisciplinaires à établir?",
]


# ============================================================================
# MAPPING PAR TYPE DE CYCLE
# ============================================================================

CYCLE_TEMPLATES: Dict[CycleType, List[str]] = {
    CycleType.DIVERGENT: DIVERGENT_TEMPLATES,
    CycleType.DEBATE: DEBATE_TEMPLATES,
    CycleType.META: META_TEMPLATES,
}


# ============================================================================
# SYSTEM PROMPTS PAR TYPE
# ============================================================================

SYSTEM_PROMPTS: Dict[CycleType, str] = {
    CycleType.DIVERGENT: """Tu es un expert en analyse conceptuelle. Ta tâche est d'explorer
les relations sémantiques autour d'un concept donné. Identifie les relations de type:
- Causalité (cause, effet, permet, empêche)
- Hiérarchie (est_un, partie_de, contient)
- Association (lié_à, similaire_à, contraire_de)
- Propriété (a_pour_propriété, caractérisé_par)

Réponds de manière structurée en listant les triplets (sujet, relation, objet).""",

    CycleType.DEBATE: """Tu es un dialecticien expert. Ta tâche est d'analyser les tensions
et complémentarités entre concepts apparemment opposés. Pour chaque paire:
- Identifie les points de tension
- Trouve les complémentarités
- Propose des synthèses ou médiations
- Extrais les relations qui émergent de cette dialectique

Réponds en listant les triplets (sujet, relation, objet) qui capturent ces dynamiques.""",

    CycleType.META: """Tu es un épistémologue. Ta tâche est d'analyser un réseau de
connaissances pour identifier:
- Les lacunes conceptuelles
- Les présupposés implicites
- Les connexions manquantes
- Les incohérences potentielles

Propose des triplets (sujet, relation, objet) qui combleraient ces lacunes.""",
}


# ============================================================================
# HELPERS
# ============================================================================

def get_template(cycle_type: CycleType, index: int = 0) -> str:
    """
    Récupère un template pour un type de cycle donné.

    Args:
        cycle_type: Type de cycle (DIVERGENT, DEBATE, META)
        index: Index du template (sera modulé par le nombre de templates)

    Returns:
        Template de question
    """
    templates = CYCLE_TEMPLATES[cycle_type]
    return templates[index % len(templates)]


def get_system_prompt(cycle_type: CycleType) -> str:
    """
    Récupère le system prompt pour un type de cycle.

    Args:
        cycle_type: Type de cycle

    Returns:
        System prompt approprié
    """
    return SYSTEM_PROMPTS[cycle_type]


def format_triplets_for_prompt(triplets: List) -> str:
    """
    Formate une liste de triplets pour insertion dans un prompt.

    Args:
        triplets: Liste de triplets (objets avec subject, relation, object)

    Returns:
        Chaîne formatée "subject→relation→object; ..."
    """
    formatted = []
    for t in triplets[:10]:  # Limite à 10 pour éviter prompts trop longs
        subject = getattr(t, 'subject', t.get('subject', '?'))
        relation = getattr(t, 'relation', t.get('relation', '?'))
        obj = getattr(t, 'object', t.get('object', '?'))
        formatted.append(f"{subject}→{relation}→{obj}")
    return "; ".join(formatted)


def get_template_count(cycle_type: CycleType) -> int:
    """
    Retourne le nombre de templates disponibles pour un type de cycle.

    Args:
        cycle_type: Type de cycle

    Returns:
        Nombre de templates
    """
    return len(CYCLE_TEMPLATES[cycle_type])
