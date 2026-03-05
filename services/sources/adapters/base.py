"""ADR-012 : Interface commune des adaptateurs sources autoritaires."""
from abc import ABC, abstractmethod
from typing import Any, Dict


class SourceAdapter(ABC):
    """Interface que tout adaptateur RWA doit implémenter. Zéro logique métier."""

    @abstractmethod
    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Interroge la source externe. Retourne la réponse brute (JSON)."""
        ...

    @abstractmethod
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise la réponse brute vers le format commun.
        Retour attendu : {"status": "clear"|"match", "score": float}
        """
        ...

    @abstractmethod
    def get_source_version(self, raw: Dict[str, Any]) -> str:
        """
        Extrait la version de la source depuis la réponse brute.
        Chaque adaptateur lit le champ approprié dans raw.
        """
        ...
