@echo off
REM ============================================================================
REM LYRA CLEAN - SERVER STARTUP SCRIPT
REM ============================================================================
REM Démarre le serveur Lyra Clean avec environnement virtuel Python
REM Utilise context7 si disponible pour des embeddings optimisés
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration
set "PROJECT_DIR=%~dp0"
set "VENV_PATH=%PROJECT_DIR%.venv"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"
set "HOST=127.0.0.1"
set "PORT=8000"

echo.
echo ============================================================================
echo  LYRA CLEAN - SERVEUR DE DÉMARRAGE
echo ============================================================================
echo.

REM Vérifier la présence du virtualenv
if not exist "%PYTHON_EXE%" (
    echo ❌ ERREUR: Environnement virtuel non trouvé à %VENV_PATH%
    echo.
    echo Solution: Créer l'environnement virtuel avec:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo ✓ Environnement virtuel trouvé: %VENV_PATH%
echo.

REM Vérifier la présence de la base de données
if not exist "%PROJECT_DIR%ispace.db" (
    echo ⚠️  AVERTISSEMENT: Base de données ispace.db non trouvée
    echo   Le serveur sera créé avec des données minimales
    echo.
)

REM Afficher la configuration
echo Configuration du serveur:
echo   - Hôte: %HOST%
echo   - Port: %PORT%
echo   - Répertoire: %PROJECT_DIR%
echo.

REM Vérifier Ollama
echo Vérification de la connectivité Ollama...
"%PYTHON_EXE%" -c "import httpx; httpx.get('http://localhost:11434/api/tags', timeout=5); print('✓ Ollama disponible')" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  Ollama ne semble pas accessible à http://localhost:11434
    echo   Assurez-vous qu'Ollama est en cours d'exécution
    echo.
)

echo.
echo ============================================================================
echo  Démarrage du serveur...
echo ============================================================================
echo.

REM Lancer le serveur
"%PYTHON_EXE%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo ============================================================================
echo  Serveur arrêté
echo ============================================================================
echo.
pause
