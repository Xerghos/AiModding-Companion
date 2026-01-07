@echo off
REM Script de configuration de l'environnement pour Vitis AI avec Conda
REM Ce script résout le problème "conda n'est pas reconnu"

echo ==========================================
echo Configuration de l'environnement Vitis AI
echo ==========================================

REM 1. Vérifier et configurer le PATH de Conda
set CONDA_FOUND=0

REM Vérifier les chemins courants de Conda
if exist "C:\ProgramData\Anaconda3\Scripts\conda.exe" (
    echo ✓ Conda trouvé à: C:\ProgramData\Anaconda3
    set "PATH=C:\ProgramData\Anaconda3\Scripts;C:\ProgramData\Anaconda3;%PATH%"
    set CONDA_FOUND=1
) else if exist "C:\Users\%USERNAME%\Anaconda3\Scripts\conda.exe" (
    echo ✓ Conda trouvé à: C:\Users\%USERNAME%\Anaconda3
    set "PATH=C:\Users\%USERNAME%\Anaconda3\Scripts;C:\Users\%USERNAME%\Anaconda3;%PATH%"
    set CONDA_FOUND=1
) else if exist "C:\ProgramData\Miniconda3\Scripts\conda.exe" (
    echo ✓ Conda trouvé à: C:\ProgramData\Miniconda3
    set "PATH=C:\ProgramData\Miniconda3\Scripts;C:\ProgramData\Miniconda3;%PATH%"
    set CONDA_FOUND=1
) else if exist "C:\Users\%USERNAME%\Miniconda3\Scripts\conda.exe" (
    echo ✓ Conda trouvé à: C:\Users\%USERNAME%\Miniconda3
    set "PATH=C:\Users\%USERNAME%\Miniconda3\Scripts;C:\Users\%USERNAME%\Miniconda3;%PATH%"
    set CONDA_FOUND=1
)

if %CONDA_FOUND%==0 (
    echo ERROR: Conda non trouvé. Installation requise.
    echo Téléchargez Miniconda depuis: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

REM 2. Vérifier la version de Conda
echo.
echo Vérification de la version Conda...
conda --version
if errorlevel 1 (
    echo ERROR: Erreur avec conda --version
    pause
    exit /b 1
)

REM 3. Initialiser Conda pour l'invite de commandes
echo.
echo Initialisation de Conda pour l'invite de commandes...
call conda init cmd.exe
if errorlevel 1 (
    echo ERROR: Impossible d'initialiser Conda automatiquement
    echo Vous devrez peut-être redémarrer l'invite de commandes
)

REM 4. Vérifier les environnements Conda existants
echo.
echo Liste des environnements Conda disponibles...
conda env list

REM 5. Créer un environnement pour Vitis AI (optionnel)
echo.
echo Création d'un environnement pour Vitis AI...
set ENV_NAME=vitis-ai

REM Vérifier si l'environnement existe déjà
conda env list | findstr /C:"%ENV_NAME%" >nul
if errorlevel 1 (
    echo Création de l'environnement '%ENV_NAME%' avec Python 3.9...
    conda create -n %ENV_NAME% python=3.9 -y
    if errorlevel 1 (
        echo ERROR: Erreur lors de la création de l'environnement
    ) else (
        echo ✓ Environnement '%ENV_NAME%' créé
    )
) else (
    echo ✓ Environnement '%ENV_NAME%' existe déjà
)

REM 6. Instructions pour l'installateur Vitis AI
echo.
echo ==========================================
echo INSTRUCTIONS POUR VITIS AI
echo ==========================================
echo.
echo Maintenant, vous pouvez exécuter l'installateur Vitis AI:
echo 1. Activez l'environnement Conda:
echo    conda activate %ENV_NAME%
echo.
echo 2. Exécutez l'installateur Vitis AI:
echo    REM Suivez les instructions de l'installateur
echo.
echo 3. Vérifiez l'installation:
echo    python -c "import onnxruntime as ort; print(ort.get_available_providers())"
echo    REM Devrait afficher 'VitisAIExecutionProvider'

REM 7. Configuration permanente du PATH (optionnel)
echo.
echo ==========================================
echo CONFIGURATION PERMANENTE (Optionnel)
echo ==========================================
echo.
echo Pour une configuration permanente, ajoutez au PATH système:
echo 1. Ouvrez "Paramètres système avancés"
echo 2. Cliquez sur "Variables d'environnement"
echo 3. Ajoutez à PATH: C:\ProgramData\Anaconda3\Scripts
echo 4. Ajoutez à PATH: C:\ProgramData\Anaconda3

echo.
echo SUCCESS: Configuration terminée!
echo Redémarrez l'invite de commandes pour que les changements prennent effet.
pause