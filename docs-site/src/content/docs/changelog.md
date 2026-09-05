---
title: "CHANGELOG.md — EPP_Verdict"
editUrl: false
---

> Journal factuel des modifications. Format : date, titre court, 2-3 lignes de faits.

---

## [2026-09-05] Réalignement documentaire post-blockchain

Présentation actuelle réécrite ; README, pitch, whitepaper et architecture
antérieurs conservés à l'identique avec empreintes dans `docs/history/2026-09-05/`.
Le portail est généré depuis les sources, avec contrôle de parité et manifeste
d'intégrité. Les anciennes décisions et le positionnement reçoivent leur
contexte historique dans le portail, sans modification des ADR sources.

Le dashboard devient une archive explicite : pas de recopie automatique de
nouvelles mesures ; les JSON antérieurs sont conservés et vérifiés par hash.
TD-001 est résolue dans les sources par cette réduction de périmètre.
Ce journal ne constate aucun déploiement public, push ou merge de cette mise à jour.

---

## [2026-05-09] TD-002 résolue — adapter UI `graph_seeder_blockchain`

Le scénario `graph_seeder_blockchain` (référencé dans `ui/src/config/families.ts` famille `pipeline`) n'avait aucune entrée dans le registry `ADAPTERS` depuis 2026-03-02 — cliquer dessus produisait l'erreur `No adapter registered for scenario "graph_seeder_blockchain"`. Les 5 attestations on-chain issues exclusivement de ce fichier (sur 12 dans `devnet_pushed.json`) n'avaient donc pas de claim viewer associé.

### Adapter joint seeder ↔ on-chain (option A + α)
- Nouvel adapter `ui/src/data/adapters/graph-seeder-blockchain.ts`. Le seeder JSON publie des claims avec `verdict: null` (les verdicts sont matérialisés plus tard, au push on-chain). L'adapter joint donc le payload seeder avec `devnet_pushed.json` par texte de claim (`claim` côté seeder ↔ `question` côté on-chain) et ne surface que les claims ayant une attestation matchante — en récupérant le verdict depuis l'attestation.
- Type `Adapter` étendu avec un 2ème paramètre optionnel (`onchain?: OnChainManifest`). Les 5 adapters existants ignorent ce paramètre et restent source-compatibles.
- `loadRun` (`ui/src/data/loader.ts`) fetch le payload et le manifeste on-chain en parallèle (`Promise.all`) et forwarde les deux à l'adapter sélectionné.
- `ClaimTypeSchema` étendu : ajout de `'foundational'` et `'security_audit'`. Tous deux déjà présents on-chain (`epistemic_type` u8=0 et u8=2 respectivement, voir `programs/epp/src/state.rs::epistemic_type_to_u8`).

### Validation
`npx vitest run` → 4 / 4 passed (test RED-GREEN-FIX dans `ui/src/data/adapters/graph-seeder-blockchain.test.ts` : join par question, drop des claims sans attestation, zéro claim si pas de manifeste on-chain, préservation du `raw`). `npx tsc --noEmit` → clean. Signature étendue rétro-compatible (covariance fonctionnelle TS).

### Documents impactés
- `ui/src/data/adapters/graph-seeder-blockchain.ts` (nouveau, adapter)
- `ui/src/data/adapters/graph-seeder-blockchain.test.ts` (nouveau, 4 tests vitest)
- `ui/src/data/adapters/index.ts` (signature étendue + entrée registry)
- `ui/src/data/loader.ts` (fetch parallèle on-chain manifest)
- `ui/src/domain/claim.ts` (extension `ClaimTypeSchema`)
- `TECH_DEBT.md` (TD-002 resolved)

---

## [2026-05-01] Audit Lean P1 cumulativity + P0 recalibrage doc

Correction d'un bug de design Lean ↔ Python rendu visible par revue critique externe : `assignTier` permettait `verified` avec 1 modèle + anchor (violation de la stratification suggérée par les noms `sandbox < proposition < validated < verified`). Refonte parallèle du WHITEPAPER §"Formal Verification — Dual-Trust" pour aligner le langage public sur l'état réel post-audit (suppression du compte obsolète "11 theorems", suppression de la référence `Encoding.lean` retirée en P2, adoucissement des phrases falsifiables, ajout d'une sous-section "What Lean does *not* prove").

### P1 — Cumulativity (`Formal/Formal/TierBoundary.lean`)

- `assignTier` prend désormais 4 paramètres : `(score, models, hasAnchor, validationCount)`. Condition `verified` corrigée en `score ≥ 8500 ∧ models ≥ 3 ∧ (hasAnchor = true ∨ validationCount ≥ 3)` — alignement strict sur Python `derive_confidence_tier` (`attestation.py:259-264`).
- Deux nouveaux théorèmes substantifs : `tier_verified_implies_validated_conditions` et `tier_validated_implies_proposition_conditions`. Prouvent la stratification complète (verified ⇒ conditions de validated ⇒ conditions de proposition).
- Les 4 théorèmes `iff` (P3.B) adaptés au 4ème paramètre. Le corollaire `tier_verified_implies_conditions` conservé pour traçabilité.
- `RedTests.lean` adapté : 5 cas tier (3 RED + 2 GREEN, dont nouveau `red_tier_3_cumulativity_one_model_not_verified` qui documente la fermeture du bug pré-P1).

### P0 — Recalibrage doc

- WHITEPAPER §"Formal Verification" refondue en 4 sous-sections : (1) ce que Lean spécifie, par catégorie épistémique distincte (substantive characterization / type-level contracts / regression tests) ; (2) "What Lean does *not* prove" (gap spec/code humain non-mécanisé, SHA-256 modélisé comme concaténation, programme Rust hors scope) ; (3) ce que la couche formelle est censée garantir (chaos honnêtement mesurable, pas chaos éliminé) ; (4) implementation. Suppression de "11 theorems mechanically proven", "formally verified epistemic oracle", "Zero AI inference pipelines formally verified anywhere", "5,400+ projects only 3 touch FV".
- Compteurs synchronisés sur **6 théorèmes substantifs** + 7 regression + 2 type-level + 1 corollaire + 1 lemme définitionnel = **17 énoncés Lean compilés** total. README/PITCH/WHITEPAPER closing line/ARCHITECTURE alignés.

### Validation

`lake clean && lake build` : 16 jobs GREEN. `pytest tests/` : 905 passed, 14 skipped (venv) / 908 passed, 11 skipped (Python système). `HYPOTHESIS_MAX_EXAMPLES=10000 pytest tests/test_lean_conformance_property.py` : 16 passed (≈ 160 000 inputs).

### Test conformance Python actualisé

`tests/test_lean_conformance_property.py::TestInv4TierBoundaryProperty::test_python_verified_implies_lean_conditions` — assertion renforcée pour refléter la nouvelle condition Lean cumulative `models ≥ 3 ∧ (anchor ∨ vc ≥ 3)` au lieu de la projection partielle pré-P1 `models ≥ 3 ∨ anchor`.

---

## [2026-05-01] Audit Lean P4.2 — alignement Python ↔ Lean sur le contrat `SourceAnchor`

Ajout d'un `pattern=r"^[0-9a-f]{64}$"` au champ Pydantic `EpistemicAttestation.source_anchor` (`services/esmm/attestation.py:89-100`) pour aligner le runtime Python sur le contrat Lean `SourceAnchor` introduit en P3.A (longueur 64, charset hex minuscule). Ferme la divergence documentée §4.1 de `docs/audit/SESSION_AUDIT_FORMAL_P4.md`.

### Sites de tests adaptés (4)
- `tests/test_lean_conformance.py:273` — `"hex_anchor_1234"` → `"a" * 64`.
- `tests/test_lean_conformance_property.py` — stratégie `text_field` (random 1-100) → nouvelle `hash_field = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)`.
- `tests/test_lean_conformance_property.py::TestInv6SourceAnchorContract` → renommé `TestInv6SourceAnchorContractEnforced` ; 1 PASS + 2 `xfail strict` documentaires → 5 tests PASS strict (valid + 4 cas de rejet).
- `tests/test_phase03_integration.py:345` — `"test_anchor"` → `"a" * 64`.

### Validation
`lake build` GREEN (16 jobs) inchangé. `pytest tests/` complet : **908 passed, 11 skipped, 0 failed** (vs 852 documenté avant audit P1–P4). Run profond `HYPOTHESIS_MAX_EXAMPLES=10000` : 16 property tests × ~10 000 inputs ≈ 160 000 cas couverts sans contre-exemple. Aucune modification du code Python pipeline (les hash en production sont calculés par `services/esmm/source_anchor_builder.py` via `hashlib.sha256(...).hexdigest()`).

### Documents impactés
- `services/esmm/attestation.py` (modification unique en code de production).
- `tests/test_lean_conformance.py`, `tests/test_lean_conformance_property.py`, `tests/test_phase03_integration.py`.
- `docs/audit/SESSION_AUDIT_FORMAL_P4.md` §13 (addendum d'alignement).
- `README.md`, `PITCH.md`, `WHITEPAPER.md`, `docs/ARCHITECTURE.md`, `TECH_DEBT.md` (consolidation des compteurs et statut Lean).

---

## [2026-04-30] Audit Lean P1–P3 — couche `Formal/` revue ligne par ligne

Audit indépendant suivant le protocole §7 de `docs/To_do_list/Formal_Review_EPP.md`, exécuté en quatre phases (P1 hygiène, P2 nettoyage tautologies, P3 correction structurelle). Validation finale : `lake clean && lake build` GREEN (**16 jobs**, vs 18 pré-audit), `pytest tests/test_lean_conformance.py -v` **26 passed**.

### P1 (hygiène)
- Suppression de `Formal/Basic.lean` (racine, orphelin résiduel `lake init`, jamais importé).
- Suppression des doublons textuels `claim_hash_timestamp_independent` et `claim_hash_submitter_independent` (`Formal/Formal/ClaimHash.lean`) — strictement identiques au sens Lean (mêmes paramètres, conclusion, preuve), redondants avec `claim_hash_purity`.
- Renommage `Formal/Formal/Eval.lean` → `Sanity.lean` (3 `#eval`, 0 théorème, hors périmètre formel).
- Retrait des hypothèses fantômes B7 (`ht_differ`, `hs_differ`) des deux red hash tests dans `RedTests.lean`.
- Reclassification `claim_hash_purity` en regression test sur la projection `toClaimCore` (NOTE GATEKEEPER ajoutée).

### P2 (nettoyage tautologies)
- Suppression de `Formal/Formal/Encoding.lean` (4 énoncés tautologiques B1+B2+B3 : titre annonçait "INV-1 — Encodage float↔u16" mais aucun `Float` n'apparaissait, juste un bornage trivial sur `Nat`). Le bornage des scores reste garanti par la struct `Score` elle-même (`val ≤ 10000` au niveau du type).

### P3.A (refactor B5 — drapeau `Bool` → typage strict `Option`)
- `Formal/Formal/Basic.lean` : nouveau type `SourceAnchor` non-construible avec hash vide (`h_nonempty : hash ≠ ""`). Champ `Attestation.source_anchor` : `Bool` (`source_anchor_nonzero`) → `Option SourceAnchor`. La non-vacuité du hash est désormais portée *par le système de types*, pas par un drapeau qui peut mentir.
- `Formal/Formal/SourceAnchor.lean` : `wellFormed` adapté à `Option.isSome = true` ; les deux théorèmes (`deterministic_requires_anchor`, `deterministic_without_anchor_not_wellformed`) restent tautologiques *en preuve* mais l'invariant qu'ils expriment est désormais structurel (B5 fermé).
- `Formal/Formal/RedTests.lean` : 4 occurrences `source_anchor_nonzero := san` → `source_anchor := san` ; paramètre `(san : Bool)` → `(san : Option SourceAnchor)`. Preuves `rfl` inchangées.

### P3.B (extension `iff` sur les 4 tiers — ferme le biais B4)
- `Formal/Formal/TierBoundary.lean` : 4 nouveaux théorèmes `iff` (`tier_verified_iff_conditions`, `tier_validated_iff_conditions`, `tier_proposition_iff_conditions`, `tier_sandbox_iff_conditions`) qui caractérisent **complètement** le comportement de `assignTier`. Une implémentation triviale qui ne retournerait jamais `verified` ne passe plus la spécification — elle doit *aussi* retourner `verified` quand les conditions sont remplies. L'ancien `tier_verified_implies_conditions` est conservé en corollaire (`(iff …).mp`) pour traçabilité historique.
- Preuve observable du biais B4 par `_RedTestVacuity.lean` (théorème prouvant que la version directionnelle est vacuusement satisfaite par `assignTierTrivial = fun _ _ _ => sandbox`) ; fichier supprimé après extension `iff`.

### Compte honnête post-audit
**5 théorèmes structurels** (4 `iff` + 1 corollaire derived) + **7 regression tests** (1 `claim_hash_purity` + 4 tier red/green + 2 hash red) + **2 invariants au niveau du type** (`SourceAnchor.lean` rendus utiles par typage strict). Total 14 énoncés Lean compilés. Aucun ajout de dépendance mathlib.

### Documents produits
- `docs/audit/SESSION_AUDIT_FORMAL_P3.md`, `docs/audit/SESSION_AUDIT_FORMAL_P4.md`, `docs/research/RESEARCH_FORMAL_AUDIT.md`.

---

## [2026-04-24] Retrait revendication "sixteen months" + ancrage temporel commit `f12a922`

Correction de cohérence avec les règles Colosseum (jugement sur la production + démarrage projet possible jusqu'à 2 mois avant le sprint). La formulation antérieure *"Built by one person in sixteen months"* mélangeait le timeline d'exploration personnelle des LLMs (causale, pas projet) avec l'historique formel d'EPP, créant une ambiguïté défavorable au regard du règlement. Reframing sur le commit de démarrage formel `f12a922` (2026-02-13) qui ouvre la séquence ESMM/Solana documentée par git.

### Fichiers corrigés

- `README.md:212` — closing line.
- `PITCH.md:122` — closing line "Built by one person…".
- `WHITEPAPER.md:442-446` — section *From Intuition to Infrastructure* refondue (3 paragraphes) : antériorité conceptuelle décrite comme "casual LLM-orchestration tinkering" sans codebase, point de départ formel ancré sur `f12a922`, walk explicitement nommé "hackathon sprint, on top of a prior personal exploration".
- `docs-site/scripts/sync-docs.mjs` (writeIndexMdx) — landing portal réécrite cohérente.
- `docs-site/src/content/docs/{pitch,whitepaper,index}.mdx` — re-synced via `node scripts/sync-docs.mjs`.
- `docs/com/EPP_Pitch_Vision_v3.md:252` — draft historique également corrigé + note ajoutée pointant vers les docs root canoniques.

### Substance préservée

- L'antériorité conceptuelle est conservée (pas niée), mais clairement étiquetée comme exploration personnelle, pas projet codé.
- Le caveat "no formal CS or math background" + "logical mind, scientific transparency" reste, alignant la voix narrative sur l'honnêteté méthodologique.
- Le commit `f12a922` est cliquable dans toutes les occurrences (URL GitHub directe).

### Audit

`grep -rn "sixteen months\|16 months" --include="*.md" --include="*.mdx" --include="*.mjs"` retourne zéro occurrence dans les fichiers tracked. Les références restantes sont dans `.claude/worktrees/` (gitignored, non publiques).

---

## [2026-04-23] Retrait expérience kappa_risk (Claw4S) + cohérence docs/positioning

Nettoyage post-documentation : suppression de la branche expérimentale avortée (kappa_risk / Claw4S) et reframe du header `docs/positioning/README.md` pour cohérence avec sa visibilité publique sur GitHub.

### Fichiers retirés (kappa_risk)

- `demos/scenario_kappa_risk.py` + `demos/scenario_kappa_risk_claw.py` — scénarios kappa-Risk v1.1 (Anthropic API direct, 4 stances épistémiques × conditions alpha/beta × 3 répétitions). Utilisaient une pipeline hors-EPP, non-alignée avec le kernel ESMM.
- `build_lyra_edges_nodes.py` — transformation corpus → graph edges pondérés avec Ollivier-Ricci simplifié, conditions alpha/beta hardcodées. Dédié exclusivement au pipeline kappa_risk.
- `analyze_kappa_phase.py` + `run_kappa_topology_on_lyra.py` — downstream kappa topology + phase analysis. Déjà supprimés dans la working copy depuis sprint précédent, finalisés dans ce commit.
- `demos/benchmark_runs/kappa_risk/` (11 artefacts : .jsonl, _meta.json, .md) — dossier jamais tracké git, nettoyé du disque local.

**Distinction critique conservée** : `KappaCalculator` (courbure Ollivier-Ricci sur le graphe sémantique EPP, `database/graph_delta.py`) reste en place. Composant central du pipeline ESMM, indépendant de l'expérience kappa_risk abandonnée.

### `docs/positioning/README.md` — reframing

Le header initial *"internal positioning material, not public-facing"* était incohérent avec la réalité : le dossier est public sur GitHub via le commit `7d43845`. Reframing honnête : *"working material behind the public docs"*. Règle explicite ajoutée : **README/PITCH/WHITEPAPER sont la narrative officielle ; si contradiction avec le positioning, public wins.**

---

## [2026-04-23] Dashboard UI (ui/), push 12 attestations devnet, déploiement Vercel

Sprint hackathon Colosseum — création d'un dashboard React lisant les `demos/benchmark_runs/*.json` et le manifest on-chain, push de 12 attestations sur Solana devnet, déploiement public sur `epp-verdict.vercel.app`. Commits `5bd13e0`, `f5e58b8`, `afeca79`, `5b11f51`, `94da9da`, `0c2e9d6`.

### Phase A — Skeleton Vite+React (commit `5bd13e0`)

- `ui/` : nouveau sous-projet Vite 6 + React 19 + TypeScript strict + Tailwind v4 + Biome + Vitest + TanStack Query + Zod + React Router v7. Architecture en 4 cercles concentriques : `domain/` (types + Zod), `data/` (loader + adapter registry), `features/` (UI par cas d'usage), `ui/` (primitives), `routes/` (pages composées).
- `ui/scripts/copy-data.mjs` : hook predev/prebuild qui copie `demos/benchmark_runs/*.json` → `ui/public/data/` + génère `manifest.json` indexé par scenario/timestamp/claimsCount.
- Premier adapter : `scenario_jiang`. Validation Zod à la frontière du loader — capture immédiate d'une incohérence réelle (`source_thesis: null` sur claims 6-7 du run jiang du 2026-03-11).
- `ui/vercel.json` : framework Vite, build/install commands déclarés.

### Phase B — Palette lighthouse, families, 4 adapters, flywheel split (commit `f5e58b8`)

- Palette signature dérivée de l'avatar EPP : navy nuit (HSL 220 50% 7%) + cyan beam (HSL 184 78% 56%) + gold lighthouse (HSL 43 78% 65%), gradient radial subtil. Verdicts conservent emerald/amber/zinc/rose pour lisibilité jury (pas de réharmonisation cosmétique sur la sémantique).
- `ui/src/config/families.ts` : taxonomie déclarative — 5 familles (Flywheel, Sources déterministes, Géopolitique, Edge cases, Pipeline). Ajouter une famille = éditer 1 fichier, aucun autre code à toucher.
- `ui/src/features/family-tabs/` : tabs URL-driven (`?family=X`), comptes dynamiques par famille, sentinels "All" + "Unclassified".
- 4 nouveaux adapters : `flywheel-v2`, `flywheel-baseline`, `scenario6` (3 scénarios partagent la même shape, enregistrés sur 3 clés de registre), `deterministic-sources` (mappe `status` → `Verdict`, gère claims `skipped: true` quand source endpoint unreachable).
- Enum `ClaimType` étendu avec `speculative` (chopé par Zod sur scenario6_1 — claim_type valide en Python pas dans le schéma initial).
- `ui/src/features/flywheel-split/` : vue dédiée à route `/flywheel?run=X`. `parseFlywheelClaims()` extrait `baseline_*` / `delta` / `flywheel_*` du `raw` préservé. Layout BASELINE → FLYWHEEL avec deltas cyan, badges NEW gold pour claims sans baseline. Vérifié end-to-end : Trump CONTESTED 0.430 → SUPPORTED 0.586 (Δ +0.156).

### Phase C.1 — Push 12 attestations Solana devnet (commit `afeca79`)

- `scripts/push_to_devnet.py` (~470 lignes) : script standalone qui lit les attestations existantes dans `data/epp_devnet.db` (57) + `data/epp_audit_devnet.db` (20), les rehydrate via `EpistemicAttestation.model_validate_json(portable_json)`, push via `EppSolanaClient.submit_attestation()`. Pas de re-run de scénario, pas de synthèse de triplets — réutilise les attestations historiques.
- Mix curé : 8 `general_knowledge_v1.0` + 4 `smartcontract_audit_v1.0`, top consensus_score, dédup intra et inter-bucket pour éviter les collisions de PDA (la table DB autorise plusieurs lignes par claim_hash via revalidation, l'on-chain non).
- Idempotent (skip si claim_hash déjà dans le manifest avec tx_signature OK), failure-tolerant (try/except per attestation, manifest flushé atomiquement après chaque push pour ne pas perdre du SOL en cas de crash mid-batch), devnet-only (hérite `validate_cluster()` de `services/solana/config.py`).
- Slot enrichment via `getSignatureStatuses` (best-effort, falls back à `null`).
- Write-back DB optionnel via `ISpaceDB.update_attestation_solana_tx()` — fixe `solana_tx_signature`, `solana_slot`, `anchored_at` sur les rows source.
- 1ère exécution : 12/12 push réussis en ~5s, 0 failed. Submitter `DRAQ7ZppvzUdASF9jR218aPutsirUFwt2ePr6f9n9rJw`. Manifest généré : `data/devnet_pushed.json` (~17 KB, 12 entrées).
- Comble le trou laissé par `cli/epp_cli.py:submit()` qui était du plumbing DB sans appel à `client.submit_attestation()`.

### Phase C.2 — Badges on-chain inline + route /onchain (commit `5b11f51`)

- `ui/src/domain/onchain.ts` : `OnChainAttestationSchema` + `OnChainManifestSchema` Zod miroirs de la sortie de `push_to_devnet.py`. `EMPTY_ONCHAIN_MANIFEST` sentinel pour fallback gracieux quand aucun push n'a encore eu lieu.
- `ui/src/services/onchain.ts` : `buildOnChainIndex()` produit `Map<question, OnChainAttestation>` indexé par texte de question — clé de matching choisie parce que les benchmark JSONs ne portent pas de `claim_hash` mais portent le texte original.
- `ui/src/ui/OnChainBadge.tsx` : chip cyan ⛓ avec lien Solana Explorer en `target="_blank"`, tooltip exposant tx + frame + slot. `stopPropagation` sur click pour cohabiter avec un parent `<Link>` sans déclencher la nav parente.
- Wiring : `ClaimRow` (claim-viewer feature) + `FlywheelRow` (flywheel-split feature) reçoivent un `onChain?: OnChainAttestation | null` via prop drilling depuis les routes — index fetché une fois par page via TanStack Query, lookup `Map.get(claim.text)` O(1) par row.
- Route `/onchain` dédiée : summary card (cluster, program ID, submitter, pushed/failed, generation time) + liste cliquable des attestations vers Solana Explorer.
- Top nav : ajout NavLink "On-chain" avec état actif cyan.
- Vérifié end-to-end : badges visibles sur AQU-01 et AQU-02 du `scenario_6_2_qualifier_sensitivity` (water boils — questions matchent les attestations poussées). Les claims des runs flywheel ne sont pas badgés car ces questions-là n'ont pas été poussées dans la sélection curée.

### Phase D — Déploiement Vercel (commit `0c2e9d6`)

- Déployé en production : `https://epp-verdict.vercel.app`. Build ~18s sur infra Vercel iad1. Auto-redeploy à chaque push sur `main`. Environnement Hobby gratuit.
- **Pivot stratégique imposé par Vercel monorepo** : Vercel en mode `Root Directory = ui/` ne donne pas accès aux dossiers frères (`../demos/`, `../data/`) même avec "Include source files outside of the Root Directory" activé dans les settings. Le `prebuild` script crashait avec `ENOENT: /vercel/path0/demos/benchmark_runs`.
- Solution : `ui/public/data/` (précédemment gitignoré et régénéré localement par `prebuild`) est désormais **commité** — 24 benchmark JSONs + `manifest.json` + `devnet_pushed.json`, ~700 KB total. Le script `copy-data.mjs` détecte les sources manquantes via `pathExists(RUNS_SRC)` et no-op proprement (préserve les fichiers commités au lieu de les écraser via `rm -rf`).
- `ui/.gitignore` : retrait de `public/data/` + commentaire explicatif du workflow.
- Workflow nouveau pour ajout de scénario : Python pipeline génère JSON dans `demos/benchmark_runs/` → `npm run prebuild` (ou `npm run dev`) refresh `ui/public/data/` → `git add ui/public/data/` → commit → push → Vercel auto-déploie.
- **Caveat documenté** : le commit de `ui/public/data/` est une concession au workflow Vercel monorepo, **pas une bonne pratique générale**. Duplication entre source de vérité (`demos/benchmark_runs/`) et copie déployée (`ui/public/data/`). À refactorer en post-hackathon — options : (a) pipeline Python écrit directement dans `ui/public/data/`, (b) dashboard dans son propre repo, (c) backend séparé servant les manifests dynamiquement, (d) Vercel function lisant depuis un blob storage.

### Notes opérationnelles

- Préférence utilisateur : aucune attribution `Co-Authored-By: Claude` ou tag `Generated with Claude Code` dans les commits ou PR. Sauvegardée en mémoire de session.
- Préview/dev local : `start-ui.bat` à la racine du repo pour lancer le dashboard sans connaître npm (double-clic Windows ou `start-ui.bat` en PowerShell). Pas commité (artefact dev personnel).

---

## [2026-04-17] Lean 4 session 2 — INV-4 complété, INV-2 prouvé, ADR-020 dual-trust

Session de réparation et d'extension de l'infrastructure Lean 4. Correction de trois défaillances structurelles pré-existantes, preuve d'INV-2 (Claim Hash Purity), clôture documentaire via ADR-020. Commits `20ab6f7` et `0fea8b3`.

### Réparation infrastructure Lean (commit `20ab6f7`)

- `Formal/Formal/TierBoundary.lean` : preuve `tier_verified_implies_conditions` complétée (nested splits + `cases h`). Précédemment incomplète — le `contradiction` terminal échouait sur la branche `isFalse` du split principal et bloquait la compilation de la lib.
- `Formal/Formal/RedTests.lean` : réécrit. 4 théorèmes — 2 red-tier (score 5000 + 5 modèles + anchor ⇒ PAS verified ; score 8500 + 1 modèle + pas d'anchor ⇒ PAS verified) et 2 green-tier (cas passants). L'ancien théorème `red1_low_score_gets_verified` était mathématiquement faux et jamais exercé par la CI.
- `Formal/Main.lean` : ajout `import Formal`. La cible par défaut `lake build` (exécutée par `leanprover/lean-action@v1` en CI) ne chargeait auparavant aucun module de la lib. Tous les théorèmes et red tests étaient invisibles à la CI. Build par défaut : 4 jobs → 16 jobs.
- Protocole C6 double falsification : TierBoundary (seuil 8500 → 4000) et SourceAnchor (contrainte `deterministic` → `True`) falsifiés temporairement → build échoue → restauration → build vert. Non-tautologie des garde-fous confirmée.

### INV-2 Claim Hash Purity (commit `0fea8b3`)

- `Formal/Formal/ClaimHash.lean` : nouveau module.
  - `claim_hash_purity` : deux attestations de noyau canonique identique (`subject`, `predicate`, `object`, `frame`) produisent le même hash.
  - `claim_hash_timestamp_independent` : corollaire — timestamps différents n'affectent pas l'identité.
  - `claim_hash_submitter_independent` : corollaire — submitters différents n'affectent pas l'identité. Condition de possibilité du cross-cluster (ADR-017).
- `Formal/Formal/Basic.lean` : structure `Attestation` étendue — 6 nouveaux champs (`subject`, `predicate`, `object`, `frame`, `timestamp`, `submitter`). Les preuves TierBoundary/SourceAnchor/Encoding pré-existantes résistent sans modification.
- `Formal/Formal/RedTests.lean` : 2 red tests INV-2 ajoutés (`red_hash_1_timestamp_independence`, `red_hash_2_submitter_independence`), prouvés par `rfl`.
- `Formal/Formal.lean` : ajout `import Formal.ClaimHash`.
- Conformité Python vérifiée : `services/esmm/attestation.py::compute_claim_hash(subject, predicate, object_, metrological_frame)` — signature à 4 paramètres strictement alignée sur le noyau canonique Lean.
- Falsification C6 : ajout temporaire d'un champ `timestamp` dans `ClaimCore` → `claim_hash_purity` tombe (`unsolved goals`) → restauration → build vert. Build final : 18 jobs.

### ADR-020 — Architecture Dual-Trust (2026-04-17)

- `docs/adr/ADR-020.md` : clôt la première session structurée de vérification formelle.
- Formalise la distinction entre **couche empirique** (consensus LLM + sources déterministes) et **couche mathématique** (preuves Lean 4 sur le protocole abstrait). Les deux couches couvrent des risques différents, ne se substituent pas.
- Inventorie les 11 théorèmes prouvés (4 pour INV-1 Encoding, 1 pour INV-4 TierBoundary, 2 pour INV-6 SourceAnchor, 3 pour INV-2 ClaimHash) et les 6 red tests associés.
- Documente le gap sémantique modèle ↔ code runtime : le lien est humain, pas mécaniquement garanti. Écart connu sur INV-2 : Python applique `.lower().strip()` avant hash — propriété Python plus forte que Lean, pas de divergence de sécurité.
- Définit 5 critères d'acceptation pour tout futur invariant : preuve sans `sorry`/`admit`, red test associé qui tombe si l'invariant est cassé, red test importé dans `lake build`, conformité code vérifiée par grep ou observation, référence à un ADR.
- Liste les invariants identifiés mais non prouvés (INV-3 PDA unicité, INV-5 regression cut isolation, INV-7 Brier proper scoring, INV-8 consensus convergence) avec leur tier de difficulté et raison d'exclusion.

---

## [2026-04-17] Lean 4, sources déterministes, et garde on-chain ADR-019

Trois axes post-sprint Gatekeeper : installation Lean 4 avec trois premiers invariants prouvés, scénario sources déterministes exécuté en live, et garde on-chain de l'Enum V2 testée avec protocole RED→GREEN. Commits `1d703fd` (major update) et `86539e7` (test on-chain).

### Lean 4 — vérification formelle (2026-04-15)

- `Formal/` : arborescence Lake créée — `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `Main.lean`, `Formal.lean`, `README.md`.
- Trois invariants prouvés : `Formal/Formal/TierBoundary.lean`, `Formal/Formal/Encoding.lean`, `Formal/Formal/SourceAnchor.lean`.
- `Formal/Formal/RedTests.lean` : vérification explicite de non-tautologie des preuves.
- `Formal/Formal/Basic.lean` + `Formal/Formal/Eval.lean` : primitives et évaluation.
- `.github/workflows/lean_action_ci.yml` : CI Lean ajoutée.
- `lake build` passe.

### Sources déterministes — scénario live (2026-04-15)

- `demos/scenario_deterministic_sources.py` (nouveau fichier) : scénario dédié aux sources déterministes — 4 sources sur 8 testées en live.
- Wikidata SPARQL : 5/5 checks validés.
- Verra VCS (Voluntary Carbon Standard) : 5/5 checks validés ; adapter Verra corrigé à cette occasion.

### ADR-019 on-chain — test de la garde Enum V2 (2026-04-17)

- `tests/epp_enum_v2_guard.ts` : test Anchor unique exerçant `require!(epistemic_type <= 2)` en ligne 69 de `programs/epp/src/lib.rs`. Construit une `submit_attestation` complète avec `epistemic_type = 3`, attrape l'erreur via `anchor.AnchorError.parse(err.logs)`, vérifie `errorCode.code === "InvalidEpistemicType"` et `errorCode.number === 6006`.
- Protocole C6 Gatekeeper : double run GREEN/RED archivé. RED produit en commentant temporairement la ligne 69 — le test échoue alors sur `expect.fail()` car la transaction passe. Preuve de non-tautologie acquise.
- `Anchor.toml` : `[programs.localnet]` aligné sur `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD` (valeur de `declare_id!` et du keypair de déploiement). Corrige le `DeclaredProgramIdMismatch` qui bloquait `anchor test`, y compris sur le test `ping` pré-existant.

### Nettoyage repo (2026-04-15)

- `.gitignore` étendu : `reports/`, `test_results/`, `docs/archives/`, CSVs kappa, fichiers de benchmark passent en local-only. Ces artefacts ne sont plus versionnés.

---

## [2026-04-14] Sprint de correction post-audit Gatekeeper — 9 blocs RED-GREEN-FIX

Sprint d'exécution stricte de `docs/To_do_list/DIRECTIVE_CORRECTION_AUDIT.md`.
Neuf blocs validés un par un par l'humain. Protocole RED→GREEN→FIX respecté à chaque étape.

- **BLOC A — S7-001 CORS dangereux** : `app/main.py` — `allow_origins=["*"]` + `allow_credentials=True` remplacé par liste explicite d'origines dev (localhost) avec override via variable d'environnement `EPP_ALLOWED_ORIGINS` (CSV).
- **BLOC B+C — S1-001 + S1-002 Enum épistémique V2 (ADR-019)** : projection HYBRIDE des 8 types Python (`foundational`, `bridge`, `specialized`, `generalist`, `hybrid`, `verdict`, `deterministic`, `security_audit`) vers 3 catégories on-chain formellement vérifiables (`empirical=0`, `deterministic=1`, `assessed=2`). `bridge.py::EPISTEMIC_TYPE_MAP` et `EPISTEMIC_TYPE_REVERSE` réécrits. Rust `lib.rs::require!(epistemic_type <= 2, ...)` + `state.rs::epistemic_type_to_u8()` match multi-alternatives. Documentation invariants Lean 4 en commentaires Rust.
- **BLOC D — S3-001 à S3-004 Exceptions silencieuses granulées** : 4 `except Exception` remplacés par exceptions typées + `logger.warning/error` avec contexte. `engine.py` (seed frames), `pipeline.py` (parse consensus_meta + cache lookup), `client.py` (load keypair — re-raise fail-fast sur erreurs inattendues).
- **BLOC E — S6-001 Schéma Pydantic config_loader** : `ConfigSchema` Pydantic strict (`extra="forbid"` à chaque niveau) ajouté dans `services/config_loader.py`. Validation fail-fast à `load_config()` — rejette clés inconnues et types invalides. Chaque champ documente sa source de lecture.
- **BLOC G — S1-003 Troncature UTF-8 codepoint-safe** : `bridge.py::string_to_fixed_bytes` aligné sur frontière de codepoint (boucle `while truncated.encode("utf-8") > max_len`). Corrige les corruptions silencieuses pour `é` (2 bytes), `中` (3 bytes), `😀` (4 bytes).
- **BLOC H — S1-005 Marker AUDIT[A10-007] reclassé** : `bridge.py:111` — `🟡 FRAGILE` → `🟡→✅ RESOLVED`. Le commentaire antérieur décrivait un bug qui n'existe pas (la guard `0.0 <= value <= 1.0` rejette déjà les valeurs hors borne). Annotation conservée pour traçabilité.
- **BLOC I — S6-002 db_path obligatoire** : `database/engine.py:50` — default `"data/ispace.db"` supprimé. `ISpaceDB(db_path)` désormais obligatoire. Zéro appelant sans arg confirmé par grep exhaustif avant modification.
- **BLOC J — S9-001 Migration asyncio.run → pytest-asyncio** : 20 fonctions de test réécrites en `async def` + `@pytest.mark.asyncio` dans `test_phase02_decoupling.py`, `test_phase02_migration.py`, `test_phase03_integration.py`, `test_phase03_revalidation.py`. Nested event-loop pattern éliminé.

### Hors scope

- **BLOC F — S7-002 Rate limiting** : différé (décision humaine). `app/main.py` n'est pas touché pour le rate limiting dans ce sprint.

### Baseline

866 passed, 11 skipped, 0 failed (delta net : **+55 passed** vs. baseline 811). 10 nouveaux fichiers de test (un par bloc + un pour le test d'inspection AST S9-001). 4 tests existants (`test_phase1_bridge.py`, `test_phase1_integration.py`, `test_phase4_solana.py`, `test_solana_deserialize.py`) mis à jour pour refléter la sémantique V2 du round-trip enum. 4 tests `test_phase3_config_loader.py` mis à jour pour utiliser des configs conformes au schéma Pydantic.

### Déploiement Rust

Les modifications `programs/epp/src/lib.rs` et `state.rs` sont préparées et syntaxiquement valides (relecture visuelle). `cargo check` indisponible sur Windows natif — validation Anchor à exécuter en WSL par l'humain.

---

## [2026-04-11] ADR-018 — Flywheel v2 : scénarios post-cutoff expandus

- `demos/scenario_flywheel_v2.py` : nouveau scénario flywheel étendu — 5 claims post-training-cutoff vérifiables via Wikidata SPARQL. Pré-validation SPARQL automatique au lancement (requêtes invalides retirées du run). Claims : Trump 2024, Starmer PM UK, Sheinbaum présidente Mexique, Nobel Physique 2024 Hopfield/Hinton, contrôle Biden.
- `demos/scenario_flywheel_v2_baseline.py` : script baseline VERIFY-only (sans pass déterministe, sans flywheel) pour mesurer les scores LLM bruts et calculer les deltas.
- Résultats flywheel v2 (3 modèles : mistral, llama3.1:8b, gemma3) :
  - Trump : 0.39 CONTESTED → 0.89 SUPPORTED (delta +0.46, verdict flip)
  - Starmer : 0.49 CONTESTED → 0.76 SUPPORTED (delta +0.28, verdict flip)
  - Sheinbaum : 0.78 SUPPORTED → 0.96 SUPPORTED (delta +0.18)
  - Nobel 2024 : 0.79 SUPPORTED → 0.95 SUPPORTED (delta +0.18)
  - Biden contrôle : 0.90 → 0.96 (delta +0.06, marginal — modèles savent déjà)
- FW2-04 (Prabowo/Indonésie) et FW2-06 (loi martiale Corée du Sud) retirés : Wikidata SPARQL retourne 0 résultats pour ces QIDs.
- FW2-CTRL-02 (UE 30+ membres) retiré : faux positif non corrigeable — le format d'injection flywheel transmet le status/score mais pas la valeur brute du count.

### Fix — consensus_meta string→dict désérialisation (DB layer)

- Cause racine : `consensus_meta` est TEXT en SQLite, sérialisé via `json.dumps` à l'écriture, mais jamais `json.loads` à la lecture. Crash `'str' object has no attribute 'get'` sur tout chemin lisant `consensus_meta` depuis la DB.
- `database/engine.py` : 4 SELECTs alignés sur la même liste de colonnes (ajout `adjusted_consensus_score`, `diversity_bonus_factor`, `commit_reveal_verified`, `consensus_meta` aux 3 requêtes courtes). `_row_to_attestation_dict()` : désérialisation `consensus_meta` via `json.loads` à l'index 28. `get_latest_attestation()` : ajout `consensus_meta` dans la boucle de désérialisation JSON.
- `services/esmm/attestation.py` : guard `isinstance(consensus_meta, str)` dans `crystallize()` — défense en profondeur.
- Protocole RED→GREEN→FIX respecté. Test ajouté : `test_consensus_meta_deserialized_as_dict_from_db`.

### Fix — get_latest_attestation() colonne inexistante

- `database/engine.py` : `ORDER BY created_at` → `ORDER BY timestamp`. La table `attestations` n'a pas de colonne `created_at`.
- Protocole RED→GREEN→FIX respecté. Test ajouté : `test_get_latest_attestation_returns_stored_row`.

### Fix — Retrait extra_system_context (ajout hors scope)

- `services/esmm/pipeline.py` : paramètre `extra_system_context` retiré de `run_pipeline()`. Ajouté hors scope pendant le fix consensus_meta, zéro appelant dans le codebase. Causait une chute du score Trump flywheel de 0.89 à 0.58.

### Baseline

811 passed, 14 skipped, 0 failed (net +2 tests : `test_consensus_meta_deserialized_as_dict_from_db`, `test_get_latest_attestation_returns_stored_row`).

---

## [2026-03-13] ADR-018 — Flywheel Épistémique

- **Fix B4 (bloquant)** : `_run_deterministic_pipeline()` (pipeline.py:172) appelait `crystallize()` sans `question=question` → colonne `question` NULL en DB → `get_attestations_by_question()` ne retournait jamais d'ancres déterministes. Ajout de `question=question` dans l'appel `crystallize()`.
- **`_lookup_existing_anchors(question, db)`** : nouvelle fonction pipeline.py — lookup par `question` via ADR-013 `get_attestations_by_question()`, filtre `consensus_method == "deterministic_source_v1"`, lit `diagnostics.result` (PAS `source_anchor_meta.normalized`). Retourne liste de dicts `{source_id, score, status, fetched_at, source_version}`.
- **`_format_anchor_context(anchors)`** : formate les ancres en bloc `[VERIFIED DATA — from deterministic sources...]...[END VERIFIED DATA...]` injecté dans le system prompt. Retourne `""` si aucune ancre.
- **Bloc flywheel dans `run_pipeline()`** : guard `is_verify = (esmm_config.input_mode == "verify")` (ADR-018 §4 — VERIFY-only). Variable `flywheel_enabled` initialisée à `False` hors du `try` (correction Opus P2 — évite NameError dans la traçabilité). Lookup encapsulé dans `try/except` non-bloquant.
- **Threading `anchor_context` sur 4 frontières** : `run_pipeline()` → `_extract_triplets_from_question(anchor_context=)` → `esmm_config.anchor_context` → `execute_cycles()` cycle_context `["anchor_context"]` → `execute_cycle()` → `_query_models(anchor_ctx=)` + `_query_models_isolated(anchor_ctx=)` → concaténation system_prompt.
- **`ESMMRunConfig`** : champ `anchor_context: str = ""` ajouté (`orchestrator.py`).
- **Traçabilité `consensus_meta`** : `consensus_meta.setdefault("methodology", {})["flywheel"] = {enabled, anchors_found, sources_injected}`.
- **`config.yaml`** : section `flywheel: { enabled: true }` ajoutée.
- **`tests/test_adr018_flywheel.py`** : 8 tests RED-GREEN-FIX — `test_lookup_no_anchors`, `test_lookup_with_deterministic_anchor`, `test_lookup_filters_out_epistemic_attestations`, `test_format_anchor_context_empty`, `test_format_anchor_context_with_data`, `test_consensus_meta_flywheel_traceability`, `test_flywheel_disabled`, `test_flywheel_skipped_in_explore_mode` (correction Opus P3). Baseline : 809 passed, 14 skipped, 0 failed.

---

## [2026-03-13] Fix ACLED 403 — header Content-Type OAuth2

- `services/sources/adapters/acled.py` : ajout `headers={"Content-Type": "application/x-www-form-urlencoded"}` au POST `/oauth/token`. Sans ce header, l'API ACLED retourne 403 même avec des credentials valides.
- Ajout `import logging` + `logger.info("[ACLED] Token request (cached=...)")` avant le check cache du token.

---

## [2026-03-13] Fix Wikidata User-Agent + SPARQL QID

- `services/sources/adapters/wikidata.py` : ajout `User-Agent: EPP_Verdict/1.0 (...)` dans les headers HTTP — cause racine des erreurs `not_found` sur les requêtes SPARQL Wikidata (API bloque les crawlers sans User-Agent).
- `demos/scenario_jiang.py` : JIANG-RESOLVED-01 `wikidata_query` corrigé — `wd:Q116827690 wdt:P1346` → `wd:Q101110072 wdt:P991` (Q101110072 = élection présidentielle US 2024, P991 = successful candidate, plus précis que P1346 winner). JIANG-RESOLVED-02 : `wikidata_query: None` (opérations militaires non interrogeables dans Wikidata). Logs debug `[WIKI]` conservés. `CLAIMS` complet restauré (filtre single-claim retiré).

---

## [2026-03-10] ADR-016 Lot 6 — scenario_jiang.py

- `demos/scenario_jiang.py` : script de démonstration géopolitique — 8 claims issues des prédictions Jiang Xueqin (Yale, "Predictive History") sur la stratégie iranienne et la dynamique du Moyen-Orient 2024-2026.
- Deux passes par claim : VERIFY épistémique (ESMM multi-LLM) + DETERMINISTIC ACLED (ancrage données de conflit, si `ACLED_EMAIL` défini). Concordance VERIFY↔ACLED calculée et exportée.
- Output JSON horodaté dans `demos/benchmark_runs/jiang_{ts}.json`. Baseline inchangée : 797 passed, 14 skipped.

---

## [2026-03-09] Fix `<think>` tag stripping — modèles reasoning (phi4/deepseek-r1)

- `services/esmm/triplet_extractor.py` : nouvelle fonction `_strip_thinking_tags()` — supprime `<think>...</think>` et `<thinking>...</thinking>` avant parsing JSON (regex non-greedy, multi-blocs). Appliquée en tête de `_parse_verdict_response()` (remplacement du `.strip()` initial).
- `services/esmm/triplet_validator.py` : appel `_strip_thinking_tags()` importé depuis `triplet_extractor` (source unique) avant le parser EXPLORE — protège aussi le mode EXPLORE si `<think>` contient du contenu JSON-like.
- Cause racine : regex `\{[\s\S]*\}` greedy capturait depuis le 1er `{` dans `<think>` jusqu'au dernier `}` → JSON invalide → `INSUFFICIENT_EVIDENCE` → vote perdu → `models_consulted: 2` au lieu de 3. 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] Correctifs métadonnées Bug A + Bug B (pipeline.py / orchestrator.py)

- **Bug A — cycle\_sequence** : `orchestrator.py:427` — write-back `self.config.cycle_sequence = cycle_sequence` après l'override VERIFY local. `_build_consensus_meta()` enregistrait la valeur config.yaml (`["divergent","debate","meta"]`) au lieu des cycles réels (`["assess","challenge","adjudicate"]`).
- **Bug B — final\_verdict None** : `pipeline.py` — boucle cristallisation splitée en 2 passes. Passe 1 : crystallize + post_hook + collecte `(attestation, triplet)` sans storage DB. Après blocs P1/P2 d'enrichissement (`final_verdict`, `evidence_corpus`), Passe 2 : `model_dump()` + `store_attestation()` + inject graph. Pydantic v2 shallow-copy confirmée : inner dicts partagés → `consensus_meta["verify"]["final_verdict"]` propagé vers toutes les attestations sans réassignation explicite. 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] Fix routing EXPLORE→VERIFY (pipeline.py)

- `_extract_triplets_from_question()` : guard `if getattr(esmm_config, "input_mode", None) != "verify"` avant appel `classify_input()`. Le prompt ASSESS_AUDIT ne contient pas les mots-clés de détection VERIFY → `classify_input()` retournait EXPLORE et écrasait `input_mode="verify"` posé par `audit_runner`. Cycles exécutés correctement mais métadonnées mentaient (symptôme observé : `cycle_sequence: ["divergent","debate","meta"]` en DB). 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] ADR-014 Lots 3+4 — Moteur d'audit smart contract

### Lot 3 — audit_runner + CLI

- Nouveau module `services/audit/audit_runner.py` : `AuditResult` dataclass, `run_audit()` async (slice → pipeline VERIFY par unité), `_safe_format()` (regex substitution évitant `KeyError` sur JSON `{}` dans template ASSESS_AUDIT), `format_unit_for_audit_prompt()`, `_sort_units_by_priority()`, `_extract_severity_from_result()`, `_aggregate_severity()` (pire sévérité gagne).
- `config.yaml` : section `audit:` (enabled, db_path, slice_strategy, severity_taxonomy, slither_path). `cli/epp_cli.py` : commande `epp audit` avec options `--frame`, `--models`, `--slither/--no-slither`, `--output`. Isolation DB : `ISpaceDB(audit_db_path)` direct, jamais le singleton `get_db()`.
- `tests/test_adr014_audit_runner.py` : 16 tests (AuditResult shape, contract_hash 64-hex, aggregate_severity propagation, db_path guard, JSON string consensus_meta round-trip).

### Lot 4 — benchmark fixtures

- `tests/fixtures/benchmark/not_so_smart/ground_truth.json` : construit depuis lecture réelle des 4 `.sol` (reentrancy/integer_overflow/unprotected_function/unchecked_call) — pragma, contract_name, units vulnérables, SWC IDs (107/101/105/104), classes ToB.
- `services/audit/contract_slicer.py:236` : regex `\bcontract\s+(\w+)\s*(?:is\b|\{)` — fix contract_name retournant `"that"` (commentaire `// A contract that...`) au lieu de `"KingOfTheEtherThrone"`.
- `tests/test_adr014_benchmark.py` : 16 tests slicer-level (noms réels, external_calls, state_writes, priority sort, SWC IDs valides).
- `scripts/benchmark_reentrancy.py` : script standalone live benchmark — `close_pool()` (pas `db.close()`), ASCII partout (cp1252-safe), modèles `mistral:latest / llama3.1:8b / gemma3:latest`. Dry-run validé.
- `scripts/benchmark_heavy.py` : benchmark heavy models (phi4-reasoning/deepseek-r1/granite3.3) avec timeout par unité, `--test-models`, `--single`, `--timeout`. Fixes : `close_pool()`, ASCII, SyntaxError `global TIMEOUT_PER_UNIT` déplacé en tête de `main()`.

---

## [2026-03-05] Migration services/rwa/ → services/sources/ (ADR-014 §2.1)

- `git mv services/rwa services/sources` — déplacement physique du répertoire.
- Imports mis à jour : `services/sources/adapters/__init__.py` (5 lignes), 4 adaptateurs (1 ligne chacun), `services/esmm/source_anchor_builder.py`, `tests/test_adr012_source_anchor.py` (9 lignes), `demos/scenario_6_full_pipeline.py` (4 lignes).
- `config.yaml` : section `rwa:` → `sources:` ; `tests/test_rwa_source_anchor.py` → `tests/test_adr012_source_anchor.py`.
- Phase A préalable : correctifs `services/solana/client.py` (3 bugs : derive_pda try/except, submit_attestation ordre + garde keypair, query_attestations_by_claim garde). `tests/test_phase4_solana.py` : `@pytest.mark.skipif(_SOLANA_AVAILABLE)` sur `TestTransactionBuildingMockMode`. Baseline : 698 passed, 14 skipped, 0 failed.

---

## [2026-03-05] graph_seeder_blockchain.py — correctifs démarrage + ESMMRunConfig

- Correctifs d'import et de signature DB : `from config_loader import get_config` → `from services.config_loader import get_section` ; `ISpaceDB(pool)` → `ISpaceDB(db_path)` (signature correcte, pool géré en interne) ; `await pool.close()` → `await db.close()` ; import `SQLiteConnectionPool` supprimé.
- Unicode Windows (cp1252) : `→` → `->`, `──` → `--`, `ℹ` → `i`, `⚡` → `*`, `≥` → `>=` (4 familles de caractères hors cp1252).
- `run_claim()` : `ESMMRunConfig(models=MODELS, input_mode="verify", original_claim=..., max_duration_hours=400/3600)` passé à `run_pipeline()` — timeout 400s pour phi4-reasoning.

---

## [2026-03-05] Correctifs post-ADR-013

- `_check_cache()` (pipeline.py) : `timestamp=best.get("timestamp", 0)` ajouté à la reconstruction `EpistemicAttestation` — champ requis par Pydantic.
- `cli/epp_cli.py` `_run_ask()` : `ESMMRunConfig(models=selected_models, input_mode="verify", original_claim=question)` ajouté et passé à `run_pipeline()` — aligne la CLI sur le pattern de scenario_6.
- `config.yaml` + fichier physique : `data/epp.db` → `data/epp_devnet.db` (isolation pré-mainnet).

---

## [2026-03-05] ADR-011-v2 — Semantic Fingerprinting : fingerprint_merges exposé

- `ConsensusResult` +`fingerprint_merges: int = 0` ; `_semantic_merge()` retourne 3-tuple `(triplet_data, semantic_dispersion, len(merge_groups))`. Champ threadé : `consensus_engine` → `triplet_extractor` (`ExtractionResult`) → `cycle_manager` (`CycleResult`, extraction dict) → `pipeline.py` diagnostics (`consensus_meta.diagnostics.fingerprint_merges`).
- Test RED-GREEN-FIX ajouté : `test_fingerprint_merges_exposed_in_consensus_result` dans `tests/test_adr010_consensus_meta.py`. 701 passed, 0 failed.

---

## [2026-03-01] ADR-013 — Graphe persistant & cache-hit épistémique

- `PipelineConfig` : +`cache_ttl_hours` (défaut 168h), +`use_cache` (défaut True). `PipelineResult` : +`from_cache`, +`cache_hit_hash`. `run_pipeline()` : cache-hit lookup avant cycles ESMM via `_check_cache()` (lecture seule, filtrage TTL + tier minimum, non-bloquant).
- `database/engine.py` : +`get_attestations_by_question()` — lookup par question exacte (`WHERE question = ?`, tri timestamp DESC). `config.yaml` : section `cache` (enabled, ttl_hours=168, min_tier_for_cache="proposition"). Scénarios benchmark `scenario_6` : `use_cache=False` (délibération complète).
- 701 passed, 11 skipped, 0 failed (+3 tests RED-GREEN-FIX). Baseline 698 → 701.

---

## [2026-02-28] Audit unifié epp_audit.py — Nettoyage legacy

- `epp_audit.py` : script unifié 4 phases remplaçant `audit_runner.py`, `audit.sh`, `find_orphans.sh`. 21 mutations (M1.1-M7.3), 7 groupes, 0 SURVIVED. Corrections : orphan detector false positives Windows/WSL, C4/C5 schema/config drift, C8 VERIFY coverage grep, pytest collection abort. Outputs → `tests/audits/`. `REPORT_PATH`/`CHECKSUMS_PATH` mis à jour.
- Tests Solana localnet validés : 26/26 (11 unit, 6 mock, 9 E2E). Total projet : 723 tests (sans vars Solana : 697 passed, 11 skipped).
- Supprimés : `audit_runner.py`, `audit.sh`, `find_orphans.sh`, `MUTATION_REPORT.md`.

---

## [2026-02-25] Nettoyage héritage Lyra ACE + correctifs post-audit ADR-012

- Renommage variables d'environnement `LYRA_*` → `EPP_*` (`ollama.py`, `ollama_embeddings.py`) : `LYRA_OLLAMA_URL` → `EPP_OLLAMA_URL`, `LYRA_MODEL` → `EPP_MODEL`, `LYRA_NUM_CTX` → `EPP_NUM_CTX`, `LYRA_EMBEDDING_MODEL` → `EPP_EMBEDDING_MODEL`. Valeurs par défaut inchangées.
- Correctifs post-audit ADR-012 (P1/P2) : `_run_deterministic_pipeline()` — predicate résolu depuis `PREDEFINED_FRAMES[frame_id].metric` (plus de `"sanctions_status"` hardcodé) ; subject résolu sur `name || serial || project_id || question`. `PREDEFINED_FRAMES` déplacé dans `metrological_frame.py` (source unique de vérité). 697 passed, 11 skipped, 0 failed (+3 tests).

---

## [2026-02-25] ADR-012 — Intégration sources RWA / Bifurcation déterministe

- Nouveau chemin `DETERMINISTIC` dans `ESMMRunConfig` (`ClaimNature` enum). `execute_cycles()` court-circuité si `claim_nature=DETERMINISTIC`. Pipeline : `_run_deterministic_pipeline()` — fetch source → `_canonical_hash()` → `crystallize(epistemic_type="deterministic")` → store snapshot + attestation.
- Nouveau module `services/esmm/source_anchor_builder.py` : `SourceAnchorSpec`, `SourceAnchorResult`, `build_source_anchor()`. Nouveau répertoire `services/rwa/adapters/` : 4 adaptateurs (`OpenSanctionsAdapter`, `OfacAdapter`, `EuCfspAdapter`, `VerraVcsAdapter`) + registre `get_adapter()`.
- 3 nouveaux `MetrologicalFrame` : `compliance_sanctions_v1.0`, `carbon_credits_vcs_v1.0`, `rwa_identity_v1.0`. Table SQL `source_anchor_snapshots` (25e table). 3 nouvelles méthodes `ISpaceDB` : `store_source_anchor_snapshot()`, `get_snapshot_by_anchor()`, `is_snapshot_fresh()`. CLI : commande `epp verify-rwa`. Config : section `rwa.sources`. `attestation.py` : `models_consulted ge=0`, `epistemic_type` étendu avec `"deterministic"`, guard `source_anchor_meta` dans `crystallize()`.
- 694 passed, 11 skipped, 0 failed (+21 tests ADR-012).

---

## [2026-02-24] Audit Solana Directives 2-5 — Couche Solana qualifiée

- D5: `CONFIDENCE_TIER_MAP` (bridge.py) — 3 aliases backward compat supprimés (`low`/`medium`/`high`). Désalignement avec `confidence_tier_to_u8` Rust confirmé (hit `_ => err!(InvalidConfidenceTier)`). Bijection stricte 4 clés ↔ 4 arms Rust désormais garantie par `test_confidence_tier_map_bijection_with_rust`. `test_legacy_tiers_backward_compat` supprimé (test du comportement retiré).
- D7: Guard `_SOLANA_AVAILABLE` — `@pytest.mark.skipif` déplacé au niveau méthode (`test_submit_requires_ready_client` uniquement). Import inutilisé supprimé de `test_phase1_client.py`. 3 tests de `TestSubmitterAuth` restaurés dans le compteur.
- D6: Program ID `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C` ajouté dans `README.md` section Solana.
- D5b: 3 marqueurs `AUDIT_REQUIRED` levés — `client.py:474` (CLAIM_HASH_OFFSET=41), `client.py:511` (SUBJECT_OFFSET=73), `lib.rs:113` (PDA seeds). Remplacés par `AUDIT_CLEARED 2026-02-23`.
- 673 passed, 11 skipped, 0 failed (inchangé : +1 bijection −1 legacy = 0 net).

---

## [2026-02-24] Restructuration Anchor — Convention standard

- Workspace Anchor déplacé à la racine : `Anchor.toml`, `Cargo.toml` [workspace], `Cargo.lock`, `package.json`, `tsconfig.json` → `EPP_Verdict/` (étaient dans `programs/epp/`).
- Programme Rust remonté d'un niveau : `programs/epp/programs/epp/src/` → `programs/epp/src/`. Dossier `programs/epp/programs/` supprimé.
- `tests/epp.ts` déplacé vers `tests/` racine. `anchor build`/`anchor test` s'exécutent depuis la racine.
- `.gitignore` mis à jour : `.anchor/` et `target/` à la racine (étaient `programs/epp/.anchor/`, `programs/epp/target/`).
- Références mises à jour : `client.py` (IDL path), `test_bridge_solana_compat.py`, `diagnostic_solana_layer.sh` (6 occurrences), `README.md`, `ARCHITECTURE.md`, `AUDIT_INTERNE.md`.
- 673 passed, 11 skipped, 0 failed (inchangé).

---

## [2026-02-24] Calibration Épistémique VERIFY Mode

- Fix A — `cycle_prompts.py` : prompt ASSESS remplacé — STEP 1 classifie `claim_type` (empirical/definitional/normative/speculative) avant STEP 2 (verdict). Normative → INSUFFICIENT_EVIDENCE obligatoire.
- Fix A bis — `triplet_extractor.py` : `_parse_verdict_response()` extrait `claim_type` depuis JSON, normalise (fallback `"empirical"`), inclus dans le dict retourné.
- Fix C — `cycle_manager.py` : majority vote `claim_type` sur réponses de tous les modèles. Résultat injecté comme triplet `{"subject": claim[:64], "relation": "claim_type", "object": consensus_claim_type}` dans `raw_model_triplets` (propagation via triplet-as-channel → `adapt_all()` → `extracted_triplets` dans pipeline).
- Fix B — `pipeline.py` : constantes `VERDICT_PENALTIES` (SUPPORTED=1.0, CONTESTED=0.65, INSUFFICIENT_EVIDENCE=0.45) + `CLAIM_TYPE_PENALTIES` (empirical=1.0, normative=0.70, speculative=0.75, definitional=0.90). Pénalité appliquée avant `crystallize()` : `adjusted_score = raw × v_penalty × t_penalty`. Traçabilité dans `consensus_meta.verify` : `claim_type`, `raw_consensus_score`, `decidability_penalty`, `adjusted_consensus_score`.
- 10 tests RED-GREEN-FIX. Baseline : 663 → 673 passed, 0 failed, 11 skipped.

---

## [2026-02-20] Polissage Final — VERIFY Mode Hackathon-Ready (P1-P4)

- pipeline.py: `_extract_triplets_from_question()` retourne 4-tuple incluant `esmm_config`
  (était 3-tuple → `esmm_config` perdu → `pipeline_mode` affichait "explore" au lieu de "verify")
- pipeline.py: `_build_consensus_meta()` écrit `pipeline_mode=verify` + section `verify`
  (original_claim, final_verdict, verdict_confidence, model_verdicts) — ADR-010
- pipeline.py: enrichissement post-cristallisation — `final_verdict` + `evidence_corpus`
  (triplets sub-consensus preservés dans consensus_meta, cap 20 items)
- cycle_manager.py: log INFO explicatif pour CHALLENGE (0/0 consensus est by design,
  counter-arguments alimentent ADJUDICATE)
- scenario_4_live_ollama.py: display conditionnel VERIFY (verdict box, split, evidence corpus,
  phases, methodology) — EXPLORE display preservé
- scenario_4_live_ollama.py: fix display Dissent — `v` (dict verify) → `att.object` (texte verdict) ;
  renommage variable shadowed `v` → `vname` dans split_parts
- 4 tests RED-GREEN-FIX. Baseline: 659 → 663 passed, 0 failed, 11 skipped

---

## [2026-02-20] A1-A3 — Corrections runtime VERIFY mode (post-Scenario 4 live)

- orchestrator.py: `cycles_per_type` fixé à `{assess: 1, challenge: 1, adjudicate: 1}` (était n_models,
  causant n×n queries ASSESS au lieu de n)
- orchestrator.py: skip convergence gaps + skip adaptation en mode VERIFY (les gaps sont un concept
  EXPLORE ; convergence prématurée empêchait CHALLENGE et ADJUDICATE d'exécuter)
- orchestrator.py: propagation context inter-phases — `_verify_model_verdicts` capturés après ASSESS,
  passés à CHALLENGE (per-model isolation) et ADJUDICATE (synthèse all_verdicts)
- cycle_manager.py: `_query_models_isolated()` — isolation épistémique CHALLENGE, rotation circulaire
  (modèle[i] voit uniquement le verdict de modèle[(i+1) % N], directive §4.2 / ADR-011-v2 §2.2)
- cycle_manager.py: `_extract_verdicts_from_responses()` — routage des verdicts par
  `_parse_verdict_response()` + `encode_verdict_as_triplets()` → `compute_consensus()`
  (agreement_ratio réel, vote_entropy, pas de construction manuelle ConsensusTriplet)
- scenario_4_live_ollama.py: affichage `pipeline_mode` + section `verify` dans consensus_meta
- 4 tests RED-GREEN-FIX. Baseline: 655 → 659 passed, 0 failed, 11 skipped

---

## [2026-02-20] Dual-Mode ESMM — Claim Verification (VERIFY mode, S1-S7)

- Nouveau enum `CycleType` (str, Enum) : 6 valeurs — DIVERGENT/DEBATE/META (EXPLORE) +
  ASSESS/CHALLENGE/ADJUDICATE (VERIFY)
- Nouveau enum `InputType` : EXPLORE (défaut) ou VERIFY, auto-détecté par `classify_input()`
  dans question_seeder.py (détection mots-clés : "is it true", "verify", "fact-check", etc.)
- cycle_prompts.py: 3 SYSTEM_PROMPTS + 6 templates VERIFY (ASSESS ×2, CHALLENGE ×2, ADJUDICATE ×2)
- triplet_extractor.py: `_parse_verdict_response()` — extraction verdict/confidence/evidence/reasoning
  depuis JSON ou texte libre LLM (fallback regex robuste)
- Nouveau module `verdict_encoder.py` : `encode_verdict_as_triplets()` — encode un verdict en triplets
  réutilisant la pipeline de cristallisation (claim → verdict → SUPPORTED/REFUTED/UNCERTAIN,
  evidence triplet, reasoning triplet)
- orchestrator.py: `ESMMRunConfig.input_mode` (explore/verify) + `original_claim` ;
  séquence VERIFY = ASSESS→CHALLENGE→ADJUDICATE
- pipeline.py: auto-détection du mode via `classify_input()`, propagation `input_mode`
  et `original_claim` dans `ESMMRunConfig`
- pipeline.py: `_build_consensus_meta()` enrichi section `verify` (original_claim, final_verdict,
  verdict_confidence)
- attestation.py: `epistemic_type="verdict"` pour les attestations VERIFY
- `__init__.py`: exports verdict_encoder, `_parse_verdict_response`, InputType, classify_input
- 19 tests RED-GREEN-FIX. Baseline: 636 → 655 passed, 0 failed, 11 skipped

---

## [2026-02-20] Refactoring — relation_vocabulary.py (source unique de vérité)

- Nouveau module `relation_vocabulary.py` : 11 groupes, superset consensus_engine (10) +
  fingerprint_match (6). Résolution conflits relies_on→DEPENDS_ON, produces∈CAUSES (ADR-006).
- `consensus_engine.py` : `_RELATION_GROUPS` local remplacé par import depuis relation_vocabulary
  (legacy snapshot conservé sous flag)
- `fingerprint_match.py` : `RELATION_GROUPS` local remplacé par import depuis relation_vocabulary
  (legacy snapshot conservé sous flag)
- Flag `use_legacy_relation_groups` dans `config.yaml` pour déploiement progressif (true=legacy)
- 29 tests ajoutés (19 relation_vocabulary + 10 fingerprint_match). Baseline: 595 → 624 passed, 0 failed
- 10 CI gate hash stability tests (ADR-006) verrouillent les hashes SHA-256 existants

---

## [2026-02-18] ADR-011-v2 — Corrections audit Semantic Fingerprinting (C1-C5)

- fingerprint_match.py: suppression import fantôme depuis consensus_engine, 3 fonctions
  self-contained (`_normalize_entity`, `_normalize_relation` avec RELATION_GROUPS, `_cosine_similarity`)
- orchestrator.py: fix attribut `self.cycle_manager.rotator` → `self.cycle_manager.model_rotator`
- fingerprint_expand.py: réécriture boucle expand_terms — un appel batch_sequential_providers
  par provider au lieu d'un seul appel global (zéro contamination inter-modèles structurelle)
- fingerprint_expand.py: format questions aligné sur pattern triplet_extractor
  `[[{"role": "user", "content": prompt}]]`
- orchestrator.py: normalisation raw_model_triplets en dicts au point d'accumulation
  (isinstance/vars/__dict__, défense contre ExtractedTriplet non-dict)
- fingerprint_apply.py: filet de sécurité `hasattr(new_t, "subject")` pour objets non-dict
- 7 tests ajoutés (3 normalisation C1, 1 assertion single-provider C3, 2 objets C5, 1 accumulation)
- Baseline: 590 → 595 passed, 0 failed, 11 skipped

---

## [2026-02-18] ADR-011-v2 — Semantic Fingerprinting (implémentation initiale)

- 4 nouveaux modules : fingerprint_config.py (~60 lignes), fingerprint_expand.py (~120 lignes),
  fingerprint_match.py (~180 lignes), fingerprint_apply.py (~90 lignes)
- fingerprint_config.py: FingerprintConfig dataclass + load_fingerprint_config() depuis config.yaml
- fingerprint_expand.py: MicroGraph/ExpandResult, build_expand_prompt(), parse_expand_response(),
  expand_terms() async — chaque modèle décrit SES propres termes (zéro contamination)
- fingerprint_match.py: Jaro-Winkler (rapidfuzz), classify_neighbor (Strong Anchor 2.0 / Weak 1.0),
  match_neighbor_pair (cascade relation-aware), compute_weighted_overlap, Union-Find components
- fingerprint_apply.py: select_canonical (fréquence → longueur → alpha), build_alignment_table,
  apply_alignment_to_triplets (S/R/O, sans mutation input)
- triplet_extractor.py: ExtractionResult.raw_model_triplets exposé
- cycle_manager.py: CycleResult.raw_model_triplets propagé
- orchestrator.py: accumulation bruts cross-cycle, reconcile() publique (EXPAND → MATCH → APPLY),
  `_final_consensus_triplets` (jamais mutation `_collected_triplets`), `reconciliation_meta`
- orchestrator.py: ESMMRunResult.reconciliation_meta, run() appelle reconcile() entre execute/finalize
- pipeline.py: appel explicite reconcile(), _build_consensus_meta enrichi section reconciliation
- config.yaml: section esmm.fingerprint (9 clés)
- __init__.py: exports des 4 modules
- requirements.txt: rapidfuzz ajouté
- 37 tests RED-GREEN-FIX. Baseline: 553 → 590 passed, 0 failed, 11 skipped

---

## [2026-02-17] Phase 1.2 — Fix désérialiseur on-chain + tests relecture

- client.py: fix _deserialize_attestation_account() — ajout champ last_revalidated
  (i64, 8 bytes) manquant entre timestamp et validation_count. Tous les champs après
  timestamp étaient décalés de 8 bytes (bug critique C4).
- client.py: assertion taille en fin de désérialisation (filet anti-décalage permanent)
- test_phase4_solana.py: fix test_deserialize_attestation_layout (buffer +8 bytes)
- test_phase4_solana.py: fix test_borsh_layout_matches_account_size (446→454, +assert ==462)
- 5 tests RED→GREEN dans test_solana_deserialize.py (roundtrip, taille invalide,
  offsets claim_hash/subject, hypothesis float)
- Baseline: 548 → 553 passed, 0 failed, 11 skipped

---

## [2026-02-16] ADR-010 — Traçabilité méthodologique du consensus

- schema.sql: colonne `consensus_meta TEXT` dans attestations
- engine.py: migration ALTER TABLE, sérialisation JSON dans store_attestation(), backfill_consensus_meta()
- consensus_engine.py: `ConsensusResult` dataclass (remplace List[ConsensusTriplet]), `_compute_vote_entropy()` (Shannon), `semantic_dispersion` (mean pairwise cosine distance)
- triplet_extractor.py: `ExtractionResult` enrichi (vote_entropy, semantic_dispersion, triplets_before/after)
- cycle_manager.py: `CycleResult` enrichi, threading via dict
- orchestrator.py: `ESMMRunResult` enrichi, accumulation max(entropy), sum(triplets)
- ollama.py: `resolve_model_version()` via POST /api/show (parameter_size + quantization_level)
- attestation.py: champ `consensus_meta` sur EpistemicAttestation, param dans crystallize()
- pipeline.py: `_build_consensus_meta()` async (methodology + conditions + diagnostics), résolution version via providers, backward-compat 2/3-tuple
- 26 tests RED→GREEN. Baseline: 522 → 548 passed, 0 failed, 11 skipped

---

## [2026-02-15] Phase 4.8 — Neutralité linguistique ESMM

- cycle_prompts.py: 3 SYSTEM_PROMPTS + 20 templates traduits en anglais
- prompts.py: 4 prompts traduits ; exemples few-shot en anglais ; directive "MUST be in English"
- consensus_engine.py: `compute_consensus()` async, accepte `embedding_provider` optionnel
- consensus_engine.py: `_semantic_merge()` — Pass 2 clustering cosine > 0.85, ambiguity preservation
- consensus_engine.py: `ConsensusTriplet` étendu (`variations`, `ambiguity_detected`)
- Annotation COMMUNITY_DECISION_REQUIRED dans 3 fichiers (consensus, post_crystallization, pipeline)
- ADR-009 créé : Language Neutrality in ESMM Protocol
- 9 tests ajoutés. Baseline: 514 → 523 passed, 0 failed, 11 skipped

---

## [2026-02-15] Live run — Normalisation triplets + correctifs pipeline

- consensus_engine.py: normalize_triplet() — synonymes relation (10 groupes: USES, IS_A, HAS, PART_OF, CAUSES, ENABLES, PREVENTS, RELATES_TO, DEPENDS_ON, PROVIDES), entités (PoW→proof of work, etc.), word synonyms (computational→computing)
- consensus_engine.py: `_hash_triplet()` appelle `normalize_triplet()` avant SHA-256
- consensus_engine.py: fix dict/getattr — les triplets (dicts du validator) avaient confidence=0.0 via getattr ; tous filtrés avant consensus
- consensus_engine.py: log INFO enrichi (processed/filtered/unique/passed)
- cycle_manager.py: META retry capped à max_retries=3 (boucle for au lieu de retry unique)
- cycle_manager.py: CYCLE_TIMEOUTS uniformisés à 60s (divergent était 30s, trop court pour modèles à froid)
- cycle_manager.py: create_cycle_manager() accepte min_consensus, propagé à get_triplet_extractor()
- orchestrator.py: min_consensus propagé de ESMMRunConfig aux 3 call sites de create_cycle_manager()
- pipeline.py: run_pipeline() accepte esmm_config (Optional[ESMMRunConfig]) ; propagé à _extract_triplets_from_question()
- orchestrator.py: import mort `from enum import Enum` supprimé
- 5 tests RED→GREEN (test_r2_normalize_triplet: synonymes, IS_A, whitespace, différents, abréviations)
- DB live migrée: 3 colonnes R2 ajoutées à attestations (ALTER TABLE)
- Baseline: 509 → 514 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.3 — Commit-reveal complet

- schema.sql: table commit_reveal (run_id, model_id, phase, response_hash, verified)
- schema.sql: colonne commit_reveal_verified dans attestations
- engine.py: 4 méthodes CRUD (store_commit, get_commit, verify_and_update_commit, update_attestation_commit_verified)
- cycle_manager.py: hash SHA-256 des réponses stocké entre query_models et extraction (L256)
- get_attestation_by_hash inclut commit_reveal_verified
- 5 tests RED→GREEN (CRUD, altération détectée, schema check)
- Baseline: 504 → 509 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.2 — Clustering embeddings (détection Sybil)

- Nouveau module services/esmm/response_deduplicator.py: detect_similar_responses()
- Similarité cosinus entre embeddings; seuil configurable (default 0.95)
- Penalty factor 0.5 pour le second modèle d'une paire quasi-identique
- MockDeterministicEmbeddingProvider dans les tests (hash-based, cosinus variable)
- 3 tests RED→GREEN (identiques détectés, différents non pénalisés, seuil respecté)
- Baseline: 501 → 504 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.1 — Diversité architecturale dans le consensus

- schema.sql: 2 colonnes ajoutées à attestations (adjusted_consensus_score, diversity_bonus_factor)
- post_crystallization.py: bonus diversité calculé APRÈS crystallize() (Option C, ADR-005/007 safe)
- Factor 1.1 si ≥2 familles d'architecture, 1.0 sinon ; adjusted capped à 1.0
- engine.py: update_attestation_diversity_bonus() + get_attestation_by_hash inclut les 2 colonnes
- 3 tests RED→GREEN (TestDiversityBonusMultiFamily, TestDiversityBonusMonoFamily, TestConsensusScoreUnchanged)
- Schema check OK, pytest 501 passed (1 flaky préexistant), 0 failed, 11 skipped
- Baseline: 498 → 501 passed

---

## [2026-02-15] R-2.1.2 — Dashboard performance modèles

- engine.py: get_all_model_brier_scores() via vue v_model_brier_scores (schéma existant)
- cli/epp_cli.py: commande `epp models stats` — tableau Model/Predictions/Resolved/Avg Brier/Weight
- Gestion cas vide (cold start message) + troncature model_id à 25 chars
- 5 tests RED→GREEN (TestGetAllModelBrierScores, TestModelsStatsCLI)
- Baseline: 493 → 498 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.1.1 — Pondération dynamique Brier des votes

- consensus_engine.py: compute_consensus() accepte model_weights (Optional[Dict[str, float]])
- Poids pondèrent agreement_ratio ET avg_confidence (weighted sum)
- Formule: weight = max(0.0, 1.0 - avg_brier_score), cold start = 1.0
- Option A: propagation par paramètre sur 7 signatures (consensus_engine → triplet_extractor → cycle_manager ×2 → orchestrator → pipeline ×2)
- orchestrator._compute_model_weights(): auto-calcul des poids depuis DB Brier au lancement du run
- 6 tests RED→GREEN (TestWeightedConsensus, TestColdStartWeight, TestBackwardCompat)
- C1 grep: 17 appelants vérifiés, tous backward-compatible (default None)
- Baseline: 487 → 493 passed, 0 failed, 11 skipped

---

## [2026-02-15] Phase 4.7 — Peaufinage post-recette

- ARCHITECTURE.md: 7/7 points verifies, note purge config ajoutee
- Bloc A: 3 providers (ollama, anthropic, openai_compat) deleguent a infer_architecture_family(), 3 tests coherence
- Bloc B: client.py complet (0 NotImplementedError, 5 methodes CHANGELOG confirmees)
- Bloc D: 2 annotations AUDIT marquees FIXED (A4-002, A4-003), 15 FIXED total
- Bloc E: hypothesis installe, 3 tests property-based (float↔u16 roundtrip ADR-001, claim hash ADR-006)
- Sync confidence_tier Rust↔Python: state.rs commentaires + helper mis a jour, 11 tests tiers roundtrip
- Conformite §5.2: print() → logger dans engine.py (3), main.py (27), chat.py (5)
- Conformite §5.3: 17 INSERT bruts audites, 0 violations (tous proteges ou AUTOINCREMENT)
- Baseline: 470 -> 487 passed, 0 failed, 11 skipped

---

## [2026-02-12] Phase 4 — Correction systematique (v2)

### Phase 4.0 — Fondations

- Isolation tests: reset 16 singletons (setup+teardown), conftest.py reecrit
- Demockage: 0 mock complaisant trouve, 1 annote
- Smoke test Solana bridge: 7 tests (types Python/Anchor compatibles)
- Migration async: 4 fichiers tests migres de asyncio.run() vers async def natif
- Baseline: 425 -> 432 passed

### Phase 4.1 — Crashs runtime (RED-GREEN-FIX)

- triplet_extractor: ON CONFLICT(source, target, relation_type) -> ON CONFLICT(source, target)
- 5 imports deprecies app.embeddings migres vers services.providers.ollama_embeddings
- session_storage: 4 INSERT -> INSERT OR IGNORE (ADR-004)
- Baseline: 435 passed

### Phase 4.2 — Corruption silencieuse (RED-GREEN-FIX)

- graph_delta ADD_EDGE: INSERT OR REPLACE -> INSERT ON CONFLICT DO UPDATE (preserve relation_type)
- pool.py: 2 except:pass -> except Exception as e: logger.warning()
- Baseline: 438 passed

### Phase 4.3 — Durcissement structurel

- get_db() warning si appele avec db_path different
- close_entity_resolver(), close_relation_normalizer() ajoutes
- 5 except:pass restants annotes ou fixes en production
- Test singleton pollution permanent
- Baseline: 440 passed

### Phase 4.4 — Nettoyage

- config.yaml: 35 cles -> 12 effectives, 3 sections mortes supprimees (providers, server, logging)
- esmm.models ajoute a config.yaml (AUDIT[A8-001] fixe)
- app/embeddings.py supprime (fully replaced by EmbeddingProvider)
- semantic_memory table supprimee du schema (in-memory only)
- Baseline: 440 passed

### Phase 4.5 — Securite

- Prompt injection: XML boundary delimiters (<system_instruction>, <user_query>)
- Concept sanitization: _sanitize_concept() dans cycle_manager.py
- Sybil: infer_architecture_family() durci (first-token match, provider prefix strip)
- Pipeline input validation: MAX_QUESTION_LENGTH=5000, control char stripping
- ADR-005 respecte: pas de retour au seuil simple
- 16 tests securite ajoutes
- Baseline: 456 passed

### Phase 4.6 — Solana devnet complet

- Transaction building: _build_and_send_submit_tx() via solders (Borsh manual)
- Account deserialization: _deserialize_attestation_account()
- PDA validation: check_pda_exists()
- Query methods: query_attestations_by_claim/subject (memcmp filters)
- Mock mode: submit retourne signature deterministe sans solders
- ADR-008 cree: strategie auth submitter
- 14 tests Solana ajoutes
- Baseline finale: 470 passed, 0 failed, 11 skipped

---

## [2026-02-12] Phase 3.3 — Relecture framework + ADR

- Audit de conformité CLAUDE.md §5 (7 règles anti-dette IA)
- Créé 7 Architecture Decision Records (docs/adr/ADR-001 à ADR-007)
- Annoté 7 violations §5.1-§5.7 dans le code (2 §5.1, 2 §5.2, 2 §5.5, 1 §5.1 session_storage)
- Corrigé 1 INSERT brut : engine.py sessions → INSERT OR IGNORE (§5.1 bloquant)
- Rapport de conformité : 2 INSERT bruts critiques, 16 except:pass (4 déjà annotés), 13 singletons, 0 mismatch signatures
- Tests: 425 passed, 0 failed, 10 skipped

## Rapport de Conformité §5 — CLAUDE.md
Date : 2026-02-12

### §5.1 — INSERT bruts
- 20 trouvés, 1 corrigé (engine.py:691 sessions → INSERT OR IGNORE), 1 annoté (session_storage.py:291)
- 16 low-risk (tables à PK autoincrement), 2 déjà protégés (ON CONFLICT)

### §5.2 — except:pass sans justification
- 16 trouvés, 4 déjà annotés AUDIT[], 5 nouvellement annotés (2 §5.2 FRAGILE, 3 # OK justifiés)
- 7 non annotés (🟢 ACCEPTED : patterns de parsing/fallback idiomatiques)

### §5.3 — Signatures non propagées
- 7 méthodes vérifiées, 45 appelants audités, 0 mismatches trouvés

### §5.4 — Schéma ↔ code
- Tables : 23 dans le code, 24 dans le schéma, 1 divergence (semantic_memory dans schéma mais pas dans code)
- Colonnes critiques vérifiées : concepts ✓, relations ✓, attestations ✓, triplet_extractions ✓, graph_deltas ✓

### §5.5 — Singletons
| Fichier | Variable | Vérifie params | Reset | Annoté |
|---------|----------|---------------|-------|--------|
| database/pool.py | _pool_instance | PARTIEL (db_path) | close_pool() | ✓ A1-006/007/008 |
| database/engine.py | _db_instance | NON | close_db() | ✓ A1-001 |
| services/config_loader.py | _config | NON | reset_config() | — |
| services/entity_resolver.py | _resolver_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/relation_normalizer.py | _normalizer_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/providers/ollama.py | _ollama_instance | NON | close_ollama_provider() | — |
| services/providers/ollama_embeddings.py | _ollama_embedding_instance | NON | close_ollama_embedding_provider() | — |
| app/llm_client.py | _client_instance | NON | close_ollama_client() | — |
| services/esmm/model_rotator.py | _rotator_instance | NON | close_model_rotator() | — |
| services/esmm/triplet_extractor.py | _extractor_instance | NON | close_triplet_extractor() | — |
| services/consciousness/memory.py | _memory_instance | NON | clear_semantic_memory() | — |
| services/relation_normalizer.py | _normalizer_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/session_storage.py | _storage_instance | NON | implicite | — |

### §5.6 — Tests substantifs
- Fichiers avec ratio < 2 : 19 fichiers (test_phase3_post_crystallization 0.75, test_phase2_diversity 1.0, test_phase2_integration 1.0, test_phase2_track_record 1.0, test_phase03_audit 1.0, etc.)
- Assertions faibles : 12 total (4 `is not None`, 8 `is True`)

### §5.7 — Configuration
- Clés orphelines : ~35 (la majorité de config.yaml est décorative — seuls database.path et esmm.* sont lus)
- Valeurs hardcodées : ~30 (seuils de confiance, URLs Ollama, modèles d'embedding, host/port serveur)

### ADR créés : 7 (docs/adr/ADR-001 à ADR-007)

---

## [2026-02-11] Phase 3.2 — Consolidation post-audit

- Ajouté colonne `submission_status` à la table `attestations` dans schema.sql (25 tables, 29 colonnes)
- Corrigé import cassé entity_resolver.py (`get_embedding` → `get_embeddings`)
- Ajouté `embedding_model` aux appels `add_concept()` dans seed_injector.py, populate_graph.py, entity_resolver.py
- Sécurisé `record_model_prediction()` avec INSERT OR IGNORE (anti-doublon retry)
- Annoté 51 points d'audit dans le code (marqueurs `AUDIT[AX-NNN]` : 9 CRITICAL, 31 FRAGILE, 11 ACCEPTED)
- Tests: 425 passed, 0 failed, 10 skipped

## [2026-02-10] Phase 3.1 — Corrections post-audit

- Installé pytest-asyncio, configuré asyncio_mode=auto (résout 32 failures async)
- Corrigé test_esmm_phase1.py: async fixture cleanup avec close_pool() (résout 1 error)
- Migré 10 tests Phase 0.3 vers nouveaux tiers (sandbox/proposition/validated/verified)
- Corrigé test_phase1_client.py: asyncio.get_event_loop() → async/await (résout 2 failures)
- Ajouté run_id dans post_crystallization hook (traçabilité)
- Vérifié alignement signature record_model_prediction (engine.py ↔ post_crystallization.py)
- Corrigé isolation DB tests : fixture conftest.py reset pool + singleton entre tests
- Corrigé rollback_deltas() : utilise applied_at au lieu de timestamp pour le filtre to_timestamp
- Corrigé rollback_deltas() : supporte rollback all (sans delta_ids ni to_timestamp)
- Sécurisé rollback DELETE_EDGE : INSERT OR REPLACE (anti UNIQUE constraint)
- Tests: 425 passed, 0 failed, 10 skipped (avant: 368 passed, 53 failed, 5 errors)

## [2026-02-10] Phase 3 — End-to-end pipeline

- config_loader.py: centralized config.yaml loading (singleton)
- MockProvider: realistic mock for full pipeline testing without Ollama
- orchestrator.py: ESMMRunResult enriched with consensus_triplets field
- cycle_manager.py: create_cycle_manager() accepts optional providers parameter
- pipeline.py: _extract_triplets_from_question() calls real orchestrator (D1-D4)
- pipeline.py: post-crystallization hook for track record + tier transitions (D8)
- pipeline.py: graph seeding from question on empty graph (D7)
- triplet_adapter.py: ConsensusTriplet -> dict pipeline conversion (D4)
- question_seeder.py: tokenizes question and seeds graph concepts (D7)
- post_crystallization.py: records model votes + logs tier transitions (D8)
- epp_cli.py: query reads DB, graph stats reads DB, submit loads/queues attestation (D9)
- engine.py: +3 methods (get_latest_attestation, get_attestation_count, update_attestation_submission_status)
- 3 demo scenarios updated to use MockProviders + real pipeline
- Tests: 264+ pass (76 new Phase 3 tests, 188 Phase 0-2 backward compat)

## [2026-02-08] Phase 2 — Robustesse & Intégrité Épistémique

- Refondu `config.yaml` : zéro référence Lyra, sections EPP complètes (esmm, confidence, solana, track_record, providers)
- Remplacé confidence tiers `low/medium/high` par méthode scientifique : `sandbox/proposition/validated/verified` avec conditions multi-critères (score + modèles + familles archi + source_anchor)
- Créé `services/esmm/pipeline.py` : pont orchestrateur -> cristallisation -> DB -> graphe (remplace les mocks CLI)
- Ajouté tables SQL 20-22 : `metrological_frames`, `model_track_record` (Brier scoring), `tier_transitions` (audit promotions/rétrogradations)
- Ajouté vue `v_model_brier_scores` : Brier score par modèle (fenêtre glissante 90j)
- Ajouté `infer_architecture_family()` dans `base.py` : mesure diversité architecturale pour anti-Sybil
- Ajouté méthodes engine.py : `update_attestation_solana_tx()`, `store_frame()`, `get_frame()`, `list_frames()`, `record_model_prediction()`, `resolve_prediction()`, `get_model_brier_score()`, `log_tier_transition()`
- Ajouté seeder automatique des MetrologicalFrames en DB lors de `initialize()`
- Branché CLI `epp ask` sur pipeline réel (pas de mocks)
- Créé 3 scénarios de démonstration dans `demos/`
- 61 tests Phase 2, 77 tests Phase 1 backward compat (tous verts)

## [2026-02-06] Phase 1 — Finalisation build Anchor + config

- Programme Anchor build OK : `anchor build` produit `epp.so` (221 KB) + IDL
- Programme ID deploye : `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`
- Ajout `DEFAULT_PROGRAM_ID` dans `services/solana/config.py` comme constante et valeur par defaut de `SolanaConfig`
- Test Anchor `ping` passe sur localnet via `anchor test`
- Fix tests async `test_phase1_client.py` : conversion sync (pytest-asyncio non charge)
- 83 tests Phase 1 passent (9 skipped, necessitent solana-test-validator)

## [2026-02-05] Phase 1 — Couche Solana (MVP)

- Cree `services/solana/` : config.py (devnet guard), metrological_frame.py, bridge.py, client.py
- Cree `programs/epp/` : programme Anchor (Rust) avec struct EpistemicAttestation (462 bytes), instruction submit_attestation + ping
- Cree `cli/epp_cli.py` : commandes ask, submit, query, frame list/show, graph stats
- PDA seeds : `[b"attestation", submitter, claim_hash]` — permet multi-submitter par claim
- Bridge Python <-> Anchor : float [0,1] <-> u16 [0,10000], strings <-> fixed bytes zero-padded
- Guard devnet-only : MAINNET absent de l'enum SolanaCluster
- Structure workspace Anchor : `programs/epp/programs/epp/src/` (lib.rs, state.rs, errors.rs, constants.rs)

## [2026-02-05] Phase 0.3 — ESMM Découplé, Cristallisation & Revalidation

- Audit et purge : zéro référence directe à un modèle/provider dans le pipeline ESMM
- Créé `services/esmm/attestation.py` : EpistemicAttestation (Pydantic), crystallize(), compute_claim_hash(), RevalidationInput
- Créé table `attestations` (table 19) : stockage attestations avec signature 5D, votes, provenance
- Créé `services/esmm/run_logger.py` : RunLogger avec PhaseEvent, logging JSON structuré
- Ajouté méthodes engine.py : store/get_attestation, get_attestation_history, get_attestations_by_subject
- Ajouté RevalidationInput : sérialisation des inputs pour revalidation
- 65 tests unitaires + intégration (test_phase03_*.py)

## [2026-02-05] Phase 0.2 — Migration Embedding Sans Perte

- Créé tables `concept_embeddings` (stockage multi-version) et `embedding_migrations` (traçabilité)
- Migration automatique des embeddings existants vers `concept_embeddings` lors de `initialize()`
- `add_concept()` écrit désormais dans les deux tables ; exige `embedding_model` si embedding fourni
- Découpé dimension hardcodée 1024 dans `SemanticMemory` — accepte maintenant toute dimension valide
- `app/embeddings.py` marqué déprécié avec `DeprecationWarning`
- Créé `tools/migrate_embeddings.py` : CLI migration progressive (--dry-run, --finalize, --rollback)
- Ajouté section `embeddings` dans `config.yaml` (active_model, fallback_reembed, similarity_min_score)
- 45 tests unitaires (test_phase02_*.py) couvrant schéma, découplage, migration, recherche cross-version

## [2026-02-04] Phase 0.1 — ModelProvider interface + découplage ESMM

- Créé `services/providers/` : ABC ModelProvider/EmbeddingProvider, OllamaProvider, OpenAICompatProvider, AnthropicProvider, ProviderRegistry
- Créé `MultiProviderRotator` remplaçant `ModelRotator` (provider-agnostique)
- Corrections : retry logic OllamaProvider, keep_alive configurable, ProviderRegistry test-friendly (clear_all)
- 55 tests unitaires (test_providers.py + test_rotator.py)
- Refactoré triplet_extractor.py et cycle_manager.py pour utiliser MultiProviderRotator

## [2026-02-03] Initialisation EPP_Verdict

- Fork de Lyra ACE vers EPP_Verdict (Epistemic Proof Program)
- Création `CLAUDE.md` (instructions figées), `ARCHITECTURE.md` (état vivant), `CHANGELOG.md` (ce fichier)
- Objectif : oracle épistémique décentralisé sur Solana — couche de validation sémantique multi-LLM
