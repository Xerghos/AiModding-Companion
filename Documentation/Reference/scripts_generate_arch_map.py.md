# Documentation Technique: `scripts/generate_arch_map.py`

## Description

Ce script Python a pour objectif de générer une cartographie détaillée de l'architecture d'un projet. Il analyse le code source Python pour extraire des métriques, identifier la structure du code (classes, fonctions, variables globales), détecter la dette technique (TODOs, FIXMEs) et résoudre les dépendances entre les modules. Le résultat final est un fichier JSON (`architecture_map.json`) qui peut être utilisé par d'autres outils pour visualiser l'architecture du projet.

## Dépendances

Ce script utilise les bibliothèques Python standard suivantes :
* `os`: Pour les interactions avec le système de fichiers (parcours de répertoires, gestion des chemins).
* `ast`: Pour l'analyse syntaxique du code Python et la construction d'un Abstract Syntax Tree (AST).
* `json`: Pour la sérialisation des données d'architecture au format JSON.
* `logging`: Pour enregistrer les informations et les erreurs pendant l'exécution.
* `time`: Pour horodater la génération de la carte d'architecture.
* `sys`: Utilisé potentiellement pour des opérations liées au système, bien que son utilisation directe soit minime dans le code actuel.
* `re`: Pour l'utilisation d'expressions régulières (pas directement visible dans ce snippet mais potentiellement utile pour des analyses plus fines).

Il n'y a pas de dépendances externes requises (pas d'installation `pip install`).

---

## Classes & Fonctions

### `get_project_root()`

*   **Signature:** `def get_project_root() -> str`
*   **Arguments:** Aucun.
*   **Retour:**
    *   `str`: Le chemin absolu vers la racine du projet.
*   **Logique Interne:**
    Détermine le chemin absolu du répertoire du script en cours (`__file__`) et remonte d'un niveau pour identifier la racine du projet.

---

### `analyze_file_metrics(file_path: str)`

*   **Signature:** `def analyze_file_metrics(file_path: str) -> dict`
*   **Arguments:**
    *   `file_path` (`str`): Chemin absolu vers le fichier Python à analyser.
*   **Retour:**
    *   `dict`: Un dictionnaire contenant les métriques du fichier :
        *   `"loc"` (`int`): Nombre de lignes de code (Line of Code).
        *   `"comments"` (`int`): Nombre de lignes de commentaires (commençant par `#`).
        *   `"todos"` (`list[str]`): Liste des commentaires TODO trouvés, formatés avec le numéro de ligne.
        *   `"fixmes"` (`list[str]`): Liste des commentaires FIXME trouvés, formatés avec le numéro de ligne.
*   **Logique Interne:**
    Ouvre le fichier spécifié, lit toutes ses lignes, compte le nombre total de lignes (`loc`), compte les lignes de commentaires, et recherche les marqueurs `# TODO` et `# FIXME` pour extraire les messages associés. Gère les erreurs d'ouverture ou de lecture de fichier en loggant un avertissement.

---

### `CodeAnalyzer(ast.NodeVisitor)`

Cette classe hérite de `ast.NodeVisitor` pour parcourir l'Abstract Syntax Tree (AST) d'un fichier Python et en extraire des informations structurelles.

*   **Initialisation (`__init__`)**:
    *   Initialise un dictionnaire `self.stats` pour stocker les résultats :
        *   `"classes"` (`dict`): Stocke les informations sur les classes définies.
        *   `"functions"` (`list`): Stocke les informations sur les fonctions définies au niveau du module.
        *   `"globals"` (`list`): Stocke les noms des variables globales (en majuscules).
        *   `"imports"` (`set`): Stocke les noms des modules importés.
        *   `"complexity"` (`int`): Cumul de la complexité cyclomatique calculée pour le module.
    *   Initialise `self.current_class` à `None` pour suivre le contexte lors de la visite des nœuds.

*   **`visit_Import(self, node)`**:
    *   Parcourt les `alias` dans `node.names` et ajoute le nom de chaque module importé (`alias.name`) à `self.stats["imports"]`.
    *   Appelle `self.generic_visit(node)` pour continuer la visite des nœuds enfants.

*   **`visit_ImportFrom(self, node)`**:
    *   Si `node.module` existe (c'est-à-dire que ce n'est pas un import relatif sans spécifier le module), ajoute le nom du module (`node.module`) à `self.stats["imports"]`.
    *   Appelle `self.generic_visit(node)`.

*   **`visit_ClassDef(self, node)`**:
    *   Extrait le nom de la classe (`node.name`), le numéro de ligne (`node.lineno`), la docstring (`ast.get_docstring(node)`), et les noms des classes mères (`bases`).
    *   Crée un dictionnaire `class_info` pour stocker ces détails ainsi qu'une liste vide pour les méthodes (`"methods"`).
    *   Sauvegarde le contexte de la classe parente (`self.current_class`) avant de définir la classe actuelle.
    *   Passe au mode visite de la classe actuelle (`self.current_class = class_info`).
    *   Appelle `self.generic_visit(node)` pour visiter le contenu de la classe (méthodes, etc.).
    *   Ajoute les informations de la classe au dictionnaire `self.stats["classes"]`.
    *   Restaure le contexte de la classe parente (`self.current_class = prev_class`).

*   **`visit_FunctionDef(self, node)`**:
    *   Calcule une mesure simplifiée de la complexité cyclomatique (à partir de 1, +1 pour chaque `If`, `For`, `While`, `Try`, `ExceptHandler` trouvé dans le corps de la fonction).
    *   Extrait le nom de la fonction (`node.name`), le numéro de ligne (`node.lineno`), les noms des arguments (`node.args.args`), la docstring, la complexité calculée, et les noms des décorateurs.
    *   Si `self.current_class` n'est pas `None`, ajoute les informations de la fonction à la liste des méthodes de la classe courante (`self.current_class["methods"]`).
    *   Sinon (fonction au niveau du module), ajoute les informations à `self.stats["functions"]`.
    *   Met à jour la complexité globale du module (`self.stats["complexity"]`).
    *   Appelle `self.generic_visit(node)`.

*   **`visit_Assign(self, node)`**:
    *   Vérifie si l'assignation se fait au niveau du module (pas dans une classe, `not self.current_class`).
    *   Pour chaque cible de l'assignation (`node.targets`), si c'est un `ast.Name` et que son identifiant (`target.id`) est entièrement en majuscules, il est considéré comme une constante globale et ajouté à `self.stats["globals"]`.
    *   Appelle `self.generic_visit(node)`.

---

### `analyze_file_ast(file_path: str)`

*   **Signature:** `def analyze_file_ast(file_path: str) -> dict`
*   **Arguments:**
    *   `file_path` (`str`): Chemin absolu vers le fichier Python à analyser.
*   **Retour:**
    *   `dict`: Un dictionnaire contenant :
        *   `"module_doc"` (`str` or `None`): La docstring du module, ou `None` si absente.
        *   `"structure"` (`dict`): Les statistiques extraites par `CodeAnalyzer` (classes, fonctions, globals, imports, complexity).
*   **Logique Interne:**
    Crée une instance de `CodeAnalyzer`. Ouvre et lit le contenu du fichier, puis utilise `ast.parse()` pour construire l'arbre syntaxique. La méthode `visit()` de l'analyser est appelée pour parcourir l'arbre. La docstring du module est également extraite. En cas d'erreur d'analyse, un avertissement est loggué et un dictionnaire partiel est retourné.

---

### `resolve_dependencies(imports: set, current_file_path: str, root_path: str, all_files_set: set)`

*   **Signature:** `def resolve_dependencies(imports: set, current_file_path: str, root_path: str, all_files_set: set) -> list[str]`
*   **Arguments:**
    *   `imports` (`set`): Ensemble des noms de modules importés par le fichier courant.
    *   `current_file_path` (`str`): Chemin relatif du fichier courant par rapport à la racine du projet.
    *   `root_path` (`str`): Chemin absolu vers la racine du projet.
    *   `all_files_set` (`set`): Ensemble de tous les chemins relatifs des fichiers Python du projet pour une recherche rapide.
*   **Retour:**
    *   `list[str]`: Une liste de chemins relatifs des fichiers du projet qui sont directement dépendants (importés) par le fichier courant.
*   **Logique Interne:**
    Pour chaque nom d'importation, tente de le mapper à un fichier Python existant dans le projet.
    1.  Convertit la notation par points de l'import (`com.example.module`) en chemin de répertoire (`com/example/module`).
    2.  Génère des candidats de chemin de fichier : `module.py` et `module/__init__.py`.
    3.  Vérifie si ces candidats existent en tant que chemins absolus à partir de `root_path`.
    4.  Si un fichier candidat est trouvé et qu'il fait partie de `all_files_set` (et n'est pas le fichier courant lui-même), son chemin relatif est ajouté à la liste des dépendances résolues.
    La fonction retourne une liste unique des dépendances résolues.

---

### `generate_ultimate_graph()`

*   **Signature:** `def generate_ultimate_graph() -> bool`
*   **Arguments:** Aucun.
*   **Retour:**
    *   `bool`: `True` si la génération et la sauvegarde ont réussi, `False` sinon.
*   **Logique Interne:**
    C'est la fonction principale qui orchestre tout le processus :
    1.  **Recensement:**
        *   Détermine la racine du projet via `get_project_root()`.
        *   Parcourt récursivement l'arborescence du projet à l'aide de `os.walk()`.
        *   Ignore les répertoires listés dans `IGNORED_DIRS` et les fichiers dans `IGNORED_FILES`.
        *   Collecte les chemins relatifs de tous les fichiers `.py` dans `all_files` et `all_files_set`.
    2.  **Analyse Profonde:**
        *   Itère sur chaque fichier Python identifié.
        *   Pour chaque fichier, appelle `analyze_file_metrics()` pour obtenir les métriques brutes.
        *   Appelle `analyze_file_ast()` pour obtenir la structure du code via AST.
        *   Appelle `resolve_dependencies()` pour identifier les imports directs vers d'autres fichiers du projet.
        *   Construit une entrée pour ce fichier dans le dictionnaire `graph`. Cette entrée contient le type, la docstring, les métriques (loc, complexité, todos, fixmes), les définitions (classes, fonctions, globals), et les dépendances directes. Le champ `"used_by"` est initialisé vide.
    3.  **Passe 2 (Rétroliens):**
        *   Itère sur le `graph` généré.
        *   Pour chaque fichier et ses dépendances (`data["dependencies"]`), ajoute le fichier courant à la liste `"used_by"` des fichiers dépendants. Cela permet de savoir quels fichiers utilisent un module donné.
    4.  **Génération Domains:**
        *   Crée une structure `domains` groupant les fichiers par leur répertoire de premier niveau (ou 'root' s'ils sont à la racine).
    5.  **Sauvegarde:**
        *   Prépare un dictionnaire `output_data` contenant des métadonnées (date, version), le `graph` complet, et les `domains`.
        *   Crée le répertoire `config` s'il n'existe pas.
        *   Sauvegarde `output_data` dans `config/architecture_map.json` au format JSON indenté.
        *   Loggue des messages de succès ou d'erreur.
        *   Affiche les 3 fichiers les plus complexes du projet en termes de complexité cyclomatique.
        *   Retourne `True` en cas de succès, `False` en cas d'erreur d'écriture.

---

## Exemple d'usage

Le script est conçu pour être exécuté directement depuis la ligne de commande dans le répertoire racine du projet.

```bash
cd /chemin/vers/votre/projet
python scripts/generate_arch_map.py
```

Après l'exécution, un fichier `architecture_map.json` sera créé dans le sous-répertoire `config/` à la racine de votre projet. Ce fichier contiendra la structure d'analyse et les dépendances de votre projet.

Ce fichier JSON peut ensuite être utilisé par des outils de visualisation d'architecture (non fournis par ce script) pour générer des diagrammes interactifs.