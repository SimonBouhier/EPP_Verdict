"""ADR-012 : Registre des adaptateurs sources autoritaires."""
from services.sources.adapters.base import SourceAdapter
from services.sources.adapters.opensanctions import OpenSanctionsAdapter
from services.sources.adapters.ofac import OfacAdapter
from services.sources.adapters.eu_cfsp import EuCfspAdapter
from services.sources.adapters.verra_vcs import VerraVcsAdapter
from services.sources.adapters.acled import ACLEDAdapter  # ADR-016
from services.sources.adapters.wikidata import WikidataAdapter  # ADR-016

_REGISTRY: dict[str, type[SourceAdapter]] = {
    "opensanctions": OpenSanctionsAdapter,
    "ofac_sdn": OfacAdapter,
    "eu_cfsp": EuCfspAdapter,
    "verra_vcs": VerraVcsAdapter,
    "acled_events": ACLEDAdapter,   # ADR-016 — événements de conflit
    "acled_cast": ACLEDAdapter,     # ADR-016 — prédictions CAST
    "wikidata": WikidataAdapter,    # ADR-016 — faits vérifiables CC-0
}


def get_adapter(source_id: str) -> SourceAdapter:
    """
    Retourne une instance de l'adaptateur correspondant à source_id.
    Lève ValueError si source_id inconnu.
    """
    cls = _REGISTRY.get(source_id)
    if cls is None:
        raise ValueError(
            f"Unknown source_id: {source_id!r}. Available: {sorted(_REGISTRY)}"
        )
    return cls()


def register_adapter(source_id: str, cls: type[SourceAdapter]) -> None:
    """Enregistre un adaptateur supplémentaire (étapes 5-6)."""
    _REGISTRY[source_id] = cls
