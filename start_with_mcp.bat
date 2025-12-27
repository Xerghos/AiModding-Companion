@echo off
REM Script pour lancer l'application avec le serveur MCP dans deux onglets séparés
REM Utilise Windows Terminal (wt) pour créer deux onglets

cd /d "%~dp0"

echo.
echo ========================================
echo   Lancement AiModding-Companion
echo   avec serveur MCP séparé
echo ========================================
echo.
echo Démarrage de deux onglets:
echo   - Onglet 1: Serveur MCP FastMCP (http://localhost:8000/mcp)
echo   - Onglet 2: Application principale (sans serveur MCP intégré)
echo.
echo Note: Le serveur MCP et l'application fonctionnent indépendamment.
echo       L'application n'essaiera plus de démarrer son propre serveur MCP.
echo.

REM Vérifier si Windows Terminal (wt) est disponible
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    REM Lancer Windows Terminal avec deux onglets
    start wt -d "%CD%" python start_mcp_server.py ; new-tab -d "%CD%" python run.py
    echo ✅ Application lancée dans Windows Terminal avec deux onglets
) else (
    REM Fallback: lancer deux fenêtres séparées
    echo ⚠️  Windows Terminal non trouvé, utilisation de deux fenêtres séparées
    start "Serveur MCP" cmd /k python start_mcp_server.py
    timeout /t 2 /nobreak >nul
    start "AiModding-Companion" cmd /k python run.py
    echo ✅ Application lancée dans deux fenêtres séparées
)

echo.
echo 💡 Pour arrêter, fermez les fenêtres ou appuyez sur Ctrl+C dans chaque terminal
echo 💡 Le serveur MCP sera accessible à: http://localhost:8000/mcp
echo.

