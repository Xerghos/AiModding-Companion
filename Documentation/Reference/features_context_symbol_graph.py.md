# Documentation Technique - `features\context\symbol_graph.py`

Ce module est responsable de la construction et de la gestion d'un graphe de symboles pour un projet donné. Il utilise la bibliothèque `networkx` pour représenter les dépendances entre les fichiers Python, calculer le PageRank et identifier les fichiers les plus centraux ou influents au sein du projet. L'extraction des dépendances est basée sur une analyse basique du code source et peut être complétée par des outils d'analyse syntaxique plus avancés comme Tree-sitter pour une précision accrue.

## Dépendances

*   **Standard Library**: `os`, `logging`, `sqlite3`, `re`, `typing` (Dict, List, Optional, Tuple)
*   **Modules Internes**:
    *   `config`: Pour `get_logger`, `get_path`.
    *   `features.Decorators`: Pour `trace_action`.
    *   `features.context.database`: Pour `_get_paths` (importé localement dans `build_graph_from_db`).
*   **Bibliothèques Tierces**:
    *   `networkx` (installé optionnellement) : Utilisé pour la création et la manipulation du graphe, ainsi que le calcul du PageRank. Le module gère son absence avec une dégradation des fonctionnalités.

---

## Classes & Fonctions

### Variables Globales

*   `log`: `logging.Logger`
    *   Instance du logger configurée pour le module `features.context.symbol_graph`.
*   `NETWORKX_AVAILABLE`: `bool`
    *   Indicateur `True` si la bibliothèque `networkx` a été importée avec succès, `False` sinon.
*   `_symbol_graph_instance`: `Optional[SymbolGraph]`
    *   Instance singleton du graphe de symboles.

---

### `class SymbolGraph`

Gestionnaire du graphe de symboles du projet.

Cette classe construit et manipule un graphe dirigé où les nœuds représentent des fichiers et les arêtes représentent des dépendances (par exemple, des imports). Elle utilise NetworkX pour des analyses graphiques, notamment le calcul du PageRank.

#### `__init__(self, db_path_base=None)`

Initialise une nouvelle instance du `SymbolGraph`.

*   **Arguments**:
    *   `db_path_base` (`str`, optional): Le chemin de base de la base de données SQLite utilisée pour récupérer les informations sur les fichiers. Par défaut à `None`.
*   **Logique interne**:
    *   Stocke le chemin de base de la base de données.
    *   Initialise l'attribut `self.graph` à un `networkx.DiGraph()` si `networkx` est disponible.
    *   Affiche un avertissement si `networkx` n'est pas disponible, indiquant que les fonctionnalités du graphe seront limitées.

#### `extract_dependencies(self, file_path: str) -> Tuple[List[str], List[str]]`

Extrait les dépendances (imports et appels de fonctions basiques) d'un fichier Python donné.

*   **Arguments**:
    *   `file_path` (`str`): Le chemin absolu du fichier Python à analyser.
*   **Retours**:
    *   `Tuple[List[str], List[str]]`: Un tuple contenant deux listes :
        *   La première liste contient les noms des modules importés.
        *   La seconde liste contient des chaînes représentant des appels de fonctions ou méthodes détectés (ex: "module.function", "Class.method").
*   **Logique interne**:
    *   Vérifie si le fichier existe et s'il est un fichier Python (`.py`).
    *   Lit le contenu du fichier.
    *   **Extraction des imports**: Parcourt les lignes du fichier à la recherche de lignes commençant par `import ` ou `from `.
    *   **Extraction des appels de fonctions**: Utilise une expression régulière simple (`r'(\w+)\.(\w+)\s*\('`) pour trouver des motifs comme `module.function()` ou `Class.method()`.
    *   Note qu'une implémentation plus robuste nécessiterait un analyseur syntaxique (comme Tree-sitter ou l'AST Python).
    *   Capture et loggue les exceptions survenant pendant l'extraction.

#### `build_graph_from_db(self)`

Construit le graphe de symboles en utilisant les informations stockées dans la base de données.

*   **Arguments**: Aucun.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   Vérifie la disponibilité de `networkx`.
    *   Récupère le chemin de la base de données SQLite via `_get_paths` (importé localement depuis `.database`).
    *   Vérifie l'existence du fichier de base de données.
    *   Se connecte à la base de données SQLite.
    *   Récupère tous les chemins de fichiers de la table `files`.
    *   Pour chaque fichier, appelle `extract_dependencies` pour obtenir ses imports et appels.
    *   Ajoute un nœud pour chaque fichier au graphe.
    *   Pour chaque import détecté, tente de trouver un fichier correspondant dans le projet et ajoute une arête dirigée (dépendance) du fichier source vers le fichier importé.
    *   Loggue le nombre de nœuds et d'arêtes du graphe construit.
    *   Gère et loggue les erreurs de connexion à la base de données ou de construction du graphe.

#### `calculate_pagerank(self, damping: float = 0.85, max_iter: int = 100) -> Dict[str, float]`

Calcule le PageRank des nœuds (fichiers) dans le graphe pour identifier leur importance relative.

*   **Arguments**:
    *   `damping` (`float`, optional): Le facteur d'amortissement utilisé dans l'algorithme PageRank. Par défaut à `0.85`.
    *   `max_iter` (`int`, optional): Le nombre maximal d'itérations pour le calcul du PageRank. Par défaut à `100`.
*   **Retours**:
    *   `Dict[str, float]`: Un dictionnaire où les clés sont les chemins des fichiers et les valeurs sont leurs scores PageRank. Retourne un dictionnaire vide si `networkx` n'est pas disponible, si le graphe est vide, ou en cas d'erreur.
*   **Logique interne**:
    *   Vérifie la disponibilité de `networkx` et l'existence du graphe.
    *   Vérifie si le graphe contient des nœuds.
    *   Appelle `nx.pagerank()` pour calculer les scores.
    *   Loggue le succès ou l'échec du calcul.

#### `get_top_files(self, n: int = 10) -> List[Tuple[str, float]]`

Retourne les `N` fichiers les plus centraux du projet, basés sur leurs scores PageRank.

*   **Arguments**:
    *   `n` (`int`, optional): Le nombre de fichiers les mieux classés à retourner. Par défaut à `10`.
*   **Retours**:
    *   `List[Tuple[str, float]]`: Une liste de tuples, où chaque tuple contient le chemin d'un fichier et son score PageRank. La liste est triée par score PageRank décroissant. Retourne une liste vide si aucun score PageRank n'est disponible.
*   **Logique interne**:
    *   Appelle `calculate_pagerank()` pour obtenir les scores de tous les fichiers.
    *   Trie les fichiers par score PageRank décroissant.
    *   Retourne les `n` premiers fichiers.

#### `save_to_db(self)`

Méthode de placeholder pour sauvegarder le graphe ou ses métadonnées dans la base de données.

*   **Arguments**: Aucun.
*   **Retours**: Aucun.
*   **Logique interne**:
    *   Actuellement non implémentée (`TODO`).

---

### `get_symbol_graph(db_path_base=None) -> SymbolGraph`

Fonction utilitaire pour obtenir l'instance singleton du graphe de symboles.

Cette fonction assure qu'une seule instance de `SymbolGraph` est créée et utilisée à travers l'application, et qu'elle est correctement initialisée à partir de la base de données la première fois qu'elle est demandée.

*   **Arguments**:
    *   `db_path_base` (`str`, optional): Le chemin de base de la base de données. Utilisé uniquement lors de la première création de l'instance. Par défaut à `None`.
*   **Retours**:
    *   `SymbolGraph`: L'instance unique du `SymbolGraph`.
*   **Logique interne**:
    *   Vérifie si l'instance globale `_symbol_graph_instance` est `None`.
    *   Si c'est le cas, crée une nouvelle instance de `SymbolGraph` avec `db_path_base`, appelle `build_graph_from_db()` sur cette instance pour la populer, puis la stocke dans `_symbol_graph_instance`.
    *   Retourne l'instance (nouvellement créée ou existante).

---

## Exemple d'Usage

```python
import os
from config import get_path
from features.context.symbol_graph import get_symbol_graph

# Assurez-vous que le chemin de base est configuré pour votre projet
# Par exemple, si votre base de données est dans ./.data/
# db_base_path = get_path(".data")

# Dans un contexte réel, db_path_base serait souvent défini via une configuration globale
# Pour cet exemple, supposons que la base de données est déjà créée et peuplée
# par d'autres modules de `features.context.database`

# Obtenir l'instance singleton du graphe de symboles
# La première fois, cela construira le graphe à partir de la DB.
# Les appels suivants retourneront l'instance existante.
symbol_graph_manager = get_symbol_graph() # db_path_base peut être passé ici si nécessaire

if symbol_graph_manager.graph is None:
    print("NetworkX n'est pas disponible ou le graphe n'a pas pu être construit.")
else:
    print(f"Graphe prêt avec {len(symbol_graph_manager.graph.nodes)} nœuds et {len(symbol_graph_manager.graph.edges)} arêtes.")

    # Calculer et afficher les 5 fichiers les plus centraux
    print("\nTop 5 des fichiers les plus centraux (par PageRank):")
    top_files = symbol_graph_manager.get_top_files(n=5)
    if top_files:
        for i, (file_path, score) in enumerate(top_files):
            print(f"{i+1}. {os.path.basename(file_path)} (Score: {score:.4f})")
    else:
        print("Aucun fichier trouvé ou PageRank non calculable.")

    # Exemple d'extraction de dépendances pour un fichier spécifique (sans passer par la DB)
    # Ceci est juste pour montrer l'utilisation de la méthode seule
    example_file = os.path.abspath(__file__) # Utiliser ce fichier lui-même comme exemple
    imports, calls = symbol_graph_manager.extract_dependencies(example_file)
    print(f"\nDépendances extraites de '{os.path.basename(example_file)}':")
    print(f"  Imports: {imports}")
    print(f"  Appels (basique): {calls}")