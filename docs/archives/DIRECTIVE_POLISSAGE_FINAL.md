# DIRECTIVE POLISSAGE FINAL — VERIFY Mode Hackathon-Ready

> **Destinataire :** Claude Code
> **Émetteur :** Audit Adversarial (Opus)
> **Statut :** 🟠 ORANGE → viser 🟢 VERT
> **Contexte :** Scenario 4 post-A1/A2/A3 — les 3 phases tournent, les verdicts sont produits, mais 4 défauts d'hygiène restent

---

## ÉTAT DES LIEUX — Ce qui marche vs ce qui reste

| Aspect | Statut | Preuve |
|:---|:---|:---|
| Auto-détection VERIFY | ✅ | `Auto-detected VERIFY mode for claim:` dans les logs |
| Séquence ASSESS → CHALLENGE → ADJUDICATE | ✅ | 3 cycles dans les logs, types corrects |
| Isolation CHALLENGE (1 provider × 1 question × N) | ✅ | Logs montrent 4 appels séparés |
| Verdicts formels produits | ✅ | `claim -> verdict -> SUPPORTED` et `-> CONTESTED` |
| `consensus_meta.pipeline_mode` = "verify" | ❌ | Affiche `mode=explore` |
| Section `consensus_meta.verify` avec claim + verdicts | ❌ | Absente |
| Evidence sub-consensus visible | ❌ | 25/27 triplets filtrés, invisibles |
| Display démo lisible pour un jury hackathon | ❌ | Affichage générique EXPLORE |

---

## P1 — consensus_meta : Traçabilité VERIFY (ADR-010)

### Problème
`_build_consensus_meta()` dans `pipeline.py` ne sait pas que le run est en mode VERIFY.
Il ne reçoit pas `input_mode` et n'écrit ni `pipeline_mode` ni la section `verify`.

### Fix — `pipeline.py` :: `_build_consensus_meta()`

**Étape 1 :** Ajouter `input_mode` dans la section `methodology` :
```python
methodology["pipeline_mode"] = getattr(esmm_config, "input_mode", "explore")
```

**Étape 2 :** Si `input_mode == "verify"`, ajouter une section `verify` dans le meta dict
avant le `return` :
```python
input_mode = getattr(esmm_config, "input_mode", "explore")
if input_mode == "verify":
    meta["verify"] = {
        "original_claim": getattr(esmm_config, "original_claim", None),
        "model_count": len(models_info),
    }
```

**Étape 3 :** Enrichir la section `verify` avec le verdict final **après** la cristallisation.
Problème : `_build_consensus_meta()` est appelé AVANT la boucle de cristallisation.
Il ne connaît pas encore le verdict final.

**Solution :** Enrichir `consensus_meta["verify"]` APRÈS la boucle de cristallisation,
dans `run_pipeline()` lui-même :

```python
# Après la boucle de cristallisation, si mode VERIFY :
if consensus_meta and consensus_meta.get("verify"):
    verdict_attestations = [
        a for a in attestations if a.predicate == "verdict"
    ]
    if verdict_attestations:
        # Trier par consensus_score descending
        best = max(verdict_attestations, key=lambda a: a.consensus_score)
        consensus_meta["verify"]["final_verdict"] = best.object  # "SUPPORTED" etc.
        consensus_meta["verify"]["verdict_confidence"] = best.consensus_score
        consensus_meta["verify"]["model_verdicts"] = {
            v.model_id: {"agreed": v.agreed, "confidence": v.confidence}
            for a in verdict_attestations for v in a.model_votes
        }
```

**⚠️ NOTE :** Le `consensus_meta` est un dict partagé par toutes les attestations du run.
L'enrichissement post-cristallisation est acceptable car le meta est le même objet Python
pour toutes les attestations (passé par référence). Les attestations déjà cristallisées
verront le meta enrichi si elles pointent vers le même dict.
Sinon, faire un deuxième passage pour mettre à jour les attestations en DB.

### RED test
```python
def test_consensus_meta_pipeline_mode_verify():
    """consensus_meta['methodology']['pipeline_mode'] == 'verify' en mode VERIFY."""
```

### Vérification C1
```bash
grep -rn "pipeline_mode" --include="*.py"
# Doit apparaître dans : pipeline.py (écriture), scenario_4_live_ollama.py (lecture)
```

---

## P2 — Evidence Preservation : Ne pas jeter 25 triplets sur 27

### Problème
Sur 27 triplets extraits des 3 phases, seuls 2 passent le consensus (les verdicts formels).
Les 25 triplets d'evidence sont des informations précieuses :
- `solana -> achieves -> 4000 tps average`
- `claim -> depends_on -> definition of effective tps`
- `solana -> has_peak_tps -> 65000 during stress tests`

Ils ne passent pas le consensus parce que chaque modèle formule l'evidence différemment
(lexical mismatch classique). Mais ils ne se CONTREDISENT pas — ils sont complémentaires.

### Solution : Deux niveaux d'output

**Niveau 1 — Attestations formelles** (inchangé) : Seuls les triplets ayant passé le consensus
sont cristallisés en attestations. C'est le mécanisme existant, on n'y touche pas.

**Niveau 2 — Evidence corpus** (nouveau) : Les triplets sub-consensus sont collectés
et attachés à la section `verify` du `consensus_meta`, catégorisés par type.

### Fix — `pipeline.py` :: `run_pipeline()` enrichissement post-cristallisation

Après la boucle de cristallisation, collecter les triplets qui n'ont PAS atteint le seuil :

```python
if consensus_meta and consensus_meta.get("verify"):
    # Evidence sub-consensus : triplets pertinents mais non attestés
    sub_consensus_evidence = []
    for triplet in extracted_triplets:
        if triplet["consensus_score"] < config.min_consensus_for_attestation:
            sub_consensus_evidence.append({
                "subject": triplet["subject"],
                "predicate": triplet["predicate"],
                "object": triplet["object"],
                "consensus_score": triplet["consensus_score"],
                "models": triplet.get("contributing_models", []),
            })
    if sub_consensus_evidence:
        consensus_meta["verify"]["evidence_corpus"] = sub_consensus_evidence[:20]
        consensus_meta["verify"]["evidence_total"] = len(sub_consensus_evidence)
```

**Pas de nouvelle table SQL.** Le `consensus_meta` JSON absorbe cette information (ADR-010).

### RED test
```python
def test_verify_evidence_corpus_preserved():
    """Les triplets sub-consensus sont dans consensus_meta['verify']['evidence_corpus']."""
```

---

## P3 — Display Hackathon : Scenario 4 lisible pour un jury

### Problème
Le display actuel est générique (format EXPLORE). Un jury hackathon veut voir :
1. La claim évaluée
2. Le verdict final avec le split des modèles
3. Les preuves qui soutiennent/contredisent
4. La progression des 3 phases

### Fix — `scenario_4_live_ollama.py` :: section display

Remplacer/enrichir la section d'affichage des attestations avec un bloc VERIFY dédié :

```
============================================================
VERIFY MODE — Claim Evaluation
============================================================
  Claim: "Solana effective TPS exceeds 3000"
  Frame: blockchain_tps_v1.0

  Phase 1 — ASSESS (independent evaluation):
    4 models consulted independently (40s)
    Verdicts: 3× SUPPORTED, 1× CONTESTED

  Phase 2 — CHALLENGE (adversarial review):
    4 models challenged peers (40s, isolated)
    Counter-arguments collected for synthesis

  Phase 3 — ADJUDICATE (final judgment):
    4 models synthesized all evidence (41s)

  ┌──────────────────────────────────────────────┐
  │  FINAL VERDICT: SUPPORTED (66% consensus)    │
  │  Dissent:       CONTESTED (62% consensus)    │
  │  Split:         2 SUPPORTED / 2 CONTESTED    │
  └──────────────────────────────────────────────┘

  Supporting evidence (sub-consensus):
    • solana -> achieves -> 4000 tps average (1 model, 80%)
    • solana -> has_peak_tps -> 65000 (1 model, 85%)
    • claim -> depends_on -> definition of effective tps (2 models, 70%)

  Duration: 151.1s | 4 models | 3 phases | 27 triplets extracted | 2 attested
============================================================
```

### Implémentation

Le display doit détecter si le run est en mode VERIFY (via `consensus_meta.get("verify")`)
et basculer sur le format ci-dessus. Si mode EXPLORE, l'affichage existant est préservé.

**Sources de données pour le display :**
- `consensus_meta["verify"]["original_claim"]` → la claim
- `consensus_meta["verify"]["final_verdict"]` → le verdict dominant
- `consensus_meta["verify"]["model_verdicts"]` → le split par modèle
- `consensus_meta["verify"]["evidence_corpus"]` → les preuves sub-consensus
- Les attestations elles-mêmes → les verdicts formels (SUPPORTED, CONTESTED)
- `result.duration_ms` → timing
- `esmm_result.cycles_completed` → nombre de phases

**Construction du split :**
```python
verdict_counts = {}
for att in attestations:
    if att.predicate == "verdict":
        verdict_counts[att.object] = verdict_counts.get(att.object, 0) + 1
# Ou mieux : compter depuis model_verdicts si disponible
```

### RED test
Pas de RED test unitaire pour le display — c'est un test visuel.
Validation : relancer `scenario_4_live_ollama.py` et vérifier le format.

---

## P4 — Dernier ajustement : min_agreement VERIFY

### Problème
Le CHALLENGE produit 4 triplets uniques (par construction : rotation circulaire)
→ agreement = 1/4 = 0.25 → TOUT est filtré → 0/0 au consensus.

Ce n'est pas un bug — c'est attendu. Le CHALLENGE alimente le contexte ADJUDICATE,
pas les attestations. MAIS dans les logs ça affiche `0/0 passed` ce qui semble
comme un échec.

### Solution — Pas de changement au consensus, ajustement au logging

**Ne PAS baisser min_agreement globalement** — ça affaiblirait le consensus EXPLORE.

**Ne PAS bypasser le consensus pour CHALLENGE** — ça crée un chemin spécial fragile.

**FAIRE :** Ajouter un log explicatif quand le cycle est CHALLENGE :
```python
if cycle_type in _VERIFY_CYCLE_TYPES and cycle_type == CycleType.CHALLENGE:
    logger.info(
        "[CycleManager] CHALLENGE cycle: %d counter-arguments collected "
        "(consensus not expected — evidence feeds ADJUDICATE)",
        len(responses),
    )
```

C'est cosmétique mais ça montre au jury que le système SAIT que le CHALLENGE
ne produit pas de consensus — c'est by design, pas un bug.

---

## SÉQUENCE D'EXÉCUTION

| # | Fix | Fichier(s) | Effort | Risque |
|:---|:---|:---|:---|:---|
| 1 | P1 — pipeline_mode + verify section | pipeline.py | 20min | Faible |
| 2 | P2 — evidence_corpus | pipeline.py | 15min | Faible |
| 3 | P3 — display VERIFY | scenario_4_live_ollama.py | 30min | Nul |
| 4 | P4 — log CHALLENGE | cycle_manager.py | 5min | Nul |
| 5 | `pytest tests/ --tb=short` | — | — | — |
| 6 | Relancer `scenario_4_live_ollama.py` | — | — | — |

**Effort total estimé : ~1h30 avec tests.**

---

## CONTRAINTES

- **Zéro modification de schema.sql** — tout passe par consensus_meta JSON
- **Zéro régression** — `pytest tests/` doit rester 655+ passed, 0 failed
- **P3 est conditionnel** — le display VERIFY ne s'active QUE si consensus_meta["verify"] existe
- **Le display EXPLORE existant est préservé** — pas de changement pour les runs non-VERIFY

---

## VÉRIFICATION FINALE POST-IMPLÉMENTATION

```bash
# 1. Non-régression
pytest tests/ --tb=short -q
# Attendu : 655+ passed, 0 failed

# 2. Traçabilité
grep -rn "pipeline_mode" --include="*.py"
# Attendu : pipeline.py (écriture), scenario_4_live_ollama.py (lecture)

# 3. Evidence
grep -rn "evidence_corpus" --include="*.py"
# Attendu : pipeline.py (écriture), scenario_4_live_ollama.py (lecture)

# 4. Run live
python demos/scenario_4_live_ollama.py
# Attendu :
#   - "mode=verify" dans consensus meta (PAS "mode=explore")
#   - Section VERIFY visible avec claim + verdict + split
#   - Evidence sub-consensus listée
#   - Log CHALLENGE avec "counter-arguments collected"
```

---

*Fin de directive. Dernier sprint avant la ligne d'arrivée.*
