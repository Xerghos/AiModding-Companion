# Instructions : gemini-cli Non Trouvé dans le PATH

## 🔍 Problème

gemini-cli n'est pas dans le PATH, mais le proxy fonctionne correctement.

## ✅ Solutions

### Solution 1 : Utiliser le Script Automatique (Recommandé)

Le script `find_and_run_gemini_cli.ps1` va :
1. Chercher gemini-cli dans tous les emplacements possibles
2. Configurer automatiquement le proxy
3. Exécuter gemini-cli avec votre commande

**Usage :**
```powershell
.\scripts\find_and_run_gemini_cli.ps1 "Lis le fichier README.md"
```

### Solution 2 : Trouver gemini-cli Manuellement

**Méthode A : Via npm**
```powershell
# Si installé via npm
npx @google/gemini-cli "votre commande"
```

**Méthode B : Chercher dans les dossiers communs**
```powershell
# Chercher gemini-cli
Get-ChildItem -Path "$env:LOCALAPPDATA\Programs" -Filter "gemini-cli*" -Recurse -ErrorAction SilentlyContinue
Get-ChildItem -Path "$env:USERPROFILE\.gemini" -Filter "gemini-cli*" -Recurse -ErrorAction SilentlyContinue
```

**Méthode C : Vérifier où npm installe les packages globaux**
```powershell
npm config get prefix
# Chercher dans ce dossier + \node_modules\@google\gemini-cli
```

### Solution 3 : Utiliser le Chemin Complet

Une fois que vous avez trouvé gemini-cli :

```powershell
# Configurer le proxy
$env:HTTP_PROXY="http://localhost:8080"
$env:HTTPS_PROXY="http://localhost:8080"

# Exécuter avec le chemin complet
& "C:\chemin\vers\gemini-cli.exe" "votre commande"
```

### Solution 4 : Ajouter gemini-cli au PATH

Si vous trouvez où gemini-cli est installé :

```powershell
# Temporairement (pour cette session)
$env:PATH += ";C:\chemin\vers\gemini-cli"

# Permanemment (pour toutes les sessions)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\chemin\vers\gemini-cli", "User")
```

## 🧪 Test Rapide

Pour tester si gemini-cli fonctionne avec le proxy :

```powershell
# Configurer le proxy
$env:HTTP_PROXY="http://localhost:8080"
$env:HTTPS_PROXY="http://localhost:8080"

# Tester avec npx (si installé via npm)
npx @google/gemini-cli --version

# Ou avec le chemin complet si vous l'avez trouvé
& "C:\chemin\vers\gemini-cli.exe" --version
```

## 📋 Checklist

- [ ] mitmproxy est démarré
- [ ] Les variables HTTP_PROXY/HTTPS_PROXY sont définies
- [ ] gemini-cli est trouvé (via le script ou manuellement)
- [ ] gemini-cli est exécuté dans le MÊME terminal où les variables sont définies
- [ ] Les logs de mitmproxy montrent des requêtes

## 💡 Astuce

Le script `find_and_run_gemini_cli.ps1` fait tout automatiquement :
- Cherche gemini-cli
- Configure le proxy
- Exécute la commande
- Capture les payloads

Utilisez-le pour simplifier le processus !
