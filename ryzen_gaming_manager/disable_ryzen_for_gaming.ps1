# disable_ryzen_for_gaming.ps1
# Script pour desactiver l'environnement Ryzen AI

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  MODE GAMING - Desactivation Ryzen AI" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. PATH
$originalPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$env:ORIGINAL_PATH = $originalPath
Write-Host "PATH original sauvegarde" -ForegroundColor Green

# 2. Conda
$u = $env:USERNAME
$newPath = $originalPath

# Utilisation de .Replace() (méthode string) au lieu de -replace (opérateur regex) pour éviter les erreurs
$newPath = $newPath.Replace('C:\ProgramData\Anaconda3\Scripts;', '').Replace('C:\ProgramData\Anaconda3\Scripts', '')
$newPath = $newPath.Replace('C:\ProgramData\Anaconda3;', '').Replace('C:\ProgramData\Anaconda3', '')

$userCondaScripts = "C:\Users\$u\Anaconda3\Scripts"
$userCondaRoot = "C:\Users\$u\Anaconda3"

# Suppression avec et sans point-virgule final
$newPath = $newPath.Replace("$userCondaScripts;", '').Replace($userCondaScripts, '')
$newPath = $newPath.Replace("$userCondaRoot;", '').Replace($userCondaRoot, '')

# Nettoyage des doubles points-virgules éventuels
$newPath = $newPath.Replace(';;', ';')

[Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
$env:PATH = $newPath
Write-Host "Conda retire du PATH" -ForegroundColor Green

# 3. Services AMD
$services = @("AMD External Events Utility", "AMD Crash Defender Service", "AMD User Experience Program", "AMD Log Utility")

foreach ($s in $services) {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") {
        Stop-Service -Name $s -Force -ErrorAction SilentlyContinue
        Write-Host ("Service arrete: " + $s) -ForegroundColor Yellow
    }
}

# 4. Processus
$pNames = @("python", "conda", "jupyter", "onnxruntime", "vitis")

foreach ($name in $pNames) {
    $list = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($list) {
        foreach ($p in $list) {
            $path = $p.Path
            # Check simple sans regex complexe
            $match = $false
            if ($path -like "*ryzen*") { $match = $true }
            if ($path -like "*anaconda*") { $match = $true }
            if ($path -like "*vitis*") { $match = $true }

            if ($match) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                Write-Host ("Processus arrete: " + $p.ProcessName) -ForegroundColor Yellow
            }
        }
    }
}

# 5. Taches
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue
if ($tasks) {
    foreach ($t in $tasks) {
        $tn = $t.TaskName
        if (($tn -like "*AMD*") -or ($tn -like "*Ryzen*")) {
             if ($t.State -eq "Ready") {
                Disable-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue | Out-Null
                Write-Host ("Tache desactivee: " + $tn) -ForegroundColor Yellow
             }
        }
    }
}

# 6. GPU
try {
    $gpus = Get-WmiObject Win32_VideoController
    if ($gpus) {
        Write-Host ""
        Write-Host "ETAT GPU:" -ForegroundColor Cyan
        foreach ($g in $gpus) {
            $n = $g.Name
            Write-Host ("  - " + $n) -ForegroundColor White
        }
    }
} catch {
    # Ignorer
}

# 7. Memoire
Write-Host ""
Write-Host "Nettoyage memoire..." -ForegroundColor Cyan
Clear-RecycleBin -Force -ErrorAction SilentlyContinue
Write-Host "Corbeille videe" -ForegroundColor Green

# 8. Fin
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "MODE GAMING ACTIVE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Votre environnement est optimise." -ForegroundColor White
Write-Host "Appuyez sur Entree pour quitter..." -ForegroundColor Gray
Read-Host
