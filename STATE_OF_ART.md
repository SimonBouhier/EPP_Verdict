# State of the art — quarantaine de contenus non fiables

Dernière revue : 2026-08-09.

## Position du projet

Le filtre EPP de La Vigie est une couche de réduction du risque, pas une preuve
d'innocuité. Un verdict de modèles ne peut ni promouvoir un contenu en mémoire
durable, ni autoriser une action, ni établir seul la robustesse du système.

La validation devra mesurer séparément les faux négatifs, les faux positifs et
la perte d'utilité sur des données tenues, avec labels humains et attaques
adaptatives. En production, la provenance et l'autorité d'une donnée restent
distinctes de son apparence textuelle.

## Travaux déterminants

### AgentDojo — Debenedetti et al. (2024)

- Source : [arXiv:2406.13352](https://arxiv.org/abs/2406.13352)
- Méthode : environnement dynamique de 97 tâches réalistes et 629 cas de
  sécurité pour agents utilisant des outils.
- Résultat utile : sécurité et utilité doivent être mesurées ensemble ; une
  défense peut bloquer l'attaque en cassant aussi la tâche bénigne.
- Conséquence EPP : conserver un échantillon bénin tenu et mesurer la perte
  d'utilité de la quarantaine.

### Adaptive Attacks Break Defenses — Zhan et al. (2025)

- Source : [arXiv:2503.00061](https://arxiv.org/abs/2503.00061)
- Méthode : attaques adaptées à huit défenses, dont détecteurs spécialisés,
  juges LLM, isolation par prompt et filtrage par perplexité.
- Résultat utile : les huit défenses sont contournées avec un taux de succès
  supérieur à 50 % dans leur protocole ; les taux de détection des détecteurs
  visés chutent presque à zéro.
- Conséquence EPP : aucun score de détecteur ne sera interprété comme garantie ;
  la campagne shadow devra inclure des attaques conçues contre le filtre connu.

### Know Thy Judge — Eiras et al. (2025)

- Source : [arXiv:2503.04474](https://arxiv.org/abs/2503.04474)
- Méthode : méta-évaluation de juges de sécurité sous variations de prompt,
  changements de distribution et attaques visant directement le juge.
- Résultat utile : de petites variations de style peuvent augmenter fortement
  les faux négatifs et certaines attaques trompent entièrement certains juges.
- Conséquence EPP : schéma de sortie fermé, raisons codées et aucune reprise de
  texte libre généré par le modèle dans la décision de sécurité.

### A Coin Flip for Safety — Schwinn et al. (2026)

- Source : [arXiv:2603.06594](https://arxiv.org/abs/2603.06594)
- Méthode : audit de juges sur 6 642 sorties annotées par des humains, avec
  changements de modèle, d'attaque et de catégorie sémantique.
- Résultat utile : la fiabilité peut tomber près du hasard sous ces décalages et
  gonfler artificiellement les taux de succès d'attaque.
- Conséquence EPP : labels humains tenus obligatoires avant tout seuil ; aucun
  auto-étiquetage circulaire pour évaluer le filtre.

### BAGEL — Hassan et al. (2026)

- Source : [arXiv:2602.08062](https://arxiv.org/abs/2602.08062)
- Méthode : ensemble incrémental de petits classifieurs spécialisés, routage par
  forêt aléatoire et agrégation de probabilités.
- Résultat utile : l'ensemble améliore efficacité et adaptation dans les jeux
  étudiés, mais suppose des catégories d'attaque déjà connues.
- Conséquence EPP : l'accord multi-modèles est un signal utile mais ne couvre
  pas les attaques hors distribution ; la divergence doit rester visible.

### ARGUS — Weng et al. (2026)

- Source : [arXiv:2605.03378](https://arxiv.org/abs/2605.03378)
- Méthode : graphe de provenance d'influence et vérification de la justification
  causale avant toute action modifiant l'état.
- Résultat utile : classifier le texte ne suffit pas ; l'autorité doit être
  reliée à une provenance bénigne et à la tâche réellement autorisée.
- Conséquence EPP : le sidecar ne peut fournir qu'un avis de quarantaine. La
  future promotion Lyra devra contrôler séparément provenance et autorité.

### Prompt Attack Detection with LLM-as-a-Judge and Mixture-of-Models — Le et al. (2026)

- Source : [arXiv:2603.25176](https://arxiv.org/abs/2603.25176)
- Méthode : 929 cas (770 bénins issus de chatbots publics et 159 attaques
  produites par red teaming), juges LLM à raisonnement structuré, puis mélange
  pondéré dont poids et seuil sont optimisés par grille.
- Résultat utile : les juges généralistes structurés peuvent être compétitifs,
  mais le mélange de plusieurs juges n'apporte que des gains modestes et peut
  se dégrader quand on ajoute des modèles.
- Conséquence EPP : l'ensemble n'est pas présumé supérieur. La campagne V1
  conserve l'unanimité gelée, publie les votes individuels et exige un gain
  conjoint de sécurité et d'utilité plutôt qu'un simple F1 agrégé.

### When Benchmarks Lie — Fomin (2026)

- Source : [arXiv:2602.14161](https://arxiv.org/abs/2602.14161)
- Méthode : 18 jeux de données, quatre familles de modèles et comparaison entre
  validation croisée standard et Leave-One-Dataset-Out (LODO).
- Résultat utile : la validation standard surestime l'AUC de 8 à 16,5 points
  selon le modèle ; 28 à 44 % des principales features SAE sont dépendantes du
  jeu de données, et les écarts par source peuvent atteindre 25 points.
- Conséquence EPP : V1 doit être interprétée par source et par transformation,
  jamais comme preuve hors distribution. Une V2 devra tenir au moins une source
  et une famille d'attaque entièrement hors conception (LODO/LOTO).

### Measuring Real-World Prompt Injection Attacks in Resume Screening — Zhang et al. (2026)

- Source : [arXiv:2605.28999](https://arxiv.org/abs/2605.28999)
- Méthode : environ 200 000 CV réels, deux détecteurs complémentaires, accord
  inter-méthodes et validation humaine stratifiée des positifs et négatifs.
- Résultat utile : les auteurs estiment environ 1 % de CV injectés et observent
  que plus de 90 % des injections détectées n'emploient pas d'instruction
  explicite ; l'accord de détecteurs ne remplace pas l'audit humain ciblé.
- Conséquence EPP : les trois payloads synthétiques figés de V1 qualifient
  l'instrument mais ne couvrent pas la prévalence naturelle. Avant S1, une V2
  devra inclure des baits naturels, une localisation de l'indice et un audit
  humain stratifié des consensus positifs comme négatifs.

### A Critical Evaluation of Defenses against Prompt Injection Attacks — Jia et al. (2025)

- Source : [arXiv:2505.18333](https://arxiv.org/abs/2505.18333)
- Méthode : cadre d'évaluation séparant utilité générale et efficacité, avec
  attaques existantes et adaptatives, appliqué à plusieurs défenses publiées.
- Résultat utile : les revendications de robustesse chutent lorsque les deux
  axes sont mesurés avec des attaques et tâches diversifiées.
- Conséquence EPP : les portes `UER` et `BRR` de V1 restent conjointes ; un
  filtre qui bloque tout ne peut pas confirmer l'hypothèse.

### NetInjectBench — Shayoni et al. (2026)

- Source : [arXiv:2607.10490](https://arxiv.org/abs/2607.10490)
- Méthode : 130 scénarios d'agents réseau séparent explicitement texte non
  fiable, métadonnées d'autorisation fiables et labels réservés à l'évaluation ;
  la sécurité, l'utilité, le surblocage et la fiabilité sont mesurés ensemble.
- Résultat utile : le blocage statique réduit les actions dangereuses mais
  bloque tous les changements légitimes à fort impact dans leur protocole ;
  les auteurs bornent aussi les taux observés par intervalles de Wilson.
- Conséquence EPP : V2 conserve des champs distincts pour le contenu visible,
  la provenance du label et les réponses de mesure. Un gain de sécurité sans
  maintien de l'utilité reste un échec.

### Classifier Risk Estimation under Limited Labeling Resources — Kumar et Raj (2016)

- Source : [arXiv:1607.02665](https://arxiv.org/abs/1607.02665)
- Méthode : estimation de performance sous budget d'annotation par
  échantillonnage aléatoire stratifié, avec allocation proportionnelle, égale
  ou optimale et analyse de la variance de l'estimateur.
- Résultat utile : la stratification réduit la variance à budget fixe lorsque
  les strates sont suffisamment homogènes ; l'effet dépend de la qualité des
  strates et ne transforme pas un petit audit en vérité exhaustive.
- Conséquence EPP : l'audit humain V2 est tiré aléatoirement dans chacune des
  six strates source × type bénin, avec expansion de toute strate où une
  discordance est trouvée. Les résultats restent qualifiants, non déployables.

### False Confidence — Juni, Feragen et Parikh (2026)

- Source : [arXiv:2607.07852](https://arxiv.org/abs/2607.07852)
- Méthode : comparaison d'une même évaluation contre des labels experts et des
  labels automatiques dits *silver*, dans un audit de segmentation médicale.
- Résultat utile : la provenance de la référence modifie les scores et peut
  produire une confiance artificielle ; les auteurs demandent que performances
  et conclusions soient publiées avec la provenance des labels.
- Conséquence EPP : V2 distingue `construction`, `human_audit` et
  `silver_source` dans chaque artefact et chaque tableau. Les 60 cas bénins non
  intégralement audités interdisent de présenter V2 comme benchmark gold ou
  comme autorisation de déploiement S1.

## Format des prochaines entrées

Chaque entrée doit contenir : référence stable, méthode réellement lue,
résultat qui modifie ou confirme la position du projet, puis conséquence
opérationnelle explicite. Les chiffres restent attribués à leur protocole et ne
sont jamais transposés directement à EPP.
