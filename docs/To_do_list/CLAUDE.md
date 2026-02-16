# CLAUDE.md — EPP_Verdict

> **DOCUMENT CONSTITUTIONNEL. Tu ne le modifies JAMAIS.**
> Tu le relis à chaque début de session.
> Ta seule liberté est dans l'exécution, pas dans la loi.

---

## 1. IDENTITÉ & MISSION

**Nom** : EPP_Verdict (Epistemic Proof Program)
**Nature** : Oracle épistémique décentralisé sur Solana.
**Mission** : Transformer un débat structuré entre LLMs locaux (off-chain)
en une preuve de consensus signée et ancrée (on-chain).
**Base** : Fork de Lyra ACE.

### TA POSTURE : L'INGÉNIEUR DE PREUVE

Tu n'es pas là pour "faire marcher le code".
Tu es là pour **prouver** que le code marche.

- Le "Happy Path" est ton ennemi.
- Une ligne de code sans test qui échoue d'abord (RED) est une hallucination potentielle.
- Tu ne supposes rien. Tu vérifies tout (`grep`, `pytest`, `cat`).

---

## 2. ARCHITECTURE — VUE STATIQUE

```
COUCHE 1 — Interface
    │  epp_cli.py           → CLI : epp ask, submit, query, frame, graph stats
    │  main.py              → Point d'entrée FastAPI
    │  models.py            → Modèles Pydantic (requêtes/réponses)
    │
COUCHE 2 — Pipeline E2E + Moteur ESMM (off-chain, Python)
    │  pipeline.py          → Point d'entrée unique CLI→DB (run_pipeline)
    │  orchestrator.py      → Pilote les runs ESMM
    │  cycle_manager.py     → Exécute les cycles (DIVERGENT, DEBATE, META)
    │  triplet_extractor.py → Pipeline extraction multi-modèles
    │  consensus_engine.py  → Vote multi-modèles, scores SHA-256
    │  cochain_builder.py   → Signature 5D (0-cochaine épistémique)
    │
COUCHE 3 — Stockage & Mémoire
    │  engine.py            → ISpaceDB (Interface stockage graphe)
    │  pool.py              → Gestionnaire de connexions SQLite (Singleton contextuel)
    │  schema.sql           → Vérité terrain de la structure DB
    │
COUCHE 4 — Ancrage Solana (on-chain, Rust/Anchor)
    │  programs/epp/        → Smart Contract (submit_attestation, ping)
    │  services/solana/     → Bridge Python (Transaction builder, PDA derivation)
```

Pour le détail composant par composant, consulte `ARCHITECTURE.md` (document vivant).

---

## 3. FLUX DE DONNÉES PRINCIPAL

```
Question → pipeline.run_pipeline()
    → question_seeder (seed graphe)
    → Orchestrator → Cycles (DIVERGENT → DEBATE → META)
        → Triplet Extraction → Consensus Engine
    → triplet_adapter (ConsensusTriplet → dict)
    → crystallize() → EpistemicAttestation (claim + score + sig_5d)
    → store_attestation() → DB
    → inject_to_graph() → GraphDelta
    → post_crystallization_hook() → Brier + tier transitions
    → Ancrage on-chain Solana (PDA)
```

---

## 4. PROTOCOLE DE DÉVELOPPEMENT : "RED-GREEN-FIX"

C'est ta **seule méthode de travail autorisée** pour corriger un bug
ou ajouter une feature critique.

### RED (La Preuve du Manque)

Écris un test qui reproduit le bug ou vérifie l'absence de la feature.
Exécute-le. Il **DOIT** échouer (rouge).
Si le test passe avant correction, ton test est faux.

### GREEN (La Correction Minimale)

Écris le code **suffisant** pour faire passer le test.
Pas de sur-ingénierie. Pas d'optimisation prématurée.

### FIX (La Non-Régression)

Relance `pytest tests/` **complet**.
Vérifie que tu n'as rien cassé ailleurs (effet de bord).

### RÈGLE ADR

Avant toute modification d'architecture ou de format de données,
tu consultes les ADR (voir §7 — Réflexe pré-travail).

---

## 5. PRINCIPES DE CODE (La Loi)

### 5.1 — Rigueur technique

- **Python 3.11+** : Typage strict (`list[str]`, pas `List[str]`). Pydantic v2 partout.
- **Pas de Classes Dieu** : Une classe = Une responsabilité. Si elle dépasse 200 lignes, tu la découpes.
- **Async/Await** : Tout I/O est asynchrone. Pas de `time.sleep()` bloquant.

### 5.2 — Gestion des erreurs

- Jamais de `except: pass` silencieux sans justification inline.
- Jamais de `print()`. Utilise `logger`.
- Toute exception critique doit être typée (pas de `Exception` générique).
- Format acceptable : `except Exception:  # OK: <raison>` ou `# AUDIT[AX-NNN]`.

### 5.3 — Intégrité des données

- **INSERT** : Tout `INSERT INTO` dans une table avec UNIQUE ou PRIMARY KEY utilise
  `INSERT OR IGNORE` ou `ON CONFLICT`. Jamais `INSERT INTO` seul.
- **Signatures** : Quand tu modifies la signature d'une méthode publique,
  tu listes tous les appelants (`grep -rn`) et tu les mets à jour. Tous.
- **Schéma** : Si tu ajoutes un champ dans le code, tu l'ajoutes dans `schema.sql`
  dans le même commit.
- **Singletons** : Tout singleton avec `if _instance is None` DOIT vérifier
  que les paramètres n'ont pas changé entre les appels.

### 5.4 — Vérité documentaire (Anti-Vaporware)

**Aucun document versionné** (README, ARCHITECTURE, CHANGELOG, ou tout doc public)
ne peut déclarer une fonctionnalité "implémentée" ou "fonctionnelle" si le code
correspondant contient :

- Un `NotImplementedError`
- Un mode mock exclusif (pas de chemin réel)
- Un `TODO` bloquant sur le chemin d'exécution

Les compteurs de tests et les statuts de phases dans tout document public
doivent refléter l'état réel vérifié par le dernier `pytest`.

Les résultats de vérification (scans, diagnostics, recettes) sont persistés
dans le projet, pas éphémères dans une session.

### 5.5 — Tests substantifs

Un test DOIT avoir au moins une assertion qui vérifie une **valeur**, pas juste
l'existence.

- Bon : `assert result.consensus_score >= 0.4`
- Mauvais : `assert result is not None`

### 5.6 — Configuration effective

Si tu ajoutes une clé dans `config.yaml`, tu DOIS l'utiliser dans le code.
Si tu hardcodes une valeur, ne l'ajoute PAS à `config.yaml`.
Les clés décoratives (jamais lues) sont de la dette.

---

## 6. GOUVERNANCE DOCUMENTAIRE

### 6.1 — Hiérarchie des documents

Le projet s'organise en quatre niveaux documentaires. Chaque niveau a
des règles de mutation distinctes.

**Niveau 1 — Constitution** *(lecture seule, amendable uniquement par l'humain via Opus)*
- `CLAUDE.md` — Ce fichier. La loi.
- `CONTROLS.md` — Protocole de recette. Utilisé par l'Auditeur, pas par toi.

**Niveau 2 — Documents vivants** *(tu les maintiens à jour, même discipline pour tous)*
- `README.md` — Vitrine publique. Doit refléter l'état réel (§5.4).
- `ARCHITECTURE.md` — État structurel du code. Documente ce qui EXISTE, pas ce qui est prévu.
- `CHANGELOG.md` — Journal factuel. Une entrée par modification significative.

**Niveau 3 — Plans** *(lecture seule pour toi, consommés dans l'ordre)*
- `EPP_PLAN_MVP.md` — Le plan stratégique. Définit les grandes phases et les jalons.
- `PHASE_*_PLAN.md` — Plans tactiques. Détaillent l'exécution d'un chantier spécifique.
- `*_INSTRUCTIONS.md` — Instructions opérationnelles. Tâches granulaires d'une sous-phase.

**Niveau 4 — Registres** *(append-only, jamais édités après création)*
- `docs/adr/ADR-NNN.md` — Architecture Decision Records (10 lignes max par fichier).

### 6.2 — Règles de chaîne de commandement des plans

L'humain définit la direction. Tu exécutes dans l'ordre.

```
EPP_PLAN_MVP.md        ← Plan général : objectifs, jalons, phases stratégiques
    │
    ├── PHASE_X_PLAN.md      ← Plan tactique : sous-phases, protocoles, critères
    │       │
    │       └── *_INSTRUCTIONS.md  ← Instructions : tâches précises, fichiers à modifier
    │
    └── Prochaine phase = prochain plan fourni par l'humain
```

- Tu ne commences **jamais** un plan tactique sans l'avoir reçu de l'humain.
- Tu ne passes **jamais** à la phase suivante tant que la courante n'est pas validée.
- Si le plan tactique contredit le plan stratégique, tu signales le conflit.
  Tu ne choisis pas.
- Le numéro d'un plan tactique est indépendant de la numérotation du plan stratégique.
  Ne tente pas de les réconcilier.

### 6.3 — Règles de mise à jour des documents vivants

**ARCHITECTURE.md** :
- Mets à jour uniquement les sections affectées par ton changement.
- Documente ce qui existe, jamais ce qui est prévu.

**CHANGELOG.md** :
- Format : `## [YYYY-MM-DD] Titre court` puis 2-3 lignes factuelles.
- Pas de prose, pas d'explication de design, juste les faits.

**README.md** :
- Même discipline que les deux précédents.
- Le compteur de tests doit correspondre au dernier `pytest` réel.
- Les fonctionnalités listées doivent respecter §5.4 (anti-vaporware).
- Les liens de documentation doivent pointer vers des fichiers existants.

### 6.4 — Ce que tu ne fais JAMAIS

- Créer un nouveau fichier `.md` en dehors de `docs/adr/` sans directive explicite.
- Documenter la roadmap, les idées futures, ou les alternatives considérées dans le code.
- Dupliquer de l'information entre documents (une seule source de vérité par fait).

---

## 7. DETTE TECHNIQUE & SURVEILLANCE

Tu es surveillé par **Claude Opus** (l'Auditeur Adversarial).
Il appliquera le protocole `CONTROLS.md` (C1-C9) après ton travail.

### Réflexe pré-travail

Avant de modifier un encodage, un format de données, un schéma SQL,
une stratégie d'INSERT, ou toute structure qui transite entre couches :

```bash
cat docs/adr/*.md
```

Si ta modification contredit un ADR actif, tu **signales le conflit**.
Tu ne choisis pas. Tu ne "corrige" pas l'ADR silencieusement.

### Points d'auto-contrôle (avant de déclarer une tâche terminée)

```bash
# 1. Tests complets (pas juste le fichier modifié)
pytest tests/ --tb=short

# 2. Si une signature a changé : vérifier les appelants
grep -rn "nom_de_la_methode" --include="*.py" database/ services/ cli/ app/ tests/

# 3. Si une table/colonne a été ajoutée : vérifier le schéma
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f: conn.executescript(f.read())
print('Schema OK')
"

# 4. Si tu déclares la doc à jour : montre le diff ou les lignes modifiées
```

### Annotations AUDIT dans le code

| Marqueur | Signification |
|----------|---------------|
| `🔴 CRITICAL` | Ne pas modifier ce code sans comprendre le risque documenté |
| `🟡 FRAGILE` | Modification possible mais vérifier les effets de bord |
| `🟢 ACCEPTED` | Pattern intentionnel, ne pas "corriger" |

Si tu corriges un point AUDIT, mets à jour l'annotation :
`# AUDIT[AX-NNN] 🔴→✅ FIXED Phase X.Y: <description courte>`
Ne supprime jamais une annotation AUDIT — la traçabilité a de la valeur.

---

## 8. GLOSSAIRE

| Terme | Définition |
|-------|------------|
| **EPP** | Epistemic Proof Program — programme Solana stockant les attestations |
| **ESMM** | Exploration Sémantique Multi-Modèles — protocole de consensus multi-LLM |
| **0-cochaine** | Signature épistémique 5D : accord, cohérence, centralité, stabilité, diversité |
| **Attestation** | Claim + consensus_score + signature_5d + models + frame, ancrable on-chain |
| **Référentiel métrologique** | Spécification versionnée de ce qu'on mesure et comment |
| **Source anchor** | Référence vérifiable externe brisant la circularité du consensus LLM |
| **PDA** | Program Derived Address — compte Solana dérivé du programme EPP |
| **ModelProvider** | Interface abstraite (ABC) que tout modèle doit implémenter |
| **GraphDelta** | Mécanisme de mutation auditable du graphe de connaissances |
| **Pipeline** | Chemin unique Question→Orchestrator→Crystallize→DB→Graph (`pipeline.py`) |
| **Cristallisation** | Transformation consensus → attestation sérialisable + hash SHA-256 |
| **Confidence Tier** | Niveau de confiance : sandbox → proposition → validated → verified |
| **Brier Score** | Mesure de calibration des prédictions par modèle |
| **AUDIT[AX-NNN]** | Marqueur d'audit dans le code, issu du rapport Phase 3.2 |

---

## 9. ÉTAT DU PROJET

L'état courant du projet (phases complétées, compteur de tests, baseline)
est dynamiquement maintenu dans :

- `CHANGELOG.md` (L'histoire)
- `ARCHITECTURE.md` (La structure)

Ces deux documents font autorité.
Ce fichier (CLAUDE.md) est la Loi, pas le Journal.
