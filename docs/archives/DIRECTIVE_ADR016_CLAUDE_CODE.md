# DIRECTIVE ADR-016 — Oracle Géopolitique

Baseline : 791 passed, 14 skipped, 0 failed.
Ordre : Lot 1 → 2 → 3 → 4 → 5 → 6 (adapter + infra + tests AVANT le script)

Voir ADR-016.md dans la base de connaissance du projet pour le contexte complet.

## Lot 1 — ACLEDAdapter (services/sources/adapters/acled.py)

Créer en suivant le pattern EXACT des adaptateurs existants. Hérite SourceAdapter.
Deux modes via query["mode"] : "events" (GET /api/acled/read) et "forecast" (GET /api/cast/read).
Auth OAuth2 : POST https://acleddata.com/oauth/token → bearer token 24h caché en mémoire.
Credentials env vars : ACLED_EMAIL + ACLED_PASSWORD.
Si absents → ValueError explicite dans fetch().
normalize() events → {status, score (min(1.0, count/500)), event_count, fatalities, event_types dict}.
normalize() forecast → {status: "forecast", predictions: [...], periods: int}.
get_source_version() → date du dernier événement.

## Lot 2 — Registre (services/sources/adapters/__init__.py)

LIRE le fichier d'abord. Ajouter ACLEDAdapter avec deux clés : "acled_events" et "acled_cast".
VÉRIFIER que source_anchor_builder.py importe depuis services.sources.adapters (pas services.rwa).

## Lot 3 — Frame (services/solana/metrological_frame.py)

Ajouter geopolitical_forecast_v1.0 dans PREDEFINED_FRAMES.
domain="geopolitical_analysis", metric="conflict_forecast_assessment",
parameters : authoritative_sources=["acled_events","acled_cast"], esmm_bypass=False.

## Lot 4 — config.yaml

Section geopolitical : acled_email_env, acled_password_env, default_limit=500.

## Lot 5 — Tests (tests/test_adr016_acled.py)

6 tests minimum, tous sans connexion ACLED (mock responses) :
1. normalize events mock → score correct
2. normalize vide → no_data
3. normalize forecast mock → status forecast
4. fetch sans credentials → ValueError
5. get_adapter("acled_events") → ACLEDAdapter
6. geopolitical_forecast_v1.0 dans PREDEFINED_FRAMES

APRÈS lots 1-5 : pytest + greps. Montre-moi les résultats AVANT le lot 6.

## Lot 6 — scenario_jiang.py (demos/)

Copier scenario_6_1_edge_cases.py comme template. Remplacer CLAIMS par le
catalogue Jiang (8 claims — voir ADR-016.md). Deux passes par claim :
1. VERIFY standard (toujours exécutée)
2. Déterministe ACLED via SourceAnchorSpec + ClaimNature.DETERMINISTIC
   (exécutée SEULEMENT si ACLED_EMAIL est setté — sinon skip avec log)

DB temporaires par claim. JSON horodaté dans demos/benchmark_runs/.
Le script DOIT fonctionner en mode VERIFY-only si ACLED inaccessible.
