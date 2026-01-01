# Script pour installer le certificat mitmproxy dans le magasin de certificats Windows
# Usage: .\scripts\install_mitmproxy_cert.ps1

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "INSTALLATION DU CERTIFICAT MITMPROXY" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier si mitmproxy est en cours d'exécution
Write-Host "1. Verification si mitmproxy est en cours d'execution..." -ForegroundColor Yellow
$mitmproxyRunning = Get-Process -Name "mitmdump" -ErrorAction SilentlyContinue
if (-not $mitmproxyRunning) {
    Write-Host "   [WARN] mitmproxy n'est pas en cours d'execution" -ForegroundColor Yellow
    Write-Host "   Le certificat sera telecharge depuis http://mitm.it" -ForegroundColor Yellow
} else {
    Write-Host "   [OK] mitmproxy est en cours d'execution" -ForegroundColor Green
}

Write-Host ""

# Télécharger le certificat
Write-Host "2. Telechargement du certificat mitmproxy..." -ForegroundColor Yellow

# L'URL correcte pour le certificat mitmproxy
$certUrl = "http://mitm.it/cert/pem"
# Alternative si la première ne fonctionne pas
$certUrlAlt = "http://127.0.0.1:8080/cert/pem"
$tempCertPath = "$env:TEMP\mitmproxy-ca-cert.pem"

try {
    # Essayer d'abord avec l'URL standard
    try {
        Invoke-WebRequest -Uri $certUrl -OutFile $tempCertPath -ErrorAction Stop
        Write-Host "   [OK] Certificat telecharge: $tempCertPath" -ForegroundColor Green
    } catch {
        # Essayer avec l'URL alternative (via le proxy local)
        Write-Host "   Tentative avec URL alternative..." -ForegroundColor Gray
        try {
            Invoke-WebRequest -Uri $certUrlAlt -OutFile $tempCertPath -ErrorAction Stop
            Write-Host "   [OK] Certificat telecharge: $tempCertPath" -ForegroundColor Green
        } catch {
            throw "Impossible de telecharger depuis les deux URLs"
        }
    }
} catch {
    Write-Host "   [ERREUR] Impossible de telecharger le certificat: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Solution manuelle:" -ForegroundColor Yellow
    Write-Host "   1. Ouvrir http://mitm.it dans votre navigateur" -ForegroundColor White
    Write-Host "   2. Telecharger le certificat pour Windows" -ForegroundColor White
    Write-Host "   3. Double-cliquer sur le fichier et suivre les instructions" -ForegroundColor White
    Write-Host ""
    Write-Host "   OU utiliser le certificat depuis le dossier mitmproxy:" -ForegroundColor Yellow
    Write-Host "   Le certificat se trouve dans: ~/.mitmproxy/mitmproxy-ca-cert.pem" -ForegroundColor White
    exit 1
}

Write-Host ""

# Installer le certificat
Write-Host "3. Installation du certificat dans le magasin Windows..." -ForegroundColor Yellow

try {
    # Importer le certificat dans le magasin "Autorités de certification racines de confiance"
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($tempCertPath)
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store(
        [System.Security.Cryptography.X509Certificates.StoreName]::Root,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine
    )
    
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $store.Add($cert)
    $store.Close()
    
    Write-Host "   [OK] Certificat installe dans 'Autorites de certification racines de confiance'" -ForegroundColor Green
    Write-Host ""
    Write-Host "   [IMPORTANT] Vous devrez peut-etre redemarrer gemini-cli pour que le certificat soit pris en compte" -ForegroundColor Yellow
    
} catch {
    Write-Host "   [ERREUR] Impossible d'installer le certificat: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Solution manuelle:" -ForegroundColor Yellow
    Write-Host "   1. Ouvrir le fichier: $tempCertPath" -ForegroundColor White
    Write-Host "   2. Cliquer sur 'Installer le certificat'" -ForegroundColor White
    Write-Host "   3. Selectionner 'Ordinateur local' -> Suivant" -ForegroundColor White
    Write-Host "   4. Selectionner 'Placer tous les certificats dans le magasin suivant'" -ForegroundColor White
    Write-Host "   5. Cliquer sur 'Parcourir' -> Selectionner 'Autorites de certification racines de confiance' -> OK" -ForegroundColor White
    Write-Host "   6. Terminer l'installation" -ForegroundColor White
}

Write-Host ""

# Nettoyer
if (Test-Path $tempCertPath) {
    Remove-Item $tempCertPath -ErrorAction SilentlyContinue
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Installation terminee" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Si vous avez toujours des erreurs SSL:" -ForegroundColor Yellow
Write-Host "   1. Redemarrer gemini-cli" -ForegroundColor White
Write-Host "   2. Redemarrer mitmproxy" -ForegroundColor White
Write-Host "   3. Verifier que le certificat est bien installe dans 'Autorites de certification racines'" -ForegroundColor White
