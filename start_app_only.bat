@echo off
REM Script pour lancer uniquement l'application sans le serveur MCP
REM Utilisez ce script si vous n'avez pas besoin du serveur MCP FastMCP

cd /d "%~dp0"

echo.
echo ========================================
echo   Lancement AiModding-Companion
echo   (sans serveur MCP)
echo ========================================
echo.
echo Pour lancer avec le serveur MCP, utilisez: start_with_mcp.bat
echo.

python run.py

pause

