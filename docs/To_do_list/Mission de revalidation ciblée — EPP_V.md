# Mission de revalidation ciblée — EPP_Verdict

## Contexte

Il existe déjà :
1. un audit interne ancien : `docs\fr\AUDIT_REPORT.md`
2. un audit externe complémentaire qui a identifié plusieurs points potentiellement nouveaux ou plus précis : `\docs\fr\audit_externe.md`

Ta mission n’est **pas** de repartir de zéro.  
Ta mission est de **revalider méthodiquement l’état actuel du code local**, de **croiser les deux audits**, puis de **préparer un plan de corrections minimalistes**, compatible avec l’architecture existante, **sans ajouter de complexité inutile**.

---

## Posture obligatoire
Tu agis comme un **auditeur adversarial orienté intégration**.

Règles :
- Tu **ne supposes rien**.
- Tu **ne déclares rien “corrigé”** sans preuve observable dans le code local.
- Tu **ne proposes pas de refacto large** si une correction locale, cohérente et minimale suffit.
- Tu **n’introduis pas de nouvelle abstraction** sans démontrer qu’elle réduit réellement la complexité nette.
- Tu **respectes l’architecture existante** ; tu ne la redessines pas.
- Tu **ne transformes pas la mission en nettoyage cosmétique**.
- Tu **priorises le fond** : exactitude, intégrité, cohérence, non-régression, simplicité.

Tu dois distinguer explicitement :
- ✅ **Vérifié dans le code local**
- ⚠️ **Probable / à confirmer**
- ❓ **Non vérifiable sans exécution ou sans artefact supplémentaire**

---

## Objectif principal
Produire une **synthèse de situation fiable** avant toute modification, en répondant à ces questions :

1. Parmi les trouvailles de `AUDIT_REPORT.md`, lesquelles sont :
   - encore vraies,
   - partiellement corrigées,
   - devenues obsolètes ?

2. Parmi les points externes ci-dessous, lesquels sont :
   - réellement nouveaux,
   - déjà couverts implicitement,
   - invalidés par l’état actuel du code local ?

3. Quelles sont les **dernières vérifications utiles** à faire avant de modifier quoi que ce soit ?

4. Quel est le **plan de correction minimal** qui :
   - s’intègre à l’architecture existante,
   - évite la complexité parasite,
   - traite d’abord les points à plus fort risque / meilleur ROI ?

---

## Périmètre de comparaison
Tu dois croiser :
- `AUDIT_REPORT.md`
- le **code local actuel**
- la **configuration locale actuelle**
- la **documentation locale actuelle** si nécessaire

Tu ne dois pas te limiter à GitHub.

---

## Points externes à revalider explicitement
Tu dois vérifier dans le code local si les points suivants sont réels, déjà traités, ou obsolètes.

### A. Chaîne attestation / DB
1. `database/engine.py` : `get_latest_attestation()` trie sur `created_at` alors que la table `attestations` n’aurait pas cette colonne.
2. `append_event()` incrémenterait `message_count` alors qu’un trigger SQL l’incrémente déjà aussi.
3. Les `degree` des concepts pourraient être modifiés à la fois par triggers SQL et par logique Python (`_update_degrees()` / delta / rollback).
4. Les foreign keys SQLite pourraient être déclarées mais non réellement activées.

### B. Tautologies / qualité probatoire des tests
5. `tests/test_adr018_flywheel.py` contiendrait des tests tautologiques qui reconstruisent localement la logique au lieu d’exercer réellement `run_pipeline()`.
6. Une partie des tests prouverait surtout la **plomberie** ou la **présence de champs**, pas le calcul réel.
7. Il faut identifier précisément quels tests critiques sont :
   - probants,
   - faibles,
   - trompeurs,
   - tautologiques.

### C. Complexité inutile
8. Il existe potentiellement trop de **sources de vérité concurrentes** :
   - triggers SQL + logique Python,
   - champs plats + `portable_json` + `consensus_meta`,
   - config centrale + defaults dispersés.
9. `orchestrator.py` pourrait concentrer trop de responsabilités.
10. Il pourrait exister des duplications évitables dans la construction des providers / rotators / mappings modèle↔provider.
11. Il faut repérer les simplifications **à fort ROI** sans casser l’architecture.

### D. Cohérence documentaire
12. Vérifier si le README / la doc locale contiennent encore des contradictions, notamment :
   - nombre de sources déterministes réellement intégrées,
   - modèle d’embedding par défaut,
   - claims publics encore exacts ou datés.

---

## Méthode de travail obligatoire
Tu dois procéder en **4 étapes**.

### Étape 1 — Revalidation de l’audit interne
Lis `AUDIT_REPORT.md` et produis un tableau :
- ID
- sujet
- statut actuel : `toujours vrai` / `partiellement corrigé` / `corrigé` / `obsolète`
- preuve locale précise
- niveau de certitude

Ne te contente pas des titres.  
Vérifie les **fichiers réellement concernés**.

### Étape 2 — Revalidation des points externes
Pour chacun des 12 points listés plus haut :
- dis s’il est **nouveau**, **déjà couvert**, **partiellement couvert**, ou **invalide**
- cite les fichiers et comportements exacts
- indique si cela mérite une correction, une suppression du finding, ou un reclassement

### Étape 3 — Dernières vérifications utiles avant patch
Dresse une liste **courte et hiérarchisée** des vérifications restantes qui ont encore un vrai rendement, par exemple :
- grep caller audit
- comparaison code ↔ schéma
- lecture d’un test critique
- validation config ↔ code
- vérification d’un invariant architectural

Ne propose pas 40 vérifications.  
Seulement les **dernières vérifications réellement utiles**.

### Étape 4 — Plan de correction minimal
Produis un **plan d’implémentation**, mais **sans coder encore**, avec :
- ordre recommandé
- dépendances entre corrections
- risques de régression
- tests à exiger en RED → GREEN → FIX
- simplifications à faire
- simplifications à **ne pas faire**

Le plan doit viser :
- **corrections locales**
- **intégration douce**
- **pas de complexité nouvelle**
- **pas de grand refactor opportuniste**

---

## Contraintes fortes
Tu ne dois **pas** :
- refaire un audit général complet du repo
- proposer une refonte d’architecture
- changer les interfaces publiques sans nécessité démontrée
- introduire une nouvelle couche “manager / service / helper / abstraction” sans preuve de gain net
- corriger des problèmes de style, naming ou mise en forme non critiques
- traiter des points purement cosmétiques
- modifier le code avant d’avoir fini la revalidation et le plan

---

## Format de sortie attendu
Ta réponse doit être structurée exactement ainsi :

# 1. Synthèse exécutive
- verdict global provisoire
- ce qui est réellement nouveau
- ce qui était déjà couvert
- ce qui semble déjà corrigé depuis l’audit interne

# 2. Revalidation de l’audit interne
Tableau ou liste structurée par ID

# 3. Revalidation des points externes
Un item par point A1 à D12

# 4. Dernières vérifications utiles
Liste hiérarchisée, courte

# 5. Plan de correction minimal
Par ordre d’exécution

# 6. Points à ne pas surtraiter
Liste explicite des zones où il ne faut pas ajouter de complexité

# 7. Préconditions avant passage en exécution
Ce qu’il faudra démontrer par tests / diff / grep avant de toucher au code

---

## Niveau d’exigence
Je veux une réponse :
- rigoureuse
- sobre
- non cosmétique
- orientée intégration réelle
- utile pour exécuter ensuite les corrections dans le bon ordre

Tu ne dois pas essayer d’impressionner par la largeur.  
Tu dois être **précis, crédible, et économiquement utile**.

---

## Rappel final
Le but n’est pas de “faire plus propre”.  
Le but est de :
- **sécuriser les derniers points vraiment importants**
- **éviter les faux positifs de validation**
- **réduire la complexité là où elle ne paie pas son loyer**
- **préparer des correctifs minimaux compatibles avec l’architecture globale existante**