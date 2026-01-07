# Script de configuration de l'environnement pour Vitis AI avec Conda
# Ce script résout le problème "conda n'est pas reconnu"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Configuration de l'environnement Vitis AI" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Vérifier et configurer le PATH de Conda
$condaPaths = @(
    "C:\ProgramData\Anaconda3\Scripts",
    "C:\ProgramData\Anaconda3",
    "C:\Users\$env:USERNAME\Anaconda3\Scripts",
    "C:\Users\$env:USERNAME\Anaconda3",
    "C:\ProgramData\Miniconda3\Scripts",
    "C:\ProgramData\Miniconda3",
    "C:\Users\$env:USERNAME\Miniconda3\Scripts",
    "C:\Users\$env:USERNAME\Miniconda3"
)

$condaFound = $false
foreach ($path in $condaPaths) {
    if (Test-Path $path) {
        Write-Host "✓ Conda trouvé à: $path" -ForegroundColor Green
        $env:PATH = "$path;$env:PATH"
        $condaFound = $true
        break
    }
}

if (-not $condaFound) {
    Write-Host "❌ Conda non trouvé. Installation requise." -ForegroundColor Red
    Write-Host "Téléchargez Miniconda depuis: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    exit 1
}

# 2. Vérifier la version de Conda
Write-Host "`nVérification de la version Conda..." -ForegroundColor Yellow
try {
    $condaVersion = conda --version
    Write-Host "✓ Conda version: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Erreur avec conda --version: $_" -ForegroundColor Red
    exit 1
}

# 3. Initialiser Conda pour PowerShell
Write-Host "`nInitialisation de Conda pour PowerShell..." -ForegroundColor Yellow
try {
    # Essayer d'initialiser Conda
    conda init powershell
    Write-Host "✓ Conda initialisé pour PowerShell" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Impossible d'initialiser Conda automatiquement" -ForegroundColor Yellow
    Write-Host "Vous devrez peut-être redémarrer PowerShell après installation" -ForegroundColor Yellow
}

# 4. Vérifier les environnements Conda existants
Write-Host "`nListe des environnements Conda disponibles..." -ForegroundColor Yellow
try {
    conda env list
} catch {
    Write-Host "❌ Erreur lors de la liste des environnements: $_" -ForegroundColor Red
}

# 5. Créer un environnement pour Vitis AI (optionnel)
Write-Host "`nCréation d'un environnement pour Vitis AI..." -ForegroundColor Yellow
$envName = "vitis-ai"
try {
    # Vérifier si l'environnement existe déjà
    $envExists = conda env list | Select-String $envName
    if ($envExists) {
        Write-Host "✓ Environnement '$envName' existe déjà" -ForegroundColor Green
    } else {
        Write-Host "Création de l'environnement '$envName' avec Python 3.9..." -ForegroundColor Yellow
        conda create -n $envName python=3.9 -y
        Write-Host "✓ Environnement '$envName' créé" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  Erreur lors de la création de l'environnement: $_" -ForegroundColor Yellow
}

# 6. Instructions pour l'installateur Vitis AI
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "INSTRUCTIONS POUR VITIS AI" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "`nMaintenant, vous pouvez exécuter l'installateur Vitis AI:" -ForegroundColor Green
Write-Host "1. Activez l'environnement Conda:" -ForegroundColor White
Write-Host "   conda activate $envName" -ForegroundColor Gray
Write-Host "`n2. Exécutez l'installateur Vitis AI:" -ForegroundColor White
Write-Host "   # Suivez les instructions de l'installateur" -ForegroundColor Gray
Write-Host "`n3. Vérifiez l'installation:" -ForegroundColor White
Write-Host "   python -c `"import onnxruntime as ort; print(ort.get_available_providers())`"" -ForegroundColor Gray
Write-Host "   # Devrait afficher 'VitisAIExecutionProvider'" -ForegroundColor Gray

# 7. Configuration permanente du PATH (optionnel)
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "CONFIGURATION PERMANENTE (Optionnel)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "`nPour une configuration permanente, ajoutez à votre profile PowerShell:" -ForegroundColor Yellow
Write-Host "`n# Ajoutez ces lignes à: $PROFILE" -ForegroundColor White
Write-Host '$condaPath = "C:\ProgramData\Anaconda3\Scripts"' -ForegroundColor Gray
Write-Host 'if (Test-Path $condaPath) {' -ForegroundColor Gray
Write-Host '    $env:PATH = "$condaPath;$env:PATH"' -ForegroundColor Gray
Write-Host '    conda init powershell' -ForegroundColor Gray
Write-Host '}' -ForegroundColor Gray

Write-Host "`n✅ Configuration terminée!" -ForegroundColor Green
Write-Host "Redémarrez PowerShell pour que les changements prennent effet complètement." -ForegroundColor Yellow