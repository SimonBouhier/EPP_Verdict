# SHIM_FINDINGS — journal de la frontière d'erreurs du client personnel

Alimenté automatiquement par `client/` (shim conversationnel + graph view).
Règle de triage (handoff) : findings **sur le chemin d'appel du shim**
(extraction → pipeline → consensus_engine → crystallization → graphe)
corrigés au fil du besoin réel, RED→GREEN ; findings **hors chemin**
tagués `[deferred]`, sans correction.

Findings pré-connus (audit esmm, session 2026-07-05) :
- `[on-path]` `consensus_engine._get_relation_synonyms` : défaut
  `use_legacy_relation_groups=True` (legacy) alors que le commentaire du
  fallback dit « use new » ; fallback `except Exception: pass` silencieux.
  Sera exercé dès la première escalade.
- `[deferred]` ~90 `except Exception` dans services/esmm hors chemin immédiat
  du shim — voir audit esmm, triage à l'usage.

| horodatage | opération | chemin de code | contexte |
|---|---|---|---|
| 2026-07-05T17:45:29 | graph_view.config | engine:<module>:17 | ModuleNotFoundError: No module named 'aiosqlite' |
