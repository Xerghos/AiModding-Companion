# enable_ryzen_ai.ps1
# Script pour reactiver l'environnement Ryzen AI

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  MODE AI - Reactivation Ryzen AI" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. PATH
if ($env:ORIGINAL_PATH) {
    [Environment]::SetEnvironmentVariable("PATH", $env:ORIGINAL_PATH, "User")
    $env:PATH = $env:ORIGINAL_PATH
    Write-Host "PATH original restaure" -ForegroundColor Green
} else {
    # Reconstruction manuelle si pas de sauvegarde
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    $u = $env:USERNAME
    
    # Construction des chemins sans interpolation complexe
    $p1 = "C:\ProgramData\Anaconda3\Scripts"
    $p2 = "C:\ProgramData\Anaconda3"
    $p3 = "C:\Users\" + $u + "\Anaconda3\Scripts"
    $p4 = "C:\Users\" + $u + "\Anaconda3"
    
    $pathsToAdd = @($p1, $p2, $p3, $p4)
    
    foreach ($p in $pathsToAdd) {
        $exists = Test-Path $p
        if ($exists) {
            # Verification simple si present
            if ($currentPath.IndexOf($p) -eq -1) {
                $currentPath = $p + ";" + $currentPath
            }
        }
    }
    
    [Environment]::SetEnvironmentVariable("PATH", $currentPath, "User")
    $env:PATH = $currentPath
    Write-Host "Conda ajoute au PATH" -ForegroundColor Green
}

# 2. Services AMD
$services = @("AMD External Events Utility", "AMD Crash Defender Service")

foreach ($s in $services) {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne "Running") {
        Start-Service -Name $s -ErrorAction SilentlyContinue
        Write-Host ("Service redemarre: " + $s) -ForegroundColor Green
    }
}

# 3. Taches
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue
if ($tasks) {
    foreach ($t in $tasks) {
        $tn = $t.TaskName
        if (($tn -like "*AMD*") -or ($tn -like "*Ryzen*")) {
             if ($t.State -eq "Disabled") {
                Enable-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue | Out-Null
                Write-Host ("Tache reactivee: " + $tn) -ForegroundColor Green
             }
        }
    }
}

# 4. Verification Conda
Write-Host ""
Write-Host "Verification environnement Ryzen AI..." -ForegroundColor Cyan

$condaWorks = $false
try {
    conda --version | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $condaWorks = $true
        Write-Host "Conda fonctionnel" -ForegroundColor Green
    } else {
        Write-Host "Conda non fonctionnel (Code erreur)" -ForegroundColor Red
    }
} catch {
    Write-Host "Conda non disponible" -ForegroundColor Red
}

# 5. Test ONNX
if ($condaWorks) {
    Write-Host ""
    Write-Host "Test ONNX Runtime..." -ForegroundColor Cyan
    
    $code = "import sys; import onnxruntime as ort; print('OK');"
    # Version simplifiee sur une ligne pour eviter les problemes de Here-String
    
    try {
        # Test basique d'import sans script complexe
        conda run -n ryzen-ai-1.6.1 python -c "import onnxruntime; print('ONNX OK')" 2>&1 | Out-String -Stream | Select-String "ONNX OK" | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ONNX Runtime fonctionnel" -ForegroundColor Green
        } else {
            Write-Host "ONNX Runtime non charge (Verifier env ryzen-ai-1.6.1)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Test ONNX echoue" -ForegroundColor Red
    }
}

# 6. Fin
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "MODE AI ACTIVE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Votre environnement est pret." -ForegroundColor White
Write-Host "Appuyez sur Entree pour quitter..." -ForegroundColor Gray
Read-Host