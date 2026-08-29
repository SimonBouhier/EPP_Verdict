# ADR-022 — Recentrage post-blockchain : EPP, organe d'attestation personnel

**Date** : 2026-08-29
**Statut** : Actif
**Dépendances** : ADR-007 (append-only), ADR-021 (gouvernance GitHub)

## 1. Contexte

ADR-021 avait déjà rétrogradé Solana au rang d'« adaptateur devnet facultatif » :
EPP délibère, SQLite conserve, GitHub gouverne, Solana publie éventuellement.

Depuis, l'usage réel a tranché. EPP sert d'**organe d'attestation personnel**
au sein du triptyque (doctrine organes & ponts de `lyra_reborn`) : son
consommateur visé est Lyra, via un pont mince dégelé sur validation — pas un
public externe. La décision est prise (Simon, 2026-08) d'**abandonner la voie
blockchain**, et non plus seulement de la rendre facultative.

Or la surface héritée du sprint Colosseum dit encore le contraire : README et
badges vantent Solana devnet, douze attestations on-chain et un dashboard
public ; le WHITEPAPER argumente la reconnaissance juridique de la preuve
blockchain ; TD-001 maintient une duplication de données au seul service du
dashboard. Cette contradiction entre documents et réalité est exactement le
type de dette que le triptyque s'interdit.

## 2. Décision

1. **Identité.** EPP est un moteur d'attestation épistémique **local et
   personnel** : délibération multi-modèles, cristallisation, provenance,
   attestations portables. Organe indépendant, jamais dépendance — consommé à
   terme par `lyra_reborn` via un pont mince.

2. **Retrait de la couche blockchain.** Le bridge Solana, son client et toute
   publication on-chain passent de « facultatifs » à **retirés** : code gelé en
   l'état, plus maintenu, aucune publication nouvelle. Les douze attestations
   devnet existantes restent des artefacts historiques — le gel n'est pas une
   dette, c'est une clôture (au sens de la clôture Origami v7).

3. **Ancre de confiance unique.** L'acceptation d'une proposition est un
   événement Git : branche protégée, pull request, merge autorisé (ADR-021).
   Aucun autre registre ne fait foi.

4. **Élagage licencié.** Ce recentrage autorise, sans nouvel ADR :
   le réalignement de README, badges et WHITEPAPER (retrait des promesses
   on-chain, reformulation de la vitrine en démo historique) ; la rétrogradation
   du dashboard public au rang d'artefact de démonstration ; la résolution de
   TD-001 par simplification (la duplication `ui/public/data/` n'a plus de
   raison d'être servie) plutôt que par l'API envisagée ; la fermeture de la
   PR #2 (Vercel analytics).

## 3. Conséquences

### Positives

- Les documents redisent la vérité : surface annoncée = surface maintenue.
- Charge de maintenance réduite (Anchor/Cargo, dashboard, parité de données).
- L'identité clarifiée simplifie le futur pont Lyra ↔ EPP : un contrat mince
  entre deux organes locaux, sans détour par un registre public.

### Limites assumées

- Perte de la vitrine publique et de l'argument « ancrage vérifiable par
  tiers ». Si un besoin de publication externe renaît, ce sera un chantier
  nouveau, explicitement pré-enregistré — pas une réactivation silencieuse.
- Le code Solana gelé vieillira sans suivi ; c'est accepté.

## 4. Migration

Les actions d'élagage du §2.4 sont un chantier de suivi (cf. TODO central du
triptyque, volet B) ; elles passent par la gouvernance ADR-021 comme toute
promotion. Le présent ADR n'en exécute aucune : il les licencie.

## 5. Non-buts

- Aucune évidence historique n'est supprimée (ADR-007 reste souverain).
- Le noyau délibératif, le format d'attestation et la couche formelle
  (ADR-020) ne changent pas.
- Cet ADR ne rouvre pas le débat blockchain : il enregistre sa fermeture.
