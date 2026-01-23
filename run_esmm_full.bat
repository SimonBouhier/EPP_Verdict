@echo off
REM ============================================================================
REM  LYRA ESMM - RUN COMPLET
REM ============================================================================
REM  Lance un run ESMM complet (5 divergent, 3 debate, 2 meta) avec surveillance
REM ============================================================================

echo.
echo ============================================================================
echo  LYRA ESMM - Run Complet (5 divergent, 3 debate, 2 meta)
echo ============================================================================
echo.
echo  ATTENTION: Ce run peut prendre plusieurs heures selon les modeles
echo.
pause

call "%~dp0esmm.bat" run --full --watch
