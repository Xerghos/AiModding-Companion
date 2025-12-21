# Documentation Technique - `scripts/cursor_deepseek_proxy.py`

## 1. En-tête

### Titre

Proxy Flask pour l'API DeepSeek V3.2 compatible avec Cursor IDE

### Description concise

Ce script Python implémente un serveur proxy léger basé sur Flask. Il agit comme un intermédiaire entre l'IDE Cursor (ou tout client compatible OpenAI API) et l'API DeepSeek V3.2 `chat/completions`. Son objectif principal est d'adapter les requêtes et les réponses de DeepSeek pour assurer la compatibilité avec Cursor, en résolvant notamment la gestion des messages utilisateur consécutifs et en intégrant le "processus de pensée" (`reasoning_content`) de DeepSeek directement dans l'interface utilisateur de Cursor.

### Dépendances

*   **Flask**: Un micro-framework web pour Python, utilisé pour créer l'API proxy.
    *   `pip install Flask`
*   **requests**: Une bibliothèque HTTP pour Python, utilisée pour effectuer les appels vers l'API DeepSeek.
    *   `pip install requests`
*   **json**: (Bibliothèque standard Python) Utilisée pour la sérialisation et la désérialisation JSON.
*   **sys**: (Bibliothèque standard Python) Utilisée pour les interactions avec le système, bien que son usage soit minimal ici.

## 2. Classes & Fonctions

### `app`

*   **Type**: Instance de `Flask`
*   **Description**: L'application Flask principale qui gère les routes et les requêtes entrantes.

### `proxy()`

*   **Signature**: `proxy()`
*   **Arguments**: Aucun directement. Reçoit les données via l'objet `request` global de Flask (spécifiquement `request.json` pour le corps de la requête POST).
*   **Retours**:
    *   `flask.Response` avec un `content_type` de `text/event-stream` pour les réponses en streaming.
    *   `flask.Response` avec un `content_type` de `application/json` et un statut 500 en cas d'erreur interne du proxy.
*   **Logique interne**:
    1.  **Réception des données**: Récupère le corps de la requête POST entrante au format JSON.
    2.  **`FIX 1: Fusion des messages User consécutifs`**:
        *   **Problématique**: L'IDE Cursor envoie fréquemment des messages utilisateur consécutifs (par exemple, un pour le contexte et un pour l'instruction réelle), ce que l'API DeepSeek peut rejeter.
        *   **Solution**: Le code itère sur la liste des messages. Si deux messages consécutifs ont le rôle `'user'`, leur contenu est fusionné en un seul message utilisateur, séparé par un double saut de ligne. Les autres messages sont conservés tels quels.
    3.  **Préparation de la charge utile (payload) pour DeepSeek**:
        *   Crée un dictionnaire `payload` contenant le modèle cible (`TARGET_MODEL`), les messages fusionnés, active le streaming (`"stream": True`) et définit une `temperature` de 0.6 (la V3.2 DeepSeek tolère ce paramètre).
        *   Copie le paramètre `max_tokens` de la requête entrante vers le `payload` DeepSeek si présent.
    4.  **Définition des en-têtes**:
        *   Crée un dictionnaire `headers` incluant la clé API DeepSeek (`DEEPSEEK_API_KEY`) pour l'autorisation, `Content-Type: application/json` et `Accept: application/json`.
    5.  **`FIX 2: Gestion du Streaming et Affichage de la Pensée`**:
        *   Définit une fonction génératrice imbriquée `generate()` pour gérer la communication en streaming avec DeepSeek et la transformation des réponses.
        *   Le `generate()` est ensuite enveloppé par `stream_with_context` et renvoyé dans une `Response` Flask.

### `generate()` (fonction génératrice interne à `proxy`)

*   **Signature**: `generate()`
*   **Arguments**: Aucun directement. Accède aux variables de la fonction `proxy` par fermeture (closure) : `DEEPSEEK_URL`, `payload`, `headers`.
*   **Retours**: Génère des chaînes de caractères au format Server-Sent Events (SSE) (`data: {json_chunk}\n\n`).
*   **Logique interne**:
    1.  **Appel à l'API DeepSeek**: Effectue une requête `POST` en streaming vers `DEEPSEEK_URL` avec le `payload` et les `headers` préparés.
    2.  **Gestion des erreurs HTTP**: Si la réponse de DeepSeek n'est pas un code 200, un message d'erreur est envoyé au client sous forme SSE.
    3.  **Traitement des lignes de streaming**:
        *   Itère sur les lignes de la réponse de DeepSeek (`resp.iter_lines()`).
        *   Décode chaque ligne en UTF-8.
        *   Si la ligne commence par `"data: "` et n'est pas juste `"data:"`:
            *   Tente de décoder le contenu JSON après `"data: "`.
            *   **Traitement du "processus de pensée" (`reasoning_content`)**:
                *   Si le chunk JSON contient `reasoning_content` (spécifique à DeepSeek V3.2), ce contenu est extrait.
                *   Un nouveau chunk est créé pour le client, avec le `reasoning_content` enveloppé dans des underscores (`_`) pour le rendre italique dans l'UI de Cursor.
                *   Le champ `model` est remplacé par `"GPT-5 Nano"` (ou similaire) pour contourner d'éventuels problèmes de compatibilité ou d'affichage dans Cursor.
                *   Ce chunk transformé est renvoyé au client.
            *   **Traitement du contenu standard (`content`)**:
                *   Si le chunk contient `content` (la réponse finale ou un fragment de code), il est renvoyé tel quel au client.
            *   Gère les `json.JSONDecodeError` silencieusement si une ligne n'est pas un JSON valide.
        *   Si la ligne est juste `"data:"`, elle est renvoyée telle quelle (souvent un heartbeat ou un délimiteur vide).
    4.  **Gestion des exceptions**: Capture toute autre exception survenant pendant le streaming et envoie un message d'erreur JSON formaté comme SSE au client.

## 3. Exemple d'usage

### 1. Configuration du Proxy

Mettez à jour votre clé API DeepSeek dans le script :

```python
DEEPSEEK_API_KEY = "sk-VOTRE_CLE_API_DEEPSEEK_ICI"
```

### 2. Exécution du Proxy

Lancez le script Python :

```bash
python scripts/cursor_deepseek_proxy.py
```

Vous devriez voir un message indiquant que le proxy est démarré sur `http://127.0.0.1:5000`.

```
🚀 Proxy DeepSeek V3.2 démarré sur http://127.0.0.1:5000
Cible API: deepseek-reasoner
 * Serving Flask app 'cursor_deepseek_proxy'
 * Debug mode: on
...
```

### 3. Configuration de l'IDE Cursor

Pour que Cursor utilise ce proxy au lieu de l'API OpenAI officielle, vous devez configurer les variables d'environnement appropriées.

**Méthode 1: Variables d'environnement globales (recommandé pour un usage fréquent)**

Définissez ces variables avant de lancer Cursor (peut varier selon votre système d'exploitation) :

*   **Linux/macOS (Terminal)**:
    ```bash
    export OPENAI_API_BASE=http://127.0.0.1:5000/v1
    export OPENAI_API_KEY=sk-dummy # La clé n'est pas utilisée par le proxy, mais Cursor en requiert une.
    # Ensuite, lancez Cursor depuis ce même terminal
    /path/to/Cursor.app/Contents/MacOS/Cursor
    ```
*   **Windows (Invite de commandes/PowerShell)**:
    ```cmd
    set OPENAI_API_BASE=http://127.0.0.1:5000/v1
    set OPENAI_API_KEY=sk-dummy
    rem Ensuite, lancez Cursor
    "C:\Users\%USERNAME%\AppData\Local\Programs\Cursor\Cursor.exe"
    ```

**Méthode 2: Fichier de configuration de l'IDE Cursor**

Certaines versions de Cursor permettent de définir ces paramètres directement dans les préférences de l'IDE ou via un fichier `.env` si supporté par l'extension. Cherchez les paramètres liés aux API OpenAI dans les réglages de Cursor.

Une fois configuré, Cursor enverra ses requêtes `chat/completions` à `http://127.0.0.1:5000/v1/chat/completions`, qui seront traitées par le proxy et redirigées vers DeepSeek. Le "processus de pensée" de DeepSeek apparaîtra en italique dans la fenêtre de chat de Cursor.