# Script pour trouver gemini-cli et l'exécuter avec le proxy configuré
# Usage: .\scripts\find_and_run_gemini_cli.ps1 "votre commande"

param(
    [Parameter(Mandatory=$false)]
    [string]$Command = "Lis le fichier README.md"
)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "RECHERCHE ET EXECUTION GEMINI-CLI AVEC PROXY" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Configurer le proxy
Write-Host "1. Configuration du proxy..." -ForegroundColor Yellow
$env:HTTP_PROXY = "http://localhost:8080"
$env:HTTPS_PROXY = "http://localhost:8080"
Write-Host "   [OK] HTTP_PROXY=$env:HTTP_PROXY" -ForegroundColor Green
Write-Host "   [OK] HTTPS_PROXY=$env:HTTPS_PROXY" -ForegroundColor Green
Write-Host ""

# 2. Chercher gemini-cli
Write-Host "2. Recherche de gemini-cli..." -ForegroundColor Yellow

$geminiCliPaths = @()

# Méthode 1: Vérifier dans le PATH
$geminiCli = Get-Command "gemini-cli" -ErrorAction SilentlyContinue
if ($geminiCli) {
    $geminiCliPaths += $geminiCli.Source
    Write-Host "   [OK] Trouve dans PATH: $($geminiCli.Source)" -ForegroundColor Green
}

# Méthode 2: Chercher dans les emplacements communs
$commonPaths = @(
    "$env:LOCALAPPDATA\Programs\gemini-cli\gemini-cli.exe",
    "$env:ProgramFiles\gemini-cli\gemini-cli.exe",
    "$env:USERPROFILE\.gemini\bin\gemini-cli.exe",
    "$env:USERPROFILE\AppData\Local\gemini-cli\gemini-cli.exe",
    "$env:USERPROFILE\AppData\Roaming\npm\gemini-cli.cmd",
    "$env:USERPROFILE\AppData\Local\npm\gemini-cli.cmd",
    "$env:APPDATA\npm\gemini-cli.cmd"
)

foreach ($path in $commonPaths) {
    if (Test-Path $path) {
        $geminiCliPaths += $path
        Write-Host "   [OK] Trouve: $path" -ForegroundColor Green
    }
}

# Méthode 3: Chercher via npm/npx
Write-Host "   Recherche via npm..." -ForegroundColor Gray
try {
    $npmList = npm list -g @google/gemini-cli 2>&1
    if ($LASTEXITCODE -eq 0) {
        $npmPath = Get-Command "npx" -ErrorAction SilentlyContinue
        if ($npmPath) {
            $geminiCliPaths += "npx @google/gemini-cli"
            Write-Host "   [OK] Trouve via npm: npx @google/gemini-cli" -ForegroundColor Green
        }
    }
} catch {
    # Ignorer les erreurs npm
}

# Méthode 4: Chercher récursivement dans certains dossiers
Write-Host "   Recherche recursive dans les dossiers communs..." -ForegroundColor Gray
$searchDirs = @(
    "$env:LOCALAPPDATA\Programs",
    "$env:ProgramFiles",
    "$env:USERPROFILE\.gemini"
)

foreach ($dir in $searchDirs) {
    if (Test-Path $dir) {
        try {
            $found = Get-ChildItem -Path $dir -Filter "gemini-cli*" -Recurse -ErrorAction SilentlyContinue | 
                     Where-Object { $_.Name -like "*gemini-cli*" -and ($_.Extension -eq ".exe" -or $_.Extension -eq ".cmd" -or $_.Extension -eq "") } |
                     Select-Object -First 1
            if ($found) {
                $geminiCliPaths += $found.FullName
                Write-Host "   [OK] Trouve: $($found.FullName)" -ForegroundColor Green
            }
        } catch {
            # Ignorer les erreurs de recherche
        }
    }
}

Write-Host ""

# 3. Sélectionner gemini-cli
if ($geminiCliPaths.Count -eq 0) {
    Write-Host "   [ERREUR] gemini-cli n'a pas ete trouve" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Solutions:" -ForegroundColor Yellow
    Write-Host "   1. Installer gemini-cli: npm install -g @google/gemini-cli" -ForegroundColor White
    Write-Host "   2. Ou fournir le chemin complet manuellement" -ForegroundColor White
    Write-Host ""
    $manualPath = Read-Host "   Entrez le chemin complet vers gemini-cli (ou appuyez sur Entree pour quitter)"
    if ([string]::IsNullOrWhiteSpace($manualPath)) {
        exit 1
    }
    if (Test-Path $manualPath) {
        $geminiCliPaths = @($manualPath)
    } else {
        Write-Host "   [ERREUR] Le chemin fourni n'existe pas: $manualPath" -ForegroundColor Red
        exit 1
    }
}

# Utiliser le premier chemin trouvé
$geminiCliPath = $geminiCliPaths[0]
Write-Host "3. Utilisation de: $geminiCliPath" -ForegroundColor Yellow
Write-Host ""

# 4. Vérifier que mitmproxy est démarré
Write-Host "4. Verification de mitmproxy..." -ForegroundColor Yellow
$mitmproxyRunning = Get-Process -Name "mitmdump" -ErrorAction SilentlyContinue
if (-not $mitmproxyRunning) {
    Write-Host "   [WARN] mitmproxy ne semble pas etre en cours d'execution" -ForegroundColor Yellow
    Write-Host "   Demarrez-le avec: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "   Continuer quand meme? (O/N)"
    if ($continue -ne "O" -and $continue -ne "o") {
        exit 1
    }
} else {
    Write-Host "   [OK] mitmproxy est en cours d'execution" -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "EXECUTION DE GEMINI-CLI" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commande: $Command" -ForegroundColor White
Write-Host "Proxy: $env:HTTP_PROXY" -ForegroundColor White
Write-Host ""
Write-Host "Les payloads seront captures dans logs/gemini_cli_tool_call_*.json" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# 5. Vérifier le certificat SSL
Write-Host "5. Verification du certificat SSL..." -ForegroundColor Yellow
Write-Host "   [INFO] Pour les requetes HTTPS, le certificat mitmproxy doit etre installe" -ForegroundColor Gray
Write-Host "   Si vous avez des erreurs SSL, executez: .\scripts\install_mitmproxy_cert.ps1" -ForegroundColor Gray
Write-Host ""

# 6. Exécuter gemini-cli
Write-Host "6. Execution de gemini-cli..." -ForegroundColor Yellow
Write-Host ""

try {
    if ($geminiCliPath -eq "npx @google/gemini-cli") {
        # Utiliser npx avec NODE_EXTRA_CA_CERTS pour le certificat mitmproxy
        # Télécharger le certificat mitmproxy si nécessaire
        $certPath = "$env:TEMP\mitmproxy-ca-cert.pem"
        if (-not (Test-Path $certPath)) {
            try {
                Invoke-WebRequest -Uri "http://mitm.it/cert/pem" -OutFile $certPath -ErrorAction Stop | Out-Null
            } catch {
                Write-Host "   [WARN] Impossible de telecharger le certificat mitmproxy automatiquement" -ForegroundColor Yellow
                Write-Host "   Executez: .\scripts\install_mitmproxy_cert.ps1" -ForegroundColor Yellow
            }
        }
        
        # Configurer NODE_EXTRA_CA_CERTS si le certificat existe
        if (Test-Path $certPath) {
            $env:NODE_EXTRA_CA_CERTS = $certPath
            Write-Host "   [OK] Certificat mitmproxy configure pour Node.js" -ForegroundColor Green
        }
        
        # Utiliser npx
        & npx @google/gemini-cli $Command
    } elseif ($geminiCliPath -like "*.cmd") {
        # Fichier .cmd
        & cmd /c "`"$geminiCliPath`" $Command"
    } else {
        # Exécutable direct
        & $geminiCliPath $Command
    }
} catch {
    Write-Host ""
    Write-Host "[ERREUR] Erreur lors de l'execution: $_" -ForegroundColor Red
    Write-Host ""
    
    if ($_.Exception.Message -like "*certificate*" -or $_.Exception.Message -like "*SSL*" -or $_.Exception.Message -like "*unable to verify*") {
        Write-Host "[INFO] Erreur SSL detectee. Solutions:" -ForegroundColor Yellow
        Write-Host "   1. Installer le certificat mitmproxy:" -ForegroundColor White
        Write-Host "      .\scripts\install_mitmproxy_cert.ps1" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "   2. OU utiliser Node.js avec --use-system-ca:" -ForegroundColor White
        Write-Host "      `$env:NODE_OPTIONS='--use-system-ca'" -ForegroundColor Cyan
        Write-Host "      npx @google/gemini-cli `"$Command`"" -ForegroundColor Cyan
    } else {
        Write-Host "Essayez d'executer manuellement:" -ForegroundColor Yellow
        Write-Host "  `$env:HTTP_PROXY='http://localhost:8080'" -ForegroundColor White
        Write-Host "  `$env:HTTPS_PROXY='http://localhost:8080'" -ForegroundColor White
        Write-Host "  & '$geminiCliPath' '$Command'" -ForegroundColor White
    }
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Execution terminee. Verifiez les logs dans logs/gemini_cli_tool_call_*.json" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
