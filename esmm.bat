@echo off
REM ============================================================================
REM  LYRA ESMM - CLI Principal
REM ============================================================================
REM  Interface en ligne de commande pour gerer les runs ESMM
REM
REM  Usage:
REM    esmm run [--quick|--full] [--watch]
REM    esmm status <run_id>
REM    esmm result <run_id>
REM    esmm pause <run_id>
REM    esmm resume <run_id>
REM    esmm watch <run_id>
REM    esmm metrics
REM    esmm gaps [--type isolated|unstable|bridge]
REM    esmm cochain
REM ============================================================================

setlocal

REM Verifier l'environnement virtuel
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo.
    echo  ERREUR: Environnement virtuel non trouve
    echo  Executez d'abord: python -m venv .venv
    echo.
    pause
    exit /b 1
)

REM Lancer le CLI Python avec tous les arguments
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\esmm_cli.py" %*
