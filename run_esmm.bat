@echo off
REM ============================================================================
REM  LYRA ESMM - LANCEMENT D'UN RUN COMPLET
REM ============================================================================
REM  Lance le protocole ESMM Phase 3 avec configuration personnalisable
REM
REM  Usage:
REM    run_esmm.bat                   - Run avec config par defaut
REM    run_esmm.bat quick             - Run rapide (1 cycle de chaque)
REM    run_esmm.bat full              - Run complet (3 divergent, 2 debate, 1 meta)
REM    run_esmm.bat custom 2 1 1      - Custom (divergent debate meta)
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration par defaut
set "API_URL=http://127.0.0.1:8000"
set "MODELS=mistral,gpt-oss:20b"
set "SEED_TYPE=standard"
set "DIVERGENT=3"
set "DEBATE=2"
set "META=1"

REM Parser les arguments
if "%1"=="quick" (
    set "DIVERGENT=1"
    set "DEBATE=1"
    set "META=1"
    echo.
    echo  Mode QUICK: 1 cycle de chaque type
    echo.
) else if "%1"=="full" (
    set "DIVERGENT=5"
    set "DEBATE=3"
    set "META=2"
    echo.
    echo  Mode FULL: 5 divergent, 3 debate, 2 meta
    echo.
) else if "%1"=="custom" (
    if not "%2"=="" set "DIVERGENT=%2"
    if not "%3"=="" set "DEBATE=%3"
    if not "%4"=="" set "META=%4"
    echo.
    echo  Mode CUSTOM: %DIVERGENT% divergent, %DEBATE% debate, %META% meta
    echo.
)

echo ============================================================================
echo  LYRA ESMM - Protocole Phase 3
echo ============================================================================
echo.
echo  Configuration:
echo    - API URL: %API_URL%
echo    - Modeles: %MODELS%
echo    - Seed: %SEED_TYPE%
echo    - Cycles: %DIVERGENT% divergent, %DEBATE% debate, %META% meta
echo.

REM Verifier que le serveur est accessible
echo  Verification du serveur...
curl -s --connect-timeout 3 "%API_URL%/health" > nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERREUR: Serveur non accessible a %API_URL%
    echo  Lancez d'abord: start_server.bat
    echo.
    pause
    exit /b 1
)
echo  Serveur OK
echo.

REM Construire le JSON de la requete
set "JSON_FILE=%TEMP%\esmm_request.json"
(
echo {
echo   "models": ["%MODELS:,=", "%"],
echo   "seed_type": "%SEED_TYPE%",
echo   "cycles_per_type": {
echo     "divergent": %DIVERGENT%,
echo     "debate": %DEBATE%,
echo     "meta": %META%
echo   },
echo   "min_consensus": 0.5,
echo   "adaptive_cycles": true,
echo   "detect_gaps": true,
echo   "build_cochain": true
echo }
) > "%JSON_FILE%"

echo ============================================================================
echo  Lancement du run ESMM...
echo ============================================================================
echo.

REM Lancer le run
curl -s -X POST "%API_URL%/graph/esmm-run" ^
    -H "Content-Type: application/json" ^
    -d @"%JSON_FILE%"

echo.
echo.
echo  Run ESMM lance avec succes!
echo.
echo  Pour verifier le statut:
echo    check_esmm_status.bat [run_id]
echo.
echo  Pour voir les resultats:
echo    curl %API_URL%/graph/esmm-run/[run_id]/result
echo.

REM Cleanup
del "%JSON_FILE%" 2>nul

pause
