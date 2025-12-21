# Documentation Technique : `features/context/loaders.py`

## Description concise

Ce module contient les fonctions pour charger du contenu à partir de diverses sources : documents Google Docs, feuilles Google Sheets, pages web et fichiers/dossiers locaux. Il est conçu pour être utilisé dans un contexte où l'extraction de données à partir de différentes origines est nécessaire.

## Dépendances

*   `os`
*   `io`
*   `re`
*   `logging`
*   `requests`
*   `googleapiclient.http.MediaIoBaseDownload`
*   `config` (spécifiquement `get_logger` et `SUPPORTED_FILE_EXTENSIONS`)
*   `features.Decorators.trace_action`

---

## Classes & Fonctions

### `fetch_google_doc_content(service, url)`

#### Signature

```python
def fetch_google_doc_content(service, url):
```

#### Arguments

*   `service`: Objet de service Google Drive API initialisé.
*   `url` (str): L'URL du Google Doc à récupérer. Doit contenir un ID de document au format `/d/FILE_ID/`.

#### Retours

*   `tuple`: Un tuple contenant :
    *   `source_name` (str | None): Le nom de la source (e.g., "GDoc: NomDuDocument"). `None` en cas d'erreur.
    *   `content` (str): Le contenu textuel du document. En cas d'erreur, contient un message d'erreur formaté.

#### Logique interne

1.  Extrait l'ID du fichier Google Doc de l'URL en utilisant une expression régulière. Si l'ID n'est pas trouvé, retourne `None` et un message d'erreur.
2.  Utilise l'API Google Drive (`service.files().get`) pour récupérer les métadonnées du fichier, notamment son nom.
3.  Logue l'intention d'exporter le document.
4.  Utilise `service.files().export_media` pour exporter le document au format `text/plain`.
5.  Télécharge le contenu du document dans un objet `io.BytesIO`.
6.  Décode le contenu téléchargé en UTF-8.
7.  Retourne le nom du document et son contenu texte.
8.  Capture toute exception survenant pendant le processus, logue l'erreur et retourne `None` et un message d'erreur formaté.

### `fetch_google_sheet_content(service_sheets, url)`

#### Signature

```python
def fetch_google_sheet_content(service_sheets, url):
```

#### Arguments

*   `service_sheets`: Objet de service Google Sheets API initialisé.
*   `url` (str): L'URL de la Google Sheet à récupérer. Doit contenir un ID de feuille au format `/d/SHEET_ID/`.

#### Retours

*   `tuple`: Un tuple contenant :
    *   `source_name` (str | None): Le nom de la source (e.g., "GSheet: TitreDeLaFeuille"). `None` en cas d'erreur.
    *   `content` (str): Le contenu concaténé de toutes les feuilles de la feuille de calcul, chaque ligne étant représentée par des valeurs séparées par des virgules. En cas d'erreur, contient un message d'erreur formaté.

#### Logique interne

1.  Extrait l'ID de la feuille de calcul de l'URL en utilisant une expression régulière. Si l'ID n'est pas trouvé, retourne `None` et un message d'erreur.
2.  Utilise l'API Google Sheets (`service_sheets.spreadsheets().get`) pour récupérer les métadonnées de la feuille de calcul, y compris son titre et la liste de ses feuilles.
3.  Itère sur chaque feuille de la feuille de calcul :
    *   Récupère les valeurs de la feuille en utilisant `service_sheets.spreadsheets().values().get`.
    *   Formate le contenu de la feuille en ajoutant un en-tête avec le titre de la feuille, puis chaque ligne de données avec les valeurs séparées par des virgules.
    *   Concatène le contenu de chaque feuille au `content` global.
4.  Retourne le titre de la feuille de calcul et son contenu concaténé.
5.  Capture toute exception survenant pendant le processus, logue l'erreur et retourne `None` et un message d'erreur formaté.

### `fetch_web_content(url)`

#### Signature

```python
def fetch_web_content(url):
```

#### Arguments

*   `url` (str): L'URL de la page web à récupérer.

#### Retours

*   `tuple`: Un tuple contenant :
    *   `source_name` (str | None): Le nom de la source (e.g., "Web: nom_du_fichier"). `None` en cas d'erreur.
    *   `content` (str): Le contenu textuel de la page web. En cas d'erreur, contient un message d'erreur formaté.

#### Logique interne

1.  Gère un cas spécifique pour les URL GitHub : remplace `github.com` par `raw.githubusercontent.com` et `/blob/` par `/` pour obtenir le contenu brut d'un fichier.
2.  Logue l'intention de récupérer le contenu web.
3.  Utilise la bibliothèque `requests` pour effectuer une requête GET vers l'URL avec un timeout de 10 secondes.
4.  Vérifie si la requête a réussi (`response.raise_for_status()`).
5.  Définit le nom de la source à partir de la dernière partie de l'URL.
6.  Retourne le nom de la source et le contenu texte de la réponse.
7.  Capture toute exception survenant pendant le processus, logue l'erreur et retourne `None` et un message d'erreur formaté.

### `fetch_local_content(path)`

#### Signature

```python
def fetch_local_content(path):
```

#### Arguments

*   `path` (str): Le chemin vers un fichier ou un répertoire local.

#### Retours

*   `tuple`: Un tuple contenant :
    *   `source_name` (str | None): Le nom de la source (e.g., "LocalFile: nom_fichier" ou "LocalDir: nom_dossier (N fichiers)"). `None` en cas d'erreur ou si le chemin est introuvable.
    *   `content` (str): Le contenu du fichier ou la concaténation des contenus des fichiers du répertoire. En cas d'erreur, contient un message d'erreur formaté.

#### Logique interne

1.  Normalise le chemin en chemin absolu (`os.path.abspath`).
2.  Obtient le nom de base du chemin (`os.path.basename`).
3.  **Si le chemin est un fichier :**
    *   Tente d'ouvrir le fichier en mode lecture ('r') avec l'encodage UTF-8.
    *   Lit et retourne le contenu du fichier.
    *   En cas d'erreur de lecture, retourne `None` et un message d'erreur.
4.  **Si le chemin est un répertoire :**
    *   Initialise un accumulateur de contenu (`content_acc`) et un compteur de fichiers (`file_count`).
    *   Utilise `os.walk` pour parcourir récursivement le répertoire.
    *   Exclut certains répertoires courants (`.git`, `__pycache__`, `venv`, etc.).
    *   Pour chaque fichier trouvé :
        *   Vérifie si l'extension du fichier est dans `SUPPORTED_FILE_EXTENSIONS`.
        *   Applique des filtres pour exclure certains types de fichiers (basés sur le nom et l'extension).
        *   Limite la lecture aux fichiers dont la taille est inférieure à 50000 caractères pour éviter de surcharger la mémoire.
        *   Lit le contenu du fichier.
        *   Ajoute le contenu du fichier à `content_acc`, précédé de son chemin relatif par rapport au répertoire de base et d'un séparateur.
        *   Incrémente `file_count`.
    *   Si aucun contenu n'a été accumulé (répertoire vide ou tous les fichiers filtrés), retourne `None` et un message indiquant un répertoire vide.
    *   Sinon, retourne le nom du répertoire (avec le nombre de fichiers lus) et le contenu accumulé.
5.  Si le chemin n'est ni un fichier ni un répertoire, retourne `None` et un message indiquant que le chemin est introuvable.

---

## Exemple d'usage

Cet exemple montre comment utiliser les différentes fonctions de chargement. Notez que les services Google (pour les fonctions `fetch_google_doc_content` et `fetch_google_sheet_content`) devraient être initialisés avant leur utilisation.

```python
import google.auth
from googleapiclient.discovery import build
# Assurez-vous que les imports de ce script sont corrects
# from features.context.loaders import fetch_google_doc_content, fetch_google_sheet_content, fetch_web_content, fetch_local_content

# Exemple d'initialisation des services Google (nécessite une authentification appropriée)
# try:
#     credentials, project = google.auth.default()
#     service_drive = build('drive', 'v3', credentials=credentials)
#     service_sheets = build('sheets', 'v4', credentials=credentials)
# except Exception as e:
#     print(f"Erreur d'initialisation des services Google: {e}")
#     service_drive = None
#     service_sheets = None

# --- Chargement d'un Google Doc ---
# google_doc_url = "https://docs.google.com/document/d/1XXXXXXXXXXXXXX/edit?usp=sharing"
# if service_drive:
#     doc_name, doc_content = fetch_google_doc_content(service_drive, google_doc_url)
#     if doc_name:
#         print(f"--- Contenu de {doc_name} ---")
#         print(doc_content[:200] + "...") # Afficher les 200 premiers caractères

# --- Chargement d'une Google Sheet ---
# google_sheet_url = "https://docs.google.com/spreadsheets/d/1YYYYYYYYYYYYYYY/edit?usp=sharing"
# if service_sheets:
#     sheet_name, sheet_content = fetch_google_sheet_content(service_sheets, google_sheet_url)
#     if sheet_name:
#         print(f"\n--- Contenu de {sheet_name} ---")
#         print(sheet_content[:200] + "...") # Afficher les 200 premiers caractères

# --- Chargement d'une page web ---
web_url = "https://example.com/some_file.txt" # Ou une URL GitHub comme "https://github.com/user/repo/blob/main/file.txt"
web_source_name, web_content = fetch_web_content(web_url)
if web_source_name:
    print(f"\n--- Contenu de {web_source_name} ---")
    print(web_content[:200] + "...")

# --- Chargement d'un fichier local ---
local_file_path = "path/to/your/local_file.txt"
file_source_name, file_content = fetch_local_content(local_file_path)
if file_source_name:
    print(f"\n--- Contenu de {file_source_name} ---")
    print(file_content[:200] + "...")

# --- Chargement d'un dossier local ---
local_dir_path = "path/to/your/local_directory"
dir_source_name, dir_content = fetch_local_content(local_dir_path)
if dir_source_name:
    print(f"\n--- Contenu de {dir_source_name} ---")
    print(dir_content[:200] + "...")