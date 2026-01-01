# Guide de Démarrage Rapide - Capture Payloads Gemini-CLI

## 🔍 Diagnostic Effectué

Le diagnostic a révélé les problèmes suivants :
- ❌ mitmproxy n'est pas en cours d'exécution
- ❌ Variables d'environnement HTTP_PROXY/HTTPS_PROXY non définies
- ❌ gemini-cli non trouvé dans le PATH

## 🚀 Solution Rapide (Windows)

### Étape 1 : Démarrer le proxy

**Option A : Script automatique**
```bash
scripts\START_CAPTURE.bat
```

**Option B : Manuel**
```bash
mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
```

Le proxy démarre sur le port **8080** par défaut.

### Étape 2 : Installer le certificat mitmproxy (pour HTTPS)

1. Ouvrir http://mitm.it dans votre navigateur
2. Télécharger le certificat pour Windows
3. Double-cliquer sur le fichier téléchargé
4. Cliquer sur "Installer le certificat"
5. Sélectionner "Ordinateur local" → Suivant
6. Sélectionner "Placer tous les certificats dans le magasin suivant"
7. Cliquer sur "Parcourir" → Sélectionner "Autorités de certification racines de confiance" → OK
8. Terminer l'installation

### Étape 3 : Configurer gemini-cli dans un NOUVEAU terminal

**⚠️ IMPORTANT : Ouvrir un NOUVEAU terminal PowerShell/CMD**

```powershell
# Définir les variables d'environnement
$env:HTTP_PROXY="http://localhost:8080"
$env:HTTPS_PROXY="http://localhost:8080"

# Vérifier que gemini-cli est accessible
gemini-cli --version

# Si gemini-cli n'est pas trouvé, utiliser le chemin complet
# Exemple: & "C:\Users\VotreUser\AppData\Local\Programs\gemini-cli\gemini-cli.exe" --version
```

### Étape 4 : Exécuter une commande avec tool call

Dans le **MÊME terminal** où les variables sont définies :

```powershell
gemini-cli "Lis le fichier README.md et résume-le"
```

### Étape 5 : Vérifier les logs

Les payloads seront sauvegardés dans `logs/gemini_cli_tool_call_*.json`

Vérifier avec :
```powershell
ls logs/gemini_cli_tool_call_*.json
```

## 🔧 Dépannage

### Le proxy ne capture rien

1. **Vérifier que mitmproxy est démarré** :
   ```powershell
   tasklist | findstr mitmdump
   ```

2. **Vérifier les variables d'environnement** :
   ```powershell
   echo $env:HTTP_PROXY
   echo $env:HTTPS_PROXY
   ```

3. **Vérifier que gemini-cli utilise le proxy** :
   - Regardez les logs de mitmproxy - vous devriez voir des requêtes
   - Si aucune requête n'apparaît, gemini-cli n'utilise pas le proxy

4. **Tester avec une requête simple** :
   ```powershell
   gemini-cli "Hello"
   ```
   Même sans tool call, vous devriez voir une requête dans les logs de mitmproxy

### Erreur de certificat SSL

Si vous voyez des erreurs SSL/TLS :
1. Vérifiez que le certificat mitmproxy est bien installé
2. Redémarrez gemini-cli après l'installation du certificat
3. Sur Windows, assurez-vous que le certificat est dans "Autorités de certification racines"

### gemini-cli non trouvé

Si `gemini-cli` n'est pas dans le PATH :
1. Trouver où il est installé :
   ```powershell
   Get-Command gemini-cli -ErrorAction SilentlyContinue
   ```

2. Utiliser le chemin complet :
   ```powershell
   & "C:\chemin\vers\gemini-cli.exe" "votre commande"
   ```

3. Ou ajouter au PATH :
   ```powershell
   $env:PATH += ";C:\chemin\vers\gemini-cli"
   ```

## 📊 Vérification

Après avoir exécuté une commande, vérifiez :

1. **Les logs de mitmproxy** - Vous devriez voir :
   ```
   [TOOL_CALL] TOOL CALL DÉTECTÉ
   [TOOL_CALL] Payload sauvegardé: gemini_cli_tool_call_*.json
   ```

2. **Les fichiers dans logs/** :
   ```powershell
   ls logs/gemini_cli_tool_call_*.json
   ```

3. **Analyser les payloads** :
   ```powershell
   python scripts/analyze_gemini_cli_tool_payloads.py --compare --detailed
   ```

## 💡 Astuces

1. **Garder deux terminaux ouverts** :
   - Terminal 1 : mitmproxy (pour voir les logs en temps réel)
   - Terminal 2 : gemini-cli (avec les variables d'environnement)

2. **Vérifier les logs de mitmproxy** :
   - Toutes les requêtes sont loggées, même celles qui ne sont pas des tool calls
   - Cherchez les lignes avec `[TOOL_CALL]` pour les tool calls

3. **Tester progressivement** :
   - D'abord une commande simple sans tool call
   - Puis une commande avec tool call
   - Vérifiez à chaque étape que les requêtes sont capturées

## 🆘 Aide Supplémentaire

Si le problème persiste :

1. Exécutez le diagnostic :
   ```powershell
   python scripts/diagnose_capture_issue.py
   ```

2. Vérifiez la documentation complète :
   ```powershell
   cat scripts/README_capture_payloads.md
   ```

3. Vérifiez les logs de mitmproxy pour voir toutes les requêtes interceptées
