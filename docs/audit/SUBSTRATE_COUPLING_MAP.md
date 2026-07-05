# SUBSTRATE_COUPLING_MAP — Carte de couplage noyau épistémique ↔ substrat Solana

**Date** : 2026-07-05
**Statut** : Évidence factuelle (préparatoire ADR-015 — Great Decoupling, différé)
**Mandat** : extension de l'audit `services/esmm` — lecture seule, aucune modification hors `docs/audit/`
**Méthode** : `rg -n "solana|Pubkey|PDA|submitter|program_id|devnet|on.chain|anchor|brier"` sur `services/`, `database/`, `programs/`, `cli/`, `scripts/`, `core/` ; lecture ciblée des fichiers touchés ; croisement ADR-007, 008, 012, 015, 017, 019.
**Extension de périmètre annoncée** : `database/schema.sql` + `database/engine.py` (les colonnes d'ancrage et l'exception UPDATE y vivent, pas dans `services/`), `programs/epp/src/**` (côté Rust des contrats d'interface), `cli/epp_cli.py` + `scripts/push_to_devnet.py` (couplage de contrôle). `Formal/` non parcouru (hors pistes du mandat) — signalé, non arbitré.

Ce document **décrit**. Il ne recommande aucun substrat, ne propose aucune abstraction, ne modifie aucun code.

**Convention de frontière** : les fichiers entièrement internes à `services/solana/**` et `programs/epp/**` constituent la couche substrat elle-même. Les points listés sont les endroits où le noyau (esmm, pipeline, database, config, CLI/scripts) et cette couche se touchent — plus les contrats d'interface que la couche substrat impose au contenu épistémique.

---

## 1. Points STRUCTURELS — l'identité ou la sémantique du protocole en dépend

### S-1 — Seeds PDA `[b"attestation", submitter, claim_hash]`
| | |
|---|---|
| Fichiers | `programs/epp/src/lib.rs:126` (`seeds = [ATTESTATION_SEED, submitter.key().as_ref(), &claim_hash]`), `programs/epp/src/constants.rs:22` (`ATTESTATION_SEED`), `services/solana/client.py:57-97` (`derive_attestation_pda`, seeds canoniques `client.py:94`) |
| Nature | identité |
| ADRs | 008, 017 (§1.4 : « 2 clusters → 2 PDA distinctes pour le même claim ») |

**Ce qui casse si le substrat devenait interchangeable** : l'adresse d'une attestation est le produit de `find_program_address`, primitive Solana. L'unicité `(submitter, claim_hash)` et l'isolation inter-clusters (ADR-017) sont garanties par le runtime, pas par le protocole. Sur un autre substrat, l'identité on-chain de chaque attestation existante devient non portable et l'unicité doit être réimplémentée et re-prouvée.

### S-2 — Colonnes d'ancrage et exception UPDATE à l'append-only (ADR-007)
| | |
|---|---|
| Fichiers | `database/schema.sql:844-849` (`solana_tx_signature`, `solana_slot`, `anchored_at`, `submission_status`), `database/engine.py:3459-3489` (`update_attestation_solana_tx` — marqué `AUDIT[A4-004]`), `database/engine.py:3427` (`update_attestation_submission_status`), `database/engine.py:1168` (comptage des attestations ancrées) |
| Nature | données + contrôle |
| ADRs | 007 |

**Ce qui casse** : la définition opérationnelle de « ancré » est *une signature de transaction Solana + un slot*. L'unique exception à l'immuabilité (ADR-007) est formulée dans le vocabulaire du substrat. Substrat interchangeable → la sémantique de l'exception doit être redéfinie (qu'est-ce que l'équivalent d'un slot ? d'une signature de tx ?) et le schéma SQL migré. Note : la clause `AND solana_tx_signature IS NULL` (`engine.py:3484`) rend l'ancrage *write-once* — propriété sémantique portable, mais exprimée sur une colonne nommée par le substrat.

### S-3 — Sérialisation bridge : u16×10000, longueurs fixes, version encodée
| | |
|---|---|
| Fichiers | `services/solana/bridge.py:26-29` (constantes miroir), `:115-131` (`float_to_u16`, `SCORE_SCALE=10000`), `:135-149` (troncature UTF-8 silencieuse `string_to_fixed_bytes`), `:174-183` (`protocol_version_to_u16`) ; côté Rust `programs/epp/src/constants.rs` (`SCORE_SCALE`, `MAX_*_LEN`), `programs/epp/src/lib.rs:54-60` (`require!` sur les bornes) |
| Nature | type |
| ADRs | 019 (contexte), marqueurs `AUDIT_REQUIRED` dans bridge.py |

**Ce qui casse** : la précision des scores (4 décimales), la troncature des champs et l'encodage de version sont dictés par le coût de rent et la taille de compte Solana. Toute attestation déjà ancrée a subi cette quantisation : un substrat sans ces contraintes soit hérite d'une perte de précision qui n'est pas la sienne, soit produit des représentations divergentes du même `portable_json`, cassant la vérifiabilité croisée.

### S-4 — Bornes de champs du noyau alignées sur les constantes de compte Solana
| | |
|---|---|
| Fichiers | `services/esmm/attestation.py:63-65` (`max_length=64/64/128`) ↔ `programs/epp/src/constants.rs:4-11` (`MAX_SUBJECT_LEN=64`, `MAX_PREDICATE_LEN=64`, `MAX_OBJECT_LEN=128`) ↔ `services/solana/bridge.py:26-28` |
| Nature | type |

**Ce qui casse** : rien à l'exécution — mais c'est le point le plus discret de la carte : le modèle Pydantic *du noyau épistémique* borne le contenu des triplets selon la taille d'un compte Solana. Les données produites depuis l'origine sont déjà façonnées par le substrat (triple définition à maintenir en cohérence manuelle, cf. commentaire « must match » `bridge.py:24`).

### S-5 — Projection enum 8→3 et garde on-chain (ADR-019)
| | |
|---|---|
| Fichiers | `services/solana/bridge.py:40-73` (`EPISTEMIC_TYPE_MAP`, `CONFIDENCE_TIER_MAP`, reverses explicites), `programs/epp/src/lib.rs:69-70` (`require!(epistemic_type <= 2)`, `require!(confidence_tier <= 3)`), `programs/epp/src/state.rs:56-61` (doc des 3 catégories) |
| Nature | type |
| ADRs | 019, 012, 014 |

**Ce qui casse** : la taxonomie on-chain à 3 catégories est un contrat d'interface *permanent* choisi pour la vérifiabilité formelle (Lean 4). La projection est avec perte (6 types métier → `empirical`). Un substrat interchangeable devrait soit répliquer exactement cette projection (sinon deux vues formelles du même corpus divergent), soit invalider les énoncés Lean adossés à l'enum.

### S-6 — `frame_hash` : le référentiel métrologique référencé par hash on-chain
| | |
|---|---|
| Fichiers | `services/solana/metrological_frame.py:1-10` (docstring : « Contrat d'interface avec le programme Solana : seul le frame_hash est transmis on-chain »), `services/solana/bridge.py:100` (`frame_hash: bytes [u8;32]`), `programs/epp/src/lib.rs:90` |
| Nature | données |

**Ce qui casse** : le lien attestation→référentiel de mesure est un hash 32 bytes stocké dans un compte Solana. Le contenu du frame est off-chain ; seule la *preuve* du référentiel dépend du substrat. Interchangeabilité → le mécanisme de preuve du « ce qu'on mesure » est à ré-ancrer, mais le hash lui-même (SHA-256) est portable. Voir aussi AMB-3 (emplacement du module).

**Inventaire structurel : 6 points.**

---

## 2. Points DOCTRINAUX — le modèle de confiance en dépend

### D-1 — Non-répudiation du submitter (ADR-008)
| | |
|---|---|
| Fichiers | `programs/epp/src/lib.rs:75` (`attestation.submitter = ctx.accounts.submitter.key()`), `:131-133` (`submitter: Signer<'info>`), `programs/epp/src/state.rs:22` (`pub submitter: Pubkey`), `services/solana/client.py:191` (`submitter_pubkey`), keypair local ADR-008 |
| Nature | identité |
| ADRs | 008, 017 (le submitter est l'unité de décentralisation : le « cluster ») |

**Ce qui casse** : la preuve d'origine est une signature ed25519 vérifiée *par le runtime Solana* (contrainte `Signer`), pas par le code EPP. Substrat interchangeable → la non-répudiation redevient déclarative tant qu'un mécanisme de signature équivalent n'est pas imposé par le nouveau substrat. De plus, l'identité même d'un cluster (ADR-017) EST une pubkey Solana — le concept d'opérateur n'a pas aujourd'hui de forme substrat-neutre.

### D-2 — Lecture permissionless via `getProgramAccounts`
| | |
|---|---|
| Fichiers | `services/solana/client.py:487-541` (memcmp sur `claim_hash` et `subject`), `programs/epp/src/lib.rs:103-108` (query off-chain documentée comme mode de lecture officiel) |
| Nature | contrôle |
| ADRs | 017 (« mesurable et vérifiable par quiconque lit la blockchain ») |

**Ce qui casse** : « quiconque peut vérifier sans permission » repose sur un substrat à état public interrogeable par n'importe quel RPC. Un substrat interchangeable qui n'offre pas cette propriété (ou l'offre différemment) change le modèle de confiance, pas seulement l'implémentation.

### D-3 — Track record Brier lisible on-chain (ADR-017, anticipé)
| | |
|---|---|
| Fichiers | actuellement 100 % off-chain : `database/schema.sql:923-998` (`brier_score`, vue `v_model_brier_scores`), `services/esmm/orchestrator.py:951-965` (poids Brier), `services/esmm/pipeline.py:845` (`weighting_strategy`) |
| Nature | données (couplage *futur* — aucun code d'ancrage Brier n'existe aujourd'hui) |
| ADRs | 017 |

**Ce qui casse** : rien dans le code actuel — le couplage est doctrinal par anticipation. La thèse ADR-017 (la confiance inter-clusters émerge d'un track record public) suppose que ce track record sera lisible sur le substrat. Si le substrat devient interchangeable *avant* cette implémentation, ADR-017 doit être reformulé en termes substrat-neutres ou re-suspendu. C'est le seul point de la carte où le découplage serait moins cher *maintenant* que plus tard — constat factuel, pas une recommandation de calendrier.

**Inventaire doctrinal : 3 points.**

---

## 3. Points INCIDENTS — remplaçables sans toucher la sémantique

| # | Fichier:ligne | Nature | Description |
|---|---|---|---|
| I-1 | `services/esmm/pipeline.py:170` | import | `from services.solana.metrological_frame import PREDEFINED_FRAMES` — **unique import `services.solana` dans tout `services/esmm/`**. Chemin d'import, pas dépendance sémantique (voir AMB-3). |
| I-2 | `services/config_loader.py:144` ; `config.yaml:71-72` | config | Section `solana:` optionnelle (`cluster: devnet`). Schéma nullable — le noyau démarre sans. |
| I-3 | `services/esmm/attestation.py:7-8` | naming/doc | Docstring : « contrat d'interface entre le moteur ESMM (off-chain) et la couche Solana (on-chain, Phase 1) ». Le nom du substrat dans la doc du noyau. |
| I-4 | `cli/epp_cli.py:26-28` ; `scripts/push_to_devnet.py:45-47, 336, 377` | contrôle | L'orchestration de l'ancrage (dérivation PDA, submit, write-back `update_attestation_solana_tx`) vit dans CLI/scripts, **hors du noyau**. `pipeline.py` ne soumet jamais on-chain. |
| I-5 | `services/esmm/run_logger.py:9` | naming/doc | « What is Solana? » comme question d'exemple dans une docstring. Anecdotique, listé par exhaustivité. |

**Inventaire incident : 5 points.**

---

## 4. Points AMBIGUS — classification non arbitrée, à trancher par l'architecte

### AMB-1 — « Dérivation de tier dépendant de l'ancrage » : la piste du mandat ne se vérifie pas telle quelle
`services/esmm/attestation.py:249-305` : `derive_confidence_tier` conditionne « verified » à `source_anchor is not None or validation_count >= 3`. Or `source_anchor` est le hash d'une **source autoritaire externe** (ADR-012, SHA-256 substrat-agnostique, pattern enforced `attestation.py:89-95`) — pas l'ancrage Solana. **Aucun chemin de code ne fait dépendre un tier de `solana_tx_signature` ou `submission_status`.** Soit le mandat visait le source anchor (auquel cas ce point est *non couplé au substrat* — voir §5), soit il existe une dépendance tier↔ancrage prévue mais non implémentée. **Question posée, pas d'arbitrage silencieux.**

### AMB-2 — Mécanisme de challenge : structurel ou doctrinal ?
`programs/epp/src/state.rs:89-91` (`is_challenge`, `challenged_attestation: Pubkey`), `services/solana/bridge.py:105-106, 194-204, 234`. Le lien de contestation est une **Pubkey de PDA** (structurel : identité substrat, hérite de S-1), mais la contestation inter-clusters est aussi un pilier du modèle de confiance ADR-017 (doctrinal). Les deux classifications sont défendables ; compté à part.

### AMB-3 — `metrological_frame.py` : module à cheval sur la frontière
Le module vit dans `services/solana/` mais son contenu (référentiels de mesure, gouvernance, Pydantic) est épistémique et substrat-neutre ; seul `compute_frame_hash` alimente le contrat on-chain (S-6). Son *emplacement* est incident (I-1 en découle), son *rôle de hash* est structurel. ADR-015 §2 le classerait probablement côté Kernel — non arbitré ici.

**Inventaire ambigu : 3 points.**

---

## 5. Évidence complémentaire — points vérifiés NON couplés (portables en l'état)

Listés parce qu'ils bornent le problème par le bas — le mandat interdit les recommandations, pas les constats négatifs :

- `compute_claim_hash` (`attestation.py:206-233`) : SHA-256 pur, aucune primitive substrat. (Son *usage* comme seed PDA est couvert par S-1.)
- Chaîne de revalidation `previous_hash` (`schema.sql:832`) : hash chain off-chain, substrat-neutre.
- `source_anchor` ADR-012 (`source_anchor_builder.py`, `schema.sql:822, 1027-1043`) : hash de source externe + snapshots SQLite, aucune dépendance Solana malgré le mot « anchor ».
- Tout le consensus (`consensus_engine.py`, poids Brier `orchestrator.py:951-965`) : computation locale, conforme à l'Axiome 4 (« computation locale, preuve on-chain »).
- `services/esmm/` ne contient qu'**un seul** import `services.solana` (I-1). Le constat ADR-015 §1 (« le découplage fonctionnel est DÉJÀ en place ») est confirmé pour la frontière esmm↔solana.

---

## 6. Notes d'évidence annexes (drift documentaire constaté, non corrigé)

- ADR-007 cite `engine.py:3085,3119` ; les fonctions sont aujourd'hui à `engine.py:3427` et `engine.py:3459`. Drift de références de lignes dans un ADR actif.
- ADR-007 nomme `solana_tx_signature` et `submission_status` comme seuls champs mutables ; `update_attestation_solana_tx` écrit aussi `solana_slot` et `anchored_at` (`engine.py:3480-3482`), et `post_crystallization.py:71` écrit `adjusted_consensus_score`/`diversity_bonus_factor` (documenté « ADR-005/007 safe » dans `schema.sql:837`). L'écart entre la lettre de l'ADR-007 et les colonnes effectivement mutables est constaté, pas arbitré.
- Hors périmètre substrat mais adjacent : `services/esmm/cycle_prompts.py:404` (SWC-107) est un couplage au *domaine* smart contracts (ADR-014), pas au *substrat d'ancrage* — non compté.

---

## 7. Inventaire chiffré

| Classification | Nombre |
|---|---|
| **Structurels** | 6 (S-1 à S-6) |
| **Doctrinaux** | 3 (D-1 à D-3, dont 1 anticipé sans code) |
| **Incidents** | 5 (I-1 à I-5) |
| **Ambigus** | 3 (AMB-1 à AMB-3) |
| Total points de couplage | **17** |

Questions ouvertes transmises à l'architecte : AMB-1 (tier↔ancrage : intention du mandat ?), AMB-2 (challenge : structurel ou doctrinal ?), AMB-3 (rattachement de `metrological_frame.py`), et le drift ADR-007 (§6 — mise à jour de l'ADR souhaitée ?).
