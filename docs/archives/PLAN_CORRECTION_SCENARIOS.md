# PLAN CORRECTION SCÉNARIOS DÉMO — J7

> **Auteur** : Sim + Claude Opus (auditeur adversarial)
> **Date** : 17 février 2026
> **Baseline** : 553 passed, 0 failed, 11 skipped
> **Cible** : Corriger scenarios 1-3, ajouter scenario 4 (live Ollama)

---

## DIAGNOSTIC : CE QUI NE VA PAS

### Problème commun : les scénarios utilisent le mauvais niveau de mock

Le `mock_provider.py` offre **deux niveaux** de mock :

| Niveau | Mécanisme | Ce qui est exercé |
|:---|:---|:---|
| **L1 — Synthetic triplets** | `make_synthetic_triplets()` → triplets pré-fabriqués | Uniquement pipeline → crystallize → store. **Pas d'extraction, pas de consensus.** |
| **L2 — MockProvider** | `MockProvider(response_set="...")` → texte extractible | TripletExtractor → ConsensusEngine → pipeline → crystallize. **90% du code réel.** |

Les 3 scénarios utilisent **L1** (synthetic). Ils doivent utiliser **L2** (MockProvider).
Avec L2, le flux est : MockProvider retourne du texte → TripletExtractor parse → ConsensusEngine vote → pipeline crystallise. Tout le code métier est exercé sauf le réseau Ollama.

### Bugs spécifiques

| Scénario | Bug | Impact |
|:---|:---|:---|
| **S1** | Triplets génériques (solana/uses/high_throughput) sans lien avec la question "Solana TPS exceeds 3000" | Démo incohérente — les résultats affichés ne correspondent pas à la question |
| **S1** | Mock retourne 2-tuple `(adapted, 1)` — run_id hardcodé, pas de run ESMM en DB | Table `esmm_runs` vide, `consensus_meta` absent |
| **S2** | `base_consensus=0.25` < `min_consensus_for_attestation=0.4` → 0 attestations produites | On ne voit jamais un tier `sandbox` — on voit juste "rien". Pas pédagogique |
| **S3** | `adapted` est une liste mutée en place dans la boucle — closure Python capte la référence, pas la valeur | Les 3 questions reçoivent potentiellement les mêmes triplets |
| **S3** | `t["triplet_hash"] = f"{t['triplet_hash']}_{i}"` — hack du hash | Le hash ne correspond plus à `compute_claim_hash(subject, predicate, object)`. Intégrité cryptographique cassée |
| **S3** | Triplets génériques sans lien thématique entre PoS, Solana et PoH | Le graphe montre des concepts aléatoires, pas un enrichissement connecté |

---

## PLAN DE CORRECTION

### Principe : utiliser MockProvider (L2) au lieu de synthetic triplets (L1)

Au lieu de patcher `_extract_triplets_from_question` avec des triplets pré-fabriqués,
on passe des `MockProvider` au pipeline via le paramètre `providers={}`.
Le pipeline appelle le vrai orchestrateur → vrai extracteur → vrai consensus.
Seul le réseau est simulé (MockProvider retourne du texte pré-écrit).

**Avantage décisif** : les cycles ESMM (divergent → debate → meta) sont réellement
exécutés. Les triplets extraits correspondent à la question. Le consensus est calculé,
pas simulé. Les attestations ont un `consensus_meta` réel (ADR-010).

---

### SCENARIO 1 : Claim factuel vérifiable (corrigé)

**Question** : `"Solana effective TPS exceeds 3000"`
**Frame** : `blockchain_tps_v1.0`
**Response set** : `"default"` (déjà dans mock_provider.py — contient des textes Solana/TPS)

```
Corrections :
1. SUPPRIMER : make_synthetic_triplets, adapt_all, unittest.mock.patch
2. AJOUTER : 3 MockProvider avec response_set="default"
             (identifiants distincts : mock-alpha, mock-beta, mock-gamma)
3. PASSER : providers={...} au run_pipeline()
4. RÉSULTAT ATTENDU :
   - Triplets liés à Solana/TPS/PoH (extraits du texte mock)
   - Tier "proposition" ou "validated" selon agreement
   - consensus_meta présent (ADR-010)
   - esmm_runs peuplé en DB
```

**Structure du code** :

```python
from services.providers.mock_provider import MockProvider

providers = {
    "mock-alpha": MockProvider(model_id="mock-alpha-7b", provider_id="mock-alpha", response_set="default"),
    "mock-beta":  MockProvider(model_id="mock-beta-13b",  provider_id="mock-beta",  response_set="default"),
    "mock-gamma": MockProvider(model_id="mock-gamma-70b", provider_id="mock-gamma", response_set="default"),
}

result = await run_pipeline(
    question=question,
    db=db,
    config=config,
    providers=providers,
)
```

**Output attendu** :
```
[PROPOSITION] solana -> uses -> proof of history
  Consensus: 85.00%
  Hash: a3f2b1c9d7e8...
  Models: 3/3
```

---

### SCENARIO 2 : Rejet d'un claim faux (corrigé)

**Question** : `"Bitcoin was invented by Elon Musk"`
**Frame** : `general_knowledge_v1.0`
**Response set** : `"bitcoin_false_claim"` (déjà dans mock_provider.py — textes de réfutation)

```
Corrections :
1. SUPPRIMER : make_synthetic_triplets, adapt_all, unittest.mock.patch
2. AJOUTER : 3 MockProvider avec response_set="bitcoin_false_claim"
3. RÉSULTAT ATTENDU :
   - Les modèles réfutent le claim → triplets contradictoires
   - Consensus bas → tier "sandbox" ou 0 attestations
   - Le REJET est visible et explicable
   - assert triplets_injected == 0 maintenu
```

**Point pédagogique** : Ajouter un commentaire dans la sortie expliquant
POURQUOI le claim est rejeté. Le scénario doit être lisible comme une démo.

```python
if not result.attestations:
    print("  ✅ CORRECT: False claim rejected — consensus too low to attest.")
    print(f"  Pipeline extracted {result.triplets_extracted} triplets but none passed")
    print(f"  the min_consensus threshold ({config.min_consensus_for_attestation}).")
elif all(att.confidence_tier == "sandbox" for att in result.attestations):
    print("  ✅ CORRECT: False claim quarantined in sandbox tier.")
```

---

### SCENARIO 3 : Enrichissement progressif (corrigé)

**Questions** :
1. `"What is proof of stake"`
2. `"How does Solana achieve consensus"`
3. `"Compare proof of stake and proof of history"`

**Response sets** : `"default"` pour les 3 (contient PoS, PoH, Solana)

```
Corrections :
1. SUPPRIMER : make_synthetic_triplets, adapt_all, unittest.mock.patch
2. SUPPRIMER : hack triplet_hash manuelle
3. AJOUTER : 3 MockProvider par question (ou réutiliser les mêmes)
4. CORRIGER : pas de closure sur mutable — les providers sont stateless,
              pas besoin de closure
5. RÉSULTAT ATTENDU :
   - Q1 : concepts PoS apparaissent dans le graphe
   - Q2 : concepts Solana/PoH s'ajoutent, liens avec PoS existants
   - Q3 : relations comparatives enrichissent le graphe
   - Stats croissantes à chaque itération
   - Hashes cryptographiquement cohérents (compute_claim_hash réel)
```

**Reset des providers entre questions** :
MockProvider cycle à travers ses RESPONSE_SETS. Après 3 appels, il reboucle.
Pour des réponses fraîches à chaque question, réinstancier les providers
dans la boucle (reset `_call_count`).

---

### SCENARIO 4 : Démo live Ollama (NOUVEAU)

**Objectif** : Exécuter un vrai cycle ESMM avec les modèles locaux.
C'est LE scénario pour le hackathon — montre le débat réel entre modèles.

**Prérequis** : Ollama running avec au moins 2 modèles installés.

```
Question : "Solana effective TPS exceeds 3000"
Frame : blockchain_tps_v1.0
Modèles : mistral:7b, llama3.1:8b (+ deepseek-r1:8b si disponible)
Durée : ~5-6 minutes
```

**Structure** :

```python
"""
Scenario 4 -- Live ESMM deliberation with Ollama models.

Executes the FULL ESMM pipeline with REAL local models via Ollama.
This is the definitive demo — shows actual multi-model debate.

Prerequisites:
    - Ollama running (ollama serve)
    - At least 2 models: ollama pull mistral:7b && ollama pull llama3.1:8b

Expected duration: 5-6 minutes (deliberative, not real-time — this is by design)
Expected result: Attestation with real consensus from contested model debate.
"""

async def main():
    # 1. Health check Ollama
    #    - Verify ollama is running (GET /api/tags)
    #    - List available models
    #    - Abort gracefully if < 2 models

    # 2. Setup
    db = ISpaceDB(temp_db)
    question = "Solana effective TPS exceeds 3000"
    config = PipelineConfig(metrological_frame="blockchain_tps_v1.0")

    # 3. Run REAL pipeline (NO mocks, NO patches)
    print("Starting ESMM deliberation (this takes ~5 minutes)...")
    print("  Phase 1: Divergent — each model extracts independently")
    print("  Phase 2: Debate — models challenge each other's triplets")
    print("  Phase 3: Meta — convergence and final consensus")
    print()

    result = await run_pipeline(
        question=question,
        db=db,
        config=config,
        # NO providers= → uses real OllamaProvider via config.yaml
    )

    # 4. Rich output
    #    - Show each attestation with full 5D signature
    #    - Show consensus_meta (ADR-010) : methodology, model versions, diagnostics
    #    - Show graph stats
    #    - Show portable_json for one attestation (what goes on-chain)

    # 5. Optional: anchor to devnet
    #    - If --anchor flag, submit to Solana devnet
    #    - Show tx signature
```

**Points critiques pour le scénario 4** :

1. **Health check** : Ne pas crasher si Ollama n'est pas lancé. Message clair :
   "Ollama not running. Start with `ollama serve` then retry."

2. **Progress feedback** : Le pipeline prend 5-6 minutes. Afficher un indicateur
   de progression (quel cycle en cours, combien de triplets extraits jusqu'ici).

3. **Sortie riche** : C'est la vitrine. Afficher :
   - Le parcours claim → extraction → debate → consensus → attestation
   - La signature 5D complète
   - Le `consensus_meta` (preuve de méthodologie)
   - Un aperçu du `portable_json` (ce qui serait ancré on-chain)

4. **Gestion d'erreur** : Si un modèle timeout, le pipeline continue avec les
   autres. Le scénario doit montrer cette résilience, pas crasher.

---

## ORGANISATION DES FICHIERS

```
demos/
├── scenario_1_factual.py          # MockProvider L2 — claim vérifiable
├── scenario_2_false_claim.py      # MockProvider L2 — rejet
├── scenario_3_enrichment.py       # MockProvider L2 — graphe progressif
├── scenario_4_live_ollama.py      # REAL Ollama — démo hackathon
└── README.md                      # Instructions d'exécution
```

Renommer le dossier de `scenarios/` à `demos/` — plus clair pour les juges.

---

## CONSIGNES POUR CLAUDE CODE

1. **NE PAS toucher** à `mock_provider.py`, `pipeline.py`, `orchestrator.py` ou
   tout fichier dans `services/`. Les scénarios sont des CLIENTS du pipeline.

2. **Chaque scénario** doit être exécutable indépendamment :
   `python demos/scenario_1_factual.py`

3. **Scénario 4** : vérifier que `config.yaml` contient `esmm.models` avec au
   moins 2 modèles réellement installés dans Ollama avant de lancer.

4. **Cleanup** : chaque scénario crée une DB temp et la supprime en fin de run.

5. **Pas de modification de la signature de run_pipeline()** — utiliser uniquement
   les paramètres existants (`providers`, `config`, `esmm_config`).

---

## LIVRABLES EXIGÉS (4 preuves)

| # | Preuve | Format |
|:---|:---|:---|
| 1 | Log scénario 1 (attestation produite, tier affiché) | Sortie terminal |
| 2 | Log scénario 2 (rejet visible, 0 injection graphe) | Sortie terminal |
| 3 | Log scénario 3 (stats graphe croissantes sur 3 questions) | Sortie terminal |
| 4 | pytest complet (553+ passed, 0 failed) | Sortie pytest |

**Le scénario 4 n'est PAS exigé dans ce livrable** — il nécessite Ollama running
et sera validé séparément en session live.

**Sans les preuves 1-4 → 🔴 ROUGE rejeté.**

---

## CRITÈRE DE SUCCÈS VISUEL (pour le hackathon)

Chaque scénario doit être lisible par un juge non-technique en 30 secondes :

```
SCENARIO 1: Verifiable factual claim
Question: "Solana effective TPS exceeds 3000"
Frame: blockchain_tps_v1.0

  [ESMM] 3 models consulted via 3 cycles (divergent → debate → meta)
  [CONSENSUS] 5 unique triplets, 3 passed threshold

  [VALIDATED] solana -> USES -> proof of history
    Consensus: 92.50% | Models: 3/3 | Hash: a3f2b1c9...
    5D Signature: agreement=0.92 semantic=0.88 centrality=0.75 stability=0.80 diversity=1.00

  Graph: 4 concepts, 3 relations
  Duration: 245ms

✅ Scenario 1 complete — verifiable claim attested.
```

Le juge voit immédiatement : question → débat → résultat → confiance → preuve.

---

*PLAN_CORRECTION_SCENARIOS.md — EPP_Verdict*
*Sim + Claude Opus — 17 février 2026*
