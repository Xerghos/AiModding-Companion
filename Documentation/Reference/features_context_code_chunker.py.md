# Documentation Technique pour `features\context\code_chunker.py`

## 1. En-tête

*   **Titre**: `features\context\code_chunker.py`
*   **Description concise**: Ce module implémente un système de "chunking" sémantique pour le code Python, utilisant la bibliothèque Tree-sitter pour analyser la structure de l'arbre syntaxique abstrait (AST). Il découpe le code source en segments logiques (chunks) basés sur des entités sémantiques comme les classes, les fonctions et les blocs de code, afin d'améliorer la pertinence contextuelle pour les traitements ultérieurs (ex: LLMs). Un mécanisme de fallback basique est fourni si Tree-sitter n'est pas disponible ou échoue.
*   **Dépendances**:
    *   `os`: Opérations sur le système de fichiers.
    *   `logging`: Pour la journalisation des événements et erreurs.
    *   `typing`: Pour les annotations de type (`List`, `Dict`, `Optional`, `Tuple`).
    *   `config.get_logger`: Utilitaire pour obtenir une instance de logger configurée.
    *   `features.Decorators.trace_action`: Décorateur pour tracer l'exécution des fonctions.
    *   `tree_sitter` (conditionnel): Bibliothèque principale pour l'analyse syntaxique.
    *   `tree_sitter.Language`, `tree_sitter.Parser` (conditionnel): Classes spécifiques de Tree-sitter.
    *   `tree_sitter_python` (conditionnel): Module de langage Tree-sitter pour Python (tentative prioritaire).
    *   `tree_sitter_language_pack` (conditionnel): Module alternatif de langage Tree-sitter pour Python.

## 2. Classes & Fonctions

### Constantes Globales

*   **`MIN_CHUNK_SIZE`**
    *   **Description**: Taille minimale (en caractères) d'un chunk pour être considéré valide. Les chunks plus petits sont généralement ignorés ou fusionnés.
    *   **Valeur**: 50
*   **`MAX_CHUNK_SIZE`**
    *   **Description**: Taille maximale (en caractères) souhaitée pour un chunk. Utilisée principalement dans le chunking basique de fallback.
    *   **Valeur**: 2000
*   **`MAX_FUNCTION_SIZE`**
    *   **Description**: Taille maximale (en caractères) d'une fonction avant qu'elle ne soit divisée en sous-chunks.
    *   **Valeur**: 1500

### Classe `SemanticChunker`

Chunker sémantique utilisant Tree-sitter pour découper le code Python en chunks intelligents basés sur la structure AST.

#### Méthodes

*   **`__init__(self)`**
    *   **Description**: Initialise le `SemanticChunker`, tentant de configurer Tree-sitter pour l'analyse du code Python.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
    *   **Retours**: `None`
    *   **Logique interne**:
        *   Initialise `self.parser` et `self.language` à `None`.
        *   Définit `self.is_available` à `False` initialement.
        *   Appelle `_init_tree_sitter()` pour tenter d'activer le chunking sémantique.

*   **`_init_tree_sitter(self)` (privée)**
    *   **Description**: Tente d'initialiser Tree-sitter et le parseur pour le langage Python. Gère les cas où Tree-sitter n'est pas installé ou les modules de langage Python ne sont pas disponibles/compatibles.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
    *   **Retours**: `None`
    *   **Logique interne**:
        *   Vérifie si `TREE_SITTER_AVAILABLE` est `False` (si l'import initial de `tree_sitter` a échoué). Si oui, désactive le chunking sémantique et logue un avertissement.
        *   Tente d'importer et de charger le langage Python via `tree_sitter_python`. Si échec (ImportError ou `PyCapsule` incompatible), tente `tree_sitter_language_pack`.
        *   Si un langage est chargé avec succès, tente de créer un `Parser` Tree-sitter.
        *   Si la création du `Parser` échoue (notamment si `self.language` est un `PyCapsule` incompatible), désactive le chunking sémantique et logue un avertissement ou une erreur.
        *   Définit `self.is_available` à `True` si l'initialisation complète est réussie, `False` sinon.
        *   Fournit des instructions d'installation si aucun des modules de langage n'est trouvé.

*   **`_query_ast(self, tree, query_string: str) -> List` (privée)**
    *   **Description**: Exécute une requête Tree-sitter sur l'arbre syntaxique abstrait (AST) fourni.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `tree`: L'objet `tree_sitter.Tree` sur lequel exécuter la requête.
        *   `query_string` (`str`): La chaîne de requête Tree-sitter.
    *   **Retours**: `List[Tuple[tree_sitter.Node, str]]` - Une liste de tuples, chaque tuple contenant un nœud AST et le nom de la capture correspondante.
    *   **Logique interne**:
        *   Vérifie la disponibilité du parseur.
        *   Crée un objet `tree_sitter.Query` à partir de la chaîne de requête et du langage Python.
        *   Utilise `tree_sitter.QueryCursor` pour exécuter la requête sur le nœud racine de l'arbre.
        *   Convertit le dictionnaire de captures en une liste de tuples `(node, capture_name)`.
        *   Gère les exceptions lors de l'exécution de la requête.

*   **`_get_node_text(self, node, source_code: bytes) -> str` (privée)**
    *   **Description**: Extrait la portion de texte source correspondant à un nœud AST donné.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `node`: Le nœud `tree_sitter.Node` dont le texte doit être extrait.
        *   `source_code` (`bytes`): Le code source complet du fichier, encodé en octets.
    *   **Retours**: `str` - La chaîne de caractères du code correspondant au nœud.
    *   **Logique interne**:
        *   Utilise `node.start_byte` et `node.end_byte` pour découper la portion pertinente des octets sources et la décode en UTF-8.

*   **`_get_node_lines(self, node) -> Tuple[int, int]` (privée)**
    *   **Description**: Retourne les numéros de ligne de début et de fin (1-indexés) d'un nœud AST.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `node`: Le nœud `tree_sitter.Node`.
    *   **Retours**: `Tuple[int, int]` - Un tuple `(start_line, end_line)`.
    *   **Logique interne**:
        *   Convertit les points de début et de fin du nœud (0-indexés par Tree-sitter) en numéros de ligne 1-indexés.

*   **`_extract_class_signature(self, class_node, source_code: bytes) -> Optional[str]` (privée)**
    *   **Description**: Extrait une représentation concise de la signature d'une classe, incluant son nom, ses bases d'héritage et une partie de sa docstring.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `class_node`: Le nœud AST représentant la définition de la classe.
        *   `source_code` (`bytes`): Le code source complet encodé.
    *   **Retours**: `Optional[str]` - La signature de la classe sous forme de chaîne, ou `None` si l'extraction échoue.
    *   **Logique interne**:
        *   Recherche l'identifiant de la classe et les bases d'héritage dans les enfants du nœud `class_node`.
        *   Extrait la docstring si elle est présente en tant que première instruction dans le bloc de la classe.
        *   Construit une chaîne de signature formatée.

*   **`_extract_function_signature(self, func_node, source_code: bytes) -> Optional[str]` (privée)**
    *   **Description**: Extrait une représentation concise de la signature d'une fonction ou méthode, incluant son nom et ses paramètres.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `func_node`: Le nœud AST représentant la définition de la fonction.
        *   `source_code` (`bytes`): Le code source complet encodé.
    *   **Retours**: `Optional[str]` - La signature de la fonction sous forme de chaîne, ou `None` si l'extraction échoue.
    *   **Logique interne**:
        *   Recherche l'identifiant de la fonction et les paramètres dans les enfants du nœud `func_node`.
        *   Gère les paramètres typés.
        *   Construit une chaîne de signature formatée.

*   **`_build_parent_context(self, node, source_code: bytes, file_path: str) -> str` (privée)**
    *   **Description**: Construit une chaîne de contexte hiérarchique pour un nœud donné (ex: "Fichier: mon_fichier.py > Classe: MaClasse > Méthode: ma_methode").
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `node`: Le nœud AST pour lequel construire le contexte.
        *   `source_code` (`bytes`): Le code source complet encodé.
        *   `file_path` (`str`): Le chemin complet du fichier source.
    *   **Retours**: `str` - La chaîne de contexte hiérarchique.
    *   **Logique interne**:
        *   Commence par le nom du fichier.
        *   Remonte l'arbre AST à partir du nœud parent, en collectant les noms des classes parentes rencontrées.
        *   Assemble les parties du contexte avec " > ".

*   **`_chunk_node(self, node, source_code: bytes, file_path: str, parent_context: str = "", ast_type: str = "") -> Optional[Dict]` (privée)**
    *   **Description**: Crée un dictionnaire de chunk à partir d'un nœud AST donné, en y ajoutant le contenu enrichi et les métadonnées.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `node`: Le nœud AST à convertir en chunk.
        *   `source_code` (`bytes`): Le code source complet encodé.
        *   `file_path` (`str`): Le chemin du fichier source.
        *   `parent_context` (`str`, optionnel): Le contexte parent pré-construit (si déjà disponible).
        *   `ast_type` (`str`, optionnel): Le type AST du nœud (ex: 'function', 'class').
    *   **Retours**: `Optional[Dict]` - Un dictionnaire représentant le chunk, ou `None` si le texte du nœud est trop court.
    *   **Logique interne**:
        *   Extrait le texte et les lignes du nœud.
        *   Vérifie si la taille du texte est supérieure à `MIN_CHUNK_SIZE`.
        *   Construit le contexte parent si non fourni.
        *   Formate le `content` du chunk avec un "Sticky Header" (`parent_context` + `node_text`).
        *   Retourne un dictionnaire avec `content`, `start_line`, `end_line`, `ast_type`, `parent_context` et `raw_content`.

*   **`_chunk_large_function(self, func_node, source_code: bytes, file_path: str, parent_context: str) -> List[Dict]` (privée)**
    *   **Description**: Divise le corps d'une fonction trop grande en plusieurs sous-chunks, en incluant la signature de la fonction dans chaque sous-chunk.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `func_node`: Le nœud AST représentant la fonction.
        *   `source_code` (`bytes`): Le code source complet encodé.
        *   `file_path` (`str`): Le chemin du fichier source.
        *   `parent_context` (`str`): Le contexte parent de la fonction.
    *   **Retours**: `List[Dict]` - Une liste de dictionnaires représentant les sous-chunks.
    *   **Logique interne**:
        *   Extrait le nœud du corps de la fonction.
        *   Extrait la signature de la fonction.
        *   Itère sur les instructions (statements) du corps de la fonction.
        *   Accumule les instructions dans un `current_chunk_lines`.
        *   Si l'ajout d'une instruction ferait dépasser `MAX_FUNCTION_SIZE` au `current_chunk_lines`, un chunk est créé à partir des lignes accumulées et un nouveau `current_chunk_lines` est commencé.
        *   Chaque sous-chunk inclut le `parent_context` et la `signature` de la fonction.

*   **`chunk_file(self, file_path: str) -> List[Dict]` (publique)**
    *   **Description**: La méthode principale pour découper un fichier Python en chunks sémantiques. Applique une stratégie "Coarse-to-Fine".
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `file_path` (`str`): Le chemin complet du fichier Python à chunker.
    *   **Retours**: `List[Dict]` - Une liste de dictionnaires, chaque dictionnaire représentant un chunk avec son contenu et ses métadonnées.
    *   **Logique interne**:
        *   Décorée avec `@trace_action` pour le suivi.
        *   Vérifie l'existence du fichier.
        *   Si Tree-sitter n'est pas disponible (`self.parser` ou `self.language` est `None`), délègue au `_chunk_basic` de fallback.
        *   Lit le fichier, parse le code en AST avec Tree-sitter.
        *   Exécute une requête AST pour trouver les définitions de classes et de fonctions.
        *   **Stratégie Coarse-to-Fine**:
            1.  **Niveau Macro**: Crée des chunks pour les signatures de classes (sans leur corps), fournissant une vue d'ensemble.
            2.  **Niveau Micro**: Crée des chunks pour les fonctions et méthodes complètes. Si une fonction dépasse `MAX_FUNCTION_SIZE`, elle est divisée en plusieurs sous-chunks à l'aide de `_chunk_large_function`.
        *   **Code orphelin**: Tente d'identifier et de chunker le code en haut du fichier qui n'appartient pas à une classe ou fonction (ex: imports, constantes globales).
        *   Logue le nombre de chunks créés.
        *   En cas d'erreur avec Tree-sitter, effectue un fallback vers `_chunk_basic`.

*   **`_chunk_basic(self, file_path: str) -> List[Dict]` (privée)**
    *   **Description**: Méthode de chunking basique utilisée comme fallback lorsque Tree-sitter n'est pas disponible ou échoue. Elle découpe le fichier par lignes, en regroupant les lignes pour former des chunks de taille raisonnable, en respectant les lignes vides comme séparateurs potentiels.
    *   **Arguments**:
        *   `self`: L'instance de la classe.
        *   `file_path` (`str`): Le chemin du fichier à chunker.
    *   **Retours**: `List[Dict]` - Une liste de dictionnaires représentant les chunks.
    *   **Logique interne**:
        *   Lit toutes les lignes du fichier.
        *   Itère sur les lignes, accumulant les `current_chunk` de lignes.
        *   Crée un nouveau chunk si la taille accumulée dépasse `MAX_CHUNK_SIZE` ou si une ligne vide est rencontrée après avoir accumulé au moins `MIN_CHUNK_SIZE` de contenu.
        *   Ajoute un dernier chunk si des lignes sont encore en attente après la boucle.
        *   Chaque chunk a un `ast_type` de 'text_block' et un `parent_context` basique.
        *   Gère les exceptions de lecture ou de traitement du fichier.

### Fonction Globale

*   **`get_chunker() -> SemanticChunker`**
    *   **Description**: Fournit un accès à une instance singleton du `SemanticChunker`. Cela garantit qu'une seule instance du chunker est créée et que Tree-sitter n'est initialisé qu'une seule fois.
    *   **Arguments**: `None`
    *   **Retours**: `SemanticChunker` - L'instance unique du chunker.
    *   **Logique interne**:
        *   Utilise une variable globale `_chunker_instance`.
        *   Si `_chunker_instance` est `None`, crée une nouvelle instance de `SemanticChunker` et la stocke.
        *   Logue l'état d'initialisation (Tree-sitter activé ou fallback).
        *   Retourne l'instance existante ou nouvellement créée.

## 3. Exemple d'usage

```python
import os
from features.context.code_chunker import get_chunker

# Créer un fichier Python temporaire pour l'exemple
temp_file_path = "temp_example_code.py"
example_code = """
\"\"\"
Ceci est un module d'exemple pour le chunking.
Il contient une classe et une fonction autonome.
\"\"\"

import sys
import os

MIN_VALUE = 0
MAX_VALUE = 100

class MyProcessor:
    \"\"\"
    Cette classe gère le traitement des données.
    \"\"\"
    def __init__(self, data: list):
        self.data = data
        self.processed_count = 0

    def process_item(self, item: int) -> int:
        \"\"\"
        Traite un seul élément de donnée.
        Vérifie les limites et incrémente le compteur.
        \"\"\"
        if item < MIN_VALUE:
            return MIN_VALUE
        elif item > MAX_VALUE:
            return MAX_VALUE
        else:
            self.processed_count += 1
            return item * 2

    def get_processed_count(self) -> int:
        \"\"\"
        Retourne le nombre d'éléments traités.
        \"\"\"
        return self.processed_count

def run_analysis(items: List[int]) -> List[int]:
    \"\"\"
    Exécute une analyse complète sur une liste d'éléments.
    \"\"\"
    processor = MyProcessor(items)
    results = []
    for item in items:
        processed = processor.process_item(item)
        results.append(processed)
    return results

if __name__ == "__main__":
    print("Démarrage de l'analyse...")
    test_data = [1, 50, 101, -5, 75]
    analysis_results = run_analysis(test_data)
    print(f"Données originales: {test_data}")
    print(f"Résultats d'analyse: {analysis_results}")
    print("Analyse terminée.")
"""

with open(temp_file_path, "w", encoding="utf-8") as f:
    f.write(example_code)

# Obtenir l'instance singleton du chunker
chunker = get_chunker()

# Chunker le fichier
chunks = chunker.chunk_file(temp_file_path)

print(f"\n--- Chunks générés pour '{temp_file_path}' ({len(chunks)} chunks) ---")
for i, chunk in enumerate(chunks):
    print(f"\nChunk {i+1} (Lignes {chunk['start_line']}-{chunk['end_line']}, Type: {chunk['ast_type']}):")
    print(f"  Parent Context: {chunk['parent_context']}")
    print("  Content:")
    # Afficher les 200 premiers caractères du contenu pour éviter l'encombrement
    print(f"    {chunk['content'][:200]}...") 
    # print(chunk['content']) # Décommenter pour voir le contenu complet

# Nettoyer le fichier temporaire
os.remove(temp_file_path)

"""
Exemple de sortie (peut varier légèrement selon l'implémentation de Tree-sitter et les versions):

--- Chunks générés pour 'temp_example_code.py' (5 chunks) ---

Chunk 1 (Lignes 1-7, Type: module_header):
  Parent Context: Fichier: temp_example_code.py
  Content:
    """
Ceci est un module d'exemple pour le chunking.
Il contient une classe et une fonction autonome.
"""

import sys
import os

MIN_VALUE = 0
MAX_VALUE = 100...

Chunk 2 (Lignes 9-11, Type: class_signature):
  Parent Context: Fichier: temp_example_code.py
  Content:
    Fichier: temp_example_code.py > Classe: MyProcessor
    class MyProcessor
        """Cette classe gère le traitement des données."""...

Chunk 3 (Lignes 12-14, Type: method):
  Parent Context: Fichier: temp_example_code.py > Classe: MyProcessor
  Content:
    Fichier: temp_example_code.py > Classe: MyProcessor > def __init__(self, data)
    def __init__(self, data: list):
        self.data = data
        self.processed_count = 0...

Chunk 4 (Lignes 16-27, Type: method):
  Parent Context: Fichier: temp_example_code.py > Classe: MyProcessor
  Content:
    Fichier: temp_example_code.py > Classe: MyProcessor > def process_item(self, item)
    def process_item(self, item: int) -> int:
        """
        Traite un seul élément de donnée.
        Vérifie les limites et incrémente le compteur.
        """
        if item < MIN_VALUE:
            return MIN_VALUE
        elif item > MAX_VALUE:
            return MAX_VALUE
        else:
            self.processed_count += 1
            return item * 2...

Chunk 5 (Lignes 29-37, Type: function):
  Parent Context: Fichier: temp_example_code.py
  Content:
    Fichier: temp_example_code.py > def run_analysis(items)
    def run_analysis(items: List[int]) -> List[int]:
        """
        Exécute une analyse complète sur une liste d'éléments.
        """
        processor = MyProcessor(items)
        results = []
        for item in items:
            processed = processor.process_item(item)
            results.append(processed)
        return results...
"""