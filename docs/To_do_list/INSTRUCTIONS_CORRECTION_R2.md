# INSTRUCTIONS — Correction PLAN_TACTIQUE_R2.md

> Décisions humaines validées + corrections Opus. Tu as déjà tout le contexte.
> Applique les 8 corrections + les 3 décisions ci-dessous, puis livre le plan corrigé.

---

## Décisions validées

### 1. Option C confirmée pour R-2.2.1 (bonus diversité)

Bonus APRÈS `crystallize()`, pas avant. Le `consensus_score` et le
`confidence_tier` restent immuables. Deux nouveaux champs **persistés en DB** :

- `adjusted_consensus_score REAL` — score avec bonus diversité appliqué
- `diversity_bonus_factor REAL DEFAULT 1.0` — facteur traçable (1.0 ou 1.1)

Ajouter ces deux colonnes à la table `attestations` dans `schema.sql`.
Les remplir dans `post_crystallization_hook()`, pas dans `crystallize()`.

### 2. Verify commit-reveal via `exploration_cycles` (R-2.2.3)

Les réponses brutes sont déjà persistées dans `exploration_cycles.responses`
(colonne TEXT NOT NULL, JSON `{model_name: response_text}`). Le log se fait
à L261 de `execute_cycle()`, après l'extraction (L256) mais les `responses`
ne sont pas transformées entre L214 et L261.

Conséquences :
- `commit_reveal` ne stocke que les hashes (léger). Pas de re-stockage des réponses.
- Le verify relit depuis `exploration_cycles` :

```python
cycle = await db.get_exploration_cycle(cycle_id)
stored_responses = json.loads(cycle["responses"])
for model_id, text in stored_responses.items():
    assert sha256(text) == committed_hash[model_id]
```

### 3. Résultat du verify dans `attestations`, pas dans `commit_reveal`

Ajouter à la table `attestations` :

- `commit_reveal_verified INTEGER` — NULL=pas de commit-reveal, 1=intègre, 0=mismatch

Ça permet de savoir pour chaque attestation si la chaîne commit→reveal
est intègre sans jointure. La table `commit_reveal` reste le journal
détaillé (hash par modèle par phase), `attestations` porte le verdict.

---

## Rappel des 8 corrections (diagnostic validé)

| # | Section | Correction |
|---|---------|------------|
| 1 | R-2.1.1 | `resolved_predictions` → `total_resolved` |
| 2 | R-2.1.1 | Chaîne d'appel : 7 signatures (Option A), pas 3 |
| 3 | R-2.1.1 | Ajouter : grep C1 sur les 7 méthodes modifiées |
| 4 | R-2.2.1 | Bonus diversité APRÈS crystallize() (Option C) |
| 5 | R-2.2.1 | Nouveaux champs DB : `adjusted_consensus_score`, `diversity_bonus_factor` |
| 6 | R-2.2.2 | Créer `MockDeterministicEmbeddingProvider` (hash-based) |
| 7 | R-2.2.3 | Commit entre L214-L256, verify via `exploration_cycles`, verdict dans `attestations` |
| 8 | Global | Estimation révisée : 15-21h total, 10-14h sans R-2.2.3 |

---

## Livrable

Un `PLAN_TACTIQUE_R2.md` corrigé intégrant les 8 corrections + les 3 décisions.
Pas d'implémentation. Juste le plan.
