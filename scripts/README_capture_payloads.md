# Guide de Capture des Payloads Gemini-CLI

Ce guide explique comment capturer et analyser les payloads réels envoyés par `gemini-cli` à l'API CodeAssist pour comprendre exactement comment les tool calls sont gérés.

## 🎯 Objectif

Comprendre la structure exacte des payloads lors des tool calls pour :
- Voir comment les IDs sont gérés (présents/absents)
- Vérifier la présence/absence de `thoughtSignature`
- Comprendre le format exact des `functionResponse`
- Comparer avec nos payloads qui génèrent des erreurs 400

## 📋 Prérequis

### Option 1 : mitmproxy (Recommandé - Support HTTPS complet)

```bash
pip install mitmproxy
```

### Option 2 : Proxy HTTP simple (Limité pour HTTPS)

Aucune dépendance supplémentaire (utilise la bibliothèque standard Python).

## 🚀 Utilisation

### Méthode 1 : mitmproxy (Recommandé)

1. **Démarrer le proxy mitmproxy** :
   ```bash
   mitmdump -s scripts/capture_gemini_cli_mitmproxy.py
   ```

2. **Installer le certificat mitmproxy** (pour HTTPS) :
   - Ouvrir http://mitm.it dans votre navigateur
   - Télécharger le certificat pour votre OS
   - Installer le certificat dans le magasin de certificats système
   - **Important** : Sur Windows, installer dans "Autorités de certification racines de confiance"

3. **Configurer gemini-cli pour utiliser le proxy** :
   ```bash
   # Windows
   set HTTP_PROXY=http://localhost:8080
   set HTTPS_PROXY=http://localhost:8080
   
   # Linux/Mac
   export HTTP_PROXY=http://localhost:8080
   export HTTPS_PROXY=http://localhost:8080
   ```

4. **Exécuter une commande avec tool call dans gemini-cli** :
   ```bash
   gemini-cli "Lis le fichier README.md et résume-le"
   ```

5. **Les payloads seront automatiquement capturés** dans `logs/gemini_cli_tool_call_*.json`

### Méthode 2 : Proxy HTTP simple

1. **Démarrer le proxy** :
   ```bash
   python scripts/capture_gemini_cli_http_proxy.py [port]
   ```
   Par défaut, le port est 8888.

2. **Configurer gemini-cli** :
   ```bash
   set HTTP_PROXY=http://localhost:8888
   ```

3. **⚠️ Limitation** : Ce proxy ne gère pas correctement HTTPS, donc certaines requêtes peuvent échouer.

## 📊 Analyse des Payloads Capturés

### Analyse automatique

Le script `capture_gemini_cli_mitmproxy.py` analyse automatiquement chaque payload et affiche :
- Détection des `functionCall` et `functionResponse`
- Présence/absence d'IDs
- Présence/absence de `thoughtSignature`
- Corrélations ID entre `functionCall` et `functionResponse`
- Comparaison avec nos payloads d'erreur 400

### Analyse approfondie

Pour une analyse complète de tous les payloads capturés :

```bash
# Analyse basique
python scripts/analyze_gemini_cli_tool_payloads.py

# Avec comparaison avec nos payloads
python scripts/analyze_gemini_cli_tool_payloads.py --compare

# Analyse détaillée de chaque payload
python scripts/analyze_gemini_cli_tool_payloads.py --detailed
```

### Rapport généré

Le script d'analyse génère un rapport JSON complet dans `logs/analysis_reports/gemini_cli_analysis_*.json` contenant :
- Statistiques agrégées
- Patterns détectés
- Comparaisons avec nos payloads
- Recommandations automatiques

## 🔍 Points à Vérifier

Lors de l'analyse, vérifiez particulièrement :

1. **IDs dans functionCall** :
   - Sont-ils toujours présents ?
   - Format des IDs (UUID v4, autres formats)
   - Que se passe-t-il quand il n'y a pas d'ID ?

2. **thoughtSignature** :
   - Est-il présent dans les réponses de l'API ?
   - Est-il réinjecté dans les requêtes suivantes ?
   - Où se trouve-t-il exactement (dans functionCall, dans part, ailleurs) ?

3. **Format functionResponse** :
   - Utilise-t-il `response.output` ou `response.content` ?
   - Structure exacte de l'objet `response`

4. **Séquence dans contents** :
   - Ordre exact : user → model (functionCall) → function (functionResponse)
   - Y a-t-il des messages intermédiaires ?

5. **Corrélation ID** :
   - Les IDs correspondent-ils toujours entre functionCall et functionResponse ?
   - Que se passe-t-il si l'un ou l'autre n'a pas d'ID ?

## 📁 Fichiers Générés

### Pendant la capture

- `logs/gemini_cli_tool_call_*.json` : Payloads contenant des tool calls
- `logs/gemini_cli_request_*.json` : Autres requêtes CodeAssist

### Après l'analyse

- `logs/analysis_reports/gemini_cli_analysis_*.json` : Rapport complet d'analyse

## 🐛 Dépannage

### Le proxy ne capture rien

1. Vérifier que gemini-cli utilise bien le proxy :
   ```bash
   echo %HTTP_PROXY%  # Windows
   echo $HTTP_PROXY   # Linux/Mac
   ```

2. Vérifier que le proxy écoute bien :
   - mitmproxy : port 8080 par défaut
   - Proxy HTTP : port 8888 par défaut

3. Vérifier les logs du proxy pour voir les requêtes interceptées

### Erreurs HTTPS avec mitmproxy

1. Vérifier que le certificat est bien installé
2. Sur Windows, s'assurer qu'il est dans "Autorités de certification racines de confiance"
3. Redémarrer gemini-cli après l'installation du certificat

### Aucun tool call détecté

1. Vérifier que la commande exécutée nécessite réellement un tool call
2. Essayer une commande explicite : `gemini-cli "Lis le fichier README.md"`
3. Vérifier les logs du proxy pour voir toutes les requêtes capturées

## 💡 Conseils

1. **Capturer plusieurs exemples** : Exécutez plusieurs commandes différentes pour avoir une vue complète
2. **Comparer avec nos erreurs** : Utilisez `--compare` pour voir les différences avec nos payloads qui génèrent des erreurs 400
3. **Vérifier les séquences** : Regardez l'ordre exact des messages dans `contents` pour comprendre la séquence attendue
4. **Analyser les IDs** : Vérifiez si les IDs sont générés par l'API ou par le client

## 📚 Références

- Code source gemini-cli : `DOC_codes_sources/gemini-cli-main/`
- Fichiers clés :
  - `packages/core/src/code_assist/converter.ts` : Construction des payloads
  - `packages/core/src/code_assist/server.ts` : Envoi des requêtes
