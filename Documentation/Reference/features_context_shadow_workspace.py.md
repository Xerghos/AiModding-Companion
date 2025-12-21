# Documentation Technique du Module `shadow_workspace.py`

## 1. En-tête

### Titre
Module Shadow Workspace pour la Validation de Code

### Description Concise
Ce module implémente un "Shadow Workspace", une alternative légère à un LSP complet, conçue pour valider syntaxiquement et sémantiquement le code Python généré avant sa présentation. Il intègre des vérifications de syntaxe basées sur l'AST et, si disponible, l'utilisation de linters externes comme Ruff ou Flake8. Il offre également des fonctionnalités pour générer des prompts de correction pour une IA.

### Dépendances
*   **Modules standards Python**: `os`, `logging`, `ast`, `subprocess`, `typing` (Tuple, List, Optional), `tempfile`
*   **Modules internes**:
    *   `config.get_logger`: Pour la gestion des journaux d'événements.
    *   `features.Decorators.trace_action`: Pour le traçage des actions exécutées par le workspace.

## 2. Classes & Fonctions

### Classe: `ShadowWorkspace`

Workspace fantôme pour la validation du code généré.
Valide syntaxiquement et sémantiquement le code avant présentation.

#### `__init__(self, use_linter: bool = True)`
*   **Signature**: `__init__(self, use_linter: bool = True)`
*   **Arguments**:
    *   `use_linter` (bool, optionnel): Si `True`, le workspace tentera d'utiliser un linter externe (Ruff ou Flake8) pour des validations supplémentaires. Par défaut à `True`.
*   **Logique interne**:
    Initialise l'instance du workspace et configure l'utilisation du linter. Appelle la méthode privée `_check_linter_available` pour déterminer si un linter est accessible dans l'environnement actuel.

#### `_check_linter_available(self) -> bool`
*   **Signature**: `_check_linter_available(self) -> bool`
*   **Arguments**: Aucun.
*   **Retours**:
    *   `bool`: `True` si un linter (Ruff ou Flake8) est détecté et disponible pour utilisation, `False` sinon.
*   **Logique interne**:
    Cette méthode privée vérifie la présence de linters. Elle tente d'abord de lancer `ruff --version`. Si Ruff n'est pas trouvé ou échoue, elle essaie `flake8 --version`. Un journal d'information est émis si un linter est trouvé, ou un avertissement si aucun n'est disponible.

#### `validate_syntax(self, code: str, filename: str = "temp.py") -> Tuple[bool, List[str]]`
*   **Signature**: `validate_syntax(self, code: str, filename: str = "temp.py") -> Tuple[bool, List[str]]`
*   **Arguments**:
    *   `code` (str): La chaîne de caractères représentant le code Python à valider.
    *   `filename` (str, optionnel): Le nom de fichier à utiliser dans les messages d'erreur (par exemple, "temp.py"). Par défaut à `"temp.py"`.
*   **Retours**:
    *   `Tuple[bool, List[str]]`: Un tuple contenant un booléen indiquant si le code est valide (`True`) ou non (`False`), et une liste de chaînes de caractères décrivant les erreurs détectées.
*   **Logique interne**:
    Cette méthode effectue une double validation :
    1.  **Validation AST**: Elle tente de parser le `code` en utilisant `ast.parse()`. Toute `SyntaxError` ou autre exception lors du parsing est capturée et ajoutée à la liste des erreurs.
    2.  **Validation Linter**: Si un linter est disponible (`self.linter_available` est `True`), elle appelle la méthode privée `_run_linter` pour obtenir des erreurs supplémentaires de style ou de conformité.
    La méthode retourne `True` si aucune erreur n'a été trouvée par l'AST ni par le linter, et la liste complète des erreurs.
*   **Décorateurs**: `@trace_action(source="shadow_workspace")`

#### `_run_linter(self, code: str, filename: str) -> List[str]`
*   **Signature**: `_run_linter(self, code: str, filename: str) -> List[str]`
*   **Arguments**:
    *   `code` (str): Le code Python à analyser par le linter.
    *   `filename` (str): Le nom de fichier à utiliser pour le linter (généralement un fichier temporaire).
*   **Retours**:
    *   `List[str]`: Une liste de chaînes de caractères, chaque chaîne représentant une erreur ou un avertissement du linter.
*   **Logique interne**:
    Cette méthode privée est responsable de l'exécution du linter.
    1.  Elle crée un fichier temporaire sur le système de fichiers et y écrit le `code` fourni.
    2.  Elle tente d'exécuter `ruff check` sur ce fichier temporaire. Si Ruff retourne des erreurs, elles sont capturées.
    3.  Si Ruff n'est pas disponible ou échoue, elle tente d'exécuter `flake8` sur le même fichier temporaire. Si Flake8 retourne des erreurs, elles sont capturées.
    4.  Dans un bloc `finally`, le fichier temporaire est supprimé pour garantir un nettoyage.
    Les sorties des linters sont analysées ligne par ligne pour extraire les messages d'erreur.

#### `validate_and_correct(self, code: str, filename: str = "temp.py", max_iterations: int = 3) -> Tuple[str, List[str]]`
*   **Signature**: `validate_and_correct(self, code: str, filename: str = "temp.py", max_iterations: int = 3) -> Tuple[str, List[str]]`
*   **Arguments**:
    *   `code` (str): Le code Python à valider et potentiellement corriger.
    *   `filename` (str, optionnel): Le nom de fichier pour les messages d'erreur. Par défaut à `"temp.py"`.
    *   `max_iterations` (int, optionnel): Le nombre maximum d'itérations pour tenter une auto-correction (non implémenté directement dans cette fonction, mais fourni en paramètre). Par défaut à `3`.
*   **Retours**:
    *   `Tuple[str, List[str]]`: Un tuple contenant le code (potentiellement inchangé) et une liste d'erreurs détectées.
*   **Logique interne**:
    Appelle `validate_syntax` pour évaluer le code. Si le code est valide, il est retourné tel quel avec une liste d'erreurs vide. Sinon, le code original et les erreurs détectées sont retournés. Actuellement, cette fonction ne met pas en œuvre un mécanisme d'auto-correction itératif mais fournit le cadre pour une telle implémentation.
*   **Décorateurs**: `@trace_action(source="shadow_workspace")`

#### `create_correction_prompt(self, code: str, errors: List[str]) -> str`
*   **Signature**: `create_correction_prompt(self, code: str, errors: List[str]) -> str`
*   **Arguments**:
    *   `code` (str): Le code Python qui contient des erreurs.
    *   `errors` (List[str]): Une liste de chaînes de caractères décrivant les erreurs détectées dans le code.
*   **Retours**:
    *   `str`: Une chaîne de caractères formatée, destinée à être utilisée comme prompt pour une Intelligence Artificielle afin de lui demander de corriger le code en fonction des erreurs.
*   **Logique interne**:
    Assemble un prompt clair et structuré qui inclut le code original et la liste des erreurs. Le prompt demande à l'IA de corriger le code tout en conservant sa logique originale.
*   **Décorateurs**: `@trace_action(source="shadow_workspace")`

### Fonction: `get_shadow_workspace`

#### `get_shadow_workspace(use_linter: bool = True) -> ShadowWorkspace`
*   **Signature**: `get_shadow_workspace(use_linter: bool = True) -> ShadowWorkspace`
*   **Arguments**:
    *   `use_linter` (bool, optionnel): Si `True`, le workspace tentera d'utiliser un linter externe (Ruff ou Flake8). Par défaut à `True`. Ce paramètre n'a d'effet que lors de la première création de l'instance.
*   **Retours**:
    *   `ShadowWorkspace`: L'instance singleton du `ShadowWorkspace`.
*   **Logique interne**:
    Implémente un motif de conception Singleton pour la classe `ShadowWorkspace`. Si une instance du workspace n'existe pas déjà, elle est créée avec le paramètre `use_linter` spécifié, puis stockée globalement. Les appels ultérieurs à cette fonction retourneront la même instance existante.

## 3. Exemple d'usage

```python
from features.context.shadow_workspace import get_shadow_workspace

# Obtenir l'instance singleton du Shadow Workspace
# Le linter sera vérifié lors du premier appel.
workspace = get_shadow_workspace(use_linter=True)

# Exemple de code avec erreur de syntaxe
code_with_syntax_error = """
def ma_fonction():
    print("Bonjour")
    if True:
        pass
    else
        return False # Erreur: 'else' doit être suivi de ':'
"""

# Valider le code avec erreur
is_valid, errors = workspace.validate_syntax(code_with_syntax_error, filename="my_module.py")

if not is_valid:
    print("Code invalide détecté:")
    for error in errors:
        print(f"- {error}")
    
    # Générer un prompt de correction pour une IA
    correction_prompt = workspace.create_correction_prompt(code_with_syntax_error, errors)
    print("\n--- Prompt de correction pour l'IA ---")
    print(correction_prompt)
else:
    print("Le code est syntaxiquement valide.")

# Exemple de code valide
valid_code = """
def autre_fonction(x: int) -> int:
    \"\"\"Docstring\"\"\"
    if x > 0:
        return x * 2
    else:
        return x
"""

# Valider le code valide
is_valid_clean, errors_clean = workspace.validate_syntax(valid_code)

if is_valid_clean:
    print("\nLe code valide est syntaxiquement correct.")
else:
    print("\nErreurs inattendues dans le code valide:")
    for error in errors_clean:
        print(f"- {error}")

# Le test de linter est effectué à l'initialisation du ShadowWorkspace.
# Si Ruff ou Flake8 est installé, des erreurs de style (par ex. E302, W292) pourraient être rapportées
# pour le 'valid_code' si la configuration du linter l'exige.