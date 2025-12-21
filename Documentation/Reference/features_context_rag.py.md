# Documentation Technique pour `features\context\rag.py`

## 1. En-tête

### Titre
Module de Génération Augmentée par Récupération (RAG)

### Description concise
Ce module gère les opérations de génération augmentée par récupération (RAG) pour l'intégration de connaissances. Il fournit des fonctionnalités pour la segmentation de texte, l'indexation de diverses sources de données (fichiers locaux, Google Drive, contenu web), la vectorisation des chunks de texte, la synchronisation de la base de connaissances avec Google Drive, et l'exécution de recherches hybrides pour enrichir les requêtes destinées aux modèles d'IA. Il orchestre le processus complet de gestion du contexte pour une IA conversationnelle.

### Dépendances
*   **Bibliothèque Standard Python** :
    *   `os` : Interactions avec le système d'exploitation (gestion des chemins de fichiers).
    *   `re` : Opérations d'expressions régulières (pour le `chunk_text`).
    *   `logging` : Système de journalisation pour le débogage et le suivi.
    *   `traceback` : Récupération des informations de trace d'exception.
*   **Modules internes au package `features.context`** :
    *   `.database` : Fonctions pour l'initialisation et l'interaction avec la base de données de connaissances (ajout, recherche).
    *   `.auth` : Fonctions d'authentification Google.
    *   `.drive` : Fonctions d'interaction avec Google Drive (création de dossier, upload, suppression).
    *   `.loaders` : Fonctions pour charger le contenu de différentes sources (fichiers locaux, Google Sheets, Google Docs, web).
*   **Modules de configuration et utilitaires** :
    *   `config` :
        *   `get_logger` : Initialisation du logger.
        *   `charger_json_robuste` : Chargement sécurisé de fichiers JSON.
        *   `MAX_SEARCH_RESULTS` : Constante pour le nombre maximal de résultats de recherche.
        *   `KB_DRIVE_FOLDER_NAME` : Nom du dossier Google Drive pour la base de connaissances.
    *   `features.Decorators` :
        *   `trace_action` : Décorateur pour tracer les appels de fonction.

---

## 2. Classes & Fonctions

### `chunk_text(source_name: str, full_text: str) -> list[dict]`
Découpe un texte intégral en morceaux (chunks) pertinents pour l'indexation.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def chunk_text(source_name: str, full_text: str) -> list[dict]:
    ```
*   **Arguments** :
    *   `source_name` (str) : Le nom ou l'identifiant de la source du texte. Utilisé pour les métadonnées de chaque chunk.
    *   `full_text` (str) : Le contenu textuel complet à découper.
*   **Retours** :
    *   `list[dict]` : Une liste de dictionnaires, où chaque dictionnaire représente un chunk et contient les clés suivantes :
        *   `"id"` (str) : Un identifiant unique généré par hachage pour le chunk.
        *   `"source"` (str) : Le nom de la source d'origine.
        *   `"content"` (str) : Le contenu du chunk.
*   **Logique interne** :
    1.  Divise le `full_text` en paragraphes en utilisant les doubles sauts de ligne (`\n\s*\n`).
    2.  Pour chaque paragraphe, supprime les espaces blancs en début et fin.
    3.  Ignore les paragraphes dont le contenu nettoyé est inférieur ou égal à 50 caractères.
    4.  Génère un hachage unique pour chaque chunk en combinant le `source_name` et le `content` du paragraphe.
    5.  Ajoute le chunk formaté (avec `id`, `source`, `content`) à la liste des chunks.

### `handle_load_context(result_queue: object, db_path: str) -> str`
Vérifie l'état de la base de connaissances locale au démarrage de l'application.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def handle_load_context(result_queue: object, db_path: str) -> str:
    ```
*   **Arguments** :
    *   `result_queue` (Queue-like object) : Une file d'attente pour communiquer les mises à jour de l'interface utilisateur. Non utilisé directement ici mais présent pour la cohérence des signatures de gestionnaires.
    *   `db_path` (str) : Le chemin de base de la base de données (avant l'extension `.sqlite`).
*   **Retours** :
    *   `str` : Un message d'état indiquant si la base de connaissances est prête, vide, ou s'il y a eu une erreur.
*   **Logique interne** :
    1.  Initialise la base de données en appelant `database.init_db(db_path)`.
    2.  Construit le chemin complet du fichier SQLite (`.sqlite`).
    3.  Vérifie si le fichier SQLite existe.
    4.  Retourne un message approprié basé sur l'existence du fichier.
    5.  Capture et loggue les exceptions, retournant un message d'erreur.

### `handle_sync_kb_to_drive(result_queue: object, db_path: str, drive_folder_name: str, cache_file_id_path: str) -> str`
Synchronise la base de connaissances locale (fichier SQLite) vers Google Drive.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def handle_sync_kb_to_drive(result_queue: object, db_path: str, drive_folder_name: str, cache_file_id_path: str) -> str:
    ```
*   **Arguments** :
    *   `result_queue` (Queue-like object) : Une file d'attente pour communiquer les mises à jour de l'interface utilisateur.
    *   `db_path` (str) : Le chemin de base de la base de données locale.
    *   `drive_folder_name` (str) : Le nom du dossier Google Drive où le fichier doit être stocké.
    *   `cache_file_id_path` (str) : Le chemin du fichier où l'ID du fichier Drive synchronisé est mis en cache.
*   **Retours** :
    *   `str` : Un message d'état indiquant le succès ou l'échec de la synchronisation.
*   **Logique interne** :
    1.  Envoie une mise à jour UI pour indiquer le début de la synchronisation.
    2.  Tente d'obtenir les services Google authentifiés (`gdrive`, `gsheets`). Retourne un échec si l'authentification échoue.
    3.  Vérifie l'existence du fichier SQLite local. Retourne un échec si la DB est vide.
    4.  Récupère ou crée l'ID du dossier cible sur Google Drive via `get_or_create_folder_id`.
    5.  Appelle `upload_drive_file_worker` pour télécharger le fichier de la base de données vers Drive.
    6.  Retourne un message de succès ou d'échec basé sur le résultat de l'upload.
    7.  Capture et loggue les exceptions, retournant un message d'erreur.

### `handle_delete_drive_kb(result_queue: object, cache_file_id_path: str) -> str`
Un wrapper pour la fonction de suppression de Google Drive, incluant la gestion de l'interface utilisateur.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def handle_delete_drive_kb(result_queue: object, cache_file_id_path: str) -> str:
    ```
*   **Arguments** :
    *   `result_queue` (Queue-like object) : Une file d'attente pour communiquer les mises à jour de l'interface utilisateur.
    *   `cache_file_id_path` (str) : Le chemin du fichier où l'ID du fichier Drive est mis en cache.
*   **Retours** :
    *   `str` : Un message d'état du succès ou de l'échec de la suppression.
*   **Logique interne** :
    1.  Envoie une mise à jour UI pour indiquer le début de la suppression.
    2.  Tente d'obtenir les services Google authentifiés. Retourne une erreur si l'authentification échoue.
    3.  Appelle la fonction `drive_delete` du module `.drive` pour effectuer la suppression réelle.
    4.  Capture et loggue les exceptions, retournant un message d'erreur.

### `handle_maj_contexte(result_queue: object, context_file_path: str, db_path: str, drive_folder_name: str, cache_file_id_path: str, session: object = None) -> str`
Orchestre le processus complet d'indexation : lecture des sources, chargement du contenu, découpage, vectorisation, ajout à la base de données et synchronisation optionnelle avec Google Drive.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def handle_maj_contexte(result_queue: object, context_file_path: str, db_path: str, drive_folder_name: str, cache_file_id_path: str, session: object = None) -> str:
    ```
*   **Arguments** :
    *   `result_queue` (Queue-like object) : Une file d'attente pour communiquer les mises à jour de l'interface utilisateur.
    *   `context_file_path` (str) : Le chemin du fichier JSON contenant la liste des liens ou chemins à indexer.
    *   `db_path` (str) : Le chemin de base de la base de données locale.
    *   `drive_folder_name` (str) : Le nom du dossier Google Drive pour la synchronisation.
    *   `cache_file_id_path` (str) : Le chemin du fichier où l'ID du fichier Drive est mis en cache.
    *   `session` (object, optionnel) : Un objet de session. Actuellement non utilisé directement dans cette fonction, mais peut être un placeholder pour de futures extensions.
*   **Retours** :
    *   `str` : Un message d'état récapitulant le résultat de l'indexation.
*   **Logique interne** :
    1.  Charge la liste des liens à partir du `context_file_path` en utilisant `charger_json_robuste`. Retourne un message si aucun lien n'est trouvé.
    2.  Envoie une mise à jour UI et tente d'obtenir les services Google (Drive, Sheets).
    3.  Initialise la base de données via `database.init_db`.
    4.  Parcourt chaque lien dans la liste :
        *   Détermine le type de source (fichier local, Google Drive, URL web).
        *   Appelle la fonction `fetch_..._content` appropriée du module `.loaders` pour récupérer le contenu.
        *   Si le contenu est récupéré avec succès, le découpe en chunks en utilisant `chunk_text`.
        *   Collecte tous les chunks pour traitement ultérieur.
        *   Signale les échecs de lecture via `result_queue`.
    5.  Vérifie si des chunks ont été extraits. Retourne une erreur si aucun contenu valide n'a été trouvé.
    6.  Envoie une mise à jour UI pour indiquer le début de la vectorisation.
    7.  Ajoute chaque chunk à la base de connaissances en appelant `database.add_knowledge`.
    8.  Si les services Google Drive sont disponibles (`gdrive` n'est pas `None`), appelle `handle_sync_kb_to_drive` pour synchroniser la DB.
    9.  Retourne un message final indiquant la fin de l'indexation et la synchronisation.
    10. Capture et loggue les exceptions (avec traceback complet), retournant un message d'erreur fatal.

### `handle_chat_rag_hybrid(prompt: str, session: object, db_path: str)`
Effectue une recherche RAG (Retrieval Augmented Generation) hybride pour trouver les informations pertinentes dans la base de connaissances et enrichir le prompt de l'IA.

*   **Signature** :
    ```python
    @trace_action(source="rag")
    def handle_chat_rag_hybrid(prompt: str, session: object, db_path: str) -> any:
    ```
*   **Arguments** :
    *   `prompt` (str) : La question ou la requête de l'utilisateur.
    *   `session` (object) : Un objet de session qui possède une méthode `send_message` pour interroger le modèle d'IA.
    *   `db_path` (str) : Le chemin de base de la base de données locale.
*   **Retours** :
    *   `any` : Le résultat de l'appel à `session.send_message`, qui est la réponse de l'IA.
*   **Logique interne** :
    1.  Loggue le début de la recherche RAG hybride.
    2.  Appelle `database.search_hybrid` pour effectuer une recherche combinant FAISS (vectorielle) et FTS5 (texte intégral) avec la fusion des résultats RRF (Reciprocal Rank Fusion). Le nombre de résultats est limité par `MAX_SEARCH_RESULTS`.
    3.  Si la recherche hybride échoue ou rencontre une erreur, loggue un avertissement et tente une recherche purement vectorielle via `database.search_vector_db` comme fallback.
    4.  Initialise une chaîne de contexte vide.
    5.  Si des résultats sont trouvés :
        *   Construit une chaîne `context_txt` contenant les sources, le contenu (tronqué) et les scores de pertinence de chaque résultat.
    6.  Construit un `final_prompt` en préfixant le `context_txt` (si pertinent) à la question originale de l'utilisateur.
    7.  Envoie ce `final_prompt` au modèle d'IA en appelant `session.send_message`.

---

## 3. Exemple d'usage

Voici comment les fonctions `handle_maj_contexte` et `handle_chat_rag_hybrid` pourraient être utilisées dans un flux de travail typique :

```python
import os
import queue
from unittest.mock import Mock # Pour simuler les dépendances

# Simuler les dépendances nécessaires
class MockLogger:
    def info(self, msg): print(f"INFO: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def error(self, msg): print(f"ERROR: {msg}")

class MockDatabase:
    def init_db(self, path):
        print(f"DB initialized at {path}.sqlite")
        # Simuler la création du fichier SQLite
        with open(f"{path}.sqlite", "w") as f:
            f.write("DB content simulation")
    def add_knowledge(self, source, content, metadata):
        print(f"Knowledge added: Source='{source}', Content='{content[:50]}...'")
    def search_hybrid(self, prompt, db_path, max_results, use_hybrid):
        print(f"Hybrid search for: {prompt}")
        if "IA" in prompt:
            return [
                ("doc_ia.txt", "L'Intelligence Artificielle est un vaste domaine...", 0.95),
                ("web_rag.html", "Le RAG améliore les réponses des LLM...", 0.88)
            ], None
        return [], "No results found (simulated)"
    def search_vector_db(self, prompt, db_path, max_results):
        print(f"Vector search for: {prompt}")
        if "IA" in prompt:
            return [
                ("doc_ia_fallback.txt", "L'IA transforme de nombreuses industries...", 0.90)
            ], None
        return [], "No results found (simulated)"

class MockGoogleServices:
    def get_google_services(self, result_queue):
        # Simuler des services Google disponibles pour Drive
        return Mock(), Mock() 

class MockDrive:
    def get_or_create_folder_id(self, service, name):
        print(f"Drive: Get/create folder '{name}'")
        return "folder_id_123"
    def upload_drive_file_worker(self, service, db_path, folder_id, cache_path):
        print(f"Drive: Uploading {db_path} to {folder_id}")
        with open(cache_path, "w") as f:
            f.write("uploaded_file_id_456")
        return True
    def handle_delete_drive_kb(self, service, cache_path):
        print(f"Drive: Deleting KB using cache file {cache_path}")
        if os.path.exists(cache_path): os.remove(cache_path)
        return "--- SUPPRESSION DRIVE : Succès ---"

class MockLoaders:
    def fetch_local_content(self, path):
        print(f"Loading local: {path}")
        return path, "Contenu du fichier local sur l'IA et le RAG. Il s'agit d'un paragraphe important."
    def fetch_web_content(self, url):
        print(f"Loading web: {url}")
        return url, "Article web sur les dernières avancées en IA générative et l'utilisation du RAG."
    def fetch_google_doc_content(self, service, url):
        print(f"Loading Google Doc: {url}")
        return url, "Document Google Docs décrivant les principes du Retrieval Augmented Generation (RAG)."
    def fetch_google_sheet_content(self, service, url):
        print(f"Loading Google Sheet: {url}")
        return url, "Feuille de calcul Google Sheets avec des statistiques sur les performances des modèles RAG."

class MockConfig:
    def get_logger(self, name): return MockLogger()
    def charger_json_robuste(self, path):
        if path == "context_links.json":
            return ["local_doc.txt", "https://example.com/ai-rag", "https://docs.google.com/document/d/doc_id"]
        return []
    MAX_SEARCH_RESULTS = 5
    KB_DRIVE_FOLDER_NAME = "My_KB_Folder"

class MockSession:
    def send_message(self, final_prompt):
        print(f"\n--- AI RECEIVES PROMPT ---\n{final_prompt}\n---")
        return "Réponse simulée de l'IA basée sur le contexte fourni."

# Injecter les mocks dans les modules
import sys
sys.modules['config'] = MockConfig()
sys.modules['features.context.database'] = MockDatabase()
sys.modules['features.context.auth'] = MockGoogleServices()
sys.modules['features.context.drive'] = MockDrive()
sys.modules['features.context.drive'].handle_delete_drive_kb = MockDrive().handle_delete_drive_kb # Réaffecter pour le wrapper
sys.modules['features.context.loaders'] = MockLoaders()
sys.modules['features.Decorators'] = Mock() # Le décorateur n'a pas besoin d'une implémentation complexe pour l'exemple

# Maintenant, importer le module rag après avoir configuré les mocks
from features.context import rag

# Configuration des chemins pour l'exemple
DB_PATH = "my_knowledge_base"
CONTEXT_FILE = "context_links.json"
CACHE_FILE_ID = "drive_file_id.cache"
DRIVE_FOLDER_NAME = MockConfig.KB_DRIVE_FOLDER_NAME

# Création de fichiers factices pour la simulation
with open("local_doc.txt", "w") as f:
    f.write("Ceci est un document local sur les bases de l'Intelligence Artificielle. Le RAG est une technique avancée.")
with open(CONTEXT_FILE, "w") as f:
    f.write('["local_doc.txt", "https://example.com/ai-rag", "https://docs.google.com/document/d/doc_id"]')

# Initialisation de la file de résultats pour l'UI
result_queue = queue.Queue()
mock_session = MockSession()

print("--- ÉTAPE 1: Chargement initial du contexte (vérification DB) ---")
status_load = rag.handle_load_context(result_queue, DB_PATH)
print(status_load)

# Simuler la suppression de la base de données SQLite pour l'indexation
if os.path.exists(f"{DB_PATH}.sqlite"):
    os.remove(f"{DB_PATH}.sqlite")

print("\n--- ÉTAPE 2: Mise à jour et indexation du contexte ---")
status_maj = rag.handle_maj_contexte(result_queue, CONTEXT_FILE, DB_PATH, DRIVE_FOLDER_NAME, CACHE_FILE_ID, mock_session)
print(status_maj)

# Vérifier les messages UI (simulés ici)
while not result_queue.empty():
    ui_msg = result_queue.get()
    print(f"UI Update: {ui_msg.get('text', '')}")

print("\n--- ÉTAPE 3: Recherche RAG hybride et interrogation de l'IA ---")
user_prompt = "Qu'est-ce que le RAG et comment l'IA l'utilise-t-elle ?"
ai_response = rag.handle_chat_rag_hybrid(user_prompt, mock_session, DB_PATH)
print(f"Réponse de l'IA: {ai_response}")

print("\n--- ÉTAPE 4: Suppression de la KB du Drive (optionnel) ---")
# Simuler l'existence du fichier cache après l'upload
with open(CACHE_FILE_ID, "w") as f:
    f.write("drive_kb_file_id_example")
status_delete = rag.handle_delete_drive_kb(result_queue, CACHE_FILE_ID)
print(status_delete)


# Nettoyage des fichiers créés pour l'exemple
os.remove("local_doc.txt")
os.remove(CONTEXT_FILE)
if os.path.exists(f"{DB_PATH}.sqlite"):
    os.remove(f"{DB_PATH}.sqlite")
if os.path.exists(CACHE_FILE_ID):
    os.remove(CACHE_FILE_ID)