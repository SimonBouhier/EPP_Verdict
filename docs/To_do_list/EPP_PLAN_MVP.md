# EPISTEMIC PROOF PROGRAM — Plan de Développement MVP

## Oracle Épistémique Décentralisé sur Solana

**Version** : 2.4
**Date** : 15 février 2026
**Statut** : Plan MVP — Hackathon Colosseum
**Périmètre** : Exclusivement l'oracle épistémique. L'agent de trading est un projet privé séparé.

---

## TABLE DES MATIÈRES

1. [Vision & Périmètre](#1-vision--périmètre)
2. [Axiomes Fondateurs](#2-axiomes-fondateurs)
3. [Architecture MVP](#3-architecture-mvp)
4. [Phases de Développement](#4-phases-de-développement)
5. [Stratégie Colosseum](#5-stratégie-colosseum)
6. [Compétences Humaines](#6-compétences-humaines)
7. [Registre des Risques](#7-registre-des-risques)
8. [Annexes Techniques](#8-annexes-techniques)

---

## 1. VISION & PÉRIMÈTRE

### 1.1 — Le produit en une phrase

> Soumets une question. Des modèles débattent en local. Une preuve de consensus signée est postée on-chain.

### 1.2 — Ce que c'est

Un **Epistemic Proof Program** (EPP) sur Solana : un protocole qui transforme le débat structuré entre LLMs locaux en attestations épistémiques vérifiables, ancrées on-chain. Chaque attestation porte une signature 5D (0-cochaine) qui encode non pas juste l'accord, mais la *qualité* de cet accord.

Combiné à un graphe de connaissances (RAG) qui s'enrichit à chaque attestation validée, le système construit une base de vérité décentralisée, transparente et croissante.

### 1.3 — Ce que ce n'est PAS

- ❌ Un agent de trading (projet privé séparé)
- ❌ Un wrapper autour d'un seul LLM
- ❌ Un oracle de prix (Chainlink, Pyth existent)
- ❌ Un prediction market (Polymarket existe)
- ❌ Un chatbot on-chain

### 1.4 — Le flux fondamental

```
   Utilisateur / Smart Contract / Agent externe
                    │
                    ▼
   ┌────────────────────────────────┐
   │  1. SOUMISSION                 │
   │  Question + référentiel        │
   │  métrologique applicable       │
   │  (+ paiement en SOL/token)     │
   └───────────────┬────────────────┘
                   ▼
   ┌────────────────────────────────┐
   │  2. DÉBAT LOCAL (ESMM)         │
   │  N modèles locaux/API          │
   │  Divergent → Débat → Méta      │
   │  Extraction de triplets        │
   │  Calcul de consensus           │
   │  Signature épistémique 5D      │
   │  ⚠ Tout se passe off-chain     │
   └───────────────┬────────────────┘
                   ▼
   ┌────────────────────────────────┐
   │  3. CRISTALLISATION            │
   │  Attestation compacte :        │
   │  claim + consensus_score +     │
   │  signature_5d + modèles +      │
   │  frame_ref + timestamp         │
   └───────────────┬────────────────┘
                   ▼
   ┌────────────────────────────────┐
   │  4. ANCRAGE ON-CHAIN           │
   │  Transaction Solana (devnet)   │
   │  Attestation stockée en PDA    │
   │  Requêtable par tout programme │
   └───────────────┬────────────────┘
                   ▼
   ┌────────────────────────────────┐
   │  5. ENRICHISSEMENT RAG         │
   │  Triplets validés intégrés     │
   │  au graphe de connaissances    │
   │  Revalidation future possible  │
   └────────────────────────────────┘
```

### 1.5 — Pourquoi c'est nouveau

| Existant | EPP |
|----------|-----|
| Chainlink/Pyth : consensus sur des **chiffres** (prix, données) | Consensus sur des **affirmations** (ce claim est-il fondé ?) |
| Polymarket : humains votent sur des **événements binaires** | LLMs débattent sur des **questions ouvertes** avec nuance |
| AI agents Solana : un LLM connecté à des outils DeFi | Infrastructure de **confiance épistémique** sous-jacente |
| RAG classique : un modèle, une base, pas de vérification | RAG **validé par consensus multi-modèles**, croissant |

---

## 2. AXIOMES FONDATEURS

### AXIOME 1 — Obsolescence permanente des modèles

Aucun modèle n'est un composant. Tout modèle est un consommable. La valeur réside dans le protocole ESMM, le graphe attesté et la signature 5D. Tout modèle qui respecte le contrat d'interface entre dans le système sans modification.

### AXIOME 2 — Le graphe survit à tout

Les modèles passent, le graphe reste. Chaque attestation porte la trace de ses producteurs mais ne dépend pas de leur survie. De nouveaux modèles revalident d'anciennes attestations. La valeur s'accumule dans le graphe, jamais dans un modèle.

### AXIOME 3 — Transparence des coupures de régression

Toute chaîne de validation s'arrête quelque part. Chaque point d'arrêt est explicite, versionné, contestable et gouvernable. Pas de vérité cachée — des choix assumés et publiés.

### AXIOME 4 — Calcul local, preuve on-chain

Le débat ESMM est trop lourd et trop riche pour la blockchain. Seul le résultat cristallisé — l'attestation compacte — va on-chain. La blockchain ne sert pas à calculer le consensus mais à le **certifier et le rendre requêtable**.

### Ce qui est stable vs ce qui est jetable

| Stable & permanent (patrimoine) | Interchangeable & jetable (consommables) |
|----------------------------------|------------------------------------------|
| Protocole ESMM | Tout modèle LLM spécifique |
| Graphe de connaissances attestées | Tout provider d'API |
| Signatures épistémiques 5D | Tout modèle d'embedding (avec migration) |
| Référentiels métrologiques | Toute infra de déploiement |
| Contrat d'interface des modèles | — |
| Programme Solana (EPP) | — |

---

## 3. ARCHITECTURE MVP

### 3.1 — Composants

```
┌──────────────────────────────────────────────────────────────┐
│                     COUCHE PRÉSENTATION                       │
│  CLI (MVP) → API REST (v2) → Frontend web (v3)              │
│  Soumission de questions, consultation du graphe             │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│                     MOTEUR ESMM (off-chain)                   │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Adaptateur  │  │ Adaptateur  │  │ Adaptateur  │  ← Contrat│
│  │ Ollama      │  │ OpenAI-     │  │ Anthropic   │    d'inter-│
│  │ (local)     │  │ compatible  │  │ (API)       │    face   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └────────────────┼────────────────┘                   │
│                          ▼                                    │
│  ┌──────────────────────────────────────────┐                │
│  │        Orchestrateur ESMM                 │                │
│  │  1. Distribution (query → N modèles)      │                │
│  │  2. Phase divergente (réponses isolées)   │                │
│  │  3. Phase débat (confrontation)           │                │
│  │  4. Phase méta (réflexion sur le débat)   │                │
│  │  5. Extraction de triplets                │                │
│  │  6. Calcul de consensus                   │                │
│  │  7. Signature épistémique 5D              │                │
│  │  8. Cristallisation → Attestation         │                │
│  └──────────────────┬───────────────────────┘                │
│                     │                                         │
│  ┌──────────────────┴───────────────────────┐                │
│  │        Graphe de connaissances (RAG)      │                │
│  │  SQLite (MVP) → Graph DB (scaling)        │                │
│  │  Triplets + signatures + historique       │                │
│  │  Requêtable par sujet, confiance, frame   │                │
│  └──────────────────────────────────────────┘                │
└──────────────────────────┬───────────────────────────────────┘
                           │ Attestation compacte
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   COUCHE SOLANA (on-chain)                     │
│                                                               │
│  ┌──────────────────────────────────────────┐                │
│  │     Epistemic Proof Program (Anchor)      │                │
│  │                                           │                │
│  │  Instructions :                           │                │
│  │  • submit_attestation(claim, score,       │                │
│  │    signature_5d, models, frame, anchor)   │                │
│  │  • query_attestations(subject, min_score) │                │
│  │  • challenge_attestation(id, evidence)    │                │
│  │  • revalidate_attestation(id, new_data)   │                │
│  │                                           │                │
│  │  Stockage : PDAs indexées par claim hash  │                │
│  └──────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 — Contrat d'interface universel des modèles

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class StructuredQuery:
    question: str
    context: Optional[str] = None        # Contexte RAG injecté
    metrological_frame: Optional[str] = None
    response_format: str = "triplets"    # triplets | analysis | boolean

@dataclass
class StructuredResponse:
    raw_text: str
    triplets: list[tuple[str, str, str]]
    confidence: float
    reasoning_trace: str                 # Pour le débat

@dataclass
class ModelMetadata:
    provider_id: str                     # "ollama_mistral7b", "api_kimi_k25"
    architecture_family: str             # "transformer_dense", "transformer_moe"
    parameter_count: Optional[int]
    training_data_epoch: Optional[str]

class ModelProvider(ABC):
    """Interface universelle. Tout modèle actuel ou futur
    qui implémente ce contrat entre dans le système."""

    @abstractmethod
    def respond(self, query: StructuredQuery) -> StructuredResponse:
        pass

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        pass
```

### 3.3 — Structure d'une attestation on-chain

```rust
// Programme Anchor (Solana) — programmes/epp/programs/epp/src/state.rs
// PDA seeds: [b"attestation", submitter, claim_hash]
#[account]
pub struct EpistemicAttestation {
    // PDA
    pub bump: u8,                            // 1 byte
    pub submitter: Pubkey,                   // 32 bytes

    // Identifiant
    pub claim_hash: [u8; 32],                // SHA-256(subject|predicate|object|frame)

    // Contenu (fixed-size, zero-padded UTF-8)
    pub subject: [u8; 64],                   // MAX_SUBJECT_LEN
    pub predicate: [u8; 64],                 // MAX_PREDICATE_LEN
    pub object: [u8; 128],                   // MAX_OBJECT_LEN

    // Consensus
    pub consensus_score: u16,                // 0-10000 (score × 10000)
    pub models_consulted: u8,
    pub models_agreeing: u8,

    // Signature épistémique 5D (0-cochaine)
    pub sig_agreement: u16,                  // 0-10000
    pub sig_semantic_consistency: u16,
    pub sig_centrality: u16,
    pub sig_stability: u16,
    pub sig_relation_diversity: u16,

    // Classification
    pub epistemic_type: u8,                  // 0=Foundational, 1=Bridge, 2=Specialized, 3=Generalist, 4=Hybrid
    pub confidence_tier: u8,                 // 0=sandbox, 1=proposition, 2=validated, 3=verified

    // Référence métrologique
    pub frame_hash: [u8; 32],                // SHA-256 du MetrologicalFrame JSON (0x00 si absent)
    pub source_anchor: [u8; 32],             // SHA-256 source vérifiable externe (0x00 si absent)

    // Temporel
    pub timestamp: i64,
    pub last_revalidated: i64,
    pub validation_count: u16,

    // Protocole
    pub protocol_version: u16,               // Ex: 100 = v1.0.0

    // Challenge
    pub is_challenge: bool,
    pub challenged_attestation: Pubkey,       // Pubkey::default() si pas un challenge
}
// Taille : 8 (discriminator) + 454 = 462 bytes → coût Solana ~0.003 SOL par attestation
```

### 3.4 — Coupures de régression

```
Niveau 5 : Gouvernance
    │  Phase MVP : équipe fondatrice (transparent, forkable)
    │  Phase future : panel d'experts → DAO
    ▼
Niveau 4 : Référentiels métrologiques
    │  Versionnés. Définissent CE QU'ON MESURE.
    │  Publiés on-chain. Contestables.
    ▼
Niveau 3 : Critères d'inclusion des modèles
    │  Diversité architecturale mesurée (corrélation d'erreurs)
    │  Track record minimum (Brier score)
    │  Anti-Sybil (pondération par diversité, pas par nombre)
    ▼
Niveau 2 : Pool de modèles validés
    │  Avec Brier scores historiques
    │  Entrée/sortie dynamique selon performance
    ▼
Niveau 1 : Attestations épistémiques
    │  Consensus + signature 5D + ancrage source
    │  Résultat cristallisé, compact, requêtable on-chain
    ▼
Niveau 0 : Consommateurs
    Smart contracts, agents, protocoles, utilisateurs
```

---

## 4. PHASES DE DÉVELOPPEMENT

---

### PHASE 0 — SOCLE TECHNIQUE (Semaines 1-3)

**Objectif** : Noyau ESMM découplé, interchangeable, fonctionnel.

#### 0.1 — Contrat d'interface universel ✅ TERMINÉ

- [x] Classe abstraite `ModelProvider` en Python → `services/providers/base.py`
- [x] Adaptateur Ollama (modèles locaux : Mistral, LLaMA, Qwen, Gemma) → `services/providers/ollama.py`
- [x] Adaptateur OpenAI-compatible (Kimi K2.5, DeepSeek, etc.) → `services/providers/openai_compat.py`
- [x] Adaptateur Anthropic (Claude via API) → `services/providers/anthropic.py`
- [x] Suite de tests d'intégration : 55 tests (`test_providers.py` + `test_rotator.py`)
- [x] Mécanisme de fallback → `MultiProviderRotator` avec rotation automatique
- [x] Registre de modèles dynamique → `services/providers/registry.py`

**Critère de validation** : ✅ Cycles ESMM fonctionnels avec `MultiProviderRotator` provider-agnostique.

#### 0.2 — Migration embedding sans perte ✅ TERMINÉ

- [x] Versioning des embeddings → table `concept_embeddings` (concept_id, model_id, dimension, embedding)
- [x] Pipeline de migration progressive → `tools/migrate_embeddings.py` (--dry-run, --finalize, --rollback)
- [x] Coexistence de vecteurs multi-versions → `UNIQUE(concept_id, model_id)` permet N versions par concept
- [x] Recherche par modèle → `get_concepts_with_embeddings_for_model()` (pas de mélange dimensions)
- [x] Traçabilité → table `embedding_migrations` (from_model, to_model, status, stats)
- [x] Config → `config.yaml::embeddings` (active_model, fallback_reembed, similarity_min_score)
- [x] Tests : 45 tests unitaires (`test_phase02_*.py`)

**Critère de validation** : ✅ Changement de modèle sans perte — embeddings versionnés, migration traçable.

#### 0.3 — ESMM refactoré et découplé ✅ TERMINÉ

- [x] Zéro référence directe à un modèle ou API spécifique dans le code ESMM
- [x] Pipeline complet : Query → Divergent → Débat → Méta → Triplets → Consensus → Signature 5D
- [x] Sérialisation des attestations (JSON portable + hash SHA-256) → `services/esmm/attestation.py`
- [x] Logs structurés de chaque phase (pour démo et debugging) → `services/esmm/run_logger.py`
- [x] Mode replay : `RevalidationInput` pour rejouer avec des modèles différents
- [x] Table `attestations` (table 19) avec méthodes CRUD dans `engine.py`
- [x] Tests : 65 tests unitaires + intégration (`test_phase03_*.py`)

**Critère de validation** : ✅ Protocole ESMM produit des attestations complètes avec signature 5D en utilisant uniquement l'interface `ModelProvider`.

---

### PHASE 1 — PREUVE ON-CHAIN (Semaines 4-6) ✅ TERMINÉ

**Objectif** : Soumettre une question, débattre localement, poster une attestation sur le devnet Solana.

#### 1.1 — Programme Solana (Anchor/Rust) ✅ TERMINÉ

- [x] Setup environnement Anchor + Solana CLI
- [x] Instruction `submit_attestation` : stocke une attestation en PDA → `programs/epp/programs/epp/src/lib.rs`
- [x] Instruction `ping` : test de connectivité → `programs/epp/programs/epp/src/lib.rs`
- [ ] Instruction `query_attestations` : requête par sujet et/ou score minimum
- [ ] Instruction `challenge_attestation` : mécanisme de contestation basique
- [x] Tests sur localnet → `anchor test` passe (ping)
- [x] Programme ID : `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`
- [x] Build OK : `epp.so` (221 KB) + IDL

**Critère de validation** : ✅ Programme Anchor compile et passe les tests localnet. Déploiement devnet en attente.

#### 1.2 — Client Solana (Python) ✅ TERMINÉ

- [x] Client Python pour signer et envoyer les transactions → `services/solana/client.py`
- [x] Bridge Python → Anchor (float↔u16, string↔bytes) → `services/solana/bridge.py`
- [x] Sérialisation attestation Python → format Anchor
- [x] Mode mock pour tests sans validator → `client.py` mock mode
- [x] PDA derivation : `[b"attestation", submitter, claim_hash]`
- [ ] Vérification : relecture on-chain de l'attestation postée

#### 1.3 — Référentiels métrologiques (v1) ✅ TERMINÉ

- [x] Structure `MetrologicalFrame` (Pydantic + SHA-256 hash) → `services/solana/metrological_frame.py`
- [x] Premier référentiel concret : `blockchain_tps_v1.0` + `general_knowledge_v1.0`
- [x] Stockage off-chain (SQLite table `metrological_frames`) avec hash
- [x] Seeding automatique lors de `ISpaceDB.initialize()`
- [ ] Documentation publique de chaque frame

#### 1.4 — CLI de démonstration ✅ TERMINÉ

- [x] Commande : `epp ask "..."` → pipeline ESMM complet → `cli/epp_cli.py`
- [x] Commande : `epp submit <claim_hash> --devnet` (poste on-chain)
- [x] Commande : `epp query <subject>` (consulte le graphe)
- [x] Commande : `epp frame list` / `epp frame show <id>` (cadres métrologiques)
- [x] Commande : `epp graph stats` (état du RAG)
- [ ] Affichage du débat en temps réel (phases ESMM)

**Critère de validation** : ✅ CLI fonctionnel (ask → submit → query → frame → graph). Tests : 83 passed, 9 skipped.

---

### PHASE 2 — ROBUSTESSE & DÉMO (Semaines 7-10) 🔧 EN COURS

**Objectif** : Fiabiliser, enrichir le RAG, préparer la soumission hackathon.

> **Note** : Les Phases 3-3.3 (pipeline E2E, audit, ADR) et 4.0-4.7 (corrections systématiques,
> sécurité, Solana devnet complet, peaufinage) du CHANGELOG correspondent au travail de
> robustesse de cette Phase 2 du plan. 487 tests, 0 failed, 8 ADR, 15 annotations AUDIT FIXED.

#### 2.1 — Track record et calibration des modèles ✅ TERMINÉ

- [x] Brier score par modèle → table `model_track_record` + vue `v_model_brier_scores`
- [x] Mesure de diversité inter-modèles → `infer_architecture_family()` dans `base.py`
- [x] Confidence tiers multi-critères : sandbox/proposition/validated/verified
- [x] Méthodes DB : `record_model_prediction()`, `resolve_prediction()`, `get_model_brier_score()`
- [x] Audit tier transitions : table `tier_transitions` + `log_tier_transition()`
- [x] Pondération dynamique des votes selon track record → R-2.1.1 (Brier → `model_weights` propagé dans le consensus)
- [x] Dashboard ou rapport : performance de chaque modèle dans le pool → R-2.1.2 (commande `epp models stats`)

#### 2.2 — Anti-Sybil et intégrité du consensus ✅ TERMINÉ

- [x] Diversité architecturale mesurée via `infer_architecture_family()`
- [x] `infer_architecture_family()` durci : first-token match, provider prefix strip (Phase 4.5)
- [x] Tous les providers (ollama, anthropic, openai_compat) délèguent à `infer_architecture_family()` (Phase 4.7)
- [x] Prompt injection : XML boundary delimiters, `_sanitize_concept()` (Phase 4.5)
- [x] Pipeline input validation : MAX_QUESTION_LENGTH=5000, control char stripping (Phase 4.5)
- [x] Protocole commit-reveal basique → R-2.2.3 (table `commit_reveal` + CRUD + vérification post-crystallize)
- [x] Détection de réponses quasi-identiques (clustering d'embeddings) → R-2.2.2 (`response_deduplicator.py`, pénalité similarité cosinus)
- [x] Pondération par diversité mesurable, pas par nombre de voix → R-2.2.1 (bonus `diversity_bonus_factor` post-crystallize)

#### 2.3 — Enrichissement du RAG

- [ ] Campagne de questions sur domaines variés (blockchain, tech, science)
- [ ] Masse critique : viser 500+ triplets attestés dans le graphe
- [ ] Revalidation : soumettre d'anciens triplets à de nouveaux modèles
- [ ] Visualisation du graphe (export vers outil de visualisation)
- [ ] Requêtes composées : "Que sait le graphe sur X relié à Y avec confiance > Z ?"

#### 2.4 — Scénarios de démonstration (partiellement fait)

- [x] **3 scénarios de base** créés dans `demos/` avec MockProviders + pipeline réel
- [ ] **Scénario 1 — Correction factuelle** : Soumettre un claim faux connu, montrer que le consensus le rejette
- [ ] **Scénario 2 — Attestation vérifiable** : Claim sur métrique blockchain, vérification contre données réelles
- [ ] **Scénario 3 — Enrichissement du RAG** : Série de questions → sous-graphe cohérent
- [ ] **Scénario 4 — Résilience aux modèles** : Même question avec 3 sets de modèles différents
- [ ] **Scénario 5 — Requête on-chain** : Un programme Solana tiers consomme une attestation EPP

#### 2.5 — Préparation vidéos

- [ ] Script vidéo pitch (3 min) : problème → solution → démo → vision
- [ ] Script vidéo technique (3 min) : architecture → code → flux → résultat on-chain
- [ ] Enregistrement et montage
- [x] README GitHub professionnel avec schémas d'architecture

**Critère de validation** : Les 5 scénarios de démo fonctionnent. Les vidéos sont prêtes. Le repo est soumissible.

---

### PHASE 3 — POST-HACKATHON / SCALING (Semaines 11+)

**Objectif** : Itérer selon le feedback, construire vers le produit.

#### 3.1 — Itération post-feedback

- [ ] Intégrer les retours du panel Eternal (si soumission Eternal)
- [ ] Affiner le positionnement pour le Spring Hackathon (6 avril)
- [ ] Identifier les faiblesses pointées par les juges

#### 3.2 — API publique

- [ ] API REST pour soumettre des questions et consulter le graphe
- [ ] Documentation OpenAPI
- [ ] Rate limiting, authentification
- [ ] Premiers utilisateurs beta

#### 3.3 — Modèle économique

- [ ] Paiement par attestation (SOL ou token)
- [ ] Tarification par profondeur ESMM (quick check vs protocole complet)
- [ ] Rémunération des opérateurs de modèles (proportionnelle à la diversité)
- [ ] Micro-paiements pour requêtes sur le graphe existant

#### 3.4 — Couches d'usage

| Couche | Description | Priorité |
|--------|-------------|----------|
| **Benchmarking décentralisé** | Métriques blockchain attestées | Haute — premier use case |
| **Vérification factuelle** | Analyse de whitepapers, claims techniques | Haute |
| **Réputation quantifiée** | Score de santé blockchain composé | Moyenne |
| **Assurances DeFi** | Triggers sur seuils attestés | Future |
| **Gouvernance algorithmique** | Ajustement de paramètres via attestations | Future |

#### 3.5 — Décentralisation progressive

- [ ] Gouvernance Phase 1 : équipe fondatrice (transparente, forkable)
- [ ] Gouvernance Phase 2 : panel d'experts (type comité IEEE)
- [ ] Gouvernance Phase 3 : DAO pour référentiels et critères d'inclusion
- [ ] Mécanisme formel de contestation d'attestations

---

## 5. STRATÉGIE COLOSSEUM

### 5.1 — Calendrier

| Étape | Dates | Action |
|-------|-------|--------|
| **Phase 0-1** | Semaines 1-6 | Socle technique + preuve on-chain |
| **Soumission Eternal** | Semaine 7-8 | Sprint soumission (vidéos + repo) |
| **Phase 2** | Semaines 7-10 | Robustesse + scénarios pendant l'attente |
| **Réponse Eternal** | ~14 jours après | Feedback ou offre accélérateur |
| **Spring Hackathon** | 6 avril — 11 mai | Version enrichie avec feedback intégré |

**Stratégie** : Soumission Eternal dès que la Phase 1 est solide. Itération continue jusqu'au Spring Hackathon.

### 5.2 — Soumission Eternal — checklist

- [ ] Nom du produit : **Epistemic Proof Program** (EPP)
- [ ] Description : Oracle de consensus épistémique multi-LLM sur Solana
- [ ] Background équipe
- [ ] Repo GitHub (code fonctionnel, README avec schémas)
- [ ] Vidéo pitch 3 minutes
- [ ] Walkthrough technique 3 minutes
- [ ] Soumission sur colosseum.org

### 5.3 — Positionnement

**Track principal** : Artificial Intelligence ($2,500–$25,000)
**Track secondaire** : Infrastructure
**Prix additionnel visé** : Public Goods Award ($10,000) — infrastructure ouverte

**Différenciation vs l'existant** :

| Projets AI Solana actuels | EPP |
|---------------------------|-----|
| Agents qui *utilisent* la DeFi | Infrastructure de *confiance* pour ces agents |
| Couplés à un modèle/provider | Agnostique — les modèles sont des consommables |
| Single-LLM, pas de vérification | Consensus multi-modèles avec preuve |
| Pas de mémoire persistante vérifiable | Graphe de connaissances attesté, croissant |

### 5.4 — Enjeux

- Tous les gagnants interviewés pour l'accélérateur
- Accélérateur : 6 semaines + **$250K pré-seed**
- Fond de $60M pour startups Colosseum

---

## 6. COMPÉTENCES HUMAINES

### 6.1 — Ce que le fondateur couvre

- Architecture système et design de protocoles (ESMM, signatures 5D)
- Prototypage Python, FastAPI, SQLite
- Vision produit et articulation stratégique
- Connaissance des modèles open source et de l'écosystème LLM

### 6.2 — Recrutements

| Priorité | Profil | Rôle dans le MVP | Quand |
|----------|--------|-------------------|-------|
| **P0** | **Développeur Solana / Rust** | Programme Anchor, PDAs, client TypeScript, déploiement devnet. Sans ce profil, pas de composante on-chain. | Immédiat — Phase 1 impossible sans |
| **P1** | **Sécurité applicative** | Review de l'architecture, threat modeling du protocole, sécurisation des interfaces. Moins urgent que pour le trading mais nécessaire avant mainnet. | Phase 2 / pré-mainnet |

### 6.3 — Où chercher

- Forum Colosseum (co-founders pour hackathon)
- Superteam (communauté Solana)
- Solana Stack Exchange
- Hackathons précédents (participants sans projet)

---

## 7. REGISTRE DES RISQUES

### 7.1 — Risques techniques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **Corrélation des modèles** : consensus faux par données d'entraînement partagées | Critique | Source anchoring, diversité architecturale mesurée, revalidation par nouveaux modèles |
| **Latence ESMM** : cycle complet trop lent | Fort | Positionnement stratégique (pas temps-réel), niveaux de profondeur, cache |
| **Migration embedding** : perte de graphe au changement | Fort | Versioning multi-vecteurs, migration progressive (Phase 0.2) |
| **Attaque Sybil** : copies du même modèle dominent le vote | Fort | Pondération par diversité mesurable (embeddings), pas par nombre |
| **Coût on-chain** : attestations trop chères | Moyen | Compression, batching, ancrage sélectif, ~0.003 SOL/attestation estimé |
| **Scalabilité du graphe** : SQLite insuffisant à terme | Moyen | Suffisant pour le MVP (10K+ triplets), migration graph DB planifiée |

### 7.2 — Risques stratégiques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **Pas de dev Solana** : bloqué en Phase 1 | Bloquant | Recrutement immédiat, Colosseum forum, Superteam |
| **Fatigue "AI agents"** chez les juges | Moyen | Pitch sur l'infrastructure, pas sur "un agent de plus" |
| **Super-modèle unique** rend le consensus moins attractif | Fort | L'axiome d'obsolescence protège — un super-modèle est un super-consommable |

### 7.3 — Le problème de la référence

**Régression de validation** : Qui valide les modèles ? Qui définit les métriques ?

**Réponse — coupures de régression explicites :**

| Étage | Question | Réponse MVP | Réponse cible |
|-------|----------|-------------|---------------|
| Métrologique | "Qu'est-ce qu'on mesure ?" | Référentiels versionnés, publiés | Gouvernés par DAO |
| Modèles | "Pourquoi ces LLMs ?" | Track record empirique (Brier), diversité mesurée, source anchoring | Auto-sélection par performance |
| Gouvernance | "Qui décide des règles ?" | Équipe fondatrice (dogmatique mais transparent, forkable) | Panel → DAO |

**Principe** : La régression ne disparaît pas — elle est rendue transparente et gouvernable à chaque étage.

---

## 8. ANNEXES TECHNIQUES

### 8.1 — Référentiel métrologique (structure)

```json
{
    "frame_id": "blockchain_tps_v1.0",
    "version": "1.0",
    "definition_hash": "<sha256>",
    "metric": "transactions_per_second",
    "parameters": {
        "include_votes": false,
        "success_only": true,
        "window": "10min_rolling",
        "exclusions": ["downtime_gt_30s"],
        "measurement_sources": ["rpc_nodes", "block_explorers"],
        "minimum_sources": 3
    },
    "governance": {
        "current_authority": "founding_team",
        "amendment_process": "version_bump_with_changelog",
        "target_authority": "dao_vote"
    }
}
```

### 8.2 — Infrastructure modèles

**Modèles locaux (Ollama, hardware modeste) :**
- Mistral 7B / Nemo 12B
- LLaMA 3.x 8B
- Gemma 2 9B
- Qwen 2.5 7B/14B
- Tout futur modèle ≤ 14B

**APIs (haute qualité, diversité architecturale) :**
- Kimi K2.5 — MoE, $0.60/M input
- Claude Sonnet — dense, analyse nuancée
- GPT-4o-mini — coût minimal
- Tout futur provider conforme au contrat d'interface

**Règle de composition** : Minimum 3 modèles par attestation. Au moins 2 familles architecturales distinctes. Pondération par diversité mesurée.

### 8.3 — Glossaire

| Terme | Définition |
|-------|------------|
| **EPP** | Epistemic Proof Program — le programme Solana qui stocke les attestations |
| **ESMM** | Exploration Sémantique Multi-Modèles — protocole de consensus multi-LLM |
| **0-cochaine** | Signature épistémique 5D (accord, cohérence, centralité, stabilité, diversité) |
| **Attestation** | Affirmation validée par consensus avec signature et métadonnées, ancrée on-chain |
| **Référentiel métrologique** | Spécification formelle versionnée de ce qu'on mesure et comment |
| **Coupure de régression** | Point explicite où la chaîne de validation s'arrête avec justification |
| **Source anchor** | Référence vérifiable externe brisant la circularité du consensus LLM |
| **Brier score** | Métrique de calibration mesurant la qualité des prédictions d'un modèle |
| **PDA** | Program Derived Address — compte Solana dérivé du programme EPP |
| **Commit-reveal** | Protocole anti-collusion : hash avant révélation |

---

## JALONS & SUIVI

| Jalon | Semaine | Critère de validation | Statut |
|-------|---------|----------------------|--------|
| **J0** | S+2 | Interface universelle + 3 adaptateurs testés | ✅ 04/02 |
| **J1** | S+3 | ESMM découplé produit des attestations avec signature 5D | ✅ 05/02 |
| **J2** | S+4 | Migration embedding sans perte de graphe | ✅ 05/02 |
| **J3** | S+6 | Programme Anchor build + test localnet | ✅ 06/02 |
| **J4** | S+7 | CLI fonctionnel (ask → submit → query → frame → graph) | ✅ 06/02 |
| **J5** | S+8 | Infrastructure track record + confidence tiers | ✅ 08/02 |
| **J6** | S+8 | Pipeline E2E + 425 tests verts | ✅ 10/02 |
| **J6.1** | S+9 | Audit interne 51 annotations + 8 ADR | ✅ 12/02 |
| **J6.2** | S+9 | Corrections systématiques Phase 4 (470 tests) | ✅ 12/02 |
| **J6.3** | S+10 | Peaufinage Phase 4.7 (487 tests, property-based, tier sync, §5.2/§5.3) | ✅ 15/02 |
| **J7** | S+11 | 5 scénarios de démo fonctionnels | ⬜ |
| **J8** | S+9 | Vidéos pitch + technique enregistrées | ⬜ |
| **J9** | S+10 | Soumission Eternal effective | ⬜ |
| **J10** | S+14 | 500+ triplets attestés dans le graphe | ⬜ |
| **J11** | S+14 | Track record Brier sur 100+ attestations vérifiables | ⬜ |
| **J12** | S+18 | Soumission Spring Hackathon (version enrichie) | ⬜ |

---

## DÉCISIONS & JOURNAL

| Date | Décision | Justification |
|------|----------|---------------|
| 03/02/2026 | Séparation trading / oracle en deux projets distincts | Focus MVP, clarté du pitch, périmètres de risque différents |
| 03/02/2026 | MVP = Epistemic Proof Program sur Solana | Primitive nouvelle, démontrable, pas de dépendance trading |
| 03/02/2026 | Axiome d'obsolescence des modèles gravé comme fondation | Tout modèle est un consommable, la valeur est dans le protocole et le graphe |
| 03/02/2026 | Stratégie Combo : Eternal + Spring Hackathon | Double exposition, itération basée sur feedback |
| 04/02/2026 | Phase 0.1 terminée — ModelProvider interface | 4 adaptateurs (Ollama, OpenAI, Anthropic, Embeddings), 55 tests, MultiProviderRotator |
| 05/02/2026 | Phase 0.2 terminée — Embedding versioning | Tables concept_embeddings + embedding_migrations, pipeline CLI, 45 tests |
| 05/02/2026 | Phase 0.3 terminée — ESMM découplé + Cristallisation | EpistemicAttestation, RunLogger, RevalidationInput, table attestations, 65 tests |
| 06/02/2026 | Phase 1 terminée — Couche Solana MVP | Programme Anchor (submit_attestation, ping), client Python, bridge, CLI (ask/submit/query/frame/graph), 83 tests |
| 08/02/2026 | Phase 2 infrastructure — Robustesse épistémique | Confidence tiers multi-critères, Brier scoring, tier transitions, pipeline.py, config_loader, 61 tests Phase 2 |
| 10/02/2026 | Phase 3 terminée — Pipeline E2E + corrections | Pipeline complet CLI→orchestrator→crystallize→DB→graph, 3 démos, post_crystallization hook, 425 tests (0 failed) |
| 10/02/2026 | Phase 3.1 — Corrections pool isolation + rollback | Fixture conftest reset singletons, get_pool() path detection, rollback_deltas applied_at fix, INSERT OR REPLACE |
| 11/02/2026 | Phase 3.2 — Consolidation post-audit | 51 annotations AUDIT (9 CRITICAL, 31 FRAGILE, 11 ACCEPTED), schema completé, 425 tests |
| 12/02/2026 | Phase 3.3 — ADR + conformité CLAUDE.md §5 | 7 ADR créés (ADR-001 à ADR-007), audit conformité 7 règles anti-dette IA |
| 12/02/2026 | Phase 4.0-4.6 — Corrections systématiques | Isolation singletons, crashs runtime, corruption, sécurité, Solana devnet complet, ADR-008, 470 tests |
| 15/02/2026 | Phase 4.7 — Peaufinage post-recette | ARCHITECTURE.md vérifié, 3 providers corrigés, 2 AUDIT FIXED, hypothesis + 3 tests property-based, 476 tests |
| 15/02/2026 | Tier sync + conformité CLAUDE.md | state.rs aligné (sandbox/proposition/validated/verified), §5.2 print→logger (35 occ), §5.3 INSERT audités (0 violation), 487 tests |

---

*Document vivant. Chaque décision majeure doit être consignée dans le journal ci-dessus.*
*Dernière mise à jour : 15 février 2026*
