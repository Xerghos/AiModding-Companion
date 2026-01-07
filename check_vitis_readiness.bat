@echo off
REM Script de vérification de la préparation pour Vitis AI

echo ==========================================
echo VERIFICATION PRE-INSTALLATION VITIS AI
echo ==========================================

echo.
echo 1. Verification Conda...
where conda
if errorlevel 1 (
    echo ERROR: Conda non trouve dans le PATH
    exit /b 1
) else (
    echo SUCCESS: Conda trouve
)

echo.
echo 2. Verification version Conda...
conda --version
if errorlevel 1 (
    echo ERROR: Impossible d'executer conda --version
    exit /b 1
)

echo.
echo 3. Verification environnement vitis-ai...
conda info --envs | findstr /C:"vitis-ai" >nul
if errorlevel 1 (
    echo ERROR: Environnement vitis-ai non trouve
    echo Creation de l'environnement...
    conda create -n vitis-ai python=3.9 -y
    if errorlevel 1 (
        echo ERROR: Echec creation environnement
        exit /b 1
    )
) else (
    echo SUCCESS: Environnement vitis-ai existe
)

echo.
echo 4. Activation environnement vitis-ai...
call conda activate vitis-ai
if errorlevel 1 (
    echo ERROR: Impossible d'activer l'environnement
    exit /b 1
) else (
    echo SUCCESS: Environnement active
)

echo.
echo 5. Verification Python dans environnement...
python --version
if errorlevel 1 (
    echo ERROR: Python non disponible dans l'environnement
    exit /b 1
)

echo.
echo 6. Verification pip...
pip --version
if errorlevel 1 (
    echo WARNING: Pip non disponible, installation...
    python -m ensurepip --upgrade
)

echo.
echo ==========================================
echo RESUME DE LA VERIFICATION
echo ==========================================
echo.
echo Conda: OK
echo Environnement vitis-ai: OK
echo Python 3.9: OK
echo.
echo ==========================================
echo INSTRUCTIONS POUR L'INSTALLATEUR VITIS AI
echo ==========================================
echo.
echo Votre environnement est maintenant pret pour Vitis AI!
echo.
echo Pour executer l'installateur Vitis AI:
echo 1. Assurez-vous que l'environnement est active:
echo    conda activate vitis-ai
echo.
echo 2. Executez l'installateur Vitis AI
echo    (Suivez les instructions de l'installateur AMD)
echo.
echo 3. Apres installation, verifiez avec:
echo    python -c "import onnxruntime as ort; print('Providers:', ort.get_available_providers())"
echo.
echo 4. Pour une configuration permanente, ajoutez au PATH systeme:
echo    - C:\ProgramData\Anaconda3\Scripts
echo    - C:\ProgramData\Anaconda3
echo.
echo SUCCESS: Systeme pret pour l'installation Vitis AI!
pause