# Solution : Le Trafic Ne Passe Pas Par mitmproxy

## 🔍 Diagnostic

Si vous voyez "If you can see this, traffic is not going through mitmproxy" sur http://mitm.it, cela signifie que **gemini-cli n'utilise pas le proxy**.

## ✅ Solution Étape par Étape

### Étape 1 : Vérifier que mitmproxy est démarré

Dans un terminal, vérifiez :
```powershell
# Windows
tasklist | findstr mitmdump

# Si rien n'apparaît, démarrez mitmproxy :
mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
```

### Étape 2 : Utiliser le script de vérification PowerShell

**⚠️ IMPORTANT : Exécutez ce script dans PowerShell (pas CMD)**

```powershell
.\scripts\verifier_proxy_gemini_cli.ps1
```

Ce script va :
- Vérifier si mitmproxy est démarré
- Configurer les variables d'environnement
- Tester le proxy
- Vous donner les instructions exactes

### Étape 3 : Exécuter gemini-cli dans le MÊME terminal

**CRITIQUE** : Après avoir exécuté le script PowerShell, **restez dans CE TERMINAL** et exécutez gemini-cli :

```powershell
# Dans le MÊME terminal PowerShell où vous avez exécuté verifier_proxy_gemini_cli.ps1
gemini-cli "Lis le fichier README.md"
```

### Étape 4 : Vérifier les logs de mitmproxy

Dans le terminal où mitmproxy est démarré, vous devriez voir :
```
[INFO] Requête #1: cloudcode-pa.googleapis.com/v1internal:streamGenerateContent
[INFO] ✅ Requête CodeAssist détectée
```

Si vous ne voyez **RIEN**, alors gemini-cli n'utilise toujours pas le proxy.

## 🔧 Solutions Alternatives Si Ça Ne Marche Toujours Pas

### Alternative 1 : Vérifier comment gemini-cli est lancé

gemini-cli peut être lancé de différentes façons qui peuvent ignorer les variables d'environnement :

1. **Via npm/npx** :
   ```powershell
   npx @google/gemini-cli "votre commande"
   ```
   → Les variables d'environnement devraient fonctionner

2. **Via un alias ou un script wrapper** :
   → Le wrapper peut ne pas passer les variables d'environnement

3. **Via un IDE ou un autre outil** :
   → L'IDE peut avoir sa propre configuration de proxy

### Alternative 2 : Configurer le proxy au niveau système Windows

Si les variables d'environnement ne fonctionnent pas :

1. **Paramètres Windows** → **Réseau et Internet** → **Proxy**
2. Activer "Utiliser un serveur proxy"
3. Adresse : `127.0.0.1`
4. Port : `8080`
5. **Désactiver** "N'utiliser le serveur proxy que pour les adresses locales"
6. Redémarrer gemini-cli

⚠️ **Attention** : Cela affectera TOUTES les applications Windows qui utilisent le proxy système.

### Alternative 3 : Utiliser Fiddler (Plus Simple)

Fiddler est un proxy HTTP pour Windows qui est plus facile à configurer :

1. **Télécharger Fiddler** : https://www.telerik.com/fiddler
2. **Démarrer Fiddler**
3. **Configurer HTTPS** :
   - Tools → Options → HTTPS
   - Cocher "Capture HTTPS CONNECTs"
   - Cocher "Decrypt HTTPS traffic"
   - Installer le certificat Fiddler
4. **Configurer le proxy système** (comme Alternative 2)
5. gemini-cli utilisera automatiquement Fiddler

Fiddler affichera toutes les requêtes HTTP/HTTPS avec les payloads complets.

### Alternative 4 : Modifier temporairement le code source de gemini-cli

Si vous avez accès au code source de gemini-cli, vous pouvez forcer l'utilisation du proxy :

**Fichier :** `packages/core/src/code_assist/server.ts`

Modifier la méthode `requestPost` pour ajouter explicitement le proxy :

```typescript
async requestPost<T>(
  method: string,
  req: object,
  signal?: AbortSignal,
): Promise<T> {
  const res = await this.client.request({
    url: this.getMethodUrl(method),
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...this.httpOptions.headers,
    },
    responseType: 'json',
    body: JSON.stringify(req),
    signal,
    // AJOUTER CETTE LIGNE :
    proxy: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || 'http://localhost:8080',
  });
  return res.data as T;
}
```

Faire de même pour `requestGet` et `requestStreamingPost`.

## 🧪 Test Rapide

Pour vérifier que le proxy fonctionne, testez avec Python :

```powershell
python scripts/test_proxy_mitmproxy.py
```

Si ce script fonctionne mais gemini-cli ne passe pas par le proxy, alors le problème vient de la façon dont gemini-cli gère les variables d'environnement.

## 📋 Checklist de Vérification

- [ ] mitmproxy est démarré (vérifier avec `tasklist | findstr mitmdump`)
- [ ] Les variables HTTP_PROXY et HTTPS_PROXY sont définies dans le terminal
- [ ] gemini-cli est exécuté dans le MÊME terminal où les variables sont définies
- [ ] Le certificat mitmproxy est installé (pour HTTPS)
- [ ] Les logs de mitmproxy montrent des requêtes (même si ce ne sont pas des tool calls)

## 💡 Astuce : Vérifier les Requêtes dans mitmproxy

Même si gemini-cli ne passe pas par le proxy pour les requêtes CodeAssist, vous devriez voir **d'autres requêtes** dans les logs de mitmproxy (mises à jour, authentification, etc.).

Si vous ne voyez **AUCUNE requête**, alors :
1. Le proxy n'est pas démarré, OU
2. gemini-cli n'utilise vraiment pas le proxy du tout

Dans ce cas, utilisez **Fiddler** (Alternative 3) qui est plus fiable pour Windows.
