# `features/context/repo_map.py` - Documentation Technique

## 1. En-tête

*   **Titre**: Module de Génération de la Repo Map
*   **Description concise**: Ce module est responsable de la création d'une "Repo Map", une carte structurelle compressée d'un dépôt de code. Il extrait uniquement les signatures (fonctions, classes, méthodes) des fichiers les plus pertinents pour les injecter dans le contexte d'un modèle de langage (LLM), facilitant ainsi sa compréhension de la structure du projet sans le corps du code.
*   **Dépendances**:
    *   `os`: Opérations système, notamment la manipulation des chemins de fichiers.
    *   `logging`: Enregistrement des logs via une instance de logger configurée.
    *   `typing.List`, `typing.Dict`, `typing.Optional`: Support des annotations de type.
    *   `config.get_logger`: Fonction utilitaire pour obtenir un logger configuré.
    *   `config.get_path`: Fonction utilitaire pour obtenir un chemin absolu.
    *   `features.Decorators.trace_action`: Décorateur pour tracer les actions et mesurer les performances.
    *   `features.context.symbol_graph`: Importé localement dans `generate_repo_map` pour obtenir le graphe de symboles et les fichiers centraux.
    *   `features.context.code_chunker`: Importé localement dans `_extract_signatures` pour le parsing AST et l'extraction de signatures.

## 2. Classes & Fonctions

### `class RepoMapGenerator`

Générateur de Repo Map : carte structurelle compressée du projet.

#### `__init__(self, db_path_base=None)`

Initialise le générateur de Repo Map.

*   **Signature**: `__init__(self, db_path_base=None)`
*   **Arguments**:
    *   `db_path_base` (str, optional): Chemin de base vers le répertoire où la base de données ou les ressources de graphe de symboles sont stockées. Par défaut à `None`.
*   **Logique interne**:
    *   Stocke le chemin de base de la base de données dans l'attribut `self.db_path_base`.

#### `@trace_action(source="repo_map")`
#### `generate_repo_map(self, top_n: int = 20) -> str`

Génère la Repo Map en extrayant les signatures des fichiers les plus importants du dépôt. Les fichiers sont classés par leur score PageRank obtenu via le graphe de symboles.

*   **Signature**: `generate_repo_map(self, top_n: int = 20) -> str`
*   **Arguments**:
    *   `top_n` (int): Nombre de fichiers les plus importants (selon leur score PageRank) à inclure dans la Repo Map. Par défaut à `20`.
*   **Retours**:
    *   `str`: La Repo Map formatée en texte, incluant les signatures des classes et fonctions/méthodes des fichiers sélectionnés. Retourne une chaîne vide si aucun fichier n'est trouvé.
*   **Logique interne**:
    1.  Importe `get_symbol_graph` depuis `features.context.symbol_graph`.
    2.  Obtient une instance du graphe de symboles en utilisant `self.db_path_base`.
    3.  Récupère les `top_n` fichiers les plus centraux du graphe de symboles, avec leurs scores PageRank.
    4.  Si aucun fichier n'est trouvé, enregistre un avertissement et retourne une chaîne vide.
    5.  Initialise une liste `repo_map_lines` et ajoute un titre.
    6.  Pour chaque fichier (`file_path`, `pagerank_score`) dans les `top_files`:
        *   Convertit `file_path` en chemin absolu.
        *   Vérifie l'existence du fichier.
        *   Appelle `_extract_signatures` pour obtenir les données de signatures du fichier.
        *   Si des signatures sont extraites:
            *   Ajoute une ligne d'en-tête pour le fichier avec son score PageRank.
            *   Organise les signatures en classes et fonctions globales.
            *   Ajoute les signatures des classes avec leurs méthodes (indentées) et docstrings.
            *   Ajoute les signatures des fonctions globales avec leurs docstrings.
    7.  Assemble toutes les lignes en une seule chaîne de caractères, séparées par des retours à la ligne.
    8.  Enregistre un message d'information sur la réussite de la génération et retourne la Repo Map.

#### `_extract_signatures(self, file_path: str) -> List[Dict[str, str]]`

Extrait les signatures enrichies (incluant paramètres, types, docstrings) d'un fichier Python en utilisant l'AST (Abstract Syntax Tree).

*   **Signature**: `_extract_signatures(self, file_path: str) -> List[Dict[str, str]]`
*   **Arguments**:
    *   `file_path` (str): Le chemin absolu du fichier Python à analyser.
*   **Retours**:
    *   `List[Dict[str, str]]`: Une liste de dictionnaires. Chaque dictionnaire représente une signature de classe ou de fonction/méthode et contient les clés suivantes :
        *   `signature` (str): La signature complète (ex: `def func(arg: Type) -> ReturnType:`).
        *   `parent` (str): Le parent de la signature (ex: `"Fichier: file.py"`, `"Fichier: file.py > Classe: MyClass"`).
        *   `ast_type` (str): Le type d'élément AST (`'class'`, `'function'`, `'method'`).
        *   `docstring` (str): La première ligne de la docstring (si présente).
        *   `name` (str): Le nom de la classe/fonction.
        *   `methods` (List[Dict]): Pour les classes, une liste de dictionnaires représentant les méthodes de la classe.
        *   `class` (str, optional): Pour les méthodes, le nom de la classe parente.
*   **Logique interne**:
    1.  Vérifie si le fichier est un fichier Python (se termine par `.py`).
    2.  Importe `get_chunker` depuis `features.context.code_chunker`.
    3.  Obtient un "chunker" qui encapsule un parser Tree-sitter.
    4.  Si le parser n'est pas disponible, utilise la méthode de fallback `_extract_signatures_basic_enriched`.
    5.  Lit le contenu du fichier Python.
    6.  Parse le code source en un AST en utilisant le parser Tree-sitter.
    7.  Définit une fonction récursive interne `traverse_node(node, parent_class=None)` pour parcourir l'AST:
        *   Lorsqu'un nœud `class_definition` est rencontré, extrait sa signature, son nom et sa docstring. Stocke les informations de la classe et initialise une liste `methods` vide. Ensuite, traverse le corps de la classe pour trouver les méthodes.
        *   Lorsqu'un nœud `function_definition` est rencontré, extrait sa signature, son nom et sa docstring. Filtre les fonctions triviales en utilisant `_is_trivial_function`. Si c'est une méthode (détectée par `parent_class`), l'ajoute à la liste `methods` de la classe parente. Sinon, l'ajoute comme fonction globale.
        *   Parcourt récursivement les enfants des autres nœuds.
    8.  Appelle `traverse_node` sur le nœud racine de l'AST.
    9.  Organise les résultats finaux en une liste où les classes avec leurs méthodes sont ajoutées en premier, suivies des fonctions globales.
    10. En cas d'erreur lors de l'extraction AST, enregistre un avertissement et utilise la méthode de fallback.

#### `_is_trivial_function(self, func_node, source_bytes: bytes, func_name: str) -> bool`

Détecte si une fonction est triviale (ex: wrapper simple, accesseur, fonction vide).

*   **Signature**: `_is_trivial_function(self, func_node, source_bytes: bytes, func_name: str) -> bool`
*   **Arguments**:
    *   `func_node`: Le nœud AST de la fonction.
    *   `source_bytes` (bytes): Le code source du fichier sous forme d'octets.
    *   `func_name` (str): Le nom de la fonction.
*   **Retours**:
    *   `bool`: `True` si la fonction est considérée comme triviale, `False` sinon.
*   **Logique interne**:
    1.  Trouve le corps de la fonction (le nœud `block` enfant).
    2.  Si le corps est vide, la fonction est triviale.
    3.  Compte le nombre de déclarations non-triviales dans le corps. Ignore les docstrings et `pass`.
    4.  Si le nombre de déclarations non-triviales est inférieur à 2, ou si le corps est très court et correspond à des patterns de fonctions triviales (getters/setters simples, wrappers), la fonction est considérée comme triviale.

#### `_get_node_text(self, node, source_bytes: bytes) -> bytes`

Fonction utilitaire pour extraire le texte correspondant à un nœud AST.

*   **Signature**: `_get_node_text(self, node, source_bytes: bytes) -> bytes`
*   **Arguments**:
    *   `node`: Le nœud AST.
    *   `source_bytes` (bytes): Le code source du fichier sous forme d'octets.
*   **Retours**:
    *   `bytes`: Le texte du code source correspondant à la portée du nœud.
*   **Logique interne**:
    1.  Tente d'utiliser la méthode `_get_node_text` du `code_chunker` pour une extraction robuste.
    2.  En cas d'échec ou d'indisponibilité, utilise une extraction basique par découpage d'octets.

#### `_extract_docstring_from_function(self, func_node, source_bytes: bytes) -> str`

Extrait la première ligne d'une docstring d'une fonction.

*   **Signature**: `_extract_docstring_from_function(self, func_node, source_bytes: bytes) -> str`
*   **Arguments**:
    *   `func_node`: Le nœud AST de la fonction.
    *   `source_bytes` (bytes): Le code source du fichier sous forme d'octets.
*   **Retours**:
    *   `str`: La première ligne nettoyée de la docstring, tronquée si trop longue. Retourne une chaîne vide si aucune docstring n'est trouvée.
*   **Logique interne**:
    1.  Recherche le corps de la fonction.
    2.  Si le premier statement du corps est une expression de type `string`, extrait le texte, le nettoie et en retourne la première ligne.

#### `_extract_docstring_from_class(self, class_node, source_bytes: bytes) -> str`

Extrait la première ligne d'une docstring d'une classe.

*   **Signature**: `_extract_docstring_from_class(self, class_node, source_bytes: bytes) -> str`
*   **Arguments**:
    *   `class_node`: Le nœud AST de la classe.
    *   `source_bytes` (bytes): Le code source du fichier sous forme d'octets.
*   **Retours**:
    *   `str`: La première ligne nettoyée de la docstring, tronquée si trop longue. Retourne une chaîne vide si aucune docstring n'est trouvée.
*   **Logique interne**:
    1.  Recherche le corps de la classe.
    2.  Si le premier statement du corps est une expression de type `string`, extrait le texte, le nettoie et en retourne la première ligne.

#### `_extract_signatures_basic_enriched(self, file_path: str) -> List[Dict[str, str]]`

Méthode de fallback pour l'extraction basique de signatures si le parsing AST échoue ou n'est pas disponible. Moins précise mais plus robuste face à des erreurs syntaxiques.

*   **Signature**: `_extract_signatures_basic_enriched(self, file_path: str) -> List[Dict[str, str]]`
*   **Arguments**:
    *   `file_path` (str): Chemin du fichier Python.
*   **Retours**:
    *   `List[Dict[str, str]]`: Une liste de dictionnaires de signatures basiques.
*   **Logique interne**:
    1.  Lit le fichier ligne par ligne.
    2.  Détecte les lignes commençant par `class ` ou `def ` pour extraire des signatures simples.
    3.  Tente de déterminer si une fonction appartient à une classe en suivant le contexte.
    4.  Retourne une liste de dictionnaires avec les informations de signature de base.

#### `@trace_action(source="repo_map")`
#### `get_repo_map(self) -> str`

Retourne la Repo Map complète pour un usage interne ou de cache, sans limite de taille.

*   **Signature**: `get_repo_map(self) -> str`
*   **Arguments**: Aucun.
*   **Retours**:
    *   `str`: La Repo Map complète générée.
*   **Logique interne**:
    1.  Appelle `generate_repo_map()` pour générer la carte sans spécifier `top_n` (ce qui utilise la valeur par défaut `20`).

#### `@trace_action(source="repo_map")`
#### `get_repo_map_for_context(self, max_chars: Optional[int] = None) -> str`

Retourne la Repo Map formatée et potentiellement tronquée pour une injection dans le contexte d'un LLM.

*   **Signature**: `get_repo_map_for_context(self, max_chars: Optional[int] = None) -> str`
*   **Arguments**:
    *   `max_chars` (int, optional): Le nombre maximum de caractères souhaité pour la Repo Map. Si `None`, aucune troncature n'est effectuée.
*   **Retours**:
    *   `str`: La Repo Map générée, tronquée à `max_chars` si spécifié et la taille est dépassée, avec une indication de troncature.
*   **Logique interne**:
    1.  Appelle `generate_repo_map()` pour obtenir la Repo Map.
    2.  Si `max_chars` est spécifié et que la longueur de la Repo Map dépasse cette limite, tronque la chaîne et ajoute `\n... (tronqué)`.
    3.  Retourne la Repo Map (complète ou tronquée).

### `get_repo_map_generator(db_path_base=None) -> RepoMapGenerator`

Fonction utilitaire pour obtenir l'instance singleton du générateur de Repo Map.

*   **Signature**: `get_repo_map_generator(db_path_base=None) -> RepoMapGenerator`
*   **Arguments**:
    *   `db_path_base` (str, optional): Chemin de base de la base de données, passé lors de la première initialisation.
*   **Retours**:
    *   `RepoMapGenerator`: L'instance unique du générateur de Repo Map.
*   **Logique interne**:
    1.  Vérifie si l'instance globale `_repo_map_generator` est déjà initialisée.
    2.  Si non, crée une nouvelle instance de `RepoMapGenerator` avec le `db_path_base fourni` et l'assigne à `_repo_map_generator`.
    3.  Retourne l'instance (existante ou nouvellement créée).

## 3. Exemple d'usage

```python
from features.context.repo_map import get_repo_map_generator

# Supposons que votre chemin de base de données est connu
# C'est souvent le chemin racine de votre dépôt ou un répertoire de configuration
db_base_path = "/chemin/vers/votre/depot" 

# Obtenir l'instance du générateur de Repo Map (singleton)
repo_map_generator = get_repo_map_generator(db_base_path)

# Générer la Repo Map pour le contexte LLM, avec une limite de caractères
# Par exemple, 4000 caractères pour s'adapter à la fenêtre contextuelle d'un LLM
repo_map_for_llm = repo_map_generator.get_repo_map_for_context(max_chars=4000)

print("--- Repo Map pour Contexte LLM ---")
print(repo_map_for_llm)
print(f"\nTaille de la Repo Map : {len(repo_map_for_llm)} caractères")

# Générer la Repo Map complète (sans limite)
full_repo_map = repo_map_generator.get_repo_map()

# Cette carte peut être utilisée pour un cache ou une analyse plus approfondie
# print("\n--- Repo Map complète ---")
# print(full_repo_map)
# print(f"\nTaille de la Repo Map complète : {len(full_repo_map)} caractères")