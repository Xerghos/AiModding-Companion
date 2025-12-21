# Documentation Technique : `config/__init__.py`

## Description Concise

Ce fichier sert de point d'entrée principal pour le package de configuration. Il expose les fonctions et les constantes importantes définies dans les modules enfants (`paths`, `logs`, `settings`, `constants`), permettant une importation plus facile des configurations et des paramètres de l'application dans d'autres parties du projet. Il gère également l'initialisation de certaines variables dérivées basées sur les paramètres chargés.

## Dépendances

Ce module dépend des modules internes suivants :
- `config.paths`
- `config.logs`
- `config.settings`
- `config.constants`

Il n'y a pas de dépendances externes déclarées directement dans ce fichier.

---

## Classes & Fonctions

### 1. `get_path(name: str, create: bool = False) -> str`

*   **Description :** Renvoie le chemin absolu d'un fichier ou répertoire de configuration prédéfini, basé sur son nom. Permet optionnellement de créer le répertoire s'il n'existe pas.
*   **Arguments :**
    *   `name` (str) : Le nom du fichier ou répertoire de configuration à récupérer (par exemple, "settings", "logs").
    *   `create` (bool, optionnel) : Si `True`, crée le répertoire parent du chemin demandé s'il n'existe pas. La valeur par défaut est `False`.
*   **Retour :**
    *   `str` : Le chemin absolu du fichier ou répertoire demandé.
*   **Logique interne :** Appelle la fonction `get_path` du module `config.paths`.

### 2. `get_logger(name: str)`

*   **Description :** Renvoie une instance de logger configurée pour une tâche ou un module spécifique.
*   **Arguments :**
    *   `name` (str) : Le nom du logger à obtenir. Ce nom est généralement utilisé pour identifier la source des logs.
*   **Retour :**
    *   Instance de logger Python standard.
*   **Logique interne :** Appelle la fonction `get_logger` du module `config.logs`.

### 3. `load_app_settings()`

*   **Description :** Charge les paramètres de l'application à partir d'un fichier de configuration (généralement `SETTINGS_FILE`). Ces paramètres sont ensuite stockés dans la variable globale `APP_SETTINGS`.
*   **Arguments :** Aucun.
*   **Retour :** `None`. Modifie `APP_SETTINGS` en place.
*   **Logique interne :** Appelle la fonction `load_app_settings` du module `config.settings`.

### 4. `save_app_settings(settings: dict)`

*   **Description :** Sauvegarde les paramètres de l'application dans le fichier de configuration `SETTINGS_FILE`.
*   **Arguments :**
    *   `settings` (dict) : Un dictionnaire contenant les paramètres de l'application à sauvegarder.
*   **Retour :** `None`.
*   **Logique interne :** Appelle la fonction `save_app_settings` du module `config.settings`.

### 5. `get_default_settings()`

*   **Description :** Renvoie un dictionnaire représentant les paramètres par défaut de l'application.
*   **Arguments :** Aucun.
*   **Retour :**
    *   `dict` : Dictionnaire des paramètres par défaut.
*   **Logique interne :** Appelle la fonction `get_default_settings` du module `config.settings`.

### 6. Constantes exposées :

Les constantes suivantes sont directement importées du module `config.settings` et `config.constants` et exposées pour un accès facile.

*   **`APP_SETTINGS`** (`dict`) : Dictionnaire contenant les paramètres de l'application actuellement chargés. Initialisé comme un dictionnaire vide et généralement peuplé par `load_app_settings()`.
*   **`SETTINGS_FILE`** (`str`) : Chemin du fichier où sont stockés les paramètres de l'application.
*   **`HISTORY_FILE`** (`str`) : Chemin du fichier d'historique principal.
*   **`OLD_HISTORY_FILE`** (`str`) : Chemin du fichier d'ancien historique principal.
*   **`ACTION_LOG_FILE`** (`str`) : Chemin du fichier de log des actions principal.
*   **`SYNTHESIS_FILE`** (`str`) : Chemin du fichier de synthèse principal.
*   **`CONTEXT_FILE`** (`str`) : Chemin du fichier de contexte principal.
*   **`KEY_STATUS_FILE`** (`str`) : Chemin du fichier d'état des clés.
*   **`SECONDARY_HISTORY_FILE`** (`str`) : Chemin du fichier d'historique secondaire.
*   **`SECONDARY_OLD_HISTORY_FILE`** (`str`) : Chemin du fichier d'ancien historique secondaire.
*   **`SECONDARY_ACTION_LOG_FILE`** (`str`) : Chemin du fichier de log des actions secondaire.
*   **`SECONDARY_SYNTHESIS_FILE`** (`str`) : Chemin du fichier de synthèse secondaire.
*   **`SECONDARY_CONTEXT_FILE`** (`str`) : Chemin du fichier de contexte secondaire.
*   **`ROADMAP_FILE`** (`str`) : Chemin du fichier de roadmap principal.
*   **`FULL_ROADMAP_FILE`** (`str`) : Chemin du fichier de roadmap complet.
*   **`ROADMAP_BACKUP_DIR`** (`str`) : Chemin du répertoire de sauvegarde pour les roadmaps.
*   **`KB_DATABASE_FILE`** (`str`) : Chemin du fichier de base de données Knowledge Base (KB) principal.
*   **`KB_DRIVE_FOLDER_NAME`** (`str`) : Nom du dossier Google Drive pour la KB principale.
*   **`KB_DRIVE_FILE_ID_CACHE`** (`str`) : Chemin du cache des ID de fichiers Google Drive pour la KB principale.
*   **`KB_ZIP_NAME`** (`str`) : Nom du fichier zip pour la KB.
*   **`SECONDARY_KB_DATABASE_FILE`** (`str`) : Chemin du fichier de base de données Knowledge Base (KB) secondaire.
*   **`SECONDARY_KB_DRIVE_FOLDER_NAME`** (`str`) : Nom du dossier Google Drive pour la KB secondaire.
*   **`SECONDARY_KB_DRIVE_FILE_ID_CACHE`** (`str`) : Chemin du cache des ID de fichiers Google Drive pour la KB secondaire.
*   **`GDRIVE_SCOPES`** (`list`) : Liste des scopes OAuth2 requis pour Google Drive.
*   **`GDRIVE_TOKEN_FILE`** (`str`) : Chemin du fichier de token d'authentification Google Drive.
*   **`GDRIVE_CREDS_FILE`** (`str`) : Chemin du fichier des identifiants client Google Drive.
*   **`APP_TO_BACKUP`** (`list`) : Liste des répertoires/fichiers à sauvegarder.
*   **`BACKUP_DIR`** (`str`) : Chemin du répertoire de sauvegarde principal.
*   **`BACKUP_INTERVAL_MINUTES`** (`int`) : Intervalle de sauvegarde en minutes.
*   **`MAX_BACKUPS_TO_KEEP`** (`int`) : Nombre maximal de sauvegardes à conserver.
*   **`MAX_SEARCH_RESULTS`** (`int`) : Nombre maximal de résultats à retourner pour les recherches.
*   **`API_COOLDOWN_SECONDS`** (`int`) : Délai de sécurité (cooldown) en secondes pour les appels API.
*   **`charger_json_robuste(*args, **kwargs)`** : Fonction robuste pour charger des fichiers JSON.
*   **`sauvegarder_json(*args, **kwargs)`** : Fonction pour sauvegarder des données au format JSON.
*   **`charger_historique_robuste_worker(*args, **kwargs)`** : Fonction worker robuste pour charger l'historique.
*   **`sauvegarder_historique_worker(*args, **kwargs)`** : Fonction worker pour sauvegarder l'historique.
*   **`charger_liens_contexte_worker(*args, **kwargs)`** : Fonction worker pour charger les liens de contexte.
*   **`sauvegarder_liens_contexte_worker(*args, **kwargs)`** : Fonction worker pour sauvegarder les liens de contexte.
*   **`SUPPORTED_FILE_EXTENSIONS`** (`tuple`) : Un tuple de chaînes de caractères représentant les extensions de fichiers supportées par l'application.

---

## Variables Dérivées

### `MAX_HISTORY`

*   **Type :** `int`
*   **Description :** Détermine le nombre maximal d'entrées à conserver dans l'historique. Cette valeur est dérivée du paramètre `max_history_retention` présent dans la section `system_settings` du dictionnaire `APP_SETTINGS`. Si le paramètre n'est pas trouvé, une valeur par défaut de `500` est utilisée.

---

## Exemple d'Usage

```python
import os
from config import (
    get_path, get_logger, load_app_settings, APP_SETTINGS,
    HISTORY_FILE, MAX_SEARCH_RESULTS, SUPPORTED_FILE_EXTENSIONS
)

# Charger les paramètres de l'application (à faire une fois au démarrage)
load_app_settings()

# Récupérer un chemin de configuration
settings_path = get_path("settings")
history_log_path = get_path("history")
print(f"Chemin du fichier de paramètres : {settings_path}")
print(f"Chemin du fichier d'historique : {HISTORY_FILE}")

# Créer un répertoire s'il n'existe pas (par exemple, pour les logs personnalisés)
custom_log_dir = get_path("custom_logs", create=True)
print(f"Répertoire de logs personnalisés : {custom_log_dir}")

# Obtenir un logger
logger = get_logger(__name__)
logger.info("Application configurée avec succès.")

# Accéder aux paramètres chargés
max_results = APP_SETTINGS.get("max_search_results", MAX_SEARCH_RESULTS)
print(f"Nombre maximal de résultats de recherche configuré : {max_results}")

# Utiliser une constante
print(f"Extensions de fichiers supportées : {SUPPORTED_FILE_EXTENSIONS}")

# Exemple de vérification de l'existence d'un fichier
if os.path.exists(HISTORY_FILE):
    print(f"Le fichier d'historique existe à : {HISTORY_FILE}")
else:
    print(f"Le fichier d'historique n'a pas encore été créé.")

# Exemple d'accès à des paramètres imbriqués (si load_app_settings() a été appelé)
if "user_interface" in APP_SETTINGS:
    theme = APP_SETTINGS["user_interface"].get("theme", "dark")
    print(f"Thème de l'interface utilisateur : {theme}")