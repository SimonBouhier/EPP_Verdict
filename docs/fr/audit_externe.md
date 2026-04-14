retour d’audit, limité aux phases 1–2 : cartographie des surfaces critiques + coutures les plus risquées.
Je n’ai pas de preuve d’exécution (pytest, logs, benchs, diff), donc je n’atteste pas les claims publics du repo. Ce qui suit est une lecture adversariale du code. Le verdict ne peut pas dépasser 🟠 ORANGE à ce stade.

Qualification provisoire

🟠 ORANGE — périmètre audité.
J’ai trouvé plusieurs anomalies ✅ vérifiées dans le code sur la chaîne pipeline ↔ attestation ↔ DB, dont une divergence code/schéma franchement sérieuse.

1) Priorité haute — divergence code ↔ schéma sur les attestations

✅ Vérifié

database/engine.py a une méthode get_latest_attestation() qui fait SELECT * FROM attestations ORDER BY created_at DESC, alors que la table attestations dans database/schema.sql expose timestamp, anchored_at, etc., mais pas de colonne created_at. C’est une couture cassée nette : si ce chemin est appelé, il est au mieux faux, au pire cassant.

Pourquoi c’est important :
ça touche l’accès au “dernier état” d’une attestation, donc potentiellement du reporting, du submit on-chain, ou de la supervision.

2) Priorité haute — double autorité sur l’état : triggers SQL + logique Python
a) message_count probablement incrémenté deux fois

✅ Vérifié

Le schéma définit un trigger tr_event_insert_update_session qui incrémente message_count après insertion dans events. En parallèle, append_event() dans engine.py fait aussi un UPDATE sessions SET message_count = message_count + 1. Même événement, deux incréments.

b) degree des concepts probablement doublé dans les deltas

✅ Vérifié

Le schéma a des triggers tr_relation_insert_update_degree et tr_relation_delete_update_degree. Mais apply_delta() et certains rollbacks dans engine.py appellent aussi _update_degrees(...) après insertion/suppression de relations. Même mutation, deux mécanismes de comptage.

Pourquoi c’est important :
tu as ici un projet où la structure du graphe sert au raisonnement. Si les degrés dérivent, la centralité, les choix d’exploration ou certaines métriques peuvent devenir silencieusement faux.

3) Priorité haute — intégrité déclarée mais probablement non imposée

✅ Vérifié / ⚠️ impact runtime non exécuté

Le schéma déclare beaucoup de FOREIGN KEY, mais l’initialisation DB ne montre pas de PRAGMA foreign_keys=ON; elle active WAL, cache, mmap, busy_timeout, etc. mais pas l’enforcement des FK. En SQLite, ça veut dire que l’intégrité relationnelle peut rester décorative si rien d’autre ne l’active.

Pourquoi c’est important :
sur un protocole de preuve/traçabilité, une DB avec des FK “sur le papier” mais pas appliquées est un risque structurel, pas cosmétique.

4) Priorité moyenne à haute — dégradation silencieuse dans le pipeline

✅ Vérifié

services/esmm/pipeline.py laisse passer plusieurs erreurs en mode “warning puis continue” :

lookup flywheel,
cache lookup,
store_attestation déterministe,
snapshot source,
post_crystallization_hook,
injection graphe,
fallback config dans _get_default_models().

Je comprends l’intention : ne pas bloquer tout le pipeline pour un enrichissement secondaire. Mais dans un protocole épistémique, il faut distinguer clairement :

échec d’ornement
échec de traçabilité
échec de validité

Là, plusieurs chemins sont proches les uns des autres. C’est robuste côté disponibilité, mais risqué côté faux vert.

5) Priorité moyenne — traçabilité ADR-010 stockée, mais pas toujours re-servie

✅ Vérifié

store_attestation() sérialise bien consensus_meta. En revanche, plusieurs getters d’attestations (get_attestations_by_question, get_attestation_by_hash, etc.) ne la re-sélectionnent pas dans leur projection standard. Résultat : on stocke la traçabilité, mais certains chemins de lecture la perdent.

Le code de pipeline.py le sait déjà partiellement : _lookup_existing_anchors() est obligé de reparser portable_json pour retrouver consensus_meta. Ça sent la suture compensatoire.

Impact :
pas forcément crashant, mais mauvais signe de cohérence API interne.

6) Point de vigilance — une logique de traçabilité possiblement mal attachée au bon triplet

⚠️ Inféré à partir du code

Dans pipeline.py, lors de l’enrichissement consensus_meta["verify"], raw_consensus_score est dérivé de la variable triplet encore en scope, pas explicitement de l’attestation best retenue pour le verdict final. Si le dernier triplet itéré n’est pas le bon, la trace méthodologique peut être associée au mauvais score.

Je le classe ⚠️ et non ✅ bloquant, car l’effet exact dépend de l’ordre réel des triplets.

7) Tautologies et tests faibles
Bon point

✅ Vérifié

tests/conftest.py est sérieux sur l’isolation : reset du pool, de l’engine, de la config, de plusieurs singletons ESMM/providers, et en setup et teardown. Sur C7, c’est un bon signal.

Point plus faible

⚠️ Vérifié

Dans tests/test_adr010_consensus_meta.py, beaucoup de tests sont utiles mais structurels :

présence de champs,
hasattr,
signature qui accepte un paramètre,
valeur non None,
sérialisation attendue.

Le test d’intégration test_full_pipeline_adr010 patch services.esmm.pipeline._extract_triplets_from_question. Donc il prouve bien le threading de consensus_meta dans le pipeline, mais pas la validité end-to-end de l’extraction/orchestration réelle.

Verdict sur ce point :
pas une tautologie totale, mais un test utile et partiellement court-circuité. Il sécurise la plomberie, pas le moteur complet.

8) Complexités inutiles déjà visibles

⚠️ Inféré / partiellement vérifié

Le plus net pour l’instant n’est pas une “sur-complexité abstraite”, mais une duplication de responsabilité :

triggers SQL + logique Python pour les compteurs/degrés,
portable_json + consensus_meta + champs plats + relecture partielle,
chemins compensatoires pour récupérer une info déjà stockée.

Ce n’est pas de la forme. C’est de la complexité qui augmente la probabilité de drift.

Hiérarchie actuelle des points à surveiller
Code ↔ schéma des attestations
get_latest_attestation() est le point le plus net à corriger ou requalifier. ✅
Double mise à jour d’état
message_count et degree semblent gérés à la fois par SQL et Python. ✅
Intégrité DB réellement enforce ou non
FK déclarées sans activation visible. ✅/⚠️
Chemins “warning puis continue” dans le pipeline
robustes, mais à borner pour éviter les faux verts. ✅
Traçabilité méthodologique non homogène en lecture
stockée, mais pas toujours restituée. ✅
Tests qui valident la plomberie plus que le calcul réel
surtout autour d’ADR-010. ⚠️
Niveau de certitude

✅ Vérifié par lecture directe du code : 5 points
⚠️ Inféré mais fortement motivé : 2 points
❓ Non vérifiable ici : exécution réelle, pytest, benchs, claims README

Phase 3 ciblée effectuée sur le sous-ensemble le plus sensible côté preuve : ADR-018 flywheel, ADR-012 deterministic/source anchors, ADR-014 audit runner, ADR-010 consensus_meta.
Qualification inchangée : 🟠 ORANGE. J’ai trouvé des tests franchement tautologiques, d’autres correctement bornés mais trop faibles pour soutenir à eux seuls une revendication “le mécanisme est prouvé”. Je n’ai toujours aucune preuve d’exécution pytest, donc je ne valide ni RED→GREEN→FIX ni la résistance à la casse.

Le point le plus net est dans tests/test_adr018_flywheel.py.
test_consensus_meta_flywheel_traceability ne vérifie pas que run_pipeline() peuple réellement la trace flywheel : il appelle _lookup_existing_anchors() et _format_anchor_context(), puis construit lui-même consensus_meta["methodology"]["flywheel"] dans le test. Ce test prouve qu’un dict Python accepte l’affectation attendue, pas que le pipeline de prod le fait correctement. Même problème pour test_flywheel_disabled, qui définit localement flywheel_cfg = {"enabled": False} puis vérifie son propre if, et pour test_flywheel_skipped_in_explore_mode, qui fabrique une FakeConfig(input_mode="explore") et teste la garde locale is_verify. Ces trois tests peuvent rester verts alors qu’un vrai branchement dans run_pipeline() régresse. C’est une tautologie avérée.

Dans tests/test_adr012_source_anchor.py, le repo est honnête sur un cas faible : test_deterministic_subject_fallback_serial dit explicitement qu’il valide la formule inline de résolution du sujet et non l’appel réel à _run_deterministic_pipeline(). Donc ce test est acceptable comme garde locale, mais ne vaut pas preuve de non-régression end-to-end. À l’inverse, les tests _canonical_hash(...) sont de bons tests : ils comparent un calcul déterministe à un SHA-256 manuel et testent l’indépendance à l’ordre des clés, ce qui prouve un vrai comportement. Les tests OpenSanctionsAdapter.normalize() sont aussi concrets : meilleur score, seuil 0.85, résultat vide, fallback de version.

Dans tests/test_adr014_audit_runner.py, la majorité des tests run_audit(...) patchent services.audit.audit_runner.run_pipeline avec un AsyncMock. Ce n’est pas automatiquement mauvais : pour audit_runner.py, ça permet de tester l’orchestration, le tri des unités, l’agrégation de sévérité, le passage du frame, et l’isolation de la DB. Mais cela ne prouve en rien la validité de la détection de vulnérabilités ni la qualité du raisonnement du pipeline d’audit. Le code de production run_audit() délègue justement l’analyse réelle à run_pipeline(), donc quand le test mocke ce point central, il prouve la plomberie du runner, pas le moteur d’audit. Ces tests sont utiles mais scope-limited ; ils deviennent trompeurs seulement s’ils sont brandis comme preuve de la capacité d’audit end-to-end.

Dans tests/test_adr010_consensus_meta.py, il y a deux familles distinctes.
Les tests de persistance sont bons : présence de la colonne consensus_meta, écriture DB réelle via store_attestation(), backfill, non-écrasement, et relecture JSON. Là, on vérifie une vraie couture stockage ↔ lecture. En revanche, plusieurs tests sont surtout structurels : hasattr, présence de champs dans des dataclasses, signature acceptant un paramètre, ou consensus_meta présent dans portable_json. Ce sont des garde-fous de contrat, pas des preuves fortes de calcul. Enfin, test_full_pipeline_adr010 patch _extract_triplets_from_question, donc il sécurise correctement le threading de consensus_meta dans le pipeline, mais pas l’extraction/orchestration réelle.

Hiérarchie des points de surveillance issus de cette phase :

🔴 Tautologies à corriger en priorité
Les tests flywheel qui reconstruisent la logique localement au lieu d’invoquer le vrai pipeline. Ce sont les plus dangereux car ils peuvent donner un faux sentiment de sécurité sur une feature centrale.
🟠 Tests de plomberie utiles mais insuffisants comme preuve du moteur
Les tests d’audit_runner avec run_pipeline mocké, et certains tests ADR-010 patchés. Ils doivent être lus comme tests d’orchestration, pas comme preuves d’intelligence ou de robustesse du système.
🟡 Tests structurels à faible pouvoir de rupture
Vérification d’existence de champs, enums, registres, paramètres. Ils sont légitimes pour geler une API interne, mais faibles contre les régressions sémantiques.
✅ Tests plutôt sains
Hash canonique manuel, normalisation OpenSanctions, persistance réelle de consensus_meta. Ceux-là prouvent des valeurs ou des effets observables.

Complications inutiles repérées côté tests : le pattern le plus coûteux n’est pas le mock en soi, c’est la duplication de logique de prod dans le test. Quand un test recopie la garde, le dict ou la formule au lieu d’appeler le vrai chemin, il devient facile à maintenir mais pauvre en signal. C’est exactement le genre de complication qui “rassure sans vérifier”.

Bilan phase 3 :

✅ Vérifié : plusieurs tests tautologiques existent réellement.
✅ Vérifié : une part notable de la suite ciblée prouve la plomberie plus que le calcul réel.
⚠️ Inféré : sans mutation testing ni exécution rouge/vert, je ne peux pas mesurer combien de ces tests cassent vraiment sur régression.
❓ Non vérifiable ici : la proportion exacte sur l’ensemble des 809 tests.

Phase 4 terminée.

Qualification provisoire

🟠 ORANGE — complexité analysée, sans exécution.
Je distingue ici ce qui me paraît structurellement nécessaire de ce qui ressemble à de la complexité qui élargit la surface de panne sans apporter un gain proportionnel.

Ce qui me paraît justifié

Je ne classerais pas comme “complication inutile” :

la bifurcation EXPLORE / VERIFY / DETERMINISTIC en elle-même,
la séparation attestation off-chain / ancrage on-chain,
l’existence d’une couche de reconciliation / fingerprinting,
ni le fait d’avoir une DB isolée pour l’audit smart contract.

Ces éléments augmentent la complexité, mais ils servent directement la méthode, la traçabilité ou l’isolation du protocole.

Complexités à plus fort ROI de simplification
1) Multiplication des “sources de vérité” pour un même comportement

✅ Vérifié

C’est le point le plus coûteux.
Tu as plusieurs endroits où un même invariant ou paramètre est porté par plusieurs couches :

SQL triggers et logique Python pour certains compteurs/états DB,
config YAML et fallback hardcodé dans plusieurs modules,
champs plats DB et portable_json et consensus_meta pour une même attestation.

Ce n’est pas seulement une question d’élégance. C’est la forme typique de complexité qui :

rend les bugs silencieux plus probables,
augmente le coût mental d’audit,
et pousse le code à écrire des chemins compensatoires.

Hiérarchie : priorité 1.

2) Dispersion des defaults et de la configuration

✅ Vérifié

Le repo a un config_loader.py central, mais plusieurs modules gardent encore leurs propres defaults/fallbacks :

_default_cycle_sequence() et _default_min_consensus() dans orchestrator.py,
_get_default_models() dans pipeline.py,
sélection de modèles et stratégie dans audit_runner.py,
timeouts hardcodés dans cycle_manager.py, avec mention explicite que config.yaml::esmm.timeout_per_cycle_seconds est ignoré.

Ça donne une architecture où la config est centralisée en théorie, mais fédérée dans la pratique.

Pourquoi c’est un vrai coût :
quand tu ajustes une politique d’exécution, tu dois te rappeler quels defaults vivent encore dans le code.

Hiérarchie : priorité 2.

3) Orchestrateur trop large en responsabilités

✅ Vérifié

services/esmm/orchestrator.py fait beaucoup :

lancement et finalisation des runs,
exécution des cycles,
adaptation dynamique,
gestion VERIFY/DETERMINISTIC,
agrégation de stats,
reconciliation fingerprinting,
reprise d’état,
calcul de poids Brier,
persistence intermédiaire/finale.

Ce n’est pas un anti-pattern automatique — un orchestrateur peut être large.
Mais ici, la quantité de politiques métiers + gestion d’erreurs + adaptation + traçabilité dans une seule classe rend la lecture des garanties plus difficile.

Mon diagnostic :
complexité probablement fonctionnelle, mais devenue trop concentrée.

Hiérarchie : priorité 3.

4) Treillis de singletons et invalidations locales

✅ Vérifié

Le système repose sur plusieurs singletons ou quasi-singletons avec règles propres :

config loader,
DB instance dans engine.py,
pool / cache / concurrency limiter dans pool.py,
triplet extractor singleton avec invalidation si DB différente.

Pris isolément, chacun se défend.
Pris ensemble, cela crée une topologie d’état implicite qui augmente :

le coût de raisonnement,
le risque de pollution entre contextes,
et la difficulté à distinguer “vrai comportement” de “comportement de contexte”.

Tes tests compensent bien une partie du problème, mais le fait qu’ils doivent le faire autant est déjà un signal.

Hiérarchie : priorité 4.

5) Architecture “best effort” trop diffusée

✅ Vérifié

Dans le noyau, de nombreux chemins capturent l’erreur et continuent :

pipeline,
orchestrator,
cycle manager,
triplet extractor.

Je ne dis pas qu’il faut tout rendre fatal.
Mais la logique de dégradation gracieuse est tellement présente qu’elle devient elle-même une couche de complexité à surveiller.

Risque :
le système reste vivant, mais la signification épistémique du résultat devient plus difficile à auditer à froid.

Hiérarchie : priorité 5.

6) Duplication de logique provider / mapping modèle↔provider

✅ Vérifié

J’ai un motif de duplication assez net :

create_cycle_manager() construit ses providers Ollama et son rotator,
TripletExtractor.extract_from_text() reconstruit aussi des providers Ollama, des provider_id, un MultiProviderRotator, et le mapping inverse.

Même si les usages ne sont pas identiques, le motif est suffisamment proche pour ressembler à une complexité répétée, donc à une future source de divergence.

Hiérarchie : priorité 6.

7) État interne déclaré mais peu rentable

⚠️ Inféré à partir du fichier

Dans cycle_manager.py, plusieurs états internes sont initialisés :

_response_cache,
_active_gaps,
_gaps_last_updated,
_cache_max_size.

Dans le chemin visible du fichier, ils semblent peu ou pas déterminants pour execute_cycle(). Je ne le monte pas en point critique car je n’ai pas fait une recherche d’usage exhaustive sur tout le repo.

Lecture prudente :
ça ressemble à de la complexité de préparation ou de vestige, pas à une complexité qui porte un invariant vital.

Hiérarchie : priorité 7.

Ce que je considérerais comme “complications inutiles” au sens strict

Pas le raffinement méthodologique.
Pas la modularité.
Pas la stratification.

Les vraies complications inutiles, ici, sont plutôt :

les duplications de responsabilité,
les defaults dispersés,
les chemins compensatoires nécessaires uniquement parce qu’il y a trop de représentations d’un même fait,
et l’état implicite issu des singletons/fallbacks.
Hiérarchie consolidée des optimisations à surveiller
Unifier les sources de vérité
Réduire la dispersion config/defaults
Désengorger l’orchestrator des politiques annexes
Réduire le treillis de singletons et d’invalidation implicite
Encadrer plus explicitement ce qui peut dégrader sans invalider
Factoriser la logique provider/rotator répétée
Élaguer l’état interne peu rentable
Niveau de certitude

✅ Vérifié par lecture directe : 6 points
⚠️ Inféré : 1 point
❓ Non vérifiable ici : coût runtime réel de chaque simplification

