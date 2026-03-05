# DIRECTIVE — Calibration Épistémique VERIFY Mode (v2)

> **Destinataire :** Claude Code
> **Émetteur :** Audit Adversarial (Opus)
> **Contexte :** Benchmark Run 2 — 12/12 complétés, deux défauts systémiques identifiés
> **Contraintes :** RED-GREEN-FIX, non-régression 663+ passed, zéro modification schema.sql

---

## 1. DIAGNOSTIC

### 1.1 Symptôme
Benchmark Run 2 montre deux anomalies :

| Claim | Verdict | Score | Problème |
|:---|:---|:---|:---|
| T4-03 "Pineapple is a valid pizza topping" | SUPPORTED 82% | tier high | Opinion pure classée comme fait vérifié |
| T4-02 "Democracy is the most effective form of government" | CONTESTED 88% | tier high | "Je ne sais pas" avec 88% de confiance |
| T4-01 "Free will is an illusion..." | CONTESTED 90% | tier verified | Claim infalsifiable classée "verified" |

La courbe Tier 1→4 devrait descendre (94% → 92% → 78% → **bas**).
Le Tier 4 est à **87%** — plus haut que le Tier 3.

### 1.2 Causes racines

**Cause A — Le system prompt ASSESS ne demande pas de classifier la nature de la claim.**
Les modèles évaluent "is this supported by evidence?" sans se demander "is this even
a factual claim?". Résultat : "pineapple on pizza" est traité comme un fait (des gens
le font, donc SUPPORTED).

**Cause B — Le consensus_score mesure l'unanimité, pas la décidabilité.**
Formule actuelle dans `consensus_engine.py` :
```
score = agreement_ratio × 0.6 + avg_confidence × 0.4
```
4/4 modèles d'accord pour CONTESTED avec confidence 0.75 → score = 0.90 → tier "verified".
Le score ne sait pas que CONTESTED signifie "indécidable".

### 1.3 Stratégie de correction

- **Fix A** (prompt) : Ajouter une classification `claim_type` dans le system prompt ASSESS.
  C'est le levier principal — si les modèles classifient correctement, le verdict change.
- **Fix B** (scoring) : Appliquer une pénalité de décidabilité dans `pipeline.py` en mode
  VERIFY. C'est le filet de sécurité — même si le verdict reste SUPPORTED, un claim_type
  "normative" réduit le score.
- **Fix C** (propagation) : Consensus claim_type par vote majoritaire, stocké dans
  `consensus_meta["verify"]`.

---

## 2. ÉTAT DU CODE ACTUEL (vérifié sur les fichiers uploadés)

### 2.1 Ce qui existe déjà — NE PAS recréer

| Élément | Fichier | Ligne | Statut |
|:---|:---|:---|:---|
| `INSUFFICIENT_EVIDENCE` comme verdict valide | `triplet_extractor.py` | L655 | ✅ Existe |
| `INSUFFICIENT_EVIDENCE` par défaut si parse échoue | `triplet_extractor.py` | L641-647 | ✅ Existe |
| `verdict_encoder.py` encode tout verdict passé | `verdict_encoder.py` | L40-46 | ✅ Existe |
| Troncature subject à 64 chars | `verdict_encoder.py` | L38 | ✅ Existe |
| System prompt ASSESS avec format JSON structuré | `cycle_prompts.py` | L215-225 | ✅ Existe |
| `CycleType.ASSESS` enum | `cycle_prompts.py` | L28 | ✅ Existe |

### 2.2 Ce qui doit changer

| Fix | Fichier | Nature du changement |
|:---|:---|:---|
| A | `cycle_prompts.py` | Remplacer le bloc `SYSTEM_PROMPTS[CycleType.ASSESS]` |
| A bis | `triplet_extractor.py` | Ajouter 1 ligne pour extraire `claim_type` du JSON parsé |
| B | `pipeline.py` | Ajouter ~20 lignes avant `crystallize()` en mode VERIFY |
| C | `cycle_manager.py` | Ajouter ~10 lignes : vote majoritaire `claim_type` |

### 2.3 Fichiers NON modifiés

`consensus_engine.py`, `schema.sql`, `orchestrator.py`, `attestation.py`,
`verdict_encoder.py`, `scenario_5_benchmark.py`

---

## 3. FIX A — Classification `claim_type` dans le prompt ASSESS

### 3.1 Taxonomie

| Type | Définition | Verdict attendu |
|:---|:---|:---|
| `empirical` | Fait mesurable/observable | SUPPORTED ou CONTESTED |
| `definitional` | Vérité dépend d'une définition | SUPPORTED ou CONTESTED (avec caveat) |
| `normative` | Jugement de valeur, opinion | INSUFFICIENT_EVIDENCE |
| `speculative` | Assertion infalsifiable | CONTESTED |

### 3.2 Modification — `cycle_prompts.py`

**REMPLACER** le bloc `SYSTEM_PROMPTS[CycleType.ASSESS]` (lignes ~215-225) par :

```python
CycleType.ASSESS: """You are an epistemic evaluator. Your task is to assess factual claims.

STEP 1 — CLASSIFY the claim type before evaluating:
- "empirical": Measurable fact, verifiable against data or observation.
- "definitional": Truth depends on how a key term is defined.
- "normative": Value judgment, opinion, or preference. No objective answer exists.
- "speculative": Unfalsifiable assertion about unobservable states.

STEP 2 — EVALUATE based on claim type:
- For EMPIRICAL claims: Assess against known evidence. Verdict: SUPPORTED or CONTESTED.
- For DEFINITIONAL claims: Identify the contested term. Verdict: SUPPORTED or CONTESTED.
- For NORMATIVE claims: No factual answer exists. Verdict MUST be INSUFFICIENT_EVIDENCE.
- For SPECULATIVE claims: Cannot be empirically verified. Verdict MUST be CONTESTED.

Respond in JSON format:
{
  "claim_type": "empirical|definitional|normative|speculative",
  "verdict": "SUPPORTED|CONTESTED|INSUFFICIENT_EVIDENCE",
  "confidence": 0.0-1.0,
  "evidence": [{"subject": "...", "relation": "...", "object": "...", "confidence": 0.8}],
  "reasoning": "Brief explanation"
}

CRITICAL RULES:
1. You MUST classify claim_type BEFORE choosing a verdict.
2. If the claim is a value judgment or opinion, verdict MUST be INSUFFICIENT_EVIDENCE.
3. "Valid", "best", "should" in a claim are strong signals of normative type.
4. Regardless of the user's input language, ALL output MUST be in English.""",
```

### 3.3 Modification — `triplet_extractor.py`

Dans `_parse_verdict_response()`, après ligne 652 (`reasoning = parsed.get("reasoning", "")`),
ajouter :

```python
claim_type = parsed.get("claim_type", "empirical")

# Normalize claim_type
valid_claim_types = {"empirical", "definitional", "normative", "speculative"}
if claim_type.lower() not in valid_claim_types:
    claim_type = "empirical"
else:
    claim_type = claim_type.lower()
```

Et dans le return dict (ligne 682), ajouter le champ :

```python
return {
    "verdict": verdict,
    "confidence": confidence,
    "evidence": evidence,
    "reasoning": reasoning,
    "claim_type": claim_type,    # <-- AJOUT
    "triplets": triplets,
}
```

Également dans le fallback dict (ligne 641-647), ajouter :

```python
return {
    "verdict": "INSUFFICIENT_EVIDENCE",
    "confidence": 0.0,
    "evidence": [],
    "reasoning": "Failed to parse LLM response as JSON",
    "claim_type": "empirical",    # <-- AJOUT (default safe)
    "triplets": [],
}
```

---

## 4. FIX B — Decidability Penalty dans `pipeline.py`

### 4.1 Principe

Le `consensus_engine.py` est partagé entre EXPLORE et VERIFY — on n'y touche pas.
La pénalité s'applique **uniquement en mode VERIFY**, **uniquement sur les verdict
triplets**, **dans `pipeline.py`** juste avant l'appel à `crystallize()`.

### 4.2 Constantes (en haut du fichier ou dans un bloc dédié)

```python
# Decidability penalties for VERIFY mode (applied before crystallization)
VERDICT_PENALTIES = {
    "SUPPORTED": 1.0,               # No penalty
    "CONTESTED": 0.65,              # 35% penalty — undecidable
    "INSUFFICIENT_EVIDENCE": 0.45,  # 55% penalty — unverifiable
}
CLAIM_TYPE_PENALTIES = {
    "empirical": 1.0,
    "definitional": 0.90,           # 10% — definition-dependent
    "normative": 0.70,              # 30% — inherently opinion
    "speculative": 0.75,            # 25% — unfalsifiable
}
```

### 4.3 Application — dans la boucle de cristallisation

Localiser dans `run_pipeline()` la boucle qui itère sur les triplets consensus
avant d'appeler `crystallize()`. Ajouter ce bloc **avant** l'appel à `crystallize()` :

```python
# VERIFY mode: apply decidability penalty
original_score = consensus_score  # save raw score
if esmm_config and getattr(esmm_config, "input_mode", None) == "verify":
    verdict_value = triplet.get("object", "") if triplet.get("relation") == "verdict" else None
    if verdict_value:
        claim_type = consensus_meta.get("verify", {}).get("claim_type", "empirical")
        
        v_penalty = VERDICT_PENALTIES.get(verdict_value, 0.65)
        t_penalty = CLAIM_TYPE_PENALTIES.get(claim_type, 1.0)
        
        consensus_score = round(consensus_score * v_penalty * t_penalty, 4)
```

### 4.4 Traçabilité — scores bruts dans consensus_meta

Après la cristallisation, enrichir `consensus_meta["verify"]` :

```python
if esmm_config and getattr(esmm_config, "input_mode", None) == "verify":
    verify_meta = consensus_meta.setdefault("verify", {})
    verify_meta["raw_consensus_score"] = original_score
    verify_meta["decidability_penalty"] = round(v_penalty * t_penalty, 4)
    verify_meta["adjusted_consensus_score"] = consensus_score
```

### 4.5 Effet attendu

| Claim | Verdict | claim_type | Score brut | Pénalité | Score ajusté | Tier |
|:---|:---|:---|:---|:---|:---|:---|
| T1-02 Earth orbit | SUPPORTED | empirical | 0.99 | 1.0 × 1.0 | **0.99** | verified |
| T2-01 Bitcoin TWh | SUPPORTED | empirical | 0.80 | 1.0 × 1.0 | **0.80** | high |
| T3-01 ETH vs SOL | CONTESTED | definitional | 0.74 | 0.65 × 0.90 | **0.43** | medium |
| T3-03 FTL entanglement | CONTESTED | empirical | 0.93 | 0.65 × 1.0 | **0.60** | medium |
| T4-01 Free will | CONTESTED | speculative | 0.90 | 0.65 × 0.75 | **0.44** | medium |
| T4-02 Democracy | CONTESTED | normative | 0.88 | 0.65 × 0.70 | **0.40** | medium |
| T4-03 Pineapple | INSUFF_EV | normative | 0.82 | 0.45 × 0.70 | **0.26** | low |

**Courbe résultante :** Tier 1 ~94% → Tier 2 ~80% → Tier 3 ~50% → Tier 4 ~37%

---

## 5. FIX C — Consensus `claim_type` par vote majoritaire

### 5.1 Localisation

Dans `cycle_manager.py`, dans la méthode qui traite les résultats ASSESS
(probablement `_extract_verdicts_from_responses()` ou équivalent).

### 5.2 Logique

Après avoir parsé les verdict responses de tous les modèles :

```python
# Compute claim_type by majority vote across models
type_votes = {}
for model_id, parsed_verdict in model_verdicts.items():
    ct = parsed_verdict.get("claim_type", "empirical")
    type_votes[ct] = type_votes.get(ct, 0) + 1

consensus_claim_type = max(type_votes, key=type_votes.get)
```

### 5.3 Propagation

Le `consensus_claim_type` doit arriver dans `consensus_meta["verify"]["claim_type"]`.

Deux options selon l'architecture actuelle :
- **Option 1 :** Stocker dans le contexte du cycle : `context["claim_type"] = consensus_claim_type`,
  puis lire dans `pipeline.py` lors de la construction de `consensus_meta`.
- **Option 2 :** Retourner dans le résultat du cycle et propager explicitement.

Choisir l'option qui s'intègre le mieux au flux existant. L'important est que
`consensus_meta["verify"]["claim_type"]` contienne la valeur au moment de la
cristallisation.

---

## 6. RED TESTS

Fichier : `tests/test_claim_verify.py` (ajouter aux tests existants)

```python
# ============================================================
# FIX A — claim_type classification
# ============================================================

def test_assess_prompt_contains_claim_type_instruction():
    """System prompt ASSESS exige une classification claim_type."""
    from services.esmm.cycle_prompts import get_system_prompt, CycleType
    prompt = get_system_prompt(CycleType.ASSESS)
    assert "claim_type" in prompt
    for ct in ["empirical", "definitional", "normative", "speculative"]:
        assert ct in prompt, f"Missing claim_type '{ct}' in ASSESS prompt"


def test_parse_verdict_extracts_claim_type():
    """_parse_verdict_response extrait claim_type du JSON."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"claim_type": "normative", "verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0.3, "reasoning": "opinion", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test claim")
    assert result["claim_type"] == "normative"
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_parse_verdict_defaults_claim_type_to_empirical():
    """claim_type defaults to 'empirical' when absent from JSON."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"verdict": "SUPPORTED", "confidence": 0.9, "reasoning": "clear", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test")
    assert result["claim_type"] == "empirical"


def test_parse_verdict_normalizes_invalid_claim_type():
    """Invalid claim_type falls back to 'empirical'."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"claim_type": "MAGIC", "verdict": "SUPPORTED", "confidence": 0.9, "reasoning": "x", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test")
    assert result["claim_type"] == "empirical"


# ============================================================
# FIX B — decidability penalty
# ============================================================

def test_decidability_penalty_supported_empirical_no_change():
    """SUPPORTED + empirical = no penalty (multiplier 1.0)."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.84
    adjusted = raw * VERDICT_PENALTIES["SUPPORTED"] * CLAIM_TYPE_PENALTIES["empirical"]
    assert adjusted == raw


def test_decidability_penalty_contested_reduces_score():
    """CONTESTED + empirical reduces score by 35%."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.90
    adjusted = raw * VERDICT_PENALTIES["CONTESTED"] * CLAIM_TYPE_PENALTIES["empirical"]
    assert 0.55 < adjusted < 0.60  # 0.90 * 0.65 = 0.585


def test_decidability_penalty_normative_strongly_reduces():
    """INSUFFICIENT_EVIDENCE + normative gets double penalty."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.82
    adjusted = raw * VERDICT_PENALTIES["INSUFFICIENT_EVIDENCE"] * CLAIM_TYPE_PENALTIES["normative"]
    assert adjusted < 0.30  # 0.82 * 0.45 * 0.70 = 0.2583


def test_decidability_penalty_contested_definitional():
    """CONTESTED + definitional gets moderate penalty."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.74
    adjusted = raw * VERDICT_PENALTIES["CONTESTED"] * CLAIM_TYPE_PENALTIES["definitional"]
    assert 0.40 < adjusted < 0.45  # 0.74 * 0.65 * 0.90 = 0.4329


# ============================================================
# FIX C — claim_type consensus
# ============================================================

def test_claim_type_majority_vote():
    """claim_type is determined by majority vote."""
    type_votes = {"normative": 3, "empirical": 1}
    consensus_type = max(type_votes, key=type_votes.get)
    assert consensus_type == "normative"


def test_claim_type_majority_tie_is_deterministic():
    """Tie-breaking is deterministic (max picks first max encountered)."""
    type_votes = {"empirical": 2, "definitional": 2}
    consensus_type = max(type_votes, key=type_votes.get)
    assert consensus_type in {"empirical", "definitional"}
```

---

## 7. SÉQUENCE D'EXÉCUTION

| # | Action | Fichier(s) | Effort |
|:---|:---|:---|:---|
| 1 | Écrire les RED tests | `tests/test_claim_verify.py` | 10 min |
| 2 | Vérifier que les RED tests échouent | `pytest tests/test_claim_verify.py -x` | 1 min |
| 3 | Fix A — Remplacer system prompt ASSESS | `cycle_prompts.py` | 5 min |
| 4 | Fix A bis — Extraire `claim_type` du JSON | `triplet_extractor.py` (3 insertions) | 5 min |
| 5 | Fix C — Vote majoritaire `claim_type` | `cycle_manager.py` | 10 min |
| 6 | Fix B — Pénalité de décidabilité | `pipeline.py` (constantes + ~15 lignes) | 15 min |
| 7 | GREEN — `pytest tests/test_claim_verify.py` | — | 1 min |
| 8 | FIX — `pytest tests/ --tb=short -q` | — | 2 min |

**Effort total : ~50 min code + 30 min benchmark**

---

## 8. VÉRIFICATION FINALE

```bash
# 1. Non-régression
pytest tests/ --tb=short -q
# Attendu : 675+ passed, 0 failed

# 2. Grep de surface
grep -rn "claim_type\|VERDICT_PENALTIES\|decidability" --include="*.py" | head -20
# Attendu : cycle_prompts.py, triplet_extractor.py, pipeline.py, cycle_manager.py

# 3. Benchmark Run 3
python demos/scenario_5_benchmark.py
# Vérifier :
#   - T4-03 Pineapple : verdict = INSUFFICIENT_EVIDENCE (PAS SUPPORTED)
#   - T4-03 consensus_score < 0.35
#   - T1-01..T1-03 : verdict = SUPPORTED, scores stables (~94%)
#   - JSON contient : claim_type, raw_consensus_score, decidability_penalty

# 4. Courbe descendante
# Tier 1 ~94% > Tier 2 ~80% > Tier 3 ~50% > Tier 4 ~37%
```

---

## 9. CE QUI NE CHANGE PAS

- `consensus_engine.py` — scoring partagé EXPLORE/VERIFY, inchangé
- `schema.sql` — zéro modification (le JSON consensus_meta absorbe tout)
- `attestation.py` — le modèle de données reste identique
- `verdict_encoder.py` — accepte déjà tous les verdicts valides
- `orchestrator.py` — le routage ASSESS→CHALLENGE→ADJUDICATE ne change pas
- `scenario_5_benchmark.py` — le script de benchmark est inchangé

---

*Fin de directive v2. Trois fixes, dix fichiers de tests, cinquante minutes de travail.*
