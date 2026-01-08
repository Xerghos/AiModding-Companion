@echo off
REM ai_mode.bat
REM Lanceur pour le mode AI

echo ==========================================
echo   MODE AI - Reactivation Ryzen AI
echo ==========================================
echo.

REM Vérifier les privilèges administrateur
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  Ce script requiert les droits administrateur
    echo.
    echo Pour executer en tant qu'admin:
    echo 1. Clic droit sur ce fichier
    echo 2. "Executer en tant qu'administrateur"
    pause
    exit /b 1
)

REM Exécuter le script PowerShell
echo Activation du mode AI...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0enable_ryzen_ai.ps1"

REM Option: Lancer l'indexation
echo.
set /p launch_index="Voulez-vous lancer l'indexation AI? (o/n): "
if /i "%launch_index%"=="o" (
    echo.
    echo Lancement de l'indexation...
    REM Ici vous pouvez ajouter la commande pour lancer votre indexation
    echo python -m features.context.database index_project_files "."
)

pause
