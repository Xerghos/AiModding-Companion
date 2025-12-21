# Documentation Technique - `ai_core\sessions.py`

## 1. En-tête

*   **Titre**: Gestion des Sessions d'IA
*   **Description concise**: Ce module gère l'initialisation et l'interaction avec diverses APIs de modèles d'IA (Gemini, DeepSeek, Groq, et Gemini CLI) en encapsulant la logique d'appel, la gestion des clés, l'historique de conversation, la journalisation des payloads et l'intégration de contextes RAG (Retrieval Augmented Generation) et de cache. Il fournit une interface unifiée pour interagir avec différents fournisseurs.
*   **Dépendances**:
    *   `google.generativeai`: Client Python officiel pour l'API Gemini.
    *   `google.generativeai.caching`: Fonctionnalités de caching pour Gemini.
    *   `time`: Mesure du temps d'exécution.
    *   `json`: Manipulation de données JSON.
    *   `contextlib`: Utilitaires pour gestionnaires de contexte.
    *   `logging`: Journalisation (bien que `UnifiedLogger` soit priorisé).
    *   `requests`: Requêtes HTTP pour les APIs REST (DeepSeek, Groq).
    *   `re`: Expressions régulières (non utilisé directement dans le code fourni, mais souvent utile).
    *   `enum.Enum`: Types énumérés pour les modes d'IA.
    *   `datetime`: Gestion des dates et heures pour la journalisation.
    *   `threading.Lock`: Verrous de thread (non utilisé directement dans le code fourni).
    *   `subprocess`: Exécution de commandes externes (pour Gemini CLI).
    *   `shutil`: Opérations sur les fichiers de haut niveau (pour Gemini CLI).
    *   `os`: Interactions avec le système d'exploitation.
    *   `sys`: Accès aux paramètres système (pour Gemini CLI).
    *   `tempfile`: Création de fichiers et répertoires temporaires (pour Gemini CLI).
    *   `atexit`: Enregistrement de fonctions à exécuter à la sortie du programme (pour Gemini CLI).
    *   `config.settings`: Paramètres globaux de l'application.
    *   `config.logs.get_logger`: Fonction de récupération d'un logger.
    *   `features.Decorators.trace_action`: Décorateur pour tracer les actions.
    *   `features.UnifiedLogger`: Système de journalisation unifié de l'application.
    *   `ai_core.prompt_builders`: Fonctions pour construire les prompts spécifiques au CLI.
    *   `config.tools_schema` (import conditionnel): Schéma des outils natifs disponibles.
    *   `features.CacheManager` (import conditionnel): Gestionnaire de cache global pour les composants de contexte.
    *   `features.TokenManager` (import local/lazy): Gestionnaire de l'utilisation des tokens.

## 2. Classes & Fonctions

### Enumérations

#### `class AiMode(Enum)`

Représente les différents modes de fonctionnement que l'IA peut adopter.

*   `STANDARD = "standard"`: Mode généraliste.
*   `ROUTER_STRICT = "router_strict"`: Mode de routage strict, probablement pour des tâches spécifiques nécessitant une grande précision.
*   `CREATIVE = "creative"`: Mode axé sur la créativité.
*   `REASONING = "reasoning"`: Mode axé sur le raisonnement et la logique.

### Exceptions

#### `class QuotaExceededException(Exception)`

Exception levée lorsqu'un quota API est dépassé.

#### `class FatalKeyError(Exception)`

Exception levée lorsqu'aucune clé API valide n'est disponible ou qu'une erreur fatale liée à la clé survient.

### Fonctions d'Aide (Helpers)

#### `def _trigger_cache_analysis(payload_path: str, session_type: str, model_name: str)`

Déclenche de manière asynchrone un script d'analyse des cassures de cache entre le payload actuel et le précédent pour le même type de session et modèle.

*   **Arguments**:
    *   `payload_path` (`str`): Chemin complet du fichier JSON du payload actuel.
    *   `session_type` (`str`): Type de session (ex: "deepseek", "gemini").
    *   `model_name` (`str`): Nom du modèle IA utilisé.
*   **Retours**: `None`
*   **Logique interne**:
    1.  Détermine le répertoire de logs.
    2.  Recherche le payload précédent du même type de session et modèle.
    3.  Construit le chemin vers le script `analyze_payload_cache_breaks.py`.
    4.  Exécute le script en arrière-plan (`subprocess.Popen`) avec les chemins des deux payloads, sans bloquer l'exécution principale.
    5.  Journalise les erreurs de déclenchement sans les propager.

#### `def _save_payload_log(session_type: str, model_name: str, payload_data: dict, extra_meta: dict = None)`

Sauvegarde un payload (prompt et contexte) dans le répertoire `logs/` avec un horodatage pour l'analyse ultérieure.

*   **Arguments**:
    *   `session_type` (`str`): Type de session (ex: "deepseek", "gemini", "gemini_cli").
    *   `model_name` (`str`): Nom du modèle IA utilisé.
    *   `payload_data` (`dict`): Dictionnaire contenant le payload complet de la requête API (messages, prompt, etc.).
    *   `extra_meta` (`dict`, optionnel): Métadonnées additionnelles à inclure dans le log (ex: métriques).
*   **Retours**: `None`
*   **Logique interne**:
    1.  Crée le répertoire `logs/` si nécessaire.
    2.  Génère un nom de fichier unique avec horodatage et nom de modèle sécurisé.
    3.  Construit le contenu du log JSON avec horodatage, type de session, modèle et le payload.
    4.  Écrit le contenu dans le fichier.
    5.  Journalise la sauvegarde du payload.
    6.  Appelle `_trigger_cache_analysis` pour l'analyse des cassures de cache.
    7.  Journalise les erreurs de sauvegarde sans les propager.

#### `def _convert_schema_to_openai(gemini_tools)`

Convertit un schéma d'outils au format Gemini (où les types sont souvent en MAJUSCULES, ex: "STRING") vers le format OpenAI/DeepSeek (types en minuscules, ex: "string").

*   **Arguments**:
    *   `gemini_tools` (`list`): Liste de dictionnaires représentant les définitions d'outils au format Gemini.
*   **Retours**: `list` (Liste de dictionnaires au format OpenAI/DeepSeek) ou `None` si `gemini_tools` est vide.
*   **Logique interne**:
    1.  Crée une copie profonde de chaque outil pour éviter les modifications d'objets originaux.
    2.  Utilise une fonction récursive `lower_types` pour parcourir la structure des `parameters` de chaque outil et convertir les valeurs associées à la clé "type" en minuscules.
    3.  Encapsule chaque outil converti dans la structure `{"type": "function", "function": {...}}` attendue par OpenAI/DeepSeek.

#### `def _proto_to_dict_recursive(obj)`

Convertit récursivement un objet de type proto (ou un objet avec des attributs d'accès similaires à un dictionnaire/liste) en un dictionnaire ou une liste Python standard. Utile pour manipuler les réponses d'API Gemini qui utilisent des objets protobuf.

*   **Arguments**:
    *   `obj`: L'objet à convertir (peut être un dictionnaire, une liste, un objet protobuf, etc.).
*   **Retours**: `dict` ou `list` (Représentation Python standard de l'objet).
*   **Logique interne**:
    1.  Si l'objet a une méthode `items` (comme un dictionnaire ou un objet proto se comportant comme tel), il est récursivement converti en dictionnaire.
    2.  Si l'objet est itérable mais pas une chaîne de caractères ou des bytes, il est récursivement converti en liste.
    3.  Sinon, l'objet est retourné tel quel (cas de base).

### Classes

#### `class UniversalResponseWrapper`

Classe utilitaire pour envelopper les réponses de différentes APIs IA dans une interface commune.

*   **Constructeur**: `__init__(self, text, raw_response=None, tool_calls=None)`
    *   **Arguments**:
        *   `text` (`str`): Le texte principal de la réponse.
        *   `raw_response` (optionnel): La réponse brute de l'API sous-jacente.
        *   `tool_calls` (`list`, optionnel): Une liste d'appels d'outils identifiés dans la réponse.
    *   **Logique interne**: Initialise les attributs `text`, `raw`, `tool_calls` et `parts`. `parts` est une liste contenant un objet simple avec un attribut `text` pour simuler la structure de réponse de certaines APIs.

#### `class GroqSession`

Gère les interactions avec l'API Groq.

*   **Constructeur**: `__init__(self, key_manager, model_name="llama3-70b-8192", system_instruction=None, agent_name=None)`
    *   **Arguments**:
        *   `key_manager`: Instance du gestionnaire de clés API.
        *   `model_name` (`str`, optionnel): Nom du modèle Groq à utiliser (par défaut: "llama3-70b-8192").
        *   `system_instruction` (`str`, optionnel): Instruction système initiale pour le modèle.
        *   `agent_name` (`str`, optionnel): Nom de l'agent utilisant cette session.
    *   **Logique interne**: Initialise le gestionnaire de clés, le nom du modèle, l'historique de chat, la clé API actuelle et l'URL de base. Ajoute l'instruction système à l'historique si fournie.

*   `@trace_action(source="sessions")`
    `send_message(self, message, stream=False, tool_config=None, rag_context=None)`
    Envoie un message à l'API Groq et gère la réponse.

    *   **Arguments**:
        *   `message`: Le message utilisateur à envoyer.
        *   `stream` (`bool`, optionnel): Si `True`, la réponse est un générateur de chunks (streaming). Par défaut: `False`.
        *   `tool_config` (optionnel): Configuration des outils (ignoré pour Groq, interface de compatibilité).
        *   `rag_context` (optionnel): Contexte RAG à injecter (dict ou str).
    *   **Retours**: Un générateur si `stream=True`, sinon une instance de `UniversalResponseWrapper`.
    *   **Logique interne**:
        1.  Récupère une clé API valide via le `key_manager`. Lève `FatalKeyError` si aucune clé.
        2.  Construit le message utilisateur final, en préfixant le `rag_context` si fourni.
        3.  Ajoute le message utilisateur à l'historique interne.
        4.  Prépare les en-têtes de la requête HTTP.
        5.  **Construction du Payload de Log**: Une logique complexe est mise en œuvre pour reconstruire le payload qui sera enregistré (pour `_save_payload_log`), en nettoyant l'historique des doublons de RAG et LTM, et en structurant les messages système (instructions, arch, tree, ltm, focus) et l'historique conversationnel de manière explicite pour la journalisation.
        6.  Sauvegarde le payload construit via `_save_payload_log`.
        7.  Effectue la requête POST vers l'API Groq.
        8.  Gère les erreurs HTTP (code 4xx/5xx) en rapportant l'erreur au `key_manager` et en levant une exception.
        9.  Marque la clé comme réussie via le `key_manager`.
        10. Calcule l'utilisation des tokens (estimation pour l'entrée avant réponse, précise après).
        11. Si `stream=True`, retourne un générateur qui lit les chunks, accumule la réponse complète, journalise les erreurs de stream, et effectue le logging des métriques à la fin.
        12. Si `stream=False`, parse la réponse JSON complète, ajoute la réponse à l'historique, loggue les métriques et retourne un `UniversalResponseWrapper`.
        13. Gère les exceptions de requête en rapportant l'erreur au `key_manager` et en les propageant.

*   `@property`
    `chat(self)`
    Propriété pour fournir une interface de compatibilité avec l'historique de chat de l'API Gemini.

    *   **Retours**: Une instance de `MockHistory` qui expose un attribut `history` et une méthode `rewind`.
    *   **Logique interne**: Adapte l'historique interne de Groq (`self.history`) au format attendu par les composants qui interagissent avec l'objet `chat` (rôles `model`/`user` au lieu de `assistant`/`user`, et `parts` pour le texte).

#### `class BaseSession`

Classe abstraite définissant l'interface commune pour toutes les sessions d'IA.

*   **Constructeur**: `__init__(self, key_manager, model_name, system_instruction)`
    *   **Arguments**:
        *   `key_manager`: Instance du gestionnaire de clés API.
        *   `model_name` (`str`): Nom du modèle IA.
        *   `system_instruction` (`str`): Instruction système initiale.
    *   **Logique interne**: Initialise les attributs de base.

*   `send_message(self, message, stream=True, tool_config=None, rag_context=None)`
    Méthode abstraite qui doit être implémentée par les classes dérivées.

    *   **Arguments**: Voir les implémentations spécifiques.
    *   **Retours**: Lève `NotImplementedError`.

#### `class DeepSeekSession(BaseSession)`

Gère les interactions avec l'API DeepSeek.

*   **Constructeur**: `__init__(self, key_manager, model_name="deepseek-chat", system_instruction=None, base_url=None, agent_name=None)`
    *   **Arguments**:
        *   `key_manager`: Instance du gestionnaire de clés API.
        *   `model_name` (`str`, optionnel): Nom du modèle DeepSeek (par défaut: "deepseek-chat").
        *   `system_instruction` (`str`, optionnel): Instruction système initiale.
        *   `base_url` (`str`, optionnel): URL de base de l'API DeepSeek (déduite si "speciale" dans le nom du modèle).
        *   `agent_name` (`str`, optionnel): Nom de l'agent utilisant cette session.
    *   **Logique interne**: Initialise les attributs et détermine l'URL de base de l'API DeepSeek en fonction du `model_name` ou du `base_url` fourni.

*   `_create_msg(self, role, text)`
    Fonction utilitaire pour créer un message au format dictionnaire (`{"role": role, "content": text}`).

    *   **Arguments**:
        *   `role` (`str`): Rôle du message ("user", "assistant", "system").
        *   `text` (`str`): Contenu du message.
    *   **Retours**: `dict` (Le message formaté).

*   `_build_payload_messages(self, rag_context=None)`
    Construit la liste des messages à envoyer à l'API DeepSeek, en intégrant les instructions système, les composants de cache (Repo Map, Arborescence, LTM) et l'historique conversationnel.

    *   **Arguments**:
        *   `rag_context` (optionnel): Contexte RAG (ignoré dans cette fonction, géré au niveau `send_message`).
    *   **Retours**: `list` (Liste de dictionnaires de messages).
    *   **Logique interne**:
        1.  Ajoute les `system_instruction` de l'agent.
        2.  Tente de récupérer les composants de cache (`repo_map`, `tree`, `ltm`) via `GlobalCacheManager` et les ajoute comme messages système (avec gestion des en-têtes dupliqués).
        3.  Itère sur l'historique interne (`self.history`), filtre les messages système dupliqués et normalise les rôles.
        4.  Ajoute une instruction "Focus sur la demande ci-dessous" juste avant le dernier message utilisateur.

*   `@trace_action(source="sessions")`
    `send_message(self, message, stream=False, tool_config=None, rag_context=None)`
    Envoie un message à l'API DeepSeek et gère la réponse.

    *   **Arguments**:
        *   `message`: Le message utilisateur à envoyer.
        *   `stream` (`bool`, optionnel): Si `True`, la réponse est un générateur de chunks. Par défaut: `False`.
        *   `tool_config` (optionnel): Configuration des outils (ignoré pour DeepSeek, les outils sont définis globalement).
        *   `rag_context` (optionnel): Contexte RAG à injecter (dict ou str).
    *   **Retours**: Un générateur si `stream=True`, sinon une instance de `UniversalResponseWrapper`.
    *   **Logique interne**:
        1.  Récupère une clé API valide.
        2.  Construit le message utilisateur avec le `rag_context` préfixé, et l'ajoute à l'historique.
        3.  Prépare les en-têtes de la requête.
        4.  Convertit le `TOOLS_SCHEMA` global en format OpenAI si des outils natifs sont activés.
        5.  Construit le payload final en utilisant `_build_payload_messages`.
        6.  Sauvegarde le payload via `_save_payload_log`.
        7.  Effectue la requête POST vers l'API DeepSeek.
        8.  Gère les erreurs HTTP, rapporte au `key_manager`.
        9.  Marque la clé comme réussie.
        10. Si `stream=True`, retourne un générateur qui lit les chunks, gère les `reasoning_content` et `content`, détecte les `tool_calls` et les formate en `!native_tool` commands, accumule la réponse, loggue les métriques à la fin.
        11. Si `stream=False`, parse la réponse, gère les `tool_calls` en les formatant également, ajoute la réponse à l'historique, loggue les métriques (incluant le cache hit/miss) et retourne un `UniversalResponseWrapper`.
        12. Gère les exceptions générales en rapportant l'erreur au `key_manager`.

*   `@property`
    `chat(self)`
    Propriété pour fournir une interface de compatibilité avec l'historique de chat de l'API Gemini.

    *   **Retours**: Une instance de `ChatInterface` qui expose un attribut `history` et une méthode `rewind`.
    *   **Logique interne**: Encapsule l'historique interne de DeepSeek pour le rendre accessible et modifiable. `rewind` supprime le dernier message de l'historique.

#### `class GeminiSession`

Gère les interactions avec l'API Gemini de Google.

*   **Constructeur**: `__init__(self, key_manager, model_name="gemini-2.5-flash", agent_name=None, system_instruction=None, enable_tools=True, cache_name=None, safety_settings=None, fallback_models=None)`
    *   **Arguments**:
        *   `key_manager`: Instance du gestionnaire de clés API.
        *   `model_name` (`str`, optionnel): Nom du modèle Gemini.
        *   `agent_name` (`str`, optionnel): Nom de l'agent.
        *   `system_instruction` (`str`, optionnel): Instruction système.
        *   `enable_tools` (`bool`, optionnel): Active ou désactive l'utilisation des outils.
        *   `cache_name` (`str`, optionnel): Nom du cache à utiliser pour le modèle.
        *   `safety_settings` (optionnel): Paramètres de sécurité (non utilisé dans le code fourni).
        *   `fallback_models` (`list`, optionnel): Liste de modèles de secours en cas d'échec d'initialisation.
    *   **Logique interne**: Initialise les attributs et tente d'initialiser le chat via `_init_chat`. En cas d'échec, essaie les modèles de secours via `_try_fallback`.

*   `@trace_action(source="sessions")`
    `_init_chat(self, key=None)`
    Initialise ou réinitialise la session de chat avec l'API Gemini.

    *   **Arguments**:
        *   `key` (`str`, optionnel): Clé API à utiliser; si `None`, le `key_manager` est sollicité.
    *   **Retours**: `None`
    *   **Logique interne**:
        1.  Récupère une clé API valide.
        2.  Configure `genai` avec la clé.
        3.  Tente de récupérer un cache existant ou d'en créer un via `GlobalCacheManager`.
        4.  Initialise le modèle `genai.GenerativeModel` à partir du cache ou directement avec le nom du modèle, l'instruction système et les outils.
        5.  Démarre la session de chat (`model.start_chat`), en préservant l'historique si la session est réinitialisée.
        6.  Journalise l'initialisation.

*   `_try_fallback(self)`
    Tente de basculer vers les modèles de secours définis dans `fallback_models` si l'initialisation du modèle principal échoue.

    *   **Retours**: `bool` (`True` si une bascule réussit, `False` sinon).
    *   **Logique interne**:
        1.  Itère sur la liste `fallback_models`.
        2.  Met à jour `self.model_name` avec le modèle de secours.
        3.  Tente d'initialiser le chat avec le nouveau modèle.
        4.  Si l'initialisation réussit, retourne `True`.
        5.  Si toutes les tentatives échouent, retourne `False`.

*   `@trace_action(source="sessions")`
    `send_message(self, message, stream=False, tool_config=None, rag_context=None)`
    Envoie un message à l'API Gemini, gère les retries en cas de quota dépassé.

    *   **Arguments**:
        *   `message`: Le message utilisateur (peut être une chaîne ou un dictionnaire pour les réponses d'outils).
        *   `stream` (`bool`, optionnel): Si `True`, la réponse est un générateur de chunks.
        *   `tool_config` (optionnel): Configuration spécifique aux outils (ex: `{'function_calling_config': {'mode': 'none'}}`).
        *   `rag_context` (optionnel): Contexte RAG à injecter (dict ou str).
    *   **Retours**: Un générateur si `stream=True`, sinon une instance de `UniversalResponseWrapper`.
    *   **Logique interne**:
        1.  **Auto-Wrapping Tool Response**: Si le dernier message du modèle était un appel de fonction et que le message actuel est une chaîne, il est automatiquement enveloppé en `function_response`.
        2.  **Gestion du RAG Context**: Le `rag_context` est préfixé au message utilisateur.
        3.  **Construction du Payload de Log**: Similaire à DeepSeekSession, reconstruit et nettoie l'historique pour la journalisation, en intégrant les messages système (instructions, cache, LTM) et l'historique conversationnel.
        4.  Sauvegarde le payload via `_save_payload_log`.
        5.  Utilise une boucle `while` pour gérer les tentatives et la rotation de clés en cas d'erreur de quota.
        6.  Appelle `self.chat.send_message` de l'API Gemini.
        7.  **Gestion des Erreurs/Rotation de Clés**:
            *   Si l'erreur est un dépassement de quota, la clé actuelle est rapportée comme défectueuse au `key_manager`.
            *   Une nouvelle clé est tentée via `key_manager.get_key(exclude_key=...)`.
            *   La session est réinitialisée avec la nouvelle clé (`_init_chat`), et l'historique est "rembobiné" (`self.chat.rewind()`) pour retirer le message ayant échoué.
            *   Si aucune clé de remplacement n'est disponible, lève `QuotaExceededException`.
            *   Pour les autres erreurs, l'erreur est rapportée et propagée.
        8.  **Traitement de la Réponse**:
            *   Si `stream=False`, la réponse est traitée en une seule fois, les `tool_calls` sont extraits et formatés en `!native_tool` commandes. Les métriques sont logguées.
            *   Si `stream=True`, un générateur `stream_wrapper` est retourné, qui itère sur les chunks, extrait le texte et les `tool_calls`, gère les erreurs de flux et loggue les métriques à la fin du flux.

*   `@trace_action(source="sessions")`
    `_log_metrics(self, start_time, response)`
    Journalise les métriques d'utilisation des tokens pour une requête Gemini non-streamée.

    *   **Arguments**:
        *   `start_time`: Timestamp de début de la requête.
        *   `response`: L'objet de réponse de l'API Gemini.
    *   **Retours**: `None`
    *   **Logique interne**:
        1.  Calcule la durée.
        2.  Extrait les informations d'utilisation (`prompt_token_count`, `candidates_token_count`) de `response.usage_metadata`.
        3.  Utilise `TokenManager` pour ajouter l'utilisation.
        4.  Journalise les métriques via `UnifiedLogger`.

#### `class GeminiCliSession(BaseSession)`

Gère les interactions avec les modèles Gemini via l'outil CLI officiel `google-gemini/gemini-cli`. Permet l'utilisation de modèles gratuits via le CLI.

*   **Constructeur**: `__init__(self, key_manager, model_name="gemini-2.5-flash", system_instruction=None, agent_name=None)`
    *   **Arguments**:
        *   `key_manager`: Instance du gestionnaire de clés API (conservé pour compatibilité, mais non utilisé activement).
        *   `model_name` (`str`, optionnel): Nom du modèle Gemini à utiliser.
        *   `system_instruction` (`str`, optionnel): Instruction système initiale.
        *   `agent_name` (`str`, optionnel): Nom de l'agent.
    *   **Logique interne**:
        1.  Recherche le chemin de l'exécutable `gemini` CLI via `_find_gemini_cli`.
        2.  Lève `FatalKeyError` si le CLI n'est pas trouvé.
        3.  Initialise un environnement d'exécution isolé pour le CLI via `_init_cli_isolation`, afin de contrôler le prompt système et désactiver la mémoire hiérarchique du CLI.
        4.  Journalise l'activation du pont CLI.

*   `_get_cli_bridge_cfg(self)`
    Lit la configuration du pont CLI depuis `config.settings.APP_SETTINGS` avec des valeurs par défaut sécurisées.

    *   **Retours**: `dict` (Configuration structurée pour le pont CLI).
    *   **Logique interne**: Accède à `APP_SETTINGS` et consolide les paramètres pour l'isolation, les limites de prompt et les configurations de `system_md`. Gère la conversion de types et les valeurs par défaut.

*   `_init_cli_isolation(self)`
    Crée un répertoire de travail temporaire avec un fichier de configuration `.gemini/settings.json` et un fichier `.gemini/system.md` pour contrôler le comportement du CLI.

    *   **Retours**: `None`
    *   **Logique interne**:
        1.  Vérifie si l'isolation est activée dans la configuration.
        2.  Crée un répertoire temporaire et un sous-répertoire `.gemini`.
        3.  Génère le contenu du prompt système via `build_cli_system_md` et l'écrit dans `.gemini/system.md`.
        4.  Crée un fichier `.gemini/settings.json` pour désactiver la mémoire hiérarchique du CLI (`context.fileName` à un nom inexistant).
        5.  Crée un environnement (`_cli_env`) qui force le CLI à utiliser le fichier `system.md` via `GEMINI_SYSTEM_MD=1`.
        6.  Enregistre un hook `atexit` pour nettoyer le répertoire temporaire à la fin du programme.

*   `_find_gemini_cli(self)`
    Recherche le chemin complet de l'exécutable `gemini` CLI, en tenant compte des spécificités Windows (ex: `gemini.cmd`).

    *   **Retours**: `str` (Chemin complet du CLI) ou `None` si non trouvé.
    *   **Logique interne**:
        1.  Utilise `shutil.which` pour trouver `gemini`.
        2.  Sur Windows, vérifie également `gemini.cmd`, `gemini.exe`, `gemini.ps1` et les chemins NPM standards.

*   `_create_msg(self, role, text)`
    Fonction utilitaire pour créer un message au format dictionnaire (`{"role": role, "content": text}`).

    *   **Arguments**:
        *   `role` (`str`): Rôle du message ("user", "assistant", "system").
        *   `text` (`str`): Contenu du message.
    *   **Retours**: `dict` (Le message formaté).

*   `_build_full_prompt(self, message, rag_context=None)`
    Construit le prompt complet pour le CLI en combinant le message utilisateur, le contexte RAG, l'historique et les composants de cache. *Note: Cette fonction est remplacée par une logique plus détaillée dans `send_message` pour gérer `stdin` et `--prompt`.*

    *   **Arguments**:
        *   `message`: Message utilisateur.
        *   `rag_context` (optionnel): Contexte RAG.
    *   **Retours**: `str` (Le prompt complet).
    *   **Logique interne**: Utilise `ai_core.prompt_builders.build_cli_prompt` pour assembler le prompt.

*   `@trace_action(source="sessions")`
    `send_message(self, message, stream=False, tool_config=None, rag_context=None)`
    Envoie un message via le CLI `gemini`.

    *   **Arguments**:
        *   `message`: Message utilisateur à envoyer.
        *   `stream` (`bool`, optionnel): Si `True`, la réponse est un générateur de lignes (streaming).
        *   `tool_config` (optionnel): Ignoré car le CLI ne supporte pas les outils.
        *   `rag_context` (optionnel): Contexte RAG à injecter.
    *   **Retours**: Un générateur si `stream=True`, sinon une instance de `UniversalResponseWrapper`.
    *   **Logique interne**:
        1.  Récupère la configuration du pont CLI.
        2.  **Construction du prompt CLI**: Utilise `build_cli_prompt` pour diviser le prompt en une partie pour `stdin` (contexte, historique) et une partie pour l'argument `--prompt` (le message utilisateur tronqué), contournant la limite de longueur des arguments Windows.
        3.  **Construction du Payload de Log**: Reconstruit un payload détaillé pour la journalisation, similaire aux autres sessions, incluant les messages système (arch, tree, ltm, rag) et l'historique nettoyé, plus le message utilisateur final.
        4.  Sauvegarde le payload CLI via `_save_payload_log`.
        5.  Construit la commande `subprocess`.
        6.  Journalise le début de la génération et un aperçu du prompt.
        7.  **Exécution du CLI**:
            *   Si `stream=True`, lance `subprocess.Popen` pour un contrôle fin de `stdin`, `stdout` et `stderr`. Envoie la partie `stdin_prompt` via `stdin`, puis lit `stdout` ligne par ligne via un générateur.
            *   Si `stream=False`, utilise `subprocess.run` pour attendre la fin de l'exécution et capturer la sortie complète.
        8.  Gère les codes de retour non nuls et les erreurs `stderr` du CLI (y compris les erreurs d'authentification).
        9.  Ajoute les messages utilisateur et assistant à l'historique interne.
        10. Journalise la fin de la génération et la durée.
        11. Retourne la réponse enveloppée dans un `UniversalResponseWrapper`.
        12. Gère les exceptions `subprocess.TimeoutExpired` et `FileNotFoundError`.

*   `@property`
    `chat(self)`
    Propriété pour fournir une interface de compatibilité avec l'historique de chat de l'API Gemini.

    *   **Retours**: Une instance de `ChatInterface` qui expose un attribut `history` et une méthode `rewind`.
    *   **Logique interne**: Encapsule l'historique interne du CLI pour le rendre accessible et modifiable. `rewind` supprime le dernier message de l'historique.

### Fonction Principale

#### `@trace_action(source="sessions")`
`call_ai_robust(session_or_agent, prompt, mode="fast", disposable=False, force_text=False, cache_name=None, stream=False, rag_context=None)`

Fonction utilitaire de haut niveau pour appeler l'IA de manière robuste, en gérant la session, les modes, le caractère jetable de l'historique, les options de streaming et l'intégration du contexte RAG.

*   **Arguments**:
    *   `session_or_agent`: Peut être une instance de session (`GeminiSession`, `DeepSeekSession`, etc.) ou un objet `Agent` ayant un attribut `session`.
    *   `prompt`: Le message (prompt) à envoyer à l'IA.
    *   `mode` (`str`, optionnel): Mode de la session (ex: "fast", "creative"). Utilisé si une nouvelle session doit être créée. Par défaut: "fast".
    *   `disposable` (`bool`, optionnel): Si `True`, l'historique de la session est sauvegardé avant l'appel et restauré après, rendant l'interaction "jetable" pour l'historique. Par défaut: `False`.
    *   `force_text` (`bool`, optionnel): Si `True`, configure la session pour forcer une réponse textuelle (désactive l'appel de fonction/outil). Par défaut: `False`.
    *   `cache_name` (`str`, optionnel): Nom du cache à utiliser pour la session.
    *   `stream` (`bool`, optionnel): Si `True`, la réponse sera un générateur de chunks. Par défaut: `False`.
    *   `rag_context` (optionnel): Contexte RAG à injecter.
*   **Retours**: Un générateur si `stream=True`, sinon une chaîne de caractères (le texte de la réponse). En cas d'erreur avec `stream=True`, un itérateur vide est retourné pour éviter de planter le consommateur.
*   **Logique interne**:
    1.  Récupère l'objet `session` à partir de `session_or_agent` ou crée une nouvelle session via `SessionFactory.create_session` si `session_or_agent` n'est pas une session directe.
    2.  Configure `tool_config` pour désactiver l'appel de fonction si `force_text` est `True`.
    3.  Si `disposable` est `True`, sauvegarde l'historique actuel de la session.
    4.  Appelle `session.send_message` avec le `prompt`, les options de `stream`, `tool_config` et `rag_context`.
    5.  Si `disposable` est `True`, restaure l'historique de la session.
    6.  Retourne la réponse (ou le générateur) de l'IA.
    7.  En cas d'erreur, journalise l'exception. Si `stream=True`, retourne un itérateur vide, sinon un message d'erreur.

## 3. Exemple d'usage

```python
import os
from unittest.mock import MagicMock
from config.settings import APP_SETTINGS
from ai_core.sessions import call_ai_robust, GeminiSession, DeepSeekSession, GroqSession, GeminiCliSession, FatalKeyError

# --- Préparation (simuler le KeyManager et APP_SETTINGS pour l'exemple) ---
class MockKeyManager:
    def __init__(self):
        self.keys = {
            "gemini-2.5-flash": ["GEMINI_KEY_1", "GEMINI_KEY_2"],
            "deepseek-chat": ["DEEPSEEK_KEY_1"],
            "llama3-70b-8192": ["GROQ_KEY_1"],
        }
        self.health = {k: 1.0 for model_keys in self.keys.values() for k in model_keys}

    def get_key(self, model_name, exclude_key=None):
        for k in self.keys.get(model_name, []):
            if k != exclude_key and self.health.get(k, 0) > 0:
                return k
        return None

    def report_error(self, key, exception, model_name):
        print(f"KeyManager: Erreur sur {key} pour {model_name}: {exception}. Santé réduite.")
        self.health[key] = 0 # Désactive la clé pour l'exemple

    def mark_success(self, key, model_name):
        print(f"KeyManager: Succès sur {key} pour {model_name}. Santé restaurée.")
        self.health[key] = 1.0 # Restaure la santé

    @property
    def num_keys(self):
        return sum(len(v) for v in self.keys.values())

# Mock GlobalCacheManager
class MockGlobalCacheManager:
    def get_components(self):
        return {
            "repo_map": "--- CARTOGRAPHIE TECHNIQUE ---\nVotre projet est un système de gestion de tâches.",
            "tree": "--- ARBORESCENCE PROJET ---\n.git/\nsrc/\n  main.py",
            "ltm": "--- MÉMOIRE LONG TERME ---\nLa dernière tâche était de refactoriser le module de log."
        }
    def get_or_create_cache(self, key, model_name):
        return f"cache_{model_name}_{key[-6:]}"

# Injecter les mocks dans les globales (nécessaire pour les imports paresseux dans le code réel)
import sys
sys.modules['features.TokenManager'] = MagicMock()
sys.modules['features.CacheManager'] = MagicMock()
sys.modules['features.CacheManager'].GlobalCacheManager = MockGlobalCacheManager()

key_manager = MockKeyManager()

# Simuler la configuration de l'application
APP_SETTINGS["cli_bridge"] = {
    "isolation": {"enabled": True},
    "max_history_turns": 3,
    "prompt_limits": {
        "total": 24000, "arch": 7000, "tree": 7000, "ltm": 4000, "rag": 8000, "history": 6000, "message": 6000
    },
    "system_md": {"language": "fr", "extra": "Soyez concis."},
}
APP_SETTINGS["ui_settings"] = {"language": "fr"}
APP_SETTINGS["system_settings"] = {"debug_mode": True}

# --- 1. Utilisation de base avec Gemini (non streamé) ---
print("--- TEST GEMINI STANDARD ---")
gemini_session = GeminiSession(key_manager, model_name="gemini-2.5-flash", system_instruction="Vous êtes un assistant IA utile.")
try:
    response = call_ai_robust(gemini_session, "Bonjour, quel est votre modèle?", stream=False)
    print(f"Réponse Gemini: {response[:100]}...")
except FatalKeyError as e:
    print(f"Erreur fatale Gemini: {e}")
except Exception as e:
    print(f"Erreur générale Gemini: {e}")

# --- 2. Utilisation de DeepSeek avec RAG (streamé) ---
print("\n--- TEST DEEPSEEK AVEC RAG STREAMING ---")
deepseek_session = DeepSeekSession(key_manager, model_name="deepseek-chat", system_instruction="Vous êtes un expert en Python.")
rag_data = {
    "docs": "Le module 'requests' est utilisé pour les requêtes HTTP. La fonction 'get' est utilisée pour récupérer des données."
}
try:
    print("Réponse DeepSeek (streaming):")
    stream_response = call_ai_robust(deepseek_session, "Comment faire une requête HTTP en Python?", stream=True, rag_context=rag_data)
    full_response = ""
    for chunk in stream_response:
        print(chunk, end='')
        full_response += chunk
    print("\n--- Fin du stream DeepSeek ---")
except FatalKeyError as e:
    print(f"Erreur fatale DeepSeek: {e}")
except Exception as e:
    print(f"Erreur générale DeepSeek: {e}")


# --- 3. Utilisation de Groq avec historique jetable ---
print("\n--- TEST GROQ AVEC HISTORIQUE JETABLE ---")
groq_session = GroqSession(key_manager, model_name="llama3-70b-8192", system_instruction="Vous êtes un codeur junior.")
try:
    # Premier message pour établir l'historique
    groq_session.send_message("Initialisez la conversation", stream=False)
    print(f"Historique Groq avant jetable: {len(groq_session.history)} messages")

    # Message jetable
    disposable_response = call_ai_robust(groq_session, "Quelle est la date d'aujourd'hui? (réponse courte)", disposable=True)
    print(f"Réponse Groq jetable: {disposable_response[:100]}...")
    print(f"Historique Groq après jetable: {len(groq_session.history)} messages (devrait être le même qu'avant)")

    # Nouveau message pour vérifier que l'historique n'a pas été affecté
    response_after_disposable = call_ai_robust(groq_session, "Quel est mon nom?", stream=False)
    print(f"Réponse Groq après jetable: {response_after_disposable[:100]}...")
except FatalKeyError as e:
    print(f"Erreur fatale Groq: {e}")
except Exception as e:
    print(f"Erreur générale Groq: {e}")

# --- 4. Utilisation de Gemini CLI (si le CLI est installé) ---
print("\n--- TEST GEMINI CLI ---")
try:
    # On mock subprocess pour ne pas exécuter réellement le CLI dans un environnement de test
    # Dans un environnement réel, retirez ces lignes de mock
    from unittest.mock import patch
    with patch('subprocess.run') as mock_run, \
         patch('subprocess.Popen') as mock_popen, \
         patch('shutil.which', return_value='/usr/local/bin/gemini'): # Simule que gemini est dans le PATH

        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Bonjour ! Je suis le modèle Gemini CLI."
        mock_run.return_value.stderr = ""

        mock_stdout = MagicMock()
        mock_stdout.__iter__.return_value = ["Bonjour !", " Je suis le modèle Gemini CLI."]
        mock_popen.return_value.stdout = mock_stdout
        mock_popen.return_value.stderr = MagicMock()
        mock_popen.return_value.stderr.read.return_value = ""
        mock_popen.return_value.wait.return_value = 0
        mock_popen.return_value.stdin = MagicMock() # Mock stdin
        mock_popen.return_value.stdin.write.return_value = None
        mock_popen.return_value.stdin.close.return_value = None


        gemini_cli_session = GeminiCliSession(key_manager, model_name="gemini-1.5-flash")
        
        # Test non streamé
        cli_response_non_stream = call_ai_robust(gemini_cli_session, "Quel est le but de la vie?", stream=False)
        print(f"Réponse Gemini CLI (non streamée): {cli_response_non_stream[:100]}...")

        # Test streamé
        print("Réponse Gemini CLI (streamée):")
        cli_stream_response = call_ai_robust(gemini_cli_session, "Décrivez votre fonctionnement.", stream=True)
        full_cli_stream_response = ""
        for chunk in cli_stream_response:
            print(chunk, end='')
            full_cli_stream_response += chunk
        print("\n--- Fin du stream Gemini CLI ---")

except FatalKeyError as e:
    print(f"Erreur fatale Gemini CLI: {e}\nAssurez-vous que le CLI 'gemini' est installé et authentifié.")
except Exception as e:
    print(f"Erreur générale Gemini CLI: {e}")

# Nettoyage des mocks si nécessaire
del sys.modules['features.TokenManager']
del sys.modules['features.CacheManager']