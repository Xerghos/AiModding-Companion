@echo off
REM gaming_mode.bat
REM Lanceur pour le mode gaming

echo ==========================================
echo   MODE GAMING - Optimisation Ryzen AI
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
echo Activation du mode gaming...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0disable_ryzen_for_gaming.ps1"

REM Option: Lancer directement un jeu
echo.
set /p launch_game="Voulez-vous lancer un jeu maintenant? (o/n): "
if /i "%launch_game%"=="o" (
    echo.
    echo Entrez le chemin de l'executable de votre jeu:
    echo Exemple: C:\Jeux\MonJeu\game.exe
    set /p game_path="Chemin: "
    
    if exist "%game_path%" (
        echo Lancement de %game_path%...
        start "" "%game_path%"
    ) else (
        echo Fichier non trouve: %game_path%
    )
)

pause
