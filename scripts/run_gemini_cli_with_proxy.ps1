# Script simplifié pour exécuter gemini-cli avec le proxy configuré
# Usage: .\scripts\run_gemini_cli_with_proxy.ps1 "votre commande"

param(
    [Parameter(Mandatory=$false)]
    [string]$Command = "Lis le fichier README.md"
)

# Configuration du proxy
$env:HTTP_PROXY = "http://localhost:8080"
$env:HTTPS_PROXY = "http://localhost:8080"

# Télécharger le certificat mitmproxy si nécessaire
$certPath = Join-Path $env:TEMP "mitmproxy-ca-cert.pem"
if (-not (Test-Path $certPath)) {
    Write-Host "Telechargement du certificat mitmproxy..." -ForegroundColor Yellow
    try {
        # Essayer via le proxy local
        Invoke-WebRequest -Uri "http://127.0.0.1:8080/cert/pem" -OutFile $certPath -ErrorAction Stop
        Write-Host "[OK] Certificat telecharge: $certPath" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Impossible de telecharger le certificat automatiquement" -ForegroundColor Yellow
        Write-Host "       Le certificat sera configure si disponible" -ForegroundColor Yellow
    }
}

# Configurer Node.js pour utiliser le certificat
if (Test-Path $certPath) {
    $env:NODE_EXTRA_CA_CERTS = $certPath
    Write-Host "[OK] Certificat SSL configure pour Node.js" -ForegroundColor Green
} else {
    # Essayer de trouver le certificat dans le dossier mitmproxy
    $mitmCertPath = Join-Path $env:USERPROFILE ".mitmproxy\mitmproxy-ca-cert.pem"
    if (Test-Path $mitmCertPath) {
        $env:NODE_EXTRA_CA_CERTS = $mitmCertPath
        Write-Host "[OK] Certificat trouve dans .mitmproxy" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Certificat mitmproxy non trouve" -ForegroundColor Yellow
        Write-Host "       Les requetes HTTPS peuvent echouer" -ForegroundColor Yellow
        Write-Host "       Installez le certificat: .\scripts\install_mitmproxy_cert.ps1" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  HTTP_PROXY=$env:HTTP_PROXY" -ForegroundColor White
Write-Host "  HTTPS_PROXY=$env:HTTPS_PROXY" -ForegroundColor White
if ($env:NODE_EXTRA_CA_CERTS) {
    Write-Host "  NODE_EXTRA_CA_CERTS=$env:NODE_EXTRA_CA_CERTS" -ForegroundColor White
}
Write-Host ""

# Exécuter gemini-cli via npx
Write-Host "Execution de gemini-cli..." -ForegroundColor Cyan
Write-Host "Commande: $Command" -ForegroundColor White
Write-Host ""

try {
    npx @google/gemini-cli $Command
} catch {
    Write-Host ""
    Write-Host "[ERREUR] $_" -ForegroundColor Red
    exit 1
}
