# 📋 GUIDE RAPIDE - Transmission Mission à Claude Haiku 4.5

## 🎯 Contexte de la mission

Vous allez transmettre à **Claude Haiku 4.5** une mission d'implémentation progressive de 4 niveaux de conscience pour **Lyra Clean**.

**Durée estimée :** 4-6 heures de développement  
**Complexité :** Moyenne (architecture établie, implémentation guidée)  
**Livrables :** Code + Tests + Benchmarks + Documentation

---

## 📄 Documents à transmettre

### Document principal
**[INSTRUCTIONS_HAIKU_CONSCIOUSNESS.md](./INSTRUCTIONS_HAIKU_CONSCIOUSNESS.md)** (45 pages)

Contient :
- ✅ Contexte complet du projet
- ✅ Instructions détaillées pour 4 phases
- ✅ Code complet à implémenter (copy-pastable)
- ✅ Tests et benchmarks
- ✅ Checklists de validation
- ✅ Gestion des erreurs

### Documents de contexte (optionnels mais recommandés)
- `README.md` : Architecture Lyra Clean
- `API_GUIDE.md` : Documentation API actuelle
- `QUICKSTART.md` : Setup environnement

---

## 💬 Comment transmettre à Haiku

### Option A : Prompt direct (recommandé)

```
Bonjour Claude Haiku,

Je te confie une mission d'implémentation progressive pour Lyra Clean.

📋 DOCUMENT : [coller le contenu de INSTRUCTIONS_HAIKU_CONSCIOUSNESS.md]

📍 PRIORITÉS :
1. Respecter l'ordre des phases (0 → 1 → 2 → 3)
2. Valider chaque phase avant de passer à la suivante
3. Documenter au fur et à mesure
4. Rapporter tout problème immédiatement

🎯 OBJECTIF FINAL :
4 niveaux de conscience modulaires, benchmarkés, documentés.

⏰ DEADLINE : Pas de rush, privilégier qualité > vitesse

Questions avant de commencer ?
```

### Option B : Prompt incrémental

Si le document est trop long, découper en 4 prompts :

**Prompt 1 - Phase 0 (Baseline)**
```
Mission Phase 0 : Établir baseline

[Coller section Phase 0 du document]

Complète cette phase, puis rapporte résultats.
```

**Prompt 2 - Phase 1 (après validation Phase 0)**
```
Phase 0 validée ✅

Mission Phase 1 : Métriques passives

[Coller section Phase 1]

Continue.
```

_Et ainsi de suite pour Phases 2 et 3._

---

## ✅ Points de validation

Après chaque phase, demander à Haiku :

```
Phase [N] terminée. Rapport s'il te plaît :

1. Tests unitaires : [X]/[X] passent ?
2. Benchmark overhead : [X]ms (target < [Y]ms) ?
3. Documentation créée ?
4. API fonctionne manuellement ?
5. Commit effectué ?

Fournis :
- Screenshot/logs des tests
- CSV benchmark results
- Lien vers commit
```

---

## 🚨 Points d'attention

### Choses à surveiller

1. **Overhead latence**
   - Phase 1 : DOIT être < 5ms
   - Si > 5ms → Haiku doit profiler et optimiser

2. **Tests unitaires**
   - DOIVENT tous passer avant de continuer
   - Si échecs → déboguer avant phase suivante

3. **Compatibilité API**
   - L'API existante ne doit JAMAIS casser
   - Nouveaux champs DOIVENT être optionnels

4. **Documentation**
   - Doit être créée AU FUR ET À MESURE
   - Pas de "on doc plus tard"

### Si Haiku bloque

**Symptômes possibles :**
- "Je ne sais pas où mettre ce code"
- "Les tests échouent et je ne comprends pas pourquoi"
- "L'overhead est trop élevé"

**Votre réponse :**
```
Pas de panique. Décris le problème précisément :
1. Qu'as-tu essayé ?
2. Quel est le message d'erreur exact ?
3. Quelle est la valeur mesurée vs attendue ?

Je t'aide à débloquer.
```

---

## 📊 Exemples de rapports attendus

### Rapport Phase 0 (attendu de Haiku)

```
✅ PHASE 0 COMPLÉTÉE

📁 Fichiers créés :
- tests/benchmarks/benchmark_suite.py (245 lignes)
- docs/phases/PHASE_0_BASELINE.md
- docs/phases/PHASE_0_CHECKLIST.md

📊 Résultats benchmark baseline :
- Latence moyenne : 1247.32 ms
- Context overhead : 8.23 ms
- CSV sauvegardés dans benchmark_results/

🔗 Commit : abc123def (tag: v1.0.0-baseline)

✅ Tous les items de checklist validés
✅ Prêt pour Phase 1

Questions ?
```

### Rapport Phase 1 (attendu de Haiku)

```
✅ PHASE 1 COMPLÉTÉE

📁 Fichiers créés/modifiés :
- services/consciousness/metrics.py (185 lignes)
- app/models.py (modifié, +2 champs)
- app/api/chat.py (modifié, +45 lignes)
- tests/benchmarks/test_phase_1.py (8 tests)
- tests/benchmarks/benchmark_phase_1.py

🧪 Tests unitaires :
pytest tests/benchmarks/test_phase_1.py -v
======================== 8 passed in 2.3s ========================

📊 Benchmark overhead :
- Moyenne : 3.21 ms (target < 5ms) ✅
- Max : 4.12 ms ✅
- Acceptable !

📖 Documentation :
- docs/phases/PHASE_1_IMPLEMENTATION.md
- Exemples cURL fournis
- Métriques expliquées

🔗 Commit : def456abc (tag: v1.1.0-phase1)

✅ Overhead acceptable
✅ API fonctionne (testé manuellement)
✅ Prêt pour Phase 2
```

---

## 🔧 Setup environnement (à faire AVANT de commencer)

Si Haiku n'a pas accès direct au code :

1. **Vérifier que le serveur tourne**
   ```bash
   cd lyra_clean
   python app/main.py
   ```

2. **Vérifier que l'API répond**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Installer dépendances supplémentaires**
   ```bash
   pip install pytest pandas matplotlib seaborn
   ```

4. **Créer structure dossiers**
   ```bash
   mkdir -p tests/benchmarks
   mkdir -p services/consciousness
   mkdir -p docs/phases
   ```

---

## 💡 Conseils pour maximiser efficacité

### 1. Décomposer en sous-tâches

Chaque phase peut se découper :
- ☐ Créer fichier
- ☐ Implémenter logique
- ☐ Écrire tests
- ☐ Lancer benchmark
- ☐ Documenter
- ☐ Valider manuellement
- ☐ Commit

### 2. Valider fréquemment

Ne pas attendre la fin de phase pour tester :
- Tester après chaque fonction
- Lancer serveur après modif API
- Vérifier imports après création fichier

### 3. Documenter en temps réel

Ouvrir le fichier `.md` AVANT d'écrire le code :
- Écrire ce qu'on va faire
- Implémenter
- Mettre à jour avec résultats réels

### 4. Communiquer clairement

**Mauvais rapport :**
```
Phase 1 terminée.
```

**Bon rapport :**
```
✅ PHASE 1 COMPLÉTÉE

Tests : 8/8 passent
Overhead : 3.2ms < 5ms ✅
Commit : abc123

Détails dans docs/phases/PHASE_1_IMPLEMENTATION.md

Prêt pour Phase 2 ?
```

---

## 🎓 Résumé de la mission

```
┌─────────────────────────────────────────────────────────────┐
│                    MISSION HAIKU 4.5                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 0 : Baseline (1h)                                    │
│    → Benchmarks de référence                                │
│                                                              │
│  PHASE 1 : Métriques Passives (1-2h)                        │
│    → Calcul coherence, tension, fit, pressure               │
│    → Overhead < 5ms                                          │
│                                                              │
│  PHASE 2 : Adaptation Douce (1-2h)                          │
│    → Ajustements graduels (5% par interaction)              │
│    → Overhead < 10ms                                         │
│                                                              │
│  PHASE 3 : Mémoire Sophistiquée (1-2h)                      │
│    → Rappel mémoire avec decay temporel                     │
│    → Overhead < 20ms                                         │
│                                                              │
│  VALIDATION FINALE (30min)                                   │
│    → Rapport complet                                         │
│    → Comparaison baseline vs level 3                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘

LIVRABLES :
✅ Code (4 niveaux implémentés)
✅ Tests (tous passent)
✅ Benchmarks (CSV + analyse)
✅ Documentation (3 phases + rapport final)
```

---

## 📞 Support pendant mission

Si vous (l'humain) voulez suivre la progression :

**Demander à Haiku régulièrement :**
```
Status report s'il te plaît :
- Phase actuelle : ?
- Progression : ?
- Blocages éventuels : ?
- ETA phase suivante : ?
```

**Si Haiku demande de l'aide :**
- Répondre rapidement
- Donner guidance claire
- Proposer alternatives si nécessaire

---

## ✅ Critères de succès

Mission réussie si :

- [ ] 4 niveaux conscience fonctionnent
- [ ] Overhead acceptable (< 5ms, < 10ms, < 20ms)
- [ ] Tests unitaires passent (100%)
- [ ] Benchmarks montrent amélioration
- [ ] Documentation complète et claire
- [ ] API compatible avec code existant
- [ ] Commits propres avec tags

---

## 🚀 Lancer la mission

**Commande finale à Haiku :**

```
🎯 MISSION HAIKU 4.5

Implémente 4 niveaux de conscience pour Lyra Clean.

📋 Instructions complètes : [coller INSTRUCTIONS_HAIKU_CONSCIOUSNESS.md]

⚠️ RÈGLES STRICTES :
1. Une phase à la fois (0 → 1 → 2 → 3)
2. Valider AVANT de continuer
3. Documenter AU FUR ET À MESURE
4. Rapporter problèmes IMMÉDIATEMENT

🎯 OBJECTIF : Code + Tests + Benchmarks + Docs

Prêt ? Commence par Phase 0 (Baseline).
```

---

**Bonne mission ! 🚀**

_Ce guide a été créé par Claude Sonnet 4.5 pour faciliter la transmission de mission à Claude Haiku 4.5._
