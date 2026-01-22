@echo off
REM ============================================================================
REM LYRA CLEAN - BENCHMARK E2E LAUNCHER
REM ============================================================================
REM Lance le benchmark complet avec tous les niveaux de conscience
REM Prérequis: Serveur fonctionnant sur http://localhost:8000
REM ============================================================================

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "VENV_PATH=%PROJECT_DIR%.venv"
set "PYTHON_EXE=%VENV_PATH%\Scripts\python.exe"

echo.
echo ============================================================================
echo  LYRA CLEAN - BENCHMARK E2E
echo ============================================================================
echo.

REM Vérifier que le venv existe
if not exist "%PYTHON_EXE%" (
    echo ❌ ERREUR: Environnement virtuel non trouvé
    echo    Lancez d'abord SETUP_ENVIRONMENT.bat
    pause
    exit /b 1
)

REM Vérifier que le serveur est accessible
echo Vérification du serveur...
"%PYTHON_EXE%" -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" 2>nul
if !errorlevel! neq 0 (
    echo ❌ ERREUR: Serveur non accessible à http://localhost:8000
    echo.
    echo Assurez-vous que le serveur est en cours d'exécution:
    echo   1. Double-cliquez sur START_SERVER.bat
    echo   2. Attendez le message "Uvicorn running on..."
    echo   3. Relancez ce benchmark
    echo.
    pause
    exit /b 1
)
echo ✓ Serveur accessible
echo.

REM Vérifier Ollama
echo Vérification d'Ollama...
"%PYTHON_EXE%" -c "import httpx; httpx.get('http://localhost:11434/api/tags', timeout=5); print('✓ Ollama disponible')" 2>nul
if !errorlevel! neq 0 (
    echo ⚠️  AVERTISSEMENT: Ollama ne semble pas accessible
    echo    Le benchmark ne fonctionnera pas sans Ollama
    echo.
)

echo.
echo ============================================================================
echo  Configuration du benchmark:
echo ============================================================================
echo   - Serveur: http://localhost:8000
echo   - Niveaux testés: 0 (baseline), 1 (passif), 2 (adaptatif), 3 (mémoire)
echo   - Prompts par niveau: 10
echo   - Total: 40 appels LLM (attention: 10-15 min)
echo.

pause
echo Lancement du benchmark... Cela peut prendre 10-15 minutes.
echo.

REM Lancer le benchmark
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" tests/benchmarks/benchmark_e2e.py

echo.
echo ============================================================================
echo  Résultats sauvegardés dans: benchmark_results/
echo ============================================================================
echo.
pause
