@echo off
REM ============================================================================
REM  LYRA CLEAN - SERVEUR DE DEMARRAGE
REM ============================================================================

REM Vérifier que l'environnement virtuel existe
if not exist "%~dp0.venv\Scripts\activate.bat" (
    echo.
    echo  ERREUR: Environnement virtuel non trouve
    echo  Executez d'abord: python -m venv .venv
    echo  Puis: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo  LYRA CLEAN - SERVEUR DE DEMARRAGE
echo ============================================================================
echo.
echo  Environnement virtuel trouve: %~dp0.venv
echo.

REM Vérifier si la base de données existe
if not exist "%~dp0data\ispace.db" (
    echo  AVERTISSEMENT: Base de donnees ispace.db non trouvee
    echo   Le serveur sera cree avec des donnees minimales
    echo.
)

REM Configuration par défaut si non définie
if not defined LYRA_MODEL set "LYRA_MODEL=gpt-oss:20b"
if not defined LYRA_NUM_CTX set "LYRA_NUM_CTX=8192"
if not defined LYRA_OLLAMA_URL set "LYRA_OLLAMA_URL=http://localhost:11434"

echo Configuration du serveur:
echo   - Modele: %LYRA_MODEL%
echo   - Contexte: %LYRA_NUM_CTX% tokens
echo   - Ollama URL: %LYRA_OLLAMA_URL%
echo   - Hote: 127.0.0.1
echo   - Port: 8000
echo   - Repertoire: %~dp0
echo.

REM Vérifier la connectivité Ollama
echo Verification de la connectivite Ollama...
curl -s --connect-timeout 3 "%LYRA_OLLAMA_URL%/api/tags" > nul 2>&1
if errorlevel 1 (
    echo  AVERTISSEMENT: Ollama ne semble pas accessible a %LYRA_OLLAMA_URL%
    echo   Assurez-vous qu'Ollama est en cours d'execution
    echo.
) else (
    echo  Ollama connecte avec succes
    echo.
)

echo.
echo ============================================================================
echo  Demarrage du serveur...
echo ============================================================================
echo.

REM Activer l'environnement et lancer le serveur
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
