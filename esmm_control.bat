@echo off
REM ============================================================================
REM  LYRA ESMM - CONTROLE DES RUNS
REM ============================================================================
REM  Pause, resume ou arrete un run ESMM
REM
REM  Usage:
REM    esmm_control.bat pause 1    - Met en pause le run #1
REM    esmm_control.bat resume 1   - Reprend le run #1
REM ============================================================================

setlocal enabledelayedexpansion

set "API_URL=http://127.0.0.1:8000"

echo.
echo ============================================================================
echo  LYRA ESMM - Controle des Runs
echo ============================================================================
echo.

if "%1"=="" (
    echo  Usage:
    echo    esmm_control.bat pause [run_id]   - Met en pause
    echo    esmm_control.bat resume [run_id]  - Reprend
    echo.
    echo  Exemple:
    echo    esmm_control.bat pause 1
    echo    esmm_control.bat resume 1
    echo.
    pause
    exit /b 0
)

if "%2"=="" (
    echo  ERREUR: Specifiez un run_id
    echo  Exemple: esmm_control.bat %1 1
    echo.
    pause
    exit /b 1
)

set "ACTION=%1"
set "RUN_ID=%2"

REM Verifier que le serveur est accessible
curl -s --connect-timeout 3 "%API_URL%/health" > nul 2>&1
if errorlevel 1 (
    echo  ERREUR: Serveur non accessible a %API_URL%
    pause
    exit /b 1
)

if "%ACTION%"=="pause" (
    echo  Mise en pause du run #%RUN_ID%...
    curl -s -X POST "%API_URL%/graph/esmm-run/%RUN_ID%/pause"
    echo.
    echo  Run #%RUN_ID% mis en pause
) else if "%ACTION%"=="resume" (
    echo  Reprise du run #%RUN_ID%...
    curl -s -X POST "%API_URL%/graph/esmm-run/%RUN_ID%/resume"
    echo.
    echo  Run #%RUN_ID% en cours de reprise
) else (
    echo  Action inconnue: %ACTION%
    echo  Utilisez: pause, resume
)

echo.
pause
