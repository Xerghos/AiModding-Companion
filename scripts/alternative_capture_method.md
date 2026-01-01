# Méthode Alternative de Capture - Si le Proxy Ne Fonctionne Pas

Si gemini-cli ne passe pas par le proxy mitmproxy, voici des alternatives :

## 🔍 Problème Identifié

Le message "If you can see this, traffic is not going through mitmproxy" signifie que :
- gemini-cli n'utilise pas le proxy HTTP_PROXY/HTTPS_PROXY
- Ou les requêtes vont directement sans passer par le proxy

## 🛠️ Solutions Alternatives

### Option 1 : Vérifier que gemini-cli respecte les variables d'environnement

gemini-cli utilise Node.js avec `google-auth-library` qui devrait respecter HTTP_PROXY/HTTPS_PROXY, mais il peut y avoir des problèmes.

**Test :**
```powershell
# Dans un nouveau terminal PowerShell
$env:HTTP_PROXY="http://localhost:8080"
$env:HTTPS_PROXY="http://localhost:8080"

# Vérifier que les variables sont bien définies
echo $env:HTTP_PROXY
echo $env:HTTPS_PROXY

# Tester avec une requête simple
gemini-cli "Hello"
```

**Vérifier dans les logs de mitmproxy** si vous voyez des requêtes.

### Option 2 : Utiliser un proxy système (Windows)

Si les variables d'environnement ne fonctionnent pas, configurez le proxy au niveau système :

1. **Paramètres Windows → Réseau et Internet → Proxy**
2. Configurer un proxy manuel :
   - Adresse : `127.0.0.1`
   - Port : `8080`
3. Redémarrer gemini-cli

⚠️ **Attention** : Cela affectera TOUTES les applications qui utilisent le proxy système.

### Option 3 : Modifier directement le code source de gemini-cli (temporaire)

Si vous avez accès au code source de gemini-cli, vous pouvez modifier temporairement le code pour forcer l'utilisation du proxy.

**Fichier à modifier :** `packages/core/src/code_assist/server.ts`

Chercher où les requêtes HTTP sont faites et ajouter explicitement le proxy.

### Option 4 : Utiliser Fiddler ou Charles Proxy

Ces outils de proxy HTTP peuvent capturer le trafic sans configuration côté client :

1. **Fiddler** (Windows) : https://www.telerik.com/fiddler
   - Démarrer Fiddler
   - Configurer pour capturer HTTPS
   - Installer le certificat Fiddler
   - gemini-cli utilisera automatiquement le proxy système

2. **Charles Proxy** (Multi-plateforme) : https://www.charlesproxy.com/
   - Similaire à Fiddler mais payant (version d'essai disponible)

### Option 5 : Analyser directement les logs de gemini-cli

gemini-cli peut avoir des logs internes qui montrent les requêtes envoyées :

```powershell
# Activer les logs détaillés
$env:DEBUG="*"
gemini-cli "votre commande"
```

### Option 6 : Utiliser Wireshark (avancé)

Capture réseau au niveau système :

1. Installer Wireshark
2. Capturer le trafic vers `cloudcode-pa.googleapis.com`
3. Filtrer les requêtes HTTP/HTTPS
4. Extraire les payloads JSON

⚠️ **Complexe** : Nécessite de décoder HTTPS (nécessite les clés privées).

## 🎯 Recommandation

1. **D'abord** : Vérifier que les variables sont bien définies dans le terminal où gemini-cli est exécuté
2. **Ensuite** : Tester avec le script `test_proxy_mitmproxy.py` pour vérifier que le proxy fonctionne
3. **Si ça ne marche toujours pas** : Utiliser Fiddler (Windows) qui est plus simple à configurer

## 📝 Test Rapide

Exécutez ce script pour tester si le proxy fonctionne :

```powershell
python scripts/test_proxy_mitmproxy.py
```

Si ce script fonctionne mais gemini-cli ne passe pas par le proxy, alors le problème vient de la configuration de gemini-cli.
