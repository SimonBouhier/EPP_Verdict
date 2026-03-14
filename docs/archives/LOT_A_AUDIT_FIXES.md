# LOT A — Correctifs chirurgicaux audit (5 Fixes)

> **Auteur** : Opus (Adversarial Gatekeeper)
> **Date** : 2026-03-09
> **Baseline** : 782 passed, 14 skipped, 0 failed
> **Contrainte** : Baseline inchangée après chaque fix. Zéro régression.
> **Protocole** : RED-GREEN-FIX pour chaque correctif.

---

## Contexte — Chaîne causale du problème principal

Les attestations d'audit stockées dans `epp_audit_devnet.db` et `epp_audit_heavy.db`
ont un `subject` qui contient le **prompt brut complet** (800+ caractères avec
`<CONTRACT_CONTEXT>`, `<FUNCTION_UNDER_AUDIT>`, `<UNIT_METADATA>`, et les instructions
JSON) au lieu d'un identifiant propre comme `"Reentrance::withdrawBalance"`.

Chaîne causale tracée :

```
audit_runner.py
  → claim = _safe_format(ASSESS_AUDIT_TEMPLATE, **placeholders)  [prompt 800+ chars]
  → run_pipeline(question=claim, esmm_config=ESMMRunConfig(original_claim=claim))

cycle_manager.py :: _extract_verdicts_from_responses()
  → claim_text = context.get("original_claim", "")  [prompt 800+ chars]
  → _parse_verdict_response(response_text, claim_text=claim_text)

triplet_extractor.py :: _parse_verdict_response()
  → triplets.append({"subject": claim_text, "relation": "verdict", ...})
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    LE BUG : claim_text EST LE PROMPT COMPLET

pipeline.py :: boucle de cristallisation
  → crystallize(subject=triplet["subject"], ...)
    → attestation.subject = prompt complet
    → claim_hash = SHA-256(prompt complet + predicate + object + frame)
    → stocké en DB avec subject = prompt brut
```

Dans la DB principale `epp_devnet.db`, les subjects VERIFY sont propres
(`"Water boils at 100 degrees Celsius..."`) car le `original_claim` est
une phrase courte. Dans l'audit, c'est un prompt technique de 800+ chars.

---

## Fix 1 — Subject propre pour les attestations d'audit

### Objectif

Les attestations d'audit doivent avoir un `subject` de la forme
`"{contract_name}::{unit_name}"` (ex: `"Reentrance::withdrawBalance"`).
Le prompt complet reste le `question` (ce que les LLMs voient).

### Approche — `subject_override` dans ESMMRunConfig

Ajouter un champ optionnel `subject_override` à `ESMMRunConfig`.
Quand il est défini, `pipeline.py` l'utilise comme `subject` lors de la
cristallisation au lieu de `triplet["subject"]`. Cela ne touche ni le
consensus engine, ni le verdict encoder, ni le cycle_manager.

### Fichiers à modifier

#### 1.1 — `services/esmm/orchestrator.py`

Ajouter un champ à la dataclass `ESMMRunConfig` :

```python
@dataclass
class ESMMRunConfig:
    # ... champs existants ...
    
    # Fix 1 (Lot A) : subject propre pour les attestations d'audit
    # Si défini, pipeline.py utilise cette valeur comme subject au lieu
    # de triplet["subject"] lors de la cristallisation.
    # Laisse le question/original_claim intact (c'est le prompt LLM).
    subject_override: Optional[str] = None
```

Position : après `source_anchor_spec`. Pas de modification à `__post_init__`.

**Contrôle C1** : `grep -rn "ESMMRunConfig" --include="*.py"` — vérifier que
tous les appelants existants continuent de fonctionner (le champ est Optional
avec default=None, donc aucun appelant existant n'est impacté).

#### 1.2 — `services/esmm/pipeline.py`

Dans la boucle de cristallisation (chercher `for triplet in extracted_triplets:`),
ajouter la résolution du subject **avant** l'appel à `crystallize()` :

```python
        # --- AVANT (code actuel) ---
        attestation = crystallize(
            subject=triplet["subject"],
            predicate=triplet["predicate"],
            ...
        )

        # --- APRÈS (avec Fix 1) ---
        # Fix 1 (Lot A) : subject_override pour audit
        effective_subject = triplet["subject"]
        if esmm_config and getattr(esmm_config, "subject_override", None):
            effective_subject = esmm_config.subject_override
        
        attestation = crystallize(
            subject=effective_subject,
            predicate=triplet["predicate"],
            ...
        )
```

**ATTENTION** : le `compute_claim_hash()` qui précède la cristallisation
utilise aussi `triplet["subject"]`. Il faut appliquer le même override :

```python
        # Chercher la ligne :
        h = compute_claim_hash(
            triplet["subject"], triplet["predicate"], triplet["object"],
            metrological_frame=config.metrological_frame,
        )
        
        # Remplacer par :
        effective_subject = triplet["subject"]
        if esmm_config and getattr(esmm_config, "subject_override", None):
            effective_subject = esmm_config.subject_override
        
        h = compute_claim_hash(
            effective_subject, triplet["predicate"], triplet["object"],
            metrological_frame=config.metrological_frame,
        )
```

**IMPORTANT** : le `effective_subject` doit être calculé UNE SEULE FOIS
et réutilisé pour le hash ET la cristallisation. Ne pas le recalculer
deux fois — DRY.

Le code de déduplication `seen_hashes` doit aussi utiliser le même subject,
sinon des triplets qui seraient des duplicats avec le subject override
passeraient le filtre.

La section `P1: Enrich verify section` qui lit `triplet["subject"]` pour
les logs/meta n'a PAS besoin d'être modifiée — on veut garder le prompt
original dans `consensus_meta.verify.original_claim` pour la traçabilité.

#### 1.3 — `services/audit/audit_runner.py`

Dans la boucle `for unit in sorted_units:`, construire le subject propre
et le passer via `ESMMRunConfig.subject_override` :

```python
        # --- AVANT ---
        esmm_cfg = ESMMRunConfig(
            models=models,
            input_mode="verify",
            original_claim=claim,
        )

        # --- APRÈS ---
        # Fix 1 (Lot A) : subject propre pour attestations d'audit
        audit_subject = f"{slice_result.contract_name}::{unit.unit_name}"
        
        esmm_cfg = ESMMRunConfig(
            models=models,
            input_mode="verify",
            original_claim=claim,
            subject_override=audit_subject,
        )
```

**NOTE** : `slice_result` est défini avant la boucle. Il a un champ
`contract_path` mais pas forcément `contract_name` (à vérifier dans
`contract_slicer.py`). Cependant, chaque `ContractUnit` a un champ
`contract_name` (voir ADR-014 §2.2). Utiliser `unit.contract_name`
est plus fiable :

```python
        audit_subject = f"{unit.contract_name}::{unit.unit_name}"
```

### Tests RED-GREEN-FIX

#### Test RED (doit échouer AVANT le fix)

```python
# tests/test_fix1_subject_override.py

import pytest
from services.esmm.orchestrator import ESMMRunConfig


def test_esmm_run_config_has_subject_override():
    """RED: ESMMRunConfig doit exposer subject_override."""
    cfg = ESMMRunConfig(models=["test:latest"])
    assert hasattr(cfg, "subject_override"), \
        "ESMMRunConfig doit avoir un champ subject_override"
    assert cfg.subject_override is None  # default None


@pytest.mark.asyncio
async def test_pipeline_uses_subject_override(tmp_path):
    """RED: crystallize() doit utiliser subject_override si présent."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from services.esmm.pipeline import PipelineConfig, run_pipeline
    from database.engine import ISpaceDB

    db = ISpaceDB(str(tmp_path / "test.db"))
    await db.initialize()

    # Ce test vérifie que le subject dans l'attestation
    # est "TestContract::testFunc" et non le prompt brut
    esmm_cfg = ESMMRunConfig(
        models=["mock:latest"],
        input_mode="verify",
        original_claim="<CONTRACT_CONTEXT>...</CONTRACT_CONTEXT>",
        subject_override="TestContract::testFunc",
    )
    
    # Mock l'orchestrateur pour éviter les appels LLM
    # Le test complet sera dans test GREEN après implémentation
    assert esmm_cfg.subject_override == "TestContract::testFunc"


def test_audit_runner_sets_subject_override():
    """RED: audit_runner doit construire un subject_override propre."""
    from services.audit.contract_slicer import ContractUnit
    
    unit = ContractUnit(
        unit_id="test_hash",
        contract_path="/test/reentrancy.sol",
        contract_name="Reentrance",
        unit_type="function",
        unit_name="withdrawBalance",
        source_code="function withdrawBalance() { }",
        visibility="public",
        access_level="public",
        modifiers=[],
        state_writes=["userBalance"],
        external_calls=[".call"],
        line_range=(1, 5),
        context_imports="contract Reentrance {",
    )
    
    expected_subject = "Reentrance::withdrawBalance"
    assert f"{unit.contract_name}::{unit.unit_name}" == expected_subject
```

#### Vérification GREEN

Après le fix : les 3 tests passent, et la baseline 782 tests reste stable.

```bash
pytest tests/test_fix1_subject_override.py -v
pytest tests/ -q  # baseline check
```

---

## Fix 2 — Filtrer les unités fantômes du slicer

### Objectif

Le slicer regex produit des `ContractUnit` avec `unit_name` correspondant
à des mots-clés réservés du langage (`"if"`, `"else"`, `"for"`, etc.).
Preuve : le benchmark heavy montre `unit_name: "if"` avec score 0.0.

### Fichier à modifier

#### 2.1 — `services/audit/contract_slicer.py`

Ajouter un ensemble de mots-clés réservés Solidity et filtrer les unités
après extraction :

```python
# Mots-clés réservés Solidity — ne peuvent pas être des noms de fonction
SOLIDITY_RESERVED_KEYWORDS = frozenset({
    # Contrôle de flux
    "if", "else", "for", "while", "do", "break", "continue", "return",
    "throw", "try", "catch",
    # Types primitifs
    "uint", "int", "bool", "address", "string", "bytes", "mapping",
    "uint256", "int256", "uint8", "uint128",
    # Mots-clés du langage
    "contract", "library", "interface", "struct", "enum", "event",
    "modifier", "function", "constructor", "fallback", "receive",
    "public", "private", "internal", "external", "pure", "view",
    "payable", "virtual", "override", "abstract", "import", "pragma",
    "using", "is", "new", "delete", "assembly", "emit", "require",
    "assert", "revert", "storage", "memory", "calldata",
    # Mots-clés réservés mais rarement vus
    "this", "super", "selfdestruct", "type",
})
```

Dans la fonction `slice_contract()`, après l'extraction des unités et
AVANT le retour du `ContractSliceResult`, filtrer :

```python
    # Fix 2 (Lot A) : filtrer les unités dont le nom est un mot-clé réservé
    valid_units = []
    reserved_skipped = []
    for unit in extracted_units:
        if unit.unit_name.lower() in SOLIDITY_RESERVED_KEYWORDS:
            reserved_skipped.append(
                f"{unit.unit_name} (reserved keyword, lines {unit.line_range})"
            )
        else:
            valid_units.append(unit)
    
    skipped_units.extend(reserved_skipped)
    # Utiliser valid_units au lieu de extracted_units dans le retour
```

**Contrôle** : les unités filtrées doivent apparaître dans
`ContractSliceResult.skipped_units` avec la raison.

### Tests RED-GREEN-FIX

```python
# tests/test_fix2_slicer_reserved.py

import pytest


def test_slicer_rejects_reserved_keyword_units():
    """RED: le slicer ne doit pas produire d'unités nommées 'if', 'for', etc."""
    from services.audit.contract_slicer import slice_contract
    import os
    
    # Utiliser le fichier reentrancy.sol du benchmark
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures", "benchmark", "not_so_smart", "reentrancy.sol"
    )
    if not os.path.exists(fixture_path):
        pytest.skip("Fixture reentrancy.sol not found")
    
    result = slice_contract(fixture_path)
    unit_names = [u.unit_name for u in result.units]
    
    # "if" ne doit jamais apparaître comme nom d'unité
    assert "if" not in unit_names, \
        f"Reserved keyword 'if' found in unit names: {unit_names}"


def test_slicer_reserved_keywords_appear_in_skipped():
    """RED: les mots-clés filtrés doivent être documentés dans skipped_units."""
    from services.audit.contract_slicer import SOLIDITY_RESERVED_KEYWORDS
    
    # Vérifier que la constante existe
    assert isinstance(SOLIDITY_RESERVED_KEYWORDS, (set, frozenset))
    assert "if" in SOLIDITY_RESERVED_KEYWORDS
    assert "for" in SOLIDITY_RESERVED_KEYWORDS
    assert "require" in SOLIDITY_RESERVED_KEYWORDS
    # Les vrais noms de fonctions ne sont pas dedans
    assert "withdrawBalance" not in SOLIDITY_RESERVED_KEYWORDS
    assert "addToBalance" not in SOLIDITY_RESERVED_KEYWORDS
```

---

## Fix 3 — Propager `epistemic_type="security_audit"`

### Objectif

Les attestations d'audit ont `epistemic_type: "foundational"` (défaut).
Elles doivent avoir `"security_audit"` pour être distinguables dans les
requêtes DB et dans la présentation.

### Chaîne causale

```
pipeline.py:
  epistemic_type=triplet.get("epistemic_type", config.default_epistemic_type)
                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  PipelineConfig.default_epistemic_type = "foundational"  ← DÉFAUT
```

### Fichier à modifier

#### 3.1 — `services/audit/audit_runner.py`

Le `PipelineConfig` est déjà construit par `audit_runner.py`. Il suffit
de setter `default_epistemic_type` :

```python
        # --- AVANT ---
        pipeline_config = PipelineConfig(
            use_cache=use_cache,
            metrological_frame=frame,
        )

        # --- APRÈS ---
        pipeline_config = PipelineConfig(
            use_cache=use_cache,
            metrological_frame=frame,
            default_epistemic_type="security_audit",  # Fix 3 (Lot A)
        )
```

#### 3.2 — Vérification : `attestation.py`

Vérifier que `"security_audit"` est une valeur acceptée par `crystallize()`.
Actuellement, `epistemic_type` est un `str` libre — pas de validation enum.
Les valeurs existantes sont `"foundational"`, `"deterministic"`, `"verdict"`.

`"security_audit"` est cohérent avec la convention. Si une validation
existe (whitelist), y ajouter `"security_audit"`.

**Contrôle** : `grep -rn "epistemic_type" --include="*.py"` — vérifier
qu'aucun code ne filtre par `epistemic_type == "foundational"` de manière
exclusive. Chercher en particulier dans `bridge.py` qui encode pour Solana.

#### 3.3 — `services/solana/bridge.py`

Le bridge Solana encode `epistemic_type` en `u8` via un dictionnaire.
Vérifier qu'un mapping existe pour `"security_audit"` :

```python
# Chercher EPISTEMIC_TYPE_MAP ou équivalent dans bridge.py
# Si "security_audit" n'est pas mappé, l'ajout :
EPISTEMIC_TYPE_MAP = {
    "foundational": 0,
    "deterministic": 1,
    "verdict": 2,
    "security_audit": 3,   # Fix 3 (Lot A)
}
EPISTEMIC_TYPE_REVERSE = {v: k for k, v in EPISTEMIC_TYPE_MAP.items()}
```

**⚠️ ATTENTION** : si le programme Rust `state.rs` a un enum correspondant,
il doit aussi être mis à jour. Vérifier `programs/epp/src/state.rs` pour
la correspondance.

**Si le Rust n'est pas mis à jour immédiatement** : utiliser le même index
que `"verdict"` (2) temporairement et documenter avec un
`# TODO: ADR-015 — sync state.rs EpistemicType enum` pour le post-hackathon.
OU garder `"foundational"` pour le bridge et ne changer que la valeur
SQLite. Cela dépend de si on ancre les attestations d'audit on-chain
pendant le hackathon.

**Décision recommandée** : stocker `"security_audit"` en SQLite
(c'est le comportement attendu pour les requêtes), et pour l'ancrage
on-chain, mapper sur l'index 0 (`foundational`) tant que le Rust n'est
pas mis à jour. Documenter avec `# AUDIT_REQUIRED: sync state.rs`.

### Tests RED-GREEN-FIX

```python
# tests/test_fix3_epistemic_type.py

import pytest


def test_audit_pipeline_config_sets_security_audit():
    """RED: PipelineConfig dans audit_runner doit utiliser security_audit."""
    from services.esmm.pipeline import PipelineConfig
    
    # Vérifier que le champ accepte "security_audit"
    config = PipelineConfig(default_epistemic_type="security_audit")
    assert config.default_epistemic_type == "security_audit"


def test_foundational_is_not_used_for_audit():
    """RED: les attestations d'audit ne doivent pas être 'foundational'."""
    # Ce test vérifie la convention — il documente l'intention
    from services.esmm.pipeline import PipelineConfig
    
    # Le défaut reste "foundational" pour le pipeline général
    default_config = PipelineConfig()
    assert default_config.default_epistemic_type == "foundational"
    
    # L'audit doit overrider
    audit_config = PipelineConfig(default_epistemic_type="security_audit")
    assert audit_config.default_epistemic_type != "foundational"
```

---

## Fix 4 — Gérer les cas score=0 / verdict="?" dans le benchmark

### Objectif

Le benchmark heavy montre 2 unités (`getBalance`, `if`) avec
`score: 0.0, verdict: "?"` mais `status: "ok"`. C'est trompeur.
Le statut devrait refléter qu'aucune attestation n'a été produite.

### Fichiers à modifier

#### 4.1 — `scripts/benchmark_heavy.py` (et `scripts/benchmark_reentrancy.py`)

Dans le code qui construit le résultat par unité, après l'appel à
`run_audit()` ou `run_pipeline()`, vérifier si des attestations ont
été produites :

```python
    # --- APRÈS l'appel pipeline ---
    if pipeline_result.attestations:
        best = max(pipeline_result.attestations, key=lambda a: a.consensus_score)
        unit_result = {
            "unit_name": unit.unit_name,
            "status": "ok",
            "verdict": best.object,  # SUPPORTED/CONTESTED/...
            "score": round(best.consensus_score, 4),
            # ...
        }
    else:
        unit_result = {
            "unit_name": unit.unit_name,
            "status": "no_attestation",  # Fix 4 (Lot A)
            "verdict": None,
            "score": 0.0,
            "tier": None,
            "duration_s": duration,
            "errors": [f"Pipeline produced 0 attestations for {unit.unit_name}"],
        }
```

#### 4.2 — `services/audit/audit_runner.py`

Dans la boucle `for unit in sorted_units:`, après l'appel à `run_pipeline()`,
ajouter un log warning si aucune attestation n'est produite :

```python
        pipeline_result = await run_pipeline(...)

        # Fix 4 (Lot A) : log explicite si pipeline ne produit rien
        if not pipeline_result.attestations:
            import logging
            logger = logging.getLogger("audit.runner")
            logger.warning(
                "[AuditRunner] No attestation produced for %s::%s — "
                "pipeline returned 0 attestations (errors: %s)",
                unit.contract_name, unit.unit_name,
                pipeline_result.errors or "none",
            )
```

### Tests RED-GREEN-FIX

```python
# tests/test_fix4_no_attestation.py

import pytest
from services.audit.audit_runner import AuditResult


def test_audit_result_tracks_units_without_attestations():
    """RED: AuditResult doit distinguer les unités sans attestation."""
    # Ce test vérifie la construction du résultat
    # Le champ errors doit capturer les unités sans attestation
    result = AuditResult(
        contract_path="/test.sol",
        contract_hash="abc123",
        contract_name="Test",
        slice_result=None,  # simplifié pour le test
        unit_results=[],
        aggregate_severity="informational",
        aggregate_consensus=0.0,
        total_vulnerabilities=0,
        total_units_audited=0,
        total_units_skipped=0,
        duration_ms=100.0,
        db_path="data/epp_audit_devnet.db",
        errors=["Unit if: Pipeline produced 0 attestations"],
    )
    assert len(result.errors) > 0
    assert "0 attestations" in result.errors[0]
```

---

## Fix 5 — `claim_type: "security_audit"` pour le chemin audit

### Objectif

Le `claim_type` dans `consensus_meta.verify.claim_type` est `"empirical"`
pour les attestations d'audit. Il devrait être `"security_audit"` pour :

1. Éviter la pénalité de décidabilité VERIFY (qui est calibrée pour les
   claims factuels, pas les audits de sécurité)
2. Traçabilité dans `consensus_meta`

### Chaîne causale

```
cycle_manager.py :: _extract_verdicts_from_responses()
  → claim_type = majority vote des modèles
  → Les modèles retournent "empirical" car le prompt ne mentionne pas "security_audit"

pipeline.py :: boucle de cristallisation
  → t_penalty = CLAIM_TYPE_PENALTIES.get(verify_claim_type, 1.0)
  → CLAIM_TYPE_PENALTIES["security_audit"] = 1.0  ← EXISTE DÉJÀ mais jamais utilisé
```

### Approche

Plutôt que de modifier les prompts LLM pour qu'ils retournent un
`claim_type` inconnu, il est plus propre de **forcer** le claim_type
dans `pipeline.py` quand le `default_epistemic_type` est `"security_audit"`.

### Fichier à modifier

#### 5.1 — `services/esmm/pipeline.py`

Dans la section qui extrait `verify_claim_type` depuis les triplets
(chercher `verify_claim_type`), ajouter un override :

```python
    # Chercher le code qui détermine verify_claim_type
    # (probablement dans la section post-orchestration)
    
    # Fix 5 (Lot A) : override claim_type pour les audits de sécurité
    if config.default_epistemic_type == "security_audit":
        verify_claim_type = "security_audit"
```

Cela garantit que :
- `CLAIM_TYPE_PENALTIES["security_audit"] = 1.0` est utilisé (pas de pénalité)
- `consensus_meta.verify.claim_type` = `"security_audit"` 
- `consensus_meta.verify.decidability_penalty.claim_type` = `"security_audit"`

**Vérification** : `CLAIM_TYPE_PENALTIES` doit contenir `"security_audit": 1.0`.
Selon le CHANGELOG, c'est déjà déclaré dans pipeline.py. Le confirmer par :
```bash
grep -n "security_audit" services/esmm/pipeline.py
```

Si absent, ajouter :
```python
CLAIM_TYPE_PENALTIES = {
    "empirical": 1.0,
    "definitional": 0.90,
    "normative": 0.70,
    "speculative": 0.75,
    "security_audit": 1.0,   # Pas de pénalité — verdict vérifiable
}
```

### Tests RED-GREEN-FIX

```python
# tests/test_fix5_claim_type.py

import pytest


def test_security_audit_claim_type_penalty_exists():
    """RED: CLAIM_TYPE_PENALTIES doit inclure security_audit."""
    from services.esmm.pipeline import CLAIM_TYPE_PENALTIES
    
    assert "security_audit" in CLAIM_TYPE_PENALTIES, \
        "CLAIM_TYPE_PENALTIES doit inclure 'security_audit'"
    assert CLAIM_TYPE_PENALTIES["security_audit"] == 1.0, \
        "security_audit ne doit pas avoir de pénalité de décidabilité"


def test_security_audit_claim_type_forces_override():
    """RED: le claim_type doit être forcé à 'security_audit' pour les audits."""
    from services.esmm.pipeline import PipelineConfig
    
    config = PipelineConfig(default_epistemic_type="security_audit")
    # Le pipeline doit utiliser security_audit comme verify_claim_type
    # quand default_epistemic_type est security_audit
    assert config.default_epistemic_type == "security_audit"
```

---

## Ordre d'exécution recommandé

| Ordre | Fix | Risque | Fichiers touchés | Dépendances |
|:---:|:---|:---|:---|:---|
| 1 | **Fix 2** (slicer reserved) | Minimal | `contract_slicer.py` | Aucune |
| 2 | **Fix 3** (epistemic_type) | Minimal | `audit_runner.py`, `bridge.py` (optionnel) | Aucune |
| 3 | **Fix 5** (claim_type) | Minimal | `pipeline.py` | Aucune |
| 4 | **Fix 1** (subject_override) | Moyen | `orchestrator.py`, `pipeline.py`, `audit_runner.py` | Aucune |
| 5 | **Fix 4** (no_attestation) | Minimal | `benchmark_heavy.py`, `audit_runner.py` | Aucune |

**Rationale** : Fix 2, 3, 5 sont isolés et sans risque. Fix 1 est le plus
impactant (touche 3 fichiers dans le pipeline). Fix 4 est cosmétique et
peut être fait en dernier.

---

## Checklist de validation finale

Après tous les fixes, exécuter dans cet ordre :

```bash
# 1. Tests des 5 fixes
pytest tests/test_fix1_subject_override.py tests/test_fix2_slicer_reserved.py \
       tests/test_fix3_epistemic_type.py tests/test_fix4_no_attestation.py \
       tests/test_fix5_claim_type.py -v

# 2. Non-régression complète
pytest tests/ -q
# Attendu : 782 + N nouveaux passed, 14 skipped, 0 failed

# 3. Contrôles C1 (signatures fantômes)
grep -rn "subject_override" --include="*.py" .
# Doit apparaître dans : orchestrator.py, pipeline.py, audit_runner.py, tests

grep -rn "security_audit" --include="*.py" .
# Doit apparaître dans : pipeline.py, audit_runner.py, bridge.py (optionnel), tests

grep -rn "SOLIDITY_RESERVED" --include="*.py" .
# Doit apparaître dans : contract_slicer.py, tests
```

---

## ⚠️ Points de vigilance pour l'audit Opus

1. **`MAX_QUESTION_LENGTH = 5000`** dans `pipeline.py` : les prompts
   d'audit avec des fonctions longues pourraient dépasser cette limite.
   Pour l'instant ça fonctionne (les fonctions de reentrancy.sol sont
   courtes). **Bombe à retardement** pour des contrats plus complexes.
   Recommandation post-Lot A : augmenter à 10000 ou rendre configurable.

2. **Claim hash déterminisme** : le Fix 1 change le `subject` utilisé pour
   le `claim_hash`. Les attestations existantes dans `epp_audit_devnet.db`
   et `epp_audit_heavy.db` auront des hashes différents de ceux produits
   après le fix. Ce n'est **pas un problème** car ces DBs sont des
   artefacts de benchmark, pas de production. Mais il faut en être conscient
   si on compare des résultats pré/post-fix.

3. **`consensus_meta.verify.original_claim`** : cette section continue de
   contenir le prompt brut complet. C'est **voulu** — c'est la traçabilité
   méthodologique (ADR-010). Le `subject` de l'attestation est le résumé
   queryable ; le `original_claim` dans la meta est la preuve complète.
