@echo off
REM ============================================================================
REM  LYRA ESMM - VERIFICATION DU STATUT
REM ============================================================================
REM  Verifie le statut d'un run ESMM en cours ou termine
REM
REM  Usage:
REM    check_esmm_status.bat          - Liste tous les runs recents
REM    check_esmm_status.bat 1        - Statut du run #1
REM    check_esmm_status.bat 1 result - Resultat complet du run #1
REM    check_esmm_status.bat 1 cycles - Cycles du run #1
REM    check_esmm_status.bat 1 gaps   - Lacunes du run #1
REM ============================================================================

setlocal enabledelayedexpansion

set "API_URL=http://127.0.0.1:8000"

echo.
echo ============================================================================
echo  LYRA ESMM - Statut des Runs
echo ============================================================================
echo.

REM Verifier que le serveur est accessible
curl -s --connect-timeout 3 "%API_URL%/health" > nul 2>&1
if errorlevel 1 (
    echo  ERREUR: Serveur non accessible a %API_URL%
    echo  Lancez d'abord: start_server.bat
    echo.
    pause
    exit /b 1
)

if "%1"=="" (
    REM Pas d'argument: afficher l'aide
    echo  Usage:
    echo    check_esmm_status.bat [run_id] [command]
    echo.
    echo  Commands:
    echo    (vide)   - Statut du run
    echo    result   - Resultat complet
    echo    cycles   - Liste des cycles
    echo    gaps     - Lacunes detectees
    echo.
    echo  Exemple:
    echo    check_esmm_status.bat 1
    echo    check_esmm_status.bat 1 result
    echo.
    pause
    exit /b 0
)

set "RUN_ID=%1"
set "COMMAND=%2"

if "%COMMAND%"=="" (
    echo  Statut du run #%RUN_ID%:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/esmm-run/%RUN_ID%"
    echo.
) else if "%COMMAND%"=="result" (
    echo  Resultat du run #%RUN_ID%:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/esmm-run/%RUN_ID%/result"
    echo.
) else if "%COMMAND%"=="cycles" (
    echo  Cycles du run #%RUN_ID%:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/esmm-run/%RUN_ID%/cycles?limit=20"
    echo.
) else if "%COMMAND%"=="gaps" (
    echo  Lacunes du run #%RUN_ID%:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/esmm-run/%RUN_ID%/gaps?limit=20"
    echo.
) else (
    echo  Commande inconnue: %COMMAND%
    echo  Utilisez: result, cycles, gaps
)

echo.
pause
