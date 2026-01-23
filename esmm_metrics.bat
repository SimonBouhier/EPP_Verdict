@echo off
REM ============================================================================
REM  LYRA ESMM - METRIQUES ET COUVERTURE
REM ============================================================================
REM  Affiche les metriques de couverture du graphe et les lacunes
REM
REM  Usage:
REM    esmm_metrics.bat              - Metriques de couverture
REM    esmm_metrics.bat coverage     - Metriques de couverture detaillees
REM    esmm_metrics.bat gaps         - Lacunes actives
REM    esmm_metrics.bat gaps bridge  - Lacunes de type bridge
REM    esmm_metrics.bat cochain      - Stats de la 0-cochaine
REM ============================================================================

setlocal enabledelayedexpansion

set "API_URL=http://127.0.0.1:8000"

echo.
echo ============================================================================
echo  LYRA ESMM - Metriques du Graphe
echo ============================================================================
echo.

REM Verifier que le serveur est accessible
curl -s --connect-timeout 3 "%API_URL%/health" > nul 2>&1
if errorlevel 1 (
    echo  ERREUR: Serveur non accessible a %API_URL%
    pause
    exit /b 1
)

set "COMMAND=%1"
set "SUBCOMMAND=%2"

if "%COMMAND%"=="" set "COMMAND=coverage"

if "%COMMAND%"=="coverage" (
    echo  Metriques de Couverture:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/coverage/metrics"
    echo.
    echo.
    echo  Legende:
    echo    coverage_score       - Score composite [0,1]
    echo    consensus_density    - Accord moyen des modeles
    echo    epistemic_diversity  - Diversite des types
    echo    structural_stability - Stabilite du graphe
    echo    graph_density        - Densite des connexions
    echo    isolated_ratio       - Concepts isoles
    echo.
) else if "%COMMAND%"=="gaps" (
    if "%SUBCOMMAND%"=="" (
        echo  Lacunes Actives (tous types):
        echo  ----------------------------------------
        curl -s "%API_URL%/graph/gaps/active?limit=30"
    ) else (
        echo  Lacunes de type: %SUBCOMMAND%
        echo  ----------------------------------------
        curl -s "%API_URL%/graph/gaps/active?gap_type=%SUBCOMMAND%&limit=30"
    )
    echo.
    echo.
    echo  Types de lacunes:
    echo    isolated  - Concepts a faible degre
    echo    unstable  - Triplets a haute variance
    echo    bridge    - Liens inter-domaines manquants
    echo.
) else if "%COMMAND%"=="cochain" (
    echo  Statistiques de la 0-Cochaine:
    echo  ----------------------------------------
    curl -s "%API_URL%/graph/cochain/stats"
    echo.
    echo.
    echo  Types epistemiques:
    echo    generalist  - Haut degre, relations diverses
    echo    specialized - Domaine specifique
    echo    hybrid      - Mix des deux
    echo.
) else (
    echo  Commande inconnue: %COMMAND%
    echo.
    echo  Commandes disponibles:
    echo    coverage  - Metriques de couverture
    echo    gaps      - Lacunes actives
    echo    cochain   - Stats de la 0-cochaine
    echo.
)

pause
