"""
Client personnel EPP — shim conversationnel + visualisation (v0).

Frontière stricte : ce paquet importe `services/` et `database/`,
jamais l'inverse. Aucun module de `services/` ne doit importer `client/`.

Régime : usage personnel, local uniquement (nœud ADR-017 n°1).
Aucun chemin d'ancrage on-chain ici.
"""

__all__ = ["shim", "graph_view", "findings"]
