# DIRECTIVE D'IMPLÉMENTATION — Mode Claim Verification

> **Destinataire :** Claude Code
> **Émetteur :** Audit Adversarial (Opus)
> **Statut :** 🔴 BLOQUANT — Le pipeline fonctionne mais ne répond pas à sa mission épistémique
> **Contexte :** Verdict Scenario 4 — zéro attestation ne répond à la claim posée

---

## 0. LE PROBLÈME EN UNE PHRASE

La claim `"Solana effective TPS exceeds 3000"` entre dans le pipeline et en ressort sous forme de thésaurus (`exceeds -> similar_to -> outstrip`). La proposition composite n'est jamais évaluée comme assertion de vérité.

**Cause racine :** Le `question_seeder` atomise la claim en concepts isolés, puis les cycles DIVERGENT/DEBATE/META explorent chaque concept séparément. Personne ne demande jamais aux modèles : *"Est-il vrai que le TPS effectif de Solana dépasse 3000 ?"*

---

## 1. PRINCIPE ARCHITECTURAL : DUAL-MODE

Le système doit fonctionner en **deux modes**, sélectionnés automatiquement :

| Mode | Input type | Objectif | Cycles |
|:---|:---|:---|:---|
| **EXPLORE** (actuel) | Requête ouverte, domaine | Knowledge graph RAG | DIVERGENT → DEBATE → META |
| **VERIFY** (nouveau) | Claim factuelle vérifiable | Jugement de vérité avec preuves | ASSESS → CHALLENGE → ADJUDICATE |

**Règle de non-régression absolue :** Le mode EXPLORE reste intact. Aucun test existant ne casse. Le mode VERIFY est un ajout, pas une réécriture.

---

## 2. FICHIERS IMPACTÉS — CHAÎNE DE RESPONSABILITÉS

### 2.1 — `question_seeder.py` : Détection du mode

**Directive :** Ajouter une fonction `classify_input(question: str) -> InputType` qui détermine si l'input est une claim vérifiable ou une requête exploratoire.

**Heuristiques de classification (non exhaustif, à enrichir) :**
- Présence d'un verbe d'état + valeur mesurable → CLAIM (`"X exceeds Y"`, `"X is greater than Y"`, `"X costs less than Y"`)
- Présence d'une assertion binaire → CLAIM (`"X uses Y"`, `"X is a Z"`)
- Question ouverte sans assertion → EXPLORE (`"What is X?"`, `"How does X work?"`)
- Formulation impérative de vérification → CLAIM (`"Verify that..."`, `"Is it true that..."`)

**Contrainte critique :** En mode VERIFY, la claim originale **complète** doit être préservée et transmise telle quelle au cycle manager. Le seeding par concepts individuels reste en parallèle (pour le graphe de fond), mais la claim intégrale est l'unité de travail primaire.

**Nouvelle signature de `seed_graph_from_question` :**
```
Returns: Tuple[int, InputType, str]  # (concepts_seeded, mode, original_claim)
```
Ou via un dataclass `SeederResult`. Le `pipeline.py` doit recevoir le mode pour le propager à l'orchestrateur.

### 2.2 — `cycle_prompts.py` : Nouveaux types de cycles

**Directive :** Ajouter trois nouveaux CycleType et leurs templates/system prompts associés.

```
CycleType.ASSESS = "assess"          # Évaluation initiale indépendante
CycleType.CHALLENGE = "challenge"    # Contre-argumentation
CycleType.ADJUDICATE = "adjudicate"  # Jugement final pondéré
```

**ASSESS — System Prompt (directives, pas code final) :**
- Le modèle reçoit la claim COMPLÈTE, pas un concept
- Il doit produire un verdict structuré : `SUPPORTED`, `CONTESTED`, `INSUFFICIENT_EVIDENCE`
- Il doit fournir des preuves sous forme de triplets orientés claim :
  - `claim -> supported_by -> [evidence]`
  - `claim -> contradicted_by -> [counter_evidence]`
  - `claim -> depends_on -> [assumption]`
- Il doit estimer une confiance numérique (0.0–1.0)
- Le format de sortie JSON doit inclure : `verdict`, `confidence`, `evidence_triplets[]`, `reasoning`

**ASSESS — Templates (3-4 suffisent) :**
1. Évaluation directe de véracité avec preuves
2. Identification des hypothèses sous-jacentes et conditions de validité
3. Recherche de données factuelles spécifiques qui confirment ou infirment
4. Évaluation des limites de l'assertion (domaine de validité, temporalité, définitions)

**CHALLENGE — System Prompt :**
- Le modèle reçoit la claim + le verdict d'un autre modèle (anonymisé)
- Sa mission est de trouver les failles dans l'argumentation
- Il doit produire des contre-arguments structurés
- Format : `counter_evidence_triplets[]`, `weakness_in_reasoning`, `alternative_interpretation`

**CHALLENGE — Templates (3-4 suffisent) :**
1. "Voici une claim et un verdict. Trouve les failles dans le raisonnement et les preuves manquantes."
2. "Quelles données ou perspectives contredisent ce verdict ?"
3. "Quelles définitions ou hypothèses implicites pourraient invalider cette conclusion ?"

**ADJUDICATE — System Prompt :**
- Le modèle reçoit la claim + les verdicts ET contre-arguments de tous les modèles
- Il doit produire un jugement synthétique final
- Format : `final_verdict`, `confidence`, `synthesis_triplets[]`, `dissenting_points[]`

**ADJUDICATE — Templates (2-3 suffisent) :**
1. "Étant donné ces arguments pour et contre, quel est le verdict le plus robuste ?"
2. "Quels points de désaccord entre les modèles sont substantiels vs superficiels ?"

**⚠️ Contrainte d'indépendance épistémique (principe fondateur EPP) :**
- En phase ASSESS, chaque modèle travaille de manière **strictement isolée** — zéro contamination croisée
- En phase CHALLENGE, chaque modèle reçoit les arguments d'un SEUL autre modèle (pas de broadcast)
- En phase ADJUDICATE, le brassage est autorisé car c'est une synthèse, pas une opinion indépendante

### 2.3 — `cycle_manager.py` : Routing et séquence VERIFY

**Directive :** Le cycle manager doit supporter la séquence VERIFY en plus de la séquence EXPLORE existante.

**Séquence VERIFY :**
```
ASSESS (tous les modèles, isolés) 
    → CHALLENGE (chaque modèle critique un pair)
        → ADJUDICATE (synthèse cross-modèles)
```

**Différences clés avec le mode EXPLORE :**

| Aspect | EXPLORE | VERIFY |
|:---|:---|:---|
| Unité de travail | Concept individuel | Claim complète |
| Sélection concepts | `_select_target_concepts()` | Non applicable — la claim est fixe |
| Template vars | `{concept}`, `{thesis}/{antithesis}` | `{claim}`, `{verdict}`, `{evidence}` |
| Question generation | Rotation de templates sur concepts | Templates fixes sur la claim |
| Nombre de cycles | Config dynamique (adaptation) | Exactement 3 phases (ASSESS → CHALLENGE → ADJUDICATE) |

**La méthode `_generate_question()` doit être étendue :** En mode VERIFY, elle reçoit la claim complète et les résultats des phases précédentes (verdicts, contre-arguments) comme contexte.

**L'appel à `_query_models()` en phase ASSESS doit respecter l'isolation :** Chaque modèle reçoit le même prompt MAIS les réponses ne sont pas partagées entre modèles avant la phase CHALLENGE.

### 2.4 — `orchestrator.py` : Séquence VERIFY

**Directive :** L'orchestrateur doit supporter un deuxième chemin d'exécution.

```python
# Pseudo-logique (PAS du code à copier-coller)
if input_mode == VERIFY:
    cycle_sequence = ["assess", "challenge", "adjudicate"]
else:
    cycle_sequence = config.cycle_sequence  # ["divergent", "debate", "meta"]
```

**Le `ESMMRunConfig` doit accepter le mode :** Ajouter un champ `input_mode: InputType` (default: EXPLORE pour backward compat).

**La propagation :** `pipeline.py` → `ESMMRunConfig` → `orchestrator` → `cycle_manager`. La claim originale doit voyager avec le config, pas être perdue au seeding.

### 2.5 — `consensus_engine.py` : Consensus sur verdicts

**Directive :** Le consensus en mode VERIFY ne porte PAS sur des triplets sémantiques mais sur des **verdicts**.

**Nouvelle unité de consensus :** Au lieu de hasher `(subject, relation, object)`, le consensus VERIFY hashe `(claim, verdict)`. Exemple : 3 modèles sur 4 disent `SUPPORTED` → consensus `SUPPORTED` avec score 0.75.

**Le mécanisme existant peut être réutilisé** si les verdicts sont encodés comme triplets spéciaux :
- `claim_hash -> verdict -> SUPPORTED` (confidence: 0.85)
- `claim_hash -> evidence -> "Solana processes ~4000 TPS on mainnet"` (confidence: 0.7)

Cela permet de réutiliser toute la mécanique de cristallisation et d'attestation sans la réécrire. C'est le **chemin de moindre risque**.

### 2.6 — `triplet_extractor.py` : Extraction de verdicts

**Directive :** L'extracteur doit supporter un deuxième format de sortie en mode VERIFY.

**Format actuel (EXPLORE) :** JSON array de `{subject, relation, object, confidence}`
**Format VERIFY :** JSON objet `{verdict, confidence, evidence: [{subject, relation, object}], reasoning}`

L'extracteur doit détecter le mode et parser en conséquence. Les triplets d'evidence sont extraits et traités normalement. Le verdict est encodé comme triplet spécial (cf. 2.5).

### 2.7 — `attestation.py` : Champ verdict

**Directive :** Les attestations produites en mode VERIFY doivent porter le verdict explicitement.

Ajouter dans `consensus_meta` (ADR-010) :
- `input_mode: "verify"`
- `claim_text: "Solana effective TPS exceeds 3000"`
- `final_verdict: "SUPPORTED" | "CONTESTED" | "INSUFFICIENT_EVIDENCE"`
- `verdict_confidence: 0.75`
- `model_verdicts: {"mistral": "SUPPORTED", "llama3.1": "SUPPORTED", "deepseek-r1": "CONTESTED", ...}`

Pas de nouvelle colonne SQL — le `consensus_meta` JSON est extensible par design (ADR-010).

---

## 3. SÉQUENCE D'IMPLÉMENTATION RECOMMANDÉE

L'ordre est critique pour permettre le RED-GREEN-FIX à chaque étape.

| Étape | Fichier(s) | Livrable | Test RED d'abord |
|:---|:---|:---|:---|
| **S1** | `cycle_prompts.py` | Nouveaux CycleType + templates ASSESS/CHALLENGE/ADJUDICATE + system prompts | Test que `CycleType.ASSESS` existe et que `get_template(CycleType.ASSESS)` retourne un string contenant `{claim}` |
| **S2** | `question_seeder.py` | `classify_input()` + `SeederResult` | Test que `classify_input("Solana TPS exceeds 3000")` → VERIFY, `classify_input("What is Solana?")` → EXPLORE |
| **S3** | `cycle_manager.py` | `_generate_question()` étendu pour mode VERIFY | Test que la question générée en mode ASSESS contient la claim complète, pas un concept isolé |
| **S4** | `triplet_extractor.py` | Parsing du format verdict | Test avec un JSON verdict mocké → extraction correcte |
| **S5** | `consensus_engine.py` | Consensus sur verdicts encodés en triplets | Test que 3x SUPPORTED + 1x CONTESTED → consensus SUPPORTED |
| **S6** | `orchestrator.py` + `pipeline.py` | Intégration end-to-end du mode VERIFY | Test d'intégration avec MockProvider |
| **S7** | `attestation.py` | `consensus_meta` enrichi avec verdict | Test que l'attestation finale contient `final_verdict` |

---

## 4. CONTRAINTES NON-NÉGOCIABLES

### 4.1 — Backward Compatibility
- Tous les nouveaux paramètres sont **optionnels avec defaults** reproduisant le comportement actuel
- `InputType` default = `EXPLORE`
- Aucun test existant ne casse — `pytest tests/` complet à chaque étape

### 4.2 — Indépendance épistémique
- Phase ASSESS : les modèles ne voient JAMAIS les réponses des autres modèles
- Phase CHALLENGE : chaque modèle ne voit que le verdict d'UN SEUL pair (pas de broadcast)
- Ceci est le **principe fondateur** d'EPP — toute violation invalide le protocole

### 4.3 — Claim preservation
- La claim originale doit être accessible **mot pour mot** à chaque étape du pipeline
- Elle ne doit JAMAIS être uniquement représentée par ses concepts atomisés
- Elle doit figurer dans le `consensus_meta` de l'attestation finale

### 4.4 — Vérifications C1 obligatoires
Après implémentation, prouver par `grep` :
- `grep -rn "CycleType" --include="*.py"` → tous les fichiers qui référencent CycleType gèrent les nouveaux types
- `grep -rn "InputType\|input_mode\|VERIFY\|EXPLORE" --include="*.py"` → propagation complète
- `grep -rn "classify_input" --include="*.py"` → appelé dans pipeline.py

### 4.5 — Documentation
- `ARCHITECTURE.md` mis à jour avec le diagramme dual-mode
- `CHANGELOG.md` mis à jour
- Pas de nouvel ADR nécessaire sauf si un choix architectural controversé émerge

---

## 5. CE QUE CLAUDE CODE NE DOIT PAS FAIRE

1. **Ne pas réécrire les prompts EXPLORE existants.** Ils fonctionnent pour leur cas d'usage (knowledge graph RAG). Le problème n'est pas leur qualité — c'est qu'ils sont utilisés pour le mauvais objectif.

2. **Ne pas forcer la claim dans les templates DIVERGENT existants.** Le template `"What are the fundamental relationships between {concept}..."` avec `concept = "Solana effective TPS exceeds 3000"` produira des résultats incohérents. Il faut des templates dédiés.

3. **Ne pas créer un flag `--verify` qu'on oublie de passer.** La détection du mode doit être **automatique** via `classify_input()`. Le mode manuel peut exister en override, mais le défaut est l'auto-détection.

4. **Ne pas sacrifier l'isolation des modèles pour simplifier le code.** Broadcaster tous les verdicts à tous les modèles en phase CHALLENGE est plus simple à coder mais viole l'indépendance épistémique. C'est interdit.

5. **Ne pas modifier `schema.sql`.** Le `consensus_meta` JSON est suffisant pour stocker les verdicts. Pas de nouvelle table, pas de nouvelle colonne. Si Claude Code estime qu'une modification de schéma est nécessaire, il doit soumettre la justification AVANT d'implémenter.

---

## 6. CRITÈRE DE SUCCÈS

Le Scenario 4 refactoré doit produire des attestations qui répondent **à la question posée** :

```
Input:  "Solana effective TPS exceeds 3000"
Output attendu (exemple):
  claim_hash -> verdict -> SUPPORTED (confidence: 0.72)
  claim_hash -> evidence -> "Solana mainnet processes ~4000 TPS average" 
  claim_hash -> evidence -> "Peak TPS exceeded 65,000 during stress tests"
  claim_hash -> caveat -> "Effective TPS varies; includes vote transactions"
  claim_hash -> depends_on -> "Definition of 'effective TPS' includes/excludes vote txs"
```

**Le test ultime :** Chercher "TPS" et "3000" dans les attestations → ils DOIVENT être présents.

---

*Fin de directive. Claude Code, compose ton plan d'implémentation à partir de ces spécifications. Tout écart par rapport à ces directives doit être justifié explicitement avant exécution.*
