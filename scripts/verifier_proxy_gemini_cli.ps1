# Script PowerShell pour vérifier et configurer le proxy pour gemini-cli
# Usage: .\scripts\verifier_proxy_gemini_cli.ps1

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "VERIFICATION ET CONFIGURATION PROXY POUR GEMINI-CLI" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier si mitmproxy est en cours d'exécution
Write-Host "1. Verification si mitmproxy est en cours d'execution..." -ForegroundColor Yellow
$mitmproxyRunning = Get-Process -Name "mitmdump" -ErrorAction SilentlyContinue
if ($mitmproxyRunning) {
    Write-Host "   [OK] mitmproxy est en cours d'execution" -ForegroundColor Green
} else {
    Write-Host "   [ERREUR] mitmproxy n'est PAS en cours d'execution" -ForegroundColor Red
    Write-Host "      Demarrez-le avec: mitmdump -s scripts/capture_gemini_cli_mitmproxy.py" -ForegroundColor Yellow
    Write-Host ""
    $start = Read-Host "Voulez-vous demarrer mitmproxy maintenant? (O/N)"
    if ($start -eq "O" -or $start -eq "o") {
        Write-Host "   Demarrage de mitmproxy..." -ForegroundColor Yellow
        Start-Process -NoNewWindow -FilePath "mitmdump" -ArgumentList "-s", "scripts/capture_gemini_cli_mitmproxy.py"
        Start-Sleep -Seconds 2
        Write-Host "   [OK] mitmproxy demarre" -ForegroundColor Green
    }
}

Write-Host ""

# Vérifier les variables d'environnement
Write-Host "2. Verification des variables d'environnement..." -ForegroundColor Yellow
$http_proxy = $env:HTTP_PROXY
$https_proxy = $env:HTTPS_PROXY

if ($http_proxy) {
    Write-Host "   [OK] HTTP_PROXY=$http_proxy" -ForegroundColor Green
} else {
    Write-Host "   [ERREUR] HTTP_PROXY n'est pas defini" -ForegroundColor Red
}

if ($https_proxy) {
    Write-Host "   [OK] HTTPS_PROXY=$https_proxy" -ForegroundColor Green
} else {
    Write-Host "   [ERREUR] HTTPS_PROXY n'est pas defini" -ForegroundColor Red
}

if (-not $http_proxy -or -not $https_proxy) {
    Write-Host ""
    Write-Host "   Configuration des variables d'environnement..." -ForegroundColor Yellow
    $env:HTTP_PROXY = "http://localhost:8080"
    $env:HTTPS_PROXY = "http://localhost:8080"
    Write-Host "   [OK] Variables configurees pour cette session:" -ForegroundColor Green
    Write-Host "      HTTP_PROXY=$env:HTTP_PROXY" -ForegroundColor Green
    Write-Host "      HTTPS_PROXY=$env:HTTPS_PROXY" -ForegroundColor Green
    Write-Host ""
    Write-Host "   [IMPORTANT] Ces variables sont valides uniquement pour cette session PowerShell" -ForegroundColor Yellow
    Write-Host "   Vous devez executer gemini-cli dans CE TERMINAL pour qu'il utilise le proxy" -ForegroundColor Yellow
}

Write-Host ""

# Tester le proxy
Write-Host "3. Test du proxy..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://httpbin.org/ip" -Proxy $env:HTTP_PROXY -TimeoutSec 5 -ErrorAction Stop
    $ip = ($response.Content | ConvertFrom-Json).origin
    Write-Host "   [OK] Proxy fonctionne - IP: $ip" -ForegroundColor Green
} catch {
    Write-Host "   [ERREUR] Le proxy ne fonctionne pas: $_" -ForegroundColor Red
    Write-Host "      Verifiez que mitmproxy est demarre" -ForegroundColor Yellow
}

Write-Host ""

# Vérifier gemini-cli
Write-Host "4. Verification de gemini-cli..." -ForegroundColor Yellow
$geminiCli = Get-Command "gemini-cli" -ErrorAction SilentlyContinue
if ($geminiCli) {
    Write-Host "   [OK] gemini-cli trouve: $($geminiCli.Source)" -ForegroundColor Green
    try {
        $version = & gemini-cli --version 2>&1
        Write-Host "   [OK] Version: $version" -ForegroundColor Green
    } catch {
        Write-Host "   [WARN] Impossible d'obtenir la version" -ForegroundColor Yellow
    }
} else {
    Write-Host "   [ERREUR] gemini-cli n'est pas trouve dans le PATH" -ForegroundColor Red
    Write-Host "      Verifiez qu'il est installe et accessible" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "INSTRUCTIONS" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pour capturer les payloads:" -ForegroundColor Yellow
Write-Host "1. Les variables d'environnement sont configurees dans CE terminal" -ForegroundColor White
Write-Host "2. Executez gemini-cli dans CE MEME terminal:" -ForegroundColor White
Write-Host "   gemini-cli `"Lis le fichier README.md`"" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Les payloads seront sauvegardes dans logs/gemini_cli_tool_call_*.json" -ForegroundColor White
Write-Host ""
Write-Host "4. Verifiez les logs de mitmproxy pour voir les requetes interceptees" -ForegroundColor White
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
