# Documentation Technique du Fichier `config/settings.py`

Ce fichier Python est le cœur de la gestion de la configuration de l'application. Il centralise les paramètres par défaut, les chemins de fichiers essentiels, et fournit des utilitaires pour charger, sauvegarder et recharger les configurations. Il permet de gérer dynamiquement les préférences utilisateur, les clés d'API, les paramètres des modèles d'IA, les configurations de sécurité et divers réglages opérationnels.

## Dépendances

*   `os`: Pour les opérations de chemin de fichier et de répertoire.
*   `json`: Pour la sérialisation et désérialisation des fichiers de configuration JSON.
*   `logging`: Implicitement utilisé pour la configuration des canaux de journalisation.
*   `pathlib.Path`: Utilisé pour la manipulation de chemins (bien que `os.path` soit majoritairement utilisé).

## Constantes Globales & Variables

Cette section détaille les constantes et variables globales définies dans le fichier, qui représentent la configuration par défaut et les chemins de ressources de l'application.

---

### `PERMISSIVE_SAFETY_SETTINGS`

*   **Type**: `list[dict]`
*   **Description**: Définit un ensemble de paramètres de sécurité permissifs pour les modèles d'IA. Chaque dictionnaire spécifie une catégorie de contenu potentiellement dangereux (`category`) et un seuil de blocage (`threshold`). Ici, toutes les catégories sont définies sur `"BLOCK_NONE"`, ce qui signifie qu'aucun contenu n'est bloqué par ces seuils.

---

### `DEFAULT_SETTINGS`

*   **Type**: `dict`
*   **Description**: Le dictionnaire de configuration par défaut complet de l'application. Il contient toutes les sections et sous-sections de paramètres possibles avec leurs valeurs initiales.

    *   **`safety_settings`** (`list`): Voir `PERMISSIVE_SAFETY_SETTINGS`.
    *   **`api_keys`** (`dict`): Clés d'API pour différents fournisseurs de modèles d'IA. Inclut `google_gemini`, `deepseek`, `openai`, `anthropic`, `mistral`, `groq`, `openrouter`, `huggingface`.
    *   **`ai_engine`** (`dict`): Configuration par défaut du moteur d'IA.
        *   `provider`: Fournisseur d'IA par défaut (`google_gemini`).
        *   `model`: Modèle par défaut (`gemini-2.5-flash`).
        *   `temperature`: Température de génération du modèle.
        *   `max_tokens`: Nombre maximal de tokens pour la réponse.
        *   `available_models`: Liste des modèles disponibles (généralement peuplée dynamiquement).
        *   `cloud_models_registry`: Mapping de profils génériques (e.g., "fast", "smart", "coder") vers des noms de modèles spécifiques.
    *   **`security`** (`dict`): Paramètres liés à la sécurité et à l'isolation du projet.
        *   `enable_sanity_check`: Active/désactive les vérifications de cohérence.
        *   `block_outside_project`: Empêche l'accès aux fichiers en dehors du répertoire du projet.
        *   `protected_directories`: Liste des répertoires sensibles à protéger.
        *   `protected_files`: Liste des fichiers sensibles à protéger.
    *   **`system_settings`** (`dict`): Paramètres généraux du système.
        *   `theme`, `font_size`: Options d'interface utilisateur.
        *   `auto_backup`, `backup_interval`, `max_backups`: Paramètres de sauvegarde automatique.
        *   `rag_enabled`, `rag_database_path`: Paramètres pour la Récupération Augmentée par Génération (RAG).
        *   `max_history_retention`: Nombre maximal d'entrées d'historique à conserver.
    *   **`general_settings`** (`dict`): Réglages opérationnels généraux.
        *   `chat_pool_size`, `secondary_chat_pool_size`: Nombre de sessions de chat parallèles.
        *   `api_cooldown_seconds`: Délai entre les appels API.
        *   `audit_interval_seconds`: Intervalle pour les audits internes.
    *   **`cli_bridge`** (`dict`): Configuration pour le pont avec l'interface en ligne de commande (CLI).
        *   `enabled`: Active/désactive le CLI.
        *   `models`: Modèles spécifiques à utiliser pour le CLI.
        *   `max_history_turns`: Nombre d'échanges (user+assistant) à inclure.
        *   `prompt_limits`: Limites de caractères pour différentes sections du prompt CLI.
        *   `isolation`: Paramètres d'isolation pour le CLI (ex: désactiver les fichiers de contexte).
        *   `system_md`: Options additionnelles pour le prompt système.
    *   **`agents_config`** (`dict`): Configuration spécifique aux agents.
        *   `react_max_steps_cloud`: Nombre maximal d'étapes pour les agents basés sur le framework ReAct.
        *   `active_agents`: Liste des agents actifs.
    *   **`swarm_settings`** (`dict`): Paramètres pour le mode swarm multi-agents.
        *   `mode`: Mode du swarm (ex: "hierarchical").
        *   `autonomy_level`: Niveau d'autonomie (ex: "supervised").
        *   `role_mapping`: Mapping des rôles d'agents vers des profils de modèles spécifiques.
        *   `max_auto_loop`: Nombre maximal d'itérations automatiques.
    *   **`key_bindings`** (`dict`): Raccourcis clavier pour l'interface utilisateur.
    *   **`logging_channels`** (`dict`): Active/désactive des canaux de journalisation spécifiques (ex: `SYSTEM`, `WORKER`, `MEMORY`).
    *   **`automation`** (`dict`): Intervalles pour les tâches d'automatisation.
        *   `arch_update_interval`: Intervalle de mise à jour de l'architecture.
        *   `auto_backup_interval`: Intervalle de sauvegarde automatique.

---

### Chemins de Fichiers

Un ensemble de constantes définit les chemins absolus vers les fichiers et répertoires cruciaux de l'application.

*   **`BASE_DIR`** (`str`): Le répertoire de base de l'application. Déterminé par le répertoire du script.
*   **`SETTINGS_FILE`** (`str`): Chemin vers le fichier JSON `app_settings.json` où les paramètres de l'utilisateur sont stockés.

#### Chemins des Données Principales

*   **`HISTORY_FILE`**: Fichier JSON pour l'historique principal des conversations.
*   **`OLD_HISTORY_FILE`**: Fichier JSON pour l'ancien historique des conversations (sauvegarde ou archivage).
*   **`ACTION_LOG_FILE`**: Fichier JSON pour les journaux d'actions.
*   **`SYNTHESIS_FILE`**: Fichier Markdown pour les journaux de synthèse.
*   **`CONTEXT_FILE`**: Fichier JSON pour le contexte du projet.
*   **`KEY_STATUS_FILE`**: Fichier JSON pour le statut des clés d'API.
*   **`TOKEN_USAGE_FILE`**: Fichier JSON pour le suivi de l'utilisation des tokens.

#### Chemins Secondaires

Des chemins similaires sont définis avec le préfixe `SECONDARY_` pour gérer un ensemble de données auxiliaires, potentiellement pour un deuxième contexte ou une deuxième session de travail.

*   **`SECONDARY_HISTORY_FILE`**, **`SECONDARY_OLD_HISTORY_FILE`**, etc.

#### Chemins de la Feuille de Route (Roadmap)

*   **`ROADMAP_FILE`**: Fichier Markdown pour la feuille de route du projet.
*   **`FULL_ROADMAP_FILE`**: Fichier Markdown pour la version complète de la feuille de route.
*   **`ROADMAP_BACKUP_DIR`**: Répertoire pour les sauvegardes de la feuille de route.

#### Chemins RAG / Drive

*   **`KB_DATABASE_FILE`**: Nom du fichier de la base de connaissances (pour RAG).
*   **`KB_DRIVE_FOLDER_NAME`**: Nom du dossier Google Drive pour la base de connaissances.
*   **`KB_DRIVE_FILE_ID_CACHE`**: Fichier cache pour l'ID du dossier Drive.
*   **`KB_ZIP_NAME`**: Nom du fichier ZIP de la base de connaissances.
*   **`SECONDARY_KB_*`**: Chemins équivalents pour une base de connaissances secondaire.

#### Chemins Google Drive Auth

*   **`GDRIVE_SCOPES`** (`list`): Permissions requises pour l'API Google Drive.
*   **`GDRIVE_TOKEN_FILE`**: Fichier JSON pour le token d'authentification Google Drive.
*   **`GDRIVE_CREDS_FILE`**: Fichier JSON pour les identifiants de l'application Google Drive.

---

### Constantes Opérationnelles

*   **`APP_TO_BACKUP`** (`str`): Le répertoire principal à sauvegarder (alias de `BASE_DIR`).
*   **`BACKUP_DIR`** (`str`): Répertoire où les sauvegardes seront stockées.
*   **`BACKUP_INTERVAL_MINUTES`** (`int`): Intervalle par défaut des sauvegardes automatiques en minutes.
*   **`MAX_BACKUPS_TO_KEEP`** (`int`): Nombre maximal de sauvegardes à conserver.
*   **`MAX_SEARCH_RESULTS`** (`int`): Nombre maximal de résultats de recherche à afficher.

---

### Variables Globales Modifiables

Ces variables sont initialisées avec des valeurs par défaut mais peuvent être mises à jour dynamiquement via les paramètres chargés.

*   **`API_COOLDOWN_SECONDS`** (`float`): Délai d'attente entre les appels d'API, en secondes.
*   **`AUDIT_INTERVAL_SECONDS`** (`float`): Intervalle d'audit interne, en secondes.

---

### `APP_SETTINGS`

*   **Type**: `dict`
*   **Description**: La variable globale qui stocke les paramètres actuellement chargés de l'application. Elle est initialisée au démarrage en appelant `load_app_settings()`. Tous les composants de l'application devraient accéder à cette variable pour obtenir les réglages en cours.

---

### `LOGGING_CHANNELS`

*   **Type**: `dict`
*   **Description**: Indique si chaque canal de journalisation est actif ou non (True/False). Initialisé à partir de `APP_SETTINGS`, ou utilise les valeurs par défaut.

---

### `LOG_SOURCE_MAP`

*   **Type**: `dict`
*   **Description**: Mapping des préfixes de noms de modules (sources de logs) vers des canaux de journalisation spécifiques (ex: "SYSTEM", "WORKER"). Utilisé par le système de journalisation pour acheminer les messages vers les canaux appropriés et appliquer les filtres définis dans `LOGGING_CHANNELS`.

## Fonctions de Gestion

Cette section décrit les fonctions utilitaires pour interagir avec les paramètres de l'application et les fichiers JSON.

---

### `load_app_settings()`

*   **Signature**: `load_app_settings()`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - Le dictionnaire des paramètres chargés et fusionnés.
*   **Logique Interne**:
    1.  Vérifie l'existence du fichier `SETTINGS_FILE`.
    2.  Si le fichier existe:
        *   Tente de charger son contenu JSON.
        *   Fusionne les paramètres chargés avec `DEFAULT_SETTINGS`. Les valeurs du fichier `SETTINGS_FILE` remplacent celles de `DEFAULT_SETTINGS` pour les clés existantes. De nouvelles sections ou clés dans le fichier de l'utilisateur sont ajoutées.
        *   Gère une conversion de format si une ancienne clé `api_keys_list` est trouvée, la transformant en format `api_keys` actuel.
        *   Met à jour les variables globales `API_COOLDOWN_SECONDS` et `AUDIT_INTERVAL_SECONDS` avec les valeurs des paramètres chargés.
        *   En cas d'erreur de lecture (fichier corrompu, etc.), imprime un message d'erreur et retourne une copie de `DEFAULT_SETTINGS`.
    3.  Si le fichier n'existe pas:
        *   Appelle `save_app_settings()` pour créer le fichier avec les `DEFAULT_SETTINGS`.
        *   Retourne une copie de `DEFAULT_SETTINGS`.

---

### `save_app_settings(new_settings=None)`

*   **Signature**: `save_app_settings(new_settings=None)`
*   **Arguments**:
    *   `new_settings` (`dict`, optionnel): Le dictionnaire de paramètres à sauvegarder. Si `None`, la fonction utilise la variable globale `APP_SETTINGS`.
*   **Retours**: `bool` - `True` si la sauvegarde est réussie, `False` sinon.
*   **Logique Interne**:
    1.  Détermine les données à sauvegarder (`new_settings` ou `APP_SETTINGS`).
    2.  Crée le répertoire parent du `SETTINGS_FILE` si nécessaire (`exist_ok=True`).
    3.  Tente d'écrire les données au format JSON (indenté, sans caractères ASCII forcés) dans le `SETTINGS_FILE`.
    4.  En cas d'erreur pendant la sauvegarde, imprime un message d'erreur et retourne `False`.

---

### `reload_app_settings()`

*   **Signature**: `reload_app_settings()`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - La variable globale `APP_SETTINGS` rechargée.
*   **Logique Interne**:
    1.  Appelle `load_app_settings()` pour obtenir une nouvelle version des paramètres.
    2.  Vide la variable globale `APP_SETTINGS`.
    3.  Met à jour `APP_SETTINGS` avec les nouveaux paramètres chargés.
    4.  Retourne la variable `APP_SETTINGS` mise à jour.

---

### `get_default_settings()`

*   **Signature**: `get_default_settings()`
*   **Arguments**: Aucun.
*   **Retours**: `dict` - Une copie des paramètres par défaut (`DEFAULT_SETTINGS`).
*   **Logique Interne**: Retourne simplement une copie des `DEFAULT_SETTINGS` pour éviter les modifications directes de la constante.

---

### `charger_json_robuste(chemin, default=None)`

*   **Signature**: `charger_json_robuste(chemin, default=None)`
*   **Arguments**:
    *   `chemin` (`str`): Le chemin du fichier JSON à charger.
    *   `default` (`any`, optionnel): La valeur à retourner si le fichier n'existe pas ou si une erreur survient lors du chargement. Par défaut, un dictionnaire vide `{}`.
*   **Retours**: `dict` ou `default` - Le contenu JSON chargé, ou la valeur par défaut.
*   **Logique Interne**:
    1.  Vérifie si le fichier existe. Si non, retourne la valeur par défaut.
    2.  Tente d'ouvrir et de lire le fichier JSON.
    3.  En cas d'erreur (ex: fichier malformé), retourne la valeur par défaut.

---

### `sauvegarder_json(chemin, data)`

*   **Signature**: `sauvegarder_json(chemin, data)`
*   **Arguments**:
    *   `chemin` (`str`): Le chemin où sauvegarder le fichier JSON.
    *   `data` (`any`): Les données Python à sérialiser en JSON.
*   **Retours**: `bool` - `True` si la sauvegarde est réussie, `False` sinon.
*   **Logique Interne**:
    1.  Tente d'écrire les `data` au format JSON (indenté, sans caractères ASCII forcés) dans le fichier spécifié par `chemin`.
    2.  Retourne `True` en cas de succès, `False` en cas d'erreur.

---

### Fonctions Wrapper pour les Workers

Ces fonctions sont des wrappers simplifiés autour de `charger_json_robuste` et `sauvegarder_json`, adaptées pour des cas d'usage spécifiques des "workers" (agents ou processus secondaires).

*   **`charger_historique_robuste_worker(fp)`**: Charge un fichier d'historique JSON, avec un défaut de liste vide `[]`.
*   **`sauvegarder_historique_worker(fp, h)`**: Sauvegarde un historique dans un fichier JSON.
*   **`charger_liens_contexte_worker(fp)`**: Charge un fichier de liens de contexte JSON, avec un défaut de dictionnaire vide `{}`.
*   **`sauvegarder_liens_contexte_worker(fp, l)`**: Sauvegarde des liens de contexte dans un fichier JSON.

## Initialisation

Le fichier s'auto-initialise en chargeant les paramètres dès son exécution:

```python
APP_SETTINGS = load_app_settings()
```

Ceci garantit que `APP_SETTINGS` est toujours peuplé avec la configuration actuelle de l'application lorsqu'un autre module importe `config.settings`.

## Exemple d'usage

Pour accéder aux paramètres de l'application ou les modifier :

```python
# Importez les paramètres
from config import settings

# Accéder à un paramètre
current_theme = settings.APP_SETTINGS["system_settings"]["theme"]
print(f"Thème actuel : {current_theme}")

# Accéder à une clé d'API
google_api_key = settings.APP_SETTINGS["api_keys"]["google_gemini"]
print(f"Clé Google Gemini : {google_api_key[:5]}...")

# Modifier un paramètre (cela ne le sauvegarde pas automatiquement sur le disque)
settings.APP_SETTINGS["system_settings"]["font_size"] = 14
print(f"Nouvelle taille de police : {settings.APP_SETTINGS['system_settings']['font_size']}")

# Pour sauvegarder les modifications sur le disque
if settings.save_app_settings():
    print("Paramètres sauvegardés avec succès.")
else:
    print("Échec de la sauvegarde des paramètres.")

# Pour recharger les paramètres depuis le fichier (par exemple, après une modification manuelle externe)
settings.reload_app_settings()
print(f"Paramètres rechargés. Taille de police après rechargement : {settings.APP_SETTINGS['system_settings']['font_size']}")

# Accéder à une variable globale mise à jour par les settings
api_cooldown = settings.API_COOLDOWN_SECONDS
print(f"Cooldown API : {api_cooldown} secondes.")

# Utilisation des fonctions de sauvegarde/chargement robustes
data = {"clé": "valeur", "liste": [1, 2, 3]}
test_file = os.path.join(settings.BASE_DIR, "test_data.json")

if settings.sauvegarder_json(test_file, data):
    print(f"Données sauvegardées dans {test_file}")
    loaded_data = settings.charger_json_robuste(test_file)
    print(f"Données chargées : {loaded_data}")
    os.remove(test_file) # Nettoyage