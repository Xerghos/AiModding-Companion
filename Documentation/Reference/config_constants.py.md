# Documentation Technique : `config\constants.py`

## Description Concise

Ce module centralise les constantes utilisées à travers l'application. Il définit les extensions de fichiers supportées, les noms de fichiers importants pour la configuration et l'historique, les constantes liées à l'intégration Google Drive et à la base de connaissances (Knowledge Base), les paramètres de sauvegarde, les fichiers liés à la feuille de route du projet, et diverses limites numériques pour les opérations.

## Dépendances

*   `os` (implicite, pour les opérations de chemin)
*   `json` (implicite, pour la manipulation des fichiers JSON)
*   `config.paths.get_path`

---

## Constantes Globales

Les constantes définies dans ce module sont accessibles directement après l'importation.

### Types de Fichiers Supportés

*   **`SUPPORTED_FILE_EXTENSIONS`**
    *   **Type:** `tuple` de `str`
    *   **Description:** Une collection de chaînes de caractères représentant les extensions de fichiers que l'application est capable de traiter ou de reconnaître.
    *   **Valeur:** `(".lua", ".xml", ".txt", ".json", ".md", ".py", ".js", ".html", ".css", ".ini", ".log", ".java", ".cpp", ".h", ".cs", ".ts")`

### Noms de Fichiers

Ces constantes définissent les noms de fichiers clés utilisés par l'application pour stocker des données spécifiques.

*   **`SETTINGS_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier JSON contenant les paramètres de configuration de l'application.
    *   **Valeur:** `"app_settings.json"`

*   **`HISTORY_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier JSON pour stocker l'historique des prompts.
    *   **Valeur:** `"prompt_history.json"`

*   **`ACTION_LOG_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier JSON pour enregistrer un journal des actions effectuées par l'application.
    *   **Valeur:** `"action_log.json"`

*   **`CONTEXT_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier JSON contenant les liens ou références contextuels.
    *   **Valeur:** `"context_links.json"`

### Constantes Google Drive & RAG (Retrieval-Augmented Generation)

Paramètres spécifiques à l'interaction avec Google Drive et à la gestion de la base de connaissances.

*   **`GDRIVE_SCOPES`**
    *   **Type:** `list` de `str`
    *   **Description:** Liste des autorisations (scopes) requises pour interagir avec l'API Google Drive. Permet l'accès au Drive et la lecture des feuilles de calcul.
    *   **Valeur:** `['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets.readonly']`

*   **`GDRIVE_TOKEN_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier où le token d'accès OAuth2 pour Google Drive sera stocké.
    *   **Valeur:** `'gdrive_token.json'`

*   **`GDRIVE_CREDS_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier contenant les identifiants de client OAuth2 pour Google Drive.
    *   **Valeur:** `'credentials.json'`

*   **`KB_DATABASE_FILE`**
    *   **Type:** `str`
    *   **Description:** Chemin de base du fichier de la base de connaissances hybride.
    *   **Valeur:** `"db/knowledge_base_hybrid"`

*   **`KB_DRIVE_FOLDER_NAME`**
    *   **Type:** `str`
    *   **Description:** Nom du dossier dans Google Drive où la base de connaissances est stockée.
    *   **Valeur:** `"Gemini_Assistant_Knowledge_Base"`

*   **`KB_DRIVE_FILE_ID_CACHE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier JSON utilisé pour mettre en cache les identifiants des fichiers de la base de connaissances sur Google Drive.
    *   **Valeur:** `"kb_drive_file_id.json"`

*   **`KB_ZIP_NAME`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier ZIP utilisé pour archiver la base de connaissances hybride.
    *   **Valeur:** `"hybrid_db_archive.zip"`

### Sauvegardes & Système

Paramètres liés aux opérations de sauvegarde du projet.

*   **`APP_TO_BACKUP`**
    *   **Type:** `str`
    *   **Description:** Chemin du répertoire racine de l'application à sauvegarder. Obtenu via `get_path(".")`.
    *   **Valeur:** Résultat de `get_path(".")`

*   **`BACKUP_DIR`**
    *   **Type:** `str`
    *   **Description:** Chemin du répertoire principal où les sauvegardes sont stockées. Obtenu via `get_path("backups")`.
    *   **Valeur:** Résultat de `get_path("backups")`

*   **`ROADMAP_BACKUP_DIR`**
    *   **Type:** `str`
    *   **Description:** Chemin du sous-répertoire spécifique pour les sauvegardes des feuilles de route. Obtenu via `get_path("backups/roadmaps")`.
    *   **Valeur:** Résultat de `get_path("backups/roadmaps")`

*   **`BACKUP_INTERVAL_MINUTES`**
    *   **Type:** `int`
    *   **Description:** Intervalle en minutes entre les sauvegardes automatiques.
    *   **Valeur:** `30`

*   **`MAX_BACKUPS_TO_KEEP`**
    *   **Type:** `int`
    *   **Description:** Nombre maximum de sauvegardes à conserver avant de supprimer les plus anciennes.
    *   **Valeur:** `40`

### Projet & Feuille de Route

Fichiers spécifiques liés à la gestion du projet et de sa feuille de route.

*   **`ROADMAP_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier Markdown principal de la feuille de route du projet.
    *   **Valeur:** `"roadmap.md"`

*   **`FULL_ROADMAP_FILE`**
    *   **Type:** `str`
    *   **Description:** Nom du fichier Markdown pour une version plus détaillée de la feuille de route.
    *   **Valeur:** `"full_detailled_roadmap.md"`

### Divers

Autres constantes numériques limitant certaines opérations ou affichages.

*   **`MAX_RAW_DISPLAY`**
    *   **Type:** `int`
    *   **Description:** Nombre maximum de lignes ou d'éléments bruts à afficher dans certaines interfaces ou logs.
    *   **Valeur:** `30`

*   **`MAX_SEARCH_RESULTS`**
    *   **Type:** `int`
    *   **Description:** Nombre maximum de résultats à retourner lors d'une recherche.
    *   **Valeur:** `5`

*   **`MAX_HISTORY`**
    *   **Type:** `int`
    *   **Description:** Taille maximale de l'historique (par exemple, nombre de prompts récents à conserver).
    *   **Valeur:** `30`

---

## Exemples d'usage

Bien que ces éléments soient des constantes, voici comment elles seraient utilisées dans le code :

```python
# Importation des constantes
from config.constants import SUPPORTED_FILE_EXTENSIONS, SETTINGS_FILE, BACKUP_INTERVAL_MINUTES

# Vérification si une extension est supportée
file_extension = ".txt"
if file_extension in SUPPORTED_FILE_EXTENSIONS:
    print(f"L'extension {file_extension} est supportée.")

# Construction d'un chemin de fichier de configuration
settings_path = os.path.join("config", SETTINGS_FILE)
print(f"Chemin du fichier de configuration : {settings_path}")

# Utilisation d'une constante pour une planification
print(f"Sauvegarde automatique toutes les {BACKUP_INTERVAL_MINUTES} minutes.")

# Utilisation pour Google Drive
if not os.path.exists(GDRIVE_TOKEN_FILE):
    # Logique pour obtenir les credentials et le token
    pass