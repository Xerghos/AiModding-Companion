# Documentation Technique: `features/context/drive.py`

Ce module fournit des fonctions pour interagir avec Google Drive pour la sauvegarde et la restauration de fichiers de base de connaissances (KB).

## Dépendances

*   `os`: Module pour interagir avec le système d'exploitation.
*   `json`: Module pour encoder et décoder des données JSON.
*   `zipfile`: Module pour travailler avec des archives ZIP.
*   `traceback`: Module pour obtenir les informations de traceback.
*   `googleapiclient.errors.HttpError`: Erreurs spécifiques à l'API Google.
*   `googleapiclient.http.MediaIoBaseDownload`: Classe pour télécharger des médias depuis Google Drive.
*   `googleapiclient.http.MediaFileUpload`: Classe pour télécharger des médias vers Google Drive.
*   `config`: Module de configuration personnalisé, fournissant:
    *   `get_path`: Pour obtenir des chemins de fichiers.
    *   `get_logger`: Pour obtenir un objet logger.
    *   `KB_ZIP_NAME`: Nom du fichier ZIP de la KB.
    *   `KB_DRIVE_FOLDER_NAME`: Nom du dossier sur Google Drive.
    *   `sauvegarder_json`: Fonction pour sauvegarder des données au format JSON.
*   `features.Decorators.trace_action`: Décorateur pour tracer les actions.

---

## Classes & Fonctions

### `get_cached_drive_file_id(cache_file_id_path)`

*   **Signature:** `def get_cached_drive_file_id(cache_file_id_path: str) -> Optional[str]`
*   **Arguments:**
    *   `cache_file_id_path` (str): Le chemin vers le fichier JSON contenant l'ID du fichier Drive mis en cache.
*   **Retour:**
    *   `str`: L'ID du fichier Drive s'il est trouvé dans le cache.
    *   `None`: Si le fichier de cache n'existe pas ou si l'ID n'a pas pu être lu.
*   **Logique interne:**
    1.  Vérifie si le fichier de cache existe au chemin spécifié.
    2.  Si le fichier existe, tente de l'ouvrir et de lire le contenu JSON.
    3.  Extrait la valeur associée à la clé `'file_id'`.
    4.  Retourne l'ID du fichier ou `None` en cas d'erreur ou si l'ID n'est pas présent.
    5.  Si le fichier de cache n'existe pas, retourne `None`.

### `set_cached_drive_file_id(file_id, cache_file_id_path)`

*   **Signature:** `def set_cached_drive_file_id(file_id: Optional[str], cache_file_id_path: str) -> None`
*   **Arguments:**
    *   `file_id` (Optional[str]): L'ID du fichier Drive à mettre en cache. Peut être `None` pour effacer l'ID.
    *   `cache_file_id_path` (str): Le chemin vers le fichier JSON où stocker l'ID.
*   **Retour:** `None`
*   **Logique interne:**
    1.  Crée un dictionnaire avec la clé `'file_id'` et la valeur fournie.
    2.  Utilise la fonction `sauvegarder_json` du module `config` pour écrire ce dictionnaire dans le fichier spécifié par `cache_file_id_path`.

### `get_or_create_folder_id(service, folder_name)`

*   **Signature:** `def get_or_create_folder_id(service: googleapiclient.discovery.Resource, folder_name: str) -> Optional[str]`
*   **Arguments:**
    *   `service` (Resource): L'objet service Google Drive authentifié.
    *   `folder_name` (str): Le nom du dossier à rechercher ou créer sur Google Drive.
*   **Retour:**
    *   `str`: L'ID du dossier s'il existe ou s'il a été créé avec succès.
    *   `None`: En cas d'erreur lors de la recherche ou de la création du dossier.
*   **Logique interne:**
    1.  Construit une requête de recherche pour trouver un dossier avec le nom et le type MIME spécifiés, et qui n'est pas dans la corbeille.
    2.  Exécute la requête de liste sur le service Drive.
    3.  Si des dossiers sont trouvés, retourne l'ID du premier dossier.
    4.  Si aucun dossier n'est trouvé, crée un nouveau dossier avec le nom et le type MIME appropriés.
    5.  Retourne l'ID du dossier nouvellement créé.
    6.  En cas d'exception, enregistre une erreur et retourne `None`.

### `download_drive_file(service, file_id, local_db_base_path, cache_file_id_path)`

*   **Signature:** `def download_drive_file(service: googleapiclient.discovery.Resource, file_id: str, local_db_base_path: str, cache_file_id_path: str) -> bool`
*   **Arguments:**
    *   `service` (Resource): L'objet service Google Drive authentifié.
    *   `file_id` (str): L'ID du fichier à télécharger depuis Google Drive.
    *   `local_db_base_path` (str): Le chemin de base local où les fichiers décompressés seront sauvegardés. Le nom du fichier lui-même n'est pas utilisé, mais son répertoire parent est utilisé pour l'extraction.
    *   `cache_file_id_path` (str): Le chemin du fichier de cache pour l'ID du fichier Drive. Utilisé pour effacer l'ID en cas de fichier introuvable.
*   **Retour:**
    *   `bool`: `True` si le téléchargement et la décompression ont réussi, `False` sinon.
*   **Logique interne:**
    1.  Détermine le chemin temporaire pour le fichier ZIP téléchargé en utilisant `get_path(KB_ZIP_NAME)`.
    2.  Détermine le répertoire de destination pour l'extraction à partir du répertoire parent de `local_db_base_path`. Crée ce répertoire s'il n'existe pas.
    3.  Prépare la requête pour obtenir le contenu du fichier Drive spécifié par `file_id`.
    4.  Ouvre le fichier ZIP temporaire en mode écriture binaire.
    5.  Crée un objet `MediaIoBaseDownload` pour télécharger le fichier.
    6.  Télécharge le fichier par morceaux jusqu'à ce que le téléchargement soit terminé.
    7.  Ouvre le fichier ZIP téléchargé en mode lecture.
    8.  Extrait toutes les entrées du fichier ZIP dans le répertoire de destination.
    9.  Retourne `True` en cas de succès.
    10. En cas d'`HttpError` avec un code de statut 404, enregistre un avertissement et efface l'ID du fichier mis en cache. Retourne `False`.
    11. En cas d'autres exceptions, enregistre une erreur et retourne `False`.
    12. Dans le bloc `finally`, supprime le fichier ZIP temporaire s'il existe.

### `upload_drive_file_worker(service, local_db_base_path, folder_id, cache_file_id_path)`

*   **Signature:** `def upload_drive_file_worker(service: googleapiclient.discovery.Resource, local_db_base_path: str, folder_id: str, cache_file_id_path: str) -> bool`
*   **Arguments:**
    *   `service` (Resource): L'objet service Google Drive authentifié.
    *   `local_db_base_path` (str): Le chemin de base local des fichiers à compresser et téléverser (par exemple, `/path/to/db/my_kb`). Les extensions `.sqlite`, `.faiss`, `.pkl` seront recherchées.
    *   `folder_id` (str): L'ID du dossier Drive dans lequel téléverser le fichier.
    *   `cache_file_id_path` (str): Le chemin du fichier de cache pour l'ID du fichier Drive. Utilisé pour stocker le nouvel ID ou le mettre à jour.
*   **Retour:**
    *   `bool`: `True` si l'upload a réussi, `False` sinon.
*   **Logique interne:**
    1.  Détermine le chemin temporaire pour le fichier ZIP à créer en utilisant `get_path(KB_ZIP_NAME)`.
    2.  Extrait le nom du répertoire et le nom de base de `local_db_base_path`.
    3.  Définit la liste des fichiers à compresser : `.sqlite`, `.faiss`, `.pkl` basés sur `base_name`.
    4.  Ouvre le fichier ZIP temporaire en mode écriture avec compression `zipfile.ZIP_DEFLATED`.
    5.  Pour chaque fichier dans `files_to_zip`, vérifie son existence dans le répertoire local et l'ajoute à l'archive ZIP avec son nom de base comme `arcname`.
    6.  Récupère l'ID du fichier Drive existant à partir du cache.
    7.  Crée un objet `MediaFileUpload` pour le fichier ZIP temporaire.
    8.  Si un `drive_file_id` existe :
        *   Tente de mettre à jour le fichier existant sur Drive.
        *   En cas d'`HttpError` (par exemple, ID invalide), réinitialise `drive_file_id` à `None` pour déclencher une création.
    9.  Si `drive_file_id` n'existe pas (nouveau fichier ou échec de mise à jour) :
        *   Définit les métadonnées du fichier, y compris le nom (`KB_ZIP_NAME`) et le dossier parent (`folder_id`).
        *   Crée le fichier sur Drive en utilisant `service.files().create()`.
        *   Récupère l'ID du nouveau fichier créé.
        *   Met à jour le cache avec le nouvel `drive_file_id`.
        *   Enregistre un message d'information.
    10. Retourne `True` en cas de succès.
    11. En cas d'exception, enregistre une erreur détaillée (avec traceback) et retourne `False`.
    12. Dans le bloc `finally`:
        *   Supprime explicitement l'objet `media` pour libérer les ressources.
        *   Supprime le fichier ZIP temporaire s'il existe.

### `handle_delete_drive_kb(service, cache_file_id_path)`

*   **Signature:** `def handle_delete_drive_kb(service: googleapiclient.discovery.Resource, cache_file_id_path: str) -> str`
*   **Arguments:**
    *   `service` (Resource): L'objet service Google Drive authentifié.
    *   `cache_file_id_path` (str): Le chemin du fichier de cache contenant l'ID du fichier Drive à supprimer.
*   **Retour:**
    *   `str`: Un message indiquant le statut de l'opération de suppression ("Pas de fichier connu.", "Base distante supprimée.") ou un message d'erreur.
*   **Logique interne:**
    1.  Récupère l'ID du fichier Drive à supprimer à partir du cache.
    2.  Si aucun ID n'est trouvé dans le cache, retourne "Pas de fichier connu.".
    3.  Tente de supprimer le fichier sur Google Drive en utilisant `service.files().delete()`.
    4.  Si la suppression réussit, efface l'ID du fichier dans le cache en appelant `set_cached_drive_file_id(None, ...)`. Retourne "Base distante supprimée.".
    5.  En cas d'exception lors de la suppression, retourne un message d'erreur formaté.

---

## Exemple d'usage

L'utilisation de ces fonctions nécessite un objet `service` Google Drive authentifié.

```python
import google.auth
from googleapiclient.discovery import build
from features.context.drive import (
    get_or_create_folder_id,
    download_drive_file,
    upload_drive_file_worker,
    handle_delete_drive_kb,
    get_cached_drive_file_id,
    set_cached_drive_file_id
)
from config import get_path, KB_DRIVE_FOLDER_NAME # Assurez-vous que config est correctement importé et configuré

# --- Configuration Initiale ---
# Obtenir les credentials (méthode à adapter selon votre authentification)
credentials, project = google.auth.default(
    scopes=['https://www.googleapis.com/auth/drive']
)
service = build('drive', 'v3', credentials=credentials)

# Définir les chemins et noms nécessaires
kb_base_path = get_path("my_knowledge_base") # Ex: /path/to/your/app/data/my_knowledge_base
drive_folder_name = KB_DRIVE_FOLDER_NAME # Ex: "MyKnowledgeBaseFolder"
cache_file_path = get_path(f"{drive_folder_name}_cache.json") # Ex: /path/to/your/app/data/MyKnowledgeBaseFolder_cache.json

# --- Opérations sur Google Drive ---

# 1. Obtenir ou créer le dossier sur Drive
folder_id = get_or_create_folder_id(service, drive_folder_name)

if folder_id:
    print(f"Dossier Drive trouvé/créé avec l'ID: {folder_id}")

    # 2. Télécharger un fichier KB (si nécessaire)
    # Supposons que vous ayez un ID de fichier KB connu ou récupéré du cache
    cached_file_id = get_cached_drive_file_id(cache_file_path)
    if not cached_file_id:
        # Si pas de cache, vous pourriez essayer de le trouver autrement ou demander à l'utilisateur
        print("Aucun ID de fichier KB en cache.")
    else:
        print(f"Tentative de téléchargement du fichier KB (ID: {cached_file_id})...")
        download_success = download_drive_file(service, cached_file_id, kb_base_path, cache_file_path)
        if download_success:
            print("Fichier KB téléchargé et décompressé avec succès.")
        else:
            print("Échec du téléchargement du fichier KB.")

    # 3. Téléverser (ou mettre à jour) un fichier KB
    print("Tentative de téléversement du fichier KB...")
    upload_success = upload_drive_file_worker(service, kb_base_path, folder_id, cache_file_path)
    if upload_success:
        print("Fichier KB téléversé/mis à jour avec succès.")
    else:
        print("Échec du téléversement du fichier KB.")

    # 4. Supprimer la base distante (si désiré)
    # print("Tentative de suppression de la base distante...")
    # delete_message = handle_delete_drive_kb(service, cache_file_path)
    # print(delete_message)

else:
    print(f"Impossible d'obtenir ou de créer le dossier '{drive_folder_name}' sur Google Drive.")