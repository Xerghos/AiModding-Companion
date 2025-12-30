# Guide de Test - Boucle Agentique CodeAssist

## ⚠️ État actuel

**Note importante** : Les méthodes `_execute_tool_call`, `_inject_function_response`, `_continue_stream_after_tool`, et `_check_circuit_breaker` doivent être implémentées dans `worker/core.py` pour que la boucle agentique fonctionne complètement.

Actuellement, le code détecte les `FunctionCallObject` (ligne 735) mais appelle `_execute_tool_call` qui n'existe pas encore.

## Vue d'ensemble

La boucle agentique permet à l'IA d'enchaîner plusieurs appels d'outils de manière autonome, en maintenant un `session_id` stable et en utilisant un Shadow History pour éviter les doublons.

## Prérequis

1. **Modèle compatible** : Utilisez un modèle qui supporte le tool calling (ex: `gemini-3-flash-preview`)
2. **OAuth configuré** : L'authentification OAuth Google doit être configurée
3. **Outils disponibles** : Les outils MCP doivent être accessibles

## Tests à effectuer (État actuel)

### Test 0 : Vérification de la détection FunctionCall

**Prompt de test :**
```
Lis le fichier worker/core.py et dis-moi combien de lignes il contient
```

**Ce que vous devriez observer :**

1. **Dans les logs** :
   - `🔧 FunctionCall détecté dans le stream: lire_fichier, id=[ID]`
   - `⏸️ Stream suspendu pour exécution du tool`
   - **⚠️ Erreur attendue** : `AttributeError: 'Worker' object has no attribute '_execute_tool_call'`
   
   **Explication** : Le code détecte bien les `FunctionCallObject`, mais la méthode `_execute_tool_call` n'est pas encore implémentée.

2. **Dans l'UI** :
   - Le stream s'arrête après la détection du tool call
   - Pas de résultat affiché (car la méthode d'exécution n'existe pas)

### Test 1 : Tool Call Simple (1 outil) - ⚠️ Nécessite implémentation

**Prompt de test :**
```
Lis le fichier worker/core.py et résume-moi les 5 premières fonctions que tu trouves
```

**Ce que vous devriez observer :**

1. **Dans les logs** :
   - `🆔 Nouveau session_id généré: [UUID]`
   - `🔧 FunctionCall détecté dans le stream: lire_fichier, id=[ID]`
   - `⏸️ Stream suspendu pour exécution du tool`
   - `⚡ Résultat : [contenu du fichier]`
   - `📝 Shadow History mis à jour: 2 messages`
   - `▶️ Reprise du stream après tool call avec session_id: [même UUID]`

2. **Dans l'UI** :
   - Affichage du résultat du tool (contenu du fichier)
   - Continuation de la réponse IA avec le résumé
   - Pas de doublon (le résultat n'apparaît qu'une fois)

### Test 2 : Boucle Multi-Outils (2-3 outils enchaînés)

**Prompt de test :**
```
Explore le dossier ui/ et trouve-moi tous les fichiers qui contiennent "ResponseContainer", puis lis le contenu du premier fichier trouvé
```

**Ce que vous devriez observer :**

1. **Séquence attendue** :
   - Tool 1 : `rechercher_texte` (cherche "ResponseContainer" dans ui/)
   - Tool 2 : `lire_fichier` (lit le premier fichier trouvé)
   - Réponse finale de l'IA

2. **Dans les logs** :
   - Même `session_id` pour tous les appels
   - `Shadow History mis à jour: 4 messages` (2 tool calls = 4 messages)
   - Pas d'erreur 429 (rate limit)

### Test 3 : Circuit Breaker (Protection boucle infinie)

**Prompt de test :**
```
Fais une boucle infinie en lisant toujours le même fichier worker/core.py
```

**Ce que vous devriez observer :**

1. **Après 15 itérations** :
   - `🛑 Circuit Breaker activé: Limite d'itérations atteinte (15)`
   - Arrêt de la boucle
   - Message d'erreur dans l'UI

2. **Après 3 répétitions identiques** :
   - `🛑 Circuit Breaker activé: Boucle détectée : même outil 'lire_fichier' appelé 3 fois de suite`
   - Arrêt de la boucle

### Test 4 : Gestion Erreurs 429

**Note** : Ce test nécessite de déclencher volontairement un rate limit (difficile en conditions normales).

**Ce que vous devriez observer si un 429 survient :**

1. **Rate Limit (retry)** :
   - `⚠️ Rate Limit (429), retry 1/3 après [X]s`
   - Retry automatique avec backoff exponentiel

2. **Quota Exhausted (arrêt)** :
   - `❌ Quota journalier épuisé (429) - Arrêt définitif`
   - Exception `QuotaExceededException` levée

## Vérifications dans les logs

### Logs à surveiller

1. **Génération session_id** :
   ```
   🆔 Nouveau session_id généré: f6c9da91-090d-4498-9c8f-09ef86fe98fe
   ```

2. **Détection functionCall** :
   ```
   🔧 FunctionCall détecté dans le stream: lire_fichier, id=abc123
   ```

3. **Exécution tool** :
   ```
   ⏸️ Stream suspendu pour exécution du tool
   ```

4. **Injection Shadow History** :
   ```
   📝 Shadow History mis à jour: 2 messages
   ```

5. **Reprise stream** :
   ```
   ▶️ Reprise du stream après tool call avec session_id: f6c9da91-090d-4498-9c8f-09ef86fe98fe
   ```

6. **Circuit Breaker** :
   ```
   🛑 Circuit Breaker activé: [raison]
   ```

## Commandes de test recommandées

### Test simple (1 outil)
```
Lis le fichier config/settings.py et dis-moi combien de clés API sont configurées
```

### Test moyen (2 outils)
```
Cherche tous les fichiers qui contiennent "AgentState" et lis le premier résultat
```

### Test complexe (3+ outils)
```
Explore le dossier ai_core/, trouve tous les fichiers qui utilisent CodeAssistClient, puis génère la documentation du premier fichier trouvé
```

### Test Circuit Breaker
```
Lis worker/core.py, puis relis-le, puis relis-le encore (test boucle)
```

## Points de vérification

✅ **Session ID stable** : Le même UUID doit apparaître pour tous les appels d'une même conversation

✅ **Pas de doublons** : Le résultat du tool n'apparaît qu'une fois dans l'UI

✅ **Pas d'erreur 429** : Aucune erreur de rate limit (sauf si quota réellement épuisé)

✅ **Shadow History** : Le nombre de messages dans le Shadow History augmente de 2 par tool call (functionCall + functionResponse)

✅ **Continuation fluide** : Après un tool call, l'IA continue naturellement sa réponse

✅ **Circuit Breaker** : La boucle s'arrête après 15 itérations ou 3 répétitions

## Dépannage

### Erreur : `AttributeError: 'Worker' object has no attribute '_execute_tool_call'`

**Cause** : Les méthodes de la boucle agentique n'ont pas encore été implémentées.

**Solution** : Implémenter les méthodes suivantes dans `worker/core.py` :
- `_execute_tool_call(self, function_call_object)`
- `_inject_function_response(self, function_call, function_response)`
- `_continue_stream_after_tool(self)`
- `_check_circuit_breaker(self, tool_name)`

### L'IA ne déclenche pas de tool call

- Vérifiez que le modèle supporte le tool calling (gemini-3-flash-preview recommandé)
- Vérifiez que les outils MCP sont accessibles
- Vérifiez les logs pour voir si `FunctionCallObject` est détecté
- Vérifiez que `detected_function_call` est bien initialisé à `None` dans `_handle_chat_stream`

### Erreur 429 persistante

- Vérifiez que le backoff exponentiel fonctionne
- Vérifiez que le même `session_id` est réutilisé
- Vérifiez que le Shadow History est utilisé (pas l'historique UI)

### Doublons dans l'UI

- Vérifiez que `_shadow_history` et `_ui_history` sont bien séparés
- Vérifiez que `is_continuation=True` est passé dans le payload

### Circuit Breaker ne fonctionne pas

- Vérifiez que `_tool_call_count` est incrémenté
- Vérifiez que `_check_circuit_breaker` est appelé avant chaque exécution
