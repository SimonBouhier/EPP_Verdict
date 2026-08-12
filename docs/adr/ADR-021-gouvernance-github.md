# ADR-021 — GitHub comme frontière de gouvernance et de promotion

**Date** : 2026-08-12
**Statut** : Actif
**Dépendances** : ADR-006 (claim hash), ADR-007 (append-only), ADR-012 (sources déterministes), ADR-020 (spécification formelle)

## 1. Contexte

EPP a été présenté autour d'un ancrage Solana alors que son travail propre est
réalisé en amont : délibération ESMM, cristallisation, provenance, stockage
SQLite et production d'une attestation portable. La blockchain a servi de
démonstrateur de publication, mais elle n'est nécessaire ni au raisonnement,
ni à la mesure, ni à la gouvernance interne d'un projet développé sur GitHub.

Cette centralité apparente créait trois confusions :

1. un résultat publié semblait plus autoritaire qu'un résultat seulement local ;
2. les référentiels métrologiques génériques vivaient dans le paquet Solana ;
3. l'acceptation humaine d'une proposition n'avait pas de frontière aussi nette
   que sa publication technique.

## 2. Décision

EPP adopte la séparation suivante :

- **EPP délibère** : ESMM produit des attestations et leurs preuves ;
- **SQLite exécute et conserve** : débats, runs, graphes et états intermédiaires ;
- **GitHub gouverne** : branche, pull request, contrôles et merge portent la
  proposition, la revue et la promotion ;
- **Solana publie éventuellement** : son bridge et son client restent un
  adaptateur devnet facultatif, sans dépendance depuis le noyau.

Le commit fusionné sur la branche protégée atteste qu'une proposition a été
acceptée dans le registre du projet. Il ne transforme pas la proposition en
vérité et ne remplace pas son niveau de confiance épistémique.

### 2.1 Artefact canonique de proposition

`services/governance/proposal.py::AttestationProposal` enveloppe :

- l'attestation portable complète ;
- le hash du référentiel métrologique exact ;
- des références de preuves adressées par SHA-256 ;
- la branche cible ;
- un `proposal_hash` déterministe vérifié à la lecture.

Le champ `decision` ne peut prendre que la valeur `proposed`. Un agent ne peut
donc pas inscrire lui-même `accepted` dans l'artefact : l'acceptation est un
événement Git externe, le merge autorisé.

L'ordre des références de preuves est canonicalisé. Toute modification du
contenu sans recalcul du hash est rejetée. Les preuves brutes ne sont pas
interprétées par cette enveloppe ; elles sont seulement désignées et hachées.

La CI parcourt `governance/proposals/**/*.json`. Elle vérifie les artefacts et
les preuves locales byte-for-byte. Elle ne télécharge jamais les références
HTTPS : leur acquisition demeure hors du job de merge et de ses permissions.

Les valeurs historiques de `FrameGovernance` restent incluses dans les hashes
de frames afin de ne pas casser les attestations publiées. Elles décrivent le
processus d'amendement imaginé lors de leur création ; elles ne confèrent aucun
droit de promotion, désormais réservé au merge protégé.

### 2.2 Frontière de sécurité

Une pull request est une **frontière de promotion**, pas un bus d'ingestion.

```text
source non fiable
    -> quarantaine / job isolé sans secret
    -> ESMM + contrôles déterministes
    -> proposition structurée sur une branche
    -> CI et revue
    -> merge humain vers main
    -> consommation par Lyra ou publication optionnelle
```

En conséquence :

- les contenus bruts, commentaires de PR et instructions rencontrées dans les
  sources ne deviennent jamais des données canoniques par leur seule présence ;
- l'acteur générant une proposition n'a pas le droit de fusionner ni d'écrire
  directement sur `main` ;
- les jobs traitant du contenu non fiable n'obtiennent ni secrets, ni jeton en
  écriture, ni environnement de déploiement ;
- les consommateurs n'utilisent que des artefacts validés et fusionnés ;
- `pull_request_target` ne doit pas exécuter du code ou du contenu non fiable.

## 3. Règles GitHub visées

Avant activation, les contrôles Python doivent être verts et stables. Le
ruleset de la branche par défaut devra ensuite imposer :

1. passage par pull request ;
2. interdiction des suppressions et force-push ;
3. réussite des checks `Python governance gate` et `Lean formal gate` ;
4. résolution des conversations avant merge ;
5. merge manuel par une identité qui n'est pas le job producteur.

Pour le fonctionnement solo initial, zéro approbation formelle est exigée :
GitHub n'autorise pas l'auteur à approuver sa propre PR. Le merge reste manuel.
Une approbation obligatoire sera ajoutée lorsqu'un second reviewer humain sera
disponible.

## 4. Conséquences

### Positives

- gouvernance lisible et peu coûteuse avec les outils déjà utilisés ;
- séparation entre score épistémique et autorité de promotion ;
- historique diffable, testable et reproductible ;
- surface Solana conservée sans imposer ses dépendances au noyau ;
- artefacts directement consommables par Lyra via un pont fin.

### Limites assumées

GitHub est centralisé et son historique n'est pas immuable au sens d'une
blockchain. Les administrateurs et la compromission d'un compte restent dans le
modèle de menace. Rulesets, tags signés et sauvegardes réduisent ce risque sans
le supprimer. Ce niveau de garantie est jugé proportionné à la gouvernance
interne actuelle.

## 5. Migration

1. déplacer la métrologie générique vers `services/metrology.py` ;
2. conserver `services/solana/metrological_frame.py` comme shim d'import ;
3. ajouter l'enveloppe de proposition et ses tests d'intégrité ;
4. ajouter la CI Python et le validateur hors réseau des propositions ;
5. ouvrir une PR dédiée puis activer le ruleset seulement après checks verts ;
6. conserver le programme Solana et le push devnet comme publication opt-in.

La suppression du code Solana, la migration du schéma SQLite et la refonte de
Lyra sont hors périmètre de cet ADR.
