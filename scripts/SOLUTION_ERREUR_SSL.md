# Solution : Erreur SSL "unable to verify the first certificate"

## 🔍 Problème

L'erreur `unable to verify the first certificate` signifie que Node.js (utilisé par gemini-cli via npx) ne fait pas confiance au certificat mitmproxy pour les requêtes HTTPS.

## ✅ Solutions

### Solution 1 : Installer le Certificat mitmproxy (Recommandé)

**Script automatique :**
```powershell
.\scripts\install_mitmproxy_cert.ps1
```

Ce script va :
1. Télécharger le certificat mitmproxy depuis http://mitm.it
2. L'installer dans "Autorités de certification racines de confiance" Windows
3. Rendre le certificat valide pour toutes les applications Windows

**Installation manuelle :**
1. Ouvrir http://mitm.it dans votre navigateur
2. Télécharger le certificat pour Windows
3. Double-cliquer sur le fichier téléchargé
4. Cliquer sur "Installer le certificat"
5. Sélectionner "Ordinateur local" → Suivant
6. Sélectionner "Placer tous les certificats dans le magasin suivant"
7. Cliquer sur "Parcourir" → Sélectionner "Autorités de certification racines de confiance" → OK
8. Terminer l'installation

### Solution 2 : Utiliser NODE_EXTRA_CA_CERTS

Si l'installation système ne fonctionne pas, configurez Node.js pour utiliser le certificat :

```powershell
# Télécharger le certificat
Invoke-WebRequest -Uri "http://mitm.it/cert/pem" -OutFile "$env:TEMP\mitmproxy-ca-cert.pem"

# Configurer Node.js
$env:NODE_EXTRA_CA_CERTS = "$env:TEMP\mitmproxy-ca-cert.pem"
$env:HTTP_PROXY = "http://localhost:8080"
$env:HTTPS_PROXY = "http://localhost:8080"

# Exécuter gemini-cli
npx @google/gemini-cli "votre commande"
```

### Solution 3 : Utiliser --use-system-ca

Forcer Node.js à utiliser les certificats système :

```powershell
$env:NODE_OPTIONS = "--use-system-ca"
$env:HTTP_PROXY = "http://localhost:8080"
$env:HTTPS_PROXY = "http://localhost:8080"

npx @google/gemini-cli "votre commande"
```

⚠️ **Note** : Cette option nécessite que le certificat soit installé dans le magasin système (Solution 1).

### Solution 4 : Désactiver la Vérification SSL (Non Recommandé - Dernier Recours)

**⚠️ ATTENTION** : Cela désactive la vérification SSL pour toutes les requêtes Node.js. Utilisez uniquement pour le développement.

```powershell
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
$env:HTTP_PROXY = "http://localhost:8080"
$env:HTTPS_PROXY = "http://localhost:8080"

npx @google/gemini-cli "votre commande"
```

## 🔧 Script Amélioré

Le script `find_and_run_gemini_cli.ps1` a été amélioré pour :
- Télécharger automatiquement le certificat mitmproxy
- Configurer `NODE_EXTRA_CA_CERTS` automatiquement
- Gérer les erreurs SSL avec des messages clairs

**Utilisation :**
```powershell
.\scripts\find_and_run_gemini_cli.ps1 "Lis le fichier README.md"
```

## 📋 Checklist

- [ ] Le certificat mitmproxy est installé (Solution 1)
- [ ] Les variables HTTP_PROXY/HTTPS_PROXY sont définies
- [ ] gemini-cli est exécuté dans le MÊME terminal
- [ ] Les logs de mitmproxy montrent des requêtes
- [ ] Pas d'erreur SSL dans les logs

## 💡 Ordre Recommandé

1. **D'abord** : Installer le certificat mitmproxy (Solution 1)
2. **Ensuite** : Utiliser le script `find_and_run_gemini_cli.ps1`
3. **Si ça ne marche toujours pas** : Utiliser NODE_EXTRA_CA_CERTS (Solution 2)
4. **Dernier recours** : Désactiver la vérification SSL (Solution 4) - **UNIQUEMENT pour le développement**

## 🧪 Test

Après avoir installé le certificat, testez :

```powershell
# Tester la connexion HTTPS via le proxy
python scripts/test_proxy_mitmproxy.py
```

Si le test fonctionne, gemini-cli devrait aussi fonctionner.
