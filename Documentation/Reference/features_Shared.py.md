# Documentation Technique - `features\Shared.py`

## 1. En-tête

### Titre
`features\Shared.py`

### Description concise
Ce module fournit un ensemble de fonctions utilitaires partagées à travers l'application, incluant un système de journalisation d'audit, un wrapper pour la gestion des sauvegardes, un vérificateur de syntaxe Python, et un `OmniscientResolver` sophistiqué pour la résolution de chemins de fichiers basée sur plusieurs stratégies (exacte, heuristique, floue, RAG, et sémantique via IA).

### Dépendances
*   **Modules internes**:
    *   `os`
    *   `json`
    *   `logging`
    *   `ast`
    *   `time`
*   **Modules du projet**:
    *   `config.paths` (pour `get_path`)
    *   `config.settings` (pour `APP_SETTINGS`)
    *   `features.Decorators` (pour `@trace_action`)
    *   `features.core_backup` (importé dynamiquement)
    *   `features.context.database` (importé dynamiquement)
    *   `ai_core.factory`, `ai_core.sessions` (importés dynamiquement)

## 2. Classes & Fonctions

### Fonctions

#### `log_action`
Enregistre une action spécifique dans un journal d'audit au format JSON. Ce journal est utilisé pour suivre les opérations critiques ou importantes au sein de l'application.

*   **Signature**:
    ```python
    @trace_action(source="Shared")
    def log_action(action_type: str, details: str, target: str, log_path: str = "action_log.json") -> None
    ```
*   **Arguments**:
    *   `action_type` (str): Le type d'action effectuée (ex: "file_save", "config_update").
    *   `details` (str): Une description plus détaillée de l'action.
    *   `target` (str): L'entité ou le fichier affecté par l'action (ex: "my_file.py", "global_settings").
    *   `log_path` (str, optional): Le chemin relatif du fichier journal. Par défaut: `"action_log.json"`.
*   **Retours**:
    *   `None`
*   **Logique interne**:
    1.  Crée une entrée de journal avec un horodatage (`timestamp`), le type d'action (`action`), les détails (`details`) et la cible (`target`).
    2.  Détermine le chemin absolu du fichier journal via `get_path()`.
    3.  Charge les entrées existantes du journal ou initialise une liste vide si le fichier n'existe pas ou est corrompu.
    4.  Ajoute la nouvelle entrée à la liste.
    5.  Tronque le journal pour ne conserver que les 1000 dernières entrées afin d'éviter une croissance excessive du fichier.
    6.  Écrit la liste mise à jour dans le fichier journal au format JSON avec une indentation de 2 espaces et sans caractères ASCII échappés.
    7.  Capture et loggue les exceptions potentielles.

#### `_creer_backup_snapshot`
Un wrapper pour la fonction de création de sauvegarde du module `features.core_backup`. Cette fonction est conçue pour être appelée en interne ou via d'autres mécanismes pour initier une sauvegarde du projet.

*   **Signature**:
    ```python
    @trace_action(source="Shared")
    def _creer_backup_snapshot() -> Optional[Any]
    ```
*   **Arguments**:
    *   `None`
*   **Retours**:
    *   `Optional[Any]`: Le résultat de `core_backup.create_backup()` si l'opération réussit, sinon `None`.
*   **Logique interne**:
    1.  Importe dynamiquement `features.core_backup` pour éviter les dépendances circulaires au démarrage du module.
    2.  Appelle la fonction `create_backup()` de `core_backup`.
    3.  Capture et loggue les exceptions potentielles, retournant `None` en cas d'erreur.

#### `verifier_syntaxe_python`
Vérifie la validité de la syntaxe d'un morceau de code Python donné en utilisant le module `ast` pour tenter de le parser.

*   **Signature**:
    ```python
    @trace_action(source="Shared")
    def verifier_syntaxe_python(code: str, filename: str = "temp.py") -> Tuple[bool, str]
    ```
*   **Arguments**:
    *   `code` (str): La chaîne de caractères contenant le code Python à vérifier.
    *   `filename` (str, optional): Nom de fichier virtuel utilisé pour le parsing AST (utile pour les messages d'erreur). Par défaut: `"temp.py"`.
*   **Retours**:
    *   `Tuple[bool, str]`: Un tuple où le premier élément est `True` si la syntaxe est valide, `False` sinon. Le second élément est un message décrivant le résultat ou l'erreur spécifique.
*   **Logique interne**:
    1.  Tente de parser le `code` en utilisant `ast.parse()`.
    2.  Si le parsing réussit, retourne `(True, "Syntaxe Valide")`.
    3.  Capture `SyntaxError` pour fournir un message d'erreur détaillé incluant le numéro de ligne.
    4.  Capture toute autre `Exception` générique pour les erreurs inattendues.

### Classe `OmniscientResolver`

Le `OmniscientResolver` est un système de résolution de chemins centralisé, conçu pour transformer des requêtes de chemin potentiellement floues ou incomplètes en chemins de fichiers relatifs réels dans le projet. Il utilise une stratégie en cascade pour maximiser la performance et la précision.

*   **Description**:
    Le GPS central du projet, utilisant une stratégie de résolution en 5 niveaux, allant de la recherche exacte et heuristique rapide à l'intelligence artificielle sémantique comme dernier recours.

#### `_get_recency_score` (méthode statique)
Calcule un score de "récence" pour un fichier donné, basé sur son temps de dernière modification. Les fichiers modifiés plus récemment reçoivent un score plus élevé.

*   **Signature**:
    ```python
    @staticmethod
    @trace_action(source="Shared")
    def _get_recency_score(filepath: str) -> int
    ```
*   **Arguments**:
    *   `filepath` (str): Le chemin absolu du fichier.
*   **Retours**:
    *   `int`: Un score de récence (10 pour moins d'une heure, 5 pour moins d'un jour, 0 sinon).
*   **Logique interne**:
    1.  Récupère le temps de dernière modification du fichier (`mtime`).
    2.  Calcule l'âge du fichier en secondes.
    3.  Attribue un score: 10 si l'âge est < 1 heure, 5 si l'âge est < 24 heures, 0 sinon.
    4.  Gère les exceptions en retournant 0.

#### `resolve` (méthode statique)
La méthode principale du `OmniscientResolver` pour trouver un chemin de fichier réel à partir d'une requête.

*   **Signature**:
    ```python
    @staticmethod
    @trace_action(source="Shared")
    def resolve(query: str, allow_ai: bool = False) -> Optional[str]
    ```
*   **Arguments**:
    *   `query` (str): La requête de chemin potentiellement floue ou incomplète.
    *   `allow_ai` (bool, optional): Si `True`, autorise l'appel au modèle d'IA sémantique en dernier recours. Par défaut: `False` pour éviter la latence dans les outils automatiques.
*   **Retours**:
    *   `Optional[str]`: Le chemin relatif résolu par rapport à la racine du projet, ou `None` si aucun chemin n'est trouvé.
*   **Logique interne**:
    1.  **Pré-traitement**: Nettoie la requête.
    2.  **Niveau 1 : Exactitude & Dictionnaire (Instant) **:
        *   Tente une correspondance directe du chemin (`get_path(query)`).
        *   Consulte un dictionnaire `COMMON_LOCATIONS` pour les fichiers fréquemment mal nommés ou recherchés.
        *   Tente d'ajouter des extensions courantes (`.py`, `.json`, `.md`).
    3.  **Niveau 2 : Fuzzy Search (Rapide) **:
        *   Parcourt récursivement la racine du projet (en ignorant certains répertoires).
        *   Calcule un score pour chaque fichier basé sur:
            *   Correspondance exacte du nom de fichier.
            *   Correspondance partielle (sous-chaîne).
            *   Correspondance des parties de la requête.
            *   Le score de récence (`_get_recency_score`).
        *   Retourne le meilleur match si son score dépasse un seuil de confiance (80).
    4.  **Niveau 3 : RAG (Base Vectorielle) **:
        *   Tente d'importer `features.context.database` dynamiquement.
        *   Si disponible, effectue une recherche dans la base de données vectorielle RAG avec la requête.
        *   Si un résultat pertinent (score < 1.5) est trouvé, le retourne.
    5.  **Niveau 4 : IA Sémantique (Coûteux - Optionnel) **:
        *   Si `allow_ai` est `True`, appelle la méthode `_semantic_ai_resolve` pour une résolution via LLM.
    6.  **Dernier recours**: Si rien n'est trouvé aux niveaux supérieurs, mais qu'un match fuzzy a été trouvé avec un score modéré (supérieur à 40), ce dernier est retourné.
    7.  Si aucune résolution n'est possible à travers toutes les stratégies, retourne `None`.

#### `_semantic_ai_resolve` (méthode statique)
Appelle un modèle d'IA sémantique (LLM) pour tenter de résoudre un chemin de fichier à partir d'une requête conceptuelle ou floue.

*   **Signature**:
    ```python
    @staticmethod
    @trace_action(source="Shared")
    def _semantic_ai_resolve(query: str) -> Optional[str]
    ```
*   **Arguments**:
    *   `query` (str): La requête conceptuelle ou floue pour le chemin.
*   **Retours**:
    *   `Optional[str]`: Le chemin relatif suggéré par l'IA, ou `None` si l'IA ne peut pas résoudre ou si une erreur se produit.
*   **Logique interne**:
    1.  Tente d'importer dynamiquement `ai_core.factory` et `ai_core.sessions`.
    2.  Crée une session IA de type "router".
    3.  Construit un prompt pour l'IA, lui demandant d'agir comme un résolveur de chemin et incluant un échantillon de la structure du projet.
    4.  Appelle l'IA via `call_ai_robust` et nettoie le résultat.
    5.  Si l'IA retourne un chemin valide et existant, le loggue et le retourne.
    6.  Gère les exceptions en retournant `None`.

### Alias

#### `smart_resolve_path`
Un alias pour la méthode `OmniscientResolver.resolve` avec `allow_ai` défini à `False`. Utile pour les appels où la latence de l'IA n'est pas souhaitable.

*   **Signature**:
    ```python
    smart_resolve_path = lambda q: OmniscientResolver.resolve(q, allow_ai=False)
    ```
*   **Arguments**:
    *   `q` (str): La requête de chemin.
*   **Retours**:
    *   `Optional[str]`: Le chemin relatif résolu ou `None`.

## 3. Exemple d'usage

```python
import os
from features.Shared import log_action, verifier_syntaxe_python, OmniscientResolver, smart_resolve_path

# --- Exemple de log_action ---
log_action("configuration_update", "Mise à jour du paramètre 'theme'", "config/settings.json")
# Vérifiez le fichier 'action_log.json' qui sera créé ou mis à jour.

# --- Exemple de verifier_syntaxe_python ---
code_valide = "def greet(name):\n    return f'Hello, {name}'"
code_invalide = "def greet(name):\n    return f'Hello, {name}'\n    print('error'"

valide, msg_valide = verifier_syntaxe_python(code_valide)
print(f"Code valide: {valide}, Message: {msg_valide}")

invalide, msg_invalide = verifier_syntaxe_python(code_invalide)
print(f"Code invalide: {invalide}, Message: {msg_invalide}")

# --- Exemple de OmniscientResolver.resolve et smart_resolve_path ---

# Création de fichiers temporaires pour l'exemple
# Assurez-vous que le répertoire 'config' existe à la racine du projet
if not os.path.exists("config"):
    os.makedirs("config")
with open("config/temp_settings.py", "w") as f:
    f.write("# Temp settings file")
with open("ui/temp_window.py", "w") as f:
    f.write("# Temp UI window")
with open("temp_doc.md", "w") as f:
    f.write("## Temporary Documentation")

print("\n--- OmniscientResolver Examples ---")

# 1. Exactitude
resolved_path = OmniscientResolver.resolve("config/temp_settings.py")
print(f"Resolve 'config/temp_settings.py': {resolved_path}") # Devrait être 'config/temp_settings.py'

# 2. Dictionnaire critique
resolved_path = OmniscientResolver.resolve("settings.py")
print(f"Resolve 'settings.py' (dict): {resolved_path}") # Devrait être 'config/settings.py' (si il existe)

# 3. Extension implicite
resolved_path = OmniscientResolver.resolve("temp_doc")
print(f"Resolve 'temp_doc': {resolved_path}") # Devrait être 'temp_doc.md'

# 4. Fuzzy Search
resolved_path = OmniscientResolver.resolve("temp settings")
print(f"Resolve 'temp settings' (fuzzy): {resolved_path}") # Devrait être 'config/temp_settings.py'

resolved_path = OmniscientResolver.resolve("ui window")
print(f"Resolve 'ui window' (fuzzy): {resolved_path}") # Devrait être 'ui/temp_window.py'

# 5. Utilisation de l'alias smart_resolve_path
resolved_path_alias = smart_resolve_path("temp settings")
print(f"Smart resolve 'temp settings': {resolved_path_alias}")

# 6. Résolution IA (nécessite allow_ai=True et un setup AI fonctionnel)
# Note: Cette partie est commentée car elle peut être coûteuse et dépend d'une configuration spécifique.
# resolved_ai_path = OmniscientResolver.resolve("find my main window", allow_ai=True)
# print(f"Resolve 'find my main window' (AI): {resolved_ai_path}")

# Nettoyage des fichiers temporaires
os.remove("config/temp_settings.py")
os.remove("ui/temp_window.py")
os.remove("temp_doc.md")