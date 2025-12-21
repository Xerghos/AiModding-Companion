# Documentation Technique - `features/context/database.py`

Ce module est le cœur de la base de connaissances hybride, gérant l'indexation, le stockage et la récupération de l'information contextuelle à partir de fichiers et de mémoires. Il combine une base de données relationnelle SQLite pour le stockage structuré et la recherche plein texte (FTS5) avec un index vectoriel FAISS pour la recherche sémantique.

Le système est conçu pour l'indexation de code source, permettant le chunking sémantique pour les fichiers Python, le suivi des fichiers indexés via des hachages et la fusion des résultats de recherche via Reciprocal Rank Fusion (RRF).

## Dépendances

**Modules Python Standard :**
*   `logging`
*   `os`
*   `sqlite3`
*   `pickle`
*   `numpy`
*   `shutil`
*   `traceback`
*   `threading`
*   `hashlib`
*   `time`
*   `json`
*   `glob`
*   `typing` (Dict, Optional, List, Tuple)
*   `re` (pour `_sanitize_fts5_query`)

**Bibliothèques Tierces :**
*   `faiss-cpu` (ou `faiss-gpu`) : Pour la recherche d'embeddings vectoriels. Importé paresseusement.
*   `sentence-transformers` : Pour la génération d'embeddings. Importé paresseusement.

**Modules Internes :**
*   `config.get_logger`, `config.get_path`, `config.SUPPORTED_FILE_EXTENSIONS`
*   `features.Decorators.trace_action`
*   `features.context.code_chunker.get_chunker`
*   `features.context.merkle_sync.MerkleTreeSync` (et `MerkleNode`)

## Classes & Fonctions

### Variables Globales et Constantes

*   `EMBEDDING_MODEL_NAME` (str): Nom du modèle SentenceTransformer utilisé pour générer les embeddings (actuellement "all-MiniLM-L6-v2").
*   `EMBEDDING_DIM` (int): Dimension des vecteurs d'embedding générés (actuellement 384).
*   `DB_DIR` (str): Nom du répertoire où la base de données sera stockée ("db").
*   `DB_NAME` (str): Nom de base des fichiers de la base de connaissances ("knowledge_base_hybrid_V2").
*   `faiss_index` (faiss.IndexIDMap ou faiss.IndexFlatL2, global): L'objet index FAISS en mémoire pour la recherche vectorielle.
*   `id_mapping` (dict, global): Dictionnaire pour mapper les IDs internes de FAISS aux IDs SQLite.
*   `faiss` (module, global): Référence au module `faiss` après importation paresseuse.
*   `SentenceTransformer` (classe, global): Référence à la classe `SentenceTransformer` après importation paresseuse.
*   `model` (SentenceTransformer, global): L'instance du modèle d'embedding chargé.

### `_get_paths(db_path_base=None)`

Détermine les chemins complets pour les fichiers de la base de données SQLite, de l'index FAISS et du mapping d'ID.

**Signature :**
```python
@trace_action(source="database")
def _get_paths(db_path_base=None) -> Tuple[str, str, str]
```

**Arguments :**
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB. Si `None`, utilise les constantes `DB_DIR` et `DB_NAME`.

**Retours :**
*   `Tuple[str, str, str]`: Un tuple contenant les chemins absolus vers le fichier SQLite, l'index FAISS et le fichier de mapping d'ID.

**Logique interne :**
*   Construit les chemins en utilisant `os.path.join`.
*   Si `db_path_base` est fourni, il extrait le répertoire et le nom de base de ce chemin.
*   Sinon, il utilise les chemins configurés globalement.

### `_ensure_libs()`

Assure que les bibliothèques `faiss` et `sentence_transformers` sont chargées. Elles sont importées paresseusement pour éviter des chargements coûteux si elles ne sont pas nécessaires.

**Signature :**
```python
@trace_action(source="database")
def _ensure_libs() -> None
```

**Arguments :**
*   Aucun.

**Retours :**
*   Aucun.

**Logique interne :**
*   Vérifie si les variables globales `faiss` et `SentenceTransformer` sont `None`.
*   Si c'est le cas, importe les modules correspondants et charge le modèle d'embedding spécifié par `EMBEDDING_MODEL_NAME`.

### `init_db(db_path_base=None)`

Initialise la base de données SQLite, créant les tables et les index nécessaires. Elle charge également l'index FAISS existant ou en crée un nouveau si absent ou corrompu. Gère la migration des anciens formats d'index FAISS vers `IndexIDMap`.

**Signature :**
```python
@trace_action(source="database")
def init_db(db_path_base=None) -> None
```

**Arguments :**
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.

**Retours :**
*   Aucun.

**Logique interne :**
*   Crée le répertoire de la DB si nécessaire.
*   Se connecte à la base de données SQLite.
*   Crée les tables `knowledge` (pour les informations générales/legacy), `files` (pour le suivi des fichiers indexés) et `chunks` (pour les morceaux de contenu sémantiques).
*   Crée les index sur `chunks.file_id`, `chunks.ast_type` et `files.path` pour des recherches rapides.
*   Tente de créer une table virtuelle `fts_code` via FTS5 pour la recherche plein texte, avec des triggers pour maintenir la synchronisation avec la table `chunks`. Gère les cas où FTS5 n'est pas disponible.
*   Appelle `_ensure_libs()` pour charger les bibliothèques d'embedding et FAISS.
*   Tente de charger l'index FAISS (`.index`) et le mapping d'ID (`.pkl`) existants.
*   **Migration FAISS** : Si l'index chargé est un `IndexFlatL2` (ancien format), il le convertit en `IndexIDMap`.
*   **Reconstruction FAISS** : Si l'index FAISS est vide mais que la DB contient des chunks ou des entrées `knowledge`, il reconstruit l'index FAISS à partir des embeddings stockés dans la DB.

### `add_knowledge(collection, content, metadata=None)`

Ajoute un élément de connaissance à la base de données. Il calcule l'embedding du contenu, l'insère dans la table `knowledge` et l'ajoute à l'index FAISS.

**Signature :**
```python
@trace_action(source="database")
def add_knowledge(collection: str, content: str, metadata: Optional[Dict] = None) -> Optional[int]
```

**Arguments :**
*   `collection` (str): La collection à laquelle appartient cette connaissance (ex: "memory://<id>").
*   `content` (str): Le texte de la connaissance à stocker.
*   `metadata` (Optional[Dict]): Dictionnaire de métadonnées optionnel, qui sera sérialisé en JSON.

**Retours :**
*   `Optional[int]`: L'ID SQLite de l'entrée insérée, ou `None` en cas d'échec ou si le contenu est vide ou un doublon.

**Logique interne :**
*   Assure que les bibliothèques sont chargées via `_ensure_libs()`.
*   Calcule le vecteur d'embedding du `content` et son hachage MD5.
*   Tente d'insérer le contenu, le hachage et l'embedding dans la table `knowledge`.
*   **Auto-réparation** : Si une `sqlite3.OperationalError` indique une table manquante, elle tente d'appeler `init_db()` et réessaie l'insertion.
*   Si l'insertion est réussie et qu'un nouvel ID est généré, ajoute le vecteur correspondant à l'index FAISS et met à jour le mapping d'ID.
*   Sauvegarde l'index FAISS et le mapping d'ID sur le disque.

### `reciprocal_rank_fusion(vector_results: List[Tuple], fts_results: List[Tuple], k: int = 60) -> Dict[int, float]`

Applique l'algorithme Reciprocal Rank Fusion (RRF) pour combiner les résultats de recherche provenant de différentes sources (ici, vectorielle et FTS5).

**Signature :**
```python
@trace_action(source="database")
def reciprocal_rank_fusion(vector_results: List[Tuple], fts_results: List[Tuple], k: int = 60) -> Dict[int, float]
```

**Arguments :**
*   `vector_results` (List[Tuple]): Liste de tuples `(chunk_id, score)` provenant de la recherche vectorielle. Un score plus bas indique une meilleure pertinence.
*   `fts_results` (List[Tuple]): Liste de tuples `(chunk_id, score)` provenant de la recherche FTS5. Un score plus haut (pour BM25) ou un rang plus bas (pour `MATCH` simple) indique une meilleure pertinence.
*   `k` (int): Constante de lissage utilisée dans la formule RRF (par défaut 60).

**Retours :**
*   `Dict[int, float]`: Un dictionnaire où la clé est le `chunk_id` et la valeur est le score RRF combiné.

**Logique interne :**
*   Initialise un dictionnaire `rrf_scores`.
*   Pour chaque liste de résultats, il parcourt les éléments, attribue un rang, et calcule un score RRF pour chaque `chunk_id` en utilisant la formule `1.0 / (k + rank)`.
*   Les scores de chaque source sont additionnés pour le même `chunk_id`.

### `search_vector_db(query, db_path_base=None, max_results=5)`

Effectue une recherche purement vectorielle dans la base de données. Cette fonction est conservée pour des raisons de compatibilité et appelle en interne `search_hybrid` avec `use_hybrid=False`.

**Signature :**
```python
@trace_action(source="database")
def search_vector_db(query: str, db_path_base: Optional[str] = None, max_results: int = 5) -> Tuple[List[Tuple], Optional[str]]
```

**Arguments :**
*   `query` (str): La requête de recherche en texte clair.
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.
*   `max_results` (int): Nombre maximum de résultats à retourner.

**Retours :**
*   `Tuple[List[Tuple], Optional[str]]`: Une liste de tuples `(source, content, score)` et un message d'erreur si applicable.

**Logique interne :**
*   Appelle `search_hybrid` en passant `use_hybrid=False`.

### `_sanitize_fts5_query(query: str) -> str`

Nettoie et échappe une chaîne de requête pour l'utiliser dans une recherche FTS5 de SQLite, gérant les caractères spéciaux et les mots d'arrêt (stop words).

**Signature :**
```python
def _sanitize_fts5_query(query: str) -> str
```

**Arguments :**
*   `query` (str): La requête FTS5 à nettoyer.

**Retours :**
*   `str`: La requête nettoyée et formatée pour FTS5.

**Logique interne :**
*   Gère les requêtes vides.
*   Détecte si la requête contient déjà des opérateurs FTS5 (AND, OR, NOT) et l'échappe si nécessaire sans modifier la structure.
*   Définit une liste de caractères spéciaux FTS5 à échapper.
*   Définit une liste de mots d'arrêt français.
*   Extrait les mots significatifs de la requête (non-stop words, longueur minimale).
*   Si plusieurs mots significatifs, les combine avec "OR".
*   Si un seul mot significatif, le retourne tel quel.
*   En cas de mots non significatifs, utilise les premiers mots de la requête avec "OR".
*   Échappe les guillemets dans la requête finale.

### `search_hybrid(query, db_path_base=None, max_results=50, use_hybrid=True)`

Effectue une recherche hybride combinant la recherche sémantique (FAISS) et la recherche plein texte (FTS5). Les résultats sont fusionnés à l'aide de l'algorithme Reciprocal Rank Fusion (RRF).

**Signature :**
```python
@trace_action(source="database")
def search_hybrid(query: str, db_path_base: Optional[str] = None, max_results: int = 50, use_hybrid: bool = True) -> Tuple[List[Tuple], Optional[str]]
```

**Arguments :**
*   `query` (str): La requête de recherche en texte clair.
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.
*   `max_results` (int): Nombre maximum de résultats finaux à retourner après fusion.
*   `use_hybrid` (bool): Si `False`, la recherche se dégrade en une recherche purement vectorielle.

**Retours :**
*   `Tuple[List[Tuple], Optional[str]]`: Une liste de tuples `(source, content, score, ast_type, parent_context, start_line, end_line)` et un message d'erreur si applicable.

**Logique interne :**
*   Assure que les bibliothèques et l'index FAISS sont initialisés.
*   **Recherche Dense (FAISS)** :
    *   Encode la `query` en vecteur.
    *   Recherche les `k` vecteurs les plus proches dans l'index FAISS (où `k` est un multiple de `max_results`).
    *   Récupère les `content` et métadonnées (path, ast_type, parent_context, start_line, end_line) des chunks correspondants dans la DB SQLite.
    *   Gère également la recherche dans la table `knowledge` (legacy).
*   **Recherche Sparse (FTS5)** :
    *   Si `use_hybrid` est `True` et que la table FTS5 existe :
        *   Nettoie la requête avec `_sanitize_fts5_query`.
        *   Exécute une requête FTS5 avec `BM25` (si disponible) ou `MATCH` simple pour obtenir les `chunk_id` et leurs scores/rangs.
        *   Récupère les `content` et métadonnées des chunks associés.
*   **Fusion RRF** :
    *   Si `use_hybrid` est `True` et que des résultats FTS5 ont été trouvés :
        *   Trie les résultats vectoriels par distance et les résultats FTS5 par score/rang.
        *   Appelle `reciprocal_rank_fusion` pour combiner les scores.
        *   Assemble les résultats complets (contenu + métadonnées) et les trie par score RRF décroissant.
*   Si pas de fusion (ou pas de résultats FTS5), retourne les résultats vectoriels triés par distance.

### `_get_or_create_file_id(file_path: str, checksum: str, db_path_base=None) -> int`

Récupère l'ID d'un fichier à partir de son chemin dans la table `files`. Si le fichier n'existe pas, il est créé. Si existant, son checksum et son horodatage `last_indexed` sont mis à jour.

**Signature :**
```python
@trace_action(source="database")
def _get_or_create_file_id(file_path: str, checksum: str, db_path_base=None) -> int
```

**Arguments :**
*   `file_path` (str): Le chemin relatif ou absolu du fichier.
*   `checksum` (str): Le hachage SHA-256 du contenu du fichier.
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.

**Retours :**
*   `int`: L'ID de la ligne correspondante dans la table `files`.

**Logique interne :**
*   Connecte à la DB SQLite.
*   Cherche le fichier par `file_path`.
*   Si trouvé, met à jour le `checksum` et `last_indexed`.
*   Si non trouvé, insère une nouvelle entrée et retourne l'ID généré.

### `_add_chunk_to_db(file_id: int, chunk_index: int, chunk_data: Dict, db_path_base=None) -> Optional[int]`

Ajoute un "chunk" de contenu à la base de données. Calcule son embedding, l'insère dans la table `chunks` et l'ajoute à l'index FAISS.

**Signature :**
```python
@trace_action(source="database")
def _add_chunk_to_db(file_id: int, chunk_index: int, chunk_data: Dict, db_path_base=None) -> Optional[int]
```

**Arguments :**
*   `file_id` (int): L'ID du fichier parent de ce chunk (clé étrangère vers `files.id`).
*   `chunk_index` (int): L'index ordonné de ce chunk au sein de son fichier.
*   `chunk_data` (Dict): Dictionnaire contenant le contenu du chunk et ses métadonnées (ex: 'content', 'start_line', 'end_line', 'ast_type', 'parent_context').
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.

**Retours :**
*   `Optional[int]`: L'ID SQLite du chunk inséré, ou `None` en cas d'échec ou si le contenu est vide.

**Logique interne :**
*   Assure que les bibliothèques sont chargées via `_ensure_libs()`.
*   Calcule le vecteur d'embedding du `content` du chunk et son hachage SHA256.
*   Insère les données du chunk dans la table `chunks`.
*   Ajoute le vecteur d'embedding à l'index FAISS en utilisant l'ID SQLite du chunk comme identifiant direct (si `IndexIDMap`).
*   Sauvegarde l'index FAISS et le mapping d'ID sur le disque.

### `_delete_file_chunks(file_id: int, db_path_base=None)`

Supprime tous les chunks associés à un fichier donné de la base de données SQLite et de l'index FAISS.

**Signature :**
```python
@trace_action(source="database")
def _delete_file_chunks(file_id: int, db_path_base=None) -> None
```

**Arguments :**
*   `file_id` (int): L'ID du fichier dont les chunks doivent être supprimés.
*   `db_path_base` (Optional[str]): Chemin de base optionnel pour la DB.

**Retours :**
*   Aucun.

**Logique interne :**
*   Connecte à la DB SQLite.
*   Récupère tous les IDs de chunks pour le `file_id` donné.
*   Si des chunks sont trouvés et que l'index FAISS est un `IndexIDMap`, les IDs sont supprimés de l'index FAISS.
*   Les chunks sont ensuite supprimés de la table `chunks` (la contrainte `ON DELETE CASCADE` sur `files.id` assure que cette opération supprime également les entrées FTS5 via les triggers).
*   L'index FAISS est sauvegardé après la suppression.

### `index_project_files(root_path, progress_callback=None, use_semantic_chunking=True)`

Scan un répertoire de projet, filtre les fichiers supportés, les découpe en chunks et les indexe dans la base de données.

**Signature :**
```python
@trace_action(source="database")
def index_project_files(root_path: str, progress_callback: Optional[Callable[[str], None]] = None, use_semantic_chunking: bool = True) -> str
```

**Arguments :**
*   `root_path` (str): Le chemin racine du projet à indexer.
*   `progress_callback` (Optional[Callable]): Une fonction de rappel optionnelle qui sera appelée avec un message de progrès.
*   `use_semantic_chunking` (bool): Si `True`, tente d'utiliser le chunking sémantique basé sur Tree-sitter pour les fichiers Python. Sinon, utilise un chunking basique par taille.

**Retours :**
*   `str`: Un message de résumé de l'opération d'indexation.

**Logique interne :**
*   Initialise un chunker sémantique si `use_semantic_chunking` est `True` et si `code_chunker` est disponible.
*   Parcourt récursivement le `root_path`, excluant les dossiers de système/cache (ex: `.git`, `__pycache__`, `venv`).
*   Filtre les fichiers par extension (`SUPPORTED_FILE_EXTENSIONS`) et par mots-clés d'exclusion.
*   Pour chaque fichier pertinent :
    *   Lit le contenu et calcule un checksum SHA256.
    *   Récupère ou crée un `file_id` dans la table `files`.
    *   Supprime les anciens chunks du fichier (pour assurer une réindexation propre).
    *   **Chunking** :
        *   Si c'est un fichier Python et que le chunking sémantique est activé, utilise `chunker.chunk_file()`.
        *   Sinon, utilise un chunking basique (découpe le fichier en blocs de texte par taille).
    *   Ajoute chaque chunk à la base de données via `_add_chunk_to_db()`.
    *   Appelle le `progress_callback` périodiquement.
*   Gère les erreurs d'indexation pour des fichiers individuels.

### `delete_local_db()`

Supprime physiquement les fichiers de la base de données (SQLite, FAISS, mapping ID) du disque et réinitialise les structures en mémoire.

**Signature :**
```python
@trace_action(source="database")
def delete_local_db() -> str
```

**Arguments :**
*   Aucun.

**Retours :**
*   `str`: Un message indiquant le succès ou l'échec de la suppression.

**Logique interne :**
*   Réinitialise les variables globales `faiss_index` et `id_mapping` à `None` et `{}`.
*   Tente de supprimer les fichiers `.sqlite`, `.index` et `.pkl` du répertoire de la DB.
*   Appelle `init_db()` juste après pour réinitialiser la DB et éviter des crashs si une opération est lancée juste après la suppression.

### `store_memory(text_content, metadata=None)`

Stocke une information textuelle comme une "mémoire" dans la base de connaissances. Elle sera indexée et pourra être retrouvée via la recherche sémantique.

**Signature :**
```python
@trace_action(source="database")
def store_memory(text_content: str, metadata: Optional[Dict] = None) -> bool
```

**Arguments :**
*   `text_content` (str): Le contenu textuel de la mémoire à stocker.
*   `metadata` (Optional[Dict]): Métadonnées optionnelles associées à la mémoire. Un `memory_id` et le type "memory" seront ajoutés.

**Retours :**
*   `bool`: `True` si la mémoire a été stockée avec succès, `False` sinon.

**Logique interne :**
*   Génère un `memory_id` unique basé sur un hachage MD5 et l'horodatage.
*   Met à jour les métadonnées avec le `memory_id` et le type "memory".
*   Appelle `add_knowledge()` pour insérer la mémoire dans la table `knowledge`.

### `search_memories(query, n_results=3)`

Recherche des "souvenirs" stockés dans la base de données en utilisant la recherche vectorielle, filtrant les résultats pour ne conserver que ceux provenant de la collection "memory://".

**Signature :**
```python
@trace_action(source="database")
def search_memories(query: str, n_results: int = 3) -> List[Tuple]
```

**Arguments :**
*   `query` (str): La requête de recherche en texte clair.
*   `n_results` (int): Le nombre maximum de résultats de mémoire à retourner.

**Retours :**
*   `List[Tuple]`: Une liste de tuples `(source, content, score)` des mémoires trouvées.

**Logique interne :**
*   Appelle `search_vector_db()` pour obtenir des résultats vectoriels bruts.
*   Filtre ces résultats, conservant uniquement ceux dont la source commence par "memory://".
*   Retourne les `n_results` premiers souvenirs filtrés.

### `sync_incremental(root_path: str, progress_callback=None, state_file: str = None)`

Effectue une synchronisation incrémentale des fichiers du projet. Elle utilise un arbre de Merkle pour détecter efficacement les fichiers modifiés et ne ré-indexe que ceux-ci.

**Signature :**
```python
@trace_action(source="database")
def sync_incremental(root_path: str, progress_callback: Optional[Callable[[str], None]] = None, state_file: Optional[str] = None) -> str
```

**Arguments :**
*   `root_path` (str): Le chemin racine du projet à synchroniser.
*   `progress_callback` (Optional[Callable]): Une fonction de rappel optionnelle qui sera appelée avec un message de progrès.
*   `state_file` (Optional[str]): Chemin du fichier JSON où l'état de l'arbre de Merkle est sauvegardé. Si `None`, utilise `db/merkle_state.json`.

**Retours :**
*   `str`: Un message de résumé de l'opération de synchronisation.

**Logique interne :**
*   Importe `MerkleTreeSync` depuis `.merkle_sync`.
*   Construit un nouvel arbre de Merkle pour l'état actuel du projet.
*   Charge l'état de l'arbre de Merkle précédent depuis le `state_file`.
*   Compare les deux arbres pour identifier les fichiers modifiés.
*   Si aucun fichier n'est modifié, retourne un message.
*   Pour chaque fichier modifié :
    *   Calcule son checksum.
    *   Récupère ou crée un `file_id`.
    *   Supprime les anciens chunks du fichier.
    *   Effectue le chunking (sémantique pour Python, basique pour les autres) et ré-indexe les nouveaux chunks via `_add_chunk_to_db()`.
    *   Appelle le `progress_callback` pour les mises à jour de progrès.
*   Sauvegarde le nouvel état de l'arbre de Merkle dans le `state_file`.

## Exemple d'usage

```python
import os
from features.context.database import init_db, index_project_files, search_hybrid, store_memory, search_memories, delete_local_db, sync_incremental

# Assurez-vous que le répertoire de la DB existe
os.makedirs("db", exist_ok=True)

# --- 1. Initialisation de la base de données ---
print("Initialisation de la base de données...")
init_db()
print("Base de données prête.")

# --- 2. Indexation de fichiers de projet (simulés) ---
print("\nCréation de fichiers de projet simulés pour l'indexation...")
project_dir = "temp_project_for_indexing"
os.makedirs(project_dir, exist_ok=True)

# Fichier Python pour tester le chunking sémantique
with open(os.path.join(project_dir, "my_module.py"), "w") as f:
    f.write("""
def factorial(n):
    \"\"\"Calculates the factorial of a number.\"\"\"
    if n == 0:
        return 1
    else:
        return n * factorial(n-1)

class MyClass:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value
""")

# Fichier texte générique pour tester le chunking basique
with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
    f.write("numpy\nscipy\npandas\nmatplotlib\nrequests\nbeautifulsoup4\nflask\ndjango")

def progress_display(msg):
    print(f"Progression: {msg}")

print(f"Indexation des fichiers dans {project_dir}...")
result_indexing = index_project_files(project_dir, progress_callback=progress_display, use_semantic_chunking=True)
print(result_indexing)

# --- 3. Recherche Hybride ---
print("\nRecherche hybride pour 'factorial function'...")
results, error = search_hybrid("factorial function", max_results=3)
if error:
    print(f"Erreur de recherche: {error}")
else:
    for source, content, score, ast_type, parent_context, start_line, end_line in results:
        print(f"--- Résultat (Score: {score:.4f}) ---")
        print(f"Source: {source} (L{start_line}-{end_line})")
        print(f"Type AST: {ast_type}, Contexte Parent: {parent_context}")
        print(f"Contenu: {content[:150]}...")
        print("-" * 20)

print("\nRecherche hybride pour 'database connection' (devrait retourner moins de choses pour un projet simple)...")
results, error = search_hybrid("database connection", max_results=2)
if error:
    print(f"Erreur de recherche: {error}")
else:
    for source, content, score, ast_type, parent_context, start_line, end_line in results:
        print(f"--- Résultat (Score: {score:.4f}) ---")
        print(f"Source: {source} (L{start_line}-{end_line})")
        print(f"Type AST: {ast_type}, Contexte Parent: {parent_context}")
        print(f"Contenu: {content[:150]}...")
        print("-" * 20)

# --- 4. Stockage et recherche de mémoires ---
print("\nStockage d'une mémoire...")
store_memory("Je dois me souvenir d'utiliser un cache pour les requêtes API récurrentes.", metadata={"topic": "optimization"})
store_memory("La fonction de vérification d'authentification se trouve dans le module users.auth.", metadata={"topic": "code_structure"})
print("Mémoires stockées.")

print("\nRecherche de mémoires sur 'cache'...")
memories = search_memories("cache API requests", n_results=2)
if memories:
    for source, content, score in memories:
        print(f"--- Mémoire (Score: {score:.4f}) ---")
        print(f"ID: {source.split('//')[1]}")
        print(f"Contenu: {content}")
        print("-" * 20)
else:
    print("Aucune mémoire trouvée pour 'cache'.")

# --- 5. Synchronisation incrémentale ---
print("\nModification d'un fichier et sync incrémentale...")
with open(os.path.join(project_dir, "my_module.py"), "a") as f:
    f.write("\n\ndef new_feature():\n    return 'Hello from new feature'")

result_sync = sync_incremental(project_dir, progress_callback=progress_display)
print(result_sync)

# Vérifier que la nouvelle feature est indexée
print("\nRecherche de 'new_feature' après sync...")
results, error = search_hybrid("new_feature", max_results=1)
if error:
    print(f"Erreur de recherche: {error}")
else:
    for source, content, score, ast_type, parent_context, start_line, end_line in results:
        print(f"--- Résultat (Score: {score:.4f}) ---")
        print(f"Source: {source} (L{start_line}-{end_line})")
        print(f"Type AST: {ast_type}, Contexte Parent: {parent_context}")
        print(f"Contenu: {content[:150]}...")
        print("-" * 20)


# --- 6. Nettoyage ---
print("\nNettoyage de la base de données et des fichiers de test...")
delete_local_db()
shutil.rmtree(project_dir)
print("Nettoyage terminé.")