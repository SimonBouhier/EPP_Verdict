# DIRECTIVE — Corrections ADR-018 Flywheel Épistémique

**Date** : 2026-03-13
**Émetteur** : Claude Opus (Auditeur Adversarial)
**Destinataire** : Claude Code (Implémenteur)
**Contexte** : L'ADR-018 contient des bugs de conception identifiés par audit. Cette directive contient 3 parties séquentielles. **NE PAS commencer la Partie 3 avant d'avoir terminé et rapporté les résultats de la Partie 2.**

---

## PARTIE 1 — Bug confirmé B1 (correction obligatoire dans l'ADR)

### Problème

La fonction `_lookup_existing_anchors()` dans ADR-018 §2.2 cherche par `claim_hash` :

```sql
WHERE claim_hash = ?
  AND json_extract(consensus_meta, '$.methodology.claim_nature') = 'deterministic'
```

C'est un bug de logique garanti. Voici pourquoi :

`compute_claim_hash()` produit un hash à partir de `(subject, predicate, object_, metrological_frame)`. Pour le même fait réel ("Donald Trump won the 2024 US presidential election") :

- **Chemin DETERMINISTIC** (Wikidata) : `subject="Donald Trump"`, `predicate=frame.metric` (ex: `"factual_accuracy"`), `object_="found"` → **Hash A**
- **Chemin VERIFY** (LLMs) : `subject` extrait par les LLMs, `predicate="verdict"`, `object_="SUPPORTED"` → **Hash B**

**Hash A ≠ Hash B. Toujours. Structurellement.** Le flywheel ne trouvera jamais rien.

### Correction

Le dénominateur commun entre les deux chemins est la **question originale** (le texte soumis au pipeline). Le lookup doit chercher par `question`, exactement comme le fait `_check_cache()` (ADR-013).

**Modifier ADR-018 §2.2** — remplacer le lookup par :

```python
async def _lookup_existing_anchors(
    question: str,
    db: "ISpaceDB",
) -> list[dict]:
    """
    Cherche les attestations déterministes existantes pour une question donnée.
    """
    rows = await db.get_attestations_by_question(
        question=question,
        min_consensus=0.0,  # On veut TOUTES les attestations déterministes
    )

    anchors = []
    for row in rows:
        meta = row.get("consensus_meta", {})
        if isinstance(meta, str):
            import json
            meta = json.loads(meta)

        methodology = meta.get("methodology", {})
        # Filtre : uniquement les attestations déterministes
        if methodology.get("consensus_method") != "deterministic_source_v1":
            continue

        source_meta = meta.get("source_anchor_meta", {})
        diagnostics = meta.get("diagnostics", {})

        anchors.append({
            "source_id": source_meta.get("source_id", "unknown"),
            "score": row.get("consensus_score", 0.0),
            "status": diagnostics.get("result", "unknown"),
            "fetched_at": source_meta.get("fetched_at", row.get("timestamp", 0)),
            "source_version": source_meta.get("source_version", "unknown"),
        })

    return anchors
```

**Points clés du fix :**
1. Lookup par `question` via `get_attestations_by_question()` (méthode existante, ADR-013)
2. Filtre post-query sur `consensus_method == "deterministic_source_v1"` (pas de `json_extract` SQL)
3. Lit `diagnostics.result` pour le statut (pas `source_anchor_meta.normalized` qui n'existe pas)
4. Lit `consensus_score` depuis la row (pas depuis `source_anchor_meta`)

---

## PARTIE 2 — Diagnostic avant implémentation

**INSTRUCTION : Exécuter ces 5 vérifications et rapporter les résultats EXACTS (sortie terminal complète) AVANT de toucher au moindre fichier.**

### D1 — La colonne `question` est-elle peuplée pour le chemin déterministe ?

```bash
grep -n "question" services/esmm/attestation.py | head -20
grep -n "store_attestation" database/engine.py | head -10
grep -n "question" database/schema.sql | head -10
```

**Ce qu'on cherche** : Est-ce que `crystallize()` accepte un paramètre `question` ? Est-ce que `store_attestation()` écrit la question dans la colonne `question` de la table `attestations` ? Si non, le fix B1 ne suffit pas — il faudra aussi s'assurer que le chemin déterministe dans `_run_deterministic_pipeline()` passe la question à la DB.

### D2 — Structure réelle de `consensus_meta` pour les attestations déterministes

```bash
grep -n "source_anchor_meta\|normalized_result\|diagnostics" services/esmm/pipeline.py | head -20
```

**Ce qu'on cherche** : Confirmer que `consensus_meta` pour le chemin déterministe contient `source_anchor_meta` et `diagnostics` mais PAS de clé `normalized` (confirmant le bug B2 de l'ADR original). Vérifier si `normalized_result` de `anchor_result` est accessible quelque part.

### D3 — Comment le `system_prompt` arrive aux LLMs

```bash
grep -n "system_prompt" services/esmm/cycle_manager.py | head -20
grep -n "def _query_models\b" services/esmm/cycle_manager.py
grep -n "def execute_cycle" services/esmm/cycle_manager.py
```

**Ce qu'on cherche** : Le chemin exact `get_system_prompt(cycle_type)` → `_query_models(question, cycle_type, timeout)` → `batch_sequential_providers(..., system_prompt=...)`. On a besoin de savoir où concaténer `anchor_context` au `system_prompt`.

### D4 — Comment `execute_cycles` passe le contexte aux cycles

```bash
grep -n "cycle_context\|anchor_context\|flywheel" services/esmm/orchestrator.py | head -20
```

**Ce qu'on cherche** : Confirmer que `cycle_context` est un dict libre passé à `execute_cycle()`, et qu'on peut y ajouter une clé `anchor_context` sans casser l'API existante.

### D5 — La méthode `get_attestations_by_question` existe et fonctionne

```bash
grep -n "get_attestations_by_question" database/engine.py | head -10
grep -n "def get_attestations_by_question" database/engine.py
```

**Ce qu'on cherche** : Confirmer que cette méthode existe (ADR-013), sa signature, et qu'elle retourne bien des dicts avec les clés `consensus_meta`, `consensus_score`, `timestamp`.

---

## PARTIE 3 — Implémentation Lot 1 (après validation Partie 2)

**NE PAS COMMENCER AVANT QUE SIMON AIT VALIDÉ LES RÉSULTATS DE PARTIE 2.**

### 3.1 — `_lookup_existing_anchors()` dans `pipeline.py`

Ajouter la fonction corrigée (voir Partie 1) après `_check_cache()` et avant `run_pipeline()`.

**VÉRIFICATION** :
```bash
grep -n "_lookup_existing_anchors" services/esmm/pipeline.py
```

### 3.2 — `_format_anchor_context()` dans `pipeline.py`

```python
def _format_anchor_context(anchors: list[dict]) -> str:
    """Formate les ancres déterministes pour injection dans le prompt LLM."""
    if not anchors:
        return ""

    lines = ["[VERIFIED DATA — from deterministic sources, for context]"]
    for a in anchors:
        lines.append(
            f"- Source: {a['source_id']} | Status: {a['status']} | "
            f"Score: {a['score']} | "
            f"Fetched: {a['fetched_at']} | Version: {a['source_version']}"
        )
    lines.append("[END VERIFIED DATA — you may contest these findings if your analysis disagrees]")
    return "\n".join(lines)
```

**VÉRIFICATION** :
```bash
grep -n "_format_anchor_context" services/esmm/pipeline.py
```

### 3.3 — Point d'injection dans `run_pipeline()`

Dans `run_pipeline()`, **APRÈS** le check déterministe (ADR-012 bypass) et **AVANT** l'appel à `_extract_triplets_from_question()` :

```python
# --- ADR-018 Flywheel: lookup existing deterministic anchors ---
flywheel_injection = ""
try:
    from services.config_loader import get_section
    flywheel_cfg = get_section("flywheel", {})
    if flywheel_cfg.get("enabled", True):
        anchors = await _lookup_existing_anchors(question, db)
        flywheel_injection = _format_anchor_context(anchors)
        if flywheel_injection:
            logger.info(
                "[Pipeline] Flywheel: %d deterministic anchor(s) found",
                len(anchors),
            )
except Exception as exc:
    logger.warning("[Pipeline] Flywheel lookup failed (continuing): %s", exc)
```

Puis passer `flywheel_injection` à `_extract_triplets_from_question()` via un nouveau paramètre optionnel `anchor_context`.

**VÉRIFICATION** :
```bash
grep -n "flywheel" services/esmm/pipeline.py
```

### 3.4 — Threading du `anchor_context` : pipeline → orchestrator → cycle_manager

Le chemin du contexte (4 frontières — ATTENTION) :

1. **`_extract_triplets_from_question()`** : ajouter paramètre `anchor_context: str = ""`
2. **`ESMMRunConfig`** (ou `ESMMOrchestrator.__init__`) : stocker `anchor_context`
3. **`execute_cycles()`** → injecter dans `cycle_context["anchor_context"]`
4. **`cycle_manager._query_models()`** → concaténer au `system_prompt` :

```python
system_prompt = get_system_prompt(cycle_type)
# ADR-018: Flywheel injection
anchor_ctx = context.get("anchor_context", "") if context else ""
if anchor_ctx:
    system_prompt = system_prompt + "\n\n" + anchor_ctx
```

**CHOIX ARCHITECTURAL** : Le point d'injection le plus propre est probablement de passer `anchor_context` via `ESMMRunConfig` (il arrive déjà dans l'orchestrateur). C'est à toi de décider le chemin le plus minimal — mais les 4 points listés ci-dessus doivent tous être touchés.

**VÉRIFICATION CRITIQUE (P3 — Fantôme)** :
```bash
grep -rn "anchor_context" services/esmm/ --include="*.py"
```
Doit retourner des hits dans **pipeline.py**, **orchestrator.py** ET **cycle_manager.py**. Si l'un manque, le threading est cassé.

### 3.5 — Traçabilité dans `consensus_meta`

Dans `_build_consensus_meta()` ou dans `run_pipeline()` après la construction de `consensus_meta`, ajouter :

```python
# ADR-018: Flywheel traceability
if flywheel_injection:
    consensus_meta["methodology"]["flywheel"] = {
        "enabled": True,
        "anchors_found": len(anchors),
        "sources_injected": [a["source_id"] for a in anchors],
    }
else:
    consensus_meta["methodology"]["flywheel"] = {
        "enabled": flywheel_cfg.get("enabled", True) if 'flywheel_cfg' in dir() else False,
        "anchors_found": 0,
        "sources_injected": [],
    }
```

**VÉRIFICATION** :
```bash
grep -n "flywheel" services/esmm/pipeline.py
```

### 3.6 — `config.yaml`

Ajouter à la racine du fichier :

```yaml
flywheel:
  enabled: true
```

**VÉRIFICATION** :
```bash
grep -n "flywheel" config.yaml
```

### 3.7 — Tests RED-GREEN-FIX

Fichier : `tests/test_adr018_flywheel.py`

**Tests requis** (minimum 4) :

1. **`test_lookup_no_anchors`** — Question sans attestation déterministe → retourne `[]`
2. **`test_lookup_with_deterministic_anchor`** — Question avec une attestation déterministe en DB → retourne 1 ancre avec les bons champs
3. **`test_format_anchor_context_empty`** — `_format_anchor_context([])` → retourne `""`
4. **`test_format_anchor_context_with_data`** — `_format_anchor_context([...])` → contient `[VERIFIED DATA`, source_id, score
5. **`test_consensus_meta_flywheel_traceability`** — Après un run avec flywheel, `consensus_meta.methodology.flywheel` est présent
6. **`test_flywheel_disabled`** — `config flywheel.enabled: false` → aucun lookup, pas de clé flywheel dans consensus_meta

**PROTOCOLE RED-GREEN-FIX** :
- Écrire les tests AVANT l'implémentation
- Montrer le log pytest où ils ÉCHOUENT (RED)
- Implémenter
- Montrer le log pytest où ils PASSENT (GREEN)
- Lancer `pytest tests/` complet (FIX — zéro régression)

**VÉRIFICATION FINALE** :
```bash
pytest tests/test_adr018_flywheel.py -v
pytest tests/ --tb=short -q
```

---

## RÉCAPITULATIF DES RISQUES

| ID | Bug | Sévérité | Statut |
|:---|:---|:---|:---|
| B1 | Lookup par `claim_hash` impossible | 🔴 Confirmé | Fix dans Partie 1 |
| B2 | Champs `normalized` absents dans `consensus_meta` | 🔴 Probable | Diagnostic D2 |
| B3 | Sous-estimation scope (4 fichiers, pas 1) | 🟠 Confirmé | Détaillé §3.4 |
| B4 | `question` non stockée pour chemin déterministe | 🟠 À vérifier | Diagnostic D1 |
| B5 | Pas de TTL minimal sur les ancres | 🟡 Accepté hackathon | Post-hackathon |

---

*Fin de directive. Attendre validation Simon après Partie 2 avant Partie 3.*
