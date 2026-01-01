@echo off
REM Script de démarrage rapide pour capturer les payloads gemini-cli
REM Usage: START_CAPTURE.bat

echo ================================================================================
echo DEMARRAGE DE LA CAPTURE PAYLOADS GEMINI-CLI
echo ================================================================================
echo.

REM Vérifier si mitmproxy est installé
python -c "import mitmproxy" 2>nul
if errorlevel 1 (
    echo [ERREUR] mitmproxy n'est pas installe
    echo.
    echo Installation de mitmproxy...
    pip install mitmproxy
    if errorlevel 1 (
        echo [ERREUR] Echec de l'installation de mitmproxy
        pause
        exit /b 1
    )
)

echo [OK] mitmproxy est installe
echo.

REM Vérifier si le proxy est déjà en cours d'exécution
tasklist /FI "IMAGENAME eq mitmdump.exe" 2>NUL | find /I /N "mitmdump.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [WARN] mitmproxy semble deja en cours d'execution
    echo        Arretez-le d'abord si vous voulez le redemarrer
    echo.
)

echo ================================================================================
echo INSTRUCTIONS
echo ================================================================================
echo.
echo 1. Ce script va demarrer le proxy mitmproxy
echo 2. Dans un AUTRE terminal, configurez gemini-cli:
echo    set HTTP_PROXY=http://localhost:8080
echo    set HTTPS_PROXY=http://localhost:8080
echo 3. Dans le MEME terminal (ou les variables sont definies), executez gemini-cli
echo 4. Les payloads seront sauvegardes dans logs/
echo.
echo ================================================================================
echo DEMARRAGE DU PROXY
echo ================================================================================
echo.

REM Démarrer mitmproxy
mitmdump -s scripts/capture_gemini_cli_mitmproxy.py

pause
