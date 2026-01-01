# Résumé : Le Trafic Ne Passe Pas Par mitmproxy

## 🔍 Problème

Vous voyez "If you can see this, traffic is not going through mitmproxy" sur http://mitm.it, ce qui signifie que **gemini-cli n'utilise pas le proxy**.

## ✅ Solution Recommandée

### Méthode 1 : Script PowerShell (Le Plus Simple)

1. **Démarrer mitmproxy** dans un terminal :
   ```powershell
   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
   ```

2. **Dans un NOUVEAU terminal PowerShell**, exécuter :
   ```powershell
   .\scripts\verifier_proxy_gemini_cli.ps1
   ```
   
   Ce script va :
   - Vérifier si mitmproxy est démarré
   - Configurer automatiquement les variables HTTP_PROXY/HTTPS_PROXY
   - Tester le proxy
   - Vous donner les instructions exactes

3. **Dans le MÊME terminal PowerShell**, exécuter gemini-cli :
   ```powershell
   gemini-cli "Lis le fichier README.md"
   ```

### Méthode 2 : Configuration Manuelle

Si le script PowerShell ne fonctionne pas :

1. **Démarrer mitmproxy** :
   ```powershell
   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
   ```

2. **Dans un NOUVEAU terminal PowerShell**, définir les variables :
   ```powershell
   $env:HTTP_PROXY="http://localhost:8080"
   $env:HTTPS_PROXY="http://localhost:8080"
   
   # Vérifier :
   echo $env:HTTP_PROXY
   echo $env:HTTPS_PROXY
   ```

3. **Dans le MÊME terminal**, exécuter gemini-cli :
   ```powershell
   gemini-cli "votre commande"
   ```

### Méthode 3 : Proxy Système Windows (Si les variables ne fonctionnent pas)

1. **Paramètres Windows** → **Réseau et Internet** → **Proxy**
2. Activer "Utiliser un serveur proxy"
3. Adresse : `127.0.0.1`, Port : `8080`
4. Redémarrer gemini-cli

⚠️ **Attention** : Cela affectera toutes les applications Windows.

### Méthode 4 : Utiliser Fiddler (Alternative Plus Fiable)

Fiddler est plus facile à configurer que mitmproxy sur Windows :

1. Télécharger Fiddler : https://www.telerik.com/fiddler
2. Démarrer Fiddler
3. Tools → Options → HTTPS → Activer "Capture HTTPS CONNECTs" et "Decrypt HTTPS traffic"
4. Installer le certificat Fiddler
5. Configurer le proxy système (Méthode 3)
6. gemini-cli utilisera automatiquement Fiddler

## 🧪 Test du Proxy

Pour vérifier que le proxy fonctionne :

```powershell
python scripts/test_proxy_mitmproxy.py
```

Si ce test fonctionne mais gemini-cli ne passe toujours pas par le proxy, alors le problème vient de la façon dont gemini-cli gère les variables d'environnement.

## 📋 Checklist

- [ ] mitmproxy est démarré (vérifier avec `tasklist | findstr mitmdump`)
- [ ] Les variables sont définies dans PowerShell (pas CMD)
- [ ] gemini-cli est exécuté dans le MÊME terminal où les variables sont définies
- [ ] Le certificat mitmproxy est installé (pour HTTPS)
- [ ] Les logs de mitmproxy montrent des requêtes

## 💡 Points Importants

1. **PowerShell vs CMD** : Les variables d'environnement doivent être définies dans PowerShell avec `$env:`, pas dans CMD avec `set`

2. **Même Terminal** : gemini-cli DOIT être exécuté dans le même terminal où les variables sont définies

3. **Node.js** : gemini-cli utilise Node.js qui peut avoir des problèmes avec les variables d'environnement selon comment il est lancé

4. **Alternative Fiddler** : Si rien ne fonctionne, Fiddler est plus fiable pour Windows

## 📚 Documentation

- Guide complet : `scripts/README_capture_payloads.md`
- Solutions alternatives : `scripts/alternative_capture_method.md`
- Solution détaillée : `scripts/SOLUTION_PROXY_GEMINI_CLI.md`
