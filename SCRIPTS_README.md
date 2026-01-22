# 🚀 LYRA CLEAN - SCRIPTS DE LANCEMENT

Trois fichiers `.bat` simples pour gérer le système Lyra Clean sans ligne de commande.

## 📋 Scripts disponibles

### 1. **SETUP_ENVIRONMENT.bat** ⚙️
**Objectif**: Configurer l'environnement au premier lancement

**Actions**:
- ✓ Crée l'environnement virtuel Python (`.venv`)
- ✓ Installe les dépendances (`requirements.txt`)
- ✓ Vérifie la connectivité Ollama
- ✓ Teste les imports principaux
- ✓ Vérifie la base de données

**Quand l'utiliser**:
- 🔴 Première installation
- 🔴 Après modification de `requirements.txt`
- 🔴 Après suppression accidentelle du dossier `.venv`

**Double-cliquez sur** `SETUP_ENVIRONMENT.bat`

---

### 2. **START_SERVER.bat** 🖥️
**Objectif**: Démarrer le serveur Lyra Clean

**Actions**:
- ✓ Vérifie l'environnement virtuel
- ✓ Teste la connexion Ollama
- ✓ Lance le serveur sur `http://127.0.0.1:8000`
- ✓ Active le mode `--reload` (rechargement automatique)

**Console affichée**:
```
Uvicorn running on http://127.0.0.1:8000
Application startup complete
```

**État prêt** ✅: Quand vous voyez "Application startup complete"

**Prérequis**:
- ✓ Ollama en cours d'exécution (`ollama serve` dans un terminal)
- ✓ Base de données `ispace.db` présente

**Double-cliquez sur** `START_SERVER.bat`

---

### 3. **RUN_BENCHMARK_E2E.bat** 📊
**Objectif**: Exécuter le benchmark complet de bout en bout

**Actions**:
- ✓ Vérifie que le serveur est accessible (`/health`)
- ✓ Teste la connexion Ollama
- ✓ Lance 40 appels LLM (10 par niveau de conscience)
- ✓ Génère rapports CSV + JSON

**Résultats générés**:
```
benchmark_results/
├── e2e_benchmark_YYYYMMDD_HHMMSS.csv
└── e2e_benchmark_YYYYMMDD_HHMMSS_config.json
```

**Durée attendue**: ⏱️ 10-15 minutes

**Prérequis**:
- ✓ `START_SERVER.bat` en cours d'exécution (autre fenêtre)
- ✓ Ollama actif

**Double-cliquez sur** `RUN_BENCHMARK_E2E.bat`

---

## 🎯 Workflow complet d'utilisation

### Première installation
```
1. Double-cliquez sur SETUP_ENVIRONMENT.bat
   ↓ Crée .venv + installe pip packages
   ↓ Affiche ✅ DIAGNOSTIC TERMINÉ

2. Lancez Ollama (terminal séparé)
   → ollama serve

3. Double-cliquez sur START_SERVER.bat
   ↓ Serveur démarré sur :8000
```

### Utilisation quotidienne
```
1. Lancez Ollama (si pas en cours d'exécution)
   → ollama serve

2. Double-cliquez sur START_SERVER.bat
   ↓ Serveur prêt

3. Utilisez le serveur via:
   - API: http://localhost:8000
   - Docs interactives: http://localhost:8000/docs
```

### Lancer le benchmark
```
1. START_SERVER.bat en cours d'exécution
2. Double-cliquez sur RUN_BENCHMARK_E2E.bat
3. Attendez 10-15 minutes
4. Consultez les résultats dans benchmark_results/
```

---

## ⚙️ Configuration avancée

### Modifier l'hôte/port du serveur
Éditez `START_SERVER.bat`:
```batch
set "HOST=0.0.0.0"    # Écouter sur toutes les interfaces
set "PORT=8080"       # Changer le port
```

### Désactiver le rechargement automatique
Éditez `START_SERVER.bat`, ligne de lancement:
```batch
REM Retirer --reload:
"%PYTHON_EXE%" -m uvicorn app.main:app --host %HOST% --port %PORT%
```

### Vérifier les logs détaillés
Les fichiers `.bat` affichent les erreurs. Pour plus de détails:
```bash
# Terminal PowerShell:
cd C:\Users\simon\PROJECTS\lyra_clean
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## 🆘 Dépannage

### ❌ "Environnement virtuel non trouvé"
→ Lancez `SETUP_ENVIRONMENT.bat`

### ❌ "Ollama n'est pas accessible"
→ Lancez `ollama serve` dans un terminal séparé

### ❌ "Serveur n'est pas accessible" (lors du benchmark)
→ Assurez-vous que `START_SERVER.bat` est en cours d'exécution

### ❌ "Import error: services.consciousness"
→ Lancez `SETUP_ENVIRONMENT.bat` pour réinstaller les dépendances

### ❌ La fenêtre se ferme immédiatement
→ Il y a une erreur d'initialisation. Lancez depuis PowerShell pour voir les logs:
```bash
cd C:\Users\simon\PROJECTS\lyra_clean
.venv\Scripts\python app/main.py
```

---

## 📊 Interprétation des résultats du benchmark

Après `RUN_BENCHMARK_E2E.bat`, ouvrez le CSV généré:

| Level | Avg Latency | vs Baseline | Memory Echoes |
|-------|-------------|------------|---------------|
| 0 | 8-12s | 0ms | N/A |
| 1 | 8-12s | <100ms | Non |
| 2 | 8-12s | <100ms | Non |
| 3 | 8-12s | <500ms | ✓ Oui (tours 2+) |

**Overhead acceptable** ✅: 
- L1: < 100ms
- L2: < 100ms
- L3: < 500ms

---

## 🔍 Liens rapides

- **API Docs**: http://localhost:8000/docs (une fois serveur actif)
- **Health Check**: http://localhost:8000/health
- **Résultats Benchmark**: `benchmark_results/` (dossier local)
- **Logs Serveur**: Console de `START_SERVER.bat`

---

**Bon courage ! 🚀**
